"""跨技法 API（DispatchAPI）：hecan 合参、决策层各面（路由 / 性别 / 占类 / 忠实度）、dispatch。"""
from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from horosa_skill import __version__
from horosa_skill.agent_guidance import build_validation_recovery
from horosa_skill.decisions.layer import decision_records
from horosa_skill.decisions.redact import build_meta_state
from horosa_skill.decisions.surfaces.extract import (
    build_gender_question,
    gender_candidates,
    resolve_gender,
)
from horosa_skill.decisions.surfaces.faithfulness import (
    build_opinion_questions,
    build_opinion_state,
    summarize_opinion,
)
from horosa_skill.decisions.surfaces.routing import (
    build_routing_questions,
    resolve_routing,
)
from horosa_skill.decisions.surfaces.zhancat import build_zhan_question, resolve_zhan
from horosa_skill.engine.registry import resolve_tool_name
from horosa_skill.engine.router import select_tools
from horosa_skill.errors import DispatchResolutionError, ToolValidationError
from horosa_skill.reports.technique_card import build_technique_report
from horosa_skill.schemas.common import DispatchEnvelope, ErrorInfo, ToolEnvelope
from horosa_skill.schemas.tools import DispatchInput, HecanInput
from horosa_skill.service._context import (
    _RUN_QUERY_TEXT,
    _degrade,
    _progress_tick,
    logger,
)
from horosa_skill.service.envelope import (
    _build_dispatch_export_contract,
    _extract_entities,
)

HECAN_SCHEMA = "horosa.skill.hecan.v1"


