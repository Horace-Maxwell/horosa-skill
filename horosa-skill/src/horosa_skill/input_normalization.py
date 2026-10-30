from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_COMPACT_COORD_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([NSEWnsew])\s*(\d+(?:\.\d+)?)\s*$")
_DECIMAL_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?$")
_ZONE_HM_RE = re.compile(r"^(?P<sign>[+-]?)(?P<hours>\d{1,2})(?::(?P<minutes>\d{1,2}))?$")
# 年带符号、1–5 位（上游 dateStrSafe.parseDateParts 同域：公元前 '-0500-03-21'、五位年 '10000-01-01'）；
# 归一成 formatSignedDate 同形（负年前导负号、年不足 4 位补零、5 位原样）。旧式只认四位无号年：公元前 / 五位年原样透传，
# 月日不补零、IANA 时区也换算不了偏移。
_DATE_RE = re.compile(r"^(?P<year>-?\d{1,5})(?P<sep>[-/])(?P<month>\d{1,2})(?P=sep)(?P<day>\d{1,2})$")
_TIME_RE = re.compile(r"^(?P<hour>\d{1,2}):(?P<minute>\d{1,2})(?::(?P<second>\d{1,2}))?$")
_DATETIME_RE = re.compile(
    r"^(?P<date>-?\d{1,5}[-/]\d{1,2}[-/]\d{1,2})(?P<sep>[T\s]+)(?P<time>\d{1,2}:\d{1,2}(?::\d{1,2})?)$"
)


def normalize_request_payload(payload: Any) -> Any:
    if isinstance(payload, list):
        return [normalize_request_payload(item) for item in payload]
    if not isinstance(payload, dict):
        return payload

    normalized = {key: normalize_request_payload(value) for key, value in payload.items()}
    _normalize_date_like_fields(normalized)
    _normalize_zone_fields(normalized)
    _normalize_coordinate_fields(normalized)
    _normalize_gender_field(normalized)
    return normalized


# 性别标签 → 0(女)/1(男)。八字链（bazi/canping/heluo/yizhangjing）下游按 0/1 判大运/大限顺逆；
# 若字符串标签（'女'/'Female'/'F'…）原样进 JS，Number(...) 得 NaN → 恒判男 → 女命方向反转。
# 只归一「可识别的字符串标签」，int/None/未识别值一律不动（零回归：既有 0/1 调用不受影响）。
_GENDER_MALE_LABELS = {"男", "male", "m", "boy", "man", "nan", "男性", "乾", "1"}
_GENDER_FEMALE_LABELS = {"女", "female", "f", "girl", "woman", "nv", "女性", "坤", "0"}


def _normalize_gender_field(payload: dict[str, Any]) -> None:
    value = payload.get("gender")
    if isinstance(value, bool):
        # Java 后端读 1/0；bool 直传会变成 JSON true/false（v0.36.0，PR #17）
        payload["gender"] = 1 if value else 0
        return
    if not isinstance(value, str):
        return
    key = value.strip().lower()
    if key in _GENDER_MALE_LABELS:
        payload["gender"] = 1
    elif key in _GENDER_FEMALE_LABELS:
        payload["gender"] = 0


def _normalize_date_like_fields(payload: dict[str, Any]) -> None:
    for key in ("date", "datetime", "guaDate", "guaTime", "time"):
        if key not in payload:
            continue
        normalized = _normalize_date_like_value(key, payload.get(key))
        if normalized is not None:
            payload[key] = normalized


