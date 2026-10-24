"""排盘报告的盘图：从引擎结果里**取**现成的位置数据（不算任何东西），画成星盘轮 / 紫微十二宫 / 六壬天地盘 / 奇门九宫。

分两半：
- `extract_figures(tool_name, data, technique_label)` 在 builder 里跑，产出可 JSON 序列化的图规格，挂在报告文档
  `figures` 上。给人读的字放在 `title` / `label` / `lines` / `text` 键里；繁体输出时 localize_document 转写报告里
  除机器键以外的所有字符串，位置 / 类型键（`branch` / `gua` / `kind` / `emphasis` / `cell_style`）已登记为机器键、
  不转——渲染器按简体地支与卦名定格。
- `pdf_flowables(...)` 在 PDF 渲染器里跑，把规格画成 reportlab flowable。

铁律 1（不手算）：这里只读引擎给的经度、宫头、相位、宫位内容；逆行看引擎给的 lonspeed 正负；
相位线只画引擎 aspects.normalAsp 里列出的相位，不自己量角度。
"""
from __future__ import annotations

import math
from typing import Any

# 西洋星盘轮：只给西洋体系画。七政四余 / 印度 / 宿占另有盘式（宫制、星名、方向都不同），套西洋轮是误导。
_WHEEL_EXCLUDED = frozenset({
    "guolao_chart", "india_chart", "india_rectify", "indiazeri", "suzhan", "qizhengzeri", "qizhengelection",
    "qizhengkin", "otherbu",
})
# 有星座与行星、但**没有十二宫与上升**的体系（巴比伦：引擎起盘信息明写「本体系无十二宫位、无相位、无上升点」）：只画星座环与行星。
_WHEEL_NO_HOUSES = frozenset({"babylon"})
_JIEQI_ORDER = ("春分", "夏至", "秋分", "冬至")
# 星座译名与引擎导出正文一致（牡羊 / 室女 / 宝瓶，见 knowledge/store.py 等处的对照表），盘图与文字不打架。
_SIGN_LABELS = ("牡羊", "金牛", "双子", "巨蟹", "狮子", "室女", "天秤", "天蝎", "射手", "摩羯", "宝瓶", "双鱼")
_BODY_LABELS = {
    "Sun": "日", "Moon": "月", "Mercury": "水", "Venus": "金", "Mars": "火", "Jupiter": "木", "Saturn": "土",
    "Uranus": "天", "Neptune": "海", "Pluto": "冥", "North Node": "北交", "South Node": "南交",
}
_NODES = frozenset({"North Node", "South Node"})
_LINE_ASPECTS = frozenset({60, 90, 120, 180})
# 推运 / 返照类：dirChart 是本次要看的盘，natalChart 是本命；有 dirChart 就两张都画。
_WHEEL_PATHS = (
    ("dirChart", "chart"), ("chart",), ("chart", "chart"), ("natalChart", "chart"), ("raw", "natalChart", "chart"),
    ("inner", "chart"), ("base", "chart"),
)

GRID12_POS = {  # 地支 → 4×4 外圈格位（行, 列）：巳午未申在上，寅丑子亥在下（紫微 / 六壬通行盘式）
    "巳": (0, 0), "午": (0, 1), "未": (0, 2), "申": (0, 3),
    "辰": (1, 0), "酉": (1, 3),
    "卯": (2, 0), "戌": (2, 3),
    "寅": (3, 0), "丑": (3, 1), "子": (3, 2), "亥": (3, 3),
}
GRID9_POS = {"巽": (0, 0), "离": (0, 1), "坤": (0, 2), "震": (1, 0), "中": (1, 1), "兑": (1, 2),
              "艮": (2, 0), "坎": (2, 1), "乾": (2, 2)}
_GUA_NUMBER = {"坎": "一", "坤": "二", "震": "三", "巽": "四", "中": "五", "乾": "六", "兑": "七", "艮": "八", "离": "九"}
_QIMEN_GODS = {"符": "值符", "蛇": "螣蛇", "阴": "太阴", "合": "六合", "虎": "白虎", "勾": "勾陈", "玄": "玄武",
               "雀": "朱雀", "地": "九地", "天": "九天"}


def _dig(data: Any, path: tuple[str, ...]) -> Any:
    for key in path:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def _is_wheel_chart(chart: Any) -> bool:
    return isinstance(chart, dict) and isinstance(chart.get("houses"), list) and isinstance(chart.get("objects"), list)


