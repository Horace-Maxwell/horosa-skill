#!/usr/bin/env python3
"""Ratchet the dispatch router against a natural-language corpus (zh + en).

An agent that cannot find a technique will not call it: the v0.35.0 audit found 58 common English
triggers 67% zero-hit, 24 techniques without any routing rule (all eight 择日 searches, tarot only in
the fallback candidate pool), and `vedic` routed to the *progression* tool. Rules alone drift; this
guard pins behaviour on a corpus of what users actually type — `contracts/router_corpus.json` maps
each query to the tool(s) a user means, and `min_pass` may only go up.

Exit non-zero when the pass count drops below `min_pass`, or when it rises without the baseline being
refreshed (`--update-baseline`), so gains are locked in. Stdlib + the package. Wired into CI.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
PKG_ROOT = SCRIPTS.parent
CORPUS = PKG_ROOT / "contracts" / "router_corpus.json"
sys.path.insert(0, str(PKG_ROOT / "src"))


def run_corpus() -> tuple[int, list[str]]:
    from horosa_skill.engine.router import select_tools
    from horosa_skill.errors import DispatchResolutionError
    from horosa_skill.schemas.tools import DispatchInput

    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    passed = 0
    failures: list[str] = []
    for case in data["cases"]:
        query, expect = case["query"], list(case["expect"])
        try:
            got = select_tools(DispatchInput(query=query))
        except DispatchResolutionError as exc:
            got = [f"<no match: {exc.details.get('candidates')}>"]
        if got == expect:
            passed += 1
        else:
            failures.append(f"{query!r}: expected {expect}, got {got}")
    return passed, failures


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--update-baseline", action="store_true", help="lock the current pass count in as min_pass")
    ap.add_argument("--verbose", action="store_true", help="print every failing case")
    args = ap.parse_args()

    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    total = len(data["cases"])
    passed, failures = run_corpus()

    if args.update_baseline:
        data["min_pass"] = passed
        CORPUS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"baseline updated: min_pass = {passed}/{total}")
        for line in failures:
            print(f"  still failing: {line}")
        return 0

    min_pass = int(data.get("min_pass", 0))
    if passed < min_pass:
        print(f"router corpus FAILED: {passed}/{total} passed, baseline requires {min_pass}", file=sys.stderr)
        for line in failures:
            print(f"  - {line}", file=sys.stderr)
        return 1
    if passed > min_pass:
        print(
            f"router corpus improved: {passed}/{total} > min_pass {min_pass}. Run "
            "`uv run python scripts/verify_router_corpus.py --update-baseline` to lock the gain in.",
            file=sys.stderr,
        )
        return 1
    if args.verbose:
        for line in failures:
            print(f"  (known miss) {line}")
    print(f"router corpus OK: {passed}/{total} passed (min_pass {min_pass}, {len(failures)} known miss(es))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
