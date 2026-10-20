"""主限法（含主限盘）与黄道释放（ZR）的快照构造。"""
from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from horosa_skill import predictive_text as _ptext
from horosa_skill.service import _clock
from horosa_skill.service._common import (
    _finite_number,
    _join_lines,
    _js_date_parse,
    _msg,
    _render_snapshot_text,
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

# 上游 utils/primaryDirectionSync.js:57-62 SUPPORTED_PD_METHODS（13 法，= 后端 perchart.py:892 白名单）+ :73-87 PD_METHOD_LABELS。
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
# 上游 primaryDirectionSync.js:64-70 SUPPORTED_PD_TIME_KEYS（26 项）+ :88-115 PD_TIME_KEY_LABELS。
_PD_TIME_KEY_LABELS: dict[str, str] = {
    "Ptolemy": "Ptolemy",
    "Naibod": "Naibod",
    "TrueSolarArc": "真太阳弧",
    "SymbolicSolarArc": "太阳弧（黄经）",
    "Kundig": "Kündig",
    "Cardano": "Cardano",
    "Umar": "Umar al-Tabari",
    "Wollner": "Wöllner",
    "Plantiko": "Plantiko",
    "Simmonite": "Simmonite",
    "SynodicYear": "Synodic Year",
    "Kepler": "Kepler",
    "Brahe": "Brahe",
    "SymbolicDegree": "Symbolic Degree",
    "SymbolicYear": "Symbolic Year",
    "SymbolicMoon": "Symbolic Moon",
    "SymbolicMonth": "Symbolic Month",
    "Quarterly": "Quarterly",
    "Quinary": "Quinary",
    "Duodenary": "Duodenary",
    "Novenary": "Novenary",
    "SelfMeasure": "Self-Measure",
    "NaibodRA": "Naibod-in-RA",
    "AscendantArc": "Ascendant-arc（界行）",
    "VanDam": "Van Dam（真弧）",
    "User": "自定义（每年度数）",
}


def _primary_direction_method_text(value: Any) -> str:
    """上游 primaryDirectionSync.js:170 getPdMethodLabel：已知 → 标签；缺省/未知 → 缺省法标签（后端
    perchart.py:892 同样把白名单外一律回退 core_alchabitius，标签与实算一致）。F20：旧实现只认「核5」，
    把 placidus/regiomontanus 等 v3.6 起已真算的方位法写成「未核验，引擎回退 Alcabitius」——对实算结果撒谎。"""
    return _PD_METHOD_LABELS.get(_msg(value)) or _PD_METHOD_LABELS["core_alchabitius"]


def _primary_direction_time_key_text(value: Any) -> str:
    """上游 primaryDirectionSync.js:177 getPdTimeKeyLabel（26 项；缺省/未知 → Ptolemy）。"""
    return _PD_TIME_KEY_LABELS.get(_msg(value)) or _PD_TIME_KEY_LABELS["Ptolemy"]


# 上游 utils/primaryDirectionSync.js:28-56 解耦两维标签 + :120-135 PD_METHOD_TO_PAIR（旧单维 → (投影, 分宫)）。
_PD_PROJECTION_LABELS = {
    "ptolemy": "Ptolemy（半弧）", "placidus": "Placidus（半弧严密）", "regiomontanus": "Regiomontanus",
    "campanus": "Campanus", "topocentric": "Topocentric", "zodiacal": "纯黄道（斜升差）",
    "ra_direct": "赤经直推", "in_zodiaco_lon": "Along Ecliptic", "in_zodiaco_abs": "Edmund Jones",
    "horosa_legacy": "Horosa原方法", "placidus_under_pole": "Placidus under-pole（旧法近似）",
}
_PD_FRAME_LABELS = {
    "alcabitius": "Alcabitius", "placidus": "Placidus", "regiomontanus": "Regiomontanus", "campanus": "Campanus",
    "topocentric": "Topocentric", "meridian": "Meridian", "porphyry": "Porphyry", "equal": "Equal（等宫）",
    "wholesign": "Whole Sign（整宫）", "morinus": "Morinus", "koch": "Koch", "equal_hour_circle": "Equal（时圈）",
}
_PD_FRAMEWORK_LABELS = {"aspect": "相位主限", "bounds": "界行·分配星", "release": "释放（hyleg）"}
_PD_METHOD_TO_PAIR: dict[str, tuple[str, str | None]] = {
    "core_alchabitius": ("ptolemy", "alcabitius"), "placidus": ("placidus", "placidus"),
    "regiomontanus": ("regiomontanus", "regiomontanus"), "campanus": ("campanus", "campanus"),
    "topocentric": ("topocentric", "topocentric"), "meridian": ("ptolemy", "meridian"),
    "porphyry": ("ptolemy", "porphyry"), "equal_ecliptic": ("ptolemy", "equal"),
    "equal_hour_circle": ("ptolemy", "equal_hour_circle"), "morinus": ("ptolemy", "morinus"),
    "in_zodiaco_lon": ("in_zodiaco_lon", None), "in_zodiaco_abs": ("in_zodiaco_abs", None),
    "horosa_legacy": ("horosa_legacy", None),
}
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
    if head == "FS":
        return f"恒星 {_pd_msg_with_house(chart_wrap, parts[1]) or parts[1]}"
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


def _pd_effective_params(response: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """上游 aiAnalysisContext.js:3066-3100：本命盘回显 params 打底（后端实算口径：pdDirect/pdConverse 缺省 1 等），
    记录（=调用载荷）的主限键覆盖；解耦两维未显式给时按 pdMethod 兼容映射推（与后端 perpredict 同表）。"""
    natal = _natal_chart_wrap(response)
    params = dict(natal.get("params") or {}) if isinstance(natal.get("params"), dict) else {}
    for key, value in payload.items():
        if key.startswith("pd") or key in ("showPdBounds", "termsVariant", "direction"):
            params[key] = value
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
    """AstroDirectMain.js:309-324 isExtensionDirectionRow（用户勾选的 S/P 扩展行不被核白名单误滤）。"""
    prom = f"{row[1] if len(row) > 1 else ''}"
    if re.match(r"^(HC|FS|LT|PD|PC|MP|RP)_", prom):
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
    """AstroDirectMain.js:325-333：core_alchabitius 下滤非核体（扩展行放行）；关界限法时滤界行。"""
    method = f"{params.get('pdMethod') or 'core_alchabitius'}"
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
    """AstroDirectMain.js:405-418：表中日期距今最近行（[当前时点] 定位行）。"""
    moment = now or _clock.now()
    method = f"{params.get('pdMethod') or 'core_alchabitius'}"
    best = None
    for row in rows:
        when = _js_date_parse(row[4] if len(row) > 4 else "")
        if when is None:
            continue
        distance = abs((when - moment).total_seconds())
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
    """逐字镜像上游 components/direction/AstroDirectMain.js:294-432 buildPrimaryDirectSnapshotText。

    行来自 /predict/pd（= 后端 getPrimaryDirection，与上游 chartObj.predictives.primaryDirection 同源）；[主限法设置]
    列上游 16 行口径（方向类型/向运方向/映点迫星/界迫星/弧算法/盘面宫制/框架/…）；表 4 列「日期(UTC)」；
    UI-only 段 [主限天球·当前动画所指] headless 不产。skill 自有 [本命盘星与虚点] 段保留在 [星盘信息] 后。
    """
    params = _pd_effective_params(response, payload)
    natal_wrap = _natal_chart_wrap(response) or _top_level_chart_wrap(response)
    method = f"{params.get('pdMethod') or 'core_alchabitius'}"
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
    proj_label = _PD_PROJECTION_LABELS.get(f"{projection}") or projection or "Ptolemy（半弧）"
    if _finite_number(pdtype_raw) == 1 and projection not in ("placidus", "regiomontanus", "campanus", "topocentric"):
        proj_label = f"{proj_label}（世界主限下走核内基线）"
    frame = params.get("pdFrame")
    framework = params.get("pdFramework")
    setting = [
        f"推运方法：{_primary_direction_method_text(method)}",
        f"度数换算：{_primary_direction_time_key_text(time_key)}",
        f"方向类型：{'世俗（In Mundo）' if pdtype_raw == 1 else '黄道（In Zodiaco）'}",
        f"向运方向：{dir_text}",
        f"映点迫星：{'是' if params.get('pdAntiscia') else '否'}",
        f"界迫星：{'是' if params.get('pdTerms') else '否'}",
        f"弧算法（投影）：{proj_label}",
        f"盘面宫制（分宫）：{_PD_FRAME_LABELS.get(f'{frame}') or frame or 'Alcabitius'}",
        f"框架：{_PD_FRAMEWORK_LABELS.get(f'{framework}') or framework or '相位主限'}",
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
    for key, label in (("pdSignificators", "应星扩展"), ("pdPromissorTypes", "迫星扩展")):
        values = params.get(key)
        if isinstance(values, list) and values:
            setting.append(f"{label}：{'、'.join(f'{v}' for v in values)}")
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

    [主限法盘设置] 5 行（时间选择/推运方法/度数换算/向运方向/当前Arc「X度Y分」，Arc 取推导盘回的 arc [Q-171/T-112]）；
    skill 自有 [本命盘星与虚点]/[主限法盘星体表格]/[主限法盘相位] 保留（registry 注记）。
    """
    natal_wrap = _natal_chart_wrap(response)
    params = _pd_effective_params(response, payload)
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
                        f"推运方法：{_primary_direction_method_text(params.get('pdMethod'))}",
                        f"度数换算：{_primary_direction_time_key_text(params.get('pdTimeKey'))}",
                        f"向运方向：{'逆向 Converse' if params.get('direction') == 'converse' else '顺向 Direct'}",
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


def _zr_period_bounds(items: list[dict[str, Any]], now: datetime) -> dict[str, Any] | None:
    """AstroZR.js:198-218 zrLocateCurrent：期起=date（Date.parse 纯日期 = UTC 零点），期讫=下一期起/末期 date+days。"""
    now_utc = now.astimezone(timezone.utc) if now.tzinfo else now.replace(tzinfo=timezone.utc)
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        start = _zr_parse_day_utc(item.get("date"))
        if start is None:
            continue
        nxt = items[index + 1] if index + 1 < len(items) and isinstance(items[index + 1], dict) else None
        next_start = _zr_parse_day_utc(nxt.get("date")) if nxt else None
        days = _finite_number(item.get("days"))
        end = next_start if next_start is not None else (start + timedelta(days=days) if days is not None else None)
        if end is not None and start <= now_utc < end:
            return {
                "item": item,
                "startText": f"{item.get('date')}",
                "endText": f"{nxt.get('date')}" if next_start is not None and nxt else end.strftime("%Y-%m-%d"),
            }
    return None


def _zr_parse_day_utc(text: Any) -> datetime | None:
    raw = f"{text or ''}".strip().replace("/", "-")
    try:
        return datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


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
