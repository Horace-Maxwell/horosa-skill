"""PDF 生僻字补字（v0.43.1，Windows 原生复验）：主字体缺字形的扩展 B 古籍字交给补字字体画，不再是方块。

本机实测（2026-10-23）：《灵棋经》《天机》条文里实有 13 个扩展 B 字，微软雅黑缺 12、正黑缺 13，SimSun-ExtB 一个不缺。
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from horosa_skill.reports import renderers

RARE = "𡛸𤣥𥦗"  # 均出自 vendor/lingqi/data/lingqiJing.js


def test_only_chars_the_primary_lacks_get_wrapped() -> None:
    primary = {ord(c) for c in "灵棋经卦"}
    fallback = {ord(c) for c in RARE + "灵"}
    markup = f'<b>灵棋</b>经：{RARE}卦<a href="#h0">{RARE[0]}</a> &amp; x'
    wrapped = renderers._wrap_missing_glyphs(markup, primary, fallback, "G")
    assert wrapped == (
        f'<b>灵棋</b>经：<font name="G">{RARE}</font>卦<a href="#h0"><font name="G">{RARE[0]}</font></a> &amp; x'
    )
    # 两边都没有的字原样留着（补不了就别动），主字体有的字永不被包
    assert renderers._wrap_missing_glyphs("㐀灵", primary, fallback, "G") == "㐀灵"


def test_no_fallback_font_means_byte_identical_markup(monkeypatch: pytest.MonkeyPatch) -> None:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.ttfonts import TTFont

    monkeypatch.setitem(renderers._PDF_GLYPH_FALLBACK_CANDIDATES, "sc", ("/nonexistent/font.ttf",))
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    patch = renderers._pdf_glyph_fallback(pdfmetrics, TTFont, "STSong-Light", "STSong-Light", renderers.SIMPLIFIED)
    assert patch(f"灵{RARE}") == f"灵{RARE}"


_HAVE_WINDOWS_FONTS = os.name == "nt" and Path("C:/Windows/Fonts/msyh.ttc").exists() and Path("C:/Windows/Fonts/simsunb.ttf").exists()


@pytest.mark.skipif(not _HAVE_WINDOWS_FONTS, reason="needs the Windows system fonts (Microsoft YaHei + SimSun-ExtB)")
def test_windows_pdf_embeds_the_extb_font_for_rare_chars(tmp_path: Path) -> None:
    document = {"title": f"灵棋经 {RARE}", "intro_text": f"象曰：{RARE}，吉。"}
    plain = {"title": "灵棋经", "intro_text": "象曰：吉。"}
    with_rare = renderers.render_report(document, output_path=tmp_path / "rare.pdf", format_name="pdf")
    without = renderers.render_report(plain, output_path=tmp_path / "plain.pdf", format_name="pdf")
    assert with_rare["format"] == "pdf" and without["format"] == "pdf"
    base_fonts = lambda p: set(re.findall(rb"/BaseFont\s*/[A-Z]{6}\+([A-Za-z0-9-]+)", Path(p).read_bytes()))  # noqa: E731
    assert b"SimSun-ExtB" in base_fonts(tmp_path / "rare.pdf"), base_fonts(tmp_path / "rare.pdf")
    assert b"SimSun-ExtB" not in base_fonts(tmp_path / "plain.pdf"), "没有生僻字时不嵌补字字体"
