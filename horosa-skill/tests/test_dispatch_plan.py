"""dispatch builds each technique's payload from its time role (engine/dispatch_plan.py, v0.50.0-dev).

Before: every selected technique got the same birth payload: qimen / tarot / 黄历 ran on the birth moment, a solar return
had no target year, `preferences` (zodiacal=1) and the user's question never reached the technique, jieqi_year got an
undisclosed "+8" zone and the birth year, an empty gua_desc ran ok, and one invalid child failed the whole dispatch.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fakes import FakeClient, FakeJsClient

from horosa_skill import __version__
from horosa_skill.config import Settings
from horosa_skill.errors import ToolValidationError
from horosa_skill.memory.store import MemoryStore
from horosa_skill.schemas.common import ToolEnvelope
from horosa_skill.service import HorosaSkillService

BIRTH = {"date": "1990-05-03", "time": "08:00:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gender": 0}
NOW = {"date": "2026-11-12", "time": "10:00:00", "zone": "+08:00", "lat": "39n54", "lon": "116e23"}
OK = {"agent_confirmed_settings": True, "save_result": False}


@pytest.fixture()
def service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[HorosaSkillService, list[tuple[str, dict[str, Any]]]]:
    settings = Settings(server_root="http://127.0.0.1:9", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    svc = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_run(tool_name: str, payload: dict[str, Any], **_: Any) -> ToolEnvelope:
        calls.append((tool_name, dict(payload)))
        if payload.get("_boom"):
            raise ToolValidationError("bad", code="tool.invalid_payload", details={"errors": []})
        return ToolEnvelope(ok=True, tool=tool_name, version=__version__, input_normalized=payload, summary=[f"{tool_name} ok"])

    monkeypatch.setattr(svc, "run_tool", fake_run)
    return svc, calls


def test_moment_techniques_never_cast_on_the_birth_moment(service) -> None:
    svc, calls = service
    refused = svc.dispatch({"query": "用奇门看看这笔投资", "birth": BIRTH, **OK})
    assert not refused.ok and refused.code == "agent_guidance.required" and calls == []
    facts = refused.details["missing_facts"]
    assert facts[0]["fact"] == "question_moment" and "context.date" in facts[0]["fields"]
    assert "服务端不拿自己的时钟" in refused.details["agent_recovery"]["prompt_to_user"]

    ran = svc.dispatch({"query": "用奇门看看这笔投资", "birth": BIRTH, "context": NOW, **OK})
    assert ran.ok and calls[-1][0] == "qimen" and calls[-1][1]["date"] == "2026-11-12" and calls[-1][1]["lat"] == "39n54"
    assert ran.time_basis["qimen"]["source"] == "context"


def test_calendar_lookup_takes_today_from_context_and_question_reaches_the_card(service) -> None:
    svc, calls = service
    ran = svc.dispatch({"query": "今天黄历宜忌", "birth": BIRTH, "context": {"date": "2026-11-12"}, **OK})
    assert ran.ok and calls[-1] == ("huangli", {"date": "2026-11-12", "agent_confirmed_settings": True})
    assert ran.time_basis["huangli"]["source"] == "query+context"
    svc.dispatch({"query": "抽张塔罗牌问工作", "context": NOW, **OK})
    assert calls[-1][0] == "tarot" and calls[-1][1]["question"] == "抽张塔罗牌问工作"


def test_target_techniques_take_the_year_from_the_query_or_context(service) -> None:
    svc, calls = service
    svc.dispatch({"query": "solar return chart 2031", "birth": BIRTH, **OK})
    assert calls[-1][1]["datetime"] == "2031-05-03 08:00:00"
    svc.dispatch({"query": "今年太阳返照", "birth": BIRTH, "context": NOW, **OK})
    assert calls[-1][1]["datetime"] == "2026-05-03 08:00:00"
    refused = svc.dispatch({"query": "今年太阳返照", "birth": BIRTH, **OK})
    assert not refused.ok and refused.details["missing_facts"][0]["fact"] == "target_year"


def test_preferences_and_top_level_settings_reach_the_techniques_that_take_them(service) -> None:
    svc, calls = service
    ran = svc.dispatch({"query": "本命盘", "birth": BIRTH, "preferences": {"zodiacal": 1, "nonsense": 3}, "hsys": 0, **OK})
    assert calls[-1][1]["zodiacal"] == 1 and calls[-1][1]["hsys"] == 0
    assert any("nonsense" in warning for warning in ran.warnings)


def test_jieqi_year_needs_a_place_and_never_defaults_to_plus_eight(service) -> None:
    svc, calls = service
    refused = svc.dispatch({"query": "2027年立春是什么时候", "birth": BIRTH, **OK})
    assert not refused.ok and refused.details["missing_facts"][0]["fact"] == "place" and calls == []
    svc.dispatch({"query": "2027年立春是什么时候", "context": {"zone": "+08:00", "lat": "39n54", "lon": "116e23"}, **OK})
    assert calls[-1][1]["year"] == 2027 and calls[-1][1]["zone"] == "+08:00"


def test_empty_gua_lookup_and_missing_second_person_are_refused(service) -> None:
    svc, calls = service
    gua = svc.dispatch({"query": "乾卦是什么意思", **OK})
    assert not gua.ok and gua.details["missing_facts"][0]["fact"] == "gua_name"
    pair = svc.dispatch({"query": "我和他合不合", "birth": BIRTH, **OK})
    assert not pair.ok and pair.details["missing_facts"][0]["fact"] == "second_person"
    assert any("合盘" in warning for warning in pair.warnings), "default technique must be disclosed"
    assert calls == []


def test_one_invalid_child_is_reported_per_technique_while_the_others_run(service) -> None:
    svc, _calls = service
    original = svc.run_tool

    def failing(tool_name: str, payload: dict[str, Any], **kw: Any) -> ToolEnvelope:
        if tool_name == "ziwei_birth":
            raise ToolValidationError("bad", code="tool.invalid_payload", details={"errors": []})
        return original(tool_name, payload, **kw)

    svc.run_tool = failing  # type: ignore[method-assign]
    mixed = svc.dispatch({"query": "八字和紫微一起看", "birth": BIRTH, **OK})
    assert not mixed.ok and mixed.results["bazi_birth"].ok and not mixed.results["ziwei_birth"].ok
    assert mixed.results["ziwei_birth"].error.code == "tool.invalid_payload"


def test_validation_errors_name_each_field_once_without_internal_model_names(service) -> None:
    svc, _ = service
    with pytest.raises(ToolValidationError) as caught:
        svc.dispatch({"query": "本命盘", "birth": {"date": "1990-05-03", "zone": "+08:00", "lat": "31n13", "lon": "121e28"}, **OK})
    errors = caught.value.details["errors"]
    locs = [tuple(error["loc"]) for error in errors]
    assert ("birth", "time") in locs and len(locs) == len(set(locs))
    assert not any("Input" in str(part) for loc in locs for part in loc)
