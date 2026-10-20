from __future__ import annotations

import json
import os
import re
import shutil
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
from horosa_skill.client_tools import zero_install_wheel_url
from horosa_skill.engine.registry import TOOL_DEFINITIONS, resolve_tool_name
from horosa_skill.errors import RuntimeError, ToolValidationError, bilingual
from horosa_skill.runtime import HorosaRuntimeManager
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces.mcp_server import COMPACT_SURFACE_TOOL_COUNT, FACADE_TOOL_COUNT
from horosa_skill.surfaces.mcp_server import run_mcp_server
from horosa_skill.tracing import TraceRecorder
from horosa_skill.client_config.audit import (
    _client_check_report,
    _normalize_client_entry,
)
from horosa_skill.client_config.locations import (
    _CLIENT_NAMES,
    _CLIENT_RESTART_HINTS,
    _codex_env_roots,
    _preferred_config_path,
    _project_root,
)
from horosa_skill.client_config.merge import (
    _MERGEABLE_ROOT_KEYS,
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
    _cache_wheel,
    _format_cli_command,
    _resolve_skill_root,
)
from horosa_skill.surfaces.doctor import (
    STATUS_BUDGET_SECONDS,
    _SETUP_NETWORK_TIMEOUT_SECONDS,
    _doctor_report,
    _explain_lines,
)
from horosa_skill.surfaces.openclaw_smoke import (
    _friendly_runtime_error_payload,
    _openclaw_setup_command,
    _setup_summary,
    _timed_call,
)
from horosa_skill.surfaces import doctor as doctor_checks
from horosa_skill.surfaces import openclaw_smoke

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


def _runtime_manager(settings: Settings | None = None) -> HorosaRuntimeManager:
    return HorosaRuntimeManager(settings or Settings.from_env())


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


def _package_root() -> Path:
    return Path(__file__).resolve().parents[3]


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


def _install_progress_printer():
    """stderr 下载进度（stdout 保持纯 JSON 契约）：TTY 用行内百分比，非 TTY 每 ~50MB 一行。"""
    state = {"last": 0}
    is_tty = sys.stderr.isatty()

    def _progress(done: int, total: int | None) -> None:
        if is_tty:
            if total:
                pct = done * 100 // total
                sys.stderr.write(f"\r下载 runtime：{done // (1024*1024)}MB / {total // (1024*1024)}MB（{pct}%）")
            else:
                sys.stderr.write(f"\r下载 runtime：{done // (1024*1024)}MB")
            sys.stderr.flush()
            if total and done >= total:
                sys.stderr.write("\n")
        else:
            if done - state["last"] >= 50 * 1024 * 1024:
                state["last"] = done
                suffix = f" / {total // (1024*1024)}MB" if total else ""
                sys.stderr.write(f"下载 runtime：{done // (1024*1024)}MB{suffix}\n")
                sys.stderr.flush()

    return _progress


def _run_install(archive: str | None, manifest_url: str | None, force: bool, *, mode: str) -> None:
    settings = Settings.from_env()
    manager = _runtime_manager(settings)
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
    manager = _runtime_manager(settings)
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
    report = _doctor_report(settings, _runtime_manager(settings), probe_network=bool(_opt(probe_network, False)))
    if _opt(explain, False):
        for line in _explain_lines(report):
            typer.echo(line, err=True)
    _print_json(report)


# ---------------------------------------------------------------------------
# `horosa-skill setup --client <target>`（v0.38.0 B4）：一条命令接入任意 MCP 客户端。
# 步骤固定、逐步记录、失败包结构化：network_probe → install → config → skill → doctor → client_check → stdio_probe → next_steps。
# 🔴 第 3 步（config）之前失败保证 `config_untouched: true`；写过配置的失败包带 `backup_path`。
# v0.41.0 第 4 步 skill：把 horosa-agent skill 装进该客户端读的 skills 目录（只建议性：装不上不让 setup 失败，next_steps 说清楚）。
# 输出契约冻结在 tests/test_cli_output_contract.py；行为在 tests/test_setup_command.py。
# ---------------------------------------------------------------------------

_SETUP_STEPS = ("network_probe", "install", "config", "skill", "doctor", "client_check", "stdio_probe", "next_steps")
# uvx-wheel 首跑要下载 wheel 与依赖（顺带焐热 uvx 缓存，客户端首次启动就快了）；uv 形态通常 5–10 s。
_SETUP_STDIO_TIMEOUT_SECONDS = 300.0
_SETUP_TRY_PROMPT = (
    "在客户端里试一句：「用八字看看 1990-01-01 12:00 北京出生的人」——Horosa 会先追问缺失的设置"
    "（时区 / 性别 / 流派），确认后才起盘。"
)


