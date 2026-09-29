"""tools/list 预算守卫的**每工具**上限（v0.40.0）：Codex 0.158.0（2026-09-28）新增 `tool_input_schema_max_bytes`，缺省 5000 B，
超出的 inputSchema 会被「压缩」——参数说明被静默剥掉。守卫对全量 / 精简两面的每个工具都断言 ≤ 5000 B（今日最大 3843 B）。
负向对照：喂一个 6 KB 的合成工具必须被点名。（总量棘轮见 tests/test_mcp_list_budget.py；本文件只管每工具硬顶。）"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("verify_mcp_list_budget", PKG_ROOT / "scripts" / "verify_mcp_list_budget.py")
budget = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(budget)


def test_codex_per_tool_schema_cap_is_the_documented_default() -> None:
    assert budget.TOOL_INPUT_SCHEMA_CAP_BYTES == 5000
    base = json.loads((PKG_ROOT / "contracts" / "mcp_list_budget.json").read_text(encoding="utf-8"))
    assert base["hard_caps"]["tool_input_schema_bytes"] == 5000
    assert 0 < base["full_max_tool_input_schema_bytes"] <= 5000 and 0 < base["compact_max_tool_input_schema_bytes"] <= 5000


def test_oversized_tool_schemas_names_the_fat_tool_and_only_it() -> None:
    slim = {"name": "horosa_slim", "inputSchema": {"type": "object", "properties": {"date": {"type": "string"}}}}
    fat = {"name": "horosa_fat", "inputSchema": {"type": "object", "properties": {f"k{i}": {"type": "string", "description": "x" * 40} for i in range(120)}}}
    assert budget.input_schema_bytes(fat) > 5000 > budget.input_schema_bytes(slim)
    assert budget.oversized_tool_schemas([slim, fat]) == [("horosa_fat", budget.input_schema_bytes(fat))]
    assert budget.oversized_tool_schemas([slim]) == []


def test_every_advertised_tool_fits_the_codex_schema_budget() -> None:
    sizes = budget.measure()
    assert sizes["_oversized"] == {"full_bytes": [], "compact_bytes": []}, sizes["_oversized"]
