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
    "unknown_detected_sections", "next_step",
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
# 给 AI 的协议 / 注册表 / 回显用户贴来的文本：整份不转。这是唯一一张表（v0.47.2-dev）：MCP 工具名 = `horosa_<操作>`
# （mcp_runner.UNLOCALIZED_TOOLS）、CLI 命令函数同名（cli.UNLOCALIZED_COMMANDS）、信封的 `tool` 字段也是它
# ——精简面 `horosa_tool_run(tool_name="export_parse")` 走的是同一个出口，这里按信封再拦一次。
PROTOCOL_OPERATIONS = frozenset({"agent_guidance", "export_parse", "export_registry", "knowledge_registry", "report_template"})


# 古籍转换档（上游 v3.13.1 toHantClassic / CLASSIC_SCOPE_CLASS）：玄史的「原文」区段里「范 / 里」缺省保留原字
# （姓氏范、地名范阳、里坊里）。上游按 DOM 容器划区（XuanShi{Events,Figures,Celestial,Micro,Search} 的原文 / 史书原文
# 块）；本仓玄史出的是一段快照文本，原文落在「原文：」格（详情一格一行；列表一条一行、格间「；」）。
# 区段 = 「原文：」之后到下一格标签（「；标签：」或下一行以「标签：」开头）/ 段头「[」/ 列表序号行 / 文末为止——
# 详情的原文可以是多行（玄学事件 original_text 有 2209 条带换行，上游 XuanShiEvents.js:113 的 pre-line 容器整块古籍档），
# 续行一并罩住；列表行的值在渲染时已收成一行（divination._xuanshi_brief_text）。
# 标签集 = service/text/divination 里原文之后可能出现的各格（通用 _XUANSHI_FIELD_ORDER 在原文之后的各项 + 天象族
# _xuanshi_celestial_lines 的档案格）；tests/test_sync3131_followups.py 用真库逐条核对区段 == 原文。
CLASSIC_TOOLS = frozenset({"xuanshi"})
_CLASSIC_HEAD = "原文："
_CLASSIC_NEXT_LABELS = (
    "白话", "解读", "可信度", "互见", "摘要", "正文", "说明", "注",
    "出处", "原历日", "纪年", "主体", "动作", "对象", "公历", "儒略历", "主题",
)
_CLASSIC_LINE_STOPS = tuple(f"{label}：" for label in _CLASSIC_NEXT_LABELS) + ("[",)


def _classic_cut(text: str, start: int, end: int) -> int:
    for label in _CLASSIC_NEXT_LABELS:
        cut = text.find(f"；{label}：", start, end)
        if cut >= 0:
            end = cut
    return end


def _classic_boundary(line: str) -> bool:
    if line.startswith(_CLASSIC_LINE_STOPS):
        return True
    digits = len(line) - len(line.lstrip("0123456789"))
    return 0 < digits and line[digits:digits + 2] == ". "  # 列表下一条「12. …」


def classic_spans(text: str) -> tuple[tuple[int, int], ...]:
    spans: list[tuple[int, int]] = []
    at = text.find(_CLASSIC_HEAD)
    while at >= 0:
        start = at + len(_CLASSIC_HEAD)
        line_end = text.find("\n", start)
        line_end = len(text) if line_end < 0 else line_end
        end = _classic_cut(text, start, line_end)
        while end == line_end and line_end < len(text):  # 本行没被下一格截断 → 看续行
            nxt = line_end + 1
            nxt_end = text.find("\n", nxt)
            nxt_end = len(text) if nxt_end < 0 else nxt_end
            if _classic_boundary(text[nxt:nxt_end]):
                break
            line_end = nxt_end
            end = _classic_cut(text, nxt, nxt_end)
        while end > start and text[end - 1] in "\n \t":
            end -= 1
        spans.append((start, end))
        at = text.find(_CLASSIC_HEAD, max(end, start))
    return tuple(spans)


def _text(value: Any, script: str, classic: bool = False) -> Any:
    if isinstance(value, str):
        return convert(value, script, classic_spans(value) if classic else ())
    if isinstance(value, list):
        return [_text(item, script, classic) if isinstance(item, (str, list)) else _walk(item, script, classic) for item in value]
    return _walk(value, script, classic)


def _walk(value: Any, script: str, classic: bool = False) -> Any:
    if isinstance(value, list):
        return [_walk(item, script, classic) for item in value]
    if not isinstance(value, dict):
        return value
    if value.get("tool") in PROTOCOL_OPERATIONS and "input_normalized" in value:
        return value
    classic = classic or value.get("tool") in CLASSIC_TOOLS
    out: dict[str, Any] = {}
    for key, item in value.items():
        if key in SKIP_KEYS:
            out[key] = item
        elif key == "data" and isinstance(item, dict) and value.get("tool") in DATA_TEXT_TOOLS:
            out[key] = _walk(item, script, classic)
        elif key == "data" and isinstance(item, dict):
            out[key] = {k: (_walk({k: v}, script, classic)[k] if k in DATA_KEYS else v) for k, v in item.items()}
        elif key == "details" and isinstance(item, dict):
            out[key] = _details(item, script)
        elif key == "technique" and isinstance(item, dict) and "preset_sections" in item:
            out[key] = item  # export_snapshot.technique = 导出注册表条目（段名是设置键），不是给人读的
        elif key in TEXT_KEYS:
            out[key] = _text(item, script, classic)
        else:
            out[key] = _walk(item, script, classic)
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
    # 地名检索（v0.48.0）：城市库里的上级地区名与 name 一样是数据——原样回送 place 时要能对上库里的写法。
    "region",
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
    if value.get("tool") in PROTOCOL_OPERATIONS and "input_normalized" in value:
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
