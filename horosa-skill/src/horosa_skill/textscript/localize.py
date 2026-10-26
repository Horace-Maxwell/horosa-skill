"""把一份要交出去的结果转成繁体：只转**给人读的字段**，机器字段一个字不动。

为什么不整份转：结果里有大量会被 AI 原样送回下一次调用的中文值——回显的入参（`input_normalized`）、
引擎原始数据（`data` 下的宫名、卦名、星名）、设置值（技法卡 `settings.*.value`）、选项清单、错误码。
这些一旦变成繁体，AI 照抄回来就对不上简体的注册表与引擎。所以规则是**白名单**：

- 任意层：`summary` `warnings` `message` `prompt_to_user` `title` `label` `notes` `body` `snippet`
  `rendered_text` `export_text` `snapshot_text` `citation` `tips` `lines`，以及段名清单
  （`titles` `section_titles` `selected_sections` `section_titles_detected` `missing_selected_sections`
  `unknown_detected_sections`）。
- 不进入的子树：回显的入参、`details`（只转其中的 `agent_recovery.prompt_to_user`）、给 AI 的协议
  （选项 / 契约 / 报告模板 / 合参契约）、`settings_used` 与 `technique`（导出注册表）、`provenance`。
- `data` 只进三处：`export_snapshot`、`snapshot_text`、`technique_card`；其余引擎原始数据保持简体。

转换在**进程出口**做（MCP 返回、CLI 打印、报告落盘），存档与内部逻辑永远是简体原文。
"""
from __future__ import annotations

from typing import Any

from horosa_skill.textscript import SIMPLIFIED, convert

TEXT_KEYS = frozenset({
    "summary", "warnings", "message", "prompt_to_user", "title", "label", "notes", "body", "snippet",
    "rendered_text", "export_text", "snapshot_text", "citation", "tips", "lines", "raw_title", "text",
    "titles", "section_titles", "selected_sections", "section_titles_detected", "missing_selected_sections",
    "unknown_detected_sections",
})
SKIP_KEYS = frozenset({
    "input_normalized", "normalized_inputs", "input", "subject", "payload", "query_normalized",
    "settings_used", "technique_registry", "provenance", "options", "choices", "accepted_forms", "fix_fields",
    "example_payload", "required", "output_contract", "input_contract", "report_template", "synthesis_contract",
    "ai_instructions", "conversation_brief", "question_analysis", "required_sections", "server_profile",
    "agent_guidance", "ai_process", "schema", "code", "tool", "tool_name", "key", "value", "version", "versions",
})
DATA_KEYS = frozenset({"export_snapshot", "snapshot_text", "technique_card"})
# 正文直接放在 `data` 里（没有导出快照）的工具：整份 data 按同一套键规则走。
DATA_TEXT_TOOLS = frozenset({"knowledge_read"})
# 给 AI 的协议 / 注册表 / 回显用户贴来的文本：整份信封不转。MCP 名单在 surfaces/mcp_runner.UNLOCALIZED_TOOLS，
# 这里按信封的 `tool` 字段再拦一次——精简面 `horosa_tool_run(tool_name="export_parse")` 走的是同一个出口。
PROTOCOL_TOOLS = frozenset({"export_parse", "export_registry", "knowledge_registry"})


def _text(value: Any, script: str) -> Any:
    if isinstance(value, str):
        return convert(value, script)
    if isinstance(value, list):
        return [_text(item, script) if isinstance(item, (str, list)) else _walk(item, script) for item in value]
    return _walk(value, script)


def _walk(value: Any, script: str) -> Any:
    if isinstance(value, list):
        return [_walk(item, script) for item in value]
    if not isinstance(value, dict):
        return value
    if value.get("tool") in PROTOCOL_TOOLS and "input_normalized" in value:
        return value
    out: dict[str, Any] = {}
    for key, item in value.items():
        if key in SKIP_KEYS:
            out[key] = item
        elif key == "data" and isinstance(item, dict) and value.get("tool") in DATA_TEXT_TOOLS:
            out[key] = _walk(item, script)
        elif key == "data" and isinstance(item, dict):
            out[key] = {k: (_walk({k: v}, script)[k] if k in DATA_KEYS else v) for k, v in item.items()}
        elif key == "details" and isinstance(item, dict):
            out[key] = _details(item, script)
        elif key == "technique" and isinstance(item, dict) and "preset_sections" in item:
            out[key] = item  # export_snapshot.technique = 导出注册表条目（段名是设置键），不是给人读的
        elif key in TEXT_KEYS:
            out[key] = _text(item, script)
        else:
            out[key] = _walk(item, script)
    return out


