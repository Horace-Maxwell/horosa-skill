"""西占整盘 AI 快照（chart 家族）—— 上游 `utils/astroAiSnapshot.js` buildAstroSnapshotContent 全链的逐字 Python 移植。

上游（Horosa-Public HEAD 9b74714b，`Horosa-Web/astrostudyui/src/`；文件:行 = 该 HEAD）：

- `utils/astroAiSnapshot.js:179-188`   fieldValue
- `utils/astroAiSnapshot.js:327-419`   CLS_CALIBRE_LABELS / CLS_CALIBRE_HEAD_DEFAULTS / buildClassicalCalibreLine
- `utils/astroAiSnapshot.js:422-500`   buildBaseInfoLines（[起盘信息] / [信息] 头部）
- `utils/astroAiSnapshot.js:553-698`   buildInfoSection（[信息]）
- `utils/astroAiSnapshot.js:702-773`   buildAspectSection（[相位]，三子块 GFM 表 + [WP-5b] 扩展对象）
- `utils/astroAiSnapshot.js:780-915`   buildPlanetSection（[行星]，五子块）
- `utils/astroAiSnapshot.js:918-948`   buildLotsSection（[希腊点]）
- `utils/astroAiSnapshot.js:991-1006`  buildDodecaSection（[12分度]，GFM 表）
- `utils/astroAiSnapshot.js:1098-1245` LIFESPAN_KEY_TO_ID / lifespanName / buildLifespanSection（[寿命格局]）
- `utils/astroAiSnapshot.js:1251-1269` buildPossibilitySection / buildSectionText
- `utils/astroAiSnapshot.js:1318-1503` 古典常量表 / buildBesiegementLines / buildEncircleLines / buildPatternOverviewLines /
  buildClassicalSection（[古典]）
- `utils/astroAiSnapshot.js:1505-1689` CLS_LOT_CN … / buildClassicalAnalysisSection（[古典格局]）
- `utils/classicalChartGlobals.js:131-213` classicalBackendOverrides（口径自陈行的「非默认键」单源）
- `utils/classicalParamSpec.js`        CLASSICAL_PARAM_SPEC（send:'nonDefault' 子集；与 vendored JS 由测试互锚）
- `constants/AstroConst.js`            LIST_POINTS / NAK_LORD_CN
- `divination/data/signs.js`           SIGNS[*].cn / body_parts（古典格局 patSignCn、Melothesia）

上游这些函数全是「已算好的 chart 对象 → 文本」的纯排版（AGENTS §5 决策树第 2 类：Python 移植）。名称一律走
`astroextra_snapshots.ai_msg`（= 上游 msg：AstroTxtMsg 单字名优先，行星「日/月/火」、星座「牡羊」、宫「第一宫」），
不用 service 侧的 `_astro_msg`（长名表，[寿命格局] 曾因此印「太阳/火星」）。JS 语义逐条对齐：`Math.round` 是
half-up、`toFixed` 取 double 精确值、`${x}` 的数字按 JS String 出、缺键（undefined）与 null 分开处理。
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from functools import cmp_to_key
from typing import Any

from horosa_skill.astro_rulers import (
    build_dispositor_ruler_tail_lines,
    build_house_system_ruler_section_lines,
    derived_whole_sign_label_of,
    ruler_of_sign,
)
from horosa_skill.engine.astroextra_snapshots import (
    _EMPTY_CELL,
    _UNDEFINED,
    HOUSE_SYS,
    LIST_OBJECTS,
    LIST_SIGNS,
    LOTS,
    ZODIACAL,
    _format_planet_house_info,
    _format_retrograde_text,
    _format_sign_degree,
    _get,
    _gfm_table_lines,
    _js_math_round,
    _js_number,
    _js_str,
    _js_truthy,
    _lon_to_sign_degree,
    _msg_with_house,
    _objects_map,
    _split_degree,
    _zodiacal_display_text,
    ai_msg,
    fmt_num,
)
from horosa_skill.time_basis import build_time_basis_line

msg = ai_msg

# astroAiSnapshot.js:33
PLANET_HOUSE_INFO_NOTE = "说明：行星名后括号中的 nR 为宫主宫位标记；逆行会明确写为“逆行”。"

# constants/AstroConst.js:645-654 LIST_POINTS（[相位]◆标准相位 的主体序；不含希腊点）
LIST_POINTS: tuple[str, ...] = (
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
    "Uranus", "Neptune", "Pluto", "North Node",
    "South Node", "Dark Moon", "Purple Clouds", "Syzygy", "Pars Fortuna",
    "Asc", "Desc", "MC", "IC",
    "Chiron", "Pholus", "Ceres", "Pallas", "Juno", "Vesta",
    "Intp_Apog", "Intp_Perg",
    "MoonSun", "SaturnMars", "JupiterVenus",
    "LifeMasterDeg74",
    "Cupido", "Hades", "Zeus", "Kronos", "Apollon", "Admetos", "Vulcanus", "Poseidon",
)

# constants/AstroConst.js:1215-1218 NAK_LORD_CN（[行星]◆位置与速度 的「月宿」列宿主中文）
NAK_LORD_CN: dict[str, str] = {
    "Ketu": "计都", "Venus": "金星", "Sun": "太阳", "Moon": "月亮", "Mars": "火星",
    "Rahu": "罗睺", "Jupiter": "木星", "Saturn": "土星", "Mercury": "水星",
}

# divination/data/signs.js SIGNS[*].cn —— 古典格局速览 patSignCn（astroAiSnapshot.js:1387）用这张表，
# 不是 AstroTxtMsg（「白羊/处女/水瓶」≠「牡羊/室女/宝瓶」）。
SIGN_CN: dict[str, str] = {
    "aries": "白羊", "taurus": "金牛", "gemini": "双子", "cancer": "巨蟹", "leo": "狮子", "virgo": "处女",
    "libra": "天秤", "scorpio": "天蝎", "sagittarius": "射手", "capricorn": "摩羯", "aquarius": "水瓶", "pisces": "双鱼",
}
# divination/data/signs.js SIGNS[*].body_parts（bodyParts.js bodyPartsOf）
SIGN_BODY_PARTS: dict[str, tuple[str, ...]] = {
    "aries": ("头", "脸", "眼", "鼻", "耳"), "taurus": ("喉", "颈", "甲状腺"),
    "gemini": ("手臂", "肩", "肺", "神经", "气管"), "cancer": ("胃", "胸", "子宫", "卵巢", "牙"),
    "leo": ("心脏", "脊椎", "背", "脊髓"), "virgo": ("小肠", "胰", "脾", "腹", "十二指肠"),
    "libra": ("下背", "肾", "静脉", "卵巢"), "scorpio": ("生殖", "排泄", "结肠", "膀胱", "摄护腺"),
    "sagittarius": ("大腿", "臀", "坐骨神经", "肝", "动脉"), "capricorn": ("膝", "关节", "胆囊", "头发", "皮肤"),
    "aquarius": ("小腿", "踝", "血液循环", "脊髓"), "pisces": ("脚掌", "淋巴"),
}


# ─────────────────────────────── JS 语义小工具 ───────────────────────────────


def field_value(fields: Any, key: str) -> Any:
    """astroAiSnapshot.js:179-188 fieldValue：fields 为假 → null；键缺 → null；wrapper `{value}` → value；否则原值。

    skill 的 fields 是扁平请求体（上游页面/挂载是 wrapper 形），两形在此同口径。返回 None = JS null（永不回 undefined）。
    """
    if not isinstance(fields, dict):
        return None
    if key not in fields:
        return None
    f = fields[key]
    if isinstance(f, dict) and "value" in f:
        return f["value"]
    return f


def _is_nan(value: float) -> bool:
    return isinstance(value, float) and math.isnan(value)


def round3(value: Any) -> str:
    """astroAiSnapshot.js:103-108：undefined/null/NaN → ''；否则 `${Math.round(Number(v) * 1000) / 1000}`。"""
    if value is _UNDEFINED or value is None:
        return ""
    num = _js_number(value)
    if not math.isfinite(num):
        return "" if math.isnan(num) else _js_str(num)
    return _js_str(_js_math_round(num * 1000) / 1000)


def aspect_text(asp: Any) -> str:
    """astroAiSnapshot.js:302-311：数值相位 → `${n}˚`；非数值原样。"""
    if asp is _UNDEFINED or asp is None:
        return ""
    num = _js_number(asp)
    if _is_nan(num):
        return _js_str(asp)
    return f"{_js_str(num)}˚"


def _js_gt(a: Any, b: Any) -> bool:
    """JS `a > b`（数值上下文：null→0、undefined→NaN，NaN 参与恒 false）。"""
    x, y = _js_number(a), _js_number(b)
    if math.isnan(x) or math.isnan(y):
        return False
    return x > y


def _js_lt(a: Any, b: Any) -> bool:
    x, y = _js_number(a), _js_number(b)
    if math.isnan(x) or math.isnan(y):
        return False
    return x < y


def _js_or_zero(value: Any) -> float:
    """JS `(v || 0)` 再参与减法。"""
    if not _js_truthy(value):
        return 0.0
    num = _js_number(value)
    return num


def _js_len(value: Any) -> int:
    if isinstance(value, (list, tuple, str)):
        return len(value)
    return 0


def _js_parse_int(value: Any) -> float:
    """JS `parseInt(`${v}`, 10)`：去前导空白、可选符号、取前导十进制数字；取不到 → NaN。"""
    text = _js_str(value).lstrip()
    m = re.match(r"[+-]?\d+", text)
    if not m:
        return math.nan
    return float(int(m.group(0)))


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def fmt_num_safe(value: Any) -> str:
    """astroAiSnapshot.js:1320 fmtNumSafe：有限数 → `${Math.round(n * 100) / 100}`；否则 `${v}`。"""
    num = _js_number(value)
    if not math.isfinite(num):
        return _js_str(value)
    return _js_str(_js_math_round(num * 100) / 100)


def fixed_num(value: Any, digits: int) -> str:
    """astroAiSnapshot.js:1331-1334 fixedNum：`Number(val)`，NaN → ''，否则 toFixed(digits)。"""
    num = _js_number(value)
    if math.isnan(num):
        return ""
    return fmt_num(num, digits)


def section_text(title: str, lines: list[Any]) -> str:
    """astroAiSnapshot.js:1263-1269 buildSectionText：逐行 trim、去空行；全空 → ''（不产段）。"""
    clean = [f"{line}".strip() for line in lines or []]
    clean = [line for line in clean if line]
    if not clean:
        return ""
    return "[" + title + "]\n" + "\n".join(clean)


def clean_lines(lines: list[Any]) -> list[str]:
    """buildSectionText 的行清洗（给 service 侧按 (title, body) 装配用）。"""
    return [line for line in (f"{item}".strip() for item in lines or []) if line]


def as_name_list(ids: Any) -> str:
    """astroAiSnapshot.js:246-251 asNameList。"""
    if not _js_truthy(ids) or _js_len(ids) == 0:
        return ""
    return " , ".join(name for name in (msg(item) for item in ids) if name)


def dignity_text(ary: Any) -> str:
    """astroAiSnapshot.js:269-274 dignityText：空 → 游走。"""
    if not _js_truthy(ary) or _js_len(ary) == 0:
        return "游走"
    return "，".join(msg(item) for item in ary)


def ruleship_text(arr: Any) -> str:
    """astroAiSnapshot.js:295-300 ruleshipText。"""
    if not _js_truthy(arr) or _js_len(arr) == 0:
        return ""
    return "+".join(msg(item) for item in arr)


def format_speed(obj: Any) -> str:
    """astroAiSnapshot.js:276-293 formatSpeed。"""
    if not _js_truthy(obj) or not isinstance(obj, dict):
        return ""
    lonspeed = _get(obj, "lonspeed")
    mean = _get(obj, "meanSpeed")
    speed = f"{round3(lonspeed)}度"
    if _js_lt(lonspeed, 0):
        speed += "；逆行"
    delta = abs(_js_or_zero(lonspeed) - _js_or_zero(mean))
    if delta > 1:
        speed += "; 快速" if _js_gt(lonspeed, mean) else "; 慢速"
    elif _js_lt(lonspeed, 0.003) and _js_gt(lonspeed, 0):
        speed += "; 停滞"
    else:
        speed += "; 平均"
    return speed


def stars_map(chart_obj: Any) -> dict[str, list[Any]]:
    """astroAiSnapshot.js:256-267 getStarsMap。"""
    chart = _as_dict(chart_obj.get("chart")) if isinstance(chart_obj, dict) else {}
    mapping: dict[str, list[Any]] = {}
    for star in _as_list(chart.get("stars")):
        if isinstance(star, dict):
            mapping[_js_str(star.get("id", _UNDEFINED))] = star.get("stars") or []
    return mapping


def format_stars_lines(stars: Any) -> list[str]:
    """astroAiSnapshot.js:313-325 formatStarsLines：item[4]（后端中文名）优先，否则 msg(item[0])。"""
    lines: list[str] = []
    for item in stars or []:
        if not isinstance(item, (list, tuple)):
            continue
        sname = _js_str(item[4]) if len(item) > 4 else msg(item[0] if item else _UNDEFINED)
        deg = _split_degree(item[2] if len(item) > 2 else _UNDEFINED)
        sign = item[1] if len(item) > 1 else _UNDEFINED
        lines.append(f"{sname}：{abs(deg[0])}˚{msg(sign)}{abs(deg[1])}分")
    return lines


def _msg_house(obj_id: Any, chart_obj: dict[str, Any]) -> str:
    """astroAiSnapshot.js:98-101 msgWithHouse（id 缺 → msg('') 空名，与上游 `${undefined}` 的空串同）。"""
    if obj_id is None or obj_id is _UNDEFINED:
        return ""
    return _msg_with_house(_js_str(obj_id), chart_obj)


# ─────────────────────── 古典口径自陈行（astroAiSnapshot.js:327-419）───────────────────────

# classicalParamSpec.js CLASSICAL_PARAM_SPEC 的 send:'nonDefault' 子集，**上游原序**（classicalBackendOverrides 按此序产键）。
# (key, backendKey|None, valueType, default, defaultAliases, options|None)。与 vendored JS 由
# tests/test_sync311_chartexport.py::test_classical_param_spec_mirror_matches_vendored_js 逐项互锚。
CLASSICAL_PARAM_SPEC_NON_DEFAULT: tuple[tuple[str, str | None, str, Any, tuple[Any, ...], tuple[Any, ...] | None], ...] = (
    ("termsVariant", None, "int", 0, (), (0, 1, 2, 3, 4)),
    ("geminiBoundEmended", None, "int", 0, (), (0, 1)),
    ("leoBoundFirst", None, "int", 0, (), None),
    ("triplicity", None, "str", "Dorothean", (), ("Dorothean", "Ptolemaic", "PtolemaicWaterVariant")),
    ("dignityDebilities", None, "int", 1, (), None),
    ("almutenTripMode", None, "str", "all", (), ("all", "sectRulerOnly")),
    ("planetaryHourMethod", None, "str", "sunrise", (), ("sunrise", "unequal", "equal24")),
    ("sectBuffer", None, "str", "geo", (), ("geo", "ptolemy5", "apparent")),
    ("westNodeType", None, "str", "mean", (), ("mean", "true")),
    ("nodeExaltation", None, "int", 0, (), None),
    ("cazimiOrb", None, "float", 17 / 60, (), (17 / 60, 16 / 60, 1)),
    ("combustOrb", None, "float", 8.5, (), (8.5, 8, 15)),
    ("combustOwnChariotExempt", None, "int", 0, (), None),
    ("underBeamsOrb", None, "float", 17, (), (17, 15)),
    ("vocMode", None, "str", "classic", ("lilly", "backend"), ("classic", "by_orb", "by_sign_perfect", "by_sign_orb", "kenodromia", "exempt4")),
    ("vocIncludeOuter", None, "int", 0, (), None),
    ("westLilithType", None, "str", "mean", (), ("mean", "true")),
    ("topocentricMoon", None, "int", 0, (), None),
    ("viaCombustaVariant", None, "str", "standard", (), ("standard", "narrow", "scorpioFull", "bothFull")),
    ("lotReversal", None, "int", 1, (), None),
    ("lotsDocReverse", None, "int", 0, (), None),
    ("hermeticLotsReversal", None, "int", 1, (), None),
    ("erosConstruction", None, "str", "paulus", (), ("paulus", "valens")),
    ("lotFortuneVariant", None, "str", "standard", (), ("standard", "moonAboveNight")),
    ("lotFatherCombustAlt", None, "int", 0, (), None),
    ("lotProjection", None, "str", "portion", (), ("portion", "sign")),
    ("orbSystem", None, "str", "perObject", (), ("perObject", "byAspect", "wholeSign", "wholeSignMoiety")),
    ("luminaryOrbBonus", None, "int", 0, (), (0, 10, 20, 30)),
    ("aspectIncludeCusps", None, "int", 0, (), None),
    ("aspectIncludeLots", None, "int", 0, (), None),
    ("aspectIncludeMidpoints", None, "int", 0, (), None),
    ("antisciaOrb", None, "float", 1, (), (0.5, 1, 1.5, 2, 3)),
    ("fixedStarOrbMode", "starOrbMode", "str", "school", (), ("school", "byMagnitude")),
    ("fixedStarOrb", "starOrb", "float", 1, (), (1, 1.5, 2, 3, 5)),
    ("stationMarking", None, "str", "off", (), ("off", "exactWindow", "distance", "absSpeed", "relSpeed")),
    ("solarReturnVariant", None, "str", "precise", (), ("precise", "hellenistic")),
    ("returnLatitudeMode", None, "str", "ecliptic", (), ("ecliptic", "withLatitude")),
    ("houseCuspAdvance", None, "int", 5, (), (5, 3, 1, 0)),
    ("vulcanCalc", None, "str", "off", (), ("off", "weston", "baker")),
)


def classical_backend_overrides(get_val: Callable[[str], Any]) -> dict[str, Any]:
    """classicalChartGlobals.js:152-208 classicalBackendOverrides：只产「非默认」键（float 差 >1e-9 / int 强转 ≠ 默认 /
    str 不等默认且非同义词；值域外脏值不发；vocIncludeOuter 只随非默认且非 exempt4 的 vocMode；termsVariant=4 须随盘
    12 座表体，headless 无本机编辑器仓 → 无表即降级不发 4）。"""
    out: dict[str, Any] = {}
    for key, backend_key, value_type, default, aliases, options in CLASSICAL_PARAM_SPEC_NON_DEFAULT:
        raw = get_val(key)
        if (raw is None or raw is _UNDEFINED or raw == "") and backend_key and backend_key != key:
            raw = get_val(backend_key)
        if raw is None or raw is _UNDEFINED or (isinstance(raw, str) and raw == ""):
            continue
        val: Any
        if value_type == "float":
            num = _js_number(raw)
            if not math.isfinite(num) or not abs(num - float(default)) > 1e-9:
                continue
            val = num
        elif value_type == "int":
            if raw is True:
                num = 1.0
            elif raw is False:
                num = 0.0
            else:
                num = _js_parse_int(raw)
            if not math.isfinite(num) or num == default:
                continue
            val = int(num)
        else:
            val = _js_str(raw)
            if val == default or val in aliases:
                continue
        if options is not None and not any(
            (isinstance(o, str) and isinstance(val, str) and o == val)
            or (not isinstance(o, str) and not isinstance(val, str) and float(o) == float(val))
            for o in options
        ):
            continue
        out[backend_key or key] = val
    if "vocIncludeOuter" in out and ("vocMode" not in out or out["vocMode"] == "exempt4"):
        del out["vocIncludeOuter"]
    if out.get("termsVariant") == 4:
        rec_day = get_val("customTermsDay")
        rec_night = get_val("customTermsNight")
        if isinstance(rec_day, list) and len(rec_day) == 12:
            out["customTermsDay"] = rec_day
            if isinstance(rec_night, list) and len(rec_night) == 12:
                out["customTermsNight"] = rec_night
        else:
            # 上游回落本机编辑器仓（customCalibreStores.loadCustomTerms）；headless 无持久化仓 = 无表 → 降级不发 4。
            del out["termsVariant"]
    return out


def classical_backend_overrides_from_fields(fields: Any) -> dict[str, Any]:
    """classicalChartGlobals.js:211-213 FromFields：wrapper 形 fields 取 `.value`；skill 扁平请求体按同一语义取原值。"""
    def get_val(key: str) -> Any:
        return field_value(fields, key) if isinstance(fields, dict) and key in fields else _UNDEFINED
    return classical_backend_overrides(get_val)


# astroAiSnapshot.js:329-376 CLS_CALIBRE_LABELS：(label, map|None, fmt|None)。map 键 = JS 属性键（`${value}`）。
_CLS_CALIBRE_LABELS: dict[str, tuple[str, dict[str, str] | None, Callable[[Any], str] | None]] = {
    "termsVariant": ("界系", {"1": "托勒密·校勘本", "2": "托勒密·经典传本", "3": "迦勒底(推演)", "4": "自定义界表"}, None),
    "geminiBoundEmended": ("双子界序", {"1": "校勘对调"}, None),
    "leoBoundFirst": ("狮子首界", {"1": "土星优先"}, None),
    "triplicity": ("三分集", {"Ptolemaic": "托勒密二主", "PtolemaicWaterVariant": "托勒密·水象变体"}, None),
    "westNodeType": ("月交点", {"true": "真交点"}, None),
    "sectBuffer": ("区分判定", {"ptolemy5": "Ptolemy 5°缓冲", "apparent": "视地平(含折射)"}, None),
    "lotReversal": ("福点", {"0": "恒昼式(不随昼夜反转)"}, None),
    "houseCuspAdvance": ("落宫宫头前移", None, lambda v: f"{_js_str(v)}°"),
    "cazimiOrb": ("日心 cazimi", None, lambda v: f"{_js_str(_js_math_round(_js_number(v) * 60))}′"),
    "combustOrb": ("燃烧上界", None, lambda v: f"{_js_str(v)}°"),
    "underBeamsOrb": ("日光束外界", None, lambda v: f"{_js_str(v)}°"),
    "vocMode": ("空亡口径", {"by_orb": "容许度12°30′", "by_sign_perfect": "本座内须完成(现代)", "by_sign_orb": "本座内入容许度(16c)", "kenodromia": "30°法(希腊化)", "exempt4": "无入相+四座豁免(中世纪)"}, None),
    "vocIncludeOuter": ("空亡计三王星", {"1": "开"}, None),
    "fixedStarOrb": ("恒星平轨", None, lambda v: f"{_js_str(v)}°"),
    "fixedStarOrbMode": ("恒星轨档", {"byMagnitude": "按星等"}, None),
    "antisciaOrb": ("映点容许度", None, lambda v: f"{_js_str(v)}°"),
    "viaCombustaVariant": ("燃烧之路", {"narrow": "窄口径(天秤28°–天蝎7°)", "scorpioFull": "天秤后15°+天蝎全宫", "bothFull": "天秤+天蝎全段"}, None),
    "lotsDocReverse": ("四点文档序公式", {"1": "开"}, None),
    "nodeExaltation": ("交点入旺", {"1": "开"}, None),
    "combustOwnChariotExempt": ("免燃烧例外", {"1": "界内三分内免(own chariot)"}, None),
    "westLilithType": ("黑月", {"true": "真实远地点"}, None),
    "topocentricMoon": ("月亮视差", {"1": "站心修正"}, None),
    "stationMarking": ("留驻判定", {"exactWindow": "距留点≤1日", "distance": "距留点≤2′", "absSpeed": "日速<1′", "relSpeed": "日速<3%均速"}, None),
    "hermeticLotsReversal": ("七星点", {"0": "恒同式(批判本校勘)"}, None),
    "erosConstruction": ("爱欲·必然构成", {"valens": "Valens 式(福点·精神系)"}, None),
    "lotFortuneVariant": ("福点变体", {"moonAboveNight": "月在地平上恒夜式"}, None),
    "lotFatherCombustAlt": ("父点", {"1": "土星伏替代式(Dorotheus 系)"}, None),
    "lotProjection": ("点度计数", {"sign": "整星座投射"}, None),
    "dignityDebilities": ("弱陷负分", {"0": "不计负分"}, None),
    "almutenTripMode": ("Almuten 三分", {"sectRulerOnly": "仅当值主"}, None),
    "planetaryHourMethod": ("行星时", {"unequal": "昼夜不等时(传统)", "equal24": "廿四时等分"}, None),
    "orbSystem": ("容许度体系", {"byAspect": "按相位名", "wholeSign": "整星座位相", "wholeSignMoiety": "整星座内半距和"}, None),
    "luminaryOrbBonus": ("发光体·四轴加成", None, lambda v: f"{_js_str(v)}%"),
    "aspectIncludeCusps": ("宫头相位", {"1": "开(≤3°)"}, None),
    "aspectIncludeLots": ("点位相位", {"1": "开(受体·≤3°)"}, None),
    "aspectIncludeMidpoints": ("中点相位", {"1": "开(日月四轴·硬相≤1.5°)"}, None),
    "solarReturnVariant": ("太阳返照法", {"hellenistic": "希腊式(月定上升)"}, None),
    "returnLatitudeMode": ("返照落宫", {"withLatitude": "计入黄纬(Umar al-Tabari 法)"}, None),
    "vulcanCalc": ("祝融星", {"weston": "轨道根数法", "baker": "水星系推算"}, None),
}
# astroAiSnapshot.js:378-381 头七键默认值（数值键只 0/1 两档按 parseInt 比）。
_CLS_CALIBRE_HEAD_DEFAULTS: dict[str, Any] = {
    "termsVariant": 0, "geminiBoundEmended": 0, "leoBoundFirst": 0, "triplicity": "Dorothean",
    "westNodeType": "mean", "sectBuffer": "geo", "lotReversal": 1,
}


def _calibre_phrase(key: str, value: Any) -> str:
    """astroAiSnapshot.js:383-389 classicalCalibrePhrase。"""
    spec = _CLS_CALIBRE_LABELS.get(key)
    if spec is None:
        return f"{key}={_js_str(value)}"
    label, mapping, fmt = spec
    if mapping is not None and _js_str(value) in mapping:
        return f"{label}={mapping[_js_str(value)]}"
    if fmt is not None:
        return f"{label}={fmt(value)}"
    return f"{label}={_js_str(value)}"


def build_classical_calibre_line(fields: Any) -> str:
    """astroAiSnapshot.js:391-419 buildClassicalCalibreLine：只列非默认键；全默认 → ''（零增行）。"""
    parts: list[str] = []
    for key, default in _CLS_CALIBRE_HEAD_DEFAULTS.items():
        value = field_value(fields, key)
        if value is None:
            continue
        if default in (0, 1) and not isinstance(default, bool):
            norm: Any = _js_parse_int(value)
            if math.isnan(norm):
                continue
            norm = int(norm)
        else:
            norm = _js_str(value)
        if norm != default:
            parts.append(_calibre_phrase(key, norm))
    overrides = classical_backend_overrides_from_fields(fields)
    custom_terms_noted = False
    for key, value in overrides.items():
        if key in _CLS_CALIBRE_HEAD_DEFAULTS:
            continue
        if key in ("customTermsDay", "customTermsNight"):
            if not custom_terms_noted:
                parts.append("界表=自定义(编辑器存表)")
                custom_terms_noted = True
            continue
        if key in ("userAyanT0", "userAyanDeg"):
            continue
        front = "fixedStarOrb" if key == "starOrb" else ("fixedStarOrbMode" if key == "starOrbMode" else key)
        parts.append(_calibre_phrase(front, value))
    if not parts:
        return ""
    return f"古典口径（非默认项）：{'；'.join(parts)}。"


# ─────────────────────── [起盘信息] / [信息]（astroAiSnapshot.js:422-698）───────────────────────


def _day_boundary_bit(value: Any) -> int:
    """astroAiSnapshot.js:449-450：0 / '0' / false → 0；其余（含 null）→ 1。"""
    if value is False or (isinstance(value, str) and value == "0"):
        return 0
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value == 0:
        return 0
    return 1


def build_base_info_lines(chart_obj: Any, fields: Any, *, with_time_basis: bool = False) -> list[str]:
    """astroAiSnapshot.js:422-500 buildBaseInfoLines。

    [V6-W2]（:457-467）宫制/黄道取值源 = 「请求参数优先、后端 echo 兜底」：fields 数字值就是发出去的排盘入参，
    标注与计算恒同源（echo 优先时 hsys 8/24 的回显与 1/0 撞名 → 标注撒谎）。派生盘宫位被后端强制成变换后上升整宫
    （houses[].hsysDerived）→ derivedWholeSignLabelOf 最先。
    """
    lines: list[str] = []
    obj = chart_obj if isinstance(chart_obj, dict) else {}
    chart = obj.get("chart") if _js_truthy(obj.get("chart")) and isinstance(obj.get("chart"), dict) else {}
    params = obj.get("params") if _js_truthy(obj.get("params")) and isinstance(obj.get("params"), dict) else {}
    lon = field_value(fields, "lon")
    if not _js_truthy(lon):
        lon = params.get("lon") if _js_truthy(params.get("lon")) else ""
    lat = field_value(fields, "lat")
    if not _js_truthy(lat):
        lat = params.get("lat") if _js_truthy(params.get("lat")) else ""
    zone = params.get("zone") if params.get("zone") is not None else field_value(fields, "zone")
    if _js_truthy(lon) or _js_truthy(lat):
        lines.append(f"经度：{_js_str(lon)}， 纬度：{_js_str(lat)}")
    if _js_truthy(params.get("birth")):
        dayofweek = chart.get("dayofweek")
        lines.append(_js_str(params["birth"]) + (f" {_js_str(dayofweek)}" if _js_truthy(dayofweek) else ""))
    if zone is not None:
        lines.append(f"时区：{_js_str(zone)} ，{'日生盘' if _js_truthy(chart.get('isDiurnal')) else '夜生盘'}")
    nongli = chart.get("nongli")
    if isinstance(nongli, dict) and _js_truthy(nongli.get("birth")):
        lines.append(f"真太阳时：{_js_str(nongli['birth'])}")
    if with_time_basis:
        lines.append(
            build_time_basis_line(
                time_alg=1,
                late_zi_hour_use_next_day=field_value(fields, "lateZiHourUseNextDay"),
                after23_new_day=field_value(fields, "after23NewDay"),
            )
        )
    # 用户拍板·v2.2.1（:446-455）：fieldValue 永不回 undefined（缺键 → null），故本行恒出；null 按 1 计。
    a23 = _day_boundary_bit(field_value(fields, "after23NewDay"))
    lzh = _day_boundary_bit(field_value(fields, "lateZiHourUseNextDay"))
    day_label = "23点算第二天(日柱进位次日)" if a23 == 1 else "24点算第二天(日柱守今、24点才换日柱)"
    hour_label = "晚子时按次日日柱计算(时干用次日日干起子时)" if lzh == 1 else "晚子时按当日柱计算(时干用今日日干起子时)"
    lines.append(f"排盘规则：日柱开关【{day_label}】+ 时柱开关【{hour_label}】。本盘四柱按此规则计算。")
    zodiacal = ZODIACAL.get(_js_str(field_value(fields, "zodiacal"))) or chart.get("zodiacal")
    hsys = derived_whole_sign_label_of(chart) or HOUSE_SYS.get(_js_str(field_value(fields, "hsys"))) or chart.get("hsys")
    if _js_truthy(zodiacal) or _js_truthy(hsys):
        ayan_key = field_value(fields, "siderealAyanamsa")
        if not _js_truthy(ayan_key):
            ayan_key = chart.get("siderealAyanamsa") if _js_truthy(chart.get("siderealAyanamsa")) else ""
        zodiacal_txt = _zodiacal_display_text(zodiacal, ayan_key) if _js_truthy(zodiacal) else msg(zodiacal)
        lines.append(f"{zodiacal_txt}，{msg(hsys)}")
    calibre = build_classical_calibre_line(fields)
    if calibre:
        lines.append(calibre)
    lines.append(PLANET_HOUSE_INFO_NOTE)
    if _js_truthy(chart.get("dayerStar")):
        lines.append(f"日主星：{msg(chart['dayerStar'])}")
    if _js_truthy(chart.get("timerStar")):
        lines.append(f"时主星：{msg(chart['timerStar'])}")
    # FIX-16（:484-495）命主星：上升落座 → 庙主（wholeSignRulers.rulerOfSign 单源 = astro_rulers.ruler_of_sign）→ 该星落宫/落座。
    object_map = _objects_map(obj)
    asc = object_map.get("Asc")
    if isinstance(asc, dict) and _js_truthy(asc.get("sign")):
        ruler_id = ruler_of_sign(asc.get("sign"))
        ruler_obj = object_map.get(ruler_id) if ruler_id else None
        if ruler_obj:
            house_part = f"落{msg(ruler_obj['house'])}" if _js_truthy(ruler_obj.get("house")) else ""
            sign_part = f"（{msg(ruler_obj['sign'])}）" if _js_truthy(ruler_obj.get("sign")) else ""
            lines.append(f"命主星：{msg(ruler_id)} {house_part}{sign_part}")
    return lines


def _has_ruler_or_exalt(ary: Any) -> bool:
    return isinstance(ary, list) and any(item in ("ruler", "exalt") for item in ary)


def _keep_reception_line(item: Any, *, abnormal: bool, only_ruler_exalt: bool) -> bool:
    """astroAiSnapshot.js:221-234 keepReceptionLine。"""
    if not only_ruler_exalt:
        return True
    if not _js_truthy(item) or not isinstance(item, dict):
        return False
    supplier_ok = _has_ruler_or_exalt(item.get("supplierRulerShip"))
    if not abnormal:
        return supplier_ok
    return supplier_ok or _has_ruler_or_exalt(item.get("beneficiaryDignity"))


def _keep_mutual_line(item: Any, *, only_ruler_exalt: bool) -> bool:
    """astroAiSnapshot.js:236-244 keepMutualLine。"""
    if not only_ruler_exalt:
        return True
    if not isinstance(item, dict) or not isinstance(item.get("planetA"), dict) or not isinstance(item.get("planetB"), dict):
        return False
    return _has_ruler_or_exalt(item["planetA"].get("rulerShip")) and _has_ruler_or_exalt(item["planetB"].get("rulerShip"))


def _is_reject(item: Any) -> bool:
    """astroAiSnapshot.js:576-581 isReject：supplier 在 beneficiary 所在座为 exile/fall。"""
    dig = item.get("supplierRulerShip") if isinstance(item, dict) else None
    if not _js_truthy(dig):
        return False
    arr = dig if isinstance(dig, list) else [dig]
    return any(d in ("exile", "fall") for d in arr)


def build_info_section(chart_obj: Any, fields: Any, *, only_ruler_exalt: bool = False) -> list[str]:
    """astroAiSnapshot.js:553-698 buildInfoSection（[信息]）：基础行（不带时间基准）+ 映点/接纳/互容/围攻/夹宫/夹星/纬照。"""
    obj = chart_obj if isinstance(chart_obj, dict) else {}
    chart = obj.get("chart") if isinstance(obj.get("chart"), dict) else {}
    lines = build_base_info_lines(obj, fields)

    anti = _as_dict(chart.get("antiscias"))
    anti_lines: list[str] = []

    def at(item: Any, idx: int) -> Any:
        return item[idx] if isinstance(item, (list, tuple)) and len(item) > idx else _UNDEFINED

    for item in _as_list(anti.get("antiscia")):
        anti_lines.append(f"{msg(at(item, 0))} 与 {msg(at(item, 1))} 成映点 误差{round3(at(item, 2))}")
    for item in _as_list(anti.get("cantiscia")):
        anti_lines.append(f"{msg(at(item, 0))} 与 {msg(at(item, 1))} 成反映点 误差{round3(at(item, 2))}")
    if anti_lines:
        lines.append("映点/反映点")
        lines.extend(anti_lines)

    receptions = _as_dict(obj.get("receptions"))
    normal = [i for i in _as_list(receptions.get("normal")) if _keep_reception_line(i, abnormal=False, only_ruler_exalt=only_ruler_exalt)]
    abnormal = [i for i in _as_list(receptions.get("abnormal")) if _keep_reception_line(i, abnormal=True, only_ruler_exalt=only_ruler_exalt)]
    if normal or abnormal:
        lines.append("接纳")
        lines.append("正接纳：")
        for item in normal:
            item = _as_dict(item)
            rej = "（拒绝）" if _is_reject(item) else ""
            lines.append(
                f"{_msg_house(item.get('beneficiary'), obj)} 被 {_msg_house(item.get('supplier'), obj)} 接纳 "
                f"({ruleship_text(item.get('supplierRulerShip'))}){rej}"
            )
        lines.append("邪接纳：")
        for item in abnormal:
            item = _as_dict(item)
            rej = "（拒绝）" if _is_reject(item) else ""
            lines.append(
                f"{_msg_house(item.get('beneficiary'), obj)} ({ruleship_text(item.get('beneficiaryDignity'))}) 被 "
                f"{_msg_house(item.get('supplier'), obj)} 接纳 ({ruleship_text(item.get('supplierRulerShip'))}){rej}"
            )

    mutuals = _as_dict(obj.get("mutuals"))
    normal_m = [i for i in _as_list(mutuals.get("normal")) if _keep_mutual_line(i, only_ruler_exalt=only_ruler_exalt)]
    abnormal_m = [i for i in _as_list(mutuals.get("abnormal")) if _keep_mutual_line(i, only_ruler_exalt=only_ruler_exalt)]

    def mutual_line(item: Any) -> str:
        a = _as_dict(_as_dict(item).get("planetA"))
        b = _as_dict(_as_dict(item).get("planetB"))
        return (
            f"{_msg_house(a.get('id'), obj)} ({ruleship_text(a.get('rulerShip'))}) 与 "
            f"{_msg_house(b.get('id'), obj)} ({ruleship_text(b.get('rulerShip'))}) 互容"
        )

    if normal_m or abnormal_m:
        lines.append("互容")
        lines.append("正互容：")
        lines.extend(mutual_line(item) for item in normal_m)
        lines.append("邪互容：")
        lines.extend(mutual_line(item) for item in abnormal_m)

    surround = _as_dict(obj.get("surround"))
    attack_lines: list[str] = []
    for key, planet in _as_dict(surround.get("attacks")).items():
        planet = _as_dict(planet)
        candidates = [
            planet[k] for k in ("MinDelta", "MarsSaturn", "SunMoon", "VenusJupiter")
            if isinstance(planet.get(k), list) and len(planet[k]) == 2
        ]
        for pair in candidates:
            p0, p1 = _as_dict(pair[0]), _as_dict(pair[1])
            attack_lines.append(
                f"{_msg_house(key, obj)} 被 {_msg_house(p0.get('id'), obj)} (通过{aspect_text(p0.get('aspect', _UNDEFINED))}相位) 与 "
                f"{_msg_house(p1.get('id'), obj)} (通过{aspect_text(p1.get('aspect', _UNDEFINED))}相位) 围攻"
            )
    if attack_lines:
        lines.append("光线围攻")
        lines.extend(attack_lines)

    house_lines: list[str] = []
    for key, pair in _as_dict(surround.get("houses")).items():
        if isinstance(pair, list) and len(pair) == 2:
            house_lines.append(f"{_msg_house(_as_dict(pair[0]).get('id'), obj)} 与 {_msg_house(_as_dict(pair[1]).get('id'), obj)} 夹 {msg(key)}")
    if house_lines:
        lines.append("夹宫")
        lines.extend(house_lines)

    planet_lines: list[str] = []
    for key, pair in _as_dict(surround.get("planets")).items():
        if key == "BySunMoon" and isinstance(pair, dict) and _js_truthy(pair.get("id")):
            planet_lines.append(f"{_msg_house('Moon', obj)} 与 {_msg_house('Sun', obj)} 夹 {_msg_house(pair['id'], obj)}")
            continue
        if isinstance(pair, dict) and isinstance(pair.get("SunMoon"), list) and len(pair["SunMoon"]) == 2:
            sm = pair["SunMoon"]
            planet_lines.append(f"{_msg_house(_as_dict(sm[0]).get('id'), obj)} 与 {_msg_house(_as_dict(sm[1]).get('id'), obj)} 夹 {_msg_house(key, obj)}")
            continue
        if isinstance(pair, list) and len(pair) == 2:
            planet_lines.append(f"{_msg_house(_as_dict(pair[0]).get('id'), obj)} 与 {_msg_house(_as_dict(pair[1]).get('id'), obj)} 夹 {_msg_house(key, obj)}")
    if planet_lines:
        lines.append("夹星")
        lines.extend(planet_lines)

    decl = _as_dict(obj.get("declParallel"))
    parallel_lines: list[str] = []
    for idx, ids in enumerate(_as_list(decl.get("parallel")), start=1):
        parallel_lines.append(f"平行星体{idx}：{as_name_list(ids)}")
    for obj_id, ids in _as_dict(decl.get("contraParallel")).items():
        if _js_len(ids or []):
            parallel_lines.append(f"相对 {msg(obj_id)} 星体：{as_name_list(ids)}")
    if parallel_lines:
        lines.append("纬照")
        lines.extend(parallel_lines)
    return lines


# ─────────────────────── [宫位宫头] / [星与虚点] / [相位] / [行星] / [希腊点] ───────────────────────


def build_house_cusp_lines(chart_obj: Any) -> list[str]:
    """astroAiSnapshot.js:521-533（宫位|宫头 表）。"""
    obj = chart_obj if isinstance(chart_obj, dict) else {}
    chart = obj.get("chart") if isinstance(obj.get("chart"), dict) else {}
    rows: list[list[str]] = []
    for house in _as_list(chart.get("houses")):
        if not isinstance(house, dict) or house.get("lon") is None:
            continue
        rows.append([msg(house.get("id", _UNDEFINED)), _lon_to_sign_degree(house.get("lon"))])
    return _gfm_table_lines(["宫位", "宫头"], rows)


def build_star_and_lot_position_lines(chart_obj: Any) -> list[str]:
    """astroAiSnapshot.js:535-551（点位|位置|逆行 表；LIST_OBJECTS 后接 LOTS）。"""
    obj = chart_obj if isinstance(chart_obj, dict) else {}
    object_map = _objects_map(obj)
    rows: list[list[str]] = []
    for obj_id in (*LIST_OBJECTS, *LOTS):
        item = object_map.get(obj_id)
        if not isinstance(item, dict) or "sign" not in item or "signlon" not in item:
            continue
        rows.append([_msg_house(obj_id, obj), _format_sign_degree(item.get("sign"), item.get("signlon")), _format_retrograde_text(item) or _EMPTY_CELL])
    return _gfm_table_lines(["点位", "位置", "逆行"], rows)


def build_aspect_section(chart_obj: Any) -> list[str]:
    """astroAiSnapshot.js:702-773：◆标准相位（LIST_POINTS 主体，相态 入相/正合/离相/—）◆立即相位 ◆星座相位 + [WP-5b] 扩展。"""
    obj = chart_obj if isinstance(chart_obj, dict) else {}
    aspects = _as_dict(obj.get("aspects"))
    normal = _as_dict(aspects.get("normalAsp"))
    immediate = _as_dict(aspects.get("immediateAsp"))
    sign_asp = _as_dict(aspects.get("signAsp"))
    lines: list[str] = []

    normal_rows: list[list[str]] = []
    for obj_id in LIST_POINTS:
        one = normal.get(obj_id)
        if not _js_truthy(one) or not isinstance(one, dict):
            continue
        subject = _msg_house(obj_id, obj)
        for key, state in (("Applicative", "入相"), ("Exact", "正合"), ("Separative", "离相"), ("None", _EMPTY_CELL)):
            for asp in _as_list(one.get(key)):
                asp = _as_dict(asp)
                normal_rows.append([subject, aspect_text(asp.get("asp", _UNDEFINED)), _msg_house(asp.get("id"), obj), state, round3(asp.get("orb", _UNDEFINED))])
    lines.append("◆ 标准相位")
    lines.extend(_gfm_table_lines(["主体", "相位", "对象", "相态", "误差"], normal_rows))

    immediate_rows: list[list[str]] = []
    for obj_id in LIST_OBJECTS:
        one = immediate.get(obj_id)
        if not isinstance(one, list) or len(one) < 2:
            continue
        subject = _msg_house(obj_id, obj)
        first, second = _as_dict(one[0]), _as_dict(one[1])
        immediate_rows.append([subject, aspect_text(first.get("asp", _UNDEFINED)), _msg_house(first.get("id"), obj), "离相", round3(first.get("orb", _UNDEFINED))])
        immediate_rows.append([subject, aspect_text(second.get("asp", _UNDEFINED)), _msg_house(second.get("id"), obj), "入相", round3(second.get("orb", _UNDEFINED))])
    lines.append("◆ 立即相位")
    lines.extend(_gfm_table_lines(["主体", "相位", "对象", "相态", "误差"], immediate_rows))

    sign_rows: list[list[str]] = []
    for obj_id in LIST_OBJECTS:
        one = sign_asp.get(obj_id)
        if not isinstance(one, list) or not one:
            continue
        subject = _msg_house(obj_id, obj)
        for asp in one:
            asp = _as_dict(asp)
            sign_rows.append([subject, aspect_text(asp.get("asp", _UNDEFINED)), _msg_house(asp.get("id"), obj)])
    lines.append("◆ 星座相位")
    lines.extend(_gfm_table_lines(["主体", "相位", "对象"], sign_rows))

    # [WP-5b]（:757-770）相位参与对象扩展：响应无 extraAspects 字段（默认全关）= 零增行。
    extra = obj.get("extraAspects")
    if isinstance(extra, dict):
        group_cn = {"cusps": "宫头相位(≤3°)", "lots": "点位相位(点为受体·≤3°)", "midpoints": "中点接触(日月四轴·硬相≤1.5°)"}
        for group in ("cusps", "lots", "midpoints"):
            rows = _as_list(extra.get(group))
            if not rows:
                continue
            lines.append(f"◆ {group_cn[group]}")
            lines.extend(_gfm_table_lines(
                ["行星", "相位", "对象", "误差"],
                [
                    [msg(_as_dict(r).get("planet", _UNDEFINED)), aspect_text(_as_dict(r).get("asp", _UNDEFINED)),
                     msg(_as_dict(r).get("target", _UNDEFINED)) or _js_str(_as_dict(r).get("target", _UNDEFINED)),
                     f"{_js_str(_as_dict(r).get('orb', _UNDEFINED))}˚"]
                    for r in rows
                ],
            ))
    return lines


def build_planet_section(chart_obj: Any) -> list[str]:
    """astroAiSnapshot.js:780-915：◆位置与速度 / ◆坐标 / ◆尊贵与主宰 / ◆映点与东西 四表 + ◆汇合恒星 kv 行组。"""
    obj = chart_obj if isinstance(chart_obj, dict) else {}
    chart = obj.get("chart") if isinstance(obj.get("chart"), dict) else {}
    object_map = _objects_map(obj)
    smap = stars_map(obj)
    orient_occident = _as_dict(chart.get("orientOccident"))
    nakshatras = chart.get("nakshatras") if _js_truthy(chart.get("nakshatras")) else (obj.get("nakshatras") if _js_truthy(obj.get("nakshatras")) else {})
    nakshatras = _as_dict(nakshatras)
    pos_rows: list[list[str]] = []
    coord_rows: list[list[str]] = []
    dignity_rows: list[list[str]] = []
    antiscia_rows: list[list[str]] = []
    star_groups: list[tuple[str, list[Any]]] = []

    for obj_id in LIST_OBJECTS:
        item = object_map.get(obj_id)
        if not isinstance(item, dict):
            continue
        name = _msg_house(obj_id, obj)
        # FIX-12（:800-807）落座 cell 内联 29°歧度 / 燃烧之路 / 压抑之路 临界标。
        sign_deg = _format_sign_degree(item.get("sign"), _get(item, "signlon"))
        extras: list[str] = []
        signlon = item.get("signlon")
        if isinstance(signlon, (int, float)) and not isinstance(signlon, bool) and math.isfinite(signlon) and math.floor(signlon) == 29:
            extras.append("位于歧度")
        if _js_truthy(item.get("isViaCombust")):
            extras.append("位于燃烧之路")
        if _js_truthy(item.get("isViaRepression")):
            extras.append("位于压抑之路")
        if extras:
            sign_deg += "；" + "；".join(extras)
        # FIX-7（:808-815）月宿 nakshatra。
        nak = nakshatras.get(obj_id)
        nak_cell = _EMPTY_CELL
        if isinstance(nak, dict) and _js_truthy(nak.get("index")):
            lord = nak.get("lord")
            lord_cn = NAK_LORD_CN.get(_js_str(lord)) if lord is not None else None
            if not lord_cn:
                lord_cn = _js_str(lord) if _js_truthy(lord) else ""
            label = f"（{_js_str(nak['label'])}）" if _js_truthy(nak.get("label")) else ""
            name_txt = _js_str(nak["name"]) if _js_truthy(nak.get("name")) else ""
            pada = _js_str(nak["pada"]) if _js_truthy(nak.get("pada")) else "?"
            nak_cell = f"第{_js_str(nak['index'])}宿 {name_txt}{label} 第{pada}步·宿主{lord_cn}"
        mean = _get(item, "meanSpeed")
        pos_rows.append([
            name,
            sign_deg,
            msg(item["house"]) if _js_truthy(item.get("house")) else _EMPTY_CELL,
            nak_cell,
            round3(mean) if mean is not _UNDEFINED else _EMPTY_CELL,
            format_speed(item) if "lonspeed" in item else _EMPTY_CELL,
        ])

        coord_cells = [
            f"{round3(item[k])}˚" if k in item else _EMPTY_CELL
            for k in ("lon", "lat", "ra", "decl", "altitudeTrue", "altitudeAppa", "azimuth")
        ]
        if any(cell != _EMPTY_CELL for cell in coord_cells):
            coord_rows.append([name, *coord_cells])

        dignity_cell = _EMPTY_CELL
        if _js_truthy(item.get("selfDignity")):
            dg = dignity_text(item.get("selfDignity"))
            if _js_truthy(item.get("hayyiz")) and item.get("hayyiz") != "None":
                dg += f"，{msg(item['hayyiz'])}"
            if _js_truthy(item.get("isVOC")):
                dg += "，空亡"
            dignity_cell = dg
        govern_cell = _EMPTY_CELL
        if _js_truthy(item.get("governSign")):
            govern_cell = msg(item["governSign"])
            if _js_truthy(item.get("governPlanets")) and _js_len(item.get("governPlanets")):
                govern_cell += f" , {as_name_list(item['governPlanets'])}"
        dignity_cells = [
            dignity_cell,
            _js_str(item["score"]) if "score" in item else _EMPTY_CELL,
            as_name_list(item["ruleHouses"]) if _js_truthy(item.get("ruleHouses")) and _js_len(item.get("ruleHouses")) else _EMPTY_CELL,
            msg(item["exaltHouse"]) if _js_truthy(item.get("exaltHouse")) else _EMPTY_CELL,
            govern_cell,
            msg(item["moonPhase"]) if "moonPhase" in item else _EMPTY_CELL,
            msg(item["sunPos"]) if "sunPos" in item else _EMPTY_CELL,
        ]
        if any(cell != _EMPTY_CELL for cell in dignity_cells):
            dignity_rows.append([name, *dignity_cells])

        occ = orient_occident.get(obj_id)
        antiscia_point = item.get("antisciaPoint")
        cantiscia_point = item.get("cantisciaPoint")
        antiscia_cells = [
            _format_sign_degree(_as_dict(antiscia_point).get("sign"), _get(_as_dict(antiscia_point), "signlon")) if _js_truthy(antiscia_point) else _EMPTY_CELL,
            _format_sign_degree(_as_dict(cantiscia_point).get("sign"), _get(_as_dict(cantiscia_point), "signlon")) if _js_truthy(cantiscia_point) else _EMPTY_CELL,
            as_name_list([_as_dict(x).get("id", _UNDEFINED) for x in _as_list(_as_dict(occ).get("oriental"))]) if _js_truthy(occ) else _EMPTY_CELL,
            as_name_list([_as_dict(x).get("id", _UNDEFINED) for x in _as_list(_as_dict(occ).get("occidental"))]) if _js_truthy(occ) else _EMPTY_CELL,
        ]
        if _js_truthy(antiscia_point) or _js_truthy(cantiscia_point) or _js_truthy(occ):
            antiscia_rows.append([name, *antiscia_cells])

        stars = smap.get(obj_id) or []
        if stars:
            star_groups.append((name, stars))

    lines: list[str] = []
    if pos_rows:
        lines.append("◆ 位置与速度")
        lines.extend(_gfm_table_lines(["星曜", "落座", "落宫", "月宿", "平均速度", "当前速度"], pos_rows))
    if coord_rows:
        lines.append("◆ 坐标")
        lines.extend(_gfm_table_lines(["星曜", "黄经", "黄纬", "赤经", "赤纬", "真地平纬度", "视地平纬度", "地坪经度"], coord_rows))
    if dignity_rows:
        lines.append("◆ 尊贵与主宰")
        lines.extend(_gfm_table_lines(["星曜", "禀赋", "分值", "入垣宫", "擢升宫", "宰制星座", "月限", "太阳关系"], dignity_rows))
    if antiscia_rows:
        lines.append("◆ 映点与东西")
        lines.extend(_gfm_table_lines(["星曜", "映点", "反映点", "东出星", "西入星"], antiscia_rows))
    if star_groups:
        lines.append("◆ 汇合恒星")
        for name, stars in star_groups:
            lines.append(name)
            lines.extend(format_stars_lines(stars))
    return lines


def build_lots_section(chart_obj: Any) -> list[str]:
    """astroAiSnapshot.js:918-948：点位|落座|落宫 表 + ◆汇合恒星。"""
    obj = chart_obj if isinstance(chart_obj, dict) else {}
    object_map = _objects_map(obj)
    smap = stars_map(obj)
    rows: list[list[str]] = []
    star_groups: list[tuple[str, list[Any]]] = []
    for obj_id in LOTS:
        item = object_map.get(obj_id)
        if not isinstance(item, dict):
            continue
        name = _msg_house(obj_id, obj)
        rows.append([name, _format_sign_degree(item.get("sign"), _get(item, "signlon")), msg(item["house"]) if _js_truthy(item.get("house")) else _EMPTY_CELL])
        stars = smap.get(obj_id) or []
        if stars:
            star_groups.append((name, stars))
    lines = _gfm_table_lines(["点位", "落座", "落宫"], rows)
    if star_groups:
        lines.append("◆ 汇合恒星")
        for name, stars in star_groups:
            lines.append(name)
            lines.extend(format_stars_lines(stars))
    return lines


# ─────────────────────── [12分度]（astroAiSnapshot.js:952-1006）───────────────────────


def _norm360(value: Any) -> float:
    v = math.fmod(_js_number(value), 360)
    if v < 0:
        v += 360
    return v


def dodeca_lon_of(lon: Any) -> float:
    """astroAiSnapshot.js:980-983 dodecaLonOf：floor(度/30)*30 + (度%30)*12。"""
    base = _norm360(lon)
    return _norm360(math.floor(base / 30) * 30 + math.fmod(base, 30) * 12)


def build_dodeca_lines(dodeca: Any) -> list[str]:
    """astroAiSnapshot.js:991-1006 buildDodecaSection（曜|本命|12分度 表）。

    输入 = vendored natalExtras 的 `dodeca`（每曜 natalLon / dodecaLon；上游 objAbsLon → lonToSignDegree 同算，
    lonToSignDegree 内部再归一，故 natalLon 已归一不影响文本）。"""
    rows: list[list[str]] = []
    for item in _as_list(dodeca):
        if not isinstance(item, dict):
            continue
        natal = _lon_to_sign_degree(item.get("natalLon"))
        dodeca_txt = _lon_to_sign_degree(item.get("dodecaLon"))
        if not natal or not dodeca_txt:
            continue
        rows.append([msg(item.get("id", _UNDEFINED)), natal, dodeca_txt])
    return _gfm_table_lines(["曜", "本命", "12分度"], rows)


def build_dispositor_chain_lines(chains: Any) -> list[str]:
    """astroAiSnapshot.js:1037 链行 `${msg(id)}：${chain.map(msg).join(' → ')}`（链由 vendored natalExtras 算，上游同一算法）。"""
    return [
        f"{msg(item.get('id', _UNDEFINED))}：{' → '.join(msg(k) for k in _as_list(item.get('chain')))}"
        for item in _as_list(chains)
        if isinstance(item, dict)
    ]


def build_dispositor_tail_lines(chart_obj: Any) -> list[str]:
    """astroAiSnapshot.js:1042-1047 链行之后：判读口径行 + ◆ 整宫制宫主表（astro_rulers 单源）。"""
    return build_dispositor_ruler_tail_lines(chart_obj, msg)


def build_house_system_ruler_lines(chart_obj: Any, fields: Any) -> list[str]:
    """astroAiSnapshot.js:1063-1077 buildHouseSystemRulerSection（astro_rulers 单源）。"""
    return build_house_system_ruler_section_lines(chart_obj, fields, msg)


# ─────────────────────── [寿命格局]（astroAiSnapshot.js:1098-1245）───────────────────────

_LIFESPAN_KEY_TO_ID = {
    "sun": "Sun", "moon": "Moon", "mercury": "Mercury", "venus": "Venus", "mars": "Mars", "jupiter": "Jupiter",
    "saturn": "Saturn", "asc": "Asc", "mc": "MC", "fortune": "Pars Fortuna", "syzygy": "Syzygy",
    "north_node": "North Node", "south_node": "South Node",
}
_VIA_DIG = {"ruler": "本垣", "exalt": "擢升", "triplicity": "三分", "term": "界", "face": "面 / 十度"}
_ANGLR = {"angular": "角宫", "succedent": "续宫", "cadent": "果宫"}
_BAND_CN = {"greatest": "大限", "mean": "中限", "least": "小限", "max": "大限", "min": "小限"}
_STATE_HAYYIZ = {"Hayyiz": "得时得地", "DemiHayyiz": "半得", "InWrongPos": "失位", "None": ""}
_STATE_SUN = {"cazimi": "核心", "combust": "焦伤", "under_beams": "日光束下", "underBeams": "日光束下", "free": "自由光"}
_STATE_ORIENT = {"oriental": "东出", "occidental": "西入"}
_STATE_MOTION = {"retro": "逆行", "direct": "顺行", "stationary": "停滞"}


def lifespan_name(key: Any) -> str:
    """astroAiSnapshot.js:1106-1117 lifespanName：小写 key → chart id → msg（单字名）；认不出 → 首字大写再 msg，仍不认原样。"""
    if not _js_truthy(key):
        return "-"
    lk = _js_str(key).lower()
    if lk in _LIFESPAN_KEY_TO_ID:
        return msg(_LIFESPAN_KEY_TO_ID[lk])
    cap = lk[:1].upper() + lk[1:]
    mapped = msg(cap)
    return mapped if mapped and mapped != cap else _js_str(key)


def build_lifespan_lines(res: Any) -> list[str]:
    """astroAiSnapshot.js:1121-1245 buildLifespanSection 的排版段（引擎 runLifespan 由 vendored natalExtras 跑，结果经 JSON
    回传：undefined 键不回传、null 保留 → `in` 判 undefined、`${null}` = 'null'）。res 为空 → []（上游 catch/无结果不产段）。"""
    if not isinstance(res, dict) or not res:
        return []
    lines = [f"区分：{'昼生盘' if _js_truthy(res.get('isDiurnal')) else '夜生盘'}"]
    hy = res.get("hyleg")
    if _js_truthy(hy) and isinstance(hy, dict):
        pos = _lon_to_sign_degree(hy["lon"]) if hy.get("lon") is not None else ""
        house = f"（第{_js_str(hy['house'])}宫）" if _js_truthy(hy.get("house")) else ""
        lines.append(f"生命主(Hyleg)：{lifespan_name(hy.get('key'))} {pos}{house}")
    else:
        lines.append("生命主(Hyleg)：未定")
    alc = res.get("alcocoden")
    if isinstance(alc, dict) and _js_truthy(alc.get("alcocoden")):
        lines.append(f"寿主星(Alcocoden)：{lifespan_name(alc.get('alcocoden'))}")
        if _js_truthy(alc.get("aspectToHyleg")):
            lines.append(f"与生命主相照：{_js_str(alc['aspectToHyleg'])}")
        if alc.get("predictedYears") is not None:
            lines.append(f"预测寿数 ≈ {_js_str(alc['predictedYears'])} 年（基础 {_js_str(_get(alc, 'baseYears'))} 年）")
    else:
        lines.append("寿主星(Alcocoden)：未能确定")
    rulers = res.get("rulers")
    if _js_truthy(rulers) and isinstance(rulers, dict):
        parts = []
        if _js_truthy(rulers.get("epikratetor")):
            parts.append(f"占控星 {lifespan_name(rulers['epikratetor'])}")
        if _js_truthy(rulers.get("oikodespotes")):
            parts.append(f"家主星 {lifespan_name(rulers['oikodespotes'])}")
        if _js_truthy(rulers.get("kurios")):
            parts.append(f"盘主星 {lifespan_name(rulers['kurios'])}")
        if parts:
            lines.append(f"盘主体系：{'；'.join(parts)}{'（家主=盘主，格局相合）' if _js_truthy(rulers.get('concordant')) else ''}")
    if _js_truthy(res.get("method")):
        lines.append(f"取主法：{_js_str(res['method'])}")
    if _js_truthy(res.get("birthType")):
        lines.append(f"朔/望月：{'朔月(合)' if res['birthType'] == 'conjunctional' else '望月(冲)'}")
    candidates = res.get("candidates")
    if isinstance(candidates, list) and candidates:
        lines.append("生命主候选：")
        for c in candidates:
            if not isinstance(c, dict) or not _js_truthy(c.get("key")):
                continue
            aphetic = "投射" if _js_truthy(c.get("aphetic")) else "非投射"
            rank = f"rank={_js_str(c['rank'])}" if c.get("rank") is not None else ""
            reason = f"·{_js_str(c['reason'])}" if _js_truthy(c.get("reason")) else ""
            house = f"第{_js_str(c['house'])}宫" if _js_truthy(c.get("house")) else ""
            lines.append(f"{lifespan_name(c.get('key'))} {house}·{aphetic}{'·' + rank if rank else ''}{reason}")
    if _js_truthy(alc) and isinstance(alc, dict):
        detail: list[str] = []
        if _js_truthy(alc.get("viaDignity")):
            detail.append(f"经{_VIA_DIG.get(_js_str(alc['viaDignity'])) or _js_str(alc['viaDignity'])}")
        if _js_truthy(alc.get("angularity")):
            detail.append(_ANGLR.get(_js_str(alc["angularity"])) or _js_str(alc["angularity"]))
        if _js_truthy(alc.get("band")):
            detail.append(f"限 {_BAND_CN.get(_js_str(alc['band'])) or _js_str(alc['band'])}")
        if "baseYears" in alc:
            detail.append(f"基础{_js_str(alc['baseYears'])}年")
        if detail:
            lines.append(f"寿主星细节：{'；'.join(detail)}")
        modifiers = alc.get("modifiers")
        if isinstance(modifiers, list) and modifiers:
            for m in modifiers:
                if not _js_truthy(m) or not isinstance(m, dict):
                    continue
                planet = lifespan_name(m["planet"]) if _js_truthy(m.get("planet")) else ""
                aspect = f"·{_js_str(m['aspect'])}" if _js_truthy(m.get("aspect")) else ""
                delta = f"(Δ{_js_str(m['delta'])})" if m.get("delta") is not None else ""
                kind = f"·{_js_str(m['kind'])}" if _js_truthy(m.get("kind")) else ""
                lines.append(f"修正：{planet}{aspect}{delta}{kind}")
    medical = res.get("medical")
    if _js_truthy(medical) and isinstance(medical, dict):
        mp: list[str] = []
        sixth_sign = medical.get("sixthSign")
        if _js_truthy(sixth_sign):
            cap = sixth_sign[:1].upper() + sixth_sign[1:] if isinstance(sixth_sign, str) else sixth_sign
            mp.append(f"六宫{msg(cap)}")
        if _js_truthy(medical.get("sixthRuler")):
            mp.append(f"六宫主 {lifespan_name(medical['sixthRuler'])}")
        if mp:
            lines.append(f"医疗危机：{'；'.join(mp)}")
        afflictions = medical.get("hylegAfflictions")
        if isinstance(afflictions, list) and afflictions:
            joined = "、".join(
                f"{lifespan_name(_as_dict(x).get('planet') or _as_dict(x).get('id'))}"
                f"{'·' + _js_str(_as_dict(x)['aspect']) if _js_truthy(_as_dict(x).get('aspect')) else ''}"
                for x in afflictions
            )
            lines.append(f"生命主受克：{joined}")
        body = medical.get("bodyHyleg")
        if isinstance(body, list) and body:
            lines.append(f"生命主部位：{'、'.join(_js_str(b) for b in body)}")
        if _js_truthy(medical.get("note")):
            lines.append(f"备注：{_js_str(medical['note'])}")
    states = res.get("states")
    rows = states.get("rows") if isinstance(states, dict) else None
    if isinstance(rows, list) and rows:
        lines.append("行星状态盘：")
        for row in rows:
            if not _js_truthy(row) or not isinstance(row, dict) or not _js_truthy(row.get("planet")):
                continue
            parts = []
            if _js_truthy(row.get("hayyiz")) and row["hayyiz"] != "None":
                label = _STATE_HAYYIZ.get(_js_str(row["hayyiz"]))
                if label:
                    parts.append(label)
            if _js_truthy(row.get("sunState")) and row["sunState"] != "None":
                parts.append(_STATE_SUN.get(_js_str(row["sunState"])) or _js_str(row["sunState"]))
            if _js_truthy(row.get("orient")):
                parts.append(_STATE_ORIENT.get(_js_str(row["orient"])) or _js_str(row["orient"]))
            if _js_truthy(row.get("motion")):
                parts.append(_STATE_MOTION.get(_js_str(row["motion"])) or _js_str(row["motion"]))
            if row.get("inSect") is True:
                parts.append("同宗派")
            elif row.get("inSect") is False:
                parts.append("异宗派")
            if _js_truthy(row.get("house")):
                parts.append(f"第{_js_str(row['house'])}宫")
            lines.append(f"{lifespan_name(row.get('planet'))}：{'·'.join(parts)}")
    return lines


def build_possibility_lines(chart_obj: Any) -> list[str]:
    """astroAiSnapshot.js:1251-1261 buildPossibilitySection。"""
    obj = chart_obj if isinstance(chart_obj, dict) else {}
    predict = _as_dict(obj.get("predict"))
    planet_sign = _as_dict(predict.get("PlanetSign"))
    lines: list[str] = []
    for key, items in planet_sign.items():
        lines.append(msg(key))
        for text in items or []:
            lines.append(_js_str(text))
    return lines


# ─────────────────────── [古典]（astroAiSnapshot.js:1318-1503）───────────────────────

CLS_STATUS_IDS = ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn")
_CLS_PHASE = {"cazimi": "核心", "combust": "焦伤", "underBeams": "日光束下", "free": "自由光"}
_CLS_PHASE_EVENT = {"morningRising": "晨星初现", "eveningSetting": "昏星初没"}
_CLS_QUALITY = {"B": "明度", "D": "暗度", "E": "空度", "S": "烟度"}
_CLS_SPECIAL = {"pitted": "陷度", "azemene": "慢病度", "fortune": "增福度"}
_CLS_APOGEE = {"rising": "升·趋远地点", "falling": "降·趋近地点"}
_CLS_NUM = {"increasing": "数增·渐疾", "decreasing": "数减·渐迟"}
_CLS_LIGHT = {"waxing": "光增·渐盈", "waning": "光减·渐亏"}
_CLS_SEASON = {"春": "春·主宰", "夏": "夏·宰执", "秋": "秋·受制", "冬": "冬·被执", "中": "中"}
_CLS_MEAN_ATK = {
    "Sun": "精神阴暗·心灵扭曲", "Moon": "凶死夭折·绝症残疾", "Mercury": "智力特异·语言障碍",
    "Venus": "欲望混乱·专断残暴", "Jupiter": "世俗无成·离经叛道", "Mars": "自身受困崩坏", "Saturn": "自身受困崩坏",
}


def build_besiegement_lines(chart_obj: Any) -> list[str]:
    """astroAiSnapshot.js:1337-1362 buildBesiegementLines（围攻详断）。"""
    obj = chart_obj if isinstance(chart_obj, dict) else {}
    lines: list[str] = []
    for b in _as_list(_as_dict(obj.get("surround")).get("besiegement")):
        if not isinstance(b, dict) or not isinstance(b.get("besiegers"), list):
            continue
        besiegers: list[str] = []
        for x in b["besiegers"]:
            x = _as_dict(x)
            season = x.get("season", _UNDEFINED)
            s = f"{msg(x.get('id', _UNDEFINED))}（{_CLS_SEASON.get(_js_str(season)) or _js_str(season)}"
            if _js_truthy(x.get("retro")):
                s += "·逆行"
            if _js_truthy(x.get("restrained")) and _js_len(x.get("restrained")):
                s += "·日木制约凶减半"
            if _js_truthy(x.get("counterBesieged")):
                s += "·围魏救赵"
            besiegers.append(f"{s}）")
        head = (
            f"{msg(b.get('target', _UNDEFINED))}{'（逆行）' if _js_truthy(b.get('targetRetro')) else ''} 被 "
            f"{' 与 '.join(besiegers)} {_js_str(b.get('kind', _UNDEFINED))}（{_js_str(b.get('nature', _UNDEFINED))}）"
        )
        if _js_truthy(b.get("severe")):
            head += "·凶剧见血"
        lines.append(head)
        defense = b.get("defense")
        if _js_truthy(defense) and _js_len(defense):
            d = "，".join(
                f"{msg(_as_dict(y).get('id', _UNDEFINED))}（{'以身作盾' if _js_truthy(_as_dict(y).get('byBody')) else '遥光'}·护"
                f"{msg(_as_dict(y)['against']) if _js_truthy(_as_dict(y).get('against')) else _js_str(_as_dict(y).get('side', _UNDEFINED))}侧·"
                f"{'强' if _js_truthy(_as_dict(y).get('strong')) else '弱'}）"
                for y in defense
            )
            lines.append(f"协防：{d}")
        kind = b.get("kind")
        if kind == "围攻":
            mean = _CLS_MEAN_ATK.get(_js_str(b.get("target", _UNDEFINED)), "")
        elif kind == "围荣":
            mean = "致富·舒适自由·财帛丰盈"
        else:
            mean = "致贵·领袖魅力·载众载民"
        if mean:
            lines.append(f"断语：{mean}")
    return lines


def build_encircle_lines(chart_obj: Any) -> list[str]:
    """astroAiSnapshot.js:1365-1385 buildEncircleLines（围绕：七政按黄经环形紧邻，跨 <90°）。"""
    object_map = _objects_map(chart_obj if isinstance(chart_obj, dict) else {})
    bodies = [
        object_map[i] for i in CLS_STATUS_IDS
        if isinstance(object_map.get(i), dict)
        and isinstance(object_map[i].get("lon"), (int, float)) and not isinstance(object_map[i].get("lon"), bool)
    ]
    if len(bodies) < 3:
        return []
    ordered = sorted(bodies, key=lambda o: o["lon"])
    n = len(ordered)

    def norm(x: float) -> float:
        return math.fmod(math.fmod(x, 360) + 360, 360)

    lines: list[str] = []
    for i in range(n):
        mid = ordered[i]
        left = ordered[(i - 1 + n) % n]
        right = ordered[(i + 1) % n]
        span = norm(mid["lon"] - left["lon"]) + norm(right["lon"] - mid["lon"])
        if span < 90:
            lines.append(f"{msg(left.get('id', _UNDEFINED))} 与 {msg(right.get('id', _UNDEFINED))} 围绕 {msg(mid.get('id', _UNDEFINED))}（跨{fmt_num(span, 1)}°）")
    return lines


def pat_sign_cn(sign: Any) -> str:
    """astroAiSnapshot.js:1387 patSignCn：SIGNS[小写].cn，认不出原样。"""
    key = _js_str(sign).lower() if _js_truthy(sign) else None
    if key and key in SIGN_CN:
        return SIGN_CN[key]
    return _js_str(sign) if _js_truthy(sign) else ""


def build_pattern_overview_lines(data: Any) -> list[str]:
    """astroAiSnapshot.js:1390-1417 buildPatternOverviewLines 的排版（数据 = buildPatternOverview 的 Python 移植）。"""
    if not isinstance(data, dict) or not data or data.get("empty"):
        return []
    lines: list[str] = []
    d = _as_dict(data.get("dragon"))
    if d and _js_truthy(d.get("has")):
        if d.get("kind") == "龙拥":
            lines.append(f"龙脉：龙拥（{_js_str(d['note']) if _js_truthy(d.get('note')) else '七星聚一侧'}）")
        elif _js_truthy(d.get("pair")):
            lines.append(f"龙脉：龙截 {''.join(msg(x) for x in d['pair'])}（两星联结）")
        else:
            house = f"·{_js_str(d['loneHouse'])}宫" if _js_truthy(d.get("loneHouse")) else ""
            rules = d.get("loneRules")
            rules_txt = f"·主{'/'.join(_js_str(r) for r in rules)}宫" if _js_truthy(rules) and _js_len(rules) else ""
            lines.append(f"龙脉：龙截 {msg(d.get('lone', _UNDEFINED))}（{pat_sign_cn(d.get('loneSign'))}{house}{rules_txt}）")
    if _js_truthy(data.get("loneMoon")) and _js_truthy(_as_dict(data.get("loneMoon")).get("has")):
        lines.append("孤月独明：是（夜生·唯月在地平上）")
    ap = _as_dict(data.get("apriori"))
    if _js_truthy(ap.get("has")):
        links = "、".join(
            f"{msg(_as_dict(lk).get('a', _UNDEFINED))}{_js_str(_as_dict(lk).get('kind', _UNDEFINED))}{msg(_as_dict(lk).get('b', _UNDEFINED))}({_js_str(_as_dict(lk).get('which', _UNDEFINED))})"
            for lk in _as_list(ap.get("links"))
        )
        lines.append(f"先验权力：{links}{'·夜生·八杀朝天大贵' if _js_truthy(ap.get('eightKill')) else '·昼生·非八杀朝天'}")
    mm = _as_dict(data.get("moonMercury"))

    def one_mm(o: Any) -> str:
        if not _js_truthy(o) or not isinstance(o, dict):
            return ""
        out = pat_sign_cn(o.get("sign"))
        if _js_truthy(o.get("modality")):
            out += f"·{_js_str(o['modality'])}"
        if _js_truthy(o.get("ruler")):
            out += f"·主{msg(o['ruler'])}{_js_str(o['rulerDign']) if _js_truthy(o.get('rulerDign')) else ''}"
        if _js_truthy(o.get("flags")) and _js_len(o.get("flags")):
            out += f"·{''.join(_js_str(f) for f in o['flags'])}"
        return out

    if _js_truthy(mm.get("moon")):
        lines.append(f"心性(月)：{one_mm(mm['moon'])}")
    if _js_truthy(mm.get("mercury")):
        lines.append(f"智识(水)：{one_mm(mm['mercury'])}")
    v = _as_dict(data.get("vocation"))
    for label, item in (("职业(月第一西没)", v.get("career")), ("行事(日第一西没)", v.get("style"))):
        if _js_truthy(item) and isinstance(item, dict):
            house = f"·{_js_str(item['house'])}宫" if _js_truthy(item.get("house")) else ""
            lines.append(f"{label}：{msg(item.get('id', _UNDEFINED))} {pat_sign_cn(item.get('sign'))}{house}")
    j = data.get("jupiter")
    if isinstance(j, dict) and _js_truthy(j.get("present")):
        lit = j.get("lit")
        lit_txt = f"（{'、'.join(msg(x) for x in lit)}）" if _js_truthy(lit) and _js_len(lit) else ""
        dign = f"·{_js_str(j['dign'])}" if _js_truthy(j.get("dign")) else ""
        lines.append(f"木星：{'强吉' if _js_truthy(j.get('strong')) else '非强吉'}·{pat_sign_cn(j.get('sign'))}{dign}·照耀{_js_str(j.get('litCount', _UNDEFINED))}星{lit_txt}")
    afflicted = _as_list(data.get("afflictedRulers"))
    if afflicted:
        lines.append(f"后天凶星：{'、'.join(msg(x) for x in afflicted)}")
    return lines


def _degree_position(deg: Any) -> str:
    """divination/data/bodyParts.js degreePosition：早/中/晚 = 上方/中间/下方。"""
    d = math.fmod(math.fmod(_js_number(deg), 30) + 30, 30)
    if d < 10:
        return "上方"
    if d < 20:
        return "中间"
    return "下方"


def build_classical_section(chart_obj: Any, *, pattern_overview: Any = None) -> list[str]:
    """astroAiSnapshot.js:1420-1503 buildClassicalSection：逐曜古典状态 / 上升宿 / 围攻详断 / 围绕 / 古典格局（格局速览）/
    身体部位(Melothesia)。`pattern_overview` = buildPatternOverview 数据（service 侧 Python 移植算好传入）。"""
    obj = chart_obj if isinstance(chart_obj, dict) else {}
    object_map = _objects_map(obj)
    lines: list[str] = []
    profile: list[str] = []
    for pid in CLS_STATUS_IDS:
        o = object_map.get(pid)
        if not isinstance(o, dict):
            continue
        parts: list[str] = []
        if _js_truthy(o.get("outOfBounds")):
            mode = ("远行" if o.get("oobMode") == "going" else "回归") if (pid == "Moon" and _js_truthy(o.get("oobMode"))) else ""
            parts.append(f"出界+{fixed_num(_get(o, 'oobDelta'), 2)}°{f'（{mode}）' if mode else ''}")
        if _js_truthy(o.get("phase")):
            p = _CLS_PHASE.get(_js_str(o["phase"])) or _js_str(o["phase"])
            if o.get("phasisElong") is not None:
                p += f"（距日{fixed_num(o['phasisElong'], 1)}°）"
            if _js_truthy(o.get("phasisEvent")):
                p += f"·{_CLS_PHASE_EVENT.get(_js_str(o['phasisEvent'])) or _js_str(o['phasisEvent'])}"
            parts.append(p)
        if _js_truthy(o.get("joy")):
            parts.append(f"喜乐（{_js_str(_get(o, 'joyHouse'))}宫）")
        if o.get("ofSect") is not None:
            parts.append("同宗" if _js_truthy(o.get("ofSect")) else "异宗")
        if _js_truthy(o.get("feral")):
            parts.append("野逸")
        if _js_truthy(o.get("degreeQuality")):
            parts.append(_CLS_QUALITY.get(_js_str(o["degreeQuality"])) or f"{_js_str(o['degreeQuality'])}度")
        if _js_truthy(o.get("degreeGender")):
            parts.append("阳性度" if o["degreeGender"] == "masculine" else "阴性度")
        special = o.get("specialDegree")
        if _js_truthy(special) and isinstance(special, dict):
            tags = [_CLS_SPECIAL.get(k) or k for k, flag in special.items() if _js_truthy(flag)]
            if tags:
                parts.append("·".join(tags))
        mansion = o.get("mansion")
        if isinstance(mansion, dict) and _js_truthy(mansion.get("cn")):
            parts.append(f"月站{_js_str(mansion['cn'])}（{_js_str(mansion.get('nature', _UNDEFINED))}）")
        if _js_truthy(o.get("apogeeDir")):
            a = _CLS_APOGEE.get(_js_str(o["apogeeDir"])) or _js_str(o["apogeeDir"])
            if _js_truthy(o.get("numberTrend")):
                a += f"·{_CLS_NUM.get(_js_str(o['numberTrend'])) or ''}"
            if _js_truthy(o.get("lightTrend")):
                a += f"·{_CLS_LIGHT.get(_js_str(o['lightTrend'])) or ''}"
            parts.append(a)
        dl: list[str] = []
        if _js_truthy(o.get("monomoiria")):
            dl.append(f"单度主星{msg(o['monomoiria'])}")
        if _js_truthy(o.get("ninthPart")):
            dl.append(f"九分{msg(o['ninthPart'])}")
        dignities = o.get("dignities")
        if isinstance(dignities, dict) and _js_truthy(dignities.get("face")):
            dl.append(f"面主{msg(dignities['face'])}")
        if _js_truthy(o.get("darijan")):
            dl.append(f"Darijan{msg(o['darijan'])}")
        if dl:
            parts.append("·".join(dl))
        if parts:
            profile.append(f"{msg(pid)}：{'；'.join(parts)}")
    if profile:
        lines.append("逐曜古典状态")
        lines.extend(profile)
    asc = object_map.get("Asc")
    if isinstance(asc, dict) and isinstance(asc.get("mansion"), dict) and _js_truthy(asc["mansion"].get("cn")):
        m = asc["mansion"]
        lines.append(f"上升宿：{_js_str(m['cn'])}（{_js_str(m.get('nature', _UNDEFINED))} · {_js_str(m.get('use', _UNDEFINED))}）")
    bsg = build_besiegement_lines(obj)
    if bsg:
        lines.append("围攻详断")
        lines.extend(bsg)
    enc = build_encircle_lines(obj)
    if enc:
        lines.append("围绕")
        lines.extend(enc)
    pat = build_pattern_overview_lines(pattern_overview)
    if pat:
        lines.append("古典格局")
        lines.extend(pat)
    melo: list[str] = []
    for pid in CLS_STATUS_IDS:
        o = object_map.get(pid)
        if not isinstance(o, dict) or not _js_truthy(o.get("sign")):
            continue
        parts_m = SIGN_BODY_PARTS.get(_js_str(o["sign"]).lower())
        if not parts_m:
            continue
        pos = _degree_position(o["signlon"]) if o.get("signlon") is not None else ""
        melo.append(f"{msg(pid)}：{pos + '·' if pos else ''}{'、'.join(parts_m)}")
    if melo:
        lines.append("身体部位(Melothesia)")
        lines.extend(melo)
    return lines


# ─────────────────────── [古典格局]（astroAiSnapshot.js:1505-1689）───────────────────────

_CLS_OVR_ASP = {"sextile": "六分", "square": "四分", "trine": "三分", "conjunction": "合", "opposition": "冲"}
# astroAiSnapshot.js:1507-1519 CLS_LOT_CN（与 AstroAnalysisLab.js LOT_CN 同源；Radix=本源点，Basis=根基点）。
_CLS_LOT_CN = {
    "Pars Fortuna": "福点", "Pars Fortunae": "福点", "Pars Spirit": "精神点", "Pars Faith": "信仰点", "Pars Substance": "资财点",
    "Pars Wedding [Male]": "婚姻点(男)", "Pars Wedding [Female]": "婚姻点(女)", "Pars Sons": "子女点",
    "Pars Father": "父亲点", "Pars Mother": "母亲点", "Pars Brothers": "兄弟点", "Pars Diseases": "疾厄点",
    "Pars Death": "死亡点", "Pars Travel": "旅行点", "Pars Friends": "朋友点", "Pars Enemies": "仇敌点",
    "Pars Saturn": "土星点", "Pars Jupiter": "木星点", "Pars Mars": "火星点", "Pars Venus": "金星点",
    "Pars Mercury": "水星点", "Pars Horsemanship": "骑术点", "Pars Life": "生命点", "Pars Radix": "本源点",
    "Pars Eros": "爱欲点", "Pars Necessity": "必然点", "Pars Courage": "勇气点", "Pars Victory": "胜利点",
    "Pars Nemesis": "报应点",
    "Pars Basis": "根基点", "Pars Exaltation": "擢升点", "Pars Sons Valens": "儿子点",
    "Pars Daughters": "女儿点", "Pars Praxis": "事业点", "Pars Wedding Dorothean": "婚姻点(通式)",
}
_CLS_ELEM = {"Fire": "火", "Earth": "土", "Air": "风", "Water": "水"}
_CLS_MODE = {"Cardinal": "始", "Fixed": "固", "Mutable": "变"}
_CLS_HEMI = {"east": "东", "west": "西", "above": "地平上", "below": "地平下"}
_CLS_TEMPER = {"Choleric": "胆汁(热干)", "Melancholic": "忧郁(冷干)", "Sanguine": "多血(热湿)", "Phlegmatic": "黏液(冷湿)"}
_CLS_QUAL = {"Hot": "热", "Cold": "冷", "Dry": "干", "Humid": "湿"}
_HOUR_MODE = {"sunrise": "日出起等长", "unequal": "昼夜不等时", "equal24": "廿四时等分"}


def _kv(obj: Any, mapping: dict[str, str]) -> str:
    return " ".join(f"{mapping.get(k) or k}{_js_str(v)}" for k, v in _as_dict(obj).items())


def build_classical_analysis_lines(analysis: Any) -> list[str]:
    """astroAiSnapshot.js:1529-1689 buildClassicalAnalysisSection（/astroextra/analysis → [古典格局]）。"""
    if not isinstance(analysis, dict):
        return []
    lines: list[str] = []
    cp = _as_dict(analysis.get("classicalPatterns"))
    dory = [f"{msg(_as_dict(d).get('planet', _UNDEFINED))} 护卫 {msg(_as_dict(d).get('light', _UNDEFINED))}（距{round3(_as_dict(d).get('elong', _UNDEFINED))}°）" for d in _as_list(cp.get("doryphory"))]
    over = [
        f"{msg(o.get('over', _UNDEFINED))}({msg(o.get('overSign', _UNDEFINED))}) 凌驾 {msg(o.get('under', _UNDEFINED))}({msg(o.get('underSign', _UNDEFINED))})·"
        f"{_CLS_OVR_ASP.get(_js_str(o.get('aspect', _UNDEFINED))) or _js_str(o.get('aspect', _UNDEFINED))}"
        for o in (_as_dict(x) for x in _as_list(cp.get("overcoming")))
    ]
    bsgd = [f"{msg(_as_dict(b).get('planet', _UNDEFINED))} 被 {msg(_as_dict(b).get('left', _UNDEFINED))}/{msg(_as_dict(b).get('right', _UNDEFINED))} 度数围攻" for b in _as_list(cp.get("besieging"))]
    if dory or over or bsgd:
        lines.append("古典格局")
        if dory:
            lines.append(f"护卫：{'；'.join(dory)}")
        if over:
            lines.append(f"优势相位：{'；'.join(over)}")
        if bsgd:
            lines.append(f"度数围攻：{'；'.join(bsgd)}")
    ad = _as_dict(analysis.get("aspectDynamics"))
    g = lambda d, k: _as_dict(d).get(k, _UNDEFINED)  # noqa: E731
    trans = [f"{msg(g(t, 'mover'))} 自 {msg(g(t, 'from'))} 传光予 {msg(g(t, 'to'))}" for t in _as_list(ad.get("translation"))]
    coll = [f"{msg(g(c, 'collector'))} 聚 {msg(g(c, 'p1'))}、{msg(g(c, 'p2'))} 之光" for c in _as_list(ad.get("collection"))]
    aver = [f"{msg(g(v, 'a'))} 与 {msg(g(v, 'b'))} 不合意" for v in _as_list(ad.get("aversion"))]
    bend = [
        f"{msg(g(b, 'planet'))} 交点弯曲" + (f"（{_js_str(_as_dict(b)['at'])}）" if _js_truthy(_as_dict(b).get("at")) else "")
        for b in _as_list(ad.get("bending"))
    ]
    voidc = [f"{msg(g(v, 'planet'))} 空亡（{'30°内' if _as_dict(v).get('mode') == 'classical' else '本座内'}不再成相）" for v in _as_list(ad.get("void"))]
    prohib = [f"{msg(g(p, 'blocker'))} 阻止 {msg(g(p, 'between'))}→{msg(g(p, 'to'))} 入相" for p in _as_list(ad.get("prohibition"))]
    frust = [f"{msg(g(f, 'frustrated'))} 挫败（{msg(g(f, 'via'))} 先成相 {msg(g(f, 'to'))}）" for f in _as_list(ad.get("frustration"))]
    refran = [f"{msg(g(r, 'planet'))} 收回（趋留撤离 {msg(g(r, 'to'))}）" for r in _as_list(ad.get("refranation"))]
    if trans or coll or aver or bend or voidc or prohib or frust or refran:
        lines.append("相位动态")
        for label, items in (("传光", trans), ("聚光", coll), ("不合意", aver), ("交点弯曲", bend), ("空亡", voidc), ("阻止", prohib), ("挫败", frust), ("收回", refran)):
            if items:
                lines.append(f"{label}：{'；'.join(items)}")
    ta = []
    for t in _as_list(analysis.get("topicAlmuten")):
        if not isinstance(t, dict) or not _js_truthy(t.get("almuten")):
            continue
        sig = f"·自然象征{msg(t['significator'])}" if _js_truthy(t.get("significator")) else ""
        ta.append(f"{_js_str(t.get('topic', _UNDEFINED))}（{_js_str(t.get('house', _UNDEFINED))}宫{sig}）主星{msg(t['almuten'])}")
    if ta:
        lines.append("逐题主星")
        lines.append("；".join(ta))
    acc = [
        f"{msg(r['planet'])} {_js_str(r.get('score', _UNDEFINED))}（{'·'.join(_js_str(x) for x in (r.get('factors') or []))}）"
        for r in _as_list(analysis.get("accidentalDignity"))
        if isinstance(r, dict) and _js_truthy(r.get("planet"))
    ]
    if acc:
        lines.append("偶然尊贵")
        lines.extend(acc)
    fs = []
    for s in _as_list(analysis.get("fixedStarHits")):
        s = _as_dict(s)
        pos = f"·{_format_sign_degree(s['sign'], s['signlon'])}" if _js_truthy(s.get("sign")) and s.get("signlon") is not None else ""
        orb = f"·容许{fmt_num_safe(s['orb'])}°" if s.get("orb") is not None else ""
        name = _js_str(s["cn"]) if _js_truthy(s.get("cn")) else _js_str(s.get("star", _UNDEFINED))
        royal = f"·王者{_js_str(s['royal'])}" if _js_truthy(s.get("royal")) else ""
        fs.append(f"{msg(s.get('point', _UNDEFINED))} 合 {name}{pos}{orb}{'·比尼' if _js_truthy(s.get('behenian')) else ''}{royal}")
    if fs:
        lines.append("恒星触发")
        lines.append("；".join(fs))
    ph = analysis.get("planetaryHours")
    if isinstance(ph, dict) and _js_truthy(ph.get("dayRuler")):
        lines.append(f"行星时：值日星 {msg(ph['dayRuler'])}（日出 {_js_str(ph.get('sunrise', _UNDEFINED))} / 日落 {_js_str(ph.get('sunset', _UNDEFINED))}）")
        hours = ph.get("hours")
        if isinstance(hours, list) and hours:
            day = [h for h in hours if _js_truthy(h) and isinstance(h, dict) and _js_truthy(h.get("diurnal"))]
            night = [h for h in hours if _js_truthy(h) and isinstance(h, dict) and not _js_truthy(h.get("diurnal"))]
            single = ph.get("hourMode") == "equal24"

            def fmt_hour(h: dict[str, Any], i: int) -> str:
                num = _js_str(_js_number(h.get("index", _UNDEFINED)) - 1) if single else _js_str(i + 1)
                return f"{num}.{msg(h.get('ruler', _UNDEFINED))}{'←当前' if _js_truthy(h.get('current')) else ''}"

            if _js_truthy(ph.get("hourMode")):
                lines.append(f"行星时制式：{_HOUR_MODE.get(_js_str(ph['hourMode'])) or _js_str(ph['hourMode'])}")
            if day:
                lines.append(f"昼时：{' / '.join(fmt_hour(h, i) for i, h in enumerate(day))}")
            if night:
                lines.append(f"夜时：{' / '.join(fmt_hour(h, i) for i, h in enumerate(night))}")
    eg = analysis.get("egyptianCalendar")
    if isinstance(eg, dict) and (_js_truthy(eg.get("siriusRising")) or _js_truthy(eg.get("decanIndex"))):
        parts = []
        if _js_truthy(eg.get("siriusRising")):
            parts.append(f"天狼偕日升 {_js_str(eg['siriusRising'])}")
        if _js_truthy(eg.get("siriusYear")):
            parts.append(f"岁年 {_js_str(eg['siriusYear'])}")
        if _js_truthy(eg.get("decanIndex")):
            parts.append(f"上升第{_js_str(eg['decanIndex'])}旬（{msg(eg.get('decanSign', _UNDEFINED))}）面主{msg(eg.get('decanRuler', _UNDEFINED))}")
        if parts:
            lines.append(f"埃及历：{'；'.join(parts)}")
    bab = []
    for b in _as_list(analysis.get("babylonianStars")):
        if not isinstance(b, dict) or not (_js_truthy(b.get("planet")) or _js_truthy(b.get("star"))):
            continue
        rd = (
            f"({_js_str(b.get('latDir', _UNDEFINED))}{_js_str(b.get('lonDir', _UNDEFINED))} {_js_str(b.get('cubits', _UNDEFINED))} 肘 "
            f"{_js_str(b.get('fingers', _UNDEFINED))} 指)"
            if "latDir" in b else ""
        )
        dist = f"·距{fmt_num_safe(b['dist'])}°" if b.get("dist") is not None else ""
        star = _js_str(b["cn"]) if _js_truthy(b.get("cn")) else _js_str(b.get("star", _UNDEFINED))
        verb = "合参照星" if _js_truthy(b.get("conj")) else "近参照星"
        bab.append(f"{msg(b.get('planet', _UNDEFINED))} {verb} {star}{rd}{dist}")
    if bab:
        lines.append("巴比伦参照星")
        lines.append("；".join(bab))
    pats = []
    for p in _as_list(analysis.get("patterns")):
        p = _as_dict(p)
        label = _js_str(p["label"]) if _js_truthy(p.get("label")) else _js_str(p.get("type", _UNDEFINED))
        apex = f",顶点{msg(p['apex'])}" if _js_truthy(p.get("apex")) else ""
        pats.append(f"{label}（{'·'.join(msg(x) for x in (p.get('points') or []))}{apex}）")
    if pats:
        lines.append("相位格局")
        lines.append("；".join(pats))
    dist_obj = analysis.get("distribution")
    if isinstance(dist_obj, dict) and (_js_truthy(dist_obj.get("elements")) or _js_truthy(dist_obj.get("modes")) or _js_truthy(dist_obj.get("hemispheres"))):
        dl = []
        if _js_truthy(dist_obj.get("elements")):
            dl.append(f"元素 {_kv(dist_obj['elements'], _CLS_ELEM)}")
        if _js_truthy(dist_obj.get("modes")):
            dl.append(f"模态 {_kv(dist_obj['modes'], _CLS_MODE)}")
        if _js_truthy(dist_obj.get("hemispheres")):
            dl.append(f"半球 {_kv(dist_obj['hemispheres'], _CLS_HEMI)}")
        if dl:
            lines.append("分布权重")
            lines.append("；".join(dl))
    temp = analysis.get("temperament")
    if isinstance(temp, dict) and (_js_truthy(temp.get("temperaments")) or _js_truthy(temp.get("qualities"))):
        tl = []
        if _js_truthy(temp.get("temperaments")):
            tl.append(f"气质 {_kv(temp['temperaments'], _CLS_TEMPER)}")
        if _js_truthy(temp.get("qualities")):
            tl.append(f"性质 {_kv(temp['qualities'], _CLS_QUAL)}")
        if tl:
            lines.append("气质评估")
            lines.append("；".join(tl))
    am = analysis.get("almutem")
    if isinstance(am, dict) and _js_truthy(am.get("winner")):
        totals = [(k, v) for k, v in _as_dict(am.get("totals")).items() if _js_gt(v, 0)]
        totals = sorted(totals, key=lambda t: -_js_number(t[1]))
        lines.append(f"Almuten 总主：{msg(am['winner'])}")
        if totals:
            lines.append("Almuten 逐星得分：")
            lines.extend(f"{msg(k)} {_js_str(v)}" for k, v in totals)
    bn = [
        b for b in _as_list(analysis.get("bonification"))
        if isinstance(b, dict) and _js_truthy(b.get("planet")) and (
            (isinstance(b.get("bonified"), list) and b["bonified"]) or (isinstance(b.get("maltreated"), list) and b["maltreated"])
        )
    ]
    if bn:
        lines.append("吉化/凶化")
        for b in bn:
            ok = "、".join(f"{msg(_as_dict(x).get('by', _UNDEFINED))}·{_js_str(_as_dict(x)['rel']) if _js_truthy(_as_dict(x).get('rel')) else '会合'}" for x in (b.get("bonified") or []))
            bad = "、".join(f"{msg(_as_dict(x).get('by', _UNDEFINED))}·{_js_str(_as_dict(x)['rel']) if _js_truthy(_as_dict(x).get('rel')) else '会合'}" for x in (b.get("maltreated") or []))
            segs = []
            if ok:
                segs.append(f"受惠[{ok}]")
            if bad:
                segs.append(f"受厄[{bad}]")
            lines.append(f"{msg(b['planet'])}：{'；'.join(segs)}")
    extra = [l for l in _as_list(analysis.get("extraLots")) if isinstance(l, dict) and _js_truthy(l.get("label"))]
    if extra:
        lines.append("阿拉伯点(扩展)")
        for lot in extra[:120]:
            label = _js_str(lot["label"])
            cn_label = _CLS_LOT_CN.get(label) or label
            cat = f"（{_js_str(lot['category'])}）" if _js_truthy(lot.get("category")) else ""
            if _js_truthy(lot.get("sign")) and lot.get("signlon") is not None:
                dg = _format_sign_degree(lot["sign"], lot["signlon"])
            elif lot.get("lon") is not None:
                dg = _lon_to_sign_degree(lot["lon"])
            elif _js_truthy(lot.get("sign")):
                dg = msg(lot["sign"])
            else:
                dg = ""
            lines.append(f"{cn_label}{cat}：{dg or '-'}")
    return lines



# ─────────────────────── 节气盘 [X宿盘]（components/jieqi/JieQiChartsMain.js:644-821）───────────────────────
# 宿占常量逐值抽自 vendored suzhan/SZConst.js（ZiSign/SignZi :266-281、SZSigns[*][0..1] :73、SZHouseStart_* :24-25）与
# su28/Su28Helper.js Su28（:4）；与 vendored JS 由 tests/test_sync311_chartexport.py 逐项互锚。
SZ_HOUSE_START_BAZI = 0
SZ_HOUSE_START_ASC = 1
SZ_ZI_SIGN: dict[str, str] = {
    "子": "Aquarius", "丑": "Capricorn", "寅": "Sagittarius", "卯": "Scorpio", "辰": "Libra", "巳": "Virgo",
    "午": "Leo", "未": "Cancer", "申": "Gemini", "酉": "Taurus", "戌": "Aries", "亥": "Pisces",
}
SZ_SIGN_ZI: dict[str, str] = {sign: zi for zi, sign in SZ_ZI_SIGN.items()}
# SZSigns[i] 前两字（按 LIST_SIGNS 序：白羊=降娄 …）
SZ_SIGN_AREA: tuple[str, ...] = ("降娄", "大梁", "实沉", "鹑首", "鹑火", "鹑尾", "寿星", "大火", "析木", "星纪", "玄枵", "娵訾")
SU28_ORDER: tuple[str, ...] = (
    "角", "亢", "氐", "房", "心", "尾", "箕", "斗", "牛", "女", "虚", "危", "室", "壁",
    "奎", "娄", "胃", "昴", "毕", "觜", "参", "井", "鬼", "柳", "星", "张", "翼", "轸",
)
# constants/AstroConst.js:616-627 DEFAULT_OBJECTS（models/app.js:201 页面 planetDisplay 缺省）/ TRADITION_OBJECTS
DEFAULT_OBJECTS: tuple[str, ...] = (
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "North Node", "South Node", "Pars Fortuna", "Asc", "MC",
)
TRADITION_OBJECTS: tuple[str, ...] = (
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "North Node", "South Node", "Dark Moon", "Purple Clouds",
    "Asc", "Desc", "MC", "IC",
)


def _jq_split_degree(degree: Any) -> tuple[int, int]:
    """JieQiChartsMain.js:661-672 splitDegree（节气页本地版：负数先 +360，度 = floor(d % 30)）。"""
    d = _js_number(degree)
    if math.isnan(d):
        return 0, 0
    if d < 0:
        d += 360
    rem = math.fmod(d, 30)
    deg = math.floor(rem)
    return deg, math.floor((rem - deg) * 60)


def _jq_sign_from_lon(lon: Any) -> str | None:
    """JieQiChartsMain.js:674-684 signFromLon。"""
    if lon is None or lon is _UNDEFINED:
        return None
    num = _js_number(lon)
    if math.isnan(num):
        return None
    val = math.fmod(num, 360)
    if val < 0:
        val += 360
    return LIST_SIGNS[math.floor(val / 30) % 12]


def _jq_house_start_mode(fields: Any) -> int:
    """JieQiChartsMain.js:686-692 resolveHouseStartMode：缺省 八字起宫。"""
    value = field_value(fields, "houseStartMode")
    if value is not None:
        return SZ_HOUSE_START_ASC if _js_parse_int(value) == SZ_HOUSE_START_ASC else SZ_HOUSE_START_BAZI
    return SZ_HOUSE_START_BAZI


def _jq_floor_div30(value: Any) -> float:
    num = _js_number(value)
    return math.nan if math.isnan(num) else float(math.floor(num / 30))


def jieqi_asc_sign_index(root_obj: Any, chart: dict[str, Any], fields: Any) -> float:
    """JieQiChartsMain.js:694-717 computeAscSignIndex：ASC 赤经起宫（或八字起宫：日赤经座 − 时支座 − 5）；无 Asc → -1。
    八字起宫要 chart.nongli.bazi（Java /chart 才挂）——缺则按 ASC 起（上游同一回退分支）。返回 NaN 表示 Asc 无赤经。"""
    objects = _as_list(chart.get("objects"))
    asc = next((o for o in objects if isinstance(o, dict) and o.get("id") == "Asc"), None)
    sun = next((o for o in objects if isinstance(o, dict) and o.get("id") == "Sun"), None)
    if asc is None:
        return -1.0
    asc_idx = _jq_floor_div30(asc.get("ra", _UNDEFINED))
    if _jq_house_start_mode(fields) == SZ_HOUSE_START_ASC:
        return asc_idx
    nongli = chart.get("nongli") if isinstance(chart.get("nongli"), dict) else None
    root_nongli = root_obj.get("nongli") if isinstance(root_obj, dict) and isinstance(root_obj.get("nongli"), dict) else None
    bazi = (nongli or {}).get("bazi") or (root_nongli or {}).get("bazi")
    if not bazi or not sun:
        return asc_idx
    time_col = bazi.get("time") if isinstance(bazi, dict) else None
    branch = time_col.get("branch") if isinstance(time_col, dict) else None
    timezi = branch.get("cell") if isinstance(branch, dict) else None
    timesig = SZ_ZI_SIGN.get(_js_str(timezi)) if timezi else None
    tmsigidx = LIST_SIGNS.index(timesig) if timesig in LIST_SIGNS else -1
    if tmsigidx < 0:
        return asc_idx
    sunidx = _jq_floor_div30(sun.get("ra", _UNDEFINED))
    if math.isnan(sunidx):
        return math.nan
    return float((int(sunidx) - tmsigidx - 5 + 24) % 12)


def _jq_house_full_label(house: Any, idx: int, asc_sign_index: float) -> str:
    """JieQiChartsMain.js:719-737 houseFullLabel：`{地支}—{星次}—{星座}座—第N宫`。"""
    house_id = house.get("id") if isinstance(house, dict) and _js_truthy(house.get("id")) else None
    house_name = msg(house_id) or f"第{idx + 1}宫"
    sign = _jq_sign_from_lon(house.get("lon") if isinstance(house, dict) else None)
    if not sign:
        return house_name
    sign_idx = LIST_SIGNS.index(sign)
    if not math.isnan(asc_sign_index) and asc_sign_index >= 0:
        house_name = f"第{(sign_idx - int(asc_sign_index) + 12) % 12 + 1}宫"
    zi = SZ_SIGN_ZI.get(sign) or ""
    area = SZ_SIGN_AREA[sign_idx]
    sign_name = SIGN_CN.get(sign.lower()) or msg(sign)   # AstroText.AstroMsgCN[sign]（星座条目 = SIGNS cn）
    return f"{zi}—{area}—{sign_name}座—{house_name}"


def _jq_ra_cmp(a: dict[str, Any], b: dict[str, Any]) -> int:
    """JieQiChartsMain.js:757-765 环形赤经序（跨 0° 两向对称判）。"""
    ra_a, ra_b = _js_number(a.get("ra", _UNDEFINED)), _js_number(b.get("ra", _UNDEFINED))
    if ra_a > 300 and ra_b < 30:
        return -1
    if ra_b > 300 and ra_a < 30:
        return 1
    diff = ra_a - ra_b
    if math.isnan(diff) or diff == 0:
        return 0
    return -1 if diff < 0 else 1


def build_jieqi_su_section(chart_obj: Any, fields: Any, planet_display: Any = DEFAULT_OBJECTS) -> str:
    """JieQiChartsMain.js:739-821 buildJieQiSuSection：逐宫「宫位：地支—星次—星座座—第N宫」+ 按二十八宿分组的星曜行
    （宿内度 = 星赤经 − 该宿距星赤经，无距星表回落黄道座内度）。`planet_display` = 页面星表（上游 props.planetDisplay，
    缺省 DEFAULT_OBJECTS）；传空 → 传统星（isTraditionPlanet）。"""
    obj = chart_obj if isinstance(chart_obj, dict) else {}
    chart = obj.get("chart") if isinstance(obj.get("chart"), dict) else {}
    houses = _as_list(chart.get("houses"))
    objects = [o for o in _as_list(chart.get("objects")) if isinstance(o, dict)]
    asc_sign_index = jieqi_asc_sign_index(obj, chart, fields)
    visible = set(planet_display) if planet_display else None
    fixed_su = _as_list(chart.get("fixedStarSu28"))
    lines: list[str] = []
    for idx, house in enumerate(houses):
        lines.append(f"宫位：{_jq_house_full_label(house, idx, asc_sign_index)}")
        house_id = house.get("id") if isinstance(house, dict) else None
        in_house = [
            o for o in objects
            if o.get("house") == house_id and (o.get("id") in visible if visible is not None else o.get("id") in TRADITION_OBJECTS)
        ]
        in_house = sorted(in_house, key=cmp_to_key(_jq_ra_cmp))
        if not in_house:
            lines.extend(["二十八宿：无", "星曜：无", ""])
            continue
        su_map: dict[str, list[dict[str, Any]]] = {}
        for o in in_house:
            su = _js_str(o["su28"]) if _js_truthy(o.get("su28")) else "未知宿"
            su_map.setdefault(su, []).append(o)

        def su_key(a: str, b: str) -> int:
            ia = SU28_ORDER.index(a) if a in SU28_ORDER else -1
            ib = SU28_ORDER.index(b) if b in SU28_ORDER else -1
            if ia < 0 and ib < 0:
                return (a > b) - (a < b)
            if ia < 0:
                return 1
            if ib < 0:
                return -1
            return ia - ib

        for su in sorted(su_map, key=cmp_to_key(su_key)):
            lines.append(f"二十八宿：{su}")
            ref = next((it for it in fixed_su if isinstance(it, dict) and it.get("name") == su), None)
            for o in su_map[su]:
                radeg = _js_number(o.get("ra", _UNDEFINED))
                if not math.isnan(radeg) and isinstance(ref, dict) and ref.get("ra") is not None:
                    radeg = radeg - _js_number(ref["ra"])
                    if radeg < 0:
                        radeg += 360
                else:
                    radeg = _js_number(o.get("signlon", _UNDEFINED))
                deg, minute = _jq_split_degree(radeg)
                label = f"{msg(o.get('id', _UNDEFINED))} ({_format_planet_house_info(o)})"
                lines.append(f"星曜：{label} {deg}˚{su}{minute}分")
        lines.append("")
    return "\n".join(lines).strip()

__all__ = [
    "DEFAULT_OBJECTS",
    "SU28_ORDER",
    "SZ_SIGN_AREA",
    "SZ_ZI_SIGN",
    "TRADITION_OBJECTS",
    "build_jieqi_su_section",
    "jieqi_asc_sign_index",
    "LIST_POINTS",
    "NAK_LORD_CN",
    "PLANET_HOUSE_INFO_NOTE",
    "SIGN_CN",
    "CLASSICAL_PARAM_SPEC_NON_DEFAULT",
    "aspect_text",
    "build_aspect_section",
    "build_base_info_lines",
    "build_classical_analysis_lines",
    "build_classical_calibre_line",
    "build_classical_section",
    "build_dispositor_chain_lines",
    "build_dispositor_tail_lines",
    "build_dodeca_lines",
    "build_house_cusp_lines",
    "build_house_system_ruler_lines",
    "build_info_section",
    "build_lifespan_lines",
    "build_lots_section",
    "build_pattern_overview_lines",
    "build_planet_section",
    "build_possibility_lines",
    "build_star_and_lot_position_lines",
    "classical_backend_overrides",
    "clean_lines",
    "dodeca_lon_of",
    "field_value",
    "format_speed",
    "lifespan_name",
    "round3",
    "section_text",
]
