"""民用历日期口径（上游 utils/civilCalendar.js · dateTimeParse.js · dateStrSafe.js · zoneOffset.js 的同式移植）。

全仓单一 Python 出处，无本仓内依赖（engine / service 两层都可 import，不绕 service 包初始化）。
口径：1582-10-15 起格里历、此前儒略历（1582-10-04 的次日是 10-15）；年份按历史纪年（公元前 1 年 = -1，无 0 年），
日期串与 formatSignedDate 同形（负年前导负号、年不足 4 位补零、5 位原样）。Python datetime 恒为外推格里历且只认
1–9999 年：1582 年前跨 2 月底差一天、跨改历缺口差十天、公元前直接抛错——凡命盘日期算术一律走这里。
逐值对拍 vendored JS 的用例见 tests/test_sync313_ports.py、tests/test_sync313_historical.py。
"""
from __future__ import annotations

import math
import re
from typing import Any


def _js_math_round(value: float) -> int:
    """JS Math.round：half 一律向 +∞。"""
    return math.floor(value + 0.5)


# ── 民用历墙钟轴（上游 utils/civilCalendar.js + dateStrSafe.civilShiftDateTimeStr 的同式移植）────────────
# 上游 v3.13.0 起 shiftMoment / solveVedicSolarIngress 的「时刻 + N 天」一律走民用历墙钟轴：1582-10-15 起格里历、
# 此前儒略历（1582-10-04 的次日是 10-15），年份按历史纪年（公元前 1 年 = -1，无 0 年）；位移 = Math.round(天 × 86400000)
# 毫秒、落回时刻时秒向下取整。Python datetime 恒为外推格里历且只认 1–9999 年：1582 年前跨 2 月底差一天、跨改历缺口
# 差十天、公元前直接抛错。逐值对拍 vendored JS 的用例见 tests/test_sync313_ports.py（JS 改了这里就红）。
_GREG_START_YMD = (1582, 10, 15)
_UNIX_EPOCH_JDN = 2440588
_MS_PER_DAY = 86400000


def _swe_julday(year: float, month: float, day: float, hour: float, greg: bool) -> float:
    """civilCalendar.julday（Swiss Ephemeris swe_julday 逐式移植；年为天文年）。"""
    u = float(year)
    if month < 3:
        u -= 1
    u0 = u + 4712.0
    u1 = float(month) + 1.0
    if u1 < 4:
        u1 += 12.0
    jd = math.floor(u0 * 365.25) + math.floor(30.6 * u1 + 0.000001) + float(day) + float(hour or 0) / 24.0 - 63.5
    if greg:
        u2 = math.floor(abs(u) / 100) - math.floor(abs(u) / 400)
        if u < 0.0:
            u2 = -u2
        jd = jd - u2 + 2
        if u < 0.0 and u / 100 == math.floor(u / 100) and u / 400 != math.floor(u / 400):
            jd -= 1
    return jd


def _swe_revjul(jd: float, greg: bool) -> tuple[int, int, int]:
    """civilCalendar.revjul（swe_revjul 逐式移植）→ (天文年, 月, 日)。"""
    u0 = float(jd) + 32082.5
    if greg:
        u1 = u0 + math.floor(u0 / 36525.0) - math.floor(u0 / 146100.0) - 38.0
        if jd >= 1830691.5:
            u1 += 1
        u0 = u0 + math.floor(u1 / 36525.0) - math.floor(u1 / 146100.0) - 38.0
    u2 = math.floor(u0 + 123.0)
    u3 = math.floor((u2 - 122.2) / 365.25)
    u4 = math.floor((u2 - math.floor(365.25 * u3)) / 30.6001)
    mon = math.trunc(u4 - 1.0)
    if mon > 12:
        mon -= 12
    day = math.trunc(u2 - math.floor(365.25 * u3) - math.floor(30.6001 * u4))
    year = math.trunc(u3 + math.floor((u4 - 2.0) / 12.0) - 4800)
    return year, mon, day


def _civil_jdn(display_year: int, month: int, day: int, hour: float = 12) -> float:
    """civilJuldayDisplay：民用日期（历史纪年）→ 儒略日（hour=12 即 JDN）。"""
    astro = display_year + 1 if display_year < 0 else display_year
    greg = (astro, month, day) >= _GREG_START_YMD
    return _swe_julday(astro, month, day, hour, greg)


