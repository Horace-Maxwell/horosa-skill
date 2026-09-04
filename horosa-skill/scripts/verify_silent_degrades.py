#!/usr/bin/env python3
"""Ratchet the number of `logger.warning(` calls inside the `horosa_skill` package.

Why a log call is debt here: every one of the 35 `logger.warning` sites `service.py` had in
v0.35.0 sat in an `except` branch of the "enrichment failed, keep the main chart" kind. The log
line said "X failed"; the envelope said `ok=True, warnings=[]` and simply had fewer sections —
a real qimen archive carried `missing_selected_sections` 10/17 with an empty `warnings` list.
Graceful degradation that the caller cannot see is silent degradation.

The fix is `service._degrade(...)`: same log line, plus a note into the current tool call's
collector that `run_tool` merges into `envelope.warnings` (nested calls bubble up). So in this
package a bare `logger.warning(` means "told the log, not the caller" — this guard keeps the
count at the baseline (0 after the v0.36.0 sweep) so the pattern cannot creep back one site at
a time. Need a warning that genuinely has no caller to tell (a startup/config notice)? Use
`logger.info` or `logger.log(logging.WARNING, ...)` with a comment saying why the caller does
not need it; the regex is deliberately literal.

Baseline lives in `contracts/silent_degrade_debt.json` (git-tracked, per-file). Refresh after
paying debt with `--update-baseline`. Stdlib-only. Wired into CI.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
PKG_ROOT = SCRIPTS.parent
SRC_DIR = PKG_ROOT / "src" / "horosa_skill"
BASELINE = PKG_ROOT / "contracts" / "silent_degrade_debt.json"

_WARNING_CALL_RE = re.compile(r"\blogger\.warning\(")


def scan() -> dict[str, list[int]]:
    found: dict[str, list[int]] = {}
    for path in sorted(SRC_DIR.rglob("*.py")):
        src = path.read_text(encoding="utf-8")
        lines = [src[: m.start()].count("\n") + 1 for m in _WARNING_CALL_RE.finditer(src)]
        if lines:
            found[path.relative_to(SRC_DIR).as_posix()] = lines
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--update-baseline", action="store_true", help="rewrite the baseline after paying debt")
    args = ap.parse_args()

    found = scan()
    total = sum(len(v) for v in found.values())

    if args.update_baseline:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(
            json.dumps(
                {
                    "_comment": (
                        "Ratchet baseline for bare `logger.warning(` calls inside src/horosa_skill. "
                        "A degrade site must call service._degrade(...) so the note reaches envelope.warnings; "
                        "new bare warnings fail CI. Refresh with "
                        "`uv run python scripts/verify_silent_degrades.py --update-baseline`."
                    ),
                    "total": total,
                    "per_file": {k: len(v) for k, v in sorted(found.items())},
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"baseline updated: {total} bare logger.warning call(s) across {len(found)} file(s)")
        return 0

    if not BASELINE.is_file():
        print(
            f"missing {BASELINE.relative_to(PKG_ROOT)} — run with --update-baseline once to seed it",
            file=sys.stderr,
        )
        return 1

    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    base_per_file: dict[str, int] = base.get("per_file", {})
    errors: list[str] = []
    for name, lines in sorted(found.items()):
        allowed = base_per_file.get(name, 0)
        if len(lines) > allowed:
            errors.append(
                f"{name}: {len(lines)} bare logger.warning call(s) at line(s) {lines}, baseline allows "
                f"{allowed}. In a degrade branch call `_degrade(fmt, *args[, note=...])` instead — the "
                f"caller must see the note in envelope.warnings, not just the log."
            )
    if errors:
        print("silent-degrade ratchet FAILED:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    if total < int(base.get("total", total)):
        print(
            f"silent-degrade debt dropped {base.get('total')} → {total}. "
            "Run `uv run python scripts/verify_silent_degrades.py --update-baseline` to lock the gain in.",
            file=sys.stderr,
        )
        return 1

    print(
        f"silent-degrade ratchet OK: {total} bare logger.warning call(s) across {len(found)} file(s), "
        "at or under the baseline."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
