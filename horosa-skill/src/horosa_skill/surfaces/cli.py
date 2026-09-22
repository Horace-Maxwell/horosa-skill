from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from importlib.metadata import PackageNotFoundError, version as package_version
from contextlib import contextmanager
from pathlib import Path, PureWindowsPath
from typing import Mapping, Any, Optional

import typer

from horosa_skill import __version__
from horosa_skill.agent_guidance import build_agent_guidance, validate_agent_preflight
from horosa_skill.config import Settings
from horosa_skill.benchmark import run_benchmark
from horosa_skill.client_tools import (
    extract_json_value,
    isolated_data_dir,
    isolated_runtime_ports,
    isolated_runtime_root,
    resolve_mcporter_command,
    resolve_uv_command,

    resolve_uvx_command,
    wheel_asset_name, zero_install_wheel_url,
)
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.errors import RuntimeError, ToolValidationError, bilingual
from horosa_skill.runtime import HorosaRuntimeManager
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces.mcp_server import COMPACT_SURFACE_TOOL_COUNT, FACADE_TOOL_COUNT
from horosa_skill.surfaces.mcp_server import run_mcp_server
from horosa_skill.tracing import TraceRecorder

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


def _resolve_skill_root(path: Path) -> Path:
    candidate = path.expanduser().resolve()
    if (candidate / "pyproject.toml").exists():
        return candidate
    nested = candidate / "horosa-skill"
    if (nested / "pyproject.toml").exists():
        return nested
    raise typer.BadParameter("Path must point to the horosa-skill package directory or the repo root that contains it.")


def _build_openclaw_server_block(
    *,
    skill_root: Path,
    isolate_home: Path | None,
) -> dict[str, Any]:
    skill_root = skill_root.expanduser().resolve()
    uv_command = resolve_uv_command()
    serve_args = [
        "run",
        "--directory",
        str(skill_root),
        "horosa-skill",
        "serve",
        "--transport",
        "stdio",
    ]
    if isolate_home is None:
        return {
            "command": uv_command[0],
            "args": [*uv_command[1:], *serve_args],
            "cwd": str(skill_root),
        }

    home_dir = isolate_home.expanduser().resolve()
    server_block = {
        "command": uv_command[0],
        "args": [*uv_command[1:], *serve_args],
        "cwd": str(skill_root),
        "env": _isolated_env_vars(home_dir),
    }
    return server_block


def _isolated_env_vars(home_dir: Path) -> dict[str, str]:
    resolved_home = home_dir.expanduser().resolve()
    backend_port, chart_port = isolated_runtime_ports(resolved_home)
    env = {
        "HOME": str(resolved_home),
        "HOROSA_RUNTIME_ROOT": str(isolated_runtime_root(resolved_home)),
        "HOROSA_SKILL_DATA_DIR": str(isolated_data_dir(resolved_home)),
        "HOROSA_LOCAL_BACKEND_PORT": str(backend_port),
        "HOROSA_LOCAL_CHART_PORT": str(chart_port),
        "HOROSA_SERVER_ROOT": f"http://127.0.0.1:{backend_port}",
        "HOROSA_CHART_SERVER_ROOT": f"http://127.0.0.1:{chart_port}",
    }
    if os.name == "nt":
        env["USERPROFILE"] = str(resolved_home)
    return env


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


def _write_json_file(path: Path, payload: object) -> Path:
    output_path = path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


_MERGEABLE_ROOT_KEYS = ("mcpServers", "servers", "context_servers")
_PIN_WHEEL = re.compile(r"/v(\d+\.\d+\.\d+)/horosa_skill-\d+\.\d+\.\d+-py3-none-any\.whl")
_PIN_GIT = re.compile(r"horosa-skill@v(\d+\.\d+\.\d+)#")
_PIN_LOCAL_WHEEL = re.compile(r"horosa_skill-(\d+\.\d+\.\d+)-py3-none-any\.whl$")


def _merge_client_config(path: Path, payload: object) -> dict[str, Any]:
    """`client config --write` / `setup` 落盘（v0.38.0 B2：根键感知、备份、原子替换、绝不写元键）。

    v0.33.0 的合并只认 `mcpServers`：VS Code 的根键是 `servers`、Zed 是 `context_servers`、claude-code
    产物只有一条命令字符串——这三家 `--write ~/.config/zed/settings.json` 会把用户整个 settings.json
    覆盖成我们的 payload（连 `note`/`tool_surface` 一起写进去），且 JSON 目标不备份、非原子写。
    现在：① 只动 `<root>[<server_name>]`，其余键（`theme`、别的 server…）逐字保留；② 目标存在则先
    `.horosa-bak`；③ 临时文件 + `os.replace`，写到一半断电也不会留半个文件；④ 非对象 JSON 拒写；
    ⑤ 没有可合并根键的格式（openclaw 之外的纯说明产物）拒写而不是把说明当配置。
    """
    target = path.expanduser().resolve()
    if isinstance(payload, dict) and isinstance(payload.get("toml_stdio"), str):
        written = _write_codex_toml_merge(target, payload["toml_stdio"])
        backup = target.with_name(f"{target.name}.horosa-bak")
        return {"path": str(written), "format": "toml", "root_key": "mcp_servers",
                "backup": str(backup) if backup.exists() else None}
    if not isinstance(payload, dict):
        raise typer.BadParameter("这份产物不是对象，无法合并进客户端配置。")
    root_key = next((key for key in _MERGEABLE_ROOT_KEYS if isinstance(payload.get(key), dict)), None)
    if root_key is None:
        raise typer.BadParameter(
            "这个格式的产物没有可合并的 server 块（mcpServers / servers / context_servers），"
            "拒绝把说明文字写成配置文件；请按 note 手动接入。"
        )
    servers = payload[root_key]
    backup: Path | None = None
    written_format = "json"
    if target.exists():
        raw = target.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise typer.BadParameter(f"{target} 不是 UTF-8 文本（{exc}），拒绝合并——请手动把 {root_key} 片段粘进去。") from exc
        from horosa_skill import jsonc as _jsonc

        if _jsonc.is_jsonc_only(text):
            # 🔴 v0.38.1 C4：Zed 出厂 settings.json / VS Code mcp.json 带注释与尾逗号，此前直接拒写。
            # 文本级插入：只动 <root_key>.<server> 这一段，注释与其它键逐字节保留；写完回读验证。
            existing = _jsonc.loads(text)
            if not isinstance(existing, dict):
                raise typer.BadParameter(f"{target} 顶层不是 JSON 对象，拒绝合并。")
            new_text = text
            for name, entry in servers.items():
                new_text = _jsonc.upsert_server_entry(new_text, root_key, name, entry)
            merged_check = _jsonc.loads(new_text)
            if not all(name in (merged_check.get(root_key) or {}) for name in servers):
                raise typer.BadParameter(f"{target} 含注释，文本级插入后回读不到 {root_key} 条目，拒绝写入。")
            backup = target.with_name(f"{target.name}.horosa-bak")
            backup.write_bytes(raw)
            output_text = new_text if new_text.endswith("\n") else new_text + "\n"
            written_format = "jsonc"
        else:
            try:
                existing = json.loads(text) if raw.strip() else {}
            except json.JSONDecodeError as exc:
                raise typer.BadParameter(
                    f"{target} 不是合法 JSON（{exc}），拒绝合并——请手动把 {root_key} 片段粘进去。"
                ) from exc
            if not isinstance(existing, dict):
                raise typer.BadParameter(f"{target} 顶层不是 JSON 对象，拒绝合并。")
            backup = target.with_name(f"{target.name}.horosa-bak")
            backup.write_bytes(raw)
            merged = dict(existing)
            block = dict(merged.get(root_key) or {})
            block.update(servers)
            merged[root_key] = block
            output_text = json.dumps(merged, ensure_ascii=False, indent=2) + "\n"
    else:
        output_text = json.dumps({root_key: dict(servers)}, ensure_ascii=False, indent=2) + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f"{target.name}.horosa-tmp")
    tmp.write_text(output_text, encoding="utf-8")
    try:
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()
    return {"path": str(target), "format": written_format, "root_key": root_key,
            "servers": sorted(servers), "backup": str(backup) if backup else None}


def _client_config_write(path: Path, payload: object) -> Path:
    """向后兼容的薄包装：返回写入路径（详情见 `_merge_client_config`）。"""
    return Path(_merge_client_config(path, payload)["path"])


def _write_codex_toml_merge(target: Path, toml_snippet: str) -> Path:
    """把生成的 `[mcp_servers.<name>]` 片段合并进已有 config.toml：只 upsert 该 server 表，
    其余内容（含注释）逐字保留（tomlkit）；覆盖前先备份 `<file>.horosa-bak`。目标不存在/为空
    则整文件写入片段。目标不是合法 TOML 时拒绝合并（绝不静默覆盖用户文件）。"""
    import tomlkit

    snippet_doc = tomlkit.parse(toml_snippet)
    snippet_servers = snippet_doc.get("mcp_servers")
    if not snippet_servers:
        raise typer.BadParameter("codex 片段缺少 [mcp_servers.<name>] 表，拒绝写入。")
    raw_bytes = target.read_bytes() if target.exists() else b""
    if raw_bytes.strip():
        # 🔴 读取也在护栏内：Notepad / `Out-File` 存出来的 config.toml 可能是 UTF-16LE（BOM ff fe）
        # 或 UTF-8-with-BOM。此前 read_text(utf-8) 在 try 之外，UTF-16 直接以 UnicodeDecodeError
        # 的 traceback 逃出 `setup --client codex`。
        try:
            if raw_bytes.startswith((b"\xff\xfe", b"\xfe\xff")):
                raw = raw_bytes.decode("utf-16")
            else:
                raw = raw_bytes.decode("utf-8-sig")
            existing = tomlkit.parse(raw)
        except (UnicodeDecodeError, Exception) as exc:  # noqa: BLE001 - 解析失败=用户文件形状未知，绝不覆盖
            raise typer.BadParameter(
                f"{target} 不是合法 TOML 或编码无法识别（{exc}），拒绝合并——请手动把生成片段粘进去。"
            ) from exc
        backup = target.with_name(f"{target.name}.horosa-bak")
        backup.write_text(raw, encoding="utf-8")
        servers_table = existing.get("mcp_servers")
        if servers_table is None:
            existing["mcp_servers"] = snippet_servers
        else:
            for name, table in snippet_servers.items():
                servers_table[name] = table
        target.write_text(tomlkit.dumps(existing), encoding="utf-8")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(toml_snippet, encoding="utf-8")
    return target


def _default_openclaw_native_config_path() -> Path:
    return Path.home() / ".openclaw" / "openclaw.json"


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"OpenClaw native config is not valid JSON: {path}",
            code="openclaw.native_config.invalid_json",
            details={"path": str(path), "error": str(exc)},
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(
            f"OpenClaw native config must be a JSON object: {path}",
            code="openclaw.native_config.invalid_shape",
            details={"path": str(path), "actual_type": type(payload).__name__},
        )
    return payload


