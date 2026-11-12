"""MCP-08：一条对**每个工具**都机检的不变量——任何 ok:false 都有顶层 code、message 与 details.agent_recovery.kind；
入参错误是 kind=input（给可选值），不是「重试 / 跑 doctor」。

扫法：真 server（create_mcp_server），全量面全部工具 × 三组坏参数（空、只有确认位、不认识的键 + 坏日期）。
引擎地址钉在 :9（conftest），所以走到引擎的调用拿到的是 runtime / transport 类错误——它们同样得满足不变量。
全程不到 5 秒（门面与闸门的拒绝都在本进程里完成）。
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from horosa_skill.config import Settings
from horosa_skill.errors import RECOVERY_KINDS, ToolValidationError, lift_failures
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces.mcp_server import create_mcp_server

_BAD_ARGUMENTS = {
    "empty": {},
    "confirmed_only": {"agent_confirmed_settings": True, "defaults_accepted": True},
    "unknown_and_bad_date": {"zzz_unknown": 1, "agent_confirmed_settings": True, "defaults_accepted": True, "date": "not-a-date"},
}
# 不是入参问题、而是「这台机器上的引擎没起」的类别：引擎钉在 :9 时它们是正确答案。
_ENVIRONMENT_KINDS = {"runtime", "transport", "js_engine", "environment"}


def _payload(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    return json.loads(result.content[0].text)


@pytest.fixture(scope="module")
def sweep(tmp_path_factory: pytest.TempPathFactory) -> dict[tuple[str, str], dict[str, Any]]:
    root = tmp_path_factory.mktemp("error-contract")
    settings = Settings(db_path=root / "memory.db", output_dir=root / "runs", runtime_root=root / "runtime")
    mcp = create_mcp_server(HorosaSkillService(settings, store=MemoryStore(settings)), settings)

    async def run_all() -> dict[tuple[str, str], dict[str, Any]]:
        out: dict[tuple[str, str], dict[str, Any]] = {}
        for tool in await mcp.list_tools():
            for label, arguments in _BAD_ARGUMENTS.items():
                out[(tool.name, label)] = _payload(await mcp.call_tool(tool.name, dict(arguments)))
        return out

    return asyncio.run(run_all())


def test_the_sweep_covers_the_whole_catalogue(sweep: dict) -> None:
    from horosa_skill.engine.registry import FACADE_TOOL_COUNT, TOOL_DEFINITIONS

    assert len({name for name, _label in sweep}) == FACADE_TOOL_COUNT + len(TOOL_DEFINITIONS)


def test_every_failure_carries_code_message_and_recovery_kind(sweep: dict) -> None:
    broken = {
        f"{name} [{label}]": {"code": payload.get("code"), "message": bool(payload.get("message")),
                              "kind": ((payload.get("details") or {}).get("agent_recovery") or {}).get("kind")}
        for (name, label), payload in sweep.items()
        if payload.get("ok") is False and not (
            payload.get("code") and payload.get("message")
            and ((payload.get("details") or {}).get("agent_recovery") or {}).get("kind") in RECOVERY_KINDS
        )
    }
    assert broken == {}


def test_every_result_says_ok(sweep: dict) -> None:
    assert sorted(f"{name} [{label}]" for (name, label), payload in sweep.items() if not isinstance(payload.get("ok"), bool)) == []


def test_input_mistakes_are_never_told_to_retry_or_run_doctor(sweep: dict) -> None:
    """坏参数得到的恢复说明要么是 input，要么是「本机引擎没起」这类环境原因——不是「重试一次，不行跑 doctor」。

    例外只有一种：码本身说的是引擎那一侧失败了（`*_unavailable` / `*_failed`，例如飞宫按当下时刻起课要先问
    /nongli/time，而引擎钉在 :9）。`horosa_skill_error`（旧的缺省码）与 `report.render.failed` 永远不该出现在这里。
    """
    wrong = {
        f"{name} [{label}]": payload.get("code")
        for (name, label), payload in sweep.items()
        if payload.get("ok") is False
        and ((payload.get("details") or {}).get("agent_recovery") or {}).get("kind") not in {"input", *_ENVIRONMENT_KINDS}
        and not str(payload.get("code")).endswith(("_unavailable", "_failed"))
    }
    assert wrong == {}
    legacy = sorted(f"{n} [{l}]" for (n, l), p in sweep.items() if p.get("code") in {"horosa_skill_error", "report.render.failed"})
    assert legacy == []


def test_named_instances_from_the_audit(sweep: dict) -> None:
    place = sweep[("horosa_place_search", "empty")]
    assert place["ok"] is False and place["details"]["agent_recovery"]["kind"] == "input"
    knowledge = sweep[("horosa_knowledge_read", "empty")]
    assert knowledge["code"] == "knowledge.unknown_domain" and "user" in knowledge["details"]["accepted"]
    assert "Unknown knowledge domain: " != knowledge["message"].split(" / ")[-1]
    huangli = sweep[("horosa_cn_huangli", "unknown_and_bad_date")]
    assert huangli["code"] != "horosa_skill_error"


def test_report_render_splits_bad_format_from_unknown_run(tmp_path: Path) -> None:
    settings = Settings(db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    mcp = create_mcp_server(HorosaSkillService(settings, store=MemoryStore(settings)), settings)
    bad_format = _payload(asyncio.run(mcp.call_tool("horosa_report_render", {"run_id": "nope", "format": "xls"})))
    unknown_run = _payload(asyncio.run(mcp.call_tool("horosa_report_render", {"run_id": "nope", "format": "docx"})))
    missing_run = _payload(asyncio.run(mcp.call_tool("horosa_memory_show", {"run_id": "nope"})))
    assert bad_format["code"] == "report.format_unsupported" and bad_format["details"]["accepted"] == ["json", "docx", "pdf", "png", "ics"]
    assert bad_format["details"]["agent_recovery"]["kind"] == "input"
    assert unknown_run["code"] == "report.run_not_found" and unknown_run["details"]["agent_recovery"]["kind"] == "input"
    assert missing_run["code"] == "memory.run.not_found" and missing_run["details"]["agent_recovery"]["kind"] == "input"


def test_place_search_success_keeps_its_fields_and_says_ok(tmp_path: Path) -> None:
    class Stub:
        def place_search(self, payload: dict) -> dict:
            return {"query": payload["query"], "resolved": False, "candidates": [], "next_step": "x", "warnings": []}

        def __getattr__(self, name: str) -> Any:
            raise AttributeError(name)

    settings = Settings(db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    mcp = create_mcp_server(Stub(), settings)  # type: ignore[arg-type]
    result = _payload(asyncio.run(mcp.call_tool("horosa_place_search", {"query": "nowhere"})))
    assert result["ok"] is True and result["query"] == "nowhere" and result["candidates"] == []


def test_dispatch_lifts_a_shared_failure_and_names_mixed_ones() -> None:
    same = lift_failures({
        "chart": ("runtime.external_unreachable", "engine down", {}),
        "bazi_birth": ("runtime.external_unreachable", "engine down", {}),
    })
    assert same[0] == "runtime.external_unreachable" and same[2]["agent_recovery"]["kind"] == "runtime"
    assert same[2]["failed_tools"] == {"chart": "runtime.external_unreachable", "bazi_birth": "runtime.external_unreachable"}
    mixed = lift_failures({"chart": ("tool.invalid_input", "bad date", {}), "qimen": ("runtime.not_installed", "no runtime", {})})
    assert mixed[0] == "dispatch.tools_failed" and mixed[2]["agent_recovery"]["kind"] == "input"
    assert lift_failures({}) is None


def test_a_validation_error_without_a_code_is_an_input_error() -> None:
    assert ToolValidationError("Invalid date for tool `huangli`: 'x'").code == "tool.invalid_input"
