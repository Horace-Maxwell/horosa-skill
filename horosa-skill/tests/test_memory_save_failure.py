"""存档失败绝不丢算好的盘（v0.47.2-dev）。

`run_tool` 的 `if save_result:` 与 `dispatch` 的收尾存档都在 try 之外：SQLite / 磁盘一出错，算好的结果连同信封一起没了，
MCP 上成了裸 `UnexpectedToolError`（绕过 agent_recovery），CLI 上成了 traceback。现在：结果照回，`memory_ref=None`，warnings 带 `memory.save_failed`。
"""
from __future__ import annotations

import ast
import json
import sqlite3
from pathlib import Path

import anyio
import pytest
from fakes import FakeClient, FakeJsClient
from typer.testing import CliRunner

from horosa_skill.config import Settings
from horosa_skill.errors import ToolValidationError
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces import cli as C
from horosa_skill.surfaces import mcp_server as M

BIRTH = {"date": "1990-06-15", "time": "10:30:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gender": 1}
CONFIRMED = {**BIRTH, "defaults_accepted": True}
SAVE_FAILED = "memory.save_failed"


def _service(tmp_path: Path, *, compact: bool = False) -> tuple[Settings, HorosaSkillService]:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
                        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs", mcp_compact=compact)
    return settings, HorosaSkillService(settings, client=FakeClient(), chart_client=FakeClient(), js_client=FakeJsClient(),
                                        store=MemoryStore(settings))


def _locked(*_args, **_kwargs):
    raise sqlite3.OperationalError("database is locked")


def _disk_full(*_args, **_kwargs):
    raise OSError(28, "No space left on device")


FAILURES = [("create_run", _locked), ("record_entities", _locked), ("record_tool_result", _disk_full)]


def _kept_the_chart(envelope) -> None:
    assert envelope.ok is True
    assert envelope.data.get("snapshot_text") or envelope.data.get("export_snapshot"), "算好的结果不能丢"
    assert envelope.memory_ref is None
    assert sum(SAVE_FAILED in line for line in envelope.warnings) == 1, envelope.warnings


@pytest.mark.parametrize(("method", "failure"), FAILURES, ids=[name for name, _ in FAILURES])
def test_run_tool_keeps_the_result_when_the_save_fails(tmp_path: Path, method: str, failure) -> None:
    _settings, service = _service(tmp_path)
    setattr(service.store, method, failure)
    _kept_the_chart(service.run_tool("chart", dict(CONFIRMED)))


def test_a_clean_save_still_fills_memory_ref(tmp_path: Path) -> None:
    _settings, service = _service(tmp_path)
    envelope = service.run_tool("chart", dict(CONFIRMED))
    assert envelope.memory_ref is not None and not any(SAVE_FAILED in line for line in envelope.warnings)
    assert envelope.data["technique_card"]["refs"]["run_id"] == envelope.memory_ref.run_id


@pytest.mark.parametrize(
    ("method", "failure"),
    [("create_run", _locked), ("record_entities", _locked), ("record_dispatch_result", _disk_full)],
    ids=["create_run", "record_entities", "record_dispatch_result"],
)
def test_dispatch_keeps_the_results_when_the_save_fails(tmp_path: Path, method: str, failure) -> None:
    _settings, service = _service(tmp_path)
    original = getattr(service.store, method)
    calls = {"n": 0}

    def _fail_on_the_dispatch_save(*args, **kwargs):
        # dispatch 与它调的 run_tool 共用 create_run / record_entities；这里只让 dispatch 自己那一下失败。
        calls["n"] += 1
        if method == "record_dispatch_result" or kwargs.get("entrypoint") == "dispatch" or (method == "record_entities" and calls["n"] > 1):
            return failure(*args, **kwargs)
        return original(*args, **kwargs)

    setattr(service.store, method, _fail_on_the_dispatch_save)
    envelope = service.dispatch({"query": "看看八字", "birth": BIRTH, "defaults_accepted": True})
    assert envelope.ok is True
    assert envelope.results and all(result.ok for result in envelope.results.values())
    assert envelope.memory_ref is None
    assert sum(SAVE_FAILED in line for line in envelope.warnings) == 1, envelope.warnings


def _call(service: HorosaSkillService, settings: Settings, tool: str, arguments: dict) -> dict:
    mcp = M.create_mcp_server(service, settings)

    async def _go():
        return await mcp.call_tool(tool, arguments)

    return json.loads(anyio.run(_go).content[0].text)


