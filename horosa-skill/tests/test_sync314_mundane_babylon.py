"""上游 v3.14.0（Horosa-Public @ e55c3a66）巴比伦「天象实算」段（aiExport v64）。

`[天象实算]` = 七曜所行三道 / 26 颗 ziqpu 星钟 / 目标年取数 / 五星周期现象与出生时可见状态，后端 `/astroextra/babylontables`
（astrostudy/babylon_tables.py）实算，vendored 上游 `buildBabylonSkySection`（utils/babylonAiSnapshot.js）排版，Python 只取数。
preset 位置：「年历预测」之后、「微黄道」之前；缺省开（上游 settingsGroups 的缺省关段只有 数理星历 / 吉日历 / 年历预测）。

期望值的独立来源 = 上游 `astropy/tests/test_babylon_tables.py`：
- 西雅图 1975-02-10 21:15 −08:00：金星 1974-12-29 16:5x 起可见、火星 1974-06-15 21:1x 起不可见、土星上一次现象 = 冲日 1975-01-06、
  火星合日 1974-10-14；
- 1950-01-01 0h UT 47°36′N 122°20′W：刚过中天 α Lac（时角 0.43°）、下一颗 λ And（时角 343.96°）；水星目标年 1904-01-01；
- 公元前 500 年：水星目标年 -0546-03-10；纬度 78°N：五星都不算偕日现象。
三道判据（|赤纬| ≤ 17° 属 Anu 道，距道界 = 到 ±17° 的距离）按定义手算。
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest
from fakes import FakeClient

from horosa_skill.config import Settings
from horosa_skill.errors import ToolTransportError
from horosa_skill.exports.registry import (
    AI_EXPORT_DEFAULT_OFF_SECTIONS,
    AI_EXPORT_OPTIONAL_SECTIONS,
    AI_EXPORT_PRESET_SECTIONS,
)
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.service.endpoints import _PYTHON_CHART_ENDPOINTS

FIX = json.loads((Path(__file__).parent / "fixtures" / "sync314_mundane_live.json").read_text(encoding="utf-8"))["babylontables"]
SEATTLE = {"date": "1975-02-10", "time": "21:15:00", "zone": "-08:00", "lat": "47n36", "lon": "122w20"}
ENDPOINT = "/astroextra/babylontables"


class SkyClient(FakeClient):
    def __init__(self, sky=None) -> None:
        super().__init__()
        self.calls: list[tuple[str, dict]] = []
        self.sky = sky

    def call(self, endpoint: str, payload: dict) -> dict:
        endpoint = "/chart" if endpoint == "/" else endpoint
        self.calls.append((endpoint, copy.deepcopy(payload)))
        if endpoint == ENDPOINT and self.sky is not None:
            return self.sky(payload) if callable(self.sky) else copy.deepcopy(self.sky)
        return super().call(endpoint, payload)

    def requests(self, endpoint: str) -> list[dict]:
        return [p for e, p in self.calls if e == endpoint]


def _service(tmp_path, client) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", runtime_root=tmp_path / "runtime",
                        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    return HorosaSkillService(settings, client=client, store=MemoryStore(settings))  # 真 JS 引擎


def _sky(text: str) -> list[str] | None:
    lines = text.split("\n")
    if "[天象实算]" not in lines:
        return None
    body = []
    for line in lines[lines.index("[天象实算]") + 1:]:
        if not line.strip() or re.fullmatch(r"\[.+\]", line):
            break
        body.append(line)
    return body


def _clean(env) -> None:
    exp = env.data["export_snapshot"]
    assert exp["missing_selected_sections"] == [] and exp["unknown_detected_sections"] == [], exp


# ────────────────────────────── 契约锚点 ──────────────────────────────


def test_sky_section_is_registered_between_almanac_and_micro_zodiac() -> None:
    preset = AI_EXPORT_PRESET_SECTIONS["babylon"]
    assert preset[preset.index("年历预测"): preset.index("微黄道") + 1] == ["年历预测", "天象实算", "微黄道"]  # 上游 presets.js:947
    assert "天象实算" not in AI_EXPORT_DEFAULT_OFF_SECTIONS["babylon"]  # 上游缺省开
    assert "天象实算" not in AI_EXPORT_OPTIONAL_SECTIONS.get("babylon", [])  # 取不到 = 真缺段，要报
    assert ENDPOINT in _PYTHON_CHART_ENDPOINTS


# ────────────────────────────── 真 JS + 脚本化后端 ──────────────────────────────


def test_sky_tables_are_requested_with_the_six_upstream_keys_and_become_a_section(tmp_path) -> None:
    client = SkyClient()
    env = _service(tmp_path, client).run_tool("babylon", {**SEATTLE, "scheme": "systemA", "era": "arsacid"}, save_result=False)
    assert env.ok, env.error
    (req,) = client.requests(ENDPOINT)
    # 上游 fetchBabylonSkyTables（babylonAiSnapshot.js:398-403）：只发盘面的 date / time / zone / lat / lon / ad，没有派系口径。
    assert req == {"date": "1975-02-10", "time": "21:15:00", "zone": "-08:00", "lat": "47n36", "lon": "122w20", "ad": 1}
    body = _sky(env.data["snapshot_text"])
    # 桩回的是夹具里的真实响应；真 builder 的正文与抓夹具时逐字相同。
    assert body == FIX["seattle_1975"]["section"]
    paths, ziqpu, goal, phenomena = body
    # 三道按定义手算：火星赤纬 −23.2635° 在 −17° 以南 → Ea 道，距道界 23.2635 − 17 = 6.26°；土星 +22.5065° → Enlil 道 5.51°；
    # 太阳 −14.2253° 在 ±17° 内 → Anu 道，距道界 17 − 14.2253 = 2.77°。度分写法 −23°16′（0.2635 × 60 = 15.8 → 16）。
    assert "火 −23°16′ Ea 道(南) 距道界 6.26°" in paths and "土 +22°30′ Enlil 道(北) 距道界 5.51°" in paths
    assert paths.startswith("七曜所行之道(赤纬 ±17° 内为 Anu 道):日 −14°14′ Anu 道(中) 距道界 2.77°;")
    assert ziqpu.startswith("ziqpu 星钟:最近过中天 ") and "下一颗 " in ziqpu
    # 目标年：月亮 223 个朔望月，其余各自周期年数（水 46、金 8、火 79 / 47、木 71 / 83、土 59）——同一民用日期往前推。
    assert [m for m in re.findall(r"(月 −223 月|[水金火木土] −\d+ 年)\((\d{4}-\d\d-\d\d)\)", goal)][1:] == [
        ("水 −46 年", "1929-02-10"), ("金 −8 年", "1967-02-10"), ("火 −79 年", "1896-02-10"), ("火 −47 年", "1928-02-10"),
        ("木 −71 年", "1904-02-10"), ("木 −83 年", "1892-02-10"), ("土 −59 年", "1916-02-10")]
    # 周期现象：上游 test_phenomena_visibility_at_birth / test_phenomena_conjunctions_stations_oppositions 的固定样本。
    assert "金 出生时可见(自 1974-12-29 16:5" in phenomena
    assert "火 出生时不可见(自 1974-06-15 21:1" in phenomena and "前 合日(不可见) 1974-10-14" in phenomena
    assert "土 出生时可见(" in phenomena and "前 冲日 1975-01-06" in phenomena
    assert "木 出生时可见(" in phenomena
    # 原始数据随结果回（报告 / 追问用），段序在三页签候选段之后。
    assert env.data["sky_tables"]["paths"][0]["id"] == "Sun"
    text = env.data["snapshot_text"]
    assert text.index("[年历预测]") < text.index("[天象实算]")
    assert not env.warnings, env.warnings
    _clean(env)


def test_missing_or_failed_sky_tables_drop_only_that_section_and_say_so(tmp_path) -> None:
    def refuse(_payload):
        raise ToolTransportError("后端拒绝了本次请求参数（backend_param_error）。", code="tool.backend_param_error", details={"err": "param error"})

    for name, sky, needle in (
        ("refused", refuse, "取数失败"),
        ("no_paths", {"ziqpu": None}, "没有回七曜三道"),
    ):
        env = _service(tmp_path, SkyClient(sky)).run_tool("babylon", dict(SEATTLE), save_result=False)
        assert env.ok, (name, env.error)
        assert _sky(env.data["snapshot_text"]) is None, name
        assert env.data["sky_tables"] is None
        assert [w for w in env.warnings if "[天象实算]" in w and needle in w], (name, env.warnings)
        assert "[七曜按宫]" in env.data["snapshot_text"]  # 其余段照常
        # 缺省开的段没出 = 真缺段：导出层照报 missing（不登记成可选段把它藏起来）。
        assert env.data["export_snapshot"]["missing_selected_sections"] == ["天象实算"], name


def test_a_failed_block_inside_the_sky_tables_is_named(tmp_path) -> None:
    # 后端四块各自 try / except，失败的那块回 None（babylon_tables.build_babylon_tables）。
    partial = {**copy.deepcopy(FIX["seattle_1975"]["response"]), "ziqpu": None, "phenomena": None}
    env = _service(tmp_path, SkyClient(partial)).run_tool("babylon", dict(SEATTLE), save_result=False)
    assert env.ok, env.error
    body = _sky(env.data["snapshot_text"])
    assert len(body) == 2 and body[0].startswith("七曜所行之道") and body[1].startswith("目标年取数:")
    (note,) = [w for w in env.warnings if "[天象实算]" in w]
    assert "ziqpu 星钟" in note and "周期现象" in note and "目标年取数" not in note
    _clean(env)


# ────────────────────────────── live（vendored v3.14.0 实例） ──────────────────────────────

from test_local_js_tools import make_service, requires_chart, requires_current_runtime_contract  # noqa: E402


def _live_sky(tmp_path, payload: dict) -> list[str]:
    env = make_service(tmp_path).run_tool("babylon", payload, save_result=False)
    assert env.ok, env.error
    assert not env.warnings, env.warnings
    _clean(env)
    body = _sky(env.data["snapshot_text"])
    assert body and len(body) == 4, body
    return body


@requires_chart
@requires_current_runtime_contract
def test_live_seattle_sky_section_matches_the_upstream_backend_samples(tmp_path) -> None:
    paths, ziqpu, goal, phenomena = _live_sky(tmp_path, SEATTLE)
    assert len(paths.split(";")) == 7 and "火 −23°16′ Ea 道(南) 距道界 6.26°" in paths
    assert "金 出生时可见(自 1974-12-29 16:5" in phenomena
    assert "火 出生时不可见(自 1974-06-15 21:1" in phenomena and "前 合日(不可见) 1974-10-14" in phenomena
    assert "前 冲日 1975-01-06" in phenomena
    assert "水 −46 年(1929-02-10)" in goal and "月 −223 月(1957-01-30)" in goal  # 1975-02-10 − 6585.32 日 = 1957-01-30


@requires_chart
@requires_current_runtime_contract
def test_live_ziqpu_clock_matches_the_reference_hour_angles(tmp_path) -> None:
    """上游 REFERENCE_HA（1950-01-01 0h UT，47°36′N 122°20′W）：α Lac 时角 0.43°（刚过中天）、λ And 343.96°（下一颗）。
    0.43° → 0 UŠ、0.43 × 4 = 1.7 分 → 「0h02m」；360 − 343.96 = 16.04° → 16 UŠ、64.2 分 → 「1h04m」。"""
    _paths, ziqpu, goal, _ph = _live_sky(tmp_path, {"date": "1950-01-01", "time": "00:00:00", "zone": "+00:00", "lat": "47n36", "lon": "122w20"})
    assert ziqpu.startswith("ziqpu 星钟:最近过中天 膝(α Lac)已过 0 bēru 0 UŠ(0h02m);下一颗 踵(λ And)还有 0 bēru 16 UŠ(1h04m),约 1950-01-01 01:0")
    assert "水 −46 年(1904-01-01)" in goal  # 上游 test_goal_year_rows


@requires_chart
@requires_current_runtime_contract
def test_live_bc_and_polar_births(tmp_path) -> None:
    # 公元前 500 年（天文纪年相减，无公元 0 年）：水星目标年 -0546-03-10（上游 test_goal_year_handles_bc_year_zero_and_leap_days）。
    _p, _z, goal, phenomena = _live_sky(tmp_path, {"date": "-0500-03-10", "time": "12:00:00", "zone": "+03:00", "lat": "32n33", "lon": "44e25"})
    assert "水 −46 年(-0546-03-10)" in goal
    assert re.findall(r"(?:^|;)([水金火木土]) ", phenomena.split(":", 1)[1]) == list("水金火木土")
    # 纬度超过 65°：五星都不算偕日现象，只列合、冲、留（上游 test_phenomena_bc_and_polar_do_not_break）。
    _p, _z, _g, polar = _live_sky(tmp_path, {**SEATTLE, "lat": "78n00"})
    assert polar.count("高纬不算可见度") == 5 and "始见" not in polar.split(":", 1)[1] and "末见" not in polar.split(":", 1)[1]
