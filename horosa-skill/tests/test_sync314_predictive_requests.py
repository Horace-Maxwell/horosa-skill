"""上游 v3.14.0 既有星运技法的口径变化里，落在 skill 这一侧要守的三件事（各自的权威写在用例里）：

1. Bija 年拆两档：`bija` 改取《苏利耶历数书》年长 365.258756 日（此前 366.256399），旧值留作 `bijaClassic`。
   129 年系统 / Balbillus / 时主轮转 / 波斯向运共用 utils/timeLordYears.js 这张表（vendored verbatim）。
2. 「容许度设置」随盘走：上游给主限法 / 主限法盘 / 各返照与小限的请求补上 orbs / orbScale 与古典口径键（classicalChartGlobals.js
   chartOrbOverrides*；AstroPrimaryDirectionChart.js / AstroDirectMain.js / aiAnalysisContext/{primaryDirection,regenPredictive}.js）。
   skill 这几个工具是「载荷原样下发」，本就带着——这里钉住，防止以后有人给请求体加白名单时把它们滤掉。
3. 太阳返照取「所选那一年」的返照：后端种子退两天（perpredict.SR_SEED_BACK_DAYS），此前选 2022 得 2023。
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from node_esm import run_node_esm
from test_sync313_predictive import BIRTH, CHART, RecordingClient, RecordingJs, _chart1998, _js, _service

from horosa_skill.service.runners.predictive import PredictiveRunners
from horosa_skill.service.text import predictive as T

CORE_JS = Path(__file__).resolve().parents[1] / "horosa-core-js"
requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="[host] node not installed")
MINOR = {"Saturn": 30, "Jupiter": 12, "Mars": 15, "Sun": 19, "Venus": 8, "Mercury": 20, "Moon": 25}   # 七星小年，合 129
BIJA, BIJA_CLASSIC = 365.258756, 366.256399   # 1,577,917,828 民用日 ÷ 4,320,000 年；恒星年里的恒星日数


@requires_node
def test_bija_year_has_two_tiers_in_the_shared_year_table(tmp_path: Path) -> None:
    """值级（按定义手算，上游 utils/__tests__/timeLordOptions.test.js 同式）：129 年系统主限天数 = 小年 × 年长。
    bija 现在是 365.258756 日 / 年，旧的 366.256399 在 bijaClassic；1,577,917,828 ÷ 4,320,000 = 365.25875648…（《苏利耶历数书》一大劫）。
    负向对照（实跑）：vendored timeLordYears.js 的 bija 天数改回 366.256399 → 红。"""
    assert abs(1_577_917_828 / 4_320_000 - BIJA) < 1e-6
    rows = json.loads(run_node_esm(
        "import fs from 'node:fs';"
        "import { computeYearSystem129 } from './src/vendor/astroextra/yearSystem129.js';"
        "import { buildBalbillusContext, buildBalbillusRoots } from './src/vendor/astroextra/balbillus.js';"
        "import { TIME_LORD_YEAR_TYPES as Y } from './src/vendor/utils/timeLordYears.js';"
        "const chart = JSON.parse(fs.readFileSync('../tests/fixtures/chart_1998_predictive.json', 'utf8'));"
        "const out = { days: { bija: Y.bija.days, bijaClassic: Y.bijaClassic.days }, labels: { bija: Y.bija.label, bijaClassic: Y.bijaClassic.label }, ys: {}, bal: {} };"
        "for (const yt of ['solar', 'bija', 'bijaClassic']) {"
        " out.ys[yt] = computeYearSystem129(chart, { yearType: yt }).rows.slice(0, 7).map((r) => [r.mainDirect, r.durDays, r.startDays]);"
        " const ctx = buildBalbillusContext(chart, { yearType: yt, maxAge: 200 }); out.bal[yt] = buildBalbillusRoots(ctx).slice(0, 3).map((r) => [r.planet, r.durDays, r.durYears]); }"
        "console.log(JSON.stringify(out));",
        cwd=CORE_JS, timeout=60,
    ))
    assert rows["days"] == {"bija": BIJA, "bijaClassic": BIJA_CLASSIC}
    assert rows["labels"] == {"bija": "Bija 年（365.2588 日）", "bijaClassic": "Bija 年 · 经典（366.2564 日）"}
    for year_type, days in (("bija", BIJA), ("bijaClassic", BIJA_CLASSIC), ("solar", 365.242199)):
        total = 0.0
        for planet, dur_days, start_days in rows["ys"][year_type]:
            assert abs(dur_days - MINOR[planet] * days) < 1e-6 and abs(start_days - total) < 1e-6, (year_type, planet)
            total += dur_days
        for _planet, dur_days, dur_years in rows["bal"][year_type]:   # Balbillus：主限天数 = 年数 × 年长
            assert abs(dur_days - dur_years * days) < 1e-6, year_type
    assert rows["ys"]["bija"][0][0] == "Sun" and abs(rows["ys"]["bija"][0][1] - 19 * BIJA) < 1e-6


@requires_node
def test_yearsystem129_and_balbillus_accept_both_bija_tiers(tmp_path: Path) -> None:
    """1998-02-20 20:48 生人、太阳主限 19 年：木星主限起于出生后 19 × 年长 天——bija 6939.92 天 = 2017-02-20，
    bijaClassic 6958.87 天 = 2017-03-11（v3.14.0 之前 `bija` 给的就是 2017-03-11：同一个键、结果变了）。日期手算，不取自输出。"""
    birth = datetime(1998, 2, 20, 20, 48)
    want = {"bija": (birth + timedelta(days=19 * BIJA)).strftime("%Y-%m-%d"), "bijaClassic": (birth + timedelta(days=19 * BIJA_CLASSIC)).strftime("%Y-%m-%d")}
    assert want == {"bija": "2017-02-20", "bijaClassic": "2017-03-11"}
    labels = {"bija": "年制=Bija 年（365.2588 日）", "bijaClassic": "年制=Bija 年 · 经典（366.2564 日）"}
    for year_type in ("bija", "bijaClassic"):
        js = RecordingJs(_js(tmp_path))
        result = _service(tmp_path, RecordingClient({CHART: _chart1998()}), js).run_tool("yearsystem129", {**BIRTH, "ys129YearType": year_type}, save_result=False)
        assert result.ok is True, result.error
        text = result.data["snapshot_text"]
        assert labels[year_type] in text and f"| 木(12.00年,起 {want[year_type]}) |" in text, (year_type, text[:400])
        bal = _service(tmp_path, RecordingClient({CHART: _chart1998()}), RecordingJs(_js(tmp_path))).run_tool("balbillus", {**BIRTH, "yearType": year_type}, save_result=False)
        assert bal.ok is True, bal.error
    assert "bijaClassic" in PredictiveRunners._PROGEXTRA_OPTION_DOMAINS["yearsystem129"]["ys129YearType"]
    assert "bijaClassic" in PredictiveRunners._PROGEXTRA_OPTION_DOMAINS["balbillus"]["yearType"]
    assert T._TIME_LORD_YEAR_TYPES[-2:] == ("bija", "bijaClassic")
    bad = _service(tmp_path, RecordingClient({CHART: _chart1998()}), RecordingJs()).run_tool("yearsystem129", {**BIRTH, "ys129YearType": "bijaclassic2"}, save_result=False)
    assert bad.ok is False and bad.error.code == "tool.predictive_invalid_option"


@pytest.mark.parametrize(
    ("tool", "extra", "endpoint"),
    [
        ("pd", {}, "/predict/pd"),
        ("pdchart", {"datetime": "2026-01-01 12:00:00"}, "/predict/pdchart"),
        ("solarreturn", {"datetime": "2026-06-03 05:30"}, "/predict/solarreturn"),
        ("lunarreturn", {"datetime": "2026-06-03 05:30"}, "/predict/lunarreturn"),
        ("givenyear", {"datetime": "2026-06-03 05:30"}, "/predict/givenyear"),
        ("profection", {"datetime": "2026-06-03 05:30"}, "/predict/profection"),
        ("solararc", {"datetime": "2026-06-03 05:30"}, "/predict/solararc"),
    ],
)
def test_chart_orbs_and_classical_settings_ride_along_with_period_requests(tmp_path: Path, tool: str, extra: dict[str, Any], endpoint: str) -> None:
    """上游 v3.14.0：推运请求带上随盘容许度（orbs / orbScale）与古典口径——不带的话外圈推运盘按出厂口径算，真交点 / 界系 / 容许度与
    内圈本命盘对不上。skill 的这些工具把载荷原样下发；钉住这一点。
    负向对照（实跑）：在 service/remote.py 的 _call_remote 入口把 orbs / orbScale 从载荷里弹掉 → 七条全红。"""
    client = RecordingClient()
    knobs = {"orbScale": 1.5, "orbs": {"Sun": 9}, "westNodeType": "true", "termsVariant": 1}
    result = _service(tmp_path, client).run_tool(tool, {**BIRTH, **extra, **knobs}, save_result=False)
    assert result.ok is True, result.error
    sent = client.payloads(endpoint)
    assert sent, [e for e, _p in client.calls]
    assert {k: sent[-1].get(k) for k in knobs} == knobs


# ── live ───────────────────────────────────────────────────────────────────────────────────────────

from test_local_js_tools import make_service, requires_chart, requires_current_runtime_contract  # noqa: E402

# 上游 astropy/tests/test_solar_return_seed_year.py 的盘：1990-06-15 12:00 +08:00 上海，此前选 2020–2027 全部得下一年。
_SR_BIRTH = {"date": "1990-06-15", "time": "12:00:00", "zone": "+08:00", "lat": "31n14", "lon": "121e28", "hsys": 0, "zodiacal": 0,
             "agent_confirmed_settings": True}


@requires_current_runtime_contract
@requires_chart
@pytest.mark.parametrize("year", [2020, 2022, 2025, 2027])
def test_live_solar_return_lands_in_the_selected_year(tmp_path: Path, year: int) -> None:
    """太阳返照：给年份 = 那一年的生日时刻（skill 的 returnPickerSeed 同式）→ 返照必须落在那一年（太阳回到本命黄经每年只一次、
    在生日前后一天内）。v3.14.0 之前这张盘会得到下一年的返照。"""
    result = make_service(tmp_path).run_tool("solarreturn", {**_SR_BIRTH, "datetime": str(year)}, save_result=False)
    assert result.ok is True, result.error
    stamp = f"{result.data.get('date') or (result.data.get('raw') or {}).get('date') or ''}"
    assert stamp.replace("/", "-").startswith(f"{year}-06-1"), (year, stamp, list(result.data)[:12])
    assert f"{year}" in result.data["snapshot_text"]
    snap = result.data["export_snapshot"]
    assert snap["missing_selected_sections"] == [] and snap["unknown_detected_sections"] == []


@requires_current_runtime_contract
@requires_chart
def test_live_yearsystem129_bija_tiers(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    birth = {"date": "1998-02-20", "time": "20:48:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "agent_confirmed_settings": True}
    texts = {yt: service.run_tool("yearsystem129", {**birth, "ys129YearType": yt}, save_result=False).data["snapshot_text"] for yt in ("bija", "bijaClassic")}
    assert "年制=Bija 年（365.2588 日）" in texts["bija"] and "| 木(12.00年,起 2017-02-20) |" in texts["bija"]
    assert "年制=Bija 年 · 经典（366.2564 日）" in texts["bijaClassic"] and "| 木(12.00年,起 2017-03-11) |" in texts["bijaClassic"]
