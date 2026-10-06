#!/usr/bin/env python3
"""Undefined names are NameErrors parked in branches nobody runs (v0.38.1 post-release lesson).

v0.38.1 shipped `_friendly_runtime_error_payload` reading `details`, a name that function never defined. The branch
runs only when `client openclaw-setup` / `openclaw-check` meets `runtime.platform_unsupported` - on Linux and Intel
Macs, exactly the hosts promised "a clear error plus the gateway way out". No test, lane, or maintainer machine
(darwin-arm64) ever executed that line, so users there would have received a traceback instead of the advice.
pytest cannot catch a bug on a line it never runs; a static check can.

The gate is limited to rules that are runtime crashes (now or in a later CPython), not style:
  F821 undefined name / F822 undefined name in __all__ / F823 local variable referenced before assignment
  B034 `re.split` / `re.sub` / `re.subn` given maxsplit / count / flags positionally - deprecated since Python 3.13
       and slated to become a TypeError; CI pins 3.12 so the DeprecationWarning only ever shows on a maintainer
       machine with a newer venv (2026-10-05: scripts/verify_runtime_python_lock.py on the new Windows box)
over src/, scripts/ and tests/, with a baseline of zero. Style rules (unused imports/variables, ...) are out of scope.

`--self-test` proves the wiring catches: a synthetic module with an undefined name in a rarely-run branch must be red,
a synthetic module passing `re.split`'s maxsplit positionally must be red, and the fixed modules must be green.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")

PKG_ROOT = Path(__file__).resolve().parents[1]
TARGETS = ("src", "scripts", "tests")
RULES = "F821,F822,F823,B034"


def ruff_command(paths: list[str]) -> list[str]:
    return [
        sys.executable,
        "-m",
        "ruff",
        "check",
        "--isolated",  # no config file may widen or narrow the rule set behind the gate's back
        "--select",
        RULES,
        "--no-cache",
        # The repo .gitignore carries the git-only literal `${env:HOME*`, which ruff's glob parser rejects with a
        # warning. Nothing under the targets is gitignored, so not reading it changes nothing but the noise.
        "--no-respect-gitignore",
        "--output-format",
        "concise",
        *paths,
    ]


def run_ruff(paths: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ruff_command(paths),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def ruff_available() -> bool:
    probe = subprocess.run(
        [sys.executable, "-m", "ruff", "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return probe.returncode == 0


BAD_MODULE = '''def friendly(exc):
    code = exc.code or ""
    if code == "runtime.platform_unsupported":
        return str((details or {}).get("next_action"))
    return None
'''
GOOD_MODULE = BAD_MODULE.replace("(details or {})", "(exc.details or {})")
BAD_RE_MODULE = '''import re


def requirement_name(line):
    return re.split(r"[<>=!~]", line, 1)[0]
'''
GOOD_RE_MODULE = BAD_RE_MODULE.replace("line, 1)", "line, maxsplit=1)")


def self_test() -> list[str]:
    problems: list[str] = []
    with tempfile.TemporaryDirectory(prefix="horosa-undefined-names-") as tmp:
        root = Path(tmp)
        (root / "bad_module.py").write_text(BAD_MODULE, encoding="utf-8")
        (root / "good_module.py").write_text(GOOD_MODULE, encoding="utf-8")
        (root / "bad_re_module.py").write_text(BAD_RE_MODULE, encoding="utf-8")
        (root / "good_re_module.py").write_text(GOOD_RE_MODULE, encoding="utf-8")
        red = run_ruff(["bad_module.py"], root)
        green = run_ruff(["good_module.py"], root)
        red_re = run_ruff(["bad_re_module.py"], root)
        green_re = run_ruff(["good_re_module.py"], root)
    if red.returncode == 0 or "F821" not in red.stdout:
        problems.append(f"self-test: an undefined name in a rarely-run branch was NOT caught (exit {red.returncode}): {red.stdout}{red.stderr}")
    if green.returncode != 0:
        problems.append(f"self-test: the fixed module was reported (exit {green.returncode}): {green.stdout}{green.stderr}")
    if red_re.returncode == 0 or "B034" not in red_re.stdout:
        problems.append(f"self-test: a positional `re.split` maxsplit was NOT caught (exit {red_re.returncode}): {red_re.stdout}{red_re.stderr}")
    if green_re.returncode != 0:
        problems.append(f"self-test: the keyword-maxsplit module was reported (exit {green_re.returncode}): {green_re.stdout}{green_re.stderr}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--self-test", action="store_true", help="prove the gate catches a synthetic undefined name")
    args = parser.parse_args(argv)

    if not ruff_available():
        print("undefined-names: ruff is not installed in this environment - run `uv sync --dev` (it is pinned in pyproject).")
        return 2
    if args.self_test:
        problems = self_test()
        if problems:
            for problem in problems:
                print(problem)
            return 1
        print(
            f"undefined-names self-test: ok ({RULES} catches the v0.38.1 `details` shape and a positional `re.split` "
            "maxsplit; the fixed modules are clean)"
        )
        return 0

    result = run_ruff(list(TARGETS), PKG_ROOT)
    if result.returncode != 0:
        print(result.stdout.rstrip())
        if result.stderr.strip():
            print(result.stderr.rstrip())
        print(
            f"undefined-names: {RULES} must stay at zero over {', '.join(TARGETS)} - each hit is a NameError waiting in "
            "a branch that no test runs (v0.38.1 shipped one on the Linux / Intel Mac error path), or a positional "
            "re.split/sub/subn argument that newer CPython deprecates (pass maxsplit= / count= / flags= by keyword)."
        )
        return 1
    print(f"undefined-names: ok ({RULES} clean over {', '.join(TARGETS)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
