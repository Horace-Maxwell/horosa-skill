from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.surfaces import cli


class _ManagerStub:
    def __init__(self) -> None:
        self.started = 0
        self.stopped = 0

    def start_local_services(self) -> dict[str, object]:
        self.started += 1
        return {"ok": True, "already_running": False}

    def stop_local_services(self) -> dict[str, object]:
        self.stopped += 1
        return {"ok": True}


def test_stdio_serve_skips_eager_runtime_start(monkeypatch) -> None:
    settings = Settings(db_path=Path("memory.db"), output_dir=Path("runs"))
    manager = _ManagerStub()
    warmups: list[_ManagerStub] = []

    monkeypatch.setattr(cli.Settings, "from_env", classmethod(lambda cls: settings))
    monkeypatch.setattr(cli, "_runtime_manager", lambda settings_arg: manager)
    monkeypatch.setattr(cli, "_start_stdio_runtime_warmup", lambda manager_arg: warmups.append(manager_arg))
    monkeypatch.setattr(cli, "run_mcp_server", lambda settings_arg, transport, service=None: None)

    cli.serve(transport="stdio", host="127.0.0.1", port=8765, skip_runtime_start=False)

    assert warmups == [manager]
    assert manager.started == 0
    assert manager.stopped == 0


def test_streamable_http_serve_stops_runtime_after_exit(monkeypatch) -> None:
    settings = Settings(db_path=Path("memory.db"), output_dir=Path("runs"))
    manager = _ManagerStub()

    monkeypatch.setattr(cli.Settings, "from_env", classmethod(lambda cls: settings))
    monkeypatch.setattr(cli, "_runtime_manager", lambda settings_arg: manager)
    monkeypatch.setattr(cli, "run_mcp_server", lambda settings_arg, transport, service=None: None)

    cli.serve(transport="streamable-http", host="127.0.0.1", port=8765, skip_runtime_start=False)

    assert manager.started == 1
    assert manager.stopped == 1


def test_resolve_skill_root_accepts_package_dir(tmp_path: Path) -> None:
    skill_root = tmp_path / "horosa-skill"
    skill_root.mkdir()
    (skill_root / "pyproject.toml").write_text("[project]\nname='horosa-skill'\n", encoding="utf-8")

    assert cli._resolve_skill_root(skill_root) == skill_root.resolve()


