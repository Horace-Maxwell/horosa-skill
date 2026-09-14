"""按安装上下文给出**能直接复制运行**的修复命令（v0.38.1 C7）。

🔴 为什么：`runtime.not_installed` 此前一律说「在仓库目录执行 `uv run horosa-skill install`」——
但 wheel / uvx 用户根本没有仓库目录，MCPB 与 Claude Code 插件用户连 `uv run` 该在哪个目录跑都不知道
（插件装在 `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`）。一条对着错误的人说的修复
提示 = 用户去 clone 一个他不需要的仓库，或者干脆放弃。

上下文判定（从确定到兜底）：
  1. `HOROSA_INSTALL_CONTEXT=plugin` + `HOROSA_PLUGIN_ROOT`（由 `.claude-plugin/mcp.json` 注入
     `${CLAUDE_PLUGIN_ROOT}`）→ `uv run --directory "<root>/horosa-skill" horosa-skill install`
  2. `HOROSA_INSTALL_CONTEXT=mcpb` + `HOROSA_PLUGIN_ROOT`（manifest.json 注入 `${__dirname}`）→
     `uv run --directory "<root>" horosa-skill install`
  3. 包旁边有 `pyproject.toml`（源码 checkout / editable）→ `uv run horosa-skill install`
  4. 其余（wheel / uvx / pip）→ `uvx --from "<钉版本的 wheel URL>" horosa-skill install`
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

Context = str  # "plugin" | "mcpb" | "checkout" | "wheel"


def _quote(value: str) -> str:
    """一律双引号：bash / zsh / PowerShell / cmd 都接受，而插件缓存路径、镜像 URL 里随时可能出现空格、中文、`&`、`?`。
    「只在需要时加引号」会让同一条提示在不同机器上长得不一样，用户复制时更容易漏。"""
    return '"' + value.replace('"', '\\"') + '"'


def _package_is_checkout() -> bool:
    """`src/horosa_skill/runtime/hints.py` 往上三层是包根，旁边有 pyproject.toml = 源码 checkout。"""
    try:
        root = Path(__file__).resolve().parents[3]
    except IndexError:
        return False
    return (root / "pyproject.toml").is_file() and (root / "src" / "horosa_skill").is_dir()


def detect_context(env: dict[str, str] | None = None) -> tuple[Context, str | None]:
    env = os.environ if env is None else env
    declared = (env.get("HOROSA_INSTALL_CONTEXT") or "").strip().lower()
    root = (env.get("HOROSA_PLUGIN_ROOT") or "").strip() or None
    if declared in {"plugin", "mcpb"} and root and "${" not in root:
        return declared, root
    if _package_is_checkout():
        return "checkout", str(Path(__file__).resolve().parents[3])
    return "wheel", None


def install_command(env: dict[str, str] | None = None) -> dict[str, Any]:
    """`{"context", "install", "doctor", "cwd"}`：install/doctor 是完整可复制的命令行字符串。"""
    context, root = detect_context(env)
    if context == "plugin" and root:
        directory = str(Path(root) / "horosa-skill")
        prefix = f"uv run --directory {_quote(directory)} horosa-skill"
        return {"context": context, "cwd": directory, "install": f"{prefix} install", "doctor": f"{prefix} doctor"}
    if context == "mcpb" and root:
        prefix = f"uv run --directory {_quote(root)} horosa-skill"
        return {"context": context, "cwd": root, "install": f"{prefix} install", "doctor": f"{prefix} doctor"}
    if context == "checkout" and root:
        return {"context": context, "cwd": root, "install": "uv run horosa-skill install", "doctor": "uv run horosa-skill doctor"}
    from horosa_skill.client_tools import zero_install_wheel_url
    from horosa_skill.runtime.mirrors import preferred_mirror_url

    wheel = preferred_mirror_url(zero_install_wheel_url())
    prefix = f"uvx --from {_quote(wheel)} horosa-skill"
    return {"context": "wheel", "cwd": None, "install": f"{prefix} install", "doctor": f"{prefix} doctor"}


def install_commands_for_error() -> dict[str, Any]:
    """`runtime.not_installed` 的 details 片段：next_action / agent_recovery 全部按上下文生成。"""
    from horosa_skill.errors import bilingual

    hint = install_command()
    where = f"（在 {hint['cwd']} 下）" if hint["cwd"] else ""
    where_en = f" (from {hint['cwd']})" if hint["cwd"] else ""
    return {
        "install_context": hint["context"],
        "next_action": bilingual(
            f"运行 `{hint['install']}` 安装离线 runtime（约 730 MB 下载）{where}，随后 `{hint['doctor']}` 确认。",
            f"Run `{hint['install']}`{where_en} to install the offline runtime (~730 MB download), then `{hint['doctor']}`.",
        ),
        "agent_recovery": {
            "kind": "install_required",
            "prompt_to_user": bilingual(
                f"本地 Horosa 运行时还没安装。请执行：{hint['install']}（首次约需数分钟下载 730 MB），装好后重试本次请求。",
                f"The local Horosa runtime is not installed yet. Run: {hint['install']} (first run downloads ~730 MB), then retry.",
            ),
            "commands": [hint["install"], hint["doctor"]],
        },
    }


__all__ = ["detect_context", "install_command", "install_commands_for_error"]
