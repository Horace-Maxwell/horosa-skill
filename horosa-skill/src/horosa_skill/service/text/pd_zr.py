"""主限法（含主限盘）与黄道释放（ZR）的快照构造。"""
from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any

from horosa_skill import predictive_text as _ptext
from horosa_skill.service import _clock
from horosa_skill.civil_calendar import _civil_instant_ms_of_str
from horosa_skill.service._common import (
    _civil_date_str_of_ms,
    _civil_wall_ms_of_moment,
    _finite_number,
    _join_lines,
    _msg,
    _render_snapshot_text,
    _require_option,
)
from horosa_skill.service.text.astro_core import (
    _append_planet_house_info,
    _build_aspect_section,
    _build_star_and_lot_position_lines,
    _chart_position_table_lines,
    _normalize_ai_planet_label,
    _top_level_chart_wrap,
)
from horosa_skill.service.text.predictive import (
    _PD_CORE_SUPPORTED_BASE_IDS,
    _directed_config_lines,
    _natal_chart_wrap,
    _natal_config_lines,
    _pd_base_object_id,
    _pd_is_bound_row,
)

# 上游 utils/primaryDirectionSync.js:298-303 SUPPORTED_PD_METHODS（13 法，= 后端 perchart.py 白名单）+ :320-334 PD_METHOD_LABELS。
_PD_METHOD_LABELS: dict[str, str] = {
    "core_alchabitius": "Alchabitius",
    "placidus": "Placidus（半弧）",
    "regiomontanus": "Regiomontanus",
    "campanus": "Campanus",
    "topocentric": "Topocentric",
    "meridian": "Meridian",
    "porphyry": "Porphyry",
    "equal_ecliptic": "Equal（黄道）",
    "equal_hour_circle": "Equal（时圈）",
    "morinus": "Morinus",
    "in_zodiaco_lon": "Along Ecliptic",
    "in_zodiaco_abs": "Edmund Jones",
    "horosa_legacy": "Horosa原方法",
}
# 上游 primaryDirectionSync.js:308-317 SUPPORTED_PD_TIME_KEYS（v3.13.0：38 项，= 后端 perpredict STATIC_TIME_KEY_SCALES
# + 每盘常数 + 动态钥匙）。顺序 = 上游下拉顺序（「（经典）」键紧跟各自的改进键）；值域闸与 agent 文档都从这里取。
_PD_SUPPORTED_TIME_KEYS: tuple[str, ...] = (
    "Ptolemy", "Naibod", "NaibodRA",
    "TrueSolarArc", "TrueSolarArcMean", "VanDam", "SymbolicSolarArc",
    "Simmonite", "BirthdaySunLon", "Kepler", "KeplerClassic", "Brahe", "BraheClassic",
    "AscendantArc", "VerticalArc",
    "Cardano", "Umar", "Wollner", "WollnerClassic", "Plantiko", "SynodicYear", "SynodicYearClassic", "Kundig",
    "SymbolicDegree", "SymbolicYear", "SymbolicMoon", "SymbolicMoonClassic", "SymbolicMonth", "SymbolicWeek",
    "Quarterly", "Quinary", "Septenary", "Novenary", "NovenaryClassic", "Duodenary", "SubDuodenary", "SelfMeasure",
    "User",
)
# 上游 primaryDirectionSync.js:335-374 PD_TIME_KEY_LABELS（逐字；v3.13.0 起 Simmonite/Kepler/Brahe/AscendantArc 改名注明口径）。
_PD_TIME_KEY_LABELS: dict[str, str] = {
    "Ptolemy": "Ptolemy",
    "Naibod": "Naibod",
    "TrueSolarArc": "真太阳弧",
    "TrueSolarArcMean": "真太阳弧（经典 · 平黄赤交角）",
    "SymbolicSolarArc": "太阳弧（黄经）",
    "Kundig": "Kündig",
    "Cardano": "Cardano",
    "Umar": "Umar al-Tabari",
    "Wollner": "Wöllner",
    "WollnerClassic": "Wöllner（经典 0.9860361°）",
    "Plantiko": "Plantiko",
    "Simmonite": "Simmonite（生日赤经日行）",
    "BirthdaySunLon": "生日黄经日行",
    "SynodicYear": "Synodic Year",
    "SynodicYearClassic": "Synodic Year（经典 0.98435°）",
    "Kepler": "Kepler（真午夜赤经日行）",
    "KeplerClassic": "Kepler（经典 · 出生后一日）",
    "Brahe": "Brahe（真午夜赤经日行）",
    "BraheClassic": "Brahe（经典 · 出生后一日）",
    "SymbolicDegree": "Symbolic Degree",
    "SymbolicYear": "Symbolic Year",
    "SymbolicMoon": "Symbolic Moon",
    "SymbolicMoonClassic": "Symbolic Moon（经典 13.167°）",
    "SymbolicMonth": "Symbolic Month",
    "SymbolicWeek": "Symbolic Week（1° = 7 年）",
    "Quarterly": "Quarterly",
    "Quinary": "Quinary",
    "Septenary": "Septenary",
    "Duodenary": "Duodenary",
    "SubDuodenary": "Sub-Duodenary",
    "Novenary": "Novenary",
    "NovenaryClassic": "Novenary（经典 3.3333°）",
    "SelfMeasure": "Self-Measure",
    "NaibodRA": "Naibod-in-RA",
    "AscendantArc": "Ascendant-arc（上升弧计时）",
    "VerticalArc": "Vertical-arc（垂直弧计时）",
    "VanDam": "Van Dam（真弧）",
    "User": "自定义（每年度数）",
}


def _primary_direction_method_text(value: Any) -> str:
    """上游 primaryDirectionSync.js:537 getPdMethodLabel：已知 → 标签；缺省/未知 → 缺省法标签（后端
    perchart.py 同样把白名单外一律回退 core_alchabitius，标签与实算一致）。F20：旧实现只认「核5」，
    把 placidus/regiomontanus 等 v3.6 起已真算的方位法写成「未核验，引擎回退 Alcabitius」——对实算结果撒谎。"""
    return _PD_METHOD_LABELS.get(_msg(value)) or _PD_METHOD_LABELS["core_alchabitius"]


def _primary_direction_time_key_text(value: Any) -> str:
    """上游 primaryDirectionSync.js:544 getPdTimeKeyLabel（38 项；缺省/未知 → Ptolemy）。"""
    return _PD_TIME_KEY_LABELS.get(_msg(value)) or _PD_TIME_KEY_LABELS["Ptolemy"]


# 上游 primaryDirectionSync.js:13-20 方向类型：0 In Zodiaco（缺省）/ 1 In Mundo / 4 Field Plane（v3.13.0 新增；
# 2、3 是后端界推运内部值，前端不下发）。
_PD_DEFAULT_TYPE = 0
_PD_SUPPORTED_TYPES = (0, 1, 4)
_PD_TYPE_LABELS = {0: "黄道（In Zodiaco）", 1: "世俗（In Mundo）", 4: "场平面（Field Plane）"}


def _pd_js_number(value: Any) -> float:
    """JS `Number(v)`：undefined/非数字串 → NaN，null/''/false → 0，true → 1。"""
    if value is None:  # Python 的 None 兼当 undefined / null：本模块各调用点两者结果相同（都判「无 / 缺省」）
        return math.nan
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = f"{value}".strip()
    if text == "":
        return 0.0
    try:
        return float(text)
    except ValueError:
        return math.nan


def _pd_normalize_type(value: Any) -> int:
    """primaryDirectionSync.js:17 normalizePdType：Number(v) ∈ {0,1,4} 原样，否则缺省 0。"""
    number = _pd_js_number(value)
    return int(number) if number in _PD_SUPPORTED_TYPES else _PD_DEFAULT_TYPE


