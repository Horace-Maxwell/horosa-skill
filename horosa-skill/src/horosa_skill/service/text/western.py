"""西洋衍生技法快照：汉堡 / 天王星盘、骰子（otherbu）、泛音盘、合盘、衍生盘与迁移盘行。"""
from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any

from horosa_skill.astro_rulers import HOUSE_SYSTEM_LABELS
from horosa_skill.astro_rulers import js_template_str as _js_template_str
from horosa_skill.astro_sidereal import zodiacal_display_text
from horosa_skill.civil_calendar import _civil_wall_ms, _civil_wall_ms_of_moment
from horosa_skill.engine import astro_snapshot as _astro_snap
from horosa_skill.engine.astroextra_snapshots import _UNDEFINED, _js_number, ai_msg, fmt_num
from horosa_skill.engine.astroextra_snapshots import _js_str as _ai_js_str
from horosa_skill.service._common import (
    _join_lines,
    _js_round3,
    _msg,
    _render_snapshot_text,
    _split_degree,
)
from horosa_skill.service.text.astro_core import (
    _astro_msg,
    _astro_msg_short,
    _planet_label,
)
from horosa_skill.service.text.chart_family import _headerless_astro_snapshot_text

# ── 汉堡学派 (Uranian) 中点盘核心：星阙 utils/uranianDial.js 的 Python 移植（纯函数）──
# 90° 盘：行星/三王/角点/TNP 折叠到 0–90°；行星图 A+B−C=D；映点 Spiegelpunkt；中点列表。
_DIAL_IDS = (
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
    "Uranus", "Neptune", "Pluto", "North Node", "South Node", "Asc", "MC",
)
_DIAL_PLANETS = ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto")
_DIAL_PERSONAL = {"Sun", "Moon", "Asc", "MC", "North Node", "South Node", "AriesPoint"}
_DIAL_URANIAN = {"Cupido", "Hades", "Zeus", "Kronos", "Apollon", "Admetos", "Vulcanus", "Poseidon"}


def _dial_norm360(x: float) -> float:
    return ((x % 360) + 360) % 360


def _dial_mid(a: float, b: float) -> float:
    m = _dial_norm360((a + b) / 2)
    if abs(m - _dial_norm360(a)) > 90:
        m = _dial_norm360(m + 180)
    return m


def _dial_sep(lon_a: float, lon_b: float, base: float) -> float:
    d = abs(_dial_norm360(lon_a - lon_b) % base)
    return min(d, base - d)


def _dial_antiscion(lon: float) -> float:
    return _dial_norm360(180 - lon)


def _dial_rank(has_personal: bool, has_tnp: bool) -> int:
    return 0 if has_personal else (1 if has_tnp else 2)


def _dial_points(objects: Any, tnp: Any) -> list[dict[str, Any]]:
    pts: list[dict[str, Any]] = []
    for obj in objects or []:
        if isinstance(obj, dict) and obj.get("id") in _DIAL_IDS:
            try:
                pts.append({"id": obj.get("id"), "lon": float(obj.get("lon"))})
            except (TypeError, ValueError):
                continue
    for item in tnp or []:
        if isinstance(item, dict) and item.get("lon") is not None:
            try:
                pts.append({"id": item.get("id"), "lon": float(item.get("lon"))})
            except (TypeError, ValueError):
                continue
    pts.append({"id": "AriesPoint", "lon": 0.0})
    return pts


def _dial_planetary_pictures(points: list[dict[str, Any]], base: float = 90.0, orb: float = 1.0, limit: int = 40) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    n = len(points)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            a, b = points[i], points[j]
            if not (a["id"] in _DIAL_PERSONAL or a["id"] in _DIAL_URANIAN or b["id"] in _DIAL_PERSONAL or b["id"] in _DIAL_URANIAN):
                continue  # 至少一锚点（个人点/TNP）
            for k in range(n):
                if k in (i, j):
                    continue
                c = points[k]
                lon = _dial_norm360(a["lon"] + b["lon"] - c["lon"])
                for m in range(n):
                    if m in (i, j, k):
                        continue
                    d = points[m]
                    sep = _dial_sep(lon, d["lon"], base)
                    if sep > orb:
                        continue
                    key = "|".join(sorted([str(a["id"]), str(b["id"])])) + f"|{c['id']}|{d['id']}"
                    if key in seen:
                        continue
                    seen.add(key)
                    ids = (a["id"], b["id"], c["id"], d["id"])
                    out.append({
                        "a": a["id"], "b": b["id"], "c": c["id"], "d": d["id"], "sep": sep,
                        "hp": any(x in _DIAL_PERSONAL for x in ids), "ht": any(x in _DIAL_URANIAN for x in ids),
                    })
    out.sort(key=lambda p: (_dial_rank(p["hp"], p["ht"]), p["sep"]))
    return out[:limit]


def _dial_midpoint_list(points: list[dict[str, Any]], base: float = 90.0) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    n = len(points)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = points[i], points[j]
            out.append({
                "a": a["id"], "b": b["id"], "lon": _dial_mid(a["lon"], b["lon"]),
                "hp": a["id"] in _DIAL_PERSONAL or b["id"] in _DIAL_PERSONAL,
                "ht": a["id"] in _DIAL_URANIAN or b["id"] in _DIAL_URANIAN,
            })
    out.sort(key=lambda p: (_dial_rank(p["hp"], p["ht"]), p["lon"]))
    return out


def _dial_spiegel(points: list[dict[str, Any]], base: float = 90.0, orb: float = 1.0) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    n = len(points)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = points[i], points[j]
            sep = _dial_sep(_dial_antiscion(a["lon"]), b["lon"], base)
            if sep > orb:
                continue
            out.append({
                "a": a["id"], "b": b["id"], "sep": sep,
                "hp": a["id"] in _DIAL_PERSONAL or b["id"] in _DIAL_PERSONAL,
                "ht": a["id"] in _DIAL_URANIAN or b["id"] in _DIAL_URANIAN,
            })
    out.sort(key=lambda p: (_dial_rank(p["hp"], p["ht"]), p["sep"]))
    return out


# 上游 AstroText.AstroTxtMsg 的 8 颗汉堡虚星 + 白羊点（AstroText.js:458-467）；其余点走 `_astro_msg_short`。
_URANIAN_TXT_MSG: dict[str, str] = {
    "Cupido": "丘比特", "Hades": "哈迪斯", "Zeus": "宙斯", "Kronos": "克洛诺斯",
    "Apollon": "阿波罗", "Admetos": "阿德墨托斯", "Vulcanus": "伏尔甘", "Poseidon": "波塞冬",
    "AriesPoint": "白羊点",
}


