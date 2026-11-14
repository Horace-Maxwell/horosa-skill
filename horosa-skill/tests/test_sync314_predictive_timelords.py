"""上游 v3.14.0 星运「时主轮转」十二法（工具 horosa_predict_timelords，registry 键 timelords）。

期表类：轮主 turn / 轨主 orb / 年度分配 annual / 月相四分 quarters / 月亮单度主 monomoiria / 月亮九年 moonnine / 九分主 nineparts；
事件类：匀速点 moving / 发展年龄 devages / 周日象限 diurnal / 对数时标 lifetime / 月亮日 moondays。

权威：
- 计算：后端 astrostudy/timelord_tables.py（/astroextra/timelords）。回包 = vendored v3.14.0 实例实抓
  （tests/fixtures/sync314_predictive_timelords_live.json.gz；请求体就是 skill runner 自己发的那一份）。命盘 = 上游
  astropy/tests/test_timelord_tables.py 的 PLACIDUS（1975-02-10 21:15 西雅图，Placidus）与 POLAR（北纬 70°）。
- 排版：上游 utils/timeLordTables.js buildTimeLordText 经 utils/directedFigures.js buildDirectedFigureText 与
  components/astro/AstroDirectedFigures.js snapshotText；请求体映射 timeLordRequestFields。
- 文本金标 = **上游源本身**在 node 里跑出来的（`_upstream_goldens()`），存进夹具的 `upstream` 键；
  `test_fixture_matches_upstream` 在 HOROSA_SOURCE_ROOT 可用时重跑一遍，夹具与上游漂移即红。
- 值级金标 = 按定义手算 / 上游后端测试夹具里的断言（`test_values_follow_the_definitions`：每法至少一条，期望值不取自回包本身）。

重生夹具（需要 vendored v3.14.0 引擎在 8877 / 9977 上跑着，且 HOROSA_SOURCE_ROOT 指向带 node_modules 的上游检出）：
    HOROSA_CHART_SERVER_ROOT=http://127.0.0.1:8877 HOROSA_SERVER_ROOT=http://127.0.0.1:9977 HOROSA_SOURCE_ROOT=… \\
      uv run python -c "import sys; sys.path[:0]=['tests']; import test_sync314_predictive_timelords as t; t._write_fixture()"

负向对照（均实跑，见各条 docstring 与备忘）。
"""
from __future__ import annotations

import gzip
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from horosa_skill.errors import ToolValidationError
from fakes import FakeClient, FakeJsClient

from horosa_skill.config import Settings
from horosa_skill.engine.js_client import HorosaJsEngineClient
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService, _clock
from horosa_skill.service.runners.predictive import PredictiveRunners as R
from horosa_skill.western_vocab import (
    TIMELORD_DEFAULTS,
    TIMELORD_EVENT_METHODS,
    TIMELORD_METHOD_FIELDS,
    TIMELORD_PERIOD_METHODS,
    TIMELORD_VOCABULARIES,
)

PKG = Path(__file__).resolve().parents[1]
CORE_JS = PKG / "horosa-core-js"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sync314_predictive_timelords_live.json.gz"
ENDPOINT = "/astroextra/timelords"
METHODS = (*TIMELORD_PERIOD_METHODS, *TIMELORD_EVENT_METHODS)
TARGET = "2026-01-01"

# 命盘 = 上游 astropy/tests/test_timelord_tables.py 的 PLACIDUS（CHART + hsys 3）与 POLAR（北纬 70°，hsys 1）。
BIRTHS: dict[str, dict[str, Any]] = {
    "seattle": {"date": "1975-02-10", "time": "21:15:00", "zone": "-08:00", "lat": "47n36", "lon": "122w20", "hsys": 3, "zodiacal": 0},
    "polar": {"date": "1975-02-10", "time": "21:15:00", "zone": "-08:00", "lat": "70n00", "lon": "122w20", "hsys": 1, "zodiacal": 0},
}
# 每法 default（全缺省）+ custom（这一法读的每个键都拨到非缺省）；另加边界场景。载荷键 = 页面键（tl*）+ targetDate。
PLAN: dict[str, dict[str, dict[str, Any]]] = {
    "turn": {
        "default": {},
        "custom": {"tlTurnStart": "hour", "tlTurnOrder": "chaldean", "tlYearType": "hellenistic"},
        "past_end": {"targetDate": "2080-01-01"},
        "before_birth": {"targetDate": "1970-01-01"},
    },
    "orb": {"default": {}, "custom": {"tlOrbMode": "cycle", "tlYearType": "sidereal"}},
    "annual": {"default": {}, "custom": {"tlAnnualDays": "tableB", "tlAnnualOrder": "return"}},
    "quarters": {"default": {}, "custom": {"tlReleaser": "Pars Fortuna", "tlYearType": "bija"}},
    "monomoiria": {"default": {}, "custom": {"tlYearType": "bijaClassic"}},
    "moonnine": {"default": {}, "custom": {"tlVariant": "classic", "tlYearType": "abumashar"}},
    "nineparts": {
        "default": {},
        "custom": {"tlNineTime": "ascension", "tlNineReverse": True, "tlVariant": "classic", "tlYearType": "mashaallah"},
        "polar": {"tlNineTime": "ascension", "_birth": "polar"},
    },
    "moving": {
        "default": {},
        "custom": {"tlRateKind": "age72", "tlMovingStart": "Syzygy", "tlMovingYear": "solar"},
        "before_first": {"tlRateKind": "age72", "tlMovingStart": "Sun", "targetDate": "1970-01-01"},
    },
    "devages": {"default": {}, "custom": {"tlDevBasis": "house", "tlVariant": "classic"}},
    "diurnal": {"default": {}, "custom": {"tlDiurnalMode": "quadrant", "tlVariant": "classic"}},
    "lifetime": {"default": {}, "custom": {"targetDate": "1990-06-01"}},
    "moondays": {"default": {}, "custom": {"tlVariant": "classic"}},
}
CASES = [(method, name) for method, scenarios in PLAN.items() for name in scenarios]

_UPSTREAM_ROOT = os.environ.get("HOROSA_SOURCE_ROOT")
UPSTREAM_UI = Path(_UPSTREAM_ROOT) / "Horosa-Web" / "astrostudyui" if _UPSTREAM_ROOT else None
requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="[host] node not installed")
requires_upstream = pytest.mark.skipif(
    UPSTREAM_UI is None or not (UPSTREAM_UI / "node_modules" / "@babel" / "parser").is_dir()
    or not (UPSTREAM_UI / "src" / "utils" / "timeLordTables.js").is_file(),
    reason="[upstream-checkout] HOROSA_SOURCE_ROOT (upstream checkout with node_modules and utils/timeLordTables.js) not set",
)
NOW_UTC = datetime(2026, 10, 30, 4, 0, 0, tzinfo=timezone.utc)


def _load() -> dict[str, Any]:
    return json.loads(gzip.decompress(FIXTURE.read_bytes()))


LIVE = _load() if FIXTURE.is_file() else {"scenarios": {}}


def _scenario(method: str, name: str) -> dict[str, Any]:
    return LIVE["scenarios"][method][name]


def _birth(method: str, name: str) -> dict[str, Any]:
    return {**BIRTHS[PLAN[method][name].get("_birth", "seattle")], "agent_confirmed_settings": True}


def _payload(method: str, name: str) -> dict[str, Any]:
    """这一场景的调用载荷（不含出生数据）：页面键 + 方法 + 目标日。"""
    knobs = {k: v for k, v in PLAN[method][name].items() if not k.startswith("_")}
    return {"targetDate": TARGET, **knobs, "tlMethod": method}


def _full_settings(method: str, name: str) -> dict[str, Any]:
    """runner 交给 progextra 的那份设置（页面键、缺省补齐）。"""
    return {**TIMELORD_DEFAULTS, **{k: v for k, v in _payload(method, name).items() if k.startswith("tl")}}


# ── 夹具：实抓回包（skill runner 自己发的请求）+ 上游源金标 ─────────────────────────────────────────────


class _Recorder:
    """真后端客户端的包装：记下发往时主轮转接口的请求体与回包。"""

    def __init__(self, inner: Any) -> None:
        self.inner, self.seen = inner, []

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    def call(self, endpoint: str, payload: dict) -> dict:
        response = self.inner.call(endpoint, payload)
        if endpoint == ENDPOINT:
            self.seen.append((json.loads(json.dumps(payload)), json.loads(json.dumps(response))))
        return response


