"""v0.36.0 A2 — the MCP elicitation gate had zero tests and swallowed every exception into `None`.

`_maybe_elicit_gate` is driven here with a fake FastMCP context; every exit must leave
`details.elicitation.status` behind so an agent can tell "the client cannot elicit" from
"the form failed" from "the user cancelled".
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from horosa_skill.surfaces.mcp_server import (
    _ELICIT_CANCEL,
    _ELICIT_DEFAULTS,
    _ELICIT_PROVIDE,
    _apply_gate_decision,
    _gate_elicitation_schema,
    _maybe_elicit_gate,
)


class _Session:
    def __init__(self, supports: bool) -> None:
        self.supports = supports

    def check_client_capability(self, _capability) -> bool:  # noqa: ANN001
        return self.supports


class _Ctx:
    def __init__(self, session: _Session, result=None, error: Exception | None = None) -> None:  # noqa: ANN001
        self.session = session
        self._result = result
        self._error = error
        self.prompts: list[str] = []

    async def elicit(self, message: str, schema):  # noqa: ANN001
        self.prompts.append(message)
        if self._error is not None:
            raise self._error
        assert "decision" in schema.model_fields and "notes" in schema.model_fields
        return self._result


class _Mcp:
    def __init__(self, ctx: _Ctx) -> None:
        self._ctx = ctx

    def get_context(self) -> _Ctx:
        return self._ctx


def _gate_error() -> dict:
    return {
        "ok": False,
        "code": "tool.clarification_required",
        "details": {"agent_recovery": {"prompt_to_user": "请确认宫制"}},
    }


def _run(mcp: _Mcp, payload: dict | None = None) -> tuple[dict | None, dict]:
    error = _gate_error()
    updated = asyncio.run(_maybe_elicit_gate(mcp, "chart", payload or {"date": "1990-01-01"}, error))
    return updated, error


@pytest.fixture(autouse=True)
def _elicitation_on(monkeypatch) -> None:
    monkeypatch.delenv("HOROSA_MCP_ELICIT", raising=False)


def test_disabled_flag_is_recorded(monkeypatch) -> None:
    monkeypatch.setenv("HOROSA_MCP_ELICIT", "0")
    updated, error = _run(_Mcp(_Ctx(_Session(True))))
    assert updated is None
    assert error["details"]["elicitation"] == {"status": "disabled"}


def test_unsupported_client_is_recorded() -> None:
    ctx = _Ctx(_Session(False))
    updated, error = _run(_Mcp(ctx))
    assert updated is None
    assert error["details"]["elicitation"] == {"status": "unsupported"}
    assert ctx.prompts == []


def test_accepting_defaults_updates_payload_and_keeps_user_notes() -> None:
    result = SimpleNamespace(action="accept", data=SimpleNamespace(decision=_ELICIT_DEFAULTS, notes="  用整宫 "))
    ctx = _Ctx(_Session(True), result=result)
    updated, error = _run(_Mcp(ctx))
    assert updated is not None
    assert updated["defaults_accepted"] is True
    assert updated["date"] == "1990-01-01"
    assert updated["clarification_notes"].endswith("user notes: 用整宫")
    assert error["details"]["elicitation"] == {"status": "defaults", "decision": _ELICIT_DEFAULTS}
    assert ctx.prompts == ["请确认宫制"]


def test_provide_with_notes_hands_the_words_back_to_the_agent() -> None:
    result = SimpleNamespace(action="accept", data=SimpleNamespace(decision=_ELICIT_PROVIDE, notes="我要 Placidus"))
    updated, error = _run(_Mcp(_Ctx(_Session(True), result=result)))
    assert updated is None
    assert error["details"]["user_notes"] == "我要 Placidus"
    assert error["details"]["agent_recovery"]["user_notes"] == "我要 Placidus"
    assert error["details"]["elicitation"]["status"] == "answered"


def test_cancel_is_recorded() -> None:
    result = SimpleNamespace(action="accept", data=SimpleNamespace(decision=_ELICIT_CANCEL, notes=""))
    updated, error = _run(_Mcp(_Ctx(_Session(True), result=result)))
    assert updated is None
    assert error["details"]["elicitation"] == {"status": "cancelled", "decision": _ELICIT_CANCEL}


def test_declined_form_is_recorded() -> None:
    result = SimpleNamespace(action="decline", data=None)
    updated, error = _run(_Mcp(_Ctx(_Session(True), result=result)))
    assert updated is None
    assert error["details"]["elicitation"] == {"status": "declined", "action": "decline"}


def test_transport_failure_is_recorded_not_swallowed() -> None:
    ctx = _Ctx(_Session(True), error=RuntimeError("socket closed"))
    updated, error = _run(_Mcp(ctx))
    assert updated is None
    assert error["details"]["elicitation"] == {"status": "failed", "error": "RuntimeError: socket closed"}


def test_apply_gate_decision_is_pure() -> None:
    payload = {"date": "x"}
    error: dict = {"details": {}}
    assert _apply_gate_decision(payload, error, _ELICIT_DEFAULTS, "") == {
        "date": "x",
        "defaults_accepted": True,
        "clarification_notes": "user accepted Xingque defaults via MCP elicitation form",
    }
    assert payload == {"date": "x"}
    assert _apply_gate_decision(payload, error, _ELICIT_PROVIDE, "") is None
    assert "user_notes" not in error["details"]


# ---- v0.36.0 B3：表单从闸问题生成，答案只写回策略声明过的值 ----
def _gate_error_with_questions() -> dict:
    return {
        "ok": False,
        "code": "tool.clarification_required",
        "details": {
            "agent_recovery": {"prompt_to_user": "请确认宫制"},
            "ask_if_missing": [
                {"field": "date/time/place", "question": "请提供出生日期时间地点。"},
                {"field": "hsys", "question": "宫制？", "options": ["0 整宫", "3 Placidus"], "values": [0, 3]},
                {"field": "zodiacal", "question": "黄道？", "options": ["回归", "恒星"], "values": [0, 1]},
                {"field": "tradition", "question": "扩展项？", "options": ["需要", "不需要"]},
            ],
        },
    }


def test_form_schema_has_one_enum_field_per_option_question() -> None:
    schema = _gate_elicitation_schema(_gate_error_with_questions())
    fields = schema.model_fields
    assert list(fields) == ["decision", "hsys", "zodiacal", "tradition", "notes"]  # 自由文本题不进表单
    json_schema = schema.model_json_schema()
    assert json_schema["properties"]["hsys"]["enum"] == ["0 整宫", "3 Placidus", ""]
    assert "$ref" not in str(json_schema["properties"]["hsys"])


def test_answers_write_back_only_declared_values_and_confirm() -> None:
    error = _gate_error_with_questions()
    updated = _apply_gate_decision(
        {"date": "1990-01-01"}, error, _ELICIT_PROVIDE, "", answers={"hsys": "3 Placidus", "zodiacal": "", "tradition": "需要", "bogus": "x"}
    )
    assert updated is not None
    assert updated["hsys"] == 3 and "zodiacal" not in updated and "tradition" not in updated  # tradition 无 values → 只记不写
    assert updated["agent_confirmed_settings"] is True
    assert "hsys=3 Placidus" in updated["clarification_notes"] and "tradition=需要" in updated["clarification_notes"]


def test_answer_outside_declared_options_is_ignored() -> None:
    error = _gate_error_with_questions()
    assert _apply_gate_decision({"date": "x"}, error, _ELICIT_PROVIDE, "", answers={"hsys": "7 Sripati"}) is None


def test_defaults_plus_answers_merge() -> None:
    error = _gate_error_with_questions()
    updated = _apply_gate_decision({"date": "x"}, error, _ELICIT_DEFAULTS, "", answers={"zodiacal": "恒星"})
    assert updated is not None and updated["zodiacal"] == 1 and updated["defaults_accepted"] is True


def test_maybe_elicit_gate_records_form_answers() -> None:
    result = SimpleNamespace(action="accept", data=SimpleNamespace(decision=_ELICIT_PROVIDE, notes="", hsys="3 Placidus", zodiacal="", tradition=""))
    ctx = _Ctx(_Session(True), result=result)
    error = _gate_error_with_questions()
    updated = asyncio.run(_maybe_elicit_gate(_Mcp(ctx), "chart", {"date": "1990-01-01"}, error))
    assert updated is not None and updated["hsys"] == 3
    assert error["details"]["elicitation"]["status"] == "answered_form"
