"""上游 v3.14.0 同步 · 命 · 其他：东亚诸术（dongya）/ 诸方杂术（zhufang）——离线契约。

两个都是「一个工具多段子术」。算法、口径词表、请求体映射与快照排版全是 vendored 上游：
- vendor/dongya/eastAsiaArts.js · eastAsiaSnapshot.js（buildEastAsiaModel / eastAsiaSnapshotLines / EAST_ASIA_PAGE_SETTINGS）
- vendor/zhufang/zhufangArts.js（localZhufangModel / zhufangSnapshotLines / ZHUFANG_PAGE_SETTINGS）
- vendor/zhufang/zhufangRequest.js（上游网络件 zhufangRemote.js 的请求体映射与回包判据，逐字抽出，sha 看守）
Python 只取后端数据（/chart、/astroextra/zhufang）并把「此刻」交给 JS。

这里钉的是接线：每个口径「改这个参数，结果必须变」、缺的东西显式进 warnings、请求体就是上游那一份、路由与互斥。
子术的值级金标（藏历新年、流年八卦两条序列、长计历 13.0.0.0.0、Kin 34 / 207、人类图手推…）在 horosa-core-js/test/selfcheck.mjs
的 dongya / zhufang 八条；本文件另把上游的 245 个对照藏历日经工具整条链重放。真后端的值在 test_sync314_mingother_live.py。

负向对照（均实跑过，注回的 bug 与红在哪一行记在各条 docstring 里）。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from fakes import CaptureClient, FakeClient, FakeJsClient
from node_esm import run_node_esm

from horosa_skill.agent_guidance import TOOL_GUIDANCE
from horosa_skill.agent_guidance.questions import GENDER_FACT_TOOLS
from horosa_skill.cn_vocab import CN_VOCABULARIES
from horosa_skill.config import Settings
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.engine.router import route
from horosa_skill.engine.time_roles import TIME_ROLES
from horosa_skill.errors import ToolTransportError, ToolValidationError
from horosa_skill.exports.registry import (
    AI_EXPORT_OPTIONAL_SECTIONS,
    AI_EXPORT_PRESET_SECTIONS,
    AI_EXPORT_SECTION_MIGRATION_KEYS,
    AI_EXPORT_TECHNIQUES,
)
from horosa_skill.memory.store import MemoryStore
from horosa_skill.schemas.tools import DispatchInput, DongyaInput, ZhufangInput
from horosa_skill.service import HorosaSkillService, _clock
from horosa_skill.service.endpoints import _PYTHON_CHART_ENDPOINTS
from horosa_skill.testing_payloads import build_sample_payloads

PKG = Path(__file__).resolve().parents[1]
CORE_JS = PKG / "horosa-core-js"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
ZHUFANG_LIVE = json.loads((CORE_JS / "test" / "fixtures" / "sync314_mingother_zhufang_live.json").read_text(encoding="utf-8"))["scenarios"]
TIBETAN = json.loads((FIXTURES / "sync314_mingother_tibetan_reference.json").read_text(encoding="utf-8"))
_UPSTREAM_ROOT = os.environ.get("HOROSA_SOURCE_ROOT")
UPSTREAM_WEB = Path(_UPSTREAM_ROOT) / "Horosa-Web" if _UPSTREAM_ROOT else None
UPSTREAM_UI = UPSTREAM_WEB / "astrostudyui" / "src" if UPSTREAM_WEB else None
requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="[host] node not installed")
requires_upstream = pytest.mark.skipif(
    UPSTREAM_UI is None or not (UPSTREAM_UI / "utils" / "eastAsiaSnapshot.js").is_file(),
    reason="[upstream-checkout] HOROSA_SOURCE_ROOT (upstream v3.14.0 checkout) not set",
)
pytestmark = requires_node  # 两个技法的离线桩直接跑真 JS（tests/fakes.py _run_real_js_tool）

CONFIRMED = {"agent_confirmed_settings": True}
CHART = "/"  # chart 服务上的 /chart（service/endpoints._chart_server_endpoint 把它映成根路径；client 看到的是这个）
# 上游 eastAsiaSnapshot.test.js / astropy/tests/test_zhufang_arts.py 的夹具盘：西雅图 1975-02-10 21:15（藏历新年前一天、朔日）。
BIRTH = {"date": "1975-02-10", "time": "21:15:00", "zone": "-08:00", "lat": "47n36", "lon": "122w20"}
DONGYA = {**CONFIRMED, **BIRTH, "gender": 0}
ZHUFANG = {**CONFIRMED, **BIRTH, "hsys": 3}
DONGYA_SECTIONS = ["藏历", "藏占", "蒙古 Zurkhai", "算命学", "九星气学", "洛书流年", "易卦星盘"]
ZHUFANG_SECTIONS = ["玛雅历", "十三月亮历", "人类图", "灵名字母"]
NOW_UTC = datetime(2026, 11, 7, 12, 0, 0, tzinfo=timezone.utc)  # 上游 eastAsiaSnapshot.test.js 的 NOW
NOW_LOCAL = datetime.fromtimestamp(NOW_UTC.timestamp())


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):  # noqa: ANN001 - datetime.now 签名
        return NOW_LOCAL if tz is None else NOW_UTC.astimezone(tz)


@pytest.fixture()
def frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_clock, "datetime", _FrozenDatetime)


def _service(tmp_path: Path, client: Any = None) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
                        runtime_root=tmp_path / "runtime", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    return HorosaSkillService(settings, client=client or FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())


def _ok(service: HorosaSkillService, tool: str, payload: dict[str, Any]) -> Any:
    result = service.run_tool(tool, payload, save_result=False)
    assert result.ok, (result.error.code if result.error else None, result.error.message if result.error else None)
    return result


def _section(text: str, title: str) -> list[str]:
    lines = text.split("\n")
    at = lines.index(f"[{title}]")
    out: list[str] = []
    for line in lines[at + 1:]:
        if re.fullmatch(r"\[[^\]]+\]", line):
            break
        out.append(line)
    return out


def _clean(result: Any, sections: list[str]) -> None:
    export = result.data["export_snapshot"]
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []
    assert [row["title"] for row in export["sections"]] == sections
    assert all(str(row.get("body") or "").strip() for row in export["sections"])


def _node(script: str) -> Any:
    return json.loads(run_node_esm(script, cwd=CORE_JS))


class _FailingClient(FakeClient):
    """指定端点抛错（其余照 FakeClient）；记录请求。"""

    def __init__(self, endpoint: str, code: str) -> None:
        super().__init__()
        self.endpoint, self.code = endpoint, code
        self.calls: list[tuple[str, dict]] = []

    def call(self, endpoint: str, payload: dict) -> dict:
        self.calls.append((endpoint, dict(payload)))
        if endpoint == self.endpoint:
            raise ToolTransportError("backend down (test)", code=self.code, details={"endpoint": endpoint})
        return super().call(endpoint, payload)


class _PartialZhufangClient(CaptureClient):
    """/astroextra/zhufang 只算出指定的块（后端内部出错：该块回 null，HTTP 200）。"""

    def __init__(self, keep: tuple[str, ...]) -> None:
        super().__init__()
        self.keep = keep

    def call(self, endpoint: str, payload: dict) -> dict:
        response = super().call(endpoint, payload)
        if endpoint == "/astroextra/zhufang":
            return {key: (value if key in self.keep else None) for key, value in response.items()}
        return response


# ───────────────────────────── 登记 / 契约 ─────────────────────────────

def test_both_tools_are_registered_local_with_export_presets_and_roles() -> None:
    assert TOOL_DEFINITIONS["dongya"].mcp_name == "horosa_cn_dongya" and TOOL_DEFINITIONS["dongya"].execution == "local"
    assert TOOL_DEFINITIONS["zhufang"].mcp_name == "horosa_other_zhufang" and TOOL_DEFINITIONS["zhufang"].execution == "local"
    assert TOOL_DEFINITIONS["dongya"].input_model is DongyaInput and TOOL_DEFINITIONS["zhufang"].input_model is ZhufangInput
    # 逐字 = 上游 aiExport/presets.js AI_EXPORT_PRESET_SECTIONS.dongya / zhufang（v64）。
    assert AI_EXPORT_PRESET_SECTIONS["dongya"] == DONGYA_SECTIONS and AI_EXPORT_PRESET_SECTIONS["zhufang"] == ZHUFANG_SECTIONS
    labels = {item["key"]: item["label"] for item in AI_EXPORT_TECHNIQUES}
    assert labels["dongya"] == "东亚诸术" and labels["zhufang"] == "诸方杂术"
    assert {"dongya", "zhufang"} <= set(AI_EXPORT_SECTION_MIGRATION_KEYS)
    # 每段无条件恒出（缺东西时段内写明）→ 没有可选段。
    assert not AI_EXPORT_OPTIONAL_SECTIONS.get("dongya") and not AI_EXPORT_OPTIONAL_SECTIONS.get("zhufang")
    assert TIME_ROLES["dongya"] == "natal" and TIME_ROLES["zhufang"] == "natal"
    # 漏登记 → 请求落到 Java 聚合层（那边没有这条路由，HTTP 500）。
    assert "/astroextra/zhufang" in _PYTHON_CHART_ENDPOINTS
    # 性别：东亚诸术的流年八卦随性别变（selfcheck 两条序列 + live A/B）；诸方杂术后端不读性别（live A/B 证明）。
    assert "dongya" in GENDER_FACT_TOOLS and "zhufang" not in GENDER_FACT_TOOLS
    assert set(build_sample_payloads()) >= {"dongya", "zhufang"}


def test_presets_vocabularies_and_defaults_equal_the_vendored_upstream_tables() -> None:
    """Python 侧的段表、口径词表、缺省值与 vendored 上游表互锚（上游改表 → 重 vendor 后这里红）。

    负向对照：CN_VOCABULARIES["dongya"]["ichingMerge"] 删掉 "lower" → `ichingMerge` 的断言红。"""
    tables = _node(
        "import { EAST_ASIA_PAGE_SETTINGS as E, EAST_ASIA_SNAPSHOT_SECTIONS as ES } from './src/vendor/dongya/eastAsiaSnapshot.js';"
        "import { ZHUFANG_PAGE_SETTINGS as Z, ZHUFANG_SNAPSHOT_SECTIONS as ZS, MAYAN_CORRELATIONS as M } from './src/vendor/zhufang/zhufangArts.js';"
        "import { FLOW_YEAR_RANGE } from './src/tools/dongya.js';"
        "console.log(JSON.stringify({ east: E.schema, eastDefaults: E.defaults(), eastSections: ES, zhufang: Z.schema,"
        " zhufangDefaults: Z.defaults(), zhufangSections: ZS, mayan: M, flowYear: FLOW_YEAR_RANGE }));"
    )
    assert AI_EXPORT_PRESET_SECTIONS["dongya"] == tables["eastSections"]
    assert AI_EXPORT_PRESET_SECTIONS["zhufang"] == tables["zhufangSections"]
    for key in ("fenyeVersion", "ichingMerge"):
        assert list(CN_VOCABULARIES["dongya"][key].labels) == tables["east"][key]["oneOf"], key
    assert list(CN_VOCABULARIES["zhufang"]["mayanCorrelation"].labels) == tables["zhufang"]["mayanCorrelation"]["oneOf"] == tables["mayan"]
    assert list(CN_VOCABULARIES["zhufang"]["spiritQuadrant"].labels) == tables["zhufang"]["spiritQuadrant"]["oneOf"]
    assert tables["zhufang"]["hdTrueNode"]["def"] is True and list(CN_VOCABULARIES["zhufang"]["hdTrueNode"].labels) == [1, 0]
    assert tables["flowYear"] == [1, 9999]
    # 指引里写的缺省 = vendored 出厂值。
    defaults = {tool: {row["field"]: row["value"] for row in TOOL_GUIDANCE[tool]["safe_defaults"]} for tool in ("dongya", "zhufang")}
    assert defaults["dongya"]["fenyeVersion"] == tables["eastDefaults"]["fenyeVersion"]
    assert defaults["dongya"]["ichingMerge"] == tables["eastDefaults"]["ichingMerge"]
    assert defaults["dongya"]["flowYear"] is None
    for key in ("mayanCorrelation", "hdTrueNode", "spiritQuadrant"):
        assert defaults["zhufang"][key] == tables["zhufangDefaults"][key], key
    # 每个旋钮在 options_keys 里都有说明（旋钮不进广告层，guidance 是唯一的文档）。
    assert {"flowYear", "fenyeVersion", "ichingMerge", "hsys", "response_sections"} <= set(TOOL_GUIDANCE["dongya"]["options_keys"])
    assert {"mayanCorrelation", "hdTrueNode", "spiritQuadrant", "hsys", "response_sections"} <= set(TOOL_GUIDANCE["zhufang"]["options_keys"])


def test_advertised_schema_keeps_knobs_out_of_tools_list() -> None:
    """广告层只给域核心 + 流年；口径旋钮照收但不广告（tools/list 预算）。"""
    from horosa_skill.surfaces.mcp_schema import advertised_technique_schema

    dongya = advertised_technique_schema("dongya", DongyaInput.model_json_schema())["properties"]
    assert {"date", "time", "zone", "lat", "lon", "gender", "flowYear"} <= set(dongya)
    assert not {"fenyeVersion", "ichingMerge", "timeAlg"} & set(dongya)
    zhufang = advertised_technique_schema("zhufang", ZhufangInput.model_json_schema())["properties"]
    assert {"date", "time", "zone", "lat", "lon", "hsys"} <= set(zhufang)
    assert not {"mayanCorrelation", "hdTrueNode", "spiritQuadrant", "zodiacal", "siderealAyanamsa", "gender"} & set(zhufang)
    # 干支历按直接时间、0 点换日是技法定义：模型不声明 timeAlg（声明了会被 CN 域核心广告出去，而它不改结果）。
    assert "timeAlg" not in DongyaInput.model_fields


# ───────────────────────────── 东亚诸术 ─────────────────────────────

def test_dongya_offline_chain_is_clean_and_every_knob_changes_its_section(tmp_path: Path, frozen: None) -> None:
    """七段齐全、段序 = 预设；流年 / 性别 / 藏干表 / 合卦方式各改各的段；本命盘请求不带技法旋钮。

    负向对照：runner 的 js_payload 去掉 `*self._DONGYA_KNOBS` → flowYear / fenyeVersion / ichingMerge 三条断言红
    （`assert lo[0].startswith("2030 年")` 一行先红）；去掉 "gender" → 流年八卦断言红。"""
    client = CaptureClient()
    service = _service(tmp_path, client)
    base = _ok(service, "dongya", DONGYA)
    _clean(base, DONGYA_SECTIONS)
    text = base.data["snapshot_text"]
    data = base.data["dongya"]
    # 流年缺省 = 冻结时钟的今年（上游「留空 = 今年」）；如实标「不是用户给的」。
    assert data["settings"] == {"fenyeVersion": "common", "ichingMerge": "horizon", "flowYear": 2026, "flowYearGiven": False}
    assert base.data["now_ms"] == int(NOW_UTC.timestamp() * 1000)
    assert _section(text, "藏历")[0] == "出生藏历:1974 年 12 月 30 日,月曜日"
    assert _section(text, "藏占")[0].startswith("2026 年 53 岁(女命):流年八卦 离(Li,南,火)")
    assert _section(text, "洛书流年")[0].startswith("2026 年(51 岁):中宫 7,当年数 9")
    # 易卦星盘读的是 /chart 回来的七政（桩盘的日 14.55° 第 8 宫 …）：七行 + 规则行 + 推运行。
    iching = _section(text, "易卦星盘")
    assert iching[0] == "合卦规则:地平上合上卦、地平下合下卦" and len(iching) == 9 and iching[-1].startswith("易卦推运:今日环位 ")
    assert data["hasChart"] is True and base.data["compute_sources"] == {"arts": "dongya", "natal_chart": "chart_service"}
    assert base.data["technique_card"]["compute"]["matches_declaration"] is True
    assert base.warnings == []
    # skill 替调用方定下的「此刻」口径进技法依据卡：流年取了哪一年、易卦推运按哪一刻的「今日」。
    card = base.data["technique_card"]["settings"]
    assert card["flowYear"]["value"] == 2026 and "未指定" in card["flowYear"]["label"]
    assert card["ichingProgressionAt"]["value"] == "2026-11-07 12:00 UTC"
    assert card["gender"]["value"] == 0 and card["fenyeVersion"]["value"] == "common" and card["hsys"]["value"] == 1

    # 本命盘请求：出生资料 + 宫制 / 黄道，predictive 0；不带性别与技法旋钮。
    chart_bodies = [body for endpoint, body in client.calls if endpoint == CHART]
    assert len(chart_bodies) == 1
    body = chart_bodies[0]
    assert body["hsys"] == 1 and body["zodiacal"] == 0 and body["predictive"] == 0 and body["tradition"] is False
    assert set(body) <= {"date", "time", "zone", "lat", "lon", "gpsLat", "gpsLon", "ad", "hsys", "zodiacal", "siderealAyanamsa", "tradition", "predictive"}

    given = _ok(service, "dongya", {**DONGYA, "flowYear": 2030})
    lo = _section(given.data["snapshot_text"], "洛书流年")
    assert lo[0].startswith("2030 年(55 岁)")
    assert "flowYear" not in given.data["settings_applied"] and given.data["technique_card"]["settings"]["flowYear"]["value"] == 2030
    male = _section(_ok(service, "dongya", {**DONGYA, "gender": 1}).data["snapshot_text"], "藏占")
    assert male[0].startswith("2026 年 53 岁(男命):流年八卦 坎(Kham,北,水)")
    fajue = _ok(service, "dongya", {**DONGYA, "fenyeVersion": "fajue"}).data["snapshot_text"]
    assert _section(fajue, "算命学")[1] != _section(text, "算命学")[1] and "月支 寅 → 己" in _section(fajue, "算命学")[1]
    upper = _section(_ok(service, "dongya", {**DONGYA, "ichingMerge": "upper"}).data["snapshot_text"], "易卦星盘")
    lower = _section(_ok(service, "dongya", {**DONGYA, "ichingMerge": "lower"}).data["snapshot_text"], "易卦星盘")
    assert upper[0] == "合卦规则:恒合上卦" and lower[0] == "合卦规则:恒合下卦" and upper[1:8] != lower[1:8]
    # 宫制 / 黄道随入参进本命盘请求（真后端上它们改落宫与黄经，见 live 用例）。
    _ok(service, "dongya", {**DONGYA, "hsys": 3, "zodiacal": 1})
    assert client.calls[-1][0] == CHART and client.calls[-1][1]["hsys"] == 3 and client.calls[-1][1]["zodiacal"] == 1


def test_dongya_needs_gender_and_refuses_values_outside_the_upstream_vocabulary(tmp_path: Path, frozen: None) -> None:
    """性别是事实（不默认成男——上游 normBinaryGender 缺省 '1'）；口径值只认上游词表；公元前照上游页面的说法拒绝。

    负向对照：GENDER_FACT_TOOLS 去掉 "dongya" → 第一条不抛（改成悄悄按男命排）。"""
    service = _service(tmp_path)
    with pytest.raises(ToolValidationError) as missing:
        service.run_tool("dongya", {**CONFIRMED, **BIRTH}, save_result=False)
    assert missing.value.code == "tool.missing_gender" and missing.value.details["field"] == "gender"
    for bad in ({"fenyeVersion": "bogus"}, {"ichingMerge": "sideways"}, {"flowYear": 0}, {"flowYear": 10000}, {"flowYear": "next"}):
        with pytest.raises(ToolValidationError) as refused:
            service.run_tool("dongya", {**DONGYA, **bad}, save_result=False)
        assert refused.value.code == "tool.invalid_option" and refused.value.details["field"] in bad, bad
    # 认得的中文叫法换成规范值（并进 warnings）。
    alias = _ok(service, "dongya", {**DONGYA, "fenyeVersion": "法诀版", "ichingMerge": "恒合上卦"})
    assert alias.data["dongya"]["settings"]["fenyeVersion"] == "fajue" and alias.data["dongya"]["settings"]["ichingMerge"] == "upper"
    # 公元前：干支历只覆盖公元后 → 结构化拒绝，不回空快照。
    bc = service.run_tool("dongya", {**DONGYA, "date": "-0500-03-01", "ad": -1}, save_result=False)
    assert not bc.ok and bc.error.code == "tool.date_range_unsupported"
    assert "公元前出生暂不排东亚诸术" in bc.error.details["engine_message"]


def test_dongya_without_the_natal_chart_degrades_visibly_and_a_starting_runtime_is_not_degraded(tmp_path: Path, frozen: None) -> None:
    """取不到本命盘：照上游「取不到就只少那一段」，六段照算、[易卦星盘] 写明未出——但必须进 warnings、算源如实标。
    runtime 正在启动则上抛（稍后重试同一调用就有完整七段）。

    负向对照：runner 的 `if chart_error is not None:` 分支删掉 → `assert len(result.warnings) == 1` 红（静默少内容）。"""
    result = _ok(_service(tmp_path, _FailingClient(CHART, "transport.http_error")), "dongya", DONGYA)
    _clean(result, DONGYA_SECTIONS)  # 段还在：导出契约不缺段
    iching = _section(result.data["snapshot_text"], "易卦星盘")
    assert iching[0] == "没有本命盘星位,易卦星盘未出。" and iching[1].startswith("易卦推运:今日环位 ")
    assert len(result.warnings) == 1 and "[易卦星盘]" in result.warnings[0] and "transport.http_error" in result.warnings[0]
    assert result.data["compute_sources"] == {"arts": "dongya", "natal_chart": "unavailable"}
    assert result.data["dongya"]["hasChart"] is False and result.data["chart"] is None
    assert _section(result.data["snapshot_text"], "藏历")[0] == "出生藏历:1974 年 12 月 30 日,月曜日"

    starting = _service(tmp_path / "s", _FailingClient(CHART, "runtime.starting")).run_tool("dongya", DONGYA, save_result=False)
    assert not starting.ok and starting.error.code == "runtime.starting"


@pytest.mark.parametrize("zone, hour, expect_year", [("+08:00", 1, 2026), ("-08:00", 9, 2025)])
def test_dongya_default_flow_year_follows_the_frozen_clock_in_the_chart_zone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, zone: str, hour: int, expect_year: int
) -> None:
    """流年缺省「今年」按盘的时区取（上游用例）：UTC 2025-12-31 17:00 = 东八区元旦凌晨、西八区除夕上午。now 来自服务层时钟。

    负向对照：runner 不传 now_ms → JS 用真实此刻，两种时区都得到真实年份，2025 那条红。"""
    eve = datetime(2025, 12, 31, 17, 0, 0, tzinfo=timezone.utc)

    class _Eve(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001
            return datetime.fromtimestamp(eve.timestamp()) if tz is None else eve.astimezone(tz)

    monkeypatch.setattr(_clock, "datetime", _Eve)
    result = _ok(_service(tmp_path), "dongya", {**DONGYA, "zone": zone})
    assert _section(result.data["snapshot_text"], "洛书流年")[0].startswith(f"{expect_year} 年(")
    assert hour in (1, 9)  # 说明用：两地此刻的钟面小时


def test_dongya_replays_the_upstream_reference_tibetan_days_through_the_tool() -> None:
    """上游的 245 个独立对照藏历日（经度 122°20′W）逐日经 tools/dongya.js 整条链重放：藏历年 / 月 / 闰月 / 日 / 重日、
    太阴日九宫、历日九宫全对。每行的儒略日换成 UT 钟面时刻、时区 +00:00、经度取夹具值。

    负向对照：tools/dongya.js 把 `lon: { value: input.lon }` 改成不传经度（上游缺经度按 0° 算日界）→ 245 行里错 77 行。"""
    script = """
