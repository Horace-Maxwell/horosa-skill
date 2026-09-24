"""西占宫主派生单一真值源——移植上游 `astrostudyui/src/utils/wholeSignRulers.js`（Horosa-Public @ 9b74714b，aiExport v57/v58）
与 `astroAiSnapshot.js` 里消费它的两段排版（[主宰星链] 尾块 / [分宫制宫神星表]）。

上游 #79 的教训：[主宰星链] 与 [起盘信息] 的 nR 宫主标记曾各自实现宫主口径，AI 按四分仪宫头定主宰而与整宫制 nR
互相打架。上游 v57 的收口：**宫主/主宰一律按整宫制（自上升星座起算）**，挂在 [主宰星链] 段尾（判读口径行 + 整宫制宫主表）；
「当前分宫制宫头星座宫主表」迁出成独立段 [分宫制宫神星表]（行星力量/角续果/实际落宫口径，不是主宰依据）。
本仓 Python 面凡是要写「宫主/宫神星」的地方一律从这里取，不许再各自算。

与上游同名同序：
- `build_whole_sign_ruler_rows(chart_obj)`：整宫制宫主表 12 行（wholeSignRulers.js:272）。
- `build_house_system_ruler_rows(chart_obj)`：当前分宫制宫神星表（wholeSignRulers.js:292；按 h.id 真宫号排 1..12）。
- `resolve_house_system(chart_obj, fields)`：当前分宫制 {num,label,isAscWholeSign[,fallback]}（wholeSignRulers.js:178）——
  派生盘（后端 houses[].hsysDerived='wholeFromAsc'）标注「整宫(变换后上升)」、极区回退（houses[].hsysFallback）标注
  「<请求宫制>→回退<回退宫制>」、回显文本撞名（hsys 24/8）用盘面自证消歧。
- `build_dispositor_ruler_tail_lines(chart_obj, msg)`：[主宰星链] 链行之后的「判读口径行 + ◆ 整宫制宫主表」
  （astroAiSnapshot.js:1042-1047）。
- `build_house_system_ruler_section_lines(chart_obj, fields, msg)`：[分宫制宫神星表] 段正文（astroAiSnapshot.js:1063-1077；
  上升整宫制盘折叠成一行说明）。

`msg` 由调用方注入，须等价于上游 astroAiSnapshot 的 `msg()`（AstroTxtMsg 优先：行星取单字「日/月/火」，星座「牡羊」，
宫 id「第一宫」）——service 侧即 `_astro_msg(value, short=True)`。

夹具与断言：tests/test_astro_rulers.py 与 tests/test_sync311_chartfamily.py（上游 jest `wholeSignRulers.test.js` /
`astroClassicalSnapshot.test.js` / `astroV2FactEquivalence.test.js` 的夹具与期望逐字照抄）。
"""
from __future__ import annotations

import math
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

# astroAiSnapshot.js:37-39 —— 段内三句定文，逐字。
WHOLE_SIGN_RULERS_HEAD = "◆ 整宫制宫主表(wholeSignRulers)"
RULER_CALIBRE_LINE = (
    "判读口径：宫主/主宰一律按整宫制（自上升星座起算，与[起盘信息]行星后的 nR 宫主标记同源，见下表）；"
    "行星力量、角/续/果与实际落宫按当前分宫制衡量，见[分宫制宫神星表]段。"
)
HOUSE_SYSTEM_RULERS_COLLAPSED = "当前分宫制即整宫制：宫神星表与[主宰星链]段「◆ 整宫制宫主表(wholeSignRulers)」逐行相同，不再重复列出。"