def _num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _wheel(chart: dict[str, Any], title: str, aspects: Any = None, *, houses: bool = True) -> dict[str, Any] | None:
    cusps: list[tuple[int, float]] = []
    for house in chart.get("houses") or []:
        if not isinstance(house, dict):
            continue
        house_id = str(house.get("id") or "")
        lon = _num(house.get("lon"))
        if house_id.startswith("House") and house_id[5:].isdigit() and lon is not None:
            cusps.append((int(house_id[5:]), lon % 360))
    cusps.sort()
    if [n for n, _ in cusps] != list(range(1, 13)):
        return None
    objects = {str(o.get("id")): o for o in chart.get("objects") or [] if isinstance(o, dict)}
    bodies = []
    for body_id, label in _BODY_LABELS.items():
        obj = objects.get(body_id)
        lon = _num(obj.get("lon")) if obj else None
        if lon is None:
            continue
        speed = _num(obj.get("lonspeed"))
        bodies.append({"id": body_id, "label": label, "lon": lon % 360,
                       "retro": bool(speed is not None and speed < 0)})  # 交点逆行与引擎位置表的「逆行」一致
    if len(bodies) < 7:
        return None
    asc = _num((objects.get("Asc") or {}).get("lon"))
    mc = _num((objects.get("MC") or {}).get("lon"))
    axes = [{"label": "上升", "lon": (asc if asc is not None else cusps[0][1]) % 360},
            {"label": "天顶", "lon": (mc if mc is not None else cusps[9][1]) % 360}]
    lines = []
    seen: set[tuple[str, str]] = set()
    present = {b["id"] for b in bodies}
    if isinstance(aspects, dict):
        for body_id, groups in aspects.items():
            if body_id not in present or not isinstance(groups, dict):
                continue
            for group in groups.values():
                for item in group if isinstance(group, list) else []:
                    other = str((item or {}).get("id"))
                    asp = _num((item or {}).get("asp"))
                    pair = tuple(sorted((body_id, other)))
                    if other in present and asp is not None and int(asp) in _LINE_ASPECTS and pair not in seen:
                        seen.add(pair)  # type: ignore[arg-type]
                        lines.append({"a": body_id, "b": other, "asp": int(asp)})
    return {
        "kind": "wheel",
        "title": title,
        "houses": houses,
        "cusps": [lon for _, lon in cusps],
        "axes": axes,
        "signs": [{"label": label} for label in _SIGN_LABELS],
        "bodies": bodies,
        "aspects": lines,
    }


def _chart_title(technique_label: str) -> str:
    # 「推运盘-太阳返照」→「太阳返照盘」；名字里已有「盘」（星盘、量化盘（…））不再叠字；纯西文名（Balbillus）加空格。
    name = technique_label.rsplit("-", 1)[-1].strip() or "星"
    if "盘" in name:
        return name
    return f"{name} 盘" if name.isascii() else f"{name}盘"


def _wheels(tool_name: str, data: dict[str, Any], technique_label: str) -> list[dict[str, Any]]:
    if tool_name in _WHEEL_EXCLUDED:
        return []
    charts = data.get("charts")
    if isinstance(charts, dict):  # 节气盘：一年四张（二分二至）
        ordered = sorted(charts.items(), key=lambda kv: _JIEQI_ORDER.index(kv[0]) if kv[0] in _JIEQI_ORDER else 99)
        out = [_wheel(item.get("chart"), f"{name}盘") for name, item in ordered
               if isinstance(item, dict) and _is_wheel_chart(item.get("chart"))]
        return [w for w in out if w][:4]
    # 相位：本命类在 data.aspects，卜卦 / 择日把整份原始结果放在 data.raw（同一张盘）。
    aspects = _dig(data, ("aspects", "normalAsp")) or _dig(data, ("raw", "aspects", "normalAsp"))
    if _is_wheel_chart(_dig(data, ("inner", "chart"))) and _is_wheel_chart(_dig(data, ("outer", "chart"))):
        return [w for w in (_wheel(data["inner"]["chart"], "甲方星盘"), _wheel(data["outer"]["chart"], "乙方星盘")) if w]
    direct = _dig(data, ("dirChart", "chart"))
    natal = _dig(data, ("natalChart", "chart"))
    if _is_wheel_chart(direct):
        out = [_wheel(direct, _chart_title(technique_label))]
        if _is_wheel_chart(natal):
            out.append(_wheel(natal, "本命盘"))
        return [w for w in out if w]
    for path in _WHEEL_PATHS:
        chart = _dig(data, path)
        if _is_wheel_chart(chart):
            plain = tool_name in _WHEEL_NO_HOUSES  # 无宫位体系同样「无相位」：不画相位线
            wheel = _wheel(chart, _chart_title(technique_label) if path[0] != "natalChart" else "本命盘",
                           aspects if path == ("chart",) and not plain else None, houses=not plain)
            return [wheel] if wheel else []
    return []


def _star_text(star: Any) -> str:
    if not isinstance(star, dict) or not star.get("name"):
        return ""
    text = str(star["name"])
    if star.get("starlight"):
        text += str(star["starlight"])
    if star.get("sihua"):
        text += f"·{star['sihua']}"
    return text


