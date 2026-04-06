from __future__ import annotations

import json

from horosa_skill.config import Settings
from horosa_skill.tracing import TraceRecorder


def test_trace_recorder_writes_redacted_jsonl(tmp_path) -> None:
    settings = Settings(
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        trace_dir=tmp_path / "traces",
        trace_capture_payloads=False,
        trace_capture_ai_answers=False,
    )
    tracer = TraceRecorder(settings)

    with tracer.span(
        workflow_name="tool.run",
        metadata={
            "payload": {"date": "2026-01-01"},
            "query_text": "问事业",
            "input_normalized": {"date": "2026-01-01"},
        },
    ) as trace:
        trace["run_id"] = "run-1"

    files = tracer.latest_trace_files(limit=1)
    assert files
    rows = [json.loads(line) for line in files[0].read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows[-1]["payload"] == "<redacted>"
    assert rows[-1]["query_text"] == "<redacted>"
    assert rows[-1]["input_normalized"] == "<redacted>"
