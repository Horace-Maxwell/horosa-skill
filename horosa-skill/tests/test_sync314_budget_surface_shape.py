"""tools/list 瘦身只许动描述文字与结构冗余：广告层的形状（去掉全部描述之后剩下的东西）与基线逐项相等（sync 3.14.0 budget 批）。

基线 `tests/fixtures/sync314_budget_surface_shape.json` 取自瘦身**之前**的工具面（提交顺序可查：基线先于瘦身落库），
所以本例在瘦身之后仍绿 = 每个工具的属性名集合、每个属性的 type / enum / items / 嵌套字段、标题、注解、`_meta` 都没动。
唯一许可的减项登记在 `mcp_schema.unadvertised_by_design`，每一类各有一条「不广告也不亏」的机检（见下）。

负向对照（逐条实跑过，括号里是红在哪）：
- `_enum_for` 里把 `ad` 的 enum 拿掉 → test_shape_matches_the_baseline：82 处 `….ad 变了：integer enum=[1,-1] → integer`；
- `CORE_TYPE["time"]` 改成 integer → 同一条：99 处 `….time 变了：string → integer`；
- `GATE_KEYS` 去掉 `clarification_notes` → 同一条：81 处（过闸技法「不再广告」；不过闸的门面反而「新广告」——摘门面三键用的就是这张表）；
- 登记了、广告层却没摘（`advertised_technique_schema` 里 `silent = frozenset()`）→ 三条都红：30 处「新广告」、
  `still_advertised` 非空、豁免技法广告了三键；
- 把过闸的 chart 当成豁免（`_unadvertised_by_design` 里 `or tool_name == "chart"`）→ test_only_tools_the_gate_never_stops_drop_the_gate_keys
  红在「horosa_astro_chart 过闸，广告层必须有闸门三键」。形状比对那条此时不红：它信登记表，登记得对不对归这一条管。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from horosa_skill.agent_guidance import validate_agent_preflight
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.surfaces import mcp_schema

PKG_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PKG_ROOT / "scripts"


@pytest.fixture(scope="module")
def shape_tool():
    sys.path.insert(0, str(SCRIPTS))  # mcp_surface_shape 自己 import verify_mcp_list_budget
    spec = importlib.util.spec_from_file_location("mcp_surface_shape_under_test", SCRIPTS / "mcp_surface_shape.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def current(shape_tool) -> dict:
    return shape_tool.current_shape()


def test_shape_matches_the_baseline(shape_tool, current) -> None:
    baseline = json.loads(shape_tool.BASELINE.read_text(encoding="utf-8"))
    problems = shape_tool.diff_shapes(shape_tool.expected_shape(baseline, shape_tool.silent_keys()), current)
    assert not problems, (
        f"广告层形状与基线不同（{len(problems)} 处）。有意的增改：逐行看过之后 "
        "`uv run python scripts/mcp_surface_shape.py --write`。\n" + "\n".join(problems[:40])
    )


def test_keys_unadvertised_by_design_are_really_gone_and_only_gate_keys_qualify(shape_tool, current) -> None:
    silent = shape_tool.silent_keys()
    assert shape_tool.still_advertised(current, silent) == []
    by_mcp = {definition.mcp_name for definition in TOOL_DEFINITIONS.values()}
    assert set(silent) <= by_mcp, "只有技法工具可以登记不广告的键；门面走 UNGATED_FACADES"
    allowed = set(mcp_schema.GATE_KEYS)
    assert all(keys <= allowed for keys in silent.values()), "新的一类「不广告的键」要带自己的机检，再放宽这里"


def test_only_tools_the_gate_never_stops_drop_the_gate_keys(current) -> None:
    """不广告闸门三键 ⇔ 闸门对这个技法恒放行（`enforced: False`，连空载荷也不拦）。两个方向都查：
    豁免的技法广告了三键 = 让模型以为要先确认；过闸的技法没广告 = 模型过不了闸。"""
    by_mcp = {definition.mcp_name: name for name, definition in TOOL_DEFINITIONS.items()}
    gate_keys = set(mcp_schema.GATE_KEYS)
    for mcp_name, shape in current["full"].items():
        tool = by_mcp.get(mcp_name)
        if tool is None:
            continue
        verdict = validate_agent_preflight(tool, {})
        never_stops = verdict.get("ok") is True and verdict.get("enforced") is False
        advertised = gate_keys & set(shape["properties"])
        if never_stops:
            assert not advertised, f"{mcp_name} 不过闸，却广告了 {sorted(advertised)}"
            assert validate_agent_preflight(tool, {"agent_confirmed_settings": False}).get("enforced") is False
        else:
            assert advertised == gate_keys, f"{mcp_name} 过闸，广告层必须有闸门三键（缺 {sorted(gate_keys - advertised)}）"


# ---------------------------------------------------------------- 比对器自己的对照（纯函数，喂合成样本）


def _shape(**props: str) -> dict:
    return {"full": {"t": {"tool": "{}", "schema": '{"type":"object"}', "properties": dict(props)}}}


def test_the_comparer_names_each_kind_of_change(shape_tool) -> None:
    base = _shape(date="string", ad="integer enum=[1,-1]", tags='array items={"type":"string"}')
    assert shape_tool.diff_shapes(base, base) == []
    assert shape_tool.diff_shapes(base, _shape(date="string", ad="integer enum=[1,-1]")) == [
        'full: t.tags 不再广告（原 array items={"type":"string"}）']
    assert shape_tool.diff_shapes(base, _shape(date="string", ad="integer", tags='array items={"type":"string"}')) == [
        "full: t.ad 变了：integer enum=[1,-1] → integer"]
    assert shape_tool.diff_shapes(base, _shape(date="integer", ad="integer enum=[1,-1]", tags='array items={"type":"string"}')) == [
        "full: t.date 变了：string → integer"]
    assert shape_tool.diff_shapes(base, {**base, "compact": {}}) == []
    grown = _shape(date="string", ad="integer enum=[1,-1]", tags='array items={"type":"string"}', extra="string")
    assert shape_tool.diff_shapes(base, grown) == ["full: t.extra 新广告（string）"]
    reordered = _shape(ad="integer enum=[1,-1]", date="string", tags='array items={"type":"string"}')
    assert shape_tool.diff_shapes(base, reordered) == ["full: t 的属性顺序变了"]
    assert shape_tool.diff_shapes(base, {"full": {}}) == ["full: 工具没了 t"]
    retitled = {"full": {"t": {**base["full"]["t"], "tool": '{"title":"x"}'}}}
    assert shape_tool.diff_shapes(base, retitled) == ['full: t 的 tool 变了：{} → {"title":"x"}']


def test_property_shape_ignores_descriptions_and_nothing_else(shape_tool) -> None:
    prop = {"type": "integer", "enum": [1, -1], "description": "-1=公元前"}
    assert shape_tool.property_shape(prop) == shape_tool.property_shape({**prop, "description": "换一句"}) == "integer enum=[1,-1]"
    assert shape_tool.property_shape({"type": "array", "items": {"type": "string"}}) == 'array items={"type":"string"}'
    nested = {"type": "object", "properties": {"date": {"type": "string", "description": "x"}}}
    assert shape_tool.property_shape(nested) == 'object properties={"date":"string"}'
    assert shape_tool.property_shape({"type": "string", "default": None}) == 'string other={"default":null}'
    assert shape_tool.tool_shape({"name": "t", "description": "d", "title": "T", "inputSchema": {
        "type": "object", "required": ["a"], "properties": {"a": {"type": "string", "description": "x"}}}}) == {
        "tool": '{"title":"T"}', "schema": '{"required":["a"],"type":"object"}', "properties": {"a": "string"}}


def test_silent_keys_are_subtracted_from_the_baseline_and_must_be_absent(shape_tool) -> None:
    base = _shape(date="string", agent_confirmed_settings="boolean")
    silent = {"t": frozenset({"agent_confirmed_settings"})}
    slim = _shape(date="string")
    assert shape_tool.diff_shapes(shape_tool.expected_shape(base, silent), slim) == []
    assert shape_tool.diff_shapes(shape_tool.expected_shape(base, {}), slim) == ["full: t.agent_confirmed_settings 不再广告（原 boolean）"]
    assert shape_tool.still_advertised(base, silent) == ["full: t.agent_confirmed_settings"]
    assert shape_tool.still_advertised(slim, silent) == []
