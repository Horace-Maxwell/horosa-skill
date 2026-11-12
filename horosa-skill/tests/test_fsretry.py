"""Windows 共享冲突（v0.47.2-dev，Windows 原生复验）：别的进程正开着文件时，replace / unlink / 读都会 PermissionError。

10 进程 15 秒写读同一份 runtime-state.json，修复前：87% 的写抛 PermissionError、11.5% 的读返回「没有状态」（调用方当成 runtime 没在跑）、
15 秒只完成 2 次加锁更新（锁文件 unlink 失败 → 异常从 finally 冒出去、锁留在盘上）。修复后 0 错误 0 假空。
"""

from __future__ import annotations

import ast
import errno
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from test_user_knowledge_and_chart_report import _chart_run, _service

from horosa_skill import fsretry
from horosa_skill.reports import renderers
from horosa_skill.runtime import pidlock, registry

PKG_ROOT = Path(__file__).resolve().parents[1]


def _sharing_error(winerror: int | None = 32) -> PermissionError:
    exc = PermissionError(errno.EACCES, "in use")
    exc.winerror = winerror
    return exc


@pytest.fixture()
def windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fsretry, "_on_windows", lambda: True)


@pytest.mark.parametrize("winerror", [5, 32, 33, None])
def test_sharing_violations_are_recognised_on_windows(windows, winerror: int | None) -> None:
    assert fsretry.is_sharing_violation(_sharing_error(winerror))  # None = open() 走 CRT，只带 errno 13


def test_other_errors_are_not_sharing_violations(windows) -> None:
    assert not fsretry.is_sharing_violation(_sharing_error(1314))
    assert not fsretry.is_sharing_violation(FileNotFoundError())
    assert not fsretry.is_sharing_violation(PermissionError(errno.EPERM, "nope"))


def test_posix_never_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fsretry, "_on_windows", lambda: False)
    assert not fsretry.is_sharing_violation(_sharing_error())