class _SetupFailure(Exception):
    """`setup` 某一步失败：payload 原样写到 stderr，退出码 2。"""

    def __init__(self, payload: dict[str, Any]) -> None:
        super().__init__(str(payload.get("message") or payload.get("code") or "setup failed"))
        self.payload = payload


# Codex 只把这些系统变量交给 MCP server（其余一律不转发，HOROSA_* 得写进 env 表）。探针按同样的形状起 server，
# 才抓得住「终端里 doctor ready、Codex 里全是 not_installed」（server 算出的 runtime 根和终端里装的不一样）。
_CODEX_PASSTHROUGH_ENV = (
    "PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "SystemRoot", "TEMP", "TMP", "LANG", "LC_ALL", "COMSPEC",
    "PATHEXT", "APPDATA", "LOCALAPPDATA", "USERNAME", "USER", "SHELL", "TERM", "TZ",
)


def _client_probe_env(client_key: str, extra_env: dict[str, str]) -> dict[str, str]:
    """stdio 探针用的环境：Codex 形状 = 最小系统变量 ∪ 配置里的 env 表；其余客户端继承整个环境。"""
    if client_key == "codex":
        base = {key: os.environ[key] for key in _CODEX_PASSTHROUGH_ENV if key in os.environ}
        return {**base, **extra_env}
    # v0.41.0：Copilot CLI 只转发 PATH——探针按同样的最坏形状起 server，才证明得了「env 表里写的够用」。
    narrowed = clients_extra.probe_env(client_key, extra_env)
    if narrowed is not None:
        return narrowed
    return {**os.environ, **extra_env}


def _probe_runtime_mismatch(probe: dict[str, Any], settings: Settings) -> str | None:
    """探针读到的 `horosa://runtime/status` 与宿主 settings 对不上 → 客户端起的 server 用的是另一套目录。"""
    status = probe.get("runtime_status")
    if not isinstance(status, dict) or not status.get("runtime_root"):
        return None
    try:
        theirs = Path(str(status["runtime_root"])).expanduser().resolve()
        ours = settings.runtime_root.expanduser().resolve()
    except OSError:
        return None
    if theirs != ours:
        return (
            f"客户端将要起的 server 算出的 runtime 根是 {theirs}，而本机（终端）用的是 {ours}：环境变量没有传到客户端"
            "（Codex 不转发 shell 环境；GUI 客户端不读 shell 配置）。请把 HOROSA_RUNTIME_ROOT / HOROSA_SKILL_DATA_DIR"
            " 写进该客户端配置的 env 表，或统一用默认目录。"
        )
    return None


def _stdio_probe(*, command: str, args: list[str], env: dict[str, str], timeout: float, cwd: str | None = None) -> dict[str, Any]:
    """用客户端**将要执行的那条命令**真起一次 MCP server（stdio），握手 + 列工具。

    进程内 `create_mcp_server()` 证明不了「客户端能起它」：绝对路径对不对、uvx 缓存能不能建、
    Windows 上 spawn 走不走得通，只有真 spawn 才知道。stderr 收进临时文件，失败时带尾巴回报。
    """
    import tempfile

    import anyio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command=command, args=args, env=env, cwd=cwd)

    with tempfile.TemporaryFile("w+", encoding="utf-8", errors="replace") as errlog:

        async def body() -> dict[str, Any]:
            with anyio.fail_after(timeout):
                async with stdio_client(params, errlog=errlog) as (read, write):
                    async with ClientSession(read, write) as session:
                        init = await session.initialize()
                        tools = await session.list_tools()
                        runtime_status: dict[str, Any] | None = None
                        try:
                            from pydantic import AnyUrl

                            resource = await session.read_resource(AnyUrl("horosa://runtime/status"))
                            text = next((c.text for c in resource.contents if getattr(c, "text", None)), None)
                            parsed = json.loads(text) if text else None
                            runtime_status = parsed if isinstance(parsed, dict) else None
                        except Exception:  # noqa: BLE001 - 探针起的可能是客户端钉住的旧版 server：
                            # 资源 horosa://runtime/status 自 v0.38.1 才有。等最低受支持版本都带它，这层就能去掉。
                            runtime_status = None
                        return {
                            "ok": True,
                            "tools": len(tools.tools),
                            "server_name": init.serverInfo.name,
                            "server_version": init.serverInfo.version,
                            "runtime_status": runtime_status,
                        }

        try:
            result = anyio.run(body)
        except Exception as exc:  # noqa: BLE001 - 任何失败都要连 stderr 尾巴一起回报
            result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300]}
        try:
            errlog.seek(0)
            result["stderr_tail"] = errlog.read()[-2000:]
        except (OSError, ValueError):
            result["stderr_tail"] = ""
    return result


