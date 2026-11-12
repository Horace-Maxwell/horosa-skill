"""择日十技法：入参问题是入参错误，带逐字段恢复——不是「重试 / doctor」（v0.50.0 深审余项）。

症状（复现于共享引擎）：印度择时公元前窗口 → tool.electionscan_failed（后端 invalid_conditions「year -499 is out of range」，
恢复建议「重试一次，仍失败跑 doctor」）；奇门 / 八字 / 太乙 / 六壬择时 → tool.<技法>_scan_failed（同样的重试建议）；黄历择吉 →
tool.huanglizeri_engine_failed「须给起止日期」；紫微 / 三式择时在域外照样出结果（lunar-javascript 域外静默算错）；黄历择吉
多给的 `hour=25`（入口已说「没有哪个设置读它」）却流进展示盘、崩成 tool.huanglizeri_base_chart_failed（transport）。

现在：本地扫描（lunar-javascript）窗口越出公元 1–9999 年 → 扫描前 tool.date_range_unsupported；引擎回报的窗口 / 条件树 /
坐标 / 域外问题 → 对应的逐字段错误（options_zeri.zeri_engine_input_error）；搜索窗三种坏法（读不出 / 倒置 / 太长）也逐字段；
展示盘只吃择日技法自己声明的键，展示盘因入参被拒时原样带出它的输入错误。

负向对照（实跑过）：`_require_sane_window` 去掉 lunar_js 判 → 本地七技法公元前用例红；`_require_electionscan_ok` 不调映射 →
后端映射用例红；`_declared_only` 改成原样返回 → hour 用例红；展示盘分支删掉 → 展示盘入参错误用例红（变成 transport）。
"""
from __future__ import annotations

from typing import Any

import pytest
from fakes import FakeClient, FakeJsClient
from test_local_js_tools import make_service, requires_runtime

from horosa_skill.config import Settings
from horosa_skill.errors import TOOL_CODE_FAMILIES, ToolValidationError, classify_code
from horosa_skill.memory.store import MemoryStore
from horosa_skill.schemas.common import ErrorInfo, ToolEnvelope
from horosa_skill.service import HorosaSkillService
from horosa_skill.service.options_zeri import _require_sane_window, zeri_engine_input_error
from horosa_skill.testing_payloads import build_sample_payloads

S = build_sample_payloads()
LOCAL_ZERI = ["qimenzeri", "huanglizeri", "bazizeri", "taiyizeri", "ziweizeri", "liurengzeri", "sanshizeri"]
WINDOW = {"startDate": "-0500-04-01", "endDate": "-0500-04-08"}


def _service(tmp_path) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    return HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())


def _input_error(error: ToolValidationError, fields: set[str]) -> None:
    assert classify_code(error.code)[0] == "input", error.code
    assert error.details["agent_recovery"]["kind"] == "input"
    assert {item["field"] for item in error.details["fields"]} == fields, error.details["fields"]


@pytest.mark.parametrize("tool", LOCAL_ZERI)
@pytest.mark.parametrize("window", [WINDOW, {"startDate": "10001-02-01", "endDate": "10001-02-08"}])
def test_local_scans_refuse_windows_outside_their_calendar(tmp_path, tool: str, window: dict[str, str]) -> None:
    env = _service(tmp_path).run_tool(tool, {**S[tool], **window}, save_result=False)
    assert env.ok is False and env.error.code == "tool.date_range_unsupported", env.error
    _input_error(env.error, {"startDate", "endDate"})
    assert env.error.details["agent_recovery"]["next_action"] == "tell_user_unsupported"


@pytest.mark.parametrize("start, end, family", [
    ("2028/04/01 10:00", "2028-04-08", "bad_window"), ("2028-04-08", "2028-04-01", "inverted_window"), ("2028-01-01", "2030-01-01", "span_too_large"),
])
def test_window_shape_errors_are_per_field(start: str, end: str, family: str) -> None:
    with pytest.raises(ToolValidationError) as caught:
        _require_sane_window(start, end, max_span=366, tool="huanglizeri")
    assert caught.value.code == f"tool.huanglizeri_{family}"
    _input_error(caught.value, {"startDate", "endDate"})


