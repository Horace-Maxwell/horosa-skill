"""入参的唯一入口：先归一（各种写法 → 引擎口径），再校验（读不懂就结构化拒绝）。v0.50.0 起两步合一。

全部技法、嵌套当事人（inner / outer、dispatch 的 birth / subject / context、natal、davison）、`horosa_tool_run`、
dispatch / hecan、命主档案都经 `normalize_request_payload`。**当事人位置**（顶层与上面这些键下面的那一层）上的
date / time / zone / 经纬度 / 性别 逐字段由 `input_fields.parse_*` 判定：读懂了 → 规范值（做了解读的进 warnings）；
读不懂 → `ToolValidationError`，details 里每个出问题的字段一条 {field, got, expected, example, options}。认不出的值不会
原样流到引擎，也不会换成缺省值。更深的引擎结构（nongli、jieqi_year_*、options、rectifyEvents…，多是引擎结果回传）
仍走旧的宽松归一（`_legacy_normalize`）：那是引擎自己的数据，不替它判。
"""
from __future__ import annotations

import difflib
import math
import re
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from horosa_skill import input_fields as F
from horosa_skill.errors import ToolValidationError, bilingual

_COMPACT_COORD_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([NSEWnsew])\s*(\d+(?:\.\d+)?)\s*$")
_DECIMAL_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?$")
_ZONE_HM_RE = re.compile(r"^(?P<sign>[+-]?)(?P<hours>\d{1,2})(?::(?P<minutes>\d{1,2}))?$")
# 年带符号、1–5 位（上游 dateStrSafe.parseDateParts 同域：公元前 '-0500-03-21'、五位年 '10000-01-01'）；
# 归一成 formatSignedDate 同形（负年前导负号、年不足 4 位补零、5 位原样）。旧式只认四位无号年：公元前 / 五位年原样透传，
# 月日不补零、IANA 时区也换算不了偏移。
_DATE_RE = re.compile(r"^(?P<year>-?\d{1,5})(?P<sep>[-/])(?P<month>\d{1,2})(?P=sep)(?P<day>\d{1,2})$")
_TIME_RE = re.compile(r"^(?P<hour>\d{1,2}):(?P<minute>\d{1,2})(?::(?P<second>\d{1,2}))?$")
_DATETIME_RE = re.compile(
    r"^(?P<date>-?\d{1,5}[-/]\d{1,2}[-/]\d{1,2})(?P<sep>[T\s]+)(?P<time>\d{1,2}:\d{1,2}(?::\d{1,2})?)$"
)



# 当事人位置：这些键下面的那一层 dict 与顶层同样逐字段严判（dispatch 的 subject.birth 也是）。
PARTY_KEYS = ("inner", "outer", "birth", "subject", "natal", "davison", "context")
_DATE_KEYS = ("date", "guaDate")
_TIME_KEYS = ("time", "guaTime")
_ZONE_KEYS = ("zone", "dirZone", "guaZone")
_COORD_KEYS = (("lat", "lat"), ("lon", "lon"), ("dirLat", "lat"), ("dirLon", "lon"), ("guaLat", "lat"), ("guaLon", "lon"))
# 常见的别名键 → 规范键（模型没声明别名时才改名，改名进 warnings）。
FIELD_ALIASES: dict[str, str] = {
    "timezone": "zone", "tz": "zone", "time_zone": "zone", "timeZone": "zone", "utc_offset": "zone",
    "latitude": "lat", "longitude": "lon", "lng": "lon", "long": "lon",
    "house_system": "hsys", "houseSystem": "hsys", "houses": "hsys",
    "sex": "gender",
    "birth_date": "date", "birthDate": "date", "birth_time": "time", "birthTime": "time",
}
# 不是技法参数、但合法出现在载荷里的键（入口 / 闸门 / 派生）：不报「未知参数」。
NON_TECHNIQUE_KEYS = frozenset({
    "place", "profile", "knowledge", "name", "pos", "question", "agent_confirmed_settings", "defaults_accepted",
    "clarification_notes", "response_view", "geoZone", "zoneAdvisory", "placeResolution", "cnUnifiedZone", "request",
    "tool_name", "save_result", "subject", "query", "group_id", "_place_records",
})
# 只有用户知道的事实：缺了要问用户，不是改写法。
USER_FACT_FIELDS = frozenset({"date", "time", "zone", "lat", "lon", "gender", "guaDate", "guaTime", "guaZone", "guaLat", "guaLon"})


class _Issues:
    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    def add(self, path: str, value: Any, issue: F.FieldIssue) -> None:
        entry = {
            "field": path, "code": issue.code, "got": _jsonable(value), "expected": bilingual(issue.expected_zh, issue.expected_en),
            "example": issue.example, "ask_user": issue.ask_user, "message": bilingual(issue.zh, issue.en),
        }
        if issue.options:
            entry["options"] = issue.options
        self.items.append(entry)


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return repr(value)


def normalize_request_payload(payload: Any, *, model: Any = None) -> Any:
    """归一 + 校验。读不懂的字段一次全部列出：抛 `ToolValidationError`（见 `field_issues_error`）。`model` 给了就按它的字段集
    报「未知参数」并把 datetime / year 拆到声明了的字段上。"""
    normalized, issues = normalize_collecting_issues(payload, model=model)
    if issues:
        raise field_issues_error(issues)
    return normalized


def normalize_collecting_issues(payload: Any, *, model: Any = None) -> tuple[Any, list[dict[str, Any]]]:
    """同上，但不抛：返回 (归一后的载荷, 逐字段问题表)。命主档案（profiles.validate_birth_fields）用它并进自己的错误形状。"""
    issues = _Issues()
    if not isinstance(payload, dict):
        return _legacy_normalize(payload), issues.items
    fields, required = _model_fields(model)
    normalized = _normalize_party(payload, path="", issues=issues, fields=fields, required=required)
    return normalized, issues.items


