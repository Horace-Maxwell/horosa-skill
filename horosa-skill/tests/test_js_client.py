from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.engine.js_client import HorosaJsEngineClient
from horosa_skill.errors import ToolTransportError


def _client_with_engine(tmp_path: Path, monkeypatch) -> HorosaJsEngineClient:
    settings = Settings(
        runtime_root=tmp_path / "runtime",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    client = HorosaJsEngineClient(settings)
    engine_root = tmp_path / "horosa-core-js"
    cli_path = engine_root / "bin" / "cli.mjs"
    cli_path.parent.mkdir(parents=True, exist_ok=True)
    cli_path.write_text("export {};\n", encoding="utf-8")
    monkeypatch.setattr(client, "_resolve_node_binary", lambda: Path("node"))
    monkeypatch.setattr(client, "_candidate_engine_roots", lambda: [engine_root])
    return client


def test_js_client_wraps_missing_node_as_transport_error(tmp_path: Path, monkeypatch) -> None:
    client = _client_with_engine(tmp_path, monkeypatch)

    def fake_run(*args, **kwargs):
        raise FileNotFoundError("node not found")

    monkeypatch.setattr("horosa_skill.engine.js_client.subprocess.run", fake_run)

    with pytest.raises(ToolTransportError) as exc_info:
        client.run("qimen", {"question": "x"})
    assert exc_info.value.code == "js_engine.node_unavailable"


def test_js_client_wraps_node_timeout_as_transport_error(tmp_path: Path, monkeypatch) -> None:
    client = _client_with_engine(tmp_path, monkeypatch)

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="node", timeout=1)

    monkeypatch.setattr("horosa_skill.engine.js_client.subprocess.run", fake_run)

    with pytest.raises(ToolTransportError) as exc_info:
        client.run("qimen", {"question": "x"})
    assert exc_info.value.code == "js_engine.timeout"


def test_js_client_invokes_node_with_utf8_encoding(tmp_path: Path, monkeypatch) -> None:
    settings = Settings(
        runtime_root=tmp_path / "runtime",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    client = HorosaJsEngineClient(settings)
    engine_root = tmp_path / "horosa-core-js"
    cli_path = engine_root / "bin" / "cli.mjs"
    cli_path.parent.mkdir(parents=True, exist_ok=True)
    cli_path.write_text("export {};\n", encoding="utf-8")

    monkeypatch.setattr(client, "_resolve_node_binary", lambda: Path("node"))
    monkeypatch.setattr(client, "_resolve_engine_root", lambda: engine_root)

    captured: dict[str, object] = {}

    def fake_run(*args, **kwargs) -> subprocess.CompletedProcess[str]:
        captured.update(kwargs)
        return subprocess.CompletedProcess(
            args=["node"],
            returncode=0,
            stdout='{"ok": true, "data": {"label": "测试"}}',
            stderr="",
        )

    monkeypatch.setattr("horosa_skill.engine.js_client.subprocess.run", fake_run)

    result = client.run("qimen", {"question": "测试"})

    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"
    assert result == {"data": {"label": "测试"}}
