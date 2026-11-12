"""记忆门面（memory_query / memory_show / memory_record_answer）的服务端：入参归一、错误成形、结果瘦身。

`ReportsAPI` 的三个方法只转到这里。存储层（`memory/store.py`）只认归一好的值：技法键列表、实体叫法列表、UTC 时刻。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from horosa_skill.agent_guidance import build_validation_recovery
from horosa_skill.engine.registry import TOOL_DEFINITIONS, resolve_tool_name
from horosa_skill.errors import ToolValidationError, bilingual, validation_errors
from horosa_skill.memory import search as memory_search
from horosa_skill.memory import timefilter
from horosa_skill.memory.rebuild import store_health
from horosa_skill.memory.store import EmptyAnswerError, UnknownRunError
from horosa_skill.schemas.tools import MemoryAnswerInput, MemoryQueryInput, MemoryShowInput

# 这些函数拿到的是 HorosaSkillService（ReportsAPI 的 self）；不从包根导入它的类型：包根在 __init__ 执行期间只初始化了一半。
HorosaSkillService = Any

# 一次最多回多少条：每条带调用与产物清单，上百条已是几百 KB。超了按上限回，并在结果里说。
QUERY_LIMIT_MAX = 100
# 写回答案的上限：一份解读几千字，报告级的长文也在几万字内；8 MiB 的「答案」只会把库和每个产物文件一起撑大。
ANSWER_MAX_CHARS = 100_000
STRUCTURED_MAX_BYTES = 262_144
QUESTION_MAX_CHARS = 10_000

# 列表行里的 subject 只留认人用的字段；完整的归一化载荷用 memory_show 取（N4：4 行 15 KB）。
_SUBJECT_KEYS = ("name", "date", "time", "zone", "place", "lat", "lon", "gpsLat", "gpsLon", "gender")
_NESTED_PEOPLE = ("inner", "outer", "subject", "birth")


def _invalid_payload(code: str, operation: str, message: str, exc: ValidationError) -> ToolValidationError:
    errors = validation_errors(exc)
    return ToolValidationError(
        message,
        code=code,
        details={"errors": errors, "agent_recovery": build_validation_recovery(operation_name=operation, errors=errors)},
    )


def store_unavailable(service: HorosaSkillService, exc: BaseException) -> ToolValidationError:
    """库打不开 / 写不了（只读目录、权限、磁盘满、损坏）：结构化的双语错误，不再把 sqlite 的原始异常抛给客户端。"""
    path = str(getattr(service.store, "db_path", "") or "")
    detail = f"{type(exc).__name__}: {exc}"
    return ToolValidationError(
        bilingual(
            f"本机记忆库这次打不开（{path}）：{detail}。起盘不受影响；检查数据目录是否可写，或跑 `horosa-skill doctor`。",
            f"The local memory store could not be used ({path}): {detail}. Chart computation is unaffected; check that the data"
            " directory is writable, or run `horosa-skill doctor`.",
        ),
        code="memory.store_unavailable",
        details={"path": path, "error": detail},
    )


def run_not_found(run_id: Any) -> ToolValidationError:
    return ToolValidationError(
        bilingual(f"没有这条记录：{run_id}。", f"Run not found: {run_id}."),
        code="memory.run.not_found",
        details={"run_id": run_id},
    )


# ---- 技法 ----


def resolve_tools(service: HorosaSkillService, value: Any) -> tuple[list[str], dict[str, Any] | None]:
    """`tool` 的各种叫法 → 注册表键（可能几个）。认得：注册表键、MCP 名（大小写不论）、中文名（繁简都行，「八字」= 两个八字技法），
    以及库里真有的名字（门面调用存的 `horosa_dispatch` 等）。都不是 → `tool.unknown`，带全部合法名字。"""
    if not isinstance(value, str) or not value.strip():
        return [], None
    text = value.strip()
    key = resolve_tool_name(text)
    if key is None:
        lowered = text.casefold()
        key = next(
            (name for name, definition in TOOL_DEFINITIONS.items() if lowered in {name.casefold(), definition.mcp_name.casefold()}),
            None,
        )
    if key is not None:
        return [key], ({"tool": text, "matched": [key]} if key != text else None)
    named = memory_search.tools_named(text)
    if named:
        return named, {"tool": text, "matched": named, "by": "display_name"}
    try:
        with service.store.connect() as conn:
            stored = conn.execute("SELECT 1 FROM tool_calls WHERE tool_name = ? LIMIT 1", (text,)).fetchone()
    except sqlite3.Error:
        stored = None
    if stored:
        return [text], None
    from horosa_skill.agent_guidance.catalog import unknown_tool_details

    raise ToolValidationError(
        bilingual(
            f"不认识的技法名：{text}。可以写注册表键（bazi_birth）、MCP 名（horosa_cn_bazi_birth）或中文名（八字）。",
            f"Unknown technique: {text}. Use the registry key (bazi_birth), the MCP name (horosa_cn_bazi_birth) or the Chinese name (八字).",
        ),
        code="tool.unknown",
        details=unknown_tool_details(text),
    )


# ---- 人 ----


def expand_entity(service: HorosaSkillService, value: Any) -> tuple[list[str], dict[str, Any] | None]:
    """`entity` → 要找的叫法。有命主档案叫这个名字（或别名）时，档案名与全部别名都算：问「我妈」找得到存成「妈妈」的 run。"""
    if not isinstance(value, str) or not value.strip():
        return [], None
    text = value.strip()
    try:
        profiles = service.profiles.all()
    except (ToolValidationError, OSError, sqlite3.Error):
        return [text], None  # 档案库打不开：照字面找，不让检索因此失败
    if not profiles:
        return [text], None
    from horosa_skill.profiles import resolve_in

    try:
        matched = [resolve_in(profiles, text)]
    except ToolValidationError as exc:
        if exc.code != "profile.ambiguous":
            return [text], None
        names = set(exc.details.get("candidates") or [])
        matched = [profile for profile in profiles if profile.name in names]
    needles = [text]
    for profile in matched:
        needles += [profile.name, *profile.aliases]
    needles = list(dict.fromkeys(needles))
    return needles, {"entity": text, "profiles": [profile.name for profile in matched], "names_searched": needles}


# ---- 结果瘦身 ----


def _compact_person(source: Any) -> dict[str, Any]:
    if not isinstance(source, dict):
        return {}
    return {key: source[key] for key in _SUBJECT_KEYS if source.get(key) not in (None, "")}


def compact_subject(subject: Any) -> Any:
    """列表行的 subject：只留名字、日期、时刻、时区、地点 / 坐标、性别（按存的原样）；合盘的两人各留一份。"""
    if not isinstance(subject, dict):
        return subject
    compact = _compact_person(subject)
    for key in _NESTED_PEOPLE:
        nested = _compact_person(subject.get(key))
        if nested:
            compact[key] = nested
    return compact


# ---- 门面 ----


def query_memory(service: HorosaSkillService, payload: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any]:
    try:
        request = MemoryQueryInput.model_validate(payload)
    except ValidationError as exc:
        trace["error_code"] = "memory.query.invalid_payload"
        raise _invalid_payload("memory.query.invalid_payload", "memory_query", "Invalid payload for memory query.", exc) from exc

    notes: list[str] = []
    applied: dict[str, Any] = {}
    limit = max(1, request.limit)
    if limit > QUERY_LIMIT_MAX:
        notes.append(
            bilingual(
                f"limit {request.limit} 超过上限，按 {QUERY_LIMIT_MAX} 条返回；更多用 offset 翻页。",
                f"limit {request.limit} is above the maximum; returned at most {QUERY_LIMIT_MAX}. Page with offset for more.",
            )
        )
        limit = QUERY_LIMIT_MAX
    applied["limit"] = limit
    tools, tool_note = resolve_tools(service, request.tool)
    if tool_note:
        applied["tool"] = tool_note
    entities, entity_note = expand_entity(service, request.entity)
    if entity_note:
        applied["entity"] = entity_note
    try:
        window = timefilter.resolve_range(request.after, request.before, request.zone)
    except timefilter.TimeFilterError as exc:
        trace["error_code"] = "memory.query.invalid_time"
        raise ToolValidationError(
            bilingual(
                f"{exc.field}={exc.value!r} 不是能认的时间（{exc.reason}）。可用写法：{'、'.join(timefilter.ACCEPTED_FORMS)}；"
                f"zone 写 {' / '.join(timefilter.ACCEPTED_ZONES)}。「昨天」这类说法请先换成日期。",
                f"{exc.field}={exc.value!r} is not a time this filter understands ({exc.reason}). Accepted forms:"
                f" {', '.join(timefilter.ACCEPTED_FORMS)}; zone as {' / '.join(timefilter.ACCEPTED_ZONES)}."
                " Turn words like 'yesterday' into a date first.",
            ),
            code="memory.query.invalid_time",
            details={"field": exc.field, "value": exc.value, "accepted_forms": list(timefilter.ACCEPTED_FORMS),
                     "accepted_zones": list(timefilter.ACCEPTED_ZONES)},
        ) from exc
    if window.get("zone_source"):
        applied["time"] = window

    scan: dict[str, Any] = {}
    try:
        results = service.store.query_runs(
            run_id=request.run_id,
            group_id=request.group_id,
            tool=tools or None,
            entity=entities or None,
            text=request.text,
            artifact_kind=request.artifact_kind,
            after=window["after"],
            before=window["before"],
            limit=limit,
            offset=max(0, request.offset or 0),
            include_payload=request.include_payload,
            scan_report=scan,
        )
        health = store_health(service.store)
    except (sqlite3.Error, OSError) as exc:
        trace["error_code"] = "memory.store_unavailable"
        raise store_unavailable(service, exc) from exc
    for row in results:
        row["subject"] = compact_subject(row.get("subject"))
    trace["result_count"] = len(results)
    not_scanned = int(scan.get("not_scanned") or 0)
    summary = [f"已检索到 {len(results)} 条本地 run 记录。"]
    if not_scanned:
        summary.append(
            bilingual(
                f"另有 {not_scanned} 条记录的盘面正文还没读进检索索引（问题、答案、技法、人名已经可搜）；"
                "再查一次会接着读，或跑 `horosa-skill memory rebuild` 一次读完。",
                f"{not_scanned} runs still have their chart text waiting to be indexed (question, answer, technique and names are"
                " already searchable); query again to continue, or run `horosa-skill memory rebuild` to finish at once.",
            )
        )
    summary += notes
    warnings = list(health.get("warnings") or [])
    result: dict[str, Any] = {
        "ok": True,
        "count": len(results),
        "results": results,
        "not_scanned": not_scanned,
        "applied_filters": applied,
        "trace_id": trace["trace_id"],
        "group_id": trace["group_id"],
        "summary": summary,
    }
    if warnings:
        result["warnings"] = warnings
    return result


def _incomplete_record(record: dict[str, Any]) -> list[dict[str, Any]]:
    problems = []
    for artifact in record.get("artifacts") or []:
        if artifact.get("kind") == "run_manifest":
            continue
        if not artifact.get("exists"):
            problems.append({"kind": artifact.get("kind"), "tool_name": artifact.get("tool_name"), "path": artifact.get("path"),
                             "problem": "missing"})
        elif artifact.get("payload_error"):
            problems.append({"kind": artifact.get("kind"), "tool_name": artifact.get("tool_name"), "path": artifact.get("path"),
                             "problem": f"unreadable: {artifact['payload_error']}"})
    return problems


def _attach_child_runs(service: HorosaSkillService, record: dict[str, Any], *, include_payload: bool) -> None:
    """合参 run：它复用的技法结果存在别的 run 里。按 hecan_result 的 child_runs 把那几份 tool_result 产物接到这条记录后面
    （`from_run` 标出处），读回合参就能看到全部子结果；`record["child_runs"]` 原样列出。"""
    own = record.get("run_id")
    children: list[dict[str, Any]] = []
    for artifact in record.get("artifacts") or []:
        if artifact.get("kind") == "hecan_result" and isinstance(artifact.get("payload"), dict):
            children = [row for row in artifact["payload"].get("child_runs") or [] if isinstance(row, dict)]
    if not children and not any(a.get("kind") == "hecan_result" for a in record.get("artifacts") or []):
        return
    if not children:
        # 没带 payload 读（include_payload=false）：产物文件里才有 child_runs。
        for artifact in record.get("artifacts") or []:
            if artifact.get("kind") == "hecan_result" and artifact.get("exists"):
                try:
                    children = json.loads(Path(artifact["path"]).read_text(encoding="utf-8")).get("child_runs") or []
                except (OSError, ValueError):
                    children = []
    record["child_runs"] = children
    wanted: dict[str, set[str]] = {}
    for row in children:
        if row.get("run_id") and row.get("run_id") != own:
            wanted.setdefault(str(row["run_id"]), set()).add(str(row.get("tool")))
    for child_id, tools in wanted.items():
        rows = service.store.query_runs(run_id=child_id, limit=1, include_payload=include_payload)
        if not rows:
            record.setdefault("artifacts", []).append(
                {"kind": "tool_result", "tool_name": ",".join(sorted(tools)), "from_run": child_id, "exists": False, "path": None})
            continue
        for artifact in rows[0].get("artifacts") or []:
            if artifact.get("kind") == "tool_result" and str(artifact.get("tool_name")) in tools:
                record.setdefault("artifacts", []).append({**artifact, "from_run": child_id})


def show_memory(service: HorosaSkillService, payload: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any]:
    try:
        request = MemoryShowInput.model_validate(payload)
    except ValidationError as exc:
        trace["error_code"] = "memory.show.invalid_payload"
        raise _invalid_payload("memory.show.invalid_payload", "memory_show", "Invalid payload for memory show.", exc) from exc
    try:
        results = service.store.query_runs(run_id=request.run_id, limit=1, include_payload=request.include_payload, include_history=True)
    except (sqlite3.Error, OSError) as exc:
        trace["error_code"] = "memory.store_unavailable"
        raise store_unavailable(service, exc) from exc
    if not results:
        trace["error_code"] = "memory.run.not_found"
        error = run_not_found(request.run_id)
        from horosa_skill.errors import recovery_for

        return {
            "ok": False,
            "code": error.code,
            "message": f"{error}",
            "details": recovery_for(error.code, error.details),
            "trace_id": trace["trace_id"],
            "group_id": trace["group_id"],
        }
    trace["run_id"] = request.run_id
    record = results[0]
    try:
        _attach_child_runs(service, record, include_payload=request.include_payload)
    except (sqlite3.Error, OSError) as exc:
        trace["error_code"] = "memory.store_unavailable"
        raise store_unavailable(service, exc) from exc
    problems = _incomplete_record(record)
    result: dict[str, Any] = {"ok": True, "result": record, "complete": not problems,
                              "trace_id": trace["trace_id"], "group_id": trace["group_id"]}
    if not problems:
        result["summary"] = ["已读取对应 run 的本地完整记录。"]
        return result
    readable = [a for a in record.get("artifacts") or [] if a.get("exists") and not a.get("payload_error") and a.get("kind") != "run_manifest"]
    result["missing_artifacts"] = problems
    result["summary"] = [
        bilingual(
            f"这条记录不完整：{len(problems)} 份产物文件缺失或读不了（见 missing_artifacts）。还在的有：问题与答案、"
            f"{len(record.get('tool_calls') or [])} 次调用的输入与摘要、{len(readable)} 份可读的产物。"
            "缺的盘面要重新起盘才有；跑 `horosa-skill memory rebuild` 可以把挪了位置的文件重新接上。",
            f"This record is incomplete: {len(problems)} artifact files are missing or unreadable (see missing_artifacts). Still"
            f" available: the question and answer, inputs and summaries of {len(record.get('tool_calls') or [])} calls, and"
            f" {len(readable)} readable artifacts. A missing chart has to be cast again; `horosa-skill memory rebuild` reconnects"
            " files that were moved.",
        )
    ]
    return result


def record_ai_answer(service: HorosaSkillService, payload: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any]:
    try:
        request = MemoryAnswerInput.model_validate(payload)
    except ValidationError as exc:
        trace["error_code"] = "memory.answer.invalid_payload"
        raise _invalid_payload("memory.answer.invalid_payload", "memory_record_answer", "Invalid payload for memory answer record.", exc) from exc
    answer = request.ai_answer_text if request.ai_answer_text is not None else request.ai_answer
    if answer is None:  # 两个名字都没给：与字段校验同一个码、同一份可自修的恢复说明
        trace["error_code"] = "memory.answer.invalid_payload"
        errors = [{"loc": ("ai_answer_text",), "msg": "Field required", "type": "missing"}]
        raise ToolValidationError(
            bilingual("缺 ai_answer_text（要写回的答案）。", "Missing ai_answer_text (the answer to store)."),
            code="memory.answer.invalid_payload",
            details={"errors": errors, "agent_recovery": build_validation_recovery(operation_name="memory_record_answer", errors=errors)},
        )
    if not answer.strip():
        trace["error_code"] = "memory.answer.empty"
        raise ToolValidationError(
            bilingual(
                "ai_answer_text 是空的：没有写回任何东西，已存的答案保持原样。写回功能不能用来清空答案。",
                "ai_answer_text is empty: nothing was written and the stored answer is unchanged. This call cannot clear an answer.",
            ),
            code="memory.answer.empty",
            details={"run_id": request.run_id},
        )
    oversize = []
    if len(answer) > ANSWER_MAX_CHARS:
        oversize.append({"field": "ai_answer_text", "size": len(answer), "max": ANSWER_MAX_CHARS, "unit": "characters"})
    if request.user_question and len(request.user_question) > QUESTION_MAX_CHARS:
        oversize.append({"field": "user_question", "size": len(request.user_question), "max": QUESTION_MAX_CHARS, "unit": "characters"})
    if request.ai_answer_structured is not None:
        size = len(json.dumps(request.ai_answer_structured, ensure_ascii=False).encode("utf-8"))
        if size > STRUCTURED_MAX_BYTES:
            oversize.append({"field": "ai_answer_structured", "size": size, "max": STRUCTURED_MAX_BYTES, "unit": "bytes"})
    if oversize:
        trace["error_code"] = "memory.answer.too_large"
        raise ToolValidationError(
            bilingual(
                "写回的内容太大：" + "、".join(f"{item['field']} {item['size']} > {item['max']}" for item in oversize) + "。没有写回任何东西。"
                "把答案压缩成结论与要点再写回；完整长文请用 horosa_report_render 出报告文件。",
                "The answer is too large: " + ", ".join(f"{item['field']} {item['size']} > {item['max']}" for item in oversize)
                + ". Nothing was written. Write back the conclusions and key points; render long text as a report with horosa_report_render.",
            ),
            code="memory.answer.too_large",
            details={"run_id": request.run_id, "limits": oversize},
        )
    try:
        result = service.store.attach_ai_response(
            run_id=request.run_id,
            user_question=request.user_question,
            ai_answer=answer,
            ai_answer_structured=request.ai_answer_structured,
            answer_meta=request.answer_meta,
        )
    except UnknownRunError as exc:
        trace["error_code"] = "memory.run.not_found"
        raise run_not_found(request.run_id) from exc
    except EmptyAnswerError as exc:  # 上面已拦；store 自己也拒收，两层说法一致
        trace["error_code"] = "memory.answer.empty"
        raise ToolValidationError(f"{exc}", code="memory.answer.empty", details={"run_id": request.run_id}) from exc
    except (sqlite3.Error, OSError) as exc:
        trace["error_code"] = "memory.store_unavailable"
        raise store_unavailable(service, exc) from exc
    updated, skipped = result["artifacts_updated"], result["artifacts_skipped"]
    summary = [
        "已把答案写回这条记录" + ("，替换了之前的答案（旧答案留在 answer_history，memory_show 可见）" if result["replaced_previous"] else "")
        + f"；manifest 已更新，{len(updated)} 份产物文件已同步。"
    ]
    if request.user_question is None:
        summary.append("没有传 user_question：沿用已存的问题。")
    if skipped:
        summary.append(
            bilingual(
                f"{len(skipped)} 份产物文件没能同步（缺失或读不了，见 artifacts_skipped）；答案已在记忆库与 manifest 里。",
                f"{len(skipped)} artifact files could not be updated (missing or unreadable, see artifacts_skipped); the answer is"
                " stored in the memory database and the manifest.",
            )
        )
    result["summary"] = summary
    result["trace_id"] = trace["trace_id"]
    result["group_id"] = trace["group_id"]
    trace["run_id"] = request.run_id
    return result