def _merge_openclaw_native_config(
    existing: dict[str, Any],
    *,
    server_name: str,
    server_block: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(existing)
    mcp_section = merged.get("mcp")
    if not isinstance(mcp_section, dict):
        mcp_section = {}
    else:
        mcp_section = dict(mcp_section)
    servers = mcp_section.get("servers")
    if not isinstance(servers, dict):
        servers = {}
    else:
        servers = dict(servers)
    servers[server_name] = server_block
    mcp_section["servers"] = servers
    merged["mcp"] = mcp_section
    return merged


def _write_openclaw_native_config(
    *,
    path: Path,
    server_name: str,
    server_block: dict[str, Any],
) -> Path:
    output_path = path.expanduser().resolve()
    existing = _read_json_object(output_path)
    payload = _merge_openclaw_native_config(
        existing,
        server_name=server_name,
        server_block=server_block,
    )
    return _write_json_file(output_path, payload)


def _timed_call(callback):
    started_at = time.perf_counter()
    result = callback()
    return result, round(time.perf_counter() - started_at, 3)


def _quote_cli_arg(value: str) -> str:
    return f'"{value}"' if any(char.isspace() for char in value) else value


def _format_cli_command(parts: list[str]) -> str:
    return " ".join(_quote_cli_arg(part) for part in parts)


def _openclaw_setup_command(workspace_root: Path | str = "<your-openclaw-workspace>") -> str:
    return _format_cli_command(
        [
            "uv",
            "run",
            "horosa-skill",
            "client",
            "openclaw-setup",
            "--workspace",
            str(workspace_root),
        ]
    )


def _openclaw_check_command(workspace_root: Path | str, config_path: Path | str | None = None) -> str:
    command = [
        "uv",
        "run",
        "horosa-skill",
        "client",
        "openclaw-check",
        "--workspace",
        str(workspace_root),
    ]
    if config_path is not None:
        command.extend(["--config", str(config_path)])
    return _format_cli_command(command)


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


def _network_hints() -> dict[str, Any]:
    """代理/镜像相关的现场事实 —— 这些是「装不上 / 连不上本地后端」最常见的两类成因。"""
    proxy_vars = {
        name: os.environ[name]
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
        if os.environ.get(name)
    }
    no_proxy = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
    loopback_excluded = any(token in no_proxy for token in ("127.0.0.1", "localhost"))
    hints: list[str] = []
    if proxy_vars and not loopback_excluded:
        hints.append(
            "检测到代理环境变量。本工具对回环地址已内建绕代理（不受影响）；"
            "但你自己的 curl / 浏览器仍会走代理，排查时请设 NO_PROXY=127.0.0.1,localhost。"
        )
    if not os.environ.get("HOROSA_RUNTIME_MIRROR"):
        hints.append("下载慢或超时可设 HOROSA_RUNTIME_MIRROR 指向就近镜像；Python 包源用 UV_INDEX_URL。")
    return {
        "proxy_env": proxy_vars,
        "no_proxy": no_proxy or None,
        "loopback_excluded_from_proxy": loopback_excluded,
        "hints": hints,
    }


def _doctor_port_holders(report: dict[str, Any]) -> list[dict[str, Any]]:
    """可达但不是我们的端点 —— 点名端口、PID、镜像，并明说本工具不会去终止它。"""
    conflicts: list[dict[str, Any]] = []
    for endpoint in report.get("endpoints", []) or []:
        identity = endpoint.get("identity")
        if not isinstance(identity, dict) or identity.get("verdict") not in {"foreign", "unknown"}:
            continue
        conflicts.append({
            "label": endpoint.get("label"),
            "url": endpoint.get("url"),
            "port": identity.get("port"),
            "verdict": identity.get("verdict"),
            "holders": identity.get("holders") or [],
            "will_not_kill": "本工具不会终止不属于自己的进程。",
        })
    return conflicts



def _doctor_listener_scope(settings: Settings) -> dict[str, Any]:
    """Which interfaces the two local services listen on (v0.38.0 B1).

    A `loopback_only: False` entry means the service is bound to 0.0.0.0/:: — on Windows that is a
    Firewall prompt on first start and a backend reachable from the LAN. The launcher templates now pin
    `--server.address=127.0.0.1`; an installed runtime picks that up on the next `runtime restart`.
    """
    from horosa_skill.runtime import ports

    scope: dict[str, Any] = {}
    for label, port in (("java_backend", settings.local_backend_port), ("python_chart", settings.local_chart_port)):
        bindings = ports.listener_bindings(port)
        scope[label] = {"port": port, "bindings": bindings, "loopback_only": ports.loopback_only(bindings)}
    return scope


def _listener_scope_warnings(scope: dict[str, Any]) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    for label, entry in scope.items():
        if entry.get("loopback_only") is not False:
            continue
        addresses = sorted({str(b.get("local_address")) for b in entry.get("bindings") or []})
        warnings.append({
            "code": "listener:not_loopback_only",
            "detail": (
                f"{label} listens on {', '.join(addresses)} (port {entry.get('port')}), not only 127.0.0.1 — "
                "Windows Firewall prompts on first start and the service is reachable from the LAN."
            ),
            "fix": (
                "升级 horosa-skill 后 `horosa-skill runtime restart` 重新套用启动器模板（现在钉 --server.address=127.0.0.1）；"
                "若这是你自己起的服务，请给它加回环绑定。"
            ),
        })
    return warnings


# v0.38.0 B6：doctor 能报出的每个 issue / warning 码都要有人话（user_summary + next_action）。
# 码集的真值：manager.DOCTOR_ISSUE_CODES（issues）+ _DOCTOR_WARNING_CODES（warnings）；
# tests/test_doctor_machine_conditions.py::test_every_doctor_code_has_advice 锁步，并扫源码里新增的字面量。
_DOCTOR_WARNING_CODES = (
    "listener:not_loopback_only", "platform:emulated_process", "env:internal_port_override", "runtime:payload_outdated",
)
_DOCTOR_ADVICE: dict[str, dict[str, str]] = {
    "runtime.manifest_invalid": {
        "user_summary": "已装 runtime 的 runtime-manifest.json 缺失或损坏，doctor 无法信任这份安装。",
        "next_action": "重跑 `horosa-skill install --force`（会重新解包并写回清单）。",
    },
    "runtime.state_invalid": {
        "user_summary": "runtime-state.json 损坏（上次启动被打断或磁盘写坏），启停状态不可信。",
        "next_action": "`horosa-skill runtime stop` 后再 `runtime start`；仍不行就删掉 runtime-state.json 重启。",
    },
    "missing:": {
        "user_summary": "已装 runtime 缺文件（解包不完整、被安全软件隔离或手动删过）。",
        "next_action": "`horosa-skill install --force` 重新解包；Windows 上先看安全软件的隔离区。",
    },
    "services:java_backend_not_running": {
        "user_summary": "Python 图表服务在跑，Java 后端（:9999）没起来——chart 族可用，八字/紫微/六壬/农历族会报错。",
        "next_action": "看报告里的 java_diagnostics；Windows 常见诱因是代理/VPN/安全软件拦 JDK 回环（issue #14）。",
    },
    "services:chart_not_running": {
        "user_summary": "Java 后端在跑，Python 图表服务（:8899）没起来。",
        "next_action": "`horosa-skill runtime restart`；仍不行看 launcher_log 里 python 的报错。",
    },
    "services:not_running": {
        "user_summary": "runtime 文件都在，本机服务还没启动。",
        "next_action": "`horosa-skill runtime start`（客户端首次调用也会自动起；冷启动 10–45 s）。",
    },
    "quarantine:runtime_binaries": {
        "user_summary": "macOS Gatekeeper 给 runtime 里的可执行文件打了 com.apple.quarantine（浏览器下载的归档常见），首次执行会被拦。",
        "next_action": "运行报告里 quarantine.fix 给出的 `xattr -dr com.apple.quarantine <runtime/current>` 后重启 runtime。",
    },
    "windows:runtime_root_not_ascii": {
        "user_summary": "Windows 上 runtime 目录路径含中文等非英文字符（常见于中文用户名）：随包的 Java 17 与 Swiss Ephemeris 用窄字符 API，"
                        "Java 起不来、星历文件打不开——八字 / 紫微 / 六壬 / 农历族与 chart 族大量技法会失败（错误还会误报成参数错误）。",
        "next_action": "`setx HOROSA_RUNTIME_ROOT C:\\horosa`（纯英文路径），新开终端并重启 AI 客户端后 `horosa-skill install`；旧目录可删。",
    },
    "listener:not_loopback_only": {
        "user_summary": "本机服务绑在 0.0.0.0（局域网可达，Windows 会弹防火墙）。",
        "next_action": "升级后 `horosa-skill runtime restart` 重套启动器模板（钉 127.0.0.1）。",
    },
    "env:internal_port_override": {
        "user_summary": "环境里有 HOROSA_SERVER_PORT / HOROSA_CHART_PORT（启动器内部变量）且与本工具算出的端口不一致；"
                        "v0.38.1 起启动器一律按本工具的端口起服务，这两个变量不再有效果。",
        "next_action": "改用 HOROSA_LOCAL_BACKEND_PORT / HOROSA_LOCAL_CHART_PORT（或 HOROSA_PORTS=auto）选端口，并把那两个内部变量从环境里删掉。",
    },
    "runtime:payload_outdated": {
        "user_summary": "已装的离线 runtime 比最后一次看到的发布清单旧，或其导出契约（export_registry_version）低于本包期望——"
                        "能用，但新技法/新导出段可能缺失或对不上。",
        "next_action": "跑 `horosa-skill upgrade`（wheel / 插件 / MCPB 形态的完整命令见 warnings[].fix）；只想核对最新版本号可 `doctor --probe-network`。",
    },
    "platform:emulated_process": {
        "user_summary": "当前 Python 进程在仿真下跑（x64 Python 在 ARM 芯片 / Rosetta）——能用，只是慢一点；离线 runtime 按芯片选载荷，不受影响。",
        "next_action": "可选：换成原生架构的 uv / Python 会更快；不换也没问题。",
    },
}


def _advice_for(code: str) -> dict[str, str]:
    if code in _DOCTOR_ADVICE:
        return dict(_DOCTOR_ADVICE[code])
    prefix = code.split(":", 1)[0] + ":"
    if prefix in _DOCTOR_ADVICE:
        return dict(_DOCTOR_ADVICE[prefix])
    return {"user_summary": f"doctor 报了 {code}。", "next_action": "看报告里对应字段的 details；`horosa-skill doctor --explain` 给人话版。"}


def _arch_warnings(report: dict[str, Any]) -> list[dict[str, str]]:
    arch = report.get("arch") or {}
    if arch.get("emulated") is not True:
        return []
    advice = _advice_for("platform:emulated_process")
    return [{
        "code": "platform:emulated_process",
        "detail": f"process={arch.get('process')} native={arch.get('native')}：{advice['user_summary']}",
        "fix": advice["next_action"],
    }]


def _payload_outdated_warnings(report: dict[str, Any]) -> list[dict[str, str]]:
    """R4：已装载荷落后于最后一次看到的发布清单 / 导出契约 → warning（不是 issue：旧载荷仍能用）。"""
    freshness = report.get("freshness") or {}
    if not report.get("installed") or not freshness.get("payload_outdated"):
        return []
    from horosa_skill.runtime.hints import install_command

    erv = freshness.get("export_registry_version") or {}
    parts: list[str] = []
    if freshness.get("outdated"):
        parts.append(f"installed {freshness.get('installed_version')} < latest {freshness.get('latest_version')}")
    if erv.get("outdated"):
        parts.append(f"export_registry_version {erv.get('installed')} < expected {erv.get('expected')}")
    advice = _advice_for("runtime:payload_outdated")
    return [{
        "code": "runtime:payload_outdated",
        "detail": "; ".join(parts) + "：" + advice["user_summary"],
        "fix": f"运行 `{install_command()['upgrade']}`（升级会先停自己起的服务、换目录、再拉起）。",
    }]


def _refresh_latest_manifest_cache(manager: HorosaRuntimeManager, probe: dict[str, Any] | None) -> dict[str, Any] | None:
    """网络探针成功后顺手 GET 一次清单并写入 runtime 根下的版本缓存（尽力而为，永不抛）。"""
    if not isinstance(probe, dict) or not probe.get("ok"):
        return None
    url = str(probe.get("url") or "")
    if not url:
        return None
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        if parsed.scheme == "file":
            data = json.loads(manager._file_url_to_path(url).read_text(encoding="utf-8"))
        elif parsed.scheme in {"http", "https"}:
            import httpx

            with httpx.Client(timeout=_SETUP_NETWORK_TIMEOUT_SECONDS, follow_redirects=True) as http:
                response = http.get(url)
                response.raise_for_status()
                data = response.json()
        else:
            return None
    except Exception:  # noqa: BLE001 - 缓存刷新失败不该让 doctor / setup 变红
        return None
    if not isinstance(data, dict):
        return None
    manager._remember_latest_manifest(data, url)
    return data


def _internal_port_env_warnings(settings: Settings) -> list[dict[str, str]]:
    """A11：`HOROSA_SERVER_PORT` / `HOROSA_CHART_PORT` 是启动器内部变量；用户若在环境里手设了别的值，
    v0.38.1 前会让启动器起在一个 manager 不知道的端口上（manager 用 setdefault 让位），随后 doctor 报「没起来」。"""
    mismatched: list[str] = []
    for key, expected in (("HOROSA_SERVER_PORT", settings.local_backend_port), ("HOROSA_CHART_PORT", settings.local_chart_port)):
        raw = os.environ.get(key, "").strip()
        if raw and raw != str(expected):
            mismatched.append(f"{key}={raw} (manager uses {expected})")
    if not mismatched:
        return []
    advice = _advice_for("env:internal_port_override")
    return [{"code": "env:internal_port_override", "detail": "; ".join(mismatched) + "：" + advice["user_summary"],
             "fix": advice["next_action"]}]


def _explain_lines(report: dict[str, Any]) -> list[str]:
    """`doctor --explain`：6–10 行人话写 stderr（stdout 仍是纯 JSON）。"""
    issues = [str(item) for item in report.get("issues") or []]
    warnings = [w for w in report.get("warnings") or [] if isinstance(w, dict)]
    reachable = [e.get("label") for e in report.get("endpoints") or [] if e.get("reachable") is True]
    lines = [
        f"状态：{report.get('status')} —— {report.get('user_summary')}",
        (
            f"runtime：{'已装 ' + str(report.get('manifest_version') or '') if report.get('installed') else '未装'}；"
            f"本机 {report.get('host_platform')}"
            + (f" → 载荷 {report.get('payload_platform')}（仿真）" if report.get("emulated") else "")
            + f"；进程架构 {(report.get('arch') or {}).get('process')} / 芯片 {(report.get('arch') or {}).get('native')}"
        ),
        f"服务：可达 {', '.join(str(x) for x in reachable) if reachable else '无'}；模式 {report.get('mode')}",
    ]
    for code in issues[:4]:
        advice = _advice_for(code)
        lines.append(f"问题 {code}：{advice['user_summary']} → {advice['next_action']}")
    for warning in warnings[:2]:
        lines.append(f"提示 {warning.get('code')}：{warning.get('fix') or warning.get('detail')}")
    probe = report.get("network_probe")
    if isinstance(probe, dict):
        okay = [a.get("url") for a in probe.get("attempts") or [] if a.get("ok")]
        lines.append(f"网络：清单 URL {'可达（' + str(okay[0]) + '）' if okay else '经所有镜像都不可达'}")
    lines.append(f"下一步：{report.get('next_action')}")
    lines.append(f"日志：{report.get('launcher_log')}")
    return lines[:10]


def _doctor_summary(report: dict[str, Any]) -> dict[str, Any]:
    issues = [str(issue) for issue in report.get("issues", [])]
    reachable_endpoints = [
        endpoint.get("label")
        for endpoint in report.get("endpoints", [])
        if endpoint.get("reachable") is True
    ]
    installed = report.get("installed") is True
    conflicts = report.get("port_conflicts") or []
    unexpanded = report.get("unexpanded_env_templates") or {}
    unsupported = report.get("platform_supported") is False
    ready_for_openclaw = installed and not issues and not conflicts and not unexpanded
    if unsupported:
        user_summary = (
            "本机平台没有离线 runtime 载荷 —— 这不是发布疏漏，而是只发 darwin-arm64 与 win32-x64"
            "（Windows on ARM 会自动装 x64 载荷走仿真；Intel Mac 本轮不做、Linux 无载荷）。"
        )
        next_action = (
            "走网关模式：在一台受支持的机器上跑 runtime，本机设 HOROSA_SERVER_ROOT 与 "
            "HOROSA_CHART_SERVER_ROOT 指过去（外部模式，本机不启动任何服务）。"
        )
        return {
            "status": "needs_attention", "ready_for_openclaw": False,
            "user_summary": user_summary, "next_action": next_action,
            "reachable_endpoints": reachable_endpoints,
        }
    if unexpanded:
        names = "、".join(sorted(unexpanded))
        return {
            "status": "needs_attention", "ready_for_openclaw": False,
            "user_summary": (
                f"环境变量 {names} 的值还是**未展开的占位符**（宿主没有替换它），已按未设置处理。"
                "这通常意味着 MCPB / 插件配置里的 user_config 没填。"
            ),
            "next_action": "在客户端的扩展设置里补上这些值，或直接删掉这些环境变量用默认路径。",
            "reachable_endpoints": reachable_endpoints,
        }
    if conflicts:
        named = "；".join(
            f"{c.get('label')} 端口 {c.get('port')} 被 "
            + (", ".join(f"pid {h.get('pid')} {(h.get('command') or '')[:60]}" for h in c.get("holders") or [])
               or "一个查不出身份的进程")
            + " 占着"
            for c in conflicts
        )
        return {
            "status": "needs_attention", "ready_for_openclaw": False,
            "user_summary": f"端口被非本工具的进程占用：{named}。本工具不会去终止它们。",
            "next_action": (
                "关掉上面点名的进程，或换端口：设 HOROSA_PORTS=auto 自动挑空闲端口，"
                "或显式设 HOROSA_LOCAL_BACKEND_PORT / HOROSA_LOCAL_CHART_PORT；"
                "若那正是你想用的服务，设 HOROSA_SERVER_ROOT / HOROSA_CHART_SERVER_ROOT 指向它。"
            ),
            "reachable_endpoints": reachable_endpoints,
        }
    if report.get("registry_status") == "starting":
        return {
            "status": "starting", "ready_for_openclaw": False,
            "user_summary": "runtime 正在启动（首次运行含解压与 CDS 训练，可能几分钟）。",
            "next_action": "等一会儿再跑 `horosa-skill runtime status`；启动器日志路径见 launcher_log。",
            "reachable_endpoints": reachable_endpoints,
        }
    if ready_for_openclaw:
        # 🔴 措辞改为客户端无关：doctor 是给**任何** MCP 客户端的用户看的（Claude Code/Desktop、
        # Cursor、VS Code、Codex、Gemini CLI…），把「去开 OpenClaw」当成唯一下一步，对其余客户端
        # 的用户既没用又误导。`ready_for_openclaw` 这个键名保留一版作兼容别名。
        user_summary = "Ready. The offline runtime is installed and the local Horosa endpoints are responding."
        if report.get("emulated") is True:
            # v0.38.0 A4: Windows on ARM runs the win32-x64 payload under emulation — worth saying once.
            user_summary += (
                f" This host is {report.get('host_platform')} and runs the {report.get('payload_platform')} payload"
                " under emulation (works; cold start is slower)."
            )
        next_action = (
            "Point your MCP client at Horosa: `uv run horosa-skill client config --format <client>` "
            "writes the right config (claude-code / claude-desktop / cursor / vscode / codex / gemini / "
            "windsurf / cline / zed). Then `uv run horosa-skill selfcheck` for an end-to-end live check."
        )
    elif not installed:
        user_summary = "The offline runtime is not installed yet."
        next_action = f"Run `{_openclaw_setup_command()}` to install the runtime, write a config, and verify the OpenClaw path."
    elif issues == ["services:not_running"]:
        user_summary = "The runtime files are installed, but the local Horosa services are not running yet."
        next_action = f"Run `{_openclaw_setup_command()}` to start the runtime and verify the OpenClaw path."
    elif issues == ["services:java_backend_not_running"]:
        user_summary = (
            "Degraded (chart-only): the Python chart service is up, but the Java backend (:9999) is not. "
            "Chart-side techniques (三式 ken/神数/地占/塔罗/西占 chart 族) still work; Java-side ones "
            "(nongli/bazi/ziwei/liureng and 占时 casts) will error until it recovers."
        )
        next_action = (
            "See `java_diagnostics` below for the captured Java boot error. Known cause on Windows: "
            "proxy/VPN or security software (WFP filters) blocking JDK-17 AF_UNIX/TCP loopback — "
            "issue #14. Retry after disabling the interfering software and rebooting, or keep using "
            "chart-only techniques."
        )
    else:
        user_summary = "Horosa still has runtime issues that need attention before OpenClaw will be fully ready."
        next_action = "Review the `issues` list below, fix the blocking item, then rerun `uv run horosa-skill doctor`."
    return {
        "status": "ready" if ready_for_openclaw else "needs_attention",
        "ready_for_openclaw": ready_for_openclaw,
        "user_summary": user_summary,
        "next_action": next_action,
        "reachable_endpoints": reachable_endpoints,
    }


def _platform_supported(report: dict[str, Any]) -> bool:
    """本机平台有没有离线载荷。已装 runtime 就是最好的证据。"""
    if report.get("installed") is True:
        return True
    from horosa_skill.runtime.manager import PLATFORM_FALLBACKS, SUPPORTED_PAYLOAD_PLATFORMS, _platform_key

    host = _platform_key()
    return host in SUPPORTED_PAYLOAD_PLATFORMS or host in PLATFORM_FALLBACKS


# 版本串探针 5 s 足够（node/uv --version 毫秒级）；此前 15 s × 2 个探针是 doctor 在慢机上卡死的一部分。
_PROBE_TIMEOUT_SECONDS = 5.0


def _probe_executable(path: Path, args: list[str]) -> dict[str, Any]:
    """实跑探针：不止「文件存在」，还验证真的能执行并回读版本串。"""
    if not path.is_file():
        return {"path": str(path), "exists": False, "runnable": False}
    try:
        completed = subprocess.run(
            [str(path), *args], capture_output=True, text=True, timeout=_PROBE_TIMEOUT_SECONDS,
            encoding="utf-8", errors="replace",
        )
        output = (completed.stdout or completed.stderr or "").strip().splitlines()
        return {
            "path": str(path),
            "exists": True,
            "runnable": completed.returncode == 0,
            "version": output[0][:80] if output else "",
        }
    except (OSError, subprocess.TimeoutExpired, UnicodeDecodeError) as exc:
        return {"path": str(path), "exists": True, "runnable": False, "error": str(exc)[:200]}


def _probe_uv() -> dict[str, Any]:
    """宿主 uv 探针（v0.38.0 B4）：MCPB 的 `server.type: "uv"` 与 `--launcher uv` 的配置都靠它。"""
    try:
        command = resolve_uv_command()
    except FileNotFoundError as exc:
        return {
            "exists": False, "runnable": False, "error": str(exc)[:200],
            "fix": "curl -LsSf https://astral.sh/uv/install.sh | sh（Windows：`irm https://astral.sh/uv/install.ps1 | iex`），或设 HOROSA_UV_BIN。",
        }
    resolved = shutil.which(command[0]) or command[0]
    return _probe_executable(Path(resolved), ["--version"])


def _probe_port(port: int) -> dict[str, Any]:
    """端口占用探测：区分空闲 / 被占（被占时是否是本产品由 doctor 的可达性检查判断）。"""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        occupied = sock.connect_ex(("127.0.0.1", port)) == 0
    return {"port": port, "occupied": occupied}


def _doctor_environment_context(settings: Settings) -> dict[str, Any]:
    explicit_runtime_root = "HOROSA_RUNTIME_ROOT" in os.environ
    explicit_data_dir = "HOROSA_SKILL_DATA_DIR" in os.environ
    explicit_home = "HOME" in os.environ or (os.name == "nt" and "USERPROFILE" in os.environ)
    workspace_hint = os.environ.get("OPENCLAW_WORKSPACE")
    default_openclaw_workspace = Path.home() / ".openclaw" / "workspace"
    # 磁盘体检：runtime 全量约 2GB，升级/重装峰值需要双份空间。
    import shutil as _shutil

    try:
        usage = _shutil.disk_usage(settings.runtime_root if settings.runtime_root.exists() else Path.home())
        disk = {
            "free_gb": round(usage.free / (1024**3), 1),
            "total_gb": round(usage.total / (1024**3), 1),
            "sufficient_for_install": usage.free > 5 * (1024**3),
        }
    except OSError:
        disk = {"free_gb": None, "total_gb": None, "sufficient_for_install": None}
    current = settings.runtime_root / "current"
    # 🔴 路径从 manager 的清单缺省取（单一真值）。此前这里手写 `runtime/win/…`，而载荷里是
    # `runtime/windows/…` → Windows 上 `probes.node` 永远 exists:false，与旁边 files[] 的「在」自相矛盾。
    from horosa_skill.runtime.manager import HorosaRuntimeManager as _Manager

    node_bin = current / _Manager(settings)._manifest_defaults()["runtimes"]["node"]
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=2) as pool:
        node_future = pool.submit(_probe_executable, node_bin, ["--version"])
        uv_future = pool.submit(_probe_uv)
        probes = {
            "node": node_future.result(),
            "uv": uv_future.result(),
            "backend_port": _probe_port(settings.local_backend_port),
            "chart_port": _probe_port(settings.local_chart_port),
        }
    return {
        "runtime_root": str(settings.runtime_root),
        "data_dir": str(settings.data_dir),
        "home": str(Path.home()),
        "disk": disk,
        "probes": probes,
        "uses_explicit_runtime_root": explicit_runtime_root,
        "uses_explicit_data_dir": explicit_data_dir,
        "uses_explicit_home": explicit_home,
        "openclaw_workspace_hint": workspace_hint or str(default_openclaw_workspace),
        "note": (
            "`doctor` checks the current process environment. If OpenClaw was set up with "
            "an isolated HOME/env block, use `client openclaw-check --workspace <workspace>` "
            "or run doctor with the same HOROSA_RUNTIME_ROOT/HOROSA_SKILL_DATA_DIR values."
        ),
    }


