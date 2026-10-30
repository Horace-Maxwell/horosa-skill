"""上游 v3.12.0 / v3.13.0（Horosa-Public 965af0f4）西占星运族同步：129 年系统 / 年龄推进点 / 界推运 / Balbillus /
多重回归 / 「此刻」按本盘时区。

权威：
- 129 年系统：上游 v3.13.0 删了后端 astrostudy/yearsystem129.py（/chart 不再回 predictives.yearsystem129），改由前端
  utils/yearSystem129.js 单源计算——本仓 verbatim vendor 为 horosa-core-js/src/vendor/astroextra/yearSystem129.js
  （vendor_manifest.json 逐字看守），经 tools/progextra.js 调用。金标 = 真 node 引擎在 fixtures/chart_1998_predictive.json
  上的输出；期长断言按上游算法注释（yearSystem129.js:14-21）手算。
- 年龄推进点 / 界推运：上游 AstroAgePoint.js / AstroDistributions.js 的 buildXxxSnapshotFromResult（v3.13.0 重写），verbatim
  vendor（truncate_before 剥 React 尾部）；后端结果 = vendored v3.13.0 chart 服务实抓（fixtures/sync313_predictive_live.json）。
- 「此刻」：上游 components/comp/DateTime.js:26-46 nowForChart / wallClockForChart、utils/returnPickerSeed.js、
  astroAiSnapshot.js birthInstantMsInZone。
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fakes import FakeClient, FakeJsClient
from node_esm import run_node_esm

from horosa_skill import service as S
from horosa_skill.config import Settings
from horosa_skill.engine.js_client import HorosaJsEngineClient
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService, _clock
from horosa_skill.service.runners.predictive import PredictiveRunners
from horosa_skill.service.text import predictive as T

_FIXTURES = Path(__file__).parent / "fixtures"
# chart 服务把 /chart 挂在根路径（service._chart_server_endpoint），桩按真实路径覆写。
CHART = S._chart_server_endpoint("/chart")
_CORE_JS = Path(__file__).resolve().parents[1] / "horosa-core-js"
LIVE = json.loads((_FIXTURES / "sync313_predictive_live.json").read_text(encoding="utf-8"))
BIRTH = {
    "date": "1995-06-03", "time": "05:30:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28",
    "hsys": 0, "zodiacal": 0, "agent_confirmed_settings": True,
}
# 冻结「此刻」= 东八区 2026-10-30 12:00（本机钟面随机器时区换算，见 _frozen）。
NOW_UTC = datetime(2026, 10, 30, 4, 0, 0, tzinfo=timezone.utc)
NOW_MS = int(NOW_UTC.timestamp() * 1000)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        server_root="http://127.0.0.1:9", runtime_root=tmp_path / "runtime",
        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs",
    )


def _js(tmp_path: Path) -> HorosaJsEngineClient:
    return HorosaJsEngineClient(_settings(tmp_path))


def _progextra(tmp_path: Path, technique: str, chart: dict, options: dict | None = None, result: dict | None = None) -> dict:
    payload = {"technique": technique, "chart": chart, "options": options or {}, "now_ms": NOW_MS}
    if result is not None:
        payload["result"] = result
    out = _js(tmp_path).run("progextra", payload)
    assert out["data"]["ok"] is True, out
    return out


class RecordingClient(FakeClient):
    def __init__(self, overrides: dict | None = None) -> None:
        super().__init__()
        self.calls: list[tuple[str, dict]] = []
        self.overrides = overrides or {}

    def call(self, endpoint: str, payload: dict) -> dict:
        self.calls.append((endpoint, dict(payload)))
        if endpoint in self.overrides:
            value = self.overrides[endpoint]
            return json.loads(json.dumps(value(payload) if callable(value) else value))
        return super().call(endpoint, payload)

    def payloads(self, endpoint: str) -> list[dict]:
        return [payload for called, payload in self.calls if called == endpoint]


class RecordingJs(FakeJsClient):
    def __init__(self, real: HorosaJsEngineClient | None = None) -> None:
        super().__init__()
        self.real = real
        self.runs: list[tuple[str, dict]] = []

    def run(self, tool_name: str, payload: dict) -> dict:
        self.runs.append((tool_name, json.loads(json.dumps(payload))))
        if self.real is not None and tool_name == "progextra":
            return self.real.run(tool_name, payload)
        return super().run(tool_name, payload)


def _service(tmp_path: Path, client=None, js=None) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9999", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    return HorosaSkillService(settings, client=client or RecordingClient(), store=MemoryStore(settings), js_client=js or RecordingJs())


@pytest.fixture()
def frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    local_now = NOW_UTC.astimezone().replace(tzinfo=None)  # 本机钟面（_clock.now() 的语义）

    class _Frozen(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001 - datetime.now 签名
            return local_now if tz is None else NOW_UTC.astimezone(tz)

    monkeypatch.setattr(_clock, "datetime", _Frozen)


def _section(text: str, title: str) -> str:
    head = f"[{title}]\n"
    start = text.index(head) + len(head)
    end = text.find("\n\n[", start)
    return text[start:] if end < 0 else text[start:end]


# ─────────────────────────── 129 年系统（vendored utils/yearSystem129.js）───────────────────────────


def _chart1998() -> dict:
    return json.loads((_FIXTURES / "chart_1998_predictive.json").read_text(encoding="utf-8"))


def test_yearsystem129_golden_is_the_vendored_engine_output(tmp_path: Path) -> None:
    # 金标重生成法：真 node 引擎（horosa-core-js progextra → vendored yearSystem129.js）在 chart_1998_predictive.json 上、
    # 缺省 opts 的 snapshot_text.strip()（见 tests/fixtures/golden_yearsystem129.txt；上游 v3.13.0 前的旧金标读后端字段）。
    out = _progextra(tmp_path, "yearsystem129", _chart1998())
    assert out["snapshot_text"].strip() == (_FIXTURES / "golden_yearsystem129.txt").read_text(encoding="utf-8")


def test_yearsystem129_periods_follow_the_upstream_algorithm(tmp_path: Path) -> None:
    text = _progextra(tmp_path, "yearsystem129", _chart1998())["snapshot_text"]
    lines = text.splitlines()
    assert lines[0] == "[129年系统表格]"
    # yearSystem129.js:156 首行 + yearSystem129OptionsLine（缺省 Sun / zodiacal / solar / days，YS129_DEFAULT_OPTS :46）。
    assert lines[1] == (
        "七星各管其小年（土 30 / 木 12 / 火 15 / 日 19 / 金 8 / 水 20 / 月 25，合 129 年）。"
        "起始星=日、次序=黄道顺序（本命黄经递增）、年制=回归年（365.2422 日）、子限=日数法（子星小年 × ⌊2.5 × 主星小年⌋ 日，不填满主限）。"
    )
    assert "| 主限 | 子限 | 起始日期 | 时长(年) |" in lines
    # 手算（yearSystem129.js:18-21）：日主限 19 年、起于出生日；日数法子限 日 = 19 × ⌊2.5×19⌋ = 893 日 = 2.445 年 → toFixed 2.44。
    assert "| 日(19.00年,起 1998-02-20) | 日 | 1998-02-20 | 2.44 |" in lines
    # 第二个主限是黄经序上紧随太阳的木星（1998-02-20 盘：日 双鱼 1°，木 双鱼 9°），起于 19 年后的出生纪念日附近。
    assert "| 木(12.00年,起 2017-02-20) | 木 | 2017-02-20 | 0.99 |" in lines


def test_yearsystem129_options_change_the_result(tmp_path: Path) -> None:
    text = _progextra(
        tmp_path, "yearsystem129", _chart1998(),
        {"startPlanet": "sect", "order": "chaldean", "yearType": "hellenistic", "subRule": "equal"},
    )["snapshot_text"]
    # 1998-02-20 20:48 上海 = 夜生盘 → 区分光体起月；迦勒底序月之后是土；360 日年；七等分 25/7 = 3.57。
    assert "起始星=区分光体 → 月、次序=迦勒底序（土木火日金水月）、年制=埃及 / 希腊化年（360 日）、子限=七等分（主限 ⁄ 7）" in text
    assert "| 月(25.00年,起 1998-02-20) | 月 | 1998-02-20 | 3.57 |" in text
    assert "| 土(30.00年," in text


def test_yearsystem129_runner_uses_the_js_engine_and_forwards_ys129_options(tmp_path: Path, frozen: None) -> None:
    js = RecordingJs(_js(tmp_path))
    client = RecordingClient({CHART: _chart1998()})
    result = _service(tmp_path, client, js).run_tool(
        "yearsystem129",
        {**BIRTH, "ys129StartPlanet": "sect", "ys129Order": "chaldean", "ys129YearType": "bija", "ys129SubRule": "proportional"},
        save_result=False,
    )
    assert result.ok is True, result.error
    sent = [p for tool, p in js.runs if tool == "progextra"][-1]
    assert sent["technique"] == "yearsystem129"
    # regenChart.js:263-267：齿轮键 ys129* → builder opts 的 startPlanet/order/yearType/subRule。
    assert sent["options"] == {"startPlanet": "sect", "order": "chaldean", "yearType": "bija", "subRule": "proportional"}
    assert sent["now_ms"] == NOW_MS
    text = result.data["snapshot_text"]
    assert "年制=Bija 修正年（366.2564 日）、子限=比例法（主限 × 子星小年 ⁄ 129，填满主限）" in text
    # builder 自算的定位行进 [当前时点]（上游 buildCurrentMomentLines(chartObj, extraLines)）。
    moment = _section(text, "当前时点").splitlines()
    assert any(line.startswith("当前主限：") for line in moment), moment
    # 旧 runner 读 /chart predictives.yearsystem129（上游 v3.13.0 已无）→ 恒「本盘无数据」。负向对照：该串不得再出现。
    assert "本盘无 129 年系统数据" not in text
    bad = _service(tmp_path, client, js).run_tool("yearsystem129", {**BIRTH, "ys129SubRule": "cycle"}, save_result=False)
    assert bad.ok is False and bad.error.code == "tool.predictive_invalid_option"


# ─────────────────────────── 年龄推进点 / 界推运（vendored buildXxxSnapshotFromResult）───────────────────────────

_NATAL = {"params": {"birth": "1995-06-03 05:30:00", "zone": "+08:00"}, "chart": {}}


def test_agepoint_builder_prints_upstream_v313_layout(tmp_path: Path) -> None:
    out = _progextra(tmp_path, "agepoint", _NATAL, {}, LIVE["agepoint"]["default"])
    lines = out["snapshot_text"].splitlines()
    assert lines[0] == "[年龄推进点（Age Point / Huber）]"
    # AstroAgePoint.js:84 首行 + agePointOptions.apSettingsLine（ap.settings 回显的出厂值）。
    assert lines[1] == (
        "年龄点自上升点起逐宫顺行，每宫 6 年、72 年回到上升。推进方式=Koch 宫（每宫 6 年，宫内匀速）、事件=全部点 × 五种相位、"
        "年长=回归年（365.2422 日）、年限=72 岁。年龄点经过本命点或其相位点的岁数为人生关键节点。"
    )
    # 关键岁数：后端 crossings（aspect 90 side S → 「四分·左」，apAspectText）+ 日期。
    assert lines[3].startswith("关键岁数（精确穿越岁数）：0.76岁四分·左土(1996-03-06)；2.91岁六合·右天底(1998-05-01)；")
    assert "| 年龄 | 日期 | 落座 | 宫 | 事件（穿越岁数） |" in lines
    assert "| 0岁 | 1995-06-03 | 双子 20.66° | 1宫 | 四分·左土(0.76岁) |" in lines
    # 定位行（Date.now 钉在 NOW_MS = 2026-10-30）：31 岁行 + 下一事件 31.63 岁合冥（2027-01-18）。
    assert out["moment_lines"] == [
        "当前年龄点：31岁 落天蝎 25.72°，第6宫，合冥(31.63岁)、六合·右天(31.89岁)",
        "下一事件：31.63岁合冥（2027-01-18）",
    ]


def test_progextra_pins_the_builders_now_to_the_service_clock(tmp_path: Path) -> None:
    # tools/progextra.js 在 builder 调用期间把 Date.now 钉到 payload.now_ms（Python `_clock` 的此刻）：定位行随它走，
    # 而不是随跑测试的真实日期。2040-01-01 → 44 岁行（真实「今天」给不出这一行）。
    out = _js(tmp_path).run("progextra", {
        "technique": "agepoint", "chart": _NATAL, "options": {}, "result": LIVE["agepoint"]["default"],
        "now_ms": int(datetime(2040, 1, 1, tzinfo=timezone.utc).timestamp() * 1000),
    })
    assert out["moment_lines"] == [
        "当前年龄点：44岁 落摩羯 23.73°，第8宫，六合·右土(44.03岁)、合海(44.38岁)",
        "下一事件：45.31岁六合·左冥（2040-09-23）",
    ]


def test_agepoint_settings_echo_changes_the_header(tmp_path: Path) -> None:
    out = _progextra(tmp_path, "agepoint", _NATAL, {"apMethod": "equal5", "apEvents": "conj", "apMaxAge": 100}, LIVE["agepoint"]["equal5_conj_100"])
    text = out["snapshot_text"]
    assert "推进方式=等速（自上升每年 5°）、事件=只报合七星、年长=回归年（365.2422 日）、年限=100 岁" in text
    assert "关键岁数（精确穿越岁数）：8.09岁合月(2003-07-06)；14.63岁合火(2010-01-18)" in text
    assert "| 100岁 |" in text


def test_distributions_builder_prints_partner_periods(tmp_path: Path) -> None:
    out = _progextra(tmp_path, "distributions", _NATAL, {}, LIVE["dist"]["default"])
    text = out["snapshot_text"]
    lines = text.splitlines()
    assert lines[0] == "[界推运（分配法 / Distributions）]"
    # AstroDistributions.js:80 首行：distSettingsLine + 发放点黄经（distSettings.releaserLon 80.6562 → toFixed 2）。
    assert "发放点=上升、时间算法=上升时间（星座内均匀，古典）、年长=回归年（365.2422 日）、年限=100 年（黄经 80.66°）。" in lines[1]
    assert "| 分配星 | 界(座) | 起始岁 | 时长(年) | 起 | 止 | 期内伙伴星 |" in lines
    assert "| 火 | 双子 | 0.00 | 3.32 | 1995-06-03 05:30:00 | 1998-09-28 06:25:30 | 土四分·左 |" in lines
    # 新 [伙伴星期] 段（distPartners）。
    partners = _section(text, "伙伴星期").splitlines()
    assert partners[0] == "| 伙伴星 | 相位点 | 起始岁 | 时长(年) | 起 | 止 |"
    assert "| 土 | 四分·左（83.83°） | 3.16 | 10.54 | 1998-07-29 15:16:36 | 2009-02-09 17:06:44 |" in partners
    assert out["moment_lines"] == [
        "当前分配星：木（巨蟹 界，2026-08-04 15:01:02 ~ 2034-08-28 10:03:59）",
        "当前伙伴星：火六合·右（2009-02-09 17:06:44 ~ 2028-05-12 14:34:29）",
    ]
    other = _progextra(
        tmp_path, "distributions", _NATAL,
        {"distReleaser": "MC", "distMethod": "qisma", "distYear": "julian", "distYears": 60}, LIVE["dist"]["mc_qisma_julian_60"],
    )["snapshot_text"]
    assert "发放点=天顶、时间算法=Qisma（每度 1 年）、年长=儒略年（365.25 日）、年限=60 年（黄经 332.90°）" in other


@pytest.mark.parametrize(
    ("tool", "endpoint", "opts", "sent"),
    [
        ("agepoint", "/predict/agepoint", {"apMethod": "equal5", "apEvents": "full", "apMaxAge": "100"}, {"apMethod": "equal5", "apMaxAge": 100}),
        ("distributions", "/predict/dist", {"distReleaser": "Pars Fortuna", "distYear": "egyptian", "distYears": 100},
         {"distReleaser": "Pars Fortuna", "distYear": "egyptian"}),
    ],
)
def test_runner_forwards_only_non_default_option_keys(tmp_path: Path, tool: str, endpoint: str, opts: dict, sent: dict) -> None:
    client = RecordingClient()
    result = _service(tmp_path, client).run_tool(tool, {**BIRTH, **opts}, save_result=False)
    assert result.ok is True, result.error
    body = client.payloads(endpoint)[-1]
    keys = set(T_OPTION_KEYS[tool])
    # 上游 apRequestParams / distRequestParams：请求体只带与出厂值不同的键（缺省请求与旧版逐字节相同）。
    assert {k: body[k] for k in keys if k in body} == sent
    assert result.data["options"] == {k: (int(v) if k in ("apMaxAge", "distYears") else v) for k, v in opts.items()}


T_OPTION_KEYS = {k: tuple(v) for k, v in PredictiveRunners._PREDICT_RESULT_OPTION_DOMAINS.items()}


@pytest.mark.parametrize(("tool", "opts"), [("agepoint", {"apYear": "julian"}), ("distributions", {"distYears": 90}), ("agepoint", {"apMaxAge": 90})])
def test_bad_options_fail_loudly(tmp_path: Path, tool: str, opts: dict) -> None:
    result = _service(tmp_path).run_tool(tool, {**BIRTH, **opts}, save_result=False)
    assert result.ok is False and result.error.code == "tool.predictive_invalid_option"


@pytest.mark.parametrize(("tool", "endpoint", "empty"), [("agepoint", "/predict/agepoint", {"agepoint": {"points": []}}), ("distributions", "/predict/dist", {"dist": []})])
def test_empty_backend_timeline_is_a_structured_error_not_a_template(tmp_path: Path, tool: str, endpoint: str, empty: dict) -> None:
    result = _service(tmp_path, RecordingClient({endpoint: empty})).run_tool(tool, dict(BIRTH), save_result=False)
    assert result.ok is False and result.error.code == f"tool.{tool}_empty"


def test_agepoint_runner_end_to_end_with_real_engine(tmp_path: Path, frozen: None) -> None:
    client = RecordingClient({"/predict/agepoint": LIVE["agepoint"]["default"]})
    result = _service(tmp_path, client, RecordingJs(_js(tmp_path))).run_tool("agepoint", dict(BIRTH), save_result=False)
    assert result.ok is True, result.error
    text = result.data["snapshot_text"]
    assert text.index("[起盘信息]") < text.index("[年龄推进点（Age Point / Huber）]") < text.index("[当前时点]") < text.index("[方法说明]")
    moment = _section(text, "当前时点").splitlines()
    assert moment[-2:] == ["当前年龄点：31岁 落天蝎 25.72°，第6宫，合冥(31.63岁)、六合·右天(31.89岁)", "下一事件：31.63岁合冥（2027-01-18）"]
    assert _section(text, "方法说明").splitlines()[0].startswith("年龄推进点：年龄点自上升点起逐宫顺行,每宫 6 年、72 年回到上升。")


# ─────────────────────────── 值域与 vendored 引擎互锚 ───────────────────────────


def _node_json(expr_module: str) -> dict:
    return json.loads(run_node_esm(expr_module, cwd=_CORE_JS, timeout=60))


def test_python_option_domains_equal_the_vendored_engine_tables() -> None:
    js = _node_json(
        "import * as Y from './src/vendor/astroextra/yearSystem129.js';"
        "import * as B from './src/vendor/astroextra/balbillus.js';"
        "import * as A from './src/vendor/utils/agePointOptions.js';"
        "import * as D from './src/vendor/utils/distributionsOptions.js';"
        "import { TIME_LORD_YEAR_TYPES } from './src/vendor/utils/timeLordYears.js';"
        "console.log(JSON.stringify({years: Object.keys(TIME_LORD_YEAR_TYPES), ysStart: Y.YS129_START_OPTIONS,"
        " ysOrder: Object.keys(Y.YS129_ORDERS), ysSub: Object.keys(Y.YS129_SUB_RULES), ysDefault: Y.YS129_DEFAULT_OPTS,"
        " bSub: Object.keys(B.BALBILLUS_SUB_RULES), bMode: Object.keys(B.BALBILLUS_MODES), bYears: Object.keys(B.BALBILLUS_YEAR_TYPES),"
        " bDefault: B.BALBILLUS_DEFAULT_OPTS,"
        " ap: {apMethod: A.AP_METHODS.map(o=>o.value), apEvents: A.AP_EVENTS.map(o=>o.value), apYear: A.AP_YEARS.map(o=>o.value), apMaxAge: A.AP_SPANS},"
        " apDefault: A.AP_DEFAULTS,"
        " dist: {distReleaser: D.DIST_RELEASERS.map(o=>o.value), distMethod: D.DIST_METHODS.map(o=>o.value),"
        " distYear: D.DIST_YEARS.map(o=>o.value), distYears: D.DIST_SPANS}, distDefault: D.DIST_DEFAULTS}))"
    )
    assert tuple(js["years"]) == T._TIME_LORD_YEAR_TYPES
    ys = PredictiveRunners._PROGEXTRA_OPTION_DOMAINS["yearsystem129"]
    assert ys == {"ys129StartPlanet": tuple(js["ysStart"]), "ys129Order": tuple(js["ysOrder"]),
                  "ys129YearType": tuple(js["years"]), "ys129SubRule": tuple(js["ysSub"])}
    bal = PredictiveRunners._PROGEXTRA_OPTION_DOMAINS["balbillus"]
    assert bal["subRule"] == tuple(js["bSub"]) and bal["mode"] == tuple(js["bMode"]) and bal["yearType"] == tuple(js["bYears"])
    domains = PredictiveRunners._PREDICT_RESULT_OPTION_DOMAINS
    assert {k: tuple(v) for k, v in js["ap"].items()} == domains["agepoint"]
    assert {k: tuple(v) for k, v in js["dist"].items()} == domains["distributions"]
    assert js["apDefault"] == PredictiveRunners._PREDICT_RESULT_OPTION_DEFAULTS["agepoint"]
    assert js["distDefault"] == PredictiveRunners._PREDICT_RESULT_OPTION_DEFAULTS["distributions"]


def test_balbillus_new_year_types_and_sub_rules_reach_the_builder(tmp_path: Path) -> None:
    js = RecordingJs()
    client = RecordingClient({CHART: _chart1998()})
    result = _service(tmp_path, client, js).run_tool("balbillus", {**BIRTH, "yearType": "sidereal", "subRule": "cycle"}, save_result=False)
    assert result.ok is True, result.error
    assert [p for t, p in js.runs if t == "progextra"][-1]["options"] == {"yearType": "sidereal", "subRule": "cycle"}
    once = _progextra(tmp_path, "balbillus", _chart1998())["snapshot_text"]
    cycle = _progextra(tmp_path, "balbillus", _chart1998(), {"yearType": "sidereal", "subRule": "cycle"})["snapshot_text"]
    assert once != cycle and "恒星年（365.2564 日）" in cycle and "循环（一轮接一轮直到父期末）" in cycle
    bad = _service(tmp_path, client, js).run_tool("balbillus", {**BIRTH, "subRule": "days"}, save_result=False)
    assert bad.ok is False and bad.error.code == "tool.predictive_invalid_option"


# ─────────────────────────── 多重回归（AstroExtraReturns.js v3.13.0）───────────────────────────


def test_extrareturns_marks_unfound_returns_and_node_type(tmp_path: Path) -> None:
    def returns(payload: dict) -> dict:
        rows = [{"which": 1, "date": "2013-01-10", "time": "08:00:00", "passes": []},
                {"which": 2, "found": False, "passes": []}]
        return {"returns": rows, "natalLon": 123.456, "body": payload.get("body")}

    client = RecordingClient({"/astroextra/planetreturn": returns})
    text = _service(tmp_path, client).run_tool("extrareturns", {**BIRTH, "westNodeType": "true"}, save_result=False).data["snapshot_text"]
    body = _section(text, "多重回归").splitlines()
    # AstroExtraReturns.js:74-82：found===false → 「范围内未找到」/ 时刻「-」；月交行标（真交点）（westNodeType 'true'）。
    assert body[0] == "土星返照（≈29.5 年）：第1回 2013-01-10，第2回 范围内未找到；时刻：第1回 08:00:00，第2回 -；本命黄经 123.5°"
    assert body[2].startswith("月交返照（真交点）（≈18.6 年）：")
    mean = _service(tmp_path, RecordingClient({"/astroextra/planetreturn": returns})).run_tool("extrareturns", dict(BIRTH), save_result=False)
    assert "月交返照（平交点）（≈18.6 年）" in mean.data["snapshot_text"]


# ─────────────────────────── 「此刻」按本盘时区（DateTime.nowForChart / wallClockForChart）───────────────────────────


def test_now_for_chart_and_wall_clock_for_chart_semantics(frozen: None) -> None:
    # 冻结真实此刻 = 2026-10-30 04:00 UTC。
    assert T._now_for_chart("+08:00") == datetime(2026, 10, 30, 12, 0, 0)
    assert T._now_for_chart("-05:00") == datetime(2026, 10, 29, 23, 0, 0)
    assert T._now_for_chart("+05:45:30") == datetime(2026, 10, 30, 9, 45, 30)
    # 不合法 / 缺 → nowForChart 回落 +08:00 钟面（new DateTime()），wallClockForChart 回落本机钟面（new Date()）。
    assert T._now_for_chart("UTC+8") == datetime(2026, 10, 30, 12, 0, 0)
    assert T._wall_clock_for_chart(None) == NOW_UTC.astimezone().replace(tzinfo=None)
    assert T._wall_clock_for_chart("-10:00") == datetime(2026, 10, 29, 18, 0, 0)
    assert T._today_for_chart("-10:00") == "2026-10-29"
    assert T._planetaryarc_default_datetime(zone="-10:00") == "2026-10-30 18:00:00"


def test_return_picker_seed_mirrors_upstream() -> None:
    now = datetime(2026, 10, 30, 12, 0, 0)
    assert T._return_picker_seed("1995-06-03 05:30:00", now) == "2026-06-03 05:30"
    # returnPickerSeed.js:15：2/29 生人、今年无 2/29 → 3/1（旧实现拼出不存在的 2026-02-29）。
    assert T._return_picker_seed("2000-02-29 08:15:00", now) == "2026-03-01 08:15"
    assert T._return_picker_seed("2000-02-29 08:15", datetime(2028, 1, 1)) == "2028-02-29 08:15"
    # 公元前 / 五位年按日期串解析（旧写法 今年 + birth[4:] 拼出「20263 年」）。
    assert T._return_picker_seed("-0003-03-10 10:00:00", now) == "2026-03-10 10:00"
    assert T._return_picker_seed("12000/01/01", now) == "2026-01-01 12:00"
    assert T._return_picker_seed("garbage", now) == "2026-10-30 12:00"


@pytest.mark.parametrize("tool", ["solarreturn", "profection"])
def test_period_predictive_default_now_follows_the_chart_zone(tmp_path: Path, frozen: None, tool: str) -> None:
    client = RecordingClient()
    birth = {**BIRTH, "zone": "-05:00", "date": "2000-02-29", "time": "08:15:00"}
    _service(tmp_path, client).run_tool(tool, birth, save_result=False)
    sent = client.payloads(f"/predict/{tool}")[-1]
    # 真实此刻 04:00 UTC = 纽约 2026-10-29 23:00（旧实现取东八区 2026-10-30 12:00）。
    expected = "2026-03-01 08:15" if tool == "solarreturn" else "2026-10-29 23:00"
    assert sent["datetime"] == expected and sent["dirZone"] == "-05:00"


def test_ephemeris_and_returntimeline_defaults_use_the_chart_zone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # 此刻 = 2026-12-31 20:00 UTC：+14:00（基里巴斯）已是 2027-01-01 10:00，西半球 / 东八区都还在 2026 年
    # ——本机钟面（旧实现）在任何本机时区下都给不出 2027，负向对照因此与跑测试的机器无关。
    instant = datetime(2026, 12, 31, 20, 0, 0, tzinfo=timezone.utc)

    class _Frozen(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001
            return instant.astimezone().replace(tzinfo=None) if tz is None else instant.astimezone(tz)

    monkeypatch.setattr(_clock, "datetime", _Frozen)
    client = RecordingClient()
    service = _service(tmp_path, client)
    service.run_tool("ephemeris", {**BIRTH, "zone": "+14:00"}, save_result=False)
    sent = client.payloads("/astroextra/ephemeris")[-1]
    assert sent["startDate"] == "2027-01-01" and sent["endDate"] == "2027-04-01"
    service.run_tool("returntimeline", {**BIRTH, "zone": "+14:00"}, save_result=False)
    assert client.payloads("/astroextra/returns")[-1]["startYear"] == 2027
    service.run_tool("returntimeline", {**BIRTH, "zone": "-10:00"}, save_result=False)
    assert client.payloads("/astroextra/returns")[-1]["startYear"] == 2026


def test_current_age_reads_the_birth_wall_clock_in_the_chart_zone(frozen: None) -> None:
    # birthInstantMsInZone：出生钟面按本盘时区解读。1995-06-05 05:30 按 -10:00 = 15:30 UTC、按 +14:00 = 前一日 15:30 UTC；
    # 此刻 2026-10-30 04:00 UTC → 两者差 24 小时，选这个出生日让两位小数恰好跨进位（31.40 / 31.41）。
    def shown(birth_utc: datetime) -> str:
        age = (NOW_UTC - birth_utc).total_seconds() / (365.2425 * 86400)
        return re.sub(r"\.?0+$", "", f"{round(age * 100) / 100:.2f}")

    west = shown(datetime(1995, 6, 5, 15, 30, tzinfo=timezone.utc))
    east = shown(datetime(1995, 6, 4, 15, 30, tzinfo=timezone.utc))
    assert (west, east) == ("31.4", "31.41")
    payload = {**BIRTH, "date": "1995-06-05"}
    assert f"盘主当前年龄：{west} 岁" in T._predictive_common_sections_text("agepoint", {**payload, "zone": "-10:00"}).splitlines()
    assert f"盘主当前年龄：{east} 岁" in T._predictive_common_sections_text("agepoint", {**payload, "zone": "+14:00"}).splitlines()


def test_birth_instant_in_zone_falls_back_to_machine_zone_for_bad_zones() -> None:
    wall = datetime(1995, 6, 3, 5, 30)
    assert T._birth_instant_in_zone(wall, "+08:00") == datetime(1995, 6, 2, 21, 30, tzinfo=timezone.utc)
    assert T._birth_instant_in_zone(wall, "bogus") == wall.astimezone()
    assert T._chart_zone_seconds("+05:45:30") == 5 * 3600 + 45 * 60 + 30 and T._chart_zone_seconds("+8:00") is None
    assert T._chart_zone_seconds(timedelta(hours=1)) is None


# ─────────────────────────── 十年期 [时间口径]（utils/decennials.js:577-582）───────────────────────────


def test_decennials_actual_calendar_label_is_the_julian_year_wording(tmp_path: Path) -> None:
    from horosa_skill.engine.decennials import DECENNIAL_CALENDAR_ACTUAL

    client = RecordingClient({CHART: _chart1998()})
    result = _service(tmp_path, client).run_tool("decennials", {**BIRTH, "calendarType": DECENNIAL_CALENDAR_ACTUAL}, save_result=False)
    assert result.ok is True, result.error
    # 上游 getDecennialCalendarLabel：1461/1440 = 儒略年（旧文案「按回归年换算」是错的，上游 [Q-176/T-116c] 已改）。
    assert "时间口径：365.25天/年（儒略年；回归年为 365.2422 天）" in result.data["snapshot_text"].splitlines()


# ─────────────────────────── [起盘信息] 极区天顶行（astroAiSnapshot.js:1955-1957）───────────────────────────


def test_predictive_birth_lines_add_the_polar_mc_note_after_house_system(tmp_path: Path) -> None:
    from horosa_skill import predictive_text as P
    from horosa_skill.astro_rulers import POLAR_MC_NOTE

    wrap = {"params": {"birth": "1990-06-21 12:00:00", "zone": "+02:00", "hsys": 1},
            "chart": {"isDiurnal": True, "houses": [{"id": "House1"}, {"id": "House10", "polarMc": "below"}]}}
    lines = P.build_predictive_birth_lines(wrap)
    assert lines[lines.index(next(line for line in lines if line.startswith("宫制："))) + 1] == POLAR_MC_NOTE
    assert lines[-1] == "盘型：日生盘"
    assert POLAR_MC_NOTE not in P.build_predictive_birth_lines({**wrap, "chart": {"isDiurnal": True, "houses": [{"id": "House10"}]}})
    # runner 的本命盘头只带 houses[].polarMc 一个字段，[起盘信息] 照样出这一行。
    natal = {"params": wrap["params"], "chart": {"isDiurnal": True, "hsys": "Placidus", "houses": wrap["chart"]["houses"], "objects": []}}
    client = RecordingClient({CHART: natal, "/predict/agepoint": LIVE["agepoint"]["default"]})
    text = _service(tmp_path, client).run_tool("agepoint", dict(BIRTH), save_result=False).data["snapshot_text"]
    assert POLAR_MC_NOTE in _section(text, "起盘信息").splitlines()
