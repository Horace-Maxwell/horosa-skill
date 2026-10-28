"""v0.36.0 A2 — the MCP elicitation gate had zero tests and swallowed every exception into `None`.

`_maybe_elicit_gate` is driven here with a fake FastMCP context; every exit must leave
`details.elicitation.status` behind so an agent can tell "the client cannot elicit" from
"the form failed" from "the user cancelled".
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from horosa_skill.surfaces.mcp_elicitation import _ELICIT_CANCEL, _ELICIT_DEFAULTS, _ELICIT_PROVIDE, _apply_gate_decision, _gate_elicitation_schema
from horosa_skill.surfaces.mcp_server import _maybe_elicit_gate


class _Session:
    """客户端能力：supports=True 时声明 elicitation（form）。"""

    def __init__(self, supports: bool) -> None:
        self.supports = supports


class _Ctx:
    """mcp 2.x 的 Context 替身：协议版本缺省是握手时代（老路：服务端发起 elicitation）。"""

    def __init__(self, session: _Session, result=None, error: Exception | None = None,  # noqa: ANN001
                 protocol: str = "2025-11-25", input_responses=None, request_state=None) -> None:  # noqa: ANN001
        self.session = session
        self._result = result
        self._error = error
        self.prompts: list[str] = []
        self._request_context = object()
        self.protocol_version = protocol
        self.input_responses = input_responses
        self.request_state = request_state

    @property
    def client_capabilities(self):  # noqa: ANN201
        if not self.session.supports:
            return SimpleNamespace(elicitation=None)
        return SimpleNamespace(elicitation=SimpleNamespace(form=SimpleNamespace(), url=None))

    async def elicit(self, message: str, schema):  # noqa: ANN001
        self.prompts.append(message)
        if self._error is not None:
            raise self._error
        assert "decision" in schema.model_fields and "notes" in schema.model_fields
        return self._result


class _Mcp:
    def __init__(self, ctx: _Ctx) -> None:
        self._ctx = ctx


def _gate_error() -> dict:
    return {
        "ok": False,
        "code": "tool.clarification_required",
        "details": {"agent_recovery": {"prompt_to_user": "请确认宫制"}},
    }


def _run(mcp: _Mcp, payload: dict | None = None, error: dict | None = None):  # noqa: ANN201
    """像 HorosaMCPServer.call_tool 那样把请求上下文放进 ContextVar 再调闸门。"""
    from horosa_skill.surfaces.mcp_runner import _CURRENT_CONTEXT

    error = error or _gate_error()

    async def call():  # noqa: ANN202
        token = _CURRENT_CONTEXT.set(mcp._ctx)
        try:
            return await _maybe_elicit_gate(mcp, "chart", payload or {"date": "1990-01-01"}, error)
        finally:
            _CURRENT_CONTEXT.reset(token)

    return asyncio.run(call()), error


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
    updated, _ = _run(_Mcp(ctx), {"date": "1990-01-01"}, error)
    assert updated is not None and updated["hsys"] == 3
    assert error["details"]["elicitation"]["status"] == "answered_form"


# ── 2026-07-28：MRTR（input_required 多轮）────────────────────────────────────────


def test_modern_clients_get_input_required_instead_of_a_push() -> None:
    from mcp import types as mcp_types

    ctx = _Ctx(_Session(True), protocol="2026-07-28")
    result, error = _run(_Mcp(ctx))
    assert isinstance(result, mcp_types.InputRequiredResult)
    request = result.input_requests["horosa_gate"]
    assert request.params.message == "请确认宫制" and "decision" in request.params.requested_schema["properties"]
    assert ctx.prompts == []  # 不走服务端发起的 elicitation（2026 会话没有回传通道）
    assert error["details"]["elicitation"] == {"status": "input_required"}


def test_modern_retry_applies_the_answer_only_for_the_same_question() -> None:
    from mcp import types as mcp_types

    first, _ = _run(_Mcp(_Ctx(_Session(True), protocol="2026-07-28")))
    answer = {"horosa_gate": mcp_types.ElicitResult(action="accept", content={"decision": _ELICIT_DEFAULTS, "notes": "按默认"})}
    retry = _Ctx(_Session(True), protocol="2026-07-28", input_responses=answer, request_state=first.request_state)
    updated, error = _run(_Mcp(retry))
    assert updated["defaults_accepted"] is True and "按默认" in updated["clarification_notes"]
    assert error["details"]["elicitation"]["status"] == "defaults"
    # 答案对应的是另一张表（requestState 里的问题摘要对不上）：不采用。
    stale = _Ctx(_Session(True), protocol="2026-07-28", input_responses=answer, request_state='{"q": "other"}')
    updated, error = _run(_Mcp(stale))
    assert updated is None and error["details"]["elicitation"]["status"] == "stale"
    declined = {"horosa_gate": mcp_types.ElicitResult(action="decline")}
    updated, error = _run(_Mcp(_Ctx(_Session(True), protocol="2026-07-28", input_responses=declined,
                                     request_state=first.request_state)))
    assert updated is None and error["details"]["elicitation"]["status"] == "declined"


def _gated_server(tmp_path):  # noqa: ANN001, ANN202
    from horosa_skill.config import Settings
    from horosa_skill.memory.store import MemoryStore
    from horosa_skill.service import HorosaSkillService
    from horosa_skill.surfaces.mcp_server import create_mcp_server

    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
                        db_path=tmp_path / "m.db", output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt")
    return create_mcp_server(HorosaSkillService(settings, store=MemoryStore(settings)), settings)


@pytest.mark.parametrize("mode", ["2026-07-28", "legacy"])
def test_end_to_end_the_client_answers_the_form_and_the_gate_opens(tmp_path, mode) -> None:  # noqa: ANN001
    """真 SDK 客户端（进程内）：2026 走 MRTR（SDK 封装 / 验证 requestState），legacy 走服务端发起的 elicitation。两条路
    答「按星阙默认」后都越过闸门（结果不再是 agent_guidance.required；后端不可达是另一回事）。"""
    import json as _json

    from mcp import types as mcp_types
    from mcp.client import Client

    asked: list[str] = []

    async def answer(context, params):  # noqa: ANN001, ANN202
        asked.append(params.message)
        return mcp_types.ElicitResult(action="accept", content={"decision": _ELICIT_DEFAULTS, "notes": ""})

    async def run():  # noqa: ANN202
        async with Client(_gated_server(tmp_path), mode=mode, elicitation_callback=answer) as client:
            return await client.call_tool("horosa_cn_bazi_birth", {"date": "1990-01-01", "time": "12:00"})

    result = asyncio.run(run())
    body = _json.loads(result.content[0].text)
    assert asked, "客户端没有被问到"
    assert (body.get("error") or {}).get("code") != "agent_guidance.required", body


def test_a_tampered_request_state_is_rejected_by_the_sdk(tmp_path) -> None:  # noqa: ANN001
    from mcp import types as mcp_types
    from mcp.client import Client
    from mcp.shared.exceptions import MCPError

    async def never(context, params):  # noqa: ANN001, ANN202 - 只为声明 elicitation 能力；本测试手动驱动多轮
        raise AssertionError("manual loop")

    async def run():  # noqa: ANN202
        async with Client(_gated_server(tmp_path), mode="2026-07-28", elicitation_callback=never) as client:
            first = await client.session.call_tool("horosa_cn_bazi_birth", {"date": "1990-01-01", "time": "12:00"},
                                                   allow_input_required=True)
            assert isinstance(first, mcp_types.InputRequiredResult)
            answer = {"horosa_gate": mcp_types.ElicitResult(action="accept", content={"decision": _ELICIT_DEFAULTS, "notes": ""})}
            await client.session.call_tool("horosa_cn_bazi_birth", {"date": "1990-01-01", "time": "12:00"},
                                           input_responses=answer, request_state=first.request_state + "x",
                                           allow_input_required=True)

    with pytest.raises(BaseException) as raised:  # noqa: PT011 - 客户端把 MCPError 包在 anyio 的 ExceptionGroup 里
        asyncio.run(run())
    def flat(error: BaseException) -> list[BaseException]:
        nested = getattr(error, "exceptions", None)  # ExceptionGroup（鸭子类型：门禁按旧目标版本查未定义名）
        return [leaf for sub in nested for leaf in flat(sub)] if nested else [error]

    errors = flat(raised.value)
    assert any(isinstance(e, MCPError) and "requestState" in str(e) for e in errors), errors
