"""罕见字（CJK 扩展 B 及以后）在报告里画不出来时怎么写——星阙 app 的同一张表。

古籍原文里的这些字（灵棋经四库本的异体字、太玄首辞 / 赞辞…）多数系统字体没有字形，PDF 里印成方块。上游 v3.14.0 的做法
（`utils/rareChars.js` + `utils/aiExportPdfVector.js` 的 `pdfSafeText`）：数据保持原字，只在「画出来」的地方回退——字体画得出就照
原字；画不出时，有通行写法的换成通行写法，没有的写成拆字说明（〔左口右臬〕）；回退写法自己也画不出、或表里没登记的字，原样不动。

表不手抄：`horosa-core-js/app-charts/build.mjs` 从 pin 住的上游把 `RARE_CHARS` 写成 `data/rare_chars.json`，清单
（`contracts/app_charts_bundle.json` 的 `rare_chars`）记哈希，`build.mjs --check` 对上游核。存档、导出正文、DOCX（文字由阅读器的
字体去画）都不经这里。

v3.15.0 上游把 `pdfSafeText` 扩成整条缺字链（`pdf_fallback`）：不占位的字直接不画 → 专门映射（˚→°、⁄→/、✓→√…，
`PDF_CHAR_FALLBACK`）→ 兼容分解（NFKC）→ 去附加符号（NFD 去 U+0300–036F）→ 希腊字母名（α→alpha）→ 繁体 / 异体的通行写法
（`data/pdfGlyphFallback.json`）→ 罕见字通行写法 / 〔拆字〕。三张表同样由 build.mjs 从 pin 写进 rare_chars.json。
skill 的 PDF 比上游多一层：先在补字字体链里找画得出的字体，整条链都画不了才走这里（上游只有一款内嵌字体）。
"""
from __future__ import annotations

import json
import unicodedata
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "rare_chars.json"
RARE_FROM = 0x20000  # 辅助平面的表意文字起点；上游 RARE_RE = [\u{20000}-\u{3FFFF}]
RARE_TO = 0x3FFFF


@lru_cache(maxsize=1)
def _data() -> dict:
    try:
        data = json.loads(DATA.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


@lru_cache(maxsize=1)
def table() -> dict[str, dict[str, str]]:
    """{字: {"same": 通行写法, "parts": 拆字}}（两键都可缺）。数据文件缺了 / 坏了就是空表：不回退，绝不因此出不了报告。"""
    chars = _data().get("chars")
    return {key: value for key, value in (chars if isinstance(chars, dict) else {}).items() if isinstance(value, dict)}


def _str_table(key: str) -> dict[str, str]:
    raw = _data().get(key)
    return {k: v for k, v in (raw if isinstance(raw, dict) else {}).items() if isinstance(v, str)}


@lru_cache(maxsize=1)
def char_fallback() -> dict[str, str]:
    """上游 PDF_CHAR_FALLBACK：符号 / 标点的等价写法（˚→°、⁄→/、✓→√、…→...）。"""
    return _str_table("pdf_char_fallback")


@lru_cache(maxsize=1)
def glyph_fallback() -> dict[str, str]:
    """上游 data/pdfGlyphFallback.json：字体没有的繁体 / 异体汉字 → 同一个字的通行写法。"""
    return _str_table("glyph_fallback")


@lru_cache(maxsize=1)
def _greek_names() -> tuple[str, ...]:
    names = _data().get("greek_names")
    return tuple(names) if isinstance(names, list) and len(names) == 25 and all(isinstance(n, str) for n in names) else ()


def greek_name(ch: str) -> str:
    """上游 greekName：小写 α–ω → 名字，大写 Α–Ω（跳过空位 U+03A2）→ 首字母大写的名字；不是希腊字母 → ""。"""
    names = _greek_names()
    code = ord(ch)
    if names and 0x03B1 <= code <= 0x03C9:
        return names[code - 0x03B1]
    if names and 0x0391 <= code <= 0x03A9 and code != 0x03A2:
        name = names[code - 0x0391]
        return name[:1].upper() + name[1:]
    return ""


def is_zero_width_mark(code: int) -> bool:
    """上游 isZeroWidthMark：本身不占位的字（组合附加符号、格式符、变体选择符、标签字符）——字体里没有就不画，画成方块反而多出一格。"""
    return (0x0300 <= code <= 0x036F or 0x1AB0 <= code <= 0x1AFF or 0x1DC0 <= code <= 0x1DFF or 0x20D0 <= code <= 0x20FF
            or 0xFE20 <= code <= 0xFE2F or code in (0x00AD, 0x034F, 0x061C, 0x180E) or 0x200B <= code <= 0x200F
            or 0x202A <= code <= 0x202E or 0x2060 <= code <= 0x2064 or 0x2066 <= code <= 0x206F or code == 0xFEFF
            or 0xFE00 <= code <= 0xFE0F or 0xE0000 <= code <= 0xE007F or 0xE0100 <= code <= 0xE01EF)


def pdf_fallback(ch: str, drawable: Callable[[int], bool]) -> str | None:
    """这个字画不出时 PDF 里写什么（上游 v3.15.0 pdfSafeText 的整条链，顺序照抄）；"" = 不画（不占位的字）；None = 没有可用
    写法（调用方照旧：符号换占位 / 记缺字）。每一步的候选都要整串画得出才用。"""
    def ok(text: str) -> bool:
        return bool(text) and all(drawable(ord(piece)) for piece in text)

    if is_zero_width_mark(ord(ch)):
        return ""
    mapped = char_fallback().get(ch)
    if mapped and ok(mapped):
        return mapped
    nfkc = unicodedata.normalize("NFKC", ch)
    if nfkc != ch and ok(nfkc):
        return nfkc
    base = "".join(piece for piece in unicodedata.normalize("NFD", ch) if not 0x0300 <= ord(piece) <= 0x036F)
    if base and base != ch and ok(base):
        return base
    greek = greek_name(ch)
    if greek and ok(greek):
        return greek
    common = glyph_fallback().get(ch)
    if common and ok(common):
        return common
    return fallback(ch, drawable)


def cache_clear() -> None:
    """换了 DATA（测试）后清掉所有表缓存。"""
    for cached in (_data, table, char_fallback, glyph_fallback, _greek_names):
        cached.cache_clear()


def is_rare(code: int) -> bool:
    return RARE_FROM <= code <= RARE_TO


def fallback(ch: str, drawable: Callable[[int], bool]) -> str | None:
    """这个字画不出时用什么顶（上游 pdfSafeText 的罕见字分支）：通行写法 → 〔拆字说明〕，哪一种都要整串画得出才用；
    都不行、或没登记 → None（调用方照旧原样留着）。"""
    entry = table().get(ch)
    if not entry:
        return None
    for candidate in (entry.get("same"), f"〔{entry['parts']}〕" if entry.get("parts") else None):
        if candidate and all(drawable(ord(piece)) for piece in candidate):
            return candidate
    return None


def safe_text(text: str, drawable: Callable[[int], bool]) -> str:
    """整串过一遍：画得出的、没登记的都原样；不含罕见字的文本原对象返回。"""
    if not any(is_rare(ord(ch)) for ch in text):
        return text
    return "".join((fallback(ch, drawable) or ch) if is_rare(ord(ch)) and not drawable(ord(ch)) else ch for ch in text)
