import json
from pathlib import Path

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore


def test_memory_store_writes_artifact(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    run_id = store.create_run(entrypoint="tool", query_text="test", group_id="group-1")
    ref = store.record_tool_result(
        run_id=run_id,
        tool_name="chart",
        ok=True,
        input_normalized={"date": "1990-01-01"},
        envelope_dict={"ok": True, "tool": "chart"},
        summary=["ok"],
        warnings=[],
        error=None,
        trace_id="trace-1",
        group_id="group-1",
        evaluation_case_id="case-1",
    )
    assert ref.run_id == run_id
    assert ref.tool_name == "chart"
    assert (tmp_path / "runs").exists()
    artifact_path = Path(ref.artifact_path)
    assert artifact_path.parent.parent.parent.parent == (tmp_path / "runs")
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["tool"] == "chart"
    assert artifact["record_meta"]["schema"] == "horosa.skill.record.v1"
    assert artifact["record_meta"]["trace_id"] == "trace-1"
    assert artifact["record_meta"]["group_id"] == "group-1"
    assert artifact["record_meta"]["evaluation_case_id"] == "case-1"
    assert artifact["conversation"]["user_question"] == "test"

    queried = store.query_runs(tool="chart", include_payload=True)
    assert queried[0]["artifacts"][0]["payload"]["tool"] == "chart"
    assert queried[0]["user_question"] == "test"
    assert queried[0]["group_id"] == "group-1"
    assert queried[0]["tool_calls"][0]["trace_id"] == "trace-1"
    manifest = [item for item in queried[0]["artifacts"] if item["kind"] == "run_manifest"]
    assert manifest
    assert manifest[0]["payload"]["kind"] == "horosa.skill.run.manifest"
    manifest_tool_artifact = next(item for item in manifest[0]["payload"]["artifacts"] if item["kind"] == "tool_result")
    assert manifest_tool_artifact["exists"] is True
    assert manifest_tool_artifact["file_size"] > 0
    assert manifest_tool_artifact["sha256"]
    assert manifest[0]["payload"]["artifact_summary"]["counts_by_kind"]["tool_result"] == 1


def test_memory_store_attach_ai_response_updates_artifacts_and_manifest(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    run_id = store.create_run(entrypoint="dispatch", query_text="问事业", subject={"name": "甲"}, group_id="dispatch-group")
    store.record_tool_result(
        run_id=run_id,
        tool_name="chart",
        ok=True,
        input_normalized={"date": "1990-01-01"},
        envelope_dict={"ok": True, "tool": "chart", "data": {}},
        summary=["ok"],
        warnings=[],
        error=None,
        trace_id="trace-chart",
        group_id="dispatch-group",
    )

    result = store.attach_ai_response(
        run_id=run_id,
        user_question="我今年事业如何？",
        ai_answer="整体先抑后扬。",
        ai_answer_structured={"tone": "mixed"},
        answer_meta={"model": "test"},
    )

    assert result["ok"] is True
    queried = store.query_runs(tool="chart", include_payload=True)
    assert queried[0]["user_question"] == "我今年事业如何？"
    assert queried[0]["ai_answer_text"] == "整体先抑后扬。"
    assert queried[0]["ai_answer_structured"] == {"tone": "mixed"}
    artifact_payload = queried[0]["artifacts"][0]["payload"]
    assert artifact_payload["conversation"]["ai_answer_text"] == "整体先抑后扬。"
    manifest = [item for item in queried[0]["artifacts"] if item["kind"] == "run_manifest"][0]["payload"]
    assert manifest["run"]["ai_answer_text"] == "整体先抑后扬。"
    assert manifest["run"]["group_id"] == "dispatch-group"
    assert manifest["artifact_summary"]["total"] == len(manifest["artifacts"])
    assert all(item["exists"] is True for item in manifest["artifacts"])
    assert all(item["file_size"] > 0 for item in manifest["artifacts"])
    assert all(item["sha256"] for item in manifest["artifacts"])
    exact = store.query_runs(run_id=run_id, include_payload=True)
    assert len(exact) == 1
    assert exact[0]["run_id"] == run_id


# ── v0.33.0 批 II-1 · SQLite 分类恢复（照 codex state_db_recovery 形状）─────────────


def test_corrupt_db_is_quarantined_and_rebuilt(tmp_path) -> None:
    """坏库（malformed）→ 隔离 .corrupt-<ts>.bak + 重建空库 + 痕迹入 corruption_recovery，库可用。"""
    db = tmp_path / "memory.db"
    db.write_bytes(b"this is not a sqlite database, definitely garbage " * 20)
    (tmp_path / "memory.db-wal").write_bytes(b"wal junk")
    settings = Settings(server_root="http://127.0.0.1:9999", db_path=db, output_dir=tmp_path / "runs")
    store = MemoryStore(settings)
    assert store.corruption_recovery is not None
    backup = Path(store.corruption_recovery["backup"])
    assert backup.exists() and backup.name.startswith("memory.db.corrupt-") and backup.name.endswith(".bak")
    # -wal/-shm 隔离是尽力而为：SQLite 在失败打开期间可能已把无效 -wal 自行清掉。
    # 硬约束 = 主库已隔离 + 新库旁不残留旧 -wal（要么随隔离走了，要么被 SQLite 清了）。
    leftover_wal = tmp_path / "memory.db-wal"
    assert (not leftover_wal.exists()) or leftover_wal.stat().st_size == 0 or Path(f"{backup}-wal").exists()
    run_id = store.create_run(entrypoint="tool", query_text="after recovery", group_id="g")
    assert run_id
    check = store.integrity_check()
    assert check["ok"] is True
    assert check["recovered_from_corruption"]["backup"] == str(backup)


def test_locked_error_is_not_classified_as_corruption() -> None:
    import sqlite3

    from horosa_skill.memory.store import _is_corruption_error

    assert _is_corruption_error(sqlite3.OperationalError("database is locked")) is False
    assert _is_corruption_error(sqlite3.DatabaseError("database disk image is malformed")) is True
    assert _is_corruption_error(sqlite3.DatabaseError("file is not a database")) is True
    assert _is_corruption_error(sqlite3.OperationalError("no such table: runs")) is False


def test_integrity_check_ok_on_fresh_store(tmp_path) -> None:
    settings = Settings(server_root="http://127.0.0.1:9999", db_path=tmp_path / "m.db", output_dir=tmp_path / "runs")
    check = MemoryStore(settings).integrity_check()
    assert check == {"ok": True, "detail": ["ok"]}


# ── v0.33.0 批 II-4 · 使用度/双谓词/prune ─────────────────────────────────────────


def _store_with_run(tmp_path, *, ok=True, with_artifact=True):
    settings = Settings(server_root="http://127.0.0.1:9999", db_path=tmp_path / "m.db", output_dir=tmp_path / "runs")
    store = MemoryStore(settings)
    run_id = store.create_run(entrypoint="tool", query_text="八字 测试", group_id="g")
    store.record_tool_result(
        run_id=run_id, tool_name="chart", ok=ok, input_normalized={"date": "1990-01-01"},
        envelope_dict={"ok": ok, "tool": "chart"} if with_artifact else None,
        summary=["s"], warnings=[], error=None, trace_id="t", group_id="g", evaluation_case_id=None,
    ) if with_artifact else store.record_tool_result(
        run_id=run_id, tool_name="chart", ok=ok, input_normalized={}, envelope_dict=None,
        summary=[], warnings=[], error={"code": "x"} if not ok else None, trace_id="t", group_id="g", evaluation_case_id=None,
    )
    return store, run_id


def test_usage_count_bumps_on_targeted_fetch_not_listing(tmp_path) -> None:
    store, run_id = _store_with_run(tmp_path)
    store.query_runs(limit=10)  # 浏览列表不记账
    listed = store.query_runs(limit=10)
    assert listed[0]["usage_count"] == 0
    store.query_runs(run_id=run_id)  # 点取记账
    store.query_runs(run_id=run_id)
    after = store.query_runs(limit=10)
    assert after[0]["usage_count"] == 2
    assert after[0]["last_used_at"]


def test_text_recall_ranks_used_runs_first(tmp_path) -> None:
    settings = Settings(server_root="http://127.0.0.1:9999", db_path=tmp_path / "m.db", output_dir=tmp_path / "runs")
    store = MemoryStore(settings)
    old_used = store.create_run(entrypoint="tool", query_text="八字 甲", group_id="g")
    newer = store.create_run(entrypoint="tool", query_text="八字 乙", group_id="g")
    store.query_runs(run_id=old_used)  # 老 run 被点用过
    hits = store.query_runs(text="八字", limit=10, include_payload=False)
    assert [h["run_id"] for h in hits][:2] == [old_used, newer], "点用过的排前（无 text 浏览仍纯新近序）"
    browse = store.query_runs(limit=10, include_payload=False)
    assert browse[0]["run_id"] == newer, "浏览列表保持新近序零回归"


def test_is_memory_worthy_dual_predicate(tmp_path) -> None:
    store, _ = _store_with_run(tmp_path)
    worthy = store.query_runs(limit=1)[0]
    assert store.is_memory_worthy(worthy) is True
    assert store.is_memory_worthy({"artifacts": [], "ai_answer_text": None, "tool_calls": [{"ok": 0}]}) is False
    assert store.is_memory_worthy({"artifacts": [], "ai_answer_text": "答", "tool_calls": []}) is True


def test_prune_unused_dry_run_then_delete(tmp_path) -> None:
    import sqlite3 as _sq

    store, run_id = _store_with_run(tmp_path)
    used_id = store.create_run(entrypoint="tool", query_text="被点用的", group_id="g")
    store.query_runs(run_id=used_id)
    # 把两条 run 都做旧 100 天
    with _sq.connect(store.db_path) as conn:
        conn.execute("UPDATE runs SET created_at = '2020-01-01T00:00:00+00:00'")
        conn.execute("UPDATE runs SET last_used_at = '2020-01-02T00:00:00+00:00' WHERE id = ?", (used_id,))
        conn.commit()
    dry = store.prune_unused(unused_days=30)
    assert dry["dry_run"] is True and dry["deleted"] == 0
    assert dry["candidates"] == 1 and dry["sample"] == [run_id], "点用过的 run 永不入选"
    # 裸 SQL 取产物路径——query_runs(run_id=…) 会点用记账，把候选洗出 prune 集（记账语义本身正确）。
    with _sq.connect(store.db_path) as conn:
        artifact_paths = [Path(row[0]) for row in conn.execute("SELECT path FROM artifacts WHERE run_id = ?", (run_id,))]
    real = store.prune_unused(unused_days=30, yes=True)
    assert real["deleted"] == 1 and real["dry_run"] is False
    assert store.query_runs(run_id=run_id) == []
    assert store.query_runs(run_id=used_id), "点用过的 run 保留"
    assert all(not p.exists() for p in artifact_paths), "磁盘产物随删"
