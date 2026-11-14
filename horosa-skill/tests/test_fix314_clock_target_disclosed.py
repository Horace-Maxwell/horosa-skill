"""推运直调没给目标：照上游缺省按时钟取，但写进 warnings（审计 F16）。

修前：horosa_predict_solarreturn {出生数据, defaults_accepted:true} →「推运时间：2026-05-03 08:00」、warnings 空；服务端托管在别处时
「服务端的今天」未必是用户的今天，模型也不知道目标从哪来。缺省本身与上游一致（推运页的钟就是用户的钟），不改；只是不再不说。
负向对照（实跑过）：_disclose_clock_target 直接 return → 第一个用例红。
"""
from __future__ import annotations

import pytest

from horosa_skill.config import Settings
from horosa_skill.engine import time_roles
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

BIRTH = {"date": "1990-05-03", "time": "08:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gender": 0,
         "defaults_accepted": True}
TARGET_TOOLS = sorted(tool for tool, role in time_roles.TIME_ROLES.items() if role == time_roles.NATAL_TARGET)


def _service(tmp_path) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path,
                        runtime_root=tmp_path / "runtime", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs",
                        trace_enabled=False)
    return HorosaSkillService(settings, store=MemoryStore(settings))


@pytest.mark.parametrize("tool", TARGET_TOOLS)
def test_a_missing_target_is_disclosed(tmp_path, tool) -> None:
    # 离线时引擎不可达、信封可能 ok:false；入参说明在起算前就定了，成功 / 失败信封都回显。
    result = _service(tmp_path).run_tool(tool, BIRTH, save_result=False)
    field = time_roles.target_fields(tool)[0]
    assert any(f"没给推运目标（`{field}`）" in line for line in result.warnings), result.warnings


def test_a_given_target_is_not_flagged(tmp_path) -> None:
    result = _service(tmp_path).run_tool("solarreturn", {**BIRTH, "year": 2027}, save_result=False)
    assert not any("没给推运目标" in line for line in result.warnings), result.warnings