def _normalize_date_like_value(key: str, value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return text

    if key in {"date", "guaDate"}:
        return _normalize_date_value(text)
    if key in {"time", "guaTime"}:
        return _normalize_time_value(text)
    if key == "datetime":
        return _normalize_datetime_value(text)
    return text


def _normalize_date_value(text: str) -> str:
    match = _DATE_RE.match(text)
    if not match:
        return text
    year = int(match.group("year"))
    sign = "-" if match.group("year").startswith("-") else ""
    return f"{sign}{abs(year):04d}-{int(match.group('month')):02d}-{int(match.group('day')):02d}"


def _normalize_time_value(text: str) -> str:
    match = _TIME_RE.match(text)
    if not match:
        return text
    second = int(match.group("second") or "0")
    return f"{int(match.group('hour')):02d}:{int(match.group('minute')):02d}:{second:02d}"


def _normalize_datetime_value(text: str) -> str:
    match = _DATETIME_RE.match(text)
    if not match:
        return text
    date_text = _normalize_date_value(match.group("date"))
    time_text = _normalize_time_value(match.group("time"))
    separator = "T" if "T" in match.group("sep") else " "
    return f"{date_text}{separator}{time_text}"


def _normalize_zone_fields(payload: dict[str, Any]) -> None:
    for key in ("zone", "dirZone", "guaZone"):
        if key not in payload:
            continue
        normalized = _normalize_zone_value(payload.get(key), payload=payload, key=key)
        if normalized is not None:
            payload[key] = normalized


def _normalize_coordinate_fields(payload: dict[str, Any]) -> None:
    for value_key, gps_key, axis in (
        ("lat", "gpsLat", "lat"),
        ("lon", "gpsLon", "lon"),
        ("dirLat", None, "lat"),
        ("dirLon", None, "lon"),
        ("guaLat", None, "lat"),
        ("guaLon", None, "lon"),
    ):
        raw_value = payload.get(value_key)
        raw_decimal = _coerce_coordinate_decimal(raw_value)
        if raw_decimal is not None:
            payload[value_key] = _format_compact_coordinate(raw_decimal, axis=axis)

        if not gps_key:
            continue

        gps_value = payload.get(gps_key)
        gps_decimal = _coerce_coordinate_decimal(gps_value)
        if gps_decimal is None and raw_decimal is not None:
            payload[gps_key] = round(raw_decimal, 6)
        elif gps_decimal is not None:
            payload[gps_key] = round(gps_decimal, 6)
            if raw_value is None:
                payload[value_key] = _format_compact_coordinate(gps_decimal, axis=axis)


def _normalize_zone_value(value: Any, *, payload: dict[str, Any] | None = None, key: str = "zone") -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _format_zone_offset(float(value))

    text = str(value).strip()
    if not text:
        return text

    iana_offset = _normalize_iana_zone_value(text, payload=payload, key=key)
    if iana_offset is not None:
        return iana_offset

    offset_text = text.upper().replace("UTC", "").replace("GMT", "").strip()
    if offset_text in ("", "Z"):
        # Bare UTC / GMT / Z (and "UTC"/"GMT" alone) -> canonical zero offset.
        return "+00:00"
    if ":" not in offset_text:
        compact_match = re.fullmatch(r"(?P<sign>[+-]?)(?P<digits>\d{3,4})", offset_text)
        if compact_match:
            sign = compact_match.group("sign") or "+"
            digits = compact_match.group("digits")
            hours = int(digits[:-2])
            minutes = int(digits[-2:])
            if minutes < 60:
                return _format_zone_offset((-1 if sign == "-" else 1) * (hours + minutes / 60))
    match = _ZONE_HM_RE.match(offset_text)
    if not match:
        if _DECIMAL_RE.match(offset_text):
            return _format_zone_offset(float(offset_text))
        return str(value)

    sign = -1 if match.group("sign") == "-" else 1
    hours = int(match.group("hours"))
    minutes = int(match.group("minutes") or "0")
    if minutes >= 60:
        return str(value)
    total_hours = sign * (hours + minutes / 60)
    return _format_zone_offset(total_hours)


# 中国大陆统一北京时间口径（上游 utils/timezone.js:124-151 unifyCnZone，horosa_tz_cn_unified_v1）：IANA 把新疆
# 划为 Asia/Urumqi（+06:00，民间「新疆时间」），而出生证/户籍/医院记录一律按法定北京时间。统一时间起点
# （1949-10-01）之后 Asia/Urumqi → Asia/Shanghai，**只做 IANA 名归并、不写死偏移**（1986–1991 夏令时照常
# 得 +09:00；统一前的新疆出生仍按 +06:00）。归并时在载荷里留 geoZone（原地理时区）+ zoneAdvisory='cn-unified'，
# 技法卡与 warnings 据此回显。退出口：cnUnifiedZone=false（上游 kill-switch 是 localStorage 'horosa.tz.cnUnified'='0'），
# 或直接给偏移 "+06:00"（偏移不归并）。
_CN_UNIFIED_SINCE_YMD = (1949, 10, 1)
_CN_UNIFY = {"Asia/Urumqi": "Asia/Shanghai"}
_OPT_OUT_VALUES = (False, 0, "0", "false", "False", "no", "off")


def _cn_unified_enabled(payload: dict[str, Any]) -> bool:
    return payload.get("cnUnifiedZone") not in _OPT_OUT_VALUES


def _normalize_iana_zone_value(text: str, *, payload: dict[str, Any] | None, key: str) -> str | None:
    if "/" not in text:
        return None
    reference = _reference_datetime_for_zone(payload or {}, key)
    unified_from: str | None = None
    target = _CN_UNIFY.get(text)
    # 上游：只有能解析出 YYYY-MM-DD 且早于起点才不归并（日期缺失照样归并——但缺日期本仓也算不出偏移，
    # 下面 reference 为 None 时原样返回 None，不改 zone）。按 (年, 月, 日) 比较：strftime('%Y') 对四位以下的年
    # 不补零（平台相关），字符串比较会把公元 100 年判成「晚于 1949」。
    if (
        target
        and payload is not None
        and _cn_unified_enabled(payload)
        and reference is not None
        and reference[:3] >= _CN_UNIFIED_SINCE_YMD
    ):
        unified_from, text = text, target
    try:
        zone = ZoneInfo(text)
    except (ZoneInfoNotFoundError, ValueError):
        return None

    if reference is None:
        return None
    if unified_from is not None and payload is not None:
        payload.setdefault("geoZone", unified_from)
        payload["zoneAdvisory"] = "cn-unified"
    wall = _wall_datetime_for_offset(reference)
    offset = wall.replace(tzinfo=zone).utcoffset() if wall is not None else None
    if offset is None:
        return None
    return _format_offset_seconds(offset.total_seconds())


def _wall_datetime_for_offset(reference: tuple[int, int, int, int, int, int]) -> datetime | None:
    """参照钟面 → datetime（只拿来问时区偏移）。年份按外推格里历读（上游 offsetForZoneAtDate 经 parseDateTimeMs 同口径）；
    datetime 只认 1–9999 年：公元前 / 五位年平移整 400 年（外推格里历 400 年 = 146097 天、星期与闰年分布逐日重合，
    时区规则得同一偏移；公元 1 年以前本就是地方平时 LMT）。2 月 29 日落在格里历平年 → 3 月 1 日（JS Date 同样进位）；
    其余不存在的日子（2 月 30 日、13 月…）→ None（上游 parseDateTimeParts 同样拒收）。"""
    year, month, day, hour, minute, second = reference
    if year < 1:
        year += 400 * ((1 - year + 399) // 400)
    elif year > 9999:
        year -= 400 * ((year - 9999 + 399) // 400)
    try:
        return datetime(year, month, day, hour, minute, second)
    except ValueError:
        if month == 2 and day == 29 and 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59:
            return datetime(year, 3, 1, hour, minute, second)
        return None


def _format_offset_seconds(total_seconds: float) -> str:
    """UTC 偏移秒数 → '±HH:MM'，秒数舍去（上游 offsetForZoneAtDate 读 Intl longOffset 'GMT+01:34:52' 只取时、分）。
    整分钟的时区与旧 round 口径逐字相同；地方平时（LMT，如雅典 +01:34:52、佛罗伦萨所在 Europe/Rome +00:49:56）
    旧 round 进成 +01:35 / +00:50，与上游差一分钟。"""
    sign = "+" if total_seconds >= 0 else "-"
    hours, minutes = divmod(int(abs(total_seconds)) // 60, 60)
    return f"{sign}{hours:02d}:{minutes:02d}"


def _reference_datetime_for_zone(payload: dict[str, Any], key: str) -> tuple[int, int, int, int, int, int] | None:
    if key == "guaZone":
        reference = _combine_date_time(payload.get("guaDate"), payload.get("guaTime"))
        if reference is not None:
            return reference
    if key == "dirZone":
        reference = _parse_datetime_text(payload.get("datetime"))
        if reference is not None:
            return reference
    return _combine_date_time(payload.get("date"), payload.get("time")) or _parse_datetime_text(payload.get("datetime"))


def _combine_date_time(date_value: Any, time_value: Any) -> tuple[int, int, int, int, int, int] | None:
    """(带符号显示年, 月, 日, 时, 分, 秒)；日期 / 时刻形状认不出、或数值越界（13 月、45 日、99 时）→ None。"""
    if date_value is None or time_value is None:
        return None
    date_text = str(date_value).strip()
    time_text = str(time_value).strip()
    date_match = _DATE_RE.match(date_text)
    time_match = _TIME_RE.match(time_text)
    if not date_match or not time_match:
        return None
    reference = (
        int(date_match.group("year")),
        int(date_match.group("month")),
        int(date_match.group("day")),
        int(time_match.group("hour")),
        int(time_match.group("minute")),
        int(time_match.group("second") or "0"),
    )
    # The regexes accept digit-shaped but calendar-invalid values (month 13, day 45,
    # hour 99, ...). Degrade like a regex miss instead of crashing normalization — the
    # backend will reject the bad date with a structured param error.
    return reference if _wall_datetime_for_offset(reference) is not None else None


def _parse_datetime_text(value: Any) -> tuple[int, int, int, int, int, int] | None:
    if value is None:
        return None
    text = str(value).strip()
    match = _DATETIME_RE.match(text)
    if not match:
        return None
    return _combine_date_time(match.group("date"), match.group("time"))


def _format_zone_offset(offset_hours: float) -> str:
    sign = "+" if offset_hours >= 0 else "-"
    total_minutes = round(abs(offset_hours) * 60)
    hours, minutes = divmod(total_minutes, 60)
    return f"{sign}{hours:02d}:{minutes:02d}"


def _coerce_coordinate_decimal(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    compact_match = _COMPACT_COORD_RE.match(text)
    if compact_match:
        degrees = float(compact_match.group(1))
        hemisphere = compact_match.group(2).lower()
        minutes = float(compact_match.group(3))
        decimal = degrees + minutes / 60
        if hemisphere in {"s", "w"}:
            decimal *= -1
        return decimal

    if _DECIMAL_RE.match(text):
        return float(text)
    return None


def _format_compact_coordinate(decimal_value: float, *, axis: str) -> str:
    hemisphere_positive = "n" if axis == "lat" else "e"
    hemisphere_negative = "s" if axis == "lat" else "w"
    hemisphere = hemisphere_positive if decimal_value >= 0 else hemisphere_negative
    absolute = abs(decimal_value)
    degrees = int(absolute)
    minutes = round((absolute - degrees) * 60)
    if minutes == 60:
        degrees += 1
        minutes = 0
    return f"{degrees}{hemisphere}{minutes:02d}"
