#!/usr/bin/env python
"""Project each release-matrix lane's live-pytest time from one local run, before the tag — not after a killed lane.

Why (v0.51.0): the v3.14.0 sync doubled the live suite; the draft matrix was killed on all three lanes (darwin 74% of 1500 s,
windows-latest 80% of 3600, windows-11-arm 78% of 5400), and each round trip costs ~3 h. A local `--junitxml` run times every
test; multiplying by each lane's measured slowdown (verify_runtime_live.LANE_SLOWDOWN_VS_MAINTAINER_MAC) predicted the next
run within ~10%.

    HOROSA_CHART_SERVER_ROOT=http://127.0.0.1:8877 HOROSA_SERVER_ROOT=http://127.0.0.1:9977 \\
      uv run pytest -q -p no:cacheprovider --junitxml=/tmp/live.xml      # vendored instance up (start_vendored_instance.sh)
    uv run python scripts/estimate_lane_budget.py /tmp/live.xml

Exit 1 when any lane would exceed PYTEST_BUDGET_WARN_FRACTION of its budget (the share at which the lane itself starts
printing near-budget annotations) or when the emulated lane's budget no longer fits runtime-matrix.yml's job timeout.
The factors are relative to the maintainer's Apple-Silicon Mac; on another machine, recalibrate them first.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS.parents[1]
MATRIX_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "runtime-matrix.yml"
OTHER_STEPS_MINUTES = 15   # same floor tests/test_verify_runtime_live.py holds the job timeout to


def _live_module():
    spec = importlib.util.spec_from_file_location("verify_runtime_live", SCRIPTS / "verify_runtime_live.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def junit_seconds(path: Path) -> tuple[float, int]:
    """(sum of testcase times, number of testcases) — skipped cases count with their (near-zero) time."""
    root = ET.parse(path).getroot()
    cases = list(root.iter("testcase"))
    if not cases:
        raise SystemExit(f"{path}: no <testcase> elements — not a pytest --junitxml report?")
    return sum(float(case.get("time") or 0.0) for case in cases), len(cases)


def lane_budgets(live) -> dict[str, int]:
    nt, posix = live.PYTEST_BUDGET_SECONDS["nt"], live.PYTEST_BUDGET_SECONDS["posix"]
    return {"darwin-arm64": posix, "win32-x64": nt, "win32-arm64": nt + live.EMULATED_PYTEST_EXTRA_SECONDS}


def matrix_job_minutes(workflow: Path = MATRIX_WORKFLOW) -> int:
    return int(re.search(r"timeout-minutes:\s*(\d+)", workflow.read_text(encoding="utf-8")).group(1))


def project(local_seconds: float, live, job_minutes: int) -> tuple[list[dict], list[str]]:
    rows, problems = [], []
    budgets = lane_budgets(live)
    for lane, factor in live.LANE_SLOWDOWN_VS_MAINTAINER_MAC.items():
        projected = local_seconds * factor
        share = projected / budgets[lane]
        rows.append({"lane": lane, "factor": factor, "projected": round(projected), "budget": budgets[lane], "share": share})
        if share > live.PYTEST_BUDGET_WARN_FRACTION:
            needed = projected / (live.PYTEST_BUDGET_WARN_FRACTION - 0.05)
            problems.append(f"{lane}: projected {projected:.0f} s = {share:.0%} of its {budgets[lane]} s budget "
                            f"(> {live.PYTEST_BUDGET_WARN_FRACTION:.0%}); raise it to ≥ {needed:.0f} s or trim the slowest tests")
    if budgets["win32-arm64"] > (job_minutes - OTHER_STEPS_MINUTES) * 60:
        problems.append(f"win32-arm64 budget {budgets['win32-arm64']} s no longer fits runtime-matrix.yml's {job_minutes}-minute job "
                        f"(needs ≥ {OTHER_STEPS_MINUTES} min for the other steps)")
    return rows, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("junit", type=Path, help="pytest --junitxml report of a local live run (vendored instance up)")
    args = parser.parse_args(argv)
    live = _live_module()
    local_seconds, count = junit_seconds(args.junit)
    rows, problems = project(local_seconds, live, matrix_job_minutes())
    print(f"local live suite: {count} tests, {local_seconds:.0f} s")
    for row in rows:
        print(f"  {row['lane']:13s} ×{row['factor']:<4} → {row['projected']:6d} s of {row['budget']:6d} s ({row['share']:.0%})")
    for problem in problems:
        print(f"[BUDGET] {problem}")
    print("lane-budget: " + ("ok" if not problems else f"{len(problems)} problem(s)"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
