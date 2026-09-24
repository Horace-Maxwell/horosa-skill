from __future__ import annotations

import contextlib
import contextvars
import copy
import gzip
import logging
import math
import os
import re
import shutil
import sqlite3
import time
import uuid
from collections.abc import Iterator
from datetime import timezone, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from horosa_skill import __version__
from horosa_skill.agent_guidance import build_tool_input_contract, build_validation_recovery
from horosa_skill.astro_rulers import (
    HOUSE_SYSTEM_LABELS,
    build_dispositor_ruler_tail_lines,
    build_house_system_ruler_section_lines,
    derived_whole_sign_label_of,
)
from horosa_skill.astro_rulers import js_template_str as _js_template_str
from horosa_skill.astro_sidereal import nakshatra_lord_cn, sidereal_ayanamsa_label, zodiacal_display_text
from horosa_skill.time_basis import GUOLAO_TIME_BASIS_NOTE, build_time_basis_line
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
from horosa_skill.engine.astroextra_snapshots import (
    DEFAULT_MINOR_VARIANT,
    MINOR_VARIANT_LABEL,
    PROG_SNAPSHOT_VARIANTS,
    build_ephemeris_snapshot_text,
    build_prenatal_syzygy_snapshot_text,
    build_prog_snapshot_text,
    build_return_timeline_snapshot_text,
    split_syzygy_datetime,
)
from horosa_skill.engine.js_client import HorosaJsEngineClient
from horosa_skill.engine.registry import TOOL_DEFINITIONS, ToolDefinition
from horosa_skill.engine.router import select_tools
from horosa_skill.errors import DispatchResolutionError, HorosaSkillError, ToolTransportError, ToolValidationError, bilingual, recovery_for
from horosa_skill.exports import build_export_registry, get_technique_info, parse_export_content
from horosa_skill.exports.registry import AI_EXPORT_PRESET_SECTIONS, MIRRORED_UPSTREAM_AIEXPORT_VERSION
from horosa_skill.input_normalization import normalize_request_payload
from horosa_skill.knowledge import build_knowledge_registry, read_knowledge_entry, search_knowledge
from horosa_skill.memory.store import MemoryStore
from horosa_skill import predictive_text as _ptext
from horosa_skill.reports import ReportBuilder, render_report
from horosa_skill.reports.technique_card import build_technique_card, build_technique_report
from horosa_skill.decisions.layer import DecisionLayer, current_decision_records, decision_records
from horosa_skill.decisions.redact import build_meta_state
from horosa_skill.decisions.surfaces.extract import build_gender_question, gender_candidates, resolve_gender
from horosa_skill.decisions.surfaces.faithfulness import build_opinion_questions, build_opinion_state, summarize_opinion
from horosa_skill.decisions.surfaces.routing import build_routing_questions, resolve_routing
from horosa_skill.decisions.surfaces.zhancat import build_zhan_question, resolve_zhan

HECAN_SCHEMA = "horosa.skill.hecan.v1"
from horosa_skill.runtime import HorosaRuntimeManager
from horosa_skill.schemas.common import (
    TOOL_ENVELOPE_SCHEMA_VERSION,
    DispatchEnvelope,
    ErrorInfo,
    ToolEnvelope,
)
from horosa_skill.schemas.tools import (
    BaZiBirthInput,
    BirthInput,
    DispatchInput,
    LiuRengGodsInput,
    MemoryAnswerInput,
    MemoryQueryInput,
    MemoryShowInput,
    NongliTimeInput,
    ReportFromToolInput,
    ReportRenderInput,
    HecanInput,
    ReportTemplateInput,
    TechniqueReportInput,
    ZiWeiBirthInput,
)
from horosa_skill.shenshu_options import SHENSHU_OPTION_KNOBS, resolve_shenshu_options
from horosa_skill.tracing import TraceRecorder

logger = logging.getLogger(__name__)

# ---- 降级说明收集器（v0.36.0 A2）----
# 35 处「富化失败不许带崩主盘」的 except 分支此前只写 logger.warning：日志里有、信封里没有，agent 看到的是
# ok=True + warnings=[] + 少几段——静默降级。`_degrade` 把同一句话同时写日志并投进当前 run_tool 的收集器，
# 出信封时并入 envelope.warnings；嵌套 run_tool（三式合一/合参）的说明冒泡到外层。守卫：
# scripts/verify_silent_degrades.py（包内 `_degrade(` 计数棘轮，基线 0——降级点一律走 `_degrade`）。
_DEGRADE_NOTES: contextvars.ContextVar[list[str] | None] = contextvars.ContextVar("horosa_degrade_notes", default=None)
# 当前 run_tool 的自然语言原话（dispatch 传入的 query_text）：决策层的门类分类要读它，runner 签名不变。
_RUN_QUERY_TEXT: contextvars.ContextVar[str | None] = contextvars.ContextVar("horosa_run_query_text", default=None)


@contextlib.contextmanager
def _run_query_scope(query_text: str | None) -> Iterator[None]:
    token = _RUN_QUERY_TEXT.set(query_text)
    try:
        yield
    finally:
        _RUN_QUERY_TEXT.reset(token)


def _degrade(fmt: str, *args: Any, note: str | None = None) -> str:
    """记一次优雅降级：日志一句 + 当前工具调用的收集器一条（→ envelope.warnings）。返回给调用方的说明。"""
    message = (fmt % args) if args else fmt
    logger.log(logging.WARNING, "%s", message)
    text = note or f"降级：{message}——相关段落缺席，其余结果仍可用。"
    notes = _DEGRADE_NOTES.get()
    if notes is not None and text not in notes:
        notes.append(text)
    return text


# ---- 进度上报与取消检查点（v0.37.0 C6）----
# 分段扫描一次可跑 60 次后端请求、几分钟墙钟；这期间客户端**什么也看不到**，只能干等或按超时掐断
# （Codex 的 tool_timeout_sec 默认 60 秒，Cursor/VS Code 也各有默认）。ContextVar 让表层注入一个
# tick 回调，服务层每完成一段调一次；没人注入时是 no-op（CLI/测试路径零开销、零行为变化）。
# tick 同时是**取消检查点**：MCP 侧的实现先调 `anyio.from_thread.check_cancelled()`，客户端撤单后
# 下一段边界就抛 CancelledError（BaseException，不会被下面的 except Exception 吞掉），长扫描因此
# 能在段边界停下，而不是把剩下 50 次后端请求全跑完才发现没人要结果。
_TOOL_PROGRESS: contextvars.ContextVar[Any | None] = contextvars.ContextVar(
    "horosa_tool_progress", default=None
)


@contextlib.contextmanager
def progress_sink(tick: Any) -> Iterator[None]:
    """在本作用域内把进度回调交给服务层（表层用；tick 签名 (done, total, label)）。"""
    token = _TOOL_PROGRESS.set(tick)
    try:
        yield
    finally:
        _TOOL_PROGRESS.reset(token)


def _progress_tick(done: int, total: int, label: str) -> None:
    """报一次进度。未注入回调即 no-op；回调自身出错绝不能带崩正在跑的计算。"""
    tick = _TOOL_PROGRESS.get()
    if tick is None:
        return
    try:
        tick(done, total, label)
    except Exception:  # noqa: BLE001 - 进度是旁路，取消走 BaseException 不经此处
        logger.debug("progress tick failed", exc_info=True)


@contextlib.contextmanager
def _degrade_collector() -> Iterator[list[str]]:
    """一次 run_tool 的降级说明作用域；退出时冒泡到外层调用（嵌套工具的缺段外层也要知道）。"""
    parent = _DEGRADE_NOTES.get()
    notes: list[str] = []
    token = _DEGRADE_NOTES.set(notes)
    try:
        yield notes
    finally:
        _DEGRADE_NOTES.reset(token)
        if parent is not None:
            parent.extend(item for item in notes if item not in parent)


def _gender_label(value: Any, *, unknown: str = "未知") -> str:
    """性别值 → 中文标签（PR #17 @xipfs 的 _gender_label 收编）：True/1/'1'/'男'/'male'/'M'/'乾'→男；
    False/0/'0'/'女'/'female'/'F'/'坤'→女；其余（含 None/-1）→ unknown。"""
    if isinstance(value, str):
        key = value.strip().lower()
        if key in {"1", "男", "male", "m", "nan", "乾"}:
            return "男"
        if key in {"0", "女", "female", "f", "nv", "坤"}:
            return "女"
        return unknown
    if value is True or value == 1:
        return "男"
    if value is False or value == 0:
        return "女"
    return unknown


def _missing_sections_warning(response_data: Any) -> str | None:
    """预设段有缺 → 一条可读的「结果不完整」说明（此前只躺在 export_snapshot.missing_selected_sections 里）。"""
    export = response_data.get("export_snapshot") if isinstance(response_data, dict) else None
    if not isinstance(export, dict):
        return None
    missing = [f"{title}".strip() for title in (export.get("missing_selected_sections") or []) if f"{title}".strip()]
    if not missing:
        return None
    selected = export.get("selected_sections") or []
    shown = "、".join(missing[:8]) + ("…" if len(missing) > 8 else "")
    return (
        f"结果不完整：预设 {len(selected)} 段中 {len(missing)} 段未产出（{shown}）；"
        "缺段原因见 warnings 其余条目，清单见 export_snapshot.missing_selected_sections。"
    )


TOOL_EXPORT_TECHNIQUE_MAP: dict[str, str] = {
    "chart": "astrochart",
    "chart13": "astrochart_like",
    "chart12": "dwadasamsa",
    "draconic": "draconic",
    "babylon": "babylon",
    "xuanshi": "xuanshi",
    # v0.33.0 主线 I 新工具（bench 生成 case 与导出契约挂接都吃本表——漏登记有锁步测试守）。
    "qizhengelection": "qizhengelection",
    "india_rectify": "india_rectify",
    "planet_cycles": "planet_cycles",
    "jieqi_birth": "jieqi_birth",
    "huangli": "huangli",
    "tongshu": "tongshu",
    "relocation": "relocation",
    # 上游把这一族按出盘页面拆键（aiExport.js 的 ASTRO_LIKE_EXPORT_KEYS）；希腊盘与调波盘各有自己的
    # 导出键，不再共用 astrochart_like，否则两者的导出勾选会互相串。
    "hellen_chart": "hellenastro",
    "harmonic": "harmonic",
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
    "calendar_month": "calendar",
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
    "yizhangjing": "yizhangjing",
    "xiaoliuren": "xiaoliuren",
    "feigong": "feigong",
    "xiaochengtu": "xiaochengtu",
    "guice": "guice",
    "zhengchuan": "zhengchuan",
    "acg": "acg",
    "astrodata": "astrodata",
    "bazi_inverse": "bazi_inverse",
    "sanshiunited": "sanshiunited",
    "germany": "germany",
    "agepoint": "agepoint",
    "distributions": "distributions",
    "jaynesprog": "jaynesprog",
    "vedicprog": "vedicprog",
    # 上游 v3.11 星运四键（[Q-106/T-10] 三页 + [#80] 回归黄道二次推运）：工具名与导出技法键同名。
    "ephemeris": "ephemeris",
    "returntimeline": "returntimeline",
    "prenatalsyzygy": "prenatalsyzygy",
    "prog": "prog",
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
    "tianxing": "tianxing",
    "qimenzeri": "qimenzeri",
    # 择日十技法（v3.10.0）：工具名与导出技法键同名，逐个入表 —— bench 的「新增技法自动获得
    # 用例」只覆盖这张表（v0.33.0 教训）。
    "huanglizeri": "huanglizeri",
    "bazizeri": "bazizeri",
    "taiyizeri": "taiyizeri",
    "ziweizeri": "ziweizeri",
    "liurengzeri": "liurengzeri",
    "sanshizeri": "sanshizeri",
    "qizhengzeri": "qizhengzeri",
    "indiazeri": "indiazeri",
    "geomancy": "geomancy",
    "tarot": "tarot",
    "lingqi": "lingqi",
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


_JAVA_CHART_DATE_ENDPOINTS = {"/chart", "/chart12", "/chart13", "/india/chart"}
_JAVA_DATE_FALLBACK_ENDPOINTS = {
    "/nongli/time",
    "/jieqi/year",
    "/liureng/gods",
    "/liureng/runyear",
}
_PYTHON_CHART_ENDPOINTS = {
    "/chart",
    # 天星择日·征象搜索（上游 v3.7.0；挂在主 chart 服务，Java 侧无此路由）
    "/electionscan/scan",
    # 单时刻逐叶判读 + 条件类型自省（上游 v3.9.x R4；explainAt 参数与条件树报错自愈用）
    "/electionscan/explain",
    "/electionscan/conditiontypes",
    # 择日十技法（v3.10.0）的两个后端扫描成员。不登记的后果不是 404 而是**被路由去 Java 聚合层**，
    # 那边没有这条路由 → HTTP 500，而同样的请求体直接打 chart 服务是好的 —— 症状像「后端坏了」，
    # 实则是路由表漏登记（AGENTS §5 布线清单第 2 步）。
    "/qizhengelectionscan/scan",
    "/qizhengelectionscan/explain",
    "/qizhengelectionscan/conditiontypes",
    "/indiaelectionscan/scan",
    "/indiaelectionscan/explain",
    "/indiaelectionscan/conditiontypes",
    # 七政择日动盘三路由（批 I-1b；同挂主 chart 服务 webqizhengelectionsrv）
    "/qizhengelection/pan",
    "/qizhengelection/eclipses",
    "/qizhengelection/azimuthsearch",
    "/chart12",
    "/chart13",
    "/predict/persianchart",
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
    # 合盘关系量化打分（契合分数 + 顺畅/张力连接），与 /modern/relative 比较盘互补。
    "/astroextra/relative",
    "/india/chart",
    # 印度出生时间校正（批 I-2；独立端点，照 shadbalarange 骨架不进命盘缓存键）
    "/india/rectify",
    # ACG 落点/事件（批 I-4）
    "/location/acgpoint",
    "/location/acgevent",
    "/germany/midpoint",
    "/astroextra/harmonic",
    # 玄史知识库（只读 SQLite bundle，随 runtime 分发）：26 个检索/结构视图端点。
    "/xuanshi/summary",
    "/xuanshi/events",
    "/xuanshi/event",
    "/xuanshi/celestial",
    "/xuanshi/celestial_event",
    "/xuanshi/microchronology",
    "/xuanshi/decade_omens",
    "/xuanshi/celestial_term_profile",
    "/xuanshi/figures",
    "/xuanshi/figure",
    "/xuanshi/techniques",
    "/xuanshi/technique",
    "/xuanshi/celestial_terms",
    "/xuanshi/celestial_term",
    "/xuanshi/dynasties",
    "/xuanshi/dynasty",
    "/xuanshi/stories",
    "/xuanshi/story",
    "/xuanshi/channels",
    "/xuanshi/map",
    "/xuanshi/persons_graph",
    "/xuanshi/timeline",
    "/xuanshi/events_meta",
    "/xuanshi/facets",
    "/xuanshi/search",
    "/xuanshi/daily",
    "/astroextra/ephemeris",
    "/astroextra/draconic",
    "/astroextra/relocation",
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
    # 批 I-3：行星周期（任意两星合冲时间轴）+ 日月返照年表
    "/astroextra/planetcycles",
    "/astroextra/returns",
    "/astroextra/barbault",
    "/geomancy/reading",
    # 占星地图（AstroCartoGraphy）：行星地理投影线精算端点。
    "/location/acg",
    "/predict/planetaryarc",
    "/jieqi/year",
    # 批 I-3：出生节气窗（BirthJieQi，八字起运窗同源）
    "/jieqi/birth",
    # 批 I-5：文本库三件（判词库/心易起卦/十六卦目录）
    "/cetian/texts",
    "/wangji/xinyi",
    "/geomancy/catalog",
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


# --- 天星择日 / 奇门择日 helpers ------------------------------------------------------------

# election_scan.ScanContext.eff 实际读取的口径键；白名单而非 **payload —— 否则 skill 自有的
# agent_confirmed_settings / response_view 之类会一起灌进引擎。
# 🔴 这份白名单必须覆盖后端**实读**的键，否则就是在客户端把已修好的后端 bug 重新装回去：
# election_scan.scan 走 `_cls_req = dict(data)` 整包下发（election_scan.py:1993），
# perchart.push_classical_request 从中实读 termsVariant / leoBoundFirst / geminiBoundEmended /
# customTermsDay / customTermsNight / triplicity / houseCuspAdvance / lotsDocReverse /
# nodeExaltation / dignityDebilities / orbSystem / luminaryOrbBonus 十二键
# （perchart.py:696-703），另有 ScanContext 读 height / partileDef、PerChart.__init__ 读
# cazimiOrb / combustOrb / underBeamsOrb 等。上游 [F8] 那条注释记的正是「dignityDebilities/
# orbSystem 等发了不生效」—— 后端已收编，而此处白名单窄 7 键，等于把它们又静默滤掉：
# schema 上带着描述、chart 工具上照常生效，唯独天星择日搜索里无声失效。
_ELECTIONSCAN_OPTION_KEYS = (
    "cazimiOrb", "combustOrb", "underBeamsOrb", "vocMode", "vocIncludeOuter", "viaCombustaVariant",
    "partileDef", "termsVariant", "triplicity", "sectBuffer", "houseCuspAdvance", "westNodeType",
    "height", "leoBoundFirst", "geminiBoundEmended",
    # push_classical_request 实读、此前被滤掉的七键：
    "nodeExaltation", "dignityDebilities", "lotsDocReverse", "orbSystem", "luminaryOrbBonus",
    "customTermsDay", "customTermsNight",
    # 上游 v3.11 起 ScanContext 实读的五键（election_scan.py:361-374）：[Q-418/T-381] 希腊点口径与主排盘
    # perchart._applyLotVariants 同式（福点反转 / 福点变体 / 赫尔墨斯六点反转）；[Q-268/T-254] 自定义恒星黄道
    # 'user' 档的历元 JD 与该历元岁差度。BirthInput 早已声明它们、chart 工具照常生效，唯独天星择日搜索被
    # 本白名单滤掉 —— 夜间点类判定与所见主盘相反、'user' 档扫描静默回落 Lahiri。
    "lotReversal", "lotFortuneVariant", "hermeticLotsReversal", "userAyanT0", "userAyanDeg",
)


# 天星择日窗口上限（天）。每段 = 一次串行后端扫描；再往上 splitByMonth 的 800 段 guard 会耗尽并
# **丢掉最后一段**，而结果仍会被报成完整搜索。取 2 年：60 段左右，已经很慢，但还不至于丢结果。
_TIANXING_MAX_SPAN_DAYS = 731

# 奇门择日窗口上限（天）。比引擎自带的 1830 天紧得多：区间搜索跑在 JS 子进程里，墙钟 60 秒
# （config.js_engine_timeout_seconds），而扫描约 2 秒/月窗 —— 引擎那个上限会把超时撑爆约 30 倍。
_QIMENZERI_MAX_SPAN_DAYS = 92


def _clamped_max_span(payload: dict[str, Any], cap: int) -> int:
    """把调用方给的 `maxSpanDays` **夹到**硬上限之内（v0.37.0 C7）。

    🔴 此前 `int(payload.get("maxSpanDays") or CAP)` 让 maxSpanDays 变成一个**能把上限抬高**的
    旋钮：传 5000 就真按 5000 天放行。上限不是礼貌建议——tianxing 的 731 天来自 splitByMonth 的
    800 次 guard（耗尽会**不 push 最后一段**就退出，尾部被丢却仍报成完整搜索），本地扫描的 92 天
    来自 JS 子进程 60 秒墙钟。抬高上限只会把这两个失败模式换成「跑到超时」或「静默截断」，
    而调用方看到的仍是一个自称成功的结果。maxSpanDays 因此只保留「调**低**」这一半语义。
    非法/缺省值一律回落 cap；≤0 也回落（0 会让任何窗口都超限）。
    """
    raw = payload.get("maxSpanDays")
    if raw is None:
        return cap
    try:
        requested = int(raw)
    except (TypeError, ValueError):
        return cap
    if requested <= 0:
        return cap
    return min(requested, cap)


def _require_sane_window(
    start_date: str, end_date: str, *, max_span: int, tool: str, span_hint: str | None = None
) -> None:
    """搜索窗必须可解析、非倒置、不超上限 —— 三者缺一都不能放行。

    🔴 `startDate`/`endDate` **不经** normalize_request_payload（它只管 date/time 等，见
    input_normalization），所以 agent 传什么就是什么。旧实现用 `_day_span(...) is not None` 判，
    于是 `'2026-08-05 10:00'` / `'2026-08-05T00:00'` 这类解析不出来的形状**直接跳过上限**——
    而 JS 侧 wallToMs 照样能解析它们，于是超长窗口一路跑到超时。解析失败必须报错，不是放行。
    倒置窗口（end < start）得负数，`负数 > max` 恒 False，同样能溜过去。
    """
    span = _day_span(start_date, end_date)
    if span is None:
        raise ToolValidationError(
            f"{tool} 无法解析搜索窗日期（需 YYYY-MM-DD）。",
            code=f"tool.{tool}_bad_window",
            details={"startDate": start_date, "endDate": end_date,
                     "hint": "只接受 YYYY-MM-DD；时刻请用 startTime/endTime 单独给。"},
        )
    if span < 0:
        raise ToolValidationError(
            f"{tool} 搜索窗倒置：结束日期早于起始日期。",
            code=f"tool.{tool}_inverted_window",
            details={"startDate": start_date, "endDate": end_date, "span_days": span},
        )
    if span > max_span:
        raise ToolValidationError(
            f"{tool} 搜索窗 {span} 天超过上限 {max_span} 天。",
            code=f"tool.{tool}_span_too_large",
            details={
                "span_days": span, "max_span_days": max_span,
                # 上限是硬的：maxSpanDays 只能调低（_clamped_max_span），提示不再暗示可以调高，
                # 否则 agent 会照着重试、再被同一条错误挡回来，白烧一轮往返。
                "max_span_days_cap": max_span,
                "hint": span_hint or "把窗口拆成多段分别搜索；每段都是一次串行后端扫描，窗口越长越慢。"
                                     "maxSpanDays 只能调低，不能超过本上限。",
            },
        )


def _require_cast_geo(payload: dict[str, Any], *, tool: str) -> None:
    """占时（按当下时刻起课）路径打 `/nongli/time` 前，先确认 lon/lat 真的有值。

    🔴 v0.26.0 的实际故障：这五个工具（xiaoliuren / feigong / xiaochengtu / guice / zhengchuan）
    的 schema 把 `lat` 列为可选、docstring 还写着「date/time/zone[+lon] 就够」，于是它们用
    `payload.get("lat")` 取值，缺省时把 **`lat: null`** 发给 Java 层 → 回 `200001 param error`
    → 用户只看到一句「本地 Horosa 后端返回 HTTP 500」。对照 qimen/taiyi 用的是 `payload["lat"]`（必填）。

    ⚠️ 这个 bug 极易被误诊成「环境问题」：Java 的农历结果按**年**缓存，任何一次带 lat 的请求都会把
    该年焐热，此后同年的无 lat 请求全部成功。所以它表现为「有时好有时坏」，v0.25.1 的台账据此把它
    错归因成「本机无 Mongo」。复现务必换一个**冷年份**。
    """
    missing = [k for k in ("lon", "lat") if payload.get(k) in (None, "")]
    if not missing:
        return
    raise ToolValidationError(
        f"{tool} 按时刻起课需要起课地点的经纬度（缺 {'/'.join(missing)}）。",
        code=f"tool.{tool}_cast_geo_required",
        details={
            "missing": missing,
            "why": (
                "起课要先经 /nongli/time 定四柱，该端点要求 lon+lat 均非空；缺任一个后端回 "
                "200001 param error（表现为 HTTP 500）。"
            ),
            "hint": "提供 lon/lat（或 gpsLon/gpsLat），或改用直接给定 nums/干支 的免起课路径。",
        },
    )


def _electionscan_options(options: Any) -> dict[str, Any]:
    if not isinstance(options, dict):
        return {}
    return {k: options[k] for k in _ELECTIONSCAN_OPTION_KEYS if options.get(k) is not None}


# [Q-452 裁决 A / Q-453 裁决] 择日十宿主 + 天星 AI 快照的「命中清单」两旋钮（上游 utils/zeriSnapshotPrefs.js）：
# 清单上限缺省 60 行（10–500）、前 N 行附判读树缺省 3（0–20，0=不附）。归一由 JS 侧 vendored 同名
# normalize* 完成，Python 原样透传 builder 自己的键名 maxRows/explainRows（跨边界不改键）。
def _zeri_snapshot_row_opts(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if payload.get("zeriSnapshotMaxRows") is not None:
        out["maxRows"] = payload["zeriSnapshotMaxRows"]
    if payload.get("zeriSnapshotExplainRows") is not None:
        out["explainRows"] = payload["zeriSnapshotExplainRows"]
    return out


# 后端扫描家族（天星/七政/印度）的判读树要由宿主**预取**（上游 prefetchSnapshotExplains），Python 得先知道
# 要打几次 /explain —— 这里与 zeriSnapshotPrefs.normalizeZeriSnapshotExplainRows 的 clampInt 同式
# （缺省 3、夹到 [0, 20]、向下取整、非数回缺省）；与 JS 归一的逐值一致由 test_sync311_divination 对拍锚定。
_ZERI_EXPLAIN_ROWS_DEFAULT, _ZERI_EXPLAIN_ROWS_MIN, _ZERI_EXPLAIN_ROWS_MAX = 3, 0, 20


def _zeri_explain_rows(payload: dict[str, Any]) -> int:
    raw = payload.get("zeriSnapshotExplainRows")
    if raw is None or str(raw).strip() == "":
        return _ZERI_EXPLAIN_ROWS_DEFAULT
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return _ZERI_EXPLAIN_ROWS_DEFAULT
    if not math.isfinite(value):
        return _ZERI_EXPLAIN_ROWS_DEFAULT
    return max(_ZERI_EXPLAIN_ROWS_MIN, min(_ZERI_EXPLAIN_ROWS_MAX, math.floor(value)))


def _electionscan_zone(zone: Any) -> str:
    """election_scan 期望 '+08:00' 形状；skill 的 zone 常是数字小时（8 / -5 / 5.5）。"""
    if zone is None:
        return "+08:00"
    text = str(zone).strip()
    if ":" in text:
        return text
    try:
        hours = float(text)
    except ValueError:
        return "+08:00"
    sign = "-" if hours < 0 else "+"
    total = int(round(abs(hours) * 60))
    return f"{sign}{total // 60:02d}:{total % 60:02d}"


def _day_span(start_date: str, end_date: str) -> int | None:
    from datetime import date as _date

    def parse(text: str) -> _date | None:
        parts = str(text).replace("/", "-").split("-")
        if len(parts) < 3:
            return None
        try:
            return _date(int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, TypeError):
            return None

    a, b = parse(start_date), parse(end_date)
    return None if a is None or b is None else (b - a).days


def _cn_unified_zone_note(input_normalized: dict[str, Any]) -> str | None:
    """F17：输入层把 Asia/Urumqi 归并成北京时间时，warnings 里说清楚（上游 advisory 'cn-unified' 同义）。"""
    if input_normalized.get("zoneAdvisory") != "cn-unified":
        return None
    geo = input_normalized.get("geoZone") or "Asia/Urumqi"
    return (
        f"时区按中国大陆统一北京时间口径起盘：{geo} → Asia/Shanghai（{input_normalized.get('zone')}，"
        f"1949-10-01 起法定时间）；如需新疆当地惯用时间，传 cnUnifiedZone=false 或直接给偏移 +06:00。"
    )


def _day_boundary_switches(payload: dict[str, Any], keys: tuple[str, ...] = ("after23NewDay", "lateZiHourUseNextDay")) -> dict[str, int]:
    """日界(after23NewDay)/晚子时时柱(lateZiHourUseNextDay)开关：仅显式给定时发送。

    None 不发送 → 后端按其默认(1/1)起算，与未传时字节级等价（零默认漂移）。
    """
    switches: dict[str, int] = {}
    for key in keys:
        value = payload.get(key)
        if value is not None:
            switches[key] = 1 if value in (1, True, "1", "true", "True") else 0
    return switches


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
                "lateZiHourUseNextDay",
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
        ("date", "time", "zone", "lat", "lon", "after23NewDay", "lateZiHourUseNextDay", "ad", "yue", "isDiurnal"),
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


def _liureng_time_alg(payload: dict[str, Any]) -> int | None:
    """大六壬起课时间算法（上游 v3.11 [Q-386/T-367]：LiuRengController 改读 timeAlg，缺省 RealSun=0）。

    `options.timeAlg` 优先、顶层 `timeAlg` 次之（三式合一子盘把共享 timeAlg 放顶层）；缺省返回 None =
    不发送（后端缺省真太阳时，与上游 LIURENG_PAGE_SETTINGS.timeAlg def 0 同值）。上游页面只给两档
    （LiuRengMain.js:3916 oneOf [0, 1]），认不出的值报错而不静默回落。
    """
    options = payload.get("options") if isinstance(payload.get("options"), dict) else {}
    raw = options.get("timeAlg")
    if raw is None:
        raw = payload.get("timeAlg")
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool) or str(raw).strip() not in {"0", "1"}:
        raise ToolValidationError(
            bilingual(
                f"大六壬 timeAlg 取值无效：{raw!r}（可选：0=真太阳时 / 1=直接时间）。",
                f"liureng timeAlg is invalid: {raw!r} (allowed: 0=true solar time / 1=clock time).",
            ),
            code="tool.liureng_invalid_option",
            details={"field": "timeAlg", "value": raw, "allowed": [0, 1]},
        )
    return int(str(raw).strip())


def _liureng_gods_payload(tool_name: str, payload: dict[str, Any], time_alg: int | None) -> dict[str, Any]:
    """`/liureng/gods` 起课请求 —— 行年盘按**起课时刻**（gua*）起课，同上游 genGodsParams(calcFields)。

    此前 liureng_runyear 只打 `/liureng/runyear`，而该端点只回 {age, ageCycle, year}（LiuRengHelper.runYear），
    没有 liureng 盘 → 四课 / 三传 / 行年整段落空（live 实测）；上游页面是 gods（起课）+ runyear（行年）两请求。
    """
    base = _liureng_remote_payload("liureng_gods", payload)
    if tool_name == "liureng_runyear":
        for key, gua_key in (("date", "guaDate"), ("time", "guaTime"), ("zone", "guaZone"),
                             ("lat", "guaLat"), ("lon", "guaLon"), ("ad", "guaAd"),
                             ("after23NewDay", "guaAfter23NewDay")):
            if payload.get(gua_key) is not None and payload.get(gua_key) != "":
                base[key] = payload[gua_key]
    if time_alg is not None:
        base["timeAlg"] = time_alg
    return base


def _liureng_runyear_from(response: Any) -> dict[str, Any] | None:
    """`/liureng/runyear` 真实回包是裸 {age, ageCycle, year}（LiuRengHelper.runYear）；兼容包了一层的旧形状。"""
    if not isinstance(response, dict):
        return None
    wrapped = response.get("runyear") or response.get("runYear")
    if isinstance(wrapped, dict):
        return wrapped
    return response if response.get("year") else None


def _gua_year_ganzi(liureng: Any) -> str:
    """上游 resolveGuaYearGanZi（LiuRengMain.js:183）：起课盘年柱 → 行年所用的卦年干支。"""
    if not isinstance(liureng, dict):
        return ""
    four = liureng.get("fourColumns") if isinstance(liureng.get("fourColumns"), dict) else {}
    year = four.get("year")
    candidates = [year.get("ganzi") if isinstance(year, dict) else year]
    nongli = liureng.get("nongli") if isinstance(liureng.get("nongli"), dict) else {}
    candidates += [nongli.get("yearGanZi"), nongli.get("yearJieqi"), nongli.get("year")]
    for text in candidates:
        match = re.search(r"[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]", str(text or ""))
        if match:
            return match.group(0)
    return ""


# 金口诀排盘流派五键 + 时间基准的词表与缺省（上游 JinKouMain.js:857-864 JINKOU_PAGE_SETTINGS，首项 = 缺省）。
# 上游本地引擎对认不出的值静默归缺省（buildJinKouData `=== 'jiaojie' ? … : 'zhongqi'`），headless 改为报错。
_JINKOU_SCHOOL_VOCAB: dict[str, tuple[str, ...]] = {
    "schoolYueJiang": ("zhongqi", "jiaojie"),
    "schoolGuiTable": ("shiwu", "liuren"),
    "schoolGuiPan": ("di", "tian"),
    "panShi": ("yang", "yin"),
    "soilChangSheng": ("shen", "yin"),
    "timeBasis": ("direct", "trueSolar"),
}


def _jinkou_option_error(field: str, value: Any, allowed: list[Any]) -> ToolValidationError:
    return ToolValidationError(
        bilingual(
            f"金口诀 {field} 取值无效：{value!r}（可选：{' / '.join(str(a) for a in allowed)}）。",
            f"jinkou {field} is invalid: {value!r} (allowed: {', '.join(str(a) for a in allowed)}).",
        ),
        code="tool.jinkou_invalid_option",
        details={"field": field, "value": value, "allowed": allowed},
    )


def _jinkou_validate_options(options: dict[str, Any]) -> None:
    for key, allowed in _JINKOU_SCHOOL_VOCAB.items():
        value = options.get(key)
        if value not in (None, "") and value not in allowed:
            raise _jinkou_option_error(key, value, list(allowed))
    for key in ("yueJiang", "zhanShi"):
        value = options.get(key)
        if value not in (None, "", "auto") and (len(str(value)) != 1 or str(value) not in _GANZHI_BRANCHES):
            raise _jinkou_option_error(key, value, ["auto", *_GANZHI_BRANCHES])
    wuxing = options.get("wuxing")
    if wuxing not in (None, "") and wuxing not in ("木", "火", "土", "金", "水"):
        raise _jinkou_option_error("wuxing", wuxing, ["木", "火", "土", "金", "水"])


def _jinkou_school_overrides(options: dict[str, Any]) -> list[str]:
    """上游 schoolsAllDefault（JinKouMain.js:1288-1294）的镜像：返回非缺省的流派/盘法键（空 = 全缺省 → ken 路径）。"""
    return [
        key for key, allowed in _JINKOU_SCHOOL_VOCAB.items()
        if key != "timeBasis" and (options.get(key) or allowed[0]) != allowed[0]
    ]


def _jinkou_resolve_difen(raw: Any, time_text: Any) -> str:
    """上游 resolveJinKouDiFen(diFen, diFenAuto, timeZi, hasExistingPan=false)（JinKouState.js:14）的首次起课口径：
    未指定 / 'auto' → 占时支（liureng.nongli.time 的地支），取不到才落「子」；显式给定须是单个地支。"""
    text = str(raw or "").strip()
    if text in ("", "auto"):
        match = re.search(f"[{_GANZHI_BRANCHES}]", str(time_text or ""))
        return match.group(0) if match else "子"
    if len(text) != 1 or text not in _GANZHI_BRANCHES:
        raise _jinkou_option_error("diFen", raw, ["auto", *_GANZHI_BRANCHES])
    return text


def _jinkou_manual_branch(value: Any) -> str:
    """月将/占时手选（上游 fetchJinKouPan：`opt.yueJiang && opt.yueJiang !== 'auto' ? … : ''`）。"""
    text = str(value or "").strip()
    return "" if text in ("", "auto") else text


def _sanshi_liureng_options(payload: dict[str, Any]) -> dict[str, Any]:
    """三式合一六壬层口径（liureng_options → liureng_gods 子盘 options）。

    上游三式合一只支持正时正将起课法（pickSanshiLiurengCastOpts 锁 castMethod:'zheng'，SanShiUnitedMain.js:957），
    其余六壬层口径（换将/分昼夜/涉害/阴阳系/年神序/土旺衰/贵人）同独立六壬页词表；时间算法是三盘共享的顶层 timeAlg。
    """
    raw = payload.get("liureng_options")
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ToolValidationError(
            bilingual("liureng_options 须为对象。", "liureng_options must be an object."),
            code="tool.sanshiunited_invalid_option",
            details={"field": "liureng_options", "value": raw},
        )
    if raw.get("castMethod") not in (None, "", "zheng"):
        raise ToolValidationError(
            bilingual(
                f"三式合一只支持正时正将起课法（castMethod=zheng），收到 {raw.get('castMethod')!r}；其余起课法请单独调 liureng_gods。",
                f"sanshiunited only supports castMethod=zheng (got {raw.get('castMethod')!r}); use liureng_gods for other methods.",
            ),
            code="tool.sanshiunited_invalid_option",
            details={"field": "liureng_options.castMethod", "value": raw.get("castMethod"), "allowed": ["zheng"]},
        )
    if "timeAlg" in raw:
        raise ToolValidationError(
            bilingual(
                "三式合一的时间算法是三盘共享的顶层 timeAlg，liureng_options 里不接受 timeAlg。",
                "sanshiunited timeAlg is the shared top-level field; liureng_options.timeAlg is not accepted.",
            ),
            code="tool.sanshiunited_invalid_option",
            details={"field": "liureng_options.timeAlg", "value": raw.get("timeAlg")},
        )
    return dict(raw)


def _raise_js_option_error(tool: str, js_result: Any) -> None:
    """JS 工具按上游词表校验口径参数，认不出的值回 data.ok=false + error{field,value,allowed}（不静默回落缺省）。"""
    data = js_result.get("data") if isinstance(js_result, dict) else None
    if not isinstance(data, dict) or data.get("ok") is not False:
        return
    error = data.get("error") if isinstance(data.get("error"), dict) else {}
    raise ToolValidationError(
        bilingual(
            str(error.get("message") or f"{tool} 参数无效。"),
            f"{tool}: invalid option {error.get('field')!r}={error.get('value')!r} (allowed: {error.get('allowed')}).",
        ),
        code=f"tool.{tool}_invalid_option",
        details={k: error.get(k) for k in ("field", "value", "allowed") if k in error},
    )


def _chart_server_endpoint(endpoint: str) -> str:
    return "/" if endpoint == "/chart" else endpoint


def _generic_summary(tool_name: str, data: dict[str, Any]) -> list[str]:
    if tool_name == "export_registry":
        count = len(data.get("techniques", []))
        total = int(data.get("techniques_total") or count)
        if count < total:
            summary = [f"已输出 1 个星阙 AI 导出 technique 的注册表（全库共 {total} 个）。"]
        else:
            summary = [f"已输出 {count} 个星阙 AI 导出 technique 的完整注册表。"]
        selected = data.get("selected_technique")
        if isinstance(selected, dict) and selected.get("label"):
            summary.append(f"当前聚焦：{selected['label']}。")
        missing = data.get("technique_not_found")
        if missing:
            summary.append(f"未识别的 technique「{missing}」——已返回全量注册表供比对名称。")
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
        if data.get("mode") == "search":
            summary = [f"已跨知识域全文检索「{data.get('query')}」：命中 {data.get('total_matched', 0)} 条（扫描 {data.get('total_scanned', 0)} 条目）。"]
            matches = data.get("matches") or []
            if matches:
                summary.append(f"最优命中：{matches[0].get('citation')}。")
            return summary
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
    if tool_name == "yizhangjing":
        model = data.get("yizhangjing", {})
        summary = ["已运行本地一掌经算法。"]
        ming = model.get("mingGong") if isinstance(model.get("mingGong"), dict) else {}
        if ming.get("branch") and ming.get("star"):
            summary.append(f"命宫 {ming['branch']}宫·{ming['star']}。")
        pattern = model.get("pattern") if isinstance(model.get("pattern"), dict) else {}
        if pattern.get("mingGe"):
            summary.append(f"命格：{pattern['mingGe']}（九品估 {pattern.get('nineGrade', '—')}）。")
        return summary
    if tool_name == "acg":
        model = data.get("acg", {})
        summary = ["已生成占星地图行星线表（AstroCartoGraphy）。"]
        planets = model.get("planets") if isinstance(model.get("planets"), dict) else {}
        if planets:
            summary.append(f"行星线：{len(planets)} 星（MC/IC 经度 + 天顶点）。")
        parans = model.get("parans")
        if isinstance(parans, list) and parans:
            summary.append(f"偕升纬度带 {len(parans)} 条。")
        return summary
    if tool_name == "bazi_inverse":
        model = data.get("bazi_inverse", {})
        pillars = "".join(f"{x} " for x in (model.get("pillars") or [])).strip()
        candidates = model.get("candidates") or []
        return [f"八字反查 {pillars or '—'}：{len(candidates)} 个候选时刻。"]
    if tool_name == "astrodata":
        model = data.get("astrodata", {})
        summary = ["已检索离线名人星盘数据库。"]
        if isinstance(model.get("person"), dict):
            summary.append(f"单人详情：{model['person'].get('name')}（评级 {model['person'].get('rodden', '—')}）。")
        elif model.get("total") is not None:
            summary.append(f"命中 {model['total']} 条。")
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

    def add(display_name: str, *, entity_type: str = "subject", key: str | None = None, metadata: dict[str, Any] | None = None) -> None:
        value = (display_name or "").strip()
        if not value:
            return
        entities.append(
            {
                "entity_type": entity_type,
                "entity_key": (key or value).lower(),
                "display_name": value,
                "metadata": metadata or {},
            }
        )

    def birth_meta(source: dict[str, Any]) -> dict[str, Any]:
        return {
            k: source.get(src_key)
            for k, src_key in (("date", "date"), ("time", "time"), ("zone", "zone"), ("lat", "lat"), ("lon", "lon"))
            if source.get(src_key) is not None
        }

    if query_text:
        add(query_text[:80], entity_type="query")

    def add_person(source: dict[str, Any]) -> None:
        # 按人聚合的索引基础：姓名实体带出生元数据；有 name+date 时另建 `name|date` 复合键实体
        # （精确定位同名同生辰之人），有 date 时建 birthdate 实体（按生日横向聚合历史盘）。
        p_name = source.get("name")
        p_date = source.get("date")
        meta = birth_meta(source)
        if isinstance(p_name, str) and p_name.strip():
            add(p_name, metadata=meta)
            if isinstance(p_date, str) and p_date.strip():
                add(p_name, entity_type="person", key=f"{p_name.strip()}|{p_date.strip()}", metadata=meta)
        if isinstance(p_date, str) and p_date.strip():
            add(p_date.strip(), entity_type="birthdate", metadata=meta)

    add_person(input_normalized)
    for key in ("inner", "outer", "subject", "birth"):
        nested = input_normalized.get(key)
        if isinstance(nested, dict):
            add_person(nested)

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


# 星运族 [方法说明]：每键 2-4 行公开通行机理与读法（零书名零章节）。键=导出 technique 名。
_PREDICTIVE_METHOD_NOTES: dict[str, list[str]] = {
    "primarydirect": [
        "主限法：天体按周日运动(赤经/方位弧)推进,约 1 度合 1 年;迫星抵达应星的弧量换算年龄,用于判大事应期。",
        "读法：表中每行=一次抵达事件;以应星宫职与迫星性质合断吉凶主题。",
    ],
    "zodialrelease": [
        # 上游 astroAiSnapshot.js:2029-2033 [Q-363/T-344]：缺省基点=福点，期长=各座守护星小年（非行星大年）。
        "黄道释放：自所选基点(默认幸运点,可改精神点等)所在星座起,按各星座守护星小年逐座、逐层释放,划分人生篇章(一级期)与子期(二级期)。",
        "读法：期主星及其本命状态定该段主题;跳宫(LB)为重大转折;与幸运点十度关系看顺逆。",
    ],
    "firdaria": [
        "法达大限：波斯行星期法,日生盘自太阳、夜生盘自月亮起,诸星依序各主政若干年,内再均分子期。",
        "读法：主期星定大主题、子期星定阶段事项,两星本命状态与彼此关系定吉凶成色。",
    ],
    "distributions": [
        # 上游 astroAiSnapshot.js:2038-2042 [Q-170/T-109]：恒以上升为释放点，界表随全局界系。
        "界推运(分配法)：上升按主限速率行经黄道各界,界主星即该段\"分配星\";界表用当前全局界系设置。",
        "读法：分配星与其间同行的本命星(参与星)共同定该段境遇;换界即换阶段。",
    ],
    "agepoint": [
        "年龄推进点：心理占星年龄点每宫约 6 年匀速推进,逐宫走完十二宫。",
        "读法：落宫定人生课题场域,与本命星的合相/相位标记该年龄的关键事件与心理主题。",
    ],
    # [Q-106/T-10] 星运三页上线（上游 astroAiSnapshot.js:2045-2057 逐字；ASCII 逗号/分号亦照抄）
    "ephemeris": [
        "星历：以本命盘地点与时区列出区间内行星入座、留与顺逆转向、朔望弦与食相,并按容许度筛出行运触发本命点的时刻。",
        "读法：入座换宫定阶段主题,留点前后事件易停滞反复,食相落宫标重大转折;行运触发行只列精确时刻,结合本命点性质判吉凶。",
    ],
    "returntimeline": [
        "回归轴：逐年列太阳返照(太阳回本命度)与该年首个月亮返照时刻及两盘上升点。",
        "读法：返照上升落座定该年/该月主色,上升与本命宫位的对应指示焦点领域;多年并列可见上升轮转的节律。",
    ],
    "prenatalsyzygy": [
        "产前朔望：自出生时刻回溯最近的朔(日月合)或望(日月冲),取更晚者为产前朔望,以该时刻、出生地排盘。",
        "读法：朔取合相度、望取地平之上发光体度为「取度」;该度及其主星为古典寿主/命主判定的重要候选,产前盘星体位置为本命的先天背景。",
    ],
    "profection": [
        "小限(年限)：每满一岁命宫顺推一宫,该宫为当年小限宫,其宫主星为年主星。",
        "读法：年主星本命状态与流年动态定当年吉凶;小限宫宫职指示当年主战场。",
    ],
    "solararc": [
        "太阳弧向运：全盘诸点按太阳年均约 1 度的弧量整体推进。",
        "读法：推进点与本命点形成的入相位(容许度约 1 度)标记事件年份;点性组合定事件性质。",
    ],
    "solarreturn": [
        "太阳返照(日返)：太阳每年回归本命黄经时刻起盘,该盘统领此后一个太阳年。",
        "读法：返照盘上升与其主星定年度基调;返照盘行星落本命宫位看事项落点。",
    ],
    "lunarreturn": [
        "太阴返照(月返)：月亮每月回归本命黄经时刻起盘,统领此后一个太阴月。",
        "读法：与日返同理,颗粒度为月;月亮状态与四轴最要紧。",
    ],
    "givenyear": [
        # 上游 astroAiSnapshot.js:2076-2080 [Q-170/T-109]：perpredict 给的是实时天象盘，不是二次推运盘。
        "指定年天象盘：按所给年份的时刻与地点起一张实时天象盘,与本命对照。",
        "读法：天象盘行星落本命宫位与两盘相位定该年主题。",
    ],
    "decennials": [
        "十年大运(Decennials)：希腊期法,诸星依序轮值主政各 129 个月(约 10.75 年),内按行星小年分子期。",
        "读法：主政星+子期星组合定阶段主题;换主政为人生大节点。",
    ],
    "planetaryages": [
        "行星年龄段：人生依序由月亮/水星/金星/太阳/火星/木星/土星主政固定年岁段(4/10/8/19/15/12/30 年制式)。",
        "读法：当前年龄所处主政星定人生阶段基调;主政星本命状态定该阶段顺逆。",
    ],
    # [#80] 回归黄道二次推运（上游 astroAiSnapshot.js:2087-2090 逐字）
    "prog": [
        "二次推运:回归黄道下的推运(二次推运一日抵一年、三次推运与小推运同族),叠加本命对照。",
        "读法：推运位与本命位的星座宫位迁移及相位,合冲刑三分为主,应期看推运点行至本命点。",
    ],
    "vedicprog": [
        "恒星推运：以恒星黄道计的推运(含二次推运一日抵一年),叠加本命对照。",
        "读法：推运位与本命位的星座宫位迁移及相位,按恒星制口径判断。",
    ],
    "jaynesprog": [
        "赤纬推运：只看推运星与本命星的赤纬平行(同纬同侧)与反平行(同纬异侧)。",
        "读法：平行视作强合相、反平行视作强对冲;成对年份即应期。",
    ],
    "planetaryarc": [
        "行星弧向运：同太阳弧原理,但以选定行星的推进速率作弧量整体前移。",
        "读法：弧主星的性质给全部触发事件染色;入相位年份为应期。",
    ],
    "persiandirected": [
        "波斯向运：中世纪波斯法,诸点按约 1 度/年向前推进与本命点会照。",
        "读法：向运点与本命点的相位事件按年龄排布;近期命中(距今最近)优先解读。",
        "指定日期：传 datetime=YYYY-MM-DD 可整铸该日向运盘(「指定日期向运盘」段:directed 点位+向运→本命命中);rateKey/direction 可换速率与顺逆。",
    ],
    "yearsystem129": [
        # 上游 astroAiSnapshot.js:2111-2115 [Q-170/T-109]：小年 Σ=129，子限=主限小年七等分。
        "129 年系统：以七星小年合计 129 年为总周期,按小年切主限,主限内再七等分为子限。",
        "读法：主限星定大阶段,子限星定小阶段,起讫日期定应期窗口。",
    ],
    "balbillus": [
        # 上游 astroAiSnapshot.js:2116-2121 [Q-170/T-109·T-110]：旺距削减主限 + 子限按削减年数×本层单位铺开。
        "主/子限期法(Balbillus)：罗马期法,主限长度=该星小年 ×(1 − 离擢升度角距/360),七星按本命黄经序自起始星铺开;子限以「子星削减年数 × 本层时间单位(L2=月)」顺序铺开,末段填满父期。",
        "读法：主限星与子限星组合断该段主题;换限日期为节点。",
    ],
    "triplicityrulers": [
        # 上游 astroAiSnapshot.js:2122-2126 [Q-170/T-109]：取当值光体所在座的三分性，非命度。
        "三分主星推运：当值光体(昼生取太阳、夜生取月亮)所在星座的三分性三主星(日/夜/伴)依序主管人生前/中/后三段。",
        "读法：各段主星的本命状态(庙旺陷落/宫位/受克)直接定该人生阶段的整体成色。",
    ],
    "keypoints": [
        # 上游 astroAiSnapshot.js:2127-2132 [Q-170/T-109]：位置数 k=自释放点第几座 + 专用小年表倍数激活。
        "数字相位推运(120 关键点)：每颗星取「自释放点起第几个星座」k(1–12),年龄为 k 的倍数时该星被激活;另按各星专用小年(3/8/18/5/7/9/13)的倍数激活一次。",
        "读法：命中即激活年;k 越小复现越密;结合被激活点的本命性质定主题。",
    ],
    "lunationphase": [
        "月相推运：二次推运的日月相位约 30 年走完一轮朔望循环,分八相。",
        "读法：新月=起始、上弦=建设、满月=显化、下弦=释放;当前相定人生大节奏。",
    ],
    "extrareturns": [
        # 上游 astroAiSnapshot.js:2137-2141 [Q-170/T-109]：后端只求整回归，不产 1/4、1/2 周期行。
        "多重回归：木星/土星等回归本命位置的整回归时刻表。",
        "读法：整回归=大周期重启(如土星回归约 29.5 岁);两次回归之间可自行取中点作阶段参照,表内不列。",
    ],
}


def _predictive_birth_source(response: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """[起盘信息]/[本命盘配置] 生辰行的取源：本命 /chart 响应（{params, chart}）。

    优先 runner 挂上的 natalChart；其次响应本身就是 /chart（balbillus/persiandirected 等）；都没有时
    降级为「只用载荷」（出生时间/经纬度/时区/黄道/宫制，**不猜昼夜**）。
    """
    def _is_chart_response(value: Any) -> bool:
        return isinstance(value, dict) and isinstance(value.get("chart"), dict) and isinstance(value.get("params"), dict)

    if isinstance(response, dict):
        # runner 结果常把 /chart 原响应放在 raw 下（progextra/persiandirected/yearsystem129 …）。
        for candidate in (response.get("natalHeader"), response.get("natalChart"), response, response.get("raw")):
            if _is_chart_response(candidate):
                return candidate
        raw = response.get("raw")
        if isinstance(raw, dict) and _is_chart_response(raw.get("natalChart")):
            return raw["natalChart"]
    return _ptext.payload_chart_wrap(payload)


def _predictive_setup_section_text(technique: str | None, payload: dict[str, Any], response: dict[str, Any]) -> str:
    """星运族的 [起盘信息] 段（上游 = buildPredictiveBirthHeaderLines(chartObj)，位于段首）。

    上游 utils/astroAiSnapshot.js:1956-1998：A 组零盘境键（agepoint/distributions/extrareturns/
    persiandirected/balbillus/…）用它自成段——出生时间(+星期)/真太阳时/经纬度/时区/黄道/宫制/盘型。
    旧实现用 buildBaseInfoLines 口径，且对无盘响应（agepoint 等）按 isDiurnal 缺省一律写「夜生盘」——
    日生盘也标夜生盘；现在 runner 补拉本命盘，拿不到盘时不出「盘型」行（不猜）。
    """
    # 门控按「该键的 preset 是否真列了 [起盘信息]」，而不是按「是不是星运键」——primarydirect /
    # primarydirchart / zodialrelease 同属星运族但上游段首是 [出生时间]，多塞一段会变成 unknown 段。
    # 这样写也自洽：以后 preset 增删该段，无需再回来改名单。
    if not _PREDICTIVE_METHOD_NOTES.get(technique or ""):
        return ""
    if "起盘信息" not in (AI_EXPORT_PRESET_SECTIONS.get(technique or "") or []):
        return ""
    lines = _ptext.build_predictive_birth_lines(_predictive_birth_source(response, payload))
    if not lines:
        return ""
    return _render_snapshot_text([("起盘信息", "\n".join(lines))])


def _predictive_common_sections_text(
    technique: str | None, payload: dict[str, Any], extra_lines: list[str] | None = None
) -> str:
    """星运族公共两段：[当前时点](导出时刻+盘主年龄) + [方法说明](机理与读法)。

    非星运键返回空串(零变化)。

    注：早先这里写着「[起盘信息]等价段各技法快照已有,不重复」——**该说法已过期**。实测 10 个星运键
    (agepoint/balbillus/distributions/extrareturns/keypoints/lunationphase/persiandirected/
    planetaryages/triplicityrulers/yearsystem129) 的快照根本没有这一段，而上游 preset 里有
    (= buildBaseInfoLines)。故另由 `_predictive_setup_section_text` 前置补出。
    """
    notes = _PREDICTIVE_METHOD_NOTES.get(technique or "")
    if not notes:
        return ""
    now = datetime.now()
    moment_lines = [f"导出时刻：{now.strftime('%Y-%m-%d %H:%M')}"]
    birth_text = f"{payload.get('date') or ''} {payload.get('time') or ''}".strip()
    if birth_text:
        try:
            birth_dt = datetime.strptime(birth_text[:16].replace("/", "-"), "%Y-%m-%d %H:%M")
        except ValueError:
            try:
                birth_dt = datetime.strptime(birth_text[:10].replace("/", "-"), "%Y-%m-%d")
            except ValueError:
                birth_dt = None
        if birth_dt is not None:
            age = (now - birth_dt).total_seconds() / (365.2425 * 24 * 3600)
            if -1 < age < 200:
                # 上游 `Math.round(age * 100) / 100`（半数向 +∞，整数不带 .0）。
                moment_lines.append(f"盘主当前年龄：{_ptext.js_str(_ptext.js_round2(age))} 岁")
    # 上游 buildCurrentMomentLines(chartObj, extraLines)（astroAiSnapshot.js:2002-2018）：各键 timeline 定位行
    # （当前年龄点 / 当前分配星 / 当前向运年龄 / 当前所处…）由 builder 用自己的时间轴算好，追加在基线两行后。
    for line in extra_lines or []:
        if line:
            moment_lines.append(f"{line}")
    # [当前时点] 按该键 preset 门控（与 [起盘信息] 同理）：目标时刻型 5 法（profection/solararc/三返照）上游
    # buildPredictiveSnapshotText 只出 [方法说明]、preset 也不列 [当前时点]（aiExport.js:641-645）。
    if "当前时点" not in (AI_EXPORT_PRESET_SECTIONS.get(technique or "") or []):
        return _render_snapshot_text([("方法说明", "\n".join(notes))])
    return _render_snapshot_text([("当前时点", "\n".join(moment_lines)), ("方法说明", "\n".join(notes))])


# 神数正传·铁算心易查询层（sync311 F14）。表键即 vendored zhengchuanXinyiLocal.js 的 XINYI_* 常量（繁体）。
_ZC_XINYI_ITEMS = ("父母", "兄弟", "姻緣", "子孫", "官祿", "疾病")
_ZC_XINYI_SOUNDS = ("日", "月", "星", "辰", "水", "火", "土", "石", "平", "上", "去", "入", "開", "發", "收", "閉")
_ZC_XINYI_KE = ("一刻", "二刻", "三刻", "四刻", "五刻", "六刻", "七刻", "八刻")
_ZC_XINYI_GONG = ("乾", "兌", "離", "震", "巽", "坎", "艮", "坤")
_ZC_XINYI_ZHI = tuple("子丑寅卯辰巳午未申酉戌亥")
_ZC_SIMPLIFIED = {"姻缘": "姻緣", "子孙": "子孫", "官禄": "官祿", "开": "開", "发": "發", "闭": "閉", "兑": "兌", "离": "離"}
# 上游挂载缺省（aiAnalysisContext.js:3240-3243，挂载自检 F-53）：父母·日·一刻·乾·子（与页面缺省同）；
# 此前 skill 只透传显式键 → 缺省心易查询 [条文秘数查询]/[八刻分命] 整段不产。
_ZC_XINYI_DEFAULTS = {"item": "父母", "sound": "日", "ke": "一刻", "gong": "乾", "xqZhi": "子"}


def _zhengchuan_xinyi_query(payload: dict[str, Any]) -> dict[str, Any]:
    query: dict[str, Any] = {}
    for key, default in _ZC_XINYI_DEFAULTS.items():
        value = payload.get(key)
        query[key] = default if value is None or f"{value}".strip() == "" else value
    ke = query["ke"]
    # 八刻分命表键是「一刻…八刻」：数字 1–8（含 "3"）按序映射；此前 ke 被 schema 限成 int 直送，查表恒空。
    ke_text = f"{ke}".strip()
    if ke_text.isdigit() and 1 <= int(ke_text) <= 8:
        ke_text = _ZC_XINYI_KE[int(ke_text) - 1]
    if ke_text not in _ZC_XINYI_KE:
        raise ToolValidationError(
            bilingual(
                f"铁算心易 ke={ke!r} 不合法：应为 1–8 或 {'/'.join(_ZC_XINYI_KE)}。",
                f"zhengchuan xinyi ke={ke!r} is invalid: use 1-8 or {'/'.join(_ZC_XINYI_KE)}.",
            ),
            code="tool.zhengchuan_invalid_xinyi_ke",
            details={"ke": ke, "allowed": list(_ZC_XINYI_KE)},
        )
    query["ke"] = ke_text
    unknown: list[str] = []
    for key, allowed in (("item", _ZC_XINYI_ITEMS), ("sound", _ZC_XINYI_SOUNDS), ("gong", _ZC_XINYI_GONG), ("xqZhi", _ZC_XINYI_ZHI)):
        text = f"{query[key]}".strip()
        text = _ZC_SIMPLIFIED.get(text, text)
        query[key] = text
        if text not in allowed:
            unknown.append(f"{key}={text}")
    if unknown:
        # 上游对表外值同样是「查不到 → 该段不出」；这里照走，但不静默（warnings 点名 + 列表内可选值）。
        _degrade(
            "铁算心易查询项不在古籍表内（%s）：对应查询段不出", "、".join(unknown),
            note=f"铁算心易：{'、'.join(unknown)} 不在表内（项目 {'/'.join(_ZC_XINYI_ITEMS)}；宫 {'/'.join(_ZC_XINYI_GONG)}），对应查询段不出。",
        )
    for key in ("xqYushu", "gender"):
        if payload.get(key) is not None:
            query[key] = payload[key]
    return query


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


# 奇门起局法 / 盘式 / 排盘家词表（上游 DunJiaCalc.js QIJU_METHOD_OPTIONS / SCHOOL_OPTIONS / PAIPAN_OPTIONS；
# 5=综合 为引擎保留分支）。缺省起局法 = 上游 DunJiaMain.js:128 DEFAULT_OPTIONS.qijuMethod 'zhirun'（置闰）——
# 此前 skill 缺省发 chaibu（且把 maoshan/wurun 也压成 chaibu），而本地脚手架 calcDunJia 缺省 zhirun：
# ken 按拆补算盘、[盘型]「定局法」却标置闰，同一张盘两套口径（live 实测局数文本「阴遁一局中」vs「中元」）。
_QIMEN_QIJU_METHODS = ("zhirun", "chaibu", "maoshan", "wurun", "shuzi")
_QIMEN_SCHOOLS = ("转盘", "飞盘", "混合")
_QIMEN_PAIPAN_TYPES = (0, 1, 2, 3, 4, 5, 6)


def _js_parse_int(value: Any) -> int | None:
    """JS `parseInt(v, 10)` 口径（DunJiaCalc normalizeNum）：前导整数前缀；bool/None/非数 → NaN(None)。"""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if math.isfinite(value) else None
    match = re.match(r"\s*([+-]?\d+)", str(value))
    return int(match.group(1)) if match else None


def _qimen_option_error(field: str, value: Any, allowed: list[Any]) -> ToolValidationError:
    return ToolValidationError(
        bilingual(
            f"奇门 {field} 取值无效：{value!r}（可选：{' / '.join(str(a) for a in allowed)}）。",
            f"qimen {field} is invalid: {value!r} (allowed: {', '.join(str(a) for a in allowed)}).",
        ),
        code="tool.qimen_invalid_option",
        details={"field": field, "value": value, "allowed": allowed},
    )


def _qimen_effective_options(payload: dict[str, Any]) -> dict[str, Any]:
    """奇门盘面口径单源：顶层起局三开关（QimenInput 声明的 timeAlg/after23NewDay/lateZiHourUseNextDay）∪
    `options`，options 优先（与 qimenzeri 扫描同一合并）。本地脚手架、路由判据、ken 请求、择日扫描全吃这一份。

    此前本地脚手架只看 `options`（顶层 after23NewDay/timeAlg 在 JS 侧被丢，[盘型]「换日/时间算法」标签与 ken 不一），
    且起局法缺省与上游不同（见 _QIMEN_QIJU_METHODS 注）。认不出的起局法/盘式/排盘家/时间算法报错，不静默归一。
    """
    # 顶层 qijuMethod/paiPanType/school 也认：澄清闸 elicitation 表单按 `values` 把答案落在顶层同名键。
    options: dict[str, Any] = {
        key: payload[key]
        for key in ("timeAlg", "after23NewDay", "lateZiHourUseNextDay", "qijuMethod", "paiPanType", "school")
        if payload.get(key) is not None
    }
    raw = payload.get("options")
    if isinstance(raw, dict):
        options.update(raw)
    method = options.get("qijuMethod")
    if method in (None, ""):
        options["qijuMethod"] = "zhirun"
    elif method not in _QIMEN_QIJU_METHODS:
        raise _qimen_option_error("qijuMethod", method, list(_QIMEN_QIJU_METHODS))
    if options["qijuMethod"] == "shuzi" and not re.sub(r"[^0-9]", "", str(options.get("shuziReportNumber") or "")):
        # 上游 calcDunJia：报数空 → 静默退节气拆补（「占位不崩」，页面上有输入框可见）；headless 没有那个框，直接报错。
        raise ToolValidationError(
            bilingual(
                "阴盘报数起局（qijuMethod=shuzi）需要 options.shuziReportNumber（报数，如 258）。",
                "qijuMethod=shuzi needs options.shuziReportNumber (the reported number, e.g. 258).",
            ),
            code="tool.qimen_invalid_option",
            details={"field": "shuziReportNumber", "value": options.get("shuziReportNumber")},
        )
    school = options.get("school")
    if school not in (None, "") and school not in _QIMEN_SCHOOLS:
        raise _qimen_option_error("school", school, list(_QIMEN_SCHOOLS))
    if options.get("paiPanType") not in (None, ""):
        pai_pan = _js_parse_int(options.get("paiPanType"))
        if pai_pan not in _QIMEN_PAIPAN_TYPES:
            raise _qimen_option_error("paiPanType", options.get("paiPanType"), list(_QIMEN_PAIPAN_TYPES))
        options["paiPanType"] = pai_pan
    if options.get("timeAlg") not in (None, ""):
        # 上游奇门只两档（DunJiaCalc.js TIME_ALG_OPTIONS）；JS normalizeTimeAlg 只认数字 1（`=== 1`），
        # 字符串 "1" 会被当真太阳时 —— 故此处统一收成 int，不让两层对同一个值各读一套。
        time_alg = options.get("timeAlg")
        if isinstance(time_alg, bool) or str(time_alg).strip() not in {"0", "1"}:
            raise _qimen_option_error("timeAlg", time_alg, [0, 1])
        options["timeAlg"] = int(str(time_alg).strip())
    return options


def _qimen_local_route_reasons(options: dict[str, Any]) -> list[str]:
    """上游路由单源 isQimenLocalRoute / qimenLocalOnlyOverrides（DunJiaCalc.js:1195-1226）的 Python 镜像。

    非空 = 走本地 calcDunJia（年/月/日/刻/金函家、飞盘/混合、阴盘报数、七组本地口径任一非缺省）——ken `/qimen/pan`
    只收排盘家/起局法/盘式，这些口径后端不认、合并阶段也不施加，照打 ken 会得到「按缺省出盘、[盘型]却标所选」。
    Python 先判（决定打不打 ken），JS 用 vendored isQimenLocalRoute 再判一次并回报 `route`，两边不一致即报错
    （tool.qimen_route_check_failed）——上游改了判据，这里当场红，而不是静默分叉。
    """
    reasons: list[str] = []
    pai_pan = _js_parse_int(options.get("paiPanType"))
    if (3 if pai_pan is None else pai_pan) not in (3, 5):
        reasons.append("paiPanType")
    if options.get("school") in ("飞盘", "混合"):
        reasons.append("school")
    if options.get("qijuMethod") == "shuzi":
        reasons.append("qijuMethod")
    zhi_shi = _js_parse_int(options.get("zhiShiType"))
    if (0 if zhi_shi is None else zhi_shi) != 0:
        reasons.append("zhiShiType")
    leap_days = _js_parse_int(options.get("zhirunLeapDays"))
    if options.get("qijuMethod") == "zhirun" and (9 if leap_days is None else leap_days) != 9:
        reasons.append("zhirunLeapDays")
    for key, default in (("godsPreset", "baihu_xuanwu"), ("jiGongMode", "kun"), ("anGanMode", "off")):
        if options.get(key) and options.get(key) != default:
            reasons.append(key)
    if options.get("kongMarkBoth"):
        reasons.append("kongMarkBoth")
    shift = _js_parse_int(options.get("shiftPalace")) or 0
    shift = 0 if shift < 0 else (shift % 8 if shift > 7 else shift)
    if shift and options.get("shiftZhiFuMode") == "recalc":
        reasons.append("shiftZhiFuMode")
    return reasons


def _parse_solar_datetime_text(text: Any) -> dict[str, int] | None:
    """上游 DunJiaCalc.js parseDateTimeText：从 nongli.birth（真太阳时串）取年月日时分秒。"""
    normalized = str(text or "").strip().replace("T", " ", 1).replace("Z", " ", 1).strip()
    match = re.search(r"([-+]?\d{1,6})[/-](\d{1,2})[/-](\d{1,2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?", normalized)
    if not match:
        return None
    year, month, day, hour, minute, second = match.groups()
    return {
        "year": int(year), "month": int(month), "day": int(day),
        "hour": int(hour), "minute": int(minute), "second": int(second or 0),
    }


def _parse_taiyi_datetime_text(text: Any) -> dict[str, int] | None:
    """上游 TaiYiCalc.js / JinKouCalc.js parseDateTimeText（行首锚定、分可单位数）：nongli.birth → 年月日时分秒。"""
    match = re.match(r"^(-?\d{1,6})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?", str(text or "").strip())
    if not match:
        return None
    year, month, day, hour, minute, second = match.groups()
    return {
        "year": int(year), "month": int(month), "day": int(day),
        "hour": int(hour), "minute": int(minute), "second": int(second or 0),
    }


def _qimen_ken_payload(payload: dict[str, Any], options: dict[str, Any], nongli: Any) -> dict[str, Any]:
    """`/qimen/pan` 请求体，逐键对齐上游 fetchQimenPan（DunJiaCalc.js:1473-1495）。

    时间：timeAlg=0（缺省）用 nongli.birth 校正后的真太阳时分量（上游 resolveCalcDateTime）——此前 skill 恒发钟表时，
    ken 只把 realSunTime 当回显，于是九宫按钟表时起、时柱按真太阳时标，两套时辰。
    """
    nongli = nongli if isinstance(nongli, dict) else {}
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    display_solar = context.get("displaySolarTime") or nongli.get("birth", "")
    parts: dict[str, int] = _ken_datetime_parts(payload)
    if options.get("timeAlg") != 1:
        solar = _parse_solar_datetime_text(nongli.get("birth") or context.get("displaySolarTime"))
        if solar:
            parts = {**parts, **solar}
    method = options.get("qijuMethod") or "zhirun"
    return {
        **parts,
        "zone": payload.get("zone"),
        "qimenMode": _ken_qimen_mode(options),
        "qijuMethod": method,
        "option": 2 if method == "zhirun" else 1,
        "school": options.get("school") or "转盘",
        "date": payload.get("date"),
        "time": payload.get("time"),
        "realSunTime": display_solar,
        "jiedelta": nongli.get("jiedelta", ""),
        # 显式日界/晚子时开关直达权威引擎（缺省不发→引擎默认 1/1）。
        **_day_boundary_switches(options),
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
        # v0.36.0 C6：快照排版口径 = 镜像的上游 aiExport 版本（与 exports.registry 常量锁步；v57 切换时同批动）
        "astro_snapshot_format_version": MIRRORED_UPSTREAM_AIEXPORT_VERSION,
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
    # JS Math.round = floor(x+0.5)：half 一律向 +∞。曾写 int(x+0.5)——int 向零截断，负数全错
    # （-1.7 → -1，JS 为 -2）；AGENTS §4 一直写的是 floor，实现没跟上。
    try:
        return math.floor(float(value) + 0.5)
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
    """[大限] 的 Python 兜底（仅当 JS 段 builder 不可用时用；正路是 vendored buildGuolaoLimitSection）。"""
    life = _guolao_life_degree(chart)
    # 🔴 skill 归一后的日期是 YYYY-MM-DD（上游 fieldsToParams 才是 YYYY/MM/DD）：旧版只按 '/' 切，
    # int('2028-04-06') 失败 → 出生年恒 0 →「（0-12年）」这类年份全错。两种分隔都认。
    m = re.match(r"\s*(-?\d{1,4})", str(payload.get("date", "")))
    birth_year = int(m.group(1)) if m else 0
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


_GANZHI_STEMS = "甲乙丙丁戊己庚辛壬癸"
_GANZHI_BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


def _ganzhi_year(year: int) -> str:
    """公历年 → 干支年（1984=甲子；与上游 GuoLaoChartMain.stemBranchForYear 同式）。"""
    idx = ((int(year) - 1984) % 60 + 60) % 60
    return f"{_GANZHI_STEMS[idx % 10]}{_GANZHI_BRANCHES[idx % 12]}"


def _moira_transit_moment(payload: dict[str, Any]) -> tuple[str, str]:
    """流年盘时刻：显式 moiraTransitDate/Time，缺省 = 当前日期（按出生时区）正午。"""
    date = f"{payload.get('moiraTransitDate') or ''}".strip().replace("/", "-")
    time_text = f"{payload.get('moiraTransitTime') or ''}".strip() or "12:00:00"
    if date:
        return date, time_text
    zone = f"{payload.get('zone') or ''}".strip()
    offset = timedelta(0)
    m = re.match(r"^([+-])(\d{1,2})(?::?(\d{2}))?$", zone)
    if m:
        sign = -1 if m.group(1) == "-" else 1
        offset = sign * timedelta(hours=int(m.group(2)), minutes=int(m.group(3) or 0))
    elif re.fullmatch(r"-?\d{1,2}(\.\d+)?", zone):
        offset = timedelta(hours=float(zone))
    now = datetime.now(timezone.utc) + offset
    return now.strftime("%Y-%m-%d"), time_text


def _swap_guolao_node_ids_deep(value: Any) -> Any:
    """上游 swapGuolaoNodeIdsDeep（GuoLaoChartMain.js:1150-1188）：北交/南交 id 深换（含字典键），其余原样。"""
    swap = {"North Node": "South Node", "South Node": "North Node"}
    if isinstance(value, str):
        return swap.get(value, value)
    if isinstance(value, list):
        return [_swap_guolao_node_ids_deep(item) for item in value]
    if isinstance(value, dict):
        return {swap.get(k, k) if isinstance(k, str) else k: _swap_guolao_node_ids_deep(v) for k, v in value.items()}
    return value


def _apply_guolao_node_mode(chart_obj: Any, settings: dict[str, Any]) -> Any:
    """上游 applyGuolaoNodeMode（:1202-1211）：罗计取「北罗南计」时整盘深换北/南交 id（盘面、规则、快照同吃换位后的盘），
    缺省「北计南罗」原样返回。"""
    if settings.get("guolaoNodeMode") != "northRahuSouthKetu" or not isinstance(chart_obj, dict):
        return chart_obj
    return _swap_guolao_node_ids_deep(copy.deepcopy(chart_obj))


def _build_guolao_snapshot_text(
    payload: dict[str, Any],
    response: dict[str, Any],
    pattern_text: str | None = None,
    *,
    info_sections: dict[str, Any] | None = None,
) -> str:
    """七政四余快照。`info_sections` = JS `guolao_moira` 的 info_sections 动作结果（vendored 上游段 builder）：
    anchorLines（[起盘信息] 命度/身度/宿主行）/ limitSection（[大限]）/ masters（[三主与化曜]）/ limitCalc（[限法实算]）。
    段序同上游 _buildGuolaoSnapshotTextV2Core（GuoLaoChartMain.js:2040-2140）：大限 → 三主与化曜 → 限法实算 →
    （虚实/本命化曜/流年流曜 由 runner 插在 [政余格局] 之前）。"""
    info = info_sections if isinstance(info_sections, dict) else {}
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
        for branch, god_info in zi_gods.items():
            if not isinstance(god_info, dict):
                continue
            gods_lines.append(
                f"{branch}：神煞={'、'.join(god_info.get('allGods', []) or []) or '无'}；太岁神={'、'.join(god_info.get('taisuiGods', []) or []) or '无'}"
            )
    info_lines = [
        f"日期：{payload.get('date', '—')} {payload.get('time', '—')}",
        f"时区：{payload.get('zone', '—')}",
        f"经纬度：{payload.get('lon', '—')} {payload.get('lat', '—')}",
        # [Q-191/T-134]（上游 GuoLaoChartMain.js:2046）时间基准 + 七政两套时标补注。上游 fieldsToParams 不带
        # timeAlg（盘面星体恒按输入钟面时刻换算）→ timeBasisLabel(undefined) = 钟表时；日界两键缺省取上游全局缺省 1/1
        # （defaultAfter23NewDay / defaultLateZiHourUseNextDay，本命四柱 /nongli/time 同口径）。
        build_time_basis_line(
            time_alg=None,
            late_zi_hour_use_next_day=1 if payload.get("lateZiHourUseNextDay") is None else payload.get("lateZiHourUseNextDay"),
            after23_new_day=1 if payload.get("after23NewDay") is None else payload.get("after23NewDay"),
            note=GUOLAO_TIME_BASIS_NOTE,
        ),
        # 七政命度 / 罗计 / 报时星太阳时 / 罗计取法 / 宿度制·身宫法 / 命主取法·行运法（上游 GuoLaoChartMain.js:2047-2073，
        # vendored buildGuolaoSetupLines 逐字产出）。
        *[f"{line}" for line in (info.get("setupLines") or []) if f"{line}".strip()],
        # [Q-231/Q-434]（上游 GuoLaoChartMain.js:2073-2076）命度 / 身度 / 命度宿主·身度宿主（右栏同源事实层）。
        *[f"{line}" for line in (info.get("anchorLines") or []) if f"{line}".strip()],
    ]
    limit_text = f"{info.get('limitSection') or ''}".strip() or "\n".join(_build_guolao_limit_lines(chart, payload)).strip()
    sections: list[tuple[str, str]] = [
        ("起盘信息", "\n".join(info_lines)),
        ("七政四余宫位与二十八宿星曜", "\n".join(house_lines).strip() or "无"),
        ("神煞", "\n".join(gods_lines).strip() or "无"),
        ("大限", limit_text or "无"),
    ]
    # [Q-435]（上游 GuoLaoChartMain.js:2092-2104）三主化曜 / 难仇恩用 与 五限实算 / 行运法实算：有数据才产段。
    masters_text = f"{info.get('masters') or ''}".strip()
    if masters_text:
        sections.append(("三主与化曜", masters_text))
    limit_calc_text = f"{info.get('limitCalc') or ''}".strip()
    if limit_calc_text:
        sections.append(("限法实算", limit_calc_text))
    sections += [
        # 政余格局 (星阙 v2.6.x Moira DSL)：由 vendored guolaoMoira.js (buildLocalMoiraPatterns) 评估，
        # 经 js_client 注入。盘面物象格局（孛犯太阳/金水相涵/命坐两歧 等）可出；依赖 七政神煞(官福疾)
        # 的格局受限于上游 guolaoGods 未随 /chart 返回（kinastro qizheng 另路，如实标出，见 AGENTS）。
        ("政余格局", (pattern_text or "").strip() or "无"),
        ("相位", "\n".join(_build_guolao_aspect_lines(chart, response)).strip() or "无"),
    ]
    return _render_snapshot_text(sections)


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


def _build_base_info_lines(chart_wrap: dict[str, Any], fields: dict[str, Any], *, with_time_basis: bool = False) -> list[str]:
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
    # 跨技法时间基准自声明（上游 astroAiSnapshot.js:442-445，v3.11）：星盘按输入钟面时刻与时区换算世界时起盘，
    # 只在整盘快照的 [起盘信息] 出（buildAstroSnapshotContent 传 withTimeBasis；[信息] 段复用本函数但不带）。
    if with_time_basis:
        lines.append(
            build_time_basis_line(
                time_alg=1,
                late_zi_hour_use_next_day=fields.get("lateZiHourUseNextDay"),
                after23_new_day=fields.get("after23NewDay"),
            )
        )
    zodiacal = chart.get("zodiacal") or ASTRO_HOUSE_SYSTEM_TEXT.get(str(fields.get("zodiacal")), fields.get("zodiacal"))
    # [Q-148/T-55]（上游 astroAiSnapshot.js:461-463）：派生盘（十三分/十二分/调波/龙盘）宫位被后端强制为
    # 「变换后上升整宫」、每宫打 houses[].hsysDerived='wholeFromAsc' —— 请求里的分宫制不是这张盘实际用的，
    # 标注必须说真话（数值不动）。非派生盘沿用本仓既有口径（后端回显优先）。
    hsys = (
        derived_whole_sign_label_of(chart)
        or chart.get("hsys")
        or ASTRO_HOUSE_SYSTEM_TEXT.get(str(fields.get("hsys")), fields.get("hsys"))
    )
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


def _only_ruler_exalt_reception(fields: dict[str, Any] | None) -> bool:
    """上游 resolveOnlyRulerExaltReception（astroAiSnapshot.js:190-207）：全局设置 showOnlyRulExaltReception（1/true）=
    「仅按本垣擢升计算互容接纳」。headless 无 localStorage，请求顶层同名键即该全局设置；缺省关。"""
    value = (fields or {}).get("showOnlyRulExaltReception") if isinstance(fields, dict) else None
    return value in (1, True, "1", "true", "True")


def _has_ruler_or_exalt(ary: Any) -> bool:
    return isinstance(ary, list) and any(value in ("ruler", "exalt") for value in ary)


def _keep_reception_line(item: dict[str, Any] | None, *, abnormal: bool = False, only_ruler_exalt: bool = False) -> bool:
    """上游 keepReceptionLine（astroAiSnapshot.js:222-235）：开关关 → 全留；开 → 正接纳须供给方为本垣/擢升，
    邪接纳供给方或受益方任一为本垣/擢升即留。"""
    if not only_ruler_exalt:
        return True
    if not isinstance(item, dict):
        return False
    supplier_ok = _has_ruler_or_exalt(item.get("supplierRulerShip"))
    if not abnormal:
        return supplier_ok
    return supplier_ok or _has_ruler_or_exalt(item.get("beneficiaryDignity"))


def _keep_mutual_line(item: dict[str, Any] | None, *, only_ruler_exalt: bool = False) -> bool:
    """上游 keepMutualLine（astroAiSnapshot.js:237-245）：开 → 互容两方都须为本垣/擢升。"""
    if not only_ruler_exalt:
        return True
    if not isinstance(item, dict) or not isinstance(item.get("planetA"), dict) or not isinstance(item.get("planetB"), dict):
        return False
    return _has_ruler_or_exalt(item["planetA"].get("rulerShip")) and _has_ruler_or_exalt(item["planetB"].get("rulerShip"))


def _reception_reject_mark(item: dict[str, Any] | None) -> str:
    # FIX-15（镜像 astroAiSnapshot.isReject）：supplier 在 beneficiary 所在座为 exile/fall = 凶接纳=拒绝。
    dig = item.get("supplierRulerShip") if isinstance(item, dict) else None
    if not dig:
        return ""
    arr = dig if isinstance(dig, list) else [dig]
    return "（拒绝）" if any(d in ("exile", "fall") for d in arr) else ""


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

    only_rul_exalt = _only_ruler_exalt_reception(fields)
    receptions = chart_data.get("receptions", {}) if isinstance(chart_data, dict) else {}
    normal_receptions = [
        item for item in receptions.get("normal", []) or [] if _keep_reception_line(item, only_ruler_exalt=only_rul_exalt)
    ]
    abnormal_receptions = [
        item for item in receptions.get("abnormal", []) or []
        if _keep_reception_line(item, abnormal=True, only_ruler_exalt=only_rul_exalt)
    ]
    if normal_receptions or abnormal_receptions:
        lines.append("接纳")
        lines.append("正接纳：")
        for item in normal_receptions:
            lines.append(
                f"{_astro_msg_with_house(item.get('beneficiary'), chart_wrap, short=True)} 被 "
                f"{_astro_msg_with_house(item.get('supplier'), chart_wrap, short=True)} 接纳 "
                f"({_ruleship_text(item.get('supplierRulerShip'))}){_reception_reject_mark(item)}"
            )
        lines.append("邪接纳：")
        for item in abnormal_receptions:
            lines.append(
                f"{_astro_msg_with_house(item.get('beneficiary'), chart_wrap, short=True)} "
                f"({_ruleship_text(item.get('beneficiaryDignity'))}) 被 "
                f"{_astro_msg_with_house(item.get('supplier'), chart_wrap, short=True)} 接纳 "
                f"({_ruleship_text(item.get('supplierRulerShip'))}){_reception_reject_mark(item)}"
            )

    mutuals = chart_data.get("mutuals", {}) if isinstance(chart_data, dict) else {}
    normal_mutuals = [item for item in mutuals.get("normal", []) or [] if _keep_mutual_line(item, only_ruler_exalt=only_rul_exalt)]
    abnormal_mutuals = [item for item in mutuals.get("abnormal", []) or [] if _keep_mutual_line(item, only_ruler_exalt=only_rul_exalt)]
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
        # [Q-254/T-227]（上游 astroAiSnapshot.js:719-722）：正合（|orbDir|<0.3，不分入离）相态写「正合」，
        # 不再与 Separative 同折为「离相」。四态序 入相/正合/离相/None 与上游同。
        for key, state in (("Applicative", "入相"), ("Exact", "正合"), ("Separative", "离相"), ("None", "")):
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
        # 链行逐字同上游 astroAiSnapshot.js:1037 `${msg(id)}：${chain.map(msg).join(' → ')}`——msg 走 AstroTxtMsg，
        # 行星是单字（日/月/火…），与同段尾部整宫制宫主表的「宫主」列同一译名（此前本仓用长名「太阳/火星」）。
        lines = [
            f"{_astro_msg(d.get('id'), short=True)}：{' → '.join(_astro_msg(k, short=True) for k in (d.get('chain') or []))}"
            for d in dispositor
            if isinstance(d, dict)
        ]
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
        lines += _lifespan_detail_lines(ls)
        # 上游 buildSectionText：逐行 trim、去空行。
        out["寿命格局"] = "\n".join(line.strip() for line in lines if line.strip())
    return out


# 上游 utils/astroAiSnapshot.js:1187-1233 英文 token 中文化表（逐字；未收的 token 原样输出，如 viaDignity=exaltation）。
_LIFESPAN_VIA_DIGNITY = {"ruler": "本垣", "exalt": "擢升", "triplicity": "三分", "term": "界", "face": "面 / 十度"}
_LIFESPAN_ANGULARITY = {"angular": "角宫", "succedent": "续宫", "cadent": "果宫"}
_LIFESPAN_BAND = {"greatest": "大限", "mean": "中限", "least": "小限", "max": "大限", "min": "小限"}
_LIFESPAN_STATE_HAYYIZ = {"Hayyiz": "得时得地", "DemiHayyiz": "半得", "InWrongPos": "失位", "None": ""}
_LIFESPAN_STATE_SUN = {"cazimi": "核心", "combust": "焦伤", "under_beams": "日光束下", "underBeams": "日光束下", "free": "自由光"}
_LIFESPAN_STATE_ORIENT = {"oriental": "东出", "occidental": "西入"}
_LIFESPAN_STATE_MOTION = {"retro": "逆行", "direct": "顺行", "stationary": "停滞"}


def _lifespan_js_value(value: Any) -> str:
    """JS `${v}`：null → 'null'（JSON 回传保留 null；undefined 键不回传）。"""
    return "null" if value is None else _ptext.js_str(value)


def _lifespan_detail_lines(res: dict[str, Any]) -> list[str]:
    """逐字镜像上游 utils/astroAiSnapshot.js:1172-1245 buildLifespanSection 的 FIX-8/9/10 尾段：
    取主法 + 朔/望月、生命主候选、寿主星细节/修正（FIX-8）；医疗危机（FIX-9）；行星状态盘（FIX-10，太阳三态
    列随 params 的 cazimiOrb/combustOrb/underBeamsOrb [SURF-3]）。名称走本段既有的 _lifespan_name。"""
    lines: list[str] = []
    if res.get("method"):
        lines.append(f"取主法：{res['method']}")
    if res.get("birthType"):
        lines.append(f"朔/望月：{'朔月(合)' if res['birthType'] == 'conjunctional' else '望月(冲)'}")
    candidates = res.get("candidates")
    if isinstance(candidates, list) and candidates:
        lines.append("生命主候选：")
        for c in candidates:
            if not isinstance(c, dict) or not c.get("key"):
                continue
            aphetic = "投射" if c.get("aphetic") else "非投射"
            rank = f"rank={_ptext.js_str(c['rank'])}" if c.get("rank") is not None else ""
            reason = f"·{c['reason']}" if c.get("reason") else ""
            house = f"第{_ptext.js_str(c['house'])}宫" if c.get("house") else ""
            lines.append(f"{_lifespan_name(c.get('key'))} {house}·{aphetic}{'·' + rank if rank else ''}{reason}")
    alc = res.get("alcocoden")
    if isinstance(alc, dict) and alc:
        detail = []
        if alc.get("viaDignity"):
            detail.append(f"经{_LIFESPAN_VIA_DIGNITY.get(alc['viaDignity']) or alc['viaDignity']}")
        if alc.get("angularity"):
            detail.append(_LIFESPAN_ANGULARITY.get(alc["angularity"]) or f"{alc['angularity']}")
        if alc.get("band"):
            detail.append(f"限 {_LIFESPAN_BAND.get(alc['band']) or alc['band']}")
        if "baseYears" in alc:
            detail.append(f"基础{_lifespan_js_value(alc['baseYears'])}年")
        if detail:
            lines.append(f"寿主星细节：{'；'.join(detail)}")
        modifiers = alc.get("modifiers")
        if isinstance(modifiers, list):
            for m in modifiers:
                if not isinstance(m, dict):  # JS `if(!m) return;`：对象（含 {}）恒为真
                    continue
                planet = _lifespan_name(m.get("planet")) if m.get("planet") else ""
                aspect = f"·{m['aspect']}" if m.get("aspect") else ""
                delta = f"(Δ{_ptext.js_str(m['delta'])})" if m.get("delta") is not None else ""
                kind = f"·{m['kind']}" if m.get("kind") else ""
                lines.append(f"修正：{planet}{aspect}{delta}{kind}")
    medical = res.get("medical")
    if isinstance(medical, dict) and medical:
        parts = []
        sixth_sign = medical.get("sixthSign")
        if sixth_sign:
            # HIGH-2：引擎 sixth.sign 小写 → 首字大写再 msg()。
            cap = sixth_sign[:1].upper() + sixth_sign[1:] if isinstance(sixth_sign, str) else sixth_sign
            parts.append(f"六宫{_astro_msg(cap)}")
        if medical.get("sixthRuler"):
            parts.append(f"六宫主 {_lifespan_name(medical['sixthRuler'])}")
        if parts:
            lines.append(f"医疗危机：{'；'.join(parts)}")
        afflictions = medical.get("hylegAfflictions")
        if isinstance(afflictions, list) and afflictions:
            joined = "、".join(
                f"{_lifespan_name(x.get('planet') or x.get('id'))}{'·' + x['aspect'] if x.get('aspect') else ''}"
                for x in afflictions
                if isinstance(x, dict)
            )
            lines.append(f"生命主受克：{joined}")
        body = medical.get("bodyHyleg")
        if isinstance(body, list) and body:
            lines.append(f"生命主部位：{'、'.join(f'{b}' for b in body)}")
        if medical.get("note"):
            lines.append(f"备注：{medical['note']}")
    states = res.get("states")
    rows = states.get("rows") if isinstance(states, dict) else None
    if isinstance(rows, list) and rows:
        lines.append("行星状态盘：")
        for row in rows:
            if not isinstance(row, dict) or not row.get("planet"):
                continue
            parts = []
            if row.get("hayyiz") and row["hayyiz"] != "None":
                label = _LIFESPAN_STATE_HAYYIZ.get(row["hayyiz"])
                if label:
                    parts.append(label)
            if row.get("sunState") and row["sunState"] != "None":
                parts.append(_LIFESPAN_STATE_SUN.get(row["sunState"]) or f"{row['sunState']}")
            if row.get("orient"):
                parts.append(_LIFESPAN_STATE_ORIENT.get(row["orient"]) or f"{row['orient']}")
            if row.get("motion"):
                parts.append(_LIFESPAN_STATE_MOTION.get(row["motion"]) or f"{row['motion']}")
            if row.get("inSect") is True:
                parts.append("同宗派")
            elif row.get("inSect") is False:
                parts.append("异宗派")
            if row.get("house"):
                parts.append(f"第{_ptext.js_str(row['house'])}宫")
            lines.append(f"{_lifespan_name(row.get('planet'))}：{'·'.join(parts)}")
    return lines


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


def _pattern_overview(response: dict[str, Any], *, only_ruler_exalt: bool = False) -> dict[str, Any]:
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
    # 「仅按本垣擢升计算互容接纳」开时先滤互容/接纳（上游 astroPatternOverview.js:197-207 keepRec/keepMut），
    # 先验权力的联结与 [信息] 段详细行同口径。
    m_raw = response.get("mutuals") or {}
    r_raw = response.get("receptions") or {}
    m = {k: [it for it in (m_raw.get(k) or []) if _keep_mutual_line(it, only_ruler_exalt=only_ruler_exalt)] for k in ("normal", "abnormal")}
    r = {
        "normal": [it for it in (r_raw.get("normal") or []) if _keep_reception_line(it, only_ruler_exalt=only_ruler_exalt)],
        "abnormal": [it for it in (r_raw.get("abnormal") or []) if _keep_reception_line(it, abnormal=True, only_ruler_exalt=only_ruler_exalt)],
    }
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


def _pattern_overview_lines(response: dict[str, Any], *, only_ruler_exalt: bool = False) -> list[str]:
    try:
        data = _pattern_overview(response, only_ruler_exalt=only_ruler_exalt)
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


def _astro_msg_short(value: Any) -> str:
    """上游 astroAiSnapshot `msg()` 的等价：AstroTxtMsg 优先（行星单字 日/月/火…，星座 牡羊…，宫 id 第一宫…）。"""
    return _astro_msg(value, short=True)


# classicalParamSpec.js:249-256 的全局仓缺省（headless 无本机仓 = 缺省档）：恒星平轨 1°、轨档 school。
_FIXED_STAR_ORB_DEFAULT = 1
_FIXED_STAR_ORB_MODE_DEFAULT = "school"


def _fixed_star_orb_params(params: dict[str, Any]) -> dict[str, Any]:
    """上游 classicalChartGlobals.js:271 fixedStarOrbParamsFor：/astroextra/analysis 的恒星轨参数。

    随盘优先（chart 级键 starOrb/starOrbMode，缺则前端名 fixedStarOrb/fixedStarOrbMode），再缺取全局缺省；
    档位仅 byMagnitude 时下发（Python fixed_star_hits 据此逐星取星等表轨）。
    """
    def pick(first: Any, second: Any) -> Any:
        return first if first is not None and first != "" else second

    orb = pick(params.get("starOrb"), pick(params.get("fixedStarOrb"), _FIXED_STAR_ORB_DEFAULT))
    mode = pick(params.get("starOrbMode"), pick(params.get("fixedStarOrbMode"), _FIXED_STAR_ORB_MODE_DEFAULT))
    out: dict[str, Any] = {"fixedStarOrb": orb}
    if mode == "byMagnitude":
        out["fixedStarOrbMode"] = "byMagnitude"
    return out


def _build_astro_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    sections = [
        # 上游 buildAstroSnapshotContent 的 [起盘信息] 带时间基准行（astroAiSnapshot.js:1696 withTimeBasis）。
        # 印占：上游 buildIndiaSnapshotText（IndiaChart.js:1170-1175）在 [起盘信息] 起首加流派 / 大运流派开关 / 当前分盘 /
        # 分盘四行（vendored buildIndiaSchoolHeaderLines，由 _attach_jyotish_sections 挂 `_indiaSchoolLines`）。
        ("起盘信息", [
            *[f"{line}" for line in (response.get("_indiaSchoolLines") or []) if f"{line}".strip()],
            *_build_base_info_lines(response, payload, with_time_basis=True),
        ]),
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
    # 星阙顺序: …主宰星链, 分宫制宫神星表, 古典, 古典格局, 寿命格局, 可能性.
    # `_natalExtras` 由 `_attach_natal_extras` 挂（西占 chart 家族 + 嵌入整盘）：JS 失败时也挂空 dict，
    # 让下面两块纯 Python 的宫主表照出（JS 只供链行 / 12分度 / 寿命格局）。
    extras = response.get("_natalExtras") if isinstance(response.get("_natalExtras"), dict) else None
    if extras is not None:
        body = extras.get("12分度")
        if body and f"{body}".strip():
            rendered.append(("12分度", f"{body}".strip()))
        # v57（上游 #79，astroAiSnapshot.js:1039-1048）：[主宰星链] = 链行 + 判读口径行 + ◆ 整宫制宫主表
        # （宫主/主宰口径 = 整宫制 = [起盘信息] 的 nR 标记）。v56 挂在这里的「当前分宫制宫神星表」迁出成下一段。
        chain = f"{extras.get('主宰星链') or ''}".strip()
        dispositor = "\n".join(line for line in [chain, *build_dispositor_ruler_tail_lines(response, _astro_msg_short)] if line).strip()
        if dispositor:
            rendered.append(("主宰星链", dispositor))
        # [分宫制宫神星表]（astroAiSnapshot.js:1063-1077，preset 九键紧随 [主宰星链]）：当前分宫制宫头星座的宫主表
        # （行星力量/角续果/实际落宫口径），上升整宫制盘折叠成一行说明。
        house_system = build_house_system_ruler_section_lines(response, payload, _astro_msg_short)
        if house_system:
            rendered.append(("分宫制宫神星表", "\n".join(house_system).strip()))
    classical = _build_classical_section(response)
    if classical:
        rendered.append(("古典", "\n".join(classical).strip()))
    # v3.9.2 古典衍化四段（派生宫转宫/气候带/显赫计分/世界范式盘）：vendored astroClassicalDerived
    # 单源计算，上游 opt-in（仅本命 astro 快照路径）→ 只在 `_classicalDerived` 已挂载（= chart 工具）
    # 时出段；段序按上游 v56 preset 插在 古典 与 古典格局 之间。
    derived = response.get("_classicalDerived") if isinstance(response.get("_classicalDerived"), dict) else None
    if derived:
        for title in ("古典·派生宫转宫", "古典·气候带", "古典·显赫计分", "古典·世界范式盘"):
            body = derived.get(title)
            if body and f"{body}".strip():
                rendered.append((title, f"{body}".strip()))
    classical_analysis = _build_classical_analysis_section(response.get("_classicalAnalysis") or {})
    # 格局速览 (龙脉/孤月独明/先验权力/…) 仅随 [古典格局] 段一并出 —— 即仅 _classicalAnalysis 已挂载的
    # chart 家族(astrochart/astrochart_like)；india/mundane 等无 [古典格局] preset 的盘不挂，避免 unknown 段。
    if response.get("_classicalAnalysis") is not None:
        pov = _pattern_overview_lines(response, only_ruler_exalt=_only_ruler_exalt_reception(payload))
        if pov:
            classical_analysis = (classical_analysis or []) + ["格局速览"] + pov
    if classical_analysis:
        rendered.append(("古典格局", "\n".join(classical_analysis).strip()))
    # [埃及历]：vendored builder 已带 `[埃及历]` 段头，这里只取正文（段头由导出层统一加）。
    egypt = response.get("_egyptSection")
    if isinstance(egypt, str) and egypt.strip():
        body = egypt.split("\n", 1)[1] if egypt.startswith("[埃及历]\n") else egypt
        if body.strip():
            rendered.append(("埃及历", body.strip()))
    if extras:
        body = extras.get("寿命格局")
        if body and f"{body}".strip():
            rendered.append(("寿命格局", f"{body}".strip()))
    possibility = _build_possibility_section(response)
    if possibility:
        rendered.append(("可能性", "\n".join(possibility).strip()))
    # 印度律盘专属 [大运Dasha]：vendored 上游 buildDashaSnapshotLines（IndiaChart.js:429-494）按所选大运体系出段
    # （Vimshottari / Yogini / Ashtottari / 条件宿系 / Chara / AKKG …，含小运全表），由 _attach_jyotish_sections 挂
    # `_indiaDashaLines`；无数据 = 上游 `if(dashaLines.length)` 同判不产段。此前这里是只认 Vimshottari 的旧版 Python 移植。
    dasha_lines = response.get("_indiaDashaLines")
    if isinstance(dasha_lines, list) and dasha_lines:
        rendered.append(("大运Dasha", "\n".join(f"{line}" for line in dasha_lines).strip()))
    # 印占 Jyotish 派生段（星阙 v3.6.0）：由 vendored `buildJyotishSnapshotLines` 逐字产出，
    # 段名与顺序均由上游 builder 决定（此处不重排、不改名），已出现过的段不重复追加。
    jyotish_sections = response.get("_jyotishSections")
    if isinstance(jyotish_sections, dict):
        seen_titles = {title for title, _ in rendered}
        for title, lines in jyotish_sections.items():
            if title in seen_titles:
                continue
            body = "\n".join(str(line) for line in lines).strip() if isinstance(lines, list) else f"{lines}".strip()
            if body:
                rendered.append((str(title), body))
    # 派生盘专属段（v3.9.2「快照重定源」）：[龙盘]/[调波盘]/[重置盘]，由各 runner 按上游 AuxLab
    # builder 逐字排出并挂 `_derivedSelf`；段序按上游 v56 preset 居末。空 lines 不产段（上游同形）。
    derived_self = response.get("_derivedSelf")
    if isinstance(derived_self, dict) and derived_self.get("title") and derived_self.get("lines"):
        body = "\n".join(str(line) for line in derived_self["lines"]).strip()
        if body:
            rendered.append((str(derived_self["title"]), body))
    # [附加分盘]（上游 v3.11.0 #80，IndiaChart.js:1298-1333）：印度盘之外另挂的分盘简表，上游把它接在整份主盘快照
    # **末尾**（`${text}\n\n${附加分盘段}`）—— 由 `_attach_india_extra_vargas` 挂 `_indiaExtraVargas`；缺省不选 = 不产段。
    extra_vargas = response.get("_indiaExtraVargas")
    if isinstance(extra_vargas, str) and extra_vargas.strip():
        rendered.append(("附加分盘", extra_vargas.strip()))
    return _render_snapshot_text(rendered)


_HEADERLESS_SECTION_TITLE = re.compile(r"^\[(.+?)\]$", re.M)


def _headerless_astro_snapshot_text(fields: dict[str, Any], chart_wrap: dict[str, Any]) -> str:
    """上游 buildAstroSnapshotContent(chartObj, fields, {headerless: true})（astroAiSnapshot.js:1740-1742）。

    嵌入父段（relative 比较盘 A/B、jieqi 分至盘）的整盘：整行段头 `[X]` 转 `· X` 标签，否则按段切分会把
    子段当顶层段拆出、按父段名过滤会把盘体删净。富化（12分度/主宰星链链行/寿命格局/埃及历）由调用方先挂上。
    """
    text = _build_astro_snapshot_text(fields, chart_wrap)
    return _HEADERLESS_SECTION_TITLE.sub(lambda match: f"· {match.group(1)}", text)


# 挂载分盘可选集（上游 v3.11.0 constants/AstroConst.js:1508-1514 INDIA_MOUNT_VARGA_OPTIONS，逐字）。
_INDIA_MOUNT_VARGA_OPTIONS: tuple[tuple[int, str], ...] = (
    (1, "D1 命盘"), (2, "D2 财富"), (3, "D3 兄弟"), (4, "D4 家宅"), (7, "D7 子女"), (9, "D9 婚姻"),
    (10, "D10 事业"), (12, "D12 父母"), (16, "D16 车乘"), (20, "D20 修行"), (24, "D24 学业"), (27, "D27 体力"),
    (30, "D30 灾厄"), (40, "D40 母系"), (45, "D45 父系"), (60, "D60 总业"),
)
_INDIA_MOUNT_EXTRA_VARGA_MAX = 4  # AstroConst.js:1524 INDIA_MOUNT_EXTRA_VARGA_MAX


def _normalize_india_extra_vargas(value: Any) -> tuple[list[int], list[Any]]:
    """上游 normalizeIndiaExtraVargas（AstroConst.js:1525-1541）逐条移植：字符串按 `,，空白` 切；parseInt；
    <=1 / 不在可选集 / 重复 / 超上限 4 的项丢弃。返回 (保留, 丢弃)——上游静默丢，skill 把丢弃项回报进 warnings。"""
    raw: Any = value
    if isinstance(raw, str):
        raw = [part for part in re.split(r"[,，\s]+", raw.strip()) if part] if raw.strip() else []
    if not isinstance(raw, (list, tuple)):
        return [], ([value] if value not in (None, "", [], ()) else [])
    allowed = {num for num, _ in _INDIA_MOUNT_VARGA_OPTIONS}
    out: list[int] = []
    dropped: list[Any] = []
    for item in raw:
        m = re.match(r"\s*([+-]?\d+)", f"{item}")  # JS parseInt：取前导整数
        num = int(m.group(1)) if m else None
        if num is None or num <= 1 or num not in allowed or num in out or len(out) >= _INDIA_MOUNT_EXTRA_VARGA_MAX:
            dropped.append(item)
            continue
        out.append(num)
    return out, dropped


def _india_mount_varga_label(chartnum: int) -> str:
    """上游 indiaMountVargaLabel（AstroConst.js:1516-1522）。"""
    for num, label in _INDIA_MOUNT_VARGA_OPTIONS:
        if num == chartnum:
            return label
    return f"D{chartnum}"


# 上游 AstroConst.INDIA_DASHA_DISPLAY_ONLY_SYSTEMS（:1819）：前端展示体系，数据恒在响应 dasha 块，不下发 dashaSystem。
_INDIA_DASHA_DISPLAY_ONLY = ("taraDasha", "akkg")
# 上游 AstroConst.INDIA_SCHOOL_DEFAULTS（:1650-1676）的 ayanamsa / hsys 两列：无头复算「给了 indiaSchool 但未显式给
# 岁差/宫制时按该派预设补默认」（IndiaChart.resolveIndiaHeadlessParams :1197-1213）。只取这两列；流派行文字走 JS 同源表。
_INDIA_SCHOOL_PRESETS: dict[str, tuple[str, int]] = {
    "parashari": ("lahiri", 0), "jaimini": ("lahiri", 0), "tajika": ("lahiri", 0),
    "kp": ("krishnamurti", 3), "nadi": ("lahiri", 0), "western_sidereal": ("fagan_bradley", 3),
}
_INDIA_PRASHNA_KEYS = ("prashnaNumber", "prashnaMatter", "prashnaSchools", "prashnaCuspMode", "prashnaPrimaryHouse")
# 直通键（webindiasrv 按名读：dashaSystem :408 / dashaSeed :404 / sthiraStart :405 / transitDate :590 / tajakaYear :686 /
# annualChartType :1178）。上游只在给了值时下发（fieldsToParams「缺省 undefined → 不入请求体」），空串一律剔掉。
_INDIA_VERBATIM_KEYS = ("dashaSystem", "dashaSeed", "sthiraStart", "transitDate", "tajakaYear", "annualChartType")


def _india_apply_school_presets(payload: dict[str, Any]) -> dict[str, Any]:
    """流派预设补默认（resolveIndiaHeadlessParams :1197-1213）：给了 indiaSchool 而未显式给岁差/宫制 → 按该派预设补。
    幂等；run_tool 在取盘**之前**对规范化输入套用一次 —— 快照 [起盘信息] 的岁差/宫制行与请求同一口径。"""
    school = f"{payload.get('indiaSchool') or ''}".strip()
    if school not in _INDIA_SCHOOL_PRESETS:
        return payload
    ayan, hsys = _INDIA_SCHOOL_PRESETS[school]
    out = dict(payload)
    if out.get("indiaAyanamsa") in (None, ""):
        out["indiaAyanamsa"] = ayan
        out["siderealMode"] = ayan
    if out.get("indiaHsys") in (None, ""):
        out["indiaHsys"] = hsys
        out["hsys"] = hsys
    return out


def _india_chart_remote_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """india_chart 的后端请求体：skill 侧开关 → 后端键（上游 IndiaChart.fieldsToParams 同一翻译）。

    `indiaTripataki`（上游挂载齿轮名）→ 后端 `tripataki=1`（IndiaChart.js:123-124；webindiasrv 读 data.get('tripataki')，
    12 次建盘 ≈0.3-0.8s 故 opt-in）。`indiaExtraVargas` 不下发主盘请求（附加分盘逐张另取）。
    其余条件透传逐条对齐 fieldsToParams（IndiaChart.js:79-143）与 resolveIndiaHeadlessParams（:1197-1213）：
    dashaSystem 展示体系不下发；indiaSchool 只补预设岁差/宫制（本身不下发）；问事族只在起了卦（prashnaTime）时下发，
    且问时数缺/非法 → 1（[Q-126/T-34]：缺它后端 KP 问事整段空）；年盘异地须经纬齐备。"""
    payload = _india_apply_school_presets(payload)
    remote = {k: v for k, v in payload.items() if k not in ("indiaExtraVargas", "indiaTripataki", "indiaSchool")}
    if payload.get("indiaTripataki") in (True, 1, "1"):
        remote["tripataki"] = 1
    for key in _INDIA_VERBATIM_KEYS:
        if remote.get(key) == "":
            remote.pop(key)
    if payload.get("dashaSystem") in _INDIA_DASHA_DISPLAY_ONLY:
        remote.pop("dashaSystem", None)
    if payload.get("prashnaTime"):
        try:
            number = int(f"{payload.get('prashnaNumber')}")
        except (TypeError, ValueError):
            number = 0
        remote["prashnaNumber"] = number if 1 <= number <= 249 else 1
        if payload.get("prashnaCuspMode") == "asc_driven_placidus":
            remote.pop("prashnaCuspMode", None)
    else:
        for key in _INDIA_PRASHNA_KEYS:
            remote.pop(key, None)
    if payload.get("varshaLat") in (None, "") or payload.get("varshaLon") in (None, ""):
        remote.pop("varshaLat", None)
        remote.pop("varshaLon", None)
    return remote


def _is_astro_chart_payload(response_data: dict[str, Any]) -> bool:
    chart = response_data.get("chart")
    return isinstance(chart, dict) and isinstance(chart.get("objects"), list) and isinstance(chart.get("houses"), list)


def _export_body(body: str) -> dict[str, Any]:
    """段正文载体（v0.36.0）：只带 body。此前还带 `__export_data__`（整份 chart/objects…）并落进每个
    段的 `data` 键——同一引擎对象被复制 10+ 次，真实存档 qimen 5 MB / india_chart 101 MB（正文仅几 KB）。
    引擎对象只在 `data.<key>` 出现一次；段一律 body-only（LESSONS v0.36.0）。"""
    return {"__export_body__": body}


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


def _gua_code_lines(gua_code: Any, changed_code: Any) -> list[dict[str, Any]]:
    """给了本卦码（/变卦码）却没给 lines：卦线即码（初→上，1=阳），动爻 = 两码相异之位（_derive_changed_gua_code 的逆）。
    否则会落到以时起卦 —— [卦象] 写的是用户的本卦，[断卦结构]/[断诀命中] 判的却是另一卦。"""
    code = str(gua_code or "")
    if len(code) != 6 or set(code) - {"0", "1"}:
        return []
    changed = str(changed_code or "")
    moving = [len(changed) == 6 and changed[i] != code[i] for i in range(6)]
    return [{"value": int(code[i]), "change": moving[i], "god": None, "name": None} for i in range(6)]


# 十二地支序（子1…亥12 取 index+1）：时支类技法共用。
# 六爻「以时起卦」不在 Python 侧：上游无头路径是 buildTimeGua(nongli)（GuaZhanMain.js:74-98：nongli.year 年支序
# ——后端该键是农历年干支，立春至正月初一之间与 yearJieqi 不同 —— + 农历月数 monthInt + 农历日数 dayInt + 时柱支序），
# vendored 在 core-js，由 tools/liuyao.js 调用。此处曾手写一份「立春年支 + 月/日取地支序 + 钟表时辰」的变体，同一时刻
# 与上游起出不同的卦（sync311 wave 3 删）。
_SIXYAO_DIZHI = "子丑寅卯辰巳午未申酉戌亥"


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


# 上游 AstroText.AstroTxtMsg 的 8 颗汉堡虚星 + 白羊点（AstroText.js:458-467）；其余点走 `_astro_msg_short`。
_URANIAN_TXT_MSG: dict[str, str] = {
    "Cupido": "丘比特", "Hades": "哈迪斯", "Zeus": "宙斯", "Kronos": "克洛诺斯",
    "Apollon": "阿波罗", "Admetos": "阿德墨托斯", "Vulcanus": "伏尔甘", "Poseidon": "波塞冬",
    "AriesPoint": "白羊点",
}


def _uranian_msg(point_id: Any) -> str:
    """AstroMidpoint.js msg()：AstroTxtMsg 优先（虚星/白羊点中文名、行星单字、交点/四轴）。"""
    return _URANIAN_TXT_MSG.get(f"{point_id}", "") or _astro_msg_short(point_id)


# AstroMidpoint.js:405-407 六框中性命名（定局法），与 UranianHouseFrames 同表、同序。
_HOUSE_FRAMES = (
    ("meridian", "子午局"), ("ascendant", "上升局"), ("sun", "太阳局"),
    ("moon", "月亮局"), ("node", "交点局"), ("earth", "地球局"),
)


def _dial_planet_house(lon: float, cusps: list[Any]) -> int:
    """uranianDial.js:132 planetHouse：按弧长口径判点落宫（跨 0° 安全，不等距同样适用）。"""
    position = _dial_norm360(lon)
    for index in range(12):
        start, end = float(cusps[index]), float(cusps[(index + 1) % 12])
        if _dial_norm360(position - start) < _dial_norm360(end - start):
            return index + 1
    return 12


def _germany_house_frames_lines(germany_result: Any, dial_points: list[dict[str, Any]]) -> list[str]:
    """[六宫框落宫]（上游 AstroMidpoint.js:408-428 buildHouseFramesSection，[Q-442/T-405]）：六宫框全框 × 全点落宫表。

    页签「六宫框」缺省开（UranianDialStyle showHouseFrames=true，headless 无本机显示仓 = 缺省）→ 后端给了
    houseFrames 即出，不受汉堡门控。落宫取后端 frames[key].placements[id]，缺则按 cusps 定宫，再缺 '—'。
    """
    house_frames = germany_result.get("houseFrames") if isinstance(germany_result, dict) else None
    frames = house_frames.get("frames") if isinstance(house_frames, dict) else None
    if not isinstance(frames, dict):
        return []
    keys = [
        (key, label)
        for key, label in _HOUSE_FRAMES
        if isinstance(frames.get(key), dict) and (frames[key].get("placements") or isinstance(frames[key].get("cusps"), list))
    ]
    if not keys or not dial_points:
        return []

    def house_of(frame: dict[str, Any], point: dict[str, Any]) -> str:
        placements = frame.get("placements")
        if isinstance(placements, dict) and placements.get(point["id"]):
            return _js_template_str(placements[point["id"]])
        cusps = frame.get("cusps")
        if isinstance(cusps, list) and len(cusps) == 12:
            return f"{_dial_planet_house(point['lon'], cusps)}"
        return "—"

    lines = [
        "（子午局=东点 1 宫头·天顶 10 宫头赤道分宫；上升/太阳/月亮/交点/地球局=等宫；太阳局太阳落 4 宫、月亮局太阴落 10 宫、地球局 1 宫头恒 180°）",
        f"| 点 | {' | '.join(label for _, label in keys)} |",
        f"| --- | {' | '.join('---' for _ in keys)} |",
    ]
    for point in dial_points:
        lines.append(f"| {_uranian_msg(point['id'])} | {' | '.join(house_of(frames[key], point) for key, _ in keys)} |")
    return lines


# uranianDial.js:289 太阳弧速率；AstroMidpoint.js:432 校时事件类型中文。
_SOLAR_ARC_RATE = {"naibod": 0.9856473, "oneDeg": 1.0, "cardan": 0.9866667}
_SOLAR_ARC_LABEL = {"oneDeg": "1°/年", "cardan": "Cardan", "naibod": "Naibod"}
_RECTIFY_TYPE_CN = {"marriage": "婚姻", "children": "生育", "career": "事业", "move": "迁居", "loss": "丧亲", "accident": "意外", "other": "其他"}
_RECTIFY_DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M")


def _parse_local_moment(text: Any) -> datetime | None:
    """moment(<ISO/斜杠日期>) 的本地时刻（naive；上游两端同一浏览器时区，差值与时区无关）。无效 → None。"""
    raw = f"{text or ''}".strip()
    if not raw:
        return None
    raw = raw[:-1] if raw.endswith("Z") else raw
    for fmt in _RECTIFY_DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _germany_rectify_lines(payload: dict[str, Any], rectify_events: Any, dial_points: list[dict[str, Any]]) -> list[str]:
    """[校时预览]（上游 AstroMidpoint.js:433-468 buildRectifySection + uranianDial.js:389 rectificationHits，[Q-442/T-405]）。

    有待校事件（带 date）才产段。盘基/容许度/太阳弧取上游显示仓缺省（90° / 1° / Naibod；headless 无显示仓），
    容许度随请求 `orb`（上游 disp.orb）。Asc 微调滑块是即时预览态，不进快照（命中表按 0 微调）。
    """
    events = [event for event in (rectify_events or []) if isinstance(event, dict) and event.get("date")] if isinstance(rectify_events, list) else []
    if not events:
        return []
    birth = _parse_local_moment(f"{payload.get('date') or ''} {payload.get('time') or '00:00:00'}") if payload.get("date") else None
    if birth is None:
        return []

    def lon_of(point_id: str) -> float | None:
        for point in dial_points:
            if point.get("id") == point_id:
                return float(point["lon"])
        return None

    axes = [(name, lon) for name, lon in (("MC", lon_of("MC")), ("Asc", lon_of("Asc"))) if lon is not None]
    base = 90.0
    try:
        orb = float(payload.get("orb"))
    except (TypeError, ValueError):
        orb = 1.0
    if not (math.isfinite(orb) and orb > 0):
        orb = 1.0
    sa_key = "naibod"
    rate = _SOLAR_ARC_RATE[sa_key]
    rows: list[str] = []
    total = 0
    for index, event in enumerate(events):
        label = f"{event['label']}" if event.get("label") and f"{event['label']}".strip() else f"事件{index + 1}"
        when = _parse_local_moment(event.get("date"))
        years = (when - birth).total_seconds() * 1000 / (86400000 * 365.2422) if when is not None else None
        hits: list[tuple[str, str, float]] = []
        arc: float | None = None
        if years is not None:
            arc = years * rate
            for angle_name, angle_lon in axes:
                directed = _dial_norm360(angle_lon + arc)
                for point in dial_points:
                    separation = _dial_sep(directed, point["lon"], base)
                    if separation <= orb:
                        hits.append((point["id"], angle_name, separation))
            hits.sort(key=lambda hit: hit[2])
        total += len(hits)
        hit_text = "，".join(f"{angle}→{_uranian_msg(factor)}·{separation:.2f}°" for factor, angle, separation in hits[:8]) or "无命中"
        date_text = when.strftime("%Y-%m-%d") if when is not None else ""
        arc_text = f"{arc:.2f}" if arc is not None and math.isfinite(arc) else "—"
        type_text = _RECTIFY_TYPE_CN.get(str(event.get("type")), "其他")
        rows.append(f"| {label} | {type_text} | {date_text or '—'} | {arc_text} | {hit_text} |")
    return [
        f"（已录事件推进 MC/Asc 看是否触动本命因子，只预览不改盘；盘基 {_js_template_str(base)}°·容许 {_js_template_str(orb)}°·太阳弧 {_SOLAR_ARC_LABEL.get(sa_key) or 'Naibod'}；1°MC≈4 分钟出生时间）",
        "| 事件 | 类型 | 日期 | 弧° | 命中(轴→本命因子·角距) |",
        "| --- | --- | --- | --- | --- |",
        *rows,
        f"命中合计：{total}",
    ]


def _build_germany_snapshot_text(
    payload: dict[str, Any],
    chart_response: dict[str, Any],
    germany_result: dict[str, Any],
    *,
    rectify_events: Any = None,
) -> str:
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
    # [Q-442/T-405]（上游 AstroMidpoint.js:561-570）：六宫框全表（页签开着即进，不受汉堡门控）与校时预览（有待校事件才进）；
    # 段序紧随 [中点列表]、在 [汉堡学派要素]/[戴维森盘]/[虚星参考] 之前（同 aiExport.js:857 preset）。
    tail_sections: list[tuple[str, str]] = []
    frames_lines = _germany_house_frames_lines(germany_result, dial_points)
    if frames_lines:
        tail_sections.append(("六宫框落宫", "\n".join(frames_lines)))
    rectify_lines = _germany_rectify_lines(payload, rectify_events, dial_points)
    if rectify_lines:
        tail_sections.append(("校时预览", "\n".join(rectify_lines)))
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
            *tail_sections,
        ]
    )


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


def _dice_split_degree(degree: Any) -> tuple[int, int]:
    """DiceMain.js:57 splitDegree：Number(degree) 非数 → [0,0]；负数先 +360；座内度/分向下取整。"""
    try:
        number = float(degree)
    except (TypeError, ValueError):
        return 0, 0
    if number != number:
        return 0, 0
    if number < 0:
        number += 360
    deg = math.floor(number % 30)
    return deg, math.floor(((number % 30) - deg) * 60)


def _dice_chart_object_lines(chart_obj: Any) -> list[str]:
    """DiceMain.js:72 buildChartObjectLines：逐宫星体 GFM 表（[Q-455/T-418] 逆行列：lonspeed<0 标「逆」，无速度字段为 —）。"""
    chart = chart_obj.get("chart") if isinstance(chart_obj, dict) else None
    if not isinstance(chart, dict):
        return []
    houses = chart.get("houses") if isinstance(chart.get("houses"), list) else []
    objects = chart.get("objects") if isinstance(chart.get("objects"), list) else []
    if not houses:
        return []
    lines = ["| 宫位 | 星体 | 度 | 座 | 分 | 逆行 |", "| --- | --- | --- | --- | --- | --- |"]
    for house in houses:
        house_id = house.get("id") if isinstance(house, dict) else None
        in_house = [obj for obj in objects if isinstance(obj, dict) and obj.get("house") == house_id]
        if not in_house:
            lines.append(f"| {_astro_msg_short(house_id)} | 无 | — | — | — | — |")
            continue
        for index, obj in enumerate(in_house):
            deg, minute = _dice_split_degree(obj.get("signlon"))
            speed = obj.get("lonspeed")
            retro = "逆" if isinstance(speed, (int, float)) and not isinstance(speed, bool) and math.isfinite(speed) and speed < 0 else "—"
            lines.append(
                f"| {_astro_msg_short(house_id) if index == 0 else '—'} | {_astro_msg_short(obj.get('id'))} | {deg} | "
                f"{_astro_msg_short(obj.get('sign'))} | {minute} | {retro} |"
            )
    return lines


def _dice_chart_aspect_lines(chart_obj: Any) -> list[str]:
    """DiceMain.js:102 buildChartAspectLines（[Q-455/T-418]）：两盘 normalAsp 四态各成行，无数据 → []（不产段）。

    ⚠ 逐字镜像上游的取数路径 `chartObj.chart.aspects.normalAsp`。后端 /predict/dice 的 diceChart/chart 是
    getChartObj 形（aspects 在 chartObj **顶层**，AstroChartCircle 画相位线读的也是顶层），故真实响应下上游这两段
    恒不产出——本仓照上游口径（条件段双登记），不擅自改路径；详见 tests/test_sync311_chartfamily.py。
    """
    chart = chart_obj.get("chart") if isinstance(chart_obj, dict) else None
    aspects = chart.get("aspects") if isinstance(chart, dict) else None
    normal = aspects.get("normalAsp") if isinstance(aspects, dict) else None
    if not isinstance(normal, dict) or not normal:
        return []
    ids = [obj.get("id") for obj in (chart.get("objects") or []) if isinstance(obj, dict) and normal.get(obj.get("id"))]
    ids.extend(key for key in normal if key not in ids)
    rows: list[str] = []
    for object_id in ids:
        one = normal.get(object_id)
        if not isinstance(one, dict) or not one:
            continue
        subject = _astro_msg_short(object_id)
        # 上游 Exact 与 Separative 同折「离相」（DiceMain.js:113-118；与星盘 [相位] 段的「正合」不同，照抄不统一）。
        for key, state in (("Applicative", "入相"), ("Exact", "离相"), ("Separative", "离相"), ("None", "—")):
            for asp in one.get(key) or []:
                if isinstance(asp, dict):
                    rows.append(
                        f"| {subject} | {_js_template_str(asp.get('asp'))}˚ | {_astro_msg_short(asp.get('id'))} | {state} | {_js_round3(asp.get('orb'))} |"
                    )
    if not rows:
        return []
    return ["| 主体 | 相位 | 对象 | 相态 | 误差 |", "| --- | --- | --- | --- | --- |", *rows]


def _build_otherbu_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    """上游 DiceMain.js:127-170 buildDiceSnapshotText（v3.11：逆行列 / 掷星星池 / 两盘相位段）。"""
    house = response.get("house")
    # [Q-145/T-52] 说清作用域：tradition 只决定**掷出的那颗星**从哪个池里抽；背景盘面恒按完整星集绘制。
    pool = "传统七政 + 交点 / 虚点(不含三王星)" if payload.get("tradition") else "含三王星的完整星集"
    sections: list[tuple[str, str]] = [
        (
            "起盘信息",
            "\n".join(
                [
                    f"日期：{payload.get('date', '—')} {payload.get('time', '—')}",
                    f"时区：{payload.get('zone', '—')}",
                    f"经纬度：{payload.get('lon', '—')} {payload.get('lat', '—')}",
                    f"掷星星池：{pool}(背景盘面仍按完整星集绘制)",
                    f"问题：{payload.get('question') or '未填写'}",
                ]
            ),
        ),
        (
            "骰子结果",
            "\n".join(
                [
                    f"行星：{_astro_msg_short(response.get('planet'))}",
                    f"星座：{_astro_msg_short(response.get('sign'))}",
                    f"宫位：{_astro_msg_short('House' + (_js_template_str(int(house) + 1) if isinstance(house, (int, float)) and not isinstance(house, bool) else ''))}",
                ]
            ),
        ),
        ("骰子盘宫位与星体", "\n".join(_dice_chart_object_lines(response.get("diceChart")))),
        ("天象盘宫位与星体", "\n".join(_dice_chart_object_lines(response.get("chart")))),
    ]
    # 两盘相位段：有相位数据才产段（缺数据时既有输出逐字不变，上游同）。
    dice_aspects = _dice_chart_aspect_lines(response.get("diceChart"))
    if dice_aspects:
        sections.append(("骰子盘相位", "\n".join(dice_aspects)))
    sky_aspects = _dice_chart_aspect_lines(response.get("chart"))
    if sky_aspects:
        sections.append(("天象盘相位", "\n".join(sky_aspects)))
    return _render_snapshot_text(sections)


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


def _ap_name(value: Any) -> str:
    """上游 AstroAgePoint.js:19 apName / AstroDistributions.js:21 distName：空 → '-'，否则 AstroTxtMsg。"""
    if value is None or value == "":
        return "-"
    return _ptext.astro_txt(value)


def _fmt_age(value: Any) -> str:
    """上游 AstroAgePoint.js:37 fmtAge：整数原样，其余 toFixed(2) 去尾零。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return f"{value}"
    if not math.isfinite(number):
        return f"{value}"
    if number == int(number):
        return str(int(number))
    return re.sub(r"\.?0+$", "", _ptext.js_to_fixed(number, 2))


def _agepoint_row_aspects(point: dict[str, Any]) -> list[dict[str, Any]]:
    """上游 AstroAgePoint.js:25 rowAspects：新后端 aspects=[{aspectTo,aspectAge}]；旧字段 aspectTo 兼容回退。"""
    aspects = point.get("aspects")
    if isinstance(aspects, list) and aspects:
        return [a for a in aspects if isinstance(a, dict)]
    if point.get("aspectTo"):
        return [{"aspectTo": point.get("aspectTo"), "aspectAge": point.get("aspectAge")}]
    return []


def _finite_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _agepoint_aspect_text(point: dict[str, Any]) -> str:
    parts = []
    for asp in _agepoint_row_aspects(point):
        age = _finite_number(asp.get("aspectAge"))
        parts.append(f"{_ap_name(asp.get('aspectTo'))}{f'({_fmt_age(age)}岁)' if age is not None else ''}")
    return "、".join(parts)


def _agepoint_sign_text(point: dict[str, Any]) -> str:
    signlon = point.get("signlon")
    return f"{_ap_name(point.get('sign'))}{(' ' + _ptext.js_str(signlon) + '°') if signlon is not None else ''}"


def _build_agepoint_snapshot_text(response: dict[str, Any]) -> str:
    # 逐字镜像上游 components/astro/AstroAgePoint.js:44-100 buildAgePointSnapshotText。
    # [Q-184/T-103]：后端给连续穿越解 crossings（精确岁数）+ 每行 aspects 列表；旧后端无 crossings 时由行拼出。
    ap = response.get("agepoint") if isinstance(response.get("agepoint"), dict) else {}
    points = [p for p in (ap.get("points") if isinstance(ap.get("points"), list) else []) if isinstance(p, dict)]
    if not points:
        # 无年龄推进点数据 = 该技法在本盘缺失（与 star阙 "挂载显示缺失" 一致）。
        return _render_snapshot_text([("年龄推进点（Age Point / Huber）", "（本盘无年龄推进点数据）")])
    crossings = ap.get("crossings") if isinstance(ap.get("crossings"), list) else []
    crossings = [c for c in crossings if isinstance(c, dict)]
    if not crossings:
        for point in points:
            for asp in _agepoint_row_aspects(point):
                age = _finite_number(asp.get("aspectAge"))
                crossings.append({"age": age if age is not None else point.get("age"), "aspectTo": asp.get("aspectTo")})
    lines = ["年龄点自上升点起，沿 Koch 宫顺行，每宫 6 年、72 年回归上升；落于本命星处（合相）为人生关键节点。"]
    if crossings:
        lines.append("")
        lines.append(
            "关键岁数（合本命，精确穿越岁数）："
            + "；".join(f"{_fmt_age(c.get('age'))}岁合{_ap_name(c.get('aspectTo'))}" for c in crossings)
        )
    lines.append("")
    lines.append("| 年龄 | 落座 | 宫 | 合本命（穿越岁数） |")
    lines.append("| --- | --- | --- | --- |")
    for point in points:
        asp = _agepoint_aspect_text(point)
        lines.append(f"| {_ptext.js_str(point.get('age'))}岁 | {_agepoint_sign_text(point)} | {_ptext.js_str(point.get('house'))}宫 | {asp or '—'} |")
    return _render_snapshot_text([("年龄推进点（Age Point / Huber）", "\n".join(lines))])


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


def _agepoint_moment_line(response: dict[str, Any], birth: Any, now: datetime | None = None) -> str:
    """上游 AstroAgePoint.js:81-92：定位行 = age ≤ 当前年龄的最大行（年长 365.2425 天）。"""
    ap = response.get("agepoint") if isinstance(response.get("agepoint"), dict) else {}
    points = [p for p in (ap.get("points") if isinstance(ap.get("points"), list) else []) if isinstance(p, dict)]
    birth_dt = _js_date_parse(birth)
    if birth_dt is None or not points:
        return ""
    cur_age = ((now or datetime.now()) - birth_dt).total_seconds() / (365.2425 * 24 * 3600)
    current = None
    for point in points:
        age = _finite_number(point.get("age"))
        if age is not None and age <= cur_age and (current is None or age > _finite_number(current.get("age"))):
            current = point
    if current is None:
        return ""
    asp = _agepoint_aspect_text(current)
    return (
        f"当前年龄点：{_ptext.js_str(current.get('age'))}岁 落{_agepoint_sign_text(current)}，"
        f"第{_ptext.js_str(current.get('house'))}宫{f'，合本命{asp}' if asp else ''}"
    )


def _distributions_moment_line(response: dict[str, Any], now: datetime | None = None) -> str:
    """上游 AstroDistributions.js:57-67：今日所在分配段（起止可解析且含今日才出）。"""
    rows = response.get("dist") if isinstance(response.get("dist"), list) else []
    moment = now or datetime.now()
    for row in rows:
        if not isinstance(row, dict):
            continue
        start, end = _js_date_parse(row.get("startDate")), _js_date_parse(row.get("endDate"))
        if start is not None and end is not None and start <= moment <= end:
            return (
                f"当前分配星：{_ap_name(row.get('distributor'))}（{_ap_name(row.get('sign'))} 界，"
                f"{row.get('startDate') or '-'} ~ {row.get('endDate') or '-'}）"
            )
    return ""


def _build_distributions_snapshot_text(response: dict[str, Any]) -> str:
    # 逐字镜像上游 components/astro/AstroDistributions.js:27-56 buildDistributionsSnapshotText。
    # [Q-176/T-116a] 界表随全局界系（后端 TermDirection 收 terms_variant），不是写死埃及界。
    rows = response.get("dist") if isinstance(response.get("dist"), list) else []
    if not rows:
        return _render_snapshot_text([("界推运（分配法 / Distributions）", "（本盘无界推运数据）")])
    lines = [
        "上升点经主限运动穿越黄道各界（界表用当前全局界系设置）；分配星=界主星，参与星=该期间内上升点触及的行星。",
        "",
        "| 分配星 | 界(座) | 参与星 | 起 | 止 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        if not isinstance(row, dict):
            continue
        participants = row.get("participants") if isinstance(row.get("participants"), list) else []
        part = "、".join(_ap_name(x) for x in participants) if participants else "—"
        lines.append(
            f"| {_ap_name(row.get('distributor'))} | {_ap_name(row.get('sign'))} | {part} | {row.get('startDate') or '-'} | {row.get('endDate') or '-'} |"
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


def _natal_birth_config_block(response: dict[str, Any], payload: dict[str, Any] | None) -> list[str]:
    """上游 [本命盘配置] 头（jaynes/vedic/planetaryarc 同形）：生辰裸行 + 星与虚点 + 宫位宫头。

    上游 AstroJaynesProgressions.js:59-66 / astroProgSnapshot.js:88-96 / AstroPlanetaryArc.js:62-72：
    `if(natalStars.length || natalHouses.length || natalBirth.length)` 才出段；生辰行在前（[YB v42]）。
    （星与虚点/宫位宫头两子块用本仓共享 line-builder——上游 v3.11 已把它们表化成 GFM 表，属西占公共件口径，
    由盘面族统一切换，这里不私自分叉。）
    """
    natal_wrap = _natal_chart_wrap(response)
    birth = _ptext.build_predictive_birth_lines(_predictive_birth_source(response, payload or {}))
    stars = _build_star_and_lot_position_lines(natal_wrap) if natal_wrap else []
    houses = _build_house_cusp_lines(natal_wrap) if natal_wrap else []
    if not (stars or houses or birth):
        return []
    block = ["[本命盘配置]", *birth]
    if stars:
        block.extend(["星与虚点", *stars])
    if houses:
        block.extend(["宫位宫头", *houses])
    return block


def _prog_parallel_row(p: dict[str, Any]) -> str:
    type_label = "反平行" if p.get("type") == "contraparallel" else "平行"
    return f"| {_ptext.astro_txt(p.get('a'))} | {type_label} | {_ptext.astro_txt(p.get('b'))} | {_ptext.js_fmt_num(p.get('orb'), 3)} |"


def _build_jaynesprog_snapshot_text(
    response: dict[str, Any],
    payload: dict[str, Any] | None = None,
    *,
    target_date: str = "",
    target_time: str = "12:00:00",
    minor_variant: str = _ptext.DEFAULT_MINOR_VARIANT,
) -> str:
    """逐字镜像上游 components/astro/AstroJaynesProgressions.js:33-117 buildJaynesProgSnapshotText。

    [Q-176/T-116b] 首行写「推至所选目标日期」；目标日期行写明目标日期→各法推运时刻的映射；
    [YB v42] 三法（二次/三次/小推运）全量各出 ◆ 小节 + 本命赤纬；[Q-180] 小推运写明月长档。
    """
    methods = [m for m in (response.get("methods") if isinstance(response.get("methods"), list) else []) if isinstance(m, dict)]
    sec = next((m for m in methods if m.get("method") == "secondary"), methods[0] if methods else None)
    parallels = sec.get("parallels") if isinstance(sec, dict) and isinstance(sec.get("parallels"), list) else []
    if not parallels:
        return _render_snapshot_text([("赤纬推运（Declination）", "（本盘无赤纬推运数据）")])
    lines = [
        "[赤纬推运（Declination）]",
        "赤纬推运：推运后看赤纬平行/反平行（下表为二次推运，推至所选目标日期）。",
        f"目标日期：{target_date} {target_time}（各法推运时刻=按该法折算，见各小节）",
    ]
    natal_block = _natal_birth_config_block(response, payload)
    natal_decls = [d for d in (response.get("natalDeclinations") if isinstance(response.get("natalDeclinations"), list) else []) if isinstance(d, dict)]
    if natal_block:
        lines.append("")
        lines.extend(natal_block)
        # [YB v42] UI 赤纬图有本命赤纬列 → ◆ 子题段内纯增（平行/反平行的本命侧参照）。
        if natal_decls:
            lines.extend(["", "◆ 本命赤纬", "| 点 | 赤纬 |", "| --- | --- |"])
            lines.extend(f"| {_ptext.astro_txt(d.get('id'))} | {_ptext.js_fmt_num(d.get('decl'), 2)}° |" for d in natal_decls)
    lines.extend(["", "[时段盘 赤纬平行/反平行]", "| 推运点 | 类型 | 本命点 | 误差 |", "| --- | --- | --- | --- |"])
    lines.extend(_prog_parallel_row(p) for p in parallels[:80] if isinstance(p, dict))

    def push_method_blocks(method: dict[str, Any], with_parallels: bool) -> None:
        label = _ptext.prog_method_tab(method)
        progressed = method.get("progressedDate") if isinstance(method.get("progressedDate"), dict) else {}
        when = progressed.get("datetime") or ""
        decls = [d for d in (method.get("declinations") if isinstance(method.get("declinations"), list) else []) if isinstance(d, dict)]
        if decls:
            lines.extend(["", f"◆ {label} 推运赤纬"])
            if when:
                lines.append(f"推运时刻：{when}")
            if method.get("method") == "minor":
                lines.append(f"月长算法：{_ptext.MINOR_VARIANT_LABEL.get(minor_variant) or minor_variant}")
            lines.extend(["| 点 | 赤纬 |", "| --- | --- |"])
            lines.extend(f"| {_ptext.astro_txt(d.get('id'))} | {_ptext.js_fmt_num(d.get('decl'), 2)}° |" for d in decls)
        rows = [p for p in (method.get("parallels") if isinstance(method.get("parallels"), list) else []) if isinstance(p, dict)]
        if with_parallels and rows:
            lines.extend(["", f"◆ {label} 赤纬平行/反平行", "| 推运点 | 类型 | 本命点 | 误差 |", "| --- | --- | --- | --- |"])
            lines.extend(_prog_parallel_row(p) for p in rows[:80])

    push_method_blocks(sec, False)
    for method in methods:
        if method is not sec:
            push_method_blocks(method, True)
    return "\n".join(lines).strip()


# 上游 components/astro/AstroPlanetaryArc.js:19 ARC_SOURCES（页面/挂载齿轮同值域）。
_ARC_SOURCES = ("Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Sun")


def _planetaryarc_default_datetime(now: datetime | None = None) -> str:
    """上游 AstroPlanetaryArc.js:46 todayStr()：[Q-174/T-114] 缺省目标时刻 = 「明天此刻」（与页面构造期
    dt.addDate(1) 同律；函数名叫 today 但取的是 now+24h）。"""
    return ((now or datetime.now()) + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")


def _build_planetaryarc_snapshot_text(response: dict[str, Any], payload: dict[str, Any] | None = None) -> str:
    """逐字镜像上游 components/astro/AstroPlanetaryArc.js:53-99 formatArcSnapshot。

    段构成：[行星弧（Planetary Arc）]（仅引言）/ [本命盘配置]（生辰 + 星与虚点 + 宫位宫头）/
    [时段盘配置]（向运盘 星与虚点 + 宫位宫头）/ [相位]（| 向运星 | 相位 | 本命星 | 误差 | 表，≤120 行）。
    旧实现把相位表塞在主段、[相位] 段另写「行运X 与 本命Y」句式——两段都与上游不同形。
    """
    chart = response.get("chart") if isinstance(response.get("chart"), dict) else {}
    aspects = chart.get("aspects") if isinstance(chart.get("aspects"), list) else None
    if aspects is None:
        return _render_snapshot_text([("行星弧（Planetary Arc）", "（本盘无行星弧数据）")])
    lines = [
        "[行星弧（Planetary Arc）]",
        "行星弧(默认月亮弧)：以所选天体的二次推运移动量为弧推进全盘，看向运星对本命的相位。",
    ]
    natal_block = _natal_birth_config_block(response, payload)
    if natal_block:
        lines.append("")
        lines.extend(natal_block)
    predictive_wrap = _predictive_chart_wrap(response)
    arc_stars = _build_star_and_lot_position_lines(predictive_wrap)
    arc_houses = _build_house_cusp_lines(predictive_wrap)
    if arc_stars or arc_houses:
        lines.extend(["", "[时段盘配置]"])
        if arc_stars:
            lines.extend(["星与虚点", *arc_stars])
        if arc_houses:
            lines.extend(["宫位宫头", *arc_houses])
    lines.extend(["", "[相位]", "| 向运星 | 相位 | 本命星 | 误差 |", "| --- | --- | --- | --- |"])
    count = 0
    for row in aspects:
        if not isinstance(row, dict):
            continue
        for obj in row.get("objects") or []:
            if count >= 120 or not isinstance(obj, dict):
                continue
            delta = obj.get("delta")
            delta_text = _ptext.js_str(_ptext.js_round(float(delta) * 1000) / 1000) if isinstance(delta, (int, float)) else ""
            lines.append(
                f"| {_ptext.astro_txt(row.get('directId'))} | {_ptext.asp_txt(obj.get('aspect'))} | "
                f"{_ptext.astro_txt(obj.get('natalId'))} | {delta_text} |"
            )
            count += 1
    return "\n".join(lines).strip()


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


# 上游 utils/planetaryAges.js:14-23 YEAR_BAND_ORDER（迦勒底序，土→月）。
_YEAR_BAND_ORDER = ("Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon")


def _full_years_between(birth: Any, when: datetime) -> int | None:
    """上游 moment(now).diff(birth,'years',true) 的整数部分（按月日时逐级比，= 日历周岁）。

    moment 以「生日 + 整月数」为锚，月末钳位：2/29 生人在平年的锚是 2/28（当天即满岁）。
    """
    birth_dt = _persian_birth_date(birth)
    if birth_dt is None:
        return None
    years = when.year - birth_dt.year
    anchor_day = birth_dt.day
    if birth_dt.month == 2 and birth_dt.day == 29 and not (when.year % 4 == 0 and (when.year % 100 != 0 or when.year % 400 == 0)):
        anchor_day = 28
    if (when.month, when.day, when.hour, when.minute, when.second) < (
        birth_dt.month, anchor_day, birth_dt.hour, birth_dt.minute, birth_dt.second
    ):
        years -= 1
    return years


def _build_planetaryages_snapshot_text(
    response: dict[str, Any], as_of: str | None, *, now: datetime | None = None, moment_lines: list[str] | None = None
) -> str:
    """逐字镜像上游 utils/planetaryAges.js:79-127 buildPlanetaryAgesSnapshotText。

    当前年龄缺省按「此刻」（上游 buildPlanetaryAges(chartObj) 无 asOf → moment()；skill 旧实现无 asOf 即不标
    当前带，与本仓 guidance「缺省=今天」矛盾）；asOf 给了则按该日（skill 扩展，同 JS asOf 形参）。
    带边界是整数岁，故 `curAge>=from && curAge<to` 只取决于日历周岁。段尾 ◆ 行星年四档（上游补的 UI 表）；
    定位行「当前主政」进 moment_lines（→ [当前时点]）。
    """
    chart = response.get("chart") if isinstance(response.get("chart"), dict) else {}
    params = response.get("params") if isinstance(response.get("params"), dict) else (chart.get("params") if isinstance(chart.get("params"), dict) else {})
    objects = chart.get("objects") if isinstance(chart.get("objects"), list) else []
    obj_by_id = {o.get("id"): o for o in objects if isinstance(o, dict)}
    reference = _persian_birth_date(as_of) if as_of else None
    if reference is None:
        reference = (now or datetime.now()).replace(microsecond=0)
    cur_age = _full_years_between(params.get("birth"), reference)
    lines = ["托勒密人生七阶：各年龄带由一颗古典行星主管，当前年龄所落之带为主运行星。"]
    if cur_age is not None:
        lines.append(f"当前年龄：约 {cur_age} 岁")
    lines += ["", "| 年龄带 | 主管 | 本命落座 | 当前 |", "| --- | --- | --- | --- |"]
    active_band = None
    for planet, frm, to in _PLANETARY_AGES:
        rng = f"{frm}+岁" if to is None else f"{frm}-{to}岁"
        active = cur_age is not None and cur_age >= frm and (to is None or cur_age < to)
        if active and active_band is None:
            active_band = (planet, rng)
        o = obj_by_id.get(planet)
        pos = "-"
        if isinstance(o, dict) and o.get("sign"):
            signlon = o.get("signlon")
            pos = _ap_name(o.get("sign")) + (f" {math.floor(float(signlon))}°" if signlon is not None else "")
        lines.append(f"| {rng} | {_ap_name(planet)} | {pos} | {'●' if active else ''} |")
    lines += [
        "",
        "◆ 行星年四档（小年/中年/大年/极大年）",
        "七政各有四档通用年数：小年为传统定数（七政小年之和为 129），中年为小年与大年之平均，大年为五星各自所辖界度数之和（日取 120、月取 108），极大年为传统极数。",
    ]
    for planet in _YEAR_BAND_ORDER:
        years = _ptext.PLANETARY_YEARS.get(planet, {})
        lines.append(
            f"{_ap_name(planet)}：小年 {_ptext.js_str(years.get('least', '-'))} · 中年 {_ptext.js_str(years.get('mean', '-'))}"
            f" · 大年 {_ptext.js_str(years.get('greater', '-'))} · 极大年 {_ptext.js_str(years.get('greatest', '-'))}"
        )
    if moment_lines is not None and active_band is not None:
        moment_lines.append(f"当前主政：{_ap_name(active_band[0])}（{active_band[1]}）")
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
        # 上游 AstroYearSystem129.js:26 cn = AstroTxtMsg[id] || id（单字行星名）。
        main_name = _ptext.astro_txt(main.get("mainDirect"))
        if not subs:
            lines.append(f"| {main_name} | - | - |")
            continue
        for sub in subs:
            if not isinstance(sub, dict):
                continue
            lines.append(f"| {main_name} | {_ptext.astro_txt(sub.get('subDirect'))} | {sub.get('date') or '-'} |")
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


# 上游 components/astro/AstroPersianDirected.js:26-29 速率表 + 缺省（波斯速率 + 顺向 + 90 年）。
_PERSIAN_RATE = {"persian": 1.0, "prophected": 30.0, "naibod": 0.9856473}
_PERSIAN_RATE_LABEL = {"persian": "波斯 1°/年", "prophected": "Prophected 30°/年", "naibod": "Naibod 59′08″/年"}
# 上游挂载齿轮（techniqueMountSettings.js:1315-1328）的应期年数五档；builder 本身收任意正数。
_PERSIAN_MAX_YEARS_OPTIONS = (50, 90, 120, 150, 200)
_PERSIAN_YEAR_DAYS = 365.2421904


def _require_option(value: Any, allowed: Any, *, field: str, tool: str) -> None:
    """推运族可选项的值域闸：认不出的值报结构化错误（不静默回落缺省——那会算出另一张盘而不自知）。"""
    if value in allowed:
        return
    raise ToolValidationError(
        f"{tool} 的 {field}={value!r} 不在上游值域内 / {tool}: {field}={value!r} is not a supported value.",
        code="tool.predictive_invalid_option",
        details={"tool": tool, "field": field, "value": value, "allowed": list(allowed)},
    )


def _persian_birth_date(birth: Any) -> datetime | None:
    raw = f"{birth or ''}".strip().replace("/", "-")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _build_persian_hits(chart_obj: dict[str, Any], rate_key: str, max_age: float, direction: str) -> list[dict[str, Any]]:
    """逐字镜像上游 AstroPersianDirected.js:56-98 `buildPersianHits`。

    [Q-168/T-102] 速率 >1°/年（Prophected 30°/年）一生可绕黄道多周：按 arc+360k 逐周取应期至 cap。
    日期 = moment(birth).add(age·365.2421904, 'days')——moment 对小数天**四舍五入到整天**（2.12+ 语义，
    node 实测 add(0.5,'days') 进一天），故这里按 JS Math.round 取整天后加到出生日上，与上游逐日一致。
    """
    chart = chart_obj.get("chart") if isinstance(chart_obj.get("chart"), dict) else {}
    params = chart_obj.get("params") if isinstance(chart_obj.get("params"), dict) else {}
    objects = chart.get("objects") if isinstance(chart.get("objects"), list) else []
    rate = _PERSIAN_RATE.get(rate_key) or 1.0
    cap = max_age or 90
    converse = direction == "converse"
    by_id: dict[str, float] = {}
    for obj in objects:
        if isinstance(obj, dict):
            lon = _persian_lon_of(obj)
            if lon is not None:
                by_id[obj.get("id")] = lon
    targets: list[tuple[str, float]] = list(by_id.items())
    for index, house in enumerate(chart.get("houses") if isinstance(chart.get("houses"), list) else []):
        lon = _persian_lon_of(house) if isinstance(house, dict) else None
        if lon is not None:
            targets.append((f"{index + 1}宫头", lon))
    birth = _persian_birth_date(params.get("birth"))
    hits: list[dict[str, Any]] = []
    for mover in _PERSIAN_MOVERS:
        mover_lon = by_id.get(mover)
        if mover_lon is None:
            continue
        for target_id, target_lon in targets:
            if target_id == mover:
                continue
            for aspect in _PERSIAN_ASPECTS:
                for sign in (1, -1):
                    if aspect in (0, 180) and sign == -1:
                        continue
                    target = (target_lon + sign * aspect) % 360
                    arc = (mover_lon - target) % 360 if converse else (target - mover_lon) % 360
                    for k in range(400):
                        age = (arc + 360 * k) / rate
                        if age > cap:
                            break
                        if age > 0:
                            date = ""
                            if birth is not None:
                                date = (birth + timedelta(days=_ptext.js_round(age * _PERSIAN_YEAR_DAYS))).strftime("%Y-%m-%d")
                            hits.append({
                                "age": _ptext.js_round2(age), "promittor": mover, "aspect": aspect,
                                "significator": target_id, "date": date,
                            })
                        if rate <= 1.0:
                            break
    hits.sort(key=lambda h: h["age"])  # 稳定排序（= V8 Array.prototype.sort）
    return hits


def _persian_directed_age_years(birth: Any, when: Any) -> float | None:
    """上游 AstroPersianDirected.js:161 directedAgeYears：两个墙钟时刻之差（天）/ 365.2421904。"""
    birth_dt = _persian_birth_date(birth)
    when_dt = when if isinstance(when, datetime) else _persian_birth_date(when)
    if birth_dt is None or when_dt is None:
        return None
    return (when_dt - birth_dt).total_seconds() / 86400.0 / _PERSIAN_YEAR_DAYS


def _select_nearby_persian_hits(hits: list[dict[str, Any]], current_age: float | None, limit: int = 12) -> list[dict[str, Any]]:
    """上游 AstroPersianDirected.js:175 selectNearbyPersianHits：按 |age−当前| 取最近 limit 条，再按 age 重排。"""
    if current_age is None or not hits or not math.isfinite(current_age):
        return []
    near = sorted(hits, key=lambda h: abs(h["age"] - current_age))[:limit]
    return sorted(near, key=lambda h: h["age"])


def _persian_hit_row(hit: dict[str, Any]) -> str:
    return (
        f"| {_ptext.js_str(hit['age'])} | {hit['date'] or '-'} | {_ptext.astro_txt(hit['promittor'])} | "
        f"{_ptext.asp_txt(hit['aspect'])} | {_ptext.astro_txt(hit['significator'])} |"
    )


def _build_persiandirected_snapshot_text(
    response: dict[str, Any],
    opts: dict[str, Any] | None = None,
    *,
    now: datetime | None = None,
    moment_lines: list[str] | None = None,
) -> str:
    """逐字镜像上游 AstroPersianDirected.js:103-157 buildPersianDirectedSnapshotText(chartObj, opts)。

    opts：rateKey（persian/prophected/naibod）/ direction（direct/converse）/ maxYears / datetime。
    [Q-168/T-102] 首行按所选速率/方向写（此前写死 1°/年）；主表上限 max(200, maxYears×4)；
    段尾 ◆ 近期命中（距今最近，12 条）。当前向运年龄：给 datetime 按推运时间，否则按导出时刻；
    该定位行写进 moment_lines（由 [当前时点] 段追加，= 上游 extraLines）。
    """
    o = {"rateKey": "persian", "direction": "direct", **(opts or {})}
    rate_key = o.get("rateKey") if o.get("rateKey") in _PERSIAN_RATE else "persian"
    direction = "converse" if o.get("direction") == "converse" else "direct"
    max_years = _finite_number(o.get("maxYears"))
    max_years = max_years if max_years is not None and max_years > 0 else 90
    hits = _build_persian_hits(response, rate_key, max_years, direction)
    if not hits:
        return _render_snapshot_text([("波斯向运（Persian Directed）", "（本盘无波斯向运应期）")])
    lines = [
        f"黄经象征向运({_PERSIAN_RATE_LABEL.get(rate_key) or rate_key})：所有行星/点按此速率"
        f"{'逆向(Converse)' if direction == 'converse' else '顺向'}推进,本命宫头不动；下表为向运星触及本命的应期。",
        "",
        "| 年龄 | 日期 | 向运星 | 相位 | 本命对象 |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend(_persian_hit_row(hit) for hit in hits[: max(200, int(max_years * 4))])
    params = response.get("params") if isinstance(response.get("params"), dict) else {}
    birth = params.get("birth")
    dt_str = f"{o.get('datetime') or ''}".strip()
    current_age = _persian_directed_age_years(birth, dt_str) if dt_str else None
    age_basis = f"按推运时间 {dt_str}"
    if current_age is None:
        # 上游 moment().format('YYYY-MM-DD HH:mm:ss') 截到秒再解析 → 这里同样去掉微秒。
        current_age = _persian_directed_age_years(birth, (now or datetime.now()).replace(microsecond=0))
        age_basis = "按导出时刻"
    near = _select_nearby_persian_hits(hits, current_age, 12)
    if near:
        lines.extend(["", "◆ 近期命中（距今最近）", "| 年龄 | 日期 | 向运星 | 相位 | 本命对象 |", "| --- | --- | --- | --- | --- |"])
        lines.extend(_persian_hit_row(hit) for hit in near)
    if moment_lines is not None and current_age is not None and math.isfinite(current_age):
        moment_lines.append(f"当前向运年龄：{_ptext.js_str(_ptext.js_round2(current_age))} 岁（{age_basis}）")
    return _render_snapshot_text([("波斯向运（Persian Directed）", "\n".join(lines))])


_KP_LORD_CN = {
    # 逐字取 IndiaChartMain.js KP_LORD_CN（罗睺/计都口径与 KP 面板同源）。
    "Sun": "太阳", "Moon": "月亮", "Mars": "火星", "Mercury": "水星", "Jupiter": "木星",
    "Venus": "金星", "Saturn": "土星", "Rahu": "罗睺", "Ketu": "计都",
    "North Node": "罗睺", "South Node": "计都",
}


def _kp_lord_cn(value: Any) -> str:
    text = f"{value or ''}".strip()
    return _KP_LORD_CN.get(text, text or "—")


def _build_india_rectify_snapshot_text(payload: dict[str, Any], res: dict[str, Any]) -> str:
    """[生时校正]（/india/rectify 的文本化）。语汇照上游校时器抽屉（IndiaChartMain.js §17）：
    「校时之靶」「N 采样」「总/RP/PP」「步长诊断…充分/建议步长 ≤Ns」；vara.note 与 disclaimer 原样带回。"""
    info_lines = [
        f"锚点时刻：{res.get('anchorTime') or '—'}（{payload.get('zone') or ''}）",
        f"地点：{payload.get('pos') or ''}　经度 {payload.get('lon')} 纬度 {payload.get('lat')}".rstrip(),
    ]
    criteria = res.get("criteriaActive") or []
    vara = res.get("vara") if isinstance(res.get("vara"), dict) else {}
    diag = res.get("resolution") if isinstance(res.get("resolution"), dict) else {}
    scan_lines = [
        f"扫描半窗：{_round3(res.get('windowMinutes'))} 分　步长：{res.get('stepSeconds')} 秒　候选：{res.get('candidates')} 个",
        f"RP 取法：{res.get('rpSource') or 'anchor'}　参评判据：{' / '.join(str(c) for c in criteria) or '—'}",
        f"日主(vara)：民用日 {_kp_lord_cn(vara.get('civil'))} · 日出日 {_kp_lord_cn(vara.get('sunrise'))}（以 {vara.get('basisUsed') or 'sunrise'} 为准）",
    ]
    if diag:
        adequacy = " · 充分" if diag.get("adequate") else f" · 会整段跳过子主,建议步长 ≤{diag.get('suggestedStepSeconds')}s"
        scan_lines.append(
            f"步长诊断:单步 Lagna 最大位移 {_round3(diag.get('maxLagnaDeltaDeg'))}° / KP 最窄 Sub {_round3(diag.get('narrowestSubDeg'))}°{adequacy}"
        )
    runs = ((res.get("runs") or {}).get("lagnaSubLord")) or []
    run_lines = [f"校时之靶 · {len(runs)} 段"]
    for r in runs:
        if isinstance(r, dict):
            run_lines.append(f"{_kp_lord_cn(r.get('value'))}：{r.get('fromTime')} ~ {r.get('toTime')}（{r.get('count')} 采样）")
    top = res.get("top") or []
    top_lines: list[str] = [f"Top {len(top)} 候选（按判据总分排序）"]
    for i, t in enumerate(top):
        if not isinstance(t, dict):
            continue
        score = t.get("score") if isinstance(t.get("score"), dict) else {}
        rp = t.get("rp") if isinstance(t.get("rp"), dict) else {}
        pp = t.get("pranapada") if isinstance(t.get("pranapada"), dict) else {}
        boundary = t.get("boundary") if isinstance(t.get("boundary"), dict) else {}
        warn_bits = []
        if boundary.get("moonGandanta"):
            warn_bits.append("月亮落界")
        if boundary.get("lagnaGandanta"):
            warn_bits.append("Lagna 落界")
        lords = (
            f"签 {_kp_lord_cn(t.get('lagnaSignLord'))} / 星 {_kp_lord_cn(t.get('lagnaStarLord'))} / "
            f"子主 {_kp_lord_cn(t.get('lagnaSubLord'))}"
        )
        top_lines.append(
            f"{i + 1}. {t.get('time')}（偏移 {t.get('offsetSeconds')}s）　总 {_round3(score.get('total'))}　"
            f"RP {_round3(rp.get('score'))}/{_round3(rp.get('maxScore'))}　PP {pp.get('overall') or '—'}　{lords}"
            + (f"　⚠ {'/'.join(warn_bits)}" if warn_bits else "")
        )
    note_lines = [line for line in (vara.get("note"), res.get("disclaimer")) if line]
    return _render_snapshot_text([
        ("起盘信息", "\n".join(info_lines)),
        ("校时扫描", "\n".join(scan_lines)),
        ("Lagna 子主区段", "\n".join(run_lines)),
        ("候选榜", "\n".join(top_lines)),
        ("声明", "\n".join(note_lines) or "—"),
    ])


def _build_persianchart_section_text(directed: dict[str, Any]) -> str:
    """[指定日期向运盘]（/predict/persianchart，getPersianDirectedByDate 的文本化）。

    directed 形状：{date, rateKey, direction, ageYears, chart:{objects, aspects}, natalChart, lots}。
    aspects 为向运点→本命点命中：[{directId, objects:[{natalId, aspect, delta}]}]。
    """
    if not isinstance(directed, dict) or not isinstance(directed.get("chart"), dict):
        return ""
    chart = directed["chart"]
    lines = [
        f"目标日期：{directed.get('date') or '—'}　速率：{directed.get('rateKey') or 'persian'}　"
        f"方向：{'逆向' if directed.get('direction') == 'converse' else '顺向'}　行进 {_round3(directed.get('ageYears'))} 年",
        "",
        "向运点位：",
    ]
    for obj in chart.get("objects") or []:
        if not isinstance(obj, dict) or obj.get("id") is None:
            continue
        sign = _astro_msg(obj.get("sign"))
        try:
            signlon = float(obj.get("signlon"))
            deg, minute = int(signlon), int(round((signlon - int(signlon)) * 60)) % 60
            pos = f"{sign} {deg}°{minute:02d}′"
        except (TypeError, ValueError):
            pos = sign or "—"
        lines.append(f"{_astro_msg(obj.get('id'))}：{pos}")
    aspect_rows: list[str] = []
    for row in chart.get("aspects") or []:
        if not isinstance(row, dict):
            continue
        direct_name = _astro_msg(row.get("directId"))
        for hit in row.get("objects") or []:
            if not isinstance(hit, dict):
                continue
            aspect_rows.append(
                f"向运{direct_name} {_aspect_label(hit.get('aspect'))} 本命{_astro_msg(hit.get('natalId'))}"
                f"（差 {_round3(hit.get('delta'))}°）"
            )
    if aspect_rows:
        lines.extend(["", "向运→本命相位命中："])
        lines.extend(aspect_rows)
    lots = directed.get("lots")
    if isinstance(lots, list) and lots:
        lines.append(f"（另有 directed 阿拉伯点 {len(lots)} 枚，见 directed_chart.lots）")
    return _render_snapshot_text([("指定日期向运盘", "\n".join(lines))])


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


# 跨技法通用的已知顶层键：dispatch/hecan 把整份出生资料（BirthInput 族全字段）原样灌给每个技法，
# 它们不是「写错的神数旋钮」→ 不回执 params_ignored（否则每次合参都刷一屏噪声警告）。
_SHENSHU_GENERIC_KEYS: frozenset[str] = frozenset(
    set(BirthInput.model_fields)
    | set(ZiWeiBirthInput.model_fields)
    | set(BaZiBirthInput.model_fields)
    | set(LiuRengGodsInput.model_fields)
    | set(NongliTimeInput.model_fields)
    | {"request", "save_result", "response_view", "question", "name", "pos", "ad"}
)


# 写在 options 里也照收的核心键（它们是请求体的一级字段，不是技法旋钮；见 _run_shenshu_tool）。
_SHENSHU_PROMOTABLE_OPTION_KEYS = frozenset(
    {"gender", "zone", "lat", "lon", "gpsLat", "gpsLon", "pos", "after23NewDay", "lateZiHourUseNextDay"}
)


def _upstream_cast_time_seed(parts: dict[str, int]) -> int:
    """上游无头起课种子（TaiXuanMain.js:141-152 / JingJueMain.js:105-117 同式）：

    (年·月·日)·时·分 拼成 yyyyMMddHHmm 再 mod 1e9；BC 年把年位平移 |年|+5（同数 BC/AD 必异种子，
    AD 逐位不变）。同一起课时刻反复挂载得同一卦——「以时起卦」语义。
    """
    year = int(parts["year"])
    year_part = year if year >= 0 else abs(year) + 5
    stamp = ((year_part * 10000 + parts["month"] * 100 + parts["day"]) * 10000) + parts["hour"] * 100 + parts["minute"]
    return stamp % 1_000_000_000


# 五兆计算键缺省（上游 WuZhaoMain DEFAULT_OPTIONS :109-121 + DEFAULT_SPLITS/QIAN_THROWS/ZHAO_NUMS :87-89）。
# 上游页面与挂载都**全量**下发这 11 键（buildPanPayload / normalizeCalcOptions），缺哪键后端就回落
# 它自己的缺省——以钱代筮关自动掷而不带六掷时后端会逐掷走 RNG（webwuzhaosrv._qian_shifa），所以必须全发。
_WUZHAO_CALC_DEFAULTS: dict[str, Any] = {
    "mode": "ganzhi", "number": 0, "manual": False, "manualSplits": [18, 8, 5, 2, 1, 1],
    "shifaVariant": "guayi", "qianThrows": [2, 2, 2, 2, 2, 2], "qianAuto": True,
    "zhaoNums": [3, 3, 3, 3, 3, 3], "xingshenMonth": "lunar", "mingZhi": "", "gender": "",
}
_WUZHAO_MODE_LABELS = {
    "ganzhi": "干支起盘", "day": "日干起盘", "hour": "时干起盘", "minute": "分干起盘",
    "tang": "唐代正法揲筮", "dunhuang": "敦煌校录揲筮", "qian": "以钱代筮", "zhushu": "直输五兆数",
}


def _append_replay_note(text: str, section_title: str, note: str) -> str:
    """上游 WuZhaoMain.appendReplayNote（:360-366）逐字移植：复现说明并入既有段，不新增段头。"""
    blocks = f"{text or ''}".split("\n\n")
    for index, block in enumerate(blocks):
        if block.startswith(f"[{section_title}]"):
            blocks[index] = f"{block}\n复现说明：{note}"
            return "\n\n".join(blocks)
    return f"{text}\n复现说明：{note}"


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


# 皇极经世·心易发微（kinwangji/xinyi.py:42-72 只收**繁体**卦名/方位，简体直送即 ValueError → 500）。
_WANGJI_XINYI_METHODS = ("none", "datetime", "number", "character", "direction")
_WANGJI_TRIGRAMS = ("乾", "兌", "離", "震", "巽", "坎", "艮", "坤")
_WANGJI_TRIGRAM_ALIASES = {"兑": "兌", "离": "離"}
_WANGJI_DIRECTIONS = ("北", "西南", "東", "東南", "南", "中", "西北", "西", "東北")
_WANGJI_DIRECTION_ALIASES = {"东": "東", "东南": "東南", "东北": "東北"}


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
_GEO_TRAD = {"european_classical": "古典定局派", "european_planetary": "行星共鸣派", "european_modern": "现代综合派(同古典口径)", "arabic_raml": "阿拉伯沙占派", "india_ramal": "印度骰占派", "sikidy": "异或表盘", "hakata": "四片盘", "greek": "希腊传本", "ifa": "西非同族结构对照"}
_GEO_PERF = {"occupation": "入主成局", "conjunction": "会合成局", "mutation": "互变成局", "translation": "传递成局", "none": "未成局"}
_GEO_ASP = {"conjunction": "合", "sextile": "六分(吉)", "square": "刑(凶)", "trine": "拱(吉)", "opposition": "冲", "none": "无相位"}
_GEO_SLOT = ["母一", "母二", "母三", "母四", "女一", "女二", "女三", "女四", "甥一", "甥二", "甥三", "甥四", "右证", "左证", "判官", "调和"]
# 传本粒度设置注记（仅注记与主流缺省不同者）；镜像 GeomancyMain GNAME。
_GEO_GNAME = {
    "house_projection": {"sequential": "落星=不落(仅图形入宫)", "astro_from_chart": "落星=占星甲(星落所主图之宫)", "astro_bytwelves": "落星=占星乙(另起点数定宫)"},
    "compound_mode": {"reverse": "合成同伴=逆转法"},
    "number_system": {"planetary": "图数=行星序", "abjad": "图数=字母值"},
    "reconciler_mode": {"judge_querent_significator": "调和者=判官⊕问者指示星"},
    "mark_style": {"lines": "记号=线形", "bindu": "记号=点线", "tablets": "记号=开合片"},
    "direction": {"RTL": "书写=自右向左"},
}
_GEO_PARITY_SCOPE = {"shield16": "全盘十六图", "mothers": "四母", "houses12": "十二宫"}
_GEO_PZH = {"Sun": "日", "Moon": "月", "Mercury": "水", "Venus": "金", "Mars": "火", "Jupiter": "木", "Saturn": "土", "NorthNode": "龙头", "SouthNode": "龙尾"}
_GEO_TRI = {1: "火", 5: "火", 9: "火", 2: "地", 6: "地", 10: "地", 3: "风", 7: "风", 11: "风", 4: "水", 8: "水", 12: "水"}
# ifa（西非同族）为结构对照模式：不产地占判读。skill 暴露的 8 家占断传本白名单（明确排除 ifa）。
_GEOMANCY_PROFILES = ("european_classical", "european_planetary", "european_modern", "arabic_raml", "india_ramal", "sikidy", "hakata", "greek")
# 传本粒度覆盖 passthrough 白名单（未传即不发 → 内核回落 profile 默认，旧盘字节零变）。键名 = webgeomancysrv.reading
# 的 `_opt/_optb(...)` 读键（:443-465）；sync311 F12 补 housePlacement / 行星地占盘四键（castNumbers 另行处理）。
_GEOMANCY_OPTION_KEYS = (
    "markStyle", "direction", "houseProjection", "wrapHouses", "reconciler", "reconcilerMode", "haltEnabled",
    "compoundMode", "numberSystem", "chartMode", "houseSystem", "ascSource", "namesSystem", "parityScope",
    "housePlacement", "planetaryChart", "planetaryChartZodiac", "planetaryChartNodes", "planetaryChartExtras",
)
# 问类 = 后端 _QTYPES 十一类（webgeomancysrv.py:42-46）；其它值后端静默改回 custom（:379-381）→ 这里显式拒。
# 值 = 问类预设所问宫：上游 GeomancyMain.QUESTION_TYPE_HOUSE（:204-208，注「与引擎 question_house 表同源」，
# 即内核 data/house_meanings.json question_house）；两边逐值对拍见 tests/test_sync311_divination_w3.py。
_GEOMANCY_QUESTION_HOUSE = {
    "custom": 1, "life": 1, "health": 6, "wealth": 2, "marriage": 7, "career": 10, "children": 5, "journey": 9,
    "religion": 9, "enemy": 7, "death": 8,
}
_GEOMANCY_QUESTION_TYPES = tuple(_GEOMANCY_QUESTION_HOUSE)


def _geomancy_time_seed(parts: dict[str, int]) -> int:
    """上游 GeomancyMain.computeTimeSeed（:229-246）：(YY)MMDDHHmm 折进 int32 正区间（mod 2^31−1）。"""
    value = (parts["year"] % 100) * 100000000 + parts["month"] * 1000000 + parts["day"] * 10000 + parts["hour"] * 100 + parts["minute"]
    return value % 2147483647


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
    # 结构对照模式（ifa）防御性早退：skill schema 已挡 ifa，此分支仅为稳健 + 供 export_parse 识别面。
    if reading.get("structuralOnly") or reading.get("structural_only"):
        notice = reading.get("culturalNotice") or reading.get("note") or "独立圣传体系，仅结构同构对照，不套地占含义、不构成占断。"
        body = [notice]
        ifa = reading.get("ifa") if isinstance(reading.get("ifa"), dict) else {}
        if ifa.get("label"):
            right = ifa.get("right") or {}
            left = ifa.get("left") or {}
            body.append(
                f"结构对照：{ifa['label']}{'(主形)' if ifa.get('is_meji') else ''}；"
                f"右列 {right.get('odu_name') or '—'}→{right.get('figure') or '—'}、"
                f"左列 {left.get('odu_name') or '—'}→{left.get('figure') or '—'}（自右向左读）"
            )
        body.append("※ 本模式只作形的识别与比特对照，不产出该体系之占断，亦不套用地占含义。")
        return _render_snapshot_text([("边界声明", "\n".join(body).strip())])

    # [起卦信息]：问题/问类/上升 + 传本设置（仅注记非默认口径）。
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
    gs = reading.get("settings") if isinstance(reading.get("settings"), dict) else {}
    for gkey, gtable in _GEO_GNAME.items():
        hit = gtable.get(gs.get(gkey))
        if hit:
            tb.append(hit)
    if gs.get("wrap_houses") is True:
        tb.append("宫位成环")
    if gs.get("reconciler") is False:
        tb.append("不取调和者")
    if gs.get("halt_enabled") is False:
        tb.append("不启用首母中止")
    if tb:
        info.append(f"传本设置：{'、'.join(tb)}")

    # [判定]：首母中止 + 判官/调和者/证 + 主宫 + sikidy/hakata 中栏结论。
    judge: list[str] = []
    if reading.get("haltedOnFirstMother"):
        judge.append("⚠ 首母中止：首母落 Rubeus/Cauda 之属，依所选传本传统应中止本占、另择时再占（以下判读仅作参考）。")
    for fig, role in ((reading.get("judge"), "判官"), (reading.get("reconciler"), "调和者"), (reading.get("rightWitness"), "右证(过去/问者)"), (reading.get("leftWitness"), "左证(现在/所问)")):
        ln = _geo_figure_line(fig, role)
        if ln:
            judge.append(ln)
    if reading.get("primaryHouse"):
        judge.append(f"主宫：第 {reading['primaryHouse']} 宫")
    sk = reading.get("sikidy")
    if isinstance(sk, dict):
        princes = sk.get("princes") if isinstance(sk.get("princes"), list) else []
        judge.append(
            f"异或表盘：三道校验{'通过' if sk.get('valid') else '未过'}"
            f"{'；红 Sikidy(大凶)' if sk.get('red_sikidy') else ''}"
            f"{('；诸侯列:' + '、'.join(str(p) for p in princes)) if princes else ''}"
        )
        compare = sk.get("compare") if isinstance(sk.get("compare"), dict) else None
        columns = sk.get("columns") if isinstance(sk.get("columns"), dict) else None
        if compare and columns:
            hits = [f"第{k}列 {(columns.get(k) or {}).get('name') or ''}（{(columns.get(k) or {}).get('meaning') or ''}）"
                    for k in compare if compare.get(k) and compare[k].get("equal")]
            judge.append(f"列比对：问者列与{('、'.join(hits) + ' 同形 —— 事之所系在此') if hits else '各主题列皆不同形，无直指之应'}")
    hk = reading.get("hakata")
    if isinstance(hk, dict):
        tablets = hk.get("tablets") if isinstance(hk.get("tablets"), list) else []
        tb_str = " ".join(f"{t.get('name') or ''}{'开' if t.get('open') else '合'}" for t in tablets if isinstance(t, dict))
        judge.append(
            f"四片盘：{tb_str or '—'} → {hk.get('figure_zh') or hk.get('figure') or '—'}"
            f"{('；' + hk['reading']) if hk.get('reading') else ''}"
            f"{('；' + hk['orientation']) if hk.get('orientation') else ''}"
        )

    # [解读技法]（条件）+ 判官之数折入。
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
            scope = _GEO_PARITY_SCOPE.get(pp.get("scope"), "全盘十六图")
            degen = "，该取样结构恒偶、不具判别力" if pp.get("degenerate") else ""
            tech.append(f"点数是否：总 {pp.get('total')} 点·{'偶→是/稳' if pp.get('parity') == 'even' else '奇→否/动'}（取样 {scope}{degen}）")
        tm = t.get("timing")
        if isinstance(tm, dict):
            tech.append(f"应期：{'速' if tm.get('speed') == 'fast' else '迟'}·以「{tm.get('unit')}」计")
        vp = t.get("via_puncti")
        if isinstance(vp, dict):
            tech.append(f"点之路：{'贯通' if vp.get('through') else '断于' + str(vp.get('broken_at'))}")
        if t.get("natural_cosignificator"):
            tech.append("自然共主：月亮")
        tri = t.get("triplicities") if isinstance(t.get("triplicities"), list) else []
        if len(tri) > 1:
            tech.append(f"黄道宫三方：宫 {'/'.join(str(x) for x in tri)}（{_GEO_TRI.get(tri[0], '')}三方）")
        if isinstance(tm, dict) and isinstance(tm.get("quantity"), dict):
            q = tm["quantity"]
            tech.append(f"数量：{q.get('label')}(总 {q.get('total')} 点·域 {q.get('min')}–{q.get('max')})")
    jn = (reading.get("judge") or {}).get("number") if isinstance(reading.get("judge"), dict) else None
    if isinstance(jn, dict) and jn.get("system") != "points":
        tech.append(f"判官之数：{jn.get('value')}（{jn.get('basis') or jn.get('system')}）")

    # [转宫派生]（条件）
    derived_lines: list[str] = []
    d = reading.get("derived")
    if isinstance(d, dict):
        derived_lines.append(f"以第 {d.get('turn_to')} 宫为新命宫：新命宫 {d.get('derived_querent_house')} → 所问宫 {d.get('derived_quesited_house')}")
        derived_lines.append(f"派生完美：{_GEO_PERF.get(d.get('perfection'), d.get('perfection'))}{('；派生阻碍在第 ' + str(d['prohibition']) + ' 宫') if d.get('prohibition') else ''}")
        df = d.get("figure")
        if isinstance(df, dict):
            derived_lines.append(f"派生宫图：{df.get('nameZh') or df.get('nameEn') or '—'}")

    # [定局落星·甲/乙]（条件）
    placement_a: list[str] = []
    ppA = reading.get("planetPlacement") if isinstance(reading.get("planetPlacement"), dict) else {}
    ppA_keys = [k for k in ppA if (ppA.get(k) or [])]
    if ppA_keys:
        placement_a.append("；".join(f"{_GEO_PZH.get(k, k)}→{'/'.join(f'{h}宫' for h in ppA[k])}" for k in ppA_keys))
        absent = [_GEO_PZH.get(k, k) for k in ppA if not (ppA.get(k) or [])]
        if absent:
            placement_a.append(f"（缺席：{'、'.join(absent)} —— 星所主之图未入盘，乃本法固有，非算漏）")
    placement_b: list[str] = []
    ppB = reading.get("planetPlacementByTwelves")
    if isinstance(ppB, dict) and ppB:
        placement_b.append("；".join(f"{_GEO_PZH.get(k, k)}→{ppB[k]}宫" for k in ppB))

    # [十二宫·图形入宫] markdown 表（印度派多支名/曜两列）
    houses = reading.get("houses") if isinstance(reading.get("houses"), list) else []
    house_body = ""
    if houses:
        is_india = reading.get("profileId") == "india_ramal"
        rows = (["| 宫 | 宫名 | 支名 | 角色 | 图形 | 曜 | 断语 |", "| --- | --- | --- | --- | --- | --- | --- |"]
                if is_india else ["| 宫 | 宫名 | 角色 | 图形 | 断语 |", "| --- | --- | --- | --- | --- |"])
        for h in houses:
            if not isinstance(h, dict):
                continue
            fig = h.get("figure") or {}
            roles = h.get("roles") or []
            role = "【所问】" if "quesited" in roles else ("【问者】" if "querent" in roles else "—")
            if is_india:
                bh = f"{h['bhava']}（{h.get('bhavaZh') or ''}）" if h.get("bhava") else "—"
                gr = ((fig.get("vedic") or {}).get("graha_zh")) or "—"
                rows.append(f"| 第{h.get('house')}宫 | {h.get('nameZh') or '—'} | {bh} | {role} | {fig.get('nameZh') or fig.get('nameEn') or '—'} | {gr} | {h.get('reading') or '—'} |")
            else:
                rows.append(f"| 第{h.get('house')}宫 | {h.get('nameZh') or '—'} | {role} | {fig.get('nameZh') or fig.get('nameEn') or '—'} | {h.get('reading') or '—'} |")
        house_body = "\n".join(rows)

    # [十六图形] markdown 表
    figs = reading.get("figures16") if isinstance(reading.get("figures16"), list) else []
    fig_body = ""
    if figs:
        rows = ["| 位 | 图形 | 行星 | 元素 |", "| --- | --- | --- | --- |"]
        for i, f in enumerate(figs):
            if not isinstance(f, dict):
                continue
            slot = _GEO_SLOT[i] if i < len(_GEO_SLOT) else f"图{i + 1}"
            rows.append(f"| {slot} | {f.get('nameZh') or f.get('nameEn')} | {f.get('planetZh') or '—'} | {f.get('elementZh') or '—'} |")
        fig_body = "\n".join(rows)

    # [图形释义] doctrine 段：上游默认关段，skill 不产出（仅在 preset 保留作 export_parse 识别面）。
    sections: list[tuple[str, str]] = [("起卦信息", "\n".join(info).strip())]
    if judge:
        sections.append(("判定", "\n".join(judge).strip()))
    if tech:
        sections.append(("解读技法", "\n".join(tech).strip()))
    if derived_lines:
        sections.append(("转宫派生", "\n".join(derived_lines).strip()))
    if placement_a:
        sections.append(("定局落星·甲", "\n".join(placement_a).strip()))
    if placement_b:
        sections.append(("定局落星·乙", "\n".join(placement_b).strip()))
    if house_body:
        sections.append(("十二宫·图形入宫", house_body))
    if fig_body:
        sections.append(("十六图形", fig_body))
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


# 玄史条目的展示键序（存在才渲染；覆盖 事件/天象/人物/朝代/术数/名词/故事 各族的常见字段）。
_XUANSHI_FIELD_ORDER: tuple[tuple[str, str], ...] = (
    ("title", "标题"), ("name", "名称"), ("event_id", "编号"), ("slug", "slug"), ("id", "编号"),
    ("tradition", "传统"), ("dynasty", "朝代"), ("period", "时期"), ("year", "公历年"),
    ("history", "史书"), ("volume_no", "卷次"), ("citation", "引证"),
    ("region", "地域"), ("operators", "施术者"), ("targets", "对象"), ("techniques", "术数"),
    ("omen", "天象类"), ("source", "出处"), ("trigger", "起因"), ("procedure", "过程"),
    ("outcome", "结局"), ("evidence", "证据"), ("original_text", "原文"), ("modern_text", "白话"),
    ("reading", "解读"), ("reliability_note", "可信度"), ("cross_ref", "互见"),
    ("summary", "摘要"), ("text", "正文"), ("desc", "说明"), ("note", "注"),
)


def _xuanshi_record_lines(rec: dict[str, Any], *, brief: bool) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for key, label in _XUANSHI_FIELD_ORDER:
        if key in seen:
            continue
        value = rec.get(key)
        if value is None or value == "" or value == []:
            continue
        seen.add(key)
        if isinstance(value, list):
            value = "、".join(f"{v}" for v in value[:12])
        text = f"{value}"
        if brief and len(text) > 120:
            text = text[:120] + "…"
        lines.append(f"{label}：{text}")
        if brief and len(lines) >= 4:
            break
    return lines


def _build_xuanshi_snapshot_text(action: str, body: dict[str, Any], response: Any) -> str:
    cond = [f"action：{action}"] + [f"{k}：{v}" for k, v in body.items()]
    sections: list[tuple[str, str]] = [("检索条件", _join_lines(cond))]
    # 列表族：裸数组，或 {items|list|events|figures…: [...], total: n} 包装；详情族：单 dict 条目。
    items: list[Any] | None = None
    total: Any = None
    detail: dict[str, Any] | None = None
    if isinstance(response, list):
        items = response
    elif isinstance(response, dict):
        for key in ("items", "list", "events", "figures", "records", "results", "rows", "points", "nodes", "stories"):
            if isinstance(response.get(key), list):
                items = response[key]
                total = response.get("total")
                break
        if items is None:
            # summary/timeline/facets 一类结构响应：作总览渲染；带 title/event_id 的当详情。
            if any(k in response for k in ("title", "event_id", "original_text", "name")):
                detail = response
            else:
                overview = _stringify_export_body(response)
                if overview.strip():
                    sections.append(("结果总览", overview.strip()[:4000]))
    if items is not None:
        head = f"命中 {total if total is not None else len(items)} 条（列出 {min(len(items), 20)} 条）"
        sections.append(("结果总览", head))
        rows: list[str] = []
        for i, rec in enumerate(items[:20], 1):
            if isinstance(rec, dict):
                brief = "；".join(_xuanshi_record_lines(rec, brief=True)) or _stringify_export_body(rec)[:120]
            else:
                brief = f"{rec}"
            rows.append(f"{i}. {brief}")
        if rows:
            sections.append(("条目列表", _join_lines(rows)))
    if detail is not None:
        lines = _xuanshi_record_lines(detail, brief=False)
        if lines:
            sections.append(("条目详情", _join_lines(lines)))
        related = detail.get("related") or detail.get("same_dyn") or detail.get("same_hist")
        if isinstance(related, list) and related:
            rel = ["、".join(f"{(r.get('title') or r.get('event_id') or r)}" if isinstance(r, dict) else f"{r}" for r in related[:8])]
            sections.append(("相关条目", _join_lines(rel)))
    # 出处引证聚合（列表与详情通吃）
    cites: list[str] = []
    pool = (items or [])[:20] + ([detail] if detail else [])
    for rec in pool:
        if isinstance(rec, dict) and rec.get("citation"):
            c = f"{rec['citation']}"
            if c not in cites:
                cites.append(c)
    if cites:
        sections.append(("出处引证", _join_lines(cites[:20])))
    return _render_snapshot_text(sections)


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
    # [Q-255/T-238·AS-22⑪]（上游 AstroRelative.js:151-159）：出人话标签（此前直出数字「宫制：1」「黄道：0」），
    # 与主命盘快照同源表：宫制 = HouseSys 选项标签；黄道 = zodiacalDisplayText（恒星黄道带岁差名）。
    hsys_raw = payload.get("hsys")
    zodiacal_raw = payload.get("zodiacal")
    zodiacal_key = {"0": "Tropical", "1": "Sidereal"}.get(_js_template_str(zodiacal_raw)) if zodiacal_raw is not None else None
    hsys_text = (HOUSE_SYSTEM_LABELS.get(_js_template_str(hsys_raw)) or hsys_raw) if hsys_raw is not None else "—"
    if zodiacal_raw is None:
        zodiacal_text: Any = "—"
    elif zodiacal_key:
        zodiacal_text = zodiacal_display_text(zodiacal_key, payload.get("siderealAyanamsa") or "")
    else:
        zodiacal_text = zodiacal_raw
    lines.append(f"宫制：{hsys_text}")
    lines.append(f"黄道：{zodiacal_text}")

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

    # 段名按盘型（payload.relative）分：上游 AstroRelative.js:164-181 —— 组合盘/影响盘保持原段名，
    # 时空中点盘(relative=3)与马克斯盘(relative=4)用独立段名，否则设置面无法分开勾选、导出文本也
    # 不辨盘型。本仓此前无条件用普通名，两个变体的段因此恒缺。
    _rel_mode = f"{payload.get('relative', 0)}"
    _composite_title = "时空中点·合成图盘" if _rel_mode == "3" else "合成图盘"
    _inner_title = "马克斯·影响图盘-星盘A" if _rel_mode == "4" else "影响图盘-星盘A"
    _outer_title = "马克斯·影响图盘-星盘B" if _rel_mode == "4" else "影响图盘-星盘B"
    rendered: list[tuple[str, str]] = [("关系起盘信息", _join_lines(lines[1:]))]
    for title, body_lines in sections:
        rendered.append((title, _join_lines(body_lines) or _missing_detail_text(title)))
    # [Q-441/T-404]（上游 AstroRelative.js:168-181）：比较盘页签此前只出互摄相位/中点/映点，无 A/B 两盘盘体 →
    # 响应自带 inner(=A)/outer(=B) 两盘，仿影响盘**无头**嵌整盘（buildAstroSnapshotContent headerless，
    # 喂工作台宫制数字位 {hsys}）。段名独立（比较盘-星盘A/B），只在比较盘（relative=0）出。
    if _rel_mode == "0":
        comp_fields = {"hsys": payload.get("hsys")} if payload.get("hsys") is not None else {}
        for comp_title, comp_key in (("比较盘-星盘A", "inner"), ("比较盘-星盘B", "outer")):
            comp_chart = response.get(comp_key)
            if isinstance(comp_chart, dict) and isinstance(comp_chart.get("chart"), dict):
                rendered.append((comp_title, _headerless_astro_snapshot_text(comp_fields, comp_chart)))
    rendered.append(
        (
            _composite_title,
            embedded_chart_text(response)
            if isinstance(response.get("chart"), dict) and isinstance(response["chart"].get("objects"), list)
            else "无",
        )
    )
    # 影响盘 A/B 只属影响盘/马克斯盘（relative=2/4，上游 AstroRelative.js:194-205 的页签门控）——比较盘的
    # inner/outer 此前被错贴成「影响图盘-星盘A/B」，现归上面的 比较盘-星盘A/B。
    _synastry_mode = _rel_mode in {"2", "4"}
    rendered.append(
        (
            _inner_title,
            embedded_chart_text(response["inner"])
            if _synastry_mode and isinstance(response.get("inner"), dict) and isinstance(response["inner"].get("chart"), dict)
            else _missing_detail_text(_inner_title),
        )
    )
    rendered.append(
        (
            _outer_title,
            embedded_chart_text(response["outer"])
            if _synastry_mode and isinstance(response.get("outer"), dict) and isinstance(response["outer"].get("chart"), dict)
            else _missing_detail_text(_outer_title),
        )
    )
    # 关系量化（v3.3.1）：契合分数 + 顺畅/张力连接，源 AstroRelative.js Score 页三段。
    score = response.get("_relativeScore") if isinstance(response.get("_relativeScore"), dict) else None
    if score and score.get("score") is not None:
        rendered.append((
            "关系量化",
            f"契合分数：{score.get('score')}（0–100，50 为中性；越高越顺畅，越低张力越大）",
        ))

        def _score_asp_lines(items: Any) -> str:
            rows: list[str] = []
            for it in (items or [])[:12]:
                if not isinstance(it, dict):
                    continue
                rows.append(
                    f"{_astro_msg(it.get('a'), short=True)} 与 {_astro_msg(it.get('b'), short=True)} 成 "
                    f"{_aspect_label(it.get('aspect'))} 相位（权重{_round3(it.get('impact'))}，误差{_round3(it.get('orb'))}）"
                )
            return "\n".join(rows)

        highlights = _score_asp_lines(score.get("highlights"))
        if highlights:
            rendered.append(("顺畅连接", highlights))
        challenges = _score_asp_lines(score.get("challenges"))
        if challenges:
            rendered.append(("张力连接", challenges))
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


def _derived_position_lines(positions: Any, label: str) -> list[str]:
    """派生盘位置行——镜像 AuxLab：`{id}：本命黄经 X° → {label} {sign}{signlon}°`。"""
    out: list[str] = []
    for row in positions if isinstance(positions, list) else []:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        natal = f"{float(row['natalLon']):.2f}" if row.get("natalLon") is not None else "—"
        signlon = f"{float(row['signlon']):.2f}°" if row.get("signlon") is not None else ""
        out.append(f"{row['id']}：本命黄经 {natal}° → {label} {row.get('sign') or ''}{signlon}")
    return out


def _derived_conjunction_lines(conjunctions: Any) -> list[str]:
    out: list[str] = []
    for c in conjunctions if isinstance(conjunctions, list) else []:
        if isinstance(c, dict) and c.get("a") and c.get("b"):
            orb = f"{float(c['orb']):.3f}" if c.get("orb") is not None else "—"
            out.append(f"同频：{c['a']} 合 {c['b']}（误差 {orb}）")
    return out


def _chart_angles(chart_shaped: Any) -> dict[str, dict[str, Any]]:
    """四角（Asc/MC/Desc/IC）——镜像 AstroRelocationLab.anglesOf：读 chart.objects 按 id 过滤。"""
    chart = chart_shaped.get("chart") if isinstance(chart_shaped, dict) else None
    objects = chart.get("objects") if isinstance(chart, dict) else None
    out: dict[str, dict[str, Any]] = {}
    for obj in objects if isinstance(objects, list) else []:
        if isinstance(obj, dict) and obj.get("id") in ("Asc", "MC", "Desc", "IC"):
            out[obj["id"]] = obj
    return out


def _angle_text(obj: dict[str, Any] | None) -> str:
    if not isinstance(obj, dict):
        return "—"
    signlon = f"{float(obj['signlon']):.2f}°" if obj.get("signlon") is not None else ""
    return f"{obj.get('sign') or ''}{signlon}" or "—"



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
        # [Q-193/T-139]（上游 v3.11.0 ZiWeiMain.js:419-420）「未知」在紫微是按男排（Java 缺省 gender=true，
        # 引擎 male = gender !== 0）：只写「未知」会与命局阴阳自相矛盾。
        f"性别：{_gender_label(payload.get('gender'), unknown='未知（按男排）')}",
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

    # [来因宫]：与生年天干同干的宫。v3.9.2 起口径收紧为 isLaiyinPalace 单源
    # （ziweiSchools.js:127-131：首字 == 年干 **且** 地支非子非丑——子丑是借干宫，排除），
    # 排版 `宫名（干支）`、顿号连接。纯查表，响应里 chart.yearGan 与 houses[].ganzi 都现成。
    year_gan = f"{chart.get('yearGan') or ''}".strip() if isinstance(chart, dict) else ""
    laiyin_lines: list[str] = []
    if year_gan and isinstance(houses, list):
        hits = [
            f"{h.get('name') or ''}（{h.get('ganzi')}）"
            for h in houses
            if isinstance(h, dict)
            and f"{h.get('ganzi') or ''}".startswith(year_gan)
            and f"{h.get('ganzi') or ''}"[1:2] not in ("子", "丑")
        ]
        if hits:
            laiyin_lines.append("、".join(hits))

    # [身宫]（v3.9.2）：判据钉死引擎输出 house.isBody（本地/后端两引擎皆保证；bodyHouseIndex 仅本地
    # 引擎有故禁走旁路——上游 ZiWeiMain.js:477 原话）。找不到整段不产（best-effort，与来因宫同范式）。
    body_lines: list[str] = []
    if isinstance(houses, list):
        body_house = next((h for h in houses if isinstance(h, dict) and h.get("isBody")), None)
        if body_house and body_house.get("name"):
            ganzi = body_house.get("ganzi")
            body_lines.append(f"身宫落{body_house['name']}{f'（{ganzi}）' if ganzi else ''}")

    # [八字大运]（v3.9.2）：盘心十列（起运虚岁+大运干支+起始年）。数据与盘心/info 面板同源
    # chart.bazi.direct.direction，缺省（本地引擎无 direct）整段不产。GFM 表镜像 ZiWeiMain.js:498-508。
    bz_dayun_lines: list[str] = []
    bazi_node = chart.get("bazi") if isinstance(chart, dict) else None
    direct = bazi_node.get("direct") if isinstance(bazi_node, dict) else None
    direction = direct.get("direction") if isinstance(direct, dict) else None
    if isinstance(direction, list) and direction:
        rows = []
        for item in direction:
            if not isinstance(item, dict):
                continue
            main_direct = item.get("mainDirect") if isinstance(item.get("mainDirect"), dict) else {}
            gz = main_direct.get("ganzi")
            if not gz:
                continue
            rows.append(f"| {(item.get('age') or 0) + 1} | {item.get('startYear') or '无'} | {gz} |")
        if rows:
            bz_dayun_lines = ["| 起运虚岁 | 起始年份 | 大运干支 |", "| --- | --- | --- |", *rows]

    # 段序逐字镜像上游 v56 preset：起盘信息, 宫位总览, 身宫, 来因宫, 八字大运, 命中格局, (运限, 流派叠层)。
    blocks = [
        ("起盘信息", _join_lines(lines)),
        ("宫位总览", _join_lines(overview) or "无"),
    ]
    if body_lines:
        blocks.append(("身宫", _join_lines(body_lines)))
    if laiyin_lines:
        blocks.append(("来因宫", _join_lines(laiyin_lines)))
    if bz_dayun_lines:
        blocks.append(("八字大运", _join_lines(bz_dayun_lines)))
    blocks.append(("命中格局", _join_lines(pattern_lines) or "无"))
    text = _render_snapshot_text(blocks)
    # [运限] / [流派叠层]：由 vendored builder 出（自带段头），仅在调用方给了 period / schools 时产。
    extras = response.get("_ziweiExtras")
    if isinstance(extras, str) and extras.strip():
        text = f"{text}\n\n{extras.strip()}"
    return text


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


def _normalize_ganzi(text: Any) -> str:
    """JieQiChartsMain.js:349 normalizeGanZi：取前两字。"""
    raw = f"{text or ''}".strip()
    return raw[:2] if len(raw) >= 2 else raw


def _simple_four_columns(nongli: Any) -> dict[str, dict[str, str]] | None:
    """JieQiChartsMain.js:354 toSimpleFourColumns：农历字段 → 四柱 ganzi（无纳音）。"""
    if not isinstance(nongli, dict) or not nongli:
        return None
    return {
        "year": {"ganzi": _normalize_ganzi(nongli.get("yearGanZi") or nongli.get("yearJieqi") or nongli.get("year")), "naying": ""},
        "month": {"ganzi": _normalize_ganzi(nongli.get("monthGanZi")), "naying": ""},
        "day": {"ganzi": _normalize_ganzi(nongli.get("dayGanZi")), "naying": ""},
        "time": {"ganzi": _normalize_ganzi(nongli.get("time") or nongli.get("timeGanZi")), "naying": ""},
    }


def _jieqi_four_columns(item: Any) -> dict[str, Any] | None:
    """JieQiChartsMain.js:378 getJieqiFourColumns：bazi.fourColumns → fourColumns → bazi(农历形) → nongli。"""
    if not isinstance(item, dict):
        return None
    bazi = item.get("bazi")
    if isinstance(bazi, dict) and bazi.get("fourColumns"):
        return bazi["fourColumns"]
    if item.get("fourColumns"):
        return item["fourColumns"]
    if bazi:
        from_bazi = _simple_four_columns(bazi)
        if from_bazi:
            return from_bazi
    if item.get("nongli"):
        return _simple_four_columns(item["nongli"])
    return None


def _compact_jieqi_seed_row(item: dict[str, Any]) -> dict[str, Any]:
    """JieQiChartsMain.js:420 compactJieqiSeedResult 的逐行形状：四柱只留 ganzi/naying（Java 四柱对象带神煞/卦等，体量大）。"""
    four = _jieqi_four_columns(item)

    def part(value: Any) -> dict[str, str]:
        src = value if isinstance(value, dict) else {}
        return {"ganzi": f"{src.get('ganzi') or ''}", "naying": f"{src.get('naying') or ''}"}

    return {
        "ord": item.get("ord"),
        "jieqi": f"{item.get('jieqi') or ''}",
        "jie": item.get("jie"),
        "time": f"{item.get('time') or ''}",
        "ad": item.get("ad"),
        "bazi": {"fourColumns": {key: part(four.get(key)) for key in ("year", "month", "day", "time")}} if isinstance(four, dict) else None,
    }


def _build_jieqi24_table_lines(rows: Any) -> list[str]:
    """[二十四节气]（上游 JieQiChartsMain.js:893-906 [Q-224/T-180]）：交节时刻 + 四柱，与页面「二十四节气」页签同源。"""
    if not isinstance(rows, list) or not rows:
        return []
    out = ["| 节气 | 交节时刻 | 年柱 | 月柱 | 日柱 | 时柱 |", "| --- | --- | --- | --- | --- | --- |"]
    for item in rows:
        item = item if isinstance(item, dict) else {}
        four = _jieqi_four_columns(item) or {}

        def gz(key: str) -> str:
            column = four.get(key) if isinstance(four, dict) else None
            return f"{column.get('ganzi')}" if isinstance(column, dict) and column.get("ganzi") else ""

        out.append(f"| {item.get('jieqi') or ''} | {item.get('time') or ''} | {gz('year')} | {gz('month')} | {gz('day')} | {gz('time')} |")
    return out


def _build_jieqi_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    """上游 JieQiChartsMain.js:880-933 buildJieQiSnapshotText（整年快照）。

    [节气盘参数] → [二十四节气]（全年交节时刻+四柱；种子行由 `_attach_jieqi_year_extras` 取自 Java /jieqi/year）
    → 未拉取分至盘的说明行 → 逐节气 [X星盘]（buildAstroSnapshotContent 全口径无头整盘，Q-446/T-409）/ [X宿盘] /
    [X3D盘]（与 [X星盘] 同一盘数据的三维视图 → 一行指引，不整盘重复）。
    """
    charts = response.get("charts") if isinstance(response, dict) else {}
    charts = charts if isinstance(charts, dict) else {}
    jieqis = payload.get("jieqis") or ["春分", "夏至", "秋分", "冬至"]
    meta_lines = [
        f"年份：{payload.get('year', '—')}",
        f"时区：{payload.get('zone', '—')}",
        f"经纬度：{payload.get('lon', '—')} {payload.get('lat', '—')}",
        "说明：以下包含二分二至（春分、夏至、秋分、冬至）的星盘与宿盘专用导出。",
    ]
    sections: list[tuple[str, list[str]]] = [("节气盘参数", meta_lines)]
    rows24 = _build_jieqi24_table_lines(response.get("_jieqi24Seed") if isinstance(response, dict) else None)
    if rows24:
        sections.append(("二十四节气", rows24))
    # [Q-224/T-180] 分至盘未拉到时明示未纳入（上游句式逐字；行落在当时的末段——有 [二十四节气] 则随它，否则随参数段）。
    missing = [title for title in jieqis if not charts.get(title)]
    if missing:
        sections[-1][1].append(f"说明：{'、'.join(missing)}的星盘 / 宿盘尚未拉取（打开对应页签后再导出即纳入）。")
    rendered: list[tuple[str, str]] = [(title, _join_lines(lines)) for title, lines in sections]
    for title in jieqis:
        one = charts.get(title)
        if not isinstance(one, dict):
            continue
        fields = one.get("params") if isinstance(one.get("params"), dict) else payload
        chart_body = (
            (_headerless_astro_snapshot_text(fields, one) if _is_astro_chart_payload(one) else "")
            or _build_jieqi_compact_chart_text(fields, one)
            or "无数据"
        )
        rendered.append((f"{title}星盘", chart_body))
        rendered.append((f"{title}宿盘", _build_jieqi_compact_suzhan_text(fields, one) or "无数据"))
        rendered.append((f"{title}3D盘", f"3D 盘为「{title}星盘」同一节气盘的三维视图(星位/宫位/相位同上 [{title}星盘] 段,无独立数据)。"))
    return _render_snapshot_text(rendered)


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


_CALENDAR_WEEK_CN = {0: "星期日", 1: "星期一", 2: "星期二", 3: "星期三", 4: "星期四", 5: "星期五", 6: "星期六"}


def _build_calendar_month_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    """黄历/万年历快照：起盘信息 / 当月月历(GFM 表) / 选中日详情(可选) / 方法说明。

    月历行只收与 days[0] 同月的项（days 可能带下月补位）；字段均后端真值直引，不重算。
    """
    days = response.get("days") if isinstance(response.get("days"), list) else []
    prev_days = response.get("prevDays") if isinstance(response.get("prevDays"), list) else []

    def month_of(d: dict[str, Any]) -> str:
        return str(d.get("birth") or "")[:7]

    def day_of(d: dict[str, Any]) -> str:
        return str(d.get("birth") or "")[5:10]

    query_month = str(payload.get("date") or "")[:7] or (month_of(days[0]) if days else "")
    info_lines: list[str] = []
    if query_month:
        info_lines.append(f"查询月份：{query_month}")
    if payload.get("zone"):
        info_lines.append(f"时区：{payload.get('zone')}")
    if payload.get("lon"):
        info_lines.append(f"历算经度：{payload.get('lon')}")

    sections: list[tuple[str, str]] = [("起盘信息", _join_lines(info_lines))]

    table_lines: list[str] = []
    if days:
        cur_month = month_of(days[0])
        rows = [d for d in days if isinstance(d, dict) and month_of(d) == cur_month]
        if rows:
            table_lines.append("| 公历 | 星期 | 农历 | 日干支 | 节气/朔望 |")
            table_lines.append("| --- | --- | --- | --- | --- |")
            for d in rows:
                nl = str(d.get("day") or "")
                if d.get("dayInt") == 1:
                    nl = f"{'闰' if d.get('leap') else ''}{d.get('month') or ''}{d.get('day') or ''}"
                notes: list[str] = []
                if d.get("jieqi"):
                    notes.append(f"{d.get('jieqi')} {d.get('jieqiTime') or ''}".strip())
                if d.get("moonTime"):
                    mt = "朔" if d.get("dayInt") == 1 else ("望" if d.get("dayInt") == 15 else "月相")
                    notes.append(f"{mt} {d.get('moonTime')}".strip())
                week = _CALENDAR_WEEK_CN.get(d.get("dayOfWeek"), "")
                table_lines.append(f"| {day_of(d)} | {week} | {nl} | {d.get('dayGanZi') or ''} | {'；'.join(notes)} |")
    sections.append(("当月月历", _join_lines(table_lines) or "无"))

    # 选中日详情：payload.day 指定公历日，从当月/补位项中按 birth 前缀匹配。
    selected_day = str(payload.get("day") or "").strip()
    if selected_day:
        sel = next(
            (d for d in [*days, *prev_days] if isinstance(d, dict) and str(d.get("birth") or "").startswith(selected_day)),
            None,
        )
        detail_lines: list[str] = []
        if sel:
            week = _CALENDAR_WEEK_CN.get(sel.get("dayOfWeek"), "")
            detail_lines.append(f"公历：{str(sel.get('birth') or '').split(' ')[0]} {week}".strip())
            sel_month = f"{'闰' if sel.get('leap') else ''}{sel.get('month') or ''}"
            detail_lines.append(f"农历：{sel.get('year') or ''}年{sel_month}{sel.get('day') or ''}")
            if sel.get("yearNaying"):
                detail_lines.append(f"年纳音：{sel.get('yearNaying')}")
            detail_lines.append(
                f"干支：{sel.get('yearJieqi') or ''}年 {sel.get('monthGanZi') or ''}月 {sel.get('dayGanZi') or ''}日 {sel.get('time') or ''}时"
            )
            jiehou = [v for v in (sel.get("jiedelta"), sel.get("chef")) if v]
            if jiehou:
                detail_lines.append(f"节候：{'，'.join(jiehou)}")
            if sel.get("jieqi"):
                jdn_note = f"（jdn {sel.get('jieqiJdn')}）" if sel.get("jieqiJdn") else ""
                detail_lines.append(f"节气：{sel.get('jieqi')} {sel.get('jieqiTime') or ''}{jdn_note}")
            if sel.get("moonTime"):
                mt = "朔月" if sel.get("dayInt") == 1 else ("望月" if sel.get("dayInt") == 15 else "月相")
                jdn_note = f"（jdn {sel.get('moonJdn')}）" if sel.get("moonJdn") else ""
                detail_lines.append(f"{mt}：{sel.get('date') or ''} {sel.get('moonTime') or ''}{jdn_note}")
            if sel.get("qimengYearGua"):
                detail_lines.append(f"奇门年卦：{sel.get('qimengYearGua')}")
        sections.append(("选中日详情", _join_lines(detail_lines) or f"未在返回月历中找到 {selected_day}"))

    sections.append(
        (
            "方法说明",
            _join_lines(
                [
                    "月干支：以当天正午12点是否已跨节气决定归属月。",
                    "年柱口径：干支年以节气（立春）为界；农历年月日以朔望月与置闰为准，两者并列显示。",
                    "节气/朔望时刻为该历算经度下的真时刻；jdn 为对应儒略日数。",
                ]
            ),
        )
    )
    text = _render_snapshot_text(sections)
    # 子模块段块（老黄历 8 段 / 通书择日 / 日子馆 2 段）按上游段序插在 [选中日详情] 与 [方法说明] 之间。
    # 文本已由 vendored builder 带好各自的 `[段名]` 段头，故不进 sections 列表（那会被再包一层段头），
    # 而是在渲染完成后按 [方法说明] 的位置整块拼进去。
    #
    # v3.9.2 [E-6] 聚合导出**子源标签**：整行 `【农历】/【老黄历】/【通书择日】/【日子馆】` 是来源分界
    # 而非内容段（上游 CALENDAR_SUB_SOURCE_LABELS + extractCalendarContent：每个子模块文本前冠一行标签，
    # 经 parseSectionTitleLine 归一为段名）。skill 同形：农历标签置顶（NongLi 主 tab 内容之前）；
    # 老黄历/通书择日/日子馆标签由 calendar_extras 的分块边界插入。标签必须进 preset，
    # 否则用户自定义段时标签行会被过滤删掉、同名段无法分辨来源（上游原话）。
    text = f"【农历】\n{text}"
    extras = response.get("_calendarExtras")
    if isinstance(extras, str) and extras.strip():
        block = extras.strip()
        # 老黄历块以 [今日宜忌] 起、通书块以 [通书择日] 起、日子馆块以 [日子馆·个性化择日] 起——
        # 在各自块首插入子源标签行（缺块则该标签自然不出，与上游「未挂载子 tab 被跳过」同形）。
        for marker, label in (
            ("[今日宜忌]", "【老黄历】"),
            ("[通书择日]", "【通书择日】"),
            ("[日子馆·个性化择日]", "【日子馆】"),
        ):
            at = block.find(marker)
            if at >= 0:
                block = f"{block[:at]}{label}\n{block[at:]}"
        marker = "[方法说明]"
        at = text.find(marker)
        if at >= 0:
            text = f"{text[:at]}{block}\n\n{text[at:]}"
        else:
            text = f"{text}\n\n{block}"
    return text


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


def _natal_config_lines(chart_wrap: dict[str, Any]) -> list[str]:
    """[本命盘配置]（内圈）：星与虚点 + 宫位宫头 两个子块（上游 AstroPrimaryDirectionChart.js:351-358）。"""
    lines: list[str] = []
    stars = _build_star_and_lot_position_lines(chart_wrap)
    if stars:
        lines.extend(["星与虚点", *stars])
    cusps = _build_house_cusp_lines(chart_wrap)
    if cusps:
        lines.extend(["宫位宫头", *cusps])
    return lines


def _directed_config_lines(chart_wrap: dict[str, Any]) -> list[str]:
    """[主限法盘配置]（外圈/时段盘）：同上两子块，取推导后的盘（上游 :359-366）。"""
    return _natal_config_lines(chart_wrap)


def _build_predictive_cross_aspect_lines(
    response: dict[str, Any],
    predictive_wrap: dict[str, Any] | None = None,
    natal_wrap: dict[str, Any] | None = None,
) -> list[str]:
    """推运盘 ↔ 本命盘的交叉相位（上游 predictiveAiSnapshot.js::buildAspectLines 同款）。

    这**不是**本命盘那种 {normalAsp, immediateAsp, signAsp} 结构：`/predict/*` 把交叉相位放在
    `response["chart"]["aspects"]` 的**数组**里，每项形如
    `{directId, objects:[{natalId, aspect, delta}]}`（后端 perpredict.getAspects 产出）。
    此前这段错走 `_build_aspect_section`（读本命盘形状、且只认顶层 aspects）→ 真机上整段只输出
    「标准相位/立即相位/星座相位」三个空子标题、一条相位都没有。离线测试没抓到，是因为
    FakeClient 在顶层塞了本命形状的 aspects——桩与真实响应形状不一致，把 bug 盖住了。
    """
    chart = response.get("chart") if isinstance(response.get("chart"), dict) else {}
    aspects = chart.get("aspects")
    if not isinstance(aspects, list):
        return []
    lines: list[str] = []
    for item in aspects:
        if not isinstance(item, dict):
            continue
        direct_id = item.get("directId") or item.get("id")
        # 上游 appendPlanetHouseInfoById：推运星的宫位取推运盘、本命星的宫位取本命盘（两张盘各查各的）。
        direct_label = _astro_msg_with_house(direct_id, predictive_wrap or {}, short=True)
        for target in item.get("objects") or []:
            if not isinstance(target, dict):
                continue
            natal_label = _astro_msg_with_house(target.get("natalId") or target.get("id"), natal_wrap or {}, short=True)
            # 上游 predictiveAiSnapshot.js:199：AstroTxtMsg['Asp'+aspect] || aspect+'º'（º=U+00BA，非 ˚）。
            aspect = _ptext.js_str(target.get("aspect"))
            asp = _ptext.UPSTREAM_ASTRO_TXT_MSG.get(f"Asp{aspect}") or f"{aspect}º"
            lines.append(
                f"行运{direct_label} 与 本命{natal_label}"
                f" 成 {asp} 相位，误差{_round3(target.get('delta'))}"
            )
    return lines


# 上游 components/astro/AstroPrimaryDirectionChart.js:39-55 / 188-260：主限法盘缺省时刻 = 主限表首条（按方法/界限法
# 过滤后）的「日期」列（UTC 墙钟，PD_DISPLAY_ZONE '+00:00'）；无行则出生次日（同一墙钟改挂 +00:00）。
_PD_DISPLAY_ZONE = "+00:00"
_PD_CORE_SUPPORTED_BASE_IDS = frozenset({
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
    "North Node", "Pars Fortuna", "Asc", "MC",
})


def _pd_base_object_id(text: Any) -> str:
    """AstroPrimaryDirectionChart.js:205 baseDirectionObjectId。"""
    raw = f"{text or ''}"
    parts = raw.split("_")
    if len(parts) < 3:
        if len(parts) == 2 and parts[0] in ("A", "C"):
            return parts[1]
        return raw.strip()
    if parts[0] == "T":
        return parts[1].strip()
    return "_".join(parts[1:-1]).strip()


def _pd_is_bound_row(row: list[Any]) -> bool:
    return f"{row[1] if len(row) > 1 else ''}".startswith("T_") or f"{row[2] if len(row) > 2 else ''}".startswith("T_")


def _pd_is_antiscia_row(row: list[Any]) -> bool:
    prom = f"{row[1] if len(row) > 1 else ''}"
    sig = f"{row[2] if len(row) > 2 else ''}"
    return prom.startswith(("A_", "C_")) or sig.startswith(("A_", "C_"))


def _pd_display_rows(rows: Any, pd_method: str, show_pd_bounds: Any) -> list[list[Any]]:
    """AstroPrimaryDirectionChart.js:235 buildDisplayRows（只取过滤后的原始行）。"""
    hide_bounds = show_pd_bounds in (0, False)
    is_core = pd_method == "core_alchabitius"
    out: list[list[Any]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, list) or not row:
            continue
        if is_core and (
            _pd_is_bound_row(row)
            or _pd_base_object_id(row[1] if len(row) > 1 else "") not in _PD_CORE_SUPPORTED_BASE_IDS
            or _pd_base_object_id(row[2] if len(row) > 2 else "") not in _PD_CORE_SUPPORTED_BASE_IDS
        ):
            continue
        if hide_bounds and _pd_is_bound_row(row):
            continue
        if is_core and _pd_is_antiscia_row(row):
            continue
        out.append(row)
    return out


def _upstream_now_wall_clock() -> datetime:
    """上游 `new DateTime()` 的「此刻」：[Q-141] 缺省钟面 = 真实此刻换算到 +08:00（DateTime 缺省时区）。"""
    return datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)


# 上游 predictiveAiSnapshot.js:106-139 pickInfoBlocks 的块标题白名单（[本命盘配置]「信息」子块）。
_PREDICTIVE_INFO_BLOCK_TITLES = ("映点/反映点", "接纳", "互容", "光线围攻", "夹宫", "夹星", "纬照")


def _pick_info_blocks(lines: list[str], titles: tuple[str, ...]) -> list[str]:
    """上游 predictiveAiSnapshot.js:120 pickInfoBlocks：自首个命中标题起收全部非空行（互容→互融）。"""
    out: list[str] = []
    in_block = False
    for line in lines:
        text = f"{line or ''}".strip()
        if not text:
            continue
        if text in titles:
            in_block = True
            out.append(text.replace("互容", "互融"))
            continue
        if in_block:
            out.append(text.replace("互容", "互融"))
    return out


def _predictive_star_info_lines(natal_wrap: dict[str, Any]) -> list[str]:
    """上游 predictiveAiSnapshot.js:51-104 buildStarInfoLines(natalChartObj)。"""
    params = natal_wrap.get("params") if isinstance(natal_wrap.get("params"), dict) else {}
    chart = natal_wrap.get("chart") if isinstance(natal_wrap.get("chart"), dict) else {}
    lines: list[str] = []
    lon, lat = params.get("lon"), params.get("lat")
    if lon or lat:
        lon_lat = f"{lon or ''} {lat or ''}".strip()
        lines.append(f"经纬度：{lon_lat}")
    if params.get("zone") is not None:
        lines.append(f"时区：{params.get('zone')}")
    zodiacal_raw = chart.get("zodiacal") or _ptext.ZODIACAL.get(_ptext.js_str(params.get("zodiacal")))
    if zodiacal_raw:
        ayan_key = params.get("siderealAyanamsa") or chart.get("siderealAyanamsa") or ""
        lines.append(f"黄道：{_ptext.zodiacal_display_text(zodiacal_raw, ayan_key)}")
    hsys = _ptext.HOUSE_SYS_LABELS.get(_ptext.js_str(params.get("hsys"))) or chart.get("hsys")
    if hsys:
        lines.append(f"宫制：{hsys}")
    if chart.get("isDiurnal") is not None:
        lines.append(f"盘型：{'日生盘' if chart.get('isDiurnal') else '夜生盘'}")
    lines.append(PLANET_HOUSE_INFO_NOTE)
    house_lines = _build_house_cusp_lines(natal_wrap)
    if house_lines:
        lines.extend(["宫位宫头", *house_lines])
    star_lines = _build_star_and_lot_position_lines(natal_wrap)
    if star_lines:
        lines.extend(["星与虚点", *star_lines])
    info_only = _pick_info_blocks(_build_info_section(natal_wrap, {}), _PREDICTIVE_INFO_BLOCK_TITLES)
    if info_only:
        lines.extend(["信息", *info_only])
    return lines


def _predictive_setup_lines(params: dict[str, Any]) -> list[str]:
    """上游 predictiveAiSnapshot.js:143-176 buildSetupLines(params)（[起盘信息] = 推运时点口径）。"""
    lines: list[str] = []
    if params.get("datetime"):
        lines.append(f"推运时间：{params['datetime']}")
    if params.get("dirZone") is not None:
        lines.append(f"推运时区：{params['dirZone']}")
    lon = params.get("dirLon") or params.get("lon")
    lat = params.get("dirLat") or params.get("lat")
    if lon or lat:
        lon_lat = f"{lon or ''} {lat or ''}".strip()
        lines.append(f"推运经纬度：{lon_lat}")
    if params.get("tmType"):
        lines.append(f"时间步进：{params['tmType']}")
    if params.get("asporb") is not None:
        lines.append(f"相位容许度：{_ptext.js_str(params['asporb'])}")
    if params.get("nodeRetrograde") is not None:
        lines.append(f"月交点逆行：{'是' if params['nodeRetrograde'] else '否'}")
    # 恒星黄道时标注具体 ayanāṃśa（仅恒星盘追加此行 → 回归盘输出逐字不变）。
    if _ptext.js_str(params.get("zodiacal")) == "1":
        lines.append(f"黄道：{_ptext.zodiacal_display_text(params.get('zodiacal'), params.get('siderealAyanamsa'))}")
    return lines


# 目标时刻型 5 法（上游 aiAnalysisContext.js:2673-2760 buildPredictivePeriodSnapshot）。
_PERIOD_PREDICTIVE_TOOLS = ("profection", "solararc", "solarreturn", "lunarreturn", "givenyear")
_RETURN_PREDICTIVE_TOOLS = ("solarreturn", "lunarreturn", "givenyear")


def _predictive_text_params(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """buildPredictivePeriodSnapshot 的请求体（= [起盘信息] 的文字源）：tmType 恒 'y'、asporb 缺省 1、
    nodeRetrograde 缺省 false、dirZone 缺省本命时区；returns 型另带 dirLat/dirLon（缺省本命经纬）。"""
    params: dict[str, Any] = {
        "date": payload.get("date"),
        "time": payload.get("time"),
        "zone": payload.get("zone"),
        "lon": payload.get("lon"),
        "lat": payload.get("lat"),
        "datetime": payload.get("datetime"),
        "dirZone": payload.get("dirZone") or payload.get("zone"),
        "tmType": "y",
        "asporb": payload.get("asporb") if payload.get("asporb") is not None else 1,
        "nodeRetrograde": bool(payload.get("nodeRetrograde")),
        "zodiacal": payload.get("zodiacal"),
        "siderealAyanamsa": payload.get("siderealAyanamsa"),
    }
    if tool_name in _RETURN_PREDICTIVE_TOOLS:
        params["dirLat"] = payload.get("dirLat") or payload.get("lat")
        params["dirLon"] = payload.get("dirLon") or payload.get("lon")
    return params


def _build_predictive_snapshot_text(tool_name: str, payload: dict[str, Any], response: dict[str, Any]) -> str:
    """逐字镜像上游 utils/predictiveAiSnapshot.js:225-287 buildPredictiveSnapshotText(natal, params, result, key)。

    段：[本命盘配置]（生辰裸行 + buildStarInfoLines）/ [起盘信息]（buildSetupLines 推运时点口径）/
    [小限摘要]（仅 profection，[Q-105]）/ [时段盘配置] / [相位]；[方法说明] 由统一出口追加（这 5 键上游
    preset 无 [当前时点]）。旧实现的 [起盘信息]「技法/目标时间/后台实际成盘时间/推运地点」是自拟文案。
    """
    natal_wrap = _natal_chart_wrap(response)
    predictive_wrap = _predictive_chart_wrap(response)
    params = _predictive_text_params(tool_name, payload)
    birth_lines = _ptext.build_predictive_birth_lines(_predictive_birth_source(response, payload))
    star_lines = _predictive_star_info_lines(natal_wrap) if natal_wrap else []
    natal_config = [*birth_lines, *star_lines]
    sections: list[tuple[str, str]] = [
        ("本命盘配置", _join_lines(natal_config) or "无"),
        ("起盘信息", _join_lines(_predictive_setup_lines(params)) or "无"),
    ]
    if tool_name == "profection":
        # [Q-105 裁决 2026-09-18] 年/月/日小限摘要（粒度 profGrain、起点 profStart；缺省 年/上升）。
        summary = _ptext.build_profection_summary_lines(
            natal_wrap, params, payload.get("profGrain"), payload.get("profStart")
        )
        sections.append(("小限摘要", _join_lines(summary) or "无"))
    directed_lines: list[str] = []
    directed_stars = _build_star_and_lot_position_lines(predictive_wrap)
    if directed_stars:
        directed_lines.extend(["时段盘 星与虚点", *directed_stars])
    directed_cusps = _build_house_cusp_lines(predictive_wrap)
    if directed_cusps:
        directed_lines.extend(["时段盘 宫位宫头", *directed_cusps])
    sections.append(("时段盘配置", _join_lines(directed_lines) or "无"))
    sections.append(
        (
            "相位",
            _join_lines(_build_predictive_cross_aspect_lines(response, _top_level_chart_wrap(response), natal_wrap))
            or _join_lines(_build_aspect_section(predictive_wrap))
            or "无",
        )
    )
    return _render_snapshot_text(sections)


# 上游 utils/primaryDirectionSync.js:57-62 SUPPORTED_PD_METHODS（13 法，= 后端 perchart.py:892 白名单）+ :73-87 PD_METHOD_LABELS。
_PD_METHOD_LABELS: dict[str, str] = {
    "core_alchabitius": "Alchabitius",
    "placidus": "Placidus（半弧）",
    "regiomontanus": "Regiomontanus",
    "campanus": "Campanus",
    "topocentric": "Topocentric",
    "meridian": "Meridian",
    "porphyry": "Porphyry",
    "equal_ecliptic": "Equal（黄道）",
    "equal_hour_circle": "Equal（时圈）",
    "morinus": "Morinus",
    "in_zodiaco_lon": "Along Ecliptic",
    "in_zodiaco_abs": "Edmund Jones",
    "horosa_legacy": "Horosa原方法",
}
# 上游 primaryDirectionSync.js:64-70 SUPPORTED_PD_TIME_KEYS（26 项）+ :88-115 PD_TIME_KEY_LABELS。
_PD_TIME_KEY_LABELS: dict[str, str] = {
    "Ptolemy": "Ptolemy",
    "Naibod": "Naibod",
    "TrueSolarArc": "真太阳弧",
    "SymbolicSolarArc": "太阳弧（黄经）",
    "Kundig": "Kündig",
    "Cardano": "Cardano",
    "Umar": "Umar al-Tabari",
    "Wollner": "Wöllner",
    "Plantiko": "Plantiko",
    "Simmonite": "Simmonite",
    "SynodicYear": "Synodic Year",
    "Kepler": "Kepler",
    "Brahe": "Brahe",
    "SymbolicDegree": "Symbolic Degree",
    "SymbolicYear": "Symbolic Year",
    "SymbolicMoon": "Symbolic Moon",
    "SymbolicMonth": "Symbolic Month",
    "Quarterly": "Quarterly",
    "Quinary": "Quinary",
    "Duodenary": "Duodenary",
    "Novenary": "Novenary",
    "SelfMeasure": "Self-Measure",
    "NaibodRA": "Naibod-in-RA",
    "AscendantArc": "Ascendant-arc（界行）",
    "VanDam": "Van Dam（真弧）",
    "User": "自定义（每年度数）",
}


def _primary_direction_method_text(value: Any) -> str:
    """上游 primaryDirectionSync.js:170 getPdMethodLabel：已知 → 标签；缺省/未知 → 缺省法标签（后端
    perchart.py:892 同样把白名单外一律回退 core_alchabitius，标签与实算一致）。F20：旧实现只认「核5」，
    把 placidus/regiomontanus 等 v3.6 起已真算的方位法写成「未核验，引擎回退 Alcabitius」——对实算结果撒谎。"""
    return _PD_METHOD_LABELS.get(_msg(value)) or _PD_METHOD_LABELS["core_alchabitius"]


def _primary_direction_time_key_text(value: Any) -> str:
    """上游 primaryDirectionSync.js:177 getPdTimeKeyLabel（26 项；缺省/未知 → Ptolemy）。"""
    return _PD_TIME_KEY_LABELS.get(_msg(value)) or _PD_TIME_KEY_LABELS["Ptolemy"]


# 上游 utils/primaryDirectionSync.js:28-56 解耦两维标签 + :120-135 PD_METHOD_TO_PAIR（旧单维 → (投影, 分宫)）。
_PD_PROJECTION_LABELS = {
    "ptolemy": "Ptolemy（半弧）", "placidus": "Placidus（半弧严密）", "regiomontanus": "Regiomontanus",
    "campanus": "Campanus", "topocentric": "Topocentric", "zodiacal": "纯黄道（斜升差）",
    "ra_direct": "赤经直推", "in_zodiaco_lon": "Along Ecliptic", "in_zodiaco_abs": "Edmund Jones",
    "horosa_legacy": "Horosa原方法", "placidus_under_pole": "Placidus under-pole（旧法近似）",
}
_PD_FRAME_LABELS = {
    "alcabitius": "Alcabitius", "placidus": "Placidus", "regiomontanus": "Regiomontanus", "campanus": "Campanus",
    "topocentric": "Topocentric", "meridian": "Meridian", "porphyry": "Porphyry", "equal": "Equal（等宫）",
    "wholesign": "Whole Sign（整宫）", "morinus": "Morinus", "koch": "Koch", "equal_hour_circle": "Equal（时圈）",
}
_PD_FRAMEWORK_LABELS = {"aspect": "相位主限", "bounds": "界行·分配星", "release": "释放（hyleg）"}
_PD_METHOD_TO_PAIR: dict[str, tuple[str, str | None]] = {
    "core_alchabitius": ("ptolemy", "alcabitius"), "placidus": ("placidus", "placidus"),
    "regiomontanus": ("regiomontanus", "regiomontanus"), "campanus": ("campanus", "campanus"),
    "topocentric": ("topocentric", "topocentric"), "meridian": ("ptolemy", "meridian"),
    "porphyry": ("ptolemy", "porphyry"), "equal_ecliptic": ("ptolemy", "equal"),
    "equal_hour_circle": ("ptolemy", "equal_hour_circle"), "morinus": ("ptolemy", "morinus"),
    "in_zodiaco_lon": ("in_zodiaco_lon", None), "in_zodiaco_abs": ("in_zodiaco_abs", None),
    "horosa_legacy": ("horosa_legacy", None),
}
# 上游 components/direction/AstroDirectMain.js:82-98（主限法表格的核支持体，比主限法盘多一个 Vertex）。
_PD_TABLE_CORE_BASE_IDS = frozenset({*_PD_CORE_SUPPORTED_BASE_IDS, "Vertex"})
_PD_TERMS_VARIANT_LABELS = {1: "托勒密界·校勘本", 2: "托勒密界·经典传本", 3: "迦勒底界", 4: "自定义界表"}


def _pd_msg(value: Any) -> str:
    """AstroDirectMain.js:100-111 msg：AstroTxtMsg[id] → AstroMsg[id]（恒星/宫位等文字条目）→ id。"""
    return _ptext.astro_msg(value)


def _pd_msg_with_house(chart_wrap: dict[str, Any], object_id: Any) -> str:
    """AstroDirectMain.js:113 msgWithHouse = appendPlanetHouseInfoById(msg(id), chartObj, id, {showHouse,showRuler})。"""
    return _normalize_ai_planet_label(_append_planet_house_info(_pd_msg(object_id), chart_wrap, f"{object_id}"))


def _pd_ext_base_text(base: str) -> str | None:
    """AstroDirectMain.js:153 extDirectionBaseText（S/P 扩展本体语义短名）。"""
    matched = re.fullmatch(r"Cusp(\d+)", base or "")
    if matched:
        return f"第{matched.group(1)}宫头"
    return {"Syzygy": "产前朔望", "Spirit": "精神点"}.get(base or "")


def _pd_direction_obj_text(text: Any, chart_wrap: dict[str, Any]) -> str:
    """逐字镜像 AstroDirectMain.js:168-223 directionObjText（迫星/应星 id → 中文）。"""
    if not text:
        return ""
    raw = f"{text}"
    parts = raw.split("_")
    if len(parts) < 2:
        return raw

    def body(base: str) -> str:
        return _pd_ext_base_text(base) or _pd_msg_with_house(chart_wrap, base)

    head = parts[0]
    third = parts[2] if len(parts) > 2 else ""
    if head == "T":
        return f"{_pd_msg_with_house(chart_wrap, third)}的{_pd_msg_with_house(chart_wrap, parts[1])}界"
    if head == "A":
        return f"{body(parts[1])}的映点"
    if head == "C":
        return f"{body(parts[1])}的反映点"
    if head == "D":
        return f"{body(parts[1])}的{third}度右相位处"
    if head == "S":
        return f"{body(parts[1])}的{third}度左相位处"
    if head == "N":
        if third and third != "0":
            return f"{body(parts[1])}的{third}度相位处"
        return body(parts[1])
    if head == "PD":
        return f"{body(parts[1])}的赤纬平行点"
    if head == "PC":
        return f"{body(parts[1])}的反平行点"
    if head in ("MP", "RP"):
        axis = {"0": "MC", "90": "ASC", "180": "IC", "270": "DSC"}.get(third, third)
        return f"{body(parts[1])}的{'世界平行' if head == 'MP' else '急动平行'}·{axis}"
    if head == "FS":
        return f"恒星 {_pd_msg_with_house(chart_wrap, parts[1]) or parts[1]}"
    if head == "LT":
        return f"{re.sub(r'^Pars ', '', parts[1])}点"
    if head == "HC":
        matched = re.fullmatch(r"Cusp(\d+)", parts[1] or "")
        return f"第{matched.group(1) if matched else parts[1]}宫头"
    return raw


def _pd_split_degree(value: Any) -> tuple[int, int]:
    """上游 AstroHelper.splitDegree 的 [度, 分]（horosa_legacy 赤经列用）。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0, 0
    text = f"{value}".lower()
    neg = number < 0
    deg = abs(number)
    whole = int(abs(int(number)))
    if "e" in text and text.split("e")[1].lstrip("+").lstrip("-").isdigit() and int(text.split("e")[1]) < 0:
        whole, deg = 0, 0.0
    minute_f = (deg - whole) * 60
    minute = math.floor(minute_f)
    sec = _ptext.js_round((minute_f - minute) * 60)
    if sec == 60:
        minute += 1
    if minute == 60:
        whole += 1
        minute = 0
    return (-whole if neg else whole), minute


def _pd_degree_text(value: Any, pd_method: str) -> str:
    """AstroDirectMain.js:122 degreeText：horosa_legacy 走 splitDegree，其余 floor 度/floor 分。"""
    if pd_method == "horosa_legacy":
        deg, minute = _pd_split_degree(value)
        return f"{deg}度{minute}分"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return f"{value or ''}".strip()
    if math.isnan(number):
        return f"{value or ''}".strip()
    neg = "-" if number < 0 else ""
    magnitude = abs(number)
    whole = math.floor(magnitude)
    minute = math.floor((magnitude - whole) * 60)
    if minute >= 60:
        minute = 0
    return f"{neg}{whole}度{minute}分"


def _pd_split_degree_text(value: Any) -> str:
    """AstroPrimaryDirectionChart.js:69 splitDegreeText / aiAnalysisContext pdSplitDegreeText（当前Arc）。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return f"{value or ''}"
    if not math.isfinite(number):
        return f"{value or ''}"
    neg = "-" if number < 0 else ""
    magnitude = abs(number)
    whole = math.floor(magnitude + 1e-12)
    minute = int(_ptext.js_round((magnitude - whole) * 60))
    if minute >= 60:
        return f"{neg}{whole + 1}度0分"
    return f"{neg}{whole}度{minute}分"


def _pd_effective_params(response: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """上游 aiAnalysisContext.js:3066-3100：本命盘回显 params 打底（后端实算口径：pdDirect/pdConverse 缺省 1 等），
    记录（=调用载荷）的主限键覆盖；解耦两维未显式给时按 pdMethod 兼容映射推（与后端 perpredict 同表）。"""
    natal = _natal_chart_wrap(response)
    params = dict(natal.get("params") or {}) if isinstance(natal.get("params"), dict) else {}
    for key, value in payload.items():
        if key.startswith("pd") or key in ("showPdBounds", "termsVariant", "direction"):
            params[key] = value
    method = f"{params.get('pdMethod') or 'core_alchabitius'}"
    pair = _PD_METHOD_TO_PAIR.get(method, ("ptolemy", "alcabitius"))
    params.setdefault("pdProjection", pair[0])
    if params.get("pdFrame") is None and pair[1] is not None:
        params["pdFrame"] = pair[1]
    return params


def _pd_birth_and_chart_info(chart_wrap: dict[str, Any], params: dict[str, Any]) -> list[tuple[str, str]]:
    """AstroDirectMain.js:258-292 appendBirthAndChartInfo：[出生时间] + [星盘信息]（黄道行取回显原词 Tropical）。"""
    chart = chart_wrap.get("chart") if isinstance(chart_wrap.get("chart"), dict) else {}
    birth_lines = []
    if params.get("birth"):
        dayofweek = chart.get("dayofweek")
        birth_lines.append(f"出生时间：{params['birth']}{f' {dayofweek}' if dayofweek else ''}")
    else:
        birth_lines.append("出生时间：无")
    nongli = chart.get("nongli")
    if isinstance(nongli, dict) and nongli.get("birth"):
        birth_lines.append(f"真太阳时：{nongli['birth']}")
    info = []
    if params.get("lon") or params.get("lat"):
        lon_lat = f"{params.get('lon') or ''} {params.get('lat') or ''}".strip()
        info.append(f"经纬度：{lon_lat}")
    if params.get("zone") is not None:
        info.append(f"时区：{params['zone']}")
    zodiacal_raw = chart.get("zodiacal") or _ptext.ZODIACAL.get(_ptext.js_str(params.get("zodiacal")))
    zodiacal = (_ptext.UPSTREAM_ASTRO_TXT_MSG.get("Sidereal") or zodiacal_raw) if zodiacal_raw == "Sidereal" else zodiacal_raw
    if zodiacal:
        info.append(f"黄道：{zodiacal}")
    hsys = _ptext.HOUSE_SYS_LABELS.get(_ptext.js_str(params.get("hsys"))) or chart.get("hsys")
    if hsys:
        info.append(f"宫制：{hsys}")
    if chart.get("isDiurnal") is not None:
        info.append(f"盘型：{'日生盘' if chart.get('isDiurnal') else '夜生盘'}")
    return [("出生时间", "\n".join(birth_lines)), ("星盘信息", "\n".join(info) or "无")]


def _pd_is_extension_row(row: list[Any], params: dict[str, Any]) -> bool:
    """AstroDirectMain.js:309-324 isExtensionDirectionRow（用户勾选的 S/P 扩展行不被核白名单误滤）。"""
    prom = f"{row[1] if len(row) > 1 else ''}"
    if re.match(r"^(HC|FS|LT|PD|PC|MP|RP)_", prom):
        return True
    sig_keys = params.get("pdSignificators") if isinstance(params.get("pdSignificators"), list) else []
    if not sig_keys:
        return False
    sig_parts = f"{row[2] if len(row) > 2 else ''}".split("_")
    sig_base = sig_parts[1] if len(sig_parts) > 1 else ""
    if "Desc" in sig_keys and sig_base == "Desc":
        return True
    if "IC" in sig_keys and sig_base == "IC":
        return True
    if "Syzygy" in sig_keys and sig_base == "Syzygy":
        return True
    if "Spirit" in sig_keys and sig_base == "Spirit":
        return True
    if "Cusps" in sig_keys and re.fullmatch(r"Cusp\d+", sig_base):
        return True
    if ("Stars" in sig_keys or "Lots" in sig_keys) and sig_base and not re.fullmatch(
        r"Sun|Moon|Mercury|Venus|Mars|Jupiter|Saturn|Uranus|Neptune|Pluto", sig_base
    ):
        return True
    return False


def _pd_table_rows(rows: Any, params: dict[str, Any]) -> list[list[Any]]:
    """AstroDirectMain.js:325-333：core_alchabitius 下滤非核体（扩展行放行）；关界限法时滤界行。"""
    method = f"{params.get('pdMethod') or 'core_alchabitius'}"
    show_bounds = params.get("showPdBounds") not in (0, False)
    out = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, list) or not row:
            continue
        if method == "core_alchabitius":
            unsupported = _pd_is_bound_row(row) or (
                _pd_base_object_id(row[1] if len(row) > 1 else "") not in _PD_TABLE_CORE_BASE_IDS
                or _pd_base_object_id(row[2] if len(row) > 2 else "") not in _PD_TABLE_CORE_BASE_IDS
            )
            if unsupported and not _pd_is_extension_row(row, params):
                continue
            if not show_bounds and _pd_is_bound_row(row):
                continue
        out.append(row)
    return out


def _pd_source_rows(response: dict[str, Any]) -> Any:
    """主限行来源：/predict/pd 回包顶层 pd；缺则本命盘内嵌 predictives.primaryDirection（上游 chartObj 同源）。"""
    if not isinstance(response, dict):
        return []
    rows = response.get("pd")
    predictives = response.get("predictives")
    if rows is None and isinstance(predictives, dict):
        rows = predictives.get("primaryDirection", [])
    return rows


def _pd_nearest_line(rows: list[list[Any]], params: dict[str, Any], chart_wrap: dict[str, Any], now: datetime | None = None) -> str:
    """AstroDirectMain.js:405-418：表中日期距今最近行（[当前时点] 定位行）。"""
    moment = now or datetime.now()
    method = f"{params.get('pdMethod') or 'core_alchabitius'}"
    best = None
    for row in rows:
        when = _js_date_parse(row[4] if len(row) > 4 else "")
        if when is None:
            continue
        distance = abs((when - moment).total_seconds())
        if best is None or distance < best[0]:
            best = (distance, row)
    if best is None:
        return ""
    row = best[1]
    return (
        f"表中距今最近行：{_pd_degree_text(row[0], method) or '无'}（{_pd_direction_obj_text(row[1], chart_wrap) or '无'} → "
        f"{_pd_direction_obj_text(row[2], chart_wrap) or '无'}，{row[4] if len(row) > 4 and row[4] else '无'}）"
    )


def _build_primarydirect_snapshot_text(
    payload: dict[str, Any], response: dict[str, Any], *, moment_lines: list[str] | None = None, now: datetime | None = None
) -> str:
    """逐字镜像上游 components/direction/AstroDirectMain.js:294-432 buildPrimaryDirectSnapshotText。

    行来自 /predict/pd（= 后端 getPrimaryDirection，与上游 chartObj.predictives.primaryDirection 同源）；[主限法设置]
    列上游 16 行口径（方向类型/向运方向/映点迫星/界迫星/弧算法/盘面宫制/框架/…）；表 4 列「日期(UTC)」；
    UI-only 段 [主限天球·当前动画所指] headless 不产。skill 自有 [本命盘星与虚点] 段保留在 [星盘信息] 后。
    """
    params = _pd_effective_params(response, payload)
    natal_wrap = _natal_chart_wrap(response) or _top_level_chart_wrap(response)
    method = f"{params.get('pdMethod') or 'core_alchabitius'}"
    time_key = f"{params.get('pdTimeKey') or 'Ptolemy'}"
    rows = _pd_table_rows(_pd_source_rows(response), params)
    show_bounds = params.get("showPdBounds") not in (0, False)
    want_direct = params.get("pdDirect") not in (0, False, "0")
    want_converse = bool(params.get("pdConverse")) and params.get("pdConverse") not in ("0",)
    if want_direct and want_converse:
        dir_text = "顺向 Direct + 逆向 Converse"
    elif want_converse:
        dir_text = "逆向 Converse"
    else:
        dir_text = "顺向 Direct"
    pdtype_raw = params.get("pdtype")
    projection = params.get("pdProjection")
    proj_label = _PD_PROJECTION_LABELS.get(f"{projection}") or projection or "Ptolemy（半弧）"
    if _finite_number(pdtype_raw) == 1 and projection not in ("placidus", "regiomontanus", "campanus", "topocentric"):
        proj_label = f"{proj_label}（世界主限下走核内基线）"
    frame = params.get("pdFrame")
    framework = params.get("pdFramework")
    setting = [
        f"推运方法：{_primary_direction_method_text(method)}",
        f"度数换算：{_primary_direction_time_key_text(time_key)}",
        f"方向类型：{'世俗（In Mundo）' if pdtype_raw == 1 else '黄道（In Zodiaco）'}",
        f"向运方向：{dir_text}",
        f"映点迫星：{'是' if params.get('pdAntiscia') else '否'}",
        f"界迫星：{'是' if params.get('pdTerms') else '否'}",
        f"弧算法（投影）：{proj_label}",
        f"盘面宫制（分宫）：{_PD_FRAME_LABELS.get(f'{frame}') or frame or 'Alcabitius'}",
        f"框架：{_PD_FRAMEWORK_LABELS.get(f'{framework}') or framework or '相位主限'}",
    ]
    if params.get("pdParallel"):
        setting.append(f"平行迫星：{'世界平行' if pdtype_raw == 1 else '赤纬平行（映点法）'}")
    if params.get("pdRaptParallel"):
        setting.append("急动平行迫星：是")
    terms_variant = _finite_number(params.get("termsVariant"))
    if terms_variant is not None and 1 <= terms_variant <= 4 and int(terms_variant) in _PD_TERMS_VARIANT_LABELS:
        setting.append(f"界系：{_PD_TERMS_VARIANT_LABELS[int(terms_variant)]}")
    if time_key == "User" and params.get("pdTimeKeyCustom"):
        setting.append(f"自定义钥匙率：{_ptext.js_str(params['pdTimeKeyCustom'])}°/年")
    for key, label in (("pdSignificators", "应星扩展"), ("pdPromissorTypes", "迫星扩展")):
        values = params.get(key)
        if isinstance(values, list) and values:
            setting.append(f"{label}：{'、'.join(f'{v}' for v in values)}")
    setting.append(f"显示界限法：{'是' if show_bounds else '否'}")
    degree_label = "赤经" if method == "horosa_legacy" else "Arc"
    table = [f"| {degree_label} | 迫星 | 应星 | 日期(UTC) |", "| --- | --- | --- | --- |"]
    if not rows:
        table.append("| 无 | 无 | 无 | 无 |")
    for row in rows:
        date = f"{row[4]}" if len(row) > 4 and row[4] else ""
        table.append(
            f"| {_pd_degree_text(row[0], method) or '无'} | {_pd_direction_obj_text(row[1] if len(row) > 1 else None, natal_wrap) or '无'} | "
            f"{_pd_direction_obj_text(row[2] if len(row) > 2 else None, natal_wrap) or '无'} | {date or '无'} |"
        )
    if moment_lines is not None:
        nearest = _pd_nearest_line(rows, params, natal_wrap, now)
        if nearest:
            moment_lines.append(nearest)
    head = _pd_birth_and_chart_info(natal_wrap, params)
    return _render_snapshot_text(
        [
            *head,
            ("本命盘星与虚点", _join_lines(_build_star_and_lot_position_lines(natal_wrap)) or "无"),
            # 上游 v48 段名对齐：主/界限法设置 → 主限法设置（旧名走 map_legacy_section_title）。
            ("主限法设置", _join_lines(setting)),
            ("主限法表格", _join_lines(table)),
        ]
    )


def _pdchart_chart_info_lines(chart_wrap: dict[str, Any], params: dict[str, Any]) -> list[str]:
    """AstroPrimaryDirectionChart.js:335-346 [星盘信息]：经纬度/时区恒出（缺则「无」）+ 黄道（显示文案）+ 宫制。"""
    chart = chart_wrap.get("chart") if isinstance(chart_wrap.get("chart"), dict) else {}
    lon_lat = f"{params.get('lon') or ''} {params.get('lat') or ''}".strip()
    lines = [f"经纬度：{lon_lat or '无'}", f"时区：{params.get('zone') or '无'}"]
    zodiacal_raw = chart.get("zodiacal") or _ptext.ZODIACAL.get(_ptext.js_str(params.get("zodiacal")))
    if zodiacal_raw:
        ayan_key = params.get("siderealAyanamsa") or chart.get("siderealAyanamsa") or ""
        lines.append(f"黄道：{_ptext.zodiacal_display_text(zodiacal_raw, ayan_key)}")
    hsys = _ptext.HOUSE_SYS_LABELS.get(_ptext.js_str(params.get("hsys"))) or chart.get("hsys")
    if hsys:
        lines.append(f"宫制：{hsys}")
    return lines


def _build_pdchart_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    """上游 AstroPrimaryDirectionChart.js:328-373 buildSnapshotText（= aiAnalysisContext 无头 buildPrimaryDirChartSnapshotText）。

    [主限法盘设置] 5 行（时间选择/推运方法/度数换算/向运方向/当前Arc「X度Y分」，Arc 取推导盘回的 arc [Q-171/T-112]）；
    skill 自有 [本命盘星与虚点]/[主限法盘星体表格]/[主限法盘相位] 保留（registry 注记）。
    """
    natal_wrap = _natal_chart_wrap(response)
    params = _pd_effective_params(response, payload)
    current_arc = response.get("currentArc") or response.get("arc") or response.get("pdArc")
    pd_wrap = _top_level_chart_wrap(response)
    return _render_snapshot_text(
        [
            ("出生时间", f"出生时间：{params.get('birth') or '无'}"),
            ("星盘信息", _join_lines(_pdchart_chart_info_lines(natal_wrap, params))),
            ("本命盘星与虚点", _join_lines(_build_star_and_lot_position_lines(natal_wrap)) or "无"),
            (
                "主限法盘设置",
                _join_lines(
                    [
                        f"时间选择：{payload.get('datetime') or '无'}",
                        f"推运方法：{_primary_direction_method_text(params.get('pdMethod'))}",
                        f"度数换算：{_primary_direction_time_key_text(params.get('pdTimeKey'))}",
                        f"向运方向：{'逆向 Converse' if params.get('direction') == 'converse' else '顺向 Direct'}",
                        f"当前Arc：{_pd_split_degree_text(current_arc) if current_arc is not None else '无'}",
                    ]
                ),
            ),
            # 上游这两段是「本命盘配置(内圈)」与「主限法盘配置(外圈/时段盘)」，各含 星与虚点 + 宫位宫头
            # 两个子块（AstroPrimaryDirectionChart.js:351-366）。本仓原有的 主限法盘星体表格 / 主限法盘相位
            # 是 skill-extra，保留在后面。
            ("本命盘配置", _join_lines(_natal_config_lines(natal_wrap)) or "无"),
            ("主限法盘配置", _join_lines(_directed_config_lines(pd_wrap)) or "无"),
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


# 上游 components/astro/AstroZR.js:314-322 ZR_BASE_POINTS：福点/六希腊点/四轴 11 项 + 十二星座（[Q-174/T-114]）。
_ZR_BASE_POINTS = (
    "Pars Fortuna", "Pars Spirit", "Pars Mercury", "Pars Venus", "Pars Mars", "Pars Jupiter", "Pars Saturn",
    "Asc", "Desc", "MC", "IC", *_ptext.LIST_SIGNS,
)
# 上游 AstroZR.js:26-46 AI_MODE_ITEMS（输出层级）。
_ZR_AI_MODES = {
    "l1_all": "输出所有L1（星座+时间）",
    "l2_in_l1": "输出某个L1下全部L2",
    "l3_in_l2": "输出某个L2下全部L3",
    "l4_in_l3": "输出某个L3下全部L4",
}


def _zr_sign_name(sign: Any) -> str:
    """AstroZR.js:63 signName：空 → '无'，否则 AstroTxtMsg。"""
    return _ptext.astro_txt(sign) if sign else "无"


def _zr_node_line(item: dict[str, Any] | None) -> str:
    """AstroZR.js:70 nodeLine：座-日期[-LB][-截]（[Q-362/T-343] truncated=末段子期按父期截断）。"""
    if not item:
        return "无"
    base = f"{_zr_sign_name(item.get('sign'))}-{item.get('date') or '无'}"
    if item.get("isLB"):
        base = f"{base}-LB"
    return f"{base}-截" if item.get("truncated") else base


def _zr_mark_special_flags(items: Any, parent_sign_idx: int) -> list[dict[str, Any]]:
    """AstroZR.js:79 markZRSpecialFlags：同父下第二个「与父座对冲」的子期标 LB（跳宫）。"""
    if not isinstance(items, list):
        return []
    opposite = 0
    marked: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        sign = item.get("sign")
        level = _finite_number(item.get("level")) or 0
        sign_idx = _ptext.LIST_SIGNS.index(sign) if sign in _ptext.LIST_SIGNS else -1
        is_lb = False
        if level > 1 and parent_sign_idx >= 0 and sign_idx >= 0 and (sign_idx + 6) % 12 == parent_sign_idx:
            opposite += 1
            if opposite == 2:
                is_lb = True
        marked.append({**item, "isLB": is_lb, "sublevel": _zr_mark_special_flags(item.get("sublevel"), sign_idx)})
    return marked


def _zr_safe_idx(idx: Any, length: int) -> int:
    """AstroZR.js:48 safeIdx。"""
    if not length or length <= 0:
        return 0
    number = _finite_number(idx)
    if number is None or number < 0:
        return 0
    return length - 1 if number >= length else int(number)


def _zr_birth_and_chart_lines(chart_wrap: dict[str, Any], params: dict[str, Any]) -> list[str]:
    """AstroZR.js:137-178 appendBirthAndChart：[起盘信息] + [星盘信息]（黄道行取 AstroTxtMsg，回归盘即写 Tropical）。"""
    chart = chart_wrap.get("chart") if isinstance(chart_wrap.get("chart"), dict) else {}
    lines = ["[起盘信息]"]
    if params.get("birth"):
        dayofweek = chart.get("dayofweek")
        lines.append(f"出生时间：{params['birth']}{f' {dayofweek}' if dayofweek else ''}")
    nongli = chart.get("nongli")
    if isinstance(nongli, dict) and nongli.get("birth"):
        lines.append(f"真太阳时：{nongli['birth']}")
    if params.get("date") or params.get("time"):
        when = f"{params.get('date') or ''} {params.get('time') or ''}".strip()
        lines.append(f"起盘时间：{when}")
    if params.get("lon") or params.get("lat"):
        lon_lat = f"{params.get('lon') or ''} {params.get('lat') or ''}".strip()
        lines.append(f"经纬度：{lon_lat}")
    if params.get("zone") is not None:
        lines.append(f"时区：{params['zone']}")
    if params.get("tradition"):
        lines.append(f"历法：{_ptext.js_str(params['tradition'])}")
    lines.extend(["", "[星盘信息]"])
    zodiacal_raw = chart.get("zodiacal") or _ptext.ZODIACAL.get(_ptext.js_str(params.get("zodiacal")))
    if zodiacal_raw:
        lines.append(f"黄道：{_ptext.UPSTREAM_ASTRO_TXT_MSG.get(zodiacal_raw) or zodiacal_raw}")
    hsys = _ptext.HOUSE_SYS_LABELS.get(_ptext.js_str(params.get("hsys"))) or chart.get("hsys")
    if hsys:
        lines.append(f"宫制：{hsys}")
    if chart.get("isDiurnal") is not None:
        lines.append(f"盘型：{'日生盘' if chart.get('isDiurnal') else '夜生盘'}")
    return lines


def _zr_natal_params(chart_wrap: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """AstroZR.js:329 zrNatalParamsStandalone 的文字源：date/time 取 params.date/time，缺则拆 params.birth。"""
    params = chart_wrap.get("params") if isinstance(chart_wrap.get("params"), dict) else {}
    birth = params.get("birth")
    parts = f"{birth}".split(" ") if birth else []
    return {
        "date": params.get("date") or (parts[0] if parts else None),
        "time": params.get("time") or (parts[1] if len(parts) > 1 else None),
        "zone": params.get("zone"),
        "lon": params.get("lon"),
        "lat": params.get("lat"),
        "hsys": params.get("hsys"),
        "tradition": params.get("tradition"),
        "birth": birth,
        "zodiacal": params.get("zodiacal"),
    }


def _zr_body_lines(base_point: str, items: list[dict[str, Any]], ai_state: dict[str, Any]) -> list[str]:
    """AstroZR.js:238-311 buildZRAISnapshotBody（[基于X推运] 段正文，按输出层级逐层钻取）。"""
    lines = [f"[基于{_ptext.UPSTREAM_ASTRO_TXT_MSG.get(base_point) or base_point}推运]"]
    ai_mode = ai_state.get("aiMode")
    lines.append(f"AI输出模式：{_ZR_AI_MODES.get(ai_mode, _ZR_AI_MODES['l1_all'])}")
    l1_list = _zr_mark_special_flags(items, -1)
    if not l1_list:
        lines.append("无推运数据")
        return lines
    if ai_mode == "l1_all":
        lines.extend(f"L1-{i + 1}：{_zr_node_line(item)}" for i, item in enumerate(l1_list))
        return lines
    l1_idx = _zr_safe_idx(ai_state.get("aiL1Idx"), len(l1_list))
    l1 = l1_list[l1_idx] if l1_list else None
    l2_list = l1.get("sublevel") if l1 and isinstance(l1.get("sublevel"), list) else []
    l2_idx = _zr_safe_idx(ai_state.get("aiL2Idx"), len(l2_list))
    l2 = l2_list[l2_idx] if l2_list else None
    l3_list = l2.get("sublevel") if l2 and isinstance(l2.get("sublevel"), list) else []
    l3_idx = _zr_safe_idx(ai_state.get("aiL3Idx"), len(l3_list))
    l3 = l3_list[l3_idx] if l3_list else None
    if not l1:
        lines.append("未找到L1数据")
        return lines
    lines.append(f"L1-{l1_idx + 1}：{_zr_node_line(l1)}")
    if ai_mode == "l2_in_l1":
        if not l2_list:
            lines.append("无L2数据")
        else:
            lines.extend(f"L2-{i + 1}：{_zr_node_line(item)}" for i, item in enumerate(l2_list))
        return lines
    if not l2:
        lines.append("未找到L2数据")
        return lines
    lines.append(f"L2-{l2_idx + 1}：{_zr_node_line(l2)}")
    if ai_mode == "l3_in_l2":
        if not l3_list:
            lines.append("无L3数据")
        else:
            lines.extend(f"L3-{i + 1}：{_zr_node_line(item)}" for i, item in enumerate(l3_list))
        return lines
    if not l3:
        lines.append("未找到L3数据")
        return lines
    lines.append(f"L3-{l3_idx + 1}：{_zr_node_line(l3)}")
    l4_list = l3.get("sublevel") if isinstance(l3.get("sublevel"), list) else []
    if not l4_list:
        lines.append("无L4数据")
    else:
        lines.extend(f"L4-{i + 1}：{_zr_node_line(item)}" for i, item in enumerate(l4_list))
    return lines


def _zr_period_bounds(items: list[dict[str, Any]], now: datetime) -> dict[str, Any] | None:
    """AstroZR.js:198-218 zrLocateCurrent：期起=date（Date.parse 纯日期 = UTC 零点），期讫=下一期起/末期 date+days。"""
    now_utc = now.astimezone(timezone.utc) if now.tzinfo else now.replace(tzinfo=timezone.utc)
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        start = _zr_parse_day_utc(item.get("date"))
        if start is None:
            continue
        nxt = items[index + 1] if index + 1 < len(items) and isinstance(items[index + 1], dict) else None
        next_start = _zr_parse_day_utc(nxt.get("date")) if nxt else None
        days = _finite_number(item.get("days"))
        end = next_start if next_start is not None else (start + timedelta(days=days) if days is not None else None)
        if end is not None and start <= now_utc < end:
            return {
                "item": item,
                "startText": f"{item.get('date')}",
                "endText": f"{nxt.get('date')}" if next_start is not None and nxt else end.strftime("%Y-%m-%d"),
            }
    return None


def _zr_parse_day_utc(text: Any) -> datetime | None:
    raw = f"{text or ''}".strip().replace("/", "-")
    try:
        return datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _zr_current_period_line(items: Any, now: datetime | None = None) -> str:
    """AstroZR.js:221-231 zrCurrentPeriodLine：「当前所处：L1 X期（…至…）/ L2 Y期（…至…）」。"""
    if not isinstance(items, list):
        return ""
    moment = now or datetime.now().astimezone()
    l1 = _zr_period_bounds(items, moment)
    if not l1:
        return ""
    text = f"当前所处：L1 {_zr_sign_name(l1['item'].get('sign'))}期（{l1['startText']} 至 {l1['endText']}）"
    sub = l1["item"].get("sublevel")
    l2 = _zr_period_bounds(sub, moment) if isinstance(sub, list) else None
    if l2:
        text += f" / L2 {_zr_sign_name(l2['item'].get('sign'))}期（{l2['startText']} 至 {l2['endText']}）"
    return text


def _zr_items(response: dict[str, Any]) -> list[dict[str, Any]]:
    predictives = response.get("predictives", {}) if isinstance(response, dict) else {}
    for key in ("zr", "zodialRelease", "zodiacalRelease", "zodialrelease"):
        if isinstance(response.get(key), list):
            return response[key]
        if isinstance(predictives, dict) and isinstance(predictives.get(key), list):
            return predictives[key]
    return []


def _build_zr_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    """逐字镜像上游 components/astro/AstroZR.js:233-311 buildZRAISnapshot(Body)（[当前时点]/[方法说明] 由统一出口追加）。

    F8：基点 basePoint（福点/六希腊点/四轴/十二星座）→ 段头 [基于<名>推运]（此前恒写「基于X点推运」字面占位）；
    输出层级 aiMode（L1 全列 / 某 L1 下全部 L2 / 某 L2 下全部 L3 / 某 L3 下全部 L4）+ aiL1Idx/aiL2Idx/aiL3Idx 钻取。
    旧实现另出 skill 自拟段 [本命盘星与虚点] 与「L1：座；开始：…；时长：…日」行式，均非上游。
    """
    natal_wrap = _natal_chart_wrap(response)
    source = natal_wrap if isinstance(natal_wrap.get("params"), dict) else _ptext.payload_chart_wrap(payload)
    base_point = payload.get("basePoint") or payload.get("startSign") or "Pars Fortuna"
    ai_state = {
        "aiMode": payload.get("aiMode") if payload.get("aiMode") in _ZR_AI_MODES else "l1_all",
        "aiL1Idx": payload.get("aiL1Idx") or 0,
        "aiL2Idx": payload.get("aiL2Idx") or 0,
        "aiL3Idx": payload.get("aiL3Idx") or 0,
    }
    lines = _zr_birth_and_chart_lines(source, _zr_natal_params(source, payload))
    lines.append("")
    lines.extend(_zr_body_lines(base_point, _zr_items(response), ai_state))
    return "\n".join(lines).strip()


def _auto_snapshot_text_for_tool(tool_name: str, input_normalized: dict[str, Any], response_data: dict[str, Any]) -> str | None:
    if tool_name in {"chart", "chart13", "chart12", "hellen_chart", "india_chart", "draconic", "relocation"} and _is_astro_chart_payload(response_data):
        return _build_astro_snapshot_text(input_normalized, response_data)
    # 调波盘：上游 v50 的 `harmonic` 键要求整套本命盘段 + 调波专属段。盘面本就在响应里（已在
    # `_run_harmonic_tool` 摊平到顶层），所以走通用盘面渲染器，再把 [调波位置]/[同频合相] 接在后面。
    # 这两段由 `_build_harmonic_snapshot_text` 出，它自带的 [起盘信息] 与通用器重复，故只取尾两段。
    if tool_name == "harmonic":
        extra = _build_harmonic_snapshot_text(input_normalized, response_data)
        # 后端只回了调波数据、没回盘面时（老响应形状 / 降级），退回「起盘信息 + 调波两段」的旧行为，
        # 而不是整个不出快照。
        if not _is_astro_chart_payload(response_data):
            return extra
        base = _build_astro_snapshot_text(input_normalized, response_data)
        tail = [block for block in extra.split("\n[") if block.startswith(("调波位置]", "同频合相]"))]
        return "\n".join([base] + [f"[{block.rstrip()}" for block in tail]) if tail else base
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
    if tool_name == "ziwei_rules":
        # ziwei_birth 由 _run_ziwei_tool 出 vendored 上游快照；这里只剩规则库（无盘）一支。
        return _build_ziwei_snapshot_text(input_normalized, response_data)
    if tool_name in {"liureng_gods", "liureng_runyear"}:
        return _build_liureng_snapshot_text(input_normalized, response_data)
    if tool_name == "jieqi_year":
        return _build_jieqi_snapshot_text(input_normalized, response_data)
    if tool_name == "nongli_time":
        return _build_nongli_snapshot_text(input_normalized, response_data)
    if tool_name == "calendar_month":
        return _build_calendar_month_snapshot_text(input_normalized, response_data)
    if tool_name in {"gua_desc", "gua_meiyi"}:
        return _build_gua_lookup_snapshot_text(tool_name, input_normalized, response_data)
    return None


def _pick_section_data(title: str, *, input_normalized: dict[str, Any], response_data: dict[str, Any]) -> Any:
    normalized_title = title.strip()
    if _is_astro_chart_payload(response_data):
        if normalized_title in {"起盘信息", "出生时间", "关系起盘信息", "节气盘参数", "星盘信息"}:
            lines = _build_base_info_lines(response_data, input_normalized)
            return _export_body("\n".join(lines).strip())
        if normalized_title in {"宫位宫头", "宫位总览"}:
            lines = _build_house_cusp_lines(response_data)
            return _export_body("\n".join(lines).strip())
        if normalized_title in {"星与虚点"}:
            lines = _build_star_and_lot_position_lines(response_data)
            return _export_body("\n".join(lines).strip())
        if normalized_title == "信息":
            lines = _build_info_section(response_data, input_normalized)
            return _export_body("\n".join(lines).strip())
        if normalized_title == "相位":
            lines = _build_aspect_section(response_data)
            return _export_body("\n".join(lines).strip())
        if normalized_title == "行星":
            lines = _build_planet_section(response_data)
            return _export_body("\n".join(lines).strip())
        if normalized_title == "希腊点":
            lines = _build_lots_section(response_data)
            return _export_body("\n".join(lines).strip())
        if normalized_title == "可能性":
            lines = _build_possibility_section(response_data)
            return _export_body("\n".join(lines).strip())

    if normalized_title in {"起盘信息", "出生时间", "关系起盘信息", "节气盘参数"}:
        return input_normalized
    if normalized_title in {"主限法设置", "主/界限法设置", "主限法盘设置", "十年大运设置"}:
        return {"input": input_normalized}
    # 其余段一律不带 data（v0.36.0）：引擎对象 chart/pan/liureng/bazi/jinkou/predictives 只在
    # `data.<key>` 出现一次。此前这里兜底 `return response_data` / `X or response_data` 把整份引擎
    # 对象复制进每个段，见 LESSONS v0.36.0「导出段 data 逐段整份复制」。
    return None


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
        body = f"{parsed_section.get('body') or ''}".strip()
        if not body:
            # 段未进快照时才生成兜底正文（此前对每段都算一遍、还把整份引擎对象塞进段 data）。
            section_data = _pick_section_data(title, input_normalized=input_normalized, response_data=response_data)
            if isinstance(section_data, dict) and "__export_body__" in section_data:
                body = _stringify_export_body(section_data.get("__export_body__"))
            else:
                body = _stringify_export_body(section_data)
                # 守卫按**字节+行数**双判：单行 JSON dump 曾靠「只数行」漏进 export_text（303 KB）。
                if body and (len(body.encode("utf-8")) > 2048 or len(body.splitlines()) > 80):
                    body = _missing_detail_text(title)
            # 段既不在快照里、又无可生成正文 → 明示「未产出」占位（旧实现靠整份 dump 触发 80 行守卫才得到同一
            # 占位；段正文绝不裸空——faithfulness/报告/「不得臆造依赖」检查都以非空正文为前提）。
            if not body:
                body = _missing_detail_text(title)
        content = parsed_section.get("content") or (f"[{title}]\n{body}".strip() if body else f"[{title}]")
        rendered_blocks.append(content)
        # 段只存 body（content 可由 "[title]\nbody" 推导）；全文只存 export_text 一份；引擎对象只在
        # data.<key> 存一份 —— 段不再带 data 键（envelope schema 0.8.0）。
        sections.append(
            {
                "index": index,
                "raw_title": parsed_section.get("raw_title", title),
                "title": title,
                "included": True,
                "body": body,
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
        "export_text": export_text,
        "format_source": "snapshot_parser" if parsed_snapshot else "generated_template",
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
    # 星运族公共段（当前时点/方法说明）在统一出口追加一次,22 键全覆盖;追加后强制重解析。
    # [起盘信息] 按上游位于段首；已有该段的技法（推运族等）不重复加。
    predictive_setup = _predictive_setup_section_text(technique, input_normalized, response_data)
    if snapshot_text and predictive_setup and "[起盘信息]" not in snapshot_text:
        snapshot_text = f"{predictive_setup}\n\n{snapshot_text}"
        augmented["snapshot_text"] = snapshot_text
        parsed_snapshot = None
    moment_extra = augmented.pop("_moment_lines", None)
    if moment_extra is None and technique == "zodialrelease":
        # 上游 AstroZR.js:236：[当前时点] 追加「当前所处：L1 …期 / L2 …期」定位行（远端工具在统一出口补算）。
        zr_line = _zr_current_period_line(_zr_items(augmented))
        moment_extra = [zr_line] if zr_line else []
    if moment_extra is None and technique == "primarydirect":
        # 上游 AstroDirectMain.js:405-431：[当前时点] 追加「表中距今最近行」。
        pd_params = _pd_effective_params(augmented, input_normalized)
        pd_rows = _pd_table_rows(_pd_source_rows(augmented), pd_params)
        pd_wrap = _natal_chart_wrap(augmented) or _top_level_chart_wrap(augmented)
        nearest = _pd_nearest_line(pd_rows, pd_params, pd_wrap)
        moment_extra = [nearest] if nearest else []
    predictive_common = _predictive_common_sections_text(
        technique, input_normalized, moment_extra if isinstance(moment_extra, list) else None
    )
    if snapshot_text and predictive_common and "[方法说明]" not in snapshot_text:
        snapshot_text = f"{snapshot_text}\n\n{predictive_common}"
        augmented["snapshot_text"] = snapshot_text
        parsed_snapshot = None
    if snapshot_text and not parsed_snapshot:
        try:
            parsed_snapshot = parse_export_content(technique=technique, content=snapshot_text)
            augmented["export_snapshot"] = parsed_snapshot
        except ValueError:
            parsed_snapshot = None
    export_contract = _build_generated_export_snapshot(
        technique=technique,
        input_normalized=input_normalized,
        response_data=augmented,
        snapshot_text=snapshot_text,
        parsed_snapshot=parsed_snapshot,
    )
    if export_contract is None:
        # 兜底剥离：_run_* 自写 parser 形状 export_snapshot 而模板生成失败时，冗余全文键不外泄。
        if isinstance(augmented.get("export_snapshot"), dict):
            augmented["export_snapshot"] = _slim_export_snapshot(augmented["export_snapshot"])
        return augmented

    # data.export_snapshot 是唯一导出契约（原 export_format 为其真子集，已并入不再单独产出）；
    # 原始全段快照的唯一权威是顶层 data.snapshot_text。
    augmented["export_snapshot"] = export_contract
    return augmented


def _slim_export_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """剥离 parser 中间态里的冗余全文键（与顶层 snapshot_text / export_text 重复）。"""
    slim = {key: value for key, value in snapshot.items() if key not in {"raw_text", "filtered_text", "snapshot_text"}}
    sections = slim.get("sections")
    if isinstance(sections, list):
        slim["sections"] = [
            {key: value for key, value in section.items() if key != "content"} if isinstance(section, dict) else section
            for section in sections
        ]
    return slim


def _with_operational_recovery(code: str, details: dict[str, Any] | None) -> dict[str, Any]:
    """给每个错误码统一补 agent_recovery（安装/体检/重试/修入参语义，双语），已带者不覆盖。

    v0.36.0 B4：此前只认 runtime./transport./js_engine./backend_param 四类，其余 ~100 个码裸奔；现在
    走 errors.recovery_for 的三层规则（精确码表 → 后缀 → 前缀），新码落不到规则即 CI 红。
    """
    return recovery_for(code, details)

def _apply_response_view(envelope: ToolEnvelope, input_normalized: dict[str, Any]) -> ToolEnvelope:
    """response_view 响应视图：titles=只留段标题索引；sections=段标题+正文。

    只精简返回体（存档已保全量，完整结果可经 memory_show(run_id) 取回）；未知/缺省值原样返回。
    """
    view = str(input_normalized.get("response_view") or "").strip().lower()
    if view not in {"titles", "sections"} or not isinstance(envelope.data, dict):
        return envelope
    data = dict(envelope.data)
    contract = data.get("export_snapshot")
    if isinstance(contract, dict):
        slim = dict(contract)
        sections = [section for section in contract.get("sections", []) if isinstance(section, dict)]
        if view == "titles":
            slim["sections"] = [{"index": section.get("index"), "title": section.get("title")} for section in sections]
        else:
            slim["sections"] = [
                {"index": section.get("index"), "title": section.get("title"), "body": section.get("body")}
                for section in sections
            ]
        slim.pop("export_text", None)
        data["export_snapshot"] = slim
    if isinstance(data.get("snapshot_text"), str):
        data["snapshot_text"] = ""
    # `technique_card` **不裁**：它几行大小，而且正是「省 token 时也要知道这盘是谁算的、什么口径」
    # 的那份数据。裁掉它等于让最需要溯源的场景（精简模式）反而没有溯源。
    envelope.data = data
    envelope.warnings = [
        *envelope.warnings,
        f"response_view={view}：返回体已按需精简；完整快照已存档，可用 memory_show(run_id) 取回。",
    ]
    return envelope


def _build_dispatch_export_contract(result: ToolEnvelope) -> dict[str, Any]:
    # dispatch 轻契约：只带元信息与段标题索引；快照本体在 results[tool].data 已有一份，不再内嵌复制。
    export_snapshot = result.data.get("export_snapshot") if isinstance(result.data, dict) else None
    technique = export_snapshot.get("technique") if isinstance(export_snapshot, dict) else None
    section_titles: list[str] = []
    if isinstance(export_snapshot, dict):
        for section in export_snapshot.get("sections", []):
            if isinstance(section, dict) and section.get("title"):
                section_titles.append(section["title"])
    return {
        "ok": result.ok,
        "tool": result.tool,
        "summary": list(result.summary),
        "warnings": list(result.warnings),
        "memory_ref": result.memory_ref.model_dump(mode="json") if result.memory_ref else None,
        "has_export_snapshot": isinstance(export_snapshot, dict),
        "technique": technique,
        "selected_sections": list(export_snapshot.get("selected_sections", [])) if isinstance(export_snapshot, dict) else [],
        "format_source": export_snapshot.get("format_source") if isinstance(export_snapshot, dict) else None,
        "section_count": len(section_titles),
        "section_titles": section_titles,
        "bundle_version": export_snapshot.get("bundle_version") if isinstance(export_snapshot, dict) else None,
        "provenance": export_snapshot.get("provenance") if isinstance(export_snapshot, dict) else None,
        "citation": export_snapshot.get("citation") if isinstance(export_snapshot, dict) else None,
        "error": result.error.model_dump(mode="json") if result.error else None,
    }


def _build_compact_subresult_contract(result: ToolEnvelope) -> dict[str, Any]:
    data = result.data if isinstance(result.data, dict) else {}
    export_snapshot = data.get("export_snapshot") if isinstance(data.get("export_snapshot"), dict) else None
    section_titles = []
    if isinstance(export_snapshot, dict):
        for section in export_snapshot.get("sections", []):
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
            "technique": export_snapshot.get("technique") if isinstance(export_snapshot, dict) else None,
            "selected_sections": list(export_snapshot.get("selected_sections", [])) if isinstance(export_snapshot, dict) else [],
            "format_source": export_snapshot.get("format_source") if isinstance(export_snapshot, dict) else None,
            "section_count": len(section_titles),
            "section_titles": section_titles,
            "bundle_version": export_snapshot.get("bundle_version") if isinstance(export_snapshot, dict) else None,
            "provenance": export_snapshot.get("provenance") if isinstance(export_snapshot, dict) else None,
            "citation": export_snapshot.get("citation") if isinstance(export_snapshot, dict) else None,
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
        decision_layer: DecisionLayer | None = None,
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
        # 可选云端决策层（v0.39.0）：HOROSA_JEV=off（缺省）→ None，本进程零对象、零网络。
        # 失败通过 _degrade 进 envelope.warnings（关闭式降级，禁静默）。测试注入桩走这个参数。
        self.decision_layer = (
            decision_layer
            if decision_layer is not None
            else DecisionLayer.from_settings(settings, degrade=lambda message: _degrade("%s", message, note=message))
        )

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

    def _java_cooldown_remaining(self) -> float:
        probe = getattr(self.runtime_manager, "java_backend_cooldown_remaining", None)
        try:
            return float(probe()) if callable(probe) else 0.0
        except Exception:  # noqa: BLE001 — a broken state file must not turn into a new failure mode
            return 0.0

    @staticmethod
    def _java_unavailable_error(endpoint: str, remaining: float) -> ToolTransportError:
        return ToolTransportError(
            "Horosa Java backend (:9999) is unavailable; the runtime is running degraded on the chart service only.",
            code="runtime.java_backend_unavailable",
            details={
                "endpoint": endpoint,
                "runtime_target": "java_backend",
                "retry_after_seconds": round(max(0.0, remaining), 1),
                "hint": (
                    "Chart-side techniques (西占 chart 族/推运/三式 ken/神数/地占/塔罗) still work. Java-side ones "
                    "(nongli/bazi/ziwei/liureng and 占时 casts) fail fast until the backend recovers; it is retried "
                    "automatically after the cooldown (HOROSA_RUNTIME_JAVA_RETRY_COOLDOWN_SECONDS, default 120s). "
                    "Run `horosa-skill doctor` for the captured Java boot error."
                ),
                "next_action": "run_doctor_or_retry_after_cooldown",
            },
        )

    @staticmethod
    def _runtime_call_wait_seconds() -> float:
        """一次工具调用**最多**为「等 runtime 起来」阻塞多久（秒）。

        🔴 旧行为是一直等到启动器自己超时（runtime_start_timeout_seconds，首次运行含解压 + CDS
        训练，实测 300–900 秒），全都发生在**一次 MCP 请求内部**。Codex 的 tool_timeout_sec 默认
        60 秒，其它客户端各有默认 —— 用户看到的是「工具超时/无响应」，而 runtime 其实正常启动中。
        默认 5 秒：够覆盖「已经起好了、只是探针慢一拍」，不够的场合改回 runtime.starting 让调用方重试。
        """
        raw = os.environ.get("HOROSA_RUNTIME_CALL_WAIT_SECONDS", "5").strip()
        try:
            value = float(raw)
        except ValueError:
            return 5.0
        return max(0.0, value)

    @staticmethod
    def _runtime_starting_error(endpoint: str, started: dict[str, Any]) -> ToolTransportError:
        retry_after = started.get("retry_after_seconds") or 5
        return ToolTransportError(
            "本机 Horosa runtime 正在启动，尚未就绪。",
            code="runtime.starting",
            details={
                "endpoint": endpoint,
                "retry_after_seconds": retry_after,
                "elapsed_seconds": started.get("elapsed_seconds"),
                "budget_seconds": started.get("budget_seconds"),
                "cap_seconds": started.get("cap_seconds"),
                "first_start": started.get("first_start"),
                "launcher_log": started.get("launcher_log"),
                "next_action": (
                    f"等 {retry_after} 秒后重试**同一个调用**（参数不用改）。"
                    "连续三次仍是 starting 就跑 `horosa-skill runtime status` 看启动器日志。"
                ),
            },
        )

    def _call_remote(self, endpoint: str, payload: dict[str, Any], *, backend: str | None = None) -> dict[str, Any]:
        # backend="java"：同名路由两端都有、而本次要的是 Java 聚合层的附加字段时显式指定（例：/jieqi/year 的
        # Java 层给 jieqi24 逐节气补 bazi.fourColumns，Python 端无此字段——上游页面的种子请求走的就是 Java）。
        if backend not in (None, "java"):
            raise ValueError(bilingual(f"未知的后端覆写：{backend!r}", f"unknown backend override: {backend!r}"))
        use_chart_server = endpoint in _PYTHON_CHART_ENDPOINTS and backend != "java"
        client = self.chart_client if use_chart_server else self.client
        # /healthz（批 I-6）：chart 服务的真就绪探针（ok/warm）；老 runtime 无此路由时 404 仍算「服务在」。
        probe_endpoint = "/healthz" if use_chart_server else "/common/time"
        runtime_ready = self._chart_runtime_ready if use_chart_server else self._java_runtime_ready
        if not runtime_ready and not client.probe(probe_endpoint):
            # 分后端就绪（v0.36.0 A5）：Java 在冷却期内快速失败，不触发会先杀健康 chart 服务的全量重启；
            # chart 端点不受 Java 状态影响。
            if not use_chart_server:
                remaining = self._java_cooldown_remaining()
                if remaining > 0:
                    raise self._java_unavailable_error(endpoint, remaining)
            started = self.runtime_manager.start_local_services(
                wait_seconds=self._runtime_call_wait_seconds()
            )
            if isinstance(started, dict) and started.get("starting"):
                raise self._runtime_starting_error(endpoint, started)
            if not use_chart_server and isinstance(started, dict) and started.get("degraded"):
                raise self._java_unavailable_error(endpoint, self._java_cooldown_remaining())
        remote_endpoint = _chart_server_endpoint(endpoint) if use_chart_server else endpoint
        connection_retry_used = False
        data: dict[str, Any] | None = None
        while True:
            candidate_payloads = _java_chart_payload_candidates(endpoint, payload)
            param_errors: list[tuple[dict[str, Any], ToolTransportError]] = []
            # 🔴 「调用成功」必须单独记：后端合法地回 JSON `null`（玄史 get_figure 等查无此 slug 即回 null）时
            # data 仍是 None——旧循环拿 `data is not None` 当成功判据，于是对 null 无限重发、每轮新建 TLS 上下文，
            # 进程 100% CPU 挂死并持续打后端（sync311 F13 实测：旧映射下 figure 恒发错键 → 恒 null → 恒挂）。
            call_succeeded = False
            for remote_payload in candidate_payloads:
                try:
                    data = client.call(remote_endpoint, remote_payload)
                    call_succeeded = True
                    break
                except ToolTransportError as exc:
                    body = str(exc.details.get("body", ""))
                    is_param_error = exc.code == "tool.backend_param_error" or (
                        exc.code == "transport.http_error" and "200001" in body and "param error" in body
                    )
                    if not is_param_error:
                        if exc.code == "transport.connection_error" and not connection_retry_used:
                            connection_retry_used = True
                            if not use_chart_server and self._java_cooldown_remaining() > 0:
                                raise self._java_unavailable_error(endpoint, self._java_cooldown_remaining()) from exc
                            restarted = self.runtime_manager.start_local_services(
                                wait_seconds=self._runtime_call_wait_seconds()
                            )
                            if isinstance(restarted, dict) and restarted.get("starting"):
                                raise self._runtime_starting_error(endpoint, restarted) from exc
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
            if call_succeeded:
                break
            continue
        if use_chart_server:
            self._chart_runtime_ready = True
        else:
            self._java_runtime_ready = True
        unwrapped = self._unwrap_result(data)
        if not isinstance(unwrapped, dict):
            # 玄史检索端点（/xuanshi/search、/xuanshi/timeline 等）按 jsonpickle 直吐**裸数组**——
            # 对这族端点数组是合法形状，包一层交给调用方；其余端点维持 dict 硬约束（形状漂移要炸出来）。
            if endpoint.startswith("/xuanshi/") and isinstance(unwrapped, list):
                return {"items": unwrapped}
            # 详情端点查无此条（slug/id 不存在）回 JSON null：是合法的「零命中」，不是形状漂移。
            if endpoint.startswith("/xuanshi/") and unwrapped is None:
                return {"items": [], "total": 0}
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

    def _apply_upstream_predictive_defaults(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        """F19：远端星运工具缺目标时刻/返照地时按上游缺省补齐（写回 input_normalized，回显即实算口径）。

        上游 utils/aiAnalysisContext.js:2673-2760 buildPredictivePeriodSnapshot：
        - solarreturn/lunarreturn/givenyear：datetime 缺省 = 「今年生日时刻」（当年 + 出生月日 + 出生时分，
          [挂载自检 F-17]）；dirLat/dirLon 缺省本命经纬（lunarreturn/givenyear 后端**必读** dirLat/dirLon，
          缺了直接 param error）；
        - profection/solararc：datetime 缺省 = 此刻（`new DateTime()` 钟面，+08:00）；
        - 五法 dirZone 缺省本命时区。
        pdchart（aiAnalysisContext.js:2515-2531 pdCurrentDateTime）：缺省 = 主限表首条应期日期（UTC 墙钟 +
        dirZone '+00:00'），无行则出生次日。旧实现一概不补：solarreturn/profection/solararc 无 datetime 时后端回
        90 年**列表**（skill 当 invalid_result_shape 报错），lunarreturn/givenyear/pdchart 直接 param error。
        """
        if tool_name == "zr":
            return self._apply_zr_base_point(payload)
        if tool_name in ("pd", "pdchart"):
            # F20：词表 = 上游 SUPPORTED_PD_METHODS（13）/ SUPPORTED_PD_TIME_KEYS（26）。后端对白名单外静默回退
            # core_alchabitius / Ptolemy——认不出就报错，不让「传了 X 实算 Alchabitius」无声发生。
            if payload.get("pdMethod") is not None:
                _require_option(payload["pdMethod"], tuple(_PD_METHOD_LABELS), field="pdMethod", tool=tool_name)
            if payload.get("pdTimeKey") is not None:
                _require_option(payload["pdTimeKey"], tuple(_PD_TIME_KEY_LABELS), field="pdTimeKey", tool=tool_name)
            if tool_name == "pd":
                return payload
        if tool_name not in _PERIOD_PREDICTIVE_TOOLS and tool_name != "pdchart":
            return payload
        if tool_name == "profection":
            # [Q-105] profGrain/profStart 只喂 [小限摘要] 文本（纯前端派生），值域 = profectionSummary.js:13-24。
            if payload.get("profGrain") is not None:
                _require_option(payload["profGrain"], tuple(_ptext.PROFECTION_GRAIN_CN), field="profGrain", tool="profection")
            if payload.get("profStart") is not None:
                _require_option(payload["profStart"], tuple(_ptext.PROFECTION_START_CN), field="profStart", tool="profection")
        effective = dict(payload)
        if tool_name in _PERIOD_PREDICTIVE_TOOLS:
            if not effective.get("datetime"):
                now = _upstream_now_wall_clock()
                date_text = f"{payload.get('date') or ''}"
                if tool_name in _RETURN_PREDICTIVE_TOOLS and len(date_text) >= 10:
                    time_text = f"{payload.get('time') or '12:00:00'}"
                    effective["datetime"] = f"{now.strftime('%Y')}{date_text[4:].replace('/', '-')} {time_text[:5]}"
                else:
                    effective["datetime"] = now.strftime("%Y-%m-%d %H:%M")
            if not effective.get("dirZone"):
                effective["dirZone"] = payload.get("zone")
            if tool_name in _RETURN_PREDICTIVE_TOOLS:
                if not effective.get("dirLat"):
                    effective["dirLat"] = payload.get("lat")
                if not effective.get("dirLon"):
                    effective["dirLon"] = payload.get("lon")
        elif not effective.get("datetime"):
            effective["datetime"], effective["dirZone"] = self._pdchart_default_datetime(payload)
        return effective

    def _apply_zr_base_point(self, payload: dict[str, Any]) -> dict[str, Any]:
        """F8：黄道星释基点 → startSign（上游 AstroZR.js:354-385 buildZodialReleaseSnapshotText）。

        福点 = 不传 startSign（后端按福点所在座起）；基点本身是星座 → 直接用；其余（六希腊点/四轴）取本命盘上
        该点所在座。显式 startSign 优先（本仓旧参数，语义 = 以星座为基点）。认不出的 basePoint/aiMode 报结构化错误，
        取不到基点位置也报错（上游此时静默回落福点而段头仍写所选基点 = 标签与算法不符）。
        """
        base_point = payload.get("basePoint")
        ai_mode = payload.get("aiMode")
        if base_point is not None:
            _require_option(base_point, _ZR_BASE_POINTS, field="basePoint", tool="zr")
        if ai_mode is not None:
            _require_option(ai_mode, tuple(_ZR_AI_MODES), field="aiMode", tool="zr")
        for field in ("aiL1Idx", "aiL2Idx", "aiL3Idx"):
            value = payload.get(field)
            if value is not None and (_finite_number(value) is None or _finite_number(value) < 0):
                raise ToolValidationError(
                    f"zr 的 {field}={value!r} 须为 ≥0 的整数 / {field} must be a non-negative integer.",
                    code="tool.predictive_invalid_option",
                    details={"tool": "zr", "field": field, "value": value},
                )
        if not base_point or base_point == "Pars Fortuna" or payload.get("startSign"):
            return payload
        effective = dict(payload)
        if base_point in _ptext.LIST_SIGNS:
            effective["startSign"] = base_point
            return effective
        natal_payload = {**payload, "predictive": 0}
        for key in ("datetime", "dirZone", "dirLat", "dirLon", "startSign", "stopLevelIdx"):
            natal_payload.pop(key, None)
        natal = self._call_remote("/chart", natal_payload)
        obj = _get_chart_object(natal, base_point) if isinstance(natal, dict) else None
        sign = obj.get("sign") if isinstance(obj, dict) else None
        if sign not in _ptext.LIST_SIGNS:
            raise ToolValidationError(
                f"zr 基点 {base_point} 在本命盘上取不到所在星座 / base point {base_point} not found on the natal chart.",
                code="tool.zr_invalid_base_point",
                details={"basePoint": base_point},
            )
        effective["startSign"] = sign
        return effective

    def _pdchart_default_datetime(self, payload: dict[str, Any]) -> tuple[str, str]:
        """上游 AstroPrimaryDirectionChart.js:454 defaultPdChartDateTime：首条（过滤后）主限行的「日期」列，
        按 UTC 墙钟解释（dirZone='+00:00'）；取不到行 → 出生次日同一墙钟挂 +00:00。"""
        chart_payload = {**payload, "predictive": 1, "includePrimaryDirection": 1}
        for key in ("datetime", "dirZone", "dirLat", "dirLon"):
            chart_payload.pop(key, None)
        rows: Any = []
        params: dict[str, Any] = {}
        try:
            chart = self._call_remote("/chart", chart_payload)
            predictives = chart.get("predictives") if isinstance(chart.get("predictives"), dict) else {}
            rows = predictives.get("primaryDirection") or []
            params = chart.get("params") if isinstance(chart.get("params"), dict) else {}
        except HorosaSkillError as exc:
            _degrade("pdchart default datetime: primary-direction table fetch failed, using birth+1d: %s", exc)
        pd_method = f"{payload.get('pdMethod') or params.get('pdMethod') or 'core_alchabitius'}"
        show_bounds = payload.get("showPdBounds") if payload.get("showPdBounds") is not None else params.get("showPdBounds")
        for row in _pd_display_rows(rows, pd_method, show_bounds):
            date_text = f"{row[4] if len(row) > 4 and row[4] else ''}".strip()
            if date_text:
                return date_text, _PD_DISPLAY_ZONE
        birth = _persian_birth_date(f"{payload.get('date') or ''} {payload.get('time') or ''}".strip())
        if birth is None:
            raise ToolValidationError(
                "pdchart 缺目标时刻且无法解析出生时刻 / pdchart needs a datetime (birth date/time unparseable).",
                code="tool.pdchart_invalid_datetime",
                details={"date": payload.get("date"), "time": payload.get("time")},
            )
        return (birth + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"), _PD_DISPLAY_ZONE

    def _attach_predictive_chart_context(self, tool_name: str, payload: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
        # planetaryarc 同属「本命 ↔ 时段两盘对照」形态（上游 preset 也列 [本命盘配置]/[时段盘配置]/[相位]），
        # 但 /predict/planetaryarc 只回时段盘 → 同样需要补拉本命盘。
        if tool_name not in {"solarreturn", "lunarreturn", "solararc", "givenyear", "profection", "pd", "pdchart", "zr", "planetaryarc", "vedicprog", "jaynesprog"}:
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
            # 辅助本命盘 fetch 失败不得清空已算好的推运结果 → 与其余 _attach_* 一致的优雅降级。
            try:
                enriched["natalChart"] = self._call_remote("/chart", natal_payload)
            except HorosaSkillError as exc:
                _degrade("predictive natal chart fetch failed (tool=%s): %s", tool_name, exc)
        return enriched

    # [寿命格局] 取主法（上游 AstroLifespan.js:14-18 METHODS）。
    _LIFESPAN_METHODS = ("ptolemy", "alcabitius", "dorotheus")

    def _attach_natal_extras(
        self, tool_name: str, response_data: dict[str, Any], payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        # v2.4.0 西占: enrich the astrochart (and mundane) export with 12分度 / 主宰星链 / 寿命格局.
        # These are computed by the vendored JS astroextra formatter (Ptolemy hyleg engine) from the
        # chart object. Only `chart` (astrochart) and `mundane` carry them in 星阙; never fail the
        # chart if the enrichment errors.
        # 上游 v50 给整个 chart 家族（含 13 宫/希腊化/衍生盘）都出 12分度/主宰星链/寿命格局，
        # 不只本命与世俗盘——门控放开到 astrochart_like 家族，段随之进导出。
        if tool_name not in {"chart", "mundane", "chart13", "chart12", "hellen_chart", "harmonic", "draconic", "relocation"}:
            return response_data
        if not isinstance(response_data, dict) or not _is_astro_chart_payload(response_data):
            return response_data
        sections: dict[str, str] = {}
        # F15：取主法随调用方（上游读 localStorage horosa.lifespan.method，缺省 ptolemy）；太阳三态阈值由 JS 侧从
        # 本盘 params 回显读取（cazimiOrb/combustOrb/underBeamsOrb，上游 astroAiSnapshot.js:1127-1132 同源）。
        lifespan_method = (payload or {}).get("lifespanMethod")
        if lifespan_method is not None:
            _require_option(lifespan_method, self._LIFESPAN_METHODS, field="lifespanMethod", tool=tool_name)
        options = {"lifespanMethod": lifespan_method} if lifespan_method else {}
        try:
            js = self.js_client.run("astroextra", {"chart": response_data, "options": options})
            extras_data = js.get("data") if isinstance(js, dict) else None
            if isinstance(extras_data, dict):
                sections = _build_natal_extra_sections(extras_data)
        except Exception as exc:  # noqa: BLE001 — 富化失败不许影响主盘；此前裸 pass 连日志都没有
            _degrade("astro natal extras (12分度/主宰星链/寿命格局) build failed: %s", exc)
        # 恒挂（JS 失败时为空 dict）：它同时是「本盘属西占 chart 家族」的标记——[主宰星链] 尾部的整宫制宫主表与
        # [分宫制宫神星表]（v57，astro_rulers.py 纯 Python 单源）在快照构建时据此照出，不随 JS 富化成败丢失。
        enriched = dict(response_data)
        enriched["_natalExtras"] = sections
        return enriched

    # [古典·显赫计分] 主宰光体判定项（上游 astroAiSnapshot.js:1716-1726 predOpts）：四键读全局仓（headless = 请求顶层），
    # 界系/双子界序/自定义界表随盘 fields。
    _EMINENCE_KEYS = (
        "busyPlaces", "dynamicalDivisions", "domicileMasterMethod", "rayWeighting",
        "termsVariant", "geminiBoundEmended", "customTermsDay", "customTermsNight",
    )

    def _attach_classical_derived(
        self, tool_name: str, response_data: dict[str, Any], payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """古典衍化四段（上游 v3.9.2）：仅本命 astrochart 挂载。

        上游 opt-in 语义（astroAiSnapshot.js:1550）：只有本命 astro 快照路径传 classicalDerived，
        germany/mundane/indiachart 等嵌套消费方缺省 falsy = 零输出——skill 同口径，只 gate `chart`。
        计算走 vendored `astroClassicalDerived.js`（与上游四组件同引），JS 失败优雅降级不产段
        （条件段双登记，缺席不算漏）。
        """
        if tool_name != "chart":
            return response_data
        if not isinstance(response_data, dict) or not _is_astro_chart_payload(response_data):
            return response_data
        eminence = {k: (payload or {})[k] for k in self._EMINENCE_KEYS if (payload or {}).get(k) not in (None, "")}
        try:
            js = self.js_client.run("classical_derived", {"chart": response_data, "eminence": eminence})
            invalid = js.get("invalid") if isinstance(js, dict) else None
            if invalid:
                parts = [f"{i.get('key')}={i.get('value')!r}（可选：{'/'.join(str(a) for a in (i.get('allowed') or []))}）" for i in invalid if isinstance(i, dict)]
                raise ToolValidationError(
                    bilingual(f"显赫计分口径取值无效：{'；'.join(parts)}。", f"eminence setting(s) invalid: {'; '.join(parts)}."),
                    code="tool.chart_invalid_setting",
                    details={"invalid": invalid},
                )
            text = js.get("snapshot_text") if isinstance(js, dict) else ""
            if isinstance(text, str) and text.strip():
                sections: dict[str, str] = {}
                for block in text.split("\n\n"):
                    lines = block.strip().splitlines()
                    if lines and lines[0].startswith("[") and lines[0].endswith("]"):
                        sections[lines[0][1:-1]] = "\n".join(lines[1:]).strip()
                if sections:
                    enriched = dict(response_data)
                    enriched["_classicalDerived"] = sections
                    return enriched
        except ToolValidationError:
            raise
        except Exception as exc:  # noqa: BLE001 - enrichment must never fail the chart, but say so
            _degrade("classical derived sections failed: %s", exc)
        return response_data

    def _attach_jyotish_sections(
        self, tool_name: str, response_data: dict[str, Any], payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """印占 Jyotish 派生段 (星阙 v3.6.0 印占大扩容)。

        后端 `/india/chart` 本就返回整棵 `jyotish` 树（panchanga / jaimini / kp / shadbala / dasha /
        ashtakavarga … 30 个子树），星阙前端用一个纯格式化函数把它铺成 50+ 个具名段——skill 此前只登记
        了 11 段，其余全被丢弃。这里复用逐字 vendor 的同一个 builder（`horosa-core-js` 的
        `india_jyotish` 工具），保持与桌面端逐字同源。与其他 `_attach_*` 同款：gated + 优雅降级，
        任何失败都只是这些段不出，绝不带崩排盘本身。
        """
        if tool_name != "india_chart":
            return response_data
        if not isinstance(response_data, dict) or not response_data.get("jyotish"):
            return response_data
        src = payload or {}
        # [大运Dasha] 体系 + [起盘信息] 流派头行的页面口径（上游 fields：indiaDashaSystem / indiaSchool /
        # indiaDashaVariants + 出生时刻供扩展大运推日期）。
        params = {
            "dashaSystem": src.get("dashaSystem"),
            "indiaSchool": src.get("indiaSchool"),
            "dashaVariants": src.get("dashaVariants"),
            "date": src.get("date"),
            "time": src.get("time"),
            "ad": src.get("ad", 1),
        }
        try:
            # js_client 已解包 envelope 的 data，返回的就是 runner 的结果对象。
            js = self.js_client.run("india_jyotish", {"chart": response_data, "params": params})
            invalid = js.get("invalid") if isinstance(js, dict) else None
            if invalid:
                parts = [f"{i.get('key')}={i.get('value')!r}（可选：{'/'.join(i.get('allowed') or [])}）" for i in invalid if isinstance(i, dict)]
                raise ToolValidationError(
                    bilingual(f"印度律盘设置取值无效：{'；'.join(parts)}。", f"india_chart setting(s) invalid: {'; '.join(parts)}."),
                    code="tool.india_chart_invalid_setting",
                    details={"invalid": invalid},
                )
            if isinstance(js, dict):
                enriched = dict(response_data)
                sections = js.get("sections")
                if isinstance(sections, dict) and sections:
                    enriched["_jyotishSections"] = sections
                if isinstance(js.get("dashaLines"), list):
                    enriched["_indiaDashaLines"] = js.get("dashaLines")
                if isinstance(js.get("schoolLines"), list):
                    enriched["_indiaSchoolLines"] = js.get("schoolLines")
                return enriched
        except ToolValidationError:
            raise
        except Exception as exc:  # noqa: BLE001 — 富化失败不许影响主盘
            _degrade(
                "jyotish section build failed: %s", exc,
                note="印度律盘 Jyotish 派生段、[大运Dasha] 与 [起盘信息] 流派行本次未产出（JS 段 builder 失败），其余段不受影响。",
            )
        return response_data

    def _attach_india_extra_vargas(
        self, tool_name: str, payload: dict[str, Any], response_data: dict[str, Any]
    ) -> dict[str, Any]:
        """[附加分盘]（上游 v3.11.0 #80，IndiaChart.js:1219-1333 buildIndiaSnapshotForFields 的 extraVargas 分支）。

        主盘之外再挂几张分盘（如婚姻 D9 + 子女 D7），每张只出「宫位宫头 + 星与虚点 + 行星」简表（整张分盘快照约
        2.6 万字，N 张全出会把预算吃穿）。归一（值域/去重/上限 4）后剔掉主盘自身（planIndiaExtraVargas），逐张另取
        /india/chart?chartnum=N（上游 fetchIndiaVargaBriefLines 同路），段内小标题 `── D9 婚姻 ──`。缺省不选 = 不发请求、不加段。
        """
        if tool_name != "india_chart" or not isinstance(response_data, dict):
            return response_data
        raw = payload.get("indiaExtraVargas")
        if raw in (None, "", [], ()):
            return response_data
        wanted, dropped = _normalize_india_extra_vargas(raw)
        if dropped:
            _degrade(
                "india extra vargas dropped invalid entries: %s", dropped,
                note=(
                    f"印度盘 [附加分盘]：已忽略无效/重复/超上限的分盘 {dropped}"
                    f"（可选 {'/'.join(str(n) for n, _ in _INDIA_MOUNT_VARGA_OPTIONS if n > 1)}，最多 {_INDIA_MOUNT_EXTRA_VARGA_MAX} 张）。"
                ),
            )
        try:
            main = int(payload.get("chartnum") or 1)
        except (TypeError, ValueError):
            main = 1
        main = main if main > 0 else 1
        extras = [n for n in wanted if n != main]
        if not extras:
            return response_data
        base_remote = {
            k: v for k, v in _india_chart_remote_payload(payload).items() if k not in ("chartnum", "tripataki")
        }
        extra_lines: list[str] = []
        for chartnum in extras:
            try:
                varga = self._call_remote("/india/chart", {**base_remote, "chartnum": chartnum})
            except Exception as exc:  # noqa: BLE001 — 单张附加分盘失败不许带崩主盘
                _degrade(
                    "india extra varga D%s fetch failed: %s", chartnum, exc,
                    note=f"印度盘 [附加分盘] D{chartnum} 本次未能取到（其余分盘与主盘不受影响）。",
                )
                continue
            if not isinstance(varga, dict) or not _is_astro_chart_payload(varga):
                _degrade(
                    "india extra varga D%s returned no chart", chartnum,
                    note=f"印度盘 [附加分盘] D{chartnum} 后端未返回盘面，已跳过。",
                )
                continue
            # 上游 pickIndiaVargaBriefLines：只挑该分盘自己的 宫位宫头 + 星与虚点 + 行星 三段正文（trimEnd + 去空行）。
            body = [
                line.rstrip()
                for block in (
                    _build_house_cusp_lines(varga),
                    _build_star_and_lot_position_lines(varga),
                    _build_planet_section(varga),
                )
                for line in "\n".join(f"{item}" for item in (block or [])).split("\n")
                if line.strip()
            ]
            if body:
                extra_lines.append(f"── {_india_mount_varga_label(chartnum)} ──")
                extra_lines.extend(body)
        if not extra_lines:
            return response_data
        enriched = dict(response_data)
        # 上游 ensureSection：首行说明 + 各张简表（ensureSection 会滤掉空行，故各张之间无空行）。
        enriched["_indiaExtraVargas"] = "\n".join(
            ["以下为主盘之外另挂的分盘,只列该分盘的宫头与星曜落宫(大运/瑜伽/相位等仍以主盘段为准)。", *extra_lines]
        )
        return enriched

    # 古典格局派生分析 (星阙 v2.6.7): astrochart/astrochart_like 的 [古典格局] 段来自 /astroextra/analysis
    # (护卫/优势相位/相位动态/逐题主星/偶然尊贵/恒星/行星时/埃及历/巴比伦/格局/分布/气质/almutem/吉化-extraLots)。
    # 与前端同源:按需 fetch、优雅降级(失败→不挂载→该段不出)。[古典](逐曜状态/围攻/围绕)直接读 /chart 响应,无需此 fetch。
    # 调波盘同属上游 ASTRO_LIKE_EXPORT_KEYS 族，盘面形状与本命盘一致 → 同样吃得下派生分析。
    # （上游把 harmonic 放在 skipClassical 名单里是 UI 侧的性能取舍，headless 无此顾虑，多出的
    # [古典格局] 是 skill 相对上游的 extra，不是漂移。）
    # mundane 也纳入：它已走 `_build_astro_snapshot_text`，开门控即得 [埃及历]。但**不要**因此
    # 给 mundane 登记 [古典格局]——世俗盘无该段是既定结论（docs/LESSONS.md）。
    _CLASSICAL_ANALYSIS_TOOLS = {"chart", "chart13", "chart12", "hellen_chart", "harmonic", "mundane", "draconic", "relocation"}

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
                    # 缓存代次盐，与上游 aiExport.js / AstroHelper.java 同值：后端 paramhash 磁盘缓存不区分
                    # 「古典口径进入临界区之前/之后」算出的结果，不带盐的请求会命中旧代次的缓存条目。
                    "_v": "cls1",
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
                    # [M-1][Q-340/T-321]（上游 aiExport.js:6742 fixedStarOrbParamsFor）：恒星轨随盘（此前硬编 1°，
                    # 用户给了 starOrb/starOrbMode 时 [古典格局] 的恒星命中与主盘口径分叉）。
                    **_fixed_star_orb_params(payload),
                },
            )
            if isinstance(analysis, dict) and analysis:
                enriched = dict(response_data)
                enriched["_classicalAnalysis"] = analysis
                enriched["_egyptSection"] = self._build_egypt_section(enriched, analysis, payload)
                return enriched
        except ToolValidationError:
            raise
        except Exception as exc:
            _degrade("classical /astroextra/analysis failed (tool=%s): %s", tool_name, exc)
        return response_data

    # 埃及历七轴（上游随盘键 egypt_<axis>，egyptianSchools.EGYPT_RECORD_KEYS；挂载齿轮 techniqueMountSettings.js:965-980）。
    _EGYPT_AXIS_KEYS = (
        "egypt_decanRuler", "egypt_decanAnchor", "egypt_decanNaming", "egypt_starClock",
        "egypt_calendarAnchor", "egypt_petosirisMod", "egypt_godEdition",
    )

    def _build_egypt_section(self, chart: dict[str, Any], analysis: dict[str, Any], payload: dict[str, Any] | None = None) -> str:
        """[埃及历] 独立段：各点落旬 / 上升旬详情 / 埃及民用历 + Sothic。

        上游把埃及历**同时**写在两处：`古典格局` 段里一行摘要（天狼偕日升/岁年/上升旬），以及这个
        逐点铺开的独立段（`aiExport.js` 的 preset 里 astrochart 与 5 个衍生盘键都列了它）。两处并存
        是上游原样，不是重复——摘要给概览、独立段给逐点明细，故这里也保持双份。

        天狼偕日升由后端算（`astroextra.compute_egyptian_calendar`），JS 只回显与对差，所以要把
        analysis 的 `egyptianCalendar` 并进盘对象再交给 vendored builder。失败只是本段不出。
        """
        try:
            chart_obj = dict(chart)
            chart_obj["egyptianCalendar"] = analysis.get("egyptianCalendar")
            # 流派口径：随盘键 egypt_* → egyptSchoolFromFields（上游 astroAiSnapshot.js:1733 优先读 fields，缺键回全局=默认档）。
            egypt_fields = {k: {"value": (payload or {})[k]} for k in self._EGYPT_AXIS_KEYS if (payload or {}).get(k) not in (None, "")}
            js = self.js_client.run("egypt_section", {"chart": chart_obj, "fields": egypt_fields})
            invalid = js.get("invalid") if isinstance(js, dict) else None
            if invalid:
                parts = [f"{i.get('key')}={i.get('value')!r}（可选：{'/'.join(str(a) for a in (i.get('allowed') or []))}）" for i in invalid if isinstance(i, dict)]
                raise ToolValidationError(
                    bilingual(f"埃及历流派口径取值无效：{'；'.join(parts)}。", f"egypt school setting(s) invalid: {'; '.join(parts)}."),
                    code="tool.egypt_invalid_setting",
                    details={"invalid": invalid},
                )
            text = js.get("text") if isinstance(js, dict) else None
            return f"{text}".strip() if text else ""
        except ToolValidationError:
            raise
        except Exception as exc:  # noqa: BLE001 — 富化失败不许影响主盘
            _degrade("egypt section build failed: %s", exc)
            return ""

    def _attach_relative_score(
        self, tool_name: str, input_normalized: dict[str, Any], response_data: dict[str, Any]
    ) -> dict[str, Any]:
        # 合盘关系量化：/modern/relative 出比较盘后，另调 /astroextra/relative 取契合分数 +
        # 顺畅/张力连接（同 inner/outer），挂到 _relativeScore 供 [关系量化]/[顺畅连接]/[张力连接] 段。
        # 打分失败不阻塞既有比较盘段（优雅降级）。
        if tool_name != "relative" or not isinstance(response_data, dict):
            return response_data
        inner = input_normalized.get("inner")
        outer = input_normalized.get("outer")
        if not isinstance(inner, dict) or not isinstance(outer, dict):
            return response_data
        try:
            score = self._call_remote(
                "/astroextra/relative",
                {
                    "inner": inner,
                    "outer": outer,
                    "hsys": input_normalized.get("hsys", 0),
                    "zodiacal": input_normalized.get("zodiacal", 0),
                },
            )
        except Exception as exc:  # noqa: BLE001 - degrade to no-score, keep comparison chart
            _degrade("relative score failed: %s", exc)
            return response_data
        if isinstance(score, dict) and score.get("score") is not None:
            enriched = dict(response_data)
            # 只留渲染三段所需字段，剥离 raw（整份 ChartComp）避免臃肿 envelope.data。
            enriched["_relativeScore"] = {
                "score": score.get("score"),
                "highlights": score.get("highlights"),
                "challenges": score.get("challenges"),
            }
            return enriched
        return response_data

    def _enrich_embedded_astro_chart(self, chart_wrap: dict[str, Any]) -> dict[str, Any]:
        """嵌入整盘（relative 比较盘 A/B、jieqi 分至盘）的富化 = 上游 buildAstroSnapshotContent 对任意盘本地算的几段：
        12分度 / 主宰星链链行 / 寿命格局（JS astroextra）+ 埃及历（JS egypt_section；无 /astroextra/analysis 的
        天狼偕日升，与上游嵌入盘同——那一行只在主盘拉了 analysis 时才有）。失败只是对应段不出（`_degrade` 进 warnings），
        [主宰星链] 尾部整宫制宫主表与 [分宫制宫神星表] 是纯 Python，照出。
        """
        if not isinstance(chart_wrap, dict) or not _is_astro_chart_payload(chart_wrap):
            return chart_wrap
        enriched = self._attach_natal_extras("chart", chart_wrap)
        egypt = self._build_egypt_section(enriched, {})
        if egypt:
            enriched = dict(enriched)
            enriched["_egyptSection"] = egypt
        return enriched

    def _attach_relative_comp_charts(self, tool_name: str, input_normalized: dict[str, Any], response_data: dict[str, Any]) -> dict[str, Any]:
        """比较盘（relative=0）的 inner/outer 两盘富化，供 [比较盘-星盘A]/[比较盘-星盘B] 无头整盘（上游 Q-441/T-404）。"""
        if tool_name != "relative" or not isinstance(response_data, dict):
            return response_data
        if f"{input_normalized.get('relative', 0)}" != "0":
            return response_data
        enriched = response_data
        for key in ("inner", "outer"):
            chart = response_data.get(key)
            if isinstance(chart, dict) and _is_astro_chart_payload(chart):
                if enriched is response_data:
                    enriched = dict(response_data)
                enriched[key] = self._enrich_embedded_astro_chart(chart)
        return enriched

    # 上游页面种子请求的参数面（JieQiChartsMain.genParams(false) → Java JieQiController.getYearParams 白名单）：
    # 不带 jieqis（= 全年 24 节气）、不带 seedOnly（= 走 setupBazi 逐节气补四柱）。
    _JIEQI_SEED_DROP_KEYS = frozenset({"jieqis", "seedOnly"})

    def _attach_jieqi_year_extras(self, tool_name: str, input_normalized: dict[str, Any], response_data: dict[str, Any]) -> dict[str, Any]:
        """jieqi_year 的两项富化（上游 v3.11 整年快照）：

        ① [二十四节气]：全年 24 节气交节时刻 + 四柱。上游页面的种子请求打的是 **Java** `/jieqi/year`（无 jieqis），
           Java 层 `JieQiController.setupBazi` 给每个节气补 `bazi.fourColumns`；本仓工具主调用走 Python 同名路由
           （只回所请求的分至四项、无四柱），故另发一次 Java 种子请求。Java 不可用 → 本段不出 + warnings（条件段双登记）。
        ② 分至盘嵌入整盘的 JS 富化（12分度/主宰星链链行/寿命格局/埃及历，见 `_enrich_embedded_astro_chart`）。
        """
        if tool_name != "jieqi_year" or not isinstance(response_data, dict):
            return response_data
        enriched = dict(response_data)
        seed_payload = {key: value for key, value in input_normalized.items() if key not in self._JIEQI_SEED_DROP_KEYS and value is not None}
        seed_payload.setdefault("timeAlg", 0)   # preciseCalcBridge.normalizeJieqiParams：timeAlg 缺省 0（真太阳时）
        try:
            seed = self._call_remote("/jieqi/year", seed_payload, backend="java")
            rows = seed.get("jieqi24") if isinstance(seed, dict) else None
            if isinstance(rows, list) and rows:
                enriched["_jieqi24Seed"] = [_compact_jieqi_seed_row(row) for row in rows if isinstance(row, dict)]
            else:
                _degrade("jieqi_year [二十四节气] seed (Java /jieqi/year) returned no jieqi24 rows")
        except Exception as exc:  # noqa: BLE001 — 种子段失败不许带崩分至四盘
            _degrade("jieqi_year [二十四节气] seed (Java /jieqi/year) failed: %s", exc)
        charts = response_data.get("charts")
        if isinstance(charts, dict):
            charts = self._jieqi_sidereal_recharts(input_normalized, charts)
            enriched["charts"] = {
                title: self._enrich_embedded_astro_chart(chart) if isinstance(chart, dict) else chart
                for title, chart in charts.items()
            }
        return enriched

    def _jieqi_sidereal_recharts(self, input_normalized: dict[str, Any], charts: dict[str, Any]) -> dict[str, Any]:
        """F16：恒星黄道岁差逐节气重排（上游 JieQiChartsMain.js:524-553 loadJieqiChart → buildChartRequestParams）。

        上游的分至盘是逐节气一次 `/chart`（带 siderealAyanamsa）；本仓主调用走 Python `/jieqi/year`，它按
        YearJieQi.params（zone/lat/lon/hsys/zodiacal/doubingSu28）起 PerChart —— **不带岁差键**，于是恒星黄道盘
        一律是 swisseph 缺省岁差。所以给了 siderealAyanamsa（且 zodiacal=1，PerChart 只在恒星黄道下读它）时，
        按交节时刻（charts[x].params.birth）逐盘重发 `/chart`。重排失败 → 该节气盘不出 + warnings
        （留着缺省岁差的盘冒充所选岁差，比缺段更糟）。
        """
        ayan = f"{input_normalized.get('siderealAyanamsa') or ''}".strip()
        if not ayan or f"{input_normalized.get('zodiacal', 0)}" not in ("1", "Sidereal"):
            return charts
        out: dict[str, Any] = {}
        for title, one in charts.items():
            params = one.get("params") if isinstance(one, dict) else None
            birth = f"{(params or {}).get('birth') or ''}".strip()
            date_text, _, time_text = birth.partition(" ")
            if not date_text or not time_text:
                _degrade("jieqi_year sidereal re-chart: %s has no birth time", title,
                         note=f"{title}盘缺交节时刻，无法按所选岁差 {ayan} 重排，该盘不出。")
                continue
            request = {
                "ad": input_normalized.get("ad", 1),
                "date": date_text, "time": time_text,
                "zone": input_normalized.get("zone"), "lat": input_normalized.get("lat"), "lon": input_normalized.get("lon"),
                "gpsLat": input_normalized.get("gpsLat"), "gpsLon": input_normalized.get("gpsLon"),
                "hsys": input_normalized.get("hsys", 0), "southchart": False,
                "zodiacal": 1, "siderealAyanamsa": ayan, "tradition": 0,
                "doubingSu28": input_normalized.get("doubingSu28", 0),
                "strongRecption": 0, "simpleAsp": 0, "virtualPointReceiveAsp": 0, "predictive": 0,
                "pdaspects": [0, 60, 90, 120, 180],
                **{k: input_normalized[k] for k in ("userAyanT0", "userAyanDeg") if input_normalized.get(k) is not None},
            }
            try:
                chart = self._call_remote("/chart", {k: v for k, v in request.items() if v is not None})
            except Exception as exc:  # noqa: BLE001 — 单盘失败不带崩其余节气
                _degrade("jieqi_year sidereal re-chart %s failed: %s", title, exc,
                         note=f"{title}盘按所选岁差 {ayan} 重排失败（{exc}），该盘不出，其余段不受影响。")
                continue
            if isinstance(chart, dict) and _is_astro_chart_payload(chart):
                out[title] = chart
            else:
                _degrade("jieqi_year sidereal re-chart %s returned no chart", title,
                         note=f"{title}盘按所选岁差 {ayan} 重排未返回盘面，该盘不出。")
        return out

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
        options = _qimen_effective_options(payload)
        time_alg = options.get("timeAlg", 0)
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
                    # 日界/晚子时开关与 ken 权威引擎同口径：仅显式给定时发送，缺省沿用后端默认(1/1)。
                    **_day_boundary_switches(options),
                    "timeAlg": time_alg,
                    "ad": payload.get("ad", 1),
                },
            )

        def _jieqi_year(target_year: int) -> Any:
            return self._call_remote(
                "/jieqi/year",
                {"year": target_year, "zone": payload["zone"], "lat": payload["lat"], "lon": payload["lon"], "time": payload["time"], "gpsLat": payload.get("gpsLat"), "gpsLon": payload.get("gpsLon"), "ad": payload.get("ad", 1), "timeAlg": time_alg},
            )

        prev_year = payload.get("jieqi_year_prev")
        if not isinstance(prev_year, dict):
            prev_year = _jieqi_year(year - 1)
        current_year = payload.get("jieqi_year_current")
        if not isinstance(current_year, dict):
            current_year = _jieqi_year(year)
        # 日家(2)/金函(6) 腊月过冬至需次年至日 → 种子年 y-1,y,y+1（上游 jieqiSeedYears，DunJiaCalc.js:1243）。
        next_year = None
        if _js_parse_int(options.get("paiPanType")) in (2, 6):
            next_year = payload.get("jieqi_year_next")
            if not isinstance(next_year, dict):
                next_year = _jieqi_year(year + 1)
        # 路由与上游 DunJiaMain.getResolvedPan 同判据（isQimenLocalRoute）：本地家/飞盘/混合/报数/七组本地口径 →
        # 本地 calcDunJia，**不打** ken（后端不认这些口径）；其余（时家/综合·转盘·全缺省口径）ken 是唯一算权。
        route_reasons = _qimen_local_route_reasons(options)
        ken_response = None
        if not route_reasons:
            ken_response = self._call_remote("/qimen/pan", _qimen_ken_payload(payload, options, nongli))
            self._require_ken_pan(ken_response, engine="kinqimen", endpoint="/qimen/pan")
        js_payload = {
            **{k: v for k, v in payload.items() if k not in ("ken_response", "kenResponse")},
            "options": options,
            "nongli": nongli,
            "jieqi_year_prev": prev_year,
            "jieqi_year_current": current_year,
            **({"jieqi_year_next": next_year} if isinstance(next_year, dict) else {}),
            **({"ken_response": ken_response} if ken_response is not None else {}),
        }
        fa_related_people = self._normalize_fa_related_people(payload)
        if fa_related_people is not None:
            js_payload["faRelatedPeople"] = fa_related_people
        js_result = self.js_client.run("qimen", js_payload)
        js_route = js_result.get("route") if isinstance(js_result, dict) else None
        if isinstance(js_route, dict) and bool(js_route.get("local")) != bool(route_reasons):
            raise ToolTransportError(
                "奇门路由判据漂移：Python 镜像与 vendored isQimenLocalRoute 结论不一致。",
                code="tool.qimen_route_check_failed",
                details={"python_local_reasons": route_reasons, "js_route": js_route, "options": options},
            )
        snapshot_text = js_result.get("snapshot_text")
        result: dict[str, Any] = {
            "pan": js_result.get("data", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="qimen", snapshot_text=snapshot_text),
            "prerequisites": {
                "nongli": nongli, "jieqi_year_prev": prev_year, "jieqi_year_current": current_year,
                **({"jieqi_year_next": next_year} if isinstance(next_year, dict) else {}),
            },
            "route": {"local": bool(route_reasons), "reasons": route_reasons},
        }
        if route_reasons:
            # 算源如实：本地路由的盘不带 pan.source，依据卡按 compute_sources 标注（technique_provenance 已声明该引擎）。
            result["compute_sources"] = {"pan": "local_route_calcDunJia"}
        return result

    # --- 天星择日 / 奇门择日（上游 v3.7.0 / v3.7.1）------------------------------------------

    def _require_electionscan_ok(self, result: Any, *, endpoint: str) -> dict[str, Any]:
        """Fail loudly when /electionscan/scan returned a failure envelope.

        Same family as `_require_ken_pan` (AGENTS §4「HTTP 200 也回失败信封，永不信状态码」):
        the endpoint wraps errors as ``{"ResultCode": -1, "Result": {"err": …, "detail": …}}``,
        and `_call_remote` only inspects a **top-level** `err`, so the unwrapped `{"err": …}` comes
        back with no exception. Without this guard a `span_too_large` / `invalid_conditions` would
        silently degrade into "zero hits" — a plausible-looking empty search that is actually a
        rejected request.
        """
        if isinstance(result, dict) and not result.get("err"):
            return result
        detail = result if not isinstance(result, dict) else {"err": result.get("err"), "detail": result.get("detail")}
        raise ToolTransportError(
            "Horosa 征象搜索端点未返回结果。",
            code="tool.electionscan_failed",
            details={
                "endpoint": endpoint,
                "scan_error": detail,
                "hint": (
                    "invalid_conditions=条件树不合法（叶子 params 见 agent_guidance）；"
                    "span_too_large=单次请求超 93 天（skill 已按月切分，出现即切分逻辑有误）。"
                ),
            },
        )

    @staticmethod
    def _tianxing_window(payload: dict[str, Any]) -> tuple[str, str, str, str]:
        start_date = str(payload.get("startDate") or payload.get("date") or "")
        end_date = str(payload.get("endDate") or start_date)
        return start_date, str(payload.get("startTime") or "00:00"), end_date, str(payload.get("endTime") or "23:59")

    def _tianxing_js(self, request: dict[str, Any], *, stage: str) -> dict[str, Any]:
        """跑 tianxing 的 JS 侧动作并**检查 data.ok**。

        🔴 tianxing.js 在 buildTianxingSnapshot 抛异常时返回 {data:{ok:false,…}, snapshot_text:''}。
        旧实现只读 snapshot_text → 拿到 None → _augment_export_payload 回落
        `format_source: "generated_template"`，产出一份拿 payload YAML 填出来的**伪造四段导出**，
        而 SKILL.md 要求 agent 只依据 export_snapshot.export_text 解读。stitch 那侧的 `or []`
        同理会把失败变成「零命中」——一个看起来完全合理的空结果。
        """
        result = self.js_client.run("tianxing", request)
        data = result.get("data") or {}
        if not data.get("ok"):
            error = data.get("error") or {}
            raise ToolTransportError(
                f"天星择日 JS 层 {stage} 失败：{error.get('message') or '未知错误'}",
                code=f"tool.tianxing_{error.get('code') or f'{stage}_failed'}",
                details={"stage": stage, "error": error},
            )
        return {**data, "snapshot_text": result.get("snapshot_text")}

    def _run_tianxing_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        start_date, start_time, end_date, end_time = self._tianxing_window(payload)
        if not start_date or not end_date:
            raise ToolValidationError(
                "天星择日需要搜索时间窗（startDate/endDate）。",
                code="tool.tianxing_missing_window",
                details={"startDate": start_date, "endDate": end_date},
            )
        conditions = payload.get("conditions")
        if not conditions:
            raise ToolValidationError(
                "天星择日需要征象条件树（conditions）。",
                code="tool.tianxing_missing_conditions",
                details={"hint": "条件类键与参数见本工具的 agent_guidance。"},
            )
        # Compile through the vendored table so validation messages come from the same source the
        # backend uses — never re-encode 32 condition schemas here (they go stale on every upstream add).
        compiled_result = self.js_client.run("tianxing", {"action": "compile", "tree": conditions})
        compiled_data = compiled_result.get("data") or {}
        if not compiled_data.get("ok"):
            error = compiled_data.get("error") or {}
            details: dict[str, Any] = {"error": error}
            # 自愈式报错：把**服务端实现集**（运行时孪生）一并带回，agent 不用猜哪些条件类键合法。
            # _call_remote 已剥 {ResultCode, Result} 信封 → 这里拿到的就是 {types, groups}。
            try:
                ct = self._call_remote("/electionscan/conditiontypes", {})
                if isinstance(ct, dict) and isinstance(ct.get("types"), list):
                    details["server_condition_types"] = ct.get("types")
            except Exception:  # noqa: BLE001 - 自省失败不该遮住原始校验错误
                pass
            raise ToolValidationError(
                f"征象条件树不合法：{error.get('message') or '未知错误'}",
                code="tool.tianxing_invalid_conditions",
                details=details,
            )
        compiled = compiled_data.get("compiled")

        # 窗口上限。每一段都是一次串行后端扫描，5 年窗口 = 60 次；而 splitByMonth 的 800 次 guard 一旦
        # 耗尽（约 66 年）会**不 push 最后一段**就退出——尾部被丢，结果却仍报成对整个窗口的完整搜索。
        # 绝不静默截断（AGENTS §5.9）。
        max_span = _clamped_max_span(payload, _TIANXING_MAX_SPAN_DAYS)
        _require_sane_window(start_date, end_date, max_span=max_span, tool="tianxing")

        cfg = {"startDate": start_date, "startTime": start_time, "endDate": end_date, "endTime": end_time}
        # The backend hard-caps ONE request at 93 days (election_scan.py MAX_SPAN_DAYS); upstream works
        # around it by month-splitting in the UI. §5「请求型 builder 一律归 Python」→ the loop lives here,
        # but the split/stitch arithmetic stays the vendored one so boundaries match 星阙 byte-for-byte.
        segments = self._tianxing_js(
            {"action": "split", "cfg": cfg}, stage="split"
        ).get("segments") or [cfg]
        base = {
            "zone": _electionscan_zone(payload.get("zone")),
            "ad": payload.get("ad", 1),
            "gpsLat": payload.get("gpsLat"),
            "gpsLon": payload.get("gpsLon"),
            "lat": payload.get("lat"),
            "lon": payload.get("lon"),
            "hsys": payload.get("hsys"),
            "zodiacal": payload.get("zodiacal"),
            # 恒星黄道口径：ScanContext 会读它，缺失就回落 Lahiri —— 而 [起盘信息] 段照样把用户给的值
            # 印出来，等于输出主动声称了一个没被使用的设置。
            "siderealAyanamsa": payload.get("siderealAyanamsa"),
            # schema 声明了 precision，之前全代码没人消费它（后端 election_scan.py:1994 恒取默认
            # 'minute'）。文档化了却什么都不做的旋钮比没有更糟——接上。
            "precision": payload.get("precision"),
            "conditions": compiled,
            # protocol salt: invalidates cached rows predating the pick/pickEnd fields (scanOrchestrator.js)
            "_v": 2,
        }
        # 古典口径既可走 `options` 字典，也可走 BirthInput 继承来的**顶层**同名字段（schema 里逐个带
        # 描述，agent 照着传是完全正确的用法）。此前只读 options → 顶层写法被静默丢弃、搜索结果不同
        # 却无任何报错。两处都收，options 优先。
        base.update(_electionscan_options(payload))
        base.update(_electionscan_options(payload.get("options")))

        lists: list[list[dict[str, Any]]] = []
        truncated = False
        eval_points = 0
        total_segments = len(segments)
        for index, segment in enumerate(segments, start=1):
            _progress_tick(index - 1, total_segments, f"天星择时：扫描第 {index}/{total_segments} 段")
            raw = self._call_remote("/electionscan/scan", {**base, **segment})
            data = self._require_electionscan_ok(raw, endpoint="/electionscan/scan")
            lists.append(list(data.get("intervals") or []))
            truncated = truncated or bool(data.get("truncated"))
            eval_points += int(((data.get("stats") or {}).get("evalPoints")) or 0)
        _progress_tick(total_segments, total_segments, "天星择时：缝合区间")
        stitched = self._tianxing_js({"action": "stitch", "lists": lists}, stage="stitch")
        intervals = stitched.get("intervals") or []

        fields = {
            "date": {"value": payload.get("date") or start_date},
            "time": {"value": payload.get("time") or start_time},
            "pos": {"value": payload.get("pos")},
            "lon": {"value": payload.get("lon")},
            "lat": {"value": payload.get("lat")},
            "zone": {"value": payload.get("zone")},
            "zodiacal": {"value": payload.get("zodiacal")},
            "siderealAyanamsa": {"value": payload.get("siderealAyanamsa")},
        }
        ctx = {
            # the snapshot renders the **UI** tree (chain joiners), not the compiled one
            # 🔴 zodiacal / siderealAyanamsa 必须进 cfg：快照的 [征象搜索配置] 段读 cfg.zodiacal
            # 决定打「回归黄道」还是「恒星黄道(ayanamsa)」（tianxingSnapshot.js:76）。此前没送 →
            # 恒星盘搜索也恒打「回归黄道」，而同一份输出里 [起盘信息] 的「黄道：」行读的是 fields
            # （已正确填充）→ 一份交付物里两行自相矛盾，且声称的口径不是真正跑的那个。
            # gpsLon/gpsLat 同理：pos 缺省时「搜索地点」行读它们（:74），不送就渲染成空。
            "cfg": {
                **cfg,
                "hsys": payload.get("hsys"),
                "pos": payload.get("pos"),
                # zone 不放这里：tianxingSnapshot.js 全文只读 startDate/startTime/endDate/endTime/
                # pos/gpsLon/gpsLat/hsys/zodiacal/siderealAyanamsa 十键，cfg.zone 无人消费。
                "zodiacal": payload.get("zodiacal"),
                "siderealAyanamsa": payload.get("siderealAyanamsa"),
                "gpsLon": payload.get("gpsLon"),
                "gpsLat": payload.get("gpsLat"),
            },
            "tree": conditions,
            "results": intervals,
            "truncated": truncated,
        }
        # [Q-453] 命中清单前 N 行附判读树：判读是服务端的，上游宿主扫描后预取（prefetchSnapshotExplains），
        # builder 经 ctx.explainAt 按行序读缓存。函数过不了 JSON 边界 → 预取结果按行序交 JS，由 JS 装 explainAt。
        explains = self._zeri_prefetch_explains("/electionscan/explain", base, intervals, payload, "天星择日")
        js_result = self._tianxing_js(
            {"action": "snapshot", "chart": payload.get("chart"), "fields": fields, "ctx": ctx,
             "explains": explains, **_zeri_snapshot_row_opts(payload)},
            stage="snapshot",
        )
        raw_snapshot = js_result.get("snapshot_text")
        snapshot_text = raw_snapshot if isinstance(raw_snapshot, str) and raw_snapshot.strip() else None
        # [选中时刻星盘]（v3.9.2）：命中时刻的整张判读底盘。上游在 UI 里把选中命中的 chart 喂
        # buildAstroSnapshotContent(headerless)——headless 侧同语义：取首个命中的 pick 时刻补铸
        # /chart（走完整 chart 工具管线，享受同一套段构建），再把子段头 `[X]` 转 `· X` 并入本段
        # （上游 headerless 正则逐字同款，防子段被顶层拆走）。无命中/铸盘失败不产段（条件段，零回归）。
        if snapshot_text and intervals:
            moment_section = self._tianxing_selected_moment_section(payload, intervals[0])
            if moment_section:
                snapshot_text = f"{snapshot_text}\n\n{moment_section}"
        # [单时判读]（v0.33.0）：explainAt 时刻的逐叶判读，与扫描求值器绝对同源（/electionscan/explain
        # pass 复用微域自证）。条件段：未给 explainAt 不产段，零回归。
        explain_tree: dict[str, Any] | None = None
        explained_at: str | None = None
        if payload.get("explainAt"):
            explained_at, explain_tree, explain_section = self._tianxing_explain(payload, base, conditions)
            if snapshot_text and explain_section:
                snapshot_text = f"{snapshot_text}\n\n{explain_section}"
        result_payload = {
            "intervals": intervals,
            "hit_count": len(intervals),
            "truncated": truncated,
            "stats": {"evalPoints": eval_points, "segments": len(segments)},
            "compiled_conditions": compiled,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="tianxing", snapshot_text=snapshot_text),
        }
        if explain_tree is not None:
            result_payload["explain"] = {"t": explained_at, "tree": explain_tree}
        return result_payload

    def _tianxing_explain(
        self, payload: dict[str, Any], base: dict[str, Any], ui_tree: Any
    ) -> tuple[str, dict[str, Any] | None, str]:
        """/electionscan/explain 往返 + [单时判读] 段文本（JS 侧同源语汇渲染）。

        t 归一照上游 explainInterval（TianxingElectionMain.js:346）：'-'→'/'，缺秒补 ':00'。
        """
        t_raw = str(payload.get("explainAt") or "").strip().replace("-", "/")
        if len(t_raw) == 16:  # YYYY/MM/DD HH:mm
            t_raw = f"{t_raw}:00"
        raw = self._call_remote("/electionscan/explain", {**base, "t": t_raw})
        data = self._require_electionscan_ok(raw, endpoint="/electionscan/explain")
        tree = data.get("tree") if isinstance(data, dict) else None
        js = self._tianxing_js(
            {"action": "explain_section", "t": data.get("t") or t_raw, "tree": ui_tree, "explain": tree},
            stage="explain_section",
        )
        section = js.get("snapshot_text")
        return t_raw, (tree if isinstance(tree, dict) else None), (section if isinstance(section, str) else "")

    # ── 七政择日动盘（批 I-1b，/qizhengelection/*）────────────────────────────────

    def _require_qizhengelection_ok(self, result: Any, *, endpoint: str, expect: str) -> Any:
        """信封判读（同 _require_electionscan_ok 家族，HTTP 200 也回失败信封）。

        pan 的 Result 是 dict → `_unwrap_result` 已剥出内层；eclipses/azimuthsearch 的 Result
        是**数组** → 信封原样返回（unwrap 只剥 dict）。失败时 Result 是字符串（"… failed"）。
        """
        if isinstance(result, dict) and "ResultCode" in result:
            if result.get("ResultCode") == 0:
                inner = result.get("Result")
                if expect == "list" and isinstance(inner, list):
                    return inner
                if expect == "dict" and isinstance(inner, dict):
                    return inner
            raise ToolTransportError(
                "七政择日端点返回失败信封。",
                code="tool.qizhengelection_failed",
                details={"endpoint": endpoint, "error": result.get("Result")},
            )
        if expect == "dict" and isinstance(result, dict):
            return result
        raise ToolTransportError(
            "七政择日端点返回了意外形状。",
            code="tool.qizhengelection_failed",
            details={"endpoint": endpoint, "shape": type(result).__name__},
        )

    def _qizhengelection_snapshot(self, kind: str, fields: dict[str, Any], data: dict[str, Any], options: dict[str, Any]) -> str:
        result = self.js_client.run(
            "qizhengelection", {"kind": kind, "fields": fields, "data": data, "options": options}
        )
        js_data = result.get("data") or {}
        if not js_data.get("ok"):
            error = js_data.get("error") or {}
            raise ToolTransportError(
                f"七政择日快照渲染失败：{error.get('message') or '未知错误'}",
                code=f"tool.qizhengelection_{error.get('code') or 'snapshot_failed'}",
                details={"error": error},
            )
        text = result.get("snapshot_text")
        return text if isinstance(text, str) else ""

    def _run_qizheng_election_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        action = str(payload.get("action") or "pan").strip().lower()
        if action not in {"pan", "eclipses", "azimuthsearch"}:
            raise ToolValidationError(
                f"未知动作 {action}（可选：pan / eclipses / azimuthsearch）。",
                code="tool.qizhengelection_unknown_action",
                details={"action": action},
            )
        zone = payload.get("zone") or "+08:00"
        fields = {
            "date": payload.get("date"),
            "time": payload.get("time"),
            "zone": zone,
            "pos": payload.get("pos"),
            "lat": payload.get("lat"),
            "lon": payload.get("lon"),
        }
        options: dict[str, Any] = {
            "plate": payload.get("plate") or "di",
            "ziZheng": payload.get("ziZheng") or "true",
            "declination": payload.get("declination") or 0,
            "eleLifeMode": payload.get("eleLifeMode") or "sunrise",
        }
        if action == "pan":
            if payload.get("gpsLat") is None or payload.get("gpsLon") is None:
                raise ToolValidationError(
                    "七政择日动盘需要经纬度（lat/lon 或 gpsLat/gpsLon）。",
                    code="tool.qizhengelection_missing_geo",
                    details={"lat": payload.get("lat"), "lon": payload.get("lon")},
                )
            remote: dict[str, Any] = {
                "date": payload.get("date"),
                "time": payload.get("time") or "12:00:00",
                "zone": zone,
                "gpsLat": payload.get("gpsLat"),
                "gpsLon": payload.get("gpsLon"),
            }
            for key in ("height", "nodeType", "lilithType", "ayanamsaDeg", "eleLifeMode", "eleLifeCustomTime", "extraBodies"):
                if payload.get(key) is not None:
                    remote[key] = payload.get(key)
            data = self._require_qizhengelection_ok(
                self._call_remote("/qizhengelection/pan", remote), endpoint="/qizhengelection/pan", expect="dict"
            )
            snapshot_text = self._qizhengelection_snapshot("pan", fields, data, options)
            body: dict[str, Any] = {"pan": data}
        elif action == "eclipses":
            options["kind"] = "lunar" if str(payload.get("kind") or "").strip().lower() == "lunar" else "solar"
            remote = {"date": payload.get("date"), "zone": zone, "kind": options["kind"]}
            if payload.get("count") is not None:
                remote["count"] = payload.get("count")
            rows = self._require_qizhengelection_ok(
                self._call_remote("/qizhengelection/eclipses", remote), endpoint="/qizhengelection/eclipses", expect="list"
            )
            snapshot_text = self._qizhengelection_snapshot("eclipses", fields, {"rows": rows}, options)
            body = {"eclipses": rows}
        else:  # azimuthsearch
            if payload.get("targetAz") is None:
                raise ToolValidationError(
                    "方位搜索需要目标罗盘方位 targetAz（0-359.9，0=北顺时针）。",
                    code="tool.qizhengelection_missing_target",
                    details={},
                )
            if payload.get("gpsLat") is None or payload.get("gpsLon") is None:
                raise ToolValidationError(
                    "方位搜索需要经纬度（lat/lon 或 gpsLat/gpsLon）。",
                    code="tool.qizhengelection_missing_geo",
                    details={"lat": payload.get("lat"), "lon": payload.get("lon")},
                )
            options["body"] = str(payload.get("body") or "日")
            options["targetAz"] = payload.get("targetAz")
            options["days"] = payload.get("days") or 3
            remote = {
                "date": payload.get("date"),
                "time": payload.get("time") or "00:00:00",
                "zone": zone,
                "gpsLat": payload.get("gpsLat"),
                "gpsLon": payload.get("gpsLon"),
                "targetAz": payload.get("targetAz"),
                "days": options["days"],
                "body": options["body"],
            }
            rows = self._require_qizhengelection_ok(
                self._call_remote("/qizhengelection/azimuthsearch", remote), endpoint="/qizhengelection/azimuthsearch", expect="list"
            )
            snapshot_text = self._qizhengelection_snapshot("azimuthsearch", fields, {"rows": rows}, options)
            body = {"hits": rows}
        return {
            "action": action,
            **body,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="qizhengelection", snapshot_text=snapshot_text),
        }

    # ── 印度出生时间校正（批 I-2，/india/rectify）───────────────────────────────

    def _run_india_rectify_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        remote = {**payload}
        for key in ("rectifyWindowMinutes", "rectifyStepSeconds", "rectifyTopK", "rectifyRpSource", "rectifyEvents"):
            if remote.get(key) is None:
                remote.pop(key, None)
        response = self._call_remote("/india/rectify", remote)
        if not isinstance(response, dict) or response.get("available") is not True:
            raise ToolTransportError(
                "印度校时端点未返回可用结果。",
                code="tool.india_rectify_failed",
                details={"endpoint": "/india/rectify", "response": response if isinstance(response, dict) else {"shape": type(response).__name__}},
            )
        snapshot_text = _build_india_rectify_snapshot_text(payload, response)
        return {
            "rectify": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="india_rectify", snapshot_text=snapshot_text),
        }

    # ── 行星周期（批 I-3，/astroextra/planetcycles）─────────────────────────────

    def _run_planet_cycles_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        remote: dict[str, Any] = {}
        for key in ("startYear", "endYear", "p1", "p2", "aspect", "center"):
            if payload.get(key) is not None:
                remote[key] = payload.get(key)
        response = self._call_remote("/astroextra/planetcycles", remote)
        events = response.get("events") if isinstance(response, dict) else None
        if not isinstance(events, list):
            raise ToolTransportError(
                "行星周期端点返回了意外形状。",
                code="tool.planet_cycles_failed",
                details={"endpoint": "/astroextra/planetcycles"},
            )
        aspect = response.get("aspect")
        aspect_cn = {0.0: "合", 180.0: "冲"}.get(float(aspect) if aspect is not None else 0.0, f"{_round3(aspect)}°")
        center_cn = {"geo": "地心", "helio": "日心", "topo": "站心"}.get(str(response.get("center") or "geo"), str(response.get("center")))
        config_lines = [
            f"星对：{_astro_msg(response.get('p1'))}-{_astro_msg(response.get('p2'))}　相位：{aspect_cn}　"
            f"区间：{response.get('startYear')}–{response.get('endYear')}　坐标系：{center_cn}",
        ]
        event_lines: list[str] = [f"共 {len(events)} 次"]
        for ev in events:
            if not isinstance(ev, dict):
                continue
            try:
                hour_val = float(ev.get("hour") or 0.0)
                hh, mm = int(hour_val), int(round((hour_val - int(hour_val)) * 60)) % 60
                when = f"{ev.get('year')}-{int(ev.get('month') or 0):02d}-{int(ev.get('day') or 0):02d} {hh:02d}:{mm:02d}"
            except (TypeError, ValueError):
                when = f"{ev.get('year')}"
            event_lines.append(f"{when}（UT）　{_sign_degree(ev.get('lon'))}")
        snapshot_text = _render_snapshot_text([
            ("周期配置", "\n".join(config_lines)),
            ("会合事件", "\n".join(event_lines)),
        ])
        return {
            "cycles": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="planet_cycles", snapshot_text=snapshot_text),
        }

    # ── 出生节气窗（批 I-3，/jieqi/birth）───────────────────────────────────────

    def _run_jieqi_birth_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        remote = {
            "date": payload.get("date"),
            "time": payload.get("time"),
            "zone": payload.get("zone"),
            "lat": payload.get("lat"),
            "lon": payload.get("lon"),
        }
        for key in ("ad", "useLocalMao", "byLon"):
            if payload.get(key) is not None:
                remote[key] = payload.get(key)
        response = self._call_remote("/jieqi/birth", remote)
        rows = response.get("jieqi") if isinstance(response, dict) else None
        if not isinstance(rows, list) or not rows:
            raise ToolTransportError(
                "出生节气端点返回了意外形状。",
                code="tool.jieqi_birth_failed",
                details={"endpoint": "/jieqi/birth"},
            )
        info_lines = [
            f"出生：{payload.get('date')} {payload.get('time')}（{payload.get('zone')}）",
            f"地点：{payload.get('pos') or ''}　经度 {payload.get('lon')} 纬度 {payload.get('lat')}".rstrip(),
        ]
        birth_key = f"{payload.get('date')} {payload.get('time')}".replace("/", "-")
        if len(birth_key) == 16:
            birth_key = f"{birth_key}:00"
        row_lines: list[str] = []
        prev_row: dict[str, Any] | None = None
        bracket: tuple[dict[str, Any], dict[str, Any]] | None = None
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_lines.append(f"{row.get('jieqi')}（{'节' if row.get('jie') else '气'}）　{row.get('time')}")
            # 括界判定：纯字符串时刻比较（后端时刻同时区），非任何技法推算。
            if prev_row is not None and bracket is None:
                if f"{prev_row.get('time')}" <= birth_key < f"{row.get('time')}":
                    bracket = (prev_row, row)
            prev_row = row
        if bracket:
            row_lines.append(
                f"出生落于 {bracket[0].get('jieqi')}（{bracket[0].get('time')}）与 "
                f"{bracket[1].get('jieqi')}（{bracket[1].get('time')}）之间"
            )
        snapshot_text = _render_snapshot_text([
            ("起盘信息", "\n".join(info_lines)),
            ("出生节气窗", "\n".join(row_lines)),
        ])
        return {
            "jieqi": rows,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="jieqi_birth", snapshot_text=snapshot_text),
        }

    def _tianxing_selected_moment_section(self, payload: dict[str, Any], hit: dict[str, Any]) -> str:
        try:
            pick = f"{(hit or {}).get('pick') or (hit or {}).get('start') or ''}".strip()
            if not pick:
                return ""
            parts = pick.split(" ")
            moment_payload = {
                "date": parts[0],
                "time": (parts[1] if len(parts) > 1 else "12:00") + (":00" if len(parts) > 1 and parts[1].count(":") == 1 else ""),
                "zone": payload.get("zone"),
                "lat": payload.get("lat"),
                "lon": payload.get("lon"),
                "pos": payload.get("pos"),
                "hsys": payload.get("hsys"),
                "zodiacal": payload.get("zodiacal"),
                "siderealAyanamsa": payload.get("siderealAyanamsa"),
                # [Q-419/T-382][Q-268/T-254] 选中时刻盘与扫描同源构参（上游 previewChartParams 带全局古典口径 +
                # 'user' 档历元两键，TianxingElectionMain.js:393-395）：否则非缺省口径下命中判定与所见盘不同形。
                # 与扫描同一次双读合并（顶层 → options 覆盖）。
                **_electionscan_options(payload),
                **_electionscan_options(payload.get("options")),
                # 择时盘沿用调用方已确认的设置；这里是同一次请求的内部子盘，不再过闸。
                "agent_confirmed_settings": True,
                "clarification_notes": "tianxing selected-moment sub-chart (same confirmed settings)",
            }
            moment_payload = {k: v for k, v in moment_payload.items() if v is not None}
            chart_env = self.run_tool("chart", moment_payload, save_result=False)
            body = ""
            if chart_env.ok and isinstance(chart_env.data, dict):
                body = f"{chart_env.data.get('snapshot_text') or ''}".strip()
            if not body:
                return ""
            headerless = re.sub(r"^\[(.+?)\]$", r"· \1", body, flags=re.MULTILINE)
            return f"[选中时刻星盘]\n选中命中：{pick}\n{headerless}"
        except Exception:  # noqa: BLE001 - 星盘正文失败不阻断搜索段（上游同款 try 包裹）
            return ""

    def _run_qimenzeri_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        start_date, start_time, end_date, end_time = self._tianxing_window(payload)
        if not start_date or not end_date:
            raise ToolValidationError(
                "奇门择日需要搜索时间窗（startDate/endDate）。",
                code="tool.qimenzeri_missing_window",
                details={"startDate": start_date, "endDate": end_date},
            )
        conditions = payload.get("conditions")
        if not conditions:
            raise ToolValidationError(
                "奇门择日需要择日条件树（conditions）。",
                code="tool.qimenzeri_missing_conditions",
                details={"hint": "条件类键与参数见本工具的 agent_guidance。"},
            )
        # Skill-side span guard, tighter than the engine's own 1830-day cap: the JS subprocess has a
        # 60s wall clock (config.js_engine_timeout_seconds) and the scan costs ~2s per month-window,
        # so the engine limit would blow the timeout ~30x over. Never silently truncate (§5.9).
        # 🔴 用 _require_sane_window，不要写 `span is not None and span > max` —— 后者正是
        # 当初为 tianxing 杀掉的形状：解析不出来（`'2026-08-05 10:00'`）就跳过上限、倒置窗
        # 拿负数恒 False 也溜过去，而 JS 侧 wallToMs 照样能解析，于是超长窗一路跑到超时。
        # 这把帮手写出来就是为了根治它，此处此前漏改。
        max_span = _clamped_max_span(payload, _QIMENZERI_MAX_SPAN_DAYS)
        _require_sane_window(
            start_date, end_date, max_span=max_span, tool="qimenzeri",
            # 奇门择日的上限成因与 tianxing 不同：JS 子进程有 60s 墙钟（js_engine_timeout_seconds），
            # 扫描约 2s/月窗，所以引擎自带的 1830 天上限会把超时撑爆约 30 倍。提示保留这条成因。
            span_hint="把窗口拆成多段分别搜索；maxSpanDays 只能调低。"
                      "本上限来自 JS 引擎墙钟（HOROSA_JS_ENGINE_TIMEOUT_SECONDS），不是可协商的礼貌建议。",
        )

        cfg = {"startDate": start_date, "startTime": start_time, "endDate": end_date, "endTime": end_time}
        geo = {
            "zone": payload.get("zone"),
            "gpsLon": payload.get("gpsLon"),
            "gpsLat": payload.get("gpsLat"),
            "lon": payload.get("lon"),
            "lat": payload.get("lat"),
            "pos": payload.get("pos"),
        }
        # 🔴 起局三开关（timeAlg / after23NewDay / lateZiHourUseNextDay）是 QimenInput 继承来的
        # **顶层**字段（schemas/tools.py:397-400，各带描述），agent 照 schema 传顶层是正确用法。
        # 扫描引擎只从 `options` 读（qimenScanEngine.js:124-126），此前顶层写法被静默丢弃 →
        # 命中区间用默认起局算、而同一次调用里的**展示盘**走 _run_qimen_tool 是honor 顶层的，
        # 于是两者不同局；[奇门择日配置] 段还会打出一个根本没用上的设置标签。
        # 与 tianxing 同款双读合并（见上方 _electionscan_options 两连击），options 优先。
        # sanshi chunk F1/F3：扫描与展示盘吃**同一份**已校验口径（_qimen_effective_options：同款双读合并 +
        # 起局法缺省 zhirun 显式填入 + 认不出的值报错）。此前展示盘缺省拆补、扫描的 calcDunJia 缺省置闰，
        # 同一次调用里命中判定与所见盘不同局。
        options = _qimen_effective_options(payload)
        _progress_tick(0, 2, "奇门择日：本地区间扫描")
        scan = self.js_client.run(
            "qimenzeri",
            {
                "action": "scan", "cfg": cfg, "geo": geo, "options": options, "tree": conditions,
                "limits": {"maxHits": payload.get("maxHits")} if payload.get("maxHits") else None,
            },
        )
        _progress_tick(1, 2, "奇门择日：铸展示盘")
        scan_data = scan.get("data") or {}
        if not scan_data.get("ok"):
            error = scan_data.get("error") or {}
            raise ToolValidationError(
                f"奇门择日搜索失败：{error.get('message') or '未知错误'}",
                code=f"tool.qimenzeri_{error.get('code') or 'scan_failed'}",
                details={"error": error},
            )
        intervals = scan_data.get("intervals") or []

        # Cast the DISPLAYED pan through ken at the winning moment, so all 17 奇门 段 keep their normal
        # compute authority (`_require_ken_pan` inside `_run_qimen_tool`). Only the interval search is
        # local — ken exposes no range endpoint (see the tool's compute_sources disclosure below).
        # `pick` is upstream's boundary-safe instant (both ends pulled 1 minute inward); using `start`
        # lands the pan on the wrong side of a 时辰 boundary.
        pan_moment = intervals[0].get("pick") if intervals else f"{start_date} {start_time}"
        pan_date, _, pan_time = str(pan_moment).partition(" ")
        # ⚠️ 必须剔掉调用方可能传进来的农历/节气**预取**：QimenInput 声明 nongli / jieqi_year_prev /
        # jieqi_year_current 作为缓存，_run_qimen_tool 见到就跳过 HTTP。但展示盘的时刻已经换成 pick，
        # 沿用按原 date 预取的那份 → realSunTime/jiedelta 对不上 → 时柱/局错；窗口跨年时
        # jieqi_year_current 更是整年都错。本工具自己返回 prerequisites，正诱使 agent 回传它们。
        qimen_payload = {k: v for k, v in payload.items()
                         if k not in ("nongli", "jieqi_year_prev", "jieqi_year_current", "jieqi_year_next",
                                      "zeriSnapshotMaxRows", "zeriSnapshotExplainRows")}
        # 展示盘跟随扫描口径：上游 QimenZeriMain.onPickInterval（:309-322）把冻结的扫描 options 整包回写
        # 主盘。_run_qimen_tool 的起局三开关读**顶层**，此前 options 里给的 timeAlg/日界 只进了扫描 →
        # 命中区间与展示盘不同局。这里用同一份合并后的 options（options 优先）回填顶层，整包 options 同传。
        for key in ("timeAlg", "after23NewDay", "lateZiHourUseNextDay"):
            if options.get(key) is not None:
                qimen_payload[key] = options[key]
        qimen_payload["options"] = options
        qimen = self._run_qimen_tool({
            **qimen_payload,
            "date": pan_date or start_date,
            "time": pan_time or start_time or "00:00:00",
        })
        extra = self.js_client.run(
            "qimenzeri",
            {
                "action": "snapshot", "cfg": cfg, "geo": geo, "options": options, "tree": conditions,
                "results": intervals, "truncated": bool(scan_data.get("truncated")),
                # [Q-452/Q-453] 命中清单上限 + 前 N 行附判读树（JS 侧同步引擎直算，与扫描同源）。
                **_zeri_snapshot_row_opts(payload),
            },
        )
        extra_data = extra.get("data") if isinstance(extra.get("data"), dict) else {}
        if extra_data.get("explain_error"):
            _degrade("qimenzeri 命中行判读树不可得：%s", extra_data.get("explain_error"))
        base_text = qimen.get("snapshot_text")
        extra_text = extra.get("snapshot_text")
        snapshot_text = "\n\n".join(part.strip() for part in (base_text, extra_text) if isinstance(part, str) and part.strip()) or None
        return {
            "pan": qimen.get("pan"),
            "pan_moment": pan_moment,
            "intervals": intervals,
            "hit_count": len(intervals),
            "truncated": bool(scan_data.get("truncated")),
            "stats": scan_data.get("stats"),
            "compiled_conditions": scan_data.get("compiled_tree"),
            # Honest算权 disclosure: the pan is ken-computed (or local calcDunJia when the options take
            # upstream's isQimenLocalRoute path), the interval search is not. Upstream anchors the local
            # 排盘 against the backend on a 42,731-point 0-diff parity grid.
            "compute_sources": {
                "scan": "local_calcDunJia",
                "pan": ((qimen.get("compute_sources") or {}).get("pan")) or "kinqimen",
            },
            "route": qimen.get("route"),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="qimenzeri", snapshot_text=snapshot_text),
            "prerequisites": qimen.get("prerequisites"),
        }

    # ── 择日十技法（上游 v3.10.0）：六个本地扫描成员 ──────────────────────────────────
    # 每个 <x>zeri = 「基底技法的完整快照」+「择时三段」，与上游 aiExport 的 preset 组成
    # 逐字同构（AI_EXPORT_PRESET_SECTIONS.bazizeri = [...bazi, '择时搜索配置', '择时条件', '命中时段']）。
    # 六个引擎共享 makeHourlyScanEngine，API 逐字同形，所以这里也只有一个 runner ——
    # 复制六份近似代码等于复制六份同样的坑（尤其是「编译树 vs UI 树」那条，qimenzeri 上踩过）。
    _ZERI_SCAN_TOOLS: dict[str, dict[str, Any]] = {
        "huanglizeri": {"label": "黄历择吉", "base_tool": "huangli", "hourly": False,
                        "sections": ("择吉搜索配置", "择吉条件", "命中日段")},
        "bazizeri": {"label": "八字择时", "base_tool": "bazi_birth", "hourly": True,
                     "sections": ("择时搜索配置", "择时条件", "命中时段")},
        "taiyizeri": {"label": "太乙择时", "base_tool": "taiyi", "hourly": True,
                      "sections": ("择时搜索配置", "择时条件", "命中时段")},
        "ziweizeri": {"label": "紫微择时", "base_tool": "ziwei_birth", "hourly": True,
                      "sections": ("择时搜索配置", "择时条件", "命中时段")},
        "liurengzeri": {"label": "六壬择时", "base_tool": "liureng_gods", "hourly": True,
                        "sections": ("择时搜索配置", "择时条件", "命中时段")},
        "sanshizeri": {"label": "三式合一择时", "base_tool": "sanshiunited", "hourly": True,
                       "sections": ("择时搜索配置", "择时条件", "命中时段")},
    }

    # 各择日成员的窗口上限（天）。都比引擎自带上限紧：JS 子进程有墙钟，而扫描成本随窗口线性涨。
    # 日粒度的黄历便宜得多，故放宽。绝不静默截断（AGENTS §5.9）。
    _ZERI_MAX_SPAN_DAYS = {"huanglizeri": 366}
    _ZERI_DEFAULT_MAX_SPAN_DAYS = 92

    # 上游各择时宿主页的**出厂扫描口径**（组件 state.options 初值；日界两键=全局出厂值 1/1）。
    # skill 此前只把调用方显式给的键交给引擎，余下落到引擎内建缺省 —— 而引擎缺省与页面出厂档并不
    # 处处相同：六壬/三式扫描的贵人 guirengType 引擎缺省 0、页面出厂 2（liureng_gods 展示盘也是 2），
    # 同一窗口因此扫出与桌面不同的命中集。现以此表打底，顶层与 options 依次覆盖。
    _ZERI_PAGE_DEFAULT_OPTIONS: dict[str, dict[str, Any]] = {
        "huanglizeri": {},                                                        # HuangliZeriMain：无扫描口径
        "bazizeri": {"timeAlg": 0, "after23NewDay": 1, "lateZiHourUseNextDay": 1,
                     "godKeyPos": "年", "phaseType": 0},                           # BaziZeriMain.js:80
        "taiyizeri": {"tn": 0},                                                   # TaiyiZeriMain.js:47
        "ziweizeri": {"timeAlg": 1, "gender": 1},                                 # ZiweiZeriMain.js:72
        "liurengzeri": {"guirengType": 2, "yueMode": "zhongqi",
                        "after23NewDay": 1, "lateZiHourUseNextDay": 1},            # LiurengZeriMain.js:79
        "sanshizeri": {"guirengType": 2, "yueMode": "zhongqi", "taiyiAccum": 0,
                       "after23NewDay": 1, "lateZiHourUseNextDay": 1, "timeAlg": 0},  # SanshiZeriMain.js:80
    }

    @staticmethod
    def _zeri_display_overrides(tool_name: str, options: dict[str, Any]) -> dict[str, Any]:
        """展示盘跟随扫描口径（上游 v3.11 [挂载自检 F-37]「所见行=所判口径」）。

        按各宿主 buildFields / applyWorkbenchCalibre 的键映射，把**扫描实际生效**的口径（页面出厂档 ⊕ 顶层
        ⊕ options；键缺席时取扫描引擎自身缺省）写进基底工具的入参。只映射基底工具真能吃的键 —— 六壬的
        yueMode(节气换将)与三式的六壬贵人，基底工具（liureng_gods / sanshiunited）尚无对应入参，未能跟随。
        """
        def eff(key: str, engine_default: Any) -> Any:
            value = options.get(key)
            return engine_default if value is None else value

        if tool_name == "bazizeri":
            # BaziZeriMain.buildFields（:323-345）：timeAlg/phaseType/godKeyPos/日界/晚子时 取冻结扫描 options。
            out = {"timeAlg": eff("timeAlg", 0), "after23NewDay": eff("after23NewDay", 1),
                   "lateZiHourUseNextDay": eff("lateZiHourUseNextDay", 1)}
            for key in ("godKeyPos", "phaseType"):
                if options.get(key) is not None:
                    out[key] = options[key]
            return out
        if tool_name == "ziweizeri":
            # ZiweiZeriMain.buildFields（:318-332）：gender/timeAlg 取扫描 options，缺省 1/1 = 扫描引擎缺省
            # （computeZiweiScanPan：timeAlg 缺省钟表时、gender 缺省男）。
            return {"timeAlg": eff("timeAlg", 1), "gender": eff("gender", 1)}
        if tool_name == "liurengzeri":
            # LiurengZeriMain.requestChartAndPlot（:146-148 日界/晚子时）+ applyWorkbenchCalibre（:306-313 贵人）。
            return {"guirengType": eff("guirengType", 0), "after23NewDay": eff("after23NewDay", 1),
                    "lateZiHourUseNextDay": eff("lateZiHourUseNextDay", 1)}
        if tool_name == "taiyizeri":
            # TaiyiZeriMain.buildFields（:309-327：性别←options.sex、日界缺省 0、晚子时缺省 1，与
            # computeTaiyiScanPan 同缺省）+ applyWorkbenchCalibre（:255-261：tn 进太乙页 options）。
            taiyi_options = {"tn": eff("tn", 0)}
            if options.get("sex") is not None:
                taiyi_options["sex"] = options["sex"]
            if isinstance(options.get("school"), dict):
                # 流派六轴对象（扫描引擎 applyTaiyiSchool(pan, o.school) 按对象展开；字符串档在扫描侧即无效）。
                taiyi_options["school"] = options["school"]
            return {"after23NewDay": eff("after23NewDay", 0), "lateZiHourUseNextDay": eff("lateZiHourUseNextDay", 1),
                    "options": taiyi_options}
        if tool_name == "sanshizeri":
            # SanshiZeriMain.applyWorkbenchCalibre（:326-335）：奇门盘式键 / 太乙 taiyiAccum / 共享时间键 进三式页。
            out: dict[str, Any] = {"timeAlg": eff("timeAlg", 0), "after23NewDay": eff("after23NewDay", 1),
                                   "lateZiHourUseNextDay": eff("lateZiHourUseNextDay", 1)}
            qimen = {k: options[k] for k in ("paiPanType", "qijuMethod", "school", "zhiShiType", "kongMode", "yimaMode")
                     if options.get(k) is not None}
            if qimen:
                out["qimen_options"] = qimen
            if options.get("taiyiAccum") is not None:
                out["taiyi_options"] = {"tn": options["taiyiAccum"]}
            return out
        return {}

    def _zeri_prefetch_explains(
        self, endpoint: str, base: dict[str, Any], intervals: list[dict[str, Any]], payload: dict[str, Any], label: str
    ) -> list[Any]:
        """[Q-453] 后端扫描家族（天星/七政/印度）命中清单前 N 行的判读树。

        与上游宿主 prefetchSnapshotExplains（TianxingElectionMain.js:358-374 等三处）同式：扫描完成后对前
        N 行（zeriSnapshotExplainRows，缺省 3）逐行打 /explain，t = row.pick 或 start+':00'、'-'→'/'；结果按
        行序交给 builder 的 explainAt。单行失败按上游置 null（该行只列清单、不附判读），但失败本身进
        envelope.warnings，不静默。
        """
        count = min(_zeri_explain_rows(payload), len(intervals))
        explains: list[Any] = []
        for index in range(count):
            row = intervals[index] if isinstance(intervals[index], dict) else {}
            t = str(row.get("pick") or f"{row.get('start')}:00").replace("-", "/")
            try:
                raw = self._call_remote(endpoint, {**base, "t": t})
                data = self._require_electionscan_ok(raw, endpoint=endpoint)
            except HorosaSkillError as exc:
                _degrade("%s 第 %d 行判读树预取失败（%s）：%s", label, index + 1, endpoint, exc)
                explains.append(None)
                continue
            explains.append(data if isinstance(data, dict) else None)
        return explains

    def _run_zeri_scan_tool(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        spec = self._ZERI_SCAN_TOOLS[tool_name]
        label = spec["label"]
        start_date, start_time, end_date, end_time = self._tianxing_window(payload)
        if not start_date or not end_date:
            raise ToolValidationError(
                f"{label}需要搜索时间窗（startDate/endDate）。",
                code=f"tool.{tool_name}_missing_window",
                details={"startDate": start_date, "endDate": end_date},
            )
        conditions = payload.get("conditions")
        if not conditions:
            raise ToolValidationError(
                f"{label}需要择日条件树（conditions）。",
                code=f"tool.{tool_name}_missing_conditions",
                details={"hint": "条件类键与参数见本工具的 agent_guidance。"},
            )
        max_span = _clamped_max_span(
            payload, self._ZERI_MAX_SPAN_DAYS.get(tool_name, self._ZERI_DEFAULT_MAX_SPAN_DAYS)
        )
        _require_sane_window(start_date, end_date, max_span=max_span, tool=tool_name)

        cfg = {"startDate": start_date, "startTime": start_time, "endDate": end_date, "endTime": end_time}
        geo = {k: payload.get(k) for k in ("zone", "gpsLon", "gpsLat", "lon", "lat", "pos")
               if payload.get(k) is not None}
        # 起局开关既可走顶层（schema 逐个带描述，agent 照传是正确用法）也可走 options，options 优先
        # —— 与 tianxing / qimenzeri 同款双读合并。只读 options 会让顶层写法被静默丢弃，
        # 于是命中区间与展示盘不同局，而配置段还打出一个没用上的设置（v0.33.1 教训）。
        # 底层先铺**上游宿主页出厂扫描口径**（_ZERI_PAGE_DEFAULT_OPTIONS）：只把调用方给的键交给
        # 引擎时，余下落到引擎内建缺省，而它与桌面页出厂档并不处处相同。
        top_keys = ("timeAlg", "after23NewDay", "lateZiHourUseNextDay", "godKeyPos", "phaseType", "guirengType", "school")
        if tool_name == "ziweizeri":
            # 紫微扫描按 options.gender 起盘（ziweiZeriScanEngine.computeZiweiScanPan），上游工作台常驻该键；
            # 此前 skill 既不声明也不合并顶层 gender → 女命恒按男命扫描，展示盘却按顶层性别出。
            top_keys = (*top_keys, "gender")
        options = {
            **self._ZERI_PAGE_DEFAULT_OPTIONS.get(tool_name, {}),
            **{k: payload[k] for k in top_keys if payload.get(k) is not None},
            **(payload.get("options") or {}),
        }
        if tool_name == "ziweizeri" and options.get("gender") is not None:
            # 上游 ZiweiZeriMain.buildGeoParams 同把工作台性别放进 geoParams（:193）。
            geo["gender"] = options["gender"]
        natal = payload.get("natal") if isinstance(payload.get("natal"), dict) else None

        request = {"technique": tool_name, "action": "scan", "cfg": cfg, "geo": geo,
                   "options": options, "tree": conditions}
        if natal:
            request["natal"] = natal
        if payload.get("maxHits"):
            request["limits"] = {"maxHits": payload.get("maxHits")}
        _progress_tick(0, 2, f"{label}：本地区间扫描")
        scan = self.js_client.run("zeri_scan", request)
        _progress_tick(1, 2, f"{label}：铸展示盘")
        scan_data = scan.get("data") or {}
        if not scan_data.get("ok"):
            error = scan_data.get("error") or {}
            raise ToolValidationError(
                f"{label}搜索失败：{error.get('message') or '未知错误'}",
                code=f"tool.{tool_name}_{error.get('code') or 'scan_failed'}",
                details={"error": error},
            )
        intervals = scan_data.get("intervals") or []

        # 展示盘走**基底技法自己的 runner**，所有段保持它原本的算权（ken/后端/本地各按其旧）。
        # 只有区间搜索在本地跑。`pick` 是上游的边界安全时刻（两端各内缩），用 `start` 会把盘
        # 落到时辰边界的另一侧 —— qimenzeri 上已验证过这一条。
        pan_moment = intervals[0].get("pick") if intervals else f"{start_date} {start_time}"
        pan_date, _, pan_time = str(pan_moment).partition(" ")
        base_payload = {k: v for k, v in payload.items()
                        if k not in ("conditions", "options", "natal", "maxHits", "maxSpanDays",
                                     "startDate", "startTime", "endDate", "endTime",
                                     "zeriSnapshotMaxRows", "zeriSnapshotExplainRows",
                                     "nongli", "jieqi_year_prev", "jieqi_year_current")}
        base_payload["date"] = pan_date or start_date
        base_payload["time"] = pan_time or start_time or "00:00:00"
        # 展示盘跟随**扫描口径**（上游 v3.11「所见行=所判口径」：各宿主 buildFields/applyWorkbenchCalibre
        # 把冻结的扫描 options 回写进 pick 后的显示盘）。此前 base_payload 丢掉 options、只剩顶层 →
        # options 里给的时间算法/贵人/日界对展示盘全无效，且缺省时展示盘走基底工具自己的缺省
        # （紫微扫描恒钟表时、展示盘却按 ziwei_birth 的真太阳时出），同一次结果里两套口径。
        base_payload.update(self._zeri_display_overrides(tool_name, options))
        # 走公共 run_tool 而非各自的私有 runner：六个基底技法的内部调用形状并不统一
        # （qimen 是 _run_qimen_tool(payload)、liureng 是 _run_liureng_tool(name, payload)、
        # bazi/ziwei 干脆没有私有 runner 而走通用远端路径）。run_tool 对四种都一致，
        # 且顺带跑完各自 runner 的富化，展示盘因此与直接调该技法**逐字同段**。
        # agent_confirmed_settings：这是同一次请求内部的子盘，设置已在外层过闸，
        # 不再重复拦（与 _tianxing_selected_moment_section 同款）。
        base_payload["agent_confirmed_settings"] = True
        base_payload.setdefault("clarification_notes", f"{tool_name} selected-moment sub-chart")
        base_env = self.run_tool(spec["base_tool"], base_payload, save_result=False)
        if not base_env.ok:
            # 🔴 把基底工具的**原始报错**带出来。只说「铸盘失败」时，无 Mongo 机器上的
            # Java 9999 与真正的接线错误长得一模一样 —— 本轮 live 验证为区分这两者做了整轮排查，
            # 而那轮排查本可以由这一行错误信息省掉。
            base_err = base_env.error
            raise ToolTransportError(
                f"{label}的展示盘（{spec['base_tool']}）铸盘失败，命中区间已算出但无法出盘："
                f"{(base_err.message if base_err else '') or '未知错误'}",
                code=f"tool.{tool_name}_base_chart_failed",
                details={"base_tool": spec["base_tool"], "pan_moment": pan_moment,
                         "base_error": {"code": base_err.code, "message": base_err.message} if base_err else None,
                         "hint": f"先单独调 {spec['base_tool']} 同刻复现：它也红 = 基底技法/环境问题"
                                 f"（Java 族回 9999 时先读 Result 原文；裸 -jar 起的实例连不上 Mongo 就是这样），"
                                 f"只有择日这条红才是接线问题。"},
            )
        base = base_env.data if isinstance(base_env.data, dict) else {}

        extra = self.js_client.run(
            "zeri_scan",
            {"technique": tool_name, "action": "snapshot", "cfg": cfg, "geo": geo, "options": options,
             **({"natal": natal} if natal else {}),
             "tree": conditions, "results": intervals, "truncated": bool(scan_data.get("truncated")),
             # [Q-452/Q-453] 命中清单上限 + 前 N 行附判读树（JS 侧同步引擎直算 explainAt，与扫描同源）。
             **_zeri_snapshot_row_opts(payload)},
        )
        extra_data = extra.get("data") if isinstance(extra.get("data"), dict) else {}
        if extra_data.get("explain_error"):
            _degrade("%s 命中行判读树不可得：%s", tool_name, extra_data.get("explain_error"))
        base_text = base.get("snapshot_text") if isinstance(base, dict) else None
        extra_text = extra.get("snapshot_text")
        snapshot_text = "\n\n".join(
            part.strip() for part in (base_text, extra_text) if isinstance(part, str) and part.strip()
        ) or None
        return {
            "pan_moment": pan_moment,
            "pan": base.get("pan") if isinstance(base, dict) else None,
            "base": base,
            "intervals": intervals,
            "hit_count": len(intervals),
            "truncated": bool(scan_data.get("truncated")),
            "stats": scan_data.get("stats"),
            "compiled_conditions": scan_data.get("compiled_tree"),
            "limits": scan_data.get("limits"),
            # 算权如实披露：展示盘按基底技法的原算源，区间搜索是本地 vendored 引擎
            # （上游对每个成员都有跨引擎一致性金标与压力网看守，见 v3.10.0 发行说明）。
            "compute_sources": {"scan": f"local_{tool_name}_engine", "pan": spec["base_tool"]},
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique=tool_name, snapshot_text=snapshot_text),
        }

    # ── 择日十技法：两个**后端扫描**成员（七政 / 印度）───────────────────────────────
    # 与上面六个的分工不同：判定跑在 astropy（swisseph 直连分钟粒度），skill 只发请求 ——
    # 与 tianxing 走 /electionscan/* 是同一条路，端点三件套 scan/conditiontypes/explain 也同形。
    # 端点写**完整字面量**而不是 f"{prefix}/scan" 拼出来：`test_registered_endpoints_have_call_sites`
    # 靠在源码里搜字面量确认「登记的端点真有人调」，拼接会让它看不见 —— 那条守卫的价值恰恰在于
    # 抓「登记了却没接线」和「拼写漂移」，为省几个字符把它弄瞎不划算。
    _ZERI_BACKEND_TOOLS: dict[str, dict[str, Any]] = {
        "qizhengzeri": {
            "label": "七政择时", "base_tool": "guolao_chart",
            "scan": "/qizhengelectionscan/scan",
            "explain": "/qizhengelectionscan/explain",
            "conditiontypes": "/qizhengelectionscan/conditiontypes",
        },
        "indiazeri": {
            # 印度页是 A 类星盘系，上游 preset 里 indiazeri 只有择时三段、无基底快照槽
            # （盘全文见 india_chart 本身）—— 故不铸展示盘，段自足。
            "label": "印度择时（Muhurta）", "base_tool": None,
            "scan": "/indiaelectionscan/scan",
            "explain": "/indiaelectionscan/explain",
            "conditiontypes": "/indiaelectionscan/conditiontypes",
        },
    }
    # 后端单请求硬上限 93 天（election_scan 家族共用），上游用按月分段绕开。
    _ZERI_BACKEND_MAX_SPAN_DAYS = 731

    # 后端扫描上下文**实读**的口径键 + 上游宿主页出厂档（buildScanPayload 同键同缺省）：
    #   七政 QizhengScanContext（qizheng_election_scan.py:72-81）读 su28Mode（仅 2 回归今宿 / 3 开禧宿度，其余
    #     ValueError）、nodeType、lilithType（mean|true）、fuOrb；页面出厂 {su28Mode:2, nodeType:'mean',
    #     lilithType:'mean'}（QizhengZeriMain.js:56,201-219）。
    #   印度 IndiaScanContext（india_election_scan.py:71-72）读 ayanamsa（缺省 lahiri）、nodeType；页面出厂
    #     {ayanamsa:'lahiri', nodeType:'mean'}（IndiaZeriMain.js:57,170-193）。
    _ZERI_BACKEND_SCAN_KEYS: dict[str, tuple[str, ...]] = {
        "qizhengzeri": ("su28Mode", "nodeType", "lilithType", "fuOrb"),
        "indiazeri": ("ayanamsa", "nodeType"),
    }
    _ZERI_BACKEND_SCAN_DEFAULTS: dict[str, dict[str, Any]] = {
        "qizhengzeri": {"su28Mode": 2, "nodeType": "mean", "lilithType": "mean"},
        "indiazeri": {"ayanamsa": "lahiri", "nodeType": "mean"},
    }

    def _zeri_backend_scan_options(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        """后端扫描口径：页面出厂档 → 顶层 → options 依次覆盖（与 tianxing 同款双读，options 优先）。

        取值越界一律结构化报错，不交后端去静默回落（nodeType 写错会被后端当 mean、su28Mode 越界会 500）。
        """
        keys = self._ZERI_BACKEND_SCAN_KEYS.get(tool_name, ())
        options = payload.get("options") if isinstance(payload.get("options"), dict) else {}
        merged: dict[str, Any] = dict(self._ZERI_BACKEND_SCAN_DEFAULTS.get(tool_name, {}))
        if tool_name == "indiazeri" and payload.get("indiaAyanamsa") is not None:
            # 与 india_chart 同词表的 indiaAyanamsa 作 ayanamsa 的别名（上游印度择时页把扫描岁差回写
            # 显示盘的 indiaAyanamsa 字段，IndiaZeriMain.js:350 —— 两名同一值）；显式 ayanamsa 优先。
            merged["ayanamsa"] = payload["indiaAyanamsa"]
        for source in (payload, options):
            for key in keys:
                if source.get(key) is not None:
                    merged[key] = source[key]
        if tool_name == "qizhengzeri":
            try:
                su28 = int(merged.get("su28Mode"))
            except (TypeError, ValueError):
                su28 = None
            if su28 not in (2, 3):
                raise ToolValidationError(
                    "七政择时的宿度制只支持 su28Mode=2（回归今宿，缺省）或 3（开禧宿度）。",
                    code="tool.qizhengzeri_bad_su28mode",
                    details={"su28Mode": merged.get("su28Mode"), "allowed": [2, 3],
                             "why": "后端 QizhengScanContext 只实现这两档（qizheng_election_scan.py:74-76）。"},
                )
            merged["su28Mode"] = su28
        for key in ("nodeType", "lilithType"):
            if key not in merged:
                continue
            value = str(merged[key]).strip().lower()
            if value not in ("mean", "true"):
                raise ToolValidationError(
                    f"{tool_name} 的 {key} 只接受 mean（平，缺省）或 true（真）。",
                    code=f"tool.{tool_name}_bad_{key.lower()}",
                    details={key: merged[key], "allowed": ["mean", "true"]},
                )
            merged[key] = value
        return merged

    def _run_zeri_backend_tool(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        spec = self._ZERI_BACKEND_TOOLS[tool_name]
        label = spec["label"]
        start_date, start_time, end_date, end_time = self._tianxing_window(payload)
        if not start_date or not end_date:
            raise ToolValidationError(
                f"{label}需要搜索时间窗（startDate/endDate）。",
                code=f"tool.{tool_name}_missing_window",
                details={"startDate": start_date, "endDate": end_date},
            )
        conditions = payload.get("conditions")
        if not conditions:
            raise ToolValidationError(
                f"{label}需要择时条件树（conditions）。",
                code=f"tool.{tool_name}_missing_conditions",
                details={"hint": "条件类键与参数见本工具的 agent_guidance。"},
            )
        max_span = _clamped_max_span(payload, self._ZERI_BACKEND_MAX_SPAN_DAYS)
        _require_sane_window(start_date, end_date, max_span=max_span, tool=tool_name)

        # 🔴 后端吃的是**编译树**，不是 UI 树。直接发 UI 树的后果不是报「形状不对」，而是
        # `unknown condition type: None`——它按编译树的键去读 type，读到 None。这与
        # zeriScan.js 里那条注释是同一个坑，只不过发生在 HTTP 边界上。tianxing 一直是先 compile
        # 再发（service.py:7126），此处照办；本地先编译还能把条件错误挡在一次远端往返之前。
        compile_result = self.js_client.run(
            "zeri_scan_remote", {"technique": tool_name, "action": "compile", "tree": conditions}
        )
        compile_data = compile_result.get("data") or {}
        if not compile_data.get("ok"):
            error = compile_data.get("error") or {}
            details: dict[str, Any] = {"error": error}
            # 自愈式报错：把服务端**实现集**（运行时孪生）带回，agent 不用猜哪些键合法。
            try:
                ct = self._call_remote(spec["conditiontypes"], {})
                if isinstance(ct, dict) and isinstance(ct.get("types"), list):
                    details["server_condition_types"] = ct.get("types")
            except Exception:  # noqa: BLE001 - 自省失败不该遮住原始校验错误
                pass
            raise ToolValidationError(
                f"{label}条件树不合法：{error.get('message') or '未知错误'}",
                code=f"tool.{tool_name}_invalid_conditions",
                details=details,
            )
        compiled = compile_data.get("compiled")

        cfg = {"startDate": start_date, "startTime": start_time, "endDate": end_date, "endTime": end_time}
        base_request: dict[str, Any] = {
            **cfg,
            "zone": _electionscan_zone(payload.get("zone")),
            "ad": payload.get("ad", 1),
            "conditions": compiled,
        }
        for key in ("lat", "lon", "gpsLat", "gpsLon", "pos", "hsys", "zodiacal", "siderealAyanamsa",
                    "height", "natal"):
            if payload.get(key) is not None:
                base_request[key] = payload[key]
        base_request.update(_electionscan_options(payload))
        base_request.update(_electionscan_options(payload.get("options")))
        # 后端扫描上下文**实读**的口径键（与上游宿主 buildScanPayload 同键同缺省）。此前 skill 发的是
        # indiaAyanamsa（IndiaScanContext 不读 → 印度择时恒按 Lahiri）与 ayanamsaDeg/indiaHsys（两个扫描都不读），
        # 七政三键一个不发、options 白名单也滤掉了它们 —— 口径看似可调，搜索结果从不变。
        scan_opts = self._zeri_backend_scan_options(tool_name, payload)
        base_request.update(scan_opts)

        # 按月分段：后端单请求 93 天硬顶，上游在 UI 里分段绕开。§5「请求型 builder 归 Python」→
        # 循环写在这里；分段/缝合的算术仍走 vendored 那份，边界才与星阙逐字一致。
        segments = self._tianxing_js({"action": "split", "cfg": cfg}, stage="split").get("segments") or [cfg]
        lists: list[list[dict[str, Any]]] = []
        truncated = False
        total_segments = len(segments)
        for index, segment in enumerate(segments, start=1):
            _progress_tick(index - 1, total_segments, f"{label}：扫描第 {index}/{total_segments} 段")
            raw = self._call_remote(spec["scan"], {**base_request, **segment})
            data = self._require_electionscan_ok(raw, endpoint=spec["scan"])
            lists.append(list(data.get("intervals") or []))
            truncated = truncated or bool(data.get("truncated"))
        _progress_tick(total_segments, total_segments, f"{label}：缝合区间")
        stitched = self._tianxing_js({"action": "stitch", "lists": lists}, stage="stitch")
        intervals = stitched.get("intervals") or []

        # [Q-453] 命中清单前 N 行附判读树：服务端判读，上游宿主扫描后预取（QizhengZeriMain.js:327-340 /
        # IndiaZeriMain.js:295-308），builder 经 explainAt 按行序读缓存。
        explains = self._zeri_prefetch_explains(spec["explain"], base_request, intervals, payload, label)
        extra = self.js_client.run(
            "zeri_scan_remote",
            {"technique": tool_name, "action": "snapshot",
             "cfg": {**cfg, **{k: payload.get(k) for k in ("pos", "hsys", "zodiacal", "siderealAyanamsa",
                                                           "gpsLon", "gpsLat") if payload.get(k) is not None}},
             "geo": {k: payload.get(k) for k in ("zone", "lat", "lon", "gpsLat", "gpsLon", "pos")
                     if payload.get(k) is not None},
             "tree": conditions, "results": intervals, "truncated": truncated,
             "explains": explains, **_zeri_snapshot_row_opts(payload)},
        )
        extra_text = extra.get("snapshot_text")

        base_text = None
        base: dict[str, Any] = {}
        if spec["base_tool"]:
            pan_moment = intervals[0].get("pick") if intervals else f"{start_date} {start_time}"
            pan_date, _, pan_time = str(pan_moment).partition(" ")
            base_payload = {k: v for k, v in payload.items()
                            if k not in ("conditions", "options", "natal", "maxHits", "maxSpanDays",
                                         "startDate", "startTime", "endDate", "endTime",
                                         "zeriSnapshotMaxRows", "zeriSnapshotExplainRows",
                                         "su28Mode", "nodeType", "lilithType", "fuOrb")}
            base_payload.update({"date": pan_date or start_date,
                                 "time": pan_time or start_time or "00:00:00",
                                 "agent_confirmed_settings": True,
                                 "clarification_notes": f"{tool_name} selected-moment sub-chart"})
            if tool_name == "qizhengzeri":
                # 展示盘跟随扫描口径（上游 QizhengZeriMain.buildFields :365-402 [挂载自检 F-37]）：罗计交点 / 月孛
                # 走 guolao 键名（perchart.applyGuolaoSiyu 读 guolaoNodeType/guolaoLilithType）；宿度制
                # su28Mode → doubingSu28（:390 `doubingSu28: Number(o.su28Mode)`，缺省 2 回归今宿）。
                base_payload["guolaoNodeType"] = scan_opts.get("nodeType", "mean")
                base_payload["guolaoLilithType"] = scan_opts.get("lilithType", "mean")
                base_payload["doubingSu28"] = int(scan_opts.get("su28Mode", 2))
            base_env = self.run_tool(spec["base_tool"], base_payload, save_result=False)
            if base_env.ok and isinstance(base_env.data, dict):
                base = base_env.data
                base_text = base.get("snapshot_text")
            else:
                # 命中区间照常交付，但展示盘缺席必须可见（此前静默吞掉 → 基底段整段消失而无任何说明）。
                base_err = base_env.error
                _degrade("%s 展示盘（%s）铸盘失败：%s", tool_name, spec["base_tool"],
                         (base_err.message if base_err else "") or "未知错误")
        else:
            pan_moment = intervals[0].get("pick") if intervals else f"{start_date} {start_time}"

        # [单时判读]：与 tianxing 同款能力 —— 后端 explain 端点复用**同一个求值器**，
        # 所以逐叶 pass 与扫描结果绝对同源。未给 explainAt 不产，零回归。
        explain_payload = None
        if payload.get("explainAt"):
            t_raw = str(payload.get("explainAt") or "").strip().replace("-", "/")
            if len(t_raw) == 16:  # YYYY/MM/DD HH:mm
                t_raw = f"{t_raw}:00"
            raw = self._call_remote(spec["explain"], {**base_request, "t": t_raw})
            data = self._require_electionscan_ok(raw, endpoint=spec["explain"])
            if isinstance(data, dict) and data.get("tree") is not None:
                explain_payload = {"t": data.get("t") or t_raw, "tree": data.get("tree")}

        snapshot_text = "\n\n".join(
            part.strip() for part in (base_text, extra_text) if isinstance(part, str) and part.strip()
        ) or None
        return {
            "pan_moment": pan_moment,
            "base": base or None,
            **({"explain": explain_payload} if explain_payload else {}),
            "intervals": intervals,
            "hit_count": len(intervals),
            "truncated": truncated,
            "segments": len(segments),
            "compiled_conditions": compiled,
            # 算权如实披露：判定与区间搜索都在后端 astropy（swisseph 直连），不是本地重算。
            "compute_sources": {"scan": f"astropy{spec['scan']}", "pan": spec["base_tool"] or "none"},
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique=tool_name, snapshot_text=snapshot_text),
        }

    def _run_taiyi_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 口径单源：顶层日界两开关（0/1 整数，JS buildOptions 按 `=== 1` 标「换日」）∪ options，options 优先。
        options = {**_day_boundary_switches(payload), **(payload.get("options") or {})}
        # 时间基准（上游 TaiYiMain TAIYI_PAGE_SETTINGS.timeBasis def 'direct'，TIME_BASIS_OPTIONS 两档）：
        # trueSolar 时 ken 按 nongli.birth 的真太阳时分量起局（上游 resolveCalculationDateTime，TaiYiCalc.js:254）。
        # 此前该档既不发也不施加，快照却标「真太阳时」—— ken 恒按钟表时起局。
        time_basis = options.get("timeBasis") or "direct"
        if time_basis not in ("direct", "trueSolar"):
            raise ToolValidationError(
                bilingual(
                    f"太乙 timeBasis 取值无效：{time_basis!r}（可选：direct=直接时间 / trueSolar=真太阳时）。",
                    f"taiyi timeBasis is invalid: {time_basis!r} (allowed: direct / trueSolar).",
                ),
                code="tool.taiyi_invalid_option",
                details={"field": "timeBasis", "value": time_basis, "allowed": ["direct", "trueSolar"]},
            )
        options["timeBasis"] = time_basis
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
                    # 日界/晚子时开关与 ken 权威引擎同口径：仅显式给定时发送，缺省沿用后端默认(1/1)。
                    **_day_boundary_switches(payload),
                    # 真太阳时基准要的是 nongli.birth = 真太阳时（上游太乙取农历不带 timeAlg = 后端缺省真太阳时）。
                    "timeAlg": 0 if time_basis == "trueSolar" else payload.get("timeAlg", 0),
                    "ad": payload.get("ad", 1),
                },
            )
        # taiyi ken 期望 sex 为 '男'/'女' 字符串；gender 经 input_normalization 已归一为 0(女)/1(男)，
        # 故此处显式映射（不能靠 `or gender` —— int 0 为 falsy 会误落默认「男」）。
        _g = payload.get("gender")
        _sex_from_gender = "女" if _g in (0, "0", False, "女", "female", "f") else "男"
        sex = options.get("sex") or _sex_from_gender
        ken_parts: dict[str, Any] = _ken_datetime_parts(payload)
        if time_basis == "trueSolar":
            solar = _parse_taiyi_datetime_text((nongli or {}).get("birth"))
            if solar:
                ken_parts = {**ken_parts, **solar}
        ken_response = self._call_remote(
            "/taiyi/pan",
            {
                **ken_parts,
                "zone": payload.get("zone"),
                "style": options.get("style", 3),
                "tn": options.get("tn", 0),
                "sex": sex,
                "timeBasis": time_basis,
                "enableGameTheory": bool(options.get("gameTheory") in (1, True, "1")),
                "date": payload.get("date"),
                "time": payload.get("time"),
                "realSunTime": (nongli or {}).get("birth", ""),
                "jiedelta": (nongli or {}).get("jiedelta", ""),
                # 显式日界/晚子时开关直达权威引擎（缺省不发→引擎默认 1/1）。
                **_day_boundary_switches(payload),
            },
        )
        self._require_ken_pan(ken_response, engine="kintaiyi", endpoint="/taiyi/pan")
        js_result = self.js_client.run(
            "taiyi", {**payload, "options": options, "nongli": nongli, "ken_response": ken_response}
        )
        # 流派六轴（options.school / 平铺键 / 顶层 school）由 JS 按上游 TAIYI_SCHOOL_OPTIONS 校验。
        _raise_js_option_error("taiyi", js_result)
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
        options = dict(payload.get("options") or {})
        _jinkou_validate_options(options)
        nongli = liureng.get("nongli") if isinstance(liureng, dict) and isinstance(liureng.get("nongli"), dict) else {}
        # 地分缺省 = 自动取占时支（上游 JinKouMain.js:907 diFenAuto:true → resolveJinKouDiFen 首次起课取
        # 占时支）。此前缺省发「子」给 ken（本地脚手架却取占时支），默认盘恒按子地分起。
        difen = _jinkou_resolve_difen(payload.get("diFen") or options.get("diFen"), nongli.get("time"))
        options["diFen"] = difen
        time_basis = options.get("timeBasis") or "direct"
        # 路由（上游 JinKouMain.assembleJinKouData:1255-1270 + schoolsAllDefault:1288）：五项流派/盘法全缺省才用
        # ken /jinkou/pan（再由 JS 判两源日柱是否对齐），任一非缺省即本地 buildJinKouData —— ken 不认这五项，照打会
        # 得到「按缺省流派出盘、快照却按所选解读」。此前 skill 恒用 ken 行覆盖本地脚手架，五项流派全是死开关。
        school_overrides = _jinkou_school_overrides(options)
        warnings: list[str] = []
        ken_response = None
        if not school_overrides:
            ken_parts: dict[str, Any] = _ken_datetime_parts(payload)
            if time_basis == "trueSolar":
                # 上游 fetchJinKouPan → resolveCalculationDateTime（JinKouCalc.js:2707）：真太阳时 = liureng.nongli.birth。
                solar = _parse_taiyi_datetime_text(nongli.get("birth"))
                if solar:
                    ken_parts = {**ken_parts, **solar}
            ken_response = self._call_remote(
                "/jinkou/pan",
                {
                    **ken_parts,
                    "zone": payload.get("zone"),
                    "difen": difen,
                    "yuejiang": _jinkou_manual_branch(options.get("yueJiang") or options.get("yuejiang")),
                    "zhanshi": _jinkou_manual_branch(options.get("zhanShi") or options.get("zhanshi")),
                    "timeBasis": time_basis,
                    "realSunTime": nongli.get("birth", ""),
                    "jiedelta": nongli.get("jiedelta", ""),
                    "date": payload.get("date"),
                    "time": payload.get("time"),
                    # 日界 + 晚子时两开关（上游 JinKouCalc.js:2823-2825 fetchJinKouPan 两键齐发，缺省=defaultAfter23NewDay()=1）：
                    # 显式给定才发送，缺省不发 → ken 缺省 1/1（webjinkousrv.py:244-245）= 上游出厂缺省，且与六壬前置同口径
                    # （LiuRengGodsInput.after23NewDay 缺省不再硬塞 False）。此前只发晚子时键，显式 after23NewDay=0 到不了 ken。
                    **_day_boundary_switches(payload),
                },
            )
            self._require_ken_pan(ken_response, engine="kinjinkou", endpoint="/jinkou/pan")
        elif time_basis != "direct":
            # 上游本地引擎不读时间基准（占时与日柱恒随 /liureng/gods 真太阳时口径），页面把该控件置灰（JinKouMain.js:1972）。
            warnings.append(
                f"金口诀 timeBasis={time_basis} 本次未生效：流派/盘法 {'/'.join(school_overrides)} 非缺省，"
                "改由本地引擎出课，占时与日柱恒按真太阳时（上游同样置灰该选项）。"
            )
        js_result = self.js_client.run(
            "jinkou",
            {**payload, "options": options, "liureng": liureng, "ken_response": ken_response},
        )
        _raise_js_option_error("jinkou", js_result)
        js_route = js_result.get("route") if isinstance(js_result, dict) else None
        if isinstance(js_route, dict) and bool(js_route.get("schoolsDefault")) != (not school_overrides):
            raise ToolTransportError(
                "金口诀路由判据漂移：Python 与 JS 对「五项流派是否全缺省」结论不一致。",
                code="tool.jinkou_route_check_failed",
                details={"python_overrides": school_overrides, "js_route": js_route},
            )
        data = js_result.get("data", {}) if isinstance(js_result.get("data"), dict) else {}
        if isinstance(data.get("daySourceNote"), str) and data["daySourceNote"]:
            # 上游只在页面上显示这条（不进快照）；headless 必须说出来：盘由本地引擎重出，不是 ken 盘。
            warnings.append(data["daySourceNote"])
        route_reason = js_route.get("reason") if isinstance(js_route, dict) else None
        if ken_response is not None and route_reason == "no_ken":
            warnings.append("金口诀 ken 盘未带四位行（rows），本次由本地引擎出课 —— 与星阙 ken 盘可能不一致。")
        snapshot_text = js_result.get("snapshot_text")
        result: dict[str, Any] = {
            "jinkou": data,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="jinkou", snapshot_text=snapshot_text),
            "prerequisites": {"liureng": liureng},
            "route": js_route if isinstance(js_route, dict) else {"schoolOverrides": school_overrides},
        }
        # 只给**上游同判据**的本地路由（五项流派非缺省 / 两源日柱不齐）标声明过的本地算源；ken 畸形被迫回退本地
        # 不标 —— 依据卡照旧把它显示成「与声明不一致」（AGENTS §4 静默回退形状）。
        if data.get("source") != "kinjinkou" and route_reason in ("school", "day_misaligned"):
            result["compute_sources"] = {"jinkou": "local_route_buildJinKouData"}
        if warnings:
            result["_warnings"] = warnings
        return result

    def _run_liureng_tool(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        time_alg = _liureng_time_alg(payload)
        gods_payload = _liureng_gods_payload(tool_name, payload, time_alg)
        remote = self._call_remote("/liureng/gods", gods_payload)
        liureng = remote.get("liureng", remote)
        runyear = None
        remote_payloads: dict[str, Any] = {"/liureng/gods": gods_payload}
        if tool_name == "liureng_runyear":
            # 上游 genRunYearParams（LiuRengMain.js:5090）：出生档 + 起课档，卦年干支取起课盘年柱。
            runyear_payload = _liureng_remote_payload("liureng_runyear", payload)
            if not runyear_payload.get("guaYearGanZi"):
                gua_year = _gua_year_ganzi(liureng)
                if gua_year:
                    runyear_payload["guaYearGanZi"] = gua_year
            remote_payloads["/liureng/runyear"] = runyear_payload
            runyear = _liureng_runyear_from(self._call_remote("/liureng/runyear", runyear_payload))
        chart: dict[str, Any] = {}
        chart_error: dict[str, Any] | None = None
        try:
            chart = self._call_remote("/chart", _liureng_chart_payload(payload))
        except HorosaSkillError as exc:
            chart_error = {"code": exc.code, "message": str(exc), "details": exc.details}
        except Exception as exc:
            chart_error = {"code": "liureng.chart_context_unavailable", "message": str(exc), "details": {}}

        # 决策层 S3（可选，缺省关）：没给 zhanCategory 时按问题文本分门类，驱动 [占断向导] 段。
        payload = self._decide_zhan_category(payload)
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
        # 起课口径（castMethod / 换将 / 分昼夜 / 涉害 / 阴阳系 / 十二长生五行 / 贵人 0–4）由 JS 按上游
        # LIURENG_PAGE_SETTINGS / QI_METHODS 词表校验；认不出的值 → 结构化报错（不回落缺省盘）。
        _raise_js_option_error("liureng", js_result)
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
                "remote_payload": gods_payload,
                **({"runyear_payload": remote_payloads["/liureng/runyear"]} if "/liureng/runyear" in remote_payloads else {}),
                "chart_available": bool(chart),
                "chart_error": chart_error,
            },
        }
        result["export_snapshot"] = self._augment_export_payload(technique="liureng", snapshot_text=snapshot_text)
        return result

    # ── 八字（F9）──────────────────────────────────────────────────────────────────────────────
    # 上游八字页主路径是**本地** lunar.js 引擎：BaZi.js:716-755 fetchBaziCached（bazi_direct 同形 :757-795）
    # `buildLocalBaziResult(params)` 成功即用，抛错（lunar-js 不可靠域：公元前 / 万年后 / 不可解析日期）才回退
    # Java /bazi/birth；两条路都经 normalizeBaziResult → buildBaziSnapshotText（BaZi.js:1000-1046）。
    # v0.40 前本仓整盘走 Java：godKeyPos 缺省「年日」（页面「年」，techniqueMountSettings.js:1699）、命宫缺省
    # 子平数法（页面通行版，:1705）、晚子时 (1,0) 档 Java /bazi/birth 直接 500（timegan.error，live 实测），
    # 快照是 Python 手写 port（缺纳音长生列 / 命宫起法标注 / 起运行 / 小运年龄口径 / 三维分列）。
    # 现与页面同源：本地引擎 + vendored builder（vendor/bazi/baziSnapshot.js，逐字抽自 BaZi.js）。
    _BAZI_OPTION_VOCAB: dict[str, tuple[Any, ...]] = {
        # 取值表逐条对照 techniqueMountSettings.js:1692-1740（八字挂载设置）；缺省 = BaZi.js:961-985 genParams。
        # timeAlg 2（春分定卯时）上游置灰「尚无独立换算」（CnTraditionInput.js:517），不收。
        "godKeyPos": ("年", "日", "年日"),
        "phaseType": (0, 1, 2),
        "timeAlg": (0, 1, 3),
        "minggongMethod": ("tongxing", "shufa"),
        "fenyeVersion": ("common", "fajue"),
        "cangVersion": ("common", "fenye"),
        "dayunPrecision": ("precise", "integer"),
        "school": ("zonghe", "fuyi", "geju", "tiaohou", "bingyao", "tongguan", "mangpai", "nayin"),
        "ageStyle": ("nominal", "real"),
        "zodiacBoundary": ("lichun", "lunar"),
    }
    _BAZI_OPTION_DEFAULTS: dict[str, Any] = {
        "godKeyPos": "年", "phaseType": 0, "timeAlg": 0, "minggongMethod": "tongxing",
        "fenyeVersion": "common", "cangVersion": "common", "dayunPrecision": "precise",
    }

    def _bazi_option(self, payload: dict[str, Any], key: str) -> Any:
        """取一个八字口径键：缺省 → 上游缺省；认不出 → 按缺省出并进 warnings（同 zodiacBoundary 先例，不静默吞）。"""
        raw = payload.get(key)
        if raw is None or f"{raw}" == "":
            return self._BAZI_OPTION_DEFAULTS.get(key)
        vocab = self._BAZI_OPTION_VOCAB[key]
        value = int(raw) if isinstance(vocab[0], int) and f"{raw}".lstrip("-").isdigit() else raw
        if value in vocab:
            return value
        if key == "timeAlg":
            raise ToolValidationError(
                f"八字 timeAlg={raw!r} 不受支持 / unsupported bazi timeAlg {raw!r}: 0=真太阳时 1=直接时间 3=平太阳时"
                "（2 春分定卯时上游尚未实现）",
                code="tool.bazi_timealg_unsupported",
                details={"field": "timeAlg", "value": raw, "valid": list(vocab)},
            )
        fallback = self._BAZI_OPTION_DEFAULTS.get(key)
        _degrade(
            "bazi %s %r unrecognised", key, raw,
            note=f"八字 {key}={raw!r} 无法识别（可选 {' / '.join(str(v) for v in vocab)}），已按缺省"
                 f"{f' {fallback}' if fallback is not None else ''}起盘。",
        )
        return fallback

    def _bazi_params(self, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        """上游 genParams（BaZi.js:961-985）同形同序的起盘参数 + 只进快照的附加项（:1029 snapshotParams / 挂载 period）。"""
        gender = payload.get("gender")
        # 性别缺省 = 上游「未知(按男排)」档 -1（CnTraditionInput.js:506-509）：引擎按男排、快照印「性别：未知」。
        gender = 1 if gender in (1, True, "1") else (0 if gender in (0, False, "0") else -1)

        def bit(value: Any) -> int:
            return 0 if value in (0, False, "0", "false", "False") else 1

        # 公元前：上游 DateTime.format('YYYY-MM-DD') 出带负号的年（'-0100-05-15'，dateStrSafe.js 头注），本地引擎按带符号
        # 年判可靠域（lunarDomainGuard：AD1–9999）→ 域外抛错走 Java。本仓约定是正号日期 + ad=-1，照上游补负号
        # （Java BaZiBirthController.java:110-114 自己也补，已带负号不重复）；不补则公元前 100 年被当成公元 100 年本地起盘。
        date = f"{payload.get('date') or ''}"
        if payload.get("ad") in (-1, "-1") and date and not date.startswith("-"):
            date = f"-{date}"
        params = {
            "date": date,
            "time": payload.get("time"),
            "ad": payload.get("ad", 1),
            "zone": payload.get("zone"),
            "lon": payload.get("lon"),
            "lat": payload.get("lat"),
            "gpsLat": payload.get("gpsLat"),
            "gpsLon": payload.get("gpsLon"),
            "gender": gender,
            "timeAlg": self._bazi_option(payload, "timeAlg"),
            "phaseType": self._bazi_option(payload, "phaseType"),
            "godKeyPos": self._bazi_option(payload, "godKeyPos"),
            # 日界/晚子时：缺省 = 上游出厂缺省 1/1（dayBoundary.js:39-45 / :91-93）；本地引擎缺键 = 不进位，必须显式补。
            "after23NewDay": 1 if payload.get("after23NewDay") is None else bit(payload.get("after23NewDay")),
            "lateZiHourUseNextDay": 1 if payload.get("lateZiHourUseNextDay") is None else bit(payload.get("lateZiHourUseNextDay")),
            "adjustJieqi": 1 if payload.get("adjustJieqi") in (1, True, "1", "true") else 0,
            "minggongMethod": self._bazi_option(payload, "minggongMethod"),
            "fenyeVersion": self._bazi_option(payload, "fenyeVersion"),
            "cangVersion": self._bazi_option(payload, "cangVersion"),
            "dayunPrecision": self._bazi_option(payload, "dayunPrecision"),
        }
        snapshot: dict[str, Any] = {}
        for key in ("school", "ageStyle", "zodiacBoundary"):
            if payload.get(key) not in (None, ""):
                value = self._bazi_option(payload, key)
                if value is not None:
                    snapshot[key] = value
        if isinstance(payload.get("period"), dict):
            snapshot["period"] = payload["period"]
        return params, snapshot

    def _run_bazi_tool(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        params, snapshot = self._bazi_params(payload)
        endpoint = "/bazi/direct" if tool_name == "bazi_direct" else "/bazi/birth"
        # byLon / adjustJieqi：本地引擎不实现（上游 CnTraditionInput.js:564 已把节气微调控件隐藏「选了不生效」），
        # 给了真值只有 Java 算得出 → 整盘走 Java 并如实告知（命宫起法随之标「子平数法(本域回退)」）。
        java_only = [key for key in ("byLon", "adjustJieqi") if payload.get(key) in (1, True, "1", "true")]
        js: dict[str, Any] = {}
        reason = ""
        if not java_only:
            js = self.js_client.run("bazi_local", {"params": params, "snapshot": snapshot}) or {}
            data = js.get("data") if isinstance(js.get("data"), dict) else {}
            if data.get("ok") is False:
                if data.get("reason") != "local_engine_unavailable":
                    raise ToolTransportError(
                        f"八字本地引擎未出盘 / bazi local engine produced no chart: {data.get('message') or data.get('reason')}",
                        code="tool.bazi_local_failed",
                        details={"reason": data.get("reason"), "message": data.get("message")},
                    )
                reason = f"本地历法引擎不可用（{data.get('message') or '域外日期'}）"
        else:
            reason = f"{'/'.join(java_only)} 只有 Java 引擎实现（上游页面本地引擎不支持）"
        if reason:
            java_payload = {k: v for k, v in params.items() if v is not None and not (k == "gender" and v == -1)}
            if payload.get("byLon") in (1, True, "1", "true"):
                java_payload["byLon"] = True
            java_result = self._call_remote(endpoint, java_payload)
            js = self.js_client.run("bazi_local", {"params": params, "snapshot": snapshot, "java_result": java_result}) or {}
            _degrade(
                "bazi computed by Java %s: %s", endpoint, reason,
                note=f"八字由 Java {endpoint} 起盘（{reason}）：命宫起法按 Java 口径（快照命宫行已标注），"
                     "五行力量/格局·用神/盲派/分野等本地派生段不出（与上游回退路径同）。",
            )
        data = js.get("data") if isinstance(js.get("data"), dict) else {}
        text = f"{js.get('snapshot_text') or ''}".strip()
        if not data.get("ok") or not text:
            raise ToolTransportError(
                "八字快照未产出 / bazi snapshot was not produced.",
                code="tool.bazi_local_failed",
                details={"reason": data.get("reason"), "message": data.get("message"), "java_fallback": bool(reason)},
            )
        local = bool(data.get("local"))
        return {
            "bazi": data.get("bazi"),
            "gender": data.get("gender"),
            "local": local,
            "compute_sources": {"bazi": "lunar-local" if local else "java"},
            "snapshot_text": text,
            "export_snapshot": self._augment_export_payload(technique="bazi", snapshot_text=text),
        }

    # ── 紫微（F8）──────────────────────────────────────────────────────────────────────────────
    # 上游 AI 无头复算 buildZiweiSnapshotForParams（ZiWeiMain.js:716-822）：Java /ziwei/birth 起盘，四化流派非通用
    # 时附 sihua 表（后端格局随流派）；22 个传本/排盘开关任一非缺省 → 本地 ZiweiCalc 重排盘核心 + 重算格局
    # （Java 不支持大限跨度/天马/星集/三盘…）；快照 = vendored buildZiWeiSnapshotText（[起盘信息] 四化流派/传本设置行、
    # [宫位总览] 四化括注与庙旺档）。编排在 tools/ziweiBirth.js（单例覆盖/还原同上游），JS 不发 HTTP → 两段式。
    # v0.40 前：sihuaSchool/传本键 Java 一概不读、Python 快照是手写 port —— 这些键全是死开关。
    _ZIWEI_OPTION_KEYS: tuple[str, ...] = (
        # 上游 ZW_ENGINE_SWITCH_KEYS（ZiWeiMain.js:752-754）+ 挂载键 ziweiXiaoxianYinyang（aiAnalysisContext.js:1904）
        "daxianSpan", "tianmaBasis", "starSet", "sanPan", "shangShi", "leapMonth", "lateZi", "yearBoundary", "huoling",
        "kongNaming", "brightnessSource", "lifeMasterBy", "liuYueBasis", "liunianSihuaGan", "changshengStart",
        "changshengDirection", "kuiYue", "kongwangStyle", "flowLuanXi", "flowHuoLing", "flowShenshaOnChart", "childLimit",
        "zhongxian", "huoPan", "qishuWei", "borrowPalace", "taiSuiRuGua", "taiSuiRelatives", "xiaoxianMode",
        "ziweiXiaoxianYinyang", "sihuaSchool", "sihuaCustomTable", "brightnessCustomTable",
    )

    def _ziwei_params(self, payload: dict[str, Any]) -> dict[str, Any]:
        """上游 buildChartZiweiParams（aiAnalysisContext.js:1879-1944）同形：起盘字段 + 显式给了的流派/传本键 + period。"""
        gender = payload.get("gender")
        gender = 1 if gender in (1, True, "1") else (0 if gender in (0, False, "0") else None)

        def bit(value: Any) -> int:
            return 0 if value in (0, False, "0", "false", "False") else 1

        params: dict[str, Any] = {
            "date": payload.get("date"),
            "time": payload.get("time"),
            "zone": payload.get("zone"),
            "lon": payload.get("lon"),
            "lat": payload.get("lat"),
            "gpsLat": payload.get("gpsLat"),
            "gpsLon": payload.get("gpsLon"),
            "gender": gender,
            "timeAlg": 1 if payload.get("timeAlg") in (1, "1") else 0,   # 紫微页只两档（:1890）
            # 本地引擎档要已解析的日界缺省（calcZiwei 'global' 分支直读，缺键 = 不进位）：上游出厂缺省 1/1。
            "after23NewDay": 1 if payload.get("after23NewDay") is None else bit(payload.get("after23NewDay")),
            "lateZiHourUseNextDay": 1 if payload.get("lateZiHourUseNextDay") is None else bit(payload.get("lateZiHourUseNextDay")),
        }
        # 旧入参 schools {childLimit, zhongxian, …} 仍收：与上游平铺键同义，平铺键优先。
        schools = payload.get("schools") if isinstance(payload.get("schools"), dict) else {}
        for key in self._ZIWEI_OPTION_KEYS:
            value = payload.get(key)
            if value is None:
                value = schools.get(key)
            if value is not None:
                params[key] = value
        # 旧入参 sihua（原样四化表）≡ 上游 custom 档随盘自定义表（sihuaCustomTable，techniqueMountSettings.js:1760-1763）。
        if isinstance(payload.get("sihua"), dict) and "sihuaSchool" not in params:
            params["sihuaSchool"] = "custom"
            params["sihuaCustomTable"] = payload["sihua"]
        if isinstance(payload.get("period"), dict):
            params["period"] = payload["period"]
        return params

    def _ziwei_warn(self, items: Any) -> None:
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            valid = item.get("valid") if isinstance(item.get("valid"), list) else []
            _degrade(
                "ziwei option %s=%r unrecognised", item.get("key"), item.get("value"),
                note=f"紫微 {item.get('key')}={item.get('value')!r} 无法识别（可选 {' / '.join(str(v) for v in valid)}），"
                     "该项按缺省排盘。",
            )

    def _run_ziwei_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        params = self._ziwei_params(payload)
        java_payload: dict[str, Any] = {
            key: params[key] for key in ("date", "time", "zone", "lat", "lon", "gpsLat", "gpsLon", "timeAlg")
            if params.get(key) is not None
        }
        java_payload["ad"] = payload.get("ad", 1)
        if params.get("gender") is not None:
            java_payload["gender"] = params["gender"]
        # 日界/晚子时：只发显式给定的（缺省 → Java 缺省 1/1 = 上游出厂缺省；ZiWeiController.java:87-90）。
        java_payload.update(_day_boundary_switches(payload))
        school = f"{params.get('sihuaSchool') or ''}".strip()
        prep_warnings: list[Any] = []
        if school and school != "beipai":
            prep = self.js_client.run("ziwei_birth", {"action": "prepare", "params": params}) or {}
            prep_data = prep.get("data") if isinstance(prep.get("data"), dict) else {}
            if isinstance(prep_data.get("sihua"), dict):
                java_payload["sihua"] = prep_data["sihua"]
            prep_warnings = prep.get("warnings") or []
        java_result = self._call_remote("/ziwei/birth", java_payload)
        fin = self.js_client.run("ziwei_birth", {"action": "finalize", "params": params, "result": java_result}) or {}
        data = fin.get("data") if isinstance(fin.get("data"), dict) else {}
        self._ziwei_warn(fin.get("warnings") or prep_warnings)
        text = f"{fin.get('text') or ''}".strip()
        if not data.get("ok") or not text:
            raise ToolTransportError(
                "紫微快照未产出 / ziwei snapshot was not produced.",
                code="tool.ziwei_snapshot_failed",
                details={"reason": data.get("reason")},
            )
        if data.get("localEngine") and not data.get("localApplied"):
            _degrade(
                "ziwei local engine failed, Java chart kept: %s", data.get("localError"),
                note=f"紫微传本开关需本地引擎重排，但本地引擎失败（{data.get('localError') or '未产出12宫'}），"
                     "已保留 Java 盘（上游同）——盘面未按所选传本设置变化。",
            )
        return {
            "chart": data.get("chart"),
            "patterns": data.get("patterns"),
            "compute_sources": {"chart": "ZiweiCalc" if data.get("localApplied") else "java"},
            "snapshot_text": text,
            "export_snapshot": self._augment_export_payload(technique="ziwei", snapshot_text=text),
        }

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

    # ── 占星地图（AstroCartoGraphy）请求口径：上游 AstroAcg.genParams（AstroAcg.js:348-372）逐键 ──────────────
    # 引擎口径键（ACGraph.__init__ 按名读，ACGraph.py:239-340）：缺省即后端默认、零回归；给了才下发。
    _ACG_ENGINE_KEYS = (
        "mode", "lsMode", "geodetic", "geodeticVar", "geodeticZero", "cuspLines", "coord", "posType", "horizon",
        "nodeType", "lilithType", "draconic", "harmonic", "vibration", "midpointMode", "lotsCustom", "asteroids",
        "ayanamsa", "stars",
    )
    # 上游这几键以字符串 '1'/'0' 下发（genParams 里 `x ? '1' : '0'`）；后端按字符串集合判真。
    _ACG_FLAG_KEYS = ("cuspLines", "vibration", "asteroids", "stars")
    # CCG 时间地图（只在给了 ccgDate 才下发，:356-360）与关系盘（relMode + relDate 都有才下发，:361-368）。
    _ACG_CCG_KEYS = ("ccgDate", "ccgTime", "ccgMix")
    _ACG_REL_KEYS = ("relMode", "relDate", "relTime", "relZone", "relLat", "relLon")
    # 快照图层开关（纯渲染；进 uiState 决定 [占星地图] 的 ◆ 子块，AstroAcg.js:277-287）。
    _ACG_LAYER_KEYS = ("paranMode", "showLS", "showGeodetic", "showStarParans")
    # 后端回显 meta 的有效值：请求值与之不符 = 后端不认、按缺省算了（ACGraph 静默归一）→ 说出来。
    _ACG_META_ECHO = ("mode", "lsMode", "geodetic", "geodeticVar", "coord", "posType", "horizon", "nodeType", "lilithType", "midpointMode", "relMode")
    _ACG_ONLY_KEYS = frozenset({
        *_ACG_ENGINE_KEYS, *_ACG_CCG_KEYS, *_ACG_REL_KEYS, *_ACG_LAYER_KEYS,
        "clickLat", "clickLon", "pointOrb", "pointHsys", "eventKind", "eventDirection", "eventFromDate",
    })

    @staticmethod
    def _acg_flag(value: Any) -> str:
        return "1" if value in (True, 1, "1", "true", "True", "yes", "on") else "0"

    def _acg_remote_params(self, payload: dict[str, Any], ccg: dict[str, Any] | None) -> dict[str, Any]:
        remote: dict[str, Any] = {
            "date": payload["date"],
            "time": payload["time"],
            "zone": payload["zone"],
            "lat": payload["lat"],
            "lon": payload["lon"],
            "ad": payload.get("ad", 1),
            "mode": payload.get("mode", "mundo"),
            "lsMode": payload.get("lsMode", "great"),
            "geodetic": payload.get("geodetic", "sepharial"),
            "geodeticVar": payload.get("geodeticVar", "longitude"),
            # 上游 genParams 恒带 hsys = 页面「落点宫制」（缺省 placidus，AstroAcg.js:130/184）：宫尖线与落点报告同用。
            "hsys": payload.get("pointHsys") or "placidus",
        }
        for key in self._ACG_ENGINE_KEYS:
            value = payload.get(key)
            if value is None or value == "" or key in remote:
                continue
            remote[key] = self._acg_flag(value) if key in self._ACG_FLAG_KEYS else (f"{value}" if key == "harmonic" else value)
        if ccg:
            remote.update(ccg)
        if payload.get("relMode") and payload.get("relDate"):
            remote["relMode"] = payload.get("relMode")
            remote["relDate"] = f"{payload.get('relDate')}".replace("-", "/")
            remote["relTime"] = payload.get("relTime") or "12:00:00"
            for key in ("relZone", "relLat", "relLon"):
                if payload.get(key) not in (None, ""):
                    remote[key] = payload.get(key)
        elif payload.get("relMode") or payload.get("relDate"):
            _degrade("acg: relMode/relDate given alone", note="占星地图关系盘须同时给 relMode（davison/composite/synastry）与 relDate（B 盘出生日期），缺一不下发（上游同口径）。")
        return remote

    def _run_acg_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 占星地图（AstroCartoGraphy）：行星地理投影线。地图渲染属 UI，无头输出为上游 [占星地图] 段（vendored
        # acgSnapshot.buildAcgSectionText）+ 本仓明细段（偕升纬度带/线交点/落点分析/事件时刻）。
        def geo_lon(value: Any) -> str:
            try:
                lon = ((float(value) + 180.0) % 360.0) - 180.0
            except (TypeError, ValueError):
                return "—"
            hemi = "E" if lon >= 0 else "W"
            return f"{abs(lon):.2f}°{hemi}"

        # [事件时刻]（/location/acgevent）先求：上游「世运事件快捷」（AstroAcg.pickMundane :386-404）把事件精确时刻填进
        # CCG 全行运通道重请求地图（事件时刻角化线）；zone 随本命时区下发（T-49：回本命时区钟面，不带则回 UT）。
        event: dict[str, Any] | None = None
        if payload.get("eventKind"):
            event_remote = {
                "kind": payload.get("eventKind"),
                "direction": payload.get("eventDirection") or "next",
                "fromDate": (payload.get("eventFromDate") or payload.get("date") or "").replace("-", "/"),
                "zone": payload.get("zone"),
            }
            event = self._call_remote("/location/acgevent", event_remote)
            if not isinstance(event, dict) or not event.get("date"):
                raise ToolTransportError(
                    "世运事件端点未找到该事件。",
                    code="tool.acg_event_failed",
                    details={"endpoint": "/location/acgevent", "kind": payload.get("eventKind"), "response": event if isinstance(event, dict) else None},
                )
        ccg: dict[str, Any] | None = None
        if payload.get("ccgDate"):
            ccg = {
                "ccgDate": f"{payload.get('ccgDate')}".replace("-", "/"),
                "ccgTime": payload.get("ccgTime") or "12:00:00",
                "ccgMix": payload.get("ccgMix") or "mixed",
            }
        elif event is not None:
            ccg = {"ccgDate": event.get("date"), "ccgTime": event.get("time") or "12:00:00", "ccgMix": payload.get("ccgMix") or "transit"}
        remote_payload = self._acg_remote_params(payload, ccg)
        response = self._call_remote("/location/acg", remote_payload)
        meta = response.get("meta") if isinstance(response.get("meta"), dict) else {}
        for key in self._ACG_META_ECHO:
            asked = payload.get(key)
            if asked in (None, "") or key not in meta:
                continue
            effective = meta.get(key)
            if f"{asked}".lower() != f"{effective}".lower():
                _degrade(
                    "acg: %s=%r not accepted by engine (effective %r)", key, asked, effective,
                    note=f"占星地图 {key}={asked!r} 引擎不认，已按 {effective!r} 计算（ACGraph 值域见 horosa_agent_guidance）。",
                )
        planets = response.get("planets") if isinstance(response.get("planets"), dict) else {}
        # 上游 locastro 是**辅盘 tab**：导出走 extractAstroContent（与 astrochart 逐字同一套本命盘段），
        # 再把地图段拼在尾巴上。这里补拉一次 /chart 并复用通用盘面渲染器；失败只是盘段不出，地图段照常。
        # 本命盘的口径 = 页面同一套 fields（黄道/岁差/宫制/古典全局键），不是只有经纬时区（此前只传 7 键）。
        chart_body = ""
        try:
            chart_payload = {k: v for k, v in payload.items() if k not in self._ACG_ONLY_KEYS}
            chart_payload["predictive"] = 0
            chart_response = self._call_remote("/chart", {k: v for k, v in chart_payload.items() if v is not None})
            if _is_astro_chart_payload(chart_response):
                chart_response = self._attach_natal_extras("chart", chart_response, payload)
                chart_response = self._attach_classical_analysis("chart", chart_payload, chart_response)
                chart_body = _build_astro_snapshot_text(chart_payload, chart_response)
        except Exception as exc:  # noqa: BLE001 — 盘面富化失败不许带崩地图段
            _degrade("acg natal chart fetch failed: %s", exc)
        acg_data: dict[str, Any] = {
            "meta": meta,
            "planets": planets,
            "parans": response.get("parans") if isinstance(response.get("parans"), list) else [],
            "crossings": response.get("crossings") if isinstance(response.get("crossings"), list) else [],
        }
        # [落点分析]（/location/acgpoint）：上游 onMapClick = { ...genParams(), clickLat, clickLon, orb, hsys }（:337）。
        point: dict[str, Any] | None = None
        if payload.get("clickLat") is not None and payload.get("clickLon") is not None:
            point_remote = {
                **remote_payload,
                "clickLat": payload.get("clickLat"),
                "clickLon": payload.get("clickLon"),
                "orb": payload.get("pointOrb") if payload.get("pointOrb") is not None else 2,
            }
            point = self._call_remote("/location/acgpoint", point_remote)
            if not isinstance(point, dict) or not isinstance(point.get("relocAngles"), dict):
                raise ToolTransportError(
                    "落点分析端点返回了意外形状。",
                    code="tool.acg_point_failed",
                    details={"endpoint": "/location/acgpoint"},
                )
            acg_data["point"] = point
        # [占星地图]：上游 buildAcgSectionText（vendored 逐字；JS acg_section）。uiState 与页面 snapshotUiState 同形。
        ui_state = {
            "pointReport": point,
            "paranMode": payload.get("paranMode") or "off",
            "showStarParans": self._acg_flag(payload.get("stars")) == "1" and self._acg_flag(payload.get("showStarParans")) == "1",
            "showLS": self._acg_flag(payload.get("showLS")) == "1",
            "showGeodetic": self._acg_flag(payload.get("showGeodetic")) == "1",
            "geodeticZero": f"{payload.get('geodeticZero') if payload.get('geodeticZero') is not None else ''}",
        }
        map_text = ""
        try:
            js = self.js_client.run("acg_section", {"acgData": response, "uiState": ui_state})
            map_text = f"{(js or {}).get('text') or ''}".strip()
        except Exception as exc:  # noqa: BLE001 — 段 builder 失败：地图段缺席并说出来
            _degrade("acg section build failed: %s", exc, note=f"占星地图 [占星地图] 段本次未产出（JS 段 builder 失败：{exc}），其余段不受影响。")
        # 上游段头是全角 `【占星地图】`（aiExport 的段名解析两种括号等价）；本仓统一以 `[X]` 渲染，正文逐字。
        map_body = map_text.split("\n", 1)[1] if map_text.startswith("【占星地图】\n") else map_text
        sections: list[tuple[str, str]] = []
        if map_body.strip():
            sections.append(("占星地图", map_body.strip()))
        parans = acg_data["parans"]
        if parans:
            rows = [f"偕升纬度带（同纬度两星同时临角，前 {min(len(parans), 40)}/{len(parans)} 条）："]
            for item in parans[:40]:
                if isinstance(item, dict):
                    rows.append(
                        f"纬 {item.get('lat')}°：{_astro_msg(item.get('a'), short=True)}·{item.get('aEvent')} × "
                        f"{_astro_msg(item.get('b'), short=True)}·{item.get('bEvent')}（{item.get('type')}）"
                    )
            sections.append(("偕升纬度带", "\n".join(rows)))
        crossings = acg_data["crossings"]
        if crossings:
            rows = [f"线交点（一星临 MC/IC 直线 × 一星临 ASC/DESC 曲线，前 {min(len(crossings), 40)}/{len(crossings)} 处）："]
            for item in crossings[:40]:
                if isinstance(item, dict):
                    a = _astro_msg(item.get("a"), short=True)
                    b = _astro_msg(item.get("b"), short=True)
                    # 源 _crossings 返回键：a/aAngle(mc|ic) × b/bAngle(asc|desc)。角色标签取 aAngle/bAngle。
                    a_ang = item.get("aAngle") or ""
                    b_ang = item.get("bAngle") or ""
                    lat_v, lon_v = item.get("lat"), item.get("lon")
                    lat_txt = f"{float(lat_v):.2f}°" if isinstance(lat_v, (int, float)) else "—"
                    rows.append(f"{a}·{a_ang} × {b}·{b_ang}：纬 {lat_txt}，经 {geo_lon(lon_v)}")
            sections.append(("线交点", "\n".join(rows)))
        if point is not None:
            point_lines = [
                f"落点：纬 {point.get('lat')}°，经 {geo_lon(point.get('lon'))}　容许度 {_round3(point.get('orb'))}°　"
                f"重置盘分宫制 {point.get('hsys')}",
            ]
            hits = point.get("hits") if isinstance(point.get("hits"), list) else []
            if hits:
                point_lines.append("命中线（该地临角的星）：")
                for hit in hits:
                    if isinstance(hit, dict):
                        point_lines.append(
                            f"{_astro_msg(hit.get('planet'), short=True)} 临 {hit.get('angle')}（距 {_round3(hit.get('orb'))}°）"
                        )
            else:
                point_lines.append("命中线：容许度内无星临角。")
            reloc = point.get("relocAngles") or {}
            point_lines.append(
                "重置四角：" + "　".join(f"{k} {_sign_degree(v)}" for k, v in reloc.items() if v is not None)
            )
            sensitive = point.get("sensitive") if isinstance(point.get("sensitive"), dict) else {}
            if sensitive:
                sens_cn = {
                    "vertex": "宿命点", "eastpoint": "东升点", "coasc_koch": "共升点(Koch)",
                    "coasc_munkasey": "共升点(Munkasey)", "polarasc": "极地上升",
                    "antiscia_mc": "映点MC", "antiscia_asc": "映点ASC",
                }
                point_lines.append(
                    "敏感点：" + "　".join(
                        f"{sens_cn.get(k, k)} {_sign_degree(v)}" for k, v in sensitive.items() if v is not None
                    )
                )
            sections.append(("落点分析", "\n".join(point_lines)))
        if event is not None:
            acg_data["event"] = event
            kind_cn = {
                "solar_eclipse": "日食", "lunar_eclipse": "月食", "newmoon": "新月", "fullmoon": "满月",
                "aries_ingress": "白羊入境（春分）", "cancer_ingress": "巨蟹入境（夏至）",
                "libra_ingress": "天秤入境（秋分）", "capricorn_ingress": "摩羯入境（冬至）",
            }.get(str(event.get("kind")), str(event.get("kind")))
            zone_text = event.get("zone") or "+00:00"
            # 时刻按请求时区的钟面回（后端带回 zone；没带 zone 的旧后端 = UT）。
            zone_label = "UTC" if zone_text in ("+00:00", "0", 0) else f"{zone_text}"
            ccg_note = "；已填入 CCG 全行运通道（事件时刻角化线见 [占星地图]）" if ccg and not payload.get("ccgDate") else ""
            sections.append((
                "事件时刻",
                f"{kind_cn}（{payload.get('eventDirection') or 'next'}）：{event.get('date')} {event.get('time')} {zone_label}{ccg_note}",
            ))
        # 段序对齐上游：本命盘段在前、[占星地图] 及其明细在后。
        snapshot_text = _render_snapshot_text(sections)
        if chart_body:
            snapshot_text = f"{chart_body}\n{snapshot_text}"
        return {
            "acg": acg_data,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="acg", snapshot_text=snapshot_text),
        }

    # ── 名人星盘数据库（离线只读检索）────────────────────────────────────────────
    _ASTRODATA_RELATIVE = Path("Horosa-Web/astrostudyui/dist-file/astrodata/astrodata-aa.sqlite.gz")

    def _astrodata_db_path(self) -> Path | None:
        # 定位序列：显式 env → 已安装 runtime → 仓内 vendored 源快照（开发/live 测试）。
        env_path = os.environ.get("HOROSA_ASTRODATA_DB")
        candidates: list[Path] = []
        if env_path:
            candidates.append(Path(env_path).expanduser())
        try:
            candidates.append(Path(self.runtime_manager.current_dir) / self._ASTRODATA_RELATIVE)
        except Exception:  # noqa: BLE001 - runtime manager optional in offline tests
            pass
        # src/horosa_skill/service.py → parents[3] = 仓根（vendor/runtime-source 所在）。
        candidates.append(Path(__file__).resolve().parents[3] / "vendor" / "runtime-source" / self._ASTRODATA_RELATIVE)
        for cand in candidates:
            if cand.is_file():
                return cand
        return None

    def _astrodata_connect(self) -> sqlite3.Connection | None:
        source = self._astrodata_db_path()
        if source is None:
            return None
        db_path = source
        if source.suffix == ".gz":
            cache_dir = Path(self.settings.runtime_root) / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            cached = cache_dir / "astrodata-aa.sqlite"
            stamp = cache_dir / "astrodata-aa.sqlite.src"
            src_sig = f"{source}|{source.stat().st_size}|{int(source.stat().st_mtime)}"
            stamp_ok = stamp.is_file() and stamp.read_text(encoding="utf-8").strip() == src_sig
            if not cached.is_file() or not stamp_ok:
                # 原子 + 流式解压：写唯一临时文件（进程/线程隔离，避免并发交错写撕裂 122MB 库），
                # copyfileobj 分块拷贝（不 fin.read() 整库进内存），成功后 os.replace 原子落位，
                # 最后才写 stamp —— 中断/并发都不会留下被当成有效的截断库。
                tmp = cache_dir / f".astrodata-aa.sqlite.{os.getpid()}.{uuid.uuid4().hex}.tmp"
                try:
                    with gzip.open(source, "rb") as fin, open(tmp, "wb") as fout:
                        shutil.copyfileobj(fin, fout, length=1024 * 1024)
                    os.replace(tmp, cached)
                    stamp.write_text(src_sig, encoding="utf-8")
                finally:
                    if tmp.exists():
                        tmp.unlink(missing_ok=True)
            db_path = cached
        # as_uri() 正确百分号编码路径（含空格/%/#/Windows 反斜杠+盘符），勿裸 f-string 拼接。
        con = sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        return con

    @staticmethod
    def _astrodata_row_get(row: sqlite3.Row, key: str, default: Any = None) -> Any:
        # sqlite3.Row 无 .get；对缺列（老库 schema）安全取值，避免裸 row[key] 抛 IndexError。
        try:
            return row[key]
        except (IndexError, KeyError):
            return default

    @classmethod
    def _astrodata_person_brief(cls, row: sqlite3.Row) -> dict[str, Any]:
        # v3.3.2 中文化：优先中文列（name_zh/pos_zh/born_zh），缺则回退英文，与上游前端 nm/ps 同口径。
        g = cls._astrodata_row_get
        name_zh = g(row, "name_zh")
        pos_zh = g(row, "pos_zh")
        born_zh = g(row, "born_zh")
        return {
            "title": row["title"],
            "name": g(row, "name"),
            "nameZh": name_zh or None,
            "nameDisplay": name_zh or g(row, "name"),
            "born": g(row, "born_display"),
            "bornDisplay": born_zh or g(row, "born_display"),
            "rodden": g(row, "rodden"),
            "sun": g(row, "sun"),
            "moon": g(row, "moon"),
            "asc": g(row, "asc"),
            "pos": g(row, "pos"),
            "posDisplay": pos_zh or g(row, "pos"),
            "hasTime": bool(g(row, "has_time", 0)),
        }

    @classmethod
    def _astrodata_has_column(cls, con: sqlite3.Connection, table: str, column: str) -> bool:
        try:
            return any(r[1] == column for r in con.execute(f"PRAGMA table_info({table})"))
        except sqlite3.Error:
            return False

    # 玄史 action → 端点全路径（存字面量：端点登记守卫按字面调用点核对）与该端点**真读**的参数名。
    # 🔴 sync311 F13：参数名逐端点对齐 webxuanshisrv.py 的 `_str/_int/_bool(d, "<键>")`——此前 figure/technique/
    # term/dynasty/story 发 `id` 而后端只读 `slug`（恒 null）、term_profile 要 `omen`、microchronology 发
    # dynasty/年段而后端读 history/omen_type/decade、figures/stories 发 page/page_size 而后端读 limit/offset、
    # celestial 丢了 q/has_crosswalk/in_chapter。离线桩当时对每个端点回同一份数据，所以一条都红不了。
    #   * slug 族：payload.slug（逃生舱）> id > q（名称/slug 皆可由 q 兜）；
    #   * term_profile：omen > q > id（后端读 omen/label）；
    #   * figures/stories 的 page/page_size 折算成 limit/offset（显式 limit/offset 优先）。
    _XUANSHI_ACTIONS: dict[str, tuple[str, tuple[str, ...]]] = {
        "search": ("/xuanshi/search", ("q", "limit", "tradition")),  # :514-516
        "events": ("/xuanshi/events", ("q", "tradition", "dynasty", "technique", "history", "evidence", "page", "page_size")),  # :114-124
        "event": ("/xuanshi/event", ("id",)),  # :138（event_id / id 双认）
        "celestial": ("/xuanshi/celestial", ("dynasty", "omen", "history", "source", "year_from", "year_to", "has_crosswalk", "in_chapter", "q", "page", "page_size")),  # :155-165（q→keyword）
        "celestial_event": ("/xuanshi/celestial_event", ("id",)),  # :179
        "figures": ("/xuanshi/figures", ("q", "dynasty", "limit", "offset")),  # :241-244
        "figure": ("/xuanshi/figure", ("slug",)),  # :268
        "dynasties": ("/xuanshi/dynasties", ()),
        "dynasty": ("/xuanshi/dynasty", ("slug",)),  # :358
        "techniques": ("/xuanshi/techniques", ()),
        "technique": ("/xuanshi/technique", ("slug",)),  # :300
        "terms": ("/xuanshi/celestial_terms", ()),
        "term": ("/xuanshi/celestial_term", ("slug",)),  # :329
        "term_profile": ("/xuanshi/celestial_term_profile", ("omen",)),  # :222
        "timeline": ("/xuanshi/timeline", ("macro", "limit")),  # :456-458
        "map": ("/xuanshi/map", ("period",)),  # :426
        "graph": ("/xuanshi/persons_graph", ("top_n", "min_weight")),  # :441-442
        "stories": ("/xuanshi/stories", ("q", "dynasty", "limit", "offset")),  # :375-382（q→search_text）
        "story": ("/xuanshi/story", ("slug",)),  # :396
        "channels": ("/xuanshi/channels", ()),
        "daily": ("/xuanshi/daily", ("date_key",)),  # :530
        "summary": ("/xuanshi/summary", ()),
        "microchronology": ("/xuanshi/microchronology", ("history", "omen", "decade")),  # :193-195（omen→omen_type）
        "decade_omens": ("/xuanshi/decade_omens", ()),  # :204-210 无参
        "facets": ("/xuanshi/facets", ("tradition", "q", "dynasty", "technique", "history", "evidence")),  # :491-496
        "events_meta": ("/xuanshi/events_meta", ("tradition",)),  # :477
    }

    def _run_xuanshi_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        """玄史知识库检索：runtime 自带的只读 SQLite bundle，经 chart 服务 /xuanshi/* 端点查询。

        纯检索、无结果敏感设置；按 action 分派到 26 个端点之一。快照四段与 astrodata 同范式：
        [检索条件] 恒出；[结果总览]/[条目列表]/[条目详情] 按响应形状条件产出（列表响应出总览+列表，
        详情响应出详情）；[出处引证] 聚合条目里的 citation。
        """
        action = f"{payload.get('action') or 'search'}".strip() or "search"
        spec = self._XUANSHI_ACTIONS.get(action)
        if spec is None:
            raise ToolValidationError(
                f"Unknown xuanshi action: {action!r}",
                code="tool.invalid_argument",
                details={"allowed_actions": sorted(self._XUANSHI_ACTIONS)},
            )
        path, keys = spec
        source = dict(payload)
        if "slug" in keys and source.get("slug") is None:
            source["slug"] = source.get("id") if source.get("id") is not None else source.get("q")
        if action == "term_profile" and source.get("omen") is None:
            source["omen"] = source.get("q") if source.get("q") is not None else source.get("id")
        if "offset" in keys and source.get("limit") is None and source.get("page_size") is not None:
            source["limit"] = source.get("page_size")
        if "offset" in keys and source.get("offset") is None and source.get("page") is not None:
            size = source.get("limit") if source.get("limit") is not None else 30
            source["offset"] = max(0, (int(source["page"]) - 1) * int(size))
        body = {k: source.get(k) for k in keys if source.get(k) is not None}
        response = self._call_remote(path, body)
        snapshot_text = _build_xuanshi_snapshot_text(action, body, response)
        return {
            "action": action,
            "xuanshi": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="xuanshi", snapshot_text=snapshot_text),
        }

    def _run_bazi_inverse_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        """八字反查（Java /common/inversebazi）：四柱干支 → 候选公历出生时刻。

        上游契约（CommController.inverseBazi / BaZiHelper.getBirthes）：Year/Month/Date/Time 四柱干支，
        Count 条数，Desc=true 从 FromYear 向过去逐年回推；返回 Dates=["YYYY-MM-DD HH:mm:ss", …]。
        """
        pillars = payload.get("pillars")
        if not isinstance(pillars, list) or len(pillars) != 4:
            pillars = [payload.get("year"), payload.get("month"), payload.get("day"), payload.get("hour")]
        cleaned = [f"{item or ''}".strip() for item in pillars]
        bad = [item for item in cleaned if len(item) != 2 or item[0] not in _GANZHI_STEMS or item[1] not in _GANZHI_BRANCHES]
        if bad or len(cleaned) != 4:
            raise ToolValidationError(
                bilingual("八字反查需要四柱干支（年/月/日/时各一组，如 甲子）。", "bazi_inverse needs four ganzhi pillars (year/month/day/hour, e.g. 甲子)."),
                code="tool.bazi_inverse_invalid_pillars",
                details={"pillars": cleaned, "invalid": bad, "hint": "pillars=['甲子','丙寅','戊辰','庚申'] 或 year/month/day/hour 四键"},
            )
        count = payload.get("count")
        try:
            count = max(1, min(10, int(count if count is not None else 3)))
        except (TypeError, ValueError):
            count = 3
        desc = payload.get("desc")
        desc = True if desc is None else bool(desc)
        remote_payload: dict[str, Any] = {
            "Year": cleaned[0], "Month": cleaned[1], "Date": cleaned[2], "Time": cleaned[3],
            "Count": count, "Desc": desc,
        }
        from_year = payload.get("fromYear")
        if from_year is not None:
            remote_payload["FromYear"] = int(from_year)
        response = self._call_remote("/common/inversebazi", remote_payload)
        dates = response.get("Dates") if isinstance(response, dict) else None
        candidates = []
        for item in dates or []:
            text = f"{item}".strip()
            if not text:
                continue
            date_part, _, time_part = text.partition(" ")
            candidates.append({"datetime": text, "date": date_part.replace("/", "-"), "time": time_part or None})
        condition_lines = [
            f"四柱：{' '.join(cleaned)}",
            f"回推方向：{'向过去' if desc else '向未来'}；起始年：{from_year if from_year is not None else '后端当前年'}；数量：{count}",
        ]
        candidate_lines = [f"{index}. {c['datetime']}" for index, c in enumerate(candidates, start=1)]
        snapshot_text = _render_snapshot_text([
            ("反查条件", "\n".join(condition_lines)),
            ("候选时刻", "\n".join(candidate_lines) if candidate_lines else "无（该四柱在起始年前后未找到匹配时刻）"),
            ("口径说明", "候选由后端按四柱干支自起始年起逐年匹配（BaZiHelper.getBirthes）；同一四柱约每 60 年重现；时刻取该时辰的代表时间，实际排盘请以候选时刻附近的真实钟表时间与地点重新起盘。"),
        ])
        return {
            "bazi_inverse": {"pillars": cleaned, "count": count, "desc": desc, "fromYear": from_year, "candidates": candidates},
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="bazi_inverse", snapshot_text=snapshot_text),
        }

    def _run_astrodata_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        con = self._astrodata_connect()
        if con is None:
            # 数据库缺席（如精简部署）：如实降级，不臆造。
            snapshot_text = _render_snapshot_text([
                ("检索条件", "名人星盘数据库文件不在本地部署中，本次无法检索；可安装完整离线 runtime 后重试。"),
            ])
            return {
                "astrodata": {"available": False, "results": []},
                "snapshot_text": snapshot_text,
                "export_snapshot": self._augment_export_payload(technique="astrodata", snapshot_text=snapshot_text),
                "_warnings": ["名人星盘数据库文件缺席，返回降级说明。"],
            }
        try:
            person_title = f"{payload.get('personTitle') or ''}".strip()
            if person_title:
                row = con.execute("SELECT * FROM person WHERE title = ?", (person_title,)).fetchone()
                if row is None:
                    snapshot_text = _render_snapshot_text([
                        ("检索条件", f"条目：{person_title}"),
                        ("名人详情", "库内无此条目；请先用 query 检索取得精确 title。"),
                    ])
                    return {
                        "astrodata": {"available": True, "person": None},
                        "snapshot_text": snapshot_text,
                        "export_snapshot": self._augment_export_payload(technique="astrodata", snapshot_text=snapshot_text),
                    }
                cats = [r["category"] for r in con.execute(
                    "SELECT category FROM category WHERE person_title = ? LIMIT 30", (person_title,))]
                g = self._astrodata_row_get
                birth_chart = f"{row['birth_chart'] or ''}".strip()
                birth_date, _, birth_time = birth_chart.partition(" ")
                # v3.3.2 中文化：详情优先中文列，缺则回退英文。
                name_disp = g(row, "name_zh") or g(row, "name")
                born_disp = g(row, "born_zh") or g(row, "born_display")
                pos_disp = g(row, "pos_zh") or g(row, "pos")
                summary_disp = g(row, "summary_zh") or g(row, "wiki_summary")
                person = {
                    **self._astrodata_person_brief(row),
                    "gender": g(row, "gender"),
                    "zone": g(row, "zone"),
                    "lat": g(row, "lat"),
                    "lon": g(row, "lon"),
                    "gpsLat": g(row, "gpsLat"),
                    "gpsLon": g(row, "gpsLon"),
                    "birthDate": birth_date or None,
                    "birthTime": birth_time or None,
                    "timeAccuracy": g(row, "time_accuracy"),
                    "adbUrl": g(row, "adb_url"),
                    "wikiUrl": g(row, "wiki_url"),
                    "summaryZh": g(row, "summary_zh") or None,
                    "categories": cats,
                }
                detail_lines = [
                    f"{name_disp}（{row['title']}）",
                    f"出生：{born_disp or '—'}　评级（Rodden）：{g(row, 'rodden') or '—'}　时刻精度：{g(row, 'time_accuracy') or '—'}",
                    f"地点：{pos_disp or '—'}　坐标：{g(row, 'lat')} / {g(row, 'lon')}　时区：{g(row, 'zone')}",
                    f"排盘入参：date={birth_date or '—'} time={birth_time or '—'} zone={g(row, 'zone')} lat={g(row, 'lat')} lon={g(row, 'lon')}",
                    f"星盘三要：日 {g(row, 'sun') or '—'} / 月 {g(row, 'moon') or '—'} / 升 {g(row, 'asc') or '—'}",
                ]
                if cats:
                    detail_lines.append("分类：" + "；".join(cats[:12]) + ("…" if len(cats) > 12 else ""))
                wiki = f"{summary_disp or ''}".strip()
                sections = [
                    ("检索条件", f"条目：{person_title}"),
                    ("名人详情", "\n".join(detail_lines)),
                ]
                if wiki:
                    sections.append(("维基摘要", wiki[:1200] + ("…" if len(wiki) > 1200 else "")))
                sections.append((
                    "数据来源",
                    "出生数据：Astro-Databank / Astrodienst AG（非商业研究用途，保留 Rodden 评级与来源链接）；"
                    f"传记摘要：Wikipedia（CC BY-SA 4.0）。{row['adb_url'] or ''} {row['wiki_url'] or ''}".strip(),
                ))
                snapshot_text = _render_snapshot_text(sections)
                return {
                    "astrodata": {"available": True, "person": person},
                    "snapshot_text": snapshot_text,
                    "export_snapshot": self._augment_export_payload(technique="astrodata", snapshot_text=snapshot_text),
                }

            query = f"{payload.get('query') or ''}".strip()
            category = f"{payload.get('category') or ''}".strip()
            rodden_raw = payload.get("rodden")
            rodden = [r for r in ([rodden_raw] if isinstance(rodden_raw, str) else (rodden_raw or [])) if f"{r}".strip()]
            try:
                limit = max(1, min(100, int(payload.get("limit") or 20)))
            except (TypeError, ValueError):
                limit = 20
            try:
                offset = max(0, int(payload.get("offset") or 0))
            except (TypeError, ValueError):
                offset = 0

            def _like_escape(text: str) -> str:
                return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

            where: list[str] = []
            params: list[Any] = []
            base = "FROM person p"
            has_zh = self._astrodata_has_column(con, "person", "name_zh")
            has_catzh = self._astrodata_has_column(con, "category_zh", "en")
            if query:
                # 多列 LIKE 检索（对齐 v3.3.2 前端：name_zh/name/title/pos_zh/summary_zh），支持中文名/
                # 中文地点；FTS 只索引英文列，中文查询会静默返回空，故不用 FTS 走 LIKE（离线库规模可承受）。
                cols = ["p.name", "p.title", "p.pos"]
                if has_zh:
                    cols = ["p.name_zh", "p.name", "p.title", "p.pos_zh", "p.summary_zh"]
                pat = f"%{_like_escape(query)}%"
                where.append("(" + " OR ".join(f"{c} LIKE ? ESCAPE '\\' COLLATE NOCASE" for c in cols) + ")")
                params.extend(pat for _ in cols)
            if category:
                safe_cat = _like_escape(category)
                if has_catzh:
                    # 中文分类：category_zh(en→zh) 映射，匹配 zh 或英文原名（对齐前端 LEFT JOIN category_zh）。
                    where.append(
                        "p.title IN (SELECT c.person_title FROM category c "
                        "LEFT JOIN category_zh z ON z.en = c.category "
                        "WHERE z.zh LIKE ? ESCAPE '\\' COLLATE NOCASE OR c.category LIKE ? ESCAPE '\\' COLLATE NOCASE)"
                    )
                    params.extend([f"%{safe_cat}%", f"%{safe_cat}%"])
                else:
                    where.append("p.title IN (SELECT person_title FROM category WHERE category LIKE ? ESCAPE '\\')")
                    params.append(f"%{safe_cat}%")
            if rodden:
                where.append(f"p.rodden IN ({','.join('?' for _ in rodden)})")
                params.extend(str(r).upper() for r in rodden)
            if payload.get("birthYearFrom") is not None:
                where.append("p.birth_year >= ?")
                params.append(int(payload["birthYearFrom"]))
            if payload.get("birthYearTo") is not None:
                where.append("p.birth_year <= ?")
                params.append(int(payload["birthYearTo"]))
            if payload.get("hasTimeOnly"):
                where.append("p.has_time = 1")
            where_sql = (" WHERE " + " AND ".join(where)) if where else ""
            order_sql = " ORDER BY p.name_zh, p.name" if has_zh else " ORDER BY p.name"
            total = con.execute(f"SELECT COUNT(*) {base}{where_sql}", params).fetchone()[0]
            rows = con.execute(
                f"SELECT p.* {base}{where_sql}{order_sql} LIMIT ? OFFSET ?", [*params, limit, offset]
            ).fetchall()
            results = [self._astrodata_person_brief(r) for r in rows]
            cond_bits = [bit for bit in (
                f"全文：{query}" if query else "",
                f"分类：{category}" if category else "",
                f"评级：{'/'.join(str(r).upper() for r in rodden)}" if rodden else "",
                f"生年：{payload.get('birthYearFrom') or '…'}–{payload.get('birthYearTo') or '…'}" if (payload.get("birthYearFrom") is not None or payload.get("birthYearTo") is not None) else "",
                "仅含出生时刻" if payload.get("hasTimeOnly") else "",
            ) if bit]
            head = [
                "、".join(cond_bits) if cond_bits else "（无过滤条件）",
                f"命中 {total} 条，返回第 {offset + 1}–{offset + len(results)} 条。",
            ]
            if results:
                rows_txt = ["| 姓名 | 出生 | 评级 | 日/月/升 | 条目 |", "| --- | --- | --- | --- | --- |"]
                for item in results:
                    tri = f"{item['sun'] or '—'}/{item['moon'] or '—'}/{item['asc'] or '—'}"
                    name_disp = item.get("nameDisplay") or item.get("name")
                    born_disp = item.get("bornDisplay") or item.get("born")
                    rows_txt.append(f"| {name_disp} | {born_disp or '—'} | {item['rodden'] or '—'} | {tri} | {item['title']} |")
                body = "\n".join(rows_txt) + "\n用 personTitle=<条目> 取单人详情（含可直接排盘的出生数据）。"
            else:
                body = "无命中；可放宽检索词或分类（支持中文与英文原名）。"
            snapshot_text = _render_snapshot_text([
                ("检索条件", "\n".join(head)),
                ("命中列表", body),
            ])
            return {
                "astrodata": {"available": True, "total": total, "results": results, "offset": offset, "limit": limit},
                "snapshot_text": snapshot_text,
                "export_snapshot": self._augment_export_payload(technique="astrodata", snapshot_text=snapshot_text),
            }
        except sqlite3.Error as exc:
            # 老版本库缺 person_fts / birth_year·has_time 列，或检索式仍非法 → 优雅降级，不让整工具 ok=False。
            _degrade("astrodata query failed: %s", exc)
            snapshot_text = _render_snapshot_text([
                ("检索条件", "名人库检索未能完成（数据库版本过旧或检索式无效）；请改用英文姓名关键词，或更新离线 runtime。"),
            ])
            return {
                "astrodata": {"available": True, "results": [], "error": "query_failed"},
                "snapshot_text": snapshot_text,
                "export_snapshot": self._augment_export_payload(technique="astrodata", snapshot_text=snapshot_text),
                "_warnings": [f"名人库检索降级：{exc}"],
            }
        finally:
            con.close()

    def _run_yizhangjing_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 一掌经：原生·非 ken 工具，JS 进程内完成 农历解析→四柱四宫→命宫/人事十二宫→格局/重犯/
        # 大限/小限流年十二神（+可选神煞合参层），返回引擎自产快照（段头已转 [段名]）。
        js_result = self.js_client.run("yizhangjing", payload)
        snapshot_text = js_result.get("snapshot_text")
        return {
            "yizhangjing": js_result.get("data", {}),
            "input_normalized": js_result.get("input_normalized", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="yizhangjing", snapshot_text=snapshot_text),
        }

    def _run_xiaoliuren_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 小六壬：三数起三传（主流六宫/道门九宫）。起课为冻结值——显式 nums 优先；缺 nums 则按占时正统起
        # （农历月 monthInt / 农历日 dayInt / 时支序 三数，前置 /nongli/time 派生，JS 层不发 HTTP，AGENTS §4）。
        nums = payload.get("nums")
        time_lines: list[str] = []
        if not (isinstance(nums, list) and len(nums) == 3):
            _require_cast_geo(payload, tool="xiaoliuren")
            nongli = self._call_remote(
                "/nongli/time",
                {
                    "date": payload["date"],
                    "time": payload["time"],
                    "zone": payload["zone"],
                    "lon": payload.get("lon"),
                    # 🔴 timeAlg 必须转发：真太阳时会改时支（经度差 >7.5° 即可跨支），
                    # 时支一变卦局/起支全变。qimen/taiyi/zhengchuan 三处一直在转发，端点
                    # 明确支持；这几处漏了 → 同一份入参在不同技法间起出不同的盘。
                    "timeAlg": payload.get("timeAlg"),
                    "lat": payload.get("lat"),
                    **_day_boundary_switches(payload),
                },
            )
            month_int = nongli.get("monthInt") if isinstance(nongli, dict) else None
            day_int = nongli.get("dayInt") if isinstance(nongli, dict) else None
            hour_gz = str(nongli.get("time") or "") if isinstance(nongli, dict) else ""
            hour_zhi = hour_gz[1] if len(hour_gz) >= 2 else ""
            hour_idx = (_SIXYAO_DIZHI.index(hour_zhi) + 1) if hour_zhi in _SIXYAO_DIZHI else None
            if not (month_int and day_int and hour_idx):
                raise ToolValidationError(
                    "小六壬占时起数失败：无法从 /nongli/time 取得 农历月/日/时支。请显式给 nums=[月,日,时] 或提供完整 date/time。",
                    code="tool.xiaoliuren_cast_unavailable",
                    details={"monthInt": month_int, "dayInt": day_int, "hourZhi": hour_zhi},
                )
            nums = [month_int, day_int, hour_idx]
            time_lines = [
                f"起卦时间:{payload.get('date')} {payload.get('time')}",
                f"农历:{month_int}月{day_int}日 {hour_zhi}时（时支序{hour_idx}）",
            ]
        js_result = self.js_client.run(
            "xiaoliuren",
            {
                "nums": nums,
                "school": payload.get("school", "main"),
                "showOneThree": payload.get("showOneThree", True),
                "askEvent": payload.get("askEvent") or payload.get("question") or "",
                "timeLines": time_lines,
            },
        )
        snapshot_text = js_result.get("snapshot_text")
        return {
            "xiaoliuren": js_result.get("data", {}),
            "input_normalized": js_result.get("input_normalized", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="xiaoliuren", snapshot_text=snapshot_text),
        }

    def _run_feigong_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 飞宫小奇门：起支 + 日干支定局（冻结）。显式 qiZhi/dayGan/dayZhi 优先；缺则占时起
        # （/nongli/time → 时支作起支 + 日干支），JS 层不发 HTTP（AGENTS §4）。
        qi_mode = payload.get("qiMode", "hour")
        day_gan = payload.get("dayGan")
        day_zhi = payload.get("dayZhi")
        hour_zhi = payload.get("hourZhi")
        time_lines: list[str] = []
        need_hour = qi_mode == "hour" and not payload.get("qiZhi") and not hour_zhi
        if (not day_gan or not day_zhi or need_hour) and payload.get("date"):
            _require_cast_geo(payload, tool="feigong")
            nongli = self._call_remote(
                "/nongli/time",
                {
                    "date": payload["date"],
                    "time": payload.get("time"),
                    "zone": payload.get("zone"),
                    "lon": payload.get("lon"),
                    # 🔴 timeAlg 必须转发：真太阳时会改时支（经度差 >7.5° 即可跨支），
                    # 时支一变卦局/起支全变。qimen/taiyi/zhengchuan 三处一直在转发，端点
                    # 明确支持；这几处漏了 → 同一份入参在不同技法间起出不同的盘。
                    "timeAlg": payload.get("timeAlg"),
                    "lat": payload.get("lat"),
                    **_day_boundary_switches(payload),
                },
            )
            if isinstance(nongli, dict):
                day_gz = str(nongli.get("dayGanZi") or "")
                if len(day_gz) >= 2:
                    day_gan = day_gan or day_gz[0]
                    day_zhi = day_zhi or day_gz[1]
                hour_gz = str(nongli.get("time") or "")
                if len(hour_gz) >= 2 and not hour_zhi:
                    hour_zhi = hour_gz[1]
                time_lines = [
                    f"起卦时间:{payload.get('date')} {payload.get('time') or ''}".strip(),
                    f"农历:{nongli.get('monthInt')}月{nongli.get('dayInt')}日 {hour_zhi}时",
                ]
        js_result = self.js_client.run(
            "feigong",
            {
                "qiMode": qi_mode,
                "qiZhi": payload.get("qiZhi"),
                "hourZhi": hour_zhi,
                "zhi": payload.get("zhi"),
                "num": payload.get("num"),
                "yearZhi": payload.get("yearZhi"),
                "dayGan": day_gan,
                "dayZhi": day_zhi,
                "mingAge": payload.get("mingAge"),
                "mingGender": payload.get("mingGender", "male"),
                "liuYueMonth": payload.get("liuYueMonth"),
                "koujing": payload.get("koujing", "zheng"),
                "askEvent": payload.get("askEvent") or payload.get("question") or "",
                "timeLines": time_lines,
            },
        )
        data = js_result.get("data", {})
        if isinstance(data, dict) and data.get("ok") is False:
            raise ToolValidationError(
                "飞宫小奇门起局失败：无法定起支/日干支。请显式给 qiZhi + dayGan + dayZhi，或提供完整 date/time 按占时起局。",
                code="tool.feigong_cast_unavailable",
                details={"reason": data.get("reason"), "qiMode": qi_mode},
            )
        snapshot_text = js_result.get("snapshot_text")
        return {
            "feigong": data,
            "input_normalized": js_result.get("input_normalized", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="feigong", snapshot_text=snapshot_text),
        }

    def _run_xiaochengtu_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 小成图：五式起卦（manual/number/stock/dayan/time）。卦为冻结值。占时=梅花时间卦：Python 前置
        # /nongli/time 算 upNum=年支序+农历月+日、loNum=upNum+时支序（镜像上游·之卦=本卦不加动爻），
        # 以 number 模式喂 JS（JS 不发 HTTP，AGENTS §4）。
        fa = payload.get("qiguaFa", "manual")
        request: dict[str, Any] = {
            "qiguaFa": fa,
            "up": payload.get("up"),
            "lo": payload.get("lo"),
            "dongYaos": payload.get("dongYaos"),
            "upNum": payload.get("upNum"),
            "loNum": payload.get("loNum"),
            "qiguaShu": payload.get("qiguaShu", "tiandi"),
            "open": payload.get("open"),
            "close": payload.get("close"),
            "seed": payload.get("seed"),
            "manualCounts": payload.get("manualCounts"),
            "yongGong": payload.get("yongGong", 1),
            "kline": payload.get("kline"),
            "askEvent": payload.get("askEvent") or payload.get("question") or "",
            # 闢卦细判口径（上游挂载 schema xiaochengtu.piKoujing：zheng 正传缺省 / yiwen 异文）→ [四象]。
            "piKoujing": payload.get("piKoujing"),
            "timeLines": [],
        }
        if fa == "time":
            _require_cast_geo(payload, tool="xiaochengtu")
            nongli = self._call_remote(
                "/nongli/time",
                {
                    "date": payload["date"],
                    "time": payload.get("time"),
                    "zone": payload.get("zone"),
                    "lon": payload.get("lon"),
                    # 🔴 timeAlg 必须转发：真太阳时会改时支（经度差 >7.5° 即可跨支），
                    # 时支一变卦局/起支全变。qimen/taiyi/zhengchuan 三处一直在转发，端点
                    # 明确支持；这几处漏了 → 同一份入参在不同技法间起出不同的盘。
                    "timeAlg": payload.get("timeAlg"),
                    "lat": payload.get("lat"),
                    **_day_boundary_switches(payload),
                },
            )
            year_gz = str(nongli.get("year") or "") if isinstance(nongli, dict) else ""
            year_zhi = year_gz[1] if len(year_gz) >= 2 else ""
            month_int = nongli.get("monthInt") if isinstance(nongli, dict) else None
            day_int = nongli.get("dayInt") if isinstance(nongli, dict) else None
            hour_gz = str(nongli.get("time") or "") if isinstance(nongli, dict) else ""
            hour_zhi = hour_gz[1] if len(hour_gz) >= 2 else ""
            year_idx = (_SIXYAO_DIZHI.index(year_zhi) + 1) if year_zhi in _SIXYAO_DIZHI else None
            hour_idx = (_SIXYAO_DIZHI.index(hour_zhi) + 1) if hour_zhi in _SIXYAO_DIZHI else None
            if not (year_idx and month_int and day_int and hour_idx):
                raise ToolValidationError(
                    "小成图占时起卦失败：无法从 /nongli/time 取得 年支/农历月日/时支。请改用 manual/number/stock/dayan 显式起卦。",
                    code="tool.xiaochengtu_cast_unavailable",
                    details={"yearZhi": year_zhi, "monthInt": month_int, "dayInt": day_int, "hourZhi": hour_zhi},
                )
            up_num = year_idx + month_int + day_int
            lo_num = up_num + hour_idx
            request["qiguaFa"] = "number"
            request["upNum"] = up_num
            request["loNum"] = lo_num
            request["timeLines"] = [
                f"起卦时间:{payload.get('date')} {payload.get('time') or ''}".strip(),
                f"梅花时间卦:上数{up_num}(年支序{year_idx}+农历{month_int}月+{day_int}日) 下数{lo_num}(+时支序{hour_idx})",
            ]
        js_result = self.js_client.run("xiaochengtu", request)
        data = js_result.get("data", {})
        if isinstance(data, dict) and data.get("ok") is False:
            reason = data.get("reason")
            code = "tool.xiaochengtu_dayan_seed_required" if reason == "dayan_seed_required" else "tool.xiaochengtu_bad_cast"
            raise ToolValidationError(
                data.get("message") or "小成图起卦失败。",
                code=code,
                details={"reason": reason, "qiguaFa": fa},
            )
        snapshot_text = js_result.get("snapshot_text")
        return {
            "xiaochengtu": data,
            "input_normalized": js_result.get("input_normalized", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="xiaochengtu", snapshot_text=snapshot_text),
        }

    def _run_guice_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 皇极轨策：十二法起卦 + 演数四位 + 卦变断法 + 元会运世 + 大定。卦为冻结值。占时四柱（立春界年柱 +
        # 农历月日 + 时支）由前置 /nongli/time 拼 ctx 后传入，JS 层不发 HTTP（AGENTS §4）。
        # settings 十开关 + 各法专属起卦字段（nums/wuShu/… + shu2/tones/zhang/chi/cun/qu/wuGuaNum/fangGuaNum/kind）
        # 经 FlexibleModel extra 透传，此处整体转发（qiGua/normalizeGuiceSettings 忽略多余键）。
        passthrough_keys = (
            "qiguaFa", "school", "yanshuFa", "jiGongMode", "qiguaShu", "shenSha", "shiFang", "shuXi",
            "dadingTable", "shiyingSet", "nums", "wuShu", "shengShu", "text", "shu", "shu2", "tones",
            "zhang", "chi", "cun", "qu", "wuGuaNum", "fangGuaNum", "kind", "hourZhi", "shiyingInputs", "fangKey",
        )
        request: dict[str, Any] = {k: payload.get(k) for k in passthrough_keys if payload.get(k) is not None}
        request["askEvent"] = payload.get("askEvent") or payload.get("question") or ""
        time_lines: list[str] = []
        if payload.get("date"):
            _require_cast_geo(payload, tool="guice")
            nongli = self._call_remote(
                "/nongli/time",
                {
                    "date": payload["date"],
                    "time": payload.get("time"),
                    "zone": payload.get("zone"),
                    "lon": payload.get("lon"),
                    # 🔴 timeAlg 必须转发：真太阳时会改时支（经度差 >7.5° 即可跨支），
                    # 时支一变卦局/起支全变。qimen/taiyi/zhengchuan 三处一直在转发，端点
                    # 明确支持；这几处漏了 → 同一份入参在不同技法间起出不同的盘。
                    "timeAlg": payload.get("timeAlg"),
                    "lat": payload.get("lat"),
                    **_day_boundary_switches(payload),
                },
            )
            if isinstance(nongli, dict):
                year_jieqi = str(nongli.get("yearJieqi") or nongli.get("year") or "")
                month_gz = str(nongli.get("monthGanZi") or "")
                day_gz = str(nongli.get("dayGanZi") or "")
                hour_gz = str(nongli.get("time") or "")
                if len(year_jieqi) >= 2:
                    request["yearZhi"] = year_jieqi[1]
                if len(month_gz) >= 2:
                    request["monthZhi"] = month_gz[1]
                request["lunarMonth"] = nongli.get("monthInt")
                request["lunarDay"] = nongli.get("dayInt")
                if len(hour_gz) >= 2 and not request.get("hourZhi"):
                    request["hourZhi"] = hour_gz[1]
                if len(day_gz) >= 2:
                    request["dayGan"] = day_gz[0]
                request["pillars"] = [p for p in (year_jieqi, month_gz, day_gz, hour_gz) if len(p) >= 2]
                try:
                    request["year"] = int(str(payload["date"]).lstrip("-").split("-")[0]) * (payload.get("ad", 1) or 1)
                except (ValueError, IndexError):
                    request["year"] = None
                time_lines = [
                    f"起卦时间:{payload.get('date')} {payload.get('time') or ''}".strip(),
                    f"农历:{nongli.get('monthInt')}月{nongli.get('dayInt')}日 四柱[{'·'.join(request.get('pillars') or [])}]",
                ]
        # 显式 ctx 覆盖（无 date 时可直接给年支/月支/农历月日/时支等）。
        for k in ("yearZhi", "monthZhi", "lunarMonth", "lunarDay", "year", "dayGan", "pillars"):
            if payload.get(k) is not None:
                request[k] = payload[k]
        request["timeLines"] = time_lines
        js_result = self.js_client.run("guice", request)
        data = js_result.get("data", {})
        if isinstance(data, dict) and data.get("ok") is False:
            raise ToolValidationError(
                data.get("message") or "皇极轨策起卦失败：所需之输入未足。",
                code="tool.guice_insufficient_cast_input",
                details={"reason": data.get("reason"), "qiguaFa": payload.get("qiguaFa")},
            )
        snapshot_text = js_result.get("snapshot_text")
        return {
            "guice": data,
            "input_normalized": js_result.get("input_normalized", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="guice", snapshot_text=snapshot_text),
        }

    def _run_zhengchuan_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 神数正传（五流派）：除 xinyi 查询层外，四柱走 /nongli/time 权威口径（立春界年柱 + 农历月日 + 时柱），
        # JS 层不发 HTTP（AGENTS §4）；条文正文库由 JS 异步载入。dading 另需 birth params 建 bazi 推运表。
        school = payload.get("school", "tieban")
        request: dict[str, Any] = {"school": school}
        if school == "xinyi":
            request.update(_zhengchuan_xinyi_query(payload))
        else:
            _require_cast_geo(payload, tool="zhengchuan")
            # 时间算法一处定、两处用：四柱（/nongli/time）与大定推运表（JS buildLocalBaziResult）必须同口径 ——
            # 上游两路都是一次 buildLocalBaziResult 同出四柱与推运表（aiAnalysisContext.buildChartShusuanBazi:1948-1979，
            # 无头缺省 timeAlg = record.timeAlg ?? 0 真太阳时，buildFieldObject:603）。此前四柱走后端缺省 0、推运表走
            # JS 缺省 1，真太阳时跨时辰的生辰两边时柱不同（sync311 wave 3）。
            time_alg = payload.get("timeAlg")
            time_alg = 0 if time_alg is None else time_alg
            nongli = self._call_remote(
                "/nongli/time",
                {
                    "date": payload["date"],
                    "time": payload.get("time"),
                    "zone": payload.get("zone"),
                    "lon": payload.get("lon"),
                    "lat": payload.get("lat"),
                    "timeAlg": time_alg,
                    **_day_boundary_switches(payload),
                },
            )
            if not isinstance(nongli, dict):
                raise ToolValidationError(
                    "神数正传起盘失败：/nongli/time 未返回农历数据。",
                    code="tool.zhengchuan_pillars_unavailable",
                    details={"school": school},
                )
            pillars = [
                str(nongli.get("yearJieqi") or nongli.get("year") or ""),
                str(nongli.get("monthGanZi") or ""),
                str(nongli.get("dayGanZi") or ""),
                str(nongli.get("time") or ""),
            ]
            if any(len(p) < 2 for p in pillars):
                raise ToolValidationError(
                    "神数正传起盘失败：/nongli/time 未返回完整四柱（年/月/日/时）。请提供完整 date/time。",
                    code="tool.zhengchuan_pillars_unavailable",
                    details={"pillars": pillars},
                )
            request["pillars"] = pillars
            request["lunarMonth"] = nongli.get("monthInt")
            # 农历日 = 后端 dayInt（钟面农历日：23 点档随日柱进位时它不进位，live 实测 after23NewDay 0/1 同值）。
            # 这正是上游 AI 挂载无头口径 —— buildChartShusuanBazi 取 bazi.nongli.dayNum（aiAnalysisContext.js:1971-1972，
            # 钟面日；进位值只在 ziwei* 键）；页面 ZhengChuanMain.getModel 另走 lunarByDayBoundary 进位（:193-196），两路
            # 不一致按无头（sync311 wave 3b 核定，tests/test_sync311_divination_w3b.py 钉值 + 上游源绊线）。
            request["lunarDay"] = nongli.get("dayInt")
            request["isLeapMonth"] = bool(nongli.get("leap"))
            request["gender"] = payload.get("gender")
            for key in ("askGz", "fatherAge", "motherAge", "yuan", "askHourZhi", "env", "dadingYear", "dayun", "xiaoyun", "suijun", "age"):
                if payload.get(key) is not None:
                    request[key] = payload[key]
            if school == "dading":
                # dading 的 JS 端需 birth params 建 bazi 推运表（小运/大运/岁君·年粒度）；timeAlg 与四柱同值。
                for key in ("date", "time", "zone", "lon", "after23NewDay", "lateZiHourUseNextDay"):
                    if payload.get(key) is not None:
                        request[key] = payload[key]
                request["timeAlg"] = time_alg
        js_result = self.js_client.run("zhengchuan", request)
        data = js_result.get("data", {})
        if isinstance(data, dict) and data.get("ok") is False:
            raise ToolValidationError(
                data.get("message") or "神数正传排盘失败。",
                code="tool.zhengchuan_calc_failed",
                details={"reason": data.get("reason"), "school": school},
            )
        snapshot_text = js_result.get("snapshot_text")
        return {
            "zhengchuan": data,
            "input_normalized": js_result.get("input_normalized", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="zhengchuan", snapshot_text=snapshot_text),
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
            # 日界/晚子时开关仅显式给定时透传三式子工具（缺省沿用各子工具/引擎默认）。
            **_day_boundary_switches(payload),
            "timeAlg": payload.get("timeAlg", 0),
        }
        liureng_options = _sanshi_liureng_options(payload)
        taiyi_options = dict(payload.get("taiyi_options") or {})
        # 上游三式合一太乙区的时间基准键名是 taiyiTimeBasis（SanShiUnitedMain.js:446 / :2326，缺省 direct，
        # 不随盘 timeAlg 串改）；skill 的 taiyi_options 用 taiyi 工具原名 timeBasis —— 两种写法都认，taiyi_options 优先。
        if payload.get("taiyiTimeBasis") not in (None, "") and taiyi_options.get("timeBasis") in (None, ""):
            taiyi_options["timeBasis"] = payload["taiyiTimeBasis"]
        qimen_result = self.run_tool(
            "qimen",
            {**shared, "options": payload.get("qimen_options", {})},
            save_result=False,
        )
        taiyi_result = self.run_tool(
            "taiyi",
            {**shared, "options": taiyi_options},
            save_result=False,
        )
        liureng_result = self.run_tool(
            "liureng_gods",
            {
                **shared,
                "yue": payload.get("liureng_yue"),
                "isDiurnal": payload.get("liureng_isDiurnal"),
                # 六壬层口径（上游 SANSHI_PAGE_SETTINGS 六壬层 + guireng：换将/分昼夜/涉害/阴阳系/年神序/土旺衰）。
                "options": liureng_options,
            },
            save_result=False,
        )

        # 口径参数认不出（*_invalid_option）是调用方输入错误，不是引擎故障：直接报错，不出「占位 + warning」的残盘。
        for _res in (qimen_result, taiyi_result, liureng_result):
            _err_info = _res.error
            if not _res.ok and _err_info is not None and str(getattr(_err_info, "code", "")).endswith("_invalid_option"):
                raise ToolValidationError(
                    str(getattr(_err_info, "message", "")),
                    code=str(getattr(_err_info, "code", "")),
                    details=dict(getattr(_err_info, "details", None) or {}),
                )
        # 子技法失败不崩整盘（对应段落为占位），但必须在 envelope.warnings 里点名，不得静默。
        sub_warnings: list[str] = []
        for _label, _res in (("奇门", qimen_result), ("太乙", taiyi_result), ("大六壬", liureng_result)):
            if not _res.ok:
                _err = (_res.error or {}).get("message") if isinstance(_res.error, dict) else _res.error
                sub_warnings.append(f"三式合一子技法「{_label}」计算失败，相关段落以占位输出：{_err or '未知错误'}")
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
        # 段单逐字同上游 sanshiSnapshotSections.js SANSHI_LIURENG_DUANGUA_SECTIONS（v3.11.0 [Q-451/T-414]
        # 补「七政」:44-45 行 —— 独立六壬快照有 [七政]、三式合一页也有「七政」页签，此前挑段单漏它）。
        for _t in (
            "十二盘式", "常用神煞", "年月神煞", "课体结构", "三传旺衰",
            "空亡真假", "旬空落点", "陷空", "遁干特殊", "年命上神",
            "毕法（已命中）", "占断向导", "七政",
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
        # [紫微四化]：上游由紫微子页签上报的 UI 状态驱动（盘 + 选中的大运/流年下标），tab 未打开过
        # 就整段不产。headless 把同一份选择开成 ziweiSihua 入参；紫微盘按**起课时间**另取一张
        # （同上游「为三式起课时间取一张紫微盘」）。不给该入参就不产该段。
        sihua_opts = payload.get("ziweiSihua") if isinstance(payload.get("ziweiSihua"), dict) else None
        if sihua_opts is not None:
            try:
                zw = self._call_remote(
                    "/ziwei/birth",
                    {**{k: v for k, v in shared.items() if v is not None}, "gender": payload.get("gender", 1)},
                )
                zw_chart = zw.get("chart") if isinstance(zw, dict) else None
                if isinstance(zw_chart, dict):
                    js_s = self.js_client.run(
                        "sanshi_ziwei_sihua",
                        {
                            "chart": zw_chart,
                            "daxianIdx": sihua_opts.get("daxianIdx") or 0,
                            "liunianIdx": sihua_opts.get("liunianIdx") or 0,
                        },
                    )
                    sihua_text = f"{(js_s or {}).get('text') or ''}".strip()
                    if sihua_text:
                        snapshot_text = f"{snapshot_text}\n\n{sihua_text}"
            except Exception as exc:  # noqa: BLE001 — 富化失败不许带崩三式主盘
                _degrade("sanshi ziwei sihua build failed: %s", exc)
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
            **({"_warnings": sub_warnings} if sub_warnings else {}),
        }

    def _run_hellen_chart_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        remote_payload = {**payload, "predictive": 0}
        response = self._call_remote("/chart13", remote_payload)
        return response

    # 七政显示层四键（上游 techniqueMountSettings.js:1159-1175 挂载齿轮；缺省 = GuoLaoChartStyle.GUOLAO_DEFAULT_DISPLAY）。
    # 值域逐字同上游 normLifeMasterMode / normMinorLimitType / normTongxianBase / normLimitChildBase。
    # 认不出的值**报错**（不静默归一成缺省）：改这个参数，结果必须变 —— 拼错的值悄悄当缺省用就违背了这一条。
    _GUOLAO_DISPLAY_KEYS: dict[str, tuple[str, tuple[Any, ...], Any]] = {
        "guolaoLifeMasterMode": ("lifeMasterMode", ("gong", "du", "dudegrade"), "gong"),
        "guolaoMinorLimitType": ("minorLimitType", ("", "minor", "month", "tong", "dongwei"), ""),
        "guolaoTongxianBase": ("tongxianBase", ("tong10", "gu9", "xu11"), "tong10"),
        "guolaoLimitChildBase": ("limitChildBase", (9, 10), 9),
    }

    def _guolao_display_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        display: dict[str, Any] = {"limitYearBoundary": "gregorian"}
        for key, (disp_key, allowed, default) in self._GUOLAO_DISPLAY_KEYS.items():
            raw = payload.get(key)
            if raw is None or (raw == "" and disp_key != "minorLimitType"):
                display[disp_key] = default
                continue
            value: Any = f"{raw}".strip()
            if disp_key == "limitChildBase":
                try:
                    value = int(raw)
                except (TypeError, ValueError):
                    value = raw
            if value not in allowed:
                raise ToolValidationError(
                    bilingual(
                        f"七政四余 {key} 取值无效：{raw!r}（可选：{'、'.join(repr(a) for a in allowed)}）。",
                        f"guolao_chart {key} is invalid: {raw!r} (allowed: {', '.join(repr(a) for a in allowed)}).",
                    ),
                    code="tool.guolao_invalid_display_setting",
                    details={"field": key, "value": raw, "allowed": list(allowed)},
                )
            display[disp_key] = value
        return display

    # 七政起盘口径（上游页面左栏 / 挂载齿轮 techniqueMountSettings.js:1123-1181；GuoLaoChartStyle.js 各 getStored* 缺省）。
    # 值域逐字同上游 normalize*/getStored*（认不出的值报错，不静默归一成缺省）。宿度制值域 = guolaoData.SU28_MODE_LABEL 的键
    # 0–8（2=回归今宿 缺省；黄仪 2/3/4/6，赤仪 0/1/5/7/8）。
    _GUOLAO_DIZHI = tuple("子丑寅卯辰巳午未申酉戌亥")
    _GUOLAO_CHART_SETTING_VALUES: dict[str, tuple[Any, ...]] = {
        "guolaoLifeMode": ("asc", "yumao", "cotrans", "gumao", *_GUOLAO_DIZHI),
        "guolaoBodyMode": ("taiyin", "youjin", *_GUOLAO_DIZHI),
        "guolaoNodeMode": ("northKetuSouthRahu", "northRahuSouthKetu"),
        "guolaoTrueSolarTime": ("true", "mean", "off"),
        "guolaoNodeType": ("mean", "true"),
        "guolaoLilithType": ("mean", "true"),
        "guolaoTuibianMethod": ("jiyuan", "jintui", "huiyuan"),
        "guolaoGufaPrecess": ("0", "1"),
        "guolaoEqTropicalAnchor": ("dongzhi", "chunfen"),
    }
    # 只在某些宿度制下生效的子选项（fieldsToParams GuoLaoChartMain.js:2360-2394 的门控）：别的制下上游不下发。
    _GUOLAO_MODE_GATED: dict[str, tuple[int, ...]] = {
        "guolaoAyanamsa": (4,),
        "guolaoTuibianMethod": (6,),
        "guolaoGufaPrecess": (6,),
        "guolaoEqTropicalAnchor": (7, 8),
    }
    _GUOLAO_DEFAULT_SU28_MODE = 2  # GuoLaoChartStyle.js:10 GUOLAO_DEFAULT_SU28_MODE（回归今宿）

    def _guolao_chart_settings(self, payload: dict[str, Any]) -> tuple[int, dict[str, str]]:
        """宿度制 + 起盘口径键（校验后的字符串值）。返回 (su28Mode, {键: 值})；缺省键不在结果里。"""
        raw_mode = payload.get("doubingSu28")
        if raw_mode is None or raw_mode == "":
            su28 = self._GUOLAO_DEFAULT_SU28_MODE
        elif isinstance(raw_mode, bool):
            # 旧布尔语义（perchart.parseSu28Mode：True→1 斗柄定房法 / False→0 荀爽距星）——照后端解释，不再当缺省。
            su28 = 1 if raw_mode else 0
        else:
            try:
                su28 = int(f"{raw_mode}".strip())
            except ValueError:
                su28 = -1
            if su28 not in range(0, 9):
                raise ToolValidationError(
                    bilingual(
                        f"七政四余 doubingSu28（宿度制）取值无效：{raw_mode!r}（可选 0–8：2 回归今宿〔缺省〕/3 回归古制开禧/4 恒星制/"
                        "6 授时历古法 · 0 荀爽距星/1 斗柄定房法/5 恒星制·现代天赤/7 赤道回归(元明)/8 赤道回归(实时)）。",
                        f"guolao_chart doubingSu28 (mansion system) is invalid: {raw_mode!r} (allowed 0–8, default 2).",
                    ),
                    code="tool.guolao_invalid_display_setting",
                    details={"field": "doubingSu28", "value": raw_mode, "allowed": list(range(0, 9))},
                )
        settings: dict[str, str] = {}
        for key, allowed in self._GUOLAO_CHART_SETTING_VALUES.items():
            raw = payload.get(key)
            if raw is None or raw == "":
                continue
            value = ("1" if raw else "0") if isinstance(raw, bool) else f"{raw}".strip()
            if value not in allowed:
                raise ToolValidationError(
                    bilingual(
                        f"七政四余 {key} 取值无效：{raw!r}（可选：{'、'.join(allowed)}）。",
                        f"guolao_chart {key} is invalid: {raw!r} (allowed: {', '.join(allowed)}).",
                    ),
                    code="tool.guolao_invalid_display_setting",
                    details={"field": key, "value": raw, "allowed": list(allowed)},
                )
            settings[key] = value
        if payload.get("guolaoAyanamsa") not in (None, ""):
            settings["guolaoAyanamsa"] = f"{payload.get('guolaoAyanamsa')}".strip()
        for key, modes in self._GUOLAO_MODE_GATED.items():
            if key in settings and su28 not in modes:
                _degrade(
                    "guolao: %s given but su28 mode %s does not use it", key, su28,
                    note=f"七政四余 {key} 只在宿度制 {'/'.join(str(m) for m in modes)} 下生效，本盘宿度制 {su28} 不下发它（上游同口径）。",
                )
                settings.pop(key)
        return su28, settings

    def _guolao_remote_payload(self, payload: dict[str, Any], su28: int, settings: dict[str, str]) -> dict[str, Any]:
        """/chart 请求体：上游 GuoLaoChartMain.fieldsToParams（:2339-2400）七政专属键的条件透传逐条对齐。"""
        remote = {k: v for k, v in payload.items() if k not in self._GUOLAO_CHART_SETTING_VALUES and k != "guolaoAyanamsa"}
        remote.update({
            "tradition": True,
            "predictive": False,
            "hsys": payload.get("hsys", 0),
            "doubingSu28": su28,
            # 恒星制（4）走恒星黄道 + guolaoZhengSidereal；其余制回归黄道（:2351-2356）。
            "zodiacal": 1 if su28 == 4 else payload.get("zodiacal", 0),
            "guolaoZhengSidereal": 1 if su28 == 4 else 0,
            # 命度法恒下发（:2357）；身宫法仅非缺省（:2396-2399）。
            "guolaoLifeMode": settings.get("guolaoLifeMode", "asc"),
        })
        # G2 恒星制岁差：仅恒星宿度制 + 选了 ayanāṃśa 才透传（复用 siderealAyanamsa 键，:2362-2366）。
        if su28 == 4 and settings.get("guolaoAyanamsa"):
            remote["siderealAyanamsa"] = settings["guolaoAyanamsa"]
        # G6 报时星太阳时：仅非缺省（mean/off）才透传（:2369-2372）。
        if settings.get("guolaoTrueSolarTime") in ("mean", "off"):
            remote["trueSolarTime"] = settings["guolaoTrueSolarTime"]
        # G10-13 四余取法：仅真值才透传（:2375-2380）。
        if settings.get("guolaoNodeType") == "true":
            remote["guolaoNodeType"] = "true"
        if settings.get("guolaoLilithType") == "true":
            remote["guolaoLilithType"] = "true"
        # WP-D 授时历古法（用制 6）：推变黄道术法 + 古宿随岁差（:2382-2388）。
        if su28 == 6 and settings.get("guolaoTuibianMethod") in ("jintui", "huiyuan"):
            remote["guolaoTuibianMethod"] = settings["guolaoTuibianMethod"]
        if su28 == 6 and settings.get("guolaoGufaPrecess") == "1":
            remote["guolaoGufaPrecess"] = 1
        # 赤道回归制（用制 7/8）锚点：仅 chunfen 才透传（:2390-2394）。
        if su28 in (7, 8) and settings.get("guolaoEqTropicalAnchor") == "chunfen":
            remote["guolaoEqTropicalAnchor"] = "chunfen"
        if settings.get("guolaoBodyMode", "taiyin") != "taiyin":
            remote["guolaoBodyMode"] = settings["guolaoBodyMode"]
        return remote

    @staticmethod
    def _guolao_fields(su28: int, settings: dict[str, str]) -> dict[str, Any]:
        """JS 段 builder 的 fields（上游页面 fields 形：{键: {value}}）：宿度制 + 起盘口径键。"""
        fields: dict[str, Any] = {"doubingSu28": {"value": su28}}
        for key in ("guolaoLifeMode", "guolaoBodyMode", "guolaoNodeMode", "guolaoTrueSolarTime", "guolaoNodeType", "guolaoLilithType"):
            if key in settings:
                fields[key] = {"value": settings[key]}
        return fields

    def _guolao_info_sections(
        self,
        payload: dict[str, Any],
        response: dict[str, Any],
        display: dict[str, Any],
        moira_rules: dict[str, Any] | None,
        guolao_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """[起盘信息] 命度/身度/宿主行 + [大限] + [三主与化曜] + [限法实算]（vendored 上游 builder，JS `info_sections`）。

        本命四柱：上游 root 是 Java /chart（Java 把 OnlyFourColumns.getNongli() 挂在 chart.nongli，ChartController.java:84-98）；
        skill 的 /chart 走 Python 服务、没有 nongli → 另取同一 Java OnlyFourColumns（/nongli/time，同默认 timeAlg=0 真太阳时、
        日界两键缺省 1/1）挂上去。取不到时事实层照上游回退（年柱按公历年干支、月限行省略）并进 warnings。
        """
        date_text = f"{payload.get('date') or ''}"
        slash_date = date_text.replace("-", "/", 2) if re.match(r"^\d{4}-\d{2}-\d{2}", date_text) else date_text
        natal_nongli: dict[str, Any] | None = None
        try:
            natal_nongli = self._call_remote(
                "/nongli/time",
                {
                    "date": payload.get("date"),
                    "time": payload.get("time"),
                    "zone": payload.get("zone"),
                    "lon": payload.get("lon"),
                    "lat": payload.get("lat"),
                    "gpsLat": payload.get("gpsLat"),
                    "gpsLon": payload.get("gpsLon"),
                    **_day_boundary_switches(payload),
                    "timeAlg": 0,
                    "ad": payload.get("ad", 1),
                },
            )
        except Exception as exc:  # noqa: BLE001 — 本命四柱只影响三主/化曜/月限的取值来源，不许带崩整盘
            _degrade(
                "guolao natal nongli (/nongli/time) unavailable: %s", exc,
                note="七政四余 [三主与化曜] 的生年化曜/命宫配干按公历年干支回退、[限法实算] 月限行省略（本命四柱 /nongli/time 不可用）。",
            )
        chart_obj = response.get("chart") if isinstance(response.get("chart"), dict) else {}
        root = dict(response)
        if isinstance(natal_nongli, dict) and natal_nongli:
            root["chart"] = {**chart_obj, "nongli": natal_nongli}
        transit_date, transit_time = _moira_transit_moment(payload)
        guolao_params = {
            "date": slash_date,
            "time": payload.get("time"),
            "zone": payload.get("zone"),
            "lat": payload.get("lat"),
            "lon": payload.get("lon"),
            "gpsLat": payload.get("gpsLat"),
            "gpsLon": payload.get("gpsLon"),
            "ad": payload.get("ad", 1),
        }
        transit_params = {
            **guolao_params,
            "date": f"{transit_date}".replace("-", "/", 2),
            "time": transit_time,
            "predictive": 1,
        }
        fields = guolao_fields if guolao_fields is not None else {}
        try:
            js = self.js_client.run(
                "guolao_moira",
                {
                    "action": "info_sections",
                    "chart": root,
                    "params": guolao_params,
                    "transitParams": transit_params,
                    "display": display,
                    "fields": fields,
                    "moiraRules": moira_rules or {},
                },
            )
        except Exception as exc:  # noqa: BLE001 — 四段来自 JS；失败 → [大限] 回退 Python 兜底、其余三段缺席，进 warnings
            _degrade(
                "guolao info sections build failed: %s", exc,
                note="七政四余 [大限] 回退内置旧算法（首限四舍童限、元旦年界），[三主与化曜]/[限法实算] 与命度/身度行本次未产出（JS 段 builder 失败）。",
            )
            return {}
        js = js if isinstance(js, dict) else {}
        for err in js.get("errors") or []:
            if isinstance(err, dict):
                _degrade(
                    "guolao info section %s degraded: %s", err.get("section"), err.get("message"),
                    note=f"七政四余 [{err.get('section') or '?'}]：{err.get('message') or '未知错误'}",
                )
        return js

    def _run_guolao_chart_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 显示层四键 + 起盘口径先校验（非法值在任何后端往返之前就报错）。
        display = self._guolao_display_settings(payload)
        # 🔴 宿度制缺省 = 上游 GUOLAO_DEFAULT_SU28_MODE 2（回归今宿）。此前发 doubingSu28=True，后端
        # parseSu28Mode 把 True 解释成 1（斗柄定房法，赤仪）—— 宿位、显示坐标（displayCoord）、格局判据全随之偏。
        su28, guolao_settings = self._guolao_chart_settings(payload)
        remote_payload = self._guolao_remote_payload(payload, su28, guolao_settings)
        guolao_fields = self._guolao_fields(su28, guolao_settings)
        response = _apply_guolao_node_mode(self._call_remote("/chart", remote_payload), guolao_settings)
        # 政余格局 (星阙 v2.6.x Moira DSL)：vendored JS buildLocalMoiraPatterns 评估盘面物象格局。
        # 失败不阻塞既有段（→ '无'），与 星阙 buildGuolaoPatternSection 的 try/catch 一致。
        pattern_text: str | None = None
        patterns: Any = None
        try:
            # 🔴 params 必须是**起盘时刻**，不是 /chart 信封。引擎读 `params.time`（判昼夜，
            # guolaoMoira.js:390）与 `params.date`（判冬令，:397），而信封顶层与其 `params` 子对象
            # 都没有 date/time（只有 `birth`）——此前传 `response` 等于两者恒缺省：
            # isDay 恒真（夜生盘拿天贵而非玉贵、孤月独明永不触发），isWinter 恒假（冬令排除永不生效）。
            # 段照出、格局照列，只有判据是错的。
            js = self.js_client.run("guolao_moira", {
                "chart": response,
                # 命度法/宿度制随 fields（上游 buildGuolaoPatternSection(result, fields, params) 同参）；恒星制判据读
                # params.doubingSu28 / guolaoZhengSidereal（guolaoMoira.js:610）。
                "fields": guolao_fields,
                "params": {
                    "date": payload.get("date"), "time": payload.get("time"),
                    "doubingSu28": su28, "guolaoZhengSidereal": remote_payload.get("guolaoZhengSidereal"),
                },
            })
            if isinstance(js, dict):
                pattern_text = js.get("snapshot_text")
                patterns = js.get("data", {}).get("patterns") if isinstance(js.get("data"), dict) else None
        except Exception as exc:  # noqa: BLE001 - degrade to '无', never break the guolao chart
            _degrade("guolao_moira pattern eval failed: %s", exc)
        # [星曜庙旺与星点动态]：上游导出的纯函数，只吃 /chart 响应（不需要 Moira 规则服务）。
        # 同批的 [虚实]/[本命化曜]/[流年流曜] 读 moiraRules.weakSolid / .yearStars，来自 **Java** 聚合层的
        # /qizheng/moira（v0.36.0 接活；此前误记为「开源 astropy 无该路由」而永久排除，见 LESSONS）。
        dignity_text: str | None = None
        try:
            js2 = self.js_client.run("guolao_star_dignity", {"chart": response, "fields": guolao_fields})
            if isinstance(js2, dict):
                dignity_text = f"{js2.get('text') or ''}".strip() or None
        except Exception as exc:  # noqa: BLE001 - 富化失败只是该段不出
            _degrade("guolao star dignity build failed: %s", exc)
        # [虚实]/[本命化曜]/[流年流曜]（v0.36.0 C1）：Java /qizheng/moira 规则层 + 流年盘二次铸盘。
        # Java 不可用（A5 冷却快速失败 / 降级）→ 三段缺席并进 envelope.warnings，其余段不受影响（optional 段）。
        moira_sections: dict[str, str] = {}
        moira_rules_slim: dict[str, Any] | None = None
        moira_rules_full: dict[str, Any] | None = None
        if payload.get("moiraRules", True) is not False:
            try:
                transit_date, transit_time = _moira_transit_moment(payload)
                moira_params = {
                    **remote_payload,
                    "guolaoLifeMode": guolao_settings.get("guolaoLifeMode", "asc"),
                    "guolaoBodyMode": guolao_settings.get("guolaoBodyMode", "taiyin"),
                }
                transit_params = {**moira_params, "date": transit_date, "time": transit_time, "predictive": True}
                # 流年盘同本命盘一样经罗计换位（上游 applyGuolaoNodeMode(tRaw, steppedFields)，GuoLaoChartMain.js:2570）。
                transit_chart = _apply_guolao_node_mode(
                    self._call_remote("/chart", {k: v for k, v in transit_params.items() if v is not None}), guolao_settings
                )
                rules = self._call_remote(
                    "/qizheng/moira",
                    {"params": moira_params, "chartObj": response, "transitParams": transit_params, "transitChartObj": transit_chart},
                )
                js3 = self.js_client.run(
                    "guolao_moira",
                    {"action": "rules_sections", "moiraRules": rules, "transitYearGz": _ganzhi_year(int(str(transit_date)[:4]))},
                )
                sections = js3.get("sections") if isinstance(js3, dict) else None
                if isinstance(sections, dict):
                    moira_sections = {k: f"{v or ''}".strip() for k, v in sections.items()}
                if isinstance(rules, dict):
                    moira_rules_full = rules
                    moira_rules_slim = {k: rules.get(k) for k in ("weakSolid", "yearStars", "transitYearStars", "natalYearStars") if k in rules}
            except Exception as exc:  # noqa: BLE001 — 三段为 optional；说明进 warnings
                _degrade(
                    "guolao moira rules (/qizheng/moira) unavailable: %s", exc,
                    note="七政四余 [虚实]/[本命化曜]/[流年流曜] 本次未产出（Java /qizheng/moira 不可用或流年盘失败），其余段不受影响。",
                )
        info_sections = self._guolao_info_sections(payload, response, display, moira_rules_full, guolao_fields)
        snapshot_text = _build_guolao_snapshot_text(
            remote_payload, response, pattern_text=pattern_text, info_sections=info_sections
        )
        if dignity_text:
            # 段序对齐上游：紧跟 [七政四余宫位与二十八宿星曜]、在 [神煞] 之前。
            marker = "[神煞]"
            at = snapshot_text.find(marker)
            snapshot_text = (
                f"{snapshot_text[:at]}{dignity_text}\n\n{snapshot_text[at:]}" if at >= 0
                else f"{snapshot_text}\n\n{dignity_text}"
            )
        moira_blocks = [
            f"[{title}]\n{moira_sections.get(key)}"
            for title, key in (("虚实", "weakSolid"), ("本命化曜", "birthStars"), ("流年流曜", "transitStars"))
            if moira_sections.get(key)
        ]
        if moira_blocks:
            # 段序对齐上游 aiExport preset：[大限] 之后、[政余格局] 之前。
            marker = "[政余格局]"
            at = snapshot_text.find(marker)
            joined = "\n\n".join(moira_blocks)
            snapshot_text = f"{snapshot_text[:at]}{joined}\n\n{snapshot_text[at:]}" if at >= 0 else f"{snapshot_text}\n\n{joined}"
        response = dict(response)
        response["snapshot_text"] = snapshot_text
        response["guolaoPatterns"] = patterns
        if moira_rules_slim is not None:
            response["guolaoMoiraRules"] = moira_rules_slim
        response["export_snapshot"] = self._augment_export_payload(technique="guolao", snapshot_text=snapshot_text)
        return response

    # 宿度制九档（perchart.py:54-62 SU28_MODE_* / parseSu28Mode :731-748；上游 newChartSeeds.js:48 check 0–8）。
    _SU28_MODES = frozenset(range(9))

    def _run_suzhan_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        """宿占（F11）：与上游页面同源 —— 盘 = Java /chart（ChartController 附农历四柱 chart.nongli），
        快照 = vendored buildSuzhanSnapshotText（SuZhanMain.js:396-428）。

        v0.40 前：doubingSu28 当 bool（缺省 True=斗柄定房，上游缺省 0 且有九档）、houseStartMode 缺省 1（上游 0=八字公式）
        且快照是手写 port 根本不读它、hsys 缺省 0（上游页面 1）、宫位只印 House1…。人事十二宫「八字公式起盘」要
        农历时支 → 只有 Java /chart 带 nongli（Python chart 服务不带），所以缺省档走 Java；ASC 档不需要农历，照走 chart 服务。
        """
        raw_su28 = payload.get("doubingSu28", 0)
        su28 = int(raw_su28) if isinstance(raw_su28, (bool, int)) or f"{raw_su28}".lstrip("-").isdigit() else raw_su28
        if su28 not in self._SU28_MODES:
            raise ToolValidationError(
                f"宿度制 doubingSu28={raw_su28!r} 不在 0–8 / doubingSu28 must be one of 0-8",
                code="tool.suzhan_su28_invalid",
                details={"field": "doubingSu28", "value": raw_su28, "valid": sorted(self._SU28_MODES)},
            )
        house_start = 1 if payload.get("houseStartMode") in (1, True, "1") else 0
        remote_payload = {**payload, "predictive": False, "doubingSu28": su28}
        nongli_alg = payload.get("nongliTimeAlg")
        if nongli_alg is not None:
            # ChartController.java:84-88 [Q-419/T-383]：农历四柱时间算法 0 真太阳时（缺省）/1 直接时间/3 平太阳时。
            if f"{nongli_alg}" not in ("0", "1", "3"):
                raise ToolValidationError(
                    f"nongliTimeAlg={nongli_alg!r} 只收 0/1/3 / nongliTimeAlg must be 0, 1 or 3",
                    code="tool.suzhan_nongli_timealg_invalid",
                    details={"field": "nongliTimeAlg", "value": nongli_alg, "valid": [0, 1, 3]},
                )
            remote_payload["nongliTimeAlg"] = int(nongli_alg)
        java_failed = False
        if house_start == 0:
            try:
                response = self._call_remote("/chart", remote_payload, backend="java")
            except HorosaSkillError as exc:
                java_failed = True
                _degrade(
                    "suzhan Java /chart unavailable, falling back to chart service: %s", exc,
                    note="宿占「八字公式起盘」要 Java /chart 的农历四柱，本次 Java 不可用 → 改由 chart 服务起盘，"
                         f"人事十二宫按 ASC 起（上游缺农历时同）。原因：{exc}",
                )
                response = self._call_remote("/chart", remote_payload)
        else:
            response = self._call_remote("/chart", remote_payload)
        js = self.js_client.run(
            "suzhan",
            {
                "chart": response,
                "params": {
                    "date": payload.get("date"),
                    "time": payload.get("time"),
                    "zone": payload.get("zone"),
                    "lon": payload.get("lon"),
                    "lat": payload.get("lat"),
                    "szchart": payload.get("szchart"),
                    "szshape": payload.get("szshape"),
                    "doubingSu28": su28,
                    "houseStartMode": house_start,
                },
            },
        ) or {}
        data = js.get("data") if isinstance(js.get("data"), dict) else {}
        snapshot_text = f"{js.get('text') or ''}".strip()
        if not snapshot_text:
            raise ToolTransportError(
                "宿占快照未产出 / suzhan snapshot was not produced.",
                code="tool.suzhan_snapshot_failed",
                details={"data": data},
            )
        if house_start == 0 and not java_failed and not data.get("nongliHour"):
            _degrade(
                "suzhan chart carries no nongli hour; house start fell back to ASC",
                note="宿占人事十二宫缺省按八字公式起盘，但本盘没有农历时支（Java /chart 未附 nongli）→ 已按 ASC 起（上游同）。",
            )
        return {
            **response,
            "compute_sources": {"chart": "java" if house_start == 0 and not java_failed else "chart_service"},
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="suzhan", snapshot_text=snapshot_text),
        }

    def _run_germany_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # rectifyEvents 只喂 [校时预览]（前端纯函数 rectificationHits），不下发后端。
        rectify_events = payload.get("rectifyEvents")
        chart_payload = {**{key: value for key, value in payload.items() if key != "rectifyEvents"}, "predictive": 0}
        chart_response = self._call_remote("/chart", chart_payload)
        germany_result = self._call_remote("/germany/midpoint", chart_payload)
        snapshot_text = _build_germany_snapshot_text(chart_payload, chart_response, germany_result, rectify_events=rectify_events)
        # [戴维森盘]（后端 davison 字段，仅在请求带 davison 第二人时返回）+ [虚星参考]（静态口径表）。
        # 两段由 vendored 上游排版逐字产出；失败只是这两段不出，不影响主盘。
        try:
            extra = self.js_client.run(
                "uranian_extra",
                {
                    "davison": germany_result.get("davison") if isinstance(germany_result, dict) else None,
                    "school": payload.get("school"),
                    "showTnp": payload.get("showTnp", True),
                    "labels": ASTRO_TEXT_MAP,
                },
            )
            extra_text = f"{(extra or {}).get('text') or ''}".strip()
            if extra_text:
                snapshot_text = f"{snapshot_text}\n{extra_text}".strip()
        except Exception as exc:  # noqa: BLE001 — 附注段失败不影响量化盘
            _degrade("uranian extra sections failed: %s", exc)
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
        # 上游 v50 已给调波盘正式导出键（aiExport.js 的 `harmonic`，属 ASTRO_LIKE_EXPORT_KEYS 族），
        # 故此处不再是「无契约的实验面」——见 TOOL_EXPORT_TECHNIQUE_MAP。
        try:
            harmonic_num = max(1, min(int(payload.get("harmonic", 9)), 360))
        except (TypeError, ValueError):
            harmonic_num = 9
        orb = payload.get("orb", 2.0)
        remote_payload = {**payload, "predictive": 0, "harmonic": harmonic_num, "orb": orb}
        response = self._call_remote("/astroextra/harmonic", remote_payload)
        # 注意：这里**不要**回填 `snapshot_text`——统一出口是「工具自带 snapshot_text 就短路自动渲染器」
        # （见 `_flush_export_snapshot` 的 `if not snapshot_text:`）。调波盘要的是通用盘面段 + 调波两段的
        # 合并文本，由 `_auto_snapshot_text_for_tool` 负责；自带一份只含 3 段的文本会把整套盘面段挡掉。
        # `/astroextra/harmonic` 把整个标准 chart-wrap（{chart, aspects, lots, receptions, mutuals,
        # declParallel, params}）放在响应的 `chart` 键下——比导出层通用段构建器预期的深一层。此前原样
        # 转发，导致 [宫位宫头]/[星与虚点]/[相位]/[行星]/[希腊点]/[12分度]/[主宰星链]/[寿命格局] 等
        # 一整批段只出「本次本地计算结果未返回…」占位存根。摊平到顶层，通用构建器才认得。
        chart_wrap = response.get("chart") if isinstance(response.get("chart"), dict) else {}
        # [调波盘] 专属段（v3.9.2）：H 数/位置表/同频，镜像 AstroHarmonicLab.js:65-73。
        lines = [f"调波数：H{response.get('harmonic', harmonic_num)}"]
        lines.extend(_derived_position_lines(response.get("positions"), "调波"))
        lines.extend(_derived_conjunction_lines(response.get("conjunctions")))
        return {
            **chart_wrap,
            "harmonic": response.get("harmonic", harmonic_num),
            "positions": response.get("positions", []),
            "conjunctions": response.get("conjunctions", []),
            "raw": response,
            **({"_derivedSelf": {"title": "调波盘", "lines": lines}} if len(lines) > 1 else {}),
        }

    @staticmethod
    def _split_ymd(value: Any, *, tool: str) -> tuple[int, int, int]:
        parts = f"{value or ''}".replace("/", "-").split("-")
        try:
            return int(parts[0]), int(parts[1]), int(parts[2][:2])
        except (IndexError, ValueError):
            raise ToolValidationError(f"Invalid date for tool `{tool}`: {value!r}") from None

    def _attach_calendar_extras(self, tool_name: str, payload: dict[str, Any], response_data: dict[str, Any]) -> dict[str, Any]:
        """黄历页的三个子模块段块（老黄历 8 段 + 通书择日 + 日子馆 2 段）。

        上游 `calendar` 是页面聚合快照：NongLi（走后端 /calendar/month，本仓已有）+ HuangLi +
        Tongshu + Rizi 四子并出。后三子纯前端推演，由 vendored builder 一次跑完。
        日子馆两段只在传了 `rizi.persons` 时产出——没有当事人就没有「个性化」可言，故列 optional。
        """
        if tool_name != "calendar_month" or not isinstance(response_data, dict):
            return response_data
        selected = f"{payload.get('day') or payload.get('date') or ''}".replace("/", "-")
        parts = selected.split("-")
        try:
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2][:2])
        except (IndexError, ValueError):
            return response_data
        tongshu = dict(payload["tongshu"]) if isinstance(payload.get("tongshu"), dict) else None
        if tongshu and tongshu.get("school"):
            tongshu["school"] = self._tongshu_school(tongshu.get("school"))
        js: Any = None
        try:
            js = self.js_client.run(
                "calendar_extras",
                {
                    "year": year,
                    "month": month,
                    "day": day,
                    "hour": payload.get("hour"),
                    "tongshu": tongshu,
                    "rizi": payload.get("rizi") if isinstance(payload.get("rizi"), dict) else None,
                },
            )
        except Exception as exc:  # noqa: BLE001 — 子模块失败不许影响月历本体
            _degrade("calendar extras build failed: %s", exc)
            return response_data
        js = js if isinstance(js, dict) else {}
        # 显式给了认不出的通书流派键：结构化报错（此前照印「（该流派待实现）」冒充一段结论）。
        for err in js.get("errors") or []:
            if isinstance(err, dict) and err.get("reason") == "unknown_school":
                self._raise_tongshu_unknown_school(err, field="tongshu.school")
        text = f"{js.get('text') or ''}".strip()
        if text:
            enriched = dict(response_data)
            enriched["_calendarExtras"] = text
            return enriched
        return response_data

    def _run_huangli_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 老黄历日课：上游这支是纯前端本地推演（lunar-javascript + 择日表），**零后端往返**，
        # 所以这里没有任何 _call_remote —— 与 canping/heluo 一类的 execution="local" 同款。
        year, month, day = self._split_ymd(payload.get("date"), tool="huangli")
        hour = payload.get("hour")
        js = self.js_client.run(
            "huangli",
            {"year": year, "month": month, "day": day, "hour": hour if hour is not None else 12},
        )
        snapshot_text = f"{(js or {}).get('text') or ''}".strip()
        return {
            "date": payload.get("date"),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="huangli", snapshot_text=snapshot_text),
        }

    # 通书流派键的唯一真值是引擎词表（vendored tongshuSchools.js TONGSHU_SCHOOLS：donggong / qimen /
    # sanyuanliexiu=三垣列宿 / wutu / sanyuan=三元玄空大卦），JS 侧核验、认不出回 unknown_school。
    # 唯一别名 xuankong：v0.40 前本仓 schema/guidance 把玄空写成 xuankong、把 sanyuan 写成三垣（与引擎相反），
    # 照旧文档传 xuankong 的调用方拿到的是「（该流派待实现）」——按引擎键 sanyuan 起并在 warnings 说明。
    _TONGSHU_SCHOOL_ALIASES = {"xuankong": "sanyuan"}

    def _tongshu_school(self, school: Any) -> Any:
        key = f"{school or ''}".strip()
        target = self._TONGSHU_SCHOOL_ALIASES.get(key)
        if target is None:
            return school
        _degrade(
            "tongshu school alias %s -> %s", key, target,
            note=f"通书流派 {key!r} 是旧文档写法，已按引擎键 {target!r}（三元玄空大卦）起盘；三垣列宿的引擎键是 'sanyuanliexiu'。",
        )
        return target

    @staticmethod
    def _raise_tongshu_unknown_school(bad: dict[str, Any], *, field: str) -> None:
        valid = bad.get("valid") if isinstance(bad.get("valid"), list) else []
        raise ToolValidationError(
            f"通书流派 {bad.get('school')!r} 不在引擎词表内 / unknown tongshu school "
            f"{bad.get('school')!r}; valid keys: {', '.join(str(v.get('key')) for v in valid if isinstance(v, dict))}",
            code="tool.tongshu_unknown_school",
            details={"field": field, "school": bad.get("school"), "valid": valid},
        )

    def _run_tongshu_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 通书择日：同样纯本地。school 是结果敏感项（五流派断语可以完全相反），由闸门在调用前问清；
        # 这里只做透传，不替用户挑。
        self._split_ymd(payload.get("date"), tool="tongshu")  # 仅校验格式，JS 侧吃 'YYYY-MM-DD' 原串
        school = self._tongshu_school(payload.get("school"))
        js = self.js_client.run(
            "tongshu",
            {
                "date": f"{payload.get('date') or ''}".replace("/", "-"),
                # zuoShan 不在此列：上游 techniqueMountSettings.js:1938 已把它删掉并记明理由
                # ——「双重幽灵：无任何流派声明 needs.zuoShan，快照 builder 全文不消费，齿轮选它
                # 100% 无效果」。继续转发只会白白打散下游 memo 缓存。
                **{k: payload.get(k) for k in ("event", "liexiuUse", "mingYear") if payload.get(k)},
                **({"school": school} if school else {}),
            },
        )
        js_data = (js or {}).get("data") if isinstance(js, dict) else None
        if isinstance(js_data, dict) and js_data.get("ok") is False and js_data.get("reason") == "unknown_school":
            self._raise_tongshu_unknown_school(js_data, field="school")
        snapshot_text = f"{(js or {}).get('text') or ''}".strip()
        return {
            "date": payload.get("date"),
            "school": school,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="tongshu", snapshot_text=snapshot_text),
        }

    def _run_babylon_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        """巴比伦占星：恒星黄道 · 毕宿锚盘 → vendored 纯函数链铺六段。

        上游的编排函数自己发两个请求，headless 侧按 §5 由 Python 发、JS 只算与排版。
        `/astroextra/ephemeris`（朔望/邻近食）取不到时，[分至天狼星] 段内两行实算自动省略、
        图式行照常 —— 与上游同一条降级口径，故不视为失败。
        """
        chart_payload = {
            **payload,
            "predictive": 0,
            "tradition": 1,
            # 口径由体系决定，不是用户可选项：巴比伦盘恒为恒星黄道 + 毕宿锚（金牛 15°）。
            "zodiacal": 1,
            "siderealAyanamsa": "aldebaran_15tau",
        }
        for stale in ("scheme", "solstice", "era", "ephemerisSource", "dodecaVariant", "cubitDeg", "schemeCn",
                      "datetime", "dirZone", "dirLat", "dirLon"):
            chart_payload.pop(stale, None)
        chart = self._call_remote("/chart", chart_payload)
        date_text = f"{payload.get('date') or ''}".replace("/", "-")
        parts = date_text.split("-")
        try:
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2][:2])
        except (IndexError, ValueError):
            raise ToolValidationError(f"Invalid date for tool `babylon`: {payload.get('date')!r}") from None
        if f"{payload.get('ad', 1)}" in {"-1", "0"}:
            year = -abs(year)  # 公元前：同上游 babylonBirthJdn 的 signedYear 分支
        ephemeris = None
        try:
            ephemeris = self._call_remote("/astroextra/ephemeris", {**chart_payload, "kinds": "lunations"})
        except Exception as exc:  # noqa: BLE001 — 实算历象缺失只丢两行，不影响成段
            _degrade("babylon ephemeris fetch failed: %s", exc)
        js = self.js_client.run(
            "babylon",
            {
                "chart": chart,
                "year": year,
                "month": month,
                "day": day,
                "ephemeris": ephemeris,
                # scheme 是**档 id**（JS 侧据它查 BABYLON_SCHEMES 解析出 judge 参数），
                # solstice/dodecaVariant/cubitDeg/era/ephemerisSource 是显式覆写，缺省则跟档走（v3.11：era 进
                # [起盘信息] 纪元行、ephemerisSource 选 [数理星历] 木星函数；值域锚定 BABYLON_PARAM_SPEC）。
                "scheme": payload.get("scheme"),
                "solstice": payload.get("solstice"),
                **{k: payload[k] for k in ("dodecaVariant", "cubitDeg", "schemeCn", "era", "ephemerisSource") if payload.get(k) is not None},
            },
        )
        invalid = (js or {}).get("invalid") if isinstance(js, dict) else None
        if invalid:
            parts = [f"{i.get('key')}={i.get('value')!r}（可选：{'/'.join(i.get('allowed') or [])}）" for i in invalid if isinstance(i, dict)]
            raise ToolValidationError(
                bilingual(f"巴比伦派系参数取值无效：{'；'.join(parts)}。", f"babylon setting(s) invalid: {'; '.join(parts)}."),
                code="tool.babylon_invalid_setting",
                details={"invalid": invalid},
            )
        snapshot_text = f"{(js or {}).get('text') or ''}".strip()
        return {
            "chart": chart.get("chart"),
            "raw": chart,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="babylon", snapshot_text=snapshot_text),
        }

    def _run_draconic_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 龙盘：各点黄经减北交点（交点归零）。后端把标准 chart-wrap 放在响应的 `chart` 键下——
        # 与 /astroextra/harmonic 同一形状，比导出层通用段构建器预期深一层，故同样摊平到顶层。
        response = self._call_remote("/astroextra/draconic", {**payload, "predictive": 0})
        chart_wrap = response.get("chart") if isinstance(response.get("chart"), dict) else {}
        # [龙盘] 专属段（v3.9.2 派生盘快照重定源）：龙首归零基准/位置/同频，逐字镜像
        # AstroDraconicLab.js:46-55；仅头一行（无位置无同频）不产段（上游 out.length > 1 同判）。
        lines: list[str] = []
        if response.get("nodeLon") is not None:
            lines.append(f"北交点 {float(response['nodeLon']):.2f}° → 归零白羊 0°（龙盘基准）")
        lines.extend(_derived_position_lines(response.get("positions"), "龙盘"))
        lines.extend(_derived_conjunction_lines(response.get("conjunctions")))
        return {
            **chart_wrap,
            "nodeLon": response.get("nodeLon"),
            "positions": response.get("positions", []),
            "conjunctions": response.get("conjunctions", []),
            "raw": response,
            **({"_derivedSelf": {"title": "龙盘", "lines": lines}} if lines else {}),
        }

    def _run_relocation_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 重置盘：出生 UT 不变，只按新经纬重算宫位与角点（行星黄经由 UT 决定故不变）。
        # 响应同 harmonic/draconic 的嵌套形状 → 同样摊平。relocLat/relocLon 缺省回退出生地。
        response = self._call_remote("/astroextra/relocation", {**payload, "predictive": 0})
        chart_wrap = response.get("chart") if isinstance(response.get("chart"), dict) else {}
        # [重置盘] 专属段（v3.9.2）：地点 + 四角对比，镜像 AstroRelocationLab.js:138-149。
        # 本命四角需另铸一张本命盘（上游用页面上已有的 props.value；headless 补一次 /chart）——
        # 上游同款 try 包裹：「角点缺省不产行」，本命盘取不到就只出地点行。
        lines = [f"重置地点：纬 {response.get('relocLat')} / 经 {response.get('relocLon')}"]
        try:
            natal_payload = {k: v for k, v in payload.items() if k not in {"relocLat", "relocLon"}}
            natal = self._call_remote("/chart", {**natal_payload, "predictive": 0})
            natal_angles = _chart_angles(natal)
            reloc_angles = _chart_angles(chart_wrap)
            for angle_id in ("Asc", "MC", "Desc", "IC"):
                n, r = natal_angles.get(angle_id), reloc_angles.get(angle_id)
                if n or r:
                    lines.append(f"{angle_id}：本命 {_angle_text(n)} → 重置后 {_angle_text(r)}")
        except Exception:  # noqa: BLE001 - 角点对比失败不阻断重置盘本体
            pass
        return {
            **chart_wrap,
            "relocLat": response.get("relocLat"),
            "relocLon": response.get("relocLon"),
            "natalLat": response.get("natalLat"),
            "natalLon": response.get("natalLon"),
            "raw": response,
            # 上游 out = [段头, 地点行, …角点]：地点行无条件 push，故 [重置盘] 恒出（角点缺省只少行）。
            "_derivedSelf": {"title": "重置盘", "lines": lines},
        }

    # [起盘信息] 生辰行只要本命盘的这几项（上游 buildPredictiveBirthLines 读 params + chart.{dayofweek,nongli,
    # zodiacal,hsys,isDiurnal,siderealAyanamsa}）——只留这些，不把 ~170 KB 的整盘塞进响应。
    _NATAL_HEADER_CHART_KEYS = ("dayofweek", "nongli", "zodiacal", "hsys", "isDiurnal", "siderealAyanamsa")

    def _natal_header(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        """A 组星运键（agepoint/distributions/extrareturns：后端只回自家时间线、不带盘）补拉本命 /chart，
        供 [起盘信息]（上游 fetchChartResultForRecord → buildPredictiveBirthHeaderLines 同源）。
        拉取失败 → 降级为只用载荷的生辰行 + envelope 警告，不拖垮技法本身。"""
        natal_payload = {**payload, "predictive": 0}
        for key in ("datetime", "dirZone", "dirLat", "dirLon"):
            natal_payload.pop(key, None)
        try:
            natal = self._call_remote("/chart", natal_payload)
        except HorosaSkillError as exc:
            _degrade("predictive natal header fetch failed (tool=%s): %s", tool_name, exc)
            return None
        chart = natal.get("chart") if isinstance(natal.get("chart"), dict) else {}
        params = natal.get("params") if isinstance(natal.get("params"), dict) else {}
        return {"params": params, "chart": {key: chart.get(key) for key in self._NATAL_HEADER_CHART_KEYS if key in chart}}

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
        natal_header = self._natal_header("agepoint", payload)
        if natal_header:
            result["natalHeader"] = natal_header
        birth = _predictive_birth_source(result, payload).get("params", {}).get("birth")
        moment_line = _agepoint_moment_line(response, birth)
        result["_moment_lines"] = [moment_line] if moment_line else []
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
        natal_header = self._natal_header("distributions", payload)
        if natal_header:
            result["natalHeader"] = natal_header
        moment_line = _distributions_moment_line(response)
        result["_moment_lines"] = [moment_line] if moment_line else []
        result["export_snapshot"] = self._augment_export_payload(technique="distributions", snapshot_text=snapshot_text)
        return result

    def _progression_target(self, payload: dict[str, Any]) -> dict[str, Any]:
        """目标时刻型推运（vedicprog/jaynesprog）的请求三键，缺省与上游 builder 同律（F10）：

        上游 AstroJaynesProgressions.js:37-39 / astroProgSnapshot.js:57-59：
        targetDate 缺省 today()（本地日期）、targetTime 缺省 12:00:00、minorVariant 缺省 synodic（[Q-180]，
        后端 progression_date 同缺省）。旧实现把 targetDate 缺省成**出生日**——推运零年、结果恒等本命，
        与上游和本仓自己的 guidance（「缺省=今天」）都不一致。
        """
        minor_variant = payload.get("minorVariant")
        if minor_variant is not None:
            _require_option(minor_variant, tuple(_ptext.MINOR_VARIANT_LABEL), field="minorVariant", tool="progression")
        return {
            "targetDate": f"{payload.get('targetDate') or datetime.now().strftime('%Y-%m-%d')}".strip(),
            "targetTime": f"{payload.get('targetTime') or '12:00:00'}".strip(),
            "minorVariant": minor_variant or _ptext.DEFAULT_MINOR_VARIANT,
        }

    def _run_jaynesprog_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # Jayne 赤纬推运 (v2.5.0): /astroextra/jaynesprog — secondary progression + declination parallels.
        target = self._progression_target(payload)
        remote_payload = {**payload, **target, "orb": payload.get("orb", 1.0)}
        response = self._call_remote("/astroextra/jaynesprog", remote_payload)
        # 上游 [本命盘配置]（生辰 + 星与虚点 + 宫位宫头 + ◆ 本命赤纬）要本命盘——/astroextra/jaynesprog 只回推运结果。
        response = self._attach_predictive_chart_context("jaynesprog", payload, response)
        snapshot_text = _build_jaynesprog_snapshot_text(
            response, payload, target_date=target["targetDate"], target_time=target["targetTime"],
            minor_variant=target["minorVariant"],
        )
        return {
            "methods": response.get("methods", []),
            "target": target,
            "raw": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="jaynesprog", snapshot_text=snapshot_text),
        }

    def _run_vedicprog_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 恒星推运 Vedic (v2.5.0): /astroextra/progressions with zodiacal=1 (sidereal).
        target = self._progression_target(payload)
        remote_payload = {**payload, **target, "zodiacal": 1, "orb": payload.get("orb", 1.5)}
        response = self._call_remote("/astroextra/progressions", remote_payload)
        # execution="local" 的工具不走统一出口的 _attach_predictive_chart_context（那一支只对
        # remote 工具生效），所以这里显式补拉本命盘 —— [本命盘配置] 段要它。
        response = self._attach_predictive_chart_context("vedicprog", payload, response)
        # 与 prog 共用 engine/astroextra_snapshots.py 的逐字移植 builder（已对上游 astroProgSnapshot.js 逐字节核过；
        # 此前本仓有第二份 service 内移植，[本命盘配置] 还是 v3.11 前的逐行旧形——合并时去重）。
        natal = response.get("natalChart") if isinstance(response, dict) else None
        snapshot_text = build_prog_snapshot_text(
            natal if isinstance(natal, dict) else {},
            response,
            "vedicprog",
            target_date=target["targetDate"],
            target_time=target["targetTime"],
            minor_variant=target["minorVariant"],
            now=datetime.now(),
            method_notes=_PREDICTIVE_METHOD_NOTES["vedicprog"],
        )
        if not snapshot_text:
            raise ToolValidationError(
                "推运端点没有返回二次推运位置（上游此时显示「缺失」） / /astroextra/progressions returned no secondary positions",
                code="tool.vedicprog_empty",
                details={"tool": "vedicprog", "targetDate": target["targetDate"]},
            )
        return {
            "methods": response.get("methods", []),
            "target": target,
            "raw": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="vedicprog", snapshot_text=snapshot_text),
        }

    # ── 星运四键（上游 v3.11：[Q-106/T-10] 星历/回归轴/产前朔望三页 + [#80] 回归黄道二次推运）──────────────
    # 与上游无头路径 aiAnalysisContext.regenerateChartTechniqueSnapshot（:2956-2983）同形：先取本命盘
    # （chartObj——[起盘信息] 与 prog 的 [本命盘配置] 由它出），再以页面同一请求体（AstroExtraCommon.chartParams：
    # tradition / predictive 恒 false）打 /astroextra/*，最后交给 engine/astroextra_snapshots.py 的逐字移植 builder。
    # 上游 builder 求不得数据时返回 ''（挂载面显示「缺失」）；skill 侧空快照会落 generated_template 假导出，
    # 故一律抛结构化错误（AGENTS §5.9 勿静默回退）。本命盘 fetch 失败同样直接抛（没有它就没有 [起盘信息]）。
    _ASTROEXTRA_OPTION_KEYS = frozenset({
        "startDate", "endDate", "includeTransits", "eclipseTimeMode", "startYear", "count",
        "targetDate", "targetTime", "minorVariant",
    })

    def _astroextra_natal_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        natal = {key: value for key, value in payload.items() if key not in self._ASTROEXTRA_OPTION_KEYS}
        natal["predictive"] = 0
        for key in ("datetime", "dirZone", "dirLat", "dirLon"):
            natal.pop(key, None)
        return natal

    @staticmethod
    def _astroextra_chart_params(natal_payload: dict[str, Any]) -> dict[str, Any]:
        # AstroExtraCommon.chartParams（:126-150）：随本命盘透传，tradition / predictive 恒 false。
        return {**natal_payload, "tradition": False, "predictive": False}

    @staticmethod
    def _astroextra_date(payload: dict[str, Any], key: str, *, code: str) -> str | None:
        """YYYY-MM-DD（亦收 YYYY/MM/DD、单位数月日）→ 规范 YYYY-MM-DD；缺省/空 → None（走上游缺省）。"""
        raw = payload.get(key)
        text = f"{raw if raw is not None else ''}".strip()
        if not text:
            return None
        match = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", text)
        try:
            if not match:
                raise ValueError(text)
            value = datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            raise ToolValidationError(
                f"{key} 不是合法日期（要 YYYY-MM-DD）：{text!r} / {key} is not a valid date (expected YYYY-MM-DD): {text!r}",
                code=code,
                details={"field": key, "value": raw},
            ) from None
        return value.strftime("%Y-%m-%d")

    def _run_ephemeris_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        """星历（AstroEphemeris.buildEphemerisSnapshotText）：区间内入座/留逆/朔望弦/食相 + 行运触发本命。

        缺省窗 = 上游 defaultEphemerisWindow：今日起 90 天、含行运触发（startDate/endDate 各自缺省，与页面
        `{...defaults, ...opts}` 同语义）；eclipseTimeMode 是上游全局口径（缺省 max=食甚，非 max 才下发）。
        """
        natal_payload = self._astroextra_natal_payload(payload)
        natal = self._call_remote("/chart", natal_payload)
        today = datetime.now()
        start_date = self._astroextra_date(payload, "startDate", code="tool.ephemeris_invalid_window") or today.strftime("%Y-%m-%d")
        end_date = self._astroextra_date(payload, "endDate", code="tool.ephemeris_invalid_window") or (
            today + timedelta(days=90)
        ).strftime("%Y-%m-%d")
        if end_date < start_date:
            raise ToolValidationError(
                f"星历结束日早于开始日：{start_date} → {end_date}（只给 startDate 时 endDate 仍按上游缺省=今日+90天）"
                f" / ephemeris endDate precedes startDate: {start_date} → {end_date} (pass endDate too)",
                code="tool.ephemeris_invalid_window",
                details={"startDate": start_date, "endDate": end_date},
            )
        include_transits = payload.get("includeTransits") is not False
        eclipse_mode = f"{payload.get('eclipseTimeMode') or ''}".strip() or "max"
        if eclipse_mode not in {"max", "syzygy"}:
            raise ToolValidationError(
                f"eclipseTimeMode 只能是 max（食甚时刻）或 syzygy（精确朔望）：{eclipse_mode!r}"
                f" / eclipseTimeMode must be 'max' or 'syzygy': {eclipse_mode!r}",
                code="tool.ephemeris_invalid_option",
                details={"field": "eclipseTimeMode", "value": eclipse_mode, "allowed": ["max", "syzygy"]},
            )
        body = {
            **self._astroextra_chart_params(natal_payload),
            "startDate": start_date,
            "endDate": end_date,
            "includeTransits": include_transits,
        }
        if eclipse_mode != "max":
            body["eclipseTimeMode"] = eclipse_mode
        response = self._call_remote("/astroextra/ephemeris", body)
        snapshot_text = build_ephemeris_snapshot_text(
            natal,
            response,
            start_date=start_date,
            end_date=end_date,
            include_transits=include_transits,
            now=datetime.now(),
            method_notes=_PREDICTIVE_METHOD_NOTES["ephemeris"],
        )
        if not snapshot_text:
            raise ToolValidationError(
                f"星历区间 {start_date} 至 {end_date} 内没有任何可列事件（入座/留逆/朔望弦/食相/行运触发皆空；上游此时显示「缺失」）"
                f" / no ephemeris events in {start_date}..{end_date} — widen the window",
                code="tool.ephemeris_empty",
                details={"startDate": start_date, "endDate": end_date, "endpoint": "/astroextra/ephemeris"},
            )
        # data 只带 builder 实际消费的事件表（每日位置/升落现象是页面专属 tab，不进上游 AI 导出；整份 ~0.4 MB）。
        return {
            "window": {
                "startDate": start_date,
                "endDate": end_date,
                "includeTransits": include_transits,
                "eclipseTimeMode": eclipse_mode,
            },
            "ephemeris": {
                key: response.get(key)
                for key in ("params", "ingresses", "stations", "lunarPhases", "eclipses", "transitAspects")
            },
            "natal_params": natal.get("params"),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="ephemeris", snapshot_text=snapshot_text),
        }

    def _run_returntimeline_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        """回归轴（AstroReturnTimeline.buildReturnTimelineSnapshotText）：逐年太阳返照 + 该年首个月亮返照 + 两盘上升。

        缺省 = 上游 `{startYear: 今年, count: 12}`；后端把 count 夹到 1–40，页面输入框同界——越界直接报错，
        免得段头写「50 年」而表里只有 40 行。
        """
        natal_payload = self._astroextra_natal_payload(payload)
        natal = self._call_remote("/chart", natal_payload)
        start_year = payload.get("startYear")
        if start_year in (None, "", 0):
            start_year = datetime.now().year
        count = payload.get("count")
        if count in (None, "", 0):
            count = 12
        try:
            start_year = int(start_year)
            count = int(count)
        except (TypeError, ValueError):
            raise ToolValidationError(
                f"startYear / count 必须是整数：{start_year!r} / {count!r} / startYear and count must be integers",
                code="tool.returntimeline_invalid_range",
                details={"startYear": start_year, "count": count},
            ) from None
        if not 1 <= count <= 40:
            raise ToolValidationError(
                f"回归轴年数 count 须在 1–40 之间（后端上限 40）：{count} / count must be within 1–40 (backend clamp): {count}",
                code="tool.returntimeline_invalid_range",
                details={"count": count, "min": 1, "max": 40},
            )
        body = {**self._astroextra_chart_params(natal_payload), "startYear": start_year, "count": count}
        response = self._call_remote("/astroextra/returns", body)
        rows = response.get("rows")
        if not isinstance(rows, list):
            raise ToolTransportError(
                "回归轴端点返回了意外形状（缺 rows 数组） / /astroextra/returns returned an unexpected shape (no rows list)",
                code="transport.invalid_result_shape",
                details={"endpoint": "/astroextra/returns", "keys": sorted(response)},
            )
        snapshot_text = build_return_timeline_snapshot_text(
            natal,
            rows,
            start_year=start_year,
            count=count,
            now=datetime.now(),
            method_notes=_PREDICTIVE_METHOD_NOTES["returntimeline"],
        )
        if not snapshot_text:
            raise ToolValidationError(
                f"回归轴没有返回任何年份行（startYear={start_year}, count={count}） / the return timeline returned no rows",
                code="tool.returntimeline_empty",
                details={"startYear": start_year, "count": count, "endpoint": "/astroextra/returns"},
            )
        return {
            "range": {"startYear": start_year, "count": count},
            "rows": rows,
            "natal_params": natal.get("params"),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="returntimeline", snapshot_text=snapshot_text),
        }

    def _run_prenatalsyzygy_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        """产前朔望（AstroPrenatalSyzygy.buildPrenatalSyzygySnapshotText）：回溯最近朔/望 + 以该时刻、出生地起盘。

        第二张盘（朔望时刻 /chart）取不到时上游照出段并写「暂缺」行——同样照写，另经 _degrade 进 envelope.warnings。
        """
        natal_payload = self._astroextra_natal_payload(payload)
        natal = self._call_remote("/chart", natal_payload)
        base = self._astroextra_chart_params(natal_payload)
        syzygy = self._call_remote("/astroextra/prenatal_syzygy", base)
        if not syzygy.get("type"):
            raise ToolValidationError(
                "未能求得产前朔望（极区或星历不可用；上游此时显示「缺失」） / prenatal syzygy could not be solved "
                "(polar latitude or ephemeris unavailable)",
                code="tool.prenatalsyzygy_unavailable",
                details={"endpoint": "/astroextra/prenatal_syzygy", "result": syzygy},
            )
        syzygy_chart: dict[str, Any] | None = None
        moment = split_syzygy_datetime(syzygy.get("datetime"))
        if moment is None:
            _degrade("prenatalsyzygy: 朔望结果缺 datetime，无法以朔望时刻排盘（[产前朔望盘·星体位置] 写「暂缺」行）")
        else:
            try:
                syzygy_chart = self._call_remote("/chart", {**base, "date": moment["date"], "time": moment["time"]})
            except HorosaSkillError as exc:
                _degrade("prenatalsyzygy: 以朔望时刻排盘失败（[产前朔望盘·星体位置] 写「暂缺」行）: %s", exc)
        snapshot_text = build_prenatal_syzygy_snapshot_text(
            natal,
            syzygy,
            syzygy_chart,
            now=datetime.now(),
            method_notes=_PREDICTIVE_METHOD_NOTES["prenatalsyzygy"],
        )
        syzygy_objects = []
        chart_body = syzygy_chart.get("chart") if isinstance(syzygy_chart, dict) else None
        for obj in (chart_body.get("objects") if isinstance(chart_body, dict) else None) or []:
            if isinstance(obj, dict) and obj.get("id"):
                syzygy_objects.append({key: obj.get(key) for key in ("id", "sign", "signlon", "lon") if key in obj})
        return {
            "syzygy": syzygy,
            "syzygy_chart": {
                "params": syzygy_chart.get("params") if isinstance(syzygy_chart, dict) else None,
                "objects": syzygy_objects,
            },
            "natal_params": natal.get("params"),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="prenatalsyzygy", snapshot_text=snapshot_text),
        }

    def _run_prog_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        """二次推运·回归黄道（astroProgSnapshot.buildProgSnapshotText variant 'prog'）。

        与 vedicprog 同一后端 /astroextra/progressions、同一 builder 族；本支**不下发 zodiacal 覆写**（随盘自身黄道，
        上游 PROG_SNAPSHOT_VARIANTS.prog.zodiacal = null）。缺省 = 上游 targetDate 今天 / targetTime 12:00:00 /
        minorVariant synodic；orb 上游写死 1.5。`datetime`（YYYY-MM-DD HH:MM:SS）只在没给 targetDate 时作目标时刻用
        （后端 build_progressions 的同一回退顺序），目标日期行照实写出，不静默吞。
        """
        natal_payload = self._astroextra_natal_payload(payload)
        natal = self._call_remote("/chart", natal_payload)
        target_date = self._astroextra_date(payload, "targetDate", code="tool.prog_invalid_option")
        target_time_raw = f"{payload.get('targetTime') or ''}".strip()
        if target_date is None and payload.get("datetime"):
            parts = f"{payload['datetime']}".strip().replace("T", " ").split(" ")
            target_date = self._astroextra_date({"datetime": parts[0]}, "datetime", code="tool.prog_invalid_option")
            if not target_time_raw and len(parts) > 1:
                target_time_raw = parts[1]
        target_date = target_date or datetime.now().strftime("%Y-%m-%d")
        target_time = "12:00:00"
        if target_time_raw:
            time_match = re.fullmatch(r"(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?", target_time_raw)
            if not time_match or int(time_match.group(1)) > 23 or int(time_match.group(2)) > 59 or int(time_match.group(3) or 0) > 59:
                raise ToolValidationError(
                    f"targetTime 不是合法时刻（要 HH:MM[:SS]）：{target_time_raw!r} / targetTime must be HH:MM[:SS]: {target_time_raw!r}",
                    code="tool.prog_invalid_option",
                    details={"field": "targetTime", "value": target_time_raw},
                )
            target_time = f"{int(time_match.group(1)):02d}:{int(time_match.group(2)):02d}:{int(time_match.group(3) or 0):02d}"
        minor_variant = f"{payload.get('minorVariant') or ''}".strip() or DEFAULT_MINOR_VARIANT
        if minor_variant not in MINOR_VARIANT_LABEL:
            raise ToolValidationError(
                f"minorVariant 只能是 {'/'.join(MINOR_VARIANT_LABEL)}：{minor_variant!r}"
                f" / minorVariant must be one of {', '.join(MINOR_VARIANT_LABEL)}: {minor_variant!r}",
                code="tool.prog_invalid_option",
                details={"field": "minorVariant", "value": minor_variant, "allowed": list(MINOR_VARIANT_LABEL)},
            )
        body = {
            **self._astroextra_chart_params(natal_payload),
            "targetDate": target_date,
            "targetTime": target_time,
            "minorVariant": minor_variant,
            "orb": 1.5,
        }
        variant_zodiacal = PROG_SNAPSHOT_VARIANTS["prog"]["zodiacal"]
        if variant_zodiacal:
            body["zodiacal"] = variant_zodiacal
        response = self._call_remote("/astroextra/progressions", body)
        snapshot_text = build_prog_snapshot_text(
            natal,
            response,
            "prog",
            target_date=target_date,
            target_time=target_time,
            minor_variant=minor_variant,
            now=datetime.now(),
            method_notes=_PREDICTIVE_METHOD_NOTES["prog"],
        )
        if not snapshot_text:
            raise ToolValidationError(
                "推运端点没有返回二次推运位置（上游此时显示「缺失」） / /astroextra/progressions returned no secondary positions",
                code="tool.prog_empty",
                details={"endpoint": "/astroextra/progressions", "targetDate": target_date, "targetTime": target_time},
            )
        return {
            "target": {"targetDate": target_date, "targetTime": target_time, "minorVariant": minor_variant},
            "methods": response.get("methods", []),
            "ageDays": response.get("ageDays"),
            "natal_params": natal.get("params"),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="prog", snapshot_text=snapshot_text),
        }

    def _run_planetaryarc_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 行星弧 (v2.5.0): /predict/planetaryarc — directs the whole chart by the arc of arcSource (default Moon).
        # F10：目标时刻缺省 = 上游 todayStr()（明天此刻，AstroPlanetaryArc.js:46）；旧实现缺省成**出生日**（零弧）。
        arc_source = payload.get("arcSource", "Moon")
        _require_option(arc_source, _ARC_SOURCES, field="arcSource", tool="planetaryarc")
        remote_payload = {
            **payload,
            "datetime": payload.get("datetime") or payload.get("targetDate") or _planetaryarc_default_datetime(),
            "asporb": payload.get("asporb", 1),
            "arcSource": arc_source,
        }
        response = self._call_remote("/predict/planetaryarc", remote_payload)
        # 后端随回的 natalChart 只有 {hsys,houses,objects,isDiurnal}：无 params/星期/黄道，也无本命 lots——
        # 旧实现经 _as_chart_wrap 的 fallback_lots 把顶层的**向运** lots 当本命 lots 印进 [本命盘配置]。
        # 上游 formatArcSnapshot 的本命块读的是真本命 chartObj（buildPredictiveBirthLines + 星与虚点 + 宫位宫头），
        # 故补拉本命 /chart 顶替之；拉取失败则退回后端那份（_degrade 已留警告）。
        natal_payload = {**payload, "predictive": 0}
        for key in ("datetime", "dirZone", "dirLat", "dirLon"):
            natal_payload.pop(key, None)
        try:
            response = {**response, "natalChart": self._call_remote("/chart", natal_payload)}
        except HorosaSkillError as exc:
            _degrade("planetaryarc natal chart fetch failed: %s", exc)
        snapshot_text = _build_planetaryarc_snapshot_text(response, payload)
        return {
            "chart": response.get("chart"),
            "target": {"datetime": remote_payload["datetime"], "arcSource": arc_source},
            "raw": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="planetaryarc", snapshot_text=snapshot_text),
        }

    def _run_planetaryages_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 行星年龄 (v2.5.0): Ptolemy seven ages of man — reads the natal chart, marks the current band.
        chart_payload = {**payload, "predictive": 0}
        response = self._call_remote("/chart", chart_payload)
        as_of = payload.get("asOf") or payload.get("targetDate")
        moment_lines: list[str] = []
        snapshot_text = _build_planetaryages_snapshot_text(response, as_of, moment_lines=moment_lines)
        return {
            "_moment_lines": moment_lines,
            "chart": response.get("chart"),
            "raw": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="planetaryages", snapshot_text=snapshot_text),
        }

    # F7：上游挂载齿轮（techniqueMountSettings.js:1237-1274）→ builder opts 的键与值域（aiAnalysisContext.js:2998-3013
    # regen 传的就是这几键）。值域抄 vendored builder 自己的常量表（balbillus.js BALBILLUS_YEAR_TYPES/MODES、
    # triplicityRulers.js TRIPLICITY_SYSTEMS/DIVISIONS、keypoints120.js RELEASE_MODES）——认不出就报错，
    # 不像 builder 那样静默回落缺省。
    _PROGEXTRA_OPTION_DOMAINS: dict[str, dict[str, tuple[str, ...]]] = {
        "balbillus": {
            "startPlanet": ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"),
            "yearType": ("solar", "hellenistic"),
            "mode": ("nearest", "forward"),
        },
        "triplicityrulers": {
            "system": ("Dorothean", "Ptolemaic", "PtolemaicWaterVariant"),
            "division": ("thirds", "halves"),
        },
        "keypoints": {"mode": ("soul", "body")},
    }
    # triplicityrulers.lifespan：上游齿轮 number 30–120（缺省 75）。
    _TRIPLICITY_LIFESPAN_RANGE = (30, 120)

    def _progextra_options(self, payload: dict[str, Any], technique: str) -> dict[str, Any]:
        options: dict[str, Any] = {}
        for field, allowed in self._PROGEXTRA_OPTION_DOMAINS.get(technique, {}).items():
            value = payload.get(field)
            if value is None:
                continue
            _require_option(value, allowed, field=field, tool=technique)
            options[field] = value
        if technique == "triplicityrulers" and payload.get("lifespan") is not None:
            lifespan = _finite_number(payload.get("lifespan"))
            low, high = self._TRIPLICITY_LIFESPAN_RANGE
            if lifespan is None or not low <= lifespan <= high:
                raise ToolValidationError(
                    f"triplicityrulers 的 lifespan={payload.get('lifespan')!r} 须在 {low}–{high} 之间 / "
                    f"lifespan must be a number within {low}-{high}.",
                    code="tool.predictive_invalid_option",
                    details={"tool": technique, "field": "lifespan", "value": payload.get("lifespan"), "allowed": [low, high]},
                )
            options["lifespan"] = lifespan
        return options

    def _run_progextra_js_tool(self, payload: dict[str, Any], technique: str) -> dict[str, Any]:
        # v2.5.0 推运 builders that are too algorithm-heavy to re-port (balbillus 129年旺距削减 / persiandirected /
        # yearsystem129): cast the natal /chart, then run the vendored 星阙 frontend builder via horosa-core-js,
        # which emits the single-section snapshot text directly.
        options = self._progextra_options(payload, technique)
        chart_payload = {**payload, "predictive": 0}
        chart_payload.pop("datetime", None)
        chart_payload.pop("dirZone", None)
        chart_payload.pop("dirLat", None)
        chart_payload.pop("dirLon", None)
        response = self._call_remote("/chart", chart_payload)
        snapshot_text = ""
        moment_lines: list[str] = []
        try:
            js = self.js_client.run("progextra", {"technique": technique, "chart": response, "options": options})
            if isinstance(js, dict):
                snapshot_text = f"{js.get('snapshot_text') or ''}".strip()
                # builder 自算的 [当前时点] 定位行（当前主限 / 当前所处阶段 / 当前推运月相…）。
                moment_lines = [f"{line}" for line in (js.get("moment_lines") or []) if line]
                js_data = js.get("data") if isinstance(js.get("data"), dict) else {}
                if js_data.get("ok") is False:
                    _degrade(
                        "progextra builder failed (technique=%s): %s %s",
                        technique, js_data.get("reason"), js_data.get("error") or "",
                    )
        except Exception as exc:
            _degrade("progextra JS engine failed (technique=%s): %s", technique, exc)
        return {
            "chart": response.get("chart"),
            "options": options,
            "_moment_lines": moment_lines,
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

    # 上游 components/astro/AstroExtraReturns.js:40：导出取 5 回（与组件 state.count=5 对齐；此前 4 回是上游已修的 bug）。
    _EXTRARETURNS_COUNT = 5

    @staticmethod
    def _extrareturns_body_line(cn: str, period: str, resp: dict[str, Any], rows: list[dict[str, Any]]) -> str:
        """逐字镜像上游 AstroExtraReturns.js:43-53 的每体一行。

        [Q-366/T-345] 后端同一回列全部逆行三过（passes，顺→逆→顺）：>1 过时写 `第N回 d1/d2(逆)/d3`，
        单过仍是一个日期；行尾追加各回时刻 + 本命黄经（toFixed(1)，与 UI 同口径）。
        """
        def dates_cell(row: dict[str, Any]) -> str:
            passes = row.get("passes")
            if isinstance(passes, list) and len(passes) > 1:
                joined = "/".join(
                    f"{pp.get('date')}{'(逆)' if pp.get('retrograde') else ''}" for pp in passes if isinstance(pp, dict)
                )
                return f"第{_ptext.js_str(row.get('which'))}回 {joined}"
            return f"第{_ptext.js_str(row.get('which'))}回 {row.get('date')}"

        dates_txt = "，".join(dates_cell(row) for row in rows)
        times_txt = "，".join(f"第{_ptext.js_str(row.get('which'))}回 {row.get('time') or '-'}" for row in rows)
        natal_lon = resp.get("natalLon")
        natal_lon_txt = f"；本命黄经 {_ptext.js_to_fixed(natal_lon, 1)}°" if natal_lon is not None else ""
        return f"{cn}（{period}）：{dates_txt}；时刻：{times_txt}{natal_lon_txt}"

    def _run_extrareturns_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        remote_base = {**payload, "predictive": 0}
        for key in ("datetime", "dirZone", "dirLat", "dirLon"):
            remote_base.pop(key, None)
        lines = ["[多重回归]"]
        for body_key, cn, period in self._EXTRARETURNS_BODIES:
            try:
                resp = self._call_remote(
                    "/astroextra/planetreturn", {**remote_base, "body": body_key, "count": self._EXTRARETURNS_COUNT}
                )
            except Exception as exc:
                _degrade("extrareturns planetreturn failed (body=%s): %s", body_key, exc)
                continue
            rows = resp.get("returns") if isinstance(resp, dict) else None
            if not isinstance(rows, list) or not rows:
                continue
            rows = [r for r in rows if isinstance(r, dict)]
            if rows:
                lines.append(self._extrareturns_body_line(cn, period, resp, rows))
        snapshot_text = "\n".join(lines) if len(lines) > 1 else ""
        result: dict[str, Any] = {}
        natal_header = self._natal_header("extrareturns", payload)
        if natal_header:
            result["natalHeader"] = natal_header
        # [日月返照年表]（v0.33.0 批 I-3，/astroextra/returns）：逐年日返/月返精确时刻 + 返照上升。
        # 条件段：给 timelineStartYear/timelineCount 才产，零回归。
        if payload.get("timelineStartYear") is not None or payload.get("timelineCount") is not None:
            timeline_remote = {**remote_base}
            if payload.get("timelineStartYear") is not None:
                timeline_remote["startYear"] = payload.get("timelineStartYear")
            if payload.get("timelineCount") is not None:
                timeline_remote["count"] = payload.get("timelineCount")
            timeline = self._call_remote("/astroextra/returns", timeline_remote)
            t_rows = timeline.get("rows") if isinstance(timeline, dict) else None
            if not isinstance(t_rows, list):
                raise ToolTransportError(
                    "日月返照年表端点返回了意外形状。",
                    code="tool.extrareturns_timeline_failed",
                    details={"endpoint": "/astroextra/returns"},
                )
            result["timeline"] = t_rows
            timeline_lines = ["[日月返照年表]"]
            for row in t_rows:
                if not isinstance(row, dict):
                    continue
                solar = row.get("solarReturn") if isinstance(row.get("solarReturn"), dict) else {}
                lunar = row.get("lunarReturn") if isinstance(row.get("lunarReturn"), dict) else {}
                solar_asc = row.get("solarAsc") if isinstance(row.get("solarAsc"), dict) else {}
                lunar_asc = row.get("lunarAsc") if isinstance(row.get("lunarAsc"), dict) else {}
                bits = [f"{row.get('year')}："]
                if solar.get("datetime"):
                    asc_txt = f"（升 {_sign_degree(solar_asc.get('lon'))}）" if solar_asc.get("lon") is not None else ""
                    bits.append(f"日返 {solar.get('datetime')}{asc_txt}")
                if lunar.get("datetime"):
                    asc_txt = f"（升 {_sign_degree(lunar_asc.get('lon'))}）" if lunar_asc.get("lon") is not None else ""
                    bits.append(f"　首月返 {lunar.get('datetime')}{asc_txt}")
                timeline_lines.append("".join(bits))
            section = "\n".join(timeline_lines)
            snapshot_text = f"{snapshot_text}\n\n{section}" if snapshot_text else section
        result["snapshot_text"] = snapshot_text
        result["export_snapshot"] = self._augment_export_payload(technique="extrareturns", snapshot_text=snapshot_text)
        return result

    def _run_shenshu_tool(self, payload: dict[str, Any], key: str) -> dict[str, Any]:
        # 神数 family (wangji / wuzhao / taixuan / jingjue / shenyishu + 9 kinastro-*): each is a kentang engine
        # mounted on the chart service that returns a backend-built `snapshot` text whose [小节] headers already
        # match 星阙's aiExport preset. The skill splits date/time into year/month/day/hour/minute, forwards the
        # 晚子时 switches + gender/place, and routes technique knobs through the shenshu_options key table
        # (typed, per tool; unknown keys are receipted in data.params_ignored instead of silently dropped).
        endpoint = _SHENSHU_ENDPOINTS[key]
        parts = _split_birth_ymdhm(payload)
        # 旧 options 是整包 update 进请求体，有人把 gender/zone 之类核心键写在 options 里——这类键不是技法旋钮，
        # 但也不该因为换了键表就被当成「未识别」丢掉：顶层没给时提升为顶层键（顶层已给则以顶层为准）。
        raw_options = payload.get("options") if isinstance(payload.get("options"), dict) else None
        promoted: dict[str, Any] = {}
        if raw_options:
            technique_knobs = SHENSHU_OPTION_KNOBS.get(key, {})
            promoted = {
                k: v for k, v in raw_options.items()
                if k in _SHENSHU_PROMOTABLE_OPTION_KEYS and k not in technique_knobs and payload.get(k) is None and v is not None
            }
            if promoted:
                payload = {**payload, **promoted, "options": {k: v for k, v in raw_options.items() if k not in promoted}}
        knobs = resolve_shenshu_options(
            key, payload, set(TOOL_DEFINITIONS[key].input_model.model_fields), set(_SHENSHU_GENERIC_KEYS)
        )
        if promoted:
            knobs.applied = sorted(set(knobs.applied) | set(promoted))
        remote_payload: dict[str, Any] = {
            **parts,
            "date": payload.get("date"),
            "time": payload.get("time"),
            "after23NewDay": payload.get("after23NewDay", 1),
            "lateZiHourUseNextDay": payload.get("lateZiHourUseNextDay", 1),
        }
        # kinastro 族读 gender + zone（四柱权威口径按时区定气/立春界）+ 经纬；策天/七政另读地名 pos
        # （上游 kinAstroFieldsSync.parseFieldsDateTime 同集下发，:56-83）。后端不读的键无害。
        for extra in ("gender", "lat", "lon", "gpsLat", "gpsLon", "zone", "pos"):
            if payload.get(extra) is not None:
                remote_payload[extra] = payload.get(extra)
        remote_payload.update(knobs.backend)
        settings_applied: dict[str, dict[str, Any]] = {}
        replay_note = ""
        result_extra: dict[str, Any] = {}
        if key in {"jingjue", "taixuan"}:
            # 🔴 起筮种子（sync311 F1/F2）：上游无头挂载按起课时刻 yyyyMMddHHmm mod 1e9 派生（同刻同卦），
            # 显式 seed 覆盖（0 合法，挂载自检 F-23）。此前 skill 不发 seed：荆诀后端 random.randint 真随机、
            # 太玄后端缺省只到小时（yyyyMMddHH）——同一时刻两次调用得不同卦 / 同一小时内恒同卦。
            explicit = knobs.backend.get("seed")
            seed = int(explicit) % 1_000_000_000 if explicit is not None else _upstream_cast_time_seed(parts)
            remote_payload["seed"] = seed
            result_extra["seed"] = seed
            settings_applied["seed"] = {
                "label": "起筮种子" + ("（显式）" if explicit is not None else "（起课时刻 yyyyMMddHHmm mod 1e9 派生）"),
                "value": seed,
            }
        elif key == "wuzhao":
            remote_payload, replay_note = self._wuzhao_calc_payload(payload, parts, knobs.backend, remote_payload, settings_applied, result_extra)
        elif key == "cetian":
            # 流年年份缺省=「今年」（webcetiansrv.py:496-500 datetime.now()）：同一盘明年再算结果就变。
            # 书法（默认）下显式钉住当年并记进技法卡，读者看得到这份结果是按哪一年起的流年。
            if remote_payload.get("method", "book") == "book" and "liunianYear" not in remote_payload:
                remote_payload["liunianYear"] = datetime.now().year
                settings_applied["liunianYear"] = {"label": "流年年份（未指定→取今年）", "value": remote_payload["liunianYear"]}
        elif key == "qizhengkin":
            # 大运所在年缺省=「今年」（webqizhengkinsrv.py:546 datetime.now()）：同 cetian，钉住并入卡。
            if "qizhengKinCurrentYear" not in remote_payload and "currentYear" not in remote_payload:
                remote_payload["qizhengKinCurrentYear"] = datetime.now().year
                settings_applied["qizhengKinCurrentYear"] = {
                    "label": "大运所在年（未指定→取今年）", "value": remote_payload["qizhengKinCurrentYear"],
                }
            if remote_payload.get("qizhengKinTransitMode") == "now" or remote_payload.get("transitMode") == "now":
                settings_applied["qizhengKinTransitMode"] = {"label": "过运（此刻：随调用时刻变化）", "value": "now"}
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
        if replay_note:
            # 上游 buildWuZhaoSnapshotForFields：回落干支起例后复现说明并入 [揲筮] 段（:394）。
            snapshot_text = _append_replay_note(snapshot_text, "揲筮", replay_note)
        # 铁板「框架推演层」五段：kinastro 后端出盘面与条文，刻分/三元/八卦滚这层是上游前端按四柱
        # 本地推演的。后端响应里的 pillars 即入参，失败只是这几段不出。
        if key == "tieban":
            try:
                framework = self.js_client.run(
                    "tieban_framework",
                    {
                        "pillars": (response or {}).get("pillars") if isinstance(response, dict) else None,
                        "birthYear": parts.get("year"),
                        "gender": payload.get("gender"),
                        # 上游 KinAstroMain.buildKinAstroSnapshotForFields（:329-346）读 tiebanSchool /
                        # tiebanKeSystem / tiebanKe，缺省 south / qing8 / 1（初刻）——考刻是占者核六亲后手定，
                        # 不由钟点换算（sync311 F8：此前读 options.school/keSystem、刻按时分自算，皆非上游口径）。
                        **{k: v for k, v in knobs.skill.items() if k in {"tiebanSchool", "tiebanKeSystem", "tiebanKe"}},
                    },
                )
                extra = f"{(framework or {}).get('text') or ''}".strip()
                fw_data = (framework or {}).get("data") if isinstance(framework, dict) else None
                if isinstance(fw_data, dict) and fw_data.get("ok") is False:
                    _degrade("tieban framework snapshot not produced: %s", (fw_data.get("error") or {}).get("message"))
                if extra:
                    # 上游 `${text}\n\n${suffix}`（KinAstroMain.js:346）：框架段与盘面之间空一行。
                    snapshot_text = f"{snapshot_text}\n\n{extra}".strip()
            except Exception as exc:  # noqa: BLE001 — 富化失败不影响盘面
                _degrade("tieban framework snapshot failed: %s", exc)
        # 演禽「演法」五段（流派/起禽/择日/占卜/投胎）：kinastro 后端不产，它们是上游前端按出生四数
        # 本地推演的（yanqin/yanqinSnapshot.js），与盘面互补。追加在后端快照之后。
        if key == "xianqin":
            snapshot_text = self._append_yanqin_yanfa(payload, parts, knobs, snapshot_text, settings_applied)
        result: dict[str, Any] = {
            "engine": response.get("engine") if isinstance(response, dict) else key,
            "raw": response,
            **result_extra,
        }
        # [判词原文]（v0.33.0 批 I-5，/cetian/texts）：textKey=list 出目录 / all 全库 / <键> 单篇。条件段。
        if key == "cetian" and payload.get("textKey"):
            text_key = str(payload.get("textKey")).strip()
            texts_raw = self._call_remote("/cetian/texts", {})
            texts = (texts_raw or {}).get("texts") if isinstance(texts_raw, dict) else None
            if not isinstance(texts, dict) or not texts:
                raise ToolTransportError(
                    "策天判词库端点返回了意外形状。",
                    code="tool.cetian_texts_failed",
                    details={"endpoint": "/cetian/texts"},
                )
            result["texts"] = texts if text_key in ("all",) else {k: texts[k] for k in texts if text_key in ("list", k)}
            text_lines: list[str] = []
            if text_key == "list":
                text_lines.append(f"判词库 {len(texts)} 篇（textKey 取单篇）：")
                for k, v in texts.items():
                    n_chars = sum(len(f"{s.get('body') or ''}") for s in (v.get("sections") or []) if isinstance(s, dict))
                    text_lines.append(f"{k}：{v.get('title')}（{n_chars} 字）")
            else:
                picked = texts if text_key == "all" else ({text_key: texts[text_key]} if text_key in texts else {})
                if not picked:
                    raise ToolValidationError(
                        f"判词库无此篇：{text_key}（可用键：{'、'.join(texts.keys())}；或 textKey=list 看目录）。",
                        code="tool.cetian_text_unknown_key",
                        details={"available": sorted(texts.keys())},
                    )
                for k, v in picked.items():
                    text_lines.append(f"《{v.get('title')}》（{k}）")
                    for s in v.get("sections") or []:
                        if isinstance(s, dict):
                            subtitle = f"{s.get('subtitle') or ''}".strip()
                            if subtitle:
                                text_lines.append(f"· {subtitle}")
                            text_lines.append(f"{s.get('body') or ''}".strip())
            if snapshot_text and text_lines:
                snapshot_text = f"{snapshot_text}\n\n[判词原文]\n" + "\n".join(text_lines)
        if key == "wangji":
            snapshot_text = self._apply_wangji_xinyi(payload, parts, snapshot_text, result)
        result["params_applied"] = knobs.applied
        result["params_ignored"] = knobs.ignored
        if knobs.ignored:
            # 口径回执（AGENTS §5.12）：认不出的键不转发、原样回执，并在 envelope.warnings 说一声。
            result["_warnings"] = [
                f"{key} 未识别的旋钮已忽略（未转发后端）：{'、'.join(knobs.ignored)}；键表见 "
                f"horosa_agent_guidance(tool_name=\"{key}\").options_keys。"
            ]
        if settings_applied:
            result["settings_applied"] = settings_applied
        result["snapshot_text"] = snapshot_text
        result["export_snapshot"] = self._augment_export_payload(technique=key, snapshot_text=snapshot_text)
        return result

    def _wuzhao_calc_payload(
        self,
        payload: dict[str, Any],
        parts: dict[str, int],
        backend_knobs: dict[str, Any],
        remote_payload: dict[str, Any],
        settings_applied: dict[str, dict[str, Any]],
        result_extra: dict[str, Any],
    ) -> tuple[dict[str, Any], str]:
        """五兆计算键（sync311 F3/F4）：镜像上游 buildWuZhaoSnapshotForFields（WuZhaoMain.js:368-396）。

        * 11 个计算键全量下发（缺省同上游 DEFAULT_OPTIONS）；
        * 性别：五兆后端只认 'male'/'female'（webwuzhaosrv.py:497-499）——顶层 gender 1/0 与 options.gender
          （输入归一化会把嵌套 'male' 改成 1）一律归回 'male'/'female'，此前恒被后端清成「未指定」；
        * 随机诸式：敦煌揲筮 / 以钱代筮（自动掷）后端按 castSeed 定兆（v3.11「按存档兆数复现」同一枚种子）——
          缺省由起课时刻派生（同刻同兆，与灵棋经/太玄/荆诀同一「以时起卦」语义），显式 castSeed 覆盖；
        * 折竹（日/时/分干起盘）与唐法揲筮的随机分爻后端不吃种子，无头不可复现：未开 manual 手动分爻复现时
          照上游挂载回落干支起例，并把上游原句「复现说明」并入 [揲筮] 段 + envelope 警告（不静默）。
        """
        calc = {**_WUZHAO_CALC_DEFAULTS}
        calc.update({k: v for k, v in backend_knobs.items() if k in _WUZHAO_CALC_DEFAULTS})
        if "gender" not in backend_knobs:
            gender = payload.get("gender")
            calc["gender"] = {1: "male", 0: "female", "1": "male", "0": "female"}.get(gender, "") if gender is not None else ""
        mode = calc["mode"]
        replay_note = ""
        if mode in {"day", "hour", "minute", "tang"} and not calc["manual"]:
            replay_note = (
                f"挂载无法复现随机起兆(所选「{_WUZHAO_MODE_LABELS[mode]}」需开启「手动分爻复现」并填分爻数;存档亦无兆数)"
                "→ 已按干支起例"
            )
            calc["mode"] = "ganzhi"
            _degrade(
                "五兆 %s 在无头起课下不可复现（后端随机分爻不吃种子）：已按上游挂载口径回落干支起例；"
                "要该法请传 options.manual=true + manualSplits（六数）", mode,
                note=f"五兆「{_WUZHAO_MODE_LABELS[mode]}」无 manual 手动分爻时不可复现，已回落干支起例（见 [揲筮] 复现说明）。",
            )
        out = {k: v for k, v in remote_payload.items() if k != "castSeed"}
        out.update(calc)
        random_cast = calc["mode"] == "dunhuang" or (calc["mode"] == "qian" and bool(calc["qianAuto"]))
        if random_cast:
            explicit = backend_knobs.get("castSeed")
            cast_seed = int(explicit) if explicit is not None else _upstream_cast_time_seed(parts)
            out["castSeed"] = cast_seed
            result_extra["castSeed"] = cast_seed
            settings_applied["castSeed"] = {
                "label": "起兆种子" + ("（显式）" if explicit is not None else "（起课时刻 yyyyMMddHHmm mod 1e9 派生）"),
                "value": cast_seed,
            }
        settings_applied["mode"] = {"label": "五兆起例", "value": calc["mode"]}
        return out, replay_note

    def _append_yanqin_yanfa(
        self,
        payload: dict[str, Any],
        parts: dict[str, int],
        knobs: Any,
        snapshot_text: str,
        settings_applied: dict[str, dict[str, Any]],
    ) -> str:
        """演禽「演法」五段（sync311 F7/F17）。

        * 流派 + 六开关（school/woBi/xunOffset/monthVerse/huoYaoVariant/sansuo/qinWuxing）逐次调用传入
          （上游经 yanqinStore 全局单例；headless 无 localStorage，此前恒池本理默认、六开关不可设）；
        * 农历月：上游无头路径经 deriveLocalNongliAsync 取权威 monthInt 注入（KinAstroMain.js:351-359）——
          这里同样走 /nongli/time（钟表时，演禽不吃真太阳时），调用方显式 lunarMonth 优先；取数失败
          只降级为引擎内置农历换算并在 warnings 说明（域外年份会退公历月）。
        """
        lunar_month = knobs.backend.get("lunarMonth")
        if lunar_month is None:
            lunar_month = self._xianqin_lunar_month(payload)
        yanfa_payload: dict[str, Any] = {
            "year": parts.get("year"),
            "month": parts.get("month"),
            "day": parts.get("day"),
            "hour": parts.get("hour", 0),
            **({"lunarMonth": lunar_month} if lunar_month is not None else {}),
            **knobs.skill,
        }
        try:
            yanfa = self.js_client.run("yanqin_yanfa", yanfa_payload)
        except Exception as exc:  # noqa: BLE001 — 富化失败不影响盘面
            _degrade("yanqin 演法 snapshot failed: %s", exc)
            return snapshot_text
        data = (yanfa or {}).get("data") if isinstance(yanfa, dict) else None
        if isinstance(data, dict) and data.get("ok") is False:
            error = data.get("error") or {}
            if error.get("code") != "invalid_setting":
                _degrade("yanqin 演法 snapshot failed: %s", error.get("message") or error)
                return snapshot_text
            raise ToolValidationError(
                bilingual(
                    f"演禽演法设置不被引擎接受：{error.get('message') or '未知'}",
                    f"yanqin yanfa setting rejected by the engine: {error.get('message') or 'unknown'}",
                ),
                code="tool.yanqin_invalid_setting",
                details={"error": error},
            )
        if isinstance(data, dict) and isinstance(data.get("settings"), dict):
            settings_applied["yanqinSchool"] = {"label": "演法流派", "value": data["settings"].get("school")}
        if lunar_month is not None:
            settings_applied["yanqinLunarMonth"] = {"label": "演法农历月", "value": lunar_month}
        extra = f"{(yanfa or {}).get('text') or ''}".strip()
        # 上游 `text + '\n\n' + yanfa`（KinAstroMain.js:359）：演法段与盘面之间空一行。
        return f"{snapshot_text}\n\n{extra}".strip() if extra else snapshot_text

    def _xianqin_lunar_month(self, payload: dict[str, Any]) -> int | None:
        try:
            nongli = self._call_remote(
                "/nongli/time",
                {
                    "date": payload.get("date"),
                    "time": payload.get("time") or "00:00:00",
                    # 上游域外农历远程桥缺时地时的兜底（divinationTimeDraft.deriveNongliRemote :306-307）。
                    "zone": payload.get("zone") or "+08:00",
                    "lat": payload.get("lat") or "0n00",
                    "lon": payload.get("lon") or "0e00",
                    # 演禽只取生辰原始钟表时刻（techniqueMountSettings xianqin 注：ken 引擎不消费真太阳时）：
                    # 缺经纬时若按真太阳时，0e00 会把钟点整体拨 8 小时、跨日换月。
                    "timeAlg": 1,
                    **_day_boundary_switches(payload),
                },
            )
        except HorosaSkillError as exc:
            _degrade("演禽演法农历月经 /nongli/time 取数失败（%s）：月禽/投胎改按引擎内置农历换算", exc)
            return None
        month = nongli.get("monthInt") if isinstance(nongli, dict) else None
        if isinstance(month, int) and 1 <= month <= 12:
            return month
        _degrade("演禽演法农历月：/nongli/time 未返回 monthInt（%r），月禽/投胎改按引擎内置农历换算", month)
        return None

    def _apply_wangji_xinyi(
        self, payload: dict[str, Any], parts: dict[str, int], snapshot_text: str, result: dict[str, Any]
    ) -> str:
        """皇极经世 [心易发微]（sync311 F15）：镜像上游 buildHuangJiSnapshotForFields（HuangJiMain.js:161-198）。

        上游挂载缺省起心易 = datetime（techniqueMountSettings huangji.xinyiMethod default 'datetime'），
        所选之法经 /wangji/xinyi 起卦后**就放进 [心易发微]**（buildSnapshotText :117-122，逐键 `键：值`）；
        'none' = 不算心易、整段不出。后端 /pan 自带的 [心易发微] 是把 {method,result,sections} 包装整体
        str() 出来的（「method：datetime / result：本卦：…」），上游前端从不采用它——这里整段替换。
        入参全量照上游：upperNum 5 / lowerNum 10 / upperStrokes 5 / lowerStrokes 8 / objectGua 離 / direction 南，
        时辰=盘面时辰（xinyiHour 可覆写）；卦名/方位收简体并归一到后端唯一认得的繁体。
        """
        method = f"{payload.get('xinyiMethod') or 'datetime'}".strip() or "datetime"
        if method not in _WANGJI_XINYI_METHODS:
            raise ToolValidationError(
                bilingual(
                    f"心易起卦法 {method!r} 不存在（可选：{'/'.join(_WANGJI_XINYI_METHODS)}）。",
                    f"Unknown xinyiMethod {method!r} (choose one of {'/'.join(_WANGJI_XINYI_METHODS)}).",
                ),
                code="tool.wangji_invalid_xinyi_method",
                details={"xinyiMethod": method, "allowed": list(_WANGJI_XINYI_METHODS)},
            )
        if method == "none":
            return _replace_snapshot_section(snapshot_text, "心易发微", None)
        object_gua = f"{payload.get('objectGua') or '離'}".strip()
        object_gua = _WANGJI_TRIGRAM_ALIASES.get(object_gua, object_gua)
        direction = f"{payload.get('xinyiDirection') or '南'}".strip()
        direction = _WANGJI_DIRECTION_ALIASES.get(direction, direction)
        if object_gua not in _WANGJI_TRIGRAMS or direction not in _WANGJI_DIRECTIONS:
            raise ToolValidationError(
                bilingual(
                    f"心易方位法入参不合法：objectGua={object_gua!r}（可选 {'/'.join(_WANGJI_TRIGRAMS)}），"
                    f"xinyiDirection={direction!r}（可选 {'/'.join(_WANGJI_DIRECTIONS)}；简体亦可）。",
                    "Invalid xinyi direction-method input (objectGua / xinyiDirection; simplified forms are accepted).",
                ),
                code="tool.wangji_invalid_xinyi_direction",
                details={"objectGua": object_gua, "xinyiDirection": direction,
                         "allowed_objectGua": list(_WANGJI_TRIGRAMS), "allowed_direction": list(_WANGJI_DIRECTIONS)},
            )

        def _num(field: str, default: int) -> Any:
            value = payload.get(field)
            return default if value is None else value

        xinyi_remote: dict[str, Any] = {
            **parts,
            "date": payload.get("date"),
            "time": payload.get("time"),
            "method": method,
            "upperNum": _num("upperNum", 5),
            "lowerNum": _num("lowerNum", 10),
            "upperStrokes": _num("upperStrokes", 5),
            "lowerStrokes": _num("lowerStrokes", 8),
            "objectGua": object_gua,
            "direction": direction,
        }
        if payload.get("xinyiHour") is not None:
            xinyi_remote["hour"] = payload.get("xinyiHour")
        try:
            # ⚠ _unwrap_result 会连剥 {Result:{…}} 与内层小写 {result:{…}} 两层 —— 这里拿到的
            # 直接就是卦面 dict（本卦/變卦/動爻/體用…），外层的 method/sections 已被剥掉。
            xinyi = self._call_remote("/wangji/xinyi", xinyi_remote)
        except HorosaSkillError as exc:
            if payload.get("xinyiMethod"):
                raise
            # 缺省（datetime）心易失败不拖主盘（上游 :195 同律），但不静默：段撤掉 + warnings 说明。
            _degrade("皇极经世缺省心易（datetime）起卦失败：%s", exc)
            return _replace_snapshot_section(snapshot_text, "心易发微", None)
        if not isinstance(xinyi, dict) or not xinyi or "本卦" not in xinyi:
            if payload.get("xinyiMethod"):
                raise ToolTransportError(
                    "心易起卦端点返回了意外形状。",
                    code="tool.wangji_xinyi_failed",
                    details={"endpoint": "/wangji/xinyi", "method": method,
                             "keys": sorted(xinyi.keys()) if isinstance(xinyi, dict) else type(xinyi).__name__},
                )
            _degrade("皇极经世缺省心易（datetime）起卦返回意外形状（%s）", type(xinyi).__name__)
            return _replace_snapshot_section(snapshot_text, "心易发微", None)
        result["xinyi"] = {"method": method, "result": xinyi}
        body = [f"{k}：{_human_scalar(v)}" for k, v in xinyi.items()]
        return _replace_snapshot_section(snapshot_text, "心易发微", body)

    # 卜卦 / 择日 JS 引擎的「请求顶层」转交：判读全局层（judgeLayerOverrides 同形）与页面覆盖都从这里取。
    # 只收标量（dict/list 形的 orbs/customTerms*/natal 与判读无关，且会把 JS 管道撑大）。
    _DIVINATION_PARAM_SKIP = frozenset({"options", "natal", "chart", "datetime", "dirZone", "dirLat", "dirLon"})

    @classmethod
    def _divination_params(cls, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            k: v for k, v in payload.items()
            if k not in cls._DIVINATION_PARAM_SKIP and not isinstance(v, (dict, list, tuple))
        }

    @staticmethod
    def _raise_invalid_divination_inputs(tool: str, invalid: Any) -> None:
        if not isinstance(invalid, list) or not invalid:
            return
        parts = [
            f"{item.get('key')}={item.get('value')!r}（可选：{item.get('allowed')}）"
            for item in invalid if isinstance(item, dict)
        ]
        raise ToolValidationError(
            bilingual(
                f"{tool} 设置取值无效：{'；'.join(parts)}。",
                f"{tool} setting(s) invalid: {'; '.join(parts)}.",
            ),
            code=f"tool.{tool}_invalid_setting",
            details={"invalid": invalid},
        )

    def _horary_backend_fields(self, payload: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        """流派档 → /chart 字段补丁（JS horary action=backend_fields，即上游 horaryBackendFields(school, overrides)）。

        上游页面 `{ zodiacal: 0, ...horaryBackendFields(school) }`（HoraryMain.js:543）、挂载再生 aiAnalysisContext.js:2264：
        宫制 / 界系 / 星群 / 福点反转 / 三分集随流派下发；显式覆盖（options 或卜卦自己的 hsys/termsVariant/
        geminiBoundEmended/tradition/tripSystem）压过流派。取不到就不能起盘——宫头、宫主、尊贵全随它变。"""
        js = self.js_client.run(
            "horary",
            {"action": "backend_fields", "school": payload.get("school") or "classical", "options": payload.get("options"), "params": params},
        )
        data = js.get("data") if isinstance(js, dict) else None
        fields = data.get("backendFields") if isinstance(data, dict) else None
        if not isinstance(fields, dict) or fields.get("hsys") is None:
            raise ToolTransportError(
                "卜卦流派起盘字段取不到（JS horary backend_fields 返回形状异常）。",
                code="tool.horary_backend_fields_failed",
                details={"school": payload.get("school") or "classical", "response_keys": sorted(js) if isinstance(js, dict) else None},
            )
        return data

    def _run_horary_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 卜卦 (horary): cast the traditional chart at the question moment, then run the vendored 星阙
        # horary engine (runHorary + buildHorarySnapshot) over it. category drives the quesited house.
        category = f"{payload.get('category') or 'general'}".strip() or "general"
        params = self._divination_params(payload)
        backend = self._horary_backend_fields(payload, params)
        backend_fields: dict[str, Any] = dict(backend["backendFields"])
        school = f"{backend.get('school') or payload.get('school') or 'classical'}"
        # 流派学理绑定键（界系/双子界序/福点反转/宫制/星群/三分集）恒以流派为准（上游 HoraryMain.js:563 globalSyncKeys
        # 注释）：顶层的 triplicity / lotReversal 是**全局**古典设置，卜卦盘不跟 —— 与流派不同就说出来，不静默吞。
        for key in ("triplicity", "lotReversal"):
            given = payload.get(key)
            if given is not None and f"{given}" != f"{backend_fields.get(key)}":
                _degrade(
                    "horary: top-level %s=%r overridden by school %s (%r)", key, given, school, backend_fields.get(key),
                    note=(
                        f"卜卦盘的 {key} 随流派档（{school} → {backend_fields.get(key)}），顶层全局设置 {key}={given!r} 不作用于卜卦盘"
                        "（上游同口径）；要改三分集请用 tripSystem（ptolemaic/dorothean）或换流派。"
                    ),
                )
        chart_payload = {**payload, "predictive": 0, "zodiacal": payload.get("zodiacal", 0), **backend_fields}
        for stale in ("datetime", "dirZone", "dirLat", "dirLon", "category", "school", "options",
                      "sincerityConfirmed", "confirmYouthMatch", "isEventChart", "questionText", "castingCamp"):
            chart_payload.pop(stale, None)
        response = self._call_remote("/chart", chart_payload)
        snapshot_text, data, snapshot_error = "", {}, None
        try:
            js = self.js_client.run(
                "horary",
                {
                    "chart": response,
                    "category": category,
                    "school": school,
                    # 判读层覆写（第 4 层）：JS 侧按引擎自带词表 HORARY_PARAM_BY_KEY 过滤，认不出的键
                    # 原样回执在 data.params_ignored（不静默吞）。顶层古典键 → 全局层（第 2 层）。
                    "options": payload.get("options"),
                    "params": params,
                    # 定盘自评（上游页面左栏三勾选，HoraryMain.js:487-497）+ 问句/阵营（→ [定盘考量]）。
                    **{k: payload[k] for k in ("sincerityConfirmed", "confirmYouthMatch", "isEventChart", "questionText", "castingCamp")
                       if payload.get(k) is not None},
                },
            )
            if isinstance(js, dict):
                data = js.get("data") if isinstance(js.get("data"), dict) else {}
                self._raise_invalid_divination_inputs("horary", data.get("invalid_inputs"))
                snapshot_text = f"{js.get('snapshot_text') or ''}".strip()
                # the JS engine resolves an unknown category back to 'general'; reflect that.
                category = f"{js.get('category') or category}".strip() or category
        except ToolValidationError:
            raise
        except Exception as exc:  # don't fail the chart, but don't hide the empty snapshot either
            snapshot_error = str(exc)
            _degrade("horary JS engine failed (category=%s): %s", category, exc)
        result = {
            "chart": response.get("chart"),
            "category": category,
            "school": school,
            # 起盘口径回执：流派档实际下发给 /chart 的字段（宫制/界系/三分集/福点反转/星群）。
            "backendFields": backend_fields,
            "judgment": data,
            "raw": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="horary", snapshot_text=snapshot_text),
        }
        if snapshot_error:
            result["snapshot_error"] = snapshot_error
        return result

    _ELECTION_TOPIC_INPUTS = ("tradeSide", "talismanStar", "surgeryPart", "surgeryPartOpposite")

    def _election_resolve(self, payload: dict[str, Any], params: dict[str, Any]) -> dict[str, Any] | None:
        """JS election action=resolve_params：四层有效口径 eff（含 pdTimeKey）+ 流派宫制联动 schoolHsys。

        引擎自己的 resolveElectionParams / westernSchools 给值，Python 不手抄流派表。取不到 → None（调用方降级并说出来）；
        认不出的全局判读键值 → ToolValidationError（同判读路径）。"""
        try:
            js = self.js_client.run(
                "election",
                {"action": "resolve_params", "school": payload.get("school"), "options": payload.get("options"), "params": params},
            )
        except Exception as exc:  # noqa: BLE001
            _degrade("election resolve_params failed: %s", exc)
            return None
        data = (js or {}).get("data") if isinstance(js, dict) else None
        if not isinstance(data, dict):
            _degrade("election resolve_params: JS 工具返回形状异常（缺 data）")
            return None
        self._raise_invalid_divination_inputs("election", data.get("invalid_inputs"))
        return data

    def _election_crisis(self, payload: dict[str, Any], js_payload: dict[str, Any]) -> None:
        """危象日参照（WP-8）：病始日期 → 上游 fetchCrisisBase（ElectionMain.js:159-171）同口径——该日正午、择日地点与盘式
        起盘，JS 侧 buildFacts 取月黄经成 crisisBase={date, moonLon}。也收上游存档形状 {date, moonLon} 直通。"""
        raw = payload.get("crisisBase")
        if raw is None or raw == "":
            return
        if isinstance(raw, dict):
            js_payload["crisisBase"] = raw
            return
        date = f"{raw}".strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            raise ToolValidationError(
                bilingual(f"crisisBase（病始日期）须为 YYYY-MM-DD：{raw!r}", f"crisisBase (illness onset date) must be YYYY-MM-DD: {raw!r}"),
                code="tool.election_invalid_setting",
                details={"invalid": [{"key": "crisisBase", "value": raw, "allowed": "YYYY-MM-DD 或 {date, moonLon}"}]},
            )
        fields_like = {k: payload.get(k) for k in ("zone", "lon", "lat", "gpsLat", "gpsLon", "hsys", "zodiacal", "siderealAyanamsa", "tradition")}
        try:
            crisis_chart = self._chart_at_moment(f"{date} 12:00:00", fields_like)
        except Exception as exc:  # noqa: BLE001 — 病始盘起不来：[危象日参照] 缺席并说出来
            _degrade("election crisis chart failed: %s", exc, note=f"择日 [危象日参照] 未产出：病始日 {date} 正午起盘失败（{exc}）。")
            return
        if crisis_chart is None:
            _degrade("election crisis chart empty", note=f"择日 [危象日参照] 未产出：病始日 {date} 正午起盘返回异常形状。")
            return
        js_payload["crisisChart"] = crisis_chart
        js_payload["crisisDate"] = date

    def _run_election_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 择日 (electional): cast the traditional chart at a candidate moment, then run the vendored 星阙
        # election engine (runElection + buildElectionSnapshot). topicId drives the rule pack + hard flags.
        topic_id = f"{payload.get('topicId') or payload.get('topic') or 'marriage'}".strip() or "marriage"
        # natal（可选，本命出生资料）：先验全再起任何盘——缺字段是输入错，不许半途静默少段。
        natal_spec = self._election_natal_spec(payload)
        params = self._divination_params(payload)
        # 流派宫制联动（westernSchools.js hsys）：切档即 patchFields({hsys})（ElectionMain.js:348-353）、挂载再生
        # chartRecord.hsys = sc.hsys（aiAnalysisContext.js:2316-2327）；现代主流档 hsys=null 不联动、页面缺省 0（:100）。
        # 显式 hsys 压过流派（同卜卦）。只在有流派档或要拉主限（natal）时才问 JS，缺省路径零额外进程。
        resolved = self._election_resolve(payload, params) if (payload.get("school") or natal_spec is not None) else None
        if payload.get("hsys") is None:
            school_hsys = (resolved or {}).get("schoolHsys")
            if payload.get("school") and resolved is None:
                _degrade("election school hsys unresolved", note="择日流派宫制联动未取到（JS 口径解析失败），本盘按整宫制 0 起。")
            payload = {**payload, "hsys": school_hsys if school_hsys is not None else 0}
        chart_payload = {**payload, "predictive": 0, "tradition": payload.get("tradition", 1)}
        for stale in ("datetime", "dirZone", "dirLat", "dirLon", "topicId", "topic", "school", "options", "natal",
                      "crisisBase", *self._ELECTION_TOPIC_INPUTS):
            chart_payload.pop(stale, None)
        response = self._call_remote("/chart", chart_payload)
        js_payload: dict[str, Any] = {
            "chart": response,
            "topicId": topic_id,
            # 流派档 + 13 个判读层参数：JS 侧按 ELECTION_PARAM_BY_KEY 过滤并回执。
            "school": payload.get("school"),
            "options": payload.get("options"),
            # 请求顶层 → 判读全局层（judgeLayerOverrides 同形，第 2 层）。
            "params": params,
            # 用事专属四键（上游左栏按用事显示：买卖方向 / 护符主星 / 手术部位 / 部位延及对宫）。
            **{k: payload[k] for k in self._ELECTION_TOPIC_INPUTS if payload.get(k) is not None},
        }
        self._election_crisis(payload, js_payload)
        natal_returns: dict[str, Any] | None = None
        if natal_spec is not None:
            natal_returns = self._attach_election_natal(payload, natal_spec, js_payload, resolved=resolved)
        snapshot_text, data, snapshot_error = "", {}, None
        try:
            js = self.js_client.run("election", js_payload)
            if isinstance(js, dict):
                data = js.get("data") if isinstance(js.get("data"), dict) else {}
                self._raise_invalid_divination_inputs("election", data.get("invalid_inputs"))
                snapshot_text = f"{js.get('snapshot_text') or ''}".strip()
                # the JS engine resolves an unknown topicId back to 'marriage'; reflect that.
                topic_id = f"{js.get('topicId') or topic_id}".strip() or topic_id
                natal_echo = data.get("natal") if isinstance(data.get("natal"), dict) else None
                if natal_spec is not None and natal_echo is not None and not natal_echo.get("integrated"):
                    _degrade("election natal chart not integrated: %s", natal_echo.get("error"))
                returns_echo = data.get("returns") if isinstance(data.get("returns"), dict) else None
                for err in (returns_echo or {}).get("errors") or []:
                    _degrade("election return chart facts failed: %s", err)
                for err in data.get("extra_errors") or []:
                    _degrade("election extra input failed: %s", err, note=f"择日：{err}")
                for key in data.get("unused_inputs") or []:
                    _degrade(
                        "election: %s given but unused by topic %s", key, topic_id,
                        note=f"择日：{key} 只作用于对应用事的规则包（买卖 trade / 护符 talisman / 手术 surgery；病始日 surgery·medication），本次用事 {topic_id} 不读它，未参与判读。",
                    )
        except ToolValidationError:
            raise
        except Exception as exc:  # don't fail the chart, but don't hide the empty snapshot either
            snapshot_error = str(exc)
            _degrade("election JS engine failed (topicId=%s): %s", topic_id, exc)
        result = {
            "chart": response.get("chart"),
            "topicId": topic_id,
            "judgment": data,
            "raw": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="election", snapshot_text=snapshot_text),
        }
        if natal_returns is not None:
            result["natalReturns"] = natal_returns
        if snapshot_error:
            result["snapshot_error"] = snapshot_error
        return result

    # ── 择日·本命合参 + 回归与主限（上游 v3.11 [Q-445]）─────────────────────────────────────────
    # 上游页面：左栏「选本命盘」（ElectionMain.js:173 selectNatal）→ natalFacts 进 runElection（[本命合参]）；
    # 其下两颗按钮「拉日/月返盘」（:204 fetchReturns → returnCharts.fetchReturnSet）与「拉主限命中」
    # （:218 fetchPdHits → returnCharts.fetchPdHitsNearElection）的结果经 extra 进快照 [回归与主限]
    # （ElectionJudgment.js:289 → electionSnapshot.js:120-135）。三者全是 HTTP 编排，按 AGENTS §5 归 Python；
    # JS 只做 buildFacts + 上游 builder 排版（tools/election.js）。
    _ELECTION_NATAL_REQUIRED = ("date", "time", "zone", "lat", "lon")
    # 上游 divination/engine/timeLords.js:209-210（returnCharts.js 的回归周期与平均速率 RATE 都取它）。
    _SOLAR_RETURN_DAYS = 365.25
    _LUNAR_RETURN_DAYS = 27.321661
    # fetchPdHitsNearElection（returnCharts.js:98）：±windowDays（缺省 240）、按 |Δ日| 升序取前 limit（缺省 8）。
    _ELECTION_PD_WINDOW_DAYS = 240
    _ELECTION_PD_LIMIT = 8
    _ELECTION_PD_TIME_KEY_COMPAT = {"Cardan": "Cardano", "Placidus": "Ptolemy"}  # returnCharts.js:106 旧存档值兼容

    def _election_natal_spec(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        natal = payload.get("natal")
        if natal is None:
            return None
        if not isinstance(natal, dict):
            raise ToolValidationError(
                bilingual("natal 必须是本命出生资料对象 {date,time,zone,lat,lon}", "natal must be an object {date,time,zone,lat,lon}"),
                code="tool.election_natal_invalid",
                details={"natal_type": type(natal).__name__},
            )
        missing = [k for k in self._ELECTION_NATAL_REQUIRED if not f"{natal.get(k) or ''}".strip()]
        if missing:
            raise ToolValidationError(
                bilingual(
                    f"本命出生资料不全，缺 {'/'.join(missing)}（本命合参与回归/主限都要完整的出生时刻与地点）",
                    f"natal birth data incomplete: missing {', '.join(missing)}",
                ),
                code="tool.election_natal_missing_fields",
                details={"missing": missing},
            )
        return natal

    def _attach_election_natal(
        self, payload: dict[str, Any], natal: dict[str, Any], js_payload: dict[str, Any], *, resolved: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """起本命盘 + 求日/月返 + 取主限命中，挂到 js_payload（natalChart / extra）。返回回执（时刻与命中）。"""
        hsys = payload.get("hsys") if payload.get("hsys") is not None else 0
        zodiacal = payload.get("zodiacal") if payload.get("zodiacal") is not None else 0
        ayanamsa = payload.get("siderealAyanamsa") or ""
        natal_ad = natal.get("ad") if natal.get("ad") is not None else 1
        natal_date = f"{natal.get('date')}".strip()
        natal_time = f"{natal.get('time')}".strip() or "12:00:00"
        # selectNatal（:173-181）：本命参数 + 页面宫制/黄道 + tradition 1 / predictive 0 / pdaspects。
        natal_chart_payload = _drop_none({
            "ad": natal_ad, "date": natal_date, "time": natal_time,
            "zone": natal.get("zone"), "lat": natal.get("lat"), "lon": natal.get("lon"),
            "gpsLat": natal.get("gpsLat"), "gpsLon": natal.get("gpsLon"),
            "hsys": hsys, "zodiacal": zodiacal, "siderealAyanamsa": ayanamsa,
            "tradition": 1, "predictive": 0, "pdaspects": [0, 60, 90, 120, 180],
        })
        try:
            natal_chart = self._call_remote("/chart", natal_chart_payload)
        except Exception as exc:  # noqa: BLE001 — 本命盘起不来：择日盘照出，合参两段缺席并说出来
            _degrade("election natal chart failed: %s", exc)
            return {"solarReturn": None, "lunarReturn": None, "pdTimeKey": None, "pdHits": [], "error": str(exc)}
        js_payload["natalChart"] = natal_chart

        # fetchReturns（:204）：fieldsLike = 电盘页的地点与盘式（geoFromFields :113）。
        fields_like = {
            "zone": payload.get("zone"), "lon": payload.get("lon"), "lat": payload.get("lat"),
            "gpsLat": payload.get("gpsLat"), "gpsLon": payload.get("gpsLon"),
            "hsys": hsys, "zodiacal": zodiacal, "siderealAyanamsa": ayanamsa,
            "tradition": payload.get("tradition") if payload.get("tradition") is not None else 1,
        }
        election_moment = f"{payload.get('date')} {payload.get('time') or '12:00:00'}"
        solar = lunar = None
        for kind in ("sun", "moon"):
            natal_lon, _ = _chart_body_lon_speed(natal_chart, kind)
            try:
                ret = self._solve_return_before(kind, natal_lon, election_moment, fields_like)
                if ret is None:
                    _degrade("election %s return: 未求得（本命黄经缺失或回归起盘失败）", kind)
            except Exception as exc:  # noqa: BLE001 — 上游 solveReturnBefore 失败 = 该返为 null；这里说出来
                _degrade("election %s return solve failed: %s", kind, exc)
                ret = None
            if kind == "sun":
                solar = ret
            else:
                lunar = ret

        # fetchPdHits（:218-240）：本命参数（日期用 /）+ 页面宫制/黄道 + tradition 1；时间钥匙 = 有效口径 eff.pdTimeKey。
        pd_time_key = self._election_effective_pd_time_key(payload, resolved=resolved)
        natal_params = _drop_none({
            "ad": natal_ad, "date": natal_date.replace("-", "/"), "time": natal_time,
            "zone": natal.get("zone"), "lat": natal.get("lat"), "lon": natal.get("lon"),
            "gpsLat": natal.get("gpsLat"), "gpsLon": natal.get("gpsLon"),
            "hsys": hsys, "zodiacal": zodiacal, "siderealAyanamsa": ayanamsa, "tradition": 1,
        })
        pd_hits = self._election_pd_hits(natal_params, f"{payload.get('date')}", pd_time_key)
        js_payload["extra"] = {"returnSet": {"solar": solar, "lunar": lunar}, "pdHits": pd_hits}
        return {
            "solarReturn": solar.get("momentStr") if solar else None,
            "lunarReturn": lunar.get("momentStr") if lunar else None,
            "pdTimeKey": pd_time_key,
            "pdHits": pd_hits,
        }

    def _election_effective_pd_time_key(self, payload: dict[str, Any], *, resolved: dict[str, Any] | None = None) -> str | None:
        """eff.pdTimeKey 由引擎自己的 resolveElectionParams 给（流派档 × 覆写四层合并），Python 不手抄默认表。"""
        data = resolved if resolved is not None else self._election_resolve(payload, self._divination_params(payload))
        if data is None:
            _degrade("election resolve_params unavailable (主限时间钥匙回落 Ptolemy)")
            return None
        effective = data.get("effective")
        value = effective.get("pdTimeKey") if isinstance(effective, dict) else None
        return f"{value}" if value else None

    def _chart_at_moment(self, moment: str, fields_like: dict[str, Any]) -> dict[str, Any] | None:
        """上游 divination/mundane/momentPipeline.chartAtMoment（:157）的 Python 端口：任意时刻 + 给定地点独立起盘。"""
        date_part, _, time_part = moment.partition(" ")
        params = {
            "ad": 1,
            "date": date_part.replace("-", "/"),
            "time": time_part or "00:00:00",
            "zone": fields_like.get("zone") or "+08:00",
            "lat": fields_like.get("lat") or "0n00",
            "lon": fields_like.get("lon") or "0e00",
            "gpsLat": fields_like.get("gpsLat") if fields_like.get("gpsLat") is not None else 0,
            "gpsLon": fields_like.get("gpsLon") if fields_like.get("gpsLon") is not None else 0,
            "hsys": fields_like.get("hsys") if fields_like.get("hsys") is not None else 0,
            "zodiacal": fields_like.get("zodiacal") if fields_like.get("zodiacal") is not None else 0,
            "siderealAyanamsa": fields_like.get("siderealAyanamsa") if fields_like.get("siderealAyanamsa") is not None else "",
            "tradition": fields_like.get("tradition") if fields_like.get("tradition") is not None else 1,
            "predictive": 0,
            "pdaspects": [0, 60, 90, 120, 180],
        }
        rsp = self._call_remote("/chart", params)
        return rsp if isinstance(rsp, dict) and isinstance(rsp.get("chart"), dict) else None

    def _solve_return_before(
        self, kind: str, natal_lon: float | None, election_moment: str, fields_like: dict[str, Any]
    ) -> dict[str, Any] | None:
        """上游 returnCharts.solveReturnBefore（:23-58）的逐步端口：择日时刻之前最近一次精确日返/月返。

        逐条照搬：种子 = 电盘时刻按「该体已行过的角距 / 平均速率」回推；牛顿迭代 ≤6 次，|Δ| < 0.005° 停；
        速率取该时刻盘的 lonspeed（|v| > 0.05 才用，否则平均速率）；**时间一律换算成整秒**（上游 daysToSec =
        Math.round(d·86400)，Math.round 是 half-up → _js_math_round）；收敛点落在电盘之后则回退一整周期、
        只重起一次盘（上游不再精化）。返回 {momentStr, chart}：chart 是**产出 facts 的那张盘**——上游循环
        未 break 时 t 在最后一次 facts 之后又前推了一步，momentStr 与 facts 来源盘因此可以不同刻，照搬。
        时刻算术为墙钟（无 DST）：等同上游在无夏令时的机器时区（如 Asia/Shanghai）下 moment.js 的行为。
        """
        if natal_lon is None:
            return None
        cycle = self._SOLAR_RETURN_DAYS if kind == "sun" else self._LUNAR_RETURN_DAYS
        rate = 360 / cycle
        try:
            elec = datetime.strptime(election_moment, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
        r0 = self._chart_at_moment(election_moment, fields_like)
        if r0 is None:
            return None
        lon0, _ = _chart_body_lon_speed(r0, kind)
        if lon0 is None:
            return None
        elapsed = ((lon0 - natal_lon) % 360 + 360) % 360
        t = elec - timedelta(seconds=_js_math_round(elapsed / rate * 86400))
        facts_chart: dict[str, Any] | None = None
        for _ in range(6):
            chart = self._chart_at_moment(_fmt_moment(t), fields_like)
            if chart is None:
                return None
            facts_chart = chart
            lon, speed = _chart_body_lon_speed(chart, kind)
            if lon is None:
                return None
            d = ((natal_lon - lon + 540) % 360) - 180
            if abs(d) < 0.005:
                break
            v = abs(speed) if isinstance(speed, (int, float)) and not isinstance(speed, bool) and abs(speed) > 0.05 else rate
            t = t + timedelta(seconds=_js_math_round(d / v * 86400))
        if t > elec:
            t = t - timedelta(seconds=_js_math_round(cycle * 86400))
            chart = self._chart_at_moment(_fmt_moment(t), fields_like)
            if chart is not None:
                facts_chart = chart
        return {"momentStr": _fmt_moment(t), "chart": facts_chart} if facts_chart is not None else None

    def _election_pd_hits(self, natal_params: dict[str, Any], election_date: str, pd_time_key: str | None) -> list[dict[str, Any]]:
        """上游 returnCharts.fetchPdHitsNearElection（:98-128）端口：本命带主限法补拉一盘，取
        predictives.primaryDirection，过滤择日日期 ±240 日，按 |Δ日| 升序取前 8。行 = [弧, 迫星, 应星, 法, 日期]。
        上游失败回 []（静默）；这里同样回 [] 但记降级。"""
        params = {
            **natal_params,
            "predictive": 1,
            "includePrimaryDirection": True,
            "pdtype": 0,
            "showPdBounds": 0,
            "pdMethod": "core_alchabitius",
            "pdTimeKey": self._ELECTION_PD_TIME_KEY_COMPAT.get(pd_time_key or "") or pd_time_key or "Ptolemy",
            "pdDirect": 1,
            "pdConverse": 0,
            "pdAntiscia": 0,
            "pdTerms": 0,
            "pdaspects": [0, 60, 90, 120, 180],
        }
        try:
            rsp = self._call_remote("/chart", params)
        except Exception as exc:  # noqa: BLE001
            _degrade("election primary-direction hits failed: %s", exc)
            return []
        predictives = rsp.get("predictives") if isinstance(rsp, dict) else None
        rows = predictives.get("primaryDirection") if isinstance(predictives, dict) else None
        try:
            elec = datetime.strptime(f"{election_date}"[:10], "%Y-%m-%d").date()
        except ValueError:
            return []
        out: list[dict[str, Any]] = []
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, list) or len(row) < 5 or not row[4]:
                continue
            day = f"{row[4]}"[:10]
            try:
                hit = datetime.strptime(day, "%Y-%m-%d").date()
            except ValueError:
                continue
            delta = (hit - elec).days
            if abs(delta) > self._ELECTION_PD_WINDOW_DAYS:
                continue
            out.append({"promissor": row[1], "significator": row[2], "method": row[3], "date": day, "deltaDays": delta})
        out.sort(key=lambda h: abs(h["deltaDays"]))  # 稳定排序，同上游 Array.prototype.sort
        return out[: self._ELECTION_PD_LIMIT]

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

    @staticmethod
    def _persian_target_datetime(payload: dict[str, Any]) -> str:
        """datetime → 'YYYY-MM-DD HH:mm:ss'；只给日期补正午（与上游 predict 面板日期选择同义）。"""
        target = str(payload.get("datetime") or "").strip().replace("/", "-").replace("T", " ")
        if len(target) == 10:
            target = f"{target} 12:00:00"
        return target

    def _run_persiandirected_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 波斯向运 (Persian Directed)：纯算术读本命盘 objects/houses/birth（上游 AstroPersianDirected.js）。
        # F6（上游 v3.11 [Q-168/T-102]）：主表此前写死 1°/年·顺向·90 年，声明的 rateKey/direction 只进了
        # 可选的指定日期盘；现在 rateKey/direction/maxYears 同时驱动主表（= 上游 builder opts）。
        rate_key = payload.get("rateKey")
        direction = payload.get("direction")
        max_years = payload.get("maxYears")
        if rate_key is not None:
            _require_option(rate_key, tuple(_PERSIAN_RATE), field="rateKey", tool="persiandirected")
        if direction is not None:
            _require_option(direction, ("direct", "converse"), field="direction", tool="persiandirected")
        if max_years is not None:
            number = _finite_number(max_years)
            if number is None or number <= 0:
                raise ToolValidationError(
                    f"persiandirected 的 maxYears={max_years!r} 必须为正数 / maxYears must be a positive number "
                    f"(上游齿轮五档 {list(_PERSIAN_MAX_YEARS_OPTIONS)})。",
                    code="tool.predictive_invalid_option",
                    details={"tool": "persiandirected", "field": "maxYears", "value": max_years,
                             "allowed": list(_PERSIAN_MAX_YEARS_OPTIONS)},
                )
        chart_payload = {**payload, "predictive": 0}
        chart_payload.pop("datetime", None)
        chart_payload.pop("dirZone", None)
        response = self._call_remote("/chart", chart_payload)
        target = self._persian_target_datetime(payload) if payload.get("datetime") else ""
        moment_lines: list[str] = []
        snapshot_text = _build_persiandirected_snapshot_text(
            response,
            {"rateKey": rate_key, "direction": direction, "maxYears": max_years, "datetime": target},
            moment_lines=moment_lines,
        )
        result: dict[str, Any] = {
            "chart": response.get("chart"),
            "raw": response,
            "_moment_lines": moment_lines,
        }
        # [指定日期向运盘]（v0.33.0 批 I-2）：datetime 时后端整铸该日向运盘（/predict/persianchart，
        # getPersianDirectedByDate）。条件段：缺省不产，零回归。
        if payload.get("datetime"):
            directed = self._persianchart_by_date(payload)
            result["directed_chart"] = directed
            section = _build_persianchart_section_text(directed)
            if snapshot_text and section:
                snapshot_text = f"{snapshot_text}\n\n{section}"
        result["snapshot_text"] = snapshot_text
        result["export_snapshot"] = self._augment_export_payload(
            technique="persiandirected", snapshot_text=snapshot_text
        )
        return result

    def _persianchart_by_date(self, payload: dict[str, Any]) -> dict[str, Any]:
        target = self._persian_target_datetime(payload).replace("-", "/")
        remote = {**payload, "datetime": target, "predictive": 0}
        # 上游 v3.11 [Q-173]：/predict/persianchart 按 dirZone 解释目标时刻（空则本命时区）——dirZone 必须透传，
        # 不能再剥（旧实现剥掉 = 撤销上游「按所选时区」修正）。
        for key in ("rateKey", "direction", "nodeRetrograde", "dirZone"):
            if payload.get(key) is None:
                remote.pop(key, None)
        return self._call_remote("/predict/persianchart", remote)

    # 恒星派入境（solunar）盘型表：逐字取自上游 divination/mundane/solunar.js 的 SOLUNAR_TYPES。
    _SOLUNAR_TYPES = {
        "capsolar": {"body": "sun", "target": 270.0, "approx": "01-14"},
        "arisolar": {"body": "sun", "target": 0.0, "approx": "04-14"},
        "cansolar": {"body": "sun", "target": 90.0, "approx": "07-16"},
        "libsolar": {"body": "sun", "target": 180.0, "approx": "10-17"},
        "caplunar": {"body": "moon", "target": 270.0, "approx": None},
        "arilunar": {"body": "moon", "target": 0.0, "approx": None},
        "canlunar": {"body": "moon", "target": 90.0, "approx": None},
        "liblunar": {"body": "moon", "target": 180.0, "approx": None},
    }
    _SOLUNAR_MEAN_SPEED = {"sun": 0.9856, "moon": 13.1764}  # °/日，同上游 MEAN_SPEED

    def _solve_sidereal_ingress(
        self, type_key: str, year: str, payload: dict[str, Any], *, ayanamsa: str = "fagan_bradley"
    ) -> tuple[str, dict[str, Any]] | None:
        """迭代 /chart 求某体入某恒星黄道度的时刻（上游 solveSiderealIngress 的 Python 端口）。

        🔴 上游 solunar.js:150-157 明确警告的陷阱，这里逐条照搬：
        - **首步的带符号最短弧**只在「近种子」时才允许取负。太阳有 approx（±2 日内）算近种子；
          月盘无 approx、种子固定 1/1 属**远种子**，月速 13°/日、距目标常 >180°，首步若允许取负
          会有约半数年份收敛到上一年 12 月的回归。故远种子首步只许向前，其后各步已贴近真根，
          恢复双向微调。
        - 收敛判据 |diff| < 0.002°（约 7″；太阳约 3 分钟）。
        - 迭代上限：太阳 4 次、月 6 次。
        """
        spec = self._SOLUNAR_TYPES.get(type_key)
        if not spec:
            return None
        body = spec["body"]
        speed = self._SOLUNAR_MEAN_SPEED[body]
        moment = f"{year}-{spec['approx']} 12:00:00" if spec["approx"] else f"{year}-01-01 12:00:00"
        near_seed = spec["approx"] is not None
        chart: dict[str, Any] = {}
        for step in range(4 if body == "sun" else 6):
            chart = self._call_remote(
                "/chart",
                {
                    "date": moment.split(" ")[0].replace("-", "/"),
                    "time": moment.split(" ")[1],
                    "zone": payload.get("zone") or "+08:00",
                    "lat": payload.get("lat") or "31n13",
                    "lon": payload.get("lon") or "121e28",
                    "gpsLat": payload.get("gpsLat"),
                    "gpsLon": payload.get("gpsLon"),
                    "ad": payload.get("ad", 1),
                    "zodiacal": 1,
                    "siderealAyanamsa": ayanamsa,
                    "hsys": 10,
                    "tradition": 0,
                    "predictive": 0,
                },
            )
            lon = _solunar_body_lon(chart, body)
            if lon is None:
                return None
            diff = (spec["target"] - lon) % 360.0  # 前向弧（入境=向前到达目标）
            if diff > 180.0 and (near_seed or step > 0):
                diff -= 360.0
            if abs(diff) < 0.002:
                break
            moment = _shift_moment(moment, diff / speed)
        return moment, chart

    # 年之九主：九职的入境目标度与种子日，逐字取自上游 vedicMundane.js 的 EVENT_TARGET / APPROX_DAY。
    _NAVANAYAKA_EVENTS = {
        "ingress_0": (0.0, "04-14"),
        "ingress_60": (60.0, "06-15"),
        "ingress_90": (90.0, "07-16"),
        "ingress_120": (120.0, "08-17"),
        "ingress_180": (180.0, "10-17"),
        "ingress_240": (240.0, "12-16"),
        "ingress_270": (270.0, "01-14"),
        "ingress_ardra": (66 + 40 / 60, "06-22"),
    }
    # 九职表（key / 中文 / 事件 / 年偏移 / 管辖），同上游 NAVANAYAKA_OFFICES。
    _NAVANAYAKA_OFFICES = [
        ("raja", "王", "lunar_new_year", 0, "全年总基调、统治者、国运"),
        ("mantri", "相", "ingress_0", 0, "行政、内阁、治理"),
        ("senadhipati", "军帅", "ingress_120", 0, "国防、军队、治安"),
        ("sasyadhipati", "田主", "ingress_90", 0, "田间庄稼、收成"),
        ("dhanyadhipati", "谷主", "ingress_240", 0, "谷物、存粮"),
        ("arghadhipati", "价主", "ingress_60", 0, "物价、生活成本"),
        ("meghadhipati", "云主", "ingress_ardra", 0, "云、降雨"),
        ("rasadhipati", "汁主", "ingress_180", 0, "油、糖、盐、汁液类"),
        # 🔴 yearOffset=1：吠陀太阳年自梅沙入境起，摩羯入境(01-14)落在**次一公历年**才属同一
        # samvatsara；与其余八职同传 year 会取到梅沙年首之前 3 个月的那次，归属上一年度（上游原注）。
        ("nirasadhipati", "干主", "ingress_270", 1, "金属、宝石、矿、干货"),
    ]

    def _solve_vedic_ingress(self, event_key: str, year: int, payload: dict[str, Any]) -> str | None:
        """太阳入某恒星黄道度（Lahiri）的时刻（上游 solveVedicSolarIngress 的 Python 端口）。

        与恒星派那支的关键差异：**首步也须取最短带符号弧**（上游 :60-62 明确写了「曾加 i>0 守卫 →
        种子晚于真实入境时 diff≈360⁻ 被当成向前一整年，收敛到次年的入境盘」）。九职的种子都是
        approx 近似日，属近种子，故无远种子那条限制。
        """
        spec = self._NAVANAYAKA_EVENTS.get(event_key)
        if not spec:
            return None
        target, approx = spec
        moment = f"{year}-{approx} 12:00:00"
        for _ in range(4):
            chart = self._call_remote(
                "/chart",
                {
                    "date": moment.split(" ")[0].replace("-", "/"),
                    "time": moment.split(" ")[1],
                    "zone": payload.get("zone") or "+08:00",
                    "lat": payload.get("lat") or "31n13",
                    "lon": payload.get("lon") or "121e28",
                    "gpsLat": payload.get("gpsLat"),
                    "gpsLon": payload.get("gpsLon"),
                    "ad": payload.get("ad", 1),
                    "zodiacal": 1,
                    "siderealAyanamsa": "lahiri",
                    "hsys": 0,
                    "tradition": 0,
                    "predictive": 0,
                },
            )
            lon = _solunar_body_lon(chart, "sun")
            if lon is None:
                return None
            diff = (target - lon) % 360.0
            if diff > 180.0:
                diff -= 360.0  # 首步也取最短带符号弧 —— 见 docstring
            if abs(diff) < 0.002:
                return moment
            moment = _shift_moment(moment, diff / 0.98565)
        return moment

    def _build_navanayaka_section(self, year: int, mesha_moment: str, payload: dict[str, Any]) -> str:
        """[年之九主]：九职各由一次恒星入境求根定时刻，再按该日的 vāra（星期主）定职星。

        「王」职是唯一例外：上游取梅沙入境前 35 日窗内**最近一次新月**，走
        `fetchMundaneEvents({kinds:['lunations']})`。本仓改用语义等价且**已在白名单**的
        `/astroextra/prenatal_syzygy`（「某时刻之前最近一次朔」正是它），避免为一职新放行端点。
        任一职求根失败留空（同上游「王位留空,UI 提示」的降级）。
        """
        try:
            js_v = self.js_client.run("mundane_navanayaka", {"offices": self._solve_navanayaka(year, mesha_moment, payload)})
            return f"{(js_v or {}).get('text') or ''}".strip()
        except Exception as exc:  # noqa: BLE001
            _degrade("navanayaka build failed: %s", exc)
            return ""

    def _solve_navanayaka(self, year: int, mesha_moment: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        offices: list[dict[str, Any]] = []
        for key, cn, event, offset, domain in self._NAVANAYAKA_OFFICES:
            moment = None
            if event == "lunar_new_year":
                moment = self._last_new_moon_before(mesha_moment, payload)
            else:
                try:
                    moment = self._solve_vedic_ingress(event, year + offset, payload)
                except Exception as exc:  # noqa: BLE001 — 单职失败只留空
                    _degrade("navanayaka office %s failed: %s", key, exc)
            offices.append({"key": key, "cn": cn, "domain": domain, "moment": moment})
        return offices

    def _last_new_moon_before(self, moment: str, payload: dict[str, Any]) -> str | None:
        """梅沙入境前最近一次朔。/astroextra/prenatal_syzygy 的语义即「此前最近一次朔望」。"""
        try:
            date_part = moment.split(" ")[0]
            rsp = self._call_remote(
                "/astroextra/prenatal_syzygy",
                {
                    "date": date_part.replace("-", "/"),
                    "time": moment.split(" ")[1] if " " in moment else "12:00:00",
                    "zone": payload.get("zone") or "+08:00",
                    "lat": payload.get("lat") or "31n13",
                    "lon": payload.get("lon") or "121e28",
                    "gpsLat": payload.get("gpsLat"),
                    "gpsLon": payload.get("gpsLon"),
                    "ad": payload.get("ad", 1),
                },
            )
            if isinstance(rsp, dict):
                for field in ("date", "localTime", "moment", "time"):
                    value = rsp.get(field)
                    if isinstance(value, str) and len(value) >= 10:
                        return value
        except Exception as exc:  # noqa: BLE001 — 王位留空
            _degrade("navanayaka raja syzygy failed: %s", exc)
        return None

    # 世运口径（上游页面设置 MUNDANE_PAGE_SETTINGS，MundaneMain.js:519-526 + 吠陀世运输入 :1330-1340）：进每张卡的 extra
    # （buildMundaneCardSections 读 ex.mundaneRuleset / mundaneOrbScheme / mundaneIngressRule / vedic*），规则集行进快照头。
    _MUNDANE_SETTING_KEYS = (
        "mundaneRuleset", "mundaneOrbScheme", "mundaneIngressRule", "vedicDashaYearLen", "vedicFoundingYear", "vedicNatalAsc",
    )
    # 世运专属输入：不进 /chart 请求体（其余键 = 页面 fields：黄道/岁差/宫制/古典全局键，与 astro 盘同一套）。
    _MUNDANE_ONLY_KEYS = frozenset({
        "year", "ingressTerm", "mundaneType", "mhKind", "solunarType", "solunarWeights", "solunarOrb", "vedicYear",
        *_MUNDANE_SETTING_KEYS,
    })

    def _mundane_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        """世运口径键（有值才收）；给了任一键就先让 JS 按引擎自带表校验值域（认不出的报错，不静默当缺省）。"""
        settings = {k: payload[k] for k in self._MUNDANE_SETTING_KEYS if payload.get(k) not in (None, "")}
        if "vedicDashaYearLen" in settings:
            try:
                settings["vedicDashaYearLen"] = float(settings["vedicDashaYearLen"])
            except (TypeError, ValueError):
                pass
            if settings.get("vedicDashaYearLen") == 360.0:
                settings["vedicDashaYearLen"] = 360
        if "vedicFoundingYear" in settings:
            try:
                settings["vedicFoundingYear"] = int(f"{settings['vedicFoundingYear']}".strip())
            except ValueError:
                raise ToolValidationError(
                    bilingual(f"世运 vedicFoundingYear（建国年）须为整数：{settings['vedicFoundingYear']!r}",
                              f"mundane vedicFoundingYear must be an integer: {settings['vedicFoundingYear']!r}"),
                    code="tool.mundane_invalid_setting",
                    details={"invalid": [{"key": "vedicFoundingYear", "value": settings["vedicFoundingYear"], "allowed": "int"}]},
                ) from None
        if "vedicNatalAsc" in settings:
            settings["vedicNatalAsc"] = f"{settings['vedicNatalAsc']}".strip().lower()
        if not settings:
            return settings
        js = self.js_client.run("mundane_cards", {"action": "settings", "settings": settings})
        data = js.get("data") if isinstance(js, dict) else None
        invalid = data.get("invalid") if isinstance(data, dict) else None
        if invalid:
            parts = [f"{i.get('key')}={i.get('value')!r}（可选：{'/'.join(str(a) for a in (i.get('allowed') or []))}）" for i in invalid if isinstance(i, dict)]
            raise ToolValidationError(
                bilingual(f"世运盘设置取值无效：{'；'.join(parts)}。", f"mundane setting(s) invalid: {'; '.join(parts)}."),
                code="tool.mundane_invalid_setting",
                details={"invalid": invalid},
            )
        return settings

    def _run_mundane_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 世俗入宫盘 (mundane ingress): (1) get the precise solar-term ingress moment for the year via
        # /jieqi/year, (2) cast a /chart at that moment, (3) enrich with the v2.4.0 natal extras, then
        # (4) prepend a [世俗入宫] section to the astrochart snapshot. Mirrors 星阙 MundaneMain.
        year = f"{payload.get('year', '')}".strip()
        term = f"{payload.get('ingressTerm') or '春分'}".strip()
        zone = payload.get("zone") or "+08:00"
        lon = payload.get("lon")
        lat = payload.get("lat")
        settings = self._mundane_settings(payload)
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
        # 入宫盘 = 页面 fields（黄道/岁差/古典全局键随盘，上游 DivinationChartShell 与 astro 盘同一套构参）+ 入宫时刻。
        chart_payload = {
            **{k: v for k, v in payload.items() if k not in self._MUNDANE_ONLY_KEYS and v is not None},
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
        chart_response = self._attach_natal_extras("mundane", chart_response, payload)

        # 世运卜卦（mundaneType='mundanehorary'）：上游对该盘型走的是「问事时刻的普通 /chart →
        # buildFacts → describeXQuestion」，机制同卜卦、问主=公众/国家、宫义按世运读。这里复用
        # 已经算好的入宫盘作为问事盘面（headless 无「问事时刻」这个交互输入，故以本盘为准），
        # 由 vendored 的三个纯函数出 [世运卜卦]/[世运问判] 两段。失败只是这两段不出。
        # 恒星派入境（solunar）：入境时刻由 Python 迭代 /chart 求根（上游那支走 HTTP，按 §5 归 Python），
        # 段文本由 vendored 的 describeSolunar / computeAngularity / rulerDeathSignature 纯函数出。
        mundane_type = f"{payload.get('mundaneType') or ''}".strip()
        if mundane_type not in self._MUNDANE_SUPPORTED_TYPES:
            # 上游 MUNDANE_TYPES 另有 region（地区盘：须从 regionCharts 预置/自定义里**选**一张建置盘，
            # headless 无此输入）。认不出的盘型不许静默当入宫盘——说出来。
            _degrade(
                "mundane: 不支持的盘型 mundaneType=%s（支持 %s），按入宫盘出段",
                mundane_type,
                "/".join(sorted(t for t in self._MUNDANE_SUPPORTED_TYPES if t)),
            )
        # 盘型专属卡要在该盘型自己的盘上算（上游页面盘 = 该盘型的盘）：求根得到的 (时刻, 盘) 记在这里。
        type_chart_ctx: dict[str, tuple[str, dict[str, Any]]] = {}
        solunar_text = ""
        if mundane_type == "solunar":
            try:
                solved = self._solve_sidereal_ingress(
                    f"{payload.get('solunarType') or 'capsolar'}", year, payload
                )
                if solved:
                    moment, solunar_chart = solved
                    type_chart_ctx["solunar"] = (moment, solunar_chart)
                    js_s = self.js_client.run(
                        "mundane_solunar",
                        {
                            "chart": solunar_chart,
                            "solunarType": payload.get("solunarType") or "capsolar",
                            "solunarWeights": payload.get("solunarWeights") or "scheme_a",
                            "solunarOrb": payload.get("solunarOrb") or 3,
                            "moment": moment,
                        },
                    )
                    solunar_text = f"{(js_s or {}).get('text') or ''}".strip()
                else:
                    # 求根器回 None（盘型键不认识 / 盘里取不到日月黄经）：盘型段与 [恒星派入境·概览] 都不会出，说出来。
                    _degrade("mundane solunar ingress unsolved (solunarType=%s)", payload.get("solunarType") or "capsolar")
            except Exception as exc:  # noqa: BLE001 — 求根/富化失败不许带崩入宫盘
                _degrade("mundane solunar build failed: %s", exc)
        # 吠陀世运（vedicmundane）：恒星黄道 Lahiri 的梅沙（白羊）入境盘。
        # 上游 castVedicIngress（MundaneMain.js:1282）用 vedicMundane.solveVedicSolarIngress('ingress_0') 求根，
        # 再把页面盘改成 恒星黄道 Lahiri · hsys 0 · tradition 0 在该时刻起盘；[吠陀世运·年度盘]/[世运大运]/
        # [KP 副主链] 读的正是这张盘，st.vedicMoment = 求根时刻。求根走同一个忠实端口 _solve_vedic_ingress
        # （九主各职也用它）——此前这里借用恒星派的 _solve_sidereal_ingress（步速 0.9856、首步规则不同），
        # 收敛点可差到分钟级，会让盘头与卡片印出两个不同的「入境时刻」。
        vedic_text = ""
        if mundane_type == "vedicmundane":
            try:
                vedic_year = f"{payload.get('vedicYear') or year}".strip()
                v_moment = self._solve_vedic_ingress("ingress_0", int(vedic_year), payload)
                if v_moment:
                    v_chart = self._call_remote("/chart", self._vedic_chart_payload(v_moment, payload))
                    type_chart_ctx["vedicmundane"] = (v_moment, v_chart)
                    vedic_text = "\n".join(
                        [
                            "[吠陀世运]",
                            f"年份：{vedic_year}",
                            "体系：恒星黄道 Lahiri · 梅沙入境为年度主盘",
                            f"梅沙入境时刻：{v_moment}",
                        ]
                    )
                    nav = self._build_navanayaka_section(int(vedic_year), v_moment, payload)
                    if nav:
                        vedic_text = f"{vedic_text}\n\n{nav}"
                else:
                    _degrade("mundane vedic mesha ingress unsolved (year=%s)", vedic_year)
            except Exception as exc:  # noqa: BLE001
                _degrade("mundane vedic ingress failed: %s", exc)
        horary_text = ""
        if mundane_type == "mundanehorary":
            try:
                js = self.js_client.run(
                    "mundane_horary",
                    {"chart": chart_response, "mhKind": payload.get("mhKind") or "war"},
                )
                horary_text = f"{(js or {}).get('text') or ''}".strip()
            except Exception as exc:  # noqa: BLE001 — 富化失败不许带崩入宫盘
                _degrade("mundane horary build failed: %s", exc)
        # 子盘群：新月/满月/日月食/地区盘/行星周期 + 世俗宫义/定局·年主·盘主/入境骨架/地理分野/地区盘推运。
        # collected 顺手收下子盘群已经取到的物料（朔望子盘、四季入境时刻），卡片段复用，不重复请求。
        collected: dict[str, Any] = {}
        subchart_sections = self._build_mundane_subchart_sections(
            base_chart_payload=chart_payload,
            seed_payload=seed_payload,
            ingress_response=chart_response,
            ingress_time=ingress_time,
            year=year,
            zone=zone,
            collect=collected,
        )
        subcharts_text = _render_snapshot_text(subchart_sections) if subchart_sections else ""
        # 右栏卡片段（上游 v3.11 [Q-444/T-407]）：上游 buildAiSnapshot 的拼接序是
        # head / 判词 / 分析段 / **cardSecs** / 盘面正文（MundaneMain.js:2992-2995），卡片段紧贴正文之前。
        cards_meta: dict[str, Any] = {}
        cards_text = self._build_mundane_card_text(
            payload=payload,
            mundane_type=mundane_type,
            year=year,
            term=term,
            ingress_time=ingress_time,
            zone=zone,
            chart_payload=chart_payload,
            chart_response=chart_response,
            collected=collected,
            type_chart_ctx=type_chart_ctx,
            settings=settings,
            meta_out=cards_meta,
        )
        # 快照头（上游 buildAiSnapshot MundaneMain.js:2852-2860）：盘名 / 规则集 / 入宫节气 / 年份 / 页面级覆盖行；
        # 「入宫时刻」是本仓底盘恒为入宫盘的补注。日/月食盘型的「受冲容许度」覆盖行（:2863-2867）同附头内。
        head_lines = ["[世俗入宫]"]
        if cards_meta.get("rulesetLabel"):
            head_lines.append(f"规则集：{cards_meta['rulesetLabel']}")
        head_lines += [f"入宫节气：{term}", f"年份：{year or '-'}"]
        if cards_meta.get("ingressRuleLabel"):
            head_lines.append(f"入境主管制：{cards_meta['ingressRuleLabel']}（页面级覆盖）")
        head_lines.append(f"入宫时刻：{ingress_time}")
        if mundane_type in ("solecl", "lunecl") and cards_meta.get("orbSchemeLabel"):
            head_lines.append(f"受冲容许度：{cards_meta['orbSchemeLabel']}（页面级覆盖）")
        head = "\n".join(head_lines)
        body = _build_astro_snapshot_text(chart_payload, chart_response)
        snapshot_text = "\n\n".join(
            part for part in (head, solunar_text, vedic_text, horary_text, subcharts_text, cards_text, body) if part
        ).strip()
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
        collect: dict[str, Any] | None = None,
    ) -> list[tuple[str, str]]:
        # 每个子盘独立 try/except：任一端点失败只降级该段为说明文本，绝不破坏世俗盘主流程。
        # collect（可选）：把已取到的朔望子盘 {'syzygy': {'new'|'full': {'moment', 'chart'}}} 与四季入境时刻
        # {'season': {节气: 时刻}} 交还调用方，供右栏卡片段复用（不为同一份物料再打一遍后端）。
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
            _degrade("mundane prenatal_syzygy failed: %s", exc)
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
                if collect is not None and isinstance(sub_chart, dict):
                    collect.setdefault("syzygy", {})[syz_type] = {"moment": moment, "chart": sub_chart}
                digest = _mundane_chart_digest(sub_chart)
                if digest:
                    lines.append("子盘四轴/日月：" + "；".join(digest))
            except Exception as exc:  # noqa: BLE001
                _degrade("mundane %s chart failed: %s", title, exc)
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
                _degrade("mundane eclipsedetail(%s) failed: %s", kind, exc)
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
            _degrade("mundane world chart failed: %s", exc)
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
                _degrade("mundane greatconj failed: %s", exc)
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
                _degrade("mundane barbault failed: %s", exc)
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
                if collect is not None and by_term:
                    collect["season"] = {t: by_term[t] for t in want if t in by_term}
        except Exception as exc:  # noqa: BLE001
            _degrade("mundane seasonal ingress failed: %s", exc)
        prog_body = ["年度四季入宫定盘序列（地区盘随每季太阳入基本宫逐季推移）："]
        prog_body.extend(prog_rows or ["未能取得四季入宫时刻。"])
        sections.append(("地区盘推运", "\n".join(prog_body)))

        return sections

    # ── 世运右栏卡片段（上游 v3.11 [Q-444/T-407]）─────────────────────────────────────────────
    # 产段函数 = 上游 components/mundane/MundaneMain.js:232 `buildMundaneCardSections(chart, extra, state, facts)`，
    # vendored 逐字（horosa-core-js/src/vendor/mundane/MundaneMain.js，manifest truncate_before 剥 UI 尾部），
    # 经 JS 工具 `mundane_cards` 调用。上游页面的「按需拉取物」在 React state 里；这里由 Python 取数后原样喂入
    # （请求型编排归 Python，AGENTS §5）。无数据即不成段，与上游「算过才成段」同形。
    #
    # 支持的盘型（上游 MUNDANE_TYPES，MundaneMain.js:43）。region（地区盘）不在内：它要从 regionCharts
    # 预置/自定义里**选**一张建置盘（UI 选择），headless 无此输入。
    _MUNDANE_SUPPORTED_TYPES = frozenset(
        {"", "ingress", "newmoon", "fullmoon", "solecl", "lunecl", "cycles", "solunar", "vedicmundane", "mundanehorary"}
    )
    # 盘型专属卡（上游按 extra.mundaneType 分支产出，行号为 MundaneMain.js）。其余「本命式」卡
    # （天气占星/四轴特殊点/会合指示星/盘型格局/世运恒星命中/赤纬平行）对任何非 cycles 盘型都会产——
    # skill 的世俗盘恒以入宫盘为底（正文段即入宫盘），故本命式卡只取入宫底盘那一轮；盘型轮只保留本表的
    # 专属卡，免得同名段在一份快照里出现两次、且归属到错的盘。天气与农业（:457）需页面手填的「受孕日」
    # st.garbhaDate，headless 无来源 → 永不产，仍留在表里以便将来有输入时自动放行。
    _MUNDANE_TYPE_CARDS: dict[str, tuple[str, ...]] = {
        "newmoon": ("新月图判读",),  # :269
        "fullmoon": ("满月图判读",),  # :269
        "solecl": ("日食图判读", "食族 Saros", "天象占参考"),  # :278-310
        "lunecl": ("月食图判读", "食族 Saros", "天象占参考"),  # :278-310
        "solunar": ("恒星派入境·概览",),  # :428
        "vedicmundane": ("吠陀世运·年度盘", "世运大运", "KP 副主链", "天气与农业"),  # :435-458
        "mundanehorary": ("世运问判·得力明细",),  # :460
        "cycles": ("木土纪元", "大年时代", "Barbault 聚散指数"),  # :471-502
    }
    # 行星周期卡的页面物料（type==='cycles'）：
    #   木土会合表 = 页面挂载即自动算的 computeGreatConj（:576 componentDidMount → :753），state 缺省
    #   gcStart 1300 / gcEnd 2200 / gcPair 'jupiter-saturn' / gcAspect 0（:554），木土合相走 /astroextra/greatconj、
    #   gcMode 置 'ages'（:769）。builder 自己的显示回落 clampYear(st.gcStart, 1300)（:476）与之同值。
    #   Barbault 指数 = 「绘制」按钮 computeBarbault（:787）：缺省 bbStart 1900 / bbEnd 2050 / bbSet 'slow5'（:557），
    #   行星取 BARBAULT_SETS[0]（:101，五慢星），stepMonths = 跨度>160 年 12、>80 年 6、否则 3（:793）。
    _MUNDANE_GC_DEFAULT_STATE = {"gcStart": 1300, "gcEnd": 2200, "gcPair": "jupiter-saturn", "gcAspect": 0, "gcMode": "ages"}
    _MUNDANE_BB_DEFAULT_STATE = {"bbStart": 1900, "bbEnd": 2050, "bbSet": "slow5"}
    _MUNDANE_BB_DEFAULT_PLANETS = ("Jupiter", "Saturn", "Uranus", "Neptune", "Pluto")

    @staticmethod
    def _vedic_chart_payload(moment: str, payload: dict[str, Any]) -> dict[str, Any]:
        """梅沙入境盘：上游 castVedicIngress 把页面盘改成 zodiacal 1 · lahiri · hsys 0 · tradition 0（:1290）。"""
        date_part, _, time_part = moment.partition(" ")
        return {
            "date": date_part.replace("-", "/"),
            "time": time_part or "12:00:00",
            "zone": payload.get("zone") or "+08:00",
            "lat": payload.get("lat") or "31n13",
            "lon": payload.get("lon") or "121e28",
            "gpsLat": payload.get("gpsLat"),
            "gpsLon": payload.get("gpsLon"),
            "ad": payload.get("ad", 1),
            "zodiacal": 1,
            "siderealAyanamsa": "lahiri",
            "hsys": 0,
            "tradition": 0,
            "predictive": 0,
        }

    def _build_mundane_card_text(
        self,
        *,
        payload: dict[str, Any],
        mundane_type: str,
        year: str,
        term: str,
        ingress_time: str,
        zone: str,
        chart_payload: dict[str, Any],
        chart_response: dict[str, Any],
        collected: dict[str, Any],
        type_chart_ctx: dict[str, tuple[str, dict[str, Any]]],
        settings: dict[str, Any] | None = None,
        meta_out: dict[str, Any] | None = None,
    ) -> str:
        try:
            year_num: int | None = int(str(year).strip())
        except (TypeError, ValueError):
            year_num = None
        # ── 入宫底盘一轮：上游 castIngress 落的 extra 就是这四键（:629）。
        base_state: dict[str, Any] = {}
        season = collected.get("season")
        if isinstance(season, dict) and season and year_num is not None:
            # 上游「起四季盘」按钮（:638 scanSeasonalIngresses）= fetchPreciseJieqiSeed 四枢轴 → {节气: {time…}}；
            # skill 的 [地区盘推运] 已为同一年取过这四个时刻（同一 /jieqi/year seedOnly 请求），直接复用。
            base_state["seasonSeed"] = {t: {"term": t, "time": v} for t, v in season.items()}
            base_state["seasonSeedYear"] = year_num
        patterns = self._mundane_pattern_data(chart_payload)
        if patterns is not None:
            base_state["patData"] = patterns
        jobs: list[dict[str, Any]] = [
            {
                "id": "ingress",
                "chart": chart_response,
                "extra": {"mundaneType": "ingress", "ingressTerm": term, "ingressYear": year_num, "ingressMoment": ingress_time},
                "state": base_state,
            }
        ]
        type_job = self._mundane_type_card_job(
            mundane_type=mundane_type,
            payload=payload,
            ingress_time=ingress_time,
            zone=zone,
            chart_payload=chart_payload,
            chart_response=chart_response,
            collected=collected,
            type_chart_ctx=type_chart_ctx,
        )
        if type_job is not None:
            jobs.append(type_job)
        # 世运口径随每张卡的 extra（上游页面 extra 是各盘型共享的一份；buildMundaneCardSections 按键读）。
        for job in jobs:
            job["extra"] = {**(settings or {}), **(job.get("extra") or {})}
        try:
            js = self.js_client.run("mundane_cards", {"jobs": jobs, "settings": settings or {}})
        except Exception as exc:  # noqa: BLE001 — 卡片段失败不许带崩世俗盘主流程，但必须说出来
            _degrade("mundane card sections failed: %s", exc)
            return ""
        data = js.get("data") if isinstance(js, dict) else None
        if meta_out is not None and isinstance(data, dict) and isinstance(data.get("meta"), dict):
            meta_out.update(data["meta"])
        results = data.get("jobs") if isinstance(data, dict) else None
        if not isinstance(results, list):
            _degrade("mundane card sections: JS 工具返回形状异常（缺 data.jobs）")
            return ""
        blocks: list[str] = []
        for res in results:
            if not isinstance(res, dict):
                continue
            job_id = f"{res.get('id') or ''}"
            if not res.get("ok"):
                err = res.get("error") if isinstance(res.get("error"), dict) else {}
                _degrade("mundane card job %s failed: %s", job_id, err.get("message") or err.get("code") or "unknown")
                continue
            keep = None if job_id == "ingress" else set(self._MUNDANE_TYPE_CARDS.get(job_id, ()))
            for card in res.get("cards") or []:
                if not isinstance(card, dict):
                    continue
                if keep is not None and card.get("title") not in keep:
                    continue
                text = f"{card.get('text') or ''}".strip()
                if text:
                    blocks.append(text)
        return "\n\n".join(blocks)

    def _mundane_pattern_data(self, chart_payload: dict[str, Any]) -> list[Any] | None:
        """[盘型格局] 的「相位格局」行：上游「查格局」按钮（MundaneMain.js:825 computeMundanePatterns）以
        chartParams(chart) 打 /astroextra/analysis、取 `patterns`（后端 detect_patterns）。

        请求体照 AstroExtraCommon.chartParams 的键：盘面时刻/地点/宫制/黄道 + tradition=false·predictive=false。
        失败返回 None（该几行不出）并记降级——**不**像上游那样把错误信封读成「本盘无显著相位格局」。
        """
        body = {
            "date": chart_payload.get("date"),
            "time": chart_payload.get("time"),
            "ad": chart_payload.get("ad", 1),
            "zone": chart_payload.get("zone"),
            "lat": chart_payload.get("lat"),
            "lon": chart_payload.get("lon"),
            "hsys": chart_payload.get("hsys", 0),
            "zodiacal": chart_payload.get("zodiacal", 0),
            "siderealAyanamsa": chart_payload.get("siderealAyanamsa") or "",
            "tradition": False,
            "predictive": False,
        }
        try:
            rsp = self._call_remote("/astroextra/analysis", body)
        except Exception as exc:  # noqa: BLE001
            _degrade("mundane aspect patterns (/astroextra/analysis) failed: %s", exc)
            return None
        if not isinstance(rsp, dict):
            _degrade("mundane aspect patterns: /astroextra/analysis 返回非对象")
            return None
        pats = rsp.get("patterns")
        # 上游：`(r && r.patterns) ? r.patterns : []` —— 成功但无格局 = 空表（卡内写「本盘无显著相位格局」）。
        return pats if isinstance(pats, list) else []

    def _mundane_type_card_job(
        self,
        *,
        mundane_type: str,
        payload: dict[str, Any],
        ingress_time: str,
        zone: str,
        chart_payload: dict[str, Any],
        chart_response: dict[str, Any],
        collected: dict[str, Any],
        type_chart_ctx: dict[str, tuple[str, dict[str, Any]]],
    ) -> dict[str, Any] | None:
        if mundane_type in ("newmoon", "fullmoon"):
            # 上游 useMoment（:688）：选中的朔/望行 → extra.selectedMoment = 该行 localTime，页面盘改排到该时刻。
            # skill 的新月/满月子盘 = 入宫前最近一次朔/望（[新月图]/[满月图] 段同一张盘）。
            syz = (collected.get("syzygy") or {}).get("new" if mundane_type == "newmoon" else "full")
            if not isinstance(syz, dict) or not isinstance(syz.get("chart"), dict):
                _degrade("mundane %s card: 未取得朔望子盘", mundane_type)
                return None
            return {
                "id": mundane_type,
                "chart": syz["chart"],
                "extra": {"mundaneType": mundane_type, "selectedMoment": syz.get("moment")},
                "state": {},
            }
        if mundane_type in ("solecl", "lunecl"):
            return self._mundane_eclipse_job(mundane_type, chart_payload=chart_payload, ingress_time=ingress_time, zone=zone)
        if mundane_type == "solunar":
            ctx = type_chart_ctx.get("solunar")
            if not ctx:
                return None  # 求根失败已在求根处记过降级
            return {
                "id": "solunar",
                "chart": ctx[1],
                "extra": {
                    "mundaneType": "solunar",
                    "solunarType": payload.get("solunarType"),
                    "solunarWeights": payload.get("solunarWeights"),
                    "solunarOrb": payload.get("solunarOrb"),
                },
                "state": {},
            }
        if mundane_type == "vedicmundane":
            ctx = type_chart_ctx.get("vedicmundane")
            if not ctx:
                return None
            try:
                vedic_year: int | None = int(f"{payload.get('vedicYear') or payload.get('year')}".strip())
            except (TypeError, ValueError):
                vedic_year = None
            return {
                "id": "vedicmundane",
                "chart": ctx[1],
                "extra": {"mundaneType": "vedicmundane", "vedicYear": vedic_year},
                "state": {"vedicMoment": ctx[0]},
            }
        if mundane_type == "mundanehorary":
            # 问事盘 = 入宫盘（同 [世运卜卦]/[世运问判] 的既有口径：headless 无「问事时刻」这个交互输入）。
            return {
                "id": "mundanehorary",
                "chart": chart_response,
                "extra": {"mundaneType": "mundanehorary", "mhKind": payload.get("mhKind") or "war"},
                "state": {},
            }
        if mundane_type == "cycles":
            return {
                "id": "cycles",
                "chart": chart_response,  # cycles 分支不读盘面（isNatalLike=false），builder 只要求 chart 非空
                "extra": {"mundaneType": "cycles"},
                "state": self._mundane_cycles_state(),
            }
        return None

    def _mundane_cycles_state(self) -> dict[str, Any]:
        state: dict[str, Any] = {}
        try:
            gc = self._call_remote(
                "/astroextra/greatconj",
                {"startYear": self._MUNDANE_GC_DEFAULT_STATE["gcStart"], "endYear": self._MUNDANE_GC_DEFAULT_STATE["gcEnd"]},
            )
            # 上游 :768：`(r && r.conjunctions) ? r.conjunctions : (Array.isArray(r) ? r : [])`。
            conjs = gc.get("conjunctions") if isinstance(gc, dict) else (gc if isinstance(gc, list) else None)
            state.update(self._MUNDANE_GC_DEFAULT_STATE)
            state["gcResults"] = conjs if isinstance(conjs, list) else []
        except Exception as exc:  # noqa: BLE001
            _degrade("mundane cycles greatconj failed: %s", exc)
        start, end = self._MUNDANE_BB_DEFAULT_STATE["bbStart"], self._MUNDANE_BB_DEFAULT_STATE["bbEnd"]
        span = end - start
        step_months = 12 if span > 160 else (6 if span > 80 else 3)
        try:
            bb = self._call_remote(
                "/astroextra/barbault",
                {"startYear": start, "endYear": end, "stepMonths": step_months, "planets": list(self._MUNDANE_BB_DEFAULT_PLANETS)},
            )
            # 上游 :801：`bbData: (r && r.points) ? r : null`。
            if isinstance(bb, dict) and bb.get("points"):
                state.update(self._MUNDANE_BB_DEFAULT_STATE)
                state["bbData"] = bb
            else:
                _degrade("mundane cycles barbault: 响应无 points")
        except Exception as exc:  # noqa: BLE001
            _degrade("mundane cycles barbault failed: %s", exc)
        return state

    def _mundane_eclipse_job(
        self, mundane_type: str, *, chart_payload: dict[str, Any], ingress_time: str, zone: str
    ) -> dict[str, Any] | None:
        """日/月食判读卡的食盘。

        上游（MundaneMain.js:669 scanEvents → :688 useMoment）：/astroextra/ephemeris 扫出食表，用户点选一行 →
        extra.selectedMoment = 该行 localTime、eclipseTypeText = 该行 eclipseType，页面盘改排到食时刻，
        并以该时刻打 /astroextra/eclipsedetail 取食时长（:703 fetchEclipseDetail → state.eclipseDetail）。
        headless 选行口径：与 skill 既有 [日食图]/[月食图] 段同一次食——eclipsedetail 自「入宫时刻 − 2 日」向后
        搜到的第一次（astroextra.compute_eclipse_detail：jd_search = jd − 2），在 ephemeris 食表里取
        localTime ≥ 入宫 − 2 日的第一行。scanYear 取该食所在年（上游 scanYear 即扫出这次食的那一年）。
        """
        kind = "lunar" if mundane_type == "lunecl" else "solar"
        try:
            ingress_dt = datetime.strptime(ingress_time, "%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError):
            _degrade("mundane %s card: 入宫时刻格式异常 %s", mundane_type, ingress_time)
            return None
        floor_dt = ingress_dt - timedelta(days=2)
        end_dt = floor_dt + timedelta(days=400)  # 两个以上食季：日食 ≥2、月食 ≥1
        try:
            eph = self._call_remote(
                "/astroextra/ephemeris",
                {
                    # 请求体照上游 momentPipeline.fetchMundaneEvents（:79）。
                    "date": floor_dt.strftime("%Y-%m-%d"),
                    "time": "00:00:00",
                    "startDate": floor_dt.strftime("%Y-%m-%d"),
                    "endDate": end_dt.strftime("%Y-%m-%d"),
                    "startTime": "00:00:00",
                    "endTime": "23:59:59",
                    "zone": zone,
                    "lat": chart_payload.get("lat") or "0n00",
                    "lon": chart_payload.get("lon") or "0e00",
                    "gpsLat": chart_payload.get("gpsLat") if chart_payload.get("gpsLat") is not None else 0,
                    "gpsLon": chart_payload.get("gpsLon") if chart_payload.get("gpsLon") is not None else 0,
                    "includeTransits": False,
                },
            )
        except Exception as exc:  # noqa: BLE001
            _degrade("mundane %s card: /astroextra/ephemeris failed: %s", mundane_type, exc)
            return None
        rows = eph.get("eclipses") if isinstance(eph, dict) else None
        picked: tuple[str, dict[str, Any]] | None = None
        for ev in rows if isinstance(rows, list) else []:
            if not isinstance(ev, dict):
                continue
            # 上游 fetchMundaneEvents：kind = type==='lunar_eclipse' ? 'lunar' : 'solar'；localTime = datetime || date+time。
            ev_kind = "lunar" if ev.get("type") == "lunar_eclipse" else "solar"
            if ev_kind != kind:
                continue
            local_time = ev.get("datetime") or (f"{ev.get('date')} {ev.get('time')}" if ev.get("date") and ev.get("time") else ev.get("date"))
            try:
                ev_dt = datetime.strptime(f"{local_time}", "%Y-%m-%d %H:%M:%S")
            except (TypeError, ValueError):
                continue
            if ev_dt >= floor_dt:
                picked = (f"{local_time}", ev)
                break
        if picked is None:
            _degrade("mundane %s card: 入宫后 400 日内未检索到%s食", mundane_type, "月" if kind == "lunar" else "日")
            return None
        local_time, ev = picked
        date_part, _, time_part = local_time.partition(" ")
        try:
            chart = self._call_remote("/chart", {**chart_payload, "date": date_part, "time": time_part})
        except Exception as exc:  # noqa: BLE001
            _degrade("mundane %s card: eclipse chart failed: %s", mundane_type, exc)
            return None
        state: dict[str, Any] = {}
        try:
            detail = self._call_remote(
                "/astroextra/eclipsedetail",
                {
                    "date": date_part,
                    "time": time_part or "00:00:00",
                    "zone": zone,
                    "lat": chart_payload.get("lat"),
                    "lon": chart_payload.get("lon"),
                    "eclipseKind": kind,
                },
            )
            # 上游 :710：`eclipseDetail: (r && !r.err) ? r : null`。
            if isinstance(detail, dict) and not detail.get("err"):
                state["eclipseDetail"] = detail
        except Exception as exc:  # noqa: BLE001
            _degrade("mundane %s card: eclipsedetail failed: %s", mundane_type, exc)
        return {
            "id": mundane_type,
            "chart": chart,
            "extra": {
                "mundaneType": mundane_type,
                "selectedMoment": local_time,
                "eclipseKind": kind,
                "eclipseTypeText": ev.get("eclipseType"),
                "scanYear": int(local_time[:4]) if local_time[:4].isdigit() else None,
            },
            "state": state,
        }

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
        # 塔罗：core-js tarot 引擎 SHA-256 种子洗牌 + 解读。种子 = 上游「生辰」种子来源 seedFromFields
        # （TarotMain.js:97-108）：name|date|time|lat|lon 取非空项以 | 相连（全空 → 'horosa-tarot-default'）；
        # 显式 seed 覆盖。此前 skill 用 yyyyMMddHHmm，与上游同一盘抽出不同的牌（sync311 F10）。
        seed = payload.get("seed")
        if seed is None or f"{seed}".strip() == "":
            parts = [f"{payload.get(k)}".strip() for k in ("name", "date", "time", "lat", "lon") if payload.get(k) not in (None, "")]
            seed = "|".join(p for p in parts if p) or "horosa-tarot-default"
        js_payload: dict[str, Any] = {
            "seed": str(seed),
            "question": payload.get("question") or "",
            "deck": payload.get("deck") or "rws",
        }
        # 牌阵缺省交给 JS 按牌组允许表定（rws 等 = three）；给了就原样送，由引擎词表裁决。
        if payload.get("spread"):
            js_payload["spread"] = payload.get("spread")
        # 逆位：缺省随牌组；显式 true/false 都下发（此前只发 false，马赛系等默认无逆位的牌组开不了逆位）。
        if payload.get("usesReversals") is not None:
            js_payload["usesReversals"] = bool(payload.get("usesReversals"))
        for key in ("dignities", "variant", "verdictMode", "birth"):
            if payload.get(key) is not None:
                js_payload[key] = payload.get(key)
        # 其余 19 个引擎判读设置（timingMethod/timingUnit/meaningSystem/reversalMode/…）：键集锚引擎 resolveSettings。
        if isinstance(payload.get("options"), dict):
            js_payload["options"] = payload.get("options")
        try:
            result = self.js_client.run("tarot", js_payload)
        except ToolTransportError as exc:
            _degrade("tarot JS engine failed: %s", exc)
            result = {}
        data = result.get("data") if isinstance(result, dict) and isinstance(result.get("data"), dict) else {}
        if data.get("ok") is False:
            error = data.get("error") if isinstance(data.get("error"), dict) else {}
            code = {
                "unknown_deck": "tool.tarot_unknown_deck",
                "unknown_spread": "tool.tarot_unknown_spread",
                "unsupported_spread_for_deck": "tool.tarot_unsupported_spread_for_deck",
                "invalid_setting": "tool.tarot_invalid_setting",
            }.get(str(error.get("code") or ""))
            if code:
                raise ToolValidationError(
                    bilingual(f"塔罗入参不被引擎接受：{error.get('message')}", f"tarot input rejected by the engine: {error.get('message')}"),
                    code=code,
                    details={**(error.get("details") or {}), "engine_error": error.get("code")},
                )
            _degrade("tarot JS engine produced no reading: %s", error.get("message") or error)
        snapshot_text = result.get("snapshot_text") if isinstance(result, dict) else ""
        ignored = list(data.get("params_ignored") or [])
        out: dict[str, Any] = {
            "deck": (isinstance(result, dict) and result.get("deck")) or js_payload["deck"],
            "spread": (isinstance(result, dict) and result.get("spread")) or js_payload.get("spread"),
            "seed": str(seed),
            "params_applied": list(data.get("params_applied") or []),
            "params_ignored": ignored,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="tarot", snapshot_text=snapshot_text),
        }
        if ignored:
            out["_warnings"] = [f"tarot 未识别的 options 键已忽略：{'、'.join(ignored)}（键集锚引擎 resolveSettings）。"]
        return out

    def _attach_technique_card(
        self, tool_name: str, input_normalized: dict[str, Any], response_data: dict[str, Any]
    ) -> dict[str, Any]:
        """给技法响应挂上技法依据卡（`data.technique_card`）。

        best-effort：卡片是元数据，任何构造失败都不许影响技法结果本身——宁可没有卡，
        也不能因为一份说明性数据让一次真实起盘失败（与 tracing 同款纪律，§9）。
        `HOROSA_TECHNIQUE_CARD=0` 关闭。
        """
        if not isinstance(response_data, dict):
            return response_data
        if os.environ.get("HOROSA_TECHNIQUE_CARD", "1").strip() in {"0", "false", "no"}:
            return response_data
        try:
            card = build_technique_card(
                tool_name=tool_name,
                technique_key=TOOL_EXPORT_TECHNIQUE_MAP.get(tool_name),
                domain=TOOL_DEFINITIONS[tool_name].domain if tool_name in TOOL_DEFINITIONS else None,
                input_normalized=input_normalized,
                response_data=response_data,
                skill_version=__version__,
                envelope_schema=TOOL_ENVELOPE_SCHEMA_VERSION,
                runtime_version=self._installed_runtime_version(),
            )
        except Exception:  # noqa: BLE001 - 元数据失败绝不拖垮技法调用
            logger.debug("technique card build failed for %s", tool_name, exc_info=True)
            return response_data
        # 决策层自陈（v0.39.0）：本次调用里每一条 Jev 决策（面 / 模型 / 选项 / 置信 / 是否采纳）。
        # 只在有记录时挂键——缺省 off 时卡片逐字节不变。
        decisions = current_decision_records()
        if decisions:
            card["decisions"] = decisions
        augmented = dict(response_data)
        augmented["technique_card"] = card
        return augmented

    def _installed_runtime_version(self) -> str | None:
        try:
            manifest = self.runtime_manager.load_installed_manifest()
        except Exception:  # noqa: BLE001 - 没装 runtime 是正常状态，不是错误
            return None
        if isinstance(manifest, dict):
            version = manifest.get("version")
            if isinstance(version, str) and version.strip():
                return version.strip()
        return None

    def _run_lingqi_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 灵棋经（上游 v3.9.0）：纯 headless JS —— 占时种子掷十二棋 → counts[上,中,下] → 六十四卦查表，
        # 七段快照由 vendored lingqiSnapshot 产出。种子算法留在 vendored core 里（tools/lingqi.js 只喂
        # 等价的 date/time 字段 shim），两边不各写一份。
        parts = _ken_datetime_parts(payload)
        js_payload: dict[str, Any] = {
            "year": parts["year"],
            "month": parts["month"],
            "day": parts["day"],
            "hour": parts["hour"],
            "minute": parts["minute"],
            "question": payload.get("question") or "",
            "category": payload.get("category") or "general",
            "timeLines": self._lingqi_time_lines(payload, parts),
        }
        if isinstance(payload.get("counts"), list):
            js_payload["counts"] = payload["counts"]
        if isinstance(payload.get("zhuVisible"), dict):
            js_payload["zhuVisible"] = payload["zhuVisible"]
        # 六戊日提示（卷首「六戊日不宜占卜」）需要日干支。走本仓 nongli 后端拿，**不**在 JS 侧引
        # lunar-javascript 另算一份——同口径原则（法奇门 faRelatedPeople 年干也是这么处理的）。
        # 拿不到就不给该行：提示缺失远好于按错口径印一行假的。
        day_ganzhi = self._lingqi_day_ganzhi(payload)
        if day_ganzhi:
            js_payload["dayGanZi"] = day_ganzhi
        try:
            result = self.js_client.run("lingqi", js_payload)
        except ToolTransportError:
            result = {}
        snapshot_text = result.get("snapshot_text") if isinstance(result, dict) else ""
        return {
            "counts": (isinstance(result, dict) and result.get("counts")) or js_payload.get("counts"),
            "seed": (isinstance(result, dict) and result.get("seed")) or None,
            "category": js_payload["category"],
            "day_ganzhi": day_ganzhi,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="lingqi", snapshot_text=snapshot_text),
        }

    def _lingqi_time_lines(self, payload: dict[str, Any], parts: dict[str, int]) -> list[str]:
        """[起盘信息] 的占时行。上游由 UI 拼，headless 这边按归一化输入如实拼一行。"""
        zone = f"{payload.get('zone') or ''}".strip()
        stamp = (
            f"{parts['year']:04d}-{parts['month']:02d}-{parts['day']:02d} "
            f"{parts['hour']:02d}:{parts['minute']:02d}"
        )
        return [f"占时：{stamp}{f'（{zone}）' if zone else ''}"]

    def _lingqi_day_ganzhi(self, payload: dict[str, Any]) -> str:
        try:
            nongli = self._call_remote(
                "/nongli/time",
                {
                    "date": payload.get("date"),
                    "time": payload.get("time") or "00:00:00",
                    "zone": payload.get("zone"),
                    "lat": payload.get("lat"),
                    "lon": payload.get("lon"),
                    "timeAlg": payload.get("timeAlg"),
                    # 显式 None 会把 null 发上线；帮手的纪律是「只在显式给定时发送」，
                    # 缺省不发 → 后端按默认 1/1 起算，与未传字节级等价。
                    **_day_boundary_switches(payload),
                },
            )
        except HorosaSkillError:
            return ""
        if not isinstance(nongli, dict):
            return ""
        # 后端两种形状都见过：顶层 dayGanZi 串，或 bazi.day.stem.cell。取到哪个用哪个，取不到就空。
        raw = nongli.get("dayGanZi") or nongli.get("dayGanzhi")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        bazi = nongli.get("bazi") if isinstance(nongli.get("bazi"), dict) else {}
        day = bazi.get("day") if isinstance(bazi.get("day"), dict) else {}
        stem = day.get("stem") if isinstance(day.get("stem"), dict) else {}
        cell = stem.get("cell")
        return f"{cell}".strip() if isinstance(cell, str) else ""

    def _run_geomancy_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 天文地占：以起卦时刻确定性起卦（castMethod='time' + timeSeed 由 年月日时分 派生，同盘可复现），
        # 后端 /geomancy/reading 由 4 母卦推 16 图形 + 十二宫图形入宫 + 判官/见证/解读技法 + 转宫派生 + 定局落星。
        options = payload.get("options") if isinstance(payload.get("options"), dict) else {}
        profile = payload.get("profile") or "european_classical"
        chart_mode = options.get("chartMode")
        # ifa（西非同族）是结构对照模式：不产地占判读、须随附文化声明。skill 只暴露 8 家占断传本，明确拒绝
        # ifa（含经 options.chartMode 触发），给结构化错误 + 声明，绝不静默降级出空盘。
        if profile == "ifa" or chart_mode == "ifa":
            raise ToolValidationError(
                "天文地占的 ifa（西非同族）为结构对照模式，只作图形/比特同构对照、不产出该体系之占断，"
                "故本 skill 不作为可调用能力暴露。请改用 "
                + "/".join(_GEOMANCY_PROFILES) + " 之一。",
                code="tool.geomancy_structural_only_unsupported",
                details={"profile": profile, "chartMode": chart_mode,
                         "cultural_notice": "Ifá 为独立圣传体系，仅结构同构对照，不套地占含义、不构成占断。"},
            )
        if profile not in _GEOMANCY_PROFILES:
            profile = "european_classical"
        question_type = f"{payload.get('questionType') or 'custom'}".strip() or "custom"
        if question_type not in _GEOMANCY_QUESTION_TYPES:
            raise ToolValidationError(
                bilingual(
                    f"地占问类 {question_type!r} 不存在（后端只认 {'/'.join(_GEOMANCY_QUESTION_TYPES)}；其余会被静默改回 custom）。",
                    f"Unknown geomancy questionType {question_type!r}; the backend knows {'/'.join(_GEOMANCY_QUESTION_TYPES)}.",
                ),
                code="tool.geomancy_invalid_question_type",
                details={"questionType": question_type, "allowed": list(_GEOMANCY_QUESTION_TYPES)},
            )
        parts = _ken_datetime_parts(payload)
        # 🔴 sync311 F10：时间起卦种子 = 上游 computeTimeSeed（YY 两位年 … mod 2^31−1）；此前 skill 用
        # YYYYMMDDHHmm 整数，与上游同一时刻起出不同的母图。
        time_seed = _geomancy_time_seed(parts)
        request: dict[str, Any] = {
            "question": payload.get("question") or "",
            "questionType": question_type,
            "castMethod": "time",
            "timeSeed": time_seed,
            "profile": profile,
        }
        # 🔴 sync311 F12：所问之时地同发（上游 GeomancyMain.clickCast :1161-1167）——后端只在
        # ascSource=real_chart / houseProjection=real_ephemeris 时用它起真实上升/真实星历（webgeomancysrv
        # _parse_time_place），此前不发 → 两档静默回落图形取法。纪元前才发 ad（公元后请求体逐字节不变）。
        for key in ("date", "time", "zone", "lat", "lon"):
            if payload.get(key) not in (None, ""):
                request[key] = payload[key]
        if payload.get("ad") == -1:
            request["ad"] = -1
        # 🔴 sync311 wave 3：所问宫 / 读取范围 / 黄道体系**恒发**，与上游两路同形 —— 页面 clickCast
        # （GeomancyMain.js:1150-1158）与 AI 挂载复算 buildGeomancySnapshotForFields（:808-817）都是
        # quesitedHouse = Number(所问宫) || QUESTION_TYPE_HOUSE[问类] || 1、readingScope || 'L3'、zodiacSystem ||
        # 'classical'，且换流派不动后两项（changeGeomancyOpt:1437-1444 只清 granular）。此前 skill 未给即不发 →
        # 内核按流派 profile 回落（chart.py:120-121）：european_planetary 走行星黄道、arabic_raml 只读到 L2 ——
        # 同一问占与上游起出两样的判读。
        try:
            quesited = int(payload.get("quesitedHouse") or 0)
        except (TypeError, ValueError):
            quesited = 0
        request["quesitedHouse"] = quesited or _GEOMANCY_QUESTION_HOUSE.get(question_type, 1)
        request["readingScope"] = payload.get("readingScope") or "L3"
        request["zodiacSystem"] = payload.get("zodiacSystem") or "classical"
        if payload.get("turnTo") is not None:
            request["turnTo"] = payload["turnTo"]
        # 传本粒度覆盖 passthrough（白名单；chartMode='ifa' 已在上方拦下，此处不会透传）。
        for key in _GEOMANCY_OPTION_KEYS:
            if options.get(key) is not None:
                request[key] = options[key]
        # 报数起卦（上游 clickCast :1175-1187）：十六个正整数，奇=单点/偶=双点，母一至母四之火风水土序；
        # castMethod=numbers + 种子（盾牌由数定，辅助随机仍须确定：缺省用本刻时间种子，options.seed 覆盖）。
        cast_numbers = options.get("castNumbers")
        if cast_numbers is not None:
            raw_numbers = cast_numbers.replace("，", ",").replace(",", " ").split() if isinstance(cast_numbers, str) else cast_numbers
            try:
                numbers = [int(x) for x in raw_numbers] if isinstance(raw_numbers, (list, tuple)) else []
            except (TypeError, ValueError):
                numbers = []
            if len(numbers) != 16 or any(n < 1 for n in numbers):
                raise ToolValidationError(
                    bilingual(
                        "报数起卦须自报十六个正整数（奇=单点、偶=双点；序为母一至母四之火风水土）。",
                        "castNumbers must be sixteen positive integers (odd = single dot, even = double dot).",
                    ),
                    code="tool.geomancy_invalid_cast_numbers",
                    details={"castNumbers": cast_numbers},
                )
            request.update({"castMethod": "numbers", "castNumbers": numbers, "seedMode": "manual"})
            request.pop("timeSeed", None)
            request["seed"] = int(options["seed"]) if options.get("seed") is not None else time_seed
        # seed 只在报数起卦里有用（时间起卦恒用 timeSeed）：单给 seed 也照实回执为未用。
        known = set(_GEOMANCY_OPTION_KEYS) | {"castNumbers"} | ({"seed"} if cast_numbers is not None else set())
        geo_ignored = sorted(k for k in options if k not in known)
        response = self._call_remote("/geomancy/reading", request)
        snapshot_text = _build_geomancy_snapshot_text(response if isinstance(response, dict) else {})
        result: dict[str, Any] = {
            "reading": response.get("reading") if isinstance(response, dict) else None,
            "figures": response.get("figures") if isinstance(response, dict) else None,
            "time_seed": request.get("timeSeed"),
            "params_ignored": geo_ignored,
        }
        if geo_ignored:
            result["_warnings"] = [f"geomancy 未识别的 options 键已忽略（未转发后端）：{'、'.join(geo_ignored)}。"]
        # [十六卦目录]（v0.33.0 批 I-5，/geomancy/catalog）：16 图形属性总表（agent grounding 用）。
        # 条件段：includeCatalog=true 才产。
        if payload.get("includeCatalog"):
            catalog = self._call_remote("/geomancy/catalog", {})
            figures = catalog.get("figures") if isinstance(catalog, dict) else None
            if not isinstance(figures, list) or not figures:
                raise ToolTransportError(
                    "地占十六卦目录端点返回了意外形状。",
                    code="tool.geomancy_catalog_failed",
                    details={"endpoint": "/geomancy/catalog"},
                )
            result["catalog"] = catalog
            cat_lines = [f"十六图形属性总表（{len(figures)} 形）："]
            for fig in figures:
                if not isinstance(fig, dict):
                    continue
                dots = fig.get("dots") if isinstance(fig.get("dots"), list) else []
                dots_txt = " ".join("●" if int(d or 0) == 1 else "●●" for d in dots)
                bits = [
                    f"{fig.get('nameZh')}（{fig.get('nameEn')}）",
                    f"卦形 {dots_txt}",
                    f"五行 {fig.get('elementZh')}",
                    f"主星 {fig.get('planetZh')}",
                    f"星座 {fig.get('signZh')}",
                    f"性 {fig.get('qualityZh')}",
                ]
                if fig.get("keywordsZh"):
                    bits.append(f"象 {fig.get('keywordsZh')}")
                cat_lines.append("　".join(bits))
            if snapshot_text:
                snapshot_text = f"{snapshot_text}\n\n[十六卦目录]\n" + "\n".join(cat_lines)
        result["snapshot_text"] = snapshot_text
        result["export_snapshot"] = self._augment_export_payload(technique="geomancy", snapshot_text=snapshot_text)
        return result

    def _run_sixyao_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # [Q-390/T-372] 占时时间算法：页面 > 全局 > 缺省真太阳时(0)（上游 GuaZhanMain.genParams，
        # GuaZhanMain.js:666-669）。此前根本不发 timeAlg → 桥恒按真太阳时，用户选「直接时间」静默无效。
        # 日界/晚子时两开关与上游同带（genParams 带 defaultAfter23NewDay/defaultLateZiHourUseNextDay）：
        # 仅显式给定时发送，缺省走后端默认 1/1 = 星阙出厂全局默认，字节与此前相同。
        time_alg = payload.get("timeAlg")
        nongli_request = {
            "date": payload["date"],
            "time": payload["time"],
            "zone": payload["zone"],
            "lon": payload["lon"],
            "lat": payload["lat"],
            "gpsLat": payload.get("gpsLat"),
            "gpsLon": payload.get("gpsLon"),
            "timeAlg": time_alg if time_alg is not None else 0,
            **_day_boundary_switches(payload),
            "ad": payload.get("ad", 1),
        }
        gender = payload.get("gender")
        if gender is not None and gender not in (0, 1):
            # 上游 buildGuaSnapshotText 只认 0/1（GuaZhanMain.js:234 `=== 0 || === 1`），别的值整行静默不出 —— 这里报错不吞。
            raise ToolValidationError(
                bilingual("六爻 gender 只认 1（男）/ 0（女）。", "sixyao gender must be 1 (male) or 0 (female)."),
                code="tool.sixyao_invalid_gender",
                details={"gender": gender},
            )
        nongli = self._call_remote("/nongli/time", nongli_request)
        lines = _normalize_gua_lines(payload.get("lines")) or _gua_code_lines(payload.get("gua_code"), payload.get("changed_code"))
        # 六爻层（core-js tools/liuyao.js）= 上游 AI 挂载无头路径 regenerateSixyaoSnapshot
        # （aiAnalysisContext.js:1739-1760）：未手动摇卦（lines 空）→ vendored buildTimeGua(nongli) 以时起卦
        # （年支序 + 农历月数 + 农历日数 + 时柱支序，时柱随 timeAlg）；齿轮 liuyaoSettings（上游 24 键扁平形）按
        # mergeLiuyaoGearSettings 合并；先载《断易天机》断语库，再由 vendored buildGuaSnapshotText(fields, st) 出**整份**
        # 快照（[起盘信息]…[占类断语] 八段，段序行式即上游；sync311 wave 3b 起不再有 Python 自写段）。
        # record = 上游 buildCaseSnapshotFields(record) 的入参（占时 + 时区 + 经纬度 + 求测人性别，:780-797）；
        # nongliParams 供 JS 按上游 ensureYearGZByLunar 补正月初一口径年干支。
        liuyao_settings = payload.get("liuyaoSettings")
        record: dict[str, Any] = {key: payload.get(key) for key in ("date", "time", "zone", "lon", "lat")}
        if gender is not None:
            record["gender"] = gender
        js_request: dict[str, Any] = {"nongli": nongli, "nongliParams": nongli_request, "record": record}
        if lines:
            js_request["lines"] = lines
        if isinstance(liuyao_settings, dict):
            js_request["liuyaoSettings"] = liuyao_settings
        try:
            struct = self.js_client.run("liuyao", js_request)
        except ToolTransportError as exc:
            # 起卦（以时）与整份快照都只在 vendored 上游函数里：引擎起不来就既起不出卦、也出不了上游快照。
            # 结构化报错，绝不回落一份自写的起卦式或自写段。
            if not lines:
                raise ToolTransportError(
                    bilingual(
                        "六爻以时起卦失败：起卦引擎（core-js buildTimeGua）不可用。请先体检 JS 运行时（horosa-skill doctor）。",
                        "sixyao time-cast failed: the core-js buildTimeGua engine is unavailable. Check the JS runtime (horosa-skill doctor).",
                    ),
                    code="tool.sixyao_time_cast_failed",
                    details={"reason": str(exc)},
                ) from exc
            raise ToolTransportError(
                bilingual(
                    "六爻快照引擎（core-js buildGuaSnapshotText）不可用：卦已由 lines 定，但出不了上游快照。请先体检 JS 运行时。",
                    "sixyao snapshot engine (core-js buildGuaSnapshotText) is unavailable: the lines fix the hexagram but the upstream snapshot cannot be built. Check the JS runtime.",
                ),
                code="tool.sixyao_engine_failed",
                details={"reason": str(exc)},
            ) from exc
        struct_data = struct.get("data") if isinstance(struct.get("data"), dict) else {}
        if struct_data.get("lines_invalid"):
            raise ToolValidationError(
                bilingual(
                    "六爻 lines 须六爻俱全（初→上），每爻 value 为 1 阳 / 0 阴。",
                    "sixyao lines must list all six lines (bottom to top), each with value 1 (yang) or 0 (yin).",
                ),
                code="tool.sixyao_invalid_lines",
                details={"lines": len(lines)},
            )
        if not lines:
            lines = _normalize_gua_lines(struct.get("lines"))
            if len(lines) != 6:
                raise ToolValidationError(
                    bilingual(
                        "六爻以时起卦失败：/nongli/time 缺年支/时柱/农历月日（buildTimeGua 取 year/time/monthInt/dayInt）。",
                        "sixyao time-cast failed: /nongli/time lacks year/time/monthInt/dayInt needed by buildTimeGua.",
                    ),
                    code="tool.sixyao_time_cast_failed",
                    details={"nongli_keys": sorted(nongli) if isinstance(nongli, dict) else []},
                )
        else:
            # 手动摇卦：回显 JS 实际装卦的逐爻（缺省爻名已按 setupYao 取该卦 yaoname）。
            lines = _normalize_gua_lines(struct.get("lines")) or lines
        current_code = payload.get("gua_code") or _derive_gua_code(lines)
        changed_code = payload.get("changed_code") or _derive_changed_gua_code(lines)
        # 卦辞原文：上游无头卦不带 guaDesc，[卦辞与断语] 只有段头（GuaZhanMain.js:338-363 + :62-63）；
        # /gua/desc 照旧取来放 data.descriptions（结构化数据面，不进快照）。
        descs = self._call_remote("/gua/desc", {"name": [current_code, changed_code]})
        snapshot_text = struct.get("snapshot_text") or ""
        if not snapshot_text.strip():
            raise ToolTransportError(
                bilingual(
                    "六爻快照引擎返回空快照（buildGuaSnapshotText）。",
                    "sixyao snapshot engine returned an empty snapshot (buildGuaSnapshotText).",
                ),
                code="tool.sixyao_engine_failed",
                details={"time_cast": bool(struct.get("time_cast"))},
            )
        result = {
            "nongli": nongli,
            "current_code": current_code,
            "changed_code": changed_code,
            "lines": lines,
            "question": payload.get("question"),
            "descriptions": descs,
            "snapshot_text": snapshot_text,
        }
        if struct_data.get("settings"):
            result["liuyao_settings"] = struct_data["settings"]
        warnings: list[str] = []
        if struct_data.get("settings_ignored"):
            warnings.append(
                f"liuyaoSettings 中这些键不是六爻判读口径，已忽略：{struct_data['settings_ignored']}"
                "（可用键见 horosa_agent_guidance(tool_name=\"sixyao\")）。"
            )
        if struct_data.get("settings_invalid"):
            warnings.append(
                f"liuyaoSettings 取值不在词表内，已按缺省处理：{struct_data['settings_invalid']}。"
            )
        # JS 层自报的缺损（断语库未载入 / 正月初一口径年干支补不出）：上游同样不阻断快照，这里如实回执。
        for note in struct_data.get("warnings") or []:
            if isinstance(note, str) and note and note not in warnings:
                warnings.append(note)
        if warnings:
            result["_warnings"] = warnings
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
            # query 模式（v0.30.0）：跨全部知识域全文检索；不给 query 走精读老路。
            if f"{payload.get('query') or ''}".strip():
                return search_knowledge(payload)
            return read_knowledge_entry(payload)
        if definition.name == "qimen":
            return self._run_qimen_tool(payload)
        if definition.name == "qimenzeri":
            return self._run_qimenzeri_tool(payload)
        if definition.name in self._ZERI_SCAN_TOOLS:
            return self._run_zeri_scan_tool(definition.name, payload)
        if definition.name in self._ZERI_BACKEND_TOOLS:
            return self._run_zeri_backend_tool(definition.name, payload)
        if definition.name == "tianxing":
            return self._run_tianxing_tool(payload)
        if definition.name == "qizhengelection":
            return self._run_qizheng_election_tool(payload)
        if definition.name == "india_rectify":
            return self._run_india_rectify_tool(payload)
        if definition.name == "planet_cycles":
            return self._run_planet_cycles_tool(payload)
        if definition.name == "jieqi_birth":
            return self._run_jieqi_birth_tool(payload)
        if definition.name == "taiyi":
            return self._run_taiyi_tool(payload)
        if definition.name == "jinkou":
            return self._run_jinkou_tool(payload)
        if definition.name in {"liureng_gods", "liureng_runyear"}:
            return self._run_liureng_tool(definition.name, payload)
        if definition.name in {"bazi_birth", "bazi_direct"}:
            return self._run_bazi_tool(definition.name, payload)
        if definition.name == "ziwei_birth":
            return self._run_ziwei_tool(payload)
        if definition.name == "suzhan":
            return self._run_suzhan_tool(payload)
        if definition.name == "sixyao":
            return self._run_sixyao_tool(payload)
        if definition.name == "geomancy":
            return self._run_geomancy_tool(payload)
        if definition.name == "tarot":
            return self._run_tarot_tool(payload)
        if definition.name == "lingqi":
            return self._run_lingqi_tool(payload)
        if definition.name == "tongshefa":
            return self._run_tongshefa_tool(payload)
        if definition.name == "canping":
            return self._run_canping_tool(payload)
        if definition.name == "heluo":
            return self._run_heluo_tool(payload)
        if definition.name == "yizhangjing":
            return self._run_yizhangjing_tool(payload)
        if definition.name == "xiaoliuren":
            return self._run_xiaoliuren_tool(payload)
        if definition.name == "feigong":
            return self._run_feigong_tool(payload)
        if definition.name == "xiaochengtu":
            return self._run_xiaochengtu_tool(payload)
        if definition.name == "guice":
            return self._run_guice_tool(payload)
        if definition.name == "zhengchuan":
            return self._run_zhengchuan_tool(payload)
        if definition.name == "acg":
            return self._run_acg_tool(payload)
        if definition.name == "astrodata":
            return self._run_astrodata_tool(payload)
        if definition.name == "bazi_inverse":
            return self._run_bazi_inverse_tool(payload)
        if definition.name == "sanshiunited":
            return self._run_sanshiunited_tool(payload)
        if definition.name == "huangli":
            return self._run_huangli_tool(payload)
        if definition.name == "tongshu":
            return self._run_tongshu_tool(payload)
        if definition.name == "xuanshi":
            return self._run_xuanshi_tool(payload)
        if definition.name == "babylon":
            return self._run_babylon_tool(payload)
        if definition.name == "draconic":
            return self._run_draconic_tool(payload)
        if definition.name == "relocation":
            return self._run_relocation_tool(payload)
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
        if definition.name == "ephemeris":
            return self._run_ephemeris_tool(payload)
        if definition.name == "returntimeline":
            return self._run_returntimeline_tool(payload)
        if definition.name == "prenatalsyzygy":
            return self._run_prenatalsyzygy_tool(payload)
        if definition.name == "prog":
            return self._run_prog_tool(payload)
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
        ) as trace, _degrade_collector() as degrade_notes, decision_records(), _run_query_scope(query_text):
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
                    input_normalized = self._apply_upstream_predictive_defaults(tool_name, input_normalized)
                    if tool_name == "india_chart":
                        # 流派预设（岁差/宫制）先落进规范化输入：请求体与快照口径行同源（否则盘按 KP 岁差算、
                        # [起盘信息] 却按缺省写 Lahiri）。
                        input_normalized = _india_apply_school_presets(input_normalized)
                    remote_input = (
                        _india_chart_remote_payload(input_normalized) if tool_name == "india_chart" else input_normalized
                    )
                    response_data = self._call_remote(definition.endpoint, remote_input)
                    response_data = self._attach_predictive_chart_context(tool_name, input_normalized, response_data)
                response_data = self._attach_natal_extras(tool_name, response_data, input_normalized)
                response_data = self._attach_classical_derived(tool_name, response_data, input_normalized)
                response_data = self._attach_classical_analysis(tool_name, input_normalized, response_data)
                response_data = self._attach_jyotish_sections(tool_name, response_data, input_normalized)
                response_data = self._attach_india_extra_vargas(tool_name, input_normalized, response_data)
                response_data = self._attach_calendar_extras(tool_name, input_normalized, response_data)
                response_data = self._attach_relative_score(tool_name, input_normalized, response_data)
                response_data = self._attach_relative_comp_charts(tool_name, input_normalized, response_data)
                response_data = self._attach_jieqi_year_extras(tool_name, input_normalized, response_data)
                response_data = _attach_export_contract(tool_name, input_normalized, response_data)
                # 技法依据卡：必须在 save_result **之前**挂，memory 才存到全量卡；
                # `_apply_response_view` 在存档之后裁剪，且显式豁免这个键（见那里的说明）。
                response_data = self._attach_technique_card(tool_name, input_normalized, response_data)
                summary = _generic_summary(tool_name, response_data)
                # 工具内部经 `_warnings` 上抛的降级说明（如子引擎不可用）落入 envelope.warnings，
                # 不静默：调用方能看到「结果不完整」而 ok 仍为 True（优雅降级 ≠ 无声降级）。
                warnings: list[str] = []
                if isinstance(response_data, dict):
                    raised = response_data.pop("_warnings", None)
                    if isinstance(raised, list):
                        warnings.extend(str(item) for item in raised if f"{item}".strip())
                warnings.extend(note for note in degrade_notes if note not in warnings)
                zone_note = _cn_unified_zone_note(input_normalized)
                if zone_note and zone_note not in warnings:
                    warnings.append(zone_note)
                # 预设段缺席 → warnings + summary 各一条：agent 不翻 export_snapshot 也知道结果不完整。
                missing_note = _missing_sections_warning(response_data)
                if missing_note:
                    warnings.append(missing_note)
                    summary = [*summary, missing_note]
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
                error_details = _with_operational_recovery(exc.code, exc.details)
                envelope = ToolEnvelope(
                    ok=False,
                    tool=tool_name,
                    version=__version__,
                    input_normalized=input_normalized,
                    data={},
                    summary=[f"工具 `{tool_name}` 调用失败（{exc.code}）。"],
                    warnings=list(degrade_notes),
                    memory_ref=None,
                    error=ErrorInfo(code=exc.code, message=str(exc), details=error_details),
                    # 顶层镜像三键（见 schemas/common.py）：MCP 面的闸门/校验错误一直镜像，工具自身的
                    # 错误（runtime.not_installed / tool.ken_compute_failed / transport.*）却没有，
                    # 按顶层 `code` 读的调用方在最常见的失败上读到 None。两条路径口径必须一致。
                    code=exc.code,
                    message=str(exc),
                    details=error_details,
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
                    warnings=list(degrade_notes),
                    memory_ref=None,
                    error=ErrorInfo(
                        code="tool.internal_error",
                        message=str(exc),
                        details={"exception_type": type(exc).__name__},
                    ),
                    code="tool.internal_error",
                    message=str(exc),
                    details={"exception_type": type(exc).__name__},
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
                # run_id 要到存档时才存在，所以技法卡的 refs 只能在这里补。存档里的那份没有自己的
                # run_id（自指），这是正常的——取回时 run_id 本来就是你用来取它的那把钥匙。
                card = envelope.data.get("technique_card") if isinstance(envelope.data, dict) else None
                if isinstance(card, dict):
                    card["refs"] = {
                        "run_id": effective_run_id,
                        "trace_id": trace["trace_id"],
                        "group_id": trace["group_id"],
                    }

            # response_view 视图裁剪在存档之后：memory 保全量，返回体按需精简。
            envelope = _apply_response_view(envelope, input_normalized)
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
                offset=max(0, getattr(request, "offset", 0) or 0),
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

    def technique_report(self, payload: dict[str, Any]) -> dict[str, Any]:
        """技法依据报告：把已存运行的技法卡渲染成 markdown / json / docx / pdf。

        与 `report_render` 的分工：那份是 **AI 写正文的咨询报告**（没有 ai_report 就拒绝出终稿）；
        这份是**确定性元数据**——用了什么技法、什么口径、谁算的、段落全不全、版本链——所以随时能出，
        不需要也不接受 AI 正文。两者不混：`references/reports.md` 明令咨询报告正文不带机器元数据。
        """
        with self.tracer.span(
            workflow_name="report.technique",
            metadata={"entrypoint": "report.technique", "payload": payload},
        ) as trace:
            try:
                request = TechniqueReportInput.model_validate(payload)
            except ValidationError as exc:
                trace["error_code"] = "report.technique.invalid_payload"
                errors = exc.errors()
                raise ToolValidationError(
                    "Invalid payload for technique report.",
                    code="report.technique.invalid_payload",
                    details={
                        "errors": errors,
                        "agent_recovery": build_validation_recovery(operation_name="technique_report", errors=errors),
                    },
                ) from exc

            normalized_format = str(request.format or "markdown").lower().strip()
            if normalized_format not in {"markdown", "json", "docx", "pdf"}:
                raise ToolValidationError(
                    "format must be one of: markdown, json, docx, pdf",
                    code="report.technique.invalid_format",
                    details={"format": request.format},
                )

            scope = "group" if request.group_id else "run"
            cards, source_runs = self._collect_technique_cards(
                run_id=request.run_id, group_id=request.group_id
            )
            if not cards:
                raise ToolValidationError(
                    "No stored run carries a technique card yet — run a technique tool first "
                    "(cards are attached to every successful technique call).",
                    code="report.technique.no_cards",
                    details={"run_id": request.run_id, "group_id": request.group_id},
                )
            document = build_technique_report(
                cards=cards,
                scope=scope,
                scope_id=request.group_id or request.run_id or (source_runs[0] if source_runs else None),
                title=request.title,
            )
            if request.include_sections is False:
                for card in document.get("cards", []):
                    (card.get("sections") or {}).pop("titles", None)

            scope_id = document["scope_id"] or "latest"
            if request.output_path:
                output_path = Path(request.output_path).expanduser().resolve()
            else:
                suffix = "md" if normalized_format == "markdown" else normalized_format
                base = self.store.default_report_path(
                    run_id=str(scope_id), tool_name="technique", format_name="json"
                )
                output_path = base.with_suffix(f".{suffix}")
            try:
                rendered = render_report(document, output_path=output_path, format_name=normalized_format)
            except ValueError as exc:
                raise ToolValidationError(
                    str(exc), code="report.technique.render_failed", details={"format": normalized_format}
                ) from exc

            result = {
                "ok": True,
                "schema": document["schema"],
                "scope": scope,
                "scope_id": document["scope_id"],
                "technique_count": document["technique_count"],
                "consistency": document["consistency"],
                "artifact_path": rendered["path"],
                "format": rendered["format"],
                "file_size": rendered.get("file_size"),
                "document": document,
                "summary": [
                    f"已生成技法依据报告（{document['technique_count']} 个技法）：{rendered['path']}",
                    *(
                        []
                        if document["consistency"]["all_clear"]
                        else ["⚠️ 报告含一致性告警，请阅读「一致性检查」一节后再引用结论。"]
                    ),
                ],
                "trace_id": trace["trace_id"],
                "group_id": trace["group_id"],
            }
            trace["artifact_path"] = rendered["path"]
            trace["success"] = True
            return result

    def _collect_technique_cards(
        self, *, run_id: str | None, group_id: str | None
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """取出目标运行的技法卡（按调用先后）。都不给时取最近一次带卡的运行。"""
        if group_id:
            runs = self.store.query_runs(group_id=group_id, include_payload=True, limit=200)
        elif run_id:
            runs = self.store.query_runs(run_id=run_id, include_payload=True, limit=1)
        else:
            runs = self.store.query_runs(include_payload=True, limit=20)
        cards: list[dict[str, Any]] = []
        seen_runs: list[str] = []
        for run in sorted(runs, key=lambda item: str(item.get("created_at") or "")):
            for artifact in run.get("artifacts") or []:
                if artifact.get("kind") != "tool_result":
                    continue
                payload = artifact.get("payload")
                if not isinstance(payload, dict):
                    continue
                card = (payload.get("data") or {}).get("technique_card")
                if isinstance(card, dict):
                    cards.append(card)
                    # query_runs 的键是 `run_id`（不是 `id`）。读错键 + `str(None)` = 报告标题和
                    # 文件名里出现字面 "None" —— f-string None 陷阱的同族（AGENTS §5 步骤 10）：
                    # 先取值判空，别把 None 直接格式化。
                    identifier = run.get("run_id")
                    if isinstance(identifier, str) and identifier and identifier not in seen_runs:
                        seen_runs.append(identifier)
            # 无 group 无 run 时只要最近的一份，多取会把不相干的历史运行混进同一份报告。
            if cards and not group_id and not run_id:
                break
        return cards, seen_runs

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
            # 只要求 export_snapshot（唯一导出契约）；旧归档带 export_format 双字段的天然满足 → 向后兼容。
            return isinstance(data, dict) and isinstance(data.get("export_snapshot"), dict)

        source = next((artifact for artifact in candidates if has_complete_export_contract(artifact)), candidates[0])
        payload = source.get("payload")
        data = payload.get("data") if isinstance(payload, dict) else {}
        source_tool = str(source.get("tool_name") or "")
        if source.get("kind") == "tool_result" and source_tool in TOOL_EXPORT_TECHNIQUE_MAP and not (
            isinstance(data, dict)
            and isinstance(data.get("export_snapshot"), dict)
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

    def hecan(self, payload: dict[str, Any]) -> dict[str, Any]:
        """合参（v0.28.0 B3）：一问多技法交叉印证——全行业没有的形态，也只有 92 技法才做得起。

        传统方法论（三式互参、八字紫微互证）+ orchestrator-workers 编排：路由/显式选盘（上限
        max_tools）→ 同一 group 逐技法起盘（复用 dispatch 全部载荷管线与澄清闸）→ 产出**合参模板**：
        逐技法证据表（引用不复制全文）+ 口径一致性（复用技法卡冲突检测）+ ai_fillable 综合槽。
        两条铁律写进模板 instructions：**只准引用已导出段落的事实**；**分歧必须披露，不许平均**。
        """
        with self.tracer.span(
            workflow_name="hecan.run",
            metadata={"entrypoint": "hecan", "payload": payload},
        ) as trace:
            try:
                request = HecanInput.model_validate(payload)
            except ValidationError as exc:
                errors = exc.errors()
                raise ToolValidationError(
                    "Invalid payload for horosa_hecan.",
                    code="hecan.invalid_payload",
                    details={
                        "errors": errors,
                        "agent_recovery": build_validation_recovery(
                            operation_name="horosa_hecan", tool_name="hecan", errors=errors
                        ),
                    },
                ) from exc

            max_tools = max(1, min(int(request.max_tools or 5), 8))
            preselected = [t for t in (request.tools or []) if t][:max_tools] or None
            dispatch_payload = request.model_dump(exclude_none=True)
            dispatch_payload.pop("tools", None)
            dispatch_payload.pop("max_tools", None)
            envelope = self.dispatch(dispatch_payload, preselected_tools=preselected)
            if not envelope.ok and not envelope.results:
                # 路由失败原样透出（含 agent_recovery），不包一层假成功。
                return {
                    "ok": False,
                    "schema": HECAN_SCHEMA,
                    "question": request.query,
                    "error": envelope.error.model_dump(mode="json") if envelope.error else None,
                    "code": envelope.code,
                    "message": envelope.message,
                    "details": envelope.details,
                    "trace_id": trace["trace_id"],
                    "group_id": envelope.group_id,
                }

            selected = envelope.selected_tools[:max_tools]
            techniques: list[dict[str, Any]] = []
            cards: list[dict[str, Any]] = []
            for tool_name in selected:
                result = envelope.results.get(tool_name)
                if result is None:
                    continue
                data = result.data if isinstance(result.data, dict) else {}
                export = data.get("export_snapshot") if isinstance(data.get("export_snapshot"), dict) else {}
                card = data.get("technique_card") if isinstance(data.get("technique_card"), dict) else None
                if card:
                    cards.append(card)
                technique_info = export.get("technique") if isinstance(export.get("technique"), dict) else {}
                titles = [
                    section.get("title")
                    for section in export.get("sections", [])
                    if isinstance(section, dict) and section.get("title")
                ]
                techniques.append({
                    "tool": tool_name,
                    "ok": result.ok,
                    "technique": {"key": technique_info.get("key"), "label": technique_info.get("label")},
                    "summary": list(result.summary),
                    "section_titles": titles,
                    "sections_health": {
                        "missing_selected_sections": export.get("missing_selected_sections") or [],
                        "unknown_detected_sections": export.get("unknown_detected_sections") or [],
                    },
                    "error": result.error.model_dump(mode="json") if result.error else None,
                    # 证据指针而非全文：完整段落在 dispatch 存档里，memory_show(run_id) 可取。
                    "evidence_pointer": {
                        "run_id": envelope.memory_ref.run_id if envelope.memory_ref else None,
                        "read_with": "horosa_memory_show",
                    },
                })

            consistency = build_technique_report(
                cards=cards, scope="group", scope_id=envelope.group_id
            )["consistency"] if cards else {"setting_conflicts": [], "export_contract_unclean": [], "compute_mismatched": [], "all_clear": None}

            template = {
                "ok": True,
                "schema": HECAN_SCHEMA,
                "question": request.query,
                "selected_tools": selected,
                "techniques": techniques,
                "consistency": consistency,
                "synthesis_contract": {
                    "instructions": [
                        "先读每个技法的导出段落（memory_show 取全量），再填 cross_validation：每技法一条结论，"
                        "必须绑定该技法真实段落里的事实，不许引用未导出的内容。",
                        "convergence 只写多技法**独立**得出的共同判断；一个技法的结论不算共识。",
                        "divergence 必须逐条披露（哪两个技法、各说什么、可能因口径差异还是体系差异）——"
                        "**分歧不许平均、不许只挑一边**；无法调和就写无法调和。",
                        "consistency.setting_conflicts 非空时，先声明口径冲突再谈结论可比性。",
                        "final_answer 先直答用户问题，再给依据与边界；引用口径/教义按 SKILL.md 带出处。",
                    ],
                    "ai_fillable": {
                        "cross_validation": [
                            {"tool": t["tool"], "label": (t["technique"] or {}).get("label"), "conclusion": "", "evidence_lines": []}
                            for t in techniques
                        ],
                        "convergence": "",
                        "divergence": "",
                        "final_answer": "",
                    },
                },
                "memory_ref": envelope.memory_ref.model_dump(mode="json") if envelope.memory_ref else None,
                "summary": [
                    f"合参已起 {len(techniques)} 个技法（{('、'.join(selected))}），同组存档待综合。",
                    "这是合参模板，不是终稿：请按 synthesis_contract 填写后给出结论（分歧必须披露）。",
                ],
                "trace_id": trace["trace_id"],
                "group_id": envelope.group_id,
            }
            trace["success"] = True
            trace["selected_tools"] = selected
            return template

    # ---- 可选云端决策层（v0.39.0）：三个面的采纳逻辑都在这里，代码持有权限、模型只供证据 ----
    def _decision_layer_view(self, records: list[dict[str, Any]]) -> dict[str, Any] | None:
        layer = self.decision_layer
        if layer is None:
            return None
        return {**layer.summary(), "records": list(records)}

    @staticmethod
    def _decision_guard(surface: str, fallback: Any, fn: Any) -> Any:
        """决策层的任何异常（问题规格、解析、编排 bug）都不许拖垮技法/调度：降级可见，返回确定性结果。

        `layer.ask` 只包住 provider；问题构造与采纳逻辑在它外面——v0.39.0 开发期一次 QuestionSpecError
        曾把整个 liureng_gods 打成 tool.internal_error，正是这一层要堵的形状。
        """
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - 决策层是可选增强，失败只能降级
            logger.debug("decision surface %s failed", surface, exc_info=True)
            _degrade("决策层（%s 面）内部错误 %s，已回落确定性路径。", surface, exc.__class__.__name__)
            return fallback

    def _decide_routing(
        self,
        request: DispatchInput,
        deterministic: list[str],
        error: DispatchResolutionError | None,
    ) -> list[str]:
        return self._decision_guard("dispatch", deterministic, lambda: self._decide_routing_inner(request, deterministic, error))

    def _decide_routing_inner(
        self,
        request: DispatchInput,
        deterministic: list[str],
        error: DispatchResolutionError | None,
    ) -> list[str]:
        """S1：两级 Choice。确定性路由命中 → 只记一致性；无解且 enforce 且 conf≥τ → 采纳兜底；其余原样。"""
        layer = self.decision_layer
        if layer is None or not layer.policy.surface_enabled("dispatch"):
            return deterministic
        state, redaction = build_meta_state(request.query)
        outcome = layer.ask(
            "dispatch",
            state=state,
            questions=build_routing_questions(),
            redaction=redaction,
            intent="route a natural-language request to one technique tool",
        )
        if not outcome.ok or outcome.answers is None:
            return deterministic
        decision = resolve_routing(outcome.answers.answers, tau=outcome.tau)
        info = {**decision.as_dict(), "deterministic": list(deterministic), "agree": bool(deterministic) and decision.tool in deterministic}
        if error is None:
            layer.finalize(outcome, adopted=False, reason="deterministic router matched; recorded for shadow comparison", decision=info)
            return deterministic
        if outcome.enforced and decision.tool:
            layer.finalize(outcome, adopted=True, reason="deterministic router had no match; decision-layer fallback", decision=info)
            return [decision.tool]
        layer.finalize(outcome, adopted=False, reason=("shadow" if not outcome.enforced else decision.reason), decision=info)
        return deterministic

    @staticmethod
    def _tool_asks_gender(tool_name: str) -> bool:
        from horosa_skill.agent_guidance import TOOL_GUIDANCE

        policy = TOOL_GUIDANCE.get(tool_name) or {}
        for item in policy.get("ask_if_missing") or []:
            fields = [part.strip() for part in str((item or {}).get("field") or "").split("/")]
            if "gender" in fields:
                return True
        return False

    def _decide_gender(
        self,
        request: DispatchInput,
        tool_name: str,
        payload: dict[str, Any],
        shared: dict[str, Any],
    ) -> None:
        self._decision_guard("extract", None, lambda: self._decide_gender_inner(request, tool_name, payload, shared))

    def _decide_gender_inner(
        self,
        request: DispatchInput,
        tool_name: str,
        payload: dict[str, Any],
        shared: dict[str, Any],
    ) -> None:
        """S2：只在工具会问性别、载荷没给、原话有性别词表命中时才问一次（同一 dispatch 共享一次调用）。"""
        layer = self.decision_layer
        if layer is None or not layer.policy.surface_enabled("extract"):
            return
        if payload.get("gender") not in (None, "") or not self._tool_asks_gender(tool_name):
            return
        candidates = gender_candidates(request.query)
        if not candidates.any:
            return
        if "gender" not in shared:
            state, redaction = build_meta_state(request.query)
            shared["gender"] = layer.ask(
                "extract",
                state=state,
                questions={"subject_gender": build_gender_question()},
                redaction=redaction,
                intent="extract the chart subject's gender only when the request states it",
            )
        outcome = shared["gender"]
        if not outcome.ok or outcome.answers is None:
            return
        decision = resolve_gender(outcome.answers.answers.get("subject_gender"), candidates, tau=outcome.tau)
        info = {**decision.as_dict(), "tool": tool_name}
        if decision.value is not None and outcome.enforced:
            payload["gender"] = decision.value
            note = f"gender={decision.value}（决策层自用户原话抽取：{'/'.join(decision.evidence)}；conf {decision.confidence:.2f}）"
            existing = payload.get("clarification_notes")
            payload["clarification_notes"] = f"{existing}；{note}" if existing else note
            layer.finalize(outcome, adopted=True, reason="explicitly stated in the request (lexicon + Jev agree)", decision=info)
            return
        layer.finalize(outcome, adopted=False, reason=("shadow" if not outcome.enforced else decision.reason), decision=info)

    def faithfulness_opinion(self, report: dict[str, Any], export_text: str | None) -> dict[str, Any] | None:
        """S4（二档 snapshot 才开）：对确定性忠实性报告的每条 claim 追加只读的模型意见；不改 report 本身。"""
        return self._decision_guard("faithfulness", None, lambda: self._faithfulness_opinion_inner(report, export_text))

    def _faithfulness_opinion_inner(self, report: dict[str, Any], export_text: str | None) -> dict[str, Any] | None:
        layer = self.decision_layer
        if layer is None or not layer.policy.surface_enabled("faithfulness"):
            return None
        claims = [claim for claim in (report.get("claims") or []) if isinstance(claim, dict)]
        if not claims or not str(export_text or "").strip():
            return None
        questions = build_opinion_questions(claims)
        if not questions:
            return None
        outcome = layer.ask(
            "faithfulness",
            state=build_opinion_state(str(export_text)),
            questions=questions,
            intent="second opinion on whether each extracted claim is supported by the chart export",
        )
        if not outcome.ok or outcome.answers is None:
            return None
        summary = summarize_opinion(claims, outcome.answers.answers, tau=outcome.tau)
        layer.finalize(outcome, adopted=False, reason="read-only second opinion (never affects report.ok)", decision={"agreement_rate": summary["agreement_rate"], "n_judged": summary["n_judged"]})
        return {"provider": "typesafe_jev", "model": outcome.answers.model, "mode": outcome.mode, "tau": outcome.tau, "latency_ms": outcome.latency_ms, **summary}

    def _decide_zhan_category(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._decision_guard("zhancat", payload, lambda: self._decide_zhan_category_inner(payload))

    def _decide_zhan_category_inner(self, payload: dict[str, Any]) -> dict[str, Any]:
        """S3：六壬占断门类（闭集 + general）；分错只多一段向导、盘面不变，conf≥τ 即填。"""
        layer = self.decision_layer
        if layer is None or not layer.policy.surface_enabled("zhancat"):
            return payload
        if payload.get("zhanCategory"):
            return payload
        text = payload.get("question") or _RUN_QUERY_TEXT.get() or ""
        if not str(text).strip():
            return payload
        state, redaction = build_meta_state(str(text))
        outcome = layer.ask(
            "zhancat",
            state=state,
            questions={"zhan_category": build_zhan_question()},
            redaction=redaction,
            intent="classify the topic of a 大六壬 question",
        )
        if not outcome.ok or outcome.answers is None:
            return payload
        decision = resolve_zhan(outcome.answers.answers.get("zhan_category"), tau=outcome.tau)
        if decision.category is not None and outcome.enforced:
            layer.finalize(outcome, adopted=True, reason="topic classified above tau", decision=decision.as_dict())
            return {**payload, "zhanCategory": decision.category}
        layer.finalize(outcome, adopted=False, reason=("shadow" if not outcome.enforced else decision.reason), decision=decision.as_dict())
        return payload

    def dispatch(
        self,
        payload: dict[str, Any],
        *,
        evaluation_case_id: str | None = None,
        preselected_tools: list[str] | None = None,
    ) -> DispatchEnvelope:
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

        routing_error: DispatchResolutionError | None = None
        decision_records_out: list[dict[str, Any]] = []
        try:
            # 合参等上层可显式点名技法（跳过关键词路由）；未知名照常走 run_tool 的 tool.unknown。
            selected_tools = list(preselected_tools) if preselected_tools else select_tools(request)
        except DispatchResolutionError as exc:
            routing_error = exc
            selected_tools = []
        # 决策层 S1（可选，缺省关）：确定性路由是权威；只有它无解时才可能采纳 Jev 的兜底，命中时只记一致性。
        if self.decision_layer is not None and not preselected_tools:
            with decision_records() as routing_records:
                selected_tools = self._decide_routing(request, selected_tools, routing_error)
            decision_records_out.extend(routing_records)
            if selected_tools:
                routing_error = None
        if routing_error is not None:
            exc = routing_error
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
                code=exc.code,
                message=str(exc),
                details=exc.details,
                decision_layer=self._decision_layer_view(decision_records_out),
            )

        normalized_inputs: dict[str, dict[str, Any]] = {}
        results: dict[str, ToolEnvelope] = {}
        result_export_contracts: dict[str, dict[str, Any]] = {}
        dispatch_warnings: list[str] = []
        extraction_shared: dict[str, Any] = {}

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
            total_tools = len(selected_tools)
            for tool_index, tool_name in enumerate(selected_tools, start=1):
                _progress_tick(tool_index - 1, total_tools, f"调度：{tool_name}（{tool_index}/{total_tools}）")
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
                    jieqi_lat = base_birth.get("lat", request.context.get("lat"))
                    jieqi_lon = base_birth.get("lon", request.context.get("lon"))
                    if not jieqi_lat or not jieqi_lon:
                        # 兜底赤道/本初子午线坐标会改变节气盘宫位——显式告知而非静默。
                        dispatch_warnings.append(
                            "jieqi_year 未提供经纬度，已按 0n00/0e00 兜底起盘；宫位随地点变化，建议补充坐标后重算。"
                        )
                    payload_for_tool = {
                        "year": year,
                        "zone": base_birth.get("zone", request.context.get("zone", "8")),
                        "lat": jieqi_lat or "0n00",
                        "lon": jieqi_lon or "0e00",
                        "time": request.context.get("time"),
                    }
                else:
                    payload_for_tool = dict(base_birth)

                payload_for_tool.update(confirmation)
                # 决策层 S2（可选，缺省关）：只把原话里**明说**的性别变成「已提供」（词表 + Jev 双钥）。
                if self.decision_layer is not None:
                    with decision_records() as extract_records:
                        self._decide_gender(request, tool_name, payload_for_tool, extraction_shared)
                    decision_records_out.extend(extract_records)
                normalized_inputs[tool_name] = payload_for_tool
                try:
                    results[tool_name] = self.run_tool(
                        tool_name,
                        payload_for_tool,
                        save_result=request.save_result,
                        run_id=run_id,
                        query_text=request.query,
                        group_id=trace["group_id"],
                        evaluation_case_id=evaluation_case_id,
                    )
                except ToolValidationError as exc:
                    # 决策层兜底选中的工具随后因缺参被拒时，调用方必须能看到「这个工具是谁选的」——否则一个
                    # 无匹配请求会以「huanglizeri 缺 startDate」的面目出现，而路由这一步的自陈全丢。
                    if decision_records_out and isinstance(exc.details, dict) and "decision_layer" not in exc.details:
                        exc.details["decision_layer"] = self._decision_layer_view(decision_records_out)
                    raise
                result_export_contracts[tool_name] = _build_dispatch_export_contract(results[tool_name])
            _progress_tick(total_tools, total_tools, "调度：汇总结果")

            degraded_tools = [name for name, result in results.items() if result.ok and result.warnings]
            if degraded_tools:
                dispatch_warnings.append(
                    f"{len(degraded_tools)} 个工具结果带降级/缺段说明：{', '.join(degraded_tools)}"
                    "（详见 results.<tool>.warnings，报告须如实转述）。"
                )
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
                warnings=dispatch_warnings,
                memory_ref=None,
                error=None,
                trace_id=trace["trace_id"],
                group_id=trace["group_id"],
                decision_layer=self._decision_layer_view(decision_records_out),
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
