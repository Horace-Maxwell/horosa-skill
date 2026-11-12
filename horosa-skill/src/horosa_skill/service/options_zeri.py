"""择日族共用的选项：搜索窗上限与校验、条件树白名单、explain 行数夹取。"""
from __future__ import annotations

import math
import re
from typing import Any

from horosa_skill.errors import ToolValidationError, bilingual, tool_code

# --- 天星择日 / 奇门择日 helpers ------------------------------------------------------------

# election_scan.ScanContext.eff 实际读取的口径键；白名单而非 **payload —— 否则 skill 自有的
# agent_confirmed_settings / response_view 之类会一起灌进引擎。
# 🔴 这份白名单必须覆盖后端**实读**的键，否则就是在客户端把已修好的后端 bug 重新装回去：
# election_scan.scan 走 `_cls_req = dict(data)` 整包下发（election_scan.py:1993），
# perchart.push_classical_request 从中实读 termsVariant / leoBoundFirst / geminiBoundEmended /
# customTermsDay / customTermsNight / triplicity / houseCuspAdvance / lotsDocReverse /
# nodeExaltation / dignityDebilities / orbSystem / luminaryOrbBonus 十二键
# （perchart.py:696-703），另有 ScanContext 读 height / partileDef、PerChart.__init__ 读
# cazimiOrb / combustOrb / underBeamsOrb 等。上游 [F8] 那条注释记的正是「dignityDebilities/
# orbSystem 等发了不生效」—— 后端已收编，而此处白名单窄 7 键，等于把它们又静默滤掉：
# schema 上带着描述、chart 工具上照常生效，唯独天星择日搜索里无声失效。
_ELECTIONSCAN_OPTION_KEYS = (
    "cazimiOrb", "combustOrb", "underBeamsOrb", "vocMode", "vocIncludeOuter", "viaCombustaVariant",
    "partileDef", "termsVariant", "triplicity", "sectBuffer", "houseCuspAdvance", "westNodeType",
    "height", "leoBoundFirst", "geminiBoundEmended",
    # push_classical_request 实读、此前被滤掉的七键：
    "nodeExaltation", "dignityDebilities", "lotsDocReverse", "orbSystem", "luminaryOrbBonus",
    "customTermsDay", "customTermsNight",
    # 上游 v3.11 起 ScanContext 实读的五键（election_scan.py:361-374）：[Q-418/T-381] 希腊点口径与主排盘
    # perchart._applyLotVariants 同式（福点反转 / 福点变体 / 赫尔墨斯六点反转）；[Q-268/T-254] 自定义恒星黄道
    # 'user' 档的历元 JD 与该历元岁差度。BirthInput 早已声明它们、chart 工具照常生效，唯独天星择日搜索被
    # 本白名单滤掉 —— 夜间点类判定与所见主盘相反、'user' 档扫描静默回落 Lahiri。
    "lotReversal", "lotFortuneVariant", "hermeticLotsReversal", "userAyanT0", "userAyanDeg",
)


# 天星择日窗口上限（天）。每段 = 一次串行后端扫描；再往上 splitByMonth 的 800 段 guard 会耗尽并
# **丢掉最后一段**，而结果仍会被报成完整搜索。取 2 年：60 段左右，已经很慢，但还不至于丢结果。
_TIANXING_MAX_SPAN_DAYS = 731

# 奇门择日窗口上限（天）。比引擎自带的 1830 天紧得多：区间搜索跑在 JS 子进程里，墙钟 60 秒
# （config.js_engine_timeout_seconds），而扫描约 2 秒/月窗 —— 引擎那个上限会把超时撑爆约 30 倍。
_QIMENZERI_MAX_SPAN_DAYS = 92


def _clamped_max_span(payload: dict[str, Any], cap: int) -> int:
    """把调用方给的 `maxSpanDays` **夹到**硬上限之内（v0.37.0 C7）。

    🔴 此前 `int(payload.get("maxSpanDays") or CAP)` 让 maxSpanDays 变成一个**能把上限抬高**的
    旋钮：传 5000 就真按 5000 天放行。上限不是礼貌建议——tianxing 的 731 天来自 splitByMonth 的
    800 次 guard（耗尽会**不 push 最后一段**就退出，尾部被丢却仍报成完整搜索），本地扫描的 92 天
    是扫描成本与客户端 600 秒工具超时的折中（扫描墙钟按窗口给，见 ZeriRunners._ZERI_SCAN_SECONDS_PER_DAY）。
    抬高上限只会把这两个失败模式换成「跑到超时」或「静默截断」，
    而调用方看到的仍是一个自称成功的结果。maxSpanDays 因此只保留「调**低**」这一半语义。
    非法/缺省值一律回落 cap；≤0 也回落（0 会让任何窗口都超限）。
    """
    raw = payload.get("maxSpanDays")
    if raw is None:
        return cap
    try:
        requested = int(raw)
    except (TypeError, ValueError):
        return cap
    if requested <= 0:
        return cap
    return min(requested, cap)


