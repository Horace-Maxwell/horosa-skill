"""ReportBuilder 八字默认解读：读不出四柱时不得凭全零计数下「木最旺、木最弱」的结论。"""
from __future__ import annotations

from horosa_skill.reports.builder import ReportBuilder

_PILLARS = "年柱：甲子\n月柱：丙寅\n日柱：戊辰\n时柱：庚申\n"


def _report(export_text: str) -> dict:
    return ReportBuilder()._default_bazi_report(
        question="事业发展如何",
        source={"technique": "bazi", "tool_name": "bazi_birth"},
        input_normalized={},
        export_sections=[],
        export_text=export_text,
    )


def _all_text(report: dict) -> str:
    return "\n".join(str(section.get("body") or "") for section in report["analysis_sections"])


def test_no_pillars_does_not_claim_wood_is_both_strongest_and_weakest() -> None:
    text = _all_text(_report(""))
    assert "木相对突出" not in text
    assert "五行强弱需要结合藏干、月令、大运流年继续细化。" in text
    assert "五行信息不足" in text


def test_pillars_still_produce_the_element_reading() -> None:
    text = _all_text(_report(_PILLARS))
    assert "明面干支计数" in text and "相对突出的元素是" in text
    assert "五行信息不足" not in text
