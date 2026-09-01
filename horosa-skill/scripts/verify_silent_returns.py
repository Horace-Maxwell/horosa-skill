#!/usr/bin/env python3
"""Ratchet the number of `src/tools/*.js` early-returns that carry no error code.

A tool that returns `{ text: '' }` (or `{ snapshot_text: '' }`, or `{ sections: {} }`) tells the
caller nothing: the section simply does not appear, and every layer above reads that as "this
technique had nothing to say" rather than "this failed". Python's enrichers then drop it silently a
second time — `_attach_bazi_geju` read only `snapshot_text`, so issue #15's structured error was
discarded one level up. Same shape, one layer higher.

Killing all of them at once would be a large, risky sweep, so this is a **ratchet**: the current
count is the baseline, new ones fail CI, and paying debt down requires lowering the baseline (the
guard says so when the count drops). Four of the highest-risk sites were fixed outright in v0.33.1
(tiebanFramework / baziPeriod / sanshiZiweiSihua / guolaoStarDignity — the last three swallowed
exceptions in a bare `catch`).

Baseline lives in `contracts/silent_empty_returns.json` (git-tracked, repo-relative paths).
Refresh after paying debt with `--update-baseline`. Stdlib-only. Wired into CI.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
PKG_ROOT = SCRIPTS.parent
TOOLS_DIR = PKG_ROOT / "horosa-core-js" / "src" / "tools"
BASELINE = PKG_ROOT / "contracts" / "silent_empty_returns.json"

# `return { text: '' }` / `{ snapshot_text: '' }` / `{ sections: {} }` with no sibling error field.
# Deliberately literal: anything cleverer would need a guard of its own.
_EMPTY_RETURN_RE = re.compile(
    r"return\s*\{\s*(?:(?:snapshot_)?text\s*:\s*(?:''|\"\")|sections\s*:\s*\{\s*\})[^{}]*\}",
    re.MULTILINE,
)
_HAS_SIGNAL_RE = re.compile(r"\b(error|reason|ok)\b")


def scan() -> dict[str, list[int]]:
    found: dict[str, list[int]] = {}
    for path in sorted(TOOLS_DIR.glob("*.js")):
        src = path.read_text(encoding="utf-8")
        lines: list[int] = []
        for m in _EMPTY_RETURN_RE.finditer(src):
            if _HAS_SIGNAL_RE.search(m.group(0)):
                continue  # carries an error code / reason / ok flag — that is the fixed shape
            lines.append(src[: m.start()].count("\n") + 1)
        if lines:
            found[path.name] = lines
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
                        "Ratchet baseline for src/tools/*.js early-returns that carry no error code. "
                        "New ones fail CI; paying debt down means lowering these numbers. "
                        "Refresh with `uv run python scripts/verify_silent_returns.py --update-baseline`."
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
        print(f"baseline updated: {total} silent empty return(s) across {len(found)} file(s)")
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
                f"{name}: {len(lines)} silent empty return(s) at line(s) {lines}, baseline allows "
                f"{allowed}. Give the new one a `data: {{ ok: false, reason, message }}` — an empty "
                f"section with no signal reads as 'nothing to say', not 'this failed'."
            )
    if errors:
        print("silent-empty-return ratchet FAILED:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    if total < int(base.get("total", total)):
        print(
            f"silent-empty-return debt dropped {base.get('total')} → {total}. "
            "Run `uv run python scripts/verify_silent_returns.py --update-baseline` to lock the gain in "
            "(an un-tightened ratchet lets the debt creep straight back).",
            file=sys.stderr,
        )
        return 1

    print(
        f"silent-empty-return ratchet OK: {total} un-signalled empty return(s) across "
        f"{len(found)} file(s), at or under the baseline."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
