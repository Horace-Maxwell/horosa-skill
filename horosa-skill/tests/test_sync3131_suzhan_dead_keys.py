"""宿占死键整表（星阙 v3.13.1 @06f25f21，utils/techniqueMountSettings.js:1722-1726 SUZHAN_DEAD_CLASSICAL_KEYS）。

上游宿占挂载齿轮从共享 ASTRO_CHART_FIELDS 里滤掉这 41 个西占古典判读键（尊贵 / 界主 / 福点 / 相位 / 燃烧 / 返照 / 推算行星 /
容许度 …，含 v3.13.1 sunriseMode），宿占 recordPayloadKeys（:1774）也不带它们：宿占快照只读宫位 / 星曜宿度 / 农历时支
（SuZhanMain.buildSuzhanSnapshotText），这些键对宿占正文零消费。v0.47.0 只把 sunriseMode 挡下；其余 40 个 BirthInput 照收
后**照单下发** /chart（Java 与 chart 服务两档），技法卡也替 sunriseMode 以外的键留着口子。现整表一个常量
（schemas/tools/cn_divination.SUZHAN_DEAD_CLASSICAL_KEYS）：照收（老调用方传了不报错，同上游「隐去」不出警告）、不下发、卡片不回显。

负向对照（实跑过）：
- 常量里删掉 "orbScale" → 逐值看守 / 照收 / 卡片三条红；
- runners/guolao._run_suzhan_tool 的 `k not in dead` 改回 `k != "sunriseMode"` → 下发断言红（40 键漏发）；
- technique_card._FIELD_DEAD_FOR_TOOLS 改回只收 sunriseMode → 卡片断言红（卡片用例把整表塞进结果敏感表，
  证明挡住它们的是死键表、不是「敏感表本来没收」）。
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import pytest
from test_local_js_tools import make_service, requires_runtime

from horosa_skill.schemas.tools.cn_divination import (
    SUZHAN_DEAD_CLASSICAL_KEYS,
    SuZhanInput,
)

_ROOT = os.environ.get("HOROSA_SOURCE_ROOT")
_TMS = Path(_ROOT) / "Horosa-Web" / "astrostudyui" / "src" / "utils" / "techniqueMountSettings.js" if _ROOT else None
requires_upstream = pytest.mark.skipif(
    _TMS is None or not _TMS.is_file(), reason="HOROSA_SOURCE_ROOT (Horosa-Public checkout) not set"
)

_BASE = {"date": "1998-02-20", "time": "20:48:00", "zone": "+08:00", "lat": "39n54", "lon": "116e23"}
# 每个死键一个非缺省、能过 BirthInput 校验的值（取值按各字段 description 的可选档）。
_NON_DEFAULT: dict[str, Any] = {
    "termsVariant": 1, "sectBuffer": 3, "leoBoundFirst": 1, "triplicity": "ptolemy", "lotReversal": 0, "lotsDocReverse": 1,
    "nodeExaltation": 1, "geminiBoundEmended": 1, "cazimiOrb": 0.5, "combustOrb": 9, "underBeamsOrb": 16, "vocMode": 2,
    "vocIncludeOuter": 1, "fixedStarOrbMode": 1, "fixedStarOrb": 2, "antisciaOrb": 2, "viaCombustaVariant": 1,
    "combustOwnChariotExempt": 1, "stationMarking": "exactWindow", "hermeticLotsReversal": 0, "erosConstruction": "valens",
    "lotFortuneVariant": "moonAboveNight", "lotFatherCombustAlt": 1, "lotProjection": "sign", "dignityDebilities": 0,
    "almutenTripMode": "sectRulerOnly", "planetaryHourMethod": "unequal", "sunriseMode": "apparent", "orbSystem": "byAspect",
    "luminaryOrbBonus": 10, "aspectIncludeCusps": 1, "aspectIncludeLots": 1, "aspectIncludeMidpoints": 1,
    "solarReturnVariant": "hellenistic", "returnLatitudeMode": "withLatitude", "vulcanCalc": "weston", "strongRecption": True,
    "simpleAsp": True, "virtualPointReceiveAsp": True, "orbScale": 1.5, "useStoredOrbs": 1,
}


@requires_upstream
def test_dead_key_list_matches_upstream_value_for_value() -> None:
    text = _TMS.read_text(encoding="utf-8")
    block = re.search(r"const SUZHAN_DEAD_CLASSICAL_KEYS = \[(.*?)\];", text, re.DOTALL)
    assert block is not None
    upstream = re.findall(r"'([^']+)'", block.group(1))
    assert len(upstream) == 41
    assert list(SUZHAN_DEAD_CLASSICAL_KEYS) == upstream
    # 上游宿占 recordPayloadKeys 与齿轮过滤都引用这张表（结构没变才谈得上「同上游隐去」）。
    assert "SUZHAN_DEAD_CLASSICAL_KEYS.indexOf(f.name) < 0" in text
    assert "suzhan: { kind: 'record', recordPayloadKeys: ['houseStartMode', 'doubingSu28', 'zodiacal', 'hsys', 'siderealAyanamsa']" in text


def test_every_dead_key_is_accepted_by_the_schema() -> None:
    """照收：BirthInput 共享键，老调用方传了不该被拒（上游 UI 只是隐去）。"""
    assert set(_NON_DEFAULT) == set(SUZHAN_DEAD_CLASSICAL_KEYS)
    dumped = SuZhanInput.model_validate({**_BASE, **_NON_DEFAULT}).model_dump(exclude_none=True)
    assert {k: dumped.get(k) for k in _NON_DEFAULT} == _NON_DEFAULT


class _StopAtChart(Exception):
    pass


def test_no_dead_key_reaches_the_backend(tmp_path: Path) -> None:
    """八字公式起盘（Java /chart）与 ASC 起盘（chart 服务）两档都不带任何死键；宿占自己的键照发。"""
    from horosa_skill.config import Settings
    from horosa_skill.memory.store import MemoryStore
    from horosa_skill.service import HorosaSkillService

    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
                        db_path=tmp_path / "m.db", output_dir=tmp_path / "runs")
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    sent: list[tuple[str | None, dict[str, Any]]] = []

    def call_remote(endpoint: str, payload: dict[str, Any], backend: str | None = None) -> dict[str, Any]:
        sent.append((backend, dict(payload)))
        raise _StopAtChart(endpoint)

    service._call_remote = call_remote  # type: ignore[method-assign]
    for house_start in (0, 1):
        with pytest.raises(_StopAtChart):
            service._run_suzhan_tool({**_BASE, **_NON_DEFAULT, "houseStartMode": house_start, "hsys": 1, "doubingSu28": 4})
    assert [backend for backend, _ in sent] == ["java", None]
    for _, body in sent:
        assert sorted(set(body) & set(SUZHAN_DEAD_CLASSICAL_KEYS)) == []
        assert body["doubingSu28"] == 4 and body["hsys"] == 1 and body["houseStartMode"] in (0, 1)


def test_card_echoes_no_dead_key_for_suzhan(monkeypatch) -> None:
    from horosa_skill.reports import technique_card

    # 把整表塞进结果敏感表：证明挡住它们的是死键表，不是「敏感表本来就没收」。
    extra = tuple((key, key, None) for key in SUZHAN_DEAD_CLASSICAL_KEYS if key != "sunriseMode")
    monkeypatch.setattr(technique_card, "_RESULT_SENSITIVE_FIELDS", technique_card._RESULT_SENSITIVE_FIELDS + extra)
    assert set(technique_card._settings_used(dict(_NON_DEFAULT), {}, "cn", "suzhan")) & set(SUZHAN_DEAD_CLASSICAL_KEYS) == set()
    # 别的工具照常回显（死键表按工具收窄）。
    other = technique_card._settings_used(dict(_NON_DEFAULT), {}, "astro", "chart")
    assert other["sunriseMode"]["value"] == "apparent" and other["orbScale"]["value"] == 1.5


def test_suzhan_tools_list_and_guidance_do_not_advertise_dead_keys() -> None:
    from horosa_skill.agent_guidance import build_agent_guidance
    from horosa_skill.engine.registry import TOOL_DEFINITIONS
    from horosa_skill.surfaces.mcp_schema import advertised_technique_schema

    schema = advertised_technique_schema("suzhan", TOOL_DEFINITIONS["suzhan"].input_model.model_json_schema())
    assert set(schema["properties"]) & set(SUZHAN_DEAD_CLASSICAL_KEYS) == set()
    options_keys = build_agent_guidance(tool_name="suzhan")["tools"]["suzhan"].get("options_keys") or {}
    assert options_keys and set(options_keys) & set(SUZHAN_DEAD_CLASSICAL_KEYS) == set()


# ─────────────────────────────── live（vendored v3.13.1 实例）───────────────────────────────

@requires_runtime
def test_live_dead_keys_leave_the_suzhan_snapshot_byte_identical(tmp_path: Path) -> None:
    """非缺省死键整表 vs 缺省：快照逐字同（八字公式 / ASC 两档）；技法卡设置项也同。
    （改动前用同一组值实测过：照单下发时快照也逐字同 —— 上游「零消费」属实，所以不下发是零回归。）"""
    for house_start in (0, 1):
        service = make_service(tmp_path / f"h{house_start}")
        plain = service.run_tool("suzhan", {**_BASE, "houseStartMode": house_start, "agent_confirmed_settings": True},
                                 save_result=False)
        dead = service.run_tool("suzhan", {**_BASE, **_NON_DEFAULT, "houseStartMode": house_start,
                                           "agent_confirmed_settings": True}, save_result=False)
        assert plain.ok and dead.ok, (plain.error, dead.error)
        assert plain.data["snapshot_text"] and dead.data["snapshot_text"] == plain.data["snapshot_text"]
        assert dead.data["technique_card"]["settings"] == plain.data["technique_card"]["settings"]
