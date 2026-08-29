"""澄清闸「策略即数据」测试（v0.33.0 批 II-2）。

真值源 = src/horosa_skill/data/sensitive_settings.json（自带 self_tests）；本文件跑表内例、
锁 coverage 不变量、验 HOROSA_CLARIFY 逃生舱三档、并按重构当日金标对拍闸输出（零回归锚点）。
"""

from __future__ import annotations

import json

import pytest

from horosa_skill.agent_guidance import (
    PREFLIGHT_EXEMPT_TOOLS,
    SENSITIVE_SETTINGS,
    TOOL_GUIDANCE,
    run_sensitive_settings_selftests,
    validate_agent_preflight,
)
from horosa_skill.engine.registry import TOOL_DEFINITIONS


def test_table_selftests_all_pass() -> None:
    report = run_sensitive_settings_selftests()
    assert report["ok"] is True, report["failures"]
    assert report["cases"] >= 9


def test_every_tool_is_classified() -> None:
    """coverage 不变量：新工具必须有 guidance 策略或进豁免表——静默不设防=红。"""
    unclassified = sorted(set(TOOL_DEFINITIONS) - set(TOOL_GUIDANCE) - PREFLIGHT_EXEMPT_TOOLS)
    assert unclassified == [], unclassified


def test_exempt_tools_all_exist_in_registry_or_are_documented() -> None:
    """豁免表不许挂幽灵键（改名/删工具后表里残留 = 假豁免）。"""
    known = set(TOOL_DEFINITIONS)
    ghosts = sorted(set(SENSITIVE_SETTINGS["exempt_tools"]) - known)
    assert ghosts == [], f"豁免表包含不存在的工具：{ghosts}"


def test_gate_output_matches_refactor_day_golden() -> None:
    """对拍锚点：表驱动改造当日捕获的闸输出逐键相等（策略值搬进 JSON，行为逐字节不动）。"""
    golden = {
        "chart_confirmed": {"ok": True, "tool_name": "chart", "enforced": True, "mode": "agent_confirmed_settings"},
        "xuanshi_bare": {"ok": True, "tool_name": "xuanshi", "enforced": False},
    }
    assert validate_agent_preflight("chart", {"agent_confirmed_settings": True}) == golden["chart_confirmed"]
    assert validate_agent_preflight("xuanshi", {}) == golden["xuanshi_bare"]
    blocked = validate_agent_preflight("chart", {})
    assert blocked["ok"] is False and blocked["code"] == "agent_guidance.required"
    assert blocked["confirmation_fields"] == ["agent_confirmed_settings", "defaults_accepted", "clarification_notes"]


def test_clarify_never_disables_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOROSA_CLARIFY", "never")
    verdict = validate_agent_preflight("chart", {})
    assert verdict == {"ok": True, "tool_name": "chart", "enforced": False, "mode": "env_never"}


def test_clarify_granular_exempts_only_listed_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOROSA_CLARIFY", 'granular:{"exempt":["chart"]}')
    assert validate_agent_preflight("chart", {})["ok"] is True
    assert validate_agent_preflight("bazi_birth", {})["ok"] is False, "未列名工具照常拦"


def test_clarify_malformed_granular_falls_back_to_always(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOROSA_CLARIFY", "granular:{not json")
    assert validate_agent_preflight("chart", {})["ok"] is False, "解析失败必须落安全侧（闸开）"


def test_table_is_valid_json_with_required_keys() -> None:
    for key in ("confirmation_fields", "exempt_tools", "failure_code", "self_tests", "clarify_env"):
        assert key in SENSITIVE_SETTINGS, key
    assert json.dumps(SENSITIVE_SETTINGS)  # 可序列化（无奇异对象混入）


def test_hermetic_benchmark_scrubs_local_flags(monkeypatch) -> None:
    """批 II-5：--hermetic 剥掉本机旗标（HOROSA_CLARIFY=never 不再能放掉闸自测），
    报告如实记录剥了什么，退出后环境恢复。"""
    import os

    from horosa_skill.benchmark.runner import _hermetic_env

    monkeypatch.setenv("HOROSA_CLARIFY", "never")
    monkeypatch.setenv("HOROSA_MCP_COMPACT", "1")
    monkeypatch.setenv("HOROSA_NODE_BIN", "/fake/node")
    with _hermetic_env() as scrubbed:
        assert "HOROSA_CLARIFY" in scrubbed and "HOROSA_MCP_COMPACT" in scrubbed
        assert os.environ.get("HOROSA_CLARIFY") is None
        assert os.environ.get("HOROSA_NODE_BIN") == "/fake/node", "实例/引擎定位白名单必须保留"
        assert validate_agent_preflight("chart", {})["ok"] is False, "剥掉 never 后闸恢复"
    assert os.environ.get("HOROSA_CLARIFY") == "never", "退出恢复"
