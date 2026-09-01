#!/usr/bin/env python3
"""Every local JS technique needs a **value-level** golden in `selfcheck.mjs`. Ratcheted.

The lesson v0.33.1 paid for: *presence-level assertions are structurally blind to value regressions.*
"the section is in `section_titles_detected`" and "the snapshot is non-empty" both stayed green while
八字格局 reported 正官格 where the truth was 正财格, 铁板 collapsed 96 局 into 12, and canping put every
大运 on the wrong decade. Six layers of green, zero coverage of the numbers.

So a golden only counts here if it pins a **computed value** — a specific 格局 name, a specific
percentage, a specific 起运岁, a specific 三传 sequence — not a section header, a line count, or a
truthiness check. The scanner approximates that with three explicit assertion shapes (CJK literal /
numeric comparison / serialized-structure equality) — see `_is_value_level`. It is an approximation:
it can accept a weak golden that happens to mention a number. What it cannot do is accept a block
with no value assertion at all, which is the state every regressed technique was in.

Two rules:

1. Any tool named in `contracts/value_golden_debt.json`'s `covered` list must still have one.
2. A tool NOT in `covered` and not in `debt` is new — it must arrive with a golden.

`debt` is the pre-existing uncovered set (ratcheted: it may only shrink). Refresh with
`--update-baseline` after paying some down. Stdlib-only. Wired into CI.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
PKG_ROOT = SCRIPTS.parent
CORE_JS = PKG_ROOT / "horosa-core-js"
TOOLS_DIR = CORE_JS / "src" / "tools"
SELFCHECK = CORE_JS / "test" / "selfcheck.mjs"
BASELINE = PKG_ROOT / "contracts" / "value_golden_debt.json"

# A block counts as value-level when an `assert(...)` in it does one of three things — the three
# shapes the goldens are actually written in. Anything cleverer would be an unguarded heuristic:
#   1. compares against a CJK literal      → `=== '正财格'`, `includes('分布：木2.6%')`
#   2. compares against a number           → `=== 3`, `qiyunAge === firstDayunAge`
#   3. compares two serialized structures  → `JSON.stringify(a) === JSON.stringify([...])`
# A header-only check (`includes('[三传]')`) matches none of them: `[三传]` is bracketed, and the
# scanner strips bracketed section tokens before looking for CJK.
_SECTION_TOKEN_RE = re.compile(r"\[[^\]]*\]")
_ASSERT_RE = re.compile(r"assert\((.*?)\);", re.DOTALL)
_CJK_LITERAL_RE = re.compile(r"['\"][^'\"]*[\u4e00-\u9fff][^'\"]*['\"]")
_NUM_COMPARE_RE = re.compile(r"(?:===|!==|>=|<=)\s*-?\d")
_STRUCT_COMPARE_RE = re.compile(r"JSON\.stringify\(.*?\)\s*(?:===|!==)")


def _is_value_level(block: str) -> bool:
    for m in _ASSERT_RE.finditer(block):
        body = _SECTION_TOKEN_RE.sub("", m.group(1))
        if _CJK_LITERAL_RE.search(body) or _NUM_COMPARE_RE.search(body) or _STRUCT_COMPARE_RE.search(body):
            return True
    return False


def _check_blocks(text: str) -> list[str]:
    """Each top-level `check('name', …)` body, as raw text."""
    blocks: list[str] = []
    for m in re.finditer(r"check\(\s*['\"](.+?)['\"]\s*,", text):
        start = m.end()
        depth, i, opened = 0, start, False
        while i < len(text):
            if text[i] == "{":
                depth += 1
                opened = True
            elif text[i] == "}":
                depth -= 1
                if opened and depth == 0:
                    break
            i += 1
        blocks.append(m.group(1) + "\n" + text[start : i + 1])
    return blocks


def scan() -> tuple[set[str], set[str]]:
    """(tools with a value-level golden, all local tool names)."""
    text = SELFCHECK.read_text(encoding="utf-8")
    value_blocks = [b for b in _check_blocks(text) if _is_value_level(b)]
    # Also count the file's top-level `try { … }` golden blocks (zhengchuan/liureng use them).
    for m in re.finditer(r"\ntry \{(.*?)\n\} catch", text, re.DOTALL):
        if _is_value_level(m.group(1)):
            value_blocks.append(m.group(1))
    haystack = "\n".join(value_blocks)

    all_tools = {p.stem for p in TOOLS_DIR.glob("*.js") if p.stem not in {"index", "dispatch"}}
    covered = set()
    for tool in all_tools:
        # `runXiaoLiuRen` / `runBaziGeju` — the exported runner name, or the module name itself.
        camel = "run" + tool[0].upper() + tool[1:]
        if re.search(rf"(?<![\w$])({re.escape(camel)}|{re.escape(tool)})(?![\w$])", haystack, re.IGNORECASE):
            covered.add(tool)
    return covered, all_tools


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--update-baseline", action="store_true")
    args = ap.parse_args()

    covered, all_tools = scan()
    debt = sorted(all_tools - covered)

    if args.update_baseline:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(
            json.dumps(
                {
                    "_comment": (
                        "Value-golden ratchet. `covered` tools have an assertion in selfcheck.mjs that "
                        "pins a computed value (a 格局 name, a percentage, a 起运岁) — not a section "
                        "header. `debt` is the uncovered remainder and may only shrink; a NEW tool must "
                        "arrive with a golden. Expected values need an authority comment (upstream jest "
                        "golden / desktop same-chart / astronomical fact), per docs/LESSONS.md. "
                        "Refresh with `uv run python scripts/verify_value_goldens.py --update-baseline`."
                    ),
                    "covered": sorted(covered),
                    "debt": debt,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"baseline updated: {len(covered)} covered, {len(debt)} in debt")
        return 0

    if not BASELINE.is_file():
        print(f"missing {BASELINE.relative_to(PKG_ROOT)} — seed it with --update-baseline", file=sys.stderr)
        return 1

    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    base_covered = set(base.get("covered", []))
    base_debt = set(base.get("debt", []))
    errors: list[str] = []

    regressed = sorted(base_covered - covered)
    if regressed:
        errors.append(
            f"these tools lost their value-level golden: {regressed}. A golden that only checks "
            "section headers does not count — pin the computed value."
        )
    unknown = sorted(all_tools - base_covered - base_debt - covered)
    if unknown:
        errors.append(
            f"new tool(s) without a value-level golden: {unknown}. Add one to selfcheck.mjs pinning a "
            "computed value, with a comment naming where the expected value comes from."
        )
    paid = sorted(base_debt & covered)
    if paid:
        errors.append(
            f"debt paid down ({paid}) — run `uv run python scripts/verify_value_goldens.py "
            "--update-baseline` so the ratchet holds the gain."
        )

    if errors:
        print("value-golden ratchet FAILED:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(
        f"value-golden ratchet OK: {len(covered)}/{len(all_tools)} local JS tools pin a computed "
        f"value in selfcheck.mjs ({len(base_debt)} still in debt)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
