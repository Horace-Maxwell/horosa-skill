"""工具 API（ToolsAPI）：list_tools、本地工具分派表、run_tool（闸门、富化、存档、信封）。"""
from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import partial
from typing import Any

from pydantic import ValidationError

from horosa_skill import __version__
from horosa_skill.agent_guidance import build_tool_input_contract
from horosa_skill.decisions.layer import decision_records
from horosa_skill.engine.registry import (
    TOOL_DEFINITIONS,
    ToolDefinition,
    resolve_tool_name,
)
from horosa_skill.errors import HorosaSkillError, ToolValidationError, bilingual
from horosa_skill.exports import build_export_registry, parse_export_content
from horosa_skill.input_fields import input_notes_scope
from horosa_skill.input_normalization import field_issues_error, normalize_request_payload, tool_error_from_validation
from horosa_skill.knowledge import (
    build_knowledge_registry,
    read_knowledge_entry,
)
from horosa_skill.schemas.common import ErrorInfo, ToolEnvelope
from horosa_skill.service._context import _degrade_collector, _memory_save_failed, _run_query_scope
from horosa_skill.service.api.place import place_resolution_note
from horosa_skill.service.text.predictive import _PERIOD_PREDICTIVE_TOOLS
from horosa_skill.service.endpoints import _SHENSHU_ENDPOINTS
from horosa_skill.service.envelope import (
    _apply_response_view,
    _cn_unified_zone_note,
    _extract_entities,
    _generic_summary,
    _missing_sections_warning,
    _with_operational_recovery,
)
from horosa_skill.service.export import TOOL_EXPORT_TECHNIQUE_MAP, _attach_export_contract
from horosa_skill.knowledge import search as knowledge_search
from horosa_skill.knowledge import user as user_knowledge
from horosa_skill.knowledge.user import build_context as build_user_knowledge_context
from horosa_skill import profiles as birth_profiles
from horosa_skill.service.text.chart_family import (
    _apply_chart_request_defaults,
    _india_apply_school_presets,
    _india_chart_remote_payload,
)


def _redact_knowledge_text(envelope: dict[str, Any]) -> dict[str, Any]:
    """存档只记自备资料的引用，不存正文（隐私：删了笔记，旧存档里不该还有全文；报告分享出去也不该带上）。"""
    data = envelope.get("data")
    if isinstance(data, dict) and isinstance(data.get("knowledge_context"), dict):
        envelope = {**envelope, "data": {**data, "knowledge_context": user_knowledge.redact_for_storage(data["knowledge_context"])}}
    return envelope


# 结果随性别而变（大运 / 大限 / 行年顺逆、条文分男女）的技法：没有性别不起盘（v0.50.0，tool.missing_gender）。旧行为是悄悄按男命
# 排（紫微 / 八字直断 / 六壬行年的 schema 缺省 True；八字、河洛、参评、一掌经走上游「未知(按男排)」；神数五支后端缺省男）。
# 太乙不在内：它多用于事件局，性别只进命法段，闸门照常追问（tool_table 的 sex 选项含「事件局/不指定」）。
GENDER_DEPENDENT_TOOLS = frozenset({
    "bazi_birth", "bazi_direct", "ziwei_birth", "liureng_runyear", "heluo", "canping", "yizhangjing",
    "tieban", "shaozi", "xianqin", "cetian", "qizhengkin",
})


# 技法内部再调技法（择日铸展示盘、三式合一、七政分盘…）时为 True：那些载荷是代码拼的事件时刻，不是用户的命主——性别闸只拦入口调用。
_INSIDE_TECHNIQUE: ContextVar[bool] = ContextVar("horosa_inside_technique", default=False)


