"""澄清闸覆盖面：每个能走到 `run_tool` 的表面入口都必须先过闸（v0.47.2-dev）。

闸门不在 service 里，而在各表面入口：MCP 的工具函数体、CLI 的命令函数。少写一处就是一条绕闸的路——`horosa_hecan` / `hecan`
从 v0.28.0 起就是这样：同一份缺性别的出生信息，技法工具与 dispatch 都拒，合参照跑。原有闸门测试逐个点名入口，没点到的入口就没人管。

所以这里**枚举**而不点名：MCP 侧调 `list_tools()` 列出的每个工具，CLI 侧扫每个 Typer 命令函数。新加的入口自动进守卫，要豁免必须写进来。
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import anyio
import pytest
from typer.testing import CliRunner

from horosa_skill.agent_guidance import PREFLIGHT_EXEMPT_TOOLS, validate_agent_preflight
from horosa_skill.config import Settings
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.memory.store import MemoryStore
from horosa_skill.schemas.common import ToolEnvelope
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces import cli as cli_module
from horosa_skill.surfaces import mcp_server as M
from horosa_skill.testing_payloads import build_sample_payloads

CLI_SOURCE = Path(cli_module.__file__)
BIRTH = {"date": "1990-06-15", "time": "10:30:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"}
CONFIRM = {"agent_confirmed_settings": True, "clarification_notes": "gate coverage test"}
SAMPLES = build_sample_payloads()
# 只有这些 MCP 工具可以不确认就到 run_tool：闸表自己声明的豁免（查知识 / 查注册表 / 解析导出文本，不起盘）。
EXEMPT_MCP = frozenset(TOOL_DEFINITIONS[name].mcp_name for name in PREFLIGHT_EXEMPT_TOOLS if name in TOOL_DEFINITIONS)
_BY_MCP_NAME = {definition.mcp_name: name for name, definition in TOOL_DEFINITIONS.items()}


def _arguments(mcp_name: str, *, confirmed: bool) -> dict:
    """给足起盘数据的一份通用入参：新门面不用改这里就进守卫。确认位是唯一变量。"""
    extra = CONFIRM if confirmed else {}
    if mcp_name in _BY_MCP_NAME:
        sample = {k: v for k, v in SAMPLES[_BY_MCP_NAME[mcp_name]].items() if k not in CONFIRM and k != "defaults_accepted"}
        return {**sample, **extra}
    return {
        **BIRTH, **extra, "gender": 1, "query": "看看八字", "tools": ["bazi_birth"], "tool_name": "bazi_birth",
        "payload": {**BIRTH, "gender": 1, **extra}, "format": "json", "run_id": "r",
    }


def _spied_server(tmp_path: Path, *, compact: bool = False):
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
                        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs", mcp_compact=compact)
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    reached: list[str] = []

    def _spy(tool_name: str, payload: dict, **_kwargs) -> ToolEnvelope:
        reached.append(tool_name)
        return ToolEnvelope(ok=True, tool=tool_name, version="test", input_normalized={})

    service.run_tool = _spy  # type: ignore[method-assign]
    return M.create_mcp_server(service, settings), service, reached


def _reached_by_tool(mcp, reached: list[str], *, confirmed: bool) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for tool in anyio.run(mcp.list_tools):
        reached.clear()

        async def _call(name: str = tool.name) -> None:
            await mcp.call_tool(name, _arguments(name, confirmed=confirmed))

        anyio.run(_call)
        if reached:
            out[tool.name] = list(reached)
    return out


@pytest.fixture(autouse=True)
def _gate_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOROSA_CLARIFY", raising=False)
    monkeypatch.setenv("HOROSA_MCP_ELICIT", "0")


@pytest.mark.parametrize("compact", [False, True], ids=["full", "compact"])
def test_no_mcp_tool_reaches_run_tool_unconfirmed(tmp_path: Path, compact: bool) -> None:
    mcp, _service, reached = _spied_server(tmp_path, compact=compact)
    leaked = {name: tools for name, tools in _reached_by_tool(mcp, reached, confirmed=False).items() if name not in EXEMPT_MCP}
    assert not leaked, f"这些 MCP 工具没过澄清闸就跑了技法：{leaked}"


@pytest.mark.parametrize("compact", [False, True], ids=["full", "compact"])
def test_the_coverage_probe_really_reaches_run_tool_once_confirmed(tmp_path: Path, compact: bool) -> None:
    """正向对照：同一份入参带上确认就到得了 run_tool。否则上一条可能只是因为入参不合法才「没到」，绿得毫无意义。"""
    mcp, _service, reached = _spied_server(tmp_path, compact=compact)
    got = _reached_by_tool(mcp, reached, confirmed=True)
    expected = {"horosa_dispatch", "horosa_hecan", "horosa_report_from_tool"}
    if compact:
        expected.add("horosa_tool_run")
    else:
        expected |= {definition.mcp_name for definition in TOOL_DEFINITIONS.values()}
    assert expected <= set(got), f"探针没到 run_tool：{sorted(expected - set(got))}"


# 命令函数里直接调了这些 service 方法，就是一条到 run_tool 的路。
_RUN_METHODS = frozenset({"run_tool", "dispatch", "hecan", "report_from_tool"})


def _is_commanded(node: ast.stmt) -> bool:
    return isinstance(node, ast.FunctionDef) and any(
        isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "command" for d in node.decorator_list
    )


def _self_confirmed_or_exempt(call: ast.Call) -> bool:
    """`run_tool("export_registry", …)` 这种字面量豁免工具，或 selfcheck 这种载荷字面量里自带确认的内部探针。"""
    args = call.args
    if args and isinstance(args[0], ast.Constant) and args[0].value in PREFLIGHT_EXEMPT_TOOLS:
        return True
    return any(
        isinstance(arg, ast.Dict) and any(isinstance(k, ast.Constant) and k.value == "agent_confirmed_settings" for k in arg.keys)
        for arg in args
    )


def unguarded_cli_commands(source: str) -> list[str]:
    offenders: list[str] = []
    for node in ast.parse(source).body:
        if not _is_commanded(node):
            continue
        calls = [n for n in ast.walk(node) if isinstance(n, ast.Call)]
        runs = [c for c in calls if isinstance(c.func, ast.Attribute) and c.func.attr in _RUN_METHODS]
        if not runs or any(isinstance(c.func, ast.Name) and c.func.id == "_enforce_agent_preflight" for c in calls):
            continue
        if not all(_self_confirmed_or_exempt(c) for c in runs):
            offenders.append(node.name)
    return offenders


def test_every_cli_command_reaching_run_tool_enforces_the_gate() -> None:
    assert unguarded_cli_commands(CLI_SOURCE.read_text(encoding="utf-8")) == []


def test_the_cli_scan_catches_a_command_that_skips_the_gate() -> None:
    """负向对照：扫描器本身要抓得到「新命令调了 service.hecan 却没过闸」。"""
    source = (
        '@app.command()\ndef fresh(payload):\n    service = _service()\n    return service.hecan(payload)\n\n'
        '@app.command()\ndef probe():\n    return service.run_tool("export_registry", {})\n'
    )
    assert unguarded_cli_commands(source) == ["fresh"]


@pytest.mark.parametrize(
    ("argv", "body"),
    [
        (["hecan", "--query", "看看八字", "--tool", "bazi_birth", "--stdin"], {"birth": BIRTH}),
        (["dispatch", "--stdin"], {"query": "看看八字", "birth": BIRTH}),
        (["tool", "run", "bazi_birth", "--stdin"], BIRTH),
        (["report", "from-tool", "bazi_birth", "--format", "json", "--stdin"], BIRTH),
    ],
    ids=["hecan", "dispatch", "tool-run", "report-from-tool"],
)
def test_cli_refuses_an_unconfirmed_calculation_before_it_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, argv: list[str], body: dict
) -> None:
    _mcp, service, reached = _spied_server(tmp_path)
    monkeypatch.setattr(cli_module, "_service", lambda: service)
    result = CliRunner().invoke(cli_module.app, argv, input=json.dumps(body))
    assert result.exit_code == 2, result.output
    assert json.loads(result.stderr)["code"] == "agent_guidance.required"
    assert reached == []


def test_cli_hecan_runs_once_the_caller_confirms(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _mcp, service, reached = _spied_server(tmp_path)
    monkeypatch.setattr(cli_module, "_service", lambda: service)
    result = CliRunner().invoke(
        cli_module.app, ["hecan", "--query", "看看八字", "--tool", "bazi_birth", "--stdin"],
        input=json.dumps({"birth": BIRTH, **CONFIRM}),
    )
    assert result.exit_code == 0, result.output
    assert reached == ["bazi_birth"]


def test_hecan_gate_is_the_dispatch_gate_with_a_named_operation() -> None:
    for name in ("hecan", "horosa_hecan"):
        verdict = validate_agent_preflight(name, {"query": "看看八字"})
        assert verdict["ok"] is False and verdict["code"] == "agent_guidance.required"
        assert "target technique" in [item["field"] for item in verdict["ask_if_missing"]]
    assert validate_agent_preflight("hecan", {"defaults_accepted": True})["ok"] is True
    # 显式 `tools` 已经答了「用哪种技法」：闸门不再问一遍。
    named = validate_agent_preflight("hecan", {"query": "看看八字", "tools": ["bazi_birth"]})
    assert named["ok"] is False and "target technique" not in [item["field"] for item in named["ask_if_missing"]]


def test_hecan_refusal_carries_the_recovery_contract(tmp_path: Path) -> None:
    mcp, _service, reached = _spied_server(tmp_path)

    async def _call():
        return await mcp.call_tool("horosa_hecan", {"query": "看看八字", "birth": BIRTH, "tools": ["bazi_birth"]})

    result = anyio.run(_call)
    body = json.loads(result.content[0].text)
    assert body["ok"] is False and body["code"] == "agent_guidance.required"
    assert body["details"]["agent_recovery"]["must_ask_user"] is True
    assert reached == []
