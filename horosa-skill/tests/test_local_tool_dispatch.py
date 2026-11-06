"""本地工具分派：缺省走命名约定 `_run_<技法名>_tool(payload)`，约定之外的才进覆盖表。

分派曾是一条 70 多个分支的 if 链，每加一个技法抄两行。约定一旦成立，「漏写分支」就变成「方法名拼错」：
运行时才报 `tool.unsupported_local_tool`，所以这里在测试期把全部本地工具解析一遍。"""
from __future__ import annotations

import pytest

from horosa_skill.engine.registry import TOOL_DEFINITIONS, ToolDefinition
from horosa_skill.errors import ToolValidationError
from horosa_skill.schemas.tools import BirthInput
from horosa_skill.service import HorosaSkillService
from horosa_skill.service.api.tools import _LOCAL_RUNNER_OVERRIDES, ToolsAPI

LOCAL_TOOLS = sorted(name for name, definition in TOOL_DEFINITIONS.items() if definition.execution == "local")
# 分派只读类属性，不需要真实例；不走 __init__，这里不碰任何后端与数据目录。
SERVICE = HorosaSkillService.__new__(HorosaSkillService)


def test_every_local_tool_resolves_to_a_real_runner() -> None:
    assert [name for name in LOCAL_TOOLS if SERVICE._local_runner(name) is None] == []


def test_the_override_table_holds_only_real_exceptions() -> None:
    assert set(_LOCAL_RUNNER_OVERRIDES) <= set(LOCAL_TOOLS), "覆盖表里有不存在的本地工具"
    dead = [name for name in _LOCAL_RUNNER_OVERRIDES if hasattr(HorosaSkillService, f"_run_{name}_tool")]
    assert dead == [], f"这些工具已有约定名 runner，覆盖项是死条目：{dead}"


def test_an_unregistered_local_tool_is_a_structured_error() -> None:
    definition = ToolDefinition("no_such_tool", "cn", "no_such_tool", None, BirthInput, "x")
    with pytest.raises(ToolValidationError) as excinfo:
        ToolsAPI._run_local_tool(SERVICE, definition, {})
    assert excinfo.value.code == "tool.unsupported_local_tool"
    assert excinfo.value.details == {"tool_name": "no_such_tool"}
