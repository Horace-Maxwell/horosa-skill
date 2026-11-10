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
    monkeypatch.setattr(client, "_candidate_engine_roots", lambda: [engine_root])

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


def test_js_client_non_object_json_stdout_is_transport_error(tmp_path: Path, monkeypatch) -> None:
    """stdout 是 JSON 数组/标量（含失败退出码）时也必须是 ToolTransportError，而不是 `.get` 的 AttributeError。"""
    client = _client_with_engine(tmp_path, monkeypatch)
    for stdout, returncode in (('[{"ok": true}]', 0), ("42", 0), ("null", 1)):
        def fake_run(*args, _stdout=stdout, _returncode=returncode, **kwargs) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(args=["node"], returncode=_returncode, stdout=_stdout, stderr="")

        monkeypatch.setattr("horosa_skill.engine.js_client.subprocess.run", fake_run)
        with pytest.raises(ToolTransportError) as exc_info:
            client.run("qimen", {"question": "x"})
        assert exc_info.value.code == "js_engine.invalid_shape", stdout


def test_timeout_recovery_does_not_blame_the_install() -> None:
    """长窗口择时超时曾被 js_engine 前缀规则说成「确认已安装离线 runtime」。"""
    from horosa_skill.errors import classify_code, recovery_for

    assert classify_code("js_engine.timeout") == ("js_engine", "exact")
    recovery = recovery_for("js_engine.timeout", {})["agent_recovery"]
    assert recovery["next_action"] == "shorten_window_or_raise_timeout"
    assert "HOROSA_JS_ENGINE_TIMEOUT_SECONDS" in recovery["prompt_to_user"]
    assert "已安装离线 runtime" not in recovery["prompt_to_user"]
    assert recovery_for("js_engine.node_unavailable", {})["agent_recovery"]["next_action"] == "install_or_set_node_then_retry"


def test_engine_timeout_at_least_only_raises_the_wall_clock(tmp_path: Path, monkeypatch) -> None:
    """择时扫描把墙钟抬到「至少 N 秒」：只抬不降、出了作用域就回到配置值，超时报的是实际用的那个数。"""
    from horosa_skill.engine.js_client import engine_timeout_at_least

    client = _client_with_engine(tmp_path, monkeypatch)
    seen: list[float] = []

    def fake_run(*args, **kwargs):
        seen.append(kwargs["timeout"])
        raise subprocess.TimeoutExpired(cmd="node", timeout=kwargs["timeout"])

    monkeypatch.setattr("horosa_skill.engine.js_client.subprocess.run", fake_run)

    def timeout_reported() -> float:
        with pytest.raises(ToolTransportError) as exc_info:
            client.run("zeri_scan", {})
        return exc_info.value.details["timeout_seconds"]

    assert timeout_reported() == 60.0
    with engine_timeout_at_least(276.0):
        assert timeout_reported() == 276.0
        with engine_timeout_at_least(5.0):
            assert timeout_reported() == 60.0  # 低于配置的下限不生效
        assert timeout_reported() == 276.0
    assert timeout_reported() == 60.0
    assert seen == [60.0, 276.0, 60.0, 276.0, 60.0]

    client.settings = client.settings.model_copy(update={"js_engine_timeout_seconds": 900.0})
    with engine_timeout_at_least(276.0):
        assert timeout_reported() == 900.0  # 用户配得更大时照用配置
