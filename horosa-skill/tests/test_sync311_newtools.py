"""上游 v3.11 星运四键（ephemeris / returntimeline / prenatalsyzygy / prog）—— 新工具的值级金标与接线守卫。

权威：`fixtures/sync311_newtools_live.json` 的 golden = 上游 builder JS 源码（AstroEphemeris.js / AstroReturnTimeline.js /
AstroPrenatalSyzygy.js / astroProgSnapshot.js / astroAiSnapshot.js / AstroExtraCommon.js，Horosa-Public 9b74714b）
逐字抽出、只替换 request/fetchChart/Date 三个 I/O 口，在**同一份**裁剪后的真实响应（vendored v3.11.1+ chart 服务实抓）
与冻结时钟上跑出的原样文本。Python 移植（engine/astroextra_snapshots.py）必须与之逐字节相等——
两个场景一起覆盖：回归/恒星(raman)黄道、北/南半球东/西经、新月/满月取度、行运表截到 60 行 / 不列行运、
区间与逐日双截断、有/无年龄行、synodic / sidereal 小推运月长。
"""
from __future__ import annotations

import copy
import json
import os
import re
from datetime import datetime
from pathlib import Path

import pytest

from horosa_skill import service as S
from horosa_skill.agent_guidance import validate_agent_preflight
from horosa_skill.config import Settings
from horosa_skill.engine import astroextra_snapshots as A
from horosa_skill.engine.client import HorosaApiClient
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.engine.router import select_tools
from horosa_skill.errors import ToolTransportError
from horosa_skill.exports import registry as R
from horosa_skill.memory.store import MemoryStore
from horosa_skill.schemas.tools import DispatchInput

FIX = json.loads((Path(__file__).parent / "fixtures" / "sync311_newtools_live.json").read_text(encoding="utf-8"))
NOW = datetime.strptime(FIX["golden_now"], "%Y-%m-%dT%H:%M:%S")
SCENARIOS = sorted(FIX["scenarios"])
NOTES = S._PREDICTIVE_METHOD_NOTES
NEW_TOOLS = ("ephemeris", "returntimeline", "prenatalsyzygy", "prog")


def _sc(name: str) -> dict:
    return copy.deepcopy(FIX["scenarios"][name])


# ─────────────────────────── builder 逐字节 = 上游 JS 金标 ───────────────────────────


@pytest.mark.parametrize("name", SCENARIOS)
def test_ephemeris_builder_is_byte_identical_to_upstream(name: str) -> None:
    sc = _sc(name)
    opts = sc["request"]["ephemerisOpts"]
    text = A.build_ephemeris_snapshot_text(
        sc["natal_chart"], sc["ephemeris"], start_date=opts["startDate"], end_date=opts["endDate"],
        include_transits=opts["includeTransits"], now=NOW, method_notes=NOTES["ephemeris"],
    )
    assert text == sc["golden"]["ephemeris"]


@pytest.mark.parametrize("name", SCENARIOS)
def test_returntimeline_builder_is_byte_identical_to_upstream(name: str) -> None:
    sc = _sc(name)
    opts = sc["request"]["returnsOpts"]
    text = A.build_return_timeline_snapshot_text(
        sc["natal_chart"], sc["returns"]["rows"], start_year=opts["startYear"], count=opts["count"], now=NOW,
        method_notes=NOTES["returntimeline"],
    )
    assert text == sc["golden"]["returntimeline"]


@pytest.mark.parametrize("name", SCENARIOS)
def test_prenatalsyzygy_builder_is_byte_identical_to_upstream(name: str) -> None:
    sc = _sc(name)
    for chart, key in ((sc["syzygy_chart"], "prenatalsyzygy"), (None, "prenatalsyzygy_nochart")):
        text = A.build_prenatal_syzygy_snapshot_text(
            sc["natal_chart"], sc["prenatal_syzygy"], chart, now=NOW, method_notes=NOTES["prenatalsyzygy"]
        )
        assert text == sc["golden"][key], key


@pytest.mark.parametrize("name", SCENARIOS)
def test_prog_builder_is_byte_identical_to_upstream(name: str) -> None:
    sc = _sc(name)
    opts = sc["request"]["progOpts"]
    text = A.build_prog_snapshot_text(
        sc["natal_chart"], sc["progressions"], "prog", target_date=opts["targetDate"], target_time=opts["targetTime"],
        minor_variant=opts["minorVariant"], now=NOW, method_notes=NOTES["prog"],
    )
    assert text == sc["golden"]["prog"]


def test_prog_and_vedicprog_variants_differ_only_in_the_variant_literals() -> None:
    """上游 astroProgSnapshot.test.js:65-86 的结构等价判据：两支除 variant 三处文案 + [方法说明] 外逐行相同。"""
    sc = _sc("sample")
    opts = sc["request"]["progOpts"]
    kwargs = dict(target_date=opts["targetDate"], target_time=opts["targetTime"], minor_variant=opts["minorVariant"], now=NOW)
    tropical = A.build_prog_snapshot_text(sc["natal_chart"], sc["progressions"], "prog", method_notes=NOTES["prog"], **kwargs)
    vedic = A.build_prog_snapshot_text(sc["natal_chart"], sc["progressions"], "vedicprog", method_notes=NOTES["vedicprog"], **kwargs)
    V = A.PROG_SNAPSHOT_VARIANTS

    def norm(text: str, key: str) -> list[str]:
        v = V[key]
        out = []
        for line in text.split("\n"):
            if line == f"[{v['section']}]":
                line = "[SECTION]"
            elif line == v["intro"]:
                line = "INTRO"
            elif line == f"| 点 | {v['posCol']} |":
                line = "| 点 | POS |"
            elif line == f"| 点 | {v['posCol']} | 速度 |":
                line = "| 点 | POS | 速度 |"
            if not line.startswith(("二次推运:", "恒星推运：", "读法：")):
                out.append(line)
        return out

    assert norm(tropical, "prog") == norm(vedic, "vedicprog")
    assert "[二次推运（回归黄道）]" in tropical and "| 点 | 推运位置 |" in tropical and "恒星" not in tropical
    assert "[恒星推运（Vedic Sidereal）]" in vedic and "| 点 | 恒星推运位置 |" in vedic
    # 回归支不覆写 zodiacal（随盘自身黄道），恒星支强制 1（astroProgSnapshot.js:34-48）
    assert V["prog"]["zodiacal"] is None and V["vedicprog"]["zodiacal"] == 1


