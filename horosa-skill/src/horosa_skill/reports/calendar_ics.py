"""日历导出（报告 format=ics，RFC 5545）：把已存结果里**现成的**日期写成 VEVENT。

铁律 1（不手算）：这里不算任何日期。每个事件的起止都是结果里写着的值——择日的命中区间（start / end）、候选时刻、
推运各期的起日（止日 = 结果里下一期的起日，或结果自己给的止日）、星历事件的时刻。唯一的运算是把结果自己的本地时间按结果
自己的时区换成 UTC（DTSTART / DTEND 写 UTC），全天事件用 DATE（不带时区）。结果里同一时刻另有绝对值（JD / 毫秒时间戳）时
逐个对照，差一分钟以上就不收这一条（与盘图「正文与数据对不上就不画」同一条规矩）。
年份必须在 0001–9999（RFC 5545 DATE 只能写四位年）：公元前、五位年一律跳过并在 skipped 里说明。

支持的工具见 `CALENDAR_TOOLS`；其余工具（含只有年龄段 / 只有目标时刻、日期只在正文文字里的）没有日历内容，由调用方拒绝。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from horosa_skill.reports.figures import _BODY_LABELS, _SIGN_IDS, _SIGN_LABELS

PRODID = "-//Horosa//Horosa Skill//ZH"
_INSTANT_TOLERANCE = timedelta(seconds=60)
_JD_UNIX_EPOCH = 2440587.5

_PLANETS = {
    "Sun": "太阳", "Moon": "月亮", "Mercury": "水星", "Venus": "金星", "Mars": "火星", "Jupiter": "木星", "Saturn": "土星",
    "Uranus": "天王星", "Neptune": "海王星", "Pluto": "冥王星", "North Node": "北交点", "South Node": "南交点",
}
_POINTS = {**_BODY_LABELS, "Asc": "上升", "MC": "中天"}
_SIGNS = dict(zip(_SIGN_IDS, _SIGN_LABELS))
_PHASES = {"New Moon": "朔", "First Quarter": "上弦", "Full Moon": "望", "Last Quarter": "下弦"}
_ECLIPSE_TYPES = {"total": "全食", "annular": "环食", "partial": "偏食", "hybrid": "全环食", "penumbral": "半影食"}
_STATIONS = {"Retrograde": "留逆", "Direct": "留顺"}


@dataclass(frozen=True)
class CalendarEvent:
    summary: str
    description: str
    start: date | datetime  # datetime 一律是 UTC（aware）；date 是全天事件
    end: date | datetime | None = None  # 全天事件的 end 是排他止日（RFC 5545 DTEND;VALUE=DATE）
    duration_days: int | None = None  # 全天事件没有止日、结果给了天数时


@dataclass
class CalendarExtraction:
    events: list[CalendarEvent] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


@dataclass
class _Context:
    tool_name: str
    data: dict[str, Any]
    input_normalized: dict[str, Any]
    label: str
    run_id: str
    out: CalendarExtraction

    def sections(self) -> list[dict[str, Any]]:
        snapshot = self.data.get("export_snapshot") if isinstance(self.data.get("export_snapshot"), dict) else {}
        return [s for s in snapshot.get("sections") or [] if isinstance(s, dict)]

    def section(self, *titles: str, startswith: str | None = None) -> str:
        for item in self.sections():
            title = str(item.get("title") or "")
            if title in titles or (startswith and title.startswith(startswith)):
                return str(item.get("body") or "")
        return ""

    def skip(self, what: str, why: str) -> None:
        self.out.skipped.append(f"{what}：{why}")


# ───────────────────────────── 解析（只读，不推算） ─────────────────────────────

_LOCAL_RE = re.compile(r"^(-?)(\d{4,})[-/](\d{1,2})[-/](\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?)?$")
_ZONE_RE = re.compile(r"^(?:UTC|GMT)?\s*([+-])(\d{1,2}):?(\d{2})$")


class _Unusable(ValueError):
    """这一个日期 / 时区不能写进日历（原因是给人读的中文）。"""


def _parse_local(text: Any) -> date | datetime:
    """'YYYY-MM-DD' → date；'YYYY-MM-DD HH:MM[:SS]' → naive datetime。公元前 / 年份越界 / 坏日期 → _Unusable。"""
    match = _LOCAL_RE.match(str(text or "").strip())
    if not match:
        raise _Unusable(f"认不出的日期「{text}」")
    bce, year_text = match.group(1), match.group(2)
    year = int(year_text)
    if bce or year == 0:
        raise _Unusable(f"公元前日期「{text}」写不进日历（RFC 5545 只收 0001–9999 年）")
    if year > 9999:
        raise _Unusable(f"年份「{text}」超出 0001–9999")
    try:
        day = date(year, int(match.group(3)), int(match.group(4)))
        if match.group(5) is None:
            return day
        return datetime(day.year, day.month, day.day, int(match.group(5)), int(match.group(6)), int(match.group(7) or 0))
    except ValueError as exc:
        raise _Unusable(f"不是合法日期「{text}」") from exc


def parse_zone(value: Any) -> timezone:
    """结果里的时区：'+08:00' / '-05:00' / '+0800' / 数字小时（8、-5、5.5）。认不出 → _Unusable。"""
    text = str(value if value is not None else "").strip()
    match = _ZONE_RE.match(text)
    if match:
        minutes = int(match.group(2)) * 60 + int(match.group(3))
        minutes = -minutes if match.group(1) == "-" else minutes
    else:
        try:
            minutes = round(float(text) * 60)
        except ValueError as exc:
            raise _Unusable(f"认不出时区「{value}」") from exc
    if abs(minutes) >= 24 * 60:
        raise _Unusable(f"时区「{value}」超出 ±24 小时")
    return timezone(timedelta(minutes=minutes))


def _utc(local: datetime, zone: timezone) -> datetime:
    try:
        moment = local.replace(tzinfo=zone).astimezone(timezone.utc)
    except OverflowError as exc:
        raise _Unusable(f"「{local:%Y-%m-%d %H:%M}」换成 UTC 后超出 0001–9999 年") from exc
    return moment


def _jd_instant(jd: Any) -> datetime | None:
    try:
        value = float(jd)
    except (TypeError, ValueError):
        return None
    try:
        return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(days=value - _JD_UNIX_EPOCH)
    except OverflowError:
        return None


def _ms_instant(ms: Any) -> datetime | None:
    try:
        return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=float(ms))
    except (TypeError, ValueError, OverflowError):
        return None


def _timed(text: Any, zone: timezone, *, check: datetime | None = None) -> datetime:
    """本地时刻 → UTC；结果另给了同一时刻的绝对值（check）就对照，差一分钟以上 → _Unusable（两处对不上不收）。"""
    local = _parse_local(text)
    if not isinstance(local, datetime):
        raise _Unusable(f"「{text}」只有日期没有时刻")
    moment = _utc(local, zone)
    if check is not None and abs(moment - check) > _INSTANT_TOLERANCE:
        raise _Unusable(f"「{text}」与结果里的绝对时刻（{check:%Y-%m-%d %H:%M} UTC）对不上")
    return moment


def _day(text: Any) -> date:
    value = _parse_local(text)
    return value.date() if isinstance(value, datetime) else value


def _section_entries(body: str) -> dict[int, tuple[str, list[str]]]:
    """「1. 头行」+ 其后缩进行 → {序号: (头行, [缩进行])}（择日命中清单的版式）。"""
    entries: dict[int, tuple[str, list[str]]] = {}
    current: int | None = None
    for line in body.splitlines():
        match = re.match(r"^(\d+)\.\s+(.*)$", line)
        if match:
            current = int(match.group(1))
            entries[current] = (match.group(2).strip(), [])
        elif current is not None and line.startswith((" ", "\t", "\u3000")) and line.strip():
            entries[current][1].append(line.strip())
        elif line.strip():
            current = None
    return entries


def _is_separator(line: str) -> bool:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return line.strip().startswith("|") and all(c and set(c) <= set("-: ") for c in cells)


def _table_lines(body: str, needle: str) -> list[str]:
    """正文里含 needle 的第一行：管道表格行写成「表头：值；…」（表头取该表自己的表头行），普通行原样。找不到返回 []。"""
    lines = body.splitlines()
    header: list[str] | None = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("|"):
            header = None  # 表格之外的行：下一张表另有表头
            if needle in stripped:
                return [stripped]
            continue
        if _is_separator(stripped):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if index + 1 < len(lines) and _is_separator(lines[index + 1]):
            header = cells
            continue
        if needle in stripped:
            if header and len(header) == len(cells):
                return ["；".join(f"{h}：{v}" for h, v in zip(header, cells) if v and v != "—")]
            return ["；".join(c for c in cells if c)]
    return []


def _source_line(ctx: _Context) -> str:
    return f"来源：星阙 Horosa · {ctx.label} · run {ctx.run_id}"


def _describe(*parts: Any) -> str:
    return "\n".join(str(p).strip() for p in parts if p and str(p).strip())


# ───────────────────────────── 择日 ─────────────────────────────

ZERI_TOOLS = frozenset({
    "tianxing", "qimenzeri", "huanglizeri", "bazizeri", "taiyizeri", "ziweizeri", "liurengzeri", "sanshizeri",
    "qizhengzeri", "indiazeri",
})
_ZERI_HIT_SECTIONS = ("命中日段", "命中时段", "命中时辰", "命中区间")
_ZERI_RULE_SECTIONS = ("择吉条件", "择时条件", "择日条件", "征象条件")
_ZERI_BADGES = ("badge", "pillarText", "keText", "chuanText", "mingText", "juText", "taiyiText", "sanshiText")


def _zeri(ctx: _Context) -> None:
    intervals = [iv for iv in ctx.data.get("intervals") or [] if isinstance(iv, dict)]
    if not intervals:
        return
    hits = _section_entries(ctx.section(*_ZERI_HIT_SECTIONS))
    rules = ctx.section(*_ZERI_RULE_SECTIONS)
    config = next((str(s.get("body") or "") for s in ctx.sections() if str(s.get("title") or "").endswith("搜索配置")), "")
    try:
        # 时区 = 扫描用的那个（入参缺省时扫描本身按 +08:00 跑，见 options_zeri._electionscan_zone）；本地扫描的区间另带毫秒时间戳、
        # 天星带 JD，逐条对照，时区读错就对不上、不收。
        zone = parse_zone(ctx.input_normalized.get("zone") or "+08:00")
    except _Unusable as exc:
        ctx.skip("全部命中", str(exc))
        return
    total = len(intervals)
    for index, interval in enumerate(intervals, start=1):
        start_text, end_text = interval.get("start"), interval.get("end")
        badge = "·".join(str(interval[k]) for k in _ZERI_BADGES if interval.get(k))
        header, reasons = hits.get(index, ("", []))
        if start_text and str(start_text) not in header:
            header, reasons = "", []  # 正文第 index 条不是这一段：不配判读
        summary = f"{ctx.label} 命中 {index}/{total}" + (f" {badge}" if badge else "")
        description = _describe(
            f"{ctx.label} · 命中第 {index} 段（共 {total} 段）",
            (f"日期（结果原文）：{start_text} ~ {end_text}" if len(str(start_text or "")) <= 10
             else f"时段（结果原文，{_zone_text(zone)}）：{start_text} ~ {end_text}"),
            f"条件：{rules}" if rules else "",
            "\n".join(reasons),
            config,
            _source_line(ctx),
        )
        try:
            if len(str(start_text or "")) <= 10:  # 日粒度（黄历择吉）：全天事件，天数取结果的 days
                first = _day(start_text)
                last = _day(end_text or start_text)
                days = interval.get("days")
                if last == first:
                    span = 1
                elif isinstance(days, int) and days > 0:
                    span = days
                else:
                    raise _Unusable("多日命中缺天数（days）")
                ctx.out.events.append(CalendarEvent(summary, description, first, duration_days=span))
                continue
            start = _timed(start_text, zone, check=_ms_instant(interval.get("startMs")) if interval.get("startMs") is not None
                           else _jd_instant(interval.get("startJd")))
            end = _timed(end_text, zone, check=_ms_instant(interval.get("endMs")) if interval.get("endMs") is not None
                         else _jd_instant(interval.get("endJd"))) if end_text else None
            ctx.out.events.append(CalendarEvent(summary, description, start, end))
        except _Unusable as exc:
            ctx.skip(f"命中 {index}", str(exc))


def _zone_text(zone: timezone) -> str:
    offset = zone.utcoffset(None) or timedelta(0)
    minutes = int(offset.total_seconds() // 60)
    sign = "-" if minutes < 0 else "+"
    return f"UTC{sign}{abs(minutes) // 60:02d}:{abs(minutes) % 60:02d}"


def _election(ctx: _Context) -> None:
    """天星择日盘（chart_election）：评估的就是一个候选时刻，引擎回显在 raw.params.birth / zone，JD 在 chart.date.jd。"""
    params = ((ctx.data.get("raw") or {}).get("params") or {}) if isinstance(ctx.data.get("raw"), dict) else {}
    moment_text = params.get("birth")
    if not moment_text:
        return
    judgment = ctx.data.get("judgment") if isinstance(ctx.data.get("judgment"), dict) else {}
    overall = judgment.get("overall") if isinstance(judgment.get("overall"), dict) else {}
    # 分数照结果自己的写法：总评段首行（「52/100　欠佳」）；没有这段才用 judgment.overall 的分数与等级。
    verdict = next((line.strip() for line in ctx.section("总评").splitlines() if line.strip()), "")
    score = verdict or " ".join(str(v) for v in (overall.get("score"), overall.get("gradeCn")) if v is not None and v != "")
    topic = str(judgment.get("topic") or "")
    jd = ((ctx.data.get("chart") or {}).get("date") or {}).get("jd") if isinstance(ctx.data.get("chart"), dict) else None
    try:
        start = _timed(moment_text, parse_zone(params.get("zone")), check=_jd_instant(jd))
    except _Unusable as exc:
        ctx.skip("候选时刻", str(exc))
        return
    summary = " ".join(part for part in (f"{ctx.label}·{topic}" if topic else ctx.label, score) if part)
    description = _describe(
        f"候选时刻（结果原文）：{moment_text} {params.get('zone') or ''}",
        ctx.section("总评"), ctx.section("红线"), ctx.section("建议"), _source_line(ctx),
    )
    ctx.out.events.append(CalendarEvent(summary, description, start))


def _qizhengelection(ctx: _Context) -> None:
    """七政择日：pan = 一个候选时刻；eclipses = 日 / 月食时刻；azimuthsearch = 星曜到达方位的时刻。时区 = 请求时区（起盘信息同写）。"""
    action = str(ctx.data.get("action") or "pan")
    try:
        zone = parse_zone(ctx.input_normalized.get("zone") or "+08:00")
    except _Unusable as exc:
        ctx.skip("全部时刻", str(exc))
        return
    if action == "pan":
        pan = ctx.data.get("pan") if isinstance(ctx.data.get("pan"), dict) else {}
        when = " ".join(str(ctx.input_normalized.get(k) or "") for k in ("date", "time")).strip()
        try:
            start = _timed(when.replace("/", "-"), zone, check=_jd_instant(pan.get("jdUt")))
        except _Unusable as exc:
            ctx.skip("候选时刻", str(exc))
            return
        ctx.out.events.append(CalendarEvent(f"{ctx.label} 候选时刻", _describe(
            f"候选时刻（结果原文）：{when} {_zone_text(zone)}", ctx.section("择日动盘"), ctx.section("天象要素"), _source_line(ctx)),
            start))
        return
    rows = ctx.data.get("eclipses") if action == "eclipses" else ctx.data.get("hits")
    body = ctx.section("日月食搜索" if action == "eclipses" else "方位搜索")
    head = body.splitlines()[0].strip() if body.strip() else ""
    for index, row in enumerate([r for r in rows or [] if isinstance(r, dict)], start=1):
        text = f"{row.get('date')} {row.get('time')}"
        lines = _table_lines(body, text)
        detail = lines[0].replace(text, "").strip(" \u3000") if lines else ""
        try:
            start = _timed(text, zone, check=_jd_instant(row.get("jd")))
        except _Unusable as exc:
            ctx.skip(f"第 {index} 条", str(exc))
            continue
        summary = " ".join(part for part in (ctx.label, head, detail) if part)
        ctx.out.events.append(CalendarEvent(summary, _describe(head, *lines, _source_line(ctx)), start))


# ───────────────────────────── 推运 / 星历 ─────────────────────────────


def _natal_zone(ctx: _Context, *paths: tuple[str, ...]) -> timezone:
    for path in paths:
        node: Any = ctx.data
        for key in path:
            node = node.get(key) if isinstance(node, dict) else None
        if node is not None:
            return parse_zone(node)
    raise _Unusable("结果里没有时区")


def _returntimeline(ctx: _Context) -> None:
    try:
        zone = _natal_zone(ctx, ("natal_params", "zone"))
    except _Unusable as exc:
        ctx.skip("返照时刻", str(exc))
        return
    body = ctx.section("太阳/月亮返照时间轴")
    for row in [r for r in ctx.data.get("rows") or [] if isinstance(r, dict)]:
        for key, name in (("solarReturn", "太阳返照"), ("lunarReturn", "月亮返照")):
            item = row.get(key) if isinstance(row.get(key), dict) else {}
            text = item.get("datetime")
            if not text:
                continue
            title = f"{name} {row.get('year')}" if key == "solarReturn" else f"{name}（{row.get('year')} 年首个）"
            try:
                start = _timed(text, zone, check=_jd_instant(item.get("jd")))
            except _Unusable as exc:
                ctx.skip(title, str(exc))
                continue
            ctx.out.events.append(CalendarEvent(f"{ctx.label} · {title}", _describe(
                f"{title}（结果原文，{_zone_text(zone)}）：{text}", *_table_lines(body, str(text)), _source_line(ctx)), start))


def _ephemeris_title(kind: str, item: dict[str, Any]) -> str:
    sign = _SIGNS.get(str(item.get("sign") or item.get("toSign") or ""), "")
    body = _PLANETS.get(str(item.get("body") or ""), str(item.get("body") or ""))
    if kind == "ingresses":
        return f"{body}入{_SIGNS.get(str(item.get('toSign')), str(item.get('toSign') or ''))}"
    if kind == "stations":
        return f"{body}{_STATIONS.get(str(item.get('direction')), str(item.get('direction') or '留'))}（{sign}）"
    if kind == "lunarPhases":
        return f"{_PHASES.get(str(item.get('phase')), str(item.get('phase') or ''))}（{sign}）"
    if kind == "eclipses":
        name = "日食" if item.get("type") == "solar_eclipse" else "月食"
        return f"{name}·{_ECLIPSE_TYPES.get(str(item.get('eclipseType')), str(item.get('eclipseType') or ''))}（{sign}）"
    transit = _POINTS.get(str(item.get("transitBody")), str(item.get("transitBody") or ""))
    natal = _POINTS.get(str(item.get("natalPoint")), str(item.get("natalPoint") or ""))
    aspect = item.get("aspect")
    aspect_text = f"{int(aspect)}°" if isinstance(aspect, (int, float)) else str(aspect or "")
    return f"行运{transit} {aspect_text} 本命{natal}"


def _ephemeris(ctx: _Context) -> None:
    eph = ctx.data.get("ephemeris") if isinstance(ctx.data.get("ephemeris"), dict) else {}
    try:
        zone = _natal_zone(ctx, ("natal_params", "zone"))
    except _Unusable as exc:
        ctx.skip("星历事件", str(exc))
        return
    events_body = ctx.section(startswith="星历事件")
    transit_body = ctx.section("行运触发本命")
    for kind in ("ingresses", "stations", "lunarPhases", "eclipses", "transitAspects"):
        for item in [i for i in eph.get(kind) or [] if isinstance(i, dict)]:
            text = item.get("datetime")
            title = _ephemeris_title(kind, item)
            try:
                start = _timed(text, zone, check=_jd_instant(item.get("jd")))
            except _Unusable as exc:
                ctx.skip(title, str(exc))
                continue
            rows = _table_lines(transit_body if kind == "transitAspects" else events_body, str(text))
            ctx.out.events.append(CalendarEvent(f"{ctx.label} · {title}", _describe(
                f"{title}（结果原文，{_zone_text(zone)}）：{text}", *rows, _source_line(ctx)), start))


def _periods(ctx: _Context, items: list[tuple[str, str, Any, Any]]) -> None:
    """[(标题, 说明, 起日, 止日或 None)] → 全天事件。止日缺 → 只标起日那一天（不拿时长去推止日）。"""
    for title, detail, start_text, end_text in items:
        try:
            first = _day(start_text)
            last = _day(end_text) if end_text else None
        except _Unusable as exc:
            ctx.skip(title, str(exc))
            continue
        if last is not None and last <= first:
            ctx.skip(title, f"止日 {end_text} 不晚于起日 {start_text}")
            continue
        tail = f"止 {end_text}（不含）" if last else "止日结果未给，只标起日"
        ctx.out.events.append(CalendarEvent(title, _describe(detail, f"起 {start_text} · {tail}", _source_line(ctx)),
                                            first, last, None if last else 1))


def _firdaria(ctx: _Context) -> None:
    flat: list[tuple[str, str, str]] = []
    for main in [m for m in ctx.data.get("firdaria") or [] if isinstance(m, dict)]:
        for sub in [s for s in main.get("subDirect") or [] if isinstance(s, dict)]:
            flat.append((str(main.get("mainDirect") or ""), str(sub.get("subDirect") or ""), str(sub.get("date") or "")))
    body = ctx.section("法达星限表格")
    items = []
    for index, (major, minor, start) in enumerate(flat):
        end = flat[index + 1][2] if index + 1 < len(flat) else None
        name = f"主限{_PLANETS.get(major, major)}·子限{_PLANETS.get(minor, minor)}"
        items.append((f"{ctx.label} · {name}", _describe(name, *_table_lines(body, start)), start, end))
    _periods(ctx, items)


def _zr(ctx: _Context) -> None:
    """黄道释放：L1 与 L2（引擎数据四层都有，日历只收两层；更细的层见正文 / JSON）。止日 = 同层下一期起日；末一期 L2 止于下一个 L1。"""
    level1 = [p for p in ctx.data.get("zr") or [] if isinstance(p, dict)]
    body = ctx.section("基于X点推运")
    items = []
    for i, period in enumerate(level1):
        next_start = level1[i + 1].get("date") if i + 1 < len(level1) else None
        sign = _SIGNS.get(str(period.get("sign")), str(period.get("sign") or ""))
        items.append((f"{ctx.label} · L1 {sign}", _describe(f"L1 {sign}，{period.get('days')} 天（结果原文）",
                                                            *_table_lines(body, f"{sign}-{period.get('date')}")),
                      period.get("date"), next_start))
        subs = [s for s in period.get("sublevel") or [] if isinstance(s, dict)]
        for j, sub in enumerate(subs):
            end = subs[j + 1].get("date") if j + 1 < len(subs) else next_start
            sub_sign = _SIGNS.get(str(sub.get("sign")), str(sub.get("sign") or ""))
            items.append((f"{ctx.label} · L2 {sign}/{sub_sign}", f"L1 {sign} · L2 {sub_sign}，{sub.get('days')} 天（结果原文）",
                          sub.get("date"), end))
    _periods(ctx, items)


def _decennials(ctx: _Context) -> None:
    """十年大运：L1 与 L2，起止取结果的 startText / endText（endText 即下一期起日）。"""
    timeline = ctx.data.get("timeline") if isinstance(ctx.data.get("timeline"), dict) else {}
    body = ctx.section("基于X起运")
    items = []
    for period in [p for p in timeline.get("list") or [] if isinstance(p, dict)]:
        planet = _PLANETS.get(str(period.get("planet")), str(period.get("planet") or ""))
        items.append((f"{ctx.label} · L1 {planet}", _describe(f"名义：{period.get('nominal')}" if period.get("nominal") else "",
                                                               *_table_lines(body, str(period.get("date") or "\0"))),
                      period.get("startText"), period.get("endText")))
        for sub in [s for s in period.get("sublevel") or [] if isinstance(s, dict)]:
            sub_planet = _PLANETS.get(str(sub.get("planet")), str(sub.get("planet") or ""))
            items.append((f"{ctx.label} · L2 {planet}/{sub_planet}", f"名义：{sub.get('nominal')}" if sub.get("nominal") else "",
                          sub.get("startText"), sub.get("endText")))
    _periods(ctx, items)


def _distributions(ctx: _Context) -> None:
    """界推运：分配星各期与伙伴星各期（起止是带时刻的本地时间，时区 = 本命盘时区）。"""
    header = ctx.data.get("natalHeader") if isinstance(ctx.data.get("natalHeader"), dict) else {}
    params = header.get("params") if isinstance(header.get("params"), dict) else {}
    try:
        zone = parse_zone(params.get("zone"))
    except _Unusable as exc:
        ctx.skip("界推运各期", str(exc))
        return
    main_body = ctx.section(startswith="界推运")
    partner_body = ctx.section("伙伴星期")
    rows: list[tuple[str, dict[str, Any], str]] = []
    for item in [d for d in ctx.data.get("distributions") or [] if isinstance(d, dict)]:
        rows.append((f"分配星{_PLANETS.get(str(item.get('distributor')), str(item.get('distributor') or ''))}"
                     f"·{_SIGNS.get(str(item.get('sign')), str(item.get('sign') or ''))}界", item, main_body))
    for item in [p for p in ctx.data.get("partners") or [] if isinstance(p, dict)]:
        rows.append((f"伙伴星{_PLANETS.get(str(item.get('planet')), str(item.get('planet') or ''))}", item, partner_body))
    for title, item, body in rows:
        try:
            start = _timed(item.get("startDate"), zone)
            end = _timed(item.get("endDate"), zone) if item.get("endDate") else None
        except _Unusable as exc:
            ctx.skip(title, str(exc))
            continue
        ctx.out.events.append(CalendarEvent(f"{ctx.label} · {title}", _describe(
            f"{title}（结果原文，{_zone_text(zone)}）：{item.get('startDate')} ~ {item.get('endDate')}",
            *_table_lines(body, str(item.get("startDate"))), _source_line(ctx)), start, end))


_EXTRACTORS: dict[str, Callable[[_Context], None]] = {
    **{name: _zeri for name in ZERI_TOOLS},
    "election": _election,
    "qizhengelection": _qizhengelection,
    "returntimeline": _returntimeline,
    "ephemeris": _ephemeris,
    "firdaria": _firdaria,
    "zr": _zr,
    "decennials": _decennials,
    "distributions": _distributions,
}
CALENDAR_TOOLS = frozenset(_EXTRACTORS)


def extract_calendar(tool_name: str, data: Any, *, input_normalized: dict[str, Any] | None, label: str,
                     run_id: str) -> CalendarExtraction:
    """结果 → 日历事件。不支持的工具、或结果里没有可用日期 → events 为空（调用方拒绝）。"""
    out = CalendarExtraction()
    extractor = _EXTRACTORS.get(tool_name)
    if extractor is None or not isinstance(data, dict):
        return out
    extractor(_Context(tool_name, data, input_normalized if isinstance(input_normalized, dict) else {}, label or tool_name,
                       run_id, out))
    return out


# ───────────────────────────── 写 RFC 5545 ─────────────────────────────


def escape_text(value: str) -> str:
    """TEXT 值转义（RFC 5545 §3.3.11）：反斜杠、分号、逗号、换行；其余控制字符删掉（TEXT 不许出现）。"""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(ch for ch in text if ch in "\n\t" or not (ord(ch) < 0x20 or ord(ch) == 0x7F))
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold_line(line: str) -> str:
    """按 75 个八位组折行（RFC 5545 §3.1）：续行以一个空格开头（空格算在 75 里），只在字符边界断，绝不拆开 UTF-8 多字节字符；
    转义对（\\n、\\; …）也不拆开（RFC 允许拆，但有的解析器先认转义再展开续行）。"""
    if len(line.encode("utf-8")) <= 75:
        return line
    tokens = re.findall(r"\\.|.", line, flags=re.DOTALL)
    parts: list[str] = []
    current, size, limit = "", 0, 75
    for token in tokens:
        width = len(token.encode("utf-8"))
        if size + width > limit:
            parts.append(current)
            current, size, limit = "", 0, 74
        current += token
        size += width
    parts.append(current)
    return "\r\n ".join(parts)


def _date_value(value: date) -> str:
    return f"{value.year:04d}{value.month:02d}{value.day:02d}"


def _utc_value(value: datetime) -> str:
    moment = value.astimezone(timezone.utc)
    return f"{_date_value(moment.date())}T{moment.hour:02d}{moment.minute:02d}{moment.second:02d}Z"


def render_ics(events: list[CalendarEvent], *, run_id: str, dtstamp: datetime, calendar_name: str,
               text: Callable[[str], str] = str) -> str:
    """VCALENDAR 全文（CRLF 行尾、已折行）。UID = run_id + 序号（同一次结果重导出 UID 不变，日历软件按 UID 更新而不是重复添加）。

    text：给人读的文字（SUMMARY / DESCRIPTION / 日历名）的转写函数（繁体输出时转字形）。"""
    stamp = _utc_value(dtstamp)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}", "CALSCALE:GREGORIAN",
             f"X-WR-CALNAME:{escape_text(text(calendar_name))}"]
    for index, event in enumerate(events, start=1):
        lines += ["BEGIN:VEVENT", f"UID:{run_id}-{index}@horosa-skill", f"DTSTAMP:{stamp}"]
        if isinstance(event.start, datetime):
            lines.append(f"DTSTART:{_utc_value(event.start)}")
            if isinstance(event.end, datetime) and event.end > event.start:
                lines.append(f"DTEND:{_utc_value(event.end)}")
        else:
            lines.append(f"DTSTART;VALUE=DATE:{_date_value(event.start)}")
            if isinstance(event.end, date) and not isinstance(event.end, datetime):
                lines.append(f"DTEND;VALUE=DATE:{_date_value(event.end)}")
            elif event.duration_days:
                lines.append(f"DURATION:P{int(event.duration_days)}D")
        lines += [f"SUMMARY:{escape_text(text(event.summary))}", f"DESCRIPTION:{escape_text(text(event.description))}",
                  "TRANSP:TRANSPARENT", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "".join(fold_line(line) + "\r\n" for line in lines)
