from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from horosa_skill import __version__
from horosa_skill.config import Settings
from horosa_skill.engine.client import HorosaApiClient
from horosa_skill.engine.js_client import HorosaJsEngineClient
from horosa_skill.engine.registry import TOOL_DEFINITIONS, ToolDefinition
from horosa_skill.engine.router import select_tools
from horosa_skill.errors import DispatchResolutionError, HorosaSkillError, ToolTransportError, ToolValidationError
from horosa_skill.exports import build_export_registry, parse_export_content
from horosa_skill.memory.store import MemoryStore
from horosa_skill.schemas.common import DispatchEnvelope, ErrorInfo, ToolEnvelope
from horosa_skill.schemas.tools import DispatchInput


def _generic_summary(tool_name: str, data: dict[str, Any]) -> list[str]:
    if tool_name == "export_registry":
        count = len(data.get("techniques", []))
        summary = [f"已输出 {count} 个星阙 AI 导出 technique 的完整注册表。"]
        selected = data.get("selected_technique")
        if isinstance(selected, dict) and selected.get("label"):
            summary.append(f"当前聚焦：{selected['label']}。")
        return summary
    if tool_name == "export_parse":
        summary = ["已将星阙 AI 导出文本转换为结构化分段 JSON。"]
        detected = data.get("section_titles_detected", [])
        if detected:
            summary.append(f"识别到 {len(detected)} 个分段标题。")
        selected = data.get("selected_sections", [])
        if selected:
            summary.append(f"当前导出将保留 {len(selected)} 个目标分段。")
        return summary
    if tool_name == "qimen":
        pan = data.get("pan", {})
        summary = ["已运行本地奇门遁甲 headless 算法。"]
        if pan.get("juText"):
            summary.append(f"局数：{pan['juText']}。")
        if pan.get("zhiFu") and pan.get("zhiShi"):
            summary.append(f"值符 {pan['zhiFu']}，值使 {pan['zhiShi']}。")
        return summary
    if tool_name == "taiyi":
        pan = data.get("pan", {})
        summary = ["已运行本地太乙 headless 算法。"]
        if pan.get("zhao"):
            summary.append(f"命式：{pan['zhao']}。")
        if pan.get("kook"):
            summary.append(f"局式：{pan['kook']}。")
        return summary
    if tool_name == "jinkou":
        result = data.get("jinkou", {})
        summary = ["已运行本金口诀 headless 算法。"]
        if result.get("guiName") and result.get("jiangName"):
            summary.append(f"贵神 {result['guiName']}，将神 {result['jiangName']}。")
        if result.get("wangElem"):
            summary.append(f"旺神五行：{result['wangElem']}。")
        return summary
    lines = [f"工具 `{tool_name}` 已返回结构化结果。"]
    keys = sorted(data.keys())
    if keys:
        lines.append(f"顶层字段：{', '.join(keys[:8])}{' ...' if len(keys) > 8 else ''}")
    if "chart" in data:
        lines.append("结果包含 chart 结构。")
    if "predictives" in data:
        lines.append("结果包含 predictive / 时运相关数据。")
    if "bazi" in data:
        lines.append("结果包含八字结构。")
    if "liureng" in data:
        lines.append("结果包含六壬结构。")
    if "jieqi24" in data and isinstance(data["jieqi24"], list):
        lines.append(f"结果包含 {len(data['jieqi24'])} 个节气节点。")
    return lines[:4]


def _extract_entities(input_normalized: dict[str, Any], query_text: str | None = None) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []

    def add(display_name: str, *, entity_type: str = "subject") -> None:
        value = (display_name or "").strip()
        if not value:
            return
        entities.append(
            {
                "entity_type": entity_type,
                "entity_key": value.lower(),
                "display_name": value,
                "metadata": {},
            }
        )

    if query_text:
        add(query_text[:80], entity_type="query")

    name = input_normalized.get("name")
    if isinstance(name, str):
        add(name)

    for key in ("inner", "outer", "subject"):
        nested = input_normalized.get(key)
        if isinstance(nested, dict):
            nested_name = nested.get("name")
            if isinstance(nested_name, str):
                add(nested_name)

    return entities


