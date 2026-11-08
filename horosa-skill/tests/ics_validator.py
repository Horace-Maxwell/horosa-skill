"""测试侧的 RFC 5545 校验器（不进运行时依赖）：只查本仓 ICS 导出用到的那部分语法，查得比日历软件严。

查：CRLF 行尾、每个物理行 ≤ 75 个八位组且单独可按 UTF-8 解码（折行没拆开多字节字符）、续行以一个空格开头、
内容行语法、VCALENDAR / VEVENT 必需属性（VERSION / PRODID / CALSCALE；UID / DTSTAMP / DTSTART）、UID 不重复、
DTSTAMP 与带时刻的 DTSTART / DTEND 是 UTC 形式、DATE 值是合法日期、DTEND 晚于 DTSTART 且同类型、DTEND 与 DURATION 不并存、
TEXT 值里没有未转义的 `;` `,` 与控制字符、反斜杠只出现在合法转义里。
"""
from __future__ import annotations

import re
from datetime import date, datetime

_NAME = re.compile(r"^([A-Z][A-Z0-9-]*)((?:;[A-Z0-9-]+=[^;:,\"]+)*):(.*)$")
_UTC = re.compile(r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$")
_DATE = re.compile(r"^(\d{4})(\d{2})(\d{2})$")
_DURATION = re.compile(r"^P(?:\d+W|\d+D(?:T\d+H(?:\d+M)?(?:\d+S)?)?|T\d+H(?:\d+M)?(?:\d+S)?)$")
_TEXT_PROPS = frozenset({"SUMMARY", "DESCRIPTION", "X-WR-CALNAME", "LOCATION"})


def unescape(value: str) -> str:
    return re.sub(r"\\([\\;,nN])", lambda m: "\n" if m.group(1) in "nN" else m.group(1), value)


def content_lines(data: bytes) -> list[str]:
    """展开续行后的内容行（不做任何校验）。"""
    return data.decode("utf-8").replace("\r\n ", "").replace("\r\n\t", "").split("\r\n")[:-1]


def _date_or_utc(value: str, params: str, where: str, problems: list[str]) -> date | datetime | None:
    if "VALUE=DATE" in params:
        match = _DATE.match(value)
        if not match:
            problems.append(f"{where}: DATE 值不是 YYYYMMDD：{value!r}")
            return None
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            problems.append(f"{where}: 不存在的日期 {value!r}")
            return None
    match = _UTC.match(value)
    if not match:
        problems.append(f"{where}: 带时刻的值不是 UTC 形式（YYYYMMDDTHHMMSSZ）：{value!r}")
        return None
    try:
        return datetime(*(int(g) for g in match.groups()))
    except ValueError:
        problems.append(f"{where}: 不存在的时刻 {value!r}")
        return None


def validate_ics(data: bytes) -> list[str]:
    problems: list[str] = []
    if not data.endswith(b"\r\n"):
        problems.append("文件不以 CRLF 结尾")
    if re.search(rb"(?<!\r)\n", data) or re.search(rb"\r(?!\n)", data):
        problems.append("有裸 LF 或裸 CR（行尾必须是 CRLF）")
    for number, physical in enumerate(data.split(b"\r\n")[:-1], start=1):
        if len(physical) > 75:
            problems.append(f"第 {number} 行 {len(physical)} 个八位组，超过 75")
        try:
            physical.decode("utf-8")
        except UnicodeDecodeError:
            problems.append(f"第 {number} 行单独解不成 UTF-8：折行拆开了多字节字符")
        if physical[:1] == b"\t":
            problems.append(f"第 {number} 行以制表符续行（本仓只用一个空格）")
    if problems:
        return problems
    lines = content_lines(data)
    if not lines or lines[0] != "BEGIN:VCALENDAR" or lines[-1] != "END:VCALENDAR":
        return ["不是以 BEGIN:VCALENDAR 开头、END:VCALENDAR 结尾"]
    calendar: dict[str, list[str]] = {}
    events: list[dict[str, list[tuple[str, str]]]] = []
    current: dict[str, list[tuple[str, str]]] | None = None
    for line in lines[1:-1]:
        match = _NAME.match(line)
        if not match:
            problems.append(f"内容行语法不对：{line[:60]!r}")
            continue
        name, params, value = match.groups()
        if name == "BEGIN" and value == "VEVENT":
            current = {}
            continue
        if name == "END" and value == "VEVENT":
            if current is not None:
                events.append(current)
            current = None
            continue
        if name in _TEXT_PROPS:
            tokens = re.findall(r"\\.?|[^\\]", value)  # 从左到右切：转义对是一个记号
            if any(tok in (";", ",") for tok in tokens):
                problems.append(f"{name} 有未转义的 ; 或 ,：{value[:60]!r}")
            if any(tok.startswith("\\") and tok not in ("\\\\", "\\;", "\\,", "\\n", "\\N") for tok in tokens):
                problems.append(f"{name} 有非法转义：{value[:60]!r}")
            if any(ord(ch) < 0x20 and ch != "\t" or ord(ch) == 0x7F for ch in value):
                problems.append(f"{name} 含控制字符")
        target = current if current is not None else calendar
        target.setdefault(name, []).append((params, value) if current is not None else value)  # type: ignore[arg-type]
    for required, expected in (("VERSION", "2.0"), ("PRODID", None), ("CALSCALE", "GREGORIAN")):
        values = calendar.get(required) or []
        if len(values) != 1 or (expected is not None and values[0] != expected):
            problems.append(f"VCALENDAR 的 {required} 必须恰好一个" + (f"且为 {expected}" if expected else "") + f"：{values}")
    uids: set[str] = set()
    for index, event in enumerate(events, start=1):
        where = f"VEVENT #{index}"
        for required in ("UID", "DTSTAMP", "DTSTART"):
            if len(event.get(required) or []) != 1:
                problems.append(f"{where}: {required} 必须恰好一个")
        if problems:
            continue
        uid = event["UID"][0][1]
        if uid in uids:
            problems.append(f"{where}: UID 重复 {uid}")
        uids.add(uid)
        if not _UTC.match(event["DTSTAMP"][0][1]):
            problems.append(f"{where}: DTSTAMP 不是 UTC 形式")
        start = _date_or_utc(event["DTSTART"][0][1], event["DTSTART"][0][0], f"{where} DTSTART", problems)
        if "DTEND" in event and "DURATION" in event:
            problems.append(f"{where}: DTEND 与 DURATION 不能并存")
        if "DTEND" in event:
            end = _date_or_utc(event["DTEND"][0][1], event["DTEND"][0][0], f"{where} DTEND", problems)
            if start is not None and end is not None:
                if type(start) is not type(end):
                    problems.append(f"{where}: DTEND 与 DTSTART 值类型不同")
                elif end <= start:  # type: ignore[operator]
                    problems.append(f"{where}: DTEND 不晚于 DTSTART")
        if "DURATION" in event and not _DURATION.match(event["DURATION"][0][1]):
            problems.append(f"{where}: DURATION 语法不对 {event['DURATION'][0][1]!r}")
    return problems


def events_of(data: bytes) -> list[dict[str, str]]:
    """每个 VEVENT 的属性（名 → 值，TEXT 已反转义；带参数的属性名形如 DTSTART;VALUE=DATE）。"""
    out: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in content_lines(data):
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT" and current is not None:
            out.append(current)
            current = None
        elif current is not None:
            key, _, value = line.partition(":")
            current[key] = unescape(value) if key in _TEXT_PROPS else value
    return out
