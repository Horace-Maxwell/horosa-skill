"""几处「换一种写法就不认」与「错误里不给下一步」（审计 S-20 / S-21 / O-12 / O-20 / O-21）。

- S-21 塔罗牌阵收常见写法（三张牌 / Celtic cross / 凯尔特十字），以前先撞一次 66 个键、没有中文名的错。
- S-20 report_render 只给 run_id + format：summary 第一句给两条出路（style:"chart" 立刻出文件 / 填 ai_report），不再说「已完成起盘」。
- O-12 memory_show 的 response_tool 收 MCP 名与中文名。
- O-20 knowledge_read 没给 category 时跨类找键（休门在 qimen/door 下）。
- O-21 export_parse 的 technique 收中文标签与技法名；认不出时给候选。
负向对照（实跑过）：各自把新分支去掉，对应用例红。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.knowledge.store import read_knowledge_entry
from horosa_skill.memory.store import MemoryStore
from horosa_skill.result_view import take_view_request
from horosa_skill.service import HorosaSkillService
from horosa_skill.testing_payloads import build_sample_payloads


@pytest.fixture()
def service(tmp_path: Path) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path,
                        runtime_root=tmp_path / "runtime", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs",
                        trace_enabled=False)
    return HorosaSkillService(settings, store=MemoryStore(settings))


@pytest.mark.parametrize(("spread", "key"), [("三张牌", "three"), ("Celtic cross", "celtic"), ("凯尔特十字", "celtic")])
def test_tarot_spread_wordings(service, spread, key) -> None:
    result = service.run_tool("tarot", {**build_sample_payloads()["tarot"], "spread": spread}, save_result=False)
    assert result.ok, result.error
    assert any(f"牌阵「{spread}」按 {key} 读" in line for line in result.warnings)


def test_report_render_without_ai_says_how_to_get_a_file(service) -> None:
    run = service.run_tool("tarot", build_sample_payloads()["tarot"])
    body = service.report_render({"run_id": run.memory_ref.run_id, "format": "pdf"})
    assert body["final_report_generated"] is False
    assert 'style:"chart"' in body["summary"][0] and "没有重新起盘" in body["summary"][1]


def test_response_tool_takes_mcp_and_chinese_names() -> None:
    assert take_view_request({"response_tool": "horosa_astro_chart"}, default_view="reading")[1].tool == "chart"
    assert take_view_request({"response_tool": "八字"}, default_view="reading")[1].tool == "bazi_birth"


def test_knowledge_read_finds_the_category_itself() -> None:
    entry = read_knowledge_entry({"domain": "qimen", "key": "休门"})
    assert entry["resolved_category"] == "door"


def test_export_parse_takes_labels_and_tool_names(service) -> None:
    content = "[起盘信息]\n日期：2026-11-14"
    for technique in ("八字", "horosa_cn_qimen"):
        assert service.run_tool("export_parse", {"technique": technique, "content": content}, save_result=False).ok
    bad = service.run_tool("export_parse", {"technique": "奇", "content": content}, save_result=False)
    assert bad.error.code == "tool.invalid_export_technique" and {c["key"] for c in bad.error.details["candidates"]} >= {"qimen"}
