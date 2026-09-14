from __future__ import annotations


class HorosaSkillError(Exception):
    def __init__(self, message: str, *, code: str = "horosa_skill_error", details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


class ToolTransportError(HorosaSkillError):
    pass


class ToolValidationError(HorosaSkillError):
    pass


class DispatchResolutionError(HorosaSkillError):
    pass


class RuntimeError(HorosaSkillError):
    pass


class RuntimeInstallError(RuntimeError):
    pass


class RuntimeValidationError(RuntimeError):
    pass


# ---------------------------------------------------------------------------------------------
# 错误可恢复（v0.36.0 B4）：每个 `code` 都能落到一条 agent 可执行的恢复说明（双语）。
# 三层：精确码表 → 前缀规则（runtime./transport./js_engine./client./…）→ 后缀规则（*_missing_*/*invalid*
# → 问用户或修入参；*_failed/*_unavailable/*timeout* → 重试再体检）。新码若三层都落不到，
# scripts/verify_error_recovery.py 即红——错误码是接口，不是日志。
# ---------------------------------------------------------------------------------------------
import re as _re
from typing import Any as _Any


def bilingual(zh: str, en: str) -> str:
    """中英并排的一句话（错误 message / prompt_to_user 用）：非中文用户也能读懂要做什么。"""
    zh, en = zh.strip(), en.strip()
    if not zh:
        return en
    if not en:
        return zh
    return f"{zh} / {en}"


DOCTOR_CMD = "uv run horosa-skill doctor"
INSTALL_CMD = "uv run horosa-skill install"

RECOVERY_KINDS: dict[str, dict[str, _Any]] = {
    "input": {
        "prompt_to_user": bilingual(
            "参数缺失或无效。请按 details.hint 补齐/修正后重试；入参口径可先看 horosa_agent_guidance(tool_name=…)。",
            "Missing or invalid input: fix it per details.hint and retry; horosa_agent_guidance(tool_name=…) documents the contract.",
        ),
        "next_action": "ask_user_or_fix_input",
    },
    "retry_or_doctor": {
        "prompt_to_user": bilingual(
            f"本地引擎/后端本次失败。可重试一次；仍失败请执行 `{DOCTOR_CMD}` 定位。",
            f"The local engine/backend failed this call. Retry once; if it persists run `{DOCTOR_CMD}`.",
        ),
        "next_action": "retry_then_doctor",
        "commands": [DOCTOR_CMD],
    },
    "runtime": {
        "prompt_to_user": bilingual(
            f"本地 Horosa 运行时不可用。请执行 `{DOCTOR_CMD}` 查看体检结果；未安装则先 `{INSTALL_CMD}`。",
            f"The local Horosa runtime is unavailable. Run `{DOCTOR_CMD}`; if it is not installed run `{INSTALL_CMD}` first.",
        ),
        "next_action": "install_or_doctor",
        "commands": [DOCTOR_CMD, INSTALL_CMD],
    },
    "transport": {
        "prompt_to_user": bilingual(
            f"本地后端暂时不可达（可能正在冷启动或已停止）。稍候数秒重试一次；仍失败请执行 `{DOCTOR_CMD}`。",
            f"The local backend is unreachable (cold start or stopped). Wait a few seconds and retry once; then run `{DOCTOR_CMD}`.",
        ),
        "retry": "backend cold start can take up to ~45s on first call; one retry is usually enough",
        "next_action": "retry_then_doctor",
        "commands": [DOCTOR_CMD],
    },
    "js_engine": {
        "prompt_to_user": bilingual(
            f"本地 JS 引擎不可用或执行失败。确认已安装离线 runtime（自带 node），或设 HOROSA_NODE_BIN 指向 node 后重试；`{DOCTOR_CMD}` 可定位。",
            f"The local JS engine is unavailable or failed. Install the offline runtime (bundled node) or point HOROSA_NODE_BIN at node, then retry; `{DOCTOR_CMD}` locates the cause.",
        ),
        "next_action": "install_or_set_node_then_retry",
        "commands": [DOCTOR_CMD],
    },
    "environment": {
        "prompt_to_user": bilingual(
            "客户端/本机环境问题（命令缺失、配置文件不合法或超时）。按 details.hint 修正环境后重试。",
            "Client/host environment problem (missing command, invalid config file, or timeout). Fix the environment per details.hint and retry.",
        ),
        "next_action": "fix_environment_then_retry",
    },
}

# 精确码表：语义明确、需要专门指路的码。
RECOVERY_TABLE: dict[str, dict[str, _Any]] = {
    "tool.backend_param_error": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "后端拒绝了本次参数。请核对 date=YYYY-MM-DD、time=HH:mm:ss、zone=+08:00、lat=31n13、lon=121e28 这类格式后重试；details.hint 里有具体建议。",
            "The backend rejected the parameters. Check formats like date=YYYY-MM-DD, time=HH:mm:ss, zone=+08:00, lat=31n13, lon=121e28 and retry; details.hint has specifics.",
        ),
        "next_action": "fix_input_format",
    },
    "tool.unknown": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "工具名不存在。用 horosa_tool_run 描述里的技法目录或 resource horosa://catalog/techniques 核对名字。",
            "Unknown tool name. Check the technique catalog in horosa_tool_run's description or resource horosa://catalog/techniques.",
        ),
        "next_action": "pick_tool_from_catalog",
    },
    "tool.invalid_payload": {"kind": "input", "next_action": "fix_input_per_validation_errors"},
    "dispatch.no_matching_tool": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "没有技法匹配这句话。从 details.candidates 里挑技法名直调对应工具，或换用更明确的技法说法。",
            "No technique matched the query. Pick a tool name from details.candidates and call it directly, or rephrase with the technique's name.",
        ),
        "next_action": "pick_candidate_tool",
    },
    "runtime.not_installed": {"kind": "runtime", "next_action": "install"},
    "runtime.java_backend_unavailable": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "Java 后端不可用，运行时处于 chart-only 降级：西占/推运/三式 ken/神数/地占/塔罗仍可用；农历/八字/紫微/六壬与占时起课在冷却期后自动重试。`uv run horosa-skill doctor` 看 Java 启动错误。",
            "The Java backend is down; the runtime is degraded to chart-only: Western/predictive/ken/shenshu/geomancy/tarot still work; nongli/bazi/ziwei/liureng and time-cast tools retry after the cooldown. Run `uv run horosa-skill doctor` for the Java boot error.",
        ),
        "next_action": "run_doctor_or_retry_after_cooldown",
        "commands": [DOCTOR_CMD],
    },
    "runtime.start_timeout": {"kind": "runtime", "next_action": "doctor_then_retry_or_raise_timeout"},
    "runtime.launcher_patch_anchor_missing": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "本机已装的 runtime 启动器与本版 horosa-skill 预期的结构对不上，「只杀自己人」的误杀"
            "保护补丁打不上去。请升级 horosa-skill（uv sync 或 uvx --refresh）后重试；"
            "确需临时跳过设 HOROSA_RUNTIME_LAUNCHER_PATCH=0（会失去该保护）。",
            "The installed runtime launcher does not match what this horosa-skill version expects, so the "
            "foreign-process kill guard could not be applied. Upgrade horosa-skill (uv sync / uvx --refresh) "
            "and retry; set HOROSA_RUNTIME_LAUNCHER_PATCH=0 to skip it deliberately (you lose the guard).",
        ),
        "next_action": "upgrade_horosa_skill_then_retry",
    },
    "runtime.port_conflict_foreign": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "Horosa 的本机服务端口被**其它进程**占用（可能是你自己开着的星阙桌面端，或另一个程序）。"
            "本工具不会去终止不属于自己的进程。请关掉占用者，或改用别的端口："
            "设 HOROSA_PORTS=auto 自动挑空闲端口，或显式设 HOROSA_LOCAL_BACKEND_PORT / "
            "HOROSA_LOCAL_CHART_PORT；若那正是你想用的服务，设 HOROSA_SERVER_ROOT / "
            "HOROSA_CHART_SERVER_ROOT 指向它。",
            "Horosa's local service ports are held by ANOTHER process (possibly your own Horosa desktop "
            "app, or an unrelated program). This tool never terminates processes it did not start. "
            "Close the holder, or move ports: set HOROSA_PORTS=auto, or set HOROSA_LOCAL_BACKEND_PORT / "
            "HOROSA_LOCAL_CHART_PORT explicitly. If that IS the server you want, point "
            "HOROSA_SERVER_ROOT / HOROSA_CHART_SERVER_ROOT at it.",
        ),
        "next_action": "free_the_port_or_change_ports",
    },
    "runtime.port_conflict_unknown_holder": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "端口上有服务在应答，但查不出它是不是 Horosa 的，因此没有采用它 —— 把陌生服务当后端"
            "的症状是「排盘失败但 HTTP 200」。确认那确实是 Horosa 后端后设 "
            "HOROSA_RUNTIME_TRUST_PORTS=1；否则换端口（HOROSA_PORTS=auto）。",
            "Something is answering on the port but could not be identified as Horosa, so it was not "
            "adopted — adopting a stranger shows up as 'chart failed but HTTP 200'. If you know it is a "
            "Horosa backend, set HOROSA_RUNTIME_TRUST_PORTS=1; otherwise move ports (HOROSA_PORTS=auto).",
        ),
        "next_action": "verify_holder_then_trust_or_change_ports",
    },
    "runtime.stop_refused_foreign": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "这些端口上的服务不是本工具启动的（可能是你自己开着的星阙桌面端），已拒绝停止 —— "
            "停脚本按端口和 pid 文件动手，停下去会关掉你正在用的程序。确认无误请用 "
            "`horosa-skill runtime stop --force`。",
            "Those services were not started by this tool (possibly your own Horosa desktop app), so the "
            "stop was refused — the stop script acts by port and pid file and would close a program you "
            "are using. Use `horosa-skill runtime stop --force` if you are sure.",
        ),
        "next_action": "confirm_then_force_stop",
    },
    "runtime.stop_refused_clients_attached": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "还有别的 Horosa 客户端挂在这份 runtime 上，停止会打断它们。确认要停请加 --force。",
            "Other Horosa clients are still attached to this runtime; stopping would cut them off. "
            "Pass --force if you are sure.",
        ),
        "next_action": "confirm_then_force_stop",
    },
    "runtime.external_unreachable": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "你已显式把后端地址指到别处（HOROSA_SERVER_ROOT / HOROSA_CHART_SERVER_ROOT），"
            "但那个地址不可达。外部模式下本工具**不会**在本机启动 runtime。请确认那台机器上的"
            "服务在跑且地址可达；要改用本机 runtime，请取消这两个环境变量。",
            "You pointed the backend elsewhere (HOROSA_SERVER_ROOT / HOROSA_CHART_SERVER_ROOT) but that "
            "address is unreachable. In external mode this tool will NOT start a local runtime. Make sure "
            "the remote services are up, or unset those variables to use the local runtime.",
        ),
        "next_action": "fix_external_address_or_unset",
    },
    "runtime.install_long_path": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "Windows 的 260 字符路径上限会让解包失败。开启长路径支持（注册表 LongPathsEnabled=1，"
            "需重启），或把 runtime 装到更短的路径：设 HOROSA_RUNTIME_ROOT=C:\\horosa 后重试。",
            "Windows' 260-character path limit would make extraction fail. Enable long paths "
            "(registry LongPathsEnabled=1, needs a reboot), or install to a shorter path: set "
            "HOROSA_RUNTIME_ROOT=C:\\horosa and retry.",
        ),
        "next_action": "enable_long_paths_or_shorten_runtime_root",
    },
    "runtime.start_blocked_quarantine": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "runtime 的可执行文件带 macOS 隔离属性，Gatekeeper 会在启动时直接终止它们（这只发生在手动下载"
            "归档后 `install --archive` 的安装方式）。请按错误里的 xattr 命令解除后重试。",
            "The runtime binaries carry the macOS quarantine attribute, so Gatekeeper kills them on launch "
            "(this happens only when the archive was downloaded by hand and installed with `install --archive`). "
            "Run the xattr command from the error, then retry.",
        ),
        "next_action": "clear_quarantine_then_retry",
    },
    "runtime.stop_timeout": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "停止脚本超时未返回。请看 details.survivors 里还活着的进程，用 `horosa-skill runtime status` 复核；"
            "确认是本工具起的服务后可 `runtime stop --force`。",
            "The stop script did not return in time. Check details.survivors, re-check with "
            "`horosa-skill runtime status`, and use `runtime stop --force` once you have confirmed the services are ours.",
        ),
        "next_action": "inspect_survivors_then_force_stop",
    },
    "runtime.launcher_patch_write_failed": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "写入启动器补丁失败（runtime 目录只读或属于别的用户）。请检查目录权限；确需临时跳过设 "
            "HOROSA_RUNTIME_LAUNCHER_PATCH=0（会失去误杀保护）。",
            "Writing the launcher patch failed (runtime directory read-only or owned by another user). Fix the "
            "permissions; set HOROSA_RUNTIME_LAUNCHER_PATCH=0 to skip deliberately (you lose the kill guard).",
        ),
        "next_action": "fix_permissions_then_retry",
    },
    "runtime.install_refused_running_foreign": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "端口上正在运行的服务不是本工具启动的（可能是你自己开着的星阙桌面端），升级/重装不会去停它。"
            "请先关掉它，或改用别的端口（HOROSA_PORTS=auto）后再装。",
            "The services running on the ports were not started by this tool (possibly your own Horosa desktop "
            "app); install/upgrade will not stop them. Close them first, or move ports (HOROSA_PORTS=auto).",
        ),
        "next_action": "close_foreign_service_or_change_ports",
    },
    "runtime.install_previous_locked": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "上一版 runtime 目录（previous/）里还有进程在用，无法清理。请看 details.holders，关掉后重试。",
            "The previous runtime directory (previous/) is still held by a process and cannot be removed. "
            "See details.holders, close them, and retry.",
        ),
        "next_action": "close_holders_then_retry",
    },
    "runtime.previous_cleanup_deferred": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "新 runtime 已装好并可用；旧目录 previous/ 暂时删不掉（Windows 常见：文件句柄未释放），"
            "重启后再跑 `horosa-skill doctor` 会提示清理。",
            "The new runtime is installed and usable; the old previous/ directory could not be removed yet "
            "(common on Windows while handles are open). `horosa-skill doctor` will suggest the cleanup later.",
        ),
        "next_action": "none_retry_cleanup_later",
    },
    "runtime.platform_unsupported": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "本机平台没有离线 runtime 载荷（只发 macOS Apple Silicon 与 Windows x64）。可走网关模式：在一台"
            "受支持的机器上跑 runtime，本机设 HOROSA_SERVER_ROOT 与 HOROSA_CHART_SERVER_ROOT 指过去。",
            "There is no offline runtime payload for this platform (only macOS Apple Silicon and Windows x64 ship). "
            "Use gateway mode: run the runtime on a supported machine and point HOROSA_SERVER_ROOT / "
            "HOROSA_CHART_SERVER_ROOT at it.",
        ),
        "next_action": "use_gateway_mode",
    },
    "config.unexpanded_template": {
        "kind": "environment",
        "prompt_to_user": bilingual(
            "某个路径设置里还留着未展开的 `${…}` 占位符（宿主没有替换它）。请在客户端的扩展设置里填上真实路径，"
            "或删掉该环境变量用默认路径。",
            "A path setting still contains an unexpanded `${…}` placeholder (the host did not substitute it). "
            "Fill in a real path in the client's extension settings, or unset the variable to use the default.",
        ),
        "next_action": "fix_placeholder_or_unset",
    },
    "runtime.starting": {
        "kind": "transport",
        "prompt_to_user": bilingual(
            "本机 runtime 正在启动（首次运行要解压并训练 CDS，可能几分钟）。等 retry_after_seconds "
            "秒后重试**同一个调用**即可，不用改参数。连续三次仍是 starting 请跑 "
            "`horosa-skill runtime status` 看启动器日志。",
            "The local runtime is still starting (first run unpacks and trains CDS; this can take minutes). "
            "Retry the SAME call after retry_after_seconds — no parameter changes needed. If it is still "
            "starting after three tries, run `horosa-skill runtime status` for the launcher log.",
        ),
        "next_action": "retry_same_call_after_delay",
    },
    "transport.connection_error": {"kind": "transport"},
    "report.run_not_found": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "run_id 不存在。先用 horosa_memory_query 找到要导出的运行记录，再用它的 run_id 渲染。",
            "run_id not found. Use horosa_memory_query to locate the run first, then render with its run_id.",
        ),
        "next_action": "query_memory_for_run_id",
    },
    "report.source_not_found": {"kind": "input", "next_action": "query_memory_for_run_id"},
    "report.from_tool.unsaved_result": {"kind": "input", "next_action": "rerun_with_save_result_true"},
    "report.technique.no_cards": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "这个 run/session 里没有技法依据卡（还没跑过技法工具，或结果未存档）。先调用技法工具（save_result=true）再导出技法报告。",
            "No technique cards in this run/session (no technique tool has run, or results were not saved). Run a technique tool with save_result=true, then export the technique report.",
        ),
        "next_action": "run_technique_tool_first",
    },
    "tool.invalid_payload": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "调用参数没解析成对象。把各个字段按工具的 inputSchema 直接传（不要整包塞进一个字符串），"
            "确需整包时 request 必须是合法 JSON 对象。",
            "The call arguments did not parse as an object. Pass fields directly per the tool's "
            "inputSchema; if you must send one blob, `request` has to be a valid JSON object.",
        ),
        "next_action": "resend_arguments_as_object",
    },
    "agent_guidance.required": {"kind": "input", "next_action": "ask_user_then_confirm"},
}

