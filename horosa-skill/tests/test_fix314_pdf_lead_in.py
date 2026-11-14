"""PDF：以「：」结尾的引导句与下面的表排在同一页（审计 O-19：「多派用神对照：」在第 5 页底、表在第 6 页）。

排版后的 story 里，引导句要么和表包在同一个 KeepTogether 里，要么前面紧挨一个 CondPageBreak（表很长时只要求下面还有 40 mm）。
负向对照（实跑过）：bind_lead_in 直接 return → 红。
"""
from __future__ import annotations

from pathlib import Path

from reportlab.platypus import CondPageBreak, KeepTogether
from test_user_knowledge_and_chart_report import _chart_run, _PdfSpy, _service

LEAD = "多派用神对照："
TABLE = "\n".join(["| 派别 | 用神 |", "| --- | --- |", *(f"| 派{n} | 木 |" for n in range(6))])


def _flat(flowable):
    yield flowable
    for child in getattr(flowable, "_content", None) or []:
        yield from _flat(child)


def test_the_lead_in_stays_with_its_table(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path)
    run_id = _chart_run(service).memory_ref.run_id
    spy = _PdfSpy(monkeypatch)
    service.report_render({"run_id": run_id, "tool_name": "chart", "format": "pdf", "ai_report": {
        "direct_answer": "结论。", "executive_summary": "摘要。",
        "analysis_sections": [{"title": "用神", "body": f"{LEAD}\n\n{TABLE}"}]}})
    story = spy.story
    hits = [n for n, item in enumerate(story) for part in _flat(item) if str(getattr(part, "text", "")).endswith(LEAD)]
    assert hits, "引导句没进 story"
    n = hits[0]
    item = story[n].__dict__.get("inner", story[n])      # 版式块外面套着 Guarded
    parts = list(_flat(item))
    lead = next(i for i, part in enumerate(parts) if str(getattr(part, "text", "")).endswith(LEAD))
    # 表必须在引导句**之后**、同一组里（同组里引导句前面的那张版式表是小标题块，不算）
    grouped = isinstance(item, KeepTogether) and any(type(part).__name__.endswith(("Table", "Panels")) for part in parts[lead + 1:])
    assert grouped or isinstance(story[n - 1], CondPageBreak), (type(story[n - 1]).__name__, type(story[n]).__name__)
