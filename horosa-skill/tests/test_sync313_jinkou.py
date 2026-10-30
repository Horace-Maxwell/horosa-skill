"""金口诀贵神昼夜按真实地平：上游无头 regenerateJinkouSnapshot（aiAnalysisContext/regenDivination.js:174-188）。

/liureng/gods 回包缺 isDiurnal → ensureLiurengChartObjects 补一份 /chart 取 isDiurnal（取不到才留 null = buildJinKouData
按占时支粗判）；页面 castIsDiurnal（v3.12.0）同为地平口径。skill 此前只认调用方显式 isDiurnal —— 缺省恒粗判，
日出 / 日落前后的课贵人昼夜取反。
"""

from __future__ import annotations

from typing import Any

from fakes import CaptureClient
from test_sync311_sanshi import BASE_LR, RecordingJs, _fake_service


class _DiurnalChartClient(CaptureClient):
    def __init__(self, is_diurnal: Any) -> None:
        super().__init__()
        self.is_diurnal = is_diurnal

    def call(self, endpoint: str, payload: dict) -> dict:
        if endpoint in ("/chart", "/"):   # _call_remote 把 /chart 发成根路径
            self.calls.append(("/chart", dict(payload)))
            return {"chart": {"isDiurnal": self.is_diurnal, "objects": []}}
        return super().call(endpoint, payload)


def _jinkou_js_payload(js: RecordingJs) -> dict[str, Any]:
    return next(p for tool, p in js.runs if tool == "jinkou")


def test_jinkou_takes_day_night_from_the_chart_when_the_caller_gives_none(tmp_path) -> None:
    """负向对照：去掉 runner 里补 /chart 的分支 → JS 收不到 isDiurnal，两条断言红（实跑过）。"""
    for horizon in (False, True):
        client, js = _DiurnalChartClient(horizon), RecordingJs()
        env = _fake_service(tmp_path, client=client, js=js).run_tool(
            "jinkou", {**BASE_LR, "agent_confirmed_settings": True}, save_result=False)
        assert env.ok, env.error
        assert [ep for ep, _ in client.calls].count("/chart") == 1
        assert _jinkou_js_payload(js)["isDiurnal"] is horizon


def test_explicit_is_diurnal_wins_and_skips_the_chart_request(tmp_path) -> None:
    client, js = _DiurnalChartClient(True), RecordingJs()
    env = _fake_service(tmp_path, client=client, js=js).run_tool(
        "jinkou", {**BASE_LR, "agent_confirmed_settings": True, "isDiurnal": False}, save_result=False)
    assert env.ok, env.error
    assert "/chart" not in [ep for ep, _ in client.calls]
    assert _jinkou_js_payload(js)["isDiurnal"] is False


def test_chart_without_day_night_falls_back_to_the_branch_judgement(tmp_path) -> None:
    client, js = _DiurnalChartClient(None), RecordingJs()
    env = _fake_service(tmp_path, client=client, js=js).run_tool(
        "jinkou", {**BASE_LR, "agent_confirmed_settings": True}, save_result=False)
    assert env.ok, env.error
    assert "isDiurnal" not in _jinkou_js_payload(js)
