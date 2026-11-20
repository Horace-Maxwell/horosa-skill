"""入参审计的几条小项：F27 dispatch 不给不收性别的技法下发 gender；F28 省略 time 与「不详」同码同文案。

负向对照（实跑过）：plan_tool 照旧整份下发 birth → 第一条红；_missing_entry 不走 time_unknown → 第二条红。
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.engine.dispatch_plan import PlanInputs, plan_tool
from horosa_skill.errors import ToolValidationError
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

BIRTH = {"date": "1990-05-03", "time": "08:00:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gender": 1}


def test_dispatch_forwards_gender_only_to_techniques_that_take_it() -> None:
    inputs = PlanInputs(birth=dict(BIRTH), birth_fields=dict(BIRTH), context={"date": "2026-11-14", "time": "10:00", "zone": "+08:00",
                                                                          "lat": "31n13", "lon": "121e28"}, query="今年运势")
    assert "gender" not in plan_tool("solarreturn", inputs).payload
    assert plan_tool("bazi_birth", inputs).payload.get("gender") == 1


def test_a_missing_time_reads_like_an_unknown_time() -> None:
    d = Path(tempfile.mkdtemp())
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=d, db_path=d / "m.db",
                        output_dir=d / "runs", runtime_root=d / "rt")
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    codes = []
    # 八字的「不详」现在排三柱（出生时刻未知模式，tests/test_v052_birth_time_unknown.py）；要时辰的技法两种写法仍同码要问
    for payload in ({k: v for k, v in BIRTH.items() if k != "time"}, {**BIRTH, "time": "不详"}):
        with pytest.raises(ToolValidationError) as caught:
            service.run_tool("ziwei_birth", {**payload, "defaults_accepted": True}, save_result=False)
        codes.append(caught.value.code)
        assert caught.value.details["agent_recovery"]["must_ask_user"] is True
    assert codes == ["tool.time_unknown", "tool.time_unknown"], codes


@pytest.mark.parametrize(("date", "time", "place", "zone"), [("1986-05-04", "01:30", "上海", "+08:00"), ("2026-03-08", "01:30", "New York", "-05:00")])
def test_a_switch_day_hour_with_one_offset_is_not_asked(date: str, time: str, place: str, zone: str) -> None:
    """审计 F14：切换日的凌晨只对应一个偏移，以前也让用户在两个偏移里选（其中一个是错的）。负向对照（实跑过）：_switch_day_is_ambiguous 恒 True → 红。"""
    d = Path(tempfile.mkdtemp())
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=d, db_path=d / "m.db",
                        output_dir=d / "runs", runtime_root=d / "rt")
    out = HorosaSkillService(settings, store=MemoryStore(settings)).resolve_place_fields({"date": date, "time": time, "place": place}, tool_name="bazi_birth")
    assert out["zone"] == zone and "正午" in " ".join(out["placeResolution"]["caveat_notes"])


@pytest.mark.parametrize(("date", "time", "place"), [("1986-05-04", "02:30", "上海"), ("2026-11-01", "01:30", "New York")])
def test_a_real_gap_or_overlap_still_asks(date: str, time: str, place: str) -> None:
    d = Path(tempfile.mkdtemp())
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=d, db_path=d / "m.db",
                        output_dir=d / "runs", runtime_root=d / "rt")
    with pytest.raises(ToolValidationError) as caught:
        HorosaSkillService(settings, store=MemoryStore(settings)).resolve_place_fields({"date": date, "time": time, "place": place}, tool_name="bazi_birth")
    assert caught.value.code == "place.zone_ambiguous"


def test_synastry_reads_a_flat_first_person_as_inner() -> None:
    """审计 F31：{date, time, place, outer:{…}} 以前回「缺 inner…收到的 ['placeResolution'] 不是这两个键」。负向对照（实跑过）：不调 _promote_flat_first_person → 红。"""
    from horosa_skill.service.api.tools import _promote_flat_first_person

    other = {"date": "1992-01-01", "time": "10:00", "zone": "+08:00", "lat": "39n54", "lon": "116e23"}
    out = _promote_flat_first_person("relative", {**BIRTH, "outer": other, "hsys": 0})
    assert out["inner"]["date"] == "1990-05-03" and out["outer"] == other and out["hsys"] == 0 and "date" not in out
    assert _promote_flat_first_person("relative", {"inner": BIRTH, "outer": other}) == {"inner": BIRTH, "outer": other}
    assert _promote_flat_first_person("chart", BIRTH) == BIRTH


def test_zone_far_from_longitude_is_flagged() -> None:
    """审计 F30：zone 0 / -5 + 上海的坐标以前照算无提示。负向对照（实跑过）：_zone_longitude_note 直接 return → 红。"""
    from horosa_skill.input_fields import input_notes_scope
    from horosa_skill.service.api.tools import _zone_longitude_note

    with input_notes_scope() as notes:
        _zone_longitude_note({"zone": "-05:00", "lon": "121e28"}, [])
        _zone_longitude_note({"zone": "+08:00", "lon": "121e28"}, [])
        _zone_longitude_note({"zone": "+08:00", "lon": "87e36"}, [])          # 乌鲁木齐用北京时间：差 2.2 小时，不报
    assert len(notes) == 1 and "-05:00" in notes[0]


def test_a_place_label_far_from_the_coordinates_is_flagged(tmp_path) -> None:
    import shutil

    if shutil.which("node") is None:
        pytest.skip("[host] node not installed")
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path, db_path=tmp_path / "m.db",
                        output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt")
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    far = service.resolve_place_fields({"date": "1990-05-03", "time": "08:00", "place": "上海", "lat": "40n42", "lon": "74w00"}, tool_name="chart")
    assert any("km" in note for note in far["placeResolution"].get("caveat_notes", []))
    near = service.resolve_place_fields({"date": "1990-05-03", "time": "08:00", "place": "上海", "lat": "31n13", "lon": "121e28"}, tool_name="chart")
    assert not any("km" in note for note in near["placeResolution"].get("caveat_notes", []))


def test_bazi_says_when_true_solar_time_moves_the_pillars(tmp_path) -> None:
    """审计 F33：成都 23:10（1990 年夏令时）→ 真太阳时 21:09，时柱 / 日柱都与钟表读法不同，以前没有一句专门的话。
    负向对照（实跑过）：_note_clock_reading 直接 return → 红。"""
    import shutil

    if shutil.which("node") is None:
        pytest.skip("[host] node not installed")
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path, db_path=tmp_path / "m.db",
                        output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt")
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    moved = service.run_tool("bazi_birth", {"date": "1990-05-03", "time": "23:10", "place": "成都", "gender": 1, "defaults_accepted": True}, save_result=False)
    if not moved.ok and moved.error and moved.error.code.startswith(("js_engine", "runtime")):
        pytest.skip("[host] local JS engine unavailable")
    assert any("跨了时辰" in w and "时柱" in w for w in moved.warnings), moved.warnings
    calm = service.run_tool("bazi_birth", {"date": "1990-05-03", "time": "10:00", "place": "上海", "gender": 1, "defaults_accepted": True}, save_result=False)
    assert not any("跨了时辰" in w for w in calm.warnings)


def test_dir_place_fills_the_target_location(tmp_path) -> None:
    """审计 F19：dirPlace 以前只换来「不是本技法的参数」、盘按出生地算。负向对照（实跑过）：_resolve_dir_place 直接 return payload → 红。"""
    import shutil

    if shutil.which("node") is None:
        pytest.skip("[host] node not installed")
    from horosa_skill.engine.registry import TOOL_DEFINITIONS

    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path, db_path=tmp_path / "m.db",
                        output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt")
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    out = service._resolve_dir_place(TOOL_DEFINITIONS["solarreturn"], {**BIRTH, "datetime": "2026-05-03 08:00", "dirPlace": "New York"})
    assert out["dirLat"].startswith("40n") and out["dirLon"].startswith("74w") and "dirPlace" not in out


def test_one_day_suitability_goes_to_the_almanac_with_the_yiji_term() -> None:
    """审计 F21：「明天适合搬家吗」以前反问「哪段时间、做什么事」——用户都说了。负向对照（实跑过）：删掉 router 里 asks_one_day_suitability 分支 → 红。"""
    from horosa_skill.engine.router import route
    from horosa_skill.schemas.tools import DispatchInput

    result = route(DispatchInput.model_validate({"query": "明天适合搬家吗"}))
    assert result.tools == ["huangli"]
    assert any("移徙 / 入宅" in warning for warning in result.warnings)


def test_date_selection_asks_only_what_is_missing() -> None:
    """窗口与用事都说了 → 只问择日法；都没说 → 原话术。负向对照：_refuse_choice 不走 _date_selection_ask → 红。"""
    from horosa_skill.engine.router import route
    from horosa_skill.errors import DispatchResolutionError
    from horosa_skill.schemas.tools import DispatchInput

    with pytest.raises(DispatchResolutionError) as caught:
        route(DispatchInput.model_validate({"query": "帮我在12月挑个结婚的日子"}))
    prompt = caught.value.details["agent_recovery"]["prompt_to_user"]
    assert "哪段时间" not in prompt and "做什么事" not in prompt and "嫁娶" in prompt
    with pytest.raises(DispatchResolutionError) as caught:
        route(DispatchInput.model_validate({"query": "帮我挑个日子"}))
    assert "哪段时间" in caught.value.details["agent_recovery"]["prompt_to_user"]


def test_pre_standard_time_uses_the_birthplace_local_mean_time(tmp_path) -> None:
    """审计 F15：北京 1900、眉山 1037 以前拿到上海的地方平时 +08:05。负向对照（实跑过）：local_mean_time_override 恒回 None → 红。"""
    import shutil

    if shutil.which("node") is None:
        pytest.skip("[host] node not installed")
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path, db_path=tmp_path / "m.db",
                        output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt")
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    beijing = service.resolve_place_fields({"place": "北京", "date": "1900-01-01", "time": "12:00"}, tool_name="chart")
    assert beijing["zone"] == "+07:46" and any("地方平时" in note for note in beijing["placeResolution"]["caveat_notes"])
    meishan = service.resolve_place_fields({"place": "眉山", "date": "1037-01-08", "time": "06:00"}, tool_name="chart")
    assert meishan["zone"] == "+06:55"
    modern = service.resolve_place_fields({"place": "上海", "date": "1990-05-03", "time": "08:00"}, tool_name="chart")
    assert modern["zone"] == "+09:00" and not modern["placeResolution"]["caveat_notes"]


def test_china_before_1949_carries_the_five_zone_caveat() -> None:
    from horosa_skill.service.api.place import china_pre1949_caveat

    note = china_pre1949_caveat("Asia/Shanghai", "1945-07-01", 106.55, "+09:00")
    assert "陇蜀" in note and "+07:00" in note
    assert china_pre1949_caveat("Asia/Shanghai", "1950-01-01", 106.55, "+08:00") == ""
    assert china_pre1949_caveat("Asia/Hong_Kong", "1945-07-01", 114.17, "+09:00") == ""


def test_chinese_mingli_accepts_a_double_hour_at_its_midpoint() -> None:
    """待决项 1 第一档：「辰时」对八字 / 紫微 / 神数照算（中点、直接时间、披露）；西洋本命盘仍问钟点；子时不分早晚仍问。
    负向对照（实跑过）：_accept_shichen 直接 return payload → 红。"""
    from horosa_skill.engine.registry import TOOL_DEFINITIONS
    from horosa_skill.input_fields import input_notes_scope
    from horosa_skill.service.api.tools import _accept_shichen

    with input_notes_scope(fresh=True) as notes:
        out = _accept_shichen(TOOL_DEFINITIONS["bazi_birth"], {**BIRTH, "time": "辰时"})
    assert out["time"] == "08:00:00" and out["timeAlg"] == 1 and any("辰时" in note for note in notes)
    assert _accept_shichen(TOOL_DEFINITIONS["ziwei_birth"], {**BIRTH, "time": "晚子时"})["time"] == "23:30:00"
    assert _accept_shichen(TOOL_DEFINITIONS["bazi_birth"], {**BIRTH, "time": "辰时", "timeAlg": 0})["timeAlg"] == 0
    assert _accept_shichen(TOOL_DEFINITIONS["chart"], {**BIRTH, "time": "辰时"})["time"] == "辰时"
    assert _accept_shichen(TOOL_DEFINITIONS["bazi_birth"], {**BIRTH, "time": "子时"})["time"] == "子时"


def test_explicit_zone_one_dst_hour_off_the_place_is_asked_once(tmp_path) -> None:
    """待决项 3：上海 1990-05-03 在行夏令时（+09:00），显式 +08:00 → 问一次；zone_confirmed 后照用；跨区（北京时间写纽约）照算并写明当地几点。
    负向对照（实跑过）：_explicit_zone_check 直接 return "" → 红。"""
    import shutil

    if shutil.which("node") is None:
        pytest.skip("[host] node not installed")
    from horosa_skill.errors import ToolValidationError

    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path, db_path=tmp_path / "m.db",
                        output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt")
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    base = {"date": "1990-05-03", "time": "08:00", "place": "上海"}
    with pytest.raises(ToolValidationError) as caught:
        service.resolve_place_fields({**base, "zone": "+08:00"}, tool_name="bazi_birth")
    assert caught.value.code == "tool.zone_conflict" and caught.value.details["agent_recovery"]["must_ask_user"] is True
    assert [o["value"] for o in caught.value.details["options"]] == ["+09:00", "+08:00"]
    confirmed = service.resolve_place_fields({**base, "zone": "+08:00", "zone_confirmed": True}, tool_name="bazi_birth")
    assert confirmed["zone"] == "+08:00"
    assert service.resolve_place_fields({**base, "zone": "+09:00"}, tool_name="bazi_birth")["zone"] == "+09:00"
    overseas = service.resolve_place_fields({"date": "1990-05-03", "time": "08:00", "place": "纽约", "zone": "+08:00"}, tool_name="chart")
    assert any("当地 1990-05-02 20:00" in note for note in overseas["placeResolution"]["caveat_notes"])
