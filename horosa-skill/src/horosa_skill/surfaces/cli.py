from __future__ import annotations

import json
import re
import os
import sys
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path
from typing import Any, NoReturn, Optional

import typer

from horosa_skill import clients_extra
from horosa_skill.agent_guidance import build_agent_guidance, validate_agent_preflight
from horosa_skill.config import Settings
from horosa_skill.benchmark import run_benchmark
from horosa_skill.engine.registry import (
    COMPACT_SURFACE_TOOL_COUNT,
    FACADE_TOOL_COUNT,
    TOOL_DEFINITIONS,
    resolve_tool_name,
)
from horosa_skill.errors import RuntimeError, ToolValidationError, bilingual
from horosa_skill.service import HorosaSkillService
from horosa_skill.textscript.localize import PROTOCOL_OPERATIONS
from horosa_skill.tracing import TraceRecorder
from horosa_skill.client_config.audit import (
    _client_check_report,
)
from horosa_skill.client_config.locations import (
    _CLIENT_NAMES,
)
from horosa_skill.client_config.merge import (
    _merge_client_config,
    _write_json_file,
)
from horosa_skill.client_config.openclaw import _build_openclaw_config
from horosa_skill.client_config.payload import (
    _build_client_config_payload,
    _resolve_skill_root,
)
from horosa_skill.surfaces.doctor import (
    STATUS_BUDGET_SECONDS,
    _doctor_report,
    _explain_lines,
)
from horosa_skill.surfaces import openclaw_flow, serve_flow
from horosa_skill.surfaces.refusals import _emit_refusal, _refuse, _write_refusal
from horosa_skill.surfaces.runtime_helpers import (
    _install_progress_printer,
)
from horosa_skill.surfaces.setup_flow import (
    _SetupFailure,
    _run_setup,
    _setup_skill_step,
)
from horosa_skill.surfaces import runtime_helpers


def _utf8_stdio(*streams: Any) -> None:
    """把 stdout / stderr 统一成 UTF-8（已是 UTF-8 的不动）。

    `_print_json` 一直按字节写 UTF-8，但帮助与 stderr 走文本流：管道 / 重定向下 Windows 的文本流是系统 ANSI 代码页（cp1252 / cp936）。
    v0.47.2-dev 实测（cp1252）：60 个命令里 55 个 `--help` 抛 UnicodeEncodeError；stderr 的 JSON 错误信封混着 `\\uXXXX` 与裸 cp1252 字节，
    不是合法 UTF-8——只有 shell 的 agent 按契约读它的 `code` 时直接 UnicodeDecodeError。控制台（已是 UTF-8）不受影响。
    pythonw / 被替换成无 reconfigure 的流时跳过。
    """
    for stream in streams or (sys.stdout, sys.stderr):
        encoding = (getattr(stream, "encoding", None) or "").lower().replace("-", "")
        reconfigure = getattr(stream, "reconfigure", None)
        if encoding != "utf8" and reconfigure is not None:
            reconfigure(encoding="utf-8", errors="backslashreplace")


class _HorosaApp(typer.Typer):
    """所有入口（console script、`python -m horosa_skill`、`python -m horosa_skill.surfaces.cli`）都经 `app()`；CliRunner 不走这里，不碰它的流。"""

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        _utf8_stdio()
        return super().__call__(*args, **kwargs)


app = _HorosaApp(
    help=(
        "Horosa Skill CLI — 本地术数/占星技法工具箱。\n"
        "上手三步：`install`（装离线 runtime）→ `selfcheck`（活体验证）→ `serve`（起 MCP 接 AI 客户端）。\n"
        "客户端注册：`client config --format claude-code|claude-desktop|codex`。\n"
        "Use `ask` / `dispatch` for natural-language orchestration, `tool run` for direct method calls, "
        "and `memory show/query/answer` for local record management. "
        "OpenClaw path: `client openclaw-setup`."
    )
)
tool_app = typer.Typer(help="Direct atomic method calls such as chart, qimen, liureng, and bazi.")
memory_app = typer.Typer(help="Inspect local records, show a single run, or attach the AI's final answer.")
export_app = typer.Typer(help="Inspect the Xingque AI export registry and parse exported text into structured JSON.")
knowledge_app = typer.Typer(help="Read bundled Xingque hover knowledge such as 星盘释义、大六壬地支提示、奇门象意。")
benchmark_app = typer.Typer(help="Run HorosaBench benchmark cases for routing, export parity, and knowledge quality.")
trace_app = typer.Typer(help="Inspect recent local trace records for tool runs, dispatches, and runtime operations.")
client_app = typer.Typer(help="Default OpenClaw entry: `openclaw-setup`. Also generate configs and run smoke checks for OpenClaw / mcporter.")
report_app = typer.Typer(help="Generate structured Horosa reports as JSON, DOCX, or PDF artifacts.")
agent_app = typer.Typer(help="Show agent-safe tool routing and clarification guidance before calculation.")
runtime_app = typer.Typer(help="Inspect and control the local offline runtime: status / start / stop / restart。查看与控制本机 runtime。")
jev_app = typer.Typer(help="Optional cloud decision layer (TypeSafe Jev, HOROSA_JEV): status / local decision ledger。可选云端决策层。")
app.add_typer(tool_app, name="tool")
app.add_typer(memory_app, name="memory")
app.add_typer(export_app, name="export")
app.add_typer(knowledge_app, name="knowledge")
app.add_typer(benchmark_app, name="benchmark")
app.add_typer(trace_app, name="trace")
app.add_typer(client_app, name="client")
app.add_typer(report_app, name="report")
app.add_typer(agent_app, name="agent")
app.add_typer(runtime_app, name="runtime")
app.add_typer(jev_app, name="jev")


@jev_app.command("status")
def jev_status() -> None:
    """Show the decision-layer policy (mode / scope / surfaces / model / thresholds lock). Never prints the key."""
    from horosa_skill.decisions.policy import load_policy, load_thresholds

    settings = Settings.from_env()
    view = load_policy().doctor_view(load_thresholds())
    view["ledger_path"] = str(settings.data_dir / "jev_events.jsonl")
    _print_json(view)


@jev_app.command("events")
def jev_events(
    limit: int = typer.Option(20, help="How many recent decision-ledger rows to print (newest last)."),
) -> None:
    """Tail the local decision ledger (redacted state digests, answers, adoption, latency)."""
    from horosa_skill.decisions.ledger import DecisionLedger

    settings = Settings.from_env()
    ledger = DecisionLedger(settings.data_dir / "jev_events.jsonl")
    _print_json({"path": str(ledger.path), "total": ledger.count(), "events": ledger.tail(max(1, limit))})


def _version_callback(value: bool) -> None:
    if not value:
        return
    try:
        resolved = package_version("horosa-skill")
    except PackageNotFoundError:
        resolved = "unknown"
    typer.echo(f"horosa-skill {resolved}")
    raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        help="Show the installed Horosa Skill package version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Horosa Skill command line entrypoint."""


def _service() -> HorosaSkillService:
    return HorosaSkillService(Settings.from_env())


def _tracer(settings: Settings | None = None) -> TraceRecorder:
    return TraceRecorder(settings or Settings.from_env())


def _refuse_payload(source: str, zh: str, en: str, **details: Any) -> NoReturn:
    _emit_refusal("tool.invalid_payload", bilingual(zh, en), {"source": source, **details})


def _read_payload_text(*, stdin: bool, input_file: Optional[Path]) -> tuple[str, str]:
    """(来源, 文本)。一律按字节读再解 utf-8-sig：Windows PowerShell 5.1 的 `Out-File -Encoding utf8` 写 BOM，而 `--input` 正是给那台机器指的路。"""
    if not stdin and input_file is None:
        raise typer.BadParameter("Provide exactly one of --stdin or --input.")
    source = "stdin" if stdin else str(input_file)
    stream = getattr(sys.stdin, "buffer", None) if stdin else None
    if stdin and stream is None:
        return source, sys.stdin.read()
    try:
        raw = stream.read() if stdin else input_file.read_bytes()
    except OSError as exc:
        _refuse_payload(source, f"读不了输入：{source}（{exc}）", f"Cannot read {source}: {exc}")
    try:
        return source, raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        _refuse_payload(source, f"输入不是 UTF-8：{source}（{exc}）", f"{source} is not UTF-8: {exc}")


def _load_payload(*, stdin: bool, input_file: Optional[Path]) -> dict:
    source, text = _read_payload_text(stdin=stdin, input_file=input_file)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        _refuse_payload(source, f"输入不是合法 JSON：{exc}", f"Invalid JSON payload: {exc}", json_error=str(exc))
    if not isinstance(data, dict):
        _refuse_payload(source, "输入的 JSON 必须是对象。", "Input JSON must be an object.", received_type=type(data).__name__)
    return data


def _load_optional_payload(*, stdin: bool, input_file: Optional[Path]) -> dict:
    if not stdin and input_file is None:
        return {}
    return _load_payload(stdin=stdin, input_file=input_file)


