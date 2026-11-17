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