@pytest.mark.parametrize("engine_code, message, code, fields", [
    ("invalid_conditions", "year -499 is out of range", "tool.date_range_unsupported", {"startDate", "endDate"}),
    ("invalid_conditions", "vara/day_kalam depend on Gregorian sunrise dates; BC era not supported", "tool.date_range_unsupported", {"startDate", "endDate"}),
    ("", "公元 1~9999 年之外(输入 -500 年)的农历/干支需走星历实算路径,本地速算不适用", "tool.date_range_unsupported", {"startDate", "endDate"}),
    ("invalid_range", "end must be after start", "tool.indiazeri_bad_window", {"startDate", "endDate"}),
    ("invalid_date", "日期不存在", "tool.indiazeri_bad_window", {"startDate", "endDate"}),
    ("span_too_large", "span 120d exceeds 93d", "tool.indiazeri_span_too_large", {"startDate", "endDate"}),
    ("invalid_coordinates", "lat out of range", "tool.invalid_coordinate", {"lat", "lon"}),
    ("invalid_conditions", "unknown leaf type 'x'", "tool.indiazeri_invalid_conditions", {"conditions"}),
])
def test_engine_reports_that_are_input_problems(engine_code: str, message: str, code: str, fields: set[str]) -> None:
    error = zeri_engine_input_error("indiazeri", "印度择时", engine_code, message, window=WINDOW)
    assert error is not None and error.code == code
    _input_error(error, fields)


@pytest.mark.parametrize("engine_code", ["scan_failed", "", "timeout", None])
def test_real_engine_failures_stay_retryable(engine_code: Any) -> None:
    assert zeri_engine_input_error("indiazeri", "印度择时", engine_code, "worker crashed", window=WINDOW) is None


def test_backend_scan_envelope_is_mapped(tmp_path) -> None:
    service = _service(tmp_path)
    with pytest.raises(ToolValidationError) as caught:
        service._require_electionscan_ok({"err": "invalid_conditions", "detail": "year -499 is out of range"},
                                         endpoint="/indiaelectionscan/scan", tool="indiazeri", label="印度择时", window=WINDOW)
    assert caught.value.code == "tool.date_range_unsupported"
    assert caught.value.details["scan_error"]["err"] == "invalid_conditions"


def test_display_chart_only_gets_declared_keys(tmp_path, monkeypatch) -> None:
    service = _service(tmp_path)
    seen: list[dict[str, Any]] = []
    original = service.run_tool

    def spy(tool: str, payload: dict[str, Any], **kwargs: Any) -> Any:
        if tool == "huangli":
            seen.append(dict(payload))
        return original(tool, payload, **kwargs)

    monkeypatch.setattr(service, "run_tool", spy)
    env = service.run_tool("huanglizeri", {**S["huanglizeri"], "hour": 25}, save_result=False)
    assert env.ok, env.error
    assert seen and "hour" not in seen[0], seen
    assert any("`hour`" in warning for warning in env.warnings)


def test_display_chart_input_error_is_not_a_transport_error(tmp_path, monkeypatch) -> None:
    service = _service(tmp_path)
    original = service.run_tool

    def failing(tool: str, payload: dict[str, Any], **kwargs: Any) -> Any:
        if tool == "huangli":
            details = {"fields": [{"field": "zone", "code": "tool.invalid_zone"}]}
            return ToolEnvelope(ok=False, tool=tool, version="t", input_normalized={}, error=ErrorInfo(code="tool.invalid_zone", message="bad zone", details=details))
        return original(tool, payload, **kwargs)

    monkeypatch.setattr(service, "run_tool", failing)
    env = service.run_tool("huanglizeri", S["huanglizeri"], save_result=False)
    assert env.ok is False and env.error.code == "tool.invalid_zone", env.error
    assert env.error.details["base_tool"] == "huangli"


def test_no_retry_family_left_for_input_shapes() -> None:
    for family in ("bad_window", "inverted_window", "span_too_large", "invalid_conditions"):
        assert TOOL_CODE_FAMILIES[family]["kind"] == "input"


@requires_runtime
def test_live_india_bc_window_is_an_input_error(tmp_path) -> None:
    env = make_service(tmp_path).run_tool("indiazeri", {**S["indiazeri"], **WINDOW}, save_result=False)
    assert env.ok is False and env.error.code == "tool.date_range_unsupported", env.error
    assert env.error.details["agent_recovery"]["kind"] == "input"
