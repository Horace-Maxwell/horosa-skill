"""记忆检索：问题与答案全库可搜，盘面正文的深扫有窗口，窗口外有多少条要如实说。

台账：docs/LESSONS.md v0.47.2-dev「文本检索只看最近 400 条」。
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from fakes import FakeClient, FakeJsClient
from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

WINDOW = 400  # limit=20 时的深扫窗口：candidate_limit = max(20 * 20, 200)


def _store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(Settings(server_root="http://127.0.0.1:9", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs"))


def _seed(store: MemoryStore, rows: list[dict]) -> list[str]:
    """直接入库（批量比走 create_run 快两个量级），FTS 由触发器照常同步。created_at 递增：列表靠后的更新。"""
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


def _old_needle_then_noise(tmp_path: Path, needle_row: dict, *, noise: int = WINDOW + 50) -> tuple[MemoryStore, str]:
    store = _store(tmp_path)
    ids = _seed(store, [needle_row] + [{"question": f"第{i}次提问"} for i in range(noise)])
    return store, ids[0]


def test_an_old_run_is_found_by_its_question(tmp_path: Path) -> None:
    """2026-11-06 实测：3000 条更新的 run 之后，FTS 表能查到，`query_runs` 却回 0 条。"""
    store, old = _old_needle_then_noise(tmp_path, {"question": "苍穹之眼的提问"})
    assert [r["run_id"] for r in store.query_runs(text="苍穹之眼", limit=20, include_payload=False)] == [old]


def test_an_old_run_is_found_by_its_answer(tmp_path: Path) -> None:
    store, old = _old_needle_then_noise(tmp_path, {"question": "普通问题", "answer": "结论是宜守不宜攻的那一份"})
    assert [r["run_id"] for r in store.query_runs(text="宜守不宜攻", limit=20, include_payload=False)] == [old]


def test_a_two_character_query_reaches_old_runs(tmp_path: Path) -> None:
    """trigram 查不了两字词，而工具说明的例子就是 `{"text": "事业"}`。"""
    store, old = _old_needle_then_noise(tmp_path, {"question": "看看财运"})
    assert [r["run_id"] for r in store.query_runs(text="财运", limit=20, include_payload=False)] == [old]


def test_search_survives_a_build_without_the_fts_table(tmp_path: Path) -> None:
    """环境缺 FTS5 时 `_ensure_fts` 静默跳过，检索不能因此回到只看窗口。"""
    store, old = _old_needle_then_noise(tmp_path, {"question": "苍穹之眼的提问"})
    with store.connect() as conn:
        for trigger in ("runs_fts_ai", "runs_fts_ad", "runs_fts_au"):
            conn.execute(f"DROP TRIGGER {trigger}")
        conn.execute("DROP TABLE runs_fts")
        conn.commit()
    assert [r["run_id"] for r in store.query_runs(text="苍穹之眼", limit=20, include_payload=False)] == [old]


def test_like_metacharacters_in_a_short_query_are_literal(tmp_path: Path) -> None:
    store = _store(tmp_path)
    ids = _seed(store, [{"question": "涨了5%左右"}, {"question": "涨了55左右"}])
    assert [r["run_id"] for r in store.query_runs(text="5%", limit=20, include_payload=False)] == [ids[0]]


@pytest.mark.parametrize("filters", [{"tool": "qimen"}, {"entity": "没有这个人"}, {"before": "2020-01-01"}])
def test_filters_still_apply_to_indexed_hits(tmp_path: Path, filters: dict) -> None:
    store, _ = _old_needle_then_noise(tmp_path, {"question": "苍穹之眼的提问", "tool": "chart"})
    assert store.query_runs(text="苍穹之眼", limit=20, include_payload=False, **filters) == []


def test_results_stay_newest_first_and_respect_limit_and_offset(tmp_path: Path) -> None:
    store = _store(tmp_path)
    ids = _seed(store, [{"question": f"苍穹之眼第{i}问"} for i in range(5)] + [{"question": f"第{i}次提问"} for i in range(WINDOW + 50)])
    newest_first = list(reversed(ids[:5]))
    assert [r["run_id"] for r in store.query_runs(text="苍穹之眼", limit=20, include_payload=False)] == newest_first
    assert [r["run_id"] for r in store.query_runs(text="苍穹之眼", limit=2, include_payload=False)] == newest_first[:2]
    assert [r["run_id"] for r in store.query_runs(text="苍穹之眼", limit=2, offset=2, include_payload=False)] == newest_first[2:4]


def test_text_inside_an_artifact_is_still_found_within_the_window(tmp_path: Path) -> None:
    """盘面正文不进 FTS，靠窗口内深扫：这条语义不能丢。"""
    store = _store(tmp_path)
    run_id = store.create_run(entrypoint="tool", query_text="普通问题", group_id="g")
    store.record_tool_result(run_id=run_id, tool_name="chart", ok=True, input_normalized={},
                             envelope_dict={"data": {"snapshot_text": "只在盘面正文里的玄武七宿"}}, summary=[], warnings=[], error=None)
    assert [r["run_id"] for r in store.query_runs(text="玄武七宿", limit=20, include_payload=False)] == [run_id]


def test_not_scanned_counts_the_runs_past_the_window(tmp_path: Path) -> None:
    store, _ = _old_needle_then_noise(tmp_path, {"question": "普通问题"})
    report: dict = {}
    store.query_runs(text="不存在的词组", limit=20, include_payload=False, scan_report=report)
    assert report == {"deep_scan_window": WINDOW, "not_scanned": 51}


def test_nothing_is_reported_unscanned_when_the_window_covers_everything(tmp_path: Path) -> None:
    store, _ = _old_needle_then_noise(tmp_path, {"question": "普通问题"}, noise=10)
    report: dict = {}
    store.query_runs(text="不存在的词组", limit=20, include_payload=False, scan_report=report)
    assert report["not_scanned"] == 0


def test_filters_narrow_what_counts_as_unscanned(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed(store, [{"question": "q", "tool": "chart"} for _ in range(WINDOW + 50)] + [{"question": "q", "tool": "qimen"} for _ in range(WINDOW + 3)])
    report: dict = {}
    store.query_runs(text="不存在的词组", tool="qimen", limit=20, include_payload=False, scan_report=report)
    assert report["not_scanned"] == 3, "只数过滤后的 run"


def test_query_memory_tells_the_caller_what_it_did_not_search(tmp_path: Path) -> None:
    settings = Settings(server_root="http://127.0.0.1:9", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    store = MemoryStore(settings)
    _seed(store, [{"question": f"第{i}次提问"} for i in range(WINDOW + 7)])
    service = HorosaSkillService(settings, client=FakeClient(), store=store, js_client=FakeJsClient())

    missed = service.query_memory({"text": "不存在的词组", "limit": 20})
    assert missed["not_scanned"] == 7
    assert any("7" in line and "盘面正文" in line for line in missed["summary"])

    browse = service.query_memory({"limit": 5})
    assert browse["not_scanned"] == 0
    assert len(browse["summary"]) == 1
