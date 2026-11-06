"""`request` 与顶层参数同时给时两边都算数（v0.47.2-dev）。

`_merge_mcp_arguments` 曾在 `request` 存在时整体改用它，兄弟参数全丢：`horosa_astro_chart(hsys=3, zodiacal=1, request={完整载荷})`
回 `ok=True`、盘按 hsys=1 / zodiacal=0 起，没有一句警告。`horosa_tool_run` 的描述还教调用方这么写（公共字段放顶层、技法专属放 `request`），
照做的结果是闸门把已经给过的日期再问一遍。精简面是七家客户端的缺省，这条路是常走的路。
"""
from __future__ import annotations

import json
from pathlib import Path

import anyio
import pytest

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.schemas.common import DispatchEnvelope, ToolEnvelope
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces import mcp_server as M
from horosa_skill.surfaces import mcp_requests
from horosa_skill.surfaces.mcp_requests import _merge_mcp_arguments

BIRTH = {"date": "1990-06-15", "time": "10:30:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gender": 1}
CONFIRM = {"agent_confirmed_settings": True}


def _server(tmp_path: Path, *, compact: bool = False):
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
                        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs", mcp_compact=compact)
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    seen: list[dict] = []

    def _run_tool(tool_name: str, payload: dict, **_kwargs) -> ToolEnvelope:
        seen.append(dict(payload))
        return ToolEnvelope(ok=True, tool=tool_name, version="test", input_normalized=dict(payload))

    service.run_tool = _run_tool  # type: ignore[method-assign]
    return M.create_mcp_server(service, settings), service, seen


def _call(mcp, name: str, arguments: dict) -> dict:
    async def _go():
        return await mcp.call_tool(name, arguments)

    return json.loads(anyio.run(_go).content[0].text)


def test_flat_arguments_fill_what_request_left_out() -> None:
    assert _merge_mcp_arguments({"request": {"run_id": "abc"}, "tool": "chart"}) == {"run_id": "abc", "tool": "chart"}


def test_request_wins_a_conflict_and_the_conflict_is_noted() -> None:
    with mcp_requests.request_conflict_scope() as notes:
        merged = _merge_mcp_arguments({"request": {"hsys": 1}, "hsys": 3, "zodiacal": 1})
    assert merged == {"hsys": 1, "zodiacal": 1}
    assert len(notes) == 1 and "hsys" in notes[0] and "zodiacal" not in notes[0]


def test_agreeing_siblings_are_not_a_conflict() -> None:
    with mcp_requests.request_conflict_scope() as notes:
        assert _merge_mcp_arguments({"request": {"hsys": 3}, "hsys": 3}) == {"hsys": 3}
    assert notes == []


def test_json_string_request_merges_like_an_object() -> None:
    assert _merge_mcp_arguments({"request": '{"hsys": 3}', "zodiacal": 1}) == {"hsys": 3, "zodiacal": 1}


def test_request_alone_passes_through_untouched() -> None:
    # 坏 JSON 留给下游按原路报 tool.invalid_payload；这里不抛（调用点在 try 之外）。
    assert _merge_mcp_arguments({"request": "{not json"}) == "{not json"
    assert _merge_mcp_arguments({"request": "{not json", "hsys": 3}) == "{not json"
    assert _merge_mcp_arguments({"request": None, "hsys": 3, "zodiacal": None}) == {"hsys": 3}


def test_declared_options_beside_a_full_request_reach_the_engine(tmp_path: Path) -> None:
    mcp, _service, seen = _server(tmp_path)
    body = _call(mcp, "horosa_astro_chart", {"hsys": 3, "zodiacal": 1, "request": {**BIRTH, **CONFIRM}})
    assert body["ok"] is True, body
    assert (seen[0]["hsys"], seen[0]["zodiacal"]) == (3, 1)
    assert body["warnings"] == []


def test_the_mix_tool_run_documents_works_as_documented(tmp_path: Path) -> None:
    """`horosa_tool_run` 的描述原文：公共字段顶层、技法专属字段进 request。"""
    mcp, _service, seen = _server(tmp_path, compact=True)
    body = _call(mcp, "horosa_tool_run", {"tool_name": "liureng_gods", **BIRTH, **CONFIRM, "request": {"guirengType": 2}})
    assert body["ok"] is True, body
    assert seen[0]["guirengType"] == 2 and seen[0]["date"] == BIRTH["date"]


def test_the_gate_reads_the_merged_payload_both_ways(tmp_path: Path) -> None:
    mcp, _service, seen = _server(tmp_path)
    # 确认位在顶层、载荷在 request：放行。
    assert _call(mcp, "horosa_astro_chart", {**CONFIRM, "request": BIRTH})["ok"] is True
    # 两边都没有确认位：闸门照拦，合并不开后门。
    seen.clear()
    refused = _call(mcp, "horosa_astro_chart", {"date": BIRTH["date"], "request": BIRTH})
    assert refused["code"] == "agent_guidance.required" and seen == []


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("horosa_astro_chart", {"hsys": 3, "request": {**BIRTH, **CONFIRM, "hsys": 1}}),
        ("horosa_dispatch", {"query": "看星盘", "request": {"query": "看八字", "birth": BIRTH, **CONFIRM}}),
        ("horosa_memory_query", {"limit": 5, "request": {"limit": 1}}),
    ],
    ids=["technique-envelope", "dispatch-envelope", "facade-dict"],
)
def test_a_conflict_warning_reaches_every_result_shape(tmp_path: Path, tool: str, arguments: dict) -> None:
    mcp, _service, _seen = _server(tmp_path)
    body = _call(mcp, tool, arguments)
    assert any("request" in str(line) for line in body.get("warnings") or []), body


def test_warning_helper_handles_every_result_shape() -> None:
    from horosa_skill.surfaces.mcp_runner import _with_request_notes

    envelope = _with_request_notes(ToolEnvelope(ok=True, tool="chart", version="x", input_normalized={}), ["n"])
    assert envelope.warnings == ["n"]
    assert _with_request_notes(DispatchEnvelope(ok=True, version="x", warnings=["a"]), ["n"]).warnings == ["a", "n"]
    assert _with_request_notes({"ok": True}, ["n"]) == {"ok": True, "warnings": ["n"]}
    assert _with_request_notes({"ok": True, "warnings": ["a"]}, []) == {"ok": True, "warnings": ["a"]}
