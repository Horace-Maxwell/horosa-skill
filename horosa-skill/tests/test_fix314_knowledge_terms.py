"""知识库补词的机械层 + 对照层（审计 O-08 / 待决项 5）。

- 对照层：黄道释放（工具正文）= 黄道星释（手册）；void of course = 月亮空亡；导出登记表的每个技法名都搜得到。
- 机械层：语料里「**术语**：定义句」进术语索引——查一个术语时，有定义句的条目随命中带 `definition`（不改排序：
  提前试过，评测集 hit@1 跌破下限，见 store.search_knowledge 注释）。
- 只在正文顺带提到的词，如实说「没有定义条目」。
负向对照（实跑过）：CJK_TERM_ALIASES 清空 → 第一、三条红；term_index 恒返回空 → 第四条红；去掉提示 → 第五条红。
"""
from __future__ import annotations

import pytest

from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.exports.contract import TOOL_EXPORT_TECHNIQUE_MAP
from horosa_skill.exports.registry import AI_EXPORT_TECHNIQUES
from horosa_skill.knowledge import store
from horosa_skill.reports.source import report_technique_name

# 没有手册的：玄史是一个独立的检索工具（horosa_knowledge_xuanshi），它自己就是那份知识。
NO_MANUAL = {"玄史知识库"}


def test_the_tool_name_for_zodiacal_releasing_finds_the_manual() -> None:
    result = store.search_knowledge({"query": "黄道释放", "limit": 3})
    assert result["matches"][0]["title"].endswith("黄道星释") and ["黄道释放", "黄道星释"] in result["aliases_used"]


@pytest.mark.parametrize(("query", "target"), [("void of course moon", "月亮空亡"), ("primary directions", "主限法")])
def test_curated_english_terms_point_at_corpus_words(query: str, target: str) -> None:
    assert any(target in doc.haystack for doc in store.search_docs())   # 值是语料里的词，不是 skill 编的
    result = store.search_knowledge({"query": query, "limit": 5})
    assert result["total_matched"] and any(target in pair for pair in result.get("aliases_used", []))


def test_every_export_technique_name_is_searchable() -> None:
    labels = {item["label"] for item in AI_EXPORT_TECHNIQUES}
    for name in TOOL_DEFINITIONS:
        key = TOOL_EXPORT_TECHNIQUE_MAP.get(name)
        labels.add(report_technique_name(name, next((t["label"] for t in AI_EXPORT_TECHNIQUES if t["key"] == key), "")))
    missing = sorted(label for label in labels - NO_MANUAL if label and not store.search_knowledge({"query": label})["total_matched"])
    assert missing == [], missing


def test_a_term_query_carries_the_defining_sentence() -> None:
    matches = store.search_knowledge({"query": "互容", "limit": 8})["matches"]
    assert any(m.get("definition", "").startswith("互容：两星各在对方的") for m in matches)
    assert any("definition" in m for m in store.search_knowledge({"query": "映点"})["matches"])


def test_a_word_only_mentioned_in_passing_says_there_is_no_definition() -> None:
    result = store.search_knowledge({"query": "入相"})
    assert result["matches"] and any("没有「入相」的定义条目" in w for w in result.get("warnings", []))
    assert not any("定义条目" in w for w in store.search_knowledge({"query": "主限法"}).get("warnings", []))
