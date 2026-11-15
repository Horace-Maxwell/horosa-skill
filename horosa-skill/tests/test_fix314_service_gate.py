"""审计 A-4 / PF-22：设置确认闸下沉到 service 层。

以前 `HorosaSkillService.run_tool("chart", {date,time,zone,lat,lon})` 不带确认位 → ok:true；同一载荷经 MCP → agent_guidance.required。
把包当库直接调的下游不受铁律 2 保护，每个新入口也都是一条潜在的绕闸路。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.errors import ToolValidationError
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

SRC = Path(__file__).resolve().parents[1] / "src" / "horosa_skill"
CHART = {"date": "1990-05-03", "time": "08:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"}


def _service(tmp_path: Path) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path,
                        db_path=tmp_path / "m.db", output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt")
    return HorosaSkillService(settings, store=MemoryStore(settings))


@pytest.mark.service_gate
def test_every_public_entry_refuses_without_confirmation_by_default(tmp_path: Path) -> None:
    """负向对照（实跑过）：gate.DEFAULT_GATE 改成 checked → run_tool 不拦 → 红。"""
    service = _service(tmp_path)
    calls = {
        "run_tool": lambda: service.run_tool("chart", dict(CHART), save_result=False),
        "dispatch": lambda: service.dispatch({"query": "看本命盘", "birth": dict(CHART), "save_result": False}),
        "hecan": lambda: service.hecan({"query": "看本命盘", "birth": dict(CHART), "tools": ["chart", "hellen_chart"], "save_result": False}),
        "report_from_tool": lambda: service.report_from_tool({"tool_name": "chart", "payload": dict(CHART), "format": "docx"}),
    }
    for name, call in calls.items():
        with pytest.raises(ToolValidationError) as caught:
            call()
        assert caught.value.code == "agent_guidance.required", name


@pytest.mark.service_gate
def test_confirmation_or_checked_lets_the_call_through_the_gate(tmp_path: Path) -> None:
    service = _service(tmp_path)
    for payload, gate in (({**CHART, "defaults_accepted": True}, None), (dict(CHART), "checked")):
        envelope = service.run_tool("chart", payload, save_result=False, gate=gate)
        assert envelope.code != "agent_guidance.required"   # 后端不可达是另一回事（:9）


def test_every_internal_and_surface_call_says_which_gate() -> None:
    """service / surfaces / benchmark 里每处 run_tool / dispatch / hecan / report_from_tool 调用都显式写 gate=：
    漏写 = 嵌套调用被二次拦（黄历择日丢段那一类），或入口绕过了自己的闸。负向对照：删掉任何一处的 gate= → 红。"""
    names = {"run_tool", "dispatch", "hecan", "report_from_tool"}
    missing = []
    for folder in (SRC / "service", SRC / "surfaces", SRC / "benchmark", SRC.parents[1] / "scripts"):
        for path in sorted(folder.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in names:
                    owner = node.func.value
                    owner_name = owner.id if isinstance(owner, ast.Name) else getattr(owner, "attr", "")
                    if owner_name not in {"self", "service"}:
                        continue
                    if not any(keyword.arg == "gate" for keyword in node.keywords) and not any(k.arg is None for k in node.keywords):
                        missing.append(f"{path.name}:{node.lineno} {owner_name}.{node.func.attr}")
    assert not missing, missing
