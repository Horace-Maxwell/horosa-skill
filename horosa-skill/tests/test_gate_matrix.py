"""澄清闸的整表行为录像：每个注册技法 × 四种载荷形状，闸的结论与它要问的字段。

**为什么（C-18 第 9 项）**：`test_sensitive_settings_gate.py::test_table_selftests_all_pass` 跑的是闸门数据文件
`data/sensitive_settings.json` 里自带的十几条 self_tests——期望与被测物住在一起，而且只覆盖少数工具。审计改
`agent_guidance/tool_table.py`（某技法的策略、要问的字段）全量照样绿。这里把期望搬出被测物：
`tests/fixtures/gate_matrix.json` 是**录下来的**全部 114 个技法的闸行为（不是手写的），改了任何一个技法该问什么，
这条就红；有意的改动重录并在 diff 里看清改了谁：

    uv run python tests/test_gate_matrix.py --record

四种形状：裸调；样例载荷不确认；样例载荷 + agent_confirmed_settings；样例载荷去掉性别 + defaults_accepted
（「确认不能代替事实」的那一格）。记录结论（pass / block）、要问的字段、给出的安全默认值字段。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "gate_matrix.json"


def _verdict(tool: str, payload: dict[str, Any]) -> dict[str, Any]:
    from horosa_skill.agent_guidance import validate_agent_preflight

    result = validate_agent_preflight(tool, payload)
    if result.get("ok"):
        return {"verdict": "pass"}
    return {
        "verdict": "block",
        "code": result.get("code"),
        "ask": sorted(str(item.get("field")) for item in result.get("ask_if_missing") or []),
        "facts": sorted(str(item.get("field")) for item in result.get("ask_if_missing") or [] if item.get("fact")),
        "defaults": sorted(str(item.get("field")) for item in result.get("safe_defaults") or []),
    }


def gate_matrix() -> dict[str, dict[str, Any]]:
    from horosa_skill.engine.registry import TOOL_DEFINITIONS
    from horosa_skill.testing_payloads import build_sample_payloads

    samples = build_sample_payloads()
    matrix: dict[str, dict[str, Any]] = {}
    for tool in sorted(TOOL_DEFINITIONS):
        sample = {k: v for k, v in (samples.get(tool) or {}).items()
                  if k not in {"agent_confirmed_settings", "defaults_accepted", "clarification_notes"}}
        no_gender = {k: v for k, v in sample.items() if k != "gender"}
        matrix[tool] = {
            "bare": _verdict(tool, {}),
            "sample": _verdict(tool, dict(sample)),
            "sample_confirmed": _verdict(tool, {**sample, "agent_confirmed_settings": True}),
            "no_gender_defaults_accepted": _verdict(tool, {**no_gender, "defaults_accepted": True}),
        }
    return matrix


def test_every_technique_gate_behaves_as_recorded() -> None:
    """负向对照（实跑过）：tool_table.py 里把 tieban 的策略从 SHENSHU_GENDER_ZONE_POLICY 换成 SHENSHU_ZONE_POLICY（不再问性别）、
    把 chart 的策略换成 ASTRO_BIRTH_POLICY，本例各红；data 文件里的 self_tests 两次都照样绿。"""
    recorded = json.loads(FIXTURE.read_text(encoding="utf-8"))
    current = gate_matrix()
    assert sorted(current) == sorted(recorded), "技法集合变了：重录 gate_matrix.json"
    changed = {tool: {shape: (recorded[tool][shape], current[tool][shape]) for shape in current[tool]
                      if current[tool][shape] != recorded[tool][shape]}
               for tool in current if current[tool] != recorded[tool]}
    assert not changed, json.dumps(changed, ensure_ascii=False, indent=1)[:3000]


def test_the_matrix_is_not_vacuous() -> None:
    """录像本身要有区分度：确认过的样例载荷大多放行，裸调大多拦，要事实（性别）的技法在「默认代替性别」那格拦。"""
    recorded = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(recorded) >= 114
    bare_blocks = sum(row["bare"]["verdict"] == "block" for row in recorded.values())
    confirmed_passes = sum(row["sample_confirmed"]["verdict"] == "pass" for row in recorded.values())
    fact_blocks = [tool for tool, row in recorded.items() if "gender" in row["no_gender_defaults_accepted"].get("facts", [])]
    assert bare_blocks >= 100 and confirmed_passes >= 100
    assert "bazi_birth" in fact_blocks and "tieban" in fact_blocks


if __name__ == "__main__":
    if sys.argv[1:] != ["--record"]:
        raise SystemExit("usage: uv run python tests/test_gate_matrix.py --record")
    FIXTURE.write_text(json.dumps(gate_matrix(), ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"recorded {FIXTURE}")
