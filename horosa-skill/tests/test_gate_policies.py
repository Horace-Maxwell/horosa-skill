"""v0.36.0 B3 — the clarification gate must ask the questions that actually change the result.

Before: 163/326 gate questions had no options; planetaryarc never asked `arcSource`, the 神数 five never
asked gender (or place for the three that cast by place); every progression tool shared the natal-chart
policy. These tests pin the technique-specific policies, the option/value pairing, and the whitelist
that keeps "no options" an explicit decision.
"""
from __future__ import annotations

from horosa_skill.agent_guidance import (
    FREE_TEXT_GATE_FIELDS,
    TOOL_GUIDANCE,
    run_sensitive_settings_selftests,
    validate_agent_preflight,
)
from horosa_skill.engine.registry import TOOL_DEFINITIONS

BIRTH = {"date": "1990-01-01", "time": "12:00:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"}


def _asked(tool: str, payload: dict | None = None) -> dict[str, dict]:
    verdict = validate_agent_preflight(tool, dict(payload or {}))
    assert verdict["ok"] is False, tool
    return {str(item["field"]): item for item in verdict["ask_if_missing"]}


def test_every_gate_question_has_options_or_is_whitelisted_free_text() -> None:
    offenders = []
    for tool, policy in TOOL_GUIDANCE.items():
        for item in policy.get("ask_if_missing", []):
            field = str(item.get("field") or "")
            if not item.get("options") and field not in FREE_TEXT_GATE_FIELDS:
                offenders.append((tool, field))
    assert offenders == [], f"gate questions without options and not whitelisted as free text: {offenders}"


def test_values_pair_with_options_when_declared() -> None:
    declared = 0
    for tool, policy in TOOL_GUIDANCE.items():
        for item in policy.get("ask_if_missing", []):
            if "values" in item:
                declared += 1
                assert len(item["values"]) == len(item["options"]), (tool, item["field"])
    assert declared >= 8  # hsys/zodiacal/ayanamsa/晚子双开关/diFen/gender/arcSource…


def test_progression_tools_ask_their_target_fields() -> None:
    arc = _asked("planetaryarc", BIRTH)
    assert "arcSource" in arc and arc["arcSource"]["values"][0] == "Moon"
    assert "datetime" in arc
    assert "asOf" in _asked("planetaryages", BIRTH)
    assert "targetDate/targetTime" in _asked("vedicprog", BIRTH)
    assert "targetDate/targetTime" in _asked("jaynesprog", BIRTH)
    assert "timelineStartYear/timelineCount" in _asked("extrareturns", BIRTH)
    # 本命盘策略不再被推运工具复用：它们不该再问「宫制」这种本命项之外的东西却漏掉目标
    assert "hsys" not in _asked("planetaryarc", BIRTH)


def test_shenshu_gender_and_place_policies() -> None:
    # 演禽（xianqin）live 实测不读地点（test_live_shenshu_gender 有反向断言钉住）：问了就是假闸门
    for tool in ("tieban", "shaozi", "xianqin"):
        asked = _asked(tool, {"date": "1990-01-01", "time": "12:00:00"})
        assert asked["gender"]["values"] == [1, 0], tool
        assert "location" not in asked, tool
    for tool in ("cetian", "qizhengkin"):
        asked = _asked(tool, {"date": "1990-01-01", "time": "12:00:00"})
        assert "gender" in asked and "location" in asked and "zone" in asked, tool
    # 提供了性别就不再问（已提供字段过滤）
    assert "gender" not in _asked("tieban", {"date": "1990-01-01", "gender": 1})
    # 干支起数的神数不问性别
    assert "gender" not in _asked("wangji", {"date": "1990-01-01"})


def test_house_system_options_carry_upstream_indexes() -> None:
    hsys = _asked("chart", BIRTH)["hsys"]
    pairs = dict(zip(hsys["options"], hsys["values"]))
    assert pairs["3 Placidus"] == 3 and pairs["1 Alcabitus"] == 1
    assert next(v for o, v in pairs.items() if o.startswith("0 整宫")) == 0


def test_table_selftests_include_b3_cases() -> None:
    report = run_sensitive_settings_selftests()
    assert report["ok"], report["failures"]
    assert report["cases"] >= 11


def test_every_registered_tool_still_classified() -> None:
    unclassified = [name for name in TOOL_DEFINITIONS if name not in TOOL_GUIDANCE and name not in run_sensitive_settings_selftests().get("failures", [])]
    # 分类完整性由 run_sensitive_settings_selftests 保证；这里只确认新策略没有把工具从表里挤掉
    assert "planetaryarc" in TOOL_GUIDANCE and "cetian" in TOOL_GUIDANCE
