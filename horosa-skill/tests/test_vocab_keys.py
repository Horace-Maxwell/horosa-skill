"""词表键不许让两个不同的数撞成一个键（v0.50.0 深审余项）。

`input_fields._vocab_key` 曾一律去掉「-」和「.」：'-1' 与 '1' 同键（纪元 ad 因此只能绕开 Vocabulary 另写 parse_era），
'1.0' 与 '10' 同键（一宫 7 / 10 年的 dayunLength 会把 1.0 读成 10）。现在数字字面量按数值写成规范串，其余照旧不敏感。
另：词表字段的 BeforeValidator 体只有一份（input_fields.parse_with），cn_vocab / western_vocab 不再各写一份。

负向对照（实跑过）：`_vocab_key` 改回整串去「-」「.」→ 撞键用例、ad 用例、dayunLength 用例红；在 western_vocab 里再定义一个
parse_with → 单一定义用例红。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from horosa_skill.cn_vocab import CN_VOCABULARIES
from horosa_skill.input_fields import FieldIssue, Vocabulary, _vocab_key, parse_era

SRC = Path(__file__).resolve().parents[1] / "src" / "horosa_skill"

NUMERALS = ["-1", "1", "+1", "1.0", "10", "-10", "0", "1.5", "15", "0.5", "05", "-1.0", "7", "70"]


def test_numerals_key_by_value_never_by_spelling() -> None:
    by_value: dict[float, set[str]] = {}
    for text in NUMERALS:
        by_value.setdefault(float(text), set()).add(_vocab_key(text))
    for value, keys in by_value.items():
        assert len(keys) == 1, f"{value}: 同一个数有多个键 {keys}"
    flat = [next(iter(keys)) for keys in by_value.values()]
    assert len(flat) == len(set(flat)), f"不同的数撞成同一个键：{sorted(flat)}"


def test_signed_choices_stay_apart() -> None:
    vocab = Vocabulary("ad", {1: ("公元",), -1: ("公元前",)})
    assert vocab.parse("-1").value == -1
    assert vocab.parse("1").value == 1
    assert vocab.parse("+1").value == 1
    with pytest.raises(FieldIssue):
        vocab.parse("-2")


def test_decimal_point_does_not_glue_digits() -> None:
    dayun = CN_VOCABULARIES["yizhangjing"]["dayunLength"]
    assert dayun.parse("10").value == 10
    assert dayun.parse("7").value == 7
    with pytest.raises(FieldIssue):
        dayun.parse("1.0")  # 1.0 年不是 10 年


def test_words_are_still_separator_insensitive() -> None:
    assert _vocab_key("Whole-Sign") == _vocab_key("whole sign") == _vocab_key("whole_sign")
    assert _vocab_key("a.d.") == _vocab_key("AD")


@pytest.mark.parametrize("value, expected", [("-1", -1), ("−1", -1), ("1", 1), ("+1", 1), ("BC", -1), ("a.d.", 1), (-1, -1), (1.0, 1)])
def test_era_runs_on_the_shared_vocabulary(value, expected) -> None:
    assert parse_era(value).value == expected


def test_one_parse_with_definition() -> None:
    owners = []
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        owners += [f"{path.relative_to(SRC)}" for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "parse_with"]
    assert owners == ["input_fields.py"], owners
