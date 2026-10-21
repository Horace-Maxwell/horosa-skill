"""工具输入契约（input_contract）与 MCP 工具 docstring 的生成；推运族逐工具输入契约与已验证示例载荷。"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from horosa_skill.agent_guidance.base import (
    CONFIRMATION_FIELDS,
    INPUT_CONTRACT_SCHEMA,
    PREFLIGHT_EXEMPT_TOOLS,
)
from horosa_skill.agent_guidance.tool_table import _EXTRA_OPTIONS_DOC, TOOL_GUIDANCE
from horosa_skill.engine.registry import TOOL_DEFINITIONS, resolve_tool_name
from horosa_skill.shenshu_options import options_doc
from horosa_skill.western_options_doc import western_options_doc

COMMON_ASTRO_PAYLOAD_EXAMPLE: dict[str, Any] = {
    "date": "1995-06-03",
    "time": "05:30",
    "zone": "+08:00",
    "lat": "31n13",
    "lon": "121e28",
    "hsys": 0,
    "zodiacal": 0,
    "agent_confirmed_settings": True,
    "clarification_notes": "User confirmed birth time, birthplace, timezone, Whole Sign houses, and tropical zodiac.",
}

PREDICTIVE_INPUT_CONTRACTS: dict[str, dict[str, Any]] = {
    "solarreturn": {
        "human_name": "太阳返照",
        "required_fields": ["date", "time", "zone", "lat", "lon", "datetime", "dirZone", "dirLat", "dirLon"],
        "must_ask": ["本命出生时间地点", "返照目标年份/日期", "返照地点与时区"],
        "target_fields": {
            "datetime": "返照目标时间，YYYY-MM-DD HH:mm:ss；缺省=今年生日时刻（当年+出生月日+出生时分，上游同律）。",
            "dirZone": "返照盘地点时区；缺省本命时区。",
            "dirLat/dirLon": "返照盘地点经纬度；缺省=出生地（上游同律）——异地返照先问用户现居地。",
        },
        "output_contract": ["本命盘配置", "起盘信息", "时段盘配置", "相位"],
        "example_payload": {
            **COMMON_ASTRO_PAYLOAD_EXAMPLE,
            "datetime": "2031-04-06 09:33:00",
            "dirZone": "+08:00",
            "dirLat": "31n13",
            "dirLon": "121e28",
        },
    },
    "lunarreturn": {
        "human_name": "月亮返照",
        "required_fields": ["date", "time", "zone", "lat", "lon", "datetime", "dirZone", "dirLat", "dirLon"],
        "must_ask": ["本命出生时间地点", "月返目标月份/日期", "月返地点与时区"],
        "target_fields": {
            "datetime": "月返目标时间，YYYY-MM-DD HH:mm:ss；缺省=今年生日时刻（上游同律）。",
            "dirZone": "月返盘地点时区；缺省本命时区。",
            "dirLat/dirLon": "月返盘地点经纬度；缺省=出生地（上游同律），异地月返先问用户。",
        },
        "output_contract": ["本命盘配置", "起盘信息", "时段盘配置", "相位"],
        "example_payload": {
            **COMMON_ASTRO_PAYLOAD_EXAMPLE,
            "datetime": "2031-04-06 09:33:00",
            "dirZone": "+08:00",
            "dirLat": "31n13",
            "dirLon": "121e28",
        },
    },
    "givenyear": {
        "human_name": "指定年推运 / 流年盘",
        "required_fields": ["date", "time", "zone", "lat", "lon", "datetime", "dirZone", "dirLat", "dirLon"],
        "must_ask": ["本命出生时间地点", "要看的年份/日期", "流年盘地点与时区"],
        "target_fields": {
            "datetime": "指定年中的目标时间，YYYY-MM-DD HH:mm:ss；缺省=今年生日时刻（上游同律）。",
            "dirZone": "流年盘地点时区；缺省本命时区。",
            "dirLat/dirLon": "流年盘地点经纬度；缺省=出生地（上游同律）。",
        },
        "output_contract": ["本命盘配置", "起盘信息", "时段盘配置", "相位"],
        "example_payload": {
            **COMMON_ASTRO_PAYLOAD_EXAMPLE,
            "datetime": "2031-04-06 09:33:00",
            "dirZone": "+08:00",
            "dirLat": "31n13",
            "dirLon": "121e28",
        },
    },
    "solararc": {
        "human_name": "太阳弧推运",
        "required_fields": ["date", "time", "zone", "lat", "lon", "datetime", "dirZone"],
        "must_ask": ["本命出生时间地点", "推运目标时间", "目标时区"],
        "target_fields": {
            "datetime": "太阳弧推运目标时间，YYYY-MM-DD HH:mm:ss；缺省=此刻（上游 +08:00 钟面）。",
            "dirZone": "推运盘目标时区；缺省本命时区。",
        },
        "output_contract": ["本命盘配置", "起盘信息", "时段盘配置", "相位"],
        "example_payload": {
            **COMMON_ASTRO_PAYLOAD_EXAMPLE,
            "datetime": "2031-04-06 09:33:00",
            "dirZone": "+08:00",
        },
    },
    "profection": {
        "human_name": "小限 / 年运推限",
        "required_fields": ["date", "time", "zone", "lat", "lon", "datetime", "dirZone"],
        "must_ask": ["本命出生时间地点", "小限目标年份/时间", "目标时区"],
        "target_fields": {
            "datetime": "小限目标时间，YYYY-MM-DD HH:mm:ss；缺省=此刻（上游 +08:00 钟面）。",
            "dirZone": "目标时区；缺省本命时区。",
            "profGrain/profStart": "[小限摘要]粒度 y/m/d（缺省 y）与起点 asc/sect/fortune/moon/mc（缺省 asc）。",
        },
        "output_contract": ["本命盘配置", "起盘信息", "小限摘要", "时段盘配置", "相位"],
        "example_payload": {
            **COMMON_ASTRO_PAYLOAD_EXAMPLE,
            "datetime": "2031-04-06 09:33:00",
            "dirZone": "+08:00",
        },
    },
    "pd": {
        "human_name": "本初方向 / 主限表",
        "required_fields": ["date", "time", "zone", "lat", "lon", "pdtype", "pdMethod", "pdTimeKey", "pdaspects"],
        "must_ask": ["本命出生时间地点", "主限方法", "时间钥匙", "相位列表"],
        "target_fields": {
            "pdtype": "坐标系：0=In Zodiaco（黄道，默认；宿命点 Vertex 应星行仅此坐标系核出），1=In Mundo（世俗/赤经空间）。",
            "pdMethod": "方位法（上游 13 法）：core_alchabitius（默认）/ horosa_legacy / placidus / regiomontanus / campanus / topocentric / meridian / porphyry / equal_ecliptic / equal_hour_circle / morinus / in_zodiaco_lon / in_zodiaco_abs。",
            "pdTimeKey": "度数换算（上游 26 项）：Ptolemy（默认）/ Naibod / TrueSolarArc / SymbolicSolarArc / Cardano / Umar / Wollner / Plantiko / Simmonite / SynodicYear / Kepler / Brahe / Kundig / SymbolicDegree / SymbolicYear / SymbolicMoon / SymbolicMonth / Quarterly / Quinary / Duodenary / Novenary / SelfMeasure / NaibodRA / AscendantArc / VanDam / User（配 pdTimeKeyCustom）。",
            "pdaspects": "纳入表格的相位角度，例如 [0, 60, 90, 120, 180]。",
            "pdDirect": "顺向开关（1 开/0 关，默认开）。",
            "pdConverse": "逆向开关（1 开/0 关，默认开；与顺向按年龄交错）。",
            "pdAntiscia": "映点/反映点作迫星（1 开/0 关，默认关）。",
            "pdTerms": "界(terms)边界作迫星（1 开/0 关，默认关）。",
            "pdYears": "推算年限上限（默认 100，上限 3000；>360 年出多圈复发行：同迫星/应星弧 +360°×n）。",
        },
        "output_contract": ["主限设置", "主限表格"],
        "example_payload": {
            **COMMON_ASTRO_PAYLOAD_EXAMPLE,
            "pdtype": 0,
            "pdMethod": "core_alchabitius",
            "pdTimeKey": "Ptolemy",
            "pdaspects": [0, 60, 90, 120, 180],
        },
    },
    "pdchart": {
        "human_name": "主限法盘",
        "required_fields": ["date", "time", "zone", "lat", "lon", "datetime", "dirZone", "pdtype", "pdMethod", "pdTimeKey"],
        "must_ask": ["本命出生时间地点", "主限盘目标时间", "主限方法", "时间钥匙"],
        "target_fields": {
            "datetime": "主限法盘目标时间，YYYY-MM-DD HH:mm:ss；缺省=主限表首条应期日期（UTC 墙钟、dirZone=+00:00），无则出生次日（上游同律）。",
            "dirZone": "目标时区（给了 datetime 时生效；缺省本命时区）。",
            "pdtype/pdMethod/pdTimeKey": "主限法盘算法设置（pdMethod/pdTimeKey 词表同 pd 工具：13 方位法、26 度数换算）。逆向用 direction='converse'。",
        },
        "output_contract": ["本命盘星与虚点", "主限法盘星体表格", "主限法盘相位"],
        "example_payload": {
            **COMMON_ASTRO_PAYLOAD_EXAMPLE,
            "datetime": "2031-04-06 09:33:00",
            "dirZone": "+08:00",
            "pdtype": 0,
            "pdMethod": "core_alchabitius",
            "pdTimeKey": "Ptolemy",
            "showPdBounds": 1,
        },
    },
    "zr": {
        "human_name": "黄道释放",
        "required_fields": ["date", "time", "zone", "lat", "lon"],
        "must_ask": ["本命出生时间地点", "是否指定释放起点/层级"],
        "target_fields": {
            "basePoint": "推运基点：Pars Fortuna 福点（缺省）/ Pars Spirit 等六希腊点 / Asc/Desc/MC/IC / 十二星座；取该点所在座起释。",
            "aiMode": "输出层级：l1_all（缺省）/ l2_in_l1 / l3_in_l2 / l4_in_l3，配 aiL1Idx/aiL2Idx/aiL3Idx（0 起）逐层钻取。",
            "startSign": "可选；直接指定起释星座（与 basePoint=星座同义）。",
        },
        "output_contract": ["起盘信息", "星盘信息", "基于X点推运", "当前时点", "方法说明"],
        "example_payload": {**COMMON_ASTRO_PAYLOAD_EXAMPLE},
    },
    "firdaria": {
        "human_name": "法达星限",
        "required_fields": ["date", "time", "zone", "lat", "lon"],
        "must_ask": ["本命出生时间地点", "是否沿用日夜与星阙默认排序"],
        "target_fields": {
            "date/time/zone/lat/lon": "本命信息；法达星限以本命盘日夜和星体顺序展开时间轴。",
        },
        "output_contract": ["法达星限时间轴"],
        "example_payload": {**COMMON_ASTRO_PAYLOAD_EXAMPLE},
    },
}


def _with_common_fields(tool_name: str, policy: dict[str, Any]) -> dict[str, Any]:
    definition = TOOL_DEFINITIONS.get(tool_name)
    result = deepcopy(policy)
    if definition is not None:
        fields = definition.input_model.model_fields
        result["tool_name"] = tool_name
        result["mcp_name"] = definition.mcp_name
        result["technical_required_fields"] = [name for name, field in fields.items() if field.is_required()]
        result["accepted_fields"] = sorted(fields)
        result["description"] = definition.description
        result["input_contract"] = build_tool_input_contract(tool_name)
    # options_keys 恒为 {键: 说明}：神数逐技法键表（sync311 F6；认不出的键回执 data.params_ignored）、非神数 options 索引、
    # 西占隐藏旋钮与引擎长词表（western_options_doc）、三式口径（策略里预置为 {"options": 文本}）——多源按键合并。
    doc_sources = (options_doc(tool_name), _EXTRA_OPTIONS_DOC.get(tool_name), western_options_doc(tool_name))
    for doc in doc_sources:
        if doc:
            result["options_keys"] = {**(result.get("options_keys") or {}), **doc}
    result["hard_gate"] = {
        "enabled": tool_name not in PREFLIGHT_EXEMPT_TOOLS,
        "pass_condition": "Provide `agent_confirmed_settings: true` after asking the user, or `defaults_accepted: true` when the user explicitly accepts Xingque/default settings.",
        "confirmation_fields": CONFIRMATION_FIELDS,
        "failure_code": "agent_guidance.required",
    }
    result["agent_should"] = [
        "ask_missing_result_changing_options_before_call",
        "use_safe_defaults_only_with_disclosure_or_user_acceptance",
        "store final answer with memory tools when user asks for follow-up continuity",
    ]
    return result


def _model_field_contract(tool_name: str) -> dict[str, Any]:
    definition = TOOL_DEFINITIONS[tool_name]
    fields = definition.input_model.model_fields
    return {
        "technical_required_fields": [name for name, field in fields.items() if field.is_required()],
        "accepted_fields": sorted(fields),
    }


# 逐工具示例载荷。手写的只覆盖预测族那 9 个；其余 101 个技法 agent 只能拿字段表自己拼，拼错一次就是一轮
# 「invalid_payload → 问用户」。testing_payloads 的样例每个都经 live 实例跑通（section_harness / 全面自检），
# 这里把它们作为示例下发：去掉可由 lat/lon 推导的 gpsLat/gpsLon、把自测说明换成「用户已确认」的写法。
EXAMPLE_NOTE = (
    "Shape example from a live-verified run: replace every value with the user's own confirmed data. "
    "agent_confirmed_settings is valid only after the user answered (defaults_accepted only after they accepted defaults). "
    "示例取自 live 跑通的载荷：值全部换成用户确认过的数据；agent_confirmed_settings 只能在用户真回答后才带。"
)
_EXAMPLE_DERIVED_KEYS = frozenset({"gpsLat", "gpsLon"})
_EXAMPLE_NOTES_TEXT = "User confirmed the birth/event data and the settings shown in this payload."
_VERIFIED_EXAMPLES: dict[str, dict[str, Any]] | None = None


def _clean_example(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned = {key: _clean_example(item) for key, item in value.items() if key not in _EXAMPLE_DERIVED_KEYS}
        if "clarification_notes" in cleaned:
            cleaned["clarification_notes"] = _EXAMPLE_NOTES_TEXT
        return cleaned
    if isinstance(value, list):
        return [_clean_example(item) for item in value]
    return value


def verified_example_payload(tool_name: str) -> dict[str, Any] | None:
    """live 跑通过的示例载荷（深拷贝）；需要确认的技法一律带上确认字段，复制即可过闸。

    返回 None = 没有样例；`{}` 是合法示例（如 ziwei_rules 不需要任何入参）。
    """
    global _VERIFIED_EXAMPLES
    if _VERIFIED_EXAMPLES is None:
        from horosa_skill.testing_payloads import build_sample_payloads

        _VERIFIED_EXAMPLES = {name: _clean_example(payload) for name, payload in build_sample_payloads().items()}
    if tool_name not in _VERIFIED_EXAMPLES:
        return None
    example = deepcopy(_VERIFIED_EXAMPLES[tool_name])
    if tool_name not in PREFLIGHT_EXEMPT_TOOLS and not (
        example.get("agent_confirmed_settings") is True or example.get("defaults_accepted") is True
    ):
        example["agent_confirmed_settings"] = True
        example["clarification_notes"] = _EXAMPLE_NOTES_TEXT
    return example


def build_tool_input_contract(tool_name: str) -> dict[str, Any]:
    """Return the user-facing input contract exposed through CLI, MCP, and docs."""

    tool_name = resolve_tool_name(tool_name) or tool_name
    if tool_name not in TOOL_DEFINITIONS:
        return {
            "schema": INPUT_CONTRACT_SCHEMA,
            "ok": False,
            "error": {"code": "input_contract.unknown_tool", "message": f"Unknown tool: {tool_name}"},
        }

    definition = TOOL_DEFINITIONS[tool_name]
    policy = TOOL_GUIDANCE.get(tool_name)
    contract: dict[str, Any] = {
        "schema": INPUT_CONTRACT_SCHEMA,
        "ok": True,
        "tool_name": tool_name,
        "mcp_name": definition.mcp_name,
        "description": definition.description,
        "confirmation_required": tool_name not in PREFLIGHT_EXEMPT_TOOLS,
        "confirmation_fields": CONFIRMATION_FIELDS if tool_name not in PREFLIGHT_EXEMPT_TOOLS else [],
        "technical": _model_field_contract(tool_name),
        "user_context_required": deepcopy(policy.get("must_have_context", [])) if policy else [],
        "ask_if_missing": deepcopy(policy.get("ask_if_missing", [])) if policy else [],
        "safe_defaults": deepcopy(policy.get("safe_defaults", [])) if policy else [],
        "do_not_assume": deepcopy(policy.get("do_not_assume", [])) if policy else [],
        "output_contract": deepcopy(policy.get("output_contract", [])) if policy else [],
        "example_payload": {},
    }
    if tool_name in PREDICTIVE_INPUT_CONTRACTS:
        predictive = deepcopy(PREDICTIVE_INPUT_CONTRACTS[tool_name])
        contract["predictive_contract"] = predictive
        contract["required_for_real_call"] = predictive["required_fields"]
        contract["target_fields"] = predictive["target_fields"]
        contract["output_contract"] = predictive["output_contract"]
        contract["example_payload"] = predictive["example_payload"]
    elif policy:
        contract["required_for_real_call"] = contract["technical"]["technical_required_fields"]
    if not contract["example_payload"]:
        verified = verified_example_payload(tool_name)
        if verified is not None:
            contract["example_payload"] = verified
            contract["example_source"] = "live_verified_sample"
    if contract["example_payload"] or contract.get("example_source"):
        contract["example_note"] = EXAMPLE_NOTE
    return contract


def build_tool_docstring(tool_name: str) -> str:
    """Build a concise MCP-visible docstring with the same input contract as the CLI."""

    definition = TOOL_DEFINITIONS[tool_name]
    contract = build_tool_input_contract(tool_name)
    lines = [definition.description]
    if contract.get("confirmation_required"):
        lines.append(
            "澄清闸：先向用户确认会改变结果的设置，再传 `agent_confirmed_settings=true` 或 "
            "`defaults_accepted=true` 并附 `clarification_notes`。 / Agent gate: confirm result-changing "
            "settings with the user first, then pass `agent_confirmed_settings=true` or "
            "`defaults_accepted=true` with `clarification_notes`."
        )
    required = contract.get("required_for_real_call") or contract.get("technical", {}).get("technical_required_fields", [])
    if required:
        lines.append("真实调用必填 / Required input: " + ", ".join(str(item) for item in required) + ".")
    target_fields = contract.get("target_fields")
    if isinstance(target_fields, dict) and target_fields:
        field_notes = "; ".join(f"{key}: {value}" for key, value in list(target_fields.items())[:5])
        lines.append("时点 / 目标字段 · Timing/target fields: " + field_notes)
    output_contract = contract.get("output_contract") or []
    if output_contract:
        # 多数策略给段名列表；择日族等给一整句说明——整句直接用，不能按字符拆开再逗号拼。
        sections = output_contract if isinstance(output_contract, str) else ", ".join(str(item) for item in output_contract)
        lines.append("预期输出段 / Expected output sections: " + sections + ".")
    return "\n".join(lines)
