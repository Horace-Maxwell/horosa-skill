"""闸门问题的判定：哪些键回答了它、什么情况下才该问、是不是「事实」（v0.50.0-dev）。

v0.49 之前闸门只按「field 里斜杠分开的键都在载荷里」过滤，而 field 很多是伪名（location / birth data / natal data /
date-time / cast-input …），于是：给了坐标还问地点、给了 seed 还问塔罗的起卦时刻、上海出生也问南半球月令、
`huangli {"date": …}` 什么都不缺照样被拦（追问文本为空）；问题只有中文；一旦带上确认标记，连性别这种只有用户
知道的事实也一并放行。

这里把每个问题解析成：
- `answered(question, payload)`：备选组（任一组的键全在 → 已答）。伪名在 `_ALIASES` 展开；纯确认类（「技法设置是否
  沿用默认」）没有键能回答，只能由确认标记回答。
- `applies(tool, question, payload)`：谓词（南半球月令只在南纬时问）。
- `is_fact(tool, question)`：只有用户知道的事实（结果依赖的性别）——确认标记代替不了。
- `english(question)`：英文版（data/gate_questions_en.json，守卫要求全覆盖）。
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from horosa_skill.errors import bilingual

_EN_PATH = Path(__file__).parents[1] / "data" / "gate_questions_en.json"

_LOCATION = (("lat", "lon"), ("gpsLat", "gpsLon"), ("place",), ("location",))
# 伪字段 → 备选组（每组内全部要有）。组里的 "@location" 展开成上面的地点备选。
_ALIASES: dict[str, tuple[tuple[str, ...], ...]] = {
    "location": _LOCATION,
    "place": _LOCATION,
    "birth data": (("date", "time", "zone", "@location"),),
    "natal data": (("date", "time", "zone", "@location"),),
    "date-time": (("date", "time"),),
    "target time": (("datetime",),),
    "four symbols": (("taiyin", "taiyang", "shaoyang", "shaoyin"),),
    "dice values": (("sign", "house", "planet"),),
    "cast-input": (("up", "lo"), ("upNum", "loNum"), ("open", "close"), ("seed",), ("manualCounts",), ("qiguaShu",),
                   ("date", "time")),
    "cast-input + date/time": (("date", "time"), ("nums",), ("pillars",), ("shu",), ("text",)),
    "options": (("options",),),
}
# 只能由确认标记回答的问题（问的是「这一揽子设置是否沿用默认」，载荷里没有一个键能代表它）。
CONFIRM_ONLY_PARTS = frozenset({"technique settings", "submethod settings", "timeline settings", "school-params", "传本"})
# 逐技法覆盖：同一个 field 在这个技法里由别的键回答。
_TOOL_OVERRIDES: dict[tuple[str, str], tuple[tuple[str, ...], ...]] = {
    ("tarot", "date/time"): (("date", "time"), ("seed",)),
    ("lingqi", "date/time"): (("date", "time"), ("counts",)),
    ("feigong", "dayGan/dayZhi"): (("dayGan", "dayZhi"), ("date", "time")),
    ("canping", "date/time/place"): (("date", "time"),),
    ("heluo", "date/time/place"): (("date", "time"),),
    ("zhengchuan", "date/time/gender"): (("date", "time"),),
    ("yizhangjing", "date/time"): (("date", "time"),),
}
# 不改结果的问题：留在 guidance 里作说明，但从不拦（「节气全要还是挑几个」只筛输出；灵棋问类只是标注）。
NON_BLOCKING: frozenset[tuple[str, str]] = frozenset({("jieqi_year", "jieqis"), ("lingqi", "category")})
# 结果依赖性别、且只有用户知道的技法：性别是事实，确认标记代替不了（v0.50 实测 1 / 0 两种性别逐行对比，见 LESSONS）。
GENDER_FACT_TOOLS: frozenset[str] = frozenset({
    "bazi_birth", "bazi_direct", "ziwei_birth", "ziweizeri", "liureng_runyear", "canping", "heluo", "yizhangjing",
    "zhengchuan", "shaozi", "tieban", "beiji", "nanji", "chunzi", "xianqin", "cetian", "qizhengkin",
})
# 选项超过这么多就不在追问里逐条列出（除非请求本身碰了这个设置）：说缺省值和怎么改。
MAX_SPELLED_OPTIONS = 8


@lru_cache(maxsize=1)
def _english_table() -> dict[str, str]:
    return dict(json.loads(_EN_PATH.read_text(encoding="utf-8"))["questions"])


def english(question: str) -> str | None:
    return _english_table().get(question)


def _has(payload: dict[str, Any], key: str) -> bool:
    if key == "@location":
        return any(all(_has(payload, part) for part in group) for group in _LOCATION)
    node: Any = payload
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return node is not None and node != "" and node != []


def answer_groups(tool: str, field: str) -> tuple[tuple[str, ...], ...] | None:
    """field → 备选组；None = 只能由确认标记回答。

    写法：「a / b」（带空格）是二选一，「a/b」「a + b」是都要。"""
    field = field.strip()
    if (tool, field) in _TOOL_OVERRIDES:
        return _TOOL_OVERRIDES[(tool, field)]
    if field in _ALIASES:
        return _ALIASES[field]
    groups: list[tuple[str, ...]] = []
    for alternative in field.split(" / "):
        parts = [part.strip() for part in re.split(r"/|\+", alternative) if part.strip()]
        expanded: list[tuple[str, ...]] = [()]
        for part in parts:
            if part in CONFIRM_ONLY_PARTS:
                return None
            options = _ALIASES.get(part, ((part,),))
            expanded = [base + option for base in expanded for option in options]
        groups.extend(expanded)
    return tuple(groups) if groups else None


def answered(tool: str, question: dict[str, Any], payload: dict[str, Any]) -> bool:
    groups = answer_groups(tool, str(question.get("field") or ""))
    if groups is None:
        return False
    return any(all(_has(payload, key) for key in group) for group in groups)


def _southern(payload: dict[str, Any]) -> bool:
    for key in ("lat", "gpsLat"):
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip().lower()
        if re.search(r"\d\s*s", text):
            return True
        try:
            return float(text) < 0
        except ValueError:
            continue
    return False


_PREDICATES = {"southern_latitude": _southern}
# 谓词登记（数据在这里，不靠问题里的说明文字）。
_APPLIES_IF: dict[tuple[str, str], str] = {("bazi_birth", "southMonth"): "southern_latitude"}


def applies(tool: str, question: dict[str, Any], payload: dict[str, Any]) -> bool:
    field = str(question.get("field") or "")
    if (tool, field) in NON_BLOCKING:
        return False
    predicate = _APPLIES_IF.get((tool, field))
    return True if predicate is None else _PREDICATES[predicate](payload)


def is_fact(tool: str, question: dict[str, Any]) -> bool:
    return tool in GENDER_FACT_TOOLS and str(question.get("field") or "").strip() in {"gender", "sex"}


def touches(question: dict[str, Any], payload: dict[str, Any]) -> bool:
    """请求本身提到了这个设置（载荷里有这个键）→ 选项值得逐条列出。"""
    return any(part in payload for part in re.split(r"/| / |\+", str(question.get("field") or "")) if part.strip())


def present(tool: str, question: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """给客户端的问题：双语 question；长选项表只在请求碰到这个设置时才逐条列出；事实问题带 fact=true。"""
    item = dict(question)
    zh = str(question.get("question") or question.get("field") or "")
    en = english(zh)
    item["question"] = bilingual(zh, en) if en else zh
    options = question.get("options")
    if isinstance(options, list) and len(options) > MAX_SPELLED_OPTIONS and not touches(question, payload):
        item.pop("options", None)
        item.pop("values", None)
        item["options_count"] = len(options)
        item["how_to_change"] = bilingual(
            f"共 {len(options)} 种，不改就用星阙缺省；要改请直接传 `{question.get('field')}`（可选值见 horosa_agent_guidance(tool_name=…)）。",
            f"{len(options)} choices; the Xingque default applies unless you pass `{question.get('field')}` (values in "
            "horosa_agent_guidance(tool_name=…)).",
        )
    if is_fact(tool, question):
        item["fact"] = True
    return item
