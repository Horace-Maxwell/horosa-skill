"""PDF 里画不出的字要说出来（审计 O-17：太玄「𥘩」、解读里的「𠮷 𬺰」在 PDF 里是空白 / 方块，结果没有 warnings）。

macOS 补字链加了华文黑体 / 冬青黑体（收部分扩展 B）；哪款都画不出的字进结果 warnings，列出是哪些字。
负向对照（实跑过）：_GlyphPatcher 不记 missing → 第一条红。
"""
from __future__ import annotations

from pathlib import Path

import pytest
from conftest import simulate_fonts
from test_user_knowledge_and_chart_report import _chart_run, _service

from horosa_skill.reports.renderers import _PDF_GLYPH_FALLBACK_CANDIDATES, _wrap_missing_glyphs_chain

NOBODY = "\U0002B820"   # 扩展 E；不在罕见字回退表里（Windows 11 的 SimSun-ExtG 收它，所以第一条用例模拟无字体）


def test_an_undrawable_character_is_named_in_the_warnings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # 「画不出」按模拟的无字体现场定（conftest.simulate_fonts）：Windows 11 的 SimSun-ExtG 真收扩展 E，
    # 按本机字体判时 windows-smoke 在这里红过（v0.51 PR #23）。补字链本身由下一条用例守。
    simulate_fonts(monkeypatch, "no_fonts")
    service = _service(tmp_path)
    run_id = _chart_run(service).memory_ref.run_id
    out = service.report_render({"run_id": run_id, "tool_name": "chart", "format": "pdf",
                                 "ai_report": {"direct_answer": f"结论：{NOBODY}字待考。", "executive_summary": "摘要。"}})
    notes = " ".join([*out.get("warnings", []), *out.get("summary", [])])
    assert NOBODY in notes and "画得出" in notes, notes


def test_the_chain_records_only_what_no_font_can_draw() -> None:
    missing: set[str] = set()
    out = _wrap_missing_glyphs_chain(f"甲{NOBODY}乙 ", frozenset(map(ord, "甲乙 ")), [("F", frozenset())], missing)
    assert missing == {NOBODY} and out == f"甲{NOBODY}乙 "


@pytest.mark.parametrize("kind", ["sc", "tc"])
def test_macos_ext_b_fonts_are_in_the_chain(kind: str) -> None:
    assert "/System/Library/Fonts/STHeiti Light.ttc" in _PDF_GLYPH_FALLBACK_CANDIDATES[kind]
