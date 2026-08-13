from __future__ import annotations

import json
import os
import re
from inspect import Parameter, Signature
from typing import Any, Literal

from typing import Annotated

from mcp import types as mcp_types
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ValidationError, WithJsonSchema, create_model

from horosa_skill.agent_guidance import (
    build_agent_guidance,
    build_technique_catalog,
    build_tool_docstring,
    build_validation_recovery,
    validate_agent_preflight,
)
from horosa_skill import __version__
from horosa_skill.config import Settings
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.errors import ToolValidationError
from horosa_skill.schemas.common import ErrorInfo
from horosa_skill.exports.registry import build_export_registry
from horosa_skill.input_normalization import normalize_request_payload
from horosa_skill.schemas.common import DispatchEnvelope, ToolEnvelope
from horosa_skill.schemas.tools import (
    AgentGuidanceInput,
    DispatchInput,
    MemoryAnswerInput,
    MemoryQueryInput,
    MemoryShowInput,
    ReportFromToolInput,
    ReportRenderInput,
    ReportTemplateInput,
    TechniqueReportInput,
)
from horosa_skill.service import HorosaSkillService

# 太极图 SVG（data URI，离线友好）：server 级图标，客户端渲染刚起步、成本近零先埋。
_SERVER_ICON = mcp_types.Icon(
    src=(
        "data:image/svg+xml;utf8,"
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>"
        "<circle cx='32' cy='32' r='30' fill='%23111827'/>"
        "<path d='M32 2a30 30 0 000 60 15 15 0 010-30 15 15 0 000-30z' fill='%23f9fafb'/>"
        "<circle cx='32' cy='17' r='5' fill='%23111827'/>"
        "<circle cx='32' cy='47' r='5' fill='%23f9fafb'/></svg>"
    ),
    mimeType="image/svg+xml",
    sizes=["64x64"],
)

# Tool annotations（MCP 2025-11-25）：客户端用它决定确认摩擦/自动放行；目录审核要求标注准确。
# 判定口径（如实标注，见 AGENTS.md §4 / LESSONS）：
# - 全部工具 openWorldHint=False（local-first：只打本机 runtime，不出网）。
# - 查询类（registry/knowledge/guidance/memory 读、报告模板）readOnlyHint=True + idempotent=True。
# - 技法计算类 readOnlyHint=False（默认会写一条本地 run 记录，memory_query 可见）、
#   destructiveHint=False（只追加、不改不删）、idempotentHint=False（重复调用会追加新 run 行）。
# - 报告渲染 readOnly=False + idempotent=True（同 run_id+format 原子覆盖同一产物）；
#   report_from_tool 会重新起盘+新 run → idempotent=False。
_ANN_QUERY = mcp_types.ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
_ANN_CALC = mcp_types.ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False
)
_ANN_RENDER = mcp_types.ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False
)

_READONLY_TOOL_NAMES = {
    "export_registry",
    "export_parse",
    "knowledge_registry",
    "knowledge_read",
    "ziwei_rules",
    "gua_desc",
    "gua_meiyi",
    "astrodata",
}


def _tool_annotations(tool_name: str) -> mcp_types.ToolAnnotations:
    if tool_name in _READONLY_TOOL_NAMES:
        return _ANN_QUERY
    return _ANN_CALC


# 入口型工具：即使客户端把 MCP 工具全部 deferred（Claude Code 的工具搜索默认行为），这几个也常驻，
# 保证模型永远看得见「怎么问路」和「有哪些技法」。键名是 Claude Code 侧的 _meta 约定。
_ALWAYS_LOAD_TOOLS = {"horosa_agent_guidance", "horosa_dispatch", "horosa_tool_run"}
_ALWAYS_LOAD_META = {"anthropic/alwaysLoad": True}


def _tool_meta(mcp_name: str) -> dict[str, Any] | None:
    return dict(_ALWAYS_LOAD_META) if mcp_name in _ALWAYS_LOAD_TOOLS else None


def _structured_output_enabled() -> bool:
    """是否给工具声明 `outputSchema`（→ 客户端拿到 `structuredContent`）。**默认关**。

    规范鼓励它，但 Claude Code 有过 anthropics/claude-code#25081：服务器带 outputSchema 时**整个
    工具列表静默消失**——该 issue 至今 stale-closed、未确认修复。工具全体消失对本产品是灾难级故障，
    而收益只是「结构化副本」（正文 JSON 一直都在 content 里）。因此默认不开，`HOROSA_OUTPUT_SCHEMA=1`
    给已在自己客户端验证过 `/mcp` 工具计数不掉的用户使用。
    """
    return os.environ.get("HOROSA_OUTPUT_SCHEMA", "0").strip().lower() in {"1", "true", "on"}


def _return_type(annotation: Any) -> Any:
    return annotation if _structured_output_enabled() else Signature.empty


def _selected_toolsets() -> set[str] | None:
    """`HOROSA_TOOLSETS=astro,cn` → 只平铺这些 domain 的技法工具（门面工具永远注册）。

    动机：Claude Code 已用工具搜索解决了 92 工具的上下文膨胀，但 Cursor 一类客户端仍有较紧的工具数
    上限，全量平铺会被静默截断。分组白名单是注册期过滤，不触碰 service 层。
    `HOROSA_TOOLSETS=none` == 精简模式（等价 HOROSA_MCP_COMPACT=1 的技法面）。
    """
    raw = os.environ.get("HOROSA_TOOLSETS", "").strip()
    if not raw:
        return None
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


