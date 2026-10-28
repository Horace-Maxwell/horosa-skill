"""报告骨架（v0.45.0，所有技法共用）：盘面段号 E1…、AI 引用 [E3] 可跳转、数据在前、AI 层单独标注、封面列关键设置。

依据见 docs/LESSONS.md v0.45.0-dev（STORM 的行内引用与 lead、kerykeion「数据层不做解读」、Anthropic citations 的
content_block 定位、Word 无障碍：替代文字）。
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

from test_user_knowledge_and_chart_report import _chart_run, _flat, _PdfSpy, _service

from horosa_skill.reports.builder import ReportBuilder
from horosa_skill.service._common import _missing_detail_text


def _produced_cites(run) -> list[tuple[str, str]]:
    sections = run.data["export_snapshot"]["sections"]
    return [(f"E{i}", s["title"]) for i, s in enumerate(sections, start=1)
            if str(s.get("body") or "").strip() not in ("", _missing_detail_text(s["title"]))]


def _ai_report(first: str, second: str) -> dict:
    return {
        "direct_answer": f"整体平稳 [{first}]。",
        "executive_summary": f"命主格局清楚 [{first}]，运势起伏在 [{second}]。",
        "analysis_sections": [{"title": "分节细读", "body": f"细读一段 [{second}]，不存在的段 [E999] 不链接。"}],
        "recommendations": ["按部就班"],
        "limitations": ["出生时间若差半小时，宫位可能换"],
    }


def test_template_hands_the_ai_the_same_section_numbers_the_report_prints(tmp_path: Path) -> None:
    service = _service(tmp_path)
    run = _chart_run(service)
    template = service.report_template({"run_id": run.memory_ref.run_id, "tool_name": "chart"})
    cites = [s["cite_id"] for s in template["source_export_sections"]]
    assert cites == [f"E{i}" for i in range(1, len(cites) + 1)]
    assert [s["cite_id"] for s in template["ai_fillable"]["analysis_sections"]] == cites
    assert any("[E3]" in line for line in template["ai_instructions"])


def test_analysis_pdf_is_data_first_with_clickable_section_citations(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path)
    run = _chart_run(service)
    (first, first_title), (second, _) = _produced_cites(run)[:2]
    spy = _PdfSpy(monkeypatch)
    service.report_render({"run_id": run.memory_ref.run_id, "tool_name": "chart", "format": "pdf",
                           "ai_report": _ai_report(first, second)})
    texts = spy.texts()
    # 目录里也有这些字：从「核心结论」卡（只在正文里）起逐个往后找，顺序必须是 结论摘要 → 盘面 → AI 分节解读 → 附录。
    position = texts.index("核心结论")
    for label in ("完整盘面", "AI 解读", "附录"):
        position = texts.index(label, position + 1)
    assert f"{first} · {first_title}" in texts and "不确定处与限制" in texts
    raw = [item.text for flowable in spy.story for item in _flat(flowable) if isinstance(getattr(item, "text", None), str)]
    assert any(f'<a name="{first}"/>' in text for text in raw)  # 盘面段标题是跳转目标
    assert any(f'<a href="#{first}"' in text for text in raw)  # 摘要里的 [E1] 链过去
    assert not any('href="#E999"' in text for text in raw) and any("[E999]" in text for text in raw)
    note = next(t for t in texts if t.startswith("以下是 AI 依据上方盘面"))
    assert "不是排盘引擎的输出" in note


def test_the_cover_lists_the_result_changing_settings() -> None:
    card = {"settings": {"timeAlg": {"label": "时间算法", "value": "0"}, "hsys": {"label": "分宫制", "value": 1},
                         "after23NewDay": {"label": "晚子时·日柱开关", "value": 1}}}
    section = ReportBuilder()._chart_basis_section({"date": "1990-01-01"}, {"technique_label": "八字"}, card=card)
    assert section["items"]["关键设置"] == "时间算法：真太阳时；晚子时·日柱开关：是"  # 分宫制这类码值不印（见 _setting_text）
    assert "关键设置" not in ReportBuilder()._chart_basis_section({}, {}, card={})["items"]


def test_docx_numbers_sections_puts_ai_after_the_chart_and_gives_figures_alt_text(tmp_path: Path) -> None:
    service = _service(tmp_path)
    run = _chart_run(service)
    (first, first_title), (second, _) = _produced_cites(run)[:2]
    rendered = service.report_render({"run_id": run.memory_ref.run_id, "tool_name": "chart", "format": "docx",
                                      "ai_report": _ai_report(first, second)})
    xml = zipfile.ZipFile(rendered["artifact_path"]).read("word/document.xml").decode("utf-8")
    text = re.sub(r"<[^>]+>", "", xml)
    assert f"{first} · {first_title}" in text
    assert text.index("核心结论") < text.index("完整盘面") < text.index("AI 解读") < text.index("附录")
    pictures = re.findall(r'<wp:docPr [^>]*>', xml)
    if pictures:  # 本机没有可用于画位图的字体时 DOCX 只放文字说明（见 _drawing_font_files）
        assert all(re.search(r'descr="[^"]+"', tag) for tag in pictures)
