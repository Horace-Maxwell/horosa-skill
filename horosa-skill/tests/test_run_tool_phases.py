"""`run_tool` 分段之后的不变量。

分段里最容易丢的是 `input_normalized`：它在计算途中会被重新绑定（上游推运缺省、印度流派预设），失败信封与存档读的都是最新值。
把计算段写成「返回新值的函数」，后端一失败新值就丢了；而成功路径的对拍照样全绿，所以这里专门测失败路径。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fakes import FakeClient, FakeJsClient

from horosa_skill.config import Settings
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.errors import ToolTransportError
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService, _degrade
from horosa_skill.testing_payloads import build_sample_payloads

SAMPLES = build_sample_payloads()
REMOTE_TOOLS = sorted(name for name, definition in TOOL_DEFINITIONS.items() if definition.execution != "local")


class _Down(FakeClient):
    def call(self, endpoint: str, payload: dict) -> dict:
        raise ToolTransportError("backend down", code="transport.connection_failed", details={"endpoint": endpoint})


class _Boom(FakeClient):
    def call(self, endpoint: str, payload: dict) -> dict:
        raise KeyError("engine shape changed")


def _service(tmp_path: Path, client: FakeClient | None = None) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
                        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    chosen = client or FakeClient()
    return HorosaSkillService(settings, client=chosen, chart_client=chosen, js_client=FakeJsClient(), store=MemoryStore(settings))


def _sample(tool: str) -> dict:
    return {**SAMPLES[tool], "defaults_accepted": True}


def _without_target(tool: str) -> dict:
    return {key: value for key, value in _sample(tool).items() if key not in {"datetime", "dirLat", "dirLon", "dirZone"}}


# 这些载荷在计算段里真的会改写 input_normalized：缺目标时刻的返照补上游缺省、给了流派的印度盘补岁差 / 宫制。
REBINDING = {
    "solarreturn": (_without_target, "datetime"),
    "lunarreturn": (_without_target, "dirLat"),
    "givenyear": (_without_target, "dirZone"),
    "india_chart": (lambda tool: {**_sample(tool), "indiaSchool": "kp"}, "indiaAyanamsa"),
}


@pytest.mark.parametrize("failing", [_Down, _Boom], ids=["transport", "internal"])
@pytest.mark.parametrize("tool", REMOTE_TOOLS)
def test_a_failed_call_reports_the_same_normalized_input_as_a_healthy_one(tmp_path: Path, tool: str, failing: type[FakeClient]) -> None:
    healthy = _service(tmp_path / "ok").run_tool(tool, _sample(tool), save_result=False)
    failed = _service(tmp_path / "bad", failing()).run_tool(tool, _sample(tool), save_result=False)
    assert failed.ok is False
    assert failed.input_normalized == healthy.input_normalized


@pytest.mark.parametrize("failing", [_Down, _Boom], ids=["transport", "internal"])
@pytest.mark.parametrize("tool", sorted(REBINDING))
def test_a_failed_call_keeps_what_compute_filled_in(tmp_path: Path, tool: str, failing: type[FakeClient]) -> None:
    build, filled_key = REBINDING[tool]
    payload = build(tool)
    assert payload.get(filled_key) is None, "这份载荷本身不能带这个键，否则考不到重新绑定"
    healthy = _service(tmp_path / "ok").run_tool(tool, dict(payload), save_result=False)
    assert healthy.input_normalized[filled_key], "计算段没有补这个键，这条测试失去意义"
    failed = _service(tmp_path / "bad", failing()).run_tool(tool, dict(payload), save_result=False)
    assert failed.ok is False
    assert failed.input_normalized == healthy.input_normalized


def test_the_saved_run_records_what_compute_filled_in(tmp_path: Path) -> None:
    service = _service(tmp_path, _Down())
    payload = _without_target("solarreturn")
    envelope = service.run_tool("solarreturn", dict(payload))
    assert envelope.input_normalized.get("datetime")
    stored = service.store.query_runs(run_id=envelope.memory_ref.run_id, limit=1, include_payload=False)[0]
    subject = stored["subject"]
    assert (json.loads(subject) if isinstance(subject, str) else subject)["datetime"] == envelope.input_normalized["datetime"]


def test_the_two_failure_envelopes_keep_their_summaries(tmp_path: Path) -> None:
    transport = _service(tmp_path / "t", _Down()).run_tool("solarreturn", _sample("solarreturn"), save_result=False)
    internal = _service(tmp_path / "i", _Boom()).run_tool("solarreturn", _sample("solarreturn"), save_result=False)
    assert transport.summary == ["工具 `solarreturn` 调用失败（transport.connection_failed）。"]
    assert internal.summary == ["工具 `solarreturn` 调用时发生内部错误。"]
    assert (transport.code, internal.code) == ("transport.connection_failed", "tool.internal_error")
    assert internal.details == {"exception_type": "KeyError"} == internal.error.details


def test_a_knowledge_failure_keeps_the_chart_and_says_so(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _broken(*_args, **_kwargs):
        raise ValueError("notes folder unreadable")

    monkeypatch.setattr("horosa_skill.service.api.tools.build_user_knowledge_context", _broken)
    envelope = _service(tmp_path).run_tool("chart", {**_sample("chart"), "knowledge": ["x"]}, save_result=False)
    assert envelope.ok is True and envelope.data.get("snapshot_text")
    assert "knowledge_context" not in envelope.data
    assert any("notes folder unreadable" in line for line in envelope.warnings), envelope.warnings


@pytest.mark.parametrize("failure", [ToolTransportError("down", code="transport.connection_failed", details={}), KeyError("shape")],
                         ids=["transport", "internal"])
def test_a_failed_call_keeps_the_notes_it_collected(tmp_path: Path, failure: Exception) -> None:
    service = _service(tmp_path)

    def _degrades_then_fails(*_args, **_kwargs):
        _degrade("first step degraded", note="第一步降级了")
        raise failure

    service._attach_natal_extras = _degrades_then_fails  # type: ignore[method-assign]
    envelope = service.run_tool("chart", _sample("chart"), save_result=False)
    assert envelope.ok is False and "第一步降级了" in envelope.warnings