def _capture_live() -> dict[str, Any]:
    from horosa_skill.engine.client import HorosaPlainJsonClient

    chart_root, java_root = os.environ["HOROSA_CHART_SERVER_ROOT"], os.environ["HOROSA_SERVER_ROOT"]
    assert ":8899" not in chart_root and ":9999" not in java_root, "never capture from the desktop app's ports"
    out: dict[str, Any] = {
        "_source": "vendored 星阙 v3.14.0 chart 服务 /astroextra/timelords 实抓（请求体 = skill runner 发出的那一份）；"
                   "upstream = 上游 utils/timeLordTables.js + directedFigures.js + AstroDirectedFigures.js 源在 node 里对同一回包跑出的正文与请求键。"
                   "命盘 = 上游 astropy/tests/test_timelord_tables.py 的 PLACIDUS / POLAR。",
        "births": BIRTHS,
        "scenarios": {},
    }
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        settings = Settings(server_root=java_root, chart_server_root=chart_root, runtime_root=root / "runtime",
                            db_path=root / "memory.db", output_dir=root / "runs")
        recorder = _Recorder(HorosaPlainJsonClient(chart_root))
        service = HorosaSkillService(settings, store=MemoryStore(settings))
        service.chart_client = recorder
        for method, name in CASES:
            recorder.seen.clear()
            result = service.run_tool("timelords", {**_birth(method, name), **_payload(method, name)}, save_result=False)
            assert result.ok is True, (method, name, result.error)
            assert len(recorder.seen) == 1, (method, name, len(recorder.seen))
            body, response = recorder.seen[0]
            out["scenarios"].setdefault(method, {})[name] = {
                "payload": _payload(method, name), "body": body, "request_fields": result.data["request"], "response": response,
            }
    return out


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
import zlib from 'node:zlib';
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
// 上游模块级依赖按 headless 口径注入：astroAiSnapshot 空对象（三段补厚 helper 全缺 → typeof 守卫回 []，与 skill 的 stub 同口径）；
// 页面保存值空记录 = 首装；fetch 换成回放夹具回包并记下请求体。
const factory = new Function('DF', 'astroAiSnapshot', 'DIRECTION_PAGE_SETTINGS', 'fetchDirectedFigure', 'today', 'chartZone',
  'const { DIRECTED_FIGURES, directedFigureRequestFields, buildDirectedFigureText } = DF;\n' + decls.join('\n')
  + '\nreturn { directedFigureOptsFromSettings, buildDirectedFigureSnapshotText };');
