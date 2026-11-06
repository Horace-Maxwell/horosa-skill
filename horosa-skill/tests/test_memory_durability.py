"""记忆存档的持久性：`runs/` 下的产物是一次起盘唯一的完整副本，写它的每一步都不能把已有内容弄丢。

台账：docs/LESSONS.md v0.47.2-dev「答案写回把唯一一份盘面写成 0 字节」。
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
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


def _damage_runs_table(store: MemoryStore) -> None:
    """只毁 runs 表的根页，库头完好：构造时看不出来，要等真去写它才报 malformed。"""
    with store.connect() as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        page_size = conn.execute("PRAGMA page_size").fetchone()[0]
        root = conn.execute("SELECT rootpage FROM sqlite_master WHERE name = 'runs'").fetchone()[0]
    with open(store.db_path, "r+b") as handle:
        handle.seek((root - 1) * page_size)
        handle.write(os.urandom(page_size))


def test_corruption_found_on_write_is_quarantined_and_the_next_write_works(tmp_path: Path) -> None:
    """2026-11-06 实测：只坏中间页时构造照常通过，之后每次存档都抛 malformed，重启也一样，只能手动搬走库。"""
    store, _, _ = _stored_run(tmp_path)
    _damage_runs_table(store)

    reopened = MemoryStore(_settings(tmp_path))
    assert reopened.corruption_recovery is None, "前提：构造时看不出这种损坏，这正是要在写时处理的原因"

    with pytest.raises(sqlite3.DatabaseError):
        reopened.create_run(entrypoint="tool", query_text="坏库上的第一次写", group_id="g")

    assert reopened.corruption_recovery is not None
    assert Path(reopened.corruption_recovery["backup"]).exists()
    assert reopened.create_run(entrypoint="tool", query_text="隔离后的下一次写", group_id="g")
    assert reopened.integrity_check()["ok"] is True


def test_a_read_that_hits_corruption_moves_nothing(tmp_path: Path) -> None:
    """读到坏页不隔离：搬走整个库只为救写路径，查询失败不值这个代价。"""
    store, _, _ = _stored_run(tmp_path)
    _damage_runs_table(store)
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
    """此前日志说「可用 memory 工具重建索引」，这样的工具不存在。"""
    db = tmp_path / "memory.db"
    db.write_bytes(b"this is not a sqlite database " * 20)
    with caplog.at_level("WARNING", logger="horosa_skill.memory.store"):
        store = MemoryStore(_settings(tmp_path))
    assert store.corruption_recovery is not None
    assert "已隔离" in caplog.text
    assert "重建索引" not in caplog.text.replace("没有重建索引", "")
