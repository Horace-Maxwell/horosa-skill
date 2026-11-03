"""星运 astroextra 族的目标日 / 区间日期走民用历口径（v0.47.0；v3.13.1 同步时 C1 查出的存量缺陷）。

`PredictiveRunners._astroextra_date`（progressions 的 targetDate、推运图族四法的 targetDate、星历 startDate / endDate）
此前是四位年正则 + `datetime()`：公元前 / 五位年的本命盘一给目标日就报「不是合法日期」，违反 civil_calendar 铁律
（AGENTS §4.2）；星历「结束日早于开始日」又是字符串比较，带号年比错（'-0400-…' < '-0500-…'）。上游页面把日期选择器
的串原样下发（AstroProgressions.js:72、AstroDirectedFigures.js:46、AstroEphemeris.js:43），skill 照收照发
dateStrSafe.formatSignedDate 同形串。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from test_sync311_newtools import _LiveFixtureClient, _payload, _sc, _service

from horosa_skill.errors import ToolValidationError
from horosa_skill.service.runners.predictive import PredictiveRunners

_date = PredictiveRunners._astroextra_date


@pytest.mark.parametrize(("raw", "expected"), [
    ("2026-11-03", "2026-11-03"),
    ("2026/1/5", "2026-01-05"),
    ("-0500-03-01", "-0500-03-01"),     # 公元前
    ("-44/3/15", "-0044-03-15"),
    ("12026-01-01", "12026-01-01"),      # 五位年
    ("1500-02-29", "1500-02-29"),        # 儒略历闰日（1582-10-15 前）
])
def test_signed_and_julian_dates_are_accepted(raw: str, expected: str) -> None:
    """负向对照：把正则换回 `(\\d{4})[-/]…` → 公元前两条、五位年一条、加下面星历区间一条共四条红（实跑过）。"""
    assert _date({"targetDate": raw}, "targetDate", code="tool.prog_invalid_option") == expected


@pytest.mark.parametrize("raw", ["1582-10-10", "0000-01-01", "2023-02-29", "1900-02-29", "2026-13-01", "next friday"])
def test_dates_that_do_not_exist_on_the_civil_calendar_are_refused(raw: str) -> None:
    with pytest.raises(ToolValidationError) as err:
        _date({"targetDate": raw}, "targetDate", code="tool.prog_invalid_option")
    assert err.value.code == "tool.prog_invalid_option"


def test_ephemeris_window_order_compares_dates_not_strings(tmp_path: Path) -> None:
    """'-0500-01-01' → '-0400-01-01' 是往后走 100 年；字符串比较会把它判成「结束日早于开始日」。
    负向对照：把比较换回 `end_date < start_date` → 本条红（实跑过）。"""
    sc = _sc("sample")
    client = _LiveFixtureClient(sc)
    result = _service(tmp_path, client).run_tool(
        "ephemeris", _payload(sc, startDate="-0500-01-01", endDate="-0400-01-01"), save_result=False)
    assert not (result.ok is False and result.error.code == "tool.ephemeris_invalid_window"), result.error
    body = client.bodies("/astroextra/ephemeris")[0]
    assert (body["startDate"], body["endDate"]) == ("-0500-01-01", "-0400-01-01")
    backwards = _service(tmp_path, _LiveFixtureClient(sc)).run_tool(
        "ephemeris", _payload(sc, startDate="-0400-01-01", endDate="-0500-01-01"), save_result=False)
    assert backwards.ok is False and backwards.error.code == "tool.ephemeris_invalid_window"
