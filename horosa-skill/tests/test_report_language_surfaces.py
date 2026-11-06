"""MCP 上的报告语言跟随全局输出文字（v0.47.2-dev）。

`ReportXInput.language` 缺省 `"zh-CN"`，而 `_normalize_mcp_request` 的 `model_dump` 把缺省值写成了显式入参，`_report_language` 据
`model_fields_set` 判「调用方写了」——于是 MCP 上 HOROSA_OUTPUT_SCRIPT 对报告恒不生效：同一个 run，CLI 出繁体，MCP 出简体。
v0.43.0 只在 CLI 那头修过（CLI 不传缺省），`test_textscript` 直接调帮手函数，从没走过 MCP。这里全走 `call_tool`。
"""
from __future__ import annotations

import json
from pathlib import Path

import anyio
import pytest
from fakes import FakeClient, FakeJsClient
from typer.testing import CliRunner

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces import cli as C
from horosa_skill.surfaces import mcp_server as M
from horosa_skill.textscript import SIMPLIFIED, TRADITIONAL

CONFIRMED = {"date": "1990-06-15", "time": "10:30:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gender": 1,
             "defaults_accepted": True}


def _service(tmp_path: Path, script: str) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
                        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs", output_script=script)
    return HorosaSkillService(settings, client=FakeClient(), chart_client=FakeClient(), js_client=FakeJsClient(),
                              store=MemoryStore(settings))


def _call(service: HorosaSkillService, tool: str, arguments: dict) -> dict:
    mcp = M.create_mcp_server(service, service.settings)

    async def _go():
        return await mcp.call_tool(tool, arguments)

    return json.loads(anyio.run(_go).content[0].text)


def _render(service: HorosaSkillService, run_id: str, **extra) -> dict:
    body = _call(service, "horosa_report_render",
                 {"run_id": run_id, "tool_name": "chart", "format": "json", "style": "chart", **extra})
    assert body.get("ok") is True, body
    return json.loads(Path(body["artifact_path"]).read_text(encoding="utf-8"))


def _run_id(service: HorosaSkillService) -> str:
    return service.run_tool("chart", dict(CONFIRMED)).memory_ref.run_id


def test_mcp_render_follows_the_traditional_setting(tmp_path: Path) -> None:
    service = _service(tmp_path, TRADITIONAL)
    document = _render(service, _run_id(service))
    text = json.dumps(document, ensure_ascii=False)
    assert document["language"] == "zh-TW"
    assert text.count("宮") > text.count("宫"), "正文要真转成繁体，不只是 language 字段"


def test_mcp_template_follows_the_traditional_setting(tmp_path: Path) -> None:
    service = _service(tmp_path, TRADITIONAL)
    assert _call(service, "horosa_report_template", {"run_id": _run_id(service), "tool_name": "chart"})["language"] == "zh-TW"


def test_mcp_from_tool_follows_the_traditional_setting(tmp_path: Path) -> None:
    service = _service(tmp_path, TRADITIONAL)
    body = _call(service, "horosa_report_from_tool",
                 {"tool_name": "chart", "payload": CONFIRMED, "format": "json", "style": "chart"})
    assert body.get("ok") is True, body
    assert json.loads(Path(body["artifact_path"]).read_text(encoding="utf-8"))["language"] == "zh-TW"


def test_an_explicit_language_still_wins_on_mcp(tmp_path: Path) -> None:
    service = _service(tmp_path, TRADITIONAL)
    assert _render(service, _run_id(service), language="zh-CN")["language"] == "zh-CN"


def test_the_simplified_default_is_unchanged(tmp_path: Path) -> None:
    service = _service(tmp_path, SIMPLIFIED)
    assert _render(service, _run_id(service))["language"] == "zh-CN"


@pytest.mark.parametrize("script", [SIMPLIFIED, TRADITIONAL])
def test_mcp_and_cli_render_the_same_language(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, script: str) -> None:
    service = _service(tmp_path, script)
    monkeypatch.setattr(C, "_service", lambda: service)
    run_id = _run_id(service)
    target = tmp_path / "runs" / "cli.json"
    result = CliRunner().invoke(C.app, ["report", "render", "--run-id", run_id, "--tool", "chart", "--format", "json",
                                        "--style", "chart", "--output", str(target)])
    assert result.exit_code == 0, result.output
    assert json.loads(target.read_text(encoding="utf-8"))["language"] == _render(service, run_id)["language"]
