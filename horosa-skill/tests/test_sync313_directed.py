"""上游 v3.13.0 之后（Horosa-Public 219d8a67 + 8964bfd5）推运图族四法：演进推运 Néroman / 推运图 Bezza / 周日小限 Jay / 双黄道 Michon。

权威：
- 计算：后端 astrostudy/directed_figures.py（/astroextra/neroman · bezzafigure · jayprofection · michon）。回包 = vendored 实例实抓
  （tests/fixtures/sync313_directed_live.json；请求体就是 skill runner 自己发的那一份，withChart 0）。
- 排版：上游 utils/directedFigures.js buildDirectedFigureText 经 components/astro/AstroDirectedFigures.js snapshotText；请求体映射
  directedFigureRequestFields ∘ directedFigureOptsFromSettings，合并规则在 buildDirectedFigureSnapshotText。
- 金标 = **上游源本身**在 node 里跑出来的（`_upstream_goldens()`：上游 directedFigures.js 直接 import，AstroDirectedFigures.js 用上游
  @babel 抽出三个纯函数，fetch 换成「回放夹具回包 + 记下请求体」），存进夹具的 `upstream` 键；`test_fixture_matches_upstream` 在
  HOROSA_SOURCE_ROOT 可用时重跑一遍，夹具与上游漂移即红。

负向对照（均实跑，见各条 docstring）。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from fakes import FakeClient, FakeJsClient

from horosa_skill.config import Settings
from horosa_skill.engine.js_client import HorosaJsEngineClient
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService, _clock
from horosa_skill.service.runners.predictive import PredictiveRunners as R

PKG = Path(__file__).resolve().parents[1]
CORE_JS = PKG / "horosa-core-js"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sync313_directed_live.json"
LIVE = json.loads(FIXTURE.read_text(encoding="utf-8"))
TECHS = ("neroman", "bezzafigure", "jayprofection", "michon")
CASES = [(tech, name) for tech in TECHS for name in ("default", "custom")]
BIRTH = {**LIVE["birth"], "agent_confirmed_settings": True}
_UPSTREAM_ROOT = os.environ.get("HOROSA_SOURCE_ROOT")
UPSTREAM_UI = Path(_UPSTREAM_ROOT) / "Horosa-Web" / "astrostudyui" if _UPSTREAM_ROOT else None
requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="[host] node not installed")
requires_upstream = pytest.mark.skipif(
    UPSTREAM_UI is None or not (UPSTREAM_UI / "node_modules" / "@babel" / "parser").is_dir()
    or not (UPSTREAM_UI / "src" / "utils" / "directedFigures.js").is_file(),
    reason="[upstream-checkout] HOROSA_SOURCE_ROOT (upstream checkout with node_modules and utils/directedFigures.js) not set",
)
NOW_UTC = datetime(2026, 10, 30, 4, 0, 0, tzinfo=timezone.utc)


def _scenario(tech: str, name: str) -> dict[str, Any]:
    return LIVE["scenarios"][tech][name]


# ── 上游金标生成器（上游源在 node 里跑）──────────────────────────────────────────────────────────────

# 上游写 `import … from '../constants/AstroConst'`（无扩展名，打包器解析）；原生 ESM 不解析 → 解析失败时补 `.js` 再试。
_EXT_LOADER = """
export async function resolve(specifier, context, next) {
  try { return await next(specifier, context); }
  catch (err) {
    if ((specifier.startsWith('.') || specifier.startsWith('/')) && !/\\.(?:[cm]?js|json)$/.test(specifier)) {
      return next(`${specifier}.js`, context);
    }
    throw err;
  }
}
"""

_UPSTREAM_JS = r"""
import { register, createRequire } from 'node:module';
import fs from 'node:fs';
register(process.argv[1]);
const require = createRequire(process.argv[2]);
const parser = require('@babel/parser');
const generate = require('@babel/generator').default;
const DF = await import(process.argv[3]);
const src = fs.readFileSync(new URL(process.argv[4]), 'utf8');
const want = new Set(['safeHelperLines', 'directedFigureOptsFromSettings', 'snapshotText', 'buildDirectedFigureSnapshotText']);
const ast = parser.parse(src, { sourceType: 'module', plugins: ['jsx', 'classProperties'] });
const decls = [];
for (let node of ast.program.body) {
  if (node.type === 'ExportNamedDeclaration' && node.declaration) node = node.declaration;
  let name = null;
  if (node.type === 'FunctionDeclaration' && node.id) name = node.id.name;
  if (node.type === 'VariableDeclaration' && node.declarations.length === 1 && node.declarations[0].id.type === 'Identifier') name = node.declarations[0].id.name;
  if (name && want.has(name)) { decls.push(generate(node, { comments: false }).code); want.delete(name); }
}
if (want.size) { throw new Error('missing upstream declarations: ' + [...want].join(',')); }
// 上游模块级依赖按 headless 口径注入：astroAiSnapshot 空对象（三段补厚 helper 全缺 → typeof 守卫回 []，与 skill 的 stub 同口径，
// [起盘信息]/[当前时点]/[方法说明] 另由 Python 公共段出）；页面保存值空记录 = 首装；fetch 换成回放夹具回包并记下请求体。
const factory = new Function('DF', 'astroAiSnapshot', 'DIRECTION_PAGE_SETTINGS', 'fetchDirectedFigure', 'today', 'chartZone',
  'const { DIRECTED_FIGURES, directedFigureRequestFields, buildDirectedFigureText } = DF;\n' + decls.join('\n')
  + '\nreturn { directedFigureOptsFromSettings, buildDirectedFigureSnapshotText };');