_WINDOW_FIELDS = ("startDate", "endDate")
_WINDOW_EXPECTED = bilingual("公历日期 YYYY-MM-DD（公元前写 -0500-03-21；时刻放 startTime / endTime）",
                             "a Gregorian date YYYY-MM-DD (BCE as -0500-03-21; put the clock time in startTime / endTime)")


def window_field_error(
    tool: str, code: str, zh: str, en: str, *, window: dict[str, Any], fields: tuple[str, ...] = _WINDOW_FIELDS,
    expected: str | None = None, example: Any = "2028-04-01", next_action: str | None = None, extra: dict[str, Any] | None = None,
) -> ToolValidationError:
    """择日族的入参问题 → 逐字段错误（每个相关字段一条恢复条目，kind=input），绝不是「重试 / doctor」的引擎故障（深审余项）。"""
    from horosa_skill.input_normalization import field_issues_error

    message = bilingual(zh, en)
    issues = [{"field": name, "code": code, "got": window.get(name), "expected": expected or _WINDOW_EXPECTED,
               "example": example, "ask_user": False, "message": message} for name in fields]
    error = field_issues_error(issues, extra_details={**window, **(extra or {})}, tool_name=tool)
    if next_action:
        error.details["agent_recovery"]["next_action"] = next_action
    return error


_OUT_OF_DOMAIN = re.compile(r"本地速算不适用|year -?\d+ is out of range|BC era not supported")


def zeri_engine_input_error(tool: str, label: str, engine_code: Any, message: Any, *, window: dict[str, Any]) -> ToolValidationError | None:
    """择日引擎（本地 JS 扫描或后端 /…scan）回报的失败里，哪些其实是入参问题 → 对应的逐字段错误；真故障返回 None。

    以前一律 `tool.<技法>_scan_failed` / `tool.<技法>_engine_failed` / `tool.electionscan_failed`（恢复建议：重试、跑 doctor）：
    公元前窗口、越过 9999 年、窗口读不出、条件树不合法都让调用方去重试一个注定再失败的请求。"""
    code, text = f"{engine_code or ''}".strip(), f"{message or ''}".strip()
    if _OUT_OF_DOMAIN.search(text):
        return window_field_error(
            tool, "tool.date_range_unsupported",
            f"{label}的历法引擎算不了这个搜索窗的年份（可靠域公元 1–9999 年）：{text}",
            f"{label}'s calendar engine cannot search that window (reliable range AD 1–9999): {text}",
            window=window, next_action="tell_user_unsupported",
            extra={"accepted": {"min_year": 1, "max_year": 9999}, "engine_code": code or None, "engine_message": text},
        )
    if code in ("invalid_date", "invalid_range", "invalid_time"):
        return window_field_error(
            tool, tool_code(tool, "bad_window"), f"{label}的搜索窗读不通：{text}", f"{label}: the search window is not usable: {text}",
            window=window, extra={"engine_code": code, "engine_message": text},
        )
    if code == "span_too_large":
        return window_field_error(
            tool, tool_code(tool, "span_too_large"), f"{label}的搜索窗太长：{text}", f"{label}: the search window is too long: {text}",
            window=window, next_action="split_window", extra={"engine_code": code, "engine_message": text},
        )
    if code == "invalid_coordinates":
        return window_field_error(
            tool, "tool.invalid_coordinate", f"{label}的经纬度读不通：{text}", f"{label}: the coordinates are not usable: {text}",
            window=window, fields=("lat", "lon"), expected=bilingual("纬度 31n13 / 31.22，经度 121e28 / 121.47", "lat 31n13 / 31.22, lon 121e28 / 121.47"),
            example="31n13", extra={"engine_code": code, "engine_message": text},
        )
    if code == "invalid_conditions":
        return window_field_error(
            tool, tool_code(tool, "invalid_conditions"), f"{label}的条件树不合法：{text}", f"{label}: the condition tree is invalid: {text}",
            window=window, fields=("conditions",), expected=bilingual("条件类键与参数见本工具的 agent_guidance", "condition keys and params: see this tool's agent_guidance"),
            example=None, extra={"engine_code": code, "engine_message": text},
        )
    return None


