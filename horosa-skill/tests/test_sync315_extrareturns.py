"""上游 v3.15.0 同步 · 多重回归星体与回数（挂载设置 erBodies / erCount → buildExtraReturnsSnapshotText opts）。

上游：页面十一体都能取、按页面星体表顺序出、缺 = 土 / 木 / 月交三体；回数只认下拉档、缺 = 5；认不出的静默回缺省。
skill：同表同序同缺省，认不出报错。表（键 / 中文名 / 周期）与下拉档读上游源逐项对拍。
负向对照：_extrareturns_pick 不读 erBodies（恒三体）→ 星体用例红；不读 erCount → 回数用例红。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from skips import needs_upstream, upstream_path
from test_sync313_predictive import BIRTH, RecordingClient, _section, _service

from horosa_skill.service.runners.predictive import PredictiveRunners as P

SRC = "Horosa-Web/astrostudyui/src/components/astro/AstroExtraReturns.js"


@needs_upstream(SRC)
def test_body_table_and_count_options_are_the_upstream_ones() -> None:
    src = upstream_path(SRC).read_text(encoding="utf-8")
    body_block = src[src.index("const BODIES = ["): src.index("];", src.index("const BODIES = ["))]
    upstream = tuple(re.findall(r"key: '(\w+)', cn: '([^']+)', period: '([^']+)'", body_block))
    assert upstream == P._EXTRARETURNS_ALL_BODIES and len(upstream) == 11
    snap = re.search(r"const SNAPSHOT_BODIES = \[([^\]]*)\]", src).group(1)
    assert tuple(re.findall(r"'(\w+)'", snap)) == P._EXTRARETURNS_SNAPSHOT_BODIES
    counts = re.search(r"const COUNT_OPTIONS = \[([^\]]*)\]", src).group(1)
    assert tuple(int(x) for x in counts.split(",")) == P._EXTRARETURNS_COUNT_OPTIONS
    assert f"EXTRA_RETURN_SNAPSHOT_COUNT = {P._EXTRARETURNS_COUNT};" in src


def _run(tmp_path: Path, **extra):
    calls: list[dict] = []

    def returns(payload: dict) -> dict:
        calls.append(payload)
        return {"returns": [{"which": i + 1, "date": f"20{10 + i}-01-10", "time": "08:00:00", "passes": []}
                            for i in range(int(payload["count"]))], "natalLon": 10.0}

    env = _service(tmp_path, RecordingClient({"/astroextra/planetreturn": returns})).run_tool(
        "extrareturns", {**BIRTH, **extra}, save_result=False)
    return env, calls


def test_default_is_three_bodies_five_returns(tmp_path: Path) -> None:
    env, calls = _run(tmp_path)
    assert env.ok, env.error
    assert [(c["body"], c["count"]) for c in calls] == [("Saturn", 5), ("Jupiter", 5), ("Node", 5)]
    assert "erBodies" not in calls[0] and "erCount" not in calls[0]


def test_picked_bodies_come_out_in_page_order_with_the_count(tmp_path: Path) -> None:
    env, calls = _run(tmp_path, erBodies=["Pluto", "Sun", "Saturn"], erCount=2)
    assert env.ok, env.error
    assert [(c["body"], c["count"]) for c in calls] == [("Saturn", 2), ("Sun", 2), ("Pluto", 2)]
    body = _section(env.data["snapshot_text"], "多重回归").splitlines()
    assert [line.split("（")[0] for line in body] == ["土星返照", "太阳返照", "冥王星返照"]
    assert body[1] == "太阳返照（≈1 年）：第1回 2010-01-10，第2回 2011-01-10；时刻：第1回 08:00:00，第2回 08:00:00；本命黄经 10.0°"


@pytest.mark.parametrize("extra", [{"erBodies": ["Chiron"]}, {"erBodies": ["Saturn", "x"]}, {"erCount": 7}, {"erCount": "abc"},
                                   {"erCount": True}])
def test_unknown_bodies_or_counts_are_refused_before_any_call(tmp_path: Path, extra) -> None:
    env, calls = _run(tmp_path, **extra)
    assert env.ok is False and env.error.code == "tool.predictive_invalid_option" and calls == []
