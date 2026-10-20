"""The 16 `setup --client` targets added in v0.41.0 — one row of facts per client, read from each vendor's own docs or
source on 2026-10-12 (contracts/third_party_facts.json `clients-2026-10.*` carries the sources).

Why a table and not more `elif` branches in cli.py: the nine original clients each grew bespoke code over five releases;
sixteen more in the same style would bury the facts that actually differ (file path, root key, entry field names, the
timeout field and its unit). Here each client is data; `client_config/` (and the setup flow in `surfaces/cli.py`) asks this
module for locations, the payload, the audit and the probe environment, and `tests/test_client_lockstep.py` pins every key to the docs, the lanes and the
ledger.

Rules every row follows:
- write only the USER-level file (a project file such as `.mcp.json` is shared with other clients — Copilot CLI and
  Kimi both read Claude Code's — and their extra fields would land in someone else's config);
- set a timeout wherever the client's default is shorter than a 45 s cold start or a multi-minute 择日 scan, and make
  `client check` flag it when missing; where the client only takes an environment variable, say so in next_steps;
- compact surface everywhere (11 facade tools; every technique still reachable through `horosa_tool_run`);
- no file at all where none is documented (Trae: deep link + paste JSON) and no edits to files that hold other people's
  patches (dsh: a standalone patch file).
"""

from __future__ import annotations

import base64
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote


@dataclass(frozen=True)
class TimeoutRule:
    """One timeout the client needs set. `where` = "entry" (a field) or "env" (a string in the entry's env table)."""

    field: str
    minimum: float
    unit: str
    why: str
    where: str = "entry"


@dataclass(frozen=True)
class ExtraClient:
    key: str
    product: str
    style: str  # json | opencode | amp | goose | trae | dsh
    root_key: str
    locations: Callable[[str, Mapping[str, str], Path, Path], list[Path]]
    restart_hint: str
    compact_reason: str
    entry_extra: Mapping[str, Any] = field(default_factory=dict)
    env_extra: Mapping[str, str] = field(default_factory=dict)
    timeout_rules: tuple[TimeoutRule, ...] = ()
    notes: tuple[str, ...] = ()
    strict_json: bool = False
    # Clients that hand the server only these variables (None = the client passes its whole environment).
    passthrough_env: tuple[str, ...] | None = None


def _xdg(env: Mapping[str, str], home: Path) -> Path:
    return Path(env["XDG_CONFIG_HOME"]) if env.get("XDG_CONFIG_HOME") else home / ".config"


def _home_override(env: Mapping[str, str], var: str, default: Path) -> Path:
    value = (env.get(var) or "").strip()
    return Path(value) if value else default


def _goose(os_name: str, env: Mapping[str, str], home: Path, _project: Path) -> list[Path]:
    if (env.get("GOOSE_PATH_ROOT") or "").strip():
        return [Path(env["GOOSE_PATH_ROOT"]) / "config" / "config.yaml"]
    if os_name == "nt":
        appdata = Path(env.get("APPDATA") or (home / "AppData" / "Roaming"))
        return [appdata / "Block" / "goose" / "config" / "config.yaml"]
    return [_xdg(env, home) / "goose" / "config.yaml"]


def _codebuddy(_os: str, env: Mapping[str, str], home: Path, _project: Path) -> list[Path]:
    # USER scope reads ONLY the first existing of these three and never merges them — creating the first one while the
    # user's servers live in the legacy ~/.codebuddy.json would hide those servers. Order = CodeBuddy's own order.
    base = _home_override(env, "CODEBUDDY_CONFIG_DIR", home / ".codebuddy")
    return [base / ".mcp.json", base / "mcp.json", home / ".codebuddy.json"]


_LONG_TOOLS = "择日类扫描本来就要几分钟"
_COLD_START = "首次冷启动约 45 s"
_WARM_FIRST = (
    "该客户端没有可写进配置的启动超时：首次使用前先在终端跑一次 `horosa-skill runtime start` 把离线 runtime 预热好"
    "（冷启动约 45 s），客户端连上时就不用等它。"
)

