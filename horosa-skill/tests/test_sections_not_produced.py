"""按设计不产出的段不许读成「失败」（v0.50.0 深审余项）。

症状（全目录 live 扫，每个技法的样例载荷）：13 宫盘印「本次本地计算结果未返回「古典格局」细项」「…「占星地图」细项」——前者是深审第二
阶段按设计撤掉的（派生盘不挂本命口径的分析），后者由独立的 acg 工具产出；卦义 / 梅花卦义印三段断卦占位（这两个工具不起卦）；
紫微规则库印六段命盘占位（不排盘）；默认关段（太玄经全文、经典原文、年度吉日榜…）没要也印占位。

现在：exports.registry.SECTIONS_NOT_PRODUCED_BY_DESIGN（工具 → 段 → 理由）与默认关段缺席时，走节气盘那套「这次没要」——
不选、不占位、不算缺，export_snapshot.not_requested_sections 列名、not_requested_reasons 给理由。真产出了就照常保留。
负向对照（实跑过）：_sections_not_requested 不读这张表 → 离线与 live 用例红（占位回来）。
"""
from __future__ import annotations

import pytest
from test_local_js_tools import make_service, requires_runtime

from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.exports.contract import TOOL_EXPORT_TECHNIQUE_MAP
from horosa_skill.exports.registry import AI_EXPORT_OPTIONAL_SECTIONS, AI_EXPORT_PRESET_SECTIONS, SECTIONS_NOT_PRODUCED_BY_DESIGN
from horosa_skill.service.export import _build_generated_export_snapshot
from horosa_skill.testing_payloads import build_sample_payloads

PLACEHOLDER = "本次本地计算结果未返回"
CASES = [(tool, title) for tool, rows in SECTIONS_NOT_PRODUCED_BY_DESIGN.items() for title in rows]


@pytest.mark.parametrize("tool, title", CASES)
def test_table_names_real_preset_sections_with_reasons(tool: str, title: str) -> None:
    assert tool in TOOL_DEFINITIONS
    technique = TOOL_EXPORT_TECHNIQUE_MAP[tool]
    assert title in AI_EXPORT_PRESET_SECTIONS[technique], (technique, title)
    assert title in AI_EXPORT_OPTIONAL_SECTIONS.get(technique, []), "按设计缺席的段必须同时是 optional（否则会算成 missing）"
    assert SECTIONS_NOT_PRODUCED_BY_DESIGN[tool][title].strip()


def _parsed(titles: list[str]) -> dict:
    return {"sections": [{"title": t, "body": f"{t}正文", "content": f"[{t}]\n{t}正文"} for t in titles]}


@pytest.mark.parametrize("tool, title", CASES)
def test_absent_by_design_section_is_not_a_placeholder(tool: str, title: str) -> None:
    technique = TOOL_EXPORT_TECHNIQUE_MAP[tool]
    present = [t for t in AI_EXPORT_PRESET_SECTIONS[technique] if t != title][:3]
    snap = _build_generated_export_snapshot(technique=technique, tool_name=tool, input_normalized={}, response_data={},
                                            snapshot_text="x", parsed_snapshot=_parsed(present))
    assert title not in snap["selected_sections"] and f"[{title}]" not in snap["export_text"]
    assert title in snap["not_requested_sections"] and snap["not_requested_reasons"][title]
    assert title not in snap["missing_selected_sections"]
    # 真产出了就照常保留（表只管「缺席」）。
    kept = _build_generated_export_snapshot(technique=technique, tool_name=tool, input_normalized={}, response_data={},
                                            snapshot_text="x", parsed_snapshot=_parsed([*present, title]))
    assert f"[{title}]" in kept["export_text"] and title not in kept.get("not_requested_sections", [])


def test_default_off_sections_are_not_requested_when_absent() -> None:
    snap = _build_generated_export_snapshot(technique="taixuan", tool_name="taixuan", input_normalized={}, response_data={},
                                            snapshot_text="x", parsed_snapshot=_parsed(["起盘信息"]))
    assert "太玄经全文" in snap["not_requested_sections"] and "默认关段" in snap["not_requested_reasons"]["太玄经全文"]


@requires_runtime
@pytest.mark.parametrize("tool", sorted(SECTIONS_NOT_PRODUCED_BY_DESIGN))
def test_live_by_design_sections_never_read_as_failures(tmp_path, tool: str) -> None:
    env = make_service(tmp_path).run_tool(tool, build_sample_payloads()[tool], save_result=False)
    assert env.ok, env.error
    snap = env.data["export_snapshot"]
    for title in SECTIONS_NOT_PRODUCED_BY_DESIGN[tool]:
        assert f"「{title}」" not in snap["export_text"] and f"[{title}]" not in snap["export_text"], title
        assert title in snap["not_requested_sections"], title
    assert not any("不完整" in warning for warning in env.warnings)
