"""命主档案（horosa_skill/profiles.py · horosa_profile · 载荷键 `profile`）。

每条守卫都做过负向对照（把被测的那一行改回去，确认这里变红）；对照清单与红的条数见提交说明。断言只钉被测的东西：
引擎收到的载荷用录制桩比，真引擎（node）那条只比同一引擎两次输出，不跟平台布局挂钩。
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import textwrap
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fakes import FakeClient, FakeJsClient

from horosa_skill import profiles as P
from horosa_skill.config import Settings
from horosa_skill.errors import ToolValidationError, recovery_for
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

MOM = {
    "date": "1962-3-5", "time": "6:00", "zone": "Asia/Shanghai", "lat": "26.9", "lon": "112.6", "gender": "女",
    "aliases": ["我妈", "Mom"], "place": "湖南衡阳", "notes": "外婆家在衡山脚下",
}
DAD = {"date": "1960-11-20", "time": "22:15", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gender": 1, "aliases": ["老爸"]}
CONFIRM = {"agent_confirmed_settings": True, "clarification_notes": "profile test"}
SRC = Path(__file__).resolve().parents[1] / "src"


class RecordingJs(FakeJsClient):
    def __init__(self) -> None:
        super().__init__()
        self.payloads: list[tuple[str, dict]] = []

    def run(self, tool_name: str, payload: dict) -> dict:  # type: ignore[override]
        self.payloads.append((tool_name, json.loads(json.dumps(payload))))
        return super().run(tool_name, payload)


class RecordingClient(FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, dict]] = []

    def call(self, endpoint: str, payload: dict) -> dict:  # type: ignore[override]
        self.calls.append((endpoint, json.loads(json.dumps(payload))))
        return super().call(endpoint, payload)


def _settings(tmp_path: Path, **extra) -> Settings:
    data = tmp_path / "data"
    return Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=data,
                    db_path=data / "memory.db", output_dir=data / "runs", runtime_root=tmp_path / "rt", **extra)


def _service(tmp_path: Path, *, js=None, client=None, layer=None) -> HorosaSkillService:
    settings = _settings(tmp_path)
    return HorosaSkillService(settings, client=client or FakeClient(), store=MemoryStore(settings),
                              js_client=js or FakeJsClient(), decision_layer=layer)


def _store(tmp_path: Path) -> P.ProfileStore:
    return P.ProfileStore(_settings(tmp_path))


def _save(store: P.ProfileStore, name: str, data: dict) -> dict:
    return P.run_action(store, {"action": "save", "name": name, "data": data})


def _code(fn) -> ToolValidationError:
    with pytest.raises(ToolValidationError) as info:
        fn()
    return info.value


def _engine_payload(js: RecordingJs, tool: str) -> dict:
    return next(payload for name, payload in reversed(js.payloads) if name == tool)


# ── 增删查改 ────────────────────────────────────────────────────────────────


def test_save_get_list_delete_round_trip(tmp_path: Path) -> None:
    store = _store(tmp_path)
    saved = _save(store, "妈妈", MOM)
    assert saved["created"] is True and store.path == tmp_path / "data" / "profiles" / "profiles.db"
    # 存的是技法归一化之后的形状（get 的 payload 原样就能并进技法载荷）；IANA 时区存名字，起盘时再按出生日期折算。
    assert saved["profile"]["payload"] == {
        "date": "1962-03-05", "time": "06:00:00", "zone": "Asia/Shanghai", "lat": "26n54", "gpsLat": 26.9,
        "lon": "112e36", "gpsLon": 112.6, "gender": 0,
    }
    got = P.run_action(store, {"action": "get", "name": "妈妈"})["profile"]
    assert got["aliases"] == ["我妈", "Mom"] and got["place"] == "湖南衡阳" and got["notes"] == MOM["notes"]
    listed = P.run_action(store, {"action": "list"})
    assert listed["profiles"] == [{"name": "妈妈", "aliases": ["我妈", "Mom"]}], "list 只给名字与别名"
    assert P.run_action(store, {"action": "list", "detail": True})["profiles"][0]["payload"] == saved["profile"]["payload"]
    deleted = P.run_action(store, {"action": "delete", "name": "我妈"})
    assert deleted["deleted"]["name"] == "妈妈" and deleted["deleted"]["notes"] == MOM["notes"], "整条交回，可原样存回"
    assert _code(lambda: P.run_action(store, {"action": "get", "name": "妈妈"})).code == "profile.not_found"


def test_save_merges_by_name_and_null_removes_a_field(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _save(store, "妈妈", MOM)
    updated = _save(store, "妈妈", {"time": "06:30"})
    assert updated["created"] is False and updated["previous"]["payload"]["time"] == "06:00:00"
    assert updated["profile"]["payload"]["time"] == "06:30:00" and updated["profile"]["payload"]["gender"] == 0
    assert updated["profile"]["aliases"] == ["我妈", "Mom"] and updated["profile"]["notes"] == MOM["notes"]
    assert "gender" not in _save(store, "妈妈", {"gender": None})["profile"]["payload"]
    # 改了 lat 就不留旧的十进制坐标（gpsLat 跟着新 lat 重算），不会一半新一半旧。
    moved = _save(store, "妈妈", {"lat": "28.2", "lon": "112.9"})["profile"]["payload"]
    assert (moved["lat"], moved["gpsLat"], moved["lon"], moved["gpsLon"]) == ("28n12", 28.2, "112e54", 112.9)
    assert len(store.all()) == 1


def test_reading_never_creates_the_database_and_runs_without_a_profile_never_touch_it(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert store.all() == [] and P.run_action(store, {"action": "list"})["count"] == 0
    service = _service(tmp_path)
    assert service.run_tool("ziwei_birth", {**MOM_FIELDS(), **CONFIRM}, save_result=False).ok
    assert not (tmp_path / "data" / "profiles").exists()


def MOM_FIELDS() -> dict:
    return {key: MOM[key] for key in ("date", "time", "zone", "lat", "lon", "gender")}


# ── 存档时的校验（与技法同一套归一化、同一批错误码）───────────────────────────


@pytest.mark.parametrize(
    ("patch", "field"),
    [
        ({"date": "1962-02-30"}, "date"),
        ({"date": "0000-01-01"}, "date"),  # 没有公元 0 年
        ({"date": "1582-10-10"}, "date"),  # 改历缺口
        ({"date": "1962年13月5日"}, "date"),  # v0.50.0：1962年3月5日 读得懂（同技法），不存在的月份才拒
        ({"time": "25:00"}, "time"),
        ({"lat": "95n00"}, "lat"),
        ({"lat": "121e28"}, "lat"),  # 半球字母与轴不符
        ({"lat": "上海"}, "lat"),
        ({"gender": "x"}, "gender"),
        ({"ad": 0}, "ad"),
        ({"timeAlg": 3}, "timeAlg"),
    ],
)
def test_bad_birth_fields_are_refused_at_save_time(tmp_path: Path, patch: dict, field: str) -> None:
    store = _store(tmp_path)
    error = _code(lambda: _save(store, "x", {**MOM_FIELDS(), **patch}))
    assert error.code == "tool.invalid_payload"
    assert [e["loc"] for e in error.details["errors"]] == [["data", field]]
    assert error.details["agent_recovery"]["must_ask_user"] is True, "出生数据是用户的：错了问用户，不是 AI 自己改"
    assert store.all() == [], "校验失败什么都不存"


@pytest.mark.parametrize("zone", ["Mars/Base", "+16:00", "CST", "480"])  # v0.50.0：东八区读得懂；一词多义的缩写、分钟数拒
def test_unrecognized_zones_use_the_existing_zone_error(tmp_path: Path, zone: str) -> None:
    error = _code(lambda: _save(_store(tmp_path), "x", {**MOM_FIELDS(), "zone": zone}))
    assert error.code == "tool.invalid_zone" and error.details["zone"] == zone


def test_lat_without_lon_missing_date_and_bad_requests_refuse(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert _code(lambda: _save(store, "x", {"date": "1962-03-05", "lat": "26n54"})).details["errors"][0]["loc"] == ["data", "lon"]
    assert _code(lambda: _save(store, "x", {"time": "06:00"})).code == "tool.invalid_payload"
    for bad in ({"action": "save", "name": "", "data": MOM_FIELDS()}, {"action": "save", "name": "妈\x07妈", "data": MOM_FIELDS()},
                {"action": "save", "name": "x", "data": "1962-03-05"}, {"action": "rename", "name": "x"},
                {"action": "get"}):
        assert _code(lambda bad=bad: P.run_action(store, bad)).code == "profile.invalid_payload", bad
    # 公元前只存一种写法（v0.50.0 _fold_era）：ad=-1 + 不带负号的日期存成带负号的日期 + ad=-1，与起盘入口同形。
    assert P.run_action(store, {"action": "save", "name": "公元前", "data": {"date": "0500-03-21", "ad": -1}})["profile"]["payload"] == {
        "date": "-0500-03-21", "ad": -1}
    assert _save(store, "妈\n妈", MOM_FIELDS())["profile"]["name"] == "妈 妈", "空白（含换行）折成一个空格，不存换行"


def test_technique_settings_are_not_stored_and_are_reported(tmp_path: Path) -> None:
    saved = _save(_store(tmp_path), "妈妈", {**MOM_FIELDS(), "hsys": 3, "guirengType": 2, "agent_confirmed_settings": True})
    assert saved["ignored_fields"] == ["agent_confirmed_settings", "guirengType", "hsys"]
    assert not {"hsys", "guirengType", "agent_confirmed_settings"} & set(saved["profile"]["payload"])
    assert any("澄清闸" in warning for warning in saved["warnings"])


# ── 并进载荷：显式字段逐键优先，模型缺省值不冒充显式 ────────────────────────


def test_explicit_fields_win_field_by_field_and_the_card_records_the_source(tmp_path: Path) -> None:
    js = RecordingJs()
    service = _service(tmp_path, js=js)
    _save(service.profiles, "妈妈", MOM)
    result = service.run_tool("bazi_birth", {"profile": "我妈", "time": "07:45", **CONFIRM}, save_result=False)
    assert result.ok, result.error
    assert (result.input_normalized["date"], result.input_normalized["time"], result.input_normalized["gender"]) == ("1962-03-05", "07:45:00", 0)
    assert "profile" not in result.input_normalized and "profile" not in _engine_payload(js, "bazi_local")
    card = result.data["technique_card"]["profiles"]
    assert card == [{"slot": "subject", "name": "妈妈", "filled": ["date", "zone", "lat", "gpsLat", "lon", "gpsLon", "gender"],
                     "overridden": ["time"]}]
    assert any("命主档案「妈妈」" in line for line in result.summary)
    from horosa_skill.reports.technique_card import render_technique_card_markdown

    assert "- 出生信息：取自命主档案「妈妈」" in render_technique_card_markdown(result.data["technique_card"])
    dumped = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
    assert MOM["notes"] not in dumped and MOM["place"] not in dumped, "备注与地点标签不进技法结果"


def test_lat_and_gps_lat_are_one_group_and_stored_decimals_survive(tmp_path: Path) -> None:
    js = RecordingJs()
    service = _service(tmp_path, js=js)
    _save(service.profiles, "上海人", {"date": "1990-06-15", "time": "10:30", "zone": "+08:00", "lat": "31.2167", "lon": "121.4667", "gender": 1})
    plain = service.run_tool("bazi_birth", {"profile": "上海人", **CONFIRM}, save_result=False)
    # 十进制坐标原样（31.2167），不是从 31n13 重算的 31.216667——与显式给 31.2167 的起盘逐值相同。
    assert (plain.input_normalized["gpsLat"], plain.input_normalized["gpsLon"]) == (31.2167, 121.4667)
    moved = service.run_tool("bazi_birth", {"profile": "上海人", "gpsLat": 39.9, **CONFIRM}, save_result=False)
    assert (moved.input_normalized["lat"], moved.input_normalized["gpsLat"]) == ("39n54", 39.9), "显式 gpsLat 压过档案的 lat 整组"
    assert moved.input_normalized["lon"] == "121e28" and moved.data["technique_card"]["profiles"][0]["overridden"] == ["gpsLat"]


def test_profile_run_reaches_the_engine_exactly_like_the_explicit_run(tmp_path: Path) -> None:
    js = RecordingJs()
    service = _service(tmp_path, js=js)
    _save(service.profiles, "妈妈", MOM)
    payload = P.run_action(service.profiles, {"action": "get", "name": "妈妈"})["profile"]["payload"]
    via_profile = service.run_tool("ziwei_birth", {"profile": "妈妈", **CONFIRM}, save_result=False)
    sent_profile = _engine_payload(js, "ziwei_birth")
    explicit = service.run_tool("ziwei_birth", {**payload, **CONFIRM}, save_result=False)
    sent_explicit = _engine_payload(js, "ziwei_birth")
    assert via_profile.input_normalized == explicit.input_normalized and sent_profile == sent_explicit
    service.run_tool("ziwei_birth", {**payload, "time": "07:00", **CONFIRM}, save_result=False)
    assert _engine_payload(js, "ziwei_birth") != sent_profile, "对照：换一个时刻引擎载荷就变（上面的相等不是空比较）"


@pytest.mark.skipif(shutil.which("node") is None, reason="[host] node not installed")
def test_real_engine_profile_run_equals_the_explicit_run(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    _save(service.profiles, "妈妈", MOM)
    payload = P.run_action(service.profiles, {"action": "get", "name": "妈妈"})["profile"]["payload"]
    text = lambda envelope: envelope.data["export_snapshot"]["export_text"]  # noqa: E731
    via_profile = service.run_tool("bazi_birth", {"profile": "妈妈", **CONFIRM}, save_result=False)
    explicit = service.run_tool("bazi_birth", {**payload, **CONFIRM}, save_result=False)
    assert via_profile.ok and explicit.ok and text(via_profile) == text(explicit)
    other = service.run_tool("bazi_birth", {**payload, "time": "14:00", **CONFIRM}, save_result=False)
    assert text(other) != text(via_profile)


def _mcp(tmp_path: Path, *, compact: bool = False, js=None, client=None, script: str | None = None):
    from horosa_skill.surfaces.mcp_server import create_mcp_server

    settings = _settings(tmp_path, mcp_compact=compact, **({"output_script": script} if script else {}))
    service = HorosaSkillService(settings, client=client or FakeClient(), store=MemoryStore(settings), js_client=js or FakeJsClient())
    return create_mcp_server(service, settings), service


async def _calls(mcp, *calls):
    from mcp.client import Client

    out = []
    async with Client(mcp) as client:
        for name, args in calls:
            result = await client.call_tool(name, args)
            out.append(json.loads(result.content[0].text))
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
    return out, tools


@pytest.fixture
def _no_elicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOROSA_CLARIFY", raising=False)
    monkeypatch.setenv("HOROSA_MCP_ELICIT", "0")


def test_mcp_model_defaults_do_not_mask_the_profile(tmp_path: Path, _no_elicit) -> None:
    """紫微模型缺省 gender=true（男）。MCP 层若先按模型校验再交给 run_tool，缺省值就成了「显式」，女命被静默排成男命。"""
    mcp, service = _mcp(tmp_path)
    _save(service.profiles, "妈妈", MOM)
    (ziwei, via_request, bc), _ = asyncio.run(_calls(
        mcp,
        ("horosa_cn_ziwei_birth", {"profile": "妈妈", **CONFIRM}),
        ("horosa_cn_ziwei_birth", {"request": {"profile": "妈妈"}, **CONFIRM}),
        ("horosa_cn_bazi_birth", {"profile": "公元前", **CONFIRM}),
    ))
    assert ziwei["ok"] and ziwei["input_normalized"]["gender"] is False
    assert via_request["ok"] and via_request["input_normalized"]["gender"] is False
    assert bc["code"] == "profile.not_found" and bc["details"]["known_profiles"] == ["妈妈"]
    assert bc["details"]["agent_recovery"]["prompt_to_user"], "MCP 错误路径补上了双语恢复说明"


# ── 名字与别名 ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize("ref", ["妈妈", "我妈", "mom", "ＭＯＭ", " Mom ", "媽媽"])
def test_names_and_aliases_resolve_case_width_and_script_insensitively(tmp_path: Path, ref: str) -> None:
    store = _store(tmp_path)
    _save(store, "妈妈", MOM)
    _save(store, "爸爸", DAD)
    assert store.resolve(ref).name == "妈妈"


def test_unknown_and_ambiguous_profiles_refuse_and_list_the_known_names(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _save(store, "妈妈", MOM)
    _save(store, "爸爸", DAD)
    shared = _save(store, "继父", {**DAD, "aliases": ["老爸"]})
    assert any("歧义" in warning for warning in shared["warnings"]), "存的时候就提醒别名撞了"
    unknown = _code(lambda: store.resolve("老王"))
    assert unknown.code == "profile.not_found" and unknown.details["known_profiles"] == ["妈妈", "爸爸", "继父"]
    assert unknown.details["agent_recovery"]["known_profiles"] == ["妈妈", "爸爸", "继父"]
    ambiguous = _code(lambda: store.resolve("老爸"))
    assert ambiguous.code == "profile.ambiguous" and ambiguous.details["candidates"] == ["爸爸", "继父"]
    assert ambiguous.details["known_profiles"] == ["妈妈", "爸爸", "继父"]
    for code in ("profile.not_found", "profile.ambiguous"):
        assert recovery_for(code, {})["agent_recovery"]["kind"] == "input"
    # 名字精确命中优先于别名：别人的别名不会把正主挤成歧义。
    _save(store, "老张", DAD)
    clash = _save(store, "张叔", {**DAD, "aliases": ["老张"]})
    assert store.resolve("老张").name == "老张" and any("同名" in warning for warning in clash["warnings"])


# ── 澄清闸：档案只补它存了的，确认照旧要用户给（铁律 2）───────────────────────


def _asked(result: dict) -> list[str]:
    return [item["field"] for item in result["details"]["ask_if_missing"]]


def test_gate_still_blocks_and_asks_only_what_the_profile_lacks(tmp_path: Path, _no_elicit) -> None:
    mcp, service = _mcp(tmp_path)
    _save(service.profiles, "妈妈", MOM)
    _save(service.profiles, "无性别", {key: value for key, value in MOM_FIELDS().items() if key != "gender"})
    (bare, chart, ziwei, ziwei_no_gender, unknown), _ = asyncio.run(_calls(
        mcp,
        ("horosa_astro_chart", {}),
        ("horosa_astro_chart", {"profile": "妈妈"}),
        ("horosa_cn_ziwei_birth", {"profile": "妈妈"}),
        ("horosa_cn_ziwei_birth", {"profile": "无性别"}),
        ("horosa_astro_chart", {"profile": "老王"}),
    ))
    for result in (chart, ziwei, ziwei_no_gender):
        assert result["code"] == "agent_guidance.required", "有档案也得用户确认口径"
    assert "date/time/place" in _asked(bare) and "date/time/place" not in _asked(chart)
    assert "hsys" in _asked(chart), "档案不存口径：宫制照问"
    assert "gender" not in _asked(ziwei) and "gender" in _asked(ziwei_no_gender), "没存性别就照旧问性别"
    assert unknown["code"] == "profile.not_found", "认不出的档案名在闸门之前就拒"


def test_cli_gate_uses_the_same_profile_view(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    from horosa_skill.surfaces import cli

    monkeypatch.delenv("HOROSA_CLARIFY", raising=False)
    monkeypatch.setenv("HOROSA_SKILL_DATA_DIR", str(tmp_path / "data"))
    runner = CliRunner()
    data = tmp_path / "mom.json"
    data.write_text(json.dumps(MOM, ensure_ascii=False), encoding="utf-8")
    saved = runner.invoke(cli.app, ["profile", "save", "妈妈", "--input", str(data)])
    assert saved.exit_code == 0 and json.loads(saved.stdout)["profile"]["payload"]["gender"] == 0
    assert [p["name"] for p in json.loads(runner.invoke(cli.app, ["profile", "list"]).stdout)["profiles"]] == ["妈妈"]
    assert json.loads(runner.invoke(cli.app, ["profile", "get", "我妈"]).stdout)["profile"]["name"] == "妈妈"
    payload = tmp_path / "p.json"
    payload.write_text(json.dumps({"profile": "妈妈"}), encoding="utf-8")
    gated = runner.invoke(cli.app, ["tool", "run", "chart", "--input", str(payload)])
    refusal = json.loads(gated.stderr)
    assert gated.exit_code == 2 and refusal["code"] == "agent_guidance.required"
    assert "date/time/place" not in [item["field"] for item in refusal["details"]["ask_if_missing"]]
    missing = runner.invoke(cli.app, ["profile", "get", "老王"])
    assert missing.exit_code == 2 and json.loads(missing.stderr)["details"]["known_profiles"] == ["妈妈"]
    assert runner.invoke(cli.app, ["profile", "delete", "妈妈"]).exit_code == 0


# ── 两个人的技法与 dispatch / hecan ──────────────────────────────────────────


def test_relationship_chart_takes_one_profile_per_person_slot(tmp_path: Path) -> None:
    client = RecordingClient()
    service = _service(tmp_path, client=client)
    _save(service.profiles, "妈妈", MOM)
    _save(service.profiles, "爸爸", DAD)
    result = service.run_tool("relative", {"inner": {"profile": "妈妈"}, "outer": {"profile": "老爸", "time": "23:00"}, **CONFIRM},
                              save_result=False)
    assert result.ok, result.error
    sent = next(payload for endpoint, payload in client.calls if endpoint == "/modern/relative")
    assert (sent["inner"]["date"], sent["outer"]["date"], sent["outer"]["time"]) == ("1962-03-05", "1960-11-20", "23:00:00")
    assert "gender" not in sent["inner"] and "profile" not in sent["inner"], "合盘双方只拿 RelativePartyInput 声明的键"
    slots = {use["slot"]: use for use in result.data["technique_card"]["profiles"]}
    assert slots["inner"]["name"] == "妈妈" and slots["outer"]["overridden"] == ["time"]
    misplaced = _code(lambda: service.run_tool("relative", {"profile": "妈妈", **CONFIRM}))
    assert misplaced.code == "profile.not_applicable" and misplaced.details["person_slots"] == ["inner", "outer"]


def test_day_picker_persons_take_profiles_with_only_the_keys_the_engine_reads(tmp_path: Path) -> None:
    js = RecordingJs()
    service = _service(tmp_path, js=js)
    _save(service.profiles, "妈妈", MOM)
    result = service.run_tool("calendar_month", {"date": "2028-04-06", "zone": "+08:00", "rizi": {"event": "嫁娶", "persons": [
        # role 走日子馆角色词表（self / spouse / family；v0.50.0 深审余项：「女方」不是上游角色，快照曾印 undefined / 原文）。
        {"profile": "妈妈", "role": "配偶"}, {"name": "乙", "date": "1990-01-01", "time": "08:00", "zone": "+08:00", "gender": 1, "role": "本人"}]}, **CONFIRM},
        save_result=False)
    assert result.ok, result.error
    person = result.input_normalized["rizi"]["persons"][0]
    # 嵌套的人一样过归一化（IANA 时区按出生日期折成偏移）；经纬度不进（日子馆不读）。
    assert person == {"role": "spouse", "date": "1962-03-05", "time": "06:00:00", "zone": "+08:00", "gender": 0}
    assert result.data["technique_card"]["profiles"][0]["slot"] == "rizi.persons[0]"


def test_dispatch_takes_birth_profile_flat_profile_and_subject_profile(tmp_path: Path) -> None:
    js = RecordingJs()
    service = _service(tmp_path, js=js)
    _save(service.profiles, "妈妈", MOM)
    for body in ({"birth": {"profile": "妈妈"}}, {"profile": "妈妈"}, {"subject": {"profile": "我妈"}}):
        result = service.dispatch({"query": "看看八字", **body, "save_result": False, **CONFIRM})
        assert result.ok and result.selected_tools == ["bazi_birth"], body
        envelope = result.results["bazi_birth"]
        assert (envelope.input_normalized["date"], envelope.input_normalized["gender"]) == ("1962-03-05", 0), body
        assert envelope.data["technique_card"]["profiles"][0]["filled"][:2] == ["date", "time"], body
        assert result.normalized_inputs["bazi_birth"]["profile"] == "妈妈", body
    flat = service.dispatch({"query": "看看八字", "profile": "妈妈", "time": "09:00", "save_result": False, **CONFIRM})
    assert flat.results["bazi_birth"].input_normalized["time"] == "09:00:00", "平铺写法的显式字段照样优先"
    pair = service.dispatch({"query": "合盘看看", "subject": {"inner": {"profile": "妈妈"}, "outer": {"profile": "妈妈", "time": "20:00"}},
                             "save_result": False, **CONFIRM})
    assert pair.selected_tools == ["relative"] and pair.results["relative"].input_normalized["outer"]["time"] == "20:00:00"
    assert _code(lambda: service.dispatch({"query": "看看八字", "birth": {"profile": "老王"}, **CONFIRM})).code == "profile.not_found"


def test_hecan_hands_profiles_down_so_every_technique_records_its_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service(tmp_path)
    _save(service.profiles, "妈妈", MOM)
    envelopes = []
    original = service.dispatch
    monkeypatch.setattr(service, "dispatch", lambda payload, **kw: envelopes.append(original(payload, **kw)) or envelopes[-1])
    # 天文地占是起课类：时刻取自 context（起卦此刻），不是命主的出生时刻（v0.50：出生数据不顶替起课时刻）。
    moment = {"date": "2026-11-12", "time": "10:00:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"}
    template = service.hecan({"query": "合参看看", "subject": {"profile": "妈妈"}, "tools": ["bazi_birth", "ziwei_birth", "geomancy"],
                              "context": moment, "save_result": False, **CONFIRM})
    assert template["ok"] and template["selected_tools"] == ["bazi_birth", "ziwei_birth", "geomancy"]
    results = envelopes[0].results
    for tool in ("bazi_birth", "ziwei_birth"):
        uses = results[tool].data["technique_card"]["profiles"]
        assert uses[0]["name"] == "妈妈" and "date" in uses[0]["filled"] and uses[0]["overridden"] == [], tool
    assert results["ziwei_birth"].input_normalized["gender"] is False
    geomancy = results["geomancy"].input_normalized
    assert geomancy["profile"] == "european_classical", "地占的 profile 是传本流派，不是档案名"
    assert geomancy["date"] == "2026-11-12", "地占按起卦此刻（context），不按命主出生时刻"


def test_a_tool_that_owns_the_profile_key_keeps_its_meaning(tmp_path: Path) -> None:
    """天文地占的 `profile` 是传本流派：不当档案名查（查了就是 profile.not_found），也不被档案字段改写。"""
    from horosa_skill.testing_payloads import build_sample_payloads

    service = _service(tmp_path)
    _save(service.profiles, "arabic_raml", MOM)  # 同名档案也不该被拿来用
    sample = {**build_sample_payloads()["geomancy"], **CONFIRM}
    result = service.run_tool("geomancy", {**sample, "profile": "arabic_raml"}, save_result=False)
    assert result.ok and result.input_normalized["profile"] == "arabic_raml"
    assert result.input_normalized["date"] == sample["date"] and "profiles" not in result.data["technique_card"]


def test_hecan_restores_profile_refs_before_dispatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service(tmp_path)
    _save(service.profiles, "妈妈", MOM)
    seen: list[dict] = []
    original = service.dispatch

    def spy(payload, **kwargs):
        seen.append(payload)
        return original(payload, **kwargs)

    monkeypatch.setattr(service, "dispatch", spy)
    service.hecan({"query": "合参", "birth": {"profile": "妈妈", "time": "08:00"}, "tools": ["bazi_birth"], "save_result": False, **CONFIRM})
    assert seen[0]["birth"]["profile"] == "妈妈" and seen[0]["birth"]["time"] == "08:00" and "date" not in seen[0]["birth"]


# ── 决策层（唯一出本机的路径）永远看不到档案原值 ─────────────────────────────


def test_meta_state_redacts_profile_names_aliases_and_places(tmp_path: Path) -> None:
    from horosa_skill.decisions.redact import build_meta_state

    store = _store(tmp_path)
    _save(store, "妈妈", MOM)
    terms = store.private_terms()
    assert set(terms) == {"妈妈", "我妈", "Mom", "湖南衡阳"}
    query = "给我妈（mom）看看紫微，她 1962年3月5日 6点 生在湖南衡阳，<妈妈> 也行"
    state, redaction = build_meta_state(query, private_terms=terms)
    text = state["user_request"]
    for leaked in ("妈妈", "我妈", "mom", "湖南衡阳", "1962", "6点"):
        assert leaked.lower() not in text.lower(), leaked
    assert redaction.counts["profile"] == 4 and "<档案>" in text
    assert build_meta_state(text, private_terms=terms)[0]["user_request"] == text, "幂等"


def test_dispatch_decision_layer_never_receives_profile_data(tmp_path: Path) -> None:
    from horosa_skill.decisions.fake import FakeJev, choice_answer
    from horosa_skill.decisions.layer import DecisionLayer
    from horosa_skill.decisions.policy import Policy

    policy = Policy(mode="shadow", scope="meta", surfaces=frozenset({"dispatch", "extract"}), model="jev-1.13.0",
                    base_url="https://api.typesafe.ai", timeout_s=3.0, ledger=False, key_present=True, requested_mode="shadow")
    fake = FakeJev({"subject_gender": choice_answer("female", confidence=0.97)})
    service = _service(tmp_path, layer=DecisionLayer(policy, fake))
    _save(service.profiles, "王秀英", {**MOM, "aliases": ["我妈"]})
    _save(service.profiles, "无性别", {key: value for key, value in MOM_FIELDS().items() if key != "gender"})
    # 两句原话都带性别词（「老婆」），S2 本来都会问；存了性别的那位不该问。
    service.dispatch({"query": "帮我老婆王秀英排紫微，湖南衡阳人", "birth": {"profile": "王秀英"}, "save_result": False, **CONFIRM})
    # v0.50.0：影子模式不填性别、档案也没存 → 紫微拒绝并请问用户（tool.missing_gender）；决策层那一问照常发生。
    with pytest.raises(ToolValidationError) as caught:
        service.dispatch({"query": "帮我老婆排紫微", "birth": {"profile": "无性别"}, "save_result": False, **CONFIRM})
    assert caught.value.code == "tool.missing_gender"
    sent = json.dumps([call["state"] for call in fake.calls], ensure_ascii=False)
    assert fake.calls, "影子模式确实问了（否则下面的断言是空比较）"
    for leaked in ("王秀英", "我妈", "湖南衡阳", "1962", MOM["notes"]):
        assert leaked not in sent, leaked
    surfaces = [call["surface"] for call in fake.calls]
    assert surfaces.count("extract") == 1, "档案存了性别就不为性别出本机；没存的那位照常走 S2"


# ── 工具面登记 ───────────────────────────────────────────────────────────────


def test_profile_tool_is_on_both_surfaces_and_technique_schemas_gain_no_bytes(tmp_path: Path, _no_elicit) -> None:
    from horosa_skill.engine.registry import COMPACT_SURFACE_TOOL_COUNT, FACADE_TOOL_COUNT, TOOL_DEFINITIONS
    from horosa_skill.surfaces.mcp_runner import UNLOCALIZED_TOOLS

    full_mcp, _ = _mcp(tmp_path / "f")
    compact_mcp, _ = _mcp(tmp_path / "c", compact=True)
    _, full = asyncio.run(_calls(full_mcp))
    _, compact = asyncio.run(_calls(compact_mcp))
    assert len(full) == FACADE_TOOL_COUNT + len(TOOL_DEFINITIONS) and len(compact) == COMPACT_SURFACE_TOOL_COUNT
    for tools in (full, compact):
        tool = tools["horosa_profile"]
        assert set(tool.input_schema["properties"]) == {"request", "action", "name", "data", "detail"}
        assert tool.input_schema["properties"]["action"]["enum"] == ["save", "get", "list", "delete", "rename"]  # v0.50.0 rename
        assert tool.annotations.destructive_hint is True and tool.annotations.read_only_hint is False
    assert "horosa_profile" in UNLOCALIZED_TOOLS
    assert "profile" in compact["horosa_tool_run"].input_schema["properties"]
    by_mcp = {definition.mcp_name: name for name, definition in TOOL_DEFINITIONS.items()}
    carrying = sorted(name for name, tool in full.items() if name in by_mcp and "profile" in tool.input_schema["properties"])
    assert carrying == ["horosa_cn_geomancy"], "档案键零字节：只有地占自己的传本流派键在广告层"
    geomancy = list(full["horosa_cn_geomancy"].input_schema["properties"])
    assert geomancy.index("profile") == geomancy.index("includeCatalog") + 1, "地占广告层按自己的声明顺序（逐字节不变）"
    # 「另 N 个高级旋钮」不把档案键算进去：本来没有隐藏旋钮的技法不会凭空多一句。
    chart_request = full["horosa_astro_chart"].input_schema["properties"]["request"]["description"]
    # MCP-11 起没有描述的技法旋钮不广告（计入隐藏数），小六壬因此也有了隐藏旋钮；换一个仍然没有隐藏旋钮的技法来证「档案键不计数」
    assert "另 " in chart_request and full["horosa_shenshu_wangji"].input_schema["properties"]["request"]["description"] == "整包载荷"


def test_mcp_save_stores_the_values_the_user_gave(tmp_path: Path, _no_elicit) -> None:
    """MCP 门面的通用归一化会把嵌套 data 里的 IANA 时区提前折成偏移、给新疆出生塞进 geoZone；档案要存原值，起盘时再折。"""
    mcp, service = _mcp(tmp_path)
    (shanghai, urumqi, bad), _ = asyncio.run(_calls(
        mcp,
        ("horosa_profile", {"action": "save", "name": "妈妈", "data": MOM}),
        ("horosa_profile", {"action": "save", "name": "新疆", "data": {**MOM_FIELDS(), "zone": "Asia/Urumqi"}}),
        ("horosa_profile", {"action": "nope"}),
    ))
    assert shanghai["profile"]["payload"]["zone"] == "Asia/Shanghai" and "ignored_fields" not in shanghai
    assert urumqi["profile"]["payload"]["zone"] == "Asia/Urumqi" and "ignored_fields" not in urumqi
    assert bad["code"] == "profile.invalid_payload"
    envelope = service.run_tool("bazi_birth", {"profile": "新疆", **CONFIRM}, save_result=False)
    assert envelope.input_normalized["zone"] == "+08:00" and envelope.input_normalized["zoneAdvisory"] == "cn-unified", "起盘时照常归并北京时间"


def test_profile_tool_output_is_never_converted_to_traditional(tmp_path: Path, _no_elicit) -> None:
    mcp, _ = _mcp(tmp_path, script="zh-Hant")
    (saved, got), _ = asyncio.run(_calls(
        mcp,
        ("horosa_profile", {"action": "save", "name": "妈妈", "data": {**MOM_FIELDS(), "notes": "说话温和"}}),
        ("horosa_profile", {"action": "get", "name": "妈妈"}),
    ))
    assert saved["ok"] and got["profile"]["name"] == "妈妈" and got["profile"]["notes"] == "说话温和", "名字与备注原样回显"


def test_guidance_server_profile_lists_saved_names_only(tmp_path: Path, _no_elicit) -> None:
    mcp, service = _mcp(tmp_path)
    _save(service.profiles, "妈妈", MOM)
    (guidance,), _ = asyncio.run(_calls(mcp, ("horosa_agent_guidance", {})))
    listed = guidance["server_profile"]["birth_profiles"]
    assert listed["count"] == 1 and listed["names"] == [{"name": "妈妈", "aliases": ["我妈", "Mom"]}]
    assert "1962" not in json.dumps(listed, ensure_ascii=False)


# ── 存储：并发、损坏、不可用、清理 ────────────────────────────────────────────


def test_concurrent_first_saves_on_a_fresh_store_never_deadlock(tmp_path: Path) -> None:
    """新库还在回滚日志模式时并发的第一批写者会互相死锁，SQLite 直接回 `database is locked`、不走 busy_timeout。
    竞态是概率性的（去掉写锁时每轮约 5–9% 撞上）：80 轮、每轮 8 个线程同时起跑，去锁后几乎必红（负向对照见提交说明）。"""
    import threading

    for round_ in range(80):
        settings = Settings(data_dir=tmp_path / f"r{round_}")
        barrier = threading.Barrier(8)
        errors: list[BaseException] = []

        def work(index: int, settings: Settings = settings, barrier: threading.Barrier = barrier, errors: list = errors) -> None:
            barrier.wait()
            try:
                _save(P.ProfileStore(settings), f"人{index}", {"date": "1990-01-01", "aliases": [f"别名{index}"]})
            except BaseException as exc:  # noqa: BLE001 - 收集起来断言
                errors.append(exc)

        threads = [threading.Thread(target=work, args=(i,)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert not errors, (round_, errors[0])
        assert len(P.ProfileStore(settings).all()) == 8


def test_concurrent_merges_on_one_name_stay_consistent(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _save(store, "共享", MOM_FIELDS())

    def work(index: int) -> None:
        _save(P.ProfileStore(store.settings), "共享", {"time": f"{index % 24:02d}:00", "aliases": [f"别名{index}"]})

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(work, range(16)))
    final = store.resolve("共享")
    assert [p.name for p in store.all()] == ["共享"] and final.fields["date"] == "1962-03-05" and final.fields["gender"] == 0
    assert len(final.aliases) == 1, "合并是整条读改写：最后一次的别名列表，不是半截"


def test_concurrent_saves_from_processes_lose_nothing(tmp_path: Path) -> None:
    script = textwrap.dedent(f"""
        import sys
        from pathlib import Path
        from horosa_skill.config import Settings
        from horosa_skill.profiles import ProfileStore, run_action
        store = ProfileStore(Settings(data_dir=Path({str(tmp_path / 'data')!r})))
        for i in range(5):
            run_action(store, {{"action": "save", "name": f"p{{sys.argv[1]}}-{{i}}", "data": {{"date": f"1990-01-0{{i + 1}}"}}}})
    """)
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(SRC), os.environ.get("PYTHONPATH", "")])}
    procs = [subprocess.Popen([sys.executable, "-c", script, str(n)], env=env, stderr=subprocess.PIPE) for n in range(3)]
    for proc in procs:
        _, err = proc.communicate(timeout=120)
        assert proc.returncode == 0, err.decode("utf-8", "replace")[-400:]
    assert len(_store(tmp_path).all()) == 15


def test_a_corrupt_store_is_reported_and_never_rebuilt(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.profiles.path.parent.mkdir(parents=True)
    service.profiles.path.write_bytes(b"this is not a sqlite database" * 40)
    before = service.profiles.path.read_bytes()
    assert _code(lambda: _save(service.profiles, "妈妈", MOM)).code == "profile.store_corrupt"
    assert _code(lambda: service.run_tool("bazi_birth", {"profile": "妈妈", **CONFIRM})).code == "profile.store_corrupt"
    assert service.profiles.path.read_bytes() == before, "用户数据：不隔离、不重建、不改一个字节"
    assert service.run_tool("bazi_birth", {**MOM_FIELDS(), **CONFIRM}, save_result=False).ok, "不带档案的起盘不受影响"
    assert recovery_for("profile.store_corrupt", {})["agent_recovery"]["kind"] == "input"


def test_an_unwritable_store_is_unavailable_not_a_crash(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "profiles").write_text("a file where the folder should be", encoding="utf-8")
    error = _code(lambda: _save(_store(tmp_path), "妈妈", MOM))
    assert error.code == "profile.store_unavailable" and recovery_for(error.code, {})["agent_recovery"]["kind"] == "retry_or_doctor"


def test_purge_data_keeps_profiles_unless_asked(tmp_path: Path) -> None:
    from horosa_skill.surfaces import runtime_helpers

    settings = _settings(tmp_path)
    _save(P.ProfileStore(settings), "妈妈", MOM)
    (tmp_path / "data" / "runs").mkdir(parents=True)
    (tmp_path / "data" / "runs" / "r.json").write_text("{}", encoding="utf-8")
    manager = runtime_helpers._runtime_manager(settings)
    plan = manager.uninstall(purge_data=True, yes=False)
    assert str(tmp_path / "data" / "profiles") not in plan["would_remove"] and str(tmp_path / "data") not in plan["would_remove"]
    assert str(tmp_path / "data" / "runs") in plan["would_remove"] and [Path(p).name for p in plan["kept"]] == ["profiles"]
    manager.uninstall(purge_data=True, yes=True)
    assert P.ProfileStore(settings).resolve("妈妈").fields["date"] == "1962-03-05" and not (tmp_path / "data" / "runs").exists()
    assert str(tmp_path / "data") in manager.uninstall(purge_data=True, purge_profiles=True, yes=False)["would_remove"]
    # 知识库与档案各管各的：只删档案时知识库照留。
    (tmp_path / "data" / "knowledge").mkdir()
    (tmp_path / "data" / "knowledge" / "笔记.md").write_text("x", encoding="utf-8")
    only_profiles = manager.uninstall(purge_data=True, purge_profiles=True, yes=False)
    assert str(tmp_path / "data" / "profiles") in only_profiles["would_remove"]
    assert [Path(p).name for p in only_profiles["kept"]] == ["knowledge"]


# ── 记忆：按档案名查回这个人的历次起盘 ────────────────────────────────────────


def test_runs_with_a_profile_are_findable_by_the_profile_name(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _save(service.profiles, "妈妈", MOM)
    run = service.run_tool("ziwei_birth", {"profile": "我妈", **CONFIRM})
    service.run_tool("ziwei_birth", {**DAD, **CONFIRM})
    found = service.query_memory({"entity": "妈妈"})
    assert [item["run_id"] for item in found["results"]] == [run.memory_ref.run_id]


# ── v0.50.0：繁简同名、改名、导出 / 导入、写坏字段的说法（PR-1）────────────────────────────────


def test_traditional_and_simplified_names_are_one_profile(tmp_path: Path) -> None:
    """「媽媽」存进已有的「妈妈」（显示名不改写），不再新建第二条。负向对照：save 回到按 name_key 定位 → 两条，红（实跑过）。"""
    store = _store(tmp_path)
    _save(store, "妈妈", {"date": "1962-03-05"})
    merged = _save(store, "媽媽", {"time": "06:00"})
    assert merged["created"] is False and merged["profile"]["name"] == "妈妈"
    assert merged["profile"]["payload"]["time"] == "06:00:00" and any("同一份档案" in w for w in merged["warnings"])
    assert store.names() == ["妈妈"]
    assert P.run_action(store, {"action": "get", "name": "媽媽"})["profile"]["name"] == "妈妈"


def test_a_store_that_already_holds_both_scripts_keeps_working(tmp_path: Path) -> None:
    """v0.50.0 前的库可能同时有「妈妈」「媽媽」两条（各自的键）：精确名照旧各取各的、各存各的，不自动合并；
    只有既不精确匹配哪条、折叠后又两条都像的写法才报歧义。"""
    import sqlite3

    store = _store(tmp_path)
    _save(store, "妈妈", {"date": "1962-03-05"})
    with sqlite3.connect(store.path) as db:  # 旧版写法：键 = name_key（不折繁简）
        db.execute("INSERT INTO profiles (key, name, fields_json, aliases_json, place, notes, created_at, updated_at)"
                   " VALUES ('媽媽', '媽媽', '{\"date\": \"1961-01-01\"}', '[]', NULL, NULL, '2026-01-01', '2026-01-01')")
    assert sorted(store.names()) == ["妈妈", "媽媽"]
    assert P.run_action(store, {"action": "get", "name": "媽媽"})["profile"]["payload"]["date"] == "1961-01-01"
    assert P.run_action(store, {"action": "get", "name": "妈妈"})["profile"]["payload"]["date"] == "1962-03-05"
    updated = _save(store, "媽媽", {"time": "07:00"})
    assert updated["profile"]["name"] == "媽媽" and updated["profile"]["payload"]["date"] == "1961-01-01"
    assert len(store.names()) == 2
    assert _code(lambda: _save(store, "妈媽", {"time": "08:00"})).code == "profile.ambiguous"
    assert P.run_action(store, {"action": "delete", "name": "媽媽"})["deleted"]["name"] == "媽媽"
    assert store.names() == ["妈妈"]


def test_rename_keeps_the_birth_data_and_refuses_to_merge_two_people(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _save(store, "妈妈", {**MOM})
    _save(store, "爸爸", {"date": "1960-11-20"})
    renamed = P.run_action(store, {"action": "rename", "name": "我妈", "data": {"new_name": "母亲"}})
    assert renamed["previous_name"] == "妈妈" and renamed["profile"]["name"] == "母亲"
    got = P.run_action(store, {"action": "get", "name": "母亲"})["profile"]
    assert got["payload"]["date"] == "1962-03-05" and got["aliases"] == ["我妈", "Mom"] and got["notes"] == MOM["notes"]
    assert _code(lambda: P.run_action(store, {"action": "get", "name": "妈妈"})).code == "profile.not_found"
    assert _code(lambda: P.run_action(store, {"action": "rename", "name": "母亲", "data": {"new_name": "爸爸"}})).code == "profile.invalid_payload"
    assert _code(lambda: P.run_action(store, {"action": "rename", "name": "母亲"})).code == "profile.invalid_payload"
    script_only = P.run_action(store, {"action": "rename", "name": "母亲", "data": {"new_name": "母親"}})
    assert script_only["profile"]["name"] == "母親" and sorted(store.names()) == ["母親", "爸爸"]


def test_malformed_birth_field_says_malformed_and_names_the_real_tool(tmp_path: Path) -> None:
    """以前：agent_recovery 说「请补充 `data.time`，这是 `horosa_profile_data` 继续执行所需的参数」——字段并不缺、工具也不存在。"""
    store = _store(tmp_path)
    err = _code(lambda: _save(store, "x", {"date": "1990-13-40", "time": "25:00"}))
    recovery = err.details["agent_recovery"]
    text = json.dumps(recovery, ensure_ascii=False)
    assert "horosa_profile_data" not in text and "horosa_profile" in text
    assert "写法不对" in text and "malformed" in text and "请补充" not in text
    assert {item["field"] for item in recovery["ask_if_missing"]} == {"data.date", "data.time"}
    missing = _code(lambda: _save(store, "y", {"time": "08:00"}))
    assert "缺 `date`" in json.dumps(missing.details["agent_recovery"], ensure_ascii=False)


def test_cli_export_then_import_round_trips_every_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    from horosa_skill.surfaces import cli

    source = _service(tmp_path / "a")
    _save(source.profiles, "妈妈", {**MOM})
    _save(source.profiles, "爸爸", {k: v for k, v in DAD.items()})
    runner = CliRunner()
    monkeypatch.setattr(cli, "_service", lambda: source)
    out = tmp_path / "profiles.json"
    exported = runner.invoke(cli.app, ["profile", "export", "--output", str(out)])
    assert exported.exit_code == 0 and json.loads(exported.stdout)["count"] == 2
    document = json.loads(out.read_text(encoding="utf-8"))
    assert document["format"] == "horosa-birth-profiles" and document["version"] == 1

    target = _service(tmp_path / "b")
    _save(target.profiles, "爸爸", {"date": "1999-01-01"})
    monkeypatch.setattr(cli, "_service", lambda: target)
    first = json.loads(runner.invoke(cli.app, ["profile", "import", "--input", str(out)]).stdout)
    assert first["imported"] == ["妈妈"] and first["skipped"][0]["name"] == "爸爸"
    assert P.run_action(target.profiles, {"action": "get", "name": "爸爸"})["profile"]["payload"]["date"] == "1999-01-01"
    again = json.loads(runner.invoke(cli.app, ["profile", "import", "--input", str(out), "--overwrite"]).stdout)
    assert sorted(again["imported"]) == ["妈妈", "爸爸"]
    for name in ("妈妈", "爸爸"):
        a = P.run_action(source.profiles, {"action": "get", "name": name})["profile"]
        b = P.run_action(target.profiles, {"action": "get", "name": name})["profile"]
        assert {k: a[k] for k in ("name", "aliases", "payload")} == {k: b[k] for k in ("name", "aliases", "payload")}
        assert a.get("place") == b.get("place") and a.get("notes") == b.get("notes")


def test_import_writes_nothing_when_any_entry_is_bad(tmp_path: Path) -> None:
    store = _store(tmp_path)
    document = {"format": "horosa-birth-profiles", "version": 1, "profiles": [
        {"name": "好的", "payload": {"date": "1990-01-01"}},
        {"name": "坏的", "payload": {"date": "1990-02-30"}},
    ]}
    err = _code(lambda: P.import_profiles(store, document))
    assert err.code == "profile.invalid_payload" and [p["name"] for p in err.details["problems"]] == ["坏的"]
    assert store.names() == []
    assert _code(lambda: P.import_profiles(store, {"profiles": []})).code == "profile.invalid_payload"
