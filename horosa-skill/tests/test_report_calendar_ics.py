"""报告 format=ics（v0.48.0，reports/calendar_ics.py）：结果里现成的日期 → RFC 5545 日历；不推算任何日期。

金样来自真引擎录下的结果（tests/fixtures/calendar_ics_live.json，录制方式见其 _comment），两个择日（黄历择吉 / 奇门择日 -05:00）
+ 两个推运（回归轴 / 法达星限）；ICS 逐字节对金样（tests/fixtures/calendar_ics/*.ics）。每份输出都过 tests/ics_validator.py。
重录金样：`uv run python tests/test_report_calendar_ics.py`（写 tests/fixtures/calendar_ics/），然后逐份读一遍再提交。
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from ics_validator import content_lines, events_of, unescape, validate_ics

from horosa_skill.errors import ToolValidationError, classify_code, recovery_for
from horosa_skill.reports.calendar_ics import (
    CALENDAR_TOOLS,
    CalendarEvent,
    escape_text,
    extract_calendar,
    fold_line,
    render_ics,
)
from horosa_skill.reports.source import report_technique_name

FIXTURES = Path(__file__).parent / "fixtures"
CASES = json.loads((FIXTURES / "calendar_ics_live.json").read_text(encoding="utf-8"))["cases"]
STAMP = datetime(2026, 11, 8, 4, 0, tzinfo=timezone.utc)
GOLDENS = ("huanglizeri", "qimenzeri_ny", "returntimeline", "firdaria")


def _label(case: dict) -> str:
    technique = case["data"]["export_snapshot"]["technique"]
    return report_technique_name(case["tool"], str(technique.get("label") or case["tool"]))


def _extract(name: str, data: dict | None = None):
    case = CASES[name]
    return extract_calendar(case["tool"], data if data is not None else case["data"], input_normalized=case["input_normalized"],
                            label=_label(case), run_id="golden")


def _ics(name: str) -> bytes:
    return render_ics(_extract(name).events, run_id="golden", dtstamp=STAMP, calendar_name=f"{_label(CASES[name])} · 星阙 Horosa").encode("utf-8")


@pytest.mark.parametrize("name", GOLDENS)
def test_golden_ics_matches_byte_for_byte(name: str) -> None:
    produced = _ics(name)
    golden = FIXTURES / "calendar_ics" / f"{name}.ics"
    assert validate_ics(produced) == []
    expected = golden.read_bytes()
    # 金样必须是 CRLF：.gitattributes 的 `*.ics -text` 一丢，git 会在提交时把它归一成 LF，这里先说清楚原因再比字节。
    assert b"\r\n" in expected and b"\n" not in expected.replace(b"\r\n", b""), "金样被换行归一了：检查 .gitattributes 的 *.ics -text"
    assert produced == expected


@pytest.mark.parametrize("name", sorted(CASES))
def test_every_recorded_result_exports_valid_ics_with_one_event_per_dated_item(name: str) -> None:
    case = CASES[name]
    extraction = _extract(name)
    assert extraction.skipped == []
    data = case["data"]
    expected = {
        "election": 1,
        "qizhengelection": len(data.get("eclipses") or data.get("hits") or [None]),
        "returntimeline": 2 * len(data.get("rows") or []),
        "firdaria": sum(len(m["subDirect"]) for m in data.get("firdaria") or []),
        "zr": sum(1 + len(p["sublevel"]) for p in data.get("zr") or []),
        "decennials": sum(1 + len(p["sublevel"]) for p in (data.get("timeline") or {}).get("list") or []),
        "ephemeris": sum(len(v) for v in (data.get("ephemeris") or {}).values()),
        "distributions": len(data.get("distributions") or []) + len(data.get("partners") or []),
    }.get(case["tool"], len(data.get("intervals") or []))
    assert len(extraction.events) == expected > 0
    produced = _ics(name)
    assert validate_ics(produced) == []
    uids = [event["UID"] for event in events_of(produced)]
    assert uids == [f"golden-{i}@horosa-skill" for i in range(1, expected + 1)]


def test_election_summary_carries_the_score_as_the_result_states_it() -> None:
    (event,) = events_of(_ics("election"))
    verdict = CASES["election"]["data"]["export_snapshot"]["sections"][0]["body"].splitlines()[0]
    assert verdict.startswith("52/100") and event["SUMMARY"] == f"择日盘·结婚/订婚 {verdict}"
    assert "月亮逢刑" in event["DESCRIPTION"]  # 红线 / 建议进说明
    assert event["DTSTART"] == "20280406T013300Z"  # 2028-04-06 09:33 +08:00


def test_zeri_events_take_the_window_and_the_hit_reasons_from_the_result() -> None:
    events = events_of(_ics("qimenzeri"))
    first = CASES["qimenzeri"]["data"]["intervals"][0]
    assert first["start"] == "2028-04-01 18:58" and first["end"] == "2028-04-01 20:58"
    assert events[0]["DTSTART"] == "20280401T105800Z" and events[0]["DTEND"] == "20280401T125800Z"
    assert events[0]["SUMMARY"] == f"奇门择日 命中 1/{len(events)} 阳遁九局中元"
    assert "设定 吉格·青龙回首 → 实际 青龙回首@兑7宫 ✓" in events[0]["DESCRIPTION"]
    assert "条件：吉格·青龙回首" in events[0]["DESCRIPTION"]
    assert "判读" not in events[-1]["DESCRIPTION"]  # 正文只给前几条附判读，后面的不硬配


def test_hit_reasons_attach_only_to_the_hit_they_were_written_for() -> None:
    """正文命中清单按序号写判读；结果的区间顺序与正文对不上时（这里倒过来），不能把第 1 条的判读安到别的区间上。"""
    data = copy.deepcopy(CASES["qimenzeri"]["data"])
    data["intervals"] = data["intervals"][::-1]
    assert sum("判读" in e.description for e in _extract("qimenzeri").events) == 3  # 原序：正文前 3 条带判读
    assert all("判读" not in e.description for e in _extract("qimenzeri", data).events)  # 倒序：一条都对不上


def test_utc_conversion_uses_the_results_own_zone_not_plus_eight() -> None:
    """-05:00 的结果：本地 19:00 → 次日 00:00Z；与结果自己的毫秒时间戳逐条一致（换成 +08:00 解读就差 13 小时）。"""
    events = events_of(_ics("qimenzeri_ny"))
    intervals = CASES["qimenzeri_ny"]["data"]["intervals"]
    assert intervals[0]["start"] == "2028-04-01 19:00" and events[0]["DTSTART"] == "20280402T000000Z"
    for event, interval in zip(events, intervals):
        assert event["DTSTART"] == datetime.fromtimestamp(interval["startMs"] / 1000, timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    returns = events_of(_ics("returntimeline_ny"))
    row = CASES["returntimeline_ny"]["data"]["rows"][0]["solarReturn"]
    assert row["datetime"] == "2026-04-06 22:10:02" and returns[0]["DTSTART"] == "20260407T031002Z"


def test_a_local_time_that_disagrees_with_the_results_absolute_instant_is_not_exported() -> None:
    """结果里本地时刻与 JD / 毫秒对不上（时区读错就是这样）：这一条不进日历、说明原因——两处对不上不收。"""
    data = copy.deepcopy(CASES["returntimeline"]["data"])
    data["natal_params"]["zone"] = "+09:00"
    extraction = _extract("returntimeline", data)
    assert extraction.events == [] and len(extraction.skipped) == 6
    assert all("对不上" in item for item in extraction.skipped)
    zeri = copy.deepcopy(CASES["qimenzeri_ny"])
    zeri["input_normalized"]["zone"] = "+08:00"
    assert extract_calendar("qimenzeri", zeri["data"], input_normalized=zeri["input_normalized"], label="奇门择日",
                            run_id="x").events == []


def test_all_day_periods_end_on_the_next_period_start_and_never_compute_an_end() -> None:
    events = events_of(_ics("firdaria"))
    flat = [sub["date"] for main in CASES["firdaria"]["data"]["firdaria"] for sub in main["subDirect"]]
    for event, start, nxt in zip(events, flat, flat[1:]):
        assert event["DTSTART;VALUE=DATE"] == start.replace("-", "") and event["DTEND;VALUE=DATE"] == nxt.replace("-", "")
    last = events[-1]
    assert last["DTSTART;VALUE=DATE"] == flat[-1].replace("-", "") and "DTEND;VALUE=DATE" not in last
    assert last["DURATION"] == "P1D" and "止日结果未给" in last["DESCRIPTION"]
    decennials = events_of(_ics("decennials"))
    first = CASES["decennials"]["data"]["timeline"]["list"][0]
    assert decennials[0]["DTEND;VALUE=DATE"] == first["endText"].replace("-", "")  # 结果自己的止日


def test_day_granular_hits_are_all_day_events_with_the_results_day_count() -> None:
    (event,) = events_of(_ics("huanglizeri"))
    assert event["DTSTART;VALUE=DATE"] == "20280403" and event["DURATION"] == "P1D" and "DTEND;VALUE=DATE" not in event
    data = copy.deepcopy(CASES["huanglizeri"]["data"])
    data["intervals"] = [{"start": "2028-04-03", "end": "2028-04-05", "days": 3}, {"start": "2028-04-07", "end": "2028-04-09"}]
    extraction = _extract("huanglizeri", data)
    assert [e.duration_days for e in extraction.events] == [3]  # 多日又没给天数：不自己数天数
    assert "缺天数" in extraction.skipped[0]


@pytest.mark.parametrize("start, why", [
    ("-0500-03-21 10:00", "公元前"), ("0000-01-01 00:00", "公元前"), ("10000-01-01 00:00", "超出"), ("2028-02-30 10:00", "不是合法日期"),
])
def test_bce_and_out_of_range_dates_are_skipped_never_written(start: str, why: str) -> None:
    data = copy.deepcopy(CASES["qimenzeri"]["data"])
    data["intervals"] = [{"start": start, "end": start}, data["intervals"][0]]
    extraction = _extract("qimenzeri", data)
    assert len(extraction.events) == 1 and why in extraction.skipped[0]
    assert validate_ics(render_ics(extraction.events, run_id="x", dtstamp=STAMP, calendar_name="x").encode()) == []


def test_a_year_one_moment_that_leaves_the_range_in_utc_is_skipped() -> None:
    data = {"intervals": [{"start": "0001-01-01 03:00", "end": "0001-01-01 05:00"}]}
    extraction = extract_calendar("qimenzeri", data, input_normalized={"zone": "+08:00"}, label="奇门择日", run_id="x")
    assert extraction.events == [] and "0001–9999" in extraction.skipped[0]


def test_folding_never_splits_a_multibyte_character_or_an_escape_and_keeps_lines_within_75_octets() -> None:
    summary = "择日" * 40 + "🀄" * 7 + "；分号;逗号,反斜杠\\换行\n" * 3
    produced = render_ics([CalendarEvent(summary, "说明" * 200, datetime(2028, 4, 1, tzinfo=timezone.utc))], run_id="r",
                          dtstamp=STAMP, calendar_name="名" * 60).encode("utf-8")
    assert validate_ics(produced) == []
    physical = produced.split(b"\r\n")[:-1]
    assert max(len(line) for line in physical) <= 75 and any(len(line) >= 73 for line in physical)
    for line in physical:
        line.decode("utf-8")  # 单独可解码 = 没有拆开多字节字符
        assert not line.endswith(b"\\") or line.endswith(b"\\\\")  # 转义对不跨行
    (event,) = events_of(produced)
    assert event["SUMMARY"] == summary and event["DESCRIPTION"] == "说明" * 200
    # 第 75 个八位组正好落在转义对「\n」中间：转义对整体挪到下一行，第一行不以单个反斜杠结尾
    pair = "DESCRIPTION:" + "a" * 62 + "\\n" + "b" * 20
    assert len(pair.split("\\n")[0].encode()) == 74
    first, rest = fold_line(pair).split("\r\n", 1)
    assert not first.endswith("\\") and rest.startswith(" \\n") and fold_line(pair).replace("\r\n ", "") == pair
    assert fold_line("短") == "短"
    long = "SUMMARY:" + "a" * 200
    assert fold_line(long).replace("\r\n ", "") == long and fold_line(long).split("\r\n")[1].startswith(" ")


def test_text_values_are_escaped_and_round_trip() -> None:
    raw = "a;b,c\\d\ne\r\nf\x07g"
    escaped = escape_text(raw)
    assert escaped == "a\\;b\\,c\\\\d\\ne\\nfg"
    assert unescape(escaped) == "a;b,c\\d\ne\nfg"
    produced = render_ics([CalendarEvent(raw, raw, datetime(2028, 4, 1, tzinfo=timezone.utc))], run_id="r", dtstamp=STAMP,
                          calendar_name="a;b").encode("utf-8")
    assert validate_ics(produced) == [] and "X-WR-CALNAME:a\\;b" in content_lines(produced)


def test_the_validator_catches_what_it_claims_to() -> None:
    """负向对照：校验器自己会红（不然所有「validate_ics == []」都可能是因为错误的原因通过）。"""
    good = _ics("huanglizeri")
    assert validate_ics(good) == []
    assert validate_ics(good.replace(b"\r\n", b"\n"))
    assert validate_ics(good.replace(b"VERSION:2.0\r\n", b""))
    assert validate_ics(good.replace(b"DTSTAMP:20261108T040000Z", b"DTSTAMP:20261108T040000"))
    assert validate_ics(good.replace(b"\\;", b";"))
    assert validate_ics(good.replace(b"DTSTART;VALUE=DATE:20280403", b"DTSTART;VALUE=DATE:20280431"))
    unfolded = good.replace(b"\r\n ", b"")
    assert any("超过 75" in p for p in validate_ics(unfolded))
    raw = ("SUMMARY:" + "中" * 30).encode("utf-8")  # 8 + 3×22 = 74：第 75 个八位组在「中」的中间
    broken = b"BEGIN:VCALENDAR\r\n" + raw[:75] + b"\r\n " + raw[75:] + b"\r\nEND:VCALENDAR\r\n"
    assert any("UTF-8" in p for p in validate_ics(broken))


def test_tools_without_dates_in_their_data_are_not_calendar_tools() -> None:
    """审计结论（2026-11-08 实录）：小限只有目标时刻、行星年龄只有年龄段，日期只在正文文字里的也不收。"""
    for tool in ("profection", "planetaryages", "bazi_birth", "chart", "keypoints", "extrareturns"):
        assert tool not in CALENDAR_TOOLS
        assert extract_calendar(tool, {"date": "2031-04-06 09:33:00"}, input_normalized={}, label=tool, run_id="x").events == []
    for tool in ("tianxing", "qimenzeri", "huanglizeri", "bazizeri", "taiyizeri", "ziweizeri", "liurengzeri", "sanshizeri",
                 "qizhengzeri", "indiazeri", "election", "qizhengelection", "returntimeline", "ephemeris", "firdaria", "zr",
                 "decennials", "distributions"):
        assert tool in CALENDAR_TOOLS


def test_no_calendar_content_is_a_registered_input_error_with_recovery() -> None:
    assert classify_code("report.no_calendar_content") == ("input", "exact")
    recovery = recovery_for("report.no_calendar_content", {})["agent_recovery"]
    assert recovery["next_action"] == "read_tool_result_or_pick_calendar_technique" and " / " in recovery["prompt_to_user"]


# ── 服务层：存档 → 日历文件 ─────────────────────────────────────────────────


def _service(tmp_path: Path):
    from fakes import FakeClient, FakeJsClient

    from horosa_skill.config import Settings
    from horosa_skill.memory.store import MemoryStore
    from horosa_skill.service import HorosaSkillService

    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", db_path=tmp_path / "m.db",
                        output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt", data_dir=tmp_path / "data")
    return HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())


def _stored(service, name: str | dict) -> str:
    case = CASES[name] if isinstance(name, str) else name
    run_id = service.store.create_run(entrypoint="tool", query_text=None)
    envelope = {"ok": True, "tool": case["tool"], "input_normalized": case["input_normalized"], "data": case["data"],
                "summary": [], "warnings": []}
    service.store.record_tool_result(run_id=run_id, tool_name=case["tool"], ok=True, input_normalized=case["input_normalized"],
                                     envelope_dict=envelope, summary=[], warnings=[], error=None)
    return run_id


def test_report_render_writes_a_valid_calendar_file_with_a_file_card(tmp_path: Path) -> None:
    service = _service(tmp_path)
    run_id = _stored(service, "qimenzeri_ny")
    result = service.report_render({"run_id": run_id, "format": "ics"})
    path = Path(result["artifact_path"])
    data = path.read_bytes()
    assert path.suffix == ".ics" and validate_ics(data) == [] and result["kind"] == "report_ics"
    assert result["file"]["mime"] == "text/calendar" and result["files"] == [result["file"]]
    assert result["event_count"] == len(CASES["qimenzeri_ny"]["data"]["intervals"]) == len(events_of(data))
    assert events_of(data)[0]["UID"] == f"{run_id}-1@horosa-skill"
    assert result["summary"][0].startswith("已生成 ICS 日历")
    again = service.report_render({"run_id": run_id, "format": "ics", "output_path": "again.ics"})
    assert Path(again["artifact_path"]).read_bytes() == data  # DTSTAMP 取 run 创建时刻：同一条结果重导出逐字节相同


def test_dtstamp_is_the_runs_creation_time_not_the_render_time(tmp_path: Path) -> None:
    """DTSTAMP 取 run 的创建时刻：同一条结果隔多久重导出都逐字节相同（日历软件按 UID + DTSTAMP 判断是不是新版本）。"""
    service = _service(tmp_path)
    run_id = _stored(service, "huanglizeri")
    with service.store._writer() as conn:  # noqa: SLF001 - 把创建时刻挪到过去，与「现在」分开
        conn.execute("UPDATE runs SET created_at = ? WHERE id = ?", ("2026-01-02T03:04:05+00:00", run_id))
        conn.commit()
    data = Path(service.report_render({"run_id": run_id, "format": "ics"})["artifact_path"]).read_bytes()
    assert [e["DTSTAMP"] for e in events_of(data)] == ["20260102T030405Z"]


def test_report_render_ics_in_traditional_chinese(tmp_path: Path) -> None:
    service = _service(tmp_path)
    run_id = _stored(service, "qimenzeri")
    result = service.report_render({"run_id": run_id, "format": "ics", "language": "zh-TW"})
    data = Path(result["artifact_path"]).read_bytes()
    assert validate_ics(data) == []
    first = events_of(data)[0]
    assert first["SUMMARY"].startswith("奇門擇日 命中 1/") and "陽遁九局中元" in first["SUMMARY"]


def test_report_render_refuses_a_calendar_tool_run_with_no_usable_dates(tmp_path: Path) -> None:
    service = _service(tmp_path)
    empty = copy.deepcopy(CASES["qimenzeri"])
    empty["data"]["intervals"] = []  # 择日扫完零命中
    bce = copy.deepcopy(CASES["qimenzeri"])
    bce["data"]["intervals"] = [{"start": "-0500-03-21 10:00", "end": "-0500-03-21 12:00"}]
    for case, skipped in ((empty, []), (bce, 1)):
        with pytest.raises(ToolValidationError) as refused:
            service.report_render({"run_id": _stored(service, case), "format": "ics"})
        assert refused.value.code == "report.no_calendar_content"
        details = refused.value.details
        assert details["tool_name"] == "qimenzeri" and "qimenzeri" in details["calendar_tools"]
        assert details["skipped"] == [] if skipped == [] else "公元前" in details["skipped"][0]
    assert not list((tmp_path / "runs").rglob("*.ics"))  # 什么都没写


def test_ics_and_png_obey_the_output_path_guard(tmp_path: Path) -> None:
    """越界的 output_path：与 PDF 同一道闸（report.output_path_not_allowed），一个文件都不写。"""
    service = _service(tmp_path)
    run_id = _stored(service, "qimenzeri")
    outside = tmp_path / "elsewhere" / "cal.ics"
    with pytest.raises(ToolValidationError) as refused:
        service.report_render({"run_id": run_id, "format": "ics", "output_path": str(outside)})
    assert refused.value.code == "report.output_path_not_allowed" and not outside.parent.exists()


def test_report_from_tool_refuses_ics_before_casting_a_tool_with_no_dates(tmp_path: Path) -> None:
    service = _service(tmp_path)
    calls: list[str] = []
    service.run_tool = lambda *args, **kwargs: calls.append(args[0])  # type: ignore[method-assign]
    with pytest.raises(ToolValidationError) as refused:
        service.report_from_tool({"tool_name": "horosa_predict_profection", "payload": {}, "format": "ics"})
    assert refused.value.code == "report.no_calendar_content" and calls == []  # 没白起一次盘


if __name__ == "__main__":  # 重录金样（见模块说明）
    (FIXTURES / "calendar_ics").mkdir(exist_ok=True)
    for golden_name in GOLDENS:
        (FIXTURES / "calendar_ics" / f"{golden_name}.ics").write_bytes(_ics(golden_name))
        print("wrote", golden_name)
