from __future__ import annotations

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