# Server instructions：客户端把它当「这台服务器是干什么的」说明书常驻上下文。自 Claude Code 起
# MCP 工具默认 deferred（工具搜索按需加载），instructions 就成了模型决定「要不要来搜我」的唯一依据
# ——它的作用更接近一份 skill 而非一句简介。上限约 2KB，超出截断，故关键信息前置。
_SERVER_INSTRUCTIONS = """Horosa (星阙) — local-first 术数/占星 computation. All engines run on this
machine (offline); nothing is sent to a remote service.

WHEN TO REACH FOR THIS SERVER
Any request to 起盘 / 排盘 / 起课 / 起卦 / 算命 / 看运势 / 合盘 / 择日 / 卜卦, or to explain, store, or
report on such a chart — in any language. Also 农历/节气/黄历 conversions and celebrity birth data.

WHAT IT COVERS (92 tools)
· Western astrology: natal + derived charts, 20+ predictive systems (returns, progressions, primary
  directions, zodiacal releasing, firdaria), horary 卜卦, election 择日, astrocartography, midpoints.
· Chinese metaphysics: 八字, 紫微斗数, 大六壬, 奇门遁甲, 太乙, 金口诀, 三式合一, 六爻, 河洛理数,
  邵子参评数, 一掌经, 小六壬, 飞宫小奇门, 小成图, 皇极轨策, 统摄法, 宿占, 灵棋经.
· 神数 family (14 engines) + 神数正传 (5 schools), 天文地占, tarot.

HOW TO USE IT
1. Unsure which tool? Call horosa_agent_guidance (or horosa_dispatch with the raw request).
2. A tool REFUSES (agent_guidance.required) when a result-changing setting is missing — time, place,
   timezone, gender, 流派/宫制/起局方式. Ask via details.agent_recovery.prompt_to_user, then retry with
   agent_confirmed_settings=true (or defaults_accepted=true). Never self-confirm.
3. Explain ONLY from the returned export_snapshot.export_text sections — never hand-calculate, and
   never read a missing section as a missing dependency.
4. Every result carries data.technique_card (technique, settings in force, which engine computed it)
   — quote it after your answer; horosa_technique_report renders it for a run or a whole session.
5. Calls are stored: horosa_memory_query finds past runs; horosa_report_render writes a DOCX/PDF
   consulting report from your ai_report.

Set HOROSA_MCP_COMPACT=1 to expose 10 facade tools instead of 92 (horosa_tool_run reaches every
technique by name); HOROSA_TOOLSETS=astro,cn limits which technique groups are exposed."""


_TITLE_TAIL_PAREN = re.compile(r"[（(][^（()）]*[)）]\s*$")


def _tool_title(tool_name: str) -> str | None:
    """人类可读的工具标题（客户端工具选择器显示它，而不是 `horosa_cn_xiaochengtu` 这种 raw id）。

    工具描述是「中文首句（补充）。English sentence.」的双语形态（registry.py），取中文首句、去掉
    结尾括注即得一个准确的技法名——中文技法名是本产品最大的可读性资产，不该丢在 raw id 后面。
    """
    definition = TOOL_DEFINITIONS.get(tool_name)
    if definition is None:
        return None
    head = str(definition.description or "").split("。", 1)[0].strip()
    if not head:
        return None
    head = _TITLE_TAIL_PAREN.sub("", head).strip()
    if not head or head.isascii():  # 纯英文描述 → 交回 FastMCP 默认（用 name）
        return None
    return head[:24]


def _normalize_mcp_request(raw_request: Any, model: type[BaseModel]) -> dict[str, Any]:
    payload = raw_request
    if isinstance(payload, BaseModel):
        payload = payload.model_dump(exclude_none=True)

    if payload is None:
        payload = {}

    if isinstance(payload, str):
        text = payload.strip()
        payload = {} if not text else json.loads(text)

    if not isinstance(payload, dict):
        raise ValueError("request must be an object or a JSON object string")

    payload = normalize_request_payload(payload)
    normalized = model.model_validate(payload)
    return normalized.model_dump(exclude_none=True)


# 输入归一化能吸收的字段：`input_normalization.normalize_request_payload` 会把这些键的数字/别名
# 形态转成引擎要的字符串（如 lat=39.9 → "39n54"）。但 FastMCP 在**进入函数体之前**就按 arg model
# 校验，纯 `"string"` 的广告类型会让 `{"lat": 39.9}`（模型极高频输出）在归一化之前就被拒，回一条裸
# pydantic 错误，绕过整套 agent_recovery 契约。故对这些键放宽广告类型。
_NUMERIC_TOLERANT_FIELDS = frozenset(
    {"lat", "lon", "dirLat", "dirLon", "gpsLat", "gpsLon", "zone", "dirZone", "gender", "date", "time", "datetime"}
)


def _inline_refs(node: Any, defs: dict[str, Any], seen: frozenset[str] = frozenset(), depth: int = 0) -> Any:
    """把 `#/$defs/X` 就地展开——单个 property 会被摘出来独立广告，`$ref` 在那里解析不到根。

    **不变量：返回值里绝不残留 `$ref`。** 模型之间存在自引用（如嵌套 BirthInput），一旦把带 `$ref`
    的片段塞进 `WithJsonSchema`，pydantic 生成 arg model 时会 `KeyError: '#/$defs/…'` 而整个服务器
    起不来。故遇环 / 超深 / 目标缺失时一律降级为「无约束对象」，宁可广告得宽松也不能构不出来。
    """
    if not isinstance(node, (dict, list)):
        return node
    if isinstance(node, list):
        return [_inline_refs(item, defs, seen, depth + 1) for item in node]

    ref = node.get("$ref")
    if isinstance(ref, str):
        name = ref.split("/")[-1]
        target = defs.get(name) if ref.startswith("#/$defs/") else None
        rest = {key: value for key, value in node.items() if key != "$ref"}
        if not isinstance(target, dict) or name in seen or depth > 6:
            return {**({"type": "object"} if not rest else {}), **rest}
        return {
            **_inline_refs(target, defs, seen | {name}, depth + 1),
            **{key: _inline_refs(value, defs, seen, depth + 1) for key, value in rest.items()},
        }
    return {key: _inline_refs(value, defs, seen, depth + 1) for key, value in node.items()}