def _uranian_msg(point_id: Any) -> str:
    """AstroMidpoint.js msg()：AstroTxtMsg 优先（虚星/白羊点中文名、行星单字、交点/四轴）。"""
    return _URANIAN_TXT_MSG.get(f"{point_id}", "") or _astro_msg_short(point_id)


# AstroMidpoint.js:405-407 六框中性命名（定局法），与 UranianHouseFrames 同表、同序。
_HOUSE_FRAMES = (
    ("meridian", "子午局"), ("ascendant", "上升局"), ("sun", "太阳局"),
    ("moon", "月亮局"), ("node", "交点局"), ("earth", "地球局"),
)


def _dial_planet_house(lon: float, cusps: list[Any]) -> int:
    """uranianDial.js:132 planetHouse：按弧长口径判点落宫（跨 0° 安全，不等距同样适用）。"""
    position = _dial_norm360(lon)
    for index in range(12):
        start, end = float(cusps[index]), float(cusps[(index + 1) % 12])
        if _dial_norm360(position - start) < _dial_norm360(end - start):
            return index + 1
    return 12


def _germany_house_frames_lines(germany_result: Any, dial_points: list[dict[str, Any]]) -> list[str]:
    """[六宫框落宫]（上游 AstroMidpoint.js:408-428 buildHouseFramesSection，[Q-442/T-405]）：六宫框全框 × 全点落宫表。

    页签「六宫框」缺省开（UranianDialStyle showHouseFrames=true，headless 无本机显示仓 = 缺省）→ 后端给了
    houseFrames 即出，不受汉堡门控。落宫取后端 frames[key].placements[id]，缺则按 cusps 定宫，再缺 '—'。
    """
    house_frames = germany_result.get("houseFrames") if isinstance(germany_result, dict) else None
    frames = house_frames.get("frames") if isinstance(house_frames, dict) else None
    if not isinstance(frames, dict):
        return []
    keys = [
        (key, label)
        for key, label in _HOUSE_FRAMES
        if isinstance(frames.get(key), dict) and (frames[key].get("placements") or isinstance(frames[key].get("cusps"), list))
    ]
    if not keys or not dial_points:
        return []

    def house_of(frame: dict[str, Any], point: dict[str, Any]) -> str:
        placements = frame.get("placements")
        if isinstance(placements, dict) and placements.get(point["id"]):
            return _js_template_str(placements[point["id"]])
        cusps = frame.get("cusps")
        if isinstance(cusps, list) and len(cusps) == 12:
            return f"{_dial_planet_house(point['lon'], cusps)}"
        return "—"

    lines = [
        "（子午局=东点 1 宫头·天顶 10 宫头赤道分宫；上升/太阳/月亮/交点/地球局=等宫；太阳局太阳落 4 宫、月亮局太阴落 10 宫、地球局 1 宫头恒 180°）",
        f"| 点 | {' | '.join(label for _, label in keys)} |",
        f"| --- | {' | '.join('---' for _ in keys)} |",
    ]
    for point in dial_points:
        lines.append(f"| {_uranian_msg(point['id'])} | {' | '.join(house_of(frames[key], point) for key, _ in keys)} |")
    return lines


# uranianDial.js:289 太阳弧速率；AstroMidpoint.js:432 校时事件类型中文。
_SOLAR_ARC_RATE = {"naibod": 0.9856473, "oneDeg": 1.0, "cardan": 0.9866667}
# v3.13.0 AstroMidpoint.js buildRectifySection：太阳弧三档改人话（cardan 59′12″ / naibod 均日弧）。
_SOLAR_ARC_LABEL = {"oneDeg": "1°/年", "cardan": "59′12″", "naibod": "均日弧"}
_RECTIFY_TYPE_CN = {"marriage": "婚姻", "children": "生育", "career": "事业", "move": "迁居", "loss": "丧亲", "accident": "意外", "other": "其他"}
_RECTIFY_DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M")


def _parse_local_moment(text: Any) -> datetime | None:
    """moment(<ISO/斜杠日期>) 的本地时刻（naive；上游两端同一浏览器时区，差值与时区无关）。无效 → None。"""
    raw = f"{text or ''}".strip()
    if not raw:
        return None
    raw = raw[:-1] if raw.endswith("Z") else raw
    for fmt in _RECTIFY_DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _germany_rectify_lines(payload: dict[str, Any], rectify_events: Any, dial_points: list[dict[str, Any]]) -> list[str]:
    """[校时预览]（上游 AstroMidpoint.js:433-468 buildRectifySection + uranianDial.js:389 rectificationHits，[Q-442/T-405]）。

    有待校事件（带 date）才产段。盘基/容许度/太阳弧取上游显示仓缺省（90° / 1° / Naibod；headless 无显示仓），
    容许度随请求 `orb`（上游 disp.orb）。Asc 微调滑块是即时预览态，不进快照（命中表按 0 微调）。
    """
    events = [event for event in (rectify_events or []) if isinstance(event, dict) and event.get("date")] if isinstance(rectify_events, list) else []
    if not events:
        return []
    # v3.12.0：出生时刻经民用历单源 momentOfCivilDateTimeStr（公元前 / 1582 以前儒略历 / 公元 1–99 年都对）；
    # 事件日期仍是 moment(ev.date)（引擎解析，现代日期）。两者都落到墙钟毫秒再相减。
    birth = (
        _civil_wall_ms_of_moment(f"{payload.get('date') or ''} {payload.get('time') or '00:00:00'}", strict=False)
        if payload.get("date") else None
    )
    if birth is None:
        return []

    def lon_of(point_id: str) -> float | None:
        for point in dial_points:
            if point.get("id") == point_id:
                return float(point["lon"])
        return None

    axes = [(name, lon) for name, lon in (("MC", lon_of("MC")), ("Asc", lon_of("Asc"))) if lon is not None]
    base = 90.0
    try:
        orb = float(payload.get("orb"))
    except (TypeError, ValueError):
        orb = 1.0
    if not (math.isfinite(orb) and orb > 0):
        orb = 1.0
    sa_key = "naibod"
    rate = _SOLAR_ARC_RATE[sa_key]
    rows: list[str] = []
    total = 0
    for index, event in enumerate(events):
        label = f"{event['label']}" if event.get("label") and f"{event['label']}".strip() else f"事件{index + 1}"
        when = _parse_local_moment(event.get("date"))
        when_ms = (
            _civil_wall_ms(when.year, when.month, when.day, when.hour, when.minute, when.second) + when.microsecond // 1000
            if when is not None else None
        )
        years = (when_ms - birth) / (86400000 * 365.2422) if when_ms is not None else None
        hits: list[tuple[str, str, float]] = []
        arc: float | None = None
        if years is not None:
            arc = years * rate
            for angle_name, angle_lon in axes:
                directed = _dial_norm360(angle_lon + arc)
                for point in dial_points:
                    separation = _dial_sep(directed, point["lon"], base)
                    if separation <= orb:
                        hits.append((point["id"], angle_name, separation))
            hits.sort(key=lambda hit: hit[2])
        total += len(hits)
        hit_text = "，".join(f"{angle}→{_uranian_msg(factor)}·{separation:.2f}°" for factor, angle, separation in hits[:8]) or "无命中"
        date_text = when.strftime("%Y-%m-%d") if when is not None else ""
        arc_text = f"{arc:.2f}" if arc is not None and math.isfinite(arc) else "—"
        type_text = _RECTIFY_TYPE_CN.get(str(event.get("type")), "其他")
        rows.append(f"| {label} | {type_text} | {date_text or '—'} | {arc_text} | {hit_text} |")
    return [
        f"（已录事件推进 MC/Asc 看是否触动本命因子，只预览不改盘；盘基 {_dial_base_deg_text(base)}·容许 {_js_template_str(orb)}°·太阳弧 {_SOLAR_ARC_LABEL.get(sa_key) or '均日弧'}；1°MC≈4 分钟出生时间）",
        "| 事件 | 类型 | 日期 | 弧° | 命中(轴→本命因子·角距) |",
        "| --- | --- | --- | --- | --- |",
        *rows,
        f"命中合计：{total}",
    ]