@pytest.mark.parametrize(
    ("tool", "arguments", "compact"),
    [
        ("horosa_astro_chart", CONFIRMED, False),
        ("horosa_tool_run", {"tool_name": "chart", "request": CONFIRMED}, True),
    ],
    ids=["technique-tool", "tool-run"],
)
def test_mcp_hands_back_the_chart_when_the_save_fails(tmp_path: Path, tool: str, arguments: dict, compact: bool) -> None:
    settings, service = _service(tmp_path, compact=compact)
    service.store.create_run = _locked
    body = _call(service, settings, tool, arguments)
    assert body["ok"] is True and body["data"], body
    assert body["memory_ref"] is None
    assert any(SAVE_FAILED in line for line in body["warnings"]), body["warnings"]


def test_mcp_dispatch_hands_back_the_results_when_the_save_fails(tmp_path: Path) -> None:
    settings, service = _service(tmp_path)
    service.store.record_dispatch_result = _disk_full
    body = _call(service, settings, "horosa_dispatch", {"query": "看看八字", "birth": BIRTH, "defaults_accepted": True})
    assert body["ok"] is True and body["results"], body
    assert body["memory_ref"] is None and any(SAVE_FAILED in line for line in body["warnings"]), body["warnings"]


@pytest.mark.parametrize(("argv", "body"), [
    (["tool", "run", "chart", "--stdin"], CONFIRMED),
    (["dispatch", "--stdin"], {"query": "看看八字", "birth": BIRTH, "defaults_accepted": True}),
], ids=["tool-run", "dispatch"])
def test_cli_prints_the_result_when_the_save_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, argv: list[str], body: dict) -> None:
    _settings, service = _service(tmp_path)
    service.store.create_run = _locked
    monkeypatch.setattr(C, "_service", lambda: service)
    result = CliRunner().invoke(C.app, argv, input=json.dumps(body))
    assert result.exit_code == 0, (result.output, repr(result.exception))
    printed = json.loads(result.stdout)
    assert printed["ok"] is True and printed["memory_ref"] is None


def test_report_from_tool_explains_that_the_save_failed(tmp_path: Path) -> None:
    """报告要读存档，存档没了就出不了；但起盘那步的告警要带出来，别只说「没存上」。"""
    _settings, service = _service(tmp_path)
    service.store.create_run = _locked
    with pytest.raises(ToolValidationError) as excinfo:
        service.report_from_tool({"tool_name": "chart", "payload": CONFIRMED, "format": "json", "style": "chart"})
    assert excinfo.value.code == "report.from_tool.unsaved_result"
    assert any(SAVE_FAILED in line for line in excinfo.value.details["warnings"])


# ---- 四个工具体合成一个：闸门 + 兜底只有一份 -----------------------------------------------------


@pytest.mark.parametrize(
    ("tool", "method", "arguments", "compact"),
    [
        ("horosa_astro_chart", "run_tool", CONFIRMED, False),
        ("horosa_tool_run", "run_tool", {"tool_name": "chart", "request": CONFIRMED}, True),
        ("horosa_dispatch", "dispatch", {"query": "看看八字", "birth": BIRTH, "defaults_accepted": True}, False),
        ("horosa_hecan", "hecan", {"query": "看看八字", "birth": BIRTH, "defaults_accepted": True}, False),
        ("horosa_report_from_tool", "report_from_tool", {"tool_name": "chart", "payload": CONFIRMED}, False),
    ],
    ids=["technique-tool", "tool-run", "dispatch", "hecan", "report-from-tool"],
)
def test_an_unexpected_exception_is_a_structured_result_on_every_gated_tool(
    tmp_path: Path, tool: str, method: str, arguments: dict, compact: bool
) -> None:
    settings, service = _service(tmp_path, compact=compact)

    def _boom(*_args, **_kwargs):
        raise KeyError("engine shape changed")

    setattr(service, method, _boom)
    body = _call(service, settings, tool, arguments)
    assert body["ok"] is False and body["code"] == "tool.internal_error", body


def _gate_call_sites(source: str) -> list[str]:
    """`_agent_preflight_error` 只许在 `_gated_run` 里调：多一个调用点就多一份会漂开的闸门 + 兜底。"""
    sites: list[str] = []
    for function in ast.walk(ast.parse(source)):
        if isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
            direct = [
                node for node in ast.walk(function)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_agent_preflight_error"
            ]
            sites.extend(function.name for _ in direct)
    return sites


def test_the_server_has_one_gated_body() -> None:
    assert _gate_call_sites(Path(M.__file__).read_text(encoding="utf-8")) == ["_gated_run"]


def test_the_body_scan_catches_a_hand_rolled_copy() -> None:
    source = "async def _gated_run():\n    _agent_preflight_error('a', {})\nasync def fresh():\n    _agent_preflight_error('b', {})\n"
    assert _gate_call_sites(source) == ["_gated_run", "fresh"]
