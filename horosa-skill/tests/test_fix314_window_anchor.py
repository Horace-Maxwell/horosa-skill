"""择日窗口搜索不再硬要「基准日期 / 时刻」：缺了取搜索窗起点（审计 S-17）。

修前：horosa_cn_huanglizeri {place:"上海", startDate:"2026-12-01", endDate:"2026-12-31", …} → tool.invalid_payload、must_ask_user:true，
缺 date、time，连带「给了 place，但这个技法没有日期…请直接给 zone」——让模型去问用户一个没有意义的时刻（展示盘按首个命中铸）。
负向对照（实跑过）：_anchor_window_search 直接 return payload → 前两个用例红。
"""
from __future__ import annotations

import pytest

from horosa_skill.agent_guidance import build_agent_guidance
from horosa_skill.config import Settings
from horosa_skill.errors import ToolValidationError
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

CONDITIONS = {"kind": "group", "joiner": "all", "children": [
    {"kind": "leaf", "type": "yi_has", "params": {"values": ["嫁娶"], "matchMode": "any"}}]}


def _service(tmp_path) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path,
                        runtime_root=tmp_path / "runtime", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs",
                        trace_enabled=False)
    return HorosaSkillService(settings, store=MemoryStore(settings))


def _run(service, tool, payload):
    try:
        return service.run_tool(tool, payload, save_result=False), None
    except ToolValidationError as exc:
        return None, exc


@pytest.mark.parametrize("where", [{"place": "上海"}, {"zone": "+08:00", "lat": "31n13", "lon": "121e28"}])
def test_window_search_without_date_time_anchors_on_the_window_start(tmp_path, where) -> None:
    result, refused = _run(_service(tmp_path), "huanglizeri", {
        **where, "startDate": "2026-12-01", "startTime": "09:00", "endDate": "2026-12-31", "conditions": CONDITIONS,
        "defaults_accepted": True})
    # 离线时引擎不可达、信封可能 ok:false；要证的是入参这一关过了，不是 invalid_payload / 要问用户
    assert refused is None, refused and refused.code
    assert result.error is None or result.error.code != "tool.invalid_payload", result.error
    assert result.input_normalized["date"] == "2026-12-01" and result.input_normalized["time"].startswith("09:00")
    assert any("展示锚点取搜索窗起点 2026-12-01 09:00" in line for line in result.warnings), result.warnings


def test_a_half_given_anchor_or_a_natal_date_is_not_filled(tmp_path) -> None:
    service = _service(tmp_path)
    # 给了 date 没给 time：照旧按字段报 time，不替它补
    result, refused = _run(service, "huanglizeri", {"zone": "+08:00", "lat": "31n13", "lon": "121e28", "date": "2026-12-05",
                                                     "startDate": "2026-12-01", "endDate": "2026-12-31", "conditions": CONDITIONS,
                                                     "defaults_accepted": True})
    assert (refused or result.error).code in ("tool.invalid_payload", "tool.missing_field")
    # 星历也有 startDate，但那里的 date 是本命盘：不补
    result, refused = _run(service, "ephemeris", {"zone": "+08:00", "lat": "31n13", "lon": "121e28", "startDate": "2026-12-01",
                                                   "defaults_accepted": True})
    assert (refused or result.error).code in ("tool.invalid_payload", "tool.missing_field")


def test_guidance_does_not_list_date_time_as_required_for_window_search() -> None:
    contract = build_agent_guidance(tool_name="huanglizeri")["tools"]["huanglizeri"]["must_have_context"]
    assert "date" not in contract and "time" not in contract
    assert any("缺省取搜索窗起点" in item for item in contract)
    assert not any("location" in item for item in build_agent_guidance(tool_name="bazi_birth")["tools"]["bazi_birth"]["must_have_context"])
