"""`doctor` / `runtime status` 的体检：端口归属与监听范围、架构 / 载荷 / 内部端口告警、下一步建议（`_DOCTOR_ADVICE`）、环境探针（uv / 可执行文件 / 发布清单可达性），以及带时间预算的整份报告。命令本身在 cli.py。"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from horosa_skill.client_tools import resolve_uv_command
from horosa_skill.config import Settings
from horosa_skill.runtime import HorosaRuntimeManager
from horosa_skill.surfaces.openclaw_smoke import _openclaw_setup_command
from horosa_skill.surfaces.toolsets import doctor_warnings as _toolsets_doctor_warnings  # MCP-07（surface 批）


def _network_hints() -> dict[str, Any]:
    """代理/镜像相关的现场事实 —— 这些是「装不上 / 连不上本地后端」最常见的两类成因。"""
    from horosa_skill.config import mask_url_userinfo

    # 🔴 C-21：代理 URL 常带账号口令（`http://user:pass@proxy:8080`），doctor 的 JSON 会被贴进 issue / 聊天 —— 只给 scheme / 主机 / 端口。
    proxy_vars = {
        name: mask_url_userinfo(os.environ[name])
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
            "evidence": identity.get("evidence"),
            "app": identity.get("app"),
            "holders": identity.get("holders") or [],
            "will_not_kill": "本工具不会终止不属于自己的进程。",
        })
    # E-07：HTTP 上没应答、socket 上却有人占着的端口（不说 HTTP 的服务 / 只 accept 不应答）—— start 会因此超时。
    for taker in report.get("port_takers") or []:
        conflicts.append({
            "label": taker.get("label"),
            "url": taker.get("url"),
            "port": taker.get("port"),
            "verdict": "silent_listener",
            "evidence": "socket.accepting" if taker.get("accepting") else "socket.bind_refused",
            "app": None,
            "holders": taker.get("holders") or [],
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
    "env:rejected_value", "env:invalid_url", "js_engine:unavailable",
    "config:toolsets_invalid",  # MCP-07（surface 批）：HOROSA_TOOLSETS 一个合法值都没有 / 有不认识的值
)
_DOCTOR_ADVICE: dict[str, dict[str, str]] = {
    # MCP-07（surface 批）
    "config:toolsets_invalid": {
        "user_summary": "HOROSA_TOOLSETS 里有不认识的值：客户端只看到一部分技法工具（一个合法值都没有时只有门面工具 + horosa_tool_run）。",
        "next_action": "改正 HOROSA_TOOLSETS（合法值见 doctor 的 warnings.detail）或删掉它，然后重启客户端。",
    },
    "memory:needs_attention": {
        "user_summary": "本机存档有要处理的事：坏库被隔离过、有 run 文件不在记忆库里，或上次重建没做完（详见 memory_db.health）。",
        "next_action": "跑 `horosa-skill memory rebuild`（只增不删）；隔离出来的 .bak 文件确认记录都在后可以自己删。",
    },
    "runtime.manifest_invalid": {
        "user_summary": "已装 runtime 的 runtime-manifest.json 缺失或损坏，doctor 无法信任这份安装。",
        "next_action": "重跑 `horosa-skill install --force`（会重新解包并写回清单）。",
    },
    "runtime.state_invalid": {
        "user_summary": "runtime-state.json 损坏（上次启动被打断或磁盘写坏），启停状态不可信。",
        "next_action": "`horosa-skill runtime stop` 后再 `runtime start`；仍不行就删掉 runtime-state.json 重启。",
    },
    "runtime:not_installed": {
        "user_summary": "离线 runtime 还没装（本机模式下所有技法都要它）。",
        "next_action": "运行 `horosa-skill install`（约 730 MB 下载），装好后 `horosa-skill selfcheck`。",
    },
    "runtime:root_not_writable": {
        "user_summary": "runtime 目录写不了（只读盘、权限不对或路径指到了别人的目录）：install / start 都会被拒（runtime.root_not_writable）。",
        "next_action": "把 HOROSA_RUNTIME_ROOT 指到一个可写目录，或修好该目录的权限。",
    },
    "external:unreachable": {
        "user_summary": "网关模式（HOROSA_SERVER_ROOT / HOROSA_CHART_SERVER_ROOT 指向别处）下，那边的服务不可达。",
        "next_action": "确认那台机器上的服务在跑、地址写成完整的 http:// URL；想改用本机 runtime 就取消这两个变量。",
    },
    "js_engine:unavailable": {
        "user_summary": "本地 JS 引擎不可用（js_engine.state 说明原因）：八字 / 紫微 / 奇门 / 太乙 / 六壬等本地 JS 技法会失败，其余照常。",
        "next_action": "按 js_engine.fix 处理：`horosa-skill install --engine-only`（任何平台，只装 JS 引擎），或装离线 runtime，或设 HOROSA_CORE_JS_ROOT（都要 node ≥ 20.10）。",
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
    "env:rejected_value": {
        "user_summary": "有环境变量的值认不出或超出范围，已按默认值处理（detail 里点名变量、原因与实际用的值；密钥类的值不显示）。",
        "next_action": "改成合法的值（或删掉它用默认值），然后重启 AI 客户端。",
    },
    "env:invalid_url": {
        "user_summary": "服务根 URL 的形状不对（缺 http:// 前缀、没有主机或端口不是数字）：这个值照原样在用，连接会失败。",
        "next_action": "写成完整的 URL，例如 HOROSA_SERVER_ROOT=http://127.0.0.1:9999，然后重启 AI 客户端。",
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


def _env_flag_audit() -> dict[str, Any]:
    """未知 / 已移除的 HOROSA_*、已设旗标的档位、取值被拒的变量。只收集不打日志：Settings.from_env 已经打过一遍（E-15）。"""
    from horosa_skill.config import ENV_FLAG_REGISTRY, audit_env_flags, env_rejections

    try:
        audit: dict[str, Any] = {"ok": True, "warnings": audit_env_flags(log=False)}
    except ValueError as exc:
        audit = {"ok": False, "warnings": [str(exc)]}
    audit["set"] = {key: ENV_FLAG_REGISTRY.get(key, "unknown") for key in sorted(os.environ) if key.startswith("HOROSA_")}
    audit["rejected"] = env_rejections()
    return audit


def _env_rejection_warnings(rejected: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    """E-10：认不出的 env 值一条一条点名（值已按名字遮过：密钥类整段遮掉，URL 遮 userinfo）。"""
    warnings: list[dict[str, str]] = []
    for name, entry in sorted(rejected.items()):
        kept = entry.get("action") == "kept_as_is"
        coded = {"code": "env:invalid_url"} if kept else {"code": "env:rejected_value"}
        advice = _advice_for(coded["code"])
        detail = (f"{name}={entry.get('value')!r}: {entry.get('reason')}; "
                  + ("the value is used as-is" if kept else f"using the default {entry.get('used')!r}"))
        warnings.append({**coded, "variable": name, "detail": detail, "fix": advice["next_action"]})
    return warnings


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


def _deployment_of(report: dict[str, Any]) -> str:
    """managed / external / not_installed —— manager.doctor 已经给出；外面拼的报告（测试、旧调用方）按 mode + installed 推。"""
    if report.get("deployment") in {"managed", "external", "not_installed"}:
        return str(report["deployment"])
    if report.get("mode") == "external":
        return "external"
    return "managed" if report.get("installed") is True else "not_installed"


def _next_steps_when_ready() -> tuple[str, str]:
    """就绪后的下一步：客户端中立；只有确知是 OpenClaw（设了 OPENCLAW_WORKSPACE）时才给 OpenClaw 的命令（MCP-10）。"""
    from horosa_skill.runtime.hints import cli_command

    if os.environ.get("OPENCLAW_WORKSPACE"):
        command = _openclaw_setup_command(Path(os.environ["OPENCLAW_WORKSPACE"]))
        return (f"运行 `{command}` 写好 OpenClaw 配置并冒烟。", f"Run `{command}` to write the OpenClaw config and smoke-test it.")
    setup = cli_command("setup --client <your-client>")
    config = cli_command("client config --format <client>")
    selfcheck = cli_command("selfcheck")
    clients = "claude-code / claude-desktop / cursor / vscode / codex / gemini / windsurf / cline / zed …"
    return (
        f"把 AI 客户端接上：`{setup}`（{clients}；只想看配置用 `{config}`），然后 `{selfcheck}` 做一次端到端活体检查。",
        f"Connect your AI client: `{setup}` ({clients}; `{config}` only prints the config), then `{selfcheck}` for an "
        "end-to-end live check.",
    )


def _doctor_summary(report: dict[str, Any]) -> dict[str, Any]:
    """一句结论 + 一条下一步。🔴 E-05 / E-06 / MCP-10：**先定模式**（managed / external / not_installed），每句话都从模式推出；
    中英成对（`中文 / English`）；命令按安装上下文写（hints.cli_command）；不再对所有人说「去配 OpenClaw」。"""
    from horosa_skill.errors import bilingual
    from horosa_skill.runtime.hints import cli_command, install_command

    issues = [str(issue) for issue in report.get("issues", [])]
    reachable_endpoints = [
        endpoint.get("label")
        for endpoint in report.get("endpoints", [])
        if endpoint.get("reachable") is True
    ]
    deployment = _deployment_of(report)
    conflicts = report.get("port_conflicts") or []
    unexpanded = report.get("unexpanded_env_templates") or {}
    js = report.get("js_engine") if isinstance(report.get("js_engine"), dict) else None
    js_down = bool(js) and js.get("ok") is False

    def result(status: str, zh: str, en: str, next_zh: str, next_en: str) -> dict[str, Any]:
        ready = status == "ready"
        if ready and js_down:
            zh += f" 但本地 JS 引擎不可用（{js.get('state')}）：{str(js.get('affects') or '').split(' / ')[0]}会失败。"
            en += f" The local JS engine is unavailable ({js.get('state')}), so {str(js.get('affects') or '').split(' / ')[-1]} will fail."
            fix = str(js.get("fix") or "")
            next_zh = f"{fix.split(' / ')[0].rstrip('。')}；{next_zh}" if fix else next_zh
            next_en = f"{fix.split(' / ')[-1].rstrip('.')}; {next_en}" if fix else next_en
        return {
            "status": status, "ready_for_openclaw": ready, "deployment": deployment,
            "user_summary": bilingual(zh, en), "next_action": bilingual(next_zh, next_en),
            "reachable_endpoints": reachable_endpoints,
        }

    if unexpanded:
        names = "、".join(sorted(unexpanded))
        return result(
            "needs_attention",
            f"环境变量 {names} 的值还是未展开的占位符（宿主没有替换它），已按未设置处理——通常是 MCPB / 插件配置里的 user_config 没填。",
            f"The environment variables {', '.join(sorted(unexpanded))} still hold unexpanded placeholders (the host did not "
            "substitute them) and were treated as unset — usually an empty user_config in the MCPB / plugin settings.",
            "在客户端的扩展设置里补上这些值，或直接删掉这些环境变量用默认路径。",
            "Fill these values in the client's extension settings, or remove the variables to use the default paths.",
        )

    # ── 网关：本机什么都不起，只看那两个地址通不通 ──
    if deployment == "external":
        if "external:unreachable" in issues:
            down = [str(e.get("url")) for e in report.get("endpoints", []) if e.get("reachable") is not True]
            return result(
                "needs_attention",
                f"网关模式（HOROSA_SERVER_ROOT / HOROSA_CHART_SERVER_ROOT 指向别处，本机不起服务）：{', '.join(down)} 不可达。",
                f"Gateway mode (HOROSA_SERVER_ROOT / HOROSA_CHART_SERVER_ROOT point elsewhere; nothing runs locally): "
                f"{', '.join(down)} cannot be reached.",
                "确认那台机器上的 Horosa 服务在跑、地址与端口写对了（要完整的 http:// URL）；想改用本机 runtime，就取消这两个变量。",
                "Check that the Horosa services on that machine are running and the address and port are right (a full "
                "http:// URL); to use a local runtime instead, unset both variables.",
            )
        steps_zh, steps_en = _next_steps_when_ready()
        return result(
            "ready",
            "就绪（网关模式）：本机不起服务，HOROSA_SERVER_ROOT / HOROSA_CHART_SERVER_ROOT 指向的服务都可达。",
            "Ready (gateway mode): nothing runs locally, and the services HOROSA_SERVER_ROOT / HOROSA_CHART_SERVER_ROOT "
            "point at are reachable.",
            steps_zh, steps_en,
        )

    # ── 还没装：一句话，不是 12 条 missing:* ──
    if deployment == "not_installed":
        if report.get("platform_supported") is False:
            # E-02：没有载荷的平台也能有本地 JS 引擎（engine-only 资产）；结论按引擎在不在分两句。
            engine_ok = bool(js) and js.get("ok") is True
            engine_zh = ("本地 JS 引擎已就位（八字、六爻、大六壬等本地 JS 技法可用）。" if engine_ok else
                         f"本地 JS 引擎也还没有：`{cli_command('install --engine-only')}` 装上它（约 7 MB，需 Node.js ≥ 20.10）。")
            engine_en = ("The local JS engine is in place (BaZi, Liuyao, Liuren and the other local JS techniques work)." if engine_ok else
                         f"The local JS engine is missing too: `{cli_command('install --engine-only')}` installs it (about 7 MB; "
                         "needs Node.js >= 20.10).")
            return result(
                "needs_attention",
                "本机平台没有离线 runtime 载荷 —— 只发 darwin-arm64 与 win32-x64（Windows on ARM 自动装 x64 载荷走仿真；"
                f"Intel Mac 与 Linux 没有载荷）。{engine_zh}",
                "There is no offline runtime payload for this platform — only darwin-arm64 and win32-x64 are published "
                f"(Windows on ARM installs the x64 payload under emulation; Intel Macs and Linux have none). {engine_en}",
                "其余技法走网关模式：在一台受支持的机器上跑 runtime，本机设 HOROSA_SERVER_ROOT 与 HOROSA_CHART_SERVER_ROOT 指过去。",
                "For the other techniques use gateway mode: run the runtime on a supported machine and point HOROSA_SERVER_ROOT "
                "and HOROSA_CHART_SERVER_ROOT at it.",
            )
        hint = install_command()
        if "runtime:root_not_writable" in issues:
            problem = (report.get("runtime_root_writable") or {}).get("problem")
            return result(
                "needs_attention",
                f"离线 runtime 还没装，而且 runtime 目录 {report.get('runtime_root')} 写不了（{problem}）。",
                f"The offline runtime is not installed, and the runtime directory {report.get('runtime_root')} is not "
                f"writable ({problem}).",
                f"把 HOROSA_RUNTIME_ROOT 指到一个可写目录（或修好权限），再运行 `{hint['install']}`。",
                f"Point HOROSA_RUNTIME_ROOT at a writable directory (or fix the permissions), then run `{hint['install']}`.",
            )
        return result(
            "needs_attention",
            "离线 runtime 还没装。",
            "The offline runtime is not installed yet.",
            f"运行 `{hint['install']}`（约 730 MB 下载），装好后 `{cli_command('selfcheck')}`。",
            f"Run `{hint['install']}` (~730 MB download), then `{cli_command('selfcheck')}`.",
        )

    # ── 本机 runtime ──
    if conflicts:
        from horosa_skill.runtime.identity import is_horosa_app

        def holder_of(c: dict[str, Any]) -> str:
            # 措辞按身份握手**实际证明了什么**来：星阙 app 标记 = 另一份星阙（常见即用户自己开着的桌面端），
            # 别的 app 标记 = 一个自报身份的服务；只有两样都没有、也点不出进程时才说「查不出身份」。
            listed = ", ".join(f"pid {h.get('pid')} {(h.get('command') or '')[:60]}" for h in c.get("holders") or [])
            app = c.get("app")
            if is_horosa_app(app):
                return (f"另一份星阙实例（{app}" + (f"；{listed}" if listed else "")
                        + "——很可能是你开着的星阙桌面端，或另一个 runtime 根下的服务）")
            if app:
                return f"一个自报为 {app} 的服务" + (f"（{listed}）" if listed else "")
            if c.get("verdict") == "silent_listener":
                return (listed or "一个查不出身份的进程") + "（不应答 HTTP）"
            return listed or "一个查不出身份的进程"

        named = "；".join(f"{c.get('label')} 端口 {c.get('port')} 被 {holder_of(c)} 占着" for c in conflicts)
        named_en = "; ".join(f"{c.get('label')} port {c.get('port')} is held by "
                             + (", ".join(f"pid {h.get('pid')}" for h in c.get("holders") or []) or "an unidentified process")
                             for c in conflicts)
        horosa_held = any(is_horosa_app(c.get("app")) for c in conflicts)
        return result(
            "needs_attention",
            f"端口被非本工具的进程占用：{named}。本工具不会去终止它们。",
            f"Ports are held by processes this tool did not start: {named_en}. This tool will not stop them.",
            ("占着端口的是星阙自己（多半是桌面端）：不想关它，就设 HOROSA_PORTS=auto 让本工具换到空闲端口；"
             "想直接用它的引擎，就设 HOROSA_SERVER_ROOT / HOROSA_CHART_SERVER_ROOT 指向它（外部模式）。也可以关掉它再重试。")
            if horosa_held else
            ("关掉上面点名的进程，或换端口：设 HOROSA_PORTS=auto 自动挑空闲端口，或显式设 HOROSA_LOCAL_BACKEND_PORT / "
             "HOROSA_LOCAL_CHART_PORT；若那正是你想用的服务，设 HOROSA_SERVER_ROOT / HOROSA_CHART_SERVER_ROOT 指向它。"),
            ("It is Horosa itself (most likely the desktop app): set HOROSA_PORTS=auto to move to free ports, or point "
             "HOROSA_SERVER_ROOT / HOROSA_CHART_SERVER_ROOT at it to use its engine, or close it and retry.")
            if horosa_held else
            ("Stop the processes named above, or move ports: HOROSA_PORTS=auto picks free ones, or set "
             "HOROSA_LOCAL_BACKEND_PORT / HOROSA_LOCAL_CHART_PORT; if that is the service you want, point "
             "HOROSA_SERVER_ROOT / HOROSA_CHART_SERVER_ROOT at it."),
        )
    if report.get("registry_status") == "starting":
        status = cli_command("runtime status")
        return {**result(
            "needs_attention",
            "runtime 正在启动（首次运行含解压与 CDS 训练，可能几分钟）。",
            "The runtime is starting (the first start unpacks and trains CDS; it can take minutes).",
            f"等一会儿再跑 `{status}`；启动器日志路径见 launcher_log。",
            f"Wait, then run `{status}`; the launcher log path is in launcher_log.",
        ), "status": "starting"}
    if not issues:
        steps_zh, steps_en = _next_steps_when_ready()
        zh = "就绪：离线 runtime 已装好，本机 Horosa 服务在应答。"
        en = "Ready. The offline runtime is installed and the local Horosa endpoints are responding."
        if report.get("emulated") is True:
            # v0.38.0 A4: Windows on ARM runs the win32-x64 payload under emulation — worth saying once.
            zh += f"本机是 {report.get('host_platform')}，跑的是 {report.get('payload_platform')} 载荷（仿真，能用，冷启动更慢）。"
            en += (f" This host is {report.get('host_platform')} and runs the {report.get('payload_platform')} payload"
                   " under emulation (works; cold start is slower).")
        return result("ready", zh, en, steps_zh, steps_en)
    if issues == ["services:not_running"]:
        start = cli_command("runtime start")
        return result(
            "needs_attention",
            "runtime 文件都在，本机服务还没启动（客户端第一次调用也会自动拉起）。",
            "The runtime files are installed, but the local Horosa services are not running yet (the first client call "
            "also starts them).",
            f"运行 `{start}`（冷启动 10–45 秒）。",
            f"Run `{start}` (a cold start takes 10–45 s).",
        )
    if issues == ["services:java_backend_not_running"]:
        return result(
            "needs_attention",
            "降级（只有 chart）：Python 图表服务在跑，Java 后端没起来。chart 侧技法（三式 ken / 神数 / 地占 / 塔罗 / 西占 chart 族）"
            "照常可用；Java 侧（农历 / 八字 / 紫微 / 六壬与占时起课）会报错，直到它恢复。",
            "Degraded (chart-only): the Python chart service is up, but the Java backend is not. Chart-side techniques "
            "(三式 ken / 神数 / 地占 / tarot / western chart family) still work; Java-side ones (nongli / bazi / ziwei / "
            "liureng and time-cast techniques) will error until it recovers.",
            "看下面 java_diagnostics 里捕获的 Java 启动错误。Windows 已知诱因：代理 / VPN / 安全软件（WFP 过滤）拦 JDK 17 的回环"
            "（issue #14）；关掉干扰软件并重启后再试，或先只用 chart 侧技法。",
            "See java_diagnostics below for the captured Java boot error. Known cause on Windows: proxy / VPN / security "
            "software (WFP filters) blocking JDK 17 loopback (issue #14). Retry after disabling it and rebooting, or keep "
            "using chart-side techniques.",
        )
    doctor_cmd = cli_command("doctor --explain")
    return result(
        "needs_attention",
        f"本机 runtime 还有问题要处理：{', '.join(issues[:6])}。",
        f"The local runtime has issues to fix: {', '.join(issues[:6])}.",
        f"按下面 advice 里每个码的说明处理，然后重跑 `{doctor_cmd}`。",
        f"Follow the advice entry for each code below, then rerun `{doctor_cmd}`.",
    )


def _platform_supported(report: dict[str, Any]) -> bool:
    """本机平台有没有离线载荷。已装 runtime 就是最好的证据。"""
    if report.get("installed") is True:
        return True
    from horosa_skill.runtime.manager import (
        PLATFORM_FALLBACKS,
        SUPPORTED_PAYLOAD_PLATFORMS,
        host_platform_key,
    )

    host = host_platform_key()
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
    """端口占用探测：区分空闲 / 被占，被占时点名监听进程（与 start 起启动器前用的是同一个 `ports.port_taken`，E-07）。
    被占的是不是本产品由 doctor 的身份判定（endpoints / port_conflicts）回答。"""
    from horosa_skill.runtime.ports import port_taken

    taken = port_taken(port)
    return {"port": port, "occupied": taken is not None, **({"accepting": taken["accepting"], "holders": taken["holders"]} if taken else {})}


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

        _store = _MemoryStore(settings)
        report["memory_db"] = {"path": str(settings.db_path), **_store.integrity_check(), "usage": _store.storage_usage()}
        # 存档健康（v0.50.0-dev）：隔离出来的坏库、没进库的 run 文件、崩溃残留、上次重建没做完——清点整棵 runs/，只报不改。
        from horosa_skill.memory.rebuild import store_health as _store_health

        report["memory_db"]["health"] = _store_health(_store, full=True)
        report["warnings"] = [
            *(report.get("warnings") or []),
            *({"code": "memory:needs_attention", "detail": line, "fix": "horosa-skill memory rebuild"}
              for line in report["memory_db"]["health"].get("warnings") or []),
        ]
    except Exception as exc:  # noqa: BLE001 - 体检项自身失败也要如实入报告
        report["memory_db"] = {"path": str(settings.db_path), "ok": False, "detail": [f"{exc}"]}
    # 可选向量检索：依赖看的是**跑 doctor 的这个环境**，客户端的 server 可能在另一个环境里（setup 的探针查的才是那边）。
    from horosa_skill.knowledge import vectors as _vectors

    report["knowledge_vectors"] = {**_vectors.status(settings), "scope": "this process; the client's server may run in another environment"}
    # env 旗标审计（批 II-1）：未知 HOROSA_* 的 warn-and-ignore 结果 + 已设旗标的生命周期档 + 取值被拒的（E-10）。
    report["env_flags"] = _env_flag_audit()
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
                report["endpoints"] = manager.endpoint_identities()
        except Exception as exc:  # noqa: BLE001 - 体检不能因为归属判定失败就整份报废，但失败本身要如实入报告（v0.41.1）
            report["endpoints_error"] = f"{type(exc).__name__}: {exc}"
        if report.get("mode") == "managed" and report.get("endpoints"):
            with _budget.timed("port_takers"):
                report["port_takers"] = manager._ports_taken_by_others(report["endpoints"])
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
    # E-02 / E-11：JS 引擎在不在、用的是哪个 node、为什么不能用、怎么修。只读（一次 `node --version`，有缓存）。
    with _budget.timed("js_engine"):
        try:
            from horosa_skill.engine.js_client import HorosaJsEngineClient

            report["js_engine"] = HorosaJsEngineClient(settings).diagnose()
        except Exception as exc:  # noqa: BLE001 - 体检项自身失败也要如实入报告
            report["js_engine"] = {"state": "unknown", "ok": None, "error": f"{type(exc).__name__}: {exc}"}
    report["warnings"] = [
        *(report.get("warnings") or []),
        *_js_engine_warnings(report["js_engine"]),
        *_listener_scope_warnings(report["listener_scope"]),
        *_arch_warnings(report),
        *_internal_port_env_warnings(settings),
        *_payload_outdated_warnings(report),
        *_env_rejection_warnings(report["env_flags"]["rejected"]),
        *_toolsets_doctor_warnings(),  # MCP-07（surface 批）
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
    _contextualize_commands(report)
    return report


def _js_engine_warnings(js: dict[str, Any]) -> list[dict[str, str]]:
    if not isinstance(js, dict) or js.get("ok") is not False:
        return []
    return [{"code": "js_engine:unavailable", "detail": f"{js.get('state')}: {js.get('affects')}", "fix": str(js.get("fix") or "")}]


def _contextualize_commands(report: dict[str, Any]) -> None:
    """报告里所有给人照抄的命令，按本机的安装方式改写（E-06：此前一律 `uv run horosa-skill …`）。"""
    from horosa_skill.runtime.hints import contextualize

    for key in ("next_action", "user_summary"):
        if isinstance(report.get(key), str):
            report[key] = contextualize(report[key])
    for item in [*(report.get("warnings") or []), *(report.get("advice") or [])]:
        if isinstance(item, dict):
            for key in ("fix", "next_action", "user_summary"):
                if isinstance(item.get(key), str):
                    item[key] = contextualize(item[key])
_SETUP_NETWORK_TIMEOUT_SECONDS = 5.0


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
