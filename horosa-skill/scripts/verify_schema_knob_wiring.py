#!/usr/bin/env python3
"""Every declared Input-schema field must have a consumer somewhere. Ratcheted.

A schema field is a promise to the agent: "pass this and it changes the result." v0.33.1 found
fifteen fields that kept that promise nowhere — 11 on `ElectionInput` (whose own comment cited
`electionParams.js`'s 13 keys while the fields below it matched **none** of them), 4 on
`HoraryInput` (two of which, `receptionMode`/`almutenScheme`, are names that exist in no engine
vocabulary at all), plus `zuoShan`, which upstream had already deleted as a "double ghost". They
were documented, described, and inert across three releases: the agent reads the description,
passes the knob, and the output silently ignores it while looking exactly as authoritative.

The check is deliberately blunt — a field is "wired" if its name appears anywhere outside the
schema module: `service.py`, a JS tool, a vendored engine, or the guidance/registry layers. That
over-accepts (a mention is not proof of consumption) but never over-rejects, which is the right
bias for a guard that gates every schema edit. Value-level proof is `selfcheck.mjs`'s job.

**One deliberate blind spot, and why the baseline is not empty**: fields forwarded verbatim to the
remote backend (`/chart`, `/india/*`, the ken endpoints) are consumed by name *in the upstream
astropy source*, which is not in this repo and is not on CI. They therefore appear "unwired" here
while being perfectly live. The seeded baseline is exactly that set — every one of its 25 entries
was checked by hand against the upstream tree before being baselined (e.g. `pdProjection` →
`perchart.py:821`). So the baseline means "verified live via the backend", not "known broken", and
a NEW name still fails: the promise this guard actually enforces is that nobody adds a field
without pointing at its consumer.

Baseline in `contracts/schema_knob_debt.json`; refresh with `--update-baseline` after wiring or
deleting a knob. Stdlib-only. Wired into CI.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
PKG_ROOT = SCRIPTS.parent
SCHEMA_FILE = PKG_ROOT / "src" / "horosa_skill" / "schemas" / "tools.py"
BASELINE = PKG_ROOT / "contracts" / "schema_knob_debt.json"

SEARCH_ROOTS = (
    PKG_ROOT / "src" / "horosa_skill",
    PKG_ROOT / "horosa-core-js" / "src",
)
SEARCH_SUFFIXES = (".py", ".js", ".mjs")

# Fields whose consumption is structural rather than by-name: they are read via `**payload`
# forwarding, by the transport layer, or by pydantic itself. Listing them here is cheaper and
# far more honest than teaching the scanner to model every passthrough.
STRUCTURAL_FIELDS = frozenset(
    {
        "date", "time", "zone", "lat", "lon", "ad", "options", "chart", "predictive", "tradition",
    }
)


def _declared_fields() -> dict[str, list[str]]:
    tree = ast.parse(SCHEMA_FILE.read_text(encoding="utf-8"))
    out: dict[str, list[str]] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        names = [
            stmt.target.id
            for stmt in node.body
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
        ]
        if names:
            out[node.name] = names
    return out


def _haystack() -> str:
    parts: list[str] = []
    for root in SEARCH_ROOTS:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.suffix not in SEARCH_SUFFIXES or path == SCHEMA_FILE:
                continue
            if "__pycache__" in path.parts or "node_modules" in path.parts:
                continue
            parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def scan() -> list[str]:
    haystack = _haystack()
    dead: list[str] = []
    for cls, fields in sorted(_declared_fields().items()):
        for field in fields:
            if field in STRUCTURAL_FIELDS:
                continue
            if field in haystack:
                continue
            dead.append(f"{cls}.{field}")
    return dead


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--update-baseline", action="store_true")
    args = ap.parse_args()

    dead = scan()
    if args.update_baseline:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(
            json.dumps(
                {
                    "_comment": (
                        "Fields with no consumer inside this repo. The seeded set is verified-live-via-"
                        "backend: each is forwarded verbatim to the upstream astropy/ken endpoints and "
                        "read there by name (checked by hand against the upstream tree — e.g. "
                        "pdProjection -> perchart.py:821). A NEW entry is not automatically that; "
                        "point at the consumer before baselining it, or the guard degrades into a "
                        "dumping ground. Refresh with "
                        "`uv run python scripts/verify_schema_knob_wiring.py --update-baseline`."
                    ),
                    "unwired": dead,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"baseline updated: {len(dead)} unwired schema knob(s)")
        return 0

    allowed = set(json.loads(BASELINE.read_text(encoding="utf-8")).get("unwired", [])) if BASELINE.is_file() else set()
    new = sorted(set(dead) - allowed)
    fixed = sorted(allowed - set(dead))

    if new:
        print("schema-knob-wiring guard FAILED — these declared fields have no consumer:", file=sys.stderr)
        for name in new:
            print(f"  - {name}", file=sys.stderr)
        print(
            "\nWire it (service.py forwarding + the engine that reads it), or delete the field. "
            "A documented knob that does nothing is worse than a missing one: the agent will pass "
            "it, read the confident output, and never learn it was ignored.",
            file=sys.stderr,
        )
        return 1
    if fixed:
        print(
            f"schema-knob debt dropped by {len(fixed)} ({', '.join(fixed)}). Run "
            "`uv run python scripts/verify_schema_knob_wiring.py --update-baseline` to lock it in.",
            file=sys.stderr,
        )
        return 1

    print(f"schema-knob-wiring OK: every declared field has a consumer ({len(allowed)} baselined exception(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
