"""星阙 v3.14.0「节气卯时『按赤经』（结果会变）：改为太阳赤经比东点赤经」—— jieqi_birth 把卯时交出来。

上游 astropy/astrostudy/jieqi/BirthJieQi.py：ascApproachByRA 此前拿 ascmc[4]（东点的**黄经**）与太阳赤经比，两个量不同系，
最多差约 10 分钟；v3.14.0 改比东点赤经 ARMC + 90°（_eastPointValue），连同原有的 +11′ 落在视太阳时约 06:00:44。

skill 侧发现的旧缺陷：jieqi_birth 的 useLocalMao / byLon 两个开关改的正是卯时（BirthJieQi.computeLocal / computeSpring ×
computeTimeZiByLon / ByRA），而 runner 只留节气表、把回包里的 mao / timeOffset 丢了 —— 两个开关给了等于没给，上游这条
「结果会变」在 skill 的输出里也就看不见。现在：数值恒进 data.mao / data.maoBasis；给了任一开关，[起盘信息]
多一行「卯时：HH:mm:ss（哪天 · 求法）」；缺省输出逐字不变。回包的 timeOffset 不带出（上游把儒略日差套了一次日期换算，
不是秒数；见备忘「只报上游」）。

期望值的独立来源（夹具 tests/fixtures/sync314_cn_a_jieqi_birth.json，录自共享 vendored v3.14.0 引擎）：
  把后端给的卯时钟面时刻送回另一条后端链路 /nongli/time（timeAlg=0，realsuntime 均时差）得到真太阳时 ——「出生当日 · 按赤经」
  = 06:00:44，与上游注释写的数逐秒相同；高纬（70°N 夏至）按黄经不收敛 → maoFallback=byRA，真太阳时 06:00:50。

负向对照（实跑过）：
- runner 去掉 `info_lines.append(mao["line"])` → 四条「卯时」行用例红；
- _jieqi_birth_mao 把 `'出生当日' if local` 的判据写反 → 口径标签用例红；
- 去掉 maoFallback 的 _degrade → 高纬回退用例红（warnings 为空）；
- 返回值不并入 mao / maoBasis / maoFallback → 五条用例红。
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fakes import FakeClient
from test_local_js_tools import make_service, requires_chart, requires_runtime
from test_sync311_w3b_gim import _section, _service

FIX = json.loads((Path(__file__).resolve().parent / "fixtures" / "sync314_cn_a_jieqi_birth.json").read_text(encoding="utf-8"))

_BASIS = {
    "default": "当年春分日 · 按赤经",
    "local": "出生当日 · 按赤经",
    "local_bylon": "出生当日 · 按黄经",
    "bylon": "当年春分日 · 按黄经",
}


class _BirthClient(FakeClient):
    def __init__(self, case: str) -> None:
        super().__init__()
        self.case = FIX["cases"][case]
        self.calls: list[tuple[str, dict]] = []

    def call(self, endpoint: str, payload: dict) -> dict:
        self.calls.append((endpoint, copy.deepcopy(payload)))
        if endpoint.rstrip("/").endswith("/jieqi/birth") or endpoint == "/birth":
            for key, value in self.case["extra"].items():
                assert payload.get(key) == value, (key, payload)
            return copy.deepcopy(self.case["response"])
        return super().call(endpoint, payload)


def _run(tmp_path, case: str):
    fix = FIX["cases"][case]
    client = _BirthClient(case)
    payload = {**fix.get("base", FIX["base"]), **fix["extra"], "agent_confirmed_settings": True}
    env = _service(tmp_path, client).run_tool("jieqi_birth", payload, save_result=False)
    return env, client


def test_recorded_mao_sits_at_apparent_six_oclock_when_solved_by_right_ascension() -> None:
    """夹具前提 = 上游 v3.14.0 的结论：「出生当日 · 按赤经」的卯时换成真太阳时是 06:00:44（东点赤经 = ARMC+90°，太阳时角 −90° 加 11′）；
    「按黄经」是另一套求法（上升点黄经追太阳黄经），不落在 06:00。四种口径的卯时两两不同 —— 两个开关都真改结果。"""
    assert FIX["cases"]["local"]["mao_true_solar"] == "1990-05-17 06:00:44"
    assert FIX["cases"]["highlat_bylon"]["mao_true_solar"] == "1990-06-21 06:00:50"
    assert FIX["cases"]["local_bylon"]["mao_true_solar"] != FIX["cases"]["local"]["mao_true_solar"]
    maos = [FIX["cases"][name]["response"]["mao"] for name in _BASIS]
    assert len(set(maos)) == 4, maos


@pytest.mark.parametrize("case", ["local", "local_bylon", "bylon"])
def test_jieqi_birth_states_the_mao_when_either_switch_is_given(tmp_path, case: str) -> None:
    """给了 useLocalMao / byLon：[起盘信息] 末行「卯时：<后端钟面时刻>（哪天 · 求法）」，data 带 mao / maoBasis，
    请求体把两键原样带给 /jieqi/birth。负向：去掉 info_lines.append(mao["line"]) → 行缺席。"""
    env, client = _run(tmp_path, case)
    assert env.ok, env.error
    response = FIX["cases"][case]["response"]
    info = _section(env.data["snapshot_text"], "起盘信息").split("\n")
    assert info[-1] == f"卯时：{response['mao']}（{_BASIS[case]}）"
    assert env.data["mao"] == response["mao"]
    assert env.data["maoBasis"] == _BASIS[case] and "maoFallback" not in env.data and "timeOffset" not in env.data
    assert list(env.warnings or []) == []
    exp = env.data["export_snapshot"]
    assert exp["missing_selected_sections"] == [] and exp["unknown_detected_sections"] == []
    # 卯时相对 05:00 的儒略日差（回包 timeOffsetJDN，Java 四柱「春分定卯时」读它）= 05:00 − 卯时，独立核一遍（±1 秒）
    mao = datetime.strptime(response["mao"], "%H:%M:%S")
    delta = timedelta(hours=5) - timedelta(hours=mao.hour, minutes=mao.minute, seconds=mao.second)
    assert abs(response["timeOffsetJDN"] * 86400 - delta.total_seconds()) <= 1, (response["timeOffsetJDN"], delta)


def test_jieqi_birth_default_output_is_unchanged_but_data_carries_the_mao(tmp_path) -> None:
    """两个开关都没给：快照不多一行（缺省输出逐字不变），数值仍在 data 里。"""
    env, _ = _run(tmp_path, "default")
    assert env.ok, env.error
    assert "卯时" not in env.data["snapshot_text"]
    assert env.data["mao"] == FIX["cases"]["default"]["response"]["mao"] and env.data["maoBasis"] == _BASIS["default"]


def test_jieqi_birth_reports_the_high_latitude_fallback(tmp_path) -> None:
    """70°N 夏至日按黄经求上升不收敛，后端退到按赤经并回 maoFallback=byRA：行里写明、进 warnings、data.maoFallback 带出。
    负向：去掉 _degrade → warnings 为空。"""
    env, _ = _run(tmp_path, "highlat_bylon")
    assert env.ok, env.error
    response = FIX["cases"]["highlat_bylon"]["response"]
    assert response["maoFallback"] == "byRA"
    info = _section(env.data["snapshot_text"], "起盘信息").split("\n")
    assert info[-1] == f"卯时：{response['mao']}（出生当日 · 按黄经；按黄经求上升不收敛（高纬），已退到按赤经）"
    assert env.data["maoFallback"] == "byRA"
    assert any("按黄经求上升不收敛" in note for note in env.warnings)


@requires_runtime
@requires_chart
def test_live_mao_by_right_ascension_is_apparent_six_oclock(tmp_path) -> None:
    """live：jieqi_birth(useLocalMao=1) 的卯时钟面时刻，经 nongli_time（真太阳时，另一条后端链路）折回去是 06:00:44 ± 2 秒；
    四种口径两两不同。"""
    service = make_service(tmp_path)
    base = {**FIX["base"], "agent_confirmed_settings": True}
    seen = {}
    for name, extra in (("default", {}), ("local", {"useLocalMao": 1}), ("local_bylon", {"useLocalMao": 1, "byLon": 1}), ("bylon", {"byLon": 1})):
        env = service.run_tool("jieqi_birth", {**base, **extra}, save_result=False)
        assert env.ok, (name, env.error)
        seen[name] = env.data["mao"]
        assert env.data["maoBasis"] == _BASIS[name]
        assert ("卯时：" in env.data["snapshot_text"]) is bool(extra), name
    assert len(set(seen.values())) == 4, seen
    solar = service._call_remote("/nongli/time", {"date": base["date"], "time": seen["local"], "zone": base["zone"],
                                                  "lat": base["lat"], "lon": base["lon"], "ad": 1, "timeAlg": 0})
    got = datetime.strptime(solar["birth"], "%Y-%m-%d %H:%M:%S")
    assert abs((got - datetime(1990, 5, 17, 6, 0, 44)).total_seconds()) <= 2, solar["birth"]
