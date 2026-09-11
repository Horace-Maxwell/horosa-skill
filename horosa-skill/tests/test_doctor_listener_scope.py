"""doctor.listener_scope + warnings (v0.38.0 B1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.runtime import ports
from horosa_skill.surfaces import cli


def _settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", runtime_root=tmp_path / "runtime", db_path=tmp_path / "m.db", output_dir=tmp_path / "runs")


def test_wildcard_binding_becomes_a_warning_with_a_fix() -> None:
    scope = {
        "java_backend": {"port": 9999, "bindings": [{"local_address": "0.0.0.0", "pid": 1}], "loopback_only": False},
        "python_chart": {"port": 8899, "bindings": [{"local_address": "127.0.0.1", "pid": 2}], "loopback_only": True},
    }
    warnings = cli._listener_scope_warnings(scope)
    assert [w["code"] for w in warnings] == ["listener:not_loopback_only"]
    assert "java_backend" in warnings[0]["detail"] and "0.0.0.0" in warnings[0]["detail"]
    assert "runtime restart" in warnings[0]["fix"]


def test_loopback_and_unknown_scopes_raise_no_warning() -> None:
    """Negative controls: loopback-only is clean; 'could not tell' (None) is not a warning either."""
    assert cli._listener_scope_warnings({"java_backend": {"port": 9999, "bindings": [{"local_address": "127.0.0.1", "pid": 1}], "loopback_only": True}}) == []
    assert cli._listener_scope_warnings({"java_backend": {"port": 9999, "bindings": [], "loopback_only": None}}) == []


def test_doctor_reports_listener_scope_and_warns(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    captured: dict[str, object] = {}

    class ManagerStub:
        LAUNCHER_LOG_NAME = "launcher.log"

        def doctor(self) -> dict[str, object]:
            return {"ok": True, "installed": True, "manifest_version": "0.38.0", "runtime_payload_version": "0.38.0",
                    "issues": [], "endpoints": [{"label": "java_backend", "reachable": True}, {"label": "python_chart", "reachable": True}]}

        def runtime_mode(self) -> str:
            return "managed"

        def endpoint_identities(self, manifest, *, endpoints=None):
            return [{"label": "java_backend", "reachable": True, "identity": None}]

        def load_installed_manifest(self, *, strict: bool = False):
            return {"version": "0.38.0"}

        def load_runtime_state(self, *, strict: bool = False):
            return None

    def fake_bindings(port: int):
        return [{"local_address": "0.0.0.0", "pid": 77}] if port == settings.local_backend_port else [{"local_address": "127.0.0.1", "pid": 78}]

    monkeypatch.setattr(cli.Settings, "from_env", classmethod(lambda cls: settings))
    monkeypatch.setattr(cli, "_runtime_manager", lambda settings_arg: ManagerStub())
    monkeypatch.setattr(cli, "_print_json", lambda data: captured.setdefault("report", data))
    monkeypatch.setattr(ports, "listener_bindings", fake_bindings)
    cli.doctor()
    report = captured["report"]
    assert report["listener_scope"]["java_backend"]["loopback_only"] is False
    assert report["listener_scope"]["python_chart"]["loopback_only"] is True
    assert [w["code"] for w in report["warnings"]] == ["listener:not_loopback_only"]
