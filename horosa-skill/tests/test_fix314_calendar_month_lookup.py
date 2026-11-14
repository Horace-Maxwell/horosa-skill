"""万年历按公历年、月查，纯查历不过闸（审计 S-26：农历日期的拒绝说「用 horosa_cn_calendar_month 给公历年、月」，该工具却不收 year / month，
不带确认位时闸门还问 3 题，含「用哪个时区？」）。负向对照（实跑过）：从 exempt_tools 拿掉 calendar_month → 第一条红。
"""
from __future__ import annotations

from horosa_skill.agent_guidance import validate_agent_preflight
from horosa_skill.schemas.tools.cn_mingli import CalendarMonthInput


def test_calendar_lookup_is_not_gated() -> None:
    assert validate_agent_preflight("calendar_month", {"year": 1990, "month": 9})["ok"] is True


def test_year_and_month_mean_the_first_of_that_month() -> None:
    model = CalendarMonthInput.model_validate({"year": 1990, "month": 9})
    assert model.date == "1990-09-01" and model.zone == "+08:00"
    assert CalendarMonthInput.model_validate({"date": "2026-11-14", "year": 1990, "month": 9}).date == "2026-11-14"