import { readFileSync } from 'node:fs';
import { runDongya } from './src/tools/dongya.js';
const fx = JSON.parse(readFileSync(process.argv[1], 'utf8'));
const pad = (n) => String(n).padStart(2, '0');
const bad = [];
let leap = 0, extra = 0;
for (const [jd, y, m, isLeap, d, isExtra, lnum, dnum] of fx.reference) {
  const t = new Date(Math.round((jd - 2440587.5) * 86400000));
  const r = runDongya({
    date: `${t.getUTCFullYear()}-${pad(t.getUTCMonth() + 1)}-${pad(t.getUTCDate())}`,
    time: `${pad(t.getUTCHours())}:${pad(t.getUTCMinutes())}:${pad(t.getUTCSeconds())}`,
    zone: '+00:00', lat: '47n36', lon: fx.lonEast, gender: 1, flowYear: 2026, now_ms: Date.UTC(2026, 10, 7, 12),
  });
  if (!r.data.ok) { bad.push([jd, r.data]); continue; }
  const tib = r.data.model.tibetan.date;
  const mewa = r.data.model.mewa;
  leap += isLeap; extra += isExtra;
  if (tib.year !== y || tib.month !== m || (tib.leap ? 1 : 0) !== isLeap || tib.day !== d || (tib.extra ? 1 : 0) !== isExtra
      || mewa.lunarDay !== lnum || mewa.calendarDay !== dnum) {
    bad.push([jd, [y, m, isLeap, d, isExtra, lnum, dnum], [tib.year, tib.month, tib.leap, tib.day, tib.extra, mewa.lunarDay, mewa.calendarDay]]);
  }
}
console.log(JSON.stringify({ rows: fx.reference.length, bad, leap, extra }));
"""
    result = json.loads(run_node_esm(script, str(FIXTURES / "sync314_mingother_tibetan_reference.json"), cwd=CORE_JS))
    assert result["rows"] == 245
    assert result["leap"] > 0 and result["extra"] > 0  # 夹具里真有闰月与重日（否则那两列等于没测）
    assert result["bad"] == [], result["bad"][:5]


# ───────────────────────────── 诸方杂术 ─────────────────────────────

def test_zhufang_offline_chain_sends_the_upstream_request_and_every_knob_changes_its_section(tmp_path: Path) -> None:
    """四段齐全；发给后端的请求体就是上游 zhufangParamsFromFields + zhufangRemote 映射产出的那一份（夹具里录的）；
    关联常数 / 交点 / 象限 / 宫制各改各的。

    负向对照：runner 把 `self._call_remote("/astroextra/zhufang", request)` 的 request 换成 payload（skill 写法的日期
    1975-02-10、布尔 hdTrueNode）→ `assert bodies[0] == …["request"]` 红。"""
    client = CaptureClient()
    service = _service(tmp_path, client)
    base = _ok(service, "zhufang", ZHUFANG)
    _clean(base, ZHUFANG_SECTIONS)
    text = base.data["snapshot_text"]
    bodies = [body for endpoint, body in client.calls if endpoint == "/astroextra/zhufang"]
    assert bodies[0] == ZHUFANG_LIVE["default"]["request"] == base.data["request"]
    assert _section(text, "玛雅历")[0].startswith("长历 12.18.1.10.11(关联常数 584283);卓尔金 7 Chuwen 猴")
    assert _section(text, "十三月亮历")[0].startswith("Kin 168:水晶调性 12 · 黄星星")
    assert _section(text, "人类图")[0] == "类型 投射者 · 内在权威 直觉(脾) · 人生角色 4/6(机会主义者 / 角色模范) · 二分人"
    assert _section(text, "灵名字母")[1] == "十一宫度数主星 土星(巨蟹 12.82°)→ מ Mem"
    assert base.data["zhufang"]["settings"] == {"mayanCorrelation": 584283, "hdTrueNode": True, "spiritQuadrant": 1}
    assert base.data["compute_sources"] == {"calendars": "zhufang", "humanDesign": "chart_service", "spiritNames": "chart_service"}
    assert base.data["technique_card"]["compute"]["matches_declaration"] is True
    assert base.warnings == []

    maya = _ok(service, "zhufang", {**ZHUFANG, "mayanCorrelation": 584285})
    assert _section(maya.data["snapshot_text"], "玛雅历")[0].startswith("长历 12.18.1.10.9(关联常数 584285);卓尔金 5 Muluk 水")
    mean = _ok(service, "zhufang", {**ZHUFANG, "hdTrueNode": False})
    assert client.calls[-1][1]["hdTrueNode"] == 0
    assert _section(mean.data["snapshot_text"], "人类图")[1].endswith("交点 平交点")
    assert "北交 9.1" in _section(mean.data["snapshot_text"], "人类图")[4] and "北交 9.2" in _section(text, "人类图")[4]
    quad = _ok(service, "zhufang", {**ZHUFANG, "spiritQuadrant": 2})
    assert client.calls[-1][1]["spiritQuadrant"] == 2
    assert _section(quad.data["snapshot_text"], "灵名字母")[2].startswith("象限 2:2 宫 ")
    alcabitius = _ok(service, "zhufang", {**ZHUFANG, "hsys": 1})
    assert client.calls[-1][1]["hsys"] == 1
    assert _section(alcabitius.data["snapshot_text"], "灵名字母")[1] == "十一宫度数主星 木星(双鱼 21.60°)→ ל Lamed"
    # 性别不是诸方杂术的事实：不给也起；给了只是随上游映射进请求体（后端不读，live 用例证明）。
    assert bodies[0]["gender"] == "1"


def test_zhufang_refuses_values_outside_the_upstream_vocabulary(tmp_path: Path) -> None:
    service = _service(tmp_path)
    for bad in ({"mayanCorrelation": 584284}, {"spiritQuadrant": 4}, {"hdTrueNode": "maybe"}):
        with pytest.raises(ToolValidationError) as refused:
            service.run_tool("zhufang", {**ZHUFANG, **bad}, save_result=False)
        assert refused.value.code == "tool.invalid_option" and refused.value.details["field"] in bad, bad
    # 挂载齿轮的写法（'mean'）也认。
    mean = _ok(service, "zhufang", {**ZHUFANG, "hdTrueNode": "mean"})
    assert mean.data["zhufang"]["settings"]["hdTrueNode"] is False


@pytest.mark.parametrize("keep, missing_titles", [
    ((), ["人类图", "灵名字母"]),
    (("humanDesign",), ["灵名字母"]),
    (("spiritNames",), ["人类图"]),
])
def test_zhufang_null_blocks_from_the_backend_are_reported_per_section(tmp_path: Path, keep: tuple[str, ...], missing_titles: list[str]) -> None:
    """后端 build_zhufang 把内部异常吞成 null（HTTP 200）：缺的那段写「未算出」，逐块进 warnings、算源逐块标。

    负向对照：runner 的 `missing = […]` 分支删掉 → `assert len(result.warnings) == 1` 红（ok=true、零提示、少了内容）。"""
    result = _ok(_service(tmp_path, _PartialZhufangClient(keep)), "zhufang", ZHUFANG)
    _clean(result, ZHUFANG_SECTIONS)  # 四段都在：缺的段正文是「未算出。」，不是整段消失
    text = result.data["snapshot_text"]
    for title in ("人类图", "灵名字母"):
        body = _section(text, title)
        assert (body == [f"{title}未算出。"]) is (title in missing_titles), (title, body)
    assert len(result.warnings) == 1 and all(f"[{title}]" in result.warnings[0] for title in missing_titles)
    assert not any(f"[{title}]" in result.warnings[0] for title in ("人类图", "灵名字母") if title not in missing_titles)
    sources = result.data["compute_sources"]
    assert sources["calendars"] == "zhufang"
    assert sources["humanDesign"] == ("chart_service" if "humanDesign" in keep else "unavailable")
    assert sources["spiritNames"] == ("chart_service" if "spiritNames" in keep else "unavailable")
    # 本地两段不受影响。
    assert _section(text, "玛雅历")[0].startswith("长历 12.18.1.10.11")


def test_zhufang_backend_failure_degrades_visibly_starting_runtime_does_not_and_sidereal_is_called_out(tmp_path: Path) -> None:
    """后端取不到：照上游页面，两种历照出、后两段「未算出」+ warnings 带错误码；runtime 正在启动则上抛；
    zodiacal=1 给了却不生效 → 明说。

    负向对照：runner 的 `if remote_error is not None:` 分支删掉 → 第一条 `len(result.warnings) == 1` 红。"""
    result = _ok(_service(tmp_path, _FailingClient("/astroextra/zhufang", "transport.http_error")), "zhufang", ZHUFANG)
    _clean(result, ZHUFANG_SECTIONS)
    text = result.data["snapshot_text"]
    assert _section(text, "人类图") == ["人类图未算出。"] and _section(text, "灵名字母") == ["灵名字母未算出。"]
    assert _section(text, "十三月亮历")[0].startswith("Kin 168:")
    assert len(result.warnings) == 1 and "transport.http_error" in result.warnings[0] and "[人类图]" in result.warnings[0]
    assert result.data["remote"] is None and result.data["compute_sources"]["humanDesign"] == "unavailable"

    starting = _service(tmp_path / "s", _FailingClient("/astroextra/zhufang", "runtime.starting")).run_tool("zhufang", ZHUFANG, save_result=False)
    assert not starting.ok and starting.error.code == "runtime.starting"

    sidereal = _ok(_service(tmp_path / "z"), "zhufang", {**ZHUFANG, "zodiacal": 1})
    assert any("zodiacal=1" in note and "没有生效" in note for note in sidereal.warnings)
    assert sidereal.data["snapshot_text"] == _ok(_service(tmp_path / "t"), "zhufang", ZHUFANG).data["snapshot_text"]


def test_zhufang_bc_birth_keeps_the_backend_sections_and_states_that_the_calendars_are_not_cast(tmp_path: Path) -> None:
    """公元前：上游两种历都不排（段内写明），人类图 / 灵名字母照后端结果出；请求体的纪年随日期（ad -1）。"""
    client = CaptureClient()
    result = _ok(_service(tmp_path, client), "zhufang", {**ZHUFANG, "date": "-0500-03-21", "ad": -1})
    _clean(result, ZHUFANG_SECTIONS)
    text = result.data["snapshot_text"]
    assert _section(text, "玛雅历") == ["公元前日期不排玛雅历。"] and _section(text, "十三月亮历") == ["公元前日期不排十三月亮历。"]
    assert _section(text, "人类图")[0].startswith("类型 ")
    body = [b for endpoint, b in client.calls if endpoint == "/astroextra/zhufang"][0]
    assert body["date"] == "-500/03/21" and body["ad"] == -1


# ───────────────────────────── 路由 ─────────────────────────────

@pytest.mark.parametrize("query, tool", [
    ("帮我排一下藏历", "dongya"), ("看看我的藏占流年八卦", "dongya"), ("蒙古 Zurkhai 年月相位", "dongya"),
    ("用算命学看看天中杀", "dongya"), ("九星气学本命星是什么", "dongya"), ("洛书流年今年走到哪", "dongya"),
    ("排个易卦星盘", "dongya"), ("易卦推运今天在哪一卦", "dongya"), ("东亚诸术全排一遍", "dongya"),
    ("tibetan astrology reading for my birth", "dongya"), ("what is my nine star ki", "dongya"),
    ("sanmeigaku chart please", "dongya"), ("i ching astrology for my natal planets", "dongya"), ("mongolian zurkhai", "dongya"),
    ("我的玛雅历长计历", "zhufang"), ("十三月亮历我的 kin 是多少", "zhufang"), ("帮我看人类图", "zhufang"),
    ("灵名字母怎么投", "zhufang"), ("诸方杂术", "zhufang"), ("我是什么星系印记", "zhufang"),
    ("my human design type", "zhufang"), ("mayan long count for my birthday", "zhufang"), ("dreamspell kin", "zhufang"),
    ("tzolkin day sign", "zhufang"), ("spirit name letters", "zhufang"),
])
def test_every_sub_art_routes_to_its_tool_and_only_to_it(query: str, tool: str) -> None:
    """说任何一个子术的名字都到它所在的那个工具，且只点亮这一个。

    负向对照：六爻规则不摘「易卦星盘」→「排个易卦星盘」得 ['sixyao', 'dongya']；万年历规则不摘「十三月亮历」→
    「十三月亮历我的 kin 是多少」得 ['zhufang', 'calendar_month']。"""
    assert route(DispatchInput(query=query)).tools == [tool]


@pytest.mark.parametrize("query, tools", [
    ("六爻起一卦看工作", ["sixyao"]), ("易卦占卜一下", ["sixyao"]), ("i ching reading", ["sixyao"]),
    ("这个月的月历", ["calendar_month"]), ("万年历", ["calendar_month"]),
    ("今天黄历宜忌，九星值日是什么", ["huangli"]), ("奇门遁甲看八门九星", ["qimen"]),
    ("易卦星盘和六爻一起看", ["sixyao", "dongya"]), ("河洛理数", ["heluo"]), ("八字流年", ["bazi_direct"]),
])
def test_neighbouring_words_keep_their_own_tools(query: str, tools: list[str]) -> None:
    """互斥：「易卦」「月历」「九星」「洛书 / 流年」这些词原来归谁还归谁。"""
    assert route(DispatchInput(query=query)).tools == tools


# ───────────────────────────── 上游源对拍（HOROSA_SOURCE_ROOT）─────────────────────────────

@requires_upstream
def test_upstream_presets_mount_schema_and_page_texts_still_say_what_this_port_assumes() -> None:
    """skill 侧手写的那几样（段表、词表标签来源、流年值域、拒绝文案、请求体抽出件）逐条锚到上游源。"""
    presets = (UPSTREAM_UI / "utils" / "aiExport" / "presets.js").read_text(encoding="utf-8")
    assert "dongya: ['藏历', '藏占', '蒙古 Zurkhai', '算命学', '九星气学', '洛书流年', '易卦星盘']," in presets
    assert "zhufang: ['玛雅历', '十三月亮历', '人类图', '灵名字母']," in presets
    assert "{ key: 'dongya', label: '东亚诸术' }" in presets and "{ key: 'zhufang', label: '诸方杂术' }" in presets
    mount = (UPSTREAM_UI / "utils" / "techniqueMountSettings.js").read_text(encoding="utf-8")
    # 挂载齿轮：流年 1–9999、留空 = 今年；三个诸方口径的选项值。
    assert "{ name: 'dongyaFlowYear', label: '流年(留空 = 今年)', type: 'number', default: '', min: 1, max: 9999" in mount
    for literal in ("{ value: 'common', label: '通行版（默认）' }", "{ value: 'fajue', label: '法诀版' }",
                    "{ value: 'horizon', label: '按地平上下（默认）' }", "{ value: 'upper', label: '恒合上卦' }",
                    "{ value: 'lower', label: '恒合下卦' }", "{ value: 584283, label: '584283（默认）' }",
                    "{ value: 'true', label: '真交点（默认）' }", "{ value: 'mean', label: '平交点' }",
                    "{ value: 1, label: '1 · 4 · 7 · 10 宫（默认）' }"):
        assert literal in mount, literal
    page = (UPSTREAM_UI / "components" / "dongya" / "EastAsiaMain.js").read_text(encoding="utf-8")
    tool = (CORE_JS / "src" / "tools" / "dongya.js").read_text(encoding="utf-8")
    for sentence in ("公元前出生暂不排东亚诸术:干支历只覆盖公元 1 年以后。", "这份出生资料排不出东亚诸术(日期超出干支历范围)。"):
        assert sentence in page and sentence in tool, sentence
    assert "<InputNumber min={1} max={9999} value={this.state.flowYear" in page
    # 无头挂载取本命盘、取不到只少那一段；诸方取不到写未算出——本仓 runner 的降级口径照这两处。
    regen = (UPSTREAM_UI / "utils" / "aiAnalysisContext" / "regenChart.js").read_text(encoding="utf-8")
    assert "try{ chartObj = await fetchChartResultForRecord(record); }catch(e){ chartObj = null; }" in regen
    assert "{ fenyeVersion: record.dongyaFenyeVersion, ichingMerge: record.dongyaIchingMerge, flowYear: record.dongyaFlowYear }" in regen
    assert "const zfRemote = await fetchZhufangRemote(zfParams, zfSettings);" in regen
    # 请求体抽出件：两处纯逻辑在上游网络件里逐字存在（另有 vendor_manifest 的 derived_sha256 看守整份文件）。
    remote = (UPSTREAM_UI / "utils" / "zhufangRemote.js").read_text(encoding="utf-8")
    extract = (CORE_JS / "src" / "vendor" / "zhufang" / "zhufangRequest.js").read_text(encoding="utf-8")
    body = "{ ...(params || {}), hdTrueNode: s.hdTrueNode === false || `${s.hdTrueNode}` === '0' || s.hdTrueNode === 'mean' ? 0 : 1, spiritQuadrant: Number(s.spiritQuadrant) || 1 }"
    accepted = "return res && (res.humanDesign || res.spiritNames) ? res : null;"
    for expression in (body, accepted, "const res = data && (data.Result || data);"):
        assert expression in remote and expression in extract, expression
    # 后端把两块的异常各自吞成 null（runner 的逐块 warnings 就是为它写的）。
    backend = (UPSTREAM_WEB / "astropy" / "astrostudy" / "zhufang_arts.py").read_text(encoding="utf-8")
    assert "out['humanDesign'] = None" in backend and "out['spiritNames'] = None" in backend
    assert "params['zodiacal'] = 0" in backend  # 灵名字母固定回归黄道 → zodiacal=1 的 warning


@requires_upstream
def test_copied_upstream_goldens_still_equal_the_upstream_files() -> None:
    upstream = json.loads((UPSTREAM_UI / "utils" / "__tests__" / "fixtures" / "tibetanCalendarGolden.json").read_text(encoding="utf-8"))
    assert TIBETAN["reference"] == upstream["reference"] and TIBETAN["lonEast"] == upstream["lonEast"]
    spirit = json.loads((FIXTURES / "sync314_mingother_spirit_names_golden.json").read_text(encoding="utf-8"))
    upstream_spirit = json.loads((UPSTREAM_WEB / "astropy" / "tests" / "data" / "golden_spirit_names.json").read_text(encoding="utf-8"))
    assert {key: spirit[key] for key in upstream_spirit} == upstream_spirit