def _dial_base_deg_text(base: float) -> str:
    """v3.13.0 UranianDialStyle.js dialBaseDegText：有限小数照原样 `${b}°`；`${b}` 超 9 字符（H7 这类无限小数）才改度分秒。
    本仓盘基恒为缺省 90（headless 无显示仓），故只实现前一支；长串小数分支不可达，遇到即原样输出以免静默错字。"""
    text = _js_template_str(base)
    return f"{text}°"


def _js_fixed2(value: Any) -> str:
    """`Number(v).toFixed(2)`：非有限 → JS 的 'NaN' / 'Infinity'。"""
    num = _js_number(value)
    if not math.isfinite(num):
        return _ai_js_str(num)
    return fmt_num(num, 2)


def _germany_declination_lines(payload: dict[str, Any], germany_result: Any) -> list[str]:
    """[赤纬接触]（v3.13.0 上游 AstroMidpoint.js buildDeclinationSection；aiExport v59 自 [汉堡学派要素] 拆出、缺省开）。

    门控 = 左栏「赤纬接触」开着（disp.showDeclination≠false；本仓 = 请求 `declination` 不是 false，缺省开），且后端给了
    `declination` 字段（关了赤纬 / 旧后端 = 不产段）。不受汉堡门控；平行 / 反平行全表（不截前 6 对）。
    """
    if payload.get("declination") is False:
        return []
    decl = germany_result.get("declination") if isinstance(germany_result, dict) else None
    if not isinstance(decl, dict):  # JS：`{}` 也是真值 → 照样成段（「暂无」行）
        return []
    par = decl.get("parallel") if isinstance(decl.get("parallel"), list) else []
    cp = decl.get("contraParallel") if isinstance(decl.get("contraParallel"), list) else []

    def get(item: Any, key: str) -> Any:
        return item.get(key, _UNDEFINED) if isinstance(item, dict) else _UNDEFINED

    def deg(value: Any) -> str:
        num = _js_number(value)
        if not math.isfinite(num):
            return "—"
        return f"{'+' if num >= 0 else ''}{fmt_num(num, 2)}°"

    def delta(value: Any) -> str:
        num = _js_number(value)
        return fmt_num(num, 2) if math.isfinite(num) else "—"

    out = [
        "（平行≈合：两点赤纬同号、相差在容许度内；反平行≈冲：异号、绝对值相差在容许度内；行星与虚星入算，四轴不入算）",
    ]
    if not par and not cp:
        out.append("容许度内暂无平行 / 反平行")
        return out
    out.append("| 接触 | 点对 | 赤纬 | 差 |")
    out.append("| --- | --- | --- | --- |")
    for p in par:
        out.append(f"| 平行 | {ai_msg(get(p, 'a'))} ∥ {ai_msg(get(p, 'b'))} | {deg(get(p, 'decA'))} / {deg(get(p, 'decB'))} | {delta(get(p, 'delta'))}° |")
    for p in cp:
        out.append(f"| 反平行 | {ai_msg(get(p, 'a'))} ⥮ {ai_msg(get(p, 'b'))} | {deg(get(p, 'decA'))} / {deg(get(p, 'decB'))} | {delta(get(p, 'delta'))}° |")
    return out


def _germany_coord_midpoint_lines(payload: dict[str, Any], germany_result: Any) -> list[str]:
    """[中点坐标]（v3.13.0 上游 AstroMidpoint.js buildCoordMidpointSection，aiExport v60）。

    门控 = 挂载/页面「中点坐标」选了 ra 赤经 / decl 赤纬（本仓 = 请求 `mpCoord`，原样透传给 /germany/midpoint），且后端
    `coordMidpoints.coord` 与之相同；黄经（缺省）不成段。接触表前 80 行。
    """
    coord = payload.get("mpCoord") if payload.get("mpCoord") in ("ra", "decl") else None
    cm = germany_result.get("coordMidpoints") if isinstance(germany_result, dict) else None
    if not coord or not isinstance(cm, dict) or cm.get("coord") != coord:
        return []
    unit = "赤经" if coord == "ra" else "赤纬"
    out = [f"坐标：{unit}({'赤经近轴中点,合 / 刑 / 冲' if coord == 'ra' else '两点赤纬平均,平行 / 反平行'})"]

    def asp(value: Any) -> str:
        if value == "parallel":
            return "平行"
        if value == "contraParallel":
            return "反平行"
        return f"{_ai_js_str(value)}°"

    rows = cm.get("contacts") if isinstance(cm.get("contacts"), list) else []
    if not rows:
        out.append(f"容许度内没有星体落在{unit}中点上")
        return out
    for c in rows[:80]:
        item = c if isinstance(c, dict) else {}
        out.append(
            f"{ai_msg(item.get('id', _UNDEFINED))} {asp(item.get('aspect', _UNDEFINED))} "
            f"{ai_msg(item.get('idA', _UNDEFINED))}/{ai_msg(item.get('idB', _UNDEFINED))} · 差 {_js_fixed2(item.get('delta', _UNDEFINED))}°"
        )
    return out


