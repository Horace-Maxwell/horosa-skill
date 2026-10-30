"""上游 v3.13.0 同步 · 手抄口径（Python 端口 / tools/*.js 胶水）随上游改动的回归钉。

每条都钉「上游 v3.11.3 → v3.13.0 改了、而 skill 这边是手抄的」那一处的**值级事实**：期望值取自 vendored 引擎
（node 跑 horosa-core-js/src/vendor）或上游源本身（HOROSA_SOURCE_ROOT 指向上游 checkout 时），不手算。
负向对照（把移植撤回 → 必红）记在各条 docstring 里，均实际跑过。
"""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from horosa_skill.service import _common
from horosa_skill.service.runners.horary_election import HoraryElectionRunners
from horosa_skill.service.runners.zeri import ZeriRunners

PKG = Path(__file__).resolve().parents[1]
CORE_JS_SRC = PKG / "horosa-core-js" / "src"
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


# ── 民用历墙钟轴：_shift_moment / _civil_* ≡ vendored civilShiftDateTimeStr ──────────────────────────────

_SHIFT_CASES = [
    ("2026-04-14 12:00:00", 3.25),
    ("2026-04-14 12:00:00", -1.0000004),       # 毫秒取整（Math.round）+ 秒向下取整
    ("2024-02-28 23:59:59", 1.0),              # 格里历闰日
    ("1500-02-28 12:00:00", 1.0),              # 儒略历 1500 年有 2 月 29 日（外推格里历没有）
    ("1582-10-17 12:00:00", -3.0),             # 跨改历缺口：10-14 落回儒略历 10-04
    ("1582-10-04 18:00:00", 0.5),              # 次日是 10-15
    ("0999-12-31 23:00:00", 0.1),              # 四位补零年
    ("-0500-04-14 12:00:00", 2.0),             # 公元前（历史纪年）
    ("-0001-12-31 12:00:00", 1.0),             # 公元前 1 年之后是公元 1 年（无 0 年）
    ("1582-10-10 12:00:00", 1.0),              # 不存在的日子 → 认不出
    ("2023-02-29 12:00:00", 1.0),              # 平年 2 月 29 日 → 认不出
    ("0000-01-01 12:00:00", 1.0),              # 0 年 → 认不出
]


@requires_node
def test_civil_shift_matches_vendored_civil_shift_datetime_str() -> None:
    """上游 v3.13.0 solunar.shiftMoment / vedicMundane.solveVedicSolarIngress 改走 civilShiftDateTimeStr（民用历墙钟轴，
    1582 以前儒略历、公元前历史纪年，位移 Math.round(天×86400000) 毫秒）。Python 端口逐例对拍 vendored JS。
    负向对照：_common._shift_moment 换回 datetime.strptime + timedelta 版 → 1500-02-28 / 1582 缺口 / 公元前三例红
    （公元前直接 ValueError）。"""
    expected = _node(
        "vendor/bazi/dateStrSafe.js",
        "return JSON.parse(argv[0]).map(([s, d]) => m.civilShiftDateTimeStr(s, Math.round(d * 86400000)));",
        json.dumps(_SHIFT_CASES),
    )
    got = [_common._civil_shift_moment(s, _common._js_math_round(d * 86400000)) for s, d in _SHIFT_CASES]
    assert got == expected
    # 认不出 → shiftMoment 原样返回（上游 `out || String(momentStr)`）
    assert [_common._shift_moment(s, d) for s, d in _SHIFT_CASES] == [e or s for e, (s, _) in zip(expected, _SHIFT_CASES)]
    assert expected[3] == "1500-02-29 12:00:00" and expected[4] == "1582-10-04 12:00:00"


@requires_node
def test_date_part_of_matches_vendored() -> None:
    """datePartOf 端口（election 主限命中的日期段）对拍 vendored dateStrSafe.datePartOf。"""
    cases = ["2026-04-14 12:00:00", "-0300-03-10 08:00", "12000/01/01", "1500-2-9T10:00", "garbage-text-123"]
    expected = _node("vendor/bazi/dateStrSafe.js", "return JSON.parse(argv[0]).map((s) => m.datePartOf(s));", json.dumps(cases))
    assert [_common._date_part_of(c) for c in cases] == expected


