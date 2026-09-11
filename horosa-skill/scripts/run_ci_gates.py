#!/usr/bin/env python3
"""Run the SAME gates ci.yml's `test` job runs, locally, before pushing (v0.38.0 lesson: main was red for 19
commits while every local run was "green" — the local ritual was pytest + docs-sync, not the ci.yml list).

Parses `.github/workflows/ci.yml`, takes every `run:` step of the `test` job that invokes `uv run …`
(pytest, verify_* scripts, build_knowledge_index --check, run_benchmark …), and executes it from
horosa-skill/ in CI shape (HOROSA_RUNTIME_ROOT → empty temp dir, both *_SERVER_ROOT unreachable).
Exit 0 only when every step passes. Steps that need a runner-only resource are skipped by name (SKIP).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PKG_ROOT.parent
CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"
# steps whose commands only make sense on the hosted runner (git+file:// rev, HOME=$(mktemp) uvx from a built wheel)
SKIP = ("Zero-install path works", "Zero-install path from the wheel works")


def ci_test_steps(text: str) -> list[tuple[str, str]]:
    """[(step name, command)] for the `test` job — single-line `run:` steps only (multi-line ones are runner glue)."""
    job = re.search(r"^  test:\n(.*?)(?=^  [a-z_-]+:\n|\Z)", text, re.S | re.M)
    if not job:
        raise SystemExit("ci.yml: no `test` job")
    steps: list[tuple[str, str]] = []
    name = ""
    for line in job.group(1).splitlines():
        stripped = line.strip()
        if stripped.startswith("- name:"):
            name = stripped[len("- name:"):].strip()
        elif stripped.startswith("run:") and not stripped.endswith("|"):
            command = stripped[len("run:"):].strip()
            if command.startswith("uv run"):
                steps.append((name, command))
    return steps


def main(argv: list[str] | None = None) -> int:
    only = set(argv or [])
    steps = ci_test_steps(CI.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="horosa-ci-shape-") as empty_root:
        env = {
            **os.environ,
            "HOROSA_RUNTIME_ROOT": empty_root,
            "HOROSA_SERVER_ROOT": "http://127.0.0.1:9",
            "HOROSA_CHART_SERVER_ROOT": "http://127.0.0.1:9",
        }
        failed: list[str] = []
        for name, command in steps:
            if only and not any(token in command or token in name for token in only):
                continue
            if any(name.startswith(skip) for skip in SKIP):
                print(f"=== SKIP (runner-only): {name}")
                continue
            print(f"\n=== {name}\n$ {command}", flush=True)
            result = subprocess.run(command, shell=True, cwd=PKG_ROOT, env=env)
            if result.returncode != 0:
                failed.append(name)
                print(f"!!! FAILED: {name}", flush=True)
        print()
        if failed:
            print(f"ci-gates: {len(failed)} of {len(steps)} steps FAILED — {failed}")
            return 1
        print(f"ci-gates: all {len(steps)} ci.yml test-job gates green locally (same commands, CI shape)")
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
