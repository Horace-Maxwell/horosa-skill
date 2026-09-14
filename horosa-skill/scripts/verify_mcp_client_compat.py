#!/usr/bin/env python3
"""广告层必须是**最低公分母客户端**也能吃下的形状。

v0.36.0 之前的广告层只对 Claude Code 对过。实测（v0.37.0 修复前，116 个工具）：
  · 70 个属性广告成空对象 `{}`（gpsLat/gpsLon×26、datetime/dirZone×6、dirLat/dirLon×3 …），
    根因是 `_widen` 里一句表达式语句把 anyOf pop 掉却不补 type；
  · 116/116 个工具带**数组** `type`（`request: ["object","string"]`、lat/lon、gender）；
  · 108 个工具写 `additionalProperties: true`；106 个工具漏出私有键 `x-horosa-hidden-knobs`；
  · 8 个门面完全没被广告层重写，直接把 pydantic 原样的 `anyOf:[…,{null}]` / `default` / `title` 发上线。
Gemini CLI / Vertex 的 FunctionDeclaration 与 OpenAI strict function calling 见到这些会拒 ——
**拒的是整张工具表，不是单个字段**，所以症状是「这个 MCP server 在某某客户端里一个工具都没有」。

这把守卫在进程内构建 full / compact 两个面，逐工具断言可移植性，并把
「没有描述的属性」做成只减不增的棘轮。负向对照见 tests/test_verify_mcp_client_compat.py。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys

# Windows 控制台默认 cp1252/cp936：脚本自己 print 的中文会抛 UnicodeEncodeError 并让脚本 exit 1
# （v0.38.0 的 repack 脚本在「打印成功信息」那一步失败过）。统一在入口把两条流改成 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")
import tempfile
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
PKG_ROOT = SCRIPTS.parent
BASELINE = PKG_ROOT / "contracts" / "mcp_client_compat.json"
sys.path.insert(0, str(PKG_ROOT / "src"))

NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
# Gemini CLI 在同名冲突时前缀 `serverName__`，并把超过 63 字符的名字中段截断成 `___`。
GEMINI_PREFIX = "horosa__"
GEMINI_NAME_LIMIT = 63
# OpenAI function 描述上限 1024 字符（超出即拒/截断）。
DESCRIPTION_CHAR_LIMIT = 1024
FORBIDDEN_KEYWORDS = ("$ref", "$defs", "oneOf", "allOf", "anyOf", "not", "patternProperties", "dependentSchemas")
PROP_FORBIDDEN_KEYS = ("default", "title", "format", "$schema")


def audit_tool(tool: dict[str, Any]) -> list[str]:
    """单个工具的可移植性断言（纯函数，测试可注入坏样本）。"""
    errors: list[str] = []
    name = str(tool.get("name") or "")
    if not NAME_RE.match(name):
        errors.append(f"{name!r}: 工具名不符 ^[a-zA-Z0-9_-]{{1,64}}$")
    if len(GEMINI_PREFIX + name) > GEMINI_NAME_LIMIT:
        errors.append(f"{name}: 加上 Gemini 的 `{GEMINI_PREFIX}` 前缀后 {len(GEMINI_PREFIX + name)} > {GEMINI_NAME_LIMIT} 会被中段截断")

    description = str(tool.get("description") or "")
    if not description.strip():
        errors.append(f"{name}: 描述为空（模型据此选工具）")
    elif len(description) > DESCRIPTION_CHAR_LIMIT:
        errors.append(f"{name}: 描述 {len(description)} 字符 > {DESCRIPTION_CHAR_LIMIT}（OpenAI 上限）")
    if not str(tool.get("title") or "").strip():
        errors.append(f"{name}: 缺 title")
    if not tool.get("annotations"):
        errors.append(f"{name}: 缺 annotations")

    schema = tool.get("inputSchema") or {}
    blob = json.dumps(schema, ensure_ascii=False)
    for keyword in FORBIDDEN_KEYWORDS:
        if f'"{keyword}"' in blob:
            errors.append(f"{name}: inputSchema 含 `{keyword}`（Gemini/Vertex 拒收）")
    if schema.get("type") != "object":
        errors.append(f"{name}: inputSchema 根 type 必须是 object")
    if schema.get("additionalProperties") not in (None, False):
        errors.append(f"{name}: additionalProperties={schema.get('additionalProperties')!r}（OpenAI strict 要求缺省或 false）")
    for key in schema:
        if key.startswith("x-"):
            errors.append(f"{name}: 广告层漏出私有键 `{key}`")

    for prop_name, prop in (schema.get("properties") or {}).items():
        where = f"{name}.{prop_name}"
        if not isinstance(prop, dict) or not prop:
            errors.append(f"{where}: 属性是空对象 —— 客户端不知道该传什么类型")
            continue
        prop_type = prop.get("type")
        if prop_type is None:
            errors.append(f"{where}: 属性没有 type")
        elif isinstance(prop_type, list):
            errors.append(f"{where}: type 是数组 {prop_type}（Gemini/Vertex 与 OpenAI strict 都要求单个 type）")
        elif prop_type == "array":
            items = prop.get("items")
            if not isinstance(items, dict) or not items.get("type"):
                errors.append(f"{where}: array 没有带 type 的 items（Gemini 会 400 INVALID_ARGUMENT）")
        for bad in PROP_FORBIDDEN_KEYS:
            if bad in prop:
                errors.append(f"{where}: 属性含 `{bad}`")
        for key in prop:
            if key.startswith("x-"):
                errors.append(f"{where}: 属性漏出私有键 `{key}`")

    required = schema.get("required")
    if required is not None:
        if not isinstance(required, list):
            errors.append(f"{name}: required 必须是数组")
        else:
            unknown = [r for r in required if r not in (schema.get("properties") or {})]
            if unknown:
                errors.append(f"{name}: required 指向不存在的属性 {unknown}")
    return errors


def _surface(compact: bool) -> list[dict[str, Any]]:
    from horosa_skill.config import Settings
    from horosa_skill.memory.store import MemoryStore
    from horosa_skill.service import HorosaSkillService
    from horosa_skill.surfaces.mcp_server import create_mcp_server

    with tempfile.TemporaryDirectory() as tmp:
        settings = Settings(
            runtime_root=Path(tmp) / "rt",
            db_path=Path(tmp) / "m.db",
            output_dir=Path(tmp) / "runs",
            mcp_compact=compact,
            server_root="http://127.0.0.1:9",
            chart_server_root="http://127.0.0.1:9",
        )
        mcp = create_mcp_server(HorosaSkillService(settings, store=MemoryStore(settings)), settings)
        return [tool.model_dump(mode="json") for tool in asyncio.run(mcp.list_tools())]


def measure() -> dict[str, Any]:
    from horosa_skill.engine.registry import TOOL_DEFINITIONS
    from horosa_skill.surfaces.mcp_server import COMPACT_SURFACE_TOOL_COUNT, FACADE_TOOL_COUNT

    out: dict[str, Any] = {"surfaces": {}, "debt": {}}
    for label, compact, expected in (
        ("full", False, FACADE_TOOL_COUNT + len(TOOL_DEFINITIONS)),
        ("compact", True, COMPACT_SURFACE_TOOL_COUNT),
    ):
        tools = _surface(compact)
        errors: list[str] = []
        if len(tools) != expected:
            errors.append(f"{label} 面 {len(tools)} 个工具 ≠ 期望 {expected}")
        for tool in tools:
            errors.extend(audit_tool(tool))
        undescribed = sum(
            1
            for tool in tools
            for prop in ((tool.get("inputSchema") or {}).get("properties") or {}).values()
            if isinstance(prop, dict) and not str(prop.get("description") or "").strip()
        )
        out["surfaces"][label] = {"tools": len(tools), "errors": errors}
        out["debt"][f"{label}_properties_without_description"] = undescribed
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--update-baseline", action="store_true")
    args = ap.parse_args()
    result = measure()
    errors = [e for surface in result["surfaces"].values() for e in surface["errors"]]

    if args.update_baseline:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(
            json.dumps(
                {
                    "_comment": (
                        "客户端可移植性契约：广告层每个属性恰一个标量 type、array 有 items、"
                        "无 anyOf/$ref/私有键/default、additionalProperties 缺省或 false、"
                        "描述 ≤1024 字符、名字加 Gemini 前缀后 ≤63。debt 是「没有描述的属性数」，只减不增。"
                        "刷新：uv run python scripts/verify_mcp_client_compat.py --update-baseline"
                    ),
                    "limits": {
                        "description_chars": DESCRIPTION_CHAR_LIMIT,
                        "gemini_name_limit": GEMINI_NAME_LIMIT,
                    },
                    "tools": {k: v["tools"] for k, v in result["surfaces"].items()},
                    "debt": result["debt"],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"baseline updated: {result['debt']}")
        return 0

    if not BASELINE.is_file():
        print(f"missing {BASELINE.relative_to(PKG_ROOT)} — seed it with --update-baseline", file=sys.stderr)
        return 1
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    for key, allowed in (base.get("debt") or {}).items():
        got = result["debt"].get(key, 0)
        if got > allowed:
            errors.append(f"{key} {got} > 基线 {allowed}（无描述属性只减不增）")
    paid = [k for k, v in (base.get("debt") or {}).items() if result["debt"].get(k, 0) < v]
    if paid and not errors:
        print(
            f"client-compat debt dropped ({paid}) — run `--update-baseline` to lock the gain in.",
            file=sys.stderr,
        )
        return 1

    if errors:
        print("mcp-client-compat guard FAILED —— 严格客户端会拒收整张工具表：", file=sys.stderr)
        for err in errors[:40]:
            print(f"  - {err}", file=sys.stderr)
        if len(errors) > 40:
            print(f"  … 另 {len(errors) - 40} 条", file=sys.stderr)
        return 1

    tools = {k: v["tools"] for k, v in result["surfaces"].items()}
    print(f"mcp-client-compat OK: full {tools['full']} / compact {tools['compact']} 个工具全部可移植；debt {result['debt']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