def _emit_json(data: object, output: Optional[Path] = None) -> None:
    """stdout 永远是那份 JSON（agent 契约不变）；`--output` 只是**多**落一份 UTF-8 文件。

    为什么要有文件出口：Windows PowerShell 5.1 把管道里的字节按控制台代码页重编码，agent 用
    `… | horosa-skill tool run --stdin` 再读 stdout 时中文会碎；写文件绕开管道。ci.yml 的 Windows
    smoke 自 v0.30 起就在调 `tool run … --output`，而这个参数直到 v0.38.0 才存在——pwsh 多行 step 只看
    最后一条命令的退出码，所以那一步失败了 N 轮没人看见（docs/LESSONS.md v0.38.0）。
    """
    if output is not None:
        _write_json_file(output, data)
    _print_json(data)


# 打印 JSON 却**不**转文字的命令：给 AI 的协议与注册表（两面共用 textscript.localize.PROTOCOL_OPERATIONS），加上 CLI 独有的
# 诊断 / 配置 / 维护命令。其余打印结果的命令都必须经 `_localized`——tests/test_textscript.py 按 AST 核对，新命令不归类就红。
UNLOCALIZED_COMMANDS = PROTOCOL_OPERATIONS | frozenset({
    "jev_status", "jev_events", "uninstall", "doctor", "setup", "selfcheck", "runtime_status",
    "runtime_start", "runtime_restart", "tool_list", "benchmark_run", "benchmark_faithfulness", "trace_latest",
    "client_check", "client_skill", "client_config", "client_openclaw_config", "client_openclaw_setup", "client_openclaw_check",
    "memory_prune", "knowledge_mine", "knowledge_add", "knowledge_remove", "knowledge_trash", "knowledge_restore",
    "knowledge_index",
})


def _localized(data: object) -> object:
    """结果类命令的输出按 HOROSA_OUTPUT_SCRIPT 转文字（简体时原样返回）；协议类命令（agent / registry / doctor）不经过这里。"""
    from horosa_skill.config import output_script_from_env
    from horosa_skill.textscript.localize import localize

    return localize(data, output_script_from_env())


def _print_json(data: object) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    stream = getattr(sys.stdout, "buffer", None)
    if stream is not None:
        stream.write(text.encode("utf-8"))
        stream.write(b"\n")
        stream.flush()
        return
    typer.echo(text)


def _enforce_agent_preflight(tool_name: str, payload: dict[str, Any]) -> None:
    from horosa_skill.profiles import gate_view

    # 与 MCP 面同一口径：闸门看并进命主档案之后的载荷（档案里有的出生信息不再追问）；认不出的档案名在这里就拒。
    preflight = validate_agent_preflight(tool_name, gate_view(Settings.from_env(), tool_name, payload))
    if preflight.get("ok"):
        return
    raise ToolValidationError(preflight["message"], code=preflight["code"], details=preflight)


def _opt(value: Any, default: Any = None) -> Any:
    """把 typer 的 `OptionInfo` 还原成它承载的默认值。

    🔴 直接以 Python 函数调用一个 typer 命令（测试、以及本模块内部的 `stop` → `runtime stop`
    这类转调）时，未传的形参拿到的是 **OptionInfo 对象**而不是默认值。对象恒真、也没有 `.strip()`，
    于是布尔开关全部按「真」走、字符串参数直接 AttributeError。
    这个陷阱在 v0.37.0 前已经让 `test_streamable_http_serve_stops_runtime_after_exit`
    「因为错误的原因通过」了很久：它断言的停机分支其实是被 `bool(OptionInfo)` 打开的。
    """
    if type(value).__name__ in {"OptionInfo", "ArgumentInfo"}:
        inner = getattr(value, "default", None)
        if inner is None or inner is Ellipsis:
            return default
        return inner
    return value


_ENTRY_HELP = (
    "How the config starts the server: auto（缺省：Windows 开着 Smart App Control 时用 module，否则 script）/ "
    "script（`horosa-skill serve`）/ module（`python -m horosa_skill serve`——uv 现生成的 horosa-skill.exe 被应用控制拦下"
    "（os error 4551）时用它，功能相同）。"
)


def _run_install(archive: str | None, manifest_url: str | None, force: bool, *, mode: str) -> None:
    settings = Settings.from_env()
    manager = runtime_helpers._runtime_manager(settings)
    typer.echo("正在解析 runtime 版本与资产…（约 730MB 下载、解压后约 2GB，请留足磁盘）", err=True)
    try:
        result = manager.install(archive=archive, manifest_url=manifest_url, force=force, progress=_install_progress_printer())
    except RuntimeError as exc:
        _refuse(exc)
    except OSError as exc:
        # 磁盘满 / 权限不足 / 跨卷等 IO 失败：结构化输出而非裸 traceback。
        _emit_refusal("runtime.install_io_error", str(exc))
    if mode == "upgrade":
        result["mode"] = "upgrade"
    _print_json(result)


@app.command(help="Install the offline runtime (~730MB download; resumable, mirror-aware). 安装离线 runtime（断点续传/多镜像）。")
def install(
    archive: str | None = typer.Option(None, help="Local archive path or URL to a runtime asset."),
    manifest_url: str | None = typer.Option(None, help="Release manifest URL that maps platforms to runtime archives."),
    force: bool = typer.Option(False, help="Reinstall even if the same runtime version is already present."),
) -> None:
    _run_install(archive, manifest_url, force, mode="install")


@app.command(help="Version-aware install alias: skips the 730MB download when already up to date. 升级（已最新则秒退）。")
def upgrade(
    manifest_url: str | None = typer.Option(None, help="Release manifest URL that maps platforms to runtime archives."),
    force: bool = typer.Option(False, help="Reinstall even if the same runtime version is already present."),
) -> None:
    _run_install(None, manifest_url, force, mode="upgrade")


@app.command(help="Uninstall the offline runtime (dry-run by default; --yes to execute). 卸载 runtime（默认只打印将删清单）。")
def uninstall(
    purge_data: bool = typer.Option(False, "--purge-data", help="Also delete user data (memory.db / runs / traces / reports). Your knowledge folder and its trash are KEPT unless --purge-knowledge is also given; saved birth profiles are KEPT unless --purge-profiles. 同时删除用户数据（不可恢复；自备知识库与命主档案默认保留）。"),
    purge_knowledge: bool = typer.Option(False, "--purge-knowledge", help="With --purge-data: also delete your own knowledge notes and their trash. 连自备知识库一起删（不可恢复）。"),
    purge_profiles: bool = typer.Option(False, "--purge-profiles", help="With --purge-data: also delete your saved birth profiles (horosa_profile). 连命主档案一起删（不可恢复）。"),
    yes: bool = typer.Option(False, "--yes", help="Actually delete. Without this flag only the removal plan is printed."),
) -> None:
    settings = Settings.from_env()
    manager = runtime_helpers._runtime_manager(settings)
    try:
        result = manager.uninstall(purge_data=purge_data, purge_knowledge=purge_knowledge, purge_profiles=purge_profiles, yes=yes)
    except RuntimeError as exc:
        _refuse(exc)
    _print_json(result)


@app.command(help='Environment check: runtime install, ports, disk, node probe, client hints (JSON; `issues: []` = healthy). 环境体检（JSON）。')
def doctor(
    explain: bool = typer.Option(False, "--explain", help="Also print 6–10 lines of plain-language explanation to stderr (stdout stays pure JSON)."),
    probe_network: bool = typer.Option(False, "--probe-network", help="HEAD the runtime manifest URL through every mirror and report reachability (default: no external request)."),
) -> None:
    settings = Settings.from_env()
    report = _doctor_report(settings, runtime_helpers._runtime_manager(settings), probe_network=bool(_opt(probe_network, False)))
    if _opt(explain, False):
        for line in _explain_lines(report):
            typer.echo(line, err=True)
    _print_json(report)


