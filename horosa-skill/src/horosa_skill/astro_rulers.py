"""西占宫主派生单一真值源（v0.36.0 C6）——移植上游 `astrostudyui/src/utils/wholeSignRulers.js`（Horosa-Public @ 0604fa41）。

上游 #79 的教训：[主宰星链] 与 [起盘信息] 的 nR 宫主标记曾各自实现宫主口径，AI 按四分仪宫头定主宰而与整宫制 nR
互相打架。上游用一个纯函数模块收口；本仓 Python 面凡是要写「宫主/宫神星」的地方一律从这里取，不许再各自算。

三张表（与上游同名同序）：
- `build_whole_sign_ruler_rows(chart_obj)`：整宫制宫主表 12 行（星座自上升座顺数，宫主落宫按整宫制）；定不出上升座 → []。
- `build_house_system_ruler_rows(chart_obj)`：当前分宫制宫神星表（按 chart.houses 宫头座取宫主，落宫 = 后端实际 obj.house）。
  houses 按黄经序返回（House8/9/…），必须从 id 取真宫号再排 1..12（上游 CRASH-1 教训）。
- `build_house_ruler_lines(chart_obj, msg)`：上游 **v56** [主宰星链] 段末的「◆ 宫神星(houseRows)」子块（GFM 表：
  宫|宫头座|宫主|宫主落宫|宫主落座），逐字同形；chart.houses 空 → []。

夹具与断言：tests/test_astro_rulers.py（上游 jest `wholeSignRulers.test.js` 的基线盘与期望逐字照抄）。
"""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

LIST_SIGNS: tuple[str, ...] = (
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
)
# AstroConst.SignsProp[*].Ruler（传统主星）
SIGN_RULERS: dict[str, str] = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury",
    "Libra": "Venus", "Scorpio": "Mars", "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn",
    "Pisces": "Jupiter",
}
WHOLE_SIGN_RULERS_HEADERS: tuple[str, ...] = ("宫", "整宫星座", "宫主", "宫主落宫(整宫)", "宫主落座")
HOUSE_SYSTEM_RULERS_HEADERS: tuple[str, ...] = ("宫", "宫头座", "宫主", "宫主落宫", "宫主落座")
EMPTY_CELL = "—"
_HOUSE_ID = re.compile(r"House\s*(\d+)")