def _ziwei(data: dict[str, Any]) -> list[dict[str, Any]]:
    chart = data.get("chart")
    if not isinstance(chart, dict) or not isinstance(chart.get("houses"), list):
        return []
    cells = []
    for house in chart["houses"]:
        if not isinstance(house, dict) or "starsMain" not in house:
            return []
        ganzi = str(house.get("ganzi") or "")
        branch = ganzi[-1:] if ganzi else ""
        if branch not in GRID12_POS:
            return []
        main = [t for t in (_star_text(s) for s in house.get("starsMain") or []) if t]
        assist = [t for t in (_star_text(s) for s in (house.get("starsAssist") or []) + (house.get("starsEvil") or [])) if t]
        others = [str(s.get("name")) for s in (house.get("starsOthersGood") or []) + (house.get("starsOthersBad") or [])
                  if isinstance(s, dict) and s.get("name")]
        direction = house.get("direction") if isinstance(house.get("direction"), list) else []
        foot = " ".join(part for part in (
            str(house.get("phase") or ""),
            f"大限 {direction[0]}–{direction[1]}" if len(direction) == 2 else "",
        ) if part)
        name = str(house.get("name") or "")
        if house.get("isBody"):
            name += "（身）"
        cells.append({
            "branch": branch,
            "title": name,
            "label": ganzi,
            "lines": ["、".join(main) or "（空宫）", "、".join(assist), "、".join(others), foot],
            "emphasis": "main" if house.get("isLife") else "",
        })
    if len(cells) != 12:
        return []
    center = [line for line in (
        " ".join(str(chart.get(k) or "") for k in ("wuxingJuText",)).strip(),
        f"命主 {chart.get('lifeMaster')} · 身主 {chart.get('bodyMaster')}" if chart.get("lifeMaster") else "",
        f"子斗 {chart.get('zidou')} · 斗君 {chart.get('doujun')}" if chart.get("zidou") else "",
        str(chart.get("birth") or ""),
    ) if line]
    return [{"kind": "grid12", "title": "紫微命盘", "cells": cells, "center": {"title": "命盘", "lines": center}}]


def _liureng(data: dict[str, Any]) -> list[dict[str, Any]]:
    source = data.get("headless_liureng") if isinstance(data.get("headless_liureng"), dict) else data.get("liureng")
    if not isinstance(source, dict):
        return []
    layout = source.get("layout") if isinstance(source.get("layout"), dict) else {}
    down, up, gods = layout.get("downZi"), layout.get("upZi"), layout.get("houseTianJiang")
    if not (isinstance(down, list) and isinstance(up, list) and isinstance(gods, list) and len(down) == len(up) == len(gods) == 12):
        return []
    cells = []
    for branch, upper, god in zip(down, up, gods):
        if str(branch) not in GRID12_POS:
            return []
        cells.append({"branch": str(branch), "title": str(god), "label": str(upper), "lines": [f"地盘 {branch}"],
                      "emphasis": ""})
    center_lines = []
    ke_columns: list[dict[str, Any]] = []
    ke = source.get("ke")
    raw_ke = ke.get("raw") if isinstance(ke, dict) else ke
    if isinstance(raw_ke, list) and len(raw_ke) == 4 and all(isinstance(k, list) and len(k) >= 3 for k in raw_ke):
        # 四课传统竖格：右起一课，每课自上而下 天将 / 上神（天盘） / 下神（地盘）。
        names = ("一课", "二课", "三课", "四课")
        ke_columns = [{"title": names[i], "lines": [str(k[0]), str(k[1]), str(k[2])]} for i, k in enumerate(raw_ke)][::-1]
    chuan = source.get("sanChuan") if isinstance(source.get("sanChuan"), dict) else {}
    cuang, jiang, qin = chuan.get("cuang"), chuan.get("tianJiang"), chuan.get("liuQin")
    if isinstance(cuang, list) and len(cuang) == 3:
        for i, label in enumerate(("初传", "中传", "末传")):
            parts = [label, str(cuang[i])]
            if isinstance(jiang, list) and i < len(jiang):
                parts.append(str(jiang[i]))
            if isinstance(qin, list) and i < len(qin):
                parts.append(str(qin[i]))
            center_lines.append(" ".join(parts))
    title = str(chuan.get("name") or source.get("panStyleName") or "四课三传")
    return [{"kind": "grid12", "title": "六壬天地盘", "cells": cells,
             "center": {"title": title, "lines": center_lines, "columns": ke_columns}, "cell_style": "liureng"}]


def _qimen(data: dict[str, Any]) -> list[dict[str, Any]]:
    # 只认技法自己的 `data.pan`。三式合一的 data.qimen 与合盘自己的概览对不上（旬首 / 空亡不同，合盘还把「奇门遁甲」段标成未产出），
    # 画出来就是一份自相矛盾的报告（v0.43 第三轮评审）——宁可不画。
    pan = data.get("pan") if isinstance(data.get("pan"), dict) else None
    if pan is None or not isinstance(pan.get("cells"), list):
        return []
    cells = []
    for cell in pan["cells"]:
        if not isinstance(cell, dict) or str(cell.get("palaceName")) not in GRID9_POS:
            return []
        gua = str(cell["palaceName"])
        flags = [label for key, label in (
            ("isZhiFu", "值符"), ("isZhiShi", "值使"), ("hasKongWang", "空亡"), ("isYiMa", "马星"),
            ("hasJiXing", "击刑"), ("hasRuMu", "入墓"), ("hasMenPo", "门迫"),
        ) if cell.get(key)]
        if _QIMEN_GODS.get(str(cell.get("god") or "")) == "值符" or cell.get("god") == "值符":
            flags = [f for f in flags if f != "值符"]  # 八神值符已写在宫里，不再重复标
        if cell.get("isCenter"):
            lines = [f"天盘 {cell.get('tianGan') or ''}　地盘 {cell.get('diGan') or ''}"]
        else:
            god = str(cell.get("god") or "")
            star = str(cell.get("tianXing") or "")
            door = str(cell.get("door") or "")
            lines = [
                _QIMEN_GODS.get(god, god),
                f"{'天' + star if star and not star.startswith('天') else star}　{cell.get('tianGan') or ''}",
                f"{door + '门' if door and not door.endswith('门') else door}　{cell.get('diGan') or ''}",
            ]
        if cell.get("anGan"):
            lines.append(f"暗干 {cell['anGan']}")
        cells.append({"gua": gua, "title": f"{gua}{_GUA_NUMBER[gua]}宫", "lines": lines, "label": "　".join(flags),
                      "emphasis": "main" if cell.get("isZhiFu") or cell.get("isZhiShi") else ""})
    if len(cells) != 9:
        return []
    caption = "　".join(part for part in (
        str(pan.get("juText") or ""),
        f"值符 {pan.get('zhiFu')}" if pan.get("zhiFu") else "",
        f"值使 {pan.get('zhiShi')}" if pan.get("zhiShi") else "",
        f"旬首 {pan.get('xunShou')}" if pan.get("xunShou") else "",
        f"空亡 {pan.get('kongWang')}" if pan.get("kongWang") else "",
    ) if part)
    return [{"kind": "grid9", "title": "奇门盘", "cells": cells, "text": caption,
             "lines": ["每宫自上而下：八神 / 九星 天盘干 / 八门 地盘干"]}]