def _build_germany_snapshot_text(
    payload: dict[str, Any],
    chart_response: dict[str, Any],
    germany_result: dict[str, Any],
    *,
    rectify_events: Any = None,
) -> str:
    chart = chart_response.get("chart", {}) if isinstance(chart_response, dict) else {}
    houses = chart.get("houses") if isinstance(chart, dict) else []
    objects = chart.get("objects") if isinstance(chart, dict) else []
    midpoints = germany_result.get("midpoints", []) if isinstance(germany_result, dict) else []
    aspects = germany_result.get("aspects", {}) if isinstance(germany_result, dict) else {}
    house_lines: list[str] = []
    for house in houses or []:
        if not isinstance(house, dict):
            continue
        house_lines.append(f"{house.get('id', 'House')}")
        in_house = [obj for obj in objects or [] if isinstance(obj, dict) and obj.get("house") == house.get("id")]
        if not in_house:
            house_lines.append("星体：无")
            continue
        for obj in in_house:
            deg, minute = _split_degree(obj.get("signlon", obj.get("lon")))
            sign = _msg(obj.get("sign"))
            house_lines.append(f"星体：{_planet_label(obj.get('id'))} {deg}˚{sign}{minute}分")
    midpoint_lines = []
    for item in midpoints or []:
        if not isinstance(item, dict):
            continue
        deg, minute = _split_degree(item.get("signlon"))
        midpoint_lines.append(f"{_planet_label(item.get('idA'))} | {_planet_label(item.get('idB'))} = {deg}˚{_msg(item.get('sign'))}{minute}分")
    aspect_lines = []
    if isinstance(aspects, dict):
        for key, arr in aspects.items():
            aspect_lines.append(f"主体：{_planet_label(key)}")
            if not arr:
                aspect_lines.append("无")
                continue
            for asp in arr:
                if not isinstance(asp, dict):
                    continue
                mid = asp.get("midpoint", {}) if isinstance(asp.get("midpoint"), dict) else {}
                id_a = mid.get("idA", asp.get("idA"))
                id_b = mid.get("idB", asp.get("idB"))
                aspect_lines.append(
                    f"与中点({_planet_label(id_a)} | {_planet_label(id_b)}) 成 {asp.get('aspect', '—')} 相位，误差{asp.get('delta', '—')}"
                )
            aspect_lines.append("")
    tnp = germany_result.get("tnp", []) if isinstance(germany_result, dict) else []
    tnp_error = germany_result.get("tnpError") if isinstance(germany_result, dict) else None
    # 行星：十曜扁平位置。
    obj_by_id = {obj.get("id"): obj for obj in objects or [] if isinstance(obj, dict)}
    planet_lines: list[str] = []
    for pid in _DIAL_PLANETS:
        obj = obj_by_id.get(pid)
        if not isinstance(obj, dict):
            continue
        deg, minute = _split_degree(obj.get("signlon", obj.get("lon")))
        planet_lines.append(f"{_planet_label(pid)} {deg}˚{_msg(obj.get('sign'))}{minute}分")
    # TNP星体：8 颗汉堡虚星。
    tnp_lines: list[str] = []
    for item in tnp or []:
        if not isinstance(item, dict):
            continue
        deg, minute = _split_degree(item.get("signlon", item.get("lon")))
        tnp_lines.append(f"{_planet_label(item.get('id'))} {deg}˚{_msg(item.get('sign'))}{minute}分")
    if tnp_error:
        tnp_lines.append("（部分 TNP 历表不可用）")
    # 90°中点盘 / 行星图 / 映点 / 中点列表（base=90、orb=1 Witte 标准）。
    dial_points = _dial_points(objects, tnp)
    dial_factor_lines = [
        f"{_planet_label(p['id'])} = {(_dial_norm360(p['lon']) % 90):.2f}°"
        for p in sorted(dial_points, key=lambda q: _dial_norm360(q["lon"]) % 90)
        if p["id"] != "AriesPoint"
    ]
    picture_lines = [
        f"{_planet_label(p['a'])} + {_planet_label(p['b'])} − {_planet_label(p['c'])} = {_planet_label(p['d'])}（误差{p['sep']:.2f}°）"
        for p in _dial_planetary_pictures(dial_points)
    ]
    spiegel_lines = [f"{_planet_label(p['a'])} ⟷ {_planet_label(p['b'])}（误差{p['sep']:.2f}°）" for p in _dial_spiegel(dial_points)]
    mplist_lines = [f"{_planet_label(p['a'])} / {_planet_label(p['b'])} = {p['lon']:.2f}°" for p in _dial_midpoint_list(dial_points)[:120]]
    # [Q-442/T-405]（上游 AstroMidpoint.js:561-570）：六宫框全表（页签开着即进，不受汉堡门控）与校时预览（有待校事件才进）；
    # 段序紧随 [中点列表]、在 [汉堡学派要素]/[戴维森盘]/[虚星参考] 之前（同 aiExport.js:857 preset）。
    tail_sections: list[tuple[str, str]] = []
    frames_lines = _germany_house_frames_lines(germany_result, dial_points)
    if frames_lines:
        tail_sections.append(("六宫框落宫", "\n".join(frames_lines)))
    # v3.13.0 段序（buildGermanySnapshotText）：六宫框落宫 → 赤纬接触 → 校时预览 → 中点坐标 → 公式求解 → 汉堡学派要素。
    # [公式求解] 只认显示仓 disp.formula（90°中点盘右栏手输），挂载齿轮无此项、headless 显示仓缺省空串 → 不产段，本仓不移植。
    declination_lines = _germany_declination_lines(payload, germany_result)
    if declination_lines:
        tail_sections.append(("赤纬接触", "\n".join(declination_lines)))
    rectify_lines = _germany_rectify_lines(payload, rectify_events, dial_points)
    if rectify_lines:
        tail_sections.append(("校时预览", "\n".join(rectify_lines)))
    coord_lines = _germany_coord_midpoint_lines(payload, germany_result)
    if coord_lines:
        tail_sections.append(("中点坐标", "\n".join(coord_lines)))
    return _render_snapshot_text(
        [
            (
                "起盘信息",
                "\n".join(
                    [
                        f"日期：{payload.get('date', '—')} {payload.get('time', '—')}",
                        f"时区：{payload.get('zone', '—')}",
                        f"经纬度：{payload.get('lon', '—')} {payload.get('lat', '—')}",
                    ]
                ),
            ),
            ("宫位宫头", "\n".join(house_lines).strip() or "无"),
            ("行星", "\n".join(planet_lines).strip() or "无"),
            ("中点", "\n".join(midpoint_lines).strip() or "暂无中点数据"),
            ("TNP星体", "\n".join(tnp_lines).strip() or "暂无 TNP 数据"),
            ("中点相位", "\n".join(aspect_lines).strip() or "暂无中点相位数据"),
            ("90°中点盘", "\n".join(dial_factor_lines).strip() or "暂无可折叠因子"),
            ("行星图", "\n".join(picture_lines).strip() or "暂无行星图"),
            ("映点", "\n".join(spiegel_lines).strip() or "暂无映点接触"),
            ("中点列表", "\n".join(mplist_lines).strip() or "暂无中点"),
            *tail_sections,
        ]
    )


