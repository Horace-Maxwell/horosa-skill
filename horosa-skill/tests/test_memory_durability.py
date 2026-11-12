"""记忆存档的持久性：`runs/` 下的产物是一次起盘唯一的完整副本，写它的每一步都不能把已有内容弄丢。

台账：docs/LESSONS.md v0.47.2-dev「答案写回把唯一一份盘面写成 0 字节」。
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pytest

from horosa_skill import fsretry
from horosa_skill.config import Settings
from horosa_skill.memory import store as store_module
from horosa_skill.memory.store import MemoryStore

TWO_MEGABYTES = "汉" * 700_000


def _settings(tmp_path: Path) -> Settings:
    return Settings(server_root="http://127.0.0.1:9", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")


def _stored_run(tmp_path: Path, *, padding: str = "") -> tuple[MemoryStore, str, Path]:
    store = MemoryStore(_settings(tmp_path))
    run_id = store.create_run(entrypoint="tool", query_text="问事业", group_id="g")
    ref = store.record_tool_result(
        run_id=run_id, tool_name="chart", ok=True, input_normalized={"date": "1990-01-01"},
        envelope_dict={"ok": True, "tool": "chart", "data": {"padding": padding}}, summary=["s"], warnings=[], error=None,
        trace_id="t", group_id="g",
    )
    return store, run_id, Path(ref.artifact_path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@contextmanager
def _file_size_capped_at(limit: int) -> Iterator[None]:
    """真实的写失败：超过上限的 write(2) 报 EFBIG（Python 启动时已忽略 SIGXFSZ），对写半截文件的效果与磁盘写满相同。"""
    resource = pytest.importorskip("resource")
    soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)
    resource.setrlimit(resource.RLIMIT_FSIZE, (limit, hard))
    try:
        yield
    finally:
        resource.setrlimit(resource.RLIMIT_FSIZE, (soft, hard))


def test_a_failed_rewrite_leaves_the_stored_chart_intact(tmp_path: Path) -> None:
    """2026-11-06 实测：12 MB 真卷写满时 record_answer 把 63 KB 的盘面写成 0 字节，重试 `ok: true` 却再也救不回来。"""
    store, run_id, artifact = _stored_run(tmp_path, padding=TWO_MEGABYTES)
    before = artifact.read_bytes()

    with _file_size_capped_at(1_000_000), pytest.raises(OSError):
        store.attach_ai_response(run_id=run_id, ai_answer="解读正文")

    assert artifact.read_bytes() == before, "写失败不能动已有产物"
    assert not [p.name for p in artifact.parent.iterdir() if p.name.endswith(".tmp")], "失败路径不留临时文件"
    store.attach_ai_response(run_id=run_id, ai_answer="解读正文")
    assert json.loads(artifact.read_text(encoding="utf-8"))["conversation"]["ai_answer_text"] == "解读正文"


def test_a_failed_replace_cleans_up_and_keeps_the_original(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """全平台：替换这一步失败（Windows 上文件开着超过重试预算）同样不动原文件、不留临时文件。"""
    store, run_id, artifact = _stored_run(tmp_path)
    before = artifact.read_bytes()

    def refuse(src: object, dst: object, **_: object) -> None:
        raise PermissionError("target is held open")

    monkeypatch.setattr(fsretry, "replace", refuse)
    with pytest.raises(PermissionError):
        store.attach_ai_response(run_id=run_id, ai_answer="解读正文")
    monkeypatch.undo()

    assert artifact.read_bytes() == before
    assert not [p.name for p in artifact.parent.iterdir() if p.name.endswith(".tmp")]


@pytest.mark.skipif(os.name == "nt", reason="Windows 上打开着的文件不能被替换；那条路径由 fsretry 的重试承担")
def test_a_reader_in_flight_keeps_a_complete_copy(tmp_path: Path) -> None:
    """改写走「新文件 + 替换」：正在读的会话拿到完整的旧内容。原地写时并发读者约 1.4% 读到 payload_error（2026-11-06 实测 26/1851）。"""
    store, run_id, artifact = _stored_run(tmp_path)
    with artifact.open("rb") as reader:
        store.attach_ai_response(run_id=run_id, ai_answer="解读正文")
        assert json.loads(reader.read())["conversation"]["ai_answer_text"] is None


def test_stored_size_and_sha_follow_a_refresh(tmp_path: Path) -> None:
    """写回答案后文件变了，库里与 manifest 里的 size / sha 必须跟上（此前停在写入时的值，manifest 自证失败）。"""
    store, run_id, artifact = _stored_run(tmp_path)
    store.attach_ai_response(run_id=run_id, ai_answer="解读正文")

    expected_sha, expected_size = _sha256(artifact), artifact.stat().st_size
    with store.connect() as conn:
        row = conn.execute("SELECT file_size, sha256 FROM artifacts WHERE kind = 'tool_result' AND run_id = ?", (run_id,)).fetchone()
    assert (row["file_size"], row["sha256"]) == (expected_size, expected_sha)

    manifest = json.loads(next(artifact.parent.glob(f"{run_id}_manifest.json")).read_text(encoding="utf-8"))
    entry = next(item for item in manifest["artifacts"] if item["kind"] == "tool_result")
    assert (entry["file_size"], entry["sha256"]) == (expected_size, expected_sha)

    shown = next(a for a in store.query_runs(run_id=run_id, include_payload=False)[0]["artifacts"] if a["kind"] == "tool_result")
    assert (shown["file_size"], shown["sha256"]) == (expected_size, expected_sha)


def test_a_refresh_leaves_rendered_reports_alone(tmp_path: Path) -> None:
    """报告是交付物（可能在 HOROSA_REPORT_OUTPUT_ROOTS 配的用户目录里），写回答案不许改写它。"""
    store, run_id, artifact = _stored_run(tmp_path)
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"schema": "horosa.skill.report.v1", "title": "报告"}, ensure_ascii=False), encoding="utf-8")
    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%PDF-1.4 not really")
    store.record_report_artifact(run_id=run_id, tool_name="chart", format_name="json", path=report)
    store.record_report_artifact(run_id=run_id, tool_name="chart", format_name="pdf", path=pdf)
    before = report.read_bytes()

    store.attach_ai_response(run_id=run_id, ai_answer="解读正文")

    assert report.read_bytes() == before
    assert json.loads(artifact.read_text(encoding="utf-8"))["conversation"]["ai_answer_text"] == "解读正文", "盘面产物照常刷新"
    reports = [a for a in store.query_runs(run_id=run_id, include_payload=False)[0]["artifacts"] if a["kind"].startswith("report_")]
    assert all(a["sha256"] == _sha256(Path(a["path"])) for a in reports)


def test_new_artifacts_keep_the_umask_mode(tmp_path: Path) -> None:
    """换写法不改权限：产物还是按 umask 建（mkstemp 的 0600 会让容器卷上的别的进程读不到）。"""
    _, _, artifact = _stored_run(tmp_path)
    probe = tmp_path / "probe"
    probe.write_text("x", encoding="utf-8")
    assert artifact.stat().st_mode == probe.stat().st_mode


def test_a_rewrite_keeps_the_mode_of_the_existing_file(tmp_path: Path) -> None:
    store, run_id, artifact = _stored_run(tmp_path)
    if os.name == "nt":
        pytest.skip("Windows 没有 POSIX 权限位")
    artifact.chmod(0o600)
    store.attach_ai_response(run_id=run_id, ai_answer="解读正文")
    assert artifact.stat().st_mode & 0o777 == 0o600


def test_the_store_has_no_in_place_writes() -> None:
    """机器守卫：memory/store.py 里任何产物写入都走原子写；`write_text` / `write_bytes` / `open(..., "w")` 回潮即红。"""
    source = Path(store_module.__file__).read_text(encoding="utf-8")
    offenders = [
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"write_text", "write_bytes"}
    ]
    assert offenders == [], f"in-place writes at lines {offenders}"


# ── 存储自身出问题：构造不许炸，写时才暴露的坏页要能自愈 ───────────────────────────────────


def _damage_table(store: MemoryStore, table: str = "tool_calls") -> None:
    """只毁一张表的根页，库头完好。建库期会读 runs / entities / run_search（补检索文档），读不到 tool_calls：
    毁 tool_calls 时构造看不出来，要等真去写它才报 malformed。"""
    with store.connect() as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        page_size = conn.execute("PRAGMA page_size").fetchone()[0]
        root = conn.execute("SELECT rootpage FROM sqlite_master WHERE name = ?", (table,)).fetchone()[0]
    with open(store.db_path, "r+b") as handle:
        handle.seek((root - 1) * page_size)
        handle.write(os.urandom(page_size))


def test_corruption_found_on_write_is_quarantined_and_the_next_write_works(tmp_path: Path) -> None:
    """2026-11-06 实测：只坏中间页时构造照常通过，之后每次存档都抛 malformed，重启也一样，只能手动搬走库。"""
    store, run_id, _ = _stored_run(tmp_path)
    _damage_table(store)

    reopened = MemoryStore(_settings(tmp_path))
    assert reopened.corruption_recovery is None, "前提：构造时看不出这种损坏，这正是要在写时处理的原因"

    with pytest.raises(sqlite3.DatabaseError):
        reopened.record_tool_result(run_id=run_id, tool_name="chart", ok=True, input_normalized={}, envelope_dict={"ok": True},
                                    summary=[], warnings=[], error=None)

    assert reopened.corruption_recovery is not None
    assert Path(reopened.corruption_recovery["backup"]).exists()
    assert reopened.create_run(entrypoint="tool", query_text="隔离后的下一次写", group_id="g")
    assert reopened.integrity_check()["ok"] is True
    # 隔离之后立刻照 runs/ 重建：坏库里的那条 run 回来了（M8）
    assert reopened.corruption_recovery["rebuild"]["complete"] is True
    assert [r["run_id"] for r in reopened.query_runs(run_id=run_id, include_payload=False)] == [run_id]


def test_corruption_seen_at_construction_is_quarantined_and_rebuilt(tmp_path: Path) -> None:
    store, run_id, _ = _stored_run(tmp_path)
    _damage_table(store, "runs")
    reopened = MemoryStore(_settings(tmp_path))
    assert reopened.corruption_recovery is not None and reopened.init_error is None
    restored = reopened.query_runs(run_id=run_id, include_payload=False)
    assert [r["run_id"] for r in restored] == [run_id]
    assert restored[0]["tool_calls"] and restored[0]["artifacts"]


def test_a_read_that_hits_corruption_moves_nothing(tmp_path: Path) -> None:
    """读到坏页不隔离：搬走整个库只为救写路径，查询失败不值这个代价。"""
    store, _, _ = _stored_run(tmp_path)
    _damage_table(store)
    with pytest.raises(sqlite3.DatabaseError):
        store.query_runs(limit=5)
    assert store.db_path.exists() and store.corruption_recovery is None
    assert not list(tmp_path.glob("memory.db.corrupt-*"))


@pytest.mark.parametrize("error", [
    sqlite3.DatabaseError("database disk image is malformed"),  # 文字像损坏，库其实是好的（别的进程刚隔离走、竞态）
    sqlite3.OperationalError("database is locked"),
])
def test_a_healthy_database_is_never_quarantined_on_write(tmp_path: Path, error: sqlite3.Error) -> None:
    store, run_id, _ = _stored_run(tmp_path)
    with pytest.raises(sqlite3.Error), store._writer():
        raise error
    assert store.corruption_recovery is None
    assert not list(tmp_path.glob("memory.db.corrupt-*"))
    assert store.query_runs(run_id=run_id), "好库原地不动"


def _make_readonly(path: Path) -> None:
    if os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0):
        pytest.skip("需要 POSIX 权限位，且不能以 root 跑")
    for suffix in ("-wal", "-shm"):
        Path(f"{path}{suffix}").unlink(missing_ok=True)
    path.chmod(0o444)
    path.parent.chmod(0o555)


def test_construction_survives_a_readonly_database_and_recovers_later(tmp_path: Path) -> None:
    """只读库：构造记下原因不抛（算盘不靠它），写时照实报错给调用方，权限恢复后自愈。"""
    home = tmp_path / "data"
    home.mkdir()
    settings = Settings(server_root="http://127.0.0.1:9", db_path=home / "memory.db", output_dir=home / "runs")
    MemoryStore(settings)
    _make_readonly(home / "memory.db")
    try:
        store = MemoryStore(settings)
        assert store.init_error and "readonly" in store.init_error
        assert store.integrity_check()["ok"] is False
        with pytest.raises(sqlite3.Error):
            store.create_run(entrypoint="tool", query_text="只读", group_id="g")
    finally:
        home.chmod(0o755)
        (home / "memory.db").chmod(0o644)
    assert store.create_run(entrypoint="tool", query_text="恢复后", group_id="g")
    assert store.init_error is None


def test_construction_survives_an_unusable_path(tmp_path: Path) -> None:
    """全平台：数据目录建不出来时，服务照样能构造、不存档的计算照样能跑。"""
    from fakes import FakeClient, FakeJsClient
    from horosa_skill.service import HorosaSkillService

    blocker = tmp_path / "a-file"
    blocker.write_text("not a directory", encoding="utf-8")
    settings = Settings(server_root="http://127.0.0.1:9", db_path=blocker / "memory.db", output_dir=blocker / "runs")

    store = MemoryStore(settings)

    assert store.init_error
    assert store.integrity_check()["ok"] is False
    service = HorosaSkillService(settings, client=FakeClient(), store=store, js_client=FakeJsClient())
    assert service.run_tool("export_registry", {}, save_result=False).ok is True


def test_a_store_whose_directory_appears_later_recovers(tmp_path: Path) -> None:
    """数据目录一开始建不出来（被一个文件占着），挪开之后下一次操作要能自愈：重试不能只重跑建表，目录也要重建。"""
    blocker = tmp_path / "a-file"
    blocker.write_text("not a directory", encoding="utf-8")
    store = MemoryStore(Settings(server_root="http://127.0.0.1:9", db_path=blocker / "memory.db", output_dir=blocker / "runs"))
    assert store.init_error

    blocker.unlink()

    assert store.create_run(entrypoint="tool", query_text="恢复后", group_id="g")
    assert store.init_error is None


def test_the_quarantine_notice_promises_no_tool_that_does_not_exist(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """此前日志说「可用 memory 工具重建索引」，这样的工具不存在。现在日志指向 `horosa-skill memory rebuild`：那条命令必须真的在。"""
    from typer.main import get_command

    from horosa_skill.surfaces.cli import app

    db = tmp_path / "memory.db"
    db.write_bytes(b"this is not a sqlite database " * 20)
    with caplog.at_level("WARNING", logger="horosa_skill.memory.store"):
        store = MemoryStore(_settings(tmp_path))
    assert store.corruption_recovery is not None
    assert "已隔离" in caplog.text
    promised = set(re.findall(r"horosa-skill memory (\w+)", caplog.text))
    assert promised, "日志要告诉用户接下来跑什么"
    memory_group = get_command(app).commands["memory"]  # type: ignore[attr-defined]
    assert promised <= set(memory_group.commands), promised


# ── 增长：省得下的先省，答过的不算没用过，用了多少看得见 ──────────────────────────────────


def _backdate(store: MemoryStore) -> None:
    with store.connect() as conn:
        conn.execute("UPDATE runs SET created_at = '2020-01-01T00:00:00+00:00'")
        conn.commit()


def test_stored_artifacts_carry_no_pretty_printing(tmp_path: Path) -> None:
    """没有人读这些文件的排版，读的都是 json.loads。一份星盘产物因此省 20%，结构多的引擎 JSON 省得更多。"""
    store, run_id, artifact = _stored_run(tmp_path)
    manifest = next(artifact.parent.glob(f"{run_id}_manifest.json"))
    for path in (artifact, manifest):
        raw = path.read_bytes()
        assert b"\n" not in raw, path.name
        assert raw == json.dumps(json.loads(raw), ensure_ascii=False, separators=(",", ":")).encode("utf-8"), path.name


def test_an_old_indented_artifact_still_reads_and_refreshes(tmp_path: Path) -> None:
    store, run_id, artifact = _stored_run(tmp_path)
    artifact.write_text(json.dumps(json.loads(artifact.read_text(encoding="utf-8")), ensure_ascii=False, indent=2), encoding="utf-8")
    store.attach_ai_response(run_id=run_id, ai_answer="解读正文")
    payload = next(a for a in store.query_runs(run_id=run_id)[0]["artifacts"] if a["kind"] == "tool_result")["payload"]
    assert payload["conversation"]["ai_answer_text"] == "解读正文" and payload["tool"] == "chart"


def test_writing_an_answer_back_counts_as_use(tmp_path: Path) -> None:
    """写回解读的 run 正是用户在乎的那些；此前只有 `memory show` 才算点用，答过没回读的会被 prune 选中。"""
    store, run_id, _ = _stored_run(tmp_path)
    store.attach_ai_response(run_id=run_id, ai_answer="解读正文")
    record = store.query_runs(limit=1, include_payload=False)[0]
    assert record["usage_count"] == 1 and record["last_used_at"]
    _backdate(store)
    with store.connect() as conn:
        conn.execute("UPDATE runs SET last_used_at = '2020-01-02T00:00:00+00:00'")
        conn.commit()
    assert store.prune_unused(unused_days=30)["candidates"] == 0


def test_prune_keeps_runs_answered_before_usage_was_counted(tmp_path: Path) -> None:
    """升级之前写回的答案没有 usage 记录，同样不能删。"""
    store, run_id, _ = _stored_run(tmp_path)
    plain = store.create_run(entrypoint="tool", query_text="没人答过", group_id="g")
    with store.connect() as conn:
        conn.execute("UPDATE runs SET ai_answer_text = '旧答案' WHERE id = ?", (run_id,))
        conn.commit()
    _backdate(store)
    plan = store.prune_unused(unused_days=30)
    assert plan["candidates"] == 1 and plan["sample"] == [plain]


def test_storage_usage_counts_what_grows(tmp_path: Path) -> None:
    settings = _settings(tmp_path).model_copy(update={"trace_dir": tmp_path / "traces"})
    (tmp_path / "traces").mkdir()
    (tmp_path / "traces" / "2026-11-06.jsonl").write_bytes(b"x" * 1000)
    store = MemoryStore(settings)
    run_id = store.create_run(entrypoint="tool", query_text="q", group_id="g")
    ref = store.record_tool_result(run_id=run_id, tool_name="chart", ok=True, input_normalized={}, envelope_dict={"ok": True},
                                   summary=[], warnings=[], error=None)

    usage = store.storage_usage()

    assert usage["runs"] == 1
    assert usage["artifact_files"] == 2, "盘面产物 + manifest"
    assert usage["artifact_bytes"] >= Path(ref.artifact_path).stat().st_size
    assert usage["trace_bytes"] == 1000
    assert usage["database_bytes"] >= store.db_path.stat().st_size
    assert usage["total_bytes"] == usage["artifact_bytes"] + usage["trace_bytes"] + usage["database_bytes"]


def test_storage_usage_is_honest_when_the_store_is_down(tmp_path: Path) -> None:
    blocker = tmp_path / "a-file"
    blocker.write_text("not a directory", encoding="utf-8")
    store = MemoryStore(Settings(server_root="http://127.0.0.1:9", db_path=blocker / "memory.db", output_dir=blocker / "runs"))
    usage = store.storage_usage()
    assert usage["runs"] is None and usage["total_bytes"] == 0


def test_doctor_shows_how_much_the_store_uses(tmp_path: Path) -> None:
    from horosa_skill.runtime import HorosaRuntimeManager
    from horosa_skill.surfaces import doctor as doctor_checks

    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", runtime_root=tmp_path / "rt",
                        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs", data_dir=tmp_path / "data")
    MemoryStore(settings).create_run(entrypoint="tool", query_text="q", group_id="g")

    report = doctor_checks._doctor_report(settings, HorosaRuntimeManager(settings))

    assert report["memory_db"]["usage"]["runs"] == 1
    assert report["memory_db"]["ok"] is True, "新增字段不影响原有判定"
