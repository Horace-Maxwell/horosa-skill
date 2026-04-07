from __future__ import annotations

from pathlib import Path

import pytest

from horosa_skill import client_tools


def test_resolve_mcporter_command_prefers_env_override(monkeypatch) -> None:
    monkeypatch.setenv("HOROSA_MCPORTER_BIN", "/custom/mcporter --flag")

    command = client_tools.resolve_mcporter_command()

    assert command == ["/custom/mcporter", "--flag"]


def test_resolve_mcporter_command_uses_cmd_on_windows(monkeypatch) -> None:
    monkeypatch.delenv("HOROSA_MCPORTER_BIN", raising=False)
    monkeypatch.setattr(client_tools.os, "name", "nt", raising=False)

    def fake_which(name: str) -> str | None:
        if name == "mcporter.cmd":
            return r"C:\Users\maxwe\AppData\Roaming\npm\mcporter.cmd"
        return None

    monkeypatch.setattr(client_tools.shutil, "which", fake_which)

    command = client_tools.resolve_mcporter_command()

    assert command == [r"C:\Users\maxwe\AppData\Roaming\npm\mcporter.cmd"]


def test_resolve_mcporter_command_falls_back_to_npx(monkeypatch) -> None:
    monkeypatch.delenv("HOROSA_MCPORTER_BIN", raising=False)
    monkeypatch.setattr(client_tools.os, "name", "posix", raising=False)

    def fake_which(name: str) -> str | None:
        if name == "npx":
            return "/usr/local/bin/npx"
        return None

    monkeypatch.setattr(client_tools.shutil, "which", fake_which)

    command = client_tools.resolve_mcporter_command()

    assert command == ["/usr/local/bin/npx", "mcporter"]


def test_resolve_mcporter_command_falls_back_to_windows_appdata(monkeypatch, tmp_path: Path) -> None:
    npm_root = tmp_path / "Roaming" / "npm"
    npm_root.mkdir(parents=True)
    mcporter_cmd = npm_root / "mcporter.cmd"
    mcporter_cmd.write_text("@echo off\n", encoding="utf-8")

    monkeypatch.delenv("HOROSA_MCPORTER_BIN", raising=False)
    monkeypatch.setattr(client_tools.os, "name", "nt", raising=False)
    monkeypatch.setattr(client_tools.shutil, "which", lambda name: None)
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))

    command = client_tools.resolve_mcporter_command()

    assert command == [str(mcporter_cmd)]


def test_resolve_mcporter_command_raises_when_missing(monkeypatch) -> None:
    monkeypatch.delenv("HOROSA_MCPORTER_BIN", raising=False)
    monkeypatch.setattr(client_tools.os, "name", "posix", raising=False)
    monkeypatch.setattr(client_tools.shutil, "which", lambda name: None)

    with pytest.raises(FileNotFoundError, match="mcporter was not found"):
        client_tools.resolve_mcporter_command()


def test_resolve_uv_command_prefers_env_override(monkeypatch) -> None:
    monkeypatch.setenv("HOROSA_UV_BIN", "python -m uv")

    command = client_tools.resolve_uv_command()

    assert command == ["python", "-m", "uv"]


def test_resolve_uv_command_preserves_windows_override_path(monkeypatch) -> None:
    monkeypatch.setattr(client_tools.os, "name", "nt", raising=False)
    monkeypatch.setenv("HOROSA_UV_BIN", r'"C:\Program Files\uv\uv.exe" --flag')

    command = client_tools.resolve_uv_command()

    assert command == [r"C:\Program Files\uv\uv.exe", "--flag"]


def test_resolve_uv_command_uses_exe_on_windows(monkeypatch) -> None:
    monkeypatch.delenv("HOROSA_UV_BIN", raising=False)
    monkeypatch.setattr(client_tools.os, "name", "nt", raising=False)

    def fake_which(name: str) -> str | None:
        if name == "uv.exe":
            return r"C:\Users\maxwe\AppData\Roaming\Python\Python313\Scripts\uv.exe"
        return None

    monkeypatch.setattr(client_tools.shutil, "which", fake_which)

    command = client_tools.resolve_uv_command()

    assert command == [r"C:\Users\maxwe\AppData\Roaming\Python\Python313\Scripts\uv.exe"]


def test_resolve_uv_command_falls_back_to_windows_appdata_python_scripts(monkeypatch, tmp_path: Path) -> None:
    scripts_root = tmp_path / "Roaming" / "Python" / "Python313" / "Scripts"
    scripts_root.mkdir(parents=True)
    uv_exe = scripts_root / "uv.exe"
    uv_exe.write_text("", encoding="utf-8")

    monkeypatch.delenv("HOROSA_UV_BIN", raising=False)
    monkeypatch.setattr(client_tools.os, "name", "nt", raising=False)
    monkeypatch.setattr(client_tools.shutil, "which", lambda name: None)
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("USERPROFILE", raising=False)

    command = client_tools.resolve_uv_command()

    assert command == [str(uv_exe)]


def test_isolated_paths_are_derived_from_home(tmp_path: Path) -> None:
    home = tmp_path / "home"

    assert client_tools.isolated_runtime_root(home) == home.resolve() / ".horosa" / "runtime"
    assert client_tools.isolated_data_dir(home) == home.resolve() / ".horosa-skill"


def test_isolated_runtime_ports_are_stable_and_distinct(tmp_path: Path) -> None:
    home = tmp_path / "home"

    backend_port, chart_port = client_tools.isolated_runtime_ports(home)
    backend_port_repeat, chart_port_repeat = client_tools.isolated_runtime_ports(home)

    assert (backend_port, chart_port) == (backend_port_repeat, chart_port_repeat)
    assert chart_port == backend_port + 1
    assert 20000 <= backend_port < 60000
    assert 20001 <= chart_port <= 60001


def test_extract_json_value_accepts_prefixed_diagnostic_output() -> None:
    payload = client_tools.extract_json_value("warning: bootstrap still warming\n{\"status\":\"ok\",\"tools\":[]}\n")

    assert payload == {"status": "ok", "tools": []}


def test_extract_json_value_rejects_non_json_output() -> None:
    with pytest.raises(ValueError, match="No JSON content was found"):
        client_tools.extract_json_value("offline\nstill warming up\n")