def _widen(field_name: str, schema: dict[str, Any]) -> dict[str, Any]:
    if field_name not in _NUMERIC_TOLERANT_FIELDS:
        return schema
    widened = dict(schema)
    declared = widened.get("type")
    if declared == "string":
        widened["type"] = ["string", "number"]
    widened.pop("anyOf", None) if declared is None and "anyOf" in widened else None
    return widened


def _signature_for_input_model(model: type[BaseModel], *, return_type: Any = Signature.empty) -> Signature:
    """Build the advertised MCP signature: **faithful schema, loose validation**.

    FastMCP registers tools with `validate_input=False`, so the advertised inputSchema and the actual
    validation are decoupled — the real validation is the pydantic model inside the function body, which
    runs *after* `normalize_request_payload`. We exploit that: every parameter is optional with a
    permissive annotation (so nothing is rejected before normalization, and the documented `request={…}`
    escape hatch actually works), while the per-field JSON schema — description, enum, required-ness as
    a `[required]` marker — is still advertised verbatim so the model sees the real contract.
    """
    json_schema = model.model_json_schema()
    defs = json_schema.get("$defs", {})
    properties = json_schema.get("properties", {})
    required = set(json_schema.get("required", []))

    parameters: list[Parameter] = [
        Parameter(
            "request",
            kind=Parameter.KEYWORD_ONLY,
            default=None,
            annotation=Annotated[
                Any,
                WithJsonSchema(
                    {
                        "type": ["object", "string"],
                        "description": (
                            "Escape hatch: pass the whole payload as one object (or a JSON string). "
                            "Required for any field not declared below."
                        ),
                    }
                ),
            ],
        )
    ]

    for field_name in model.model_fields:
        field_schema = _inline_refs(properties.get(field_name, {}), defs)
        if not isinstance(field_schema, dict):
            field_schema = {}
        field_schema = _widen(field_name, dict(field_schema))
        field_schema.pop("default", None)
        if field_name in required:
            description = str(field_schema.get("description") or "").strip()
            field_schema["description"] = f"[required] {description}".strip()
            field_schema["x-horosa-required"] = True
        parameters.append(
            Parameter(
                field_name,
                kind=Parameter.KEYWORD_ONLY,
                default=None,
                annotation=Annotated[Any, WithJsonSchema(field_schema)],
            )
        )

    return Signature(parameters=parameters, return_annotation=return_type)


def _merge_mcp_arguments(kwargs: dict[str, Any]) -> dict[str, Any] | str | None:
    request = kwargs.pop("request", None)
    if request is not None:
        return request
    # 每个参数现在都以 None 为默认值出现在 kwargs 里；把它们喂进 extra="allow" 的模型会凭空造出
    # 几十个 None 字段，也会让澄清闸误判「用户已提供该设置」。未显式给出的一律剔除。
    return {key: value for key, value in kwargs.items() if value is not None}


# `horosa_tool_run` 的公共字段：覆盖绝大多数技法的起盘输入 + 闸门确认位。
# 其余技法专属字段走 `request`（arg model 是 extra=ignore，未声明的顶层键会被静默吞）。
_TOOL_RUN_COMMON_FIELDS: tuple[tuple[str, Any, str], ...] = (
    ("date", str | None, "公历日期 YYYY-MM-DD / solar date"),
    ("time", str | None, "时间 HH:mm:ss / time of day"),
    ("zone", str | None, "时区偏移，如 +08:00 / timezone offset"),
    ("lat", str | float | None, "纬度，如 31n13 或 31.22 / latitude"),
    ("lon", str | float | None, "经度，如 121e28 或 121.47 / longitude"),
    ("gpsLat", float | None, "十进制纬度 / decimal latitude"),
    ("gpsLon", float | None, "十进制经度 / decimal longitude"),
    ("ad", int | None, "公元前后，1=公元 / era flag"),
    ("gender", str | int | None, "性别 / gender (男/女 or 1/0)"),
    ("name", str | None, "当事人姓名 / subject name"),
    ("pos", str | None, "地点名 / place name"),
    ("datetime", str | None, "推运类的目标时刻 / predictive target datetime"),
    ("dirZone", str | None, "推运目标地时区 / directed timezone"),
    ("dirLat", str | float | None, "推运目标地纬度 / directed latitude"),
    ("dirLon", str | float | None, "推运目标地经度 / directed longitude"),
    ("question", str | None, "所问事项 / the question asked"),
    ("response_view", str | None, "响应裁剪：titles | sections / response view"),
    ("agent_confirmed_settings", bool | None, "用户已确认结果敏感设置后置 true"),
    ("defaults_accepted", bool | None, "用户明确接受星阙默认值后置 true"),
    ("clarification_notes", str | None, "澄清摘要 / what the user confirmed"),
)


def _tool_run_signature(*, return_type: Any = Signature.empty) -> Signature:
    parameters = [
        Parameter("tool_name", kind=Parameter.KEYWORD_ONLY, default=None, annotation=str | None),
        Parameter(
            "request",
            kind=Parameter.KEYWORD_ONLY,
            default=None,
            annotation=dict[str, Any] | str | None,
        ),
    ]
    parameters.extend(
        Parameter(field_name, kind=Parameter.KEYWORD_ONLY, default=None, annotation=annotation)
        for field_name, annotation, _doc in _TOOL_RUN_COMMON_FIELDS
    )
    return Signature(parameters=parameters)


