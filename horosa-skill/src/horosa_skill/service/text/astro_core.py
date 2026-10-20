"""西洋占星快照的基础段：标签表、盘对象访问器、基本信息 / 宫位 / 星体 / 相位 / 希腊点等段的构造。"""
from __future__ import annotations

import re
from typing import Any

from horosa_skill.astro_rulers import derived_whole_sign_label_of
from horosa_skill.astro_sidereal import nakshatra_lord_cn, sidereal_ayanamsa_label
from horosa_skill.engine import astro_snapshot as _astro_snap
from horosa_skill.service._common import _msg, _split_degree
from horosa_skill.time_basis import build_time_basis_line

ASTRO_TEXT_MAP: dict[str, str] = {
    "Aries": "牡羊",
    "Taurus": "金牛",
    "Gemini": "双子",
    "Cancer": "巨蟹",
    "Leo": "狮子",
    "Virgo": "室女",
    "Libra": "天秤",
    "Scorpio": "天蝎",
    "Sagittarius": "射手",
    "Capricorn": "摩羯",
    "Aquarius": "宝瓶",
    "Pisces": "双鱼",
    "Sun": "太阳",
    "Moon": "月亮",
    "Mercury": "水星",
    "Venus": "金星",
    "Mars": "火星",
    "Jupiter": "木星",
    "Saturn": "土星",
    "Uranus": "天王星",
    "Neptune": "海王星",
    "Pluto": "冥王星",
    "North Node": "北交",
    "South Node": "南交",
    "Dark Moon": "暗月",
    "Purple Clouds": "紫气",
    "Pars Fortuna": "福点",
    "Chiron": "凯龙",
    "Syzygy": "月亮朔望点",
    "Intp_Apog": "月亮平均远地点",
    "Intp_Perg": "月亮平均近地点",
    "Pholus": "人龙星",
    "Ceres": "谷神星",
    "Pallas": "智神星",
    "Juno": "婚神星",
    "Vesta": "灶神星",
    "MoonSun": "日月中点",
    "SaturnMars": "火土中点",
    "JupiterVenus": "金木中点",
    # 主限法 v12 (星阙 v2.6.6)：宿命点应星行 id N_Vertex_0（仅 In-Zodiaco 核出）。
    "Vertex": "宿命点",
    "LifeMasterDeg74": "七政命度点",
    "Asc": "上升",
    "Desc": "下降",
    "MC": "中天",
    "IC": "天底",
    "Pars Spirit": "灵点",
    "Pars Faith": "信心点",
    "Pars Substance": "占有点",
    "Pars Wedding [Male]": "婚姻点（男性）",
    "Pars Wedding [Female]": "婚姻点（女性）",
    "Pars Sons": "子嗣点",
    "Pars Father": "父权点",
    "Pars Mother": "母爱点",
    "Pars Brothers": "友情点",
    "Pars Diseases": "灾厄点",
    "Pars Death": "死亡点",
    "Pars Travel": "旅行点",
    "Pars Friends": "朋友点",
    "Pars Enemies": "宿敌点",
    "Pars Saturn": "罪点",
    "Pars Jupiter": "赢点",
    "Pars Mars": "勇点",
    "Pars Venus": "爱点",
    "Pars Mercury": "弱点",
    "Pars Horsemanship": "驾驭点",
    "Pars Life": "生命点",
    "Pars Radix": "光耀点",
    "Whole Sign": "整宫制",
    "Tropical": "回归黄道",
    # 恒星黄道 (星阙 v2.6.4)：原 '恒星黄道，岁差:Lahiri' 硬编码 Lahiri 会误标 Raman/Fagan 盘。
    # 去硬编码 → 真实岁差名由 _build_base_info_lines 另起一行（sidereal_ayanamsa_label）补上。
    "Sidereal": "恒星黄道",
    "ruler": "本垣",
    "exalt": "擢升",
    "dayTrip": "日三分",
    "nightTrip": "夜三分",
    "partTrip": "共管三分",
    "term": "界",
    "face": "十度",
    "exile": "陷",
    "fall": "落",
    "Hayyiz": "得时得地",
    "DemiHayyiz": "得时不得地",
    "InWrongPos": "失时",
    "Cazimi": "日熔",
    "Combust": "灼伤",
    "Sunbeams": "日光蔽匿",
    "House1": "第一宫",
    "House2": "第二宫",
    "House3": "第三宫",
    "House4": "第四宫",
    "House5": "第五宫",
    "House6": "第六宫",
    "House7": "第七宫",
    "House8": "第八宫",
    "House9": "第九宫",
    "House10": "第十宫",
    "House11": "第十一宫",
    "House12": "第十二宫",
    "First Quarter": "第一象限",
    "Second Quarter": "第二象限",
    "Third Quarter": "第三象限",
    "Last Quarter": "第四象限",
}

ASTRO_SHORT_TEXT_MAP: dict[str, str] = {
    "Sun": "日",
    "Moon": "月",
    "Mercury": "水",
    "Venus": "金",
    "Mars": "火",
    "Jupiter": "木",
    "Saturn": "土",
    "Uranus": "天",
    "Neptune": "海",
    "Pluto": "冥",
    "North Node": "北交",
    "South Node": "南交",
    "Dark Moon": "暗月",
    "Purple Clouds": "紫气",
    "Pars Fortuna": "福点",
    "Chiron": "凯龙",
    "Syzygy": "月亮朔望点",
    "Intp_Apog": "月亮平均远地点",
    "Intp_Perg": "月亮平均近地点",
    "Pholus": "人龙星",
    "Ceres": "谷神星",
    "Pallas": "智神星",
    "Juno": "婚神星",
    "Vesta": "灶神星",
    "MoonSun": "日月中点",
    "SaturnMars": "火土中点",
    "JupiterVenus": "金木中点",
    # 主限法 v12 (星阙 v2.6.6)：宿命点应星行 id N_Vertex_0（仅 In-Zodiaco 核出）。
    "Vertex": "宿命点",
    "LifeMasterDeg74": "七政命度点",
}

