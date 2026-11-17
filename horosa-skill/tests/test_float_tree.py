"""tests/float_tree.py: cross-compiler last-bit noise passes, anything a reading could notice fails (v0.51.0 release matrix)."""
from __future__ import annotations

import math

import float_tree
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


# ── golden_diff / golden_text_*: value-level on POSIX, shape on Windows (v0.51.0 second matrix run) ───────────────────
# The Windows values below are what windows-latest returned in release run 44026495396 (pytest.log of the x64 lane).
MAC_ROWS = [{"end": "2025-06-11 00:38:42", "start": "2025-06-10 01:02:03", "lord": "Mars"},
            {"a": "Asc", "b": "Sun", "distance": 0.02581627415361254, "aspect": 0},
            {"a": "MC", "b": "Sun", "distance": 90.02581627415361, "aspect": 90}]
WIN_ROWS = [{"end": "2025-06-11 00:38:41", "start": "2025-06-10 01:02:03", "lord": "Mars"},
            {"a": "MC", "b": "Sun", "distance": 90.02581627415088, "aspect": 90},
            {"a": "Asc", "b": "Sun", "distance": 0.025816274150912477, "aspect": 0}]
MAC_TEXT = "[盘面细节]\n入世相位:上升 合 太阳 0.03°\n入世相位:天顶 刑 太阳 90.03°\n终:2025-06-11 00:38:42"
WIN_TEXT = "[盘面细节]\n入世相位:天顶 刑 太阳 90.03°\n入世相位:上升 合 太阳 0.03°\n终:2025-06-11 00:38:41"


def test_on_posix_the_golden_is_value_level(monkeypatch) -> None:
    monkeypatch.setattr(float_tree, "VALUE_GOLDEN_HOST", True)
    assert float_tree.golden_diff(WIN_ROWS, MAC_ROWS) != []           # a flipped second / swapped rows stay red where goldens are recorded
    assert float_tree.golden_text_diff(WIN_TEXT, MAC_TEXT) != []
    assert float_tree.golden_text_contains(WIN_TEXT, MAC_TEXT.splitlines()[-1]) != []
    assert float_tree.golden_diff(MAC_ROWS, MAC_ROWS) == [] and float_tree.golden_text_diff(MAC_TEXT, MAC_TEXT) == []


def test_on_windows_what_the_engine_drift_produces_passes(monkeypatch) -> None:
    monkeypatch.setattr(float_tree, "VALUE_GOLDEN_HOST", False)
    assert float_tree.golden_diff(WIN_ROWS, MAC_ROWS) == []
    assert float_tree.golden_text_diff(WIN_TEXT, MAC_TEXT) == []
    assert float_tree.golden_text_contains(WIN_TEXT, MAC_TEXT.splitlines()[-1]) == []


def test_on_windows_a_change_in_shape_or_wording_still_fails(monkeypatch) -> None:
    monkeypatch.setattr(float_tree, "VALUE_GOLDEN_HOST", False)
    assert float_tree.golden_diff(WIN_ROWS[:2], MAC_ROWS) == ["$: length 2 != 3"]
    assert float_tree.golden_diff([{**WIN_ROWS[0], "extra": 1}, *WIN_ROWS[1:]], MAC_ROWS) == ["$[0]: keys ['extra'] differ"]
    assert float_tree.golden_diff([{**WIN_ROWS[0], "lord": None}, *WIN_ROWS[1:]], MAC_ROWS) == ["$[0].lord: NoneType != str"]
    assert float_tree.golden_text_diff(WIN_TEXT.replace("刑", "冲"), MAC_TEXT) != []                  # a changed label
    assert float_tree.golden_text_diff(WIN_TEXT.rsplit("\n", 1)[0], MAC_TEXT) != []                   # a missing line
    assert float_tree.golden_text_contains(WIN_TEXT, "入世相位:下降 合 太阳 0.03°") == ["入世相位:下降 合 太阳 #.#°"]