def _civil_ymd_of_jdn(jdn: float) -> tuple[int, int, int]:
    """civilYmdOfJdn：JDN → (历史纪年, 月, 日)。"""
    j = math.floor(jdn)
    astro, month, day = _swe_revjul(j, j >= 2299160.5)
    return (astro - 1 if astro <= 0 else astro), month, day


# dateTimeParse.js DATE_TIME_RE 逐字（re.ASCII = JS 的 \d / \s 只认 ASCII 数字）。
_DATE_TIME_RE = re.compile(
    r"^([+-]?\d{1,6})(?:([-/])(\d{1,2})(?:([-/])(\d{1,2}))?)?(?:(?:T|\s+)(\d{1,2}):(\d{1,2})(?::(\d{1,2})(?:[.,](\d+))?)?)?"
    r"\s*(Z|z|[+-]\d{2}(?::?\d{2})?)?$",
    re.ASCII,
)


def _greg_days_in_month(year: int, month: int) -> int:
    """dateTimeParse.daysInMonth：外推格里历（年按天文年读，与 Date#setUTCFullYear 同）。"""
    if month == 2:
        return 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28
    return 30 if month in (4, 6, 9, 11) else 31


def _parse_date_time_parts(text: Any) -> dict[str, Any] | None:
    """dateTimeParse.parseDateTimeParts 逐式移植：认不出 → None。年 1–6 位可带 ± 号、斜杠 / 横杠混用、T 或空白分隔时刻、
    小数秒与 Z / ±HH:MM 时区尾巴都认；2 月 29 日不论哪年都认（儒略历闰日）。返回 year 是带符号「显示年」原样。"""
    if not isinstance(text, str):
        return None
    s = text.strip()
    if not s:
        return None
    m = _DATE_TIME_RE.match(s)
    if not m:
        return None
    ys, sep1, ms1, sep2, ds, hs, mis, ss, frac, zone = m.groups()
    if sep1 is None and not re.fullmatch(r"(?:\d{4}|[+-]\d{4,6})", ys, re.ASCII):
        return None
    year = int(ys)
    month = int(ms1) if ms1 is not None else 1
    day = int(ds) if ds is not None else 1
    if month < 1 or month > 12:
        return None
    if day < 1 or (day > _greg_days_in_month(year, month) and not (month == 2 and day == 29)):
        return None
    has_time = hs is not None
    hour = int(hs) if has_time else 0
    minute = int(mis) if has_time else 0
    second = int(ss) if ss is not None else 0
    msec = int(f"{frac}00"[:3]) if frac is not None else 0
    if hour > 24 or minute > 59 or second > 59:
        return None
    if hour == 24 and (minute or second or msec):
        return None
    offset_min: int | None = None
    if zone:
        if zone in ("Z", "z"):
            offset_min = 0
        else:
            zm = re.match(r"^([+-])(\d{2}):?(\d{2})?$", zone)
            zh = int(zm.group(2)) if zm else 99
            zmin = int(zm.group(3)) if zm and zm.group(3) is not None else 0
            if zh > 23 or zmin > 59:
                return None
            offset_min = (-1 if zm.group(1) == "-" else 1) * (zh * 60 + zmin)
    # 严格 ISO 的纯日期：「YYYY」「YYYY-MM」「YYYY-MM-DD」（四位或带号六位扩展年、两位月日、只用「-」）
    iso_date_only = (
        not has_time and sep1 != "/" and sep2 != "/"
        and re.fullmatch(r"(?:\d{4}|[+-]\d{6})", ys, re.ASCII) is not None
        and (ms1 is None or len(ms1) == 2) and (ds is None or len(ds) == 2)
    )
    return {
        "year": year, "month": month, "day": day, "hour": hour, "minute": minute, "second": second, "ms": msec,
        "hasTime": has_time, "isoDateOnly": iso_date_only, "offsetMin": offset_min,
    }


def _civil_ymd_exists(year: int, month: int, day: int) -> bool:
    """civilCalendar.civilYmdExists：1582-10-05…14、儒略历以外的平年 2 月 29 日、年 0 → False。"""
    if year == 0:
        return False
    return _civil_ymd_of_jdn(_civil_jdn(year, month, day)) == (year, month, day)