# AstroConst.HOUSE_SYSTEM_OPTIONS → HouseSys（数字宫制 → 选项表标签；键序 0..24 与 JS Object.keys 同）。
HOUSE_SYSTEM_LABELS: dict[str, str] = {
    "0": "整宫制",
    "1": "Alcabitus",
    "2": "Regiomontanus",
    "3": "Placidus",
    "4": "Koch",
    "5": "Vehlow Equal",
    "6": "Polich Page",
    "7": "Sripati",
    "8": "天顶为10宫中点等宫制",
    "9": "Porphyry",
    "10": "Campanus",
    "11": "Equal",
    "12": "Equal MC",
    "13": "Meridian",
    "14": "Horizontal",
    "15": "Morinus",
    "16": "Carter Poli-Equatorial",
    "17": "Sunshine",
    "18": "Sunshine Alternate",
    "19": "Krusinski-Pisa-Goelzer",
    "20": "Pullen SD",
    "21": "Pullen SR",
    "22": "APC Houses",
    "23": "Savard-A",
    "24": "福点整宫制",
}
HSYS_WHOLE_SIGN = "Whole Sign"   # AstroConst.HSYS_Whole_Sign
HSYS_ALCABITUS = "Alcabitus"     # AstroConst.HSYS_Alcabitus
# wholeSignRulers.js:147 —— flatlib 内部拼写（极区回退标记/盘级回显用它）的显式别名。
_FLATLIB_HSYS_ALIAS: dict[str, str] = {"Porphyrius": "Porphyry", "Azimuthal": "Horizontal"}
# AstroText.AstroMsg[HSYS_*]（AstroText.js:316-339）：上游 msg(label) 对回显文本/选项标签的译名。
_HSYS_ASTRO_MSG: dict[str, str] = {
    "Whole Sign": "整宫制",
    "Alcabitus": "Alcabitus",
    "Regiomontanus": "Regiomontanus",
    "Placidus": "Placidus",
    "Koch": "Koch",
    "Vehlow Equal": "Vehlow Equal",
    "Polich Page": "Polich Page",
    "Sripati": "Sripati",
    "Porphyrius": "Porphyry",
    "Campanus": "Campanus",
    "Equal": "Equal",
    "Equal MC": "Equal MC",
    "Meridian": "Meridian",
    "Azimuthal": "Horizontal",
    "Morinus": "Morinus",
    "Carter Poli-Equatorial": "Carter Poli-Equatorial",
    "Sunshine": "Sunshine",
    "Sunshine Alternate": "Sunshine Alternate",
    "Krusinski-Pisa-Goelzer": "Krusinski-Pisa-Goelzer",
    "Pullen SD": "Pullen SD",
    "Pullen SR": "Pullen SR",
    "APC Houses": "APC Houses",
    "Savard-A": "Savard-A",
    "Fortuna_Whole": "福点整宫制",
}
# wholeSignRulers.js:167 —— 派生盘（调波/龙盘/十三分/十二分）宫位被后端强制为「变换后上升整宫」。
DERIVED_WHOLE_SIGN_LABEL = "整宫(变换后上升)"
_DERIVED_HOUSE_MODE = "wholeFromAsc"   # 后端 thirteenthchart.py DERIVED_HOUSE_MODE


def js_template_str(value: Any) -> str:
    """JS 模板串 `${v}` 的 Python 等价（仅本模块用到的标量形态）：bool → true/false、整值浮点去 .0。"""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return str(int(value))
    return f"{value}"


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


def _house_system_num_of_text(text: Any) -> str | None:
    """wholeSignRulers.js:119 houseSystemNumOfText：后端回显文本 → 数字宫制；认不出 → None（不折叠的安全方向）。"""
    if text is None or text == "":
        return None
    t = js_template_str(text).strip()
    if t in (HSYS_WHOLE_SIGN, "整宫制"):
        return "0"
    if t in ("Alcabitius", HSYS_ALCABITUS):
        return "1"
    for key, label in HOUSE_SYSTEM_LABELS.items():
        if label == t:
            return key
    alias = _FLATLIB_HSYS_ALIAS.get(t)
    if alias:
        for key, label in HOUSE_SYSTEM_LABELS.items():
            if label == alias:
                return key
    return None


def _field_value(fields: Any, key: str) -> Any:
    """wholeSignRulers.js:149 fieldValue：fields[key] 为 {value} 形取 .value，否则取原值。"""
    if not isinstance(fields, dict) or not fields:
        return None
    field = fields.get(key)
    if isinstance(field, dict) and "value" in field:
        return field.get("value")
    return field


def derived_whole_sign_label_of(chart: Any) -> str:
    """wholeSignRulers.js:168：任一宫带 hsysDerived='wholeFromAsc' → 「整宫(变换后上升)」，否则 ''。"""
    houses = chart.get("houses") if isinstance(chart, dict) else None
    for house in houses if isinstance(houses, list) else []:
        if isinstance(house, dict) and house.get("hsysDerived") == _DERIVED_HOUSE_MODE:
            return DERIVED_WHOLE_SIGN_LABEL
    return ""


def house_system_fallback_of(chart: Any) -> str:
    """wholeSignRulers.js:210：极区回退标记 houses[].hsysFallback → 选项表标签；认不出原样返回；无 → ''。"""
    houses = chart.get("houses") if isinstance(chart, dict) else None
    for house in houses if isinstance(houses, list) else []:
        fallback = house.get("hsysFallback") if isinstance(house, dict) else None
        if fallback:
            num = _house_system_num_of_text(fallback)
            return (HOUSE_SYSTEM_LABELS.get(num, "") if num is not None else "") or js_template_str(fallback)
    return ""


def _js_number(house: dict[str, Any]) -> float | None:
    """`Number(h.size)` 的有限值判定：缺键 → NaN（None）；显式 null → 0（JS Number(null) === 0）。"""
    if "size" not in house:
        return None
    raw = house.get("size")
    if raw is None:
        return 0.0
    if isinstance(raw, bool):
        return 1.0 if raw else 0.0
    try:
        number = float(raw)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _disambiguate_echo_num(chart_obj: Any, num: str | None) -> str | None:
    """wholeSignRulers.js:226：数字位缺失时回显文本的撞名消歧（'Whole Sign'→24 / 'Alcabitus'→8 用盘面自证）。"""
    if num not in ("0", "1"):
        return num
    houses = _chart(chart_obj).get("houses")
    houses = houses if isinstance(houses, list) else []
    if num == "0":
        asc_sign = resolve_asc_sign(chart_obj)
        house1 = _house_by_id(chart_obj, "House1")
        h1_sign = _object_sign(house1) if house1 else None
        if asc_sign and h1_sign and h1_sign != asc_sign:
            return "24"
        return num
    sizes = [_js_number(house) if isinstance(house, dict) else None for house in houses]
    if len(sizes) == 12 and all(size is not None and abs(size - 30) < 0.01 for size in sizes):
        return "8"
    return num


