"""工具 API（ToolsAPI）：list_tools、本地工具分派表、run_tool（闸门、富化、存档、信封）。"""
from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from horosa_skill import __version__
from horosa_skill.agent_guidance import (
    build_tool_input_contract,
    build_validation_recovery,
)
from horosa_skill.decisions.layer import decision_records
from horosa_skill.engine.registry import (
    TOOL_DEFINITIONS,
    ToolDefinition,
    resolve_tool_name,
)
from horosa_skill.errors import HorosaSkillError, ToolValidationError, bilingual
from horosa_skill.exports import build_export_registry, parse_export_content
from horosa_skill.input_normalization import normalize_request_payload
from horosa_skill.knowledge import (
    build_knowledge_registry,
    read_knowledge_entry,
    search_knowledge,
)
from horosa_skill.schemas.common import ErrorInfo, ToolEnvelope
from horosa_skill.service._context import _degrade_collector, _run_query_scope
from horosa_skill.service.endpoints import _SHENSHU_ENDPOINTS
from horosa_skill.service.envelope import (
    _apply_response_view,
    _cn_unified_zone_note,
    _extract_entities,
    _generic_summary,
    _missing_sections_warning,
    _with_operational_recovery,
)
from horosa_skill.service.export import _attach_export_contract
from horosa_skill.service.text.chart_family import (
    _apply_chart_request_defaults,
    _india_apply_school_presets,
    _india_chart_remote_payload,
)


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

    def _run_local_tool(self, definition: ToolDefinition, payload: dict[str, Any]) -> dict[str, Any]:
        if definition.name == "export_registry":
            return build_export_registry(technique=payload.get("technique"))
        if definition.name == "export_parse":
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
                    details={"tool_name": definition.name, "technique": payload.get("technique")},
                ) from exc
        if definition.name == "knowledge_registry":
            return build_knowledge_registry(domain=payload.get("domain"))
        if definition.name == "knowledge_read":
            # query 模式（v0.30.0）：跨全部知识域全文检索；不给 query 走精读老路。
            if f"{payload.get('query') or ''}".strip():
                return search_knowledge(payload)
            return read_knowledge_entry(payload)
        if definition.name == "qimen":
            return self._run_qimen_tool(payload)
        if definition.name == "qimenzeri":
            return self._run_qimenzeri_tool(payload)
        if definition.name in self._ZERI_SCAN_TOOLS:
            return self._run_zeri_scan_tool(definition.name, payload)
        if definition.name in self._ZERI_BACKEND_TOOLS:
            return self._run_zeri_backend_tool(definition.name, payload)
        if definition.name == "tianxing":
            return self._run_tianxing_tool(payload)
        if definition.name == "qizhengelection":
            return self._run_qizheng_election_tool(payload)
        if definition.name == "india_rectify":
            return self._run_india_rectify_tool(payload)
        if definition.name == "planet_cycles":
            return self._run_planet_cycles_tool(payload)
        if definition.name == "jieqi_birth":
            return self._run_jieqi_birth_tool(payload)
        if definition.name == "taiyi":
            return self._run_taiyi_tool(payload)
        if definition.name == "jinkou":
            return self._run_jinkou_tool(payload)
        if definition.name in {"liureng_gods", "liureng_runyear"}:
            return self._run_liureng_tool(definition.name, payload)
        if definition.name in {"bazi_birth", "bazi_direct"}:
            return self._run_bazi_tool(definition.name, payload)
        if definition.name == "ziwei_birth":
            return self._run_ziwei_tool(payload)
        if definition.name == "suzhan":
            return self._run_suzhan_tool(payload)
        if definition.name == "sixyao":
            return self._run_sixyao_tool(payload)
        if definition.name == "geomancy":
            return self._run_geomancy_tool(payload)
        if definition.name == "tarot":
            return self._run_tarot_tool(payload)
        if definition.name == "lingqi":
            return self._run_lingqi_tool(payload)
        if definition.name == "tongshefa":
            return self._run_tongshefa_tool(payload)
        if definition.name == "canping":
            return self._run_canping_tool(payload)
        if definition.name == "heluo":
            return self._run_heluo_tool(payload)
        if definition.name == "yizhangjing":
            return self._run_yizhangjing_tool(payload)
        if definition.name == "xiaoliuren":
            return self._run_xiaoliuren_tool(payload)
        if definition.name == "feigong":
            return self._run_feigong_tool(payload)
        if definition.name == "xiaochengtu":
            return self._run_xiaochengtu_tool(payload)
        if definition.name == "guice":
            return self._run_guice_tool(payload)
        if definition.name == "zhengchuan":
            return self._run_zhengchuan_tool(payload)
        if definition.name == "acg":
            return self._run_acg_tool(payload)
        if definition.name == "astrodata":
            return self._run_astrodata_tool(payload)
        if definition.name == "bazi_inverse":
            return self._run_bazi_inverse_tool(payload)
        if definition.name == "sanshiunited":
            return self._run_sanshiunited_tool(payload)
        if definition.name == "huangli":
            return self._run_huangli_tool(payload)
        if definition.name == "tongshu":
            return self._run_tongshu_tool(payload)
        if definition.name == "xuanshi":
            return self._run_xuanshi_tool(payload)
        if definition.name == "babylon":
            return self._run_babylon_tool(payload)
        if definition.name == "draconic":
            return self._run_draconic_tool(payload)
        if definition.name == "relocation":
            return self._run_relocation_tool(payload)
        if definition.name == "hellen_chart":
            return self._run_hellen_chart_tool(payload)
        if definition.name == "guolao_chart":
            return self._run_guolao_chart_tool(payload)
        if definition.name == "germany":
            return self._run_germany_tool(payload)
        if definition.name == "harmonic":
            return self._run_harmonic_tool(payload)
        if definition.name == "agepoint":
            return self._run_agepoint_tool(payload)
        if definition.name == "distributions":
            return self._run_distributions_tool(payload)
        if definition.name == "jaynesprog":
            return self._run_jaynesprog_tool(payload)
        if definition.name == "vedicprog":
            return self._run_vedicprog_tool(payload)
        if definition.name == "ephemeris":
            return self._run_ephemeris_tool(payload)
        if definition.name == "returntimeline":
            return self._run_returntimeline_tool(payload)
        if definition.name == "prenatalsyzygy":
            return self._run_prenatalsyzygy_tool(payload)
        if definition.name == "prog":
            return self._run_prog_tool(payload)
        if definition.name == "planetaryarc":
            return self._run_planetaryarc_tool(payload)
        if definition.name == "planetaryages":
            return self._run_planetaryages_tool(payload)
        if definition.name == "balbillus":
            return self._run_balbillus_tool(payload)
        if definition.name == "yearsystem129":
            return self._run_yearsystem129_tool(payload)
        if definition.name == "persiandirected":
            return self._run_persiandirected_tool(payload)
        if definition.name in {"triplicityrulers", "keypoints", "lunationphase"}:
            return self._run_progextra_js_tool(payload, definition.name)
        if definition.name == "extrareturns":
            return self._run_extrareturns_tool(payload)
        if definition.name == "horary":
            return self._run_horary_tool(payload)
        if definition.name == "election":
            return self._run_election_tool(payload)
        if definition.name in _SHENSHU_ENDPOINTS:
            return self._run_shenshu_tool(payload, definition.name)
        if definition.name == "mundane":
            return self._run_mundane_tool(payload)
        if definition.name == "firdaria":
            return self._run_firdaria_tool(payload)
        if definition.name == "decennials":
            return self._run_decennials_tool(payload)
        if definition.name == "otherbu":
            return self._run_otherbu_tool(payload)
        raise ToolValidationError(
            f"Unsupported local tool: {definition.name}",
            code="tool.unsupported_local_tool",
            details={"tool_name": definition.name},
        )

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
        ) as trace, _degrade_collector() as degrade_notes, decision_records(), _run_query_scope(query_text):
            try:
                payload = normalize_request_payload(payload)
                validated = definition.input_model.model_validate(payload)
            except ValidationError as exc:
                trace["error_code"] = "tool.invalid_payload"
                errors = exc.errors()
                raise ToolValidationError(
                    f"Invalid payload for tool `{tool_name}`.",
                    code="tool.invalid_payload",
                    details={
                        "errors": errors,
                        "agent_recovery": build_validation_recovery(
                            operation_name=f"tool.{tool_name}",
                            tool_name=tool_name,
                            errors=errors,
                        ),
                    },
                ) from exc

            input_normalized = validated.model_dump(exclude_none=True)
            input_normalized = _apply_chart_request_defaults(tool_name, input_normalized)
            memory_ref = None

            try:
                if definition.execution == "local":
                    response_data = self._run_local_tool(definition, input_normalized)
                else:
                    assert definition.endpoint is not None
                    input_normalized = self._apply_upstream_predictive_defaults(tool_name, input_normalized)
                    if tool_name == "india_chart":
                        # 流派预设（岁差/宫制）先落进规范化输入：请求体与快照口径行同源（否则盘按 KP 岁差算、
                        # [起盘信息] 却按缺省写 Lahiri）。
                        input_normalized = _india_apply_school_presets(input_normalized)
                    remote_input = (
                        _india_chart_remote_payload(input_normalized) if tool_name == "india_chart" else input_normalized
                    )
                    response_data = self._call_remote(definition.endpoint, remote_input)
                    response_data = self._attach_predictive_chart_context(tool_name, input_normalized, response_data)
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
                response_data = self._attach_technique_card(tool_name, input_normalized, response_data)
                summary = _generic_summary(tool_name, response_data)
                # 工具内部经 `_warnings` 上抛的降级说明（如子引擎不可用）落入 envelope.warnings，
                # 不静默：调用方能看到「结果不完整」而 ok 仍为 True（优雅降级 ≠ 无声降级）。
                warnings: list[str] = []
                if isinstance(response_data, dict):
                    raised = response_data.pop("_warnings", None)
                    if isinstance(raised, list):
                        warnings.extend(str(item) for item in raised if f"{item}".strip())
                warnings.extend(note for note in degrade_notes if note not in warnings)
                zone_note = _cn_unified_zone_note(input_normalized)
                if zone_note and zone_note not in warnings:
                    warnings.append(zone_note)
                # 预设段缺席 → warnings + summary 各一条：agent 不翻 export_snapshot 也知道结果不完整。
                missing_note = _missing_sections_warning(response_data)
                if missing_note:
                    warnings.append(missing_note)
                    summary = [*summary, missing_note]
                envelope = ToolEnvelope(
                    ok=True,
                    tool=tool_name,
                    version=__version__,
                    input_normalized=input_normalized,
                    data=response_data,
                    summary=summary,
                    warnings=warnings,
                    memory_ref=None,
                    error=None,
                    trace_id=trace["trace_id"],
                    group_id=trace["group_id"],
                )
            except HorosaSkillError as exc:
                trace["error_code"] = exc.code
                error_details = _with_operational_recovery(exc.code, exc.details)
                envelope = ToolEnvelope(
                    ok=False,
                    tool=tool_name,
                    version=__version__,
                    input_normalized=input_normalized,
                    data={},
                    summary=[f"工具 `{tool_name}` 调用失败（{exc.code}）。"],
                    warnings=list(degrade_notes),
                    memory_ref=None,
                    error=ErrorInfo(code=exc.code, message=str(exc), details=error_details),
                    # 顶层镜像三键（见 schemas/common.py）：MCP 面的闸门/校验错误一直镜像，工具自身的
                    # 错误（runtime.not_installed / tool.ken_compute_failed / transport.*）却没有，
                    # 按顶层 `code` 读的调用方在最常见的失败上读到 None。两条路径口径必须一致。
                    code=exc.code,
                    message=str(exc),
                    details=error_details,
                    trace_id=trace["trace_id"],
                    group_id=trace["group_id"],
                )
            except Exception as exc:  # noqa: BLE001 - last-resort guard: a surface/dispatch must never crash
                # Tool execution and the snapshot/summary/export post-processing touch backend-shaped
                # data and can raise unexpected ValueError/KeyError/IndexError/TypeError. Convert those
                # into a structured ok=False envelope instead of letting a traceback escape the CLI or
                # break the MCP session / abort a whole dispatch. (Bad-payload ValidationError is handled
                # separately above and intentionally still raises.)
                trace["error_code"] = "tool.internal_error"
                envelope = ToolEnvelope(
                    ok=False,
                    tool=tool_name,
                    version=__version__,
                    input_normalized=input_normalized,
                    data={},
                    summary=[f"工具 `{tool_name}` 调用时发生内部错误。"],
                    warnings=list(degrade_notes),
                    memory_ref=None,
                    error=ErrorInfo(
                        code="tool.internal_error",
                        message=str(exc),
                        details={"exception_type": type(exc).__name__},
                    ),
                    code="tool.internal_error",
                    message=str(exc),
                    details={"exception_type": type(exc).__name__},
                    trace_id=trace["trace_id"],
                    group_id=trace["group_id"],
                )

            if save_result:
                effective_run_id = run_id or self.store.create_run(
                    entrypoint="tool",
                    query_text=query_text,
                    subject=input_normalized,
                    group_id=trace["group_id"],
                )
                self.store.record_entities(effective_run_id, _extract_entities(input_normalized, query_text))
                memory_ref = self.store.record_tool_result(
                    run_id=effective_run_id,
                    tool_name=tool_name,
                    ok=envelope.ok,
                    input_normalized=input_normalized,
                    envelope_dict=envelope.model_dump(mode="json"),
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

            # response_view 视图裁剪在存档之后：memory 保全量，返回体按需精简。
            envelope = _apply_response_view(envelope, input_normalized)
            trace["success"] = envelope.ok
            trace["input_normalized"] = input_normalized
            trace["summary"] = envelope.summary
            trace["warnings"] = envelope.warnings
            return envelope
