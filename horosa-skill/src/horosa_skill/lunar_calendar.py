"""农历 → 公历（1900–2100），只查 `data/lunar_months.json`（scripts/gen_lunar_table.mjs 从 lunar-javascript 生成，与八字 / 黄历 / 万年历
同一个历法引擎）。不手写任何历法规则；表外年份由调用方按「不支持」处理。守卫：tests/test_fix314_lunar_input.py 逐日往返。"""
from __future__ import annotations

import json
from datetime import date, timedelta
from functools import lru_cache
from importlib import resources
from typing import Any

MONTH_NAMES = {1: "正", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七", 8: "八", 9: "九", 10: "十", 11: "冬", 12: "腊"}
_DAY_NAMES = ["初一", "初二", "初三", "初四", "初五", "初六", "初七", "初八", "初九", "初十", "十一", "十二", "十三", "十四", "十五",
              "十六", "十七", "十八", "十九", "二十", "廿一", "廿二", "廿三", "廿四", "廿五", "廿六", "廿七", "廿八", "廿九", "三十"]
WEEKDAYS = "一二三四五六日"


class LunarDateError(ValueError):
    """kind：out_of_range / no_such_leap / day_out_of_range / leap_ambiguous（options 带两个公历日期）。"""

    def __init__(self, *, kind: str, zh: str, en: str, options: list[dict[str, Any]] | None = None) -> None:
        super().__init__(f"{zh} / {en}")  # str(exc) 也是双语（与 errors.bilingual 同形）；调用方另取 zh / en 拼 FieldIssue
        self.kind, self.zh, self.en, self.options = kind, zh, en, options


@lru_cache(maxsize=1)
def _table() -> dict[str, Any]:
    text = resources.files("horosa_skill").joinpath("data/lunar_months.json").read_text(encoding="utf-8")
    return json.loads(text)


def year_range() -> tuple[int, int]:
    lo, hi = _table()["range"]
    return int(lo), int(hi)


def _months(year: int) -> list[tuple[int, int]]:
    entry = _table()["years"].get(str(year))
    if entry is None:
        lo, hi = year_range()
        raise LunarDateError(kind="out_of_range", zh=f"农历自动换算只支持 {lo}–{hi} 年（{year} 年不在内）。",
                             en=f"Lunar dates convert automatically only for {lo}–{hi} (not {year}).")
    return [(int(m), int(d)) for m, d in entry["months"]]


def leap_month(year: int) -> int | None:
    leaps = [-m for m, _ in _months(year) if m < 0]
    return leaps[0] if leaps else None


def label(year: int, month: int, day: int, leap: bool) -> str:
    return f"农历{year}年{'闰' if leap else ''}{MONTH_NAMES[month]}月{_DAY_NAMES[day - 1] if 1 <= day <= 30 else day}"


def to_solar(year: int, month: int, day: int, leap: bool | None = None) -> date:
    """leap=None：没说是不是闰月——该年恰好闰这个月时是歧义（leap_ambiguous），否则按平月。"""
    months = _months(year)
    if not 1 <= month <= 12:
        raise LunarDateError(kind="no_such_month", zh=f"农历没有 {month} 月。", en=f"The lunar calendar has no month {month}.")
    year_leap = leap_month(year)
    if leap is None and year_leap == month:
        plain, leaped = to_solar(year, month, min(day, _days(months, month)), False), None
        try:
            leaped = to_solar(year, month, day, True)
        except LunarDateError:
            leaped = None
        options = [{"value": plain.isoformat(), "label": f"{label(year, month, day, False)}（平月）→ {plain.isoformat()}"}]
        if leaped is not None:
            options.append({"value": leaped.isoformat(), "label": f"{label(year, month, day, True)}（闰月）→ {leaped.isoformat()}"})
        raise LunarDateError(
            kind="leap_ambiguous",
            zh=f"农历 {year} 年有两个{MONTH_NAMES[month]}月（平月与闰月），没说是哪一个。",
            en=f"Lunar year {year} has two month-{month}s (regular and leap); which one is meant?",
            options=options,
        )
    if leap and year_leap != month:
        has = f"这年闰{MONTH_NAMES[year_leap]}月" if year_leap else "这年没有闰月"
        has_en = f"its leap month is {year_leap}" if year_leap else "it has no leap month"
        raise LunarDateError(kind="no_such_leap", zh=f"农历 {year} 年没有闰{MONTH_NAMES[month]}月（{has}）。",
                             en=f"Lunar year {year} has no leap month {month} ({has_en}).")
    start = date.fromisoformat(_table()["years"][str(year)]["start"])
    offset = 0
    for m, days in months:
        if m == (-month if leap else month):
            if not 1 <= day <= days:
                raise LunarDateError(kind="day_out_of_range", zh=f"{label(year, month, 1, bool(leap))[:-2]}只有 {days} 天（没有 {day} 日）。",
                                     en=f"Lunar month {'leap ' if leap else ''}{month} of {year} has {days} days (no day {day}).")
            return start + timedelta(days=offset + day - 1)
        offset += days
    raise LunarDateError(kind="no_such_month", zh=f"农历 {year} 年没有 {month} 月。", en=f"Lunar year {year} has no month {month}.")


def _days(months: list[tuple[int, int]], month: int) -> int:
    return next(days for m, days in months if m == month)


def last_day(year: int, month: int) -> int:
    return _days(_months(year), month)
