"""技法卡逐项设置（深审 F10）：闸门会问的每一项设置都在卡上，带人读的值与来源（用户 / 档案 / 地点 / 缺省）。

结果敏感设置只从一处来——agent_guidance 的指引表（ask_if_missing 带选项的问题 + safe_defaults）。这里的整表守卫用**闸门自己的
解析器**（agent_guidance.questions.answer_groups）独立地列出问题的键，与卡片对照：卡片漏了闸门会问的一项即红。
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fakes import FakeClient, FakeJsClient

from horosa_skill.agent_guidance import TOOL_GUIDANCE
from horosa_skill.agent_guidance.policies import FREE_TEXT_GATE_FIELDS
from horosa_skill.agent_guidance.questions import CONFIRM_ONLY_PARTS, NON_BLOCKING, answer_groups, gender_required
from horosa_skill.config import Settings
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.memory.store import MemoryStore
from horosa_skill.reports.technique_card import (
    CARDLESS_DOMAINS,
    SOURCE_TEXT,
    annotate_setting_sources,
    build_technique_card,
)
from horosa_skill.service import HorosaSkillService
from horosa_skill.testing_payloads import build_sample_payloads

_MOMENT = {"date", "time", "zone", "lat", "lon", "gpsLat", "gpsLon", "place", "location", "datetime"}
CARDED = sorted(name for name, definition in TOOL_DEFINITIONS.items() if definition.domain not in CARDLESS_DOMAINS)


def _gate_setting_keys(tool: str) -> set[str]:
    """闸门会问的设置键：带选项、会拦的问题，用闸门的解析器展开；时刻 / 地点类与纯确认类不算。"""
    keys: set[str] = set()
    for question in (TOOL_GUIDANCE.get(tool) or {}).get("ask_if_missing") or []:
        field = str(question.get("field") or "").strip()
        if not field or field in FREE_TEXT_GATE_FIELDS or (tool, field) in NON_BLOCKING:
            continue
        for group in answer_groups(tool, field) or ():
            keys.update(key.lstrip("@") for key in group)
        # 混着纯确认类部件的问题（如「sihuaSchool/传本」）：answer_groups 整体回 None，具名的那部分照样是设置。
        keys.update(part.strip() for part in field.replace("+", "/").split("/") if part.strip() and part.strip() not in CONFIRM_ONLY_PARTS
                    and " " not in part.strip())
    return {key for key in keys if key not in _MOMENT}


def _defaults(tool: str) -> dict:
    model = TOOL_DEFINITIONS[tool].input_model
    try:
        return model.model_construct().model_dump(exclude_none=True)
    except Exception:  # noqa: BLE001 - 个别模型的缺省工厂要求字段：用空载荷
        return {}


@pytest.mark.parametrize("tool", CARDED)
def test_every_setting_the_gate_can_ask_about_is_on_the_card(tool: str) -> None:
    payload = _defaults(tool)
    card = build_technique_card(tool_name=tool, technique_key=None, input_normalized=payload, response_data={"export_snapshot": {}},
                                skill_version="0", envelope_schema="x", domain=TOOL_DEFINITIONS[tool].domain)
    settings = card["settings"]
    expected = _gate_setting_keys(tool) | {
        key for item in (TOOL_GUIDANCE.get(tool) or {}).get("safe_defaults") or []
        for key in str(item.get("field") or "").split("/") if key and key not in _MOMENT and " " not in key
    }
    if not gender_required(tool, payload):
        expected -= {"gender"} if tool in __import__("horosa_skill.agent_guidance.questions", fromlist=["x"]).GENDER_FACT_TOOLS else set()
    missing = sorted(key for key in expected if key not in settings)
    assert not missing, f"{tool}: 闸门会问 / 有缺省的设置没上卡：{missing}"
    for key, item in settings.items():
        assert str(item.get("text") or "").strip(), f"{tool}.{key}: 没有人读的值"
        assert item.get("source") in SOURCE_TEXT, f"{tool}.{key}: 来源 {item.get('source')!r}"


def _service(tmp_path: Path) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", runtime_root=tmp_path / "rt",
                        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    return HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())


def test_the_three_audit_cases_read_as_words_with_sources(tmp_path: Path) -> None:
    """冷启动客户端看到的三处：六爻性别缺省男却 settings={}；紫微原样 `gender: false`；西占岁差哪里都没写。"""
    service = _service(tmp_path)
    samples = build_sample_payloads()
    sixyao = service.run_tool("sixyao", {**samples["sixyao"], "agent_confirmed_settings": True}, save_result=False)
    item = sixyao.data["technique_card"]["settings"]["gender"]
    assert item["value"] == 1 and "男" in item["text"] and item["source"] == "default"
    assert sixyao.data["technique_card"]["settings"]["liuyaoSettings.askType"]["source"] in ("user", "default")

    ziwei = service.run_tool("ziwei_birth", {**samples["ziwei_birth"], "gender": False, "agent_confirmed_settings": True}, save_result=False)
    item = ziwei.data["technique_card"]["settings"]["gender"]
    assert item["text"] == "女" and item["source"] == "user"

    chart = service.run_tool("chart", {**samples["chart"], "agent_confirmed_settings": True}, save_result=False)
    settings = chart.data["technique_card"]["settings"]
    assert "Lahiri" in settings["siderealAyanamsa"]["text"] and settings["siderealAyanamsa"]["source"] == "default"
    assert settings["hsys"]["text"] and settings["zodiacal"]["text"] == "回归黄道"


def test_profile_filled_settings_say_so(tmp_path: Path) -> None:
    service = _service(tmp_path)
    samples = build_sample_payloads()
    birth = {key: samples["ziwei_birth"][key] for key in ("date", "time", "zone", "lat", "lon")}
    service.profile({"action": "save", "name": "妈妈", "data": {**birth, "gender": 0}})
    result = service.run_tool("ziwei_birth", {"profile": "妈妈", "agent_confirmed_settings": True}, save_result=False)
    item = result.data["technique_card"]["settings"]["gender"]
    assert item["source"] == "profile" and item["text"] == "女"


def test_place_derived_settings_say_so() -> None:
    card = {"settings": {"zone": {"value": "+08:00"}, "hsys": {"value": 1}, "timeAlg": {"value": 0}}}
    annotate_setting_sources(card, explicit_paths=frozenset({"zone", "hsys"}), profile_keys=set(), place_keys={"zone"})
    assert [card["settings"][k]["source"] for k in ("zone", "hsys", "timeAlg")] == ["place", "user", "default"]


def test_gender_is_left_off_when_this_call_does_not_depend_on_it() -> None:
    """神数正传·铁算心易（school=xinyi）是查询层、不分男女：卡上不列性别（与闸门 / 入口同一个判断 gender_required）。"""
    card = build_technique_card(tool_name="zhengchuan", technique_key=None, input_normalized={"school": "xinyi"},
                                response_data={"export_snapshot": {}}, skill_version="0", envelope_schema="x", domain="shenshu")
    assert "gender" not in card["settings"]
    natal = build_technique_card(tool_name="zhengchuan", technique_key=None, input_normalized={"school": "tieban", "gender": 1},
                                 response_data={"export_snapshot": {}}, skill_version="0", envelope_schema="x", domain="shenshu")
    assert natal["settings"]["gender"]["text"] == "男"


def test_reference_lookups_carry_no_technique_card(tmp_path: Path) -> None:
    """知识库 / 导出注册表：没有起任何盘，不挂技法卡（深审 F13：一份注册表回答里 2.9 KB 是它）。"""
    service = _service(tmp_path)
    for tool in ("knowledge_registry", "export_registry"):
        result = service.run_tool(tool, {}, save_result=False)
        assert result.ok and "technique_card" not in result.data, tool
