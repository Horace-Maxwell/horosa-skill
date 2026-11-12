"""MCP-11：给照字面办事的模型用的广告层——每个属性都有描述、同名字段同一句、闭集有 enum、嵌套有形状、标题不断词。"""
from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces import mcp_schema
from horosa_skill.surfaces.mcp_server import create_mcp_server
from horosa_skill.surfaces.mcp_surface import _tool_title, _word_safe

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_mcp_list_budget.py"


@pytest.fixture(scope="module")
def surfaces(tmp_path_factory: pytest.TempPathFactory) -> dict[str, list[dict]]:
    root = tmp_path_factory.mktemp("field-docs")
    out: dict[str, list[dict]] = {}
    for label, compact in (("full", False), ("compact", True)):
        settings = Settings(db_path=root / f"{label}.db", output_dir=root / "runs", mcp_compact=compact)
        mcp = create_mcp_server(HorosaSkillService(settings, store=MemoryStore(settings)), settings)
        out[label] = [tool.model_dump(mode="json", by_alias=True) for tool in asyncio.run(mcp.list_tools())]
    return out


def _verifier():
    spec = importlib.util.spec_from_file_location("verify_mcp_list_budget_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _tool(tools: list[dict], name: str) -> dict:
    return next(tool for tool in tools if tool["name"] == name)


def test_no_advertised_property_lacks_a_description(surfaces: dict) -> None:
    verifier = _verifier()
    assert verifier.undescribed_properties(surfaces["full"]) == []
    assert verifier.undescribed_properties(surfaces["compact"]) == []


def test_the_gate_goes_red_on_an_undescribed_property() -> None:
    tools = [{"name": "t", "inputSchema": {"properties": {"a": {"type": "string"}, "b": {
        "type": "object", "description": "x", "properties": {"c": {"type": "string"}}}}}}]
    assert _verifier().undescribed_properties(tools) == ["t.a", "t.b.c"]


def test_fields_without_their_own_description_share_one_sentence(surfaces: dict) -> None:
    """词典补的是「模型上没写描述」的字段：同一个名字在所有工具上是同一句。

    工具模型自己写了描述的（例如各技法 after23NewDay 的缺省不同）保留工具自己的——那句话带着本工具的缺省值。
    """
    from horosa_skill.surfaces.mcp_field_docs import field_docs

    docs = field_docs()
    for name in ("gpsLat", "gpsLon", "include_payload", "include_raw_json", "language", "title"):
        texts = {
            prop.get("description")
            for surface in surfaces.values() for tool in surface
            for key, prop in ((tool.get("inputSchema") or {}).get("properties") or {}).items()
            if key == name and not str(prop.get("description", "")).startswith("[required]")
        }
        assert texts == {docs[name]}, (name, texts)


def test_closed_sets_have_enums_and_tool_run_says_how_to_find_names(surfaces: dict) -> None:
    render = _tool(surfaces["full"], "horosa_report_render")["inputSchema"]["properties"]
    assert render["format"]["enum"] == ["json", "docx", "pdf", "png", "ics"]
    assert render["style"]["enum"] == ["analysis", "chart"]
    tool_run = _tool(surfaces["compact"], "horosa_tool_run")["inputSchema"]["properties"]["tool_name"]
    assert "horosa://catalog/techniques" in tool_run["description"]


def test_relative_inner_and_outer_are_shaped(surfaces: dict) -> None:
    props = _tool(surfaces["full"], "horosa_astro_relative")["inputSchema"]["properties"]
    for side in ("inner", "outer"):
        assert props[side]["type"] == "object"
        assert {"date", "time", "zone", "lat", "lon"} <= set(props[side]["properties"])
        assert all(p.get("description") for p in props[side]["properties"].values())


def test_facades_that_do_not_gate_do_not_advertise_the_gate_keys(surfaces: dict) -> None:
    for tool in surfaces["full"]:
        props = set(((tool.get("inputSchema") or {}).get("properties") or {}))
        if tool["name"] in mcp_schema.UNGATED_FACADES:
            assert not props & set(mcp_schema.GATE_KEYS), tool["name"]
    assert set(mcp_schema.GATE_KEYS) <= set(_tool(surfaces["full"], "horosa_dispatch")["inputSchema"]["properties"])


@pytest.mark.parametrize(("text", "expected"), [
    ("把星阙 AI 导出文本快照解析为结构化 JSON 啊啊", "把星阙 AI 导出文本快照解析为结构化 JSON"),
    ("精读一条知识（带出处）：内置知识 domain+key", "精读一条知识（带出处）：内置知识"),
    ("abcdefghij klmnopqrstuvwxyzABCDE", "abcdefghij"),
    ("短标题", "短标题"),
])
def test_titles_are_not_cut_mid_word(text: str, expected: str) -> None:
    assert _word_safe(text, 24) == expected


def test_every_real_title_ends_on_a_whole_word() -> None:
    from horosa_skill.engine.registry import TOOL_DEFINITIONS

    for name in TOOL_DEFINITIONS:
        title = _tool_title(name)
        if title is None:
            continue
        head = TOOL_DEFINITIONS[name].description.split("。", 1)[0]
        nxt = head[len(title):len(title) + 1] if head.startswith(title) else ""
        assert not (title[-1:].isascii() and title[-1:].isalnum() and nxt.isascii() and nxt.isalnum()), (name, title)
