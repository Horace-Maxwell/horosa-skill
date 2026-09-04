"""v0.36.0 B2 — every technique must be findable: synonyms for all tools, a routing rule for each
technique, and the zh+en corpus ratchet (`contracts/router_corpus.json`)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.engine.router import _CANDIDATE_POOL, _suggest_candidates, select_tools
from horosa_skill.engine.synonyms import TOOL_SYNONYMS, aka_line, synonym_scores
from horosa_skill.errors import DispatchResolutionError
from horosa_skill.schemas.tools import DispatchInput

PKG_ROOT = Path(__file__).resolve().parents[1]
ROUTER_SRC = (PKG_ROOT / "src/horosa_skill/engine/router.py").read_text(encoding="utf-8")
CORPUS = json.loads((PKG_ROOT / "contracts/router_corpus.json").read_text(encoding="utf-8"))
NON_TECHNIQUE_DOMAINS = {"export", "knowledge", "memory", "report"}
# 查询层/派生层工具，靠 dispatch 关键词到达没有意义（agent 直呼或经 guidance 发现）。
ROUTING_EXEMPT = {"xuanshi"}


def test_synonym_table_covers_exactly_the_registry() -> None:
    assert set(TOOL_SYNONYMS) == set(TOOL_DEFINITIONS)
    for name, words in TOOL_SYNONYMS.items():
        assert len(words) >= 2, name
        assert any(re.search(r"[A-Za-z]", w) for w in words), f"{name}: needs an English/pinyin synonym"


def test_every_technique_tool_has_a_routing_rule_or_is_exempt() -> None:
    ruled = set(re.findall(r'add\("([a-z_0-9]+)"\)', ROUTER_SRC)) | set(re.findall(r'"([a-z_0-9]+)": \[', ROUTER_SRC))
    missing = [
        name
        for name, definition in TOOL_DEFINITIONS.items()
        if definition.domain not in NON_TECHNIQUE_DOMAINS and name not in ruled and name not in ROUTING_EXEMPT
    ]
    assert missing == [], f"technique tools with no dispatch rule (add one or list it in ROUTING_EXEMPT): {missing}"
    # 豁免表不许藏已经有规则的工具
    assert not (ROUTING_EXEMPT & ruled), ROUTING_EXEMPT & ruled


def test_router_corpus_meets_the_ratchet() -> None:
    passed = 0
    misses = []
    for case in CORPUS["cases"]:
        try:
            got = select_tools(DispatchInput(query=case["query"]))
        except DispatchResolutionError:
            got = []
        if got == list(case["expect"]):
            passed += 1
        else:
            misses.append((case["query"], case["expect"], got))
    assert passed >= int(CORPUS["min_pass"]), f"corpus regressed to {passed}/{len(CORPUS['cases'])}: {misses[:8]}"


@pytest.mark.parametrize(
    "query, expect",
    [
        ("vedic chart with lahiri", ["india_chart"]),
        ("vedic progression next year", ["vedicprog"]),
        ("八字择日开业", ["bazizeri"]),
        ("紫微择时开张", ["ziweizeri"]),
        ("六壬择日结婚", ["liurengzeri"]),
        ("通书择日吉日", ["huanglizeri"]),
        ("紫微斗数规则库", ["ziwei_rules"]),
        ("本月万年历", ["calendar_month"]),
        ("今天老黄历宜忌", ["huangli"]),
    ],
)
def test_new_rules_are_mutually_exclusive_with_their_base_technique(query: str, expect: list[str]) -> None:
    assert select_tools(DispatchInput(query=query)) == expect


def test_candidates_come_from_synonyms_before_the_static_pool() -> None:
    assert _suggest_candidates("draconic something unknown")[0] == "draconic"
    assert _suggest_candidates("muhurta wedding")[0] == "indiazeri"
    # 零命中时回落常用池顺序
    assert _suggest_candidates("zzz")[: len(_CANDIDATE_POOL[:3])] == [name for name, _ in _CANDIDATE_POOL[:3]]
    assert synonym_scores("purple star")[0][1] == "ziwei_birth"


def test_aka_line_is_short_and_skips_the_tool_name() -> None:
    line = aka_line("chart")
    assert line.startswith("aka: ") and "chart" not in line.split("aka: ")[1].split(", ")[0]
    assert len(aka_line("qimen").encode("utf-8")) < 120
