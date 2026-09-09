#!/usr/bin/env python3
"""仓内提交的客户端配置必须**真能连上**，占位符必须属于该作用域的词表。

为什么有这把守卫：仓根 `.mcp.json` 曾把**插件作用域**的占位符写进 Claude Code 的**项目**配置
（`${CLAUDE_PLUGIN_ROOT}` 与 `${user_config.*}`）。项目作用域里这两类都不展开：前者变空串 →
`uv run --directory /horosa-skill` → 目录不存在；后者原样落进 env → 每个技法工具回
`runtime.not_installed`，`Settings.ensure_dirs()` 还会 mkdir 出一个名叫 `${user_config.runtimeRoot}`
的真目录。本机 `~/Library/Caches/claude-cli-nodejs/.../mcp-logs-horosa/` 里 2026-08-21 起
**24 份日志、24 次 CONNECTION_CLOSED，零成功** —— 本仓自己的 MCP 从未连通过，而所有测试全绿：
没有任何检查看过这个文件。

三条断言：
1. 项目配置（`.mcp.json`）只许用 Claude Code 文档化的 `${VAR:-default}` 形态，且不得出现
   插件/MCPB 专属占位符；`--directory` 去掉占位符后必须指向仓内真实的 `pyproject.toml`。
2. 插件配置（`.claude-plugin/mcp.json`）的占位符必须 ⊆ 插件词表，且 `user_config.<key>` 里的
   key 必须在 `plugin.json.userConfig` 里声明过（写错 key 的后果与上面那 24 次一模一样）。
3. 两份配置都必须显式 `--transport stdio`——`serve` 的默认传输是 streamable-http，漏了这个
   参数客户端会连一个**根本没在监听 stdio** 的进程，症状同样是 CONNECTION_CLOSED。

stdlib-only；负向对照见 tests/test_verify_client_configs.py。接在 ci.yml。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
PKG_ROOT = SCRIPTS.parent
REPO_ROOT = PKG_ROOT.parent

PROJECT_CONFIG = REPO_ROOT / ".mcp.json"
PLUGIN_CONFIG = REPO_ROOT / ".claude-plugin" / "mcp.json"
PLUGIN_MANIFEST = REPO_ROOT / ".claude-plugin" / "plugin.json"

_PLACEHOLDER = re.compile(r"\$\{([^}]*)\}")
# 插件作用域词表（Claude Code 插件文档）。项目作用域**只有** env 变量，且必须带 `:-` 默认值。
_PLUGIN_VARS = {"CLAUDE_PLUGIN_ROOT", "CLAUDE_PLUGIN_DATA", "CLAUDE_PROJECT_DIR"}
# 这些名字出现在项目配置里就是把作用域搞混了。
_PLUGIN_ONLY_MARKERS = ("CLAUDE_PLUGIN_ROOT", "CLAUDE_PLUGIN_DATA", "user_config.")


def _servers(payload: dict) -> dict:
    for key in ("mcpServers", "servers", "context_servers"):
        if isinstance(payload.get(key), dict):
            return payload[key]
    return {}


def _placeholders(blob: str) -> list[str]:
    return [m.group(1) for m in _PLACEHOLDER.finditer(blob)]


def _directory_arg(args: list) -> str | None:
    for i, arg in enumerate(args):
        if arg == "--directory" and i + 1 < len(args):
            return str(args[i + 1])
    return None


def check_project_config(errors: list[str]) -> None:
    if not PROJECT_CONFIG.is_file():
        errors.append(f"{PROJECT_CONFIG.name} 不存在——Claude Code 打开本仓时就没有可用的项目 MCP 配置")
        return
    payload = json.loads(PROJECT_CONFIG.read_text(encoding="utf-8"))
    blob = json.dumps(payload, ensure_ascii=False)
    for marker in _PLUGIN_ONLY_MARKERS:
        if marker in blob:
            errors.append(
                f"{PROJECT_CONFIG.name} 含插件作用域占位符 `{marker}` —— 项目作用域不展开它。"
                "插件那份放 .claude-plugin/mcp.json。"
            )
    for name, entry in _servers(payload).items():
        args = [str(a) for a in entry.get("args", [])]
        if "--transport" not in args or "stdio" not in args:
            errors.append(f"{PROJECT_CONFIG.name}:{name} 的 args 缺 `--transport stdio`（serve 默认是 streamable-http）")
        if entry.get("env"):
            errors.append(
                f"{PROJECT_CONFIG.name}:{name} 带 env 块 —— 项目作用域没有 user_config 可展开，"
                "留空即用默认值（~/.horosa/runtime、~/.horosa-skill）。"
            )
        for var in _placeholders(json.dumps(entry, ensure_ascii=False)):
            if ":-" not in var:
                errors.append(
                    f"{PROJECT_CONFIG.name}:{name} 的占位符 `${{{var}}}` 没有 `:-默认值` —— "
                    "宿主没设该变量时会展开成空串"
                )
        directory = _directory_arg(args)
        if directory:
            # 去掉占位符段落后应指向仓内真实包目录。
            tail = _PLACEHOLDER.sub("", directory).removeprefix("/") or "horosa-skill"
            if not (REPO_ROOT / tail / "pyproject.toml").is_file():
                errors.append(
                    f"{PROJECT_CONFIG.name}:{name} 的 --directory `{directory}` 去掉占位符后是 `{tail}`，"
                    f"但 {tail}/pyproject.toml 不存在"
                )


def check_plugin_config(errors: list[str]) -> None:
    if not PLUGIN_CONFIG.is_file():
        errors.append(f"{PLUGIN_CONFIG} 不存在（plugin.json.mcpServers 指向它）")
        return
    payload = json.loads(PLUGIN_CONFIG.read_text(encoding="utf-8"))
    manifest = json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8")) if PLUGIN_MANIFEST.is_file() else {}
    declared = set((manifest.get("userConfig") or {}).keys())
    pointer = str(manifest.get("mcpServers") or "")
    # 🔴 用 removeprefix 而不是 lstrip("./")：lstrip 剥的是**字符集**，会把 `.claude-plugin`
    # 开头那个点也吃掉 → 查 `claude-plugin/mcp.json`（不存在）。写这把守卫时当场踩了一次。
    if pointer and not (REPO_ROOT / pointer.removeprefix("./")).is_file():
        errors.append(f"plugin.json.mcpServers 指向 `{pointer}`，该文件不存在")

    for name, entry in _servers(payload).items():
        args = [str(a) for a in entry.get("args", [])]
        if "--transport" not in args or "stdio" not in args:
            errors.append(f"{PLUGIN_CONFIG.name}:{name} 的 args 缺 `--transport stdio`")
        for var in _placeholders(json.dumps(entry, ensure_ascii=False)):
            base = var.split(":-", 1)[0]
            if base.startswith("user_config."):
                key = base.split(".", 1)[1]
                if key not in declared:
                    errors.append(
                        f"{PLUGIN_CONFIG.name}:{name} 引用 `${{{base}}}`，但 plugin.json.userConfig "
                        f"没有声明 `{key}`（已声明：{sorted(declared)}）——宿主不会替换未声明的键"
                    )
            elif base not in _PLUGIN_VARS:
                errors.append(f"{PLUGIN_CONFIG.name}:{name} 用了词表外的占位符 `${{{base}}}`")


def main() -> int:
    errors: list[str] = []
    check_project_config(errors)
    check_plugin_config(errors)
    if errors:
        print("client-config guard FAILED —— 提交的客户端配置连不上：", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print(
        "client-config OK: 项目配置无插件占位符、占位符全带默认值、--directory 指向真实包；"
        "插件配置占位符 ⊆ 插件词表且 user_config 键均已声明。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