def _norm360(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return ((number % 360) + 360) % 360


def sign_index(sign: Any) -> int:
    if sign is None:
        return -1
    try:
        return LIST_SIGNS.index(f"{sign}")
    except ValueError:
        return -1


def sign_of_lon(lon: Any) -> str | None:
    normalized = _norm360(lon)
    if normalized is None:
        return None
    return LIST_SIGNS[int(normalized // 30) % 12]


def house_num_of_id(house_id: Any) -> int | None:
    match = _HOUSE_ID.search(f"{house_id or ''}")
    if not match:
        return None
    number = int(match.group(1))
    return number if 1 <= number <= 12 else None


def ruler_of_sign(sign: Any) -> str | None:
    return SIGN_RULERS.get(f"{sign}") if sign else None


def _object_sign(obj: Any) -> str | None:
    if not isinstance(obj, dict):
        return None
    if obj.get("sign") and sign_index(obj.get("sign")) >= 0:
        return f"{obj['sign']}"
    if obj.get("lon") is not None:
        return sign_of_lon(obj.get("lon"))
    return None


def _chart(chart_obj: Any) -> dict[str, Any]:
    chart = chart_obj.get("chart") if isinstance(chart_obj, dict) else None
    return chart if isinstance(chart, dict) else {}


def objects_map(chart_obj: Any) -> dict[str, dict[str, Any]]:
    """上游 getObjectsMapPure：chart.objects + 顶层 lots，按 id 索引。"""
    mapping: dict[str, dict[str, Any]] = {}
    for obj in _chart(chart_obj).get("objects") or []:
        if isinstance(obj, dict) and obj.get("id"):
            mapping[f"{obj['id']}"] = obj
    lots = chart_obj.get("lots") if isinstance(chart_obj, dict) else None
    for obj in lots or []:
        if isinstance(obj, dict) and obj.get("id"):
            mapping[f"{obj['id']}"] = obj
    return mapping


def _house_by_id(chart_obj: Any, house_id: str) -> dict[str, Any] | None:
    for house in _chart(chart_obj).get("houses") or []:
        if isinstance(house, dict) and house.get("id") == house_id:
            return house
    return None


def resolve_asc_sign(chart_obj: Any) -> str | None:
    """上升座：Asc.sign → House1.sign → Asc.lon → House1.lon（与上游同序）。"""
    mapping = objects_map(chart_obj)
    asc = mapping.get("Asc")
    if isinstance(asc, dict) and asc.get("sign") and sign_index(asc.get("sign")) >= 0:
        return f"{asc['sign']}"
    house1 = _house_by_id(chart_obj, "House1")
    if house1 and house1.get("sign") and sign_index(house1.get("sign")) >= 0:
        return f"{house1['sign']}"
    if isinstance(asc, dict) and asc.get("lon") is not None:
        sign = sign_of_lon(asc.get("lon"))
        if sign:
            return sign
    if house1 and house1.get("lon") is not None:
        return sign_of_lon(house1.get("lon"))
    return None


def whole_sign_house_of(sign: Any, asc_sign: Any) -> int | None:
    si, ai = sign_index(sign), sign_index(asc_sign)
    if si < 0 or ai < 0:
        return None
    return ((si - ai + 12) % 12) + 1


def _ruler_row(house: int, sign: str, mapping: dict[str, dict[str, Any]], ruler_house_num_of: Callable[[dict[str, Any], str | None], int | None]) -> dict[str, Any] | None:
    ruler = ruler_of_sign(sign)
    if not ruler:
        return None
    ruler_obj = mapping.get(ruler)
    if not ruler_obj:
        return {"house": house, "sign": sign, "ruler": ruler, "rulerFound": False, "rulerHouseNum": None, "rulerHouseId": None, "rulerSign": None}
    ruler_sign = _object_sign(ruler_obj)
    ruler_house_num = ruler_house_num_of(ruler_obj, ruler_sign)
    return {
        "house": house,
        "sign": sign,
        "ruler": ruler,
        "rulerFound": True,
        "rulerHouseNum": ruler_house_num,
        "rulerHouseId": f"House{ruler_house_num}" if ruler_house_num else None,
        "rulerSign": ruler_sign or None,
    }


def build_whole_sign_ruler_rows(chart_obj: Any) -> list[dict[str, Any]]:
    asc_sign = resolve_asc_sign(chart_obj)
    ai = sign_index(asc_sign)
    if ai < 0:
        return []
    mapping = objects_map(chart_obj)
    rows: list[dict[str, Any]] = []
    for house in range(1, 13):
        sign = LIST_SIGNS[(ai + house - 1) % 12]
        row = _ruler_row(house, sign, mapping, lambda _obj, ruler_sign: whole_sign_house_of(ruler_sign, asc_sign))
        if row:
            rows.append(row)
    return rows


def build_house_system_ruler_rows(chart_obj: Any) -> list[dict[str, Any]]:
    houses = _chart(chart_obj).get("houses") or []
    if not houses:
        return []
    mapping = objects_map(chart_obj)
    seeds: list[tuple[int, str]] = []
    for house in houses:
        if not isinstance(house, dict) or not house.get("id"):
            continue
        number = house_num_of_id(house.get("id"))
        sign = _object_sign(house)
        if number and sign:
            seeds.append((number, sign))
    seeds.sort(key=lambda item: item[0])
    rows: list[dict[str, Any]] = []
    for number, sign in seeds:
        row = _ruler_row(number, sign, mapping, lambda obj, _ruler_sign: house_num_of_id(obj.get("house")))
        if row:
            rows.append(row)
    return rows


def gfm_table_lines(headers: tuple[str, ...] | list[str], rows: list[list[str]]) -> list[str]:
    if not rows:
        return []
    return [
        f"| {' | '.join(headers)} |",
        f"| {' | '.join('---' for _ in headers)} |",
        *[f"| {' | '.join(cells)} |" for cells in rows],
    ]


def build_house_ruler_lines(chart_obj: Any, msg: Callable[[Any], str]) -> list[str]:
    """上游 v56 [主宰星链] 段末「◆ 宫神星(houseRows)」子块（逐字同形）。

    上游 v56 只按 `h.sign` 取宫头座（不回退 lon）、宫主对象在但缺落宫/落座 → 空 cell、宫主对象缺 → '—'；
    行序按真宫号 1..12。
    """
    houses = _chart(chart_obj).get("houses") or []
    if not houses:
        return []
    mapping = objects_map(chart_obj)
    seeds: list[tuple[int, str]] = []
    for house in houses:
        if not isinstance(house, dict) or not house.get("sign") or not house.get("id"):
            continue
        number = house_num_of_id(house.get("id"))
        if number:
            seeds.append((number, f"{house['sign']}"))
    seeds.sort(key=lambda item: item[0])
    cells: list[list[str]] = []
    for number, sign in seeds:
        ruler = ruler_of_sign(sign)
        ruler_obj = mapping.get(ruler) if ruler else None
        if ruler and ruler_obj:
            ruler_house = msg(ruler_obj.get("house")) if ruler_obj.get("house") else ""
            ruler_sign = msg(ruler_obj.get("sign")) if ruler_obj.get("sign") else ""
            cells.append([f"{number}宫", msg(sign), msg(ruler), ruler_house, ruler_sign])
        elif ruler:
            cells.append([f"{number}宫", msg(sign), msg(ruler), EMPTY_CELL, EMPTY_CELL])
    if not cells:
        return []
    return ["◆ 宫神星(houseRows)", *gfm_table_lines(("宫", "宫头座", "宫主", "宫主落宫", "宫主落座"), cells)]
