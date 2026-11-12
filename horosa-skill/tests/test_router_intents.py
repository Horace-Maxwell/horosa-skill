"""Dispatch routing by intent (v0.50.0-dev): the intent corpus, script-insensitive keywords, and no birth→chart fallback.

`contracts/dispatch_intent_corpus.json` pins what a user means for 200+ requests (Simplified, Traditional, English,
pinyin, full-width; with and without birth data). Before this, an unmatched query with birth data silently became a
Western natal chart (「我和他合不合」, 「明天适合搬家吗」, "transits this month"), 起一卦 became a gua lookup, generic
择日 an election chart for a moment nobody gave, and Traditional queries matched nothing at all.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from horosa_skill.engine import intents, router
from horosa_skill.engine.query_text import normalize_query
from horosa_skill.engine.router import route
from horosa_skill.errors import DispatchResolutionError
from horosa_skill.schemas.tools import DispatchInput
from horosa_skill.textscript import convert

PKG_ROOT = Path(__file__).resolve().parents[1]
CORPUS = json.loads((PKG_ROOT / "contracts" / "dispatch_intent_corpus.json").read_text(encoding="utf-8"))
BIRTH = {"date": "1990-05-03", "time": "08:00", "zone": "8", "lat": "31n13", "lon": "121e28"}


def _outcome(query: str, *, birth: bool) -> dict:
    request = DispatchInput(query=query, birth=BIRTH if birth else None)
    try:
        result = route(request)
    except DispatchResolutionError as exc:
        details = exc.details or {}
        return {
            "code": exc.code,
            "intent_class": details.get("intent_class"),
            "reason": details.get("reason"),
            "category": details.get("category"),
            "has_prompt": bool((details.get("agent_recovery") or {}).get("prompt_to_user")),
        }
    return {"tools": result.tools, "warn": bool(result.warnings)}


def _matches(expect: dict, got: dict) -> bool:
    if "tools" in expect:
        return got.get("tools") == expect["tools"] and got.get("warn") == bool(expect.get("warn"))
    if got.get("code") != expect["code"] or not got.get("has_prompt"):
        return False
    return all(got.get(key) == expect[key] for key in ("intent_class", "reason", "category") if key in expect)


def test_corpus_is_large_and_mixed() -> None:
    cases = CORPUS["cases"]
    assert len(cases) >= 150
    assert any(not case["birth"] for case in cases) and any(case["birth"] for case in cases)
    queries = [case["query"] for case in cases]
    assert any(re.search(r"[a-z]", q) and not re.search(r"[一-鿿]", q) for q in queries)  # English
    assert any(normalize_query(q) != q.lower() for q in queries)  # Traditional / full-width


def test_every_corpus_case_routes_as_the_user_means() -> None:
    misses = []
    for case in CORPUS["cases"]:
        got = _outcome(case["query"], birth=case["birth"])
        if not _matches(case["expect"], got):
            misses.append((case["query"], case["birth"], case["expect"], got))
    assert not misses, f"{len(misses)} misrouted: {misses[:10]}"


def test_birth_data_never_picks_the_technique() -> None:
    """同一句话带不带出生数据，路由结果一样（合盘的 inner/outer 例外：那是两个人的数据，见 intents）。"""
    for case in CORPUS["cases"]:
        assert _outcome(case["query"], birth=True) == _outcome(case["query"], birth=False), case["query"]


def _router_literals() -> list[str]:
    """router.py 里列表 / 元组中的全部字面量 + intents.py 的全部关键词表。"""
    words: list[str] = []
    tree = ast.parse(Path(router.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.List, ast.Tuple)):
            for item in node.elts:
                if isinstance(item, ast.Constant) and isinstance(item.value, str) and 1 <= len(item.value) <= 24:
                    words.append(item.value)
    for intent in (intents.RELATIONSHIP, intents.DATE_SELECTION, intents.LIFE_TIMING, intents.DIVINATION, intents.NATAL_CHOICE):
        words.extend(intent.words)
    for table in (intents.SOLAR_TERM_NAMES, intents.NATAL_WESTERN_WORDS, intents.NATAL_WESTERN_INFERRED,
                  intents.BAZI_WORDS, intents.MATCHING_WORDS, intents.LIFE_TIMING_STRONG):
        words.extend(table)
    for table, _zh, _en in intents.OUT_OF_SCOPE.values():
        words.extend(table)
    return words


def test_every_routing_keyword_is_already_in_normal_form() -> None:
    """路由在归一后的文本上匹配：表里写了繁体 / 全角 / 大写的词永远匹配不到。"""
    bad = [w for w in _router_literals() if re.search(r"[一-鿿A-Za-z]", w) and normalize_query(w) != w.strip()]
    assert not bad, bad


@pytest.mark.parametrize("variant", ["traditional", "fullwidth", "upper"])
def test_routing_is_script_and_width_insensitive(variant: str) -> None:
    """每个语料句换成繁体 / 全角 / 大写，路由结果不变（去掉 normalize_query 的任何一步就红）。"""

    def transform(text: str) -> str:
        if variant == "traditional":
            return convert(text, "zh-Hant")
        if variant == "fullwidth":
            return "".join(chr(ord(ch) + 0xFEE0) if "!" <= ch <= "~" else ch for ch in text)
        return text.upper()

    changed = 0
    for case in CORPUS["cases"]:
        query = case["query"]
        if re.search(r"\b[A-Z]{2,5}\b", query):  # 股票代码靠原文大写识别，不参与大小写变体
            continue
        variant_query = transform(query)
        if variant_query == query:
            continue
        changed += 1
        assert _outcome(variant_query, birth=True) == _outcome(query, birth=True), (query, variant_query)
    assert changed > 50


def test_choice_refusals_name_techniques_for_humans() -> None:
    got = None
    try:
        route(DispatchInput(query="他喜欢我吗"))
    except DispatchResolutionError as exc:
        got = exc
    assert got is not None and got.code == intents.CODE_CHOICE
    recovery = got.details["agent_recovery"]
    assert " / " in recovery["prompt_to_user"]  # bilingual
    question = recovery["ask_if_missing"][0]
    assert question["values"] == got.details["candidates"]
    assert "六爻" in question["options"] and "sixyao" not in question["options"]
    assert "include_all" not in got.details["hint"]
