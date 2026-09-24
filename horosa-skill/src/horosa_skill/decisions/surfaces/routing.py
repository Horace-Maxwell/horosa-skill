"""S1 路由：自然语言 → 技法族 → 工具，两级 Choice 在**同一请求**投机展开（族问 + 每族一问，代码只消费命中族）。

只在确定性 `select_tools()` 抛 `dispatch.no_matching_tool` 时才可能采纳；命中时只记录一致性（影子）。
族表是手工的：`tests/test_decisions_routing.py` 锁「每个注册工具恰在一个族」。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from horosa_skill.decisions.questions import Choice, ChoiceAnswer
from horosa_skill.engine.registry import TOOL_DEFINITIONS

UNKNOWN_FAMILY = "unknown"
NONE_OF_THESE = "none_of_these"

# family → (English+Chinese description, tools)。描述可中文；键必须 ASCII。
FAMILIES: dict[str, tuple[str, tuple[str, ...]]] = {
    "western_natal": (
        "Western natal / derived charts：本命星盘、13 宫、十二分盘、龙盘、迁居盘、中点盘、希腊占星、七政四余、世俗、合盘、占星地图、行星周期、巴比伦",
        ("acg", "babylon", "chart", "chart12", "chart13", "draconic", "germany", "guolao_chart", "harmonic", "hellen_chart", "mundane", "planet_cycles", "relative", "relocation"),
    ),
    "western_predictive": (
        "Western predictive techniques：返照、次限/太阳弧/主限法、黄道释放、法达、小限、年限、推运释放点、行星年龄等",
        ("agepoint", "balbillus", "decennials", "distributions", "ephemeris", "extrareturns", "firdaria", "givenyear", "jaynesprog", "keypoints", "lunarreturn", "lunationphase", "pd", "pdchart", "persiandirected", "planetaryages", "planetaryarc", "prenatalsyzygy", "profection", "prog", "returntimeline", "solararc", "solarreturn", "triplicityrulers", "vedicprog", "yearsystem129", "zr"),
    ),
    "horary_election_western": (
        "Western horary and electional astrology：卜卦占星问事、择日评估、天星征象搜索、七政择日动盘",
        ("horary", "election", "tianxing", "qizhengelection"),
    ),
    "india": ("Indian (Vedic / Jyotish) chart and birth-time rectification：印度占星、生时校正", ("india_chart", "india_rectify")),
    "bazi": ("八字 / 四柱 (Four Pillars)：排八字、直断与大运流年、八字反查出生", ("bazi_birth", "bazi_direct", "bazi_inverse")),
    "ziwei": ("紫微斗数 (Zi Wei Dou Shu)：排盘或格局规则", ("ziwei_birth", "ziwei_rules")),
    "liureng": ("大六壬 (Da Liu Ren)：起课四课三传、行年", ("liureng_gods", "liureng_runyear")),
    "sanshi": ("奇门遁甲 / 太乙神数 / 金口诀 / 三式合一 / 飞宫小奇门", ("qimen", "taiyi", "jinkou", "sanshiunited", "feigong")),
    "yijing_divination": (
        "易占与杂占：六爻、卦辞与梅花易、鬼谷、小六壬、小成图、统摄法、灵棋经、宿占、地占、塔罗、其他卜术",
        ("sixyao", "gua_desc", "gua_meiyi", "guice", "xiaoliuren", "xiaochengtu", "tongshefa", "lingqi", "suzhan", "geomancy", "tarot", "otherbu"),
    ),
    "numerology_shenshu": (
        "神数与数算（以干支起数）：铁板、邵子、皇极、河洛理数、参评、一掌经、神数正传、五兆、太玄、京氏易等",
        ("beiji", "cetian", "chunzi", "fendjing", "jingjue", "nanji", "qizhengkin", "shaozi", "shenyishu", "taixuan", "tieban", "wangji", "wuzhao", "xianqin", "zhengchuan", "heluo", "canping", "yizhangjing"),
    ),
    "zeri": (
        "择日 / 择时：在一段日期范围里搜索合适时刻（黄历、八字、太乙、紫微、六壬、三式、奇门、七政、印度择时）",
        ("bazizeri", "huanglizeri", "indiazeri", "liurengzeri", "qimenzeri", "qizhengzeri", "sanshizeri", "taiyizeri", "ziweizeri"),
    ),
    "calendar": ("Calendar conversion and almanac：农历换算、节气、黄历宜忌、万年历、通书", ("nongli_time", "jieqi_year", "jieqi_birth", "huangli", "calendar_month", "tongshu")),
    "reference_data": ("Reference data and knowledge lookups：名人星盘库、玄史知识库、知识条目、导出契约", ("astrodata", "xuanshi", "knowledge_read", "knowledge_registry", "export_parse", "export_registry")),
}

_FAMILY_OF: dict[str, str] = {tool: family for family, (_desc, tools) in FAMILIES.items() for tool in tools}


def family_of(tool: str) -> str | None:
    return _FAMILY_OF.get(tool)


def _tool_blurb(tool: str) -> str:
    definition = TOOL_DEFINITIONS.get(tool)
    if definition is None:
        return tool
    text = re.split(r"(?<=[。.!?！？])\s*", str(definition.description).strip(), maxsplit=1)[0]
    return text[:80] if text else tool


def build_routing_questions() -> dict[str, Choice]:
    questions: dict[str, Choice] = {
        "family": Choice(
            instructions=(
                "The user_request is a Chinese (or English) request for a divination / astrology computation. "
                "Which technique family does it ask for? Judge only from what the request says. "
                "If it names none of the families, or is not a divination request at all, choose unknown."
            ),
            criteria={**{family: desc for family, (desc, _tools) in FAMILIES.items()}, UNKNOWN_FAMILY: "None of the listed families, or not a divination request"},
            abstain=UNKNOWN_FAMILY,
        )
    }
    for family, (desc, tools) in FAMILIES.items():
        questions[f"tool__{family}"] = Choice(
            instructions=(
                f"Assume the request belongs to the technique family '{family}'. Which single tool below matches the request best? "
                "Pick a tool only when the request clearly asks for what that tool does; otherwise choose none_of_these."
            ),
            criteria={**{tool: _tool_blurb(tool) for tool in tools}, NONE_OF_THESE: "The request wants this family but none of the listed tools fits"},
            abstain=NONE_OF_THESE,
        )
    return questions


@dataclass(frozen=True)
class RoutingDecision:
    tool: str | None
    family: str | None
    family_confidence: float
    tool_confidence: float
    abstained: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "family": self.family,
            "family_confidence": round(self.family_confidence, 4),
            "tool_confidence": round(self.tool_confidence, 4),
            "abstained": self.abstained,
            "reason": self.reason,
        }


def resolve_routing(answers: dict[str, Any], *, tau: float) -> RoutingDecision:
    family_answer = answers.get("family")
    if not isinstance(family_answer, ChoiceAnswer):
        return RoutingDecision(None, None, 0.0, 0.0, True, "family answer missing")
    family = family_answer.choice
    if family == UNKNOWN_FAMILY:
        return RoutingDecision(None, None, family_answer.confidence, 0.0, True, "family=unknown")
    if family_answer.confidence < tau:
        return RoutingDecision(None, family, family_answer.confidence, 0.0, True, f"family confidence {family_answer.confidence:.2f} < tau {tau:.2f}")
    tool_answer = answers.get(f"tool__{family}")
    if not isinstance(tool_answer, ChoiceAnswer):
        return RoutingDecision(None, family, family_answer.confidence, 0.0, True, "tool answer missing")
    if tool_answer.choice == NONE_OF_THESE:
        return RoutingDecision(None, family, family_answer.confidence, tool_answer.confidence, True, "tool=none_of_these")
    if tool_answer.confidence < tau:
        return RoutingDecision(None, family, family_answer.confidence, tool_answer.confidence, True, f"tool confidence {tool_answer.confidence:.2f} < tau {tau:.2f}")
    if tool_answer.choice not in TOOL_DEFINITIONS:
        return RoutingDecision(None, family, family_answer.confidence, tool_answer.confidence, True, "tool not registered")
    return RoutingDecision(tool_answer.choice, family, family_answer.confidence, tool_answer.confidence, False, "ok")