RECOVERY_PREFIX_KINDS: tuple[tuple[str, str], ...] = (
    ("runtime.", "runtime"),
    ("transport.", "transport"),
    ("js_engine.", "js_engine"),
    ("client.", "environment"),
    ("openclaw.", "environment"),
)
_INPUT_SUFFIX = _re.compile(r"(missing|required|empty|invalid|unknown|bad_|unsupported|insufficient|traversal|mismatch|unsaved)")
_RETRY_SUFFIX = _re.compile(r"(failed|unavailable|timeout|not_found|_error$|^error$)")


def classify_code(code: str) -> tuple[str | None, str | None]:
    """错误码 → (kind, 来源)；来源 ∈ exact / prefix / suffix；三层都落不到 → (None, None)。"""
    text = f"{code or ''}".strip()
    if not text:
        return None, None
    entry = RECOVERY_TABLE.get(text)
    if entry is not None:
        return str(entry.get("kind") or "input"), "exact"
    # 基础设施前缀优先于通用后缀：js_engine.node_unavailable 要的是「装 runtime/设 HOROSA_NODE_BIN」，
    # 不是泛泛的「重试再体检」；runtime.* 同理（安装/体检语义比后缀更具体）。
    for prefix, kind in RECOVERY_PREFIX_KINDS:
        if text.startswith(prefix):
            return kind, "prefix"
    last = text.rsplit(".", 1)[-1]
    if _INPUT_SUFFIX.search(last):
        return "input", "suffix"
    if _RETRY_SUFFIX.search(last):
        return "retry_or_doctor", "suffix"
    return None, None


def recovery_for(code: str, details: dict[str, _Any] | None) -> dict[str, _Any]:
    """给 details 补 agent_recovery（kind/prompt_to_user/next_action[/commands]）与 hint；已带者不覆盖。"""
    result = dict(details) if isinstance(details, dict) else {}
    kind, source = classify_code(code)
    if kind is None:
        return result
    base = dict(RECOVERY_KINDS.get(kind) or RECOVERY_KINDS["input"])
    exact = RECOVERY_TABLE.get(f"{code}".strip(), {})
    recovery = {**base, **{k: v for k, v in exact.items() if k != "kind"}, "kind": kind, "code": f"{code}".strip(), "source": source}
    if "agent_recovery" not in result:
        result["agent_recovery"] = recovery
    elif isinstance(result["agent_recovery"], dict):
        for key in ("kind", "next_action", "prompt_to_user"):
            result["agent_recovery"].setdefault(key, recovery[key])
    result.setdefault("hint", recovery["prompt_to_user"])
    result.setdefault("next_action", recovery["next_action"])
    return result
