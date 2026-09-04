"""v0.36.0 B1 — two-layer MCP schema: slim advertised inputSchema, full validation signature.

`tools/list` was 1186 KB (≈318k tokens). The advertised layer now carries the domain core + the tool's own
fields + a `request` escape hatch, while the function signature still declares every model field so an
agent that knows an advanced knob can pass it at top level and it is **not** dropped.
"""
from __future__ import annotations

import asyncio
import json

import pytest
from test_service import FakeClient, FakeJsClient

from horosa_skill.astro_sidereal import INDIA_HOUSE_SYSTEM_LABELS
from horosa_skill.config import Settings
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.memory.store import MemoryStore
from horosa_skill.schemas.tools import BirthInput
from horosa_skill.service import ASTRO_HOUSE_SYSTEM_TEXT, HorosaSkillService
from horosa_skill.surfaces.mcp_schema import GATE_KEYS, advertised_technique_schema
from horosa_skill.surfaces.mcp_server import create_mcp_server
from horosa_skill.testing_payloads import build_sample_payloads

FULL_CAP = 256 * 1024
COMPACT_CAP = 30 * 1024


def _server(tmp_path, *, compact: bool = False):
    settings = Settings(db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs", mcp_compact=compact)
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    return create_mcp_server(service, settings)


def _listed(mcp) -> dict[str, dict]:
    return {tool.name: tool.model_dump(mode="json") for tool in asyncio.run(mcp.list_tools())}


@pytest.fixture(scope="module")
def full_tools(tmp_path_factory) -> dict[str, dict]:
    return _listed(_server(tmp_path_factory.mktemp("full")))


def test_full_surface_fits_the_budget(full_tools) -> None:
    size = len(json.dumps(list(full_tools.values()), ensure_ascii=False).encode("utf-8"))
    assert size <= FULL_CAP, f"full tools/list is {size} B (> {FULL_CAP} B)"
    assert len(full_tools) == 10 + len(TOOL_DEFINITIONS)


def test_compact_surface_fits_the_budget(tmp_path) -> None:
    tools = _listed(_server(tmp_path, compact=True))
    size = len(json.dumps(list(tools.values()), ensure_ascii=False).encode("utf-8"))
    assert size <= COMPACT_CAP, f"compact tools/list is {size} B (> {COMPACT_CAP} B)"


def test_advertised_schema_shape_is_flat_and_open(full_tools) -> None:
    schema = full_tools["horosa_astro_chart"]["inputSchema"]
    text = json.dumps(schema)
    assert "$ref" not in text and "$defs" not in text
    assert schema["additionalProperties"] is True
    props = schema["properties"]
    for key in ("date", "time", "zone", "lat", "lon", "hsys", "zodiacal", "request", *GATE_KEYS):
        assert key in props, key
    assert schema["x-horosa-hidden-knobs"] > 40  # the BirthInput long tail is hidden, not deleted
    assert "高级旋钮" in props["request"]["description"]
    # 中式技法不广告宫制/黄道，但广告性别
    qimen = full_tools["horosa_cn_qimen"]["inputSchema"]["properties"]
    assert "hsys" not in qimen and "zodiacal" not in qimen
    # 澄清闸段不再逐工具重复（server instructions 已讲），描述指向 guidance
    assert "澄清闸" not in full_tools["horosa_astro_chart"]["description"]
    assert "horosa_agent_guidance" in full_tools["horosa_astro_chart"]["description"]


def test_predictive_tools_advertise_their_target_fields(full_tools) -> None:
    props = full_tools["horosa_predict_solarreturn"]["inputSchema"]["properties"]
    for key in ("datetime", "dirZone", "dirLat", "dirLon"):
        assert key in props, key


def test_enums_are_locked_to_their_tables(full_tools) -> None:
    hsys = full_tools["horosa_astro_chart"]["inputSchema"]["properties"]["hsys"]
    assert hsys["enum"] == sorted(int(k) for k in ASTRO_HOUSE_SYSTEM_TEXT)
    assert "3=Placidus" in hsys["description"] and "1=Alcabitus" in hsys["description"]
    india = full_tools["horosa_astro_india_chart"]["inputSchema"]["properties"]["hsys"]
    assert india["enum"] == sorted(INDIA_HOUSE_SYSTEM_LABELS)
    props = full_tools["horosa_astro_chart"]["inputSchema"]["properties"]
    assert props["zodiacal"]["enum"] == [0, 1]
    assert props["ad"]["enum"] == [1, -1]
    assert props["response_view"]["enum"] == ["full", "sections", "titles"]


def test_dispatch_and_hecan_advertise_a_single_loose_object(full_tools) -> None:
    for name in ("horosa_dispatch", "horosa_hecan"):
        schema = full_tools[name]["inputSchema"]
        assert "anyOf" not in json.dumps(schema["properties"]["birth"])
        assert schema["properties"]["birth"]["type"] == "object"
        assert len(json.dumps(schema, ensure_ascii=False).encode("utf-8")) < 3 * 1024
    assert "tools" in full_tools["horosa_hecan"]["inputSchema"]["properties"]


def test_hidden_knob_passed_at_top_level_still_reaches_run_tool(tmp_path) -> None:
    mcp = _server(tmp_path)
    schema = advertised_technique_schema("chart", {"properties": BirthInput.model_json_schema().get("properties", {})})
    advertised = set(schema["properties"])
    hidden = [f for f in BirthInput.model_fields if f not in advertised]
    assert hidden
    # 挑一个整数/布尔类的隐藏旋钮，顶层直接传：广告层没有它，校验层必须照收
    knob = next(f for f in hidden if "int" in str(BirthInput.model_fields[f].annotation) or "bool" in str(BirthInput.model_fields[f].annotation))
    payload = {**build_sample_payloads()["chart"], knob: 1}
    result = asyncio.run(mcp.call_tool("horosa_astro_chart", payload))
    # FastMCP 1.x：声明了 outputSchema 时返回 (content, structured)，否则返回 content 序列
    if isinstance(result, tuple):
        content, structured = result
        envelope = structured if isinstance(structured, dict) else json.loads(content[0].text)
    elif isinstance(result, dict):
        envelope = result
    else:
        envelope = json.loads(result[0].text)
    assert envelope["ok"] is True, envelope.get("error")
    assert envelope["input_normalized"].get(knob) in (1, True), (knob, envelope["input_normalized"].get(knob))
