"""CLI 的拒绝路径：exit 2 + stderr 一份 JSON，绝不是 traceback（v0.47.2-dev）。

22 处手写的 `typer.echo(json.dumps({...}))`：pydantic 的 `exc.errors()` 把 ValueError 留在 `ctx` 里，`json.dumps` 当场 TypeError，
契约写的 exit 2 + JSON 变成 exit 1 + 197 行 traceback；`--input` 读失败同样裸奔；BOM 只有 stdin 收；`hint` / `next_action` 只有 MCP 面有。
全部收进 `_refuse`，这里锁住。"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import anyio
import pytest
import typer
from fakes import FakeClient, FakeJsClient
from typer.testing import CliRunner

from horosa_skill.config import Settings
from horosa_skill.errors import ToolValidationError
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces import cli as C
from horosa_skill.surfaces import mcp_runner
from horosa_skill.surfaces import mcp_server as M
from horosa_skill.textscript import TRADITIONAL, convert
from horosa_skill.textscript import localize as localize_module
from horosa_skill.textscript.localize import localize

BIRTH = {"date": "1990-06-15", "time": "10:30:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gender": 1}
CONFIRM = {"defaults_accepted": True}
RUNNER = CliRunner()


def _service(tmp_path: Path, **kwargs) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
                        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs", **kwargs)
    return HorosaSkillService(settings, client=FakeClient(), chart_client=FakeClient(), js_client=FakeJsClient(),
                              store=MemoryStore(settings))


@pytest.fixture()
def service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> HorosaSkillService:
    built = _service(tmp_path)
    monkeypatch.setattr(C, "_service", lambda: built)
    return built


def _refusal(result) -> dict:
    assert result.exit_code == 2, (result.exit_code, repr(result.exception), result.output)
    return json.loads(result.stderr)


@pytest.mark.parametrize(
    ("argv", "knob"),
    [
        (["tool", "run", "chart", "--stdin"], "sunriseMode"),
        (["report", "from-tool", "chart", "--format", "json", "--stdin"], "sunriseMode"),
        (["tool", "run", "draconic", "--stdin"], "draconicHouses"),
    ],
    ids=["tool-run", "report-from-tool", "draconic"],
)
def test_a_validator_rejection_is_exit_2_json_not_a_traceback(service, argv: list[str], knob: str) -> None:
    body = _refusal(RUNNER.invoke(C.app, argv, input=json.dumps({**BIRTH, **CONFIRM, knob: "bogus"})))
    assert body["code"] == "tool.invalid_payload"
    assert any(knob in str(error.get("msg")) or knob in str(error.get("loc")) for error in body["details"]["errors"])


def test_validation_errors_carry_no_exception_objects(service) -> None:
    with pytest.raises(ToolValidationError) as excinfo:
        service.run_tool("chart", {**BIRTH, **CONFIRM, "sunriseMode": "bogus"})
    json.dumps(excinfo.value.details)  # 不抛才算数：错误信封要能出进程


def test_missing_input_file_is_a_clean_refusal(service, tmp_path: Path) -> None:
    body = _refusal(RUNNER.invoke(C.app, ["tool", "run", "chart", "--input", str(tmp_path / "nope.json")]))
    assert body["code"] == "tool.invalid_payload" and "nope.json" in body["message"]


def test_undecodable_input_file_is_a_clean_refusal(service, tmp_path: Path) -> None:
    target = tmp_path / "gbk.json"
    target.write_bytes('{"name": "张三"}'.encode("gbk"))
    assert _refusal(RUNNER.invoke(C.app, ["tool", "run", "chart", "--input", str(target)]))["code"] == "tool.invalid_payload"


def test_undecodable_stdin_is_a_clean_refusal(service) -> None:
    result = RUNNER.invoke(C.app, ["tool", "run", "chart", "--stdin"], input='{"name": "张三"}'.encode("gbk"))
    assert _refusal(result)["code"] == "tool.invalid_payload"


@pytest.mark.parametrize("raw", ["{not json", "[1, 2]"], ids=["broken-json", "not-an-object"])
def test_bad_json_is_a_json_refusal_too(service, raw: str) -> None:
    assert _refusal(RUNNER.invoke(C.app, ["tool", "run", "chart", "--stdin"], input=raw))["code"] == "tool.invalid_payload"


def test_a_bom_is_accepted_from_a_file_exactly_as_from_stdin(service, tmp_path: Path) -> None:
    """Windows PowerShell 5.1 的 `Out-File -Encoding utf8` 写 BOM，而 `--input` 正是 SKILL.md 给那台机器指的路。"""
    payload = json.dumps({**BIRTH, **CONFIRM}, ensure_ascii=False).encode("utf-8")
    target = tmp_path / "bom.json"
    target.write_bytes(b"\xef\xbb\xbf" + payload)
    from_file = RUNNER.invoke(C.app, ["tool", "run", "chart", "--input", str(target), "--no-save-result"])
    from_stdin = RUNNER.invoke(C.app, ["tool", "run", "chart", "--stdin", "--no-save-result"], input=b"\xef\xbb\xbf" + payload)
    assert from_file.exit_code == from_stdin.exit_code == 0, from_file.output
    assert json.loads(from_file.stdout)["input_normalized"] == json.loads(from_stdin.stdout)["input_normalized"]


def _mcp_call(service: HorosaSkillService, tool: str, arguments: dict) -> dict:
    mcp = M.create_mcp_server(service, service.settings)

    async def _go():
        return await mcp.call_tool(tool, arguments)

    return json.loads(anyio.run(_go).content[0].text)


@pytest.mark.parametrize("flat", [False, True], ids=["nested", "flat"])
def test_numeric_coordinates_dispatch_on_the_cli_as_on_mcp(service, tmp_path: Path, flat: bool) -> None:
    place = {**BIRTH, "lat": 31.22, "lon": 121.47, "zone": 8}
    payload = {"query": "看看八字", **CONFIRM, **(place if flat else {"birth": place})}
    result = RUNNER.invoke(C.app, ["dispatch", "--stdin"], input=json.dumps(payload))
    assert result.exit_code == 0, (result.output, repr(result.exception))
    via_cli = json.loads(result.stdout)
    via_mcp = _mcp_call(_service(tmp_path / "mcp"), "horosa_dispatch", {"request": payload})
    assert via_cli["ok"] is via_mcp["ok"] is True
    assert via_cli["normalized_inputs"] == via_mcp["normalized_inputs"]


def test_numeric_coordinates_hecan_on_the_cli(service) -> None:
    body = {"birth": {**BIRTH, "lat": 31.22, "lon": 121.47}, **CONFIRM}
    result = RUNNER.invoke(C.app, ["hecan", "--query", "看看八字", "--tool", "bazi_birth", "--stdin"], input=json.dumps(body))
    assert result.exit_code == 0, (result.output, repr(result.exception))
    assert json.loads(result.stdout)["ok"] is True


def test_a_clean_dispatch_payload_is_echoed_byte_for_byte(service) -> None:
    """合法载荷不走归一化：成功命令的 stdout 不许变，`normalized_inputs` 回显的还是调用方写的 Asia/Shanghai。"""
    clean = {"query": "看看八字", "birth": {**BIRTH, "zone": "Asia/Shanghai"}, **CONFIRM}
    result = RUNNER.invoke(C.app, ["dispatch", "--stdin"], input=json.dumps(clean))
    assert result.exit_code == 0, (result.output, repr(result.exception))
    echoed = json.loads(result.stdout)["normalized_inputs"]["bazi_birth"]
    assert echoed["zone"] == "Asia/Shanghai" and "gpsLat" not in echoed


def test_a_payload_normalization_cannot_save_is_still_refused(service) -> None:
    body = _refusal(RUNNER.invoke(C.app, ["dispatch", "--stdin"], input=json.dumps({"birth": BIRTH, **CONFIRM})))
    assert body["code"] == "dispatch.invalid_payload"


@pytest.mark.parametrize(
    ("argv", "body", "tool", "arguments"),
    [
        (["tool", "run", "chart", "--stdin"], BIRTH, "horosa_astro_chart", BIRTH),
        (["tool", "run", "chart", "--stdin"], {"time": "10:30:00", **CONFIRM}, "horosa_astro_chart", {"time": "10:30:00", **CONFIRM}),
    ],
    ids=["gate", "invalid-payload"],
)
def test_cli_refusals_carry_the_recovery_hints_mcp_gives(service, tmp_path: Path, argv, body, tool, arguments) -> None:
    on_cli = _refusal(RUNNER.invoke(C.app, argv, input=json.dumps(body)))
    on_mcp = _mcp_call(_service(tmp_path / "mcp"), tool, arguments)
    assert on_cli["code"] == on_mcp["code"]
    for key in ("hint", "next_action", "agent_recovery"):
        assert key in on_cli["details"] and key in on_mcp["details"], key


def test_an_unknown_tool_refusal_carries_agent_recovery(service) -> None:
    body = _refusal(RUNNER.invoke(C.app, ["tool", "run", "nosuch", "--stdin"], input="{}"))
    assert body["code"] == "tool.unknown" and "agent_recovery" in body["details"] and "catalog" in body["details"]


def _hand_rolled_refusals(source: str) -> list[int]:
    """stderr 上的 JSON 只许由 `_write_refusal` 写：每多一份手写，就多一处忘 recovery、忘 default=str 的机会。"""
    tree = ast.parse(source)
    allowed = {id(node) for fn in ast.walk(tree) if isinstance(fn, ast.FunctionDef) and fn.name == "_write_refusal" for node in ast.walk(fn)}
    lines: list[int] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "echo") or id(node) in allowed:
            continue
        to_stderr = any(k.arg == "err" and isinstance(k.value, ast.Constant) and k.value.value is True for k in node.keywords)
        first = node.args[0] if node.args else None
        dumped = isinstance(first, ast.Call) and isinstance(first.func, ast.Attribute) and first.func.attr == "dumps"
        if to_stderr and dumped:
            lines.append(node.lineno)
    return lines


def test_the_cli_has_one_refusal_writer() -> None:
    # 流程模块也算：命令挪出 cli.py 之后，守卫要跟着它们走。
    offenders = {path.name: _hand_rolled_refusals(path.read_text(encoding="utf-8")) for path in Path(C.__file__).parent.glob("*.py")}
    assert {name: lines for name, lines in offenders.items() if lines} == {}


def test_the_refusal_scan_catches_a_hand_rolled_copy() -> None:
    assert _hand_rolled_refusals('import json, typer\ntyper.echo(json.dumps({"ok": False}), err=True)\n') == [2]
    assert _hand_rolled_refusals('import typer\ntyper.echo("progress", err=True)\n') == []


def test_refusal_output_survives_values_json_cannot_encode(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(typer.Exit) as excinfo:
        C._emit_refusal("tool.invalid_payload", "bad", {"errors": [{"ctx": {"error": ValueError("boom")}}]})  # type: ignore[arg-type]
    assert excinfo.value.exit_code == 2
    assert "boom" in json.loads(capsys.readouterr().err)["details"]["errors"][0]["ctx"]["error"]


# ---- 一张不转文字的名单 ----------------------------------------------------------------------


def _traditional(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[HorosaSkillService, str]:
    built = _service(tmp_path, output_script=TRADITIONAL)
    monkeypatch.setattr(C, "_service", lambda: built)
    monkeypatch.setattr(C, "_localized", lambda data: localize(data, TRADITIONAL))
    return built, built.run_tool("chart", {**BIRTH, **CONFIRM}).memory_ref.run_id


def test_report_template_is_protocol_on_both_surfaces(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    built, run_id = _traditional(tmp_path, monkeypatch)
    on_cli = json.loads(RUNNER.invoke(C.app, ["report", "template", "--run-id", run_id, "--tool", "chart"]).stdout)
    on_mcp = _mcp_call(built, "horosa_report_template", {"run_id": run_id, "tool_name": "chart"})
    assert on_mcp["ai_fillable"] == on_cli["ai_fillable"], "报告模板是给 AI 的协议，两面都不转（AGENTS §4.5）"


def test_memory_answer_summary_is_for_people_on_both_surfaces(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    built, run_id = _traditional(tmp_path, monkeypatch)
    body = json.dumps({"run_id": run_id, "ai_answer": "解读"})
    on_cli = json.loads(RUNNER.invoke(C.app, ["memory", "answer", "--stdin"], input=body).stdout)
    on_mcp = _mcp_call(built, "horosa_memory_record_answer", {"run_id": run_id, "ai_answer": "解读"})
    assert on_cli["summary"] == on_mcp["summary"] == [convert(line, TRADITIONAL) for line in built.record_ai_answer(json.loads(body))["summary"]]


def test_every_surface_reads_the_one_list() -> None:
    protocol = localize_module.PROTOCOL_OPERATIONS
    assert mcp_runner.UNLOCALIZED_TOOLS == {f"horosa_{name}" for name in protocol}
    assert protocol <= C.UNLOCALIZED_COMMANDS