const live = JSON.parse(zlib.gunzipSync(fs.readFileSync(process.argv[5])).toString('utf8'));
const out = {};
for (const [method, scenarios] of Object.entries(live.scenarios)) {
  out[method] = {};
  for (const [name, s] of Object.entries(scenarios)) {
    let request = null;
    const fetchStub = async (key, chartObj, targetDate, targetTime, opts) => {
      request = { targetDate, targetTime, fields: DF.directedFigureRequestFields(key, opts) };
      return s.response;
    };
    const api = factory(DF, {}, { load: () => ({}) }, fetchStub, () => { throw new Error('today() reached'); }, () => '');
    // = 上游 aiAnalysisContext/regenChart.js：opts = { ...directedFigureOptsFromSettings(key, record), targetDate, targetTime }；
    // record = 挂载齿轮记录（页面键），没拨的键 undefined → 回落页面保存值（空）→ normalizeTimeLordOpts 的缺省。
    const record = { ...s.payload, targetTime: s.body.targetTime };
    const opts = { ...api.directedFigureOptsFromSettings('timelords', record), targetDate: record.targetDate, targetTime: record.targetTime };
    const text = await api.buildDirectedFigureSnapshotText('timelords', { params: {} }, opts);
    out[method][name] = { text, request };
  }
}
process.stdout.write(JSON.stringify(out));
"""


def _upstream_goldens(live: dict[str, Any] | None = None) -> dict[str, Any]:
    """上游源当场跑出的 {方法: {场景: {text, request}}}（回放 `live` 或磁盘上的夹具回包）。"""
    from node_esm import esm_argv

    assert UPSTREAM_UI is not None
    with tempfile.TemporaryDirectory() as tmp:
        loader = Path(tmp) / "ext_loader.mjs"
        loader.write_text(_EXT_LOADER, encoding="utf-8")
        replay = Path(tmp) / "live.json.gz"
        replay.write_bytes(gzip.compress(json.dumps(live).encode("utf-8"), mtime=0) if live is not None else FIXTURE.read_bytes())
        argv = esm_argv(
            _UPSTREAM_JS, loader, UPSTREAM_UI / "package.json", UPSTREAM_UI / "src" / "utils" / "directedFigures.js",
            UPSTREAM_UI / "src" / "components" / "astro" / "AstroDirectedFigures.js", "live.json.gz",
        )
        completed = subprocess.run(
            ["node", "--no-warnings", *argv[1:]], capture_output=True, text=True, encoding="utf-8", cwd=tmp, timeout=180,
        )
    if completed.returncode:
        raise RuntimeError(completed.stderr[-4000:])
    return json.loads(completed.stdout)


def _write_fixture() -> None:
    live = _capture_live()
    gold = _upstream_goldens(live)
    for method, scenarios in live["scenarios"].items():
        for name, scenario in scenarios.items():
            scenario["upstream"] = gold[method][name]
    FIXTURE.write_bytes(gzip.compress(json.dumps(live, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"), mtime=0))


def test_fixture_covers_every_method_and_scenario() -> None:
    assert set(LIVE["scenarios"]) == set(METHODS) == set(PLAN) and len(METHODS) == 12
    for method, name in CASES:
        scenario = _scenario(method, name)
        assert scenario["payload"] == _payload(method, name), (method, name)
        assert scenario["response"]["method"] == method and scenario["response"]["rows"], (method, name)
        assert scenario["upstream"]["text"].startswith("[时主轮转]\n方法："), (method, name)
    assert FIXTURE.read_bytes()[4:8] == b"\x00\x00\x00\x00", "gzip header mtime must be 0 (deterministic bytes)"


@requires_node
@requires_upstream
def test_fixture_matches_upstream() -> None:
    """夹具里的 `upstream` = 上游 v3.14.0 源当场跑出来的正文与请求体（不是 skill 自己的输出）。上游改了 timeLordTables.js /
    directedFigures.js / AstroDirectedFigures.js 的纯逻辑段 → 红，重生夹具后逐条复核。
    负向对照（实跑）：把夹具 turn/default 的 upstream.text 里「起始星」改成「起点星」→ 红；改回 → 绿。"""
    gold = _upstream_goldens()
    for method, name in CASES:
        assert gold[method][name] == _scenario(method, name)["upstream"], (method, name)


# ── Python 表 == vendored 上游表 ─────────────────────────────────────────────────────────────────────


@requires_node
def test_python_tables_equal_the_vendored_tables() -> None:
    """词表（方法 / 各选项的规范值、上游中文名、缺省）、每法读哪些键、期表 / 事件两类、接口名 == vendored timeLordTables.js / directedFigures.js。
    负向对照（实跑）：western_vocab._TIMELORD_CHOICES 的 tlTurnOrder 去掉 house → 红；TIMELORD_METHOD_FIELDS["moonnine"] 去掉 tlVariant → 红；
    tlMovingYear 缺省改 solar → 红。"""
    from node_esm import run_node_esm

    js = json.loads(run_node_esm(
        "import * as T from './src/vendor/utils/timeLordTables.js';"
        "import * as D from './src/vendor/utils/directedFigures.js';"
        "console.log(JSON.stringify({methods: T.TIMELORD_METHODS, defaults: T.TIMELORD_DEFAULTS, options: T.TIMELORD_OPTIONS,"
        " fields: T.TIMELORD_METHOD_FIELDS, keys: D.DIRECTED_FIGURE_KEYS, endpoint: D.DIRECTED_FIGURES.timelords.endpoint, polar: T.TIMELORD_POLAR_NOTE}))",
        cwd=CORE_JS, timeout=60,
    ))

    def page_key(key: str) -> str:
        return "tl" + key[0].upper() + key[1:]

    def table(field: str) -> dict[Any, str]:
        return {value: label.replace("（缺省）", "") for value, label in TIMELORD_VOCABULARIES[field].labels.items()}

    assert table("tlMethod") == {m["value"]: m["label"] for m in js["methods"]}
    assert tuple(m["value"] for m in js["methods"]) == METHODS
    for key, options in js["options"].items():
        if key == "nineReverse":
            assert [o["value"] for o in options] == [False, True] == list(R._DIRECTED_FIGURE_SELECTS["timelords"]["tlNineReverse"])
            continue
        assert table(page_key(key)) == {o["value"]: o["label"] for o in options}, key
    assert table("tlMovingYear") == table("tlYearType")   # 匀速点年长与 yearType 同一组选项（TIMELORD_OPTIONS.yearType）
    assert {page_key(k): v for k, v in js["defaults"].items()} == TIMELORD_DEFAULTS == R._DIRECTED_FIGURE_DEFAULTS["timelords"]
    assert {field: vocab for field, vocab in TIMELORD_VOCABULARIES.items()}.keys() | {"tlNineReverse"} == set(TIMELORD_DEFAULTS)
    for field, vocab in TIMELORD_VOCABULARIES.items():
        assert vocab.labels[TIMELORD_DEFAULTS[field]].endswith("（缺省）"), field
        assert tuple(vocab.labels) == R._DIRECTED_FIGURE_SELECTS["timelords"][field]
    assert TIMELORD_METHOD_FIELDS == {
        method: (page_key(spec["yearField"]) if spec.get("yearField") else None, tuple(page_key(f) for f in spec["fields"]))
        for method, spec in js["fields"].items()
    }
    assert set(R._TIMELORD_REQUEST_KEYS) == {f for _year, fields in TIMELORD_METHOD_FIELDS.values() for f in fields}
    assert all(page_key(request) == page for page, request in R._TIMELORD_REQUEST_KEYS.items())
    assert "timelords" in js["keys"] and js["endpoint"] == R._DIRECTED_FIGURE_ENDPOINTS["timelords"] == ENDPOINT
    assert js["polar"] == "极圈内斜升不单调,上升时档不成立,已改按度数"
    kinds = {method: _scenario(method, "default")["response"]["kind"] for method in METHODS}
    assert {m for m, k in kinds.items() if k == "periods"} == set(TIMELORD_PERIOD_METHODS)
    assert {m for m, k in kinds.items() if k == "events"} == set(TIMELORD_EVENT_METHODS)


@requires_upstream
def test_field_names_equal_the_upstream_mount_gear_and_page_keys() -> None:
    """字段名 = 上游挂载齿轮字段（techniqueMountSettings.js TIMELORD_FIELDS）= 星运页保存键（directionPageSettings.js）。"""
    assert UPSTREAM_UI is not None
    mount = (UPSTREAM_UI / "src" / "utils" / "techniqueMountSettings.js").read_text(encoding="utf-8")
    block = mount[mount.index("const TIMELORD_FIELDS = ["):]
    block = block[: block.index("\n];")]
    assert set(re.findall(r"TL_FIELD\('(\w+)'", block)) == set(TIMELORD_DEFAULTS)
    assert "...DIRECTED_TARGET_FIELDS" in block   # 目标日期 / 时刻两键与推运图族共用
    page = (UPSTREAM_UI / "src" / "utils" / "directionPageSettings.js").read_text(encoding="utf-8")
    assert set(re.findall(r"^\t(tl\w+): \{", page, re.M)) == set(TIMELORD_DEFAULTS)


# ── vendored 引擎 == 上游 ────────────────────────────────────────────────────────────────────────────


def _settings(tmp_path: Path, **extra: Any) -> Settings:
    return Settings(
        server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", runtime_root=tmp_path / "runtime",
        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs", **extra,
    )


def _progextra(tmp_path: Path, settings: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    payload = {"technique": "timelords", "chart": {"params": {}, "chart": {}}, "options": settings, "result": response, "now_ms": 0}
    out = HorosaJsEngineClient(_settings(tmp_path)).run("progextra", payload)
    assert out["data"]["ok"] is True, out
    return out


@requires_node
@pytest.mark.parametrize(("method", "name"), CASES)
def test_vendored_progextra_equals_upstream(tmp_path: Path, method: str, name: str) -> None:
    """vendored timeLordTables.buildTimeLordText（经 directedFigures / AstroDirectedFigures.snapshotText，manifest verbatim 看守）在实抓回包上
    逐字等于上游；progextra 回传的 request_fields 等于上游 timeLordRequestFields 的结果。
    负向对照（实跑）：vendored timeLordTables.js 把 NEXT_ROWS 8 改成 7 → 多数期表 / 事件场景红；把 timeLordRequestFields 里
    `fields.yearType = o[spec.yearField]` 改成 `o.yearType` → moving/default（匀速点读自己的年长）红。"""
    scenario = _scenario(method, name)
    out = _progextra(tmp_path, _full_settings(method, name), scenario["response"])
    assert out["snapshot_text"] == scenario["upstream"]["text"]
    assert out["request_fields"] == scenario["upstream"]["request"]["fields"]


@pytest.mark.parametrize(("method", "name"), CASES)
def test_python_request_body_equals_upstream(method: str, name: str) -> None:
    """runner 自己算的请求体（Python 移植 timeLordRequestFields）== 上游；目标日 / 时刻 == 上游收到的；请求体里只有上游映射后的口径键。
    负向对照（实跑）：_directed_figure_request_fields 的 timelords 分支把年长恒取 tlYearType → moving 的三个场景红。"""
    scenario = _scenario(method, name)
    upstream = scenario["upstream"]["request"]
    assert R._directed_figure_request_fields("timelords", _full_settings(method, name)) == upstream["fields"] == scenario["request_fields"]
    body = scenario["body"]
    assert {k: body[k] for k in upstream["fields"]} == upstream["fields"]
    assert (body["targetDate"], body["targetTime"]) == (upstream["targetDate"], upstream["targetTime"])
    assert body["withChart"] == 0 and body["tradition"] is False and body["predictive"] is False
    assert not {k for k in body if k.startswith("tl")}, "页面键不进请求体"
    assert set(body) & R._TIMELORD_RAW_KEYS == set(upstream["fields"]), "这一法不读的口径键、maxAge 都不下发"


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

    def sent(self, endpoint: str = ENDPOINT) -> dict[str, Any]:
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
@pytest.mark.parametrize(("method", "name"), CASES)
def test_runner_end_to_end_with_real_engine(tmp_path: Path, frozen: None, method: str, name: str) -> None:
    """真 JS + 实抓回包：请求体逐键 == 夹具（= 上游）；正文段 == 上游金标；段序 = 上游 preset（月亮日没有 [当前时段] / [后续]，其余十一法
    两段恒出）；导出零缺段零未知段；回执只列这一法读的口径。
    负向对照（实跑）：exports/registry.py 去掉 timelords 的 optional 登记 → moondays×2 红（缺段）；runner 的 knob_keys 不并入
    _TIMELORD_RAW_KEYS 且载荷带裸键 → 见 test_raw_backend_keys_are_not_forwarded。"""
    from horosa_skill.exports.registry import AI_EXPORT_PRESET_SECTIONS
    from horosa_skill.service.text.predictive import _PREDICTIVE_METHOD_NOTES

    scenario = _scenario(method, name)
    client = _Client({ENDPOINT: scenario["response"]})
    result = _service(tmp_path, client, _RealJs(tmp_path)).run_tool("timelords", {**_birth(method, name), **_payload(method, name)}, save_result=False)
    assert result.ok is True, result.error
    assert client.sent() == scenario["body"]
    text = result.data["snapshot_text"]
    assert scenario["upstream"]["text"] in text
    snap = result.data["export_snapshot"]
    assert snap["missing_selected_sections"] == [] and snap["unknown_detected_sections"] == []
    titles = [s["title"] for s in snap["sections"]]
    preset = AI_EXPORT_PRESET_SECTIONS["timelords"]
    assert titles == ([t for t in preset if t not in ("当前时段", "后续")] if method == "moondays" else preset)
    assert "未返回" not in snap["export_text"], "按设计不出的段不留「未返回」占位"
    assert set(snap.get("not_requested_sections") or []) == ({"当前时段", "后续"} if method == "moondays" else set())
    assert _section(text, "方法说明").splitlines() == _PREDICTIVE_METHOD_NOTES["timelords"]   # 逐字对上游由 test_method_notes_* 守
    data = result.data
    assert data["request"] == scenario["upstream"]["request"]["fields"] and data["method"] == method
    assert data["kind"] == ("periods" if method in TIMELORD_PERIOD_METHODS else "events")
    year_field, fields = TIMELORD_METHOD_FIELDS[method]
    wanted = {"tlMethod", *([year_field] if year_field else []), *fields}
    if method == "devages" and _full_settings(method, name)["tlDevBasis"] != "house":
        wanted.discard("tlVariant")
    assert set(data["settings"]) == wanted and set(data["settings_not_applicable"]) & wanted == set()
    assert (data["target"] is None) == (method == "moondays")
    card = data["technique_card"]["settings"]
    assert {k for k in card if k.startswith("tl")} == wanted, "技法依据卡只印这一法读的口径"
    assert ("targetDate" in card) == (method != "moondays")


@requires_node
def test_every_setting_changes_the_request_and_the_text(tmp_path: Path) -> None:
    """「改这个参数，结果必须变」（离线半边：请求体 + 上游正文写出的口径）。后端结果真的变没变由 live 用例
    `test_live_every_option_changes_the_table` 守。"""
    for method in METHODS:
        default, custom = _scenario(method, "default"), _scenario(method, "custom")
        assert default["upstream"]["text"] != custom["upstream"]["text"], method
        if method != "lifetime":   # 对数时标没有口径键，custom 只换了目标日
            assert default["request_fields"] != custom["request_fields"], method
            assert default["response"]["rows"] != custom["response"]["rows"], method
    text = {(m, n): _scenario(m, n)["upstream"]["text"] for m, n in CASES}
    assert "年长：埃及 / 希腊化年（360 日）\n次序：迦勒底序\n起始星：土\n出生行星时主(不等时)：土" in text[("turn", "custom")]
    assert "年长：回归年（365.2422 日）\n次序：本命黄经序\n起始星：金" in text[("turn", "default")]
    assert "年长：恒星年（365.2564 日）\n走法：循环(二十四年)" in text[("orb", "custom")]
    assert "子段天数：乙表(金 33、火 36、木 30)\n子段次序：当年返照盘黄经序" in text[("annual", "custom")]
    assert "年长" not in text[("annual", "default")] and "年长" not in text[("lifetime", "default")] and "年长" not in text[("moondays", "default")]
    assert "年长：Bija 年（365.2588 日）\n释放星：福点" in text[("quarters", "custom")]
    assert "年长：Bija 年 · 经典（366.2564 日）" in text[("monomoiria", "custom")]
    assert "年长：Abu Ma'shar 年（365.2583 日）\n算法：经典" in text[("moonnine", "custom")]
    assert "年长：Masha'allah 年（365.2590 日）\n时间：上升时\n子主：首段子主反转\n算法：经典" in text[("nineparts", "custom")]
    assert "年长：恒星年（365.2564 日）\n速率：30°/年\n起点：上升" in text[("moving", "default")]   # 匀速点缺省恒星年
    assert "年长：回归年（365.2422 日）\n速率：72 年一周\n起点：产前朔望" in text[("moving", "custom")]
    assert "分段：按星座" in text[("devages", "default")] and "算法" not in text[("devages", "default")]
    assert "分段：按宫位\n算法：经典" in text[("devages", "custom")]
    assert "速率：四象限 90 年\n算法：经典" in text[("diurnal", "custom")]
    assert "算法：经典" in text[("moondays", "custom")] and "算法：改进" in text[("moondays", "default")]


def test_polar_circle_note_is_printed_and_the_table_falls_back_to_degrees() -> None:
    """极圈内「上升时档不成立」：后端回 polar=true、time 改回 degree，上游正文原样写出 TIMELORD_POLAR_NOTE（并把「时间」行写成度数）。
    负向对照（实跑）：vendored timeLordTables.js 的 echoLines 去掉 `if(r.polar){ lines.push(TIMELORD_POLAR_NOTE); }` →
    test_vendored_progextra_equals_upstream[nineparts-polar] 红（本条断言的是上游金标，随夹具重生才会变）。"""
    polar, plain = _scenario("nineparts", "polar"), _scenario("nineparts", "custom")
    assert polar["body"]["lat"] == "70n00" and polar["request_fields"]["nineTime"] == "ascension"
    assert polar["response"]["polar"] is True and polar["response"]["time"] == "degree"
    head = _section(polar["upstream"]["text"], "时主轮转")
    assert "时间：度数(1° = 1 年)" in head and head.splitlines()[-1] == "极圈内斜升不单调,上升时档不成立,已改按度数"
    assert plain["response"]["polar"] is False and plain["response"]["time"] == "ascension"
    assert "极圈内" not in plain["upstream"]["text"] and "时间：上升时" in plain["upstream"]["text"]
    # 度数档 1° = 1 年：极圈盘每段长恒为 10⁄9 年（首段只走余量）；上升时档的段长随斜升差变。
    spans = [row["endAge"] - row["startAge"] for row in polar["response"]["rows"][1:]]
    assert max(spans) - min(spans) < 1e-9 and math.isclose(spans[0], 10 / 9, abs_tol=1e-9)
    plain_spans = [row["endAge"] - row["startAge"] for row in plain["response"]["rows"][1:]]
    assert max(plain_spans) - min(plain_spans) > 0.05


def test_boundary_targets_are_worded_like_upstream() -> None:
    """目标时刻在表尾之后 / 出生之前 / 全部事件之前：上游三种写法原样出。"""
    after, before = _scenario("turn", "past_end"), _scenario("turn", "before_birth")
    assert after["response"]["pastEnd"] is True and after["response"]["currentIndex"] == -1
    assert _section(after["upstream"]["text"], "当前时段") == "目标时刻不在列表范围内" and after["upstream"]["text"].endswith("[后续]")
    assert before["response"]["pastEnd"] is False and before["response"]["currentIndex"] == -1
    assert _section(before["upstream"]["text"], "当前时段") == "目标时刻不在列表范围内"
    assert _section(before["upstream"]["text"], "后续").splitlines()[0] == "金:1975-02-10 起,0.00 岁"
    first = _scenario("moving", "before_first")
    assert first["response"]["currentIndex"] == 0
    assert _section(first["upstream"]["text"], "当前时段") == "目标时刻之前没有事件"


# ── 值级金标：按定义手算 / 上游后端测试夹具的断言（期望值不取自回包本身）──────────────────────────────

CHALDEAN = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]
SIGN_RULERS = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter"]
LESSER_YEARS = {"Sun": 19, "Moon": 25, "Mercury": 20, "Venus": 8, "Mars": 15, "Jupiter": 12, "Saturn": 30}
CHALDEAN_RANK = {"Moon": 1, "Mercury": 2, "Venus": 3, "Sun": 4, "Mars": 5, "Jupiter": 6, "Saturn": 7}
YEAR_DAYS = {"solar": 365.242199, "sidereal": 365.256363, "hellenistic": 360.0, "bija": 365.258756, "bijaClassic": 366.256399}
DEV_LENGTHS = list(range(2, 14))


def _rows(method: str, name: str = "default") -> list[dict[str, Any]]:
    return _scenario(method, name)["response"]["rows"]


def _days_between(a: str, b: str) -> float:
    fmt = "%Y-%m-%d %H:%M:%S"
    return (datetime.strptime(b, fmt) - datetime.strptime(a, fmt)).total_seconds() / 86400


def test_values_follow_the_definitions() -> None:
    """每法至少一条值级金标。期望值的来源：上游 astropy/tests/test_timelord_tables.py 的断言（同一张西雅图盘：上升天秤、行星时主土星）
    与各法的定义手算（序、段长、年龄换算）——不是把回包抄成期望。
    负向对照（实跑，离线：改夹具里的回包再跑本条）：见备忘「验证」一节逐条；live 侧 `test_live_engine_reproduces_the_fixture` 守引擎 == 夹具。"""
    turn = _scenario("turn", "default")["response"]
    # 轮主：上升天秤（上游 test_turn_starts_from_the_ascendant_ruler_by_default：首段金星）→ 起始星 = 座主金星，一年一段、百年百段。
    assert turn["ascSign"] == 6 and SIGN_RULERS[6] == "Venus"
    assert turn["startLord"] == "Venus" and turn["rows"][0]["lord"] == "Venus" and len(turn["rows"]) == 100
    assert [(r["startAge"], r["endAge"]) for r in turn["rows"][:3]] == [(0.0, 1.0), (1.0, 2.0), (2.0, 3.0)]
    ring = [r["lord"] for r in turn["rows"][:7]]
    assert sorted(ring) == sorted(CHALDEAN) and [r["lord"] for r in turn["rows"][7:14]] == ring   # 七星一轮、循环
    assert turn["rows"][0]["start"] == "1975-02-10 21:15:00"
    assert math.isclose(_days_between(turn["rows"][0]["start"], turn["rows"][50]["start"]), 50 * YEAR_DAYS["solar"], abs_tol=1e-4)
    # 行星时主用昼夜不等时（上游 test_hour_lord_uses_seasonal_hours：土星）；迦勒底序从土星起 = 土木火日金水月；360 日年。
    custom = _scenario("turn", "custom")["response"]
    assert custom["hourLord"] == "Saturn" and custom["startLord"] == "Saturn"
    assert [r["lord"] for r in custom["rows"][:8]] == [*CHALDEAN, "Saturn"]
    assert math.isclose(_days_between(custom["rows"][0]["start"], custom["rows"][50]["start"]), 50 * 360.0, abs_tol=1e-4)
    # 轨主：单轮沿十二宫座主走、十二年一周；循环档走迦勒底序、二十四年后重头（上游 test_orb_*）。
    single = [r["lord"] for r in _rows("orb")]
    asc_ring = [SIGN_RULERS[(6 + i) % 12] for i in range(12)]
    first = asc_ring.index("Saturn")   # 从第一个座主 = 行星时主（土星）的宫起
    assert single[:12] == asc_ring[first:] + asc_ring[:first] and single[12:24] == single[:12]
    cycle = [r["lord"] for r in _rows("orb", "custom")]
    assert cycle[:8] == [*CHALDEAN, "Saturn"] and cycle[24:32] == cycle[:8] and cycle[21:24] == ["Saturn", "Jupiter", "Mars"]
    # 年度分配：首段 = 出生到首个太阳返照、年主 = 上升座主，其后逐座；子段七星、甲表合 328 日（53+70+22+22+42+34+85）、乙表 329 日。
    annual, annual_b = _rows("annual"), _rows("annual", "custom")
    assert annual[0]["startAge"] == 0.0 and [r["lord"] for r in annual[:3]] == ["Venus", "Mars", "Jupiter"]
    assert abs(annual[1]["startAge"] - 1.0) < 0.01
    table_a = {"Sun": 53, "Moon": 70, "Mercury": 22, "Venus": 22, "Mars": 42, "Jupiter": 34, "Saturn": 85}
    table_b = {**table_a, "Venus": 33, "Mars": 36, "Jupiter": 30}
    for rows, table in ((annual, table_a), (annual_b, table_b)):
        for row in rows[:5]:
            assert len(row["children"]) == 7 and row["children"][0]["lord"] == row["lord"]
            assert {c["lord"]: c["days"] for c in row["children"]} == table
    assert sum(table_a.values()) == 328 and sum(table_b.values()) == 329
    assert [c["lord"] for c in annual[1]["children"]] != [c["lord"] for c in annual_b[1]["children"]]   # 返照盘黄经序 ≠ 本命黄经序
    # 月相四分：段长 = 小年 × 90 日；缺省释放星月亮 → 首段月亮 25 × 90；每轮七段、下一轮起点后移 3 位；子段 = 段长 × 小年 ⁄ 129。
    quarters = _rows("quarters")
    order = [r["lord"] for r in quarters[:7]]
    assert quarters[0]["lord"] == "Moon" and all(r["days"] == LESSER_YEARS[r["lord"]] * 90.0 for r in quarters)
    assert [r["lord"] for r in quarters[7:14]] == order[3:] + order[:3] and quarters[7]["cycle"] == 2
    assert math.isclose(quarters[0]["endAge"], 25 * 90 / 360, abs_tol=1e-12)
    assert all(math.isclose(c["days"], quarters[0]["days"] * LESSER_YEARS[c["lord"]] / 129.0, abs_tol=1e-9) for c in quarters[0]["children"])
    assert _scenario("quarters", "custom")["response"]["releaser"] == "Pars Fortuna"
    # 月亮单度主：年数 = 迦勒底序位（月 1 … 土 7），一轮合 28 年；下一轮起点按黄经序后移 1 位。
    mono = _rows("monomoiria")
    assert all(r["days"] == CHALDEAN_RANK[r["lord"]] * 360.0 for r in mono)
    assert sum(r["days"] for r in mono[:7]) == 28 * 360.0 and math.isclose(mono[7]["startAge"], 28.0, abs_tol=1e-9)
    assert mono[7]["lord"] == mono[1]["lord"] and mono[0]["lord"] == _scenario("monomoiria", "default")["response"]["startLord"]
    # 月亮九年：从月亮所在座起逐座，每座 3240 日 = 9 年、九个子段各 360 日；首段缺省 = 座内余下度数 × 108 日，经典档 = 已走度数 × 108 日，
    # 两档首段合起来正好一座（30° × 108 = 3240）。
    nine, nine_classic = _rows("moonnine"), _rows("moonnine", "custom")
    assert all(r["days"] == 3240.0 and r["lord"] == SIGN_RULERS[r["sign"]] for r in nine[1:])
    assert [r["sign"] for r in nine[:4]] == [(nine[0]["sign"] + i) % 12 for i in range(4)]
    assert math.isclose(nine[0]["days"] + nine_classic[0]["days"], 3240.0, abs_tol=1e-6)
    assert [round(c["days"], 9) for c in nine[1]["children"]] == [360.0] * 9
    # 九分主：单元 10⁄9°、度数档 1° = 1 年 → 首段只走余量（< 10⁄9 年），其后每段正好 10⁄9 年；子主三段一轮。
    parts = _rows("nineparts")
    assert 0 < parts[0]["endAge"] < 10 / 9 and all(math.isclose(r["endAge"] - r["startAge"], 10 / 9, abs_tol=1e-9) for r in parts[1:])
    asc = parts[0]["from"]
    assert math.isclose(parts[0]["endAge"], (math.floor(asc / (10 / 9) + 1e-9) + 1) * (10 / 9) - asc, abs_tol=1e-9)
    # 匀速点：从上升按 30°/年匀速走，年龄 = 弧 ⁄ 速率；上升合自己在 0 岁。72 年一周 = 5°/年。恒星年换日期。
    moving = _scenario("moving", "default")["response"]
    start = next(r["at"] for r in moving["rows"] if r["point"] == "Asc" and r["aspect"] == 0)
    assert math.isclose(start, asc, abs_tol=1e-9) and moving["yearType"] == "sidereal" and moving["rate"] == 30.0
    for row in moving["rows"][::37]:
        assert math.isclose((start + row["age"] * 30.0 - row["at"] + 180.0) % 360.0 - 180.0, 0.0, abs_tol=1e-6)
    age72 = _scenario("moving", "custom")["response"]
    assert age72["rate"] == 5.0 and age72["startPoint"] == "Syzygy" and age72["yearType"] == "solar"
    probe = moving["rows"][200]
    assert math.isclose(_days_between("1975-02-10 21:15:00", probe["date"]), probe["age"] * YEAR_DAYS["sidereal"], abs_tol=2e-5)
    # 发展年龄（按星座）：十二段依次 2..13 年合 90 年，段内线性：年龄 = Σ前段 + 本段 ×（座内度数 ⁄ 30）。
    assert sum(DEV_LENGTHS) == 90
    for row in _rows("devages"):
        sign = int(row["at"] // 30)
        assert math.isclose(row["age"], sum(DEV_LENGTHS[:sign]) + DEV_LENGTHS[sign] * (row["at"] - sign * 30.0) / 30.0, abs_tol=1e-9)
    # 周日象限：十二个座首都列出（上游 test_sign_heads_are_listed）；四象限经典档上升排在一周末尾、年龄 > 61（test_quadrant_option_*）。
    assert {f"sign:{i}" for i in range(12)} <= {r["point"] for r in _rows("diurnal")}
    quadrant_asc = [r for r in _rows("diurnal", "custom") if r["point"] == "Asc"]
    assert len(quadrant_asc) == 1 and quadrant_asc[0]["age"] > 61.0 and math.isclose(quadrant_asc[0]["at"], asc, abs_tol=1e-9)
    assert all(0 <= r["age"] <= 60.0 + 1e-9 for r in _rows("diurnal"))   # 每宫 5 年 × 十二宫
    # 对数时标：年龄 + c = c × 10^(θ ⁄ 120)，c = 279.7755 日，θ = 点自上升逆时针的弧；第 1 宫头（Placidus = 上升）在 0 岁。
    life = _rows("lifetime")
    c_days = 279.7755
    house1 = next(r for r in life if r["point"] == "House1" and r["aspect"] == 0)
    assert math.isclose(house1["at"], asc, abs_tol=1e-9) and abs(house1["age"]) < 1e-9
    for row in life[::11]:
        theta = (row["at"] - asc) % 360.0
        ages = [c_days * (10.0 ** (theta / 120.0) - 1.0) / YEAR_DAYS["solar"]]
        if theta >= 240.0 - 1e-9:
            ages.append(c_days * (10.0 ** ((theta - 360.0) / 120.0) - 1.0) / YEAR_DAYS["solar"])
        assert any(math.isclose(row["age"], age, abs_tol=1e-9) for age in ages), row
    assert any(r["point"] == "MC" for r in life) and all(r["point"] != "Asc" for r in life)
    # 月亮日：第 3 / 7 / 40 日 ↔ 本命月加 30° / 90° / 180°；月亮一天约 13.2° → 改进档第 40 日约在第 41 天（第二次到冲），经典档取第一次到冲（约第 14 天）。
    improved, classic = _rows("moondays"), _rows("moondays", "custom")
    assert [(r["day"], r["arc"]) for r in improved] == [(3, 30.0), (7, 90.0), (40, 180.0)]
    assert 38.0 < improved[2]["afterDays"] < 43.0 and 12.0 < classic[2]["afterDays"] < 16.0
    assert [r["afterDays"] for r in improved[:2]] == [r["afterDays"] for r in classic[:2]]
    assert 1.5 < improved[0]["afterDays"] < 3.5 and 5.5 < improved[1]["afterDays"] < 8.5   # 30° ⁄ 13.2 ≈ 2.3 天，90° ⁄ 13.2 ≈ 6.8 天
    natal_moon = (improved[0]["at"] - 30.0) % 360.0
    assert [math.isclose((r["at"] - natal_moon) % 360.0, r["arc"], abs_tol=1e-9) for r in improved] == [True] * 3
    assert math.isclose(natal_moon, (nine[0]["sign"] * 30.0 + 30.0 - nine[0]["days"] / 108.0) % 360.0, abs_tol=1e-6)   # 与月亮九年首段互证


# ── 入口：词表、报错、不下发的键 ────────────────────────────────────────────────────────────────────


@requires_node
def test_methods_can_be_named_in_chinese(tmp_path: Path) -> None:
    """每一法都能点名调用：tlMethod 收规范值，也收上游中文名（解读进 warnings）；选项的中文名同理。"""
    labels = {value: label.replace("（缺省）", "") for value, label in TIMELORD_VOCABULARIES["tlMethod"].labels.items()}
    assert len(labels) == 12
    for method, label in labels.items():
        client = _Client()
        result = _service(tmp_path, client, _RealJs(tmp_path)).run_tool("timelords", {**_birth(method, "default"), "targetDate": TARGET, "tlMethod": label}, save_result=False)
        assert result.ok is True, (method, result.error)
        assert client.sent()["method"] == method and result.data["method"] == method
        assert f"方法：{label}(" in result.data["snapshot_text"]
        assert any("tlMethod" in w and label in w for w in result.warnings), (method, result.warnings)
    client = _Client()
    result = _service(tmp_path, client).run_tool(
        "timelords", {**_birth("turn", "default"), "targetDate": TARGET, "tlMethod": "turn", "tlTurnOrder": "迦勒底序", "tlTurnStart": "行星时主", "tlYearType": "埃及年"},
        save_result=False)
    assert result.ok is True, result.error
    assert client.sent() == _scenario("turn", "custom")["body"]   # 中文名读成的规范值 == custom 场景发出的那一份


@pytest.mark.parametrize(
    ("bad", "code"),
    [
        ({"tlMethod": "nope"}, "tool.invalid_option"),
        ({"tlMethod": "turn", "tlTurnOrder": "sideways"}, "tool.invalid_option"),
        ({"tlMethod": "turn", "tlYearType": "lunar"}, "tool.invalid_option"),
        ({"tlMethod": "moving", "tlMovingStart": "Pluto"}, "tool.invalid_option"),
        ({"tlMethod": "quarters", "tlReleaser": "Asc"}, "tool.invalid_option"),
        ({"tlMethod": "nineparts", "tlNineReverse": "maybe"}, "tool.predictive_invalid_option"),
        ({"tlMethod": "turn", "targetDate": "2026-13-01"}, "tool.directed_invalid_target"),
        ({"tlMethod": "turn", "targetTime": "25:00"}, "tool.directed_invalid_target"),
    ],
)
def test_bad_options_fail_loudly(tmp_path: Path, bad: dict[str, Any], code: str) -> None:
    """上游 normalizeTimeLordOpts 与后端 build_timelords 都会把认不出的值静默换成缺省（方法认不出 → 轮主）= 算出另一张表而不自知；
    skill 一律报错，且不发请求。负向对照（实跑）：TimeLordsInput 去掉 field_validator → 前五条不再是 tool.invalid_option。"""
    client = _Client()
    try:
        result = _service(tmp_path, client).run_tool("timelords", {**_birth("turn", "default"), **bad}, save_result=False)
        got = result.error.code if result.error else None
        assert result.ok is False
    except Exception as exc:  # run_tool 对校验错误直接抛结构化异常
        got = getattr(exc, "code", None)
    assert got == code
    assert not [e for e, _p in client.calls if e == ENDPOINT]


def test_settings_another_method_reads_are_reported_not_sent(tmp_path: Path) -> None:
    """所选方法不读的口径键：不下发、回执 settings_ignored + 一条告警（上游挂载齿轮用 showWhen 把它们藏起来，headless 没有那层界面）。
    月亮日不看目标日，但 targetDate 不为此告警（dispatch 对这类技法恒带目标日）。
    负向对照（实跑）：_timelord_result_extras 里去掉 settings_ignored / _warnings 两行 → 红。"""
    client = _Client()
    result = _service(tmp_path, client).run_tool(
        "timelords", {**_birth("orb", "default"), "tlMethod": "orb", "tlTurnOrder": "chaldean", "tlVariant": "classic", "tlOrbMode": "cycle"}, save_result=False)
    assert result.ok is True, result.error
    assert result.data["settings_ignored"] == ["tlTurnOrder", "tlVariant"]
    assert any("tlTurnOrder、tlVariant" in w and "轨主" in w for w in result.warnings)
    sent = client.sent()
    assert sent["orbMode"] == "cycle" and "turnOrder" not in sent and "variant" not in sent
    quiet = _service(tmp_path, _Client()).run_tool("timelords", {**_birth("moondays", "default"), "tlMethod": "moondays", "targetDate": TARGET}, save_result=False)
    assert quiet.ok is True and "settings_ignored" not in quiet.data and not quiet.warnings
    # 发展年龄按星座分段时两档算法同值：tlVariant 不下发（上游 timeLordFields），给了就回执。
    sign = _service(tmp_path, client).run_tool("timelords", {**_birth("devages", "default"), "tlMethod": "devages", "tlVariant": "classic"}, save_result=False)
    assert sign.data["settings_ignored"] == ["tlVariant"] and "variant" not in client.sent()
    house = _service(tmp_path, client).run_tool(
        "timelords", {**_birth("devages", "default"), "tlMethod": "devages", "tlDevBasis": "house", "tlVariant": "classic"}, save_result=False)
    assert "settings_ignored" not in house.data and client.sent()["variant"] == "classic"


def test_raw_backend_keys_are_not_forwarded(tmp_path: Path) -> None:
    """后端认的裸键（method / yearType / maxAge / turnOrder …）不许绕过词表混进请求体：星阙页面与挂载从不发 maxAge，Java 白名单也不放行；
    skill 直连 chart 服务没有那层白名单。负向对照（实跑）：_directed_figure_body 不并入 _TIMELORD_RAW_KEYS → 红（maxAge=3、variant 进了请求体）。"""
    client = _Client()
    payload = {**_birth("turn", "default"), "tlMethod": "turn", "method": "orb", "maxAge": 3}
    result = _service(tmp_path, client).run_tool("timelords", payload, save_result=False)
    assert result.ok is True, result.error
    sent = client.sent()
    assert {k: sent[k] for k in ("method", "yearType", "turnOrder")} == {"method": "turn", "yearType": "solar", "turnOrder": "zodiac"}
    assert "maxAge" not in sent and "variant" not in sent
    # 审计 S-13：与本技法参数只差前缀、又不是任何技法参数名的后端裸键（turnOrder ~ tlTurnOrder）拒绝并点名——以前只告警、按缺省次序照算，
    # 调用方要的是 house 次序，拿到的是 zodiac 的表。yearType / variant 是别的技法真有的参数名（合参会把它们交过来），只告警、不下发。
    with pytest.raises(ToolValidationError) as excinfo:
        _service(tmp_path, _Client()).run_tool("timelords", {**payload, "turnOrder": "house"}, save_result=False)
    assert excinfo.value.code == "tool.unknown_argument" and "`tlTurnOrder`" in str(excinfo.value)
    client = _Client()
    other = _service(tmp_path, client).run_tool("timelords", {**payload, "yearType": "hellenistic", "variant": "classic"}, save_result=False)
    assert other.ok is True and "variant" not in client.sent() and client.sent()["yearType"] == "solar"


def test_backend_echo_mismatch_is_an_error(tmp_path: Path) -> None:
    """后端对认不出 / 算不出的值静默回落缺省；回显的方法 / 年长 / 选项与请求不符 = 另一张表，报错而不是配着请求的标题返回。
    负向对照（实跑）：_timelord_result_extras 去掉回显比对 → 三条都 ok=true。"""
    wrong_method = _scenario("turn", "default")["response"]
    result = _service(tmp_path, _Client({ENDPOINT: wrong_method})).run_tool("timelords", {**_birth("orb", "default"), "tlMethod": "orb"}, save_result=False)
    assert result.ok is False and result.error.code == "tool.timelords_echo_mismatch"
    assert result.error.details["requested"]["method"] == "orb" and result.error.details["echoed"]["method"] == "turn"
    wrong_year = {**_scenario("turn", "default")["response"], "yearType": "solar"}
    result = _service(tmp_path, _Client({ENDPOINT: wrong_year})).run_tool(
        "timelords", {**_birth("turn", "default"), "tlMethod": "turn", "tlYearType": "hellenistic"}, save_result=False)
    assert result.ok is False and result.error.code == "tool.timelords_echo_mismatch"
    # 后端真会这样回落：释放星选产前朔望而朔望求不出 → 按月亮算、回显 releaser=Moon（timelord_tables._build_quarters）。
    fell_back = _scenario("quarters", "default")["response"]   # releaser == "Moon"
    result = _service(tmp_path, _Client({ENDPOINT: fell_back})).run_tool(
        "timelords", {**_birth("quarters", "default"), "tlMethod": "quarters", "tlReleaser": "Syzygy"}, save_result=False)
    assert result.ok is False and result.error.code == "tool.timelords_echo_mismatch"
    assert result.error.details["requested"]["releaser"] == "Syzygy" and result.error.details["echoed"]["releaser"] == "Moon"
    # 极圈内九分主上升时档改按度数：不是静默回落（正文写明），照常返回。
    polar = _scenario("nineparts", "polar")
    ok = _service(tmp_path, _Client({ENDPOINT: polar["response"]})).run_tool(
        "timelords", {**_birth("nineparts", "polar"), **_payload("nineparts", "polar")}, save_result=False)
    assert ok.ok is True and polar["response"]["time"] == "degree" and polar["request_fields"]["nineTime"] == "ascension"


@requires_node
def test_echo_table_equals_the_vendored_echo_fields() -> None:
    """runner 的回显核对表 == vendored timeLordTables.js 的 ECHO_FIELDS（上游用它把口径写进正文；未导出，按源码字面量取）；
    夹具里每个场景的回显都与请求相符（表里的键是后端真回的键）。
    负向对照（实跑）：_TIMELORD_ECHO["moving"] 的 startPoint 写成 start → 红（两条断言各一处）。"""
    from node_esm import run_node_esm

    source = (CORE_JS / "src" / "vendor" / "utils" / "timeLordTables.js").read_text(encoding="utf-8")
    literal = re.search(r"const ECHO_FIELDS = (\{.*?\n\});", source, re.S)
    assert literal, "vendored timeLordTables.js no longer declares ECHO_FIELDS"
    js = json.loads(run_node_esm(f"console.log(JSON.stringify({literal.group(1)}))", cwd=CORE_JS, timeout=60))
    assert R._TIMELORD_ECHO == js
    for method, name in CASES:
        scenario = _scenario(method, name)
        for response_key, request_key in R._TIMELORD_ECHO.get(method, {}).items():
            assert response_key in scenario["response"], (method, name, response_key)
            if request_key in scenario["request_fields"] and not (request_key == "nineTime" and scenario["response"].get("polar")):
                wanted = scenario["request_fields"][request_key]
                assert scenario["response"][response_key] == (bool(wanted) if request_key == "nineReverse" else wanted), (method, name, request_key)


def test_empty_backend_result_is_a_structured_error(tmp_path: Path) -> None:
    """上游 builder 无数据返回 ''（挂载显示「缺失」）；skill 侧空快照会落 generated_template 假导出——一律报错（AGENTS §5.9）。"""
    empty = {**_scenario("turn", "default")["response"], "rows": []}
    result = _service(tmp_path, _Client({ENDPOINT: empty})).run_tool("timelords", {**_birth("turn", "default"), "tlMethod": "turn"}, save_result=False)
    assert result.ok is False and result.error.code == "tool.timelords_empty"


@requires_node
def test_runner_cross_checks_python_against_upstream_mapping(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Python 移植的 timeLordRequestFields 一旦与 vendored 上游函数不一致（progextra 回传 request_fields），runner 报错而不是拿错请求体
    算出的表照常返回。这条本身就是负向对照：把移植改坏（恒发 turnOrder）→ tool.directed_request_mismatch。"""
    original = R._directed_figure_request_fields

    def drifted(technique: str, settings: dict[str, Any]) -> dict[str, Any]:
        return {**original(technique, settings), "turnOrder": "zodiac"}

    monkeypatch.setattr(R, "_directed_figure_request_fields", staticmethod(drifted))
    result = _service(tmp_path, _Client(), _RealJs(tmp_path)).run_tool("timelords", {**_birth("orb", "default"), "tlMethod": "orb"}, save_result=False)
    assert result.ok is False and result.error.code == "tool.directed_request_mismatch"
    assert "turnOrder" in result.error.details["sent"] and "turnOrder" not in result.error.details["upstream"]