@app.command(
    help=(
        "One command onboarding for any MCP client: probe network → install runtime → write the client config "
        "(backup + atomic) → doctor → re-read check → real stdio probe. 一条命令接入任意 AI 客户端。"
    )
)
def setup(
    client: str = typer.Option(
        ..., "--client",
        help="Target client: claude-code / claude-desktop / cursor / vscode / codex / gemini / windsurf / cline / zed / "
             + " / ".join(clients_extra.EXTRA_CLIENTS) + ".",
    ),
    launcher: str | None = typer.Option(
        None, "--launcher",
        help="uv（源码 checkout 内默认）/ uvx-wheel（零安装，其余情况默认）/ uvx-git / uvx。",
    ),
    surface: str = typer.Option("auto", "--surface", help="auto（按客户端上限）/ full / compact。"),
    output_script: str = typer.Option(
        "zh-Hans",
        "--output-script",
        help="结果文字：zh-Hans（简体，缺省）/ zh-Hant（繁体·台湾字形）/ zh-Hant-HK（繁体·香港字形）。写进客户端配置的 HOROSA_OUTPUT_SCRIPT；重跑 setup 不带它就回到简体。",
    ),
    entry: str = typer.Option(
        "auto", "--entry",
        help=_ENTRY_HELP,
    ),
    config: Path | None = typer.Option(None, "--config", help="Write this file instead of the client's default location."),
    scope: str = typer.Option(
        "auto", "--scope",
        help="claude-code only: auto（CWD 有 .mcp.json 则项目级，否则 `claude mcp add --scope user`）/ project / user。",
    ),
    server_name: str = typer.Option("horosa", help="Server name key written into the client config."),
    skill_root: Path | None = typer.Option(None, help="horosa-skill package dir or repo root (uv launcher only)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan only: no download, no write, no process spawned."),
    skip_install: bool = typer.Option(False, "--skip-install", help="Do not install / upgrade the offline runtime."),
    archive: str | None = typer.Option(None, "--archive", help="Local archive path or URL for the runtime (offline install)."),
    manifest_url: str | None = typer.Option(None, "--manifest-url", help="Release manifest URL (default: latest GitHub release, mirror-aware)."),
    probe_network: bool = typer.Option(True, "--probe-network/--no-probe-network", help="HEAD the manifest URL (5 s) before downloading."),
    stdio_probe: bool = typer.Option(
        True, "--stdio-probe/--no-stdio-probe",
        help="Start the server once over stdio with the exact client command and count the tools.",
    ),
    write: bool = typer.Option(True, "--write/--no-write", help="Write the client config (default) or only print the block."),
    cache_wheel: bool = typer.Option(
        True, "--cache-wheel/--no-cache-wheel",
        help="uvx-wheel launcher only: pre-download the wheel to ~/.horosa/wheels and write that local path (offline-capable cold start).",
    ),
    skill: bool = typer.Option(
        True, "--skill/--no-skill",
        help="Also install the horosa-agent skill (rules: clarify-before-call, read the export snapshot, never hand-calculate) "
             "into the skills folder this client reads (~/.agents/skills or the client's own).",
    ),
    skill_dir: Path | None = typer.Option(
        None, "--skill-dir", help="Install the skill into this skills folder instead (the skill lands in <dir>/horosa-agent).",
    ),
    vectors: bool | None = typer.Option(
        None, "--vectors/--no-vectors",
        help="Optional vector search over your notes: install onnxruntime + tokenizers + numpy (~128 MB) into the environment "
             "the client starts the server in, download + verify the bge-small-zh model (24 MB) and embed the notes, all before "
             "the config is written. Omitted: kept on if the model is already on this machine. 可选向量检索（换了说法也能搜到）。",
    ),
) -> None:
    try:
        report = _run_setup(
            client=client, launcher=launcher, surface=surface, config=config, scope=scope, server_name=server_name,
            output_script=str(_opt(output_script, "zh-Hans")), entry=str(_opt(entry, "auto")),
            skill_root=skill_root, dry_run=dry_run, skip_install=skip_install, archive=archive, manifest_url=manifest_url,
            probe_network=probe_network, stdio_probe=stdio_probe, write=write, cache_wheel=cache_wheel,
            skill=skill, skill_dir=skill_dir, vectors=vectors,
        )
    except _SetupFailure as failure:
        _write_refusal(failure.payload)
    _print_json(report)
    if not report["ok"]:
        raise typer.Exit(code=2)


@app.command(help="Client-agnostic live check: cast one chart, store it, read it back. 活体体检（起一张盘→存→读回）。")
def selfcheck() -> None:
    settings = Settings.from_env()
    manager = runtime_helpers._runtime_manager(settings)
    report: dict[str, Any] = {"ok": False, "steps": {}}
    try:
        doctor_report = manager.doctor()
        report["steps"]["doctor"] = {"ok": not doctor_report.get("issues"), "issues": doctor_report.get("issues", [])}
        # 🔴 v0.38.1 R11：工具路径只为「等 runtime 起来」阻塞 5 s（HOROSA_RUNTIME_CALL_WAIT_SECONDS），够覆盖
        # 「已经起好、探针慢一拍」，不够一次冷启动。`setup` 之后紧跟 `selfcheck` 在每个平台上都会以
        # runtime.starting 退出 1 —— 用户看到的是「刚装完就坏了」。selfcheck 是活体体检，先用**全预算**把
        # runtime 拉起来（外部模式 / 已可达时跳过），再做探针。
        endpoints = doctor_report.get("endpoints") or []
        all_reachable = bool(endpoints) and all(item.get("reachable") for item in endpoints)
        if doctor_report.get("installed") and manager.runtime_mode() != "external" and not all_reachable:
            started = manager.start_local_services()
            report["steps"]["start"] = {
                "ok": bool(started.get("ok")),
                "starting": bool(started.get("starting")),
                "already_running": bool(started.get("already_running")),
                "budget_seconds": settings.runtime_start_timeout_seconds,
            }
        service = HorosaSkillService(settings, runtime_manager=manager)
        result = service.run_tool(
            "nongli_time",
            {
                "date": "2028-04-06",
                "time": "09:33:00",
                "zone": "+08:00",
                "lon": "121e28",
                "lat": "31n13",
                "agent_confirmed_settings": True,
            },
            query_text="selfcheck 活体体检",
        )
        report["steps"]["compute"] = {"ok": result.ok, "tool": "nongli_time", "error": result.error.model_dump(mode="json") if result.error else None}
        probe_result = result
        if not result.ok:
            # Issue #14: nongli_time 走 Java 后端(:9999)；Java 被环境杀死（如 WFP 拦 JDK-17 loopback）时
            # 不能让整个 selfcheck 挂死 —— 改用 chart 侧 kentang 的 wangji 证明 chart 半边活着（降级可用）。
            fallback = service.run_tool(
                "wangji",
                {
                    "date": "1998-02-20",
                    "time": "20:48:00",
                    "after23NewDay": 1,
                    "agent_confirmed_settings": True,
                    "clarification_notes": "selfcheck degraded chart-only probe",
                },
                query_text="selfcheck 降级 chart-only 活体体检",
            )
            report["steps"]["compute_chart_only_fallback"] = {
                "ok": fallback.ok,
                "tool": "wangji",
                "error": fallback.error.model_dump(mode="json") if fallback.error else None,
            }
            if fallback.ok:
                report["degraded"] = "chart_only"
                probe_result = fallback
        run_id = probe_result.memory_ref.run_id if probe_result.memory_ref else None
        shown = service.show_memory({"run_id": run_id}) if run_id else {"ok": False}
        report["steps"]["memory_roundtrip"] = {"ok": bool(shown.get("ok")), "run_id": run_id}
        report["ok"] = bool(probe_result.ok and shown.get("ok"))
        if report.get("degraded") == "chart_only":
            report["next_action"] = (
                "降级可用（chart-only）：Java 后端(:9999)未就绪，nongli/bazi/ziwei/liureng 与占时起课暂不可用；"
                "chart 侧技法（三式 ken/神数/地占/塔罗/西占 chart 族）可正常 `serve` 使用。"
                "跑 `uv run horosa-skill doctor` 看 java_diagnostics 里捕获的 Java 启动错误；"
                "Windows 已知诱因 = 代理/VPN/安全软件的 WFP 过滤拦截 JDK-17 loopback（issue #14）。"
            )
        else:
            report["next_action"] = (
                "全部通过：可以 `serve` 并接入 AI 客户端。" if report["ok"]
                else "有步骤失败：按 steps 中的 error/issues 排查，或运行 `uv run horosa-skill doctor` 看完整体检。"
            )
    except RuntimeError as exc:
        report["steps"]["error"] = {"code": exc.code, "message": str(exc), "details": exc.details}
        if exc.code in {"runtime.not_installed", "runtime.platform_unsupported"}:
            # 修复命令按安装上下文生成（checkout / wheel / 插件 / MCPB），平台死胡同直接给网关出路。
            report["next_action"] = str(exc.details.get("next_action") or "运行 `uv run horosa-skill install` 安装离线 runtime 后重试。")
        else:
            report["next_action"] = "运行 `uv run horosa-skill doctor` 定位。"
    _print_json(report)
    if not report["ok"]:
        raise typer.Exit(code=1)


@app.command(help="Alias of `runtime stop`. 停止本机 runtime（等同 `runtime stop`）。")
def stop(
    force: bool = typer.Option(False, "--force", help="Stop even when the services were not started by this tool."),
) -> None:
    _runtime_stop_impl(force=bool(_opt(force, False)))


def _runtime_stop_impl(*, force: bool) -> None:
    settings = Settings.from_env()
    manager = runtime_helpers._runtime_manager(settings)
    try:
        result = manager.stop_local_services(force=force)
    except RuntimeError as exc:
        _refuse(exc)
    _print_json(result)
    if result.get("refused"):
        raise typer.Exit(code=2)


