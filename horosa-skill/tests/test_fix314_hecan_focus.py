"""审计 surface 待决项 3：合参保持摘录，但按问题选段；evidence_sections 点名的段先放。"""
from __future__ import annotations

from horosa_skill.service import hecan_template as tpl


def _envelope(*sections: tuple[str, int]) -> dict:
    rows = [{"index": i + 1, "title": title, "body": "字" * size} for i, (title, size) in enumerate(sections)]
    return {"ok": True, "tool": "bazi_birth", "data": {"export_snapshot": {"sections": rows}}}


ENVELOPE = _envelope(("起盘信息", 200), ("四柱", 1500), ("十神", 1500), ("神煞", 1500), ("大运", 1200), ("流年", 800))


def test_timing_question_puts_the_luck_sections_first() -> None:
    """负向对照（实跑过）：_ordered 原样返回 → 「大运」「流年」被挤出节选 → 红。"""
    intent, focus = tpl.focus_for("我明年的运势怎么样")
    assert intent == "life_timing"
    excerpt = tpl.evidence(ENVELOPE, run_id="r1", focus=focus)
    assert excerpt["sections_shown"][:3] == ["起盘信息", "大运", "流年"]
    assert "read_rest" in excerpt and not excerpt["complete"]


def test_named_sections_come_first_and_unknown_questions_keep_the_order() -> None:
    excerpt = tpl.evidence(ENVELOPE, run_id="r1", requested=("神煞",))
    assert excerpt["sections_shown"][:2] == ["起盘信息", "神煞"]
    assert tpl.focus_for("帮我看看")[0] == ""
    plain = tpl.evidence(ENVELOPE, run_id="r1")
    assert plain["sections_shown"][:2] == ["起盘信息", "四柱"]


def test_a_section_too_big_is_skipped_not_the_end_of_the_excerpt() -> None:
    envelope = _envelope(("起盘信息", 200), ("长段", 5000), ("短段", 300))
    assert tpl.evidence(envelope, run_id="r1")["sections_shown"] == ["起盘信息", "短段"]
