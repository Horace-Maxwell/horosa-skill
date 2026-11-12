"""Gate questions ask the right things (agent_guidance/questions.py, v0.50.0-dev).

Before: questions were filtered only by literal keys, so pseudo-fields (location / birth data / cast-input …) were
re-asked after being answered, 南半球月令 was asked for Shanghai, `huangli {"date": …}` was blocked with an empty prompt,
questions were Chinese-only, and a confirmation flag also waved through facts only the user has (gender).
"""
from __future__ import annotations

import json

import pytest

from horosa_skill.agent_guidance import validate_agent_preflight
from horosa_skill.agent_guidance import questions as Q
from horosa_skill.agent_guidance.base import PREFLIGHT_EXEMPT_TOOLS
from horosa_skill.agent_guidance.tool_table import TOOL_GUIDANCE
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.testing_payloads import build_sample_payloads

SAMPLES = build_sample_payloads()
SHANGHAI = {"date": "1990-05-03", "time": "08:00:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"}
# 不是模型字段、但载荷里可以带（FlexibleModel 收下）并回答问题的键。
PAYLOAD_ONLY_KEYS = {"place", "location", "question", "topic", "qijuMethod", "sex"}


def _all_questions():
    for tool, policy in sorted(TOOL_GUIDANCE.items()):
        for question in policy.get("ask_if_missing", []):
            yield tool, question


def test_every_gate_question_has_an_english_version() -> None:
    missing = sorted({q["question"] for _tool, q in _all_questions() if Q.english(q["question"]) is None})
    assert not missing, f"add these to data/gate_questions_en.json: {missing}"


def test_every_gate_question_says_which_keys_answer_it() -> None:
    """每个问题要么能被载荷里的键回答（键必须是该技法的字段或登记过的载荷键），要么明确是「只能确认」类。"""
    bad = []
    for tool, question in _all_questions():
        groups = Q.answer_groups(tool, question["field"])
        if groups is None:
            continue
        fields = set(TOOL_DEFINITIONS[tool].input_model.model_fields) | PAYLOAD_ONLY_KEYS
        for group in groups:
            for key in group:
                root = key.lstrip("@").split(".")[0]
                if root != "location" and root not in fields:
                    bad.append((tool, question["field"], key))
    assert not bad, bad


def test_a_complete_payload_runs_without_flags_and_a_missing_one_still_blocks() -> None:
    assert validate_agent_preflight("huangli", {"date": "2026-11-11"}) == {
        "ok": True, "tool_name": "huangli", "enforced": True, "mode": "nothing_to_confirm"}
    blocked = validate_agent_preflight("huangli", {})
    assert not blocked["ok"] and blocked["agent_recovery"]["prompt_to_user"].strip()
    # 给了 seed 就不再问塔罗的起卦时刻；牌阵（流派级设置）照问。
    tarot = validate_agent_preflight("tarot", {"seed": "abc", "question": "工作"})
    assert [item["field"] for item in tarot["ask_if_missing"]] == ["spread"]
    assert validate_agent_preflight("calendar_month", {"date": "2026-11-01", "zone": "+08:00", "lon": "121e28"})["ok"]


def test_southern_month_question_only_for_southern_latitudes() -> None:
    north = validate_agent_preflight("bazi_birth", {**SHANGHAI, "gender": 1})
    assert "southMonth" not in [item["field"] for item in north["ask_if_missing"]]
    south = validate_agent_preflight("bazi_birth", {**SHANGHAI, "lat": "33s52", "gender": 1})
    assert "southMonth" in [item["field"] for item in south["ask_if_missing"]]
    assert "birth data" not in [item["field"] for item in north["ask_if_missing"]], "已给的出生数据不再问"


@pytest.mark.parametrize("tool", sorted(Q.GENDER_FACT_TOOLS))
def test_a_confirmation_cannot_stand_in_for_gender(tool: str) -> None:
    sample = {k: v for k, v in SAMPLES[tool].items() if k != "gender"}
    for flag in ("agent_confirmed_settings", "defaults_accepted"):
        verdict = validate_agent_preflight(tool, {**sample, flag: True})
        assert not verdict["ok"] and verdict["agent_recovery"]["reason"] == "missing_required_facts", tool
        item = verdict["ask_if_missing"][0]
        assert item["field"] == "gender" and item["fact"] is True and item["values"] == [1, 0]
    assert validate_agent_preflight(tool, {**sample, "gender": 0, "agent_confirmed_settings": True})["ok"]


@pytest.mark.parametrize("tool", sorted(set(TOOL_GUIDANCE) - PREFLIGHT_EXEMPT_TOOLS))
def test_every_refusal_is_bilingual_and_never_spells_a_huge_option_list(tool: str) -> None:
    verdict = validate_agent_preflight(tool, {})
    if verdict["ok"]:
        return
    for item in verdict["ask_if_missing"]:
        assert " / " in item["question"], (tool, item["question"])
        assert len(item.get("options") or []) <= Q.MAX_SPELLED_OPTIONS, (tool, item["field"])
    prompt = verdict["agent_recovery"]["prompt_to_user"]
    assert "Before running" in prompt or "facts only the user knows" in prompt
    assert f"`{tool}`" not in prompt or tool not in {"chart", "qimen", "bazi_birth"}, "use display names"
    assert len(json.dumps(verdict, ensure_ascii=False).encode()) < 12_000, tool


def test_guidance_intent_selects_a_few_techniques_instead_of_echoing() -> None:
    """F2：`intent` 过去只被回显，未命中的 hint 指向 1.4 MB 的 include_all。现在回几种技法 + 各自要的字段（几 KB）。"""
    from horosa_skill.agent_guidance.catalog import build_agent_guidance

    guidance = build_agent_guidance(intent="他喜欢我吗")
    rows = guidance["suggested_tools"]
    assert 1 <= len(rows) <= 5 and rows[0]["tool"] == "sixyao" and rows[0]["name"] == "六爻"
    assert {"date", "time"} <= set(rows[0]["required_fields"]) and rows[0]["time_role"] == "moment"
    assert len(json.dumps(guidance, ensure_ascii=False).encode()) < 10_000
    assert build_agent_guidance(intent="zi wei dou shu")["suggested_tools"][0]["tool"] == "ziwei_birth"
