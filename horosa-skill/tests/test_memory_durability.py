"""记忆存档的持久性：`runs/` 下的产物是一次起盘唯一的完整副本，写它的每一步都不能把已有内容弄丢。

台账：docs/LESSONS.md v0.47.2-dev「答案写回把唯一一份盘面写成 0 字节」。
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
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
