"""逐字段的入参理解（v0.50.0）：时区 / 时刻 / 日期 / 经纬度 / 性别 / 宫制 / 黄道。

每个 `parse_*` 只有两种结局：读懂了 → `Parsed(规范值, 说明)`（说明非空 = 这是「解读」出来的，要进 warnings）；读不懂 → `FieldIssue`
（带错误码、中英说明、可接受的写法、示例、可选的候选项）。**没有第三种**：认不出的值绝不原样往下传，也绝不换成缺省值。
`input_normalization.normalize_request_payload` 是唯一的调用方（全部技法、嵌套当事人、调度 / 合参 / 档案都经它）；
这里不 import service / surfaces，不碰引擎。引擎自己的宽容（把 `东八区` 当 +08:00、把 2 月 30 日进位）是上游行为，不在这里改。
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from horosa_skill.astro_rulers import HOUSE_SYSTEM_LABELS


@dataclass(frozen=True)
class Parsed:
    value: Any
    note_zh: str = ""
    note_en: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


class FieldIssue(Exception):
    """一个字段读不懂。`ask_user` = 缺的是只有用户知道的事实（要问用户，不是改写法）。"""

    def __init__(
        self, code: str, zh: str, en: str, *, expected_zh: str, expected_en: str, example: Any,
        options: list[Any] | None = None, ask_user: bool = False,
    ) -> None:
        super().__init__(zh)
        self.code, self.zh, self.en = code, zh, en
        self.expected_zh, self.expected_en, self.example = expected_zh, expected_en, example
        self.options, self.ask_user = options or [], ask_user


def clean_text(value: Any) -> str:
    """NFKC（全角 → 半角：＋０８：００、８点）+ 各种减号 / 破折号 → '-' + 去首尾空白。"""
    text = unicodedata.normalize("NFKC", f"{value}")
    return re.sub(r"[\u2212\u2012\u2013\u2014\u2015\ufe63\uff0d]", "-", text).strip()


def is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not clean_text(value))


_CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "兩": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _cn_number(text: str) -> int | None:
    """0–99 的中文数字（八、十、十二、二十、二十三、五十九）或阿拉伯数字 → int；别的 → None。"""
    if not text:
        return None
    if text.isascii() and text.isdigit():
        return int(text)
    if text in _CN_DIGITS:
        return _CN_DIGITS[text]
    if "十" in text and len(text) <= 3:
        head, _, tail = text.partition("十")
        tens = 1 if not head else _CN_DIGITS.get(head)
        ones = 0 if not tail else _CN_DIGITS.get(tail)
        if tens is None or ones is None or not 1 <= tens <= 9:
            return None
        return tens * 10 + ones
    return None


# ───────────────────────── 时区 ─────────────────────────

ZONE_MIN_MINUTES, ZONE_MAX_MINUTES = -12 * 60, 14 * 60
_ZONE_EXPECTED_ZH = "UTC 偏移 ±HH:MM（-12:00…+14:00），或小时数 8 / -5 / 5.5、UTC+8、东八区、E8 / W5，或 IANA 名 Asia/Shanghai"
_ZONE_EXPECTED_EN = "a UTC offset ±HH:MM (-12:00…+14:00), hours such as 8 / -5 / 5.5, UTC+8, 东八区, E8 / W5, or an IANA name such as Asia/Shanghai"

# 有唯一含义的地名式时区 → IANA 名（偏移随日期，由调用方按盘面日期换算；中国大陆 1986–1991 夏令时照常生效）。
ZONE_NAME_TO_IANA: dict[str, str] = {
    "北京时间": "Asia/Shanghai", "北京": "Asia/Shanghai", "中国标准时间": "Asia/Shanghai", "中国时间": "Asia/Shanghai",
    "beijing": "Asia/Shanghai", "beijing time": "Asia/Shanghai", "china standard time": "Asia/Shanghai", "prc": "Asia/Shanghai",
    "香港时间": "Asia/Hong_Kong", "hkt": "Asia/Hong_Kong", "台北时间": "Asia/Taipei", "台湾时间": "Asia/Taipei",
    "东京时间": "Asia/Tokyo", "日本时间": "Asia/Tokyo", "jst": "Asia/Tokyo", "首尔时间": "Asia/Seoul", "韩国时间": "Asia/Seoul", "kst": "Asia/Seoul",
    "新加坡时间": "Asia/Singapore", "sgt": "Asia/Singapore",
}
# 固定偏移的缩写（没有第二种通行读法）。
_ZONE_FIXED_ABBREVIATIONS: dict[str, int] = {"utc": 0, "gmt": 0, "ut": 0, "z": 0, "zulu": 0}
# 一词多义的缩写：拒，并把候选偏移交给调用方去问用户。
ZONE_AMBIGUOUS_ABBREVIATIONS: dict[str, list[tuple[str, str]]] = {
    "cst": [("+08:00", "China Standard Time 中国标准时间"), ("-06:00", "US Central Standard Time 美国中部标准时间"), ("-05:00", "Cuba Standard Time 古巴标准时间")],
    "est": [("-05:00", "US Eastern Standard Time 美国东部标准时间"), ("+10:00", "Australian Eastern Standard Time 澳大利亚东部标准时间")],
    "edt": [("-04:00", "US Eastern Daylight Time 美国东部夏令时"), ("+11:00", "Australian Eastern Daylight Time 澳大利亚东部夏令时")],
    "ist": [("+05:30", "India Standard Time 印度标准时间"), ("+01:00", "Irish Standard Time 爱尔兰标准时间"), ("+02:00", "Israel Standard Time 以色列标准时间")],
    "pst": [("-08:00", "US Pacific Standard Time 美国太平洋标准时间"), ("+08:00", "Philippine Standard Time 菲律宾标准时间")],
    "pdt": [("-07:00", "US Pacific Daylight Time 美国太平洋夏令时")],
    "mst": [("-07:00", "US Mountain Standard Time 美国山地标准时间"), ("+08:00", "Malaysia Standard Time 马来西亚标准时间")],
    "mdt": [("-06:00", "US Mountain Daylight Time 美国山地夏令时")],
    "cdt": [("-05:00", "US Central Daylight Time 美国中部夏令时"), ("-04:00", "Cuba Daylight Time 古巴夏令时")],
    "bst": [("+01:00", "British Summer Time 英国夏令时"), ("+06:00", "Bangladesh Standard Time 孟加拉标准时间")],
    "ast": [("-04:00", "Atlantic Standard Time 大西洋标准时间"), ("+03:00", "Arabia Standard Time 阿拉伯标准时间")],
    "cet": [("+01:00", "Central European Time 中欧时间（冬令）")], "cest": [("+02:00", "Central European Summer Time 中欧夏令时")],
    "eet": [("+02:00", "Eastern European Time 东欧时间（冬令）")], "aest": [("+10:00", "Australian Eastern Standard Time")],
    "aedt": [("+11:00", "Australian Eastern Daylight Time")], "nzst": [("+12:00", "New Zealand Standard Time")],
    "wet": [("+00:00", "Western European Time 西欧时间（冬令）")], "msk": [("+03:00", "Moscow Time 莫斯科时间")],
}
_ZONE_CN_RE = re.compile(r"^(?P<side>[东東西])(?P<num>[0-9零〇一二两兩三四五六七八九十]{1,3})(?:时区|時區|区|區)$")
_ZONE_EW_RE = re.compile(r"^(?P<side>[EW])(?P<num>\d{1,2})$", re.IGNORECASE)
_ZONE_HM_TEXT_RE = re.compile(r"^(?P<sign>[+-]?)(?P<hours>\d{1,2}):(?P<minutes>\d{2})(?::(?P<seconds>\d{2}))?$")
_ZONE_COMPACT_RE = re.compile(r"^(?P<sign>[+-]?)(?P<digits>\d{3,4})$")
_ZONE_DECIMAL_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?$")


def format_zone_minutes(total_minutes: int) -> str:
    sign = "-" if total_minutes < 0 else "+"
    hours, minutes = divmod(abs(total_minutes), 60)
    return f"{sign}{hours:02d}:{minutes:02d}"


def _zone_issue(value: Any, zh: str, en: str, *, options: list[Any] | None = None, ask_user: bool = False) -> FieldIssue:
    return FieldIssue("tool.invalid_zone", zh, en, expected_zh=_ZONE_EXPECTED_ZH, expected_en=_ZONE_EXPECTED_EN,
                      example="+08:00", options=options, ask_user=ask_user)


def _zone_from_minutes(value: Any, minutes: float) -> str:
    if not math.isfinite(minutes) or abs(minutes - round(minutes)) > 1e-6:
        raise _zone_issue(value, f"时区 {value!r} 不是整分钟的偏移。", f"Zone {value!r} is not a whole-minute offset.")
    total = round(minutes)
    if not ZONE_MIN_MINUTES <= total <= ZONE_MAX_MINUTES:
        raise _zone_issue(
            value, f"时区 {value!r} 超出 -12:00…+14:00：地球上没有这个偏移。",
            f"Zone {value!r} is outside -12:00…+14:00; no such UTC offset exists.",
        )
    return format_zone_minutes(total)


def _zone_from_hours(value: Any, hours: float) -> str:
    if math.isfinite(hours) and abs(hours) > 14:
        # 480 / -300 是分钟、28800 是秒：给出「如果是分钟 / 秒」的读法，但不替调用方定。
        options = []
        for unit_zh, unit_en, minutes in (("分钟", "minutes", hours), ("秒", "seconds", hours / 60)):
            if abs(minutes - round(minutes)) < 1e-6 and ZONE_MIN_MINUTES <= round(minutes) <= ZONE_MAX_MINUTES:
                options.append({"value": format_zone_minutes(round(minutes)), "label": f"若 {value} 是{unit_zh} / if {value} is in {unit_en}"})
        raise _zone_issue(
            value, f"时区 {value!r} 不是小时数（-12…+14）。看起来像分钟或秒，请改传 ±HH:MM。",
            f"Zone {value!r} is not an hour count (-12…+14). It looks like minutes or seconds; pass ±HH:MM instead.",
            options=options,
        )
    return _zone_from_minutes(value, hours * 60)


def parse_zone(value: Any) -> Parsed:
    """偏移类写法 → '±HH:MM'。IANA 名 / 地名式时区由调用方先处理（要盘面日期）；这里遇到会当作认不出。"""
    if isinstance(value, bool):
        raise _zone_issue(value, f"时区不能是布尔值 {value!r}。", f"Zone cannot be a boolean ({value!r}).")
    if isinstance(value, (int, float)):
        return Parsed(_zone_from_hours(value, float(value)))
    raw = clean_text(value)
    text = raw.upper().replace(" ", "")
    lowered = raw.lower().strip()
    if lowered in _ZONE_FIXED_ABBREVIATIONS:
        return Parsed("+00:00")
    if lowered in ZONE_AMBIGUOUS_ABBREVIATIONS:
        candidates = ZONE_AMBIGUOUS_ABBREVIATIONS[lowered]
        options = [{"value": offset, "label": label} for offset, label in candidates]
        raise _zone_issue(
            value, f"时区缩写 {raw} 不止一种含义（或随夏令时变化），不能替用户选：请改传偏移或 IANA 名。",
            f"Zone abbreviation {raw} has more than one meaning (or shifts with DST); pass an offset or an IANA name instead.",
            options=options, ask_user=True,
        )
    for prefix in ("UTC", "GMT", "UT"):
        if text.startswith(prefix) and len(text) > len(prefix):
            text = text[len(prefix):]
            break
    cn = _ZONE_CN_RE.match(raw.replace(" ", ""))
    if cn:
        hours = _cn_number(cn.group("num"))
        if hours is None or hours > (14 if cn.group("side") in "东東" else 12):
            raise _zone_issue(value, f"没有「{raw}」这个时区（东 0–14 区、西 0–12 区）。", f"There is no zone '{raw}' (east 0–14, west 0–12).")
        offset = format_zone_minutes((1 if cn.group("side") in "东東" else -1) * hours * 60)
        return Parsed(offset, f"时区「{raw}」按 {offset} 读。", f"Zone '{raw}' was read as {offset}.")
    ew = _ZONE_EW_RE.match(text)
    if ew:
        sign = 1 if ew.group("side").upper() == "E" else -1
        offset = _zone_from_minutes(value, sign * int(ew.group("num")) * 60)
        return Parsed(offset, f"时区「{raw}」按 {offset} 读。", f"Zone '{raw}' was read as {offset}.")
    hm = _ZONE_HM_TEXT_RE.match(text)
    if hm:
        minutes, seconds = int(hm.group("minutes")), int(hm.group("seconds") or 0)
        if minutes >= 60 or seconds >= 60:
            raise _zone_issue(value, f"时区 {raw!r} 的分 / 秒超过 59。", f"Zone {raw!r} has minutes or seconds above 59.")
        if seconds:
            raise _zone_issue(
                value, f"时区 {raw!r} 带秒：起盘只收整分钟的偏移（地方平时请改用真太阳时开关，或给 IANA 名）。",
                f"Zone {raw!r} carries seconds; only whole-minute offsets are accepted (for local mean time give an IANA name).",
            )
        sign = -1 if hm.group("sign") == "-" else 1
        return Parsed(_zone_from_minutes(value, sign * (int(hm.group("hours")) * 60 + minutes)))
    compact = _ZONE_COMPACT_RE.match(text)
    if compact:
        digits = compact.group("digits")
        hours, minutes = int(digits[:-2]), int(digits[-2:])
        if minutes < 60 and hours <= 14:
            sign = -1 if compact.group("sign") == "-" else 1
            return Parsed(_zone_from_minutes(value, sign * (hours * 60 + minutes)))
    if _ZONE_DECIMAL_RE.match(text):
        return Parsed(_zone_from_hours(value, float(text)))
    raise _zone_issue(value, f"认不出时区：{raw!r}。", f"Unrecognized time zone: {raw!r}.")


# ───────────────────────── 时刻 ─────────────────────────

_TIME_EXPECTED_ZH = "24 小时制钟表时刻 HH:MM[:SS]（00:00:00–23:59:59）；也认 0830、8点半、上午8点、8:30 PM"
_TIME_EXPECTED_EN = "a 24-hour clock time HH:MM[:SS] (00:00:00–23:59:59); 0830, 8点半, 上午8点 and 8:30 PM are also understood"
TIME_UNKNOWN_WORDS = frozenset({
    "unknown", "unk", "n/a", "na", "none", "null", "nil", "?", "??", "不详", "不詳", "不知道", "不清楚", "未知", "不明", "不记得", "不記得",
    "忘了", "忘记了", "忘記了", "无", "無", "没有", "沒有", "not known", "not sure", "dont know", "don't know", "tbd",
})
# 十二时辰 → 钟表时段（起，止）。子时跨日：23:00–01:00。
SHICHEN_SPANS: dict[str, tuple[str, str]] = {
    "子": ("23:00", "01:00"), "丑": ("01:00", "03:00"), "寅": ("03:00", "05:00"), "卯": ("05:00", "07:00"),
    "辰": ("07:00", "09:00"), "巳": ("09:00", "11:00"), "午": ("11:00", "13:00"), "未": ("13:00", "15:00"),
    "申": ("15:00", "17:00"), "酉": ("17:00", "19:00"), "戌": ("19:00", "21:00"), "亥": ("21:00", "23:00"),
}
_SHICHEN_RE = re.compile(r"^(?:早|晚|夜)?(?P<zhi>[子丑寅卯辰巳午未申酉戌亥])(?:时|時|正|初)?(?:辰)?$")
_TIME_COLON_RE = re.compile(r"^(?P<hour>\d{1,2}):(?P<minute>\d{1,2})(?::(?P<second>\d{1,2})(?:\.\d+)?)?$")
_TIME_COMPACT_RE = re.compile(r"^(?P<hour>\d{2})(?P<minute>\d{2})(?P<second>\d{2})?$")
_TIME_CN_RE = re.compile(
    r"^(?P<hour>[0-9零〇一二两兩三四五六七八九十]{1,3})(?:点钟|點鐘|点|點|时|時)"
    r"(?:(?P<half>半)|(?P<quarter>[一三1-3]刻)|(?P<minute>[0-9零〇一二两兩三四五六七八九十]{1,3})(?:分)?"
    r"(?:(?P<second>[0-9零〇一二两兩三四五六七八九十]{1,3})秒)?|整)?$"
)
_TIME_AMPM_RE = re.compile(r"^(?:(?P<pre>[AP])\.?M\.?)?(?P<hour>\d{1,2})(?::(?P<minute>\d{2})(?::(?P<second>\d{2}))?)?(?:(?P<post>[AP])\.?M\.?)?$", re.IGNORECASE)
_PERIOD_AM = ("凌晨", "清晨", "早晨", "早上", "上午", "早")
_PERIOD_PM = ("下午", "傍晚", "晚上", "夜里", "夜裡", "夜晚", "晚")
_PERIOD_NOON = ("中午", "正午")
_PERIOD_MIDNIGHT = ("半夜", "午夜", "深夜")


def _time_issue(code: str, zh: str, en: str, *, options: list[Any] | None = None, ask_user: bool = False, example: str = "08:30:00") -> FieldIssue:
    return FieldIssue(code, zh, en, expected_zh=_TIME_EXPECTED_ZH, expected_en=_TIME_EXPECTED_EN, example=example,
                      options=options, ask_user=ask_user)


def _format_clock(hour: int, minute: int, second: int) -> str:
    return f"{hour:02d}:{minute:02d}:{second:02d}"


def _checked_clock(value: Any, hour: int, minute: int, second: int) -> str:
    if hour == 24 and minute == 0 and second == 0:
        raise _time_issue(
            "tool.invalid_time",
            "24:00 不是一个钟表时刻：若指当天结束的午夜，请把日期加一天并传 00:00:00。",
            "24:00 is not a clock time: for the midnight that ends the day, add one day to the date and pass 00:00:00.",
            options=[{"value": "00:00:00", "label": "次日 00:00:00（日期加一天）/ 00:00:00 on the NEXT calendar day"}],
        )
    if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
        raise _time_issue(
            "tool.invalid_time", f"时刻 {value!r} 越界：时 0–23、分 0–59、秒 0–59。",
            f"Time {value!r} is out of range: hour 0–23, minute 0–59, second 0–59.",
        )
    return _format_clock(hour, minute, second)


def _period_hour(value: Any, period: str, hour: int) -> int:
    """上午 / 下午 / 中午 / 半夜 + 钟点 → 24 小时制的时；读法不唯一的（晚上12点、上午12点）拒并给候选。"""
    def ambiguous(options: list[tuple[str, str]]) -> FieldIssue:
        return _time_issue(
            "tool.invalid_time", f"「{value}」有不止一种读法，请改传 24 小时制 HH:MM。",
            f"'{value}' can be read more than one way; pass a 24-hour HH:MM instead.",
            options=[{"value": v, "label": label} for v, label in options], ask_user=True,
        )
    if period in _PERIOD_AM:
        if hour == 12:
            raise ambiguous([("00:00:00", "当天凌晨零点 / midnight starting that day"), ("12:00:00", "中午十二点 / noon")])
        if hour > 12:
            raise _time_issue("tool.invalid_time", f"「{value}」自相矛盾：上午没有 {hour} 点。", f"'{value}' contradicts itself: there is no {hour} o'clock in the morning.")
        return hour
    if period in _PERIOD_PM:
        if hour == 12 and period != "下午":
            raise ambiguous([("00:00:00", "次日零点（日期加一天）/ 00:00 on the next day"), ("12:00:00", "中午十二点 / noon")])
        if hour == 0:
            raise ambiguous([("00:00:00", "次日零点（日期加一天）/ 00:00 on the next day")])
        return hour if hour >= 12 else hour + 12
    if period in _PERIOD_NOON:
        if hour in (11, 12):
            return hour
        if hour in (1, 2):
            return hour + 12
        raise _time_issue("tool.invalid_time", f"「{value}」读不通：中午只接 11、12、1、2 点。", f"'{value}' does not parse: noon only goes with 11, 12, 1 or 2 o'clock.")
    # 半夜 / 午夜 / 深夜：12 点与 0 点落在哪一天不唯一
    if hour in (12, 0):
        raise ambiguous([("00:00:00", "当天零点（这一天刚开始）/ 00:00 starting that day"), ("00:00:00+1d", "次日零点（日期加一天）/ 00:00 on the next day")])
    if 1 <= hour <= 5:
        return hour
    if hour in (10, 11):
        return hour + 12
    if 22 <= hour <= 23:
        return hour
    raise _time_issue("tool.invalid_time", f"「{value}」读不通，请改传 24 小时制 HH:MM。", f"'{value}' does not parse; pass a 24-hour HH:MM instead.")


def parse_time(value: Any) -> Parsed:
    if isinstance(value, (bool, int, float)):
        raise _time_issue(
            "tool.invalid_time", f"时刻不能是数字 {value!r}：请传 HH:MM[:SS] 字符串。",
            f"Time cannot be the number {value!r}; pass an HH:MM[:SS] string.",
        )
    raw = clean_text(value)
    lowered = raw.lower()
    if not raw or lowered in TIME_UNKNOWN_WORDS:
        raise _time_issue(
            "tool.time_unknown",
            "没有出生 / 起课的钟点。钟点决定时柱、命宫与上升、月亮的精确位置和全部宫位，不能编一个也不能默认成 0 点：请向用户问到钟点再起盘。",
            "The clock time is missing. It decides the hour pillar, the Ascendant and houses and the Moon's exact position; it must not be invented or defaulted to midnight. Ask the user for the time.",
            ask_user=True,
        )
    text = raw.upper().lstrip("T") if re.match(r"^[Tt]\d", raw) else raw.upper()
    text = text.replace(" ", "")
    colon = _TIME_COLON_RE.match(text)
    if colon:
        return Parsed(_checked_clock(raw, int(colon.group("hour")), int(colon.group("minute")), int(colon.group("second") or 0)))
    compact = _TIME_COMPACT_RE.match(text)
    if compact:
        clock = _checked_clock(raw, int(compact.group("hour")), int(compact.group("minute")), int(compact.group("second") or 0))
        return Parsed(clock, f"时刻「{raw}」按 {clock} 读。", f"Time '{raw}' was read as {clock}.")
    shichen = _SHICHEN_RE.match(text)
    if shichen:
        start, end = SHICHEN_SPANS[shichen.group("zhi")]
        raise _time_issue(
            "tool.time_is_shichen",
            f"「{raw}」是时辰（{start}–{end}），不是钟表时刻。两小时内的不同钟点会得到不同的命宫 / 上升、宫位与真太阳时换算，不能替用户挑一个：请问用户具体钟点；"
            "只知道时辰时，把这一点如实告诉用户并由用户决定取哪个钟点。",
            f"'{raw}' is a double-hour ({start}–{end}), not a clock time. Different times inside it give different Ascendants, houses and true-solar-time results, "
            "so do not pick one: ask the user for the clock time, or let the user decide which time in the span to use.",
            options=[{"value": f"{start}–{end}", "label": f"{shichen.group('zhi')}时的钟表时段 / clock span of this double-hour"}],
            ask_user=True,
        )
    period = next((p for p in (*_PERIOD_AM, *_PERIOD_PM, *_PERIOD_NOON, *_PERIOD_MIDNIGHT) if raw.startswith(p) and len(raw) > len(p)), "")
    body = raw[len(period):].replace(" ", "") if period else raw.replace(" ", "")
    cn = _TIME_CN_RE.match(body)
    body_colon = _TIME_COLON_RE.match(body) if period else None
    if cn or body_colon:
        if cn:
            hour = _cn_number(cn.group("hour"))
            minute = 30 if cn.group("half") else 0
            if cn.group("quarter"):
                minute = 15 * (_cn_number(cn.group("quarter")[0]) or 0)
            elif cn.group("minute"):
                minute = _cn_number(cn.group("minute"))
            second = _cn_number(cn.group("second")) if cn.group("second") else 0
            if hour is None or minute is None or second is None:
                raise _time_issue("tool.invalid_time", f"认不出时刻：{raw!r}。", f"Unrecognized time: {raw!r}.")
        else:
            hour, minute, second = int(body_colon.group("hour")), int(body_colon.group("minute")), int(body_colon.group("second") or 0)
        if period:
            hour = _period_hour(raw, period, hour)
        clock = _checked_clock(raw, hour, minute, second)
        return Parsed(clock, f"时刻「{raw}」按 {clock} 读。", f"Time '{raw}' was read as {clock}.")
    ampm = _TIME_AMPM_RE.match(text)
    if ampm and (ampm.group("pre") or ampm.group("post")) and not (ampm.group("pre") and ampm.group("post")):
        marker = (ampm.group("pre") or ampm.group("post")).upper()
        hour, minute, second = int(ampm.group("hour")), int(ampm.group("minute") or 0), int(ampm.group("second") or 0)
        if not 1 <= hour <= 12:
            raise _time_issue(
                "tool.invalid_time", f"「{raw}」自相矛盾：带 AM / PM 的钟点只能是 1–12。",
                f"'{raw}' contradicts itself: an AM / PM time needs an hour of 1–12.",
            )
        hour = (0 if hour == 12 else hour) + (12 if marker == "P" else 0)
        clock = _checked_clock(raw, hour, minute, second)
        return Parsed(clock, f"时刻「{raw}」按 {clock} 读。", f"Time '{raw}' was read as {clock}.")
    raise _time_issue("tool.invalid_time", f"认不出时刻：{raw!r}。", f"Unrecognized time: {raw!r}.")


# ───────────────────────── 日期 ─────────────────────────

_DATE_EXPECTED_ZH = "公历日期 YYYY-MM-DD（也认 1990/5/3、1990.5.3、19900503、1990年5月3日；公元前写 -0500-03-21 或配 ad=-1）"
_DATE_EXPECTED_EN = "a Gregorian date YYYY-MM-DD (1990/5/3, 1990.5.3, 19900503 and 1990年5月3日 are understood; BCE as -0500-03-21 or with ad=-1)"
_DATE_YMD_RE = re.compile(r"^(?P<year>-?\d{1,5})(?P<sep>[-/.])(?P<month>\d{1,2})(?P=sep)(?P<day>\d{1,2})$")
_DATE_COMPACT_RE = re.compile(r"^(?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2})$")
_DATE_CN_RE = re.compile(r"^(?:公元)?(?P<year>\d{1,5})年(?P<month>\d{1,2})月(?P<day>\d{1,2})[日号號]?$")
_DATE_DMY_RE = re.compile(r"^(?P<a>\d{1,2})(?P<sep>[-/.])(?P<b>\d{1,2})(?P=sep)(?P<year>\d{4})$")
_LUNAR_MARKS = ("农历", "農曆", "阴历", "陰曆", "旧历", "舊曆", "正月", "腊月", "臘月", "冬月", "闰", "閏", "初一", "初二", "初三", "初四", "初五",
                "初六", "初七", "初八", "初九", "初十", "廿", "卅", "lunar")
_ISO_DATETIME_RE = re.compile(
    r"^(?P<date>-?\d{1,5}[-/.]\d{1,2}[-/.]\d{1,2}|\d{8}|(?:公元)?\d{1,5}年\d{1,2}月\d{1,2}[日号號]?)"
    r"(?:T|\s+|,\s*)(?P<time>\S.*?)(?P<offset>Z|[+-]\d{2}:?\d{2})?$",
    re.IGNORECASE,
)


def _date_issue(code: str, zh: str, en: str, *, options: list[Any] | None = None, ask_user: bool = False) -> FieldIssue:
    return FieldIssue(code, zh, en, expected_zh=_DATE_EXPECTED_ZH, expected_en=_DATE_EXPECTED_EN, example="1990-05-03",
                      options=options, ask_user=ask_user)


def days_in_month_certain(year: int, month: int) -> int:
    """这个月**最多**有几天——只拒确定不存在的日子。1583 年起按格里历；此前闰日按儒略历（逢 4 年）且两种纪年法（有无 0 年）都放行，
    1582-10-05…14 的改历缺口不拒：引擎在 1582 年以前按哪部历读，各技法并不一致（见 LESSONS），这里不替它们定。"""
    if month in (4, 6, 9, 11):
        return 30
    if month != 2:
        return 31
    if year >= 1583:
        return 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28
    return 29 if year % 4 == 0 or (year <= 0 and (year + 1) % 4 == 0) else 28


def _checked_date(value: Any, year: int, month: int, day: int) -> str:
    if not 1 <= month <= 12:
        raise _date_issue("tool.invalid_date", f"日期 {value!r} 的月份 {month} 不存在。", f"Date {value!r} has no month {month}.")
    limit = days_in_month_certain(year, month)
    if not 1 <= day <= limit:
        raise _date_issue(
            "tool.invalid_date", f"日期 {value!r} 不存在：{year} 年 {month} 月只有 {limit} 天。",
            f"Date {value!r} does not exist: month {month} of {year} has {limit} days.",
        )
    sign = "-" if year < 0 else ""
    return f"{sign}{abs(year):04d}-{month:02d}-{day:02d}"


def parse_date(value: Any, *, era_explicit: bool = False) -> Parsed:
    """→ Parsed('YYYY-MM-DD'，extra 里可能带从 ISO 日期时间拆出的 time / zone)。`era_explicit` = 载荷显式给了 ad。"""
    if isinstance(value, (bool, float)):
        raise _date_issue("tool.invalid_date", f"日期不能是 {value!r}：请传 YYYY-MM-DD 字符串。", f"Date cannot be {value!r}; pass a YYYY-MM-DD string.")
    raw = clean_text(value)
    if any(mark in raw.lower() for mark in _LUNAR_MARKS):
        raise _date_issue(
            "tool.lunar_date_unsupported",
            f"「{raw}」是农历日期，起盘只收公历。先换成公历再传：用 horosa_cn_calendar_month（给公历年、月，逐日列出对应的农历月日）查到那一天，"
            "或直接向用户问公历生日；不要自己推算。",
            f"'{raw}' is a lunar-calendar date; charts take Gregorian dates only. Convert it first: horosa_cn_calendar_month (Gregorian year + month, lists "
            "each day's lunar date) finds the day, or ask the user for the Gregorian date. Do not convert by hand.",
            ask_user=True,
        )
    iso = _ISO_DATETIME_RE.match(raw)
    if iso and not _DATE_YMD_RE.match(raw):
        date_part = parse_date(iso.group("date"), era_explicit=era_explicit)
        time_part = parse_time(iso.group("time"))
        extra: dict[str, Any] = {"time": time_part.value}
        if iso.group("offset"):
            extra["zone"] = parse_zone(iso.group("offset")).value
        return Parsed(date_part.value, f"「{raw}」拆成日期 {date_part.value} 与时刻 {time_part.value}。",
                      f"'{raw}' was split into date {date_part.value} and time {time_part.value}.", extra)
    match = _DATE_YMD_RE.match(raw) or _DATE_CN_RE.match(raw) or _DATE_COMPACT_RE.match(raw)
    if match:
        year_text = match.group("year")
        year = int(year_text)
        if len(year_text.lstrip("-")) <= 2 and not year_text.startswith("-") and not era_explicit:
            full = [f"19{int(year_text):02d}", f"20{int(year_text):02d}"]
            raise _date_issue(
                "tool.invalid_date",
                f"日期 {raw!r} 的年份只有 {len(year_text)} 位：是 {full[0]} 年、{full[1]} 年，还是公元 {int(year_text)} 年？请写四位年（公元 {int(year_text)} 年写 {int(year_text):04d}，或显式带 ad）。",
                f"Date {raw!r} has a {len(year_text)}-digit year: {full[0]}, {full[1]} or the year {int(year_text)} CE? Write four digits ({int(year_text):04d} for year {int(year_text)} CE, or pass ad explicitly).",
                options=[f"{y}-{int(match.group('month')):02d}-{int(match.group('day')):02d}" for y in (*full, f"{int(year_text):04d}")],
                ask_user=True,
            )
        canonical = _checked_date(raw, year, int(match.group("month")), int(match.group("day")))
        if canonical == raw:
            return Parsed(canonical)
        plain = _DATE_YMD_RE.match(raw) is not None and match.group("sep") in "-/"
        return Parsed(canonical) if plain else Parsed(canonical, f"日期「{raw}」按 {canonical} 读。", f"Date '{raw}' was read as {canonical}.")
    dmy = _DATE_DMY_RE.match(raw)
    if dmy:
        a, b, year = int(dmy.group("a")), int(dmy.group("b")), int(dmy.group("year"))
        readings: list[str] = []
        for month, day in ((a, b), (b, a)):  # 月/日/年、日/月/年
            if 1 <= month <= 12 and 1 <= day <= days_in_month_certain(year, month):
                text = f"{year:04d}-{month:02d}-{day:02d}"
                if text not in readings:
                    readings.append(text)
        if len(readings) == 1:
            return Parsed(readings[0], f"日期「{raw}」只有一种读得通：{readings[0]}。", f"Date '{raw}' has only one valid reading: {readings[0]}.")
        if len(readings) == 2:
            raise _date_issue(
                "tool.ambiguous_date",
                f"日期 {raw!r} 有两种读法（月/日/年 → {readings[0]}，日/月/年 → {readings[1]}），不能替用户选：请改传 YYYY-MM-DD。",
                f"Date {raw!r} reads two ways (month/day/year → {readings[0]}, day/month/year → {readings[1]}); pass YYYY-MM-DD instead.",
                options=readings, ask_user=True,
            )
        raise _date_issue("tool.invalid_date", f"日期 {raw!r} 不存在。", f"Date {raw!r} does not exist.")
    raise _date_issue("tool.invalid_date", f"认不出日期：{raw!r}。", f"Unrecognized date: {raw!r}.")


# ───────────────────────── 经纬度 ─────────────────────────

_COORD_EXPECTED = {
    "lat": ("纬度：十进制度（31.22，南纬为负）或 31n13 / 31°13′N / 北纬31.22，范围 0–90",
            "latitude: decimal degrees (31.22, south negative) or 31n13 / 31°13′N / 北纬31.22, within 0–90", "31n13"),
    "lon": ("经度：十进制度（121.47，西经为负）或 121e28 / 121°28′E / 东经121.47，范围 0–180",
            "longitude: decimal degrees (121.47, west negative) or 121e28 / 121°28′E / 东经121.47, within 0–180", "121e28"),
}
_HEMI_WORDS = (("北纬", "N"), ("北緯", "N"), ("南纬", "S"), ("南緯", "S"), ("东经", "E"), ("東經", "E"), ("西经", "W"), ("西經", "W"),
               ("north", "N"), ("south", "S"), ("east", "E"), ("west", "W"))
_COORD_COMPACT_RE = re.compile(r"^(?P<deg>\d{1,3})(?P<hemi>[NSEW])(?P<min>\d{1,2})(?::(?P<sec>\d{1,2}))?$")
_COORD_NUMBER = r"\d+(?:\.\d+)?"
_COORD_DMS_RE = re.compile(
    rf"^(?P<pre>[NSEW])?(?P<sign>[+-])?(?P<deg>{_COORD_NUMBER})(?:[°度d:\s]\s*(?P<min>{_COORD_NUMBER})?(?:['′分m:\s]\s*(?P<sec>{_COORD_NUMBER})?(?:\"|″|''|′′|秒|s)?)?)?\s*(?P<post>[NSEW])?$",
    re.IGNORECASE,
)
_COORD_DOMAIN = 1e21


def _coord_issue(axis: str, zh: str, en: str, *, options: list[Any] | None = None, ask_user: bool = False) -> FieldIssue:
    expected_zh, expected_en, example = _COORD_EXPECTED[axis]
    return FieldIssue("tool.invalid_coordinate", zh, en, expected_zh=expected_zh, expected_en=expected_en, example=example,
                      options=options, ask_user=ask_user)


def _axis_name(axis: str) -> tuple[str, str]:
    return ("纬度", "latitude") if axis == "lat" else ("经度", "longitude")


def parse_coordinate(value: Any, *, axis: str) -> Parsed:
    """→ Parsed(十进制度 float)。罗盘串由调用方统一格式化（上游 AstroHelper 同式）。"""
    zh_axis, en_axis = _axis_name(axis)
    limit = 90.0 if axis == "lat" else 180.0
    hemis = "NS" if axis == "lat" else "EW"

    def bounded(decimal: float) -> float:
        if not math.isfinite(decimal) or abs(decimal) >= _COORD_DOMAIN:
            raise _coord_issue(axis, f"{zh_axis} {value!r} 不是一个有限的数。", f"{en_axis.capitalize()} {value!r} is not a finite number.")
        if abs(decimal) > limit:
            hint_zh = "（经纬度是不是传反了？）" if axis == "lat" and abs(decimal) <= 180 else ""
            hint_en = " (are latitude and longitude swapped?)" if hint_zh else ""
            raise _coord_issue(
                axis, f"{zh_axis} {value!r} 超出 ±{limit:g}°{hint_zh}。", f"{en_axis.capitalize()} {value!r} is outside ±{limit:g}°{hint_en}.",
            )
        return decimal

    if isinstance(value, bool):
        raise _coord_issue(axis, f"{zh_axis}不能是布尔值。", f"{en_axis.capitalize()} cannot be a boolean.")
    if isinstance(value, (int, float)):
        return Parsed(bounded(float(value)))
    raw = clean_text(value)
    text = raw
    for word, letter in _HEMI_WORDS:
        text = re.sub(re.escape(word), letter, text, flags=re.IGNORECASE)
    text = text.replace("º", "°").replace("˚", "°").replace("’", "'").replace("‘", "'").replace("”", '"').replace("“", '"').strip()
    upper = text.upper().replace(" ", "")
    compact = _COORD_COMPACT_RE.match(upper)
    if compact:
        hemi, degrees, minutes = compact.group("hemi"), int(compact.group("deg")), int(compact.group("min"))
        if hemi not in hemis:
            raise _coord_issue(axis, f"{zh_axis} {raw!r} 用了 {hemi}：{zh_axis}只认 {' / '.join(hemis)}（经纬度是不是传反了？）。",
                               f"{en_axis.capitalize()} {raw!r} uses {hemi}; only {' / '.join(hemis)} apply (are latitude and longitude swapped?).")
        if minutes >= 60:
            as_decimal = float(f"{degrees}.{compact.group('min')}")
            carried = degrees + minutes / 60
            raise _coord_issue(
                axis,
                f"{zh_axis} {raw!r} 的「分」是 {minutes}（要小于 60）。它是十进制度 {as_decimal}°，还是 {degrees}°{minutes}′（= {carried:.4f}°）？请改成不含糊的写法。",
                f"{en_axis.capitalize()} {raw!r} has {minutes} arc-minutes (must be below 60). Is it {as_decimal}° in decimal degrees, or {degrees}°{minutes}′ (= {carried:.4f}°)? Rewrite it unambiguously.",
                options=[{"value": as_decimal * (-1 if hemi in "SW" else 1), "label": f"{as_decimal}°{hemi}（十进制度 / decimal degrees）"},
                         {"value": round(carried * (-1 if hemi in "SW" else 1), 6), "label": f"{degrees}°{minutes}′{hemi}（度分 / degrees and minutes）"}],
            )
        seconds = int(compact.group("sec") or 0)
        if seconds >= 60:
            raise _coord_issue(axis, f"{zh_axis} {raw!r} 的秒要小于 60。", f"{en_axis.capitalize()} {raw!r} needs seconds below 60.")
        return Parsed(bounded((degrees + minutes / 60 + seconds / 3600) * (-1 if hemi in "SW" else 1)))
    dms = _COORD_DMS_RE.match(text.strip())
    if dms and dms.group("deg") is not None:
        pre, post = (dms.group("pre") or "").upper(), (dms.group("post") or "").upper()
        if pre and post and pre != post:
            raise _coord_issue(axis, f"{zh_axis} {raw!r} 同时写了 {pre} 和 {post}。", f"{en_axis.capitalize()} {raw!r} carries both {pre} and {post}.")
        hemi = pre or post
        if hemi and hemi not in hemis:
            raise _coord_issue(axis, f"{zh_axis} {raw!r} 用了 {hemi}：{zh_axis}只认 {' / '.join(hemis)}（经纬度是不是传反了？）。",
                               f"{en_axis.capitalize()} {raw!r} uses {hemi}; only {' / '.join(hemis)} apply (are latitude and longitude swapped?).")
        if hemi and dms.group("sign"):
            raise _coord_issue(axis, f"{zh_axis} {raw!r} 既有正负号又有方向字母。", f"{en_axis.capitalize()} {raw!r} carries both a sign and a hemisphere letter.")
        degrees = float(dms.group("deg"))
        minutes = float(dms.group("min")) if dms.group("min") else 0.0
        seconds = float(dms.group("sec")) if dms.group("sec") else 0.0
        if (dms.group("min") and "." in dms.group("deg")) or (dms.group("sec") and "." in (dms.group("min") or "")):
            raise _coord_issue(axis, f"{zh_axis} {raw!r} 的度 / 分带小数又接着写了下一级。", f"{en_axis.capitalize()} {raw!r} mixes a fractional part with a further sexagesimal part.")
        if minutes >= 60 or seconds >= 60:
            raise _coord_issue(axis, f"{zh_axis} {raw!r} 的分 / 秒要小于 60。", f"{en_axis.capitalize()} {raw!r} needs minutes and seconds below 60.")
        decimal = degrees + minutes / 60 + seconds / 3600
        negative = hemi in ("S", "W") or dms.group("sign") == "-"
        parsed = bounded(-decimal if negative else decimal)
        plain = re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text.strip()) is not None
        return Parsed(parsed) if plain else Parsed(parsed, f"{zh_axis}「{raw}」按 {parsed:.4f}° 读。", f"{en_axis.capitalize()} '{raw}' was read as {parsed:.4f}°.")
    raise _coord_issue(axis, f"认不出{zh_axis}：{raw!r}。", f"Unrecognized {en_axis}: {raw!r}.")


# ───────────────────────── 性别 ─────────────────────────

# 性别标签 → 1 男 / 0 女（全仓唯一词表：service/_common._gender_label 的回显也用它）。键一律小写、NFKC、繁体折成简体后比较。
GENDER_MALE_LABELS = frozenset({
    "男", "male", "m", "boy", "man", "nan", "男性", "乾", "1", "乾造", "男命", "男士", "先生", "男生", "男孩", "男人", "♂", "mr", "mr.", "he", "him",
})
GENDER_FEMALE_LABELS = frozenset({
    "女", "female", "f", "girl", "woman", "nv", "女性", "坤", "0", "坤造", "女命", "女士", "小姐", "太太", "女生", "女孩", "女人", "♀", "ms", "ms.", "mrs",
    "mrs.", "miss", "she", "her",
})


def parse_gender(value: Any) -> Parsed:
    if isinstance(value, bool):
        return Parsed(1 if value else 0)
    if isinstance(value, int) and value in (0, 1):
        return Parsed(value)
    if isinstance(value, float) and value in (0.0, 1.0):
        return Parsed(int(value))
    key = clean_text(value).lower()
    if key in GENDER_MALE_LABELS:
        return Parsed(1)
    if key in GENDER_FEMALE_LABELS:
        return Parsed(0)
    raise FieldIssue(
        "tool.invalid_gender", f"认不出性别：{value!r}。起盘只分男 / 女（大运、大限的顺逆由它定）。",
        f"Unrecognized gender: {value!r}. Charts only distinguish male / female (it sets the direction of the luck cycles).",
        expected_zh="1 / 男 / male / 乾造 = 男；0 / 女 / female / 坤造 = 女", expected_en="1 / 男 / male / 乾造 = male; 0 / 女 / female / 坤造 = female",
        example=1, options=[{"value": 1, "label": "男 / male"}, {"value": 0, "label": "女 / female"}], ask_user=True,
    )


# ───────────────────────── 纪元（ad）与日界开关 ─────────────────────────

_ERA_WORDS = {
    1: ("1", "+1", "ad", "ce", "公元", "公元后", "西元"),
    -1: ("-1", "bc", "bce", "公元前", "西元前", "前"),
}
ERA_OPTIONS = [{"value": 1, "label": "1 = 公元（AD）"}, {"value": -1, "label": "-1 = 公元前（BC）"}]


def parse_era(value: Any) -> Parsed:
    """`ad` / `guaAd`：1 公元 / -1 公元前。0 拒：上游 DateTime 的公元前是 ad=0，而 Python 后端 `int(ad or 1)` 把 0 读成公元——两种读法相反。
    （不走 Vocabulary：它的键会去掉「-」，'-1' 会被读成 1。）"""
    if isinstance(value, bool):
        raise _era_issue(value)
    if isinstance(value, (int, float)) and value in (1, -1):
        return Parsed(int(value))
    if isinstance(value, str):
        key = clean_text(value).lower().replace(" ", "").replace(".", "")
        for era, words in _ERA_WORDS.items():
            if key in words:
                plain = key in ("1", "-1")
                return Parsed(era) if plain else Parsed(era, f"纪元「{value}」按 ad={era} 读。", f"Era '{value}' was read as ad={era}.")
    raise _era_issue(value)


def _era_issue(value: Any) -> FieldIssue:
    return FieldIssue(
        "tool.invalid_option", f"ad 认不出 {value!r}：只收 1（公元）或 -1（公元前）。", f"Unrecognized ad {value!r}: only 1 (AD) or -1 (BC).",
        expected_zh="1 = 公元，-1 = 公元前（或把日期写成带负号的 -0500-03-21）", expected_en="1 = AD, -1 = BC (or write the date with a leading minus, -0500-03-21)",
        example=1, options=ERA_OPTIONS,
    )


# 日界两开关（上游全局出厂缺省 1 / 1：dayBoundary.js defaultAfter23NewDay / defaultLateZiHourUseNextDay）。
DAY_SWITCH_KEYS = ("after23NewDay", "lateZiHourUseNextDay")
DAY_SWITCH_DEFAULTS = {"after23NewDay": 1, "lateZiHourUseNextDay": 1}
_DAY_SWITCH_LABELS = {
    "after23NewDay": {1: "23 点换日（日柱进次日，缺省）", 0: "24 点换日"},
    "lateZiHourUseNextDay": {1: "晚子时时干按次日日干起（缺省）", 0: "晚子时时干按当日日干起"},
}
_DAY_SWITCH_WORDS = {1: ("1", "true", "yes", "on", "是"), 0: ("0", "false", "no", "off", "否")}


def parse_day_switch(value: Any, *, field_name: str = "after23NewDay") -> Parsed:
    """日界 / 晚子时开关 → 0 / 1。旧做法「不是 1 / true 就当 0」把 'bogus'、2 都悄悄读成 24 点换日。"""
    labels = _DAY_SWITCH_LABELS.get(field_name, _DAY_SWITCH_LABELS["after23NewDay"])
    if isinstance(value, bool):
        return Parsed(1 if value else 0)
    if isinstance(value, (int, float)) and value in (0, 1):
        return Parsed(int(value))
    if isinstance(value, str):
        key = clean_text(value).lower()
        for switch, words in _DAY_SWITCH_WORDS.items():
            if key in words:
                return Parsed(switch)
    pairs = " ".join(f"{v}={label}" for v, label in labels.items())
    raise FieldIssue(
        "tool.invalid_option", f"{field_name} 认不出 {value!r}：只收 1 / 0（或 true / false）。",
        f"Unrecognized {field_name} {value!r}: only 1 / 0 (or true / false).",
        expected_zh="可选值：" + pairs, expected_en="accepted values: " + pairs, example=1,
        options=[{"value": v, "label": label} for v, label in labels.items()],
    )


# ───────────────────────── 宫制 / 黄道 ─────────────────────────

def _name_key(text: str) -> str:
    return re.sub(r"[\s_\-·.]+", "", clean_text(text).lower())


# 宫制别名 → 索引。正名取自 astro_rulers.HOUSE_SYSTEM_LABELS（上游 AstroConst.HOUSE_SYSTEM_OPTIONS 的镜像），这里只补通行的别写。
_HOUSE_SYSTEM_ALIASES: dict[str, int] = {
    "wholesign": 0, "wholesigns": 0, "wholesignhouses": 0, "whole": 0, "ws": 0, "整宫": 0, "整宫制": 0, "整宮制": 0, "整宮": 0, "rashi": 0,
    "alcabitius": 1, "alchabitius": 1, "alcabitus": 1, "阿卡比特": 1, "阿卡比特制": 1,
    "regio": 2, "regiomontanus": 2, "芮氏": 2, "芮氏分宫制": 2, "雷氏": 2,
    "placidus": 3, "placidian": 3, "普拉西德": 3, "普拉西德制": 3, "普拉西度": 3, "普氏": 3, "普氏分宫制": 3,
    "koch": 4, "柯赫": 4, "科赫": 4, "柯氏": 4, "vehlow": 5, "vehlowequal": 5, "polichpage": 6, "topocentric": 6, "sripati": 7,
    "porphyry": 9, "porphyrius": 9, "波菲利": 9, "campanus": 10, "坎帕纳斯": 10, "equal": 11, "equalhouse": 11, "equalhouses": 11, "等宫制": 11, "等宫": 11,
    "equalmc": 12, "meridian": 13, "axial": 13, "horizontal": 14, "azimuthal": 14, "morinus": 15, "莫林": 15,
}


# 印占（webindiasrv）另有一张编号表（astro_sidereal.INDIA_HOUSE_SYSTEM_LABELS：3=KP/Placidus、5=Equal、8=Alcabitus……）。
_INDIA_HOUSE_SYSTEM_ALIASES: dict[str, int] = {
    "wholesign": 0, "wholesigns": 0, "whole": 0, "rashi": 0, "整宫": 0, "整宫制": 0, "regiomontanus": 2, "regio": 2, "kp": 3, "placidus": 3,
    "koch": 4, "equal": 5, "lagnabhava": 5, "bhava": 5, "等宫制": 5, "vehlow": 6, "sripati": 7, "alcabitus": 8, "alcabitius": 8, "porphyry": 9,
    "campanus": 10, "morinus": 11, "meridian": 12, "axial": 12, "polichpage": 13, "topocentric": 13, "equalmc": 14, "azimuthal": 15,
    "horizon": 15, "horizontal": 15,
}


def house_system_table(family: str = "astro") -> dict[int, str]:
    """宫制索引 → 名称。西占 = astro_rulers.HOUSE_SYSTEM_LABELS（报告人话化用的同一张表），印占 = astro_sidereal 那张。"""
    if family in ("india", "india-hsys"):
        from horosa_skill.astro_sidereal import INDIA_HOUSE_SYSTEM_LABELS

        table = dict(INDIA_HOUSE_SYSTEM_LABELS)
        if family == "india-hsys":
            # 印占模型上的通用 `hsys`：上游印占页的请求照带页面通用宫制（缺省 1，录制见 tests/fixtures/sync311_w3b_india_live.json），
            # 印占后端只在没有 indiaHsys / 流派预设时才按印占表读它——所以多收一个 1。`indiaHsys` 严格按印占表。
            table = dict(sorted({**table, 1: "Alcabitus（页面通用缺省；印占按 indiaHsys / 流派预设）"}.items()))
        return table
    return {int(key): label for key, label in HOUSE_SYSTEM_LABELS.items()}


def _house_system_names(family: str) -> dict[str, int]:
    names = dict(_INDIA_HOUSE_SYSTEM_ALIASES if family.startswith("india") else _HOUSE_SYSTEM_ALIASES)
    for index, label in house_system_table(family).items():
        names.setdefault(_name_key(label), index)
    return names


def parse_house_system(value: Any, *, family: str = "astro") -> Parsed:
    table = house_system_table(family)
    pairs = [f"{index}={label}" for index, label in table.items()]

    def issue(zh: str, en: str) -> FieldIssue:
        return FieldIssue("tool.invalid_house_system", zh, en, expected_zh="宫制索引或名称：" + " ".join(pairs),
                          expected_en="a house-system index or name: " + " ".join(pairs), example=0 if family.startswith("india") else 3,
                          options=[{"value": index, "label": label} for index, label in table.items()])

    if isinstance(value, bool):
        raise issue("宫制不能是布尔值。", "House system cannot be a boolean.")
    number: int | None = None
    if isinstance(value, int):
        number = value
    elif isinstance(value, float) and value == int(value):
        number = int(value)
    elif isinstance(value, str) and re.fullmatch(r"[+-]?\d+", clean_text(value)):
        number = int(clean_text(value))
    if number is not None:
        if number not in table:
            raise issue(f"没有索引为 {number} 的宫制。", f"There is no house system with index {number}.")
        return Parsed(number)
    if isinstance(value, str):
        from horosa_skill.textscript import fold_to_simplified

        key = _name_key(fold_to_simplified(clean_text(value)))
        names = _house_system_names(family)
        for suffix in ("", "housesystem", "houses", "house", "system", "分宫制", "宫制", "制"):
            if suffix and not key.endswith(suffix):
                continue
            hit = names.get(key[: len(key) - len(suffix)])
            if hit is not None:
                return Parsed(hit, f"宫制「{value}」按 {hit}（{table[hit]}）读。", f"House system '{value}' was read as {hit} ({table[hit]}).")
    raise issue(f"认不出宫制：{value!r}。", f"Unrecognized house system: {value!r}.")


_ZODIACAL_NAMES: dict[str, int] = {
    "tropical": 0, "tropic": 0, "回归": 0, "回归黄道": 0, "回归制": 0, "0": 0,
    "sidereal": 1, "恒星": 1, "恒星黄道": 1, "恒星制": 1, "vedic": 1, "1": 1,
}


def parse_zodiacal(value: Any) -> Parsed:
    def issue(zh: str, en: str) -> FieldIssue:
        return FieldIssue("tool.invalid_zodiacal", zh, en, expected_zh="0 / tropical / 回归黄道，或 1 / sidereal / 恒星黄道",
                          expected_en="0 / tropical, or 1 / sidereal", example=0,
                          options=[{"value": 0, "label": "回归黄道 tropical"}, {"value": 1, "label": "恒星黄道 sidereal"}])

    if isinstance(value, bool):
        return Parsed(1 if value else 0)
    if isinstance(value, (int, float)) and value in (0, 1):
        return Parsed(int(value))
    if isinstance(value, str):
        from horosa_skill.textscript import fold_to_simplified

        hit = _ZODIACAL_NAMES.get(_name_key(fold_to_simplified(clean_text(value))))
        if hit is not None:
            plain = clean_text(value) in ("0", "1")
            return Parsed(hit) if plain else Parsed(hit, f"黄道「{value}」按 {hit} 读。", f"Zodiac '{value}' was read as {hit}.")
    raise issue(f"认不出黄道制：{value!r}。", f"Unrecognized zodiac: {value!r}.")


# ───────────────────────── 解读说明收集 ─────────────────────────

# 一次调用里「读懂了但做了解读」的说明（东八区 → +08:00、1990年5月3日 → 1990-05-03…）。嵌套作用域共用最外层那张表：
# MCP 层先归一化一遍、service 再归一化一遍（幂等，第二遍不再产出说明），说明只记一次、由 run_tool 并进 warnings。
_NOTES: ContextVar[list[str] | None] = ContextVar("horosa_input_notes", default=None)


@contextmanager
def input_notes_scope(*, fresh: bool = False) -> Iterator[list[str]]:
    """`fresh=True`：技法内部再调技法（择日铸展示盘、三式合一取奇门 / 太乙）用自己的一张表，内部载荷的说明不漏到用户的结果里。"""
    current = _NOTES.get()
    if current is not None and not fresh:
        yield current
        return
    notes: list[str] = []
    token = _NOTES.set(notes)
    try:
        yield notes
    finally:
        _NOTES.reset(token)


def add_input_note(zh: str, en: str) -> None:
    notes = _NOTES.get()
    if notes is None or not zh:
        return
    text = f"{zh} / {en}"
    if text not in notes:
        notes.append(text)


def note_parsed(parsed: Parsed, field_name: str = "") -> Any:
    if parsed.note_zh:
        prefix = f"`{field_name}`：" if field_name else ""
        add_input_note(prefix + parsed.note_zh, (f"`{field_name}`: " if field_name else "") + parsed.note_en)
    return parsed.value


# ───────────────────────── 取值词表（枚举类设置的通用机制） ─────────────────────────


class Vocabulary:
    """一个枚举类设置的全部合法值 + 每个值认得的别名（大小写 / 繁简 / 全角 / 空格不敏感）。

    `parse(value)` 只有两种结局：规范值，或 `tool.invalid_option`（details 带 `accepted` 全表）。schema 里用
    `vocabulary_field(vocab)` 把它挂成 pydantic BeforeValidator：认不出的值在校验层就被拒，永远到不了 runner 的
    `payload.get(k) or 缺省`。西占 / 中式各族的枚举旋钮（westNodeType、decennials 选项……）都用这一个机制，不另起一套。
    """

    def __init__(self, field_name: str, choices: Mapping[Any, Sequence[str]], *, labels: Mapping[Any, str] | None = None,
                 code: str = "tool.invalid_option", numeric: bool = False) -> None:
        """`numeric=True`：取值是数（容许度 8.5、界系 0–4、开关 0/1）。数与数字串按数值比（容差 1e-3，选项之间至少差 1′），
        `8.5°` / `17′`（角分）也认；数值不在表里即拒——绝不落进别名表（`_vocab_key` 会吃掉小数点，`1.5` 与 `15` 撞键）。"""
        self.field_name, self.code, self.numeric = field_name, code, numeric
        self.labels = {value: (labels or {}).get(value, str(value)) for value in choices}
        self._lookup: dict[str, Any] = {}
        for value, aliases in choices.items():
            for alias in ((*aliases,) if numeric else (str(value), *aliases)):
                self._lookup.setdefault(_vocab_key(alias), value)

    @property
    def accepted(self) -> list[dict[str, Any]]:
        return [{"value": value, "label": label} for value, label in self.labels.items()]

    def _read_as(self, value: Any, hit: Any) -> Parsed:
        plain = not isinstance(value, bool) and ((self.numeric and value == hit) or clean_text(value) == str(hit))
        return Parsed(hit) if plain else Parsed(
            # 字段名由 note_parsed 加前缀（`field`：…），这里不再重复。
            hit, f"「{value}」按 {hit}（{self.labels[hit]}）读。", f"'{value}' was read as {hit} ({self.labels[hit]}).")

    def issue(self, value: Any) -> FieldIssue:
        pairs = " ".join(f"{v}={label}" for v, label in self.labels.items())
        return FieldIssue(
            self.code, f"{self.field_name} 认不出 {value!r}。", f"Unrecognized {self.field_name}: {value!r}.",
            expected_zh="可选值：" + pairs, expected_en="accepted values: " + pairs, example=next(iter(self.labels)), options=self.accepted,
        )

    def parse(self, value: Any) -> Parsed:
        if self.numeric and not isinstance(value, bool):
            number = _vocab_number(value)
            if number is not None:
                for choice in self.labels:
                    if isinstance(choice, (int, float)) and not isinstance(choice, bool) and abs(float(choice) - number) <= 1e-3:
                        return self._read_as(value, choice)
                raise self.issue(value)
        if isinstance(value, (str, int, float)) and not isinstance(value, bool):
            exact = next((choice for choice in self.labels if type(choice) is type(value) and choice == value), None)
            if exact is not None:
                return Parsed(exact)
            hit = self._lookup.get(_vocab_key(value))
        else:
            hit = self._lookup.get(_vocab_key(str(value).lower())) if isinstance(value, bool) else None
        if hit is not None:
            return self._read_as(value, hit)
        raise self.issue(value)


def _vocab_key(value: Any) -> str:
    from horosa_skill.textscript import fold_to_simplified

    return re.sub(r"[\s_\-·.]", "", fold_to_simplified(clean_text(value)).lower())


_VOCAB_NUMBER_RE = re.compile(r"^(?P<num>[+-]?\d+(?:\.\d+)?)\s*(?P<unit>°|度|′|'|分)?$")


def _vocab_number(value: Any) -> float | None:
    """数 / 数字串（`8.5`、`8.5°`、`17′` = 17 角分）→ float；别的 → None（交给别名表）。"""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) if math.isfinite(float(value)) else None
    if not isinstance(value, str):
        return None
    match = _VOCAB_NUMBER_RE.match(clean_text(value))
    if not match:
        return None
    number = float(match.group("num"))
    return number / 60 if match.group("unit") in ("′", "'", "分") else number


def field_validator_for(parse: Callable[[Any], Parsed], field_name: str) -> Callable[[Any], Any]:
    """`parse_*` / `Vocabulary.parse` → pydantic BeforeValidator 用的函数：None 原样放行（缺省由模型定），解读说明进 warnings，
    读不懂 → PydanticCustomError('horosa_field', ctx=issue)，由 `input_normalization.tool_error_from_validation` 还原成结构化的逐字段错误。"""

    def validate(value: Any) -> Any:
        if value is None:
            return None
        try:
            return note_parsed(parse(value), field_name)
        except FieldIssue as issue:
            from pydantic_core import PydanticCustomError

            raise PydanticCustomError("horosa_field", "{message}", {"message": f"{issue.zh} / {issue.en}", **issue_context(issue)}) from None

    return validate


def pydantic_field_error(issue: FieldIssue, field_name: str) -> Exception:
    """模型级校验器（没有 loc 的 model_validator）用：同一个 horosa_field 错误，字段名放进 ctx（tool_error_from_validation 认它）。"""
    from pydantic_core import PydanticCustomError

    return PydanticCustomError("horosa_field", "{message}", {"message": f"{issue.zh} / {issue.en}", "field": field_name, **issue_context(issue)})


def issue_context(issue: FieldIssue) -> dict[str, Any]:
    return {"code": issue.code, "zh": issue.zh, "en": issue.en, "expected": f"{issue.expected_zh} / {issue.expected_en}",
            "example": issue.example, "options": issue.options, "ask_user": issue.ask_user}
