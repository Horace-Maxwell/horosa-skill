from __future__ import annotations

import copy
import logging
import re
import time
from datetime import timezone, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from horosa_skill import __version__
from horosa_skill.agent_guidance import build_tool_input_contract, build_validation_recovery
from horosa_skill.astro_sidereal import nakshatra_lord_cn, sidereal_ayanamsa_label
from horosa_skill.config import Settings
from horosa_skill.engine.client import HorosaApiClient, HorosaPlainJsonClient
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
from horosa_skill.input_normalization import normalize_request_payload
from horosa_skill.knowledge import build_knowledge_registry, read_knowledge_entry
from horosa_skill.memory.store import MemoryStore
from horosa_skill.reports import ReportBuilder, render_report
from horosa_skill.runtime import HorosaRuntimeManager
from horosa_skill.schemas.common import DispatchEnvelope, ErrorInfo, ToolEnvelope
from horosa_skill.schemas.tools import (
    DispatchInput,
    MemoryAnswerInput,
    MemoryQueryInput,
    MemoryShowInput,
    ReportFromToolInput,
    ReportRenderInput,
    ReportTemplateInput,
)
from horosa_skill.tracing import TraceRecorder

logger = logging.getLogger(__name__)


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
    "canping": "canping",
    "heluo": "heluo",
    "sanshiunited": "sanshiunited",
    "germany": "germany",
    "agepoint": "agepoint",
    "distributions": "distributions",
    "jaynesprog": "jaynesprog",
    "vedicprog": "vedicprog",
    "planetaryarc": "planetaryarc",
    "planetaryages": "planetaryages",
    "balbillus": "balbillus",
    "yearsystem129": "yearsystem129",
    "persiandirected": "persiandirected",
    "triplicityrulers": "triplicityrulers",
    "keypoints": "keypoints",
    "lunationphase": "lunationphase",
    "extrareturns": "extrareturns",
    "horary": "horary",
    "election": "election",
    "geomancy": "geomancy",
    "tarot": "tarot",
    "wangji": "wangji",
    "wuzhao": "wuzhao",
    "taixuan": "taixuan",
    "jingjue": "jingjue",
    "shenyishu": "shenyishu",
    "shaozi": "shaozi",
    "tieban": "tieban",
    "fendjing": "fendjing",
    "beiji": "beiji",
    "nanji": "nanji",
    "chunzi": "chunzi",
    "xianqin": "xianqin",
    "cetian": "cetian",
    "qizhengkin": "qizhengkin",
    "mundane": "mundane",
    "firdaria": "firdaria",
    "decennials": "decennials",
    "otherbu": "otherbu",
}


_JAVA_CHART_DATE_ENDPOINTS = {"/chart", "/chart13", "/india/chart"}
_JAVA_DATE_FALLBACK_ENDPOINTS = {
    "/nongli/time",
    "/jieqi/year",
    "/liureng/gods",
    "/liureng/runyear",
}
_PYTHON_CHART_ENDPOINTS = {
    "/chart",
    "/chart13",
    "/predict/solarreturn",
    "/predict/lunarreturn",
    "/predict/solararc",
    "/predict/givenyear",
    "/predict/profection",
    "/predict/pd",
    "/predict/pdchart",
    "/predict/zr",
    "/predict/dice",
    "/modern/relative",
    "/india/chart",
    "/germany/midpoint",
    "/astroextra/harmonic",
    "/predict/agepoint",
    "/predict/dist",
    "/astroextra/jaynesprog",
    "/astroextra/progressions",
    "/astroextra/planetreturn",
    "/astroextra/analysis",
    # 世俗盘子盘群（新月/满月图、日月食判词、木土大合相、行星聚散指数）依赖的 astroextra 精算端点。
    "/astroextra/prenatal_syzygy",
    "/astroextra/eclipsedetail",
    "/astroextra/greatconj",
    "/astroextra/barbault",
    "/geomancy/reading",
    "/predict/planetaryarc",
    "/jieqi/year",
    "/qimen/pan",
    "/taiyi/pan",
    "/jinkou/pan",
    # 神数 family (v2.5.x) — kentang mounts on the chart service (:8899), each returns a backend-built `snapshot`.
    "/wangji/pan",
    "/wuzhao/pan",
    "/taixuan/pan",
    "/jingjue/pan",
    "/shenyishu/pan",
    # 9 kinastro-* 神数
    "/shaozi/pan",
    "/tieban/pan",
    "/fendjing/pan",
    "/beiji/pan",
    "/nanji/pan",
    "/chunzi/pan",
    "/xianqin/pan",
    "/cetian/pan",
    "/qizhengkin/pan",
}