class HorosaSkillService:
    def __init__(
        self,
        settings: Settings,
        client: HorosaApiClient | None = None,
        store: MemoryStore | None = None,
        js_client: HorosaJsEngineClient | None = None,
    ) -> None:
        self.settings = settings
        self.client = client or HorosaApiClient(settings.server_root)
        self.store = store or MemoryStore(settings)
        self.js_client = js_client or HorosaJsEngineClient(settings)

    def _unwrap_result(self, payload: Any) -> Any:
        current = payload
        for _ in range(4):
            if not isinstance(current, dict):
                return current
            if isinstance(current.get("Result"), dict):
                current = current["Result"]
                continue
            if isinstance(current.get("result"), dict):
                current = current["result"]
                continue
            return current
        return current

    def _call_remote(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.client.call(endpoint, payload)
        unwrapped = self._unwrap_result(data)
        if not isinstance(unwrapped, dict):
            raise ToolTransportError(
                "Horosa endpoint returned a non-object result payload.",
                code="transport.invalid_result_shape",
                details={"endpoint": endpoint},
            )
        return unwrapped

    def _augment_export_payload(self, *, technique: str, snapshot_text: str | None) -> dict[str, Any] | None:
        if not snapshot_text:
            return None
        try:
            return parse_export_content(technique=technique, content=snapshot_text)
        except ValueError:
            return None

    def _run_qimen_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        year = int(str(payload["date"])[:4])
        nongli = payload.get("nongli")
        if not isinstance(nongli, dict):
            nongli = self._call_remote(
                "/nongli/time",
                {
                    "date": payload["date"],
                    "time": payload["time"],
                    "zone": payload["zone"],
                    "lon": payload["lon"],
                    "lat": payload["lat"],
                    "gpsLat": payload.get("gpsLat"),
                    "gpsLon": payload.get("gpsLon"),
                    "after23NewDay": payload.get("after23NewDay", False),
                    "timeAlg": payload.get("timeAlg", 0),
                    "ad": payload.get("ad", 1),
                },
            )
        prev_year = payload.get("jieqi_year_prev")
        if not isinstance(prev_year, dict):
            prev_year = self._call_remote(
                "/jieqi/year",
                {
                    "year": year - 1,
                    "zone": payload["zone"],
                    "lat": payload["lat"],
                    "lon": payload["lon"],
                    "time": payload["time"],
                    "gpsLat": payload.get("gpsLat"),
                    "gpsLon": payload.get("gpsLon"),
                    "ad": payload.get("ad", 1),
                    "timeAlg": payload.get("timeAlg", 0),
                },
            )
        current_year = payload.get("jieqi_year_current")
        if not isinstance(current_year, dict):
            current_year = self._call_remote(
                "/jieqi/year",
                {
                    "year": year,
                    "zone": payload["zone"],
                    "lat": payload["lat"],
                    "lon": payload["lon"],
                    "time": payload["time"],
                    "gpsLat": payload.get("gpsLat"),
                    "gpsLon": payload.get("gpsLon"),
                    "ad": payload.get("ad", 1),
                    "timeAlg": payload.get("timeAlg", 0),
                },
            )
        js_result = self.js_client.run(
            "qimen",
            {
                **payload,
                "nongli": nongli,
                "jieqi_year_prev": prev_year,
                "jieqi_year_current": current_year,
            },
        )
        snapshot_text = js_result.get("snapshot_text")
        return {
            "pan": js_result.get("data", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="qimen", snapshot_text=snapshot_text),
            "prerequisites": {
                "nongli": nongli,
                "jieqi_year_prev": prev_year,
                "jieqi_year_current": current_year,
            },
        }

    def _run_taiyi_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        nongli = payload.get("nongli")
        if not isinstance(nongli, dict):
            nongli = self._call_remote(
                "/nongli/time",
                {
                    "date": payload["date"],
                    "time": payload["time"],
                    "zone": payload["zone"],
                    "lon": payload["lon"],
                    "lat": payload["lat"],
                    "gpsLat": payload.get("gpsLat"),
                    "gpsLon": payload.get("gpsLon"),
                    "after23NewDay": payload.get("after23NewDay", False),
                    "timeAlg": payload.get("timeAlg", 0),
                    "ad": payload.get("ad", 1),
                },
            )
        js_result = self.js_client.run("taiyi", {**payload, "nongli": nongli})
        snapshot_text = js_result.get("snapshot_text")
        return {
            "pan": js_result.get("data", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="taiyi", snapshot_text=snapshot_text),
            "prerequisites": {
                "nongli": nongli,
            },
        }

    def _run_jinkou_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        liureng = payload.get("liureng")
        if not isinstance(liureng, dict):
            remote = self._call_remote(
                "/liureng/gods",
                {
                    "date": payload["date"],
                    "time": payload["time"],
                    "zone": payload["zone"],
                    "lat": payload["lat"],
                    "lon": payload["lon"],
                    "after23NewDay": payload.get("after23NewDay", False),
                    "yue": payload.get("yue"),
                    "isDiurnal": payload.get("isDiurnal"),
                    "ad": payload.get("ad", 1),
                },
            )
            liureng = remote.get("liureng", remote)
        js_result = self.js_client.run(
            "jinkou",
            {
                **payload,
                "liureng": liureng,
            },
        )
        snapshot_text = js_result.get("snapshot_text")
        return {
            "jinkou": js_result.get("data", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="jinkou", snapshot_text=snapshot_text),
            "prerequisites": {
                "liureng": liureng,
            },
        }

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "mcp_name": tool.mcp_name,
                "execution": tool.execution,
                "endpoint": tool.endpoint,
                "description": tool.description,
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
        if definition.name == "qimen":
            return self._run_qimen_tool(payload)
        if definition.name == "taiyi":
            return self._run_taiyi_tool(payload)
        if definition.name == "jinkou":
            return self._run_jinkou_tool(payload)
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
    ) -> ToolEnvelope:
        if tool_name not in TOOL_DEFINITIONS:
            raise ToolValidationError(f"Unknown tool: {tool_name}", code="tool.unknown", details={"tool_name": tool_name})

        definition = TOOL_DEFINITIONS[tool_name]

        try:
            validated = definition.input_model.model_validate(payload)
        except ValidationError as exc:
            raise ToolValidationError(
                f"Invalid payload for tool `{tool_name}`.",
                code="tool.invalid_payload",
                details={"errors": exc.errors()},
            ) from exc

        input_normalized = validated.model_dump(exclude_none=True)
        memory_ref = None

        try:
            if definition.execution == "local":
                response_data = self._run_local_tool(definition, input_normalized)
            else:
                assert definition.endpoint is not None
                response_data = self._call_remote(definition.endpoint, input_normalized)
            summary = _generic_summary(tool_name, response_data)
            warnings: list[str] = []
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
            )
        except HorosaSkillError as exc:
            envelope = ToolEnvelope(
                ok=False,
                tool=tool_name,
                version=__version__,
                input_normalized=input_normalized,
                data={},
                summary=[f"工具 `{tool_name}` 调用失败。"],
                warnings=[],
                memory_ref=None,
                error=ErrorInfo(code=exc.code, message=str(exc), details=exc.details),
            )

        if save_result:
            effective_run_id = run_id or self.store.create_run(
                entrypoint="tool",
                query_text=query_text,
                subject=input_normalized,
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
            )
            envelope.memory_ref = memory_ref

        return envelope

    def dispatch(self, payload: dict[str, Any]) -> DispatchEnvelope:
        try:
            request = DispatchInput.model_validate(payload)
        except ValidationError as exc:
            raise ToolValidationError(
                "Invalid payload for horosa_dispatch.",
                code="dispatch.invalid_payload",
                details={"errors": exc.errors()},
            ) from exc

        try:
            selected_tools = select_tools(request)
        except DispatchResolutionError as exc:
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
            )

        normalized_inputs: dict[str, dict[str, Any]] = {}
        results: dict[str, ToolEnvelope] = {}

        run_id = self.store.create_run(
            entrypoint="dispatch",
            query_text=request.query,
            subject=request.model_dump(exclude_none=True),
        ) if request.save_result else None

        def birth_payload() -> dict[str, Any]:
            if request.birth is not None:
                return request.birth.model_dump(exclude_none=True)
            if request.subject and request.subject.birth is not None:
                return request.subject.birth.model_dump(exclude_none=True)
            return {}

        base_birth = birth_payload()
        for tool_name in selected_tools:
            if tool_name == "relative":
                payload_for_tool = {
                    "inner": request.subject.inner.model_dump(exclude_none=True) if request.subject and request.subject.inner else {},
                    "outer": request.subject.outer.model_dump(exclude_none=True) if request.subject and request.subject.outer else {},
                    "hsys": request.preferences.get("hsys", 0),
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
                payload_for_tool = {
                    "year": year,
                    "zone": base_birth.get("zone", request.context.get("zone", "8")),
                    "lat": base_birth.get("lat", request.context.get("lat", "0n00")),
                    "lon": base_birth.get("lon", request.context.get("lon", "0e00")),
                    "time": request.context.get("time"),
                }
            else:
                payload_for_tool = dict(base_birth)

            normalized_inputs[tool_name] = payload_for_tool
            results[tool_name] = self.run_tool(
                tool_name,
                payload_for_tool,
                save_result=request.save_result,
                run_id=run_id,
                query_text=request.query,
            )

        summary = [f"horosa_dispatch 选择了 {len(selected_tools)} 个工具：{', '.join(selected_tools)}。"]
        summary.extend([line for result in results.values() for line in result.summary[:1]])

        envelope = DispatchEnvelope(
            ok=all(result.ok for result in results.values()),
            version=__version__,
            selected_tools=selected_tools,
            normalized_inputs=normalized_inputs,
            results=results,
            summary=summary[:6],
            warnings=[],
            memory_ref=None,
            error=None,
        )

        if request.save_result and run_id is not None:
            self.store.record_entities(run_id, _extract_entities(request.model_dump(exclude_none=True), request.query))
            envelope.memory_ref = self.store.record_dispatch_result(run_id=run_id, payload=envelope.model_dump(mode="json"))

        return envelope