def test_ephemeris_limits_text_matches_upstream() -> None:
    assert [A.ephemeris_limits_text(p) for p in FIX["limits_cases"]] == FIX["limits_golden"]
    # 上游 components/astro/__tests__/ephemerisLimits.test.js 的断言逐条照搬
    t = A.ephemeris_limits_text(FIX["limits_cases"][2])
    assert "区间超过 732 天上限，有效区间 2026-01-01 至 2028-01-02（请求至 2028-06-01）" in t
    assert "每日位置只列前 370 天" in t
    assert "行运触发共 2523 条，按时间先后只列前 600 条" in t
    assert "缩小日期范围可查看全部" in t
    assert A.ephemeris_limits_text(FIX["limits_cases"][3]) == "行运触发共 700 条，按时间先后只列前 600 条（缩小日期范围可查看全部）"


def test_js_number_semantics_are_mirrored_not_approximated() -> None:
    """每条都是 Python 默认行为会**算错**的 JS 语义（改回 Python 原生写法，这里必红）。"""
    # Number.prototype.toFixed：double 精确值的平局取大（0.125 精确可表示）；Python format 是银行家舍入 → '0.12'
    assert A.fmt_num(0.125, 2) == "0.13"
    assert A.fmt_num(2.5, 0) == "3"
    assert A.fmt_num(1.005, 2) == "1.00"  # 1.005 的 double 略小于 1.005 → 两边都是 1.00
    assert A.fmt_num(-0.001, 2) == "-0.00"  # toFixed 对负数保留符号
    assert A.fmt_num(None, 2) == "0.00"  # Number(null) === 0
    assert A.fmt_num(A._UNDEFINED, 2) == "-"  # Number(undefined) → NaN → '-'
    # 后端入座行没有 sign/signlon：fmtDegree 退到 signName(undefined)='-' + Number(lon)%30（上游页面同样显示）
    assert A.fmt_degree({"lon": 89.99999998170112}) == "- 30.00°"
    assert A.fmt_degree({"lon": 270.00000000981737}) == "- 0.00°"
    # AstroTxtMsg 行星是**单字**名、相位用 º(U+00BA) —— 不是 skill 通用 _astro_msg 的「太阳」
    assert A.ASTRO_TXT_MSG["Sun"] == "日" and A.ASTRO_TXT_MSG["Asp90"] == "90º"
    assert A.ASTRO_TXT_MSG["Pars Sons"] == "子女点"  # 上游名实订正（skill 旧表仍是「子嗣点」）


# ─────────────────────────── 经 service 端到端（runner → builder）───────────────────────────


class _LiveFixtureClient(HorosaApiClient):
    """按场景回放真实响应；/chart（chart 服务根 "/"）按日期区分本命盘与朔望时刻盘。记录每次请求体。"""

    _ENDPOINT_KEY = {
        "/astroextra/ephemeris": "ephemeris",
        "/astroextra/returns": "returns",
        "/astroextra/prenatal_syzygy": "prenatal_syzygy",
        "/astroextra/progressions": "progressions",
    }

    def __init__(self, scenario: dict, overrides: dict | None = None) -> None:
        super().__init__("http://fake")
        self.sc = scenario
        self.overrides = overrides or {}
        self.calls: list[tuple[str, dict]] = []

    def probe(self, endpoint: str = "/common/time", payload: dict | None = None) -> bool:
        return True

    def call(self, endpoint: str, payload: dict) -> dict:
        self.calls.append((endpoint, copy.deepcopy(payload)))
        if endpoint in self.overrides:
            value = self.overrides[endpoint]
            if isinstance(value, Exception):
                raise value
            return copy.deepcopy(value)
        if endpoint == "/":
            syz = self.sc["prenatal_syzygy"]
            if payload.get("date") == syz["date"].replace("-", "/") and payload.get("time") == syz["time"]:
                if "syzygy_chart" in self.overrides:
                    raise self.overrides["syzygy_chart"]
                return copy.deepcopy(self.sc["syzygy_chart"])
            return copy.deepcopy(self.sc["natal_chart"])
        return copy.deepcopy(self.sc[self._ENDPOINT_KEY[endpoint]])

    def bodies(self, endpoint: str) -> list[dict]:
        return [payload for ep, payload in self.calls if ep == endpoint]


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):  # noqa: ANN001 - datetime.now 签名
        return NOW if tz is None else datetime.now(tz)


@pytest.fixture()
def frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(S, "datetime", _FrozenDatetime)


def _service(tmp_path: Path, client: HorosaApiClient) -> S.HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9999", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    return S.HorosaSkillService(settings, client=client, store=MemoryStore(settings))


def _payload(sc: dict, **opts) -> dict:
    return {**sc["request"]["natal"], "agent_confirmed_settings": True, **opts}


def _assert_clean(result) -> None:
    assert result.ok is True, result.error
    export = result.data["export_snapshot"]
    assert export["format_source"] == "snapshot_parser"
    assert export["missing_selected_sections"] == []
    assert export["unknown_detected_sections"] == []


