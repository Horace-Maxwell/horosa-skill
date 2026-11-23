"""上游 v3.14.0 同步 · 罕见字在报告里的写法（reports/rare_chars.py）。

上游：「灵棋经、太玄、六爻占类歌赋与天文馆星官名里，系统字库没有的字不再显示成方框（界面与导出 PDF 同一张表）」——
`utils/rareChars.js` 的 `RARE_CHARS` + `utils/aiExportPdfVector.js` 的 `pdfSafeText`。skill 的报告此前只有补字字体链
（Windows 的 SimSun-ExtB）；macOS / Linux 的缺省字体一个扩展 B 的字都没有，灵棋经四库本的异体字、太玄的古字在 PDF 里是方块。

规则（照 pdfSafeText 的罕见字分支）：字体画得出 → 原字；画不出且登记过 → 通行写法（整串画得出才用）→〔拆字说明〕（整串画得出才用）
→ 原样；没登记的字永远原样。表由 app-charts 的构建从 pin 住的上游写出（不手抄），清单记哈希。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from horosa_skill.reports import app_charts, rare_chars, renderers

PKG_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((PKG_ROOT / "contracts" / "app_charts_bundle.json").read_text(encoding="utf-8"))


def _codes(text: str) -> set[int]:
    return {ord(ch) for ch in text}


def test_table_is_the_one_the_build_wrote_from_the_pinned_upstream() -> None:
    """data/rare_chars.json = build.mjs 从 app 自己的 RARE_CHARS 写出的那一份（清单记 sha；`build.mjs --check` 对上游）。
    负向对照：手改数据文件里任何一个字 → sha 对不上 → 红。"""
    body = rare_chars.DATA.read_bytes()
    assert hashlib.sha256(body).hexdigest() == MANIFEST["rare_chars"]["sha256"]
    table = rare_chars.table()
    assert len(table) == MANIFEST["rare_chars"]["count"] == 34, "太玄 19 + 灵棋 13 + 类推简化 2（上游 v3.14.0）"
    assert all(rare_chars.is_rare(ord(ch)) and len(ch) == 1 for ch in table), "only CJK Ext-B+ characters are registered"
    assert all(set(entry) <= {"same", "parts"} and entry for entry in table.values())
    # 上游表里的三种形状各取一条（utils/rareChars.js）：只有通行写法 / 只有拆字 / 两样都有
    assert table["𠉀"] == {"same": "候"} and table["𠹑"] == {"parts": "左口右臬"} and table["𥧲"] == {"same": "浸", "parts": "上穴下㴆"}


def test_fallback_follows_the_upstream_pdf_rule() -> None:
    """pdfSafeText：通行写法画得出就用它；画不出再看〔拆字〕；都画不出、或没登记 → 不换。"""
    everything = lambda code: True  # noqa: E731
    nothing = lambda code: False  # noqa: E731
    assert rare_chars.fallback("𠉀", everything) == "候"
    assert rare_chars.fallback("𠹑", everything) == "〔左口右臬〕"
    assert rare_chars.fallback("𥧲", everything) == "浸", "通行写法优先于拆字"
    without_common = _codes("〔上穴下㴆〕")
    assert rare_chars.fallback("𥧲", lambda code: code in without_common) == "〔上穴下㴆〕", "通行写法画不出 → 拆字说明"
    assert rare_chars.fallback("𥧲", lambda code: code in _codes("〔上穴下〕")) is None, "拆字里有画不出的部件（㴆）→ 不换"
    assert rare_chars.fallback("𠉀", nothing) is None and rare_chars.fallback("𠀀", everything) is None
    # 整串：画得出的罕见字、没登记的罕见字、普通字都原样；不含罕见字时原对象返回
    drawable = _codes("天候不常玄") | {ord("𤣥")}
    assert rare_chars.safe_text("天𠉀不常𤣥𠀀", lambda code: code in drawable) == "天候不常𤣥𠀀"
    plain = "天候不常"
    assert rare_chars.safe_text(plain, nothing) is plain


def test_pdf_text_swaps_a_registered_rare_char_only_when_no_font_draws_it() -> None:
    """`_wrap_missing_glyphs_chain`（PDF 正文补字）：补字链里有字形（Windows 的 SimSun-ExtB）→ 照旧包进补字字体、原字不动；
    哪款字体都没有 → 换成通行写法 / 拆字说明，换上去的字自己缺主字体字形时照样走补字链；标签里的字不动。
    负向对照：去掉该函数里的罕见字分支 → 第二、三、四条断言红（原样输出，即方块）。"""
    primary = _codes("天不常灵棋经〔〕左口右臬")
    with_extb = [("ExtB", _codes("𠉀𠹑"))]
    assert renderers._wrap_missing_glyphs_chain("天𠉀不常", primary, with_extb) == '天<font name="ExtB">𠉀</font>不常'
    no_extb = [("Sym", _codes("候"))]
    assert renderers._wrap_missing_glyphs_chain("天𠉀不常", primary, no_extb) == '天<font name="Sym">候</font>不常'
    assert renderers._wrap_missing_glyphs_chain("<b>𠹑</b>经", primary, []) == "<b>〔左口右臬〕</b>经"
    assert renderers._wrap_missing_glyphs_chain("天𠉀不常", primary | _codes("候"), []) == "天候不常"
    assert renderers._wrap_missing_glyphs_chain('<a href="#𠉀">𠀀</a>', primary | _codes("候"), []) == '<a href="#𠉀">𠀀</a>', "tags and unregistered characters stay"
    assert renderers._wrap_missing_glyphs_chain("天𠉀不常", primary, []) == "天𠉀不常", "通行写法也画不出 → 原样（不造别的字）"


def test_figure_strings_get_the_same_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """app 盘图里的字（灵棋盘的卦名 / 断语行）：换回报告字体时，哪款字体都画不出的登记字同样换成通行写法——否则 PDF 里是方块、
    PNG 整张拒绝出图（report.png_font_unavailable）。字体覆盖用替身，不依赖本机装了什么。
    负向对照：去掉 `_swap_text_fonts` 里那三行 → 文字仍是「𠉀」→ 红。"""
    from reportlab.graphics.shapes import Group, String

    coverage = {"Regular": frozenset(_codes("天候不常卦")), "Bold": frozenset(_codes("天候不常卦"))}
    monkeypatch.setattr(app_charts, "_charset", lambda name: coverage[name])
    monkeypatch.setattr(app_charts, "_symbol_chain", lambda: [("ExtB", "/x.ttf", 0, frozenset(_codes("𤣥")))])
    group = Group(String(0, 0, "天𠉀不常", fontName="Courier"), String(0, 0, "𤣥", fontName="Courier-Bold"), String(0, 0, "𠀀卦", fontName="Courier"))
    app_charts._swap_text_fonts(group, "Regular", "Bold")
    first, second, third = group.contents
    assert (first.text, first.fontName) == ("天候不常", "Regular")
    assert (second.text, second.fontName) == ("𤣥", "ExtB"), "a chain font that has the glyph keeps the original character"
    assert third.text == "𠀀卦", "unregistered: left as is"


def test_a_missing_or_broken_table_never_blocks_a_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    broken = tmp_path / "rare_chars.json"
    broken.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(rare_chars, "DATA", broken)
    rare_chars.cache_clear()
    try:
        assert rare_chars.table() == {} and rare_chars.safe_text("天𠉀", lambda code: False) == "天𠉀"
        assert rare_chars.glyph_fallback() == {} and rare_chars.pdf_fallback("龢", lambda code: True) is None
    finally:
        monkeypatch.undo()
        rare_chars.cache_clear()