def _model_fields(model: Any) -> tuple[frozenset[str] | None, frozenset[str]]:
    model_fields = getattr(model, "model_fields", None) if model is not None else None
    if not isinstance(model_fields, dict):
        return None, frozenset()
    return frozenset(model_fields), frozenset(name for name, info in model_fields.items() if info.is_required())


def _normalize_party(
    payload: dict[str, Any], *, path: str, issues: _Issues, fields: frozenset[str] | None, required: frozenset[str] = frozenset()
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in payload.items():
        if key in PARTY_KEYS and isinstance(value, dict):
            out[key] = _normalize_party(value, path=f"{path}{key}.", issues=issues, fields=None)
        else:
            out[key] = _legacy_normalize(value)
    if fields is not None:
        _lift_nested_party(out, fields)
    _apply_aliases(out, path=path, fields=fields)
    if fields is not None:
        _split_target_fields(out, path=path, issues=issues, fields=fields)
    era_explicit = out.get("ad") is not None
    for key in _DATE_KEYS:
        _strict(out, key, path, issues, lambda v: F.parse_date(v, era_explicit=era_explicit), extras=True)
    for key in _TIME_KEYS:
        # 空串钟点：模型要求钟点 → 「钟点未知」问用户；否则等于没给。
        _strict(out, key, path, issues, F.parse_time, drop_blank=key not in required)
    if "datetime" in out:
        _strict(out, "datetime", path, issues, _parse_target_datetime)
    flagged = {item["field"] for item in issues.items}
    for key in _ZONE_KEYS:
        _strict_zone(out, key, path, issues, flagged)
    _strict_coordinates(out, path, issues)
    _strict(out, "gender", path, issues, F.parse_gender)
    if fields is not None:
        _report_unknown_keys(out, fields)
    return out


def _strict(out: dict[str, Any], key: str, path: str, issues: _Issues, parse: Any, *, extras: bool = False, drop_blank: bool = True) -> None:
    if key not in out:
        return
    value = out[key]
    if value is None:
        return
    if F.is_blank(value) and drop_blank:
        # 客户端常把可选字符串填成 ""：等于没给（必填字段随后报缺）。
        del out[key]
        return
    try:
        parsed = parse(value)
    except F.FieldIssue as issue:
        issues.add(path + key, value, issue)
        return
    out[key] = F.note_parsed(parsed, path + key)
    if extras and parsed.extra:
        time_key = "guaTime" if key == "guaDate" else "time"
        zone_key = "guaZone" if key == "guaDate" else "zone"
        for extra_key, target in (("time", time_key), ("zone", zone_key)):
            if extra_key not in parsed.extra:
                continue
            given = out.get(target)
            if F.is_blank(given):
                out[target] = parsed.extra[extra_key]
                continue
            try:
                given_value = (F.parse_time if extra_key == "time" else F.parse_zone)(given).value
            except F.FieldIssue:
                continue  # 单独那个字段自己会报
            if given_value != parsed.extra[extra_key]:
                issues.add(path + target, given, F.FieldIssue(
                    "tool.field_conflict",
                    f"`{key}` 里带的{('时刻' if extra_key == 'time' else '时区')} {parsed.extra[extra_key]} 与 `{target}`={given!r} 不一致，不知道该用哪个。",
                    f"The {extra_key} inside `{key}` ({parsed.extra[extra_key]}) disagrees with `{target}`={given!r}; cannot tell which one is meant.",
                    expected_zh=f"只在一处给{('时刻' if extra_key == 'time' else '时区')}", expected_en=f"give the {extra_key} in one place only",
                    example=parsed.extra[extra_key], options=[parsed.extra[extra_key], given_value],
                ))


def _strict_coordinates(out: dict[str, Any], path: str, issues: _Issues) -> None:
    """经纬度：罗盘串 / 十进制 / 度分秒 / 北纬东经 → 罗盘串（上游 AstroHelper 同式）+ gps 十进制。

    gpsLat / gpsLon 与 lat / lon 是同一个点的两种写法：Java 控制器把 gps 键原样转给后端、后端按候选回退，所以两者都要对。
    只给一边就补另一边（旧口径：gps = 原值十进制 6 位）；两边都给且相差超过 1′ → 以 lat / lon 为准、改写 gps 并进 warnings。"""
    for value_key, axis in _COORD_KEYS:
        gps_key = {"lat": "gpsLat", "lon": "gpsLon"}.get(value_key)
        decimal = _strict_decimal(out, value_key, axis, path, issues)
        if gps_key is None:
            if decimal is not None:
                out[value_key] = _format_compact_coordinate(decimal, axis=axis)
            continue
        gps_decimal = _strict_decimal(out, gps_key, axis, path, issues)
        if decimal is False or gps_decimal is False:
            continue
        if decimal is not None:
            out[value_key] = _format_compact_coordinate(decimal, axis=axis)
            if gps_decimal is not None and abs(decimal - gps_decimal) > 1 / 60 + 1e-9:
                F.add_input_note(
                    f"`{path}{value_key}` 与 `{path}{gps_key}`={out[gps_key]} 不是同一个点：按 {value_key}={out[value_key]} 起盘，{gps_key} 已改成 {round(decimal, 6)}。",
                    f"`{path}{value_key}` and `{path}{gps_key}`={out[gps_key]} are different points; {value_key}={out[value_key]} was used and {gps_key} rewritten to {round(decimal, 6)}.",
                )
                gps_decimal = None
            out[gps_key] = round(gps_decimal if gps_decimal is not None else decimal, 6)
        elif gps_decimal is not None:
            out[gps_key] = round(gps_decimal, 6)
            out[value_key] = _format_compact_coordinate(gps_decimal, axis=axis)


def _strict_decimal(out: dict[str, Any], key: str, axis: str, path: str, issues: _Issues) -> float | None | bool:
    """→ 十进制度；没给 → None；给了但读不懂（已记问题）→ False。"""
    if key not in out or out[key] is None:
        return None
    value = out[key]
    if F.is_blank(value):
        del out[key]
        return None
    try:
        return F.note_parsed(F.parse_coordinate(value, axis=axis), path + key)
    except F.FieldIssue as issue:
        issues.add(path + key, value, issue)
        return False


def _iana_name(text: str) -> str | None:
    """IANA 名（大小写不敏感：asia/shanghai → Asia/Shanghai）或地名式时区（北京时间 → Asia/Shanghai）→ 规范 IANA 名。"""
    folded = text.strip()
    named = F.ZONE_NAME_TO_IANA.get(folded.lower()) or F.ZONE_NAME_TO_IANA.get(_fold(folded))
    if named:
        return named
    if "/" not in folded:
        return None
    return _iana_casefold_map().get(folded.casefold())


def _fold(text: str) -> str:
    from horosa_skill.textscript import fold_to_simplified

    return fold_to_simplified(text).lower()


_IANA_MAP: dict[str, str] | None = None


def _iana_casefold_map() -> dict[str, str]:
    global _IANA_MAP
    if _IANA_MAP is None:
        from zoneinfo import available_timezones

        _IANA_MAP = {name.casefold(): name for name in available_timezones()}
    return _IANA_MAP


def _strict_zone(out: dict[str, Any], key: str, path: str, issues: _Issues, flagged: set[str]) -> None:
    if key not in out or out[key] is None:
        return
    value = out[key]
    if F.is_blank(value):
        del out[key]
        return
    iana = _iana_name(F.clean_text(value)) if isinstance(value, str) else None
    if iana is None:
        try:
            out[key] = F.note_parsed(F.parse_zone(value), path + key)
        except F.FieldIssue as issue:
            if isinstance(value, str) and "/" in value:
                issue = F.FieldIssue("tool.invalid_zone", f"没有叫 {value!r} 的时区（IANA 名区分地区 / 城市，如 Asia/Shanghai）。",
                                     f"There is no time zone named {value!r} (IANA names look like Asia/Shanghai).",
                                     expected_zh=issue.expected_zh, expected_en=issue.expected_en, example="Asia/Shanghai")
            issues.add(path + key, value, issue)
        return
    date_keys = {"zone": ("date", "time"), "dirZone": ("datetime",), "guaZone": ("guaDate", "guaTime")}[key]
    if any(path + k in flagged for k in date_keys):
        return  # 日期 / 时刻自己已经报错，换算不了偏移，不重复报
    if _reference_datetime_for_zone(out, key) is None:
        issues.add(path + key, value, F.FieldIssue(
            "tool.invalid_zone",
            f"时区 {value!r} 是地区名：要知道日期和钟点才能换算成偏移（夏令时、历史改制）。请同时给 date + time，或直接给偏移如 +08:00。",
            f"Zone {value!r} is a region name; converting it to an offset needs the date and time (DST, historical changes). Give date + time, or an offset such as +08:00.",
            expected_zh="±HH:MM 偏移，或 IANA 名 + 日期时刻", expected_en="an ±HH:MM offset, or an IANA name together with date and time", example="+08:00",
        ))
        return
    if iana != value:
        F.add_input_note(f"`{path}{key}`「{value}」按 IANA 时区 {iana} 读。", f"`{path}{key}` '{value}' was read as the IANA zone {iana}.")
    offset = _normalize_iana_zone_value(iana, payload=out, key=key)
    if offset is None:
        return
    ambiguous = _wall_time_ambiguity(out, key)
    if ambiguous is not None:
        kind, options = ambiguous
        zh = ("这个钟点在该地落在夏令时切换的回拨重叠里，出现过两次" if kind == "fold" else "这个钟点在该地因夏令时拨快而不存在")
        en = ("this wall time occurred twice there (DST fall-back overlap)" if kind == "fold" else "this wall time did not exist there (DST spring-forward gap)")
        issues.add(path + key, value, F.FieldIssue(
            "tool.zone_ambiguous", f"时区 {value!r}：{zh}，偏移是 {options[0]} 还是 {options[1]} 只有用户知道（出生证上的钟点按哪套时间记）。",
            f"Zone {value!r}: {en}; whether the offset is {options[0]} or {options[1]} is something only the user knows.",
            expected_zh="明确的偏移 ±HH:MM", expected_en="an explicit ±HH:MM offset", example=options[0], options=options, ask_user=True,
        ))
        return
    out[key] = offset


def _wall_time_ambiguity(payload: dict[str, Any], key: str) -> tuple[str, list[str]] | None:
    """IANA 名 + 钟点 落在夏令时缺口 / 重叠里 → ('gap' | 'fold', [两个偏移])。上游覆盖表生效的日子不判（那里恒为一个偏移）。"""
    from zoneinfo import ZoneInfo

    reference = _reference_datetime_for_zone(payload, key)
    if reference is None:
        return None
    name = _iana_name(f"{payload.get(key)}") or ""
    if payload.get("zoneAdvisory") == "cn-unified" and name in _CN_UNIFY:
        name = _CN_UNIFY[name]
    if not name or _override_offset(name, reference[:3]) is not None:
        return None
    wall = _wall_datetime_for_offset(reference)
    if wall is None:
        return None
    zone = ZoneInfo(name)
    first, second = wall.replace(tzinfo=zone, fold=0), wall.replace(tzinfo=zone, fold=1)
    off0, off1 = first.utcoffset(), second.utcoffset()
    if off0 is None or off1 is None or off0 == off1:
        return None

    roundtrip = first.astimezone(UTC).astimezone(zone).replace(tzinfo=None)
    kind = "fold" if roundtrip == wall else "gap"
    return kind, [_format_offset_seconds(off0.total_seconds()), _format_offset_seconds(off1.total_seconds())]


_YEAR_ONLY_RE = re.compile(r"^\d{4}$")


def _parse_target_datetime(value: Any) -> F.Parsed:
    """推运 / 返照的目标时刻：'YYYY'（那一年的返照 / 流年，由 enrich 按出生月日补全）、日期、日期 + 时刻（空格或 ISO 'T'）。"""
    if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 9999:
        return F.Parsed(f"{value:04d}")
    text = F.clean_text(value)
    if _YEAR_ONLY_RE.match(text):
        return F.Parsed(text)
    match = re.match(r"^(?P<date>\S+?)(?:(?:T|\s+)(?P<time>\S.*?))?(?P<offset>Z|[+-]\d{2}:?\d{2})?$", text, re.IGNORECASE)
    issue = F.FieldIssue(
        "tool.invalid_datetime", f"认不出目标时刻：{value!r}。", f"Unrecognized target datetime: {value!r}.",
        expected_zh="YYYY（那一年）、YYYY-MM-DD 或 YYYY-MM-DD HH:MM[:SS]（也认 ISO 的 T）", expected_en="YYYY (that year), YYYY-MM-DD or YYYY-MM-DD HH:MM[:SS] (ISO 'T' accepted)",
        example="2026-05-03 08:00:00",
    )
    if not match:
        raise issue
    try:
        date = F.parse_date(match.group("date")).value
        clock = F.parse_time(match.group("time")).value if match.group("time") else None
    except F.FieldIssue as inner:
        raise F.FieldIssue("tool.invalid_datetime", inner.zh, inner.en, expected_zh=issue.expected_zh, expected_en=issue.expected_en,
                           example=issue.example, options=inner.options) from None
    if match.group("offset"):
        raise F.FieldIssue("tool.invalid_datetime", f"目标时刻 {value!r} 里带了时区：请把时区单独放进 dirZone。",
                           f"Target datetime {value!r} carries a zone; put the zone in dirZone instead.",
                           expected_zh=issue.expected_zh, expected_en=issue.expected_en, example=issue.example)
    canonical = f"{date} {clock}" if clock else date
    plain = text == canonical or _DATETIME_RE.match(text) is not None or _DATE_RE.match(text) is not None
    return F.Parsed(canonical) if plain else F.Parsed(canonical, f"目标时刻「{text}」按 {canonical} 读。", f"Target datetime '{text}' was read as {canonical}.")


def _lift_nested_party(out: dict[str, Any], fields: frozenset[str]) -> None:
    """技法模型没有 `birth` / `subject` 却收到了（dispatch 的写法用在技法工具上）→ 里层字段提到顶层；顶层显式给的优先。"""
    for key in ("birth", "subject"):
        nested = out.get(key)
        if key in fields or not isinstance(nested, dict):
            continue
        del out[key]
        lifted = [name for name in nested if name not in out]
        for name in lifted:
            out[name] = nested[name]
        F.add_input_note(f"`{key}` 里的字段按顶层参数读（{', '.join(lifted) or '无新增'}）。",
                         f"Fields inside `{key}` were read as top-level arguments ({', '.join(lifted) or 'none new'}).")


def _apply_aliases(out: dict[str, Any], *, path: str, fields: frozenset[str] | None) -> None:
    for alias, canonical in FIELD_ALIASES.items():
        if alias not in out or (fields is not None and alias in fields):
            continue
        value = out.pop(alias)
        if canonical in out and out[canonical] is not None and out[canonical] != value:
            F.add_input_note(f"`{path}{alias}` 与 `{path}{canonical}` 都给了且不同：按 `{canonical}`，`{alias}` 已忽略。",
                             f"`{path}{alias}` and `{path}{canonical}` disagree; `{canonical}` was used and `{alias}` ignored.")
            continue
        out[canonical] = value
        F.add_input_note(f"参数 `{path}{alias}` 按 `{path}{canonical}` 读。", f"Argument `{path}{alias}` was read as `{path}{canonical}`.")


def _split_target_fields(out: dict[str, Any], *, path: str, issues: _Issues, fields: frozenset[str]) -> None:
    """模型没有 datetime 却给了 datetime（起盘工具）→ 拆成 date + time；推运工具给了 year 而没给 datetime → datetime='YYYY'。"""
    if "datetime" in out and "datetime" not in fields and "date" in fields:
        value = out.pop("datetime")
        if F.is_blank(value):
            return
        try:
            parsed = F.parse_date(value)
        except F.FieldIssue as issue:
            issues.add(path + "datetime", value, issue)
            return
        if not parsed.extra.get("time"):
            try:
                parsed = F.parse_date(F.clean_text(value).split()[0])
            except F.FieldIssue:
                pass
        if F.is_blank(out.get("date")):
            out["date"] = value  # 交给下面的 date 校验（含拆出的 time / zone 的冲突判定）
            F.add_input_note(f"`{path}datetime` 拆成 date / time 起盘。", f"`{path}datetime` was split into date / time.")
        elif F.parse_date(out["date"]).value != parsed.value if _safe_date(out["date"]) else False:
            issues.add(path + "datetime", value, F.FieldIssue(
                "tool.field_conflict", f"`datetime`={value!r} 与 `date`={out['date']!r} 不是同一天。", f"`datetime`={value!r} and `date`={out['date']!r} are different days.",
                expected_zh="只给 date + time", expected_en="give date + time only", example="1990-05-03",
            ))
    if "year" in out and "year" not in fields and "datetime" in fields and F.is_blank(out.get("datetime")):
        out["datetime"] = out.pop("year")
        F.add_input_note(f"`{path}year` 作为推运目标年（datetime）读。", f"`{path}year` was read as the target year (datetime).")


def _safe_date(value: Any) -> bool:
    try:
        F.parse_date(value)
        return True
    except F.FieldIssue:
        return False


def _report_unknown_keys(out: dict[str, Any], fields: frozenset[str]) -> None:
    unknown = [key for key in out if key not in fields and key not in NON_TECHNIQUE_KEYS and not key.startswith("_")]
    if not unknown:
        return
    vocabulary = sorted(fields | set(FIELD_ALIASES))
    parts_zh, parts_en = [], []
    for key in unknown:
        match = difflib.get_close_matches(key, vocabulary, n=1, cutoff=0.75)
        hint = FIELD_ALIASES.get(match[0], match[0]) if match else None
        parts_zh.append(f"`{key}`" + (f"（是不是 `{hint}`？）" if hint else ""))
        parts_en.append(f"`{key}`" + (f" (did you mean `{hint}`?)" if hint else ""))
    F.add_input_note(
        "这些参数不是本技法的参数，没有哪个设置读它们：" + "、".join(parts_zh) + "。",
        "These arguments are not parameters of this technique and no setting reads them: " + ", ".join(parts_en) + ".",
    )


def field_issues_error(issues: list[dict[str, Any]], *, extra_details: dict[str, Any] | None = None) -> ToolValidationError:
    """逐字段问题表 → 一个 ToolValidationError。code = 第一个问题的码；每个字段一条恢复条目（不是整份闸门问卷）。"""
    first = issues[0]
    must_ask = any(item.get("ask_user") for item in issues)
    message = "\n".join(item["message"] for item in issues)
    fix_fields = [{key: item[key] for key in ("field", "code", "got", "expected", "example", "options") if key in item} for item in issues]
    details: dict[str, Any] = {
        "field": first["field"], "got": first["got"], "expected": first["expected"], "example": first["example"],
        **({"options": first["options"]} if first.get("options") else {}),
        "fields": issues,
        **(extra_details or {}),
        "agent_recovery": {
            "kind": "input", "must_ask_user": must_ask, "reason": "invalid_field",
            "next_action": "ask_user_then_retry" if must_ask else "fix_field_and_retry",
            "fix_fields": fix_fields, "prompt_to_user": message,
            # 与闸门 / 地名错误同名的键：只列要问用户的那些字段（问题原文 + 候选），客户端按同一套逻辑把它念给用户。
            "ask_if_missing": [{"field": item["field"], "question": item["message"], **({"options": item["options"]} if item.get("options") else {})}
                               for item in issues if item.get("ask_user")],
        },
    }
    return ToolValidationError(message, code=first["code"], details=details)


def tool_error_from_validation(exc: Any, *, tool_name: str, payload: dict[str, Any] | None = None) -> ToolValidationError:
    """pydantic ValidationError（技法模型）→ 逐字段的结构化错误。缺字段：只有用户知道的事实标 ask_user；缺坐标的提示「或传 place」。
    `horosa_field` 类错误（词表 / parse_* 挂在 schema 上的 BeforeValidator）还原成它自己的码。"""
    from horosa_skill.errors import validation_errors

    issues: list[dict[str, Any]] = []
    for error in exc.errors(include_url=False):
        loc = [str(part) for part in error.get("loc", ())]
        field = ".".join(loc) or "(payload)"
        leaf = loc[-1] if loc else ""
        ctx = error.get("ctx") or {}
        if error.get("type") == "horosa_field":
            entry = {"field": field, "code": ctx.get("code", "tool.invalid_option"), "got": _jsonable(error.get("input")),
                     "expected": ctx.get("expected"), "example": ctx.get("example"), "ask_user": bool(ctx.get("ask_user")),
                     "message": ctx.get("message") or error.get("msg")}
            if ctx.get("options"):
                entry["options"] = ctx["options"]
        elif error.get("type") == "missing":
            entry = _missing_entry(field, leaf, tool_name, payload or {})
        else:
            entry = {"field": field, "code": "tool.invalid_payload", "got": _jsonable(error.get("input")),
                     "expected": error.get("msg"), "example": None, "ask_user": False,
                     "message": bilingual(f"`{field}` 不合法：{error.get('msg')}", f"`{field}` is invalid: {error.get('msg')}")}
        issues.append(entry)
    if not issues:
        issues.append({"field": "(payload)", "code": "tool.invalid_payload", "got": None, "expected": None, "example": None,
                       "ask_user": False, "message": bilingual(f"`{tool_name}` 的入参不合法。", f"Invalid payload for `{tool_name}`.")})
    codes = {item["code"] for item in issues}
    error = field_issues_error(issues, extra_details={"errors": validation_errors(exc)})
    if len(codes) > 1 or codes & {"tool.invalid_payload", "tool.missing_field"}:
        error = ToolValidationError(
            bilingual(f"`{tool_name}` 的入参不合法：", f"Invalid payload for tool `{tool_name}`:") + "\n" + str(error),
            code="tool.invalid_payload", details=error.details,
        )
    return error


_MISSING_TEXT: dict[str, tuple[str, str, Any]] = {
    "date": ("公历日期 YYYY-MM-DD", "the Gregorian date YYYY-MM-DD", "1990-05-03"),
    "time": ("钟表时刻 HH:MM:SS", "the clock time HH:MM:SS", "08:30:00"),
    "zone": ("时区：偏移 +08:00 或 IANA 名；或传 `place`（地名，连时区一起解析）", "the time zone: an offset such as +08:00 or an IANA name; or pass `place` (a place name also resolves the zone)", "+08:00"),
    "lat": ("纬度 31n13 / 31.22；或传 `place`（地名）", "the latitude 31n13 / 31.22; or pass `place` (a place name)", "31n13"),
    "lon": ("经度 121e28 / 121.47；或传 `place`（地名）", "the longitude 121e28 / 121.47; or pass `place` (a place name)", "121e28"),
    "gender": ("性别 1 男 / 0 女", "the gender, 1 male / 0 female", 1),
}


def _missing_entry(field: str, leaf: str, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    zh, en, example = _MISSING_TEXT.get(leaf, (f"`{leaf}`", f"`{leaf}`", None))
    ask = leaf in USER_FACT_FIELDS
    if leaf in ("lat", "lon") and not F.is_blank(payload.get("pos")) and F.is_blank(payload.get("place")):
        zh += f"（`pos`={payload.get('pos')!r} 只是盘头显示名，不解析坐标：要按地名起盘请传 `place`）"
        en += f" (`pos`={payload.get('pos')!r} is a display label only and is not resolved; pass `place` to resolve a place name)"
    resolution = payload.get("placeResolution") if isinstance(payload.get("placeResolution"), dict) else {}
    if leaf == "zone" and resolution.get("zone_source") == "not_filled_no_date":
        zh = "时区：给了 place，但这个技法没有日期，地名换算不出当天的 UTC 偏移（夏令时、历史改制）——请直接给 zone（如 +08:00）"
        en = "the time zone: place was given, but this technique has no date, so the place cannot be turned into that day's UTC offset; pass zone (e.g. +08:00)"
    if leaf in ("inner", "outer"):
        others = [key for key, value in payload.items() if isinstance(value, dict) and key not in ("inner", "outer")]
        zh = "合盘两人：inner = 第一人（本人）、outer = 第二人，各带 {date, time, zone, lat, lon}" + (f"；收到的 {others} 不是这两个键" if others else "")
        en = "the two people: inner = the first person, outer = the second, each {date, time, zone, lat, lon}" + (f"; {others} are not these keys" if others else "")
        example = {"date": "1990-05-03", "time": "08:00:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"}
        ask = False
    code = "tool.missing_field"
    if leaf == "time" and "time" in payload and F.is_blank(payload.get("time")):
        code = "tool.time_unknown"
    return {"field": field, "code": code, "got": None, "expected": bilingual(zh, en), "example": example, "ask_user": ask,
            "message": bilingual(f"缺 `{field}`：{zh}。", f"Missing `{field}`: {en}.")}


def _legacy_normalize(payload: Any) -> Any:
    """v0.49 及以前的宽松归一（只认得的写法补齐格式，认不出原样留下）。只用在当事人位置以外的引擎结构上。"""
    if isinstance(payload, list):
        return [_legacy_normalize(item) for item in payload]
    if not isinstance(payload, dict):
        return payload
    normalized = {key: _legacy_normalize(value) for key, value in payload.items()}
    _normalize_date_like_fields(normalized)
    _normalize_zone_fields(normalized)
    _normalize_coordinate_fields(normalized)
    _normalize_gender_field(normalized)
    return normalized


# 性别标签词表的唯一来源是 input_fields（service/_common._gender_label 经这两个名字读）。
_GENDER_MALE_LABELS = F.GENDER_MALE_LABELS
_GENDER_FEMALE_LABELS = F.GENDER_FEMALE_LABELS


def _normalize_gender_field(payload: dict[str, Any]) -> None:
    value = payload.get("gender")
    if isinstance(value, bool):
        payload["gender"] = 1 if value else 0
        return
    if not isinstance(value, str):
        return
    key = value.strip().lower()
    if key in _GENDER_MALE_LABELS:
        payload["gender"] = 1
    elif key in _GENDER_FEMALE_LABELS:
        payload["gender"] = 0


def _normalize_date_like_fields(payload: dict[str, Any]) -> None:
    for key in ("date", "datetime", "guaDate", "guaTime", "time"):
        if key not in payload:
            continue
        normalized = _normalize_date_like_value(key, payload.get(key))
        if normalized is not None:
            payload[key] = normalized


def _normalize_date_like_value(key: str, value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return text

    if key in {"date", "guaDate"}:
        return _normalize_date_value(text)
    if key in {"time", "guaTime"}:
        return _normalize_time_value(text)
    if key == "datetime":
        return _normalize_datetime_value(text)
    return text


def _normalize_date_value(text: str) -> str:
    match = _DATE_RE.match(text)
    if not match:
        return text
    year = int(match.group("year"))
    sign = "-" if match.group("year").startswith("-") else ""
    return f"{sign}{abs(year):04d}-{int(match.group('month')):02d}-{int(match.group('day')):02d}"


def _normalize_time_value(text: str) -> str:
    match = _TIME_RE.match(text)
    if not match:
        return text
    second = int(match.group("second") or "0")
    return f"{int(match.group('hour')):02d}:{int(match.group('minute')):02d}:{second:02d}"


def _normalize_datetime_value(text: str) -> str:
    match = _DATETIME_RE.match(text)
    if not match:
        return text
    date_text = _normalize_date_value(match.group("date"))
    time_text = _normalize_time_value(match.group("time"))
    separator = "T" if "T" in match.group("sep") else " "
    return f"{date_text}{separator}{time_text}"


def _normalize_zone_fields(payload: dict[str, Any]) -> None:
    for key in ("zone", "dirZone", "guaZone"):
        if key not in payload:
            continue
        normalized = _normalize_zone_value(payload.get(key), payload=payload, key=key)
        if normalized is not None:
            payload[key] = normalized


def _normalize_coordinate_fields(payload: dict[str, Any]) -> None:
    for value_key, gps_key, axis in (
        ("lat", "gpsLat", "lat"),
        ("lon", "gpsLon", "lon"),
        ("dirLat", None, "lat"),
        ("dirLon", None, "lon"),
        ("guaLat", None, "lat"),
        ("guaLon", None, "lon"),
    ):
        raw_value = payload.get(value_key)
        raw_decimal = _coerce_coordinate_decimal(raw_value)
        if raw_decimal is not None:
            payload[value_key] = _format_compact_coordinate(raw_decimal, axis=axis)

        if not gps_key:
            continue

        gps_value = payload.get(gps_key)
        gps_decimal = _coerce_coordinate_decimal(gps_value)
        if gps_decimal is None and raw_decimal is not None:
            payload[gps_key] = round(raw_decimal, 6)
        elif gps_decimal is not None:
            payload[gps_key] = round(gps_decimal, 6)
            if raw_value is None:
                payload[value_key] = _format_compact_coordinate(gps_decimal, axis=axis)


def _normalize_zone_value(value: Any, *, payload: dict[str, Any] | None = None, key: str = "zone") -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _format_zone_offset(float(value))

    text = str(value).strip()
    if not text:
        return text

    iana_offset = _normalize_iana_zone_value(text, payload=payload, key=key)
    if iana_offset is not None:
        return iana_offset

    offset_text = text.upper().replace("UTC", "").replace("GMT", "").strip()
    if offset_text in ("", "Z"):
        # Bare UTC / GMT / Z (and "UTC"/"GMT" alone) -> canonical zero offset.
        return "+00:00"
    if ":" not in offset_text:
        compact_match = re.fullmatch(r"(?P<sign>[+-]?)(?P<digits>\d{3,4})", offset_text)
        if compact_match:
            sign = compact_match.group("sign") or "+"
            digits = compact_match.group("digits")
            hours = int(digits[:-2])
            minutes = int(digits[-2:])
            if minutes < 60:
                return _format_zone_offset((-1 if sign == "-" else 1) * (hours + minutes / 60))
    match = _ZONE_HM_RE.match(offset_text)
    if not match:
        if _DECIMAL_RE.match(offset_text):
            return _format_zone_offset(float(offset_text))
        return str(value)

    sign = -1 if match.group("sign") == "-" else 1
    hours = int(match.group("hours"))
    minutes = int(match.group("minutes") or "0")
    if minutes >= 60:
        return str(value)
    total_hours = sign * (hours + minutes / 60)
    return _format_zone_offset(total_hours)


# 中国大陆统一北京时间口径（上游 utils/timezone.js:124-151 unifyCnZone，horosa_tz_cn_unified_v1）：IANA 把新疆
# 划为 Asia/Urumqi（+06:00，民间「新疆时间」），而出生证/户籍/医院记录一律按法定北京时间。统一时间起点
# （1949-10-01）之后 Asia/Urumqi → Asia/Shanghai，**只做 IANA 名归并、不写死偏移**（1986–1991 夏令时照常
# 得 +09:00；统一前的新疆出生仍按 +06:00）。归并时在载荷里留 geoZone（原地理时区）+ zoneAdvisory='cn-unified'，
# 技法卡与 warnings 据此回显。退出口：cnUnifiedZone=false（上游 kill-switch 是 localStorage 'horosa.tz.cnUnified'='0'），
# 或直接给偏移 "+06:00"（偏移不归并）。
_CN_UNIFIED_SINCE_YMD = (1949, 10, 1)
_CN_UNIFY = {"Asia/Urumqi": "Asia/Shanghai"}
_OPT_OUT_VALUES = (False, 0, "0", "false", "False", "no", "off")


def _cn_unified_enabled(payload: dict[str, Any]) -> bool:
    return payload.get("cnUnifiedZone") not in _OPT_OUT_VALUES


# 上游 utils/timezone.js TZ_RULE_OVERRIDES 的逐值抄本（v0.48.0）：IANA 新规先于 ICU / tzdata 落地时的前瞻覆盖——
# 当日（含）起恒为该偏移，只收「永久废除夏令时」类已立法规则。上游用它补 ICU，本仓用它补 zoneinfo（tzdata>=2025.2 的下限
# 早于 2026b/2026c，系统 tzdata 更旧）：否则同一个 IANA 名在 2026-11-01 之后比星阙选点差 1 小时。
# 守卫：tests/test_place_search.py 把本表与 vendored horosa-core-js/src/vendor/utils/timezone.js 逐条比对（vendored 文件
# 又由 revendor --from-manifest 锁到上游），上游改表 → re-vendor → 测试红 → 改这里。
_TZ_RULE_OVERRIDES: dict[str, tuple[tuple[tuple[int, int, int], str], ...]] = {
    "America/Edmonton": (((2026, 11, 1), "-06:00"),),
    "America/Vancouver": (((2026, 11, 1), "-07:00"),),
    "Africa/Casablanca": (((2026, 9, 20), "+00:00"),),
    "Africa/El_Aaiun": (((2026, 9, 20), "+00:00"),),
}


def _override_offset(zone: str, ymd: tuple[int, int, int]) -> str | None:
    for since, offset in _TZ_RULE_OVERRIDES.get(zone, ()):
        if ymd >= since:
            return offset
    return None


def _normalize_iana_zone_value(text: str, *, payload: dict[str, Any] | None, key: str) -> str | None:
    if "/" not in text:
        return None
    reference = _reference_datetime_for_zone(payload or {}, key)
    unified_from: str | None = None
    target = _CN_UNIFY.get(text)
    # 上游：只有能解析出 YYYY-MM-DD 且早于起点才不归并（日期缺失照样归并——但缺日期本仓也算不出偏移，
    # 下面 reference 为 None 时原样返回 None，不改 zone）。按 (年, 月, 日) 比较：strftime('%Y') 对四位以下的年
    # 不补零（平台相关），字符串比较会把公元 100 年判成「晚于 1949」。
    if (
        target
        and payload is not None
        and _cn_unified_enabled(payload)
        and reference is not None
        and reference[:3] >= _CN_UNIFIED_SINCE_YMD
    ):
        unified_from, text = text, target
    try:
        zone = ZoneInfo(text)
    except (ZoneInfoNotFoundError, ValueError):
        return None

    if reference is None:
        return None
    if unified_from is not None and payload is not None:
        payload.setdefault("geoZone", unified_from)
        payload["zoneAdvisory"] = "cn-unified"
    # 上游 offsetForZoneAtDate 先查覆盖表再问 Intl（同序）。
    override = _override_offset(text, reference[:3])
    if override is not None:
        return override
    wall = _wall_datetime_for_offset(reference)
    offset = wall.replace(tzinfo=zone).utcoffset() if wall is not None else None
    if offset is None:
        return None
    return _format_offset_seconds(offset.total_seconds())


def _wall_datetime_for_offset(reference: tuple[int, int, int, int, int, int]) -> datetime | None:
    """参照钟面 → datetime（只拿来问时区偏移）。年份按外推格里历读（上游 offsetForZoneAtDate 经 parseDateTimeMs 同口径）；
    datetime 只认 1–9999 年：公元前 / 五位年平移整 400 年（外推格里历 400 年 = 146097 天、星期与闰年分布逐日重合，
    时区规则得同一偏移；公元 1 年以前本就是地方平时 LMT）。2 月 29 日落在格里历平年 → 3 月 1 日（JS Date 同样进位）；
    其余不存在的日子（2 月 30 日、13 月…）→ None（上游 parseDateTimeParts 同样拒收）。"""
    year, month, day, hour, minute, second = reference
    if year < 1:
        year += 400 * ((1 - year + 399) // 400)
    elif year > 9999:
        year -= 400 * ((year - 9999 + 399) // 400)
    try:
        return datetime(year, month, day, hour, minute, second)
    except ValueError:
        if month == 2 and day == 29 and 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59:
            return datetime(year, 3, 1, hour, minute, second)
        return None


def _format_offset_seconds(total_seconds: float) -> str:
    """UTC 偏移秒数 → '±HH:MM'，秒数舍去（上游 offsetForZoneAtDate 读 Intl longOffset 'GMT+01:34:52' 只取时、分）。
    整分钟的时区与旧 round 口径逐字相同；地方平时（LMT，如雅典 +01:34:52、佛罗伦萨所在 Europe/Rome +00:49:56）
    旧 round 进成 +01:35 / +00:50，与上游差一分钟。"""
    sign = "+" if total_seconds >= 0 else "-"
    hours, minutes = divmod(int(abs(total_seconds)) // 60, 60)
    return f"{sign}{hours:02d}:{minutes:02d}"


def _reference_datetime_for_zone(payload: dict[str, Any], key: str) -> tuple[int, int, int, int, int, int] | None:
    if key == "guaZone":
        reference = _combine_date_time(payload.get("guaDate"), payload.get("guaTime"))
        if reference is not None:
            return reference
    if key == "dirZone":
        reference = _parse_datetime_text(payload.get("datetime"))
        if reference is not None:
            return reference
    return _combine_date_time(payload.get("date"), payload.get("time")) or _parse_datetime_text(payload.get("datetime"))


def _combine_date_time(date_value: Any, time_value: Any) -> tuple[int, int, int, int, int, int] | None:
    """(带符号显示年, 月, 日, 时, 分, 秒)；日期 / 时刻形状认不出、或数值越界（13 月、45 日、99 时）→ None。"""
    if date_value is None or time_value is None:
        return None
    date_text = str(date_value).strip()
    time_text = str(time_value).strip()
    date_match = _DATE_RE.match(date_text)
    time_match = _TIME_RE.match(time_text)
    if not date_match or not time_match:
        return None
    reference = (
        int(date_match.group("year")),
        int(date_match.group("month")),
        int(date_match.group("day")),
        int(time_match.group("hour")),
        int(time_match.group("minute")),
        int(time_match.group("second") or "0"),
    )
    # The regexes accept digit-shaped but calendar-invalid values (month 13, day 45,
    # hour 99, ...). Degrade like a regex miss instead of crashing normalization — the
    # backend will reject the bad date with a structured param error.
    return reference if _wall_datetime_for_offset(reference) is not None else None


def _parse_datetime_text(value: Any) -> tuple[int, int, int, int, int, int] | None:
    if value is None:
        return None
    text = str(value).strip()
    match = _DATETIME_RE.match(text)
    if not match:
        return None
    return _combine_date_time(match.group("date"), match.group("time"))


def _format_zone_offset(offset_hours: float) -> str:
    sign = "+" if offset_hours >= 0 else "-"
    total_minutes = round(abs(offset_hours) * 60)
    hours, minutes = divmod(total_minutes, 60)
    return f"{sign}{hours:02d}:{minutes:02d}"


# 上游 splitDegree 先把数字转成字符串再 parseInt 取度：|x| ≥ 1e21 时 JS 写成「1e+21」，度只剩首位数字（实测 convertLatToStr(1e21)
# = '1n06'）；非有限值（NaN / ±Infinity）上游一律当 0 → '0n00'（一个真实存在的位置）。两者都不是坐标——这里不换算、原样交给校验层
# 报 tool.invalid_payload（铁律：解析失败不许换成默认值），这是本节唯一一处有意不跟上游。
_COORDINATE_DOMAIN = 1e21


def _coerce_coordinate_decimal(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _in_coordinate_domain(float(value))

    text = str(value).strip()
    if not text:
        return None

    compact_match = _COMPACT_COORD_RE.match(text)
    if compact_match:
        degrees = float(compact_match.group(1))
        hemisphere = compact_match.group(2).lower()
        minutes = float(compact_match.group(3))
        decimal = degrees + minutes / 60
        if hemisphere in {"s", "w"}:
            decimal *= -1
        return _in_coordinate_domain(decimal)

    if _DECIMAL_RE.match(text):
        return _in_coordinate_domain(float(text))
    return None


def _in_coordinate_domain(value: float) -> float | None:
    return value if math.isfinite(value) and abs(value) < _COORDINATE_DOMAIN else None


def _js_math_round(value: float) -> int:
    """JS Math.round：最近的整数，恰在 .5 时向 +∞（Python round 是银行家舍入，floor(x + 0.5) 在 0.49999999999999994 上也会多进一）。"""
    floor = math.floor(value)
    return int(floor) + (1 if value - floor >= 0.5 else 0)


def _format_compact_coordinate(decimal_value: float, *, axis: str) -> str:
    """十进制度 → 罗盘串（31n13 / 121e28）。上游 components/astro/AstroHelper.js 的 convertLatToStr / convertLonToStr + splitDegree
    逐步同构（utils/aiTools/normalize/geoCompass.js 是它的逐字抄本）：方向按**原值**符号判（-0 与 0 都是北 / 东，-0.12 是南 / 西）；
    度取整；分**向下取整**；秒按 JS Math.round 取整；秒满 60 进 1 分、分满 60 进 1 度。旧实现把分四舍五入（31.2304 → 31n14，上游
    31n13），差 1′ 进起盘请求。地名解析（service/api/place.py）与一般十进制入参都走这一个函数；守卫：tests/test_coordinate_text.py
    （金标 = 上游 AstroHelper 在 node 里跑出）。"""
    hemisphere = ("s" if axis == "lat" else "w") if decimal_value < 0 else ("n" if axis == "lat" else "e")
    absolute = abs(decimal_value)
    degrees = int(absolute)
    minute = (absolute - degrees) * 60
    minutes = math.floor(minute)
    if _js_math_round((minute - minutes) * 60) == 60:
        minutes += 1
    if minutes == 60:
        degrees += 1
        minutes = 0
    return f"{degrees}{hemisphere}{minutes:02d}"
