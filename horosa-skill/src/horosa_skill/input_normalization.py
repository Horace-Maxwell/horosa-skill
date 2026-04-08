from __future__ import annotations

import re
from typing import Any

_COMPACT_COORD_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([NSEWnsew])\s*(\d+(?:\.\d+)?)\s*$")
_DECIMAL_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?$")
_ZONE_HM_RE = re.compile(r"^(?P<sign>[+-]?)(?P<hours>\d{1,2})(?::(?P<minutes>\d{1,2}))?$")


def normalize_request_payload(payload: Any) -> Any:
    if isinstance(payload, list):
        return [normalize_request_payload(item) for item in payload]
    if not isinstance(payload, dict):
        return payload

    normalized = {key: normalize_request_payload(value) for key, value in payload.items()}
    _normalize_zone_fields(normalized)
    _normalize_coordinate_fields(normalized)
    return normalized


def _normalize_zone_fields(payload: dict[str, Any]) -> None:
    for key in ("zone", "dirZone", "guaZone"):
        if key not in payload:
            continue
        normalized = _normalize_zone_value(payload.get(key))
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


def _normalize_zone_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _format_zone_offset(float(value))

    text = str(value).strip()
    if not text:
        return text

    text = text.upper().replace("UTC", "").replace("GMT", "").strip()
    match = _ZONE_HM_RE.match(text)
    if not match:
        if _DECIMAL_RE.match(text):
            return _format_zone_offset(float(text))
        return str(value)

    sign = -1 if match.group("sign") == "-" else 1
    hours = int(match.group("hours"))
    minutes = int(match.group("minutes") or "0")
    if minutes >= 60:
        return str(value)
    total_hours = sign * (hours + minutes / 60)
    return _format_zone_offset(total_hours)


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
