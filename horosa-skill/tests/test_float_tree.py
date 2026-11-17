"""tests/float_tree.py: cross-compiler last-bit noise passes, anything a reading could notice fails (v0.51.0 release matrix)."""
from __future__ import annotations

import math

from float_tree import float_tree_diff

# The shape of the transform-chart golden that failed on both Windows lanes (`vertical/improved`).
GOLDEN = {"vertical": [{"id": "Sun", "outside": False, "declination": -14.22525924262729,
                        "first": 321.85064526744065, "second": 218.14935473255935}],
          "rows": [[1, "Venus", 360.0], [2, "Mars", 129.0]], "target": None}


def _nudged(ulps: int) -> dict:
    tree = {"vertical": [dict(GOLDEN["vertical"][0])], "rows": [list(r) for r in GOLDEN["rows"]], "target": None}
    first = tree["vertical"][0]["first"]
    for _ in range(ulps):
        first = math.nextafter(first, math.inf)
    tree["vertical"][0]["first"] = first
    return tree


def test_last_bit_noise_between_compilers_is_equal() -> None:
    noisy = _nudged(4)
    assert noisy != GOLDEN                       # the old `==` comparison fails on this (what the Windows lanes hit)
    assert float_tree_diff(noisy, GOLDEN) == []


def test_a_change_a_reading_could_notice_is_reported_with_its_path() -> None:
    moved = _nudged(0)
    moved["vertical"][0]["declination"] += 1e-5
    [diff] = float_tree_diff(moved, GOLDEN)
    assert diff.startswith("$.vertical[0].declination: ") and diff.endswith("(Δ=1e-05)")


def test_shape_strings_bools_and_none_stay_exact() -> None:
    assert float_tree_diff({**GOLDEN, "extra": 1}, GOLDEN) == ["$: keys ['extra'] differ"]
    assert float_tree_diff({**GOLDEN, "rows": GOLDEN["rows"][:1]}, GOLDEN) == ["$.rows: length 1 != 2"]
    assert float_tree_diff({**GOLDEN, "rows": [[1, "Venus", 360.0], [2, "Saturn", 129.0]]}, GOLDEN) == ["$.rows[1][1]: 'Saturn' != 'Mars'"]
    flipped = _nudged(0)
    flipped["vertical"][0]["outside"] = True
    assert float_tree_diff(flipped, GOLDEN) == ["$.vertical[0].outside: True != False"]
    assert float_tree_diff({**GOLDEN, "target": 0}, GOLDEN) == ["$.target: 0 != None"]
    assert float_tree_diff({**GOLDEN, "rows": [[True, "Venus", 360.0], [2, "Mars", 129.0]]}, GOLDEN) == ["$.rows[0][0]: True != 1"]


def test_int_and_float_compare_by_value() -> None:
    assert float_tree_diff({**GOLDEN, "rows": [[1, "Venus", 360], [2, "Mars", 129]]}, GOLDEN) == []
