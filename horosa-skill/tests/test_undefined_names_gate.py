"""The undefined-name gate must catch its target shape, must pass on the repo, and must be run by CI.

v0.38.1 shipped a NameError (`details`) on the Linux / Intel Mac branch of the OpenClaw error formatter; no test ran
that line. See scripts/verify_undefined_names.py for the rule set and why it is limited to runtime-crash rules.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
GATE = PKG_ROOT / "scripts" / "verify_undefined_names.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GATE), *args],
        cwd=str(PKG_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=180,
    )


def test_gate_self_test_catches_an_undefined_name_in_a_rarely_run_branch() -> None:
    result = _run("--self-test")
    assert result.returncode == 0, result.stdout + result.stderr


def test_repo_has_no_undefined_names() -> None:
    result = _run()
    assert result.returncode == 0, result.stdout + result.stderr


def test_ci_test_job_runs_the_gate_and_its_self_test() -> None:
    ci = (PKG_ROOT.parent / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "uv run python scripts/verify_undefined_names.py --self-test && uv run python scripts/verify_undefined_names.py" in ci
