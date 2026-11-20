"""出生时刻未知模式（审计输入一路待决项 1 第二档；第一档「只知时辰」在 service/api/tools.py::SHICHEN_PRECISION_TOOLS）。

以前 `time: "不详"` 一律拒绝——对西占式技法是对的起点，对「真的不知道」的用户是死路，而且结果里看不出模型自己编的钟点是假设。
现在按技法族定策略（每个本命类技法都归了族，tests/test_v052_birth_time_unknown.py 守「每个都声明了」）：

- **八字**（bazi_birth / bazi_direct）：按当地正午起，只给年 / 月 / 日三柱——时柱、命宫、身宫、十二串宫、含时柱 / 命宫 / 身宫的神煞与合冲行、
  小运去掉；五行力量 / 格局·用神 / 盲派结构整段略去（都算进了时柱）；起运岁数标约数。八字「时辰不详排三柱」是通行做法。
- **西洋本命盘族**（chart / chart13 / hellen_chart / draconic / harmonic / germany）：按当地正午起「无宫位盘」——只留行星与相位类段，
  去掉上升 / 天顶等四轴与宫位、阿拉伯点、日夜盘与依赖它们的古典段；月亮一天走 12–15°，度数与是否换星座写成「以出生钟点为准」。
- **其余本命类**（紫微 / 河洛 / 神数 / 七政 / 印度 / 推运 / 合盘…）：拒绝，但按族说清楚为什么、还能用什么（起课类不需要出生时刻）。

披露：结果 `data.birth_time = {precision: "unknown", computed_at, omitted_sections, masked_lines, uncertain}`，warnings 与 [起盘信息] 各写一行，技法卡同挂。
引擎不改：起盘照常按正午算，只在导出层过滤段与行（原始树 `full` 视图里仍在，故 warnings 明说那些字段不可用）。
"""
from __future__ import annotations

import re
from typing import Any

from horosa_skill.errors import bilingual

NOON = "12:00:00"

BAZI_TOOLS = frozenset({"bazi_birth", "bazi_direct"})
WESTERN_TOOLS = frozenset({"chart", "chart13", "hellen_chart", "draconic", "harmonic"})
GERMANY_TOOLS = frozenset({"germany"})
SUPPORTED_TOOLS = BAZI_TOOLS | WESTERN_TOOLS | GERMANY_TOOLS

# 拒绝时按族说清楚（键 = 技法注册名）
_MINGLI_REFUSE = frozenset({"ziwei_birth", "heluo", "canping", "yizhangjing", "zhengchuan", "shaozi", "tieban", "beiji", "nanji",
                            "chunzi", "xianqin", "cetian", "qizhengkin", "fendjing", "shenyishu", "dongya", "jieqi_birth",
                            "liureng_runyear"})
_PREDICTIVE_REFUSE = frozenset({"bezzafigure", "ephemeris", "extrareturns", "givenyear", "jaynesprog", "jayprofection", "lunarreturn",
                                "neroman", "planetaryages", "planetaryarc", "profection", "prog", "returntimeline", "solararc",
                                "solarreturn", "timelords", "vedicprog"})
_CHART_REFUSE = frozenset({"guolao_chart", "india_chart", "chart12", "relocation", "acg", "babylon", "transformchart", "zodiacsystems",
                           "zhufang", "suzhan", "prenatalsyzygy", "lunationphase", "keypoints", "michon", "agepoint", "balbillus",
                           "decennials", "distributions", "firdaria", "pd", "pdchart", "persiandirected", "triplicityrulers",
                           "yearsystem129", "zr", "india_rectify", "wangji", "wuzhao", "jingjue", "taixuan"})

