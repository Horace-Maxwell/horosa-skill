"""认不出的 env 值要被点名（docs/LESSONS.md v0.50.0-dev「env 值被拒却说来源是 env」）。

旧行为：`HOROSA_RUNTIME_DOWNLOAD_ATTEMPTS=abc` 悄悄回落 3，doctor 的 provenance 还写 `env:HOROSA_RUNTIME_DOWNLOAD_ATTEMPTS`；
`HOROSA_SERVER_ROOT=127.0.0.1:9977`（少了 http://）没人提；未知变量的告警在 doctor 里打两遍；代理 URL 里的口令原样进 doctor JSON。
"""
from __future__ import annotations

import logging

import pytest

from horosa_skill import config as config_module
from horosa_skill.config import Settings


@pytest.fixture(autouse=True)
def _clean_rejections():
    config_module._env_rejections.clear()
    yield
    config_module._env_rejections.clear()


def _provenance(settings: Settings, field: str) -> str:
    return settings.settings_provenance[field]


@pytest.mark.parametrize(("name", "raw", "field", "default", "reason"), [
    ("HOROSA_RUNTIME_DOWNLOAD_ATTEMPTS", "abc", "runtime_download_attempts", 3, "not an integer"),
    ("HOROSA_RUNTIME_DOWNLOAD_ATTEMPTS", "99", "runtime_download_attempts", 3, "above the maximum 20"),
    ("HOROSA_JS_ENGINE_TIMEOUT_SECONDS", "-5", "js_engine_timeout_seconds", 60.0, "below the minimum 0.1"),
    ("HOROSA_JS_ENGINE_TIMEOUT_SECONDS", "nan", "js_engine_timeout_seconds", 60.0, "not a finite number"),
    ("HOROSA_MCP_COMPACT", "maybe", "mcp_compact", False, "not one of"),
])
def test_a_rejected_value_says_so_in_the_provenance(monkeypatch: pytest.MonkeyPatch, name: str, raw: str, field: str,
                                                    default: object, reason: str) -> None:
    monkeypatch.setenv(name, raw)
    settings = Settings.from_env()

    assert getattr(settings, field) == default
    source = _provenance(settings, field)
    assert source.startswith(f"default:rejected env:{name}={raw!r}") and reason in source
    assert source.split(":")[0] == "default", "doctor 的契约按冒号前一段分组（env / derived / default）"
    entry = config_module.env_rejections()[name]
    assert entry == {"value": raw, "reason": entry["reason"], "action": "used_default", "used": default}


def test_a_fixed_value_clears_the_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOROSA_RUNTIME_DOWNLOAD_ATTEMPTS", "abc")
    Settings.from_env()
    monkeypatch.setenv("HOROSA_RUNTIME_DOWNLOAD_ATTEMPTS", "5")
    settings = Settings.from_env()
    assert settings.runtime_download_attempts == 5
    assert _provenance(settings, "runtime_download_attempts") == "env:HOROSA_RUNTIME_DOWNLOAD_ATTEMPTS"
    assert "HOROSA_RUNTIME_DOWNLOAD_ATTEMPTS" not in config_module.env_rejections()


@pytest.mark.parametrize(("raw", "problem"), [
    ("127.0.0.1:9977", "no http:// or https:// scheme"),
    ("ftp://127.0.0.1:9977", "scheme `ftp`"),
    ("http://:9977", "no host"),
    ("http://127.0.0.1:99999", "port"),
])
def test_a_malformed_url_root_is_kept_but_named(monkeypatch: pytest.MonkeyPatch, raw: str, problem: str) -> None:
    """换成默认值会悄悄打到另一台服务（默认端口上可能正跑着用户的桌面端）：照用，但 doctor 点名。"""
    monkeypatch.setenv("HOROSA_SERVER_ROOT", raw)
    settings = Settings.from_env()
    assert settings.server_root == raw
    entry = config_module.env_rejections()["HOROSA_SERVER_ROOT"]
    assert entry["action"] == "kept_as_is" and problem in entry["reason"]


