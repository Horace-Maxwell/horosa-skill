"""对外示例不教模型自我确认、不带夹具值与该技法不读的键（审计 S-09）。

修前：horosa_agent_guidance(tool_name=…) 的 input_contract.example_payload，114 个里 106 个带 "agent_confirmed_settings": true 和一句编好的
"User confirmed the birth/event data…"——弱模型照抄就自我确认过闸；还有 "name":"Horosa Smoke"、塔罗 / 择日里八个用不上的西占键。
负向对照（实跑过）：build_tool_input_contract 不过 public_example → 红。
"""
from __future__ import annotations

import json

import pytest

from horosa_skill.agent_guidance.contracts import build_tool_input_contract
from horosa_skill.engine.registry import TOOL_DEFINITIONS


def _keys(value) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for item in value.values() for k in _keys(item)}
    if isinstance(value, list):
        return {k for item in value for k in _keys(item)}
    return set()


@pytest.mark.parametrize("tool_name", sorted(TOOL_DEFINITIONS))
def test_public_example_has_no_confirmation_and_no_fixture_values(tool_name) -> None:
    example = build_tool_input_contract(tool_name).get("example_payload") or {}
    assert not {"agent_confirmed_settings", "defaults_accepted", "clarification_notes"} & _keys(example)
    blob = json.dumps(example, ensure_ascii=False)
    assert "Horosa Smoke" not in blob and "User confirmed" not in blob and "self-check fixture" not in blob
    fields = set(TOOL_DEFINITIONS[tool_name].input_model.model_fields)
    assert set(example) <= fields | {"place", "question", "profile"}, set(example) - fields


def test_sample_coordinates_become_place_names() -> None:
    example = build_tool_input_contract("bazi_birth")["example_payload"]
    assert example.get("place") == "上海" and "lat" not in example and "zone" not in example
