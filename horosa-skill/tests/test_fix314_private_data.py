"""本机数据缺省私有：新建的数据目录 0700、存档 / trace / 记忆库 0600；已有的不动；HOROSA_DATA_PRIVATE=0 回到 umask（审计 O-05 / PF-11）。

修前：~/.horosa-skill 0755、memory.db 与存档 0644（同机别的账户读得到姓名、出生时刻地点、问题与解读），报告却是 0600。
负向对照（实跑过）：fileperm.data_private 恒 False → 第一个用例红。
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.tracing import TraceRecorder

pytestmark = pytest.mark.skipif(os.name == "nt", reason="[platform] Windows 走用户 profile 的 ACL")


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _settings(root: Path) -> Settings:
    return Settings(data_dir=root, db_path=root / "memory.db", output_dir=root / "runs", trace_dir=root / "traces",
                    runtime_root=root / "runtime")


def test_new_data_is_private(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOROSA_DATA_PRIVATE", raising=False)
    root = tmp_path / "data"
    settings = _settings(root)
    settings.ensure_dirs()
    store = MemoryStore(settings)
    run_id = store.create_run(entrypoint="tool", query_text="问事业", group_id="g")
    ref = store.record_tool_result(run_id=run_id, tool_name="chart", ok=True, input_normalized={}, envelope_dict={"ok": True},
                                   summary=["s"], warnings=[], error=None, trace_id="t", group_id="g")
    with TraceRecorder(settings).span(workflow_name="tool.run", metadata={}):
        pass
    assert _mode(root) == 0o700
    assert _mode(root / "memory.db") == 0o600
    assert _mode(Path(ref.artifact_path)) == 0o600
    assert all(_mode(p) == 0o600 for p in (root / "traces").glob("*.jsonl"))


def test_an_existing_data_dir_is_left_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOROSA_DATA_PRIVATE", raising=False)
    root = tmp_path / "data"
    root.mkdir()
    root.chmod(0o755)
    MemoryStore(_settings(root))
    assert _mode(root) == 0o755   # 用户的目录：只由 doctor 报，不替用户改


def test_opt_out_keeps_the_umask(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOROSA_DATA_PRIVATE", "0")
    root = tmp_path / "data"
    MemoryStore(_settings(root))
    probe = tmp_path / "probe"
    probe.mkdir()
    assert _mode(root) == _mode(probe)
