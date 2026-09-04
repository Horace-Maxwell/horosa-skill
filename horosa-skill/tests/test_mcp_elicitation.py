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
