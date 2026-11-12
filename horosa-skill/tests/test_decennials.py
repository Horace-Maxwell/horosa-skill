"""Value-alignment regression for the decennials Python port.

Golden vectors are taken from 星阙's own
`Horosa-Web/astrostudyui/src/utils/__tests__/decennials.test.js` so the headless Python port stays
value-identical to the authoritative JavaScript algorithm (`utils/decennials.js`).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from horosa_skill.engine.decennials import build_decennial_timeline, DECENNIAL_TRADITIONAL_PLANETS


def _golden_chart() -> dict:
    # Mirrors decennials.test.js buildChart([Sun, Mercury, Saturn, Venus, Mars, Jupiter, Moon]):
    # zodiacal longitudes 10,20,...,70 by that order; objects listed in DECENNIAL_TRADITIONAL_PLANETS.
    zodiacal_order = ["Sun", "Mercury", "Saturn", "Venus", "Mars", "Jupiter", "Moon"]
    lons = {planet: 10 + idx * 10 for idx, planet in enumerate(zodiacal_order)}
    return {
        "params": {"birth": "1984-01-23 00:00:00", "zone": "+00:00"},
        "chart": {
            "isDiurnal": True,
            "objects": [{"id": planet, "lon": lons[planet]} for planet in DECENNIAL_TRADITIONAL_PLANETS],
        },
    }


def test_decennials_traditional_matches_xingque_golden_vector() -> None:
    timeline = build_decennial_timeline(
        _golden_chart(),
        {"startMode": "sect_light", "orderType": "zodiacal", "dayMethod": "valens"},
    )
    node = timeline["list"][0]
    assert timeline["resolvedStartPlanet"] == "Sun"
    assert node["planet"] == "Sun"
    assert node["date"] == "1984-01-23 - 1994-08-28"
    assert node["nominal"] == "0个月 - 10年9个月"
    assert [item["planet"] for item in node["sublevel"]] == [
        "Sun", "Mercury", "Saturn", "Venus", "Mars", "Jupiter", "Moon",
    ]
    assert node["sublevel"][0]["nominal"] == "0个月 - 1年7个月"


def test_decennials_actual_calendar_stretches_to_tropical_year() -> None:
    timeline = build_decennial_timeline(
        _golden_chart(),
        {"startMode": "sect_light", "orderType": "zodiacal", "dayMethod": "valens", "calendarType": "calendar_365_25"},
    )
    # 星阙 test: actual-mode L1 end == birth + 3870 * 1461 minutes (365.25/360 stretch).
    birth = datetime(1984, 1, 23, tzinfo=timezone.utc)
    expected_end = (birth + timedelta(minutes=3870 * 1461)).strftime("%Y-%m-%d")
    assert timeline["list"][0]["date"] == f"1984-01-23 - {expected_end}"


def test_decennials_hephaistio_day_method_builds_full_order() -> None:
    timeline = build_decennial_timeline(
        _golden_chart(),
        {"startMode": "sect_light", "orderType": "zodiacal", "dayMethod": "hephaistio"},
    )
    assert timeline["list"][0]["planet"] == "Sun"
    assert len(timeline["list"][0]["sublevel"]) == 7


# ───────────── [十年大运设置] 行星名照上游（v0.50.0 深审余项）─────────────
# 上游 utils/decennials.js：得时光体括注短名（日 / 月）、起运主星 / 实际起运 / [基于X起运] / 逐期行用长名（太阳 / 木星）；
# AI 输出模式印选项标签；「名义」区间只在 360 天口径附；宫制印名称；真太阳时只在盘上有时印。此前一律印英文 id 与内部值。
# 负向对照（实跑过）：start_label / node_line 改回印 id → 本用例红。

@pytest.mark.parametrize("start_mode, calendar, start_line", [
    ("sect_light", "calendar_360", "起运主星：得时光体（日）"),
    ("Jupiter", "calendar_365_25", "起运主星：木星"),
])
def test_decennial_snapshot_names_planets_like_upstream(start_mode: str, calendar: str, start_line: str) -> None:
    from horosa_skill.service.text.predictive import _build_decennials_snapshot_text

    response = {
        "chart": {"isDiurnal": True, "nongli": {}, "zodiacal": "Tropical"},
        "params": {"birth": "2028-04-06 09:33:00", "lon": "121e28", "lat": "31n13", "zone": "+08:00", "hsys": 1},
        "timeline": {"resolvedStartPlanet": "Sun", "list": [{"planet": "Jupiter", "date": "2028-04-06 - 2038-11-10", "nominal": "0个月 - 10年9个月"}]},
    }
    text = _build_decennials_snapshot_text(response, {"startMode": start_mode, "calendarType": calendar}, {"aiMode": "l1_all"})
    assert start_line in text
    assert "实际起运：太阳" in text and "[基于太阳起运]" in text
    assert "AI输出模式：输出所有L1（年主星+时间）" in text and "宫制：Alcabitus" in text
    assert "L1-1：木星-2028-04-06 - 2038-11-10" in text
    assert ("（名义：" in text) == (calendar == "calendar_360")
    assert "真太阳时" not in text and "Sun" not in text and "Jupiter" not in text
