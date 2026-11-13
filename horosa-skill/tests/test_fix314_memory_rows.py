"""horosa_memory_query 的列表行是摘要，不是整条记录（审计 O-01，P0）。

修前：每行 2–8 KB（tool_calls[].input 全量、artifacts 带 sha256、artifact_summary 再列一遍、解读全文），阅读视图按整块裁——
limit ≥ 25 或带解读的记录用缺省 limit 时 `results` 整个换成占位，「查某人的历史」拿不到任何 run_id；结果里也没有总数 / 续读位置。

负向对照（实跑过）：query_memory 里 `compact_row` 那一行改回原样 → 体积用例与 MCP 用例红。
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService


def _service(tmp_path: Path) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", db_path=tmp_path / "m.db",
                        output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt", data_dir=tmp_path / "d")
    return HorosaSkillService(settings, store=MemoryStore(settings))


def _seed(service: HorosaSkillService, n: int, *, answer_chars: int = 0) -> list[str]:
    ids = []
    for i in range(n):
        env = {"ok": True, "tool": "bazi_birth", "summary": ["s"], "data": {"export_snapshot": {"export_text": "x" * 4000, "sections": []}}}
        rid = service.store.create_run(entrypoint="tool", query_text=f"第{i}问：事业怎么样" + "详" * 200, group_id="g",
                                       subject={"name": "张三", "date": "1990-05-03", "time": "08:00", "gender": 0})
        service.store.record_tool_result(run_id=rid, tool_name="bazi_birth", ok=True,
                                         input_normalized={"date": "1990-05-03", "time": "08:00:00", "zone": "+08:00", "notes": "长" * 2000},
                                         envelope_dict=env, summary=["已生成八字"], warnings=[], error=None, trace_id="t", group_id="g")
        if answer_chars:
            service.store.record_answer(run_id=rid, ai_answer_text="解" * answer_chars) if hasattr(service.store, "record_answer") else None
        ids.append(rid)
    return ids


def test_rows_are_summaries_and_paging_is_reported(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _seed(service, 30)
    result = service.query_memory({"limit": 20})
    rows = result["results"]
    assert len(rows) == 20 and result["has_more"] is True and result["next_offset"] == 20
    biggest = max(len(json.dumps(row, ensure_ascii=False)) for row in rows)
    assert biggest < 900, biggest
    row = rows[0]
    assert row["tools"] == ["bazi_birth"] and row["subject"]["name"] == "张三"
    assert len(row["question"]) <= 81 and row["question"].endswith("…")
    assert all(a["path"] for a in row["artifacts"]) and not any("sha256" in a for a in row["artifacts"])
    assert "tool_calls" not in row or all(set(c) <= {"tool_name", "ok"} for c in row["tool_calls"])
    last = service.query_memory({"limit": 20, "offset": 20})
    assert len(last["results"]) == 10 and last["has_more"] is False and "next_offset" not in last


def test_full_rows_are_still_there_on_request(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _seed(service, 2)
    full = service.query_memory({"limit": 5, "include_payload": True})
    assert "tool_calls" in full["results"][0] and "input" in full["results"][0]["tool_calls"][0]


def test_mcp_reading_view_returns_rows_for_a_hundred_runs(tmp_path: Path) -> None:
    from mcp.client import Client

    from horosa_skill.surfaces.mcp_server import create_mcp_server

    service = _service(tmp_path)
    _seed(service, 100)
    mcp = create_mcp_server(service, service.settings)

    async def run():
        async with Client(mcp) as client:
            result = await client.call_tool("horosa_memory_query", {"limit": 100})
            return json.loads(result.content[0].text)

    body = asyncio.run(run())
    rows = body["results"]
    assert isinstance(rows, list) and len(rows) >= 40, str(rows)[:200]   # 按行截，不再整块换成占位
    if len(rows) < 100:
        assert body["has_more"] is True and body["next_offset"] == len(rows)
        assert any(f"offset={len(rows)}" in w for w in body["warnings"])
