"""bazi_direct 不再单独广告成平铺工具，注册键照收（审计 S-16，维护者 2026-11-14 按推荐定）。

它与 bazi_birth 同一引擎、同一输出（Java 回退也统一走 /bazi/direct），两个并列工具只会让模型二选一、白占全量面。
负向对照（实跑过）：mcp_server 注册循环不跳 UNADVERTISED_TECHNIQUES → 第一个用例红。
"""
from __future__ import annotations

import asyncio

from horosa_skill.config import Settings
from horosa_skill.engine.registry import FACADE_TOOL_COUNT, FULL_SURFACE_TOOL_COUNT, TOOL_DEFINITIONS, resolve_tool_name
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces.mcp_server import create_mcp_server


def _settings(tmp_path) -> Settings:
    return Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path,
                    runtime_root=tmp_path / "runtime", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs",
                    trace_enabled=False)


def test_full_surface_lists_bazi_birth_but_not_bazi_direct(tmp_path) -> None:
    settings = _settings(tmp_path)
    names = {tool.name for tool in asyncio.run(create_mcp_server(HorosaSkillService(settings, store=MemoryStore(settings)), settings).list_tools())}
    assert "horosa_cn_bazi_birth" in names and "horosa_cn_bazi_direct" not in names
    assert len(names) == FULL_SURFACE_TOOL_COUNT == FACADE_TOOL_COUNT + len(TOOL_DEFINITIONS) - 1


def test_the_registry_key_still_resolves() -> None:
    assert resolve_tool_name("bazi_direct") == "bazi_direct"
    assert resolve_tool_name("horosa_cn_bazi_direct") == "bazi_direct"   # tool_run / CLI / 记忆检索照认旧名