class DispatchAPI:
    def hecan(self, payload: dict[str, Any]) -> dict[str, Any]:
        """合参（v0.28.0 B3）：一问多技法交叉印证——全行业没有的形态，也只有 92 技法才做得起。

        传统方法论（三式互参、八字紫微互证）+ orchestrator-workers 编排：路由/显式选盘（上限
        max_tools）→ 同一 group 逐技法起盘（复用 dispatch 全部载荷管线与澄清闸）→ 产出**合参模板**：
        逐技法证据表（引用不复制全文）+ 口径一致性（复用技法卡冲突检测）+ ai_fillable 综合槽。
        两条铁律写进模板 instructions：**只准引用已导出段落的事实**；**分歧必须披露，不许平均**。
        """
        with self.tracer.span(
            workflow_name="hecan.run",
            metadata={"entrypoint": "hecan", "payload": payload},
        ) as trace:
            try:
                request = HecanInput.model_validate(payload)
            except ValidationError as exc:
                errors = exc.errors()
                raise ToolValidationError(
                    "Invalid payload for horosa_hecan.",
                    code="hecan.invalid_payload",
                    details={
                        "errors": errors,
                        "agent_recovery": build_validation_recovery(
                            operation_name="horosa_hecan", tool_name="hecan", errors=errors
                        ),
                    },
                ) from exc

            max_tools = max(1, min(int(request.max_tools or 5), 8))
            preselected = [resolve_tool_name(t) or t for t in (request.tools or []) if t][:max_tools] or None
            dispatch_payload = request.model_dump(exclude_none=True)
            dispatch_payload.pop("tools", None)
            dispatch_payload.pop("max_tools", None)
            envelope = self.dispatch(dispatch_payload, preselected_tools=preselected)
            if not envelope.ok and not envelope.results:
                # 路由失败原样透出（含 agent_recovery），不包一层假成功。
                return {
                    "ok": False,
                    "schema": HECAN_SCHEMA,
                    "question": request.query,
                    "error": envelope.error.model_dump(mode="json") if envelope.error else None,
                    "code": envelope.code,
                    "message": envelope.message,
                    "details": envelope.details,
                    "trace_id": trace["trace_id"],
                    "group_id": envelope.group_id,
                }

            selected = envelope.selected_tools[:max_tools]
            techniques: list[dict[str, Any]] = []
            cards: list[dict[str, Any]] = []
            for tool_name in selected:
                result = envelope.results.get(tool_name)
                if result is None:
                    continue
                data = result.data if isinstance(result.data, dict) else {}
                export = data.get("export_snapshot") if isinstance(data.get("export_snapshot"), dict) else {}
                card = data.get("technique_card") if isinstance(data.get("technique_card"), dict) else None
                if card:
                    cards.append(card)
                technique_info = export.get("technique") if isinstance(export.get("technique"), dict) else {}
                titles = [
                    section.get("title")
                    for section in export.get("sections", [])
                    if isinstance(section, dict) and section.get("title")
                ]
                techniques.append({
                    "tool": tool_name,
                    "ok": result.ok,
                    "technique": {"key": technique_info.get("key"), "label": technique_info.get("label")},
                    "summary": list(result.summary),
                    "section_titles": titles,
                    "sections_health": {
                        "missing_selected_sections": export.get("missing_selected_sections") or [],
                        "unknown_detected_sections": export.get("unknown_detected_sections") or [],
                    },
                    "error": result.error.model_dump(mode="json") if result.error else None,
                    # 证据指针而非全文：完整段落在 dispatch 存档里，memory_show(run_id) 可取。
                    "evidence_pointer": {
                        "run_id": envelope.memory_ref.run_id if envelope.memory_ref else None,
                        "read_with": "horosa_memory_show",
                    },
                })

            consistency = build_technique_report(
                cards=cards, scope="group", scope_id=envelope.group_id
            )["consistency"] if cards else {"setting_conflicts": [], "export_contract_unclean": [], "compute_mismatched": [], "all_clear": None}

            template = {
                "ok": True,
                "schema": HECAN_SCHEMA,
                "question": request.query,
                "selected_tools": selected,
                "techniques": techniques,
                "consistency": consistency,
                "synthesis_contract": {
                    "instructions": [
                        "先读每个技法的导出段落（memory_show 取全量），再填 cross_validation：每技法一条结论，"
                        "必须绑定该技法真实段落里的事实，不许引用未导出的内容。",
                        "convergence 只写多技法**独立**得出的共同判断；一个技法的结论不算共识。",
                        "divergence 必须逐条披露（哪两个技法、各说什么、可能因口径差异还是体系差异）——"
                        "**分歧不许平均、不许只挑一边**；无法调和就写无法调和。",
                        "consistency.setting_conflicts 非空时，先声明口径冲突再谈结论可比性。",
                        "final_answer 先直答用户问题，再给依据与边界；引用口径/教义按 SKILL.md 带出处。",
                    ],
                    "ai_fillable": {
                        "cross_validation": [
                            {"tool": t["tool"], "label": (t["technique"] or {}).get("label"), "conclusion": "", "evidence_lines": []}
                            for t in techniques
                        ],
                        "convergence": "",
                        "divergence": "",
                        "final_answer": "",
                    },
                },
                "memory_ref": envelope.memory_ref.model_dump(mode="json") if envelope.memory_ref else None,
                "summary": [
                    f"合参已起 {len(techniques)} 个技法（{('、'.join(selected))}），同组存档待综合。",
                    "这是合参模板，不是终稿：请按 synthesis_contract 填写后给出结论（分歧必须披露）。",
                ],
                "trace_id": trace["trace_id"],
                "group_id": envelope.group_id,
            }
            trace["success"] = True
            trace["selected_tools"] = selected
            return template

    # ---- 可选云端决策层（v0.39.0）：三个面的采纳逻辑都在这里，代码持有权限、模型只供证据 ----
    def _decision_layer_view(self, records: list[dict[str, Any]]) -> dict[str, Any] | None:
        layer = self.decision_layer
        if layer is None:
            return None
        return {**layer.summary(), "records": list(records)}

    @staticmethod
    def _decision_guard(surface: str, fallback: Any, fn: Any) -> Any:
        """决策层的任何异常（问题规格、解析、编排 bug）都不许拖垮技法/调度：降级可见，返回确定性结果。

        `layer.ask` 只包住 provider；问题构造与采纳逻辑在它外面——v0.39.0 开发期一次 QuestionSpecError
        曾把整个 liureng_gods 打成 tool.internal_error，正是这一层要堵的形状。
        """
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - 决策层是可选增强，失败只能降级
            logger.debug("decision surface %s failed", surface, exc_info=True)
            _degrade("决策层（%s 面）内部错误 %s，已回落确定性路径。", surface, exc.__class__.__name__)
            return fallback

    def _decide_routing(
        self,
        request: DispatchInput,
        deterministic: list[str],
        error: DispatchResolutionError | None,
    ) -> list[str]:
        return self._decision_guard("dispatch", deterministic, lambda: self._decide_routing_inner(request, deterministic, error))

    def _decide_routing_inner(
        self,
        request: DispatchInput,
        deterministic: list[str],
        error: DispatchResolutionError | None,
    ) -> list[str]:
        """S1：两级 Choice。确定性路由命中 → 只记一致性；无解且 enforce 且 conf≥τ → 采纳兜底；其余原样。"""
        layer = self.decision_layer
        if layer is None or not layer.policy.surface_enabled("dispatch"):
            return deterministic
        state, redaction = build_meta_state(request.query)
        outcome = layer.ask(
            "dispatch",
            state=state,
            questions=build_routing_questions(),
            redaction=redaction,
            intent="route a natural-language request to one technique tool",
        )
        if not outcome.ok or outcome.answers is None:
            return deterministic
        decision = resolve_routing(outcome.answers.answers, tau=outcome.tau)
        info = {**decision.as_dict(), "deterministic": list(deterministic), "agree": bool(deterministic) and decision.tool in deterministic}
        if error is None:
            layer.finalize(outcome, adopted=False, reason="deterministic router matched; recorded for shadow comparison", decision=info)
            return deterministic
        if outcome.enforced and decision.tool:
            layer.finalize(outcome, adopted=True, reason="deterministic router had no match; decision-layer fallback", decision=info)
            return [decision.tool]
        layer.finalize(outcome, adopted=False, reason=("shadow" if not outcome.enforced else decision.reason), decision=info)
        return deterministic

    @staticmethod
    def _tool_asks_gender(tool_name: str) -> bool:
        from horosa_skill.agent_guidance import TOOL_GUIDANCE

        policy = TOOL_GUIDANCE.get(tool_name) or {}
        for item in policy.get("ask_if_missing") or []:
            fields = [part.strip() for part in str((item or {}).get("field") or "").split("/")]
            if "gender" in fields:
                return True
        return False

    def _decide_gender(
        self,
        request: DispatchInput,
        tool_name: str,
        payload: dict[str, Any],
        shared: dict[str, Any],
    ) -> None:
        self._decision_guard("extract", None, lambda: self._decide_gender_inner(request, tool_name, payload, shared))

    def _decide_gender_inner(
        self,
        request: DispatchInput,
        tool_name: str,
        payload: dict[str, Any],
        shared: dict[str, Any],
    ) -> None:
        """S2：只在工具会问性别、载荷没给、原话有性别词表命中时才问一次（同一 dispatch 共享一次调用）。"""
        layer = self.decision_layer
        if layer is None or not layer.policy.surface_enabled("extract"):
            return
        if payload.get("gender") not in (None, "") or not self._tool_asks_gender(tool_name):
            return
        candidates = gender_candidates(request.query)
        if not candidates.any:
            return
        if "gender" not in shared:
            state, redaction = build_meta_state(request.query)
            shared["gender"] = layer.ask(
                "extract",
                state=state,
                questions={"subject_gender": build_gender_question()},
                redaction=redaction,
                intent="extract the chart subject's gender only when the request states it",
            )
        outcome = shared["gender"]
        if not outcome.ok or outcome.answers is None:
            return
        decision = resolve_gender(outcome.answers.answers.get("subject_gender"), candidates, tau=outcome.tau)
        info = {**decision.as_dict(), "tool": tool_name}
        if decision.value is not None and outcome.enforced:
            payload["gender"] = decision.value
            note = f"gender={decision.value}（决策层自用户原话抽取：{'/'.join(decision.evidence)}；conf {decision.confidence:.2f}）"
            existing = payload.get("clarification_notes")
            payload["clarification_notes"] = f"{existing}；{note}" if existing else note
            layer.finalize(outcome, adopted=True, reason="explicitly stated in the request (lexicon + Jev agree)", decision=info)
            return
        layer.finalize(outcome, adopted=False, reason=("shadow" if not outcome.enforced else decision.reason), decision=info)

    def faithfulness_opinion(self, report: dict[str, Any], export_text: str | None) -> dict[str, Any] | None:
        """S4（二档 snapshot 才开）：对确定性忠实性报告的每条 claim 追加只读的模型意见；不改 report 本身。"""
        return self._decision_guard("faithfulness", None, lambda: self._faithfulness_opinion_inner(report, export_text))

    def _faithfulness_opinion_inner(self, report: dict[str, Any], export_text: str | None) -> dict[str, Any] | None:
        layer = self.decision_layer
        if layer is None or not layer.policy.surface_enabled("faithfulness"):
            return None
        claims = [claim for claim in (report.get("claims") or []) if isinstance(claim, dict)]
        if not claims or not str(export_text or "").strip():
            return None
        questions = build_opinion_questions(claims)
        if not questions:
            return None
        outcome = layer.ask(
            "faithfulness",
            state=build_opinion_state(str(export_text)),
            questions=questions,
            intent="second opinion on whether each extracted claim is supported by the chart export",
        )
        if not outcome.ok or outcome.answers is None:
            return None
        summary = summarize_opinion(claims, outcome.answers.answers, tau=outcome.tau)
        layer.finalize(outcome, adopted=False, reason="read-only second opinion (never affects report.ok)", decision={"agreement_rate": summary["agreement_rate"], "n_judged": summary["n_judged"]})
        return {"provider": "typesafe_jev", "model": outcome.answers.model, "mode": outcome.mode, "tau": outcome.tau, "latency_ms": outcome.latency_ms, **summary}

    def _decide_zhan_category(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._decision_guard("zhancat", payload, lambda: self._decide_zhan_category_inner(payload))

    def _decide_zhan_category_inner(self, payload: dict[str, Any]) -> dict[str, Any]:
        """S3：六壬占断门类（闭集 + general）；分错只多一段向导、盘面不变，conf≥τ 即填。"""
        layer = self.decision_layer
        if layer is None or not layer.policy.surface_enabled("zhancat"):
            return payload
        if payload.get("zhanCategory"):
            return payload
        text = payload.get("question") or _RUN_QUERY_TEXT.get() or ""
        if not str(text).strip():
            return payload
        state, redaction = build_meta_state(str(text))
        outcome = layer.ask(
            "zhancat",
            state=state,
            questions={"zhan_category": build_zhan_question()},
            redaction=redaction,
            intent="classify the topic of a 大六壬 question",
        )
        if not outcome.ok or outcome.answers is None:
            return payload
        decision = resolve_zhan(outcome.answers.answers.get("zhan_category"), tau=outcome.tau)
        if decision.category is not None and outcome.enforced:
            layer.finalize(outcome, adopted=True, reason="topic classified above tau", decision=decision.as_dict())
            return {**payload, "zhanCategory": decision.category}
        layer.finalize(outcome, adopted=False, reason=("shadow" if not outcome.enforced else decision.reason), decision=decision.as_dict())
        return payload

    def dispatch(
        self,
        payload: dict[str, Any],
        *,
        evaluation_case_id: str | None = None,
        preselected_tools: list[str] | None = None,
    ) -> DispatchEnvelope:
        try:
            request = DispatchInput.model_validate(payload)
        except ValidationError as exc:
            errors = exc.errors()
            raise ToolValidationError(
                "Invalid payload for horosa_dispatch.",
                code="dispatch.invalid_payload",
                details={
                    "errors": errors,
                    "agent_recovery": build_validation_recovery(
                        operation_name="horosa_dispatch",
                        tool_name="dispatch",
                        errors=errors,
                    ),
                },
            ) from exc

        routing_error: DispatchResolutionError | None = None
        decision_records_out: list[dict[str, Any]] = []
        try:
            # 合参等上层可显式点名技法（跳过关键词路由）；未知名照常走 run_tool 的 tool.unknown。
            selected_tools = list(preselected_tools) if preselected_tools else select_tools(request)
        except DispatchResolutionError as exc:
            routing_error = exc
            selected_tools = []
        # 决策层 S1（可选，缺省关）：确定性路由是权威；只有它无解时才可能采纳 Jev 的兜底，命中时只记一致性。
        if self.decision_layer is not None and not preselected_tools:
            with decision_records() as routing_records:
                selected_tools = self._decide_routing(request, selected_tools, routing_error)
            decision_records_out.extend(routing_records)
            if selected_tools:
                routing_error = None
        if routing_error is not None:
            exc = routing_error
            return DispatchEnvelope(
                ok=False,
                version=__version__,
                selected_tools=[],
                normalized_inputs={},
                results={},
                summary=["未能从当前输入解析出匹配的 Horosa 工具。"],
                warnings=[],
                memory_ref=None,
                error=ErrorInfo(code=exc.code, message=str(exc), details=exc.details),
                code=exc.code,
                message=str(exc),
                details=exc.details,
                decision_layer=self._decision_layer_view(decision_records_out),
            )

        normalized_inputs: dict[str, dict[str, Any]] = {}
        results: dict[str, ToolEnvelope] = {}
        result_export_contracts: dict[str, dict[str, Any]] = {}
        dispatch_warnings: list[str] = []
        extraction_shared: dict[str, Any] = {}

        workflow_group_id = self.tracer.new_group_id()
        with self.tracer.span(
            workflow_name="dispatch.run",
            group_id=workflow_group_id,
            metadata={
                "entrypoint": "dispatch",
                "payload": request.model_dump(exclude_none=True),
                "query_text": request.query,
                "selected_tools": selected_tools,
                "evaluation_case_id": evaluation_case_id,
            },
        ) as trace:
            run_id = self.store.create_run(
                entrypoint="dispatch",
                query_text=request.query,
                subject=request.model_dump(exclude_none=True),
                group_id=trace["group_id"],
            ) if request.save_result else None

            def birth_payload() -> dict[str, Any]:
                if request.birth is not None:
                    return request.birth.model_dump(exclude_none=True)
                if request.subject and request.subject.birth is not None:
                    return request.subject.birth.model_dump(exclude_none=True)
                return {}

            base_birth = birth_payload()
            confirmation = {
                key: value
                for key, value in {
                    "agent_confirmed_settings": request.agent_confirmed_settings,
                    "defaults_accepted": request.defaults_accepted,
                    "clarification_notes": request.clarification_notes,
                    # 自备知识库点名随确认三键一起传给每个技法（各自按本技法解析 `auto`）。
                    "knowledge": request.knowledge,
                }.items()
                if value is not None
            }
            total_tools = len(selected_tools)
            for tool_index, tool_name in enumerate(selected_tools, start=1):
                _progress_tick(tool_index - 1, total_tools, f"调度：{tool_name}（{tool_index}/{total_tools}）")
                if tool_name == "relative":
                    payload_for_tool = {
                        "inner": request.subject.inner.model_dump(exclude_none=True) if request.subject and request.subject.inner else {},
                        "outer": request.subject.outer.model_dump(exclude_none=True) if request.subject and request.subject.outer else {},
                        "hsys": request.preferences.get("hsys", 1),  # 缺省随 RelativeInput（星阙 DefaultHouseSystem 1）
                        "zodiacal": request.preferences.get("zodiacal", 0),
                        "relative": request.preferences.get("relative", 0),
                    }
                elif tool_name in {"gua_desc", "gua_meiyi"}:
                    gua_names = []
                    if request.subject and request.subject.gua_names:
                        gua_names = request.subject.gua_names
                    elif "gua_names" in request.context:
                        gua_names = list(request.context["gua_names"])
                    payload_for_tool = {"name": gua_names}
                elif tool_name == "jieqi_year":
                    year = request.subject.year if request.subject and request.subject.year is not None else None
                    if year is None and base_birth.get("date"):
                        year = str(base_birth["date"])[:4]
                    jieqi_lat = base_birth.get("lat", request.context.get("lat"))
                    jieqi_lon = base_birth.get("lon", request.context.get("lon"))
                    if not jieqi_lat or not jieqi_lon:
                        # 兜底赤道/本初子午线坐标会改变节气盘宫位——显式告知而非静默。
                        dispatch_warnings.append(
                            "jieqi_year 未提供经纬度，已按 0n00/0e00 兜底起盘；宫位随地点变化，建议补充坐标后重算。"
                        )
                    payload_for_tool = {
                        "year": year,
                        "zone": base_birth.get("zone", request.context.get("zone", "8")),
                        "lat": jieqi_lat or "0n00",
                        "lon": jieqi_lon or "0e00",
                        "time": request.context.get("time"),
                    }
                else:
                    payload_for_tool = dict(base_birth)

                payload_for_tool.update(confirmation)
                # 决策层 S2（可选，缺省关）：只把原话里**明说**的性别变成「已提供」（词表 + Jev 双钥）。
                if self.decision_layer is not None:
                    with decision_records() as extract_records:
                        self._decide_gender(request, tool_name, payload_for_tool, extraction_shared)
                    decision_records_out.extend(extract_records)
                normalized_inputs[tool_name] = payload_for_tool
                try:
                    results[tool_name] = self.run_tool(
                        tool_name,
                        payload_for_tool,
                        save_result=request.save_result,
                        run_id=run_id,
                        query_text=request.query,
                        group_id=trace["group_id"],
                        evaluation_case_id=evaluation_case_id,
                    )
                except ToolValidationError as exc:
                    # 决策层兜底选中的工具随后因缺参被拒时，调用方必须能看到「这个工具是谁选的」——否则一个
                    # 无匹配请求会以「huanglizeri 缺 startDate」的面目出现，而路由这一步的自陈全丢。
                    if decision_records_out and "decision_layer" not in exc.details:
                        exc.details["decision_layer"] = self._decision_layer_view(decision_records_out)
                    raise
                result_export_contracts[tool_name] = _build_dispatch_export_contract(results[tool_name])
            _progress_tick(total_tools, total_tools, "调度：汇总结果")

            degraded_tools = [name for name, result in results.items() if result.ok and result.warnings]
            if degraded_tools:
                dispatch_warnings.append(
                    f"{len(degraded_tools)} 个工具结果带降级/缺段说明：{', '.join(degraded_tools)}"
                    "（详见 results.<tool>.warnings，报告须如实转述）。"
                )
            summary = [f"horosa_dispatch 选择了 {len(selected_tools)} 个工具：{', '.join(selected_tools)}。"]
            summary.extend([line for result in results.values() for line in result.summary[:1]])

            envelope = DispatchEnvelope(
                ok=all(result.ok for result in results.values()),
                version=__version__,
                selected_tools=selected_tools,
                normalized_inputs=normalized_inputs,
                results=results,
                result_export_contracts=result_export_contracts,
                summary=summary[:6],
                warnings=dispatch_warnings,
                memory_ref=None,
                error=None,
                trace_id=trace["trace_id"],
                group_id=trace["group_id"],
                decision_layer=self._decision_layer_view(decision_records_out),
            )

            if request.save_result and run_id is not None:
                self.store.record_entities(run_id, _extract_entities(request.model_dump(exclude_none=True), request.query))
                envelope.memory_ref = self.store.record_dispatch_result(
                    run_id=run_id,
                    payload=envelope.model_dump(mode="json"),
                    trace_id=trace["trace_id"],
                    group_id=trace["group_id"],
                )
                trace["run_id"] = run_id
                trace["artifact_path"] = envelope.memory_ref.artifact_path if envelope.memory_ref else None

            trace["success"] = envelope.ok
            return envelope