def _slash_date_prefix(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if len(value) < 10 or value[4] != "-" or value[7] != "-":
        return value
    return f"{value[:4]}/{value[5:7]}/{value[8:10]}{value[10:]}"


def _dash_date_prefix(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if len(value) < 10 or value[4] != "/" or value[7] != "/":
        return value
    return f"{value[:4]}-{value[5:7]}-{value[8:10]}{value[10:]}"


def _java_zone_hour(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if len(text) != 6 or text[0] not in "+-" or text[3] != ":":
        return value
    hours = text[1:3]
    minutes = text[4:6]
    if not (hours.isdigit() and minutes == "00"):
        return value
    signed = int(hours)
    if text[0] == "-":
        signed = -signed
    return str(signed)


def _java_chart_payload(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    if endpoint not in _JAVA_CHART_DATE_ENDPOINTS:
        return payload
    normalized = dict(payload)
    for key in ("date", "datetime"):
        if key in normalized:
            normalized[key] = _slash_date_prefix(normalized[key])
    return normalized


def _java_chart_payload_candidates(endpoint: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    first = _java_chart_payload(endpoint, payload)
    if endpoint not in _JAVA_CHART_DATE_ENDPOINTS and endpoint not in _JAVA_DATE_FALLBACK_ENDPOINTS:
        return [first]

    variants: list[dict[str, Any]] = []

    def add(candidate: dict[str, Any]) -> None:
        if candidate not in variants:
            variants.append(candidate)

    date_variants = [dict(first)]
    dashed = dict(first)
    slash = dict(first)
    for key in ("date", "datetime", "guaDate"):
        if key in dashed:
            dashed[key] = _dash_date_prefix(dashed[key])
        if key in slash:
            slash[key] = _slash_date_prefix(slash[key])
    if endpoint in _JAVA_CHART_DATE_ENDPOINTS:
        if dashed != first:
            date_variants.append(dashed)
    else:
        # Nongli/jieqi/liureng endpoints are less consistent across bundled
        # Java runtime builds. Keep the validated Xingque-style payload first,
        # then retry the slash date variant that older local backends accept.
        if slash != first:
            date_variants.append(slash)
        if dashed != first and dashed not in date_variants:
            date_variants.append(dashed)

    zone_hour = _java_zone_hour(first.get("zone"))
    zone_values = [first.get("zone")]
    if zone_hour != first.get("zone"):
        zone_values.append(zone_hour)

    for date_candidate in date_variants:
        for zone_value in zone_values:
            candidate = dict(date_candidate)
            if "zone" in candidate:
                candidate["zone"] = zone_value
            add(candidate)

            gps_lon = candidate.get("gpsLon")
            if isinstance(gps_lon, (int, float)) and gps_lon < 0:
                absolute_lon = dict(candidate)
                absolute_lon["gpsLon"] = abs(gps_lon)
                add(absolute_lon)

            gps_lat = candidate.get("gpsLat")
            gps_lon = candidate.get("gpsLon")
            if isinstance(gps_lat, (int, float)) and isinstance(gps_lon, (int, float)):
                # Some Windows chart-runtime builds reject compact `31n13`/`121e28`
                # before falling through to gpsLat/gpsLon. Try decimal-only
                # variants so user-facing clients do not have to hand-edit payloads.
                gps_only = {key: value for key, value in candidate.items() if key not in {"lat", "lon"}}
                add(gps_only)

                decimal_lat_lon = dict(candidate)
                decimal_lat_lon["lat"] = gps_lat
                decimal_lat_lon["lon"] = gps_lon
                add(decimal_lat_lon)

                if gps_lon < 0:
                    decimal_abs_lon = dict(decimal_lat_lon)
                    decimal_abs_lon["lon"] = abs(gps_lon)
                    decimal_abs_lon["gpsLon"] = abs(gps_lon)
                    add(decimal_abs_lon)

            without_gps = {key: value for key, value in candidate.items() if key not in {"gpsLat", "gpsLon"}}
            add(without_gps)
    return variants


def _only_payload_keys(payload: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: payload[key] for key in keys if key in payload and payload[key] is not None}


def _liureng_remote_payload(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "liureng_runyear":
        return _only_payload_keys(
            payload,
            (
                "date",
                "time",
                "zone",
                "lat",
                "lon",
                "after23NewDay",
                "ad",
                "gender",
                "guaYearGanZi",
                "guaDate",
                "guaTime",
                "guaZone",
                "guaLon",
                "guaLat",
                "guaAd",
                "guaAfter23NewDay",
            ),
        )
    return _only_payload_keys(
        payload,
        ("date", "time", "zone", "lat", "lon", "after23NewDay", "ad", "yue", "isDiurnal"),
    )


def _liureng_chart_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in {
            "date": payload.get("guaDate") or payload.get("date"),
            "time": payload.get("guaTime") or payload.get("time"),
            "zone": payload.get("guaZone") or payload.get("zone"),
            "lat": payload.get("guaLat") or payload.get("lat"),
            "lon": payload.get("guaLon") or payload.get("lon"),
            "gpsLat": payload.get("gpsLat"),
            "gpsLon": payload.get("gpsLon"),
            "ad": payload.get("guaAd") or payload.get("ad", 1),
            "hsys": 0,
            "tradition": False,
            "predictive": False,
            "zodiacal": 0,
        }.items()
        if value is not None
    }


def _chart_server_endpoint(endpoint: str) -> str:
    return "/" if endpoint == "/chart" else endpoint


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
        summary = ["已通过 ken 后端运行奇门遁甲。"]
        if pan.get("juText"):
            summary.append(f"局数：{pan['juText']}。")
        if pan.get("zhiFu") and pan.get("zhiShi"):
            summary.append(f"值符 {pan['zhiFu']}，值使 {pan['zhiShi']}。")
        return summary
    if tool_name == "taiyi":
        pan = data.get("pan", {})
        summary = ["已通过 ken 后端运行太乙。"]
        if pan.get("zhao"):
            summary.append(f"命式：{pan['zhao']}。")
        kook = pan.get("kook")
        kook_text = kook.get("text") if isinstance(kook, dict) else kook
        if kook_text:
            summary.append(f"局式：{kook_text}。")
        return summary
    if tool_name == "jinkou":
        result = data.get("jinkou", {})
        summary = ["已通过 ken 后端运行金口诀。"]
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
    if tool_name == "canping":
        model = data.get("canping", {})
        summary = ["已运行本地邵子参评数（金锁银匙）算法。"]
        if model.get("element") and model.get("partName"):
            summary.append(f"年纳音：{model['element']}（{model['partName']}）。")
        if model.get("dayPalaceBranch") and model.get("mingGong"):
            summary.append(f"日宫支 {model['dayPalaceBranch']}，命宫 {model['mingGong']}。")
        benming = model.get("benming") if isinstance(model.get("benming"), dict) else {}
        verses = benming.get("verses") if isinstance(benming.get("verses"), dict) else {}
        if verses.get("numShun") and verses.get("numNi"):
            summary.append(f"本命数：顺 {verses['numShun']} / 逆 {verses['numNi']}。")
        return summary
    if tool_name == "heluo":
        model = data.get("heluo", {})
        summary = ["已运行本地河洛理数算法。"]
        chart = model.get("chart") if isinstance(model.get("chart"), dict) else {}
        xian = chart.get("xian") if isinstance(chart.get("xian"), dict) else {}
        hou = chart.get("hou") if isinstance(chart.get("hou"), dict) else {}
        if xian.get("name") and hou.get("name"):
            summary.append(f"先天卦 {xian['name']} → 后天卦 {hou['name']}。")
        if chart.get("tian") is not None and chart.get("di") is not None:
            summary.append(f"天数 {chart['tian']}（{chart.get('tianGua', '')}）／地数 {chart['di']}（{chart.get('diGua', '')}）。")
        return summary
    if tool_name == "harmonic":
        summary = [f"已生成调波盘（H{data.get('harmonic', '—')}）。"]
        positions = data.get("positions")
        if isinstance(positions, list):
            summary.append(f"调波位置点数：{len(positions)}。")
        conjunctions = data.get("conjunctions")
        if isinstance(conjunctions, list) and conjunctions:
            summary.append(f"同频合相：{len(conjunctions)} 组。")
        return summary
    if tool_name == "agepoint":
        summary = ["已生成年龄推进点（Age Point / Huber）时间线。"]
        points = data.get("points")
        if isinstance(points, list):
            summary.append(f"年龄点数：{len(points)}。")
            key_ages = [p for p in points if isinstance(p, dict) and p.get("aspectTo")]
            if key_ages:
                summary.append(f"合本命关键岁数：{len(key_ages)} 处。")
        return summary
    if tool_name == "distributions":
        summary = ["已生成界推运（分配法 / Distributions）时间线。"]
        rows = data.get("distributions")
        if isinstance(rows, list):
            summary.append(f"分配期数：{len(rows)}。")
        return summary
    if tool_name == "mundane":
        summary = ["已生成世俗入宫盘（mundane ingress）。"]
        if data.get("ingressTerm") and data.get("ingressYear"):
            summary.append(f"{data['ingressYear']} 年「{data['ingressTerm']}」入宫。")
        if data.get("ingressMoment"):
            summary.append(f"入宫时刻：{data['ingressMoment']}。")
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


def _missing_detail_text(title: str) -> str:
    return (
        f"本次本地计算结果未返回「{title}」细项；"
        "报告只能基于已返回盘面判断，不能臆造外部依赖、桌面端服务或不存在的数据。"
    )


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
    fallback = _missing_detail_text(title) if default == "无" else default
    section = _section_map_from_export(export_snapshot).get(title)
    if not section:
        return fallback
    body = section.get("body")
    if isinstance(body, str) and body.strip():
        return body.strip()
    content = section.get("content")
    if isinstance(content, str) and content.strip():
        content_lines = [line for line in content.splitlines() if not line.startswith("[")]
        text = "\n".join(content_lines).strip()
        if text:
            return text
    return fallback


def _render_snapshot_text(sections: list[tuple[str, str]]) -> str:
    blocks: list[str] = []
    for title, body in sections:
        clean_body = (body or "").strip() or _missing_detail_text(title)
        blocks.append(f"[{title}]\n{clean_body}".strip())
    return "\n\n".join(blocks).strip()


def _ken_datetime_parts(payload: dict[str, Any]) -> dict[str, int]:
    date_text = str(payload.get("date") or "")
    time_text = str(payload.get("time") or "")
    date_bits = [int(p) for p in date_text.split("-") if p.strip().lstrip("-").isdigit()]
    time_bits = [int(p) for p in time_text.split(":") if p.strip().isdigit()]
    while len(date_bits) < 3:
        date_bits.append(1)
    while len(time_bits) < 3:
        time_bits.append(0)
    return {
        "year": date_bits[0],
        "month": date_bits[1],
        "day": date_bits[2],
        "hour": time_bits[0],
        "minute": time_bits[1],
        "second": time_bits[2],
    }


def _ken_qimen_mode(options: dict[str, Any]) -> str:
    explicit = options.get("qimenMode")
    if isinstance(explicit, str) and explicit:
        return explicit
    mode_by_paipan = {0: "year", 2: "golden", 4: "minute", 5: "overall"}
    pai_pan = options.get("paiPanType")
    try:
        return mode_by_paipan.get(int(pai_pan), "hour")
    except (TypeError, ValueError):
        return "hour"


def _build_export_provenance(technique: str, snapshot_text: str | None) -> dict[str, Any]:
    technique_info = get_technique_info(technique) or {}
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
        return [(title, _missing_detail_text(title)) for title in palace_map.values()]

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


# ── 七政四余·大限（命度→十二宫）+ 相位：星阙 GuoLaoMoiraWheel/GuoLaoChartMain 的 Python 移植 ──
# 默认 lifeMode=ASC（headless 无 UI 偏好；不支持 per-盘命主显示偏好——见 README/AGENTS）。
# 政余格局（buildLocalMoiraPatterns Moira DSL）v0.11.0 起 JS vendor（guolaoMoira.js）评估：盘面物象
# 格局（孛犯太阳/金水相涵/命坐两歧 等）可出；依赖 七政神煞(官福疾) 的格局受限于 guolaoGods 未随
# /chart 返回（kinastro qizheng 另路，如实标出）。见 _run_guolao_chart_tool 的 js_client 调用。
_GUOLAO_LIMIT_SEQ = [11.0, 10.0, 11.0, 15.0, 8.0, 7.0, 11.0, 4.5, 4.5, 4.5, 5.0, 5.0]
_GUOLAO_HOUSE_BRANCH = ("命宫", "财帛", "兄弟", "田宅", "男女", "奴仆", "夫妻", "疾厄", "迁移", "官禄", "福德", "相貌")
_GUOLAO_ASP_STATES = (("Applicative", "入相"), ("Exact", "精确"), ("Separative", "离相"), ("None", "容许"))


def _js_round(value: Any) -> int:
    # JS Math.round（half-up）；age/span 恒正，int(x+0.5) 等价（含 0.5 进位与 星阙 一致）。
    try:
        return int(float(value) + 0.5)
    except (TypeError, ValueError):
        return 0


def _guolao_norm(deg: Any) -> float:
    try:
        val = float(deg) % 360
    except (TypeError, ValueError):
        return 0.0
    return val + 360 if val < 0 else val


def _guolao_object_ra(obj: Any, prefer_lon: bool) -> float | None:
    if not isinstance(obj, dict):
        return None
    if prefer_lon and obj.get("lon") is not None:
        raw = obj.get("lon")
    elif obj.get("ra") is not None:
        raw = obj.get("ra")
    else:
        raw = obj.get("lon")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _guolao_life_degree(chart: dict[str, Any]) -> float:
    # 命度（默认 ASC 模式）：primary=ASC 赤经，缺则命主度(LifeMasterDeg74)，再缺则太阳。
    objects = chart.get("objects") if isinstance(chart, dict) else []
    params = chart.get("params") if isinstance(chart, dict) else {}
    prefer_lon = isinstance(params, dict) and (str(params.get("doubingSu28")) == "4" or str(params.get("guolaoZhengSidereal")) == "1")
    by_id = {o.get("id"): o for o in objects or [] if isinstance(o, dict)}
    asc = _guolao_object_ra(by_id.get("Asc"), prefer_lon)
    life = _guolao_object_ra(by_id.get("LifeMasterDeg74"), prefer_lon)
    sun = _guolao_object_ra(by_id.get("Sun"), prefer_lon)
    val = asc if asc is not None else (life if life is not None else sun)
    return 0.0 if val is None else val


def _guolao_limit_table(life: float, birth_year: int) -> list[dict[str, Any]]:
    in_sign = _guolao_norm(life) % 30
    segs = [max(1, _js_round(9 + in_sign / 3))] + _GUOLAO_LIMIT_SEQ[1:]
    rows: list[dict[str, Any]] = []
    age = 1.0
    for k in range(12):
        span = max(0.5, float(segs[k]) if k < len(segs) else 0.0)
        from_age = _js_round(age)
        to_age = _js_round(age + span) - 1
        rows.append({
            "index": k + 1, "palace": _GUOLAO_HOUSE_BRANCH[k], "years": _js_round(span * 10) / 10,
            "from_age": from_age, "to_age": to_age,
            "from_year": birth_year + from_age - 1, "to_year": birth_year + to_age - 1,
        })
        age += span
    return rows


def _build_guolao_limit_lines(chart: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    life = _guolao_life_degree(chart)
    try:
        birth_year = int(str(payload.get("date", "")).split("/")[0])
    except (TypeError, ValueError):
        birth_year = 0
    return [
        f"第{r['index']}限 {r['palace']}：{r['from_age']}-{r['to_age']}岁（{r['from_year']}-{r['to_year']}年），约{r['years']}年"
        for r in _guolao_limit_table(life, birth_year)
    ]


def _build_guolao_aspect_lines(chart: dict[str, Any], response: dict[str, Any]) -> list[str]:
    aspects = (chart.get("aspects") if isinstance(chart, dict) else None) or (response.get("aspects") if isinstance(response, dict) else None)
    normal = aspects.get("normalAsp") if isinstance(aspects, dict) and isinstance(aspects.get("normalAsp"), dict) else aspects
    lines: list[str] = []
    if not isinstance(normal, dict):
        return lines
    for key, bucket in normal.items():
        if not isinstance(bucket, dict):
            continue
        for field, state in _GUOLAO_ASP_STATES:
            for asp in bucket.get(field) or []:
                if not isinstance(asp, dict) or not asp.get("id"):
                    continue
                try:
                    orb_text = f"，误差{_round3(float(asp.get('orb')))}"
                except (TypeError, ValueError):
                    orb_text = ""
                lines.append(f"{_planet_label(key)} {_aspect_text(asp.get('asp'))} {_planet_label(asp.get('id'))}（{state}{orb_text}）")
    return lines


def _build_guolao_snapshot_text(payload: dict[str, Any], response: dict[str, Any], pattern_text: str | None = None) -> str:
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
            ("大限", "\n".join(_build_guolao_limit_lines(chart, payload)).strip() or "无"),
            # 政余格局 (星阙 v2.6.x Moira DSL)：由 vendored guolaoMoira.js (buildLocalMoiraPatterns) 评估，
            # 经 js_client 注入。盘面物象格局（孛犯太阳/金水相涵/命坐两歧 等）可出；依赖 七政神煞(官福疾)
            # 的格局受限于上游 guolaoGods 未随 /chart 返回（kinastro qizheng 另路，如实标出，见 AGENTS）。
            ("政余格局", (pattern_text or "").strip() or "无"),
            ("相位", "\n".join(_build_guolao_aspect_lines(chart, response)).strip() or "无"),
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
    # 主限法 v12 (星阙 v2.6.6)：宿命点应星行 id N_Vertex_0（仅 In-Zodiaco 核出）。
    "Vertex": "宿命点",
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
    # 恒星黄道 (星阙 v2.6.4)：原 '恒星黄道，岁差:Lahiri' 硬编码 Lahiri 会误标 Raman/Fagan 盘。
    # 去硬编码 → 真实岁差名由 _build_base_info_lines 另起一行（sidereal_ayanamsa_label）补上。
    "Sidereal": "恒星黄道",
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
    # 主限法 v12 (星阙 v2.6.6)：宿命点应星行 id N_Vertex_0（仅 In-Zodiaco 核出）。
    "Vertex": "宿命点",
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
    # 恒星黄道 (星阙 v2.6.4)：sidereal 盘附岁差(ayanāṃśa)名，区分 Lahiri/Raman/Fagan 等不同制。
    # chart.zodiacal 是已本地化的字符串("恒星黄道")，故以后端解析后的字段为准（西洋盘=siderealAyanamsa，
    # 印占盘=siderealModeKey + 数值 ayanamsaValue）；旧后端缺字段时，回退「请求为恒星黄道→请求 ayan/缺省 lahiri」。
    ayan_key = chart.get("siderealAyanamsa") or chart.get("siderealModeKey")
    if not ayan_key and str(fields.get("zodiacal")) in {"1", "True", "true"}:
        ayan_key = fields.get("siderealAyanamsa") or fields.get("indiaAyanamsa") or "lahiri"
    if not ayan_key and (fields.get("indiaHsys") is not None or fields.get("indiaAyanamsa") is not None):
        ayan_key = fields.get("indiaAyanamsa") or "lahiri"  # 印占盘恒为恒星黄道
    if ayan_key:
        ayan_value = chart.get("ayanamsaValue")
        if ayan_value not in (None, ""):
            lines.append(f"恒星黄道岁差：{sidereal_ayanamsa_label(ayan_key)}（{ayan_value}）")
        else:
            lines.append(f"恒星黄道岁差：{sidereal_ayanamsa_label(ayan_key)}")
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


def _as_chart_wrap(value: Any, *, fallback_lots: Any = None, fallback_aspects: Any = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    if isinstance(value.get("chart"), dict):
        wrapper = dict(value)
    elif isinstance(value.get("objects"), list) or isinstance(value.get("houses"), list):
        wrapper = {"chart": value}
    else:
        return {}
    if fallback_lots is not None and "lots" not in wrapper:
        wrapper["lots"] = fallback_lots
    if fallback_aspects is not None and "aspects" not in wrapper:
        wrapper["aspects"] = fallback_aspects
    return wrapper


def _top_level_chart_wrap(response: dict[str, Any]) -> dict[str, Any]:
    return _as_chart_wrap(
        response.get("chart"),
        fallback_lots=response.get("lots"),
        fallback_aspects=response.get("aspects"),
    )


def _chart_wrap_from_response(response: dict[str, Any], key: str) -> dict[str, Any]:
    return _as_chart_wrap(
        response.get(key),
        fallback_lots=response.get("lots"),
        fallback_aspects=response.get("aspects"),
    )


def _chart_position_table_lines(chart_wrap: dict[str, Any], *, limit: int | None = None) -> list[str]:
    object_map = _get_objects_map(chart_wrap)
    rows = ["| 星体/虚点 | 位置 | 宫位 | 速度 |", "| --- | --- | --- | --- |"]
    count = 0
    for object_id in [*ASTRO_OBJECT_ORDER, *ASTRO_LOT_ORDER]:
        obj = object_map.get(object_id)
        if not isinstance(obj, dict) or obj.get("sign") is None or obj.get("signlon") is None:
            continue
        rows.append(
            "| "
            f"{_astro_msg(object_id, short=True)} | "
            f"{_format_sign_degree(obj.get('sign'), obj.get('signlon'))}{_format_retrograde_text(obj)} | "
            f"{_astro_msg(obj.get('house')) or '—'} | "
            f"{_format_speed(obj) if obj.get('lonspeed') is not None else '—'} |"
        )
        count += 1
        if limit is not None and count >= limit:
            break
    if count == 0:
        rows.append("| 无 | 无 | 无 | 无 |")
    return rows


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
    normal = aspects.get("normalAsp") if isinstance(aspects, dict) else None
    immediate = aspects.get("immediateAsp") if isinstance(aspects, dict) else None
    sign_asp = aspects.get("signAsp") if isinstance(aspects, dict) else None
    # Some chart types (e.g. india_chart) return these as empty lists instead of dicts; coerce any
    # non-dict to {} so the per-object `.get()` lookups below don't raise `'list' object has no attribute 'get'`.
    normal = normal if isinstance(normal, dict) else {}
    immediate = immediate if isinstance(immediate, dict) else {}
    sign_asp = sign_asp if isinstance(sign_asp, dict) else {}
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
    if not isinstance(planet_sign, dict):  # some chart types return this empty as a list, not a dict
        planet_sign = {}
    lines: list[str] = []
    for key, items in planet_sign.items():
        lines.append(_astro_msg(key, short=True))
        for text in items or []:
            lines.append(_msg(text))
    return lines


# 寿命引擎产出小写 key → chart id (= 星阙 LIFESPAN_KEY_TO_ID), 再经 _astro_msg 显示中文.
_LIFESPAN_KEY_TO_ID = {
    "sun": "Sun", "moon": "Moon", "mercury": "Mercury", "venus": "Venus",
    "mars": "Mars", "jupiter": "Jupiter", "saturn": "Saturn", "asc": "Asc", "mc": "MC",
    "fortune": "Pars Fortuna", "syzygy": "Syzygy", "north_node": "North Node", "south_node": "South Node",
}


def _lifespan_name(key: Any) -> str:
    if not key:
        return "-"
    lk = f"{key}".lower()
    if lk in _LIFESPAN_KEY_TO_ID:
        return _astro_msg(_LIFESPAN_KEY_TO_ID[lk])
    cap = lk[:1].upper() + lk[1:]
    mapped = _astro_msg(cap)
    return mapped if mapped and mapped != cap else f"{key}"


def _sign_degree(lon: Any) -> str:
    # lon → "Y˚<座>Z分" (simplified lonToSignDegree; the term clause is dropped — sign+degree is faithful).
    try:
        value = float(lon) % 360.0
    except (TypeError, ValueError):
        return ""
    if value < 0:
        value += 360.0
    sign_idx = int(value // 30) % 12
    signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
    deg, minute = _split_degree(value)
    return f"{deg}˚{_astro_msg(signs[sign_idx])}{minute}分"


def _build_natal_extra_sections(extras: dict[str, Any]) -> dict[str, str]:
    """Format the v2.4.0 本命增补 sections (12分度 / 主宰星链 / 寿命格局) from astroextra's structured data."""
    out: dict[str, str] = {}
    dodeca = extras.get("dodeca") if isinstance(extras.get("dodeca"), list) else []
    if dodeca:
        lines = [f"{_astro_msg(d.get('id'))}：本命 {_sign_degree(d.get('natalLon'))} → 12分度 {_sign_degree(d.get('dodecaLon'))}" for d in dodeca if isinstance(d, dict)]
        out["12分度"] = "\n".join(lines)
    dispositor = extras.get("dispositor") if isinstance(extras.get("dispositor"), list) else []
    if dispositor:
        lines = [f"{_astro_msg(d.get('id'))}：{' → '.join(_astro_msg(k) for k in (d.get('chain') or []))}" for d in dispositor if isinstance(d, dict)]
        out["主宰星链"] = "\n".join(lines)
    ls = extras.get("lifespan") if isinstance(extras.get("lifespan"), dict) else None
    if ls:
        lines = [f"区分：{'昼生盘' if ls.get('isDiurnal') else '夜生盘'}"]
        hy = ls.get("hyleg") if isinstance(ls.get("hyleg"), dict) else None
        if hy:
            pos = _sign_degree(hy.get("lon")) if hy.get("lon") is not None else ""
            house = f"（第{hy.get('house')}宫）" if hy.get("house") else ""
            lines.append(f"生命主(Hyleg)：{_lifespan_name(hy.get('key'))} {pos}{house}")
        else:
            lines.append("生命主(Hyleg)：未定")
        alc = ls.get("alcocoden") if isinstance(ls.get("alcocoden"), dict) else None
        if alc and alc.get("alcocoden"):
            lines.append(f"寿主星(Alcocoden)：{_lifespan_name(alc.get('alcocoden'))}")
            if alc.get("aspectToHyleg"):
                lines.append(f"与生命主相照：{alc.get('aspectToHyleg')}")
            if alc.get("predictedYears") is not None:
                lines.append(f"预测寿数 ≈ {alc.get('predictedYears')} 年（基础 {alc.get('baseYears')} 年）")
        else:
            lines.append("寿主星(Alcocoden)：未能确定")
        rulers = ls.get("rulers") if isinstance(ls.get("rulers"), dict) else None
        if rulers:
            parts = []
            if rulers.get("epikratetor"):
                parts.append(f"占控星 {_lifespan_name(rulers.get('epikratetor'))}")
            if rulers.get("oikodespotes"):
                parts.append(f"家主星 {_lifespan_name(rulers.get('oikodespotes'))}")
            if rulers.get("kurios"):
                parts.append(f"盘主星 {_lifespan_name(rulers.get('kurios'))}")
            if parts:
                concordant = "（家主=盘主，格局相合）" if rulers.get("concordant") else ""
                lines.append(f"盘主体系：{'；'.join(parts)}{concordant}")
        out["寿命格局"] = "\n".join(lines)
    return out


def _build_nakshatra_lines(response: dict[str, Any]) -> list[str]:
    """西洋月宿 (星阙 v2.6.4)：恒星黄道盘的 perchart 响应在 chart.nakshatras 带 27 宿，
    逐行星列「宿名(梵)·宿(中)·宿主·第N足」。取数路径是 chart.nakshatras（非顶层），仅 sidereal 出。"""
    chart = response.get("chart", {}) if isinstance(response, dict) else {}
    nakshatras = chart.get("nakshatras") if isinstance(chart, dict) else None
    if not isinstance(nakshatras, dict) or not nakshatras:
        return []
    lines: list[str] = []
    for obj_id, info in nakshatras.items():
        if not isinstance(info, dict):
            continue
        name = _msg(info.get("name"))
        label = _msg(info.get("label"))
        lord = nakshatra_lord_cn(info.get("lord"))
        pada = info.get("pada")
        parts = [p for p in (name, label) if p]
        head = "·".join(parts) if parts else "—"
        suffix = f"，宿主{lord}" if lord else ""
        pada_text = f"，第{pada}足" if pada else ""
        lines.append(f"{_planet_label(obj_id)}：{head}{suffix}{pada_text}")
    return lines


# ── 古典占星 (星阙 v2.6.7)：[古典] 逐曜状态/围攻/围绕/身体部位 + [古典格局] analyze_chart 派生分析 ──
# Ports astroAiSnapshot.js#buildClassicalSection + buildClassicalAnalysisSection verbatim; reuses the
# skill's _astro_msg / _format_sign_degree / _round3 helpers. Both are pure dict→text builders.
_CLS_STATUS_IDS = ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn")
_CLS_PHASE = {"cazimi": "核心", "combust": "焦伤", "underBeams": "日光束下", "free": "自由光"}
_CLS_PHASE_EVENT = {"morningRising": "晨星初现", "eveningSetting": "昏星初没"}
_CLS_QUALITY = {"B": "明度", "D": "暗度", "E": "空度", "S": "烟度"}
_CLS_SPECIAL = {"pitted": "陷度", "azemene": "慢病度", "fortune": "增福度"}
_CLS_APOGEE = {"rising": "升·趋远地点", "falling": "降·趋近地点"}
_CLS_NUM = {"increasing": "数增·渐疾", "decreasing": "数减·渐迟"}
_CLS_LIGHT = {"waxing": "光增·渐盈", "waning": "光减·渐亏"}
_CLS_SEASON = {"春": "春·主宰", "夏": "夏·宰执", "秋": "秋·受制", "冬": "冬·被执", "中": "中"}
_CLS_MEAN_ATK = {
    "Sun": "精神阴暗·心灵扭曲", "Moon": "凶死夭折·绝症残疾", "Mercury": "智力特异·语言障碍",
    "Venus": "欲望混乱·专断残暴", "Jupiter": "世俗无成·离经叛道", "Mars": "自身受困崩坏", "Saturn": "自身受困崩坏",
}
_CLS_OVR_ASP = {"sextile": "六分", "square": "四分", "trine": "三分", "conjunction": "合", "opposition": "冲"}
_CLS_LOT_CN = {
    "Pars Fortuna": "福点", "Pars Fortunae": "福点", "Pars Spirit": "精神点", "Pars Faith": "信仰点", "Pars Substance": "资财点",
    "Pars Wedding [Male]": "婚姻点(男)", "Pars Wedding [Female]": "婚姻点(女)", "Pars Sons": "子女点",
    "Pars Father": "父亲点", "Pars Mother": "母亲点", "Pars Brothers": "兄弟点", "Pars Diseases": "疾厄点",
    "Pars Death": "死亡点", "Pars Travel": "旅行点", "Pars Friends": "朋友点", "Pars Enemies": "仇敌点",
    "Pars Saturn": "土星点", "Pars Jupiter": "木星点", "Pars Mars": "火星点", "Pars Venus": "金星点",
    "Pars Mercury": "水星点", "Pars Horsemanship": "骑术点", "Pars Life": "生命点", "Pars Radix": "根基点",
    "Pars Eros": "爱欲点", "Pars Necessity": "必然点", "Pars Courage": "勇气点", "Pars Victory": "胜利点", "Pars Nemesis": "报应点",
}
_CLS_ELEM = {"Fire": "火", "Earth": "土", "Air": "风", "Water": "水"}
_CLS_MODE = {"Cardinal": "始", "Fixed": "固", "Mutable": "变"}
_CLS_HEMI = {"east": "东", "west": "西", "above": "地平上", "below": "地平下"}
_CLS_TEMPER = {"Choleric": "胆汁(热干)", "Melancholic": "忧郁(冷干)", "Sanguine": "多血(热湿)", "Phlegmatic": "黏液(冷湿)"}
_CLS_QUAL = {"Hot": "热", "Cold": "冷", "Dry": "干", "Humid": "湿"}
_MELOTHESIA = {
    "aries": ["头", "脸", "眼", "鼻", "耳"], "taurus": ["喉", "颈", "甲状腺"],
    "gemini": ["手臂", "肩", "肺", "神经", "气管"], "cancer": ["胃", "胸", "子宫", "卵巢", "牙"],
    "leo": ["心脏", "脊椎", "背", "脊髓"], "virgo": ["小肠", "胰", "脾", "腹", "十二指肠"],
    "libra": ["下背", "肾", "静脉", "卵巢"], "scorpio": ["生殖", "排泄", "结肠", "膀胱", "摄护腺"],
    "sagittarius": ["大腿", "臀", "坐骨神经", "肝", "动脉"], "capricorn": ["膝", "关节", "胆囊", "头发", "皮肤"],
    "aquarius": ["小腿", "踝", "血液循环", "脊髓"], "pisces": ["脚掌", "淋巴"],
}


def _cls_msg(value: Any) -> str:
    # = frontend msg(id): short Chinese name for planet/sign/lot ids; falls back to the id text.
    return _astro_msg(value, short=True) or f"{value if value is not None else ''}"


def _cls_num(val: Any, digits: int) -> str:
    try:
        return f"{float(val):.{digits}f}"
    except (TypeError, ValueError):
        return ""


def _degree_position(signlon: Any) -> str:
    try:
        d = (float(signlon) % 30 + 30) % 30
    except (TypeError, ValueError):
        return ""
    return "上方" if d < 10 else ("中间" if d < 20 else "下方")


def _build_besiegement_lines(chart_response: dict[str, Any]) -> list[str]:
    surround = chart_response.get("surround") if isinstance(chart_response.get("surround"), dict) else {}
    besiegements = surround.get("besiegement") or []
    lines: list[str] = []
    for b in besiegements:
        if not isinstance(b, dict) or not isinstance(b.get("besiegers"), list):
            continue
        besiegers_txt = []
        for x in b["besiegers"]:
            if not isinstance(x, dict):
                continue
            s = f"{_cls_msg(x.get('id'))}（{_CLS_SEASON.get(x.get('season'), x.get('season'))}"
            if x.get("retro"):
                s += "·逆行"
            if x.get("restrained"):
                s += "·日木制约凶减半"
            if x.get("counterBesieged"):
                s += "·围魏救赵"
            besiegers_txt.append(f"{s}）")
        head = f"{_cls_msg(b.get('target'))}{'（逆行）' if b.get('targetRetro') else ''} 被 {' 与 '.join(besiegers_txt)} {b.get('kind')}（{b.get('nature')}）"
        if b.get("severe"):
            head += "·凶剧见血"
        lines.append(head)
        defense = b.get("defense") or []
        if defense:
            d = "，".join(
                f"{_cls_msg(y.get('id'))}（{'以身作盾' if y.get('byBody') else '遥光'}·护{_cls_msg(y.get('against')) if y.get('against') else y.get('side')}侧·{'强' if y.get('strong') else '弱'}）"
                for y in defense if isinstance(y, dict)
            )
            lines.append(f"协防：{d}")
        kind = b.get("kind")
        mean = _CLS_MEAN_ATK.get(b.get("target"), "") if kind == "围攻" else ("致富·舒适自由·财帛丰盈" if kind == "围荣" else "致贵·领袖魅力·载众载民")
        if mean:
            lines.append(f"断语：{mean}")
    return lines


def _build_encircle_lines(object_map: dict[str, Any]) -> list[str]:
    bodies = [object_map[i] for i in _CLS_STATUS_IDS if isinstance(object_map.get(i), dict) and isinstance(object_map[i].get("lon"), (int, float))]
    if len(bodies) < 3:
        return []
    sorted_b = sorted(bodies, key=lambda o: o["lon"])
    n = len(sorted_b)
    norm = lambda x: ((x % 360) + 360) % 360
    lines: list[str] = []
    for i in range(n):
        mid, left, right = sorted_b[i], sorted_b[(i - 1) % n], sorted_b[(i + 1) % n]
        span = norm(mid["lon"] - left["lon"]) + norm(right["lon"] - mid["lon"])
        if span < 90:
            lines.append(f"{_cls_msg(left.get('id'))} 与 {_cls_msg(right.get('id'))} 围绕 {_cls_msg(mid.get('id'))}（跨{span:.1f}°）")
    return lines


def _classical_object_map(chart_response: dict[str, Any]) -> dict[str, Any]:
    chart = chart_response.get("chart") if isinstance(chart_response.get("chart"), dict) else {}
    out: dict[str, Any] = {}
    for o in chart.get("objects") or []:
        if isinstance(o, dict) and o.get("id"):
            out[o["id"]] = o
    for o in chart_response.get("lots") or []:
        if isinstance(o, dict) and o.get("id"):
            out[o["id"]] = o
    return out


def _build_classical_section(chart_response: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    om = _classical_object_map(chart_response)
    profile: list[str] = []
    for pid in _CLS_STATUS_IDS:
        o = om.get(pid)
        if not isinstance(o, dict):
            continue
        parts: list[str] = []
        if o.get("outOfBounds"):
            mode = ("远行" if o.get("oobMode") == "going" else "回归") if (pid == "Moon" and o.get("oobMode")) else ""
            parts.append(f"出界+{_cls_num(o.get('oobDelta'), 2)}°{f'（{mode}）' if mode else ''}")
        if o.get("phase"):
            p = _CLS_PHASE.get(o["phase"], o["phase"])
            if o.get("phasisElong") is not None:
                p += f"（距日{_cls_num(o.get('phasisElong'), 1)}°）"
            if o.get("phasisEvent"):
                p += f"·{_CLS_PHASE_EVENT.get(o['phasisEvent'], o['phasisEvent'])}"
            parts.append(p)
        if o.get("joy"):
            parts.append(f"喜乐（{o.get('joyHouse')}宫）")
        if o.get("ofSect") is not None:
            parts.append("同宗" if o.get("ofSect") else "异宗")
        if o.get("feral"):
            parts.append("野逸")
        if o.get("degreeQuality"):
            parts.append(_CLS_QUALITY.get(o["degreeQuality"], f"{o['degreeQuality']}度"))
        if o.get("degreeGender"):
            parts.append("阳性度" if o["degreeGender"] == "masculine" else "阴性度")
        if isinstance(o.get("specialDegree"), dict):
            tags = [_CLS_SPECIAL.get(k, k) for k, v in o["specialDegree"].items() if v]
            if tags:
                parts.append("·".join(tags))
        if isinstance(o.get("mansion"), dict) and o["mansion"].get("cn"):
            parts.append(f"月站{o['mansion']['cn']}（{o['mansion'].get('nature')}）")
        if o.get("apogeeDir"):
            a = _CLS_APOGEE.get(o["apogeeDir"], o["apogeeDir"])
            if o.get("numberTrend"):
                a += f"·{_CLS_NUM.get(o['numberTrend'], '')}"
            if o.get("lightTrend"):
                a += f"·{_CLS_LIGHT.get(o['lightTrend'], '')}"
            parts.append(a)
        dl: list[str] = []
        if o.get("monomoiria"):
            dl.append(f"单度主星{_cls_msg(o['monomoiria'])}")
        if o.get("ninthPart"):
            dl.append(f"九分{_cls_msg(o['ninthPart'])}")
        if isinstance(o.get("dignities"), dict) and o["dignities"].get("face"):
            dl.append(f"面主{_cls_msg(o['dignities']['face'])}")
        if o.get("darijan"):
            dl.append(f"Darijan{_cls_msg(o['darijan'])}")
        if dl:
            parts.append("·".join(dl))
        if parts:
            profile.append(f"{_cls_msg(pid)}：{'；'.join(parts)}")
    if profile:
        lines.append("逐曜古典状态")
        lines.extend(profile)
    asc = om.get("Asc")
    if isinstance(asc, dict) and isinstance(asc.get("mansion"), dict) and asc["mansion"].get("cn"):
        m = asc["mansion"]
        lines.append(f"上升宿：{m['cn']}（{m.get('nature')} · {m.get('use')}）")
    bsg = _build_besiegement_lines(chart_response)
    if bsg:
        lines.append("围攻详断")
        lines.extend(bsg)
    enc = _build_encircle_lines(om)
    if enc:
        lines.append("围绕")
        lines.extend(enc)
    melo: list[str] = []
    for pid in _CLS_STATUS_IDS:
        o = om.get(pid)
        if not isinstance(o, dict) or not o.get("sign"):
            continue
        parts_m = _MELOTHESIA.get(str(o["sign"]).lower())
        if not parts_m:
            continue
        pos = _degree_position(o.get("signlon")) if o.get("signlon") is not None else ""
        melo.append(f"{_cls_msg(pid)}：{pos + '·' if pos else ''}{'、'.join(parts_m)}")
    if melo:
        lines.append("身体部位(Melothesia)")
        lines.extend(melo)
    return lines


def _build_classical_analysis_section(analysis: dict[str, Any]) -> list[str]:
    if not isinstance(analysis, dict):
        return []
    lines: list[str] = []
    cp = analysis.get("classicalPatterns") or {}
    dory = [f"{_cls_msg(d.get('planet'))} 护卫 {_cls_msg(d.get('light'))}（距{_round3(d.get('elong'))}°）" for d in (cp.get("doryphory") or []) if isinstance(d, dict)]
    over = [f"{_cls_msg(o.get('over'))}({_cls_msg(o.get('overSign'))}) 凌驾 {_cls_msg(o.get('under'))}({_cls_msg(o.get('underSign'))})·{_CLS_OVR_ASP.get(o.get('aspect'), o.get('aspect'))}" for o in (cp.get("overcoming") or []) if isinstance(o, dict)]
    bsgd = [f"{_cls_msg(b.get('planet'))} 被 {_cls_msg(b.get('left'))}/{_cls_msg(b.get('right'))} 度数围攻" for b in (cp.get("besieging") or []) if isinstance(b, dict)]
    if dory or over or bsgd:
        lines.append("古典格局")
        if dory:
            lines.append(f"护卫：{'；'.join(dory)}")
        if over:
            lines.append(f"优势相位：{'；'.join(over)}")
        if bsgd:
            lines.append(f"度数围攻：{'；'.join(bsgd)}")
    ad = analysis.get("aspectDynamics") or {}
    trans = [f"{_cls_msg(t.get('mover'))} 自 {_cls_msg(t.get('from'))} 传光予 {_cls_msg(t.get('to'))}" for t in (ad.get("translation") or []) if isinstance(t, dict)]
    coll = [f"{_cls_msg(c.get('collector'))} 聚 {_cls_msg(c.get('p1'))}、{_cls_msg(c.get('p2'))} 之光" for c in (ad.get("collection") or []) if isinstance(c, dict)]
    aver = [f"{_cls_msg(v.get('a'))} 与 {_cls_msg(v.get('b'))} 不合意" for v in (ad.get("aversion") or []) if isinstance(v, dict)]
    bend = [f"{_cls_msg(b.get('planet'))} 交点弯曲{f'（{b.get('at')}）' if b.get('at') else ''}" for b in (ad.get("bending") or []) if isinstance(b, dict)]
    # 连接学说后四式：空亡（指定星离座前不再成相）/ 阻止（更快之星先到截断入相）/ 挫败（受体移情致甲落空）/ 收回（趋留撤离）。
    voidc = [f"{_cls_msg(x.get('planet'))} 空亡（{'30°内' if x.get('mode') == 'classical' else '本座内'}不再成相）" for x in (ad.get("void") or []) if isinstance(x, dict)]
    prohib = [f"{_cls_msg(p.get('blocker'))} 阻止 {_cls_msg(p.get('between'))}→{_cls_msg(p.get('to'))} 入相" for p in (ad.get("prohibition") or []) if isinstance(p, dict)]
    frust = [f"{_cls_msg(x.get('frustrated'))} 挫败（{_cls_msg(x.get('via'))} 先成相 {_cls_msg(x.get('to'))}）" for x in (ad.get("frustration") or []) if isinstance(x, dict)]
    refran = [f"{_cls_msg(r.get('planet'))} 收回（趋留撤离 {_cls_msg(r.get('to'))}）" for r in (ad.get("refranation") or []) if isinstance(r, dict)]
    if trans or coll or aver or bend or voidc or prohib or frust or refran:
        lines.append("相位动态")
        if trans:
            lines.append(f"传光：{'；'.join(trans)}")
        if coll:
            lines.append(f"聚光：{'；'.join(coll)}")
        if aver:
            lines.append(f"不合意：{'；'.join(aver)}")
        if bend:
            lines.append(f"交点弯曲：{'；'.join(bend)}")
        if voidc:
            lines.append(f"空亡：{'；'.join(voidc)}")
        if prohib:
            lines.append(f"阻止：{'；'.join(prohib)}")
        if frust:
            lines.append(f"挫败：{'；'.join(frust)}")
        if refran:
            lines.append(f"收回：{'；'.join(refran)}")
    ta = [f"{t.get('topic')}（{t.get('house')}宫{('·自然象征' + _cls_msg(t.get('significator'))) if t.get('significator') else ''}）主星{_cls_msg(t.get('almuten'))}" for t in (analysis.get("topicAlmuten") or []) if isinstance(t, dict) and t.get("almuten")]
    if ta:
        lines.append("逐题主星")
        lines.append("；".join(ta))
    acc = [f"{_cls_msg(r.get('planet'))} {r.get('score')}（{'·'.join(r.get('factors') or [])}）" for r in (analysis.get("accidentalDignity") or []) if isinstance(r, dict) and r.get("planet")]
    if acc:
        lines.append("偶然尊贵")
        lines.extend(acc)
    fs = [f"{_cls_msg(s.get('point'))} 合 {s.get('cn') or s.get('star')}{'·比尼' if s.get('behenian') else ''}{('·王者' + str(s.get('royal'))) if s.get('royal') else ''}" for s in (analysis.get("fixedStarHits") or []) if isinstance(s, dict)]
    if fs:
        lines.append("恒星触发")
        lines.append("；".join(fs))
    ph = analysis.get("planetaryHours")
    if isinstance(ph, dict) and ph.get("dayRuler"):
        lines.append(f"行星时：值日星 {_cls_msg(ph.get('dayRuler'))}（日出 {ph.get('sunrise')} / 日落 {ph.get('sunset')}）")
        hours = ph.get("hours") if isinstance(ph.get("hours"), list) else []
        if hours:
            fmt = lambda h: f"{h.get('index') if h.get('diurnal') else (h.get('index', 0) - 12)}.{_cls_msg(h.get('ruler'))}{'←当前' if h.get('current') else ''}"
            day = [fmt(h) for h in hours if isinstance(h, dict) and h.get("diurnal")]
            night = [fmt(h) for h in hours if isinstance(h, dict) and not h.get("diurnal")]
            if day:
                lines.append(f"昼时：{' / '.join(day)}")
            if night:
                lines.append(f"夜时：{' / '.join(night)}")
    eg = analysis.get("egyptianCalendar")
    if isinstance(eg, dict) and (eg.get("siriusRising") or eg.get("decanIndex")):
        eparts: list[str] = []
        if eg.get("siriusRising"):
            eparts.append(f"天狼偕日升 {eg.get('siriusRising')}")
        if eg.get("siriusYear"):
            eparts.append(f"岁年 {eg.get('siriusYear')}")
        if eg.get("decanIndex"):
            eparts.append(f"上升第{eg.get('decanIndex')}旬（{_cls_msg(eg.get('decanSign'))}）面主{_cls_msg(eg.get('decanRuler'))}")
        if eparts:
            lines.append(f"埃及历：{'；'.join(eparts)}")
    bab = [f"{_cls_msg(b.get('planet'))} 合参照星 {b.get('cn') or b.get('star')}" for b in (analysis.get("babylonianStars") or []) if isinstance(b, dict) and b.get("conj")]
    if bab:
        lines.append("巴比伦参照星")
        lines.append("；".join(bab))
    pats = [f"{p.get('label') or p.get('type')}（{'·'.join(_cls_msg(x) for x in (p.get('points') or []))}{(',顶点' + _cls_msg(p.get('apex'))) if p.get('apex') else ''}）" for p in (analysis.get("patterns") or []) if isinstance(p, dict)]
    if pats:
        lines.append("相位格局")
        lines.append("；".join(pats))
    dist = analysis.get("distribution")
    if isinstance(dist, dict) and (dist.get("elements") or dist.get("modes") or dist.get("hemispheres")):
        kv = lambda obj, mp: " ".join(f"{mp.get(k, k)}{v}" for k, v in (obj or {}).items())
        dl2: list[str] = []
        if dist.get("elements"):
            dl2.append(f"元素 {kv(dist['elements'], _CLS_ELEM)}")
        if dist.get("modes"):
            dl2.append(f"模态 {kv(dist['modes'], _CLS_MODE)}")
        if dist.get("hemispheres"):
            dl2.append(f"半球 {kv(dist['hemispheres'], _CLS_HEMI)}")
        if dl2:
            lines.append("分布权重")
            lines.append("；".join(dl2))
    temp = analysis.get("temperament")
    if isinstance(temp, dict) and (temp.get("temperaments") or temp.get("qualities")):
        kv = lambda obj, mp: " ".join(f"{mp.get(k, k)}{v}" for k, v in (obj or {}).items())
        tl: list[str] = []
        if temp.get("temperaments"):
            tl.append(f"气质 {kv(temp['temperaments'], _CLS_TEMPER)}")
        if temp.get("qualities"):
            tl.append(f"性质 {kv(temp['qualities'], _CLS_QUAL)}")
        if tl:
            lines.append("气质评估")
            lines.append("；".join(tl))
    am = analysis.get("almutem")
    if isinstance(am, dict) and am.get("winner"):
        totals = sorted(((k, v) for k, v in (am.get("totals") or {}).items() if v and v > 0), key=lambda t: t[1], reverse=True)
        lines.append(f"Almuten 总主：{_cls_msg(am.get('winner'))}")
        if totals:
            lines.append("Almuten 逐星得分：")
            lines.extend(f"{_cls_msg(k)} {v}" for k, v in totals)
    bn = [b for b in (analysis.get("bonification") or []) if isinstance(b, dict) and b.get("planet") and ((b.get("bonified") or []) or (b.get("maltreated") or []))]
    if bn:
        lines.append("吉化/凶化")
        for b in bn:
            ok = "、".join(f"{_cls_msg(x.get('by'))}·{x.get('rel') or '会合'}" for x in (b.get("bonified") or []) if isinstance(x, dict))
            bad = "、".join(f"{_cls_msg(x.get('by'))}·{x.get('rel') or '会合'}" for x in (b.get("maltreated") or []) if isinstance(x, dict))
            segs = []
            if ok:
                segs.append(f"受惠[{ok}]")
            if bad:
                segs.append(f"受厄[{bad}]")
            lines.append(f"{_cls_msg(b.get('planet'))}：{'；'.join(segs)}")
    extra = [l for l in (analysis.get("extraLots") or []) if isinstance(l, dict) and l.get("label")]
    if extra:
        lines.append("阿拉伯点(扩展)")
        for l in extra[:60]:
            cn_label = _CLS_LOT_CN.get(l.get("label"), l.get("label"))
            cat = f"（{l.get('category')}）" if l.get("category") else ""
            if l.get("sign") and l.get("signlon") is not None:
                dg = _format_sign_degree(l.get("sign"), l.get("signlon"))
            elif l.get("lon") is not None:
                dg = _lon_to_sign_degree(l.get("lon"))
            elif l.get("sign"):
                dg = _cls_msg(l.get("sign"))
            else:
                dg = ""
            lines.append(f"{cn_label}{cat}：{dg or '-'}")
    return lines


# ── 格局速览 (pattern overview)：龙脉/孤月独明/先验权力/心性·智识/职业·行事/强吉木星/后天凶星 ──
# 纯派生自 /chart 活盘对象(objects: lon/lonspeed/sign/selfDignity/ruleHouses/house/feral/aboveHorizon)
# + isDiurnal + 北交 + mutuals/receptions/aspects.normalAsp 及主宰星链。供 [古典格局] 段尾「格局速览」子块。绝不抛(失败回空)。
_PO_TRAD_KEYS = ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn")
_PO_KEY_TO_ID = {"sun": "Sun", "moon": "Moon", "mercury": "Mercury", "venus": "Venus", "mars": "Mars", "jupiter": "Jupiter", "saturn": "Saturn"}
_PO_ID_TO_KEY = {v: k for k, v in _PO_KEY_TO_ID.items()}
_PO_SEVEN_IDS = ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn")
_PO_SIGN_DOMICILE = {
    "aries": "mars", "taurus": "venus", "gemini": "mercury", "cancer": "moon",
    "leo": "sun", "virgo": "mercury", "libra": "venus", "scorpio": "mars",
    "sagittarius": "jupiter", "capricorn": "saturn", "aquarius": "saturn", "pisces": "jupiter",
}
_PO_SIGN_MODALITY = {
    "aries": "cardinal", "cancer": "cardinal", "libra": "cardinal", "capricorn": "cardinal",
    "taurus": "fixed", "leo": "fixed", "scorpio": "fixed", "aquarius": "fixed",
    "gemini": "mutable", "virgo": "mutable", "sagittarius": "mutable", "pisces": "mutable",
}
_PO_MODALITY_CN = {"cardinal": "转宫", "fixed": "定宫", "mutable": "二体宫"}
_PO_MALEFIC_HOUSES = frozenset({6, 8, 12})
_PO_JUP_WEAK_HOUSES = frozenset({3, 6, 8, 12})


def _po_norm360(x: Any) -> float:
    try:
        return ((float(x) % 360.0) + 360.0) % 360.0
    except (TypeError, ValueError):
        return 0.0


def _po_house_num(h: Any) -> int | None:
    if isinstance(h, bool):
        return None
    if isinstance(h, (int, float)):
        return int(h)
    m = re.search(r"(\d+)", str(h if h is not None else ""))
    return int(m.group(1)) if m else None


def _po_sign_key(s: Any) -> str | None:
    return str(s).lower() if s else None


def _po_dign_token(sd: Any) -> str:
    if not isinstance(sd, list):
        return ""
    if "ruler" in sd:
        return "庙"
    if "exalt" in sd:
        return "旺"
    if "exile" in sd:
        return "陷"
    if "fall" in sd:
        return "落"
    return ""


def _po_compute_dispositors(objects: list[Any]) -> dict[str, Any]:
    # 七政各落座的本垣主，顺链至「落自家座」终极主宰或互容成环；返回 {step: key->本垣主key, loops: [环key数组]}。
    pos: dict[str, str | None] = {}
    for o in objects or []:
        if not isinstance(o, dict):
            continue
        key = _PO_ID_TO_KEY.get(o.get("id"))
        if key:
            pos[key] = _po_sign_key(o.get("sign"))
    step: dict[str, str] = {}
    for k in _PO_TRAD_KEYS:
        sign = pos.get(k)
        dom = _PO_SIGN_DOMICILE.get(sign) if sign else None
        if dom is not None:
            step[k] = dom
    loops: list[list[str]] = []
    for start in _PO_TRAD_KEYS:
        if start not in step:
            continue
        path: list[str] = []
        seen: set[str] = set()
        cur: str | None = start
        while cur is not None and cur in step:
            if cur in seen:
                loops.append(path[path.index(cur):])
                break
            seen.add(cur)
            path.append(cur)
            nxt = step[cur]
            if nxt == cur:
                break
            cur = nxt
    uniq: list[list[str]] = []
    seen_loop: set[str] = set()
    for c in loops:
        key = ">".join(sorted(c))
        if key not in seen_loop:
            seen_loop.add(key)
            uniq.append(c)
    return {"step": step, "loops": uniq}


def _po_pair_linked(id_a: Any, id_b: Any, response: dict[str, Any], by_id: dict[str, Any]) -> bool:
    def in_list(lst: Any) -> bool:
        for it in lst or []:
            if not isinstance(it, dict):
                continue
            x = it["planetA"].get("id") if isinstance(it.get("planetA"), dict) else it.get("beneficiary")
            y = it["planetB"].get("id") if isinstance(it.get("planetB"), dict) else it.get("supplier")
            if (x == id_a and y == id_b) or (x == id_b and y == id_a):
                return True
        return False
    m = response.get("mutuals") or {}
    r = response.get("receptions") or {}
    if in_list(m.get("normal")) or in_list(m.get("abnormal")) or in_list(r.get("normal")) or in_list(r.get("abnormal")):
        return True
    na = (response.get("aspects") or {}).get("normalAsp") if isinstance(response.get("aspects"), dict) else None
    row = na.get(id_a) if isinstance(na, dict) else None
    if isinstance(row, dict):
        for cat in ("Exact", "Applicative", "Separative"):
            for x in (row.get(cat) or []):
                if isinstance(x, dict) and x.get("id") == id_b:
                    try:
                        if int(x.get("asp")) == 0:
                            return True
                    except (TypeError, ValueError):
                        pass
    return False


def _pattern_overview(response: dict[str, Any]) -> dict[str, Any]:
    perchart = response.get("chart") if isinstance(response.get("chart"), dict) else {}
    objects = perchart.get("objects") if isinstance(perchart.get("objects"), list) else []
    if not objects:
        return {}
    by_id = {o.get("id"): o for o in objects if isinstance(o, dict) and o.get("id")}
    seven = [by_id[i] for i in _PO_SEVEN_IDS if i in by_id]
    is_day = bool(perchart.get("isDiurnal"))
    disp = _po_compute_dispositors(objects)

    def rule_houses(o: Any) -> list[int]:
        if not isinstance(o, dict):
            return []
        return [n for n in (_po_house_num(h) for h in (o.get("ruleHouses") or [])) if n is not None]

    def house_of(o: Any) -> int | None:
        return _po_house_num(o.get("house")) if isinstance(o, dict) else None

    def afflict_flags(o: Any) -> list[str]:
        f: list[str] = []
        if not isinstance(o, dict):
            return f
        try:
            if float(o.get("lonspeed") or 0) < 0:
                f.append("逆")
        except (TypeError, ValueError):
            pass
        if o.get("feral"):
            f.append("野逸")
        t = _po_dign_token(o.get("selfDignity"))
        if t in ("陷", "落"):
            f.append(t)
        return f

    # 龙截龙拥：北交黄经为轴分盘，统计 7 真星各半
    nn = by_id.get("North Node")
    if not nn or nn.get("lon") is None or len(seven) < 7:
        dragon: dict[str, Any] = {"has": False}
    else:
        axis = _po_norm360(nn.get("lon"))
        side_a: list[Any] = []
        side_b: list[Any] = []
        for o in seven:
            (side_a if _po_norm360((o.get("lon") or 0) - axis) < 180 else side_b).append(o)
        small = side_a if len(side_a) <= len(side_b) else side_b
        if len(small) == 0:
            dragon = {"has": True, "kind": "龙拥", "note": f"七星聚一侧（{'昼' if is_day else '夜'}限）"}
        elif len(small) == 1:
            lone = small[0]
            dragon = {"has": True, "kind": "龙截", "lone": lone.get("id"), "loneHouse": house_of(lone), "loneSign": lone.get("sign"), "loneRules": rule_houses(lone)}
        elif len(small) == 2 and _po_pair_linked(small[0].get("id"), small[1].get("id"), response, by_id):
            dragon = {"has": True, "kind": "龙截", "pair": [small[0].get("id"), small[1].get("id")], "note": "两星联结"}
        else:
            dragon = {"has": False}

    # 孤月独明：夜生且 7 星中唯月在地平上
    if is_day:
        lone_moon = {"has": False}
    else:
        def above(o: Any) -> bool:
            ah = o.get("aboveHorizon")
            if ah is not None:
                return bool(ah)
            h = house_of(o)
            return h is not None and 7 <= h <= 12
        above_list = [o for o in seven if above(o)]
        lone_moon = {"has": len(above_list) == 1 and above_list[0].get("id") == "Moon"}

    # 月水心性智识：座·模式·主宰星·主宰星资质·受损旗标
    def mm_one(planet_id: str) -> dict[str, Any] | None:
        o = by_id.get(planet_id)
        if not o:
            return None
        sign_k = _po_sign_key(o.get("sign"))
        modality = _PO_MODALITY_CN.get(_PO_SIGN_MODALITY.get(sign_k or "", ""), "")
        dk = disp["step"].get(_PO_ID_TO_KEY.get(planet_id, ""))
        disp_id = _PO_KEY_TO_ID.get(dk) if dk else None
        disp_obj = by_id.get(disp_id) if disp_id else None
        return {"sign": o.get("sign"), "modality": modality, "ruler": disp_id,
                "rulerDign": _po_dign_token(disp_obj.get("selfDignity")) if disp_obj else "", "flags": afflict_flags(o)}
    moon_mercury = {"moon": mm_one("Moon"), "mercury": mm_one("Mercury")}

    # 职业/行事(东升西没)：西没=黄经在前，取最近为第一
    def first_occidental(ref_id: str) -> str | None:
        ref = by_id.get(ref_id)
        if not ref:
            return None
        occ = sorted(
            ({"id": o.get("id"), "d": _po_norm360((o.get("lon") or 0) - (ref.get("lon") or 0))} for o in seven if o.get("id") != ref_id),
            key=lambda x: x["d"],
        )
        occ = [x for x in occ if 0 < x["d"] < 180]
        occ.sort(key=lambda x: x["d"])
        return occ[0]["id"] if occ else None

    def detail_of(pid: str | None) -> dict[str, Any] | None:
        o = by_id.get(pid) if pid else None
        if not o:
            return None
        return {"id": pid, "sign": o.get("sign"), "house": house_of(o)}
    vocation = {"career": detail_of(first_occidental("Moon")), "style": detail_of(first_occidental("Sun"))}

    # 强吉木星：不主 {3,6,8,12}(例外 ruleHouses=={6,9}) + 照耀星数(遵当前容许度 normalAsp)
    jup = by_id.get("Jupiter")
    if not jup:
        jupiter: dict[str, Any] = {"present": False}
    else:
        rh = rule_houses(jup)
        rh_set = set(rh)
        is69 = len(rh_set) == 2 and 6 in rh_set and 9 in rh_set
        strong = (not any(h in _PO_JUP_WEAK_HOUSES for h in rh)) or is69
        lit: list[str] = []
        na = (response.get("aspects") or {}).get("normalAsp") if isinstance(response.get("aspects"), dict) else None
        ja = na.get("Jupiter") if isinstance(na, dict) else None
        if isinstance(ja, dict):
            for cat in ("Exact", "Applicative", "Separative", "None"):
                for a in (ja.get(cat) or []):
                    aid = a.get("id") if isinstance(a, dict) else None
                    if aid in _PO_SEVEN_IDS and aid != "Jupiter" and aid not in lit:
                        lit.append(aid)
        jupiter = {"present": True, "strong": strong, "sign": jup.get("sign"),
                   "dign": _po_dign_token(jup.get("selfDignity")), "lit": lit, "litCount": len(lit)}

    # 后天凶星：主宰 6/8/12 者
    afflicted = [o.get("id") for o in seven if any(h in _PO_MALEFIC_HOUSES for h in rule_houses(o))]

    # 先验权力：8th 与 12th 或 8th 与 1th 之联结(接纳/互容/主宰环)；夜生 → 八杀朝天大贵
    def in_or_rules(o: Any, h: int) -> bool:
        if not o:
            return False
        return house_of(o) == h or h in rule_houses(o)

    def apriori_link(oa: Any, ob: Any) -> str | None:
        if not oa or not ob:
            return None
        if (in_or_rules(oa, 8) and in_or_rules(ob, 12)) or (in_or_rules(oa, 12) and in_or_rules(ob, 8)):
            return "8·12"
        if (in_or_rules(oa, 8) and in_or_rules(ob, 1)) or (in_or_rules(oa, 1) and in_or_rules(ob, 8)):
            return "8·1"
        return None
    apriori: dict[str, Any] = {"has": False, "links": []}

    def check_apriori(a_id: Any, b_id: Any, kind: str) -> None:
        w = apriori_link(by_id.get(a_id), by_id.get(b_id))
        if w:
            apriori["has"] = True
            apriori["links"].append({"a": a_id, "b": b_id, "which": w, "kind": kind})
    m = response.get("mutuals") or {}
    r = response.get("receptions") or {}
    for it in list(m.get("normal") or []) + list(m.get("abnormal") or []):
        if isinstance(it, dict):
            pa = it["planetA"].get("id") if isinstance(it.get("planetA"), dict) else None
            pb = it["planetB"].get("id") if isinstance(it.get("planetB"), dict) else None
            check_apriori(pa, pb, "互容")
    for it in list(r.get("normal") or []) + list(r.get("abnormal") or []):
        if isinstance(it, dict):
            check_apriori(it.get("beneficiary"), it.get("supplier"), "接纳")
    for lp in disp["loops"]:
        ids = [i for i in (_PO_KEY_TO_ID.get(k) for k in lp) if i]
        for x in range(len(ids)):
            for y in range(x + 1, len(ids)):
                check_apriori(ids[x], ids[y], "主宰环")
    apriori["eightKill"] = apriori["has"] and not is_day

    return {"dragon": dragon, "loneMoon": lone_moon, "moonMercury": moon_mercury,
            "vocation": vocation, "jupiter": jupiter, "afflictedRulers": afflicted, "apriori": apriori}


def _pattern_overview_lines(response: dict[str, Any]) -> list[str]:
    try:
        data = _pattern_overview(response)
    except Exception:  # noqa: BLE001 — 格局速览失败绝不连累整段，回空降级
        return []
    if not data:
        return []
    lines: list[str] = []
    d = data.get("dragon") or {}
    if d.get("has"):
        if d.get("kind") == "龙拥":
            lines.append(f"龙脉：龙拥（{d.get('note') or '七星聚一侧'}）")
        elif d.get("pair"):
            lines.append(f"龙脉：龙截 {''.join(_cls_msg(x) for x in d['pair'])}（两星联结）")
        else:
            rules = d.get("loneRules") or []
            house_suf = f"·{d.get('loneHouse')}宫" if d.get("loneHouse") else ""
            rules_suf = f"·主{'/'.join(str(h) for h in rules)}宫" if rules else ""
            lines.append(f"龙脉：龙截 {_cls_msg(d.get('lone'))}（{_cls_msg(d.get('loneSign'))}{house_suf}{rules_suf}）")
    if (data.get("loneMoon") or {}).get("has"):
        lines.append("孤月独明：是（夜生·唯月在地平上）")
    ap = data.get("apriori") or {}
    if ap.get("has"):
        link_txt = "、".join(f"{_cls_msg(lk['a'])}{lk['kind']}{_cls_msg(lk['b'])}({lk['which']})" for lk in (ap.get("links") or []))
        tail = "·夜生·八杀朝天大贵" if ap.get("eightKill") else "·昼生·非八杀朝天"
        lines.append(f"先验权力：{link_txt}{tail}")
    mm = data.get("moonMercury") or {}

    def one_mm(o: dict[str, Any] | None) -> str:
        if not o:
            return ""
        out = _cls_msg(o.get("sign"))
        if o.get("modality"):
            out += f"·{o['modality']}"
        if o.get("ruler"):
            out += f"·主{_cls_msg(o['ruler'])}{o.get('rulerDign') or ''}"
        if o.get("flags"):
            out += f"·{''.join(o['flags'])}"
        return out
    if mm.get("moon"):
        lines.append(f"心性(月)：{one_mm(mm['moon'])}")
    if mm.get("mercury"):
        lines.append(f"智识(水)：{one_mm(mm['mercury'])}")
    v = data.get("vocation") or {}
    for label, item in (("职业(月第一西没)", v.get("career")), ("行事(日第一西没)", v.get("style"))):
        if item:
            house_suf = f"·{item.get('house')}宫" if item.get("house") else ""
            lines.append(f"{label}：{_cls_msg(item.get('id'))} {_cls_msg(item.get('sign'))}{house_suf}")
    j = data.get("jupiter") or {}
    if j.get("present"):
        lit = j.get("lit") or []
        lit_txt = f"（{'、'.join(_cls_msg(x) for x in lit)}）" if lit else ""
        dign_suf = f"·{j['dign']}" if j.get("dign") else ""
        lines.append(f"木星：{'强吉' if j.get('strong') else '非强吉'}·{_cls_msg(j.get('sign'))}{dign_suf}·照耀{j.get('litCount')}星{lit_txt}")
    if data.get("afflictedRulers"):
        lines.append(f"后天凶星：{'、'.join(_cls_msg(x) for x in data['afflictedRulers'])}")
    return lines


# ── 印度律盘 Vimshottari 大运（120 年周期）：后端 jyotish.dasha.vimshottari 已算好，挂载 [大运Dasha] 段 ──
_DASHA_SYS_LABEL = {
    "vimshottari": "Vimshottari（120 年周期）",
    "yogini": "Yogini（36 年 · 8 女神）",
    "ashtottari": "Ashtottari（108 年 · Ardradi）",
    "tribhagi": "Tribhāgī（Vimśottarī÷3 · 3 遍×40=120 年）",
}


def _dasha_lord_name(lord: Any) -> str:
    return (lord.get("label") or lord.get("key") or "—") if isinstance(lord, dict) else "—"


def _dasha_fmt_date(d: Any) -> str:
    s = f"{d if d is not None else ''}"
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", s)
    return m.group(1) if m else (s or "—")


def _dasha_n1(x: Any) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _dasha_date_only(s: Any) -> Any:
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", f"{s if s is not None else ''}")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
    except ValueError:
        return None


def _build_vimshottari_dasha_lines(response: dict[str, Any]) -> list[str]:
    jy = response.get("jyotish")
    dasha_root = jy.get("dasha") if isinstance(jy, dict) else None
    v = dasha_root.get("vimshottari") if isinstance(dasha_root, dict) else None
    mahadashas = v.get("mahadashas") if isinstance(v, dict) else None
    if not isinstance(v, dict) or not v.get("available") or not isinstance(mahadashas, list) or not mahadashas:
        return []
    out: list[str] = []
    nak = v.get("moonNakshatra") or {}
    out.append(f"系统：{_DASHA_SYS_LABEL['vimshottari']}")
    out.append(f"月宿：{nak.get('label') or nak.get('name') or nak.get('key') or '—'}（宿主星 {_dasha_lord_name(v.get('firstLord'))}）")
    out.append(f"首运：已历 {_dasha_n1(v.get('firstElapsedYears')):.1f} 年、余 {_dasha_n1(v.get('firstBalanceYears')):.1f} 年")
    active = next((m for m in mahadashas if isinstance(m, dict) and m.get("active")), None)
    if active:
        out.append(f"当前大运（Mahadasha）：{_dasha_lord_name(active.get('lord'))}（{_dasha_fmt_date(active.get('start'))} → {_dasha_fmt_date(active.get('end'))}，{_dasha_n1(active.get('startAge')):.0f}–{_dasha_n1(active.get('endAge')):.0f} 岁）")
        antars = active.get("antardashas")
        if isinstance(antars, list) and antars:
            today = datetime.now().date()
            for srow in antars:
                if not isinstance(srow, dict):
                    continue
                st = _dasha_date_only(srow.get("start"))
                en = _dasha_date_only(srow.get("end"))
                if st and en and st <= today < en:
                    out.append(f"当前小运（Antardasha）：{_dasha_lord_name(srow.get('lord'))}（{_dasha_fmt_date(srow.get('start'))} → {_dasha_fmt_date(srow.get('end'))}）")
                    break
    out.append("大运序列：")
    for m in mahadashas:
        if not isinstance(m, dict):
            continue
        mark = "▶ " if m.get("active") else ("· " if m.get("birthBalance") else "  ")
        out.append(f"{mark}{_dasha_lord_name(m.get('lord'))} {_dasha_fmt_date(m.get('start'))} → {_dasha_fmt_date(m.get('end'))}（{_dasha_n1(m.get('years')):.1f} 年，{_dasha_n1(m.get('startAge')):.0f}–{_dasha_n1(m.get('endAge')):.0f} 岁）")
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 世俗盘子盘群：年度入宫盘之外，围绕定盘展开的新月/满月/日月食/地区盘/行星周期等子盘。
# 子盘时刻均由后端精算端点求得（prenatal_syzygy 朔望、eclipsedetail 食时长、greatconj/barbault
# 慢星周期、jieqi/year 四季入宫），再以入宫盘同制起 /chart；纯确定性、无 UI 依赖。静态释义块
# （世俗宫义/地理分野）采占星通行定则。食端点仅回全球食时长（食时长定则的关键量）不回极大时刻，
# 故日/月食段呈影响时长判词而非整轮盘，如实标注。
_MUNDANE_HOUSE_MEANINGS = [
    "1宫：国家整体、国民、国运气象与当年基调",
    "2宫：国库财政、货币、贸易收入、国家资产",
    "3宫：交通通讯、媒体舆论、邻国往来、基础教育",
    "4宫：土地农业、矿产、反对党、国土与气候",
    "5宫：出生率与青年、文体娱乐、股市投机、外交使节",
    "6宫：公共卫生、劳工军警、公务体系、疫病",
    "7宫：外交与盟约、对外战争、公开对手、国际关系",
    "8宫：国债与死亡率、税收、外资、危机与转型",
    "9宫：司法宗教、高等教育、长途外贸、国际法",
    "10宫：政府元首、执政威望、国家声誉与权力",
    "11宫：立法议会、执政盟友、国家愿景与社团",
    "12宫：隐患与敌谍、监狱医院、幕后势力、集体潜困",
]
_MUNDANE_PTOLEMAIC_ALLOCATION = [
    "白羊：不列颠、法兰西、日耳曼、叙利亚",
    "金牛：波斯、爱尔兰、塞浦路斯、小亚细亚",
    "双子：亚美尼亚、下埃及、比利时、北美西北",
    "巨蟹：北非、荷兰、苏格兰、东亚沿海",
    "狮子：意大利、法国南部、罗马、阿尔卑斯",
    "处女：希腊、两河、加勒比、瑞士",
    "天秤：奥地利、上埃及、里海、中亚",
    "天蝎：马格里布、挪威、巴伐利亚、摩洛哥",
    "射手：西班牙、匈牙利、阿拉伯、澳洲",
    "摩羯：印度、马其顿、墨西哥、阿富汗",
    "水瓶：俄罗斯、瑞典、阿拉伯半岛、低地欧洲",
    "双鱼：葡萄牙、埃及、诺曼底、地中海诸岛",
]


def _mundane_chart_digest(
    chart_response: dict[str, Any], *, points: tuple[str, ...] = ("Sun", "Moon", "Asc", "MC")
) -> list[str]:
    """子盘四轴/日月摘要：不铺全盘，仅取关键结构点，避免子盘群把导出撑爆。"""
    wrap = _top_level_chart_wrap(chart_response)
    om = _get_objects_map(wrap)
    lines: list[str] = []
    for pid in points:
        obj = om.get(pid)
        if isinstance(obj, dict) and obj.get("sign") is not None and obj.get("signlon") is not None:
            lines.append(
                f"{_astro_msg(pid, short=True)}："
                f"{_format_sign_degree(obj.get('sign'), obj.get('signlon'))}"
                f"{_format_retrograde_text(obj)}"
            )
    return lines


def _mundane_year_lord_lines(ingress_response: dict[str, Any]) -> list[str]:
    """定局·年主/盘主：上升座主（命主星）落点 + 二分二至发光体宫位定当年基调。"""
    wrap = _top_level_chart_wrap(ingress_response)
    om = _get_objects_map(wrap)
    asc = om.get("Asc")
    asc_sign = _po_sign_key(asc.get("sign")) if isinstance(asc, dict) else None
    if not asc_sign:
        return ["本盘缺上升信息，无法定盘主。"]
    modality_key = _PO_SIGN_MODALITY.get(asc_sign, "")
    modality = _PO_MODALITY_CN.get(modality_key, "")
    lines = [f"上升星座：{_astro_msg(asc.get('sign'))}{('（' + modality + '）') if modality else ''}"]
    # 定局定则（入宫图效力时长随上升宫性而定）：定宫全年一图；二体宫半年、秋分补图；转宫一季、逐季另起。
    validity = {
        "fixed": "定局：上升落定宫（固定宫）→ 本图效力全年。",
        "mutable": "定局：上升落二体宫（变动宫）→ 本图效力半年，需秋分补图。",
        "cardinal": "定局：上升落转宫（基本宫）→ 本图效力一季，逐季另起入宫图（参见[地区盘推运]四季序列）。",
    }.get(modality_key)
    if validity:
        lines.append(validity)
    ruler_key = _PO_SIGN_DOMICILE.get(asc_sign)
    ruler_id = _PO_KEY_TO_ID.get(ruler_key) if ruler_key else None
    if ruler_id:
        r = om.get(ruler_id)
        if isinstance(r, dict) and r.get("sign") is not None:
            house = _po_house_num(r.get("house"))
            house_txt = f"，落第 {house} 宫" if house else ""
            lines.append(
                f"盘主（命主星／年主）：{_astro_msg(ruler_id, short=True)} —— "
                f"{_format_sign_degree(r.get('sign'), r.get('signlon'))}{house_txt}"
            )
        else:
            lines.append(f"盘主（命主星／年主）：{_astro_msg(ruler_id, short=True)}")
    for lum in ("Sun", "Moon"):
        obj = om.get(lum)
        if isinstance(obj, dict) and obj.get("sign") is not None:
            house = _po_house_num(obj.get("house"))
            house_txt = f"（第 {house} 宫）" if house else ""
            lines.append(
                f"{_astro_msg(lum, short=True)}："
                f"{_format_sign_degree(obj.get('sign'), obj.get('signlon'))}{house_txt}"
            )
    return lines


def _mundane_skeleton_lines(ingress_response: dict[str, Any]) -> list[str]:
    """入境骨架：四轴星座 + 临角行星（±3°），入宫盘的结构应力点。"""
    wrap = _top_level_chart_wrap(ingress_response)
    om = _get_objects_map(wrap)
    lines: list[str] = []
    angle_lons: dict[str, float] = {}
    for pid in ("Asc", "MC", "Desc", "IC"):
        obj = om.get(pid)
        if isinstance(obj, dict) and obj.get("sign") is not None and obj.get("signlon") is not None:
            lines.append(f"{_astro_msg(pid, short=True)}：{_format_sign_degree(obj.get('sign'), obj.get('signlon'))}")
        if isinstance(obj, dict) and obj.get("lon") is not None:
            angle_lons[pid] = _po_norm360(obj.get("lon"))
    on_angle: list[str] = []
    for pkey in _PO_TRAD_KEYS:
        oid = _PO_KEY_TO_ID.get(pkey)
        obj = om.get(oid) if oid else None
        if not isinstance(obj, dict) or obj.get("lon") is None:
            continue
        plon = _po_norm360(obj.get("lon"))
        for ang, alon in angle_lons.items():
            diff = abs(plon - alon)
            diff = min(diff, 360.0 - diff)
            if diff <= 3.0:
                on_angle.append(f"{_astro_msg(oid, short=True)} 合 {_astro_msg(ang, short=True)}（{diff:.1f}°）")
                break
    if on_angle:
        lines.append("临角行星：" + "、".join(on_angle))
    return lines


def _build_astro_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    sections = [
        ("起盘信息", _build_base_info_lines(response, payload)),
        ("宫位宫头", _build_house_cusp_lines(response)),
        ("星与虚点", _build_star_and_lot_position_lines(response)),
        ("信息", _build_info_section(response, payload)),
        ("相位", _build_aspect_section(response)),
        ("行星", _build_planet_section(response)),
        ("月宿", _build_nakshatra_lines(response)),
        ("希腊点", _build_lots_section(response)),
    ]
    rendered = [(title, "\n".join(lines).strip()) for title, lines in sections if lines]
    # v2.4.0 本命增补: 12分度 / 主宰星链 / 寿命格局; v2.6.7 古典占星: 古典 / 古典格局.
    # 星阙顺序: …主宰星链, 古典, 古典格局, 寿命格局, 可能性 → 古典两段插在 主宰星链 与 寿命格局 之间.
    extras = response.get("_natalExtras") if isinstance(response.get("_natalExtras"), dict) else None
    if extras:
        for title in ("12分度", "主宰星链"):
            body = extras.get(title)
            if body and f"{body}".strip():
                rendered.append((title, f"{body}".strip()))
    classical = _build_classical_section(response)
    if classical:
        rendered.append(("古典", "\n".join(classical).strip()))
    classical_analysis = _build_classical_analysis_section(response.get("_classicalAnalysis") or {})
    # 格局速览 (龙脉/孤月独明/先验权力/…) 仅随 [古典格局] 段一并出 —— 即仅 _classicalAnalysis 已挂载的
    # chart 家族(astrochart/astrochart_like)；india/mundane 等无 [古典格局] preset 的盘不挂，避免 unknown 段。
    if response.get("_classicalAnalysis") is not None:
        pov = _pattern_overview_lines(response)
        if pov:
            classical_analysis = (classical_analysis or []) + ["格局速览"] + pov
    if classical_analysis:
        rendered.append(("古典格局", "\n".join(classical_analysis).strip()))
    if extras:
        body = extras.get("寿命格局")
        if body and f"{body}".strip():
            rendered.append(("寿命格局", f"{body}".strip()))
    possibility = _build_possibility_section(response)
    if possibility:
        rendered.append(("可能性", "\n".join(possibility).strip()))
    # 印度律盘专属：Vimshottari 大运（仅 india_chart 响应带 jyotish.dasha → 其余盘自然跳过）。
    dasha_lines = _build_vimshottari_dasha_lines(response)
    if dasha_lines:
        rendered.append(("大运Dasha", "\n".join(dasha_lines).strip()))
    return _render_snapshot_text(rendered)


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


# 以时起卦 (梅花易数): lines 未提供时按四柱干支 + 时辰确定性生成六爻，不同起卦时间 → 不同卦象。
_SIXYAO_DIZHI = "子丑寅卯辰巳午未申酉戌亥"
# 先天八卦数 → 自下而上三爻 (1=阳 0=阴): 乾1 兑2 离3 震4 巽5 坎6 艮7 坤8。
_SIXYAO_TRIGRAM = {1: (1, 1, 1), 2: (1, 1, 0), 3: (1, 0, 1), 4: (1, 0, 0),
                   5: (0, 1, 1), 6: (0, 1, 0), 7: (0, 0, 1), 8: (0, 0, 0)}
_SIXYAO_GODS = ("青龙", "朱雀", "勾陈", "腾蛇", "白虎", "玄武")
_SIXYAO_NAMES = ("初爻", "二爻", "三爻", "四爻", "五爻", "上爻")
# 日干起六神: 甲乙→青龙起, 丙丁→朱雀, 戊→勾陈, 己→腾蛇, 庚辛→白虎, 壬癸→玄武 (从初爻起，循环)。
_SIXYAO_GOD_START = {"甲": 0, "乙": 0, "丙": 1, "丁": 1, "戊": 2, "己": 3, "庚": 4, "辛": 4, "壬": 5, "癸": 5}


def _gz_zhi_index(gz: Any) -> int:
    """从干支字符串取地支序 (子1…亥12)；取不到返回 0。"""
    for ch in reversed(str(gz or "")):
        idx = _SIXYAO_DIZHI.find(ch)
        if idx >= 0:
            return idx + 1
    return 0


def _hour_zhi_index(time_str: Any) -> int:
    """从 HH:MM 取时辰地支序 (子1…亥12)；23/0 点皆子时。"""
    try:
        hour = int(str(time_str or "0").split(":")[0]) % 24
    except (ValueError, IndexError):
        hour = 0
    return ((hour + 1) // 2) % 12 + 1


def _time_based_gua_lines(nongli: dict[str, Any], payload: dict[str, Any]) -> list[dict[str, Any]]:
    """以时起卦: 上卦=(年支+月支+日支)%8，下卦=+时支后%8，动爻=同式%6 (余0取末)。
    卦码 = 下卦三爻(初二三) + 上卦三爻(四五上)。六神按日干起。"""
    base = (
        _gz_zhi_index(nongli.get("yearGanZi") or nongli.get("yearJieqi") or nongli.get("year"))
        + _gz_zhi_index(nongli.get("monthGanZi"))
        + _gz_zhi_index(nongli.get("dayGanZi"))
    )
    hour_zhi = _hour_zhi_index(payload.get("time") or nongli.get("time"))
    upper = base % 8 or 8
    lower = (base + hour_zhi) % 8 or 8
    moving = (base + hour_zhi) % 6 or 6
    yao = list(_SIXYAO_TRIGRAM[lower]) + list(_SIXYAO_TRIGRAM[upper])
    god0 = _SIXYAO_GOD_START.get(str(nongli.get("dayGanZi") or "")[:1], 0)
    return [
        {
            "value": yao[idx],
            "change": (idx + 1) == moving,
            "god": _SIXYAO_GODS[(god0 + idx) % 6],
            "name": _SIXYAO_NAMES[idx],
        }
        for idx in range(6)
    ]


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


# ── 汉堡学派 (Uranian) 中点盘核心：星阙 utils/uranianDial.js 的 Python 移植（纯函数）──
# 90° 盘：行星/三王/角点/TNP 折叠到 0–90°；行星图 A+B−C=D；映点 Spiegelpunkt；中点列表。
_DIAL_IDS = (
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
    "Uranus", "Neptune", "Pluto", "North Node", "South Node", "Asc", "MC",
)
_DIAL_PLANETS = ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto")
_DIAL_PERSONAL = {"Sun", "Moon", "Asc", "MC", "North Node", "South Node", "AriesPoint"}
_DIAL_URANIAN = {"Cupido", "Hades", "Zeus", "Kronos", "Apollon", "Admetos", "Vulcanus", "Poseidon"}


def _dial_norm360(x: float) -> float:
    return ((x % 360) + 360) % 360


def _dial_mid(a: float, b: float) -> float:
    m = _dial_norm360((a + b) / 2)
    if abs(m - _dial_norm360(a)) > 90:
        m = _dial_norm360(m + 180)
    return m


def _dial_sep(lon_a: float, lon_b: float, base: float) -> float:
    d = abs(_dial_norm360(lon_a - lon_b) % base)
    return min(d, base - d)


def _dial_antiscion(lon: float) -> float:
    return _dial_norm360(180 - lon)


def _dial_rank(has_personal: bool, has_tnp: bool) -> int:
    return 0 if has_personal else (1 if has_tnp else 2)


def _dial_points(objects: Any, tnp: Any) -> list[dict[str, Any]]:
    pts: list[dict[str, Any]] = []
    for obj in objects or []:
        if isinstance(obj, dict) and obj.get("id") in _DIAL_IDS:
            try:
                pts.append({"id": obj.get("id"), "lon": float(obj.get("lon"))})
            except (TypeError, ValueError):
                continue
    for item in tnp or []:
        if isinstance(item, dict) and item.get("lon") is not None:
            try:
                pts.append({"id": item.get("id"), "lon": float(item.get("lon"))})
            except (TypeError, ValueError):
                continue
    pts.append({"id": "AriesPoint", "lon": 0.0})
    return pts


def _dial_planetary_pictures(points: list[dict[str, Any]], base: float = 90.0, orb: float = 1.0, limit: int = 40) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    n = len(points)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            a, b = points[i], points[j]
            if not (a["id"] in _DIAL_PERSONAL or a["id"] in _DIAL_URANIAN or b["id"] in _DIAL_PERSONAL or b["id"] in _DIAL_URANIAN):
                continue  # 至少一锚点（个人点/TNP）
            for k in range(n):
                if k in (i, j):
                    continue
                c = points[k]
                lon = _dial_norm360(a["lon"] + b["lon"] - c["lon"])
                for m in range(n):
                    if m in (i, j, k):
                        continue
                    d = points[m]
                    sep = _dial_sep(lon, d["lon"], base)
                    if sep > orb:
                        continue
                    key = "|".join(sorted([str(a["id"]), str(b["id"])])) + f"|{c['id']}|{d['id']}"
                    if key in seen:
                        continue
                    seen.add(key)
                    ids = (a["id"], b["id"], c["id"], d["id"])
                    out.append({
                        "a": a["id"], "b": b["id"], "c": c["id"], "d": d["id"], "sep": sep,
                        "hp": any(x in _DIAL_PERSONAL for x in ids), "ht": any(x in _DIAL_URANIAN for x in ids),
                    })
    out.sort(key=lambda p: (_dial_rank(p["hp"], p["ht"]), p["sep"]))
    return out[:limit]


def _dial_midpoint_list(points: list[dict[str, Any]], base: float = 90.0) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    n = len(points)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = points[i], points[j]
            out.append({
                "a": a["id"], "b": b["id"], "lon": _dial_mid(a["lon"], b["lon"]),
                "hp": a["id"] in _DIAL_PERSONAL or b["id"] in _DIAL_PERSONAL,
                "ht": a["id"] in _DIAL_URANIAN or b["id"] in _DIAL_URANIAN,
            })
    out.sort(key=lambda p: (_dial_rank(p["hp"], p["ht"]), p["lon"]))
    return out


def _dial_spiegel(points: list[dict[str, Any]], base: float = 90.0, orb: float = 1.0) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    n = len(points)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = points[i], points[j]
            sep = _dial_sep(_dial_antiscion(a["lon"]), b["lon"], base)
            if sep > orb:
                continue
            out.append({
                "a": a["id"], "b": b["id"], "sep": sep,
                "hp": a["id"] in _DIAL_PERSONAL or b["id"] in _DIAL_PERSONAL,
                "ht": a["id"] in _DIAL_URANIAN or b["id"] in _DIAL_URANIAN,
            })
    out.sort(key=lambda p: (_dial_rank(p["hp"], p["ht"]), p["sep"]))
    return out


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
    tnp = germany_result.get("tnp", []) if isinstance(germany_result, dict) else []
    tnp_error = germany_result.get("tnpError") if isinstance(germany_result, dict) else None
    # 行星：十曜扁平位置。
    obj_by_id = {obj.get("id"): obj for obj in objects or [] if isinstance(obj, dict)}
    planet_lines: list[str] = []
    for pid in _DIAL_PLANETS:
        obj = obj_by_id.get(pid)
        if not isinstance(obj, dict):
            continue
        deg, minute = _split_degree(obj.get("signlon", obj.get("lon")))
        planet_lines.append(f"{_planet_label(pid)} {deg}˚{_msg(obj.get('sign'))}{minute}分")
    # TNP星体：8 颗汉堡虚星。
    tnp_lines: list[str] = []
    for item in tnp or []:
        if not isinstance(item, dict):
            continue
        deg, minute = _split_degree(item.get("signlon", item.get("lon")))
        tnp_lines.append(f"{_planet_label(item.get('id'))} {deg}˚{_msg(item.get('sign'))}{minute}分")
    if tnp_error:
        tnp_lines.append("（部分 TNP 历表不可用）")
    # 90°中点盘 / 行星图 / 映点 / 中点列表（base=90、orb=1 Witte 标准）。
    dial_points = _dial_points(objects, tnp)
    dial_factor_lines = [
        f"{_planet_label(p['id'])} = {(_dial_norm360(p['lon']) % 90):.2f}°"
        for p in sorted(dial_points, key=lambda q: _dial_norm360(q["lon"]) % 90)
        if p["id"] != "AriesPoint"
    ]
    picture_lines = [
        f"{_planet_label(p['a'])} + {_planet_label(p['b'])} − {_planet_label(p['c'])} = {_planet_label(p['d'])}（误差{p['sep']:.2f}°）"
        for p in _dial_planetary_pictures(dial_points)
    ]
    spiegel_lines = [f"{_planet_label(p['a'])} ⟷ {_planet_label(p['b'])}（误差{p['sep']:.2f}°）" for p in _dial_spiegel(dial_points)]
    mplist_lines = [f"{_planet_label(p['a'])} / {_planet_label(p['b'])} = {p['lon']:.2f}°" for p in _dial_midpoint_list(dial_points)[:120]]
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
            ("行星", "\n".join(planet_lines).strip() or "无"),
            ("中点", "\n".join(midpoint_lines).strip() or "暂无中点数据"),
            ("TNP星体", "\n".join(tnp_lines).strip() or "暂无 TNP 数据"),
            ("中点相位", "\n".join(aspect_lines).strip() or "暂无中点相位数据"),
            ("90°中点盘", "\n".join(dial_factor_lines).strip() or "暂无可折叠因子"),
            ("行星图", "\n".join(picture_lines).strip() or "暂无行星图"),
            ("映点", "\n".join(spiegel_lines).strip() or "暂无映点接触"),
            ("中点列表", "\n".join(mplist_lines).strip() or "暂无中点"),
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


def _build_harmonic_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    harmonic = response.get("harmonic", payload.get("harmonic", 9))
    positions = response.get("positions") or []
    conjunctions = response.get("conjunctions") or []
    pos_lines: list[str] = []
    for p in positions:
        if not isinstance(p, dict):
            continue
        deg, minute = _split_degree(p.get("signlon", p.get("lon")))
        natal_deg, natal_min = _split_degree(p.get("natalLon"))
        pos_lines.append(
            f"{_planet_label(p.get('id'))}：本命 {natal_deg}˚{natal_min}分 → 调波 {_astro_msg(p.get('sign'))} {deg}˚{minute}分"
        )
    conj_lines: list[str] = []
    for c in conjunctions:
        if not isinstance(c, dict):
            continue
        try:
            orb_text = f"{float(c.get('orb')):.2f}°"
        except (TypeError, ValueError):
            orb_text = f"{c.get('orb')}"
        conj_lines.append(f"{_planet_label(c.get('a'))} ☌ {_planet_label(c.get('b'))}（误差 {orb_text}）")
    return _render_snapshot_text(
        [
            (
                "起盘信息",
                "\n".join(
                    [
                        f"日期：{payload.get('date', '—')} {payload.get('time', '—')}",
                        f"时区：{payload.get('zone', '—')}",
                        f"经纬度：{payload.get('lon', '—')} {payload.get('lat', '—')}",
                        f"调波数：H{harmonic}",
                        f"容许度(orb)：{payload.get('orb', 2)}°",
                    ]
                ),
            ),
            ("调波位置", "\n".join(pos_lines).strip() or "无"),
            ("同频合相", "\n".join(conj_lines).strip() or "无"),
        ]
    )


def _build_agepoint_snapshot_text(response: dict[str, Any]) -> str:
    # Port of 星阙 AstroAgePoint.buildAgePointSnapshotText. response = {agepoint: {points: [...]}}.
    ap = response.get("agepoint") if isinstance(response.get("agepoint"), dict) else {}
    points = ap.get("points") if isinstance(ap.get("points"), list) else []
    if not points:
        # 无年龄推进点数据 = 该技法在本盘缺失（与 star阙 "挂载显示缺失" 一致）。
        return _render_snapshot_text([("年龄推进点（Age Point / Huber）", "（本盘无年龄推进点数据）")])
    lines = ["年龄点自上升点起，沿 Koch 宫顺行，每宫 6 年、72 年回归上升；落于本命星处（合相）为人生关键节点。"]
    key_ages = [p for p in points if isinstance(p, dict) and p.get("aspectTo")]
    if key_ages:
        lines.append("")
        lines.append("关键岁数（合本命）：" + "；".join(f"{p.get('age')}岁合{_astro_msg(p.get('aspectTo'))}" for p in key_ages))
    lines.append("")
    lines.append("| 年龄 | 落座 | 宫 | 合本命 |")
    lines.append("| --- | --- | --- | --- |")
    for p in points:
        if not isinstance(p, dict):
            continue
        signlon = p.get("signlon")
        sign = _astro_msg(p.get("sign")) + (f" {signlon}°" if signlon is not None else "")
        aspect_to = _astro_msg(p.get("aspectTo")) if p.get("aspectTo") else "—"
        lines.append(f"| {p.get('age')}岁 | {sign} | {p.get('house')}宫 | {aspect_to} |")
    return _render_snapshot_text([("年龄推进点（Age Point / Huber）", "\n".join(lines))])


def _build_distributions_snapshot_text(response: dict[str, Any]) -> str:
    # Port of 星阙 AstroDistributions.buildDistributionsSnapshotText. response = {dist: [...]}.
    rows = response.get("dist") if isinstance(response.get("dist"), list) else []
    if not rows:
        return _render_snapshot_text([("界推运（分配法 / Distributions）", "（本盘无界推运数据）")])
    lines = [
        "上升点经主限运动穿越各埃及界；分配星=界主星，参与星=该期间内上升点触及的行星。",
        "",
        "| 分配星 | 界(座) | 参与星 | 起 | 止 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        if not isinstance(row, dict):
            continue
        participants = row.get("participants") if isinstance(row.get("participants"), list) else []
        part = "、".join(_astro_msg(x) for x in participants) if participants else "—"
        lines.append(
            f"| {_astro_msg(row.get('distributor'))} | {_astro_msg(row.get('sign'))} | {part} | {row.get('startDate') or '-'} | {row.get('endDate') or '-'} |"
        )
    return _render_snapshot_text([("界推运（分配法 / Distributions）", "\n".join(lines))])


def _aspect_label(deg: Any) -> str:
    mapped = ASTRO_TEXT_MAP.get(f"Asp{deg}")
    return mapped if mapped else f"{deg}°"


def _fmt_num(value: Any, digits: int = 3) -> str:
    try:
        return f"{round(float(value), digits)}"
    except (TypeError, ValueError):
        return f"{value}" if value is not None else ""


_PROGRESSION_EVENT_POINTS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Asc", "MC"]


def _build_jaynesprog_snapshot_text(response: dict[str, Any]) -> str:
    # Port of 星阙 AstroJaynesProgressions.buildJaynesProgSnapshotText. response = {methods:[{method,parallels}]}.
    methods = response.get("methods") if isinstance(response.get("methods"), list) else []
    sec = next((m for m in methods if isinstance(m, dict) and m.get("method") == "secondary"), methods[0] if methods else None)
    parallels = sec.get("parallels") if isinstance(sec, dict) and isinstance(sec.get("parallels"), list) else []
    if not parallels:
        return _render_snapshot_text([("赤纬推运（Declination）", "（本盘无赤纬推运数据）")])
    type_label = {"parallel": "平行", "contraparallel": "反平行"}
    table = ["| 推运点 | 类型 | 本命点 | 误差 |", "| --- | --- | --- | --- |"]
    for p in parallels[:80]:
        if not isinstance(p, dict):
            continue
        table.append(f"| {_astro_msg(p.get('a'))} | {type_label.get(p.get('type'), p.get('type'))} | {_astro_msg(p.get('b'))} | {_fmt_num(p.get('orb'), 3)} |")
    return _render_snapshot_text([
        ("赤纬推运（Declination）", "赤纬推运：推运后看赤纬平行/反平行（下表为二次推运，截至目标日）。"),
        ("时段盘 赤纬平行/反平行", "\n".join(table)),
    ])


def _build_vedicprog_snapshot_text(response: dict[str, Any]) -> str:
    # Port of 星阙 AstroVedicProgressions.buildVedicProgSnapshotText. response = {methods:[{method,positions}]}.
    methods = response.get("methods") if isinstance(response.get("methods"), list) else []
    sec = next((m for m in methods if isinstance(m, dict) and m.get("method") == "secondary"), methods[0] if methods else None)
    positions = sec.get("positions") if isinstance(sec, dict) and isinstance(sec.get("positions"), list) else []
    rows = [p for p in positions if isinstance(p, dict) and p.get("id") in _PROGRESSION_EVENT_POINTS]
    if not rows:
        return _render_snapshot_text([("恒星推运（Vedic Sidereal）", "（本盘无恒星推运数据）")])
    lines = [
        "二次/三次/小限推运在恒星黄道（sidereal）下计算；下表为二次推运（截至目标日）。",
        "",
        "| 点 | 恒星推运位置 |",
        "| --- | --- |",
    ]
    for p in rows:
        deg, minute = _split_degree(p.get("signlon", p.get("lon")))
        lines.append(f"| {_astro_msg(p.get('id'))} | {_astro_msg(p.get('sign'))} {deg}˚{minute}分 |")
    return _render_snapshot_text([("恒星推运（Vedic Sidereal）", "\n".join(lines))])


def _build_planetaryarc_snapshot_text(response: dict[str, Any]) -> str:
    # Port of 星阙 AstroPlanetaryArc.formatArcSnapshot. response = {chart:{aspects:[{directId,objects:[{aspect,natalId,delta}]}]}}.
    chart = response.get("chart") if isinstance(response.get("chart"), dict) else {}
    aspects = chart.get("aspects") if isinstance(chart.get("aspects"), list) else []
    rows: list[str] = []
    for row in aspects:
        if not isinstance(row, dict):
            continue
        for o in row.get("objects") or []:
            if len(rows) >= 120 or not isinstance(o, dict):
                continue
            delta = o.get("delta")
            delta_text = f"{round(float(delta) * 1000) / 1000}" if isinstance(delta, (int, float)) else ""
            rows.append(f"| {_astro_msg(row.get('directId'))} | {_aspect_label(o.get('aspect'))} | {_astro_msg(o.get('natalId'))} | {delta_text} |")
    if not rows:
        return _render_snapshot_text([("行星弧（Planetary Arc）", "（本盘无行星弧数据）")])
    body = ["行星弧(默认月亮弧)：以所选天体的二次推运移动量为弧推进全盘，看向运星对本命的相位。", "", "| 向运星 | 相位 | 本命星 | 误差 |", "| --- | --- | --- | --- |"] + rows
    return _render_snapshot_text([("行星弧（Planetary Arc）", "\n".join(body))])


# 托勒密人生七阶 (Ports of Man) — fixed age bands, each ruled by a classical planet (= 星阙 PLANETARY_AGES).
_PLANETARY_AGES = [
    ("Moon", 0, 4), ("Mercury", 4, 14), ("Venus", 14, 22), ("Sun", 22, 41),
    ("Mars", 41, 56), ("Jupiter", 56, 68), ("Saturn", 68, None),
]


def _years_between(birth: str, as_of: str | None) -> float | None:
    # birth/as_of are "YYYY-MM-DD[ HH:MM:SS]"; returns fractional years, or None if unparseable / no as_of.
    if not birth or not as_of:
        return None
    import datetime as _dt

    def _parse(s: str) -> _dt.datetime | None:
        s = f"{s}".strip().replace("/", "-")
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return _dt.datetime.strptime(s, fmt)
            except ValueError:
                continue
        return None

    b, a = _parse(birth), _parse(as_of)
    if b is None or a is None:
        return None
    return (a - b).days / 365.2425


def _build_planetaryages_snapshot_text(response: dict[str, Any], as_of: str | None) -> str:
    # Port of 星阙 planetaryAges.buildPlanetaryAgesSnapshotText (reads the chart; pure JS → pure Python).
    chart = response.get("chart") if isinstance(response.get("chart"), dict) else {}
    params = response.get("params") if isinstance(response.get("params"), dict) else (chart.get("params") if isinstance(chart.get("params"), dict) else {})
    objects = chart.get("objects") if isinstance(chart.get("objects"), list) else []
    obj_by_id = {o.get("id"): o for o in objects if isinstance(o, dict)}
    cur_age = _years_between(params.get("birth", ""), as_of)
    lines = ["托勒密人生七阶：各年龄带由一颗古典行星主管，当前年龄所落之带为主运行星。"]
    if cur_age is not None:
        lines.append(f"当前年龄：约 {int(cur_age)} 岁")
    lines += ["", "| 年龄带 | 主管 | 本命落座 | 当前 |", "| --- | --- | --- | --- |"]
    for planet, frm, to in _PLANETARY_AGES:
        rng = f"{frm}+岁" if to is None else f"{frm}-{to}岁"
        active = cur_age is not None and cur_age >= frm and (to is None or cur_age < to)
        o = obj_by_id.get(planet)
        pos = "-"
        if isinstance(o, dict) and o.get("sign"):
            signlon = o.get("signlon")
            pos = _astro_msg(o.get("sign")) + (f" {int(signlon)}°" if signlon is not None else "")
        lines.append(f"| {rng} | {_astro_msg(planet)} | {pos} | {'●' if active else ''} |")
    return _render_snapshot_text([("行星年龄（Ages of Man）", "\n".join(lines))])


def _build_yearsystem129_snapshot_text(response: dict[str, Any]) -> str:
    # Port of 星阙 AstroYearSystem129.buildYearSystem129SnapshotText. The 129-year data is computed
    # server-side (perpredict.getYearSystem129) and carried in response.predictives.yearsystem129
    # whenever the chart is cast with predictive truthy.
    predictives = response.get("predictives") if isinstance(response.get("predictives"), dict) else {}
    data = predictives.get("yearsystem129") if isinstance(predictives.get("yearsystem129"), list) else []
    if not data:
        return _render_snapshot_text([("129年系统表格", "（本盘无 129 年系统数据）")])
    lines = [
        "七政各管其小年（土30木12火15日19金8水20月25 = 129 年一轮），按 sect 起始、含子限。（succession 序实验性，待校准）",
        "",
        "| 主限 | 子限 | 日期 |",
        "| --- | --- | --- |",
    ]
    for main in data:
        if not isinstance(main, dict):
            continue
        subs = main.get("subDirect") if isinstance(main.get("subDirect"), list) else []
        main_name = _astro_msg(main.get("mainDirect"))
        if not subs:
            lines.append(f"| {main_name} | - | - |")
            continue
        for sub in subs:
            if not isinstance(sub, dict):
                continue
            lines.append(f"| {main_name} | {_astro_msg(sub.get('subDirect'))} | {sub.get('date') or '-'} |")
    return _render_snapshot_text([("129年系统表格", "\n".join(lines))])


_PERSIAN_MOVERS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
_PERSIAN_ASPECTS = [0, 60, 90, 120, 180]
_PERSIAN_SIGN_ORDER = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]


def _persian_lon_of(obj: dict[str, Any] | None) -> float | None:
    if not isinstance(obj, dict):
        return None
    lon = obj.get("lon")
    if lon is not None:
        try:
            return float(lon)
        except (TypeError, ValueError):
            return None
    sign = obj.get("sign")
    signlon = obj.get("signlon")
    if sign in _PERSIAN_SIGN_ORDER and signlon is not None:
        try:
            return _PERSIAN_SIGN_ORDER.index(sign) * 30 + float(signlon)
        except (TypeError, ValueError):
            return None
    return None


def _build_persiandirected_snapshot_text(response: dict[str, Any]) -> str:
    # Port of 星阙 AstroPersianDirected.buildPersianHits + buildPersianDirectedSnapshotText (pure arithmetic):
    # symbolic 1°/year direction — every planet/point advances +1° per year, natal cusps fixed; list the hits.
    import datetime as _dt

    chart = response.get("chart") if isinstance(response.get("chart"), dict) else {}
    params = response.get("params") if isinstance(response.get("params"), dict) else {}
    objects = chart.get("objects") if isinstance(chart.get("objects"), list) else []
    houses = chart.get("houses") if isinstance(chart.get("houses"), list) else []
    rate, cap = 1.0, 90  # persian rate 1°/年, direct, maxAge 90

    by_id: dict[str, float] = {}
    for o in objects:
        if isinstance(o, dict):
            lon = _persian_lon_of(o)
            if lon is not None:
                by_id[o.get("id")] = lon % 360
    targets: list[tuple[str, float]] = [(oid, lon) for oid, lon in by_id.items()]
    for i, h in enumerate(houses):
        lon = _persian_lon_of(h)
        if lon is not None:
            targets.append((f"{i + 1}宫头", lon % 360))

    birth_raw = f"{params.get('birth', '')}".strip().replace("/", "-")
    birth_dt = None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            birth_dt = _dt.datetime.strptime(birth_raw, fmt)
            break
        except ValueError:
            continue

    hits: list[dict[str, Any]] = []
    for p in _PERSIAN_MOVERS:
        pl = by_id.get(p)
        if pl is None:
            continue
        for tid, tlon in targets:
            if tid == p:
                continue
            for a in _PERSIAN_ASPECTS:
                for s in (1, -1):
                    if a in (0, 180) and s == -1:
                        continue
                    target = (tlon + s * a) % 360
                    arc = (target - pl) % 360
                    age = arc / rate
                    if 0 < age <= cap:
                        date = ""
                        if birth_dt is not None:
                            # NOTE: 星阙 dates this via moment `birth.add(age*365.2421904, 'days')`, which
                            # TRUNCATES the fractional day; our full-precision timedelta + JS-vs-Python
                            # floating-point in `arc` make the 应期 DATE differ from 星阙 by ≤1 day on
                            # ~40% of rows (the ages/aspects/targets are byte-identical). For 应期 this is
                            # astrologically negligible; see docs/v091-fidelity-spotcheck.md.
                            date = (birth_dt + _dt.timedelta(days=age * 365.2421904)).strftime("%Y-%m-%d")
                        hits.append({"age": round(age * 100) / 100, "promittor": p, "aspect": a, "significator": tid, "date": date})
    hits.sort(key=lambda h: h["age"])
    if not hits:
        return _render_snapshot_text([("波斯向运（Persian Directed）", "（本盘无波斯向运应期）")])
    lines = [
        "黄经象征向运(1°/年)：所有行星/点每年 +1°,本命宫头不动；下表为向运星触及本命的应期。",
        "",
        "| 年龄 | 日期 | 向运星 | 相位 | 本命对象 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for h in hits[:120]:
        sig = h["significator"]
        sig_name = sig if "宫头" in f"{sig}" else _astro_msg(sig)
        lines.append(f"| {h['age']} | {h['date'] or '-'} | {_astro_msg(h['promittor'])} | {_aspect_label(h['aspect'])} | {sig_name} |")
    return _render_snapshot_text([("波斯向运（Persian Directed）", "\n".join(lines))])


_SHENSHU_ENDPOINTS = {
    # 5 standalone engines
    "wangji": "/wangji/pan",
    "wuzhao": "/wuzhao/pan",
    "taixuan": "/taixuan/pan",
    "jingjue": "/jingjue/pan",
    "shenyishu": "/shenyishu/pan",
    # 9 kinastro-* engines (shared kinastro engine)
    "shaozi": "/shaozi/pan",
    "tieban": "/tieban/pan",
    "fendjing": "/fendjing/pan",
    "beiji": "/beiji/pan",
    "nanji": "/nanji/pan",
    "chunzi": "/chunzi/pan",
    "xianqin": "/xianqin/pan",
    "cetian": "/cetian/pan",
    "qizhengkin": "/qizhengkin/pan",
}


def _split_birth_ymdhm(payload: dict[str, Any]) -> dict[str, int]:
    # 神数 engines take split year/month/day/hour/minute (ganzhi-based). Derive from date "YYYY-MM-DD"/
    # "YYYY/MM/DD" (+ optional time "HH:MM[:SS]"). Raises ToolValidationError on an unparseable date
    # rather than silently substituting a default (which would compute a chart for the wrong moment).
    date_raw = f"{payload.get('date', '')}".strip().replace("/", "-")
    time_raw = f"{payload.get('time', '')}".strip()
    combined = f"{date_raw} {time_raw}".strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(combined if "%H" in fmt else date_raw, fmt)
            return {"year": dt.year, "month": dt.month, "day": dt.day, "hour": dt.hour, "minute": dt.minute}
        except ValueError:
            continue
    raise ToolValidationError(
        f"无法解析神数起盘日期/时间：date={payload.get('date')!r} time={payload.get('time')!r}。"
        "请提供公历日期（YYYY-MM-DD，可含 HH:MM[:SS] 时间）。",
        code="tool.shenshu_bad_date",
        details={"date": payload.get("date"), "time": payload.get("time")},
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


# ── 天文地占 (astronomical geomancy)：4 母卦→16 图形 + 十二宫图形入宫 + 判官/见证/解读技法。port GeomancyMain.buildGeomancySnapshotText ──
_GEO_TRAD = {"european_classical": "古典定局派", "european_planetary": "行星共鸣派", "european_modern": "现代综合派", "arabic_raml": "阿拉伯沙占派", "india_ramal": "印度骰占派", "sikidy": "异或表盘", "hakata": "四片盘"}
_GEO_PERF = {"occupation": "入主成局", "conjunction": "会合成局", "mutation": "互变成局", "translation": "传递成局", "none": "未成局"}
_GEO_ASP = {"conjunction": "合", "sextile": "六分(吉)", "square": "刑(凶)", "trine": "拱(吉)", "opposition": "冲", "none": "无相位"}
_GEO_SLOT = ["母一", "母二", "母三", "母四", "女一", "女二", "女三", "女四", "甥一", "甥二", "甥三", "甥四", "右证", "左证", "判官", "调和"]


def _geo_figure_line(fig: Any, role: str) -> str:
    if not isinstance(fig, dict):
        return ""
    parts = [p for p in [fig.get("nameZh") or fig.get("nameEn")] if p]
    if fig.get("planetZh"):
        parts.append(f"行星{fig['planetZh']}")
    if fig.get("elementZh"):
        parts.append(fig["elementZh"])
    if fig.get("keywordsZh"):
        parts.append(fig["keywordsZh"])
    return f"{role}：{' · '.join(parts)}" if parts else ""


def _build_geomancy_snapshot_text(response: dict[str, Any]) -> str:
    reading = response.get("reading") if isinstance(response.get("reading"), dict) else {}
    info = [
        f"问题：{reading.get('question') or '—'}",
        f"问类：{reading.get('questionTypeZh') or reading.get('questionType') or '—'}",
        f"上升图形：{(reading.get('ascendantFigure') or {}).get('nameZh') or ''}（上升星座 {reading.get('ascendantSignZh') or ''}）",
    ]
    tb: list[str] = []
    if reading.get("profileId") and reading.get("profileId") != "european_classical":
        tb.append(f"流派={_GEO_TRAD.get(reading['profileId'], reading['profileId'])}")
    if reading.get("zodiacSystem") == "planetary":
        tb.append("黄道=行星归属体系")
    if reading.get("readingScope") and reading.get("readingScope") != "L3":
        tb.append(f"范围={reading['readingScope']}")
    if tb:
        info.append(f"传本设置：{'、'.join(tb)}")
    judge: list[str] = []
    for fig, role in ((reading.get("judge"), "判官"), (reading.get("reconciler"), "调和者"), (reading.get("rightWitness"), "右证(过去/问者)"), (reading.get("leftWitness"), "左证(现在/所问)")):
        ln = _geo_figure_line(fig, role)
        if ln:
            judge.append(ln)
    if reading.get("primaryHouse"):
        judge.append(f"主宫：第 {reading['primaryHouse']} 宫")
    tech: list[str] = []
    t = reading.get("technique")
    if isinstance(t, dict):
        perf = t.get("perfection")
        if perf and perf != "none":
            tech.append(f"完美：{_GEO_PERF.get(perf, perf)}")
        elif t.get("perfection_by_aspect"):
            tech.append(f"完美：借相位({_GEO_ASP.get(t['perfection_by_aspect'], t['perfection_by_aspect'])})成局")
        else:
            tech.append("完美：未成局")
        tech.append(f"相位：{_GEO_ASP.get(t.get('aspect'), t.get('aspect'))}")
        if t.get("prohibition"):
            tech.append(f"阻碍：第 {t['prohibition']} 宫强凶图阻断")
        pp = t.get("points_parity")
        if isinstance(pp, dict):
            tech.append(f"点数是否：总 {pp.get('total')} 点·{'偶→是/稳' if pp.get('parity') == 'even' else '奇→否/动'}")
        tm = t.get("timing")
        if isinstance(tm, dict):
            tech.append(f"应期：{'速' if tm.get('speed') == 'fast' else '迟'}·以「{tm.get('unit')}」计")
        vp = t.get("via_puncti")
        if isinstance(vp, dict):
            tech.append(f"点之路：{'贯通' if vp.get('through') else '断于' + str(vp.get('broken_at'))}")
        if t.get("natural_cosignificator"):
            tech.append("自然共主：月亮")
    house_lines: list[str] = []
    for h in (reading.get("houses") or []):
        if not isinstance(h, dict):
            continue
        fig = h.get("figure") or {}
        roles = h.get("roles") or []
        role = "【所问】" if "quesited" in roles else ("【问者】" if "querent" in roles else "")
        reading_note = f" — {h['reading']}" if h.get("reading") else ""
        house_lines.append(f"第{h.get('house')}宫({h.get('nameZh') or ''}){role}：{fig.get('nameZh') or fig.get('nameEn') or ''}{reading_note}")
    fig_lines: list[str] = []
    for i, f in enumerate(reading.get("figures16") or []):
        if not isinstance(f, dict):
            continue
        slot = _GEO_SLOT[i] if i < len(_GEO_SLOT) else f"图{i + 1}"
        elem = f"·{f['elementZh']}" if f.get("elementZh") else ""
        fig_lines.append(f"{slot}：{f.get('nameZh') or f.get('nameEn')}（{f.get('planetZh') or ''}{elem}）")
    sections: list[tuple[str, str]] = [("起卦信息", "\n".join(info).strip())]
    if judge:
        sections.append(("判定", "\n".join(judge).strip()))
    if tech:
        sections.append(("解读技法", "\n".join(tech).strip()))
    if house_lines:
        sections.append(("十二宫·图形入宫", "\n".join(house_lines).strip()))
    if fig_lines:
        sections.append(("十六图形", "\n".join(fig_lines).strip()))
    return _render_snapshot_text(sections)


def _build_sixyao_snapshot_text(payload: dict[str, Any], nongli: dict[str, Any], current_code: str, changed_code: str, lines: list[dict[str, Any]], descs: dict[str, Any], struct_text: str = "") -> str:
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
    sections: list[tuple[str, str]] = [
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
    ]
    # 断卦结构（六爻全流派）：由 core-js analyzeLiuyao 引擎派生（纳甲/世应/六亲/用神/旺衰/飞伏/六神/动变）。
    # struct_text 以 "[断卦结构]" 段头开头 → 去头留正文（_render_snapshot_text 会补回 [标题]）；失败/无 node 时为空则不出该段。
    struct_body = (struct_text or "").strip()
    if struct_body.startswith("[断卦结构]"):
        struct_body = struct_body[len("[断卦结构]"):].lstrip("\n")
    if struct_body:
        sections.append(("断卦结构", struct_body))
    sections.append(("卦辞与断语", "\n".join(judge_lines).strip() or "无"))
    return _render_snapshot_text(sections)


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
        rendered.append((title, _join_lines(body_lines) or _missing_detail_text(title)))
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
            else _missing_detail_text("影响图盘-星盘A"),
        )
    )
    rendered.append(
        (
            "影响图盘-星盘B",
            embedded_chart_text(response["outer"])
            if isinstance(response.get("outer"), dict) and isinstance(response["outer"].get("chart"), dict)
            else _missing_detail_text("影响图盘-星盘B"),
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
    # 星阙 v2.6.x aiExport splits 大运 (the luck-period steps) from 流年行运概略 (the per-大运 年运 detail);
    # the skill mirrors that split (起运/性别 缺失时 direction 为空 → 大运段不出, 故列为可选段).
    dayun_lines: list[str] = []
    liunian_lines: list[str] = []
    for idx, item in enumerate(bazi.get("mainDirection") or [], start=1):
        if isinstance(item, dict):
            dayun_lines.append(f"第{idx}步：{item.get('year', '—')} {_gz_text(item)}")
    for block in bazi.get("direction") or []:
        if not isinstance(block, dict):
            continue
        main_gz = _gz_text(block.get("mainDirect"))
        dayun_lines.append(f"大运：{main_gz} 起于{block.get('startYear', '—')}年")
        subs = []
        for sub in block.get("subDirect") or []:
            if isinstance(sub, dict):
                subs.append(f"{sub.get('date', '—')} {_gz_text(sub)}")
        if subs:
            liunian_lines.append(f"{main_gz}大运 流年：" + "；".join(subs))
    sections: list[tuple[str, str]] = [
        ("起盘信息", _join_lines(base_lines)),
        ("四柱与三元", _join_lines(four_lines)),
        ("神煞（四柱与三元）", _join_lines(god_lines)),
    ]
    # 八字格局（五行力量/格局·用神/盲派结构/月令司令）：core-js baziGeju 引擎（_attach_bazi_geju 挂载）
    # 从后端 fourColumns 派生，插于 神煞 与 大运 之间；无 node/引擎失败则 _baziGeju 缺 → 该批段不出。
    geju_text = response.get("_baziGeju") if isinstance(response.get("_baziGeju"), str) else ""
    for block in (geju_text or "").split("\n\n"):
        block = block.strip()
        if not block.startswith("["):
            continue
        blk_lines = block.splitlines()
        geju_title = blk_lines[0].strip().lstrip("[").rstrip("]")
        geju_body = "\n".join(blk_lines[1:]).strip()
        if geju_title and geju_body:
            sections.append((geju_title, geju_body))
    if dayun_lines:
        sections.append(("大运", _join_lines(dayun_lines)))
    sections.append(
        (
            "流年行运概略",
            _join_lines(liunian_lines)
            or "本次八字结果未返回大运/流年明细；如问题涉及阶段走势，请优先使用 bazi_direct 或补齐性别、起运与节气设置后重算，不能臆造外部依赖。",
        )
    )
    return _render_snapshot_text(sections)


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


def _ziwei_star_names(value: Any) -> list[str]:
    names: list[str] = []
    if isinstance(value, list):
        for item in value:
            text = _msg(item.get("name") or item.get("id")) if isinstance(item, dict) else _msg(item)
            if text:
                # 四化标注（紫微 P1 流派四化随 jar）：星体若带 sihua 化象，附「(化X)」。
                hua = item.get("sihua") or item.get("hua") if isinstance(item, dict) else None
                names.append(f"{text}（化{_msg(hua)}）" if hua else text)
    return names


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
    # 命主/身主/五行局/斗君/年命（星阙 P0 杂曜与全盘信息一并落盘）。
    extra = [
        ("命主", chart.get("lifeMaster")),
        ("身主", chart.get("bodyMaster")),
        ("五行局", chart.get("wuxingJuText") or chart.get("wuxingJu")),
        ("斗君", chart.get("doujun")),
        ("子斗", chart.get("zidou")),
        ("年命", f"{_msg(chart.get('yearGan'))}{_msg(chart.get('yearZi'))}".strip() or None),
    ]
    for label, val in extra:
        text = _msg(val)
        if text:
            lines.append(f"{label}：{text}")

    overview: list[str] = []
    for index, house in enumerate(houses or [], start=1):
        if not isinstance(house, dict):
            continue
        name = house.get("name") or house.get("id") or f"宫位{index}"
        ganzi = _msg(house.get("ganzi")) or "无"
        direction = house.get("direction")
        direction_text = f"{direction[0]}~{direction[1]}" if isinstance(direction, list) and len(direction) == 2 else "无"
        # 主星 / 辅星 / 煞星 / 杂曜 (星阙 P0：杂曜补显 OthersGood/OthersBad/Small)，分类列出。
        main = _ziwei_star_names(house.get("starsMain"))
        assist = _ziwei_star_names(house.get("starsAssist"))
        evil = _ziwei_star_names(house.get("starsEvil"))
        misc = _ziwei_star_names(house.get("starsOthersGood")) + _ziwei_star_names(house.get("starsOthersBad")) + _ziwei_star_names(house.get("starsSmall"))
        small_dir = house.get("smallDirection")
        small_text = "、".join(str(a) for a in small_dir) if isinstance(small_dir, list) else _msg(small_dir)
        overview.append(f"{name}（干支={ganzi}，大限={direction_text}{('，小限=' + small_text) if small_text else ''}）")
        overview.append(f"主星：{'、'.join(main) or '无'}；辅星：{'、'.join(assist) or '无'}")
        overview.append(f"煞星：{'、'.join(evil) or '无'}；杂曜：{'、'.join(misc) or '无'}")
        overview.append("")

    # 命中格局（星阙 P2：格局随流派四化 + 新增格局/天伤天使安星，由 jar 返回 response.patterns）。
    patterns = response.get("patterns")
    pattern_lines: list[str] = []
    if isinstance(patterns, list):
        for pat in patterns:
            if not isinstance(pat, dict):
                continue
            pname = _msg(pat.get("name"))
            if not pname:
                continue
            cat = _msg(pat.get("category"))
            broke = "（破格）" if pat.get("broken") else ""
            duan = _msg(pat.get("duanyi"))
            head = f"{pname}（{cat}）{broke}" if cat else f"{pname}{broke}"
            pattern_lines.append(f"{head}：{duan}" if duan else head)

    blocks = [
        ("起盘信息", _join_lines(lines)),
        ("宫位总览", _join_lines(overview) or "无"),
        ("命中格局", _join_lines(pattern_lines) or "无"),
    ]
    return _render_snapshot_text(blocks)


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
    key_aliases = {
        "十二盘式": ("panStyle", "panStyleName", "pan_style"),
        "十二地盘/十二天盘/十二贵神对应": ("layout", "pan", "twelvePan"),
        "四课": ("keText", "ke", "fourLessons", "fourLesson", "sike", "courses"),
        "三传": ("sanChuan", "sanchuan", "threeTransmissions", "threeTransmission", "transmissions"),
    }
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
            body = ""
            if isinstance(liureng, dict):
                for candidate_key in key_aliases.get(title, (key,)):
                    body = _stringify_export_body(liureng.get(candidate_key))
                    if body:
                        break
            if not body and isinstance(response, dict):
                for candidate_key in key_aliases.get(title, (key,)):
                    body = _stringify_export_body(response.get(candidate_key))
                    if body:
                        break
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
            ("六爻与动爻", "此工具为卦义查询，不包含起卦六爻与动爻排盘；如需完整六爻盘，请调用 sixyao。"),
            (
                "卦辞与断语",
                _join_lines(desc_lines)
                or "本次卦义查询未返回卦辞断语；请基于已返回卦象说明，不能臆造不存在的数据来源。",
            ),
        ]
    )


def _predictive_chart_label(tool_name: str) -> str:
    return {
        "solarreturn": "返照盘",
        "lunarreturn": "返照盘",
        "givenyear": "流年盘",
        "solararc": "推运盘",
        "profection": "推运盘",
    }.get(tool_name, "推运盘")


def _predictive_chart_wrap(response: dict[str, Any]) -> dict[str, Any]:
    return (
        _chart_wrap_from_response(response, "dirChart")
        or _top_level_chart_wrap(response)
    )


def _natal_chart_wrap(response: dict[str, Any]) -> dict[str, Any]:
    return (
        _chart_wrap_from_response(response, "natalChart")
        or _chart_wrap_from_response(response, "birthChart")
        or _chart_wrap_from_response(response, "baseChart")
    )


def _build_predictive_snapshot_text(tool_name: str, payload: dict[str, Any], response: dict[str, Any]) -> str:
    natal_wrap = _natal_chart_wrap(response)
    predictive_wrap = _predictive_chart_wrap(response)
    chart_label = _predictive_chart_label(tool_name)
    predictive_params = response.get("dirParams") if isinstance(response.get("dirParams"), dict) else {}
    exact_datetime = response.get("date") or payload.get("datetime") or "无"
    birth_lines = _build_base_info_lines(natal_wrap, payload) if natal_wrap else [
        f"出生时间：{payload.get('date', '—')} {payload.get('time', '—')}",
        f"出生时区：{payload.get('zone', '—')}",
        f"出生地点：{payload.get('lon', '—')} {payload.get('lat', '—')}",
    ]
    predictive_setup_lines = [
        f"技法：{tool_name}",
        f"目标时间：{payload.get('datetime', '无')}",
        f"后台实际成盘时间：{exact_datetime}",
        f"推运时区：{predictive_params.get('zone') or payload.get('dirZone') or payload.get('zone', '无')}",
        f"推运地点：{predictive_params.get('lon') or payload.get('dirLon') or payload.get('lon', '—')} {predictive_params.get('lat') or payload.get('dirLat') or payload.get('lat', '—')}",
    ]
    sections = [
        ("本命盘起盘信息", _join_lines(birth_lines) or "无"),
        ("本命盘星与虚点", _join_lines(_build_star_and_lot_position_lines(natal_wrap)) if natal_wrap else "无"),
        (f"{chart_label}起盘信息", _join_lines(predictive_setup_lines)),
        (f"{chart_label}星与虚点", _join_lines(_build_star_and_lot_position_lines(predictive_wrap)) or "无"),
        (f"{chart_label}相位", _join_lines(_build_aspect_section(predictive_wrap)) or "无"),
    ]
    return _render_snapshot_text(sections)


def _primary_direction_method_text(value: Any) -> str:
    # 主限法 v12 (星阙 v2.6.6)：仅保留逐位核验的核5方位法（In-Zodiaco 全走核 kernel）。
    # core_alchabitius = 规范键；任何未知/未核验键经后端 fallback 至 core_alchabitius，同义。
    mapping = {
        "horosa_legacy": "传统赤经法",
        "core_alchabitius": "Alcabitius 半弧法",
        "meridian": "Meridian",
        "porphyry": "Porphyry",
        "equal_ecliptic": "Equal（黄道）",
        "equal_hour_circle": "Equal（时圈）",
    }
    raw = _msg(value)
    if raw in mapping:
        return mapping[raw]
    if not raw:
        return "无"
    # /predict/pd 的 params 回显是原样输入；白名单外的方位法（如旧 placidus）引擎内已按
    # 核5白名单回退 core_alchabitius 计算（行集与显式 core 逐位一致，live 测试钉死），如实标注。
    return f"{raw}（未核验，引擎回退 Alcabitius 半弧法）"


def _primary_direction_time_key_text(value: Any) -> str:
    # 时间钥匙 22 项 (星阙 v2.6.6)：静态常数 + 每盘真算 (Simmonite/Kepler/Brahe 取本命太阳日速)
    # + 动态弧 (TrueSolarArc/SymbolicSolarArc 逐弧查星历)。标签与上游方法下拉一致。
    mapping = {
        "Ptolemy": "Ptolemy（托勒密 1°/年）",
        "Naibod": "Naibod（奈博德平太阳速）",
        "TrueSolarArc": "真太阳弧",
        "SymbolicSolarArc": "太阳弧（黄经）",
        "Cardano": "Cardano",
        "Umar": "Umar al-Tabari",
        "Wollner": "Wöllner",
        "Plantiko": "Plantiko",
        "Simmonite": "Simmonite",
        "SynodicYear": "Synodic Year",
        "Kepler": "Kepler",
        "Brahe": "Brahe",
        "Kundig": "Kündig",
        "SymbolicDegree": "Symbolic Degree",
        "SymbolicYear": "Symbolic Year",
        "SymbolicMoon": "Symbolic Moon",
        "SymbolicMonth": "Symbolic Month",
        "Quarterly": "Quarterly",
        "Quinary": "Quinary",
        "Duodenary": "Duodenary",
        "Novenary": "Novenary",
        "SelfMeasure": "Self-Measure",
    }
    return mapping.get(_msg(value), _msg(value) or "无")


def _primary_direction_dir_text(params: dict[str, Any]) -> str:
    # pdDirect/pdConverse 默认都开（顺逆按年龄交错）；显式 0/False 才关。
    direct = params.get("pdDirect") not in {0, False, "0"}
    converse = params.get("pdConverse") not in {0, False, "0"}
    if direct and converse:
        return "顺向+逆向（按年龄交错）"
    if converse:
        return "仅逆向 (converse)"
    return "仅顺向 (direct)"


def _primary_direction_type_text(value: Any) -> str:
    # pdtype 0 = In Zodiaco（黄道）, 1 = In Mundo（世俗）。
    return "In Mundo（世俗）" if _msg(value) in {"1", "True"} else "In Zodiaco（黄道）"


def _pd_obj_text(value: Any, chart_wrap: dict[str, Any]) -> str:
    if isinstance(value, dict):
        object_id = value.get("id") or value.get("obj") or value.get("name")
        if object_id:
            return _astro_msg_with_house(object_id, chart_wrap, short=True)
        return _stringify_export_body(value)
    text = _msg(value)
    if "_" in text:
        parts = text.split("_")
        prefix = parts[0]
        aspect = parts[-1] if parts and parts[-1].lstrip("-").isdigit() else ""
        object_id = "_".join(parts[1:-1] if aspect else parts[1:]).replace("_", " ")
        prefix_text = {"D": "推运", "S": "纬照", "N": "本命"}.get(prefix, prefix)
        object_text = _astro_msg_with_house(object_id, chart_wrap, short=True) or _astro_msg(object_id, short=True) or object_id
        return f"{prefix_text}{object_text}{(' ' + _aspect_text(aspect)) if aspect else ''}".strip()
    return _astro_msg_with_house(value, chart_wrap, short=True) or _planet_label(value)


def _build_primarydirect_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    params = response.get("params", {}) if isinstance(response, dict) and isinstance(response.get("params"), dict) else payload
    predictives = response.get("predictives", {}) if isinstance(response, dict) else {}
    pds = response.get("pd")
    if pds is None and isinstance(predictives, dict):
        pds = predictives.get("primaryDirection", [])
    natal_wrap = _natal_chart_wrap(response) or _top_level_chart_wrap(response)
    show_pd_bounds = not (params.get("showPdBounds") in {0, False})
    degree_label = "赤经" if params.get("pdMethod") == "horosa_legacy" else "Arc"
    rows = [f"| {degree_label} | 迫星 | 应星 | 类型 | 日期 |", "| --- | --- | --- | --- | --- |"]
    if not isinstance(pds, list) or not pds:
        rows.append("| 无 | 无 | 无 | 无 | 无 |")
    else:
        for row in pds:
            if not isinstance(row, list):
                continue
            degree = _msg(row[0]) or "无"
            promittor = _pd_obj_text(row[1] if len(row) > 1 else None, natal_wrap) or "无"
            significator = _pd_obj_text(row[2] if len(row) > 2 else None, natal_wrap) or "无"
            pd_type = _msg(row[3] if len(row) > 3 else None) or "无"
            date = _msg(row[4] if len(row) > 4 else None) or "无"
            rows.append(f"| {degree} | {promittor} | {significator} | {pd_type} | {date} |")
    return _render_snapshot_text(
        [
            ("出生时间", f"出生时间：{params.get('birth', '无')}"),
            ("本命盘星与虚点", _join_lines(_build_star_and_lot_position_lines(natal_wrap)) or "无"),
            (
                "主/界限法设置",
                _join_lines(
                    [
                        f"推运方法：{_primary_direction_method_text(params.get('pdMethod'))}",
                        f"坐标系：{_primary_direction_type_text(params.get('pdtype'))}",
                        f"推运方向：{_primary_direction_dir_text(params)}",
                        f"度数换算：{_primary_direction_time_key_text(params.get('pdTimeKey'))}",
                        f"映点(antiscia)作迫星：{'是' if params.get('pdAntiscia') in {1, True, '1'} else '否'}",
                        f"界(terms)作迫星：{'是' if params.get('pdTerms') in {1, True, '1'} else '否'}",
                        f"显示界限法：{'是' if show_pd_bounds else '否'}",
                    ]
                ),
            ),
            ("主/界限法表格", _join_lines(rows)),
        ]
    )


def _build_pdchart_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    params = response.get("params", {}) if isinstance(response, dict) and isinstance(response.get("params"), dict) else payload
    current_arc = response.get("currentArc") or response.get("arc") or response.get("pdArc") or "无"
    natal_wrap = _natal_chart_wrap(response)
    pd_wrap = _top_level_chart_wrap(response)
    return _render_snapshot_text(
        [
            ("出生时间", f"出生时间：{params.get('birth', '无')}"),
            ("本命盘星与虚点", _join_lines(_build_star_and_lot_position_lines(natal_wrap)) or "无"),
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
            ("主限法盘星体表格", _join_lines(_chart_position_table_lines(pd_wrap)) or "无"),
            ("主限法盘相位", _join_lines(_build_aspect_section(pd_wrap)) or "无"),
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
    params = response.get("params", {}) if isinstance(response, dict) and isinstance(response.get("params"), dict) else payload
    predictives = response.get("predictives", {}) if isinstance(response, dict) else {}
    zr_data = None
    for key in ("zodialRelease", "zodiacalRelease", "zr", "zodialrelease"):
        if response.get(key) is not None:
            zr_data = response.get(key)
            break
        if isinstance(predictives, dict) and predictives.get(key) is not None:
            zr_data = predictives.get(key)
            break
    lines = [f"出生时间：{params.get('birth', '无')}", f"经纬度：{params.get('lon', '—')} {params.get('lat', '—')}", f"时区：{params.get('zone', '—')}"]
    natal_wrap = _natal_chart_wrap(response) or _top_level_chart_wrap(response)
    base_point = payload.get("basePoint") or response.get("basePoint") or "X点"
    zr_lines: list[str] = []
    def push_zr(items: Any, *, level_limit: int = 3) -> None:
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            level = item.get("level", "")
            sign = _astro_msg(item.get("sign"))
            date = item.get("date", "无")
            days = item.get("days", "无")
            zr_lines.append(f"L{level}：{sign}；开始：{date}；时长：{days}日")
            if level_limit > 1:
                sublevel = item.get("sublevel")
                if isinstance(sublevel, list):
                    for sub in sublevel[:6]:
                        if isinstance(sub, dict):
                            zr_lines.append(
                                f"  L{sub.get('level', '')}：{_astro_msg(sub.get('sign'))}；开始：{sub.get('date', '无')}；时长：{sub.get('days', '无')}日"
                            )
    if isinstance(zr_data, list):
        push_zr(zr_data)
    elif isinstance(zr_data, dict):
        zr_lines.append(_stringify_export_body(zr_data))
    return _render_snapshot_text([("起盘信息", _join_lines(lines)), ("本命盘星与虚点", _join_lines(_build_star_and_lot_position_lines(natal_wrap)) or "无"), (f"基于{base_point}推运", _join_lines(zr_lines) or "无推运数据")])


def _auto_snapshot_text_for_tool(tool_name: str, input_normalized: dict[str, Any], response_data: dict[str, Any]) -> str | None:
    if tool_name in {"chart", "chart13", "hellen_chart", "india_chart"} and _is_astro_chart_payload(response_data):
        return _build_astro_snapshot_text(input_normalized, response_data)
    if tool_name in {"solarreturn", "lunarreturn", "solararc", "givenyear", "profection"}:
        return _build_predictive_snapshot_text(tool_name, input_normalized, response_data)
    if tool_name == "pd":
        return _build_primarydirect_snapshot_text(input_normalized, response_data)
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
        # 兜底 body：段未进快照(parsed body 空)且无 __export_body__ 时，退回 stringify(section_payload)。
        # 但 _pick_section_data 对未识别段名兜底返回整份 response_data → stringify 会把整份响应 dump 进段正文，
        # 导出文本暴涨百倍(条件 preset 段未产出时触发)。故超阈值即判定为原始 dump，改用简短「未产出」占位。
        fallback_body = _stringify_export_body(section_payload)
        if fallback_body and len(fallback_body.splitlines()) > 80:
            fallback_body = _missing_detail_text(title)
        body = parsed_section.get("body") or section_body_override or fallback_body
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


def _build_compact_subresult_contract(result: ToolEnvelope) -> dict[str, Any]:
    data = result.data if isinstance(result.data, dict) else {}
    export_snapshot = data.get("export_snapshot") if isinstance(data.get("export_snapshot"), dict) else None
    export_format = data.get("export_format") if isinstance(data.get("export_format"), dict) else None
    section_titles = []
    if isinstance(export_format, dict):
        for section in export_format.get("sections", []):
            if isinstance(section, dict) and section.get("title"):
                section_titles.append(section["title"])
    return {
        "ok": result.ok,
        "tool": result.tool,
        "version": result.version,
        "input_normalized": result.input_normalized,
        "summary": list(result.summary),
        "warnings": list(result.warnings),
        "memory_ref": result.memory_ref.model_dump(mode="json") if result.memory_ref else None,
        "trace_id": result.trace_id,
        "group_id": result.group_id,
        "export_contract": {
            "has_export_snapshot": isinstance(export_snapshot, dict),
            "has_export_format": isinstance(export_format, dict),
            "technique": export_snapshot.get("technique") if isinstance(export_snapshot, dict) else None,
            "selected_sections": list(export_format.get("selected_sections", [])) if isinstance(export_format, dict) else [],
            "format_source": export_format.get("format_source") if isinstance(export_format, dict) else None,
            "section_count": len(section_titles),
            "section_titles": section_titles,
            "bundle_version": export_format.get("bundle_version") if isinstance(export_format, dict) else None,
            "provenance": export_format.get("provenance") if isinstance(export_format, dict) else None,
            "citation": export_format.get("citation") if isinstance(export_format, dict) else None,
        },
        "error": result.error.model_dump(mode="json") if result.error else None,
    }


class HorosaSkillService:
    def __init__(
        self,
        settings: Settings,
        client: HorosaApiClient | None = None,
        chart_client: HorosaPlainJsonClient | HorosaApiClient | None = None,
        store: MemoryStore | None = None,
        js_client: HorosaJsEngineClient | None = None,
        runtime_manager: HorosaRuntimeManager | None = None,
    ) -> None:
        self.settings = settings
        self.client = client or HorosaApiClient(settings.server_root)
        self.chart_client = chart_client or (client if client is not None else HorosaPlainJsonClient(settings.chart_server_root))
        self.store = store or MemoryStore(settings)
        self.js_client = js_client or HorosaJsEngineClient(settings)
        self.runtime_manager = runtime_manager or HorosaRuntimeManager(settings)
        self.tracer = TraceRecorder(settings)
        self.report_builder = ReportBuilder()
        self._java_runtime_ready = False
        self._chart_runtime_ready = False

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
        use_chart_server = endpoint in _PYTHON_CHART_ENDPOINTS
        client = self.chart_client if use_chart_server else self.client
        probe_endpoint = "/" if use_chart_server else "/common/time"
        runtime_ready = self._chart_runtime_ready if use_chart_server else self._java_runtime_ready
        if not runtime_ready and not client.probe(probe_endpoint):
            self.runtime_manager.start_local_services()
        remote_endpoint = _chart_server_endpoint(endpoint) if use_chart_server else endpoint
        connection_retry_used = False
        data: dict[str, Any] | None = None
        while True:
            candidate_payloads = _java_chart_payload_candidates(endpoint, payload)
            param_errors: list[tuple[dict[str, Any], ToolTransportError]] = []
            for remote_payload in candidate_payloads:
                try:
                    data = client.call(remote_endpoint, remote_payload)
                    break
                except ToolTransportError as exc:
                    body = str(exc.details.get("body", ""))
                    is_param_error = exc.code == "tool.backend_param_error" or (
                        exc.code == "transport.http_error" and "200001" in body and "param error" in body
                    )
                    if not is_param_error:
                        if exc.code == "transport.connection_error" and not connection_retry_used:
                            connection_retry_used = True
                            self.runtime_manager.start_local_services()
                            time.sleep(1.0)
                            break
                        raise
                    param_errors.append((remote_payload, exc))
            else:
                remote_payload, exc = param_errors[-1]
                payload_preview = {
                    key: remote_payload.get(key)
                    for key in ("date", "time", "zone", "lat", "lon", "gpsLat", "gpsLon", "dirZone", "dirLat", "dirLon")
                    if key in remote_payload
                }
                attempted_payloads = [
                    {
                        key: attempted.get(key)
                        for key in ("date", "time", "zone", "lat", "lon", "gpsLat", "gpsLon", "dirZone", "dirLat", "dirLon")
                        if key in attempted
                    }
                    for attempted, _error in param_errors
                ]
                raise ToolTransportError(
                    "Horosa backend rejected the birth parameters.",
                    code="tool.backend_param_error",
                    details={
                        **exc.details,
                        "endpoint": endpoint,
                        "runtime_target": "python_chart" if use_chart_server else "java_backend",
                        "payload_preview": payload_preview,
                        "attempted_payloads": attempted_payloads,
                        "hint": (
                            "Use timezone like `+08:00` and compact coordinates like `31n13` / `121e28`, or send decimal "
                            "coordinates so Horosa Skill can normalize them automatically."
                        ),
                    },
                ) from exc
            if data is not None:
                break
            continue
        if use_chart_server:
            self._chart_runtime_ready = True
        else:
            self._java_runtime_ready = True
        unwrapped = self._unwrap_result(data)
        if not isinstance(unwrapped, dict):
            raise ToolTransportError(
                "Horosa endpoint returned a non-object result payload.",
                code="transport.invalid_result_shape",
                details={"endpoint": endpoint, "runtime_target": "python_chart" if use_chart_server else "java_backend"},
            )
        return unwrapped

    def _augment_export_payload(self, *, technique: str, snapshot_text: str | None) -> dict[str, Any] | None:
        if not snapshot_text:
            return None
        try:
            return parse_export_content(technique=technique, content=snapshot_text)
        except ValueError:
            return None

    def _attach_predictive_chart_context(self, tool_name: str, payload: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
        if tool_name not in {"solarreturn", "lunarreturn", "solararc", "givenyear", "profection", "pd", "pdchart", "zr"}:
            return response
        enriched = dict(response)
        if "params" not in enriched:
            enriched["params"] = {
                **payload,
                "birth": f"{payload.get('date', '—')} {payload.get('time', '—')}",
            }
        if not any(key in enriched for key in ("natalChart", "birthChart", "baseChart")):
            natal_payload = {**payload, "predictive": 0}
            natal_payload.pop("datetime", None)
            natal_payload.pop("dirZone", None)
            natal_payload.pop("dirLat", None)
            natal_payload.pop("dirLon", None)
            enriched["natalChart"] = self._call_remote("/chart", natal_payload)
        return enriched

    def _attach_natal_extras(self, tool_name: str, response_data: dict[str, Any]) -> dict[str, Any]:
        # v2.4.0 西占: enrich the astrochart (and mundane) export with 12分度 / 主宰星链 / 寿命格局.
        # These are computed by the vendored JS astroextra formatter (Ptolemy hyleg engine) from the
        # chart object. Only `chart` (astrochart) and `mundane` carry them in 星阙; never fail the
        # chart if the enrichment errors.
        if tool_name not in {"chart", "mundane"}:
            return response_data
        if not isinstance(response_data, dict) or not _is_astro_chart_payload(response_data):
            return response_data
        try:
            js = self.js_client.run("astroextra", {"chart": response_data})
            extras_data = js.get("data") if isinstance(js, dict) else None
            if isinstance(extras_data, dict):
                sections = _build_natal_extra_sections(extras_data)
                if sections:
                    enriched = dict(response_data)
                    enriched["_natalExtras"] = sections
                    return enriched
        except Exception:
            pass
        return response_data

    # 古典格局派生分析 (星阙 v2.6.7): astrochart/astrochart_like 的 [古典格局] 段来自 /astroextra/analysis
    # (护卫/优势相位/相位动态/逐题主星/偶然尊贵/恒星/行星时/埃及历/巴比伦/格局/分布/气质/almutem/吉化-extraLots)。
    # 与前端同源:按需 fetch、优雅降级(失败→不挂载→该段不出)。[古典](逐曜状态/围攻/围绕)直接读 /chart 响应,无需此 fetch。
    _CLASSICAL_ANALYSIS_TOOLS = {"chart", "chart13", "hellen_chart"}

    def _attach_classical_analysis(self, tool_name: str, payload: dict[str, Any], response_data: dict[str, Any]) -> dict[str, Any]:
        if tool_name not in self._CLASSICAL_ANALYSIS_TOOLS:
            return response_data
        if not isinstance(response_data, dict) or not _is_astro_chart_payload(response_data):
            return response_data
        for key in ("date", "zone", "lat", "lon"):
            if not payload.get(key):
                return response_data
        try:
            analysis = self._call_remote(
                "/astroextra/analysis",
                {
                    "date": payload.get("date"),
                    "time": payload.get("time"),
                    "zone": payload.get("zone"),
                    "lat": payload.get("lat"),
                    "lon": payload.get("lon"),
                    "gpsLat": payload.get("gpsLat"),
                    "gpsLon": payload.get("gpsLon"),
                    "ad": payload.get("ad", 1),
                    "hsys": payload.get("hsys"),
                    "zodiacal": payload.get("zodiacal"),
                    "siderealAyanamsa": payload.get("siderealAyanamsa"),
                    "fixedStarOrb": 1,
                },
            )
            if isinstance(analysis, dict) and analysis:
                enriched = dict(response_data)
                enriched["_classicalAnalysis"] = analysis
                return enriched
        except Exception as exc:
            logger.warning("classical /astroextra/analysis failed (tool=%s): %s", tool_name, exc)
        return response_data

    # 八字格局（v3.0.x 本地化）：五行力量/格局·用神/盲派结构 由 core-js baziGeju 引擎从后端 fourColumns 派生，
    # 与 [四柱与三元] 同源。按需调用、优雅降级（无 node/引擎失败→不挂载→该批段不出，列 optional）。
    _BAZI_GEJU_TOOLS = {"bazi_birth", "bazi_direct"}

    def _attach_bazi_geju(self, tool_name: str, response_data: dict[str, Any]) -> dict[str, Any]:
        if tool_name not in self._BAZI_GEJU_TOOLS or not isinstance(response_data, dict):
            return response_data
        bazi = response_data.get("bazi")
        fc = bazi.get("fourColumns") if isinstance(bazi, dict) else None
        if not isinstance(fc, dict):
            return response_data
        try:
            geju = self.js_client.run("bazi_geju", {"fourColumns": fc})
            text = geju.get("snapshot_text") if isinstance(geju, dict) else None
            if isinstance(text, str) and text.strip():
                enriched = dict(response_data)
                enriched["_baziGeju"] = text
                return enriched
        except ToolTransportError as exc:
            logger.warning("bazi geju engine failed (tool=%s): %s", tool_name, exc)
        return response_data

    def _require_ken_pan(self, ken_response: Any, *, engine: str, endpoint: str) -> None:
        """Fail loudly when the ken backend did not actually compute a pan.

        The ken chart endpoints (`/qimen/pan`, `/taiyi/pan`, `/jinkou/pan`) return HTTP 200
        even on failure, with an envelope like ``{"ResultCode": -1, "Result": "<engine> ...
        failed"}`` (a string ``Result``). That envelope is still a ``dict``, so ``_call_remote``
        does not treat it as a transport error. If we forwarded it to the JS layer, the formatter
        would silently fall back to its *local* scaffold compute — producing a chart that does
        NOT match 星阙. ken is the sole compute authority for these techniques, so a failed ken
        response must surface as a loud error instead of a silent local-engine fallback.
        """
        if isinstance(ken_response, dict) and ken_response.get("source") == engine:
            return
        detail_result = ken_response.get("Result") if isinstance(ken_response, dict) else ken_response
        raise ToolTransportError(
            f"Horosa ken ({engine}) engine did not return a valid pan.",
            code="tool.ken_compute_failed",
            details={
                "endpoint": endpoint,
                "engine": engine,
                "ken_result": detail_result,
                "hint": (
                    f"{engine} is the sole compute authority for this technique; the chart "
                    "service raised on these parameters (it returns HTTP 200 with a failure "
                    "envelope). Check the chart-service log and the input fields — the skill "
                    "will not silently fall back to a local-engine chart."
                ),
            },
        )

    _TIAN_GAN = ("甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸")

    def _normalize_fa_related_people(self, payload: dict[str, Any]) -> list[dict[str, Any]] | None:
        """法奇门「相关人员」：把 [{name, yearGan|birth}] 归一化为上游 stamp 形状 [{name, yearGan}]。

        yearGan 直接收十天干字符；birth（公历 YYYY-MM-DD[ HH:mm:ss]）走 /nongli/time 的
        yearJieqi（立春界年干支）取年干——与上游 birthToYearGan 同口径（1-2 月出生立春前后
        归属不同年）。解析不出的人员跳过：computeProtect 对 falsy yearGan 同样不出行。
        """
        raw = payload.get("faRelatedPeople")
        if not isinstance(raw, list):
            return None
        normalized: list[dict[str, Any]] = []
        for person in raw:
            if not isinstance(person, dict):
                continue
            name = str(person.get("name") or "").strip() or "相关人员"
            year_gan = str(person.get("yearGan") or "").strip()
            if year_gan not in self._TIAN_GAN:
                year_gan = ""
                birth = str(person.get("birth") or "").strip()
                if birth:
                    birth_date, _, birth_time = birth.partition(" ")
                    birth_time = birth_time.strip() or "12:00:00"
                    if len(birth_time) == 5:
                        birth_time = f"{birth_time}:00"
                    try:
                        person_nongli = self._call_remote(
                            "/nongli/time",
                            {
                                "date": birth_date,
                                "time": birth_time,
                                "zone": payload.get("zone"),
                                "lat": payload.get("lat"),
                                "lon": payload.get("lon"),
                                "gpsLat": payload.get("gpsLat"),
                                "gpsLon": payload.get("gpsLon"),
                                "ad": 1,
                            },
                        )
                        year_jieqi = str((person_nongli or {}).get("yearJieqi") or "")
                        if year_jieqi[:1] in self._TIAN_GAN:
                            year_gan = year_jieqi[0]
                    except Exception:
                        year_gan = ""
            if year_gan:
                normalized.append({"name": name, "yearGan": year_gan})
        return normalized

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
                {"year": year - 1, "zone": payload["zone"], "lat": payload["lat"], "lon": payload["lon"], "time": payload["time"], "gpsLat": payload.get("gpsLat"), "gpsLon": payload.get("gpsLon"), "ad": payload.get("ad", 1), "timeAlg": payload.get("timeAlg", 0)},
            )
        current_year = payload.get("jieqi_year_current")
        if not isinstance(current_year, dict):
            current_year = self._call_remote(
                "/jieqi/year",
                {"year": year, "zone": payload["zone"], "lat": payload["lat"], "lon": payload["lon"], "time": payload["time"], "gpsLat": payload.get("gpsLat"), "gpsLon": payload.get("gpsLon"), "ad": payload.get("ad", 1), "timeAlg": payload.get("timeAlg", 0)},
            )
        options = payload.get("options") or {}
        qiju_method = "zhirun" if str(options.get("qijuMethod") or "").strip() == "zhirun" else "chaibu"
        # ken is the compute authority; the JS layer only reformats this into aiExport.js sections.
        ken_response = self._call_remote(
            "/qimen/pan",
            {
                **_ken_datetime_parts(payload),
                "zone": payload.get("zone"),
                "qimenMode": _ken_qimen_mode(options),
                "qijuMethod": qiju_method,
                "option": 2 if qiju_method == "zhirun" else 1,
                "date": payload.get("date"),
                "time": payload.get("time"),
                "realSunTime": (nongli or {}).get("birth", ""),
                "jiedelta": (nongli or {}).get("jiedelta", ""),
            },
        )
        self._require_ken_pan(ken_response, engine="kinqimen", endpoint="/qimen/pan")
        js_payload = {
            **payload,
            "nongli": nongli,
            "jieqi_year_prev": prev_year,
            "jieqi_year_current": current_year,
            "ken_response": ken_response,
        }
        fa_related_people = self._normalize_fa_related_people(payload)
        if fa_related_people is not None:
            js_payload["faRelatedPeople"] = fa_related_people
        js_result = self.js_client.run("qimen", js_payload)
        snapshot_text = js_result.get("snapshot_text")
        return {
            "pan": js_result.get("data", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="qimen", snapshot_text=snapshot_text),
            "prerequisites": {"nongli": nongli, "jieqi_year_prev": prev_year, "jieqi_year_current": current_year},
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
        options = payload.get("options") or {}
        sex = options.get("sex") or payload.get("gender") or "男"
        ken_response = self._call_remote(
            "/taiyi/pan",
            {
                **_ken_datetime_parts(payload),
                "zone": payload.get("zone"),
                "style": options.get("style", 3),
                "tn": options.get("tn", 0),
                "sex": sex,
                "enableGameTheory": bool(options.get("gameTheory") in (1, True, "1")),
                "date": payload.get("date"),
                "time": payload.get("time"),
                "realSunTime": (nongli or {}).get("birth", ""),
                "jiedelta": (nongli or {}).get("jiedelta", ""),
            },
        )
        self._require_ken_pan(ken_response, engine="kintaiyi", endpoint="/taiyi/pan")
        js_result = self.js_client.run("taiyi", {**payload, "nongli": nongli, "ken_response": ken_response})
        snapshot_text = js_result.get("snapshot_text")
        return {
            "pan": js_result.get("data", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="taiyi", snapshot_text=snapshot_text),
            "prerequisites": {"nongli": nongli},
        }

    def _run_jinkou_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        liureng = payload.get("liureng")
        if not isinstance(liureng, dict):
            remote = self._call_remote(
                "/liureng/gods",
                _liureng_remote_payload("liureng_gods", payload),
            )
            liureng = remote.get("liureng", remote)
        options = payload.get("options") or {}
        difen = payload.get("diFen") or options.get("diFen") or "子"
        ken_response = self._call_remote(
            "/jinkou/pan",
            {
                **_ken_datetime_parts(payload),
                "zone": payload.get("zone"),
                "difen": difen,
                "yuejiang": options.get("yueJiang") or options.get("yuejiang") or "",
                "zhanshi": options.get("zhanShi") or options.get("zhanshi") or "",
                "date": payload.get("date"),
                "time": payload.get("time"),
            },
        )
        self._require_ken_pan(ken_response, engine="kinjinkou", endpoint="/jinkou/pan")
        js_result = self.js_client.run("jinkou", {**payload, "liureng": liureng, "ken_response": ken_response})
        snapshot_text = js_result.get("snapshot_text")
        return {
            "jinkou": js_result.get("data", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="jinkou", snapshot_text=snapshot_text),
            "prerequisites": {"liureng": liureng},
        }

    def _run_liureng_tool(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = "/liureng/runyear" if tool_name == "liureng_runyear" else "/liureng/gods"
        remote = self._call_remote(endpoint, _liureng_remote_payload(tool_name, payload))
        liureng = remote.get("liureng", remote)
        runyear = remote.get("runyear") or remote.get("runYear")
        chart: dict[str, Any] = {}
        chart_error: dict[str, Any] | None = None
        try:
            chart = self._call_remote("/chart", _liureng_chart_payload(payload))
        except HorosaSkillError as exc:
            chart_error = {"code": exc.code, "message": str(exc), "details": exc.details}
        except Exception as exc:
            chart_error = {"code": "liureng.chart_context_unavailable", "message": str(exc), "details": {}}

        js_result = self.js_client.run(
            "liureng",
            {
                **payload,
                "liureng": liureng,
                "runyear": runyear,
                "chart": chart,
                "guirengType": payload.get("guirengType", 2),
            },
        )
        snapshot_text = js_result.get("snapshot_text")
        data = js_result.get("data", {}) if isinstance(js_result.get("data"), dict) else {}
        result = {
            "liureng": {
                **(liureng if isinstance(liureng, dict) else {}),
                "layout": data.get("layout"),
                "ke": data.get("ke", {}).get("raw") if isinstance(data.get("ke"), dict) else None,
                "keText": data.get("ke", {}).get("lines") if isinstance(data.get("ke"), dict) else None,
                "sanChuan": data.get("sanChuan"),
                "panStyle": data.get("panStyleName"),
            },
            "runyear": runyear,
            "headless_liureng": data,
            "snapshot_text": snapshot_text,
            "prerequisites": {
                "remote_payload": _liureng_remote_payload(tool_name, payload),
                "chart_available": bool(chart),
                "chart_error": chart_error,
            },
        }
        result["export_snapshot"] = self._augment_export_payload(technique="liureng", snapshot_text=snapshot_text)
        return result

    def _run_tongshefa_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        js_result = self.js_client.run("tongshefa", payload)
        snapshot_text = js_result.get("snapshot_text")
        return {
            "tongshefa": js_result.get("data", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="tongshefa", snapshot_text=snapshot_text),
        }

    def _run_canping_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # canping is computed entirely in-process by horosa-core-js (bazi chain → 金锁银匙 起数),
        # not the ken backend. The JS returns the canping model + the 星阙-identical snapshot text.
        js_result = self.js_client.run("canping", payload)
        snapshot_text = js_result.get("snapshot_text")
        return {
            "canping": js_result.get("data", {}),
            "input_normalized": js_result.get("input_normalized", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="canping", snapshot_text=snapshot_text),
        }

    def _run_heluo_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # heluo (河洛理数) is also a 原生·非 ken tool: the JS computes the chart (起命/先天/后天), 大限/
        # 岁运, and 命运篇 judge in-process and returns the 星阙-identical snapshot text.
        js_result = self.js_client.run("heluo", payload)
        snapshot_text = js_result.get("snapshot_text")
        return {
            "heluo": js_result.get("data", {}),
            "input_normalized": js_result.get("input_normalized", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="heluo", snapshot_text=snapshot_text),
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
        sections: list[tuple[str, str]] = [
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
        # 三式合一对齐独立页：复用三个独立技法（奇门/太乙/六壬）builder 已产出的富化段，
        # 按前缀规则拼入（太乙 pan.sections 加「太乙」前缀避叠词、六壬断卦层保留原名、奇门派生加「奇门」
        # 前缀避与六壬「概览」等碰撞），单一真值源不重复实现；缺段优雅降级为简短占位，不臆造。
        for _out, _src in (
            ("太乙主客定算", "主客定算"),
            ("太乙八门与宿曜", "八门与宿曜"),
            ("太乙断法", "断法"),
            ("太乙七大兵法", "七大兵法"),
            ("太乙博弈", "博弈"),
            ("太乙命法", "命法"),
            ("太乙命宫行限", "命宫行限"),
        ):
            sections.append((_out, _section_body(taiyi_export, _src, f"（本盘未产出「{_src}」）")))
        for _t in (
            "十二盘式", "常用神煞", "年月神煞", "课体结构", "三传旺衰",
            "空亡真假", "旬空落点", "陷空", "遁干特殊", "年命上神",
            "毕法（已命中）", "占断向导",
        ):
            sections.append((_t, _section_body(liureng_export, _t, f"（本盘未产出「{_t}」）")))
        for _out, _src in (
            ("奇门九宫方盘", "九宫方盘"),
            ("奇门旺相休囚死·月令能量", "旺相休囚死·月令能量"),
            ("奇门六害总览", "六害总览"),
            ("奇门化解方案", "化解方案"),
            ("奇门八门化气大阵", "八门化气大阵"),
            ("奇门用神分论", "用神分论"),
            ("奇门财富七要", "财富七要"),
            ("奇门事业七要", "事业七要"),
            ("奇门恋爱姻缘", "恋爱姻缘"),
            ("奇门孤辰寡宿", "孤辰寡宿"),
        ):
            sections.append((_out, _section_body(qimen_export, _src, f"（本盘未产出「{_src}」）")))
        snapshot_text = _render_snapshot_text(sections)
        return {
            "qimen": qimen_result.data.get("pan", {}),
            "taiyi": taiyi_result.data.get("pan", {}),
            "liureng": liureng_result.data.get("liureng", {}),
            "subresults": {
                "qimen": _build_compact_subresult_contract(qimen_result),
                "taiyi": _build_compact_subresult_contract(taiyi_result),
                "liureng_gods": _build_compact_subresult_contract(liureng_result),
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
        # 政余格局 (星阙 v2.6.x Moira DSL)：vendored JS buildLocalMoiraPatterns 评估盘面物象格局。
        # 失败不阻塞既有段（→ '无'），与 星阙 buildGuolaoPatternSection 的 try/catch 一致。
        pattern_text: str | None = None
        patterns: Any = None
        try:
            js = self.js_client.run("guolao_moira", {"chart": response, "fields": {}, "params": response})
            if isinstance(js, dict):
                pattern_text = js.get("snapshot_text")
                patterns = js.get("data", {}).get("patterns") if isinstance(js.get("data"), dict) else None
        except Exception as exc:  # noqa: BLE001 - degrade to '无', never break the guolao chart
            logger.warning("guolao_moira pattern eval failed: %s", exc)
        snapshot_text = _build_guolao_snapshot_text(remote_payload, response, pattern_text=pattern_text)
        response = dict(response)
        response["snapshot_text"] = snapshot_text
        response["guolaoPatterns"] = patterns
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

    def _run_harmonic_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 调波盘: a backend chart-extra computation on the Python chart service (/astroextra/harmonic).
        # 星阙 has no aiExport contract for 调波盘 (it is a UI/lab-only auxiliary chart), so this returns
        # the structured data (positions/conjunctions/chart) plus a readable snapshot_text for the AI,
        # but no formal export technique (harmonic is intentionally absent from TOOL_EXPORT_TECHNIQUE_MAP).
        try:
            harmonic_num = max(1, min(int(payload.get("harmonic", 9)), 360))
        except (TypeError, ValueError):
            harmonic_num = 9
        orb = payload.get("orb", 2.0)
        remote_payload = {**payload, "predictive": 0, "harmonic": harmonic_num, "orb": orb}
        response = self._call_remote("/astroextra/harmonic", remote_payload)
        snapshot_text = _build_harmonic_snapshot_text(remote_payload, response)
        return {
            "harmonic": response.get("harmonic", harmonic_num),
            "positions": response.get("positions", []),
            "conjunctions": response.get("conjunctions", []),
            "chart": response.get("chart"),
            "raw": response,
            "snapshot_text": snapshot_text,
        }

    def _run_agepoint_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 年龄推进点 (Age Point / Huber): backend /predict/agepoint computes the whole Koch-house cycle.
        remote_payload = {**payload, "predictive": payload.get("predictive", 1)}
        response = self._call_remote("/predict/agepoint", remote_payload)
        snapshot_text = _build_agepoint_snapshot_text(response)
        agepoint = response.get("agepoint") if isinstance(response.get("agepoint"), dict) else {}
        result = {
            "agepoint": agepoint,
            "points": agepoint.get("points", []),
            "raw": response,
            "snapshot_text": snapshot_text,
        }
        result["export_snapshot"] = self._augment_export_payload(technique="agepoint", snapshot_text=snapshot_text)
        return result

    def _run_distributions_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 界推运 (Distributions / 分配法): backend /predict/dist computes the full-life term timeline.
        remote_payload = {**payload, "predictive": payload.get("predictive", 1)}
        response = self._call_remote("/predict/dist", remote_payload)
        snapshot_text = _build_distributions_snapshot_text(response)
        result = {
            "distributions": response.get("dist", []),
            "raw": response,
            "snapshot_text": snapshot_text,
        }
        result["export_snapshot"] = self._augment_export_payload(technique="distributions", snapshot_text=snapshot_text)
        return result

    def _progression_target(self, payload: dict[str, Any]) -> dict[str, Any]:
        # These v2.5.0 progressions are "as of a target date". Default the target to the chart date if
        # the agent didn't pass one (a valid, if trivial, request); the agent should pass targetDate for
        # a meaningful analysis horizon.
        return {
            "targetDate": payload.get("targetDate") or payload.get("date"),
            "targetTime": payload.get("targetTime") or "12:00:00",
        }

    def _run_jaynesprog_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # Jayne 赤纬推运 (v2.5.0): /astroextra/jaynesprog — secondary progression + declination parallels.
        remote_payload = {**payload, **self._progression_target(payload), "orb": payload.get("orb", 1.0)}
        response = self._call_remote("/astroextra/jaynesprog", remote_payload)
        snapshot_text = _build_jaynesprog_snapshot_text(response)
        return {
            "methods": response.get("methods", []),
            "raw": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="jaynesprog", snapshot_text=snapshot_text),
        }

    def _run_vedicprog_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 恒星推运 Vedic (v2.5.0): /astroextra/progressions with zodiacal=1 (sidereal).
        remote_payload = {**payload, **self._progression_target(payload), "zodiacal": 1, "orb": payload.get("orb", 1.5)}
        response = self._call_remote("/astroextra/progressions", remote_payload)
        snapshot_text = _build_vedicprog_snapshot_text(response)
        return {
            "methods": response.get("methods", []),
            "raw": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="vedicprog", snapshot_text=snapshot_text),
        }

    def _run_planetaryarc_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 行星弧 (v2.5.0): /predict/planetaryarc — directs the whole chart by the arc of arcSource (default Moon).
        remote_payload = {
            **payload,
            "datetime": payload.get("datetime") or payload.get("targetDate") or payload.get("date"),
            "asporb": payload.get("asporb", 1),
            "arcSource": payload.get("arcSource", "Moon"),
        }
        response = self._call_remote("/predict/planetaryarc", remote_payload)
        snapshot_text = _build_planetaryarc_snapshot_text(response)
        return {
            "chart": response.get("chart"),
            "raw": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="planetaryarc", snapshot_text=snapshot_text),
        }

    def _run_planetaryages_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 行星年龄 (v2.5.0): Ptolemy seven ages of man — reads the natal chart, marks the current band.
        chart_payload = {**payload, "predictive": 0}
        response = self._call_remote("/chart", chart_payload)
        as_of = payload.get("asOf") or payload.get("targetDate")
        snapshot_text = _build_planetaryages_snapshot_text(response, as_of)
        return {
            "chart": response.get("chart"),
            "raw": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="planetaryages", snapshot_text=snapshot_text),
        }

    def _run_progextra_js_tool(self, payload: dict[str, Any], technique: str) -> dict[str, Any]:
        # v2.5.0 推运 builders that are too algorithm-heavy to re-port (balbillus 129年旺距削减 / persiandirected /
        # yearsystem129): cast the natal /chart, then run the vendored 星阙 frontend builder via horosa-core-js,
        # which emits the single-section snapshot text directly.
        chart_payload = {**payload, "predictive": 0}
        chart_payload.pop("datetime", None)
        chart_payload.pop("dirZone", None)
        chart_payload.pop("dirLat", None)
        chart_payload.pop("dirLon", None)
        response = self._call_remote("/chart", chart_payload)
        snapshot_text = ""
        try:
            js = self.js_client.run("progextra", {"technique": technique, "chart": response})
            if isinstance(js, dict):
                snapshot_text = f"{js.get('snapshot_text') or ''}".strip()
        except Exception as exc:
            logger.warning("progextra JS engine failed (technique=%s): %s", technique, exc)
        return {
            "chart": response.get("chart"),
            "raw": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique=technique, snapshot_text=snapshot_text),
        }

    def _run_balbillus_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # Balbillus 129年系统（旺距削减）: vendored JS builder (see horosa-core-js progextra).
        return self._run_progextra_js_tool(payload, "balbillus")

    # 多重回归 (星阙 v2.6.x): 土/木/月交三体返照。上游前端 buildExtraReturnsSnapshotText 是「请求型」——
    # 逐体拉 /astroextra/planetreturn。skill 把这三次后端调用放在 Python 侧（headless JS 不发 HTTP），
    # 再按上游同格式拼 [多重回归] 段。
    _EXTRARETURNS_BODIES = (("Saturn", "土星返照", "≈29.5 年"), ("Jupiter", "木星返照", "≈11.9 年"), ("Node", "月交返照", "≈18.6 年"))

    def _run_extrareturns_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        remote_base = {**payload, "predictive": 0}
        for key in ("datetime", "dirZone", "dirLat", "dirLon"):
            remote_base.pop(key, None)
        lines = ["[多重回归]"]
        for body_key, cn, period in self._EXTRARETURNS_BODIES:
            try:
                resp = self._call_remote("/astroextra/planetreturn", {**remote_base, "body": body_key, "count": 4})
            except Exception as exc:
                logger.warning("extrareturns planetreturn failed (body=%s): %s", body_key, exc)
                continue
            rows = resp.get("returns") if isinstance(resp, dict) else None
            if not isinstance(rows, list) or not rows:
                continue
            cells = [f"第{r.get('which')}回 {r.get('date')}" for r in rows if isinstance(r, dict) and r.get("date")]
            if cells:
                lines.append(f"{cn}（{period}）：" + "，".join(cells))
        snapshot_text = "\n".join(lines) if len(lines) > 1 else ""
        return {
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="extrareturns", snapshot_text=snapshot_text),
        }

    def _run_shenshu_tool(self, payload: dict[str, Any], key: str) -> dict[str, Any]:
        # 神数 family (wangji / wuzhao / taixuan / jingjue / shenyishu): each is a kentang engine mounted on
        # the chart service (:8899) that returns a backend-built `snapshot` text whose [小节] headers already
        # match 星阙's aiExport preset. The skill splits date/time into year/month/day/hour/minute, forwards
        # the晚子时 switches + any technique-specific overrides (payload.options), and exports the snapshot.
        endpoint = _SHENSHU_ENDPOINTS[key]
        remote_payload: dict[str, Any] = {
            **_split_birth_ymdhm(payload),
            "date": payload.get("date"),
            "time": payload.get("time"),
            "after23NewDay": payload.get("after23NewDay", 1),
            "lateZiHourUseNextDay": payload.get("lateZiHourUseNextDay", 1),
        }
        # cetian / qizhengkin / xianqin also read gender + place; forward them when present (no-op for the rest).
        for extra in ("gender", "lat", "lon", "gpsLat", "gpsLon", "zone"):
            if payload.get(extra) is not None:
                remote_payload[extra] = payload.get(extra)
        options = payload.get("options")
        if isinstance(options, dict):
            remote_payload.update(options)
        response = self._call_remote(endpoint, remote_payload)
        if isinstance(response, dict) and response.get("ResultCode") not in (None, 0):
            raise ToolValidationError(
                f"{key} 引擎返回错误：{response.get('Result')}",
                code="tool.shenshu_engine_error",
                details={"technique": key, "result": response.get("Result")},
            )
        raw_snapshot = response.get("snapshot") if isinstance(response, dict) else None
        snapshot_text = f"{raw_snapshot}".strip() if raw_snapshot else ""
        if not snapshot_text:
            # A reachable engine that returns no `snapshot` is an OLD chart-service build: the 神数 srv
            # only emits `snapshot` once the current source's build_snapshot() is present. Fail loudly
            # instead of returning a hollow export, so the agent can tell the user to update 星阙 / use
            # the bundled runtime (rather than silently producing an empty reading).
            raise ToolTransportError(
                f"{key} 引擎未返回 snapshot（命中的图表服务构建过旧，缺该神数的 snapshot 输出）。"
                "请更新 星阙 App 或改用 skill 自带的离线 runtime。",
                code="transport.shenshu_snapshot_unavailable",
                details={"technique": key, "endpoint": endpoint, "engine": response.get("engine") if isinstance(response, dict) else None},
            )
        return {
            "engine": response.get("engine") if isinstance(response, dict) else key,
            "raw": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique=key, snapshot_text=snapshot_text),
        }

    def _run_horary_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 卜卦 (horary): cast the traditional chart at the question moment, then run the vendored 星阙
        # horary engine (runHorary + buildHorarySnapshot) over it. category drives the quesited house.
        category = f"{payload.get('category') or 'general'}".strip() or "general"
        chart_payload = {**payload, "predictive": 0, "tradition": payload.get("tradition", 1)}
        for stale in ("datetime", "dirZone", "dirLat", "dirLon", "category"):
            chart_payload.pop(stale, None)
        response = self._call_remote("/chart", chart_payload)
        snapshot_text, data, snapshot_error = "", {}, None
        try:
            js = self.js_client.run("horary", {"chart": response, "category": category})
            if isinstance(js, dict):
                snapshot_text = f"{js.get('snapshot_text') or ''}".strip()
                data = js.get("data") if isinstance(js.get("data"), dict) else {}
                # the JS engine resolves an unknown category back to 'general'; reflect that.
                category = f"{js.get('category') or category}".strip() or category
        except Exception as exc:  # don't fail the chart, but don't hide the empty snapshot either
            snapshot_error = str(exc)
            logger.warning("horary JS engine failed (category=%s): %s", category, exc)
        result = {
            "chart": response.get("chart"),
            "category": category,
            "judgment": data,
            "raw": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="horary", snapshot_text=snapshot_text),
        }
        if snapshot_error:
            result["snapshot_error"] = snapshot_error
        return result

    def _run_election_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 择日 (electional): cast the traditional chart at a candidate moment, then run the vendored 星阙
        # election engine (runElection + buildElectionSnapshot). topicId drives the rule pack + hard flags.
        topic_id = f"{payload.get('topicId') or payload.get('topic') or 'marriage'}".strip() or "marriage"
        chart_payload = {**payload, "predictive": 0, "tradition": payload.get("tradition", 1)}
        for stale in ("datetime", "dirZone", "dirLat", "dirLon", "topicId", "topic"):
            chart_payload.pop(stale, None)
        response = self._call_remote("/chart", chart_payload)
        snapshot_text, data, snapshot_error = "", {}, None
        try:
            js = self.js_client.run("election", {"chart": response, "topicId": topic_id})
            if isinstance(js, dict):
                snapshot_text = f"{js.get('snapshot_text') or ''}".strip()
                data = js.get("data") if isinstance(js.get("data"), dict) else {}
                # the JS engine resolves an unknown topicId back to 'marriage'; reflect that.
                topic_id = f"{js.get('topicId') or topic_id}".strip() or topic_id
        except Exception as exc:  # don't fail the chart, but don't hide the empty snapshot either
            snapshot_error = str(exc)
            logger.warning("election JS engine failed (topicId=%s): %s", topic_id, exc)
        result = {
            "chart": response.get("chart"),
            "topicId": topic_id,
            "judgment": data,
            "raw": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="election", snapshot_text=snapshot_text),
        }
        if snapshot_error:
            result["snapshot_error"] = snapshot_error
        return result

    def _run_yearsystem129_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 129年系统: data is computed server-side and carried in response.predictives.yearsystem129
        # only when the chart is cast with predictive truthy.
        chart_payload = {**payload, "predictive": 1}
        chart_payload.pop("datetime", None)
        chart_payload.pop("dirZone", None)
        response = self._call_remote("/chart", chart_payload)
        snapshot_text = _build_yearsystem129_snapshot_text(response)
        return {
            "chart": response.get("chart"),
            "raw": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="yearsystem129", snapshot_text=snapshot_text),
        }

    def _run_persiandirected_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 波斯向运 (Persian Directed): pure arithmetic off the natal chart objects/houses/birth (1°/year).
        chart_payload = {**payload, "predictive": 0}
        chart_payload.pop("datetime", None)
        chart_payload.pop("dirZone", None)
        response = self._call_remote("/chart", chart_payload)
        snapshot_text = _build_persiandirected_snapshot_text(response)
        return {
            "chart": response.get("chart"),
            "raw": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="persiandirected", snapshot_text=snapshot_text),
        }

    def _run_mundane_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 世俗入宫盘 (mundane ingress): (1) get the precise solar-term ingress moment for the year via
        # /jieqi/year, (2) cast a /chart at that moment, (3) enrich with the v2.4.0 natal extras, then
        # (4) prepend a [世俗入宫] section to the astrochart snapshot. Mirrors 星阙 MundaneMain.
        year = f"{payload.get('year', '')}".strip()
        term = f"{payload.get('ingressTerm') or '春分'}".strip()
        zone = payload.get("zone") or "+08:00"
        lon = payload.get("lon")
        lat = payload.get("lat")
        seed_payload = {
            "year": year,
            "ad": payload.get("ad", 1),
            "zone": zone,
            "lon": lon or "116e23",
            "lat": "23n26",  # jieqi MOMENT is global; lat only affects the (unused) seed chart.
            "gpsLat": 23.43,
            "gpsLon": payload.get("gpsLon") if payload.get("gpsLon") is not None else 116.38,
            "timeAlg": 0,
            "jieqis": [term],
            "seedOnly": 1,
        }
        seed_response = self._call_remote("/jieqi/year", seed_payload)
        jieqi24 = seed_response.get("jieqi24") if isinstance(seed_response, dict) else None
        ingress_time = ""
        if isinstance(jieqi24, list):
            for entry in jieqi24:
                if isinstance(entry, dict) and f"{entry.get('jieqi')}".strip() == term and entry.get("time"):
                    ingress_time = f"{entry.get('time')}".strip()
                    break
        if not ingress_time:
            raise ToolValidationError(
                f"无法取得 {year} 年「{term}」的入宫时刻。",
                code="tool.mundane_ingress_unavailable",
                details={"year": year, "ingressTerm": term, "jieqi24_count": len(jieqi24) if isinstance(jieqi24, list) else 0},
            )
        date_part, _, time_part = ingress_time.partition(" ")
        chart_payload = {
            "date": date_part,
            "time": time_part or "00:00:00",
            "zone": zone,
            "lat": lat or "23n26",
            "lon": lon or "116e23",
            "gpsLat": payload.get("gpsLat"),
            "gpsLon": payload.get("gpsLon"),
            "ad": payload.get("ad", 1),
            "hsys": payload.get("hsys", 0),
            "tradition": payload.get("tradition", False),
            "predictive": 0,
        }
        chart_response = self._call_remote("/chart", chart_payload)
        chart_response = self._attach_natal_extras("mundane", chart_response)
        head = "\n".join(["[世俗入宫]", f"入宫节气：{term}", f"年份：{year or '-'}", f"入宫时刻：{ingress_time}"])
        # 子盘群：新月/满月/日月食/地区盘/行星周期 + 世俗宫义/定局·年主·盘主/入境骨架/地理分野/地区盘推运。
        subchart_sections = self._build_mundane_subchart_sections(
            base_chart_payload=chart_payload,
            seed_payload=seed_payload,
            ingress_response=chart_response,
            ingress_time=ingress_time,
            year=year,
            zone=zone,
        )
        subcharts_text = _render_snapshot_text(subchart_sections) if subchart_sections else ""
        body = _build_astro_snapshot_text(chart_payload, chart_response)
        snapshot_text = "\n\n".join(part for part in (head, subcharts_text, body) if part).strip()
        result = {
            "ingressTerm": term,
            "ingressYear": year,
            "ingressMoment": ingress_time,
            "chart": chart_response.get("chart"),
            "raw": chart_response,
            "snapshot_text": snapshot_text,
        }
        result["export_snapshot"] = self._augment_export_payload(technique="mundane", snapshot_text=snapshot_text)
        return result

    def _build_mundane_subchart_sections(
        self,
        *,
        base_chart_payload: dict[str, Any],
        seed_payload: dict[str, Any],
        ingress_response: dict[str, Any],
        ingress_time: str,
        year: str,
        zone: str,
    ) -> list[tuple[str, str]]:
        # 每个子盘独立 try/except：任一端点失败只降级该段为说明文本，绝不破坏世俗盘主流程。
        ing_date = base_chart_payload.get("date")
        ing_time = base_chart_payload.get("time")
        lat = base_chart_payload.get("lat")
        lon = base_chart_payload.get("lon")
        try:
            year_num = int(str(year).strip())
        except (TypeError, ValueError):
            year_num = 0
        sections: list[tuple[str, str]] = []

        # ── 新月图 / 满月图：自入宫时刻回溯最近朔望，再自该朔望回溯得另一相，一朔一望各起子盘 ──
        syz_by_type: dict[str, dict[str, Any]] = {}
        try:
            s1 = self._call_remote(
                "/astroextra/prenatal_syzygy",
                {"date": ing_date, "time": ing_time, "zone": zone, "lat": lat, "lon": lon},
            )
            if isinstance(s1, dict) and s1.get("type"):
                syz_by_type[s1["type"]] = s1
                # 另一相恒在首相之前 ~14.77 天：探针取首相前一日再回溯。若直接从首相时刻起搜，
                # 该时刻按秒舍入恰落在真朔/望点之后时，回溯会把同一相当场重捕，另一相就丢了。
                probe_date, probe_time = s1.get("date"), s1.get("time")
                try:
                    probe_dt = datetime.strptime(f"{probe_date} {probe_time}", "%Y-%m-%d %H:%M:%S") - timedelta(days=1)
                    probe_date, probe_time = probe_dt.strftime("%Y-%m-%d"), probe_dt.strftime("%H:%M:%S")
                except (TypeError, ValueError):
                    pass
                s2 = self._call_remote(
                    "/astroextra/prenatal_syzygy",
                    {"date": probe_date, "time": probe_time, "zone": zone, "lat": lat, "lon": lon},
                )
                if isinstance(s2, dict) and s2.get("type") and s2["type"] not in syz_by_type:
                    syz_by_type[s2["type"]] = s2
        except Exception as exc:  # noqa: BLE001 - degrade to a note, never break mundane
            logger.warning("mundane prenatal_syzygy failed: %s", exc)
        for title, syz_type, phase_cn in (("新月图", "new", "朔（新月·日月合）"), ("满月图", "full", "望（满月·日月冲）")):
            syz = syz_by_type.get(syz_type)
            if not isinstance(syz, dict):
                sections.append((title, f"未能定位入宫前最近的{phase_cn}。"))
                continue
            moment = syz.get("datetime") or f"{syz.get('date', '')} {syz.get('time', '')}".strip()
            lines = [
                f"{phase_cn}时刻：{moment}",
                f"日黄经 {syz.get('sunLon')}°，月黄经 {syz.get('moonLon')}°",
            ]
            try:
                sub_chart = self._call_remote("/chart", {**base_chart_payload, "date": syz.get("date"), "time": syz.get("time")})
                digest = _mundane_chart_digest(sub_chart)
                if digest:
                    lines.append("子盘四轴/日月：" + "；".join(digest))
            except Exception as exc:  # noqa: BLE001
                logger.warning("mundane %s chart failed: %s", title, exc)
            sections.append((title, "\n".join(lines)))

        # ── 日食图 / 月食图：eclipsedetail 只回全球食时长（食时长定则的关键量），呈影响时长判词 ──
        for title, kind, phase_cn, unit_default, rule in (
            ("日食图", "solar", "日食", "年", "日食时长 N 小时 → 影响约 N 年"),
            ("月食图", "lunar", "月食", "月", "月食时长 N 小时 → 影响约 N 月"),
        ):
            try:
                ed = self._call_remote(
                    "/astroextra/eclipsedetail",
                    {"date": ing_date, "time": ing_time, "zone": zone, "eclipseKind": kind},
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("mundane eclipsedetail(%s) failed: %s", kind, exc)
                ed = {}
            if isinstance(ed, dict) and ed.get("durationHours"):
                unit = ed.get("influenceUnit") or unit_default
                sections.append((
                    title,
                    "\n".join([
                        f"自入宫时刻顺推最近{phase_cn}：全球食持续约 {ed.get('durationHours')} 小时。",
                        f"食时长定则（{rule}）→ 本次影响约 {ed.get('influence')} {unit}。",
                        "（食盘极大时刻的整轮定盘属交互功能，此处给出无头可复算的影响时长判词。）",
                    ]),
                ))
            else:
                sections.append((title, f"自入宫时刻顺推未检索到{phase_cn}。"))

        # ── 地区盘：以入宫（全球统一）时刻定盘于格林尼治（世界年图基准），与本地入宫盘对照 ──
        try:
            world_chart = self._call_remote(
                "/chart",
                {**base_chart_payload, "lat": "51n29", "lon": "0e00", "gpsLat": 51.48, "gpsLon": 0.0},
            )
            digest = _mundane_chart_digest(world_chart)
            body = [f"以入宫时刻（{ingress_time}）定盘于格林尼治（0°经线 51°29′N，世界年图基准）："]
            body.extend(digest or ["未取得地区盘轴点。"])
            body.append("——同一天象、异地宫位；与上文本地入宫盘四轴对照可见地域落点差异。")
            sections.append(("地区盘", "\n".join(body)))
        except Exception as exc:  # noqa: BLE001
            logger.warning("mundane world chart failed: %s", exc)
            sections.append(("地区盘", "未能取得世界年图基准盘。"))

        # ── 行星周期：木土大合相（前后 20 年最近三次）+ Barbault 行星聚散指数拐点 ──
        cycle_lines: list[str] = []
        if year_num:
            try:
                gc = self._call_remote("/astroextra/greatconj", {"startYear": year_num - 20, "endYear": year_num + 20})
                conjs = gc.get("conjunctions") if isinstance(gc, dict) else None
                if isinstance(conjs, list) and conjs:
                    nearest = sorted(conjs, key=lambda c: abs(int(c.get("year", 0)) - year_num))[:3]
                    cycle_lines.append("木土大合相（前后 20 年内，至多三次）：")
                    for c in sorted(nearest, key=lambda c: int(c.get("year", 0))):
                        cycle_lines.append(f"  {c.get('year')}-{int(c.get('month', 0)):02d} 合于 {_lon_to_sign_degree(c.get('lon'))}")
            except Exception as exc:  # noqa: BLE001
                logger.warning("mundane greatconj failed: %s", exc)
            try:
                bb = self._call_remote(
                    "/astroextra/barbault",
                    {"startYear": year_num - 10, "endYear": year_num + 10, "stepMonths": 1},
                )
                extrema = bb.get("extrema") if isinstance(bb, dict) else None
                if isinstance(extrema, list) and extrema:
                    near = sorted(extrema, key=lambda e: abs(int(e.get("year", 0)) - year_num))[:2]
                    planets = "、".join(str(p) for p in (bb.get("planets") or []))
                    cycle_lines.append(f"Barbault 行星聚散指数（{planets}；满值 {bb.get('maxIndex')}）最近拐点：")
                    for e in sorted(near, key=lambda e: int(e.get("year", 0))):
                        kind_cn = "极小（聚集·危机/紧张）" if e.get("kind") == "min" else "极大（四散·扩张/繁荣）"
                        cycle_lines.append(f"  {e.get('year')}-{int(e.get('month', 0)):02d} 指数 {e.get('index')} {kind_cn}")
            except Exception as exc:  # noqa: BLE001
                logger.warning("mundane barbault failed: %s", exc)
        sections.append(("行星周期", "\n".join(cycle_lines) if cycle_lines else "未能取得慢星周期数据（需有效年份）。"))

        # ── 世俗宫义（通行定则静态释义）──
        sections.append(("世俗宫义", "\n".join(_MUNDANE_HOUSE_MEANINGS)))

        # ── 定局·年主/盘主：上升座主落点 + 二分二至发光体宫位 ──
        sections.append(("定局·年主/盘主", "\n".join(_mundane_year_lord_lines(ingress_response))))

        # ── 入境骨架：四轴星座 + 临角行星 ──
        skel = _mundane_skeleton_lines(ingress_response)
        sections.append(("入境骨架", "\n".join(skel) if skel else "本盘缺四轴信息。"))

        # ── 地理分野（托勒密星座—地域配当静态表）+ 上升所属 ──
        alloc_lines = list(_MUNDANE_PTOLEMAIC_ALLOCATION)
        asc_obj = _get_objects_map(_top_level_chart_wrap(ingress_response)).get("Asc")
        if isinstance(asc_obj, dict) and asc_obj.get("sign") is not None:
            alloc_lines.append(f"——本盘上升为 {_astro_msg(asc_obj.get('sign'))}，当年天象着重投射于其对应地域。")
        sections.append(("地理分野", "\n".join(alloc_lines)))

        # ── 地区盘推运：年度四季入宫时刻序列（地区盘随每季太阳入基本宫推移）──
        prog_rows: list[str] = []
        try:
            sy = self._call_remote(
                "/jieqi/year",
                {**seed_payload, "jieqis": ["春分", "夏至", "秋分", "冬至"]},
            )
            j24 = sy.get("jieqi24") if isinstance(sy, dict) else None
            if isinstance(j24, list):
                want = ["春分", "夏至", "秋分", "冬至"]
                by_term = {
                    str(e.get("jieqi")).strip(): str(e.get("time")).strip()
                    for e in j24
                    if isinstance(e, dict) and str(e.get("jieqi")).strip() in want and e.get("time")
                }
                for t in want:
                    if t in by_term:
                        prog_rows.append(f"  {t}入宫：{by_term[t]}")
        except Exception as exc:  # noqa: BLE001
            logger.warning("mundane seasonal ingress failed: %s", exc)
        prog_body = ["年度四季入宫定盘序列（地区盘随每季太阳入基本宫逐季推移）："]
        prog_body.extend(prog_rows or ["未能取得四季入宫时刻。"])
        sections.append(("地区盘推运", "\n".join(prog_body)))

        return sections

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

    def _run_tarot_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 塔罗：以起卦时刻确定性抽牌（seed 由 年月日时分 派生，或用户显式 seed），core-js tarot 引擎 SHA-256种子洗牌+解读。
        seed = payload.get("seed")
        if not seed:
            parts = _ken_datetime_parts(payload)
            seed = f"{parts['year']:04d}{parts['month']:02d}{parts['day']:02d}{parts['hour']:02d}{parts['minute']:02d}"
        js_payload: dict[str, Any] = {
            "seed": str(seed),
            "question": payload.get("question") or "",
            "spread": payload.get("spread") or "three",
            "deck": payload.get("deck") or "rws",
        }
        if payload.get("usesReversals") is False:
            js_payload["usesReversals"] = False
        try:
            result = self.js_client.run("tarot", js_payload)
        except ToolTransportError:
            result = {}
        snapshot_text = result.get("snapshot_text") if isinstance(result, dict) else ""
        return {
            "deck": (isinstance(result, dict) and result.get("deck")) or js_payload["deck"],
            "spread": (isinstance(result, dict) and result.get("spread")) or js_payload["spread"],
            "seed": str(seed),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="tarot", snapshot_text=snapshot_text),
        }

    def _run_geomancy_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 天文地占：以起卦时刻确定性起卦（castMethod='time' + timeSeed 由 年月日时分 派生，同盘可复现），
        # 后端 /geomancy/reading 由 4 母卦推 16 图形 + 十二宫图形入宫 + 判官/见证/解读技法。
        parts = _ken_datetime_parts(payload)
        time_seed = int(f"{parts['year']:04d}{parts['month']:02d}{parts['day']:02d}{parts['hour']:02d}{parts['minute']:02d}")
        response = self._call_remote(
            "/geomancy/reading",
            {
                "question": payload.get("question") or "",
                "questionType": payload.get("questionType") or "custom",
                "castMethod": "time",
                "timeSeed": time_seed,
                "profile": payload.get("profile") or "european_classical",
            },
        )
        snapshot_text = _build_geomancy_snapshot_text(response if isinstance(response, dict) else {})
        return {
            "reading": response.get("reading") if isinstance(response, dict) else None,
            "figures": response.get("figures") if isinstance(response, dict) else None,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="geomancy", snapshot_text=snapshot_text),
        }

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
            # 未手动摇卦 (lines 空) → 以时起卦，按四柱干支 + 时辰确定性生成 (不同时间不同卦)。
            lines = _time_based_gua_lines(nongli, payload)
        current_code = payload.get("gua_code") or _derive_gua_code(lines)
        changed_code = payload.get("changed_code") or _derive_changed_gua_code(lines)
        descs = self._call_remote("/gua/desc", {"name": [current_code, changed_code]})
        # 断卦结构（六爻全流派 analyzeLiuyao 引擎，core-js）：纳甲/世应/六亲/用神/旺衰/飞伏/六神/动变。
        # 优雅降级：无 node / 引擎失败 → struct_text 空 → 快照不出 [断卦结构] 段（列 optional，不误报 missing）。
        struct_text = ""
        try:
            struct = self.js_client.run("liuyao", {"lines": lines, "nongli": nongli})
            struct_text = struct.get("snapshot_text") or ""
        except ToolTransportError:
            struct_text = ""
        snapshot_text = _build_sixyao_snapshot_text(payload, nongli, current_code, changed_code, lines, descs, struct_text)
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
                "input_contract": build_tool_input_contract(tool.name),
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
        if definition.name in {"liureng_gods", "liureng_runyear"}:
            return self._run_liureng_tool(definition.name, payload)
        if definition.name == "suzhan":
            return self._run_suzhan_tool(payload)
        if definition.name == "sixyao":
            return self._run_sixyao_tool(payload)
        if definition.name == "geomancy":
            return self._run_geomancy_tool(payload)
        if definition.name == "tarot":
            return self._run_tarot_tool(payload)
        if definition.name == "tongshefa":
            return self._run_tongshefa_tool(payload)
        if definition.name == "canping":
            return self._run_canping_tool(payload)
        if definition.name == "heluo":
            return self._run_heluo_tool(payload)
        if definition.name == "sanshiunited":
            return self._run_sanshiunited_tool(payload)
        if definition.name == "hellen_chart":
            return self._run_hellen_chart_tool(payload)
        if definition.name == "guolao_chart":
            return self._run_guolao_chart_tool(payload)
        if definition.name == "germany":
            return self._run_germany_tool(payload)
        if definition.name == "harmonic":
            return self._run_harmonic_tool(payload)
        if definition.name == "agepoint":
            return self._run_agepoint_tool(payload)
        if definition.name == "distributions":
            return self._run_distributions_tool(payload)
        if definition.name == "jaynesprog":
            return self._run_jaynesprog_tool(payload)
        if definition.name == "vedicprog":
            return self._run_vedicprog_tool(payload)
        if definition.name == "planetaryarc":
            return self._run_planetaryarc_tool(payload)
        if definition.name == "planetaryages":
            return self._run_planetaryages_tool(payload)
        if definition.name == "balbillus":
            return self._run_balbillus_tool(payload)
        if definition.name == "yearsystem129":
            return self._run_yearsystem129_tool(payload)
        if definition.name == "persiandirected":
            return self._run_persiandirected_tool(payload)
        if definition.name in {"triplicityrulers", "keypoints", "lunationphase"}:
            return self._run_progextra_js_tool(payload, definition.name)
        if definition.name == "extrareturns":
            return self._run_extrareturns_tool(payload)
        if definition.name == "horary":
            return self._run_horary_tool(payload)
        if definition.name == "election":
            return self._run_election_tool(payload)
        if definition.name in _SHENSHU_ENDPOINTS:
            return self._run_shenshu_tool(payload, definition.name)
        if definition.name == "mundane":
            return self._run_mundane_tool(payload)
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
                payload = normalize_request_payload(payload)
                validated = definition.input_model.model_validate(payload)
            except ValidationError as exc:
                trace["error_code"] = "tool.invalid_payload"
                errors = exc.errors()
                raise ToolValidationError(
                    f"Invalid payload for tool `{tool_name}`.",
                    code="tool.invalid_payload",
                    details={
                        "errors": errors,
                        "agent_recovery": build_validation_recovery(
                            operation_name=f"tool.{tool_name}",
                            tool_name=tool_name,
                            errors=errors,
                        ),
                    },
                ) from exc

            input_normalized = validated.model_dump(exclude_none=True)
            memory_ref = None

            try:
                if definition.execution == "local":
                    response_data = self._run_local_tool(definition, input_normalized)
                else:
                    assert definition.endpoint is not None
                    response_data = self._call_remote(definition.endpoint, input_normalized)
                    response_data = self._attach_predictive_chart_context(tool_name, input_normalized, response_data)
                response_data = self._attach_natal_extras(tool_name, response_data)
                response_data = self._attach_classical_analysis(tool_name, input_normalized, response_data)
                response_data = self._attach_bazi_geju(tool_name, response_data)
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
            except Exception as exc:  # noqa: BLE001 - last-resort guard: a surface/dispatch must never crash
                # Tool execution and the snapshot/summary/export post-processing touch backend-shaped
                # data and can raise unexpected ValueError/KeyError/IndexError/TypeError. Convert those
                # into a structured ok=False envelope instead of letting a traceback escape the CLI or
                # break the MCP session / abort a whole dispatch. (Bad-payload ValidationError is handled
                # separately above and intentionally still raises.)
                trace["error_code"] = "tool.internal_error"
                envelope = ToolEnvelope(
                    ok=False,
                    tool=tool_name,
                    version=__version__,
                    input_normalized=input_normalized,
                    data={},
                    summary=[f"工具 `{tool_name}` 调用时发生内部错误。"],
                    warnings=[],
                    memory_ref=None,
                    error=ErrorInfo(
                        code="tool.internal_error",
                        message=str(exc),
                        details={"exception_type": type(exc).__name__},
                    ),
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
                errors = exc.errors()
                raise ToolValidationError(
                    "Invalid payload for memory answer record.",
                    code="memory.answer.invalid_payload",
                    details={
                        "errors": errors,
                        "agent_recovery": build_validation_recovery(operation_name="memory_record_answer", errors=errors),
                    },
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
                errors = exc.errors()
                raise ToolValidationError(
                    "Invalid payload for memory query.",
                    code="memory.query.invalid_payload",
                    details={
                        "errors": errors,
                        "agent_recovery": build_validation_recovery(operation_name="memory_query", errors=errors),
                    },
                ) from exc

            results = self.store.query_runs(
                run_id=request.run_id,
                tool=request.tool,
                entity=request.entity,
                text=request.text,
                artifact_kind=request.artifact_kind,
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
                errors = exc.errors()
                raise ToolValidationError(
                    "Invalid payload for memory show.",
                    code="memory.show.invalid_payload",
                    details={
                        "errors": errors,
                        "agent_recovery": build_validation_recovery(operation_name="memory_show", errors=errors),
                    },
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

    def report_template(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.tracer.span(
            workflow_name="report.template",
            metadata={"entrypoint": "report.template", "payload": payload},
        ) as trace:
            try:
                request = ReportTemplateInput.model_validate(payload)
                run, source_artifact = self._load_report_source(request.run_id, request.tool_name)
            except ValidationError as exc:
                trace["error_code"] = "report.template.invalid_payload"
                errors = exc.errors()
                raise ToolValidationError(
                    "Invalid payload for report template.",
                    code="report.template.invalid_payload",
                    details={
                        "errors": errors,
                        "agent_recovery": build_validation_recovery(operation_name="report_template", errors=errors),
                    },
                ) from exc
            template = self.report_builder.build_template(
                run=run,
                source_artifact=source_artifact,
                language=request.language,
            )
            template["trace_id"] = trace["trace_id"]
            template["group_id"] = trace["group_id"]
            trace["run_id"] = request.run_id
            trace["tool_name"] = template.get("tool_name")
            return template

    def report_render(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.tracer.span(
            workflow_name="report.render",
            metadata={"entrypoint": "report.render", "payload": payload},
        ) as trace:
            try:
                request = ReportRenderInput.model_validate(payload)
                normalized_format = self._normalize_report_format(request.format)
                run, source_artifact = self._load_report_source(request.run_id, request.tool_name)
                source_tool_name = str(source_artifact.get("tool_name") or request.tool_name or "")
                normalized_ai_report = self._normalize_report_ai_payload(
                    ai_report=request.ai_report,
                    ai_answer_text=request.ai_answer_text,
                )
                if not normalized_ai_report and not self._run_has_report_ai(run):
                    template = self.report_builder.build_template(
                        run=run,
                        source_artifact=source_artifact,
                        language=request.language,
                    )
                    trace["run_id"] = request.run_id
                    trace["tool_name"] = source_tool_name
                    trace["success"] = True
                    return self._report_ai_required_response(
                        run_id=request.run_id,
                        tool_name=source_tool_name,
                        format_name=normalized_format,
                        template=template,
                        tool_result=None,
                        trace_id=trace["trace_id"],
                        group_id=trace["group_id"],
                    )
                answer_writeback = self._record_report_ai_if_present(
                    run=run,
                    tool_name=source_tool_name,
                    ai_report=normalized_ai_report,
                    format_name=normalized_format,
                )
                if answer_writeback:
                    run, source_artifact = self._load_report_source(request.run_id, request.tool_name)
                document = self.report_builder.build_document(
                    run=run,
                    source_artifact=source_artifact,
                    language=request.language,
                    title=request.title,
                    ai_report=normalized_ai_report,
                    include_raw_json=request.include_raw_json,
                )
                tool_name = str(document["source"]["tool_name"])
                output_path = (
                    Path(request.output_path).expanduser().resolve()
                    if request.output_path
                    else self.store.default_report_path(
                        run_id=request.run_id,
                        tool_name=tool_name,
                        format_name=normalized_format,
                    )
                )
                rendered = render_report(document, output_path=output_path, format_name=normalized_format)
                artifact = self.store.record_report_artifact(
                    run_id=request.run_id,
                    tool_name=tool_name,
                    format_name=normalized_format,
                    path=Path(rendered["path"]),
                    trace_id=trace["trace_id"],
                    group_id=trace["group_id"],
                )
            except ValidationError as exc:
                trace["error_code"] = "report.render.invalid_payload"
                errors = exc.errors()
                raise ToolValidationError(
                    "Invalid payload for report render.",
                    code="report.render.invalid_payload",
                    details={
                        "errors": errors,
                        "agent_recovery": build_validation_recovery(operation_name="report_render", errors=errors),
                    },
                ) from exc
            except ValueError as exc:
                trace["error_code"] = "report.render.failed"
                raise ToolValidationError(
                    str(exc),
                    code="report.render.failed",
                    details={"payload": payload},
                ) from exc

            result = {
                **artifact,
                "document_schema": document["schema"],
                "title": document["title"],
                "source": document["source"],
                "answer_writeback": answer_writeback,
                "summary": [f"已生成 {normalized_format.upper()} 结构化报告：{artifact['artifact_path']}"],
                "trace_id": trace["trace_id"],
                "group_id": trace["group_id"],
            }
            trace["run_id"] = request.run_id
            trace["artifact_path"] = artifact["artifact_path"]
            trace["success"] = True
            return result

    def report_from_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.tracer.span(
            workflow_name="report.from_tool",
            metadata={"entrypoint": "report.from_tool", "payload": payload},
        ) as trace:
            try:
                request = ReportFromToolInput.model_validate(payload)
                normalized_format = self._normalize_report_format(request.format)
            except ValidationError as exc:
                trace["error_code"] = "report.from_tool.invalid_payload"
                errors = exc.errors()
                raise ToolValidationError(
                    "Invalid payload for report from tool.",
                    code="report.from_tool.invalid_payload",
                    details={
                        "errors": errors,
                        "agent_recovery": build_validation_recovery(operation_name="report_from_tool", errors=errors),
                    },
                ) from exc

            result = self.run_tool(
                request.tool_name,
                request.payload,
                save_result=True,
                query_text=request.question,
                group_id=trace["group_id"],
            )
            if not result.memory_ref:
                raise ToolValidationError(
                    "Tool result was not saved and cannot be rendered as a report.",
                    code="report.from_tool.unsaved_result",
                    details={"tool_name": request.tool_name},
                )
            normalized_ai_report = self._normalize_report_ai_payload(
                ai_report=request.ai_report,
                ai_answer_text=request.ai_answer_text,
            )
            if not normalized_ai_report:
                run, source_artifact = self._load_report_source(result.memory_ref.run_id, request.tool_name)
                template = self.report_builder.build_template(
                    run=run,
                    source_artifact=source_artifact,
                    language=request.language,
                )
                trace["run_id"] = result.memory_ref.run_id
                trace["tool_name"] = request.tool_name
                trace["success"] = True
                return self._report_ai_required_response(
                    run_id=result.memory_ref.run_id,
                    tool_name=request.tool_name,
                    format_name=normalized_format,
                    template=template,
                    tool_result={
                        "ok": result.ok,
                        "tool": result.tool,
                        "input_normalized": result.input_normalized,
                        "summary": result.summary,
                        "memory_ref": result.memory_ref.model_dump(mode="json") if result.memory_ref else None,
                        "trace_id": result.trace_id,
                        "group_id": result.group_id,
                    },
                    trace_id=trace["trace_id"],
                    group_id=trace["group_id"],
                )
            rendered = self.report_render(
                {
                    "run_id": result.memory_ref.run_id,
                    "tool_name": request.tool_name,
                    "format": normalized_format,
                    "language": request.language,
                    "title": request.title,
                    "ai_report": normalized_ai_report,
                    "include_raw_json": request.include_raw_json,
                    "output_path": request.output_path,
                }
            )
            rendered["tool_result"] = {
                "ok": result.ok,
                "tool": result.tool,
                "input_normalized": result.input_normalized,
                "summary": result.summary,
                "memory_ref": result.memory_ref.model_dump(mode="json") if result.memory_ref else None,
                "trace_id": result.trace_id,
                "group_id": result.group_id,
            }
            rendered["summary"] = [
                f"已调用 `{request.tool_name}` 并生成 {normalized_format.upper()} 结构化报告。",
                *rendered.get("summary", []),
            ]
            trace["run_id"] = result.memory_ref.run_id
            trace["artifact_path"] = rendered.get("artifact_path")
            trace["success"] = True
            return rendered

    def _report_ai_required_response(
        self,
        *,
        run_id: str,
        tool_name: str,
        format_name: str,
        template: dict[str, Any],
        tool_result: dict[str, Any] | None,
        trace_id: str,
        group_id: str,
    ) -> dict[str, Any]:
        ai_fillable = template.get("ai_fillable") if isinstance(template.get("ai_fillable"), dict) else {}
        conversation_brief = template.get("conversation_brief") if isinstance(template.get("conversation_brief"), dict) else {}
        return {
            "ok": True,
            "mode": "analysis_required",
            "needs_ai_analysis": True,
            "final_report_generated": False,
            "artifact_path": None,
            "format": format_name,
            "run_id": run_id,
            "tool_name": tool_name,
            "tool_result": tool_result,
            "report_template": template,
            "ai_process": {
                "schema": "horosa.skill.report.ai_process.v1",
                "input": "用户的时间、地点、事情和工具 payload 已保存到本地 run。",
                "conversation_brief": conversation_brief,
                "process": [
                    "读取 conversation_brief，明确用户问题、盘面上下文、解盘方法和输出口吻。",
                    "阅读 report_template.source_context.export_text/export_sections 中的真实起盘结果。",
                    "像在 AI 对话窗口里正式解盘一样，先给结论，再给盘面依据、推理过程、风险边界和建议。",
                    "把完整正文写入 ai_report.answer_text，同时填写 direct_answer、executive_summary、analysis_sections、recommendations、limitations、evidence。",
                    "最后调用 horosa_report_render 或 horosa_report_from_tool，并把 ai_report 一起传入，生成最终 JSON/DOCX/PDF 和 memory。",
                ],
                "output": "最终报告必须来自 AI 对真实盘结果和用户问题的分析；未填写 ai_report 时不会生成假装完成的最终解读报告。",
                "ai_report_skeleton": {
                    "analysis_focus": ai_fillable.get("analysis_focus", ""),
                    "answer_text": ai_fillable.get("answer_text", ""),
                    "direct_answer": ai_fillable.get("direct_answer", ""),
                    "executive_summary": ai_fillable.get("executive_summary", ""),
                    "analysis_sections": ai_fillable.get("analysis_sections", []),
                    "recommendations": ai_fillable.get("recommendations", []),
                    "limitations": ai_fillable.get("limitations", []),
                    "evidence": ai_fillable.get("evidence", []),
                    "follow_up_questions": ai_fillable.get("follow_up_questions", []),
                },
                "next_call": {
                    "tool": "horosa_report_render",
                    "payload": {
                        "run_id": run_id,
                        "tool_name": tool_name,
                        "format": format_name,
                        "ai_report": "<AI fills this object from ai_report_skeleton>",
                    },
                },
            },
            "summary": [
                "已完成起盘和本地保存；尚未生成最终报告，因为缺少 AI 对真实盘结果和用户问题的解读。",
                "请让接入的 AI 按 report_template 填写 ai_report 后，再调用 horosa_report_render 生成 PDF/DOCX/JSON 与 memory。",
            ],
            "trace_id": trace_id,
            "group_id": group_id,
        }

    def _normalize_report_format(self, value: str) -> str:
        normalized = str(value or "").lower().strip()
        if normalized not in {"json", "docx", "pdf"}:
            raise ValueError("format must be one of: json, docx, pdf")
        return normalized

    def _normalize_report_ai_payload(
        self,
        *,
        ai_report: dict[str, Any],
        ai_answer_text: str | None,
    ) -> dict[str, Any]:
        normalized = copy.deepcopy(ai_report) if isinstance(ai_report, dict) else {}
        answer_text = str(ai_answer_text or "").strip()
        if answer_text and not normalized.get("answer_text"):
            normalized["answer_text"] = answer_text
        if answer_text and not normalized.get("direct_answer"):
            normalized["direct_answer"] = self._first_nonempty_line(answer_text)
        return normalized

    def _first_nonempty_line(self, text: str) -> str:
        for line in str(text or "").splitlines():
            stripped = line.strip(" #*-：:")
            if stripped:
                return stripped[:240]
        return str(text or "").strip()[:240]

    def _run_has_report_ai(self, run: dict[str, Any]) -> bool:
        structured = run.get("ai_answer_structured")
        if isinstance(structured, dict) and self._report_ai_answer_text(structured):
            return True
        answer = run.get("ai_answer_text")
        return isinstance(answer, str) and bool(answer.strip())

    def _record_report_ai_if_present(
        self,
        *,
        run: dict[str, Any],
        tool_name: str,
        ai_report: dict[str, Any],
        format_name: str,
    ) -> dict[str, Any] | None:
        if not ai_report:
            return None
        answer_text = self._report_ai_answer_text(ai_report)
        if not answer_text:
            return None
        result = self.store.attach_ai_response(
            run_id=run["run_id"],
            user_question=run.get("user_question") or run.get("query_text"),
            ai_answer=answer_text,
            ai_answer_structured=ai_report,
            answer_meta={
                "source": "report_render",
                "tool_name": tool_name,
                "format": format_name,
                "schema": "horosa.skill.report.answer_writeback.v1",
            },
        )
        return {
            "ok": result["ok"],
            "run_id": result["run_id"],
            "source": "report_render",
            "tool_name": tool_name,
            "format": format_name,
            "answer_text_chars": len(answer_text),
            "manifest_path": result.get("manifest_path"),
        }

    def _report_ai_answer_text(self, ai_report: dict[str, Any]) -> str:
        for key in ("answer_text", "direct_answer", "executive_summary", "summary", "answer"):
            value = ai_report.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        sections = ai_report.get("analysis_sections")
        if isinstance(sections, list):
            for section in sections:
                if isinstance(section, dict):
                    value = section.get("body") or section.get("content")
                    if isinstance(value, str) and value.strip():
                        return value.strip()
                elif isinstance(section, str) and section.strip():
                    return section.strip()
        return ""

    def _load_report_source(self, run_id: str, tool_name: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
        runs = self.store.query_runs(run_id=run_id, tool=tool_name, include_payload=True, limit=1)
        if not runs:
            raise ToolValidationError(
                f"Run not found: {run_id}",
                code="report.run_not_found",
                details={"run_id": run_id, "tool_name": tool_name},
            )
        run = runs[0]
        artifacts = run.get("artifacts") if isinstance(run.get("artifacts"), list) else []
        candidates = [
            artifact
            for artifact in artifacts
            if artifact.get("kind") == "tool_result"
            and isinstance(artifact.get("payload"), dict)
            and (tool_name is None or artifact.get("tool_name") == tool_name)
        ]
        if not candidates and tool_name is None:
            candidates = [
                artifact
                for artifact in artifacts
                if artifact.get("kind") == "dispatch_result"
                and isinstance(artifact.get("payload"), dict)
            ]
        if not candidates:
            raise ToolValidationError(
                "No reportable tool artifact found for this run.",
                code="report.source_not_found",
                details={"run_id": run_id, "tool_name": tool_name},
            )
        def has_complete_export_contract(artifact: dict[str, Any]) -> bool:
            payload = artifact.get("payload")
            data = payload.get("data") if isinstance(payload, dict) else {}
            source_tool = str(artifact.get("tool_name") or "")
            if artifact.get("kind") != "tool_result" or source_tool not in TOOL_EXPORT_TECHNIQUE_MAP:
                return True
            return (
                isinstance(data, dict)
                and isinstance(data.get("export_snapshot"), dict)
                and isinstance(data.get("export_format"), dict)
            )

        source = next((artifact for artifact in candidates if has_complete_export_contract(artifact)), candidates[0])
        payload = source.get("payload")
        data = payload.get("data") if isinstance(payload, dict) else {}
        source_tool = str(source.get("tool_name") or "")
        if source.get("kind") == "tool_result" and source_tool in TOOL_EXPORT_TECHNIQUE_MAP and not (
            isinstance(data, dict)
            and isinstance(data.get("export_snapshot"), dict)
            and isinstance(data.get("export_format"), dict)
        ):
            raise ToolValidationError(
                "Selected artifact does not contain a complete export contract.",
                code="report.export_contract_missing",
                details={
                    "run_id": run_id,
                    "tool_name": source.get("tool_name"),
                    "artifact_count": len(candidates),
                    "source_ok": payload.get("ok") if isinstance(payload, dict) else None,
                    "source_error": payload.get("error") if isinstance(payload, dict) else None,
                },
            )
        return run, source

    def dispatch(self, payload: dict[str, Any], *, evaluation_case_id: str | None = None) -> DispatchEnvelope:
        try:
            request = DispatchInput.model_validate(payload)
        except ValidationError as exc:
            errors = exc.errors()
            raise ToolValidationError(
                "Invalid payload for horosa_dispatch.",
                code="dispatch.invalid_payload",
                details={
                    "errors": errors,
                    "agent_recovery": build_validation_recovery(
                        operation_name="horosa_dispatch",
                        tool_name="dispatch",
                        errors=errors,
                    ),
                },
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
            confirmation = {
                key: value
                for key, value in {
                    "agent_confirmed_settings": request.agent_confirmed_settings,
                    "defaults_accepted": request.defaults_accepted,
                    "clarification_notes": request.clarification_notes,
                }.items()
                if value is not None
            }
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

                payload_for_tool.update(confirmation)
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