def _validation_error(operation_name: str, tool_name: str | None, exc: ValidationError) -> ToolValidationError:
    """pydantic 校验失败 → 与闸门同形的、可直接转问用户的结构化错误。"""
    errors = [
        {"loc": list(err.get("loc", [])), "msg": err.get("msg"), "type": err.get("type")}
        for err in exc.errors(include_url=False)
    ]
    recovery = build_validation_recovery(operation_name=operation_name, errors=errors, tool_name=tool_name)
    return ToolValidationError(
        f"{operation_name} payload failed validation; see details.agent_recovery.",
        code="tool.invalid_payload",
        details={"validation_errors": errors, "agent_recovery": recovery},
    )


def _mcp_error_envelope(exc: ToolValidationError, *, tool_name: str) -> ToolEnvelope:
    """错误也返回一个合规 ToolEnvelope（顶层 code/message/details 镜像保持向后兼容）。

    技法工具/dispatch/tool_run 的返回类型是信封；错误路径若返回裸 dict，一旦声明 outputSchema，
    server 与 client 两侧的出参校验都会失败并被包成协议级 ToolError——整个澄清闸会当场报废。
    """
    details = dict(exc.details or {})
    return ToolEnvelope(
        ok=False,
        tool=tool_name,
        version=__version__,
        input_normalized={},
        error=ErrorInfo(code=exc.code, message=str(exc), details=details),
        code=exc.code,
        message=str(exc),
        details=details,
    )


def _gate_to_envelope(error: dict[str, Any], *, tool_name: str) -> ToolEnvelope:
    """闸门/恢复类错误 dict → 合规 ToolEnvelope（顶层 code/message/details 原样镜像）。

    闸门是最常见的首次返回；它若不合返回类型，声明 outputSchema 后会被两侧出参校验打成协议级
    ToolError，澄清闸直接报废。转换保证「错误也是信封」，同时不动 details.agent_recovery 的内容。
    """
    details = dict(error.get("details") or {})
    code = str(error.get("code") or "tool.error")
    message = str(error.get("message") or "")
    return ToolEnvelope(
        ok=False,
        tool=tool_name,
        version=__version__,
        input_normalized={},
        error=ErrorInfo(code=code, message=message, details=details),
        code=code,
        message=message,
        details=details,
    )


def _gate_to_dispatch_envelope(error: dict[str, Any]) -> DispatchEnvelope:
    details = dict(error.get("details") or {})
    code = str(error.get("code") or "tool.error")
    message = str(error.get("message") or "")
    return DispatchEnvelope(
        ok=False,
        version=__version__,
        error=ErrorInfo(code=code, message=message, details=details),
        code=code,
        message=message,
        details=details,
    )


def _mcp_error_payload(exc: ToolValidationError) -> dict[str, Any]:
    return {
        "ok": False,
        "code": exc.code,
        "message": str(exc),
        "details": exc.details,
        "error": {
            "code": exc.code,
            "message": str(exc),
            "details": exc.details,
        },
    }


def _mcp_internal_error_payload(exc: Exception) -> dict[str, Any]:
    # Last-resort structured error so an unexpected failure (e.g. a DOCX/PDF renderer or disk
    # I/O error during report generation) returns cleanly instead of breaking the MCP session.
    message = str(exc) or exc.__class__.__name__
    details = {"exception_type": type(exc).__name__}
    return {
        "ok": False,
        "code": "tool.internal_error",
        "message": message,
        "details": details,
        "error": {"code": "tool.internal_error", "message": message, "details": details},
    }


def _mcp_validation_error_payload(operation_name: str, tool_name: str | None, exc: ValidationError) -> dict[str, Any]:
    # 已确认但载荷畸形（类型错/字段形状错）→ 与闸门同形的「可转问用户」恢复契约，
    # 而不是让 pydantic 文本裸奔（agent_guidance.build_validation_recovery 是同一套机读结构）。
    errors = [
        {"loc": list(err.get("loc", [])), "msg": err.get("msg"), "type": err.get("type")}
        for err in exc.errors(include_url=False)
    ]
    recovery = build_validation_recovery(operation_name=operation_name, errors=errors, tool_name=tool_name)
    details = {"validation_errors": errors, "agent_recovery": recovery}
    message = f"{operation_name} payload failed validation; see details.agent_recovery."
    return {
        "ok": False,
        "code": "tool.invalid_payload",
        "message": message,
        "details": details,
        "error": {"code": "tool.invalid_payload", "message": message, "details": details},
    }


