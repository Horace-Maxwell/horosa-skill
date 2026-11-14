"""dispatch 缺出生地点时，给用户看的话是人话，不是 pydantic 的内部路径（审计 S-08）。

修前（MCP 面）：`birth` 是几种出生模型的联合，pydantic 每个分支各报一遍（16 条），loc 夹着
`function-after[_custom_terms_need_tables(), BirthInput]` / `ZiWeiBirthInput`；prompt_to_user 原样外露、zone / lat / lon 各问一条。
负向对照（实跑过）：mcp_errors 去掉 one_error_per_field、或 preflight 不合并地点 → 两个用例都红。
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from horosa_skill.input_normalization import normalize_request_payload
from horosa_skill.schemas.tools import DispatchInput
from horosa_skill.surfaces.mcp_errors import _mcp_validation_error_payload, _validation_error

PAYLOAD = {"query": "帮我排个八字", "birth": {"date": "1990-05-03", "time": "08:00", "gender": "女"}}


def _exc() -> ValidationError:
    with pytest.raises(ValidationError) as excinfo:
        DispatchInput.model_validate(normalize_request_payload(PAYLOAD))
    return excinfo.value


@pytest.mark.parametrize("build", [
    lambda exc: _validation_error("horosa_dispatch", "dispatch", exc).details,
    lambda exc: _mcp_validation_error_payload("horosa_dispatch", "dispatch", exc)["details"],
])
def test_mcp_validation_failure_asks_for_the_place_once(build) -> None:
    details = build(_exc())
    locs = [error["loc"] for error in details["validation_errors"]]
    assert locs == [["birth", "zone"], ["birth", "lat"], ["birth", "lon"]]   # 每个字段一条，没有模型类名
    prompt = details["agent_recovery"]["prompt_to_user"]
    assert "function-after" not in prompt and "BirthInput" not in prompt and "Field required" not in prompt
    # 合成一条：中英各写一遍 → 「缺出生地点」一次、birth.zone 两次；没有单独的 lat / lon 缺失行
    assert prompt.count("缺出生地点") == 1 and prompt.count("birth.zone") == 2 and "`birth.place`" in prompt
    assert "`birth.lat` 缺失" not in prompt