def _hexagram(data: dict[str, Any]) -> list[dict[str, Any]]:
    """六爻：本卦 / 变卦的爻画。爻画取引擎卦库的 `yao`（自下而上），动爻与六神取引擎 `lines`。"""
    descriptions = data.get("descriptions")
    current, changed = str(data.get("current_code") or ""), str(data.get("changed_code") or "")
    lines = data.get("lines")
    if not (isinstance(descriptions, dict) and isinstance(lines, list) and len(lines) == 6 and current in descriptions):
        return []
    moving = [bool(line.get("change")) for line in lines if isinstance(line, dict)]
    base = descriptions.get(current) if isinstance(descriptions.get(current), dict) else {}
    other = descriptions.get(changed) if isinstance(descriptions.get(changed), dict) else {}
    # 变卦只在「数据里的变卦码」与「本卦 + 动爻」对得上时才画：结果里没有引擎推出的之卦码，changed_code 可能是调用方
    # 另给的、与动爻不符（样例载荷就是这样：动爻得兑为泽，changed_code 却是既济）。对不上就只画本卦，之卦以正文「卦象」为准——
    # 绝不在这里自己翻爻推之卦（铁律 1）。
    consistent = (
        len(moving) == 6 and isinstance(base.get("yao"), list) and isinstance(other.get("yao"), list)
        and len(base["yao"]) == len(other["yao"]) == 6
        and all(bool(a) != bool(b) if m else bool(a) == bool(b) for a, b, m in zip(base["yao"], other["yao"], moving))
    )
    columns = []
    for code, label in ((current, "本卦"), (changed, "变卦")):
        entry = descriptions.get(code)
        if label == "变卦" and not consistent:
            continue
        if not isinstance(entry, dict) or not isinstance(entry.get("yao"), list) or len(entry["yao"]) != 6:
            continue
        columns.append({
            "title": f"{label} · {entry.get('desc') or entry.get('name') or ''}".strip(" ·"),
            "yao": [int(bool(v)) for v in entry["yao"]],
            "moving": [bool(line.get("change")) for line in lines] if label == "本卦" else [False] * 6,
            # 六神不从 data.lines 取：它与引擎「断卦结构」表的六神（按日干起）可以不一致（样例里就不一致），六神以正文为准。
            "lines": [""] * 6,
        })
    if not columns:
        return []
    note = "○ = 动爻（自下而上 初爻 → 上爻）；六神、六亲、世应见下文「断卦结构」" + ("" if len(columns) == 2 else "；之卦见下文「卦象」")
    return [{"kind": "hexagram", "title": "卦象", "columns": columns, "text": note}]


def extract_figures(tool_name: str, data: Any, technique_label: str = "") -> list[dict[str, Any]]:
    """返回这次结果能画的盘图规格（可能为空）。任何一种取不全就整张不画——画一张缺宫的盘比不画更糟。"""
    if not isinstance(data, dict):
        return []
    figures: list[dict[str, Any]] = []
    for extractor in (_ziwei, _qimen, _liureng, _hexagram):
        try:
            figures.extend(extractor(data))
        except (TypeError, ValueError, KeyError, IndexError):
            continue
    if not figures:
        try:
            figures.extend(_wheels(tool_name, data, technique_label or "星"))
        except (TypeError, ValueError, KeyError, IndexError):
            pass
    return figures


# ───────────────────────────── PDF 绘制 ─────────────────────────────

_ELEMENT_FILLS = ("#fbe9e1", "#eef3e2", "#eaf1f8", "#e6f1ef")  # 火 土 风 水（白羊起，四象循环）
_ASPECT_COLORS = {60: "#2b6cb0", 120: "#2f855a", 90: "#c53030", 180: "#c53030"}


