from __future__ import annotations

from datetime import timezone, datetime
from typing import Any

from pydantic import ValidationError

from horosa_skill import __version__
from horosa_skill.config import Settings
from horosa_skill.engine.client import HorosaApiClient
from horosa_skill.engine.decennials import (
    DECENNIAL_CALENDAR_ACTUAL,
    DECENNIAL_CALENDAR_TRADITIONAL,
    DECENNIAL_DAY_METHOD_HEPHAISTIO,
    DECENNIAL_DAY_METHOD_VALENS,
    DECENNIAL_ORDER_CHALDEAN,
    DECENNIAL_ORDER_ZODIACAL,
    DECENNIAL_START_MODE_SECT_LIGHT,
    build_decennial_timeline,
)
from horosa_skill.engine.js_client import HorosaJsEngineClient
from horosa_skill.engine.registry import TOOL_DEFINITIONS, ToolDefinition
from horosa_skill.engine.router import select_tools
from horosa_skill.errors import DispatchResolutionError, HorosaSkillError, ToolTransportError, ToolValidationError
from horosa_skill.exports import build_export_registry, get_technique_info, parse_export_content
from horosa_skill.knowledge import build_knowledge_registry, read_knowledge_entry
from horosa_skill.memory.store import MemoryStore
from horosa_skill.runtime import HorosaRuntimeManager
from horosa_skill.schemas.common import DispatchEnvelope, ErrorInfo, ToolEnvelope
from horosa_skill.schemas.tools import DispatchInput, MemoryAnswerInput, MemoryQueryInput, MemoryShowInput
from horosa_skill.tracing import TraceRecorder


TOOL_EXPORT_TECHNIQUE_MAP: dict[str, str] = {
    "chart": "astrochart",
    "chart13": "astrochart_like",
    "hellen_chart": "astrochart_like",
    "guolao_chart": "guolao",
    "solarreturn": "solarreturn",
    "lunarreturn": "lunarreturn",
    "solararc": "solararc",
    "givenyear": "givenyear",
    "profection": "profection",
    "pd": "primarydirect",
    "pdchart": "primarydirchart",
    "zr": "zodialrelease",
    "relative": "relative",
    "india_chart": "indiachart",
    "ziwei_birth": "ziwei",
    "ziwei_rules": "ziwei",
    "bazi_birth": "bazi",
    "bazi_direct": "bazi",
    "liureng_gods": "liureng",
    "liureng_runyear": "liureng",
    "jieqi_year": "jieqi",
    "nongli_time": "generic",
    "gua_desc": "sixyao",
    "gua_meiyi": "sixyao",
    "qimen": "qimen",
    "taiyi": "taiyi",
    "jinkou": "jinkou",
    "suzhan": "suzhan",
    "sixyao": "sixyao",
    "tongshefa": "tongshefa",
    "sanshiunited": "sanshiunited",
    "germany": "germany",
    "firdaria": "firdaria",
    "decennials": "decennials",
    "otherbu": "otherbu",
}


def _generic_summary(tool_name: str, data: dict[str, Any]) -> list[str]:
    if tool_name == "export_registry":
        count = len(data.get("techniques", []))
        summary = [f"已输出 {count} 个星阙 AI 导出 technique 的完整注册表。"]
        selected = data.get("selected_technique")
        if isinstance(selected, dict) and selected.get("label"):
            summary.append(f"当前聚焦：{selected['label']}。")
        return summary
    if tool_name == "export_parse":
        summary = ["已将星阙 AI 导出文本转换为结构化分段 JSON。"]
        detected = data.get("section_titles_detected", [])
        if detected:
            summary.append(f"识别到 {len(detected)} 个分段标题。")
        selected = data.get("selected_sections", [])
        if selected:
            summary.append(f"当前导出将保留 {len(selected)} 个目标分段。")
        return summary
    if tool_name == "knowledge_registry":
        domains = data.get("domains", [])
        summary = [f"已输出 {len(domains)} 个悬浮知识域的可读目录。"]
        if domains:
            summary.append(f"当前包含：{'、'.join(one.get('domain', '') for one in domains if one.get('domain'))}。")
        return summary
    if tool_name == "knowledge_read":
        summary = ["已读取星阙悬浮知识，并转换为稳定的本地可读文档。"]
        if data.get("domain") and data.get("category"):
            summary.append(f"知识域：{data['domain']} / {data['category']}。")
        if data.get("title"):
            summary.append(f"条目：{data['title']}。")
        return summary
    if tool_name == "qimen":
        pan = data.get("pan", {})
        summary = ["已运行本地奇门遁甲 headless 算法。"]
        if pan.get("juText"):
            summary.append(f"局数：{pan['juText']}。")
        if pan.get("zhiFu") and pan.get("zhiShi"):
            summary.append(f"值符 {pan['zhiFu']}，值使 {pan['zhiShi']}。")
        return summary
    if tool_name == "taiyi":
        pan = data.get("pan", {})
        summary = ["已运行本地太乙 headless 算法。"]
        if pan.get("zhao"):
            summary.append(f"命式：{pan['zhao']}。")
        if pan.get("kook"):
            summary.append(f"局式：{pan['kook']}。")
        return summary
    if tool_name == "jinkou":
        result = data.get("jinkou", {})
        summary = ["已运行本金口诀 headless 算法。"]
        if result.get("guiName") and result.get("jiangName"):
            summary.append(f"贵神 {result['guiName']}，将神 {result['jiangName']}。")
        if result.get("wangElem"):
            summary.append(f"旺神五行：{result['wangElem']}。")
        return summary
    if tool_name == "suzhan":
        chart = data.get("chart", {})
        summary = ["已生成宿占 / 宿盘输出。"]
        if isinstance(chart.get("objects"), list):
            summary.append(f"星曜数量：{len(chart['objects'])}。")
        return summary
    if tool_name == "sixyao":
        summary = ["已生成易卦 / 六爻输出。"]
        if data.get("current_code"):
            summary.append(f"本卦编码：{data['current_code']}。")
        if data.get("changed_code"):
            summary.append(f"之卦编码：{data['changed_code']}。")
        return summary
    if tool_name == "tongshefa":
        model = data.get("tongshefa", {})
        summary = ["已运行本地统摄法算法。"]
        if model.get("baseLeft", {}).get("name") and model.get("baseRight", {}).get("name"):
            summary.append(f"本卦：左{model['baseLeft']['name']}，右{model['baseRight']['name']}。")
        if model.get("main_relation"):
            summary.append(f"主关系：{model['main_relation']}。")
        return summary
    if tool_name == "sanshiunited":
        summary = ["已运行本地三式合一聚合算法。"]
        qimen = data.get("qimen", {})
        taiyi = data.get("taiyi", {})
        if qimen.get("juText"):
            summary.append(f"奇门局数：{qimen['juText']}。")
        taiyi_kook = taiyi.get("kook")
        if isinstance(taiyi_kook, dict) and taiyi_kook.get("text"):
            summary.append(f"太乙局式：{taiyi_kook['text']}。")
        elif taiyi_kook:
            summary.append(f"太乙局式：{taiyi_kook}。")
        return summary
    if tool_name == "guolao_chart":
        chart = data.get("chart", {})
        summary = ["已生成七政四余盘。"]
        if isinstance(chart.get("objects"), list):
            summary.append(f"星曜数量：{len(chart['objects'])}。")
        return summary
    if tool_name == "hellen_chart":
        chart = data.get("chart", {})
        summary = ["已生成希腊星盘。"]
        if isinstance(chart, dict):
            summary.append(f"字段数：{len(chart.keys())}。")
        return summary
    if tool_name == "germany":
        summary = ["已生成量化盘 / 中点盘。"]
        if isinstance(data.get("midpoints"), list):
            summary.append(f"中点数量：{len(data['midpoints'])}。")
        return summary
    if tool_name == "firdaria":
        firdaria = data.get("firdaria", [])
        summary = ["已生成法达星限。"]
        if isinstance(firdaria, list):
            summary.append(f"主限数量：{len(firdaria)}。")
        return summary
    if tool_name == "decennials":
        timeline = data.get("timeline", {})
        summary = ["已生成十年大运。"]
        if isinstance(timeline.get("list"), list):
            summary.append(f"L1 层数量：{len(timeline['list'])}。")
        resolved = timeline.get("resolvedStartPlanet")
        if resolved:
            summary.append(f"起运主星：{resolved}。")
        return summary
    if tool_name == "otherbu":
        summary = ["已生成西洋游戏 / 占星骰子结果。"]
        if data.get("planet") and data.get("sign"):
            summary.append(f"骰面：{data['planet']} / {data['sign']}。")
        return summary
    lines = [f"工具 `{tool_name}` 已返回结构化结果。"]
    keys = sorted(data.keys())
    if keys:
        lines.append(f"顶层字段：{', '.join(keys[:8])}{' ...' if len(keys) > 8 else ''}")
    if "chart" in data:
        lines.append("结果包含 chart 结构。")
    if "predictives" in data:
        lines.append("结果包含 predictive / 时运相关数据。")
    if "bazi" in data:
        lines.append("结果包含八字结构。")
    if "liureng" in data:
        lines.append("结果包含六壬结构。")
    if "jieqi24" in data and isinstance(data["jieqi24"], list):
        lines.append(f"结果包含 {len(data['jieqi24'])} 个节气节点。")
    return lines[:4]


def _extract_entities(input_normalized: dict[str, Any], query_text: str | None = None) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []

    def add(display_name: str, *, entity_type: str = "subject") -> None:
        value = (display_name or "").strip()
        if not value:
            return
        entities.append(
            {
                "entity_type": entity_type,
                "entity_key": value.lower(),
                "display_name": value,
                "metadata": {},
            }
        )

    if query_text:
        add(query_text[:80], entity_type="query")

    name = input_normalized.get("name")
    if isinstance(name, str):
        add(name)

    for key in ("inner", "outer", "subject"):
        nested = input_normalized.get(key)
        if isinstance(nested, dict):
            nested_name = nested.get("name")
            if isinstance(nested_name, str):
                add(nested_name)

    return entities


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


