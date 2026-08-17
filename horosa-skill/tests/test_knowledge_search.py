"""knowledge_read 全文检索模式（v0.30.0）：跨 24 域一把搜，命中带出处、可直接回读。

检索器是确定性代码（得分 + 字典序），离线可测到位；bundle 内容随上游收割变化，
测试锚定**行为**（形状/排序/出处/回读性）而非具体条目文案。
"""

from __future__ import annotations

import pytest

from horosa_skill.errors import ToolValidationError
from horosa_skill.knowledge.store import (
    load_knowledge_bundles,
    read_knowledge_entry,
    search_knowledge,
)


def test_exact_hover_key_ranks_first_and_is_re_readable() -> None:
    result = search_knowledge({"query": "休门"})
    assert result["mode"] == "search" and result["total_matched"] >= 1
    top = result["matches"][0]
    assert (top["domain"], top["category"], top["key"]) == ("qimen", "door", "休门")
    assert top["score"] >= 100 and top["citation"]
    # 命中坐标必须能直接喂回精读——search → read 闭环。
    entry = read_knowledge_entry({"domain": top["domain"], "category": top["category"], "key": top["key"]})
    assert entry["key"] == "休门" and entry["citation"]


def test_manual_fulltext_hit_carries_file_and_version_citation() -> None:
    result = search_knowledge({"query": "晚子时"})
    assert result["total_matched"] >= 2
    manual_hits = [m for m in result["matches"] if "星阙操作手册" in m["citation"]]
    assert manual_hits, "手册域全文命中必须带「星阙操作手册 · … · …（文件 @ 星阙 版本）」出处"
    assert all("@ 星阙" in m["citation"] for m in manual_hits)
    assert all(m["snippet"] for m in result["matches"])


def test_domain_filter_and_limit() -> None:
    unfiltered = search_knowledge({"query": "晚子时"})
    filtered = search_knowledge({"query": "晚子时", "domain": "bazi", "limit": 2})
    assert all(m["domain"] == "bazi" for m in filtered["matches"])
    assert len(filtered["matches"]) <= 2
    assert filtered["total_scanned"] < unfiltered["total_scanned"]


def test_search_is_deterministic() -> None:
    a = search_knowledge({"query": "四化"})
    b = search_knowledge({"query": "四化"})
    assert a["matches"] == b["matches"]


def test_liureng_bespoke_shapes_are_searchable() -> None:
    """liureng 散装结构（shen_entries / jiang_info）也要进索引，且坐标可回读。"""
    result = search_knowledge({"query": "神后", "domain": "liureng"})
    assert result["total_matched"] >= 1
    top = result["matches"][0]
    entry = read_knowledge_entry({"domain": "liureng", "category": top["category"], "key": top["key"]})
    assert entry["domain"] == "liureng"


def test_empty_query_rejected_and_unknown_domain_rejected() -> None:
    with pytest.raises(ToolValidationError):
        search_knowledge({"query": "   "})
    with pytest.raises(ToolValidationError):
        search_knowledge({"query": "四化", "domain": "nope"})


def test_no_match_returns_empty_not_error() -> None:
    result = search_knowledge({"query": "斯芬克斯之谜语无此词"})
    assert result["total_matched"] == 0 and result["matches"] == []


def test_scan_covers_all_domains() -> None:
    result = search_knowledge({"query": "四化"})
    domains = len(load_knowledge_bundles())
    assert domains >= 24
    # 扫描条目数必须显著大于域数——每域都被走到（liureng 散装 + 手册 + hover 全算）。
    assert result["total_scanned"] > domains * 2
