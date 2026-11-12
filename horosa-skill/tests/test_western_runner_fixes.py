"""西占 / 推运 runner 结果正确性（审计 v0.50.0-dev：C-01、C-10、C-11 端到端、调波越界、CN-N5/N6 七政择日）。

C-01：[古典格局] 曾挂在十三分 / 十二分 / 希腊分 / 调波 / 龙盘上——内容是本命盘的分析、逐字节相同（后端 /astroextra/analysis
按常规黄道以本命参数重算）。上游钉版 pipeline.js:513-518 CLASSICAL_SKIP_KEYS 明说这是「本命结论冒充派生盘结论」而跳过。
另：分析请求只带十来个键，用户改的古典口径（界系 / 三分 / 交点 / 容许度体系…）主盘照改、[古典格局] 仍按缺省算。

负向对照（实跑过，见 LESSONS v0.50.0-dev）：
- CLASSICAL_ANALYSIS_TOOLS 加回 chart13 → test_derived_charts_get_no_natal_analysis 与对上游钉版那条红；
- enrich 里去掉 `**classical_backend_overrides_from_fields(payload)` → test_analysis_request_carries_the_chart_classical_calibre 红；
- `_round_hour_to_minute` 换回 `round(分) % 60` → test_planet_cycles_minute_carries_into_the_hour_and_date 红。
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import pytest
from fakes import FakeClient, FakeJsClient
from test_local_js_tools import make_service, requires_runtime

from horosa_skill.civil_calendar import _round_hour_to_minute
from horosa_skill.config import Settings
from horosa_skill.engine.registry import ASTRO_CHART_FAMILY_TOOLS, CLASSICAL_ANALYSIS_TOOLS
from horosa_skill.errors import ToolValidationError
from horosa_skill.exports.contract import TOOL_EXPORT_TECHNIQUE_MAP
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.service.text.predictive import _build_persianchart_section_text

_BIRTH = {"date": "1990-05-17", "time": "14:30:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28",
          "gpsLat": 31.22, "gpsLon": 121.47, "defaults_accepted": True}
_DERIVED = {"chart13": {}, "chart12": {}, "hellen_chart": {}, "harmonic": {"harmonic": 7}, "draconic": {}}


class _Recording(FakeClient):
    def __init__(self, overrides: dict[str, Any] | None = None) -> None:
        super().__init__()
        self.calls: list[tuple[str, dict]] = []
        self.overrides = overrides or {}

    def call(self, endpoint: str, payload: dict) -> dict:
        self.calls.append((endpoint, dict(payload)))
        if endpoint in self.overrides:
            return self.overrides[endpoint]
        return super().call(endpoint, payload)

    def sent(self, endpoint: str) -> list[dict]:
        return [body for e, body in self.calls if e == endpoint]


class _RecordingJs(FakeJsClient):
    def __init__(self) -> None:
        super().__init__()
        self.runs: list[tuple[str, dict]] = []

    def run(self, tool_name: str, payload: dict) -> dict:
        self.runs.append((tool_name, payload))
        return super().run(tool_name, payload)


def _service(tmp_path: Path, client: FakeClient | None = None, js: FakeJsClient | None = None) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", db_path=tmp_path / "m.db", output_dir=tmp_path / "runs")
    return HorosaSkillService(settings, client=client or FakeClient(), store=MemoryStore(settings), js_client=js or FakeJsClient())


def _section(text: str, title: str) -> str | None:
    match = re.search(r"^\[" + re.escape(title) + r"\]\n(.*?)(?=\n\[[^\]\n]+\]\n|\Z)", text, re.S | re.M)
    return match.group(1).strip() if match else None


def _text(result: Any) -> str:
    return result.data["export_snapshot"]["export_text"]


# ───────────────────────── C-01：[古典格局] 只挂上游会挂的盘 ─────────────────────────

@pytest.mark.parametrize("tool", sorted(_DERIVED))
def test_derived_charts_get_no_natal_analysis(tmp_path: Path, tool: str) -> None:
    client = _Recording()
    result = _service(tmp_path, client).run_tool(tool, {**_BIRTH, **_DERIVED[tool]}, save_result=False)
    assert result.ok, result.error
    assert client.sent("/astroextra/analysis") == [], f"{tool} 不该再拉本命口径的派生分析"
    body = _section(_text(result), "古典格局")
    # 十三分盘的导出键 astrochart_like 上游 preset 列着该段（为重置盘 / 占星地图）→ 只剩「未返回」护栏句；其余四键段单里已删。
    assert body is None or body.startswith("本次本地计算结果未返回「古典格局」"), (tool, body[:80] if body else body)
    assert _section(_text(result), "埃及历"), f"{tool} 的 [埃及历] 吃本盘，照挂"


@pytest.mark.parametrize("tool", ["chart", "relocation"])
def test_chart_and_relocation_keep_the_analysis(tmp_path: Path, tool: str) -> None:
    client = _Recording()
    payload = {**_BIRTH, **({"relocLat": "40n43", "relocLon": "74w00"} if tool == "relocation" else {})}
    result = _service(tmp_path, client).run_tool(tool, payload, save_result=False)
    assert result.ok, result.error
    (sent,) = client.sent("/astroextra/analysis")
    # 钉版口径：重置盘的分析照本命出生地（上游 chartObj.params = 本命盘；HEAD dacdc905 改按重置地点，re-vendor 时跟进）。
    assert (sent["lat"], sent["lon"]) == ("31n13", "121e28")
    assert _section(_text(result), "古典格局") and not _section(_text(result), "古典格局").startswith("本次本地计算结果未返回")


def test_analysis_request_carries_the_chart_classical_calibre(tmp_path: Path) -> None:
    """上游请求体 `{...chartObj.params}` 带这张盘的非缺省古典口径；skill 曾只带十来个键。别名写法先读成规范值再转发。"""
    client = _Recording()
    payload = {**_BIRTH, "termsVariant": 1, "westNodeType": True, "orbSystem": "whole_sign", "triplicity": "托勒密", "combustOrb": 9}
    result = _service(tmp_path, client).run_tool("chart", payload, save_result=False)
    assert result.ok, result.error
    (sent,) = client.sent("/astroextra/analysis")
    assert {k: sent.get(k) for k in ("termsVariant", "westNodeType", "orbSystem", "triplicity", "combustOrb")} == {
        "termsVariant": 1, "westNodeType": "true", "orbSystem": "wholeSign", "triplicity": "Ptolemaic", "combustOrb": 9.0,
    }
    chart_req = client.calls[0][1]  # 主盘请求（FakeClient 下 chart 工具的端点是 "/"）
    assert chart_req["westNodeType"] == "true" and chart_req["triplicity"] == "Ptolemaic"
    line = next(line for line in _text(result).splitlines() if line.startswith("古典口径"))
    assert "月交点=真交点" in line and "三分集=托勒密二主" in line and "容许度体系=整星座位相" in line and "燃烧上界=9°" in line


_PIN = os.environ.get("HOROSA_SOURCE_ROOT")
_PIPELINE = Path(_PIN) / "Horosa-Web" / "astrostudyui" / "src" / "utils" / "aiExport" / "pipeline.js" if _PIN else None


@pytest.mark.skipif(_PIPELINE is None or not _PIPELINE.is_file(), reason="HOROSA_SOURCE_ROOT (Horosa-Public pin) not set")
def test_analysis_tool_set_mirrors_the_upstream_skip_list() -> None:
    """CLASSICAL_ANALYSIS_TOOLS = 西占盘族里上游不跳过的那些（CLASSICAL_SKIP_KEYS + astrochart_like 的派生名单）。"""
    text = _PIPELINE.read_text(encoding="utf-8")
    keys = re.findall(r"'([^']+)'", re.search(r"const CLASSICAL_SKIP_KEYS = \[(.*?)\];", text).group(1))
    derived = re.findall(r"'([^']+)'", re.search(r"const CLASSICAL_SKIP_DERIVED = \[(.*?)\];", text).group(1))
    assert "十三分" in derived  # chart13 → astrochart_like + 页名「十三分盘」
    display = {"chart13": "十三分盘"}
    expected = set()
    for tool in ASTRO_CHART_FAMILY_TOOLS - {"mundane"}:  # 世运盘不是 astrochart 族（上游只给 astrochart / astro-like 键挂）
        key = TOOL_EXPORT_TECHNIQUE_MAP[tool]
        skipped = key in keys or (key == "astrochart_like" and any(word in display.get(tool, "") for word in derived))
        if not skipped:
            expected.add(tool)
    assert expected == set(CLASSICAL_ANALYSIS_TOOLS)


@requires_runtime
def test_live_derived_charts_and_forwarded_calibre(tmp_path: Path) -> None:
    """真引擎：派生盘不再带本命分析；[古典格局] 随主盘的古典口径变（转发生效）。"""
    service = make_service(tmp_path)
    base = _section(_text(service.run_tool("chart", _BIRTH, save_result=False)), "古典格局")
    assert base and "逐题主星" in base
    for tool, extra in _DERIVED.items():
        body = _section(_text(service.run_tool(tool, {**_BIRTH, **extra}, save_result=False)), "古典格局")
        assert body is None or body.startswith("本次本地计算结果未返回"), tool
    for extra in ({"westNodeType": True}, {"termsVariant": 1}, {"orbSystem": "wholeSign"}):
        moved = _section(_text(service.run_tool("chart", {**_BIRTH, **extra}, save_result=False)), "古典格局")
        assert moved and moved != base, extra
    reloc = service.run_tool("relocation", {**_BIRTH, "relocLat": "40n43", "relocLon": "74w00"}, save_result=False)
    assert _section(_text(reloc), "古典格局") == base  # 钉版：重置盘挂本命出生地的分析


# ───────────────────────── C-10：分钟进位 ─────────────────────────

def test_round_hour_to_minute_carries() -> None:
    assert _round_hour_to_minute(1955, 1, 7, 1.9917) == (1955, 1, 7, 2, 0)
    assert _round_hour_to_minute(2020, 12, 31, 23.9995) == (2021, 1, 1, 0, 0)
    assert _round_hour_to_minute(2024, 2, 28, 23.99999) == (2024, 2, 29, 0, 0)
    assert _round_hour_to_minute(1582, 10, 4, 23.9999) == (1582, 10, 15, 0, 0)  # 民用历改历缺口
    assert _round_hour_to_minute(0, 12, 31, 23.9999) == (1, 1, 1, 0, 0)        # 天文年 0 = 公元前 1 年
    assert _round_hour_to_minute(1968, 12, 11, 14.5) == (1968, 12, 11, 14, 30)


def test_planet_cycles_minute_carries_into_the_hour_and_date(tmp_path: Path) -> None:
    events = [
        {"jd": 0, "year": 1955, "month": 1, "day": 7, "hour": 1.9917, "lon": 116.07, "sign": 3},
        {"jd": 0, "year": 2020, "month": 12, "day": 31, "hour": 23.9995, "lon": 300.49, "sign": 10},
    ]
    client = _Recording({"/astroextra/planetcycles": {"events": events, "startYear": 1950, "endYear": 2030, "p1": "Jupiter",
                                                      "p2": "Uranus", "aspect": 0.0, "center": "geo"}})
    result = _service(tmp_path, client).run_tool("planet_cycles", {"startYear": 1950, "endYear": 2030, "p1": "木星", "p2": "uranus"},
                                                save_result=False)
    assert result.ok, result.error
    body = _section(_text(result), "会合事件")
    assert "1955-01-07 02:00（UT）" in body and "1955-01-07 01:00" not in body
    assert "2021-01-01 00:00（UT）" in body
    (sent,) = client.sent("/astroextra/planetcycles")
    assert (sent["p1"], sent["p2"]) == ("Jupiter", "Uranus")


def test_persian_directed_positions_carry_minutes_into_degrees_and_signs() -> None:
    text = _build_persianchart_section_text({"date": "2025-01-01", "ageYears": 3, "chart": {"objects": [
        {"id": "Sun", "sign": "Virgo", "signlon": 12.9995},
        {"id": "Moon", "sign": "Scorpio", "signlon": 29.9999},
        {"id": "Mars", "sign": "Aries", "signlon": 5.25},
    ]}})
    assert "13°00′" in text and "12°00′" not in text
    assert "射手 0°00′" in text and "30°00′" not in text
    assert "5°15′" in text


# ───────────────────────── C-11 / 调波 / 七政择日：端到端 ─────────────────────────

def test_decennials_settings_reach_the_timeline_and_the_text(tmp_path: Path) -> None:
    result = _service(tmp_path).run_tool(
        "decennials", {**_BIRTH, "orderType": "迦勒底", "calendarType": "365.25", "dayMethod": "Hephaistio"}, save_result=False)
    assert result.ok, result.error
    assert result.data["settings"] == {"startMode": "sect_light", "orderType": "chaldean", "dayMethod": "hephaistio",
                                       "calendarType": "calendar_365_25"}
    body = _section(_text(result), "十年大运设置")
    assert "分配次序：迦勒底星序" in body and "日限体系：Hephaistio（原表日数）" in body and "365.25天/年" in body
    with pytest.raises(ToolValidationError) as info:
        _service(tmp_path).run_tool("decennials", {**_BIRTH, "orderType": "chaldaean"}, save_result=False)
    assert info.value.code == "tool.invalid_option" and info.value.details["field"] == "orderType"


def test_harmonic_out_of_range_is_refused_before_any_request(tmp_path: Path) -> None:
    for bad in (0, -3, 1000, 7.5):
        client = _Recording()
        with pytest.raises(ToolValidationError) as info:
            _service(tmp_path, client).run_tool("harmonic", {**_BIRTH, "harmonic": bad}, save_result=False)
        assert info.value.code == "tool.invalid_option" and info.value.details["field"] == "harmonic", bad
        assert client.calls == []
    client = _Recording()
    assert _service(tmp_path, client).run_tool("harmonic", {**_BIRTH, "harmonic": "H360"}, save_result=False).ok
    assert client.sent("/astroextra/harmonic")[0]["harmonic"] == 360


def test_qizhengelection_kind_plate_and_true_north(tmp_path: Path) -> None:
    client, js = _Recording(), _RecordingJs()
    payload = {**_BIRTH, "action": "eclipses", "kind": "月食", "plate": "天盘", "ziZheng": True}
    assert _service(tmp_path, client, js).run_tool("qizhengelection", payload, save_result=False).ok
    assert client.sent("/qizhengelection/eclipses")[0]["kind"] == "lunar"
    options = next(p for name, p in js.runs if name == "qizhengelection")["options"]
    assert (options["kind"], options["plate"], options["ziZheng"]) == ("lunar", "tian", "true")
    for field, bad in (("plate", "bogus"), ("ziZheng", False), ("kind", "eclipse")):
        with pytest.raises(ToolValidationError) as info:
            _service(tmp_path).run_tool("qizhengelection", {**_BIRTH, "action": "eclipses", field: bad}, save_result=False)
        assert info.value.details["field"] == field
