from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_COMPACT_COORD_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([NSEWnsew])\s*(\d+(?:\.\d+)?)\s*$")
_DECIMAL_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?$")
_ZONE_HM_RE = re.compile(r"^(?P<sign>[+-]?)(?P<hours>\d{1,2})(?::(?P<minutes>\d{1,2}))?$")
_DATE_RE = re.compile(r"^(?P<year>\d{4})(?P<sep>[-/])(?P<month>\d{1,2})(?P=sep)(?P<day>\d{1,2})$")
_TIME_RE = re.compile(r"^(?P<hour>\d{1,2}):(?P<minute>\d{1,2})(?::(?P<second>\d{1,2}))?$")
_DATETIME_RE = re.compile(
    r"^(?P<date>\d{4}[-/]\d{1,2}[-/]\d{1,2})(?P<sep>[T\s]+)(?P<time>\d{1,2}:\d{1,2}(?::\d{1,2})?)$"
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
    return normalized


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
    return f"{int(match.group('year')):04d}-{int(match.group('month')):02d}-{int(match.group('day')):02d}"


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


def _normalize_iana_zone_value(text: str, *, payload: dict[str, Any] | None, key: str) -> str | None:
    if "/" not in text:
        return None
    try:
        zone = ZoneInfo(text)
    except (ZoneInfoNotFoundError, ValueError):
        return None

    reference = _reference_datetime_for_zone(payload or {}, key)
    if reference is None:
        return None
    offset = reference.replace(tzinfo=zone).utcoffset()
    if offset is None:
        return None
    return _format_zone_offset(offset.total_seconds() / 3600)


def _reference_datetime_for_zone(payload: dict[str, Any], key: str) -> datetime | None:
    if key == "guaZone":
        reference = _combine_date_time(payload.get("guaDate"), payload.get("guaTime"))
        if reference is not None:
            return reference
    if key == "dirZone":
        reference = _parse_datetime_text(payload.get("datetime"))
        if reference is not None:
            return reference
    return _combine_date_time(payload.get("date"), payload.get("time")) or _parse_datetime_text(payload.get("datetime"))


def _combine_date_time(date_value: Any, time_value: Any) -> datetime | None:
    if date_value is None or time_value is None:
        return None
    date_text = str(date_value).strip()
    time_text = str(time_value).strip()
    date_match = _DATE_RE.match(date_text)
    time_match = _TIME_RE.match(time_text)
    if not date_match or not time_match:
        return None
    try:
        return datetime(
            int(date_match.group("year")),
            int(date_match.group("month")),
            int(date_match.group("day")),
            int(time_match.group("hour")),
            int(time_match.group("minute")),
            int(time_match.group("second") or "0"),
        )
    except ValueError:
        # The regexes accept digit-shaped but calendar-invalid values (month 13, day 45,
        # hour 99, ...). Degrade like a regex miss instead of crashing normalization — the
        # backend will reject the bad date with a structured param error.
        return None


def _parse_datetime_text(value: Any) -> datetime | None:
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
