"""字体注册名跟着字体文件走，不跟着候选表序号走（v0.48.0 windows-smoke 两条红）。

reportlab 的 `registerFont` 对 TrueType 只认第一次：同名再注册被静默忽略，`getFont` 仍回旧字体。注册名此前是
`HorosaSC{序号}`，候选表一变就拿回别的文件。Windows 上序号 0 恰是系统真字体（雅黑），于是钉了 Vera 的缺字用例
拿回雅黑、画成了（「DID NOT RAISE」）；反过来 Vera 占着 `HorosaTC0`，繁体报告的用例拿到缺中文字形的字体。
macOS 上能载入的字体序号靠后，名字不撞，所以本机一直绿。这里用 reportlab 自带的两款 TTF 在任何平台复现。
"""

from __future__ import annotations

from pathlib import Path

import pytest
import reportlab
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont

from horosa_skill.reports import renderers
from horosa_skill.textscript import SIMPLIFIED

FONTS = Path(reportlab.__file__).parent / "fonts"


def _pin(monkeypatch: pytest.MonkeyPatch, regular: str, bold: str) -> None:
    pair = (str(FONTS / regular), None, str(FONTS / bold), None)
    monkeypatch.setattr(renderers, "_PDF_FONT_CANDIDATES", {"sc": [pair], "tc": [pair]})


def test_a_different_file_at_the_same_candidate_slot_is_not_shadowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """负向对照：注册名改回只看序号（f"{prefix}"）→ 第二次拿回第一次的 Vera，红（实跑过）。"""
    _pin(monkeypatch, "Vera.ttf", "VeraBd.ttf")
    first, _ = renderers._register_pdf_fonts(pdfmetrics, UnicodeCIDFont, TTFont, SIMPLIFIED)  # noqa: SLF001
    _pin(monkeypatch, "VeraIt.ttf", "VeraBI.ttf")
    second, _ = renderers._register_pdf_fonts(pdfmetrics, UnicodeCIDFont, TTFont, SIMPLIFIED)  # noqa: SLF001
    assert first != second
    assert Path(pdfmetrics.getFont(first).horosa_source[0]).name == "Vera.ttf"
    assert Path(pdfmetrics.getFont(second).horosa_source[0]).name == "VeraIt.ttf"


def test_the_same_file_keeps_one_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """同一文件反复注册拿到同一个名字（长命 MCP server 不会把字体表越注册越多）。"""
    _pin(monkeypatch, "Vera.ttf", "VeraBd.ttf")
    a = renderers._register_pdf_fonts(pdfmetrics, UnicodeCIDFont, TTFont, SIMPLIFIED)  # noqa: SLF001
    b = renderers._register_pdf_fonts(pdfmetrics, UnicodeCIDFont, TTFont, SIMPLIFIED)  # noqa: SLF001
    assert a == b