def _failed_smoke_checks(report: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    compute_ok = report.get("compute_ok")
    for field in ("server_visible", "knowledge_registry_ok", "memory_show_ok"):
        if report.get(field) is not True:
            failures.append(field)
    if compute_ok is not None:
        if compute_ok is not True:
            failures.append("compute_ok")
    elif report.get("chart_ok") is not True:
        failures.append("chart_ok")
    return failures


def _smoke_summary(
    report: dict[str, Any],
    *,
    workspace_root: Path,
    config_path: Path,
) -> dict[str, Any]:
    failed_checks = _failed_smoke_checks(report)
    ready_for_openclaw = report.get("ok") is True
    list_checked = report.get("list_checked", True)
    if ready_for_openclaw:
        compute_tool = report.get("compute_tool") or "a representative Horosa tool"
        if list_checked:
            user_summary = (
                f"Ready. OpenClaw can see Horosa, list {report.get('listed_tool_count', 0)} tools, "
                f"run {compute_tool}, save the result, and read it back."
            )
        else:
            user_summary = "Ready. Horosa passed the quick OpenClaw smoke check: call, compute, save, and readback all worked."
        next_action = f"Open OpenClaw and use the config at {config_path}."
    elif "server_visible" in failed_checks or "knowledge_registry_ok" in failed_checks:
        user_summary = "OpenClaw did not get a healthy response from the Horosa server."
        next_action = f"Run `{_openclaw_check_command(workspace_root, config_path)}` after you confirm the runtime is installed and mcporter is available."
    elif "compute_ok" in failed_checks or "chart_ok" in failed_checks:
        user_summary = "OpenClaw reached Horosa, but the representative tool call did not finish successfully."
        next_action = f"Run `{_openclaw_check_command(workspace_root, config_path)}` again after `uv run horosa-skill doctor` confirms the runtime is healthy."
    else:
        user_summary = "OpenClaw computed a result, but the saved chart could not be read back cleanly."
        next_action = f"Run `{_openclaw_check_command(workspace_root, config_path)}` again to confirm the readback path."
    return {
        "status": "ready" if ready_for_openclaw else "needs_attention",
        "ready_for_openclaw": ready_for_openclaw,
        "user_summary": user_summary,
        "next_action": next_action,
        "recheck_command": _openclaw_check_command(workspace_root, config_path),
        "failed_checks": failed_checks,
        "checks": {
            "server_visible": report.get("server_visible") is True,
            "knowledge_registry_ok": report.get("knowledge_registry_ok") is True,
            "chart_ok": report.get("chart_ok") is True,
            "compute_ok": report.get("compute_ok", report.get("chart_ok")) is True,
            "memory_show_ok": report.get("memory_show_ok") is True,
        },
    }


def _setup_summary(
    *,
    workspace_root: Path,
    config_path: Path,
    native_config_path: Path | None,
    home_dir: Path,
    doctor_issues: list[str],
    smoke_report: dict[str, Any] | None,
    skip_smoke: bool,
) -> dict[str, Any]:
    smoke_ready = (smoke_report or {}).get("ok") is True
    ready_for_openclaw = not doctor_issues and (skip_smoke or smoke_ready)
    if ready_for_openclaw and not skip_smoke:
        user_summary = "Ready. Horosa installed the runtime, wrote the OpenClaw config, and passed the quick smoke check."
        next_action = f"Open OpenClaw and use the config at {config_path}."
    elif ready_for_openclaw:
        user_summary = "Setup finished and the local runtime looks healthy, but the smoke check was skipped."
        next_action = f"Run `{_openclaw_check_command(workspace_root, config_path)}` before relying on the OpenClaw path."
    elif doctor_issues:
        user_summary = "Setup finished the install, but the local runtime still needs attention before OpenClaw is fully ready."
        next_action = "Run `uv run horosa-skill doctor` to inspect the runtime issues, then rerun the setup command."
    else:
        user_summary = "Setup wrote the config, but the OpenClaw smoke check did not complete every required step."
        next_action = f"Run `{_openclaw_check_command(workspace_root, config_path)}` again after `uv run horosa-skill doctor` looks healthy."
    return {
        "status": "ready" if ready_for_openclaw else "needs_attention",
        "ready_for_openclaw": ready_for_openclaw,
        "user_summary": user_summary,
        "next_action": next_action,
        "default_entry": _openclaw_setup_command(workspace_root),
        "recheck_command": _openclaw_check_command(workspace_root, config_path),
        "config_written_to": str(config_path),
        "native_config_written_to": str(native_config_path) if native_config_path is not None else None,
        "local_home": str(home_dir),
    }


def _friendly_runtime_error_payload(
    exc: RuntimeError,
    *,
    action_label: str,
    workspace_root: Path | None = None,
    config_path: Path | None = None,
) -> dict[str, Any]:
    retry_command: str | None = None
    if action_label == "OpenClaw setup" and workspace_root is not None:
        retry_command = _openclaw_setup_command(workspace_root)
    elif workspace_root is not None:
        retry_command = _openclaw_check_command(workspace_root, config_path)

    next_action = "Review the error details below and rerun the command."
    user_summary = f"{action_label} did not finish successfully."
    code = exc.code or ""
    details = exc.details if isinstance(exc.details, dict) else {}
    command = [str(part) for part in details.get("command", [])]
    command_text = " ".join(command).lower()
    if code == "client.command_not_found" and "mcporter" in command_text:
        user_summary = f"{action_label} could not find `mcporter` on this machine."
        next_action = (
            "Install it with `npm i -g mcporter`, or set `HOROSA_MCPORTER_BIN`, "
            + (f"then rerun `{retry_command}`." if retry_command else "then rerun the command.")
        )
    elif code == "client.command_not_found" and "uv" in command_text:
        user_summary = f"{action_label} could not find `uv`."
        next_action = "Install uv, or set `HOROSA_UV_BIN`, then rerun the command."
    elif code == "runtime.platform_unsupported":
        user_summary = f"{action_label} found no offline runtime payload for this platform."
        next_action = str(details.get("next_action") or "Use gateway mode: point HOROSA_SERVER_ROOT / HOROSA_CHART_SERVER_ROOT at a supported machine.")
    elif code.startswith("runtime.install") or code == "runtime.not_installed":
        user_summary = f"{action_label} could not finish installing the offline runtime."
        next_action = "Check your network access to the Horosa runtime release and rerun the setup command."
    elif code.startswith("runtime.start"):
        user_summary = f"{action_label} installed the runtime, but the local Horosa services did not start cleanly."
        next_action = "Run `uv run horosa-skill doctor` for more details, then rerun the setup command."
    elif code in {"client.command_failed", "client.invalid_json"}:
        user_summary = f"{action_label} started the OpenClaw client command, but it did not return a clean JSON result."
        next_action = "Run `uv run horosa-skill doctor` and make sure mcporter can start Horosa, then retry the smoke check."
    elif code == "client.command_timeout" and details.get("phase") == "npx_install":
        user_summary = f"{action_label} could not fetch `mcporter` through npx in time (npx downloads it on first use)."
        next_action = (
            "Install it once with `npm i -g mcporter` (or set `HOROSA_MCPORTER_BIN`), "
            + (f"then rerun `{retry_command}`." if retry_command else "then rerun the command.")
        )
    elif code == "client.command_timeout" and details.get("output_complete"):
        user_summary = (
            f"{action_label}: the OpenClaw client command printed its complete result, but its process did not exit in time."
        )
        next_action = (
            "Something in the client's process tree (usually the stdio server it started) kept the pipes open. "
            "Rerun with `MCPORTER_DEBUG_HANG=1` to list what mcporter was waiting on, stop leftover "
            "`horosa-skill serve --transport stdio` / `mcporter` processes, then retry the smoke check."
        )
    elif code == "client.command_timeout":
        user_summary = f"{action_label} started the OpenClaw client command, but the subprocess did not return in time."
        next_action = (
            "Stop any stuck `horosa-skill serve --transport stdio` / `mcporter` processes, "
            "rerun `uv run horosa-skill client openclaw-setup --workspace <workspace>`, "
            "then retry the smoke check."
        )

    payload = {
        "ok": False,
        "status": "needs_attention",
        "ready_for_openclaw": False,
        "user_summary": user_summary,
        "next_action": next_action,
        "code": exc.code,
        "message": str(exc),
        "details": exc.details,
    }
    if retry_command is not None:
        payload["retry_command"] = retry_command
    return payload


def _build_openclaw_config(
    *,
    skill_root: Path,
    server_name: str,
    format_name: str,
    isolate_home: Path | None,
) -> dict[str, Any]:
    server_block = _build_openclaw_server_block(
        skill_root=skill_root,
        isolate_home=isolate_home,
    )
    if format_name == "mcporter":
        return {"mcpServers": {server_name: server_block}}
    if format_name == "openclaw":
        return {"mcp": {"servers": {server_name: server_block}}}
    raise typer.BadParameter("`--format` must be either `mcporter` or `openclaw`.")


def _timeout_output_text(value: object) -> str:
    """`TimeoutExpired.stdout/stderr` is bytes on POSIX even with text=True (str on Windows) — keep both."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value if isinstance(value, str) else ""


def _has_json_object(text: str) -> bool:
    try:
        return isinstance(extract_json_value(text or ""), dict)
    except ValueError:
        return False


# v0.38.1 post-release: the first `npx mcporter …` also downloads mcporter (with a native bundler binding) — that
# install used to run inside the 150 s budget of the first tool call. Fetch it once, on its own budget, first.
NPX_MCPORTER_WARMUP_TIMEOUT_SECONDS = 300.0


def _is_npx_mcporter(command: list[str]) -> bool:
    # PureWindowsPath splits on both "/" and "\\", so the check reads the same on every host.
    return len(command) == 2 and PureWindowsPath(command[0]).name.lower() in {"npx", "npx.cmd", "npx.exe"} and command[1] == "mcporter"


def _warm_npx_mcporter(command: list[str], *, cwd: Path) -> float | None:
    """When mcporter resolves through the npx fallback, run `npx mcporter --version` once so npx's first-run install
    is not charged to a tool call's timeout. Returns seconds spent, or None when mcporter is a real executable."""
    if not _is_npx_mcporter(command):
        return None
    warm_command = [*command, "--version"]
    started = time.perf_counter()
    try:
        subprocess.run(
            warm_command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=NPX_MCPORTER_WARMUP_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            str(exc), code="client.command_not_found", details={"command": warm_command, "cwd": str(cwd), "phase": "npx_install"}
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            bilingual(
                f"npx 在 {NPX_MCPORTER_WARMUP_TIMEOUT_SECONDS:.0f} 秒内没下载完 mcporter（首次使用时 npx 会先下载它）。",
                f"npx did not finish fetching mcporter within {NPX_MCPORTER_WARMUP_TIMEOUT_SECONDS:.0f} seconds (npx downloads it on first use).",
            ),
            code="client.command_timeout",
            details={
                "command": warm_command,
                "cwd": str(cwd),
                "phase": "npx_install",
                "timeout_seconds": NPX_MCPORTER_WARMUP_TIMEOUT_SECONDS,
                "output_complete": False,
                "stderr": _timeout_output_text(exc.stderr)[-4000:],
            },
        ) from exc
    # The exit code is deliberately ignored: this step only pays for the download. A broken install surfaces on the
    # first real call with its own error.
    return round(time.perf_counter() - started, 3)


def _run_subprocess_json(command: list[str], *, cwd: Path, timeout_seconds: float = 180.0) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(str(exc), code="client.command_not_found", details={"command": command, "cwd": str(cwd)}) from exc
    except subprocess.TimeoutExpired as exc:
        stdout_text = _timeout_output_text(exc.stdout)
        stderr_text = _timeout_output_text(exc.stderr)
        raise RuntimeError(
            f"Command timed out after {timeout_seconds} seconds: {' '.join(command)}",
            code="client.command_timeout",
            details={
                "command": command,
                "cwd": str(cwd),
                "timeout_seconds": timeout_seconds,
                # True = the command had already printed a complete JSON result and then did not exit: something in its
                # process tree (usually the stdio server it started) kept the pipes open. False = it never finished.
                "output_complete": _has_json_object(stdout_text),
                "stdout": stdout_text[-4000:],
                "stderr": stderr_text[-4000:],
            },
        ) from exc
    parsed: dict[str, Any] | None = None
    for candidate in (result.stdout, result.stderr):
        try:
            candidate_value = extract_json_value(candidate or "")
        except ValueError:
            continue
        if isinstance(candidate_value, dict):
            parsed = candidate_value
            break
    if result.returncode != 0 and parsed is None:
        raise RuntimeError(
            result.stderr.strip() or result.stdout.strip() or "Command failed",
            code="client.command_failed",
            details={"command": command, "cwd": str(cwd), "returncode": result.returncode},
        )
    if parsed is not None:
        return parsed
    raise RuntimeError(
        f"Command did not return JSON: {' '.join(command)}",
        code="client.invalid_json",
        details={
            "command": command,
            "cwd": str(cwd),
            "stdout": (result.stdout or "")[-4000:],
            "stderr": (result.stderr or "")[-4000:],
        },
    )


def _is_mcporter_timeout_response(payload: dict[str, Any]) -> bool:
    issue = payload.get("issue")
    if not isinstance(issue, dict) or issue.get("kind") != "offline":
        return False
    text = f"{payload.get('error', '')}\n{issue.get('rawMessage', '')}".lower()
    return "timed out" in text


def _run_openclaw_smoke_check(
    *,
    workspace_root: Path,
    config_path: Path,
    output_path: Path,
    include_list: bool = True,
) -> dict[str, Any]:
    call_timeout_ms = 120000
    mcporter_command = resolve_mcporter_command()
    npx_warmup_seconds = _warm_npx_mcporter(mcporter_command, cwd=workspace_root)

    def call_tool(tool_name: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        command = [
            *mcporter_command,
            "call",
            f"horosa.{tool_name}",
        ]
        if payload is not None:
            command.extend(["--args", json.dumps(payload, ensure_ascii=False)])
        command.extend(
            [
                "--output",
                "json",
                "--config",
                str(config_path),
                "--root",
                str(workspace_root),
                "--timeout",
                str(call_timeout_ms),
            ]
        )
        return _run_subprocess_json(command, cwd=workspace_root, timeout_seconds=150)

    list_result: dict[str, Any] | None = None
    if include_list:
        list_result = _run_subprocess_json(
            [
                *mcporter_command,
                "list",
                "horosa",
                "--json",
                "--config",
                str(config_path),
                "--root",
                str(workspace_root),
            ],
            cwd=workspace_root,
            timeout_seconds=60,
        )
    registry_result = call_tool("horosa_knowledge_registry")
    confirmed_payload = {
        "agent_confirmed_settings": True,
        "clarification_notes": "OpenClaw smoke check fixture with explicit test settings.",
    }
    chart_payload = {
        **confirmed_payload,
        "date": "2026-04-04",
        "time": "15:58:35",
        "zone": "+08:00",
        "lat": "26n04",
        "lon": "119e19",
        "gpsLat": 26.066667,
        "gpsLon": 119.316667,
        "hsys": 1,
        "tradition": False,
        "predictive": True,
        "zodiacal": 0,
        "simpleAsp": False,
        "strongRecption": False,
        "virtualPointReceiveAsp": True,
        "southchart": False,
        "ad": 1,
    }
    chart_result = call_tool("horosa_astro_chart", chart_payload)
    if _is_mcporter_timeout_response(chart_result):
        chart_result = call_tool("horosa_astro_chart", chart_payload)

    chart_ok = chart_result.get("ok") is True
    fallback_tool = "horosa_cn_qimen"
    fallback_result: dict[str, Any] | None = None
    if not chart_ok:
        # Keep the heavyweight chart result as a diagnostic, but verify the
        # OpenClaw path with a stable headless local tool before failing setup.
        fallback_payload = {
            **confirmed_payload,
            "date": "2026-04-04",
            "time": "15:58:35",
            "zone": "+08:00",
            "lat": "26n04",
            "lon": "119e19",
        }
        fallback_result = call_tool(fallback_tool, fallback_payload)
        if _is_mcporter_timeout_response(fallback_result):
            fallback_result = call_tool(fallback_tool, fallback_payload)

    fallback_ok = (fallback_result or {}).get("ok") is True
    compute_result = chart_result if chart_ok else (fallback_result or chart_result)
    compute_ok = chart_ok or fallback_ok
    compute_tool = "horosa_astro_chart" if chart_ok else (fallback_tool if fallback_ok else None)
    memory_ref = compute_result.get("memory_ref") or {}
    run_id = memory_ref.get("run_id")
    artifact_path = memory_ref.get("artifact_path")
    memory_show = call_tool("horosa_memory_show", {"run_id": run_id, "include_payload": False}) if run_id else {}
    report = {
        "workspace": str(workspace_root),
        "config": str(config_path),
        "list_checked": include_list,
        "npx_warmup_seconds": npx_warmup_seconds,
        "server_visible": (list_result or {}).get("status") == "ok" if include_list else registry_result.get("ok") is True,
        "listed_tool_count": len((list_result or {}).get("tools", [])) if include_list else None,
        "knowledge_registry_ok": registry_result.get("ok") is True,
        "chart_ok": chart_ok,
        "chart_error": chart_result.get("error") if not chart_ok else None,
        "fallback_tool": fallback_tool if not chart_ok else None,
        "fallback_tool_ok": fallback_ok if fallback_result is not None else None,
        "fallback_error": (fallback_result or {}).get("error") if fallback_result and not fallback_ok else None,
        "compute_ok": compute_ok,
        "compute_tool": compute_tool,
        "memory_show_ok": memory_show.get("ok") is True,
        "run_id": run_id,
        "artifact_path": artifact_path,
        "ok": (
            (registry_result.get("ok") is True)
            and compute_ok
            and memory_show.get("ok") is True
            and ((list_result or {}).get("status") == "ok" if include_list else True)
        ),
    }
    report.update(_smoke_summary(report, workspace_root=workspace_root, config_path=config_path))
    _write_json_file(output_path, report)
    return report


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


# doctor / runtime status 的整体时间预算（秒）。MCP 客户端 60 s 掐工具，agent 常把 doctor 当工具调；
# 单个探针各 5–15 s 加起来在 Windows 上最坏 ~165 s（v0.38.1 审计实算），所以要有一个总闸。
# 预算耗尽的探针按「查不到」处理并列进 report.budget.skipped —— 宁可少一项证据，不可让 doctor 本身挂掉。
DOCTOR_BUDGET_SECONDS = 25.0
STATUS_BUDGET_SECONDS = 15.0


def _doctor_report(settings: Settings, manager: HorosaRuntimeManager, *, probe_network: bool = False) -> dict[str, Any]:
    """`doctor` 的完整报告；`setup` 第 4 步用的是同一份（v0.38.0 B4）——两边永远同一套判定。

    默认**零外网请求**（回环探测只打 127.0.0.1 且 trust_env=False）；`probe_network=True` 才逐个镜像 HEAD 清单 URL。
    整份报告跑在 `budget.scope(DOCTOR_BUDGET_SECONDS)` 里，各子进程探针自动把超时压进剩余预算。
    """
    from horosa_skill.runtime import budget as _budget

    with _budget.scope(DOCTOR_BUDGET_SECONDS) as budget_scope:
        report = _doctor_report_unbudgeted(settings, manager, probe_network=probe_network)
        report["budget"] = budget_scope.as_dict()
    return report


def _doctor_report_unbudgeted(settings: Settings, manager: HorosaRuntimeManager, *, probe_network: bool = False) -> dict[str, Any]:
    from horosa_skill.runtime import budget as _budget

    with _budget.timed("manager.doctor"):
        report = manager.doctor()
    with _budget.timed("environment"):
        report["environment"] = _doctor_environment_context(settings)
    # 记忆库完整性探针（v0.33.0 批 II-1）：PRAGMA quick_check + 损坏自愈痕迹；坏库在 MemoryStore
    # 构造时已分类恢复（隔离 .corrupt-<ts>.bak 并重建），这里如实呈现。
    try:
        from horosa_skill.memory.store import MemoryStore as _MemoryStore

        report["memory_db"] = {"path": str(settings.db_path), **_MemoryStore(settings).integrity_check()}
    except Exception as exc:  # noqa: BLE001 - 体检项自身失败也要如实入报告
        report["memory_db"] = {"path": str(settings.db_path), "ok": False, "detail": [f"{exc}"]}
    # env 旗标审计（批 II-1）：未知 HOROSA_* 的 warn-and-ignore 结果 + 已设旗标的生命周期档。
    from horosa_skill.config import ENV_FLAG_REGISTRY as _ENV_REGISTRY
    from horosa_skill.config import audit_env_flags as _audit_env_flags

    try:
        report["env_flags"] = {"ok": True, "warnings": _audit_env_flags(force=True)}
    except ValueError as exc:
        report["env_flags"] = {"ok": False, "warnings": [str(exc)]}
    report["env_flags"]["set"] = {
        key: _ENV_REGISTRY.get(key, "unknown") for key in sorted(os.environ) if key.startswith("HOROSA_")
    }
    # 可选云端决策层（v0.39.0）：模式 / 范围 / 面 / 模型 / 阈值锁 / 配置问题——**永不**含 key 的值；
    # 缺省 off 时也如实报 data_leaves_machine=False。零外网请求。
    from horosa_skill.decisions.policy import load_policy as _load_jev_policy
    from horosa_skill.decisions.policy import load_thresholds as _load_jev_thresholds

    report["decision_layer"] = _load_jev_policy().doctor_view(_load_jev_thresholds())
    # Settings provenance 三列（批 II-3）：字段 / 当前值 / 来源（env:<NAME> | derived:data_dir | default）。
    report["settings_provenance"] = [
        {"field": field, "value": str(getattr(settings, field, None)), "source": source}
        for field, source in sorted(settings.settings_provenance.items())
    ]
    from horosa_skill.config import unexpanded_env_templates as _unexpanded

    report["mode"] = manager.runtime_mode()
    report["platform_supported"] = _platform_supported(report)
    if settings.runtime_current_dir.exists():
        try:
            with _budget.timed("endpoint_identities"):
                report["endpoints"] = manager.endpoint_identities(manager.load_installed_manifest())
        except Exception:  # noqa: BLE001 - 体检不能因为归属判定失败就整份报废
            pass
    report["port_conflicts"] = _doctor_port_holders(report)
    # 监听范围（v0.38.0 B1）：绑 0.0.0.0 的服务不是"坏"，但 Windows 上会弹防火墙、暴露到局域网 —— 进 warnings 而非 issues。
    report["listener_scope"] = _doctor_listener_scope(settings)
    report["network_probe"] = (
        _probe_manifest_url(settings.runtime_manifest_url or settings.default_runtime_manifest_url, stop_at_first_success=False)
        if probe_network else None
    )
    # R4：探针成功 → GET 清单刷新版本缓存 → 新鲜度按刷新后的缓存重算（默认路径零外网请求，只读缓存）。
    if report["network_probe"] and _refresh_latest_manifest_cache(manager, report["network_probe"]):
        report["freshness"] = manager.payload_freshness(report.get("manifest"))
        report["latest_version"] = report["freshness"]["latest_version"]
    report["warnings"] = [
        *(report.get("warnings") or []),
        *_listener_scope_warnings(report["listener_scope"]),
        *_arch_warnings(report),
        *_internal_port_env_warnings(settings),
        *_payload_outdated_warnings(report),
    ]
    # v0.38.0 B6：每个码一条人话（issues 与 warnings 都有），脚本用户与 agent 不用再猜码的意思。
    report["advice"] = [
        {"code": code, **_advice_for(code)}
        for code in [*(str(i) for i in report.get("issues") or []), *(w.get("code") for w in report["warnings"] if isinstance(w, dict))]
    ]
    report["unexpanded_env_templates"] = _unexpanded()
    report["network_hints"] = _network_hints()
    report["registry_status"] = (manager.load_runtime_state() or {}).get("status")
    report["launcher_log"] = str(settings.runtime_root / manager.LAUNCHER_LOG_NAME)
    report.update(_doctor_summary(report))
    return report


@app.command()
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
# 步骤固定、逐步记录、失败包结构化：network_probe → install → config → doctor → client_check → stdio_probe → next_steps。
# 🔴 第 3 步（config）之前失败保证 `config_untouched: true`；写过配置的失败包带 `backup_path`。
# 输出契约冻结在 tests/test_cli_output_contract.py；行为在 tests/test_setup_command.py。
# ---------------------------------------------------------------------------

_SETUP_STEPS = ("network_probe", "install", "config", "doctor", "client_check", "stdio_probe", "next_steps")
_SETUP_NETWORK_TIMEOUT_SECONDS = 5.0
# uvx-wheel 首跑要下载 wheel 与依赖（顺带焐热 uvx 缓存，客户端首次启动就快了）；uv 形态通常 5–10 s。
_SETUP_STDIO_TIMEOUT_SECONDS = 300.0
_CLIENT_RESTART_HINTS = {
    "claude-code": "新开一个 Claude Code 会话（或重启）；`claude mcp list` 应列出 horosa。",
    "claude-desktop": "完全退出并重开 Claude Desktop（菜单里 Quit，不只是关窗口）；Settings → Developer 里应看到 horosa。",
    "cursor": "重启 Cursor；Settings → MCP 里 horosa 应亮绿灯。",
    "vscode": "重载 VS Code 窗口（Developer: Reload Window）；Copilot Chat 的工具列表里应出现 horosa。",
    "codex": "重启 codex；首轮可能看不到 horosa 工具（冷启动只等 1 s），第二轮即恢复。",
    "gemini": "重启 gemini；`/mcp` 应列出 horosa。",
    "windsurf": "重启 Windsurf；Cascade 的 MCP 面板里应看到 horosa。",
    "cline": "重载 VS Code 窗口；Cline 的 MCP Servers 面板里应看到 horosa。",
    "zed": "重启 Zed；Agent 面板的 Context Servers 里应看到 horosa。",
}
_SETUP_TRY_PROMPT = (
    "在客户端里试一句：「用八字看看 1990-01-01 12:00 北京出生的人」——Horosa 会先追问缺失的设置"
    "（时区 / 性别 / 流派），确认后才起盘。"
)


class _SetupFailure(Exception):
    """`setup` 某一步失败：payload 原样写到 stderr，退出码 2。"""

    def __init__(self, payload: dict[str, Any]) -> None:
        super().__init__(str(payload.get("message") or payload.get("code") or "setup failed"))
        self.payload = payload


def _probe_manifest_url(url: str, *, timeout: float = _SETUP_NETWORK_TIMEOUT_SECONDS, stop_at_first_success: bool = True) -> dict[str, Any]:
    """5 s 内判断清单 URL 能不能取到（逐个镜像 HEAD；HEAD 被拒则 GET 流式只看状态）。

    失败在这里就失败——比等 120 s 下载超时再报清楚得多；`--no-probe-network` 可跳过。
    """
    from urllib.parse import urlparse
    from urllib.request import url2pathname

    from horosa_skill.runtime.mirrors import mirror_candidates

    parsed = urlparse(url)
    if parsed.scheme == "file":
        exists = Path(url2pathname(parsed.path)).is_file()
        return {"ok": exists, "url": url, "attempts": [{"url": url, "ok": exists, "kind": "file"}]}
    if parsed.scheme not in {"http", "https"}:
        return {"ok": False, "url": url, "attempts": [{"url": url, "ok": False, "error": f"unsupported scheme `{parsed.scheme}`"}]}
    import httpx

    attempts: list[dict[str, Any]] = []
    for candidate in mirror_candidates(url):
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as http:
                status = http.head(candidate).status_code
                if status in {403, 405}:  # 有些镜像不接 HEAD
                    with http.stream("GET", candidate) as streamed:
                        status = streamed.status_code
            ok = status < 400
            attempts.append({"url": candidate, "status": status, "ok": ok})
            if ok and stop_at_first_success:
                return {"ok": True, "url": candidate, "attempts": attempts}
        except httpx.HTTPError as exc:
            attempts.append({"url": candidate, "ok": False, "error": f"{type(exc).__name__}: {exc}"[:200]})
    reachable = [a["url"] for a in attempts if a.get("ok")]
    return {"ok": bool(reachable), "url": reachable[0] if reachable else url, "attempts": attempts}


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
                        except Exception:  # noqa: BLE001 - 老版本 server 没有这个资源；探针本身不因此失败
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
        probe, seconds = _timed_call(lambda: _probe_manifest_url(manifest_location))
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
            fail("install", exc.code or "runtime.install_failed", str(exc), exc.details if isinstance(exc.details, dict) else {})
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
    elif target is None:
        target = _preferred_config_path(client_key)
    root_key = "toml_stdio" if client_key == "codex" else next(
        (key for key in _MERGEABLE_ROOT_KEYS if isinstance(payload.get(key), dict)), None
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
    if dry_run or not write:
        config_step.update({"ok": True, "skipped": True, "reason": "dry-run" if dry_run else "--no-write"})
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

    # ---- 4 doctor
    announce(4, "doctor", "体检…")
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

    # ---- 5 client_check
    if dry_run or not write or mode == "printed":
        reason = "dry-run" if dry_run else "--no-write" if not write else "配置未落盘（claude 不在 PATH，命令已打印）"
        steps["client_check"] = {"ok": True, "skipped": True, "reason": reason}
    else:
        announce(5, "client_check", "回读磁盘上的配置…")
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

    # ---- 6 stdio_probe
    if dry_run or not stdio_probe:
        steps["stdio_probe"] = {"ok": True, "skipped": True, "reason": "dry-run" if dry_run else "--no-stdio-probe"}
    else:
        announce(6, "stdio_probe", "用客户端将要执行的命令真起一次 MCP server（stdio，不起离线 runtime）…")
        expected = int(payload["tool_surface"]["tools"])
        probe_args = [*stdio_command[1:], "--skip-runtime-start"]
        # 🔴 v0.38.1 C14：按**客户端的形状**起——Codex 只给最小环境（∪ 配置里的 env 表），其余客户端继承整个环境；
        # cwd = 项目根（uv 形态 = Codex 的 cwd）。再读 horosa://runtime/status，抓「server 算出的 runtime 根 ≠ 终端里的」。
        configured_env = {**surface_env, **(_codex_env_roots() if client_key == "codex" else {})}
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

    # ---- 7 next_steps
    prefix = "uv run horosa-skill" if launcher_key == "uv" else "horosa-skill"
    next_steps: list[str] = []
    if mode == "printed":
        next_steps.append(f"先执行：{config_step['command']}")
    next_steps.append(_CLIENT_RESTART_HINTS[client_key])
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
        else "注册命令已打印（claude 不在 PATH）" if mode == "printed"
        else "配置未落盘"
    )
    probe_text = (
        f"stdio 起服务成功（{steps['stdio_probe'].get('tools')} 个工具）" if not steps["stdio_probe"].get("skipped")
        else "stdio 探测已跳过"
    )
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
        "summary": f"{client_key}：{install_text}；{config_text}；{probe_text}。",
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
        help="Target client: claude-code / claude-desktop / cursor / vscode / codex / gemini / windsurf / cline / zed.",
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
) -> None:
    try:
        report = _run_setup(
            client=client, launcher=launcher, surface=surface, config=config, scope=scope, server_name=server_name,
            skill_root=skill_root, dry_run=dry_run, skip_install=skip_install, archive=archive, manifest_url=manifest_url,
            probe_network=probe_network, stdio_probe=stdio_probe, write=write, cache_wheel=cache_wheel,
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
            report["next_action"] = str((exc.details or {}).get("next_action") or "运行 `uv run horosa-skill install` 安装离线 runtime 后重试。")
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


@app.command()
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


@tool_app.command("list")
def tool_list() -> None:
    _print_json(_service().list_tools())


@tool_app.command("run")
def tool_run(
    tool_name: str,
    stdin: bool = typer.Option(False, "--stdin", help="Read a JSON object from stdin."),
    input_file: Optional[Path] = typer.Option(None, "--input", help="Read a JSON object from a file."),
    save_result: bool = typer.Option(True, help="Persist the result in local memory."),
    query_text: str | None = typer.Option(None, help="Optional original user question to store together with this run."),
    output: Optional[Path] = typer.Option(None, "--output", help="Also write the JSON envelope to this UTF-8 file (stdout keeps printing it)."),
) -> None:
    payload = _load_payload(stdin=stdin, input_file=input_file)
    service = _service()
    try:
        _enforce_agent_preflight(tool_name, payload)
        result = service.run_tool(tool_name, payload, save_result=save_result, query_text=query_text)
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


@export_app.command("registry")
def export_registry(
    technique: str | None = typer.Option(None, help="Return only one technique block."),
    save_result: bool = typer.Option(False, help="Persist the result in local memory."),
) -> None:
    service = _service()
    result = service.run_tool("export_registry", {"technique": technique} if technique else {}, save_result=save_result)
    _print_json(result.model_dump(mode="json"))


@export_app.command("parse")
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


@knowledge_app.command("registry")
def knowledge_registry(
    domain: str | None = typer.Option(None, help="Optional knowledge domain filter: astro, liureng, qimen."),
    save_result: bool = typer.Option(False, help="Persist the result in local memory."),
) -> None:
    service = _service()
    result = service.run_tool("knowledge_registry", {"domain": domain} if domain else {}, save_result=save_result)
    _print_json(result.model_dump(mode="json"))


@knowledge_app.command("read")
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
    query: str = typer.Argument(..., help="Full-text query across all 24 knowledge domains."),
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


@app.command()
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


@benchmark_app.command("run")
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


@trace_app.command("latest")
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


# 各客户端的工具总数上限（实测/官方文档，2026-09）：Cursor 全局约 40 个**静默丢弃**超出部分；
# VS Code Copilot 与 OpenAI 兼容端 128（跨所有 server 共享）；Windsurf 100；Codex 无工具搜索，
# 116 个工具的定义每轮都进上下文（约 7 万 token）。这些客户端默认发精简面（11 个门面工具，
# 全部技法仍可经 horosa_tool_run 按名直达）；Claude Code / Claude Desktop 有工具搜索且无硬上限，
# 保持全量平铺（按名可见 = 更好的发现性）。`--surface full|compact` 可覆盖。
_CLIENT_COMPACT_DEFAULT = {
    "cursor": True,
    "vscode": True,
    "codex": True,
    "gemini": True,
    "windsurf": True,
    "cline": True,
    "zed": True,
    "claude-code": False,
    "claude-desktop": False,
}
_CLIENT_COMPACT_REASON = {
    "cursor": "Cursor 全局约 40 个工具上限，超出部分**静默丢弃**（不会报错）",
    "vscode": "VS Code Copilot 跨所有 server 共 128 个工具上限",
    "codex": "Codex 无工具搜索，全量工具定义每轮都进上下文",
    "gemini": "Gemini CLI 对工具数与 schema 都更严格",
    "windsurf": "Windsurf 100 个工具上限",
    "cline": "Cline 无工具搜索，全量面偏重",
    "zed": "Zed 无工具搜索，全量面偏重",
}


# 各客户端配置文件在本机的位置（`client check` 找、`client config` 报 `config_path`、`setup` 写）。
# v0.38.0 B2 之前是一张 POSIX 路径表：Windows 上 cursor/vscode/gemini/windsurf/cline/zed 一个都找不到，
# `client check` 在 Windows 只会说「还没配」。现在按 os 与环境变量算真实位置；找不到不是错误。
_CLIENT_NAMES = ("claude-code", "claude-desktop", "cursor", "vscode", "codex", "gemini", "windsurf", "cline", "zed")


def _project_root(start: Path | None = None) -> Path:
    """项目级配置该落在哪：从 `start`（默认 CWD）向上找最近的 `.git` 或已有 `.mcp.json` 的目录；都没有就是 CWD 本身。

    🔴 v0.38.1 C10：此前项目级候选一律取 `Path.cwd()`。在子目录里跑 `setup` / `client check`（最常见：
    `cd horosa-skill && uv run horosa-skill setup --client cursor`）会把 `.cursor/mcp.json` 写进子目录 ——
    客户端按项目根找配置，根本看不到它；`client check` 也在错的地方找。
    """
    start = (start or Path.cwd()).resolve()
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists() or (candidate / ".mcp.json").is_file():
            return candidate
    return start


def _client_config_locations(
    client: str, *, os_name: str | None = None, env: Mapping[str, str] | None = None,
    home: Path | None = None, cwd: Path | None = None,
) -> list[Path]:
    """候选配置文件（先全局后项目级；第一个存在的就是 `config_path`）。纯函数，便于跨平台测试。

    项目级候选按 `_project_root(cwd)`（`.git` / `.mcp.json` 所在的最近祖先），不是裸 CWD。
    v0.38.1 C19 追加：`CODEX_HOME`（Codex 官方覆盖变量）、Linux 的 `XDG_CONFIG_HOME`、项目级
    `.gemini/settings.json`、Cline 装在 Cursor / Windsurf 里时的 globalStorage 根。
    """
    # os_name ∈ {"nt", "darwin", "linux"}（默认按本机）；参数化是为了在任何平台上都能测别的平台的路径表。
    if os_name is None:
        os_name = "nt" if os.name == "nt" else ("darwin" if sys.platform == "darwin" else "linux")
    env = os.environ if env is None else env
    home = Path(home) if home is not None else Path.home()
    project = Path(cwd) if cwd is not None else _project_root()
    if os_name == "nt":
        appdata = Path(env.get("APPDATA") or (home / "AppData" / "Roaming"))
        claude_desktop = appdata / "Claude" / "claude_desktop_config.json"
        code_user = appdata / "Code" / "User"
        cursor_user = appdata / "Cursor" / "User"
        windsurf_user = appdata / "Windsurf" / "User"
        zed = appdata / "Zed" / "settings.json"
    elif os_name == "darwin":
        app_support = home / "Library" / "Application Support"
        claude_desktop = app_support / "Claude" / "claude_desktop_config.json"
        code_user = app_support / "Code" / "User"
        cursor_user = app_support / "Cursor" / "User"
        windsurf_user = app_support / "Windsurf" / "User"
        zed = home / ".config" / "zed" / "settings.json"
    else:
        xdg = Path(env.get("XDG_CONFIG_HOME") or (home / ".config"))
        claude_desktop = xdg / "Claude" / "claude_desktop_config.json"
        code_user = xdg / "Code" / "User"
        cursor_user = xdg / "Cursor" / "User"
        windsurf_user = xdg / "Windsurf" / "User"
        zed = xdg / "zed" / "settings.json"
    codex_home = Path(env["CODEX_HOME"]) if env.get("CODEX_HOME") else home / ".codex"
    cline_tail = Path("globalStorage") / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json"
    table: dict[str, list[Path]] = {
        "claude-code": [home / ".claude.json", project / ".mcp.json"],
        "claude-desktop": [claude_desktop],
        "cursor": [home / ".cursor" / "mcp.json", project / ".cursor" / "mcp.json"],
        "vscode": [code_user / "mcp.json", project / ".vscode" / "mcp.json"],
        "codex": [codex_home / "config.toml"],
        "gemini": [home / ".gemini" / "settings.json", project / ".gemini" / "settings.json"],
        "windsurf": [home / ".codeium" / "windsurf" / "mcp_config.json"],
        "cline": [code_user / cline_tail, cursor_user / cline_tail, windsurf_user / cline_tail],
        "zed": [zed],
    }
    if client not in table:
        raise typer.BadParameter(f"未知客户端 `{client}`。可选：{', '.join(_CLIENT_NAMES)}")
    return table[client]


def _preferred_config_path(client: str) -> Path:
    """第一个已存在的候选；都不存在则第一个候选（全局级）。"""
    candidates = _client_config_locations(client)
    return next((c for c in candidates if c.is_file()), candidates[0])


# 三种根键：mcpServers（多数）/ servers（VS Code）/ context_servers（Zed）。
_SERVER_ROOT_KEYS = ("mcpServers", "servers", "context_servers", "mcp_servers")


def _iter_client_entries(payload: Any) -> Any:
    """从一份客户端配置里找出 horosa 条目（含 Claude Code 的 projects.<path>.mcpServers 嵌套）。"""
    if not isinstance(payload, dict):
        return
    for key in _SERVER_ROOT_KEYS:
        block = payload.get(key)
        if isinstance(block, dict):
            for name, entry in block.items():
                if isinstance(entry, dict) and "horosa" in str(name).lower():
                    yield name, entry
    projects = payload.get("projects")
    if isinstance(projects, dict):
        for project_path, project in projects.items():
            for name, entry in _iter_client_entries(project):
                yield f"{project_path}::{name}", entry


# 每个客户端**真的会展开**的 `${…}` 占位符（2026-09 按各家官方文档核对；前缀型以 `:` 结尾）。
# 不在表里的占位符会被客户端原样传给 server → `--directory ${x}` 不存在、env 里留着字面量。
CLIENT_PLACEHOLDER_WHITELIST: dict[str, tuple[str, ...]] = {
    "cursor": ("env:", "userHome", "workspaceFolder", "workspaceFolderBasename", "pathSeparator"),
    "vscode": ("workspaceFolder", "workspaceFolderBasename", "env:", "userHome", "input:"),
    "claude-code": ("CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT", "CLAUDE_PLUGIN_DATA"),
    "claude-desktop": (),
    "codex": (),
    "gemini": (),
    "windsurf": (),
    "cline": (),
    "zed": (),
}
_PLACEHOLDER_RE = re.compile(r"\$\{([^}]*)\}")


def _placeholder_allowed(var: str, client: str) -> bool:
    base = var.split(":-", 1)[0]
    for allowed in CLIENT_PLACEHOLDER_WHITELIST.get(client, ()):
        if allowed.endswith(":"):
            if base.startswith(allowed):
                return True
        elif base == allowed:
            return True
    return False


def _expand_client_placeholders(text: str, *, client: str, config_dir: Path | None) -> str:
    """按客户端规则把占位符换成本机路径（只为了检查 `--directory` 指得对不对；不知道的原样保留）。

    `${workspaceFolder}` / `${CLAUDE_PROJECT_DIR}` → 项目根（配置文件在 `.cursor/` / `.vscode/` 里时取上一层）。
    """
    project_root: Path | None = None
    if config_dir is not None:
        project_root = config_dir.parent if config_dir.name in {".cursor", ".vscode", ".gemini"} else config_dir

    def repl(match: re.Match[str]) -> str:
        var = match.group(1)
        base, _, default = var.partition(":-")
        if base in {"workspaceFolder", "CLAUDE_PROJECT_DIR"} and project_root is not None:
            return str(project_root)
        if base == "workspaceFolderBasename" and project_root is not None:
            return project_root.name
        if base == "userHome":
            return str(Path.home())
        if base == "pathSeparator":
            return os.sep
        if base.startswith("env:"):
            return os.environ.get(base[4:], default)
        return match.group(0)

    return _PLACEHOLDER_RE.sub(repl, text)


def _audit_client_entry(
    name: str, entry: dict[str, Any], *, client: str, config_dir: Path | None = None
) -> list[dict[str, str]]:
    """一条 horosa 配置的体检结果。纯函数，便于测试与守卫复用。"""
    problems: list[dict[str, str]] = []
    args = [str(a) for a in (entry.get("args") or [])]
    command = str(entry.get("command") or "")
    blob = " ".join([command, *args, json.dumps(entry.get("env") or {}, ensure_ascii=False)])

    # 🔴 按客户端白名单逐个判：此前只放行 `${workspaceFolder}` 与 `${CLAUDE_PROJECT_DIR`，于是 `.vscode/mcp.json`
    # 里写 `${CLAUDE_PROJECT_DIR}`（VS Code 不认）是绿的，而 `${env:HOME}`（Cursor / VS Code 都认）是红的。
    for var in _PLACEHOLDER_RE.findall(blob):
        if not _placeholder_allowed(var, client):
            allowed = ", ".join("${" + a + ("…}" if a.endswith(":") else "}") for a in CLIENT_PLACEHOLDER_WHITELIST.get(client, ())) or "（该客户端不展开任何占位符）"
            problems.append({
                "code": "unexpanded_placeholder",
                "detail": f"`${{{var}}}` 不是 {client} 会展开的占位符，会原样传给 server。",
                "fix": f"换成真实路径，或只用 {client} 支持的变量：{allowed}。",
            })
            break
    if args and "--transport" not in args:
        problems.append({
            "code": "missing_transport",
            "detail": "没有 `--transport stdio`。",
            "fix": "在 args 末尾加 [\"--transport\", \"stdio\"]；缺它时旧版本会默认起 HTTP server，客户端连不上。",
        })
    if "mcp" in args and "serve" not in args:
        problems.append({
            "code": "legacy_subcommand",
            "detail": "用的是已下线的 `horosa-skill mcp` 子命令。",
            "fix": "改成 `serve --transport stdio`。",
        })
    if "--directory" in args:
        index = args.index("--directory")
        if index + 1 < len(args):
            target = args[index + 1]
            # 🔴 相对路径要按**配置文件所在目录**解析，不是按跑 check 的那一刻的 CWD ——
            # 客户端启动 server 时的工作目录是项目根，而 `client check` 可能在任何地方被调用。
            expanded = _expand_client_placeholders(target, client=client, config_dir=config_dir)
            resolved = Path(expanded).expanduser()
            if not resolved.is_absolute() and config_dir is not None:
                resolved = (config_dir / resolved).resolve()
            # 占位符按客户端规则展开后再查；展开不了的（插件作用域 / 未知）跳过而不是误报。
            if "${" not in expanded and not (resolved / "pyproject.toml").is_file():
                problems.append({
                    "code": "directory_missing",
                    "detail": f"--directory 指向的目录里没有 pyproject.toml：{target}" + (f"（展开后 {expanded}）" if expanded != target else ""),
                    "fix": "指向 horosa-skill 包目录（含 pyproject.toml 的那一层）。",
                })
    # 裸命令名要靠 PATH；GUI 客户端（Claude Desktop / Cursor / VS Code…）在 Windows 上不继承 shell PATH，
    # 终端里能跑的 `uvx` 在客户端里就是 file not found（v0.38.0 B2）。绝对路径不查 PATH。
    if command and not any(sep in command for sep in ("/", "\\")) and shutil.which(command) is None:
        problems.append({
            "code": "command_not_on_path",
            "detail": f"`{command}` 不在 PATH 上（本机 which 找不到）；GUI 客户端还不继承你的 shell PATH。",
            "fix": "重跑 `horosa-skill client config --format <client>`（现在写绝对路径），或把 command 改成可执行文件的完整路径。",
        })
    # 钉版本的零安装源（wheel 资产 URL / git tag）与本包版本不一致 → 客户端跑的是别的版本（v0.38.0 B3）。
    if "--from" in args:
        source = args[args.index("--from") + 1] if args.index("--from") + 1 < len(args) else ""
        # v0.38.1 C15：`--from` 可以是 setup 预下载的本地 wheel；文件没了（清过缓存 / 换了机器）客户端就起不来。
        if source.endswith(".whl") and "://" not in source and not Path(source).expanduser().is_file():
            problems.append({
                "code": "wheel_cache_missing",
                "detail": f"--from 指向的本地 wheel 不存在：{source}",
                "fix": "重跑 `horosa-skill setup --client <client>`（会重新下载到 ~/.horosa/wheels/），或改回发布页的 wheel URL。",
            })
        pinned = _PIN_WHEEL.search(source) or _PIN_GIT.search(source) or _PIN_LOCAL_WHEEL.search(source)
        if pinned and pinned.group(1) != __version__:
            problems.append({
                "code": "launcher_version_drift",
                "detail": f"配置钉的是 v{pinned.group(1)}，本机 horosa-skill 是 v{__version__}。",
                "fix": "重跑 `horosa-skill client config --format <client> --launcher uvx-wheel --write <配置>`（或 `setup`）让 URL 跟上版本。",
            })
    if command.endswith("uvx") and "--from" not in args:
        problems.append({
            "code": "pypi_not_published",
            "detail": "`uvx horosa-skill` 依赖 PyPI，而本项目的 PyPI 通道尚未开通。",
            "fix": "用 `uvx --from \"git+https://github.com/Horace-Maxwell/horosa-skill@v<版本>"
                   "#subdirectory=horosa-skill\" horosa-skill`，或本地 checkout 走 `uv run --directory`。",
        })
    if client == "codex":
        # 缺省 = Codex 默认 startup 10 s / tool 60 s：首次冷启动要解压 runtime、择日扫描本来就几分钟——
        # 「一堆报错」（issue #18）最像的成因就是这两个没写。此前只在**写了且太短**时才报（v0.38.0 B2 补缺席分支）。
        startup = entry.get("startup_timeout_sec")
        if startup is None:
            problems.append({
                "code": "codex_startup_timeout_missing",
                "detail": "没写 startup_timeout_sec（Codex 默认 10 秒，首次启动要解压 runtime）。",
                "fix": "在 [mcp_servers.<name>] 里加 `startup_timeout_sec = 120`。",
            })
        elif float(startup) < 120:
            problems.append({
                "code": "codex_startup_timeout_too_short",
                "detail": f"startup_timeout_sec={startup}（默认 10 秒）。",
                "fix": "设 120 以上：首次启动要解压 runtime。",
            })
        tool_timeout = entry.get("tool_timeout_sec")
        if tool_timeout is None:
            problems.append({
                "code": "codex_tool_timeout_missing",
                "detail": "没写 tool_timeout_sec（Codex 默认 60 秒，择日类扫描本来就要几分钟）。",
                "fix": "在 [mcp_servers.<name>] 里加 `tool_timeout_sec = 600`。",
            })
        elif float(tool_timeout) < 600:
            problems.append({
                "code": "codex_tool_timeout_too_short",
                "detail": f"tool_timeout_sec={tool_timeout}（默认 60 秒）。",
                "fix": "设 600 以上：择日类扫描本来就要几分钟。",
            })
        cwd = entry.get("cwd")
        if cwd and "${" not in str(cwd) and not Path(str(cwd)).expanduser().is_dir():
            problems.append({
                "code": "codex_cwd_missing",
                "detail": f"cwd 指向的目录不存在：{cwd}（Codex 会 spawn 失败）。",
                "fix": "删掉 cwd（uvx 形态不需要），或指向存在的 horosa-skill 包目录。",
            })
        # v0.38.1 C6：Codex 不把你 shell 里的 HOROSA_* 交给 server。runtime 根 / 数据目录若只设在 shell 里，
        # Codex 起的那份 server 会算出**另一个** runtime 根 → 终端里 doctor ready、Codex 里全是 not_installed。
        env_table = entry.get("env") or {}
        missing_roots = [key for key in ("HOROSA_RUNTIME_ROOT", "HOROSA_SKILL_DATA_DIR") if not str(env_table.get(key) or "").strip()]
        if missing_roots:
            problems.append({
                "code": "codex_env_roots_missing",
                "detail": f"[mcp_servers.<name>.env] 缺 {' / '.join(missing_roots)}：Codex 不转发 shell 环境，server 会用默认目录。",
                "fix": "重跑 `horosa-skill client config --format codex --write ~/.codex/config.toml`（v0.38.1 起写入两个绝对路径）。",
            })
    if client in {"cline", "zed"}:
        # v0.38.1 C5：两家的 per-server `timeout` 都是秒、默认 60 —— 择日扫描 / 冷启动都会超。
        timeout = entry.get("timeout")
        if timeout is None:
            problems.append({
                "code": f"{client}_tool_timeout_missing",
                "detail": f"没写 timeout（{client} 默认 60 秒；择日类扫描与首次冷启动都可能超）。",
                "fix": "在该 server 条目里加 `\"timeout\": 600`（秒）。",
            })
        else:
            try:
                too_short = float(timeout) < 600
            except (TypeError, ValueError):
                too_short = True
            if too_short:
                problems.append({
                    "code": f"{client}_tool_timeout_too_short",
                    "detail": f"timeout={timeout}（{client} 默认 60 秒）。",
                    "fix": "设 600 以上（秒）。",
                })
    return problems


def _client_check_report(targets: list[str], config_path: Path | None = None) -> dict[str, Any]:
    """`client check` 的报告；`setup` 第 5 步回读磁盘时用同一份（v0.38.0 B4）。"""
    results: list[dict[str, Any]] = []
    for name in targets:
        if name not in _CLIENT_NAMES:
            raise typer.BadParameter(f"未知客户端 `{name}`。可选：{', '.join(_CLIENT_NAMES)}")
        candidates = [config_path] if config_path else _client_config_locations(name)
        found: list[dict[str, Any]] = []
        for candidate in candidates:
            path = candidate.expanduser()
            if not path.is_file():
                continue
            try:
                if path.suffix == ".toml":
                    import tomllib

                    payload = tomllib.loads(path.read_text(encoding="utf-8"))
                    payload = {"mcpServers": (payload.get("mcp_servers") or {})}
                else:
                    from horosa_skill import jsonc as _jsonc

                    payload = _jsonc.loads(path.read_text(encoding="utf-8-sig"))  # Zed / VS Code 允许注释与尾逗号
            except (OSError, ValueError) as exc:
                found.append({"path": str(path), "ok": False, "error": f"{type(exc).__name__}: {exc}"})
                continue
            entries = list(_iter_client_entries(payload))
            if not entries:
                found.append({"path": str(path), "ok": True, "horosa_entries": 0,
                              "note": "该文件存在但没有 horosa 条目。"})
                continue
            for entry_name, entry in entries:
                problems = _audit_client_entry(entry_name, entry, client=name, config_dir=path.parent)
                found.append({
                    "path": str(path), "entry": entry_name, "ok": not problems,
                    "problems": problems,
                    "tool_surface": "compact" if (entry.get("env") or {}).get("HOROSA_MCP_COMPACT") else "full",
                    "recommended_surface": "compact" if _CLIENT_COMPACT_DEFAULT.get(name) else "full",
                })
        results.append({
            "client": name,
            "searched": [str(Path(item).expanduser()) for item in candidates],
            "configured": bool([f for f in found if f.get("entry")]),
            "findings": found,
            "fix_command": f"uv run horosa-skill client config --format {name}",
        })
    problems_total = sum(len(f.get("problems") or []) for r in results for f in r["findings"])
    configured = [r["client"] for r in results if r["configured"]]
    return {
        "ok": problems_total == 0,
        "configured_clients": configured,
        "problems": problems_total,
        "summary": (
            f"检查了 {len(results)} 个客户端；已配置 {len(configured)} 个"
            + (f"，发现 {problems_total} 处问题。" if problems_total else "，未发现问题。")
        ),
        "clients": results,
    }


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


def _codex_env_roots() -> dict[str, str]:
    """Codex env 表里显式写的两个根（解析后的绝对路径；`HOROSA_PORTS=auto` 等其它旋钮不在此列）。"""
    settings = Settings.from_env()
    return {
        "HOROSA_RUNTIME_ROOT": str(settings.runtime_root.expanduser().resolve()),
        "HOROSA_SKILL_DATA_DIR": str(settings.data_dir.expanduser().resolve()),
    }


def _wheel_cache_dir() -> Path:
    return Path.home() / ".horosa" / "wheels"


def _wheel_looks_valid(path: Path, version: str) -> bool:
    import zipfile

    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            metadata = f"horosa_skill-{version}.dist-info/METADATA"
            if metadata not in names or "horosa_skill/__init__.py" not in names:
                return False
            return f"Version: {version}" in archive.read(metadata).decode("utf-8", errors="replace")
    except (OSError, zipfile.BadZipFile):
        return False


def _cache_wheel(url: str, *, version: str | None = None, dest_dir: Path | None = None, fetch: Any | None = None) -> tuple[Path | None, str | None]:
    """把发布页的 wheel 预下载到 ~/.horosa/wheels/（v0.38.1 C15），返回 (本地路径 | None, 警告 | None)。

    🔴 为什么：`uvx --from <URL>` 按 URL 缓存环境，但 uv 对直链依赖「尊重 HTTP 缓存头」——每次客户端冷启动都可能
    发一次再验证请求，离线时不保证能起。配置里写本地 wheel 路径 → 冷启动零网络、离线可用；升级 = 换文件名。
    校验：zip 结构 + dist-info 的 Version 必须等于本包版本（wheel 没有单独签名；sha256 记在旁边的 .sha256）。
    """
    import hashlib

    version = version or __version__
    dest_dir = dest_dir or _wheel_cache_dir()
    dest = dest_dir / wheel_asset_name(version)
    if dest.is_file() and _wheel_looks_valid(dest, version):
        return dest, None
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + ".part")
        if fetch is not None:
            fetch(url, part)
        else:
            import httpx

            with httpx.Client(timeout=120.0, follow_redirects=True) as http, http.stream("GET", url) as response:
                response.raise_for_status()
                with part.open("wb") as handle:
                    for chunk in response.iter_bytes():
                        handle.write(chunk)
        if not _wheel_looks_valid(part, version):
            part.unlink(missing_ok=True)
            return None, f"下载到的文件不是 horosa_skill {version} 的 wheel（结构或版本不符），配置里保留 URL。"
        digest = hashlib.sha256(part.read_bytes()).hexdigest()
        part.replace(dest)
        dest.with_name(dest.name + ".sha256").write_text(f"{digest}  {dest.name}\n", encoding="utf-8")
        return dest, None
    except Exception as exc:  # noqa: BLE001 - 预下载失败不阻断 setup：配置回退到 URL 形态
        return None, f"wheel 预下载失败（{type(exc).__name__}: {exc}）；配置里保留 URL，客户端冷启动时再取。"


def _build_client_config_payload(
    *, format_name: str, skill_root: Path, server_name: str, launcher: str, surface: str,
    wheel_source: str | None = None,
) -> tuple[dict[str, Any], list[str], dict[str, str]]:
    """`client config` 的产物，也是 `setup` 第 3 步（v0.38.0 B4）。返回 (payload, stdio 命令, 工具面 env)。

    源码 checkout 只在 `uv` 启动器与 mcporter/openclaw 形态下才需要：uvx 形态是给**没有 checkout** 的机器
    用的（wheel 装出来的包旁边没有 pyproject.toml），此前一律先 `_resolve_skill_root` → 零安装用户跑
    `client config --launcher uvx-wheel` 直接 BadParameter。
    """
    launcher_key = launcher.strip().lower()
    if launcher_key not in {"uv", "uvx", "uvx-git", "uvx-wheel"}:
        raise typer.BadParameter("`--launcher` must be `uv`, `uvx-wheel`, `uvx-git` or `uvx`.")
    resolved_skill_root: Path | None = None
    if launcher_key == "uv" or format_name.strip().lower() in {"mcporter", "openclaw"}:
        resolved_skill_root = _resolve_skill_root(skill_root)
    warnings: list[str] = []
    launcher_info: dict[str, Any] = {"kind": launcher_key}
    if launcher_key in {"uvx", "uvx-git", "uvx-wheel"}:
        # 🔴 写绝对路径（v0.38.0 B2）：GUI 客户端在 Windows 上不继承 shell PATH，裸 `uvx` = file not found。
        try:
            uvx_command = resolve_uvx_command()
        except FileNotFoundError as exc:
            uvx_command = ["uvx"]
            warnings.append(f"uvx 未找到，配置里只能写裸 `uvx`（GUI 客户端可能起不来）：{exc}")
    if launcher_key == "uvx-wheel":
        # 🔴 免 git、免 PyPI 的零安装（v0.38.0 B3）：每个 Release 都附带纯 Python wheel，`uvx --from <URL>` 直接起；
        # URL 走 HOROSA_RUNTIME_MIRROR 的前缀改写（github.com:443 不通的机器只需一个开关，issue #14）。
        # uvx 按 `--from` 的 URL 缓存环境：钉版本的 URL 稳定，升级 = 换 URL（重跑 client config / setup）。
        from horosa_skill.runtime.mirrors import mirror_candidates, preferred_mirror_url

        wheel_url = zero_install_wheel_url()
        # `wheel_source`（setup 预下载到 ~/.horosa/wheels 的本地文件）优先：冷启动零网络、离线可用。
        from_value = wheel_source or preferred_mirror_url(wheel_url)
        stdio_command = [*uvx_command, "--from", from_value, "horosa-skill", "serve", "--transport", "stdio"]
        launcher_info.update({
            "wheel_url": preferred_mirror_url(wheel_url),
            **({"wheel_cached_path": wheel_source} if wheel_source else {}),
            "alternatives": mirror_candidates(wheel_url),
            "pinned_version": __version__,
            "install_hint": f"uvx --from \"{preferred_mirror_url(wheel_url)}\" horosa-skill install",
            "refresh_hint": f"uvx --refresh --from \"{preferred_mirror_url(wheel_url)}\" horosa-skill --version",
            "docs": "docs/INSTALL_RESTRICTED_NETWORK.md（镜像 / API 直链 / 离线搬运）",
        })
    elif launcher_key == "uvx":
        # PyPI 分发（v0.36.0 C4）：不需要源码 checkout；离线 runtime 仍由 `uvx horosa-skill install` 装到默认目录。
        stdio_command = [*uvx_command, "horosa-skill", "serve", "--transport", "stdio"]
    elif launcher_key == "uvx-git":
        # 🔴 PyPI 尚未开通（`pip install horosa-skill` 现在是 404），所以 `uvx` 那条今天还跑不通。
        # 直接从 Git 装是**当下唯一可用的零安装路径**；钉当前版本 tag 让配置可复现。
        stdio_command = [
            *uvx_command, "--from",
            f"git+https://github.com/Horace-Maxwell/horosa-skill@v{__version__}#subdirectory=horosa-skill",
            "horosa-skill", "serve", "--transport", "stdio",
        ]
    else:
        uv_command = resolve_uv_command()
        stdio_command = [
            *uv_command,
            "run",
            "--directory",
            str(resolved_skill_root),
            "horosa-skill",
            "serve",
            "--transport",
            "stdio",
        ]
    key = format_name.strip().lower()
    surface_key = surface.strip().lower()
    if surface_key not in {"auto", "full", "compact"}:
        raise typer.BadParameter("`--surface` must be `auto`, `full` or `compact`.")
    use_compact = _CLIENT_COMPACT_DEFAULT.get(key, False) if surface_key == "auto" else surface_key == "compact"
    surface_env = {"HOROSA_MCP_COMPACT": "1"} if use_compact else {}
    tool_surface = {
        "mode": "compact" if use_compact else "full",
        "tools": COMPACT_SURFACE_TOOL_COUNT if use_compact else FACADE_TOOL_COUNT + len(TOOL_DEFINITIONS),
        "reason": (
            _CLIENT_COMPACT_REASON.get(key, "该客户端对工具总数敏感")
            if use_compact
            else f"该客户端能吃下全量平铺面（{FACADE_TOOL_COUNT + len(TOOL_DEFINITIONS)} 个工具）"
        ),
        "override": "--surface full / --surface compact",
    }
    if key in {"mcporter", "openclaw"}:
        payload: dict[str, Any] = _build_openclaw_config(
            skill_root=resolved_skill_root,
            server_name=server_name,
            format_name=key,
            isolate_home=None,
        )
    elif key == "claude-code":
        payload = {
            "note": "运行下面这一条命令即可把 Horosa 注册进 Claude Code（stdio 直连，无需常驻 serve）；或把 mcpServers 合并进项目的 .mcp.json / ~/.claude.json。",
            # 🔴 必须走 _format_cli_command：checkout / uv 路径里有空格（`C:\Users\John Doe\…`、
            # `/Users/x/My Projects`）时，裸 join 出来的命令会把路径拆成两个参数 —— README 教的
            # 就是这条复制粘贴命令。精简面顺带带上 `-e HOROSA_MCP_COMPACT=1`，与 setup 的写法一致。
            "command": _format_cli_command(
                ["claude", "mcp", "add", server_name]
                + [item for key, value in (surface_env or {}).items() for item in ("-e", f"{key}={value}")]
                + ["--", *stdio_command]
            ),
            "config_path": str(_preferred_config_path("claude-code")),
            "mcpServers": {
                server_name: {
                    "command": stdio_command[0],
                    "args": stdio_command[1:],
                    **({"env": surface_env} if surface_env else {}),
                }
            },
            "tool_surface": tool_surface,
            **({"env_note": "精简面：给这条命令加 `-e HOROSA_MCP_COMPACT=1`"} if use_compact else {}),
            "alternative_http": {
                # 跟随 launcher：uvx/uvx-git 用户没有 checkout，`uv run` 那条对他们不成立。
                "note": ("或先 `" + (" ".join(stdio_command[:-2]) if launcher_key != "uv"
                                     else "uv run --directory <checkout>/horosa-skill horosa-skill")
                         + " serve` 再注册 HTTP 端点："),
                "command": f"claude mcp add {server_name} --transport http http://127.0.0.1:8765/mcp",
            },
        }
    elif key == "claude-desktop":
        payload = {
            "note": "合并进 Claude Desktop 的 claude_desktop_config.json（mcpServers 键下）。",
            "config_path": str(_preferred_config_path("claude-desktop")),
            "tool_surface": tool_surface,
            "mcpServers": {
                server_name: {
                    "command": stdio_command[0],
                    "args": stdio_command[1:],
                    **({"env": surface_env} if surface_env else {}),
                }
            },
        }
    elif key == "codex":
        # Codex 硬约束（examples/clients/codex.md 有全文）：RawMcpServerConfig deny_unknown_fields
        # （字段写错=整段拒收）；env 不转发 shell 环境 → HOROSA_* 必须显式写进 env 表；
        # 启动超时默认 10 s < 首次冷启动（runtime 预热 ~45s）→ 显式 120s；工具默认 60s < 长盘
        # （tianxing 跨月扫描）→ 600s。首轮工具目录只等 1s（mcp_optional_startup_grace_ms=1000）：
        # 冷启动时第一轮对话可能看不到 horosa 工具，第二轮即恢复——要首轮即见就解开 required 注释
        # （代价：server 起不来时 Codex 启动直接报错）。
        payload = {
            "note": (
                "追加到 ~/.codex/config.toml（或用 --write 原位合并，只动 [mcp_servers." + server_name + "] 表并先备份）。"
                "HTTP 变体需先 `uv run horosa-skill serve`。"
            ),
            "config_path": str(_preferred_config_path("codex")),
            "toml_stdio": (
                f"[mcp_servers.{server_name}]\n"
                # command 必须与 args/cwd 一样走 json.dumps：JSON 转义 ⊂ TOML 基本字符串转义。
                # 裸插值在 Windows 上会把路径里的反斜杠原样写进 TOML → 整个文件不可解析
                # （tomllib: Unescaped '\'；mac/Linux 路径无反斜杠故恒绿，windows-smoke 才炸）。
                f"command = {json.dumps(stdio_command[0])}\n"
                f"args = {json.dumps(stdio_command[1:])}\n"
                # 🔴 cwd 只在 uv（源码 checkout）形态写。uvx 形态是给**没有 checkout** 的机器用的，
                # 写死本机路径 → 对方 Codex 起不来（cwd 不存在即 spawn 失败）。
                + (f"cwd = {json.dumps(str(resolved_skill_root))}\n" if launcher_key == "uv" else "")
                + (
                "# 冷启动（首次装 runtime/预热）可超 Codex 默认 10 s；长盘（择日扫描）可超默认工具 60 s。\n"
                "startup_timeout_sec = 120\n"
                "tool_timeout_sec = 600\n"
                "# 首轮即见工具（否则冷启动首轮目录里可能没有 horosa，第二轮恢复）；\n"
                "# 代价：server 启动失败时 Codex 直接报错。按需解开：\n"
                "# required = true\n"
                "\n"
                f"[mcp_servers.{server_name}.env]\n"
                + ("HOROSA_MCP_COMPACT = \"1\"          # " + tool_surface["reason"] + "\n" if use_compact else "")
                # 🔴 v0.38.1 C6：Codex 不转发你 shell 里的 HOROSA_*。runtime 根与数据目录显式写成绝对路径
                # （与 MCPB / 插件的 user_config 一致），否则 Codex 起的 server 会算出另一个 runtime 根。
                # 不写 `env_vars`：老版本 Codex 对未知键 deny_unknown_fields，会整块拒收这个 server。
                + f"HOROSA_RUNTIME_ROOT = {json.dumps(str(_codex_env_roots()['HOROSA_RUNTIME_ROOT']))}\n"
                + f"HOROSA_SKILL_DATA_DIR = {json.dumps(str(_codex_env_roots()['HOROSA_SKILL_DATA_DIR']))}\n"
                + "# Codex 不把 shell 环境交给 server——任何 HOROSA_* 必须在这里显式声明才可见，例如：\n"
                f"# HOROSA_MCP_COMPACT = \"1\"          # 11 门面模式（Codex 无工具搜索，{len(TOOL_DEFINITIONS)} 技法全量较重）\n"
                "# HOROSA_TOOLSETS = \"astro,cn\"      # 或按域裁剪\n"
                )
            ),
            "toml_http": (
                f"[mcp_servers.{server_name}]\n"
                "url = \"http://127.0.0.1:8765/mcp\"\n"
                "startup_timeout_sec = 120\n"
                "tool_timeout_sec = 600\n"
            ),
            "docs": "examples/clients/codex.md（含 exec 模式文本回落、enabled_tools 高频入口集、排障清单）",
            "tool_surface": tool_surface,
        }
    elif key == "cursor":
        # Cursor 官方 install deep link：config = base64({"command","args"})，点击即装。
        import base64

        cursor_entry = {"command": stdio_command[0], "args": stdio_command[1:]}
        if surface_env:
            cursor_entry["env"] = surface_env
        cursor_config = json.dumps(cursor_entry, ensure_ascii=False)
        encoded = base64.b64encode(cursor_config.encode("utf-8")).decode("ascii")
        payload = {
            "note": "点击 deep_link 一键安装进 Cursor；或把 mcpServers 合并进 ~/.cursor/mcp.json。",
            "config_path": str(_preferred_config_path("cursor")),
            "deep_link": f"cursor://anysphere.cursor-deeplink/mcp/install?name={server_name}&config={encoded}",
            "mcpServers": {server_name: cursor_entry},
            "tool_surface": tool_surface,
        }
    elif key == "vscode":
        # VS Code 官方安装链接（vscode:mcp/install?<url-encoded JSON>）+ CLI 等价命令。
        from urllib.parse import quote

        vscode_entry = {"name": server_name, "command": stdio_command[0], "args": stdio_command[1:]}
        if surface_env:
            vscode_entry["env"] = surface_env
        vscode_config = json.dumps(vscode_entry, ensure_ascii=False)
        # mcp.json 形状（`servers` 根键 + `type: stdio`）：让 --write / setup 能合并进用户级 mcp.json，
        # 而不是把 install_link/cli_command 这些说明写成配置（v0.38.0 B2）。
        vscode_file_entry: dict[str, Any] = {"type": "stdio", "command": stdio_command[0], "args": stdio_command[1:]}
        if surface_env:
            vscode_file_entry["env"] = surface_env
        payload = {
            "note": "点击 install_link 一键安装进 VS Code；或运行 cli_command；或把 servers 合并进用户级 mcp.json。",
            "config_path": str(_preferred_config_path("vscode")),
            "servers": {server_name: vscode_file_entry},
            "install_link": f"vscode:mcp/install?{quote(vscode_config, safe='')}",
            # 单引号只在 POSIX shell 里成立；cmd.exe / PowerShell 会把它当字面量 → JSON 解析失败。
            # 两条都给，让 Windows 用户不用自己猜转义。
            "cli_command": f"code --add-mcp '{vscode_config}'",
            "cli_command_windows": "code --add-mcp \"" + vscode_config.replace('"', '\\"') + "\"",
            "tool_surface": tool_surface,
        }
    elif key in {"gemini", "windsurf", "cline", "zed"}:
        # 四家都是「一个 JSON 文件里挂一个 stdio server」，只是根键与个别字段不同。
        entry: dict[str, Any] = {"command": stdio_command[0], "args": stdio_command[1:]}
        if surface_env:
            entry["env"] = surface_env
        if key == "gemini":
            # Gemini CLI 的 per-server `timeout` 是毫秒；默认 600000（10 分钟）已够长盘扫描。
            # `trust: false` = 每次工具调用仍走确认，别替用户放开。
            entry.update({"timeout": 600000, "trust": False})
            root_key = "mcpServers"
        elif key == "windsurf":
            root_key = "mcpServers"
        elif key == "cline":
            # Cline 的 per-server `timeout` 是**秒**（源码 sdk/packages/shared/src/mcp.ts：默认 60，范围 1–3600）。
            entry.update({"type": "stdio", "timeout": 600})
            root_key = "mcpServers"
        else:  # zed：context_servers 下直接 command/args/env（zed.dev/docs/ai/mcp，2026-09 核对）；无 `source` 字段
            # Zed 的 ContextServerCommand 也有 per-server `timeout`（秒，默认 60）——这才是 Zed 的真缺口。
            entry["timeout"] = 600
            root_key = "context_servers"
        config_path = str(_preferred_config_path(key))
        payload = {
            "note": f"合并进 {config_path}（{root_key} 键下）。",
            "config_path": config_path,
            root_key: {server_name: entry},
            "tool_surface": tool_surface,
        }
    else:
        raise typer.BadParameter(
            "format must be one of: claude-code / claude-desktop / cursor / vscode / codex / "
            "gemini / windsurf / cline / zed / mcporter / openclaw"
        )
    payload["launcher"] = launcher_info
    if warnings:
        payload["warnings"] = warnings
    return payload, stdio_command, surface_env


@client_app.command("config")
def client_config(
    format_name: str = typer.Option(
        "claude-code",
        "--format",
        help=(
            "Target client: claude-code / claude-desktop / cursor / vscode / codex / "
            "gemini / windsurf / cline / zed / mcporter / openclaw."
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
            "`full`（116 个工具）/ `compact`（11 个门面工具，全部技法仍可经 horosa_tool_run 到达）。"
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


@client_app.command("openclaw-config")
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


@client_app.command("openclaw-setup")
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
                    lambda: _run_openclaw_smoke_check(
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


@client_app.command("openclaw-check")
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
        report = _run_openclaw_smoke_check(
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


@report_app.command("template")
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


@report_app.command("render")
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


@report_app.command("from-tool")
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


@memory_app.command("query")
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


@memory_app.command("show")
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


@memory_app.command("answer")
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
