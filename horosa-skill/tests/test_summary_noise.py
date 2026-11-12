"""摘要与结果的噪声（深审 F13）：每个技法一句有信息的标题行（不再是「工具 `x` 已返回结构化结果」「顶层字段：…」）；
节气盘只查某个节气 / seedOnly 时，没要的二分二至盘不占位、不算「结果不完整」。"""
from __future__ import annotations

from pathlib import Path

import pytest
from fakes import FakeClient, FakeJsClient

from horosa_skill.config import Settings
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.memory.search import _FILLER_SUMMARY
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.testing_payloads import build_sample_payloads

SAMPLES = build_sample_payloads()


@pytest.fixture(scope="module")
def service(tmp_path_factory) -> HorosaSkillService:
    tmp = tmp_path_factory.mktemp("noise")
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", runtime_root=tmp / "rt",
                        db_path=tmp / "memory.db", output_dir=tmp / "runs")
    return HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())


def test_no_technique_summary_is_filler(service: HorosaSkillService) -> None:
    checked = 0
    for name in sorted(TOOL_DEFINITIONS):
        if name not in SAMPLES:
            continue
        try:
            result = service.run_tool(name, {**SAMPLES[name], "agent_confirmed_settings": True}, save_result=False)
        except Exception:  # noqa: BLE001 - 离线替身跑不了的技法不在这条守卫的范围
            continue
        if not result.ok:
            continue
        checked += 1
        filler = [line for line in result.summary if _FILLER_SUMMARY.match(line) or line.startswith("顶层字段")]
        assert not filler, (name, filler)
        assert result.summary and result.summary[0].strip(), name
    assert checked >= 80, checked


@pytest.mark.parametrize("extra", [{"jieqis": ["立春"]}, {"seedOnly": True}])
def test_jieqi_year_does_not_call_unrequested_charts_missing(service: HorosaSkillService, extra: dict) -> None:
    result = service.run_tool("jieqi_year", {**SAMPLES["jieqi_year"], **extra, "agent_confirmed_settings": True}, save_result=False)
    snapshot = result.data["export_snapshot"]
    assert snapshot["missing_selected_sections"] == []
    assert len(snapshot["not_requested_sections"]) == 12
    assert [s["title"] for s in snapshot["sections"]] == ["节气盘参数", "二十四节气"]
    assert "未返回" not in snapshot["export_text"]
    assert not any("结果不完整" in line for line in [*result.summary, *result.warnings])


def test_jieqi_year_asking_for_one_solstice_expects_only_its_charts(service: HorosaSkillService) -> None:
    result = service.run_tool("jieqi_year", {**SAMPLES["jieqi_year"], "jieqis": ["春分"], "agent_confirmed_settings": True},
                              save_result=False)
    snapshot = result.data["export_snapshot"]
    assert [s["title"] for s in snapshot["sections"]][2:] == ["春分星盘", "春分宿盘", "春分3D盘"]
    assert "夏至星盘" in snapshot["not_requested_sections"]
