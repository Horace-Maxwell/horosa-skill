"""MCP 请求的入参：各家客户端的参数形状归一（request 字符串 / 平铺 / 嵌套）、按输入模型生成工具签名（数值字段放宽）、horosa_tool_run 的公共字段。"""
from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from inspect import Parameter, Signature
from typing import Annotated, Any

from pydantic import BaseModel, Field, WithJsonSchema

from pydantic import ValidationError

from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.errors import ToolValidationError, bilingual
from horosa_skill.input_normalization import normalize_request_payload, tool_error_from_validation
from horosa_skill.profiles import carries_profile

# 一次工具调用里 `request` 与顶层参数的冲突说明：合并发生在工具函数体里，警告要等结果出门时才有地方放，
# 所以由 `HorosaMCPServer.call_tool` 开作用域、把这张表并进 warnings。
_REQUEST_NOTES: ContextVar[list[str] | None] = ContextVar("horosa_mcp_request_notes", default=None)
# 客户端发来的原始参数（v0.50.0）：SDK 按签名生成的 arg model 会在函数体之前丢掉未声明的顶层键（`place`、`name`、别名键、
# 嵌套 `birth`…）。`call_tool` 把原始参数放在这里，`_merge_mcp_arguments` 把签名之外的键接回来，交给归一化去认或报「未知参数」。
_RAW_ARGUMENTS: ContextVar[dict[str, Any] | None] = ContextVar("horosa_mcp_raw_arguments", default=None)
# 技法输入模型：这一层只校验、原样交给 run_tool（它再归一化一次并把解读说明写进 warnings）。
_TECHNIQUE_MODELS = frozenset(definition.input_model for definition in TOOL_DEFINITIONS.values())


@contextmanager
def request_conflict_scope(arguments: dict[str, Any] | None = None) -> Iterator[list[str]]:
    notes: list[str] = []
    token = _REQUEST_NOTES.set(notes)
    raw_token = _RAW_ARGUMENTS.set(dict(arguments) if isinstance(arguments, dict) else None)
    try:
        yield notes
    finally:
        _RAW_ARGUMENTS.reset(raw_token)
        _REQUEST_NOTES.reset(token)


def _normalize_mcp_request(raw_request: Any, model: type[BaseModel], *, tool_name: str | None = None) -> dict[str, Any]:
    body = _request_object(raw_request)
    try:
        normalized = model.model_validate(normalize_request_payload(body, model=model))
    except ValidationError as exc:
        if model not in _TECHNIQUE_MODELS:
            raise
        # 技法模型：与 run_tool 同一份逐字段错误（每个字段一条恢复条目），不是整份闸门问卷。
        raise tool_error_from_validation(exc, tool_name=tool_name or model.__name__, payload=body) from exc
    return normalized.model_dump(exclude_none=True)


def _mcp_payload(raw_request: Any, model: type[BaseModel]) -> dict[str, Any]:
    """MCP 参数 → 交给 service 的载荷。带命主档案名的载荷**不在这一层校验**，原样交下去：

    这一层的 `model_dump` 会把模型缺省值写成显式值（ad=1、紫微 gender=true），档案里存的同名字段就被缺省值压掉了；
    run_tool / dispatch 先并档案、再归一化与校验（错误照样是带 agent_recovery 的 tool.invalid_payload）。

    技法模型（v0.50.0）：这一层只做校验（坏入参在这里就是结构化错误），交下去的是**原载荷**——run_tool 自己归一化，
    「东八区 → +08:00」这类解读说明才进得了结果的 warnings（归一化过的值再归一化一次不会再产生说明）。"""
    body = _request_object(raw_request)
    if carries_profile(body, model):
        return body
    validated = _normalize_mcp_request(body, model)
    return body if model in _TECHNIQUE_MODELS else validated


_CONFIRMATION_FLAGS = ("agent_confirmed_settings", "defaults_accepted")