ASTRO_EGYPTIAN_TERMS: dict[str, list[tuple[str, int, int]]] = {
    "Aries": [("Jupiter", 0, 6), ("Venus", 6, 12), ("Mercury", 12, 20), ("Mars", 20, 25), ("Saturn", 25, 30)],
    "Taurus": [("Venus", 0, 8), ("Mercury", 8, 14), ("Jupiter", 14, 22), ("Saturn", 22, 27), ("Mars", 27, 30)],
    "Gemini": [("Mercury", 0, 6), ("Jupiter", 6, 12), ("Venus", 12, 17), ("Mars", 17, 24), ("Saturn", 24, 30)],
    "Cancer": [("Mars", 0, 7), ("Venus", 7, 13), ("Mercury", 13, 19), ("Jupiter", 19, 26), ("Saturn", 26, 30)],
    "Leo": [("Jupiter", 0, 6), ("Venus", 6, 11), ("Saturn", 11, 18), ("Mercury", 18, 24), ("Mars", 24, 30)],
    "Virgo": [("Mercury", 0, 7), ("Venus", 7, 17), ("Jupiter", 17, 21), ("Mars", 21, 28), ("Saturn", 28, 30)],
    "Libra": [("Saturn", 0, 6), ("Mercury", 6, 14), ("Jupiter", 14, 21), ("Venus", 21, 28), ("Mars", 28, 30)],
    "Scorpio": [("Mars", 0, 7), ("Venus", 7, 11), ("Mercury", 11, 19), ("Jupiter", 19, 24), ("Saturn", 24, 30)],
    "Sagittarius": [("Jupiter", 0, 12), ("Venus", 12, 17), ("Mercury", 17, 21), ("Saturn", 21, 26), ("Mars", 26, 30)],
    "Capricorn": [("Mercury", 0, 7), ("Jupiter", 7, 14), ("Venus", 14, 22), ("Saturn", 22, 26), ("Mars", 26, 30)],
    "Aquarius": [("Mercury", 0, 7), ("Venus", 7, 13), ("Jupiter", 13, 20), ("Mars", 20, 25), ("Saturn", 25, 30)],
    "Pisces": [("Venus", 0, 12), ("Jupiter", 12, 16), ("Mercury", 16, 19), ("Mars", 19, 28), ("Saturn", 28, 30)],
}

ASTRO_OBJECT_ORDER: list[str] = [
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
    "Uranus", "Neptune", "Pluto", "North Node", "South Node", "Dark Moon",
    "Purple Clouds", "Syzygy", "Pars Fortuna", "Intp_Apog", "Intp_Perg",
    "Chiron", "Pholus", "Ceres", "Pallas", "Juno", "Vesta", "LifeMasterDeg74",
]

ASTRO_LOT_ORDER: list[str] = [
    "Pars Spirit", "Pars Mercury", "Pars Venus", "Pars Mars", "Pars Jupiter", "Pars Saturn",
    "Pars Faith", "Pars Substance", "Pars Wedding [Female]", "Pars Wedding [Male]", "Pars Sons",
    "Pars Mother", "Pars Father", "Pars Brothers", "Pars Friends", "Pars Enemies", "Pars Diseases",
    "Pars Death", "Pars Travel", "Pars Horsemanship", "Pars Life", "Pars Radix",
]

ASTRO_POINT_ORDER: list[str] = [
    *ASTRO_OBJECT_ORDER, "Asc", "Desc", "MC", "IC", *ASTRO_LOT_ORDER, "MoonSun", "SaturnMars", "JupiterVenus",
]

ASTRO_HOUSE_SYSTEM_TEXT: dict[str, str] = {
    "0": "整宫制",
    "1": "Alcabitus",
    "2": "Regiomontanus",
    "3": "Placidus",
    "4": "Koch",
    "5": "Vehlow Equal",
    "6": "Polich Page",
    "7": "Sripati",
    "8": "天顶为10宫中点等宫制",
}

PLANET_HOUSE_INFO_NOTE = "说明：行星名后括号中的 nR 为宫主宫位标记；逆行会明确写为“逆行”。"


def _planet_label(value: Any) -> str:
    return _msg(value) or "无"


def _astro_msg(value: Any, *, short: bool = False) -> str:
    text = f"{value or ''}".strip()
    if not text:
        return ""
    if short and text in ASTRO_SHORT_TEXT_MAP:
        return ASTRO_SHORT_TEXT_MAP[text]
    return ASTRO_TEXT_MAP.get(text, text)


