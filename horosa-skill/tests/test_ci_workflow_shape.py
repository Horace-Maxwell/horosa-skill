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
_SHELL = re.compile(r"^\s*shell:\s*(\S+)\s*$")
_STEP_START = re.compile(r"^(\s*)- ")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _job_bodies(text: str) -> dict[str, list[str]]:
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
    return jobs


def _steps(body: list[str]) -> list[list[str]]:
    """Split a job body into its `- …` step blocks (the `steps:` list items)."""
    try:
        start = next(i for i, line in enumerate(body) if line.strip() == "steps:")
    except StopIteration:
        return []
    step_indent: int | None = None
    steps: list[list[str]] = []
    for line in body[start + 1 :]:
        match = _STEP_START.match(line)
        if match and (step_indent is None or len(match.group(1)) == step_indent):
            step_indent = len(match.group(1))
            steps.append([line])
        elif steps:
            steps[-1].append(line)
    return steps


def _job_default_shell(body: list[str]) -> str | None:
    """`defaults: run: shell: X` at job level (the part of the body before `steps:`)."""
    head = []
    for line in body:
        if line.strip() == "steps:":
            break
        head.append(line)
    for line in head:
        match = _SHELL.match(line)
        if match:
            return match.group(1)
    return None


def pwsh_run_blocks(text: str) -> list[tuple[str, str]]:
    """Return (job, first_effective_line) for every multi-line `run: |` block executed by pwsh.

    The shell of a block is the step's own `shell:` key if present, else the job's `defaults.run.shell`.
    A bash step inside a pwsh job (or vice versa) is judged by its own shell. Comment and blank lines
    at the top of a block do not count as the first line.
    """
    found: list[tuple[str, str]] = []
    for job, body in _job_bodies(text).items():
        default_shell = _job_default_shell(body)
        for step in _steps(body):
            shell = default_shell
            for line in step:
                match = _SHELL.match(line)
                if match:
                    shell = match.group(1)
            if shell != "pwsh":
                continue
            for index, entry in enumerate(step):
                run = _RUN.match(entry)
                if not run:
                    continue
                base = _indent(entry)
                first = ""
                for block_line in step[index + 1 :]:
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
  mixed:
    runs-on: windows-latest
    steps:
      - name: bash inside a windows job
        shell: bash
        run: |
          set -euo pipefail
      - name: pwsh by explicit step shell
        shell: pwsh
        run: |
          {first}
"""


def test_guard_catches_a_pwsh_block_without_the_switch() -> None:
    """Negative control: the exact shape that hid the `--output` failure must be red."""
    bad = _SYNTHETIC.format(first="$root = Join-Path $env:RUNNER_TEMP 'x'")
    assert offending_blocks(bad) == [
        ("win", "$root = Join-Path $env:RUNNER_TEMP 'x'"),
        ("mixed", "$root = Join-Path $env:RUNNER_TEMP 'x'"),
    ]
    good = _SYNTHETIC.format(first=REQUIRED_LINE)
    assert offending_blocks(good) == []
    # bash jobs — and bash steps inside a pwsh job — are never held to the pwsh rule
    assert [job for job, _ in pwsh_run_blocks(good)] == ["win", "mixed"]


# --------------------------------------------------------------------------------------
# v0.40.0：stdio 探针的工具数不许写死（首推时 116 已过时 → 两个 job 红）
# --------------------------------------------------------------------------------------

_CI_YML_PATH = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"
_PROBE_LITERAL = re.compile(r"\['tools'\] -ne \d+|probe\[\"tools\"\] == \d+")


def literal_probe_counts(workflow_text: str) -> list[str]:
    return [m.group(0) for m in _PROBE_LITERAL.finditer(workflow_text)]


def test_stdio_probes_read_the_tool_count_from_the_budget_contract() -> None:
    text = _CI_YML_PATH.read_text(encoding="utf-8")
    assert literal_probe_counts(text) == []
    assert "mcp_list_budget.json" in text and "full_tools" in text and "compact_tools" in text


def test_guard_catches_a_literal_probe_count() -> None:
    assert literal_probe_counts("if ($r['steps']['stdio_probe']['tools'] -ne 116) { throw 'x' }") == ["['tools'] -ne 116"]
    assert literal_probe_counts('assert probe["tools"] == 116 == probe["expected_tools"]') == ['probe["tools"] == 116']

