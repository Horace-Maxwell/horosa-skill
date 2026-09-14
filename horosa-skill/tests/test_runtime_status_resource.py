"""`horosa://runtime/status` 资源（v0.38.1 C14）：只读、绝不启动 runtime、报出本进程算出的目录。"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from pydantic import AnyUrl

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.runtime.manager import HorosaRuntimeManager
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces.mcp_server import create_mcp_server


def test_runtime_status_resource_reports_this_processes_roots_without_starting_anything(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        raise AssertionError("reading runtime status must never start the runtime")

    monkeypatch.setattr(HorosaRuntimeManager, "start_local_services", boom)
    settings = Settings(runtime_root=tmp_path / "rt", data_dir=tmp_path / "data", db_path=tmp_path / "m.db", output_dir=tmp_path / "runs")
    mcp = create_mcp_server(HorosaSkillService(settings, store=MemoryStore(settings)), settings)
    templates = {str(r.uri) for r in asyncio.run(mcp.list_resources())}
    assert "horosa://runtime/status" in templates
    contents = asyncio.run(mcp.read_resource(AnyUrl("horosa://runtime/status")))
    payload = json.loads(next(iter(contents)).content)
    assert payload["installed"] is False and Path(payload["runtime_root"]) == tmp_path / "rt"
    assert Path(payload["data_dir"]) == tmp_path / "data" and payload["mode"] in {"managed", "external"}
    assert payload["package_version"]
