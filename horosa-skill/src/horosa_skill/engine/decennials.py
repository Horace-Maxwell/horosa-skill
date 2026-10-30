from __future__ import annotations

import math
import time
from datetime import datetime
from typing import Any

from horosa_skill.civil_calendar import (
    _civil_date_str_of_ms,
    _civil_wall_ms_of_moment,
    _zone_offset_minutes_of,
)


def _js_round(value: float) -> int:
    """Match JavaScript ``Math.round`` (round half toward +infinity).

    Python's built-in ``round`` is banker's rounding (half-to-even), so ``round(2.5) == 2`` while
    ``Math.round(2.5) === 3``. The 星阙 ``decennials.js`` source uses ``Math.round`` throughout, so the
    port must mirror it exactly to stay value-identical.
    """
    return math.floor(value + 0.5)


DECENNIAL_START_MODE_SECT_LIGHT = "sect_light"
DECENNIAL_ORDER_ZODIACAL = "zodiacal"
DECENNIAL_ORDER_CHALDEAN = "chaldean"
DECENNIAL_DAY_METHOD_VALENS = "valens"
DECENNIAL_DAY_METHOD_HEPHAISTIO = "hephaistio"
DECENNIAL_CALENDAR_TRADITIONAL = "calendar_360"
DECENNIAL_CALENDAR_ACTUAL = "calendar_365_25"

DECENNIAL_TRADITIONAL_PLANETS = [
    "Saturn",
    "Jupiter",
    "Mars",
    "Sun",
    "Venus",
    "Mercury",
    "Moon",
]

DECENNIAL_PLANET_BASE_MONTHS = {
    "Saturn": 30,
    "Jupiter": 12,
    "Mars": 15,
    "Sun": 19,
    "Venus": 8,
    "Mercury": 20,
    "Moon": 25,
}

DECENNIAL_HEPHAISTIO_DAY_TABLE = {
    "Saturn": {"Saturn": 210, "Jupiter": 84, "Mars": 105, "Sun": 133, "Venus": 56, "Mercury": 150, "Moon": 175},
    "Jupiter": {"Jupiter": 34, "Saturn": 85, "Mars": 42, "Sun": 54, "Venus": 22, "Mercury": 57, "Moon": 71},
    "Mars": {"Mars": 52, "Sun": 66, "Venus": 28, "Mercury": 70, "Moon": 87, "Saturn": 105, "Jupiter": 42},
    "Sun": {"Sun": 83, "Moon": 118, "Saturn": 130, "Jupiter": 52, "Mars": 64, "Venus": 35, "Mercury": 87},
    "Venus": {"Venus": 15, "Sun": 36, "Moon": 47, "Saturn": 57, "Jupiter": 22, "Mars": 28, "Mercury": 38},
    "Mercury": {"Mercury": 96, "Sun": 90, "Moon": 117, "Saturn": 141, "Jupiter": 56, "Mars": 70, "Venus": 36},
    "Moon": {"Moon": 148, "Sun": 115, "Saturn": 177, "Jupiter": 71, "Mars": 87, "Venus": 47, "Mercury": 119},
}

TOTAL_BASE_MONTHS = 129
TOTAL_L1_DAYS = TOTAL_BASE_MONTHS * 30
FIVE_MINUTES = 5
MINUTES_PER_DAY = 24 * 60
MINUTES_PER_MONTH = 30 * MINUTES_PER_DAY
MINUTES_PER_YEAR = 12 * MINUTES_PER_MONTH
ACTUAL_YEAR_SCALE_NUMERATOR = 1461
ACTUAL_YEAR_SCALE_DENOMINATOR = 1440

PLANET_ALIASES = {
    "saturn": "Saturn",
    "jupiter": "Jupiter",
    "mars": "Mars",
    "sun": "Sun",
    "venus": "Venus",
    "mercury": "Mercury",
    "moon": "Moon",
}