_BAZI_OMIT = ("五行力量", "格局·用神", "盲派结构")
_BAZI_LINE_DROP = re.compile(r"^\|\s*时柱\s*\||^(?:时柱|命宫|身宫|十二串宫)：|^直接时间：")
_BAZI_PILLAR_MARK = re.compile(r"（(?:时|命|身)）")
_WESTERN_KEEP = ("起盘信息", "星与虚点", "相位", "行星", "月宿", "12分度", "主宰星链", "埃及历")
_GERMANY_KEEP = ("起盘信息", "行星", "TNP星体", "中点", "中点相位", "中点列表", "中点坐标", "赤纬接触")
_ANGLE_WORDS = re.compile(r"上升|天顶|下降|天底|中天|宿命点|福点|时主|命主星|\bAsc\b|\bASC\b|\bMC\b|\bIC\b|\bDsc\b|\bDSC\b|\bDesc\b"
                          r"|Ascendant|Midheaven|Vertex")
# 阿拉伯点（希腊点）都要上升起算：名字清单取自 chart 快照实跑（2026-11-20）；不收「顶点」（Yod 的顶点）、「交点 / 映点 / 中点 / 朔望点」
_LOT_WORDS = re.compile(r"(?:福|灵|弱|爱|勇|赢|罪|信心|占有|婚姻|子女|母爱|父权|父亲|友情|精神|根基|擢升|胜利|生命|爱欲|死亡|朋友|旅行|报应|必然"
                        r"|女儿|儿子|勇气|事业|驾驭|灾厄|宿敌|光耀|骑术|资财|疾厄|宿命|阿拉伯)点")
_HOUSE_MARK = re.compile(r"\s*\(\d+(?:st|nd|rd|th);[^)]*\)")
# 表头里这些列只有知道时刻才有意义：落宫 / 宫位、地平坐标（随钟点转）、含日夜三分的禀赋分值
_BLANK_COLUMNS = frozenset({"落宫", "入垣宫", "擢升宫", "宫主落宫(整宫)", "真地平纬度", "视地平纬度", "地坪经度", "分值"})
_HEADER_DROP = re.compile(r"^(?:直接时间：|时间：|说明：.*宫主宫位标记|时主星：|命主星：|排盘规则：)")


def family(tool_name: str) -> str | None:
    if tool_name in BAZI_TOOLS:
        return "bazi"
    if tool_name in WESTERN_TOOLS:
        return "western"
    if tool_name in GERMANY_TOOLS:
        return "germany"
    return None


def refusal_text(tool_name: str) -> tuple[str, str]:
    """不支持未知时刻的本命类技法：按族说为什么、还能用什么。"""
    if tool_name in _MINGLI_REFUSE:
        return ("这门技法按时辰起盘（命宫 / 起数都要时辰），缺出生时刻整盘不成立：问到时辰就能排（只知时辰也行，传「辰时」）。"
                "完全不知道出生时刻时，八字可以只排三柱（time 传「不详」），或改用起课类（六爻 / 奇门 / 六壬，用的是提问的此刻）问具体的事。",
                "This technique is cast from the double-hour (its life palace / counts need it), so it cannot run without a birth time: "
                "ask for the double-hour (passing '辰时' is enough). With no time at all, BaZi can give three pillars (time: '不详'), or use a "
                "divination technique (Liu Yao / Qi Men / Liu Ren), which uses the moment of the question.")
    if tool_name in _PREDICTIVE_REFUSE:
        return ("推运从本命盘起（上升 / 宫位 / 日夜盘 / 精确的日月位置），缺出生时刻算不出来：请问到出生钟点。"
                "只想看一段时间的天象可用行星周期（planet_cycles，不需要出生时刻）；八字可排三柱看大运（time 传「不详」）。",
                "Predictive techniques start from the natal chart (Ascendant / houses / sect / exact luminaries), so they need the birth time: "
                "ask for it. For the sky over a period use planet_cycles (no birth time needed); BaZi can give three pillars with luck "
                "periods (time: '不详').")
    if tool_name in _CHART_REFUSE:
        return ("这门技法依赖上升 / 宫位 / 日夜盘或精确的月亮位置，缺出生时刻算不出来：请问到出生钟点。"
                "完全不知道时刻时，本命盘（chart）可以起「无宫位盘」（time 传「不详」）；看行运用星历（ephemeris）或行星周期（planet_cycles）。",
                "This technique depends on the Ascendant / houses / sect or the Moon's exact position, so it needs the birth time: ask for it. "
                "With no time at all, the natal chart (chart) can give a no-houses chart (time: '不详'); for transits use ephemeris or planet_cycles.")
    return ("缺出生时刻：请问到出生钟点再起盘。完全不知道时刻时，八字可排三柱、本命盘可起无宫位盘（time 传「不详」）。",
            "The birth time is missing: ask for it. With no time at all, BaZi gives three pillars and the natal chart a no-houses chart (time: '不详').")


