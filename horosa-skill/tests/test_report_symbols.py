"""PDF 里的 emoji 与符号（v0.50.0，评审 R-02）。

旧规则只把 U+1F300–1FAFF 一段换成 ▸：✅ ❌ ⚠️ ⭐ 1️⃣ 不在这一段，在 PDF 里是方块；🔴 / 🟢、👍 / 👎 全成 ▸，意思反了也看不出；
DOCX 也把 emoji 换掉了（Word 本来画得出）。旧断言只测了 📍 一个字，正好落在那一段里，所以一直是绿的。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from test_user_knowledge_and_chart_report import _chart_run, _flat, _PdfSpy, _service

from horosa_skill.reports import renderers

EMOJI = "✅ 对 ❌ 错 ⚠️ 注意 ⭐ 重点 1️⃣ 第一 🔴 凶 🟢 吉 👍 好 👎 差 👨‍👩‍👧 家 🎉 喜 ☯ 太极 𡛸"


def test_meanings_map_to_distinct_drawable_symbols() -> None:
    sym = renderers._pdf_symbols
    assert re.sub("<[^>]+>", "", sym("✅❌⭐⚠️1️⃣🔟")) == "✓✗★⚠①⑩"
    assert sym("🔴") != sym("🟢") and "●" in sym("🔴") and "●" in sym("🟢")
    assert sym("👍") != sym("👎")
    assert "‍" not in sym("👨‍👩‍👧") and "️" not in sym("⚠️")
    # 标签里的字不动；纯 ASCII 原样返回
    assert sym('<a href="#E1">✅</a>') == '<a href="#E1"><font color="#2f855a">✓</font></a>'
    assert sym("plain <b>x</b>") == "plain <b>x</b>"


def test_the_guard_measures_the_real_cmap_and_never_replaces_text() -> None:
    primary = {ord(c) for c in "x灵"}
    chain = [("S", {ord("▸"), ord("✓")})]
    wrap = renderers._wrap_missing_glyphs_chain
    assert wrap("🎉x灵", primary, chain) == '<font name="S">▸</font>x灵'  # 画不了的符号 → ▸（由补字字体画）
    assert wrap("✓x", primary, chain) == '<font name="S">✓</font>x'  # 画得了的符号照常补字
    assert wrap("㐀灵", primary, chain) == "㐀灵"  # 文字补不了就原样留（v0.43 起的规矩）
    assert wrap('<a href="#🎉">x</a>', primary, chain) == '<a href="#🎉">x</a>'  # 标签内不动


def _drawn_chars(markup: str, primary: str) -> list[tuple[str, str]]:
    """标记里每个要画的非 ASCII 字 + 画它的字体名（<font name> 嵌套时取最内层）。"""
    import html

    out: list[tuple[str, str]] = []
    stack = [primary]
    for token in re.split(r"(<[^>]+>)", markup):
        if token.startswith("</font"):
            stack.pop()
        elif token.startswith("<font"):
            name = re.search(r'name="([^"]+)"', token)
            stack.append(name.group(1) if name else stack[-1])
        elif not token.startswith("<"):
            out += [(ch, stack[-1]) for ch in html.unescape(token) if ord(ch) >= 0x80 and not ch.isspace()]
    return out


def test_no_symbol_reaches_the_pdf_that_its_font_cannot_draw(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from reportlab.pdfbase import pdfmetrics

    service = _service(tmp_path)
    run_id = _chart_run(service).memory_ref.run_id
    spy = _PdfSpy(monkeypatch)
    service.report_render({"run_id": run_id, "format": "pdf", "ai_answer_text": f"## 结论\n\n{EMOJI}\n\n- {EMOJI}"})
    paragraphs = [item for flowable in spy.story for item in _flat(flowable) if isinstance(getattr(item, "text", None), str)]
    target = [p for p in paragraphs if "太极" in p.text]
    assert target, "解读段落进了 PDF"
    primary_name = target[0].style.fontName
    face = getattr(pdfmetrics.getFont(primary_name), "face", None)
    if face is None:
        pytest.skip("[host] 本机没有中文 TrueType，PDF 用不嵌入的 CID 字体：量不了 cmap（R-16 另有说明）")
    for paragraph in target:
        for ch, font in _drawn_chars(paragraph.text, primary_name):
            covered = pdfmetrics.getFont(font).face.charToGlyph
            if ord(ch) in covered:
                continue
            assert not renderers._is_symbol(ch), f"{ch!r} U+{ord(ch):04X} 在 {font} 里画不出来"
    text = "\n".join(p.text for p in target)
    assert "️" not in text and "‍" not in text and "🎉" not in text


def test_docx_keeps_real_emoji(tmp_path: Path) -> None:
    from docx import Document

    service = _service(tmp_path)
    run_id = _chart_run(service).memory_ref.run_id
    rendered = service.report_render({"run_id": run_id, "format": "docx", "ai_answer_text": f"## 结论\n\n{EMOJI}"})
    text = "\n".join(p.text for p in Document(rendered["artifact_path"]).paragraphs)
    for emoji in ("✅", "❌", "⚠️", "⭐", "🔴", "🟢", "👍"):
        assert emoji in text, emoji
