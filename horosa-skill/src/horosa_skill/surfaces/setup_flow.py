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
from horosa_skill.client_config import claude_cli, env_carry
from horosa_skill.client_config.audit import (
    _client_check_report,
    _normalize_client_entry,
)
from horosa_skill.client_config.locations import (
    _CLIENT_NAMES,
    _CLIENT_RESTART_HINTS,
    _client_config_locations,
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
from horosa_skill.knowledge import vectors as knowledge_vectors
from horosa_skill.surfaces import doctor as doctor_checks
from horosa_skill.surfaces import runtime_helpers
from horosa_skill.surfaces.doctor import _SETUP_NETWORK_TIMEOUT_SECONDS, _doctor_report
from horosa_skill.surfaces.openclaw_smoke import _timed_call
from horosa_skill.surfaces.runtime_helpers import _install_progress_printer

# ---------------------------------------------------------------------------
# `horosa-skill setup --client <target>`（v0.38.0 B4）：一条命令接入任意 MCP 客户端。
# 步骤固定、逐步记录、失败包结构化：network_probe → install → vectors → config → skill → doctor → client_check → stdio_probe → next_steps。
# 🔴 config 步之前失败保证 `config_untouched: true`；写过配置的失败包带 `backup_path`。
# v0.41.0 第 4 步 skill：把 horosa-agent skill 装进该客户端读的 skills 目录（只建议性：装不上不让 setup 失败，next_steps 说清楚）。
# 输出契约冻结在 tests/test_cli_output_contract.py；行为在 tests/test_setup_command.py。
# ---------------------------------------------------------------------------

_SETUP_STEPS = ("network_probe", "install", "vectors", "config", "skill", "doctor", "client_check", "stdio_probe", "next_steps")
# uvx-wheel 首跑要下载 wheel 与依赖（顺带焐热 uvx 缓存，客户端首次启动就快了）；uv 形态通常 5–10 s。
_SETUP_STDIO_TIMEOUT_SECONDS = 300.0
# 首次：uv 装 onnxruntime（约 128 MB）、下模型 24 MB、向量化全部笔记（CPU，几千段要几分钟）。
_SETUP_VECTORS_TIMEOUT_SECONDS = 1800.0
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
    """stdio 探针用的环境 = 客户端真会给 server 的那份：系统变量 ∪ 配置条目里写着的 env，**没有** shell 里的 `HOROSA_*`。

    🔴 旧写法让非 Codex 客户端「继承整个环境」：shell 里设了 HOROSA_RUNTIME_ROOT 而条目里没写，探针照样绿，
    客户端（GUI 不读 shell 配置）起的 server 却用另一个 runtime 根 / 另一份记忆库。只因 shell 才能跑的配置必须在这里红。
    """
    if client_key == "codex":
        base = {key: os.environ[key] for key in _CODEX_PASSTHROUGH_ENV if key in os.environ}
        return {**base, **extra_env}
    # v0.41.0：Copilot CLI 只转发 PATH——探针按同样的最坏形状起 server，才证明得了「env 表里写的够用」。
    narrowed = clients_extra.probe_env(client_key, extra_env)
    if narrowed is not None:
        return narrowed
    return {**env_carry.minimal_client_env(), **extra_env}


def _probe_env_shape(client_key: str) -> str:
    """探针环境的形状名（进 `steps.stdio_probe.env_shape`）：`codex` / `passthrough`（只转发点名的变量）/ `minimal`。"""
    if client_key == "codex":
        return "codex"
    return "passthrough" if clients_extra.probe_env(client_key, {}) is not None else "minimal"


def _probe_runtime_differences(probe: dict[str, Any], settings: Settings) -> list[dict[str, str]]:
    """探针读到的 `horosa://runtime/status` 与宿主 settings 逐项比：runtime 根、数据目录、两个引擎地址。

    每一项都决定「客户端起的 server 用哪套引擎、读写哪份记忆库」；任何一项对不上 = 终端里的环境变量没有传到客户端。
    状态里没有的项不比（老 server 只报 runtime_root，更老的没有这个资源）。
    """
    status = probe.get("runtime_status")
    if not isinstance(status, dict):
        return []

    def same_path(theirs: str, ours: Path) -> tuple[str, str] | None:
        try:
            left, right = Path(theirs).expanduser().resolve(), ours.expanduser().resolve()
        except OSError:
            return None
        return None if left == right else (str(left), str(right))

    def same_url(theirs: str, ours: str) -> tuple[str, str] | None:
        left, right = theirs.strip().rstrip("/"), str(ours).strip().rstrip("/")
        return None if left == right else (left, right)

    checks = (
        ("runtime_root", "HOROSA_RUNTIME_ROOT", "runtime 根", lambda v: same_path(v, settings.runtime_root)),
        ("data_dir", "HOROSA_SKILL_DATA_DIR", "数据目录", lambda v: same_path(v, settings.data_dir)),
        ("server_root", "HOROSA_SERVER_ROOT", "后端地址", lambda v: same_url(v, settings.server_root)),
        ("chart_server_root", "HOROSA_CHART_SERVER_ROOT", "星盘引擎地址", lambda v: same_url(v, settings.chart_server_root)),
    )
    differences: list[dict[str, str]] = []
    for field, variable, label, compare in checks:
        value = status.get(field)
        if not value:
            continue
        differing = compare(str(value))
        if differing:
            differences.append({"field": field, "env": variable, "label": label, "client": differing[0], "host": differing[1]})
    return differences


def _probe_runtime_mismatch(probe: dict[str, Any], settings: Settings) -> str | None:
    """上面那份差异的一句话版本（没有差异 → None）。"""
    differences = _probe_runtime_differences(probe, settings)
    if not differences:
        return None
    listed = "；".join(f"{item['label']}是 {item['client']}，而本机（终端）用的是 {item['host']}" for item in differences)
    return (
        f"客户端将要起的 server 算出的{listed}：环境变量没有传到客户端"
        "（Codex 不转发 shell 环境；GUI 客户端不读 shell 配置）。请把 "
        f"{' / '.join(item['env'] for item in differences)} 写进该客户端配置的 env 表，或统一用默认值。"
    )


def _configured_client_env(client_key: str, payload: dict[str, Any], surface_env: dict[str, str], *, root_key: str | None, server_name: str) -> dict[str, str]:
    """配置条目里**实际写着**的 env：这才是客户端会交给 server 的（Copilot CLI 的 HOME 与两个 runtime 根、TRAE 的超时变量）。

    只给 Codex 补根的旧写法，在 Copilot CLI 上把「配置写对了」测成 runtime_mismatch（v0.41.0 首次真探针实跑抓到）。
    """
    configured = {**surface_env, **(_codex_env_roots() if client_key == "codex" else {})}
    written = (payload.get(root_key) or {}).get(server_name) if root_key and root_key != "toml_stdio" else None
    if isinstance(written, dict):
        configured.update({str(k): str(v) for k, v in (_normalize_client_entry(written).get("env") or {}).items()})
    return configured


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
                            # mcp 2.x 的 ReadResourceRequestParams.uri 只收字符串（传 AnyUrl 校验失败，被下面吞成 None）。
                            resource = await session.read_resource("horosa://runtime/status")
                            text = next((c.text for c in resource.contents if getattr(c, "text", None)), None)
                            parsed = json.loads(text) if text else None
                            runtime_status = parsed if isinstance(parsed, dict) else None
                        except Exception:  # noqa: BLE001 - 探针起的可能是客户端钉住的旧版 server：
                            # 资源 horosa://runtime/status 自 v0.38.1 才有。等最低受支持版本都带它，这层就能去掉。
                            runtime_status = None
                        return {
                            "ok": True,
                            "tools": len(tools.tools),
                            "server_name": init.server_info.name,
                            "server_version": init.server_info.version,
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
# uv 的 `error: Failed to spawn: `horosa-skill`` / 旧版无反引号；`(os error 4551)` 不本地化，中间的系统描述会本地化。
_WINDOWS_SPAWN_RE = re.compile(r"Failed to spawn:\s*`?(?P<name>[^`\r\n]+?)`?\s*(?:\r?\n|$)", re.IGNORECASE)


def _diagnose_app_control(stderr_tail: str, command: list[str] | None) -> dict[str, Any] | None:
    """Windows 应用控制（Smart App Control / WDAC）拒绝执行 uv 现生成的 trampoline：`(os error 4551)`。

    `ERROR_SYSTEM_INTEGRITY_POLICY_VIOLATION`：uv / uvx 每建一个环境就现写一份 `Scripts\\horosa-skill.exe`，内容随安装路径变，
    云端永远没有它的信誉，开着 Smart App Control 的机器可能拒绝运行（同一台机器上时拦时放）。出路是不经 trampoline：
    `python -m horosa_skill`（环境里的 python.exe 是解释器自带的那份）。
    """
    if "(os error 4551)" not in (stderr_tail or ""):
        return None
    spawned = _WINDOWS_SPAWN_RE.search(stderr_tail or "")
    blocked = spawned.group("name").strip() if spawned else None
    from horosa_skill.client_config.payload import module_entry_command

    module_command = module_entry_command(list(command)) if command else None
    if module_command == list(command or []):
        module_command = None
    return {
        "cause": "windows_app_control_blocked",
        "blocked_program": blocked,
        **({"module_command": _format_cli_command(module_command)} if module_command else {}),
        "explanation": bilingual(
            f"Windows 应用控制（Smart App Control）拒绝运行 `{blocked or 'horosa-skill.exe'}`：这是 uv 为该环境现生成的启动器，"
            "没有数字签名、也没有云端信誉，所以 MCP server 还没启动就被系统拦下（os error 4551）。",
            f"Windows Application Control (Smart App Control) refused to run `{blocked or 'horosa-skill.exe'}`: uv generates "
            "this launcher per environment, so it is unsigned and has no cloud reputation, and the OS blocked it before "
            "the MCP server started (os error 4551).",
        ),
        "next_action": bilingual(
            "加 `--entry module` 重跑本命令：配置改写成 `… python -m horosa_skill serve`（venv 自带的 python.exe 不受影响），"
            "功能完全相同。不必为此关闭 Smart App Control。",
            "Re-run this command with `--entry module`: the config then starts `… python -m horosa_skill serve` (the venv's "
            "own python.exe is not affected) with identical behaviour. There is no need to turn Smart App Control off.",
        ),
    }


def _diagnose_probe_stderr(stderr_tail: str, command: list[str] | None = None) -> dict[str, Any] | None:
    """把 stdio 探针 stderr 里**可识别的环境性原因**翻成可操作的诊断；认不出返回 None（stderr_tail 原样保留）。

    Windows 独有（v0.39.0 维护机复验撞到）：一个已挂着的 horosa MCP 会话（`uv run … serve`）占着 venv 里的
    `Scripts\\horosa-skill.exe`（或已加载的 .pyd）；客户端这条 `uv run` 要先把 venv 同步到当前版本，删不掉被占文件
    → uv 在 MCP server 启动前就退出，stderr 只剩一屏构建噪声。macOS / Linux 能替换运行中的文件，不会遇到。
    另一种 Windows 独有形状见 `_diagnose_app_control`（应用控制拦 trampoline，v0.43.1）。
    """
    app_control = _diagnose_app_control(stderr_tail, command)
    if app_control:
        return app_control
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


def _vectors_choice(flag: bool | None, settings: Settings) -> tuple[bool, str]:
    """要不要开向量：显式参数优先；没给时沿用——模型只在用户要过时才下，它在就说明开过。

    升级靠重跑 setup：不带参数就把开关丢了的话，搜索质量会悄悄变差，还没有任何报错。
    """
    if flag is not None:
        return flag, "--vectors" if flag else "--no-vectors"
    if knowledge_vectors.enabled_by_env() and knowledge_vectors.model_ready(settings):
        return True, "模型已在本机（之前开过），沿用；--no-vectors 关闭"
    return False, "未开启（--vectors 开启）"


_VECTORS_FIX = {
    "deps": "依赖没能装进客户端起 server 的环境（常见原因：这个平台没有 onnxruntime 的轮子、连不上 PyPI）。",
    "download": "模型下载失败：设 HF_ENDPOINT=<镜像>（内容有 sha256 把关）重跑；或把两份文件放进 HOROSA_EMBED_MODEL_DIR 指的目录。",
    "disabled": "HOROSA_KNOWLEDGE_VECTORS 把向量关掉了：去掉这个变量再重跑。",
    "timeout": "准备超时（30 分钟）：网络太慢或笔记太多。可以重跑，已下载和已向量化的部分不会重做。",
    "unreadable": "准备命令的输出不是预期的 JSON（客户端启动器跑的可能是旧版本）。",
}


def _vectors_prepare(*, command: list[str], env: dict[str, str] | None, cwd: str | None, timeout: float) -> dict[str, Any]:
    """跑一次 `<客户端启动器> knowledge index --vectors`，把结果归成 ok / failure（deps·download·disabled·timeout·unreadable）。

    用的就是客户端起 server 的那个环境：`uvx` / `uv run` 在这里把依赖真装上，模型真下来，笔记真向量化。
    """
    def failed(kind: str, message: str, **extra: Any) -> dict[str, Any]:
        return {"ok": False, "failure": kind, "message": message, **extra}

    try:
        completed = subprocess.run(command, env=env, cwd=cwd, capture_output=True, timeout=timeout, check=False,
                                   text=True, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return failed("timeout", _VECTORS_FIX["timeout"])
    except OSError as exc:
        return failed("deps", f"启动器起不来：{type(exc).__name__}: {exc}")
    stderr_tail = (completed.stderr or "")[-2000:]
    try:
        report = json.loads(completed.stdout)
    except ValueError:
        report = None
    if not isinstance(report, dict):
        kind = "deps" if completed.returncode != 0 else "unreadable"
        return failed(kind, _VECTORS_FIX[kind], stderr_tail=stderr_tail, returncode=completed.returncode)
    status = report.get("vectors") if isinstance(report.get("vectors"), dict) else {}
    if report.get("code") == "knowledge.vectors_download_failed":
        return failed("download", f"{_VECTORS_FIX['download']}（{report.get('message')}）", vectors=status, stderr_tail=stderr_tail)
    if report.get("ok") and status.get("ready"):
        return report
    kind = "disabled" if report.get("ok") and status.get("enabled_by_env") is False else "deps"
    return failed(kind, _VECTORS_FIX[kind], vectors=status, stderr_tail=stderr_tail, returncode=completed.returncode)


def _knowledge_index_command(stdio_command: list[str]) -> list[str]:
    """客户端启动命令 → 同一个环境里的 `knowledge index --vectors`：只换 `serve` 及其参数。"""
    return [*stdio_command[:stdio_command.index("serve")], "knowledge", "index", "--vectors"]


def _run_claude(command: list[str]) -> subprocess.CompletedProcess[str]:
    """执行一条 `claude mcp …`（add / remove / add-json；单独成函数：测试用替身，不真调 claude）。"""
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
    output_script: str = "zh-Hans",
    entry: str = "auto",
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
    vectors: bool | None = None,
) -> dict[str, Any]:
    from horosa_skill.runtime.manager import host_platform_key, platform_dead_end_advice, platform_has_payload

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
    vectors_on, vectors_reason = _vectors_choice(vectors, settings)

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

    def announce(name: str, text: str) -> None:
        typer.echo(f"[{_SETUP_STEPS.index(name) + 1}/{total}] {name}: {text}", err=True)

    # ---- 1 network_probe
    manifest_location = manifest_url or settings.runtime_manifest_url or settings.default_runtime_manifest_url
    if dry_run or skip_install or archive or not probe_network:
        reason = "dry-run" if dry_run else "--skip-install" if skip_install else "--archive（离线安装）" if archive else "--no-probe-network"
        steps["network_probe"] = {"ok": True, "skipped": True, "reason": reason, "manifest_url": manifest_location}
    else:
        announce("network_probe", f"HEAD {manifest_location}（{_SETUP_NETWORK_TIMEOUT_SECONDS:.0f} s，镜像优先）")
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
    platform_key = settings.runtime_platform or host_platform_key()
    # 🔴 E-12：没有离线载荷可装的两种情形不是「安装失败」，是「这台机器不装 runtime」：
    #   · 外部引擎模式（HOROSA_SERVER_ROOT / HOROSA_CHART_SERVER_ROOT 指到别处）——装了也不会用；
    #   · 本平台没有载荷（Linux / Intel Mac）——旧实现在这里死掉，retry_command 原样重复同一次失败。
    # 跳过安装、照写配置（两个地址由 env_carry 写进条目），doctor 降为提示；出路写进 next_steps。
    # 接缝：平台判定用 runtime.manager.platform_has_payload；清单里缺本平台（发布不全）时 install 抛的
    # runtime.install_missing_platform 也按同一条路走。runtime 侧若改成返回「无载荷」结果，只需改这里的两个判断。
    no_runtime_reason: str | None = None
    if dry_run or skip_install:
        steps["install"] = {
            "ok": True, "skipped": True, "reason": "dry-run" if dry_run else "--skip-install",
            "would_install_from": archive or manifest_location,
            "platform": platform_key, "runtime_root": str(settings.runtime_root),
        }
    elif not archive and manager.runtime_mode() == "external":
        no_runtime_reason = "external_engine"
        steps["install"] = {
            "ok": True, "skipped": True, "reason": no_runtime_reason, "platform": platform_key,
            "server_root": settings.server_root, "chart_server_root": settings.chart_server_root,
            "explanation": bilingual(
                "引擎地址指向本机 runtime 之外（外部引擎 / 网关模式）：本机不装也不起离线 runtime，工具调用直连这两个地址。",
                "The engine addresses point outside the local runtime (external engine / gateway mode): nothing is installed "
                "or started here; tool calls go straight to those addresses.",
            ),
        }
    elif not archive and not platform_has_payload(platform_key):
        no_runtime_reason = "no_payload_for_platform"
        advice = platform_dead_end_advice(platform_key)
        steps["install"] = {"ok": True, "skipped": True, "reason": no_runtime_reason, "platform": platform_key,
                            "why": advice.get("reason"), "next_action": advice.get("next_action")}
    else:
        announce("install", "安装 / 校验离线 runtime（已是最新版则秒退；约 730MB 下载、解压后约 2GB）…")
        try:
            result, seconds = _timed_call(
                lambda: manager.install(archive=archive, manifest_url=manifest_url, progress=_install_progress_printer())
            )
        except RuntimeError as exc:
            if exc.code != "runtime.install_missing_platform":
                fail("install", exc.code, str(exc), exc.details)
            # 清单里没有本平台：与「本平台没有载荷」同一条路（跳过、照写配置），不让重试命令重复同一次失败。
            no_runtime_reason = "no_payload_for_platform"
            result, seconds = None, 0.0
            details = exc.details or {}
            steps["install"] = {"ok": True, "skipped": True, "reason": no_runtime_reason, "platform": platform_key,
                                "manifest_url": manifest_location, "supported_platforms": details.get("supported_platforms"),
                                "why": details.get("reason") or str(exc), "next_action": details.get("next_action")}
        except OSError as exc:
            fail("install", "runtime.install_io_error", str(exc), {})
        if result is not None:
            steps["install"] = {
                "ok": True, "seconds": seconds, "changed": result.get("changed"),
                "skipped_download": bool(result.get("skipped_download")), "platform": result.get("platform"),
                "platform_fallback": result.get("platform_fallback"), "warnings": result.get("warnings") or [],
                "version": (result.get("manifest") or {}).get("version"), "runtime_root": result.get("runtime_root"),
            }

    # ---- 3 vectors / 4 config：先生成配置（不落盘），向量验证过了才写——写上 `[vectors]` 而依赖装不上，server 就起不来了。
    announce("config", f"生成 {client_key} 配置（launcher={launcher_key}）…")
    try:
        wheel_source: str | None = None
        wheel_cache_note: str | None = None
        if launcher_key == "uvx-wheel" and cache_wheel and not dry_run:
            # v0.38.1 C15：先把 wheel 落到 ~/.horosa/wheels/，配置里写本地路径 → 客户端冷启动零网络、离线可起。
            from horosa_skill.runtime.mirrors import preferred_mirror_url

            announce("config", "预下载 wheel 到 ~/.horosa/wheels/（配置里写本地路径；--no-cache-wheel 可跳过）…")
            cached, wheel_cache_note = _cache_wheel(preferred_mirror_url(zero_install_wheel_url()))
            wheel_source = str(cached) if cached else None
        payload, stdio_command, surface_env = _build_client_config_payload(
            format_name=client_key, skill_root=root, server_name=server_name, launcher=launcher_key, surface=surface,
            wheel_source=wheel_source, output_script=output_script, entry=entry, vectors=vectors_on,
        )
        if wheel_cache_note:
            payload.setdefault("warnings", []).append(wheel_cache_note)
    except typer.BadParameter as exc:
        fail("config", "setup.config_build_failed", str(exc), {"launcher": launcher_key, "skill_root": str(root)})
    declared_root = payload.get("root_key")
    root_key = "toml_stdio" if client_key == "codex" else (
        declared_root if isinstance(declared_root, str) and isinstance(payload.get(declared_root), dict)
        else next((key for key in _MERGEABLE_ROOT_KEYS if isinstance(payload.get(key), dict)), None)
    )
    configured_env = _configured_client_env(client_key, payload, surface_env, root_key=root_key, server_name=server_name)
    probe_cwd = str(root) if (launcher_key == "uv" and root is not None) else str(_project_root())

    vectors_step: dict[str, Any] = {"requested": vectors_on, "reason": vectors_reason}
    if vectors_on and not (dry_run or not write):
        prepare_command = _knowledge_index_command(stdio_command)
        announce("vectors", "把依赖装进客户端起 server 的环境（首次约 128 MB）、下载并校验模型（24 MB）、向量化笔记…")
        # 全环境 ∪ 配置里的 env：这一步要能走用户的代理 / HF_ENDPOINT；「Codex 只给最小环境也够用」由 stdio 探针证明。
        prepared, seconds = _timed_call(lambda: _vectors_prepare(
            command=prepare_command, env={**os.environ, **configured_env}, cwd=probe_cwd, timeout=_SETUP_VECTORS_TIMEOUT_SECONDS,
        ))
        vectors_step.update({"ok": prepared.get("ok") is True, "seconds": seconds, "command": _format_cli_command(prepare_command)})
        if not prepared.get("ok"):
            diagnosis = _diagnose_probe_stderr(str(prepared.get("stderr_tail") or ""), command=prepare_command)
            vectors_step.update({key: prepared[key] for key in ("failure", "message", "stderr_tail", "vectors") if key in prepared})
            if diagnosis:
                vectors_step["diagnosis"] = diagnosis
            steps["vectors"] = vectors_step
            fail("vectors", "setup.vectors_failed",
                 f"{diagnosis['explanation'] if diagnosis else prepared.get('message')} 配置一个字没动；不要向量就加 --no-vectors，搜索照常（BM25）。",
                 {key: value for key, value in vectors_step.items() if key != "ok"}, retry_extra=("--no-vectors",))
        vectors_step.update({"engine": prepared.get("engine"), "embedded": (prepared.get("sync") or {}).get("vectors", 0),
                             "entries": prepared.get("entries"), "model": (prepared.get("vectors") or {}).get("model")})
    else:
        vectors_step.update({"ok": True, "skipped": True})
        if vectors_on:
            vectors_step.update({"reason": "dry-run" if dry_run else "--no-write",
                                 "would_run": _format_cli_command(_knowledge_index_command(stdio_command))})
    steps["vectors"] = vectors_step

    target: Path | None = config.expanduser().resolve() if config is not None else None
    mode = "merge"
    add_command: list[str] | None = None
    if client_key == "claude-code" and target is None:
        project_mcp = _project_root() / ".mcp.json"
        if scope == "project" or (scope == "auto" and project_mcp.is_file()):
            target = project_mcp
        else:
            # 用户级注册走官方命令（可 `claude mcp remove` 回退），不去手改 ~/.claude.json 这份状态文件。
            # 命令怎么拼（名字必须在 `-e` 前）、已有条目怎么办（读 → 比 → 换）都在 client_config/claude_cli.py。
            mode = "claude-mcp-add"
            add_command = claude_cli.add_command("claude", server_name, stdio_command, surface_env)
    elif target is None and payload.get("config_mode") == "printed":
        # v0.41.0：没有文档化用户级配置文件的客户端（TRAE）——打印一键导入链接与可粘贴 JSON，不猜路径写文件。
        mode = "printed"
    elif target is None:
        target = _preferred_config_path(client_key)
    config_step: dict[str, Any] = {
        "mode": mode, "path": str(target) if target is not None else None,
        "server_block": payload.get(root_key) if root_key else None,
        "launcher": payload["launcher"], "tool_surface": payload["tool_surface"],
    }
    if payload.get("warnings"):
        config_step["warnings"] = payload["warnings"]
    # 终端里的 HOROSA_*：哪些写进了条目的 env（carried_env）、哪些会改行为却没写（shell_only_env）。只有名字。
    config_step.update({key: payload[key] for key in ("carried_env", "shell_only_env") if payload.get(key)})
    if add_command is not None:
        config_step["command"] = claude_cli.shell_text(add_command)
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
            # 🔴 `claude mcp add` 只会新增：同名条目在时它（和 add-json）以 "already exists" 退出码 1 结束。
            # 重跑 setup 因此必须先读已有条目：一致 → 不动；不同 → remove + add（add 失败把旧条目装回去）。
            outcome, seconds = _timed_call(lambda: claude_cli.register_user_server(
                claude_bin=shutil.which("claude") or "claude", server_name=server_name, stdio_command=stdio_command,
                env=surface_env, run=_run_claude, config_path=_client_config_locations("claude-code")[0],
            ))
            state["config_untouched"] = not outcome["touched"]
            if not outcome["ok"]:
                restored = outcome.get("restored_previous")
                fail(
                    "config", "setup.claude_mcp_add_failed",
                    f"`{outcome['failed_command']}` 没成功（退出码 {outcome['returncode']}）。"
                    + ("原来的注册已装回去，没有变化。" if restored
                       else "原来的注册已被移除且没能装回去：执行 details.restore_command 可恢复。" if restored is False
                       else ""),
                    {key: outcome[key] for key in ("command", "commands", "failed_command", "returncode", "stdout", "stderr",
                                                   "restored_previous", "restore_command", "rollback_redacted") if key in outcome},
                )
            config_step.update({"ok": True, "seconds": seconds, **{
                key: outcome[key] for key in ("status", "executed", "commands", "changes", "rollback", "rollback_redacted",
                                              "previous_entry_unreadable", "stdout") if key in outcome}})
    else:
        assert target is not None
        try:
            written, seconds = _timed_call(lambda: _merge_client_config(target, payload))
        except typer.BadParameter as exc:
            fail("config", "setup.config_merge_refused", str(exc), {"path": str(target)})
        state["config_untouched"] = False
        state["backup_path"] = written.get("backup")
        config_step.update({"ok": True, "seconds": seconds, "written": written, "changed": written.get("changed"),
                            "backup": written.get("backup")})
    steps["config"] = config_step

    # ---- 4 skill
    steps["skill"] = _setup_skill_step(client_key, enabled=skill, skill_dir=skill_dir, plan_only=dry_run or not write,
                                       announce=lambda text: announce("skill", text))

    # ---- 5 doctor
    announce("doctor", "体检…")
    report, seconds = _timed_call(lambda: _doctor_report(settings, manager))
    issues = [str(item) for item in report.get("issues") or []]
    installed = report.get("installed") is True
    ready = (
        installed
        and set(issues) <= {"services:not_running"}
        and report.get("platform_supported") is not False
        and not (report.get("port_conflicts") or [])
    )
    # 没装就不该因为「没装」失败；结果照报。这台机器本就不装 runtime（外部引擎 / 无载荷）同理。
    advisory = dry_run or skip_install or no_runtime_reason is not None
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
        announce("client_check", "回读磁盘上的配置…")
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
        announce("stdio_probe", "用客户端将要执行的命令真起一次 MCP server（stdio，不起离线 runtime）…")
        expected = int(payload["tool_surface"]["tools"])
        probe_args = [*stdio_command[1:], "--skip-runtime-start"]
        # 🔴 v0.38.1 C14：按**客户端的形状**起——系统变量 ∪ 配置里的 env 表，shell 里的 HOROSA_* 一个不带（见 _client_probe_env）；
        # cwd = 项目根（uv 形态 = Codex 的 cwd）。再读 horosa://runtime/status，抓「server 算出的 runtime 根 ≠ 终端里的」。
        probe_env = _client_probe_env(client_key, configured_env)
        probe, seconds = _timed_call(
            lambda: _stdio_probe(command=stdio_command[0], args=probe_args, env=probe_env,
                                 timeout=_SETUP_STDIO_TIMEOUT_SECONDS, cwd=probe_cwd)
        )
        mismatch = _probe_runtime_mismatch(probe, settings) if probe.get("ok") else None
        probe_ok = probe.get("ok") is True and probe.get("tools") == expected and mismatch is None
        steps["stdio_probe"] = {"ok": probe_ok, "seconds": seconds, "expected_tools": expected, "env_shape": _probe_env_shape(client_key),
                                "cwd": probe_cwd, "command": _format_cli_command([stdio_command[0], *probe_args]), **probe}
        if mismatch:
            steps["stdio_probe"]["runtime_mismatch"] = mismatch
            fail("stdio_probe", "setup.stdio_probe_runtime_mismatch", mismatch,
                 {**probe, "host_runtime_root": str(settings.runtime_root), "command": steps["stdio_probe"]["command"],
                  "mismatched": _probe_runtime_differences(probe, settings)})
        if probe_ok and vectors_on and not steps["vectors"].get("skipped"):
            # 准备步骤跑在全环境里；客户端给 server 的环境可能更窄（Codex）。server 自己报 ready 才算开着。
            served = (probe.get("runtime_status") or {}).get("knowledge_vectors")
            steps["stdio_probe"]["knowledge_vectors"] = served
            if not (isinstance(served, dict) and served.get("ready") is True):
                fail("stdio_probe", "setup.stdio_probe_vectors_not_ready",
                     "server 起来了，但它自己报向量没就绪：客户端给 server 的环境和准备时不一样。搜索照常可用（BM25）。",
                     {"knowledge_vectors": served, "command": steps["stdio_probe"]["command"],
                      "next_action": "看 knowledge_vectors 哪一项是 false；重跑 setup，或加 --no-vectors 回到纯 BM25。"})
        if not probe_ok:
            # 起不来时先认环境性原因（Windows 文件锁），认出来就给人话 + 可执行的下一步，而不是一屏 uv 构建噪声。
            diagnosis = None if probe.get("ok") else _diagnose_probe_stderr(
                str(probe.get("stderr_tail") or ""), command=[stdio_command[0], *probe_args],
            )
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
    if vectors_on and not steps["vectors"].get("skipped"):
        next_steps.append(
            f"向量检索已开（{steps['vectors'].get('model')}）：本次向量化 {steps['vectors'].get('embedded')} 段，之后新增 / 改动的笔记自动补上。"
            "换了说法也能搜到；关闭：重跑 setup 加 --no-vectors。"
        )
    if config_step.get("carried_env"):
        next_steps.append(
            f"终端里设着的 {'、'.join(config_step['carried_env'])} 已写进该客户端条目的 env（客户端不读你的 shell 环境）；"
            "以后改了这些值，重跑本命令即可。"
        )
    if config_step.get("shell_only_env"):
        next_steps.append(
            f"终端里设着的 {'、'.join(config_step['shell_only_env'])} 没有写进配置：客户端起的 server 看不到它们，"
            "要生效请自己加进条目的 env 表。"
        )
    if no_runtime_reason == "external_engine":
        next_steps.append(
            f"外部引擎模式：工具调用直连 {settings.server_root} 与 {settings.chart_server_root}（地址已写进客户端配置），"
            "本机不装也不起离线 runtime；那两个地址上的服务要一直开着。"
        )
    elif no_runtime_reason == "no_payload_for_platform":
        next_steps.append(
            f"这台机器（{platform_key}）没有离线载荷，runtime 没装：走网关模式——在 darwin-arm64 / win32-x64 机器上跑 runtime，"
            f"然后 `HOROSA_SERVER_ROOT=http://<那台机器>:9999 HOROSA_CHART_SERVER_ROOT=http://<那台机器>:8899 "
            f"{_setup_command_text(client_key, launcher=launcher_key, config=config)}` 重跑本命令（两个地址会写进客户端配置）。"
        )
    elif issues == ["services:not_running"]:
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
        else "runtime 不在本机（外部引擎模式）" if no_runtime_reason == "external_engine"
        else f"runtime 未安装（{platform_key} 没有离线载荷，见 next_steps）" if no_runtime_reason == "no_payload_for_platform"
        else "runtime 已是最新" if steps["install"].get("skipped_download") else "runtime 已安装"
    )
    config_text = (
        f"配置计划写到 {target}" if (dry_run or not write) and target is not None
        else f"配置已是最新（{target} 未改动）" if mode == "merge" and target is not None and steps["config"].get("changed") is False
        else f"配置已写入 {target}" if mode == "merge" and target is not None
        else "Claude Code 用户级注册已是最新（未改动）" if mode == "claude-mcp-add" and steps["config"].get("status") == "unchanged"
        else "已更新 Claude Code 用户级注册（remove + add）" if mode == "claude-mcp-add" and steps["config"].get("status") == "updated"
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
    if vectors_on:
        skill_text += "；向量检索计划开启" if steps["vectors"].get("skipped") else "；向量检索已开"
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