@runtime_app.command("status", help="What is running, on which ports, started by whom. 谁在跑、跑在哪个端口、是谁起的。")
def runtime_status() -> None:
    """永远 exit 0：这是**诊断**命令，「没在跑」是一个正常答案而不是错误。"""
    from horosa_skill.runtime.pidlock import describe_lock
    from horosa_skill.runtime.registry import live_clients

    settings = Settings.from_env()
    manager = runtime_helpers._runtime_manager(settings)
    installed = settings.runtime_current_dir.exists()
    manifest = manager.load_installed_manifest() if installed else None
    state = manager.load_runtime_state() or {}
    from horosa_skill.runtime import budget as _budget

    with _budget.scope(STATUS_BUDGET_SECONDS) as status_budget:
        endpoints = manager.endpoint_identities() if installed else []
    report: dict[str, Any] = {
        "ok": True,
        "installed": installed,
        "mode": manager.runtime_mode(),
        "runtime_root": str(settings.runtime_root),
        "runtime_version": (manifest or {}).get("version"),
        "platform": (manifest or {}).get("platform"),
        "ports": {
            "backend": settings.local_backend_port,
            "chart": settings.local_chart_port,
            "source": settings.settings_provenance.get("local_backend_port", "default"),
        },
        "endpoints": endpoints,
        "registry_status": state.get("status"),
        "launcher": state.get("launcher") or None,
        "clients": live_clients(state),
        "start_lock": describe_lock(settings.runtime_root / ".runtime-start.lock"),
        "launcher_log": str(settings.runtime_root / manager.LAUNCHER_LOG_NAME),
        "budget": status_budget.as_dict(),
    }
    reachable = [item for item in endpoints if item.get("reachable")]
    if not installed:
        report["summary"] = "runtime 未安装 —— 运行 `horosa-skill install`。"
    elif report["mode"] == "external":
        report["summary"] = "外部模式：地址已显式指向别处，本工具不会在本机启动或停止任何服务。"
    elif len(reachable) == len(endpoints) and endpoints:
        owners = {(item.get("identity") or {}).get("evidence") for item in reachable}
        report["summary"] = f"全部服务在跑（归属证据：{', '.join(sorted(o for o in owners if o))}）。"
    elif state.get("status") == "starting":
        report["summary"] = "正在启动 —— 看 launcher_log 跟进度。"
    elif reachable:
        report["summary"] = "只有一部分服务在跑（Java 起不来时属正常降级；chart 族技法仍可用）。"
    else:
        report["summary"] = "没有服务在跑 —— 运行 `horosa-skill runtime start`。"
    _print_json(report)


@runtime_app.command("start", help="Start the local runtime. 启动本机 runtime。")
def runtime_start(
    wait: float = typer.Option(
        None, "--wait", help="Max seconds to block (default: the full startup budget). 最多阻塞多少秒。"
    ),
    no_wait: bool = typer.Option(False, "--no-wait", help="Return immediately with `starting`. 立即返回。"),
) -> None:
    settings = Settings.from_env()
    manager = runtime_helpers._runtime_manager(settings)
    wait = _opt(wait)
    budget = 0.0 if bool(_opt(no_wait, False)) else wait
    try:
        result = manager.start_local_services(wait_seconds=budget)
    except RuntimeError as exc:
        _refuse(exc)
    _print_json(result)


@runtime_app.command("stop", help="Stop the local runtime. 停止本机 runtime（只停本工具起的那份）。")
def runtime_stop(
    force: bool = typer.Option(False, "--force", help="Stop even when the services were not started by this tool."),
) -> None:
    _runtime_stop_impl(force=bool(_opt(force, False)))


@runtime_app.command("restart", help="Stop then start. 重启（先停后起）。")
def runtime_restart(
    force: bool = typer.Option(False, "--force", help="Stop even when the services were not started by this tool."),
    wait: float = typer.Option(None, "--wait", help="Max seconds to block on the start half."),
) -> None:
    settings = Settings.from_env()
    manager = runtime_helpers._runtime_manager(settings)
    try:
        # restart = 服务马上回来：挂着的客户端不拦（它们下一次调用只见一次 runtime.starting 然后自动重试）。
        stopped = manager.stop_local_services(force=force, ignore_clients=True)
        if stopped.get("refused"):
            _print_json({"ok": False, "phase": "stop", **stopped})
            raise typer.Exit(code=2)
        started = manager.start_local_services(wait_seconds=wait)
    except RuntimeError as exc:
        _refuse(exc)
    _print_json({"ok": True, "stopped": stopped, "started": started})


@app.command(help='Start the MCP server: `--transport stdio` for a client that launches it, streamable-http (default, http://127.0.0.1:8765/mcp) for remote/HTTP clients. 启动 MCP 服务。')
def serve(
    transport: str = typer.Option(
        "streamable-http",
        help="MCP transport: streamable-http | stdio | sse (legacy). 传输方式。",
    ),
    host: str = typer.Option(None, help="Host for streamable HTTP (default: HOROSA_SKILL_HOST or 127.0.0.1)."),
    port: int = typer.Option(None, help="Port for streamable HTTP (default: HOROSA_SKILL_PORT or 8765)."),
    token: str = typer.Option(
        None, "--token",
        help="Shared bearer token required on every request (or HOROSA_MCP_TOKEN). 共享访问令牌。",
    ),
    allow_unauthenticated: bool = typer.Option(
        False, "--allow-unauthenticated",
        help="Bind to a non-loopback address without a token (you accept the exposure). 明知无鉴权仍对外绑定。",
    ),
    skip_runtime_start: bool = typer.Option(False, help="Do not auto-start the installed offline runtime."),
    stop_runtime_on_exit: bool = typer.Option(
        False,
        "--stop-runtime-on-exit",
        help="Stop the offline runtime when this server exits (default: keep it warm). 退出时顺带停掉 runtime。",
    ),
) -> None:
    # 直接函数调用时 typer 不做默认值解析，见 _opt 的说明。
    serve_flow._run_serve(
        transport=_opt(transport, "streamable-http"),
        host=_opt(host),
        port=_opt(port),
        token=_opt(token),
        allow_unauthenticated=bool(_opt(allow_unauthenticated, False)),
        skip_runtime_start=bool(_opt(skip_runtime_start, False)),
        stop_runtime_on_exit=bool(_opt(stop_runtime_on_exit, False)),
    )


@tool_app.command("list", help='List all techniques as JSON: registry name, MCP name, description, input contract with an example payload. 列出全部技法。')
def tool_list() -> None:
    _print_json(_service().list_tools())


@tool_app.command("run", help='Run one technique: `tool run <name> --input in.json [--output out.json]`; exit 0 = envelope written (check `ok`), 2 = refused before running (stderr JSON `code`). 直调一个技法。')
def tool_run(
    tool_name: str = typer.Argument(
        ...,
        help="Technique name: registry key (chart) or MCP name (horosa_astro_chart); `tool list` shows all. 技法名，两种写法都收。",
    ),
    stdin: bool = typer.Option(False, "--stdin", help="Read a JSON object from stdin."),
    input_file: Optional[Path] = typer.Option(None, "--input", help="Read a JSON object from a file."),
    save_result: bool = typer.Option(True, help="Persist the result in local memory."),
    query_text: str | None = typer.Option(None, help="Optional original user question to store together with this run."),
    output: Optional[Path] = typer.Option(None, "--output", help="Also write the JSON envelope to this UTF-8 file (stdout keeps printing it)."),
) -> None:
    payload = _load_payload(stdin=stdin, input_file=input_file)
    service = _service()
    try:
        # chart 与 horosa_astro_chart 都收；必须在闸门前归一（闸门只拦已登记的名字）。
        resolved = resolve_tool_name(tool_name)
        if resolved is None:
            from horosa_skill.agent_guidance import unknown_tool_details

            raise ToolValidationError(
                bilingual(f"未知技法：{tool_name}", f"Unknown tool: {tool_name}"),
                code="tool.unknown",
                details=unknown_tool_details(tool_name),
            )
        _enforce_agent_preflight(resolved, payload)
        result = service.run_tool(resolved, payload, save_result=save_result, query_text=query_text)
    except ToolValidationError as exc:
        _refuse(exc)
    _emit_json(_localized(result.model_dump(mode="json")), output)


@agent_app.command("guidance")
def agent_guidance(
    tool_name: str | None = typer.Option(None, "--tool", help="Tool name or MCP tool name, such as liureng_gods or horosa_cn_liureng_gods."),
    intent: str | None = typer.Option(None, "--intent", help="Optional user intent text to echo back in the guidance payload."),
    include_all: bool = typer.Option(False, "--all", help="Return guidance for every registered calculation/export tool."),
) -> None:
    """Return machine-readable guidance that tells agents what to ask before tool calls."""

    _print_json(build_agent_guidance(tool_name=tool_name, intent=intent, include_all=include_all))


@export_app.command("registry", help='Show the 星阙 AI export registry (sections and settings per technique). 导出设置注册表。')
def export_registry(
    technique: str | None = typer.Option(None, help="Return only one technique block."),
    save_result: bool = typer.Option(False, help="Persist the result in local memory."),
) -> None:
    service = _service()
    result = service.run_tool("export_registry", {"technique": technique} if technique else {}, save_result=save_result)
    _print_json(result.model_dump(mode="json"))


@export_app.command("parse", help='Parse exported snapshot text into structured sections: JSON {technique, content}. 解析导出快照文本。')
def export_parse(
    stdin: bool = typer.Option(False, "--stdin", help="Read a JSON object from stdin."),
    input_file: Optional[Path] = typer.Option(None, "--input", help="Read a JSON object from a file."),
    save_result: bool = typer.Option(False, help="Persist the result in local memory."),
) -> None:
    payload = _load_payload(stdin=stdin, input_file=input_file)
    service = _service()
    try:
        result = service.run_tool("export_parse", payload, save_result=save_result)
    except ToolValidationError as exc:
        _refuse(exc)
    _print_json(result.model_dump(mode="json"))


