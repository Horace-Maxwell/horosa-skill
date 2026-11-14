"""起课技法带 profile：只取当事人，不拿档案里的出生时刻起课（审计 F09）。

修前：horosa_cn_qimen {"profile":"妈妈","question":"看看我妈的病"} → ok，局是 1963-03-08 06:00（档案的出生时刻）的局，summary 只有一句
「出生信息取自命主档案」。dispatch 路径一直对（要 context 的此刻）；直调是漏的一半。奇门确有「终身局」用法，那应是调用方显式给的。
负向对照（实跑过）：expand_tool_payload 的 _is_cast 恒 False → 两个用例都红。
"""
from __future__ import annotations

import pytest

from horosa_skill import profiles as P
from horosa_skill.config import Settings
from horosa_skill.errors import ToolValidationError
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

MOM = {"date": "1963-03-08", "time": "06:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gender": 0}


def _service(tmp_path) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path,
                        runtime_root=tmp_path / "runtime", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs",
                        trace_enabled=False)
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    P.run_action(service.profiles, {"action": "save", "name": "妈妈", "data": MOM})
    return service


def test_a_cast_with_only_a_profile_asks_for_the_moment_not_her_birth(tmp_path) -> None:
    with pytest.raises(ToolValidationError) as excinfo:
        _service(tmp_path).run_tool("qimen", {"profile": "妈妈", "question": "看看我妈的病", "defaults_accepted": True}, save_result=False)
    fields = {entry["field"]: entry for entry in excinfo.value.details["fields"]}
    assert {"date", "time"} <= set(fields) and fields["date"]["ask_user"] is False   # F10 的「传此刻」话术


def test_explicit_moment_is_used_and_the_profile_note_says_why(tmp_path) -> None:
    result = _service(tmp_path).run_tool("qimen", {"profile": "妈妈", "question": "看看我妈的病", "date": "2026-11-14", "time": "10:00",
                                                   "zone": "+08:00", "lat": "31n13", "lon": "121e28", "defaults_accepted": True},
                                         save_result=False)
    assert result.input_normalized["date"] == "2026-11-14"   # 不是 1963-03-08
    assert any("档案「妈妈」只取当事人" in line for line in result.warnings), result.warnings