def _with_true_station_directions(golden: str, truth: list[dict]) -> str:
    """本仓声明式偏离（v0.40.0，engine/ephemeris_stations.py）施加到上游金标上：「留与顺逆转向」表的方向列换成真值。

    上游 calc_stations 按留点那一刻≈0 的速度正负定方向（浮点噪声：金标 sample 4 个错 2 个、south_sidereal 37 个错 17 个，
    Windows 上错的是另一批）；`station_truth` = 每个留前后各半天的速度变号（fixture 增补，独立于纠正算法）。其余文本逐字不动。
    """
    lines = golden.splitlines(keepends=True)
    start = lines.index("留与顺逆转向：\n") + 3  # 表头 + 分隔行
    for offset, row in enumerate(truth):
        cells = lines[start + offset].split(" | ")
        assert cells[0] == f"| {row['datetime']}", (cells, row)
        cells[2] = row["direction"]
        lines[start + offset] = " | ".join(cells)
    return "".join(lines)


@pytest.mark.parametrize("name", SCENARIOS)
def test_service_runners_reproduce_the_upstream_goldens(tmp_path: Path, frozen: None, name: str) -> None:
    sc = _sc(name)
    req = sc["request"]
    cases = {
        "ephemeris": (req["ephemerisOpts"], "ephemeris"),
        "returntimeline": (req["returnsOpts"], "returntimeline"),
        "prenatalsyzygy": ({}, "prenatalsyzygy"),
        "prog": (req["progOpts"], "prog"),
    }
    for tool, (opts, golden_key) in cases.items():
        client = _LiveFixtureClient(sc)
        result = _service(tmp_path, client).run_tool(tool, _payload(sc, **opts), save_result=False)
        _assert_clean(result)
        expected = sc["golden"][golden_key]
        if tool == "ephemeris":
            expected = _with_true_station_directions(expected, sc["station_truth"])
        assert result.data["snapshot_text"] == expected, tool
        assert result.data["export_snapshot"]["technique"]["key"] == tool
        assert result.data["export_snapshot"]["section_titles_detected"] == R.AI_EXPORT_PRESET_SECTIONS[tool], tool
    eph = _service(tmp_path, _LiveFixtureClient(sc)).run_tool("ephemeris", _payload(sc, **req["ephemerisOpts"]), save_result=False)
    stations = eph.data["ephemeris"]["stations"]
    assert [s["direction"] for s in stations] == [row["direction"] for row in sc["station_truth"]]
    upstream = [s["direction"] for s in sc["ephemeris"]["stations"]]
    assert [s.get("directionUpstream") for s in stations] == [
        up if up != row["direction"] else None for up, row in zip(upstream, sc["station_truth"])
    ], "directionUpstream marks exactly the corrected stations"
    assert not eph.warnings