def resolve_house_system(chart_obj: Any, fields: Any) -> dict[str, Any]:
    """wholeSignRulers.js:178 resolveHouseSystem：当前分宫制 {num, label, isAscWholeSign}（极区回退时另附 fallback）。

    取值序与 [起盘信息] 同：fields.hsys（发出去的入参）→ params.hsys（请求 echo）→ 反查 chart.hsys 文本；数字位命中即权威。
    """
    chart = _chart(chart_obj)
    params = chart_obj.get("params") if isinstance(chart_obj, dict) and isinstance(chart_obj.get("params"), dict) else {}
    num: str | None = None
    for raw in (_field_value(fields, "hsys"), params.get("hsys")):
        if num is not None:
            break
        if raw is None or raw == "":
            continue
        if js_template_str(raw) in HOUSE_SYSTEM_LABELS:
            num = js_template_str(raw)
    echo_text = js_template_str(chart.get("hsys")) if chart.get("hsys") is not None else ""
    if num is None:
        num = _disambiguate_echo_num(chart_obj, _house_system_num_of_text(echo_text))
    base_label = (HOUSE_SYSTEM_LABELS.get(num, "") if num is not None else "") or echo_text or ""
    fallback = house_system_fallback_of(chart)
    derived_label = derived_whole_sign_label_of(chart)
    label = derived_label or (f"{base_label}→回退{fallback}" if fallback else base_label)
    is_asc_whole_sign = num == "0" if num is not None else echo_text in (HSYS_WHOLE_SIGN, "整宫制")
    resolved: dict[str, Any] = {"num": num, "label": label, "isAscWholeSign": is_asc_whole_sign}
    if fallback:
        resolved["fallback"] = fallback
    return resolved


def hsys_label_msg(label: Any) -> str:
    """上游 astroAiSnapshot `msg(label)` 对宫制标签的译名（AstroMsg[HSYS_*]；认不出原样）。"""
    text = js_template_str(label) if label is not None else ""
    return _HSYS_ASTRO_MSG.get(text, text)


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


def ruler_row_cells(row: dict[str, Any], msg: Callable[[Any], str]) -> list[str]:
    """astroAiSnapshot.js:1053 rulerRowCells：宫主对象整体缺 → '—'；宫主在但缺落宫/落座 → 空串 cell。"""
    if not row.get("rulerFound"):
        return [f"{row['house']}宫", msg(row["sign"]), msg(row["ruler"]), EMPTY_CELL, EMPTY_CELL]
    return [
        f"{row['house']}宫",
        msg(row["sign"]),
        msg(row["ruler"]),
        msg(row["rulerHouseId"]) if row.get("rulerHouseId") else "",
        msg(row["rulerSign"]) if row.get("rulerSign") else "",
    ]


def build_dispositor_ruler_tail_lines(chart_obj: Any, msg: Callable[[Any], str]) -> list[str]:
    """[主宰星链] 链行之后的尾块（astroAiSnapshot.js:1042-1047）：判读口径行 + ◆ 整宫制宫主表；定不出上升座 → []。"""
    rows = build_whole_sign_ruler_rows(chart_obj)
    if not rows:
        return []
    return [
        RULER_CALIBRE_LINE,
        WHOLE_SIGN_RULERS_HEAD,
        *gfm_table_lines(WHOLE_SIGN_RULERS_HEADERS, [ruler_row_cells(row, msg) for row in rows]),
    ]


def build_house_system_ruler_section_lines(chart_obj: Any, fields: Any, msg: Callable[[Any], str]) -> list[str]:
    """[分宫制宫神星表] 段正文（astroAiSnapshot.js:1063-1077）。

    chart.houses 空 → []（不产段）；上升整宫制（hsys 0）且整宫表可出 → 折叠成一行说明；否则
    「◆ 当前分宫制(<label>)宫神星表(houseRows)」+ GFM 表。福点整宫制（24）从福点起算 ≠ 上升整宫制，不折叠。
    """
    rows = build_house_system_ruler_rows(chart_obj)
    if not rows:
        return []
    resolved = resolve_house_system(chart_obj, fields)
    if resolved["isAscWholeSign"] and build_whole_sign_ruler_rows(chart_obj):
        return [HOUSE_SYSTEM_RULERS_COLLAPSED]
    label = hsys_label_msg(resolved["label"]) if resolved["label"] else ""
    return [
        f"◆ 当前分宫制{f'({label})' if label else ''}宫神星表(houseRows)",
        *gfm_table_lines(HOUSE_SYSTEM_RULERS_HEADERS, [ruler_row_cells(row, msg) for row in rows]),
    ]
