"""纬度「度分 + 尾随 S」不许读成北纬（审计 F01，P0：悉尼的人拿到北半球的盘）。

根因：`_COORD_DMS_RE` 的秒单位分支在 IGNORECASE 下把尾随的 `S`（南）当成「秒」的单位吃掉，哪怕前面没有秒的数字。
修：秒单位只能跟在秒的数字后面，且不再收裸字母 `s`。期望值是手算的十进制度（33°52′ = 33.8667°）。

负向对照（实跑过）：把 `_COORD_DMS_RE` 换回旧正则 → 南纬的 6 种写法全部变正（北纬），本用例红。
"""
from __future__ import annotations

import pytest

from horosa_skill.input_fields import parse_coordinate

SOUTH = ["33°52′S", "33°52'S", "33° 52′ S", "33 52 S", "33d52mS", "33:52 S", "33°52′34″S", "33° 52' 34\" S", "S33°52′"]
UNCHANGED = {
    "33°S": -33.0, "33.87S": -33.87, "31°13′N": 31 + 13 / 60, "31°13′48″N": 31 + 13 / 60 + 48 / 3600, "31:13:48": 31 + 13 / 60 + 48 / 3600,
    "31 13 N": 31 + 13 / 60, "31d13m": 31 + 13 / 60, "31度13分": 31 + 13 / 60, "31度13分48秒": 31 + 13 / 60 + 48 / 3600,
}


def _value(parsed) -> float:
    return float(getattr(parsed, "value", parsed))


@pytest.mark.parametrize("text", SOUTH)
def test_trailing_or_leading_s_is_south(text: str) -> None:
    got = _value(parse_coordinate(text, axis="lat"))
    expected = 33 + 52 / 60 + (34 / 3600 if "34" in text else 0)
    assert got == pytest.approx(-expected, abs=1e-6), text


@pytest.mark.parametrize("text,expected", sorted(UNCHANGED.items()))
def test_other_spellings_read_as_before(text: str, expected: float) -> None:
    assert _value(parse_coordinate(text, axis="lat")) == pytest.approx(expected, abs=1e-6)


@pytest.mark.parametrize("text,expected", [("74°00′W", -74.0), ("151°12′E", 151.2), ("58°24′W", -58.4)])
def test_longitude_hemispheres(text: str, expected: float) -> None:
    assert _value(parse_coordinate(text, axis="lon")) == pytest.approx(expected, abs=1e-6)
