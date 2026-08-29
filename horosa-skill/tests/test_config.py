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
    # 冷启动默认 45s：Java+Python 后端首启常超 15s。
    assert settings.runtime_start_timeout_seconds == 45.0
    assert settings.mcp_compact is False
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


# ── v0.33.0 批 II-1 · env 旗标前向兼容（warn-and-ignore；STRICT 才拒）──────────────


def test_unknown_env_flag_warns_but_never_raises(monkeypatch) -> None:
    from horosa_skill import config as config_module

    monkeypatch.setenv("HOROSA_TYPO_FLAG", "1")
    monkeypatch.delenv("HOROSA_STRICT_CONFIG", raising=False)
    warnings = config_module.audit_env_flags(force=True)
    assert any("HOROSA_TYPO_FLAG" in w for w in warnings)
    settings = config_module.Settings.from_env()  # 未知旗标绝不阻断加载（codex 0.112.0 反面教材）
    assert settings.server_root


def test_strict_config_rejects_unknown_flags(monkeypatch) -> None:
    import pytest

    from horosa_skill import config as config_module

    monkeypatch.setenv("HOROSA_TYPO_FLAG", "1")
    monkeypatch.setenv("HOROSA_STRICT_CONFIG", "1")
    with pytest.raises(ValueError, match="HOROSA_TYPO_FLAG"):
        config_module.audit_env_flags(force=True)


def test_known_env_flags_produce_no_warnings(monkeypatch) -> None:
    from horosa_skill import config as config_module

    for key in list(__import__("os").environ):
        if key.startswith("HOROSA_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HOROSA_MCP_COMPACT", "1")
    monkeypatch.setenv("HOROSA_SERVER_ROOT", "http://127.0.0.1:9999")
    assert config_module.audit_env_flags(force=True) == []


def test_env_registry_covers_all_flags_code_reads() -> None:
    """锁步：src/ 里出现的每个 HOROSA_* 字面量都必须在 ENV_FLAG_REGISTRY 登记——
    新增旗标忘登记 = 用户一设就被 warn-and-ignore 误伤为「未知」。"""
    import re
    from pathlib import Path

    from horosa_skill.config import ENV_FLAG_REGISTRY, REMOVED_ENV_FLAGS

    src = Path(__import__("horosa_skill").__file__).parent
    seen: set[str] = set()
    for py in src.rglob("*.py"):
        seen.update(re.findall(r"HOROSA_[A-Z0-9_]+", py.read_text(encoding="utf-8", errors="replace")))
    seen.discard("HOROSA_")
    known = set(ENV_FLAG_REGISTRY) | set(REMOVED_ENV_FLAGS)
    # 排除测试夹具/文档示例专用名（不是运行时读的旗标）
    unregistered = sorted(k for k in seen if k not in known and not k.startswith("HOROSA_TYPO"))
    assert unregistered == [], f"HOROSA_* 旗标未在 ENV_FLAG_REGISTRY 登记：{unregistered}"