# 上游 primaryDirectionSync.js:23-42 SUPPORTED_PD_PROJECTIONS（v3.13.0：14 种，+ morinus / horizontal / koch）+ 标签
# （placidus_under_pole 改名「（极下法）」）。与后端 perpredict._PD_PROJECTION_REGISTRY 同表。
_PD_SUPPORTED_PROJECTIONS: tuple[str, ...] = (
    "ptolemy", "placidus", "regiomontanus", "campanus", "topocentric",
    "zodiacal", "ra_direct", "in_zodiaco_lon", "in_zodiaco_abs", "horosa_legacy",
    "placidus_under_pole", "morinus", "horizontal", "koch",
)
_PD_PROJECTION_LABELS = {
    "ptolemy": "Ptolemy（半弧）", "placidus": "Placidus（半弧严密）", "regiomontanus": "Regiomontanus",
    "campanus": "Campanus", "topocentric": "Topocentric", "zodiacal": "纯黄道（斜升差）",
    "ra_direct": "赤经直推", "in_zodiaco_lon": "Along Ecliptic", "in_zodiaco_abs": "Edmund Jones",
    "horosa_legacy": "Horosa原方法",
    "placidus_under_pole": "Placidus under-pole（极下法）",
    "morinus": "Morinus（黄极圈）",
    "horizontal": "Horizontal（地平经圈）",
    "koch": "Koch（出生地）",
}
# 上游 primaryDirectionSync.js:28-31 SUPPORTED_PD_FRAMES（12）+ :289-295 两张标签表。
_PD_SUPPORTED_FRAMES: tuple[str, ...] = (
    "alcabitius", "placidus", "regiomontanus", "campanus", "topocentric",
    "meridian", "porphyry", "equal", "wholesign", "morinus", "koch", "equal_hour_circle",
)
_PD_FRAME_LABELS = {
    "alcabitius": "Alcabitius", "placidus": "Placidus", "regiomontanus": "Regiomontanus", "campanus": "Campanus",
    "topocentric": "Topocentric", "meridian": "Meridian", "porphyry": "Porphyry", "equal": "Equal（等宫）",
    "wholesign": "Whole Sign（整宫）", "morinus": "Morinus", "koch": "Koch", "equal_hour_circle": "Equal（时圈）",
}
_PD_FRAMEWORK_LABELS = {"aspect": "相位主限", "bounds": "界行·分配星", "release": "释放（hyleg）"}
# 上游 primaryDirectionSync.js:379-393 PD_METHOD_TO_PAIR（旧单维 → (投影, 分宫)，与后端 perpredict._PD_METHOD_TO_PAIR
# 逐项同步）。v3.13.0：morinus 有了自己的投影（Morinus 黄极圈），不再借 ptolemy。
_PD_METHOD_TO_PAIR: dict[str, tuple[str, str | None]] = {
    "core_alchabitius": ("ptolemy", "alcabitius"), "placidus": ("placidus", "placidus"),
    "regiomontanus": ("regiomontanus", "regiomontanus"), "campanus": ("campanus", "campanus"),
    "topocentric": ("topocentric", "topocentric"), "meridian": ("ptolemy", "meridian"),
    "porphyry": ("ptolemy", "porphyry"), "equal_ecliptic": ("ptolemy", "equal"),
    "equal_hour_circle": ("ptolemy", "equal_hour_circle"), "morinus": ("morinus", "morinus"),
    "in_zodiaco_lon": ("in_zodiaco_lon", None), "in_zodiaco_abs": ("in_zodiaco_abs", None),
    "horosa_legacy": ("horosa_legacy", None),
}

# 上游 primaryDirectionSync.js:44-65 应星 / 迫星扩展选项 + pdExtensionLabels（AI 自陈行写面板上的名字，未登记值原样）。
_PD_SIGNIFICATOR_OPTIONS: tuple[tuple[str, str], ...] = (
    ("Desc", "下降 DSC"), ("IC", "天底 IC"), ("Syzygy", "产前朔望"), ("Spirit", "精神点"),
    ("Cusps", "中间宫始点"), ("Stars", "恒星（王星+比尼）"), ("Lots", "阿拉伯点（全目录）"),
)
_PD_PROMISSOR_TYPE_OPTIONS: tuple[tuple[str, str], ...] = (("cusps", "宫始点"), ("stars", "恒星"), ("lots", "阿拉伯点"))


def _pd_extension_labels(values: Any, options: tuple[tuple[str, str], ...]) -> list[str]:
    labels = dict(options)
    items = values if isinstance(values, list) else []
    return [labels[v] if isinstance(v, str) and v in labels else _ptext.js_str(v) for v in items]


# 上游 primaryDirectionSync.js:69-95 PD_EXTRA_SETTING_SPECS（主限法设置项登记表：相位侧 / 传统逆向 / 取点四项 /
# 日期两项 / 几何口径）。单一来源：值域闸、schema 描述、[主限法设置] 自陈行都从这张表生成。与后端
# perchart.PD_EXTRA_SETTING_KEYS、Java PdWire.SETTING_KEYS 同名同序。options = (值, 面板标签)。
_PD_EXTRA_SETTING_SPECS: tuple[dict[str, Any], ...] = (
    {"key": "pdGeometry", "type": "select", "default": "improved", "label": "几何口径", "inProjection": True,
     "options": (("improved", "改进"), ("classic", "经典"))},
    {"key": "pdAspectSide", "type": "select", "default": 0, "label": "相位侧",
     "options": ((0, "两侧都出"), (1, "只出右旋"), (2, "只出左旋"))},
    {"key": "pdTradConverse", "type": "switch", "default": 1, "label": "传统逆向"},
    {"key": "pdIgnoreSigLat", "type": "switch", "default": 0, "label": "忽略应星黄纬"},
    {"key": "pdIgnorePromLat", "type": "switch", "default": 0, "label": "忽略迫星黄纬"},
    {"key": "pdLunarParallax", "type": "switch", "default": 0, "label": "月亮视差"},
    {"key": "pdTruePosition", "type": "switch", "default": 0, "label": "真位置"},
    {"key": "pdSolarArcRegressive", "type": "switch", "default": 0, "label": "逆向弧用出生前太阳"},
    {"key": "pdYearDays", "type": "select", "default": 0, "label": "日期年长",
     "options": ((0, "实际天数"), (1, "365 / 366"))},
    {"key": "pdPromAspectLat", "type": "select", "default": 0, "label": "相位点黄纬",
     "options": ((0, "在黄道上"), (1, "合冲带黄纬"), (2, "余弦递减"), (3, "线性递减"), (4, "按宫位"))},
)
_PD_EXTRA_SETTING_KEYS: tuple[str, ...] = tuple(spec["key"] for spec in _PD_EXTRA_SETTING_SPECS)
_PD_EXTRA_SPEC_BY_KEY: dict[str, dict[str, Any]] = {spec["key"]: spec for spec in _PD_EXTRA_SETTING_SPECS}


def _pd_js_strict_equal(left: Any, right: Any) -> bool:
    """JS `===`：数字与数字比值（0 === 0.0），bool 只等 bool，字符串只等字符串。"""
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    return type(left) is type(right) and left == right


def _pd_normalize_extra_value(spec: dict[str, Any], raw: Any) -> Any:
    """primaryDirectionSync.js:98 normalizePdExtraValue：空 → 缺省；开关认 0/1/'0'/'1'/'true'/'false'/bool，其余回缺省；
    下拉按值或其字符串形命中，认不出回缺省。"""
    if raw is None or raw == "":
        return spec["default"]
    if spec["type"] == "switch":
        if raw is False or _pd_js_strict_equal(raw, 0) or raw in ("0", "false"):
            return 0
        return 1 if (raw is True or _pd_js_strict_equal(raw, 1) or raw in ("1", "true")) else spec["default"]
    for value, _label in spec["options"]:
        if _pd_js_strict_equal(value, raw) or _ptext.js_str(value) == _ptext.js_str(raw):
            return value
    return spec["default"]


def _pd_pick_extra_settings(*sources: Any) -> dict[str, Any]:
    """primaryDirectionSync.js:113 pickPdExtraSettings：每键取第一个有值（非 null/undefined）的来源，归一后返回全套。"""
    out: dict[str, Any] = {}
    for spec in _PD_EXTRA_SETTING_SPECS:
        raw = None
        for src in sources:
            if isinstance(src, dict) and src.get(spec["key"]) is not None:
                raw = src[spec["key"]]
                break
        out[spec["key"]] = _pd_normalize_extra_value(spec, raw)
    return out


