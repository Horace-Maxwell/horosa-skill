"""dispatch / hecan 的逐技法载荷规划（v0.50.0-dev）：按时间角色拼载荷，缺什么事实就明说缺什么。

v0.49 之前 dispatch 把同一份出生数据原样发给每个被选中的技法（`payload_for_tool = dict(base_birth)`）：
奇门起的是出生时刻的局、塔罗拿出生时刻当种子、「今天黄历」查出生那天、太阳返照不知道推哪一年；
`preferences`（如 zodiacal=1）与用户的问题根本到不了技法。

这里是纯函数（不碰服务、不联网），dispatch 与闸门共用同一份规划：
- 每个技法按 `engine/time_roles.py` 的角色取时刻：`natal` 用出生数据；`moment` 只用 `context`（AI 客户端
  知道「此刻」，服务端不拿自己的钟当用户的此刻）；`natal+target` 的目标来自问句里的明确日期 / 年份、或
  「今年 / 明年」+ `context.date`、或 `context` 的时刻；出生数据**永不**顶替起课时刻。
- 偏好（`preferences` 与请求顶层的额外键）只交给声明了该字段的技法；没有任何选中技法接受的键 → 警告点名。
- 技法声明了 `question` / `askEvent` 就把用户原话带过去（没显式给的话）。
- 缺的是只有用户知道的事实（起课时刻、第二个人、要推的年份、卦名……）→ `missing`，由 dispatch 结构化拒绝。

每个技法的规划带 `time_basis`：用了哪个时刻、来自哪里（context / birth / query / query+context）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.engine.synonyms import display_name
from horosa_skill.engine.time_roles import (
    CALENDAR_LOOKUPS,
    LOOKUP,
    MOMENT,
    NATAL,
    NATAL_MOMENT,
    NATAL_TARGET,
    TARGET_STYLE,
    TWO_PARTY,
    WINDOW,
    YEAR,
    time_role,
)
from horosa_skill.errors import bilingual

MOMENT_FIELDS = ("date", "time", "zone", "lat", "lon")
# 只是确认标记 / 存档开关，不是技法设置：照常透传，不算「没人接受的偏好」。
_CONFIRMATION_KEYS = ("agent_confirmed_settings", "defaults_accepted", "clarification_notes", "knowledge")
# dispatch 自己的键（不转发给技法）。
_DISPATCH_KEYS = frozenset({
    "query", "subject", "birth", "context", "preferences", "save_result", "tools", "max_tools", "profile",
    "request", "place", "response_view", *_CONFIRMATION_KEYS,
})

_ISO_DATE = re.compile(r"(?<!\d)((?:1[6-9]|2\d)\d{2})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)")
_CN_DATE = re.compile(r"((?:1[6-9]|2\d)\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]")
_CN_YEAR = re.compile(r"((?:1[6-9]|2\d)\d{2})\s*年")
_EN_YEAR = re.compile(r"\b(?:in|for|of|during|year)\s+((?:1[6-9]|2\d)\d{2})\b|\b((?:19|20)\d{2})\b")
_RELATIVE_YEAR = (("前年", -2), ("去年", -1), ("今年", 0), ("明年", 1), ("后年", 2), ("後年", 2),
                  ("last year", -1), ("this year", 0), ("next year", 1))
_RELATIVE_DAY = (("前天", -2), ("昨天", -1), ("今天", 0), ("今日", 0), ("明天", 1), ("后天", 2), ("後天", 2),
                 ("yesterday", -1), ("today", 0), ("tomorrow", 1))


@dataclass
class PlanInputs:
    query: str = ""
    birth: dict[str, Any] = field(default_factory=dict)          # 给本命类技法的出生载荷（可带 profile 引用）
    birth_fields: dict[str, Any] = field(default_factory=dict)   # 展开后的出生字段（判断缺什么用）
    context: dict[str, Any] = field(default_factory=dict)
    preferences: dict[str, Any] = field(default_factory=dict)
    inner: dict[str, Any] | None = None
    outer: dict[str, Any] | None = None
    subject_year: int | None = None
    gua_names: list[str] = field(default_factory=list)
    confirmation: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolPlan:
    tool: str
    payload: dict[str, Any]
    role: str
    time_basis: dict[str, Any] | None = None
    missing: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    used_keys: set[str] = field(default_factory=set)


def _fields(tool: str) -> set[str]:
    definition = TOOL_DEFINITIONS.get(tool)
    return set(definition.input_model.model_fields) if definition else set()


def _required(tool: str) -> set[str]:
    definition = TOOL_DEFINITIONS.get(tool)
    if definition is None:
        return set()
    return {name for name, info in definition.input_model.model_fields.items() if info.is_required()}


def _present(value: Any) -> bool:
    return value is not None and value != "" and value != []


def _date_parts(value: Any) -> tuple[int, int, int] | None:
    match = re.match(r"\s*(\d{4})-(\d{1,2})-(\d{1,2})", str(value or ""))
    return (int(match.group(1)), int(match.group(2)), int(match.group(3))) if match else None


def _shift_day(date_text: str, days: int) -> str | None:
    from datetime import date, timedelta

    parts = _date_parts(date_text)
    if parts is None:
        return None
    try:
        return (date(*parts) + timedelta(days=days)).isoformat()
    except ValueError:
        return None


_BIRTH_YEAR_AFTER = re.compile(r"^\s*(?:年)?\s*(?:\d{1,2}\s*月[^，,。]{0,8})?(?:出生|生人|生的|生)")
_BIRTH_YEAR_BEFORE = re.compile(r"(?:born|birth)\s*(?:in|on|year)?\s*$", re.IGNORECASE)


def _target_year_in(text: str) -> int | None:
    """问句里的目标年份；「1990年出生」「born in 1990」这种出生年份不算。"""
    for pattern in (_CN_YEAR, _EN_YEAR):
        for match in pattern.finditer(text):
            group = next((g for g in match.groups() if g), None)
            if group is None:
                continue
            start, end = match.span()
            if _BIRTH_YEAR_AFTER.match(text[end:]) or _BIRTH_YEAR_BEFORE.search(text[:start]):
                continue
            return int(group)
    return None


def query_target(query: str, context: dict[str, Any]) -> dict[str, Any] | None:
    """问句里明说的目标：完整日期 > 年份 > 「今年 / 明年」+ context.date。都没有 → None。

    只认这几种明确写法，不做自由文本的日期理解（那是留给维护者决定的事）。"""
    text = query or ""
    for pattern in (_ISO_DATE, _CN_DATE):
        match = pattern.search(text)
        if match:
            year, month, day = (int(group) for group in match.groups())
            return {"date": f"{year:04d}-{month:02d}-{day:02d}", "year": year, "source": "query"}
    year = _target_year_in(text)
    if year is not None:
        return {"year": year, "source": "query"}
    lowered = text.lower()
    for word, offset in _RELATIVE_DAY:
        if word in lowered:
            base = context.get("date")
            if not _date_parts(base):
                return {"needs_context": word}
            shifted = _shift_day(str(base), offset)
            if shifted:
                return {"date": shifted, "year": int(shifted[:4]), "source": "query+context", "word": word}
    for word, offset in _RELATIVE_YEAR:
        if word in lowered:
            base = _date_parts(context.get("date"))
            if base is None:
                return {"needs_context": word}
            return {"year": base[0] + offset, "source": "query+context", "word": word}
    return None


def _fact(fact: str, fields: list[str], zh: str, en: str) -> dict[str, Any]:
    return {"fact": fact, "fields": fields, "question": bilingual(zh, en)}


def _moment_fact(tool: str, missing: list[str], *, candidate: bool = False) -> dict[str, Any]:
    name = display_name(tool)
    if candidate:
        zh = f"{name}评估的是一个候选时刻：请提供要评估的日期、时间、时区和地点（放进 context）。"
        en = f"{name} evaluates one candidate moment: give its date, time, time zone and place (in `context`)."
    else:
        zh = (f"{name}按起课 / 提问的那个时刻起盘：请提供这一刻的日期、时间、时区和地点（放进 context）。"
              "服务端不拿自己的时钟当作用户的「此刻」——AI 客户端知道当前时间和用户所在地，请如实填写；出生时间不能代替。")
        en = (f"{name} is cast for the moment of the question: give that moment's date, time, time zone and place "
              "(in `context`). The server does not assume its own clock is the user's 'now'; the AI client knows the "
              "current time and the user's location, so fill them in. Birth data cannot stand in for it.")
    return _fact("question_moment", [f"context.{key}" for key in missing], zh, en)


def _birth_fact(tool: str, missing: list[str]) -> dict[str, Any]:
    name = display_name(tool)
    return _fact(
        "birth_data", [f"birth.{key}" for key in missing],
        f"{name}需要出生数据：请提供出生日期、时间、时区和出生地（缺：{', '.join(missing)}）。",
        f"{name} needs birth data: birth date, time, time zone and place (missing: {', '.join(missing)}).",
    )


def _context_moment(context: dict[str, Any], wanted: tuple[str, ...]) -> tuple[dict[str, Any], list[str]]:
    payload: dict[str, Any] = {}
    missing: list[str] = []
    for key in wanted:
        if _present(context.get(key)):
            payload[key] = context[key]
        elif key in ("lat", "lon") and _present(context.get("gps" + key.capitalize())):
            payload["gps" + key.capitalize()] = context["gps" + key.capitalize()]
        else:
            missing.append(key)
    return payload, missing


def _apply_preferences(plan: ToolPlan, inputs: PlanInputs, fields: set[str]) -> None:
    for key, value in inputs.preferences.items():
        if key in fields and key not in plan.payload:
            plan.payload[key] = value
            plan.used_keys.add(key)
        elif key in fields:
            plan.used_keys.add(key)


def _apply_question(plan: ToolPlan, inputs: PlanInputs, fields: set[str]) -> None:
    question = (inputs.query or "").strip()
    if not question:
        return
    for key in ("question", "askEvent"):
        if key in fields and not _present(plan.payload.get(key)):
            plan.payload[key] = question


def _target_for(tool: str, inputs: PlanInputs) -> tuple[dict[str, Any], dict[str, Any] | None, list[dict[str, Any]]]:
    """natal+target：返回 (写进载荷的目标键, time_basis 片段, missing)。"""
    style = TARGET_STYLE[tool]
    birth_parts = _date_parts(inputs.birth_fields.get("date"))
    birth_time = str(inputs.birth_fields.get("time") or "").strip() or None
    explicit = query_target(inputs.query, inputs.context)
    if explicit and explicit.get("needs_context"):
        word = explicit["needs_context"]
        return {}, None, [_fact(
            "target_year", ["context.date"],
            f"问句说的是「{word}」：请在 context.date 里给出今天的日期（服务端不拿自己的时钟当用户的今天），或直接写明年份 / 日期。",
            f"The query says '{word}': give today's date in context.date (the server does not assume its own clock is "
            "the user's today), or state the year / date explicitly.",
        )]
    date = year = None
    time_text = None
    source = None
    if explicit:
        date, year, source = explicit.get("date"), explicit.get("year"), explicit["source"]
    elif _date_parts(inputs.context.get("date")):
        date = str(inputs.context["date"])[:10]
        year = int(date[:4])
        time_text = inputs.context.get("time")
        source = "context"
    if year is None:
        return {}, None, [_fact(
            "target", ["context.date (或问句里的年份 / 日期)"],
            f"{display_name(tool)}要推到哪一年 / 哪一天？请在问句里写明，或在 context.date 给出当前日期。",
            f"Which year / date should {display_name(tool)} be cast for? State it in the query, or give the current "
            "date in context.date.",
        )]

    def birthday_in(target_year: int) -> str | None:
        if birth_parts is None:
            return None
        month, day = birth_parts[1], birth_parts[2]
        if month == 2 and day == 29:
            day = 28
        return f"{target_year:04d}-{month:02d}-{day:02d}"

    note = None
    if date is None:
        # 只有年份：落到那一年的生日（与 _RETURN_DEFAULTS 写明的「当年 + 出生月日 + 出生时分」同一规则）。
        if style in ("startYear", "timelineStartYear"):
            pass
        elif style == "startDate":
            date = f"{year:04d}-01-01"
            note = "year → Jan 1"
        elif tool in ("lunarreturn", "liureng_runyear"):
            return {}, None, [_fact(
                "target", ["context.date"],
                f"{display_name(tool)}需要具体日期，不只是年份：请写明哪一天，或在 context.date 给出当前日期。",
                f"{display_name(tool)} needs a specific date, not just a year: name the day, or give the current date in context.date.",
            )]
        else:
            date = birthday_in(year)
            time_text = birth_time
            note = "year → birthday in that year"
    payload: dict[str, Any] = {}
    if style == "datetime":
        payload["datetime"] = f"{date} {time_text or birth_time or '12:00:00'}"
    elif style == "targetDate":
        payload["targetDate"] = date
        if time_text:
            payload["targetTime"] = time_text
    elif style == "asOf":
        payload["asOf"] = date
    elif style == "startDate":
        payload["startDate"] = date
    elif style == "startYear":
        payload["startYear"] = year
    elif style == "timelineStartYear":
        payload["timelineStartYear"] = year
    elif style == "guaDate":
        payload["guaDate"] = date
        if time_text:
            payload["guaTime"] = time_text
        if _present(inputs.context.get("zone")):
            payload["guaZone"] = inputs.context["zone"]
    basis = {"target": {k: v for k, v in payload.items()}, "target_source": source}
    if note:
        basis["target_rule"] = note
    return payload, basis, []


def plan_tool(tool: str, inputs: PlanInputs) -> ToolPlan:
    role = time_role(tool) or LOOKUP
    fields = _fields(tool)
    required = _required(tool)
    plan = ToolPlan(tool=tool, payload={}, role=role)

    def need_birth() -> None:
        wanted = [key for key in MOMENT_FIELDS if key in required]
        missing = [key for key in wanted if not _present(inputs.birth_fields.get(key))
                   and not (key in ("lat", "lon") and _present(inputs.birth_fields.get("gps" + key.capitalize())))]
        if missing:
            plan.missing.append(_birth_fact(tool, missing))

    if role in (NATAL, NATAL_TARGET, NATAL_MOMENT):
        plan.payload = dict(inputs.birth)
        need_birth()
        plan.time_basis = {"role": role, "birth": _moment_view(inputs.birth_fields), "source": "birth"}
        if role in (NATAL_TARGET, NATAL_MOMENT):
            target, basis, missing = _target_for(tool, inputs)
            plan.payload.update(target)
            plan.missing.extend(missing)
            if basis:
                plan.time_basis.update(basis)
    elif role == MOMENT:
        wanted = tuple(key for key in MOMENT_FIELDS if key in fields)
        if tool in CALENDAR_LOOKUPS:
            wanted = tuple(key for key in MOMENT_FIELDS if key in required) or ("date",)
            explicit = query_target(inputs.query, inputs.context)
            context = dict(inputs.context)
            source = "context"
            if explicit and explicit.get("date"):
                context["date"] = explicit["date"]
                source = explicit["source"]
            elif explicit and explicit.get("needs_context"):
                pass
            moment, missing = _context_moment(context, wanted)
            for key in ("zone", "lat", "lon"):
                if key in fields and key not in moment and _present(inputs.context.get(key)):
                    moment[key] = inputs.context[key]
        else:
            moment, missing = _context_moment(inputs.context, wanted)
            source = "context"
        plan.payload = moment
        if missing:
            plan.missing.append(_moment_fact(tool, missing, candidate=(tool in ("election", "qizhengelection"))))
        plan.time_basis = {"role": role, "moment": _moment_view(moment), "source": source}
        # 求测人的性别（六爻 / 金口诀 / 太乙 …）是问事人的属性，不是时刻：出生数据里有就带上。
        for key in ("gender", "sex"):
            if key in fields and _present(inputs.birth_fields.get(key)):
                plan.payload.setdefault(key, inputs.birth_fields[key])
    elif role == WINDOW:
        moment, missing = _context_moment(inputs.context, tuple(key for key in MOMENT_FIELDS if key in required))
        plan.payload = moment
        for key in ("startDate", "endDate", "startTime", "endTime", "conditions", "pos"):
            if _present(inputs.context.get(key)):
                plan.payload[key] = inputs.context[key]
        if missing:
            plan.missing.append(_moment_fact(tool, missing))
        if not (_present(plan.payload.get("startDate")) and _present(plan.payload.get("endDate"))):
            plan.missing.append(_fact(
                "search_window", ["context.startDate", "context.endDate"],
                f"{display_name(tool)}要在哪段时间里找？请给出起止日期（context.startDate / context.endDate）和要满足的条件。",
                f"Which date range should {display_name(tool)} search? Give context.startDate / context.endDate and the conditions.",
            ))
        plan.time_basis = {"role": role, "window": {k: plan.payload.get(k) for k in ("startDate", "endDate") if k in plan.payload}, "source": "context"}
    elif role == YEAR:
        explicit = query_target(inputs.query, inputs.context)
        year = None
        source = None
        if explicit and explicit.get("year"):
            year, source = explicit["year"], explicit["source"]
        elif inputs.subject_year:
            year, source = inputs.subject_year, "subject.year"
        elif _date_parts(inputs.context.get("date")):
            year, source = _date_parts(inputs.context["date"])[0], "context"
        if year is None:
            plan.missing.append(_fact(
                "target_year", ["subject.year", "context.date"],
                f"{display_name(tool)}看哪一年？请写明年份（或在 context.date 给出当前日期）。",
                f"Which year should {display_name(tool)} cover? State the year (or give the current date in context.date).",
            ))
        else:
            plan.payload["year"] = year
        place, missing = _context_moment(inputs.context, tuple(key for key in ("zone", "lat", "lon") if key in fields))
        plan.payload.update(place)
        if any(key in required for key in missing):
            plan.missing.append(_fact(
                "place", [f"context.{key}" for key in missing],
                f"{display_name(tool)}的时刻按地点的时区算：请在 context 给出地点（place，或 zone + lat/lon）。不默认东八区。",
                f"{display_name(tool)} times depend on the place's time zone: give the place in `context` (place, or zone + "
                "lat/lon). No +08:00 default is assumed.",
            ))
        if "time" in fields and _present(inputs.context.get("time")):
            plan.payload["time"] = inputs.context["time"]
        plan.time_basis = {"role": role, "year": year, "source": source}
    elif role == TWO_PARTY:
        inner = inputs.inner or (inputs.birth or None)
        outer = inputs.outer
        if inner:
            plan.payload["inner"] = dict(inner)
        if outer:
            plan.payload["outer"] = dict(outer)
        if not outer:
            plan.missing.append(_fact(
                "second_person", ["subject.outer"],
                "合盘需要两个人的出生数据：请提供对方的出生日期、时间、时区和出生地（subject.inner = 本人，subject.outer = 对方）。",
                "A relationship chart needs both people's birth data: give the other person's birth date, time, time zone "
                "and place (subject.inner = the user, subject.outer = the other person).",
            ))
        if not inner:
            plan.missing.append(_birth_fact(tool, ["date", "time", "zone", "lat", "lon"]))
        plan.time_basis = {"role": role, "source": "subject.inner/outer" if inputs.inner else "birth + subject.outer"}
    else:  # LOOKUP
        if tool in ("gua_desc", "gua_meiyi"):
            names = [str(name) for name in inputs.gua_names if str(name).strip()]
            if names:
                plan.payload["name"] = names
            else:
                extra_zh = "；想起一卦请改用六爻（sixyao）。" if tool == "gua_meiyi" else "。"
                extra_en = "; to cast a hexagram use Liu Yao (sixyao) instead." if tool == "gua_meiyi" else "."
                plan.missing.append(_fact(
                    "gua_name", ["subject.gua_names"],
                    f"{display_name(tool)}是按卦名查断语：请给出卦名（subject.gua_names，如 [\"乾\", \"坤\"]）{extra_zh}",
                    f"{display_name(tool)} looks text up by hexagram name: give the names in subject.gua_names (e.g. "
                    f"[\"乾\", \"坤\"]){extra_en}",
                ))
        else:
            for key in fields & set(inputs.context):
                plan.payload[key] = inputs.context[key]
            for key in ("q", "query"):
                if key in fields and not _present(plan.payload.get(key)) and inputs.query:
                    plan.payload[key] = inputs.query
        plan.time_basis = None
    _apply_preferences(plan, inputs, fields)
    _apply_question(plan, inputs, fields)
    plan.payload.update(inputs.confirmation)
    return plan


def _moment_view(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: payload[key] for key in (*MOMENT_FIELDS, "gpsLat", "gpsLon", "place") if _present(payload.get(key))}


def plan_all(tools: list[str], inputs: PlanInputs) -> tuple[list[ToolPlan], list[str]]:
    """全部技法的规划 + 「没有任何选中技法接受的偏好键」警告。"""
    plans = [plan_tool(tool, inputs) for tool in tools]
    used = set().union(*(plan.used_keys for plan in plans)) if plans else set()
    unused = sorted(key for key in inputs.preferences if key not in used)
    warnings: list[str] = []
    if unused:
        names = "、".join(display_name(tool) for tool in tools)
        warnings.append(bilingual(
            f"这些设置没有被任何选中的技法（{names}）接受，已忽略：{', '.join(unused)}。",
            f"These settings are not accepted by any selected technique ({', '.join(tools)}) and were ignored: {', '.join(unused)}.",
        ))
    return plans, warnings


def extra_request_settings(payload: dict[str, Any], model_fields: set[str]) -> dict[str, Any]:
    """请求顶层除 dispatch 自己的键以外的设置（如直接写在顶层的 zodiacal / hsys）——与 preferences 同等对待。"""
    return {key: value for key, value in payload.items() if key not in model_fields and key not in _DISPATCH_KEYS}


def missing_facts_recovery(plans: list[ToolPlan], *, operation: str = "horosa_dispatch") -> dict[str, Any] | None:
    """所有规划里缺的事实 → 一份 agent_recovery（双语，逐条点名缺什么、放在哪个键）。没缺 → None。"""
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for plan in plans:
        for fact in plan.missing:
            key = (fact["fact"], fact["question"])
            if key in seen:
                continue
            seen.add(key)
            items.append({**fact, "field": " / ".join(fact["fields"]), "tools": [plan.tool]})
    if not items:
        return None
    lines_zh = ["还缺这些只有用户知道的信息（确认默认设置代替不了它们）："]
    lines_en = ["These facts only the user knows are missing (accepting defaults cannot stand in for them):"]
    for index, item in enumerate(items, start=1):
        zh, _, en = item["question"].partition(" / ")
        lines_zh.append(f"{index}. {zh}")
        lines_en.append(f"{index}. {en or zh}")
    return {
        "must_ask_user": True,
        "kind": "input",
        "reason": "missing_required_facts",
        "prompt_to_user": "\n".join(lines_zh + lines_en),
        "missing_facts": [{"fact": item["fact"], "fields": item["fields"], "tools": item["tools"]} for item in items],
        "ask_if_missing": [{"field": item["field"], "question": item["question"], "fact": True} for item in items],
        "safe_defaults": [],
        "do_not_assume": [
            "Do not substitute birth data for the question's moment, or the server clock for the user's 'now'.",
            "agent_confirmed_settings / defaults_accepted do not answer these: they are facts, not settings.",
        ],
        "example_payload": _example_payload(items),
        "next_action": "ask_user_then_retry",
        "operation": operation,
    }


def _example_payload(items: list[dict[str, Any]]) -> dict[str, Any]:
    facts = {item["fact"] for item in items}
    example: dict[str, Any] = {"query": "…"}
    if facts & {"question_moment", "target", "target_year", "search_window", "place"}:
        context: dict[str, Any] = {"date": "YYYY-MM-DD", "time": "HH:MM:SS", "zone": "+08:00", "place": "城市名 / city"}
        if "search_window" in facts:
            context.update({"startDate": "YYYY-MM-DD", "endDate": "YYYY-MM-DD"})
        example["context"] = context
    if "birth_data" in facts:
        example["birth"] = {"date": "YYYY-MM-DD", "time": "HH:MM:SS", "zone": "+08:00", "place": "出生地 / birthplace"}
    if "second_person" in facts:
        example["subject"] = {"inner": {"date": "…", "time": "…", "zone": "…", "place": "…"},
                              "outer": {"date": "…", "time": "…", "zone": "…", "place": "…"}}
    if "gua_name" in facts:
        example.setdefault("subject", {})["gua_names"] = ["乾"]
    return example


def inputs_from_request(
    request: Any,
    *,
    birth_for_run: dict[str, Any] | None = None,
    inner: dict[str, Any] | None = None,
    outer: dict[str, Any] | None = None,
) -> PlanInputs:
    """DispatchInput / HecanInput → PlanInputs。服务层传 `birth_for_run`（带档案引用的出生载荷）；闸门不传，用展开后的。"""
    subject = getattr(request, "subject", None)
    birth_model = request.birth or (subject.birth if subject is not None else None)
    birth_fields = birth_model.model_dump(exclude_none=True) if birth_model is not None else {}

    def dump(model: Any) -> dict[str, Any] | None:
        return model.model_dump(exclude_none=True) if model is not None else None

    preferences = dict(request.preferences or {})
    for key, value in (getattr(request, "model_extra", None) or {}).items():
        if key not in _DISPATCH_KEYS and value is not None:
            preferences.setdefault(key, value)
    gua_names: list[str] = []
    if subject is not None and subject.gua_names:
        gua_names = list(subject.gua_names)
    elif isinstance(request.context.get("gua_names"), list):
        gua_names = list(request.context["gua_names"])
    confirmation = {
        key: value
        for key, value in {
            "agent_confirmed_settings": request.agent_confirmed_settings,
            "defaults_accepted": request.defaults_accepted,
            "clarification_notes": request.clarification_notes,
            "knowledge": getattr(request, "knowledge", None),
        }.items()
        if value is not None
    }
    return PlanInputs(
        query=request.query or "",
        birth=dict(birth_for_run if birth_for_run is not None else birth_fields),
        birth_fields=birth_fields,
        context=dict(request.context or {}),
        preferences=preferences,
        inner=inner if inner is not None else dump(getattr(subject, "inner", None) if subject is not None else None),
        outer=outer if outer is not None else dump(getattr(subject, "outer", None) if subject is not None else None),
        subject_year=_int_or_none(getattr(subject, "year", None) if subject is not None else None),
        gua_names=gua_names,
        confirmation=confirmation,
    )


def _int_or_none(value: Any) -> int | None:
    try:
        return int(str(value).strip()) if value is not None and str(value).strip() else None
    except ValueError:
        return None


def basis_line(plan: ToolPlan) -> str | None:
    """给 summary 的一行：这个技法用了哪个时刻、从哪来。"""
    basis = plan.time_basis or {}
    if not basis:
        return None
    name = display_name(plan.tool)
    source = basis.get("target_source") or basis.get("source")
    if plan.role == MOMENT:
        moment = basis.get("moment") or {}
        when = " ".join(str(moment[key]) for key in ("date", "time", "zone") if key in moment)
        return f"{name}：时刻取自 {source}（{when}）"
    if plan.role in (NATAL_TARGET, NATAL_MOMENT):
        target = basis.get("target") or {}
        return f"{name}：出生数据 + 目标 {', '.join(f'{k}={v}' for k, v in target.items())}（目标来自 {source}）"
    if plan.role == YEAR:
        return f"{name}：年份 {basis.get('year')}（来自 {source}）"
    return None