# uv 自己的报错是英文且不本地化；Rust io::Error 的 `(os error 32)`（ERROR_SHARING_VIOLATION）也不本地化；
# 夹在中间的系统描述随 Windows 显示语言变（"being used by another process" / 「另一个程序正在使用此文件」）——只锚两头。
_WINDOWS_FILE_LOCK_RE = re.compile(
    r"failed to remove file [`'\"](?P<path>[^`'\"\r\n]+)[`'\"]\s*:[^\r\n]*?\(os error 32\)",
    re.IGNORECASE,
)


def _diagnose_probe_stderr(stderr_tail: str) -> dict[str, Any] | None:
    """把 stdio 探针 stderr 里**可识别的环境性原因**翻成可操作的诊断；认不出返回 None（stderr_tail 原样保留）。

    Windows 独有（v0.39.0 维护机复验撞到）：一个已挂着的 horosa MCP 会话（`uv run … serve`）占着 venv 里的
    `Scripts\\horosa-skill.exe`（或已加载的 .pyd）；客户端这条 `uv run` 要先把 venv 同步到当前版本，删不掉被占文件
    → uv 在 MCP server 启动前就退出，stderr 只剩一屏构建噪声。macOS / Linux 能替换运行中的文件，不会遇到。
    """
    match = _WINDOWS_FILE_LOCK_RE.search(stderr_tail or "")
    if not match:
        return None
    import ntpath

    locked = ntpath.normpath(match.group("path"))  # uv 打印的是 `…\\site-packages\\../../Scripts/x.exe` 混写
    return {
        "cause": "windows_file_in_use",
        "locked_file": locked,
        "explanation": bilingual(
            f"Windows 文件锁：`{locked}` 正被另一个进程占用（通常是已挂着的 horosa MCP 会话——Claude Code / "
            "Claude Desktop / Cursor 用 `uv run … serve` 起的那一份）。客户端这条命令要先把 venv 同步到当前版本，"
            "而 Windows 不允许删除或覆盖运行中的文件，于是 MCP server 还没启动就失败了。",
            f"Windows file lock: `{locked}` is held by another process (usually an already-running horosa MCP session "
            "that Claude Code / Claude Desktop / Cursor started via `uv run … serve`). The client's command must first "
            "sync the venv to the current version, and Windows does not allow deleting or overwriting a file in use, "
            "so the MCP server failed before it started.",
        ),
        "next_action": bilingual(
            "关掉（或重启）挂着 horosa 的 MCP 客户端会话，再重跑本命令；终端里直接 `uv run horosa-skill …` 撞到同一"
            "错误时，可临时加 `UV_NO_SYNC=1`（依赖没变时安全）。macOS / Linux 不受影响。",
            "Close (or restart) the MCP client sessions that have horosa attached, then re-run this command; for a "
            "terminal `uv run horosa-skill …` hitting the same error, `UV_NO_SYNC=1` is a safe stopgap when "
            "dependencies did not change. macOS / Linux are unaffected.",
        ),
    }


def _claude_mcp_add(command: list[str]) -> subprocess.CompletedProcess[str]:
    """执行 `claude mcp add …`（单独成函数：测试用替身，不真调 claude）。"""
    return subprocess.run(
        command, capture_output=True, text=True, timeout=60, check=False, encoding="utf-8", errors="replace"
    )


