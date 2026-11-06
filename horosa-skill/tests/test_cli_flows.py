"""命令函数与流程模块的接缝：`serve` 与 `client openclaw-*` 挪出 cli.py 之后，退出码、传输校验、报告打印要原样留着。

这几条路径原先没有端到端测试：把 openclaw-check 的退出码或 serve 的传输校验摘掉，全仓照绿。"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from horosa_skill.surfaces import cli, openclaw_smoke, runtime_helpers

RUNNER = CliRunner()


class _Manager:
    def load_runtime_state(self) -> dict:
        return {}


@pytest.fixture()
def served(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[str]:
    """把真正监听的那一步换掉，记下 serve 最后交给 MCP server 的传输。"""
    transports: list[str] = []
    monkeypatch.setenv("HOROSA_RUNTIME_ROOT", str(tmp_path / "runtime"))
    monkeypatch.setenv("HOROSA_SKILL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(runtime_helpers, "_runtime_manager", lambda settings: _Manager())
    monkeypatch.setattr("horosa_skill.runtime.ports.port_bindable", lambda port, host: True)
    monkeypatch.setattr("horosa_skill.surfaces.mcp_server.run_mcp_server",
                        lambda settings, *, transport, service=None: transports.append(transport))
    return transports


def test_serve_refuses_an_unknown_transport(served: list[str]) -> None:
    result = RUNNER.invoke(cli.app, ["serve", "--transport", "websocket", "--skip-runtime-start"])
    assert result.exit_code == 2 and served == []
    assert "websocket" in result.output


@pytest.mark.parametrize(("given", "expected"), [("http", "streamable-http"), ("STDIO", "stdio"), ("sse", "sse")])
def test_serve_hands_the_normalized_transport_to_the_server(served: list[str], given: str, expected: str) -> None:
    result = RUNNER.invoke(cli.app, ["serve", "--transport", given, "--skip-runtime-start", "--port", "18765"])
    assert result.exit_code == 0, (result.output, repr(result.exception))
    assert served == [expected]


def _workspace(tmp_path: Path) -> tuple[Path, Path]:
    config = tmp_path / "config" / "mcporter.json"
    config.parent.mkdir(parents=True)
    config.write_text("{}", encoding="utf-8")
    return tmp_path, config


@pytest.mark.parametrize(("ok", "exit_code"), [(True, 0), (False, 2)])
def test_openclaw_check_prints_the_report_and_exits_by_it(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, ok: bool, exit_code: int) -> None:
    workspace, config = _workspace(tmp_path)
    monkeypatch.setenv("HOROSA_SKILL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(openclaw_smoke, "_run_openclaw_smoke_check", lambda **_kwargs: {"ok": ok, "marker": "quick"})
    result = RUNNER.invoke(cli.app, ["client", "openclaw-check", "--workspace", str(workspace), "--config", str(config)])
    assert result.exit_code == exit_code
    assert json.loads(result.stdout) == {"ok": ok, "marker": "quick"}


def _fake_full_run(monkeypatch: pytest.MonkeyPatch, *, returncode: int, report: dict | None, stderr: str = "") -> None:
    def fake_run(command: list[str], **_kwargs):
        if report is not None:
            Path(command[command.index("--output") + 1]).write_text(json.dumps(report), encoding="utf-8")
        return subprocess.CompletedProcess(command, returncode, stdout="", stderr=stderr)

    monkeypatch.setattr(subprocess, "run", fake_run)


@pytest.mark.parametrize(("returncode", "exit_code"), [(0, 0), (1, 2)])
def test_openclaw_full_check_prints_its_report_and_passes_on_the_exit_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, returncode: int, exit_code: int
) -> None:
    workspace, config = _workspace(tmp_path)
    monkeypatch.setenv("HOROSA_SKILL_DATA_DIR", str(tmp_path / "data"))
    _fake_full_run(monkeypatch, returncode=returncode, report={"ok": returncode == 0, "marker": "full"})
    result = RUNNER.invoke(cli.app, ["client", "openclaw-check", "--workspace", str(workspace), "--config", str(config), "--full"])
    assert result.exit_code == exit_code
    assert json.loads(result.stdout)["marker"] == "full"


def test_openclaw_full_check_without_a_report_forwards_the_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    workspace, config = _workspace(tmp_path)
    monkeypatch.setenv("HOROSA_SKILL_DATA_DIR", str(tmp_path / "data"))
    _fake_full_run(monkeypatch, returncode=1, report=None, stderr="self-check crashed")
    result = RUNNER.invoke(cli.app, ["client", "openclaw-check", "--workspace", str(workspace), "--config", str(config), "--full"])
    assert result.exit_code == 2
    assert result.stdout == "" and "self-check crashed" in result.stderr
