"""F9: the MCP gate judges the payload after place resolution and profile expansion (v0.50.0-dev).

Before: `_gated_run` evaluated the gate on the raw payload, so a call with `place` was still asked for the location, and
dispatch / hecan ignored profile fields (gate_view returned the unexpanded payload).
"""
from __future__ import annotations

import json
from pathlib import Path

import anyio
import pytest

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.schemas.common import ToolEnvelope
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces import mcp_server as M


@pytest.fixture(autouse=True)
def _gate_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOROSA_CLARIFY", raising=False)
    monkeypatch.setenv("HOROSA_MCP_ELICIT", "0")


def _server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
                        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    reached: list[str] = []

    def fake_place(payload: dict, *, tool_name: str = "") -> dict:
        def fill(node: dict) -> dict:
            if isinstance(node, dict) and node.get("place"):
                node = {**node, "lat": "31n13", "lon": "121e28", "zone": "+08:00"}
                node.pop("place")
            return node
        out = fill(dict(payload))
        for key in ("birth", "context"):
            if isinstance(out.get(key), dict):
                out[key] = fill(out[key])
        return out

    monkeypatch.setattr(service, "resolve_place_fields", fake_place)
    monkeypatch.setattr(service, "run_tool", lambda name, payload, **kw: reached.append(name) or ToolEnvelope(
        ok=True, tool=name, version="t", input_normalized=payload))
    return M.create_mcp_server(service, settings), reached


def _call(mcp, name: str, args: dict) -> dict:
    async def go():
        return await mcp.call_tool(name, args)
    result = anyio.run(go)
    return json.loads(result.content[0].text)


def test_a_place_answers_the_location_question(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mcp, reached = _server(tmp_path, monkeypatch)
    # 太玄只问日期 / 时间 / 时区：时区只有解析了地名才有。闸门若看解析前的载荷，就会追问一个用户已经给了的时区。
    body = _call(mcp, "horosa_shenshu_taixuan", {"request": {"date": "1990-05-03", "time": "08:00:00", "place": "上海"}})
    assert reached == ["taixuan"], body
    body = _call(mcp, "horosa_dispatch", {"query": "用奇门看看这笔投资", "context": {"date": "2026-11-12", "time": "10:00:00", "place": "上海"},
                                          "agent_confirmed_settings": True})
    assert body["ok"] and reached[-1] == "qimen", body
