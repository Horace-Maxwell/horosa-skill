"""问句改写与排序（2026-11-11 深审 K-1 / K-2 / K-3）。

K-1：「八字里的用神怎么选」此前改写成「字里 用神 八 选」——切词只看「语料里连着出现过没有」，「八 / 字里」与「八字 / 里」同价。
现在按语料自己的词表切（条目名、小节名、加粗词），虚词几乎不算代价，孤立的单字丢掉；语料在 contracts/knowledge_question_rewrite.json。
K-2：裸词时讲界面的手册页与一行口诀往后放；领域词只加权不计分；多个词时全含的在前，没有全含的就说出来。
K-3：英文术语按语料自己的中英对照换成中文；零命中给近似词，并说明语料是中文写的。
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

from horosa_skill.knowledge import retrieval, store

ROOT = Path(__file__).resolve().parents[1]
REWRITES = json.loads((ROOT / "contracts" / "knowledge_question_rewrite.json").read_text(encoding="utf-8"))["cases"]


def test_the_question_corpus_is_big_and_covers_both_scripts_and_english() -> None:
    langs = [case["lang"] for case in REWRITES]
    assert len(REWRITES) >= 100 and langs.count("zh-Hant") >= 20 and langs.count("en") >= 5


@pytest.mark.parametrize("case", REWRITES, ids=lambda case: case["q"])
def test_a_question_is_rewritten_to_the_terms_it_asks_about(case: dict) -> None:
    got = store.rewrite_query(case["q"]) or case["q"]
    assert set(got.split()) in [set(terms) for terms in case["expect"]], got


def test_the_reported_segmentation_is_fixed_and_leftover_single_characters_are_dropped() -> None:
    result = store.search_knowledge({"query": "八字里的用神怎么选", "limit": 3})
    assert result["expanded_query"] == "八字 用神"
    assert (result["matches"][0]["domain"], result["matches"][0]["key"]) == ("bazi", "格局用神")
    # 连着两个以上没落在词上的字仍作弱线索（已记录的取舍：「塔罗怎么读牌」→「塔罗 读 牌」）
    assert store.search_knowledge({"query": "塔罗怎么读牌"})["expanded_query"] == "塔罗 读 牌"


def test_without_a_vocabulary_the_segmenter_behaves_as_before() -> None:
    corpus = {"八字", "字里", "用神"}

    def df(term: str) -> int:
        return 1 if term in corpus else 0

    assert retrieval.expand_query("八字里的用神", df, 100, frozenset({"八字", "用神"})) == "八字 用神"
    assert retrieval.expand_query("食神生财", lambda t: 1 if t in {"食神", "生财"} else 0, 100) == "食神 生财"


# ---- K-2：相关度集合与排序规则

_SPEC = importlib.util.spec_from_file_location("eval_knowledge_search", ROOT / "scripts" / "eval_knowledge_search.py")
_EVAL = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_EVAL)
# 2026-11-11：改排序前 0.776（裸词 0.972 · 多词 0.4 · 问句 0.636 · 英文 0.571 · 繁体 0.667）→ 改后 0.985。只许往上调。
RELEVANCE_FLOOR = 0.95


def test_the_relevance_set_stays_above_its_floor() -> None:
    result = _EVAL.evaluate_relevance()
    assert result["n"] >= 60 and result["hit"] >= RELEVANCE_FLOOR, result["misses"]


@pytest.mark.parametrize("query", ["用神", "互容", "燃烧", "长生"])
def test_interface_pages_and_one_line_pithy_rank_after_entries_that_explain_a_bare_term(query: str) -> None:
    matches = store.search_knowledge({"query": query, "limit": 20})["matches"]
    docs = {(doc.domain, doc.key): doc for doc in store.search_docs()}
    first = docs[(matches[0]["domain"], matches[0]["key"])]
    assert not store._is_aside(first), (query, first.domain, first.key)
    assert any(store._is_aside(docs[(m["domain"], m["key"])]) for m in matches), "往后放，不是删掉"


def test_an_interface_page_is_still_first_when_the_query_names_it() -> None:
    top = store.search_knowledge({"query": "八字排盘设置"})["matches"][0]
    assert (top["domain"], top["key"]) == ("bazi", "排盘设置")


def test_several_terms_prefer_entries_with_all_of_them_and_say_when_none_has() -> None:
    both = store.search_knowledge({"query": "四化 流年"})
    assert both["match_mode"] == "all" and (both["matches"][0]["domain"], both["matches"][0]["key"]) == ("ziwei", "四化与运限")
    some = store.search_knowledge({"query": "互容 起课"})
    assert some["match_mode"] == "any" and some["matches"]
    chinese, english = some["warnings"][0].split(" / ", 1)
    assert "没有一条同时含全部检索词" in chinese and "only some" in english


@pytest.mark.parametrize("query", ["身强 身弱", "四化 流年", "值符 值使", "动爻 变卦"])
def test_entries_with_every_term_come_before_entries_with_only_some(query: str) -> None:
    """「身强 身弱」此前前三条都是只含其中一个词的一行口诀，同时讲两者的「格局用神」在后面。"""
    docs = {(doc.domain, doc.key): doc for doc in store.search_docs()}
    terms = query.split()
    # 条目名正好是其中一个词的也算（它就是在讲那个词：「值符 值使」里 qimen/值符 那一条）
    covered = [all(term in docs[(m["domain"], m["key"])].haystack for term in terms) or bool(set(terms) & docs[(m["domain"], m["key"])].names)
               for m in store.search_knowledge({"query": query, "limit": 20})["matches"]]
    assert covered[0] and covered == sorted(covered, reverse=True), covered


def test_a_domain_word_weights_but_does_not_score() -> None:
    """「八字 用神」此前前两条是一行口诀：「八字断语库」的标题里就有「八字」。"""
    top = store.search_knowledge({"query": "八字 用神"})["matches"][0]
    assert (top["domain"], top["key"]) == ("bazi", "格局用神")


# ---- K-3：英文与零命中


def test_english_aliases_come_from_the_corpus_and_point_at_its_titles() -> None:
    vocabulary = store.search_vocabulary()
    bodies = [retrieval.normalize(f"{doc.title}\n{' '.join(doc.names)}\n{doc.body}") for doc in store.search_docs()]
    for english, chinese in store.TERM_ALIASES.items():
        pattern = r"(?<![a-z])" + re.escape(english).replace(r"\ ", r"[\s\-]+") + r"(?![a-z])"
        paired = any(re.search(rf"{pattern}.{{0,40}}{re.escape(chinese)}|{re.escape(chinese)}.{{0,40}}{pattern}", body, re.S)
                     for body in bodies)
        assert paired, f"语料里没有把 {english} 与 {chinese} 写在一起"
        assert chinese in vocabulary, f"{chinese} 不是语料里的标题 / 小节名 / 加粗词"
        assert store.search_knowledge({"query": chinese})["total_matched"] > 0


@pytest.mark.parametrize(("query", "domain", "key"), [("primary direction", "direction", "主限法"),
                                                      ("What is a solar arc?", "germany", "太阳弧 · 校时")])
def test_english_terms_find_the_chinese_entry(query: str, domain: str, key: str) -> None:
    result = store.search_knowledge({"query": query, "limit": 3})
    assert (domain, key) in [(m["domain"], m["key"]) for m in result["matches"]]
    assert result["aliases_used"]


def test_a_zero_result_says_the_corpus_is_chinese_and_suggests_terms() -> None:
    result = store.search_knowledge({"query": "Combust"})
    assert result["total_matched"] == 0 and result["suggestions"]
    chinese, english = result["no_match"].split(" / ", 1)
    assert "中文写的" in chinese and "written in Chinese" in english
    for word in result["suggestions"]:
        assert word in chinese and word in english
    typo = store.search_knowledge({"query": "財多身弱"})
    assert typo["total_matched"] == 0 and "身弱" in typo["suggestions"] and "中文写的" not in typo["no_match"]