def test_transient_failure_is_retried_until_it_clears(windows, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls = {"n": 0}
    real = os.replace

    def flaky(src, dst):
        calls["n"] += 1
        if calls["n"] < 4:
            raise _sharing_error()
        real(src, dst)

    monkeypatch.setattr(fsretry.os, "replace", flaky)
    source = tmp_path / "a"
    source.write_text("new", encoding="utf-8")
    fsretry.replace(source, tmp_path / "b")
    assert calls["n"] == 4 and (tmp_path / "b").read_text(encoding="utf-8") == "new"


def test_a_lock_that_never_clears_raises_after_the_budget(windows, monkeypatch: pytest.MonkeyPatch) -> None:
    def always(_src, _dst):
        raise _sharing_error()

    monkeypatch.setattr(fsretry.os, "replace", always)
    with pytest.raises(PermissionError):
        fsretry.replace("a", "b", budget_seconds=0.05)


def test_a_real_permission_problem_is_not_retried(windows, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def denied(_src, _dst):
        calls["n"] += 1
        raise PermissionError(errno.EPERM, "really denied")

    monkeypatch.setattr(fsretry.os, "replace", denied)
    with pytest.raises(PermissionError):
        fsretry.replace("a", "b")
    assert calls["n"] == 1


def test_unlink_ignores_a_missing_file(tmp_path: Path) -> None:
    fsretry.unlink(tmp_path / "nope")


def test_lock_release_never_raises_out_of_the_context(windows, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """旧实现只接 FileNotFoundError：PermissionError 从 finally 冒出去，盖掉调用方的结果，锁还留在盘上。"""
    lock = tmp_path / "x.lock"

    def blocked(_path):
        raise _sharing_error()

    with monkeypatch.context() as patch:
        patch.setattr(fsretry, "DEFAULT_BUDGET_SECONDS", 0.05)
        patch.setattr(fsretry.os, "unlink", blocked)
        patch.setattr(fsretry, "unlink", lambda path: fsretry._retrying(lambda: blocked(path), 0.05))
        with pidlock.pid_lock(lock, timeout_seconds=1.0):
            result = "the caller's work"
    assert result == "the caller's work"


def test_lock_is_gone_after_a_transient_block(windows, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    lock = tmp_path / "x.lock"
    calls = {"n": 0}
    real = os.unlink

    def flaky(path):
        calls["n"] += 1
        if calls["n"] < 3:
            raise _sharing_error()
        real(path)

    monkeypatch.setattr(fsretry.os, "unlink", flaky)
    with pidlock.pid_lock(lock, timeout_seconds=1.0):
        assert lock.exists()
    assert not lock.exists() and calls["n"] == 3


_HAMMER = textwrap.dedent(
    """
    import json, sys, time
    from collections import Counter
    from pathlib import Path
    sys.path.insert(0, sys.argv[4])
    from horosa_skill.runtime import registry
    role, target, stop_at = sys.argv[1], Path(sys.argv[2]), time.time() + float(sys.argv[3])
    stats = Counter()
    while time.time() < stop_at:
        try:
            if role == "writer":
                registry.write_state(target, {"status": "running", "pad": "x" * 2000})
                stats["ok"] += 1
            elif role == "updater":
                registry.update_state(target, lambda s: s.update(tick=(s.get("tick") or 0) + 1), timeout_seconds=10.0)
                stats["ok"] += 1
            else:
                stats["ok" if registry.read_state(target) is not None else "read_none"] += 1
        except OSError as exc:
            stats[type(exc).__name__] += 1
    print(json.dumps(stats))
    """
)


def test_processes_sharing_the_state_file_see_no_errors_and_no_false_empty(tmp_path: Path) -> None:
    worker = tmp_path / "hammer.py"
    worker.write_text(_HAMMER, encoding="utf-8")
    target = tmp_path / "runtime-state.json"
    registry.write_state(target, {"status": "running"})
    roles = ["writer", "writer", "updater", "updater", "reader", "reader", "reader"]
    procs = [subprocess.Popen([sys.executable, str(worker), role, str(target), "3", str(PKG_ROOT / "src")],
                              stdout=subprocess.PIPE, text=True) for role in roles]
    totals: dict[str, int] = {}
    for proc in procs:
        out, _ = proc.communicate(timeout=120)
        assert proc.returncode == 0
        for key, value in json.loads(out.strip().splitlines()[-1]).items():
            totals[key] = totals.get(key, 0) + value
    assert set(totals) == {"ok"}, totals
    assert registry.read_state(target) is not None


def test_no_raw_os_replace_in_the_package() -> None:
    """Windows 上裸 os.replace 碰到读者就抛；统一走 fsretry。"""
    offenders = []
    for path in (PKG_ROOT / "src").rglob("*.py"):
        if path.name == "fsretry.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "replace"
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == "os"):
                offenders.append(f"{path.relative_to(PKG_ROOT)}:{node.lineno}")
    assert not offenders, offenders


# ── 报告：目标开在阅读器里 / 渲染失败 ────────────────────────────────────────────


def test_held_target_keeps_the_rendered_report_under_a_free_name(windows, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / "report.pdf"
    target.write_bytes(b"old version")
    (tmp_path / "report (1).pdf").write_bytes(b"older copy")
    real = os.replace

    def held(src, dst):
        if Path(dst) == target:
            raise _sharing_error()
        real(src, dst)

    monkeypatch.setattr(fsretry, "DEFAULT_BUDGET_SECONDS", 0.05)
    monkeypatch.setattr(fsretry.os, "replace", held)
    monkeypatch.setattr(fsretry, "replace", lambda s, d, budget_seconds=0.05: fsretry._retrying(lambda: held(s, d), budget_seconds))
    result = renderers.render_report({"title": "t", "intro_text": "x"}, output_path=target, format_name="pdf")
    assert result["format"] == "pdf" and "degraded_from" not in result
    assert Path(result["path"]).name == "report (2).pdf" and Path(result["path"]).read_bytes().startswith(b"%PDF")
    assert result["requested_output_path"] == str(target)
    assert target.read_bytes() == b"old version" and (tmp_path / "report (1).pdf").read_bytes() == b"older copy"


@pytest.mark.skipif(os.name != "nt", reason="[platform] a real open handle only blocks replace on Windows")
def test_really_open_target_on_windows(tmp_path: Path) -> None:
    target = tmp_path / "report.pdf"
    renderers.render_report({"title": "t", "intro_text": "first"}, output_path=target, format_name="pdf")
    before = target.read_bytes()
    with open(target, "rb"):
        result = renderers.render_report({"title": "t", "intro_text": "second"}, output_path=target, format_name="pdf")
    assert result["format"] == "pdf" and Path(result["path"]).name == "report (1).pdf"
    assert target.read_bytes() == before


def test_caller_is_told_the_truth_about_a_saved_as_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service(tmp_path)
    run = _chart_run(service)
    args = {"run_id": run.memory_ref.run_id, "tool_name": "chart", "format": "pdf", "style": "chart", "output_path": "r.pdf"}
    real_place = renderers._place_rendered

    def moved(tmp, output):
        return real_place(tmp, output.with_name("r (1).pdf"))

    monkeypatch.setattr(renderers, "_place_rendered", moved)
    result = service.report_render(args)
    assert Path(result["artifact_path"]).name == "r (1).pdf"
    assert Path(result["requested_output_path"]).name == "r.pdf"
    assert any("另存为" in line for line in result["summary"])


def test_degraded_report_is_not_announced_as_a_pdf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """修复前：format=pdf、summary「已生成 PDF」、路径却是 .txt，degraded_from / degrade_reason 全丢。"""
    service = _service(tmp_path)
    run = _chart_run(service)

    def boom(*_args, **_kwargs):
        raise RuntimeError("renderer exploded")

    monkeypatch.setattr(renderers, "_render_pdf", boom)
    result = service.report_render({"run_id": run.memory_ref.run_id, "tool_name": "chart", "format": "pdf", "style": "chart"})
    assert result["artifact_path"].endswith(".txt")
    assert result["format"] == "txt", "存档与结果记的是真实格式，不是请求的格式"
    assert result["degraded_from"] == "pdf" and "renderer exploded" in result["degrade_reason"]
    assert not any("已生成 PDF" in line for line in result["summary"])
    assert any("退化为纯文本" in line for line in result["summary"])
    assert result["file"]["path"].endswith(".txt")
