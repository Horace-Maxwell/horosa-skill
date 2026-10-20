"""多个模块共用的小工具：快照拼接、性别标签、JS 口径取整、干支年、选项校验等纯函数。"""
from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from horosa_skill.astro_rulers import js_template_str as _js_template_str
from horosa_skill.errors import ToolValidationError
from horosa_skill.input_normalization import _GENDER_FEMALE_LABELS, _GENDER_MALE_LABELS

# 源码树布局下的仓根：service/<模块>.py → [0] service [1] horosa_skill [2] src [3] horosa-skill [4] 仓根
# （与拆包前 service.py 的 parents[3] 同一目录）。wheel 安装时那里没有 vendor/，调用方逐个候选判存在。
_REPO_ROOT = Path(__file__).resolve().parents[4]


def _gender_label(value: Any, *, unknown: str = "未知") -> str:
    """性别值 → 中文标签（PR #17 @xipfs 的 _gender_label 收编）：True/1/'1'/男类词→男；False/0/'0'/女类词→女；其余（含 None/-1）→ unknown。

    词表只有一份：`input_normalization._GENDER_*_LABELS`（v0.41.1 前这里另抄了一份，已经漂移——「男性」「boy」只在那边）。"""
    if isinstance(value, str):
        key = value.strip().lower()
        if key in _GENDER_MALE_LABELS:
            return "男"
        if key in _GENDER_FEMALE_LABELS:
            return "女"
        return unknown
    if value is True or value == 1:
        return "男"
    if value is False or value == 0:
        return "女"
    return unknown


def _only_payload_keys(payload: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: payload[key] for key in keys if key in payload and payload[key] is not None}