def _spread(angles: list[float], min_gap: float) -> list[float]:
    """标签防重叠：输入按黄经升序，输出同序的显示角，相邻至少 min_gap 度、先后次序不变（只挪标签，刻度仍在真实黄经）。

    做法：从最大空档处把圆剪开拉直，相邻太近的并成一簇，簇以原位置均值为中心等距排开；并到不再相撞为止。
    """
    n = len(angles)
    if n < 2:
        return list(angles)
    min_gap = min(min_gap, 360 / n * 0.95)
    gaps = [((angles[(i + 1) % n] - angles[i]) % 360, i) for i in range(n)]
    cut = max(gaps)[1]  # 在 cut 与 cut+1 之间剪开
    order = [(cut + 1 + k) % n for k in range(n)]
    base = angles[order[0]]
    linear = [base + (angles[i] - base) % 360 for i in order]
    groups: list[list[int]] = [[k] for k in range(n)]

    def placed(group: list[int]) -> list[float]:
        center = sum(linear[k] for k in group) / len(group)
        return [center + (j - (len(group) - 1) / 2) * min_gap for j in range(len(group))]

    merged = True
    while merged:
        merged = False
        for g in range(len(groups) - 1):
            if placed(groups[g + 1])[0] - placed(groups[g])[-1] < min_gap - 1e-9:
                groups[g:g + 2] = [groups[g] + groups[g + 1]]
                merged = True
                break
    shown = [0.0] * n
    for group in groups:
        for k, value in zip(group, placed(group)):
            shown[order[k]] = value % 360
    return shown


def wheel_drawing(spec: dict[str, Any], size: float, font: str, bold_font: str, colors: Any) -> Any:
    """星盘轮（reportlab Drawing；PDF 直接嵌矢量，DOCX 经 drawing_to_png 转位图）。字号下限 7 pt，四周留轴标签的位置。"""
    from reportlab.graphics.shapes import Circle, Drawing, Line, String, Wedge

    drawing = Drawing(size, size)
    cx = cy = size / 2
    r_out = size / 2 - 16  # 外圈留 16 pt 给「上升 / 天顶」标签，不出图框、不压到相邻元素
    r_sign = r_out * 0.85
    r_house = r_out * 0.75
    r_body = r_out * 0.58
    r_core = r_out * 0.38
    small = max(7.0, size * 0.021)
    ink = colors.HexColor("#14211f")
    muted = colors.HexColor("#66706d")
    rule = colors.HexColor("#9fb0aa")
    teal = colors.HexColor("#0f766e")
    with_houses = spec.get("houses", True) is not False
    asc = spec["axes"][0]["lon"] if with_houses else 0.0  # 无宫体系：牡羊 0° 放左侧

    def angle(lon: float) -> float:
        return 180 + (lon - asc)

    def point(lon: float, radius: float) -> tuple[float, float]:
        a = math.radians(angle(lon))
        return cx + radius * math.cos(a), cy + radius * math.sin(a)

    for index, sign in enumerate(spec["signs"]):
        start = angle(index * 30)
        drawing.add(Wedge(cx, cy, r_out, start, start + 30, radius1=r_sign,
                          fillColor=colors.HexColor(_ELEMENT_FILLS[index % 4]), strokeColor=rule, strokeWidth=0.5))
        x, y = point(index * 30 + 15, (r_out + r_sign) / 2)
        drawing.add(String(x, y - small * 0.36, sign["label"], fontName=font, fontSize=max(small, size * 0.026), fillColor=ink,
                           textAnchor="middle"))
    drawing.add(Circle(cx, cy, r_sign, fillColor=colors.white, strokeColor=rule, strokeWidth=0.5))
    if with_houses:
        drawing.add(Circle(cx, cy, r_house, fillColor=None, strokeColor=rule, strokeWidth=0.4))
    drawing.add(Circle(cx, cy, r_core, fillColor=colors.HexColor("#fbfaf5"), strokeColor=rule, strokeWidth=0.5))
    if with_houses:
        cusps = spec["cusps"]
        for index, lon in enumerate(cusps):
            x1, y1 = point(lon, r_sign)
            x2, y2 = point(lon, r_house)
            drawing.add(Line(x1, y1, x2, y2, strokeColor=rule, strokeWidth=0.5))
            x1, y1 = point(lon, r_core)
            x2, y2 = point(lon, r_core * 0.92)
            drawing.add(Line(x1, y1, x2, y2, strokeColor=rule, strokeWidth=0.5))
            span = (cusps[(index + 1) % 12] - lon) % 360
            x, y = point(lon + span / 2, (r_sign + r_house) / 2)
            drawing.add(String(x, y - small * 0.36, str(index + 1), fontName=font, fontSize=small, fillColor=muted,
                               textAnchor="middle"))
        for axis in spec["axes"]:
            for lon, text in ((axis["lon"], axis["label"]), ((axis["lon"] + 180) % 360, None)):
                # 轴线只画在星座环与宫位环里（不穿过行星标签带），标签在圈外。
                x1, y1 = point(lon, r_out + 2)
                x2, y2 = point(lon, r_house)
                drawing.add(Line(x1, y1, x2, y2, strokeColor=teal, strokeWidth=1.4))
                if text:
                    x, y = point(lon, r_out + 9)
                    drawing.add(String(x, y - small * 0.36, text, fontName=bold_font, fontSize=small, fillColor=teal,
                                       textAnchor="middle"))
    bodies = sorted(spec["bodies"], key=lambda b: b["lon"])
    # 标签间隔按「星名 + 度数」两行的高度折成角度：盘侧边的标签是上下叠的，间隔小于这个高度就会压字（小图尤甚）。
    glyph = max(small + 1, size * 0.032)
    label_radius = r_body + r_out * 0.03
    shown = _spread([b["lon"] for b in bodies], max(10.0, math.degrees((glyph + small + 6) / label_radius)))
    inner_edge = r_house if with_houses else r_sign
    position = {}
    for body, display in zip(bodies, shown):
        tx1, ty1 = point(body["lon"], inner_edge)
        tx2, ty2 = point(body["lon"], inner_edge - 4)
        drawing.add(Line(tx1, ty1, tx2, ty2, strokeColor=ink, strokeWidth=0.9))
        if abs(((display - body["lon"] + 180) % 360) - 180) > 1.5:  # 标签被挪开了：细线连回真实位置
            lx, ly = point(display, r_body + r_out * 0.1)
            drawing.add(Line(tx2, ty2, lx, ly, strokeColor=colors.HexColor("#b8c4bf"), strokeWidth=0.4))
        x, y = point(display, label_radius)
        drawing.add(String(x, y, body["label"], fontName=bold_font, fontSize=glyph, fillColor=ink, textAnchor="middle"))
        # 度数（及逆行 R）紧贴在星名正下方：不管在盘的哪一侧，读者都知道它属于哪颗星（此前沿径线放在内侧，左下半盘看着像邻星的）。
        degree = f"{int(body['lon'] % 30)}°" + ("R" if body.get("retro") else "")
        drawing.add(String(x, y - small - 1, degree, fontName=font, fontSize=small,
                           fillColor=colors.HexColor("#c53030") if body.get("retro") else muted, textAnchor="middle"))
        position[body["id"]] = point(body["lon"], r_core)
    for aspect in spec.get("aspects") or []:
        a, b = position.get(aspect["a"]), position.get(aspect["b"])
        if a and b:
            drawing.add(Line(a[0], a[1], b[0], b[1], strokeColor=colors.HexColor(_ASPECT_COLORS.get(aspect["asp"], "#999999")),
                             strokeWidth=0.6, strokeOpacity=0.75))
    return drawing


