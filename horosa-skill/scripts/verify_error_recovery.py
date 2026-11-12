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

Rule 3 (hard, A-5 / C-13): no error code is built with an f-string (`code=f"tool.{tool}_…"`). Such codes were
invisible to rule 1 and two families (`inverted_window`, `span_too_large`) classified to nothing, so their envelopes
had no agent_recovery. Per-technique codes go through `errors.tool_code(tool, "<family>")` /
`errors.engine_tool_code(...)`, whose families live in `errors.TOOL_CODE_FAMILIES` (and are checked like codes).
At runtime, `HorosaSkillError` refuses an unclassifiable code raised from package code under pytest.

Rule 4 (ratchet): every code and family is exercised by at least one test (its spelling appears under `tests/`),
or is listed in `contracts/error_code_test_debt.json`, which may only shrink. A guard nothing exercises is the
C-18 failure mode: it cannot go red.
Stdlib + the package. Wired into CI.
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
SRC = PKG_ROOT / "src" / "horosa_skill"
BASELINE = PKG_ROOT / "contracts" / "error_recovery_debt.json"
TEST_DEBT = PKG_ROOT / "contracts" / "error_code_test_debt.json"
TESTS = PKG_ROOT / "tests"
sys.path.insert(0, str(PKG_ROOT / "src"))

_CODE_RE = re.compile(r'code="([a-z_.]+)"')


def dynamic_code_sites(src: Path = SRC) -> list[str]:
    """`code=f"…"` keyword arguments: codes nobody can read off the source."""
    sites: list[str] = []
    for py in sorted(src.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == "code" and isinstance(node.value, ast.JoinedStr):
                sites.append(f"{py.relative_to(src).as_posix()}:{node.value.lineno}")
    return sites


def collect_families(src: Path = SRC) -> dict[str, list[str]]:
    """Literal families passed to `tool_code(tool, "<family>")` / `engine_tool_code(tool, engine_code, "<default>")`."""
    found: dict[str, list[str]] = {}
    for py in sorted(src.rglob("*.py")):
        for node in ast.walk(ast.parse(py.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name in {"tool_code", "engine_tool_code"} and node.args:
                last = node.args[-1]
                if isinstance(last, ast.Constant) and isinstance(last.value, str):
                    found.setdefault(last.value, []).append(py.relative_to(src).as_posix())
    return found


def untested(codes: dict[str, list[str]], families: dict[str, list[str]], tests: Path = TESTS) -> list[str]:
    """Codes / families whose spelling appears in no test file (`family:<name>` for families)."""
    corpus = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in sorted(tests.rglob("*.py")))
    missing = [code for code in codes if code not in corpus]
    missing += [f"family:{family}" for family in families
                if not re.search(rf"tool\.[a-z0-9_]+_{re.escape(family)}\b|\"{re.escape(family)}\"", corpus)]
    return sorted(missing)


def check_registry(src: Path = SRC, tests: Path = TESTS, debt: list[str] | None = None) -> list[str]:
    """Rules 1, 3, 4 (the hard and ratchet parts that do not depend on the bilingual baseline)."""
    from horosa_skill.errors import TOOL_CODE_FAMILIES, classify_code

    errors: list[str] = []
    codes = collect_codes(src)
    unclassified = sorted(code for code in codes if classify_code(code)[0] is None)
    if unclassified:
        errors.append(
            "error codes with no recovery rule (add to errors.RECOVERY_TABLE or use a classifiable suffix): "
            + ", ".join(f"{c} ({codes[c][0]})" for c in unclassified)
        )
    dynamic = dynamic_code_sites(src)
    if dynamic:
        errors.append("error codes built with f-strings (use errors.tool_code / engine_tool_code): " + ", ".join(dynamic))
    families = collect_families(src)
    unknown_families = sorted(f for f in families if f not in TOOL_CODE_FAMILIES)
    if unknown_families:
        errors.append("tool_code families not registered in errors.TOOL_CODE_FAMILIES: " + ", ".join(unknown_families))
    debt_set = set(debt or [])
    missing = untested(codes, families, tests)
    new_debt = [item for item in missing if item not in debt_set]
    if new_debt:
        errors.append(
            "error codes no test exercises (write a test that produces / asserts each one): " + ", ".join(new_debt)
        )
    paid = sorted(debt_set - set(missing))
    if paid:
        errors.append(
            f"{len(paid)} code(s) in {TEST_DEBT.name} are tested now — remove them (the debt only shrinks): " + ", ".join(paid)
        )
    return errors
_CJK = re.compile(r"[一-鿿]")
_LATIN = re.compile(r"[A-Za-z]{3,}")


def collect_codes(src: Path = SRC) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for py in sorted(src.rglob("*.py")):
        for code in _CODE_RE.findall(py.read_text(encoding="utf-8")):
            found.setdefault(code, []).append(py.relative_to(src).as_posix())
    return found


def load_test_debt() -> list[str]:
    if not TEST_DEBT.is_file():
        return []
    return list(json.loads(TEST_DEBT.read_text(encoding="utf-8")).get("untested") or [])


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
    ap.add_argument("--seed-test-debt", action="store_true",
                    help="write the current untested codes into contracts/error_code_test_debt.json (first run only)")
    args = ap.parse_args()

    from horosa_skill.errors import classify_code

    codes = collect_codes()
    unclassified = sorted(code for code in codes if classify_code(code)[0] is None)
    per_file = non_bilingual_sites()
    total = sum(per_file.values())
    if args.seed_test_debt:
        if TEST_DEBT.is_file():
            print(f"{TEST_DEBT.name} exists; it only shrinks — edit it by hand when a code gets its test", file=sys.stderr)
            return 1
        missing = untested(codes, collect_families())
        TEST_DEBT.write_text(json.dumps({
            "_comment": ("Error codes / tool_code families that no test exercises yet (C-18). May only shrink: "
                         "scripts/verify_error_recovery.py fails when a new untested code appears or a listed one gets a test."),
            "untested": missing,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"seeded {len(missing)} untested code(s)")
        return 0

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
            encoding="utf-8", newline="\n",
        )
        print(f"baseline updated: {total} non-bilingual message(s), {len(codes)} codes seen")
        if unclassified:
            print(f"  (still unclassified codes: {unclassified})")
        return 0

    errors: list[str] = check_registry(debt=load_test_debt())
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
