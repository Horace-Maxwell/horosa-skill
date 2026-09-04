"""v0.36.0 B2 — HOROSA_TOOLSETS: aliases, unknown-token fallback, and tool_run on every filtered surface.

Before: a typo (`HOROSA_TOOLSETS=astr`) registered zero technique tools and no `horosa_tool_run` — the
client saw only facades and no way to reach any technique.
"""
from __future__ import annotations

import asyncio
import json

from horosa_skill.config import Settings
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces.mcp_server import _resolve_toolsets, _server_profile, create_mcp_server


def _names(tmp_path, monkeypatch, toolsets: str) -> set[str]:
    monkeypatch.setenv("HOROSA_TOOLSETS", toolsets)
    settings = Settings(db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    mcp = create_mcp_server(HorosaSkillService(settings, store=MemoryStore(settings)), settings)
    return {tool.name for tool in asyncio.run(mcp.list_tools())}


def test_resolve_toolsets_aliases_and_unknowns() -> None:
    assert _resolve_toolsets("") == {"requested": [], "effective": None, "unknown": []}
    assert _resolve_toolsets("western")["effective"] == {"astro", "predict", "chart"}
    assert _resolve_toolsets("Chinese, other")["effective"] == {"cn", "shenshu", "other"}
    typo = _resolve_toolsets("astr")
    assert typo["effective"] is None and typo["unknown"] == ["astr"]  # 全空 → 回落全量，不是零技法
    mixed = _resolve_toolsets("cn,astr")
    assert mixed["effective"] == {"cn"} and mixed["unknown"] == ["astr"]
    assert _resolve_toolsets("none")["effective"] == set()


def test_typo_falls_back_to_full_surface_and_still_registers_tool_run(tmp_path, monkeypatch) -> None:
    names = _names(tmp_path, monkeypatch, "astr")
    assert "horosa_cn_qimen" in names and "horosa_astro_chart" in names
    assert "horosa_tool_run" not in names  # 未过滤（回落全量）→ 与默认面一致


def test_western_alias_filters_and_registers_tool_run(tmp_path, monkeypatch) -> None:
    names = _names(tmp_path, monkeypatch, "western")
    assert "horosa_astro_chart" in names and "horosa_predict_solarreturn" in names
    assert "horosa_cn_qimen" not in names and "horosa_shenshu_tieban" not in names
    assert "horosa_tool_run" in names  # 被裁掉的技法仍可按名直呼


def test_none_is_compact_technique_surface(tmp_path, monkeypatch) -> None:
    names = _names(tmp_path, monkeypatch, "none")
    assert "horosa_tool_run" in names
    assert not any(name in names for name in (d.mcp_name for d in TOOL_DEFINITIONS.values()))


def test_server_profile_reports_what_is_exposed(monkeypatch) -> None:
    monkeypatch.setenv("HOROSA_TOOLSETS", "cn,typo")
    profile = _server_profile(Settings(db_path=None, output_dir=None))
    assert profile["toolsets_effective"] == ["cn"] and profile["toolsets_unknown"] == ["typo"]
    assert profile["tool_run_registered"] is True and profile["compact"] is False
    assert profile["technique_tools_registered"] == sum(1 for d in TOOL_DEFINITIONS.values() if d.domain == "cn")


def test_guidance_tool_carries_server_profile(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOROSA_TOOLSETS", "western")
    settings = Settings(db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    mcp = create_mcp_server(HorosaSkillService(settings, store=MemoryStore(settings)), settings)
    result = asyncio.run(mcp.call_tool("horosa_agent_guidance", {"include_all": False}))
    if isinstance(result, tuple):
        content, structured = result
        payload = structured if isinstance(structured, dict) else json.loads(content[0].text)
    elif isinstance(result, dict):
        payload = result
    else:
        payload = json.loads(result[0].text)
    profile = payload.get("server_profile") or payload.get("result", {}).get("server_profile")
    assert profile and profile["toolsets_effective"] == ["astro", "chart", "predict"]
