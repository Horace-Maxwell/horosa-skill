"""v0.36.0 C6 — Python port of upstream `utils/wholeSignRulers.js` (single source for 宫主/宫神星 derivation).

Fixture `tests/fixtures/astro_v2_baseline_chartobj.json` = `chartObj` of upstream
`astrostudyui/src/utils/__tests__/fixtures/astroV2Baseline.json` (Horosa-Public @ 0604fa41, aiExport v56);
the expectations below are the upstream jest assertions (`wholeSignRulers.test.js`), so the port is pinned to
the same truth the desktop app is tested against. The `ruleHouses` round-trip is the upstream "整宫制宫主表 ↔
后端 nR 宫主标记逐宫对拍" test.
"""
from __future__ import annotations

import json
from pathlib import Path

from horosa_skill.astro_rulers import (
    HOUSE_SYSTEM_RULERS_HEADERS,
    WHOLE_SIGN_RULERS_HEADERS,
    build_house_ruler_lines,
    build_house_system_ruler_rows,
    build_whole_sign_ruler_rows,
    resolve_asc_sign,
    ruler_of_sign,
    sign_of_lon,
    whole_sign_house_of,
)
from horosa_skill.service import _astro_msg

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "astro_v2_baseline_chartobj.json"


def _chart_obj() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_primitives_match_upstream_tables() -> None:
    assert ruler_of_sign("Aries") == "Mars" and ruler_of_sign("Cancer") == "Moon" and ruler_of_sign("Pisces") == "Jupiter"
    assert ruler_of_sign("Nope") is None
    assert sign_of_lon(0) == "Aries" and sign_of_lon(359.9) == "Pisces" and sign_of_lon(-30) == "Pisces" and sign_of_lon("x") is None
    assert whole_sign_house_of("Scorpio", "Cancer") == 5 and whole_sign_house_of("Cancer", "Cancer") == 1
    assert whole_sign_house_of("Nope", "Cancer") is None


def test_whole_sign_rows_match_upstream_jest_baseline() -> None:
    chart_obj = _chart_obj()
    assert resolve_asc_sign(chart_obj) == "Cancer"
    ws = build_whole_sign_ruler_rows(chart_obj)
    assert [r["house"] for r in ws] == list(range(1, 13))
    # 上游 jest：整宫 1 宫巨蟹→月落第五宫天蝎；5 宫天蝎→火星整宫落第九宫双鱼
    assert {k: ws[0][k] for k in ("house", "sign", "ruler", "rulerFound", "rulerHouseNum", "rulerHouseId", "rulerSign")} == {
        "house": 1, "sign": "Cancer", "ruler": "Moon", "rulerFound": True, "rulerHouseNum": 5, "rulerHouseId": "House5", "rulerSign": "Scorpio"
    }
    assert {k: ws[4][k] for k in ("house", "sign", "ruler", "rulerHouseNum", "rulerSign")} == {
        "house": 5, "sign": "Scorpio", "ruler": "Mars", "rulerHouseNum": 9, "rulerSign": "Pisces"
    }


def test_house_system_rows_differ_from_whole_sign_by_construction() -> None:
    chart_obj = _chart_obj()
    ws = build_whole_sign_ruler_rows(chart_obj)
    hs = build_house_system_ruler_rows(chart_obj)
    # 上游 jest：分宫表 5 宫火星缺分宫落宫（rulerHouseNum null）；两表 宫/座/主 三列相同，落宫列不同
    assert {k: hs[4][k] for k in ("house", "sign", "ruler", "rulerFound", "rulerHouseNum", "rulerHouseId", "rulerSign")} == {
        "house": 5, "sign": "Scorpio", "ruler": "Mars", "rulerFound": True, "rulerHouseNum": None, "rulerHouseId": None, "rulerSign": "Pisces"
    }
    assert [(r["house"], r["sign"], r["ruler"]) for r in hs] == [(r["house"], r["sign"], r["ruler"]) for r in ws]
    assert [r["rulerHouseNum"] for r in hs] != [r["rulerHouseNum"] for r in ws]


def test_whole_sign_rows_round_trip_backend_rule_houses() -> None:
    """上游对拍：后端 perchart 的 ruleHouses（nR 宫主标记）== 整宫宫主表里该星所主的宫号集合。"""
    chart_obj = _chart_obj()
    ws = build_whole_sign_ruler_rows(chart_obj)
    with_rules = [o for o in chart_obj["chart"]["objects"] if isinstance(o.get("ruleHouses"), list)]
    assert with_rules
    for obj in with_rules:
        expected = [r["house"] for r in ws if r["ruler"] == obj["id"]]
        nums = sorted(int(str(h).replace("House", "")) for h in obj["ruleHouses"])
        assert nums == sorted(expected), obj["id"]


def test_house_ruler_lines_render_the_v56_sub_block() -> None:
    lines = build_house_ruler_lines(_chart_obj(), _astro_msg)
    assert lines[0] == "◆ 宫神星(houseRows)"
    assert lines[1] == "| 宫 | 宫头座 | 宫主 | 宫主落宫 | 宫主落座 |"
    assert lines[2] == "| --- | --- | --- | --- | --- |"
    assert lines[3].startswith("| 1宫 | 巨蟹 | 月亮 | ") and "天蝎" in lines[3]
    assert len(lines) == 3 + 12
    assert WHOLE_SIGN_RULERS_HEADERS[3] == "宫主落宫(整宫)" and HOUSE_SYSTEM_RULERS_HEADERS[3] == "宫主落宫"
    assert build_house_ruler_lines({"chart": {"houses": []}}, _astro_msg) == []
