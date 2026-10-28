"""可选向量检索（v0.45.1，knowledge/vectors.py）：BM25 + 向量做 RRF；换了说法的查询能找回来；没装 / 没模型就退回纯 BM25。

真模型（bge-small-zh int8）只在本机装了 [vectors] 且下好了模型时才跑（最后一条）；其余用概念替身：
把字映射到几个「概念」上，「日主衰弱钱守不住」与「财多身弱，富屋贫人」没有一个双字相同、向量却相近。
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.knowledge import index as kindex
from horosa_skill.knowledge import user as uk
from horosa_skill.knowledge import vectors

np = pytest.importorskip("numpy")

CONCEPTS = {"弱": 0, "衰": 0, "旺": 1, "强": 1, "财": 2, "钱": 2, "富": 2, "官": 3, "杀": 3, "印": 4, "紫": 5, "命": 5}


class _ConceptEmbedder:
    calls = 0

    def embed(self, texts, *, query=False, batch=16):
        _ConceptEmbedder.calls += len(texts)
        out = np.zeros((len(texts), 8), dtype=np.float32)
        for row, text in enumerate(texts):
            for ch in text:
                if ch in CONCEPTS:
                    out[row, CONCEPTS[ch]] += 1
            out[row, 7] += 0.01
        return out / np.linalg.norm(out, axis=1, keepdims=True)


def _settings(tmp_path: Path) -> Settings:
    return Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", runtime_root=tmp_path / "rt",
                    db_path=tmp_path / "data" / "m.db", output_dir=tmp_path / "data" / "runs", data_dir=tmp_path / "data")


def _put(tmp_path: Path, name: str, text: str) -> None:
    path = tmp_path / "data" / "knowledge" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def fake_vectors(monkeypatch: pytest.MonkeyPatch) -> _ConceptEmbedder:
    fake = _ConceptEmbedder()
    _ConceptEmbedder.calls = 0
    monkeypatch.setattr(vectors, "ready", lambda settings: True)
    monkeypatch.setattr(vectors, "embedder", lambda settings: fake)
    return fake


def test_a_paraphrase_with_no_shared_words_is_found_through_vectors(tmp_path: Path, fake_vectors) -> None:
    _put(tmp_path, "财.md", "财多身弱，富屋贫人。")
    _put(tmp_path, "紫微.md", "紫微坐命，主一生贵显。")
    settings = _settings(tmp_path)
    assert uk.search_user(settings, "日主衰弱钱守不住")["engine"] == "fts5-bm25+vectors"
    matches = uk.search_user(settings, "日主衰弱钱守不住")["matches"]
    assert matches and matches[0]["key"] == "财"  # 一个双字都对不上，BM25 单独查是空的
    # 纯 BM25 时同一查询确实找不到（证明是向量补回来的，不是测试数据碰巧有共同双字）
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(vectors, "ready", lambda settings: False)
        assert uk.search_user(settings, "日主衰弱钱守不住")["matches"] == []


def test_vectors_are_embedded_once_and_follow_edits_and_deletes(tmp_path: Path, fake_vectors) -> None:
    _put(tmp_path, "a.md", "财多身弱。")
    _put(tmp_path, "b.md", "官杀混杂。")
    settings = _settings(tmp_path)
    assert uk.indexed_catalog(settings).index_report["vectors"] == 2
    assert uk.indexed_catalog(settings).index_report["vectors"] == 0  # 没改就不重算
    (tmp_path / "data" / "knowledge" / "b.md").unlink()
    uk.indexed_catalog(settings)
    import sqlite3

    with sqlite3.connect(kindex.index_path(settings)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM chunk_vec").fetchone()[0] == 1  # 删掉的条目向量也删


def test_fusion_ties_break_deterministically_on_the_lexical_rank() -> None:
    lexical = [("a", 0, 0.9), ("b", 0, 0.8)]
    semantic = [("b", 0, 0.7), ("a", 0, 0.6)]
    fused = kindex._fuse(lexical, semantic)  # a、b 的 RRF 分完全相同
    assert [r[0] for r in fused] == ["a", "b"] and fused[0][2] == 1.0
    assert kindex._fuse(lexical, semantic) == fused


def test_without_the_extra_or_the_model_search_stays_pure_bm25(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _put(tmp_path, "财.md", "财多身弱，富屋贫人。")
    monkeypatch.setenv("HOROSA_EMBED_MODEL_DIR", str(tmp_path / "no-model"))
    settings = _settings(tmp_path)
    assert not vectors.model_ready(settings) and not vectors.ready(settings)
    result = uk.search_user(settings, "身弱")
    assert result["engine"] == "fts5-bm25" and result["matches"][0]["key"] == "财"
    monkeypatch.setenv("HOROSA_KNOWLEDGE_VECTORS", "0")
    assert not vectors.enabled_by_env()


def test_a_tampered_model_file_is_not_used(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = tmp_path / "model"
    for name in vectors.MODEL_FILES:
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(b"not the pinned bytes")
    monkeypatch.setenv("HOROSA_EMBED_MODEL_DIR", str(folder))
    assert vectors.model_ready(_settings(tmp_path)) is False  # sha256 对不上就当没有


@pytest.mark.skipif(not (vectors.deps_available() and os.environ.get("HOROSA_EMBED_MODEL_DIR")),
                    reason="需要 [vectors] 依赖 + HOROSA_EMBED_MODEL_DIR 指向已下好的 bge-small-zh 模型")
def test_real_bge_model_finds_the_paraphrase(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    assert vectors.model_ready(settings)
    _put(tmp_path, "财.md", "财多身弱，富屋贫人。")
    _put(tmp_path, "印.md", "印绶太旺，母多子病。")
    _put(tmp_path, "紫微.md", "紫微坐命，逢左辅右弼夹拱，主一生贵显。")
    matches = uk.search_user(settings, "日主衰弱却遇到很多财星，有钱也守不住")["matches"]
    assert matches and matches[0]["key"] == "财"
