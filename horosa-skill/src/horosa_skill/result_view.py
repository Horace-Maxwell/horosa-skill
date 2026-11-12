"""结果的阅读视图与模型预算（v0.50.0-dev）：一次 MCP 工具调用交给模型读的，是这一盘的正文，不是引擎的原始树。

为什么有这一层：v0.49.0 的 MCP 结果是「正文两遍（snapshot_text + export_text）+ 分段正文一遍 + 整棵原始引擎树」，
114 个技法的中位数约 17 万字符，72 个超过 Claude Code 的 5 万字符落盘线（超了客户端把结果写进文件，模型只看到一句
提示），调度两个技法是 290 万字符。模型要读的只有正文那几千字。

四种视图（调用参数 `response_view`）：
- ``reading``（MCP 缺省）：正文一遍（`data.export_snapshot.export_text`）+ 段索引 + 技法依据卡 + 存档引用；原始树不带。
- ``sections``：正文按段给（`data.export_snapshot.sections[].body`），不带 `export_text`。
- ``titles``：只给段索引（序号、标题、字数）。
- ``full``（别名 ``raw``）：完整结果，原始树都在；只受线上体积预算管（与 v0.49.0 的缺省相同）。

正文超过模型预算时按段裁：整段整段地给，放不下的段标成未给，剩下的额度给第一个未给的段的开头（按行截断）；
`warnings` 写明哪几段没给、下一次调用怎么写（`response_sections` 选段、`response_offset` 续读）。

纯函数、不碰 I/O：入参是工具的原始返回值（pydantic 信封或 dict），出参是 dict。CLI 不经过这里，存档也不经过这里。
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from horosa_skill.errors import bilingual
from horosa_skill.textscript import fold_to_simplified

READING = "reading"
SECTIONS = "sections"
TITLES = "titles"
FULL = "full"
VIEWS: tuple[str, ...] = (READING, SECTIONS, TITLES, FULL)
VIEW_ALIASES: dict[str, str] = {"raw": FULL}

# 只管返回体形状的调用参数：MCP 面在进工具之前取走，服务层与存档都见不到它们。
VIEW_KNOBS: tuple[str, ...] = ("response_view", "response_sections", "response_offset", "response_tool")
# 参数可能嵌在哪一层：顶层、整包载荷 `request`、horosa_tool_run / report_from_tool 的 `payload`。
_KNOB_CARRIERS: tuple[str, ...] = ("request", "payload")

# 调用方写的自由文本：会被回显（input_normalized、技法卡、存档），过长就截断。值 = 上限字符数。
FREE_TEXT_LIMITS: dict[str, int] = {"clarification_notes": 2_000, "query": 4_000, "question": 4_000}

HECAN_SCHEMA = "horosa.skill.hecan.v1"
# summary 里列原始字段名的那一行（service/envelope._generic_summary）：阅读视图不带原始字段，这一行跟着去掉。
RAW_FIELDS_SUMMARY_PREFIX = "顶层字段："

# 阅读视图里 `data` 下原样保留的键：给模型读的、或指向文件 / 来源的。
_KEPT_DATA_KEYS = frozenset({"technique_card", "compute_sources", "route", "knowledge_context", "file", "files", "condition_echo"})
# 其余键：序列化后不超过这个长度的小值留着（命中数、是否截断、性别……），更大的算原始明细。
_SMALL_VALUE_CHARS = 300
# 预算留的余量：繁体转换、告警文字的长度浮动。
_BUDGET_MARGIN = 0.04
# 剩余额度至少够这么多字符才值得给半段。
_MIN_PARTIAL_CHARS = 600
_PLACEHOLDER = "omitted_for_model_budget"
# 通用裁剪不动的顶层键：模型要知道发生了什么、下一步怎么做。
_GENERIC_PROTECTED = frozenset({"ok", "warnings", "summary", "memory_ref", "error", "code", "message", "schema", "tool"})
# 任何一层都不拿的键：已经按预算放好的正文与依据卡（兜底只该拿别的东西）。
_KEEP_EVERYWHERE = frozenset({"export_snapshot", "technique_card", "response_view"})


@dataclass(frozen=True)
class Budget:
    """一次结果给模型的上限：估算 token 数与字符数，两条都要守。"""

    max_tokens: int
    max_chars: int

    def fraction(self, chars: float, tokens: float) -> float:
        return max(chars / self.max_chars, tokens / self.max_tokens)

    def text_fraction(self, text: str) -> float:
        return self.fraction(*text_cost(text))

    def value_fraction(self, value: Any) -> float:
        return self.text_fraction(compact_json(value))


@dataclass(frozen=True)
class ViewRequest:
    view: str = READING
    sections: tuple[Any, ...] = ()
    offset: int = 0
    tool: str | None = None
    notes: tuple[str, ...] = ()


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def text_cost(text: str) -> tuple[int, float]:
    """(字符数, 估算 token 数)。估算偏保守：非 ASCII（汉字、全角标点、制表符号）每字 1.5，ASCII 每 3 字符 1。

    不调分词器：每次工具调用都要走这条路，而且客户端各用各的分词器。宁可估多，不许估少。"""
    chars = len(text)
    non_ascii = chars - len(text.encode("ascii", "ignore"))
    return chars, non_ascii * 1.5 + (chars - non_ascii) / 3


def estimate_tokens(text: str) -> int:
    return math.ceil(text_cost(text)[1])


def _json_text(text: str) -> str:
    """字符串放进 JSON 之后的样子（换行、引号要转义），量预算按这个量。"""
    return json.dumps(text, ensure_ascii=False)[1:-1]


def normalize_view(value: Any) -> str | None:
    name = str(value or "").strip().lower()
    name = VIEW_ALIASES.get(name, name)
    return name if name in VIEWS else None


# ---------------------------------------------------------------------------------------------------------------------
# 调用参数


def _carried(arguments: dict[str, Any], carrier: str, keys: tuple[str, ...]) -> Mapping[str, Any] | None:
    """`request` / `payload` 里的那一层（JSON 字符串也认）；不含任何 keys 时返回 None。"""
    inner = arguments.get(carrier)
    if isinstance(inner, str) and any(key in inner for key in keys):
        try:
            inner = json.loads(inner)
        except ValueError:
            return None
    if isinstance(inner, Mapping) and any(key in inner for key in keys):
        return inner
    return None


def take_view_request(arguments: Any, *, default_view: str) -> tuple[Any, ViewRequest]:
    """从调用参数里取走视图参数。返回（去掉这些键的参数，视图请求）；入参不改。

    顶层优先，其次 `request` / `payload` 里的同名键。认不出的值不报错：按缺省视图返回，warnings 里说明可用的取值。"""
    if not isinstance(arguments, Mapping):
        return arguments, ViewRequest(view=default_view)
    cleaned: dict[str, Any] = dict(arguments)
    found: dict[str, Any] = {}
    for carrier in _KNOB_CARRIERS:
        inner = _carried(cleaned, carrier, VIEW_KNOBS)
        if inner is not None:
            cleaned[carrier] = {key: value for key, value in inner.items() if key not in VIEW_KNOBS}
            for knob in VIEW_KNOBS:
                if knob in inner:
                    found.setdefault(knob, inner[knob])
    for knob in VIEW_KNOBS:
        if knob in cleaned:
            found[knob] = cleaned.pop(knob)
    if not found:
        return arguments, ViewRequest(view=default_view)

    notes: list[str] = []
    view = default_view
    if found.get("response_view") not in (None, ""):
        named = normalize_view(found["response_view"])
        if named is None:
            notes.append(bilingual(
                f"response_view={found['response_view']!r} 不认识，已按 {default_view} 返回；可用：reading / sections / titles / full。",
                f"unknown response_view; returned as {default_view}. Valid: reading / sections / titles / full.",
            ))
        else:
            view = named
    offset = 0
    if found.get("response_offset") not in (None, ""):
        try:
            offset = max(0, int(found["response_offset"]))
        except (TypeError, ValueError):
            notes.append(bilingual(
                "response_offset 要给非负整数（段内字符位置），这次没有生效。",
                "response_offset must be a non-negative integer (character position inside a section); ignored.",
            ))
    tool = str(found["response_tool"]).strip() if found.get("response_tool") not in (None, "") else None
    return cleaned, ViewRequest(
        view=view, sections=_selection(found.get("response_sections")), offset=offset, tool=tool, notes=tuple(notes),
    )


def _selection(value: Any) -> tuple[Any, ...]:
    """`response_sections`：序号或标题的列表；也接受单个值、逗号分隔的字符串、JSON 数组字符串。"""
    if value in (None, "", []):
        return ()
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("["):
            try:
                value = json.loads(text)
            except ValueError:
                value = [text]
        else:
            value = [part.strip() for part in text.replace("，", ",").replace("、", ",").split(",") if part.strip()]
    if not isinstance(value, (list, tuple)):
        value = [value]
    picked: list[Any] = []
    for item in value:
        if isinstance(item, bool):
            continue
        if isinstance(item, int):
            picked.append(item)
        elif isinstance(item, float) and item.is_integer():
            picked.append(int(item))
        elif isinstance(item, str) and item.strip():
            text = item.strip()
            picked.append(int(text) if text.isdigit() else text)
    return tuple(picked)


def cap_free_text(arguments: Any) -> tuple[Any, list[str]]:
    """把过长的自由文本截到上限（顶层与 `request` / `payload` 里一层）。返回（新参数，说明）；入参不改。

    这些字段会被原样回显进 input_normalized、技法卡与存档：3 MB 的澄清备注曾让一次八字结果变成 6 MB。"""
    if not isinstance(arguments, Mapping):
        return arguments, []
    notes: list[str] = []

    def cap(holder: Mapping[str, Any], where: str) -> dict[str, Any] | None:
        changed: dict[str, Any] | None = None
        for key, limit in FREE_TEXT_LIMITS.items():
            value = holder.get(key)
            if isinstance(value, str) and len(value) > limit:
                changed = dict(holder) if changed is None else changed
                changed[key] = value[:limit]
                notes.append(bilingual(
                    f"{where}{key} 有 {len(value)} 字，超过上限 {limit}，只保留了前 {limit} 字。",
                    f"{where}{key} is {len(value)} characters, over the {limit} limit; only the first {limit} were kept.",
                ))
        return changed

    result: dict[str, Any] | None = cap(arguments, "")
    for carrier in _KNOB_CARRIERS:
        inner = _carried(dict(arguments), carrier, tuple(FREE_TEXT_LIMITS))
        capped = cap(inner, f"{carrier}.") if inner is not None else None
        if capped is not None:
            result = dict(arguments) if result is None else result
            result[carrier] = capped
    return (arguments if result is None else result), notes


# ---------------------------------------------------------------------------------------------------------------------
# 一份技法结果的正文槽：先定骨架（不含正文），再按分到的额度把正文放进去。


@dataclass
class _TextSlot:
    snapshot: dict[str, Any]            # 输出里的 data.export_snapshot（就地写）
    target: list[str]                   # 这个槽的告警写到哪（技法信封的 warnings，或存档读回的顶层 warnings）
    sections: list[dict[str, Any]]      # 完整的段：index / title / body
    verbatim: str | None                # 原结果的 export_text（整篇都给时逐字用它）
    view: str
    tool: str
    run_id: str | None
    chosen: list[int]                   # 要给的段在 sections 里的位置（按原顺序）
    offset: int                         # 第一个要给的段从第几个字符起
    explicit: bool                      # 调用方点名了段 / 给了续读位置
    own: list[str] = field(default_factory=list)
    demand: float = 0.0

    def measure(self, budget: Budget) -> None:
        self.demand = sum(budget.text_fraction(_json_text(self._piece(pos, self._start(n, pos))))
                          for n, pos in enumerate(self.chosen))

    def _start(self, n: int, pos: int) -> int:
        return min(self.offset, len(self.sections[pos]["body"])) if n == 0 else 0

    def _piece(self, pos: int, start: int) -> str:
        section = self.sections[pos]
        return f"[{section['title']}]\n{section['body'][start:]}\n\n"

    def render(self, allowance: float, budget: Budget) -> None:
        """按额度放正文：整段优先、按原顺序；放不下的段先跳过，剩下的额度给第一个被跳过的段的开头。"""
        shown: dict[int, tuple[int, int]] = {}
        skipped: list[int] = []
        remaining = allowance + 1e-9
        for n, pos in enumerate(self.chosen):
            start = self._start(n, pos)
            cost = budget.text_fraction(_json_text(self._piece(pos, start)))
            if cost <= remaining:
                shown[pos] = (start, len(self.sections[pos]["body"]))
                remaining -= cost
            else:
                skipped.append(pos)
        partial: int | None = None
        if skipped:
            pos = skipped[0]
            start = self._start(self.chosen.index(pos), pos)
            end = self._cut(budget, pos, start, remaining)
            if end > start:
                shown[pos] = (start, end)
                partial = pos
        self._write(shown, skipped, partial)

    def _cut(self, budget: Budget, pos: int, start: int, remaining: float) -> int:
        """这一段从 start 起在额度内能给到哪（按行截断；第一行就放不下时按字符截）。"""
        body = self.sections[pos]["body"]
        room = remaining - budget.text_fraction(_json_text(f"[{self.sections[pos]['title']}]\n")) - budget.fraction(120, 180)
        if room * budget.max_chars < _MIN_PARTIAL_CHARS:
            return start
        end = start
        for line in body[start:].splitlines(keepends=True):
            cost = budget.text_fraction(_json_text(line))
            if cost > room:
                break
            room -= cost
            end += len(line)
        if end == start:
            # 一整段只有一行（长表）：按字符截，每字符按最贵的算，保证不超。
            per_char = max(2 / budget.max_chars, 1.5 / budget.max_tokens)
            end = start + int(room / per_char)
        return min(end, len(body))

    def _write(self, shown: dict[int, tuple[int, int]], skipped: list[int], partial: int | None) -> None:
        sections = self.sections
        whole = not self.explicit and not skipped and len(shown) == len(sections) and all(
            shown[pos] == (0, len(section["body"])) for pos, section in enumerate(sections)
        )
        index: list[dict[str, Any]] = []
        for pos, section in enumerate(sections):
            row: dict[str, Any] = {"index": section["index"], "title": section["title"], "chars": len(section["body"])}
            span = shown.get(pos)
            if not whole:
                if span is None:
                    row["shown"] = "none"
                elif span == (0, len(section["body"])):
                    row["shown"] = "full"
                else:
                    row["shown"] = "partial"
                    row["from"] = span[0]
                    row["to"] = span[1]
            if self.view == SECTIONS and span is not None:
                row["body"] = section["body"][span[0]:span[1]]
            index.append(row)
        self.snapshot["sections"] = index
        if self.view == READING:
            if whole and self.verbatim is not None:
                self.snapshot["export_text"] = self.verbatim
            else:
                parts: list[str] = []
                for pos in sorted(shown):
                    start, end = shown[pos]
                    section = sections[pos]
                    text = f"[{section['title']}]\n{section['body'][start:end]}"
                    if end < len(section["body"]):
                        text = text.rstrip("\n") + f"\n…（本段未完：给到第 {end} 字，共 {len(section['body'])} 字）"
                    parts.append(text)
                self.snapshot["export_text"] = "\n\n".join(parts)
        self.own = [self._cut_note(shown, skipped, partial)] if skipped else []

    def _cut_note(self, shown: dict[int, tuple[int, int]], skipped: list[int], partial: int | None) -> str:
        sections = self.sections
        rest = [sections[pos]["index"] for pos in skipped]
        offset = shown[partial][1] if partial is not None else 0
        follow = self.follow_up(rest, offset)
        complete = len([pos for pos in shown if pos != partial])
        if partial is not None:
            zh_cut = f"；第 {sections[partial]['index']} 段只给到第 {offset} 字"
            en_cut = f"; section {sections[partial]['index']} stops at character {offset}"
        else:
            zh_cut = en_cut = ""
        return bilingual(
            f"`{self.tool}` 正文超过单次返回的模型预算：要给的 {len(self.chosen)} 段里完整给了 {complete} 段{zh_cut}。"
            f"没给完的段：{rest}。接着读：{follow}",
            f"`{self.tool}` reader text exceeds the per-result model budget: {complete} of {len(self.chosen)} sections "
            f"shown in full{en_cut}. Not finished: {rest}. Continue with: {follow}",
        )

    def follow_up(self, section_indexes: list[Any], offset: int) -> str:
        """取其余正文的那一次调用，写成可以照抄的样子。"""
        picks = f"response_sections={json.dumps(section_indexes)}"
        if offset:
            picks += f", response_offset={offset}"
        if self.run_id:
            return f'horosa_memory_show(run_id="{self.run_id}", response_tool="{self.tool}", {picks})'
        return f"the same `{self.tool}` call + {picks}"


def _match_sections(sections: list[dict[str, Any]], wanted: tuple[Any, ...]) -> tuple[list[int], list[Any]]:
    """把调用方点的序号 / 标题对到段的位置上（繁体标题折回简体再比）。返回（位置，没对上的）。"""
    positions: list[int] = []
    unknown: list[Any] = []
    for item in wanted:
        hit: int | None
        if isinstance(item, int):
            hit = next((pos for pos, section in enumerate(sections) if section["index"] == item), None)
        else:
            text = fold_to_simplified(str(item).strip().strip("[]【】"))
            hit = next((pos for pos, section in enumerate(sections) if section["title"] == text), None)
            if hit is None and text:
                hit = next((pos for pos, section in enumerate(sections) if text in section["title"]), None)
        if hit is None:
            unknown.append(item)
        elif hit not in positions:
            positions.append(hit)
    return sorted(positions), unknown


def _is_envelope(value: Any) -> bool:
    return isinstance(value, dict) and isinstance(value.get("tool"), str) and isinstance(value.get("data"), dict) and "ok" in value


def _run_id(value: Mapping[str, Any]) -> str | None:
    ref = value.get("memory_ref")
    run_id = ref.get("run_id") if isinstance(ref, Mapping) else None
    return str(run_id) if run_id else None


def _full_hint(run_id: str | None, tool: str) -> str:
    if run_id:
        return f'horosa_memory_show(run_id="{run_id}", response_tool="{tool}", response_view="full")'
    return 'the same call + response_view="full"'


def _plan_envelope(
    envelope: dict[str, Any], request: ViewRequest, *, run_id: str | None = None, target: list[str] | None = None,
) -> tuple[dict[str, Any], _TextSlot | None]:
    """把一份技法信封变成阅读骨架（不含正文）+ 正文槽。失败的信封、没有导出快照的信封原样返回（没有正文槽）。"""
    data = envelope.get("data")
    snapshot = data.get("export_snapshot") if isinstance(data, dict) else None
    if not envelope.get("ok") or not isinstance(snapshot, dict):
        return envelope, None
    tool = str(envelope.get("tool") or "")
    run_id = _run_id(envelope) or run_id
    sections = [
        {"index": row.get("index", pos + 1), "title": str(row.get("title") or ""), "body": str(row.get("body") or "")}
        for pos, row in enumerate(snapshot.get("sections") or []) if isinstance(row, dict)
    ]
    verbatim = snapshot.get("export_text") if isinstance(snapshot.get("export_text"), str) else None
    if not sections:
        # 快照没分出段（解析不了的正文）：整篇当一段，照样能按预算裁、能续读。
        whole = verbatim if verbatim else str(data.get("snapshot_text") or "")
        if whole:
            label = (snapshot.get("technique") or {}).get("label") if isinstance(snapshot.get("technique"), dict) else None
            sections = [{"index": 1, "title": str(label or tool), "body": whole}]
            verbatim = None

    slim: dict[str, Any] = {}
    technique = snapshot.get("technique")
    if isinstance(technique, dict):
        slim["technique"] = {key: technique[key] for key in ("key", "label") if key in technique}
    if request.view == READING:
        slim["export_text"] = ""
    slim["sections"] = []
    for key in ("missing_selected_sections", "unknown_detected_sections", "citation", "output_script"):
        if snapshot.get(key):
            slim[key] = snapshot[key]

    shaped: dict[str, Any] = {}
    omitted: list[str] = []
    for key, value in data.items():
        if key == "export_snapshot":
            shaped[key] = slim
        elif key == "snapshot_text":
            continue    # 与 export_text 是同一篇正文
        elif key in _KEPT_DATA_KEYS or not isinstance(value, (dict, list, str)) or len(compact_json(value)) <= _SMALL_VALUE_CHARS:
            shaped[key] = value
        else:
            omitted.append(key)
    shaped["response_view"] = {"view": request.view, "raw_fields_omitted": omitted, "full": _full_hint(run_id, tool)}
    warnings = list(envelope.get("warnings") or [])
    result = {
        **envelope,
        "data": shaped,
        "summary": [line for line in envelope.get("summary") or []
                    if not (isinstance(line, str) and line.startswith(RAW_FIELDS_SUMMARY_PREFIX))],
        "warnings": warnings,
    }
    card = shaped.get("technique_card")
    echoed = ((card or {}).get("gate") or {}).get("clarification_notes") if isinstance(card, dict) else None
    inputs = envelope.get("input_normalized")
    if isinstance(echoed, dict) and isinstance(inputs, dict) and inputs.get("clarification_notes") == echoed.get("value"):
        # 澄清备注只回显一次：技法卡的闸门记录里已经有了。
        result["input_normalized"] = {key: value for key, value in inputs.items() if key != "clarification_notes"}

    if request.view == TITLES or not sections:
        slim["sections"] = [{"index": s["index"], "title": s["title"], "chars": len(s["body"])} for s in sections]
        if request.view == TITLES:
            slim.pop("export_text", None)
        return result, None
    chosen = list(range(len(sections)))
    explicit = False
    offset = 0
    if request.sections:
        chosen, unknown = _match_sections(sections, request.sections)
        explicit = True
        offset = request.offset if chosen else 0
        if unknown:
            warnings.append(bilingual(
                f"`{tool}` 没有这些段：{unknown}；可选的序号见 data.export_snapshot.sections。",
                f"`{tool}` has no such sections: {unknown}; valid indexes are in data.export_snapshot.sections.",
            ))
    elif request.offset:
        offset = request.offset
        explicit = True
        chosen = [0]
    slot = _TextSlot(
        snapshot=slim, target=warnings if target is None else target, sections=sections, verbatim=verbatim,
        view=request.view, tool=tool, run_id=run_id, chosen=chosen, offset=offset, explicit=explicit,
    )
    return result, slot


def _fill(result: dict[str, Any], slots: list[_TextSlot], budget: Budget) -> dict[str, Any]:
    """把预算分给各个正文槽：需求小的先满足，剩下的平分；放完量一次整体，超了就收紧重放。"""
    if not slots:
        return result
    bases: dict[int, tuple[list[str], list[str]]] = {}
    for slot in slots:
        bases.setdefault(id(slot.target), (slot.target, list(slot.target)))

    def sync() -> None:
        for target, base in bases.values():
            target[:] = base
        for slot in slots:
            slot.target.extend(slot.own)

    for slot in slots:
        slot.measure(budget)
        slot.render(0.0, budget)
    sync()
    available = max(0.0, 1.0 - _BUDGET_MARGIN - budget.value_fraction(result))
    for _ in range(8):
        remaining = available
        pending = sorted(slots, key=lambda slot: slot.demand)
        for position, slot in enumerate(pending):
            grant = min(slot.demand, remaining / (len(pending) - position))
            slot.render(grant, budget)
            remaining -= grant
        sync()
        if budget.value_fraction(result) <= 1.0:
            return result
        available *= 0.85
    for slot in slots:
        slot.render(0.0, budget)
    sync()
    return result


# ---------------------------------------------------------------------------------------------------------------------
# 各种结果形状


def shape_result(raw: Any, request: ViewRequest, budget: Budget) -> Any:
    """按视图与模型预算整形一个工具结果。`full` 视图原样返回（只并入参数说明）。"""
    if request.view == FULL:
        return _with_notes(raw, request.notes)
    value = raw.model_dump(mode="json") if hasattr(raw, "model_dump") else raw
    if not isinstance(value, dict):
        return raw
    if _is_envelope(value):
        shaped, slot = _plan_envelope(value, request)
        shaped = _fill(shaped, [slot] if slot else [], budget)
    elif isinstance(value.get("results"), dict) and ("selected_tools" in value or value.get("schema") == HECAN_SCHEMA):
        shaped = _shape_results_map(value, request, budget)
    elif _has_memory_records(value):
        shaped = _shape_memory(value, request, budget)
    else:
        shaped = value
    return _with_notes(fit_to_budget(shaped, budget), request.notes)


def _with_notes(raw: Any, notes: tuple[str, ...] | list[str]) -> Any:
    if not notes:
        return raw
    if isinstance(raw, dict):
        return {**raw, "warnings": [*(raw.get("warnings") or []), *notes]}
    if hasattr(raw, "warnings") and hasattr(raw, "model_copy"):
        return raw.model_copy(update={"warnings": [*raw.warnings, *notes]})
    return raw


def with_notes(raw: Any, notes: list[str]) -> Any:
    return _with_notes(raw, notes)


def _shape_results_map(value: dict[str, Any], request: ViewRequest, budget: Budget) -> dict[str, Any]:
    """调度 / 合参：`results.<tool>` 各自成阅读视图，预算几份结果一起分。`response_tool` 只展开点名的那一个。"""
    result = dict(value)
    run_id = _run_id(value)
    results: dict[str, Any] = {}
    slots: list[_TextSlot] = []
    for name, envelope in (value.get("results") or {}).items():
        if not _is_envelope(envelope):
            results[name] = envelope
            continue
        wanted = request.tool in (None, name, envelope.get("tool"))
        shaped, slot = _plan_envelope(envelope, request if wanted else ViewRequest(view=TITLES), run_id=run_id)
        results[name] = shaped
        if slot is not None:
            slots.append(slot)
    result["results"] = results
    # 每个技法的导出契约在各自的阅读视图里已经有了（export_snapshot 的段索引），不再另抄一份（每个技法约 2 KB）。
    if isinstance(result.get("result_export_contracts"), dict) and result["result_export_contracts"]:
        result["result_export_contracts"] = {}
    return _fill(result, slots, budget)


def _has_memory_records(value: dict[str, Any]) -> bool:
    if isinstance(value.get("result"), dict) and isinstance(value["result"].get("artifacts"), list):
        return True
    return isinstance(value.get("results"), list) and any(
        isinstance(item, dict) and isinstance(item.get("artifacts"), list) for item in value["results"]
    )


def _shape_memory(value: dict[str, Any], request: ViewRequest, budget: Budget) -> dict[str, Any]:
    """存档读回：技法产物的载荷成阅读视图；调度产物里重复的那份结果只留指向；运行清单是索引，不带载荷。"""
    result = dict(value)
    warnings = list(result.get("warnings") or [])
    result["warnings"] = warnings
    slots: list[_TextSlot] = []
    matched = request.tool is None

    def shape_record(record: dict[str, Any]) -> dict[str, Any]:
        nonlocal matched
        record = dict(record)
        run_id = str(record.get("run_id") or "") or None
        artifacts: list[Any] = []
        for artifact in record.get("artifacts") or []:
            if not isinstance(artifact, dict) or not isinstance(artifact.get("payload"), dict):
                artifacts.append(artifact)
                continue
            artifact = dict(artifact)
            payload = artifact["payload"]
            kind = artifact.get("kind")
            if kind == "tool_result" and _is_envelope(payload):
                wanted = request.tool in (None, artifact.get("tool_name"), payload.get("tool"))
                matched = matched or wanted
                shaped, slot = _plan_envelope(
                    payload, request if wanted else ViewRequest(view=TITLES), run_id=run_id, target=warnings,
                )
                if slot is not None:
                    slots.append(slot)
                artifact["payload"] = shaped
            elif kind == "dispatch_result" and isinstance(payload.get("results"), dict):
                artifact["payload"] = {
                    **{key: item for key, item in payload.items()
                       if key not in ("results", "result_export_contracts", "normalized_inputs")},
                    "results": {name: {"ok": item.get("ok") if isinstance(item, dict) else None,
                                       "see": f"tool_result artifact (response_tool=\"{name}\")"}
                                for name, item in payload["results"].items()},
                }
            elif kind == "hecan_result":
                # 合参模板：各技法的正文在同一条记录的 tool_result 阅读视图里（复用的子结果已由 memory_show 接上），节选不再重复一份。
                artifact["payload"] = {
                    **payload,
                    "techniques": [
                        {**row, "evidence": {key: value for key, value in row["evidence"].items() if key != "text"}
                         | {"text_in": f"tool_result artifact (response_tool=\"{row.get('tool')}\")"}}
                        if isinstance(row, dict) and isinstance(row.get("evidence"), dict) else row
                        for row in payload.get("techniques") or []
                    ],
                }
            elif kind == "run_manifest":
                artifact.pop("payload")
            artifacts.append(artifact)
        record["artifacts"] = artifacts
        return record

    if isinstance(result.get("result"), dict) and isinstance(result["result"].get("artifacts"), list):
        result["result"] = shape_record(result["result"])
    if isinstance(result.get("results"), list):
        result["results"] = [
            shape_record(item) if isinstance(item, dict) and isinstance(item.get("artifacts"), list) else item
            for item in result["results"]
        ]
    if not matched:
        warnings.append(bilingual(
            f"这条记录里没有 `{request.tool}` 的结果；技法名见 artifacts[].tool_name。",
            f"this run has no result for `{request.tool}`; tool names are in artifacts[].tool_name.",
        ))
    return _fill(result, slots, budget)


# ---------------------------------------------------------------------------------------------------------------------
# 兜底：没有正文槽的大结果


def fit_to_budget(value: Any, budget: Budget) -> Any:
    """仍超预算（没有正文槽的大结果、骨架本身就大）：从最大的子树起逐个换成占位，直到放得下。入参不改。"""
    if not isinstance(value, dict) or budget.value_fraction(value) <= 1.0:
        return value
    result = dict(value)
    omitted: list[str] = []
    for _ in range(64):
        if budget.value_fraction(result) <= 1.0 - _BUDGET_MARGIN:
            break
        path = _omit_largest(result)
        if path is None:
            break
        omitted.append(path)
    if omitted:
        result["warnings"] = [
            *(result.get("warnings") or []),
            bilingual(
                f"结果超过单次返回的模型预算，已略去：{'、'.join(omitted)}。要完整结果：同一次调用加 response_view=\"full\"。",
                f"result exceeds the per-result model budget; omitted: {', '.join(omitted)}. "
                'For everything: the same call + response_view="full".',
            ),
        ]
    return result


def _omit_largest(root: dict[str, Any]) -> str | None:
    """从顶层往下找：取最大的子项，若它有一个子项占了它一半以上就继续往下，否则把它换成占位。返回路径。

    沿途的容器逐层浅拷贝，入参不变。"""
    holder: Any = root
    path: list[str] = []
    depth = 0
    while True:
        if isinstance(holder, dict):
            items = [(key, item) for key, item in holder.items()
                     if key not in _KEEP_EVERYWHERE and not (depth == 0 and key in _GENERIC_PROTECTED)]
        else:
            items = list(enumerate(holder))
        sized = [(len(compact_json(item)), key) for key, item in items
                 if isinstance(item, (dict, list, str)) and not (isinstance(item, dict) and item.get("omitted") == _PLACEHOLDER)]
        if not sized:
            return None
        size, key = max(sized, key=lambda pair: pair[0])
        if size < 200:
            return None
        child = holder[key]
        if isinstance(child, (dict, list)) and child and depth < 6:
            inner = [len(compact_json(item)) for item in (child.values() if isinstance(child, dict) else child)]
            if max(inner) * 2 > size:
                copy = dict(child) if isinstance(child, dict) else list(child)
                holder[key] = copy
                holder = copy
                path.append(str(key))
                depth += 1
                continue
        holder[key] = {"omitted": _PLACEHOLDER, "chars": size}
        path.append(str(key))
        return ".".join(path)


# ---------------------------------------------------------------------------------------------------------------------
# 指引索引


def _one_line(text: Any, limit: int = 80) -> str:
    line = str(text or "").strip().splitlines()[0] if str(text or "").strip() else ""
    for stop in ("。", ". "):
        head, found, _ = line.partition(stop)
        if found and head:
            line = head + stop.strip()
            break
    return line if len(line) <= limit else line[: limit - 1] + "…"


def guidance_index(guidance: dict[str, Any]) -> dict[str, Any]:
    """`include_all` 的全量指引 → 索引：每个技法一行（名字、一句话、要先和用户确认的设置），全文按 tool_name 取。

    全量指引每个技法带完整输入契约，合计 1.26 M 字符；模型挑技法只要这张表。"""
    tools = guidance.get("tools") if isinstance(guidance.get("tools"), dict) else {}
    rows: list[dict[str, Any]] = []
    for name, entry in tools.items():
        if not isinstance(entry, dict):
            continue
        asks = [item.get("field") for item in entry.get("ask_if_missing") or [] if isinstance(item, dict) and item.get("field")]
        settings = [item.get("field") for item in entry.get("safe_defaults") or [] if isinstance(item, dict) and item.get("field")]
        rows.append({
            "tool": name,
            "mcp_name": entry.get("mcp_name"),
            "line": _one_line(entry.get("intent") or entry.get("description")),
            # 问用户什么（缺了闸门会拒）、哪些设置键会改结果（有缺省，用缺省要说明）。
            "confirm": list(dict.fromkeys(asks)),
            "settings": list(dict.fromkeys(settings)),
            "gated": bool((entry.get("hard_gate") or {}).get("enabled")) if isinstance(entry.get("hard_gate"), dict) else False,
        })
    index = {key: value for key, value in guidance.items() if key != "tools"}
    index["view"] = "index"
    index["tools"] = rows
    index["next"] = "horosa_agent_guidance(tool_name=\"<tool>\") returns one tool's full guidance (settings, defaults, input contract)."
    return index
