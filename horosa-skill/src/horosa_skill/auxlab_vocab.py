"""辅盘「变换盘」「黄道制」的词表（上游 v3.14.0，`input_fields.Vocabulary` 机制）。

这两页的选项只有一个来源：上游 `utils/transformCharts.js`（TRANSFORM_GROUPS / TRANSFORM_PLANETS / TRANSFORM_HOUSES /
TRANSFORM_PAGE_SETTINGS / ZODIAC_VERSIONS / ZODIAC_PAGE_SETTINGS），本仓逐字 vendor 在
`horosa-core-js/src/vendor/utils/transformCharts.js`。Python 侧要这几张表做三件事——schema 校验（认不出即拒，后端对
认不出的变换静默退回倒置盘、对认不出的黄道版本静默退回十三星座甲本）、决定请求体带哪些键、给 guidance / 技法卡写说明——
所以这里抄了值、中文名与「这种变换用到哪些选项」，由 `tests/test_sync314_labs_vocab.py` 对 vendored JS 逐项比
（上游加一种变换 / 改一个名字 / 改缺省即红）。说明文字（desc）不抄：正文里的那一句由 vendored transformSnapshotLines 出。
"""
from __future__ import annotations

from typing import Any

from horosa_skill.input_fields import Vocabulary

# ───────────────────────── 变换盘 ─────────────────────────

# (分组名, ((值, 中文名, 用到的选项), …))：顺序 = 上游 TRANSFORM_GROUPS；选项名 = 页面设置键（planet / shift / house / variant）。
TRANSFORM_GROUPS: tuple[tuple[str, tuple[tuple[str, str, tuple[str, ...]], ...]], ...] = (
    ("旋转与翻转", (
        ("inverted", "倒置盘", ("variant",)),
        ("sunRise", "日升盘", ("variant",)),
        ("superimposed", "叠置盘", ("planet", "shift")),
        ("antiscia", "映点盘", ()),
        ("contraAntiscia", "反映点盘", ()),
    )),
    ("分度重排", (
        ("decanate", "旬盘", ()),
        ("novien", "九分盘", ("variant",)),
        ("nodeHouses", "北交宫盘", ("variant",)),
        ("vertical", "垂直黄道盘", ()),
    )),
    ("地方盘", (
        ("geodeticLong", "地理盘 · 经度作中天赤经", ()),
        ("geodeticRa", "地理盘 · 经度作中天黄经", ()),
        ("localityArmc", "地方盘 · 中天赤经(经典)", ()),
        ("localityMc", "地方盘 · 中天黄经(经典)", ()),
    )),
    ("换中心与换时刻", (
        ("planetCentered", "行星中心盘", ("planet",)),
        ("persona", "人格盘", ("planet",)),
        ("epoch", "受孕盘", ("house",)),
    )),
    ("行星根数", (
        ("planetNodes", "行星升交点", ()),
        ("planetNodesSouth", "行星降交点", ()),
        ("perihelion", "近日点", ()),
        ("aphelion", "远日点", ()),
        ("secondFocus", "第二焦点", ()),
    )),
    ("坐标类比", (
        ("analogLatitude", "黄纬类比", ()),
        ("analogRightAscension", "赤经类比", ()),
        ("analogDeclination", "赤纬类比", ()),
        ("analogDeclinationFold", "赤纬折叠", ()),
        ("analogDeclinationBack", "赤纬反折", ()),
        ("analogAzimuth", "方位角类比", ()),
        ("analogAzimuthLocal", "本地地平类比", ()),
        ("analogAltitude", "高度类比", ()),
        ("housePlacidus", "宫位类比 · Placidus", ()),
        ("houseRegiomontanus", "宫位类比 · Regiomontanus", ()),
        ("houseCampanus", "宫位类比 · Campanus", ()),
        ("houseTopocentric", "宫位类比 · Topocentric", ()),
    )),
)

TRANSFORM_KIND_LABELS: dict[str, str] = {value: label for _group, kinds in TRANSFORM_GROUPS for value, label, _opts in kinds}
TRANSFORM_KIND_OPTIONS: dict[str, tuple[str, ...]] = {value: opts for _group, kinds in TRANSFORM_GROUPS for value, _label, opts in kinds}
TRANSFORM_KINDS: tuple[str, ...] = tuple(TRANSFORM_KIND_LABELS)

# 基准星（上游 TRANSFORM_PLANETS，十星；中文名 = AstroMsgCN）与对应宫头（TRANSFORM_HOUSES）。
TRANSFORM_PLANET_LABELS: dict[str, str] = {
    "Sun": "太阳", "Moon": "月亮", "Mercury": "水星", "Venus": "金星", "Mars": "火星",
    "Jupiter": "木星", "Saturn": "土星", "Uranus": "天王星", "Neptune": "海王星", "Pluto": "冥王星",
}
TRANSFORM_PLANETS: tuple[str, ...] = tuple(TRANSFORM_PLANET_LABELS)
TRANSFORM_HOUSES: tuple[int, ...] = tuple(range(1, 13))
TRANSFORM_VARIANT_LABELS: dict[str, str] = {"improved": "改进", "classic": "经典"}

