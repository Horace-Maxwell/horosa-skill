"""只有用户知道的事实，不许被缺省值或确认位顶替（审计 F08 / F11）。

F08 修前：14 个神数不给 time，带 defaults_accepted 就按 00:00 起（铁板时柱壬子），闸门把时刻问成「可选设置，留空按 00:00」。
F11 修前：合盘缺整个第二人 → must_ask_user:false，example 是一组现成出生数据——等于教模型自己编一个人。
负向对照（实跑过）：place_fields_required 去掉 SHENSHU_TIME_TOOLS → 第一个用例红；inner/outer 分支恒 ask=False → 第二个用例红。
"""
from __future__ import annotations

import pytest

from horosa_skill.agent_guidance.questions import SHENSHU_TIME_TOOLS
from horosa_skill.config import Settings
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.errors import ToolValidationError
from horosa_skill.memory.store import MemoryStore
from horosa_skill.schemas.tools.shenshu import ShenShuInput
from horosa_skill.service import HorosaSkillService


def _service(tmp_path) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path,
                        runtime_root=tmp_path / "runtime", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs",
                        trace_enabled=False)
    return HorosaSkillService(settings, store=MemoryStore(settings))


def test_every_shenshu_tool_is_covered() -> None:
    assert SHENSHU_TIME_TOOLS == {name for name, d in TOOL_DEFINITIONS.items() if issubclass(d.input_model, ShenShuInput)}


@pytest.mark.parametrize("tool", sorted(SHENSHU_TIME_TOOLS))
def test_shenshu_without_a_birth_time_is_refused_even_with_defaults_accepted(tmp_path, tool) -> None:
    payload = {"date": "1990-05-03", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gender": 0, "defaults_accepted": True}
    with pytest.raises(ToolValidationError) as excinfo:
        _service(tmp_path).run_tool(tool, payload, save_result=False)
    assert excinfo.value.code in ("tool.missing_field", "tool.time_unknown")   # 审计 F28：本命类缺 time 与「不详」同码
    fields = excinfo.value.details["fields"]
    assert [entry["field"] for entry in fields] == ["time"] and fields[0]["ask_user"] is True


def test_synastry_missing_the_second_person_asks_the_user(tmp_path) -> None:
    person = {"date": "1990-05-03", "time": "08:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"}
    with pytest.raises(ToolValidationError) as excinfo:
        _service(tmp_path).run_tool("relative", {"inner": person, "defaults_accepted": True}, save_result=False)
    entry = next(e for e in excinfo.value.details["fields"] if e["field"] == "outer")
    assert entry["ask_user"] is True and entry["example"]["date"] == "YYYY-MM-DD"
    # 键名写错（person2）才是模型自己改
    with pytest.raises(ToolValidationError) as excinfo:
        _service(tmp_path).run_tool("relative", {"inner": person, "person2": person, "defaults_accepted": True}, save_result=False)
    entry = next(e for e in excinfo.value.details["fields"] if e["field"] == "outer")
    assert entry["ask_user"] is False
