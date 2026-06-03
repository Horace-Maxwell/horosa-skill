"""Offline golden + invariant tests for the pure-Python v2.5.0 推运 snapshot builders.

These builders were ported by hand from 星阙's frontend (persiandirected = pure 1°/年 arithmetic;
yearsystem129 = reads server-computed predictives; planetaryages = Ptolemy seven ages). Before this
file they were only exercised by `@requires_chart` live tests, so an arithmetic/formatting regression
would slip through CI when no chart service is up. Here we feed a FIXED `/chart` response fixture
(`fixtures/chart_1998_predictive.json`, captured once from the live service) and assert both the exact
golden snapshot text AND structural invariants that survive a deliberate golden regeneration.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from horosa_skill import service as S

_FIXTURES = Path(__file__).parent / "fixtures"


def _chart() -> dict:
    return json.loads((_FIXTURES / "chart_1998_predictive.json").read_text(encoding="utf-8"))


def _golden(name: str) -> str:
    return (_FIXTURES / f"golden_{name}.txt").read_text(encoding="utf-8")


# --- golden equality (regression guard) -------------------------------------------------

def test_persiandirected_matches_golden() -> None:
    assert S._build_persiandirected_snapshot_text(_chart()) == _golden("persiandirected")


def test_yearsystem129_matches_golden() -> None:
    assert S._build_yearsystem129_snapshot_text(_chart()) == _golden("yearsystem129")


def test_planetaryages_matches_golden() -> None:
    assert S._build_planetaryages_snapshot_text(_chart(), "2028-04-06") == _golden("planetaryages")


# --- structural invariants (catch logic errors even if golden is regenerated) -----------

def test_persiandirected_invariants() -> None:
    text = S._build_persiandirected_snapshot_text(_chart())
    assert text.startswith("[波斯向运（Persian Directed）]")
    rows = [ln for ln in text.splitlines() if ln.startswith("| ") and "°" in ln]
    assert 0 < len(rows) <= 120, "120-row cap (or empty) expected"
    # Exact per-row dates are owned by the golden test; here we check structural invariants that a
    # deliberate golden regeneration would NOT mask: ascending ages, valid aspects, dates tracking ages.
    ages: list[float] = []
    dates: list[datetime] = []
    birth = datetime(1998, 2, 20, 20, 48, 0)
    for row in rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        age, date_str, aspect = float(cells[0]), cells[1], cells[3]
        ages.append(age)
        dates.append(datetime.strptime(date_str, "%Y-%m-%d"))
        assert 0 < age <= 90, f"age {age} out of (0,90]"
        assert aspect in {"合相", "六合", "四分(刑)", "三合", "对分(冲)", "0°", "60°", "90°", "120°", "180°"}
        # rate sanity (1°/年): the row's date must be ~age years after birth (±1 week tolerates the
        # 2-dp age rounding); this still catches a wrong rate, wrong epoch, or wrong day-per-year constant.
        approx = birth + timedelta(days=age * 365.2421904)
        assert abs((dates[-1] - approx).days) <= 7, f"date {date_str} not ~{age}yr after birth ({approx:%Y-%m-%d})"
    # Sorted by the 2-dp-ROUNDED age (faithful to 星阙's `hits.sort((x,y)=>x.age-y.age)`); dates are NOT
    # strictly monotonic within a rounded-age group (same-rounded-age hits keep insertion order).
    assert ages == sorted(ages), "hits must be sorted ascending by (rounded) age"


def test_yearsystem129_invariants() -> None:
    text = S._build_yearsystem129_snapshot_text(_chart())
    assert text.startswith("[129年系统表格]")
    assert "129 年一轮" in text
    # every data row is | 主限 | 子限 | 日期 | with a non-empty 主限
    data_rows = [ln for ln in text.splitlines() if ln.startswith("| ") and "主限" not in ln and "---" not in ln]
    assert data_rows, "expected at least one 主限/子限 row"
    for row in data_rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        assert cells[0], "主限 column must be non-empty"


def test_planetaryages_invariants() -> None:
    text = S._build_planetaryages_snapshot_text(_chart(), "2028-04-06")
    assert text.startswith("[行星年龄（Ages of Man）]")
    # exactly the 7 Ptolemy bands, exactly one marked current (●) for a valid as_of
    band_rows = [ln for ln in text.splitlines() if re.match(r"\| .+岁 \|", ln)]
    assert len(band_rows) == 7, f"expected 7 age bands, got {len(band_rows)}"
    assert text.count("●") == 1, "exactly one current band should be marked"


def test_planetaryages_no_current_band_without_as_of() -> None:
    # with no as_of the current age is unknown → no band marked, no crash
    text = S._build_planetaryages_snapshot_text(_chart(), None)
    assert "●" not in text
    assert text.startswith("[行星年龄（Ages of Man）]")
