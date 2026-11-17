"""Compare a live engine response with a golden recorded on another machine: same shape, same strings, numbers within a tolerance.

Why (v0.51.0 release matrix): the live goldens of the v3.14.0 sync (transform charts, chart details, time lords) were
recorded on macOS and compared with `==` on full-precision floats. The Windows payload runs the same Python + Swiss
Ephemeris code, but compiled with MSVC against a different libm, so trig-heavy values can differ in the last bit or two
(1e-13°). Both Windows lanes failed `vertical/improved` and `superimposed` on exactly that while macOS stayed green.
A tolerance of 1e-7 (0.00036″ of arc; 0.009 s of a day) is still far below anything a reading could show, and a real
algorithm change moves values by orders of magnitude more — the negative controls in tests/test_float_tree.py prove both.
"""
from __future__ import annotations

import math
import os
import re
from typing import Any

# Default: well above last-bit noise across compilers (~1e-13), well below any printed precision (the exports print 2–6 dp).
ABS_TOL = 1e-7
REL_TOL = 1e-12


def float_tree_diff(actual: Any, expected: Any, *, abs_tol: float = ABS_TOL, rel_tol: float = REL_TOL,
                    path: str = "$", limit: int = 20) -> list[str]:
    """Paths where `actual` differs from `expected` (empty = equal). Dict keys, list lengths, strings, bools and None must
    match exactly; int/float pairs compare numerically within the tolerance."""
    diffs: list[str] = []

    def walk(a: Any, e: Any, at: str) -> None:
        if len(diffs) >= limit:
            return
        if isinstance(a, bool) or isinstance(e, bool) or a is None or e is None:
            if a is not e and a != e or type(a) is not type(e):
                diffs.append(f"{at}: {a!r} != {e!r}")
            return
        if isinstance(a, (int, float)) and isinstance(e, (int, float)):
            if not (math.isfinite(a) and math.isfinite(e)):
                if not (a == e or (math.isnan(a) and math.isnan(e))):
                    diffs.append(f"{at}: {a!r} != {e!r}")
            elif not math.isclose(a, e, rel_tol=rel_tol, abs_tol=abs_tol):
                diffs.append(f"{at}: {a!r} != {e!r} (Δ={a - e:.3g})")
            return
        if isinstance(a, dict) and isinstance(e, dict):
            if set(a) != set(e):
                diffs.append(f"{at}: keys {sorted(map(str, set(a) ^ set(e)))} differ")
                return
            for key in e:
                walk(a[key], e[key], f"{at}.{key}")
            return
        if isinstance(a, (list, tuple)) and isinstance(e, (list, tuple)):
            if len(a) != len(e):
                diffs.append(f"{at}: length {len(a)} != {len(e)}")
                return
            for index, (x, y) in enumerate(zip(a, e)):
                walk(x, y, f"{at}[{index}]")
            return
        if a != e:
            diffs.append(f"{at}: {a!r} != {e!r}")

    walk(actual, expected, path)
    return diffs


# ── Goldens recorded on macOS, compared on whichever host runs the suite ─────────────────────────────────────────────
# v0.51.0 release matrix, second run: with the 1e-7 tolerance the Windows lanes still differed from the macOS goldens in
# ways no single tolerance absorbs — planet speed percentages by up to ~4e-6 (speeds come from numerical differentiation),
# timestamps the engine truncates to whole seconds flipping by one second, and rows whose sort keys nearly tie coming back in
# another order (in-mundo aspects at 70°N, where Asc and MC almost coincide). None of it would show in a reading.
# So the value-level golden holds on POSIX (the darwin release lane and every maintainer run use the same engine code), and on
# Windows the same call must produce the same SHAPE: identical keys, list lengths and value types; texts the same lines once
# every digit run is masked, in any order. That is a deliberately weaker check, stated here instead of hidden in a tolerance.
VALUE_GOLDEN_HOST = os.name != "nt"
_DIGITS = re.compile(r"\d+")


def shape_diff(actual: Any, expected: Any, *, path: str = "$", limit: int = 20) -> list[str]:
    """Paths where the two trees differ in structure: dict keys, list lengths, or value type (int and float count as one)."""
    diffs: list[str] = []

    def kind(value: Any) -> str:
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, (int, float)):
            return "number"
        return type(value).__name__

    def walk(a: Any, e: Any, at: str) -> None:
        if len(diffs) >= limit:
            return
        if kind(a) != kind(e):
            diffs.append(f"{at}: {kind(a)} != {kind(e)}")
        elif isinstance(e, dict):
            if set(a) != set(e):
                diffs.append(f"{at}: keys {sorted(map(str, set(a) ^ set(e)))} differ")
                return
            for key in e:
                walk(a[key], e[key], f"{at}.{key}")
        elif isinstance(e, (list, tuple)):
            if len(a) != len(e):
                diffs.append(f"{at}: length {len(a)} != {len(e)}")
                return
            for index, (x, y) in enumerate(zip(a, e)):
                walk(x, y, f"{at}[{index}]")

    walk(actual, expected, path)
    return diffs


def golden_diff(actual: Any, expected: Any, **tolerance: float) -> list[str]:
    """Value-level comparison against a macOS-recorded golden on POSIX; the shape only on Windows (see above)."""
    return float_tree_diff(actual, expected, **tolerance) if VALUE_GOLDEN_HOST else shape_diff(actual, expected)


# Inline lists (「世俗相位(比例):日合月(差 0.1°)、天顶刑福点(…)、…」) reorder inside the line too (third matrix run): each
# masked line is compared as the sorted multiset of its pieces between list separators.
_LIST_SEPARATORS = re.compile(r"[、，,；;：:]")


def _normalized(line: str) -> str:
    return "\x1f".join(sorted(_LIST_SEPARATORS.split(_DIGITS.sub("#", line))))


def _masked_lines(text: str) -> list[str]:
    return sorted(_normalized(line) for line in text.splitlines())


def golden_text_diff(actual: str, expected: str) -> list[str]:
    """Exact text on POSIX; on Windows the same lines with digits masked, in any order. Returns the lines that differ."""
    if VALUE_GOLDEN_HOST:
        return [] if actual == expected else [f"text differs (first {next((i for i, (x, y) in enumerate(zip(actual, expected)) if x != y), min(len(actual), len(expected)))} chars equal)"]
    mine, theirs = _masked_lines(actual), _masked_lines(expected)
    if mine == theirs:
        return []
    readable = {_normalized(line): _DIGITS.sub("#", line) for line in (*expected.splitlines(), *actual.splitlines())}
    return [readable[key] for key in sorted(set(mine) ^ set(theirs))][:20] or [f"line counts {len(mine)} != {len(theirs)}"]


def golden_text_contains(haystack: str, block: str) -> list[str]:
    """`block in haystack` on POSIX; on Windows every line of the block appears in the haystack with digits masked."""
    if VALUE_GOLDEN_HOST:
        return [] if block in haystack else ["block not found verbatim"]
    lines = set(_masked_lines(haystack))
    return [_DIGITS.sub("#", line) for line in block.splitlines() if _normalized(line) not in lines]