def test_default_target_is_today_in_the_chart_zone(tmp_path: Path, frozen: None) -> None:
    """targetDate 缺省 = 本盘时区今日（上游 today(chartZone)），targetTime 缺省 12:00:00（冻结此刻 = 2026-10-30 04:00 UTC，西八区还是 29 日）。"""
    client = _Client()
    _service(tmp_path, client).run_tool("timelords", {**_birth("turn", "default"), "tlMethod": "turn"}, save_result=False)
    assert (client.sent()["targetDate"], client.sent()["targetTime"]) == ("2026-10-29", "12:00:00")


# ── 广告层 / 指引 / 路由 / 导出登记 ─────────────────────────────────────────────────────────────────


def test_advertised_surface_guidance_and_gate() -> None:
    """tools/list 只广告方法与目标日，十五个口径键隐藏但 guidance 里逐个有说明；闸门先问方法（不默认成轮主）。"""
    from horosa_skill.agent_guidance import TOOL_GUIDANCE, build_agent_guidance
    from horosa_skill.engine.registry import TOOL_DEFINITIONS
    from horosa_skill.surfaces.mcp_schema import advertise_hidden_fields

    definition = TOOL_DEFINITIONS["timelords"]
    assert (definition.domain, definition.execution) == ("predict", "local")
    hidden = advertise_hidden_fields(definition.input_model)
    assert {k for k in TIMELORD_DEFAULTS if k != "tlMethod"} <= hidden and "tlMethod" not in hidden and "targetDate" not in hidden
    assert {"zodiacal", "siderealAyanamsa", "targetTime"} <= hidden
    guidance = build_agent_guidance(tool_name="timelords")["tools"]["timelords"]
    keys = guidance["options_keys"]
    assert hidden <= set(keys)
    for method, (year_field, fields) in TIMELORD_METHOD_FIELDS.items():
        wanted = " ".join([*([year_field] if year_field else []), *fields]) or "无口径键"
        label = TIMELORD_VOCABULARIES["tlMethod"].labels[method].replace("（缺省）", "")
        assert f"{method} {label}（{wanted}）" in keys["tlMethod"], method
    question = {item["field"]: item for item in TOOL_GUIDANCE["timelords"]["ask_if_missing"]}["tlMethod"]
    assert tuple(question["values"]) == METHODS and len(question["options"]) == 12
    for value, option in zip(question["values"], question["options"]):
        assert option.startswith(TIMELORD_VOCABULARIES["tlMethod"].labels[value].replace("（缺省）", "")), value
    defaults = {item["field"]: item["value"] for item in TOOL_GUIDANCE["timelords"]["safe_defaults"] if item["field"] in TIMELORD_DEFAULTS}
    assert defaults == TIMELORD_DEFAULTS


