"""知识检索的质量下限（ratchet）：scripts/eval_knowledge_search.py 跑出来的数不许掉。

下限是 2026-11-06 实测值略往下取整，只许往上调。dev 集是调参用的，分数偏乐观；heldout 在改检索之前写好，
只用来报数，不许按它调（contracts/knowledge_eval.json）。掉线先看是不是真退化，别顺手把下限改低。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location("eval_knowledge_search", Path(__file__).parents[1] / "scripts" / "eval_knowledge_search.py")
_EVAL = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_EVAL)

# 2026-11-06 实测（hit@1 / hit@5）：dev 0.932 / 1.0；第一批 heldout（已看过，改作 dev）0.846 / 0.974；
# 现行 heldout（偏难：复合词 + 问句）0.714 / 0.918；唯一名自检索 0.945；问句模板 0.883。
FLOORS = {"dev": {"hit1": 0.92, "hit5": 0.98}, "seen_2026_11_06": {"hit1": 0.83, "hit5": 0.95}, "heldout": {"hit1": 0.70, "hit5": 0.90}}
SELF_UNIQUE_HIT1_FLOOR = 0.93
SELF_QUESTION_HIT5_FLOOR = 0.87


@pytest.mark.parametrize("name", sorted(FLOORS))
def test_overall_quality_does_not_drop(name: str) -> None:
    overall = _EVAL.evaluate_set(name)["overall"]
    assert overall["hit1"] >= FLOORS[name]["hit1"] and overall["hit5"] >= FLOORS[name]["hit5"], overall


def test_every_entry_with_a_unique_name_is_found_by_it() -> None:
    assert _EVAL.evaluate_self_unique() >= SELF_UNIQUE_HIT1_FLOOR


def test_asking_about_an_entry_finds_it() -> None:
    """此前「X 是什么」这种问法全库命中率 0.016：连写的问句当成一个词，一条都搜不到。"""
    results = _EVAL.evaluate_self()
    for template, summary in results.items():
        if template != "<名>":
            assert summary["hit5"] >= SELF_QUESTION_HIT5_FLOOR, (template, summary)
