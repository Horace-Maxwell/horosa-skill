"""审计 S-30：HOROSA_OUTPUT_SCHEMA=1 时全体工具共用一个极小 outputSchema（以前每个工具一份完整信封 schema，tools/list 485 KB）。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService


def test_every_tool_shares_one_small_output_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """负向对照（实跑过）：apply_advertised_schemas 不调 share_minimal_output_schema → 每份几 KB、合计约 28 万字节 → 红。"""
    monkeypatch.setenv("HOROSA_OUTPUT_SCHEMA", "1")
    from horosa_skill.surfaces.mcp_server import create_mcp_server

    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path,
                        db_path=tmp_path / "m.db", output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt")
    mcp = create_mcp_server(HorosaSkillService(settings, store=MemoryStore(settings)), settings)
    schemas = [tool.output_schema for tool in mcp._tool_manager.list_tools() if tool.output_schema is not None]
    assert schemas, "开了 HOROSA_OUTPUT_SCHEMA 应当有工具声明 outputSchema"
    assert max(len(json.dumps(schema)) for schema in schemas) <= 200
    assert sum(len(json.dumps(schema)) for schema in schemas) <= 200 * len(schemas)