def _dice_split_degree(degree: Any) -> tuple[int, int]:
    """DiceMain.js:57 splitDegree：Number(degree) 非数 → [0,0]；负数先 +360；座内度/分向下取整。"""
    try:
        number = float(degree)
    except (TypeError, ValueError):
        return 0, 0
    if number != number:
        return 0, 0
    if number < 0:
        number += 360
    deg = math.floor(number % 30)
    return deg, math.floor(((number % 30) - deg) * 60)


def _dice_chart_object_lines(chart_obj: Any) -> list[str]:
    """DiceMain.js:72 buildChartObjectLines：逐宫星体 GFM 表（[Q-455/T-418] 逆行列：lonspeed<0 标「逆」，无速度字段为 —）。"""
    chart = chart_obj.get("chart") if isinstance(chart_obj, dict) else None
    if not isinstance(chart, dict):
        return []
    houses = chart.get("houses") if isinstance(chart.get("houses"), list) else []
    objects = chart.get("objects") if isinstance(chart.get("objects"), list) else []
    if not houses:
        return []
    lines = ["| 宫位 | 星体 | 度 | 座 | 分 | 逆行 |", "| --- | --- | --- | --- | --- | --- |"]
    for house in houses:
        house_id = house.get("id") if isinstance(house, dict) else None
        in_house = [obj for obj in objects if isinstance(obj, dict) and obj.get("house") == house_id]
        if not in_house:
            lines.append(f"| {_astro_msg_short(house_id)} | 无 | — | — | — | — |")
            continue
        for index, obj in enumerate(in_house):
            deg, minute = _dice_split_degree(obj.get("signlon"))
            speed = obj.get("lonspeed")
            retro = "逆" if isinstance(speed, (int, float)) and not isinstance(speed, bool) and math.isfinite(speed) and speed < 0 else "—"
            lines.append(
                f"| {_astro_msg_short(house_id) if index == 0 else '—'} | {_astro_msg_short(obj.get('id'))} | {deg} | "
                f"{_astro_msg_short(obj.get('sign'))} | {minute} | {retro} |"
            )
    return lines


def _dice_chart_aspect_lines(chart_obj: Any) -> list[str]:
    """DiceMain.js:102 buildChartAspectLines（[Q-455/T-418]）：两盘 normalAsp 四态各成行，无数据 → []（不产段）。

    ⚠ 声明式 deviation（v0.40.0，用户拍板）：上游只读 `chartObj.chart.aspects.normalAsp`（DiceMain.js:102），而后端
    /predict/dice 的 diceChart/chart 是 getChartObj 形——aspects 在 chartObj **顶层**（AstroChartCircle 画相位线读的也是顶层），
    上游 jest 夹具把 aspects 嵌错了层所以照样绿，真实响应下这两段恒不产出。本仓先读顶层（真实形状），再退回上游路径
    （夹具形状），两段因此在真数据下可达；详见 tests/test_sync311_chartfamily.py。
    """
    chart = chart_obj.get("chart") if isinstance(chart_obj, dict) else None
    top_aspects = chart_obj.get("aspects") if isinstance(chart_obj, dict) else None
    aspects = top_aspects if isinstance(top_aspects, dict) else (chart.get("aspects") if isinstance(chart, dict) else None)
    normal = aspects.get("normalAsp") if isinstance(aspects, dict) else None
    if not isinstance(normal, dict) or not normal:
        return []
    ids = [obj.get("id") for obj in (chart.get("objects") or []) if isinstance(obj, dict) and normal.get(obj.get("id"))]
    ids.extend(key for key in normal if key not in ids)
    rows: list[str] = []
    for object_id in ids:
        one = normal.get(object_id)
        if not isinstance(one, dict) or not one:
            continue
        subject = _astro_msg_short(object_id)
        # 上游 Exact 与 Separative 同折「离相」（DiceMain.js:113-118；与星盘 [相位] 段的「正合」不同，照抄不统一）。
        for key, state in (("Applicative", "入相"), ("Exact", "离相"), ("Separative", "离相"), ("None", "—")):
            for asp in one.get(key) or []:
                if isinstance(asp, dict):
                    rows.append(
                        f"| {subject} | {_js_template_str(asp.get('asp'))}˚ | {_astro_msg_short(asp.get('id'))} | {state} | {_js_round3(asp.get('orb'))} |"
                    )
    if not rows:
        return []
    return ["| 主体 | 相位 | 对象 | 相态 | 误差 |", "| --- | --- | --- | --- | --- |", *rows]


def _build_otherbu_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    """上游 DiceMain.js:127-170 buildDiceSnapshotText（v3.11：逆行列 / 掷星星池 / 两盘相位段）。"""
    house = response.get("house")
    # [Q-145/T-52] 说清作用域：tradition 只决定**掷出的那颗星**从哪个池里抽；背景盘面恒按完整星集绘制。
    pool = "传统七政 + 交点 / 虚点(不含三王星)" if payload.get("tradition") else "含三王星的完整星集"
    sections: list[tuple[str, str]] = [
        (
            "起盘信息",
            "\n".join(
                [
                    f"日期：{payload.get('date', '—')} {payload.get('time', '—')}",
                    f"时区：{payload.get('zone', '—')}",
                    f"经纬度：{payload.get('lon', '—')} {payload.get('lat', '—')}",
                    f"掷星星池：{pool}(背景盘面仍按完整星集绘制)",
                    f"问题：{payload.get('question') or '未填写'}",
                ]
            ),
        ),
        (
            "骰子结果",
            "\n".join(
                [
                    f"行星：{_astro_msg_short(response.get('planet'))}",
                    f"星座：{_astro_msg_short(response.get('sign'))}",
                    f"宫位：{_astro_msg_short('House' + (_js_template_str(int(house) + 1) if isinstance(house, (int, float)) and not isinstance(house, bool) else ''))}",
                ]
            ),
        ),
        ("骰子盘宫位与星体", "\n".join(_dice_chart_object_lines(response.get("diceChart")))),
        ("天象盘宫位与星体", "\n".join(_dice_chart_object_lines(response.get("chart")))),
    ]
    # 两盘相位段：有相位数据才产段（缺数据时既有输出逐字不变，上游同）。
    dice_aspects = _dice_chart_aspect_lines(response.get("diceChart"))
    if dice_aspects:
        sections.append(("骰子盘相位", "\n".join(dice_aspects)))
    sky_aspects = _dice_chart_aspect_lines(response.get("chart"))
    if sky_aspects:
        sections.append(("天象盘相位", "\n".join(sky_aspects)))
    return _render_snapshot_text(sections)


