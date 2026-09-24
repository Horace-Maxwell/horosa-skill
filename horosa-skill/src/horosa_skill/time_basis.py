"""跨技法「时间基准」自声明（单源）——逐字移植上游 `astrostudyui/src/utils/timeBasisLine.js`（Horosa-Public @ 9b74714b）。

各技法 [起盘信息] 段追加一行，让 AI 与读者知道这张盘的日柱/宫位是按哪种时间口径起的——八字默认真太阳时
（经度+均时差校正），七政/占星按输入钟面时刻与时区换算，同一个 23:40 出生在不同技法里日柱可差一柱，
这是口径差异而非计算错误。只追加一行、不改既有字段顺序。上游消费方：BaZi.js / GuoLaoChartMain.js /
astroAiSnapshot.js（星盘族 [起盘信息]，`timeAlg: 1`）。
"""
from __future__ import annotations

import math
from typing import Any

# timeBasisLine.js:5
TIME_ALG_LABEL: dict[str, str] = {
    "0": "真太阳时(经度+均时差校正)",
    "1": "钟表时(按输入钟面时刻,无真太阳时校正)",
    "2": "春分定卯时",
    "3": "平太阳时(仅经度校正,无均时差)",
}

# timeBasisLine.js:40 —— 七政专用补注（本页一张盘上真有两套时标）。
GUOLAO_TIME_BASIS_NOTE = "本页两套时标：盘面星体与宫位按上列基准；四柱由排盘服务按真太阳时(经度+均时差)另算；琴堂逢酉身宫的时支按钟面时刻取"


def _js_str(value: Any) -> str:
    """JS 模板串 `${v}` 的等价（bool → true/false、整值浮点去 .0）。"""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return str(int(value))
    return f"{value}"


def time_basis_label(time_alg: Any) -> str:
    """timeBasisLine.js:7 timeBasisLabel：缺省 → 钟表时；认不出的码原样回显。"""
    if time_alg is None or _js_str(time_alg) == "":
        return TIME_ALG_LABEL["1"]
    return TIME_ALG_LABEL.get(_js_str(time_alg)) or _js_str(time_alg)


def _yes_no(value: Any, fallback: str) -> str:
    """timeBasisLine.js:14：缺位 → fallback；0 / '0' / false → 否；其余 → 是（JS 严格相等语义）。"""
    if value is None or _js_str(value) == "":
        return fallback
    if value is False or value == "0" or (isinstance(value, (int, float)) and not isinstance(value, bool) and value == 0):
        return "否"
    return "是"


def build_time_basis_line(
    *,
    time_alg: Any = None,
    late_zi_hour_use_next_day: Any = None,
    after23_new_day: Any = None,
    zone: Any = None,
    note: Any = None,
) -> str:
    """timeBasisLine.js:24 buildTimeBasisLine：单行文本；缺参按各技法惯例给缺省（晚子时归次日=否、23 点换日=否）。"""
    parts = [f"时间基准：{time_basis_label(time_alg)}"]
    parts.append(f"晚子时归次日：{_yes_no(late_zi_hour_use_next_day, '否')}")
    parts.append(f"23 点换日：{_yes_no(after23_new_day, '否')}")
    if zone is not None and _js_str(zone) != "":
        parts.append(f"时区：{_js_str(zone)}")
    if note is not None and _js_str(note) != "":
        parts.append(_js_str(note))
    return "；".join(parts)


__all__ = ["TIME_ALG_LABEL", "GUOLAO_TIME_BASIS_NOTE", "time_basis_label", "build_time_basis_line"]
