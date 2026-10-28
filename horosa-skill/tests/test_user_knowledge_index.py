"""自备知识库的检索索引（v0.45.0）：分块、中文双字检索、增量同步、相关段落、翻页精读、检索门面。

设计照搬的开源实现与取舍见 docs/LESSONS.md v0.45.0-dev；每条测试都对应一个「此前做不到 / 做错」的行为。
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.knowledge import index as kindex
from horosa_skill.knowledge import user as uk


def _settings(tmp_path: Path, **extra) -> Settings:
    return Settings(
        server_root="http://127.0.0.1:9",
        chart_server_root="http://127.0.0.1:9",
        runtime_root=tmp_path / "runtime",
        db_path=tmp_path / "data" / "memory.db",
        output_dir=tmp_path / "data" / "runs",
        data_dir=tmp_path / "data",
        **extra,
    )


def _put(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / "data" / "knowledge" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


LONG_NOTE = (
    "---\ntitle: 八字笔记\ntags: [古籍]\n---\n\n"
    "# 总论\n\n" + "日主强弱为先，次看月令。" * 40 + "\n\n"
    "## 七杀格\n\n" + "七杀有制，化为权柄。羊刃驾杀，威震边疆。" * 60 + "\n\n"
    "## 伤官格\n\n" + "伤官见官，为祸百端。伤官配印，贵不可言。" * 60 + "\n"
)


# ── 检索：中文两字词、繁简互通、出处行号 ──────────────────────────────────


def test_two_character_terms_and_traditional_text_are_found_with_file_line_citations(tmp_path: Path) -> None:
    _put(tmp_path, "八字.md", LONG_NOTE)
    _put(tmp_path, "紫微.md", "紫微斗數：命宮見紫微，主一生富貴。\n\n遷移宮見天機，主奔波。")
    settings = _settings(tmp_path)

    result = uk.search_user(settings, "命宫")  # 简体查繁体
    assert [m["key"] for m in result["matches"]] == ["紫微"] and result["engine"] == "fts5-bm25"
    hit = uk.search_user(settings, "伤官")["matches"][0]
    assert hit["key"] == "八字" and hit["heading"] == "总论 › 伤官格"
    # 行号是原文件的行号（元数据占 4 行 + 空行），精读从这一行起正好是命中段。
    lines = (tmp_path / "data" / "knowledge" / "八字.md").read_text(encoding="utf-8").split("\n")
    first = int(hit["lines"].split("-")[0])
    assert lines[first - 1].startswith("## 伤官格") or "伤官" in lines[first - 1]
    assert hit["read"] == {"domain": "user", "key": "八字", "from_line": first}
    assert "第" in hit["citation"] and "伤官格" in hit["citation"]
    # 四个字的词按双字短语查：「羊刃驾杀」命中七杀格，不命中伤官格。
    assert {m["heading"] for m in uk.search_user(settings, "羊刃驾杀")["matches"]} == {"总论 › 七杀格"}
    # 单个汉字也能查（子串回退）。
    assert uk.search_user(settings, "宫")["matches"]


def test_query_syntax_cannot_reach_fts(tmp_path: Path) -> None:
    _put(tmp_path, "a.md", "甲木参天，脱胎要火。")
    settings = _settings(tmp_path)
    for hostile in ('甲木" OR *', "NEAR(甲木 参天)", "title:甲木", "^甲木", '"', "NOT", "甲木 AND", "or 参天", "near"):
        uk.search_user(settings, hostile)  # 不抛 sqlite3.OperationalError（只有引号里的双字进 MATCH）


# ── 分块 ────────────────────────────────────────────────────────────────


def test_chunks_follow_headings_keep_exact_offsets_and_overlap_one_sentence() -> None:
    body = LONG_NOTE.split("---\n\n", 1)[1]
    chunks = kindex.chunk_body(body)
    assert {c.heading for c in chunks} == {("总论",), ("总论", "七杀格"), ("总论", "伤官格")}
    for chunk in chunks:
        text = body[chunk.start:chunk.end]
        assert len(text) <= kindex.MAX_CHARS and text == text.strip()
        # 不跨标题：块里除了开头，不再出现另一个标题行。
        assert "\n## " not in text[1:]
        assert body.count("\n", 0, chunk.start) == chunk.line_start
    # 同一节里相邻两块重叠一句（qmd：overlap），不同节之间不重叠。
    same = [(a, b) for a, b in zip(chunks, chunks[1:]) if a.heading == b.heading]
    assert same and all(b.start < a.end for a, b in same)
    across = [(a, b) for a, b in zip(chunks, chunks[1:]) if a.heading != b.heading]
    assert all(b.start >= a.end for a, b in across)


def test_a_heading_only_parent_merges_into_its_child_not_into_a_sibling() -> None:
    body = "## 大运\n\n### 甲子运\n\n" + "甲子运见财。" * 30 + "\n\n## 流年\n\n短。\n\n## 小限\n\n" + "小限行。" * 50
    headings = [c.heading for c in kindex.chunk_body(body)]
    assert headings[0] == ("大运", "甲子运")  # 只有标题的上级节并进下级，路径取下级
    assert ("流年",) in headings and ("小限",) in headings  # 平级的短节自己成块，不和下一节揉在一起


# ── 增量同步与隐私 ────────────────────────────────────────────────────────


def test_index_syncs_incrementally_and_stores_no_note_text(tmp_path: Path) -> None:
    note = _put(tmp_path, "八字.md", LONG_NOTE)
    _put(tmp_path, "b.md", "独一无二的私密句子：庚金带煞。")
    settings = _settings(tmp_path)
    first = uk.indexed_catalog(settings).index_report
    assert first["added"] == 2 and first["chunks"] > 3
    assert uk.indexed_catalog(settings).index_report["unchanged"] == 2  # 没改就不重建

    note.write_text(LONG_NOTE.replace("七杀有制", "七煞有制"), encoding="utf-8")
    os.utime(note, ns=(time.time_ns() - 10**10,) * 2)  # 避开「刚改过不信 mtime」窗口，走正常路径
    report = uk.indexed_catalog(settings).index_report
    assert report["updated"] == 1 and report["unchanged"] == 1
    assert uk.search_user(settings, "七煞")["matches"]

    def index_bytes() -> bytes:
        return b"".join(p.read_bytes() for p in kindex.index_path(settings).parent.glob("index.sqlite*"))

    # 索引里不存正文（FTS5 contentless + 只记字符区间）：连切好的双字串（存进普通 FTS 表时的样子）都找不到。
    secret = "独一无二的私密句子"
    assert " ".join(kindex.grams(secret)).encode() not in index_bytes() and secret.encode() not in index_bytes()
    (tmp_path / "data" / "knowledge" / "b.md").unlink()
    assert uk.indexed_catalog(settings).index_report["removed"] == 1
    # 删掉的条目：索引里它的块与倒排一并删掉（不只是检索时被目录过滤掉）。
    assert kindex.stored_chunks(settings, "b") == [] and uk.search_user(settings, "庚金")["matches"] == []
    assert not (tmp_path / "data" / "knowledge" / "index.sqlite").exists()  # 不在用户的文件夹里放东西


def test_a_file_rewritten_within_the_same_mtime_is_reread(tmp_path: Path) -> None:
    note = _put(tmp_path, "a.md", "甲甲甲")
    settings = _settings(tmp_path)
    stamp = note.stat().st_mtime_ns
    assert uk.list_entries(settings)[0].text == "甲甲甲"
    note.write_text("乙乙乙", encoding="utf-8")  # 同样大小
    os.utime(note, ns=(stamp, stamp))  # 粗粒度文件系统上同一秒内的两次写：(大小, mtime) 一模一样
    assert uk.list_entries(settings)[0].text == "乙乙乙"  # 刚改过的不进缓存（racy-clean），下次照样重读


def test_without_fts5_search_falls_back_to_substrings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _put(tmp_path, "八字.md", LONG_NOTE)
    monkeypatch.setattr(kindex, "fts5_available", lambda: False)
    result = uk.search_user(_settings(tmp_path), "伤官")
    assert result["engine"] == "substring" and result["matches"][0]["heading"] == "总论 › 伤官格"


def test_a_broken_index_degrades_to_substring_search_and_is_reported(tmp_path: Path) -> None:
    _put(tmp_path, "八字.md", LONG_NOTE)
    settings = _settings(tmp_path)
    path = kindex.index_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"not a database" * 100)
    catalog = uk.indexed_catalog(settings)
    assert not catalog.index_ok and any(p.kind == "index" for p in catalog.problems)
    assert uk.search_user(settings, "伤官")["matches"]


# ── 计算时：长条目挑相关段落，`?检索词` ──────────────────────────────────────


def test_long_entries_carry_the_passages_relevant_to_the_chart_not_the_opening(tmp_path: Path) -> None:
    _put(tmp_path, "八字.md", LONG_NOTE)
    settings = _settings(tmp_path, user_knowledge_max_chars=1200)
    context = uk.build_context(settings, ["八字"], tool_name="bazi_birth",
                               focus="[格局]\n本命为伤官格，伤官配印。")
    item = context["entries"][0]
    assert item["selection"] == "relevant" and item["truncated"] is True
    assert "伤官" in item["text"] and "日主强弱" not in item["text"]  # 此前是从开头截：只会带到「总论」
    assert item["passages"] and all("伤官格" in p["heading"] for p in item["passages"])
    assert item["text"].startswith("【总论 › 伤官格 · 第") and len(item["text"]) <= 1200
    # 存档只留引用：段落清单（行号 / 标题）留下，正文去掉。
    stored = uk.redact_for_storage(context)["entries"][0]
    assert "text" not in stored and stored["passages"] == item["passages"]


def test_search_tokens_attach_the_best_passages_from_the_whole_folder(tmp_path: Path) -> None:
    _put(tmp_path, "八字.md", LONG_NOTE)
    _put(tmp_path, "紫微.md", "命宫见紫微，主一生富贵。")
    context = uk.build_context(_settings(tmp_path), ["?羊刃 驾杀", "?根本没有的词"], tool_name="chart")
    assert [(e["id"], e["selection"]) for e in context["entries"]] == [("八字", "search")]
    assert context["entries"][0]["matched_by"] == "search:羊刃 驾杀" and "羊刃驾杀" in context["entries"][0]["text"]
    assert context["missing"] == ["?根本没有的词"]


# ── 精读翻页 ──────────────────────────────────────────────────────────────


def test_read_pages_by_file_line_numbers_with_an_outline(tmp_path: Path) -> None:
    _put(tmp_path, "八字.md", LONG_NOTE)
    settings = _settings(tmp_path)
    whole = uk.read_entry(settings, "八字")
    assert "truncated" not in whole and whole["first_line"] == 6
    outline = {o["heading"]: o["line"] for o in whole["outline"]}
    assert outline == {"总论": 6, "七杀格": 10, "伤官格": 14}
    page = uk.read_entry(settings, "八字", from_line=outline["七杀格"], max_lines=2)
    assert page["text"].startswith("## 七杀格") and page["line_range"] == "10-11"
    assert page["truncated"] is True and page["next_from_line"] == 12 and "第10–11行" in page["citation"]


# ── 门面 ────────────────────────────────────────────────────────────────


def test_knowledge_search_facade_fuses_bundled_and_user_results_and_pages(tmp_path: Path) -> None:
    from horosa_skill.service import HorosaSkillService

    _put(tmp_path, "门.md", "休门：我的笔记里休门主休养。")
    service = HorosaSkillService(_settings(tmp_path))
    result = service.knowledge_search({"query": "休门", "limit": 3})
    domains = {m["domain"] for m in result["matches"]}
    assert "user" in domains and domains - {"user"}  # 内置与自备同在一个排好序的列表里（RRF 融合）
    assert result["next_offset"] == 3 and "how_to_read" in result
    second = service.knowledge_search({"query": "休门", "limit": 3, "offset": 3})
    assert not {(m["domain"], m["key"]) for m in second["matches"]} & {(m["domain"], m["key"]) for m in result["matches"]}
    only_mine = service.knowledge_search({"query": "休门", "domain": "user"})
    assert {m["domain"] for m in only_mine["matches"]} == {"user"}


def test_a_term_found_in_most_passages_still_scores_above_zero(tmp_path: Path) -> None:
    # FTS5 自带的 bm25() 对出现在过半块里的词把 IDF 压到 1e-6：两块的小笔记里查「休门」得 0.0 分，看着像没命中。
    _put(tmp_path, "a.md", "## 七杀格\n\n七杀有制，化为权柄。\n\n## 休门\n\n休门在坎宫，休门主休养。")
    match = uk.search_user(_settings(tmp_path), "休门")["matches"][0]
    assert match["heading"] == "休门" and match["score"] > 0.3
    # 西文按整词：jupiter 不该命中 jupiterian。
    _put(tmp_path, "b.md", "Jupiterian themes only.")
    assert uk.search_user(_settings(tmp_path), "jupiter")["matches"] == []
