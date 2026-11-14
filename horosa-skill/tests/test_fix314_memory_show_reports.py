"""出过 PDF / DOCX / PNG 报告的记录，horosa_memory_show 不能判成「不完整、要重新起盘」（审计 S-02）。

根因：存档读回时对每个产物都 `json.loads(path.read_text("utf-8"))`，二进制报告必然 UnicodeDecodeError → payload_error → 「缺失或读不了」。
修：只有 JSON 产物读 payload；报告类产物存在即完整。负向对照（实跑过）：把 `_artifact_record_to_dict` 的后缀判断去掉 → 本用例红。
"""
from __future__ import annotations

from pathlib import Path

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService


def test_binary_report_artifacts_do_not_make_a_record_incomplete(tmp_path: Path) -> None:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", db_path=tmp_path / "m.db",
                        output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt", data_dir=tmp_path / "d")
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    env = {"ok": True, "tool": "bazi_birth", "summary": ["s"], "data": {"export_snapshot": {"export_text": "x", "sections": []}}}
    run_id = service.store.create_run(entrypoint="tool", query_text="问", group_id="g")
    service.store.record_tool_result(run_id=run_id, tool_name="bazi_birth", ok=True, input_normalized={}, envelope_dict=env,
                                     summary=["s"], warnings=[], error=None, trace_id="t", group_id="g")
    for fmt, data in (("pdf", b"%PDF-1.7\n\x89\xff\x00binary"), ("png", b"\x89PNG\r\n\x1a\n\x00\x00"), ("docx", b"PK\x03\x04\x89\x00")):
        path = tmp_path / f"report.{fmt}"
        path.write_bytes(data)
        service.store.record_report_artifact(run_id=run_id, tool_name="bazi_birth", format_name=fmt, path=path)
    shown = service.show_memory({"run_id": run_id})
    assert shown.get("complete") is not False, shown.get("summary")
    assert not shown.get("missing_artifacts")