def _require_result_facts(tool_name: str, payload: dict[str, Any]) -> None:
    target = payload.get("datetime")
    if isinstance(target, str) and len(target) == 4 and target.isdigit() and tool_name not in _PERIOD_PREDICTIVE_TOOLS:
        # 只给年份的目标时刻只对「有那一年含义」的技法成立（返照 / 流年 / 小限 / 太阳弧，见 enrich._apply_yearly_target）。
        raise field_issues_error([{
            "field": "datetime", "code": "tool.invalid_datetime", "got": target,
            "expected": bilingual("YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS", "YYYY-MM-DD or YYYY-MM-DD HH:MM:SS"), "example": f"{target}-01-01 12:00:00",
            "ask_user": False, "message": bilingual(f"`{tool_name}` 的目标时刻要具体到日期：只给年份「{target}」不知道是哪一天。",
                                                   f"`{tool_name}` needs a target date, not just the year '{target}'."),
        }])
    options = payload.get("options") if isinstance(payload.get("options"), dict) else {}
    if payload.get("gender") is None and options.get("gender") is not None:
        # 神数旧写法：性别写在 options 里（runner 会提升到顶层）——同一个解析器判它，认得就算给了。
        from horosa_skill.input_fields import FieldIssue, parse_gender

        try:
            parse_gender(options["gender"])
        except FieldIssue as issue:
            raise field_issues_error([{"field": "options.gender", "code": issue.code, "got": options["gender"],
                                       "expected": bilingual(issue.expected_zh, issue.expected_en), "example": issue.example,
                                       "options": issue.options, "ask_user": True, "message": bilingual(issue.zh, issue.en)}]) from None
        return
    if tool_name in GENDER_DEPENDENT_TOOLS and payload.get("gender") is None and not _INSIDE_TECHNIQUE.get():
        raise field_issues_error([{
            "field": "gender", "code": "tool.missing_gender", "got": None,
            "expected": bilingual("1 / 男 / 乾造 = 男；0 / 女 / 坤造 = 女", "1 / 男 / male = male; 0 / 女 / female = female"),
            "example": 1, "ask_user": True, "options": [{"value": 1, "label": "男 / male"}, {"value": 0, "label": "女 / female"}],
            "message": bilingual(
                f"`{tool_name}` 的结果随性别而变（大运 / 大限顺逆、条文分男女），没有性别不起盘：请向用户问性别，不要默认成男。",
                f"`{tool_name}` depends on gender (direction of the luck cycles, gendered verses); ask the user instead of assuming male.",
            ),
        }])


@dataclass
class _ToolCall:
    """一次 run_tool 的现场。`input_normalized` 放这里而不是局部变量：计算途中它会被重新绑定（上游推运缺省、印度流派预设），
    而后端失败时的信封与存档读的都是最新值。写成计算函数的返回值，失败路径就把它丢了（tests/test_run_tool_phases.py）。"""

    definition: ToolDefinition
    input_normalized: dict[str, Any]
    knowledge_selection: Any
    trace: dict[str, Any]
    degrade_notes: list[str]
    # 这次并进载荷的命主档案（profiles.ProfileUse）：技法卡 `profiles` 与 summary 一行读它；不带 notes。
    profile_uses: list[Any] = field(default_factory=list)
    # 载荷里 `place` 的解析记录（service/api/place.py）：成功 / 失败信封的 warnings 与技法卡都回显，不进引擎请求。
    place_records: list[dict[str, Any]] = field(default_factory=list)
    # 入参解读说明（input_fields.add_input_note：别名改名、东八区 → +08:00、未知参数…）：成功 / 失败信封的 warnings 都回显。
    input_notes: list[str] = field(default_factory=list)

    @property
    def place_notes(self) -> list[str]:
        """入口说明（入参解读 + 地名解析），两种信封的 warnings 都以它开头。"""
        return [*self.input_notes, *(place_resolution_note(record) for record in self.place_records)]

    @property
    def tool_name(self) -> str:
        return self.definition.name


def _failure_envelope(call: _ToolCall, *, summary: str, code: str, message: str, details: dict[str, Any]) -> ToolEnvelope:
    profile_line = birth_profiles.profile_summary_line(call.profile_uses)
    return ToolEnvelope(
        ok=False,
        tool=call.tool_name,
        version=__version__,
        input_normalized=call.input_normalized,
        data={},
        summary=[summary, *([profile_line] if profile_line else [])],
        warnings=[*call.place_notes, *call.degrade_notes],
        memory_ref=None,
        error=ErrorInfo(code=code, message=message, details=details),
        code=code,
        message=message,
        details=details,
        trace_id=call.trace["trace_id"],
        group_id=call.trace["group_id"],
    )