def _civil_wall_ms(year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0) -> int:
    """civilCalendar.civilWallMs：民用日期时刻（历史纪年）→ 墙钟毫秒（1970-01-01 00:00 = 0，与 Unix 毫秒同轴）。"""
    jdn = int(_civil_jdn(year, month, day, 0) + 0.5)
    return (jdn - _UNIX_EPOCH_JDN) * _MS_PER_DAY + ((hour * 60 + minute) * 60 + second) * 1000


def _civil_wall_ms_of_moment(text: str, *, strict: bool = True) -> int | None:
    """dateStrSafe.civilWallMsOfStr（strict，缺省）/ civilMoment.momentOfCivilDateTimeStr 的墙钟毫秒（strict=False）。
    串经 `_parse_date_time_parts`（= parseDateTimeParts）拆；年为 0 → None；strict 时日期不存在（改历缺口 1582-10-05…14、
    平年 2 月 29 日）也 → None。串里写了时区也按钟面读（上游同）。"""
    p = _parse_date_time_parts(f"{text}") if text is not None else None
    if not p or p["year"] == 0:
        return None
    if strict and not _civil_ymd_exists(p["year"], p["month"], p["day"]):
        return None
    return _civil_wall_ms(p["year"], p["month"], p["day"], p["hour"], p["minute"], p["second"]) + p["ms"]


def _greg_jdn_of_ymd(astro_year: int, month: int, day: int) -> int:
    """civilCalendar.gregJdnOfYmd：外推格里历（天文年）年月日 → JDN。"""
    return int(_swe_julday(astro_year, month, day, 12, True))


def _local_offset_ms_at(astro_year: int, month: int, day: int, hour: int, minute: int, second: int) -> int:
    """本机时区在该外推格里历钟面上的 UTC 偏移（毫秒）：datetime 能表示的年份按本机时区规则取；公元 1 年以前 / 9999 年以后
    取 1 年 / 9999 年同一钟面的偏移（JS Date 对这些年份同样只按本机 tz 数据外推）。"""
    from datetime import datetime as _dt

    y = min(max(astro_year, 1), 9999)
    try:
        local = _dt(y, month, min(day, 28) if month == 2 else day, hour, minute, second).astimezone()
    except (ValueError, OverflowError, OSError):
        local = _dt.now().astimezone()
    offset = local.utcoffset()
    return int(offset.total_seconds() * 1000) if offset is not None else 0


def _parse_date_time_ms(text: Any) -> float | None:
    """dateTimeParse.parseDateTimeMs（字符串支）：写了时区按它；严格 ISO 纯日期 = UTC 0 点；其余按本机钟面。
    年份按天文年（与 ECMAScript 同；外推格里历）。认不出 → None（上游 NaN）。"""
    p = _parse_date_time_parts(text)
    if not p:
        return None
    jdn = _greg_jdn_of_ymd(p["year"], p["month"], 1) + (p["day"] - 1)
    utc_ms = (jdn - _UNIX_EPOCH_JDN) * _MS_PER_DAY + ((p["hour"] * 60 + p["minute"]) * 60 + p["second"]) * 1000 + p["ms"]
    if p["offsetMin"] is not None:
        return utc_ms - p["offsetMin"] * 60000
    if p["isoDateOnly"]:
        return utc_ms
    return utc_ms - _local_offset_ms_at(p["year"], p["month"], p["day"], p["hour"], p["minute"], p["second"])


def _civil_instant_ms_of_str(text: Any) -> float | None:
    """dateStrSafe.civilInstantMsOfStr：按 parseDateTimeMs 读钟面，再补「民用历与外推格里历同一标签」相差的整天数
    （1582 以前儒略历、公元前历史纪年；1582-10-15 以后为 0）。认不出 → None。"""
    s = f"{text if text is not None else ''}"
    ms = _parse_date_time_ms(s)
    if ms is None:
        return None
    p = _parse_date_parts(_date_part_of(s))
    if not p:
        return ms
    year, month, day = p
    if year == 0:
        return None  # civilJdnOfYmd(0, …) = NaN → 整个结果 NaN
    civil = _civil_jdn(year, month, day)
    greg = _swe_julday(year, month, day, 12, True)  # gregJdnOfYmd 把显示年当天文年读（与 parseDateTimeMs 同口径）
    return ms + (civil - greg) * _MS_PER_DAY


