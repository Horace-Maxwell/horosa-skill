from __future__ import annotations

from horosa_skill.errors import DispatchResolutionError
from horosa_skill.schemas.tools import DispatchInput


def _contains_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


def select_tools(request: DispatchInput) -> list[str]:
    text = request.query.lower()
    selected: list[str] = []

    def add(tool_name: str) -> None:
        if tool_name not in selected:
            selected.append(tool_name)

    if _contains_any(text, ["紫微", "ziwei"]):
        add("ziwei_birth")
    if _contains_any(text, ["八字", "bazi", "四柱"]):
        if _contains_any(text, ["直断", "direct", "大运", "流年"]):
            add("bazi_direct")
        else:
            add("bazi_birth")
    if _contains_any(text, ["六壬", "liureng"]):
        if _contains_any(text, ["年运", "runyear", "行年"]):
            add("liureng_runyear")
        else:
            add("liureng_gods")
    if _contains_any(text, ["奇门", "qimen"]):
        add("qimen")
    if _contains_any(text, ["太乙", "taiyi", "太一"]):
        add("taiyi")
    if _contains_any(text, ["金口诀", "jinkou"]):
        add("jinkou")
    if _contains_any(text, ["节气", "jieqi"]):
        add("jieqi_year")
    if _contains_any(text, ["农历", "nongli"]):
        add("nongli_time")
    if _contains_any(text, ["梅易", "卦", "gua"]):
        if _contains_any(text, ["梅易", "meiyi"]):
            add("gua_meiyi")
        else:
            add("gua_desc")
    if _contains_any(text, ["合盘", "关系", "relative", "synastry", "composite"]):
        add("relative")
    if _contains_any(text, ["solar return", "solarreturn", "太阳返照"]):
        add("solarreturn")
    if _contains_any(text, ["lunar return", "lunarreturn", "月返"]):
        add("lunarreturn")
    if _contains_any(text, ["solar arc", "solararc", "太阳弧"]):
        add("solararc")
    if _contains_any(text, ["primary direction", "pdchart", "pd ", "本初方向", "主限"]):
        if _contains_any(text, ["chart", "盘", "chart view"]):
            add("pdchart")
        else:
            add("pd")
    if _contains_any(text, ["profection", "小限"]):
        add("profection")
    if _contains_any(text, ["given year", "流年"]):
        add("givenyear")
    if _contains_any(text, ["zodiacal release", "zr"]):
        add("zr")
    if _contains_any(text, ["印度", "india"]):
        add("india_chart")
    if _contains_any(text, ["13宫", "chart13"]):
        add("chart13")

    if not selected:
        birth = request.birth or (request.subject.birth if request.subject else None)
        relative = request.subject and request.subject.inner and request.subject.outer
        if relative:
            add("relative")
        elif birth:
            add("chart")

    if not selected:
        raise DispatchResolutionError(
            "Unable to resolve a Horosa tool from the dispatch input.",
            code="dispatch.no_matching_tool",
        )

    return selected
