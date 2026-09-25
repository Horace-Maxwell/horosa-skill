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
        assert result.data["snapshot_text"] == sc["golden"][golden_key], tool
        assert result.data["export_snapshot"]["technique"]["key"] == tool
        assert result.data["export_snapshot"]["section_titles_detected"] == R.AI_EXPORT_PRESET_SECTIONS[tool], tool


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
        assert result.data["snapshot_text"] == sc["golden"][golden_key], tool


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
