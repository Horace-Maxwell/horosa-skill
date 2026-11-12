"""知识检索的行为契约（v0.47.2）。每条都来自 2026-11-06 审计里真实复现过的失败，打分与切词的回归网。

排序质量的整体下限在 test_knowledge_eval.py；这里钉的是具体的行为。
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.knowledge import index as kindex
from horosa_skill.knowledge import retrieval, store, vectors
from horosa_skill.knowledge import search as knowledge_search
from horosa_skill.knowledge import user as uk
from horosa_skill.knowledge.store import ASTRO_LABELS, read_knowledge_entry, search_docs, search_knowledge


def _settings(tmp_path: Path, **extra) -> Settings:
    return Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", runtime_root=tmp_path / "rt",
                    db_path=tmp_path / "data" / "m.db", output_dir=tmp_path / "data" / "runs", data_dir=tmp_path / "data", **extra)


def _put(tmp_path: Path, name: str, text: str) -> None:
    path = tmp_path / "data" / "knowledge" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _top(query: str, **payload) -> dict:
    return search_knowledge({"query": query, **payload})["matches"][0]


# ---- 打分


def test_a_term_of_three_or_more_characters_scores_above_zero(tmp_path: Path) -> None:
    """双字序列拼成「紫微微斗斗数」去数：这串字不可能出现，三字以上的中文词一律 0 分。"""
    _put(tmp_path, "a.md", "紫微斗数入门笔记，紫微斗数的基本结构。")
    assert uk.search_user(_settings(tmp_path), "紫微斗数")["matches"][0]["score"] > 0


def test_the_note_about_the_long_term_beats_a_passing_mention_of_the_short_one(tmp_path: Path) -> None:
    _put(tmp_path, "专论.md", "伤官见官，为祸百端。伤官见官要看月令之外的救应。伤官见官者须细审。")
    _put(tmp_path, "杂记.md", "月令是提纲。")
    assert uk.search_user(_settings(tmp_path), "伤官见官 月令")["matches"][0]["key"] == "专论"


def test_latin_terms_match_whole_words_on_both_pipelines(tmp_path: Path) -> None:
    assert retrieval.term_count("sunshine and sun", ("sun",)) == 1
    assert retrieval.term_count("紫微斗数", ("紫微斗数",)) == 1
    assert _top("sun")["key"] == "Sun"
    _put(tmp_path, "a.md", "sunshine only")
    _put(tmp_path, "b.md", "the sun rises")
    assert [m["key"] for m in uk.search_user(_settings(tmp_path), "sun")["matches"]] == ["b"]


def test_scores_inside_a_tier_are_not_clamped_into_a_tie() -> None:
    """此前正文分封顶 60：「值符 值使 九星 八门」前八条全是 60.0，按字典序排。"""
    scores = [m["score"] for m in search_knowledge({"query": "值符 值使 九星 八门"})["matches"]]
    assert len(set(scores)) == len(scores) and scores == sorted(scores, reverse=True)


def test_exact_names_stay_above_any_body_match() -> None:
    result = search_knowledge({"query": "休门", "limit": 20})["matches"]
    assert result[0]["key"] == "休门" and result[0]["score"] >= 100 and result[0]["exact"] is True
    assert all(m["score"] < 100 for m in result if m["key"] != "休门")


# ---- 叫法


@pytest.mark.parametrize(("key", "label"), sorted(ASTRO_LABELS.items()))
def test_every_label_the_charts_print_finds_its_entry(key: str, label: str) -> None:
    """read 认的 40 个标签，搜索此前有 18 个搜不到，而 福点 / 灵点 就印在输出里。"""
    match = _top(label)
    assert (match["domain"], match["key"]) == ("astro", key), match


def test_the_planet_outranks_a_method_with_its_name_in_the_title() -> None:
    assert _top("太阳")["key"] == "Sun"  # 此前第一名是「太阳弧 · 校时」


def test_lower_case_keys_resolve() -> None:
    assert _top("sagittarius")["key"] == "Sagittarius"


@pytest.mark.parametrize(("query", "key"), [("白羊座", "Aries"), ("处女座", "Virgo"), ("水瓶座", "Aquarius"), ("第十宫", "House10"),
                                            ("北交点", "North Node"), ("四分相", "90"), ("腾蛇", "螣蛇"), ("贵人", "天乙"), ("神后", "子")])
def test_variant_names_are_exact_hits(query: str, key: str) -> None:
    assert _top(query)["key"] == key


def test_manuals_keyed_by_component_name_answer_to_their_chinese_label() -> None:
    assert _top("小六壬")["key"] == "Xiaoliuren"
    assert _top("宿占")["key"] == "Suzhan"
    assert _top("世俗盘")["key"] == "Mundane"
    assert read_knowledge_entry({"domain": "cnyibu", "key": "Xiaoliuren"})["title"].endswith("小六壬")


def test_the_technique_name_reaches_its_manual_overview() -> None:
    match = _top("奇門遁甲")
    assert (match["domain"], match["key"]) == ("dunjia", "总览")


def test_pithy_categories_are_searchable() -> None:
    assert _top("三字诀")["category"] == "三字诀"
    assert _top("子息")["category"] == "子息"


def test_spelling_variants_search_both_ways() -> None:
    assert retrieval.parse_query("阳刃").terms == ("阳刃", "羊刃")
    assert search_knowledge({"query": "调候"})["total_matched"] > 0 and retrieval.parse_query("调候").terms == ("调候", "调侯")
    assert search_knowledge({"query": "阳刃"})["total_matched"] > 0


# ---- 语料


def test_the_indexed_text_is_the_text_read_returns() -> None:
    """此前奇门条目 31% 的「正文」是 text / blank 这种块类型标记。"""
    for doc in search_docs():
        assert doc.body == read_knowledge_entry(doc.read())["rendered_text"]
    qimen = next(doc for doc in search_docs() if doc.domain == "qimen")
    assert not re.search(r"\b(text|blank)\b", qimen.body) and "<font" not in qimen.body


def test_every_hit_reads_back() -> None:
    for doc in search_docs():
        assert read_knowledge_entry(doc.read())["citation"], doc.read()
    match = _top("朱雀", domain="liureng")
    assert read_knowledge_entry(match["read"])["key"] == "朱雀"


def test_a_general_reads_without_branches_and_a_bad_branch_still_fails() -> None:
    entry = read_knowledge_entry({"domain": "liureng", "category": "house", "key": "朱雀"})
    assert "——" in entry["rendered_text"]
    from horosa_skill.errors import ToolValidationError

    with pytest.raises(ToolValidationError):
        read_knowledge_entry({"domain": "liureng", "category": "house", "key": "朱雀", "tian_branch": "x", "di_branch": "y"})


def test_manual_text_has_no_jsx_left_in_it() -> None:
    residue = re.compile(r"return\s*\(|const \w+ =|=>|\bthis\.|export default|\.map\(|className")
    bad = [(doc.domain, doc.key, match.group(0)) for doc in search_docs() if (match := residue.search(doc.body))]
    assert bad == []


def test_the_generator_pairs_each_section_with_its_label() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("gen_knowledge_packs", Path(__file__).parents[1] / "scripts" / "gen_knowledge_packs.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    source = """
class X {
\trenderSuzhan(){
\t\treturn (
\t\t\t<div>正文内容足够长</div>
\t\t);
\t}
\trenderHelper(){
\t\treturn (<div>第二节</div>);
\t}
\trender(){
\t\tconst groups = [ { key: 'x', label: '分组', items: [
\t\t\t{ key: 'suzhan', label: '宿盘', render: ()=>this.renderSuzhan() },
\t\t] } ];
\t\treturn <div/>;
\t}
}
export default X;
"""
    tabs = gen._split_tabs(source)
    assert [(key, label) for key, _body, label in tabs] == [("Suzhan", "宿盘"), ("Helper", None)]
    assert all("const groups" not in body and "return" not in body for _key, body, _label in tabs)


def test_map_expressions_are_dropped_without_eating_the_next_paragraph() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("gen_knowledge_packs", Path(__file__).parents[1] / "scripts" / "gen_knowledge_packs.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    text = gen._jsx_to_markdown("<p>前文</p>{LIST.map((e) => (<b key={e}>{e}</b>))}<p>后文</p>")
    assert "前文" in text and "后文" in text and "map" not in text


# ---- 零命中改写


@pytest.mark.parametrize(("query", "term"), [("什么是空亡", "空亡"), ("怎么看大运", "大运"), ("如何判断用神", "用神"),
                                             ("七杀羊刃", "七杀"), ("太阳天蝎", "太阳")])
def test_questions_and_compounds_are_rewritten(query: str, term: str) -> None:
    result = search_knowledge({"query": query})
    assert result["total_matched"] > 0 and term in result["expanded_query"].split()


@pytest.mark.parametrize("query", ["斯芬克斯之谜语无此词", "今天天气真好", "我的猫跑了", "量子计算机", "zzqq123", "完全不存在的词zzqq"])
def test_unrelated_queries_stay_empty_instead_of_returning_noise(query: str) -> None:
    result = search_knowledge({"query": query})
    assert result["total_matched"] == 0 and "expanded_query" not in result


def test_function_words_never_end_up_inside_a_term() -> None:
    """「斗数的四化」在语料里连着出现过，曾被当成一个词。"""
    assert search_knowledge({"query": "紫微斗数的四化是什么"})["expanded_query"] == "紫微斗数 四化"


def test_a_question_wrapper_is_evidence_enough_for_half_coverage() -> None:
    result = search_knowledge({"query": "塔罗怎么读牌"})
    assert result["expanded_query"] == "塔罗 读 牌" and {m["domain"] for m in result["matches"][:3]} == {"tarot"}
    assert search_knowledge({"query": "量子计算机是什么"})["total_matched"] == 0


def test_a_thin_result_is_topped_up_with_the_pieces() -> None:
    """整串碰巧在一本手册里连着出现过一次：原命中留在前面，再补上切开后的结果。"""
    result = search_knowledge({"query": "紫微流派"})
    assert result["matches"][0]["key"] == "Ziwei" and "紫微 流派" == result["expanded_query"]
    assert any((m["domain"], m["key"]) == ("ziwei", "流派分歧") for m in result["matches"])


def test_a_named_domain_outranks_passing_mentions_elsewhere() -> None:
    assert search_knowledge({"query": "六爻 起卦"})["matches"][0]["domain"] == "guazhan"
    assert search_knowledge({"query": "紫微 四化"})["matches"][0]["domain"] == "ziwei"


def test_a_query_that_already_hits_is_not_rewritten() -> None:
    assert "expanded_query" not in search_knowledge({"query": "七杀 羊刃"})


def test_segmentation_prefers_fewer_pieces_and_keeps_rare_terms() -> None:
    vocabulary = {"食神": 5, "生财": 3, "食神生": 1, "飞宫": 2, "飞宫小奇门": 2, "小奇门": 2}
    df = lambda term: vocabulary.get(term, 0)  # noqa: E731
    assert retrieval.expand_query("食神生财", df, 100) == "食神 生财"
    assert retrieval.expand_query("飞宫小奇门怎么用", df, 100) == "飞宫小奇门"


def test_user_notes_get_the_same_rewrite(tmp_path: Path) -> None:
    _put(tmp_path, "a.md", "空亡的笔记：空亡者，虚也。")
    found = uk.search_user(_settings(tmp_path), "什么是空亡")
    assert found["expanded_query"] == "空亡" and found["matches"][0]["key"] == "a"


def test_snippets_point_at_the_term_past_a_compatibility_character() -> None:
    """NFKC 把「…」展开成三个点，归一文本的下标比原文靠后：长省略号后面的词曾经切出空白摘要。"""
    text = "…" * 300 + "目标词在这里" + "后文" * 100
    assert "目标词" in retrieval.snippet(text, ["目标词"], 60)


# ---- 融合与翻页（search_all）


def test_paging_reaches_every_counted_match_without_repeats(tmp_path: Path) -> None:
    """此前 total_matched 说 135，翻到 40 条就没了。"""
    for index in range(30):
        _put(tmp_path, f"n{index}.md", f"第{index}篇：七杀羊刃的笔记。")
    settings = _settings(tmp_path)
    seen, offset = [], 0
    for _ in range(50):  # 有上限：翻页坏了要红，不能挂死（负向对照时真的挂了 26 分钟）
        page = knowledge_search.search_all(settings, {"query": "七杀", "limit": 20, "offset": offset})
        seen.extend((m["domain"], m["category"], m["key"], m.get("lines")) for m in page["matches"])
        total, offset = page["total_matched"], page["next_offset"]
        if offset is None:
            break
    else:
        pytest.fail("next_offset 一直不结束")
    assert len(seen) == total == len(set(seen)) and total > 20


def test_every_match_tells_how_to_read_it_in_full(tmp_path: Path) -> None:
    _put(tmp_path, "a.md", "七杀的笔记。")
    matches = knowledge_search.search_all(_settings(tmp_path), {"query": "七杀", "limit": 20})["matches"]
    assert matches and all(m["read"]["domain"] == m["domain"] for m in matches)


def test_an_exact_key_beats_a_note_that_merely_ties_on_rank(tmp_path: Path) -> None:
    _put(tmp_path, "a.md", "随手记：四化与运限这一节以后再看。")
    match = knowledge_search.search_all(_settings(tmp_path), {"query": "四化与运限"})["matches"][0]
    assert (match["domain"], match["key"]) == ("ziwei", "四化与运限")


def test_a_note_titled_exactly_the_query_beats_bundled_body_matches(tmp_path: Path) -> None:
    """RRF 同分时先出现的靠前，内置结果总在前：不置顶的话，用户点名自己的笔记也排在别人的正文命中后面。"""
    query = "伤官"
    assert not any(m.get("exact") for m in search_knowledge({"query": query})["matches"])
    assert search_knowledge({"query": query})["total_matched"] > 0
    _put(tmp_path, "b.md", f"---\ntitle: {query}\n---\n我的笔记。")
    match = knowledge_search.search_all(_settings(tmp_path), {"query": query})["matches"][0]
    assert (match["domain"], match["key"]) == ("user", "b") and match["exact"] is True


def test_both_exact_hits_lead_the_results(tmp_path: Path) -> None:
    _put(tmp_path, "我的休门.md", "---\ntitle: 休门\n---\n我自己的休门笔记。")
    match = knowledge_search.search_all(_settings(tmp_path), {"query": "休门"})["matches"]
    assert {m["domain"] for m in match[:2]} == {"qimen", "user"} and all(m.get("exact") for m in match[:2])


# ---- 故障隔离


def _damage_mid_file(path: Path) -> None:
    data = bytearray(path.read_bytes())
    page = 4096
    for start in range(page, len(data), page):
        data[start + 200 : start + 3800] = b"\xff" * 3600
    path.write_bytes(bytes(data))


def test_a_damaged_index_cannot_take_bundled_search_down(tmp_path: Path) -> None:
    """此前随机损坏 8 页：180 次检索里 83 次抛 DatabaseError，内置结果一起没了。"""
    for index in range(40):
        _put(tmp_path, f"n{index}.md", f"第{index}篇七杀笔记。\n\n" + "命理杂记。" * 200)
    settings = _settings(tmp_path)
    uk.search_user(settings, "七杀")
    _damage_mid_file(kindex.index_path(settings))
    result = knowledge_search.search_all(settings, {"query": "七杀"})
    assert any(m["domain"] != "user" for m in result["matches"])
    assert any(m["domain"] == "user" for m in result["matches"]), "笔记本身没坏，应该照样搜得到"
    assert uk.search_user(settings, "七杀")["matches"], "笔记本身没坏"


def test_a_read_that_finds_damage_quarantines_and_rebuilds_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """同步看不出来的损坏（只坏在 FTS 页上）要到读的时候才露面：这一路也得自愈，不能永远退回逐条匹配。"""
    _put(tmp_path, "a.md", "七杀的笔记。")
    settings = _settings(tmp_path)
    uk.search_user(settings, "七杀")
    real = kindex.search
    calls = []

    def damaged_once(*args, **kwargs):
        calls.append(kwargs.get("use_index"))
        if len(calls) == 1:
            raise sqlite3.DatabaseError("database disk image is malformed")
        return real(*args, **kwargs)
    monkeypatch.setattr(kindex, "search", damaged_once)
    found = uk.search_user(settings, "七杀")
    assert calls == [True, True] and found["engine"] == "fts5-bm25" and found["matches"]
    assert list(kindex.index_path(settings).parent.glob("index.sqlite.corrupt-*"))


def test_engine_says_substring_when_the_results_came_from_substring(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """被占着不是损坏，重建解决不了：退回逐条匹配，engine 如实写，不能照旧报 fts5-bm25。"""
    _put(tmp_path, "a.md", "七杀的笔记。")
    settings = _settings(tmp_path)
    uk.search_user(settings, "七杀")
    real = kindex.search

    def locked(*args, **kwargs):
        if kwargs.get("use_index"):
            raise sqlite3.OperationalError("database is locked")
        return real(*args, **kwargs)
    monkeypatch.setattr(kindex, "search", locked)
    found = uk.search_user(settings, "七杀")
    assert found["engine"] == "substring" and found["matches"] and "locked" in found["warnings"][0]
    assert not list(kindex.index_path(settings).parent.glob("index.sqlite.corrupt-*")), "被占着不许隔离"


def test_unexpected_user_side_failures_leave_a_warning_and_the_bundled_results(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args, **_kwargs):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(uk, "search_user", boom)
    result = knowledge_search.search_all(_settings(tmp_path), {"query": "七杀"})
    assert result["matches"] and result["warnings"] and result["engine"] == "unavailable"


def test_a_vector_failure_falls_back_to_bm25_with_a_note(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _put(tmp_path, "a.md", "七杀的笔记。")
    settings = _settings(tmp_path)
    uk.search_user(settings, "七杀")
    monkeypatch.setattr(vectors, "ready", lambda _settings: True)
    monkeypatch.setattr(kindex, "_sync_vectors", lambda *_a, **_k: (0, 0))

    def boom(*_args, **_kwargs):
        raise RuntimeError("model exploded")
    monkeypatch.setattr(kindex, "_vector_rank", boom)
    found = uk.search_user(settings, "七杀")
    assert found["matches"] and "model exploded" in found["warnings"][0]


def test_an_emptied_chunks_table_is_rebuilt_not_reported_as_zero_hits(tmp_path: Path) -> None:
    _put(tmp_path, "a.md", "七杀的笔记。")
    settings = _settings(tmp_path)
    uk.search_user(settings, "七杀")
    with sqlite3.connect(kindex.index_path(settings)) as conn:
        conn.execute("DELETE FROM chunks")
    assert uk.search_user(settings, "七杀")["matches"]


# ---- 读路径不拿写锁


def test_searching_does_not_queue_behind_another_sessions_writer(tmp_path: Path) -> None:
    _put(tmp_path, "a.md", "七杀的笔记。")
    settings = _settings(tmp_path)
    uk.search_user(settings, "七杀")
    writer = sqlite3.connect(kindex.index_path(settings), isolation_level=None)
    writer.execute("BEGIN IMMEDIATE")
    try:
        started = time.monotonic()
        found = uk.search_user(settings, "七杀")
        assert time.monotonic() - started < 1.5
        assert found["matches"] and found["engine"] == "fts5-bm25"
    finally:
        writer.execute("ROLLBACK")
        writer.close()


def test_a_large_vector_backlog_is_worked_off_a_bounded_slice_at_a_time(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    np = pytest.importorskip("numpy", reason="[host] numpy not installed (the [vectors] extra)")

    class Stub:
        calls = 0

        def embed(self, texts, *, query=False, batch=16):
            Stub.calls += len(texts)
            return np.ones((len(texts), 8), dtype=np.float32) / np.sqrt(8)

    for index in range(100):
        _put(tmp_path, f"n{index}.md", f"第{index}篇七杀笔记。")
    settings = _settings(tmp_path)
    monkeypatch.setattr(vectors, "ready", lambda _settings: True)
    monkeypatch.setattr(vectors, "embedder", lambda _settings: Stub())
    catalog = uk.indexed_catalog(settings)
    assert catalog.index_report["vectors"] == kindex.EMBED_BUDGET and catalog.index_report["vectors_pending"] == 100 - kindex.EMBED_BUDGET
    assert uk.indexed_catalog(settings, embed_all=True).index_report["vectors_pending"] == 0
    assert Stub.calls == 100


def test_a_settled_index_with_vectors_does_not_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """开了向量后，什么都没变时也不能写库：否则每次检索又要拿写锁。"""
    np = pytest.importorskip("numpy", reason="[host] numpy not installed (the [vectors] extra)")

    class Stub:
        def embed(self, texts, *, query=False, batch=16):
            return np.ones((len(texts), 8), dtype=np.float32) / np.sqrt(8)

    _put(tmp_path, "a.md", "七杀的笔记。")
    settings = _settings(tmp_path)
    monkeypatch.setattr(vectors, "ready", lambda _settings: True)
    monkeypatch.setattr(vectors, "embedder", lambda _settings: Stub())
    uk.indexed_catalog(settings)
    writer = sqlite3.connect(kindex.index_path(settings), isolation_level=None)
    writer.execute("BEGIN IMMEDIATE")
    try:
        started = time.monotonic()
        assert uk.indexed_catalog(settings).index_ok
        assert time.monotonic() - started < 1.5
    finally:
        writer.execute("ROLLBACK")
        writer.close()


def test_two_notes_folders_keep_separate_indexes(tmp_path: Path) -> None:
    (tmp_path / "other").mkdir()
    (tmp_path / "other" / "b.md").write_text("另一处的七杀笔记。", encoding="utf-8")
    _put(tmp_path, "a.md", "这里的七杀笔记。")
    default = _settings(tmp_path)
    other = _settings(tmp_path, user_knowledge_dir=tmp_path / "other")
    assert kindex.index_path(default).name == "index.sqlite"
    assert kindex.index_path(other) != kindex.index_path(default)
    uk.search_user(default, "七杀")
    uk.search_user(other, "七杀")
    assert uk.indexed_catalog(default).index_report["added"] == 0


def test_store_does_not_reach_into_the_user_index() -> None:
    """依赖方向：store / index 指向 retrieval，store 不依赖 index。"""
    source = Path(store.__file__).read_text(encoding="utf-8")
    assert "knowledge import index" not in source and "kindex" not in source
    assert json.dumps(retrieval.FIELD_WEIGHTS)
