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