def _setup_skill_step(
    client_key: str | None, *, enabled: bool, skill_dir: Path | None, plan_only: bool, announce: Any,
) -> dict[str, Any]:
    """`setup` 第 4 步：把 horosa-agent skill 装进该客户端读的 skills 目录（v0.41.0）。

    🔴 只建议性：任何失败都记进 `targets[*].error` + `notes`，step 仍 ok——MCP 配置已写好，server 的 instructions
    同样带着「先问后调 / 禁手算」；不能因为 skills 目录写不进去就让整条接入报失败。
    """
    from horosa_skill import skill_install

    if not enabled:
        return {"ok": True, "skipped": True, "reason": "--no-skill", "summary": "skill 未安装（--no-skill）"}
    if skill_dir is not None:
        targets = [skill_dir.expanduser()]
    elif client_key is None:
        targets = [skill_install.shared_skills_dir()]  # `client skill` 不指定客户端 = 共享目录（读它的客户端最多）
    else:
        targets = skill_install.client_skill_dirs(client_key)
    if not targets:
        step: dict[str, Any] = {
            "ok": True, "skipped": True, "reason": f"{client_key} 不从本机文件夹读 skill",
            "summary": "该客户端不读本机 skill 文件夹（规则随 MCP server 的 instructions 下发）",
        }
        if client_key == "claude-desktop":
            # Claude Desktop 的聊天 / Cowork 只收界面里上传的 ZIP——打好包、告诉用户在哪上传（它的 Code 标签页 = Claude Code）。
            try:
                archive = skill_install.export_zip() if not plan_only else None
            except OSError as exc:
                step["notes"] = [f"skill ZIP 没打出来（{type(exc).__name__}: {exc}）。"]
                return step
            step["zip"] = str(archive) if archive else None
            step["notes"] = [
                ("skill 打包成 " + str(archive) + "：" if archive else "（dry-run：不打包）")
                + "在 Claude Desktop 里 Customize > Skills > + > Create skill > Upload a skill 上传它（需开启 Settings > Capabilities > "
                "Code execution and file creation）。Code 标签页读的是 ~/.claude/skills，用 `setup --client claude-code` 装。"
            ]
            step["summary"] = "skill 已打包成 ZIP（需在 Claude Desktop 里上传）" if archive else step["summary"]
        return step
    announce(("计划" if plan_only else "安装") + " horosa-agent skill → " + ", ".join(str(t) for t in targets))
    results: list[dict[str, Any]] = []
    notes: list[str] = []
    for target in targets:
        try:
            result = skill_install.install_skill(target, dry_run=plan_only)
        except (OSError, FileNotFoundError) as exc:
            result = {"path": str(target / skill_install.SKILL_NAME), "action": "failed", "error": f"{type(exc).__name__}: {exc}"[:300]}
            notes.append(f"skill 没装上（{result['error']}）：MCP 已可用；可稍后重跑本命令，或手动把 skill 复制到 {target}。")
        results.append(result)
        action = result.get("action")
        if action in {"installed", "updated", "adopted"}:
            notes.append(f"horosa-agent skill 已装到 {result['path']}：新开一个会话，agent 才会读到「先问后调 / 读快照 / 禁手算」规则。")
        if result.get("backup"):
            notes.append(f"你改过的旧 skill 备份在 {result['backup']}。")
        if action == "skipped":
            notes.append(f"{result['path']} 已存在且不是本工具装的（{result.get('reason')}），没有覆盖。")
        if action in {"installed", "updated", "adopted", "unchanged"} and not plan_only:
            for other in skill_install.duplicate_copies(target):
                notes.append(
                    f"另有一份在 {other}：Cursor / VS Code / Codex 同时读 ~/.agents/skills 与 ~/.claude/skills，会列出两份同名 skill"
                    "（Claude Code 只读后者、其余多数只读前者——只用一类客户端的话删掉另一份即可）。"
                )
    done = [r for r in results if r.get("action") in {"installed", "updated", "adopted", "unchanged"}]
    summary = (
        "skill 计划安装" if plan_only
        else "skill 已是最新" if done and all(r.get("action") == "unchanged" for r in done)
        else "skill 已安装" if done
        else "skill 未安装（见 next_steps）"
    )
    return {"ok": True, "skill": skill_install.SKILL_NAME, "plan_only": plan_only, "targets": results,
            "notes": notes, "summary": summary, **({"skipped": True, "reason": "dry-run / --no-write"} if plan_only else {})}


def _default_setup_launcher(skill_root: Path | None) -> str:
    """源码 checkout 里默认 `uv`；wheel / uvx 装出来的包旁边没有 pyproject.toml → `uvx-wheel`。"""
    try:
        _resolve_skill_root(skill_root or _package_root())
    except typer.BadParameter:
        return "uvx-wheel"
    return "uv"


def _setup_command_text(client: str, *, launcher: str, config: Path | None, extra: tuple[str, ...] = ()) -> str:
    prefix = ["uv", "run", "horosa-skill"] if launcher == "uv" else ["horosa-skill"]
    parts = [*prefix, "setup", "--client", client]
    if config is not None:
        parts += ["--config", str(config)]
    return _format_cli_command([*parts, *extra])