@pytest.mark.parametrize("name", SCENARIOS)
def test_station_directions_without_the_correction_are_upstream_noise(tmp_path: Path, frozen: None, name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """负向对照：拿掉纠正，输出就是上游金标（噪声标签），与真值版金标对不上——上面那条断言确实咬得住。"""
    sc = _sc(name)
    monkeypatch.setattr(S, "correct_station_directions", lambda stations, daily: (list(stations or []), []))
    result = _service(tmp_path, _LiveFixtureClient(sc)).run_tool("ephemeris", _payload(sc, **sc["request"]["ephemerisOpts"]), save_result=False)
    assert result.data["snapshot_text"] == sc["golden"]["ephemeris"]
    assert result.data["snapshot_text"] != _with_true_station_directions(sc["golden"]["ephemeris"], sc["station_truth"])


def test_station_directions_degrade_visibly_without_daily_speeds(tmp_path: Path, frozen: None) -> None:
    """响应里没有逐日速度（如被代理裁掉）：判不出方向的留沿用上游标签，并在 warnings 里明示，不静默。"""
    sc = _sc("sample")
    eph = copy.deepcopy(sc["ephemeris"])
    eph.pop("dailyPositions")
    client = _LiveFixtureClient(sc, overrides={"/astroextra/ephemeris": eph})
    result = _service(tmp_path, client).run_tool("ephemeris", _payload(sc, **sc["request"]["ephemerisOpts"]), save_result=False)
    assert result.ok is True and result.data["snapshot_text"] == sc["golden"]["ephemeris"]
    assert any("留的顺逆方向无法按逐日速度复核" in w for w in result.warnings), result.warnings


def test_request_bodies_mirror_the_upstream_page_requests(tmp_path: Path, frozen: None) -> None:
    sc = _sc("south_sidereal")
    req = sc["request"]

    client = _LiveFixtureClient(sc)
    _service(tmp_path, client).run_tool("ephemeris", _payload(sc, **req["ephemerisOpts"]), save_result=False)
    (natal_body,) = client.bodies("/")
    assert natal_body["predictive"] == 0 and "startDate" not in natal_body  # 本命盘：选项键不外泄
    (body,) = client.bodies("/astroextra/ephemeris")
    assert (body["startDate"], body["endDate"], body["includeTransits"]) == ("2025-01-01", "2027-06-30", False)
    assert body["eclipseTimeMode"] == "syzygy"  # 非 max 才下发（AstroEphemeris.js:40）
    assert body["tradition"] is False and body["predictive"] is False  # chartParams 恒 false

    client = _LiveFixtureClient(sc)
    _service(tmp_path, client).run_tool("prog", _payload(sc, **req["progOpts"]), save_result=False)
    (body,) = client.bodies("/astroextra/progressions")
    assert body["zodiacal"] == 1, "回归支不覆写 zodiacal：透传盘自身黄道（本盘恒星）"
    assert (body["targetDate"], body["targetTime"], body["minorVariant"], body["orb"]) == ("2026-09-24", "08:05:00", "sidereal", 1.5)

    client = _LiveFixtureClient(sc)
    _service(tmp_path, client).run_tool("prenatalsyzygy", _payload(sc), save_result=False)
    natal_call, syzygy_call = client.bodies("/")
    assert (syzygy_call["date"], syzygy_call["time"]) == ("1990/07/07", "22:23:29")  # splitDateTime：斜杠日期
    assert syzygy_call["tradition"] is False and syzygy_call["zodiacal"] == 1

    client = _LiveFixtureClient(sc)
    _service(tmp_path, client).run_tool("returntimeline", _payload(sc, **req["returnsOpts"]), save_result=False)
    (body,) = client.bodies("/astroextra/returns")
    assert (body["startYear"], body["count"]) == (2024, 5)


def test_upstream_defaults_apply_when_options_are_omitted(tmp_path: Path, frozen: None) -> None:
    """上游缺省：星历今日起 90 天含行运、max 食甚；回归轴今年起 12 年；推运今天 12:00:00 synodic。"""
    sc = _sc("sample")
    client = _LiveFixtureClient(sc)
    result = _service(tmp_path, client).run_tool("ephemeris", _payload(sc), save_result=False)
    (body,) = client.bodies("/astroextra/ephemeris")
    assert (body["startDate"], body["endDate"], body["includeTransits"]) == ("2026-09-24", "2026-12-23", True)
    assert "eclipseTimeMode" not in body
    assert "区间：2026-09-24 至 2026-12-23（" in result.data["snapshot_text"]

    client = _LiveFixtureClient(sc)
    result = _service(tmp_path, client).run_tool("returntimeline", _payload(sc), save_result=False)
    (body,) = client.bodies("/astroextra/returns")
    assert (body["startYear"], body["count"]) == (2026, 12)
    assert "区间：2026 年起 12 年（" in result.data["snapshot_text"]

    client = _LiveFixtureClient(sc)
    result = _service(tmp_path, client).run_tool("prog", _payload(sc), save_result=False)
    (body,) = client.bodies("/astroextra/progressions")
    assert (body["targetDate"], body["targetTime"], body["minorVariant"]) == ("2026-09-24", "12:00:00", "synodic")
    assert body["zodiacal"] == 0
    assert "目标日期：2026-09-24 12:00:00（" in result.data["snapshot_text"]

    # `datetime` 只在没给 targetDate 时作目标时刻（build_progressions 同序回退），且照实写进目标日期行
    client = _LiveFixtureClient(sc)
    result = _service(tmp_path, client).run_tool("prog", _payload(sc, datetime="2030-05-01 08:00:00"), save_result=False)
    (body,) = client.bodies("/astroextra/progressions")
    assert (body["targetDate"], body["targetTime"]) == ("2030-05-01", "08:00:00")
    assert "目标日期：2030-05-01 08:00:00（" in result.data["snapshot_text"]


@pytest.mark.parametrize(
    ("tool", "opts", "code"),
    [
        ("ephemeris", {"startDate": "2026-13-01"}, "tool.ephemeris_invalid_window"),
        ("ephemeris", {"startDate": "2027-01-01", "endDate": "2026-01-01"}, "tool.ephemeris_invalid_window"),
        ("ephemeris", {"eclipseTimeMode": "peak"}, "tool.ephemeris_invalid_option"),
        ("returntimeline", {"count": 41}, "tool.returntimeline_invalid_range"),
        ("prog", {"minorVariant": "lunar"}, "tool.prog_invalid_option"),
        ("prog", {"targetTime": "25:00"}, "tool.prog_invalid_option"),
        ("prog", {"targetDate": "next friday"}, "tool.prog_invalid_option"),
    ],
)
def test_bad_options_fail_loudly_with_structured_codes(tmp_path: Path, tool: str, opts: dict, code: str) -> None:
    sc = _sc("sample")
    result = _service(tmp_path, _LiveFixtureClient(sc)).run_tool(tool, _payload(sc, **opts), save_result=False)
    assert result.ok is False and result.error.code == code
    assert result.details.get("agent_recovery", {}).get("kind") == "input"


@pytest.mark.parametrize(
    ("tool", "endpoint", "response", "code"),
    [
        ("ephemeris", "/astroextra/ephemeris",
         {"params": {}, "ingresses": [], "stations": [], "lunarPhases": [], "eclipses": [], "transitAspects": []},
         "tool.ephemeris_empty"),
        ("returntimeline", "/astroextra/returns", {"rows": []}, "tool.returntimeline_empty"),
        ("returntimeline", "/astroextra/returns", {"result": "shape drift"}, "transport.invalid_result_shape"),
        ("prenatalsyzygy", "/astroextra/prenatal_syzygy", {"type": None}, "tool.prenatalsyzygy_unavailable"),
        ("prog", "/astroextra/progressions", {"methods": []}, "tool.prog_empty"),
    ],
)
def test_empty_backend_results_never_become_a_template_export(tmp_path: Path, tool: str, endpoint: str, response: dict, code: str) -> None:
    """上游 builder 此时返回 ''（挂载面显示「缺失」）；skill 若照样返回空快照会落 generated_template 假导出。"""
    sc = _sc("sample")
    client = _LiveFixtureClient(sc, overrides={endpoint: response})
    result = _service(tmp_path, client).run_tool(tool, _payload(sc), save_result=False)
    assert result.ok is False and result.error.code == code
    assert result.data == {}


def test_prenatal_syzygy_chart_failure_keeps_upstream_text_and_warns(tmp_path: Path, frozen: None) -> None:
    sc = _sc("sample")
    failure = ToolTransportError("boom / chart down", code="transport.http_error", details={})
    client = _LiveFixtureClient(sc, overrides={"syzygy_chart": failure})
    result = _service(tmp_path, client).run_tool("prenatalsyzygy", _payload(sc), save_result=False)
    _assert_clean(result)
    # 上游第二张盘取不到时的原样输出（AstroPrenatalSyzygy.js:65-66）——同一份 JS 金标
    assert result.data["snapshot_text"] == sc["golden"]["prenatalsyzygy_nochart"]
    assert any("prenatalsyzygy" in w for w in result.warnings), result.warnings

    # 朔望结果缺 datetime（splitDateTime → null）：同样写「暂缺」行，同样不许静默
    broken = {k: v for k, v in sc["prenatal_syzygy"].items() if k != "datetime"}
    client = _LiveFixtureClient(sc, overrides={"/astroextra/prenatal_syzygy": broken})
    result = _service(tmp_path, client).run_tool("prenatalsyzygy", _payload(sc), save_result=False)
    _assert_clean(result)
    assert "时刻：—" in result.data["snapshot_text"]
    assert "（产前朔望盘暂缺：未能以朔望时刻排盘。）" in result.data["snapshot_text"]
    assert len(client.bodies("/")) == 1, "缺 datetime 时不该再去排第二张盘"
    assert any("prenatalsyzygy" in w for w in result.warnings), result.warnings


# ─────────────────────────── live：真实 chart 服务 → 与上游 JS 金标逐字节相等 ───────────────────────────
# fixture 是同一组入参的 live 实抓（只裁掉 builder 不读的键 / CAP 之外的行），所以对一台同版本引擎的实例，
# 冻结时钟后的整段快照必须与金标逐字节相等；引擎值一漂（重同步了新版 astropy/flatlib）这里先红。

from test_local_js_tools import make_service, requires_chart, requires_current_runtime_contract  # noqa: E402

# 上游 astroextra.calc_stations 对「速度 = 0」二分求根，停滞这一行天生病态：Swiss Ephemeris 的速度带 5–9e-9 °/日的
# 数值抖动，停滞处速度的变化率却很小（冥王星 ≈ 4.6e-4 °/日²），根落在一个「速度符号由噪声决定」的窗口里——v0.40.0 payload
# 实测冥王星 2025-10-13 前后 ±5 s 内速度符号翻 181 次、窗口宽 6.9 s（天王星 3.7 s，木土海 ≈ 0.5 s，水金火 ≤ 0.03 s）。于是：
#   · 方向 = 根处速度的符号（'Direct' if hit_speed >= 0），纯噪声——mac 金标与 Windows（托管 x64 / ARM 与维护机）在不同
#     停滞点上翻，**两边都约一半标错**（天王星 2026-02-04 金牛 27°27′ 停滞转顺，mac 金标写 Retrograde）；
#   · 时刻跨平台差 ±1 s（Windows 实测 south_sidereal 木星 2025-02-04、冥王星 2025-10-13 各差 1 s），上界 = 窗口宽 + 1 s 取整。
# 所以 live 比对把停滞行单独拿出来：星体、位置逐字节相等，时刻差 ≤ 10 s；其余全文照旧逐字节比。方向：0.40.0 起产品侧声明式偏离
# （engine/ephemeris_stations.py，用户 2026-10-01 拍板）按逐日速度纠正，方向不再是噪声，按 fixture station_truth 逐字节比。引擎漂移由
# 那些行把关，不靠这 10 s：退回 Moshier 时停滞时刻只挪 1–28 s，但约一半月相时刻、四成月亮入座时刻按秒变。
# 台账 v0.40.0 / 2026-09-30「停滞方向取根处速度符号」；上游修好方向后由 test_upstream_station_direction_* 提醒恢复比方向。
_STATION_TABLE_TITLE = "留与顺逆转向："
_STATION_DIRECTIONS = ("Direct", "Retrograde")
_STATION_ROW = "| <station> |"
_STATION_TIME = re.compile(r"\| (\d{4}-\d{2}-\d{2}) (\d{2}):(\d{2}):(\d{2})")
_STATION_TIME_SLACK_S = 10


def _lift_station_rows(text: str) -> tuple[str, list[tuple[int, str, str, str]]]:
    """停滞表的数据行换成占位行，原样取出 (本地时刻秒数, 星体, 方向, 位置)；表头 / 分隔行 / 其它表、时刻认不出的行一字不动
    （留在全文里逐字节比）。"""
    out: list[str] = []
    rows: list[tuple[int, str, str]] = []
    in_table = False
    for line in text.split("\n"):
        if line == _STATION_TABLE_TITLE:
            in_table = True
        elif in_table and not line.startswith("|"):
            in_table = False
        if in_table:
            cells = line.split(" | ")
            stamp = _STATION_TIME.fullmatch(cells[0]) if len(cells) == 4 and cells[2] in _STATION_DIRECTIONS else None
            if stamp:
                day, h, m, s = stamp.groups()  # 上游取整进位可写出 24:00:00，不能交给 strptime
                seconds = datetime.fromisoformat(day).toordinal() * 86400 + int(h) * 3600 + int(m) * 60 + int(s)
                rows.append((seconds, cells[1], cells[2], cells[3]))
                line = _STATION_ROW
        out.append(line)
    return "\n".join(out), rows


def _assert_same_stations(got: list[tuple[int, str, str, str]], want: list[tuple[int, str, str, str]]) -> None:
    assert [r[1:] for r in got] == [r[1:] for r in want], "停滞：星体 / 方向 / 位置应逐行相等"
    drift = [(g[1], g[0] - w[0]) for g, w in zip(got, want) if g[0] != w[0]]
    assert all(abs(d) <= _STATION_TIME_SLACK_S for _, d in drift), f"停滞时刻超出噪声窗口（秒）：{drift}"


@requires_current_runtime_contract
@requires_chart
@pytest.mark.parametrize("name", SCENARIOS)
def test_live_chart_service_reproduces_the_upstream_goldens(tmp_path: Path, frozen: None, name: str) -> None:
    sc = _sc(name)
    req = sc["request"]
    service = make_service(tmp_path)
    for tool, opts, golden_key in (
        ("ephemeris", req["ephemerisOpts"], "ephemeris"),
        ("returntimeline", req["returnsOpts"], "returntimeline"),
        ("prenatalsyzygy", {}, "prenatalsyzygy"),
        ("prog", req["progOpts"], "prog"),
    ):
        result = service.run_tool(tool, _payload(sc, **opts), save_result=False)
        _assert_clean(result)
        got, want = result.data["snapshot_text"], sc["golden"][golden_key]
        if tool == "ephemeris":
            want = _with_true_station_directions(want, sc["station_truth"])  # 声明式偏离：方向 = 真值，与平台无关
            (got, got_rows), (want, want_rows) = _lift_station_rows(got), _lift_station_rows(want)
            assert want_rows, "金标里应有停滞行"
            _assert_same_stations(got_rows, want_rows)
        assert got == want, tool


def test_station_rows_are_lifted_out_and_nothing_else() -> None:
    for name, sc in FIX["scenarios"].items():
        golden = sc["golden"]["ephemeris"]
        lifted, rows = _lift_station_rows(golden)
        assert len(rows) == len(sc["ephemeris"]["stations"]), name
        before, after = golden.split("\n"), lifted.split("\n")
        assert len(before) == len(after), name
        changed = [b for b, a in zip(before, after) if b != a]
        assert len(changed) == len(rows) and all(a == _STATION_ROW for b, a in zip(before, after) if b != a), name
        assert all(c.split(" | ")[2] in _STATION_DIRECTIONS for c in changed), name
    # 其它表里的同名单词不受影响：只认停滞表；时刻认不出的停滞行留在全文里逐字节比
    assert _lift_station_rows("x | y | Direct | z") == ("x | y | Direct | z", [])
    odd = f"{_STATION_TABLE_TITLE}\n| — | 冥 | Direct | 摩羯 1.00° |"
    assert _lift_station_rows(odd) == (odd, [])
    # 取整进位写出的 24:00:00 = 次日 00:00:00；跨日的时刻差照样按秒算
    (_, (a,)) = _lift_station_rows(f"{_STATION_TABLE_TITLE}\n| 2025-01-01 24:00:00 | 冥 | Direct | 摩羯 1.00° |")
    (_, (b,)) = _lift_station_rows(f"{_STATION_TABLE_TITLE}\n| 2025-01-02 00:00:03 | 冥 | Direct | 摩羯 1.00° |")
    assert b[0] - a[0] == 3 and a[1:] == b[1:] and a[2] == "Direct"


def test_station_comparison_tolerates_the_noise_window_only() -> None:
    row = (1000, "冥", "Direct", "摩羯 1.00°")
    _assert_same_stations([(1000 + _STATION_TIME_SLACK_S, *row[1:])], [row])
    _assert_same_stations([(1000 - 1, *row[1:])], [row])
    with pytest.raises(AssertionError, match="噪声窗口"):
        _assert_same_stations([(1000 + _STATION_TIME_SLACK_S + 1, *row[1:])], [row])
    with pytest.raises(AssertionError, match="星体 / 方向 / 位置"):
        _assert_same_stations([(1000, "冥", "Direct", "摩羯 1.01°")], [row])
    with pytest.raises(AssertionError, match="星体 / 方向 / 位置"):
        _assert_same_stations([(1000, "冥", "Retrograde", "摩羯 1.00°")], [row])  # 纠正后方向是确定的，翻了就红
    with pytest.raises(AssertionError, match="星体 / 方向 / 位置"):
        _assert_same_stations([row, row], [row])


def test_upstream_station_direction_is_still_ill_conditioned() -> None:
    """自我退役守卫：同一颗星相邻停滞点必然顺逆交替，区间起点的运动状态（dailyPositions[0] 的速度）一定，
    每个停滞点「转成什么」就完全确定——这样推出的方向与天文事实一致。fixture 里 mac 实抓的上游标签与之矛盾，
    证明上游缺陷仍在。上游哪天改成按括号端的速度判向（它对入座已经这么修过：astroextra.py「入座符号取『已知的进入
    星座』cur_sign,而非由 hit_lon 反推」），重抓 fixture 后这里变红——那时本仓声明式偏离 engine/ephemeris_stations.py
    成了空操作、可以撤（时刻的噪声窗口是天生的，那 10 s 不撤）。这里推出的方向还与 station_truth（前后半天速度变号）逐条
    互证：两种独立推法必须一致。"""
    contradicted: list[str] = []
    for name, sc in FIX["scenarios"].items():
        eph = sc["ephemeris"]
        start = eph["dailyPositions"][0]
        assert start["jd"] == eph["params"]["startDate"]["jd"], name
        direct = {body: (pos.get("speed") or 0) >= 0 for body, pos in start["positions"].items()}
        for ev in eph["stations"]:
            direct[ev["body"]] = not direct[ev["body"]]
            derived = "Direct" if direct[ev["body"]] else "Retrograde"
            if derived != ev["direction"]:
                contradicted.append(f"{name} {ev['datetime']} {ev['body']} upstream={ev['direction']} derived={derived}")
            truth = next(r for r in sc["station_truth"] if (r["datetime"], r["body"]) == (ev["datetime"], ev["body"]))
            assert derived == truth["direction"], (name, ev["datetime"], ev["body"], derived, truth)
    hint = "上游停滞方向已与推导一致——本仓声明式偏离 engine/ephemeris_stations.py 可撤（见本测试 docstring）"
    assert contradicted, hint
    # 天文核对的一个锚：天王星 2026-02-04 在金牛 27°27′（黄经 57.46°）停滞转顺。
    uranus = next(e for e in FIX["scenarios"]["sample"]["ephemeris"]["stations"] if e["body"] == "Uranus")
    assert round(uranus["lon"], 2) == 57.46 and uranus["datetime"].startswith("2026-02-04")
    assert any("sample 2026-02-04" in c and "Uranus" in c and "derived=Direct" in c for c in contradicted), (hint, contradicted)
    # 同一次 mac 实抓里，同一个物理停滞点在两个场景里标反（只差时区 → 日网格不同 → 二分终点不同）：噪声的直接证据
    by_lon: dict[tuple[str, float], set[str]] = {}
    for sc in FIX["scenarios"].values():
        for ev in sc["ephemeris"]["stations"]:
            by_lon.setdefault((ev["body"], round(ev["lon"], 4)), set()).add(ev["direction"])
    assert any(len(v) == 2 for v in by_lon.values()), (hint, by_lon)


# ─────────────────────────── 注册 / 导出契约 / 路由 / 闸门 ───────────────────────────


def test_export_contract_mirrors_upstream_aiexport_v58() -> None:
    # 上游 utils/aiExport.js:635-637,648（逐字）
    assert R.AI_EXPORT_PRESET_SECTIONS["ephemeris"] == ["起盘信息", "星历事件（入座 · 留逆 · 朔望弦 · 食相）", "行运触发本命", "当前时点", "方法说明"]
    assert R.AI_EXPORT_PRESET_SECTIONS["returntimeline"] == ["起盘信息", "太阳/月亮返照时间轴", "当前时点", "方法说明"]
    assert R.AI_EXPORT_PRESET_SECTIONS["prenatalsyzygy"] == ["起盘信息", "产前朔望", "产前朔望盘·星体位置", "当前时点", "方法说明"]
    assert R.AI_EXPORT_PRESET_SECTIONS["prog"] == ["二次推运（回归黄道）", "本命盘配置", "时段盘配置 二次推运位置", "当前时点", "方法说明"]
    labels = {item["key"]: item["label"] for item in R.AI_EXPORT_TECHNIQUES}
    # aiExport.js:500-502,510
    assert [labels[k] for k in NEW_TOOLS] == ["星运-星历", "星运-回归轴", "星运-产前朔望", "星运-二次推运"]
    # aiExport.js:309-311,374 迁移键；:433 planet-info 只收 prog（三页不在集合内）
    assert set(NEW_TOOLS) <= set(R.AI_EXPORT_SECTION_MIGRATION_KEYS)
    assert "prog" in R.AI_EXPORT_PLANET_INFO_TECHNIQUES
    assert not {"ephemeris", "returntimeline", "prenatalsyzygy"} & R.AI_EXPORT_PLANET_INFO_TECHNIQUES
    for key in NEW_TOOLS:
        assert key not in R.AI_EXPORT_DEFAULT_OFF_SECTIONS and key not in R.AI_EXPORT_OPTIONAL_SECTIONS
        assert S.TOOL_EXPORT_TECHNIQUE_MAP[key] == key
        assert TOOL_DEFINITIONS[key].execution == "local" and TOOL_DEFINITIONS[key].mcp_name == f"horosa_predict_{key}"
    # [方法说明] 四键文案（上游 astroAiSnapshot.js:2046-2057,2087-2090 逐字；ASCII ',' ';' ':' 亦照抄）
    assert NOTES["prog"][0].startswith("二次推运:回归黄道下的推运(")
    assert NOTES["ephemeris"][1].endswith("结合本命点性质判吉凶。") and ";" in NOTES["ephemeris"][1]


@pytest.mark.parametrize(
    ("query", "expect"),
    [
        ("看看我接下来三个月的星历，有哪些行星入座", ["ephemeris"]),
        ("ephemeris for the next quarter", ["ephemeris"]),
        ("巴比伦数理星历", ["babylon"]),
        ("排一张回归轴看未来十年", ["returntimeline"]),
        ("太阳返照时间轴", ["returntimeline"]),  # 含「太阳返照」却是时间轴
        ("日月返照年表", ["returntimeline"]),  # 含「月返」二字
        ("今年的太阳返照盘", ["solarreturn"]),  # 原规则不受影响
        ("我的产前朔望取度是多少", ["prenatalsyzygy"]),
        ("prenatal syzygy of my chart", ["prenatalsyzygy"]),
        ("二次推运看明年", ["prog"]),
        ("secondary progression to 2030", ["prog"]),
        ("恒星黄道二次推运", ["vedicprog"]),  # 恒星支，不是回归支
        ("赤纬推运", ["jaynesprog"]),
        ("vedic progression next year", ["vedicprog"]),
    ],
)
def test_router_reaches_the_new_tools_without_collisions(query: str, expect: list[str]) -> None:
    assert select_tools(DispatchInput(query=query)) == expect


# ─────────────────────────── 上游漂移哨兵（有上游 checkout 时跑）───────────────────────────
# Python 移植件没有 vendor_manifest 的源 sha 戳可挂；这里直接对着上游源码核：builder 里每一段静态文案、四键
# [方法说明]、variant 三处文案、常量表（AstroTxtMsg / AstroMsg / LOTS / LIST_OBJECTS / 埃及界 / 宫制 / 岁差）。
# 上游改了任何一处 → 红 → 重核本移植并更新 fixture 金标（preflight_release 带 HOROSA_SOURCE_ROOT 跑全套 pytest）。

_UPSTREAM_SRC = Path(os.environ.get("HOROSA_SOURCE_ROOT") or "/nonexistent") / "Horosa-Web" / "astrostudyui" / "src"
needs_upstream = pytest.mark.skipif(not _UPSTREAM_SRC.is_dir(), reason="drift sentinel needs HOROSA_SOURCE_ROOT (upstream checkout)")

_UPSTREAM_BUILDERS = {
    "components/astro/AstroEphemeris.js": ("buildEphemerisSnapshotText", "ephemerisLimitsText", "defaultEphemerisWindow", "fmtDateOf"),
    "components/astro/AstroReturnTimeline.js": ("buildReturnTimelineSnapshotText", "rtDeg"),
    "components/astro/AstroPrenatalSyzygy.js": ("buildPrenatalSyzygySnapshotText", "splitDateTime", "psName"),
    "components/astro/astroProgSnapshot.js": ("buildProgSnapshotText", "methodTab"),
    "components/astro/AstroExtraCommon.js": ("signName", "fmtNum", "fmtDegree"),
    "utils/astroAiSnapshot.js": (
        "buildPredictiveBirthLines", "buildPredictiveBirthHeaderLines", "buildCurrentMomentLines", "buildMethodNoteLines",
        "formatSignDegree", "gfmTableLines", "buildHouseCuspLines", "buildStarAndLotPositionLines",
    ),
}


def _upstream_function(text: str, name: str) -> str:
    match = re.search(r"^(?:export\s+)?(?:async\s+)?function\s+" + name + r"\s*\(", text, re.M)
    assert match, f"upstream function {name} vanished — re-audit the port"
    end = text.index("\n}\n", match.start())
    return text[match.start() : end]


def _static_fragments(src: str) -> list[str]:
    body = "\n".join(line for line in src.splitlines() if not line.strip().startswith("//"))
    frags = re.findall(r"'((?:[^'\\\n]|\\.)*)'", body)
    for tpl in re.findall(r"`((?:[^`\\]|\\.)*)`", body):
        frags.extend(re.split(r"\$\{(?:[^{}]|\{[^{}]*\})*\}", tpl))
    return [f.strip() for f in frags if len(f.strip()) >= 2 and re.search(r"[^\x00-\x7f]", f)]


@needs_upstream
def test_every_upstream_builder_literal_is_in_the_port() -> None:
    port = Path(A.__file__).read_text(encoding="utf-8")
    missing = []
    for rel, names in _UPSTREAM_BUILDERS.items():
        text = (_UPSTREAM_SRC / rel).read_text(encoding="utf-8")
        for name in names:
            for frag in _static_fragments(_upstream_function(text, name)):
                # 嵌套模板字符串会被切出 `: '—'}` 这类代码碎片（含引号/花括号）——不是文案，跳过。
                if frag not in port and not re.search(r"[{}'?]", frag):
                    missing.append((rel, name, frag))
    assert missing == [], f"upstream builder text changed — re-port engine/astroextra_snapshots.py: {missing[:10]}"


@needs_upstream
def test_method_notes_variants_and_tables_track_upstream() -> None:
    snap = (_UPSTREAM_SRC / "utils/astroAiSnapshot.js").read_text(encoding="utf-8")
    block = snap[snap.index("export const PREDICTIVE_METHOD_NOTES = {") :]
    block = block[: block.index("\n};")]
    for key in NEW_TOOLS:
        m = re.search(r"\n\t" + key + r": \[(.*?)\n\t\],", block, re.S)
        assert re.findall(r"'((?:[^'\\]|\\.)*)'", m.group(1)) == NOTES[key], key
    prog_src = (_UPSTREAM_SRC / "components/astro/astroProgSnapshot.js").read_text(encoding="utf-8")
    for variant in A.PROG_SNAPSHOT_VARIANTS.values():
        for field in ("section", "intro", "posCol"):
            assert f"'{variant[field]}'" in prog_src, (field, variant[field])
    const = (_UPSTREAM_SRC / "constants/AstroConst.js").read_text(encoding="utf-8")
    consts = dict(re.findall(r"export const ([A-Za-z_0-9]+)\s*=\s*'([^']*)'", const))
    text = (_UPSTREAM_SRC / "constants/AstroText.js").read_text(encoding="utf-8")
    seg = text[text.index("export const AstroTxtMsg = {") : text.index("export const UranianAbbr")]
    txt = dict(re.findall(r"^\s*(Asp\d+):\s*'([^']*)'", seg, re.M))
    txt.update({consts[k]: v for k, v in re.findall(r"AstroTxtMsg\[AstroConst\.([A-Za-z_0-9]+)\]\s*=\s*'([^']*)';", seg)})
    assert txt == A.ASTRO_TXT_MSG

    def const_list(name: str) -> tuple[str, ...]:
        body = re.search(r"export const " + name + r" = \[(.*?)\]", const, re.S).group(1)
        return tuple(consts[x.strip()] for x in body.replace("\n", " ").split(",") if x.strip())

    assert const_list("LOTS") == A.LOTS and const_list("LIST_OBJECTS") == A.LIST_OBJECTS and const_list("LIST_SIGNS") == A.LIST_SIGNS
    house = re.search(r"export const HOUSE_SYSTEM_OPTIONS = \[(.*?)\];", const, re.S).group(1)
    assert {v: lab for v, lab in re.findall(r"\{ value: (\d+), label: '([^']*)' \}", house)} == A.HOUSE_SYS
    ayan = re.search(r"export const INDIA_AYANAMSA_OPTIONS = \[(.*?)\];", const, re.S).group(1)
    assert dict(re.findall(r"\{ value: '([^']*)', label: '([^']*)'", ayan)) == A.AYANAMSA_LABELS


def test_gate_asks_the_result_changing_settings() -> None:
    birth = {"date": "1990-01-01", "time": "12:00:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"}

    def asked(tool: str, payload: dict) -> dict:
        verdict = validate_agent_preflight(tool, payload)
        assert verdict["ok"] is False, tool
        return {str(item["field"]): item for item in verdict["ask_if_missing"]}

    eph = asked("ephemeris", birth)
    assert "startDate/endDate" in eph and eph["includeTransits"]["values"] == [True, False]
    assert "startYear/count" in asked("returntimeline", birth)
    prog = asked("prog", birth)
    assert "targetDate/targetTime" in prog and prog["minorVariant"]["values"] == ["synodic", "sidereal", "engine"]
    assert "startDate/endDate" not in asked("ephemeris", {**birth, "startDate": "2026-01-01", "endDate": "2026-02-01"})
    for tool in NEW_TOOLS:
        assert validate_agent_preflight(tool, {**birth, "defaults_accepted": True})["ok"] is True
