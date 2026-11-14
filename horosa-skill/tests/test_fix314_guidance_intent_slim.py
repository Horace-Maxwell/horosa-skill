"""horosa_agent_guidance(intent=…) 只回随问题变的部分（审计 S-19）。

修前：「下个月哪天适合搬家？我属马」一调 6,879 B，随问题变的 suggested_tools 约 1.6 KB；其余每次照发 9 条 global_rules（第一条是让管理员跑
OpenClaw setup）、安装说明（约 730MB 下载）、default_workflow、server_profile。全套规则在不带参数 / include_all 时给。
负向对照（实跑过）：去掉 intent 分支的提前返回 → 红。
"""
from __future__ import annotations

import json

from horosa_skill.agent_guidance import build_agent_guidance


def test_intent_form_is_just_the_suggestions() -> None:
    result = build_agent_guidance(intent="下个月哪天适合搬家？我属马")
    assert result["suggested_tools"] and result["next_step"]
    assert not {"global_rules", "usage_help", "default_workflow", "tools"} & set(result)
    assert len(json.dumps(result, ensure_ascii=False).encode()) < 4_000


def test_bare_call_still_has_the_rules() -> None:
    result = build_agent_guidance()
    assert result["global_rules"] and result["usage_help"]
