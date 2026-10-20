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

Second rule (v0.41.1): **silent broad excepts**. The `logger.warning(` regex cannot see a handler that says nothing
at all — `except Exception: pass`, `continue`, `return ""` — and that is exactly how four enrichment paths in
service.py stayed silent after the v0.36.0 sweep (the 2026-10 audit found 12). A broad handler (`except Exception` /
`BaseException` / bare) whose body only passes, continues, returns a constant / empty literal or assigns one, and
calls nothing (no `_degrade`, no logger, no raise), is counted per file and ratcheted the same way. Probes whose
`None` / `False` *is* the answer are in the baseline on purpose; a new one needs `--update-baseline` in the same
change — a visible decision, not an accident.

Baseline lives in `contracts/silent_degrade_debt.json` (git-tracked, per-file). Refresh after
paying debt with `--update-baseline`. Stdlib-only. Wired into CI.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")
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


_BROAD = {"Exception", "BaseException"}


def _is_broad(handler: ast.ExceptHandler) -> bool:
    kind = handler.type
    if kind is None:
        return True
    names = kind.elts if isinstance(kind, ast.Tuple) else [kind]
    return any(isinstance(n, ast.Name) and n.id in _BROAD for n in names)


def _is_quiet_value(node: ast.expr | None) -> bool:
    if node is None or isinstance(node, ast.Constant):
        return True
    return isinstance(node, ast.List | ast.Dict | ast.Tuple | ast.Set) and not getattr(node, "elts", getattr(node, "keys", None))


def silent_handler(handler: ast.ExceptHandler) -> bool:
    """True when a broad handler swallows quietly: no call, no raise, only pass / continue / constant return or assign."""
    if not _is_broad(handler):
        return False
    for stmt in handler.body:
        if any(isinstance(node, ast.Call | ast.Raise) for node in ast.walk(stmt)):
            return False
        if isinstance(stmt, ast.Pass | ast.Continue | ast.Break):
            continue
        if isinstance(stmt, ast.Return) and _is_quiet_value(stmt.value):
            continue
        if isinstance(stmt, ast.Assign) and _is_quiet_value(stmt.value):
            continue
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):  # a bare string / docstring-ish note
            continue
        return False
    return True


def scan_silent_excepts(source: str) -> list[int]:
    return [node.lineno for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ExceptHandler) and silent_handler(node)]


def scan_silent_excepts_tree() -> dict[str, list[int]]:
    found: dict[str, list[int]] = {}
    for path in sorted(SRC_DIR.rglob("*.py")):
        lines = scan_silent_excepts(path.read_text(encoding="utf-8"))
        if lines:
            found[path.relative_to(SRC_DIR).as_posix()] = lines
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--update-baseline", action="store_true", help="rewrite the baseline after paying debt")
    args = ap.parse_args()

    found = scan()
    total = sum(len(v) for v in found.values())
    quiet = scan_silent_excepts_tree()
    quiet_total = sum(len(v) for v in quiet.values())

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
                    "silent_excepts": {
                        "_comment": "Broad excepts that pass / continue / return a constant and call nothing (probes whose "
                                    "None/False is the answer are here on purpose). New ones fail CI; pay down with _degrade.",
                        "total": quiet_total,
                        "per_file": {k: len(v) for k, v in sorted(quiet.items())},
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"baseline updated: {total} bare logger.warning call(s), {quiet_total} silent broad except(s)")
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
    quiet_base = base.get("silent_excepts") or {}
    quiet_per_file: dict[str, int] = quiet_base.get("per_file", {})
    for name, lines in sorted(quiet.items()):
        allowed = quiet_per_file.get(name, 0)
        if len(lines) > allowed:
            errors.append(
                f"{name}: {len(lines)} silent broad except(s) at line(s) {lines}, baseline allows {allowed}. "
                "A broad handler must tell the caller (`_degrade(...)`, a report field, a raise); if its None/False is "
                "genuinely the answer (a probe), say so in a comment and refresh the baseline in the same change."
            )
    if errors:
        print("silent-degrade ratchet FAILED:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    if total < int(base.get("total", total)) or quiet_total < int(quiet_base.get("total", quiet_total)):
        print(
            f"silent-degrade debt dropped (warnings {base.get('total')} → {total}, quiet excepts "
            f"{quiet_base.get('total')} → {quiet_total}). "
            "Run `uv run python scripts/verify_silent_degrades.py --update-baseline` to lock the gain in.",
            file=sys.stderr,
        )
        return 1

    print(
        f"silent-degrade ratchet OK: {total} bare logger.warning call(s), {quiet_total} silent broad except(s), "
        "at or under the baseline."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