@knowledge_app.command("registry", help='List the bundled knowledge base: every domain with its categories and keys. 列出知识库全部域 / 分类 / 键。')
def knowledge_registry(
    domain: str | None = typer.Option(None, help="Optional domain filter, e.g. astro, bazi, qimen, liureng (omit to list every domain)."),
    save_result: bool = typer.Option(False, help="Persist the result in local memory."),
) -> None:
    service = _service()
    result = service.run_tool("knowledge_registry", {"domain": domain} if domain else {}, save_result=save_result)
    _print_json(result.model_dump(mode="json"))


@knowledge_app.command("read", help='Read cited knowledge: JSON {domain, category, key} for one entry, or {query} for full-text search. 读知识条目（逐条带出处）。')
def knowledge_read(
    stdin: bool = typer.Option(False, "--stdin", help="Read a JSON object from stdin."),
    input_file: Optional[Path] = typer.Option(None, "--input", help="Read a JSON object from a file."),
    save_result: bool = typer.Option(False, help="Persist the result in local memory."),
) -> None:
    payload = _load_payload(stdin=stdin, input_file=input_file)
    service = _service()
    try:
        result = service.run_tool("knowledge_read", payload, save_result=save_result)
    except ToolValidationError as exc:
        _refuse(exc)
    _print_json(_localized(result.model_dump(mode="json")))


@knowledge_app.command("search")
def knowledge_search(
    query: str = typer.Argument(..., help="Words separated by spaces; two-character Chinese terms work, 繁/简 match each other."),
    domain: Optional[str] = typer.Option(None, help='Optional filter: "user" = only your own notes, or one bundled domain (e.g. bazi, qimen).'),
    limit: int = typer.Option(8, help="Max matches to return (1-20)."),
    offset: int = typer.Option(0, help="Skip this many matches (page with next_offset)."),
) -> None:
    """Search bundled knowledge AND your own notes; every match carries a score, a citation and how to read it in full.
    Doubles as the retrieval test (like RAGFlow / Dify hit testing): see which passages a query would bring. 检索（兼检索测试）。"""
    payload: dict[str, Any] = {"query": query, "limit": limit, "offset": offset}
    if domain:
        payload["domain"] = domain
    try:
        result = _service().knowledge_search(payload)
    except ToolValidationError as exc:
        _refuse(exc)
    _print_json(_localized({"ok": True, **result}))


@knowledge_app.command("index", help="Show (or --rebuild) the search index of your own notes: entries, passages, engine. 自备知识库检索索引的状态 / 重建。")
def knowledge_index(
    rebuild: bool = typer.Option(False, "--rebuild", help="Throw the index away and rebuild it from the notes folder (the notes are never touched)."),
    vectors_on: bool = typer.Option(False, "--vectors", help="Download + verify the bge-small-zh model (24 MB, pinned sha256) and embed every passage. Needs the [vectors] extra in THIS environment; to turn vector search on for an MCP client use `setup --client <client> --vectors`."),
) -> None:
    from horosa_skill.knowledge import index as kindex
    from horosa_skill.knowledge import user as user_knowledge
    from horosa_skill.knowledge import vectors

    settings = Settings.from_env()
    path = kindex.index_path(settings)
    if vectors_on:
        if not vectors.deps_available():
            _print_json({"ok": False, "code": "knowledge.vectors_missing_deps", "vectors": vectors.status(settings)})
            raise typer.Exit(code=2)
        try:
            vectors.download(settings)
        except Exception as exc:  # noqa: BLE001 - 下载 / 校验失败照实报告，索引照旧可用（纯 BM25）
            _print_json({"ok": False, "code": "knowledge.vectors_download_failed",
                         "message": f"{type(exc).__name__}: {exc}", "vectors": vectors.status(settings)})
            raise typer.Exit(code=2) from exc
    if rebuild and path.exists():
        path.unlink()  # 索引是派生数据，删了照笔记重建；笔记文件夹从不动
    catalog = user_knowledge.indexed_catalog(settings, rebuild=rebuild, embed_all=vectors_on)
    _print_json({
        "ok": True, "dir": str(catalog.root), "index": str(path), "entries": len(catalog.entries),
        "engine": user_knowledge._engine(settings, catalog), "sync": catalog.index_report,
        "vectors": vectors.status(settings),
        "problems": [p.as_dict() for p in catalog.problems if p.kind == "index"],
    })


def _split_option(value: Optional[str]) -> list[str]:
    return [item.strip() for item in re.split(r"[,，、]", value or "") if item.strip()]


@knowledge_app.command("mine", help="List your own knowledge entries (the folder you can drop .md / .txt files into) and any files that could not be read. 列出自备知识库（含读不了的文件与原因）。")
def knowledge_mine() -> None:
    from horosa_skill.knowledge import user as user_knowledge

    _print_json({
        "ok": True,
        **user_knowledge.overview(Settings.from_env(), limit=10_000),
        "how_to_use": "计算时传 knowledge=[条目 id / 标题 / #标签 / auto]；往这个文件夹放 .md / .txt 即可新增（可选 front matter：title / techniques / tags）。problems 是没能读入的文件与原因；trash 是回收站件数（`knowledge trash`）。",
    })


