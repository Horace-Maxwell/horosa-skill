"""原 9 家客户端的配置位置、精简面缺省与理由、重启提示（其余 16 家在 clients_extra）。"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Mapping

import typer

from horosa_skill import clients_extra
from horosa_skill.config import Settings

_CLIENT_RESTART_HINTS = {
    "claude-code": "新开一个 Claude Code 会话（或重启）；`claude mcp list` 应列出 horosa。",
    "claude-desktop": "完全退出并重开 Claude Desktop（菜单里 Quit，不只是关窗口）；Settings → Developer 里应看到 horosa。",
    "cursor": "重启 Cursor；Settings → MCP 里 horosa 应亮绿灯。",
    "vscode": "重载 VS Code 窗口（Developer: Reload Window）；Copilot Chat 的工具列表里应出现 horosa。",
    "codex": "重启 codex；首轮可能看不到 horosa 工具（冷启动只等 1 s），第二轮即恢复。",
    "gemini": "重启 gemini；`/mcp` 应列出 horosa。",
    "windsurf": "重启 Devin Desktop（原 Windsurf）；Devin Local 的 MCP 列表里应看到 horosa（旧版 Cascade 看 MCP 面板）。",
    "cline": "重载 VS Code 窗口；Cline 的 MCP Servers 面板里应看到 horosa。",
    "zed": "重启 Zed；Agent 面板的 Context Servers 里应看到 horosa。",
    # v0.41.0：另 16 家的提示与其余事实同住 clients_extra（每家一行）。
    **{key: spec.restart_hint for key, spec in clients_extra.EXTRA_CLIENTS.items()},
}


# 各客户端的工具总数上限（实测/官方文档，2026-09）：Cursor 全局约 40 个**静默丢弃**超出部分；
# VS Code Copilot 与 OpenAI 兼容端 128（跨所有 server 共享）；Windsurf 100；Codex 无工具搜索，
# 116 个工具的定义每轮都进上下文（约 7 万 token）。这些客户端默认发精简面（11 个门面工具，
# 全部技法仍可经 horosa_tool_run 按名直达）；Claude Code / Claude Desktop 有工具搜索且无硬上限，
# 保持全量平铺（按名可见 = 更好的发现性）。`--surface full|compact` 可覆盖。
_CLIENT_COMPACT_DEFAULT = {
    "cursor": True,
    "vscode": True,
    "codex": True,
    "gemini": True,
    "windsurf": True,
    "cline": True,
    "zed": True,
    "claude-code": False,
    "claude-desktop": False,
    **{key: True for key in clients_extra.EXTRA_CLIENTS},
}
_CLIENT_COMPACT_REASON = {
    "cursor": "Cursor 全局约 40 个工具上限，超出部分**静默丢弃**（不会报错）",
    "vscode": "VS Code Copilot 跨所有 server 共 128 个工具上限",
    "codex": "Codex 无工具搜索，全量工具定义每轮都进上下文",
    "gemini": "Gemini CLI 对工具数与 schema 都更严格",
    "windsurf": "Windsurf（现 Devin Desktop）：旧 Cascade 100 个工具上限，Devin Local 未公布上限且无工具搜索",
    "cline": "Cline 无工具搜索，全量面偏重",
    "zed": "Zed 无工具搜索，全量面偏重",
    **{key: spec.compact_reason for key, spec in clients_extra.EXTRA_CLIENTS.items()},
}


# 各客户端配置文件在本机的位置（`client check` 找、`client config` 报 `config_path`、`setup` 写）。
# v0.38.0 B2 之前是一张 POSIX 路径表：Windows 上 cursor/vscode/gemini/windsurf/cline/zed 一个都找不到，
# `client check` 在 Windows 只会说「还没配」。现在按 os 与环境变量算真实位置；找不到不是错误。
_CLIENT_NAMES = (
    "claude-code", "claude-desktop", "cursor", "vscode", "codex", "gemini", "windsurf", "cline", "zed",
    # v0.41.0：16 家（事实与出处见 clients_extra + contracts/third_party_facts.json；tests/test_client_lockstep.py 锁步）
    *clients_extra.EXTRA_CLIENTS,
)


def _project_root(start: Path | None = None) -> Path:
    """项目级配置该落在哪：从 `start`（默认 CWD）向上找最近的 `.git` 或已有 `.mcp.json` 的目录；都没有就是 CWD 本身。

    🔴 v0.38.1 C10：此前项目级候选一律取 `Path.cwd()`。在子目录里跑 `setup` / `client check`（最常见：
    `cd horosa-skill && uv run horosa-skill setup --client cursor`）会把 `.cursor/mcp.json` 写进子目录 ——
    客户端按项目根找配置，根本看不到它；`client check` 也在错的地方找。
    """
    start = (start or Path.cwd()).resolve()
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists() or (candidate / ".mcp.json").is_file():
            return candidate
    return start


def _client_config_locations(
    client: str, *, os_name: str | None = None, env: Mapping[str, str] | None = None,
    home: Path | None = None, cwd: Path | None = None,
) -> list[Path]:
    """候选配置文件（先全局后项目级；第一个存在的就是 `config_path`）。纯函数，便于跨平台测试。

    项目级候选按 `_project_root(cwd)`（`.git` / `.mcp.json` 所在的最近祖先），不是裸 CWD。
    v0.38.1 C19 追加：`CODEX_HOME`（Codex 官方覆盖变量）、Linux 的 `XDG_CONFIG_HOME`、项目级
    `.gemini/settings.json`、Cline 装在 Cursor / Windsurf 里时的 globalStorage 根；windsurf 键 = Devin Desktop / Devin CLI 的
    mcp_config.json（用户级 → 项目级 → 旧 Cascade 路径）。
    """
    # os_name ∈ {"nt", "darwin", "linux"}（默认按本机）；参数化是为了在任何平台上都能测别的平台的路径表。
    if os_name is None:
        os_name = "nt" if os.name == "nt" else ("darwin" if sys.platform == "darwin" else "linux")
    env = os.environ if env is None else env
    home = Path(home) if home is not None else Path.home()
    project = Path(cwd) if cwd is not None else _project_root()
    if client in clients_extra.EXTRA_CLIENTS:
        return clients_extra.locations(client, os_name=os_name, env=env, home=home, project=project)
    if os_name == "nt":
        appdata = Path(env.get("APPDATA") or (home / "AppData" / "Roaming"))
        claude_desktop = appdata / "Claude" / "claude_desktop_config.json"
        code_user = appdata / "Code" / "User"
        cursor_user = appdata / "Cursor" / "User"
        windsurf_user = appdata / "Windsurf" / "User"
        devin_user = appdata / "devin" / "mcp_config.json"
        zed = appdata / "Zed" / "settings.json"
    elif os_name == "darwin":
        app_support = home / "Library" / "Application Support"
        claude_desktop = app_support / "Claude" / "claude_desktop_config.json"
        code_user = app_support / "Code" / "User"
        cursor_user = app_support / "Cursor" / "User"
        windsurf_user = app_support / "Windsurf" / "User"
        devin_user = home / ".config" / "devin" / "mcp_config.json"
        zed = home / ".config" / "zed" / "settings.json"
    else:
        xdg = Path(env.get("XDG_CONFIG_HOME") or (home / ".config"))
        claude_desktop = xdg / "Claude" / "claude_desktop_config.json"
        code_user = xdg / "Code" / "User"
        cursor_user = xdg / "Cursor" / "User"
        windsurf_user = xdg / "Windsurf" / "User"
        devin_user = xdg / "devin" / "mcp_config.json"
        zed = xdg / "zed" / "settings.json"
    codex_home = Path(env["CODEX_HOME"]) if env.get("CODEX_HOME") else home / ".codex"
    cline_tail = Path("globalStorage") / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json"
    table: dict[str, list[Path]] = {
        "claude-code": [home / ".claude.json", project / ".mcp.json"],
        "claude-desktop": [claude_desktop],
        "cursor": [home / ".cursor" / "mcp.json", project / ".cursor" / "mcp.json"],
        "vscode": [code_user / "mcp.json", project / ".vscode" / "mcp.json"],
        "codex": [codex_home / "config.toml"],
        "gemini": [home / ".gemini" / "settings.json", project / ".gemini" / "settings.json"],
        # Windsurf 于 2026-06-02 更名 Devin Desktop；2026-09-08（v3.9.19）起 Cascade 被移除，唯一 agent = Devin Local，
        # 它读 Devin CLI 的 MCP 文件（docs.devin.ai/cli/extensibility/mcp/configuration：用户级 ~/.config/devin/mcp_config.json、
        # Windows %APPDATA%\devin\mcp_config.json、项目级 .devin/mcp_config.json；根键仍是 mcpServers，字段 command/args/env/disabled）。
        # 旧 Cascade 路径 ~/.codeium/windsurf/mcp_config.json 留作最后候选：已有文件者继续原位合并，新装机写 Devin 路径。
        "windsurf": [devin_user, project / ".devin" / "mcp_config.json", home / ".codeium" / "windsurf" / "mcp_config.json"],
        "cline": [code_user / cline_tail, cursor_user / cline_tail, windsurf_user / cline_tail],
        "zed": [zed],
    }
    if client not in table:
        raise typer.BadParameter(f"未知客户端 `{client}`。可选：{', '.join(_CLIENT_NAMES)}")
    return table[client]


def _preferred_config_path(client: str) -> Path:
    """第一个已存在的候选；都不存在则第一个候选（全局级）。"""
    candidates = _client_config_locations(client)
    return next((c for c in candidates if c.is_file()), candidates[0])


def _codex_env_roots() -> dict[str, str]:
    """Codex env 表里显式写的两个根（解析后的绝对路径；`HOROSA_PORTS=auto` 等其它旋钮不在此列）。"""
    settings = Settings.from_env()
    return {
        "HOROSA_RUNTIME_ROOT": str(settings.runtime_root.expanduser().resolve()),
        "HOROSA_SKILL_DATA_DIR": str(settings.data_dir.expanduser().resolve()),
    }
