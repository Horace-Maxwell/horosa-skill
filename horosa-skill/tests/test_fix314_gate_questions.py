"""审计 F26：闸门问得多、念给用户的话夹内部键名。

- 给了 date + time + place 不再问「出生日期、时间、时区和地点」；问题里要地点（城市即可），不要时区。
- 八字 08:00 不问子时换日 / 晚子时（late-zi.md：23 点以外两开关不起作用），只问真太阳时；23:30 照问。
- 没选恒星黄道不问岁差制。
- prompt_to_user 里没有 `timeAlg=0` / options_keys / 驼峰键；缺省句是人话。
- 地名歧义的抬头是「只有用户知道的信息」，不是「设置」。
"""
from __future__ import annotations

import re

from horosa_skill.agent_guidance.preflight import build_clarification_recovery, validate_agent_preflight

BAZI = {"date": "1990-05-03", "place": "上海", "gender": "女"}
_INTERNAL = re.compile(r"options_keys|[a-z]+[A-Z][A-Za-z]*\s*=|\b[a-z]+[A-Z][A-Za-z]+\b|SIDEREAL_AYANAMSA|上游表")


def _prompt(tool: str, payload: dict) -> tuple[list[str], str]:
    result = validate_agent_preflight(tool, payload)
    recovery = result.get("agent_recovery") or {}
    return [str(item.get("field")) for item in result.get("ask_if_missing") or []], str(recovery.get("prompt_to_user") or "")


def test_bazi_far_from_zi_asks_only_true_solar_time_and_no_birth_data() -> None:
    """负向对照（实跑过）：preflight.open_questions 不调 questions.narrow、birth data 别名去掉 place 组 → 红。"""
    fields, prompt = _prompt("bazi_birth", {**BAZI, "time": "08:00"})
    assert "birth data" not in fields
    assert "timeAlg" in fields and not any("after23NewDay" in field for field in fields)
    assert "子时换日" not in prompt and "23 点换日" not in prompt


def test_bazi_near_zi_still_asks_the_two_switches() -> None:
    fields, _ = _prompt("bazi_birth", {**BAZI, "time": "23:30"})
    assert any("after23NewDay" in field for field in fields)


def test_west_china_true_solar_time_near_zi_still_asks() -> None:
    """喀什 02:00（北京时间）≈ 当地平太阳时 23:04：钟点离 23 点远、真太阳时却在子时 → 照问。"""
    fields, _ = _prompt("bazi_birth", {"date": "1990-05-03", "time": "02:00", "zone": "+08:00", "lat": "39n28", "lon": "75e59", "gender": "女"})
    assert any("after23NewDay" in field for field in fields)


def test_ayanamsa_is_asked_only_for_sidereal() -> None:
    base = {"date": "1990-05-03", "time": "08:00", "place": "上海"}
    assert "siderealAyanamsa" not in _prompt("chart", base)[0]
    assert "siderealAyanamsa" in _prompt("chart", {**base, "zodiacal": 1})[0]


def test_prompt_to_user_has_no_internal_keys_and_asks_for_a_city() -> None:
    for tool, payload in (("bazi_birth", {**BAZI, "time": "08:00"}), ("chart", {"date": "1990-05-03", "time": "08:00", "place": "上海"}),
                          ("relative", {"inner": {"date": "1990-05-03", "time": "08:00", "place": "上海"}}), ("ziwei_birth", {})):
        _, prompt = _prompt(tool, payload)
        assert prompt and not _INTERNAL.search(prompt), (tool, _INTERNAL.search(prompt))
        assert "时区" not in prompt, tool


def test_place_ambiguity_is_framed_as_a_fact() -> None:
    recovery = build_clarification_recovery(tool_name="chart", ask_if_missing=[{"field": "place", "question": "「朝阳」是哪一个？"}],
                                            do_not_assume=[], reason="place_ambiguous")
    assert "只有用户知道" in recovery["prompt_to_user"] and "会影响结果的设置" not in recovery["prompt_to_user"]