# 页面缺省（上游 TRANSFORM_PAGE_SETTINGS 的 def）：没给的选项按它补，再只下发这种变换用到的那几个。
TRANSFORM_DEFAULTS: dict[str, Any] = {"kind": "inverted", "planet": "Moon", "shift": False, "house": 1, "variant": "improved"}

# 入参键（= 后端请求键，Java AstroExtraController 白名单同名）→ 页面设置键。
TRANSFORM_FIELD_TO_SETTING: dict[str, str] = {
    "transformKind": "kind", "transformPlanet": "planet", "transformShift": "shift",
    "transformHouse": "house", "transformVariant": "variant",
}
TRANSFORM_SETTING_TO_FIELD: dict[str, str] = {setting: field for field, setting in TRANSFORM_FIELD_TO_SETTING.items()}
TRANSFORM_OPTION_LABELS: dict[str, str] = {"planet": "基准星", "shift": "宫位同转", "house": "对应宫头", "variant": "口径"}

# 别名只收有唯一含义的：中文名（去掉「 · 」两侧空格的写法由 _vocab_key 归一）、通行英文名。
# 不收「九分盘」以外会和别的技法撞名的简称（印占 D9 也叫九分盘，路由层不拿它选技法；作为本工具的入参值没有歧义）。
_KIND_ALIASES: dict[str, tuple[str, ...]] = {
    "inverted": ("倒置", "inverted chart"),
    "sunRise": ("日升", "sunrise", "sunrise chart", "solar chart"),
    "superimposed": ("叠置", "superimposed chart"),
    "antiscia": ("映点", "antiscia chart", "antiscion"),
    "contraAntiscia": ("反映点", "contra-antiscia", "contrantiscia", "contra antiscia chart"),
    "decanate": ("旬", "decan chart", "decanate chart"),
    "novien": ("九分", "novien chart"),
    "nodeHouses": ("北交宫", "node houses", "nodal houses"),
    "vertical": ("垂直黄道", "vertical zodiac"),
    "geodeticLong": ("地理盘经度作中天赤经", "geodetic", "geodetic chart"),
    "geodeticRa": ("地理盘经度作中天黄经",),
    "localityArmc": ("地方盘中天赤经",),
    "localityMc": ("地方盘中天黄经",),
    "planetCentered": ("行星中心", "日心盘", "planet centered", "planetocentric", "heliocentric", "heliocentric chart"),
    "persona": ("人格", "persona chart"),
    "epoch": ("受孕", "epoch chart", "prenatal epoch"),
    "planetNodes": ("升交点盘", "planetary nodes"),
    "planetNodesSouth": ("降交点盘", "planetary south nodes"),
    "perihelion": ("近日点盘", "perihelia"),
    "aphelion": ("远日点盘", "aphelia"),
    "secondFocus": ("第二焦点盘", "second focus"),
    "analogLatitude": ("latitude analog",),
    "analogRightAscension": ("right ascension analog", "ra analog"),
    "analogDeclination": ("declination analog",),
    "analogDeclinationFold": (),
    "analogDeclinationBack": (),
    "analogAzimuth": ("方位类比", "azimuth analog"),
    "analogAzimuthLocal": ("local horizon analog",),
    "analogAltitude": ("altitude analog",),
    "housePlacidus": ("宫位类比 Placidus",),
    "houseRegiomontanus": ("宫位类比 Regiomontanus",),
    "houseCampanus": ("宫位类比 Campanus",),
    "houseTopocentric": ("宫位类比 Topocentric",),
}

_PLANET_ALIASES: dict[str, tuple[str, ...]] = {
    "Sun": ("日",), "Moon": ("月",), "Mercury": ("水",), "Venus": ("金",), "Mars": ("火",), "Jupiter": ("木",), "Saturn": ("土",),
    "Uranus": ("天王",), "Neptune": ("海王",), "Pluto": ("冥王",),
}