def test_gate_asks_for_the_method_before_computing(tmp_path: Path) -> None:
    """没给方法、也没确认按默认：闸门拦下并问用哪一法（铁律 2）；给了方法就不再问它；确认按默认后才按轮主算。
    负向对照（实跑）：TIMELORDS_POLICY 的 targets 去掉 tlMethod 那一问 → 第一条不再问方法 → 红。"""
    from horosa_skill.agent_guidance import validate_agent_preflight

    birth = {k: v for k, v in _birth("turn", "default").items() if k != "agent_confirmed_settings"}
    blocked = validate_agent_preflight("timelords", {**birth, "targetDate": TARGET})
    assert blocked["ok"] is False and blocked["code"] == "agent_guidance.required"
    asked = {item["field"]: item for item in blocked["ask_if_missing"]}
    # 十二个选项超过追问里逐条列出的上限（MAX_SPELLED_OPTIONS）：十二法的名字写在问题里，中英各一遍。
    assert asked["tlMethod"]["options_count"] == 12
    for value, label in TIMELORD_VOCABULARIES["tlMethod"].labels.items():
        assert label.replace("（缺省）", "") in asked["tlMethod"]["question"] and value in asked["tlMethod"]["question"], value
    named = validate_agent_preflight("timelords", {**birth, "targetDate": TARGET, "tlMethod": "moonnine"})
    assert "tlMethod" not in {item["field"] for item in named.get("ask_if_missing") or []}
    assert validate_agent_preflight("timelords", {**birth, "defaults_accepted": True})["ok"] is True
    client = _Client()
    accepted = _service(tmp_path, client).run_tool("timelords", {**birth, "targetDate": TARGET, "defaults_accepted": True}, save_result=False)
    assert accepted.ok is True and client.sent()["method"] == "turn"


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("看一下我的时主轮转", ["timelords"]),
        ("我现在的轮主是哪颗星", ["timelords"]),
        ("轨主怎么排", ["timelords"]),
        ("年度分配法看今年", ["timelords"]),
        ("月相四分的当前段", ["timelords"]),
        ("月亮单度主", ["timelords"]),
        ("月亮九年走到哪一座", ["timelords"]),
        ("九分主的当前段主", ["timelords"]),
        ("匀速点走到哪个相位了", ["timelords"]),
        ("发展年龄对应的点", ["timelords"]),
        ("周日象限的年龄表", ["timelords"]),
        ("对数时标看人生节点", ["timelords"]),
        ("出生后的月亮日时刻", ["timelords"]),
        ("timelords table for my chart", ["timelords"]),
        ("time lord rotation periods", ["timelords"]),
        # 互斥：别名相近的技法各归各的
        ("界推运分配法", ["distributions"]),
        ("周日小限今年落哪宫", ["jayprofection"]),
        ("年龄推进点", ["agepoint"]),
        ("三分主星推运", ["triplicityrulers"]),
        ("月相推运", ["lunationphase"]),
    ],
)
def test_router_names_every_method_and_keeps_neighbours_apart(query: str, expected: list[str]) -> None:
    """负向对照（实跑）：router 的界推运那条改回含「分配法」不排除「年度分配」→「年度分配法看今年」同时点亮 distributions → 红。"""
    from horosa_skill.engine.router import select_tools
    from horosa_skill.schemas.tools import DispatchInput

    assert select_tools(DispatchInput(query=query)) == expected


