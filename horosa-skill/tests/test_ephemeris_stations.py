"""星历「留」的顺逆方向——本仓声明式偏离（v0.40.0，engine/ephemeris_stations.py）的纯函数守卫。

上游 calc_stations 用留点那一刻（速度≈0）的速度正负定方向，是浮点噪声；这里用合成的逐日速度网格钉住纠正规则：
留后第一行定方向、速度恰为 0 的行不算、逐日覆盖之外按同一行星的交替续推、无数据保留上游标签并上报。
真实数据（两个场景 41 个留、独立的前后半天速度真值）由 tests/test_sync311_newtools.py 的离线与 live 金标守着。
"""

from __future__ import annotations

from horosa_skill.engine.ephemeris_stations import correct_station_directions


def _row(jd: float, **speeds: float) -> dict:
    return {"jd": jd, "positions": {body: {"speed": v} for body, v in speeds.items()}}


def _upstream_station(jd: float, body: str, hit_speed: float) -> dict:
    """上游 calc_stations 的形状与标签规则（留点时刻速度正负）。"""
    return {"jd": jd, "body": body, "speed": hit_speed, "direction": "Direct" if hit_speed >= 0 else "Retrograde"}


# 2026 年一季度的四个真实留（vendored v3.11.3 实测的留点时刻速度——噪声量级——与前后半天速度）。
_Q1_2026 = [
    ("Uranus", 2461075.94, -5.082e-09, -0.00043, 0.00044, "Direct"),  # 2026-02-04 转顺
    ("Mercury", 2461098.12, 3.505e-09, 0.08222, -0.08177, "Retrograde"),  # 2026-02-26 转逆
    ("Jupiter", 2461110.98, -2.835e-09, -0.00163, 0.00163, "Direct"),  # 2026-03-11 转顺
    ("Mercury", 2461120.65, 3.477e-09, -0.04988, 0.04898, "Direct"),  # 2026-03-21 转顺
]


def test_direction_comes_from_the_daily_speed_after_the_station() -> None:
    stations = [_upstream_station(jd, body, hit) for body, jd, hit, _, _, _ in _Q1_2026]
    rows = []
    for body, jd, _, before, after, _ in _Q1_2026:
        rows += [_row(jd - 0.4, **{body: before}), _row(jd + 0.6, **{body: after})]
    corrected, unresolved = correct_station_directions(stations, rows)
    assert [s["direction"] for s in corrected] == [truth for *_, truth in _Q1_2026]
    assert unresolved == []
    # 只有改了的留带 directionUpstream；没改的原样（同一个对象）
    assert [s.get("directionUpstream") for s in corrected] == ["Retrograde", "Direct", "Retrograde", None]
    assert corrected[3] is stations[3]
    # 负向对照：上游规则在同一批数据上错 3 个——测试若退回上游标签必红
    assert sum(s["direction"] != truth for s, (*_, truth) in zip(stations, _Q1_2026)) == 3


def test_zero_speed_rows_carry_no_direction_and_are_skipped() -> None:
    stations = [_upstream_station(10.3, "Mars", 1e-9)]
    rows = [_row(10.0, Mars=0.01), _row(11.0, Mars=0.0), _row(12.0, Mars=-0.02)]
    corrected, _ = correct_station_directions(stations, rows)
    assert corrected[0]["direction"] == "Retrograde"


def test_beyond_daily_coverage_directions_alternate_per_planet() -> None:
    # 逐日表只覆盖 day 0..9（上游 370 天上限的缩影）；之后的留按同一行星交替续推
    rows = [_row(float(d), Mercury=(0.5 if d < 5 else -0.4), Venus=0.9) for d in range(10)]
    stations = [
        _upstream_station(4.7, "Mercury", 1e-9),  # 覆盖内：day 5 速度为负 → 转逆
        _upstream_station(25.2, "Mercury", 1e-9),  # 覆盖外：上一个是转逆 → 转顺
        _upstream_station(48.9, "Mercury", 1e-9),  # 再翻 → 转逆
        _upstream_station(40.0, "Venus", -1e-9),  # 覆盖外且覆盖内无留：末行速度为正 → 这一留翻成转逆
    ]
    corrected, unresolved = correct_station_directions(stations, rows)
    assert [s["direction"] for s in corrected] == ["Retrograde", "Direct", "Retrograde", "Retrograde"]
    assert unresolved == []


def test_without_daily_speeds_upstream_labels_are_kept_and_reported() -> None:
    stations = [_upstream_station(1.5, "Saturn", 2e-9), "not-a-station"]
    for daily in (None, [], [{"jd": 1.0, "positions": {"Saturn": {"speed": None}}}]):
        corrected, unresolved = correct_station_directions(stations, daily)
        assert corrected == stations
        assert unresolved == stations
    assert correct_station_directions(None, []) == ([], [])
