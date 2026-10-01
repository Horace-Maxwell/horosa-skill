"""星历「留」的顺逆方向——本仓声明式偏离（v0.40.0）。

上游 `astroextra.calc_stations` 用求根得到的留点**那一刻**的速度正负定方向
（`'Direct' if hit_speed >= 0 else 'Retrograde'`）。留点上速度本来就≈0：1 天区间二分 24 次后 |v| 只有 ~1e-9 °/日，
正负是浮点噪声，随 Swiss Ephemeris 的编译器（mac clang / Windows MSVC）与采样网格起点翻转——上游自己的金标
2026 年一季度 4 个留错 2 个（天王星、木星），Windows 上错的是另外 2 个（两次水星）。

纠正只用上游同一份响应，不多发请求：`dailyPositions` 与 `calc_stations` 走同一张网格（本地零点起、1 天步长、
同一个 `swe_lon`），留点之后第一行的速度正负就是留后的真实方向（转顺 = 正、转逆 = 负，离留点 ≤ 1 天，|v| 远大于噪声）。
逐日表只列前 370 天、留表最长 732 天：覆盖之外按「同一行星的留顺逆严格交替」续推，起点是该行星上一个留的方向，
或覆盖内最后一行的速度正负（那之后第一个留把它翻过来）。两样都没有才保留上游标签，交给调用方发 warning。
改过的留带 `directionUpstream`（上游原标签），可审计。
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from typing import Any

DIRECT = "Direct"
RETROGRADE = "Retrograde"


def _flip(direction: str) -> str:
    return RETROGRADE if direction == DIRECT else DIRECT


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _speed_series(daily_rows: Any) -> dict[str, tuple[list[float], list[float]]]:
    """body → (jd 升序, 同序速度)；速度恰为 0 的行没有方向信息，不收。"""
    rows: dict[str, list[tuple[float, float]]] = {}
    for row in daily_rows if isinstance(daily_rows, list) else []:
        if not isinstance(row, dict) or not _is_number(row.get("jd")) or not isinstance(row.get("positions"), dict):
            continue
        for body, position in row["positions"].items():
            speed = position.get("speed") if isinstance(position, dict) else None
            if _is_number(speed) and speed != 0:
                rows.setdefault(body, []).append((float(row["jd"]), float(speed)))
    series: dict[str, tuple[list[float], list[float]]] = {}
    for body, samples in rows.items():
        samples.sort()
        series[body] = ([jd for jd, _ in samples], [speed for _, speed in samples])
    return series


def correct_station_directions(stations: Any, daily_rows: Any) -> tuple[list[Any], list[Any]]:
    """(方向按逐日速度复核后的留表, 判不出方向的留)——两者都保持原表顺序。"""
    if not isinstance(stations, list):
        return [], []
    series = _speed_series(daily_rows)
    corrected: list[Any] = list(stations)
    unresolved: set[int] = set()
    by_body: dict[str, list[int]] = {}
    for index, station in enumerate(stations):
        if isinstance(station, dict) and _is_number(station.get("jd")) and isinstance(station.get("body"), str):
            by_body.setdefault(station["body"], []).append(index)
        else:
            unresolved.add(index)
    for body, indexes in by_body.items():
        indexes.sort(key=lambda i: stations[i]["jd"])
        jds, speeds = series.get(body, ([], []))
        state: str | None = None  # 上一个留之后的方向
        for i in indexes:
            station = stations[i]
            jd = float(station["jd"])
            after = bisect_right(jds, jd)
            before = bisect_left(jds, jd) - 1
            if after < len(jds):
                direction: str | None = DIRECT if speeds[after] > 0 else RETROGRADE
            elif state is not None:
                direction = _flip(state)
            elif before >= 0:
                direction = _flip(DIRECT if speeds[before] > 0 else RETROGRADE)
            else:
                direction = None
            state = direction
            if direction is None:
                unresolved.add(i)
            elif station.get("direction") != direction:
                corrected[i] = {**station, "direction": direction, "directionUpstream": station.get("direction")}
    return corrected, [stations[i] for i in sorted(unresolved)]