def _build_harmonic_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    harmonic = response.get("harmonic", payload.get("harmonic", 9))
    positions = response.get("positions") or []
    conjunctions = response.get("conjunctions") or []
    pos_lines: list[str] = []
    for p in positions:
        if not isinstance(p, dict):
            continue
        deg, minute = _split_degree(p.get("signlon", p.get("lon")))
        natal_deg, natal_min = _split_degree(p.get("natalLon"))
        pos_lines.append(
            f"{_planet_label(p.get('id'))}：本命 {natal_deg}˚{natal_min}分 → 调波 {_astro_msg(p.get('sign'))} {deg}˚{minute}分"
        )
    conj_lines: list[str] = []
    for c in conjunctions:
        if not isinstance(c, dict):
            continue
        try:
            orb_text = f"{float(c.get('orb')):.2f}°"
        except (TypeError, ValueError):
            orb_text = f"{c.get('orb')}"
        conj_lines.append(f"{_planet_label(c.get('a'))} ☌ {_planet_label(c.get('b'))}（误差 {orb_text}）")
    return _render_snapshot_text(
        [
            (
                "起盘信息",
                "\n".join(
                    [
                        f"日期：{payload.get('date', '—')} {payload.get('time', '—')}",
                        f"时区：{payload.get('zone', '—')}",
                        f"经纬度：{payload.get('lon', '—')} {payload.get('lat', '—')}",
                        f"调波数：H{harmonic}",
                        f"容许度(orb)：{payload.get('orb', 2)}°",
                    ]
                ),
            ),
            ("调波位置", "\n".join(pos_lines).strip() or "无"),
            ("同频合相", "\n".join(conj_lines).strip() or "无"),
        ]
    )


def _relation_name(value: Any) -> str:
    mapping = {
        0: "比较盘",
        1: "组合盘",
        2: "影响盘",
        3: "时空中点盘",
        4: "马克斯盘",
        "0": "比较盘",
        "1": "组合盘",
        "2": "影响盘",
        "3": "时空中点盘",
        "4": "马克斯盘",
        "Comp": "比较盘",
        "Composite": "组合盘",
        "Synastry": "影响盘",
        "TimeSpace": "时空中点盘",
        "Marks": "马克斯盘",
    }
    return mapping.get(value, _msg(value) or "关系盘")


# ── 合盘快照 helpers：逐字镜像上游 components/astro/AstroRelative.js:28-133（本文件的 msg/round3/aspectText 与
# astroAiSnapshot 同名函数略有不同：aspectText 对 null 回 '0˚'、对非数回 `${asp || ''}`）。表格一律 GFM，空列表不产段。
def _rel_aspect_text(asp: Any) -> str:
    """AstroRelative.js:48-54 aspectText。"""
    num = _js_number_undef(asp)
    if math.isnan(num):
        return _js_template_str(asp) if asp not in (None, "", 0, False) and asp is not _REL_UNDEF else ""
    return f"{_js_template_str(num)}˚"


_REL_UNDEF = object()


def _js_number_undef(value: Any) -> float:
    # JS Number(v)：缺键（undefined）→ NaN、null → 0（与 astroextra_snapshots._js_number 同，但本处以 _REL_UNDEF 表缺键）。
    if value is _REL_UNDEF:
        return math.nan
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return 0.0
        try:
            return float(text)
        except ValueError:
            return math.nan
    return math.nan


def _rel_get(obj: Any, key: str) -> Any:
    return obj[key] if isinstance(obj, dict) and key in obj else _REL_UNDEF


def _rel_id(obj: Any, key: str, alt: str) -> Any:
    """`obj.key !== undefined ? obj.key : obj.alt`。"""
    value = _rel_get(obj, key)
    return value if value is not _REL_UNDEF else _rel_get(obj, alt)


def _rel_msg(value: Any) -> str:
    return "" if value is _REL_UNDEF else _astro_snap.msg(value)


def _rel_round3(value: Any) -> str:
    return "" if value is _REL_UNDEF else _astro_snap.round3(value)


_REL_ASPECT_HEAD = ["| 星A | 星B | 相位 | 误差 |", "| --- | --- | --- | --- |"]


def _relative_aspect_lines(items: Any) -> list[str]:
    """AstroRelative.js:74-94 pushAspectArray（A对B相位 / B对A相位）：空列表 → []（不产段）。"""
    if not isinstance(items, list) or not items:
        return []
    lines = list(_REL_ASPECT_HEAD)
    for obj in items:
        obj_id = _rel_id(obj, "id", "directId")
        objs = _rel_get(obj, "objects")
        objs = objs if isinstance(objs, list) else []
        if not objs:
            lines.append(f"| {_rel_msg(obj_id)} | 无 | — | — |")
            continue
        for k, natal in enumerate(objs):
            natal_id = _rel_id(natal, "id", "natalId")
            lines.append(
                f"| {_rel_msg(obj_id) if k == 0 else '—'} | {_rel_msg(natal_id)} | "
                f"{_rel_aspect_text(_rel_get(natal, 'aspect'))} | {_rel_round3(_rel_get(natal, 'delta'))} |"
            )
    return lines


def _relative_midpoint_lines(mapping: Any) -> list[str]:
    """AstroRelative.js:96-118 pushMidpointMap（A对B中点相位 / B对A中点相位）：无键 → []。"""
    if not isinstance(mapping, dict) or not mapping:
        return []
    lines = ["| 星A | 中点 | 相位 | 误差 |", "| --- | --- | --- | --- |"]
    for key, arr in mapping.items():
        arr = arr if isinstance(arr, list) else []
        if not arr:
            lines.append(f"| {_rel_msg(key)} | 无 | — | — |")
            continue
        for k, asp in enumerate(arr):
            midpoint = _rel_get(asp, "midpoint")
            midpoint = midpoint if isinstance(midpoint, dict) else {}
            lines.append(
                f"| {_rel_msg(key) if k == 0 else '—'} | {_rel_msg(_rel_get(midpoint, 'idA'))}·{_rel_msg(_rel_get(midpoint, 'idB'))} | "
                f"{_rel_aspect_text(_rel_get(asp, 'aspect'))} | {_rel_round3(_rel_get(asp, 'delta'))} |"
            )
    return lines