@knowledge_app.command("add", help="Add a note to your own knowledge base (from a file or --text). 往自备知识库加一条。")
def knowledge_add(
    entry_id: str = typer.Argument(..., help="Entry name; may contain folder levels, e.g. 八字/滴天髓笔记."),
    source: Optional[Path] = typer.Option(None, "--file", help="Read the entry text from this file (UTF-8 / UTF-16 / GB18030)."),
    text: Optional[str] = typer.Option(None, "--text", help="Entry text given inline."),
    title: Optional[str] = typer.Option(None, help="Display title (defaults to the entry name, or the existing title when overwriting)."),
    techniques: Optional[str] = typer.Option(None, help="Comma-separated tools / techniques / domains / Chinese technique names that `knowledge=auto` should pick this for, e.g. bazi,ziwei_birth,八字; `*` = all."),
    tags: Optional[str] = typer.Option(None, help="Comma-separated tags, selectable as `#tag`."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Replace an existing entry with the same name (the old version goes to the trash)."),
) -> None:
    from horosa_skill.knowledge import user as user_knowledge

    if (source is None) == (text is None):
        raise typer.BadParameter("give exactly one of --file or --text")
    if source is not None:
        try:
            raw = source.read_bytes()
        except OSError as exc:
            _refuse(ToolValidationError(bilingual(f"读不了文件：{source}（{exc}）", f"Cannot read {source}: {exc}"),
                                                 code="knowledge.user_unreadable", details={"file": str(source)}))
        decoded = user_knowledge.decode_bytes(raw)
        if decoded is None:
            _refuse(ToolValidationError(
                bilingual(f"{source} 不是 UTF-8 / UTF-16 / GB18030 文本", f"{source} is not UTF-8 / UTF-16 / GB18030 text"),
                code="knowledge.user_unreadable", details={"file": str(source)}))
        body = decoded[0]
    else:
        body = str(text)
    try:
        entry = user_knowledge.add_entry(
            Settings.from_env(), text=body, entry_id=entry_id, title=title,
            techniques=_split_option(techniques) if techniques is not None else None,
            tags=_split_option(tags) if tags is not None else None, overwrite=bool(_opt(overwrite, False)),
        )
    except ToolValidationError as exc:
        _refuse(exc)
    _print_json({"ok": True, "entry": entry.summary(), "path": str(entry.path)})


@knowledge_app.command("remove", help="Move one entry to the knowledge trash (by id, file name or unique title; `knowledge restore` brings it back). 删除一条（进回收站，可恢复）。")
def knowledge_remove(entry_id: str = typer.Argument(..., help="Entry id, file name or unique title (`knowledge mine` lists them).")) -> None:
    from horosa_skill.knowledge import user as user_knowledge

    try:
        removed = user_knowledge.remove_entry(Settings.from_env(), entry_id)
    except ToolValidationError as exc:
        _refuse(exc)
    _print_json({"ok": True, "removed": removed["path"], **removed,
                 "restore": f"horosa-skill knowledge restore {removed['trash_id']}"})


@knowledge_app.command("trash", help="List the knowledge trash (removed and overwritten versions, newest first). 列出知识库回收站。")
def knowledge_trash() -> None:
    from horosa_skill.knowledge import user as user_knowledge

    settings = Settings.from_env()
    items = user_knowledge.list_trash(settings)
    _print_json({"ok": True, "dir": str(user_knowledge.trash_dir(settings)), "count": len(items), "items": items})


@knowledge_app.command("restore", help="Put a trashed entry back where it was. 从回收站放回一条。")
def knowledge_restore(
    trash_id: str = typer.Argument(..., help="trash_id from `knowledge trash` (or from the remove result)."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Replace a file now at that path (it goes to the trash first)."),
) -> None:
    from horosa_skill.knowledge import user as user_knowledge

    try:
        restored = user_knowledge.restore_entry(Settings.from_env(), trash_id, overwrite=bool(_opt(overwrite, False)))
    except ToolValidationError as exc:
        _refuse(exc)
    _print_json({"ok": True, **restored})


@app.command(help="Saved birth profiles on this machine: `profile list [--detail]` / `profile get <name>` / `profile save <name> --input data.json` / `profile delete <name>`. 命主档案（存了以后技法载荷带 profile=名字 即可）。")
def profile(
    action: str = typer.Argument(..., help="save | get | list | delete"),
    name: Optional[str] = typer.Argument(None, help="Profile name or alias (save / get / delete)."),
    stdin: bool = typer.Option(False, "--stdin", help="save: read the data object (date/time/zone/lat/lon/gender/ad/timeAlg + aliases/place/notes) from stdin."),
    input_file: Optional[Path] = typer.Option(None, "--input", help="save: read the data object from a JSON file."),
    detail: bool = typer.Option(False, "--detail", help="list: include each profile's birth fields."),
) -> None:
    from horosa_skill.profiles import ProfileStore, run_action

    body: dict[str, Any] = {"action": action, "name": name, "detail": bool(_opt(detail, False)) or None}
    if stdin or input_file is not None:
        body["data"] = _load_payload(stdin=stdin, input_file=input_file)
    try:
        result = run_action(ProfileStore(Settings.from_env()), body)
    except ToolValidationError as exc:
        _refuse(exc)
    _print_json(result)


@app.command(help='Natural-language routing: JSON {query, birth|subject|flat birth fields, …} → picks and runs the right techniques. 自然语言路由起盘。')
def dispatch(
    stdin: bool = typer.Option(False, "--stdin", help="Read a JSON object from stdin."),
    input_file: Optional[Path] = typer.Option(None, "--input", help="Read a JSON object from a file."),
    output: Optional[Path] = typer.Option(None, "--output", help="Also write the JSON envelope to this UTF-8 file (stdout keeps printing it)."),
) -> None:
    payload = _load_payload(stdin=stdin, input_file=input_file)
    service = _service()
    try:
        _enforce_agent_preflight("dispatch", payload)
        result = service.dispatch(payload)
    except ToolValidationError as exc:
        _refuse(exc)
    _emit_json(_localized(result.model_dump(mode="json")), output)


@app.command(help="Friendly alias of `dispatch` for natural-language use.")
def ask(
    stdin: bool = typer.Option(False, "--stdin", help="Read a JSON object from stdin."),
    input_file: Optional[Path] = typer.Option(None, "--input", help="Read a JSON object from a file."),
    output: Optional[Path] = typer.Option(None, "--output", help="Also write the JSON envelope to this UTF-8 file (stdout keeps printing it)."),
) -> None:
    dispatch(stdin=stdin, input_file=input_file, output=output)


@benchmark_app.command("run", help='Run HorosaBench (router, knowledge, per-tool export contract and faithfulness cases). 运行基准评测。')
def benchmark_run(
    dataset: Optional[Path] = typer.Option(None, help="Optional benchmark dataset JSON path."),
    skip_runtime: bool = typer.Option(False, help="Skip runtime-backed cases and run only local knowledge / metadata checks."),
    save_result: bool = typer.Option(False, help="Persist benchmark tool outputs into the local record layer."),
    hermetic: bool = typer.Option(False, "--hermetic", help="可复现模式：剥除白名单外全部 HOROSA_* env（本机旗标不再左右结论），报告记录剥了什么。"),
) -> None:
    settings = Settings.from_env()
    report = run_benchmark(settings=settings, dataset_path=dataset, skip_runtime=skip_runtime, save_result=save_result, hermetic=hermetic)
    _print_json(report)


@app.command(help="合参：一问多技法交叉印证，产出合参模板（分歧必须披露）。Cross-technique synthesis template.")
def hecan(
    query: str = typer.Option(..., "--query", help="用户的问题（路由据此选盘，除非显式 --tool）。"),
    tool: list[str] = typer.Option([], "--tool", help="显式指定技法（可重复），缺省由路由选。"),
    max_tools: int = typer.Option(5, "--max-tools", help="最多同时起几个技法。"),
    stdin: bool = typer.Option(False, "--stdin", help="Read birth/subject JSON from stdin."),
    input_file: Optional[Path] = typer.Option(None, "--input", help="Read birth/subject JSON from a file."),
    output: Optional[Path] = typer.Option(None, "--output", help="Also write the JSON result to this UTF-8 file (stdout keeps printing it)."),
) -> None:
    payload = _load_optional_payload(stdin=stdin, input_file=input_file)
    payload.update({"query": query, "max_tools": max_tools})
    if tool:
        payload["tools"] = list(tool)
    service = _service()
    try:
        _enforce_agent_preflight("hecan", payload)
        result = service.hecan(payload)
    except ToolValidationError as exc:
        _refuse(exc)
    _emit_json(_localized(result), output)


@benchmark_app.command("faithfulness", help="盘面事实忠实性校验：AI 答案 vs 已存 run 的机读真值（supported/invented/contradicted）。Verify an AI answer against a stored run's computed chart facts.")
def benchmark_faithfulness(
    run_id: str = typer.Option(..., "--run-id", help="Stored run whose computed facts are the ground truth."),
    answer_file: Optional[Path] = typer.Option(None, "--answer-file", help="Read the AI answer text from a file."),
    answer_text: Optional[str] = typer.Option(None, "--answer-text", help="Short inline AI answer text."),
    tool: str | None = typer.Option(None, "--tool", help="Optional tool name for multi-tool runs."),
) -> None:
    from horosa_skill.benchmark.faithfulness import extract_facts, verify_answer

    if not answer_file and not answer_text:
        _emit_refusal("benchmark.faithfulness.answer_missing", "需要 --answer-file 或 --answer-text")
    if answer_file:
        try:
            answer = answer_file.expanduser().read_text(encoding="utf-8")
        except OSError as exc:
            raise typer.BadParameter(f"无法读取 --answer-file：{exc}") from exc
    else:
        answer = answer_text or ""
    service = _service()
    try:
        run, artifact = service._load_report_source(run_id, tool)  # noqa: SLF001 - 同包 CLI 面复用装载器
    except ToolValidationError as exc:
        _refuse(exc)
    payload = artifact.get("payload") or {}
    facts = extract_facts(payload)
    report = verify_answer(answer, facts)
    report["run_id"] = run_id
    report["tool"] = artifact.get("tool_name")
    # 可选云端决策层 S4（HOROSA_JEV 开且 HOROSA_JEV_SCOPE=snapshot 才有）：只读第二意见，永不改 ok/metrics。
    export_text = (((payload.get("data") or {}).get("export_snapshot") or {}).get("export_text")) if isinstance(payload, dict) else None
    opinion = service.faithfulness_opinion(report, export_text)
    if opinion is not None:
        report["model_opinion"] = opinion
    _print_json(report)
    if not report["ok"]:
        raise typer.Exit(code=1)


@trace_app.command("latest", help='Show the most recent local trace events (sanitized). 查看最近的追踪记录。')
def trace_latest(
    limit: int = typer.Option(30, help="How many recent trace rows to print from the newest local trace file."),
) -> None:
    tracer = _tracer()
    _print_json(
        {
            "enabled": tracer.enabled,
            "files": [str(path) for path in tracer.latest_trace_files(limit=3)],
            "events": tracer.read_latest(limit=max(1, limit)),
        }
    )


@client_app.command("check", help="Audit this machine's MCP client configs for horosa entries. 体检本机各客户端的 horosa 配置。")
def client_check(
    client: str = typer.Option(None, "--client", help="Only check this client (claude-code / cursor / vscode / codex / …)."),
    config_path: Path = typer.Option(None, "--config", help="Check this exact config file instead of the known locations."),
) -> None:
    """看每个客户端**实际写着什么**，而不是我们建议它写什么。

    🔴 `client config` 只会打印「应该长什么样」。用户配错时（占位符没展开、缺 --transport stdio、
    目录搬了、Codex 超时是默认的 10/60 秒、`uvx horosa-skill` 指着还没开通的 PyPI）唯一的症状是
    客户端里安静地少了这个 server —— 没有任何一处会告诉他们哪一步错了。
    """
    _print_json(_client_check_report([client] if client else list(_CLIENT_NAMES), config_path))


@client_app.command(
    "skill",
    help="Install / refresh only the horosa-agent skill (no MCP config) into the skills folder a client reads. "
         "只装 skill 规则文件（手动配过 MCP 的用户用）。",
)
def client_skill(
    client: str = typer.Option(None, "--client", help="Target client (same keys as `setup --client`); default = the shared ~/.agents/skills."),
    skill_dir: Path | None = typer.Option(None, "--skill-dir", help="Install into this skills folder instead (skill lands in <dir>/horosa-agent)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Report what would change; write nothing."),
) -> None:
    from horosa_skill import skill_install

    if client is not None and client.strip().lower() not in _CLIENT_NAMES:
        raise typer.BadParameter(f"未知客户端 `{client}`。可选：{', '.join(_CLIENT_NAMES)}")
    key = client.strip().lower() if client else "shared"
    step = _setup_skill_step(
        key if client else None, enabled=True, skill_dir=skill_dir, plan_only=dry_run,
        announce=lambda text: typer.echo(text, err=True),
    )
    step["client"] = key
    if client is None and skill_dir is None:
        step["note"] = f"装到共享目录 {skill_install.shared_skills_dir()}；只读自家目录的客户端请加 --client。"
    _print_json(step)
    if any(t.get("action") == "failed" for t in step.get("targets") or []):
        raise typer.Exit(code=2)


@client_app.command("config")
def client_config(
    format_name: str = typer.Option(
        "claude-code",
        "--format",
        help=(
            "Target client: claude-code / claude-desktop / cursor / vscode / codex / "
            "gemini / windsurf / cline / zed / " + " / ".join(clients_extra.EXTRA_CLIENTS) + " / mcporter / openclaw."
        ),
    ),
    skill_root: Path = typer.Option(
        runtime_helpers._package_root(),
        help="Path to the horosa-skill package directory, or the repo root that contains it.",
    ),
    server_name: str = typer.Option("horosa", help="Server name key written into the MCP config."),
    write: Path | None = typer.Option(None, help="Optional output file path (also printed to stdout)."),
    launcher: str = typer.Option(
        "uv",
        "--launcher",
        help=(
            "How the client starts the server: `uv` (source checkout) / `uvx-wheel` (zero-install from the "
            "release wheel asset — no git, no PyPI; honours HOROSA_RUNTIME_MIRROR) / `uvx-git` (zero-install "
            "from this repo; needs git + github.com) / `uvx` (PyPI, not live yet). "
            "mcporter/openclaw formats always use the checkout."
        ),
    ),
    surface: str = typer.Option(
        "auto",
        "--surface",
        help=(
            "Advertised tool surface: `auto`（按客户端上限自动选，见 _CLIENT_COMPACT_DEFAULT）/ "
            f"`full`（{FACADE_TOOL_COUNT + len(TOOL_DEFINITIONS)} 个工具）/ `compact`（{COMPACT_SURFACE_TOOL_COUNT} 个门面工具，全部技法仍可经 horosa_tool_run 到达）。"
        ),
    ),
    output_script: str = typer.Option(
        "zh-Hans",
        "--output-script",
        help="结果文字：zh-Hans（简体，缺省）/ zh-Hant（繁体·台湾字形）/ zh-Hant-HK（繁体·香港字形）。写进客户端配置的 HOROSA_OUTPUT_SCRIPT；重跑 setup 不带它就回到简体。",
    ),
    entry: str = typer.Option("auto", "--entry", help=_ENTRY_HELP),
    vectors: bool = typer.Option(
        False, "--vectors",
        help="Add the [vectors] extra to the launcher. Only generates the config: nothing is installed or verified — `setup --vectors` does that.",
    ),
) -> None:
    """按客户端生成即用 MCP 配置（自动注入真实绝对路径，无手填占位符）。"""
    payload, _stdio_command, _surface_env = _build_client_config_payload(
        format_name=format_name, skill_root=skill_root, server_name=server_name, launcher=launcher, surface=surface,
        output_script=str(_opt(output_script, "zh-Hans")), entry=str(_opt(entry, "auto")), vectors=bool(_opt(vectors, False)),
    )
    if write is not None:
        payload["written"] = _merge_client_config(write, payload)
    _print_json(payload)


@client_app.command("openclaw-config", help='Print the OpenClaw / mcporter config for this machine. 生成 OpenClaw 配置。')
def client_openclaw_config(
    skill_root: Path = typer.Option(
        runtime_helpers._package_root(),
        help="Path to the horosa-skill package directory, or the repo root that contains it.",
    ),
    format_name: str = typer.Option(
        "mcporter",
        "--format",
        help="Output config format: mcporter or openclaw.",
    ),
    server_name: str = typer.Option("horosa", help="Server name key written into the MCP config."),
    isolate_home: Path | None = typer.Option(
        None,
        help="Optional HOME directory to embed for fully isolated installs and smoke tests.",
    ),
    write: Path | None = typer.Option(
        None,
        help="Optional output file path. When set, the config is written there and also printed to stdout.",
    ),
) -> None:
    resolved_skill_root = _resolve_skill_root(skill_root)
    payload = _build_openclaw_config(
        skill_root=resolved_skill_root,
        server_name=server_name,
        format_name=format_name,
        isolate_home=isolate_home,
    )
    if write is not None:
        _write_json_file(write, payload)
    _print_json(payload)


@client_app.command("openclaw-setup", help='Install the Horosa skill and MCP entry into an OpenClaw workspace. 接入 OpenClaw 工作区。')
def client_openclaw_setup(
    workspace: Path = typer.Option(
        Path.home() / ".openclaw" / "workspace",
        help="OpenClaw workspace root. The command creates config/ under it when missing.",
    ),
    skill_root: Path = typer.Option(
        runtime_helpers._package_root(),
        help="Path to the horosa-skill package directory, or the repo root that contains it.",
    ),
    server_name: str = typer.Option("horosa", help="Server name key written into the mcporter config."),
    isolate_home: Path | None = typer.Option(
        None,
        help="Optional isolated HOME. Defaults to <workspace>/.horosa-home for a self-contained setup.",
    ),
    config: Path | None = typer.Option(
        None,
        help="Optional mcporter config path. Defaults to <workspace>/config/mcporter.json.",
    ),
    native_config: Path | None = typer.Option(
        None,
        "--native-config",
        help="Optional OpenClaw native config path. Defaults to ~/.openclaw/openclaw.json.",
    ),
    write_native_config: bool = typer.Option(
        True,
        "--write-native-config/--no-write-native-config",
        help="Also merge Horosa into OpenClaw's native mcp.servers config so agent sessions can see horosa_* tools.",
    ),
    skip_smoke: bool = typer.Option(
        False,
        help="Skip the final smoke check if you only want install + config generation.",
    ),
    manifest_url: str | None = typer.Option(
        None,
        "--manifest-url",
        help="Optional runtime manifest URL. Defaults to the public GitHub Release manifest for the installed package version.",
    ),
) -> None:
    report = openclaw_flow._run_openclaw_setup(
        workspace=workspace,
        skill_root=skill_root,
        server_name=server_name,
        isolate_home=isolate_home,
        config=config,
        native_config=native_config,
        write_native_config=write_native_config,
        skip_smoke=skip_smoke,
        manifest_url=manifest_url,
    )
    _print_json(report)
    if not report["ok"]:
        raise typer.Exit(code=2)


@client_app.command("openclaw-check", help="Check an OpenClaw workspace's Horosa skill and MCP entry. 体检 OpenClaw 接入。")
def client_openclaw_check(
    workspace: Path = typer.Option(
        Path.home() / ".openclaw" / "workspace",
        help="OpenClaw workspace root. The default assumes ~/.openclaw/workspace.",
    ),
    config: Path | None = typer.Option(
        None,
        help="Explicit mcporter config path. Defaults to <workspace>/config/mcporter.json.",
    ),
    full: bool = typer.Option(
        False,
        help="Run the exhaustive all-tool OpenClaw self-check instead of a quick smoke check.",
    ),
    output: Path | None = typer.Option(
        None,
        help="Optional report path. Defaults to a JSON file in the Horosa data directory.",
    ),
) -> None:
    report, failed = openclaw_flow._run_openclaw_check(workspace=workspace, config=config, full=full, output=output)
    if report is not None:
        _print_json(report)
    if failed:
        raise typer.Exit(code=2)


@report_app.command("template", help='Turn a stored run into an AI-fillable report template. 生成可填写的报告模板。')
def report_template(
    run_id: str = typer.Option(..., "--run-id", help="Run id to turn into an AI-fillable report template."),
    tool: str | None = typer.Option(None, "--tool", help="Optional tool name for dispatch or multi-tool runs."),
    language: str | None = typer.Option(None, "--language", help="Report language tag (zh-CN / zh-TW / zh-HK …); omit to follow HOROSA_OUTPUT_SCRIPT."),
) -> None:
    service = _service()
    try:
        result = service.report_template({"run_id": run_id, "tool_name": tool, **({"language": language} if language else {})})
    except ToolValidationError as exc:
        _refuse(exc)
    _print_json(result)


@report_app.command("render", help='Render a stored run (plus optional ai_report JSON) to JSON / DOCX / PDF. 渲染报告文件。')
def report_render(
    run_id: str = typer.Option(..., "--run-id", help="Run id to render."),
    format_name: str = typer.Option("pdf", "--format", help="Output format: json, docx, or pdf."),
    tool: str | None = typer.Option(None, "--tool", help="Optional tool name for dispatch or multi-tool runs."),
    output: Path | None = typer.Option(None, "--output", help="Optional output path. Defaults to the Horosa memory output directory."),
    title: str | None = typer.Option(None, "--title", help="Optional report title."),
    language: str | None = typer.Option(None, "--language", help="Report language tag (zh-CN / zh-TW / zh-HK …); omit to follow HOROSA_OUTPUT_SCRIPT."),
    style: str = typer.Option("analysis", "--style", help="analysis (AI report; without an AI answer you get the template) / chart (complete chart report rendered right away)."),
    include_raw_json: bool = typer.Option(False, "--include-raw-json/--no-include-raw-json", help="Embed the full source envelope in the report JSON."),
    stdin: bool = typer.Option(False, "--stdin", help="Read optional ai_report JSON from stdin."),
    input_file: Optional[Path] = typer.Option(None, "--input", help="Read optional ai_report JSON from a file."),
) -> None:
    ai_payload = _load_optional_payload(stdin=stdin, input_file=input_file)
    ai_report = ai_payload.get("ai_report", ai_payload)
    service = _service()
    try:
        result = service.report_render(
            {
                "run_id": run_id,
                "tool_name": tool,
                "format": format_name,
                **({"language": language} if language else {}),
                "style": style,
                "title": title,
                "ai_report": ai_report,
                "include_raw_json": include_raw_json,
                "output_path": str(output.expanduser()) if output else None,
            }
        )
    except ToolValidationError as exc:
        _refuse(exc)
    _print_json(_localized(result))


@report_app.command("technique", help="技法依据报告：本次/本会话用了什么技法、什么口径、谁算的（确定性，无需 AI 正文）。Deterministic method/provenance report — no ai_report needed.")
def report_technique(
    run_id: str | None = typer.Option(None, "--run-id", help="Report on a single stored run."),
    group_id: str | None = typer.Option(None, "--group-id", help="Report on a whole session (all runs sharing this group id)."),
    format_name: str = typer.Option("markdown", "--format", help="Output format: markdown, json, docx, or pdf."),
    output: Path | None = typer.Option(None, "--output", help="Optional output path. Defaults to the Horosa memory output directory."),
    title: str | None = typer.Option(None, "--title", help="Optional report title."),
    include_sections: bool = typer.Option(True, "--include-sections/--no-include-sections", help="List each technique's produced section titles."),
) -> None:
    service = _service()
    try:
        result = service.technique_report(
            {
                "run_id": run_id,
                "group_id": group_id,
                "format": format_name,
                "title": title,
                "include_sections": include_sections,
                "output_path": str(output.expanduser()) if output else None,
            }
        )
    except ToolValidationError as exc:
        _refuse(exc)
    # 报告正文已落盘；命令行只回摘要 + 一致性结论（把整篇 markdown 打进 stdout 会淹掉真正要看的告警）。
    _print_json(_localized({key: value for key, value in result.items() if key != "document"}))


@report_app.command("from-tool", help='Run a technique and render its report in one step: `report from-tool <name> --input payload.json --format docx`. 起盘并出报告。')
def report_from_tool(
    tool: str = typer.Argument(..., help="Tool name such as chart, qimen, liureng_gods, or sixyao."),
    format_name: str = typer.Option("pdf", "--format", help="Output format: json, docx, or pdf."),
    output: Path | None = typer.Option(None, "--output", help="Optional output path. Defaults to the Horosa memory output directory."),
    question: str | None = typer.Option(None, "--question", help="Optional user question to store with this report run."),
    title: str | None = typer.Option(None, "--title", help="Optional report title."),
    language: str | None = typer.Option(None, "--language", help="Report language tag (zh-CN / zh-TW / zh-HK …); omit to follow HOROSA_OUTPUT_SCRIPT."),
    style: str = typer.Option("analysis", "--style", help="analysis (AI report; without an AI answer you get the template) / chart (complete chart report rendered right away)."),
    ai_answer_text: str | None = typer.Option(None, "--ai-answer-text", help="Free-form AI analysis text to render directly into the final report."),
    ai_answer_file: Optional[Path] = typer.Option(None, "--ai-answer-file", help="Read free-form AI analysis text from a UTF-8 file."),
    ai_report_file: Optional[Path] = typer.Option(None, "--ai-report-file", help="Read structured ai_report JSON from a UTF-8 file."),
    include_raw_json: bool = typer.Option(False, "--include-raw-json/--no-include-raw-json", help="Embed the full source envelope in the report JSON."),
    stdin: bool = typer.Option(False, "--stdin", help="Read the tool payload JSON from stdin."),
    input_file: Optional[Path] = typer.Option(None, "--input", help="Read the tool payload JSON from a file."),
) -> None:
    payload = _load_payload(stdin=stdin, input_file=input_file)
    ai_report: dict[str, Any] = {}
    if ai_report_file is not None:
        try:
            raw_ai_report = json.loads(ai_report_file.read_text(encoding="utf-8"))
        except OSError as exc:
            raise typer.BadParameter(f"--ai-report-file could not be read: {exc}")
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(f"--ai-report-file is not valid JSON: {exc}")
        if not isinstance(raw_ai_report, dict):
            raise typer.BadParameter("--ai-report-file must contain a JSON object.")
        ai_report = raw_ai_report.get("ai_report", raw_ai_report)
        if not isinstance(ai_report, dict):
            raise typer.BadParameter("--ai-report-file ai_report must be a JSON object.")
    final_ai_answer_text = ai_answer_text
    if ai_answer_file is not None:
        try:
            file_text = ai_answer_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise typer.BadParameter(f"--ai-answer-file could not be read: {exc}")
        final_ai_answer_text = f"{final_ai_answer_text}\n\n{file_text}".strip() if final_ai_answer_text else file_text
    service = _service()
    try:
        _enforce_agent_preflight(tool, payload)
        result = service.report_from_tool(
            {
                "tool_name": tool,
                "payload": payload,
                "format": format_name,
                **({"language": language} if language else {}),
                "style": style,
                "title": title,
                "question": question,
                "ai_report": ai_report,
                "ai_answer_text": final_ai_answer_text,
                "include_raw_json": include_raw_json,
                "output_path": str(output.expanduser()) if output else None,
            }
        )
    except ToolValidationError as exc:
        _refuse(exc)
    _print_json(_localized(result))


@memory_app.command("query", help='Search stored runs by run id, tool, entity, text or date range. 检索本地运行记录。')
def memory_query(
    run_id: str | None = typer.Option(None, help="Filter by exact run id."),
    tool: str | None = typer.Option(None, help="Filter by tool name."),
    entity: str | None = typer.Option(None, help="Filter by entity name."),
    text: str | None = typer.Option(None, help="Search query text, user question, AI answer, subject, tool, artifact path, or artifact kind."),
    artifact_kind: str | None = typer.Option(None, help="Filter by artifact kind, for example report_json, report_docx, report_pdf, or tool_result."),
    after: str | None = typer.Option(None, help="Only return runs created after this ISO timestamp."),
    before: str | None = typer.Option(None, help="Only return runs created before this ISO timestamp."),
    limit: int = typer.Option(20, help="Maximum runs to return."),
    include_payload: bool = typer.Option(True, "--include-payload/--no-include-payload", help="Embed saved JSON payloads in the query output."),
    worthy_only: bool = typer.Option(False, "--worthy-only", help="只留召回语料级条目（有产物/答案/成功调用；空失败 run 滤除）。"),
) -> None:
    service = _service()
    scan: dict[str, Any] = {}
    data = service.store.query_runs(
        run_id=run_id,
        tool=tool,
        entity=entity,
        text=text,
        artifact_kind=artifact_kind,
        after=after,
        before=before,
        limit=limit,
        include_payload=include_payload,
        scan_report=scan,
    )
    if worthy_only:
        data = [record for record in data if service.store.is_memory_worthy(record)]
    if scan.get("not_scanned"):  # stdout 的列表形状是对外契约，说明走 stderr
        typer.echo(f"另有 {scan['not_scanned']} 条较早的记录只按问题与答案检索过，盘面正文没有搜。", err=True)
    _print_json(_localized(data))


@memory_app.command("show", help='Show one stored run in full (envelope, artifacts, recorded AI answer). 查看单条运行记录。')
def memory_show(
    run_id: str = typer.Argument(..., help="Exact run id to display."),
    include_payload: bool = typer.Option(True, "--include-payload/--no-include-payload", help="Embed saved JSON payloads in the output."),
) -> None:
    service = _service()
    data = service.store.query_runs(run_id=run_id, limit=1, include_payload=include_payload)
    if not data:
        _emit_refusal("memory.run.not_found", f"Run not found: {run_id}")
    _print_json(_localized(data[0]))


@memory_app.command("prune", help="清理长期未点用的 run（默认 dry-run 只打印计划；--yes 才删）。Prune runs never recalled within N days.")
def memory_prune(
    unused_days: int = typer.Option(90, "--unused-days", help="判据：创建/最后点用早于 N 天且从未点用（usage_count=0）。"),
    yes: bool = typer.Option(False, "--yes", help="真正删除（含磁盘产物文件）。缺省只打印将删清单。"),
) -> None:
    service = _service()
    _print_json(service.store.prune_unused(unused_days=unused_days, yes=yes))


@memory_app.command("answer", help="Attach the AI's final answer to a stored run: JSON {run_id, ai_answer[, user_question]}. 把 AI 解读写回运行记录。")
def memory_answer(
    stdin: bool = typer.Option(False, "--stdin", help="Read a JSON object from stdin."),
    input_file: Optional[Path] = typer.Option(None, "--input", help="Read a JSON object from a file."),
) -> None:
    payload = _load_payload(stdin=stdin, input_file=input_file)
    service = _service()
    try:
        result = service.record_ai_answer(payload)
    except ToolValidationError as exc:
        _refuse(exc)
    except ValueError as exc:
        _emit_refusal("memory.answer.unknown_run", str(exc))
    _print_json(_localized(result))


if __name__ == "__main__":
    app()