def _sections(snapshot_text: str) -> list[tuple[str, list[str]]]:
    out: list[tuple[str, list[str]]] = []
    for line in snapshot_text.splitlines():
        match = re.fullmatch(r"\[(.+)\]\s*", line)
        if match:
            out.append((match.group(1), []))
        elif out:
            out[-1][1].append(line)
        else:
            out.append(("", [line]))
    return out


def _filter_bazi(title: str, lines: list[str]) -> tuple[list[str] | None, int]:
    if title in _BAZI_OMIT:
        return None, 0
    kept, dropped = [], 0
    for line in lines:
        if _BAZI_LINE_DROP.search(line.strip()) or _BAZI_PILLAR_MARK.search(line):
            dropped += 1
            continue
        kept.append(line)
    if title == "大运":
        cut = next((i for i, line in enumerate(kept) if line.startswith("小运")), None)
        if cut is not None:
            dropped += len(kept) - cut
            kept = kept[:cut]
        kept = [f"{line}（出生时刻未知：起运岁数是约数，前后约差两个月）" if line.startswith("起运：") else line for line in kept]
    return kept, dropped


def _is_point_off(text: str) -> bool:
    return bool(_ANGLE_WORDS.search(text) or _LOT_WORDS.search(text))


def _filter_header(lines: list[str]) -> list[str]:
    kept = []
    for line in lines:
        if _HEADER_DROP.search(line):
            continue
        line = re.sub(r"\s*[，,]\s*[日夜]生盘", "", line)
        line = re.sub(r"^((?:回归|恒星)黄道[^，,]*)[，,].*$", r"\1（无宫位）", line)
        line = re.sub(r"(\d{4}-\d{2}-\d{2}\s+)12:00(?::00)?", r"\g<1>12:00（出生时刻未知，按正午起）", line)
        kept.append(line)
    return kept


def _filter_body(lines: list[str]) -> tuple[list[str], int]:
    """逐行过滤：去宫位标记、阿拉伯点 / 四轴行，整块（◆ 小节 / 主体： / 带宫位标记的点名小标题）随标题一起删，表格里依赖时刻的列抹成 —。"""
    kept: list[str] = []
    dropped = 0
    skip: str | None = None      # 正在跳过的块：diamond / subject / named
    blank: set[int] = set()
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("◆"):
            skip = "diamond" if (_is_point_off(stripped) or "宫" in stripped) else None
        elif stripped.startswith("主体："):
            skip = "subject" if _is_point_off(stripped) else (None if skip in ("subject", "named") else skip)
        elif not stripped.startswith("|") and _HOUSE_MARK.search(stripped):
            if skip in (None, "named"):
                skip = "named" if _is_point_off(_HOUSE_MARK.sub("", stripped)) else None
        if skip is not None:
            dropped += 1
            continue
        if stripped.startswith("|"):
            cells = stripped.strip("|").split("|")
            names = [cell.strip() for cell in cells]
            if any(name in _BLANK_COLUMNS for name in names):
                blank = {i for i, name in enumerate(names) if name in _BLANK_COLUMNS}
            elif not set(stripped) <= set("|-: ") and blank:
                cells = [" — " if i in blank else cell for i, cell in enumerate(cells)]
                line = "|" + "|".join(cells) + "|"
            if _is_point_off(_HOUSE_MARK.sub("", line)):
                dropped += 1
                continue
        else:
            blank = set()
            if _is_point_off(_HOUSE_MARK.sub("", stripped)):
                dropped += 1
                continue
        line = _HOUSE_MARK.sub("", line)
        line = line.replace("日三分", "日三分（须白天出生）").replace("夜三分", "夜三分（须夜间出生）")
        kept.append(line)
    return kept, dropped