def _pd_extra_setting_value_label(spec: dict[str, Any], value: Any) -> str:
    """primaryDirectionSync.js:162 pdExtraSettingValueLabel。"""
    if spec["type"] == "switch":
        return "是" if value else "否"
    for option_value, label in spec["options"]:
        if _pd_js_strict_equal(option_value, value):
            return label
    return _ptext.js_str(value)


def _pd_extra_setting_lines(values: Any) -> list[str]:
    """primaryDirectionSync.js:170 pdExtraSettingLines（9 行；几何口径并在「弧算法」行，不另起行）。"""
    picked = _pd_pick_extra_settings(values)
    return [
        f"{spec['label']}：{_pd_extra_setting_value_label(spec, picked[spec['key']])}"
        for spec in _PD_EXTRA_SETTING_SPECS
        if not spec.get("inProjection")
    ]


# 上游 primaryDirectionSync.js:179-191 PD_GEOMETRY_APPLIES：几何口径（改进 / 经典）真有差别的
# [盘类, 弧算法, 盘面宫制或 '*', 是否只在世俗平行开时]（与后端 pd_geometry.APPLIES 同表）。
_PD_GEOMETRY_APPLIES: tuple[tuple[int, str, str, bool], ...] = (
    (0, "placidus", "*", False), (0, "regiomontanus", "*", False), (0, "campanus", "*", False),
    (0, "in_zodiaco_abs", "*", False), (0, "topocentric", "*", False),
    (0, "horizontal", "*", False), (0, "koch", "*", False), (1, "horizontal", "*", False),
    (4, "placidus", "*", False), (4, "regiomontanus", "*", False), (4, "campanus", "*", False),
    (4, "in_zodiaco_abs", "*", False),
    (4, "ptolemy", "*", False), (4, "morinus", "*", False), (4, "zodiacal", "*", False), (4, "ra_direct", "*", False),
    (4, "placidus_under_pole", "*", False), (4, "topocentric", "*", False), (4, "horizontal", "*", False), (4, "koch", "*", False),
    (1, "ptolemy", "alcabitius", False), (1, "ptolemy", "porphyry", False),
    (1, "placidus", "*", False), (1, "regiomontanus", "*", False), (1, "campanus", "*", False),
    (1, "ptolemy", "meridian", True), (1, "ptolemy", "equal", True), (1, "ptolemy", "equal_hour_circle", True),
    (1, "morinus", "*", True),
)


def _pd_geometry_applies(ctx: dict[str, Any]) -> bool:
    """primaryDirectionSync.js:192 pdGeometryApplies({ pdtype, pdProjection, pdFrame, pdParallel })。"""
    pd_type = _pd_normalize_type(ctx.get("pdtype"))
    proj = ctx.get("pdProjection") or "ptolemy"
    frame = ctx.get("pdFrame") or "alcabitius"
    parallel = _pd_js_number(ctx.get("pdParallel"))
    parallel_on = bool(parallel) and not math.isnan(parallel)
    return any(
        at == pd_type and ap == proj and (af == "*" or af == frame) and (not need_par or parallel_on)
        for at, ap, af, need_par in _PD_GEOMETRY_APPLIES
    )


def _pd_projection_label_with_geometry(ctx: dict[str, Any], geometry: Any) -> str:
    """primaryDirectionSync.js:230 pdProjectionLabelWithGeometry：受几何口径影响的组合带「（改进）/（经典）」。"""
    proj = ctx.get("pdProjection")
    label = _PD_PROJECTION_LABELS.get(f"{proj}") or (_ptext.js_str(proj) if proj else "")
    if not label or not _pd_geometry_applies(ctx):
        return label
    geo = _pd_pick_extra_settings({"pdGeometry": geometry})["pdGeometry"]
    geo_label = dict(_PD_EXTRA_SPEC_BY_KEY["pdGeometry"]["options"])[geo]
    return f"{label}（{geo_label}）"


# 上游 primaryDirectionSync.js:403-406 世俗 / Field Plane 下有专属实现的 (投影, 分宫)；:489 pdTypeBaselineNote。
_PD_MUNDO_DEDICATED_PROJECTIONS = ("placidus", "regiomontanus", "campanus", "topocentric", "morinus", "horizontal", "koch")
_PD_MUNDO_DEDICATED_PTOLEMY_FRAMES = ("alcabitius", "meridian", "equal_hour_circle")
_PD_FIELD_PLANE_DEDICATED_PROJECTIONS = (
    "ptolemy", "placidus", "regiomontanus", "campanus", "morinus", "in_zodiaco_abs", "in_zodiaco_lon",
)


def _pd_type_baseline_note(pdtype: Any, projection: Any, frame: Any) -> str:
    """方向类型 × (投影, 分宫) 无专属实现时的注记（诚实回显：几种选择输出逐字节相同时不各写各的名字）。"""
    pd_type = _pd_normalize_type(pdtype)
    proj = projection or "ptolemy"
    fr = frame or "alcabitius"
    if pd_type == 1:
        dedicated = proj in _PD_MUNDO_DEDICATED_PROJECTIONS or (proj == "ptolemy" and fr in _PD_MUNDO_DEDICATED_PTOLEMY_FRAMES)
        return "" if dedicated else "（世界主限下走核内基线）"
    if pd_type == 4:
        return "" if proj in _PD_FIELD_PLANE_DEDICATED_PROJECTIONS else "（Field Plane 下走核内基线）"
    return ""


def _pd_display_method(pd_method: Any, pd_projection: Any) -> str:
    """primaryDirectionSync.js:398 pdDisplayMethod：弧算法选 Horosa原方法 与旧单维 horosa_legacy 同一显示口径
    （列头「赤经」、不按 core 白名单滤行）；其余按 pdMethod，缺省 core_alchabitius。"""
    if f"{pd_projection or ''}" == "horosa_legacy":
        return "horosa_legacy"
    return f"{pd_method}" if pd_method else "core_alchabitius"


# 上游 primaryDirectionSync.js:242-273：恒星作迫星的行编号 FS_<星>_0 合 / FS_<星>_180 冲 / FSD_<星>_θ 右相位 /
# FSS_<星>_θ 左相位；扩展迫星前缀（宫始点 HC / 恒星 FS·FSD·FSS / 阿拉伯点 LT / 平行 PD·PC·MP·RP）。
_PD_STAR_ID_HEADS = {"FS": "N", "FSD": "D", "FSS": "S"}
_PD_EXTENSION_PROMISSOR_HEADS = ("HC", *_PD_STAR_ID_HEADS, "LT", "PD", "PC", "MP", "RP")


def _pd_is_extension_promissor_id(value: Any) -> bool:
    return f"{value or ''}".split("_")[0] in _PD_EXTENSION_PROMISSOR_HEADS


def _pd_parse_star_point_id(value: Any) -> dict[str, Any] | None:
    parts = f"{value or ''}".split("_")
    head = _PD_STAR_ID_HEADS.get(parts[0])
    if not head or len(parts) < 3:
        return None
    deg = _pd_js_number(parts[-1])
    return {"head": head, "name": "_".join(parts[1:-1]), "deg": deg if math.isfinite(deg) else 0.0}


def _pd_star_point_text(value: Any, name_of: Any) -> str | None:
    """primaryDirectionSync.js:260 pdStarPointText（与行星「X的60度右相位处」同一句式）。"""
    point = _pd_parse_star_point_id(value)
    if point is None:
        return None
    name = f"恒星 {(name_of(point['name']) if name_of else '') or point['name']}"
    deg = _ptext.js_str(point["deg"])
    if point["head"] == "D":
        return f"{name}的{deg}度右相位处"
    if point["head"] == "S":
        return f"{name}的{deg}度左相位处"
    return f"{name}的{deg}度相位处" if point["deg"] else name