def _parse_date_parts(text: Any) -> tuple[int, int, int] | None:
    """dateStrSafe.parseDateParts：'YYYY-MM-DD' / '-YYYY/MM/DD' / 带时间尾巴 → (带符号年, 月, 日)；认不出 → None。"""
    if text is None:
        return None
    head = f"{text}".strip().split(" ")[0].replace("/", "-")
    m = re.match(r"^(-?)(\d{1,5})-(\d{1,2})-(\d{1,2})$", head, re.ASCII)
    if not m:
        return None
    year = (-1 if m.group(1) == "-" else 1) * int(m.group(2))
    month, day = int(m.group(3)), int(m.group(4))
    if month < 1 or month > 12 or day < 1 or day > 31:
        return None
    return year, month, day


def _format_signed_date(year: int, month: int, day: int, sep: str = "-") -> str:
    """dateStrSafe.formatSignedDate：负年前导负号、年不足 4 位补零、5 位原样。"""
    return f"{'-' if year < 0 else ''}{abs(int(year)):04d}{sep}{int(month):02d}{sep}{int(day):02d}"


def _civil_date_str_of_jdn(jdn: float, sep: str = "-") -> str:
    """dateStrSafe.civilDateStrOfJdn。"""
    year, month, day = _civil_ymd_of_jdn(jdn)
    return _format_signed_date(year, month, day, sep)


def _civil_date_str_of_ms(ms: float) -> str:
    """dateStrSafe.civilDateStrOfMs：毫秒（墙钟 / UTC）所在那一天的民用历日期串；非有限数 → ''。"""
    if ms is None or not math.isfinite(float(ms)):
        return ""
    return _civil_date_str_of_jdn(math.floor(float(ms) / _MS_PER_DAY) + _UNIX_EPOCH_JDN)


def _year_month_key(text: Any) -> str:
    """dateStrSafe.yearMonthKey：日期串 → 'YYYY-MM'（formatSignedDate 同形；替代 [:7]）；认不出 → ''。"""
    p = _parse_date_parts(text)
    if not p:
        return ""
    s = _format_signed_date(*p)
    return s[: s.rfind("-")]


def _month_day_label(text: Any) -> str:
    """dateStrSafe.monthDayLabel：日期串 → 'MM-DD'（替代 [5:10]）；认不出时原样返回。"""
    p = _parse_date_parts(text)
    return f"{p[1]:02d}-{p[2]:02d}" if p else f"{text if text is not None else ''}"


def _greg_ymd_of_jdn(jdn: float) -> tuple[int, int, int]:
    """civilCalendar.gregYmdOfJdn：JDN → 外推格里历 (天文年, 月, 日)（= moment / JS Date 眼里的「同一天」）。"""
    return _swe_revjul(math.floor(jdn), True)


def _to_slash_date(text: Any) -> str:
    """dateStrSafe.toSlashDate：只换数字之间的 '-'（公元前前导负号保留）。"""
    return re.sub(r"(\d)-(?=\d)", r"\1/", f"{text if text is not None else ''}")


def _leading_year_of(text: Any) -> int | None:
    """dateStrSafe.leadingYearOf：串首带符号年（'-0300-03-10' → -300）；取不到 → None（上游 NaN）。"""
    m = re.match(r"^\s*(-?\d{1,5})(?!\d)", f"{text if text is not None else ''}", re.ASCII)
    return int(m.group(1)) if m else None


def _zone_offset_minutes_of(zone: Any) -> int | None:
    """zoneOffset.zoneOffsetMinutesOf：'±HH[:MM]' / '±HHMM' / '±H' / 小时数 → 分钟；认不出 → None。"""
    if zone is None or zone == "" or isinstance(zone, bool):
        return None
    if isinstance(zone, (int, float)):
        return _js_math_round(zone * 60) if math.isfinite(zone) else None
    m = re.match(r"^([+-]?)(\d{1,2})(?::?(\d{2}))?$", f"{zone}".strip(), re.ASCII)
    if not m:
        try:
            n = float(f"{zone}".strip())
        except ValueError:
            return None
        return _js_math_round(n * 60) if math.isfinite(n) else None
    return (-1 if m.group(1) == "-" else 1) * (int(m.group(2)) * 60 + int(m.group(3) or 0))