def test_router_does_not_mistake_ordinary_words_for_a_method() -> None:
    """「轮主」两个字会出现在「这一轮主要看…」里；「月亮日」在印度 / 藏历语境里是 tithi。"""
    from horosa_skill.engine.router import _TIMELORD_MOONDAY_EXCLUDE, _TIMELORD_TURN_RE, _TIMELORD_WORDS, _contains_any

    def hits(text: str) -> bool:
        return bool(_contains_any(text, _TIMELORD_WORDS) or _TIMELORD_TURN_RE.search(text)
                    or ("月亮日" in text and not _contains_any(text, _TIMELORD_MOONDAY_EXCLUDE)))

    assert not hits("这一轮主要看财运") and not hits("本轮主题是感情") and hits("今年的轮主")
    assert not hits("印度占星里的月亮日 tithi") and hits("月亮日")
    assert not hits("周日小限") and not hits("分配法") and not hits("年龄点") and not hits("三分主")


def test_registered_everywhere_a_predictive_tool_must_be() -> None:
    from horosa_skill.decisions.surfaces.routing import FAMILIES
    from horosa_skill.engine.synonyms import TOOL_SYNONYMS
    from horosa_skill.engine.time_roles import NATAL_TARGET, TARGET_STYLE, TIME_ROLES
    from horosa_skill.exports.registry import (
        AI_EXPORT_OPTIONAL_SECTIONS,
        AI_EXPORT_PRESET_SECTIONS,
        AI_EXPORT_SECTION_MIGRATION_KEYS,
        get_technique_info,
    )
    from horosa_skill.service.endpoints import _PYTHON_CHART_ENDPOINTS

    assert ENDPOINT in _PYTHON_CHART_ENDPOINTS
    assert TIME_ROLES["timelords"] == NATAL_TARGET and TARGET_STYLE["timelords"] == "targetDate"
    assert "timelords" in FAMILIES["western_predictive"][1] and TOOL_SYNONYMS["timelords"][0] == "时主轮转"
    assert AI_EXPORT_PRESET_SECTIONS["timelords"] == ["起盘信息", "时主轮转", "当前时段", "后续", "当前时点", "方法说明"]
    assert AI_EXPORT_OPTIONAL_SECTIONS["timelords"] == ["当前时段", "后续"] and "timelords" in AI_EXPORT_SECTION_MIGRATION_KEYS
    info = get_technique_info("timelords")
    assert info["label"] == "星运-时主轮转" and info["supports_planet_info"] is False and info["supports_astro_meaning"] is True


