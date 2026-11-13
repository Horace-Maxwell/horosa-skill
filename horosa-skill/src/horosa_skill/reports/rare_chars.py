"""罕见字（CJK 扩展 B 及以后）在报告里画不出来时怎么写——星阙 app 的同一张表。

古籍原文里的这些字（灵棋经四库本的异体字、太玄首辞 / 赞辞…）多数系统字体没有字形，PDF 里印成方块。上游 v3.14.0 的做法
（`utils/rareChars.js` + `utils/aiExportPdfVector.js` 的 `pdfSafeText`）：数据保持原字，只在「画出来」的地方回退——字体画得出就照
原字；画不出时，有通行写法的换成通行写法，没有的写成拆字说明（〔左口右臬〕）；回退写法自己也画不出、或表里没登记的字，原样不动。

表不手抄：`horosa-core-js/app-charts/build.mjs` 从 pin 住的上游把 `RARE_CHARS` 写成 `data/rare_chars.json`，清单
（`contracts/app_charts_bundle.json` 的 `rare_chars`）记哈希，`build.mjs --check` 对上游核。存档、导出正文、DOCX（文字由阅读器的
字体去画）都不经这里。
"""
from __future__ import annotations

import json
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "rare_chars.json"
RARE_FROM = 0x20000  # 辅助平面的表意文字起点；上游 RARE_RE = [\u{20000}-\u{3FFFF}]
RARE_TO = 0x3FFFF


@lru_cache(maxsize=1)
def table() -> dict[str, dict[str, str]]:
    """{字: {"same": 通行写法, "parts": 拆字}}（两键都可缺）。数据文件缺了 / 坏了就是空表：不回退，绝不因此出不了报告。"""
    try:
        chars = json.loads(DATA.read_text(encoding="utf-8")).get("chars")
    except (OSError, ValueError):
        return {}
    return {key: value for key, value in (chars or {}).items() if isinstance(value, dict)}


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
