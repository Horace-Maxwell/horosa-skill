"""记忆检索的时间范围：`after` / `before` 解析成时刻再比，不按字面比。

`created_at` 存的是秒精度的 UTC（`2026-11-11T03:04:05+00:00`）。此前 `after` / `before` 原样拿去和它做字符串比较：
`昨天`、`11/11/2026` 照收不误（静默返回空或全部），`2026-11-11T08:00+08:00` 与 UTC 串按字典序比，差出八小时。

接受的写法（`ACCEPTED_FORMS`）：
- 只给日期 `2026-11-11`：那一整天。哪个时区的一天：调用方给的 `zone`，没给就用本机时区；结果里说用的是哪个。
- 日期 + 时刻 `2026-11-11T08:30`（`T` 或空格，秒可省）：带偏移（`+08:00` / `Z`）就按它，不带就按 `zone` / 本机时区。
别的一律拒收，错误里列出这些写法。
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, time, timedelta, timezone, tzinfo
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ACCEPTED_FORMS = (
    "2026-11-11",
    "2026-11-11T08:30",
    "2026-11-11 08:30:00",
    "2026-11-11T08:30:00+08:00",
    "2026-11-11T00:30:00Z",
)
ACCEPTED_ZONES = ("+08:00", "-05:00", "UTC", "Asia/Shanghai")

_DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?$", re.IGNORECASE)
_OFFSET = re.compile(r"^([+-])(\d{2}):?(\d{2})$")


class TimeFilterError(ValueError):
    def __init__(self, field: str, value: Any, reason: str) -> None:
        super().__init__(f"{field}: {reason}")
        self.field = field
        self.value = value
        self.reason = reason


def parse_zone(value: Any) -> tuple[tzinfo, str] | None:
    """`+08:00` / `-0500` / `Z` / `UTC` / IANA 名 → (tzinfo, 标签)。空 → None；认不出抛 TimeFilterError。"""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    text = f"{value}".strip()
    if text.upper() in {"Z", "UTC", "GMT"}:
        return UTC, "UTC"
    match = _OFFSET.match(text)
    if match:
        sign, hours, minutes = match.groups()
        if int(hours) > 14 or int(minutes) > 59:
            raise TimeFilterError("zone", value, "offset out of range")
        delta = timedelta(hours=int(hours), minutes=int(minutes))
        label = f"{sign}{hours}:{minutes}"
        return timezone(-delta if sign == "-" else delta), label
    try:
        return ZoneInfo(text), text
    except (ZoneInfoNotFoundError, ValueError):
        raise TimeFilterError("zone", value, "unknown time zone") from None


def _to_utc_string(moment: datetime) -> str:
    return moment.astimezone(UTC).replace(microsecond=0).isoformat()


def _localize(naive: datetime, zone: tzinfo | None) -> datetime:
    if zone is not None:
        return naive.replace(tzinfo=zone)
    return naive.astimezone()  # 本机时区（含那一天的夏令时）


def parse_bound(value: Any, *, field: str, end: bool, zone: tzinfo | None) -> tuple[str, str]:
    """一个边界 → (UTC 串, 用的是谁的时区：`value` / `input` / `machine`)。`end=True` 时只给日期 = 那天的最后一秒。"""
    text = f"{value}".strip() if isinstance(value, str) else ""
    if not text:
        raise TimeFilterError(field, value, "not a date")
    source = "input" if zone is not None else "machine"
    if _DATE_ONLY.match(text):
        try:
            day = date.fromisoformat(text)
        except ValueError:
            raise TimeFilterError(field, value, "not a real date") from None
        moment = _localize(datetime.combine(day, time(23, 59, 59) if end else time(0, 0, 0)), zone)
        return _to_utc_string(moment), source
    if not _DATETIME.match(text):
        raise TimeFilterError(field, value, "not an ISO date or date-time")
    try:
        parsed = datetime.fromisoformat(text.replace(" ", "T", 1).replace("z", "Z").replace("Z", "+00:00"))
    except ValueError:
        raise TimeFilterError(field, value, "not a real date-time") from None
    if parsed.tzinfo is not None:
        return _to_utc_string(parsed), "value"
    return _to_utc_string(_localize(parsed, zone)), source


def resolve_range(after: Any, before: Any, zone_value: Any) -> dict[str, Any]:
    """`after` / `before` / `zone` → `{"after": UTC 串|None, "before": …, "zone": 标签, "zone_source": …}`。

    `zone_source`：`input` = 调用方给的 zone；`machine` = 本机时区；`value` = 两个边界都自带偏移（zone 没用上）。"""
    zone_info = parse_zone(zone_value)
    zone = zone_info[0] if zone_info else None
    result: dict[str, Any] = {"after": None, "before": None}
    sources: set[str] = set()
    for field, value, end in (("after", after, False), ("before", before, True)):
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        result[field], source = parse_bound(value, field=field, end=end, zone=zone)
        sources.add(source)
    if result["after"] and result["before"] and result["after"] > result["before"]:
        raise TimeFilterError("after", after, "after is later than before")
    if not sources:
        return result
    if sources == {"value"}:
        result["zone_source"] = "value"
        result["zone"] = None
    elif zone_info:
        result["zone_source"] = "input"
        result["zone"] = zone_info[1]
    else:
        result["zone_source"] = "machine"
        local = datetime.now().astimezone()
        result["zone"] = local.tzname() or local.strftime("%z")
        result["zone_offset"] = local.strftime("%z")
    return result
