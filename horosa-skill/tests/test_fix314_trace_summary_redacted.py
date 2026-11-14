"""trace 的 summary 在没开载荷捕获时不落原文（审计 O-06 的隐私部分）。

修前：trace 行里 payload / input_normalized 是 <redacted>，summary 却是原文——
「已生成塔罗…(种子:张三丰ZSFUNIQ|2026-11-13|10:00:00|31n13|121e28)」「日期：1990-05-17 14:30:00；时区：+09:00」；trace 缺省开启。
删除时连带清报告 / trace 改了删除语义（有用例守「报告只列不删」），留给维护者定，不在本修。
负向对照（实跑过）：去掉 summary 分支 → 第一个用例红。
"""
from __future__ import annotations

import json

from horosa_skill.config import Settings
from horosa_skill.tracing import TraceRecorder


def _rows(tmp_path, capture: bool) -> list[dict]:
    settings = Settings(db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs", trace_dir=tmp_path / "traces",
                        trace_capture_payloads=capture, trace_capture_ai_answers=False)
    tracer = TraceRecorder(settings)
    with tracer.span(workflow_name="tool.run", metadata={"payload": {}}) as trace:
        trace["summary"] = ["已生成塔罗（种子:张三丰ZSFUNIQ|2026-11-13|10:00:00|31n13|121e28）", "日期：1990-05-17 14:30:00"]
    files = tracer.latest_trace_files(limit=1)
    return [json.loads(line) for line in files[0].read_text(encoding="utf-8").splitlines() if line.strip()]


def test_summary_is_redacted_without_payload_capture(tmp_path) -> None:
    rows = _rows(tmp_path, capture=False)
    assert rows[-1]["summary"] == "<redacted: 2 line(s)>"
    assert "ZSFUNIQ" not in json.dumps(rows, ensure_ascii=False)


def test_summary_is_kept_when_the_user_opted_into_payload_capture(tmp_path) -> None:
    rows = _rows(tmp_path, capture=True)
    assert "ZSFUNIQ" in rows[-1]["summary"][0]
