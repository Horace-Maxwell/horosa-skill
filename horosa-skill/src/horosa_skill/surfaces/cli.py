from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from importlib.metadata import PackageNotFoundError, version as package_version
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

import typer

from horosa_skill import clients_extra
from horosa_skill.agent_guidance import build_agent_guidance, validate_agent_preflight
from horosa_skill.config import Settings
from horosa_skill.benchmark import run_benchmark
from horosa_skill.engine.registry import TOOL_DEFINITIONS, resolve_tool_name
from horosa_skill.errors import RuntimeError, ToolValidationError, bilingual
from horosa_skill.runtime import HorosaRuntimeManager
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces.mcp_server import COMPACT_SURFACE_TOOL_COUNT, FACADE_TOOL_COUNT
from horosa_skill.surfaces.mcp_server import run_mcp_server
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
from horosa_skill.client_config.openclaw import (
    _build_openclaw_config,
    _default_openclaw_native_config_path,
    _isolated_env_vars,
    _write_openclaw_native_config,
)
from horosa_skill.client_config.payload import (
    _build_client_config_payload,
    _resolve_skill_root,
)
from horosa_skill.surfaces.doctor import (
    STATUS_BUDGET_SECONDS,
    _doctor_report,
    _explain_lines,
)
from horosa_skill.surfaces.openclaw_smoke import (
    _friendly_runtime_error_payload,
    _openclaw_setup_command,
    _setup_summary,
    _timed_call,
)
from horosa_skill.surfaces import openclaw_smoke
from horosa_skill.surfaces.runtime_helpers import (
    _install_progress_printer,
)
from horosa_skill.surfaces.setup_flow import (
    _SetupFailure,
    _run_setup,
    _setup_skill_step,
)
from horosa_skill.surfaces import runtime_helpers

