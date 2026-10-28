"""工具面设计（v0.45.0）：检索 / 精读分成两个工具、核心工具常驻、报告结果带文件卡与 resource_link。

依据见 docs/LESSONS.md v0.45.0-dev（Anthropic「Writing effective tools for agents」、MCP 2025-06-18 起的 resource_link、
OpenAI search/fetch、qmd query/get）。
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces.mcp_runner import RESOURCE_LINK_SINCE, _with_file_link


def _server(tmp_path: Path):
    from horosa_skill.surfaces.mcp_server import create_mcp_server

    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
                        db_path=tmp_path / "m.db", output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt",
                        data_dir=tmp_path / "data")
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    return create_mcp_server(service, settings), service


def test_knowledge_search_is_its_own_always_loaded_read_only_tool(tmp_path: Path) -> None:
    from mcp.shared.memory import create_connected_server_and_client_session

    notes = tmp_path / "data" / "knowledge"
    notes.mkdir(parents=True)
    (notes / "笔记.md").write_text("## 休门\n\n休门在坎宫，主休养。", encoding="utf-8")
    mcp, _ = _server(tmp_path)

    async def run() -> tuple[dict, dict]:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
            result = await client.call_tool("horosa_knowledge_search", {"query": "休门", "domain": "user"})
            return tools, json.loads(result.content[0].text)

    tools, result = asyncio.run(run())
    search = tools["horosa_knowledge_search"]
    assert search.annotations.readOnlyHint is True and search.annotations.destructiveHint is False
    assert (search.meta or {}).get("anthropic/alwaysLoad") is True  # 不被工具搜索延后
    assert search.description.startswith("Search knowledge")  # 关键词放最前（工具搜索只看描述开头）
    assert "from_line" in json.dumps(tools["horosa_knowledge_read"].inputSchema)
    match = result["matches"][0]
    assert match["key"] == "笔记" and match["heading"] == "休门" and match["read"]["from_line"] == 1


def test_report_results_carry_a_file_card_and_a_resource_link_for_new_clients(tmp_path: Path) -> None:
    from mcp.shared.memory import create_connected_server_and_client_session

    from horosa_skill.service.api.reports import _file_card

    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%PDF-1.7 fake")
    card = _file_card(pdf, "pdf")
    assert card["uri"] == pdf.resolve().as_uri() and card["mime"] == "application/pdf" and card["bytes"] == 13
    mcp, service = _server(tmp_path)
    service.report_render = lambda payload: {"ok": True, "artifact_path": str(pdf), "file": card}

    async def run():
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            return await client.call_tool("horosa_report_render", {"run_id": "x", "format": "pdf"})

    result = asyncio.run(run())
    links = [block for block in result.content if block.type == "resource_link"]
    assert json.loads(result.content[0].text)["file"]["sha256"] == card["sha256"]
    assert len(links) == 1 and str(links[0].uri) == card["uri"] and links[0].mimeType == "application/pdf"


def test_old_protocol_clients_get_no_resource_link() -> None:
    raw = {"file": {"uri": "file:///tmp/r.pdf", "name": "r.pdf", "mime": "application/pdf", "bytes": 1}}
    converted = ["json-text-block"]
    assert _with_file_link(raw, converted, "2025-03-26") == converted
    assert _with_file_link(raw, converted, "") == converted
    assert len(_with_file_link(raw, converted, RESOURCE_LINK_SINCE)) == 2
    assert _with_file_link({"ok": True}, converted, "2099-01-01") == converted  # 没有文件卡就不加
