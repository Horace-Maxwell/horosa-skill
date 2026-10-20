"""MCP 请求的入参：各家客户端的参数形状归一（request 字符串 / 平铺 / 嵌套）、按输入模型生成工具签名（数值字段放宽）、horosa_tool_run 的公共字段。"""
from __future__ import annotations

import json
from inspect import Parameter, Signature
from typing import Annotated, Any

from pydantic import BaseModel, WithJsonSchema

from horosa_skill.errors import ToolValidationError
from horosa_skill.input_normalization import normalize_request_payload


def _normalize_mcp_request(raw_request: Any, model: type[BaseModel]) -> dict[str, Any]:
    # 与 service.run_tool / 各门面的归一化 + 校验是**有意重复**：两步都幂等，但这一层产出 MCP 形状的
    # 校验错误（_validation_error），那一层产出带 agent_recovery 的 tool.invalid_payload；两种形状都被
    # MCP 健壮性测试钉住。合并之前先审测试，别顺手删。
    payload = raw_request
    if isinstance(payload, BaseModel):
        payload = payload.model_dump(exclude_none=True)

    if payload is None:
        payload = {}

    if isinstance(payload, str):
        text = payload.strip()
        try:
            payload = {} if not text else json.loads(text)
        except json.JSONDecodeError as exc:
            # 🔴 这两条以前抛 JSONDecodeError / ValueError，而它们发生在**每个工具的 try 之前** ——
            # lowlevel server 把裸异常转成 `isError: true` + 原始字符串，绕过整个 agent_recovery 契约。
            # 影响面是全部 116 个工具：任何把参数字符串化的客户端（Gemini CLI、旧版 Cursor、
            # n8n/Dify 的模板渲染）传坏一次 JSON，拿到的就是一条模型无从恢复的裸报错。
            raise ToolValidationError(
                "request 不是合法的 JSON 对象字符串。",
                code="tool.invalid_payload",
                details={
                    "request_preview": text[:120],
                    "json_error": str(exc),
                    "next_action": "把参数按 inputSchema 直接作为对象传；确需整包时 request 必须是合法 JSON 对象。",
                },
            ) from exc

    if not isinstance(payload, dict):
        raise ToolValidationError(
            "request 必须是对象或 JSON 对象字符串。",
            code="tool.invalid_payload",
            details={
                "received_type": type(payload).__name__,
                "next_action": "把参数按 inputSchema 直接作为对象传。",
            },
        )

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
    if declared is None and "anyOf" in widened:
        # 🔴 以前这里是一句表达式语句 `widened.pop("anyOf", None) if … else None`：它把唯一的类型
        # 信息摘掉却不补回去。pydantic 给 `float | None` 的形状是 anyOf:[{number},{null}]，pop 完
        # 只剩 {"title": "Gpslat"}，再经 _own_property 的键白名单过滤后就是**空对象 {}**。
        # 实测 70 个属性（gpsLat/gpsLon×26、datetime/dirZone×6、dirLat/dirLon×3 …）广告成 {}，
        # 而 Gemini/Vertex 的 FunctionDeclaration 与 OpenAI strict 都要求每个属性有 type ——
        # 它们拒的不是这一个字段，是**整张工具表**。
        members = {
            str(entry.get("type"))
            for entry in widened.get("anyOf", [])
            if isinstance(entry, dict) and entry.get("type") and entry.get("type") != "null"
        }
        widened.pop("anyOf", None)
        # 这批字段的引擎口径都能吃字符串（normalize_request_payload 会把 "31.22" 归一成 "31n13"），
        # 所以多类型时统一广告成 string，是**无损**的收窄。
        widened["type"] = "string" if len(members) != 1 else members.pop()
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
    ("date", str | None, "公历日期 YYYY-MM-DD"),
    ("time", str | None, "HH:mm:ss"),
    ("zone", str | None, "时区偏移，如 +08:00"),
    ("lat", str | float | None, "纬度 31n13 / 31.22"),
    ("lon", str | float | None, "经度 121e28 / 121.47"),
    ("gpsLat", float | None, "十进制纬度"),
    ("gpsLon", float | None, "十进制经度"),
    ("ad", int | None, "纪元 1=公元后 -1=公元前"),
    ("gender", str | int | None, "性别 1/男 0/女"),
    ("name", str | None, "当事人姓名"),
    ("pos", str | None, "地点名"),
    ("datetime", str | None, "推运目标时刻"),
    ("dirZone", str | None, "推运目标地时区"),
    ("dirLat", str | float | None, "推运目标地纬度"),
    ("dirLon", str | float | None, "推运目标地经度"),
    ("question", str | None, "所问事项"),
    ("response_view", str | None, "响应裁剪 titles|sections"),
    ("agent_confirmed_settings", bool | None, "用户已确认设置→true"),
    ("defaults_accepted", bool | None, "用户接受默认→true"),
    ("clarification_notes", str | None, "确认摘要"),
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