def hexagram_drawing(spec: dict[str, Any], width: float, font: str, bold_font: str, colors: Any) -> Any:
    """本卦 / 变卦爻画：阳爻一整条、阴爻断开，动爻右侧标 ○，左侧六神。自上而下画上爻 → 初爻。"""
    from reportlab.graphics.shapes import Circle, Drawing, Rect, String

    columns = spec["columns"]
    bar_w, bar_h, gap = 92.0, 9.0, 9.0
    col_w = 200.0
    height = 6 * (bar_h + gap) + 26
    drawing = Drawing(min(width, col_w * len(columns)), height)
    ink = colors.HexColor("#14211f")
    for c, column in enumerate(columns):
        x0 = c * col_w + 52
        drawing.add(String(x0 + bar_w / 2, height - 12, column["title"], fontName=bold_font, fontSize=9.5, fillColor=ink,
                           textAnchor="middle"))
        for i in range(6):  # i = 0 是初爻（最下）
            y = (bar_h + gap) * i + 4
            if column["yao"][i]:
                drawing.add(Rect(x0, y, bar_w, bar_h, fillColor=ink, strokeColor=None))
            else:
                half = (bar_w - 14) / 2
                drawing.add(Rect(x0, y, half, bar_h, fillColor=ink, strokeColor=None))
                drawing.add(Rect(x0 + bar_w - half, y, half, bar_h, fillColor=ink, strokeColor=None))
            god = column["lines"][i]
            if god:
                drawing.add(String(x0 - 8, y + 1.5, god, fontName=font, fontSize=8, fillColor=colors.HexColor("#66706d"),
                                   textAnchor="end"))
            if column["moving"][i]:
                drawing.add(Circle(x0 + bar_w + 11, y + bar_h / 2, 3.6, fillColor=None,
                                   strokeColor=colors.HexColor("#c53030"), strokeWidth=1.2))
    return drawing


