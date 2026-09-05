#!/usr/bin/env python3
"""Every error code must map to an agent-executable recovery; bilingual messages may only increase.

An error code is an interface, not a log line: the agent on the other side of MCP has to decide
whether to ask the user, fix an input, retry, or tell the user to run `doctor`. v0.35.0 classified only
runtime./transport./js_engine./backend_param — the other ~100 codes carried no recovery at all, and
112 of 151 error messages were single-language.

Rule 1 (hard): every `code="..."` literal in `src/horosa_skill` must classify through
`errors.classify_code` (exact table → suffix rule → prefix rule). A new code that fits none fails CI —
add it to RECOVERY_TABLE or name it with a classifiable suffix (`*_missing_*`, `*_invalid*`,
`*_failed`, `*_unavailable`, …).

Rule 2 (ratchet): the number of raise sites whose literal message is not bilingual (CJK + Latin)
lives in `contracts/error_recovery_debt.json` and may only go down. Refresh with `--update-baseline`.
Stdlib + the package. Wired into CI.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
PKG_ROOT = SCRIPTS.parent
SRC = PKG_ROOT / "src" / "horosa_skill"
BASELINE = PKG_ROOT / "contracts" / "error_recovery_debt.json"
sys.path.insert(0, str(PKG_ROOT / "src"))

_CODE_RE = re.compile(r'code="([a-z_.]+)"')
_CJK = re.compile(r"[一-鿿]")
_LATIN = re.compile(r"[A-Za-z]{3,}")


def collect_codes() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for py in sorted(SRC.rglob("*.py")):
        for code in _CODE_RE.findall(py.read_text(encoding="utf-8")):
            found.setdefault(code, []).append(py.relative_to(SRC).as_posix())
    return found


def non_bilingual_sites() -> dict[str, int]:
    per_file: dict[str, int] = {}
    for py in sorted(SRC.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call) and node.exc.args):
                continue
            func = node.exc.func
            name = getattr(func, "id", None) or getattr(func, "attr", "")
            if not str(name).endswith("Error"):
                continue
            first = node.exc.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                text = first.value
            elif isinstance(first, ast.JoinedStr):
                text = "".join(v.value for v in first.values if isinstance(v, ast.Constant) and isinstance(v.value, str))
            else:
                continue
            if not (_CJK.search(text) and _LATIN.search(text)):
                key = py.relative_to(SRC).as_posix()
                per_file[key] = per_file.get(key, 0) + 1
    return per_file


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--update-baseline", action="store_true", help="rewrite the bilingual-message baseline")
    args = ap.parse_args()

    from horosa_skill.errors import classify_code

    codes = collect_codes()
    unclassified = sorted(code for code in codes if classify_code(code)[0] is None)
    per_file = non_bilingual_sites()
    total = sum(per_file.values())

    if args.update_baseline:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(
            json.dumps(
                {
                    "_comment": (
                        "Ratchet baseline for error raise sites whose literal message is not bilingual (CJK + Latin). "
                        "May only go down; refresh with `uv run python scripts/verify_error_recovery.py --update-baseline`. "
                        "Code classification (every code must reach a recovery rule) is a hard rule, not a baseline."
                    ),
                    "non_bilingual_messages": total,
                    "per_file": dict(sorted(per_file.items())),
                    "codes_seen": len(codes),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"baseline updated: {total} non-bilingual message(s), {len(codes)} codes seen")
        if unclassified:
            print(f"  (still unclassified codes: {unclassified})")
        return 0

    errors: list[str] = []
    if unclassified:
        errors.append(
            "error codes with no recovery rule (add to errors.RECOVERY_TABLE or use a classifiable suffix): "
            + ", ".join(f"{c} ({codes[c][0]})" for c in unclassified)
        )
    if not BASELINE.is_file():
        errors.append(f"missing {BASELINE.relative_to(PKG_ROOT)} — run with --update-baseline once to seed it")
    else:
        base = json.loads(BASELINE.read_text(encoding="utf-8"))
        allowed = int(base.get("non_bilingual_messages", total))
        if total > allowed:
            worse = {k: v for k, v in per_file.items() if v > int(base.get("per_file", {}).get(k, 0))}
            errors.append(
                f"non-bilingual error messages rose {allowed} → {total} ({worse}); write new messages with "
                "errors.bilingual(zh, en)"
            )
        elif total < allowed:
            errors.append(
                f"non-bilingual error messages dropped {allowed} → {total}; run "
                "`uv run python scripts/verify_error_recovery.py --update-baseline` to lock the gain in"
            )
    if errors:
        print("error-recovery guard FAILED:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print(f"error-recovery guard OK: {len(codes)} codes all classified; {total} non-bilingual message(s) at baseline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