def _require_sane_window(
    start_date: str, end_date: str, *, max_span: int, tool: str, span_hint: str | None = None, lunar_js: bool = False,
) -> None:
    """搜索窗必须可解析、非倒置、不超上限 —— 三者缺一都不能放行（错误逐字段：startDate / endDate 各一条恢复条目）。

    🔴 `startDate`/`endDate` **不经** normalize_request_payload（它只管 date/time 等，见
    input_normalization），所以 agent 传什么就是什么。旧实现用 `_day_span(...) is not None` 判，
    于是 `'2026-08-05 10:00'` / `'2026-08-05T00:00'` 这类解析不出来的形状**直接跳过上限**——
    而 JS 侧 wallToMs 照样能解析它们，于是超长窗口一路跑到超时。解析失败必须报错，不是放行。
    倒置窗口（end < start）得负数，`负数 > max` 恒 False，同样能溜过去。
    """
    window = {"startDate": start_date, "endDate": end_date}
    span = _day_span(start_date, end_date)
    if span is None:
        raise window_field_error(
            tool, tool_code(tool, "bad_window"), f"{tool} 无法解析搜索窗日期（需 YYYY-MM-DD）。",
            f"{tool}: the search window dates cannot be read (YYYY-MM-DD).", window=window,
            extra={"hint": "只接受 YYYY-MM-DD；时刻请用 startTime/endTime 单独给。"},
        )
    if span < 0:
        raise window_field_error(
            tool, tool_code(tool, "inverted_window"), f"{tool} 搜索窗倒置：结束日期早于起始日期。",
            f"{tool}: the search window is inverted (end before start).", window=window,
            next_action="swap_window_bounds", extra={"span_days": span},
        )
    if span > max_span:
        raise window_field_error(
            tool, tool_code(tool, "span_too_large"), f"{tool} 搜索窗 {span} 天超过上限 {max_span} 天。",
            f"{tool}: the search window of {span} days exceeds the {max_span}-day limit.", window=window,
            next_action="split_window",
            extra={
                "span_days": span, "max_span_days": max_span,
                # 上限是硬的：maxSpanDays 只能调低（_clamped_max_span），提示不再暗示可以调高，
                # 否则 agent 会照着重试、再被同一条错误挡回来，白烧一轮往返。
                "max_span_days_cap": max_span,
                "hint": span_hint or "把窗口拆成多段分别搜索；每段都是一次串行后端扫描，窗口越长越慢。"
                                     "maxSpanDays 只能调低，不能超过本上限。",
            },
        )
    if lunar_js:
        # 本地扫描引擎跑在 lunar-javascript 上（可靠域公元 1–9999 年，上游 lunarDomainGuard：域外不报错、节气错位、干支静默算错）。
        # 以前奇门 / 八字 / 太乙 / 六壬择时报「搜索失败（重试 / doctor）」，黄历择吉报「须给起止日期」，紫微 / 三式择时照样出结果。
        from horosa_skill.civil_calendar import (
            LUNAR_JS_MAX_YEAR,
            LUNAR_JS_MIN_YEAR,
            _parse_date_parts,
        )

        years = [parts[0] for parts in (_parse_date_parts(start_date), _parse_date_parts(end_date)) if parts]
        if any(not LUNAR_JS_MIN_YEAR <= year <= LUNAR_JS_MAX_YEAR for year in years):
            raise window_field_error(
                tool, "tool.date_range_unsupported",
                f"{tool} 的本地扫描引擎（lunar-javascript）只算公元 {LUNAR_JS_MIN_YEAR}–{LUNAR_JS_MAX_YEAR} 年：搜索窗 {start_date} → {end_date} 在域外。",
                f"{tool} scans on a local calendar engine (lunar-javascript) that only covers AD {LUNAR_JS_MIN_YEAR}–{LUNAR_JS_MAX_YEAR}: "
                f"the window {start_date} → {end_date} is outside it.",
                window=window, next_action="tell_user_unsupported",
                extra={"accepted": {"min_year": LUNAR_JS_MIN_YEAR, "max_year": LUNAR_JS_MAX_YEAR}, "engine": "lunar-javascript"},
            )


def _electionscan_options(options: Any) -> dict[str, Any]:
    if not isinstance(options, dict):
        return {}
    return {k: options[k] for k in _ELECTIONSCAN_OPTION_KEYS if options.get(k) is not None}