const live = JSON.parse(fs.readFileSync(process.argv[5], 'utf8'));
const out = {};
for (const [tech, scenarios] of Object.entries(live.scenarios)) {
  out[tech] = {};
  for (const [name, s] of Object.entries(scenarios)) {
    let request = null;
    const fetchStub = async (key, chartObj, targetDate, targetTime, opts) => {
      request = { targetDate, targetTime, fields: DF.directedFigureRequestFields(key, opts) };
      return s.response;
    };
    const api = factory(DF, {}, { load: () => ({}) }, fetchStub, () => { throw new Error('today() reached'); }, () => '');
    // = 上游 aiAnalysisContext/regenChart.js：opts = { ...directedFigureOptsFromSettings(key, record), targetDate, targetTime }。
    const record = { ...s.settings, targetDate: s.body.targetDate, targetTime: s.body.targetTime };
    const opts = { ...api.directedFigureOptsFromSettings(tech, record), targetDate: record.targetDate, targetTime: record.targetTime };
    const text = await api.buildDirectedFigureSnapshotText(tech, { params: {} }, opts);
    out[tech][name] = { text, request };
  }
}
process.stdout.write(JSON.stringify(out));
"""


def _upstream_goldens() -> dict[str, Any]:
    """上游源当场跑出的 {技法: {场景: {text, request}}}。重生夹具：
    `HOROSA_SOURCE_ROOT=… uv run python -c "import sys; sys.path[:0]=['tests']; import test_sync313_directed as t; t._write_fixture()"`。"""
    from node_esm import esm_argv

    assert UPSTREAM_UI is not None
    with tempfile.TemporaryDirectory() as tmp:
        loader = Path(tmp) / "ext_loader.mjs"
        loader.write_text(_EXT_LOADER, encoding="utf-8")
        argv = esm_argv(
            _UPSTREAM_JS, loader, UPSTREAM_UI / "package.json", UPSTREAM_UI / "src" / "utils" / "directedFigures.js",
            UPSTREAM_UI / "src" / "components" / "astro" / "AstroDirectedFigures.js", f"{FIXTURE.name}",
        )
        completed = subprocess.run(
            ["node", "--no-warnings", *argv[1:]], capture_output=True, text=True, encoding="utf-8", cwd=FIXTURE.parent, timeout=120,
        )
    if completed.returncode:
        raise RuntimeError(completed.stderr[-4000:])
    return json.loads(completed.stdout)


def _write_fixture() -> None:
    gold = _upstream_goldens()
    for tech, scenarios in LIVE["scenarios"].items():
        for name, scenario in scenarios.items():
            scenario["upstream"] = gold[tech][name]
    FIXTURE.write_text(json.dumps(LIVE, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


@requires_node
@requires_upstream
def test_fixture_matches_upstream() -> None:
    """夹具里的 `upstream` = 上游 8964bfd5 源当场跑出来的正文与请求体（不是 skill 自己的输出）。上游改了 directedFigures.js /
    AstroDirectedFigures.js 的纯逻辑段 → 红，按 `_upstream_goldens` docstring 重生夹具后逐条复核。
    负向对照（实跑）：把夹具 neroman/default 的 upstream.text 里「演进弧」改成「推进弧」→ 红；改回 → 绿。"""
    gold = _upstream_goldens()
    for tech, name in CASES:
        assert gold[tech][name] == _scenario(tech, name)["upstream"], (tech, name)


# ── vendored 引擎 == 上游 ────────────────────────────────────────────────────────────────────────────


def _settings(tmp_path: Path, **extra: Any) -> Settings:
    return Settings(
        server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", runtime_root=tmp_path / "runtime",
        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs", **extra,
    )


def _progextra(tmp_path: Path, tech: str, settings: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    payload = {"technique": tech, "chart": {"params": {}, "chart": {}}, "options": settings, "result": response, "now_ms": 0}
    out = HorosaJsEngineClient(_settings(tmp_path)).run("progextra", payload)
    assert out["data"]["ok"] is True, out
    return out


@requires_node
@pytest.mark.parametrize(("tech", "name"), CASES)
def test_vendored_progextra_equals_upstream(tmp_path: Path, tech: str, name: str) -> None:
    """vendored AstroDirectedFigures.snapshotText + directedFigures.js（manifest verbatim 看守）在实抓回包上逐字等于上游；
    progextra 回传的 request_fields 等于上游合并规则 + directedFigureRequestFields 的结果。
    负向对照（实跑）：vendored directedFigures.js 里 fmtN(r.arc, 4) 改成 fmtN(r.arc, 3) → neroman×2 / bezzafigure×2 红；
    tools/progextra.js 的 directedFigureRequest 去掉「页面保存值为底」那一步改成直接 directedFigureRequestFields(key, settings)
    → 4 个 custom 场景红（页面键 nerK 不是口径键 k，自选值全被吞成 DEFAULTS；default 场景恰好等于缺省而照绿）。"""
    scenario = _scenario(tech, name)
    out = _progextra(tmp_path, tech, scenario["settings"], scenario["response"])
    assert out["snapshot_text"] == scenario["upstream"]["text"]
    assert out["request_fields"] == scenario["upstream"]["request"]["fields"]


@pytest.mark.parametrize(("tech", "name"), CASES)
def test_python_request_body_equals_upstream(tech: str, name: str) -> None:
    """runner 自己算的请求体（Python 移植 directedFigureRequestFields）== 上游；目标日 / 时刻 == 上游收到的。"""
    scenario = _scenario(tech, name)
    upstream = scenario["upstream"]["request"]
    assert R._directed_figure_request_fields(tech, scenario["settings"]) == upstream["fields"]
    assert {k: scenario["body"][k] for k in upstream["fields"]} == upstream["fields"]
    assert (scenario["body"]["targetDate"], scenario["body"]["targetTime"]) == (upstream["targetDate"], upstream["targetTime"])
    assert scenario["body"]["withChart"] == 0 and scenario["body"]["tradition"] is False and scenario["body"]["predictive"] is False


@requires_node
def test_python_defaults_equal_the_vendored_tables(tmp_path: Path) -> None:
    """Python 侧出厂值（页面键）== vendored directedFigures.js 的 *_DEFAULTS（= 后端缺省）。
    负向对照（实跑）：_DIRECTED_FIGURE_DEFAULTS["neroman"]["nerT0"] 改 0.7 → 红。"""
    from node_esm import run_node_esm

    js = json.loads(run_node_esm(
        "import * as D from './src/vendor/utils/directedFigures.js';"
        "console.log(JSON.stringify({n: D.NEROMAN_DEFAULTS, b: D.BEZZA_DEFAULTS, j: D.JAY_DEFAULTS, m: D.MICHON_DEFAULTS, keys: D.DIRECTED_FIGURE_KEYS,"
        " endpoints: Object.fromEntries(Object.entries(D.DIRECTED_FIGURES).map(([k, v]) => [k, v.endpoint]))}))",
        cwd=CORE_JS, timeout=60,
    ))
    assert R._DIRECTED_FIGURE_DEFAULTS == {
        "neroman": {"nerK": js["n"]["k"], "nerT0": js["n"]["t0"], "nerKeepDec": js["n"]["keepDec"], "nerOrb": js["n"]["orb"]},
        "bezzafigure": {"bezzaOrb": js["b"]["orb"]},
        "jayprofection": {"jayFrom": js["j"]["from"]},
        "michon": {"michonOrb": js["m"]["orb"], "michonSwap": js["m"]["swap"], "michonEqual": js["m"]["equal"]},
    }
    assert tuple(js["keys"]) == TECHS and js["endpoints"] == R._DIRECTED_FIGURE_ENDPOINTS


@requires_upstream
def test_option_domains_equal_the_upstream_page_settings() -> None:
    """值域 == 上游星阙页保存键的 oneOf / min–max（utils/directionPageSettings.js，挂载齿轮同一组选项）。
    负向对照（实跑）：_DIRECTED_FIGURE_SELECTS["bezzafigure"]["bezzaOrb"] 去掉 5 → 红。"""
    import re

    assert UPSTREAM_UI is not None
    text = (UPSTREAM_UI / "src" / "utils" / "directionPageSettings.js").read_text(encoding="utf-8")

    def entry(key: str) -> str:
        match = re.search(rf"^\t{key}: \{{(.*)\}},$", text, re.M)
        assert match, key
        return match.group(1)

    def one_of(key: str) -> tuple[float, ...]:
        body = re.search(r"oneOf: \[([^\]]*)\]", entry(key)).group(1)
        return tuple(int(x) if float(x) == int(float(x)) else float(x) for x in (s.strip() for s in body.split(",")))

    selects = {tech: {k: v for k, v in table.items() if v[0] is not False} for tech, table in R._DIRECTED_FIGURE_SELECTS.items()}
    assert {k: v for t in selects.values() for k, v in t.items()} == {k: one_of(k) for k in ("nerOrb", "bezzaOrb", "jayFrom", "michonOrb")}
    bools = {k for t in R._DIRECTED_FIGURE_SELECTS.values() for k, v in t.items() if v[0] is False}
    assert bools == {"nerKeepDec", "michonSwap", "michonEqual"} and all("oneOf" not in entry(k) for k in bools)
    for key, (low, high) in R._DIRECTED_FIGURE_RANGES["neroman"].items():
        body = entry(key)
        assert f"min: {low}" in body and f"max: {high}" in body, key


# ── runner 端到端（离线桩 + 真 JS）──────────────────────────────────────────────────────────────────


class _Client(FakeClient):
    def __init__(self, overrides: dict[str, Any] | None = None) -> None:
        super().__init__()
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.overrides = overrides or {}

    def call(self, endpoint: str, payload: dict) -> dict:
        self.calls.append((endpoint, dict(payload)))
        if endpoint in self.overrides:
            return json.loads(json.dumps(self.overrides[endpoint]))
        return super().call(endpoint, payload)

    def sent(self, endpoint: str) -> dict[str, Any]:
        return [p for e, p in self.calls if e == endpoint][-1]


class _RealJs(FakeJsClient):
    def __init__(self, tmp_path: Path) -> None:
        super().__init__()
        self.real = HorosaJsEngineClient(_settings(tmp_path))

    def run(self, tool_name: str, payload: dict) -> dict:
        return self.real.run(tool_name, payload) if tool_name == "progextra" else super().run(tool_name, payload)


def _service(tmp_path: Path, client: FakeClient, js: FakeJsClient | None = None) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    return HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=js or FakeJsClient())


@pytest.fixture()
def frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    local_now = NOW_UTC.astimezone().replace(tzinfo=None)

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


@requires_node
@pytest.mark.parametrize(("tech", "name"), CASES)
def test_runner_end_to_end_with_real_engine(tmp_path: Path, frozen: None, tech: str, name: str) -> None:
    """真 JS + 实抓回包：请求体逐键 == 夹具（= 上游）；正文段 == 上游金标；段序 = 上游 preset；导出零缺段零未知段。
    负向对照（实跑）：runner 的 knob_keys 置空 → 页面键 nerOrb / bezzaOrb / michon* 漏进请求体 → neroman / bezzafigure / michon 的 custom 场景红（jayFrom 本就是口径键）。"""
    scenario = _scenario(tech, name)
    endpoint = R._DIRECTED_FIGURE_ENDPOINTS[tech]
    client = _Client({endpoint: scenario["response"]})
    payload = {**BIRTH, **scenario["payload"]}
    if tech == "michon":
        payload.pop("targetDate", None)
    result = _service(tmp_path, client, _RealJs(tmp_path)).run_tool(tech, payload, save_result=False)
    assert result.ok is True, result.error
    sent = client.sent(endpoint)
    expected_body = dict(scenario["body"])
    if tech == "michon":  # 双黄道请求体照上游带「本盘时区今日 12:00」（冻结此刻 = 东八区 2026-10-30）
        assert (sent["targetDate"], sent["targetTime"]) == ("2026-10-30", "12:00:00")
    assert {k: sent.get(k) for k in expected_body} == expected_body
    page_only = set(R._DIRECTED_FIGURE_DEFAULTS[tech]) - set(scenario["upstream"]["request"]["fields"])
    assert not page_only & set(sent), "只有页面键（nerOrb / bezzaOrb / michon*）不进请求体：后端只认上游映射后的口径键"
    text = result.data["snapshot_text"]
    assert scenario["upstream"]["text"] in text
    snap = result.data["export_snapshot"]
    assert snap["missing_selected_sections"] == [] and snap["unknown_detected_sections"] == []
    from horosa_skill.exports.registry import AI_EXPORT_PRESET_SECTIONS

    assert [s["title"] for s in snap["sections"]] == AI_EXPORT_PRESET_SECTIONS[tech]
    assert _section(text, "当前时点").splitlines()[0].startswith("导出时刻：")
    from horosa_skill.service.text.predictive import _PREDICTIVE_METHOD_NOTES

    assert _section(text, "方法说明").splitlines() == _PREDICTIVE_METHOD_NOTES[tech]  # 逐字对上游由 test_method_notes_* 守
    assert result.data["request"] == scenario["upstream"]["request"]["fields"]


def test_settings_change_the_request_and_the_text() -> None:
    """「改这个参数，结果必须变」：每个技法 custom 场景的请求体与上游正文都与 default 不同，且正文写出了所选口径。"""
    for tech in TECHS:
        default, custom = _scenario(tech, "default"), _scenario(tech, "custom")
        assert default["request_fields"] != custom["request_fields"], tech
        assert default["upstream"]["text"] != custom["upstream"]["text"], tech
    assert "换到赤道：保留本命赤纬" in _scenario("neroman", "custom")["upstream"]["text"]
    contacts = {name: _section(_scenario("bezzafigure", name)["upstream"]["text"], "推运图接触").count("\n| ") for name in ("default", "custom")}
    assert contacts["custom"] > contacts["default"]  # 接触窗 ±5° 比 ±1° 宽
    assert "| 36 |" in _scenario("jayprofection", "custom")["upstream"]["text"].split("[逐年小限]")[1].splitlines()[3]
    assert "守护：水金互换;宫位：等宫(上升居第一宫正中);容许度 2.0°" in _scenario("michon", "custom")["upstream"]["text"]


def test_default_target_is_today_in_the_chart_zone(tmp_path: Path, frozen: None) -> None:
    """targetDate 缺省 = 本盘时区今日（上游 today(chartZone)），targetTime 缺省 12:00:00；HH:mm 补秒。
    负向对照（实跑）：_directed_figure_target 改用本机今日（_clock.now()）→ 西五区那条红（冻结此刻 = 2026-10-30 04:00 UTC）。"""
    client = _Client({"/astroextra/neroman": _scenario("neroman", "default")["response"]})
    _service(tmp_path, client).run_tool("neroman", {**BIRTH, "zone": "-05:00"}, save_result=False)
    assert (client.sent("/astroextra/neroman")["targetDate"], client.sent("/astroextra/neroman")["targetTime"]) == ("2026-10-29", "12:00:00")
    _service(tmp_path, client).run_tool("neroman", {**BIRTH, "targetDate": "2031/4/6", "targetTime": "8:05"}, save_result=False)
    assert (client.sent("/astroextra/neroman")["targetDate"], client.sent("/astroextra/neroman")["targetTime"]) == ("2031-04-06", "08:05:00")


@pytest.mark.parametrize(
    ("tech", "bad", "code"),
    [
        ("neroman", {"nerOrb": 1.5}, "tool.predictive_invalid_option"),
        ("neroman", {"nerK": 0}, "tool.predictive_invalid_option"),
        ("neroman", {"nerT0": 11}, "tool.predictive_invalid_option"),
        ("neroman", {"nerKeepDec": "maybe"}, "tool.predictive_invalid_option"),
        ("bezzafigure", {"bezzaOrb": 4}, "tool.predictive_invalid_option"),
        ("jayprofection", {"jayFrom": 13}, "tool.predictive_invalid_option"),
        ("michon", {"michonOrb": 3}, "tool.predictive_invalid_option"),
        ("neroman", {"targetDate": "2026-13-01"}, "tool.directed_invalid_target"),
        ("bezzafigure", {"targetTime": "25:00"}, "tool.directed_invalid_target"),
    ],
)
def test_bad_options_fail_loudly(tmp_path: Path, tech: str, bad: dict[str, Any], code: str) -> None:
    """上游 num(…, 缺省) 会把认不出的值静默回落缺省 = 算出另一张盘而不自知；skill 一律报错。"""
    result = _service(tmp_path, _Client()).run_tool(tech, {**BIRTH, **bad}, save_result=False)
    assert result.ok is False and result.error.code == code


@pytest.mark.parametrize("tech", TECHS)
def test_empty_backend_result_is_a_structured_error(tmp_path: Path, tech: str) -> None:
    """上游 builder 无数据返回 ''（挂载显示「缺失」）；skill 侧空快照会落 generated_template 假导出——一律报错（AGENTS §5.9）。"""
    empty = {"neroman": {"evolved": []}, "bezzafigure": {"points": []}, "jayprofection": {"rows": []}, "michon": {"superpositions": []}}[tech]
    client = _Client({R._DIRECTED_FIGURE_ENDPOINTS[tech]: empty})
    result = _service(tmp_path, client).run_tool(tech, dict(BIRTH), save_result=False)
    assert result.ok is False and result.error.code == f"tool.{tech}_empty"


@requires_node
def test_runner_cross_checks_python_against_upstream_mapping(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Python 移植的 directedFigureRequestFields 一旦与 vendored 上游函数不一致（progextra 回传 request_fields），runner 报错而不是
    拿错请求体算出的盘照常返回。这条本身就是负向对照：把移植改坏（orb + 0.5）→ tool.directed_request_mismatch。"""
    original = R._directed_figure_request_fields

    def drifted(technique: str, settings: dict[str, Any]) -> dict[str, Any]:
        fields = original(technique, settings)
        return {**fields, "orb": fields["orb"] + 0.5} if "orb" in fields else fields

    monkeypatch.setattr(R, "_directed_figure_request_fields", staticmethod(drifted))
    client = _Client({"/astroextra/bezzafigure": _scenario("bezzafigure", "default")["response"]})
    result = _service(tmp_path, client, _RealJs(tmp_path)).run_tool("bezzafigure", dict(BIRTH), save_result=False)
    assert result.ok is False and result.error.code == "tool.directed_request_mismatch"
    assert result.error.details["sent"] == {"orb": 1.5} and result.error.details["upstream"] == {"orb": 1}