def pdf_flowables(figures: list[dict[str, Any]], *, content_width: float, font: str, bold_font: str,
                  styles: dict[str, Any], colors: Any, paragraph: Any, esc: Any, t: Any) -> list[Any]:
    """盘图 → flowable 列表（每张：图 + 图题）。styles 需含 cell / cell_muted / cell_strong / cell_title / cell_big / center* / caption。"""
    from reportlab.platypus import KeepTogether, Spacer, Table, TableStyle

    out: list[Any] = []
    wheels = [f for f in figures if f.get("kind") == "wheel"]
    # 一张：大图独占一行。多张（返照 + 本命、四季节气盘）：两张一排——轴标签留在各自图框里（wheel_drawing 外圈留白）、字号有下限，
    # 不再一张一页留半页空白（v0.43 第三轮评审）。
    per_row = 1 if len(wheels) == 1 else 2
    size = min(content_width * 0.74, 400.0) if per_row == 1 else content_width / 2 - 6
    for i in range(0, len(wheels), per_row):
        chunk = wheels[i:i + per_row]
        cells = [[wheel_drawing(w, size, font, bold_font, colors) for w in chunk] + [""] * (per_row - len(chunk)),
                 [paragraph(esc(w.get("title") or ""), styles["caption"]) for w in chunk] + [""] * (per_row - len(chunk))]
        block = [Table(cells, colWidths=[content_width / per_row] * per_row,
                       style=TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                         ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))]
        if any(w.get("aspects") for w in chunk):
            block.append(paragraph(esc(t("内圈连线为引擎给出的相位：蓝 = 六合，绿 = 三分，红 = 刑 / 冲；R = 逆行。")), styles["caption"]))
        elif any(b.get("retro") for w in chunk for b in w.get("bodies") or []):
            block.append(paragraph(esc(t("R = 逆行。")), styles["caption"]))
        block.append(Spacer(1, 10))
        out.append(KeepTogether(block))
    for figure in figures:
        kind = figure.get("kind")
        if kind == "grid12":
            out.append(KeepTogether([_grid12(figure, content_width, styles, colors, paragraph, esc),
                                     paragraph(esc(figure.get("title") or ""), styles["caption"]), Spacer(1, 10)]))
        elif kind == "grid9":
            block = [_grid9(figure, content_width, styles, colors, paragraph, esc)]
            for line in [figure.get("text"), *(figure.get("lines") or []), figure.get("title")]:
                if line:
                    block.append(paragraph(esc(str(line)), styles["caption"]))
            block.append(Spacer(1, 10))
            out.append(KeepTogether(block))
        elif kind == "hexagram":
            block = [Table([[hexagram_drawing(figure, content_width, font, bold_font, colors)]], colWidths=[content_width],
                           style=TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))]
            for line in (figure.get("text"), figure.get("title")):
                if line:
                    block.append(paragraph(esc(str(line)), styles["caption"]))
            block.append(Spacer(1, 10))
            out.append(KeepTogether(block))
    return out


def _cell_paragraphs(cell: dict[str, Any], styles: dict[str, Any], paragraph: Any, esc: Any, *, liureng: bool) -> list[Any]:
    if liureng:
        return [paragraph(esc(cell.get("title") or ""), styles["cell"]),
                paragraph(esc(cell.get("label") or ""), styles["cell_big"]),
                *[paragraph(esc(line), styles["cell_muted"]) for line in cell.get("lines") or [] if str(line).strip()]]
    head = esc(cell.get("title") or "")
    if cell.get("label"):
        head += f'　<font color="#66706d">{esc(cell["label"])}</font>'
    lines = [line for line in cell.get("lines") or [] if str(line).strip()]
    out = [paragraph(head, styles["cell_title"])]
    if lines:
        out.append(paragraph(esc(lines[0]), styles["cell_strong"]))
        out += [paragraph(esc(line), styles["cell"] if i < len(lines) - 2 else styles["cell_muted"])
                for i, line in enumerate(lines[1:])]
    return out


def _center_paragraphs(center: dict[str, Any], width: float, styles: dict[str, Any], colors: Any, paragraph: Any, esc: Any) -> list[Any]:
    from reportlab.platypus import Spacer, Table, TableStyle

    out = [paragraph(esc(center.get("title") or ""), styles["center_title"])]
    columns = center.get("columns") or []
    if columns:  # 六壬四课竖格（右起一课）
        rows = [[paragraph(esc(col.get("title") or ""), styles["cell_muted"]) for col in columns]]
        for r in range(3):
            style = styles["cell_strong"] if r == 1 else styles["cell"]
            rows.append([paragraph(esc((col.get("lines") or ["", "", ""])[r]), style) for col in columns])
        out.append(Table(rows, colWidths=[width * 0.42 / len(columns)] * len(columns), style=TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("GRID", (0, 1), (-1, -1), 0.4, colors.HexColor("#c9d3ce")),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ])))
        out.append(Spacer(1, 4))
    out += [paragraph(esc(line), styles["center"]) for line in center.get("lines") or []]
    return out


