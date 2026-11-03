"""v0.47.0（星阙 v3.13.1 @06f25f21）同步后的三条后续：玄史天象记录的原文、古籍区段罩全多行原文、「盘主当前年龄」的出生解析。

期望值取自上游源本身（HOROSA_SOURCE_ROOT 指 Horosa-Public；xuanshiDate.js / astroAiSnapshot.js 原样在 node 里跑）、
vendored dateTimeParse.js 与上游玄史只读库，不手算。负向对照均实际跑过，记在各条 docstring 里。
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from test_local_js_tools import make_service, requires_chart

from horosa_skill.service.text.divination import (
    _build_xuanshi_snapshot_text,
    _xuanshi_brief_text,
)
from horosa_skill.textscript import TRADITIONAL
from horosa_skill.textscript.localize import classic_spans, localize

PKG = Path(__file__).resolve().parents[1]
CORE_JS_SRC = PKG / "horosa-core-js" / "src"
_UPSTREAM_ROOT = os.environ.get("HOROSA_SOURCE_ROOT")
UPSTREAM_WEB = Path(_UPSTREAM_ROOT) / "Horosa-Web" if _UPSTREAM_ROOT else None
UPSTREAM_UI = UPSTREAM_WEB / "astrostudyui" / "src" if UPSTREAM_WEB else None
XUANSHI_DB = UPSTREAM_WEB / "astropy" / "astrostudy" / "xuanshi" / "data" / "public_data.sqlite" if UPSTREAM_WEB else None
requires_upstream = pytest.mark.skipif(
    UPSTREAM_UI is None or not UPSTREAM_UI.is_dir(), reason="HOROSA_SOURCE_ROOT (upstream checkout) not set"
)
requires_xuanshi_db = pytest.mark.skipif(
    XUANSHI_DB is None or not XUANSHI_DB.is_file(), reason="HOROSA_SOURCE_ROOT xuanshi public_data.sqlite not available"
)
requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

# 上游库里的真实天象记录（/xuanshi/celestial_event?id=TWCHRON-00132，vendored v3.13.1 实例 :8877 实抓，原样）。
CELESTIAL_132: dict[str, Any] = {
    "event_id": "TWCHRON-00132", "source": "wuxing", "source_label": "天文五行年表",
    "source_file": "xuanxue_topic_tianwen_wuxing_chronology_index.csv", "row_index": 131, "history": "漢書", "volume_no": "26",
    "paragraph_no": "134", "citation": "《漢書》卷二十六（CCDH 02-026；對照 Kanripo KR2a0007），段134", "date_phrase": None,
    "era": None, "julian_date": None, "year": -77, "dynasty": "西汉", "omen_raw": "客星", "omen": "客星", "subject": "客星;星變總類",
    "action": "見", "target": "斗;奎;婁;星",
    "original": "元鳳四年九月，客星在紫宮中斗樞極間。占曰：「為兵。」其五年六月，發三輔郡國少年詣北軍。五年四月，燭星見奎、婁間。"
                "占曰「有土功，胡人死，邊城和。」其六年正月，築遼東、玄菟城。二月，度遼將軍范明友擊烏桓還。",
    "interpretation": "占辞应验;兵乱军事;臣僚官职",
    "modern": "元鳳四年九月，客星在紫宮中斗樞極間。占辞称：「为战事之象」这之后第五年六月，發三輔郡國少年詣北軍。五年四月，燭星出现奎、"
              "婁間。占辞称：「有土功，北方游牧族人死，邊城和」这之后第六年正月，築遼東、玄菟城。二月，度遼將軍范明友擊烏桓還。",
    "modern_date": "-0077-09-29", "modern_date_disp": "前77年9月", "modern_precision": "month", "has_crosswalk": False,
    "day_delta": None, "routing_theme": None, "in_chapter": False,
}


def _node(body: str, *args: Any) -> Any:
    from node_esm import run_node_esm

    script = (
        "(async () => { const argv = process.argv.slice(1); const fs = await import('node:fs');"
        f" const out = await (async () => {{ {body} }})(); process.stdout.write(JSON.stringify(out)); }})();"
    )
    return json.loads(run_node_esm(script, *args))


# ── 1. 玄史天象记录：original / modern / interpretation + 天象档案（XuanShiCelestial.js renderDetail） ─────────────


def test_celestial_detail_renders_upstream_fields_in_upstream_order() -> None:
    """上游 XuanShiCelestial.js@06f25f21 renderDetail（:358-399）：标题行「天象类 · 朝代 · 历法标注日期」、史书卷次 chip、正文
    原文 / 白话（nearSame 则不出）/ 解读、天象档案（出处=citation / 原历日 / 纪年 / 主体 / 动作 / 对象 / 公历|儒略历 / 主题）。
    此前本仓天象记录走通用键序：只认 `original_text`（天象族的键是 `original`），原文 / 白话 / 解读一格都不出，「出处」印的是机器
    来源码 wuxing。
    负向对照：_xuanshi_record_lines 去掉天象分支（走回通用键序）→ 无「原文：」行 → 红（实跑过）。"""
    text = _build_xuanshi_snapshot_text("celestial_event", {"id": "TWCHRON-00132"}, CELESTIAL_132)
    body = text.split("[条目详情]\n", 1)[1].split("\n\n", 1)[0].splitlines()
    assert body == [
        "编号：TWCHRON-00132",
        "天象类：客星",
        "朝代：西汉",
        "日期：前77年9月（儒略历）",
        "史书：《漢書》卷26",
        f"原文：{CELESTIAL_132['original']}",
        f"白话：{CELESTIAL_132['modern']}",
        "解读：占辞应验;兵乱军事;臣僚官职",
        "出处：《漢書》卷二十六（CCDH 02-026；對照 Kanripo KR2a0007），段134",
        "主体：客星;星變總類",
        "动作：見",
        "对象：斗;奎;婁;星",
        "儒略历：前77年9月",
    ]
    # nearSame（白话≈原文）→ 详情不出白话（XuanShiCelestial.js:370；玄学事件同理 XuanShiEvents.js:168）
    near = {**CELESTIAL_132, "modern": CELESTIAL_132["original"] + "。"}
    assert not any(line.startswith("白话：") for line in _build_xuanshi_snapshot_text("celestial_event", {}, near).splitlines())
    event = {"event_id": "E1", "title": "t", "original_text": "甲乙丙丁戊己庚辛壬癸", "modern_text": "甲乙丙丁戊己庚辛壬癸子"}
    assert "白话：" not in _build_xuanshi_snapshot_text("event", {}, event)


def test_celestial_list_rows_carry_date_and_original_snippet() -> None:
    """列表卡（XuanShiCelestial.js:475-487）：天象类 / 朝代 / 历法标注日期 chip + `original || interpretation || date_phrase` 一格；
    本仓另带编号（回调 celestial_event 用）与史书卷次。此前只出「编号 / 朝代 / 公历年 / 史书」四格，看不到天象本身。
    负向对照：brief 分支的 `original` 改成 `original_text` → 第一行退成「解读：…」→ 红（实跑过）。"""
    micro = {"event_id": "SONG-TW-00658", "history": "宋史", "volume_no": "53", "period": "北宋", "title": "皇祐二年三月丁酉",
             "original": "二年三月丁酉，犯軒轅大星", "year": 1050, "date_phrase": "皇祐二年三月丁酉", "era": "皇祐", "omen": "月犯",
             "interpretation": "月靠近轩辕大星。", "modern_date_disp": "1050年4月4日", "julian_date": ""}
    no_original = {**CELESTIAL_132, "original": None}
    text = _build_xuanshi_snapshot_text("celestial", {}, {"events": [CELESTIAL_132, micro, no_original], "total": 3})
    rows = text.split("[条目列表]\n", 1)[1].split("\n\n", 1)[0].splitlines()
    assert rows[0] == ("1. 编号：TWCHRON-00132；天象类：客星；朝代：西汉；日期：前77年9月（儒略历）；史书：《漢書》卷26；原文："
                       + _xuanshi_brief_text(CELESTIAL_132["original"]))
    # 微年表行只有 modern_date_disp（非 Y-M-D 串）→ 上游 celestialCalendarLabel 落「公历」（照搬，不改判儒略历）
    assert rows[1] == "2. 编号：SONG-TW-00658；天象类：月犯；日期：1050年4月4日（公历）；史书：《宋史》卷53；原文：二年三月丁酉，犯軒轅大星"
    assert rows[2].endswith("；解读：占辞应验;兵乱军事;臣僚官职")


@requires_upstream
@requires_node
@requires_xuanshi_db
def test_celestial_date_label_and_near_same_equal_upstream_xuanshiDate_over_the_real_library(tmp_path: Path) -> None:
    """日期历法标注（celestialDateWithCalendar / celestialCalendarLabel）与 nearSame 的 Python 移植 = 上游 xuanshiDate.js 原样在
    node 里跑，逐条覆盖上游玄史库全部天象记录（27196 条）+ 改历边界与旧载荷构造例。
    负向对照：_xuanshi_celestial_calendar_label 的 `mo == 10 and d < 15` 改成 `d <= 15` → 红；nearSame 阈值 0.85 改成 0.8
    → 红（均实跑过）。"""
    from horosa_skill.service.text.divination import (
        _xuanshi_celestial_calendar_label,
        _xuanshi_celestial_date,
        _xuanshi_near_same,
    )

    con = sqlite3.connect(f"{XUANSHI_DB.resolve().as_uri()}?mode=ro&immutable=1", uri=True)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(
        "SELECT event_id, modern_date, modern_date_disp, julian_date, original, modern FROM celestial_event ORDER BY event_id")]
    con.close()
    rows += [
        {"modern_date": "1582-10-14"}, {"modern_date": "1582-10-15"}, {"modern_date": "1582-09-30"}, {"modern_date": "-0500-03-04"},
        {"modern_date": "12345-01-01"}, {"modern_date": "1054-07-04", "julian_date": "1054-06-28"}, {"modern_date_disp": "前77年9月"},
        {"modern_date": "", "modern_date_disp": ""}, {"modern_date": "1600-1-2"},
    ]
    payload = tmp_path / "celestial.json"
    payload.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    js = _node(
        "const m = await import(argv[0]); const rows = JSON.parse(fs.readFileSync(new URL(argv[1]), 'utf8'));"
        " return rows.map((r) => [m.celestialDateWithCalendar(r), m.celestialCalendarLabel(r), m.nearSame(r.modern, r.original)]);",
        UPSTREAM_UI / "components" / "xuanshi" / "xuanshiDate.js", payload,
    )

    ours = [[_xuanshi_celestial_date(r), _xuanshi_celestial_calendar_label(r), _xuanshi_near_same(r.get("modern"), r.get("original"))]
            for r in rows]
    mismatches = [(rows[i].get("event_id") or rows[i], js[i], ours[i]) for i in range(len(rows)) if js[i] != ours[i]]
    assert not mismatches, mismatches[:5]
    assert len(rows) > 27000


# ── 1b. 古籍区段：罩住整段原文（含多行），且只罩原文 ─────────────────────────────────────────────


def test_classic_span_covers_multiline_original_and_stops_at_the_next_field() -> None:
    """上游 XuanShiEvents.js:113 原文容器（pre-line）整块挂 horosa-script-classic；玄学事件 original_text 有 2209 条带换行。
    v0.47.0 的 classic_spans 只罩「原文：」那一行 → 续行里的「范 / 里」在繁体输出被转成「範 / 裡」。
    负向对照：classic_spans 的续行判断改成恒 break（只罩「原文：」那一行）→ 红（实跑过）。"""
    event = {"event_id": "SHIJI-CQ-028", "title": "赵简子梦游帝所",
             "original_text": "《史記》卷四十三，段24\n帝告我：『晉國且世衰，嬴姓將大敗周人於范魁之西。』\n\n昭国里中",
             "modern_text": "天帝说赢姓将在范魁之西大败周人", "reading": "范魁"}
    text = _build_xuanshi_snapshot_text("event", {"id": "SHIJI-CQ-028"}, event)
    assert [text[a:b] for a, b in classic_spans(text)] == [event["original_text"]]
    out = localize({"tool": "xuanshi", "data": {"snapshot_text": text}}, TRADITIONAL)["data"]["snapshot_text"]
    assert "嬴姓將大敗周人於范魁之西" in out and "\n昭國里中\n" in out  # 原文续行：范 / 里 保留
    assert "白話：天帝說贏姓將在範魁之西大敗周人" in out and "解讀：範魁" in out  # 原文之后的格照通用档
    # 天象详情：原文后接「白话」行；列表行：原文是最后一格 → 止于下一条「2. 」与段头
    cel = _build_xuanshi_snapshot_text("celestial_event", {}, CELESTIAL_132)
    assert [cel[a:b] for a, b in classic_spans(cel)] == [CELESTIAL_132["original"]]
    listing = _build_xuanshi_snapshot_text("celestial", {}, {"events": [CELESTIAL_132, CELESTIAL_132]})
    assert [listing[a:b] for a, b in classic_spans(listing)] == [_xuanshi_brief_text(CELESTIAL_132["original"])] * 2
    hant = localize({"tool": "xuanshi", "data": {"snapshot_text": cel}}, TRADITIONAL)["data"]["snapshot_text"]
    assert "度遼將軍范明友擊烏桓還。\n白話：" in hant and "白話：" in hant and "度遼將軍範明友擊烏桓還。\n解讀" in hant


@requires_xuanshi_db
def test_classic_span_equals_the_original_for_every_record_in_the_library() -> None:
    """逐条渲染上游玄史库全部记录（玄学事件 7921 + 天象 27196）的详情快照：古籍区段恰好 == 原文本身（一段、不多不少）；天象列表
    每页 20 条，区段 == 各条原文片段。守住「区段止于下一格」的标签集与渲染器的格名同步（加了新格忘了登记就会把下一格吞进古籍档）。
    负向对照：localize._CLASSIC_NEXT_LABELS 去掉「出处」→ 原文后直接接「出处」行的天象详情把出处吞进古籍档 → 红；去掉续行
    循环（只罩「原文：」那一行）→ 红（均实跑过）。"""
    con = sqlite3.connect(f"{XUANSHI_DB.resolve().as_uri()}?mode=ro&immutable=1", uri=True)
    con.row_factory = sqlite3.Row
    bad: list[Any] = []
    checked = 0
    for table, key in (("xuanxue_event", "original_text"), ("celestial_event", "original")):
        rows = [dict(r) for r in con.execute(f"SELECT * FROM {table}")]
        for rec in rows:
            value = rec.get(key)
            if value is None or not f"{value}".strip():
                continue
            checked += 1
            text = _build_xuanshi_snapshot_text("event", {}, rec)
            if [text[a:b] for a, b in classic_spans(text)] != [f"{value}".rstrip("\n \t")]:
                bad.append((table, rec.get("event_id")))
        if table == "celestial_event":
            for i in range(0, len(rows), 20):
                chunk = rows[i:i + 20]
                text = _build_xuanshi_snapshot_text("celestial", {}, {"events": chunk})
                want = [_xuanshi_brief_text(r[key]) for r in chunk if r.get(key) is not None and f"{r[key]}".strip()]
                if [text[a:b] for a, b in classic_spans(text)] != want:
                    bad.append(("celestial_list", i))
    con.close()
    assert checked > 33000 and not bad, bad[:5]


@requires_chart
def test_live_celestial_event_original_renders_and_keeps_classic_chars(tmp_path: Path) -> None:
    """vendored v3.13.1 实例：celestial_event 详情出原文 / 白话 / 解读 / 天象档案；繁体出口原文里「范明友」保留，白话里照通用档。"""
    result = make_service(tmp_path).run_tool("xuanshi", {"action": "celestial_event", "id": "TWCHRON-00132"}, save_result=False)
    assert result.ok, result.error
    lines = result.data["snapshot_text"].splitlines()
    assert f"原文：{CELESTIAL_132['original']}" in lines and "日期：前77年9月（儒略历）" in lines and "动作：見" in lines
    hant = localize(result, TRADITIONAL).data["snapshot_text"]
    assert "度遼將軍范明友擊烏桓還。\n白話：" in hant and "度遼將軍範明友擊烏桓還。\n解讀" in hant


# ── 3. 盘主当前年龄：出生串按 parseLocalDateTimeMs 全式解析（astroAiSnapshot.js birthInstantMsInZone） ─────────

NOW_UTC = datetime(2026, 10, 30, 4, 0, 0, tzinfo=timezone.utc)
AGE_BIRTHS = [
    "1995-06-05 05:30:00", "1995-06-05 05:30", "1995-06-05T05:30:45", "1995-06-05 05:30:59.9", "1995/06/05 05:30",
    "1995/06-05 05:30", "1995-6-5 5:30", "1995-06-05 24:00", "1995-06-05  05:30", "1995-06-05", "1995-06", "1995",
    "2000-02-29 12:00", "1900-02-29 12:00", "1827-01-01 00:00", "1826-11-01 00:00", "1500-02-29 12:00", "-0500-03-04 12:00",
    "12345-01-01", "+001995-06-05 05:30", "1995-06-05 05:30:00+08:00", "1995-06-05 05:30Z", "1995-06-05 25:00",
    "1995-13-01", "1995-02-30", "garbage", "2026-12-01 00:00", "2027-10-29 00:00", "2027-11-01 00:00", "95-06-05",
]
AGE_ZONES = ["+08:00", "-10:00", "+05:45:30", "+14:00", "bogus", "+8:00", None]


def _upstream_age_lines(cases: list[tuple[str, Any]], tmp_path: Path) -> list[str | None]:
    """上游 buildCurrentMomentLines + birthInstantMsInZone 原文（从 astroAiSnapshot.js 抽出函数体）+ vendored dateTimeParse.js，
    在 node 里以冻结的 new Date() 跑；返回每例的「盘主当前年龄」行（无 → None）。"""
    payload = tmp_path / "age.json"
    payload.write_text(json.dumps({"now": NOW_UTC.timestamp() * 1000, "cases": cases}), encoding="utf-8")
    return _node(
        "const dtp = await import(argv[0]); const src = fs.readFileSync(new URL(argv[1]), 'utf8');"
        " const grab = (head) => { const at = src.indexOf(head); if (at < 0) throw new Error('missing ' + head);"
        "   return src.slice(at, src.indexOf('\\n}\\n', at) + 2); };"
        " const body = grab('function birthInstantMsInZone(') + grab('export function buildCurrentMomentLines(').replace('export ', '');"
        " const { now, cases } = JSON.parse(fs.readFileSync(new URL(argv[2]), 'utf8'));"
        " const RealDate = Date; class FrozenDate extends RealDate { constructor(...a) { super(...(a.length ? a : [now])); }"
        "   static now() { return now; } }"
        " const build = new Function('parseLocalDateTimeMs', 'Date', body + '; return buildCurrentMomentLines;')(dtp.parseLocalDateTimeMs, FrozenDate);"
        " return cases.map(([birth, zone]) => (build({ params: { birth, zone } }).find((l) => l.startsWith('盘主当前年龄：')) || null));",
        CORE_JS_SRC / "vendor" / "utils" / "dateTimeParse.js", UPSTREAM_UI / "utils" / "astroAiSnapshot.js", payload,
    )


@pytest.fixture
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    from horosa_skill.service import _clock

    local_now = NOW_UTC.astimezone().replace(tzinfo=None)  # 本机钟面（_clock.now() 的语义）

    class _Frozen(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return NOW_UTC.astimezone(tz) if tz is not None else local_now

    monkeypatch.setattr(_clock, "datetime", _Frozen)


@requires_upstream
@requires_node
def test_current_age_line_equals_upstream_for_every_birth_shape(frozen_clock: None, tmp_path: Path) -> None:
    """上游 astroAiSnapshot.js@06f25f21 :1978-2004：出生串经 parseLocalDateTimeMs（秒 / 小数秒 / T 或多个空白 / 斜杠横杠混用 / 24:00
    次日 / 2 月 29 日恒认 / 带时区尾巴 / 只有年或年月）读成本机钟面，再按本盘时区折成真实瞬时；-1 < 年龄 < 200 才出行。
    此前两处都用 strptime：predictive 截前 16 位（秒被丢、T 与 24:00 退成当日 0 点、1900-02-29 / 只有年不出行），astroextra
    认不出 24:00 / 多空白 / 时区尾巴，无时区时纯日期按 UTC 0 点（上游是本机 0 点）。儒略历 2 月 29 日 / 公元前 / 5 位年的出生
    上游年龄 ≥200 → 恒不出行，与此前一致（该类输入行为本来相同，本例一并钉住）。
    负向对照：civil_calendar._parse_date_time_parts 的 `hour > 24` 改成 `hour > 23`（不认 24:00）→ 24:00 七例红；
    _parse_local_date_time_ms 改回 date_only_utc=True（Date.parse 的纯日期 UTC 口径）→ 纯日期例红（均实跑过，本机 EST）。"""
    from horosa_skill.engine import astroextra_snapshots as ax
    from horosa_skill.service.text import predictive as T

    cases = [(b, z) for b in AGE_BIRTHS for z in AGE_ZONES]
    upstream = _upstream_age_lines(cases, tmp_path)
    ours_ax, ours_pred = [], []
    for birth, zone in cases:
        lines = ax.current_moment_lines({"params": {"birth": birth, "zone": zone}}, None, NOW_UTC)
        ours_ax.append(next((x for x in lines if x.startswith("盘主当前年龄：")), None))
        text = T._predictive_common_sections_text("agepoint", {"date": birth, "time": "", "zone": zone})
        ours_pred.append(next((x for x in text.splitlines() if x.startswith("盘主当前年龄：")), None))
    assert [(c, u, a) for c, u, a in zip(cases, upstream, ours_ax) if u != a] == []
    assert [(c, u, p) for c, u, p in zip(cases, upstream, ours_pred) if u != p] == []
    # 用例确实覆盖到「出行 / 不出行」两边，以及此前 strptime 认不出的形状
    printed = {c[0] for c, u in zip(cases, upstream) if u}
    assert {"1995-06-05 24:00", "1995-06-05  05:30", "1900-02-29 12:00", "1995", "1995-06-05 05:30Z"} <= printed
    assert not printed & {"1500-02-29 12:00", "-0500-03-04 12:00", "12345-01-01", "garbage", "2027-11-01 00:00", "95-06-05"}
