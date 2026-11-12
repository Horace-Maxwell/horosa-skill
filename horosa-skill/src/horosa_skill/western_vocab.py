"""西占 / 推运 / 七政择日的枚举类设置词表（v0.50.0，`input_fields.Vocabulary` 机制）。

一个设置只有一张表：规范值（= 上游 / 引擎认的线上值）+ 认得的别名（大小写 / 中文名 / 布尔，只收有唯一含义的）。
schema 层用 `field_validator_for(vocab.parse, 字段)` 挂成 BeforeValidator：认得 → 规范值（做了解读的进 warnings），
认不出 → `tool.invalid_option`（`details.options` / 逐字段 `options` 是全表）。于是后端拿到的值、[起盘信息] 的
「古典口径（非默认项）」行、技法卡三处都从同一个规范值来——不会再有「行里写真交点、引擎按平交点算」。

古典口径键的值域取自 `engine.astro_snapshot.CLASSICAL_PARAM_SPEC_NON_DEFAULT`（上游 classicalParamSpec.js 的
send:'nonDefault' 子集，与 vendored JS 由测试互锚）；这里只补每个值的中文名与别名，`tests/test_western_vocab.py`
逐键断言两边的值域相同（上游加档 / 删档即红）。
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping
from functools import cache
from typing import Any

from horosa_skill.input_fields import (
    FieldIssue,
    Parsed,
    Vocabulary,
    clean_text,
    is_blank,
)

# ───────────────────────── 古典口径（classicalParamSpec.js send:'nonDefault'）─────────────────────────

_SWITCH_ON = ("true", "on", "yes", "开", "是", "启用")
_SWITCH_OFF = ("false", "off", "no", "关", "否", "不启用")

# spec 键 → {规范值: (中文名, 别名…)}。中文名取自上游 CLS_CALIBRE_LABELS（astroAiSnapshot.js:324-372）与 BirthInput 字段说明；
# 只列有唯一含义的别名（「托勒密」不作 termsVariant 的别名：1 / 2 两个托勒密界本都叫这个名）。开关键（spec options=None）
# 一律 0 / 1，另认 true/false/开/关。
_CLASSICAL_CHOICES: dict[str, dict[Any, tuple[str, ...]]] = {
    "termsVariant": {0: ("埃及界（缺省）", "埃及", "埃及界", "egyptian", "egypt"), 1: ("托勒密·校勘本",), 2: ("托勒密·经典传本",),
                     3: ("迦勒底(推演)", "迦勒底", "chaldean"), 4: ("自定义界表", "自定义", "custom")},
    "geminiBoundEmended": {0: ("原序（缺省）", *_SWITCH_OFF), 1: ("校勘对调", *_SWITCH_ON)},
    "leoBoundFirst": {0: ("缺省", *_SWITCH_OFF), 1: ("土星优先", *_SWITCH_ON)},
    "triplicity": {"Dorothean": ("Dorotheus 三主（缺省）", "dorotheus", "多罗修斯"), "Ptolemaic": ("托勒密二主", "托勒密", "ptolemy"),
                   "PtolemaicWaterVariant": ("托勒密·水象变体", "托勒密水象变体")},
    "dignityDebilities": {1: ("计负分（缺省）", *_SWITCH_ON), 0: ("不计负分", *_SWITCH_OFF)},
    "almutenTripMode": {"all": ("三主全计（缺省）",), "sectRulerOnly": ("仅当值主",)},
    "planetaryHourMethod": {"sunrise": ("日出起算等长时（缺省）",), "unequal": ("昼夜不等时(传统)", "不等时"), "equal24": ("廿四时等分",)},
    "sectBuffer": {"geo": ("地心地平（缺省）",), "ptolemy5": ("Ptolemy 5°缓冲",), "apparent": ("视地平(含折射)", "视地平")},
    "sunriseMode": {"center": ("日心·不计折射（缺省）",), "apparent": ("日面上缘·含大气折射",)},
    "westNodeType": {"mean": ("平交点（缺省）", "平交点", "平", "平均交点", "mean node", "false"), "true": ("真交点", "真", "true node")},
    "nodeExaltation": {0: ("不参与（缺省）", *_SWITCH_OFF), 1: ("参与", *_SWITCH_ON)},
    "cazimiOrb": {17 / 60: ("17′（缺省）",), 16 / 60: ("16′",), 1: ("1°",)},
    "combustOrb": {8.5: ("8.5°（缺省）",), 8: ("8°",), 15: ("15°",)},
    "combustOwnChariotExempt": {0: ("关（缺省）", *_SWITCH_OFF), 1: ("界内三分内免(own chariot)", *_SWITCH_ON)},
    "underBeamsOrb": {17: ("17°（缺省）",), 15: ("15°",)},
    "vocMode": {"classic": ("经典（缺省）", "经典", "lilly", "backend"), "by_orb": ("容许度12°30′",), "by_sign_perfect": ("本座内须完成(现代)",),
                "by_sign_orb": ("本座内入容许度(16c)",), "kenodromia": ("30°法(希腊化)",), "exempt4": ("无入相+四座豁免(中世纪)",)},
    "vocIncludeOuter": {0: ("不计（缺省）", *_SWITCH_OFF), 1: ("计三王星", *_SWITCH_ON)},
    "westLilithType": {"mean": ("平均远地点（缺省）", "平均远地点", "平", "平均", "false"), "true": ("真实远地点", "真实", "真", "osculating")},
    "topocentricMoon": {0: ("不修正（缺省）", *_SWITCH_OFF), 1: ("站心修正", *_SWITCH_ON)},
    "viaCombustaVariant": {"standard": ("标准（缺省）",), "narrow": ("窄口径(天秤28°–天蝎7°)",), "scorpioFull": ("天秤后15°+天蝎全宫",),
                           "bothFull": ("天秤+天蝎全段",)},
    "lotReversal": {1: ("按昼夜反转（缺省）", *_SWITCH_ON), 0: ("恒昼式(不随昼夜反转)", *_SWITCH_OFF)},
    "lotsDocReverse": {0: ("关（缺省）", *_SWITCH_OFF), 1: ("开", *_SWITCH_ON)},
    "hermeticLotsReversal": {1: ("按昼夜反转（缺省）", *_SWITCH_ON), 0: ("恒同式(批判本校勘)", *_SWITCH_OFF)},
    "erosConstruction": {"paulus": ("金星·水星系（缺省）",), "valens": ("Valens 式(福点·精神系)",)},
    "lotFortuneVariant": {"standard": ("标准昼夜式（缺省）",), "moonAboveNight": ("月在地平上恒夜式",)},
    "lotFatherCombustAlt": {0: ("关（缺省）", *_SWITCH_OFF), 1: ("土星伏替代式(Dorotheus 系)", *_SWITCH_ON)},
    "lotProjection": {"portion": ("度数投射（缺省）",), "sign": ("整星座投射", "整星座")},
    "orbSystem": {"perObject": ("星体轨任一覆盖（缺省）",), "byAspect": ("按相位名",), "wholeSign": ("整星座位相",),
                  "wholeSignMoiety": ("整星座内半距和",)},
    "luminaryOrbBonus": {0: ("0%（缺省）",), 10: ("10%",), 20: ("20%",), 30: ("30%",)},
    "aspectIncludeCusps": {0: ("关（缺省）", *_SWITCH_OFF), 1: ("开(≤3°)", *_SWITCH_ON)},
    "aspectIncludeLots": {0: ("关（缺省）", *_SWITCH_OFF), 1: ("开(受体·≤3°)", *_SWITCH_ON)},
    "aspectIncludeMidpoints": {0: ("关（缺省）", *_SWITCH_OFF), 1: ("开(日月四轴·硬相≤1.5°)", *_SWITCH_ON)},
    "antisciaOrb": {0.5: ("0.5°",), 1: ("1°（缺省）",), 1.5: ("1.5°",), 2: ("2°",), 3: ("3°",)},
    "fixedStarOrbMode": {"school": ("按流派平轨（缺省）",), "byMagnitude": ("按星等",)},
    "fixedStarOrb": {1: ("1°（缺省）",), 1.5: ("1.5°",), 2: ("2°",), 3: ("3°",), 5: ("5°",)},
    "stationMarking": {"off": ("仅逆行R标（缺省）",), "exactWindow": ("距留点≤1日",), "distance": ("距留点≤2′",), "absSpeed": ("日速<1′",),
                       "relSpeed": ("日速<3%均速",)},
    "solarReturnVariant": {"precise": ("精确回归（缺省）",), "hellenistic": ("希腊式(月定上升)",)},
    "returnLatitudeMode": {"ecliptic": ("黄道度（缺省）",), "withLatitude": ("计入黄纬(Umar al-Tabari 法)",)},
    "houseCuspAdvance": {5: ("5°（缺省）",), 3: ("3°",), 1: ("1°",), 0: ("0°",)},
    "vulcanCalc": {"off": ("关（缺省）",), "weston": ("轨道根数法",), "baker": ("水星系推算",)},
}

# 请求体里的字段名 → spec 键（恒星轨两键 BirthInput 用后端名 starOrb / starOrbMode，前端名 fixedStarOrb* 照收）。
CLASSICAL_FIELD_KEYS: dict[str, str] = {
    **{key: key for key in _CLASSICAL_CHOICES if key not in ("fixedStarOrb", "fixedStarOrbMode")},
    "starOrb": "fixedStarOrb", "fixedStarOrb": "fixedStarOrb",
    "starOrbMode": "fixedStarOrbMode", "fixedStarOrbMode": "fixedStarOrbMode",
}
# BirthInput 声明着的那些（BeforeValidator 挂在这些字段上）；前端名 fixedStarOrb / fixedStarOrbMode 未声明（走 extra，
# 键名原样保留：宿占死键表、judgeLayerHeadless 双名回退都按名认它们），由 BirthInput 的模型级前置校验判同一张词表。
CLASSICAL_DECLARED_FIELDS: tuple[str, ...] = tuple(name for name in CLASSICAL_FIELD_KEYS if name not in ("fixedStarOrb", "fixedStarOrbMode"))
CLASSICAL_UNDECLARED_FIELDS: tuple[str, ...] = ("fixedStarOrb", "fixedStarOrbMode")


def _strip_default(label: str) -> str:
    return label.replace("（缺省）", "")


# 容许度类键（spec valueType 'float'）：上游页面只给表里几档，但后端 /chart 与判读层（judgeLayerHeadless：「数值键不设档，
# 引擎吃任意有限值」，那是本仓刻意的移植口径）照算任意有限值——所以表外的数照收（在量程内），由「古典口径」行照写
# （classical_backend_overrides 对 float 键不卡档，见那里）。量程外 / 非数拒。cazimi 以度计，17′ 写 0.2833 或 "17′"。
OPEN_ORB_RANGES: dict[str, tuple[float, float]] = {
    "cazimiOrb": (0, 1), "combustOrb": (0, 30), "underBeamsOrb": (0, 30), "antisciaOrb": (0, 30), "fixedStarOrb": (0, 30),
}


class _OrbVocabulary(Vocabulary):
    """表里的档（含别名 17′ / 8.5°）照词表读；表外的有限数在量程内照收（不换档、不进说明）。"""

    def __init__(self, *args: Any, bounds: tuple[float, float], **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.bounds = bounds

    def parse(self, value: Any) -> Parsed:
        try:
            return super().parse(value)
        except FieldIssue as issue:
            from horosa_skill.input_fields import _vocab_number

            number = None if isinstance(value, bool) else _vocab_number(value)
            low, high = self.bounds
            if number is not None and low <= number <= high:
                canonical: Any = int(number) if number == int(number) else number
                return Parsed(canonical) if canonical == value else Parsed(
                    canonical, f"「{value}」按 {canonical}° 读。", f"'{value}' was read as {canonical}°.")
            issue.zh += f"容许度要是 {low:g}–{high:g}° 的数（表内档：{'、'.join(self.labels.values())}）。"
            issue.en += f" An orb must be a number {low:g}–{high:g}° (listed steps: {', '.join(map(str, self.labels))})."
            raise


@cache
def classical_vocabulary(field_name: str) -> Vocabulary:
    """请求字段名 → 它的词表（值域 = spec 的 options；开关键 0 / 1；容许度类另收量程内任意数）。"""
    key = CLASSICAL_FIELD_KEYS[field_name]
    choices = _CLASSICAL_CHOICES[key]
    numeric = all(isinstance(value, (int, float)) for value in choices)
    args = (field_name, {value: (_strip_default(label), *aliases) for value, (label, *aliases) in choices.items()})
    kwargs: dict[str, Any] = {"labels": {value: names[0] for value, names in choices.items()}, "numeric": numeric}
    if key in OPEN_ORB_RANGES:
        return _OrbVocabulary(*args, bounds=OPEN_ORB_RANGES[key], **kwargs)
    return Vocabulary(*args, **kwargs)


def classical_vocabulary_options(field_name: str) -> list[dict[str, Any]]:
    return classical_vocabulary(field_name).accepted


def parse_classical(field_name: str, value: Any) -> Any:
    """BeforeValidator 体：空串 = 没给（上游 classicalBackendOverrides 同口径，不下发）；其余必须读成规范值。"""
    if value is None or is_blank(value):
        return None
    from horosa_skill.input_fields import field_validator_for

    return field_validator_for(classical_vocabulary(field_name).parse, field_name)(value)


def classical_spec_values() -> dict[str, tuple[Any, ...]]:
    """本表的值域（给守卫与上游 spec 对表用）。"""
    return {key: tuple(choices) for key, choices in _CLASSICAL_CHOICES.items()}


# ───────────────────────── 十年大运（上游 utils/decennials.js + AstroDecennials.js）─────────────────────────

_DECENNIAL_PLANETS: dict[str, tuple[str, ...]] = {
    "Sun": ("太阳", "日"), "Moon": ("月亮", "月", "太阴"), "Mercury": ("水星", "水"), "Venus": ("金星", "金"),
    "Mars": ("火星", "火"), "Jupiter": ("木星", "木"), "Saturn": ("土星", "土"),
}
DECENNIAL_VOCABULARIES: dict[str, Vocabulary] = {
    "startMode": Vocabulary(
        "startMode",
        {"sect_light": ("得时光体", "sect light", "sect"), **_DECENNIAL_PLANETS},
        labels={"sect_light": "得时光体（缺省，昼生日 / 夜生月）", **{p: names[0] for p, names in _DECENNIAL_PLANETS.items()}},
    ),
    "orderType": Vocabulary("orderType", {"zodiacal": ("实际黄道次序", "黄道"), "chaldean": ("迦勒底星序", "迦勒底")},
                            labels={"zodiacal": "实际黄道次序（缺省）", "chaldean": "迦勒底星序"}),
    "dayMethod": Vocabulary("dayMethod", {"valens": ("Valens（精确）",), "hephaistio": ("Hephaistio（原表日数）", "hephaestio")},
                            labels={"valens": "Valens（精确，缺省）", "hephaistio": "Hephaistio（原表日数）"}),
    "calendarType": Vocabulary("calendarType", {"calendar_360": ("360", "360天", "traditional"), "calendar_365_25": ("365.25", "365.25天", "actual", "julian")},
                               labels={"calendar_360": "360天/年（按30天/月换算，缺省）", "calendar_365_25": "365.25天/年（儒略年）"}),
    "aiMode": Vocabulary("aiMode", {"l1_all": (), "l2_in_l1": (), "l3_in_l2": (), "l4_in_l3": ()},
                         labels={"l1_all": "输出所有L1（缺省）", "l2_in_l1": "某个L1下全部L2", "l3_in_l2": "某个L2下全部L3", "l4_in_l3": "某个L3下全部L4"}),
}


# ───────────────────────── 七政择日动盘（vendored qizhengElection.js / electionCore.js）─────────────────────────

QIZHENG_ELECTION_VOCABULARIES: dict[str, Vocabulary] = {
    # eclipses：JS `kind === 'lunar' ? 'lunar' : 'solar'`——月食写成中文曾静默搜日食。
    "kind": Vocabulary("kind", {"solar": ("日食", "日", "solar eclipse", "sun"), "lunar": ("月食", "月", "lunar eclipse", "moon")},
                       labels={"solar": "日食（缺省）", "lunar": "月食"}),
    # 二十四山盘别：JS 对认不出的 plate 原样当盘名、mountainPosition 查不到 → 山位行缺。
    "plate": Vocabulary("plate", {"di": ("地盘", "地", "earth"), "tian": ("天盘", "天", "heaven"), "ren": ("人盘", "人", "man")},
                        labels={"di": "地盘（缺省）", "tian": "天盘（+7.5°）", "ren": "人盘（−7.5°）"}),
    # 子正口径不是开关：'true' = 真北（字面就叫 true），'magnetic' = 磁北。布尔 true 读成真北；false / 0 不指任何北向 → 拒。
    "ziZheng": Vocabulary("ziZheng", {"true": ("真北", "true north", "geographic"), "magnetic": ("磁北", "magnetic north")},
                          labels={"true": "真北（缺省）", "magnetic": "磁北（配 declination）"}),
}


_MEAN_TRUE = {"mean": ("平", "平均", "mean node", "false"), "true": ("真", "osculating")}
QIZHENG_ELECTION_VOCABULARIES.update({
    # 后端 webqizhengelectionsrv.pan：`life_mode == 'sunrise' / 'sunset' / 'noon' / 'custom'`，认不出 → 按盘面时刻本身立命（静默）。
    "eleLifeMode": Vocabulary("eleLifeMode", {"sunrise": ("日出", "日出立命"), "sunset": ("日落", "日没", "日落立命"), "noon": ("正午", "中午"),
                                              "custom": ("自定义",)},
                              labels={"sunrise": "日出立命（缺省）", "sunset": "日落立命", "noon": "正午立命", "custom": "自定义时刻（配 eleLifeCustomTime）"}),
    # 后端 `node_type == 'true' ? TRUE_NODE : MEAN_NODE`：「真」/ True 曾静默按平交点算。
    "nodeType": Vocabulary("nodeType", {**_MEAN_TRUE, "true": ("真", "真交点", "true node")},
                           labels={"mean": "平罗计（缺省）", "true": "真罗计"}),
    "lilithType": Vocabulary("lilithType", {**_MEAN_TRUE, "true": ("真", "真远地点", "osculating")},
                             labels={"mean": "平月孛（缺省）", "true": "真月孛（osculating）"}),
    # 后端 azimuthsearch：`{label: swe_id}.get(body, SUN)`——认不出的星曜静默按日搜。
    "body": Vocabulary("body", {"日": ("sun", "太阳"), "月": ("moon", "月亮", "太阴"), "金": ("venus", "金星"), "木": ("jupiter", "木星"),
                                "水": ("mercury", "水星"), "火": ("mars", "火星"), "土": ("saturn", "土星")},
                       labels={"日": "太阳（缺省）", "月": "月亮", "金": "金星", "木": "木星", "水": "水星", "火": "火星", "土": "土星"}),
})


# ───────────────────────── 行星周期（后端 astroextra_parts/cycles.py）─────────────────────────

# 后端 `_SWE_PLANET_BY_NAME.get(str(p1), JUPITER)` / `.get(str(p2), SATURN)`：认不出的星名静默换成木 / 土，配置行却照抄原名
# （「星对：土星-天王」实为木星-天王）；center 认不出 → 地心，配置行照抄原值。
PLANET_CYCLE_VOCABULARIES: dict[str, Vocabulary] = {
    name: Vocabulary(name, {
        "Sun": ("太阳", "日"), "Moon": ("月亮", "月", "太阴"), "Mercury": ("水星",), "Venus": ("金星",), "Mars": ("火星",),
        "Jupiter": ("木星",), "Saturn": ("土星",), "Uranus": ("天王星",), "Neptune": ("海王星",), "Pluto": ("冥王星",),
        "Node": ("北交点", "真交点", "罗睺", "north node", "true node"),
    }, labels={"Sun": "太阳", "Moon": "月亮", "Mercury": "水星", "Venus": "金星", "Mars": "火星", "Jupiter": "木星", "Saturn": "土星",
               "Uranus": "天王星", "Neptune": "海王星", "Pluto": "冥王星", "Node": "北交点（真交点）"})
    for name in ("p1", "p2")
}
PLANET_CYCLE_VOCABULARIES["center"] = Vocabulary(
    "center", {"geo": ("地心", "geocentric"), "helio": ("日心", "heliocentric"), "topo": ("站心", "topocentric")},
    labels={"geo": "地心（缺省）", "helio": "日心", "topo": "站心"},
)


# ───────────────────────── 占星地图落点宫制（上游 AstroAcg.js HSYS_OPTIONS；后端 ACGraph.hsys_code）─────────────────────────

# 后端 `HSYS_MAP.get(name, b'W')`：认不出的宫制名静默按整宫（连缺省 placidus 都不是）。单字母 swe 码后端原样收，这里读成名。
_ACG_HSYS: tuple[tuple[str, str, str], ...] = (
    ("placidus", "普拉西德", "P"), ("koch", "柯赫", "K"), ("whole", "整宫", "W"), ("equal", "等宫(ASC)", "A"), ("equalmc", "等宫(MC)", "D"),
    ("vehlow", "维洛", "V"), ("aries", "0°白羊等宫", "N"), ("porphyry", "波菲利", "O"), ("regiomontanus", "雷乔蒙", "R"),
    ("campanus", "坎帕努斯", "C"), ("alcabitius", "阿卡比特", "B"), ("topocentric", "站心", "T"), ("meridian", "子午宫", "X"),
    ("morinus", "莫林", "M"), ("krusinski", "克鲁辛斯基", "U"), ("apc", "APC", "Y"), ("horizon", "地平宫", "H"), ("gauquelin", "高奎林", "G"),
    ("carter", "卡特", "F"), ("sunshine", "Sunshine", "I"), ("sripati", "Sripati", "S"), ("pullensd", "Pullen SD", "L"), ("pullensr", "Pullen SR", "Q"),
)
ACG_POINT_HSYS = Vocabulary(
    "pointHsys",
    {name: (cn, code, *({"whole": ("wholesign", "整宫制"), "equal": ("equalasc",), "meridian": ("axial",)}.get(name, ()))) for name, cn, code in _ACG_HSYS},
    labels={name: cn + ("（缺省）" if name == "placidus" else "") for name, cn, _code in _ACG_HSYS},
)


# ───────────────────────── 宿占 / 世运卜卦 ─────────────────────────

# 宿占人事十二宫起法（上游 SuZhanMain.js:312-316 0=八字公式 / 1=ASC）：runner 曾 `in (1, True, "1") else 0`——2 静默按 0。
SUZHAN_HOUSE_START = Vocabulary("houseStartMode", {0: ("八字公式", "公式", "formula", "false"), 1: ("上升", "命宫", "asc", "true")},
                                labels={0: "八字公式起宫（缺省）", 1: "上升（ASC）起宫"}, numeric=True)
# 世运卜卦问类（vendored mundaneHorary.js：认不出 → war，静默）。
MUNDANE_HORARY_KIND = Vocabulary("mhKind", {"war": ("战争", "战事"), "weather": ("天候", "天气"), "price": ("物价", "价格")},
                                 labels={"war": "战争（缺省）", "weather": "天候", "price": "物价"})


# ───────────────────────── 卜卦 / 择日（引擎词表，键集由 tests/test_sync311_western.py 对 vendored 引擎逐键核对）─────────────────────────

def _split_cn(label: str) -> tuple[str, ...]:
    parts = [part for part in re.split(r"[/（）()]", label) if part]
    return (label, *parts)


@cache
def divination_vocabularies() -> dict[str, dict[str, Vocabulary]]:
    """horary.category / school、election.topicId / school。引擎对认不出的值静默回落（general / classical / marriage / modern_main），
    快照只写回落后的结果——这里在入口就拒。"""
    from horosa_skill.western_options_doc import ELECTION_SCHOOLS, ELECTION_TOPICS, HORARY_CATEGORIES, HORARY_SCHOOLS

    return {
        "horary": {
            "category": Vocabulary("category", {key: _split_cn(label) for key, label, _house in HORARY_CATEGORIES},
                                   labels={key: label for key, label, _house in HORARY_CATEGORIES}),
            "school": Vocabulary("school", {key: (label,) for key, label, _fields in HORARY_SCHOOLS},
                                 labels={key: label for key, label, _fields in HORARY_SCHOOLS}),
        },
        "election": {
            "topicId": Vocabulary("topicId", {key: _split_cn(label) for key, label in ELECTION_TOPICS},
                                  labels=dict(ELECTION_TOPICS)),
            "school": Vocabulary("school", {key: (label,) for key, label in ELECTION_SCHOOLS}, labels=dict(ELECTION_SCHOOLS)),
        },
    }


# ───────────────────────── 调波数 ─────────────────────────

HARMONIC_MIN, HARMONIC_MAX = 1, 360
_HARMONIC_RE = re.compile(r"^(?:h|H)?\s*(?P<num>[+-]?\d+(?:\.0+)?)$")


def parse_harmonic(value: Any) -> Parsed:
    """调波数 = 1–360 的整数（上游 AstroHarmonicLab clampHarmonic 的页面口径；页面会把夹取后的数写回输入框，无头调用看不到，
    所以越界一律拒，不静默夹成 H1 / H360）。`H7` / `7` / `7.0` 都认。"""
    number: float | None = None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
    elif isinstance(value, str):
        match = _HARMONIC_RE.match(clean_text(value))
        number = float(match.group("num")) if match else None
    if number is not None and math.isfinite(number) and number == int(number) and HARMONIC_MIN <= number <= HARMONIC_MAX:
        canonical = int(number)
        plain = isinstance(value, int) and not isinstance(value, bool)
        return Parsed(canonical) if plain else Parsed(canonical, f"调波数「{value}」按 H{canonical} 读。", f"Harmonic '{value}' was read as H{canonical}.")
    raise FieldIssue(
        "tool.invalid_option",
        f"调波数要是 {HARMONIC_MIN}–{HARMONIC_MAX} 的整数，收到 {value!r}（不会替你夹到边界值）。",
        f"The harmonic must be a whole number {HARMONIC_MIN}–{HARMONIC_MAX}; got {value!r} (it is not clamped to the nearest bound).",
        expected_zh=f"{HARMONIC_MIN}–{HARMONIC_MAX} 的整数（星阙缺省 9）", expected_en=f"a whole number {HARMONIC_MIN}–{HARMONIC_MAX} (Horosa default 9)",
        example=9,
    )


def parse_with(vocabulary: Vocabulary, field_name: str, value: Any) -> Any:
    """BeforeValidator 体（十年大运 / 七政择日旋钮）：空串 = 没给（交给模型 / runner 的缺省），其余必须读成规范值。"""
    if value is None or is_blank(value):
        return None
    from horosa_skill.input_fields import field_validator_for

    return field_validator_for(vocabulary.parse, field_name)(value)


def vocabulary_table(vocabularies: Mapping[str, Vocabulary]) -> dict[str, list[dict[str, Any]]]:
    return {name: vocab.accepted for name, vocab in vocabularies.items()}
