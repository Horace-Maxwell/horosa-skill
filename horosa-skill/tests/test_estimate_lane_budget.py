"""scripts/estimate_lane_budget.py: one local junit run → per-lane projections, red before the tag instead of after a killed lane."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "estimate_lane_budget.py"
_spec = importlib.util.spec_from_file_location("estimate_lane_budget", _SCRIPT)
est = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("estimate_lane_budget", est)
_spec.loader.exec_module(est)

LIVE = est._live_module()


def _junit(tmp_path: Path, seconds: list[float]) -> Path:
    cases = "".join(f'<testcase classname="tests.t" name="c{i}" time="{s}"/>' for i, s in enumerate(seconds))
    path = tmp_path / "live.xml"
    path.write_text(f'<?xml version="1.0"?><testsuites><testsuite name="pytest">{cases}</testsuite></testsuites>', encoding="utf-8")
    return path


def test_the_factors_and_budgets_cover_the_same_lanes() -> None:
    assert set(LIVE.LANE_SLOWDOWN_VS_MAINTAINER_MAC) == set(est.lane_budgets(LIVE)) == {"darwin-arm64", "win32-x64", "win32-arm64"}


def test_junit_seconds_sums_every_case(tmp_path) -> None:
    assert est.junit_seconds(_junit(tmp_path, [1.5, 2.0, 0.25])) == (3.75, 3)


def test_the_suite_that_passed_the_v051_matrix_fits(tmp_path) -> None:
    # 1185 s locally (junit, same suite) ↔ the passing run 44098676839: 2076 / 4802 / 8182 s actual.
    rows, problems = est.project(1185.0, LIVE, est.matrix_job_minutes())
    projected = {row["lane"]: row["projected"] for row in rows}
    actual = {"darwin-arm64": 2076, "win32-x64": 4802, "win32-arm64": 8182}
    assert all(abs(projected[lane] - actual[lane]) / actual[lane] < 0.05 for lane in actual), projected
    assert problems == [], problems
    assert all(row["share"] <= LIVE.PYTEST_BUDGET_WARN_FRACTION for row in rows)


def test_the_untrimmed_v051_suite_is_flagged_on_every_lane() -> None:
    """1558 s = the local run with the 261 s polar sweep still in it."""
    _, problems = est.project(1558.0, LIVE, est.matrix_job_minutes())
    assert [p.split(":")[0] for p in problems] == ["darwin-arm64", "win32-x64", "win32-arm64"]


def test_the_old_budgets_would_have_been_flagged_before_the_tag() -> None:
    """Negative control: the v0.50.1 budgets (posix 1500 / nt 3600 / +1800, job 120 min) against the v0.51.0 suite."""
    old = SimpleNamespace(PYTEST_BUDGET_SECONDS={"nt": 3600, "posix": 1500}, EMULATED_PYTEST_EXTRA_SECONDS=1800,
                          PYTEST_BUDGET_WARN_FRACTION=LIVE.PYTEST_BUDGET_WARN_FRACTION,
                          LANE_SLOWDOWN_VS_MAINTAINER_MAC=LIVE.LANE_SLOWDOWN_VS_MAINTAINER_MAC)
    _, problems = est.project(1185.0, old, 120)
    assert len(problems) == 3 and all("raise it to" in p for p in problems)


def test_an_emulated_budget_that_outgrows_the_job_timeout_is_flagged() -> None:
    _, problems = est.project(100.0, LIVE, 120)
    want = (f"win32-arm64 budget {est.lane_budgets(LIVE)['win32-arm64']} s no longer fits runtime-matrix.yml's 120-minute job "
            "(needs ≥ 15 min for the other steps)")
    assert problems == [want]


def test_main_exit_code_follows_the_projection(tmp_path, capsys) -> None:
    assert est.main([str(_junit(tmp_path, [600.0, 400.0]))]) == 0
    assert "lane-budget: ok" in capsys.readouterr().out
    assert est.main([str(_junit(tmp_path, [1000.0, 1000.0]))]) == 1
    assert "[BUDGET] win32-x64" in capsys.readouterr().out
