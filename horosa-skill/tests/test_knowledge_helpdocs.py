"""方法论手册知识包（v0.28.0 B1）：完整性 + 出处 + 通用读取契约。

这批包是「引教义必带出处」策略的机器前提——每条缺 source 就是一条无从溯源的教义，
比没有更糟（读者以为它有据）。守住：包结构、逐条出处、registry/read round-trip、幂等可再生。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from horosa_skill.errors import ToolValidationError
from horosa_skill.knowledge.store import (
    build_knowledge_registry,
    load_helpdoc_bundles,
    read_knowledge_entry,
)

PACK_DIR = Path(__file__).resolve().parents[1] / "src/horosa_skill/knowledge/data/helpdocs"


def test_helpdoc_packs_exist_and_cover_the_major_technique_manuals() -> None:
    bundles = load_helpdoc_bundles()
    assert len(bundles) >= 18, f"收割面塌了：只剩 {sorted(bundles)}"
    for must in ("bazi", "ziwei", "dunjia", "liureng_manual", "astro_manual", "tarot", "cnyibu"):
        assert must in bundles, f"缺关键手册域 {must}"


def test_every_entry_carries_a_nonempty_source_and_text() -> None:
    """逐条出处是硬约束：file + tab 都非空，text 是抽干净的正文（无 JSX 残渣）。"""
    for domain, bundle in load_helpdoc_bundles().items():
        src = bundle.get("source") or {}
        assert src.get("file") and src.get("upstream_git_sha"), f"{domain}: 包级出处缺失"
        for cat in bundle.get("categories") or []:
            for entry in cat.get("entries") or []:
                key = entry.get("key")
                assert key and f"{entry.get('text', '')}".strip(), f"{domain}/{key}: 空条目"
                entry_src = entry.get("source") or {}
                assert entry_src.get("file") and entry_src.get("tab"), f"{domain}/{key}: 条目出处缺失"
                text = entry["text"]
                assert "TabPane" not in text and "style={" not in text, f"{domain}/{key}: JSX 残渣"
                assert "className" not in text, f"{domain}/{key}: JSX 残渣"


def test_registry_lists_helpdoc_domains_with_keys() -> None:
    registry = build_knowledge_registry()
    domains = {d["domain"]: d for d in registry["domains"]}
    assert "bazi" in domains and "astro" in domains, "手册域与 hover 域必须并存"
    bazi = domains["bazi"]
    assert bazi["source"] == "xingque_help_docs"
    assert bazi["categories"][0]["count"] >= 5
    assert any("排盘" in f"{k}" for k in bazi["categories"][0]["keys"])


def test_read_round_trip_returns_cited_text() -> None:
    entry = read_knowledge_entry({"domain": "bazi", "key": "算法与口径"})
    assert entry["rendered_text"].strip()
    assert "BaziHelpDoc.js" in entry["citation"], "citation 必须落到具体组件文件"
    assert entry["provenance"]["upstream_git_sha"]
    # 前缀兜底：唯一命中才放行
    loose = read_knowledge_entry({"domain": "bazi", "key": "算法"})
    assert loose["key"] == "算法与口径"


def test_read_without_key_fails_with_the_key_list() -> None:
    with pytest.raises(ToolValidationError) as excinfo:
        read_knowledge_entry({"domain": "bazi"})
    assert excinfo.value.code == "knowledge.helpdoc.key_required"
    assert "排盘设置" in f"{excinfo.value.details.get('keys')}"


def test_hover_domains_still_work_unchanged() -> None:
    """三个 hover 域的专用渲染分支不许被通用分支影响。"""
    entry = read_knowledge_entry({"domain": "qimen", "category": "door", "key": "开"})
    assert entry["source"] == "xingque_hover_docs"
    assert entry["rendered_text"].strip()


def test_packs_are_committed_and_parseable_on_disk() -> None:
    files = sorted(PACK_DIR.glob("*.json"))
    assert len(files) >= 18
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data.get("schema") == "horosa.knowledge.helpdoc.v1"
        assert data.get("domain") == path.stem, f"{path.name}: 文件名必须等于 domain（自动发现的键）"
