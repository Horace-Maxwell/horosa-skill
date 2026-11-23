"""上游 v3.15.0 同步 · 量化盘并列定序（utils/stableOrder.js tieSort / TIE_EPS）与边界判据。

上游把「数学上相等、浮点末位各差各的」的量统一处理：南北交点成对的相位、A+B−C=D 与 A+B−D=C、正对两点的两个中点、恰在宫头上的点。
Python 移植（service/text/western.py `_tie_sort` / `_dial_*`）与上游 uranianDial.js 同输入逐项对拍——上游函数经报告盘图 bundle 的
app-text 通道跑（uranian_dial），不另抄。点集特意让南北交点恰好对冲（十进制 123.4567° / 303.4567°，二进制只差末位）。
负向对照：`_tie_sort` 退回普通 sorted（并列按值不按生成先后）→ 列表顺序用例红；planetHouse 去掉 TIE_EPS → 宫头用例红。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.engine.js_client import HorosaJsEngineClient
from horosa_skill.service.text import western as W

PKG_ROOT = Path(__file__).resolve().parents[1]
PERSONAL = sorted(W._DIAL_PERSONAL)
URANIAN = sorted(W._DIAL_URANIAN)
POINTS = [   # 十进制小数（二进制不精确）+ 南北交点在十进制上恰差 180°：成对的量只差浮点末位，普通排序会按末位定序
    {"id": "Sun", "lon": 55.3}, {"id": "Moon", "lon": 145.3}, {"id": "Mercury", "lon": 33.1}, {"id": "Venus", "lon": 77.7},
    {"id": "Mars", "lon": 235.3}, {"id": "Jupiter", "lon": 100.1}, {"id": "Saturn", "lon": 280.1},
    {"id": "North Node", "lon": 123.4567}, {"id": "South Node", "lon": 303.4567}, {"id": "Asc", "lon": 325.3}, {"id": "MC", "lon": 235.3},
    {"id": "Cupido", "lon": 145.3}, {"id": "Hades", "lon": 33.1}, {"id": "AriesPoint", "lon": 0.0},
]


def _upstream(tmp_path, *calls):
    client = HorosaJsEngineClient(Settings(server_root="http://127.0.0.1:9", runtime_root=tmp_path / "rt", db_path=tmp_path / "m.db",
                                           output_dir=tmp_path / "o"))
    client._candidate_engine_roots = lambda: [PKG_ROOT / "horosa-core-js"]  # type: ignore[method-assign]
    out = client.run_app_texts([{"name": "uranian_dial", "args": {"fn": fn, "args": list(args)}} for fn, *args in calls])
    if out is None:
        pytest.skip("[host] node / app-charts bundle unavailable")
    assert all(r["ok"] for r in out), out
    return [r["value"] for r in out]


def test_midpoint_of_exactly_opposite_points_and_house_boundaries(tmp_path) -> None:
    pairs = [(10.25, 190.25), (190.25, 10.25), (350.0, 170.0), (100.0, 130.0), (300.0, 10.0)]
    cusps = [0.0, 30.0, 60.0, 90.0, 120.0, 150.0, 180.0, 210.0, 240.0, 270.0, 300.0, 330.0]
    lons = [30.0, 60.0 - 1e-12, 30.0 - 1e-13, 359.9999999999999, 0.0, 15.0, 330.0]
    up = _upstream(tmp_path, *[("midpoint", a, b) for a, b in pairs], *[("planetHouse", lon, cusps) for lon in lons])
    assert up[: len(pairs)] == [W._dial_mid(a, b) for a, b in pairs]
    assert up[len(pairs):] == [W._dial_planet_house(lon, cusps) for lon in lons]
    assert W._dial_mid(10.25, 190.25) == W._dial_mid(190.25, 10.25) == 100.25   # 两个中点一样近 → 取黄经小的


def test_lists_keep_generation_order_for_ties(tmp_path) -> None:
    opts = {"personal": PERSONAL, "uranian": URANIAN}
    mpl, sp, pics = _upstream(tmp_path, ("midpointList", POINTS, 90, opts), ("spiegelContacts", POINTS, 90, 1, opts),
                              ("planetaryPictures", POINTS, 90, 1, {**opts, "limit": 40}))
    assert [(p["a"], p["b"]) for p in mpl] == [(p["a"], p["b"]) for p in W._dial_midpoint_list(POINTS)]
    assert [(p["a"], p["b"]) for p in sp] == [(p["a"], p["b"]) for p in W._dial_spiegel(POINTS)]
    assert [(p["a"], p["b"], p["c"], p["d"]) for p in pics] == [(p["a"], p["b"], p["c"], p["d"]) for p in W._dial_planetary_pictures(POINTS)]


def test_tie_sort_semantics() -> None:
    rows = [{"k": 1.0 + 1e-12, "n": "a"}, {"k": 1.0, "n": "b"}, {"k": 0.5, "n": "c"}, {"k": 1.0 - 1e-12, "n": "d"}]
    assert [r["n"] for r in W._tie_sort(rows, lambda r: r["k"])] == ["c", "a", "b", "d"]   # 三个 ≈1.0 并列，保持原先后
    assert [r["n"] for r in sorted(rows, key=lambda r: r["k"])] == ["c", "d", "b", "a"]    # 普通排序按末位