def precheck_arguments(gate: str | None, payload: Any) -> ToolValidationError | None:
    """闸门之前的两道检查（v0.50.0，`_gated_run` 第一步）：

    1. 确认位必须是 JSON 布尔：`"true"` / 1 / `"yes"` 以前会被闸门当成「没确认」反复追问，模型不知道错在哪（闸门读 `is True`）。
    2. 技法载荷的逐字段校验先于闸门：「东八区」读不懂、`zone=480`、`time=辰时` 这类错误直接回逐字段的恢复条目，
       不先走一轮「请确认设置」的问卷。带命主档案名的载荷跳过（档案并进来之后 run_tool 再校验）。"""
    if not isinstance(payload, dict):
        return None
    for key in _CONFIRMATION_FLAGS:
        value = payload.get(key)
        if value is not None and not isinstance(value, bool):
            return ToolValidationError(
                bilingual(f"`{key}` 必须是 JSON 布尔值 true（收到 {value!r}）：只在用户真的确认之后传 true。",
                          f"`{key}` must be the JSON boolean true (got {value!r}); pass true only after the user really confirmed."),
                code="tool.confirmation_flag_not_boolean",
                details={"field": key, "got": value if isinstance(value, (str, int, float)) else repr(value), "expected": "true", "example": True,
                         "agent_recovery": {"kind": "input", "must_ask_user": False, "reason": "invalid_field", "next_action": "fix_field_and_retry",
                                            "fix_fields": [{"field": key, "got": value if isinstance(value, (str, int, float)) else repr(value),
                                                            "expected": "JSON boolean true", "example": True}]}},
            )
    definition = TOOL_DEFINITIONS.get(gate or "")
    if definition is not None:
        model: Any = definition.input_model
    elif gate in ("dispatch", "hecan"):
        from horosa_skill.schemas.tools.facades import DispatchInput

        model = DispatchInput
    else:
        return None
    if carries_profile(payload, model):
        return None
    try:
        # dispatch / hecan：只判当事人位置上的字段（birth / subject / context），不按门面模型报「未知参数」。
        normalize_request_payload(payload, model=model if definition is not None else None)
    except ToolValidationError as exc:
        return exc
    return None


def _request_object(raw_request: Any) -> dict[str, Any]:
    """整包载荷（`request` 或合并后的参数）→ dict：BaseModel / None / JSON 对象字符串都收，其余 → tool.invalid_payload。"""
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

    return payload


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
                        # 与 dispatch / hecan 同一句（v0.48.0：原英文长句 113 B × 9 个门面，两面都付）。
                        # 技法工具的 request 描述由广告层 `mcp_schema._request_property` 重写。
                        "description": "整包载荷（对象或 JSON 串）；未声明的键放这里",
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

    if model in _TECHNIQUE_MODELS:
        # 全技法通用的两个入口参数（v0.50.0）：`place` = 地名（service.resolve_place_fields 解析成坐标 + 时区，可代替 lat / lon / zone）、
        # `name` = 当事人（存档按人查找用；也收 subject.name）。声明在签名上是为了 SDK 不丢它；广告层只广告 place（预算）。
        for common, doc in COMMON_TECHNIQUE_PARAMS.items():
            if common in model.model_fields or (common == "place" and not _takes_location(model)):
                continue
            parameters.append(Parameter(common, kind=Parameter.KEYWORD_ONLY, default=None,
                                        annotation=Annotated[Any, WithJsonSchema({"type": "string", "description": doc})]))
    return Signature(parameters=parameters, return_annotation=return_type)


COMMON_TECHNIQUE_PARAMS: dict[str, str] = {
    "place": "地名（解析出坐标与时区，可代替 lat/lon/zone）",
    "name": "当事人姓名（存档按人查找）",
}


def _takes_location(model: type[BaseModel]) -> bool:
    fields = model.model_fields
    return "lat" in fields or "lon" in fields or "inner" in fields


def _merge_mcp_arguments(kwargs: dict[str, Any]) -> dict[str, Any] | str | None:
    """顶层参数 + `request` → 一份载荷：`{**flat, **request}`，同名不同值时 `request` 优先并留一条警告。

    `horosa_tool_run` 的描述就教这种写法（公共字段放顶层、技法专属字段进 `request`）。曾经 `request` 一出现就整体替换，
    `horosa_astro_chart(hsys=3, request={…})` 回 ok=True 而盘按 hsys=1 起，没有一句话。
    """
    declared = set(kwargs)
    request = kwargs.pop("request", None)
    # 每个参数现在都以 None 为默认值出现在 kwargs 里；把它们喂进 extra="allow" 的模型会凭空造出
    # 几十个 None 字段，也会让澄清闸误判「用户已提供该设置」。未显式给出的一律剔除。
    flat = {key: value for key, value in kwargs.items() if value is not None}
    # 签名之外的顶层键（SDK 已经丢了）从原始参数里接回来：顶层与 `request` 同等对待（schema 写的就是
    # additionalProperties: true）。认得的由归一化接住（place / name / 别名键），认不得的进 warnings。
    raw = _RAW_ARGUMENTS.get() or {}
    for key, value in raw.items():
        if key not in declared and key != "tool_name" and value is not None:
            flat.setdefault(key, value)
    flat = _unwrap(flat, declared)
    if request is None:
        return flat
    if not flat:
        return _unwrap(request, declared)
    try:
        body = _unwrap(_request_object(request), declared)
    except ToolValidationError:
        # 调用点都在各工具的 try 之外：这里不抛，坏 request 原样往下走，由 _normalize_mcp_request 报 tool.invalid_payload。
        return request
    conflicts = sorted(key for key, value in flat.items() if key in body and body[key] != value)
    notes = _REQUEST_NOTES.get()
    if conflicts and notes is not None:
        names = "、".join(conflicts)
        notes.append(bilingual(f"`request` 与顶层参数同名不同值（{names}），已按 `request` 的值起盘。",
                               f"`request` and top-level arguments disagree on {', '.join(conflicts)}; the `request` value was used."))
    return {**flat, **body}