def _pd_validate_options(payload: dict[str, Any], tool: str) -> None:
    """pd / pdchart 的主限键值域闸（F20 同律：认不出就报错，不让「传了 X 实算另一档」无声发生）。

    词表全取自上面的上游镜像表。为什么每一项都要拦：
    - pdMethod / pdTimeKey：后端白名单外静默回退 core_alchabitius / Ptolemy；
    - pdProjection / pdFrame：后端白名单外静默丢弃、改由 pdMethod 推导，而 [主限法设置] 会照抄传入的名字；
    - pdtype：后端按 `in (0, 1, 4)` 严格比较，2 / 3 是界推运内部值（快照方向类型只认 0 / 1 / 4），字符串 '4' 会落进
      旧 flatlib 分支（2026-10-30 在 vendored 实例实测：标「场平面」实算的是另一张表）——只收整数 0 / 1 / 4；
    - 设置项登记表十键：认不出的值上游 normalizePdExtraValue 回缺省，而后端各有各的宽松解析（pdGeometry 大小写不敏感、
      pdAspectSide 取 int()），两边回落可能不同 → 自陈行与实算分叉。只收上游能命中的值。
    """
    if payload.get("pdMethod") is not None:
        _require_option(payload["pdMethod"], tuple(_PD_METHOD_LABELS), field="pdMethod", tool=tool)
    if payload.get("pdTimeKey") is not None:
        _require_option(payload["pdTimeKey"], _PD_SUPPORTED_TIME_KEYS, field="pdTimeKey", tool=tool)
    if payload.get("pdProjection") is not None:
        _require_option(payload["pdProjection"], _PD_SUPPORTED_PROJECTIONS, field="pdProjection", tool=tool)
    if payload.get("pdFrame") is not None:
        _require_option(payload["pdFrame"], _PD_SUPPORTED_FRAMES, field="pdFrame", tool=tool)
    pdtype = payload.get("pdtype")
    if pdtype is not None and (isinstance(pdtype, bool) or not isinstance(pdtype, int) or pdtype not in _PD_SUPPORTED_TYPES):
        _require_option(pdtype, _PD_SUPPORTED_TYPES, field="pdtype", tool=tool)  # 必然报错：值域闸同一错误信封
    for spec in _PD_EXTRA_SETTING_SPECS:
        raw = payload.get(spec["key"])
        if raw is None:
            continue
        if spec["type"] == "switch":
            recognized = raw in (True, False, "0", "1", "true", "false") or (
                isinstance(raw, (int, float)) and raw in (0, 1)
            )
            allowed: tuple[Any, ...] = (0, 1)
        else:
            allowed = tuple(value for value, _label in spec["options"])
            recognized = any(
                _pd_js_strict_equal(value, raw) or _ptext.js_str(value) == _ptext.js_str(raw) for value in allowed
            )
        if not recognized:
            _require_option(raw, allowed, field=spec["key"], tool=tool)


# 上游 components/direction/AstroDirectMain.js:82-98（主限法表格的核支持体，比主限法盘多一个 Vertex）。
_PD_TABLE_CORE_BASE_IDS = frozenset({*_PD_CORE_SUPPORTED_BASE_IDS, "Vertex"})
_PD_TERMS_VARIANT_LABELS = {1: "托勒密界·校勘本", 2: "托勒密界·经典传本", 3: "迦勒底界", 4: "自定义界表"}


def _pd_msg(value: Any) -> str:
    """AstroDirectMain.js:100-111 msg：AstroTxtMsg[id] → AstroMsg[id]（恒星/宫位等文字条目）→ id。"""
    return _ptext.astro_msg(value)


def _pd_msg_with_house(chart_wrap: dict[str, Any], object_id: Any) -> str:
    """AstroDirectMain.js:113 msgWithHouse = appendPlanetHouseInfoById(msg(id), chartObj, id, {showHouse,showRuler})。"""
    return _normalize_ai_planet_label(_append_planet_house_info(_pd_msg(object_id), chart_wrap, f"{object_id}"))


def _pd_ext_base_text(base: str) -> str | None:
    """AstroDirectMain.js:153 extDirectionBaseText（S/P 扩展本体语义短名）。"""
    matched = re.fullmatch(r"Cusp(\d+)", base or "")
    if matched:
        return f"第{matched.group(1)}宫头"
    return {"Syzygy": "产前朔望", "Spirit": "精神点"}.get(base or "")


def _pd_direction_obj_text(text: Any, chart_wrap: dict[str, Any]) -> str:
    """逐字镜像 AstroDirectMain.js:168-223 directionObjText（迫星/应星 id → 中文）。"""
    if not text:
        return ""
    raw = f"{text}"
    parts = raw.split("_")
    if len(parts) < 2:
        return raw

    def body(base: str) -> str:
        return _pd_ext_base_text(base) or _pd_msg_with_house(chart_wrap, base)

    # v3.13.0（AstroDirectMain.js:191-194）：恒星迫星 FS_/FSD_/FSS_ 先走 pdStarPointText（含右 / 左相位句式），
    # 取代旧的「FS_ → 恒星 X」一支（FSD_/FSS_ 相位行此前原样露出内部 id）。
    star_text = _pd_star_point_text(raw, lambda base: _pd_msg_with_house(chart_wrap, base))
    if star_text:
        return star_text
    head = parts[0]
    third = parts[2] if len(parts) > 2 else ""
    if head == "T":
        return f"{_pd_msg_with_house(chart_wrap, third)}的{_pd_msg_with_house(chart_wrap, parts[1])}界"
    if head == "A":
        return f"{body(parts[1])}的映点"
    if head == "C":
        return f"{body(parts[1])}的反映点"
    if head == "D":
        return f"{body(parts[1])}的{third}度右相位处"
    if head == "S":
        return f"{body(parts[1])}的{third}度左相位处"
    if head == "N":
        if third and third != "0":
            return f"{body(parts[1])}的{third}度相位处"
        return body(parts[1])
    if head == "PD":
        return f"{body(parts[1])}的赤纬平行点"
    if head == "PC":
        return f"{body(parts[1])}的反平行点"
    if head in ("MP", "RP"):
        axis = {"0": "MC", "90": "ASC", "180": "IC", "270": "DSC"}.get(third, third)
        return f"{body(parts[1])}的{'世界平行' if head == 'MP' else '急动平行'}·{axis}"
    if head == "LT":
        return f"{re.sub(r'^Pars ', '', parts[1])}点"
    if head == "HC":
        matched = re.fullmatch(r"Cusp(\d+)", parts[1] or "")
        return f"第{matched.group(1) if matched else parts[1]}宫头"
    return raw


def _pd_split_degree(value: Any) -> tuple[int, int]:
    """上游 AstroHelper.splitDegree 的 [度, 分]（horosa_legacy 赤经列用）。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0, 0
    text = f"{value}".lower()
    neg = number < 0
    deg = abs(number)
    whole = int(abs(int(number)))
    if "e" in text and text.split("e")[1].lstrip("+").lstrip("-").isdigit() and int(text.split("e")[1]) < 0:
        whole, deg = 0, 0.0
    minute_f = (deg - whole) * 60
    minute = math.floor(minute_f)
    sec = _ptext.js_round((minute_f - minute) * 60)
    if sec == 60:
        minute += 1
    if minute == 60:
        whole += 1
        minute = 0
    return (-whole if neg else whole), minute


def _pd_degree_text(value: Any, pd_method: str) -> str:
    """AstroDirectMain.js:122 degreeText：horosa_legacy 走 splitDegree，其余 floor 度/floor 分。"""
    if pd_method == "horosa_legacy":
        deg, minute = _pd_split_degree(value)
        return f"{deg}度{minute}分"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return f"{value or ''}".strip()
    if math.isnan(number):
        return f"{value or ''}".strip()
    neg = "-" if number < 0 else ""
    magnitude = abs(number)
    whole = math.floor(magnitude)
    minute = math.floor((magnitude - whole) * 60)
    if minute >= 60:
        minute = 0
    return f"{neg}{whole}度{minute}分"


def _pd_split_degree_text(value: Any) -> str:
    """AstroPrimaryDirectionChart.js:69 splitDegreeText / aiAnalysisContext pdSplitDegreeText（当前Arc）。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return f"{value or ''}"
    if not math.isfinite(number):
        return f"{value or ''}"
    neg = "-" if number < 0 else ""
    magnitude = abs(number)
    whole = math.floor(magnitude + 1e-12)
    minute = int(_ptext.js_round((magnitude - whole) * 60))
    if minute >= 60:
        return f"{neg}{whole + 1}度0分"
    return f"{neg}{whole}度{minute}分"


