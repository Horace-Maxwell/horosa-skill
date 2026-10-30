"""上游 v3.12.0「1582 年以前与公元前历史盘全技法校正」· skill Python 端口的值级回归钉。

上游把命盘日期的读 / 算 / 写收口到 utils/civilCalendar · civilMoment · dateTimeParse · dateStrSafe（1582-10-15 以前儒略历、
年份按历史纪年：公元前 1 年 = -1、无 0 年；日期串负年前导负号、年补足 4 位、5 位原样）。skill 手抄过的那几处
（十年大运 / 波斯向运 / 行星年龄 / ZR 当前期 / 主限距今最近行 / 产前朔望起盘 / 世俗盘求根与食盘 / 七政日期 / 农历月历）
在这里逐条对拍：

- 民用历小工具（horosa_skill/civil_calendar.py）对拍 **vendored** JS（node 跑 horosa-core-js/src/vendor，离线可跑）；
- 上游组件 / utils 里的 builder 对拍 **上游源本身**：tests/fixtures/sync313_historical_upstream.json 由
  `_upstream_goldens()` 在上游 checkout 上跑出（Babel 抽函数 + vendored 依赖，node 执行），离线测试读夹具；
  `test_fixture_matches_upstream` 在 HOROSA_SOURCE_ROOT 可用时重跑一遍，夹具与上游漂移即红。

负向对照（把移植撤回 → 必红）记在各条 docstring 里，均实际跑过。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from horosa_skill import civil_calendar as cc
from horosa_skill.engine.astroextra_snapshots import split_syzygy_datetime
from horosa_skill.engine.decennials import build_decennial_timeline

PKG = Path(__file__).resolve().parents[1]
CORE_JS = PKG / "horosa-core-js"
CORE_JS_SRC = CORE_JS / "src"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sync313_historical_upstream.json"
_UPSTREAM_ROOT = os.environ.get("HOROSA_SOURCE_ROOT")
UPSTREAM_UI = Path(_UPSTREAM_ROOT) / "Horosa-Web" / "astrostudyui" if _UPSTREAM_ROOT else None
requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
requires_upstream = pytest.mark.skipif(
    UPSTREAM_UI is None or not (UPSTREAM_UI / "node_modules" / "@babel" / "parser").is_dir(),
    reason="HOROSA_SOURCE_ROOT (upstream checkout with node_modules) not set",
)

NOW_MS = 1793318400000  # 2026-10-30T00:00:00Z：所有「此刻」冻结在这一刻


def _run_esm(script: str, *args: Any, env: dict[str, str] | None = None) -> Any:
    from node_esm import esm_argv
    import subprocess

    completed = subprocess.run(
        esm_argv(script, *args), capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, **(env or {})},
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr[-4000:])
    return json.loads(completed.stdout)


def _node(module: str, body: str, *args: str, env: dict[str, str] | None = None) -> Any:
    """import 仓内 core-js 模块 m，跑 body（可用 m / argv），打印 JSON。"""
    script = (
        "import(process.argv[1]).then(async (m) => { const argv = process.argv.slice(2);"
        f" const out = await (async () => {{ {body} }})(); process.stdout.write(JSON.stringify(out)); }});"
    )
    return _run_esm(script, CORE_JS_SRC / module, *args, env=env)


# ── 夹具里的盘（合成黄经，日期是主角）───────────────────────────────────────────────────────────────

_PLANETS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]


def _chart(params: dict[str, Any], diurnal: bool = True) -> dict[str, Any]:
    return {
        "params": params,
        "chart": {
            "isDiurnal": diurnal,
            "objects": [{"id": p, "lon": (17 + 41 * i) % 360} for i, p in enumerate(_PLANETS)],
            "houses": [{"id": f"House{i + 1}", "lon": (5 + 30 * i) % 360} for i in range(12)],
        },
    }


DECENNIAL_CASES: list[tuple[str, dict[str, Any], dict[str, Any]]] = [
    ("bc_athens", {"birth": "-0500-03-21 12:00:00", "zone": "+02:00"}, {}),
    ("julian_1500", {"birth": "1500-02-20 12:00:00", "zone": "+01:00"}, {}),
    ("julian_leap_1500_0229", {"birth": "1500-02-29 06:30:00", "zone": "+01:00"}, {"calendarType": "calendar_365_25"}),
    ("eve_of_reform_1582", {"birth": "1582-10-04 23:59:00", "zone": "+01:00"}, {"dayMethod": "hephaistio"}),
    ("bc1_new_year_eve", {"birth": "-0001-12-31 12:00:00", "zone": "+00:00"}, {"orderType": "chaldean"}),
    ("five_digit_year", {"birth": "12000-01-01 00:00:00", "zone": "+08:00"}, {}),
    ("modern_default_zone", {"birth": "1990-03-21 12:00:00"}, {}),
    ("date_time_params_ad500", {"date": "0500/03/21", "time": "08:15", "zone": "-03:30"}, {}),
    ("reform_gap_invalid", {"birth": "1582-10-10 12:00:00", "zone": "+01:00"}, {}),
]

PERSIAN_BIRTHS = ["-0500-03-21 12:00:00", "1500-02-20 12:00:00", "1582-09-30 06:00:00", "1990-03-21 12:00:00"]
DIRECTED_AGE_CASES = [
    ["-0500-03-21 12:00:00", "-0450-03-21 12:00:00"],
    ["-0001-12-31 12:00:00", "0001-01-01 12:00:00"],
    ["1500-02-20 12:00:00", "1582-10-15 12:00:00"],
    ["1500-02-20 12:00", "1500-03-01"],
    ["12000-01-01 00:00:00", "12050-06-01 00:00:00"],
    ["1990-03-21 12:00:00", "2026-10-30 08:00:00"],
    ["1990/03/21 12:00:00", "2026/10/30 08:00:00"],
    ["0000-01-01 12:00:00", "2026-10-30 08:00:00"],
]
PLANETARY_AGE_CASES = [
    ["-0500-03-21 12:00:00", "2026-10-30"],
    ["1500-02-29 06:30:00", "2026-03-09"],
    ["1500-02-29 06:30:00", "2026-03-10"],
    ["1582-10-04 23:59:00", "2026-10-13"],
    ["1582-10-04 23:59:00", "2026-10-14"],
    ["1990-03-21 12:00:00", "2026-03-21"],
    ["12000-01-01 00:00:00", "2026-10-30"],
]
ZR_CASES: list[dict[str, Any]] = [
    {
        "items": [{"date": "-500-03-21", "days": 3000, "sign": "Aries"}, {"date": "-0492-06-06", "days": 400.5, "sign": "Taurus"}],
        "now": "-0491-01-01 00:00:00",
    },
    {
        "items": [{"date": "1500-02-20", "days": 10, "sign": "Aries"}, {"date": "1500-03-01", "days": 30000, "sign": "Taurus"}],
        "now": "1500-02-29 12:00:00",
    },
    {"items": [{"date": "1580-01-01", "days": 1200, "sign": "Leo"}], "now": "1582-10-15 00:00:00"},
    {"items": [{"date": "2020-01-01", "days": 3000.25, "sign": "Leo"}], "now": "2026-10-30 00:00:00"},
    {"items": [{"date": "garbage", "days": 3}, {"date": "2026-01-01", "days": 400}], "now": "2026-10-30 00:00:00"},
]
SYZYGY_CASES = ["-0500-03-20 23:41:03", "1500-02-15T07:37:59", "2026-01-01", "-12000-01-01 00:00:00", "", "0999-12-31 01:02:03"]
DATETIME_FORMAT_CASES = [
    "-0500-03-21 12:00:00", "-500-03-21 08:15:00", "1500-02-20 12:00:00", "0999-01-01 00:00:00", "12000-01-01 00:00:00",
    "2026-03-20 03:04:05", "1990/03/21 12:00:00", "-0001-12-31", "2026-3-5 7:08:09",
]


# ── 上游源 → 可执行 ESM（Babel 抽顶层声明 + vendored 依赖；对上游树只读）────────────────────────────────

_EXTRACT_JS = r"""
import { createRequire } from 'module';
import fs from 'fs';
const require = createRequire(process.argv[1]);
const parser = require('@babel/parser');
const generate = require('@babel/generator').default;
const src = fs.readFileSync(new URL(process.argv[2]), 'utf8');
const want = new Set(JSON.parse(process.argv[3]));
const ast = parser.parse(src, { sourceType: 'module', plugins: ['jsx', 'classProperties'] });
const out = [];
for (let node of ast.program.body) {
  if ((node.type === 'ExportNamedDeclaration' || node.type === 'ExportDefaultDeclaration') && node.declaration) node = node.declaration;
  let name = null;
  if ((node.type === 'FunctionDeclaration' || node.type === 'ClassDeclaration') && node.id) name = node.id.name;
  if (node.type === 'VariableDeclaration' && node.declarations.length === 1 && node.declarations[0].id.type === 'Identifier') name = node.declarations[0].id.name;
  if (name && want.has(name)) { out.push(generate(node, { comments: false }).code); want.delete(name); }
}
if (want.size) { throw new Error('missing upstream declarations: ' + [...want].join(',')); }
process.stdout.write(JSON.stringify(out.join('\n')));
"""


def _vurl(rel: str) -> str:
    return (CORE_JS / rel).resolve().as_uri()


def _upstream_decls(rel: str, names: list[str]) -> str:
    assert UPSTREAM_UI is not None
    return _run_esm(_EXTRACT_JS, Path(UPSTREAM_UI / "package.json"), Path(UPSTREAM_UI / "src" / rel), json.dumps(names))


def _run_module(source: str, body: str, *args: str, env: dict[str, str] | None = None) -> Any:
    with tempfile.TemporaryDirectory() as tmp:
        module = Path(tmp) / "m.mjs"
        module.write_text(source, encoding="utf-8")
        script = (
            "import(process.argv[1]).then(async (m) => { const argv = process.argv.slice(2);"
            f" const out = await (async () => {{ {body} }})(); process.stdout.write(JSON.stringify(out)); }});"
        )
        return _run_esm(script, module, *args, env=env)


_MOMENT = "src/../node_modules/moment/moment.js"
_STRIP_TREE_JS = "const strip = (n) => [n.planet, n.date, n.active, n.nominal, n.startText, n.endText, (n.sublevel || []).map(strip)];"


def _upstream_decennials() -> dict[str, Any]:
    assert UPSTREAM_UI is not None
    src = (UPSTREAM_UI / "src" / "utils" / "decennials.js").read_text(encoding="utf-8")
    for old, new in (
        ("import moment from 'moment';", f"import moment from '{_vurl(_MOMENT)}';"),
        ("from '../constants/AstroConst';", f"from '{_vurl('src/constants/AstroConst.js')}';"),
        ("import * as AstroText from '../constants/AstroText';", "const AstroText = { AstroTxtMsg: {}, AstroMsg: {} };"),
        ("from './civilMoment';", f"from '{_vurl('src/vendor/utils/civilMoment.js')}';"),
    ):
        assert old in src, f"upstream decennials.js import changed: {old}"
        src = src.replace(old, new)
    src += "\nexport { moment };\n"
    body = (
        "m.moment.now = () => Number(argv[1]); " + _STRIP_TREE_JS +
        " const out = {}; for (const [key, params, settings] of JSON.parse(argv[0])) {"
        " const chart = JSON.parse(argv[2]); chart.params = params;"
        " const t = m.buildDecennialTimeline(chart, settings); out[key] = { list: t.list.map(strip), baseOrder: t.baseOrder,"
        " resolvedStartPlanet: t.resolvedStartPlanet, birthMoment: t.birthMoment && t.birthMoment.isValid() ? t.birthMoment.utcOffset() : null }; }"
        " return out;"
    )
    return _run_module(src, body, json.dumps(DECENNIAL_CASES), str(NOW_MS), json.dumps(_chart({})))


def _upstream_persian() -> dict[str, Any]:
    decls = _upstream_decls(
        "components/astro/AstroPersianDirected.js",
        ["RATE", "MOVERS", "ASPECTS", "norm360", "lonOf", "buildPersianHits", "directedAgeYears"],
    )
    src = (
        f"import * as AstroConst from '{_vurl('src/constants/AstroConst.js')}';\n"
        f"import {{ momentOfCivilDateTimeStr, civilDateAfterDays }} from '{_vurl('src/vendor/utils/civilMoment.js')}';\n"
        f"{decls}\nexport {{ buildPersianHits, directedAgeYears }};\n"
    )
    body = (
        "const chart = JSON.parse(argv[2]); const hits = {}; for (const birth of JSON.parse(argv[0])) {"
        " for (const [rate, dir] of [['persian', 'direct'], ['prophected', 'converse']]) {"
        " hits[`${birth}|${rate}|${dir}`] = m.buildPersianHits({ ...chart, params: { birth } }, rate, 90, dir)"
        ".map((h) => [h.age, h.promittor, h.aspect, h.significator, h.date]); } }"
        " return { hits, ages: JSON.parse(argv[1]).map(([b, d]) => m.directedAgeYears(b, d)) };"
    )
    return _run_module(src, body, json.dumps(PERSIAN_BIRTHS), json.dumps(DIRECTED_AGE_CASES), json.dumps(_chart({})))


def _upstream_planetary_ages() -> list[Any]:
    decls = _upstream_decls("utils/planetaryAges.js", ["PLANETARY_AGES", "parseBirthMoment", "buildPlanetaryAges"])
    src = (
        f"import moment from '{_vurl(_MOMENT)}';\n"
        f"import * as AstroConst from '{_vurl('src/constants/AstroConst.js')}';\n"
        f"import {{ birthMomentOfChart }} from '{_vurl('src/vendor/utils/civilMoment.js')}';\n"
        f"{decls}\nexport {{ buildPlanetaryAges }};\n"
    )
    body = (
        "return JSON.parse(argv[0]).map(([birth, asOf]) => { const r = m.buildPlanetaryAges({ params: { birth }, chart: {} }, asOf);"
        " return r.curAge === null ? null : Math.floor(r.curAge); });"
    )
    return _run_module(src, body, json.dumps(PLANETARY_AGE_CASES), env={"TZ": "UTC"})


def _upstream_zr() -> list[Any]:
    decls = _upstream_decls("components/astro/AstroZR.js", ["zrPeriodStartMs", "zrLocateCurrent", "zrFmtDayUTC"])
    src = (
        f"import {{ civilWallMsOfStr, civilDateStrOfMs }} from '{_vurl('src/vendor/bazi/dateStrSafe.js')}';\n"
        f"{decls}\nexport {{ zrLocateCurrent }};\n"
    )
    body = (
        f"const ds = await import('{_vurl('src/vendor/bazi/dateStrSafe.js')}');"
        " return JSON.parse(argv[0]).map((c) => { const r = m.zrLocateCurrent(c.items, ds.civilWallMsOfStr(c.now));"
        " return r ? [r.item.sign, r.startText, r.endText] : null; });"
    )
    return _run_module(src, body, json.dumps(ZR_CASES))


def _upstream_split_syzygy() -> list[Any]:
    decls = _upstream_decls("components/astro/AstroPrenatalSyzygy.js", ["splitDateTime"])
    src = f"import {{ toSlashDate }} from '{_vurl('src/vendor/bazi/dateStrSafe.js')}';\n{decls}\nexport {{ splitDateTime }};\n"
    return _run_module(src, "return JSON.parse(argv[0]).map((s) => m.splitDateTime(s));", json.dumps(SYZYGY_CASES))


def _upstream_datetime_format() -> list[Any]:
    """components/comp/DateTime.js：parse(串, 'YYYY-MM-DD HH:mm:ss') → ad / format('YYYY/MM/DD') / format('HH:mm:ss') /
    format('YYYY-MM')（momentPipeline.chartAtMoment、七政 fieldsToParams、农历「查询月份」都是这一形）。"""
    assert UPSTREAM_UI is not None
    src = (UPSTREAM_UI / "src" / "components" / "comp" / "DateTime.js").read_text(encoding="utf-8")
    for old, new in (
        ("import moment from 'moment';", f"import moment from '{_vurl(_MOMENT)}';"),
        ("import request from '../../utils/request';", "const request = () => { throw new Error('no network'); };"),
        ("import * as Constants from '../../utils/constants';", "const Constants = {};"),
    ):
        assert old in src, f"upstream DateTime.js import changed: {old}"
        src = src.replace(old, new)
    body = (
        "return JSON.parse(argv[0]).map((s) => { const dt = new m.default(); dt.parse(s, 'YYYY-MM-DD HH:mm:ss');"
        " return [dt.ad, dt.format('YYYY/MM/DD'), dt.format('HH:mm:ss'), dt.format('YYYY-MM')]; });"
    )
    return _run_module(src, body, json.dumps(DATETIME_FORMAT_CASES))


def _upstream_goldens() -> dict[str, Any]:
    return {
        "decennials": _upstream_decennials(),
        "persian": _upstream_persian(),
        "planetaryAges": _upstream_planetary_ages(),
        "zr": _upstream_zr(),
        "splitSyzygy": _upstream_split_syzygy(),
        "dateTimeFormat": _upstream_datetime_format(),
    }


def _compact_decennials(gold: dict[str, Any]) -> dict[str, Any]:
    """夹具体积：L1 全表（不含子树）+ 首个 / 当前 L1 的 L2 全表 + 各自首个 L2 的 L3 全表 + 首个 L3 的 L4 全表 + 全树 sha256。"""
    def head(node: list[Any], depth: int) -> list[Any]:
        kids = node[6]
        if depth == 0 or not kids:
            return [*node[:6], []]
        return [*node[:6], [head(kids[0], depth - 1), *[[*k[:6], []] for k in kids[1:]]]]

    out: dict[str, Any] = {}
    for key, value in gold.items():
        lst = value["list"]
        active = next((i for i, n in enumerate(lst) if n[2]), None)
        out[key] = {
            "l1": [[*n[:6], []] for n in lst],
            "first": head(lst[0], 3) if lst else None,
            "activeIndex": active,
            "active": head(lst[active], 3) if active is not None else None,
            "sha256": hashlib.sha256(json.dumps(lst, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest(),
            "baseOrder": value["baseOrder"],
            "resolvedStartPlanet": value["resolvedStartPlanet"],
            "birthOffset": value["birthMoment"],
        }
    return out


def _js_num(value: Any) -> Any:
    """JSON 数字的 JS 写法（整数值的 float 不带 .0），sha256 两侧同一字节流。"""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, list):
        return [_js_num(v) for v in value]
    return value


def _rows_digest(rows: list[Any]) -> dict[str, Any]:
    """长表的夹具形：条数 + 前 40 行 + 带日期的行里每 25 行取一 + 全表 sha256。"""
    rows = _js_num(rows)
    dated = [r for r in rows if r[-1]]
    return {
        "count": len(rows), "head": rows[:40], "sample": dated[::25],
        "sha256": hashlib.sha256(json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest(),
    }


def _compact_goldens(raw: dict[str, Any]) -> dict[str, Any]:
    persian = {**raw["persian"], "hits": {k: _rows_digest(v) for k, v in raw["persian"]["hits"].items()}}
    return {**raw, "decennials": _compact_decennials(raw["decennials"]), "persian": persian}


@pytest.fixture(scope="module")
def gold() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@requires_node
@requires_upstream
def test_fixture_matches_upstream(gold: dict[str, Any]) -> None:
    """夹具 = 上游 v3.13.0 源码当场跑出来的值（不是手算 / 不是 skill 自己的输出）。上游改了这些 builder → 红，重生夹具：
    `uv run python -c "import json,sys; sys.path[:0]=['tests']; import test_sync313_historical as t;
    open(t.FIXTURE,'w').write(json.dumps(t._compact_goldens(t._upstream_goldens()), ensure_ascii=False, indent=1))"`。"""
    assert _compact_goldens(_upstream_goldens()) == gold


# ── 十年大运（utils/decennials.js · v3.12.0 zonedBirthMomentOfChart + civilLabelOf）──────────────────────

def _py_tree(node: dict[str, Any]) -> list[Any]:
    return [node["planet"], node["date"], node["active"], node["nominal"], node["startText"], node["endText"], [_py_tree(n) for n in node["sublevel"]]]


@pytest.mark.parametrize("key", [case[0] for case in DECENNIAL_CASES])
def test_decennials_match_upstream_on_historical_births(gold: dict[str, Any], key: str) -> None:
    """公元前 / 儒略历 1500（含儒略闰日 2 月 29 日）/ 改历前夜 / 公元前 1 年跨元年 / 五位年 / 缺时区（缺省 +08:00）/
    date+time 两键 / 改历缺口（无效 → 空表）九例，全树逐节点（sha256）+ L1 全表 + 首个与当前 L1 的展开逐字等于上游。
    负向对照（实跑）：① 缺省时区改回 +00:00 → modern_default_zone 红；② 期界标签改回外推格里历（datetime + timedelta）
    → 公元前 / 1500 / 1582 / 公元前 1 年 / 五位年 / 公元 500 年共 8 例红。"""
    _, params, settings = next(case for case in DECENNIAL_CASES if case[0] == key)
    want = gold["decennials"][key]
    chart = _chart(params)
    timeline = build_decennial_timeline(chart, settings, now_ms=NOW_MS)
    lst = [_py_tree(n) for n in timeline["list"]]
    assert [[*n[:6], []] for n in lst] == want["l1"]
    assert timeline["baseOrder"] == want["baseOrder"]
    assert timeline["resolvedStartPlanet"] == want["resolvedStartPlanet"]
    compact = _compact_decennials({key: {"list": lst, "baseOrder": timeline["baseOrder"],
                                         "resolvedStartPlanet": timeline["resolvedStartPlanet"], "birthMoment": want["birthOffset"]}})[key]
    assert compact["first"] == want["first"]
    assert compact["activeIndex"] == want["activeIndex"]
    assert compact["active"] == want["active"]
    assert compact["sha256"] == want["sha256"]
    if want["birthOffset"] is None:
        assert timeline["birthMoment"] is None
    else:
        offset = int(want["birthOffset"])
        assert timeline["birthMoment"].endswith(f"{'-' if offset < 0 else '+'}{abs(offset) // 60:02d}:{abs(offset) % 60:02d}")


def test_decennials_bc_chart_is_not_empty_and_labels_are_julian() -> None:
    """可读的锚点（与上面的 sha 互补）：公元前盘出表、首期起于出生日、1500 年盘的首期标签是儒略历日期。"""
    bc = build_decennial_timeline(_chart({"birth": "-0500-03-21 12:00:00", "zone": "+02:00"}), {}, now_ms=NOW_MS)
    assert bc["list"] and bc["list"][0]["startText"] == "-0500-03-21"
    assert bc["birthMoment"] == "-0500-03-21T12:00:00+02:00"
    j = build_decennial_timeline(_chart({"birth": "1500-02-20 12:00:00", "zone": "+01:00"}), {}, now_ms=NOW_MS)
    assert j["list"][0]["date"].startswith("1500-02-20 - ")


# ── 波斯向运 / 行星年龄（AstroPersianDirected.js · planetaryAges.js · v3.12.0 momentOfCivilDateTimeStr）──────────

def test_persian_hits_dates_match_upstream(gold: dict[str, Any]) -> None:
    """buildPersianHits 的应期日期 = civilDateAfterDays(出生, 年龄×365.2421904)：公元前盘此前整列为空、1500 年盘按外推
    格里历加天数（跨 1500-02-29 与 1582 改历差 1 / 10 天）。四盘 × 两档速率/方向逐条对拍上游。
    负向对照（实跑）：出生时刻改回 strptime + 外推格里历轴（`_civil_birth_wall_ms` 换成 moment 格式解析）→ 红。"""
    from horosa_skill.service.text.predictive import _build_persian_hits

    chart = _chart({})
    for key, want in gold["persian"]["hits"].items():
        birth, rate, direction = key.split("|")
        got = _build_persian_hits({**chart, "params": {"birth": birth}}, rate, 90, direction)
        rows = [[h["age"], h["promittor"], h["aspect"], h["significator"], h["date"]] for h in got]
        assert _rows_digest(rows) == want, key


def test_persian_directed_age_matches_upstream(gold: dict[str, Any]) -> None:
    """directedAgeYears：两端都经民用历单源（公元前 1 年 → 公元 1 年只隔 1 天、1500 年 2 月有 29 日、五位年、年 0 无效）。
    负向对照（实跑）：同上（出生时刻改回 strptime + 外推格里历轴）→ 公元前 / 五位年返回 None → 红。"""
    from horosa_skill.service.text.predictive import _persian_directed_age_years

    got = [_persian_directed_age_years(b, d) for b, d in DIRECTED_AGE_CASES]
    want = gold["persian"]["ages"]
    assert [g is None for g in got] == [w is None for w in want]
    assert all(g is None or abs(g - w) < 1e-12 for g, w in zip(got, want))


def test_planetary_ages_current_age_matches_upstream(gold: dict[str, Any]) -> None:
    """buildPlanetaryAges(chartObj, asOf).curAge 的整数部分（快照「当前年龄：约 N 岁」与带判定都只看它）：出生日经民用历读、
    moment 里装同一天的外推格里历——儒略 1500-02-29 = 格里 1500-03-10，故 2026-03-09 未满、03-10 满。
    负向对照（实跑）：同上（出生时刻改回 strptime + 外推格里历轴）→ 公元前 / 1500-02-29 例 None → 红。"""
    from horosa_skill.service.text.predictive import _full_years_between, _moment_format_parse

    got = [_full_years_between(b, _moment_format_parse(a)) for b, a in PLANETARY_AGE_CASES]
    assert got == gold["planetaryAges"]


# ── ZR 当前期 / 产前朔望起盘 / DateTime 日期形 ────────────────────────────────────────────────────

def test_zr_current_period_matches_upstream(gold: dict[str, Any]) -> None:
    """zrLocateCurrent：期起 civilWallMsOfStr、末期讫日 civilDateStrOfMs（公元前 / 儒略历标签，小数天）。
    负向对照（实跑）：zrPeriodStartMs 换回 strptime('%Y-%m-%d') 版 → 公元前期起认不出、儒略历期讫标签错 → 红。"""
    from horosa_skill.service.text.pd_zr import _zr_period_bounds

    got = []
    for case in ZR_CASES:
        now_ms = cc._civil_wall_ms_of_moment(case["now"])
        r = _zr_period_bounds(case["items"], now_ms)
        got.append([r["item"].get("sign"), r["startText"], r["endText"]] if r else None)
    assert got == gold["zr"]


def test_split_syzygy_datetime_matches_upstream(gold: dict[str, Any]) -> None:
    """splitDateTime 改用 toSlashDate（公元前前导负号保留）。负向对照（实跑）：换回 replace('-', '/') → '/0500/03/20' → 红。"""
    assert [split_syzygy_datetime(s) for s in SYZYGY_CASES] == gold["splitSyzygy"]


def test_datetime_parse_format_port_matches_upstream(gold: dict[str, Any]) -> None:
    """_chart_at_moment_date_fields = DateTime.parse(…).format(…)（chartAtMoment 的 ad/date/time、七政 params.date、
    农历查询月份）。负向对照（实跑）：① ad 改回恒 1 → 公元前例红；② 七政日期改回 replace('-', '/', 2) → 公元前与 0999 例红。"""
    from horosa_skill.service.text.chinese import _guolao_slash_date

    for text, (ad, ymd, hms, ym) in zip(DATETIME_FORMAT_CASES, gold["dateTimeFormat"]):
        fields = cc._chart_at_moment_date_fields(text)
        assert [fields["ad"], fields["date"], fields["time"]] == [ad, ymd, hms], text
        assert _guolao_slash_date(text.split(" ")[0]) == ymd, text


# ── 民用历小工具 ≡ vendored JS（离线、不需要上游树）──────────────────────────────────────────────

_PARSE_CASES = [
    "-0500-03-21 12:00:00", "-500/3/21 8:05", "1500-02-29", "1500-02-30", "2023-02-29 10:00", "1582-10-10 12:00:00",
    "0000-01-01", "12000-01-01T00:00:00.5Z", "+002026-04-14", "2026-04-14T12:30:15+05:30", "2026-04-14 24:00",
    "2026-04-14 24:01", "1776", "5", "2026/4", "  -0001-12-31   23:59:59  ", "2026-13-01", "garbage",
]


@requires_node
def test_parse_and_wall_ms_match_vendored() -> None:
    """parseDateTimeParts / civilWallMsOfStr / momentOfCivilDateTimeStr（墙钟毫秒）/ civilDateStrOfMs 逐例对拍 vendored。
    负向对照（实跑）：去掉「24 点只许 24:00」一条 → '2026-04-14 24:01' 例红。"""
    expected = _node(
        "vendor/utils/civilMoment.js",
        f"const dp = await import('{_vurl('src/vendor/utils/dateTimeParse.js')}');"
        f" const ds = await import('{_vurl('src/vendor/bazi/dateStrSafe.js')}');"
        " return JSON.parse(argv[0]).map((s) => { const p = dp.parseDateTimeParts(s); const w = ds.civilWallMsOfStr(s);"
        " const mm = m.momentOfCivilDateTimeStr(s);"
        " const lenient = mm.isValid() ? (m.civilJdnOfMoment(mm) - 2440588) * 86400000 + ((mm.hour() * 60 + mm.minute()) * 60 + mm.second()) * 1000 : null;"
        " return [p && [p.year, p.month, p.day, p.hour, p.minute, p.second, p.ms, p.isoDateOnly, p.offsetMin],"
        " Number.isFinite(w) ? w : null, lenient, Number.isFinite(w) ? ds.civilDateStrOfMs(w) : ''];"
        " });",
        json.dumps(_PARSE_CASES),
    )
    got = []
    for s in _PARSE_CASES:
        p = cc._parse_date_time_parts(s)
        w = cc._civil_wall_ms_of_moment(s)
        lenient = cc._civil_wall_ms_of_moment(s, strict=False)
        got.append([
            p and [p["year"], p["month"], p["day"], p["hour"], p["minute"], p["second"], p["ms"], p["isoDateOnly"], p["offsetMin"]],
            w, None if lenient is None else lenient - (p["ms"] if p else 0), cc._civil_date_str_of_ms(w) if w is not None else "",
        ])
    assert got == expected


@requires_node
def test_small_date_string_helpers_match_vendored() -> None:
    """toSlashDate / leadingYearOf / yearMonthKey / monthDayLabel / zoneOffsetMinutesOf / formatSignedDate 对拍 vendored。"""
    strs = ["-0500-03-21 12:00:00", "1500-02-20", "12000/01/01", "0999-1-2", "garbage", "", "-0300-03-10T08:00"]
    zones = ["+08:00", "-0330", "+5", "5.5", "-03:30", "abc", ""]
    expected = _node(
        "vendor/bazi/dateStrSafe.js",
        f"const z = await import('{_vurl('src/vendor/utils/zoneOffset.js')}');"
        " const s = JSON.parse(argv[0]); return [s.map((x) => m.toSlashDate(x)), s.map((x) => { const y = m.leadingYearOf(x); return Number.isFinite(y) ? y : null; }),"
        " s.map((x) => m.yearMonthKey(x)), s.map((x) => m.monthDayLabel(x)), JSON.parse(argv[1]).map((x) => z.zoneOffsetMinutesOf(x)),"
        " [m.formatSignedDate(-500, 3, 1), m.formatSignedDate(12000, 1, 2), m.formatSignedDate(5, 6, 7)]];",
        json.dumps(strs), json.dumps(zones),
    )
    got = [
        [cc._to_slash_date(x) for x in strs], [cc._leading_year_of(x) for x in strs], [cc._year_month_key(x) for x in strs],
        [cc._month_day_label(x) for x in strs], [cc._zone_offset_minutes_of(x) for x in zones],
        [cc._format_signed_date(-500, 3, 1), cc._format_signed_date(12000, 1, 2), cc._format_signed_date(5, 6, 7)],
    ]
    assert got == expected


@requires_node
@pytest.mark.skipif(not hasattr(time, "tzset"), reason="time.tzset 只在 POSIX 上有（本进程钉 TZ=UTC 比对；mac / Linux lane 覆盖）")
def test_civil_instant_ms_matches_vendored_in_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    """civilInstantMsOfStr（主限「表中距今最近行」的时刻轴）：钟面按 parseDateTimeMs（严格 ISO 纯日期 = UTC 0 点、其余本机钟面）
    + 民用历与外推格里历同一标签之差。两侧都钉在 TZ=UTC 比（本机时区只影响「本机钟面」那一项）。
    负向对照见下一条（距今最近行）。"""
    cases = ["-0500-03-21 12:00:00", "1500-02-20 12:00:00", "1500-02-29", "2026-04-14", "2026-04-14 12:00", "0000-03-01", "-1-01-01", "x"]
    expected = _node(
        "vendor/bazi/dateStrSafe.js",
        "return JSON.parse(argv[0]).map((s) => { const v = m.civilInstantMsOfStr(s); return Number.isFinite(v) ? v : null; });",
        json.dumps(cases), env={"TZ": "UTC"},
    )
    monkeypatch.setenv("TZ", "UTC")
    time.tzset()
    try:
        assert [cc._civil_instant_ms_of_str(s) for s in cases] == expected
    finally:
        monkeypatch.undo()
        time.tzset()


def test_pd_nearest_line_reads_bc_rows() -> None:
    """AstroDirectMain.js 距今最近行（v3.12.0 civilInstantMsOfStr）：公元前盘的主限行此前被 Date.parse 口径整表跳过 → 定位行缺席；
    现在取到离「此刻」最近（= 最晚）的那行。负向对照（实跑）：公元前行按旧口径跳过 → 定位行为空 → 红。"""
    from horosa_skill.service.text.pd_zr import _pd_nearest_line

    rows = [[10.0, "Sun", "Asc", "D", "-0490-03-21 12:00:00"], [20.0, "Moon", "MC", "D", "-0480-06-01 08:00:00"]]
    line = _pd_nearest_line(rows, {}, {"chart": {"objects": []}}, now=datetime(2026, 10, 30, 8, 0, 0))
    assert line and "-0480-06-01 08:00:00" in line


# ── 世俗盘：chartAtMoment / 食盘 / scanYear（mundane.py）─────────────────────────────────────────────

class _RecordingMundane:
    """只录请求、按端点回假数据的世俗盘 runner 宿主（不打真后端）。"""

    def __init__(self, responses: dict[str, Any]):
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._responses = responses

    def _call_remote(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((endpoint, dict(payload)))
        value = self._responses.get(endpoint)
        return value(payload) if callable(value) else (value or {})


def _mundane_host(responses: dict[str, Any]) -> Any:
    from horosa_skill.service.runners.mundane import MundaneRunners

    host = type("Host", (_RecordingMundane, MundaneRunners), {})(responses)
    return host


def test_mundane_solunar_and_vedic_requests_keep_bc_era(gold: dict[str, Any]) -> None:
    """solveSiderealIngress / solveVedicSolarIngress → chartAtMoment：ad / date / time 取自时刻本身（DateTime.parse → format）。
    公元前种子 '-500-01-14 12:00:00' 的请求体 = 上游 DateTime 同形（ad=-1, date '-500/01/14'），且不沿用页面 ad。
    负向对照（实跑）：换回 `moment.split(" ")[0].replace("-", "/")` + payload ad → date '/500/01/14'、ad=1 → 红。"""
    lon = {"value": 270.0}
    host = _mundane_host({"/chart": lambda p: {"chart": {"objects": [{"id": "Sun", "lon": lon["value"]}, {"id": "Moon", "lon": 0.0}]}}})
    moment, _ = host._solve_sidereal_ingress("capsolar", "-500", {"zone": "+02:00", "ad": 1})
    endpoint, body = host.calls[0]
    want = dict(zip(DATETIME_FORMAT_CASES, gold["dateTimeFormat"]))["-500-03-21 08:15:00"]
    assert endpoint == "/chart" and body["ad"] == want[0] == -1
    assert body["date"] == "-500/01/14" and body["time"] == "12:00:00"
    host.calls.clear()
    lon["value"] = 0.0
    assert host._solve_vedic_ingress("ingress_0", -500, {"zone": "+02:00", "ad": 1}) == "-500-04-14 12:00:00"
    assert host.calls[0][1]["ad"] == -1 and host.calls[0][1]["date"] == "-500/04/14"
    vedic = host._vedic_chart_payload("-0500-03-15 16:39:56", {"ad": 1})
    assert (vedic["ad"], vedic["date"], vedic["time"]) == (-1, "-500/03/15", "16:39:56")


def test_mundane_eclipse_job_runs_for_bc_ingress() -> None:
    """食盘卡：入宫 − 2 日起扫 400 日（民用历墙钟轴）；公元前入宫时刻此前 strptime 失败 → 卡缺席。scanYear = leadingYearOf。
    负向对照（实跑）：① 公元前入宫时刻按旧 strptime 口径认不出 → None → 红；② scanYear 改回 int([:4]) → None → 红。"""
    eclipse = {"type": "solar_eclipse", "datetime": "-500-09-02 10:11:12", "eclipseType": "Partial"}
    host = _mundane_host({
        "/astroextra/ephemeris": {"eclipses": [{"type": "solar_eclipse", "datetime": "-500-03-20 00:00:00"}, eclipse]},
        "/chart": {"chart": {"objects": []}},
        "/astroextra/eclipsedetail": {"durationHours": 2},
    })
    job = host._mundane_eclipse_job("solecl", chart_payload={"ad": 1, "lat": "37n58", "lon": "23e43"},
                                    ingress_time="-500-03-26 20:40:24", zone="+02:00")
    assert job is not None and job["extra"]["selectedMoment"] == "-500-09-02 10:11:12" and job["extra"]["scanYear"] == -500
    eph = next(body for ep, body in host.calls if ep == "/astroextra/ephemeris")
    assert (eph["startDate"], eph["endDate"]) == (
        cc._civil_date_str_of_ms(cc._civil_wall_ms_of_moment("-500-03-24 20:40:24")),
        cc._civil_date_str_of_ms(cc._civil_wall_ms_of_moment("-500-03-24 20:40:24") + 400 * 86400000),
    )
    assert eph["startDate"] == "-0500-03-24"
    chart_body = next(body for ep, body in host.calls if ep == "/chart")
    assert chart_body["ad"] == -1 and chart_body["date"] == "-500-09-02"


# ── 波斯向运指定日期 / 主限盘缺省目标 / 校时预览 ─────────────────────────────────────────────────────

def test_persian_target_datetime_keeps_bc_sign() -> None:
    """只给日期补正午按「日期段 = 整串」判；/predict/persianchart 的 datetime 经 toSlashDate（前导负号保留）。
    负向对照（实跑）：换回 len()==10 + replace('-', '/') → '-0450-03-21' 不补正午、写成 '/0450/03/21' → 红。"""
    from horosa_skill.service.runners.predictive import PredictiveRunners

    assert PredictiveRunners._persian_target_datetime({"datetime": "-0450-03-21"}) == "-0450-03-21 12:00:00"
    assert PredictiveRunners._persian_target_datetime({"datetime": "12000-01-01"}) == "12000-01-01 12:00:00"
    assert PredictiveRunners._persian_target_datetime({"datetime": "2026-03-21"}) == "2026-03-21 12:00:00"
    host = type("H", (PredictiveRunners,), {})()
    sent: list[dict[str, Any]] = []
    host._call_remote = lambda endpoint, payload: sent.append(payload) or {}  # type: ignore[attr-defined]
    host._persianchart_by_date({"datetime": "-0450-03-21"})
    assert sent[0]["datetime"] == "-0450/03/21 12:00:00"


@requires_node
def test_germany_rectify_birth_reads_bc_and_julian(monkeypatch: pytest.MonkeyPatch) -> None:
    """AstroMidpoint.buildRectifySection（v3.12.0）：出生时刻经 momentOfCivilDateTimeStr；事件日期仍 moment(ev.date)。
    弧 = (事件 − 出生) 年 × Naibod，期望值由 vendored civilMoment + moment 在 TZ=UTC 下算（不手算）。
    负向对照（实跑）：出生时刻换回 _parse_local_moment(strptime，外推格里历轴) → 1500 例弧差 10 天、公元前段缺席 → 红。"""
    from horosa_skill.service.text.western import _SOLAR_ARC_RATE, _germany_rectify_lines

    births = [("1500-02-20", "12:00:00"), ("0800-07-01", "06:30:00")]
    events = [{"date": "1582-10-20", "label": "e1", "type": "career"}]
    rate = _SOLAR_ARC_RATE["naibod"]
    expected = _node(
        "vendor/utils/civilMoment.js",
        f"const moment = (await import('{_vurl(_MOMENT)}')).default;"
        " return JSON.parse(argv[0]).map(([d, t]) => { const b = m.momentOfCivilDateTimeStr(`${d} ${t}`); const w = moment(JSON.parse(argv[1]));"
        " return ((w.valueOf() - b.valueOf()) / (86400000 * 365.2422) * Number(argv[2])).toFixed(2); });",
        json.dumps(births), json.dumps(events[0]["date"]), str(rate), env={"TZ": "UTC"},
    )
    for (d, t), arc in zip(births, expected):
        lines = _germany_rectify_lines({"date": d, "time": t, "orb": 1}, events, [{"id": "MC", "lon": 10.0}, {"id": "Asc", "lon": 100.0}])
        row = next(line for line in lines if line.startswith("| e1 |"))
        assert row.split(" | ")[3] == arc, (d, row)
    # 公元前出生：此前 strptime 失败 → 整段缺席；现出段（事件在公元后，弧照算）。
    assert _germany_rectify_lines({"date": "-0100-01-01", "time": "00:00:00"}, events, [{"id": "MC", "lon": 1.0}])


def test_pdchart_default_datetime_is_civil_next_day() -> None:
    """defaultPdChartDateTime 无主限行时 = 出生次日（DateTime.addDate(1)：儒略 1500-02-28 的次日是 02-29；公元前照算）。
    负向对照（实跑）：换回 strptime + timedelta → 1500 例得 03-01、公元前例 ValueError → 红。"""
    from horosa_skill.service.enrich import EnrichMixin

    host = type("H", (EnrichMixin,), {})()
    host._call_remote = lambda endpoint, payload: {"predictives": {"primaryDirection": []}, "params": {}}  # type: ignore[attr-defined]
    assert host._pdchart_default_datetime({"date": "1500-02-28", "time": "12:00:00"})[0] == "1500-02-29 12:00:00"
    assert host._pdchart_default_datetime({"date": "-0500-12-31", "time": "23:00:00"})[0] == "-0499-01-01 23:00:00"
    assert host._pdchart_default_datetime({"date": "2024-02-28", "time": "12:00:00"})[0] == "2024-02-29 12:00:00"


def test_calendar_month_labels_parse_bc_dates() -> None:
    """农历月历（NongLiMain.buildNongliSnapshotText）：月 / 日标签走 yearMonthKey / monthDayLabel，查询月份 = DateTime
    format('YYYY-MM')。负向对照（实跑）：换回 [:7] / [5:10] → 公元前行的公历列写成 '3-21 ' → 红。"""
    from horosa_skill.service.text.chinese import _build_calendar_month_snapshot_text

    days = [{"birth": "-0500-03-21 00:00:00", "day": "初一", "dayInt": 1, "month": "二月", "dayGanZi": "甲子", "dayOfWeek": 0},
            {"birth": "-0500-04-01 00:00:00", "day": "十二", "dayInt": 12, "dayGanZi": "乙丑", "dayOfWeek": 1}]
    text = _build_calendar_month_snapshot_text({"date": "-0500-03-21"}, {"days": days})
    assert "查询月份：-500-03" in text
    assert "| 03-21 | 星期日 |" in text and "04-01" not in text


def test_guolao_transit_year_reads_signed_year() -> None:
    """七政流年干支：yearFromParams 取 `-?\\d{3,4}`（旧 [:4] 对 '-0500-…' 取成 -50）。负向对照（实跑）：改回 [:4] → 红。"""
    from horosa_skill.service.runners.guolao import _guolao_year_from_date

    assert [_guolao_year_from_date(s) for s in ("-0500-03-21", "2026-10-30", "0999-01-01")] == [-500, 2026, 999]
    assert re.fullmatch(r"\d{4}", f"{_guolao_year_from_date('')}")