@requires_node
def test_election_pd_hit_delta_days_counts_civil_days() -> None:
    """上游 v3.13.0 fetchPdHitsNearElection：日差 = momentOfCivilDateTimeStr(datePartOf(..)).diff(elec, 'days')
    （民用历日序）。1500 年儒略历有 2 月 29 日 → 1500-02-28 → 1500-03-01 隔 2 天（外推格里历只隔 1 天）。
    期望值取自 vendored civilDayDiffOfStr。负向对照：换回 strptime(date[:10]) 版 → deltaDays 1 ≠ 2 → 红。"""
    expected = _node(
        "vendor/bazi/dateStrSafe.js",
        "return [m.civilDayDiffOfStr('1500-02-28', '1500-03-01'), m.civilDayDiffOfStr('1500-02-28', '1499-12-25')];",
    )
    runner = HoraryElectionRunners.__new__(HoraryElectionRunners)
    rows = [[1.0, "Sun", "Asc", "D", "1500-03-01 10:00:00"], [2.0, "Moon", "MC", "D", "1499-12-25"]]
    runner._call_remote = lambda endpoint, payload: {"predictives": {"primaryDirection": rows}}  # type: ignore[attr-defined]
    hits = runner._election_pd_hits({"date": "1450-01-01"}, "1500-02-28 09:00:00", None)
    assert [h["deltaDays"] for h in hits] == expected
    assert hits[0]["date"] == "1500-03-01"


# ── 择日：太乙择时展示盘日界缺省 = 全局出厂值（与扫描引擎同） ─────────────────────────────────────

@requires_node
def test_taiyizeri_display_day_boundary_default_follows_scan_engine() -> None:
    """上游 v3.13.0：TaiyiZeriMain.buildFields 与 taiyiZeriScanEngine.computeTaiyiScanPan 的日界缺省都从 0 改成
    defaultAfter23NewDay()（全局出厂 = 1）。skill 的展示盘覆写手抄了旧缺省 0 → 展示盘「24点算第二天」、扫描按 23 点换日。
    期望值取自 vendored dayBoundary（扫描引擎 import 的同一份）。负向对照：zeri.py 改回 eff("after23NewDay", 0) → 红。"""
    defaults = _node("vendor/bazi/dayBoundary.js", "return [m.defaultAfter23NewDay(), m.defaultLateZiHourUseNextDay()];")
    out = ZeriRunners._zeri_display_overrides("taiyizeri", {"tn": 0})
    assert [out["after23NewDay"], out["lateZiHourUseNextDay"]] == defaults == [1, 1]
    assert ZeriRunners._zeri_display_overrides("taiyizeri", {"tn": 0, "after23NewDay": 0})["after23NewDay"] == 0


@requires_upstream
def test_taiyizeri_upstream_build_fields_uses_global_day_boundary() -> None:
    """上游源对拍：TaiyiZeriMain.buildFields 的日界缺省是 defaultAfter23NewDay()（不再是字面 0）。"""
    src = (UPSTREAM_UI / "components" / "zeri" / "TaiyiZeriMain.js").read_text(encoding="utf-8")
    start = src.index("buildFields(frozen){")
    body = src[start: src.index("onEmbedFieldsChange", start)]
    assert "o.after23NewDay !== undefined ? o.after23NewDay : defaultAfter23NewDay()" in body


# ── 六爻：mergeLiuyaoGearSettings（v3.13.0 regenCase.js:447-491）─────────────────────────────────────

