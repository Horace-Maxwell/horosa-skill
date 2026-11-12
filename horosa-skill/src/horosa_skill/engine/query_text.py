"""查询文本归一：路由只在归一后的文本上匹配。

为什么单独成模块：路由表（router.py / intents.py / synonyms.py）全部用简体、半角、小写写成。v0.49 之前
`select_tools` 只做 `.lower()`，于是「擇日結婚」「今天農曆幾號」「ＱＩＭＥＮ」这些与简体同义的说法一个关键词也
碰不到，再被「有出生数据就起本命盘」的兜底悄悄吃掉。归一顺序固定：NFKC（全角→半角、兼容字形）→ 繁→简
（textscript 的转换表，与输出侧的简→繁是同一份资产）→ 小写 → 空白压成单个空格。

守卫：tests/test_router_intents.py 断言路由表里的每个关键词自身已是归一形态，并且把它换成繁体 / 全角 /
大写后路由结果不变（去掉这里任何一步，那条测试就红）。
"""
from __future__ import annotations

import re
import unicodedata

from horosa_skill.textscript import fold_to_simplified

_WHITESPACE = re.compile(r"\s+")


def normalize_query(text: str | None) -> str:
    """NFKC → 繁体折成简体 → 小写 → 压空白。纯函数、离线、确定性。"""
    if not text:
        return ""
    folded = fold_to_simplified(unicodedata.normalize("NFKC", str(text)))
    return _WHITESPACE.sub(" ", folded.lower()).strip()
