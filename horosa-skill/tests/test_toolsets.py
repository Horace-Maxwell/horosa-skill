"""v0.36.0 B2 — HOROSA_TOOLSETS: aliases, unknown-token fallback, and tool_run on every filtered surface.

Before: a typo (`HOROSA_TOOLSETS=astr`) registered zero technique tools and no `horosa_tool_run` — the
client saw only facades and no way to reach any technique.
"""
from __future__ import annotations

import asyncio
import json
import re

import pytest

from horosa_skill.config import Settings
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces.mcp_server import create_mcp_server
from horosa_skill.surfaces.mcp_surface import _resolve_toolsets, _server_profile


def _names(tmp_path, monkeypatch, toolsets: str) -> set[str]:
    monkeypatch.setenv("HOROSA_TOOLSETS", toolsets)
    settings = Settings(db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    mcp = create_mcp_server(HorosaSkillService(settings, store=MemoryStore(settings)), settings)
    return {tool.name for tool in asyncio.run(mcp.list_tools())}


def test_resolve_toolsets_aliases_and_unknowns() -> None:
    assert _resolve_toolsets("") == {"requested": [], "effective": None, "unknown": [], "problem": None}
    assert _resolve_toolsets("western")["effective"] == {"astro", "predict", "chart"}
    assert _resolve_toolsets("Chinese, other")["effective"] == {"cn", "shenshu", "other"}
    typo = _resolve_toolsets("astr")
    # MCP-07：一个合法 token 都没有 → 安全面（零平铺技法 + horosa_tool_run），不是「全部 127」；问题写进 problem
    assert typo["effective"] == set() and typo["unknown"] == ["astr"] and "astr" in typo["problem"]
    mixed = _resolve_toolsets("cn,astr")
    assert mixed["effective"] == {"cn"} and mixed["unknown"] == ["astr"] and "astr" in mixed["problem"]
    assert _resolve_toolsets("none")["effective"] == set() and _resolve_toolsets("none")["problem"] is None
    # `all`（或把每个域都点了名）就是完整目录本身：不额外注册 horosa_tool_run
    assert _resolve_toolsets("all")["effective"] is None and _resolve_toolsets("western,chinese,reference,other")["effective"] is None


def test_typo_fails_safe_to_the_compact_technique_surface(tmp_path, monkeypatch) -> None:
    """旧行为（v0.36.0 B2 起）：全是拼错的 token → 回落全量平铺。一个拼错的白名单悄悄变成「全开」——
    旧断言写的正是这条（`horosa_cn_qimen in names`），把 fail-open 当成了契约。现在：零平铺技法 + tool_run，可达性不丢。"""
    names = _names(tmp_path, monkeypatch, "astr")
    assert "horosa_tool_run" in names
    assert not any(name in names for name in (d.mcp_name for d in TOOL_DEFINITIONS.values()))


def test_all_is_exactly_the_full_catalogue(tmp_path, monkeypatch) -> None:
    unset = _names(tmp_path, monkeypatch, "")
    assert _names(tmp_path, monkeypatch, "all") == unset, "`all` 曾比全量多一个 horosa_tool_run（128）"
    assert "horosa_tool_run" not in unset


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
    result = getattr(result, "content", result)  # mcp 2.x：CallToolResult
    if isinstance(result, tuple):
        content, structured = result
        payload = structured if isinstance(structured, dict) else json.loads(content[0].text)
    elif isinstance(result, dict):
        payload = result
    else:
        payload = json.loads(result[0].text)
    profile = payload.get("server_profile") or payload.get("result", {}).get("server_profile")
    assert profile and profile["toolsets_effective"] == ["astro", "chart", "predict"]


def _instructions_and_count(tmp_path, monkeypatch, toolsets: str, *, compact: bool = False) -> tuple[str, int, set[str]]:
    monkeypatch.setenv("HOROSA_TOOLSETS", toolsets)
    settings = Settings(db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs", mcp_compact=compact)
    mcp = create_mcp_server(HorosaSkillService(settings, store=MemoryStore(settings)), settings)
    names = {tool.name for tool in asyncio.run(mcp.list_tools())}
    return mcp.instructions, len(names), names


@pytest.mark.parametrize(("toolsets", "compact"), [("", False), ("", True), ("all", False), ("western", False), ("cn", False),
                                                    ("astr", False), ("none", False)])
def test_instructions_describe_what_is_actually_registered(tmp_path, monkeypatch, toolsets: str, compact: bool) -> None:
    """MCP-07：说明书里的工具数与 tools/list 一致；技法没全部平铺时，说明书指明 horosa_tool_run 是通道。"""
    text, count, names = _instructions_and_count(tmp_path, monkeypatch, toolsets, compact=compact)
    claimed = [int(n) for n in re.findall(r"WHAT IT COVERS \((\d+) tools", text)]
    assert claimed == [count], (toolsets, compact, claimed, count)
    assert len(text.encode("utf-8")) <= 2048
    if "horosa_tool_run" in names:
        assert "horosa_tool_run(tool_name=" in text
    else:
        assert "horosa_tool_run(tool_name=" not in text


def test_a_toolsets_problem_reaches_stderr_and_the_server_profile(tmp_path, monkeypatch, capsys) -> None:
    _names(tmp_path, monkeypatch, "astr,cnn")
    err = capsys.readouterr().err
    assert "HOROSA_TOOLSETS" in err and "astr" in err and "cnn" in err
    profile = _server_profile(Settings(db_path=None, output_dir=None))
    assert "astr" in profile["toolsets_problem"] and profile["tool_run_registered"] is True
    from horosa_skill.surfaces import doctor

    warnings = doctor._toolsets_doctor_warnings()
    assert [w["code"] for w in warnings] == ["config:toolsets_invalid"] and "astr" in warnings[0]["detail"]
    assert doctor._advice_for("config:toolsets_invalid")["next_action"]
    monkeypatch.setenv("HOROSA_TOOLSETS", "western")
    assert doctor._toolsets_doctor_warnings() == []