@requires_node
def test_liuyao_gear_merge_marks_custom_and_keeps_case_inputs() -> None:
    """上游 v3.13.0 mergeLiuyaoGearSettings：① 偏离所选预设的齿轮键经 setOption 落 → 流派标「custom」（此前单改卦身
    仍自称「通用」）；② 换派时 askType/yongOverride/benming 不随预设改；③ 神煞以合并后的值为底。
    期望值由 vendored liuyaoSchools.applyPreset/setOption 直接推（不手算）。
    负向对照：liuyao.js 换回 v3.11 版（base[k]=f[k] 直写、不经 setOption）→ guashen 例 school 仍为 'default' → 红。"""
    got = _node(
        "tools/liuyao.js",
        "return [m.mergeLiuyaoGearSettings({}, {guashen: false}),"
        " m.mergeLiuyaoGearSettings({}, {school: 'zengshan', askType: 'wealth'}),"
        " m.mergeLiuyaoGearSettings({}, {school: 'zengshan', shenshaOn: 1}),"
        " m.mergeLiuyaoGearSettings({}, {})];",
    )
    ref = _node(
        "vendor/gua/liuyaoSchools.js",
        "const base = m.normalizeLiuyaoSettings(null);"
        " return [m.setOption(base, 'guashen', false),"
        " m.setOption({...m.applyPreset('zengshan', base), askType: base.askType}, 'askType', 'wealth'),"
        " m.setOption({...m.applyPreset('zengshan', base), askType: base.askType}, 'shensha', {on: true})];",
    )
    assert got[0] == ref[0] and got[0]["school"] == "custom" and got[0]["guashen"] is False
    assert got[1] == ref[1] and got[1]["school"] == "zengshan" and got[1]["askType"] == "wealth"
    assert got[2] == ref[2] and got[2]["school"] == "custom" and got[2]["shensha"]["on"] is True
    assert got[3] == {}


# ── 五兆：挂载复现说明原句（v3.13.0 措辞）─────────────────────────────────────────────────────────

@requires_upstream
def test_wuzhao_replay_note_wording_matches_upstream_source() -> None:
    """shenshu.py 手抄了上游 buildWuZhaoSnapshotForFields 的复现说明原句；上游 v3.13.0 改了措辞。
    这里从上游源取原句模板，代入「日干起盘」比对 skill 实发的那句（tests/test_sync311_shenshu.py 钉 skill 侧整句）。
    负向对照：shenshu.py 换回「开启「手动分爻复现」…已按干支起例」→ 红。"""
    src = (UPSTREAM_UI / "components" / "wuzhao" / "WuZhaoMain.js").read_text(encoding="utf-8")
    match = re.search(r"replayNote = `挂载无法复现随机起兆\(所选「\$\{wuzhaoModeLabel\(calc\.mode\)\}」需\$\{.*?: '([^']+)'\)?\};([^`]+)`", src)
    assert match, "上游 WuZhaoMain.js 的复现说明模板变形了——复核 shenshu._wuzhao_calc_payload"
    upstream = f"挂载无法复现随机起兆(所选「日干起盘」需{match.group(1)};{match.group(2)}"
    shenshu_src = (PKG / "src" / "horosa_skill" / "service" / "runners" / "shenshu.py").read_text(encoding="utf-8")
    skill = re.search(r'f"(挂载无法复现随机起兆\(所选「\{_WUZHAO_MODE_LABELS\[mode\]\}」[^"]+)"\s*"([^"]+)"', shenshu_src)
    assert skill
    assert (skill.group(1) + skill.group(2)).replace("{_WUZHAO_MODE_LABELS[mode]}", "日干起盘") == upstream


# ── 日子馆：当事人八字的日界 / 晚子时随全局（RiziMain.baziOf）──────────────────────────────────────

@requires_node
def test_rizi_person_bazi_uses_global_day_boundary() -> None:
    """上游 RiziMain.baziOf 显式下发 after23NewDay / lateZiHourUseNextDay = 全局（出厂 1/1）。vendored v3.13.0
    buildLocalBaziResult 缺键也取全局（resolveAfter23NewDay），故此处钉的是「skill 实发的日界 = 全局出厂 23 点换日」：
    23:30 生人 [当事人八字] 的日主（日干）= vendored personBazi(after23=1)，≠ after23=0。
    负向对照：calendarExtras.js 把 after23NewDay 改成 0 → 日柱落成 after23=0 那一柱 → 红（vendored 缺键自愈，
    所以「删掉两键」这条对照不红——如实记）。"""
    person = {"date": "1990-05-05", "time": "23:30:00", "gender": 1}
    on_day, off_day = _node(
        "vendor/calendar/riziEngine.js",
        "const p = JSON.parse(argv[0]); return [m.personBazi({...p, after23NewDay: 1, lateZiHourUseNextDay: 1}).dayGZ,"
        " m.personBazi({...p, after23NewDay: 0, lateZiHourUseNextDay: 1}).dayGZ];",
        json.dumps(person),
    )
    assert on_day and off_day and on_day != off_day, "夹具须落在 23 点换日窗口内（两种日界日柱不同）"
    text = _node(
        "tools/calendarExtras.js",
        "return m.runCalendarExtras({year: 2026, month: 6, day: 1, rizi: {event: 'marriage', year: 2026, persons: [JSON.parse(argv[0])]}}).text;",
        json.dumps({**person, "name": "甲", "role": "self"}),
    )
    section = text[text.index("[当事人八字]"):]
    nxt = section.find("\n[", 1)
    section = section[:nxt] if nxt > 0 else section
    # [当事人八字] 行只印日主（日干）：两种日界的日干不同即足以判。
    assert f"日主{on_day[0]}" in section and f"日主{off_day[0]}" not in section


