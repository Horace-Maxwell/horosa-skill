"""共用常量与澄清闸的单一真值源（data/sensitive_settings.json）；HOROSA_CLARIFY 逃生舱。"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

GUIDANCE_SCHEMA = "horosa.skill.agent_guidance.v1"

# ── 澄清闸单一真值源（v0.33.0 批 II-2：策略即数据）────────────────────────────────
# 豁免表/过闸字段/失败码/逃生舱档位全部声明在 data/sensitive_settings.json（自带 self_tests，
# pytest 与 benchmark 直接跑）；本模块只留判定逻辑。改闸策略改表，不改代码。
_SENSITIVE_SETTINGS_PATH = Path(__file__).parents[1] / "data" / "sensitive_settings.json"  # agent_guidance/ 的上一层 = 包根
SENSITIVE_SETTINGS: dict[str, Any] = json.loads(_SENSITIVE_SETTINGS_PATH.read_text(encoding="utf-8"))

GLOBAL_AGENT_RULES: list[str] = [
    "If the client does not expose native horosa_* MCP tools, stop and ask the user/admin to run OpenClaw setup/check; do not fall back to shell or hand-written calculations.",
    "Do not hand-calculate Horosa methods with shell, Python, JavaScript, web snippets, or memorized formulas.",
    "Before calling a calculation tool, check whether the user supplied the fields and method settings that change the result.",
    "If a required or result-changing setting is missing, ask a short clarification question with concrete options instead of silently inventing a value.",
    "Use Horosa/Xingque defaults only when the user accepts defaults, asks for a quick/default reading, or the setting is explicitly documented as safe to default.",
    "For current-time questions, using the current local date/time/timezone is allowed, but location and technique-specific settings still need clarification when they matter.",
    "Timezone may be a fixed offset like +08:00 or an IANA name like America/Los_Angeles; Horosa normalizes IANA names by the chart date/time before calling the runtime.",
    "After a tool call, treat export_snapshot.export_text, export_snapshot.sections, and summary as the source of truth.",
]

COMMON_LOCATION_FIELDS = ["date", "time", "zone/timezone", "lat/lon or gpsLat/gpsLon/location"]
COMMON_BIRTH_FIELDS = ["birth date", "birth time", "birth timezone", "birth place / longitude / latitude"]
# 日界缺省（F2）：上游出厂缺省 1=「23 点算第二天」（utils/dayBoundary.js:39-45 defaultAfter23NewDay、models/astro.js:395-398）。
# v0.40 前这里写「False=星阙默认」且 schema 硬塞 False 下发 → bazi/ziwei/liureng/nongli 静默按 24 点换日。
_AFTER23_DEFAULT_MEANING = "星阙默认：23 点换日（缺省不传=引擎默认 1）；0=24 点换日"
CONFIRMATION_FIELDS: list[str] = list(SENSITIVE_SETTINGS["confirmation_fields"])
PREFLIGHT_EXEMPT_TOOLS: set[str] = set(SENSITIVE_SETTINGS["exempt_tools"])
GATE_FAILURE_CODE: str = str(SENSITIVE_SETTINGS["failure_code"])
INPUT_CONTRACT_SCHEMA = "horosa.skill.input_contract.v1"


def _clarify_override(tool_name: str) -> str | None:
    """HOROSA_CLARIFY 逃生舱：never=闸全关；granular:{"exempt":[…]}=按工具豁免；其余/缺省=always。
    返回 None（不干预）或放行模式名（写进闸结果的 mode，审计可见）。解析失败按 always（安全侧）。"""
    raw = os.environ.get("HOROSA_CLARIFY", "").strip()
    if not raw or raw.lower() == "always":
        return None
    if raw.lower() == "never":
        return "env_never"
    if raw.lower().startswith("granular:"):
        try:
            spec = json.loads(raw[len("granular:"):])
            if isinstance(spec, dict) and tool_name in set(spec.get("exempt") or []):
                return "env_granular_exempt"
        except (ValueError, TypeError):
            return None
    return None
