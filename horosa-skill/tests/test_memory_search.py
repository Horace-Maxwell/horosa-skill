"""记忆检索：每个 run 一份检索文档（人会搜的字），全库可搜；还没读进索引的盘面正文有多少要如实说。

台账：docs/LESSONS.md v0.47.2-dev「文本检索只看最近 400 条」，v0.50.0-dev「检索搜的是文件字节」。
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

import pytest

from fakes import FakeClient, FakeJsClient
from horosa_skill.config import Settings
from horosa_skill.memory import store as store_module
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

NOISE = 450  # 比旧的深扫窗口（400）多：老实现在这里漏


def _settings(tmp_path: Path) -> Settings:
    return Settings(server_root="http://127.0.0.1:9", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")


def _store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(_settings(tmp_path))


def _seed(store: MemoryStore, rows: list[dict]) -> list[str]:
    """绕过 store 直接入库（批量比走 create_run 快两个量级；也是旧版本进程写的行的样子）：检索文档由查询前的补齐建起来。
    created_at 递增：列表靠后的更新。"""
    ids = []
    with store.connect() as conn:
        for index, row in enumerate(rows):
            run_id = uuid.uuid4().hex
            stamp = f"2026-{(index // 28800) % 12 + 1:02d}-{(index // 1440) % 28 + 1:02d}T{(index // 60) % 24:02d}:{index % 60:02d}:00+00:00"
            conn.execute(
                "INSERT INTO runs (id, entrypoint, query_text, user_question_text, ai_answer_text, subject_json, created_at, updated_at)"
                " VALUES (?, 'tool', ?, ?, ?, '{}', ?, ?)",
                (run_id, row.get("question"), row.get("question"), row.get("answer"), stamp, stamp),
            )
            if row.get("tool"):
                conn.execute(
                    "INSERT INTO tool_calls (run_id, tool_name, ok, input_json, summary_json, warnings_json, created_at)"
                    " VALUES (?, ?, 1, '{}', '[]', '[]', ?)",
                    (run_id, row["tool"], stamp),
                )
            ids.append(run_id)
        conn.commit()
    return ids


def _old_needle_then_noise(tmp_path: Path, needle_row: dict, *, noise: int = NOISE) -> tuple[MemoryStore, str]:
    store = _store(tmp_path)
    ids = _seed(store, [needle_row] + [{"question": f"第{i}次提问"} for i in range(noise)])
    return store, ids[0]


def _ids(rows: list[dict]) -> list[str]:
    return [row["run_id"] for row in rows]


def _chart_run(store: MemoryStore, *, question: str = "普通问题", export_text: str = "盘面正文", tool: str = "chart") -> str:
    run_id = store.create_run(entrypoint="tool", query_text=question, group_id="g")
    store.record_tool_result(
        run_id=run_id, tool_name=tool, ok=True, input_normalized={"date": "1990-05-03"},
        envelope_dict={"ok": True, "tool": tool, "data": {"export_snapshot": {"export_text": export_text}}},
        summary=[], warnings=[], error=None,
    )
    return run_id


def test_an_old_run_is_found_by_its_question(tmp_path: Path) -> None:
    """2026-11-06 实测：3000 条更新的 run 之后，FTS 表能查到，`query_runs` 却回 0 条。"""
    store, old = _old_needle_then_noise(tmp_path, {"question": "苍穹之眼的提问"})
    assert _ids(store.query_runs(text="苍穹之眼", limit=20, include_payload=False)) == [old]


def test_an_old_run_is_found_by_its_answer(tmp_path: Path) -> None:
    store, old = _old_needle_then_noise(tmp_path, {"question": "普通问题", "answer": "结论是宜守不宜攻的那一份"})
    assert _ids(store.query_runs(text="宜守不宜攻", limit=20, include_payload=False)) == [old]


def test_a_two_character_query_reaches_old_runs(tmp_path: Path) -> None:
    """trigram 查不了两字词，而工具说明的例子就是 `{"text": "事业"}`。"""
    store, old = _old_needle_then_noise(tmp_path, {"question": "看看财运"})
    assert _ids(store.query_runs(text="财运", limit=20, include_payload=False)) == [old]


def test_search_survives_a_build_without_the_fts_table(tmp_path: Path) -> None:
    """环境缺 FTS5 时 `_ensure_fts` 跳过（`_fts_ok=False`），检索退回逐行比，结果一样。"""
    store, old = _old_needle_then_noise(tmp_path, {"question": "苍穹之眼的提问"})
    with store.connect() as conn:
        for trigger in ("run_search_ai", "run_search_ad", "run_search_au"):
            conn.execute(f"DROP TRIGGER {trigger}")
        conn.execute("DROP TABLE run_search_fts")
        conn.commit()
    store._fts_ok = False
    assert _ids(store.query_runs(text="苍穹之眼", limit=20, include_payload=False)) == [old]
    assert _ids(store.query_runs(text="苍穹 眼的提", limit=20, include_payload=False)) == [old]


def test_like_metacharacters_in_a_short_query_are_literal(tmp_path: Path) -> None:
    store = _store(tmp_path)
    ids = _seed(store, [{"question": "涨了5%左右"}, {"question": "涨了55左右"}])
    assert _ids(store.query_runs(text="5%", limit=20, include_payload=False)) == [ids[0]]


@pytest.mark.parametrize("pattern", ["*", "a*b", "[x]", "?"])
def test_glob_metacharacters_in_a_long_query_are_literal(tmp_path: Path, pattern: str) -> None:
    store = _store(tmp_path)
    ids = _seed(store, [{"question": f"含有 {pattern} 的问题文本"}, {"question": "完全不同的问题"}])
    assert _ids(store.query_runs(text=f"有 {pattern} 的", limit=20, include_payload=False)) == [ids[0]]


@pytest.mark.parametrize("filters", [{"tool": "qimen"}, {"entity": "没有这个人"}, {"before": "2020-01-01"}])
def test_filters_still_apply_to_indexed_hits(tmp_path: Path, filters: dict) -> None:
    store, _ = _old_needle_then_noise(tmp_path, {"question": "苍穹之眼的提问", "tool": "chart"})
    assert store.query_runs(text="苍穹之眼", limit=20, include_payload=False, **filters) == []


def test_results_stay_newest_first_and_respect_limit_and_offset(tmp_path: Path) -> None:
    store = _store(tmp_path)
    ids = _seed(store, [{"question": f"苍穹之眼第{i}问"} for i in range(5)] + [{"question": f"第{i}次提问"} for i in range(NOISE)])
    newest_first = list(reversed(ids[:5]))
    assert _ids(store.query_runs(text="苍穹之眼", limit=20, include_payload=False)) == newest_first
    assert _ids(store.query_runs(text="苍穹之眼", limit=2, include_payload=False)) == newest_first[:2]
    assert _ids(store.query_runs(text="苍穹之眼", limit=2, offset=2, include_payload=False)) == newest_first[2:4]


def test_text_inside_an_artifact_is_found_at_any_depth(tmp_path: Path) -> None:
    """盘面正文进检索文档：不再只深扫最近的窗口。老产物只有 `snapshot_text` 时取它。"""
    store = _store(tmp_path)
    run_id = store.create_run(entrypoint="tool", query_text="普通问题", group_id="g")
    store.record_tool_result(run_id=run_id, tool_name="chart", ok=True, input_normalized={},
                             envelope_dict={"data": {"snapshot_text": "只在盘面正文里的玄武七宿"}}, summary=[], warnings=[], error=None)
    _seed(store, [{"question": f"第{i}次提问"} for i in range(NOISE)])
    assert _ids(store.query_runs(text="玄武七宿", limit=20, include_payload=False)) == [run_id]


# ── 文档里只有人会搜的字（M1）────────────────────────────────────────────────────────


def test_ids_paths_timestamps_and_json_keys_match_nothing(tmp_path: Path) -> None:
    """此前深扫把整份产物文件、路径、run id 当字符串比：搜 `json`、`ok`、日期、id 都「命中」每一条。"""
    store = _store(tmp_path)
    run_id = _chart_run(store)
    record = store.query_runs(run_id=run_id, include_payload=False)[0]
    artifact = Path(record["artifacts"][-1]["path"])
    for needle in (run_id, run_id[:8], "json", "tool_result", "input_normalized", "record_meta", "export_text",
                   record["created_at"][:10], artifact.parent.name, "runs", "trace_id", "true"):
        assert store.query_runs(text=needle, include_payload=False) == [], needle


def test_what_a_person_searches_for_is_found(tmp_path: Path) -> None:
    store = _store(tmp_path)
    run_id = _chart_run(store, question="王小明的事业运", export_text="命宫 太阳星 庙旺", tool="bazi_birth")
    store.record_entities(run_id, [{"entity_type": "subject", "entity_key": "王小明", "display_name": "王小明"}])
    store.attach_ai_response(run_id=run_id, ai_answer="宜守不宜攻")
    for needle in ("事业运", "太阳星", "宜守不宜攻", "王小明", "bazi_birth", "八字", "horosa_cn_bazi_birth", "BAZI_BIRTH"):
        assert _ids(store.query_runs(text=needle, include_payload=False)) == [run_id], needle


def test_space_separated_words_must_all_match(tmp_path: Path) -> None:
    """此前整串当一个子串：`王 小明`、`婚姻 李四` 一条都搜不到。"""
    store = _store(tmp_path)
    both = _seed(store, [{"question": "李四问婚姻"}])[0]
    _seed(store, [{"question": "李四问事业"}, {"question": "张三问婚姻"}])
    assert _ids(store.query_runs(text="婚姻 李四", include_payload=False)) == [both]
    assert _ids(store.query_runs(text="李四，婚姻", include_payload=False)) == [both]
    assert _ids(store.query_runs(text="李 四问婚", include_payload=False)) == [both]


@pytest.mark.parametrize(("stored", "query"), [("事业运势", "事業"), ("事業運勢", "事业"), ("ＡＢＣ盘", "abc"), ("Saturn Return", "saturn return")])
def test_traditional_simplified_width_and_case_fold(tmp_path: Path, stored: str, query: str) -> None:
    store = _store(tmp_path)
    run_id = _seed(store, [{"question": stored}])[0]
    assert _ids(store.query_runs(text=query, include_payload=False)) == [run_id]


def test_a_document_written_by_an_older_process_is_brought_up_to_date(tmp_path: Path) -> None:
    """旧版本进程（或别的工具）改了 runs 行却不碰检索文档：`stamp` 对不上，查询前重建 head。"""
    store = _store(tmp_path)
    run_id = _seed(store, [{"question": "原来的问题"}])[0]
    assert _ids(store.query_runs(text="原来的问题", include_payload=False)) == [run_id]
    with store.connect() as conn:
        conn.execute("UPDATE runs SET ai_answer_text = '后来补的答案', updated_at = '2030-01-01T00:00:00+00:00' WHERE id = ?", (run_id,))
        conn.commit()
    assert _ids(store.query_runs(text="后来补的答案", include_payload=False)) == [run_id]


# ── 翻页（M12）────────────────────────────────────────────────────────────────────────


def test_paging_never_repeats_or_skips_while_usage_changes(tmp_path: Path) -> None:
    """此前 text 结果按点用次数重排：翻页之间有人点开一条，下一页就重复 / 漏掉一条。顺序现在只看时间。"""
    store = _store(tmp_path)
    ids = _seed(store, [{"question": f"八字第{i}问"} for i in range(9)])
    seen: list[str] = []
    for page in range(3):
        rows = store.query_runs(text="八字", limit=3, offset=page * 3, include_payload=False)
        seen += _ids(rows)
        store.query_runs(run_id=ids[page])  # 翻页之间点开一条还没翻到的（最老的几条）
    assert seen == list(reversed(ids))


def test_same_second_runs_keep_a_total_order(tmp_path: Path) -> None:
    store = _store(tmp_path)
    ids = [store.create_run(entrypoint="tool", query_text=f"同一秒 {i}", group_id="g") for i in range(6)]
    with store.connect() as conn:
        conn.execute("UPDATE runs SET created_at = '2026-01-01T00:00:00+00:00'")
        conn.commit()
    pages = [_ids(store.query_runs(text="同一秒", limit=2, offset=offset, include_payload=False)) for offset in (0, 2, 4)]
    assert sum(pages, []) == list(reversed(ids))


# ── 还没读进索引的正文：如实说 ───────────────────────────────────────────────────────


def _pending_bodies(store: MemoryStore, count: int, *, tool: str = "chart") -> list[str]:
    ids = [_chart_run(store, export_text=f"正文{i}", tool=tool) for i in range(count)]
    with store.connect() as conn:  # 模拟老库升级：文档有了 head，正文还在产物文件里
        conn.execute("UPDATE run_search SET body = '', state = 0")
        conn.commit()
    return ids


def test_not_scanned_counts_bodies_not_yet_indexed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _store(tmp_path)
    _pending_bodies(store, 5)
    monkeypatch.setattr(store_module, "BODY_BACKFILL_BUDGET_SECONDS", 0.0)
    report: dict = {}
    store.query_runs(text="不存在的词组", limit=20, include_payload=False, scan_report=report)
    assert report == {"not_scanned": 4}, "预算为 0 时一次只读一个 run 的正文"


def test_bodies_are_backfilled_and_then_found(tmp_path: Path) -> None:
    store = _store(tmp_path)
    ids = _pending_bodies(store, 3)
    report: dict = {}
    assert _ids(store.query_runs(text="正文1", include_payload=False, scan_report=report)) == [ids[1]]
    assert report["not_scanned"] == 0


def test_filters_narrow_what_counts_as_unscanned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _store(tmp_path)
    _pending_bodies(store, 4, tool="qimen")
    _pending_bodies(store, 2, tool="chart")
    with store.connect() as conn:
        conn.execute("UPDATE run_search SET body = '', state = 0")
        conn.commit()
    monkeypatch.setattr(store_module, "BODY_BACKFILL_BUDGET_SECONDS", 0.0)
    report: dict = {}
    store.query_runs(text="不存在的词组", tool="qimen", limit=20, include_payload=False, scan_report=report)
    assert report["not_scanned"] == 4, "只数过滤后的 run（读掉的那一个是最新的 chart）"


def test_query_memory_tells_the_caller_what_it_did_not_search(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(tmp_path)
    store = MemoryStore(settings)
    _pending_bodies(store, 8)
    monkeypatch.setattr(store_module, "BODY_BACKFILL_BUDGET_SECONDS", 0.0)
    service = HorosaSkillService(settings, client=FakeClient(), store=store, js_client=FakeJsClient())

    missed = service.query_memory({"text": "不存在的词组", "limit": 20})
    assert missed["not_scanned"] == 7
    assert any("7" in line and "memory rebuild" in line for line in missed["summary"])

    browse = service.query_memory({"limit": 5})
    assert browse["not_scanned"] == 0
    assert len(browse["summary"]) == 1


# ── 老库升级（M1 / M5 的迁移）─────────────────────────────────────────────────────────

_OLDEST_SCHEMA = """
CREATE TABLE runs (id TEXT PRIMARY KEY, entrypoint TEXT NOT NULL, query_text TEXT, subject_json TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE tool_calls (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, tool_name TEXT NOT NULL, ok INTEGER NOT NULL,
  input_json TEXT NOT NULL, summary_json TEXT NOT NULL, warnings_json TEXT NOT NULL, error_json TEXT, created_at TEXT NOT NULL);
CREATE TABLE artifacts (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, tool_call_id INTEGER, tool_name TEXT NOT NULL,
  kind TEXT NOT NULL, path TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE entities (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, entity_type TEXT NOT NULL, entity_key TEXT NOT NULL,
  display_name TEXT NOT NULL, metadata_json TEXT NOT NULL, created_at TEXT NOT NULL);
"""

# v0.49.0 的检索索引：只有问题与答案三列，不折叠繁简。
_V049_FTS = """
CREATE VIRTUAL TABLE runs_fts USING fts5(query_text, user_question_text, ai_answer_text, content='runs', content_rowid='rowid', tokenize='trigram');
CREATE TRIGGER runs_fts_ai AFTER INSERT ON runs BEGIN
  INSERT INTO runs_fts(rowid, query_text, user_question_text, ai_answer_text) VALUES (new.rowid, new.query_text, new.user_question_text, new.ai_answer_text);
END;
CREATE TRIGGER runs_fts_ad AFTER DELETE ON runs BEGIN
  INSERT INTO runs_fts(runs_fts, rowid, query_text, user_question_text, ai_answer_text) VALUES ('delete', old.rowid, old.query_text, old.user_question_text, old.ai_answer_text);
END;
CREATE TRIGGER runs_fts_au AFTER UPDATE ON runs BEGIN
  INSERT INTO runs_fts(runs_fts, rowid, query_text, user_question_text, ai_answer_text) VALUES ('delete', old.rowid, old.query_text, old.user_question_text, old.ai_answer_text);
  INSERT INTO runs_fts(rowid, query_text, user_question_text, ai_answer_text) VALUES (new.rowid, new.query_text, new.user_question_text, new.ai_answer_text);
END;
"""


def _old_store_on_disk(tmp_path: Path, *, with_v049_fts: bool) -> Path:
    folder = tmp_path / "runs" / "2025" / "01" / "02"
    folder.mkdir(parents=True)
    run_id = "a" * 32
    artifact = folder / f"{run_id}_chart_1.json"
    artifact.write_text(json.dumps({"ok": True, "tool": "chart", "data": {"export_snapshot": {"export_text": "老盘 太阳在狮子"}}},
                                   ensure_ascii=False, indent=2), encoding="utf-8")
    conn = sqlite3.connect(tmp_path / "memory.db")
    conn.executescript(_OLDEST_SCHEMA)
    if with_v049_fts:
        for column in ("user_question_text", "ai_answer_text", "ai_answer_json", "answer_meta_json", "group_id", "usage_count", "last_used_at"):
            conn.execute(f"ALTER TABLE runs ADD COLUMN {column} TEXT")
        conn.executescript(_V049_FTS)
    conn.execute("INSERT INTO runs (id, entrypoint, query_text, subject_json, created_at, updated_at) VALUES (?, 'tool', '給張三看星盤', '{}',"
                 " '2025-01-02T03:04:05+00:00', '2025-01-02T03:04:05+00:00')", (run_id,))
    conn.execute("INSERT INTO tool_calls (run_id, tool_name, ok, input_json, summary_json, warnings_json, created_at)"
                 " VALUES (?, 'chart', 1, '{}', '[]', '[]', '2025-01-02T03:04:05+00:00')", (run_id,))
    conn.execute("INSERT INTO artifacts (run_id, tool_call_id, tool_name, kind, path, created_at) VALUES (?, 1, 'chart', 'tool_result', ?,"
                 " '2025-01-02T03:04:05+00:00')", (run_id, str(artifact)))
    conn.execute("INSERT INTO entities (run_id, entity_type, entity_key, display_name, metadata_json, created_at)"
                 " VALUES (?, 'birthdate', '1980-01-01', '1980-01-01', '{}', '2025-01-02T03:04:05+00:00')", (run_id,))
    conn.commit()
    conn.close()
    return artifact


@pytest.mark.parametrize("with_v049_fts", [False, True], ids=["oldest-schema", "v0.49.0-schema"])
def test_an_existing_store_migrates_and_searches_the_new_way(tmp_path: Path, with_v049_fts: bool) -> None:
    _old_store_on_disk(tmp_path, with_v049_fts=with_v049_fts)
    store = _store(tmp_path)
    assert store.init_error is None
    run_id = "a" * 32
    assert _ids(store.query_runs(text="张三 星盘", include_payload=False)) == [run_id], "繁简折叠 + AND"
    assert _ids(store.query_runs(text="太阳在狮子", include_payload=False)) == [run_id], "正文从产物文件回填"
    assert _ids(store.query_runs(text="星图", include_payload=False)) == [], "chart 的中文名在 head 里，但「星图」不是它"
    assert _ids(store.query_runs(entity="1980/1/1", include_payload=False)) == [run_id], "老实体补了匹配键"
    with store.connect() as conn:
        assert conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'runs_fts'").fetchone() is None, "旧索引与它的触发器撤掉"
        assert conn.execute("SELECT COUNT(*) FROM run_search WHERE state = 0").fetchone()[0] == 0
    store.attach_ai_response(run_id=run_id, ai_answer="迁移后写回的答案")
    assert _ids(store.query_runs(text="迁移后写回", include_payload=False)) == [run_id]
    assert MemoryStore(_settings(tmp_path)).init_error is None, "迁移幂等：再开一次照常"