def _round3(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    return f"{round(number, 3):g}"


def _parse_house_num(house_id: Any) -> int | None:
    text = _msg(house_id)
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return None
    try:
        number = int(digits)
    except ValueError:
        return None
    return number if number > 0 else None


def _uniq_sorted(values: list[int | None]) -> list[int]:
    output = sorted({value for value in values if isinstance(value, int) and value > 0})
    return output


def _get_chart_object(chart_wrap: dict[str, Any], object_id: str) -> dict[str, Any] | None:
    chart = chart_wrap.get("chart", {}) if isinstance(chart_wrap, dict) else {}
    for obj in chart.get("objects", []) or []:
        if isinstance(obj, dict) and obj.get("id") == object_id:
            return obj
    for obj in chart_wrap.get("lots", []) or []:
        if isinstance(obj, dict) and obj.get("id") == object_id:
            return obj
    return None


def _get_objects_map(chart_wrap: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    chart = chart_wrap.get("chart", {}) if isinstance(chart_wrap, dict) else {}
    for obj in chart.get("objects", []) or []:
        if isinstance(obj, dict) and obj.get("id"):
            mapping[obj["id"]] = obj
    for obj in chart_wrap.get("lots", []) or []:
        if isinstance(obj, dict) and obj.get("id"):
            mapping[obj["id"]] = obj
    return mapping


def _get_stars_map(chart_wrap: dict[str, Any]) -> dict[str, list[Any]]:
    mapping: dict[str, list[Any]] = {}
    chart = chart_wrap.get("chart", {}) if isinstance(chart_wrap, dict) else {}
    for item in chart.get("stars", []) or []:
        if isinstance(item, dict) and item.get("id"):
            mapping[item["id"]] = item.get("stars", []) or []
    return mapping


def _format_planet_house_info(obj: dict[str, Any] | None) -> str:
    if not isinstance(obj, dict):
        return ""
    house_num = _parse_house_num(obj.get("house"))
    rule_nums = _uniq_sorted([_parse_house_num(value) for value in obj.get("ruleHouses", []) or []])
    parts = [f"{house_num}th" if house_num else "-"]
    parts.append("".join(f"{number}R" for number in rule_nums) if rule_nums else "-")
    return "; ".join(parts)


def _append_planet_house_info(label: str, chart_wrap: dict[str, Any], object_id: str) -> str:
    obj = _get_chart_object(chart_wrap, object_id)
    info = _format_planet_house_info(obj)
    return f"{label} ({info})" if info else label


def _normalize_ai_planet_label(text: str) -> str:
    return text.replace("R (宫主)", "R")


def _astro_msg_with_house(object_id: str, chart_wrap: dict[str, Any], *, short: bool = False) -> str:
    label = _astro_msg(object_id, short=short)
    return _normalize_ai_planet_label(_append_planet_house_info(label, chart_wrap, object_id))


def _which_term(sign: str, degree: int) -> str:
    for ruler, start, end in ASTRO_EGYPTIAN_TERMS.get(sign, []):
        if start <= degree < end:
            return _astro_msg(ruler, short=True)
    return ""


def _format_sign_degree(sign: Any, signlon: Any) -> str:
    if sign is None or signlon is None:
        return ""
    degree, minute = _split_degree(signlon)
    deg = abs(degree)
    minute = abs(minute)
    term = _which_term(_msg(sign), deg)
    term_text = f"；位于 {term} 界" if term else ""
    return f"{deg}˚{_astro_msg(sign)}{minute}分{term_text}"


def _format_retrograde_text(obj: dict[str, Any] | None) -> str:
    if not isinstance(obj, dict):
        return ""
    try:
        speed = float(obj.get("lonspeed"))
    except (TypeError, ValueError):
        return ""
    return "；逆行" if speed < 0 else ""


def _lon_to_sign_degree(lon: Any) -> str:
    try:
        value = float(lon) % 360
    except (TypeError, ValueError):
        return ""
    if value < 0:
        value += 360
    sign_index = int(value // 30) % 12
    sign = [
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
    ][sign_index]
    return _format_sign_degree(sign, value - sign_index * 30)


def _as_name_list(values: list[Any], *, short: bool = False) -> str:
    return " , ".join(_astro_msg(value, short=short) for value in values if _msg(value))


def _dignity_text(values: list[Any] | None) -> str:
    if not values:
        return "游走"
    return "，".join(_astro_msg(value) for value in values if _msg(value))


def _format_speed(obj: dict[str, Any] | None) -> str:
    if not isinstance(obj, dict):
        return ""
    try:
        current = float(obj.get("lonspeed"))
    except (TypeError, ValueError):
        return ""
    try:
        mean = float(obj.get("meanSpeed"))
    except (TypeError, ValueError):
        mean = 0.0
    text = f"{_round3(current)}度"
    if current < 0:
        text += "；逆行"
    delta = abs(current - mean)
    if delta > 1:
        text += "; 快速" if current > mean else "; 慢速"
    elif 0 < current < 0.003:
        text += "; 停滞"
    else:
        text += "; 平均"
    return text


def _ruleship_text(values: list[Any] | None) -> str:
    if not values:
        return ""
    return "+".join(_astro_msg(value) for value in values if _msg(value))


def _aspect_text(value: Any) -> str:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return _msg(value)
    return f"{number}˚"


def _format_star_lines(stars: list[Any] | None) -> list[str]:
    lines: list[str] = []
    for item in stars or []:
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            continue
        sign = item[1]
        signlon = item[2]
        star_name = item[4] if len(item) > 4 else item[0]
        degree, minute = _split_degree(signlon)
        lines.append(f"{_astro_msg(star_name)}：{abs(degree)}˚{_astro_msg(sign)}{abs(minute)}分")
    return lines


def _build_base_info_lines(chart_wrap: dict[str, Any], fields: dict[str, Any], *, with_time_basis: bool = False) -> list[str]:
    chart = chart_wrap.get("chart", {}) if isinstance(chart_wrap, dict) else {}
    params = chart_wrap.get("params", {}) if isinstance(chart_wrap, dict) else {}
    lines: list[str] = []
    lon = fields.get("lon") or params.get("lon") or ""
    lat = fields.get("lat") or params.get("lat") or ""
    zone = params.get("zone", fields.get("zone"))
    if lon or lat:
        lines.append(f"经度：{lon}， 纬度：{lat}")
    birth = params.get("birth")
    if birth:
        dayofweek = _msg(chart.get("dayofweek"))
        lines.append(f"{birth}{(' ' + dayofweek) if dayofweek else ''}")
    if zone is not None:
        lines.append(f"时区：{zone} ，{'日生盘' if chart.get('isDiurnal') else '夜生盘'}")
    nongli = chart.get("nongli", {})
    if isinstance(nongli, dict) and nongli.get("birth"):
        lines.append(f"真太阳时：{nongli['birth']}")
    # 跨技法时间基准自声明（上游 astroAiSnapshot.js:442-445，v3.11）：星盘按输入钟面时刻与时区换算世界时起盘，
    # 只在整盘快照的 [起盘信息] 出（buildAstroSnapshotContent 传 withTimeBasis；[信息] 段复用本函数但不带）。
    if with_time_basis:
        lines.append(
            build_time_basis_line(
                time_alg=1,
                late_zi_hour_use_next_day=fields.get("lateZiHourUseNextDay"),
                after23_new_day=fields.get("after23NewDay"),
            )
        )
    zodiacal = chart.get("zodiacal") or ASTRO_HOUSE_SYSTEM_TEXT.get(str(fields.get("zodiacal")), fields.get("zodiacal"))
    # [Q-148/T-55]（上游 astroAiSnapshot.js:461-463）：派生盘（十三分/十二分/调波/龙盘）宫位被后端强制为
    # 「变换后上升整宫」、每宫打 houses[].hsysDerived='wholeFromAsc' —— 请求里的分宫制不是这张盘实际用的，
    # 标注必须说真话（数值不动）。非派生盘沿用本仓既有口径（后端回显优先）。
    hsys = (
        derived_whole_sign_label_of(chart)
        or chart.get("hsys")
        or ASTRO_HOUSE_SYSTEM_TEXT.get(str(fields.get("hsys")), fields.get("hsys"))
    )
    zodiacal_text = _astro_msg(zodiacal)
    hsys_text = _astro_msg(hsys)
    if zodiacal_text or hsys_text:
        lines.append(f"{zodiacal_text}，{hsys_text}")
    # 恒星黄道 (星阙 v2.6.4)：sidereal 盘附岁差(ayanāṃśa)名，区分 Lahiri/Raman/Fagan 等不同制。
    # chart.zodiacal 是已本地化的字符串("恒星黄道")，故以后端解析后的字段为准（西洋盘=siderealAyanamsa，
    # 印占盘=siderealModeKey + 数值 ayanamsaValue）；旧后端缺字段时，回退「请求为恒星黄道→请求 ayan/缺省 lahiri」。
    ayan_key = chart.get("siderealAyanamsa") or chart.get("siderealModeKey")
    if not ayan_key and str(fields.get("zodiacal")) in {"1", "True", "true"}:
        ayan_key = fields.get("siderealAyanamsa") or fields.get("indiaAyanamsa") or "lahiri"
    if not ayan_key and (fields.get("indiaHsys") is not None or fields.get("indiaAyanamsa") is not None):
        ayan_key = fields.get("indiaAyanamsa") or "lahiri"  # 印占盘恒为恒星黄道
    if ayan_key:
        ayan_value = chart.get("ayanamsaValue")
        if ayan_value not in (None, ""):
            lines.append(f"恒星黄道岁差：{sidereal_ayanamsa_label(ayan_key)}（{ayan_value}）")
        else:
            lines.append(f"恒星黄道岁差：{sidereal_ayanamsa_label(ayan_key)}")
    lines.append(PLANET_HOUSE_INFO_NOTE)
    if chart.get("dayerStar"):
        lines.append(f"日主星：{_astro_msg(chart['dayerStar'], short=True)}")
    if chart.get("timerStar"):
        lines.append(f"时主星：{_astro_msg(chart['timerStar'], short=True)}")
    return lines


def _build_house_cusp_lines(chart_wrap: dict[str, Any]) -> list[str]:
    chart = chart_wrap.get("chart", {}) if isinstance(chart_wrap, dict) else {}
    lines: list[str] = []
    for house in chart.get("houses", []) or []:
        if not isinstance(house, dict) or house.get("lon") is None:
            continue
        lines.append(f"{_astro_msg(house.get('id'))} 宫头：{_lon_to_sign_degree(house.get('lon'))}")
    return lines


def _build_star_and_lot_position_lines(chart_wrap: dict[str, Any]) -> list[str]:
    object_map = _get_objects_map(chart_wrap)
    lines: list[str] = []

    def push_one(object_id: str) -> None:
        obj = object_map.get(object_id)
        if not isinstance(obj, dict) or obj.get("sign") is None or obj.get("signlon") is None:
            return
        lines.append(
            f"{_astro_msg_with_house(object_id, chart_wrap, short=True)}："
            f"{_format_sign_degree(obj.get('sign'), obj.get('signlon'))}"
            f"{_format_retrograde_text(obj)}"
        )

    for object_id in ASTRO_OBJECT_ORDER:
        push_one(object_id)
    for object_id in ASTRO_LOT_ORDER:
        push_one(object_id)
    return lines


def _as_chart_wrap(value: Any, *, fallback_lots: Any = None, fallback_aspects: Any = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    if isinstance(value.get("chart"), dict):
        wrapper = dict(value)
    elif isinstance(value.get("objects"), list) or isinstance(value.get("houses"), list):
        wrapper = {"chart": value}
    else:
        return {}
    if fallback_lots is not None and "lots" not in wrapper:
        wrapper["lots"] = fallback_lots
    if fallback_aspects is not None and "aspects" not in wrapper:
        wrapper["aspects"] = fallback_aspects
    return wrapper


def _top_level_chart_wrap(response: dict[str, Any]) -> dict[str, Any]:
    return _as_chart_wrap(
        response.get("chart"),
        fallback_lots=response.get("lots"),
        fallback_aspects=response.get("aspects"),
    )


def _chart_wrap_from_response(response: dict[str, Any], key: str) -> dict[str, Any]:
    return _as_chart_wrap(
        response.get(key),
        fallback_lots=response.get("lots"),
        fallback_aspects=response.get("aspects"),
    )


def _chart_position_table_lines(chart_wrap: dict[str, Any], *, limit: int | None = None) -> list[str]:
    object_map = _get_objects_map(chart_wrap)
    rows = ["| 星体/虚点 | 位置 | 宫位 | 速度 |", "| --- | --- | --- | --- |"]
    count = 0
    for object_id in [*ASTRO_OBJECT_ORDER, *ASTRO_LOT_ORDER]:
        obj = object_map.get(object_id)
        if not isinstance(obj, dict) or obj.get("sign") is None or obj.get("signlon") is None:
            continue
        rows.append(
            "| "
            f"{_astro_msg(object_id, short=True)} | "
            f"{_format_sign_degree(obj.get('sign'), obj.get('signlon'))}{_format_retrograde_text(obj)} | "
            f"{_astro_msg(obj.get('house')) or '—'} | "
            f"{_format_speed(obj) if obj.get('lonspeed') is not None else '—'} |"
        )
        count += 1
        if limit is not None and count >= limit:
            break
    if count == 0:
        rows.append("| 无 | 无 | 无 | 无 |")
    return rows


def _only_ruler_exalt_reception(fields: dict[str, Any] | None) -> bool:
    """上游 resolveOnlyRulerExaltReception（astroAiSnapshot.js:190-207）：全局设置 showOnlyRulExaltReception（1/true）=
    「仅按本垣擢升计算互容接纳」。headless 无 localStorage，请求顶层同名键即该全局设置；缺省关。"""
    value = (fields or {}).get("showOnlyRulExaltReception") if isinstance(fields, dict) else None
    return value in (1, True, "1", "true", "True")


def _has_ruler_or_exalt(ary: Any) -> bool:
    return isinstance(ary, list) and any(value in ("ruler", "exalt") for value in ary)


def _keep_reception_line(item: dict[str, Any] | None, *, abnormal: bool = False, only_ruler_exalt: bool = False) -> bool:
    """上游 keepReceptionLine（astroAiSnapshot.js:222-235）：开关关 → 全留；开 → 正接纳须供给方为本垣/擢升，
    邪接纳供给方或受益方任一为本垣/擢升即留。"""
    if not only_ruler_exalt:
        return True
    if not isinstance(item, dict):
        return False
    supplier_ok = _has_ruler_or_exalt(item.get("supplierRulerShip"))
    if not abnormal:
        return supplier_ok
    return supplier_ok or _has_ruler_or_exalt(item.get("beneficiaryDignity"))


def _keep_mutual_line(item: dict[str, Any] | None, *, only_ruler_exalt: bool = False) -> bool:
    """上游 keepMutualLine（astroAiSnapshot.js:237-245）：开 → 互容两方都须为本垣/擢升。"""
    if not only_ruler_exalt:
        return True
    if not isinstance(item, dict) or not isinstance(item.get("planetA"), dict) or not isinstance(item.get("planetB"), dict):
        return False
    return _has_ruler_or_exalt(item["planetA"].get("rulerShip")) and _has_ruler_or_exalt(item["planetB"].get("rulerShip"))


def _reception_reject_mark(item: dict[str, Any] | None) -> str:
    # FIX-15（镜像 astroAiSnapshot.isReject）：supplier 在 beneficiary 所在座为 exile/fall = 凶接纳=拒绝。
    dig = item.get("supplierRulerShip") if isinstance(item, dict) else None
    if not dig:
        return ""
    arr = dig if isinstance(dig, list) else [dig]
    return "（拒绝）" if any(d in ("exile", "fall") for d in arr) else ""


def _build_info_section(chart_wrap: dict[str, Any], fields: dict[str, Any]) -> list[str]:
    chart = chart_wrap.get("chart", {}) if isinstance(chart_wrap, dict) else {}
    chart_data = chart_wrap if isinstance(chart_wrap, dict) else {}
    lines = _build_base_info_lines(chart_wrap, fields)

    anti = chart.get("antiscias", {}) if isinstance(chart, dict) else {}
    anti_lines: list[str] = []
    for item in anti.get("antiscia", []) or []:
        if isinstance(item, (list, tuple)) and len(item) >= 3:
            anti_lines.append(f"{_astro_msg(item[0], short=True)} 与 {_astro_msg(item[1], short=True)} 成映点 误差{_round3(item[2])}")
    for item in anti.get("cantiscia", []) or []:
        if isinstance(item, (list, tuple)) and len(item) >= 3:
            anti_lines.append(f"{_astro_msg(item[0], short=True)} 与 {_astro_msg(item[1], short=True)} 成反映点 误差{_round3(item[2])}")
    if anti_lines:
        lines.append("映点/反映点")
        lines.extend(anti_lines)

    only_rul_exalt = _only_ruler_exalt_reception(fields)
    receptions = chart_data.get("receptions", {}) if isinstance(chart_data, dict) else {}
    normal_receptions = [
        item for item in receptions.get("normal", []) or [] if _keep_reception_line(item, only_ruler_exalt=only_rul_exalt)
    ]
    abnormal_receptions = [
        item for item in receptions.get("abnormal", []) or []
        if _keep_reception_line(item, abnormal=True, only_ruler_exalt=only_rul_exalt)
    ]
    if normal_receptions or abnormal_receptions:
        lines.append("接纳")
        lines.append("正接纳：")
        for item in normal_receptions:
            lines.append(
                f"{_astro_msg_with_house(item.get('beneficiary'), chart_wrap, short=True)} 被 "
                f"{_astro_msg_with_house(item.get('supplier'), chart_wrap, short=True)} 接纳 "
                f"({_ruleship_text(item.get('supplierRulerShip'))}){_reception_reject_mark(item)}"
            )
        lines.append("邪接纳：")
        for item in abnormal_receptions:
            lines.append(
                f"{_astro_msg_with_house(item.get('beneficiary'), chart_wrap, short=True)} "
                f"({_ruleship_text(item.get('beneficiaryDignity'))}) 被 "
                f"{_astro_msg_with_house(item.get('supplier'), chart_wrap, short=True)} 接纳 "
                f"({_ruleship_text(item.get('supplierRulerShip'))}){_reception_reject_mark(item)}"
            )

    mutuals = chart_data.get("mutuals", {}) if isinstance(chart_data, dict) else {}
    normal_mutuals = [item for item in mutuals.get("normal", []) or [] if _keep_mutual_line(item, only_ruler_exalt=only_rul_exalt)]
    abnormal_mutuals = [item for item in mutuals.get("abnormal", []) or [] if _keep_mutual_line(item, only_ruler_exalt=only_rul_exalt)]
    if normal_mutuals or abnormal_mutuals:
        lines.append("互容")
        lines.append("正互容：")
        for item in normal_mutuals:
            if not isinstance(item, dict):
                continue
            a = item.get("planetA", {})
            b = item.get("planetB", {})
            lines.append(
                f"{_astro_msg_with_house(a.get('id'), chart_wrap, short=True)} "
                f"({_ruleship_text(a.get('rulerShip'))}) 与 "
                f"{_astro_msg_with_house(b.get('id'), chart_wrap, short=True)} "
                f"({_ruleship_text(b.get('rulerShip'))}) 互容"
            )
        lines.append("邪互容：")
        for item in abnormal_mutuals:
            if not isinstance(item, dict):
                continue
            a = item.get("planetA", {})
            b = item.get("planetB", {})
            lines.append(
                f"{_astro_msg_with_house(a.get('id'), chart_wrap, short=True)} "
                f"({_ruleship_text(a.get('rulerShip'))}) 与 "
                f"{_astro_msg_with_house(b.get('id'), chart_wrap, short=True)} "
                f"({_ruleship_text(b.get('rulerShip'))}) 互容"
            )

    surround = chart_data.get("surround", {}) if isinstance(chart_data, dict) else {}
    attack_lines: list[str] = []
    for key, planet in (surround.get("attacks", {}) or {}).items():
        if not isinstance(planet, dict):
            continue
        candidates: list[list[dict[str, Any]]] = []
        for candidate_key in ("MinDelta", "MarsSaturn", "SunMoon", "VenusJupiter"):
            candidate = planet.get(candidate_key)
            if isinstance(candidate, list) and len(candidate) == 2:
                candidates.append(candidate)
        for pair in candidates:
            attack_lines.append(
                f"{_astro_msg_with_house(key, chart_wrap, short=True)} 被 "
                f"{_astro_msg_with_house(pair[0].get('id'), chart_wrap, short=True)} "
                f"(通过{_aspect_text(pair[0].get('aspect'))}相位) 与 "
                f"{_astro_msg_with_house(pair[1].get('id'), chart_wrap, short=True)} "
                f"(通过{_aspect_text(pair[1].get('aspect'))}相位) 围攻"
            )
    if attack_lines:
        lines.append("光线围攻")
        lines.extend(attack_lines)

    house_lines: list[str] = []
    for key, pair in (surround.get("houses", {}) or {}).items():
        if isinstance(pair, list) and len(pair) == 2:
            house_lines.append(
                f"{_astro_msg_with_house(pair[0].get('id'), chart_wrap, short=True)} 与 "
                f"{_astro_msg_with_house(pair[1].get('id'), chart_wrap, short=True)} 夹 {_astro_msg(key)}"
            )
    if house_lines:
        lines.append("夹宫")
        lines.extend(house_lines)

    planet_lines: list[str] = []
    for key, pair in (surround.get("planets", {}) or {}).items():
        if key == "BySunMoon" and isinstance(pair, dict) and pair.get("id"):
            planet_lines.append(f"{_astro_msg_with_house('Moon', chart_wrap, short=True)} 与 {_astro_msg_with_house('Sun', chart_wrap, short=True)} 夹 {_astro_msg_with_house(pair['id'], chart_wrap, short=True)}")
            continue
        if isinstance(pair, dict) and isinstance(pair.get("SunMoon"), list) and len(pair["SunMoon"]) == 2:
            sun_moon = pair["SunMoon"]
            planet_lines.append(
                f"{_astro_msg_with_house(sun_moon[0].get('id'), chart_wrap, short=True)} 与 "
                f"{_astro_msg_with_house(sun_moon[1].get('id'), chart_wrap, short=True)} 夹 "
                f"{_astro_msg_with_house(key, chart_wrap, short=True)}"
            )
            continue
        if isinstance(pair, list) and len(pair) == 2:
            planet_lines.append(
                f"{_astro_msg_with_house(pair[0].get('id'), chart_wrap, short=True)} 与 "
                f"{_astro_msg_with_house(pair[1].get('id'), chart_wrap, short=True)} 夹 "
                f"{_astro_msg_with_house(key, chart_wrap, short=True)}"
            )
    if planet_lines:
        lines.append("夹星")
        lines.extend(planet_lines)

    decl_parallel = chart_data.get("declParallel", {}) if isinstance(chart_data, dict) else {}
    parallel_lines: list[str] = []
    for index, ids in enumerate(decl_parallel.get("parallel", []) or [], start=1):
        if isinstance(ids, list) and ids:
            parallel_lines.append(f"平行星体{index}：{_as_name_list(ids, short=True)}")
    for object_id, ids in (decl_parallel.get("contraParallel", {}) or {}).items():
        if isinstance(ids, list) and ids:
            parallel_lines.append(f"相对 {_astro_msg(object_id, short=True)} 星体：{_as_name_list(ids, short=True)}")
    if parallel_lines:
        lines.append("纬照")
        lines.extend(parallel_lines)
    return lines


def _build_aspect_section(chart_wrap: dict[str, Any]) -> list[str]:
    aspects = chart_wrap.get("aspects", {}) if isinstance(chart_wrap, dict) else {}
    normal = aspects.get("normalAsp") if isinstance(aspects, dict) else None
    immediate = aspects.get("immediateAsp") if isinstance(aspects, dict) else None
    sign_asp = aspects.get("signAsp") if isinstance(aspects, dict) else None
    # Some chart types (e.g. india_chart) return these as empty lists instead of dicts; coerce any
    # non-dict to {} so the per-object `.get()` lookups below don't raise `'list' object has no attribute 'get'`.
    normal = normal if isinstance(normal, dict) else {}
    immediate = immediate if isinstance(immediate, dict) else {}
    sign_asp = sign_asp if isinstance(sign_asp, dict) else {}
    lines = ["标准相位"]
    for object_id in ASTRO_POINT_ORDER:
        one = normal.get(object_id)
        if not isinstance(one, dict):
            continue
        lines.append(_astro_msg_with_house(object_id, chart_wrap, short=True))
        # [Q-254/T-227]（上游 astroAiSnapshot.js:719-722）：正合（|orbDir|<0.3，不分入离）相态写「正合」，
        # 不再与 Separative 同折为「离相」。四态序 入相/正合/离相/None 与上游同。
        for key, state in (("Applicative", "入相"), ("Exact", "正合"), ("Separative", "离相"), ("None", "")):
            for asp in one.get(key, []) or []:
                if not isinstance(asp, dict):
                    continue
                suffix = f" {state}" if state else ""
                lines.append(
                    f"{_aspect_text(asp.get('asp'))} {_astro_msg_with_house(asp.get('id'), chart_wrap, short=True)}{suffix} 误差{_round3(asp.get('orb'))}".strip()
                )
    lines.append("立即相位")
    for object_id in ASTRO_OBJECT_ORDER:
        one = immediate.get(object_id)
        if not isinstance(one, list) or len(one) < 2:
            continue
        lines.append(
            f"{_astro_msg_with_house(object_id, chart_wrap, short=True)} "
            f"{_aspect_text(one[0].get('asp'))} {_astro_msg_with_house(one[0].get('id'), chart_wrap, short=True)} 离相 误差{_round3(one[0].get('orb'))}；"
            f"{_aspect_text(one[1].get('asp'))} {_astro_msg_with_house(one[1].get('id'), chart_wrap, short=True)} 入相 误差{_round3(one[1].get('orb'))}"
        )
    lines.append("星座相位")
    for object_id in ASTRO_OBJECT_ORDER:
        one = sign_asp.get(object_id)
        if not isinstance(one, list) or not one:
            continue
        lines.append(f"主体：{_astro_msg_with_house(object_id, chart_wrap, short=True)}")
        for asp in one:
            if isinstance(asp, dict):
                lines.append(f"与 {_astro_msg_with_house(asp.get('id'), chart_wrap, short=True)} 成 {_aspect_text(asp.get('asp'))} 相位")
    return lines


def _build_planet_section(chart_wrap: dict[str, Any]) -> list[str]:
    object_map = _get_objects_map(chart_wrap)
    stars_map = _get_stars_map(chart_wrap)
    orient_occident = chart_wrap.get("chart", {}).get("orientOccident", {}) if isinstance(chart_wrap, dict) else {}
    lines: list[str] = []
    for object_id in ASTRO_OBJECT_ORDER:
        obj = object_map.get(object_id)
        if not isinstance(obj, dict):
            continue
        lines.append(_astro_msg_with_house(object_id, chart_wrap, short=True))
        lines.append(f"落座：{_format_sign_degree(obj.get('sign'), obj.get('signlon'))}{_format_retrograde_text(obj)}")
        if obj.get("house"):
            lines.append(f"落宫：{_astro_msg(obj.get('house'))}")
        if isinstance(obj.get("antisciaPoint"), dict):
            lines.append(f"映点：{_format_sign_degree(obj['antisciaPoint'].get('sign'), obj['antisciaPoint'].get('signlon'))}")
        if isinstance(obj.get("cantisciaPoint"), dict):
            lines.append(f"反映点：{_format_sign_degree(obj['cantisciaPoint'].get('sign'), obj['cantisciaPoint'].get('signlon'))}")
        if obj.get("meanSpeed") is not None:
            lines.append(f"平均速度：{_round3(obj.get('meanSpeed'))}")
        if obj.get("lonspeed") is not None:
            lines.append(f"当前速度：{_format_speed(obj)}")
        dignity = _dignity_text(obj.get("selfDignity"))
        extras = []
        if _msg(obj.get("hayyiz")) and _msg(obj.get("hayyiz")) != "None":
            extras.append(_astro_msg(obj.get("hayyiz")))
        if obj.get("isVOC"):
            extras.append("空亡")
        if dignity != "游走" or extras:
            lines.append(f"禀赋：{dignity}{('，' + '，'.join(extras)) if extras else ''}")
        if obj.get("score") is not None:
            lines.append(f"分值：{obj.get('score')}")
        for key, label in (
            ("altitudeTrue", "真地平纬度"),
            ("altitudeAppa", "视地平纬度"),
            ("azimuth", "地坪经度"),
            ("lon", "黄经"),
            ("lat", "黄纬"),
            ("ra", "赤经"),
            ("decl", "赤纬"),
        ):
            if obj.get(key) is not None:
                lines.append(f"{label}：{_round3(obj.get(key))}˚")
        if obj.get("moonPhase") is not None:
            lines.append(f"月限：{_astro_msg(obj.get('moonPhase'))}")
        if obj.get("sunPos") is not None:
            lines.append(f"太阳关系：{_astro_msg(obj.get('sunPos'))}")
        if obj.get("ruleHouses"):
            lines.append(f"入垣宫：{_as_name_list(obj.get('ruleHouses'))}")
        if obj.get("exaltHouse"):
            lines.append(f"擢升宫：{_astro_msg(obj.get('exaltHouse'))}")
        if obj.get("governSign"):
            govern = _astro_msg(obj.get("governSign"))
            govern_planets = obj.get("governPlanets") or []
            if govern_planets:
                govern += f" , {_as_name_list(govern_planets, short=True)}"
            lines.append(f"宰制星座：{govern}")
        occ = orient_occident.get(object_id) if isinstance(orient_occident, dict) else None
        if isinstance(occ, dict):
            oriental = [item.get("id") for item in occ.get("oriental", []) or [] if isinstance(item, dict)]
            occidental = [item.get("id") for item in occ.get("occidental", []) or [] if isinstance(item, dict)]
            if oriental:
                lines.append(f"东出星：{_as_name_list(oriental, short=True)}")
            if occidental:
                lines.append(f"西入星：{_as_name_list(occidental, short=True)}")
        stars = stars_map.get(object_id) or []
        if stars:
            lines.append("汇合恒星：")
            lines.extend(_format_star_lines(stars))
    return lines


def _build_lots_section(chart_wrap: dict[str, Any]) -> list[str]:
    object_map = _get_objects_map(chart_wrap)
    stars_map = _get_stars_map(chart_wrap)
    lines: list[str] = []
    for object_id in ASTRO_LOT_ORDER:
        obj = object_map.get(object_id)
        if not isinstance(obj, dict):
            continue
        lines.append(_astro_msg_with_house(object_id, chart_wrap, short=False))
        lines.append(f"落座：{_format_sign_degree(obj.get('sign'), obj.get('signlon'))}{_format_retrograde_text(obj)}")
        if obj.get("house"):
            lines.append(f"落宫：{_astro_msg(obj.get('house'))}")
        stars = stars_map.get(object_id) or []
        if stars:
            lines.append("汇合恒星：")
            lines.extend(_format_star_lines(stars))
    return lines


def _build_possibility_section(chart_wrap: dict[str, Any]) -> list[str]:
    predict = chart_wrap.get("predict", {}) if isinstance(chart_wrap, dict) else {}
    planet_sign = predict.get("PlanetSign", {}) if isinstance(predict, dict) else {}
    if not isinstance(planet_sign, dict):  # some chart types return this empty as a list, not a dict
        planet_sign = {}
    lines: list[str] = []
    for key, items in planet_sign.items():
        lines.append(_astro_msg(key, short=True))
        for text in items or []:
            lines.append(_msg(text))
    return lines


def _sign_degree(lon: Any) -> str:
    # lon → "Y˚<座>Z分" (simplified lonToSignDegree; the term clause is dropped — sign+degree is faithful).
    try:
        value = float(lon) % 360.0
    except (TypeError, ValueError):
        return ""
    if value < 0:
        value += 360.0
    sign_idx = int(value // 30) % 12
    signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
    deg, minute = _split_degree(value)
    return f"{deg}˚{_astro_msg(signs[sign_idx])}{minute}分"


def _build_natal_extra_sections(extras: dict[str, Any]) -> dict[str, str]:
    """本命增补三段（12分度 / 主宰星链链行 / 寿命格局）的排版——数据来自 vendored natalExtras（JS astroextra），排版逐字镜像
    上游 astroAiSnapshot.js（engine/astro_snapshot.py 单源）：

    - [12分度]（:991-1006）：曜|本命|12分度 GFM 表，位置走 lonToSignDegree（带「位于 X 界」），名称 msg 单字名；
    - 链行（:1037）：`${msg(id)}：${chain.map(msg).join(' → ')}`（段尾判读口径行 + 整宫制宫主表由快照装配时补）；
    - [寿命格局]（:1121-1245）：lifespanName = msg 单字名（日/火…，此前本仓印长名「太阳/火星」）、生命主位置带界。
    """
    out: dict[str, str] = {}
    dodeca_lines = _astro_snap.build_dodeca_lines(extras.get("dodeca"))
    if dodeca_lines:
        out["12分度"] = "\n".join(dodeca_lines)
    chain_lines = _astro_snap.build_dispositor_chain_lines(extras.get("dispositor"))
    if chain_lines:
        out["主宰星链"] = "\n".join(chain_lines)
    lifespan_lines = _astro_snap.clean_lines(_astro_snap.build_lifespan_lines(extras.get("lifespan")))
    if lifespan_lines:
        out["寿命格局"] = "\n".join(lifespan_lines)
    return out


def _build_nakshatra_lines(response: dict[str, Any]) -> list[str]:
    """西洋月宿 (星阙 v2.6.4)：恒星黄道盘的 perchart 响应在 chart.nakshatras 带 27 宿，
    逐行星列「宿名(梵)·宿(中)·宿主·第N足」。取数路径是 chart.nakshatras（非顶层），仅 sidereal 出。"""
    chart = response.get("chart", {}) if isinstance(response, dict) else {}
    nakshatras = chart.get("nakshatras") if isinstance(chart, dict) else None
    if not isinstance(nakshatras, dict) or not nakshatras:
        return []
    lines: list[str] = []
    for obj_id, info in nakshatras.items():
        if not isinstance(info, dict):
            continue
        name = _msg(info.get("name"))
        label = _msg(info.get("label"))
        lord = nakshatra_lord_cn(info.get("lord"))
        pada = info.get("pada")
        parts = [p for p in (name, label) if p]
        head = "·".join(parts) if parts else "—"
        suffix = f"，宿主{lord}" if lord else ""
        pada_text = f"，第{pada}足" if pada else ""
        lines.append(f"{_planet_label(obj_id)}：{head}{suffix}{pada_text}")
    return lines


# ─────────────────────────────────────────────────────────────────────────────
# 世俗盘子盘群：年度入宫盘之外，围绕定盘展开的新月/满月/日月食/地区盘/行星周期等子盘。
# 子盘时刻均由后端精算端点求得（prenatal_syzygy 朔望、eclipsedetail 食时长、greatconj/barbault
# 慢星周期、jieqi/year 四季入宫），再以入宫盘同制起 /chart；纯确定性、无 UI 依赖。判词与分析段
# （世俗宫义/定局·年主/盘主/入境骨架/地理分野）由 vendored 上游 buildAiSnapshot 抽出件产出（见 _mundane_analysis_sections）。
# 食端点仅回全球食时长（食时长定则的关键量）不回极大时刻，故日/月食段呈影响时长判词而非整轮盘，如实标注。


def _mundane_analysis_sections(analysis: dict[str, Any] | None, titles: tuple[str, ...]) -> list[tuple[str, str]]:
    """把 JS `mundane_cards` action=analysis 的 judge（'[世俗宫义]\n…'）与 extraSecs（各 '[标题]\n正文'）按 titles 序转成
    (标题, 正文) 段；缺的段不补（上游 try/catch 同形：算不出即不出段）。"""
    if not isinstance(analysis, dict):
        return []
    blocks: list[str] = []
    judge = analysis.get("judge")
    if isinstance(judge, str) and judge.strip():
        blocks.append(judge)
    blocks.extend(b for b in (analysis.get("extraSecs") or []) if isinstance(b, str) and b.strip())
    by_title: dict[str, str] = {}
    for block in blocks:
        head, _, body = block.strip().partition("\n")
        m = re.match(r"^\[(.+)\]$", head.strip())
        if m and m.group(1) not in by_title:
            by_title[m.group(1)] = body.strip()
    return [(title, by_title[title]) for title in titles if title in by_title]
def _mundane_chart_digest(
    chart_response: dict[str, Any], *, points: tuple[str, ...] = ("Sun", "Moon", "Asc", "MC")
) -> list[str]:
    """子盘四轴/日月摘要：不铺全盘，仅取关键结构点，避免子盘群把导出撑爆。"""
    wrap = _top_level_chart_wrap(chart_response)
    om = _get_objects_map(wrap)
    lines: list[str] = []
    for pid in points:
        obj = om.get(pid)
        if isinstance(obj, dict) and obj.get("sign") is not None and obj.get("signlon") is not None:
            lines.append(
                f"{_astro_msg(pid, short=True)}："
                f"{_format_sign_degree(obj.get('sign'), obj.get('signlon'))}"
                f"{_format_retrograde_text(obj)}"
            )
    return lines


def _astro_msg_short(value: Any) -> str:
    """上游 astroAiSnapshot `msg()` 的等价：AstroTxtMsg 优先（行星单字 日/月/火…，星座 牡羊…，宫 id 第一宫…）。"""
    return _astro_msg(value, short=True)