_WRAPPER_KEYS = ("payload", "arguments", "params", "input")


def _unwrap(body: Any, declared: set[str]) -> Any:
    """`{"payload": {...}}` / `{"arguments": {...}}` 这类客户端包装层（工具没声明这个键时）→ 拆开，里层键优先级低于外层显式键。"""
    if not isinstance(body, dict):
        return body
    for key in _WRAPPER_KEYS:
        inner = body.get(key)
        if key in declared or not isinstance(inner, dict):
            continue
        rest = {k: v for k, v in body.items() if k != key}
        body = {**inner, **rest}
        notes = _REQUEST_NOTES.get()
        if notes is not None:
            notes.append(bilingual(f"`{key}` 包装层已拆开，里面的字段按顶层参数读。", f"The `{key}` wrapper was unpacked; its fields were read as top-level arguments."))
    return body


# `horosa_tool_run` 的公共字段：覆盖绝大多数技法的起盘输入 + 闸门确认位。
# 其余技法专属字段走 `request`（arg model 是 extra=ignore，未声明的顶层键会被静默吞）。
# 第三列是广告层描述（v0.48.0 起真的发出去：`mcp_schema.apply_advertised_schemas` 按 `tool_run_field_docs()` 补进
# tools/list——此前这一列从没广告过，精简面唯一的技法通道连闸门三键都没说明）。同一字段与技法广告层同一句（`mcp_schema.CORE_DOC`）；
# tool_run 没有 enum，ad / response_view 把取值写进描述。签名（校验层）只用前两列。
_TOOL_RUN_COMMON_FIELDS: tuple[tuple[str, Any, str], ...] = (
    ("date", str | None, "公历 YYYY-MM-DD"),
    ("time", str | None, "HH:mm:ss"),
    ("zone", str | None, "偏移，如 +08:00"),
    ("lat", str | float | None, "31n13 / 31.22"),
    ("lon", str | float | None, "121e28 / 121.47"),
    ("gpsLat", float | None, "十进制纬度"),
    ("gpsLon", float | None, "十进制经度"),
    ("ad", int | None, "1=公元 -1=公元前"),
    ("gender", str | int | None, "1/男 0/女"),
    ("name", str | None, "当事人姓名（透传盘头）"),
    ("pos", str | None, "地点显示名（只显示；要解析坐标传 place）"),
    ("place", str | None, "地名（解析出坐标与时区，可代替 lat/lon/zone）"),
    ("datetime", str | None, "推运目标时刻"),
    ("dirZone", str | None, "推运目标地时区"),
    ("dirLat", str | float | None, "推运目标地纬度"),
    ("dirLon", str | float | None, "推运目标地经度"),
    ("question", str | None, "所问事项"),
    ("response_view", str | None, "full / sections / titles（全文已存档）"),
    ("agent_confirmed_settings", bool | None, "用户已确认设置→true"),
    ("defaults_accepted", bool | None, "用户接受默认→true"),
    ("clarification_notes", str | None, "确认摘要"),
    # 签名上也带描述的唯一一个：它是新概念（自备知识库），在别处的门面 schema 上同样有说明。
    ("knowledge", Annotated[list[str] | str | None, Field(description="自备知识库：条目名,#标签,auto")], "自备知识库：条目名 / #标签 / auto"),
    # 命主档案名（精简面是多数客户端的缺省面，这里是它唯一的起盘入口）：同样是新概念，带描述。
    ("profile", Annotated[str | None, Field(description="命主档案名（horosa_profile 存的）")], "命主档案名"),
)


def tool_run_field_docs() -> dict[str, str]:
    """`horosa_tool_run` 公共字段 → 广告层描述（广告层只补缺：签名里已带描述的键保持原样）。"""
    return {name: doc for name, _annotation, doc in _TOOL_RUN_COMMON_FIELDS}


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