def _agent_preflight_error(tool_name: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    preflight = validate_agent_preflight(tool_name, payload)
    if preflight.get("ok"):
        return None
    return _mcp_error_payload(ToolValidationError(preflight["message"], code=preflight["code"], details=preflight))


# ---------------------------------------------------------------------------
# MCP elicitation（双轨澄清闸）
#
# 客户端声明 elicitation 能力（Claude Code ≥2.1.76 / Cursor / VS Code）时，闸门拦截不再只回
# 结构化错误，而是先用原生表单问一次用户：
#   - 「按星阙默认继续」→ 直接以 defaults_accepted=true 重跑（最常见的快路径一跳闭环）；
#   - 「我在对话里补充设置」/取消 → 回落到既有 agent_guidance.required 错误往返（agent 照
#     SKILL.md 在聊天里追问并自行构造载荷——表单答案只进 clarification_notes，绝不静默替用户
#     选具体术数参数）。
# 不支持 elicitation 的客户端（Claude Desktop / Codex / Open WebUI / OpenClaw / CLI）行为与
# 从前逐字节一致。HOROSA_MCP_ELICIT=0 可整体关闭。任何异常都吞掉并回落——elicitation 永远
# 只能是增强，不能成为新的失败点。
# ---------------------------------------------------------------------------

_ELICIT_DEFAULTS = "按星阙默认继续 (use Xingque defaults)"
_ELICIT_PROVIDE = "我在对话里补充设置 (I will provide settings in chat)"
_ELICIT_CANCEL = "取消 (cancel)"


def _elicitation_enabled() -> bool:
    return os.environ.get("HOROSA_MCP_ELICIT", "1").strip().lower() not in {"0", "false", "off"}


async def _maybe_elicit_gate(
    mcp: FastMCP, tool_name: str, payload: dict[str, Any], gate_error: dict[str, Any]
) -> dict[str, Any] | None:
    """Try resolving a tripped clarification gate via native MCP elicitation.

    Returns an updated payload to proceed with, or None to fall back to the structured
    gate error (which may be enriched with the user's form answer in details.user_notes).
    """
    if not _elicitation_enabled():
        return None
    try:
        ctx = mcp.get_context()
        session = ctx.session
        if not session.check_client_capability(
            mcp_types.ClientCapabilities(elicitation=mcp_types.ElicitationCapability())
        ):
            return None
        prompt = (
            gate_error.get("details", {}).get("agent_recovery", {}).get("prompt_to_user")
            or f"调用 {tool_name} 前需要确认会影响结果的设置。"
        )
        schema = create_model(
            "HorosaGateDecision",
            decision=(
                Literal[_ELICIT_DEFAULTS, _ELICIT_PROVIDE, _ELICIT_CANCEL],  # type: ignore[valid-type]
                _ELICIT_DEFAULTS,
            ),
            notes=(str, ""),
        )
        result = await ctx.elicit(message=prompt, schema=schema)
        if result.action != "accept" or result.data is None:
            return None
        decision = getattr(result.data, "decision", "")
        notes = str(getattr(result.data, "notes", "") or "").strip()
        if decision == _ELICIT_DEFAULTS:
            updated = dict(payload)
            updated["defaults_accepted"] = True
            note = "user accepted Xingque defaults via MCP elicitation form"
            updated["clarification_notes"] = f"{note}; user notes: {notes}" if notes else note
            return updated
        if notes:
            # 用户选了「补充设置」并给了备注：不代答具体参数，把原话带回给 agent 追问闭环。
            gate_error.setdefault("details", {})["user_notes"] = notes
            recovery = gate_error.get("details", {}).get("agent_recovery")
            if isinstance(recovery, dict):
                recovery["user_notes"] = notes
        return None
    except Exception:  # noqa: BLE001 — elicitation must never become a new failure mode
        return None


def create_mcp_server(service: HorosaSkillService, settings: Settings) -> FastMCP:
    mcp = FastMCP(
        "Horosa Skill",
        instructions=_SERVER_INSTRUCTIONS,
        website_url="https://github.com/Horace-Maxwell/horosa-skill",
        icons=[_SERVER_ICON],
        host=settings.host,
        port=settings.port,
        streamable_http_path="/mcp",
        mount_path="/",
        log_level=settings.log_level,
    )

    async def horosa_dispatch(**kwargs: Any) -> DispatchEnvelope:
        raw_payload = _merge_mcp_arguments(kwargs)
        if isinstance(raw_payload, dict):
            error = _agent_preflight_error("dispatch", raw_payload)
            if error is not None:
                updated = await _maybe_elicit_gate(mcp, "dispatch", raw_payload, error)
                if updated is None:
                    return _gate_to_dispatch_envelope(error)
                raw_payload = updated
        try:
            return service.dispatch(_normalize_mcp_request(raw_payload, DispatchInput))
        except ToolValidationError as exc:
            return _gate_to_dispatch_envelope(_mcp_error_payload(exc))
        except ValidationError as exc:
            return _gate_to_dispatch_envelope(
                _mcp_error_payload(_validation_error("horosa_dispatch", "dispatch", exc))
            )
    dispatch_doc = (
        "Route a natural-language 术数/占星 request to the right Horosa technique tools and run them. "
        "Results are saved to local memory by default (save_result=false to disable)."
    )
    if settings.mcp_compact:
        dispatch_doc += "\n\n" + build_technique_catalog()
    horosa_dispatch.__doc__ = dispatch_doc
    horosa_dispatch.__signature__ = _signature_for_input_model(
        DispatchInput, return_type=_return_type(DispatchEnvelope)
    )
    mcp.tool(
        name="horosa_dispatch",
        title="自然语言调度 / dispatch",
        annotations=_ANN_CALC,
        meta=_tool_meta("horosa_dispatch"),
    )(horosa_dispatch)

    def horosa_agent_guidance(**kwargs: Any) -> dict[str, Any]:
        payload = _normalize_mcp_request(_merge_mcp_arguments(kwargs), AgentGuidanceInput)
        return build_agent_guidance(
            tool_name=payload.get("tool_name"),
            intent=payload.get("intent"),
            include_all=payload.get("include_all", False),
        )
    horosa_agent_guidance.__doc__ = (
        "Return machine-readable guidance for agents before calling Horosa tools. "
        "Use this to decide which user settings must be clarified instead of silently defaulted."
    )
    horosa_agent_guidance.__signature__ = _signature_for_input_model(AgentGuidanceInput)
    horosa_agent_guidance.__annotations__ = {"return": dict[str, Any]}
    mcp.tool(
        name="horosa_agent_guidance",
        title="调用前参数指引 / clarification guidance",
        annotations=_ANN_QUERY,
        meta=_tool_meta("horosa_agent_guidance"),
    )(horosa_agent_guidance)

    def horosa_memory_record_answer(**kwargs: Any) -> dict[str, Any]:
        try:
            return service.record_ai_answer(
                _normalize_mcp_request(_merge_mcp_arguments(kwargs), MemoryAnswerInput)
            )
        except ToolValidationError as exc:
            return _mcp_error_payload(exc)
    horosa_memory_record_answer.__doc__ = (
        "Attach your final AI answer to a stored run (by run_id) without rendering a report. "
        "Use this only when you are NOT calling horosa_report_render — that one already writes "
        "the ai_report back to memory itself."
    )
    horosa_memory_record_answer.__signature__ = _signature_for_input_model(MemoryAnswerInput)
    horosa_memory_record_answer.__annotations__ = {"return": dict[str, Any]}
    mcp.tool(
        name="horosa_memory_record_answer",
        title="回写 AI 结论 / record answer",
        annotations=_ANN_RENDER,
    )(horosa_memory_record_answer)

    def horosa_memory_query(**kwargs: Any) -> dict[str, Any]:
        try:
            return service.query_memory(
                _normalize_mcp_request(_merge_mcp_arguments(kwargs), MemoryQueryInput)
            )
        except ToolValidationError as exc:
            return _mcp_error_payload(exc)
    horosa_memory_query.__doc__ = (
        "Search past Horosa runs stored locally (every tool call is recorded). Filters combine with AND:\n"
        "  text — full-text over question / answer / snapshot (SQLite FTS5 trigram: Chinese substrings "
        "match, no word segmentation needed)\n"
        "  entity — the subject a run is about, i.e. a person's name (e.g. \"张三\")\n"
        "  tool — technique tool name (e.g. \"qimen\", \"bazi_birth\")\n"
        "  artifact_kind — stored artifact type: report_json / report_docx / report_pdf / snapshot\n"
        "  after / before — ISO dates bounding when the run happened; limit + offset paginate\n"
        "Examples: {\"entity\": \"张三\", \"tool\": \"bazi_birth\", \"limit\": 5} · "
        "{\"text\": \"事业\", \"after\": \"2026-01-01\"}\n"
        "Returns run summaries with run_id — pass that to horosa_memory_show or horosa_report_render."
    )
    horosa_memory_query.__signature__ = _signature_for_input_model(MemoryQueryInput)
    horosa_memory_query.__annotations__ = {"return": dict[str, Any]}
    mcp.tool(
        name="horosa_memory_query",
        title="检索历史记录 / search runs",
        annotations=_ANN_QUERY,
    )(horosa_memory_query)

    def horosa_memory_show(**kwargs: Any) -> dict[str, Any]:
        try:
            return service.show_memory(
                _normalize_mcp_request(_merge_mcp_arguments(kwargs), MemoryShowInput)
            )
        except ToolValidationError as exc:
            return _mcp_error_payload(exc)
    horosa_memory_show.__doc__ = (
        "Fetch one stored run in full by run_id: the normalized input, the export snapshot, any AI "
        "answer written back, and the paths of generated artifacts (JSON/DOCX/PDF). Use it to resume "
        "a past reading without re-casting the chart."
    )
    horosa_memory_show.__signature__ = _signature_for_input_model(MemoryShowInput)
    horosa_memory_show.__annotations__ = {"return": dict[str, Any]}
    mcp.tool(
        name="horosa_memory_show",
        title="查看单次记录 / show run",
        annotations=_ANN_QUERY,
    )(horosa_memory_show)

    def horosa_report_template(**kwargs: Any) -> dict[str, Any]:
        try:
            return service.report_template(
                _normalize_mcp_request(_merge_mcp_arguments(kwargs), ReportTemplateInput)
            )
        except ToolValidationError as exc:
            return _mcp_error_payload(exc)
        except Exception as exc:  # noqa: BLE001 - never break the MCP session on a report/IO error
            return _mcp_internal_error_payload(exc)
    horosa_report_template.__doc__ = (
        "Return the empty ai_report skeleton for a stored run (run_id + tool_name): which analysis "
        "fields to fill (direct_answer / executive_summary / analysis_sections / evidence / "
        "recommendations / limitations) and which export sections are available as evidence. "
        "Fill it from the run's export snapshot, then pass it to horosa_report_render."
    )
    horosa_report_template.__signature__ = _signature_for_input_model(ReportTemplateInput)
    horosa_report_template.__annotations__ = {"return": dict[str, Any]}
    mcp.tool(
        name="horosa_report_template",
        title="报告骨架 / report template",
        annotations=_ANN_QUERY,
    )(horosa_report_template)

    def horosa_report_render(**kwargs: Any) -> dict[str, Any]:
        try:
            return service.report_render(
                _normalize_mcp_request(_merge_mcp_arguments(kwargs), ReportRenderInput)
            )
        except ToolValidationError as exc:
            return _mcp_error_payload(exc)
        except Exception as exc:  # noqa: BLE001 - never break the MCP session on a report/IO error
            return _mcp_internal_error_payload(exc)
    horosa_report_render.__doc__ = (
        "Render a stored run into a DOCX/PDF/JSON report. Preferred when you already have a run_id "
        "(from a prior tool call): pass run_id + format + your ai_report; the ai_report is auto "
        "written back to memory (no separate memory_record_answer call needed)."
    )
    horosa_report_render.__signature__ = _signature_for_input_model(ReportRenderInput)
    horosa_report_render.__annotations__ = {"return": dict[str, Any]}
    mcp.tool(
        name="horosa_report_render",
        title="渲染报告 / render report",
        annotations=_ANN_RENDER,
    )(horosa_report_render)

    def horosa_technique_report(**kwargs: Any) -> dict[str, Any]:
        try:
            return service.technique_report(
                _normalize_mcp_request(_merge_mcp_arguments(kwargs), TechniqueReportInput)
            )
        except ToolValidationError as exc:
            return _mcp_error_payload(exc)
        except Exception as exc:  # noqa: BLE001 - never break the MCP session on a report/IO error
            return _mcp_internal_error_payload(exc)
    horosa_technique_report.__doc__ = (
        "Render the DETERMINISTIC method/provenance report for stored runs: which techniques ran, "
        "which result-sensitive settings were in force (晚子时 switches, 贵人法, ayanamsa, …), which "
        "engine actually computed each one, section coverage, and the version chain. Pass run_id for "
        "one call or group_id to cover a whole session (it then also flags cross-technique setting "
        "conflicts). format = markdown | json | docx | pdf.\n\n"
        "This is NOT the consulting report: it needs no ai_report and never contains an interpretation. "
        "Use horosa_report_render for the AI-authored reading."
    )
    horosa_technique_report.__signature__ = _signature_for_input_model(TechniqueReportInput)
    horosa_technique_report.__annotations__ = {"return": dict[str, Any]}
    mcp.tool(
        name="horosa_technique_report",
        title="技法依据报告 / technique provenance report",
        # 只读已存 run + 渲染一个文件：不起盘、不改盘面记录，同参数同结果 → readOnly + idempotent。
        # openWorld 恒 False（local-first）。如实标注，目录审核会核。
        annotations=_ANN_QUERY,
    )(horosa_technique_report)

    # horosa_report_from_run 已下线：与 horosa_report_render 逐行同义（同一 ReportRenderInput
    # → service.report_render），两个同义工具挤占 tools/list 并造成「该用哪个」歧义。

    async def horosa_report_from_tool(**kwargs: Any) -> dict[str, Any]:
        raw_payload = _merge_mcp_arguments(kwargs)
        if isinstance(raw_payload, dict):
            tool_name = raw_payload.get("tool_name")
            payload = raw_payload.get("payload")
            if isinstance(tool_name, str) and isinstance(payload, dict):
                error = _agent_preflight_error(tool_name, payload)
                if error is not None:
                    updated = await _maybe_elicit_gate(mcp, tool_name, payload, error)
                    if updated is None:
                        return error
                    raw_payload = dict(raw_payload)
                    raw_payload["payload"] = updated
        try:
            return service.report_from_tool(
                _normalize_mcp_request(raw_payload, ReportFromToolInput)
            )
        except ToolValidationError as exc:
            return _mcp_error_payload(exc)
        except ValidationError as exc:
            return _mcp_validation_error_payload("horosa_report_from_tool", None, exc)
        except Exception as exc:  # noqa: BLE001 - never break the MCP session on a report/IO error
            return _mcp_internal_error_payload(exc)
    horosa_report_from_tool.__doc__ = (
        "One-shot: run a technique tool AND prepare its report. NOTE this re-casts the chart — if you "
        "already called the tool and hold a run_id, use horosa_report_render instead (avoids a duplicate "
        "backend call and a duplicate stored run)."
    )
    horosa_report_from_tool.__signature__ = _signature_for_input_model(ReportFromToolInput)
    horosa_report_from_tool.__annotations__ = {"return": dict[str, Any]}
    mcp.tool(
        name="horosa_report_from_tool",
        title="起盘并出报告 / cast + report",
        annotations=_ANN_CALC,
    )(horosa_report_from_tool)

    # ------------------------------------------------------------------
    # MCP resources：只读目录以资源形态暴露（客户端可 @ 引用，不占 tools/list）。
    # ------------------------------------------------------------------

    @mcp.resource(
        "horosa://catalog/techniques",
        name="horosa-technique-catalog",
        title="Horosa 技法目录 / technique catalog",
        description="All callable Horosa technique tools with one-line bilingual descriptions.",
        mime_type="text/markdown",
    )
    def technique_catalog_resource() -> str:
        return build_technique_catalog()

    @mcp.resource(
        "horosa://catalog/export-registry",
        name="horosa-export-registry",
        title="Horosa 导出契约注册表 / export contract registry",
        description="Machine-readable export contract (per-technique snapshot sections) mirrored from Xingque aiExport.",
        mime_type="application/json",
    )
    def export_registry_resource() -> str:
        return json.dumps(build_export_registry(), ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # MCP prompts：高频工作流按钮化（Claude Code 里成为 /mcp__horosa__… 斜杠命令）。
    # ------------------------------------------------------------------

    @mcp.prompt(
        name="quick_cast",
        title="快速起盘并解读 / quick cast & read",
        description="Cast one Horosa technique for a moment/birth and explain from the export snapshot.",
    )
    def prompt_quick_cast(technique: str = "", question: str = "") -> str:
        target = technique or "（按用户意图选择技法）"
        asked = question or "（用户尚未给出具体问题）"
        return (
            f"请用 Horosa 工具起一个「{target}」盘并解读。用户的问题：{asked}。\n"
            "流程：1) 若时间/地点/性别/流派等会改变结果的设置缺失，先按 horosa_agent_guidance 问我；"
            "2) 调用对应技法工具（用户确认后带 agent_confirmed_settings/defaults_accepted）；"
            "3) 只根据返回的 export_snapshot.export_text 分段解读——先结论、再证据段、再机会/风险/时机/建议；"
            "4) 不要手算任何术数结果。"
        )

    @mcp.prompt(
        name="annual_fortune",
        title="流年运势报告 / annual fortune report",
        description="Run the right predictive tools for a target year and produce a structured reading.",
    )
    def prompt_annual_fortune(year: str = "", birth: str = "") -> str:
        return (
            f"请为我做{year or '目标年份'}的流年运势分析（出生信息：{birth or '待我提供'}）。\n"
            "要求：1) 先确认目标年份、出生数据、地点时区等必需设置（缺了就问我）；"
            "2) 选择合适的推运工具（如 profection/solarreturn/bazi_direct/liureng_runyear），"
            "预测类必须带目标 datetime/dirZone 等字段；3) 每个结论都引用返回快照里的具体段落；"
            "4) 最后按 机会/风险/时机/建议 汇总。"
        )

    @mcp.prompt(
        name="export_report",
        title="导出正式报告 / export a formal report",
        description="Render the latest run into a DOCX/PDF consulting report with the AI analysis written back.",
    )
    def prompt_export_report(format: str = "docx") -> str:
        return (
            f"请把刚才的分析导出为 {format or 'docx'} 报告。\n"
            "流程：用已有 run_id 调 horosa_report_render（format + ai_report，分析会自动写回记忆；"
            "不要用 horosa_report_from_tool 重复起盘）。报告正文要像咨询报告：直接结论开头、"
            "引用盘面证据、机会/风险/时机/建议分列、保留「排盘规则」行；不要出现 run_id/JSON 等机器元数据。"
        )

    if settings.mcp_compact:
        # 精简模式（8 门面 + tool_run = 9 工具）：技法工具不平铺，注册一个按名直呼的通用工具（dispatch 关键词路由只覆盖部分技法，
        # 直呼通道保证 92 技法全部可达）；澄清闸照常生效。
        async def horosa_tool_run(**kwargs: Any) -> ToolEnvelope:
            # tool_name 必须在合并之前取走：它是 `request` 的**兄弟**参数，而 `_merge_mcp_arguments`
            # 在 request 存在时会整体改用 request 作为载荷（否则 `{tool_name, request}` 这种最常见的
            # 调法会把 tool_name 丢掉）。未显式给出的公共字段是 None，一并剔除，避免 None 被当作
            # 「用户已提供该设置」而影响澄清闸的追问过滤。
            tool_name = str(kwargs.pop("tool_name", "") or "")
            request = kwargs.get("request")
            kwargs = {key: value for key, value in kwargs.items() if value is not None}
            raw_payload = _merge_mcp_arguments(kwargs)
            if not isinstance(raw_payload, dict):
                raw_payload = {}
            raw_payload.pop("tool_name", None)
            payload = request if isinstance(request, dict) else raw_payload
            if tool_name not in TOOL_DEFINITIONS:
                return _mcp_error_envelope(
                    ToolValidationError(
                        f"Unknown tool: {tool_name or '(missing tool_name)'}",
                        code="tool.unknown",
                        details={"tool_name": tool_name, "hint": "See the technique catalog in this tool's description."},
                    ),
                    tool_name=tool_name or "horosa_tool_run",
                )
            error = _agent_preflight_error(tool_name, payload)
            if error is not None:
                updated = await _maybe_elicit_gate(mcp, tool_name, payload, error)
                if updated is None:
                    return _gate_to_envelope(error, tool_name=tool_name)
                payload = updated
            try:
                return service.run_tool(
                    tool_name,
                    _normalize_mcp_request(payload, TOOL_DEFINITIONS[tool_name].input_model),
                )
            except ToolValidationError as exc:
                return _mcp_error_envelope(exc, tool_name=tool_name)
            except ValidationError as exc:
                return _mcp_error_envelope(
                    _validation_error("horosa_tool_run", tool_name, exc), tool_name=tool_name
                )

        horosa_tool_run.__doc__ = (
            "Run any Horosa technique tool by name. Pass `tool_name` plus the tool's input fields: "
            "the common birth/event fields are declared below, and **any other technique-specific "
            "field must go inside `request`** (e.g. request={\"guirengType\":2}) — undeclared "
            "top-level keys are dropped by the MCP argument layer. Same clarification gate and "
            "envelope as the dedicated tools.\n\n"
            + build_technique_catalog()
        )
        # 必须手写 signature：函数是 `**kwargs` 多态入口，没有单一 input model 可推导。
        # 缺了它 FastMCP 会内省出一个名叫 `kwargs` 的 string 必填参数，整个工具无法调用——
        # 而它是 compact 模式下抵达全部技法的唯一通道（技法工具在该模式下根本不注册）。
        horosa_tool_run.__signature__ = _tool_run_signature(return_type=_return_type(ToolEnvelope))
        mcp.tool(
            name="horosa_tool_run",
            title="按名直调技法 / run any technique",
            annotations=_ANN_CALC,
            meta=_tool_meta("horosa_tool_run"),
        )(horosa_tool_run)
        return mcp

    toolsets = _selected_toolsets()
    for definition in TOOL_DEFINITIONS.values():
        if toolsets is not None and definition.domain.lower() not in toolsets:
            continue
        input_model = definition.input_model

        def _factory(tool_name: str, model: Any) -> Any:
            async def _tool(**kwargs: Any) -> ToolEnvelope:
                raw_payload = _merge_mcp_arguments(kwargs)
                if isinstance(raw_payload, dict):
                    error = _agent_preflight_error(tool_name, raw_payload)
                    if error is not None:
                        updated = await _maybe_elicit_gate(mcp, tool_name, raw_payload, error)
                        if updated is None:
                            return _gate_to_envelope(error, tool_name=tool_name)
                        raw_payload = updated
                try:
                    return service.run_tool(
                        tool_name,
                        _normalize_mcp_request(raw_payload, model),
                    )
                except ToolValidationError as exc:
                    return _mcp_error_envelope(exc, tool_name=tool_name)
                except ValidationError as exc:
                    return _mcp_error_envelope(
                        _validation_error(tool_name, tool_name, exc), tool_name=tool_name
                    )

            _tool.__name__ = TOOL_DEFINITIONS[tool_name].mcp_name
            _tool.__doc__ = build_tool_docstring(tool_name)
            _tool.__signature__ = _signature_for_input_model(
                model, return_type=_return_type(ToolEnvelope)
            )
            mcp_name = TOOL_DEFINITIONS[tool_name].mcp_name
            return mcp.tool(
                name=mcp_name,
                title=_tool_title(tool_name),
                annotations=_tool_annotations(tool_name),
                meta=_tool_meta(mcp_name),
            )(_tool)

        _factory(definition.name, input_model)

    return mcp


def run_mcp_server(settings: Settings, *, transport: str, service: HorosaSkillService | None = None) -> None:
    service = service or HorosaSkillService(settings)
    server = create_mcp_server(service, settings)
    server.run(transport=transport)