# [Q-452 裁决 A / Q-453 裁决] 择日十宿主 + 天星 AI 快照的「命中清单」两旋钮（上游 utils/zeriSnapshotPrefs.js）：
# 清单上限缺省 60 行（10–500）、前 N 行附判读树缺省 3（0–20，0=不附）。归一由 JS 侧 vendored 同名
# normalize* 完成，Python 原样透传 builder 自己的键名 maxRows/explainRows（跨边界不改键）。
def _zeri_snapshot_row_opts(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if payload.get("zeriSnapshotMaxRows") is not None:
        out["maxRows"] = payload["zeriSnapshotMaxRows"]
    if payload.get("zeriSnapshotExplainRows") is not None:
        out["explainRows"] = payload["zeriSnapshotExplainRows"]
    return out


# 后端扫描家族（天星/七政/印度）的判读树要由宿主**预取**（上游 prefetchSnapshotExplains），Python 得先知道
# 要打几次 /explain —— 这里与 zeriSnapshotPrefs.normalizeZeriSnapshotExplainRows 的 clampInt 同式
# （缺省 3、夹到 [0, 20]、向下取整、非数回缺省）；与 JS 归一的逐值一致由 test_sync311_divination 对拍锚定。
_ZERI_EXPLAIN_ROWS_DEFAULT, _ZERI_EXPLAIN_ROWS_MIN, _ZERI_EXPLAIN_ROWS_MAX = 3, 0, 20


def _zeri_explain_rows(payload: dict[str, Any]) -> int:
    raw = payload.get("zeriSnapshotExplainRows")
    if raw is None or str(raw).strip() == "":
        return _ZERI_EXPLAIN_ROWS_DEFAULT
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return _ZERI_EXPLAIN_ROWS_DEFAULT
    if not math.isfinite(value):
        return _ZERI_EXPLAIN_ROWS_DEFAULT
    return max(_ZERI_EXPLAIN_ROWS_MIN, min(_ZERI_EXPLAIN_ROWS_MAX, math.floor(value)))


_ZONE_OFFSET_RE = re.compile(r"[+-]?\d{1,2}:\d{2}(?::\d{2})?")


def _electionscan_zone(zone: Any) -> str:
    """election_scan 期望 '+08:00' 形状；skill 的 zone 常是数字小时（8 / -5 / 5.5）。

    认不出就拒：曾静默回落 +08:00，`zone="New York"` 按东八区搜出一整张窗口表，ok=True，回显还写着 New York。
    IANA 名到这里已由 input_normalization 按盘面日期换成偏移，还留着名字说明它解析不了（AGENTS §5.3 第 9 条）。
    """
    if zone is None:
        return "+08:00"
    text = str(zone).strip()
    if _ZONE_OFFSET_RE.fullmatch(text):
        return text
    try:
        hours = float(text)
    except ValueError:
        hours = math.nan
    if not math.isfinite(hours):
        raise ToolValidationError(
            bilingual(f"认不出时区：{zone!r}。", f"Unrecognized time zone: {zone!r}."),
            code="tool.invalid_zone",
            details={"zone": zone, "accepted_forms": ["+08:00", "-05:00", "8", "Asia/Shanghai"]},
        )
    sign = "-" if hours < 0 else "+"
    total = int(round(abs(hours) * 60))
    return f"{sign}{total // 60:02d}:{total % 60:02d}"


def _day_span(start_date: str, end_date: str) -> int | None:
    """两端日期相隔的民用历日数（后端 election_scan._jd_from 同口径：1582-10-15 以前儒略历、公元前历史纪年）。
    旧实现 split('-') + datetime.date：公元前 '-0500-03-21' 撕成 ['', '0500', …] → 恒报「无法解析搜索窗」，
    五位年 / 跨改历缺口按外推格里历数差十天。日期不存在（2 月 30 日、改历缺口 1582-10-05…14）仍 → None。"""
    from horosa_skill.civil_calendar import (
        _civil_jdn,
        _civil_ymd_exists,
        _parse_date_parts,
    )

    def parse(text: str) -> float | None:
        s = f"{text}".strip()
        parts = _parse_date_parts(s) if s and not any(ch.isspace() for ch in s) else None  # 带时刻尾巴照旧拒收
        if parts is None or not _civil_ymd_exists(*parts):
            return None
        return _civil_jdn(*parts)

    a, b = parse(start_date), parse(end_date)
    return None if a is None or b is None else round(b - a)
