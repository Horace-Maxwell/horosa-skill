"""一档（meta）状态的本地脱敏：日期 / 时刻 / 坐标 / 地名后缀 / 号码 → 占位符，再按长度阶梯截断。

路由、澄清抽取、门类分类只需要「说了什么」不需要「几点几分在哪」——占位符保留了「有没有给出生时刻」
这类存在性信息，原值留在本机。已知残余风险：不带 省/市/县/区 后缀的地名、纯数字年龄等不在模式里；
这是用户显式开启决策层后才有的路径，README 隐私表如实列出。
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

MAX_STATE_CHARS = 1200
_TRUNCATION_MARK = "…<截断>"

# 顺序有意义：先长后短，避免半个日期被时刻规则吃掉。
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("id_number", re.compile(r"(?<!\d)\d{15,18}[Xx]?(?!\d)")),
    ("phone", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    ("coordinate", re.compile(r"(?<![A-Za-z0-9])\d{1,3}(?:\.\d+)?\s*[nNsSeEwW]\s*\d{1,2}(?:\.\d+)?(?![A-Za-z0-9])")),
    ("coordinate", re.compile(r"[-+]?\d{1,3}\.\d{3,}\s*[°º]?\s*[NSEW]?\s*[,，]\s*[-+]?\d{1,3}\.\d{3,}\s*[°º]?\s*[NSEW]?")),
    ("date", re.compile(r"(?:公元前|公元)?\d{2,4}\s*[-/年.]\s*\d{1,2}\s*[-/月.]\s*\d{1,2}\s*[日号]?")),
    ("date", re.compile(r"(?<!\d)\d{1,2}\s*月\s*\d{1,2}\s*[日号]")),
    ("date", re.compile(r"(?:农历|阴历|旧历)\s*[正一二三四五六七八九十冬腊]{1,2}月\s*(?:初|廿|三十|二十)?[一二三四五六七八九十]{0,2}")),
    ("time", re.compile(r"(?<!\d)\d{1,2}\s*[:：]\s*\d{2}(?:\s*[:：]\s*\d{2})?")),
    ("time", re.compile(r"(?:凌晨|清晨|早上|早晨|上午|中午|下午|傍晚|晚上|夜里|夜间|半夜)?\s*\d{1,2}\s*点\s*(?:半|\d{1,2}\s*分?|钟)?")),
    ("place", re.compile(r"[一-鿿]{2,7}(?:特别行政区|自治区|自治州|自治县|省|市|县|区|镇|乡|村)")),
)
_PLACEHOLDER = {
    "email": "<邮箱>",
    "id_number": "<证件号>",
    "phone": "<电话>",
    "coordinate": "<坐标>",
    "date": "<日期>",
    "time": "<时刻>",
    "place": "<地点>",
}
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


@dataclass
class Redaction:
    text: str
    counts: dict[str, int] = field(default_factory=dict)
    truncated: bool = False
    original_chars: int = 0

    def as_dict(self) -> dict[str, object]:
        return {"counts": dict(self.counts), "truncated": self.truncated, "original_chars": self.original_chars}


def redact_text(text: str, *, max_chars: int = MAX_STATE_CHARS) -> Redaction:
    """脱敏 + 截断；幂等（对已脱敏文本再跑一次不变）。"""
    raw = unicodedata.normalize("NFC", str(text or ""))
    raw = _CONTROL.sub("", raw)
    counts: dict[str, int] = {}
    out = raw
    for name, pattern in _PATTERNS:
        out, hits = pattern.subn(_PLACEHOLDER[name], out)
        if hits:
            counts[name] = counts.get(name, 0) + hits
    out = re.sub(r"[ \t]+", " ", out).strip()
    truncated = False
    if len(out) > max_chars:
        out = out[: max(0, max_chars - len(_TRUNCATION_MARK))].rstrip() + _TRUNCATION_MARK
        truncated = True
    return Redaction(text=out, counts=counts, truncated=truncated, original_chars=len(raw))


def build_meta_state(
    query: str,
    *,
    technique_names: list[str] | None = None,
    known_setting_keys: list[str] | None = None,
) -> tuple[dict[str, object], Redaction]:
    """一档状态：脱敏问题文本 + 技法名 + 已知设置键名（只有键名，没有值）。"""
    redaction = redact_text(query)
    state: dict[str, object] = {"user_request": redaction.text}
    if technique_names:
        state["technique_names"] = list(technique_names)
    if known_setting_keys:
        state["known_setting_keys"] = sorted(known_setting_keys)
    return state, redaction