def _shenshu_runner(api: Any, name: str, payload: dict[str, Any]) -> dict[str, Any]:
    return api._run_shenshu_tool(payload, name)


def _by_name(method: str) -> Callable[[Any, str, dict[str, Any]], dict[str, Any]]:
    """一个 runner 服务一族技法，第一个参数是技法名。"""
    return lambda api, name, payload: getattr(api, method)(name, payload)


def _payload_only(method: str) -> Callable[[Any, str, dict[str, Any]], dict[str, Any]]:
    return lambda api, _name, payload: getattr(api, method)(payload)


def _progextra(api: Any, name: str, payload: dict[str, Any]) -> dict[str, Any]:
    return api._run_progextra_js_tool(payload, name)


# 不走命名约定的本地工具（技法名 → (api, 技法名, 载荷) → 结果）。一批共用 runner 的技法表（神数、择日）在 `_local_runner` 里按表判。
_LOCAL_RUNNER_OVERRIDES: dict[str, Callable[[Any, str, dict[str, Any]], dict[str, Any]]] = {
    "export_registry": _payload_only("_local_export_registry"),
    "export_parse": _payload_only("_local_export_parse"),
    "knowledge_registry": _payload_only("_local_knowledge_registry"),
    "knowledge_read": _payload_only("_local_knowledge_read"),
    "qizhengelection": _payload_only("_run_qizheng_election_tool"),
    "ziwei_birth": _payload_only("_run_ziwei_tool"),
    "liureng_gods": _by_name("_run_liureng_tool"),
    "liureng_runyear": _by_name("_run_liureng_tool"),
    "bazi_birth": _by_name("_run_bazi_tool"),
    "bazi_direct": _by_name("_run_bazi_tool"),
    "triplicityrulers": _progextra,
    "keypoints": _progextra,
    "lunationphase": _progextra,
}