def _pd_explicit_params(response: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """本命盘回显 params 打底（后端实算口径：pdDirect/pdConverse 缺省 1、设置项登记表十键的归一值等），调用载荷的
    主限键覆盖——尚未补推导值（判「是否显式给了弧算法」用）。"""
    natal = _natal_chart_wrap(response)
    params = dict(natal.get("params") or {}) if isinstance(natal.get("params"), dict) else {}
    for key, value in payload.items():
        if key.startswith("pd") or key in ("showPdBounds", "termsVariant", "direction"):
            params[key] = value
    return params


def _pd_effective_params(response: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """上游 aiAnalysisContext/regenChart.js:305-345：_pd_explicit_params，再把解耦两维未显式给的按 pdMethod 兼容映射推
    （与后端 perpredict._pdResolveProjectionFrame 同表同序：显式优先、缺者由旧单维推），标签与实算同口径。"""
    params = _pd_explicit_params(response, payload)
    method = f"{params.get('pdMethod') or 'core_alchabitius'}"
    pair = _PD_METHOD_TO_PAIR.get(method, ("ptolemy", "alcabitius"))
    params.setdefault("pdProjection", pair[0])
    if params.get("pdFrame") is None and pair[1] is not None:
        params["pdFrame"] = pair[1]
    return params


def _pd_birth_and_chart_info(chart_wrap: dict[str, Any], params: dict[str, Any]) -> list[tuple[str, str]]:
    """AstroDirectMain.js:258-292 appendBirthAndChartInfo：[出生时间] + [星盘信息]（黄道行取回显原词 Tropical）。"""
    chart = chart_wrap.get("chart") if isinstance(chart_wrap.get("chart"), dict) else {}
    birth_lines = []
    if params.get("birth"):
        dayofweek = chart.get("dayofweek")
        birth_lines.append(f"出生时间：{params['birth']}{f' {dayofweek}' if dayofweek else ''}")
    else:
        birth_lines.append("出生时间：无")
    nongli = chart.get("nongli")
    if isinstance(nongli, dict) and nongli.get("birth"):
        birth_lines.append(f"真太阳时：{nongli['birth']}")
    info = []
    if params.get("lon") or params.get("lat"):
        lon_lat = f"{params.get('lon') or ''} {params.get('lat') or ''}".strip()
        info.append(f"经纬度：{lon_lat}")
    if params.get("zone") is not None:
        info.append(f"时区：{params['zone']}")
    zodiacal_raw = chart.get("zodiacal") or _ptext.ZODIACAL.get(_ptext.js_str(params.get("zodiacal")))
    zodiacal = (_ptext.UPSTREAM_ASTRO_TXT_MSG.get("Sidereal") or zodiacal_raw) if zodiacal_raw == "Sidereal" else zodiacal_raw
    if zodiacal:
        info.append(f"黄道：{zodiacal}")
    hsys = _ptext.HOUSE_SYS_LABELS.get(_ptext.js_str(params.get("hsys"))) or chart.get("hsys")
    if hsys:
        info.append(f"宫制：{hsys}")
    if chart.get("isDiurnal") is not None:
        info.append(f"盘型：{'日生盘' if chart.get('isDiurnal') else '夜生盘'}")
    return [("出生时间", "\n".join(birth_lines)), ("星盘信息", "\n".join(info) or "无")]


def _pd_is_extension_row(row: list[Any], params: dict[str, Any]) -> bool:
    """AstroDirectMain.js:323-341 isExtensionDirectionRow（用户勾选的 S/P 扩展行不被核白名单误滤）。
    v3.13.0：迫星前缀走 isPdExtensionPromissorId（含恒星右 / 左相位 FSD_/FSS_；旧正则只认 FS_，恒星相位行被当 core
    不支持行滤掉）。"""
    prom = f"{row[1] if len(row) > 1 else ''}"
    if _pd_is_extension_promissor_id(prom):
        return True
    sig_keys = params.get("pdSignificators") if isinstance(params.get("pdSignificators"), list) else []
    if not sig_keys:
        return False
    sig_parts = f"{row[2] if len(row) > 2 else ''}".split("_")
    sig_base = sig_parts[1] if len(sig_parts) > 1 else ""
    if "Desc" in sig_keys and sig_base == "Desc":
        return True
    if "IC" in sig_keys and sig_base == "IC":
        return True
    if "Syzygy" in sig_keys and sig_base == "Syzygy":
        return True
    if "Spirit" in sig_keys and sig_base == "Spirit":
        return True
    if "Cusps" in sig_keys and re.fullmatch(r"Cusp\d+", sig_base):
        return True
    if ("Stars" in sig_keys or "Lots" in sig_keys) and sig_base and not re.fullmatch(
        r"Sun|Moon|Mercury|Venus|Mars|Jupiter|Saturn|Uranus|Neptune|Pluto", sig_base
    ):
        return True
    return False


def _pd_table_rows(rows: Any, params: dict[str, Any]) -> list[list[Any]]:
    """AstroDirectMain.js:342-350：core_alchabitius 下滤非核体（扩展行放行）；关界限法时滤界行。
    方法口径 = pdDisplayMethod（v3.13.0：弧算法选 Horosa原方法 与旧单维 horosa_legacy 同口径，不滤行）。"""
    method = _pd_display_method(params.get("pdMethod"), params.get("pdProjection"))
    show_bounds = params.get("showPdBounds") not in (0, False)
    out = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, list) or not row:
            continue
        if method == "core_alchabitius":
            unsupported = _pd_is_bound_row(row) or (
                _pd_base_object_id(row[1] if len(row) > 1 else "") not in _PD_TABLE_CORE_BASE_IDS
                or _pd_base_object_id(row[2] if len(row) > 2 else "") not in _PD_TABLE_CORE_BASE_IDS
            )
            if unsupported and not _pd_is_extension_row(row, params):
                continue
            if not show_bounds and _pd_is_bound_row(row):
                continue
        out.append(row)
    return out


def _pd_source_rows(response: dict[str, Any]) -> Any:
    """主限行来源：/predict/pd 回包顶层 pd；缺则本命盘内嵌 predictives.primaryDirection（上游 chartObj 同源）。"""
    if not isinstance(response, dict):
        return []
    rows = response.get("pd")
    predictives = response.get("predictives")
    if rows is None and isinstance(predictives, dict):
        rows = predictives.get("primaryDirection", [])
    return rows


def _pd_nearest_line(rows: list[list[Any]], params: dict[str, Any], chart_wrap: dict[str, Any], now: datetime | None = None) -> str:
    """AstroDirectMain.js:423-437：表中日期距今最近行（[当前时点] 定位行）。"""
    moment = now or _clock.now()
    now_ms = moment.timestamp() * 1000  # naive = 本机钟面（Date.now()）
    method = _pd_display_method(params.get("pdMethod"), params.get("pdProjection"))
    best = None
    for row in rows:
        # v3.12.0：civilInstantMsOfStr（民用历真实时刻：公元前 / 1582 以前儒略历 / 五位年都认）；认不出即跳过
        when_ms = _civil_instant_ms_of_str(f"{(row[4] if len(row) > 4 else '') or ''}".strip().replace("/", "-"))
        if when_ms is None:
            continue
        distance = abs(when_ms - now_ms)
        if best is None or distance < best[0]:
            best = (distance, row)
    if best is None:
        return ""
    row = best[1]
    return (
        f"表中距今最近行：{_pd_degree_text(row[0], method) or '无'}（{_pd_direction_obj_text(row[1], chart_wrap) or '无'} → "
        f"{_pd_direction_obj_text(row[2], chart_wrap) or '无'}，{row[4] if len(row) > 4 and row[4] else '无'}）"
    )


def _build_primarydirect_snapshot_text(
    payload: dict[str, Any], response: dict[str, Any], *, moment_lines: list[str] | None = None, now: datetime | None = None
) -> str:
    """逐字镜像上游 components/direction/AstroDirectMain.js:308-450 buildPrimaryDirectSnapshotText（v3.13.0）。

    行来自 /predict/pd（= 后端 getPrimaryDirection，与上游 chartObj.predictives.primaryDirection 同源）；[主限法设置]
    按上游口径：「推运方法」只在没有显式弧算法时出（此时旧单维决定弧）；方向类型三值（含 Field Plane）；弧算法行带
    几何口径「（改进）/（经典）」与核内基线注记；框架后接设置项登记表 9 行；应星 / 迫星扩展写面板名。表 4 列
    「日期(UTC)」，方法口径 = pdDisplayMethod。UI-only 段 [主限天球·当前动画所指] headless 不产。skill 自有
    [本命盘星与虚点] 段保留在 [星盘信息] 后。
    """
    explicit_projection = _pd_explicit_params(response, payload).get("pdProjection")
    params = _pd_effective_params(response, payload)
    natal_wrap = _natal_chart_wrap(response) or _top_level_chart_wrap(response)
    method = _pd_display_method(params.get("pdMethod"), params.get("pdProjection"))
    time_key = f"{params.get('pdTimeKey') or 'Ptolemy'}"
    rows = _pd_table_rows(_pd_source_rows(response), params)
    show_bounds = params.get("showPdBounds") not in (0, False)
    want_direct = params.get("pdDirect") not in (0, False, "0")
    want_converse = bool(params.get("pdConverse")) and params.get("pdConverse") not in ("0",)
    if want_direct and want_converse:
        dir_text = "顺向 Direct + 逆向 Converse"
    elif want_converse:
        dir_text = "逆向 Converse"
    else:
        dir_text = "顺向 Direct"
    pdtype_raw = params.get("pdtype")
    projection = params.get("pdProjection")
    frame = params.get("pdFrame")
    framework = params.get("pdFramework")
    # 受几何口径影响的方法带「（改进）/（经典）」（几何口径不另起一行）；世俗 / Field Plane 下无专属实现的组合注明走核内基线。
    proj_label = _pd_projection_label_with_geometry(params, params.get("pdGeometry")) or projection or "Ptolemy（半弧）"
    proj_label += _pd_type_baseline_note(pdtype_raw, projection, frame)
    # 旧单维「推运方法」只在没有显式弧算法时决定弧；有显式两维时由「弧算法 / 盘面宫制」两行表达（上游 :363-367）。
    # skill 的显式 = 调用载荷 / 本命回显里带了 pdProjection（_pd_effective_params 补的推导值不算）。
    setting = [] if explicit_projection else [f"推运方法：{_primary_direction_method_text(method)}"]
    setting += [
        f"度数换算：{_primary_direction_time_key_text(time_key)}",
        f"方向类型：{_PD_TYPE_LABELS[_pd_normalize_type(pdtype_raw)]}",
        f"向运方向：{dir_text}",
        f"映点迫星：{'是' if params.get('pdAntiscia') else '否'}",
        f"界迫星：{'是' if params.get('pdTerms') else '否'}",
        f"弧算法（投影）：{proj_label}",
        f"盘面宫制（分宫）：{_PD_FRAME_LABELS.get(f'{frame}') or frame or 'Alcabitius'}",
        f"框架：{_PD_FRAMEWORK_LABELS.get(f'{framework}') or framework or '相位主限'}",
        *_pd_extra_setting_lines(params),
    ]
    if params.get("pdParallel"):
        setting.append(f"平行迫星：{'世界平行' if pdtype_raw == 1 else '赤纬平行（映点法）'}")
    if params.get("pdRaptParallel"):
        setting.append("急动平行迫星：是")
    terms_variant = _finite_number(params.get("termsVariant"))
    if terms_variant is not None and 1 <= terms_variant <= 4 and int(terms_variant) in _PD_TERMS_VARIANT_LABELS:
        setting.append(f"界系：{_PD_TERMS_VARIANT_LABELS[int(terms_variant)]}")
    if time_key == "User" and params.get("pdTimeKeyCustom"):
        setting.append(f"自定义钥匙率：{_ptext.js_str(params['pdTimeKeyCustom'])}°/年")
    for key, label, options in (
        ("pdSignificators", "应星扩展", _PD_SIGNIFICATOR_OPTIONS),
        ("pdPromissorTypes", "迫星扩展", _PD_PROMISSOR_TYPE_OPTIONS),
    ):
        values = params.get(key)
        if isinstance(values, list) and values:
            setting.append(f"{label}：{'、'.join(_pd_extension_labels(values, options))}")
    setting.append(f"显示界限法：{'是' if show_bounds else '否'}")
    degree_label = "赤经" if method == "horosa_legacy" else "Arc"
    table = [f"| {degree_label} | 迫星 | 应星 | 日期(UTC) |", "| --- | --- | --- | --- |"]
    if not rows:
        table.append("| 无 | 无 | 无 | 无 |")
    for row in rows:
        date = f"{row[4]}" if len(row) > 4 and row[4] else ""
        table.append(
            f"| {_pd_degree_text(row[0], method) or '无'} | {_pd_direction_obj_text(row[1] if len(row) > 1 else None, natal_wrap) or '无'} | "
            f"{_pd_direction_obj_text(row[2] if len(row) > 2 else None, natal_wrap) or '无'} | {date or '无'} |"
        )
    if moment_lines is not None:
        nearest = _pd_nearest_line(rows, params, natal_wrap, now)
        if nearest:
            moment_lines.append(nearest)
    head = _pd_birth_and_chart_info(natal_wrap, params)
    return _render_snapshot_text(
        [
            *head,
            ("本命盘星与虚点", _join_lines(_build_star_and_lot_position_lines(natal_wrap)) or "无"),
            # 上游 v48 段名对齐：主/界限法设置 → 主限法设置（旧名走 map_legacy_section_title）。
            ("主限法设置", _join_lines(setting)),
            ("主限法表格", _join_lines(table)),
        ]
    )


def _pdchart_chart_info_lines(chart_wrap: dict[str, Any], params: dict[str, Any]) -> list[str]:
    """AstroPrimaryDirectionChart.js:335-346 [星盘信息]：经纬度/时区恒出（缺则「无」）+ 黄道（显示文案）+ 宫制。"""
    chart = chart_wrap.get("chart") if isinstance(chart_wrap.get("chart"), dict) else {}
    lon_lat = f"{params.get('lon') or ''} {params.get('lat') or ''}".strip()
    lines = [f"经纬度：{lon_lat or '无'}", f"时区：{params.get('zone') or '无'}"]
    zodiacal_raw = chart.get("zodiacal") or _ptext.ZODIACAL.get(_ptext.js_str(params.get("zodiacal")))
    if zodiacal_raw:
        ayan_key = params.get("siderealAyanamsa") or chart.get("siderealAyanamsa") or ""
        lines.append(f"黄道：{_ptext.zodiacal_display_text(zodiacal_raw, ayan_key)}")
    hsys = _ptext.HOUSE_SYS_LABELS.get(_ptext.js_str(params.get("hsys"))) or chart.get("hsys")
    if hsys:
        lines.append(f"宫制：{hsys}")
    return lines


def _build_pdchart_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    """上游 AstroPrimaryDirectionChart.js:328-373 buildSnapshotText（= aiAnalysisContext 无头 buildPrimaryDirChartSnapshotText）。

    [主限法盘设置] 7 行（v3.13.0 AstroPrimaryDirectionChart.js:361-370 / aiAnalysisContext/primaryDirection.js:172-184）：
    时间选择 / 弧算法（主限法表用，带几何口径）/ 盘面宫制（外圈宫头）/ 度数换算 / 向运方向 / 日期年长 / 当前Arc「X度Y分」
    （Arc 取推导盘回的 arc [Q-171/T-112]）。旧「推运方法」行撤掉：外圈按主限弧在赤经上整体推进，与弧算法无关，宫头只看
    盘面宫制（上游挂载同改用 pdFrame 不用 pdMethod）。skill 自有 [本命盘星与虚点]/[主限法盘星体表格]/[主限法盘相位] 保留（registry 注记）。
    """
    natal_wrap = _natal_chart_wrap(response)
    params = _pd_effective_params(response, payload)
    frame = params.get("pdFrame")
    year_days_spec = _PD_EXTRA_SPEC_BY_KEY["pdYearDays"]
    current_arc = response.get("currentArc") or response.get("arc") or response.get("pdArc")
    pd_wrap = _top_level_chart_wrap(response)
    return _render_snapshot_text(
        [
            ("出生时间", f"出生时间：{params.get('birth') or '无'}"),
            ("星盘信息", _join_lines(_pdchart_chart_info_lines(natal_wrap, params))),
            ("本命盘星与虚点", _join_lines(_build_star_and_lot_position_lines(natal_wrap)) or "无"),
            (
                "主限法盘设置",
                _join_lines(
                    [
                        f"时间选择：{payload.get('datetime') or '无'}",
                        f"弧算法（主限法表用）：{_pd_projection_label_with_geometry(params, params.get('pdGeometry')) or 'Ptolemy（半弧）'}",
                        f"盘面宫制（外圈宫头）：{_PD_FRAME_LABELS.get(f'{frame}') or frame or 'Alcabitius'}",
                        f"度数换算：{_primary_direction_time_key_text(params.get('pdTimeKey'))}",
                        f"向运方向：{'逆向 Converse' if params.get('direction') == 'converse' else '顺向 Direct'}",
                        f"{year_days_spec['label']}：{_pd_extra_setting_value_label(year_days_spec, _pd_pick_extra_settings(params)['pdYearDays'])}",
                        f"当前Arc：{_pd_split_degree_text(current_arc) if current_arc is not None else '无'}",
                    ]
                ),
            ),
            # 上游这两段是「本命盘配置(内圈)」与「主限法盘配置(外圈/时段盘)」，各含 星与虚点 + 宫位宫头
            # 两个子块（AstroPrimaryDirectionChart.js:351-366）。本仓原有的 主限法盘星体表格 / 主限法盘相位
            # 是 skill-extra，保留在后面。
            ("本命盘配置", _join_lines(_natal_config_lines(natal_wrap)) or "无"),
            ("主限法盘配置", _join_lines(_directed_config_lines(pd_wrap)) or "无"),
            ("主限法盘星体表格", _join_lines(_chart_position_table_lines(pd_wrap)) or "无"),
            ("主限法盘相位", _join_lines(_build_aspect_section(pd_wrap)) or "无"),
            (
                "主限法盘说明",
                _join_lines(
                    [
                        "左侧双盘内圈为本命盘，外圈为按当前主限法设置和所选时间推导出的主限法盘位置。",
                        "当前页面会先将所选时间换算为主限年龄弧，再按后台主限法算法推进各星曜与虚点，最后统一投影回黄道后与本命盘套盘显示。",
                    ]
                ),
            ),
        ]
    )


# 上游 components/astro/AstroZR.js:314-322 ZR_BASE_POINTS：福点/六希腊点/四轴 11 项 + 十二星座（[Q-174/T-114]）。
_ZR_BASE_POINTS = (
    "Pars Fortuna", "Pars Spirit", "Pars Mercury", "Pars Venus", "Pars Mars", "Pars Jupiter", "Pars Saturn",
    "Asc", "Desc", "MC", "IC", *_ptext.LIST_SIGNS,
)
# 上游 AstroZR.js:26-46 AI_MODE_ITEMS（输出层级）。
_ZR_AI_MODES = {
    "l1_all": "输出所有L1（星座+时间）",
    "l2_in_l1": "输出某个L1下全部L2",
    "l3_in_l2": "输出某个L2下全部L3",
    "l4_in_l3": "输出某个L3下全部L4",
}


def _zr_sign_name(sign: Any) -> str:
    """AstroZR.js:63 signName：空 → '无'，否则 AstroTxtMsg。"""
    return _ptext.astro_txt(sign) if sign else "无"


def _zr_node_line(item: dict[str, Any] | None) -> str:
    """AstroZR.js:70 nodeLine：座-日期[-LB][-截]（[Q-362/T-343] truncated=末段子期按父期截断）。"""
    if not item:
        return "无"
    base = f"{_zr_sign_name(item.get('sign'))}-{item.get('date') or '无'}"
    if item.get("isLB"):
        base = f"{base}-LB"
    return f"{base}-截" if item.get("truncated") else base


def _zr_mark_special_flags(items: Any, parent_sign_idx: int) -> list[dict[str, Any]]:
    """AstroZR.js:79 markZRSpecialFlags：同父下第二个「与父座对冲」的子期标 LB（跳宫）。"""
    if not isinstance(items, list):
        return []
    opposite = 0
    marked: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        sign = item.get("sign")
        level = _finite_number(item.get("level")) or 0
        sign_idx = _ptext.LIST_SIGNS.index(sign) if sign in _ptext.LIST_SIGNS else -1
        is_lb = False
        if level > 1 and parent_sign_idx >= 0 and sign_idx >= 0 and (sign_idx + 6) % 12 == parent_sign_idx:
            opposite += 1
            if opposite == 2:
                is_lb = True
        marked.append({**item, "isLB": is_lb, "sublevel": _zr_mark_special_flags(item.get("sublevel"), sign_idx)})
    return marked


def _zr_safe_idx(idx: Any, length: int) -> int:
    """AstroZR.js:48 safeIdx。"""
    if not length or length <= 0:
        return 0
    number = _finite_number(idx)
    if number is None or number < 0:
        return 0
    return length - 1 if number >= length else int(number)


def _zr_birth_and_chart_lines(chart_wrap: dict[str, Any], params: dict[str, Any]) -> list[str]:
    """AstroZR.js:137-178 appendBirthAndChart：[起盘信息] + [星盘信息]（黄道行取 AstroTxtMsg，回归盘即写 Tropical）。"""
    chart = chart_wrap.get("chart") if isinstance(chart_wrap.get("chart"), dict) else {}
    lines = ["[起盘信息]"]
    if params.get("birth"):
        dayofweek = chart.get("dayofweek")
        lines.append(f"出生时间：{params['birth']}{f' {dayofweek}' if dayofweek else ''}")
    nongli = chart.get("nongli")
    if isinstance(nongli, dict) and nongli.get("birth"):
        lines.append(f"真太阳时：{nongli['birth']}")
    if params.get("date") or params.get("time"):
        when = f"{params.get('date') or ''} {params.get('time') or ''}".strip()
        lines.append(f"起盘时间：{when}")
    if params.get("lon") or params.get("lat"):
        lon_lat = f"{params.get('lon') or ''} {params.get('lat') or ''}".strip()
        lines.append(f"经纬度：{lon_lat}")
    if params.get("zone") is not None:
        lines.append(f"时区：{params['zone']}")
    if params.get("tradition"):
        lines.append(f"历法：{_ptext.js_str(params['tradition'])}")
    lines.extend(["", "[星盘信息]"])
    zodiacal_raw = chart.get("zodiacal") or _ptext.ZODIACAL.get(_ptext.js_str(params.get("zodiacal")))
    if zodiacal_raw:
        lines.append(f"黄道：{_ptext.UPSTREAM_ASTRO_TXT_MSG.get(zodiacal_raw) or zodiacal_raw}")
    hsys = _ptext.HOUSE_SYS_LABELS.get(_ptext.js_str(params.get("hsys"))) or chart.get("hsys")
    if hsys:
        lines.append(f"宫制：{hsys}")
    if chart.get("isDiurnal") is not None:
        lines.append(f"盘型：{'日生盘' if chart.get('isDiurnal') else '夜生盘'}")
    return lines


def _zr_natal_params(chart_wrap: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """AstroZR.js:329 zrNatalParamsStandalone 的文字源：date/time 取 params.date/time，缺则拆 params.birth。"""
    params = chart_wrap.get("params") if isinstance(chart_wrap.get("params"), dict) else {}
    birth = params.get("birth")
    parts = f"{birth}".split(" ") if birth else []
    return {
        "date": params.get("date") or (parts[0] if parts else None),
        "time": params.get("time") or (parts[1] if len(parts) > 1 else None),
        "zone": params.get("zone"),
        "lon": params.get("lon"),
        "lat": params.get("lat"),
        "hsys": params.get("hsys"),
        "tradition": params.get("tradition"),
        "birth": birth,
        "zodiacal": params.get("zodiacal"),
    }


def _zr_body_lines(base_point: str, items: list[dict[str, Any]], ai_state: dict[str, Any]) -> list[str]:
    """AstroZR.js:238-311 buildZRAISnapshotBody（[基于X推运] 段正文，按输出层级逐层钻取）。"""
    lines = [f"[基于{_ptext.UPSTREAM_ASTRO_TXT_MSG.get(base_point) or base_point}推运]"]
    ai_mode = ai_state.get("aiMode")
    lines.append(f"AI输出模式：{_ZR_AI_MODES.get(ai_mode, _ZR_AI_MODES['l1_all'])}")
    l1_list = _zr_mark_special_flags(items, -1)
    if not l1_list:
        lines.append("无推运数据")
        return lines
    if ai_mode == "l1_all":
        lines.extend(f"L1-{i + 1}：{_zr_node_line(item)}" for i, item in enumerate(l1_list))
        return lines
    l1_idx = _zr_safe_idx(ai_state.get("aiL1Idx"), len(l1_list))
    l1 = l1_list[l1_idx] if l1_list else None
    l2_list = l1.get("sublevel") if l1 and isinstance(l1.get("sublevel"), list) else []
    l2_idx = _zr_safe_idx(ai_state.get("aiL2Idx"), len(l2_list))
    l2 = l2_list[l2_idx] if l2_list else None
    l3_list = l2.get("sublevel") if l2 and isinstance(l2.get("sublevel"), list) else []
    l3_idx = _zr_safe_idx(ai_state.get("aiL3Idx"), len(l3_list))
    l3 = l3_list[l3_idx] if l3_list else None
    if not l1:
        lines.append("未找到L1数据")
        return lines
    lines.append(f"L1-{l1_idx + 1}：{_zr_node_line(l1)}")
    if ai_mode == "l2_in_l1":
        if not l2_list:
            lines.append("无L2数据")
        else:
            lines.extend(f"L2-{i + 1}：{_zr_node_line(item)}" for i, item in enumerate(l2_list))
        return lines
    if not l2:
        lines.append("未找到L2数据")
        return lines
    lines.append(f"L2-{l2_idx + 1}：{_zr_node_line(l2)}")
    if ai_mode == "l3_in_l2":
        if not l3_list:
            lines.append("无L3数据")
        else:
            lines.extend(f"L3-{i + 1}：{_zr_node_line(item)}" for i, item in enumerate(l3_list))
        return lines
    if not l3:
        lines.append("未找到L3数据")
        return lines
    lines.append(f"L3-{l3_idx + 1}：{_zr_node_line(l3)}")
    l4_list = l3.get("sublevel") if isinstance(l3.get("sublevel"), list) else []
    if not l4_list:
        lines.append("无L4数据")
    else:
        lines.extend(f"L4-{i + 1}：{_zr_node_line(item)}" for i, item in enumerate(l4_list))
    return lines


def _zr_period_bounds(items: list[dict[str, Any]], now: datetime | float) -> dict[str, Any] | None:
    """AstroZR.js zrLocateCurrent（v3.12.0）：期起 = civilWallMsOfStr(date)（民用历墙钟轴：公元前历史纪年、1582 以前儒略历；
    严格 ISO 纯日期与旧 Date.parse 的 UTC 零点逐值相同），期讫 = 下一期起 / 末期 date + days 天；与 Date.now() 比。
    `now` 可直接给毫秒（= 上游 nowMs 形参；datetime 只能表示公元 1–9999 年）。"""
    if isinstance(now, datetime):
        now_utc = now.astimezone(timezone.utc) if now.tzinfo else now.replace(tzinfo=timezone.utc)
        now_ms = now_utc.timestamp() * 1000
    else:
        now_ms = float(now)
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        start = _zr_period_start_ms(item)
        if start is None:
            continue
        nxt = items[index + 1] if index + 1 < len(items) and isinstance(items[index + 1], dict) else None
        next_start = _zr_period_start_ms(nxt) if nxt else None
        days = _finite_number(item.get("days"))
        end = next_start if next_start is not None else (start + days * 86400000 if days is not None else None)
        if end is not None and start <= now_ms < end:
            return {
                "item": item,
                "startText": f"{item.get('date')}",
                # zrFmtDayUTC = civilDateStrOfMs（墙钟轴 → 民用历日期标签）
                "endText": f"{nxt.get('date')}" if next_start is not None and nxt else _civil_date_str_of_ms(end),
            }
    return None


def _zr_period_start_ms(item: Any) -> int | None:
    """AstroZR.js zrPeriodStartMs：civilWallMsOfStr(`${item.date}`.trim())；认不出 → None。"""
    return _civil_wall_ms_of_moment(f"{(item.get('date') if isinstance(item, dict) else None) or ''}".strip())


def _zr_current_period_line(items: Any, now: datetime | None = None) -> str:
    """AstroZR.js:221-231 zrCurrentPeriodLine：「当前所处：L1 X期（…至…）/ L2 Y期（…至…）」。"""
    if not isinstance(items, list):
        return ""
    moment = now or _clock.now().astimezone()
    l1 = _zr_period_bounds(items, moment)
    if not l1:
        return ""
    text = f"当前所处：L1 {_zr_sign_name(l1['item'].get('sign'))}期（{l1['startText']} 至 {l1['endText']}）"
    sub = l1["item"].get("sublevel")
    l2 = _zr_period_bounds(sub, moment) if isinstance(sub, list) else None
    if l2:
        text += f" / L2 {_zr_sign_name(l2['item'].get('sign'))}期（{l2['startText']} 至 {l2['endText']}）"
    return text


def _zr_items(response: dict[str, Any]) -> list[dict[str, Any]]:
    predictives = response.get("predictives", {}) if isinstance(response, dict) else {}
    for key in ("zr", "zodialRelease", "zodiacalRelease", "zodialrelease"):
        if isinstance(response.get(key), list):
            return response[key]
        if isinstance(predictives, dict) and isinstance(predictives.get(key), list):
            return predictives[key]
    return []


def _build_zr_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    """逐字镜像上游 components/astro/AstroZR.js:233-311 buildZRAISnapshot(Body)（[当前时点]/[方法说明] 由统一出口追加）。

    F8：基点 basePoint（福点/六希腊点/四轴/十二星座）→ 段头 [基于<名>推运]（此前恒写「基于X点推运」字面占位）；
    输出层级 aiMode（L1 全列 / 某 L1 下全部 L2 / 某 L2 下全部 L3 / 某 L3 下全部 L4）+ aiL1Idx/aiL2Idx/aiL3Idx 钻取。
    旧实现另出 skill 自拟段 [本命盘星与虚点] 与「L1：座；开始：…；时长：…日」行式，均非上游。
    """
    natal_wrap = _natal_chart_wrap(response)
    source = natal_wrap if isinstance(natal_wrap.get("params"), dict) else _ptext.payload_chart_wrap(payload)
    base_point = payload.get("basePoint") or payload.get("startSign") or "Pars Fortuna"
    ai_state = {
        "aiMode": payload.get("aiMode") if payload.get("aiMode") in _ZR_AI_MODES else "l1_all",
        "aiL1Idx": payload.get("aiL1Idx") or 0,
        "aiL2Idx": payload.get("aiL2Idx") or 0,
        "aiL3Idx": payload.get("aiL3Idx") or 0,
    }
    lines = _zr_birth_and_chart_lines(source, _zr_natal_params(source, payload))
    lines.append("")
    lines.extend(_zr_body_lines(base_point, _zr_items(response), ai_state))
    return "\n".join(lines).strip()
