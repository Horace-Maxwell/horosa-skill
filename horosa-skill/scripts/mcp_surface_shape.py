#!/usr/bin/env python3
"""MCP 广告层的「形状」快照：tools/list 去掉全部描述文字之后剩下的东西（全量面 + 精简面）。

瘦身 tools/list 只许动两样：描述文字、线上并不携带信息的结构冗余。每个工具的属性名集合、每个属性的 type / enum / items、
嵌套对象的字段、标题、注解、`_meta` 一律不许变——变了就是改了客户端看到的接口，不是瘦身。总量棘轮
（`verify_mcp_list_budget.py`）只看字节：把一个字段从广告层拿掉，它只会报「变小了」。这份快照把「形状没变」单独钉住。

    uv run python scripts/mcp_surface_shape.py            # 与基线逐项比对，列出每一处不同（exit 1）
    uv run python scripts/mcp_surface_shape.py --write    # 看过差异、确认是有意的增改之后，重写基线
    uv run python scripts/mcp_surface_shape.py --dump f   # 把当前形状写到别处（做前后对照用）

基线 `tests/fixtures/sync314_budget_surface_shape.json`。按设计不广告的键登记在
`surfaces/mcp_schema.py::unadvertised_by_design`（每一类各带「不广告也不亏」的机检），比对时从基线里减掉，且当前广告层里必须真的没有。
守卫：`tests/test_sync314_budget_surface_shape.py`。进程内构建，不需要 runtime。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")

SCRIPTS = Path(__file__).resolve().parent
PKG_ROOT = SCRIPTS.parent
BASELINE = PKG_ROOT / "tests" / "fixtures" / "sync314_budget_surface_shape.json"
sys.path.insert(0, str(PKG_ROOT / "src"))

SURFACES = (("full", False), ("compact", True))
# 属性里算「形状」的键：除 description 以外、可移植广告层允许出现的全部（surfaces/mcp_schema.py::_PORTABLE_PROP_KEYS）。
# 这里不引用那张表：表里多放一个键，这里要跟着红（_unknown_keys），而不是跟着放行。
_SHAPE_KEYS = ("type", "enum", "items", "properties")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def property_shape(prop: dict[str, Any]) -> str:
    """一个属性去掉描述之后的签名：`type` + enum + items + 嵌套字段；认不出的键原样带上（多出来就会和基线不同）。"""
    kind = prop.get("type")
    parts = [kind if isinstance(kind, str) else _json(kind)]
    if "enum" in prop:
        parts.append(f"enum={_json(prop['enum'])}")
    if "items" in prop:
        parts.append(f"items={_json(prop['items'])}")
    if isinstance(prop.get("properties"), dict):
        nested = {name: property_shape(child) for name, child in prop["properties"].items()}
        parts.append(f"properties={_json(nested)}")
    unknown = sorted(set(prop) - set(_SHAPE_KEYS) - {"description"})
    if unknown:
        parts.append(f"other={_json({key: prop[key] for key in unknown})}")
    return " ".join(parts)


def tool_shape(tool: dict[str, Any]) -> dict[str, Any]:
    """一个工具去掉描述之后的形状。`tool` 是线上形状（`wire_tools`）。"""
    schema = dict(tool.get("inputSchema") or {})
    props = schema.pop("properties", None) or {}
    extra = {key: value for key, value in tool.items() if key not in {"name", "description", "inputSchema"}}
    return {
        "tool": _json(extra),  # title / annotations / _meta……描述以外的每一个顶层键（一行一个工具，diff 好读）
        "schema": _json(schema),  # type / required / additionalProperties……properties 以外的每一个键
        "properties": {name: property_shape(prop if isinstance(prop, dict) else {}) for name, prop in props.items()},
    }


def wire_tools(*, compact: bool, directory: Path) -> list[dict[str, Any]]:
    """这一面线上真发的 tools 数组（与 `verify_mcp_list_budget.py` 同一种量法）。"""
    from verify_mcp_list_budget import wire_shape

    from horosa_skill.config import Settings
    from horosa_skill.memory.store import MemoryStore
    from horosa_skill.service import HorosaSkillService
    from horosa_skill.surfaces.mcp_server import create_mcp_server

    settings = Settings(db_path=directory / f"shape-{int(compact)}.db", output_dir=directory / "runs", mcp_compact=compact)
    mcp = create_mcp_server(HorosaSkillService(settings, store=MemoryStore(settings)), settings)
    return [wire_shape(tool) for tool in asyncio.run(mcp.list_tools())]


def current_shape() -> dict[str, dict[str, Any]]:
    with tempfile.TemporaryDirectory() as tmp:
        return {
            label: {str(tool["name"]): tool_shape(tool) for tool in wire_tools(compact=compact, directory=Path(tmp))}
            for label, compact in SURFACES
        }


def silent_keys() -> dict[str, frozenset[str]]:
    """{MCP 工具名: 按设计不广告的键}（理由与守卫在 mcp_schema._unadvertised_by_design 旁）。"""
    from horosa_skill.surfaces.mcp_schema import unadvertised_by_design

    return unadvertised_by_design()


def expected_shape(baseline: dict[str, dict[str, Any]], silent: dict[str, frozenset[str]]) -> dict[str, dict[str, Any]]:
    """基线减去按设计不广告的键。基线重写之后那些键本来就不在，减法是空操作。"""
    out: dict[str, dict[str, Any]] = {}
    for surface, tools in baseline.items():
        out[surface] = {}
        for name, shape in tools.items():
            drop = silent.get(name, frozenset())
            out[surface][name] = {**shape, "properties": {k: v for k, v in shape["properties"].items() if k not in drop}}
    return out


def diff_shapes(expected: dict[str, dict[str, Any]], current: dict[str, dict[str, Any]]) -> list[str]:
    """逐面、逐工具、逐属性的不同；空表 = 形状相同。"""
    out: list[str] = []
    for surface in sorted(set(expected) | set(current)):
        want, got = expected.get(surface, {}), current.get(surface, {})
        for name in sorted(set(want) - set(got)):
            out.append(f"{surface}: 工具没了 {name}")
        for name in sorted(set(got) - set(want)):
            out.append(f"{surface}: 多了工具 {name}")
        for name in sorted(set(want) & set(got)):
            for part in ("tool", "schema"):
                if want[name][part] != got[name][part]:
                    out.append(f"{surface}: {name} 的 {part} 变了：{want[name][part]} → {got[name][part]}")
            before, after = want[name]["properties"], got[name]["properties"]
            for key in sorted(set(before) - set(after)):
                out.append(f"{surface}: {name}.{key} 不再广告（原 {before[key]}）")
            for key in sorted(set(after) - set(before)):
                out.append(f"{surface}: {name}.{key} 新广告（{after[key]}）")
            for key in sorted(set(before) & set(after)):
                if before[key] != after[key]:
                    out.append(f"{surface}: {name}.{key} 变了：{before[key]} → {after[key]}")
            if list(before) != list(after) and set(before) == set(after):
                out.append(f"{surface}: {name} 的属性顺序变了")
    return out


def still_advertised(current: dict[str, dict[str, Any]], silent: dict[str, frozenset[str]]) -> list[str]:
    """登记成「不广告」的键，当前广告层里必须真的没有（登记与实现不许各说各的）。"""
    return sorted(
        f"{surface}: {name}.{key}"
        for surface, tools in current.items()
        for name, shape in tools.items()
        for key in silent.get(name, frozenset())
        if key in shape["properties"]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--write", action="store_true", help="rewrite the baseline from the current surfaces")
    parser.add_argument("--dump", type=Path, help="write the current shape to this file and exit")
    args = parser.parse_args()
    current = current_shape()
    text = json.dumps(current, ensure_ascii=False, indent=1, sort_keys=False) + "\n"
    if args.dump:
        args.dump.write_text(text, encoding="utf-8", newline="\n")
        return 0
    if args.write:
        BASELINE.write_text(text, encoding="utf-8", newline="\n")
        print(f"baseline written: {', '.join(f'{k} {len(v)} tools' for k, v in current.items())}")
        return 0
    if not BASELINE.is_file():
        print(f"missing {BASELINE.relative_to(PKG_ROOT)} — run with --write once to seed it", file=sys.stderr)
        return 1
    silent = silent_keys()
    problems = diff_shapes(expected_shape(json.loads(BASELINE.read_text(encoding="utf-8")), silent), current)
    problems += [f"{item} 登记成不广告，却还在广告层" for item in still_advertised(current, silent)]
    if problems:
        print(f"mcp advertised shape CHANGED ({len(problems)}):", file=sys.stderr)
        for line in problems[:60]:
            print(f"  - {line}", file=sys.stderr)
        if len(problems) > 60:
            print(f"  … {len(problems) - 60} more", file=sys.stderr)
        print("有意的增改：看过上面每一行之后 `uv run python scripts/mcp_surface_shape.py --write`。", file=sys.stderr)
        return 1
    print(f"mcp advertised shape OK: {', '.join(f'{k} {len(v)} tools' for k, v in current.items())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