EXTRA_CLIENTS: dict[str, ExtraClient] = {
    "opencode": ExtraClient(
        key="opencode", product="OpenCode", style="opencode", root_key="mcp",
        locations=lambda _os, env, home, _p: [_xdg(env, home) / "opencode" / name for name in ("opencode.json", "opencode.jsonc", "config.json")],
        entry_extra={"enabled": True, "timeout": 600000},
        timeout_rules=(TimeoutRule("timeout", 600000, "ms", f"缺省连接 / 列工具 30 s、调用 60 s；{_COLD_START}，{_LONG_TOOLS}"),),
        restart_hint="退出并重开 opencode（配置在启动时读取）；`opencode mcp list` 应显示 horosa connected。",
        compact_reason="OpenCode 没有工具搜索，全部工具定义每轮都进上下文",
    ),
    "goose": ExtraClient(
        key="goose", product="Goose", style="goose", root_key="extensions", locations=_goose,
        entry_extra={"enabled": True, "type": "stdio", "description": "Horosa 星阙 — 术数 / 占星 (local)", "env_keys": [], "timeout": 600},
        timeout_rules=(TimeoutRule("timeout", 600, "s", f"缺省 300 s 且每次请求固定计时；{_LONG_TOOLS}"),),
        restart_hint="扩展按会话加载：新开一个 `goose session`（或重开 Goose Desktop）；`goose info -v` 显示已加载的配置。",
        compact_reason="Goose 没有工具数上限也没有工具搜索，全量面偏重",
    ),
    "kiro": ExtraClient(
        key="kiro", product="Kiro", style="json", root_key="mcpServers",
        locations=lambda _os, env, home, _p: [_home_override(env, "KIRO_HOME", home / ".kiro") / "settings" / "mcp.json"],
        entry_extra={"disabled": False},
        notes=("Kiro CLI 的 MCP 启动缺省只等 5 s（`mcp.initTimeout`），首次冷启动约 45 s：先运行 `kiro-cli settings mcp.initTimeout 120000`；"
               "Kiro IDE 在 MCP 面板对 horosa 点 Reconnect 即可。",),
        restart_hint="保存即生效（下一个空闲点）；IDE 的 MCP servers 面板里 Reconnect，CLI 里 `kiro-cli mcp list global`。",
        compact_reason="Kiro IDE 没有工具搜索（CLI 的 Tool Search 缺省关闭）",
    ),
    "copilot-cli": ExtraClient(
        key="copilot-cli", product="GitHub Copilot CLI", style="json", root_key="mcpServers",
        locations=lambda _os, env, home, _p: [_home_override(env, "COPILOT_HOME", home / ".copilot") / "mcp-config.json"],
        entry_extra={"type": "local", "tools": ["*"], "timeout": 600000},
        timeout_rules=(TimeoutRule("timeout", 600000, "ms", f"缺省 30 s（工具发现与调用共用）；{_LONG_TOOLS}"),),
        restart_hint="会话里 `/mcp reload`（或重开 copilot）；`copilot mcp get horosa` 应列出它。",
        compact_reason="Copilot CLI 的工具搜索只对部分模型生效，精简面在任何模型下都轻",
        # 官方文档：「PATH 自动继承；其余环境变量都必须在这里配置」。所以 HOME 等写进 env 表，stdio 探针也只给 PATH。
        passthrough_env=("PATH",),
    ),
    "junie": ExtraClient(
        key="junie", product="JetBrains Junie", style="json", root_key="mcpServers",
        locations=lambda _os, env, home, _p: [_home_override(env, "JUNIE_HOME", home / ".junie") / "mcp" / "mcp.json"],
        notes=(_WARM_FIRST,),
        restart_hint="新开一个 Junie CLI 会话（或重启 IDE 里的 Junie 会话）；`/mcp` 应显示 horosa Active。",
        compact_reason="Junie 未公布工具上限也没有工具搜索",
    ),
    "qwen": ExtraClient(
        key="qwen", product="Qwen Code", style="json", root_key="mcpServers",
        locations=lambda _os, env, home, _p: [_home_override(env, "QWEN_HOME", home / ".qwen") / "settings.json"],
        entry_extra={"discoveryTimeoutMs": 120000, "timeout": 600000},
        timeout_rules=(
            TimeoutRule("discoveryTimeoutMs", 60000, "ms", f"缺省 30 s（连接 + 列工具）；{_COLD_START}"),
            TimeoutRule("timeout", 600000, "ms", _LONG_TOOLS),
        ),
        restart_hint="在同一项目里重启 qwen；会话里 `/mcp` 看状态（别信 `qwen mcp list`：它只等 10 s）。",
        compact_reason="Qwen Code 每次 MCP 调用都要确认，精简面让确认次数与上下文都更少",
    ),
    "kimi": ExtraClient(
        key="kimi", product="Kimi Code CLI", style="json", root_key="mcpServers",
        locations=lambda _os, env, home, _p: [_home_override(env, "KIMI_CODE_HOME", home / ".kimi-code") / "mcp.json"],
        entry_extra={"startupTimeoutMs": 120000, "toolTimeoutMs": 600000},
        timeout_rules=(
            TimeoutRule("startupTimeoutMs", 60000, "ms", f"缺省 30 s；{_COLD_START}"),
            TimeoutRule("toolTimeoutMs", 600000, "ms", f"缺省 60 s；{_LONG_TOOLS}"),
        ),
        restart_hint="MCP 在会话开始时加载：`/new` 或重启 kimi；`/mcp` 看状态。",
        compact_reason="Kimi Code 的延迟加载仍是实验特性，缺省全部工具进上下文",
    ),
    "qoder": ExtraClient(
        key="qoder", product="Qoder (CLI / new desktop app)", style="json", root_key="mcpServers",
        locations=lambda _os, env, home, _p: [_home_override(env, "QODER_CONFIG_DIR", home / ".qoder") / "settings.json"],
        entry_extra={"timeout": 600000},
        timeout_rules=(TimeoutRule("timeout", 600000, "ms", f"连接与请求共用一个超时；{_COLD_START}，{_LONG_TOOLS}"),),
        restart_hint="`/mcp reload` 或新开会话；`qoder mcp list` 应列出 horosa。（旧版 Qoder IDE 只能在它的界面里配 MCP。）",
        compact_reason="Qoder 的懒加载缺省关闭，全部工具进上下文",
    ),
    "codebuddy": ExtraClient(
        key="codebuddy", product="Tencent CodeBuddy Code", style="json", root_key="mcpServers", locations=_codebuddy,
        entry_extra={"type": "stdio"},
        notes=("CodeBuddy 的超时只能用环境变量设：在启动它的 shell 里 `export MCP_TIMEOUT=120000 MCP_TOOL_TIMEOUT=600000`"
               f"（{_COLD_START}，{_LONG_TOOLS}）。",),
        restart_hint="重启 CodeBuddy；`codebuddy mcp get horosa` 应显示它。",
        compact_reason="CodeBuddy 超过 30 个工具会转延迟加载，单次输出上限 2 万 token",
    ),
    "trae": ExtraClient(
        key="trae", product="TRAE", style="trae", root_key="mcpServers",
        # 没有文档化的用户级文件——只有界面里的 Settings > MCP；项目级 .trae/mcp.json 要先在设置里打开「Enable Project MCP」。
        locations=lambda _os, _env, _home, project: [project / ".trae" / "mcp.json"],
        env_extra={"START_MCP_TIMEOUT_MS": "120000", "RUN_MCP_TIMEOUT_MS": "600000"},
        timeout_rules=(
            TimeoutRule("START_MCP_TIMEOUT_MS", 60000, "ms", _COLD_START, where="env"),
            TimeoutRule("RUN_MCP_TIMEOUT_MS", 600000, "ms", _LONG_TOOLS, where="env"),
        ),
        notes=("TRAE 没有用户级配置文件：打开 config 步骤里的 deep_link（国内版用 deep_link_cn）一键导入，或在 Settings > MCP > Add > "
               "Create Manually 粘贴 paste_json。TRAE 所有 MCP 合计最多 40 个工具、8000 字符描述——精简面 11 个工具也要和你的其它 server 分这份额度。",),
        restart_hint="界面里添加后立即启动；Settings > MCP 列表里应看到 horosa（日志在 Output 面板的 MCP Server Host）。",
        compact_reason="TRAE 所有 MCP 合计最多 40 个工具、8000 字符描述，超出直接丢弃",
    ),
    "amp": ExtraClient(
        key="amp", product="Amp", style="amp", root_key="amp.mcpServers",
        locations=lambda _os, _env, home, _p: [home / ".config" / "amp" / name for name in ("settings.json", "settings.jsonc")],
        notes=(_WARM_FIRST,),
        restart_hint="重启 Amp CLI / 重载编辑器扩展；`amp mcp doctor` 看状态。",
        compact_reason="Amp 文档提醒工具太多会降低模型表现，且没有工具搜索",
    ),
    "warp": ExtraClient(
        key="warp", product="Warp", style="json", root_key="mcpServers",
        locations=lambda _os, _env, home, _p: [home / ".warp" / ".mcp.json"],
        notes=("Warp 若打开了「Auto-spawn servers from third-party agents」，又在 Claude Code / Codex 里也配了 horosa，"
               "同一个 server 可能出现两次——只在一处保留即可。",),
        restart_hint="保存即自动生效；Settings > Agents > MCP servers 里应看到「Detected from Warp」的 horosa。",
        compact_reason="Warp 未公布工具上限也没有工具搜索",
    ),
    "droid": ExtraClient(
        key="droid", product="Factory Droid", style="json", root_key="mcpServers",
        locations=lambda _os, _env, home, _p: [home / ".factory" / "mcp.json"],
        entry_extra={"type": "stdio", "connectTimeout": 120000, "timeout": 600000, "disabled": False},
        timeout_rules=(
            TimeoutRule("connectTimeout", 60000, "ms", f"stdio 握手缺省 30 s；{_COLD_START}"),
            TimeoutRule("timeout", 600000, "ms", _LONG_TOOLS),
        ),
        restart_hint="mcp.json 一改 Droid 就自动重载；`droid mcp list` 应显示 horosa connected。",
        compact_reason="Droid 的 MCP 工具搜索是否缺省开启未公布",
    ),
    "augment": ExtraClient(
        key="augment", product="Augment Auggie CLI", style="json", root_key="mcpServers",
        locations=lambda _os, _env, home, _p: [home / ".augment" / "settings.json"],
        entry_extra={"type": "stdio"},
        notes=(_WARM_FIRST + "（Auggie 只等 15 s 就先开工，冷启动中的 server 头几轮不在工具列表里。）",),
        restart_hint="手改配置后重启 auggie；`auggie mcp list` 应列出 horosa。（Augment 的 IDE 扩展用自己的设置面板，不读这个文件。）",
        compact_reason="Auggie 的 MCP 工具搜索缺省关闭",
    ),
    "deepcode": ExtraClient(
        key="deepcode", product="Deep Code", style="json", root_key="mcpServers",
        locations=lambda _os, _env, home, _p: [home / ".deepcode" / "settings.json"],
        strict_json=True,
        notes=("Deep Code 启动只等 30 s：先 `export DEEPCODE_MCP_TIMEOUT=120000` 再启动 deepcode。它的单次工具调用固定 60 s、不可调——"
               "择日扫描这类长任务在 Deep Code 里会超时，请换别的客户端跑。",),
        restart_hint="重启 deepcode（配置每个会话读一次）；会话里 `/mcp` 看状态。",
        compact_reason="Deep Code 没有工具上限也没有延迟加载，全部工具常驻上下文",
    ),
    "dsh": ExtraClient(
        key="dsh", product="DeepSeek Harness (dsh, developer preview)", style="dsh", root_key="insert",
        # 不改 ~/.dsh/cordis.patch.yml（官方：「别覆盖已有文件，里面可能有你别的补丁」）——生成一份独立补丁，让用户自己挂上。
        locations=lambda _os, _env, home, _p: [home / ".horosa" / "clients" / "dsh" / "horosa.cordis.yml"],
        timeout_rules=(TimeoutRule("toolCallTimeoutMs", 600000, "ms", f"缺省 60 s；{_LONG_TOOLS}"),),
        notes=("dsh 仍是开发者预览版：本命令只生成独立补丁文件（见 config 步骤的 path），不改你的 ~/.dsh/cordis.patch.yml。"
               "运行 `dsh web --patch <那个文件>`，或把文件里唯一的 insert 操作并进 cordis.patch.yml（二选一，别两处都挂）。",),
        restart_hint="`dsh web` 带 --patch 启动即生效；`dsh web --dump-config` 应看到 mcp__horosa__* 工具。",
        compact_reason="dsh 没有工具延迟加载，全部工具定义常驻上下文",
    ),
}

