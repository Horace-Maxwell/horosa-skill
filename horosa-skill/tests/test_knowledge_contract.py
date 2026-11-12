"""知识检索对调用方的契约（2026-11-11 深审）：参数怎么认、什么会被说出来、哪些文字要标「不可信」。

每条都对着一次真实复现：域名只认内部 id、limit / offset 越界不吭声、自备知识库里没进索引的文件不吭声、
笔记原文不带标记就交给模型、同一条笔记的命中被悄悄截掉、空库 0 命中没有任何说明。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.errors import ToolValidationError
from horosa_skill.knowledge import search as knowledge_search
from horosa_skill.knowledge import store
from horosa_skill.knowledge import user as uk


def _settings(tmp_path: Path, **extra) -> Settings:
    return Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", runtime_root=tmp_path / "rt",
                    db_path=tmp_path / "data" / "m.db", output_dir=tmp_path / "data" / "runs", data_dir=tmp_path / "data", **extra)


def _put(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / "data" / "knowledge" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ---- domain 参数（K-4）


@pytest.mark.parametrize(("given", "domain"), [
    ("bazi", "bazi"), ("BAZI", "bazi"), (" Bazi ", "bazi"), ("八字", "bazi"), ("八字四柱", "bazi"), ("八字四柱 · 操作手册", "bazi"),
    ("八字断语库", "bazi_pithy"), ("Bazi-Pithy", "bazi_pithy"), ("bazi pithy", "bazi_pithy"),
    ("紫微斗数", "ziwei"), ("紫微斗數", "ziwei"), ("奇門遁甲", "dunjia"), ("大六壬", "liureng_manual"), ("六爻", "guazhan"),
    ("塔羅", "tarot"), ("擇日", "zeri"), ("量化盘", "germany"), ("QIMEN", "qimen"), ("Astro", "astro"),
])
def test_a_domain_is_accepted_by_id_or_display_name_in_either_script_and_any_case(given: str, domain: str) -> None:
    assert store.canonical_domain(given) == domain
    assert store.search_knowledge({"query": "用神", "domain": given})["domain"] == domain
    assert store.build_knowledge_registry(domain=given)["domains"][0]["domain"] == domain


@pytest.mark.parametrize("given", ["user", "USER", "自备知识库", "自備知識庫", "笔记", "Notes"])
def test_the_notes_folder_answers_to_its_names_too(tmp_path: Path, given: str) -> None:
    _put(tmp_path, "a.md", "空亡者，虚也。")
    result = knowledge_search.search_all(_settings(tmp_path), {"query": "空亡", "domain": given})
    assert result["domain"] == "user" and result["matches"][0]["key"] == "a"


def test_every_bundled_display_name_resolves_to_its_own_domain() -> None:
    """清单是从语料自己长出来的：以后收割进来的手册不用改代码就认。"""
    for domain, bundle in store.load_knowledge_bundles().items():
        assert store.canonical_domain(domain.upper()) == domain
        if bundle.get("label"):
            assert store.canonical_domain(bundle["label"]) == domain, bundle["label"]
    assert store.USER_DOMAIN == uk.USER_DOMAIN


@pytest.mark.parametrize("call", [
    lambda: store.search_knowledge({"query": "四化", "domain": "nope"}),
    lambda: store.read_knowledge_entry({"domain": "nope", "category": "x", "key": "y"}),
    lambda: store.build_knowledge_registry(domain="nope"),
    lambda: store.search_knowledge({"query": "四化", "domain": "user"}),  # 内置语料自己的函数不认 user
])
def test_an_unknown_domain_says_so_in_both_languages_and_lists_the_valid_ones(call) -> None:
    with pytest.raises(ToolValidationError) as caught:
        call()
    error = caught.value
    zh, _, en = str(error).partition(" / ")
    assert error.code == "knowledge.unknown_domain"
    assert "没有这个知识域" in zh and "Unknown knowledge domain" in en
    listed = {row["domain"] for row in error.details["valid_domains"]}
    assert set(store.load_knowledge_bundles()) <= listed
    for domain in ("bazi", "ziwei", "astro"):
        assert domain in zh and domain in en


def test_a_near_miss_gets_a_suggestion() -> None:
    with pytest.raises(ToolValidationError) as caught:
        knowledge_search.resolve_domain("bazzi")
    assert "bazi" in caught.value.details["suggestions"] and "Did you mean" in str(caught.value)


def test_a_name_that_covers_two_domains_says_which_one_was_searched(tmp_path: Path) -> None:
    result = knowledge_search.search_all(_settings(tmp_path), {"query": "用神", "domain": "八字"})
    assert result["domain"] == "bazi"
    assert any("bazi_pithy" in note and " / " in note for note in result["warnings"])
    assert "warnings" not in knowledge_search.search_all(_settings(tmp_path), {"query": "用神", "domain": "bazi"})


# ---- limit / offset（K-4）


@pytest.mark.parametrize(("payload", "limit", "offset", "said"), [
    ({"limit": 500}, 20, 0, "limit=500"),
    ({"limit": 0}, 8, 0, "limit=0"),
    ({"limit": -1}, 8, 0, "limit=-1"),
    ({"limit": "many"}, 8, 0, "limit='many'"),
    ({"limit": True}, 8, 0, "limit=True"),
    ({"offset": -3}, 8, 0, "offset=-3"),
    ({"offset": "x"}, 8, 0, "offset='x'"),
    ({"limit": 2.5}, 8, 0, "limit=2.5"),
])
def test_out_of_range_paging_is_reported_not_silently_replaced(tmp_path: Path, payload: dict, limit: int, offset: int, said: str) -> None:
    result = knowledge_search.search_all(_settings(tmp_path), {"query": "用神", **payload})
    assert (result["limit"], result["offset"]) == (limit, offset)
    assert [note for note in result["warnings"] if said in note and " / " in note], result["warnings"]


@pytest.mark.parametrize("payload", [{}, {"limit": 1}, {"limit": 20}, {"limit": "5"}, {"offset": 0}, {"offset": 3, "limit": 2}, {"limit": None}])
def test_valid_paging_is_taken_as_given_without_a_note(tmp_path: Path, payload: dict) -> None:
    result = knowledge_search.search_all(_settings(tmp_path), {"query": "用神", **payload})
    assert "warnings" not in result
    assert result["limit"] == int(payload.get("limit") or 8) and result["offset"] == int(payload.get("offset") or 0)