def test_a_good_url_root_is_not_named(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOROSA_SERVER_ROOT", "http://127.0.0.1:9")
    Settings.from_env()
    assert "HOROSA_SERVER_ROOT" not in config_module.env_rejections()


def test_secret_looking_values_never_show(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOROSA_TYPO_API_TOKEN", "sk-live-123")
    assert config_module._env_bool("HOROSA_TYPO_API_TOKEN", False) is False
    entry = config_module.env_rejections()["HOROSA_TYPO_API_TOKEN"]
    assert entry["value"] == "<redacted>" and "sk-live" not in repr(entry)
    assert config_module.redact_env_value("HOROSA_JEV_API_KEY", "k") == "<redacted>"
    assert config_module.redact_env_value("HOROSA_TRACE_OTLP_ENDPOINT", "https://u:p@h:4318/v1") == "https://***@h:4318/v1"


def test_doctor_names_each_rejection_and_masks_proxy_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    from horosa_skill.surfaces import doctor

    monkeypatch.setenv("HOROSA_RUNTIME_DOWNLOAD_ATTEMPTS", "abc")
    monkeypatch.setenv("HOROSA_SERVER_ROOT", "127.0.0.1:9977")
    Settings.from_env()
    warnings = doctor._env_rejection_warnings(config_module.env_rejections())
    by_code = {w["code"]: w for w in warnings}
    assert by_code["env:rejected_value"]["variable"] == "HOROSA_RUNTIME_DOWNLOAD_ATTEMPTS"
    assert "using the default 3" in by_code["env:rejected_value"]["detail"]
    assert by_code["env:invalid_url"]["variable"] == "HOROSA_SERVER_ROOT"

    monkeypatch.setenv("HTTPS_PROXY", "http://bob:hunter2@proxy.corp:8080")
    monkeypatch.setenv("http_proxy", "http://proxy.corp:3128")
    hints = doctor._network_hints()
    assert hints["proxy_env"]["HTTPS_PROXY"] == "http://***@proxy.corp:8080"
    assert hints["proxy_env"]["http_proxy"] == "http://proxy.corp:3128"
    assert "hunter2" not in repr(hints)


def test_the_unknown_variable_warning_is_logged_once(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    """auditor 的 c1.err：doctor 先在 Settings.from_env 里打一遍，再用 force=True 打第二遍。"""
    monkeypatch.setenv("HOROSA_TYPO_RUNTIME_MIROR", "x")
    monkeypatch.setattr(config_module, "_ENV_AUDIT_DONE", False)
    from horosa_skill.surfaces import doctor

    with caplog.at_level(logging.WARNING, logger="horosa_skill.config"):
        Settings.from_env()
        Settings.from_env()
        audit = doctor._env_flag_audit()  # doctor 收集同一份告警放进 JSON
    assert any("HOROSA_TYPO_RUNTIME_MIROR" in line for line in audit["warnings"])
    assert audit["set"]["HOROSA_TYPO_RUNTIME_MIROR"] == "unknown"
    assert sum("HOROSA_TYPO_RUNTIME_MIROR" in r.getMessage() for r in caplog.records) == 1


def test_the_other_float_readers_report_rejections_too(monkeypatch: pytest.MonkeyPatch) -> None:
    from horosa_skill.service.remote import RemoteMixin
    from horosa_skill.surfaces.mcp_elicitation import _elicit_timeout_seconds

    monkeypatch.setenv("HOROSA_MCP_ELICIT_TIMEOUT_SECONDS", "soon")
    monkeypatch.setenv("HOROSA_RUNTIME_CALL_WAIT_SECONDS", "-3")
    assert _elicit_timeout_seconds() == 120.0
    assert RemoteMixin._runtime_call_wait_seconds() == 5.0
    rejected = config_module.env_rejections()
    assert rejected["HOROSA_MCP_ELICIT_TIMEOUT_SECONDS"]["reason"] == "not a number"
    assert rejected["HOROSA_RUNTIME_CALL_WAIT_SECONDS"]["reason"] == "below the minimum 0"