def _relative_antiscia_lines(items: Any, type_label: str) -> list[str]:
    """AstroRelative.js:120-133 pushAntisciaArray（映点 / 反映点）：空列表 → []。"""
    if not isinstance(items, list) or not items:
        return []
    return [*_REL_ASPECT_HEAD, *(
        f"| {_rel_msg(_rel_get(item, 'idA'))} | {_rel_msg(_rel_get(item, 'idB'))} | {type_label} | {_rel_round3(_rel_get(item, 'delta'))} |"
        for item in items
    )]


def _relative_score_lines(items: Any) -> list[str]:
    """AstroRelative.js:212-225 pushScoreAsps（顺畅连接 / 张力连接）：前 12 条；空 → []。"""
    arr = (items if isinstance(items, list) else [])[:12]
    if not arr:
        return []
    return ["| 星A | 星B | 相位 | 权重 | 误差 |", "| --- | --- | --- | --- | --- |", *(
        f"| {_rel_msg(_rel_get(it, 'a'))} | {_rel_msg(_rel_get(it, 'b'))} | {_rel_aspect_text(_rel_get(it, 'aspect'))} | "
        f"{_rel_round3(_rel_get(it, 'impact'))} | {_rel_round3(_rel_get(it, 'orb'))} |"
        for it in arr
    )]


# 本仓 relative 的 `relative` 码 → 上游合盘页签（AstroRelative.js:276-316 hook：Comp 0 / Composite 1 / Synastry 2 /
# TimeSpace 3 / Marks 4）。页签决定 buildRelativeSnapshotText 出哪几段（:160-206）。
_RELATIVE_TAB_BY_CODE = {"0": "Comp", "1": "Composite", "2": "Synastry", "3": "TimeSpace", "4": "Marks"}


def _build_relative_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    """上游 components/astro/AstroRelative.js:135-233 buildRelativeSnapshotText 逐字移植（本仓一次只起一个盘型 +
    上游无头合盘 buildRelativeSnapshotForRecords（aiAnalysisContext.js:1225-1260）同款把「关系量化」接在后面）。

    - 比较盘（Comp）：A/B 互摄相位 · 中点相位 · 映点/反映点 八张 GFM 表（空列表不产段）+ [比较盘-星盘A/B] 无头整盘
      （fields = {hsys}，[Q-441/T-404]）；
    - 组合盘/时空中点盘：[合成图盘]/[时空中点·合成图盘] = 响应盘的无头整盘（fields = {hsys}）；
    - 影响盘/马克斯盘：[影响图盘-星盘A/B]（马克斯前缀）= inner/outer 的无头整盘（fields = null）；
    - 关系量化：契合分数 + 顺畅/张力连接前 12 条（GFM 表）。
    上游不出的段（别的页签的段、空列表）一律不产；这些段在 registry 双登记为条件段。
    """
    lines: list[str] = ["[关系起盘信息]"]
    lines.append(f"盘型：{_relation_name(payload.get('relative'))}")
    inner = payload.get("inner") if isinstance(payload.get("inner"), dict) else {}
    outer = payload.get("outer") if isinstance(payload.get("outer"), dict) else {}
    if inner:
        lines.append(f"星盘A：{inner.get('name') or 'A'} {inner.get('date', '')} {inner.get('time', '')}".strip())
        lines.append(f"星盘A经纬度：{inner.get('lon', '—')} {inner.get('lat', '—')}")
    if outer:
        lines.append(f"星盘B：{outer.get('name') or 'B'} {outer.get('date', '')} {outer.get('time', '')}".strip())
        lines.append(f"星盘B经纬度：{outer.get('lon', '—')} {outer.get('lat', '—')}")
    # [Q-255/T-238·AS-22⑪]（上游 AstroRelative.js:151-159）：出人话标签（此前直出数字「宫制：1」「黄道：0」），
    # 与主命盘快照同源表：宫制 = HouseSys 选项标签；黄道 = zodiacalDisplayText（恒星黄道带岁差名）。
    hsys_raw = payload.get("hsys")
    zodiacal_raw = payload.get("zodiacal")
    zodiacal_key = {"0": "Tropical", "1": "Sidereal"}.get(_js_template_str(zodiacal_raw)) if zodiacal_raw is not None else None
    hsys_text = (HOUSE_SYSTEM_LABELS.get(_js_template_str(hsys_raw)) or hsys_raw) if hsys_raw is not None else "—"
    if zodiacal_raw is None:
        zodiacal_text: Any = "—"
    elif zodiacal_key:
        zodiacal_text = zodiacal_display_text(zodiacal_key, payload.get("siderealAyanamsa") or "")
    else:
        zodiacal_text = zodiacal_raw
    tab = _RELATIVE_TAB_BY_CODE.get(f"{payload.get('relative', 0)}", "Comp")
    # v3.13.0（AstroRelative.js:146-150）：组合盘所选宫制合不出 / 属整宫一类时后端回落（响应带 compositeHouseNote 与
    # 回显的实际宫制 params.hsys）→ 表头如实写「所选 X,本盘实际 Y」（逗号是上游原文的半角「,」）。
    house_note = response.get("compositeHouseNote")
    res_params = response.get("params") if isinstance(response.get("params"), dict) else None
    sel_hsys_str = _js_template_str(hsys_raw) if hsys_raw is not None else "undefined"
    actual_hsys = (
        res_params.get("hsys")
        if tab in ("Composite", "TimeSpace") and house_note and res_params is not None and "hsys" in res_params
        and _js_template_str(res_params.get("hsys")) != sel_hsys_str
        else None
    )
    if actual_hsys is not None:
        actual_text = HOUSE_SYSTEM_LABELS.get(_js_template_str(actual_hsys)) or _js_template_str(actual_hsys)
        lines.append(f"宫制：所选 {hsys_text},本盘实际 {actual_text}")
    else:
        lines.append(f"宫制：{hsys_text}")
    lines.append(f"黄道：{zodiacal_text}")
    # v3.13.0（:154）：AI 双盘挂载（aiAnalysisContext/pair.js 传 unifiedByA）才出的口径行；合盘页 / 本仓 relative 工具不传。
    if payload.get("unifiedByA"):
        lines.append("口径：两盘统一按星盘A的宫制 / 黄道 / 古典口径起盘(星盘B 的单盘段仍按它自己记录的口径)")
    rendered: list[tuple[str, str]] = [("关系起盘信息", _join_lines(lines[1:]))]

    def add(title: str, body_lines: list[str]) -> None:
        body = "\n".join(body_lines).strip()
        if body:
            rendered.append((title, body))

    # 合成盘/比较盘响应无请求 fields：上游把工作台宫制数字位喂进去（:174/:191，`{ hsys: comp.params.hsys }`），
    # 否则 [分宫制宫神星表] 只能靠后端回显文本反查（hsys 8/24 与 1/0 撞名）。影响盘两盘传 null（:199/:204）。
    hsys_fields = {"hsys": payload.get("hsys")} if payload.get("hsys") is not None else {}
    if tab == "Comp":
        add("A对B相位", _relative_aspect_lines(response.get("inToOutAsp")))
        add("B对A相位", _relative_aspect_lines(response.get("outToInAsp")))
        add("A对B中点相位", _relative_midpoint_lines(response.get("inToOutMidpoint")))
        add("B对A中点相位", _relative_midpoint_lines(response.get("outToInMidpoint")))
        add("A对B映点", _relative_antiscia_lines(response.get("inToOutAnti"), "映点"))
        add("A对B反映点", _relative_antiscia_lines(response.get("inToOutCAnti"), "反映点"))
        add("B对A映点", _relative_antiscia_lines(response.get("outToInAnti"), "映点"))
        add("B对A反映点", _relative_antiscia_lines(response.get("outToInCAnti"), "反映点"))
        for title, key in (("比较盘-星盘A", "inner"), ("比较盘-星盘B", "outer")):
            one = response.get(key)
            if isinstance(one, dict) and isinstance(one.get("chart"), dict):
                add(title, [_headerless_astro_snapshot_text(hsys_fields, one)])
    if tab in ("Composite", "TimeSpace") and isinstance(response.get("chart"), dict):
        # v3.13.0（:187-193）：后端回落整宫 / Porphyry 时先写「宫制说明：…」，宫制数字位改取回显的实际值（snapHsys）。
        composite_lines: list[str] = [f"宫制说明：{_js_template_str(house_note)}"] if house_note else []
        if house_note and res_params is not None and "hsys" in res_params:
            snap_fields: dict[str, Any] = {"hsys": res_params.get("hsys")}
        else:
            snap_fields = hsys_fields
        composite_lines.append(_headerless_astro_snapshot_text(snap_fields, response))
        add("时空中点·合成图盘" if tab == "TimeSpace" else "合成图盘", composite_lines)
    if tab in ("Synastry", "Marks"):
        prefix = "马克斯·" if tab == "Marks" else ""
        for title, key in ((f"{prefix}影响图盘-星盘A", "inner"), (f"{prefix}影响图盘-星盘B", "outer")):
            one = response.get(key)
            if isinstance(one, dict) and isinstance(one.get("chart"), dict):
                add(title, [_headerless_astro_snapshot_text({}, one)])
    # 关系量化（AstroRelative.js:207-226 Score 页签；/astroextra/relative 由 `_attach_relative_score` 另取）。
    score = response.get("_relativeScore") if isinstance(response.get("_relativeScore"), dict) else None
    if score and score.get("score") is not None:
        add("关系量化", [f"契合分数：{_js_template_str(score.get('score'))}（0–100，50 为中性；越高越顺畅，越低张力越大）"])
        add("顺畅连接", _relative_score_lines(score.get("highlights")))
        add("张力连接", _relative_score_lines(score.get("challenges")))
    return _render_snapshot_text(rendered)