def _stringify_export_body(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return "\n".join(item for item in (_stringify_export_body(one) for one in value) if item).strip()
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            item_text = _stringify_export_body(item)
            if item_text:
                lines.append(f"{key}: {item_text}")
        return "\n".join(lines).strip()
    return str(value).strip()


def _missing_detail_text(title: str) -> str:
    return (
        f"本次本地计算结果未返回「{title}」细项；"
        "报告只能基于已返回盘面判断，不能臆造外部依赖、桌面端服务或不存在的数据。"
    )


def _render_snapshot_text(sections: list[tuple[str, str]]) -> str:
    blocks: list[str] = []
    for title, body in sections:
        clean_body = (body or "").strip() or _missing_detail_text(title)
        blocks.append(f"[{title}]\n{clean_body}".strip())
    return "\n\n".join(blocks).strip()


def _js_round(value: Any) -> int:
    # JS Math.round = floor(x+0.5)：half 一律向 +∞。曾写 int(x+0.5)——int 向零截断，负数全错
    # （-1.7 → -1，JS 为 -2）；AGENTS §4 一直写的是 floor，实现没跟上。
    try:
        return math.floor(float(value) + 0.5)
    except (TypeError, ValueError):
        return 0


_GANZHI_STEMS = "甲乙丙丁戊己庚辛壬癸"
_GANZHI_BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


def _ganzhi_year(year: int) -> str:
    """公历年 → 干支年（1984=甲子；与上游 GuoLaoChartMain.stemBranchForYear 同式）。"""
    idx = ((int(year) - 1984) % 60 + 60) % 60
    return f"{_GANZHI_STEMS[idx % 10]}{_GANZHI_BRANCHES[idx % 12]}"


def _split_degree(value: Any) -> tuple[int, int]:
    try:
        degree = float(value)
    except (TypeError, ValueError):
        return 0, 0
    if degree < 0:
        degree += 360.0
    deg = int(degree % 30)
    minute = int(((degree % 30) - deg) * 60)
    return deg, minute


def _msg(value: Any) -> str:
    return f"{value or ''}".strip()


def _is_astro_chart_payload(response_data: dict[str, Any]) -> bool:
    chart = response_data.get("chart")
    return isinstance(chart, dict) and isinstance(chart.get("objects"), list) and isinstance(chart.get("houses"), list)


def _export_body(body: str) -> dict[str, Any]:
    """段正文载体（v0.36.0）：只带 body。此前还带 `__export_data__`（整份 chart/objects…）并落进每个
    段的 `data` 键——同一引擎对象被复制 10+ 次，真实存档 qimen 5 MB / india_chart 101 MB（正文仅几 KB）。
    引擎对象只在 `data.<key>` 出现一次；段一律 body-only（LESSONS v0.36.0）。"""
    return {"__export_body__": body}


# 十二地支序（子1…亥12 取 index+1）：时支类技法共用。
# 六爻「以时起卦」不在 Python 侧：上游无头路径是 buildTimeGua(nongli)（GuaZhanMain.js:74-98：nongli.year 年支序
# ——后端该键是农历年干支，立春至正月初一之间与 yearJieqi 不同 —— + 农历月数 monthInt + 农历日数 dayInt + 时柱支序），
# vendored 在 core-js，由 tools/liuyao.js 调用。此处曾手写一份「立春年支 + 月/日取地支序 + 钟表时辰」的变体，同一时刻
# 与上游起出不同的卦（sync311 wave 3 删）。
_SIXYAO_DIZHI = "子丑寅卯辰巳午未申酉戌亥"


def _js_round3(value: Any) -> str:
    """JS `round3`（`${Math.round(Number(v) * 1000) / 1000}`）：半入向 +∞（非 Python 银行家舍入），整值去 .0。"""
    if value is None or isinstance(value, bool):
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if number != number or number in (float("inf"), float("-inf")):
        return ""
    rounded = math.floor(number * 1000 + 0.5) / 1000
    return _js_template_str(rounded) if rounded.is_integer() else repr(rounded)


def _finite_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _js_date_parse(text: Any) -> datetime | None:
    """浏览器 `Date.parse` 对后端日期串的两种形：纯日期 'YYYY-MM-DD' = UTC 零点；带时刻 = 本地墙钟。
    返回 naive 本地时间（与 datetime.now() 同一参照系）；解析不了 → None。"""
    raw = f"{text or ''}".strip().replace("/", "-")
    if not raw:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        try:
            utc = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
        return utc.astimezone().replace(tzinfo=None)
    raw = raw.replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _require_option(value: Any, allowed: Any, *, field: str, tool: str) -> None:
    """推运族可选项的值域闸：认不出的值报结构化错误（不静默回落缺省——那会算出另一张盘而不自知）。"""
    if value in allowed:
        return
    raise ToolValidationError(
        f"{tool} 的 {field}={value!r} 不在上游值域内 / {tool}: {field}={value!r} is not a supported value.",
        code="tool.predictive_invalid_option",
        details={"tool": tool, "field": field, "value": value, "allowed": list(allowed)},
    )


_SNAPSHOT_HEADER_LINE_RE = re.compile(r"^\[[^\]\n]+\]$")


def _replace_snapshot_section(text: str, title: str, body: list[str] | None) -> str:
    """把快照里 `[title]` 整段换成 body（None=删段；段不存在则追加到末尾）。段间空行照旧。"""
    lines = f"{text or ''}".split("\n")
    header = f"[{title}]"
    if header not in lines:
        if body is None:
            return text
        block = "\n".join([header, *body])
        return f"{text.rstrip()}\n\n{block}" if f"{text or ''}".strip() else block
    start = lines.index(header)
    end = start + 1
    while end < len(lines) and not _SNAPSHOT_HEADER_LINE_RE.match(lines[end]):
        end += 1
    new_block = [] if body is None else [header, *body]
    if body is not None and end < len(lines):
        new_block.append("")
    merged = "\n".join(lines[:start] + new_block + lines[end:])
    return re.sub(r"\n{3,}", "\n\n", merged).strip()


def _human_scalar(value: Any) -> str:
    """上游 humanReadableFields.formatHumanValue 的标量/数组子集（心易卦面只有这两形）。"""
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        text = "、".join(item for item in (_human_scalar(v) for v in value) if item and item != "—")
        return text or "—"
    if isinstance(value, dict):
        text = "；\n".join(f"{k}：{_human_scalar(v)}" for k, v in value.items() if _human_scalar(v) != "—")
        return text or "—"
    return f"{value}".strip()


def _join_lines(lines: list[Any]) -> str:
    return "\n".join(text for text in (_msg(line) for line in lines) if text).strip()


def _solunar_body_lon(chart_response: dict[str, Any], body: str) -> float | None:
    """从 /chart 响应取日/月黄经（同上游 lonOf）。"""
    chart = chart_response.get("chart") if isinstance(chart_response.get("chart"), dict) else {}
    wanted = "Sun" if body == "sun" else "Moon"
    for obj in chart.get("objects") or []:
        if isinstance(obj, dict) and obj.get("id") == wanted:
            try:
                return float(obj.get("lon"))
            except (TypeError, ValueError):
                return None
    return None


def _shift_moment(moment: str, days: float) -> str:
    """把 'YYYY-MM-DD HH:MM:SS' 平移若干天（可为负），同上游 shiftMoment。"""
    base = datetime.strptime(moment, "%Y-%m-%d %H:%M:%S")
    return (base + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")


def _chart_body_lon_speed(chart_response: Any, body: str) -> tuple[float | None, Any]:
    """(黄经, 速度)：同上游 chartFacts.getObj（先 objectMap[id]、再 chart.objects）→ planets[k].lon / .speed(=lonspeed)。"""
    if not isinstance(chart_response, dict):
        return None, None
    wanted = "Sun" if body == "sun" else "Moon"
    obj: Any = None
    object_map = chart_response.get("objectMap")
    if isinstance(object_map, dict) and isinstance(object_map.get(wanted), dict):
        obj = object_map.get(wanted)
    else:
        chart = chart_response.get("chart") if isinstance(chart_response.get("chart"), dict) else {}
        obj = next((o for o in chart.get("objects") or [] if isinstance(o, dict) and o.get("id") == wanted), None)
    if not isinstance(obj, dict):
        return None, None
    lon = obj.get("lon")
    if isinstance(lon, bool) or not isinstance(lon, (int, float)):
        return None, obj.get("lonspeed")
    return float(lon), obj.get("lonspeed")


def _fmt_moment(value: datetime) -> str:
    """moment.format('YYYY-MM-DD HH:mm:ss')：年份补足四位（strftime 的 %Y 对 <1000 年不补零）。"""
    return f"{value.year:04d}-{value.month:02d}-{value.day:02d} {value.hour:02d}:{value.minute:02d}:{value.second:02d}"


def _js_math_round(value: float) -> int:
    """JS Math.round：half 一律向 +∞（与 _js_round 同口径，此处不吞非数值）。"""
    return math.floor(value + 0.5)


def _drop_none(mapping: dict[str, Any]) -> dict[str, Any]:
    """JSON.stringify 丢 undefined 键：请求体里 None 值的键不发（上游对象字面量里缺席的字段即此形）。"""
    return {k: v for k, v in mapping.items() if v is not None}


def _gz_text(item: Any) -> str:
    if isinstance(item, dict):
        for key in ("ganzhi", "ganzi", "ganZhi"):
            text = _msg(item.get(key))
            if text:
                return text
        stem = item.get("stem")
        branch = item.get("branch")
        if isinstance(stem, dict) and isinstance(branch, dict):
            return f"{_msg(stem.get('name') or stem.get('gan'))}{_msg(branch.get('name') or branch.get('zhi'))}".strip()
    return _msg(item)