class ToolsAPI:
    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "mcp_name": tool.mcp_name,
                "execution": tool.execution,
                "endpoint": tool.endpoint,
                "description": tool.description,
                "input_contract": build_tool_input_contract(tool.name),
            }
            for tool in TOOL_DEFINITIONS.values()
        ]

    def _user_knowledge_summary(self) -> dict[str, Any]:
        return {
            **user_knowledge.overview(self.settings, limit=200),
            "how_to_use": "计算时传 knowledge=[条目 id / 标题 / #标签 / auto / ?检索词]，选中的正文挂在 data.knowledge_context"
                          "（长条目只带与本盘相关的段落，每段标标题与行号）；检索：horosa_knowledge_search；精读一条："
                          "knowledge_read(domain=\"user\", key=…, from_line=…)。往文件夹里放 .md / .txt 即可新增；"
                          "problems 列出没能读入的文件和原因。",
        }

    def knowledge_search(self, payload: dict[str, Any]) -> dict[str, Any]:
        """门面 horosa_knowledge_search：检索内置知识与自备知识库，返回排好序的片段 + 出处 + 精读参数。"""
        from horosa_skill.schemas.tools.facades import KnowledgeSearchInput

        try:
            request = KnowledgeSearchInput.model_validate(payload)
        except ValidationError as exc:
            raise ToolValidationError(bilingual("知识检索的参数不对。", "Invalid payload for knowledge search."),
                                      code="knowledge.search.invalid_payload", details={"errors": exc.errors()}) from exc
        result = self._search_knowledge(request.model_dump())
        matches = result.get("matches") or []
        result["how_to_read"] = (
            "精读一条：horosa_knowledge_read，参数取命中项的 read 字段（自备笔记带 from_line，从命中段开始读）；"
            "内置条目用 domain + category + key。" if matches else
            "没有命中：换个说法、拆成更短的词（两个字也能查），或去掉 domain 过滤。"
        )
        return result

    def _search_knowledge(self, payload: dict[str, Any]) -> dict[str, Any]:
        return knowledge_search.search_all(self.settings, payload)

    def _local_export_registry(self, payload: dict[str, Any]) -> dict[str, Any]:
        return build_export_registry(technique=payload.get("technique"))

    def _local_export_parse(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return parse_export_content(
                technique=payload["technique"],
                content=payload["content"],
                selected_sections=payload.get("selected_sections"),
                planet_info=payload.get("planet_info"),
                astro_meaning=payload.get("astro_meaning"),
            )
        except ValueError as exc:
            raise ToolValidationError(
                str(exc),
                code="tool.invalid_export_technique",
                details={"tool_name": "export_parse", "technique": payload.get("technique")},
            ) from exc

    def _local_knowledge_registry(self, payload: dict[str, Any]) -> dict[str, Any]:
        if f"{payload.get('domain') or ''}".strip() == user_knowledge.USER_DOMAIN:
            return {"domain": user_knowledge.USER_DOMAIN, "user_knowledge": self._user_knowledge_summary()}
        registry = build_knowledge_registry(domain=payload.get("domain"))
        if not payload.get("domain"):
            registry = {**registry, "user_knowledge": self._user_knowledge_summary()}
        return registry

    def _local_knowledge_read(self, payload: dict[str, Any]) -> dict[str, Any]:
        if f"{payload.get('query') or ''}".strip():
            # 检索已有专门的门面 horosa_knowledge_search（v0.45.0）；knowledge_read 带 query 的老用法照旧可用。
            return self._search_knowledge(payload)
        domain = f"{payload.get('domain') or ''}".strip()
        if domain == user_knowledge.USER_DOMAIN:
            return user_knowledge.read_entry(self.settings, payload.get("key") or payload.get("category") or "",
                                             from_line=payload.get("from_line"), max_lines=payload.get("max_lines"))
        return read_knowledge_entry(payload)

    def _local_runner(self, name: str) -> Callable[[dict[str, Any]], dict[str, Any]] | None:
        """本地工具 → runner。缺省 `_run_<技法名>_tool(payload)`：加技法写好 runner 就够。认不出返回 None。"""
        override = _LOCAL_RUNNER_OVERRIDES.get(name)
        if override is not None:
            return partial(override, self, name)
        if name in self._ZERI_SCAN_TOOLS:
            return partial(self._run_zeri_scan_tool, name)
        if name in self._ZERI_BACKEND_TOOLS:
            return partial(self._run_zeri_backend_tool, name)
        if name in _SHENSHU_ENDPOINTS:
            return partial(_shenshu_runner, self, name)
        return getattr(self, f"_run_{name}_tool", None)

    def _run_local_tool(self, definition: ToolDefinition, payload: dict[str, Any]) -> dict[str, Any]:
        runner = self._local_runner(definition.name)
        if runner is None:
            raise ToolValidationError(
                f"Unsupported local tool: {definition.name}",
                code="tool.unsupported_local_tool",
                details={"tool_name": definition.name},
            )
        return runner(payload)

    @property
    def profiles(self) -> birth_profiles.ProfileStore:
        """命主档案库（构造不碰磁盘；只有载荷带档案名或调 horosa_profile 时才读写）。"""
        store = self.__dict__.get("_profile_store")
        if store is None:
            store = self.__dict__["_profile_store"] = birth_profiles.ProfileStore(self.settings)
        return store

    def profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        """门面 horosa_profile：命主档案 save / get / list / delete（CLI `profile` 走同一个函数）。"""
        payload, resolution = self._profile_place_coordinates(payload)
        result = birth_profiles.run_action(self.profiles, payload)
        if resolution is not None:
            # 存下的坐标 / 时区来自地名：结果里回显，让 AI 念给用户确认（与技法载荷的 place 同一条解析、同一套回显）。
            result = {**result, "place_resolution": resolution,
                      "warnings": [*result.get("warnings", []), place_resolution_note(resolution)]}
        return result

    def _profile_place_coordinates(self, payload: Any) -> tuple[Any, dict[str, Any] | None]:
        """save 时只给了地名、没给经纬度：用技法载荷同一条 `resolve_place_fields` 补 lat / lon（+ 按出生日期补 zone）。
        唯一命中才补；歧义 / 找不到 / 夏令时切换日照常拒绝（place.*，带候选）。显式经纬度永远优先；这次没给坐标、
        库里已有坐标且地名没变（例如只改备注）就不重查——同名多地的标签不该让一次改备注被拒。"""
        if not isinstance(payload, dict) or payload.get("action") != "save" or not isinstance(payload.get("data"), dict):
            return payload, None
        data = payload["data"]
        label = data.get("place")
        if not isinstance(label, str) or not label.strip():
            return payload, None
        if any(data.get(key) not in (None, "") for key in ("lat", "lon", "gpsLat", "gpsLon")):
            return payload, None
        previous = next(
            (p for p in self.profiles.all() if birth_profiles.name_key(p.name) == birth_profiles.name_key(payload.get("name") or "")),
            None,
        )
        if previous is not None and previous.place == label and any(k in previous.fields for k in ("lat", "gpsLat")):
            return payload, None
        dated = {**(previous.fields if previous is not None else {}), **{k: v for k, v in data.items() if v is not None}}
        # 日期 / 时间可借库里已存的（只改地名时按原出生日期取偏移）；zone 只认这次给的——换了地名还沿用旧 zone 就错了。
        spot = {key: dated[key] for key in ("date", "time") if key in dated}
        spot.update({key: data[key] for key in ("zone", "cnUnifiedZone") if data.get(key) is not None})
        resolved = self.resolve_place_fields({**spot, "place": label}, tool_name="horosa_profile")
        resolution = resolved.get("placeResolution")
        filled = {key: resolved[key] for key in ("lat", "lon", "gpsLat", "gpsLon") if key in resolved}
        if "zone" not in data and "zone" in resolved and (resolution or {}).get("zone_source") == "place_and_date":
            filled["zone"] = resolved["zone"]
        return {**payload, "data": {**data, **filled}}, resolution

    def _validated_tool_input(
        self, definition: ToolDefinition, payload: dict[str, Any], trace: dict[str, Any]
    ) -> tuple[dict[str, Any], Any, list[Any], list[dict[str, Any]]]:
        """(规范化入参, 自备知识库点名, 并进来的命主档案, 地名解析记录)。这一段的 ValidationError 有意抛出去：坏入参不是一次失败的计算。
        先并档案、再解析地名：档案只存 place 文字标签、不进载荷，所以两者不会互相覆盖；载荷自己的 place 照常解析。"""
        tool_name = definition.name
        # 命主档案在归一化与校验**之前**并进来：显式字段逐键优先，模型缺省值不会冒充「显式」压掉档案里的值。
        # 认不出 / 有歧义的档案名与坏入参同级：拒绝，不起盘（profile.not_found / profile.ambiguous）。
        try:
            payload, profile_uses = birth_profiles.expand_tool_payload(
                self.profiles, payload, model=definition.input_model, domain=definition.domain
            )
        except ToolValidationError as exc:
            trace["error_code"] = exc.code
            raise
        try:
            # 地名 → 坐标 + 时区（v0.48.0，service/api/place.py）：lat / lon / zone 是必填，place 得在归一化与校验之前补上；
            # 有歧义 / 找不到 / 旧 runtime 都是结构化拒绝（place.*，带 agent_recovery），同样有意抛出去。
            payload = self.resolve_place_fields(payload, tool_name=tool_name)
        except ToolValidationError as exc:
            trace["error_code"] = exc.code
            raise
        raw_payload = payload if isinstance(payload, dict) else {}  # 含 placeResolution：缺 zone 的提示要知道 place 给过
        payload, place_records = self.pop_place_records(payload)
        try:
            # 归一 + 逐字段校验（v0.50.0，input_normalization）：读不懂的字段一次全列出（每个字段一条恢复条目），
            # 做了解读的（东八区 → +08:00、1990年5月3日…）记进 input_notes，成功信封的 warnings 回显。
            payload = normalize_request_payload(payload, model=definition.input_model)
            # 自备知识库点名只决定附加上下文：校验前取走，绝不进 input_normalized / 引擎请求 / 存档 subject。
            knowledge_selection = None
            if isinstance(payload, dict) and "knowledge" in payload:
                payload = dict(payload)
                knowledge_selection = payload.pop("knowledge")
            validated = definition.input_model.model_validate(payload)
        except ToolValidationError as exc:
            trace["error_code"] = exc.code
            raise
        except ValidationError as exc:
            error = tool_error_from_validation(exc, tool_name=tool_name, payload=raw_payload)
            trace["error_code"] = error.code
            raise error from exc
        input_normalized = validated.model_dump(exclude_none=True)
        _require_result_facts(tool_name, input_normalized)
        return (
            _apply_chart_request_defaults(tool_name, input_normalized),
            knowledge_selection,
            profile_uses,
            place_records,
        )

    def _compute_tool_result(self, call: _ToolCall) -> dict[str, Any]:
        """起盘 + 富化 + 导出契约 + 技法卡。"""
        tool_name, definition = call.tool_name, call.definition
        if definition.execution == "local":
            response_data = self._run_local_tool(definition, call.input_normalized)
        else:
            assert definition.endpoint is not None
            call.input_normalized = self._apply_upstream_predictive_defaults(tool_name, call.input_normalized)
            if tool_name == "india_chart":
                # 流派预设（岁差/宫制）先落进规范化输入：请求体与快照口径行同源（否则盘按 KP 岁差算、
                # [起盘信息] 却按缺省写 Lahiri）。
                call.input_normalized = _india_apply_school_presets(call.input_normalized)
            remote_input = (
                _india_chart_remote_payload(call.input_normalized) if tool_name == "india_chart" else call.input_normalized
            )
            response_data = self._call_remote(definition.endpoint, remote_input)
            response_data = self._attach_predictive_chart_context(tool_name, call.input_normalized, response_data)
        input_normalized = call.input_normalized
        response_data = self._attach_natal_extras(tool_name, response_data, input_normalized)
        response_data = self._attach_classical_derived(tool_name, response_data, input_normalized)
        response_data = self._attach_classical_analysis(tool_name, input_normalized, response_data)
        response_data = self._attach_jyotish_sections(tool_name, response_data, input_normalized)
        response_data = self._attach_india_extra_vargas(tool_name, input_normalized, response_data)
        response_data = self._attach_calendar_extras(tool_name, input_normalized, response_data)
        response_data = self._attach_relative_score(tool_name, input_normalized, response_data)
        response_data = self._attach_relative_comp_charts(tool_name, input_normalized, response_data)
        response_data = self._attach_jieqi_year_extras(tool_name, input_normalized, response_data)
        response_data = _attach_export_contract(tool_name, input_normalized, response_data)
        # 技法依据卡：必须在 save_result **之前**挂，memory 才存到全量卡；
        # `_apply_response_view` 在存档之后裁剪，且显式豁免这个键（见那里的说明）。
        return self._attach_technique_card(tool_name, input_normalized, response_data)

    def _with_user_knowledge(self, call: _ToolCall, response_data: dict[str, Any]) -> tuple[dict[str, Any], Any, str | None]:
        """把自备知识库的选中条目挂上去：(结果, 知识上下文, 失败说明)。附加资料出错绝不该让一张算好的盘作废。"""
        if call.knowledge_selection in (None, "", []) or not isinstance(response_data, dict):
            return response_data, None, None
        card = response_data.get("technique_card") if isinstance(response_data.get("technique_card"), dict) else {}
        snapshot = response_data.get("export_snapshot") if isinstance(response_data.get("export_snapshot"), dict) else {}
        try:
            knowledge_context = build_user_knowledge_context(
                self.settings, call.knowledge_selection, tool_name=call.tool_name,
                technique=TOOL_EXPORT_TECHNIQUE_MAP.get(call.tool_name), domain=call.definition.domain,
                technique_label=str((card.get("technique") or {}).get("label") or "") or None,
                # 长条目按「与这张盘相关」挑段落：拿本次导出正文当检索依据。
                focus=str(snapshot.get("export_text") or ""),
            )
        except Exception as exc:  # noqa: BLE001 - 附加资料出错绝不该让一张算好的盘作废
            return response_data, None, bilingual(
                f"自备知识库这次没能带入（{type(exc).__name__}: {exc}）；盘面结果不受影响。",
                f"Your knowledge entries could not be attached ({type(exc).__name__}: {exc}); the chart is unaffected.",
            )
        return {**response_data, "knowledge_context": knowledge_context}, knowledge_context, None

    def _success_envelope(self, call: _ToolCall, response_data: dict[str, Any]) -> ToolEnvelope:
        response_data, knowledge_context, knowledge_failure = self._with_user_knowledge(call, response_data)
        summary = _generic_summary(call.tool_name, response_data)
        if call.profile_uses and isinstance(response_data, dict):
            # 出处：哪个档案、填了哪些键、哪些被本次显式值压过。不带 notes / 别名 / 地点标签。
            card = response_data.get("technique_card")
            if isinstance(card, dict):
                card["profiles"] = [use.card() for use in call.profile_uses]
            summary = [*summary, birth_profiles.profile_summary_line(call.profile_uses)]
        # 工具内部经 `_warnings` 上抛的降级说明（如子引擎不可用）落入 envelope.warnings，
        # 不静默：调用方能看到「结果不完整」而 ok 仍为 True（优雅降级 ≠ 无声降级）。
        warnings: list[str] = list(call.place_notes)
        if call.place_records and isinstance(response_data, dict) and isinstance(response_data.get("technique_card"), dict):
            # 技法卡在存档之前就挂好了（_compute_tool_result）；这里补上「地点是怎么来的」，同一份存进 memory。
            response_data["technique_card"]["place_resolution"] = [dict(record) for record in call.place_records]
        if isinstance(response_data, dict):
            raised = response_data.pop("_warnings", None)
            if isinstance(raised, list):
                warnings.extend(str(item) for item in raised if f"{item}".strip())
        warnings.extend(note for note in call.degrade_notes if note not in warnings)
        zone_note = _cn_unified_zone_note(call.input_normalized)
        if zone_note and zone_note not in warnings:
            warnings.append(zone_note)
        # 预设段缺席 → warnings + summary 各一条：agent 不翻 export_snapshot 也知道结果不完整。
        if knowledge_context is not None:
            warnings.extend(user_knowledge.context_warnings(knowledge_context))
        if knowledge_failure:
            warnings.append(knowledge_failure)
        missing_note = _missing_sections_warning(response_data)
        if missing_note:
            warnings.append(missing_note)
            summary = [*summary, missing_note]
        return ToolEnvelope(
            ok=True,
            tool=call.tool_name,
            version=__version__,
            input_normalized=call.input_normalized,
            data=response_data,
            summary=summary,
            warnings=warnings,
            memory_ref=None,
            error=None,
            trace_id=call.trace["trace_id"],
            group_id=call.trace["group_id"],
        )

    def _persist_tool_result(
        self, call: _ToolCall, envelope: ToolEnvelope, *, run_id: str | None, query_text: str | None, evaluation_case_id: str | None
    ) -> None:
        """写进本地记忆，补 `memory_ref` 与技法卡的 refs。存档是旁路：写不进去不许丢掉已经算好的结果。"""
        trace = call.trace
        try:
            effective_run_id = run_id or self.store.create_run(
                entrypoint="tool",
                query_text=query_text,
                subject=call.input_normalized,
                group_id=trace["group_id"],
            )
            self.store.record_entities(
                effective_run_id,
                _extract_entities(call.input_normalized, query_text) + [
                    # 按档案名能查回这个人的历次起盘（horosa_memory_query entity="妈妈"）。
                    {"entity_type": "profile", "entity_key": birth_profiles.name_key(use.name), "display_name": use.name, "metadata": {"slot": use.slot}}
                    for use in call.profile_uses
                ],
            )
            memory_ref = self.store.record_tool_result(
                run_id=effective_run_id,
                tool_name=call.tool_name,
                ok=envelope.ok,
                input_normalized=call.input_normalized,
                envelope_dict=_redact_knowledge_text(envelope.model_dump(mode="json")),
                summary=envelope.summary,
                warnings=envelope.warnings,
                error=envelope.error.model_dump(mode="json") if envelope.error else None,
                trace_id=trace["trace_id"],
                group_id=trace["group_id"],
                evaluation_case_id=evaluation_case_id,
            )
            envelope.memory_ref = memory_ref
            trace["run_id"] = effective_run_id
            trace["artifact_path"] = memory_ref.artifact_path
            # run_id 要到存档时才存在，所以技法卡的 refs 只能在这里补。存档里的那份没有自己的
            # run_id（自指），这是正常的——取回时 run_id 本来就是你用来取它的那把钥匙。
            card = envelope.data.get("technique_card")
            if isinstance(card, dict):
                card["refs"] = {
                    "run_id": effective_run_id,
                    "trace_id": trace["trace_id"],
                    "group_id": trace["group_id"],
                }
        except Exception as exc:  # noqa: BLE001 - 存档是旁路：写不进去不许丢掉已经算好的结果
            envelope.memory_ref = None
            envelope.warnings.append(_memory_save_failed(exc))

    def run_tool(
        self,
        tool_name: str,
        payload: dict[str, Any],
        *,
        save_result: bool = True,
        run_id: str | None = None,
        query_text: str | None = None,
        group_id: str | None = None,
        evaluation_case_id: str | None = None,
    ) -> ToolEnvelope:
        resolved = resolve_tool_name(tool_name)
        if resolved is None:
            from horosa_skill.agent_guidance import unknown_tool_details

            raise ToolValidationError(
                bilingual(f"未知技法：{tool_name}", f"Unknown tool: {tool_name}"),
                code="tool.unknown",
                details=unknown_tool_details(tool_name),
            )
        tool_name = resolved

        definition = TOOL_DEFINITIONS[tool_name]
        workflow_group_id = group_id or self.tracer.new_group_id()
        with self.tracer.span(
            workflow_name="tool.run",
            group_id=workflow_group_id,
            metadata={
                "entrypoint": "tool",
                "tool_name": tool_name,
                "runtime_target": definition.execution,
                "query_text": query_text,
                "payload": payload,
                "evaluation_case_id": evaluation_case_id,
            },
        ) as trace, _degrade_collector() as degrade_notes, decision_records(), _run_query_scope(query_text), input_notes_scope(fresh=_INSIDE_TECHNIQUE.get()) as input_notes:
            input_normalized, knowledge_selection, profile_uses, place_records = self._validated_tool_input(definition, payload, trace)
            call = _ToolCall(
                definition, input_normalized, knowledge_selection, trace, degrade_notes,
                profile_uses=profile_uses, place_records=place_records, input_notes=input_notes,
            )
            try:
                inside = _INSIDE_TECHNIQUE.set(True)
                try:
                    computed = self._compute_tool_result(call)
                finally:
                    _INSIDE_TECHNIQUE.reset(inside)
                envelope = self._success_envelope(call, computed)
            except HorosaSkillError as exc:
                trace["error_code"] = exc.code
                envelope = _failure_envelope(
                    call,
                    # 顶层镜像三键（见 schemas/common.py）：MCP 面的闸门/校验错误一直镜像，工具自身的
                    # 错误（runtime.not_installed / tool.ken_compute_failed / transport.*）却没有，
                    # 按顶层 `code` 读的调用方在最常见的失败上读到 None。两条路径口径必须一致。
                    summary=f"工具 `{tool_name}` 调用失败（{exc.code}）。",
                    code=exc.code,
                    message=str(exc),
                    details=_with_operational_recovery(exc.code, exc.details),
                )
            except Exception as exc:  # noqa: BLE001 - last-resort guard: a surface/dispatch must never crash
                # Tool execution and the snapshot/summary/export post-processing touch backend-shaped
                # data and can raise unexpected ValueError/KeyError/IndexError/TypeError. Convert those
                # into a structured ok=False envelope instead of letting a traceback escape the CLI or
                # break the MCP session / abort a whole dispatch. (Bad-payload ValidationError is handled
                # separately above and intentionally still raises.)
                trace["error_code"] = "tool.internal_error"
                envelope = _failure_envelope(
                    call,
                    summary=f"工具 `{tool_name}` 调用时发生内部错误。",
                    code="tool.internal_error",
                    message=str(exc),
                    details={"exception_type": type(exc).__name__},
                )

            if save_result:
                self._persist_tool_result(call, envelope, run_id=run_id, query_text=query_text, evaluation_case_id=evaluation_case_id)

            # response_view 视图裁剪在存档之后：memory 保全量，返回体按需精简。
            envelope = _apply_response_view(envelope, call.input_normalized)
            trace["success"] = envelope.ok
            trace["input_normalized"] = call.input_normalized
            trace["summary"] = envelope.summary
            trace["warnings"] = envelope.warnings
            return envelope