# ── 大六壬：timeAlg 进 builder（v3.13.0 main/snapshot.js:20-26）───────────────────────────────────

@requires_node
def test_liureng_snapshot_prints_clock_time_line_when_time_alg_is_1(tmp_path: Path) -> None:
    """上游 v3.13.0 buildLiuRengSnapshotText 读 params.timeAlg：=1 时 [起盘信息] 出「时间算法：直接时间(按钟表时定时辰)」。
    skill 此前不把 timeAlg 交给 builder → 选了直接时间，快照里看不出来。
    负向对照：liureng.js 的 params 去掉 timeAlg → 红。"""
    fixture = json.loads((PKG / "horosa-core-js" / "test" / "fixtures" / "chart_liureng.json").read_text(encoding="utf-8"))
    base = {**fixture, "date": "2026-04-04", "time": "21:18:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"}
    # 盘 JSON 走临时文件、不走命令行参数：Windows 命令行上限约 32 KB，整盘夹具塞进 argv 报 WinError 206（windows-smoke 实红过）。
    payload = tmp_path / "liureng_payload.json"
    payload.write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8", newline="\n")
    texts = _node(
        "tools/liureng.js",
        "const fs = await import('node:fs'); const p = JSON.parse(fs.readFileSync(argv[0], 'utf8'));"
        " return [m.runLiureng(p).snapshot_text,"
        " m.runLiureng({...p, options: {timeAlg: 1}}).snapshot_text, m.runLiureng({...p, timeAlg: 1}).snapshot_text];",
        str(payload),
    )
    line = "时间算法：直接时间(按钟表时定时辰)"
    assert line not in texts[0]
    assert line in texts[1] and line in texts[2]


# ── 巴比伦：/chart 没回七曜 → 不出快照（v3.13.0 buildBabylonSnapshotForFields）───────────────────────

@requires_node
def test_babylon_refuses_snapshot_without_planet_positions() -> None:
    """上游 v3.13.0：七曜位置为空即抛错、不出快照（此前空 lons 照样铺六段）。负向对照：babylon.js 去掉空检 → text 非空 → 红。"""
    out = _node("tools/babylon.js", "return m.runBabylon({year: 2000, month: 1, day: 1, chart: {chart: {objects: []}}});")
    assert out["text"] == "" and out["error"] == "no_planet_positions"


@requires_node
def test_babylon_tool_reports_missing_planet_positions_instead_of_an_empty_snapshot(tmp_path) -> None:
    """runner 侧：JS 回 error=no_planet_positions → 结构化报错（tool.babylon_chart_unavailable），不再交出空快照。
    负向对照：去掉 _run_babylon_tool 里该分支 → env.ok 为真、断言红（实跑过）。"""
    import copy

    from fakes import FakeClient
    from test_sync311_w3b_gim import _service

    class _EmptyChart(FakeClient):
        def call(self, endpoint: str, payload: dict) -> dict:
            if endpoint in ("/", "/chart"):
                return {"chart": {"objects": []}, "params": copy.deepcopy(payload)}
            return super().call(endpoint, payload)

    env = _service(tmp_path, _EmptyChart()).run_tool(
        "babylon", {"date": "2000-01-01", "time": "12:00:00", "zone": "+00:00", "lat": "32n33", "lon": "44e25",
                    "agent_confirmed_settings": True}, save_result=False)
    assert not env.ok
    assert env.error.code == "tool.babylon_chart_unavailable"