# 发给 Copilot CLI 的 env 表要自带这些（它只转发 PATH）；按 OS 取本机当前值，没有就不写。
_HOME_VARS = {"nt": ("USERPROFILE", "APPDATA", "LOCALAPPDATA", "SYSTEMROOT", "TEMP", "TMP"), "posix": ("HOME",)}


def locations(key: str, *, os_name: str, env: Mapping[str, str], home: Path, project: Path) -> list[Path]:
    return EXTRA_CLIENTS[key].locations(os_name, env, home, project)


def _home_env(os_name: str, environ: Mapping[str, str]) -> dict[str, str]:
    names = _HOME_VARS["nt" if os_name == "nt" else "posix"]
    return {name: environ[name] for name in names if environ.get(name)}


def build_payload(
    key: str, *, server_name: str, stdio_command: list[str], surface_env: Mapping[str, str], env_roots: Mapping[str, str],
    config_path: Path, os_name: str | None = None, environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """The `client config` / `setup` payload for one extra client (cli adds `launcher` / `tool_surface` / `warnings`)."""
    spec = EXTRA_CLIENTS[key]
    os_name = os_name or ("nt" if os.name == "nt" else "posix")
    environ = os.environ if environ is None else environ
    command, args = stdio_command[0], list(stdio_command[1:])
    env: dict[str, str] = {**surface_env, **spec.env_extra}
    if spec.passthrough_env is not None:
        # 只拿到 PATH 的子进程算不出 runtime 根、uvx 也找不到缓存目录：两个根与 home 变量都显式写（与 Codex 同理）。
        env.update(env_roots)
        env.update(_home_env(os_name, environ))
    payload: dict[str, Any] = {"config_path": str(config_path), "root_key": spec.root_key}
    warnings: list[str] = []
    if spec.style == "opencode":
        entry: Any = {"type": "local", "command": [command, *args], **({"environment": env} if env else {}), **spec.entry_extra}
    elif spec.style == "goose":
        entry = {"enabled": True, "name": server_name, "type": "stdio", "cmd": command, "args": args,
                 "envs": env, **{k: v for k, v in spec.entry_extra.items() if k not in {"enabled", "type"}}}
        payload["config_format"] = "yaml"
    elif spec.style == "dsh":
        config: dict[str, Any] = {"serverName": server_name, "transport": "stdio", "command": command, "args": args,
                                  **({"env": env} if env else {}), "toolCallTimeoutMs": 600000}
        payload["config_format"] = "dsh-patch"
        payload["dsh_patch"] = [{"insert": [{"id": f"mcp-{server_name}", "name": "@deepseek-ai/dsh-mcp-client", "config": config}]}]
        payload["note"] = f"独立补丁文件 {config_path}：`dsh web --patch {config_path}`，或把其中的 insert 操作并进 ~/.dsh/cordis.patch.yml。"
        payload["insert"] = {server_name: config}  # 供 setup 报告 server_block；写盘走 dsh_patch
        return payload
    else:
        entry = {**({"type": spec.entry_extra["type"]} if "type" in spec.entry_extra else {}), "command": command, "args": args,
                 **({"env": env} if env else {}), **{k: v for k, v in spec.entry_extra.items() if k != "type"}}
    if spec.style == "trae":
        if any(ch.isspace() for ch in command):
            warnings.append(f"TRAE 要求 command 里不能有空格（否则解析报错）：{command}——把 uv 装到不含空格的路径后重跑。")
        encoded = quote(base64.b64encode(json.dumps(entry, ensure_ascii=False).encode("utf-8")).decode("ascii"), safe="")
        payload["deep_link"] = f"trae://trae.ai-ide/mcp-import?type=stdio&name={server_name}&config={encoded}"
        payload["deep_link_cn"] = f"trae-cn://trae.ai-ide/mcp-import?type=stdio&name={server_name}&config={encoded}"
        payload["paste_json"] = json.dumps({"mcpServers": {server_name: entry}}, ensure_ascii=False, indent=2)
        payload["note"] = "TRAE 没有用户级配置文件：点 deep_link 一键导入（国内版 deep_link_cn），或在 Settings > MCP > Add > Create Manually 粘贴 paste_json。"
        payload["config_mode"] = "printed"
    else:
        payload["note"] = f"合并进 {config_path}（{spec.root_key} 键下）。"
    if spec.strict_json:
        payload["strict_json"] = True
    payload[spec.root_key] = {server_name: entry}
    if warnings:
        payload["warnings"] = warnings
    return payload


def render_dsh_patch(payload: Mapping[str, Any]) -> str:
    """The patch file body. JSON is valid YAML 1.2, so dsh reads it and `client check` can parse it back without a YAML library."""
    header = "# horosa-skill 生成的 DeepSeek Harness 补丁：dsh web --patch <本文件>（重跑 setup 会整份重写，别手改）\n"
    return header + json.dumps(payload["dsh_patch"], ensure_ascii=False, indent=2) + "\n"


def read_dsh_patch(text: str) -> dict[str, dict[str, Any]]:
    """{serverName: entry normalised to command/args/env} from a patch file this module wrote."""
    body = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    ops = json.loads(body)
    out: dict[str, dict[str, Any]] = {}
    for op in ops if isinstance(ops, list) else []:
        for row in (op or {}).get("insert") or []:
            config = (row or {}).get("config") or {}
            if config.get("serverName"):
                out[str(config["serverName"])] = dict(config)
    return out


def audit(key: str, entry: Mapping[str, Any], *, os_name: str | None = None) -> list[dict[str, str]]:
    """Client-specific findings for one (normalised) entry: missing / too-short timeouts, Copilot's env, TRAE's spaces."""
    spec = EXTRA_CLIENTS.get(key)
    if spec is None:
        return []
    problems: list[dict[str, str]] = []
    raw = dict(entry)
    for rule in spec.timeout_rules:
        source = raw.get("env") if rule.where == "env" else raw
        value = (source or {}).get(rule.field) if isinstance(source, Mapping) else None
        code = key.replace("-", "_")
        if value is None:
            problems.append({
                "code": f"{code}_{rule.field}_missing",
                "detail": f"没写 {rule.field}（{rule.why}）。",
                "fix": f"在该条目{'的 env 表' if rule.where == 'env' else ''}里加 `{rule.field}` ≥ {int(rule.minimum)}（{rule.unit}），或重跑 `horosa-skill setup --client {key}`。",
            })
            continue
        try:
            too_short = float(value) < rule.minimum
        except (TypeError, ValueError):
            too_short = True
        if too_short:
            problems.append({
                "code": f"{code}_{rule.field}_too_short",
                "detail": f"{rule.field}={value}（{rule.why}）。",
                "fix": f"设 {int(rule.minimum)} 以上（{rule.unit}）。",
            })
    if key == "copilot-cli":
        if raw.get("tools") is None:
            problems.append({"code": "copilot_cli_tools_missing", "detail": "没写 `tools`（Copilot CLI 参考表把它列为必填）。",
                             "fix": "加 `\"tools\": [\"*\"]`。"})
        os_name = os_name or ("nt" if os.name == "nt" else "posix")
        wanted = "USERPROFILE" if os_name == "nt" else "HOME"
        if not str((raw.get("env") or {}).get(wanted) or "").strip():
            problems.append({
                "code": "copilot_cli_env_home_missing",
                "detail": f"env 表里没有 {wanted}：Copilot CLI 只把 PATH 交给 server，uvx 找不到缓存目录、server 算不出 runtime 根。",
                "fix": f"重跑 `horosa-skill setup --client copilot-cli`（写入 {wanted} 与两个 runtime 根）。",
            })
    if key == "trae" and any(ch.isspace() for ch in str(raw.get("command") or "")):
        problems.append({"code": "trae_command_has_space", "detail": f"command 含空格：{raw.get('command')}（TRAE 会解析出错）。",
                         "fix": "把 uv 装到不含空格的路径，重跑 setup。"})
    return problems


def probe_env(key: str, configured_env: Mapping[str, str], environ: Mapping[str, str] | None = None) -> dict[str, str] | None:
    """The environment the client would give the server, for setup's stdio probe; None = inherit everything."""
    spec = EXTRA_CLIENTS.get(key)
    if spec is None or spec.passthrough_env is None:
        return None
    environ = os.environ if environ is None else environ
    return {**{name: environ[name] for name in spec.passthrough_env if name in environ}, **configured_env}