def test_traditional_script_keeps_diurnal_and_cycle_wording() -> None:
    """繁体输出（AGENTS §4.5 新术语）：「周日象限」是周日运动的周日，不是星期日；「28 年一周 / 盘面一周」是走满一圈，不是一星期——
    词典会转成「週日象限」「一週」，上游 hantRules.js 也没收这几词（只报上游）。本仓在 horosa_char_rules.json 的「周」字白名单里钉住。
    其余新术语（轮主 / 轨主 / 匀速点 / 发展年龄 / 对数时标 / 极圈说明）随词典即对。
    负向对照（实跑）：从 horosa_char_rules.json 去掉「周日象限」一词 → 红（週日象限）。"""
    from horosa_skill import textscript as ts

    def hant(text: str) -> str:
        return ts.convert(text, ts.TRADITIONAL)

    assert hant(_scenario("diurnal", "custom")["upstream"]["text"].splitlines()[1]) == "方法：周日象限(移動點從上升起順時針走,依次過 12、11 … 1 宮)"
    assert hant("速率：72 年一周") == "速率：72 年一周" and hant("速率：28 年一周") == "速率：28 年一周"
    assert "盤面一周按對數時標換成一生" in hant(_scenario("lifetime", "default")["upstream"]["text"])
    from horosa_skill.service.text.predictive import _PREDICTIVE_METHOD_NOTES

    assert "事件類(勻速點、發展年齡、周日象限、對數時標、月亮日)" in hant(_PREDICTIVE_METHOD_NOTES["timelords"][0])
    assert hant("极圈内斜升不单调,上升时档不成立,已改按度数") == "極圈內斜升不單調,上升時檔不成立,已改按度數"
    assert hant("方法：轮主(一年一段,沿所选次序循环)") == "方法：輪主(一年一段,沿所選次序循環)"
    assert hant("方法：轨主(从出生时的行星时主起,一年一段)") == "方法：軌主(從出生時的行星時主起,一年一段)"
    assert hant("冥 248 年一周),交点与阿拉伯点不向运") == "冥 248 年一周),交點與阿拉伯點不向運"
    assert hant("下周日见") == "下週日見"   # 星期日仍照词典
    # 段名来回：AI 从繁体输出里抄回来的段名对回原名。
    from horosa_skill.exports.registry import AI_EXPORT_PRESET_SECTIONS

    for title in AI_EXPORT_PRESET_SECTIONS["timelords"]:
        assert ts.canonical_name(hant(title), AI_EXPORT_PRESET_SECTIONS["timelords"]) == title