def test_resolve_skill_root_accepts_repo_root(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    skill_root = repo_root / "horosa-skill"
    skill_root.mkdir(parents=True)
    (skill_root / "pyproject.toml").write_text("[project]\nname='horosa-skill'\n", encoding="utf-8")

    assert cli._resolve_skill_root(repo_root) == skill_root.resolve()


def test_build_openclaw_config_uses_uv_stdio_by_default(tmp_path: Path, monkeypatch) -> None:
    skill_root = tmp_path / "horosa-skill"
    skill_root.mkdir()
    uv_bin = str((tmp_path / "bin" / "uv").resolve())
    monkeypatch.setattr(cli, "resolve_uv_command", lambda: [uv_bin])

    payload = cli._build_openclaw_config(
        skill_root=skill_root,
        server_name="horosa",
        format_name="mcporter",
        isolate_home=None,
    )

    server = payload["mcpServers"]["horosa"]
    assert server["command"] == uv_bin
    assert server["args"][-2:] == ["--transport", "stdio"]
    assert server["cwd"] == str(skill_root.resolve())


def test_build_openclaw_config_supports_isolated_home(tmp_path: Path, monkeypatch) -> None:
    skill_root = tmp_path / "horosa-skill"
    home_dir = tmp_path / "home"
    skill_root.mkdir()
    monkeypatch.setattr(cli.os, "name", "posix", raising=False)
    monkeypatch.setattr(cli, "resolve_uv_command", lambda: ["python", "-m", "uv"])

    payload = cli._build_openclaw_config(
        skill_root=skill_root,
        server_name="horosa",
        format_name="openclaw",
        isolate_home=home_dir,
    )

    server = payload["mcp"]["servers"]["horosa"]
    assert server["command"] == "python"
    assert server["args"][:3] == ["-m", "uv", "run"]
    assert server["args"][-2:] == ["--transport", "stdio"]
    assert server["env"]["HOME"] == str(home_dir.resolve())
    assert server["env"]["HOROSA_RUNTIME_ROOT"] == str((home_dir / ".horosa" / "runtime").resolve())
    assert server["env"]["HOROSA_SKILL_DATA_DIR"] == str((home_dir / ".horosa-skill").resolve())


def test_build_openclaw_config_supports_isolated_home_on_windows(tmp_path: Path, monkeypatch) -> None:
    skill_root = tmp_path / "horosa-skill"
    home_dir = tmp_path / "home"
    skill_root.mkdir()

    monkeypatch.setattr(cli.os, "name", "nt", raising=False)
    monkeypatch.setattr(cli, "resolve_uv_command", lambda: [r"C:\Program Files\uv\uv.exe"])

    payload = cli._build_openclaw_config(
        skill_root=skill_root,
        server_name="horosa",
        format_name="mcporter",
        isolate_home=home_dir,
    )

    server = payload["mcpServers"]["horosa"]
    assert server["command"] == r"C:\Program Files\uv\uv.exe"
    assert server["args"][:2] == ["run", "--directory"]
    assert server["args"][-2:] == ["--transport", "stdio"]
    assert server["env"]["HOME"] == str(home_dir.resolve())
    assert server["env"]["USERPROFILE"] == str(home_dir.resolve())
    assert server["env"]["HOROSA_RUNTIME_ROOT"] == str((home_dir / ".horosa" / "runtime").resolve())
    assert server["env"]["HOROSA_SKILL_DATA_DIR"] == str((home_dir / ".horosa-skill").resolve())


def test_openclaw_setup_bootstraps_workspace_and_runs_smoke(monkeypatch, tmp_path: Path) -> None:
    skill_root = tmp_path / "repo" / "horosa-skill"
    skill_root.mkdir(parents=True)
    (skill_root / "pyproject.toml").write_text("[project]\nname='horosa-skill'\n", encoding="utf-8")
    workspace = tmp_path / "workspace"
    expected_home = (workspace / ".horosa-home").resolve()
    captured: dict[str, object] = {}
    smoke_calls: list[dict[str, object]] = []

    class ManagerStub:
        def install(self) -> dict[str, object]:
            assert os.environ["HOME"] == str(expected_home)
            return {"ok": True, "installed": True, "changed": True}

        def start_local_services(self) -> dict[str, object]:
            return {"ok": True, "already_running": False}

        def doctor(self) -> dict[str, object]:
            return {"issues": [], "endpoints": [{"label": "java_backend", "reachable": True}]}

    def fake_smoke_check(*, workspace_root: Path, config_path: Path, output_path: Path, include_list: bool = True) -> dict[str, object]:
        smoke_calls.append(
            {
                "workspace_root": workspace_root,
                "config_path": config_path,
                "output_path": output_path,
                "include_list": include_list,
            }
        )
        return {"ok": True, "server_visible": True, "listed_tool_count": 43}

    monkeypatch.setattr(cli, "resolve_uv_command", lambda: ["/usr/local/bin/uv"])
    monkeypatch.setattr(cli, "_runtime_manager", lambda settings_arg: ManagerStub())
    monkeypatch.setattr(cli, "_run_openclaw_smoke_check", fake_smoke_check)
    monkeypatch.setattr(cli, "_print_json", lambda data: captured.setdefault("report", data))

    original_home = os.environ.get("HOME")

    cli.client_openclaw_setup(
        workspace=workspace,
        skill_root=skill_root,
        server_name="horosa",
        isolate_home=None,
        config=None,
        skip_smoke=False,
    )

    config_path = (workspace / "config" / "mcporter.json").resolve()
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    server = payload["mcpServers"]["horosa"]

    assert server["env"]["HOME"] == str(expected_home)
    if os.name == "nt":
        assert server["env"]["USERPROFILE"] == str(expected_home)
    else:
        assert "USERPROFILE" not in server["env"]
    assert smoke_calls == [
        {
            "workspace_root": workspace.resolve(),
            "config_path": config_path,
            "output_path": (expected_home / ".horosa-skill" / "openclaw_setup_smoke_check.json"),
            "include_list": False,
        }
    ]
    assert captured["report"]["ok"] is True
    assert captured["report"]["config"] == str(config_path)
    assert captured["report"]["config_written_to"] == str(config_path)
    assert captured["report"]["local_home"] == str(expected_home)
    assert captured["report"]["ready_for_openclaw"] is True
    assert captured["report"]["smoke"]["ok"] is True
    assert os.environ.get("HOME") == original_home


def test_doctor_adds_user_facing_summary(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path / "data",
        runtime_root=tmp_path / "runtime",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    captured: dict[str, object] = {}

    class ManagerStub:
        def doctor(self) -> dict[str, object]:
            return {
                "ok": True,
                "installed": True,
                "issues": ["services:not_running"],
                "endpoints": [{"label": "java_backend", "reachable": False}],
            }

    monkeypatch.setattr(cli.Settings, "from_env", classmethod(lambda cls: settings))
    monkeypatch.setattr(cli, "_runtime_manager", lambda settings_arg: ManagerStub())
    monkeypatch.setattr(cli, "_print_json", lambda data: captured.setdefault("report", data))

    cli.doctor()

    report = captured["report"]
    assert report["ready_for_openclaw"] is False
    assert report["status"] == "needs_attention"
    assert "not running yet" in report["user_summary"]
    assert "openclaw-setup" in report["next_action"]


def test_openclaw_check_reports_missing_config_as_user_facing_error(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    errors: list[str] = []

    monkeypatch.setattr(cli.typer, "echo", lambda message, err=False: errors.append(message))

    with pytest.raises(cli.typer.Exit):
        cli.client_openclaw_check(workspace=workspace, config=None, full=False, output=tmp_path / "report.json")

    payload = json.loads(errors[0])
    assert payload["code"] == "client.config_missing"
    assert payload["ready_for_openclaw"] is False
    assert "config not found" in payload["user_summary"].lower()
    assert "openclaw-setup" in payload["next_action"]


def test_openclaw_check_wraps_runtime_error_for_users(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    config_path = workspace / "config" / "mcporter.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("{}", encoding="utf-8")
    settings = Settings(
        data_dir=tmp_path / "data",
        runtime_root=tmp_path / "runtime",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    errors: list[str] = []

    monkeypatch.setattr(cli.Settings, "from_env", classmethod(lambda cls: settings))
    monkeypatch.setattr(
        cli,
        "_run_openclaw_smoke_check",
        lambda **kwargs: (_ for _ in ()).throw(
            cli.RuntimeError(
                "missing mcporter",
                code="client.command_not_found",
                details={"command": ["mcporter"], "cwd": str(workspace)},
            )
        ),
    )
    monkeypatch.setattr(cli.typer, "echo", lambda message, err=False: errors.append(message))

    with pytest.raises(cli.typer.Exit):
        cli.client_openclaw_check(workspace=workspace, config=config_path, full=False, output=tmp_path / "report.json")

    payload = json.loads(errors[0])
    assert payload["ready_for_openclaw"] is False
    assert "could not find `mcporter`" in payload["user_summary"]
    assert "HOROSA_MCPORTER_BIN" in payload["next_action"]


def test_run_subprocess_json_accepts_diagnostic_prefix(monkeypatch, tmp_path: Path) -> None:
    def fake_run(*args, **kwargs) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["mcporter"],
            returncode=0,
            stdout='warming runtime\n{"status":"ok","tools":[]}\n',
            stderr="",
        )

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    payload = cli._run_subprocess_json(["mcporter", "list"], cwd=tmp_path)

    assert payload == {"status": "ok", "tools": []}


def test_openclaw_check_uses_extended_timeout_for_tool_calls(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    config_path = workspace / "config" / "mcporter.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("{}", encoding="utf-8")

    settings = Settings(
        data_dir=tmp_path / "data",
        runtime_root=tmp_path / "runtime",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    commands: list[list[str]] = []
    chart_calls = 0

    def fake_run_subprocess_json(command: list[str], *, cwd: Path) -> dict[str, object]:
        nonlocal chart_calls
        commands.append(command)
        if "list" in command:
            return {"status": "ok", "tools": ["a", "b"]}
        if any("horosa_knowledge_registry" in item for item in command):
            return {"ok": True}
        if any("horosa_astro_chart" in item for item in command):
            chart_calls += 1
            if chart_calls == 1:
                return {"ok": False, "error": "Call timed out", "issue": {"kind": "offline", "rawMessage": "timed out after 120000ms"}}
            return {"ok": True, "memory_ref": {"run_id": "run-1", "artifact_path": str(tmp_path / "artifact.json")}}
        if any("horosa_memory_show" in item for item in command):
            return {"ok": True}
        raise AssertionError(command)

    monkeypatch.setattr(cli.Settings, "from_env", classmethod(lambda cls: settings))
    monkeypatch.setattr(cli, "resolve_mcporter_command", lambda: ["mcporter"])
    monkeypatch.setattr(cli, "_run_subprocess_json", fake_run_subprocess_json)

    cli.client_openclaw_check(workspace=workspace, config=config_path, full=False, output=tmp_path / "report.json")

    assert chart_calls == 2
    assert len(commands) == 5
    list_command, knowledge_command, first_chart_command, second_chart_command, memory_command = commands
    assert "--timeout" not in list_command
    for command in (knowledge_command, first_chart_command, second_chart_command, memory_command):
        assert command[-2:] == ["--timeout", "120000"]
