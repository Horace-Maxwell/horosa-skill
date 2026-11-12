"""记忆检索的「检索文档」：一次 run 里人会去搜的字，别的一概不进。

每个 run 一份文档，分两栏：
- `head`：问题、写回的答案（含被替换掉的旧答案）、技法键与中文名、实体、各次调用的摘要行——全在库里，随写随算；
- `body`：盘面正文（`export_snapshot.export_text`；老产物没有它时取 `snapshot_text`）——只在产物文件里，写产物时顺手取，
  老库与重建时从文件回填。

路径、run id、时间戳、JSON 键名都不进文档：以前深扫把整份产物当字符串比，搜 `json` / `ok` / 用户名都能「命中」每一条。
两栏都按知识库检索的同一套归一存放（NFKC → 繁转简 → casefold，`knowledge.retrieval.normalize`），查询词走同一个函数。
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

# 文档格式版本：变了就让老行重新回填（run_search.state 记的是「正文已按哪一版进索引」）。
SEARCH_DOC_VERSION = 1

# 一个查询里按空白 / 中文逗号顿号分词；词与词是 AND。`/` `-` `.` 留在词里（日期、技法键）。
_TERM_SPLIT = re.compile(r"[\s,，、;；]+")
# FTS5 trigram 的最短可查长度（码点）。
TRIGRAM_MIN = 3

_DATE_FORM = re.compile(
    r"(?<!\d)(\d{4})\s*[-/.年]\s*(\d{1,2})(?:\s*[-/.月]\s*(\d{1,2})(?:\s*日)?|\s*月)?(?!\d)"
)
# body 里各段正文之间的分隔（记录分隔符，查询词里不会有）：回填时靠它把已有的段认回来。
BODY_SEPARATOR = "\x1e"
# 调用摘要里的填充行（工具键、顶层 JSON 键名）不是人会搜的字。
_FILLER_SUMMARY = re.compile(r"^(?:工具\s*`|顶层字段|Top-level fields)")


def normalize(text: Any) -> str:
    """建文档与查询共用的归一（与自备知识库检索同一个函数）。"""
    from horosa_skill.knowledge.retrieval import normalize as fold

    return fold(f"{text}") if text is not None else ""


def normalize_dates(text: str) -> str:
    """把文字里的日期写法统一成 `YYYY-MM-DD` / `YYYY-MM`：`1990/5/3`、`1990.05.03`、`1990年5月3日` 是同一天。

    只改长得像「四位年 + 月（+ 日）」的片段，月日越界的原样不动（那不是日期）。"""

    def iso(match: re.Match[str]) -> str:
        year, month, day = match.group(1), int(match.group(2)), match.group(3)
        if not 1 <= month <= 12 or (day is not None and not 1 <= int(day) <= 31):
            return match.group(0)
        return f"{year}-{month:02d}" + (f"-{int(day):02d}" if day is not None else "")

    return _DATE_FORM.sub(iso, text)


def entity_search_key(*values: Any) -> str:
    """实体的匹配键：显示名与实体键归一、日期写法统一后拼在一起。建库与查询都走它。"""
    seen: list[str] = []
    for value in values:
        folded = normalize_dates(normalize(value)).strip()
        if folded and folded not in seen:
            seen.append(folded)
    return "\n".join(seen)


def query_terms(text: Any) -> list[str]:
    """查询串 → 归一后的词（去重、保序）。空串 / 只有分隔符 → 空列表（调用方按「没给 text」处理）。"""
    terms: list[str] = []
    for raw in _TERM_SPLIT.split(f"{text or ''}"):
        term = normalize(raw).strip()
        if term and term not in terms:
            terms.append(term)
    return terms


def fts_phrase(term: str) -> str:
    """一个词 → FTS5 的带引号短语：查询里的 `*` `^` `:` `NEAR` `AND` 一律到不了解析器。"""
    return '"' + term.replace('"', '""') + '"'


_TOOL_NAMES: dict[str, tuple[str, ...]] | None = None


def technique_names(tool_name: str) -> tuple[str, ...]:
    """技法键 → 人会用的叫法：键本身、MCP 名、导出注册表的中文名、报告标题用的名字。"""
    global _TOOL_NAMES
    if _TOOL_NAMES is None:
        table: dict[str, tuple[str, ...]] = {}
        try:
            from horosa_skill.engine.registry import TOOL_DEFINITIONS
            from horosa_skill.knowledge.user import technique_labels
            from horosa_skill.reports.source import report_technique_name

            labels = technique_labels()
            for name, definition in TOOL_DEFINITIONS.items():
                label = labels.get(name) or ""
                names = [name, definition.mcp_name, label, report_technique_name(name, label) if label else ""]
                table[name] = tuple(dict.fromkeys(item for item in names if item))
        except ImportError:  # 注册表导入失败：只剩键本身可搜，不让检索因此不可用
            table = {}
        _TOOL_NAMES = table
    return _TOOL_NAMES.get(tool_name, (tool_name,) if tool_name else ())


def tools_named(value: Any) -> list[str]:
    """按中文名找技法：`八字` → 叫这个名字的全部技法键（繁简折叠后比）。键 / MCP 名另由 `resolve_tool_name` 认。"""
    wanted = normalize(value).strip()
    if not wanted:
        return []
    technique_names("")  # 建表
    hits = [
        name
        for name, names in (_TOOL_NAMES or {}).items()
        if any(normalize(item) == wanted for item in names)
    ]
    return sorted(hits)


_NOT_WORDS = re.compile(r"(?:^|_)(?:id|ids|path|paths|url|uri|sha256|hash|created_at|updated_at|at)$")


def answer_strings(value: Any, *, _depth: int = 0) -> list[str]:
    """结构化答案（`ai_answer_structured`，如报告的 `ai_report`）里人写的字：只取字符串值，不取键名；
    `*_id` / `path` / `url` / 时间戳这类键下的值不是人会搜的字，跳过。"""
    found: list[str] = []
    if _depth > 6:
        return found
    if isinstance(value, str):
        if value.strip():
            found.append(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            if not _NOT_WORDS.search(f"{key}".lower()):
                found += answer_strings(item, _depth=_depth + 1)
    elif isinstance(value, list):
        for item in value[:200]:
            found += answer_strings(item, _depth=_depth + 1)
    return found


def build_head(
    *,
    query_text: Any,
    user_question: Any,
    ai_answer: Any,
    answer_structured: Any = None,
    previous_answers: Iterable[Any] = (),
    tool_names: Iterable[str] = (),
    entities: Iterable[tuple[Any, Any]] = (),
    summaries: Iterable[Any] = (),
) -> str:
    parts: list[str] = []

    def add(value: Any) -> None:
        folded = normalize(value).strip() if isinstance(value, str) else ""
        if folded and folded not in parts:
            parts.append(folded)

    add(query_text)
    add(user_question)
    add(ai_answer)
    for text in answer_strings(answer_structured):
        add(text)
    for answer in previous_answers:
        add(answer)
    for tool in dict.fromkeys(tool_names):
        for name in technique_names(tool):
            add(name)
    for display_name, entity_key in entities:
        add(display_name)
        add(entity_key)
        if isinstance(entity_key, str):
            add(normalize_dates(normalize(entity_key)))
    for line in summaries:
        add(line)
    return "\n".join(parts)


def summary_lines(summary_json_values: Iterable[Any]) -> list[str]:
    """各次调用的摘要行（`tool_calls.summary_json`），去掉只列工具键 / JSON 键名的填充行。"""
    lines: list[str] = []
    for raw in summary_json_values:
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
        except ValueError:
            continue
        for line in parsed if isinstance(parsed, list) else []:
            if isinstance(line, str) and line.strip() and not _FILLER_SUMMARY.match(line.strip()):
                lines.append(line)
    return lines


def _collect(payload: Any, key: str, found: list[str], depth: int = 0) -> None:
    if depth > 8:
        return
    if isinstance(payload, dict):
        for name, value in payload.items():
            if name == key and isinstance(value, str):
                if value.strip() and value not in found:
                    found.append(value)
            elif isinstance(value, (dict, list)):
                _collect(value, key, found, depth + 1)
    elif isinstance(payload, list):
        for item in payload:
            _collect(item, key, found, depth + 1)


def export_texts(payload: Any) -> list[str]:
    """从一份产物（单技法信封或调度结果）里取盘面正文：所有 `export_text` 字符串，按出现顺序去重。

    一个 `export_text` 都没有（老产物）才取 `snapshot_text`——两者是同一份正文的两种排法，都收会让文档翻倍。
    原始引擎 JSON 是数字和键名，不进文档。"""
    for key in ("export_text", "snapshot_text"):
        found: list[str] = []
        _collect(payload, key, found)
        if found:
            return found
    return []


def export_texts_from_file(path: Path) -> list[str]:
    """同 `export_texts`，但直接扫文件文本、只解码命中的那几个字符串：一份八字产物 600 多 KB，回填上万个不值得逐个整份解析。

    扫不出来（键写法不同、文件不是紧凑 JSON）就整份解析一次；读不了 / 不是 JSON 返回空列表（这份产物没有可搜的正文）。"""
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return []
    for key in ("export_text", "snapshot_text"):
        found: list[str] = []
        try:
            for match in re.finditer(rf'"{key}"\s*:\s*"', raw):
                value, _ = json.decoder.scanstring(raw, match.end(), True)
                if value.strip() and value not in found:
                    found.append(value)
        except ValueError:
            found = []
            break
        if found:
            return found
    if '"export_text"' not in raw and '"snapshot_text"' not in raw:
        return []
    try:
        return export_texts(json.loads(raw))
    except ValueError:
        return []


def merge_body(existing: str, texts: Iterable[str], *, normalized: bool = False) -> str:
    """把新的正文段并进已有的 body（归一后已在里面的不重复加）。`normalized=True`：传进来的段已经归一过（来自另一份 body）。"""
    parts = [part for part in (existing or "").split(BODY_SEPARATOR) if part]
    for text in texts:
        folded = (text if normalized else normalize(text)).strip()
        if folded and folded not in parts:
            parts.append(folded)
    return BODY_SEPARATOR.join(parts)


def body_parts(body: str) -> list[str]:
    return [part for part in (body or "").split(BODY_SEPARATOR) if part]