# ── live（共享的 vendored v3.14.0 引擎）────────────────────────────────────────────────────────────


from test_local_js_tools import make_service, requires_chart, requires_current_runtime_contract  # noqa: E402


def _live(tmp_path: Path, method: str, birth: str = "seattle", **knobs: Any) -> Any:
    result = make_service(tmp_path).run_tool(
        "timelords", {**BIRTHS[birth], "agent_confirmed_settings": True, "targetDate": TARGET, "tlMethod": method, **knobs}, save_result=False)
    assert result.ok is True, (method, knobs, result.error)
    return result


@requires_current_runtime_contract
@requires_chart
@pytest.mark.parametrize(("method", "name"), CASES)
def test_live_engine_reproduces_the_fixture(tmp_path: Path, method: str, name: str) -> None:
    """引擎现在回的 == 夹具里实抓的（行逐值相同）；正文 == 上游金标；导出干净。上游改了算法 → 这里红 → 重生夹具并复核值级金标。"""
    scenario = _scenario(method, name)
    payload = {k: v for k, v in _payload(method, name).items() if k != "tlMethod"}
    result = _live(tmp_path, method, PLAN[method][name].get("_birth", "seattle"), **payload)
    raw = result.data["raw"]
    assert raw["rows"] == scenario["response"]["rows"]
    for key in ("kind", "method", "yearType", "currentIndex", "pastEnd", "hourLord", "ascSign", "startLord", "polar", "target"):
        assert raw.get(key) == scenario["response"].get(key), key
    assert scenario["upstream"]["text"] in result.data["snapshot_text"]
    snap = result.data["export_snapshot"]
    assert snap["missing_selected_sections"] == [] and snap["unknown_detected_sections"] == []


# 上游 astropy/tests/test_timelord_tables.py::test_every_option_changes_the_table 的参数表（页面键）。
_LIVE_OPTION_PAIRS = [
    ("turn", "tlTurnOrder", "zodiac", "chaldean"), ("turn", "tlTurnOrder", "astronomical", "house"), ("turn", "tlTurnStart", "asc", "hour"),
    ("turn", "tlYearType", "solar", "hellenistic"), ("orb", "tlOrbMode", "single", "cycle"), ("annual", "tlAnnualDays", "tableA", "tableB"),
    ("annual", "tlAnnualOrder", "natal", "return"), ("quarters", "tlReleaser", "Moon", "Sun"), ("quarters", "tlReleaser", "Moon", "Pars Fortuna"),
    ("quarters", "tlReleaser", "Moon", "Pars Spirit"), ("quarters", "tlReleaser", "Moon", "Syzygy"),
    ("quarters", "tlYearType", "solar", "hellenistic"), ("monomoiria", "tlYearType", "solar", "hellenistic"),
    ("moonnine", "tlVariant", "improved", "classic"), ("moonnine", "tlYearType", "solar", "hellenistic"),
    ("nineparts", "tlNineTime", "degree", "ascension"), ("nineparts", "tlNineReverse", False, True),
    ("nineparts", "tlVariant", "improved", "classic"), ("nineparts", "tlYearType", "solar", "hellenistic"),
    ("moving", "tlRateKind", "condition", "quadrant28"), ("moving", "tlRateKind", "condition", "age72"),
    ("moving", "tlMovingStart", "Asc", "MC"), ("moving", "tlMovingStart", "Asc", "Sun"), ("moving", "tlMovingStart", "Asc", "Syzygy"),
    ("moving", "tlMovingYear", "sidereal", "solar"), ("devages", "tlDevBasis", "sign", "house"), ("devages", "tlYearType", "solar", "hellenistic"),
    ("diurnal", "tlDiurnalMode", "five", "seven"), ("diurnal", "tlDiurnalMode", "five", "quadrant"),
    ("diurnal", "tlVariant", "improved", "classic"), ("diurnal", "tlYearType", "solar", "hellenistic"),
    ("moondays", "tlVariant", "improved", "classic"),
    ("turn", "tlYearType", "bija", "bijaClassic"), ("turn", "tlYearType", "abumashar", "mashaallah"), ("turn", "tlYearType", "solar", "sidereal"),
]


@requires_current_runtime_contract
@requires_chart
@pytest.mark.parametrize(("method", "field", "one", "other"), _LIVE_OPTION_PAIRS)
def test_live_every_option_changes_the_table(tmp_path: Path, method: str, field: str, one: Any, other: Any) -> None:
    """「改这个参数，结果必须变」：每个口径键的每一档都真的到了后端——两档算出的表不同，正文也不同。
    负向对照（实跑）：_TIMELORD_REQUEST_KEYS 把 tlRateKind 映成 rateKindX → 后端回落 30°/年，moving×2 红（先被 request_mismatch 拦下）。"""
    a, b = _live(tmp_path, method, **{field: one}), _live(tmp_path, method, **{field: other})
    assert a.data["raw"]["rows"] != b.data["raw"]["rows"]
    assert a.data["snapshot_text"] != b.data["snapshot_text"]
    assert a.data["request"] != b.data["request"]


@requires_current_runtime_contract
@requires_chart
def test_live_variant_reaches_the_house_based_developmental_ages_only(tmp_path: Path) -> None:
    """发展年龄：按宫位分段时两档算法不同；按星座分段时相同（所以上游不发、skill 回执 ignored）。"""
    house = [_live(tmp_path, "devages", tlDevBasis="house", tlVariant=v).data["raw"]["rows"] for v in ("improved", "classic")]
    assert house[0] != house[1]
    sign = _live(tmp_path, "devages", tlVariant="classic")
    assert sign.data["settings_ignored"] == ["tlVariant"] and sign.data["raw"]["rows"] == _scenario("devages", "default")["response"]["rows"]


@requires_current_runtime_contract
@requires_chart
def test_live_nodes_follow_the_chart_node_setting_and_zodiac_does_not_change_the_table(tmp_path: Path) -> None:
    """南北交随本盘平 / 真交点（上游 test_nodes_follow_the_chart_node_setting）；黄道制不改结果（后端强制回归黄道），只改盘头。"""
    mean = _live(tmp_path, "devages")
    true = _live(tmp_path, "devages", westNodeType="true")
    node = lambda result: next(r["at"] for r in result.data["raw"]["rows"] if r["point"] == "North Node")  # noqa: E731
    assert abs(((node(mean) - node(true) + 180) % 360) - 180) > 0.05
    sidereal = _live(tmp_path, "turn", zodiacal=1)
    assert sidereal.data["raw"]["rows"] == _scenario("turn", "default")["response"]["rows"]
    assert "黄道：恒星黄道" in sidereal.data["snapshot_text"]


@requires_current_runtime_contract
@requires_chart
def test_live_every_method_answers_inside_the_polar_circle(tmp_path: Path) -> None:
    """极圈内十二法都有结果（上游 test_every_method_answers_inside_the_polar_circle）；九分主上升时档改按度数并写明。"""
    for method in METHODS:
        result = _live(tmp_path, method, "polar", **({"tlNineTime": "ascension"} if method == "nineparts" else {}))
        assert result.data["raw"]["rows"], method
    polar = _live(tmp_path, "nineparts", "polar", tlNineTime="ascension")
    assert "极圈内斜升不单调,上升时档不成立,已改按度数" in polar.data["snapshot_text"]
