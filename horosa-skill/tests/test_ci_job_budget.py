"""scripts/ci_job_budget.py: a ci.yml job that used >85% of its own timeout says so (v0.51.0: both jobs sat at 95–97% unseen)."""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ci_job_budget.py"
_spec = importlib.util.spec_from_file_location("ci_job_budget", _SCRIPT)
budget = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("ci_job_budget", budget)
_spec.loader.exec_module(budget)

CI_TEXT = budget.CI.read_text(encoding="utf-8")
JOBS = dict(re.findall(r"^  ([\w-]+):\n(.*?)(?=^  \S|\Z)", CI_TEXT.split("\njobs:\n", 1)[1], flags=re.MULTILINE | re.DOTALL))


def test_reads_each_jobs_own_timeout_not_a_step_level_one() -> None:
    assert set(JOBS) == {"test", "windows-smoke"}
    assert budget.job_timeout_minutes(CI_TEXT, "test") == 40
    assert budget.job_timeout_minutes(CI_TEXT, "windows-smoke") == 90      # not the 35-minute step-level timeout inside it


def test_the_v051_near_misses_would_have_been_annotated() -> None:
    """ec626fa1: test 24:19 of 25 min; 030d8784 era: windows-smoke 57 of 60 min. Both green, both one slow runner from cancelled."""
    warn, line = budget.verdict("test", 24 * 60 + 19, 25)
    assert warn and line.startswith("::warning title=ci job near its timeout (test)::test used 24.3 of its 25 min (97%)")
    warn, _ = budget.verdict("windows-smoke", 57 * 60, 60)
    assert warn


def test_comfortable_runs_print_a_plain_line() -> None:
    warn, line = budget.verdict("test", 20 * 60, 40)
    assert not warn and line == "ci-job-budget: test used 20.0 of its 40 min (50%)"


def test_every_ci_job_records_its_start_first_and_reports_last() -> None:
    for job, block in JOBS.items():
        names = re.findall(r"^      - (?:name: (.+)|uses: )", block, flags=re.MULTILINE)
        assert names[0] == "Record job start", (job, names[:2])
        assert names[-1] == "Job time vs its timeout", (job, names[-2:])
        tail = block[block.rindex("- name: Job time vs its timeout"):]
        assert "if: ${{ !cancelled() }}" in tail and f"ci_job_budget.py --job {job}\n" in tail + "\n", job
        assert 'HOROSA_JOB_STARTED=$(date +%s)' in block, job


def test_missing_start_never_fails_the_job(monkeypatch, capsys) -> None:
    monkeypatch.delenv("HOROSA_JOB_STARTED", raising=False)
    assert budget.main(["--job", "test"]) == 0
    assert "not recorded" in capsys.readouterr().out
