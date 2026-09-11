"""CI workflow shape guards (v0.38.0 B0).

Why this exists: GitHub's `pwsh` shell runs a multi-line `run:` block as ONE script and reports only
the LAST command's exit code. The Windows smoke step called `tool run … --output` — an option that did
not exist until v0.38.0 — and the failure stayed invisible for many rounds because the `memory query`
line at the end exited 0. `$PSNativeCommandUseErrorActionPreference = $true` (pwsh ≥ 7.3; the
`windows-latest` image ships 7.4) makes every native non-zero exit fail the step under the
`$ErrorActionPreference = 'stop'` that GitHub prepends. A pwsh step without that line is a step whose
failures are not evidence of anything.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
REQUIRED_LINE = "$PSNativeCommandUseErrorActionPreference = $true"

_JOB = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")
_RUN = re.compile(r"^(\s*)(?:- )?run:\s*\|\s*$")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def pwsh_run_blocks(text: str) -> list[tuple[str, str]]:
    """Return (job, first_effective_line) for every multi-line `run: |` block executed by pwsh.

    A job counts as pwsh when it declares `shell: pwsh` anywhere (job default or any step); bash jobs
    are ignored. Comment and blank lines at the top of a block do not count as the first line.
    """
    lines = text.splitlines()
    jobs: dict[str, list[str]] = {}
    current: str | None = None
    in_jobs = False
    for line in lines:
        if line.strip() == "jobs:":
            in_jobs = True
            continue
        if not in_jobs:
            continue
        match = _JOB.match(line)
        if match:
            current = match.group(1)
            jobs[current] = []
            continue
        if current is not None:
            jobs[current].append(line)
    found: list[tuple[str, str]] = []
    for job, body in jobs.items():
        if not any(re.search(r"^\s*shell:\s*pwsh\s*$", entry) for entry in body):
            continue
        for index, entry in enumerate(body):
            run = _RUN.match(entry)
            if not run:
                continue
            base = _indent(entry)
            first = ""
            for block_line in body[index + 1 :]:
                if block_line.strip() == "":
                    continue
                if _indent(block_line) <= base:
                    break
                if block_line.strip().startswith("#"):
                    continue
                first = block_line.strip()
                break
            found.append((job, first))
    return found


def offending_blocks(text: str) -> list[tuple[str, str]]:
    return [(job, first) for job, first in pwsh_run_blocks(text) if first != REQUIRED_LINE]


def test_every_pwsh_run_block_propagates_native_exit_codes() -> None:
    offenders: list[str] = []
    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        for job, first in offending_blocks(workflow.read_text(encoding="utf-8")):
            offenders.append(f"{workflow.name}::{job} starts with {first!r}")
    assert offenders == [], (
        "pwsh multi-line steps only report the LAST command's exit code — every such block must start with "
        f"`{REQUIRED_LINE}`: {offenders}"
    )


_SYNTHETIC = """name: x
on: push
jobs:
  win:
    runs-on: windows-latest
    defaults:
      run:
        shell: pwsh
    steps:
      - name: smoke
        run: |
          # a comment does not count as the first line
          {first}
          uv run horosa-skill tool run qimen --stdin --output out.json
          uv run horosa-skill memory query --tool qimen --limit 1
  nix:
    runs-on: ubuntu-latest
    steps:
      - name: bash step
        run: |
          echo hello
"""


def test_guard_catches_a_pwsh_block_without_the_switch() -> None:
    """Negative control: the exact shape that hid the `--output` failure must be red."""
    bad = _SYNTHETIC.format(first="$root = Join-Path $env:RUNNER_TEMP 'x'")
    assert offending_blocks(bad) == [("win", "$root = Join-Path $env:RUNNER_TEMP 'x'")]
    good = _SYNTHETIC.format(first=REQUIRED_LINE)
    assert offending_blocks(good) == []
    # bash jobs are never held to the pwsh rule
    assert [job for job, _ in pwsh_run_blocks(good)] == ["win"]