def _derived_position_lines(positions: Any, label: str) -> list[str]:
    """派生盘位置行——镜像 AuxLab（AstroHarmonicLab.js:75-77 / AstroDraconicLab.js:54-56）：
    `${row.id}：本命黄经 ${Number(natalLon).toFixed(2)}° → {label} ${sign}${Number(signlon).toFixed(2)}°`。
    toFixed 取 double 精确值、平局取大（fmt_num），不是 Python `:.2f` 的银行家舍入。"""
    out: list[str] = []
    for row in positions if isinstance(positions, list) else []:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        natal = fmt_num(row["natalLon"], 2) if row.get("natalLon") is not None else "—"
        signlon = f"{fmt_num(row['signlon'], 2)}°" if row.get("signlon") is not None else ""
        out.append(f"{_js_template_str(row['id'])}：本命黄经 {natal}° → {label} {_js_template_str(row.get('sign') or '')}{signlon}")
    return out


def _derived_conjunction_lines(conjunctions: Any) -> list[str]:
    """AuxLab 同频行：`同频：${c.a} 合 ${c.b}（误差 ${Number(orb).toFixed(3)}）`。"""
    out: list[str] = []
    for c in conjunctions if isinstance(conjunctions, list) else []:
        if isinstance(c, dict) and c.get("a") and c.get("b"):
            orb = fmt_num(c["orb"], 3) if c.get("orb") is not None else "—"
            out.append(f"同频：{_js_template_str(c['a'])} 合 {_js_template_str(c['b'])}（误差 {orb}）")
    return out


def _chart_angles(chart_shaped: Any) -> dict[str, dict[str, Any]]:
    """四角（Asc/MC/Desc/IC）——镜像 AstroRelocationLab.anglesOf：读 chart.objects 按 id 过滤。"""
    chart = chart_shaped.get("chart") if isinstance(chart_shaped, dict) else None
    objects = chart.get("objects") if isinstance(chart, dict) else None
    out: dict[str, dict[str, Any]] = {}
    for obj in objects if isinstance(objects, list) else []:
        if isinstance(obj, dict) and obj.get("id") in ("Asc", "MC", "Desc", "IC"):
            out[obj["id"]] = obj
    return out


def _angle_text(obj: dict[str, Any] | None) -> str:
    """AstroRelocationLab.js:144：`n ? `${n.sign || ''}${Number(n.signlon).toFixed(2)}°` : '—'`（角点在而空 → 空串，不补 —）。"""
    if not isinstance(obj, dict):
        return "—"
    signlon = f"{fmt_num(obj['signlon'], 2)}°" if obj.get("signlon") is not None else ""
    return f"{_js_template_str(obj.get('sign') or '')}{signlon}"


def _reloc_display_degree(value: Any, *, lat: bool) -> str:
    """AstroRelocationLab.js:51-55/139：页面 state 存十进制度 `Number(deg.toFixed(4))`，[重置盘] 地点行按它出
    （如 40n43 → 40.7167、74w00 → -74）。字符串走 AstroHelper.convertLat/LonStrToDegree（n/s·e/w 分隔，整数度分）。"""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        degree = float(value)
    else:
        text = f"{value if value is not None else ''}".lower().strip()
        pos, neg = ("n", "s") if lat else ("e", "w")
        parts = text.split(pos)
        sign = 1
        if len(parts) == 1:
            parts = text.split(neg)
            sign = -1

        def js_int(raw: str) -> int:
            m = re.match(r"\s*[+-]?\d+", raw)
            return int(m.group(0)) if m else 0

        degree = (js_int(parts[0]) + (js_int(parts[1]) if len(parts) > 1 else 0) / 60.0) * sign
    if not math.isfinite(degree):
        return "0"
    return _js_template_str(float(fmt_num(degree, 4)))
