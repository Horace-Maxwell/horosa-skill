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
    for payload in ({k: v for k, v in BIRTH.items() if k != "time"}, {**BIRTH, "time": "不详"}):
        with pytest.raises(ToolValidationError) as caught:
            service.run_tool("bazi_birth", {**payload, "defaults_accepted": True}, save_result=False)
        codes.append((caught.value.code, str(caught.value).split("\n")[-1]))
    assert codes[0] == codes[1] and codes[0][0] == "tool.time_unknown", codes


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
