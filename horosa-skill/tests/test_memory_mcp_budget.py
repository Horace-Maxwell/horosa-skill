"""记忆门面的线上体积：`horosa_memory_query` 缺省只回摘要，`horosa_memory_query` / `horosa_memory_show` 带载荷时也受 MCP 预算约束。

台账：docs/LESSONS.md v0.47.2-dev「memory_query 缺省把 20 份全量产物塞进一条消息」。
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

SSE_EVENT_LIMIT = 1_048_576  # mcp/client/streamable_http.py，见 test_mcp_result_budget.py
READABLE = {"export_text": "八字起盘信息", "sections": [{"title": "起盘信息", "body": "四柱" * 12_000}]}  # 大过裁剪门槛：受保护键不是因为小才留下


def _server(tmp_path: Path):
    from horosa_skill.surfaces.mcp_server import create_mcp_server

    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
                        db_path=tmp_path / "m.db", output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt",
                        data_dir=tmp_path / "data")
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    return create_mcp_server(service, settings), service


def _stored_bazi(service: HorosaSkillService, *, raw_chars: int) -> str:
    """形状照真实八字存档：给 AI 读的快照很小，原始大运 / 流年明细很大。"""
    envelope = {
        "ok": True, "tool": "bazi_birth", "summary": ["s"],
        "data": {"snapshot_text": "快照", "export_snapshot": READABLE, "technique_card": {"technique": {"key": "bazi"}},
                 "bazi": {"fourColumns": {"year": "甲子"}, "direction": ["大运" * (raw_chars // 2)]}},
    }
    run_id = service.store.create_run(entrypoint="tool", query_text="问事业", group_id="g")
    service.store.record_tool_result(run_id=run_id, tool_name="bazi_birth", ok=True, input_normalized={}, envelope_dict=envelope,
                                     summary=["s"], warnings=[], error=None, trace_id="t", group_id="g")
    return run_id


def _call(mcp, name: str, args: dict) -> tuple[int, dict]:
    from mcp.client import Client

    async def run():
        async with Client(mcp) as client:
            result = await client.call_tool(name, args)
            return len(result.model_dump_json(by_alias=True, exclude_none=True).encode("utf-8")), json.loads(result.content[0].text)

    return asyncio.run(run())


def _payloads(body: dict) -> list[dict]:
    records = body.get("results") or [body["result"]]
    return [a["payload"] for r in records for a in r["artifacts"] if a["kind"] == "tool_result" and "payload" in a]


def test_memory_query_returns_summaries_by_default(tmp_path: Path) -> None:
    """工具说明写的是「Returns run summaries」。此前缺省带全量载荷：20 份 63 KB 的星盘 1.8 MB，超过 1 MiB 的 SSE 上限（2026-11-06 实测）。"""
    mcp, service = _server(tmp_path)
    for _ in range(3):
        _stored_bazi(service, raw_chars=300_000)

    wire, body = _call(mcp, "horosa_memory_query", {"limit": 3})

    assert wire < 100_000
    assert body["count"] == 3
    assert all("payload" not in artifact for record in body["results"] for artifact in record["artifacts"])
    assert all(artifact["path"] for record in body["results"] for artifact in record["artifacts"]), "摘要里仍能拿到产物路径"


def test_asking_for_payloads_still_fits_one_message(tmp_path: Path) -> None:
    mcp, service = _server(tmp_path)
    for _ in range(6):
        _stored_bazi(service, raw_chars=300_000)

    # 线上预算管的是 full 视图（原始树全带）；缺省阅读视图另见 tests/test_result_view*.py。
    wire, body = _call(mcp, "horosa_memory_query", {"limit": 6, "include_payload": True, "response_view": "full"})

    assert wire <= mcp_runner.MCP_RESULT_WIRE_BUDGET < SSE_EVENT_LIMIT
    payloads = _payloads(body)
    assert len(payloads) == 6
    assert all(p["data"]["export_snapshot"] == READABLE and p["data"]["snapshot_text"] == "快照" for p in payloads), "给 AI 读的部分一字不动"
    assert any(p["data"]["bazi"]["direction"].get("omitted") == "too_large_for_mcp" for p in payloads)
    assert any("已略去" in warning for warning in body["warnings"])


def test_memory_show_fits_one_message_and_keeps_what_the_ai_reads(tmp_path: Path) -> None:
    """`horosa_memory_show` 是「读回全量段落」的入口（references/reports.md），大八字整条超限时不能失败，段落要还在。"""
    mcp, service = _server(tmp_path)
    run_id = _stored_bazi(service, raw_chars=1_500_000)

    wire, body = _call(mcp, "horosa_memory_show", {"run_id": run_id, "response_view": "full"})

    assert wire <= mcp_runner.MCP_RESULT_WIRE_BUDGET
    payload = _payloads(body)[0]
    assert payload["data"]["export_snapshot"] == READABLE
    assert payload["data"]["bazi"]["fourColumns"] == {"year": "甲子"}, "只略去大的原始子树"
    direction = payload["data"]["bazi"]["direction"]
    assert direction["omitted"] == "too_large_for_mcp" and f"memory show {run_id}" in direction["note"]


def test_unstructured_payloads_are_dropped_whole_as_a_last_resort() -> None:
    """没有可裁的 `data`（或裁完仍超）时整份载荷换成占位，路径与 sha 这些摘要留着。"""
    big = {"artifacts": [{"kind": "dispatch_result", "path": "/a.json", "sha256": "s", "payload": {"text": "x" * 2_000_000}}], "run_id": "r1"}
    raw = {"ok": True, "result": big}

    fitted = mcp_runner._fit_result_budget(raw, lambda value: json.dumps(value))

    artifact = fitted["result"]["artifacts"][0]
    assert artifact["path"] == "/a.json" and artifact["sha256"] == "s"
    assert artifact["payload"]["omitted"] == "too_large_for_mcp" and "memory show r1" in artifact["payload"]["note"]
    assert any("已略去" in warning for warning in fitted["warnings"])


def test_what_the_ai_reads_survives_even_when_it_is_the_largest_part() -> None:
    """裁的次序按大小，但受保护的键不进候选：快照比原始明细大时，先走的仍是原始明细。"""
    readable = {"sections": "s" * 700_000}
    artifact = {"kind": "tool_result", "payload": {"data": {"export_snapshot": readable, "bazi": {"direction": "y" * 300_000}}}}

    fitted = mcp_runner._fit_result_budget({"ok": True, "result": {"run_id": "r1", "artifacts": [artifact]}}, lambda value: json.dumps(value))

    data = fitted["result"]["artifacts"][0]["payload"]["data"]
    assert data["export_snapshot"] == readable
    assert data["bazi"]["direction"]["omitted"] == "too_large_for_mcp"


def test_memory_fit_does_not_mutate_its_input() -> None:
    artifact = {"kind": "tool_result", "payload": {"data": {"snapshot_text": "s", "bazi": {"direction": "y" * 2_000_000, "small": 1}}}}
    raw = {"ok": True, "results": [{"run_id": "r1", "artifacts": [artifact]}]}
    before = json.dumps(raw)

    fitted = mcp_runner._fit_result_budget(raw, lambda value: json.dumps(value))

    assert json.dumps(raw) == before
    bazi = fitted["results"][0]["artifacts"][0]["payload"]["data"]["bazi"]
    assert bazi["small"] == 1 and bazi["direction"]["omitted"] == "too_large_for_mcp"


def test_a_small_memory_show_is_untouched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mcp, service = _server(tmp_path)
    run_id = _stored_bazi(service, raw_chars=1_000)
    full = {"run_id": run_id, "include_payload": True, "response_view": "full"}
    _, normal = _call(mcp, "horosa_memory_show", full)
    monkeypatch.setattr(mcp_runner, "MCP_RESULT_WIRE_BUDGET", 10**12)
    _, unlimited = _call(mcp, "horosa_memory_show", full)
    for body in (normal, unlimited):
        body.pop("trace_id")
        body.pop("group_id")
        body["result"].pop("usage_count")
        body["result"].pop("last_used_at")
    assert normal == unlimited
