"""失败必须走到调用方（v0.47.2-dev）：搜索时区、灵棋日干、六壬本命盘、report_from_tool 的真错误码。

这四处都是 `ok=True`（或换了一个无关错误码）而调用方看不到原因。`_electionscan_zone` 最重：`zone="New York"` 回落 +08:00，纽约的窗口
按东八区搜出来，`input_normalized.zone` 还写着 New York。"""
from __future__ import annotations

from pathlib import Path

import pytest
from fakes import CaptureClient, FakeClient, FakeJsClient

from horosa_skill.config import Settings
from horosa_skill.errors import ToolTransportError, ToolValidationError
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.service.options_zeri import _electionscan_zone

BIRTH = {"date": "2026-03-15", "time": "10:30:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gender": 1}
CONFIRMED = {**BIRTH, "defaults_accepted": True}
WINDOW = {
    "startDate": "2026-03-15", "endDate": "2026-03-16",
    "conditions": {"kind": "group", "joiner": "all", "children": [{"type": "moon_void", "params": {}}]},
}


class _Failing(FakeClient):
    def __init__(self, *endpoints: str) -> None:
        super().__init__()
        self.failing = set(endpoints)

    def call(self, endpoint: str, payload: dict) -> dict:
        if endpoint in self.failing:
            raise ToolTransportError("backend 500", code="transport.http_error", details={"endpoint": endpoint})
        return super().call(endpoint, payload)


def _service(tmp_path: Path, client: FakeClient | None = None) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
                        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    chosen = client or FakeClient()
    return HorosaSkillService(settings, client=chosen, chart_client=chosen, js_client=FakeJsClient(), store=MemoryStore(settings))


@pytest.mark.parametrize("zone", ["New York", "Beijing", "east8", "abc:def", "nan", "inf"])
def test_an_unparsable_zone_is_refused_not_read_as_beijing(zone: str) -> None:
    with pytest.raises(ToolValidationError) as excinfo:
        _electionscan_zone(zone)
    assert excinfo.value.code == "tool.invalid_zone"
    assert excinfo.value.details["zone"] == zone


@pytest.mark.parametrize(
    ("zone", "expected"),
    [("+08:00", "+08:00"), ("-05:00", "-05:00"), ("+05:30", "+05:30"), (8, "+08:00"), (-5, "-05:00"), (5.5, "+05:30"), ("9", "+09:00"), (None, "+08:00")],
)
def test_valid_zones_keep_their_exact_wire_form(zone, expected: str) -> None:
    assert _electionscan_zone(zone) == expected


def test_tianxing_refuses_a_city_name_for_zone_before_scanning(tmp_path: Path) -> None:
    client = CaptureClient()
    service = _service(tmp_path, client)
    # v0.50.0：入口的逐字段校验先拒（抛结构化错误，带字段级恢复），比 runner 里的 _electionscan_zone 更早。
    with pytest.raises(ToolValidationError) as caught:
        service.run_tool("tianxing", {**CONFIRMED, **WINDOW, "zone": "New York"}, save_result=False)
    assert caught.value.code == "tool.invalid_zone" and caught.value.details["fields"][0]["field"] == "zone"
    assert not [endpoint for endpoint, _ in client.calls if endpoint == "/electionscan/scan"]


def test_a_valid_zone_scans_at_that_zone(tmp_path: Path) -> None:
    client = CaptureClient()
    service = _service(tmp_path, client)
    envelope = service.run_tool("tianxing", {**CONFIRMED, **WINDOW, "zone": "America/New_York"}, save_result=False)
    assert envelope.ok is True, envelope.error
    assert {payload["zone"] for endpoint, payload in client.calls if endpoint == "/electionscan/scan"} == {"-04:00"}


def test_lingqi_says_when_the_day_stem_could_not_be_fetched(tmp_path: Path) -> None:
    envelope = _service(tmp_path, _Failing("/nongli/time")).run_tool("lingqi", {**CONFIRMED, "question": "x"}, save_result=False)
    assert envelope.ok is True and envelope.data["day_ganzhi"] == ""
    assert any("六戊" in line for line in envelope.warnings), envelope.warnings


def test_lingqi_says_when_the_backend_answers_without_a_day_stem(tmp_path: Path) -> None:
    class _NoStem(FakeClient):
        def call(self, endpoint: str, payload: dict) -> dict:
            return {} if endpoint == "/nongli/time" else super().call(endpoint, payload)

    envelope = _service(tmp_path, _NoStem()).run_tool("lingqi", {**CONFIRMED, "question": "x"}, save_result=False)
    assert envelope.ok is True and any("六戊" in line for line in envelope.warnings), envelope.warnings


def test_lingqi_stays_quiet_when_the_day_stem_arrives(tmp_path: Path) -> None:
    envelope = _service(tmp_path).run_tool("lingqi", {**CONFIRMED, "question": "x"}, save_result=False)
    assert envelope.data["day_ganzhi"] and not any("六戊" in line for line in envelope.warnings), envelope.warnings


def test_liureng_says_when_the_chart_context_is_missing(tmp_path: Path) -> None:
    envelope = _service(tmp_path, _Failing("/chart", "/")).run_tool("liureng_gods", {**CONFIRMED, "question": "x"}, save_result=False)
    assert envelope.ok is True
    assert envelope.data["prerequisites"]["chart_error"]["code"] == "transport.http_error"
    assert any("大六壬" in line and "星盘" in line for line in envelope.warnings), envelope.warnings


def test_liureng_stays_quiet_with_a_healthy_chart(tmp_path: Path) -> None:
    envelope = _service(tmp_path).run_tool("liureng_gods", {**CONFIRMED, "question": "x"}, save_result=False)
    assert envelope.data["prerequisites"]["chart_available"] is True
    assert not any("星盘" in line and "大六壬" in line for line in envelope.warnings), envelope.warnings


@pytest.mark.parametrize("style", ["analysis", "chart"])
def test_report_from_tool_reports_the_real_failure(tmp_path: Path, style: str) -> None:
    service = _service(tmp_path, _Failing("/chart", "/"))
    result = service.report_from_tool(
        {"tool_name": "chart", "payload": CONFIRMED, "format": "json", "style": style, "ai_answer_text": "解读" if style == "analysis" else None}
    )
    assert result["ok"] is False
    assert result["code"] == "transport.http_error", result
    assert result["error"]["code"] == "transport.http_error"
    assert result["details"].get("agent_recovery"), result
