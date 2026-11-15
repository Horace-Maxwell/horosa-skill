"""设置确认闸在 service 层（审计 A-4 / PF-22）。

以前闸门只在入口层（MCP `_gated_run` 与 CLI 四处）：把包当库直接调 `HorosaSkillService.run_tool("chart", {…})` 不带确认位
照样出盘——铁律 2「结果敏感设置缺失先问后调」对库用户不成立，每个新入口也都是一条潜在的绕闸路。

现在 `run_tool` / `dispatch` / `hecan` / `report_from_tool` 带仅限关键字的 `gate`：
- 缺省 `"enforce"`：跑同一个 `validate_agent_preflight`，不过就抛 `agent_guidance.required`（details 与入口层同形）。
- `"checked"`：调用方已经过了闸（MCP 先问用户 / elicitation，CLI 自己的闸）或是内部的嵌套调用。
service 内部嵌套的技法调用（runner 拼子盘、dispatch 下发、合参）一律显式写 `gate="checked"`（tests 里有 AST 守卫）；
嵌套深度 > 1 的 run_tool 本来就不再判闸。测试套件经 conftest 把缺省换成 "checked"（只有专测闸门的用例用真缺省）。
"""
from __future__ import annotations

from typing import Any

from horosa_skill.errors import ToolValidationError, bilingual

ENFORCE = "enforce"
CHECKED = "checked"
GATE_MODES = frozenset({ENFORCE, CHECKED})
# 进程级缺省：库用户拿到的是 enforce。tests/conftest.py 把它换成 checked（专测闸门的用例标 @pytest.mark.service_gate 用真缺省）。
DEFAULT_GATE = ENFORCE


def effective(gate: str | None) -> str:
    if gate is None:
        return DEFAULT_GATE
    if gate not in GATE_MODES:
        raise ValueError(f"gate 只收 enforce / checked，收到 {gate!r} / gate must be one of {sorted(GATE_MODES)}, got {gate!r}")
    return gate


def enforce(tool_name: str, payload: Any, gate: str | None) -> None:
    """`gate` 生效为 enforce 时判闸；没过就抛 agent_guidance.required（details = 入口层同一份裁决）。"""
    if effective(gate) != ENFORCE or not isinstance(payload, dict):
        return
    from horosa_skill.agent_guidance import validate_agent_preflight

    verdict = validate_agent_preflight(tool_name, payload)
    if verdict.get("ok"):
        return
    raise ToolValidationError(
        bilingual("调用前要先确认会影响结果的设置（details.agent_recovery 里是要问用户的话）；已经问过用户就带 defaults_accepted / "
                  "agent_confirmed_settings，或由已过闸的入口传 gate=\"checked\"。",
                  str(verdict.get("message") or "Confirm the result-changing settings first.")),
        code=str(verdict.get("code")), details=verdict)
