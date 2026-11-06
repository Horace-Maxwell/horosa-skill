"""三条改进线合并后才接得上的几处（v0.47.2）：追踪目录建不出来不拖垮服务；CLI 的 memory query 也说出没搜全。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from horosa_skill.config import Settings
from horosa_skill.surfaces.cli import app
from horosa_skill.tracing import TraceRecorder

runner = CliRunner()


def test_an_uncreatable_trace_dir_only_turns_tracing_off(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", runtime_root=tmp_path / "rt",
                        db_path=tmp_path / "m.db", output_dir=tmp_path / "runs", data_dir=blocker / "nested",
                        trace_dir=blocker / "nested" / "traces", trace_enabled=True)
    assert TraceRecorder(settings).enabled is False


def test_cli_memory_query_says_when_older_chart_text_was_not_searched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOROSA_SKILL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("HOROSA_RUNTIME_ROOT", str(tmp_path / "rt"))

    def fake_query(self, **kwargs):  # noqa: ANN001, ANN003
        kwargs["scan_report"]["not_scanned"] = 7
        return []
    monkeypatch.setattr("horosa_skill.memory.store.MemoryStore.query_runs", fake_query)
    result = runner.invoke(app, ["memory", "query", "--text", "苍穹"])
    assert result.exit_code == 0 and json.loads(result.stdout) == []
    assert "7" in result.stderr