app = typer.Typer(
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


def _start_stdio_runtime_warmup(manager: HorosaRuntimeManager) -> None:
    def _warmup() -> None:
        try:
            manager.start_local_services()
        except RuntimeError as exc:
            # 预热失败推迟不了问题只会掩盖它：stderr 一行警告（stdio 协议流在 stdout，不受影响）。
            sys.stderr.write(f"[horosa] runtime 预热失败（首次调用时会重试）：{exc.code} {exc}\n")
            sys.stderr.flush()

    threading.Thread(target=_warmup, name="horosa-stdio-runtime-warmup", daemon=True).start()


def _tracer(settings: Settings | None = None) -> TraceRecorder:
    return TraceRecorder(settings or Settings.from_env())


def _load_payload(*, stdin: bool, input_file: Optional[Path]) -> dict:
    if stdin:
        stream = getattr(sys.stdin, "buffer", None)
        if stream is not None:
            raw = stream.read().decode("utf-8-sig")
        else:
            raw = sys.stdin.read()
    elif input_file is not None:
        raw = input_file.read_text(encoding="utf-8")
    else:
        raise typer.BadParameter("Provide exactly one of --stdin or --input.")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Invalid JSON payload: {exc}") from exc
    if not isinstance(data, dict):
        raise typer.BadParameter("Input JSON must be an object.")
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
    preflight = validate_agent_preflight(tool_name, payload)
    if preflight.get("ok"):
        return
    raise ToolValidationError(preflight["message"], code=preflight["code"], details=preflight)


@contextmanager
def _temporary_env(overrides: dict[str, str]):
    previous = {key: os.environ.get(key) for key in overrides}
    os.environ.update(overrides)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


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


_TRANSPORT_ALIASES = {
    "http": "streamable-http",
    "streamable_http": "streamable-http",
    "streamablehttp": "streamable-http",
    "shttp": "streamable-http",
}
_TRANSPORTS = {"streamable-http", "stdio", "sse"}


def _normalized_transport(value: str) -> str:
    text = (value or "").strip().lower()
    text = _TRANSPORT_ALIASES.get(text, text)
    if text not in _TRANSPORTS:
        raise typer.BadParameter(
            f"未知传输 `{value}`。可选：streamable-http（默认）、stdio、sse（legacy）。"
            "注意 `http` 是 Claude Code 注册命令里的说法，这里请写 streamable-http。"
        )
    return text


def _mask_token(token: str | None) -> str:
    if not token:
        return ""
    return f"{token[:4]}…{token[-2:]}" if len(token) > 8 else "****"


def _run_install(archive: str | None, manifest_url: str | None, force: bool, *, mode: str) -> None:
    settings = Settings.from_env()
    manager = runtime_helpers._runtime_manager(settings)
    typer.echo("正在解析 runtime 版本与资产…（约 730MB 下载、解压后约 2GB，请留足磁盘）", err=True)
    try:
        result = manager.install(archive=archive, manifest_url=manifest_url, force=force, progress=_install_progress_printer())
    except RuntimeError as exc:
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    except OSError as exc:
        # 磁盘满 / 权限不足 / 跨卷等 IO 失败：结构化输出而非裸 traceback。
        typer.echo(json.dumps({"ok": False, "code": "runtime.install_io_error", "message": str(exc), "details": {}}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
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
    purge_data: bool = typer.Option(False, "--purge-data", help="Also delete user data (memory.db / runs / traces). 同时删除用户数据（不可恢复）。"),
    yes: bool = typer.Option(False, "--yes", help="Actually delete. Without this flag only the removal plan is printed."),
) -> None:
    settings = Settings.from_env()
    manager = runtime_helpers._runtime_manager(settings)
    try:
        result = manager.uninstall(purge_data=purge_data, yes=yes)
    except RuntimeError as exc:
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
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
) -> None:
    try:
        report = _run_setup(
            client=client, launcher=launcher, surface=surface, config=config, scope=scope, server_name=server_name,
            skill_root=skill_root, dry_run=dry_run, skip_install=skip_install, archive=archive, manifest_url=manifest_url,
            probe_network=probe_network, stdio_probe=stdio_probe, write=write, cache_wheel=cache_wheel,
            skill=skill, skill_dir=skill_dir,
        )
    except _SetupFailure as failure:
        typer.echo(json.dumps(failure.payload, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
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
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
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
        endpoints = manager.endpoint_identities(manifest) if installed else []
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
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
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
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
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
    transport = _opt(transport, "streamable-http")
    host = _opt(host)
    port = _opt(port)
    token = _opt(token)
    allow_unauthenticated = bool(_opt(allow_unauthenticated, False))
    skip_runtime_start = bool(_opt(skip_runtime_start, False))
    stop_runtime_on_exit = bool(_opt(stop_runtime_on_exit, False))
    settings = Settings.from_env()
    # 🔴 `--transport http` 是最常见的手误（Claude Code 的 `claude mcp add --transport http` 用的
    # 就是这个词）。旧实现把未知值原样传给 SDK，得到的是一句不知所云的内部报错。
    transport = _normalized_transport(transport)
    # host/port 缺省来自 env（旧实现把 typer 的字面默认写死，于是 docker-compose 里设的
    # HOROSA_SKILL_HOST/PORT 永远不生效 —— 容器只监听 127.0.0.1，宿主怎么连都连不上）。
    if host is not None:
        settings.host = host
    if port is not None:
        settings.port = port
    host, port = settings.host, settings.port
    token = (token or os.environ.get("HOROSA_MCP_TOKEN", "") or "").strip() or None
    if token:
        os.environ["HOROSA_MCP_TOKEN"] = token
    if transport != "stdio" and host not in {"127.0.0.1", "localhost", "::1"}:
        if not token and not allow_unauthenticated:
            typer.echo(
                json.dumps(
                    {
                        "ok": False,
                        "code": "serve.token_required",
                        "message": f"绑定到非回环地址 {host} 而没有设置访问令牌 —— 已拒绝启动。",
                        "details": {
                            "host": host,
                            "next_action": (
                                "设 --token <随机串>（或 HOROSA_MCP_TOKEN），客户端在 Authorization: Bearer "
                                "头里带上它；确实想裸奔请显式加 --allow-unauthenticated。"
                            ),
                            "why": (
                                "本 server 能读写本机记忆库、生成文件、驱动本地 runtime。"
                                "对外绑定且无鉴权 = 同网段任何人都能做这些事。"
                            ),
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                err=True,
            )
            raise typer.Exit(code=2)
        if not token:
            typer.echo(
                f"⚠️  正在以**无鉴权**方式绑定 {host}:{port}，且没有 TLS。"
                "同网段的任何人都能调用本机的 Horosa 工具、读你的记忆库。仅在可信网络里这么做。",
                err=True,
            )
    manager = runtime_helpers._runtime_manager(settings)
    # 🔴 端口先探再起：8765 被占时旧实现让 uvicorn 抛裸 traceback（OSError: [Errno 48]），
    # 而这是**最常见**的一次失败 —— 用户在两个终端里各起一个 serve。
    if transport != "stdio":
        from horosa_skill.runtime.ports import port_bindable, port_holders

        if not port_bindable(port, host if host not in {"0.0.0.0", "::"} else "127.0.0.1"):
            holders = port_holders(port)
            typer.echo(
                json.dumps(
                    {
                        "ok": False,
                        "code": "serve.port_in_use",
                        "message": f"端口 {port} 已被占用，MCP server 无法监听。",
                        "details": {
                            "host": host,
                            "port": port,
                            "holders": holders,
                            "next_action": (
                                f"换端口：`--port <其它端口>` 或设 HOROSA_SKILL_PORT；"
                                "或关掉上面点名的进程（本工具不会代为终止）。"
                            ),
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                err=True,
            )
            raise typer.Exit(code=2)
    service = HorosaSkillService(settings, runtime_manager=manager)
    # 🔴 横幅必须在启动 runtime **之前**打印：start_local_services 可以阻塞到 45 秒
    # （首次更久），期间用户盯着一个没有任何输出的终端，无从判断是卡住了还是在装。
    if transport != "stdio":
        path = "/sse" if transport == "sse" else "/mcp"
        typer.echo(
            f"Horosa Skill MCP 正在 http://{host}:{port}{path} 监听"
            f"（{transport}{'（legacy）' if transport == 'sse' else ''}，{len(TOOL_DEFINITIONS)} 个技法工具）。\n"
            + (f"访问令牌：已启用（Authorization: Bearer {_mask_token(token)}）。\n" if token else "")
            + f"接入 Claude Code：claude mcp add horosa --transport http http://{host}:{port}{path}\n"
            f"其他客户端：uv run horosa-skill client config --format <client>（见 README「接入 AI 客户端」）。\n"
            + ("正在启动本机 runtime（首次可能要几分钟）……" if not skip_runtime_start else ""),
            err=True,
        )
    started_now = False
    if not skip_runtime_start:
        if transport == "stdio":
            _start_stdio_runtime_warmup(manager)
        else:
            try:
                start_result = manager.start_local_services()
                started_now = not start_result.get("already_running", False)
            except RuntimeError as exc:
                typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
                raise typer.Exit(code=2)
    from horosa_skill.runtime import registry as _registry

    try:
        _registry.attach_client(settings.runtime_state_path, pid=os.getpid(), transport=transport)
    except OSError:
        pass
    try:
        run_mcp_server(settings, transport=transport, service=service)
    finally:
        try:
            _registry.detach_client(settings.runtime_state_path, pid=os.getpid())
        except OSError:
            pass
        # 🔴 默认**保温**。旧行为是「这次 serve 起的就在退出时停掉」——而 runtime 是**共享**的：
        # Claude Desktop 与 Cursor 同时挂着时，关掉其中一个会把另一个的后端一起停掉；
        # 而重启一次要几十秒到几分钟。要恢复旧行为请显式加 --stop-runtime-on-exit。
        if stop_runtime_on_exit and started_now and transport != "stdio":
            others = _registry.live_clients(manager.load_runtime_state(), exclude_pid=os.getpid())
            if others:
                typer.echo(
                    f"还有 {len(others)} 个客户端挂在这份 runtime 上，未停止（--stop-runtime-on-exit 让位于它们）。",
                    err=True,
                )
            else:
                try:
                    manager.stop_local_services()
                except RuntimeError:
                    pass


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
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    _emit_json(result.model_dump(mode="json"), output)


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
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
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
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    _print_json(result.model_dump(mode="json"))


@knowledge_app.command("search")
def knowledge_search(
    query: str = typer.Argument(..., help="Full-text query across every bundled knowledge domain (`knowledge registry` lists them)."),
    domain: Optional[str] = typer.Option(None, help="Optional domain filter (e.g. bazi, ziwei, qimen)."),
    limit: int = typer.Option(8, help="Max matches to return (1-20)."),
    save_result: bool = typer.Option(False, help="Persist the result in local memory."),
) -> None:
    """Search bundled knowledge (hover + technique manuals); every match carries a citation."""
    payload: dict[str, Any] = {"query": query, "limit": limit}
    if domain:
        payload["domain"] = domain
    service = _service()
    try:
        result = service.run_tool("knowledge_read", payload, save_result=save_result)
    except ToolValidationError as exc:
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    _print_json(result.model_dump(mode="json"))


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
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    _emit_json(result.model_dump(mode="json"), output)


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
        result = service.hecan(payload)
    except ToolValidationError as exc:
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    _emit_json(result, output)


@benchmark_app.command("faithfulness", help="盘面事实忠实性校验：AI 答案 vs 已存 run 的机读真值（supported/invented/contradicted）。Verify an AI answer against a stored run's computed chart facts.")
def benchmark_faithfulness(
    run_id: str = typer.Option(..., "--run-id", help="Stored run whose computed facts are the ground truth."),
    answer_file: Optional[Path] = typer.Option(None, "--answer-file", help="Read the AI answer text from a file."),
    answer_text: Optional[str] = typer.Option(None, "--answer-text", help="Short inline AI answer text."),
    tool: str | None = typer.Option(None, "--tool", help="Optional tool name for multi-tool runs."),
) -> None:
    from horosa_skill.benchmark.faithfulness import extract_facts, verify_answer

    if not answer_file and not answer_text:
        typer.echo(json.dumps({"ok": False, "message": "需要 --answer-file 或 --answer-text"}, ensure_ascii=False), err=True)
        raise typer.Exit(code=2)
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
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc)}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
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
) -> None:
    """按客户端生成即用 MCP 配置（自动注入真实绝对路径，无手填占位符）。"""
    payload, _stdio_command, _surface_env = _build_client_config_payload(
        format_name=format_name, skill_root=skill_root, server_name=server_name, launcher=launcher, surface=surface,
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
    resolved_skill_root = _resolve_skill_root(skill_root)
    workspace_root = workspace.expanduser().resolve()
    workspace_root.mkdir(parents=True, exist_ok=True)
    config_path = (config.expanduser().resolve() if config is not None else workspace_root / "config" / "mcporter.json")
    native_config_path = (
        native_config.expanduser().resolve()
        if native_config is not None
        else _default_openclaw_native_config_path().expanduser().resolve()
    )
    home_dir = (isolate_home.expanduser().resolve() if isolate_home is not None else workspace_root / ".horosa-home")
    env_overrides = _isolated_env_vars(home_dir)

    payload = _build_openclaw_config(
        skill_root=resolved_skill_root,
        server_name=server_name,
        format_name="mcporter",
        isolate_home=home_dir,
    )
    _write_json_file(config_path, payload)
    native_config_written_to: Path | None = None
    if write_native_config:
        native_config_written_to = _write_openclaw_native_config(
            path=native_config_path,
            server_name=server_name,
            server_block=payload["mcpServers"][server_name],
        )

    with _temporary_env(env_overrides):
        settings = Settings.from_env()
        manager = runtime_helpers._runtime_manager(settings)
        try:
            install_result, install_seconds = _timed_call(lambda: manager.install(manifest_url=manifest_url))
            start_result, start_seconds = _timed_call(lambda: manager.start_local_services())
            doctor_result, doctor_seconds = _timed_call(manager.doctor)
            smoke_report: dict[str, Any] | None = None
            smoke_seconds: float | None = None
            if not skip_smoke:
                smoke_output = settings.data_dir / "openclaw_setup_smoke_check.json"
                smoke_report, smoke_seconds = _timed_call(
                    lambda: openclaw_smoke._run_openclaw_smoke_check(
                        workspace_root=workspace_root,
                        config_path=config_path,
                        output_path=smoke_output,
                        include_list=False,
                    )
                )
        except RuntimeError as exc:
            typer.echo(
                json.dumps(
                    _friendly_runtime_error_payload(
                        exc,
                        action_label="OpenClaw setup",
                        workspace_root=workspace_root,
                        config_path=config_path,
                    ),
                    ensure_ascii=False,
                    indent=2,
                ),
                err=True,
            )
            raise typer.Exit(code=2)

    doctor_issues = doctor_result.get("issues", [])
    install_summary = {
        "ok": install_result.get("ok"),
        "changed": install_result.get("changed"),
        "platform": install_result.get("platform"),
        "runtime_root": install_result.get("runtime_root"),
        "version": ((install_result.get("manifest") or {}).get("version")),
        "runtime_payload_version": ((install_result.get("manifest") or {}).get("runtime_payload_version")),
    }
    runtime_summary = {
        "ok": start_result.get("ok"),
        "already_running": start_result.get("already_running"),
        "reachable_endpoints": [
            endpoint.get("label")
            for endpoint in start_result.get("endpoints", [])
            if endpoint.get("reachable") is True
        ],
    }
    doctor_summary = {
        "issues": doctor_issues,
        "manifest_version": doctor_result.get("manifest_version"),
        "runtime_payload_version": doctor_result.get("runtime_payload_version"),
        "reachable_endpoints": [
            endpoint.get("label")
            for endpoint in doctor_result.get("endpoints", [])
            if endpoint.get("reachable") is True
        ],
    }
    report = {
        "ok": (not doctor_issues) and (skip_smoke or (smoke_report or {}).get("ok") is True),
        "workspace": str(workspace_root),
        "config": str(config_path),
        "config_written_to": str(config_path),
        "native_config": str(native_config_written_to) if native_config_written_to is not None else None,
        "native_config_written_to": str(native_config_written_to) if native_config_written_to is not None else None,
        "native_config_note": (
            "Horosa was merged into OpenClaw native mcp.servers. Restart OpenClaw or start a new agent session "
            "if an existing session still reports clientToolCount: 0."
            if native_config_written_to is not None
            else "Skipped native OpenClaw config write. mcporter checks may pass, but agent sessions may not see horosa_* tools until mcp.servers is configured."
        ),
        "isolate_home": str(home_dir),
        "local_home": str(home_dir),
        "runtime_root": env_overrides["HOROSA_RUNTIME_ROOT"],
        "data_dir": env_overrides["HOROSA_SKILL_DATA_DIR"],
        "timings": {
            "install_seconds": install_seconds,
            "runtime_start_seconds": start_seconds,
            "doctor_seconds": doctor_seconds,
            "smoke_seconds": smoke_seconds,
        },
        "install": install_summary,
        "runtime_start": runtime_summary,
        "doctor": doctor_summary,
        "smoke": smoke_report,
        "next_steps": (
            [
                (
                    f"Restart OpenClaw or start a new agent session so it reloads native MCP config at {native_config_written_to}."
                    if native_config_written_to is not None
                    else f"Open OpenClaw and use the generated mcporter config at {config_path}."
                ),
                f"Re-run `uv run horosa-skill client openclaw-check --workspace {workspace_root} --config {config_path}` whenever you want a fresh smoke report.",
            ]
            if not skip_smoke
            else [
                (
                    f"Restart OpenClaw or start a new agent session so it reloads native MCP config at {native_config_written_to}."
                    if native_config_written_to is not None
                    else f"Open OpenClaw and use the generated mcporter config at {config_path}."
                ),
                f"Run `uv run horosa-skill client openclaw-check --workspace {workspace_root} --config {config_path}` to verify the setup when convenient.",
            ]
        ),
    }
    report.update(
        _setup_summary(
            workspace_root=workspace_root,
            config_path=config_path,
            native_config_path=native_config_written_to,
            home_dir=home_dir,
            doctor_issues=doctor_issues,
            smoke_report=smoke_report,
            skip_smoke=skip_smoke,
        )
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
    settings = Settings.from_env()
    workspace_root = workspace.expanduser().resolve()
    config_path = (config.expanduser().resolve() if config is not None else workspace_root / "config" / "mcporter.json")
    if not config_path.exists():
        typer.echo(
            json.dumps(
                {
                    "ok": False,
                    "status": "needs_attention",
                    "ready_for_openclaw": False,
                    "user_summary": "OpenClaw config not found yet.",
                    "next_action": f"Run `{_openclaw_setup_command(workspace_root)}` to create a ready-to-use config and smoke test it.",
                    "code": "client.config_missing",
                    "message": f"mcporter config not found: {config_path}",
                    "details": {"config": str(config_path), "workspace": str(workspace_root)},
                },
                ensure_ascii=False,
                indent=2,
            ),
            err=True,
        )
        raise typer.Exit(code=2)

    default_output = settings.data_dir / ("openclaw_full_check.json" if full else "openclaw_smoke_check.json")
    output_path = (output.expanduser().resolve() if output is not None else default_output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if full:
        script_path = runtime_helpers._package_root() / "scripts" / "run_openclaw_full_self_check.py"
        if not script_path.is_file():
            # 全量自检脚本只在源码仓里（不进 wheel）：uvx / pip 装的包跑 --full 以前只回一句 Python 的
            # "can't open file"。现在说清楚为什么、下一步怎么走；快速体检（不带 --full）照常可用。
            typer.echo(
                json.dumps(
                    {
                        "ok": False,
                        "code": "openclaw_check.full_unavailable",
                        "message": bilingual(
                            "全量自检脚本只随源码仓分发，当前安装（wheel / uvx）里没有它。",
                            "The exhaustive self-check script ships with the source checkout only, not with this install.",
                        ),
                        "next_action": (
                            "Run the quick check without --full, or clone "
                            "https://github.com/Horace-Maxwell/horosa-skill and run "
                            "`uv run horosa-skill client openclaw-check --full` from its horosa-skill/ directory."
                        ),
                        "details": {"expected_script": str(script_path)},
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                err=True,
            )
            raise typer.Exit(code=2)
        command = [
            sys.executable,
            str(script_path),
            "--workspace",
            str(workspace_root),
            "--config",
            str(config_path),
            "--output",
            str(output_path),
        ]
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, check=False, timeout=900, encoding="utf-8", errors="replace",
            )
        except subprocess.TimeoutExpired:
            typer.echo(
                json.dumps(
                    {"ok": False, "code": "openclaw_check.timeout", "message": "openclaw-check --full exceeded 900s and was aborted (a child MCP/runtime process is likely wedged)."},
                    ensure_ascii=False,
                    indent=2,
                ),
                err=True,
            )
            raise typer.Exit(code=2)
        if output_path.exists():
            report = json.loads(output_path.read_text(encoding="utf-8"))
            _print_json(report)
        else:
            typer.echo(result.stderr or result.stdout, err=True)
        if result.returncode != 0:
            raise typer.Exit(code=2)
        return

    try:
        report = openclaw_smoke._run_openclaw_smoke_check(
            workspace_root=workspace_root,
            config_path=config_path,
            output_path=output_path,
        )
    except RuntimeError as exc:
        typer.echo(
            json.dumps(
                _friendly_runtime_error_payload(
                    exc,
                    action_label="OpenClaw smoke check",
                    workspace_root=workspace_root,
                    config_path=config_path,
                ),
                ensure_ascii=False,
                indent=2,
            ),
            err=True,
        )
        raise typer.Exit(code=2)
    _print_json(report)
    if not report["ok"]:
        raise typer.Exit(code=2)


@report_app.command("template", help='Turn a stored run into an AI-fillable report template. 生成可填写的报告模板。')
def report_template(
    run_id: str = typer.Option(..., "--run-id", help="Run id to turn into an AI-fillable report template."),
    tool: str | None = typer.Option(None, "--tool", help="Optional tool name for dispatch or multi-tool runs."),
    language: str = typer.Option("zh-CN", "--language", help="Report language tag."),
) -> None:
    service = _service()
    try:
        result = service.report_template({"run_id": run_id, "tool_name": tool, "language": language})
    except ToolValidationError as exc:
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    _print_json(result)


@report_app.command("render", help='Render a stored run (plus optional ai_report JSON) to JSON / DOCX / PDF. 渲染报告文件。')
def report_render(
    run_id: str = typer.Option(..., "--run-id", help="Run id to render."),
    format_name: str = typer.Option("pdf", "--format", help="Output format: json, docx, or pdf."),
    tool: str | None = typer.Option(None, "--tool", help="Optional tool name for dispatch or multi-tool runs."),
    output: Path | None = typer.Option(None, "--output", help="Optional output path. Defaults to the Horosa memory output directory."),
    title: str | None = typer.Option(None, "--title", help="Optional report title."),
    language: str = typer.Option("zh-CN", "--language", help="Report language tag."),
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
                "language": language,
                "title": title,
                "ai_report": ai_report,
                "include_raw_json": include_raw_json,
                "output_path": str(output.expanduser()) if output else None,
            }
        )
    except ToolValidationError as exc:
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    _print_json(result)


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
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    # 报告正文已落盘；命令行只回摘要 + 一致性结论（把整篇 markdown 打进 stdout 会淹掉真正要看的告警）。
    _print_json({key: value for key, value in result.items() if key != "document"})


@report_app.command("from-tool", help='Run a technique and render its report in one step: `report from-tool <name> --input payload.json --format docx`. 起盘并出报告。')
def report_from_tool(
    tool: str = typer.Argument(..., help="Tool name such as chart, qimen, liureng_gods, or sixyao."),
    format_name: str = typer.Option("pdf", "--format", help="Output format: json, docx, or pdf."),
    output: Path | None = typer.Option(None, "--output", help="Optional output path. Defaults to the Horosa memory output directory."),
    question: str | None = typer.Option(None, "--question", help="Optional user question to store with this report run."),
    title: str | None = typer.Option(None, "--title", help="Optional report title."),
    language: str = typer.Option("zh-CN", "--language", help="Report language tag."),
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
                "language": language,
                "title": title,
                "question": question,
                "ai_report": ai_report,
                "ai_answer_text": final_ai_answer_text,
                "include_raw_json": include_raw_json,
                "output_path": str(output.expanduser()) if output else None,
            }
        )
    except ToolValidationError as exc:
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    _print_json(result)


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
    )
    if worthy_only:
        data = [record for record in data if service.store.is_memory_worthy(record)]
    _print_json(data)


@memory_app.command("show", help='Show one stored run in full (envelope, artifacts, recorded AI answer). 查看单条运行记录。')
def memory_show(
    run_id: str = typer.Argument(..., help="Exact run id to display."),
    include_payload: bool = typer.Option(True, "--include-payload/--no-include-payload", help="Embed saved JSON payloads in the output."),
) -> None:
    service = _service()
    data = service.store.query_runs(run_id=run_id, limit=1, include_payload=include_payload)
    if not data:
        typer.echo(json.dumps({"ok": False, "code": "memory.run.not_found", "message": f"Run not found: {run_id}", "details": {}}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    _print_json(data[0])


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
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    except ValueError as exc:
        typer.echo(json.dumps({"ok": False, "code": "memory.answer.unknown_run", "message": str(exc), "details": {}}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    _print_json(result)


if __name__ == "__main__":
    app()