TRANSFORM_KIND_VOCAB = Vocabulary(
    "transformKind",
    {value: (TRANSFORM_KIND_LABELS[value], *_KIND_ALIASES[value]) for value in TRANSFORM_KINDS},
    labels={value: label + ("（缺省）" if value == TRANSFORM_DEFAULTS["kind"] else "") for value, label in TRANSFORM_KIND_LABELS.items()},
)
TRANSFORM_PLANET_VOCAB = Vocabulary(
    "transformPlanet",
    {value: (label, *_PLANET_ALIASES[value]) for value, label in TRANSFORM_PLANET_LABELS.items()},
    labels={value: label + ("（缺省）" if value == TRANSFORM_DEFAULTS["planet"] else "") for value, label in TRANSFORM_PLANET_LABELS.items()},
)
TRANSFORM_VARIANT_VOCAB = Vocabulary(
    "transformVariant",
    {"improved": ("改进", "改进档"), "classic": ("经典", "经典档", "classical")},
    labels={"improved": "改进（缺省）", "classic": "经典（四轴留在本命；现代宫主表白羊主冥王、天蝎主火星）"},
)
TRANSFORM_HOUSE_VOCAB = Vocabulary(
    "transformHouse",
    {house: (str(house), f"第{house}宫", f"{house}宫") for house in TRANSFORM_HOUSES},
    labels={house: f"第 {house} 宫" + ("（缺省）" if house == TRANSFORM_DEFAULTS["house"] else "") for house in TRANSFORM_HOUSES},
    numeric=True,
)

def transform_field_applies(payload: dict[str, Any], field: str) -> bool:
    """这次调用的变换种类用不用得上 `field`（transformPlanet / transformShift / transformHouse / transformVariant）。

    技法卡据此只回显参与计算的选项（倒置盘不印「对应宫头=1」）；transformKind 本身恒适用，认不出的种类按都不适用。"""
    setting = TRANSFORM_FIELD_TO_SETTING.get(field)
    if setting is None or setting == "kind":
        return True
    kind = payload.get("transformKind") or TRANSFORM_DEFAULTS["kind"]
    return setting in TRANSFORM_KIND_OPTIONS.get(kind, ())


def transform_request_fields(settings: dict[str, Any]) -> dict[str, Any]:
    """= 上游 transformRequestOptions(settings, transformKindDef(settings.kind))：只发这种变换真正用到的选项。

    JS 工具用 vendored 上游函数把同一份设置重算一遍，runner 逐键比对（不一致即 tool.transformchart_request_mismatch）。"""
    options = TRANSFORM_KIND_OPTIONS[settings["kind"]]
    out: dict[str, Any] = {"transformKind": settings["kind"]}
    if "planet" in options:
        out["transformPlanet"] = settings["planet"]
    if "shift" in options:
        out["transformShift"] = 1 if settings["shift"] else 0
    if "house" in options:
        out["transformHouse"] = settings["house"]
    if "variant" in options:
        out["transformVariant"] = settings["variant"]
    return out


# ───────────────────────── 黄道制 ─────────────────────────

# 上游 ZODIAC_VERSIONS（值, 中文名），顺序同上游；缺省 = ZODIAC_PAGE_SETTINGS.version 的 def。
ZODIAC_VERSIONS: tuple[tuple[str, str], ...] = (
    ("z13a", "十三星座 · 甲本"), ("z13iau", "十三星座 · 官方边界"), ("z13true", "十三星座 · 官方边界实测"),
    ("z13b", "十三星座 · 乙本"), ("z13c", "十三星座 · 丙本"), ("z13ab", "十三星座 · 甲乙均值"),
    ("z13ac", "十三星座 · 甲丙均值"), ("z13bc", "十三星座 · 乙丙均值"), ("z13cancer", "十三星座 · 巨蟹零度起"),
    ("z13cancerClassic", "十三星座 · 巨蟹零度起(旧排法)"),
    ("z13mid", "十三星座 · 中点"), ("z14", "十四星座 · 等分"),
    ("z12a", "十二段 · 甲本"), ("z12b", "十二段 · 乙本"), ("z12c", "十二段 · 丙本"), ("z12d", "十二段 · 丁本"),
    ("z12e", "十二段 · 戊本"), ("z12f", "十二段 · 综合本"), ("z12g", "十二段 · 己本"),
)
ZODIAC_VERSION_LABELS: dict[str, str] = dict(ZODIAC_VERSIONS)
ZODIAC_VERSION_DEFAULT = "z13a"
# 不参与黄道制计算的本命盘口径键：后端一律把各点换回回归黄经再分段（zodiac_systems._body_rows），四轴与宫制无关。
# 共享引擎实测（1990-05-15 上海）：hsys 0 / 1 / 3 三张结果逐字节相同；恒星黄道三种岁差下只有朔望点的回归黄经差 0.000334°（约 1″），
# 落段、星座、换星座时刻与十三宫全部相同。schema 据此不广告这三个键，技法卡不回显它们。
ZODIAC_UNUSED_CHART_KEYS: tuple[str, ...] = ("hsys", "zodiacal", "siderealAyanamsa")

ZODIAC_VERSION_VOCAB = Vocabulary(
    "zodiacVersion",
    {value: (label,) for value, label in ZODIAC_VERSIONS},
    labels={value: label + ("（缺省）" if value == ZODIAC_VERSION_DEFAULT else "") for value, label in ZODIAC_VERSIONS},
)