def _grid12(figure: dict[str, Any], width: float, styles: dict[str, Any], colors: Any, paragraph: Any, esc: Any) -> Any:
    from reportlab.platypus import Table, TableStyle

    liureng = figure.get("cell_style") == "liureng"
    grid: list[list[Any]] = [["" for _ in range(4)] for _ in range(4)]
    style = [
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c9d3ce")),
        ("SPAN", (1, 1), (2, 2)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER" if liureng else "LEFT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BACKGROUND", (1, 1), (2, 2), colors.HexColor("#f3f7f5")),
        ("VALIGN", (1, 1), (2, 2), "MIDDLE"),
    ]
    for cell in figure["cells"]:
        row, col = GRID12_POS[cell["branch"]]
        grid[row][col] = _cell_paragraphs(cell, styles, paragraph, esc, liureng=liureng)
        if cell.get("emphasis"):
            style += [("BACKGROUND", (col, row), (col, row), colors.HexColor("#eef6f2")),
                      ("BOX", (col, row), (col, row), 1.2, colors.HexColor("#0f766e"))]
    grid[1][1] = _center_paragraphs(figure.get("center") or {}, width, styles, colors, paragraph, esc)
    height = 26 * 2.835 if liureng else None
    return Table(grid, colWidths=[width / 4] * 4, rowHeights=[height] * 4 if height else None, style=TableStyle(style))


def _grid9(figure: dict[str, Any], width: float, styles: dict[str, Any], colors: Any, paragraph: Any, esc: Any) -> Any:
    from reportlab.platypus import Table, TableStyle

    grid: list[list[Any]] = [["" for _ in range(3)] for _ in range(3)]
    style = [
        ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#c9d3ce")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BACKGROUND", (1, 1), (1, 1), colors.HexColor("#f3f7f5")),
    ]
    for cell in figure["cells"]:
        row, col = GRID9_POS[cell["gua"]]
        parts = [paragraph(esc(cell.get("title") or ""), styles["cell_muted"])]
        lines = [line for line in cell.get("lines") or [] if str(line).strip()]
        if lines:
            parts.append(paragraph(esc(lines[0]), styles["cell"]))
            parts += [paragraph(esc(line), styles["cell_strong"]) for line in lines[1:]]
        if cell.get("label"):
            parts.append(paragraph(f'<font color="#b7791f">{esc(cell["label"])}</font>', styles["cell"]))
        grid[row][col] = parts
        if cell.get("emphasis"):
            style += [("BACKGROUND", (col, row), (col, row), colors.HexColor("#eef6f2")),
                      ("BOX", (col, row), (col, row), 1.2, colors.HexColor("#0f766e"))]
    # 与六壬 / 紫微盘同宽；每格同高（行高取三行里最高的那格），格内自上而下排，不再出现某行贴边。
    return Table(grid, colWidths=[width / 3] * 3, rowHeights=[33 * 2.835] * 3, style=TableStyle(style))


# ───────────────────────────── DOCX 位图（不依赖 renderPM） ─────────────────────────────


def drawing_to_png(drawing: Any, font_files: dict[str, tuple[str, int]], scale: float = 3.0) -> bytes | None:
    """把本模块画的 Drawing（Wedge / Circle / Line / Rect / String 五种图元）用 Pillow 画成 PNG，给 DOCX 用。

    reportlab 自带的位图后端 renderPM 要另装 rlPyCairo，干净安装里没有；Pillow 是 reportlab 的依赖，一定在。
    font_files：reportlab 字体名 → (TTF/TTC 路径, 子字体序号)；拿不到字体就返回 None（调用方退回文字说明）。
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        from reportlab.graphics.shapes import Circle, Line, Rect, String, Wedge
    except ImportError:
        return None
    width, height = int(drawing.width * scale), int(drawing.height * scale)
    image = Image.new("RGB", (width, height), "white")
    pen = ImageDraw.Draw(image)
    fonts: dict[tuple[str, float], Any] = {}

    def rgb(color: Any) -> tuple[int, int, int] | None:
        if color is None:
            return None
        return tuple(round(v * 255) for v in (color.red, color.green, color.blue))  # type: ignore[return-value]

    def xy(x: float, y: float) -> tuple[float, float]:
        return x * scale, height - y * scale

    def font_for(name: str, size: float) -> Any:
        key = (name, size)
        if key not in fonts:
            path, index = font_files.get(name) or next(iter(font_files.values()))
            fonts[key] = ImageFont.truetype(path, max(1, round(size * scale)), index=index)
        return fonts[key]

    for shape in drawing.contents:
        stroke = rgb(getattr(shape, "strokeColor", None))
        fill = rgb(getattr(shape, "fillColor", None))
        stroke_width = max(1, round((getattr(shape, "strokeWidth", 1) or 1) * scale))
        if isinstance(shape, Wedge):
            r0, r1 = shape.radius, shape.radius1 or 0
            a0, a1 = shape.startangledegrees, shape.endangledegrees
            steps = max(8, int(abs(a1 - a0)))
            outer = [xy(shape.centerx + r0 * math.cos(math.radians(a0 + (a1 - a0) * k / steps)),
                        shape.centery + r0 * math.sin(math.radians(a0 + (a1 - a0) * k / steps))) for k in range(steps + 1)]
            inner = [xy(shape.centerx + r1 * math.cos(math.radians(a1 - (a1 - a0) * k / steps)),
                        shape.centery + r1 * math.sin(math.radians(a1 - (a1 - a0) * k / steps))) for k in range(steps + 1)]
            pen.polygon(outer + inner, fill=fill, outline=stroke)
        elif isinstance(shape, Circle):
            (x0, y0), (x1, y1) = xy(shape.cx - shape.r, shape.cy + shape.r), xy(shape.cx + shape.r, shape.cy - shape.r)
            pen.ellipse([x0, y0, x1, y1], fill=fill, outline=stroke, width=stroke_width)
        elif isinstance(shape, Rect):
            (x0, y0), (x1, y1) = xy(shape.x, shape.y + shape.height), xy(shape.x + shape.width, shape.y)
            pen.rectangle([x0, y0, x1, y1], fill=fill, outline=stroke)
        elif isinstance(shape, Line):
            pen.line([xy(shape.x1, shape.y1), xy(shape.x2, shape.y2)], fill=stroke, width=stroke_width)
        elif isinstance(shape, String):
            anchor = {"middle": "ms", "end": "rs"}.get(getattr(shape, "textAnchor", "start"), "ls")
            pen.text(xy(shape.x, shape.y), shape.text, font=font_for(shape.fontName, shape.fontSize), fill=fill, anchor=anchor)
    import io

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
