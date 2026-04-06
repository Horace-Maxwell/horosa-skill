from __future__ import annotations

from pathlib import Path

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


def test_stdio_serve_keeps_runtime_warm(monkeypatch) -> None:
    settings = Settings()
    manager = _ManagerStub()

    monkeypatch.setattr(cli.Settings, "from_env", classmethod(lambda cls: settings))
    monkeypatch.setattr(cli, "_runtime_manager", lambda settings_arg: manager)
    monkeypatch.setattr(cli, "run_mcp_server", lambda settings_arg, transport: None)

    cli.serve(transport="stdio", host="127.0.0.1", port=8765, skip_runtime_start=False)

    assert manager.started == 1
    assert manager.stopped == 0


def test_streamable_http_serve_stops_runtime_after_exit(monkeypatch) -> None:
    settings = Settings()
    manager = _ManagerStub()

    monkeypatch.setattr(cli.Settings, "from_env", classmethod(lambda cls: settings))
    monkeypatch.setattr(cli, "_runtime_manager", lambda settings_arg: manager)
    monkeypatch.setattr(cli, "run_mcp_server", lambda settings_arg, transport: None)

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


def test_build_openclaw_config_uses_uv_stdio_by_default(tmp_path: Path) -> None:
    skill_root = tmp_path / "horosa-skill"
    skill_root.mkdir()

    payload = cli._build_openclaw_config(
        skill_root=skill_root,
        server_name="horosa",
        format_name="mcporter",
        isolate_home=None,
    )

    server = payload["mcpServers"]["horosa"]
    assert server["command"] == "uv"
    assert server["args"][-2:] == ["--transport", "stdio"]
    assert server["cwd"] == str(skill_root.resolve())


def test_build_openclaw_config_supports_isolated_home(tmp_path: Path) -> None:
    skill_root = tmp_path / "horosa-skill"
    home_dir = tmp_path / "home"
    skill_root.mkdir()

    payload = cli._build_openclaw_config(
        skill_root=skill_root,
        server_name="horosa",
        format_name="openclaw",
        isolate_home=home_dir,
    )

    server = payload["mcp"]["servers"]["horosa"]
    assert server["command"] == "/bin/zsh"
    assert "export HOME=" in server["args"][1]
    assert "horosa-skill serve --transport stdio" in server["args"][1]
