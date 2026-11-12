"""MCP 工具结果的线上体积预算（v0.46.1，`surfaces.mcp_runner.MCP_RESULT_WIRE_BUDGET`）。

官方 MCP SDK（mcp 2.x）客户端走 streamable HTTP 时单条 SSE 事件上限 1 MiB；八字 bazi_birth 的原始盘（整生流年 / 大运明细）
序列化后约 2.4 MB，整条调用报「Server-sent event exceeded the 1048576 byte limit」（v0.45.1 起即如此，v0.46.0 发布后
surface_audit 的 HTTP 阶段查出）。超预算时只略去 data 里最大的原始子树，给 AI 读的快照 / 导出段 / 依据卡一字不动。
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces import mcp_runner

SSE_EVENT_LIMIT = 1_048_576  # mcp/client/streamable_http.py
BIRTH = {"date": "1995-06-03", "time": "05:30:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gender": 1,
         "agent_confirmed_settings": True, "clarification_notes": "result budget test"}


def _server(tmp_path: Path):
    from horosa_skill.surfaces.mcp_server import create_mcp_server

    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
                        db_path=tmp_path / "m.db", output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt",
                        data_dir=tmp_path / "data")
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    return create_mcp_server(service, settings), service


def _call(mcp, name: str, args: dict) -> tuple[int, dict]:
    from mcp.client import Client

    async def run():
        async with Client(mcp) as client:
            result = await client.call_tool(name, args)
            return len(result.model_dump_json(by_alias=True, exclude_none=True).encode("utf-8")), json.loads(result.content[0].text)

    return asyncio.run(run())


def test_bazi_result_fits_one_sse_event_and_keeps_what_the_ai_reads(tmp_path: Path) -> None:
    """负向对照：call_tool 里去掉「超预算 → _fit_result_budget」分支 → 线上超预算，第一条断言红（实跑过）。

    v0.50.0-dev：缺省改成阅读视图（不带原始树，见 tests/test_result_view*.py），线上预算管的是 `full` 视图；
    JSON 正文不再缩进后八字全量约 33 万字符，只需略去 smallDirection 一张表。"""
    mcp, service = _server(tmp_path)
    wire, body = _call(mcp, "horosa_cn_bazi_birth", {**BIRTH, "response_view": "full"})
    assert wire <= mcp_runner.MCP_RESULT_WIRE_BUDGET < SSE_EVENT_LIMIT
    full = service.run_tool("bazi_birth", BIRTH, save_result=False).model_dump(mode="json")
    # 给 AI 读的部分逐字不变；原始盘只略去最大的两张明细表，四柱等小块留着。
    assert body["data"]["snapshot_text"] == full["data"]["snapshot_text"]
    for key in ("export_text", "sections", "selected_sections"):   # provenance.build_timestamp 随调用时刻走，不比
        assert body["data"]["export_snapshot"][key] == full["data"]["export_snapshot"][key], key
    # 依据卡逐字不变（refs = 这次存档的 run / trace id、generated_at = 调用时刻，两者随调用走 → 只比其余字段）
    volatile = {"refs", "generated_at"}
    assert {k: v for k, v in body["data"]["technique_card"].items() if k not in volatile} == {
        k: v for k, v in full["data"]["technique_card"].items() if k not in volatile}
    assert set(body["data"]) == set(full["data"]) and set(body) == set(full)
    bazi = body["data"]["bazi"]
    assert bazi["fourColumns"] == full["data"]["bazi"]["fourColumns"]
    small = bazi["smallDirection"]
    assert small["omitted"] == "too_large_for_mcp" and "memory show" in small["note"]
    assert bazi["direction"] == full["data"]["bazi"]["direction"], "放得下的明细原样留着"
    assert any("已略去原始明细" in w and "bazi.smallDirection" in w for w in body["warnings"])


def test_small_results_are_untouched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """预算内的结果与关掉预算时逐字节相同（不经 _fit_result_budget）。"""
    mcp, _ = _server(tmp_path)
    args = {"query": "休门", "domain": ""}
    _, normal = _call(mcp, "horosa_knowledge_search", args)
    monkeypatch.setattr(mcp_runner, "MCP_RESULT_WIRE_BUDGET", 10**12)
    _, unlimited = _call(mcp, "horosa_knowledge_search", args)
    assert normal == unlimited


def test_fit_is_pure_and_prefers_second_level_subtrees() -> None:
    raw = {"ok": True, "warnings": [], "memory_ref": {"run_id": "r1"},
           "data": {"snapshot_text": "x" * 10, "chart": {"big": "y" * 1_000_000, "small": [1, 2, 3]}, "other": "z" * 10}}
    before = json.dumps(raw)

    def convert(value):
        return json.dumps(value)

    fitted = mcp_runner._fit_result_budget(raw, convert)
    assert json.dumps(raw) == before  # 不改入参
    assert fitted["data"]["chart"]["small"] == [1, 2, 3] and fitted["data"]["chart"]["big"]["omitted"] == "too_large_for_mcp"
    assert "horosa-skill memory show r1" in fitted["data"]["chart"]["big"]["note"]
    assert fitted["data"]["snapshot_text"] == "x" * 10


def test_dispatch_results_are_fitted_across_techniques() -> None:
    """调度 / 合参（`results.<tool>`）也受线上预算管：v0.49.0 两个技法 3.2 MB 原样上线（审计 MCP-03）。

    负向对照：_fit_result_budget 去掉 results 映射这一支 → 原样返回，第一条断言红（实跑过）。"""
    def envelope(tool: str, size: int) -> dict:
        return {"ok": True, "tool": tool, "data": {"export_snapshot": {"export_text": "正文"},
                                                 "chart": {"big": "y" * size, "small": [1]}}, "warnings": []}

    raw = {"ok": True, "selected_tools": ["a", "b"], "memory_ref": {"run_id": "d1"}, "warnings": [],
           "results": {"a": envelope("a", 700_000), "b": envelope("b", 600_000)}}
    before = json.dumps(raw)
    fitted = mcp_runner._fit_result_budget(raw, lambda value: json.dumps(value))
    assert len(json.dumps(fitted)) <= mcp_runner.MCP_RESULT_WIRE_BUDGET
    assert json.dumps(raw) == before
    assert fitted["results"]["a"]["data"]["chart"]["big"]["omitted"] == "too_large_for_mcp"
    assert fitted["results"]["b"]["data"]["export_snapshot"] == {"export_text": "正文"}
    assert fitted["results"]["b"]["data"]["chart"]["small"] == [1]
    assert any("已略去原始明细" in w for w in fitted["warnings"])
