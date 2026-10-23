"""输出文字：简体（缺省，逐字节不变）/ 繁体（台湾字形）/ 繁体（香港字形）。

只是**显示层**：引擎、存档、门禁比对的都是简体原文，只在结果离开本进程（MCP 返回、CLI 打印、报告落盘）时转换。
转换的范围与理由见 `localize.py`；字典与术数词表见 `converter.py`。
"""
from __future__ import annotations

from collections.abc import Iterable

from horosa_skill.textscript.converter import to_simplified, to_traditional, traditional_only_characters

SIMPLIFIED = "zh-Hans"
TRADITIONAL = "zh-Hant"
TRADITIONAL_HK = "zh-Hant-HK"
SCRIPTS = (SIMPLIFIED, TRADITIONAL, TRADITIONAL_HK)

# 设置里能写的值 → 规范值。布尔写法是给图形界面里的开关用的（MCPB / 插件的 user_config 只有 boolean / string）。
_ALIASES = {
    "": SIMPLIFIED, "zh-hans": SIMPLIFIED, "zh-cn": SIMPLIFIED, "simplified": SIMPLIFIED, "简体": SIMPLIFIED,
    "false": SIMPLIFIED, "0": SIMPLIFIED, "off": SIMPLIFIED, "no": SIMPLIFIED,
    "zh-hant": TRADITIONAL, "zh-tw": TRADITIONAL, "traditional": TRADITIONAL, "繁体": TRADITIONAL, "繁體": TRADITIONAL,
    "true": TRADITIONAL, "1": TRADITIONAL, "on": TRADITIONAL, "yes": TRADITIONAL,
    "zh-hant-hk": TRADITIONAL_HK, "zh-hk": TRADITIONAL_HK, "traditional-hk": TRADITIONAL_HK, "hk": TRADITIONAL_HK,
}

# 报告的 `language` 字段（缺省 zh-CN）与规范值的对应。
REPORT_LANGUAGE = {SIMPLIFIED: "zh-CN", TRADITIONAL: "zh-TW", TRADITIONAL_HK: "zh-HK"}


def parse_script(value: object) -> str | None:
    """规范化设置值；认不出返回 None（调用方决定是告警回落还是报错）。"""
    if value is None:
        return SIMPLIFIED
    return _ALIASES.get(str(value).strip().lower())


def convert(text: str, script: str) -> str:
    if script == SIMPLIFIED or not text:
        return text
    return to_traditional(text, script)


def looks_traditional(text: str) -> bool:
    """含只属于繁体的字（如「們」「於」「剋」）。纯简体或简繁同形的文本返回 False。"""
    marks = traditional_only_characters()
    return any(ch in marks for ch in text)


def fold_to_simplified(text: str) -> str:
    """把繁体写的检索词折回简体（本来没有繁体专用字的原样返回）。只用于全文检索这类「没有固定词表」的输入。"""
    return to_simplified(text) if looks_traditional(text) else text


def canonical_name(value: str, vocabulary: Iterable[str]) -> str:
    """把 AI 从繁体输出里抄回来的**标识**（段名、知识库键）对回词表里的原名。

    词表本身就不全是简体（上游有「命宮」「佈局」「大运·歲運」这类原名），所以不能一律繁转简：
    先看原值在不在词表；再按「词表每一项的繁体 / 港繁写法」反查；最后才试繁转简、且结果必须在词表里。
    都对不上就原样返回，由调用方照旧报「未知」。
    """
    names = vocabulary if isinstance(vocabulary, (set, frozenset, dict)) else set(vocabulary)
    if value in names:
        return value
    for name in names:
        if isinstance(name, str) and (convert(name, TRADITIONAL) == value or convert(name, TRADITIONAL_HK) == value):
            return name
    folded = to_simplified(value)
    return folded if folded in names else value


__all__ = [
    "REPORT_LANGUAGE",
    "SCRIPTS",
    "SIMPLIFIED",
    "canonical_name",
    "TRADITIONAL",
    "TRADITIONAL_HK",
    "convert",
    "fold_to_simplified",
    "looks_traditional",
    "parse_script",
]