def _section_map_from_export(export_snapshot: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(export_snapshot, dict):
        return {}
    sections = export_snapshot.get("sections")
    if not isinstance(sections, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for section in sections:
        if isinstance(section, dict) and isinstance(section.get("title"), str):
            result[section["title"]] = section
    return result


def _section_body(export_snapshot: dict[str, Any] | None, title: str, default: str = "无") -> str:
    section = _section_map_from_export(export_snapshot).get(title)
    if not section:
        return default
    body = section.get("body")
    if isinstance(body, str) and body.strip():
        return body.strip()
    content = section.get("content")
    if isinstance(content, str) and content.strip():
        content_lines = [line for line in content.splitlines() if not line.startswith("[")]
        text = "\n".join(content_lines).strip()
        if text:
            return text
    return default


def _render_snapshot_text(sections: list[tuple[str, str]]) -> str:
    blocks: list[str] = []
    for title, body in sections:
        clean_body = (body or "").strip() or "无"
        blocks.append(f"[{title}]\n{clean_body}".strip())
    return "\n\n".join(blocks).strip()


def _build_export_provenance(technique: str, snapshot_text: str | None) -> dict[str, Any]:
    technique_info = get_technique_info(technique)
    registry = build_export_registry(technique=technique)
    return {
        "source_domain": "xingque_ai_export",
        "technique": technique,
        "category": technique_info.get("label"),
        "snapshot_key": technique_info.get("snapshot_key"),
        "bundle_version": registry.get("settings_version"),
        "section_migration_version": registry.get("section_migration_version"),
        "upstream_source_marker": "aiExport.js",
        "build_timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "snapshot_text_present": bool(snapshot_text),
    }


def _render_qimen_palace_sections(qimen_pan: dict[str, Any]) -> list[tuple[str, str]]:
    palace_map = {
        8: "正北坎宫",
        7: "东北艮宫",
        4: "正东震宫",
        1: "东南巽宫",
        2: "正南离宫",
        3: "西南坤宫",
        6: "正西兑宫",
        9: "西北乾宫",
    }
    cells = qimen_pan.get("cells")
    if not isinstance(cells, list):
        return [(title, "无") for title in palace_map.values()]

    by_num = {
        cell.get("palaceNum"): cell
        for cell in cells
        if isinstance(cell, dict) and cell.get("palaceNum") in palace_map
    }
    sections: list[tuple[str, str]] = []
    for palace_num, title in palace_map.items():
        cell = by_num.get(palace_num, {})
        body = "\n".join(
            [
                f"宫数：{palace_num}",
                f"天盘干：{cell.get('tianGan', '—')}",
                f"地盘干：{cell.get('diGan', '—')}",
                f"八神：{cell.get('god', '—')}",
                f"九星：{cell.get('tianXing', '—')}",
                f"八门：{cell.get('door', '—')}",
            ]
        )
        sections.append((title, body))
    return sections


def _build_guolao_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    chart = response.get("chart", {})
    houses = chart.get("houses") if isinstance(chart, dict) else []
    objects = chart.get("objects") if isinstance(chart, dict) else []
    zi_gods = (
        response.get("nongli", {})
        .get("bazi", {})
        .get("guolaoGods", {})
        .get("ziGods", {})
        if isinstance(response.get("nongli"), dict)
        else {}
    )

    house_lines: list[str] = []
    for index, house in enumerate(houses or [], start=1):
        house_id = house.get("id", f"House{index}") if isinstance(house, dict) else f"House{index}"
        house_lines.append(f"宫位：{house_id}")
        in_house = [obj for obj in (objects or []) if isinstance(obj, dict) and obj.get("house") == house_id]
        if not in_house:
            house_lines.append("星曜：无")
        else:
            for obj in in_house:
                house_lines.append(f"星曜：{obj.get('id', '—')} {obj.get('su28', '')}".strip())
        house_lines.append("")
    gods_lines: list[str] = []
    if isinstance(zi_gods, dict) and zi_gods:
        for branch, info in zi_gods.items():
            if not isinstance(info, dict):
                continue
            gods_lines.append(
                f"{branch}：神煞={'、'.join(info.get('allGods', []) or []) or '无'}；太岁神={'、'.join(info.get('taisuiGods', []) or []) or '无'}"
            )
    return _render_snapshot_text(
        [
            (
                "起盘信息",
                "\n".join(
                    [
                        f"日期：{payload.get('date', '—')} {payload.get('time', '—')}",
                        f"时区：{payload.get('zone', '—')}",
                        f"经纬度：{payload.get('lon', '—')} {payload.get('lat', '—')}",
                    ]
                ),
            ),
            ("七政四余宫位与二十八宿星曜", "\n".join(house_lines).strip() or "无"),
            ("神煞", "\n".join(gods_lines).strip() or "无"),
        ]
    )


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


ASTRO_TEXT_MAP: dict[str, str] = {
    "Aries": "牡羊",
    "Taurus": "金牛",
    "Gemini": "双子",
    "Cancer": "巨蟹",
    "Leo": "狮子",
    "Virgo": "室女",
    "Libra": "天秤",
    "Scorpio": "天蝎",
    "Sagittarius": "射手",
    "Capricorn": "摩羯",
    "Aquarius": "宝瓶",
    "Pisces": "双鱼",
    "Sun": "太阳",
    "Moon": "月亮",
    "Mercury": "水星",
    "Venus": "金星",
    "Mars": "火星",
    "Jupiter": "木星",
    "Saturn": "土星",
    "Uranus": "天王星",
    "Neptune": "海王星",
    "Pluto": "冥王星",
    "North Node": "北交",
    "South Node": "南交",
    "Dark Moon": "暗月",
    "Purple Clouds": "紫气",
    "Pars Fortuna": "福点",
    "Chiron": "凯龙",
    "Syzygy": "月亮朔望点",
    "Intp_Apog": "月亮平均远地点",
    "Intp_Perg": "月亮平均近地点",
    "Pholus": "人龙星",
    "Ceres": "谷神星",
    "Pallas": "智神星",
    "Juno": "婚神星",
    "Vesta": "灶神星",
    "MoonSun": "日月中点",
    "SaturnMars": "火土中点",
    "JupiterVenus": "金木中点",
    "LifeMasterDeg74": "七政命度点",
    "Asc": "上升",
    "Desc": "下降",
    "MC": "中天",
    "IC": "天底",
    "Pars Spirit": "灵点",
    "Pars Faith": "信心点",
    "Pars Substance": "占有点",
    "Pars Wedding [Male]": "婚姻点（男性）",
    "Pars Wedding [Female]": "婚姻点（女性）",
    "Pars Sons": "子嗣点",
    "Pars Father": "父权点",
    "Pars Mother": "母爱点",
    "Pars Brothers": "友情点",
    "Pars Diseases": "灾厄点",
    "Pars Death": "死亡点",
    "Pars Travel": "旅行点",
    "Pars Friends": "朋友点",
    "Pars Enemies": "宿敌点",
    "Pars Saturn": "罪点",
    "Pars Jupiter": "赢点",
    "Pars Mars": "勇点",
    "Pars Venus": "爱点",
    "Pars Mercury": "弱点",
    "Pars Horsemanship": "驾驭点",
    "Pars Life": "生命点",
    "Pars Radix": "光耀点",
    "Whole Sign": "整宫制",
    "Tropical": "回归黄道",
    "Sidereal": "恒星黄道，岁差:Lahiri",
    "ruler": "本垣",
    "exalt": "擢升",
    "dayTrip": "日三分",
    "nightTrip": "夜三分",
    "partTrip": "共管三分",
    "term": "界",
    "face": "十度",
    "exile": "陷",
    "fall": "落",
    "Hayyiz": "得时得地",
    "DemiHayyiz": "得时不得地",
    "InWrongPos": "失时",
    "Cazimi": "日熔",
    "Combust": "灼伤",
    "Sunbeams": "日光蔽匿",
    "House1": "第一宫",
    "House2": "第二宫",
    "House3": "第三宫",
    "House4": "第四宫",
    "House5": "第五宫",
    "House6": "第六宫",
    "House7": "第七宫",
    "House8": "第八宫",
    "House9": "第九宫",
    "House10": "第十宫",
    "House11": "第十一宫",
    "House12": "第十二宫",
    "First Quarter": "第一象限",
    "Second Quarter": "第二象限",
    "Third Quarter": "第三象限",
    "Last Quarter": "第四象限",
}

ASTRO_SHORT_TEXT_MAP: dict[str, str] = {
    "Sun": "日",
    "Moon": "月",
    "Mercury": "水",
    "Venus": "金",
    "Mars": "火",
    "Jupiter": "木",
    "Saturn": "土",
    "Uranus": "天",
    "Neptune": "海",
    "Pluto": "冥",
    "North Node": "北交",
    "South Node": "南交",
    "Dark Moon": "暗月",
    "Purple Clouds": "紫气",
    "Pars Fortuna": "福点",
    "Chiron": "凯龙",
    "Syzygy": "月亮朔望点",
    "Intp_Apog": "月亮平均远地点",
    "Intp_Perg": "月亮平均近地点",
    "Pholus": "人龙星",
    "Ceres": "谷神星",
    "Pallas": "智神星",
    "Juno": "婚神星",
    "Vesta": "灶神星",
    "MoonSun": "日月中点",
    "SaturnMars": "火土中点",
    "JupiterVenus": "金木中点",
    "LifeMasterDeg74": "七政命度点",
}

ASTRO_EGYPTIAN_TERMS: dict[str, list[tuple[str, int, int]]] = {
    "Aries": [("Jupiter", 0, 6), ("Venus", 6, 12), ("Mercury", 12, 20), ("Mars", 20, 25), ("Saturn", 25, 30)],
    "Taurus": [("Venus", 0, 8), ("Mercury", 8, 14), ("Jupiter", 14, 22), ("Saturn", 22, 27), ("Mars", 27, 30)],
    "Gemini": [("Mercury", 0, 6), ("Jupiter", 6, 12), ("Venus", 12, 17), ("Mars", 17, 24), ("Saturn", 24, 30)],
    "Cancer": [("Mars", 0, 7), ("Venus", 7, 13), ("Mercury", 13, 19), ("Jupiter", 19, 26), ("Saturn", 26, 30)],
    "Leo": [("Jupiter", 0, 6), ("Venus", 6, 11), ("Saturn", 11, 18), ("Mercury", 18, 24), ("Mars", 24, 30)],
    "Virgo": [("Mercury", 0, 7), ("Venus", 7, 17), ("Jupiter", 17, 21), ("Mars", 21, 28), ("Saturn", 28, 30)],
    "Libra": [("Saturn", 0, 6), ("Mercury", 6, 14), ("Jupiter", 14, 21), ("Venus", 21, 28), ("Mars", 28, 30)],
    "Scorpio": [("Mars", 0, 7), ("Venus", 7, 11), ("Mercury", 11, 19), ("Jupiter", 19, 24), ("Saturn", 24, 30)],
    "Sagittarius": [("Jupiter", 0, 12), ("Venus", 12, 17), ("Mercury", 17, 21), ("Saturn", 21, 26), ("Mars", 26, 30)],
    "Capricorn": [("Mercury", 0, 7), ("Jupiter", 7, 14), ("Venus", 14, 22), ("Saturn", 22, 26), ("Mars", 26, 30)],
    "Aquarius": [("Mercury", 0, 7), ("Venus", 7, 13), ("Jupiter", 13, 20), ("Mars", 20, 25), ("Saturn", 25, 30)],
    "Pisces": [("Venus", 0, 12), ("Jupiter", 12, 16), ("Mercury", 16, 19), ("Mars", 19, 28), ("Saturn", 28, 30)],
}

ASTRO_OBJECT_ORDER: list[str] = [
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
    "Uranus", "Neptune", "Pluto", "North Node", "South Node", "Dark Moon",
    "Purple Clouds", "Syzygy", "Pars Fortuna", "Intp_Apog", "Intp_Perg",
    "Chiron", "Pholus", "Ceres", "Pallas", "Juno", "Vesta", "LifeMasterDeg74",
]

ASTRO_LOT_ORDER: list[str] = [
    "Pars Spirit", "Pars Mercury", "Pars Venus", "Pars Mars", "Pars Jupiter", "Pars Saturn",
    "Pars Faith", "Pars Substance", "Pars Wedding [Female]", "Pars Wedding [Male]", "Pars Sons",
    "Pars Mother", "Pars Father", "Pars Brothers", "Pars Friends", "Pars Enemies", "Pars Diseases",
    "Pars Death", "Pars Travel", "Pars Horsemanship", "Pars Life", "Pars Radix",
]

ASTRO_POINT_ORDER: list[str] = [
    *ASTRO_OBJECT_ORDER, "Asc", "Desc", "MC", "IC", *ASTRO_LOT_ORDER, "MoonSun", "SaturnMars", "JupiterVenus",
]

ASTRO_HOUSE_SYSTEM_TEXT: dict[str, str] = {
    "0": "整宫制",
    "1": "Alcabitus",
    "2": "Regiomontanus",
    "3": "Placidus",
    "4": "Koch",
    "5": "Vehlow Equal",
    "6": "Polich Page",
    "7": "Sripati",
    "8": "天顶为10宫中点等宫制",
}

PLANET_HOUSE_INFO_NOTE = "说明：行星名后括号中的 nR 为宫主宫位标记；逆行会明确写为“逆行”。"


def _planet_label(value: Any) -> str:
    return _msg(value) or "无"


def _astro_msg(value: Any, *, short: bool = False) -> str:
    text = f"{value or ''}".strip()
    if not text:
        return ""
    if short and text in ASTRO_SHORT_TEXT_MAP:
        return ASTRO_SHORT_TEXT_MAP[text]
    return ASTRO_TEXT_MAP.get(text, text)


def _round3(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    return f"{round(number, 3):g}"


def _parse_house_num(house_id: Any) -> int | None:
    text = _msg(house_id)
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return None
    try:
        number = int(digits)
    except ValueError:
        return None
    return number if number > 0 else None


def _uniq_sorted(values: list[int | None]) -> list[int]:
    output = sorted({value for value in values if isinstance(value, int) and value > 0})
    return output


def _get_chart_object(chart_wrap: dict[str, Any], object_id: str) -> dict[str, Any] | None:
    chart = chart_wrap.get("chart", {}) if isinstance(chart_wrap, dict) else {}
    for obj in chart.get("objects", []) or []:
        if isinstance(obj, dict) and obj.get("id") == object_id:
            return obj
    for obj in chart_wrap.get("lots", []) or []:
        if isinstance(obj, dict) and obj.get("id") == object_id:
            return obj
    return None


def _get_objects_map(chart_wrap: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    chart = chart_wrap.get("chart", {}) if isinstance(chart_wrap, dict) else {}
    for obj in chart.get("objects", []) or []:
        if isinstance(obj, dict) and obj.get("id"):
            mapping[obj["id"]] = obj
    for obj in chart_wrap.get("lots", []) or []:
        if isinstance(obj, dict) and obj.get("id"):
            mapping[obj["id"]] = obj
    return mapping


def _get_stars_map(chart_wrap: dict[str, Any]) -> dict[str, list[Any]]:
    mapping: dict[str, list[Any]] = {}
    chart = chart_wrap.get("chart", {}) if isinstance(chart_wrap, dict) else {}
    for item in chart.get("stars", []) or []:
        if isinstance(item, dict) and item.get("id"):
            mapping[item["id"]] = item.get("stars", []) or []
    return mapping


def _format_planet_house_info(obj: dict[str, Any] | None) -> str:
    if not isinstance(obj, dict):
        return ""
    house_num = _parse_house_num(obj.get("house"))
    rule_nums = _uniq_sorted([_parse_house_num(value) for value in obj.get("ruleHouses", []) or []])
    parts = [f"{house_num}th" if house_num else "-"]
    parts.append("".join(f"{number}R" for number in rule_nums) if rule_nums else "-")
    return "; ".join(parts)


def _append_planet_house_info(label: str, chart_wrap: dict[str, Any], object_id: str) -> str:
    obj = _get_chart_object(chart_wrap, object_id)
    info = _format_planet_house_info(obj)
    return f"{label} ({info})" if info else label


def _normalize_ai_planet_label(text: str) -> str:
    return text.replace("R (宫主)", "R")


def _astro_msg_with_house(object_id: str, chart_wrap: dict[str, Any], *, short: bool = False) -> str:
    label = _astro_msg(object_id, short=short)
    return _normalize_ai_planet_label(_append_planet_house_info(label, chart_wrap, object_id))


def _which_term(sign: str, degree: int) -> str:
    for ruler, start, end in ASTRO_EGYPTIAN_TERMS.get(sign, []):
        if start <= degree < end:
            return _astro_msg(ruler, short=True)
    return ""


def _format_sign_degree(sign: Any, signlon: Any) -> str:
    if sign is None or signlon is None:
        return ""
    degree, minute = _split_degree(signlon)
    deg = abs(degree)
    minute = abs(minute)
    term = _which_term(_msg(sign), deg)
    term_text = f"；位于 {term} 界" if term else ""
    return f"{deg}˚{_astro_msg(sign)}{minute}分{term_text}"


def _format_retrograde_text(obj: dict[str, Any] | None) -> str:
    if not isinstance(obj, dict):
        return ""
    try:
        speed = float(obj.get("lonspeed"))
    except (TypeError, ValueError):
        return ""
    return "；逆行" if speed < 0 else ""


def _lon_to_sign_degree(lon: Any) -> str:
    try:
        value = float(lon) % 360
    except (TypeError, ValueError):
        return ""
    if value < 0:
        value += 360
    sign_index = int(value // 30) % 12
    sign = [
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
    ][sign_index]
    return _format_sign_degree(sign, value - sign_index * 30)


def _as_name_list(values: list[Any], *, short: bool = False) -> str:
    return " , ".join(_astro_msg(value, short=short) for value in values if _msg(value))


def _dignity_text(values: list[Any] | None) -> str:
    if not values:
        return "游走"
    return "，".join(_astro_msg(value) for value in values if _msg(value))


def _format_speed(obj: dict[str, Any] | None) -> str:
    if not isinstance(obj, dict):
        return ""
    try:
        current = float(obj.get("lonspeed"))
    except (TypeError, ValueError):
        return ""
    try:
        mean = float(obj.get("meanSpeed"))
    except (TypeError, ValueError):
        mean = 0.0
    text = f"{_round3(current)}度"
    if current < 0:
        text += "；逆行"
    delta = abs(current - mean)
    if delta > 1:
        text += "; 快速" if current > mean else "; 慢速"
    elif 0 < current < 0.003:
        text += "; 停滞"
    else:
        text += "; 平均"
    return text


def _ruleship_text(values: list[Any] | None) -> str:
    if not values:
        return ""
    return "+".join(_astro_msg(value) for value in values if _msg(value))


def _aspect_text(value: Any) -> str:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return _msg(value)
    return f"{number}˚"


def _format_star_lines(stars: list[Any] | None) -> list[str]:
    lines: list[str] = []
    for item in stars or []:
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            continue
        sign = item[1]
        signlon = item[2]
        star_name = item[4] if len(item) > 4 else item[0]
        degree, minute = _split_degree(signlon)
        lines.append(f"{_astro_msg(star_name)}：{abs(degree)}˚{_astro_msg(sign)}{abs(minute)}分")
    return lines


def _build_base_info_lines(chart_wrap: dict[str, Any], fields: dict[str, Any]) -> list[str]:
    chart = chart_wrap.get("chart", {}) if isinstance(chart_wrap, dict) else {}
    params = chart_wrap.get("params", {}) if isinstance(chart_wrap, dict) else {}
    lines: list[str] = []
    lon = fields.get("lon") or params.get("lon") or ""
    lat = fields.get("lat") or params.get("lat") or ""
    zone = params.get("zone", fields.get("zone"))
    if lon or lat:
        lines.append(f"经度：{lon}， 纬度：{lat}")
    birth = params.get("birth")
    if birth:
        dayofweek = _msg(chart.get("dayofweek"))
        lines.append(f"{birth}{(' ' + dayofweek) if dayofweek else ''}")
    if zone is not None:
        lines.append(f"时区：{zone} ，{'日生盘' if chart.get('isDiurnal') else '夜生盘'}")
    nongli = chart.get("nongli", {})
    if isinstance(nongli, dict) and nongli.get("birth"):
        lines.append(f"真太阳时：{nongli['birth']}")
    zodiacal = chart.get("zodiacal") or ASTRO_HOUSE_SYSTEM_TEXT.get(str(fields.get("zodiacal")), fields.get("zodiacal"))
    hsys = chart.get("hsys") or ASTRO_HOUSE_SYSTEM_TEXT.get(str(fields.get("hsys")), fields.get("hsys"))
    zodiacal_text = _astro_msg(zodiacal)
    hsys_text = _astro_msg(hsys)
    if zodiacal_text or hsys_text:
        lines.append(f"{zodiacal_text}，{hsys_text}")
    lines.append(PLANET_HOUSE_INFO_NOTE)
    if chart.get("dayerStar"):
        lines.append(f"日主星：{_astro_msg(chart['dayerStar'], short=True)}")
    if chart.get("timerStar"):
        lines.append(f"时主星：{_astro_msg(chart['timerStar'], short=True)}")
    return lines


def _build_house_cusp_lines(chart_wrap: dict[str, Any]) -> list[str]:
    chart = chart_wrap.get("chart", {}) if isinstance(chart_wrap, dict) else {}
    lines: list[str] = []
    for house in chart.get("houses", []) or []:
        if not isinstance(house, dict) or house.get("lon") is None:
            continue
        lines.append(f"{_astro_msg(house.get('id'))} 宫头：{_lon_to_sign_degree(house.get('lon'))}")
    return lines


def _build_star_and_lot_position_lines(chart_wrap: dict[str, Any]) -> list[str]:
    object_map = _get_objects_map(chart_wrap)
    lines: list[str] = []

    def push_one(object_id: str) -> None:
        obj = object_map.get(object_id)
        if not isinstance(obj, dict) or obj.get("sign") is None or obj.get("signlon") is None:
            return
        lines.append(
            f"{_astro_msg_with_house(object_id, chart_wrap, short=True)}："
            f"{_format_sign_degree(obj.get('sign'), obj.get('signlon'))}"
            f"{_format_retrograde_text(obj)}"
        )

    for object_id in ASTRO_OBJECT_ORDER:
        push_one(object_id)
    for object_id in ASTRO_LOT_ORDER:
        push_one(object_id)
    return lines


def _keep_reception_line(item: dict[str, Any] | None, *, abnormal: bool = False) -> bool:
    if not isinstance(item, dict):
        return False
    supplier = item.get("supplierRulerShip") or []
    supplier_ok = any(value in {"ruler", "exalt"} for value in supplier)
    if not abnormal:
        return True if not supplier else supplier_ok or True
    beneficiary = item.get("beneficiaryDignity") or []
    beneficiary_ok = any(value in {"ruler", "exalt"} for value in beneficiary)
    return True if not supplier and not beneficiary else supplier_ok or beneficiary_ok or True


def _build_info_section(chart_wrap: dict[str, Any], fields: dict[str, Any]) -> list[str]:
    chart = chart_wrap.get("chart", {}) if isinstance(chart_wrap, dict) else {}
    chart_data = chart_wrap if isinstance(chart_wrap, dict) else {}
    lines = _build_base_info_lines(chart_wrap, fields)

    anti = chart.get("antiscias", {}) if isinstance(chart, dict) else {}
    anti_lines: list[str] = []
    for item in anti.get("antiscia", []) or []:
        if isinstance(item, (list, tuple)) and len(item) >= 3:
            anti_lines.append(f"{_astro_msg(item[0], short=True)} 与 {_astro_msg(item[1], short=True)} 成映点 误差{_round3(item[2])}")
    for item in anti.get("cantiscia", []) or []:
        if isinstance(item, (list, tuple)) and len(item) >= 3:
            anti_lines.append(f"{_astro_msg(item[0], short=True)} 与 {_astro_msg(item[1], short=True)} 成反映点 误差{_round3(item[2])}")
    if anti_lines:
        lines.append("映点/反映点")
        lines.extend(anti_lines)

    receptions = chart_data.get("receptions", {}) if isinstance(chart_data, dict) else {}
    normal_receptions = [item for item in receptions.get("normal", []) or [] if _keep_reception_line(item)]
    abnormal_receptions = [item for item in receptions.get("abnormal", []) or [] if _keep_reception_line(item, abnormal=True)]
    if normal_receptions or abnormal_receptions:
        lines.append("接纳")
        lines.append("正接纳：")
        for item in normal_receptions:
            lines.append(
                f"{_astro_msg_with_house(item.get('beneficiary'), chart_wrap, short=True)} 被 "
                f"{_astro_msg_with_house(item.get('supplier'), chart_wrap, short=True)} 接纳 "
                f"({_ruleship_text(item.get('supplierRulerShip'))})"
            )
        lines.append("邪接纳：")
        for item in abnormal_receptions:
            lines.append(
                f"{_astro_msg_with_house(item.get('beneficiary'), chart_wrap, short=True)} "
                f"({_ruleship_text(item.get('beneficiaryDignity'))}) 被 "
                f"{_astro_msg_with_house(item.get('supplier'), chart_wrap, short=True)} 接纳 "
                f"({_ruleship_text(item.get('supplierRulerShip'))})"
            )

    mutuals = chart_data.get("mutuals", {}) if isinstance(chart_data, dict) else {}
    normal_mutuals = mutuals.get("normal", []) or []
    abnormal_mutuals = mutuals.get("abnormal", []) or []
    if normal_mutuals or abnormal_mutuals:
        lines.append("互容")
        lines.append("正互容：")
        for item in normal_mutuals:
            if not isinstance(item, dict):
                continue
            a = item.get("planetA", {})
            b = item.get("planetB", {})
            lines.append(
                f"{_astro_msg_with_house(a.get('id'), chart_wrap, short=True)} "
                f"({_ruleship_text(a.get('rulerShip'))}) 与 "
                f"{_astro_msg_with_house(b.get('id'), chart_wrap, short=True)} "
                f"({_ruleship_text(b.get('rulerShip'))}) 互容"
            )
        lines.append("邪互容：")
        for item in abnormal_mutuals:
            if not isinstance(item, dict):
                continue
            a = item.get("planetA", {})
            b = item.get("planetB", {})
            lines.append(
                f"{_astro_msg_with_house(a.get('id'), chart_wrap, short=True)} "
                f"({_ruleship_text(a.get('rulerShip'))}) 与 "
                f"{_astro_msg_with_house(b.get('id'), chart_wrap, short=True)} "
                f"({_ruleship_text(b.get('rulerShip'))}) 互容"
            )

    surround = chart_data.get("surround", {}) if isinstance(chart_data, dict) else {}
    attack_lines: list[str] = []
    for key, planet in (surround.get("attacks", {}) or {}).items():
        if not isinstance(planet, dict):
            continue
        candidates: list[list[dict[str, Any]]] = []
        for candidate_key in ("MinDelta", "MarsSaturn", "SunMoon", "VenusJupiter"):
            candidate = planet.get(candidate_key)
            if isinstance(candidate, list) and len(candidate) == 2:
                candidates.append(candidate)
        for pair in candidates:
            attack_lines.append(
                f"{_astro_msg_with_house(key, chart_wrap, short=True)} 被 "
                f"{_astro_msg_with_house(pair[0].get('id'), chart_wrap, short=True)} "
                f"(通过{_aspect_text(pair[0].get('aspect'))}相位) 与 "
                f"{_astro_msg_with_house(pair[1].get('id'), chart_wrap, short=True)} "
                f"(通过{_aspect_text(pair[1].get('aspect'))}相位) 围攻"
            )
    if attack_lines:
        lines.append("光线围攻")
        lines.extend(attack_lines)

    house_lines: list[str] = []
    for key, pair in (surround.get("houses", {}) or {}).items():
        if isinstance(pair, list) and len(pair) == 2:
            house_lines.append(
                f"{_astro_msg_with_house(pair[0].get('id'), chart_wrap, short=True)} 与 "
                f"{_astro_msg_with_house(pair[1].get('id'), chart_wrap, short=True)} 夹 {_astro_msg(key)}"
            )
    if house_lines:
        lines.append("夹宫")
        lines.extend(house_lines)

    planet_lines: list[str] = []
    for key, pair in (surround.get("planets", {}) or {}).items():
        if key == "BySunMoon" and isinstance(pair, dict) and pair.get("id"):
            planet_lines.append(f"{_astro_msg_with_house('Moon', chart_wrap, short=True)} 与 {_astro_msg_with_house('Sun', chart_wrap, short=True)} 夹 {_astro_msg_with_house(pair['id'], chart_wrap, short=True)}")
            continue
        if isinstance(pair, dict) and isinstance(pair.get("SunMoon"), list) and len(pair["SunMoon"]) == 2:
            sun_moon = pair["SunMoon"]
            planet_lines.append(
                f"{_astro_msg_with_house(sun_moon[0].get('id'), chart_wrap, short=True)} 与 "
                f"{_astro_msg_with_house(sun_moon[1].get('id'), chart_wrap, short=True)} 夹 "
                f"{_astro_msg_with_house(key, chart_wrap, short=True)}"
            )
            continue
        if isinstance(pair, list) and len(pair) == 2:
            planet_lines.append(
                f"{_astro_msg_with_house(pair[0].get('id'), chart_wrap, short=True)} 与 "
                f"{_astro_msg_with_house(pair[1].get('id'), chart_wrap, short=True)} 夹 "
                f"{_astro_msg_with_house(key, chart_wrap, short=True)}"
            )
    if planet_lines:
        lines.append("夹星")
        lines.extend(planet_lines)

    decl_parallel = chart_data.get("declParallel", {}) if isinstance(chart_data, dict) else {}
    parallel_lines: list[str] = []
    for index, ids in enumerate(decl_parallel.get("parallel", []) or [], start=1):
        if isinstance(ids, list) and ids:
            parallel_lines.append(f"平行星体{index}：{_as_name_list(ids, short=True)}")
    for object_id, ids in (decl_parallel.get("contraParallel", {}) or {}).items():
        if isinstance(ids, list) and ids:
            parallel_lines.append(f"相对 {_astro_msg(object_id, short=True)} 星体：{_as_name_list(ids, short=True)}")
    if parallel_lines:
        lines.append("纬照")
        lines.extend(parallel_lines)
    return lines


def _build_aspect_section(chart_wrap: dict[str, Any]) -> list[str]:
    aspects = chart_wrap.get("aspects", {}) if isinstance(chart_wrap, dict) else {}
    normal = aspects.get("normalAsp", {}) if isinstance(aspects, dict) else {}
    immediate = aspects.get("immediateAsp", {}) if isinstance(aspects, dict) else {}
    sign_asp = aspects.get("signAsp", {}) if isinstance(aspects, dict) else {}
    lines = ["标准相位"]
    for object_id in ASTRO_POINT_ORDER:
        one = normal.get(object_id)
        if not isinstance(one, dict):
            continue
        lines.append(_astro_msg_with_house(object_id, chart_wrap, short=True))
        for key, state in (("Applicative", "入相"), ("Exact", "离相"), ("Separative", "离相"), ("None", "")):
            for asp in one.get(key, []) or []:
                if not isinstance(asp, dict):
                    continue
                suffix = f" {state}" if state else ""
                lines.append(
                    f"{_aspect_text(asp.get('asp'))} {_astro_msg_with_house(asp.get('id'), chart_wrap, short=True)}{suffix} 误差{_round3(asp.get('orb'))}".strip()
                )
    lines.append("立即相位")
    for object_id in ASTRO_OBJECT_ORDER:
        one = immediate.get(object_id)
        if not isinstance(one, list) or len(one) < 2:
            continue
        lines.append(
            f"{_astro_msg_with_house(object_id, chart_wrap, short=True)} "
            f"{_aspect_text(one[0].get('asp'))} {_astro_msg_with_house(one[0].get('id'), chart_wrap, short=True)} 离相 误差{_round3(one[0].get('orb'))}；"
            f"{_aspect_text(one[1].get('asp'))} {_astro_msg_with_house(one[1].get('id'), chart_wrap, short=True)} 入相 误差{_round3(one[1].get('orb'))}"
        )
    lines.append("星座相位")
    for object_id in ASTRO_OBJECT_ORDER:
        one = sign_asp.get(object_id)
        if not isinstance(one, list) or not one:
            continue
        lines.append(f"主体：{_astro_msg_with_house(object_id, chart_wrap, short=True)}")
        for asp in one:
            if isinstance(asp, dict):
                lines.append(f"与 {_astro_msg_with_house(asp.get('id'), chart_wrap, short=True)} 成 {_aspect_text(asp.get('asp'))} 相位")
    return lines


def _build_planet_section(chart_wrap: dict[str, Any]) -> list[str]:
    object_map = _get_objects_map(chart_wrap)
    stars_map = _get_stars_map(chart_wrap)
    orient_occident = chart_wrap.get("chart", {}).get("orientOccident", {}) if isinstance(chart_wrap, dict) else {}
    lines: list[str] = []
    for object_id in ASTRO_OBJECT_ORDER:
        obj = object_map.get(object_id)
        if not isinstance(obj, dict):
            continue
        lines.append(_astro_msg_with_house(object_id, chart_wrap, short=True))
        lines.append(f"落座：{_format_sign_degree(obj.get('sign'), obj.get('signlon'))}{_format_retrograde_text(obj)}")
        if obj.get("house"):
            lines.append(f"落宫：{_astro_msg(obj.get('house'))}")
        if isinstance(obj.get("antisciaPoint"), dict):
            lines.append(f"映点：{_format_sign_degree(obj['antisciaPoint'].get('sign'), obj['antisciaPoint'].get('signlon'))}")
        if isinstance(obj.get("cantisciaPoint"), dict):
            lines.append(f"反映点：{_format_sign_degree(obj['cantisciaPoint'].get('sign'), obj['cantisciaPoint'].get('signlon'))}")
        if obj.get("meanSpeed") is not None:
            lines.append(f"平均速度：{_round3(obj.get('meanSpeed'))}")
        if obj.get("lonspeed") is not None:
            lines.append(f"当前速度：{_format_speed(obj)}")
        dignity = _dignity_text(obj.get("selfDignity"))
        extras = []
        if _msg(obj.get("hayyiz")) and _msg(obj.get("hayyiz")) != "None":
            extras.append(_astro_msg(obj.get("hayyiz")))
        if obj.get("isVOC"):
            extras.append("空亡")
        if dignity != "游走" or extras:
            lines.append(f"禀赋：{dignity}{('，' + '，'.join(extras)) if extras else ''}")
        if obj.get("score") is not None:
            lines.append(f"分值：{obj.get('score')}")
        for key, label in (
            ("altitudeTrue", "真地平纬度"),
            ("altitudeAppa", "视地平纬度"),
            ("azimuth", "地坪经度"),
            ("lon", "黄经"),
            ("lat", "黄纬"),
            ("ra", "赤经"),
            ("decl", "赤纬"),
        ):
            if obj.get(key) is not None:
                lines.append(f"{label}：{_round3(obj.get(key))}˚")
        if obj.get("moonPhase") is not None:
            lines.append(f"月限：{_astro_msg(obj.get('moonPhase'))}")
        if obj.get("sunPos") is not None:
            lines.append(f"太阳关系：{_astro_msg(obj.get('sunPos'))}")
        if obj.get("ruleHouses"):
            lines.append(f"入垣宫：{_as_name_list(obj.get('ruleHouses'))}")
        if obj.get("exaltHouse"):
            lines.append(f"擢升宫：{_astro_msg(obj.get('exaltHouse'))}")
        if obj.get("governSign"):
            govern = _astro_msg(obj.get("governSign"))
            govern_planets = obj.get("governPlanets") or []
            if govern_planets:
                govern += f" , {_as_name_list(govern_planets, short=True)}"
            lines.append(f"宰制星座：{govern}")
        occ = orient_occident.get(object_id) if isinstance(orient_occident, dict) else None
        if isinstance(occ, dict):
            oriental = [item.get("id") for item in occ.get("oriental", []) or [] if isinstance(item, dict)]
            occidental = [item.get("id") for item in occ.get("occidental", []) or [] if isinstance(item, dict)]
            if oriental:
                lines.append(f"东出星：{_as_name_list(oriental, short=True)}")
            if occidental:
                lines.append(f"西入星：{_as_name_list(occidental, short=True)}")
        stars = stars_map.get(object_id) or []
        if stars:
            lines.append("汇合恒星：")
            lines.extend(_format_star_lines(stars))
    return lines


def _build_lots_section(chart_wrap: dict[str, Any]) -> list[str]:
    object_map = _get_objects_map(chart_wrap)
    stars_map = _get_stars_map(chart_wrap)
    lines: list[str] = []
    for object_id in ASTRO_LOT_ORDER:
        obj = object_map.get(object_id)
        if not isinstance(obj, dict):
            continue
        lines.append(_astro_msg_with_house(object_id, chart_wrap, short=False))
        lines.append(f"落座：{_format_sign_degree(obj.get('sign'), obj.get('signlon'))}{_format_retrograde_text(obj)}")
        if obj.get("house"):
            lines.append(f"落宫：{_astro_msg(obj.get('house'))}")
        stars = stars_map.get(object_id) or []
        if stars:
            lines.append("汇合恒星：")
            lines.extend(_format_star_lines(stars))
    return lines


def _build_possibility_section(chart_wrap: dict[str, Any]) -> list[str]:
    predict = chart_wrap.get("predict", {}) if isinstance(chart_wrap, dict) else {}
    planet_sign = predict.get("PlanetSign", {}) if isinstance(predict, dict) else {}
    lines: list[str] = []
    for key, items in planet_sign.items():
        lines.append(_astro_msg(key, short=True))
        for text in items or []:
            lines.append(_msg(text))
    return lines


def _build_astro_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    sections = [
        ("起盘信息", _build_base_info_lines(response, payload)),
        ("宫位宫头", _build_house_cusp_lines(response)),
        ("星与虚点", _build_star_and_lot_position_lines(response)),
        ("信息", _build_info_section(response, payload)),
        ("相位", _build_aspect_section(response)),
        ("行星", _build_planet_section(response)),
        ("希腊点", _build_lots_section(response)),
        ("可能性", _build_possibility_section(response)),
    ]
    return _render_snapshot_text([(title, "\n".join(lines).strip()) for title, lines in sections if lines])


def _is_astro_chart_payload(response_data: dict[str, Any]) -> bool:
    chart = response_data.get("chart")
    return isinstance(chart, dict) and isinstance(chart.get("objects"), list) and isinstance(chart.get("houses"), list)


def _export_body_data(body: str, data: Any) -> dict[str, Any]:
    return {"__export_body__": body, "__export_data__": data}


def _sanitize_section_data(value: Any, seen: set[int] | None = None) -> Any:
    if seen is None:
        seen = set()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    value_id = id(value)
    if value_id in seen:
        return "<circular>"
    if isinstance(value, list):
        seen.add(value_id)
        return [_sanitize_section_data(item, seen) for item in value]
    if isinstance(value, dict):
        seen.add(value_id)
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if key in {"export_snapshot", "export_format", "snapshot_text"}:
                continue
            cleaned[key] = _sanitize_section_data(item, seen)
        return cleaned
    return _msg(value)


def _normalize_gua_lines(lines: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in lines or []:
        if not isinstance(item, dict):
            continue
        value = 1 if bool(item.get("value")) else 0
        normalized.append(
            {
                "value": value,
                "change": bool(item.get("change")),
                "god": item.get("god"),
                "name": item.get("name"),
            }
        )
    return normalized[:6]


def _derive_gua_code(lines: list[dict[str, Any]]) -> str:
    return "".join(str(int(line.get("value", 0))) for line in lines) or "000000"


def _derive_changed_gua_code(lines: list[dict[str, Any]]) -> str:
    chars: list[str] = []
    for line in lines:
        value = int(line.get("value", 0))
        if line.get("change"):
            value = 1 - value
        chars.append(str(value))
    return "".join(chars) or "000000"


def _extract_gua_detail(raw: Any, code: str) -> dict[str, Any]:
    if isinstance(raw, dict):
        if isinstance(raw.get(code), dict):
            return raw[code]
        if isinstance(raw.get("data"), dict) and isinstance(raw["data"].get(code), dict):
            return raw["data"][code]
        if isinstance(raw.get("result"), dict) and isinstance(raw["result"].get(code), dict):
            return raw["result"][code]
    return {}


def _build_suzhan_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    chart = response.get("chart", {})
    houses = chart.get("houses") if isinstance(chart, dict) else []
    objects = chart.get("objects") if isinstance(chart, dict) else []
    house_lines: list[str] = []
    if isinstance(houses, list):
        for house in houses:
            if not isinstance(house, dict):
                continue
            house_id = house.get("id", "House")
            house_lines.append(f"宫位：{house_id}")
            in_house = [obj for obj in (objects or []) if isinstance(obj, dict) and obj.get("house") == house_id]
            if not in_house:
                house_lines.append("星曜：无")
                house_lines.append("")
                continue
            for obj in in_house:
                deg, minute = _split_degree(obj.get("signlon", obj.get("lon")))
                su28 = _msg(obj.get("su28"))
                su_text = f"{deg}˚{su28}{minute}分" if su28 else f"{deg}˚{minute}分"
                house_lines.append(f"星曜：{_planet_label(obj.get('id'))} {su_text}".strip())
            house_lines.append("")
    return _render_snapshot_text(
        [
            (
                "起盘信息",
                "\n".join(
                    [
                        f"日期：{payload.get('date', '—')} {payload.get('time', '—')}",
                        f"时区：{payload.get('zone', '—')}",
                        f"经纬度：{payload.get('lon', '—')} {payload.get('lat', '—')}",
                        f"外盘：{payload.get('szchart', 0)}",
                        f"盘型：{payload.get('szshape', 0)}",
                    ]
                ),
            ),
            ("宿盘宫位与二十八宿星曜", "\n".join(house_lines).strip() or "无"),
        ]
    )


def _build_germany_snapshot_text(payload: dict[str, Any], chart_response: dict[str, Any], germany_result: dict[str, Any]) -> str:
    chart = chart_response.get("chart", {}) if isinstance(chart_response, dict) else {}
    houses = chart.get("houses") if isinstance(chart, dict) else []
    objects = chart.get("objects") if isinstance(chart, dict) else []
    midpoints = germany_result.get("midpoints", []) if isinstance(germany_result, dict) else []
    aspects = germany_result.get("aspects", {}) if isinstance(germany_result, dict) else {}
    house_lines: list[str] = []
    for house in houses or []:
        if not isinstance(house, dict):
            continue
        house_lines.append(f"{house.get('id', 'House')}")
        in_house = [obj for obj in objects or [] if isinstance(obj, dict) and obj.get("house") == house.get("id")]
        if not in_house:
            house_lines.append("星体：无")
            continue
        for obj in in_house:
            deg, minute = _split_degree(obj.get("signlon", obj.get("lon")))
            sign = _msg(obj.get("sign"))
            house_lines.append(f"星体：{_planet_label(obj.get('id'))} {deg}˚{sign}{minute}分")
    midpoint_lines = []
    for item in midpoints or []:
        if not isinstance(item, dict):
            continue
        deg, minute = _split_degree(item.get("signlon"))
        midpoint_lines.append(f"{_planet_label(item.get('idA'))} | {_planet_label(item.get('idB'))} = {deg}˚{_msg(item.get('sign'))}{minute}分")
    aspect_lines = []
    if isinstance(aspects, dict):
        for key, arr in aspects.items():
            aspect_lines.append(f"主体：{_planet_label(key)}")
            if not arr:
                aspect_lines.append("无")
                continue
            for asp in arr:
                if not isinstance(asp, dict):
                    continue
                mid = asp.get("midpoint", {}) if isinstance(asp.get("midpoint"), dict) else {}
                id_a = mid.get("idA", asp.get("idA"))
                id_b = mid.get("idB", asp.get("idB"))
                aspect_lines.append(
                    f"与中点({_planet_label(id_a)} | {_planet_label(id_b)}) 成 {asp.get('aspect', '—')} 相位，误差{asp.get('delta', '—')}"
                )
            aspect_lines.append("")
    return _render_snapshot_text(
        [
            (
                "起盘信息",
                "\n".join(
                    [
                        f"日期：{payload.get('date', '—')} {payload.get('time', '—')}",
                        f"时区：{payload.get('zone', '—')}",
                        f"经纬度：{payload.get('lon', '—')} {payload.get('lat', '—')}",
                    ]
                ),
            ),
            ("宫位宫头", "\n".join(house_lines).strip() or "无"),
            ("中点", "\n".join(midpoint_lines).strip() or "暂无中点数据"),
            ("中点相位", "\n".join(aspect_lines).strip() or "暂无中点相位数据"),
        ]
    )


def _build_otherbu_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    def chart_lines(chart_obj: dict[str, Any] | None) -> list[str]:
        chart = chart_obj.get("chart", {}) if isinstance(chart_obj, dict) else {}
        houses = chart.get("houses") if isinstance(chart, dict) else []
        objects = chart.get("objects") if isinstance(chart, dict) else []
        lines: list[str] = []
        for house in houses or []:
            if not isinstance(house, dict):
                continue
            lines.append(f"{house.get('id', 'House')}")
            in_house = [obj for obj in objects or [] if isinstance(obj, dict) and obj.get("house") == house.get("id")]
            if not in_house:
                lines.append("星体：无")
                continue
            for obj in in_house:
                deg, minute = _split_degree(obj.get("signlon", obj.get("lon")))
                lines.append(f"星体：{_planet_label(obj.get('id'))} {deg}˚{_msg(obj.get('sign'))}{minute}分")
        return lines

    return _render_snapshot_text(
        [
            (
                "起盘信息",
                "\n".join(
                    [
                        f"日期：{payload.get('date', '—')} {payload.get('time', '—')}",
                        f"时区：{payload.get('zone', '—')}",
                        f"经纬度：{payload.get('lon', '—')} {payload.get('lat', '—')}",
                        f"传统模式：{'无三王星' if payload.get('tradition') else '含三王星'}",
                        f"问题：{payload.get('question') or '未填写'}",
                    ]
                ),
            ),
            (
                "骰子结果",
                "\n".join(
                    [
                        f"行星：{_planet_label(response.get('planet'))}",
                        f"星座：{_msg(response.get('sign')) or '无'}",
                        f"宫位：House{int(response.get('house', 0)) + 1 if response.get('house') is not None else '无'}",
                    ]
                ),
            ),
            ("骰子盘宫位与星体", "\n".join(chart_lines(response.get("diceChart"))).strip() or "无"),
            ("天象盘宫位与星体", "\n".join(chart_lines(response.get("chart"))).strip() or "无"),
        ]
    )


def _build_firdaria_snapshot_text(response: dict[str, Any]) -> str:
    chart = response.get("chart", {}) if isinstance(response, dict) else {}
    params = response.get("params", {}) if isinstance(response, dict) else {}
    predictives = response.get("predictives", {}) if isinstance(response, dict) else {}
    firdaria = predictives.get("firdaria", []) if isinstance(predictives, dict) else []
    birth_text = params.get("birth") or f"{params.get('date', '—')} {params.get('time', '—')}"
    true_solar = chart.get("nongli", {}).get("birth", "无") if isinstance(chart, dict) else "无"
    lines = [
        ("出生时间", "\n".join([f"出生时间：{birth_text}", f"真太阳时：{true_solar}"]).strip()),
        (
            "星盘信息",
            "\n".join(
                [
                    f"经纬度：{params.get('lon', '—')} {params.get('lat', '—')}",
                    f"时区：{params.get('zone', '—')}",
                    f"盘型：{'日生盘' if chart.get('isDiurnal') else '夜生盘'}" if isinstance(chart, dict) and chart.get("isDiurnal") is not None else "盘型：无",
                ]
            ),
        ),
    ]
    table_lines = ["| 主限 | 子限 | 日期 |", "| --- | --- | --- |"]
    row_count = 0
    for main in firdaria or []:
        if not isinstance(main, dict):
            continue
        main_direct = _planet_label(main.get("mainDirect"))
        subs = main.get("subDirect") if isinstance(main.get("subDirect"), list) else []
        if not subs:
            table_lines.append(f"| {main_direct} | 无 | 无 |")
            row_count += 1
            continue
        for sub in subs:
            if not isinstance(sub, dict):
                continue
            table_lines.append(f"| {main_direct} | {_planet_label(sub.get('subDirect'))} | {sub.get('date', '无')} |")
            row_count += 1
    if row_count == 0:
        table_lines.append("| 无 | 无 | 无 |")
    lines.append(("法达星限表格", "\n".join(table_lines)))
    return _render_snapshot_text(lines)


def _build_decennials_snapshot_text(response: dict[str, Any], settings: dict[str, Any], ai_state: dict[str, Any]) -> str:
    chart = response.get("chart", {}) if isinstance(response, dict) else {}
    params = response.get("params", {}) if isinstance(response, dict) else {}
    timeline = response.get("timeline", {}) if isinstance(response, dict) else {}
    list_data = timeline.get("list", []) if isinstance(timeline, dict) else []
    resolved = timeline.get("resolvedStartPlanet", "Sun")
    birth_text = params.get("birth") or f"{params.get('date', '—')} {params.get('time', '—')}"
    true_solar = chart.get("nongli", {}).get("birth", "无") if isinstance(chart, dict) else "无"
    order_label = "迦勒底星序" if settings.get("orderType") == DECENNIAL_ORDER_CHALDEAN else "实际黄道次序"
    day_label = "Hephaistio（原表日数）" if settings.get("dayMethod") == DECENNIAL_DAY_METHOD_HEPHAISTIO else "Valens（精确）"
    cal_label = "365.25天/年（按回归年换算）" if settings.get("calendarType") == DECENNIAL_CALENDAR_ACTUAL else "360天/年（按30天/月换算）"
    start_label = f"得时光体（{resolved}）" if settings.get("startMode") == DECENNIAL_START_MODE_SECT_LIGHT else settings.get("startMode", resolved)

    def safe_idx(index: Any, length: int) -> int:
        if length <= 0:
            return 0
        try:
            number = int(index)
        except (TypeError, ValueError):
            return 0
        return max(0, min(number, length - 1))

    mode = ai_state.get("aiMode", "l1_all")
    l1_idx = safe_idx(ai_state.get("aiL1Idx", 0), len(list_data))
    l1 = list_data[l1_idx] if list_data else None
    l2_list = l1.get("sublevel", []) if isinstance(l1, dict) else []
    l2_idx = safe_idx(ai_state.get("aiL2Idx", 0), len(l2_list))
    l2 = l2_list[l2_idx] if l2_list else None
    l3_list = l2.get("sublevel", []) if isinstance(l2, dict) else []
    l3_idx = safe_idx(ai_state.get("aiL3Idx", 0), len(l3_list))
    l3 = l3_list[l3_idx] if l3_list else None

    def node_line(prefix: str, item: dict[str, Any], idx: int) -> str:
        return f"{prefix}-{idx + 1}：{item.get('planet', '无')}-{item.get('date', '无')}{'（名义：' + item.get('nominal', '') + '）' if item.get('nominal') else ''}{'-当前' if item.get('active') else ''}"

    output_lines: list[str] = [f"AI输出模式：{mode}"]
    if not list_data:
        output_lines.append("无推运数据")
    elif mode == "l1_all":
        output_lines.extend(node_line("L1", item, idx) for idx, item in enumerate(list_data))
    else:
        if l1:
            output_lines.append(node_line("L1", l1, l1_idx))
        if mode in {"l2_in_l1", "l3_in_l2", "l4_in_l3"}:
            if mode == "l2_in_l1":
                output_lines.extend(node_line("L2", item, idx) for idx, item in enumerate(l2_list)) if l2_list else output_lines.append("无L2数据")
            elif l2:
                output_lines.append(node_line("L2", l2, l2_idx))
        if mode in {"l3_in_l2", "l4_in_l3"}:
            if mode == "l3_in_l2":
                output_lines.extend(node_line("L3", item, idx) for idx, item in enumerate(l3_list)) if l3_list else output_lines.append("无L3数据")
            elif l3:
                output_lines.append(node_line("L3", l3, l3_idx))
        if mode == "l4_in_l3":
            l4_list = l3.get("sublevel", []) if isinstance(l3, dict) else []
            output_lines.extend(node_line("L4", item, idx) for idx, item in enumerate(l4_list)) if l4_list else output_lines.append("无L4数据")

    return _render_snapshot_text(
        [
            (
                "起盘信息",
                "\n".join(
                    [
                        f"出生时间：{birth_text}",
                        f"真太阳时：{true_solar}",
                        f"经纬度：{params.get('lon', '—')} {params.get('lat', '—')}",
                        f"时区：{params.get('zone', '—')}",
                    ]
                ),
            ),
            (
                "星盘信息",
                "\n".join(
                    [
                        f"黄道：{chart.get('zodiacal', params.get('zodiacal', 0)) if isinstance(chart, dict) else params.get('zodiacal', 0)}",
                        f"宫制：{params.get('hsys', 0)}",
                        f"盘型：{'日生盘' if chart.get('isDiurnal') else '夜生盘'}" if isinstance(chart, dict) and chart.get("isDiurnal") is not None else "盘型：无",
                    ]
                ),
            ),
            (
                "十年大运设置",
                "\n".join(
                    [
                        f"起运主星：{start_label}",
                        f"实际起运：{resolved}",
                        f"分配次序：{order_label}",
                        f"日限体系：{day_label}",
                        f"时间口径：{cal_label}",
                    ]
                ),
            ),
            (f"基于{resolved}起运", "\n".join(output_lines).strip() or "无"),
        ]
    )


def _build_sixyao_snapshot_text(payload: dict[str, Any], nongli: dict[str, Any], current_code: str, changed_code: str, lines: list[dict[str, Any]], descs: dict[str, Any]) -> str:
    question = payload.get("question")
    current_desc = _extract_gua_detail(descs, current_code)
    changed_desc = _extract_gua_detail(descs, changed_code)
    line_texts: list[str] = []
    for index, line in enumerate(lines, start=1):
        yao_type = "阳爻" if int(line.get("value", 0)) == 1 else "阴爻"
        moving = "（动）" if line.get("change") else "（静）"
        extras = []
        if line.get("god"):
            extras.append(f"六神:{line['god']}")
        if line.get("name"):
            extras.append(f"爻名:{line['name']}")
        suffix = f"，{'，'.join(extras)}" if extras else ""
        line_texts.append(f"第{index}爻：{yao_type}{moving}{suffix}")
    judge_lines = []
    if question:
        judge_lines.append(f"问题：{question}")
    judge_lines.append(f"本卦：{current_desc.get('name', current_code)}")
    if current_desc.get("卦辞"):
        judge_lines.append(f"卦辞：{current_desc['卦辞']}")
    judge_lines.append(f"之卦：{changed_desc.get('name', changed_code)}")
    if changed_desc.get("卦辞"):
        judge_lines.append(f"之卦卦辞：{changed_desc['卦辞']}")
    return _render_snapshot_text(
        [
            (
                "起盘信息",
                "\n".join(
                    [
                        f"日期：{payload.get('date', '—')} {payload.get('time', '—')}",
                        f"时区：{payload.get('zone', '—')}",
                        f"经纬度：{payload.get('lon', '—')} {payload.get('lat', '—')}",
                        f"起卦时间：{nongli.get('birth', '无')}",
                        f"干支：年{nongli.get('yearJieqi') or nongli.get('year') or nongli.get('yearGanZi') or '无'} 月{nongli.get('monthGanZi', '无')} 日{nongli.get('dayGanZi', '无')} 时{nongli.get('time', '无')}",
                    ]
                ),
            ),
            ("卦象", "\n".join([f"本卦：{current_desc.get('name', current_code)}", f"之卦：{changed_desc.get('name', changed_code)}"]).strip()),
            ("六爻与动爻", "\n".join(line_texts).strip() or "暂无爻线数据"),
            ("卦辞与断语", "\n".join(judge_lines).strip() or "无"),
        ]
    )


def _join_lines(lines: list[Any]) -> str:
    return "\n".join(text for text in (_msg(line) for line in lines) if text).strip()


def _relation_name(value: Any) -> str:
    mapping = {
        0: "比较盘",
        1: "组合盘",
        2: "影响盘",
        3: "时空中点盘",
        4: "马克斯盘",
        "0": "比较盘",
        "1": "组合盘",
        "2": "影响盘",
        "3": "时空中点盘",
        "4": "马克斯盘",
        "Comp": "比较盘",
        "Composite": "组合盘",
        "Synastry": "影响盘",
        "TimeSpace": "时空中点盘",
        "Marks": "马克斯盘",
    }
    return mapping.get(value, _msg(value) or "关系盘")


def _relative_aspect_lines(items: Any) -> list[str]:
    lines: list[str] = []
    for obj in items or []:
        if not isinstance(obj, dict):
            continue
        lines.append(f"主体：{_planet_label(obj.get('id') or obj.get('directId'))}")
        targets = obj.get("objects") or []
        if not isinstance(targets, list) or not targets:
            lines.append("无")
            continue
        for target in targets:
            if not isinstance(target, dict):
                continue
            lines.append(
                f"与 {_planet_label(target.get('id') or target.get('natalId'))} 成 {_aspect_text(target.get('aspect'))} 相位，误差{_round3(target.get('delta'))}"
            )
        lines.append("")
    return lines


def _relative_midpoint_lines(mapping: Any) -> list[str]:
    lines: list[str] = []
    if not isinstance(mapping, dict):
        return lines
    for key, items in mapping.items():
        lines.append(f"主体：{_planet_label(key)}")
        if not isinstance(items, list) or not items:
            lines.append("无")
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            midpoint = item.get("midpoint") if isinstance(item.get("midpoint"), dict) else {}
            lines.append(
                f"与中点({_planet_label(midpoint.get('idA'))} | {_planet_label(midpoint.get('idB'))}) 成 {_aspect_text(item.get('aspect'))} 相位，误差{_round3(item.get('delta'))}"
            )
        lines.append("")
    return lines


def _relative_antiscia_lines(items: Any, type_label: str) -> list[str]:
    lines: list[str] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"{_planet_label(item.get('idA'))} 与 {_planet_label(item.get('idB'))} 成{type_label}，误差{_round3(item.get('delta'))}"
        )
    return lines


def _build_relative_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    def embedded_chart_text(chart_payload: Any) -> str:
        if not isinstance(chart_payload, dict):
            return "无"
        chart_wrap = chart_payload
        if isinstance(chart_payload.get("chart"), dict):
            chart_wrap = chart_payload
        lines: list[str] = []
        base_lines = _build_base_info_lines(chart_wrap, {})
        if base_lines:
            lines.append("起盘信息：")
            lines.extend(base_lines)
            lines.append("")
        house_lines = _build_house_cusp_lines(chart_wrap)
        if house_lines:
            lines.append("宫位宫头：")
            lines.extend(house_lines)
            lines.append("")
        body_lines = _build_star_and_lot_position_lines(chart_wrap)
        if body_lines:
            lines.append("星与虚点：")
            lines.extend(body_lines[:24])
            lines.append("")
        info_lines = _build_info_section(chart_wrap, {})
        if info_lines:
            lines.append("信息：")
            lines.extend(info_lines[:18])
            lines.append("")
        aspect_lines = _build_aspect_section(chart_wrap)
        if aspect_lines:
            lines.append("相位：")
            lines.extend(aspect_lines[:18])
        return _join_lines(lines) or "无"

    lines: list[str] = ["[关系起盘信息]"]
    lines.append(f"盘型：{_relation_name(payload.get('relative'))}")
    inner = payload.get("inner") if isinstance(payload.get("inner"), dict) else {}
    outer = payload.get("outer") if isinstance(payload.get("outer"), dict) else {}
    if inner:
        lines.append(f"星盘A：{inner.get('name') or 'A'} {inner.get('date', '')} {inner.get('time', '')}".strip())
        lines.append(f"星盘A经纬度：{inner.get('lon', '—')} {inner.get('lat', '—')}")
    if outer:
        lines.append(f"星盘B：{outer.get('name') or 'B'} {outer.get('date', '')} {outer.get('time', '')}".strip())
        lines.append(f"星盘B经纬度：{outer.get('lon', '—')} {outer.get('lat', '—')}")
    lines.append(f"宫制：{payload.get('hsys', '—')}")
    lines.append(f"黄道：{payload.get('zodiacal', '—')}")

    sections = [
        ("A对B相位", _relative_aspect_lines(response.get("inToOutAsp"))),
        ("B对A相位", _relative_aspect_lines(response.get("outToInAsp"))),
        ("A对B中点相位", _relative_midpoint_lines(response.get("inToOutMidpoint"))),
        ("B对A中点相位", _relative_midpoint_lines(response.get("outToInMidpoint"))),
        ("A对B映点", _relative_antiscia_lines(response.get("inToOutAnti"), "映点")),
        ("A对B反映点", _relative_antiscia_lines(response.get("inToOutCAnti"), "反映点")),
        ("B对A映点", _relative_antiscia_lines(response.get("outToInAnti"), "映点")),
        ("B对A反映点", _relative_antiscia_lines(response.get("outToInCAnti"), "反映点")),
    ]

    rendered: list[tuple[str, str]] = [("关系起盘信息", _join_lines(lines[1:]))]
    for title, body_lines in sections:
        rendered.append((title, _join_lines(body_lines) or "无"))
    rendered.append(
        (
            "合成图盘",
            embedded_chart_text(response)
            if isinstance(response.get("chart"), dict) and isinstance(response["chart"].get("objects"), list)
            else "无",
        )
    )
    rendered.append(
        (
            "影响图盘-星盘A",
            embedded_chart_text(response["inner"])
            if isinstance(response.get("inner"), dict) and isinstance(response["inner"].get("chart"), dict)
            else "无",
        )
    )
    rendered.append(
        (
            "影响图盘-星盘B",
            embedded_chart_text(response["outer"])
            if isinstance(response.get("outer"), dict) and isinstance(response["outer"].get("chart"), dict)
            else "无",
        )
    )
    return _render_snapshot_text(rendered)


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


def _collect_god_names(node: Any) -> list[str]:
    if not isinstance(node, dict):
        return []
    values: list[str] = []
    for key in ("goodGods", "neutralGods", "badGods", "allGods", "taisuiGods"):
        for item in node.get(key) or []:
            text = _msg(item)
            if text:
                values.append(text)
    return values


def _build_bazi_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    bazi = response.get("bazi", response if isinstance(response, dict) else {})
    four = bazi.get("fourColumns", {}) if isinstance(bazi, dict) else {}
    nongli = bazi.get("nongli", {}) if isinstance(bazi, dict) else {}
    gender_map = {"-1": "未知", "0": "女", "1": "男"}
    time_alg_map = {"0": "真太阳时", "1": "直接时间", "2": "春分定卯时"}
    adjust_map = {"0": "不调整节气", "1": "节气按纬度调整"}

    def gz_gods(item: Any) -> str:
        if not isinstance(item, dict):
            return "无"
        stem = "、".join(_collect_god_names(item.get("stem"))) or "无"
        branch = "、".join(_collect_god_names(item.get("branch"))) or "无"
        whole = "、".join(_collect_god_names(item)) or "无"
        return f"整柱={whole}；天干={stem}；地支={branch}"

    base_lines = [
        f"日期：{payload.get('date', '—')} {payload.get('time', '—')}",
        f"时区：{payload.get('zone', '—')}",
        f"经纬度：{payload.get('lon', '—')} {payload.get('lat', '—')}",
        f"性别：{gender_map.get(str(payload.get('gender')), payload.get('gender', '未知'))}",
        f"时间算法：{time_alg_map.get(str(payload.get('timeAlg', 0)), payload.get('timeAlg', 0))}",
        f"节气修正：{adjust_map.get(str(payload.get('adjustJieqi', 0)), payload.get('adjustJieqi', 0))}",
        f"农历：{nongli.get('year', '')}年{'闰' if nongli.get('leap') else ''}{nongli.get('month', '')}{nongli.get('day', '')}".strip() or "农历：未知",
        f"真太阳时：{nongli.get('birth') or (str(payload.get('date', '')) + ' ' + str(payload.get('time', ''))).strip()}",
    ]
    four_lines = [
        f"年柱：{_gz_text(four.get('year'))}",
        f"月柱：{_gz_text(four.get('month'))}",
        f"日柱：{_gz_text(four.get('day'))}",
        f"时柱：{_gz_text(four.get('time'))}",
        f"胎元：{_gz_text(four.get('tai'))}",
        f"命宫：{_gz_text(four.get('ming'))}",
        f"身宫：{_gz_text(four.get('shen'))}",
    ]
    god_lines = [
        f"年柱：{gz_gods(four.get('year'))}",
        f"月柱：{gz_gods(four.get('month'))}",
        f"日柱：{gz_gods(four.get('day'))}",
        f"时柱：{gz_gods(four.get('time'))}",
        f"胎元：{gz_gods(four.get('tai'))}",
        f"命宫：{gz_gods(four.get('ming'))}",
        f"身宫：{gz_gods(four.get('shen'))}",
    ]
    direction_lines: list[str] = []
    for idx, item in enumerate(bazi.get("mainDirection") or [], start=1):
        if isinstance(item, dict):
            direction_lines.append(f"第{idx}步：{item.get('year', '—')} {_gz_text(item)}")
    for block in bazi.get("direction") or []:
        if not isinstance(block, dict):
            continue
        line = f"大运：{_gz_text(block.get('mainDirect'))} 起于{block.get('startYear', '—')}年"
        subs = []
        for sub in block.get("subDirect") or []:
            if isinstance(sub, dict):
                subs.append(f"{sub.get('date', '—')} {_gz_text(sub)}")
        direction_lines.append(line)
        if subs:
            direction_lines.append("流年：" + "；".join(subs))
    return _render_snapshot_text(
        [
            ("起盘信息", _join_lines(base_lines)),
            ("四柱与三元", _join_lines(four_lines)),
            ("流年行运概略", _join_lines(direction_lines) or "无"),
            ("神煞（四柱与三元）", _join_lines(god_lines)),
        ]
    )


def _collect_house_stars(house: Any) -> list[str]:
    stars: list[str] = []
    if not isinstance(house, dict):
        return stars
    for key, value in house.items():
        if "star" not in key.lower():
            continue
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    text = _msg(item.get("name") or item.get("id"))
                else:
                    text = _msg(item)
                if text:
                    stars.append(text)
    return stars


def _build_ziwei_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    chart = response.get("chart", response if isinstance(response, dict) else {})
    houses = chart.get("houses") if isinstance(chart, dict) else []
    lines = [
        f"日期：{payload.get('date', '—')} {payload.get('time', '—')}",
        f"时区：{payload.get('zone', '—')}",
        f"经纬度：{payload.get('lon', '—')} {payload.get('lat', '—')}",
        f"性别：{payload.get('gender', '—')}",
        f"时间算法：{'直接时间' if str(payload.get('timeAlg', 0)) == '1' else '真太阳时'}",
    ]
    overview: list[str] = []
    for index, house in enumerate(houses or [], start=1):
        if not isinstance(house, dict):
            continue
        name = house.get("name") or house.get("id") or f"宫位{index}"
        ganzi = _msg(house.get("ganzi")) or "无"
        direction = house.get("direction")
        direction_text = f"{direction[0]}~{direction[1]}" if isinstance(direction, list) and len(direction) == 2 else "无"
        stars = "、".join(_collect_house_stars(house)) or "无"
        overview.append(f"{name}：大限={direction_text}，干支={ganzi}")
        overview.append(f"星曜：{stars}")
        overview.append("")
    return _render_snapshot_text(
        [
            ("起盘信息", _join_lines(lines)),
            ("宫位总览", _join_lines(overview) or "无"),
        ]
    )


def _append_map_section_snapshot(blocks: list[tuple[str, str]], title: str, data: Any) -> None:
    body = _stringify_export_body(data) or "无"
    blocks.append((title, body))


def _build_liureng_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    liureng = response.get("liureng", response if isinstance(response, dict) else {})
    nongli = liureng.get("nongli") if isinstance(liureng, dict) else {}
    four = liureng.get("fourColumns") if isinstance(liureng, dict) else {}
    runyear = response.get("runyear") or response.get("runYear") or liureng.get("runyear") if isinstance(liureng, dict) else None
    base_lines = [
        f"日期：{payload.get('date', '—')} {payload.get('time', '—')}",
        f"时区：{payload.get('zone', '—')}",
        f"经纬度：{payload.get('lon', '—')} {payload.get('lat', '—')}",
    ]
    if isinstance(nongli, dict) and nongli.get("birth"):
        base_lines.append(f"真太阳时：{nongli.get('birth')}")
    if isinstance(four, dict):
        base_lines.append(
            f"四柱：{_gz_text(four.get('year'))}年 {_gz_text(four.get('month'))}月 {_gz_text(four.get('day'))}日 {_gz_text(four.get('time'))}时"
        )
    sections: list[tuple[str, str]] = [("起盘信息", _join_lines(base_lines))]
    for title, key in [
        ("十二盘式", "panStyle"),
        ("十二地盘/十二天盘/十二贵神对应", "layout"),
        ("四课", "ke"),
        ("三传", "sanChuan"),
        ("行年", None),
        ("旬日", "xun"),
        ("旺衰", "season"),
        ("基础神煞", "gods"),
        ("干煞", "godsGan"),
        ("月煞", "godsMonth"),
        ("支煞", "godsZi"),
        ("岁煞", "godsYear"),
        ("十二长生", "zhangsheng"),
        ("大格", "dage"),
        ("小局", "xiaoju"),
        ("参考", "reference"),
        ("概览", "overview"),
    ]:
        if title == "行年":
            body = _stringify_export_body(runyear) or "无"
        else:
            body = _stringify_export_body(liureng.get(key)) if isinstance(liureng, dict) else ""
            if not body and isinstance(response, dict):
                body = _stringify_export_body(response.get(key))
        sections.append((title, body or "无"))
    return _render_snapshot_text(sections)


def _build_jieqi_compact_chart_text(payload: dict[str, Any], chart_wrap: dict[str, Any]) -> str:
    lines = _build_base_info_lines(chart_wrap, payload)
    lines.extend(_build_house_cusp_lines(chart_wrap))
    lines.extend(_build_star_and_lot_position_lines(chart_wrap))
    return _join_lines(lines) or "无数据"


def _build_jieqi_compact_suzhan_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    chart = response.get("chart", {})
    houses = chart.get("houses") if isinstance(chart, dict) else []
    objects = chart.get("objects") if isinstance(chart, dict) else []
    lines = [
        f"日期：{payload.get('date', '—')} {payload.get('time', '—')}",
        f"时区：{payload.get('zone', '—')}",
        f"经纬度：{payload.get('lon', '—')} {payload.get('lat', '—')}",
        f"外盘：{payload.get('szchart', 0)}",
        f"盘型：{payload.get('szshape', 0)}",
        "",
        "宿盘宫位与二十八宿星曜：",
    ]
    if isinstance(houses, list):
        for house in houses:
            if not isinstance(house, dict):
                continue
            house_id = house.get("id", "House")
            lines.append(f"宫位：{house_id}")
            in_house = [obj for obj in (objects or []) if isinstance(obj, dict) and obj.get("house") == house_id]
            if not in_house:
                lines.append("星曜：无")
                lines.append("")
                continue
            for obj in in_house:
                deg, minute = _split_degree(obj.get("signlon", obj.get("lon")))
                su28 = _msg(obj.get("su28"))
                su_text = f"{deg}˚{su28}{minute}分" if su28 else f"{deg}˚{minute}分"
                lines.append(f"星曜：{_planet_label(obj.get('id'))} {su_text}".strip())
            lines.append("")
    return _join_lines(lines) or "无数据"


def _build_jieqi_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    charts = response.get("charts") if isinstance(response, dict) else {}
    jieqis = payload.get("jieqis") or ["春分", "夏至", "秋分", "冬至"]
    sections: list[tuple[str, str]] = [
        (
            "节气盘参数",
            _join_lines(
                [
                    f"年份：{payload.get('year', '—')}",
                    f"时区：{payload.get('zone', '—')}",
                    f"经纬度：{payload.get('lon', '—')} {payload.get('lat', '—')}",
                    "说明：以下包含二分二至（春分、夏至、秋分、冬至）的星盘与宿盘专用导出。",
                ]
            ),
        )
    ]
    if isinstance(charts, dict):
        for title in jieqis:
            one = charts.get(title)
            if not isinstance(one, dict):
                continue
            sections.append((f"{title}星盘", _build_jieqi_compact_chart_text(one.get("params", payload), one)))
            su_body = _build_jieqi_compact_suzhan_text(one.get("params", payload), one)
            sections.append((f"{title}宿盘", su_body))
    return _render_snapshot_text(sections)


def _build_nongli_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    lines = [
        f"日期：{payload.get('date', '—')} {payload.get('time', '—')}",
        f"时区：{payload.get('zone', '—')}",
        f"经纬度：{payload.get('lon', '—')} {payload.get('lat', '—')}",
    ]
    for key in ("birth", "nongli", "year", "yearJieqi", "monthGanZi", "dayGanZi", "time", "jiedelta", "chef"):
        value = response.get(key) if isinstance(response, dict) else None
        if value:
            lines.append(f"{key}：{value}")
    return _render_snapshot_text([("起盘信息", _join_lines(lines))])


def _build_gua_lookup_snapshot_text(tool_name: str, payload: dict[str, Any], response: dict[str, Any]) -> str:
    queried = payload.get("name") or []
    gua_lines: list[str] = []
    desc_lines: list[str] = []
    for key in queried:
        item = response.get(key) if isinstance(response, dict) else None
        if isinstance(item, dict):
            gua_lines.append(f"{key}：{item.get('name', '无')}")
            text = item.get("卦辞") or item.get("desc") or item.get("text") or _stringify_export_body(item)
            desc_lines.append(f"{item.get('name', key)}：{text}")
        else:
            gua_lines.append(f"{key}：无")
    return _render_snapshot_text(
        [
            ("起盘信息", _join_lines([f"查询：{'、'.join(queried) if queried else '无'}", f"来源：{tool_name}"])),
            ("卦象", _join_lines(gua_lines) or "无"),
            ("六爻与动爻", "无"),
            ("卦辞与断语", _join_lines(desc_lines) or "无"),
        ]
    )


def _build_predictive_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    star_lines = _build_star_and_lot_position_lines(response)[:20]
    setup_lines = [
        f"出生时间：{response.get('params', {}).get('birth', '无')}",
        f"推运时间：{payload.get('datetime', '无')}",
        f"推运时区：{payload.get('dirZone') or payload.get('zone', '无')}",
        f"推运地点：{payload.get('dirLon') or payload.get('lon', '—')} {payload.get('dirLat') or payload.get('lat', '—')}",
    ]
    aspect_lines = _build_aspect_section(response)
    return _render_snapshot_text(
        [
            ("星盘信息", _join_lines(star_lines) or "无"),
            ("起盘信息", _join_lines(setup_lines)),
            ("相位", _join_lines(aspect_lines) or "无"),
        ]
    )


def _primary_direction_method_text(value: Any) -> str:
    mapping = {"horosa_legacy": "Horosa原方法", "astroapp_alchabitius": "AstroAPP-Alchabitius"}
    return mapping.get(_msg(value), _msg(value) or "无")


def _primary_direction_time_key_text(value: Any) -> str:
    mapping = {"Ptolemy": "Ptolemy", "Naibod": "Naibod", "Cardan": "Cardan"}
    return mapping.get(_msg(value), _msg(value) or "无")


def _pd_obj_text(value: Any, chart_wrap: dict[str, Any]) -> str:
    if isinstance(value, dict):
        object_id = value.get("id") or value.get("obj") or value.get("name")
        if object_id:
            return _astro_msg_with_house(object_id, chart_wrap, short=True)
        return _stringify_export_body(value)
    return _astro_msg_with_house(value, chart_wrap, short=True) or _planet_label(value)


def _build_primarydirect_snapshot_text(response: dict[str, Any]) -> str:
    params = response.get("params", {}) if isinstance(response, dict) else {}
    predictives = response.get("predictives", {}) if isinstance(response, dict) else {}
    pds = predictives.get("primaryDirection", []) if isinstance(predictives, dict) else []
    show_pd_bounds = not (params.get("showPdBounds") in {0, False})
    degree_label = "赤经" if params.get("pdMethod") == "horosa_legacy" else "Arc"
    rows = [f"| {degree_label} | 迫星 | 应星 | 日期 |", "| --- | --- | --- | --- |"]
    if not isinstance(pds, list) or not pds:
        rows.append("| 无 | 无 | 无 | 无 |")
    else:
        for row in pds:
            if not isinstance(row, list):
                continue
            degree = _msg(row[0]) or "无"
            promittor = _pd_obj_text(row[1] if len(row) > 1 else None, response) or "无"
            significator = _pd_obj_text(row[2] if len(row) > 2 else None, response) or "无"
            date = _msg(row[4] if len(row) > 4 else None) or "无"
            rows.append(f"| {degree} | {promittor} | {significator} | {date} |")
    return _render_snapshot_text(
        [
            ("出生时间", f"出生时间：{params.get('birth', '无')}"),
            ("星盘信息", _join_lines([f"经纬度：{params.get('lon', '—')} {params.get('lat', '—')}", f"时区：{params.get('zone', '—')}"])),
            (
                "主/界限法设置",
                _join_lines(
                    [
                        f"推运方法：{_primary_direction_method_text(params.get('pdMethod'))}",
                        f"度数换算：{_primary_direction_time_key_text(params.get('pdTimeKey'))}",
                        f"显示界限法：{'是' if show_pd_bounds else '否'}",
                    ]
                ),
            ),
            ("主/界限法表格", _join_lines(rows)),
        ]
    )


def _build_pdchart_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    params = response.get("params", {}) if isinstance(response, dict) else {}
    current_arc = response.get("currentArc") or response.get("arc") or response.get("pdArc") or "无"
    return _render_snapshot_text(
        [
            ("出生时间", f"出生时间：{params.get('birth', '无')}"),
            ("星盘信息", _join_lines([f"经纬度：{params.get('lon', '—')} {params.get('lat', '—')}", f"时区：{params.get('zone', '—')}"])),
            (
                "主限法盘设置",
                _join_lines(
                    [
                        f"时间选择：{payload.get('datetime', '无')}",
                        f"推运方法：{_primary_direction_method_text(params.get('pdMethod'))}",
                        f"度数换算：{_primary_direction_time_key_text(params.get('pdTimeKey'))}",
                        f"当前Arc：{current_arc}",
                    ]
                ),
            ),
            (
                "主限法盘说明",
                _join_lines(
                    [
                        "左侧双盘内圈为本命盘，外圈为按当前主限法设置和所选时间推导出的主限法盘位置。",
                        "当前页面会先将所选时间换算为主限年龄弧，再按后台主限法算法推进各星曜与虚点，最后统一投影回黄道后与本命盘套盘显示。",
                    ]
                ),
            ),
        ]
    )


def _build_zr_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    params = response.get("params", {}) if isinstance(response, dict) else {}
    predictives = response.get("predictives", {}) if isinstance(response, dict) else {}
    zr_data = None
    for key in ("zodialRelease", "zodiacalRelease", "zr", "zodialrelease"):
        if isinstance(predictives, dict) and predictives.get(key) is not None:
            zr_data = predictives.get(key)
            break
    lines = [f"出生时间：{params.get('birth', '无')}", f"经纬度：{params.get('lon', '—')} {params.get('lat', '—')}", f"时区：{params.get('zone', '—')}"]
    base_point = payload.get("basePoint") or response.get("basePoint") or "X点"
    zr_lines: list[str] = []
    if isinstance(zr_data, list):
        for idx, item in enumerate(zr_data, start=1):
            if isinstance(item, dict):
                zr_lines.append(f"L1-{idx}：{item.get('planet', item.get('name', '无'))}-{item.get('date', '无')}")
    elif isinstance(zr_data, dict):
        zr_lines.append(_stringify_export_body(zr_data))
    return _render_snapshot_text([("起盘信息", _join_lines(lines)), ("星盘信息", _join_lines(_build_star_and_lot_position_lines(response)[:20]) or "无"), (f"基于{base_point}推运", _join_lines(zr_lines) or "无推运数据")])


def _auto_snapshot_text_for_tool(tool_name: str, input_normalized: dict[str, Any], response_data: dict[str, Any]) -> str | None:
    if tool_name in {"chart", "chart13", "hellen_chart", "india_chart"} and _is_astro_chart_payload(response_data):
        return _build_astro_snapshot_text(input_normalized, response_data)
    if tool_name in {"solarreturn", "lunarreturn", "solararc", "givenyear", "profection"}:
        return _build_predictive_snapshot_text(input_normalized, response_data)
    if tool_name == "pd":
        return _build_primarydirect_snapshot_text(response_data)
    if tool_name == "pdchart":
        return _build_pdchart_snapshot_text(input_normalized, response_data)
    if tool_name == "zr":
        return _build_zr_snapshot_text(input_normalized, response_data)
    if tool_name == "relative":
        return _build_relative_snapshot_text(input_normalized, response_data)
    if tool_name in {"bazi_birth", "bazi_direct"}:
        return _build_bazi_snapshot_text(input_normalized, response_data)
    if tool_name in {"ziwei_birth", "ziwei_rules"}:
        return _build_ziwei_snapshot_text(input_normalized, response_data)
    if tool_name in {"liureng_gods", "liureng_runyear"}:
        return _build_liureng_snapshot_text(input_normalized, response_data)
    if tool_name == "jieqi_year":
        return _build_jieqi_snapshot_text(input_normalized, response_data)
    if tool_name == "nongli_time":
        return _build_nongli_snapshot_text(input_normalized, response_data)
    if tool_name in {"gua_desc", "gua_meiyi"}:
        return _build_gua_lookup_snapshot_text(tool_name, input_normalized, response_data)
    return None


def _pick_section_data(title: str, *, input_normalized: dict[str, Any], response_data: dict[str, Any]) -> Any:
    normalized_title = title.strip()
    chart = response_data.get("chart")
    pan = response_data.get("pan")
    bazi = response_data.get("bazi")
    liureng = response_data.get("liureng")
    jinkou = response_data.get("jinkou")
    predictives = response_data.get("predictives")
    if _is_astro_chart_payload(response_data):
        if normalized_title in {"起盘信息", "出生时间", "关系起盘信息", "节气盘参数", "星盘信息"}:
            lines = _build_base_info_lines(response_data, input_normalized)
            return _export_body_data("\n".join(lines).strip(), {"input": input_normalized, "chart": chart or response_data})
        if normalized_title in {"宫位宫头", "宫位总览"}:
            lines = _build_house_cusp_lines(response_data)
            return _export_body_data("\n".join(lines).strip(), (chart or {}).get("houses") or [])
        if normalized_title in {"星与虚点"}:
            lines = _build_star_and_lot_position_lines(response_data)
            return _export_body_data("\n".join(lines).strip(), {"objects": (chart or {}).get("objects") or [], "lots": response_data.get("lots") or []})
        if normalized_title == "信息":
            lines = _build_info_section(response_data, input_normalized)
            return _export_body_data("\n".join(lines).strip(), {"chart": chart or response_data, "receptions": response_data.get("receptions"), "mutuals": response_data.get("mutuals"), "surround": response_data.get("surround"), "declParallel": response_data.get("declParallel")})
        if normalized_title == "相位":
            lines = _build_aspect_section(response_data)
            return _export_body_data("\n".join(lines).strip(), response_data.get("aspects") or {})
        if normalized_title == "行星":
            lines = _build_planet_section(response_data)
            return _export_body_data("\n".join(lines).strip(), (chart or {}).get("objects") or [])
        if normalized_title == "希腊点":
            lines = _build_lots_section(response_data)
            return _export_body_data("\n".join(lines).strip(), response_data.get("lots") or [])
        if normalized_title == "可能性":
            lines = _build_possibility_section(response_data)
            return _export_body_data("\n".join(lines).strip(), response_data.get("predict", {}) or {})

    if normalized_title in {"起盘信息", "出生时间", "关系起盘信息", "节气盘参数"}:
        return input_normalized
    if normalized_title in {"星盘信息", "合成图盘", "影响图盘-星盘A", "影响图盘-星盘B"}:
        return chart or response_data
    if normalized_title in {"宫位宫头", "宫位总览"}:
        if isinstance(chart, dict) and chart.get("houses") is not None:
            return chart.get("houses")
        return chart or response_data
    if normalized_title in {"星与虚点", "行星"}:
        if isinstance(chart, dict):
            return chart.get("planets") or chart.get("stars") or chart
        return response_data.get("planets") or response_data
    if normalized_title == "相位":
        if isinstance(chart, dict) and chart.get("aspects") is not None:
            return chart.get("aspects")
        return response_data.get("aspects") or response_data
    if normalized_title == "希腊点":
        if isinstance(chart, dict):
            return chart.get("greekPoints") or chart.get("lots") or {}
        return response_data.get("greekPoints") or response_data.get("lots") or {}
    if normalized_title == "可能性":
        if isinstance(chart, dict):
            return chart.get("possibility") or chart.get("possibilities") or {}
        return response_data.get("possibility") or response_data.get("possibilities") or {}
    if normalized_title in {"主/界限法设置", "主限法盘设置", "十年大运设置"}:
        return {"input": input_normalized, "predictives": predictives or response_data}
    if normalized_title in {"主/界限法表格", "主限法盘说明", "法达星限表格", "基于X点推运", "基于X起运"}:
        return predictives or response_data
    if normalized_title in {"中点", "中点相位"}:
        return response_data
    if normalized_title in {"宿盘宫位与二十八宿星曜"}:
        return chart or response_data
    if normalized_title in {"骰子结果", "骰子盘宫位与星体", "天象盘宫位与星体"}:
        return response_data
    if normalized_title in {"四柱与三元", "流年行运概略", "神煞（四柱与三元）"}:
        return bazi or response_data
    if normalized_title in {"十二盘式", "十二地盘/十二天盘/十二贵神对应", "四课", "三传", "行年", "旬日", "旺衰", "基础神煞", "干煞", "月煞", "支煞", "岁煞", "十二长生", "大格", "小局", "参考", "概览"}:
        return liureng or response_data
    if normalized_title in {"金口诀速览", "金口诀四位", "四位神煞"}:
        return jinkou or response_data
    if normalized_title in {"盘型", "盘面要素", "奇门演卦", "八宫详解", "九宫方盘"}:
        return pan or response_data
    if normalized_title in {"太乙盘", "十六宫标记"}:
        return pan or response_data
    if normalized_title in {"卦象", "六爻与动爻", "卦辞与断语", "本卦", "六爻", "潜藏", "亲和"}:
        return response_data
    return response_data


def _build_generated_export_snapshot(
    *,
    technique: str,
    input_normalized: dict[str, Any],
    response_data: dict[str, Any],
    snapshot_text: str | None = None,
    parsed_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    technique_info = get_technique_info(technique)
    if technique_info is None:
        return None

    preset_sections = list(technique_info["preset_sections"])
    forbidden_sections = {f"{item or ''}".strip() for item in technique_info.get("forbidden_sections", [])}
    selected_sections = list(preset_sections)
    settings_used = {
        "version": build_export_registry(technique=technique)["settings_version"],
        "sections": {technique: selected_sections},
        "planetInfo": {},
        "astroMeaning": {},
    }
    if technique_info["supports_planet_info"]:
        settings_used["planetInfo"][technique] = technique_info["planet_info_default"]
    if technique_info["supports_astro_meaning"] or technique_info["supports_hover_meaning"]:
        settings_used["astroMeaning"][technique] = technique_info["astro_meaning_default"]

    parsed_sections_by_title = {}
    detected_titles: list[str] = []
    unknown_detected_sections: list[str] = []
    missing_selected_sections: list[str] = []
    if isinstance(parsed_snapshot, dict):
        for section in parsed_snapshot.get("sections", []):
            if isinstance(section, dict) and section.get("title"):
                parsed_sections_by_title[section["title"]] = section
                title = f"{section['title']}".strip()
                if title and title not in forbidden_sections:
                    detected_titles.append(title)
        if detected_titles:
            merged_sections = list(preset_sections)
            for title in detected_titles:
                if title not in merged_sections:
                    merged_sections.append(title)
            selected_sections = [title for title in merged_sections if title not in forbidden_sections]
            settings_used["sections"][technique] = selected_sections
        unknown_detected_sections = list(parsed_snapshot.get("unknown_detected_sections", []) or [])
        missing_selected_sections = list(parsed_snapshot.get("missing_selected_sections", []) or [])

    sections: list[dict[str, Any]] = []
    rendered_blocks: list[str] = []
    for index, title in enumerate(selected_sections, start=1):
        parsed_section = parsed_sections_by_title.get(title, {})
        section_data = _pick_section_data(title, input_normalized=input_normalized, response_data=response_data)
        section_body_override = None
        section_payload = section_data
        if isinstance(section_data, dict) and ("__export_body__" in section_data or "__export_data__" in section_data):
            section_body_override = _stringify_export_body(section_data.get("__export_body__"))
            section_payload = section_data.get("__export_data__")
        body = parsed_section.get("body") or section_body_override or _stringify_export_body(section_payload)
        content = parsed_section.get("content") or (f"[{title}]\n{body}".strip() if body else f"[{title}]")
        rendered_blocks.append(content)
        sections.append(
            {
                "index": index,
                "raw_title": parsed_section.get("raw_title", title),
                "title": title,
                "included": True,
                "body": body,
                "content": content,
                "data": _sanitize_section_data(section_payload),
            }
        )

    export_text = "\n\n".join(block for block in rendered_blocks if block.strip()).strip()
    provenance = _build_export_provenance(technique, snapshot_text)
    citation = (
        f"Xingque AI export · {technique_info.get('label', technique)} · "
        f"settings v{provenance.get('bundle_version')} · source {provenance.get('upstream_source_marker')}"
    )
    return {
        "technique": technique_info,
        "settings_used": settings_used,
        "section_titles_detected": detected_titles or [section["title"] for section in sections],
        "selected_sections": selected_sections,
        "unknown_detected_sections": unknown_detected_sections,
        "missing_selected_sections": missing_selected_sections,
        "sections": sections,
        "raw_text": snapshot_text or (parsed_snapshot.get("raw_text", "") if isinstance(parsed_snapshot, dict) else ""),
        "filtered_text": export_text,
        "export_text": export_text,
        "format_source": "snapshot_parser" if parsed_snapshot else "generated_template",
        "snapshot_text": snapshot_text,
        "bundle_version": provenance.get("bundle_version"),
        "provenance": provenance,
        "citation": citation,
    }


def _attach_export_contract(tool_name: str, input_normalized: dict[str, Any], response_data: dict[str, Any]) -> dict[str, Any]:
    technique = TOOL_EXPORT_TECHNIQUE_MAP.get(tool_name)
    if not technique:
        return response_data

    augmented = dict(response_data)
    snapshot_text = augmented.get("snapshot_text") if isinstance(augmented.get("snapshot_text"), str) else None
    parsed_snapshot = augmented.get("export_snapshot") if isinstance(augmented.get("export_snapshot"), dict) else None
    if not snapshot_text:
        snapshot_text = _auto_snapshot_text_for_tool(tool_name, input_normalized, response_data)
        augmented["snapshot_text"] = snapshot_text
    if snapshot_text and not parsed_snapshot:
        try:
            parsed_snapshot = parse_export_content(technique=technique, content=snapshot_text)
            augmented["export_snapshot"] = parsed_snapshot
        except ValueError:
            parsed_snapshot = None
    export_format = _build_generated_export_snapshot(
        technique=technique,
        input_normalized=input_normalized,
        response_data=augmented,
        snapshot_text=snapshot_text,
        parsed_snapshot=parsed_snapshot,
    )
    if export_format is None:
        return augmented

    augmented["export_snapshot"] = export_format
    augmented["export_format"] = {
        "technique": export_format["technique"],
        "selected_sections": export_format["selected_sections"],
        "format_source": export_format["format_source"],
        "snapshot_text": export_format["snapshot_text"],
        "bundle_version": export_format.get("bundle_version"),
        "provenance": export_format.get("provenance"),
        "citation": export_format.get("citation"),
        "sections": [
            {
                "index": section["index"],
                "title": section["title"],
                "included": section["included"],
                "body": section["body"],
                "data": section["data"],
            }
            for section in export_format["sections"]
        ],
    }
    return augmented


def _build_dispatch_export_contract(result: ToolEnvelope) -> dict[str, Any]:
    export_snapshot = result.data.get("export_snapshot") if isinstance(result.data, dict) else None
    export_format = result.data.get("export_format") if isinstance(result.data, dict) else None
    technique = export_snapshot.get("technique") if isinstance(export_snapshot, dict) else None
    return {
        "ok": result.ok,
        "tool": result.tool,
        "summary": list(result.summary),
        "warnings": list(result.warnings),
        "memory_ref": result.memory_ref.model_dump(mode="json") if result.memory_ref else None,
        "has_export_snapshot": isinstance(export_snapshot, dict),
        "has_export_format": isinstance(export_format, dict),
        "technique": technique,
        "selected_sections": list(export_format.get("selected_sections", [])) if isinstance(export_format, dict) else [],
        "format_source": export_format.get("format_source") if isinstance(export_format, dict) else None,
        "snapshot_text": export_format.get("snapshot_text") if isinstance(export_format, dict) else None,
        "bundle_version": export_format.get("bundle_version") if isinstance(export_format, dict) else None,
        "provenance": export_format.get("provenance") if isinstance(export_format, dict) else None,
        "citation": export_format.get("citation") if isinstance(export_format, dict) else None,
        "export_snapshot": export_snapshot if isinstance(export_snapshot, dict) else None,
        "export_format": export_format if isinstance(export_format, dict) else None,
        "error": result.error.model_dump(mode="json") if result.error else None,
    }


class HorosaSkillService:
    def __init__(
        self,
        settings: Settings,
        client: HorosaApiClient | None = None,
        store: MemoryStore | None = None,
        js_client: HorosaJsEngineClient | None = None,
        runtime_manager: HorosaRuntimeManager | None = None,
    ) -> None:
        self.settings = settings
        self.client = client or HorosaApiClient(settings.server_root)
        self.store = store or MemoryStore(settings)
        self.js_client = js_client or HorosaJsEngineClient(settings)
        self.runtime_manager = runtime_manager or HorosaRuntimeManager(settings)
        self.tracer = TraceRecorder(settings)
        self._remote_runtime_ready = False

    def _unwrap_result(self, payload: Any) -> Any:
        current = payload
        for _ in range(4):
            if not isinstance(current, dict):
                return current
            if isinstance(current.get("Result"), dict):
                current = current["Result"]
                continue
            if isinstance(current.get("result"), dict):
                current = current["result"]
                continue
            return current
        return current

    def _call_remote(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self._remote_runtime_ready and not self.client.probe("/common/time"):
            self.runtime_manager.start_local_services()
        data = self.client.call(endpoint, payload)
        self._remote_runtime_ready = True
        unwrapped = self._unwrap_result(data)
        if not isinstance(unwrapped, dict):
            raise ToolTransportError(
                "Horosa endpoint returned a non-object result payload.",
                code="transport.invalid_result_shape",
                details={"endpoint": endpoint},
            )
        return unwrapped

    def _augment_export_payload(self, *, technique: str, snapshot_text: str | None) -> dict[str, Any] | None:
        if not snapshot_text:
            return None
        try:
            return parse_export_content(technique=technique, content=snapshot_text)
        except ValueError:
            return None

    def _run_qimen_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        year = int(str(payload["date"])[:4])
        nongli = payload.get("nongli")
        if not isinstance(nongli, dict):
            nongli = self._call_remote(
                "/nongli/time",
                {
                    "date": payload["date"],
                    "time": payload["time"],
                    "zone": payload["zone"],
                    "lon": payload["lon"],
                    "lat": payload["lat"],
                    "gpsLat": payload.get("gpsLat"),
                    "gpsLon": payload.get("gpsLon"),
                    "after23NewDay": payload.get("after23NewDay", False),
                    "timeAlg": payload.get("timeAlg", 0),
                    "ad": payload.get("ad", 1),
                },
            )
        prev_year = payload.get("jieqi_year_prev")
        if not isinstance(prev_year, dict):
            prev_year = self._call_remote(
                "/jieqi/year",
                {
                    "year": year - 1,
                    "zone": payload["zone"],
                    "lat": payload["lat"],
                    "lon": payload["lon"],
                    "time": payload["time"],
                    "gpsLat": payload.get("gpsLat"),
                    "gpsLon": payload.get("gpsLon"),
                    "ad": payload.get("ad", 1),
                    "timeAlg": payload.get("timeAlg", 0),
                },
            )
        current_year = payload.get("jieqi_year_current")
        if not isinstance(current_year, dict):
            current_year = self._call_remote(
                "/jieqi/year",
                {
                    "year": year,
                    "zone": payload["zone"],
                    "lat": payload["lat"],
                    "lon": payload["lon"],
                    "time": payload["time"],
                    "gpsLat": payload.get("gpsLat"),
                    "gpsLon": payload.get("gpsLon"),
                    "ad": payload.get("ad", 1),
                    "timeAlg": payload.get("timeAlg", 0),
                },
            )
        js_result = self.js_client.run(
            "qimen",
            {
                **payload,
                "nongli": nongli,
                "jieqi_year_prev": prev_year,
                "jieqi_year_current": current_year,
            },
        )
        snapshot_text = js_result.get("snapshot_text")
        return {
            "pan": js_result.get("data", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="qimen", snapshot_text=snapshot_text),
            "prerequisites": {
                "nongli": nongli,
                "jieqi_year_prev": prev_year,
                "jieqi_year_current": current_year,
            },
        }

    def _run_taiyi_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        nongli = payload.get("nongli")
        if not isinstance(nongli, dict):
            nongli = self._call_remote(
                "/nongli/time",
                {
                    "date": payload["date"],
                    "time": payload["time"],
                    "zone": payload["zone"],
                    "lon": payload["lon"],
                    "lat": payload["lat"],
                    "gpsLat": payload.get("gpsLat"),
                    "gpsLon": payload.get("gpsLon"),
                    "after23NewDay": payload.get("after23NewDay", False),
                    "timeAlg": payload.get("timeAlg", 0),
                    "ad": payload.get("ad", 1),
                },
            )
        js_result = self.js_client.run("taiyi", {**payload, "nongli": nongli})
        snapshot_text = js_result.get("snapshot_text")
        return {
            "pan": js_result.get("data", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="taiyi", snapshot_text=snapshot_text),
            "prerequisites": {
                "nongli": nongli,
            },
        }

    def _run_jinkou_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        liureng = payload.get("liureng")
        if not isinstance(liureng, dict):
            remote = self._call_remote(
                "/liureng/gods",
                {
                    "date": payload["date"],
                    "time": payload["time"],
                    "zone": payload["zone"],
                    "lat": payload["lat"],
                    "lon": payload["lon"],
                    "after23NewDay": payload.get("after23NewDay", False),
                    "yue": payload.get("yue"),
                    "isDiurnal": payload.get("isDiurnal"),
                    "ad": payload.get("ad", 1),
                },
            )
            liureng = remote.get("liureng", remote)
        js_result = self.js_client.run(
            "jinkou",
            {
                **payload,
                "liureng": liureng,
            },
        )
        snapshot_text = js_result.get("snapshot_text")
        return {
            "jinkou": js_result.get("data", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="jinkou", snapshot_text=snapshot_text),
            "prerequisites": {
                "liureng": liureng,
            },
        }

    def _run_tongshefa_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        js_result = self.js_client.run("tongshefa", payload)
        snapshot_text = js_result.get("snapshot_text")
        return {
            "tongshefa": js_result.get("data", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="tongshefa", snapshot_text=snapshot_text),
        }

    def _run_sanshiunited_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        shared = {
            "date": payload["date"],
            "time": payload["time"],
            "zone": payload["zone"],
            "lat": payload["lat"],
            "lon": payload["lon"],
            "gpsLat": payload.get("gpsLat"),
            "gpsLon": payload.get("gpsLon"),
            "ad": payload.get("ad", 1),
            "after23NewDay": payload.get("after23NewDay", False),
            "timeAlg": payload.get("timeAlg", 0),
        }
        qimen_result = self.run_tool(
            "qimen",
            {**shared, "options": payload.get("qimen_options", {})},
            save_result=False,
        )
        taiyi_result = self.run_tool(
            "taiyi",
            {**shared, "options": payload.get("taiyi_options", {})},
            save_result=False,
        )
        liureng_result = self.run_tool(
            "liureng_gods",
            {
                **shared,
                "yue": payload.get("liureng_yue"),
                "isDiurnal": payload.get("liureng_isDiurnal"),
            },
            save_result=False,
        )

        qimen_export = qimen_result.data.get("export_snapshot")
        taiyi_export = taiyi_result.data.get("export_snapshot")
        liureng_export = liureng_result.data.get("export_snapshot")
        snapshot_text = _render_snapshot_text(
            [
                ("起盘信息", _section_body(qimen_export, "起盘信息")),
                (
                    "概览",
                    "\n".join(
                        [
                            _section_body(qimen_export, "盘型"),
                            _section_body(qimen_export, "盘面要素"),
                        ]
                    ).strip(),
                ),
                ("太乙", _section_body(taiyi_export, "太乙盘")),
                ("太乙十六宫", _section_body(taiyi_export, "十六宫标记")),
                (
                    "神煞",
                    "\n".join(
                        [
                            _section_body(liureng_export, "基础神煞", ""),
                            _section_body(liureng_export, "干煞", ""),
                            _section_body(liureng_export, "月煞", ""),
                            _section_body(liureng_export, "支煞", ""),
                            _section_body(liureng_export, "岁煞", ""),
                        ]
                    ).strip()
                    or "无",
                ),
                ("大六壬", _section_body(liureng_export, "四课")),
                ("六壬大格", _section_body(liureng_export, "大格")),
                ("六壬小局", _section_body(liureng_export, "小局")),
                ("六壬参考", _section_body(liureng_export, "参考")),
                ("六壬概览", _section_body(liureng_export, "概览")),
                ("八宫详解", _section_body(qimen_export, "八宫详解")),
                *_render_qimen_palace_sections(qimen_result.data.get("pan", {})),
            ]
        )
        return {
            "qimen": qimen_result.data.get("pan", {}),
            "taiyi": taiyi_result.data.get("pan", {}),
            "liureng": liureng_result.data.get("liureng", {}),
            "subresults": {
                "qimen": qimen_result.model_dump(mode="json"),
                "taiyi": taiyi_result.model_dump(mode="json"),
                "liureng_gods": liureng_result.model_dump(mode="json"),
            },
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="sanshiunited", snapshot_text=snapshot_text),
        }

    def _run_hellen_chart_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        remote_payload = {**payload, "predictive": 0}
        response = self._call_remote("/chart13", remote_payload)
        return response

    def _run_guolao_chart_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        remote_payload = {
            **payload,
            "tradition": True,
            "doubingSu28": payload.get("doubingSu28", True),
            "predictive": False,
            "hsys": payload.get("hsys", 0),
            "zodiacal": payload.get("zodiacal", 0),
        }
        response = self._call_remote("/chart", remote_payload)
        snapshot_text = _build_guolao_snapshot_text(remote_payload, response)
        response = dict(response)
        response["snapshot_text"] = snapshot_text
        response["export_snapshot"] = self._augment_export_payload(technique="guolao", snapshot_text=snapshot_text)
        return response

    def _run_suzhan_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        remote_payload = {**payload, "predictive": False, "doubingSu28": payload.get("doubingSu28", True)}
        response = self._call_remote("/chart", remote_payload)
        snapshot_text = _build_suzhan_snapshot_text(remote_payload, response)
        return {
            **response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="suzhan", snapshot_text=snapshot_text),
        }

    def _run_germany_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        chart_payload = {**payload, "predictive": 0}
        chart_response = self._call_remote("/chart", chart_payload)
        germany_result = self._call_remote("/germany/midpoint", chart_payload)
        snapshot_text = _build_germany_snapshot_text(chart_payload, chart_response, germany_result)
        result = {
            "chart": chart_response.get("chart"),
            "midpoints": germany_result.get("midpoints", germany_result if isinstance(germany_result, list) else []),
            "aspects": germany_result.get("aspects", {}),
            "raw": germany_result,
            "snapshot_text": snapshot_text,
        }
        result["export_snapshot"] = self._augment_export_payload(technique="germany", snapshot_text=snapshot_text)
        return result

    def _run_otherbu_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        remote_payload = {
            **payload,
            "date": payload["date"],
            "time": payload["time"],
            "zone": payload["zone"],
            "lon": payload["lon"],
            "lat": payload["lat"],
            "gpsLon": payload.get("gpsLon"),
            "gpsLat": payload.get("gpsLat"),
            "hsys": payload.get("hsys", 0),
            "zodiacal": payload.get("zodiacal", 0),
            "tradition": payload.get("tradition", False),
            "virtualPointReceiveAsp": payload.get("virtualPointReceiveAsp"),
            "sign": payload.get("sign", "Aries"),
            "house": payload.get("house", 0),
            "planet": payload.get("planet", "Sun"),
        }
        response = self._call_remote("/predict/dice", remote_payload)
        snapshot_text = _build_otherbu_snapshot_text({**remote_payload, "question": payload.get("question")}, response)
        result = {**response, "question": payload.get("question"), "snapshot_text": snapshot_text}
        result["export_snapshot"] = self._augment_export_payload(technique="otherbu", snapshot_text=snapshot_text)
        return result

    def _run_firdaria_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        remote_payload = {**payload, "predictive": True}
        response = self._call_remote("/chart", remote_payload)
        snapshot_text = _build_firdaria_snapshot_text(response)
        result = {
            "chart": response.get("chart"),
            "params": response.get("params", remote_payload),
            "predictives": response.get("predictives", {}),
            "firdaria": response.get("predictives", {}).get("firdaria", {}) if isinstance(response.get("predictives"), dict) else [],
            "snapshot_text": snapshot_text,
        }
        result["export_snapshot"] = self._augment_export_payload(technique="firdaria", snapshot_text=snapshot_text)
        return result

    def _run_decennials_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        remote_payload = {**payload, "predictive": True}
        response = self._call_remote("/chart", remote_payload)
        response = dict(response)
        if "params" not in response or not isinstance(response.get("params"), dict):
            response["params"] = remote_payload
        settings = {
            "startMode": payload.get("startMode", DECENNIAL_START_MODE_SECT_LIGHT),
            "orderType": payload.get("orderType", DECENNIAL_ORDER_ZODIACAL),
            "dayMethod": payload.get("dayMethod", DECENNIAL_DAY_METHOD_VALENS),
            "calendarType": payload.get("calendarType", DECENNIAL_CALENDAR_TRADITIONAL),
        }
        ai_state = {
            "aiMode": payload.get("aiMode", "l1_all"),
            "aiL1Idx": payload.get("aiL1Idx", 0),
            "aiL2Idx": payload.get("aiL2Idx", 0),
            "aiL3Idx": payload.get("aiL3Idx", 0),
        }
        timeline = build_decennial_timeline(response, settings)
        snapshot_holder = {"chart": response.get("chart"), "params": response.get("params"), "timeline": timeline}
        snapshot_text = _build_decennials_snapshot_text(snapshot_holder, settings, ai_state)
        result = {
            "chart": response.get("chart"),
            "params": response.get("params"),
            "timeline": timeline,
            "settings": settings,
            "aiState": ai_state,
            "snapshot_text": snapshot_text,
        }
        result["export_snapshot"] = self._augment_export_payload(technique="decennials", snapshot_text=snapshot_text)
        return result

    def _run_sixyao_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        nongli = self._call_remote(
            "/nongli/time",
            {
                "date": payload["date"],
                "time": payload["time"],
                "zone": payload["zone"],
                "lon": payload["lon"],
                "lat": payload["lat"],
                "gpsLat": payload.get("gpsLat"),
                "gpsLon": payload.get("gpsLon"),
                "ad": payload.get("ad", 1),
            },
        )
        lines = _normalize_gua_lines(payload.get("lines"))
        if not lines:
            lines = [
                {"value": 1, "change": False, "god": "青龙", "name": "初爻"},
                {"value": 0, "change": False, "god": "朱雀", "name": "二爻"},
                {"value": 1, "change": True, "god": "勾陈", "name": "三爻"},
                {"value": 0, "change": False, "god": "腾蛇", "name": "四爻"},
                {"value": 1, "change": False, "god": "白虎", "name": "五爻"},
                {"value": 0, "change": True, "god": "玄武", "name": "上爻"},
            ]
        current_code = payload.get("gua_code") or _derive_gua_code(lines)
        changed_code = payload.get("changed_code") or _derive_changed_gua_code(lines)
        descs = self._call_remote("/gua/desc", {"name": [current_code, changed_code]})
        snapshot_text = _build_sixyao_snapshot_text(payload, nongli, current_code, changed_code, lines, descs)
        result = {
            "nongli": nongli,
            "current_code": current_code,
            "changed_code": changed_code,
            "lines": lines,
            "question": payload.get("question"),
            "descriptions": descs,
            "snapshot_text": snapshot_text,
        }
        result["export_snapshot"] = self._augment_export_payload(technique="sixyao", snapshot_text=snapshot_text)
        return result

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "mcp_name": tool.mcp_name,
                "execution": tool.execution,
                "endpoint": tool.endpoint,
                "description": tool.description,
            }
            for tool in TOOL_DEFINITIONS.values()
        ]

    def _run_local_tool(self, definition: ToolDefinition, payload: dict[str, Any]) -> dict[str, Any]:
        if definition.name == "export_registry":
            return build_export_registry(technique=payload.get("technique"))
        if definition.name == "export_parse":
            try:
                return parse_export_content(
                    technique=payload["technique"],
                    content=payload["content"],
                    selected_sections=payload.get("selected_sections"),
                    planet_info=payload.get("planet_info"),
                    astro_meaning=payload.get("astro_meaning"),
                )
            except ValueError as exc:
                raise ToolValidationError(
                    str(exc),
                    code="tool.invalid_export_technique",
                    details={"tool_name": definition.name, "technique": payload.get("technique")},
                ) from exc
        if definition.name == "knowledge_registry":
            return build_knowledge_registry(domain=payload.get("domain"))
        if definition.name == "knowledge_read":
            return read_knowledge_entry(payload)
        if definition.name == "qimen":
            return self._run_qimen_tool(payload)
        if definition.name == "taiyi":
            return self._run_taiyi_tool(payload)
        if definition.name == "jinkou":
            return self._run_jinkou_tool(payload)
        if definition.name == "suzhan":
            return self._run_suzhan_tool(payload)
        if definition.name == "sixyao":
            return self._run_sixyao_tool(payload)
        if definition.name == "tongshefa":
            return self._run_tongshefa_tool(payload)
        if definition.name == "sanshiunited":
            return self._run_sanshiunited_tool(payload)
        if definition.name == "hellen_chart":
            return self._run_hellen_chart_tool(payload)
        if definition.name == "guolao_chart":
            return self._run_guolao_chart_tool(payload)
        if definition.name == "germany":
            return self._run_germany_tool(payload)
        if definition.name == "firdaria":
            return self._run_firdaria_tool(payload)
        if definition.name == "decennials":
            return self._run_decennials_tool(payload)
        if definition.name == "otherbu":
            return self._run_otherbu_tool(payload)
        raise ToolValidationError(
            f"Unsupported local tool: {definition.name}",
            code="tool.unsupported_local_tool",
            details={"tool_name": definition.name},
        )

    def run_tool(
        self,
        tool_name: str,
        payload: dict[str, Any],
        *,
        save_result: bool = True,
        run_id: str | None = None,
        query_text: str | None = None,
        group_id: str | None = None,
        evaluation_case_id: str | None = None,
    ) -> ToolEnvelope:
        if tool_name not in TOOL_DEFINITIONS:
            raise ToolValidationError(f"Unknown tool: {tool_name}", code="tool.unknown", details={"tool_name": tool_name})

        definition = TOOL_DEFINITIONS[tool_name]
        workflow_group_id = group_id or self.tracer.new_group_id()
        with self.tracer.span(
            workflow_name="tool.run",
            group_id=workflow_group_id,
            metadata={
                "entrypoint": "tool",
                "tool_name": tool_name,
                "runtime_target": definition.execution,
                "query_text": query_text,
                "payload": payload,
                "evaluation_case_id": evaluation_case_id,
            },
        ) as trace:
            try:
                validated = definition.input_model.model_validate(payload)
            except ValidationError as exc:
                trace["error_code"] = "tool.invalid_payload"
                raise ToolValidationError(
                    f"Invalid payload for tool `{tool_name}`.",
                    code="tool.invalid_payload",
                    details={"errors": exc.errors()},
                ) from exc

            input_normalized = validated.model_dump(exclude_none=True)
            memory_ref = None

            try:
                if definition.execution == "local":
                    response_data = self._run_local_tool(definition, input_normalized)
                else:
                    assert definition.endpoint is not None
                    response_data = self._call_remote(definition.endpoint, input_normalized)
                response_data = _attach_export_contract(tool_name, input_normalized, response_data)
                summary = _generic_summary(tool_name, response_data)
                warnings: list[str] = []
                envelope = ToolEnvelope(
                    ok=True,
                    tool=tool_name,
                    version=__version__,
                    input_normalized=input_normalized,
                    data=response_data,
                    summary=summary,
                    warnings=warnings,
                    memory_ref=None,
                    error=None,
                    trace_id=trace["trace_id"],
                    group_id=trace["group_id"],
                )
            except HorosaSkillError as exc:
                trace["error_code"] = exc.code
                envelope = ToolEnvelope(
                    ok=False,
                    tool=tool_name,
                    version=__version__,
                    input_normalized=input_normalized,
                    data={},
                    summary=[f"工具 `{tool_name}` 调用失败。"],
                    warnings=[],
                    memory_ref=None,
                    error=ErrorInfo(code=exc.code, message=str(exc), details=exc.details),
                    trace_id=trace["trace_id"],
                    group_id=trace["group_id"],
                )

            if save_result:
                effective_run_id = run_id or self.store.create_run(
                    entrypoint="tool",
                    query_text=query_text,
                    subject=input_normalized,
                    group_id=trace["group_id"],
                )
                self.store.record_entities(effective_run_id, _extract_entities(input_normalized, query_text))
                memory_ref = self.store.record_tool_result(
                    run_id=effective_run_id,
                    tool_name=tool_name,
                    ok=envelope.ok,
                    input_normalized=input_normalized,
                    envelope_dict=envelope.model_dump(mode="json"),
                    summary=envelope.summary,
                    warnings=envelope.warnings,
                    error=envelope.error.model_dump(mode="json") if envelope.error else None,
                    trace_id=trace["trace_id"],
                    group_id=trace["group_id"],
                    evaluation_case_id=evaluation_case_id,
                )
                envelope.memory_ref = memory_ref
                trace["run_id"] = effective_run_id
                trace["artifact_path"] = memory_ref.artifact_path

            trace["success"] = envelope.ok
            trace["input_normalized"] = input_normalized
            trace["summary"] = envelope.summary
            trace["warnings"] = envelope.warnings
            return envelope

    def record_ai_answer(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.tracer.span(
            workflow_name="memory.answer",
            metadata={"entrypoint": "memory.answer", "payload": payload},
        ) as trace:
            try:
                request = MemoryAnswerInput.model_validate(payload)
            except ValidationError as exc:
                trace["error_code"] = "memory.answer.invalid_payload"
                raise ToolValidationError(
                    "Invalid payload for memory answer record.",
                    code="memory.answer.invalid_payload",
                    details={"errors": exc.errors()},
                ) from exc

            result = self.store.attach_ai_response(
                run_id=request.run_id,
                user_question=request.user_question,
                ai_answer=request.ai_answer,
                ai_answer_structured=request.ai_answer_structured,
                answer_meta=request.answer_meta,
            )
            result["summary"] = ["已将 AI 回答写回对应 run 记录，并同步更新本地 manifest 与 artifact。"]
            result["trace_id"] = trace["trace_id"]
            result["group_id"] = trace["group_id"]
            trace["run_id"] = request.run_id
            return result

    def query_memory(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.tracer.span(
            workflow_name="memory.query",
            metadata={"entrypoint": "memory.query", "payload": payload},
        ) as trace:
            try:
                request = MemoryQueryInput.model_validate(payload)
            except ValidationError as exc:
                trace["error_code"] = "memory.query.invalid_payload"
                raise ToolValidationError(
                    "Invalid payload for memory query.",
                    code="memory.query.invalid_payload",
                    details={"errors": exc.errors()},
                ) from exc

            results = self.store.query_runs(
                run_id=request.run_id,
                tool=request.tool,
                entity=request.entity,
                after=request.after,
                before=request.before,
                limit=max(1, request.limit),
                include_payload=request.include_payload,
            )
            trace["result_count"] = len(results)
            return {
                "ok": True,
                "count": len(results),
                "results": results,
                "trace_id": trace["trace_id"],
                "group_id": trace["group_id"],
                "summary": [f"已检索到 {len(results)} 条本地 run 记录。"],
            }

    def show_memory(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.tracer.span(
            workflow_name="memory.show",
            metadata={"entrypoint": "memory.show", "payload": payload},
        ) as trace:
            try:
                request = MemoryShowInput.model_validate(payload)
            except ValidationError as exc:
                trace["error_code"] = "memory.show.invalid_payload"
                raise ToolValidationError(
                    "Invalid payload for memory show.",
                    code="memory.show.invalid_payload",
                    details={"errors": exc.errors()},
                ) from exc

            results = self.store.query_runs(
                run_id=request.run_id,
                limit=1,
                include_payload=request.include_payload,
            )
            if not results:
                trace["error_code"] = "memory.run.not_found"
                return {
                    "ok": False,
                    "code": "memory.run.not_found",
                    "message": f"Run not found: {request.run_id}",
                    "details": {},
                    "trace_id": trace["trace_id"],
                    "group_id": trace["group_id"],
                }

            trace["run_id"] = request.run_id
            return {
                "ok": True,
                "result": results[0],
                "trace_id": trace["trace_id"],
                "group_id": trace["group_id"],
                "summary": ["已读取对应 run 的本地完整记录。"],
            }

    def dispatch(self, payload: dict[str, Any], *, evaluation_case_id: str | None = None) -> DispatchEnvelope:
        try:
            request = DispatchInput.model_validate(payload)
        except ValidationError as exc:
            raise ToolValidationError(
                "Invalid payload for horosa_dispatch.",
                code="dispatch.invalid_payload",
                details={"errors": exc.errors()},
            ) from exc

        try:
            selected_tools = select_tools(request)
        except DispatchResolutionError as exc:
            return DispatchEnvelope(
                ok=False,
                version=__version__,
                selected_tools=[],
                normalized_inputs={},
                results={},
                summary=["未能从当前输入解析出匹配的 Horosa 工具。"],
                warnings=[],
                memory_ref=None,
                error=ErrorInfo(code=exc.code, message=str(exc), details=exc.details),
            )

        normalized_inputs: dict[str, dict[str, Any]] = {}
        results: dict[str, ToolEnvelope] = {}
        result_export_contracts: dict[str, dict[str, Any]] = {}

        workflow_group_id = self.tracer.new_group_id()
        with self.tracer.span(
            workflow_name="dispatch.run",
            group_id=workflow_group_id,
            metadata={
                "entrypoint": "dispatch",
                "payload": request.model_dump(exclude_none=True),
                "query_text": request.query,
                "selected_tools": selected_tools,
                "evaluation_case_id": evaluation_case_id,
            },
        ) as trace:
            run_id = self.store.create_run(
                entrypoint="dispatch",
                query_text=request.query,
                subject=request.model_dump(exclude_none=True),
                group_id=trace["group_id"],
            ) if request.save_result else None

            def birth_payload() -> dict[str, Any]:
                if request.birth is not None:
                    return request.birth.model_dump(exclude_none=True)
                if request.subject and request.subject.birth is not None:
                    return request.subject.birth.model_dump(exclude_none=True)
                return {}

            base_birth = birth_payload()
            for tool_name in selected_tools:
                if tool_name == "relative":
                    payload_for_tool = {
                        "inner": request.subject.inner.model_dump(exclude_none=True) if request.subject and request.subject.inner else {},
                        "outer": request.subject.outer.model_dump(exclude_none=True) if request.subject and request.subject.outer else {},
                        "hsys": request.preferences.get("hsys", 0),
                        "zodiacal": request.preferences.get("zodiacal", 0),
                        "relative": request.preferences.get("relative", 0),
                    }
                elif tool_name in {"gua_desc", "gua_meiyi"}:
                    gua_names = []
                    if request.subject and request.subject.gua_names:
                        gua_names = request.subject.gua_names
                    elif "gua_names" in request.context:
                        gua_names = list(request.context["gua_names"])
                    payload_for_tool = {"name": gua_names}
                elif tool_name == "jieqi_year":
                    year = request.subject.year if request.subject and request.subject.year is not None else None
                    if year is None and base_birth.get("date"):
                        year = str(base_birth["date"])[:4]
                    payload_for_tool = {
                        "year": year,
                        "zone": base_birth.get("zone", request.context.get("zone", "8")),
                        "lat": base_birth.get("lat", request.context.get("lat", "0n00")),
                        "lon": base_birth.get("lon", request.context.get("lon", "0e00")),
                        "time": request.context.get("time"),
                    }
                else:
                    payload_for_tool = dict(base_birth)

                normalized_inputs[tool_name] = payload_for_tool
                results[tool_name] = self.run_tool(
                    tool_name,
                    payload_for_tool,
                    save_result=request.save_result,
                    run_id=run_id,
                    query_text=request.query,
                    group_id=trace["group_id"],
                    evaluation_case_id=evaluation_case_id,
                )
                result_export_contracts[tool_name] = _build_dispatch_export_contract(results[tool_name])

            summary = [f"horosa_dispatch 选择了 {len(selected_tools)} 个工具：{', '.join(selected_tools)}。"]
            summary.extend([line for result in results.values() for line in result.summary[:1]])

            envelope = DispatchEnvelope(
                ok=all(result.ok for result in results.values()),
                version=__version__,
                selected_tools=selected_tools,
                normalized_inputs=normalized_inputs,
                results=results,
                result_export_contracts=result_export_contracts,
                summary=summary[:6],
                warnings=[],
                memory_ref=None,
                error=None,
                trace_id=trace["trace_id"],
                group_id=trace["group_id"],
            )

            if request.save_result and run_id is not None:
                self.store.record_entities(run_id, _extract_entities(request.model_dump(exclude_none=True), request.query))
                envelope.memory_ref = self.store.record_dispatch_result(
                    run_id=run_id,
                    payload=envelope.model_dump(mode="json"),
                    trace_id=trace["trace_id"],
                    group_id=trace["group_id"],
                )
                trace["run_id"] = run_id
                trace["artifact_path"] = envelope.memory_ref.artifact_path if envelope.memory_ref else None

            trace["success"] = envelope.ok
            return envelope
