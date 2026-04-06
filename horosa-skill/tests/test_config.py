from __future__ import annotations

from pathlib import Path

from horosa_skill.config import Settings


def test_settings_from_env_uses_safe_fallbacks(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOROSA_SKILL_DATA_DIR", str(tmp_path / "data-home"))
    monkeypatch.setenv("HOROSA_RUNTIME_ROOT", str(tmp_path / "runtime-root"))
    monkeypatch.setenv("HOROSA_RUNTIME_RELEASE_REPO", "   ")
    monkeypatch.setenv("HOROSA_LOCAL_BACKEND_PORT", "not-a-port")
    monkeypatch.setenv("HOROSA_LOCAL_CHART_PORT", "70000")
    monkeypatch.setenv("HOROSA_RUNTIME_START_TIMEOUT_SECONDS", "0")
    monkeypatch.setenv("HOROSA_JS_ENGINE_TIMEOUT_SECONDS", "-5")
    monkeypatch.setenv("HOROSA_SKILL_PORT", "bad")
    monkeypatch.setenv("HOROSA_SKILL_LOG_LEVEL", "debug")
    monkeypatch.setenv("HOROSA_TRACE_ENABLED", "no")
    monkeypatch.setenv("HOROSA_TRACE_CAPTURE_PAYLOADS", "yes")
    monkeypatch.setenv("HOROSA_TRACE_CAPTURE_AI_ANSWERS", "1")
    monkeypatch.setenv("HOROSA_TRACE_OTLP_ENDPOINT", "https://example.com/trace")

    settings = Settings.from_env()

    assert settings.data_dir == tmp_path / "data-home"
    assert settings.runtime_root == tmp_path / "runtime-root"
    assert settings.db_path == settings.data_dir / "memory.db"
    assert settings.output_dir == settings.data_dir / "runs"
    assert settings.runtime_release_repo == "Horace-Maxwell/horosa-skill"
    assert settings.local_backend_port == 9999
    assert settings.local_chart_port == 8899
    assert settings.runtime_start_timeout_seconds == 15.0
    assert settings.js_engine_timeout_seconds == 60.0
    assert settings.port == 8765
    assert settings.log_level == "DEBUG"
    assert settings.trace_enabled is False
    assert settings.trace_capture_payloads is True
    assert settings.trace_capture_ai_answers is True
    assert settings.trace_otlp_endpoint == "https://example.com/trace"


def test_settings_from_env_expands_user_paths(monkeypatch) -> None:
    monkeypatch.setenv("HOROSA_SKILL_DB_PATH", "~/horosa-test/memory.db")
    monkeypatch.setenv("HOROSA_SKILL_OUTPUT_DIR", "~/horosa-test/runs")
    monkeypatch.setenv("HOROSA_TRACE_DIR", "~/horosa-test/traces")

    settings = Settings.from_env()

    assert str(settings.db_path).startswith(str(Path.home()))
    assert str(settings.output_dir).startswith(str(Path.home()))
    assert str(settings.trace_dir).startswith(str(Path.home()))