def _normalize_planet_id(value: Any) -> str | None:
    text = f"{value or ''}".strip()
    if not text:
        return None
    return PLANET_ALIASES.get(text.lower(), text)


# 期界时刻的表示：(墙钟毫秒, 时区分钟)。墙钟毫秒 = 出生地钟面在民用历墙钟轴上的位置（civilCalendar.civilWallMs，
# 1970-01-01 00:00 = 0）。上游 moment 的「外推格里历同一天 + 固定 utcOffset」与它逐分钟同构：按分钟加减、与此刻比先后都是
# 线性的；标签一律经 civilDateOfMoment（= 本轴的民用历日期），1582-10-15 以后与 moment.format 逐字相同。
_MS_PER_MINUTE = 60000


def _local_offset_minutes() -> int:
    """本机此刻时区偏移（分钟）：上游 zonedMomentOfCivilDateTimeStr 时区认不出时退回 momentOfCivilDateTimeStr（本机钟面）。"""
    offset = datetime.now().astimezone().utcoffset()
    return int(offset.total_seconds() // 60) if offset is not None else 0


def _parse_birth_moment(chart_obj: dict[str, Any]) -> tuple[int, int] | None:
    """上游 v3.12.0 decennials.parseBirthMoment = civilMoment.zonedBirthMomentOfChart(chartObj, '+08:00')：
    params.birth（或 date + time）经民用历单源读（公元前负号、五位年、儒略闰日都认，日期不存在 → 无效），
    落在 params.zone（缺省 +08:00；认不出 → 本机钟面）上。返回 (墙钟毫秒, 时区分钟)；无效 → None。"""
    params = chart_obj.get("params", {}) if isinstance(chart_obj, dict) else {}
    params = params if isinstance(params, dict) else {}
    birth = f"{params.get('birth') or ''}".strip()
    date_text = f"{params.get('date') or ''}".strip()
    time_text = f"{params.get('time') or ''}".strip()
    text = birth or f"{date_text} {time_text}".strip()
    zone = params.get("zone")
    if zone is None or f"{zone}".strip() == "":
        zone = "+08:00"
    wall = _civil_wall_ms_of_moment(text, strict=True)
    if wall is None:
        return None
    zone_min = _zone_offset_minutes_of(zone)
    if zone_min is None:
        zone_min = _local_offset_minutes()
    return wall, zone_min


def _iso_of(wall_ms: float, zone_min: int) -> str:
    """出生时刻的 ISO 形（民用历日期 + 钟面 + 偏移；1582-10-15 以后与 datetime.isoformat() 逐字相同）。"""
    seconds_of_day = int(math.floor(wall_ms / 1000)) % 86400
    sign = "-" if zone_min < 0 else "+"
    hh, mm = divmod(abs(zone_min), 60)
    return (
        f"{_civil_date_str_of_ms(wall_ms)}T{seconds_of_day // 3600:02d}:{seconds_of_day // 60 % 60:02d}:"
        f"{seconds_of_day % 60:02d}{sign}{hh:02d}:{mm:02d}"
    )


def _civil_label(wall_ms: float, with_time: bool) -> str:
    """decennials.civilLabelOf：民用历日期（+ 出生地钟面 HH:mm）。"""
    date = _civil_date_str_of_ms(wall_ms)
    if not with_time:
        return date
    minutes_of_day = int(math.floor(wall_ms / _MS_PER_MINUTE)) % (24 * 60)
    return f"{date} {minutes_of_day // 60:02d}:{minutes_of_day % 60:02d}"


def _safe_lon(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    normalized = number % 360.0
    if normalized < 0:
        normalized += 360.0
    return normalized


def _find_object(chart_obj: dict[str, Any], planet: str) -> dict[str, Any] | None:
    chart = chart_obj.get("chart", {}) if isinstance(chart_obj, dict) else {}
    objects = chart.get("objects") if isinstance(chart, dict) else []
    if not isinstance(objects, list):
        return None
    for item in objects:
        if not isinstance(item, dict):
            continue
        candidate = _normalize_planet_id(item.get("id"))
        if candidate == planet:
            return item
    return None


def _rotate_list(items: list[str], start_value: str | None) -> list[str]:
    if not items or not start_value or start_value not in items:
        return list(items)
    idx = items.index(start_value)
    return items[idx:] + items[:idx]


def _build_zodiacal_order(chart_obj: dict[str, Any]) -> list[str]:
    ranked: list[tuple[float, int, str]] = []
    for idx, planet in enumerate(DECENNIAL_TRADITIONAL_PLANETS):
        obj = _find_object(chart_obj, planet)
        if not obj:
            return list(DECENNIAL_TRADITIONAL_PLANETS)
        lon = _safe_lon(obj.get("lon"))
        if lon is None:
            lon = _safe_lon(obj.get("signlon"))
        if lon is None:
            return list(DECENNIAL_TRADITIONAL_PLANETS)
        ranked.append((lon, idx, planet))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [planet for _, _, planet in ranked]


def resolve_decennial_start_planet(chart_obj: dict[str, Any], start_mode: str | None) -> str:
    if start_mode and start_mode != DECENNIAL_START_MODE_SECT_LIGHT:
        normalized = _normalize_planet_id(start_mode)
        if normalized in DECENNIAL_TRADITIONAL_PLANETS:
            return normalized
    chart = chart_obj.get("chart", {}) if isinstance(chart_obj, dict) else {}
    is_diurnal = bool(chart.get("isDiurnal")) if isinstance(chart, dict) else False
    return "Sun" if is_diurnal else "Moon"


def get_decennial_order(chart_obj: dict[str, Any], start_planet: str, order_type: str | None) -> list[str]:
    base = list(DECENNIAL_TRADITIONAL_PLANETS) if order_type == DECENNIAL_ORDER_CHALDEAN else _build_zodiacal_order(chart_obj)
    return _rotate_list(base, start_planet)


def _get_rounded_distribution(total_value: float, order: list[str], round_unit: int, preserve_last: bool = True) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    consumed = 0.0
    for index, planet in enumerate(order):
        exact = total_value * DECENNIAL_PLANET_BASE_MONTHS[planet] / TOTAL_BASE_MONTHS
        value = exact
        if index == len(order) - 1 and preserve_last:
            value = total_value - consumed
        elif round_unit > 0:
            value = _js_round(exact / round_unit) * round_unit
        value = max(0.0, value)
        consumed += value
        segments.append({"planet": planet, "value": value})
    return segments


def _minutes_from_level_three(total_days: float, day_method: str | None, month_lord: str, order: list[str]) -> list[dict[str, Any]]:
    if day_method == DECENNIAL_DAY_METHOD_HEPHAISTIO:
        table = DECENNIAL_HEPHAISTIO_DAY_TABLE.get(month_lord)
        if table:
            return [{"planet": planet, "value": table.get(planet, 0) * MINUTES_PER_DAY} for planet in order]
        return [{"planet": item["planet"], "value": item["value"] * MINUTES_PER_DAY} for item in _get_rounded_distribution(total_days, order, 1)]
    return _get_rounded_distribution(total_days * MINUTES_PER_DAY, order, FIVE_MINUTES)


def _minutes_from_level_four(total_minutes: float, order: list[str]) -> list[dict[str, Any]]:
    return _get_rounded_distribution(total_minutes, order, 1)


def _scale_nominal_minutes(total_minutes: float, calendar_type: str | None) -> int:
    normalized = max(0, _js_round(float(total_minutes or 0)))
    if calendar_type != DECENNIAL_CALENDAR_ACTUAL:
        return normalized
    return _js_round(normalized * ACTUAL_YEAR_SCALE_NUMERATOR / ACTUAL_YEAR_SCALE_DENOMINATOR)


def _scale_nominal_segments(segments: list[dict[str, Any]], calendar_type: str | None, round_unit: int = 1) -> list[dict[str, Any]]:
    if calendar_type != DECENNIAL_CALENDAR_ACTUAL:
        return [{"planet": item["planet"], "value": max(0, _js_round(float(item["value"] or 0)))} for item in segments]
    unit = round_unit if round_unit > 0 else 1
    total_nominal = sum(max(0.0, float(item["value"] or 0)) for item in segments)
    total_scaled = _js_round(_scale_nominal_minutes(total_nominal, calendar_type) / unit) * unit
    scaled: list[dict[str, Any]] = []
    consumed = 0
    cumulative_exact = 0.0
    for index, item in enumerate(segments):
        nominal_value = max(0.0, float(item["value"] or 0))
        cumulative_exact += nominal_value * ACTUAL_YEAR_SCALE_NUMERATOR / ACTUAL_YEAR_SCALE_DENOMINATOR
        if index == len(segments) - 1:
            value = total_scaled - consumed
        else:
            value = _js_round(cumulative_exact / unit) * unit - consumed
        value = max(0, value)
        consumed += value
        scaled.append({"planet": item["planet"], "value": value})
    return scaled


def _format_range(start_moment: float, end_moment: float, with_time: bool) -> str:
    return f"{_civil_label(start_moment, with_time)} - {_civil_label(end_moment, with_time)}"


def _format_nominal_offset(total_minutes: int, level: int) -> str:
    minutes = max(0, _js_round(total_minutes or 0))
    years, minutes = divmod(minutes, MINUTES_PER_YEAR)
    months, minutes = divmod(minutes, MINUTES_PER_MONTH)
    days, minutes = divmod(minutes, MINUTES_PER_DAY)
    hours, minutes = divmod(minutes, 60)
    if level >= 4:
        parts: list[str] = []
        if years:
            parts.append(f"{years}年")
        if months:
            parts.append(f"{months}个月")
        if days:
            parts.append(f"{days}天")
        prefix = "".join(parts) or "0天"
        return f"{prefix} {hours:02d}:{minutes:02d}"
    if level == 3:
        parts = []
        if years:
            parts.append(f"{years}年")
        if months:
            parts.append(f"{months}个月")
        if days or not parts:
            parts.append(f"{days}天")
        return "".join(parts)
    parts = []
    if years:
        parts.append(f"{years}年")
    if months or not parts:
        parts.append(f"{months}个月")
    return "".join(parts)


def _format_nominal_range(start_offset_minutes: int, end_offset_minutes: int, level: int) -> str:
    return f"{_format_nominal_offset(start_offset_minutes, level)} - {_format_nominal_offset(end_offset_minutes, level)}"


def _build_node(
    level: int,
    key: str,
    planet: str,
    start_moment: float,
    end_moment: float,
    now_moment: float,
    sublevel: list[dict[str, Any]],
    start_offset_minutes: int,
    end_offset_minutes: int,
) -> dict[str, Any]:
    with_time = level >= 4
    active = start_moment <= now_moment < end_moment
    return {
        "key": key,
        "level": level,
        "planet": planet,
        "date": _format_range(start_moment, end_moment, with_time),
        "nominal": _format_nominal_range(start_offset_minutes, end_offset_minutes, level),
        "startText": _civil_label(start_moment, with_time),
        "endText": _civil_label(end_moment, with_time),
        "active": active,
        "startOffsetMinutes": start_offset_minutes,
        "endOffsetMinutes": end_offset_minutes,
        "sublevel": sublevel,
    }


def _build_level_four(level_three_node: dict[str, Any], base_order: list[str], now_moment: float, calendar_type: str | None) -> list[dict[str, Any]]:
    order = _rotate_list(base_order, level_three_node["planet"])
    nominal_segments = _minutes_from_level_four(level_three_node["nominalMinutes"], order)
    actual_segments = _scale_nominal_segments(nominal_segments, calendar_type, 1)
    list_data: list[dict[str, Any]] = []
    cursor = level_three_node["startMoment"]
    cursor_offset = level_three_node["startOffsetMinutes"]
    for index, nominal_item in enumerate(nominal_segments):
        actual_item = actual_segments[index]
        next_moment = cursor + actual_item["value"] * _MS_PER_MINUTE
        next_offset = cursor_offset + round(nominal_item["value"])
        list_data.append(
            _build_node(4, f"{level_three_node['key']}_l4_{index}", actual_item["planet"], cursor, next_moment, now_moment, [], cursor_offset, next_offset)
        )
        cursor = next_moment
        cursor_offset = next_offset
    return list_data


def _build_level_three(level_two_node: dict[str, Any], base_order: list[str], day_method: str | None, now_moment: float, calendar_type: str | None) -> list[dict[str, Any]]:
    order = _rotate_list(base_order, level_two_node["planet"])
    nominal_segments = _minutes_from_level_three(level_two_node["nominalDays"], day_method, level_two_node["planet"], order)
    actual_segments = _scale_nominal_segments(nominal_segments, calendar_type, 1)
    list_data: list[dict[str, Any]] = []
    cursor = level_two_node["startMoment"]
    cursor_offset = level_two_node["startOffsetMinutes"]
    for index, nominal_item in enumerate(nominal_segments):
        actual_item = actual_segments[index]
        next_moment = cursor + actual_item["value"] * _MS_PER_MINUTE
        meta = {
            "key": f"{level_two_node['key']}_l3_{index}",
            "planet": actual_item["planet"],
            "startMoment": cursor,
            "endMoment": next_moment,
            "nominalMinutes": round(nominal_item["value"]),
            "startOffsetMinutes": cursor_offset,
            "endOffsetMinutes": cursor_offset + round(nominal_item["value"]),
        }
        sublevel = _build_level_four(meta, base_order, now_moment, calendar_type)
        list_data.append(
            _build_node(3, meta["key"], meta["planet"], meta["startMoment"], meta["endMoment"], now_moment, sublevel, meta["startOffsetMinutes"], meta["endOffsetMinutes"])
        )
        cursor = next_moment
        cursor_offset = meta["endOffsetMinutes"]
    return list_data


def _build_level_two(level_one_node: dict[str, Any], base_order: list[str], day_method: str | None, now_moment: float, calendar_type: str | None) -> list[dict[str, Any]]:
    order = _rotate_list(base_order, level_one_node["planet"])
    nominal_segments = [{"planet": planet, "value": DECENNIAL_PLANET_BASE_MONTHS[planet] * MINUTES_PER_MONTH} for planet in order]
    actual_segments = _scale_nominal_segments(nominal_segments, calendar_type, 1)
    list_data: list[dict[str, Any]] = []
    cursor = level_one_node["startMoment"]
    cursor_offset = level_one_node["startOffsetMinutes"]
    for index, nominal_item in enumerate(nominal_segments):
        actual_item = actual_segments[index]
        next_moment = cursor + actual_item["value"] * _MS_PER_MINUTE
        meta = {
            "key": f"{level_one_node['key']}_l2_{index}",
            "planet": nominal_item["planet"],
            "nominalDays": round(nominal_item["value"]) / MINUTES_PER_DAY,
            "startMoment": cursor,
            "endMoment": next_moment,
            "startOffsetMinutes": cursor_offset,
            "endOffsetMinutes": cursor_offset + round(nominal_item["value"]),
        }
        sublevel = _build_level_three(meta, base_order, day_method, now_moment, calendar_type)
        list_data.append(
            _build_node(2, meta["key"], meta["planet"], meta["startMoment"], meta["endMoment"], now_moment, sublevel, meta["startOffsetMinutes"], meta["endOffsetMinutes"])
        )
        cursor = next_moment
        cursor_offset = meta["endOffsetMinutes"]
    return list_data


def _resolve_l1_count(birth_moment: float | None, now_moment: float, calendar_type: str | None) -> int:
    if birth_moment is None:
        return 7
    age_minutes = max(0.0, (now_moment - birth_moment) / _MS_PER_MINUTE)
    l1_minutes = _scale_nominal_minutes(TOTAL_L1_DAYS * MINUTES_PER_DAY, calendar_type)
    if l1_minutes <= 0:
        return 7
    # JS: Math.max(7, Math.ceil(ageMinutes / l1Minutes) + 2). The previous integer "(x+n-1)//n"
    # ceil-trick floored fractional ages (age_minutes is a float), dropping the final L1 lord for
    # any chart landing in the first <1 minute after a ~10.6-year boundary.
    return max(7, math.ceil(age_minutes / l1_minutes) + 2)


def build_decennial_timeline(
    chart_obj: dict[str, Any], settings: dict[str, Any] | None = None, *, now_ms: float | None = None
) -> dict[str, Any]:
    """上游 utils/decennials.js buildDecennialTimeline。期界时刻在民用历墙钟轴上推（见 `_parse_birth_moment`）；
    `now_ms` = 此刻的 UTC 毫秒（缺省本机此刻；测试冻结用），按出生时区换成钟面（上游 moment().utcOffset(出生偏移)）。"""
    settings = settings or {}
    calendar_type = settings.get("calendarType") or DECENNIAL_CALENDAR_TRADITIONAL
    parsed_birth = _parse_birth_moment(chart_obj)
    birth_moment = parsed_birth[0] if parsed_birth else None
    resolved_start_planet = resolve_decennial_start_planet(chart_obj, settings.get("startMode"))
    order_type = settings.get("orderType") or DECENNIAL_ORDER_ZODIACAL
    day_method = settings.get("dayMethod") or DECENNIAL_DAY_METHOD_VALENS
    if birth_moment is None:
        return {
            "list": [],
            "baseOrder": [],
            "resolvedStartPlanet": resolved_start_planet,
            "orderType": order_type,
            "dayMethod": day_method,
            "calendarType": calendar_type,
            "birthMoment": None,
        }

    zone_min = parsed_birth[1]
    now_moment = (time.time() * 1000 if now_ms is None else float(now_ms)) + zone_min * _MS_PER_MINUTE
    base_order = get_decennial_order(chart_obj, resolved_start_planet, order_type)
    count = _resolve_l1_count(birth_moment, now_moment, calendar_type)
    list_data: list[dict[str, Any]] = []
    l1_nominal_minutes = TOTAL_L1_DAYS * MINUTES_PER_DAY
    l1_actual_minutes = _scale_nominal_minutes(l1_nominal_minutes, calendar_type)
    cursor = birth_moment
    for index in range(count):
        planet = base_order[index % len(base_order)]
        start_moment = cursor
        end_moment = start_moment + l1_actual_minutes * _MS_PER_MINUTE
        start_offset = l1_nominal_minutes * index
        end_offset = start_offset + l1_nominal_minutes
        meta = {
            "key": f"l1_{index}",
            "planet": planet,
            "startMoment": start_moment,
            "endMoment": end_moment,
            "startOffsetMinutes": start_offset,
            "endOffsetMinutes": end_offset,
        }
        sublevel = _build_level_two(meta, base_order, day_method, now_moment, calendar_type)
        list_data.append(_build_node(1, meta["key"], planet, start_moment, end_moment, now_moment, sublevel, start_offset, end_offset))
        cursor = end_moment

    return {
        "list": list_data,
        "baseOrder": base_order,
        "resolvedStartPlanet": resolved_start_planet,
        "orderType": order_type,
        "dayMethod": day_method,
        "calendarType": calendar_type,
        "birthMoment": _iso_of(birth_moment, zone_min),
    }
