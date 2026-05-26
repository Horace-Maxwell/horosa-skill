"""Value-alignment regression for the decennials Python port.

Golden vectors are taken from 星阙's own
`Horosa-Web/astrostudyui/src/utils/__tests__/decennials.test.js` so the headless Python port stays
value-identical to the authoritative JavaScript algorithm (`utils/decennials.js`).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
