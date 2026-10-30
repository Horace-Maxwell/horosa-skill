"""上游 v3.12.0/v3.13.0 民用历日期口径 · 第二批：公元前 / 1582 年前 / 五位年在择日、卜卦择日、奇门、神数、时区归一里的手抄点。

每条钉一个值级事实，期望值取自上游源本身（HOROSA_SOURCE_ROOT 指向上游 checkout：comp/DateTime.js、utils/timezone.js
原文只换 import 路径后在 node 里跑）或 vendored dateStrSafe（horosa-core-js/src/vendor/bazi），不手算。
负向对照（把改动撤回 → 必红）记在各条 docstring 里，均实际跑过。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from horosa_skill.errors import ToolValidationError
from horosa_skill.input_normalization import normalize_request_payload
from horosa_skill.service.endpoints import _dash_date_prefix, _slash_date_prefix
from horosa_skill.service.options_cn import _ken_datetime_parts, _split_birth_ymdhm
from horosa_skill.service.options_zeri import _day_span, _require_sane_window
from horosa_skill.service.runners.horary_election import HoraryElectionRunners
from horosa_skill.service.runners.sanshi import SanshiRunners
from horosa_skill.service.runners.zeri import ZeriRunners, _explain_at_text

PKG = Path(__file__).resolve().parents[1]
CORE_JS = PKG / "horosa-core-js"
CORE_JS_SRC = CORE_JS / "src"
_UPSTREAM_ROOT = os.environ.get("HOROSA_SOURCE_ROOT")
UPSTREAM_UI = Path(_UPSTREAM_ROOT) / "Horosa-Web" / "astrostudyui" / "src" if _UPSTREAM_ROOT else None
requires_upstream = pytest.mark.skipif(
    UPSTREAM_UI is None or not UPSTREAM_UI.is_dir(), reason="HOROSA_SOURCE_ROOT (upstream checkout) not set"
)
requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def _node(module: str, body: str, *args: str) -> Any:
    """import 仓内 core-js 模块 m，跑 body（可用 m / argv），打印 JSON。"""
    from node_esm import run_node_esm

    script = (
        "import(process.argv[1]).then(async (m) => { const argv = process.argv.slice(2);"
        f" const out = await (async () => {{ {body} }})(); process.stdout.write(JSON.stringify(out)); }});"
    )
    return json.loads(run_node_esm(script, CORE_JS_SRC / module, *args))


def _upstream_module(tmp_path: Path, rel: str, rewrites: dict[str, str], name: str) -> Path:
    """把上游源文件原文拷进 tmp_path，只把 import 说明符换成本机可解析的路径（不改任何逻辑行）。"""
    text = (UPSTREAM_UI / rel).read_text(encoding="utf-8")
    for spec, target in rewrites.items():
        assert f"from '{spec}'" in text, spec
        text = text.replace(f"from '{spec}'", f"from '{target}'")
    out = tmp_path / name
    out.write_text(text, encoding="utf-8")
    return out


def _run_mjs(path: Path, *args: str) -> Any:
    done = subprocess.run(["node", str(path), *args], capture_output=True, text=True, encoding="utf-8", check=True, timeout=60)
    return json.loads(done.stdout)


def _upstream_datetime(tmp_path: Path, moments: list[str]) -> list[dict[str, Any]]:
    """上游 comp/DateTime：parse(串, 'YYYY-MM-DD HH:mm:ss') → format('YYYY') / format('YYYY-MM-DD') / ad。"""
    stub = tmp_path / "dt_stub.mjs"
    stub.write_text("export default function request(){ return null; }\nexport const ServerRoot = '';\nexport const ResultKey = 'Result';\n")
    mod = _upstream_module(tmp_path, "components/comp/DateTime.js", {
        "moment": str(CORE_JS / "node_modules" / "moment" / "dist" / "moment.js"),
        "../../utils/request": str(stub),
        "../../utils/constants": str(stub),
    }, "DateTime.mjs")
    runner = tmp_path / "dt_run.mjs"
    runner.write_text(
        f"import DateTime from '{mod}';\n"
        "const out = JSON.parse(process.argv[2]).map((s) => { const d = new DateTime(); d.parse(s, 'YYYY-MM-DD HH:mm:ss');"
        " return { yyyy: d.format('YYYY'), ymd: d.format('YYYY-MM-DD'), slash: d.format('YYYY/MM/DD'), time: d.format('HH:mm:ss'), ad: d.ad }; });\n"
        "process.stdout.write(JSON.stringify(out));\n"
    )
    return _run_mjs(runner, json.dumps(moments))


# ── 择日判读时刻 t：toSlashDate（公元前前导负号保留） ─────────────────────────────────────────────────

_EXPLAIN_CASES = ["-0500-03-21 12:00", "-0500-03-21 06:43:00", "1500-02-20 12:00", "10000-01-01 09:05", "2026-04-14 09:30:15"]


@requires_node
def test_explain_at_text_keeps_bc_sign_like_upstream_to_slash_date() -> None:
    """上游 explainInterval（TianxingElectionMain.js:397）`toSlashDate(String(row.pick || `${row.start}:00`))`。
    旧 replace('-', '/') 把 '-0500-03-21' 换成 '/0500/03/21'（回显进 [单时判读] 段），旧 len == 16 判缺秒对公元前 / 五位年
    失灵（不补 ':00'）。期望 = vendored toSlashDate + 缺秒补 ':00'。负向对照：_explain_at_text 改回
    replace('-', '/') + len==16 → 公元前 / 五位年三条红。"""
    slashed = _node("vendor/bazi/dateStrSafe.js", "return JSON.parse(argv[0]).map((s) => m.toSlashDate(s));", json.dumps(_EXPLAIN_CASES))
    expected = [s if re.search(r"\d{1,2}:\d{1,2}:\d{1,2}$", s) else f"{s}:00" for s in slashed]
    assert [_explain_at_text(s) for s in _EXPLAIN_CASES] == expected
    assert expected[0] == "-0500/03/21 12:00:00"


def test_zeri_explain_requests_carry_signed_slash_t() -> None:
    """[单时判读] / 前 N 行预取两条路径发给后端的 t 都按 toSlashDate。负向对照：zeri.py 预取行改回
    `.replace("-", "/")` → 预取 t = '/0500/03/21 06:43:00' → 红。"""
    seen: list[str] = []
    runner = ZeriRunners.__new__(ZeriRunners)
    runner._call_remote = lambda endpoint, payload: (seen.append(payload["t"]), {"ResultCode": 0, "Result": {"t": payload["t"], "tree": {}}})[1]  # type: ignore[attr-defined]
    runner._require_electionscan_ok = lambda raw, endpoint: raw["Result"]  # type: ignore[attr-defined]
    runner._zeri_prefetch_explains(
        "/qizhengelectionscan/explain", {}, [{"pick": "-0500-03-21 06:43:00"}, {"start": "10000-01-01 09:05"}], {}, "七政择时"
    )
    assert seen == ["-0500/03/21 06:43:00", "10000/01/01 09:05:00"]


# ── 择日搜索窗：民用历日数（后端 _jd_from 同口径） ─────────────────────────────────────────────────

_SPAN_CASES = [
    ("-0500-03-21", "-0500-03-23"),   # 公元前：旧 split('-') 撕成 ['', '0500', …] → 恒报「无法解析搜索窗」
    ("1582-10-01", "1582-10-20"),     # 跨改历缺口：民用历 9 天（外推格里历 19 天）
    ("1500-02-28", "1500-03-01"),     # 儒略历 1500 有 2 月 29 日
    ("10000-01-01", "10000-02-01"),   # 五位年
    ("2026-04-01", "2026-04-20"),     # 现代：与旧口径同值
]


@requires_node
def test_day_span_counts_civil_days_like_backend() -> None:
    """择日搜索窗上限校验的日数 = 民用历日序差（后端 election_scan._jd_from → civil_julday 同口径）。期望值取自
    vendored civilJdnOfDateStr。负向对照：_day_span 换回 split('-') + datetime.date → 公元前 None、缺口 19、1500 年 1、
    五位年 None → 红。"""
    expected = _node(
        "vendor/bazi/dateStrSafe.js",
        "return JSON.parse(argv[0]).map(([a, b]) => m.civilJdnOfDateStr(b) - m.civilJdnOfDateStr(a));",
        json.dumps(_SPAN_CASES),
    )
    assert [_day_span(a, b) for a, b in _SPAN_CASES] == expected
    assert expected[:3] == [2, 9, 2]
    _require_sane_window("-0500-03-21", "-0500-03-23", max_span=93, tool="tianxing")  # 公元前窗口放行


def test_day_span_still_rejects_shapes_and_nonexistent_days() -> None:
    """带时刻尾巴 / ISO T 形 / 2 月 30 日 / 改历缺口日 / 0 年 → 仍判「无法解析」（旧口径的拒收面不缩）。"""
    for bad in ("2026-08-05 10:00", "2026-08-05T00:00", "2026-02-30", "1582-10-10", "0000-01-01", ""):
        assert _day_span(bad, "2026-09-01") is None, bad
    with pytest.raises(ToolValidationError):
        _require_sane_window("2026-08-05 10:00", "2026-08-06", max_span=93, tool="tianxing")


# ── 择日（electional）：危象日 / 本命主限 / chartAtMoment ─────────────────────────────────────────────

def _election_runner(captured: list[dict[str, Any]]) -> HoraryElectionRunners:
    runner = HoraryElectionRunners.__new__(HoraryElectionRunners)

    def call_remote(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        captured.append({"endpoint": endpoint, **payload})
        return {"chart": {"objects": []}, "params": {}}

    runner._call_remote = call_remote  # type: ignore[attr-defined]
    return runner


def test_election_crisis_base_accepts_bc_and_five_digit_years() -> None:
    """上游 fetchCrisisBase（ElectionMain.js:160）`/^-?\\d{4,5}-\\d{2}-\\d{2}$/`。旧 `^\\d{4}-…$` 把公元前 / 五位年的
    病始日整条拒收（tool.election_invalid_setting）。负向对照：正则改回 `^\\d{4}-\\d{2}-\\d{2}$` → 前两条 raise → 红。"""
    for date in ("-0500-03-01", "10000-01-01", "1500-02-20"):
        captured: list[dict[str, Any]] = []
        js_payload: dict[str, Any] = {}
        _election_runner(captured)._election_crisis({"crisisBase": date, "zone": "+02:00"}, js_payload)
        assert js_payload.get("crisisDate") == date
        assert captured and captured[0]["endpoint"] == "/chart"
    with pytest.raises(ToolValidationError):
        _election_runner([])._election_crisis({"crisisBase": "0500-3-1"}, {})


@requires_upstream
@requires_node
def test_election_chart_at_moment_fields_match_upstream_datetime(tmp_path: Path) -> None:
    """上游 momentPipeline.chartAtMoment：{ad, date, time} = DateTime.parse(串, 'YYYY-MM-DD HH:mm:ss') 的 ad /
    format('YYYY/MM/DD') / format('HH:mm:ss')。旧 skill 端口 ad 恒 1、日期 replace('-', '/')（'-0500-03-21' →
    '/0500/03/21'）。期望值 = 上游 DateTime 原文在 node 里跑。负向对照：_chart_at_moment 改回旧三行 → 公元前 ad / date 红。"""
    moments = ["-0500-03-21 12:00:00", "-0501-07-03 06:12:08", "1500-02-20 05:54:55", "10000-01-01 12:00:00"]
    golden = _upstream_datetime(tmp_path, moments)
    for moment, want in zip(moments, golden, strict=True):
        captured: list[dict[str, Any]] = []
        _election_runner(captured)._chart_at_moment(moment, {"zone": "+02:00"})
        sent = captured[0]
        assert (sent["ad"], sent["date"], sent["time"]) == (want["ad"], want["slash"], want["time"]), moment


def test_election_pd_natal_date_keeps_bc_sign() -> None:
    """fetchPdHits（ElectionMain.js:226）本命日期 `toSlashDate(parts[0])`。负向对照：改回 natal_date.replace('-', '/')
    → '/0530/07/04' → 红。"""
    captured: list[dict[str, Any]] = []
    runner = _election_runner(captured)
    runner._solve_return_before = lambda *a, **k: None  # type: ignore[attr-defined]
    runner._election_effective_pd_time_key = lambda payload, resolved=None: "Ptolemy"  # type: ignore[attr-defined]
    natal = {"date": "-0530-07-04", "time": "06:00:00", "zone": "+02:00", "lat": "37n58", "lon": "23e43", "ad": -1}
    runner._attach_election_natal({"date": "-0500-03-21", "time": "12:00:00"}, natal, {})
    pd_call = next(c for c in captured if c.get("predictive") == 1)
    assert pd_call["date"] == "-0530/07/04"


# ── 奇门：节气种子年 = DateTime.format('YYYY') ──────────────────────────────────────────────────────

class _StopAtKen(Exception):
    pass


def _qimen_seed_years(payload: dict[str, Any]) -> list[int]:
    years: list[int] = []
    runner = SanshiRunners.__new__(SanshiRunners)

    def call_remote(endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
        if endpoint == "/jieqi/year":
            years.append(body["year"])
            return {}
        raise _StopAtKen(endpoint)

    runner._call_remote = call_remote  # type: ignore[attr-defined]
    with pytest.raises(_StopAtKen):
        runner._run_qimen_tool({"time": "12:00:00", "zone": "+02:00", "lat": "37n58", "lon": "23e43", "nongli": {}, **payload})
    return years


@requires_upstream
@requires_node
def test_qimen_jieqi_seed_year_is_signed_display_year(tmp_path: Path) -> None:
    """上游 DunJiaMain（:1765）`parseInt(flds.date.value.format('YYYY'), 10)` = ad × year。旧 int(date[:4]) 把
    '-0500-03-21' 切成 -50、'10000-…' 切成 1000。期望值 = 上游 DateTime 原文。负向对照：sanshi.py 改回
    int(str(payload["date"])[:4]) → [-51, -50] / [999, 1000] → 红。"""
    golden = _upstream_datetime(tmp_path, ["-0500-03-21 12:00:00", "1500-02-20 12:00:00", "10000-01-01 12:00:00"])
    for date, want in zip(("-0500-03-21", "1500-02-20", "10000-01-01"), golden, strict=True):
        y = int(want["yyyy"])
        assert _qimen_seed_years({"date": date}) == [y - 1, y], date
    assert _qimen_seed_years({"date": "0500-03-21", "ad": -1}) == [-501, -500]  # 不带负号 + ad=-1 = 公元前


@requires_upstream
@requires_node
def test_core_js_fields_formatter_matches_upstream_datetime(tmp_path: Path) -> None:
    """shared/fields.js 的 fields.date.value 是上游 comp/DateTime 的替身：format('YYYY') / format('YYYY-MM-DD') 必须同形
    （ad × year、不补零）。旧 ensureDateString 只认 `\\d{4}` → 公元前 / 五位年的奇门 / 太乙 / 三式合一整条抛
    「Invalid date string」；旧 split('-') 对公元前 'YYYY' 得 ''。负向对照：ensureDateString 正则改回 `^\\d{4}-…$` → 抛 → 红。"""
    dates = ["-0500-03-21", "1500-02-20", "10000-01-01", "0999-01-02"]
    golden = _upstream_datetime(tmp_path, [f"{d} 12:00:00" for d in dates])
    got = _node(
        "shared/fields.js",
        "return JSON.parse(argv[0]).map((d) => { const f = m.makeFields({ date: d, time: '12:00:00' });"
        " return { yyyy: f.date.value.format('YYYY'), ymd: f.date.value.format('YYYY-MM-DD') }; });",
        json.dumps(dates),
    )
    assert got == [{"yyyy": g["yyyy"], "ymd": g["ymd"]} for g in golden]


@requires_node
def test_core_js_qimen_runs_for_bc_dates() -> None:
    """runQimen 公元前日期不再在 normalizeDateTimeInput 抛错，盘的「日期」随 DateTime 口径（'-500-03-21'）。"""
    out = _node(
        "tools/qimen.js",
        "const r = m.runQimen({ date: '-0500-03-21', time: '12:00:00', zone: '+02:00', lat: '37n58', lon: '23e43',"
        " options: { paiPanType: 3, school: '飞盘' } }); return { ok: !!r.data, snap: (r.snapshot_text || '').includes('-500-03-21') };",
    )
    assert out == {"ok": True, "snap": True}


# ── 神数 / ken 年月日：parseDateParts 带符号年 ───────────────────────────────────────────────────────

@requires_node
def test_shenshu_and_ken_split_keep_signed_year() -> None:
    """上游 fieldsDateTime / kinAstroFieldsSync.parseFieldsDateTime 与 DunJiaCalc.parseDateTime 都走 parseDateParts。
    旧 _split_birth_ymdhm（strptime）对公元前 / 五位年整盘拒收、拒收儒略历闰日 1500-02-29；旧 _ken_datetime_parts
    把公元前前导负号连空段一起滤掉 → 年 +500（太乙直接时间 / 奇门直接时间按公元 500 年起局）。期望年月日取自
    vendored parseDateParts。负向对照：两函数各自换回旧实现 → 公元前三条红。"""
    dates = ["-0500-03-21", "1500-02-29", "10000-01-01", "2024-05-01"]
    expected = _node("vendor/bazi/dateStrSafe.js", "return JSON.parse(argv[0]).map((d) => m.parseDateParts(d));", json.dumps(dates))
    for date, want in zip(dates, expected, strict=True):
        split = _split_birth_ymdhm({"date": date, "time": "09:05:00"})
        assert (split["year"], split["month"], split["day"], split["hour"], split["minute"]) == (want["year"], want["month"], want["day"], 9, 5)
        ken = _ken_datetime_parts({"date": date, "time": "09:05:00"})
        assert (ken["year"], ken["month"], ken["day"]) == (want["year"], want["month"], want["day"])
    for bad in ("2020-02-30", "1582-10-10", "abc"):
        with pytest.raises(ToolValidationError):
            _split_birth_ymdhm({"date": bad, "time": "12:00"})


# ── Java 日期写法重试：日期头 '-' → '/' 只换数字之间的 ───────────────────────────────────────────────

@requires_node
def test_java_slash_date_prefix_handles_signed_and_five_digit_years() -> None:
    """/chart 等 Java 日期端点的日期写法：上游 toSlashDate 只换数字之间的 '-'。旧 _slash_date_prefix 按下标 [4]/[7]
    判，公元前 / 五位年原样发出。期望 = vendored toSlashDate。负向对照：换回下标版 → 前两条红。"""
    cases = ["-0500-03-21", "10000-01-01 12:00:00", "2020-01-01", "1500-02-20 12:00:00"]
    expected = _node("vendor/bazi/dateStrSafe.js", "return JSON.parse(argv[0]).map((s) => m.toSlashDate(s));", json.dumps(cases))
    assert [_slash_date_prefix(c) for c in cases] == expected
    assert [_dash_date_prefix(e) for e in expected] == cases


# ── 入参归一：带符号年补零 + IANA 时区偏移（上游 offsetForZoneAtDate） ────────────────────────────────

def test_normalize_signed_and_five_digit_dates() -> None:
    """日期归一成 formatSignedDate 同形（负年前导负号、补足 4 位、月日补零）。旧 _DATE_RE 只认 `\\d{4}` → 公元前 /
    五位年原样透传（'-500-3-21' 进下游 `^-?\\d{4,5}-\\d{2}-\\d{2}$` 判形直接失败）。负向对照：_DATE_RE 改回 `\\d{4}` → 红。"""
    n = normalize_request_payload({"date": "-500-3-21", "guaDate": "10000/1/2", "datetime": "-500-3-21 9:5"})
    assert (n["date"], n["guaDate"], n["datetime"]) == ("-0500-03-21", "10000-01-02", "-0500-03-21 09:05:00")


_ZONE_CASES = [
    ("Europe/Athens", "-0500-03-21"),   # 公元前：旧 datetime() 抛错 → 偏移算不出、zone 原样留 IANA 名
    ("Europe/Rome", "1500-02-20"),      # 地方平时 +00:49:56：上游舍秒 +00:49（旧 round → +00:50）
    ("Europe/Rome", "1500-02-29"),      # 儒略历闰日（外推格里历平年）
    ("Europe/Athens", "10000-01-01"),   # 五位年
    ("America/New_York", "1800-01-01"), # 负的地方平时 -04:56:02 → -04:56
    ("Asia/Urumqi", "-0100-05-01"),     # 统一北京时间以前（公元前）不归并
    ("Asia/Urumqi", "2000-05-01"),      # 统一以后归并 Asia/Shanghai
    ("Europe/Athens", "2026-07-01"),    # 现代夏令时：与旧口径同值
]


@requires_upstream
@requires_node
def test_iana_zone_offset_matches_upstream_offset_for_zone_at_date(tmp_path: Path) -> None:
    """IANA 时区 → 偏移 = 上游 utils/timezone.js offsetForZoneAtDate(unifyCnZone(zone, date).zone, date)（原文只换 import
    路径，在 node 里跑 Intl）。旧实现：公元前 / 五位年 datetime() 失败 → zone 留 IANA 名；地方平时 round 进位差一分钟。
    负向对照：_format_offset_seconds 换回 round(abs(h)*60) → 罗马 / 纽约两条红；_wall_datetime_for_offset 去掉 400 年平移
    → 公元前 / 五位年红。"""
    vendor = CORE_JS_SRC / "vendor"
    tz_stub = tmp_path / "tz_stub.mjs"
    tz_stub.write_text("export default function tzLookup(){ return null; }\n")
    mod = _upstream_module(tmp_path, "utils/timezone.js", {
        "./dateTimeParse": str(vendor / "utils" / "dateTimeParse.js"),
        "tz-lookup": str(tz_stub),
        "./dateStrSafe": str(vendor / "bazi" / "dateStrSafe.js"),
    }, "timezone.mjs")
    runner = tmp_path / "tz_run.mjs"
    runner.write_text(
        f"import {{ offsetForZoneAtDate, unifyCnZone }} from '{mod}';\n"
        "process.stdout.write(JSON.stringify(JSON.parse(process.argv[2]).map(([z, d]) => offsetForZoneAtDate(unifyCnZone(z, d).zone, d))));\n"
    )
    expected = _run_mjs(runner, json.dumps(_ZONE_CASES))
    got = [normalize_request_payload({"zone": z, "date": d, "time": "12:00:00"})["zone"] for z, d in _ZONE_CASES]
    assert got == expected
    assert expected[:2] == ["+01:34", "+00:49"]


# ── 皇极轨策：ctx.year = leadingYearOf(农历回包 date) ────────────────────────────────────────────────

class _StopAtJs(Exception):
    pass


@requires_node
def test_guice_ctx_year_is_leading_year_of_nongli_date() -> None:
    """上游 GuiceMain.ctxLive（:219）`year: leadingYearOf(nl.date || '') || undefined`。旧 skill 取
    int(date.lstrip('-').split('-')[0]) × ad：公元前 '-0500-03-21'（ad 缺省 1）读成公元 500 年。期望 = vendored
    leadingYearOf(回包 date)。负向对照：cn_divination.py 换回 lstrip 版 → 500 ≠ -500 → 红。"""
    from horosa_skill.service.runners.cn_divination import CnDivinationRunners

    nongli_dates = ["-500-03-21", "1500-02-20", "10000-01-01"]
    expected = _node("vendor/bazi/dateStrSafe.js", "return JSON.parse(argv[0]).map((s) => m.leadingYearOf(s));", json.dumps(nongli_dates))
    got = []
    for payload_date, nongli_date in zip(("-0500-03-21", "1500-02-20", "10000-01-01"), nongli_dates, strict=True):
        runner = CnDivinationRunners.__new__(CnDivinationRunners)
        runner._call_remote = lambda endpoint, body, _d=nongli_date: {  # type: ignore[attr-defined]
            "date": _d, "yearJieqi": "辛丑", "monthGanZi": "辛卯", "dayGanZi": "甲子", "time": "庚午", "monthInt": 2, "dayInt": 1}
        seen: dict[str, Any] = {}

        class _Js:
            def run(self, tool: str, request: dict[str, Any]) -> Any:
                seen.update(request)
                raise _StopAtJs(tool)

        runner.js_client = _Js()  # type: ignore[attr-defined]
        with pytest.raises(_StopAtJs):
            runner._run_guice_tool({"date": payload_date, "time": "12:00:00", "zone": "+02:00", "lat": "37n58", "lon": "23e43"})
        got.append(seen.get("year"))
    assert got == expected == [-500, 1500, 10000]


@requires_upstream
@requires_node
def test_jinkou_snapshot_date_line_follows_upstream_datetime(tmp_path: Path) -> None:
    """上游 JinKouMain genGodsParams `date: flds.date.value.format('YYYY-MM-DD')`（ad × year、不补零）→ [起盘信息]
    「日期」行。旧 tools/jinkou.js 原样回带 '-0500-03-21'。期望 = 上游 DateTime 原文。负向对照：jinkou.js 改回
    `date: payload.date || ''` → 公元前 / 公元 999 年两条红。"""
    dates = ["-0500-03-21", "0999-01-02", "1500-02-20"]
    golden = _upstream_datetime(tmp_path, [f"{d} 12:00:00" for d in dates])
    got = _node("shared/fields.js", "return JSON.parse(argv[0]).map((d) => m.formatDateLikeDateTime(d, 1));", json.dumps(dates))
    assert got == [g["ymd"] for g in golden]
    jinkou_src = (CORE_JS_SRC / "tools" / "jinkou.js").read_text(encoding="utf-8")
    assert "date: payload.date ? formatDateLikeDateTime(payload.date, payload.ad) : ''" in jinkou_src


# ── 出生节气窗：括界按民用历时刻比（skill 自有行） ────────────────────────────────────────────────────

def test_jieqi_birth_bracket_brackets_bc_and_three_digit_years() -> None:
    """[出生节气窗]「出生落于 A 与 B 之间」：后端回的节气时刻是不补零的带符号年（'-500-03-11 …'，live :8877 实测），
    旧字符串比较对补零的出生串（'-0500-03-21 …'）恒判「小于」→ 公元前整行缺席。负向对照：mingli.py 括界判定换回
    `f"{prev_row.get('time')}" <= birth_key < f"{row.get('time')}"` 字符串比较 → 公元前 / 999 年两条红。"""
    from horosa_skill.service.runners.mingli import MingliRunners

    cases = [
        ("-0500-03-21", [("惊蛰", "-500-03-11 10:45:28"), ("春分", "-500-03-26 20:40:24"), ("清明", "-500-04-10 12:00:00")], "惊蛰"),
        ("-0501-12-30", [("冬至", "-501-12-22 01:00:00"), ("小寒", "-500-01-05 12:00:00")], "冬至"),
        ("0999-03-21", [("惊蛰", "999-03-06 10:00:00"), ("春分", "999-03-21 20:00:00")], "惊蛰"),
        ("1500-02-20", [("雨水", "1500-02-10 02:06:34"), ("惊蛰", "1500-02-25 01:45:37")], "雨水"),
    ]
    for date, rows, want in cases:
        runner = MingliRunners.__new__(MingliRunners)
        runner._call_remote = lambda endpoint, body, _r=rows: {  # type: ignore[attr-defined]
            "jieqi": [{"jieqi": name, "jie": True, "time": t} for name, t in _r]}
        runner._augment_export_payload = lambda **kw: {}  # type: ignore[attr-defined]
        out = runner._run_jieqi_birth_tool({"date": date, "time": "12:00:00", "zone": "+02:00", "lat": "37n58", "lon": "23e43"})
        assert f"出生落于 {want}（" in out["snapshot_text"], date


# ── horosa_dispatch → jieqi_year：年取串首带符号年 ─────────────────────────────────────────────────────

@pytest.mark.parametrize(("date", "want"), [("-0500-03-21", "-500"), ("10000-01-01", "10000"), ("1500-02-20", "1500")])
def test_dispatch_jieqi_year_takes_leading_signed_year(tmp_path: Path, date: str, want: str) -> None:
    """dispatch 给 jieqi_year 补年份：旧 str(date)[:4] 把公元前 '-0500-03-21' 切成 '-050'、五位年切成 '1000'。
    期望 = dateStrSafe.leadingYearOf 口径（'-0500' → -500）。负向对照：dispatch.py 换回 [:4] → 前两条红。"""
    from horosa_skill.config import Settings
    from horosa_skill.memory.store import MemoryStore
    from horosa_skill.service import HorosaSkillService

    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", db_path=tmp_path / "m.db",
                        output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt", data_dir=tmp_path / "data")
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    seen: dict[str, Any] = {}

    def run_tool(name: str, payload: dict[str, Any], **kwargs: Any) -> Any:
        seen[name] = payload
        raise _StopAtJs(name)

    service.run_tool = run_tool  # type: ignore[method-assign]
    with pytest.raises(_StopAtJs):
        service.dispatch(
            {"query": "节气", "birth": {"date": date, "time": "12:00:00", "zone": "+02:00", "lat": "37n58", "lon": "23e43"},
             "save_result": False, "agent_confirmed_settings": True},
            preselected_tools=["jieqi_year"],
        )
    assert seen["jieqi_year"]["year"] == want
