"""上游 v3.15.0 同步 · PDF 缺字链（reports/rare_chars.py `pdf_fallback`，照 utils/aiExportPdfVector.js `pdfSafeText`）。

上游的 PDF 只嵌一款中文子集字体，字体没有的字此前画成空白 / 方块（度数「˚」、分数斜杠「⁄」、希腊字母、转写附加符号、繁体异体字）。
v3.15.0 起按固定顺序换成字体里有的写法。skill 的 PDF 先在补字字体链里找画得出的字体，整条链都画不了才走这条换字链。

钉三件事：
① 表 = build.mjs 从 pin 写进 rare_chars.json 的那几张（独立读上游文件对拍）；
② 上游自己的测试用例（`utils/__tests__/aiExportPdfGlyphFallback.test.js`），用上游同一款字体的字符集当「画得出」，逐条同值；
③ 接进 PDF 渲染：字体链画得出的字不换，整条链都画不了才换。
负向对照：renderers 只对罕见字换（v3.14 写法）→ ③ 红；去掉 pdf_fallback 的通行写法一步 → ② 的「尅」用例红。
"""
from __future__ import annotations

import json

import pytest
from skips import needs_upstream, upstream_path

from horosa_skill.reports import rare_chars

UI = "Horosa-Web/astrostudyui"
FONT = f"{UI}/public/fonts/HorosaCJK-subset.ttf"
BOLD = f"{UI}/public/fonts/HorosaCJK-Bold-subset.ttf"


def _charset(relative: str) -> frozenset[int]:
    from reportlab.pdfbase.ttfonts import TTFontFile

    return frozenset(TTFontFile(str(upstream_path(relative))).charToGlyph)


def _pdf_safe_text(text: str, charset: frozenset[int]) -> str:
    """上游 pdfSafeText 的外壳（控制字符与字体里有的字原样，其余走换字链，换不了落 □）——链本身是被测的 skill 代码。"""
    def drawable(code: int) -> bool:
        return code < 0x20 or code in charset

    out = []
    for ch in text:
        if drawable(ord(ch)):
            out.append(ch)
            continue
        replacement = rare_chars.pdf_fallback(ch, drawable)
        out.append(replacement if replacement is not None else ("□" if 0x25A1 in charset else "?"))
    return "".join(out)


@needs_upstream(f"{UI}/src/data/pdfGlyphFallback.json", f"{UI}/src/utils/aiExportPdfVector.js")
def test_tables_are_the_pinned_upstream_ones() -> None:
    upstream = json.loads(upstream_path(f"{UI}/src/data/pdfGlyphFallback.json").read_text(encoding="utf-8"))
    assert rare_chars.glyph_fallback() == upstream and len(upstream) > 1000
    src = upstream_path(f"{UI}/src/utils/aiExportPdfVector.js").read_text(encoding="utf-8")
    literal = src[src.index("const PDF_CHAR_FALLBACK = {"): src.index("};", src.index("const PDF_CHAR_FALLBACK = {"))]
    # 逐条在上游字面量里找得到（引号形式两种：'x': 'y' / 'x': "'"），且条数相同（每条恰有一个「': 」）
    for key, value in rare_chars.char_fallback().items():
        assert f"'{key}': '{value}'" in literal or f"'{key}': \"{value}\"" in literal, (key, value)
    assert len(rare_chars.char_fallback()) == literal.count("': ") > 30
    assert rare_chars.greek_name("α") == "alpha" and rare_chars.greek_name("Δ") == "Delta" and rare_chars.greek_name("ς") == "sigma"


@needs_upstream(FONT, BOLD)
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("26.4872˚(J2000.0 时 26˚37分18秒)", "26.4872°(J2000.0 时 26°37分18秒)"),
        ("14 谐(360˚⁄14 倍数)", "14 谐(360°/14 倍数)"),
        ("木星 金牛 ☉ 12°", "木星 金牛 ☉ 12°"),
        ("一\n二\t三", "一\n二\t三"),
        ("流派：Parāśarī", "流派：Parasari"),
        ("牡鹿四星(α Cas)", "牡鹿四星(alpha Cas)"),
        ("闭式(ε≈23.44˚)", "闭式(epsilon≈23.44°)"),
        ("木·拱(Δ12)", "木·拱(Delta12)"),
        ("GU₄.AN.NA", "GU4.AN.NA"),
        ("Duʾūzu", "Du'uzu"),
        ("日11宫✓", "日11宫√"),
        ("Utu/Šamaš LÚ.ḪUN.GÁ", "Utu/Samas LÚ.HUN.GÁ"),
        ("H̱olon", "Holon"),
        ("甲​乙‍丙﻿丁", "甲乙丙丁"),
        ("‪右‬", "右"),
        ("主尅客,主勝", "主克客,主勝"),
        ("隂盛尅陽", "阴盛克陽"),
        ("齡 週 兇", "龄 周 凶"),
        ("✗ 宜:日月吉相", "× 宜:日月吉相"),
        ("日⟷上升", "日↔上升"),
        ("金⥮火", "金⇅火"),
        ("克 阴 照", "克 阴 照"),
    ],
)
def test_upstream_cases_with_the_upstream_font(text: str, expected: str) -> None:
    assert _pdf_safe_text(text, _charset(FONT)) == expected


@needs_upstream(FONT, BOLD)
def test_every_output_is_drawable_in_both_upstream_weights() -> None:
    sample = "˚⁄∕‐‑‒–′″‘’“”…•∙⋅ﬁ①Ⅻ㎡é ñ Ǖ ☽♈𝔄🜨"
    for relative in (FONT, BOLD):
        charset = _charset(relative)
        out = _pdf_safe_text(sample, charset)
        assert all(ord(ch) < 0x20 or ord(ch) in charset for ch in out), (relative, out)
    assert len(_pdf_safe_text("🜨", _charset(FONT))) == 1, "四字节字符按一个字处理"
    assert _pdf_safe_text("注意⚠️", _charset(FONT)) == _pdf_safe_text("注意⚠", _charset(FONT)), "变体选择符不多出一格"


def test_pdf_renderer_swaps_only_what_no_font_in_the_chain_draws() -> None:
    from horosa_skill.reports.renderers import _wrap_missing_glyphs_chain

    primary = {ord(c) for c in "度数°/克阴√×"} | set(range(0x20, 0x80))
    symbols = {ord("˚")}
    # 补字链有一款画得出「˚」→ 用那款字体画原字，不换
    assert _wrap_missing_glyphs_chain("26˚", primary, [("Sym", symbols)]) == '26<font name="Sym">˚</font>'
    # 整条链都画不了 → 照上游换写法；繁体异体换通行写法；不占位的字不画
    missing: set[str] = set()
    assert _wrap_missing_glyphs_chain("26˚ 360⁄14 尅 隂 ✗ 克​阴", primary, [("Sym", set())], missing) == "26° 360/14 克 阴 × 克阴"
    assert not missing, "换掉的字不算缺字"
