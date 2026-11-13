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


@pytest.mark.skipif(not _HAVE_WINDOWS_FONTS, reason="[platform] needs the Windows system fonts (Microsoft YaHei + SimSun-ExtB)")
def test_windows_pdf_embeds_the_extb_font_for_rare_chars(tmp_path: Path) -> None:
    document = {"title": f"灵棋经 {RARE}", "intro_text": f"象曰：{RARE}，吉。"}
    plain = {"title": "灵棋经", "intro_text": "象曰：吉。"}
    with_rare = renderers.render_report(document, output_path=tmp_path / "rare.pdf", format_name="pdf")
    without = renderers.render_report(plain, output_path=tmp_path / "plain.pdf", format_name="pdf")
    assert with_rare["format"] == "pdf" and without["format"] == "pdf"
    base_fonts = lambda p: set(re.findall(rb"/BaseFont\s*/[A-Z]{6}\+([A-Za-z0-9-]+)", Path(p).read_bytes()))  # noqa: E731
    assert b"SimSun-ExtB" in base_fonts(tmp_path / "rare.pdf"), base_fonts(tmp_path / "rare.pdf")
    assert b"SimSun-ExtB" not in base_fonts(tmp_path / "plain.pdf"), "没有生僻字时不嵌补字字体"


# ---- v0.50.2-dev：基本平面以外的字（扩展 B、emoji）在 ToUnicode 里写成 UTF-16 代理对，复制 / 检索才拿得回原字 ----


def test_to_unicode_cmap_writes_astral_code_points_as_surrogate_pairs() -> None:
    from reportlab.pdfbase import ttfonts

    renderers._patch_to_unicode_cmap()
    renderers._patch_to_unicode_cmap()  # 幂等：不会层层包
    cmap = ttfonts.makeToUnicodeCMap("F", [0x41, 0x4E00, 0x216F8, 0x1F680])
    entries = re.findall(r"^<([0-9A-F]{2})> <([0-9A-F]+)>$", cmap.split("beginbfchar", 1)[1], re.M)
    assert entries == [("00", "0041"), ("01", "4E00"), ("02", "D845DEF8"), ("03", "D83DDE80")], cmap


def _cmap_entries(raw: bytes) -> list[tuple[str, str]]:
    import zlib

    entries: list[tuple[str, str]] = []
    for match in re.finditer(rb"/Length (\d+)[^>]*>>\s*stream\r?\n", raw):
        try:
            data = zlib.decompress(raw[match.end():match.end() + int(match.group(1))]).decode("latin-1")
        except zlib.error:
            continue
        if "beginbfchar" in data:
            entries += re.findall(r"<([0-9A-Fa-f]+)> <([0-9A-Fa-f]+)>", data.split("beginbfchar", 1)[1])
    return entries


@pytest.mark.skipif(not _HAVE_WINDOWS_FONTS, reason="[platform] needs the Windows system fonts (Microsoft YaHei + SimSun-ExtB)")
def test_windows_pdf_maps_rare_chars_and_emoji_back_to_unicode(tmp_path: Path) -> None:
    """Windows 上扩展 B 由 SimSun-ExtB、emoji 由 Segoe UI Symbol 画：此前它们的 ToUnicode 条目是 5 位十六进制（非法）。"""
    out = tmp_path / "astral.pdf"
    assert renderers.render_report({"title": f"灵棋经 {RARE}", "intro_text": f"象曰：{RARE}，吉。🚀💰"},
                                   output_path=out, format_name="pdf")["format"] == "pdf"
    entries = _cmap_entries(out.read_bytes())
    assert entries and all(len(dst) % 4 == 0 for _src, dst in entries), [e for e in entries if len(e[1]) % 4]
    mapped = {bytes.fromhex(dst).decode("utf-16-be") for _src, dst in entries}
    assert set(RARE) <= mapped and {"🚀", "💰"} <= mapped, sorted(c for c in mapped if ord(c[0]) > 0xFFFF)
