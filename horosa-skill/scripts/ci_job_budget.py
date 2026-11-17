#!/usr/bin/env python
"""Annotate a ci.yml job that used more than 85% of its own `timeout-minutes` — before it starts getting cancelled.

Why (v0.51.0): after the v3.14.0 sync the Linux `test` job ran 19–24 of 25 minutes and `windows-smoke` 45–57 of 60, and
nobody noticed until each was cancelled mid-unit-tests (030d8784, e83b6450) — a green run says nothing about how close it
was. The release-matrix lanes already print a near-budget `::warning::` (verify_runtime_live.PYTEST_BUDGET_WARN_FRACTION);
this gives the per-push CI jobs the same signal. It reads the timeout from ci.yml itself (no second number to keep in
sync) and never fails the job: a cancelled job skips this step anyway, so its only use is the near miss.

    - name: Record job start            # first step
      shell: bash
      run: echo "HOROSA_JOB_STARTED=$(date +%s)" >> "$GITHUB_ENV"
    ...
    - name: Job time vs its timeout     # last step
      if: ${{ !cancelled() }}
      run: python horosa-skill/scripts/ci_job_budget.py --job test
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

CI = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"
WARN_FRACTION = 0.85   # same share as the release lanes (verify_runtime_live.PYTEST_BUDGET_WARN_FRACTION)


def job_timeout_minutes(text: str, job: str) -> int:
    """`timeout-minutes` at the job level (4-space indent) of `job` in a workflow file; step-level timeouts are deeper."""
    block = re.search(rf"^  {re.escape(job)}:\n(.*?)(?=^  \S|\Z)", text, flags=re.MULTILINE | re.DOTALL)
    if not block:
        raise SystemExit(f"job {job!r} not found in {CI}")
    found = re.search(r"^    timeout-minutes:\s*(\d+)\s*$", block.group(1), flags=re.MULTILINE)
    if not found:
        raise SystemExit(f"job {job!r} has no job-level timeout-minutes in {CI}")
    return int(found.group(1))


def verdict(job: str, elapsed_seconds: float, timeout_minutes: int) -> tuple[bool, str]:
    share = elapsed_seconds / (timeout_minutes * 60)
    message = (f"{job} used {elapsed_seconds / 60:.1f} of its {timeout_minutes} min ({share:.0%})")
    if share > WARN_FRACTION:
        return True, (f"::warning title=ci job near its timeout ({job})::{message} — raise timeout-minutes in ci.yml "
                      "before it gets cancelled mid-step, or find what grew (docs/LESSONS.md v0.51.0)")
    return False, f"ci-job-budget: {message}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--job", required=True, help="job id in ci.yml (test / windows-smoke)")
    args = parser.parse_args(argv)
    started = os.environ.get("HOROSA_JOB_STARTED", "").strip()
    if not started.isdigit():
        print("ci-job-budget: HOROSA_JOB_STARTED not recorded (the job's first step sets it) — nothing to compare")
        return 0
    _, line = verdict(args.job, time.time() - int(started), job_timeout_minutes(CI.read_text(encoding="utf-8"), args.job))
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
