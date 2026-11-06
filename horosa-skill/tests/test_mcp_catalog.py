"""MCP 资源与提示词挪出 `create_mcp_server` 之后，两种工具面都要照常注册。提示词原先没有任何测试：不注册全仓照绿。"""
from __future__ import annotations

from pathlib import Path

import anyio
import pytest

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces import mcp_server as M


def _server(tmp_path: Path, *, compact: bool):
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
                        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs", mcp_compact=compact)
    return M.create_mcp_server(HorosaSkillService(settings, store=MemoryStore(settings)), settings)


@pytest.mark.parametrize("compact", [False, True], ids=["full", "compact"])
def test_both_surfaces_register_the_prompts(tmp_path: Path, compact: bool) -> None:
    async def _names() -> list[str]:
        listed = await _server(tmp_path, compact=compact).list_prompts()
        return sorted(prompt.name for prompt in getattr(listed, "prompts", listed))

    assert anyio.run(_names) == ["annual_fortune", "export_report", "quick_cast"]


@pytest.mark.parametrize("compact", [False, True], ids=["full", "compact"])
def test_both_surfaces_register_the_resources(tmp_path: Path, compact: bool) -> None:
    async def _uris() -> list[str]:
        listed = await _server(tmp_path, compact=compact).list_resources()
        return sorted(str(resource.uri) for resource in getattr(listed, "resources", listed))

    assert anyio.run(_uris) == ["horosa://catalog/export-registry", "horosa://catalog/techniques", "horosa://runtime/status"]


def test_a_prompt_still_renders_its_arguments(tmp_path: Path) -> None:
    async def _text() -> str:
        rendered = await _server(tmp_path, compact=False).get_prompt("quick_cast", {"technique": "大六壬", "question": "问事业"})
        return rendered.messages[0].content.text

    text = anyio.run(_text)
    assert "大六壬" in text and "问事业" in text