def _chart_at_moment_date_fields(moment: Any) -> dict[str, Any]:
    """momentPipeline.chartAtMoment 的 {ad, date, time}：DateTime.parse(串, 'YYYY-MM-DD HH:mm:ss') 再
    format('YYYY/MM/DD') / format('HH:mm:ss')——前导 '-' = 公元前（ad=-1），年按整数写（不补零），月日时分秒补两位；
    缺时刻 = 12:00:00。纪元标志随时刻本身（不沿用本命盘 ad）。"""
    text = f"{moment if moment is not None else ''}".strip()
    parts = text.split(" ")
    dstr = parts[0]
    tmstr = parts[1] if len(parts) > 1 and parts[1] else "12:00:00"
    ad = 1
    if dstr.startswith("-"):
        ad = -1
        dstr = dstr[1:]
    dparts = dstr.split("/")
    if len(dparts) == 1:
        dparts = dstr.split("-")
    if len(dparts) == 1:
        dparts += ["01", "01"]
    tparts = tmstr.split(":")
    if len(tparts) == 2:
        tparts.append("00")
    try:
        year, month, day = (int(dparts[i]) for i in range(3))
        hour, minute, second = (int(tparts[i]) for i in range(3))
    except (ValueError, IndexError):
        return {"ad": ad, "date": _to_slash_date(text.split(" ")[0]), "time": tmstr}
    return {
        "ad": ad,
        "date": f"{ad * year}/{month:02d}/{day:02d}",
        "time": f"{hour:02d}:{minute:02d}:{second:02d}",
    }


def _ad_of_date(date_text: Any) -> int:
    """后端 civil_calendar.reset_ad_for_date 的判据：派生日期串带前导负号 = 公元前（-1），否则 1。"""
    return -1 if f"{date_text if date_text is not None else ''}".strip().startswith("-") else 1


def _civil_moment_of_wall_ms(ms: int) -> str:
    """civilDateTimeStrOfWallMs：墙钟毫秒 → 'YYYY-MM-DD HH:mm:ss'（formatSignedDate 同形：负年前导负号、年补足 4 位）。"""
    day_n = ms // _MS_PER_DAY
    rem = ms - day_n * _MS_PER_DAY
    year, month, day = _civil_ymd_of_jdn(day_n + _UNIX_EPOCH_JDN)
    hour, rem = divmod(rem, 3600000)
    minute, rem = divmod(rem, 60000)
    second = rem // 1000
    sign = "-" if year < 0 else ""
    return f"{sign}{abs(year):04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"


_DATE_HEAD_RE = re.compile(r"^\s*([+-]?\d{1,6}[-/]\d{1,2}[-/]\d{1,2})")


def _date_part_of(text: str) -> str:
    """dateStrSafe.datePartOf：日期时刻串的日期段（负年 / 五位年 / 斜杠原样）；认不出时退回前 10 个字符（上游旧口径）。"""
    s = f"{text if text is not None else ''}"
    match = _DATE_HEAD_RE.match(s)
    return match.group(1) if match else s[:10]


def _civil_shift_moment(moment: str, delta_ms: int) -> str:
    """dateStrSafe.civilShiftDateTimeStr：民用日期时刻串挪 delta_ms 毫秒；认不出 → ''。"""
    ms = _civil_wall_ms_of_moment(f"{moment or ''}".strip())
    return _civil_moment_of_wall_ms(ms + int(delta_ms)) if ms is not None else ""


def _shift_moment(moment: str, days: float) -> str:
    """把 'YYYY-MM-DD HH:MM:SS' 平移若干天（可为负）：上游 solunar.shiftMoment（v3.13.0）——民用历墙钟轴、
    位移 Math.round(天 × 86400000) 毫秒；认不出原样返回。"""
    out = _civil_shift_moment(f"{moment}", _js_math_round(days * 86400000))
    return out or f"{moment}"