def _filter_angles(title: str, lines: list[str], keep: tuple[str, ...]) -> tuple[list[str] | None, int]:
    if title not in keep:
        return None, 0
    if title == "起盘信息":
        kept = _filter_header(lines)
        return kept, len(lines) - len(kept)
    return _filter_body(lines)


def filter_snapshot(tool_name: str, snapshot_text: str) -> tuple[str, list[str], int]:
    """(过滤后的快照文本, 整段略去的段名, 删掉的行数)。"""
    fam = family(tool_name)
    out: list[str] = []
    omitted: list[str] = []
    dropped_total = 0
    for title, lines in _sections(snapshot_text):
        if fam == "bazi":
            kept, dropped = _filter_bazi(title, lines)
        else:
            kept, dropped = _filter_angles(title, lines, _GERMANY_KEEP if fam == "germany" else _WESTERN_KEEP)
        dropped_total += dropped
        if kept is None or (title and not any(line.strip() for line in kept)):
            if not title:
                continue
            # 段名留着、写明为什么空：导出契约见段缺席会补「本次计算未返回」的占位（那是另一回事），AI 也该知道这段是有意略去的
            omitted.append(title)
            out.extend([f"[{title}]", _OMITTED_LINE, ""])
            continue
        if title == "起盘信息":
            if fam == "bazi":
                kept = [line for line in kept if not line.startswith(("直接时间：", "时间："))]
            kept.append(_header_line(fam))
        out.append(f"[{title}]" if title else "")
        out.extend(kept)
        out.append("")
    return "\n".join(out).strip() + "\n", omitted, dropped_total


_OMITTED_LINE = "（出生时刻未知：本段依赖出生时刻（时柱 / 上升 / 宫位 / 日夜盘），已略去。/ Birth time unknown: this section depends on it and was removed.）"


def _header_line(fam: str | None) -> str:
    if fam == "bazi":
        return "出生时刻：未知——按当地正午 12:00 起，只给年 / 月 / 日三柱；时柱及依赖时柱的内容已略去。"
    return "出生时刻：未知——按当地正午 12:00 起无宫位盘：只读行星星座与相位；上升 / 天顶 / 宫位不可用，月亮度数与是否换星座以出生钟点为准。"


def apply(tool_name: str, response_data: dict[str, Any]) -> dict[str, Any]:
    """在导出契约挂好之前过滤快照：之后的 export_snapshot / export_text 由过滤后的快照解析，正文里就不会出现时柱 / 上升段。"""
    if not isinstance(response_data, dict) or not isinstance(response_data.get("snapshot_text"), str):
        return response_data
    text, omitted, dropped = filter_snapshot(tool_name, response_data["snapshot_text"])
    out = dict(response_data)
    out["snapshot_text"] = text
    out.pop("export_snapshot", None)   # 由过滤后的快照重新解析
    fam = family(tool_name)
    out["birth_time"] = {"precision": "unknown", "computed_at": NOON, "omitted_sections": omitted, "masked_lines": dropped,
                         "uncertain": (["起运岁数"] if fam == "bazi" else ["月亮度数", "月亮星座（若当天换座）"])}
    warning = (bilingual("出生时刻未知：按正午起、只给三柱；时柱、命宫、身宫与五行力量 / 格局·用神等依赖时柱的段已略去（原始树里仍有，勿引用）。",
                         "Birth time unknown: computed at noon with three pillars only; the hour pillar, life / body palace and the sections that "
                         "depend on it were removed (still in the raw tree — do not quote them).")
               if fam == "bazi" else
               bilingual("出生时刻未知：按正午起无宫位盘；上升 / 天顶 / 宫位、阿拉伯点与日夜盘相关的段已略去（原始树里仍有，勿引用），月亮度数以出生钟点为准。",
                         "Birth time unknown: a no-houses chart computed at noon; the Ascendant / MC / houses, lots and sect-dependent sections were "
                         "removed (still in the raw tree — do not quote them); the Moon's exact degree depends on the birth time."))
    out["_warnings"] = [*(out.get("_warnings") or []), warning]
    return out