def _run_setup(
    *,
    client: str,
    launcher: str | None,
    surface: str,
    config: Path | None,
    scope: str,
    server_name: str,
    skill_root: Path | None,
    dry_run: bool,
    skip_install: bool,
    archive: str | None,
    manifest_url: str | None,
    probe_network: bool,
    stdio_probe: bool,
    write: bool,
    cache_wheel: bool = True,
    skill: bool = True,
    skill_dir: Path | None = None,
) -> dict[str, Any]:
    from horosa_skill.runtime.manager import _platform_key

    client_key = client.strip().lower()
    if client_key not in _CLIENT_NAMES:
        raise typer.BadParameter(f"未知客户端 `{client}`。可选：{', '.join(_CLIENT_NAMES)}")
    if scope not in {"auto", "project", "user"}:
        raise typer.BadParameter("`--scope` must be `auto`, `project` or `user`.")
    launcher_key = (launcher or _default_setup_launcher(skill_root)).strip().lower()
    root = skill_root or _package_root()
    settings = Settings.from_env()
    manager = _runtime_manager(settings)
    steps: dict[str, dict[str, Any]] = {}
    state: dict[str, Any] = {"config_untouched": True, "backup_path": None}
    total = len(_SETUP_STEPS)

    def fail(step: str, code: str, message: str, details: dict[str, Any] | None = None, *, retry_extra: tuple[str, ...] = ()) -> None:
        raise _SetupFailure({
            "ok": False,
            "step": step,
            "code": code,
            "message": message,
            "details": details or {},
            "config_untouched": state["config_untouched"],
            "backup_path": state["backup_path"],
            "retry_command": _setup_command_text(client_key, launcher=launcher_key, config=config, extra=retry_extra),
            "client": client_key,
            "steps": steps,
        })

    def announce(index: int, name: str, text: str) -> None:
        typer.echo(f"[{index}/{total}] {name}: {text}", err=True)

    # ---- 1 network_probe
    manifest_location = manifest_url or settings.runtime_manifest_url or settings.default_runtime_manifest_url
    if dry_run or skip_install or archive or not probe_network:
        reason = "dry-run" if dry_run else "--skip-install" if skip_install else "--archive（离线安装）" if archive else "--no-probe-network"
        steps["network_probe"] = {"ok": True, "skipped": True, "reason": reason, "manifest_url": manifest_location}
    else:
        announce(1, "network_probe", f"HEAD {manifest_location}（{_SETUP_NETWORK_TIMEOUT_SECONDS:.0f} s，镜像优先）")
        probe, seconds = _timed_call(lambda: doctor_checks._probe_manifest_url(manifest_location))
        steps["network_probe"] = {"seconds": seconds, **probe}
        if not probe["ok"]:
            fail(
                "network_probe", "setup.network_unreachable",
                "清单 URL 经所有镜像都取不到，离线 runtime 装不了（本机配置一个字都没动）。",
                {
                    "manifest_url": manifest_location, "attempts": probe["attempts"],
                    "next_action": (
                        "设 HOROSA_RUNTIME_MIRROR=<镜像前缀> 重跑；或 `--archive <本地归档>` 离线安装；"
                        "或 `--no-probe-network` 跳过预检直接下载。三条路见 docs/INSTALL_RESTRICTED_NETWORK.md。"
                    ),
                },
                retry_extra=("--no-probe-network",),
            )

    # ---- 2 install
    if dry_run or skip_install:
        steps["install"] = {
            "ok": True, "skipped": True, "reason": "dry-run" if dry_run else "--skip-install",
            "would_install_from": archive or manifest_location,
            "platform": settings.runtime_platform or _platform_key(), "runtime_root": str(settings.runtime_root),
        }
    else:
        announce(2, "install", "安装 / 校验离线 runtime（已是最新版则秒退；约 730MB 下载、解压后约 2GB）…")
        try:
            result, seconds = _timed_call(
                lambda: manager.install(archive=archive, manifest_url=manifest_url, progress=_install_progress_printer())
            )
        except RuntimeError as exc:
            fail("install", exc.code, str(exc), exc.details)
        except OSError as exc:
            fail("install", "runtime.install_io_error", str(exc), {})
        steps["install"] = {
            "ok": True, "seconds": seconds, "changed": result.get("changed"),
            "skipped_download": bool(result.get("skipped_download")), "platform": result.get("platform"),
            "platform_fallback": result.get("platform_fallback"), "warnings": result.get("warnings") or [],
            "version": (result.get("manifest") or {}).get("version"), "runtime_root": result.get("runtime_root"),
        }

    # ---- 3 config
    announce(3, "config", f"生成 {client_key} 配置（launcher={launcher_key}）…")
    try:
        wheel_source: str | None = None
        wheel_cache_note: str | None = None
        if launcher_key == "uvx-wheel" and cache_wheel and not dry_run:
            # v0.38.1 C15：先把 wheel 落到 ~/.horosa/wheels/，配置里写本地路径 → 客户端冷启动零网络、离线可起。
            from horosa_skill.runtime.mirrors import preferred_mirror_url

            announce(3, "config", "预下载 wheel 到 ~/.horosa/wheels/（配置里写本地路径；--no-cache-wheel 可跳过）…")
            cached, wheel_cache_note = _cache_wheel(preferred_mirror_url(zero_install_wheel_url()))
            wheel_source = str(cached) if cached else None
        payload, stdio_command, surface_env = _build_client_config_payload(
            format_name=client_key, skill_root=root, server_name=server_name, launcher=launcher_key, surface=surface,
            wheel_source=wheel_source,
        )
        if wheel_cache_note:
            payload.setdefault("warnings", []).append(wheel_cache_note)
    except typer.BadParameter as exc:
        fail("config", "setup.config_build_failed", str(exc), {"launcher": launcher_key, "skill_root": str(root)})
    target: Path | None = config.expanduser().resolve() if config is not None else None
    mode = "merge"
    add_command: list[str] | None = None
    if client_key == "claude-code" and target is None:
        project_mcp = _project_root() / ".mcp.json"
        if scope == "project" or (scope == "auto" and project_mcp.is_file()):
            target = project_mcp
        else:
            # 用户级注册走官方命令（可 `claude mcp remove` 回退），不去手改 ~/.claude.json 这份状态文件。
            mode = "claude-mcp-add"
            claude_bin = shutil.which("claude")
            env_flags = [item for key, value in surface_env.items() for item in ("-e", f"{key}={value}")]
            add_command = [claude_bin or "claude", "mcp", "add", "--scope", "user", *env_flags, server_name, "--", *stdio_command]
    elif target is None and payload.get("config_mode") == "printed":
        # v0.41.0：没有文档化用户级配置文件的客户端（TRAE）——打印一键导入链接与可粘贴 JSON，不猜路径写文件。
        mode = "printed"
    elif target is None:
        target = _preferred_config_path(client_key)
    declared_root = payload.get("root_key")
    root_key = "toml_stdio" if client_key == "codex" else (
        declared_root if isinstance(declared_root, str) and isinstance(payload.get(declared_root), dict)
        else next((key for key in _MERGEABLE_ROOT_KEYS if isinstance(payload.get(key), dict)), None)
    )
    config_step: dict[str, Any] = {
        "mode": mode, "path": str(target) if target is not None else None,
        "server_block": payload.get(root_key) if root_key else None,
        "launcher": payload["launcher"], "tool_surface": payload["tool_surface"],
    }
    if payload.get("warnings"):
        config_step["warnings"] = payload["warnings"]
    if add_command is not None:
        config_step["command"] = _format_cli_command(add_command)
    if mode == "printed" and add_command is None:
        config_step.update({key: payload[key] for key in ("deep_link", "deep_link_cn", "paste_json", "note") if key in payload})
    if dry_run or not write:
        config_step.update({"ok": True, "skipped": True, "reason": "dry-run" if dry_run else "--no-write"})
    elif mode == "printed" and add_command is None:
        config_step.update({"ok": True, "executed": False})
    elif mode == "claude-mcp-add":
        assert add_command is not None
        if shutil.which("claude") is None:
            mode = "printed"
            config_step.update({
                "ok": True, "mode": mode, "executed": False,
                "note": "`claude` 不在 PATH 上：把 command 复制到装了 Claude Code 的终端里执行即可（或加 --scope project 写项目 .mcp.json）。",
            })
        else:
            try:
                completed, seconds = _timed_call(lambda: _claude_mcp_add(add_command))
            except (OSError, subprocess.TimeoutExpired) as exc:
                fail("config", "setup.claude_mcp_add_failed", f"`claude mcp add` 没跑起来：{exc}", {"command": config_step["command"]})
            state["config_untouched"] = False
            rollback = f"claude mcp remove --scope user {server_name}"
            if completed.returncode != 0:
                fail(
                    "config", "setup.claude_mcp_add_failed", "`claude mcp add` 退出码非 0。",
                    {"command": config_step["command"], "returncode": completed.returncode,
                     "stdout": (completed.stdout or "")[-500:], "stderr": (completed.stderr or "")[-500:], "rollback": rollback},
                )
            config_step.update({"ok": True, "executed": True, "seconds": seconds, "rollback": rollback,
                                "stdout": (completed.stdout or "").strip()[-500:]})
    else:
        assert target is not None
        try:
            written, seconds = _timed_call(lambda: _merge_client_config(target, payload))
        except typer.BadParameter as exc:
            fail("config", "setup.config_merge_refused", str(exc), {"path": str(target)})
        state["config_untouched"] = False
        state["backup_path"] = written.get("backup")
        config_step.update({"ok": True, "seconds": seconds, "written": written, "backup": written.get("backup")})
    steps["config"] = config_step

    # ---- 4 skill
    steps["skill"] = _setup_skill_step(client_key, enabled=skill, skill_dir=skill_dir, plan_only=dry_run or not write,
                                       announce=lambda text: announce(4, "skill", text))

    # ---- 5 doctor
    announce(5, "doctor", "体检…")
    report, seconds = _timed_call(lambda: _doctor_report(settings, manager))
    issues = [str(item) for item in report.get("issues") or []]
    installed = report.get("installed") is True
    ready = (
        installed
        and set(issues) <= {"services:not_running"}
        and report.get("platform_supported") is not False
        and not (report.get("port_conflicts") or [])
    )
    advisory = dry_run or skip_install  # 没装就不该因为「没装」失败；结果照报
    steps["doctor"] = {
        "ok": bool(ready or advisory), "ready": bool(ready), "advisory": advisory, "seconds": seconds,
        "status": report.get("status"), "installed": installed, "issues": issues,
        "warnings": [w.get("code") for w in report.get("warnings") or [] if isinstance(w, dict)],
        "platform_supported": report.get("platform_supported"), "host_platform": report.get("host_platform"),
        "payload_platform": report.get("payload_platform"), "emulated": report.get("emulated"),
        "user_summary": report.get("user_summary"), "next_action": report.get("next_action"),
    }
    if not ready and not advisory:
        fail(
            "doctor", "setup.doctor_not_ready", str(report.get("user_summary") or "doctor reports issues."),
            {"issues": issues, "next_action": report.get("next_action"), "port_conflicts": report.get("port_conflicts") or [],
             "platform_supported": report.get("platform_supported")},
        )

    # ---- 6 client_check
    if dry_run or not write or mode == "printed":
        reason = "dry-run" if dry_run else "--no-write" if not write else (
            "配置未落盘（claude 不在 PATH，命令已打印）" if client_key == "claude-code" else "该客户端没有可写的配置文件（导入链接 / 粘贴 JSON 已打印）"
        )
        steps["client_check"] = {"ok": True, "skipped": True, "reason": reason}
    else:
        announce(6, "client_check", "回读磁盘上的配置…")
        check_path = target if mode == "merge" else None
        check, seconds = _timed_call(lambda: _client_check_report([client_key], check_path))
        findings = [f for r in check["clients"] for f in r["findings"] if f.get("entry")]
        searched = [item for r in check["clients"] for item in r["searched"]]
        check_ok = bool(findings) and check["problems"] == 0
        steps["client_check"] = {"ok": check_ok, "seconds": seconds, "configured": bool(findings),
                                 "problems": check["problems"], "findings": findings, "searched": searched}
        if not check_ok:
            fail("client_check", "setup.client_check_failed", "写完回读，配置里的 horosa 条目缺失或有问题。",
                 {"findings": findings, "searched": searched})

    # ---- 7 stdio_probe
    if dry_run or not stdio_probe:
        steps["stdio_probe"] = {"ok": True, "skipped": True, "reason": "dry-run" if dry_run else "--no-stdio-probe"}
    else:
        announce(7, "stdio_probe", "用客户端将要执行的命令真起一次 MCP server（stdio，不起离线 runtime）…")
        expected = int(payload["tool_surface"]["tools"])
        probe_args = [*stdio_command[1:], "--skip-runtime-start"]
        # 🔴 v0.38.1 C14：按**客户端的形状**起——Codex 只给最小环境（∪ 配置里的 env 表），其余客户端继承整个环境；
        # cwd = 项目根（uv 形态 = Codex 的 cwd）。再读 horosa://runtime/status，抓「server 算出的 runtime 根 ≠ 终端里的」。
        configured_env = {**surface_env, **(_codex_env_roots() if client_key == "codex" else {})}
        # v0.41.0：条目里**实际写着**的 env 才是客户端会交给 server 的（Copilot CLI 的 HOME 与两个 runtime 根、TRAE 的超时变量）。
        # 只给 Codex 补根的旧写法，在 Copilot CLI 上把「配置写对了」测成 runtime_mismatch（首次真探针实跑抓到）。
        written = (payload.get(root_key) or {}).get(server_name) if root_key and root_key != "toml_stdio" else None
        if isinstance(written, dict):
            configured_env.update({str(k): str(v) for k, v in (_normalize_client_entry(written).get("env") or {}).items()})
        probe_env = _client_probe_env(client_key, configured_env)
        probe_cwd = str(root) if (launcher_key == "uv" and root is not None) else str(_project_root())
        probe, seconds = _timed_call(
            lambda: _stdio_probe(command=stdio_command[0], args=probe_args, env=probe_env,
                                 timeout=_SETUP_STDIO_TIMEOUT_SECONDS, cwd=probe_cwd)
        )
        mismatch = _probe_runtime_mismatch(probe, settings) if probe.get("ok") else None
        probe_ok = probe.get("ok") is True and probe.get("tools") == expected and mismatch is None
        steps["stdio_probe"] = {"ok": probe_ok, "seconds": seconds, "expected_tools": expected, "env_shape": client_key if client_key == "codex" else "inherit",
                                "cwd": probe_cwd, "command": _format_cli_command([stdio_command[0], *probe_args]), **probe}
        if mismatch:
            steps["stdio_probe"]["runtime_mismatch"] = mismatch
            fail("stdio_probe", "setup.stdio_probe_runtime_mismatch", mismatch,
                 {**probe, "host_runtime_root": str(settings.runtime_root), "command": steps["stdio_probe"]["command"]})
        if not probe_ok:
            # 起不来时先认环境性原因（Windows 文件锁），认出来就给人话 + 可执行的下一步，而不是一屏 uv 构建噪声。
            diagnosis = None if probe.get("ok") else _diagnose_probe_stderr(str(probe.get("stderr_tail") or ""))
            if diagnosis:
                steps["stdio_probe"]["diagnosis"] = diagnosis
            fail("stdio_probe", "setup.stdio_probe_failed",
                 diagnosis["explanation"] if diagnosis else "客户端将要执行的命令起不来 MCP server，或列出的工具数不对。",
                 {**probe, "expected_tools": expected, "command": steps["stdio_probe"]["command"],
                  **({"diagnosis": diagnosis} if diagnosis else {})})

    # ---- 8 next_steps
    prefix = "uv run horosa-skill" if launcher_key == "uv" else "horosa-skill"
    next_steps: list[str] = []
    if mode == "printed" and config_step.get("command"):
        next_steps.append(f"先执行：{config_step['command']}")
    next_steps.append(_CLIENT_RESTART_HINTS[client_key])
    if client_key in clients_extra.EXTRA_CLIENTS:
        next_steps.extend(clients_extra.EXTRA_CLIENTS[client_key].notes)
    next_steps.extend(steps["skill"].get("notes") or [])
    if issues == ["services:not_running"]:
        next_steps.append(f"离线 runtime 已装好，客户端首次调用时自动启动（冷启动 10–45 s）；想现在就起：`{prefix} runtime start`。")
    elif not installed:
        next_steps.append(f"离线 runtime 还没装：`{prefix} install`（或不带 --skip-install 重跑 setup）。")
    for warning in report.get("warnings") or []:
        if isinstance(warning, dict):
            next_steps.append(f"doctor 提示 {warning.get('code')}：{warning.get('fix') or warning.get('detail') or ''}".rstrip("："))
    for warning in steps["install"].get("warnings") or []:
        if isinstance(warning, dict) and warning.get("message"):
            next_steps.append(str(warning["message"]))
    next_steps.append(_SETUP_TRY_PROMPT)
    next_steps.append(
        f"活体检查：`{prefix} selfcheck`（起 runtime → 起一张盘 → 存 → 读回）；"
        f"不对劲先跑 `{prefix} client check --client {client_key}` 与 `{prefix} doctor`。"
    )
    steps["next_steps"] = {"ok": True, "items": next_steps}

    install_text = (
        "runtime 未处理（dry-run）" if dry_run else "runtime 未处理（--skip-install）" if skip_install
        else "runtime 已是最新" if steps["install"].get("skipped_download") else "runtime 已安装"
    )
    config_text = (
        f"配置计划写到 {target}" if (dry_run or not write) and target is not None
        else f"配置已写入 {target}" if mode == "merge" and target is not None
        else "已执行 claude mcp add（用户级）" if mode == "claude-mcp-add" and steps["config"].get("executed")
        else "注册命令已打印（claude 不在 PATH）" if mode == "printed" and client_key == "claude-code"
        else "导入链接 / 粘贴 JSON 已打印（该客户端没有可写的配置文件）" if mode == "printed"
        else "配置未落盘"
    )
    probe_text = (
        f"stdio 起服务成功（{steps['stdio_probe'].get('tools')} 个工具）" if not steps["stdio_probe"].get("skipped")
        else "stdio 探测已跳过"
    )
    skill_text = steps["skill"].get("summary") or "skill 未处理"
    ok = all(step.get("ok") for step in steps.values())
    return {
        "ok": ok,
        "client": client_key,
        "launcher": payload["launcher"],
        "surface": payload["tool_surface"]["mode"],
        "tools": payload["tool_surface"]["tools"],
        "config_path": str(target) if target is not None else None,
        "config_mode": mode,
        "dry_run": dry_run,
        "steps": steps,
        "next_steps": next_steps,
        "summary": f"{client_key}：{install_text}；{config_text}；{skill_text}；{probe_text}。",
        "recheck_command": f"{prefix} client check --client {client_key}",
    }


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
    manager = _runtime_manager(settings)
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
    manager = _runtime_manager(settings)
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
    manager = _runtime_manager(settings)
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
    manager = _runtime_manager(settings)
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
    manager = _runtime_manager(settings)
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
    manager = _runtime_manager(settings)
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
        _package_root(),
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
        _package_root(),
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
        _package_root(),
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
        manager = _runtime_manager(settings)
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
        script_path = _package_root() / "scripts" / "run_openclaw_full_self_check.py"
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