def _details(details: dict[str, Any], script: str) -> dict[str, Any]:
    out = dict(details)
    recovery = details.get("agent_recovery")
    if isinstance(recovery, dict) and isinstance(recovery.get("prompt_to_user"), str):
        out["agent_recovery"] = {**recovery, "prompt_to_user": convert(recovery["prompt_to_user"], script)}
    return out


def _mark(value: Any, script: str) -> Any:
    """在每份导出快照上注明「这是从简体机器转换的」——引用原文、排查用词时要知道。"""
    if isinstance(value, dict):
        snapshot = (value.get("data") or {}).get("export_snapshot") if isinstance(value.get("data"), dict) else None
        if isinstance(snapshot, dict):
            snapshot["output_script"] = script
        for item in value.values():
            _mark(item, script)
    elif isinstance(value, list):
        for item in value:
            _mark(item, script)
    return value


def localize(value: Any, script: str) -> Any:
    """返回转换后的**新**对象（简体时原样返回同一个对象，零拷贝）。pydantic 模型转完按原类型重建。"""
    if script == SIMPLIFIED or value is None:
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        converted = _mark(_walk(dump(mode="json"), script), script)
        return type(value).model_validate(converted)
    return _mark(_walk(value, script), script)


def localize_document(document: Any, script: str) -> Any:
    """报告文档是给人读的整份文本：除机器字段外的字符串都转。"""
    if script == SIMPLIFIED:
        return document
    return _document(document, script)


_DOCUMENT_MACHINE_KEYS = frozenset({
    "schema", "run_id", "scope_id", "tool", "tool_name", "key", "format", "artifact_path", "path", "sha256",
    "generated_at", "created_at", "language", "trace_id", "group_id", "versions", "version", "input_normalized",
    "raw_json", "raw", "data", "payload", "declared_engines", "declared_endpoints", "measured", "value",
    "declared_class", "matches_declaration", "format_source",
    # 盘图规格（reports/figures.py）的位置 / 类型键：渲染器按简体地支、卦名定格，转了就对不上格位。
    "branch", "gua", "kind", "emphasis", "cell_style", "layout",
})


def _document(value: Any, script: str) -> Any:
    if isinstance(value, str):
        return convert(value, script)
    if isinstance(value, list):
        return [_document(item, script) for item in value]
    if isinstance(value, dict):
        return {k: (v if k in _DOCUMENT_MACHINE_KEYS else _document(v, script)) for k, v in value.items()}
    return value


# 有意保持原文的键（不是给人读的正文，或要原样送回）。和 TEXT_KEYS / SKIP_KEYS 一起构成**完整分类**：
# 结果里出现中文字符串、而它的键三处都不在 → `unclassified_text_paths` 报出来，测试红，逼新字段先归类。
KEEP_KEYS = frozenset({
    "question", "query", "user_question", "raw_question", "query_text", "clarification_notes", "ai_answer_text",
    "category", "domain", "name", "mode", "scope", "technique_label", "source", "format_source", "entrypoint",
    "path", "artifact_path", "role",
})


def unclassified_text_paths(value: Any, path: str = "$") -> list[str]:
    """列出没被归类的中文字符串路径（既不转、也没声明保持原文）。新加的输出字段必须进三张表之一。"""
    found: list[str] = []
    if isinstance(value, list):
        for index, item in enumerate(value):
            found += unclassified_text_paths(item, f"{path}[{index}]")
        return found
    if isinstance(value, str):
        return [path] if any("㐀" <= ch <= "鿿" for ch in value) else []
    if not isinstance(value, dict):
        return found
    if value.get("tool") in PROTOCOL_TOOLS and "input_normalized" in value:
        return found
    for key, item in value.items():
        child = f"{path}.{key}"
        if key in SKIP_KEYS or key in KEEP_KEYS or key in TEXT_KEYS:
            continue
        if key == "details" or (key == "technique" and isinstance(item, dict) and "preset_sections" in item):
            continue
        if key == "data" and isinstance(item, dict) and value.get("tool") in DATA_TEXT_TOOLS:
            found += unclassified_text_paths(item, child)
            continue
        if key == "data" and isinstance(item, dict):
            for data_key, data_value in item.items():
                if data_key in DATA_KEYS and data_key != "snapshot_text":
                    found += unclassified_text_paths(data_value, f"{child}.{data_key}")
            continue
        found += unclassified_text_paths(item, child)
    return found
