"""`setup` 一条命令接入的流程：网络探测 → 装 runtime → 写客户端配置 → 装 skill → doctor → 真 stdio 探针，逐步出结果与失败原因。命令本身在 cli.py。"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import typer

from horosa_skill import clients_extra
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
from horosa_skill.client_config.merge import _MERGEABLE_ROOT_KEYS, _merge_client_config
from horosa_skill.client_config.payload import (
    _build_client_config_payload,
    _cache_wheel,
    _format_cli_command,
    _resolve_skill_root,
)
from horosa_skill.client_tools import zero_install_wheel_url
from horosa_skill.config import Settings
from horosa_skill.errors import RuntimeError, bilingual
from horosa_skill.surfaces import doctor as doctor_checks
from horosa_skill.surfaces import runtime_helpers
from horosa_skill.surfaces.doctor import _SETUP_NETWORK_TIMEOUT_SECONDS, _doctor_report
from horosa_skill.surfaces.openclaw_smoke import _timed_call
from horosa_skill.surfaces.runtime_helpers import _install_progress_printer

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
        _resolve_skill_root(skill_root or runtime_helpers._package_root())
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
    root = skill_root or runtime_helpers._package_root()
    settings = Settings.from_env()
    manager = runtime_helpers._runtime_manager(settings)
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
