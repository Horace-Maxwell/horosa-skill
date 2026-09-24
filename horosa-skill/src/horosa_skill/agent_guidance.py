from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.shenshu_options import options_doc
from horosa_skill.western_options_doc import western_options_doc


GUIDANCE_SCHEMA = "horosa.skill.agent_guidance.v1"

# ── 澄清闸单一真值源（v0.33.0 批 II-2：策略即数据）────────────────────────────────
# 豁免表/过闸字段/失败码/逃生舱档位全部声明在 data/sensitive_settings.json（自带 self_tests，
# pytest 与 benchmark 直接跑）；本模块只留判定逻辑。改闸策略改表，不改代码。
_SENSITIVE_SETTINGS_PATH = Path(__file__).parent / "data" / "sensitive_settings.json"
SENSITIVE_SETTINGS: dict[str, Any] = json.loads(_SENSITIVE_SETTINGS_PATH.read_text(encoding="utf-8"))

GLOBAL_AGENT_RULES: list[str] = [
    "If the client does not expose native horosa_* MCP tools, stop and ask the user/admin to run OpenClaw setup/check; do not fall back to shell or hand-written calculations.",
    "Do not hand-calculate Horosa methods with shell, Python, JavaScript, web snippets, or memorized formulas.",
    "Before calling a calculation tool, check whether the user supplied the fields and method settings that change the result.",
    "If a required or result-changing setting is missing, ask a short clarification question with concrete options instead of silently inventing a value.",
    "Use Horosa/Xingque defaults only when the user accepts defaults, asks for a quick/default reading, or the setting is explicitly documented as safe to default.",
    "For current-time questions, using the current local date/time/timezone is allowed, but location and technique-specific settings still need clarification when they matter.",
    "Timezone may be a fixed offset like +08:00 or an IANA name like America/Los_Angeles; Horosa normalizes IANA names by the chart date/time before calling the runtime.",
    "After a tool call, treat export_snapshot.export_text, export_snapshot.sections, and summary as the source of truth.",
]

COMMON_LOCATION_FIELDS = ["date", "time", "zone/timezone", "lat/lon or gpsLat/gpsLon/location"]
COMMON_BIRTH_FIELDS = ["birth date", "birth time", "birth timezone", "birth place / longitude / latitude"]
# 日界缺省（F2）：上游出厂缺省 1=「23 点算第二天」（utils/dayBoundary.js:39-45 defaultAfter23NewDay、models/astro.js:395-398）。
# v0.40 前这里写「False=星阙默认」且 schema 硬塞 False 下发 → bazi/ziwei/liureng/nongli 静默按 24 点换日。
_AFTER23_DEFAULT_MEANING = "星阙默认：23 点换日（缺省不传=引擎默认 1）；0=24 点换日"
CONFIRMATION_FIELDS: list[str] = list(SENSITIVE_SETTINGS["confirmation_fields"])
PREFLIGHT_EXEMPT_TOOLS: set[str] = set(SENSITIVE_SETTINGS["exempt_tools"])
GATE_FAILURE_CODE: str = str(SENSITIVE_SETTINGS["failure_code"])
INPUT_CONTRACT_SCHEMA = "horosa.skill.input_contract.v1"


def _clarify_override(tool_name: str) -> str | None:
    """HOROSA_CLARIFY 逃生舱：never=闸全关；granular:{"exempt":[…]}=按工具豁免；其余/缺省=always。
    返回 None（不干预）或放行模式名（写进闸结果的 mode，审计可见）。解析失败按 always（安全侧）。"""
    raw = os.environ.get("HOROSA_CLARIFY", "").strip()
    if not raw or raw.lower() == "always":
        return None
    if raw.lower() == "never":
        return "env_never"
    if raw.lower().startswith("granular:"):
        try:
            spec = json.loads(raw[len("granular:"):])
            if isinstance(spec, dict) and tool_name in set(spec.get("exempt") or []):
                return "env_granular_exempt"
        except (ValueError, TypeError):
            return None
    return None


def run_sensitive_settings_selftests() -> dict[str, Any]:
    """跑闸表自带的 self_tests（match/not_match 行为例）+ coverage 不变量（每个注册工具必须
    有 guidance 策略或在豁免表——新工具漏登记=红）。pytest 与 benchmark 共用本执行器。"""
    failures: list[str] = []
    for case in SENSITIVE_SETTINGS.get("self_tests", []):
        verdict = validate_agent_preflight(str(case["tool"]), dict(case.get("payload") or {}))
        actual = "pass" if verdict.get("ok") else "block"
        if actual != case["expect"]:
            failures.append(f"{case['name']}: expect {case['expect']}, got {actual}")
    unclassified = sorted(set(TOOL_DEFINITIONS) - set(TOOL_GUIDANCE) - PREFLIGHT_EXEMPT_TOOLS)
    if unclassified:
        failures.append(f"未分类工具（既无 guidance 策略也不在豁免表）：{unclassified}")
    return {"ok": not failures, "failures": failures, "cases": len(SENSITIVE_SETTINGS.get("self_tests", []))}


COMMON_ASTRO_PAYLOAD_EXAMPLE: dict[str, Any] = {
    "date": "1995-06-03",
    "time": "05:30",
    "zone": "+08:00",
    "lat": "31n13",
    "lon": "121e28",
    "hsys": 0,
    "zodiacal": 0,
    "agent_confirmed_settings": True,
    "clarification_notes": "User confirmed birth time, birthplace, timezone, Whole Sign houses, and tropical zodiac.",
}

PREDICTIVE_INPUT_CONTRACTS: dict[str, dict[str, Any]] = {
    "solarreturn": {
        "human_name": "太阳返照",
        "required_fields": ["date", "time", "zone", "lat", "lon", "datetime", "dirZone", "dirLat", "dirLon"],
        "must_ask": ["本命出生时间地点", "返照目标年份/日期", "返照地点与时区"],
        "target_fields": {
            "datetime": "返照目标时间，YYYY-MM-DD HH:mm:ss；缺省=今年生日时刻（当年+出生月日+出生时分，上游同律）。",
            "dirZone": "返照盘地点时区；缺省本命时区。",
            "dirLat/dirLon": "返照盘地点经纬度；缺省=出生地（上游同律）——异地返照先问用户现居地。",
        },
        "output_contract": ["本命盘配置", "起盘信息", "时段盘配置", "相位"],
        "example_payload": {
            **COMMON_ASTRO_PAYLOAD_EXAMPLE,
            "datetime": "2031-04-06 09:33:00",
            "dirZone": "+08:00",
            "dirLat": "31n13",
            "dirLon": "121e28",
        },
    },
    "lunarreturn": {
        "human_name": "月亮返照",
        "required_fields": ["date", "time", "zone", "lat", "lon", "datetime", "dirZone", "dirLat", "dirLon"],
        "must_ask": ["本命出生时间地点", "月返目标月份/日期", "月返地点与时区"],
        "target_fields": {
            "datetime": "月返目标时间，YYYY-MM-DD HH:mm:ss；缺省=今年生日时刻（上游同律）。",
            "dirZone": "月返盘地点时区；缺省本命时区。",
            "dirLat/dirLon": "月返盘地点经纬度；缺省=出生地（上游同律），异地月返先问用户。",
        },
        "output_contract": ["本命盘配置", "起盘信息", "时段盘配置", "相位"],
        "example_payload": {
            **COMMON_ASTRO_PAYLOAD_EXAMPLE,
            "datetime": "2031-04-06 09:33:00",
            "dirZone": "+08:00",
            "dirLat": "31n13",
            "dirLon": "121e28",
        },
    },
    "givenyear": {
        "human_name": "指定年推运 / 流年盘",
        "required_fields": ["date", "time", "zone", "lat", "lon", "datetime", "dirZone", "dirLat", "dirLon"],
        "must_ask": ["本命出生时间地点", "要看的年份/日期", "流年盘地点与时区"],
        "target_fields": {
            "datetime": "指定年中的目标时间，YYYY-MM-DD HH:mm:ss；缺省=今年生日时刻（上游同律）。",
            "dirZone": "流年盘地点时区；缺省本命时区。",
            "dirLat/dirLon": "流年盘地点经纬度；缺省=出生地（上游同律）。",
        },
        "output_contract": ["本命盘配置", "起盘信息", "时段盘配置", "相位"],
        "example_payload": {
            **COMMON_ASTRO_PAYLOAD_EXAMPLE,
            "datetime": "2031-04-06 09:33:00",
            "dirZone": "+08:00",
            "dirLat": "31n13",
            "dirLon": "121e28",
        },
    },
    "solararc": {
        "human_name": "太阳弧推运",
        "required_fields": ["date", "time", "zone", "lat", "lon", "datetime", "dirZone"],
        "must_ask": ["本命出生时间地点", "推运目标时间", "目标时区"],
        "target_fields": {
            "datetime": "太阳弧推运目标时间，YYYY-MM-DD HH:mm:ss；缺省=此刻（上游 +08:00 钟面）。",
            "dirZone": "推运盘目标时区；缺省本命时区。",
        },
        "output_contract": ["本命盘配置", "起盘信息", "时段盘配置", "相位"],
        "example_payload": {
            **COMMON_ASTRO_PAYLOAD_EXAMPLE,
            "datetime": "2031-04-06 09:33:00",
            "dirZone": "+08:00",
        },
    },
    "profection": {
        "human_name": "小限 / 年运推限",
        "required_fields": ["date", "time", "zone", "lat", "lon", "datetime", "dirZone"],
        "must_ask": ["本命出生时间地点", "小限目标年份/时间", "目标时区"],
        "target_fields": {
            "datetime": "小限目标时间，YYYY-MM-DD HH:mm:ss；缺省=此刻（上游 +08:00 钟面）。",
            "dirZone": "目标时区；缺省本命时区。",
            "profGrain/profStart": "[小限摘要]粒度 y/m/d（缺省 y）与起点 asc/sect/fortune/moon/mc（缺省 asc）。",
        },
        "output_contract": ["本命盘配置", "起盘信息", "小限摘要", "时段盘配置", "相位"],
        "example_payload": {
            **COMMON_ASTRO_PAYLOAD_EXAMPLE,
            "datetime": "2031-04-06 09:33:00",
            "dirZone": "+08:00",
        },
    },
    "pd": {
        "human_name": "本初方向 / 主限表",
        "required_fields": ["date", "time", "zone", "lat", "lon", "pdtype", "pdMethod", "pdTimeKey", "pdaspects"],
        "must_ask": ["本命出生时间地点", "主限方法", "时间钥匙", "相位列表"],
        "target_fields": {
            "pdtype": "坐标系：0=In Zodiaco（黄道，默认；宿命点 Vertex 应星行仅此坐标系核出），1=In Mundo（世俗/赤经空间）。",
            "pdMethod": "方位法（上游 13 法）：core_alchabitius（默认）/ horosa_legacy / placidus / regiomontanus / campanus / topocentric / meridian / porphyry / equal_ecliptic / equal_hour_circle / morinus / in_zodiaco_lon / in_zodiaco_abs。",
            "pdTimeKey": "度数换算（上游 26 项）：Ptolemy（默认）/ Naibod / TrueSolarArc / SymbolicSolarArc / Cardano / Umar / Wollner / Plantiko / Simmonite / SynodicYear / Kepler / Brahe / Kundig / SymbolicDegree / SymbolicYear / SymbolicMoon / SymbolicMonth / Quarterly / Quinary / Duodenary / Novenary / SelfMeasure / NaibodRA / AscendantArc / VanDam / User（配 pdTimeKeyCustom）。",
            "pdaspects": "纳入表格的相位角度，例如 [0, 60, 90, 120, 180]。",
            "pdDirect": "顺向开关（1 开/0 关，默认开）。",
            "pdConverse": "逆向开关（1 开/0 关，默认开；与顺向按年龄交错）。",
            "pdAntiscia": "映点/反映点作迫星（1 开/0 关，默认关）。",
            "pdTerms": "界(terms)边界作迫星（1 开/0 关，默认关）。",
            "pdYears": "推算年限上限（默认 100，上限 3000；>360 年出多圈复发行：同迫星/应星弧 +360°×n）。",
        },
        "output_contract": ["主限设置", "主限表格"],
        "example_payload": {
            **COMMON_ASTRO_PAYLOAD_EXAMPLE,
            "pdtype": 0,
            "pdMethod": "core_alchabitius",
            "pdTimeKey": "Ptolemy",
            "pdaspects": [0, 60, 90, 120, 180],
        },
    },
    "pdchart": {
        "human_name": "主限法盘",
        "required_fields": ["date", "time", "zone", "lat", "lon", "datetime", "dirZone", "pdtype", "pdMethod", "pdTimeKey"],
        "must_ask": ["本命出生时间地点", "主限盘目标时间", "主限方法", "时间钥匙"],
        "target_fields": {
            "datetime": "主限法盘目标时间，YYYY-MM-DD HH:mm:ss；缺省=主限表首条应期日期（UTC 墙钟、dirZone=+00:00），无则出生次日（上游同律）。",
            "dirZone": "目标时区（给了 datetime 时生效；缺省本命时区）。",
            "pdtype/pdMethod/pdTimeKey": "主限法盘算法设置（pdMethod/pdTimeKey 词表同 pd 工具：13 方位法、26 度数换算）。逆向用 direction='converse'。",
        },
        "output_contract": ["本命盘星与虚点", "主限法盘星体表格", "主限法盘相位"],
        "example_payload": {
            **COMMON_ASTRO_PAYLOAD_EXAMPLE,
            "datetime": "2031-04-06 09:33:00",
            "dirZone": "+08:00",
            "pdtype": 0,
            "pdMethod": "core_alchabitius",
            "pdTimeKey": "Ptolemy",
            "showPdBounds": 1,
        },
    },
    "zr": {
        "human_name": "黄道释放",
        "required_fields": ["date", "time", "zone", "lat", "lon"],
        "must_ask": ["本命出生时间地点", "是否指定释放起点/层级"],
        "target_fields": {
            "basePoint": "推运基点：Pars Fortuna 福点（缺省）/ Pars Spirit 等六希腊点 / Asc/Desc/MC/IC / 十二星座；取该点所在座起释。",
            "aiMode": "输出层级：l1_all（缺省）/ l2_in_l1 / l3_in_l2 / l4_in_l3，配 aiL1Idx/aiL2Idx/aiL3Idx（0 起）逐层钻取。",
            "startSign": "可选；直接指定起释星座（与 basePoint=星座同义）。",
        },
        "output_contract": ["起盘信息", "星盘信息", "基于X点推运", "当前时点", "方法说明"],
        "example_payload": {**COMMON_ASTRO_PAYLOAD_EXAMPLE},
    },
    "firdaria": {
        "human_name": "法达星限",
        "required_fields": ["date", "time", "zone", "lat", "lon"],
        "must_ask": ["本命出生时间地点", "是否沿用日夜与星阙默认排序"],
        "target_fields": {
            "date/time/zone/lat/lon": "本命信息；法达星限以本命盘日夜和星体顺序展开时间轴。",
        },
        "output_contract": ["法达星限时间轴"],
        "example_payload": {**COMMON_ASTRO_PAYLOAD_EXAMPLE},
    },
}


def _prompt_from_guidance(tool_name: str, ask_if_missing: list[dict[str, Any]], safe_defaults: list[dict[str, Any]]) -> str:
    """闸门追问文案（**双语**）。

    这段文本会被 agent 原样转给用户，在支持 elicitation 的客户端还会直接变成原生表单的标题——
    单中文会让非中文用户面对一整块看不懂的表单。技法名词保持中文（它们本就是专名），但每条指引
    都配英文，使任何语言的用户都知道「要我确认什么、怎么快速继续」。
    """
    if not ask_if_missing:
        return (
            "我还缺少这次调用所需的关键参数。请补充必要输入，或明确说明是否按星阙默认设置继续。\n"
            "I still need the key inputs for this call — please provide them, or say to continue with "
            "Xingque defaults."
        )
    lines = [
        f"调用 `{tool_name}` 前需要先确认这些会影响结果的设置：",
        f"Before running `{tool_name}`, please confirm these result-changing settings:",
    ]
    for index, item in enumerate(ask_if_missing[:6], start=1):
        question = str(item.get("question") or item.get("field") or "请补充这个参数。")
        options = item.get("options")
        if isinstance(options, list) and options:
            question = f"{question} 可选 / options：{' / '.join(str(option) for option in options)}"
        lines.append(f"{index}. {question}")
    if safe_defaults:
        defaults = "; ".join(f"{item.get('field')}={item.get('value')}" for item in safe_defaults[:5])
        lines.append(f"如果你想快速继续，也可以明确说“按星阙默认”，我会使用：{defaults}。")
        lines.append(f"To continue immediately, say “use Xingque defaults” and I will use: {defaults}.")
    return "\n".join(lines)


def _agent_recovery(
    *,
    tool_name: str,
    ask_if_missing: list[dict[str, Any]],
    safe_defaults: list[dict[str, Any]],
    do_not_assume: list[str],
    reason: str,
) -> dict[str, Any]:
    return {
        "must_ask_user": True,
        "reason": reason,
        "prompt_to_user": _prompt_from_guidance(tool_name, ask_if_missing, safe_defaults),
        "ask_if_missing": ask_if_missing,
        "safe_defaults": safe_defaults,
        "do_not_assume": do_not_assume,
        "retry_requires_one_of": [
            {"agent_confirmed_settings": True, "meaning": "Use after the user explicitly answered the clarification."},
            {"defaults_accepted": True, "meaning": "Use only after the user explicitly accepted Horosa/Xingque defaults."},
        ],
        "retry_should_include": ["clarification_notes"],
    }


def _policy(
    *,
    intent: str,
    required_context: list[str],
    ask_if_missing: list[dict[str, Any]],
    safe_defaults: list[dict[str, Any]] | None = None,
    do_not_assume: list[str] | None = None,
    output_contract: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "intent": intent,
        "must_have_context": required_context,
        "ask_if_missing": ask_if_missing,
        "safe_defaults": safe_defaults or [],
        "do_not_assume": do_not_assume or [],
        "output_contract": output_contract
        or [
            "Use ok=true result only.",
            "Read export_snapshot.export_text and export_snapshot.sections before explaining.",
            "Persist or report only through Horosa memory/report tools when requested.",
        ],
    }


SHENSHU_POLICY = _policy(
    intent="神数 (皇极经世/五兆/荆诀/神易数/鬼谷分定经)：以干支起数，只需日期(可含时间)即可起盘，不需经纬度。技法旋钮走 options（键表见 options_keys）。",
    required_context=["date (公历日期)", "time (可选，影响时柱)"],
    ask_if_missing=[
        {"field": "date", "question": "请提供起盘的公历日期（年月日）。"},
        {"field": "time", "question": "几点起盘？（可选；影响时柱，留空按 00:00 起）"},
    ],
    safe_defaults=[
        {"field": "time", "value": "00:00:00", "meaning": "未给时间时按子初起时柱"},
        {"field": "after23NewDay", "value": 1, "meaning": "23 点后归次日（星阙默认）"},
        {"field": "lateZiHourUseNextDay", "value": 1, "meaning": "晚子时时干按次日日干起（星阙默认）"},
    ],
    do_not_assume=["date"],
)

# v0.36.0 B3：神数五支此前共用 SHENSHU_POLICY，从不问性别/地点——而 `_run_shenshu_tool` 一直在转发它们，
# 铁板/邵子/演禽按性别分条文（演禽不读地点，live 实测），策天/张果按地点起盘：不问就是静默默认。
_GENDER_QUESTION = {"field": "gender", "question": "性别？（条文按男女分列）", "options": ["男", "女"], "values": [1, 0]}
_PLACE_QUESTION = {
    "field": "location",
    "question": "起盘地点（经纬度或城市）与时区？",
    "options": ["当前位置/客户端位置", "指定城市或经纬度"],
}
SHENSHU_GENDER_POLICY = _policy(
    intent="神数 (演禽/北极/南极)：以干支起数并按性别取条文/定大运顺逆；需日期(含时间更准)与性别。",
    required_context=["date (公历日期)", "time (可选，影响时柱)", "gender (性别)"],
    ask_if_missing=[*SHENSHU_POLICY["ask_if_missing"], _GENDER_QUESTION],
    safe_defaults=SHENSHU_POLICY["safe_defaults"],
    do_not_assume=["date", "gender"],
)
# sync311 F16：年/月柱走 kin_year_domain 权威四柱（立春界 + 定气月，按**时区**折算，kinastro_common
# authoritative_pillars / webtaixuansrv _zone_to_hours）——live 实测 1990-02-04 10:00 +08:00 与 -05:00 年柱
# 己巳↔庚午、月柱丁丑↔戊寅。时区缺省 +08:00 是后端兜底，不是用户的口径 → 要问。
_ZONE_QUESTION = {
    "field": "zone",
    "question": "出生/起盘地的时区？（年柱月柱按时区定立春与节气）",
    "options": ["+08:00 北京时间", "其它时区（如 -05:00 / Asia/Tokyo）"],
}
SHENSHU_ZONE_POLICY = _policy(
    intent="神数 (太玄筮法)：以起课时刻起筮（种子=起课时刻派生，同刻同卦），四柱按时区定立春/节气；需日期、时间与时区。",
    required_context=["date (公历日期)", "time", "zone (时区)"],
    ask_if_missing=[*SHENSHU_POLICY["ask_if_missing"], _ZONE_QUESTION],
    safe_defaults=SHENSHU_POLICY["safe_defaults"],
    do_not_assume=["date", "timezone"],
)
SHENSHU_GENDER_ZONE_POLICY = _policy(
    intent="神数 (铁板/邵子/蠢子数)：以权威四柱起数并按性别取条文；四柱按时区定立春/节气，需日期、时间、时区与性别。",
    required_context=["date (公历日期)", "time", "zone (时区)", "gender (性别)"],
    ask_if_missing=[*SHENSHU_POLICY["ask_if_missing"], _GENDER_QUESTION, _ZONE_QUESTION],
    safe_defaults=SHENSHU_POLICY["safe_defaults"],
    do_not_assume=["date", "gender", "timezone"],
)
SHENSHU_PLACE_POLICY = _policy(
    intent="神数 (策天飞星/张果星宗)：按出生时刻+地点起盘并按性别取用；需日期、时间、时区、地点与性别。",
    required_context=["date (公历日期)", "time", "zone (时区)", "lat/lon 或 gpsLat/gpsLon (地点)", "gender (性别)"],
    ask_if_missing=[*SHENSHU_POLICY["ask_if_missing"], _GENDER_QUESTION, _PLACE_QUESTION, {"field": "zone", "question": "时区偏移（如 +08:00）？"}],
    safe_defaults=SHENSHU_POLICY["safe_defaults"],
    do_not_assume=["date", "gender", "location", "timezone"],
)


ASTRO_BIRTH_POLICY = _policy(
    intent="Birth/event astrology chart calculation.",
    required_context=COMMON_BIRTH_FIELDS,
    ask_if_missing=[
        {"field": "date/time/place", "question": "请提供出生/事件的日期、时间、时区和地点。"},
        {
            "field": "hsys",
            "question": "宫制要用哪一种？（索引见上游表：1 是 Alcabitus，不是 Placidus）",
            "options": ["0 整宫制/Whole Sign（默认推荐）", "3 Placidus", "1 Alcabitus", "2 Regiomontanus", "4 Koch", "其他指定宫制（5–24：Vehlow/Polich Page/Sripati/MC等宫/Porphyry/Campanus/Equal/…/福点整宫制，全表见 options_keys.hsys）"],
            "values": [0, 3, 1, 2, 4, None],
        },
        {"field": "zodiacal", "question": "黄道体系要用哪一种？", "options": ["回归黄道（默认推荐）", "恒星黄道（需配 siderealAyanamsa）"], "values": [0, 1]},
        {
            "field": "siderealAyanamsa",
            "question": "若用恒星黄道，岁差(ayanāṃśa)取哪一制？（仅 zodiacal=1 时生效，缺省=lahiri）",
            "options": [
                "lahiri（默认）",
                "raman",
                "krishnamurti / KP",
                "fagan_bradley",
                "yukteshwar / true_citra / ss_revati 等（共 47 制，见 SIDEREAL_AYANAMSA_LABELS）",
            ],
            "values": ["lahiri", "raman", "krishnamurti", "fagan_bradley", None],
        },
        {"field": "tradition", "question": "是否需要传统占星扩展项？", "options": ["需要", "不需要/默认"]},
    ],
    safe_defaults=[
        {"field": "hsys", "value": 0, "meaning": "Whole Sign / 整宫制"},
        {"field": "zodiacal", "value": 0, "meaning": "Tropical / 回归黄道"},
        {"field": "siderealAyanamsa", "value": "lahiri", "meaning": "恒星黄道缺省 Lahiri（仅 zodiacal=1 生效）"},
        {"field": "ad", "value": 1, "meaning": "公历纪年"},
    ],
    do_not_assume=["birth time", "birthplace", "timezone"],
)

PREDICTIVE_POLICY = _policy(
    intent="Predictive astrology calculation based on a natal chart and a target time.",
    required_context=COMMON_BIRTH_FIELDS + ["target/prediction date or year"],
    ask_if_missing=[
        {"field": "natal data", "question": "请提供本命出生日期、时间、时区和地点。"},
        {"field": "target time", "question": "要推哪一年/哪一天/哪个事件时间？"},
        {"field": "technique settings", "question": "是否沿用星阙默认推运设置？", "options": ["沿用默认", "指定主限/释放/返照等参数"]},
    ],
    safe_defaults=[
        {"field": "hsys", "value": 0, "meaning": "Whole Sign / 整宫制"},
        {"field": "zodiacal", "value": 0, "meaning": "Tropical / 回归黄道"},
    ],
    do_not_assume=["target date/year", "birth time", "timezone"],
)

EVENT_METHOD_POLICY = _policy(
    intent="Event-time Chinese method pan calculation.",
    required_context=COMMON_LOCATION_FIELDS + ["question/topic"],
    ask_if_missing=[
        {"field": "date/time", "question": "是用当前时间，还是你要指定一个起盘时间？", "options": ["当前时间", "指定时间"]},
        {"field": "location", "question": "起盘地点用哪里？", "options": ["当前位置/客户端位置", "指定城市或经纬度"]},
        {"field": "question", "question": "这次主要问什么事？", "options": ["事业/财务", "感情/关系", "健康", "出行/失物/选择", "整体局势"]},
        {"field": "after23NewDay", "question": "23 点后是否按次日换日？", "options": ["按星阙默认", "23 点后换日", "23 点后不换日"], "values": [None, 1, 0]},
        {"field": "lateZiHourUseNextDay", "question": "晚子时（23-24点）时柱是否按次日日干起子时？", "options": ["按星阙默认（次日）", "按当日"], "values": [None, 0]},
    ],
    safe_defaults=[
        {"field": "ad", "value": 1, "meaning": "公历"},
        {"field": "after23NewDay", "value": 1, "meaning": _AFTER23_DEFAULT_MEANING},
    ],
    do_not_assume=["location for location-sensitive methods", "question context"],
)


def _progression_target_policy(
    *,
    intent: str,
    targets: list[dict[str, Any]],
    do_not_assume: list[str],
    extra_defaults: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """推运族专属策略工厂（v0.36.0 B3）：此前 vedicprog/jaynesprog/planetaryarc/planetaryages/extrareturns
    共用 ASTRO_BIRTH_POLICY——问宫制却从不问目标时刻/弧源，agent 只能静默默认。
    extra_defaults：该工具在上游的真实缺省（v3.11 同步：目标时刻/月长/速率等），如实写进 safe_defaults。"""
    return _policy(
        intent=intent,
        required_context=COMMON_BIRTH_FIELDS + [str(item.get("field")) for item in targets],
        ask_if_missing=[
            {"field": "natal data", "question": "请提供本命出生日期、时间、时区和地点。"},
            *targets,
            {"field": "technique settings", "question": "是否沿用星阙默认推运设置？", "options": ["沿用默认", "指定参数"]},
        ],
        safe_defaults=[
            {"field": "hsys", "value": 0, "meaning": "Whole Sign / 整宫制"},
            {"field": "zodiacal", "value": 0, "meaning": "Tropical / 回归黄道"},
            *(extra_defaults or []),
        ],
        do_not_assume=["birth time", "timezone", *do_not_assume],
    )


_TARGET_DATE_QUESTION = {"field": "targetDate/targetTime", "question": "推到哪一天？（targetDate YYYY-MM-DD，可加 targetTime；缺省=今天）"}
# F10（上游 AstroJaynesProgressions.js:37-39 / astroProgSnapshot.js:57-59）：目标日缺省今天（旧实现是出生日）。
_PROG_TARGET_DEFAULTS = [
    {"field": "targetDate", "value": "今天", "meaning": "缺省推到今日（本地日期，上游同律）"},
    {"field": "targetTime", "value": "12:00:00", "meaning": "目标时刻缺省正午"},
    {"field": "minorVariant", "value": "synodic", "meaning": "小推运月长=朔望月/年（上游 [Q-180] 缺省）"},
]
VEDICPROG_POLICY = _progression_target_policy(
    intent="恒星推运 / Vedic sidereal 二次推运：本命 + 目标日期。",
    targets=[_TARGET_DATE_QUESTION],
    do_not_assume=["target date"],
    extra_defaults=_PROG_TARGET_DEFAULTS,
)
JAYNESPROG_POLICY = _progression_target_policy(
    intent="赤纬推运 / Jayne：二次推运 + 赤纬平行，本命 + 目标日期。",
    targets=[_TARGET_DATE_QUESTION],
    do_not_assume=["target date"],
    extra_defaults=_PROG_TARGET_DEFAULTS,
)
PLANETARYARC_POLICY = _progression_target_policy(
    intent="行星弧向运：整盘按 arcSource 的二次推运弧推进，本命 + 弧源 + 目标时刻。",
    targets=[
        {
            "field": "arcSource",
            "question": "弧源用哪颗星？（月亮弧=Moon，太阳弧=Sun）",
            "options": ["Moon（默认·月亮弧）", "Sun（太阳弧）", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"],
            "values": ["Moon", "Sun", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"],
        },
        {"field": "datetime", "question": "推到哪个目标时刻？（datetime YYYY-MM-DD HH:mm:ss + dirZone）"},
    ],
    do_not_assume=["arcSource", "target datetime"],
    extra_defaults=[
        {"field": "datetime", "value": "明天此刻", "meaning": "缺省目标时刻=明天此刻（上游 AstroPlanetaryArc.js todayStr，与页面同律）"},
        {"field": "arcSource", "value": "Moon", "meaning": "月亮弧（上游缺省）"},
    ],
)
PLANETARYAGES_POLICY = _progression_target_policy(
    intent="行星年龄 / 托勒密人生七阶：本命 + 观察基准日。",
    targets=[{"field": "asOf", "question": "以哪一天为基准算当前所在阶段？（asOf YYYY-MM-DD，缺省=今天）"}],
    do_not_assume=["asOf"],
)
EXTRARETURNS_POLICY = _progression_target_policy(
    intent="多重回归（土星/木星/月交返照）应期表：本命 + 年表范围。",
    targets=[
        {
            "field": "timelineStartYear/timelineCount",
            "question": "日月返照年表从哪一年起、算几年？",
            "options": ["缺省（出生年起 10 年）", "指定起始年与年数"],
        }
    ],
    do_not_assume=["timeline range"],
)
# 上游 v3.11 星运四键：区间 / 起始年与年数 / 目标日 都会改结果（缺省取「今天」，不同日子调用结果不同）→ 必问或记录接受默认。
EPHEMERIS_POLICY = _progression_target_policy(
    intent="星历：本命盘地点与时区下，区间内行星入座/留逆/朔望弦/食相 + 行运触发本命点（上游缺省今日起 90 天）。",
    targets=[
        {"field": "startDate/endDate", "question": "查哪段区间？（startDate/endDate YYYY-MM-DD；缺省=今天起 90 天，上限 732 天）"},
        {
            "field": "includeTransits",
            "question": "是否列出行运触发本命点的时刻？",
            "options": ["列出（默认）", "不列"],
            "values": [True, False],
        },
    ],
    do_not_assume=["date window"],
)
RETURNTIMELINE_POLICY = _progression_target_policy(
    intent="回归轴：逐年太阳返照 + 该年首个月亮返照时刻与两盘上升（上游缺省今年起 12 年，年数上限 40）。",
    targets=[
        {
            "field": "startYear/count",
            "question": "从哪一年起、列几年？",
            "options": ["缺省（今年起 12 年）", "指定起始年与年数（1–40）"],
        }
    ],
    do_not_assume=["year range"],
)
PRENATALSYZYGY_POLICY = _progression_target_policy(
    intent="产前朔望：自出生时刻回溯最近的朔/望，取度 + 以该时刻、出生地排盘（只需本命数据；出生时刻决定取哪一次朔望）。",
    targets=[],
    do_not_assume=["birth date/time"],
)
PROG_POLICY = _progression_target_policy(
    intent="二次推运（回归黄道）：二次/三次/小推运位置 + 与本命相位，本命 + 目标日期（上游缺省今天 12:00）。",
    targets=[
        _TARGET_DATE_QUESTION,
        {
            "field": "minorVariant",
            "question": "小推运月长按哪种算？",
            "options": ["synodic 朔望月每年（默认）", "sidereal 恒星月每年", "engine 引擎历史值（≈无推进）"],
            "values": ["synodic", "sidereal", "engine"],
        },
    ],
    do_not_assume=["target date"],
)

PERSIANDIRECTED_POLICY = _progression_target_policy(
    intent="波斯向运：黄经象征向运应期表（速率/方向/应期年数驱动主表与指定日期盘）。",
    targets=[
        {
            "field": "rateKey",
            "question": "向运速率？",
            "options": ["波斯 1°/年（默认）", "Prophected 30°/年", "Naibod 59′08″/年"],
            "values": ["persian", "prophected", "naibod"],
        },
        {"field": "direction", "question": "向运方向？", "options": ["顺向（默认）", "逆向 Converse"], "values": ["direct", "converse"]},
    ],
    do_not_assume=["rateKey", "direction"],
    extra_defaults=[
        {"field": "rateKey", "value": "persian", "meaning": "波斯 1°/年（上游缺省）"},
        {"field": "direction", "value": "direct", "meaning": "顺向（上游缺省）"},
        {"field": "maxYears", "value": 90, "meaning": "应期年数（上游齿轮 50/90/120/150/200）"},
    ],
)
BALBILLUS_POLICY = _progression_target_policy(
    intent="Balbillus 129 年系统（旺距削减主限）：起始星 / 年制 / 距离口径改主限铺排。",
    targets=[{"field": "technique settings", "question": "起始星/年制/距离口径是否沿用星阙默认？", "options": ["沿用默认（太阳·回归年·最近角距）", "指定参数"]}],
    do_not_assume=[],
    extra_defaults=[
        {"field": "startPlanet", "value": "Sun", "meaning": "自太阳起（上游缺省）"},
        {"field": "yearType", "value": "solar", "meaning": "回归年 365.2422 日"},
        {"field": "mode", "value": "nearest", "meaning": "最近角距"},
    ],
)
TRIPLICITYRULERS_POLICY = _progression_target_policy(
    intent="三分主星推运：当值光体三分主星分掌人生阶段（体系/划分法/寿命基准可调）。",
    targets=[{"field": "technique settings", "question": "三分体系/划分法/寿命基准是否沿用星阙默认？", "options": ["沿用默认（随本盘三分体系·三分·75 岁）", "指定参数"]}],
    do_not_assume=[],
    extra_defaults=[
        {"field": "system", "value": "随本盘 triplicity，否则 Dorothean", "meaning": "三分体系（上游 [Q-187/T-111] 同序）"},
        {"field": "division", "value": "thirds", "meaning": "三分 0–25/25–50/50–75"},
        {"field": "lifespan", "value": 75, "meaning": "寿命基准（30–120）"},
    ],
)
KEYPOINTS_POLICY = _progression_target_policy(
    intent="数字相位推运（120 关键点）：释放点（身=月亮 / 命=上升）改全部激活年。",
    targets=[{"field": "mode", "question": "释放点？", "options": ["身·月亮起（默认）", "命·上升起"], "values": ["soul", "body"]}],
    do_not_assume=["mode"],
    extra_defaults=[{"field": "mode", "value": "soul", "meaning": "身（月亮起，上游缺省）"}],
)


def _predictive_policy_with_defaults(extra_defaults: list[dict[str, Any]]) -> dict[str, Any]:
    """目标时刻型推运（返照/小限/太阳弧/主限/黄道释放）：共用 PREDICTIVE_POLICY 的问题，safe_defaults 写上游真实缺省。"""
    policy = deepcopy(PREDICTIVE_POLICY)
    policy["safe_defaults"] = [*policy["safe_defaults"], *extra_defaults]
    return policy


# F19（上游 aiAnalysisContext.js:2673-2760 / AstroPrimaryDirectionChart.js:454）。
_RETURN_DEFAULTS = [
    {"field": "datetime", "value": "今年生日时刻", "meaning": "当年+出生月日+出生时分（上游 [挂载自检 F-17]）"},
    {"field": "dirLat/dirLon", "value": "出生地", "meaning": "返照地缺省=本命经纬（异地返照请显式给）"},
    {"field": "dirZone", "value": "本命时区", "meaning": "返照地时区缺省=本命时区"},
]
_NOW_TARGET_DEFAULTS = [
    {"field": "datetime", "value": "此刻", "meaning": "缺省=当前时刻（上游 new DateTime() 钟面 +08:00）"},
    {"field": "dirZone", "value": "本命时区", "meaning": "目标时区缺省=本命时区"},
]
SOLARRETURN_POLICY = _predictive_policy_with_defaults(_RETURN_DEFAULTS)
PROFECTION_POLICY = _predictive_policy_with_defaults([
    *_NOW_TARGET_DEFAULTS,
    {"field": "profGrain", "value": "y", "meaning": "[小限摘要] 年小限（上游缺省）"},
    {"field": "profStart", "value": "asc", "meaning": "[小限摘要] 自上升起数（上游缺省）"},
])
SOLARARC_POLICY = _predictive_policy_with_defaults(_NOW_TARGET_DEFAULTS)
PD_POLICY = _predictive_policy_with_defaults([
    {"field": "pdMethod", "value": "core_alchabitius", "meaning": "上游缺省方位法（共 13 法）"},
    {"field": "pdTimeKey", "value": "Ptolemy", "meaning": "上游缺省度数换算（共 26 项）"},
])
PDCHART_POLICY = _predictive_policy_with_defaults([
    {"field": "datetime", "value": "主限表首条应期", "meaning": "过滤后首条主限行日期（UTC、dirZone=+00:00），无则出生次日"},
    {"field": "pdMethod", "value": "core_alchabitius", "meaning": "上游缺省方位法"},
    {"field": "pdTimeKey", "value": "Ptolemy", "meaning": "上游缺省度数换算"},
])
ZR_POLICY = _predictive_policy_with_defaults([
    {"field": "basePoint", "value": "Pars Fortuna", "meaning": "自福点所在座起释（上游缺省）"},
    {"field": "aiMode", "value": "l1_all", "meaning": "输出全部 L1 期（上游缺省）"},
])
# 盘面族（chart/chart13/chart12/hellen_chart/draconic）：[寿命格局] 取主法（F15，上游 AstroLifespan.js METHODS）。
ASTRO_CHART_POLICY = deepcopy(ASTRO_BIRTH_POLICY)
ASTRO_CHART_POLICY["safe_defaults"] = [
    *ASTRO_CHART_POLICY["safe_defaults"],
    {"field": "lifespanMethod", "value": "ptolemy", "meaning": "[寿命格局] 托勒密取主法（上游缺省；alcabitius/dorotheus 可选）"},
]


# 闸问题允许没有 options 的字段（自由文本/复合输入）；新问题要么带 options 要么在这里登记（tests/test_gate_policies.py 守）。
FREE_TEXT_GATE_FIELDS: frozenset[str] = frozenset({
    "date", "time", "date/time", "date/time/place", "date/time/gender", "datetime", "targetDate/targetTime", "asOf",
    "startDate/endDate", "conditions", "topic", "question", "natal data", "target time", "location", "askEvent",
    "birth data", "year", "name", "technique", "content", "category/key", "rectifyEvents", "guaDate/guaYearGanZi",
    "q", "query", "pillars", "fromYear", "nums / date-time", "qiZhi / date-time", "dayGan/dayZhi", "cast-input", "cast-input + date/time",
    "school-params", "event", "relocLat/relocLon", "inner/outer", "zone", "target technique",
})


# [Q-452 裁决 A / Q-453] 择日十技法 + 天星的快照「命中清单」两旋钮（上游 utils/zeriSnapshotPrefs.js 缺省）。
ZERI_SNAPSHOT_SAFE_DEFAULTS: list[dict[str, Any]] = [
    {"field": "zeriSnapshotMaxRows", "value": 60, "meaning": "快照命中清单最多列 60 行（可调 10–500；上游全局缺省）"},
    {"field": "zeriSnapshotExplainRows", "value": 3, "meaning": "清单前 3 行各附一棵判读树（设定 vs 实际 ✓✗，与扫描同源；可调 0–20，0=不附；上游全局缺省）"},
]

# ── 三式口径（sanshi chunk，上游 v3.11）──────────────────────────────────────────────────────
# 「星阙默认」必须字面等于上游缺省：奇门起局法缺省 = DunJiaMain.js:128 DEFAULT_OPTIONS.qijuMethod 'zhirun'（置闰）。
_QIMEN_QIJU_QUESTION: dict[str, Any] = {
    "field": "qijuMethod",
    "question": "起局方式？星阙默认为置闰（zhirun）。",
    "options": ["置闰（星阙默认）", "拆补", "茅山", "无闰", "阴盘报数（需 shuziReportNumber）"],
    "values": ["zhirun", "chaibu", "maoshan", "wurun", "shuzi"],
}
_QIMEN_SAFE_DEFAULTS: list[dict[str, Any]] = [
    {"field": "qijuMethod", "value": "zhirun", "meaning": "星阙默认（DunJiaMain DEFAULT_OPTIONS）：置闰"},
    {"field": "paiPanType", "value": 3, "meaning": "时家奇门（星阙默认）"},
    {"field": "timeAlg", "value": 0, "meaning": "星阙默认：真太阳时（ken 按真太阳时分量起局，时柱与九宫同一时辰）"},
    {"field": "sex", "value": 1, "meaning": "星阙默认；涉及命式时应先问"},
    {"field": "after23NewDay", "value": 1, "meaning": _AFTER23_DEFAULT_MEANING + "（不传即不发送，ken/农历前置按后端缺省 1）"},
]
# 大六壬起课法全 26 法（键序 = 上游 LiuRengMain.js:3860 QI_METHODS；tests/test_sync311_sanshi.py 对 vendored 表锚定）。
LIURENG_CAST_METHODS: tuple[tuple[str, str], ...] = (
    ("zheng", "正时正将"), ("bake2", "月建加太岁"), ("bake3", "太岁加月建"), ("bake4", "月建加日干"),
    ("bake5", "岁干加正时"), ("bake6", "月将加日干"), ("bake7", "月将加太岁"), ("bake8", "太岁加月将"),
    ("bake9", "月将加本命"), ("bake10", "月将加行年"), ("bake11", "太岁加本命"), ("bake12", "太岁加行年"),
    ("tsjs", "太岁加时"), ("yjjs", "月建加时"), ("xnjs", "行年加时"), ("bmjs", "本命加时"),
    ("cike1", "次客·一筹"), ("cike2", "次客·二筹"), ("cike3", "次客·三筹"),
    ("alnr", "年日对齐"), ("alns", "年时对齐"), ("alyr", "月日对齐"), ("alys", "月时对齐"),
    ("xuanshi", "选时"), ("yanshu", "演数"), ("baoshu", "报数"),
)
_LIURENG_OPTIONS_KEYS = (
    "options（起课口径；缺省 = 上游 LIURENG_PAGE_SETTINGS 出厂值，认不出的值报 tool.liureng_invalid_option）："
    "castMethod 起课法 " + " / ".join(f"{k}={v}" for k, v in LIURENG_CAST_METHODS) + "（缺省 zheng；"
    "xuanshi 需 xuanShiZhi=事发时地支；yanshu/baoshu 需 yanShuNum=整数；bake9-12/xnjs/bmjs 用本命/行年支）；"
    "yueJiangMethod zhongqi 中气过宫(缺省)/jieqi 节气换将/richan 日躔含岁差；"
    "fenZhouYe chenhun 晨昏(缺省)/maoyou 卯酉/yinshen 寅申；"
    "seHaiMethod app(缺省)/standard/mengzhongji；seHaiBoundary app(缺省)/both/neither；shiRuKe false(缺省)/true；"
    "yearShenShaSort sanyuan(缺省)/suigui；yinyangSystem danmu 旦暮(缺省)/yinyang 阳阴系(六壬法贵人甲乙丙辛壬癸昼夜互换)；"
    "tuWangShuai siji(缺省)/huotu；wuxing 十二长生五行(缺省=日干五行)；"
    "timeAlg 0 真太阳时(缺省)/1 直接时间（只作用于 /liureng/gods 四柱与神煞，课盘占时同上游取星历农历）。"
    "顶层 guirengType：0 六壬法 / 1 遁甲法 / 2 星占法(缺省) / 3 甲戊兼牛羊 / 4 干合阳阴贵。"
)
_SANSHI_OPTIONS_KEYS: dict[str, str] = {
    "qimen": (
        "options（盘面口径；缺省 = 上游 DunJiaMain DEFAULT_OPTIONS，认不出报 tool.qimen_invalid_option）："
        "qijuMethod zhirun 置闰(缺省)/chaibu 拆补/maoshan 茅山/wurun 无闰/shuzi 阴盘报数(需 shuziReportNumber)；"
        "paiPanType 3 时家(缺省)/0 年家/1 月家/2 日家/4 刻家/6 日家·金函；school 转盘(缺省)/飞盘/混合；"
        "timeAlg 0 真太阳时(缺省)/1 直接时间；zhiShiType 0/1/2；zhirunLeapDays 9；godsPreset baihu_xuanwu；"
        "jiGongMode kun；anGanMode off；kongMarkBoth；shiftPalace + shiftZhiFuMode follow/recalc；kongMode/yimaMode day/time 等。"
        "路由同上游 isQimenLocalRoute：paiPanType∉{3,5}、飞盘/混合、shuzi，或 zhiShiType/zhirunLeapDays/godsPreset/"
        "jiGongMode/anGanMode/kongMarkBoth/shiftZhiFuMode=recalc 任一非缺省 → 本地 calcDunJia（不打 ken，data.route.local=true，"
        "compute_sources.pan=local_route_calcDunJia）；其余由 ken 算盘。"
    ),
    "qimenzeri": "options 同 qimen（扫描与展示盘吃同一份已校验口径，起局法缺省 zhirun）。",
    "taiyi": (
        "options：style 3 时计(缺省，0 年计/1 月计/2 日计/4 分计/5 命法)；tn 0 统宗(缺省)/1 金镜/2 淘金歌/3 太乙局；"
        "timeBasis direct 直接时间=钟表时(缺省)/trueSolar 真太阳时（ken 按 nongli.birth 真太阳时起局，四柱随之）；"
        "gameTheory 0/1；school 流派六轴对象 {jishen 逆/顺, wenchang 重留/无重留, keJianChen 加一/无加一, "
        "sanji 淘金歌/金镜, youshen 顺/逆, shijiCoord 九宫/十六神}（缺省各轴 default=从盘；也认 options 里平铺六轴键）。"
        "顶层 timeAlg 只影响农历前置显示，不改太乙起局。"
    ),
    "taiyizeri": "school：顶层流派六轴对象（同 taiyi options.school），扫描与展示盘同用；认不出的轴/值报错。",
    "jinkou": (
        "options：diFen auto=占时支(缺省)/地支；yueJiang、zhanShi auto(缺省)/地支；wuxing 十二长生五行(缺省日干五行)；"
        "guirengType 0 六壬法(缺省)；流派五键 schoolYueJiang zhongqi(缺省)/jiaojie、schoolGuiTable shiwu(缺省)/liuren、"
        "schoolGuiPan di(缺省)/tian、panShi yang(缺省)/yin、soilChangSheng shen(缺省)/yin；timeBasis direct(缺省)/trueSolar。"
        "路由同上游：五键全缺省且两源日柱对齐 → ken(kinjinkou) 盘；任一非缺省 → 本地 buildJinKouData"
        "（compute_sources.jinkou=local_route_buildJinKouData），此时 timeBasis 无效并进 warnings（上游置灰）。"
    ),
    "liureng_gods": _LIURENG_OPTIONS_KEYS,
    "liureng_runyear": _LIURENG_OPTIONS_KEYS + "行年盘：date/time=问测人出生，guaDate/guaTime=起课时刻（课盘按起课时刻起）。",
    "sanshiunited": (
        "qimen_options 同 qimen options；taiyi_options 同 taiyi options（上游键 taiyiTimeBasis 亦可放顶层）；"
        "liureng_options 同 liureng_gods options（castMethod 锁 zheng 正时正将，同上游；timeAlg 用顶层共享值）。"
    ),
}

TOOL_GUIDANCE: dict[str, dict[str, Any]] = {
    "export_registry": _policy(
        intent="Inspect Xingque export registry.",
        required_context=[],
        ask_if_missing=[{"field": "technique", "question": "要查看全部导出 registry，还是某个技法？", "options": ["全部", "指定 technique"]}],
        safe_defaults=[{"field": "technique", "value": None, "meaning": "return all techniques"}],
    ),
    "export_parse": _policy(
        intent="Parse Xingque export text.",
        required_context=["technique", "content"],
        ask_if_missing=[
            {"field": "technique", "question": "这段导出正文属于哪个 technique？"},
            {"field": "content", "question": "请提供完整星阙 AI 导出正文。"},
            {"field": "selected_sections", "question": "是否只解析指定 section？", "options": ["全部解析", "指定 section"]},
        ],
        do_not_assume=["technique when content is ambiguous"],
    ),
    "knowledge_registry": _policy(
        intent="List bundled hover knowledge.",
        required_context=[],
        ask_if_missing=[{"field": "domain", "question": "要看全部知识域，还是只看 astro/liureng/qimen？", "options": ["全部", "astro", "liureng", "qimen"]}],
        safe_defaults=[{"field": "domain", "value": None, "meaning": "return all domains"}],
    ),
    "knowledge_read": _policy(
        intent="Read bundled Xingque hover knowledge.",
        required_context=["domain", "category", "key or structured lookup fields"],
        ask_if_missing=[
            {"field": "domain", "question": "要读哪个知识域？", "options": ["astro", "liureng", "qimen"]},
            {"field": "category/key", "question": "请给出分类和 key，例如 planet/日、shen/子、door/休门。"},
        ],
        do_not_assume=["category", "key"],
    ),
    "qimen": _policy(
        intent="奇门遁甲起盘。可选 faRelatedPeople=[{name, yearGan|birth}]（法奇门相关人员：提供后[八门化气大阵]段逐人多出「生年干·姓名」保护行；birth 为公历生日时按立春界自动解析年干；缺省不出该类行）。",
        required_context=COMMON_LOCATION_FIELDS + ["question/topic"],
        ask_if_missing=[
            {"field": "date/time", "question": "奇门用当前时间还是指定时间？", "options": ["当前时间", "指定时间"]},
            {"field": "location", "question": "起盘地点用哪里？", "options": ["当前位置/客户端位置", "指定城市或经纬度"]},
            {"field": "question", "question": "这局主要问什么事？"},
            _QIMEN_QIJU_QUESTION,
            {"field": "sex", "question": "如果是命盘/人事局，请确认性别；纯事件局可沿用默认。", "options": ["男", "女", "事件局/不指定"]},
        ],
        safe_defaults=_QIMEN_SAFE_DEFAULTS,
        do_not_assume=["question", "location", "non-default qijuMethod"],
    ),
    "qimenzeri": _policy(
        intent=(
            "奇门择日「找局」：在一段时间窗内扫出满足奇门条件树的时辰，并附命中首刻的完整奇门盘"
            "（17 段奇门 + [择日搜索配置]/[择日条件]/[命中时辰]）。"
            "\n算权：**展示盘与普通 qimen 工具同源同路由**（缺省 ken /qimen/pan；本地路由口径时为本地 calcDunJia，"
            "以 compute_sources.pan 为准），扫描与展示盘吃同一份已校验口径；"
            "**区间搜索用本地引擎**——ken 无区间扫描端点，一个月窗口走 HTTP 是约 44,000 次往返；"
            "上游对本地排盘与后端做过 42,731 点 0 差 parity 锚。结果里 compute_sources 逐项写明。"
            "\n条件树形状：组 {kind:'group', joiner:'all'|'any'|'xor', negate?, children:[…]}；"
            "叶 {type:'<键>', params:{…}}。常用条件类键（完整表见 vendored qimenConditionTypes）："
            "pattern_ji/pattern_xiong（格局，params.names 必填）、tian_gan/di_gan（天/地盘干）、"
            "door（八门）、star（九星）、god（八神）、palace_flag（宫位标记）、men_gong_relation（门宫关系）、"
            "zhifu/zhishi（值符值使）、ju_info（局象：dun/juShu/sanYuan 至少给一项）。"
        ),
        required_context=COMMON_LOCATION_FIELDS + ["搜索窗 startDate/endDate", "择日条件 conditions", "用事主题"],
        ask_if_missing=[
            {"field": "startDate/endDate", "question": "要在哪段时间里找日子？（起止日期）"},
            {"field": "conditions", "question": "择日要满足什么条件？（如某吉格出现、某门某宫等）"},
            {"field": "location", "question": "起盘地点用哪里？", "options": ["当前位置/客户端位置", "指定城市或经纬度"]},
            {"field": "topic", "question": "这次择日是为什么事？（搬家/开业/婚嫁…）"},
            _QIMEN_QIJU_QUESTION,
        ],
        safe_defaults=[
            *_QIMEN_SAFE_DEFAULTS,
            {"field": "maxSpanDays", "value": 92, "meaning": "搜索窗上限；更长请分段，否则 JS 引擎会超时"},
            {"field": "options", "value": "扫描口径", "meaning": "展示盘跟随扫描口径：顶层与 options 合并（options 优先）后整包回写展示盘（上游 QimenZeriMain.onPickInterval）"},
            *ZERI_SNAPSHOT_SAFE_DEFAULTS,
        ],
        do_not_assume=["搜索时间窗", "择日条件", "location", "non-default qijuMethod"],
        output_contract=(
            "intervals 为本地引擎扫出的命中时辰（含 pick/pickEnd 边界安全时刻）；pan 为展示盘（算源见 "
            "compute_sources.pan：kinqimen 或本地路由的 local_route_calcDunJia），"
            "起于 intervals[0].pick。零命中时 [命中时辰] 段仍会出现并写明「时间段内无满足条件的时辰」，"
            "不是缺段。切勿把本地搜索结果说成 ken 算出的。"
        ),
    ),
    "huanglizeri": _policy(
        intent=(
            "黄历择吉：在一段时间窗内扫出满足条件树的日，并附命中首刻的完整黄历日课 10 段"
            "（[择吉搜索配置]/[择吉条件]/[命中日段]）。"
            "\n算权：**区间搜索由本地 vendored 通书引擎计算**；"
            "**展示盘按 huangli 自己的算源铸**（与直接调该工具逐字同段）；"
            "结果里 compute_sources 逐项写明，切勿把搜索结果说成别的引擎算的。"
            "\n日粒度：命中的是整**日**，不是时辰。通书五流派口径由 school 决定，结果敏感。"
            "\n条件树形状：组 {kind:'group', joiner:'all'|'any'|'xor', negate?, children:[…]}；"
            "叶 {kind:'leaf', type:'<键>', negate?, params:{…}}。条件类键（引擎自带词表，非本文件手抄）："
            "yi_has（宜含事项） / ji_not（忌避事项） / jianchu（建除十二神） / tianshen_dao（黄黑道） / zhixiu（值宿(廿八宿)） / jishen_has（吉神宜趋） / xiongsha_not（凶煞回避） / nine_star（九星值日） / chong_shengxiao（冲煞生肖） / day_ganzhi（日干支） / nayin_wuxing（日纳音五行） / liuyao（六曜）；…共 26 类，完整表见 vendored huangliZeriConditionTypes。"
        ),
        required_context=COMMON_LOCATION_FIELDS + ["搜索窗 startDate/endDate", "择日条件 conditions", "用事主题"],
        ask_if_missing=[
            {"field": "startDate/endDate", "question": "要在哪段时间里找？（起止日期）"},
            {"field": "conditions", "question": "择日要满足什么条件？"},
            {"field": "location", "question": "起盘地点用哪里？", "options": ["当前位置/客户端位置", "指定城市或经纬度"]},
            {"field": "topic", "question": "这次择日是为什么事？（搬家/开业/婚嫁…）"},
        ],
        safe_defaults=[
            {"field": "maxSpanDays", "value": 366, "meaning": "搜索窗上限；更长请分段"},
            *ZERI_SNAPSHOT_SAFE_DEFAULTS,
        ],
        do_not_assume=["搜索时间窗", "择日条件", "location"],
        output_contract=(
            "intervals 是命中区间（含 pick/pickEnd 边界安全时刻，取盘请用 pick 而非 start——"
            "start 会落到时辰边界的另一侧）。零命中时三段仍会出现并写明范围内无满足条件的时段，不是缺段。"
        ),
    ),
    "bazizeri": _policy(
        intent=(
            "八字择时：在一段时间窗内扫出满足条件树的时辰，并附命中首刻的完整八字盘（四柱/大运/神煞/五行力量/格局）"
            "（[择时搜索配置]/[择时条件]/[命中时段]）。"
            "\n算权：**区间搜索由本地 vendored 八字引擎计算**；"
            "**展示盘按 bazi_birth 自己的算源铸**（与直接调该工具逐字同段）；"
            "结果里 compute_sources 逐项写明，切勿把搜索结果说成别的引擎算的。"
            "\n起局三开关（timeAlg/after23NewDay/lateZiHourUseNextDay）顶层与 options 双读，options 优先；真太阳时会改时支，改它命中集就变。"
            "\n条件树形状：组 {kind:'group', joiner:'all'|'any'|'xor', negate?, children:[…]}；"
            "叶 {kind:'leaf', type:'<键>', negate?, params:{…}}。条件类键（引擎自带词表，非本文件手抄）："
            "day_ganzhi（日柱干支） / hour_ganzhi（时柱干支） / month_year_gz（年月柱干支） / zhi_relation（支间关系） / gan_wuhe（天干五合） / sanhe_ju（地支三合局） / shensha_has（吉神在柱） / shensha_not（凶煞回避） / nayin_wuxing（柱纳音五行） / changsheng（日干长生态） / xunkong（旬空） / wuxing_day（日主五行）；…共 26 类，完整表见 vendored baziZeriConditionTypes。"
        ),
        required_context=COMMON_LOCATION_FIELDS + ["搜索窗 startDate/endDate", "择日条件 conditions", "用事主题"],
        ask_if_missing=[
            {"field": "startDate/endDate", "question": "要在哪段时间里找？（起止日期）"},
            {"field": "conditions", "question": "择日要满足什么条件？"},
            {"field": "location", "question": "起盘地点用哪里？", "options": ["当前位置/客户端位置", "指定城市或经纬度"]},
            {"field": "topic", "question": "这次择日是为什么事？（搬家/开业/婚嫁…）"},
        ],
        safe_defaults=[
            {"field": "maxSpanDays", "value": 92, "meaning": "搜索窗上限；更长请分段"},
            {"field": "options", "value": {"timeAlg": 0, "after23NewDay": 1, "lateZiHourUseNextDay": 1, "godKeyPos": "年", "phaseType": 0}, "meaning": "八字择时页出厂扫描口径（BaziZeriMain.js:80），调用方未给的键以此打底；展示盘（bazi_birth）同跟这五键"},
            *ZERI_SNAPSHOT_SAFE_DEFAULTS,
        ],
        do_not_assume=["搜索时间窗", "择日条件", "location"],
        output_contract=(
            "intervals 是命中区间（含 pick/pickEnd 边界安全时刻，取盘请用 pick 而非 start——"
            "start 会落到时辰边界的另一侧）。零命中时三段仍会出现并写明范围内无满足条件的时段，不是缺段。"
        ),
    ),
    "taiyizeri": _policy(
        intent=(
            "太乙择时：在一段时间窗内扫出满足条件树的时辰，并附命中首刻的完整太乙盘（十六宫/十精/分野）"
            "（[择时搜索配置]/[择时条件]/[命中时段]）。"
            "\n算权：**区间搜索由本地 vendored 太乙引擎计算**；"
            "**展示盘按 taiyi 自己的算源铸**（与直接调该工具逐字同段）；"
            "结果里 compute_sources 逐项写明，切勿把搜索结果说成别的引擎算的。"
            "\n太乙时基是**钟表时**（上游口径，与后端 kentang 太乙一致），故 timeAlg 在本技法不改盘。"
            "\n条件树形状：组 {kind:'group', joiner:'all'|'any'|'xor', negate?, children:[…]}；"
            "叶 {kind:'leaf', type:'<键>', negate?, params:{…}}。条件类键（引擎自带词表，非本文件手抄）："
            "yinyang_ju（阴阳遁） / ju_num（局数） / taiyi_gong（太乙落宫） / wenchang_gong（文昌(天目)落宫） / shiji_gong（始击落宫） / jishen_gong（计神/合神落宫） / youshen_gong（游神落宫(五福/大游/小游)） / geju_kind（格局(掩迫关囚格对提挟击)） / victory_side（主客胜负） / suan_range（主客算区间） / suan_parity（算数阴阳(奇偶)） / dajiang_gong（主客大将宫）；…共 24 类，完整表见 vendored taiyiZeriConditionTypes。"
        ),
        required_context=COMMON_LOCATION_FIELDS + ["搜索窗 startDate/endDate", "择日条件 conditions", "用事主题"],
        ask_if_missing=[
            {"field": "startDate/endDate", "question": "要在哪段时间里找？（起止日期）"},
            {"field": "conditions", "question": "择日要满足什么条件？"},
            {"field": "location", "question": "起盘地点用哪里？", "options": ["当前位置/客户端位置", "指定城市或经纬度"]},
            {"field": "topic", "question": "这次择日是为什么事？（搬家/开业/婚嫁…）"},
        ],
        safe_defaults=[
            {"field": "maxSpanDays", "value": 92, "meaning": "搜索窗上限；更长请分段"},
            {"field": "options", "value": {"tn": 0}, "meaning": "太乙择时页出厂扫描口径（TaiyiZeriMain.js:47）；展示盘同跟 tn/sex 与日界（缺省 0 = 扫描引擎缺省）"},
            {"field": "school", "value": "六轴全 default", "meaning": "星阙默认：从盘；给了对象则扫描与展示盘同用"},
            *ZERI_SNAPSHOT_SAFE_DEFAULTS,
        ],
        do_not_assume=["搜索时间窗", "择日条件", "location"],
        output_contract=(
            "intervals 是命中区间（含 pick/pickEnd 边界安全时刻，取盘请用 pick 而非 start——"
            "start 会落到时辰边界的另一侧）。零命中时三段仍会出现并写明范围内无满足条件的时段，不是缺段。"
        ),
    ),
    "ziweizeri": _policy(
        intent=(
            "紫微择时：在一段时间窗内扫出满足条件树的时辰，并附命中首刻的完整紫微斗数盘（十二宫方盘）"
            "（[择时搜索配置]/[择时条件]/[命中时段]）。"
            "\n算权：**区间搜索由本地 vendored 紫微引擎计算**；"
            "**展示盘按 ziwei_birth 自己的算源铸**（与直接调该工具逐字同段）；"
            "结果里 compute_sources 逐项写明，切勿把搜索结果说成别的引擎算的。"
            "\n格局条件含**破格**判定；宫干四化与来因宫都可作条件。"
            "\n条件树形状：组 {kind:'group', joiner:'all'|'any'|'xor', negate?, children:[…]}；"
            "叶 {kind:'leaf', type:'<键>', negate?, params:{…}}。条件类键（引擎自带词表，非本文件手抄）："
            "wuxing_ju（五行局） / ming_gong_zhi（命宫地支） / ming_zhu_xing（命宫正曜） / shen_zhu_xing（身宫正曜） / ming_changsheng（命宫长生态） / star_in_gong（星落宫名） / star_in_zhi（星落地支） / star_tong_gong（两星同宫） / sihua_star（生年四化为星） / sihua_in_gong（生年四化入宫） / sihua_dui_ming（四化会命宫(同宫/对照)） / star_brightness（星曜亮度）；…共 28 类，完整表见 vendored ziweiZeriConditionTypes。"
        ),
        required_context=COMMON_LOCATION_FIELDS + ["搜索窗 startDate/endDate", "择日条件 conditions", "用事主题"],
        ask_if_missing=[
            {"field": "startDate/endDate", "question": "要在哪段时间里找？（起止日期）"},
            {"field": "conditions", "question": "择日要满足什么条件？"},
            {"field": "location", "question": "起盘地点用哪里？", "options": ["当前位置/客户端位置", "指定城市或经纬度"]},
            {"field": "topic", "question": "这次择日是为什么事？（搬家/开业/婚嫁…）"},
            {"field": "gender", "question": "紫微择时按男命还是女命起盘？（扫描按性别起命盘，影响阴阳局与宫位条件）", "options": ["男（星阙默认）", "女"]},
        ],
        safe_defaults=[
            {"field": "maxSpanDays", "value": 92, "meaning": "搜索窗上限；更长请分段"},
            {"field": "options", "value": {"timeAlg": 1, "gender": 1}, "meaning": "紫微择时页出厂扫描口径（ZiweiZeriMain.js:72：钟表时、男）；顶层 gender/timeAlg 与 options 双读，展示盘（ziwei_birth）同跟"},
            *ZERI_SNAPSHOT_SAFE_DEFAULTS,
        ],
        do_not_assume=["搜索时间窗", "择日条件", "location"],
        output_contract=(
            "intervals 是命中区间（含 pick/pickEnd 边界安全时刻，取盘请用 pick 而非 start——"
            "start 会落到时辰边界的另一侧）。零命中时三段仍会出现并写明范围内无满足条件的时段，不是缺段。"
        ),
    ),
    "liurengzeri": _policy(
        intent=(
            "六壬择时：在一段时间窗内扫出满足条件树的时辰，并附命中首刻的完整六壬盘（天地盘/四课/三传）"
            "（[择时搜索配置]/[择时条件]/[命中时段]）。"
            "\n算权：**区间搜索由本地 vendored 六壬引擎计算**；"
            "**展示盘按 liureng_gods 自己的算源铸**（与直接调该工具逐字同段）；"
            "结果里 compute_sources 逐项写明，切勿把搜索结果说成别的引擎算的。"
            "\n贵人昼夜会切分区间；不涉贵人的条件不会被日出日落切碎（上游的行粒度折叠）。"
            "\n条件树形状：组 {kind:'group', joiner:'all'|'any'|'xor', negate?, children:[…]}；"
            "叶 {kind:'leaf', type:'<键>', negate?, params:{…}}。条件类键（引擎自带词表，非本文件手抄）："
            "ke_name（课名(九宗门)） / chuan_zhi（三传含支） / chuan_jiang（三传天将） / chuan_liuqin（三传六亲） / chuan_kong（三传旬空） / chuan_ju（三传合局） / fa_yong（发用(初传)神煞） / tianpan_at（天盘乘临） / guiren_pos（贵人临支·顺逆） / jiang_at（天将临支） / yue_jiang_is（月将） / zhou_ye（昼占/夜占）；…共 27 类，完整表见 vendored liurengZeriConditionTypes。"
        ),
        required_context=COMMON_LOCATION_FIELDS + ["搜索窗 startDate/endDate", "择日条件 conditions", "用事主题"],
        ask_if_missing=[
            {"field": "startDate/endDate", "question": "要在哪段时间里找？（起止日期）"},
            {"field": "conditions", "question": "择日要满足什么条件？"},
            {"field": "location", "question": "起盘地点用哪里？", "options": ["当前位置/客户端位置", "指定城市或经纬度"]},
            {"field": "topic", "question": "这次择日是为什么事？（搬家/开业/婚嫁…）"},
        ],
        safe_defaults=[
            {"field": "maxSpanDays", "value": 92, "meaning": "搜索窗上限；更长请分段"},
            {"field": "options", "value": {"guirengType": 2, "yueMode": "zhongqi", "after23NewDay": 1, "lateZiHourUseNextDay": 1}, "meaning": "六壬择时页出厂扫描口径（LiurengZeriMain.js:79；贵人 2 = 星阙默认取法，扫描引擎自身缺省是 0）；展示盘（liureng_gods）同跟贵人与日界，节气换将 yueMode=jieqi 尚不能随到展示盘"},
            *ZERI_SNAPSHOT_SAFE_DEFAULTS,
        ],
        do_not_assume=["搜索时间窗", "择日条件", "location"],
        output_contract=(
            "intervals 是命中区间（含 pick/pickEnd 边界安全时刻，取盘请用 pick 而非 start——"
            "start 会落到时辰边界的另一侧）。零命中时三段仍会出现并写明范围内无满足条件的时段，不是缺段。"
        ),
    ),
    "sanshizeri": _policy(
        intent=(
            "三式合一择时：在一段时间窗内扫出满足条件树的时辰，并附命中首刻的完整三式合一盘"
            "（[择时搜索配置]/[择时条件]/[命中时段]）。"
            "\n算权：**区间搜索由本地 vendored 三式引擎（六壬+奇门+太乙同跑）计算**；"
            "**展示盘按 sanshi_united 自己的算源铸**（与直接调该工具逐字同段）；"
            "结果里 compute_sources 逐项写明，切勿把搜索结果说成别的引擎算的。"
            "\n70 个条件类，前缀标明来自哪一式：lr_=六壬、qm_=奇门、ty_=太乙，可跨式自由组合。"
            "\n条件树形状：组 {kind:'group', joiner:'all'|'any'|'xor', negate?, children:[…]}；"
            "叶 {kind:'leaf', type:'<键>', negate?, params:{…}}。条件类键（引擎自带词表，非本文件手抄）："
            "lr_ke_name（六壬·课名(九宗门)） / lr_chuan_zhi（六壬·三传含支） / lr_chuan_jiang（六壬·三传天将） / lr_chuan_liuqin（六壬·三传六亲） / lr_chuan_kong（六壬·三传旬空） / lr_chuan_ju（六壬·三传合局） / lr_fa_yong（六壬·发用(初传)神煞） / lr_tianpan_at（六壬·天盘乘临） / lr_guiren_pos（六壬·贵人临支·顺逆） / lr_jiang_at（六壬·天将临支） / lr_yue_jiang_is（六壬·月将） / lr_zhou_ye（六壬·昼占/夜占）；…共 70 类，完整表见 vendored sanshiZeriConditionTypes。"
        ),
        required_context=COMMON_LOCATION_FIELDS + ["搜索窗 startDate/endDate", "择日条件 conditions", "用事主题"],
        ask_if_missing=[
            {"field": "startDate/endDate", "question": "要在哪段时间里找？（起止日期）"},
            {"field": "conditions", "question": "择日要满足什么条件？"},
            {"field": "location", "question": "起盘地点用哪里？", "options": ["当前位置/客户端位置", "指定城市或经纬度"]},
            {"field": "topic", "question": "这次择日是为什么事？（搬家/开业/婚嫁…）"},
        ],
        safe_defaults=[
            {"field": "maxSpanDays", "value": 92, "meaning": "搜索窗上限；更长请分段"},
            {"field": "options", "value": {"guirengType": 2, "yueMode": "zhongqi", "taiyiAccum": 0, "after23NewDay": 1, "lateZiHourUseNextDay": 1, "timeAlg": 0}, "meaning": "三式择时页出厂扫描口径（SanshiZeriMain.js:80）；展示盘同跟时间三键/奇门盘式键/taiyiAccum，六壬贵人与节气换将尚不能随到 sanshiunited 展示盘"},
            *ZERI_SNAPSHOT_SAFE_DEFAULTS,
        ],
        do_not_assume=["搜索时间窗", "择日条件", "location"],
        output_contract=(
            "intervals 是命中区间（含 pick/pickEnd 边界安全时刻，取盘请用 pick 而非 start——"
            "start 会落到时辰边界的另一侧）。零命中时三段仍会出现并写明范围内无满足条件的时段，不是缺段。"
        ),
    ),
    "qizhengzeri": _policy(
        intent=(
            "七政择时：在一段时间窗内扫出满足条件树的分钟级区间，并附命中首刻的完整七政四余/果老盘"
            "（[择时搜索配置]/[择时条件]/[命中时段]）。"
            "\n算权：**区间搜索由astropy 后端（swisseph 直连）计算**；"
            "**展示盘按 guolao_chart 自己的算源铸**（与直接调该工具逐字同段）；"
            "结果里 compute_sources 逐项写明，切勿把搜索结果说成别的引擎算的。"
            "\n判定与搜索**都在后端**，不是本地重算；窗口超 93 天时 skill 自动按月切分再缝合。"
            "\n条件树形状：组 {kind:'group', joiner:'all'|'any'|'xor', negate?, children:[…]}；"
            "叶 {kind:'leaf', type:'<键>', negate?, params:{…}}。条件类键（引擎自带词表，非本文件手抄）："
            "body_in_gong（曜落地支宫） / body_in_xiu（曜落二十八宿） / dignity（曜庙旺状态） / dignity_seven（曜七态(殿垣庙旺乐喜怒)） / deg_lord（所在宿度主） / speed_state（曜行度态） / combust（合日伏焦） / day_night（昼占/夜占） / asc_gong（命宫(上升)落支） / body_rel（两曜宫位关系） / hua_lu（化曜(年干禄主)落处）。"
        ),
        required_context=COMMON_LOCATION_FIELDS + ["搜索窗 startDate/endDate", "择日条件 conditions", "用事主题"],
        ask_if_missing=[
            {"field": "startDate/endDate", "question": "要在哪段时间里找？（起止日期）"},
            {"field": "conditions", "question": "择日要满足什么条件？"},
            {"field": "location", "question": "起盘地点用哪里？", "options": ["当前位置/客户端位置", "指定城市或经纬度"]},
            {"field": "topic", "question": "这次择日是为什么事？（搬家/开业/婚嫁…）"},
        ],
        safe_defaults=[
            {"field": "maxSpanDays", "value": 731, "meaning": "搜索窗上限；更长请分段"},
            {"field": "su28Mode", "value": 2, "meaning": "宿度制回归今宿（七政择时页出厂，QizhengZeriMain.js:56）；扫描只支持 2/3（3=开禧宿度）"},
            {"field": "nodeType", "value": "mean", "meaning": "罗计平交点（页面出厂）；true=真交点，展示盘同跟（guolaoNodeType）"},
            {"field": "lilithType", "value": "mean", "meaning": "月孛平远地点（页面出厂）；true=真远地点，展示盘同跟（guolaoLilithType）；宿度制尚不能随到展示盘"},
            *ZERI_SNAPSHOT_SAFE_DEFAULTS,
        ],
        do_not_assume=["搜索时间窗", "择日条件", "location"],
        output_contract=(
            "intervals 是命中区间（含 pick/pickEnd 边界安全时刻，取盘请用 pick 而非 start——"
            "start 会落到时辰边界的另一侧）。零命中时三段仍会出现并写明范围内无满足条件的时段，不是缺段。"
        ),
    ),
    "indiazeri": _policy(
        intent=(
            "印度择时（Muhurta）：在一段时间窗内扫出满足条件树的分钟级区间，（不附基底盘）"
            "（[择时搜索配置]/[择时条件]/[命中时段]）。"
            "\n算权：**区间搜索由astropy 后端计算**；"
            ""
            "结果里 compute_sources 逐项写明，切勿把搜索结果说成别的引擎算的。"
            "\n段自足：印度盘全文见 india_chart 本身，本工具只出择时三段（上游同款）。条件覆盖 Panchanga 五肢（tithi/vara/nakshatra/yoga/karana）+ Lagna + 日凶段 + 三十须臾等。"
            "\n条件树形状：组 {kind:'group', joiner:'all'|'any'|'xor', negate?, children:[…]}；"
            "叶 {kind:'leaf', type:'<键>', negate?, params:{…}}。条件类键（引擎自带词表，非本文件手抄）："
            "tithi（Tithi(月相日)） / vara（Vara(曜日·日出界)） / nakshatra（Nakshatra(月宿)） / yoga（Yoga(日月合行)） / karana（Karana(半日)） / lagna（Lagna(上升星座)） / planet_sign（曜落星座） / retro（曜顺逆） / day_kalam（日凶段(Rahu Kalam 类)） / tara_bala（Tara Bala(宿力)） / chandra_bala（Chandra Bala(月力)） / muhurta_seg（三十须臾(Muhurta/Abhijit)）；…共 18 类，完整表见 vendored indiaZeriConditionTypes。"
        ),
        required_context=COMMON_LOCATION_FIELDS + ["搜索窗 startDate/endDate", "择日条件 conditions", "用事主题"],
        ask_if_missing=[
            {"field": "startDate/endDate", "question": "要在哪段时间里找？（起止日期）"},
            {"field": "conditions", "question": "择日要满足什么条件？"},
            {"field": "location", "question": "起盘地点用哪里？", "options": ["当前位置/客户端位置", "指定城市或经纬度"]},
            {"field": "topic", "question": "这次择日是为什么事？（搬家/开业/婚嫁…）"},
        ],
        safe_defaults=[
            {"field": "maxSpanDays", "value": 731, "meaning": "搜索窗上限；更长请分段"},
            {"field": "indiaAyanamsa", "value": "lahiri", "meaning": "扫描岁差制（IndiaScanContext 读 ayanamsa，缺省 lahiri；indiaAyanamsa 为同词表别名，显式 ayanamsa 优先）"},
            {"field": "nodeType", "value": "mean", "meaning": "罗睺计都平交点（印度择时页出厂，IndiaZeriMain.js:57）；true=真交点"},
            *ZERI_SNAPSHOT_SAFE_DEFAULTS,
        ],
        do_not_assume=["搜索时间窗", "择日条件", "location"],
        output_contract=(
            "intervals 是命中区间（含 pick/pickEnd 边界安全时刻，取盘请用 pick 而非 start——"
            "start 会落到时辰边界的另一侧）。零命中时三段仍会出现并写明范围内无满足条件的时段，不是缺段。"
        ),
    ),
    "tianxing": _policy(
        intent=(
            "天星择日·征象搜索：在一段时间窗内扫出满足西占征象条件树的时段"
            "（[起盘信息]/[征象搜索配置]/[征象条件]/[命中区间]）。搜索由 Python 端 /electionscan/scan 计算；"
            "窗口超 93 天时 skill 自动按月切分再缝合。"
            "\n条件树形状：组 {kind:'group', joiner:'all'|'any'|'xor', negate?, children:[…]}；"
            "叶 {type:'<键>', params:{…}}。32 个条件类键（运行时孪生：GET /electionscan/conditiontypes）："
            "aspect(planetA,planetB,angle,orb)、in_sign(planet,signs=星座序号 0-11)、"
            "numeric(planet,field,op,value)、midpoint(a,b,target,modulus,orb)、"
            "point_relation(planet,point,relation)、in_house(planet,houses)、reception(planetA,planetB)、"
            "mutual_reception、rulership、dignity_state、degree_state、decan_state、fixed_star、"
            "besieged、antiscia、moon_phase、void_of_course、considerations、chart_shape、"
            "almuten_is、eminence_level、light_dynamics、distribution_state、lifespan_state、"
            "classical_pattern、aspect_pattern、dispositor_cycle、accidental_score、day_window、"
            "mansion、sect_joy、royal_slot 等。星座/宫位一律用**序号**，不是英文名。"
            "\n单时判读：传 explainAt='YYYY-MM-DD HH:mm[:ss]' 可对该时刻逐叶判读（[单时判读] 段，"
            "每叶「设定/实际 ✓✗」，与扫描求值器绝对同源）——用于回答「为什么这个时刻中/不中选」。"
        ),
        required_context=COMMON_LOCATION_FIELDS + ["搜索窗 startDate/endDate", "征象条件 conditions", "用事主题"],
        ask_if_missing=[
            {"field": "startDate/endDate", "question": "要在哪段时间里找吉时？（起止日期）"},
            {"field": "conditions", "question": "要满足什么天象条件？（如月亮拱木星、日在白羊等）"},
            {"field": "location", "question": "择日地点用哪里？", "options": ["当前位置/客户端位置", "指定城市或经纬度"]},
            {"field": "topic", "question": "这次择日是为什么事？"},
            {"field": "hsys", "question": "宫制是否沿用默认？", "options": ["默认", "指定宫制"]},
        ],
        safe_defaults=[
            {"field": "precision", "value": "minute", "meaning": "扫描到分钟"},
            {"field": "lotReversal/lotFortuneVariant/hermeticLotsReversal", "value": "1/standard/1",
             "meaning": "希腊点口径与主排盘同式（上游缺省：福点昼夜反转、标准福点式、七星点反转）；顶层或 options 传入即进扫描与 [选中时刻星盘]"},
            {"field": "userAyanT0/userAyanDeg", "value": None,
             "meaning": "siderealAyanamsa='user' 档的历元 JD 与该历元岁差度（缺参按 Lahiri）；进扫描与 [选中时刻星盘]"},
            *ZERI_SNAPSHOT_SAFE_DEFAULTS,
        ],
        do_not_assume=["搜索时间窗", "征象条件", "location"],
        output_contract=(
            "intervals 为命中时段（含 pick/pickEnd 边界安全时刻）。零命中时 [命中区间] 段仍会出现并写明"
            "「时间段内无满足全部条件的时刻」，不是缺段。条件不合法会明确报错（details 附服务端支持的"
            "条件类型表），不会退化成零命中。给了 explainAt 时结果多一个 explain 键与 [单时判读] 段。"
        ),
    ),
    "planet_cycles": _policy(
        intent=(
            "行星周期：任意两星（木土/土冥/天海/火木…）在给定年区间内合(0°)或冲(180°)的精确时间轴——"
            "世运周期研究的骨架数据；支持地心/日心/站心坐标系。无出生盘概念，事件时刻为 UT。"
        ),
        required_context=["星对 p1/p2（或接受木土默认）", "年区间 startYear/endYear"],
        ask_if_missing=[
            {"field": "p1/p2", "question": "看哪两颗星的周期？", "options": ["木土（默认，20 年会合）", "指定星对"]},
            {"field": "startYear/endYear", "question": "看哪段年区间？", "options": ["1900–2100（默认）", "指定区间"]},
            {"field": "aspect", "question": "合还是冲？", "options": ["合 0°（默认）", "冲 180°", "指定角度"]},
        ],
        safe_defaults=[
            {"field": "center", "value": "geo", "meaning": "地心（上游缺省；日心 helio 用于纯周期研究）"},
        ],
        do_not_assume=["星对", "年区间"],
        output_contract=(
            "cycles.events 为逐次事件（jd/年月日/UT 小时/黄经/宫）；快照 [会合事件] 行 = 时刻(UT) + 黄经度分。"
            "地心模式下外行星合冲附近可因逆行三次经过——多行同年是真实现象不是重复。"
        ),
    ),
    "jieqi_birth": _policy(
        intent=(
            "出生节气窗：给出出生时刻前后各节气（节/气标注）的精确时刻，并标出出生所落的区间——"
            "八字起运数窗的同源数据（BirthJieQi）。"
        ),
        required_context=COMMON_LOCATION_FIELDS,
        ask_if_missing=[
            {"field": "date/time", "question": "出生的公历日期和时间？"},
            {"field": "location", "question": "出生地点用哪里？"},
        ],
        safe_defaults=[
            {"field": "useLocalMao/byLon", "value": 0, "meaning": "上游缺省（不开真太阳时卯正/经度修正）"},
        ],
        do_not_assume=["location"],
        output_contract=(
            "jieqi 为节气行表（ord/名/节气性/精确时刻）；[出生节气窗] 末行标出出生落于哪两个节气之间"
            "（纯时刻比较）。起运天数换算属八字断法，请交给 bazi 工具而非自行推算。"
        ),
    ),
    "india_rectify": _policy(
        intent=(
            "印度 KP 法出生时间校正：以给定 date/time 为锚，±半窗内扫描候选出生时刻并按判据打分排序"
            "（RP 命中 / Pranapada / gandanta 边界预警；录入 rectifyEvents 后事件评分才参评）。"
            "输出证据与排序（候选榜 / Lagna 子主区段 / 步长诊断），**是否采用由用户决定**。"
        ),
        required_context=COMMON_LOCATION_FIELDS + ["锚点出生时刻（待校正）", "扫描半窗与步长（或接受默认）"],
        ask_if_missing=[
            {"field": "date/time", "question": "大致的出生时间是？（作为扫描锚点）"},
            {"field": "location", "question": "出生地点用哪里？"},
            {"field": "rectifyWindowMinutes", "question": "扫描半窗多大？", "options": ["30 分钟（默认）", "自定（≤240 分）"]},
            {"field": "rectifyEvents", "question": "有已知人生大事可供参评吗？（可选，录入后事件判据才生效）"},
        ],
        safe_defaults=[
            {"field": "rectifyWindowMinutes", "value": 30, "meaning": "锚点前后各 30 分钟"},
            {"field": "rectifyStepSeconds", "value": 60, "meaning": "60 秒步长（诊断不充分时按建议改小）"},
            {"field": "rectifyRpSource", "value": "anchor", "meaning": "RP 按原始钟表时刻取（无自指）"},
        ],
        do_not_assume=["出生时刻已准确", "location", "事件列表"],
        output_contract=(
            "rectify 键为后端原始响应（top/samples/runs/vara/resolution/criteriaActive）。判据常态为三项"
            "（rp/pranapada/boundary），事件评分仅在请求携 rectifyEvents 时参评——criteriaActive 如实回显，"
            "勿宣称五判据。候选榜是打分排序不是二值判定；免责声明原样在 [声明] 段，采用与否由用户决定。"
            "步长诊断 adequate=false 时须按 suggestedStepSeconds 建议用户改小步长重扫。"
        ),
    ),
    "qizhengelection": _policy(
        intent=(
            "七政择日动盘（果老「择日双轮」headless 版）：候选时刻的十一曜黄道地支度 / 二十四山方位"
            "（山分度+地平上下）/ 顺逆 + 真太阳时·均时差·日月出没·命度。action=eclipses 搜未来日月食；"
            "action=azimuthsearch 搜星曜到达指定罗盘方位（0=北顺时针）的时刻。date/time 是**候选择日"
            "时刻**，不是出生时间。"
        ),
        required_context=COMMON_LOCATION_FIELDS + ["候选时刻（或搜索起点）", "用事主题"],
        ask_if_missing=[
            {"field": "date/time", "question": "要评估哪个候选时刻？（择日用时，非出生时间）"},
            {"field": "location", "question": "用事地点用哪里？", "options": ["当前位置/客户端位置", "指定城市或经纬度"]},
            {"field": "plate", "question": "二十四山用哪套盘？", "options": ["地盘（默认）", "天盘(+7.5°)", "人盘(−7.5°)"]},
            {"field": "ziZheng", "question": "子正用真北还是磁北？", "options": ["真北（默认）", "磁北（请提供当地磁偏角）"]},
        ],
        safe_defaults=[
            {"field": "plate", "value": "di", "meaning": "地盘（上游缺省）"},
            {"field": "ziZheng", "value": "true", "meaning": "真北（不套磁偏）"},
            {"field": "nodeType/lilithType", "value": "mean", "meaning": "平均罗计/月孛（上游缺省）"},
            {"field": "eleLifeMode", "value": "sunrise", "meaning": "命度从日出起（上游缺省）"},
        ],
        do_not_assume=["候选时刻", "location", "磁偏角"],
        output_contract=(
            "pan 键为后端原始动盘数据（十一曜/宫位系/28宿界/日月出没）；快照 [择日动盘] 每行 = "
            "星：黄道地支度 | 山分度±地平 | 方位/高度 | 顺逆。升殿失垣列依赖 /qizheng/moira——开源栈"
            "无此路由（排除台账），故不产。eclipses/hits 为搜索行表，附 [日月食搜索]/[方位搜索] 段。"
            "方位搜索行自带实测 azimuth 列——上游粗扫在与目标差 180° 的对冲方位也会报行（±180 回绕），"
            "取用时以 azimuth 列为准。"
            "紫炁与天海冥不在默认十一曜内，需经 extraBodies 透传（照上游从流年盘取黄经）。"
        ),
    ),
    "taiyi": _policy(
        intent="太乙起盘。",
        required_context=COMMON_LOCATION_FIELDS + ["question/topic"],
        ask_if_missing=[
            {"field": "date/time", "question": "太乙用当前时间还是指定时间？", "options": ["当前时间", "指定时间"]},
            {"field": "location", "question": "起盘地点用哪里？"},
            {"field": "gender/options", "question": "是否需要指定性别或太乙参数（盘式/积年/时间基准/流派）？", "options": ["沿用星阙默认", "指定参数"]},
        ],
        safe_defaults=[
            {"field": "options.timeBasis", "value": "direct", "meaning": "星阙默认：直接时间（钟表时起局；trueSolar 改按真太阳时）"},
            {"field": "options.style", "value": 3, "meaning": "星阙默认：时计太乙"},
            {"field": "options.tn", "value": 0, "meaning": "星阙默认：太乙统宗积年"},
            {"field": "options.school", "value": "六轴全 default", "meaning": "星阙默认：从盘（kintaiyi 原盘，不覆盖）"},
        ],
        do_not_assume=["location", "custom options"],
    ),
    "jinkou": _policy(
        intent="金口诀起课。",
        required_context=COMMON_LOCATION_FIELDS + ["question/topic", "diFen/地分 when the method requires it"],
        ask_if_missing=[
            {
                "field": "diFen",
                "question": "金口诀地分/方位用哪一支？星阙默认「自动」= 取占时支。",
                "options": ["自动（占时支，星阙默认）", "子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"],
                "values": ["auto", "子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"],
            },
            {"field": "guirengType", "question": "贵人体系用哪一种？", "options": ["六壬法贵人（星阙金口诀默认）", "星占法贵人", "遁甲法贵人"]},
            {"field": "question", "question": "这课主要问什么事？"},
        ],
        safe_defaults=[
            {"field": "guirengType", "value": 0, "meaning": "金口诀星阙默认（六壬法贵人）"},
            {"field": "diFen", "value": "auto", "meaning": "星阙默认：自动取占时支"},
            {"field": "options.wuxing", "value": "日干五行", "meaning": "星阙默认：十二长生五行随日干"},
            {"field": "options.流派五键", "value": "全缺省", "meaning": "星阙默认：中气换将/实务贵人表/地盘起贵/阳盘/水土同宫 → ken 盘"},
            {"field": "options.timeBasis", "value": "direct", "meaning": "星阙默认：直接时间（只在 ken 路径生效）"},
        ],
        do_not_assume=["diFen"],
    ),
    "liureng_gods": _policy(
        intent="大六壬正盘：四课、三传、贵神、神煞。",
        required_context=COMMON_LOCATION_FIELDS + ["question/topic"],
        ask_if_missing=[
            {"field": "date/time", "question": "大六壬用当前时间还是指定时间？", "options": ["当前时间", "指定时间"]},
            {"field": "location", "question": "起课地点用哪里？", "options": ["当前位置/客户端位置", "指定城市或经纬度"]},
            {"field": "question", "question": "这课主要问什么事？"},
            {"field": "guirengType", "question": "贵人体系用哪一种？", "options": ["星占法贵人（星阙默认/推荐）", "六壬法贵人", "遁甲法贵人", "甲戊兼牛羊", "干合阳阴贵"], "values": [2, 0, 1, 3, 4]},
            {"field": "isDiurnal", "question": "昼夜贵人是否由 Horosa 自动判定？", "options": ["自动判定", "指定昼贵", "指定夜贵"]},
            {"field": "options", "question": "起课口径是否沿用星阙默认（正时正将 / 中气过宫 / 晨昏分昼夜 / 涉害仅下贼上）？", "options": ["沿用星阙默认", "指定起课法或换将等（见 options_keys）"]},
        ],
        safe_defaults=[
            {"field": "guirengType", "value": 2, "meaning": "星占法贵人 / Xingque default"},
            {"field": "isDiurnal", "value": None, "meaning": "由本地 runtime 根据时间判定"},
            {"field": "options.castMethod", "value": "zheng", "meaning": "星阙默认：正时正将"},
            {"field": "options.timeAlg", "value": 0, "meaning": "星阙默认：真太阳时（后端缺省，不传即此档）"},
            {"field": "options.wuxing", "value": "日干五行", "meaning": "星阙默认：十二长生五行随日干"},
            {"field": "after23NewDay", "value": 1, "meaning": _AFTER23_DEFAULT_MEANING},
        ],
        do_not_assume=["question", "location", "non-default guirengType", "non-default castMethod"],
    ),
    "liureng_runyear": _policy(
        intent="大六壬行年/年运。",
        required_context=COMMON_LOCATION_FIELDS + ["gender", "target year/date when different from base time"],
        ask_if_missing=[
            {"field": "gender", "question": "行年需要性别，请选择。", "options": ["男", "女"]},
            {"field": "guaDate/guaYearGanZi", "question": "要看哪一年/哪一段行年？"},
            {"field": "guirengType", "question": "贵人体系是否沿用星阙默认星占法贵人？", "options": ["星占法贵人", "六壬法贵人", "遁甲法贵人", "甲戊兼牛羊", "干合阳阴贵"], "values": [2, 0, 1, 3, 4]},
        ],
        safe_defaults=[
            {"field": "guirengType", "value": 2, "meaning": "星占法贵人"},
            {"field": "options.castMethod", "value": "zheng", "meaning": "星阙默认：正时正将（行年加时/本命加时等见 options_keys）"},
        ],
        do_not_assume=["gender", "target year"],
    ),
    "sanshiunited": _policy(
        intent="三式合一：奇门、太乙、大六壬聚合。",
        required_context=COMMON_LOCATION_FIELDS + ["question/topic"],
        ask_if_missing=[
            {"field": "date/time/location", "question": "三式合一用当前时间地点还是指定时间地点？", "options": ["当前时间地点", "指定时间地点"]},
            {"field": "question", "question": "这次要三式合参判断什么事？"},
            {"field": "submethod settings", "question": "子技法设置是否沿用星阙默认？", "options": ["全部沿用默认", "指定奇门/太乙/六壬参数"]},
        ],
        safe_defaults=[
            {"field": "liureng guirengType", "value": 2, "meaning": "通过六壬工具使用星阙默认"},
            {"field": "qimen_options.qijuMethod", "value": "zhirun", "meaning": "星阙默认：置闰"},
            {"field": "taiyi_options.timeBasis", "value": "direct", "meaning": "星阙默认：直接时间（不随顶层 timeAlg 串改，同上游）"},
            {"field": "liureng_options.castMethod", "value": "zheng", "meaning": "三式合一锁正时正将（同上游）"},
        ],
        do_not_assume=["question"],
    ),
    "sixyao": _policy(
        intent=(
            "六爻/易卦。"
            "\n判读口径 liuyaoSettings = 上游六爻挂载齿轮 24 键（扁平形；选 school 即按上游 mergeLiuyaoGearSettings "
            "套该派细项，其余键再叠上）：school=default 通用·卜筮正宗口径（缺省）/zengshan 增删卜易/yiyin 易隐/"
            "xinpai 邵伟华新派/mangpai 盲派/tianji 断易天机；askType 占测事项(定用神)=self（缺省）、opponent、wealth、"
            "career、marriage_m、marriage_f、illness、parents、children、doctor、sibling、thief、weather_rain、weather_sun、"
            "lost、travel、lawsuit、home、guishen、study、guochao；yongOverride ''(跟占测事项)/父母/兄弟/子孙/妻财/官鬼/世/应；"
            "benming ''(不用)/子…亥；tuChangsheng water（缺省）/fire/off；bianyaoScope traditional（缺省）/blind；"
            "fushen missing（缺省）/all；yuepoMode inMonth（缺省）/always；shishen off（缺省）/standard/lichunfeng；"
            "jinTuiTu chain（缺省）/break（考据声明项，两档输出恒同）；tianshiSchool fumu（缺省）/ancient；"
            "yearBoundary lichun（缺省）/lunar；开关（1/0）guashen=1 sixGods=1 yuqi=0 yingqi=1 doctrine=1 gufa=0 "
            "yueLiushen=0 shenshaOn=1 shenshaExOn=0；guirenFa standard（缺省）/geng_ma_hu；shenshaBase day（缺省）/year；"
            "shenshaSet=神煞名数组（缺省 天乙贵人/禄神/羊刃/驿马/桃花/将星/华盖/劫煞/亡神）。"
            "\n[断卦结构]/[断诀命中]/[占类断语] 由 vendored 上游 liuyaoStructLines/liuyaoSnapshotEx 产出（含《断易天机》"
            "断语摘要）；shishen/tianshiSchool/yuqi/gufa/yueLiushen/shenshaExOn 只改后两段。认不出的键/不在词表的值回执在 warnings。"
            "\n不给 lines/gua_code = 以时起卦（上游 buildTimeGua：年支序 + 农历月数 + 农历日数 + 时柱支序，时柱随 timeAlg）。"
        ),
        required_context=COMMON_LOCATION_FIELDS + ["question", "lines or gua_code"],
        ask_if_missing=[
            {"field": "question", "question": "这卦要问什么事？"},
            {"field": "lines/gua_code", "question": "卦怎么来？", "options": ["用户给六爻阴阳动静", "用户给本卦/变卦", "以起卦时刻时间起卦（不给 lines，同星阙 AI 挂载）"]},
            {"field": "liuyaoSettings.askType", "question": "所问归哪一类？（决定用神取用）", "options": ["自身/综合 self", "求财 wealth", "功名/工作 career", "婚姻（男测 marriage_m / 女测 marriage_f）", "疾病 illness", "其他（见 intent 全表）"]},
            {"field": "liuyaoSettings.school", "question": "断卦流派沿用星阙默认吗？", "options": ["通用·卜筮正宗口径（默认）", "增删卜易 zengshan", "易隐 yiyin", "邵伟华新派 xinpai", "盲派 mangpai", "断易天机 tianji"]},
            {"field": "timeAlg", "question": "占时用真太阳时还是直接时间？", "options": ["真太阳时（星阙默认）", "直接时间（钟表时）"]},
        ],
        safe_defaults=[
            {"field": "timeAlg", "value": 0, "meaning": "真太阳时（上游 [Q-390/T-372]：页面 > 全局 > 缺省真太阳时）"},
            {"field": "after23NewDay", "value": 1, "meaning": "23 点后归次日（不发送 = 后端默认 = 星阙出厂全局默认）"},
            {"field": "lateZiHourUseNextDay", "value": 1, "meaning": "晚子时时干按次日日干起（不发送 = 后端默认 = 星阙出厂全局默认）"},
            {"field": "liuyaoSettings.school", "value": "default", "meaning": "通用（卜筮正宗口径），上游 DEFAULT_LIUYAO_SETTINGS"},
            {"field": "liuyaoSettings.askType", "value": "self", "meaning": "自身/综合运势；问事明确时应按所问改"},
        ],
        do_not_assume=["lines", "gua_code", "question"],
    ),
    "tongshefa": _policy(
        intent="统摄法。",
        required_context=["taiyin", "taiyang", "shaoyang", "shaoyin or explicit acceptance of defaults"],
        ask_if_missing=[
            {"field": "four symbols", "question": "统摄法四象参数用默认还是指定？", "options": ["沿用默认", "指定太阴/太阳/少阳/少阴"]},
        ],
        safe_defaults=[
            {"field": "taiyin/taiyang/shaoyang/shaoyin", "value": "巽/坤/震/震", "meaning": "current contract default; ask if user expects custom setup"}
        ],
    ),
    "canping": _policy(
        intent="邵子参评数 / 金锁银匙：以年纳音定部、四柱起数、查本命/大运/流年歲運条文。",
        required_context=["birth date", "birth time", "longitude (真太阳时可选)", "gender", "method (明法/古法)"],
        ask_if_missing=[
            {"field": "date/time/place", "question": "请提供出生日期、时间、经度（真太阳时用）和性别。"},
            {"field": "method", "question": "取法用明法还是古法？", "options": ["明法（月支反向取日宫·默认）", "古法（八字日支为日宫）"]},
            {"field": "timeAlg", "question": "用真太阳时还是钟表时？", "options": ["钟表时（星阙参评数默认）", "真太阳时（按经度+均时差校正）"]},
        ],
        safe_defaults=[
            {"field": "method", "value": "ming", "meaning": "明法·月支反向取日宫（星阙默认）"},
            {"field": "timeAlg", "value": 1, "meaning": "钟表时，对应 CanPingMain.js 的默认"},
        ],
        do_not_assume=["gender", "method"],
    ),
    "heluo": _policy(
        intent="河洛理数：以四柱天地数起先天/后天卦与元堂，推命运篇与大限·岁运（含元堂爻辞）。",
        required_context=["birth date", "birth time", "longitude (真太阳时可选)", "gender"],
        ask_if_missing=[
            {"field": "date/time/place", "question": "请提供出生日期、时间、经度（真太阳时用）和性别。"},
            {"field": "timeAlg", "question": "用真太阳时还是钟表时？", "options": ["钟表时（星阙河洛默认）", "真太阳时（按经度+均时差校正）"]},
            {"field": "quHuaGong", "question": "取化工法用哪一档？（只在四立前十八日土用期生人有差）", "options": ["土王寄坤艮（星阙默认）", "直取四方伯 siFangBoOnly"]},
        ],
        safe_defaults=[
            {"field": "timeAlg", "value": 1, "meaning": "钟表时，对应 HeLuoMain.js 的默认"},
            {"field": "quHuaGong", "value": "tuWangKunGen", "meaning": "土王寄坤艮：土用期补坤艮/反乾兑（上游挂载 schema 缺省）；改 siFangBoOnly 只动 [命运篇] 化工/反化工行"},
            {"field": "huangdiOffset", "value": 2697, "meaning": "纪年基准（公历=黄帝纪元−2697，上游缺省）；只动 [断验] 纪年行"},
        ],
        do_not_assume=["gender"],
    ),
    "yizhangjing": _policy(
        intent=(
            "一掌经：农历生辰四宫十二星（六道），排命宫/人事十二宫/格局/重犯/大限/小限流年十二神，可叠神煞合参层。"
            "\n排盘选项 = 上游 KinAstroMain.buildYizhangjingOpts 同键，缺省 = 桌面出厂档（「秘传口诀」预设）："
            "shunniRule yangNanYinNv/menShunNvNi；mingGongMethod shiShang/shuZhiMao；dingYue lunar/jieqi；"
            "dayunLength 7/10；dayunStartAge mi/age1；xiaoxianStart ri/yue；xiaoxianDir chart/always；"
            "annualMethod xiaoxian（只出小限）/liunian（只出流年十二神，同时出 [流年总论]）/未设（两法并列 + [流年总论]，"
            "同上游 AI 挂载无头重算缺省；桌面页出厂为小限）；flowShenSet A/B/C；"
            "leapRule half/midnight；zaoZiAdjust；starNaming A/B/C；daoTerm gui/edao；gradeSet standard/variant；"
            "chongfanKou alpha/beta；tongxianShow（童限，出厂开）；shenshaLayer（神煞合参层，出厂关）。"
        ),
        required_context=["birth date", "birth time", "gender"],
        ask_if_missing=[
            {"field": "date/time", "question": "请提供出生日期、时间和性别（一掌经按农历口径排盘）。"},
            {"field": "dingYue", "question": "定月用农历月还是节气月？", "options": ["农历月（默认，闰月十五折半）", "节气月（按八字月支序）"]},
            {"field": "annualMethod", "question": "逐年看小限还是流年十二神？（文献明训两法只用一套；不指定则两法并列）", "options": ["小限 xiaoxian", "流年十二神 liunian", "两法并列（不指定，同星阙 AI 挂载缺省）"]},
        ],
        safe_defaults=[
            {"field": "dingYue", "value": "lunar", "meaning": "农历月，闰月十五折半归属"},
            {"field": "dayunLength", "value": 7, "meaning": "大限一宫 7 年（通行口径）"},
            {"field": "annualMethod", "value": None, "meaning": "未设 = 小限与流年十二神两法并列（星阙 AI 挂载无头重算的缺省：record 不带该键；桌面页出厂档 yizhangjingAnnual 为小限）"},
            {"field": "shenshaLayer", "value": False, "meaning": "神煞合参层关（星阙桌面出厂档 yizhangjingShensha=false；开则多出 [神煞合参] 段）"},
            {"field": "after23NewDay", "value": 1, "meaning": "23 点后归次日（星阙出厂全局日界；影响 23 点档生人的日柱与农历日）"},
        ],
        do_not_assume=["gender"],
    ),
    "acg": _policy(
        intent="占星地图（AstroCartoGraphy）：本命时刻行星地理投影线（MC/IC 经度、天顶点、偕升纬度带、线交点）。",
        required_context=COMMON_BIRTH_FIELDS,
        ask_if_missing=[
            {"field": "date/time/place", "question": "请提供出生日期、时间、时区和出生地坐标。"},
            {"field": "mode", "question": "投影口径沿用默认吗？", "options": ["默认（mundo 真黄纬 + 大圆 + Sepharial 地理等价）", "指定 mode/lsMode/geodetic"]},
        ],
        safe_defaults=[
            {"field": "mode", "value": "mundo", "meaning": "真黄纬本体（Jim Lewis 原版口径）"},
            {"field": "lsMode", "value": "great", "meaning": "本地空间线取大圆"},
            {"field": "pointOrb", "value": 2.0, "meaning": "落点命中容许度（上游缺省）"},
        ],
        output_contract=(
            "问「某城市对我如何」时传 clickLat/clickLon（十进制，西经为负）→ [落点分析] 段给该地"
            "命中线（临角的星+距离）/重置四角/敏感点（宿命点/东升点/共升点/极地上升/映点）。"
            "传 eventKind（日月食/朔望/四至入境）→ [事件时刻] 段给 UTC 时刻（CCG 事件线用）。"
        ),
    ),
    "xuanshi": _policy(
        intent="玄史（中国玄学史知识库）：7900+ 玄学事件（原文/白话/解读/引证）、27000+ 史书天象、人物图谱、朝代/术数/天象名词与时间线。纯检索，只读。",
        required_context=["action 或 q"],
        ask_if_missing=[
            {"field": "q", "question": "要查什么？（人物 / 事件关键词 / 术数名 / 天象类别皆可；也可给 action 走结构视图）"},
        ],
        safe_defaults=[
            {"field": "action", "value": "search", "meaning": "缺省走全文检索"},
            {"field": "limit", "value": 30, "meaning": "默认返回前 30 条"},
        ],
    ),
    "bazi_inverse": _policy(
        intent="八字反查：四柱干支 → 候选公历出生时刻（逐年回推）。纯反查，无结果敏感设置。",
        required_context=["pillars (四柱干支)"],
        ask_if_missing=[
            {"field": "pillars", "question": "四柱干支是什么？（年/月/日/时各一组，如 甲子 丙寅 戊辰 庚申）"},
            {"field": "fromYear", "question": "从哪一年开始回推？（缺省=今年）"},
        ],
        safe_defaults=[
            {"field": "count", "value": 3, "meaning": "默认给 3 个候选"},
            {"field": "desc", "value": True, "meaning": "默认向过去回推"},
        ],
    ),
    "astrodata": _policy(
        intent="名人星盘数据库（离线只读检索）：FTS 全文/分类/Rodden 评级过滤，单人详情含可直接排盘的出生数据。",
        required_context=["query 或 personTitle"],
        ask_if_missing=[
            {"field": "query", "question": "要检索哪位名人或哪个关键词？（库内条目以英文为主）"},
        ],
        safe_defaults=[
            {"field": "limit", "value": 20, "meaning": "默认返回前 20 条"},
        ],
    ),
    "suzhan": _policy(
        intent="宿占/宿盘（人事十二宫缺省按八字公式起盘，读 Java /chart 农历时支；ASC 档不需要）。",
        required_context=COMMON_BIRTH_FIELDS,
        ask_if_missing=[
            {"field": "date/time/place", "question": "请提供出生/事件日期、时间、时区和地点。"},
            {
                "field": "doubingSu28/houseStartMode",
                "question": "宿法与人事十二宫起法是否沿用星阙默认？（宿法改二十八宿度数，起法改宫序）",
                "options": ["沿用默认（宿法 0 荀爽距星 · 八字公式起盘）", "指定宿法 0–8 / ASC 起盘"],
            },
        ],
        # 上游 models/astro.js:117-119（doubingSu28 新盘种子缺省 0）/ :312-316（houseStartMode 0）/ :81-83（hsys=DefaultHouseSystem 1）。
        safe_defaults=[
            {"field": "doubingSu28", "value": 0, "meaning": "星阙默认：宿法 0（荀爽距星）；0–8 九档见 options_keys"},
            {"field": "houseStartMode", "value": 0, "meaning": "星阙默认：八字公式起盘（1=ASC 起盘）"},
            {"field": "hsys", "value": 1, "meaning": "星阙页面缺省宫制 1（Alcabitus）"},
        ],
    ),
    "hellen_chart": ASTRO_CHART_POLICY,
    "guolao_chart": ASTRO_BIRTH_POLICY,
    "germany": ASTRO_BIRTH_POLICY,
    "agepoint": ASTRO_BIRTH_POLICY,
    "distributions": ASTRO_BIRTH_POLICY,
    "jaynesprog": JAYNESPROG_POLICY,
    "vedicprog": VEDICPROG_POLICY,
    "ephemeris": EPHEMERIS_POLICY,
    "returntimeline": RETURNTIMELINE_POLICY,
    "prenatalsyzygy": PRENATALSYZYGY_POLICY,
    "prog": PROG_POLICY,
    "planetaryarc": PLANETARYARC_POLICY,
    "planetaryages": PLANETARYAGES_POLICY,
    "balbillus": BALBILLUS_POLICY,
    "yearsystem129": ASTRO_BIRTH_POLICY,
    "persiandirected": PERSIANDIRECTED_POLICY,
    "triplicityrulers": TRIPLICITYRULERS_POLICY,
    "keypoints": KEYPOINTS_POLICY,
    "lunationphase": ASTRO_BIRTH_POLICY,
    "extrareturns": EXTRARETURNS_POLICY,
    "horary": _policy(
        intent="卜卦 / horary：盘的时刻是「提问的当下」（占者收到问题、心中疑问成形的那一刻），不是当事人的出生时间。按问题类别取事项宫。",
        required_context=["提问时刻 date/time/zone", "提问地点 lon/lat", "问题类别 category"],
        ask_if_missing=[
            {"field": "date/time/place", "question": "请提供「提问当下」的日期、时间、时区和地点（卜卦以提问时刻起盘，不是出生时间）。"},
            # 上游 CATEGORY_DEF 20 类（此前只列 14）；中文名/事项宫全表见 options_keys.category。
            {
                "field": "category",
                "question": "问的是哪一类事？",
                "options": [
                    "综合 general", "财物 wealth", "兄弟/亲属 family", "房产/田宅 property", "父亲 father", "母亲 mother",
                    "子嗣 pregnancy", "疾病 health", "婚姻/对象 marriage", "官非/对手 lawsuit", "盗窃/失物 theft",
                    "死亡/遗产 death", "旅行 travel", "事业/职位 career", "愿望 hope", "私敌 enemy", "消息/书信 message",
                    "失物(非盗) lost", "走失活物 lost_animal", "买卖 trade",
                ],
                "values": [
                    "general", "wealth", "family", "property", "father", "mother", "pregnancy", "health", "marriage",
                    "lawsuit", "theft", "death", "travel", "career", "hope", "enemy", "message", "lost", "lost_animal", "trade",
                ],
            },
            # 流派同时定起盘字段（宫制/界系/三分集/福点反转/星群，上游 horaryBackendFields）→ 结果敏感，缺省不静默。
            {
                "field": "school",
                "question": "卜卦按哪一派判？（流派同时决定宫制、界系、三分集等起盘口径）",
                "options": ["经典主流 classical（默认）", "文艺复兴 renaissance", "当代严谨 strict", "序列判读 sequence", "希腊化 hellenistic", "中世纪 medieval", "现代心理 modern"],
                "values": ["classical", "renaissance", "strict", "sequence", "hellenistic", "medieval", "modern"],
            },
        ],
        safe_defaults=[
            {"field": "category", "value": "general", "meaning": "综合判断：事项守护星取月亮下一个入相的星 / 相关宫主"},
            {"field": "school", "value": "classical", "meaning": "经典主流：Regiomontanus（hsys 2）· 托勒密界经典传本 · 托勒密三分 · 七政"},
        ],
        do_not_assume=["提问时刻（绝不可编造，必须是占者真实收到问题的时刻）", "问题类别"],
    ),
    "election": _policy(
        intent="择日 / electional：评估某个「候选时刻」适不适合做某事；盘的时刻是被评估的候选时间，topicId 决定用事规则包与红线。",
        required_context=["候选时刻 date/time/zone", "举事地点 lon/lat", "用事类型 topicId"],
        ask_if_missing=[
            {"field": "date/time/place", "question": "请提供要评估的候选日期、时间、时区和举事地点。"},
            {"field": "topicId", "question": "做什么事（用事类型）？", "options": ["结婚 marriage", "开业/创业 business", "入宅/迁居 move_in", "购屋 buy_property", "买卖交易 trade", "购车 buy_car", "签约 contract", "手术 surgery", "出行 travel", "求职 job_hunt", "其它（37 类全表见 options_keys.topicId）"]},
        ],
        safe_defaults=[{"field": "topicId", "value": "marriage", "meaning": "默认按结婚用事规则包评估"}],
        # natal 可选：给了才加产 [本命合参] 与 [回归与主限]（择日前最近日/月返 + ±240 日主限命中）。
        do_not_assume=["候选时刻", "用事类型", "本命出生资料 natal（只在用户给出时传，不可编造）"],
    ),
    "geomancy": _policy(
        intent="天文地占 / astronomical geomancy：以「起卦时刻」确定性起卦（castMethod='time'，由 date/time 派生 timeSeed，同刻可复现），由 4 母卦推 16 图形入十二宫，取判官/见证/解读技法断吉凶。",
        required_context=["起卦时刻 date/time/zone", "起卦地点 lon/lat", "所问 question", "问类 questionType"],
        ask_if_missing=[
            {"field": "date/time/place", "question": "请提供起卦的日期、时间、时区和地点（地占以起卦时刻确定性起卦）。"},
            {"field": "question", "question": "所问何事？请给出具体问题。"},
            # 后端 _QTYPES 十一类（webgeomancysrv.py:42-46）；此前给的 lawsuit/theft/pregnancy/property/travel/hope
            # 后端不认、静默改回 custom。
            {"field": "questionType", "question": "问的是哪一类？", "options": ["综合/自定 custom", "命主/性格 life", "疾病 health", "财物 wealth", "婚姻/合伙 marriage", "事业/名誉 career", "子女/恋爱 children", "远行 journey", "宗教/学问 religion", "对手/暗敌 enemy", "死亡/遗产 death"]},
        ],
        safe_defaults=[
            {"field": "questionType", "value": "custom", "meaning": "自定问类：按主问句判事项宫"},
            # 上游页面与 AI 挂载复算恒发这三项（GeomancyMain.js:1150-1158 / :808-817），换流派不改。
            {"field": "quesitedHouse", "value": None, "meaning": "所问宫缺省 = 问类预设宫（custom/life 一宫、wealth 二宫、career 十宫…）"},
            {"field": "readingScope", "value": "L3", "meaning": "读取范围 L3（不随流派回落；arabic_raml 内核默认 L2 也按 L3 发）"},
            {"field": "zodiacSystem", "value": "classical", "meaning": "黄道体系 classical（不随流派回落；european_planetary 内核默认行星黄道也按 classical 发）"},
        ],
        do_not_assume=["起卦时刻（须是真实起卦当下）", "所问内容"],
        output_contract=(
            "includeCatalog=true 附 [十六卦目录] 段（16 图形五行/主星/星座/性/象意总表，判读 grounding 用）。"
        ),
    ),
    "tarot": _policy(
        intent="塔罗 / tarot：以「起卦时刻」确定性抽牌（SHA-256(种子)→洗牌，同刻同盘可复现），按牌阵逐位取牌 + 正逆位 + 花色/元素/大牌统计 + Yes/No 定局与精华牌。",
        required_context=["起卦时刻 date/time（派生种子）", "所问 question", "牌阵 spread"],
        ask_if_missing=[
            {"field": "date/time", "question": "请提供起卦的日期与时间（塔罗以起卦时刻确定性抽牌）。也可直接给 seed。"},
            {"field": "question", "question": "想问什么？请给出具体问题。"},
            # 键名 = 引擎 SPREADS 真键（spreads.js）；此前给的 one / relationship 不存在，被静默换成 three。
            {"field": "spread", "question": "用哪种牌阵？", "options": ["三张·过去现在未来 three", "凯尔特十字 celtic", "单张 single", "关系 relation", "马蹄 horseshoe", "其它（见 guidance options_keys.spread）"]},
        ],
        safe_defaults=[
            {"field": "spread", "value": "three", "meaning": "默认三张牌阵（过去·现在·未来）"},
            {"field": "deck", "value": "rws", "meaning": "默认韦特-史密斯牌（RWS 78 张）"},
        ],
        do_not_assume=["起卦时刻/种子（决定抽到的牌，须真实）", "所问内容"],
    ),
    "lingqi": _policy(
        intent=(
            "灵棋经 / lingqi：以「起卦时刻」确定性掷十二棋（上四·中四·下四，一时掷之，古法「不可再擲」），"
            "上中下三层正面枚数成六十四卦之一，出 棋势（三才层位·耦敌·阴阳）/ 卦象 / 繇辞 / 诸家注（颜何陈刘）/ 课断 / 断诗。"
        ),
        required_context=["起卦时刻 date/time（派生种子，同刻同卦可复现）", "所问 question"],
        ask_if_missing=[
            {"field": "date/time", "question": "请提供起卦的日期与时间（灵棋经以起卦时刻确定性掷棋）。"},
            {"field": "question", "question": "想问什么？请给出具体问题。"},
            {
                "field": "category",
                "question": "属于哪一类问事？（只影响问类标注，不改卦）",
                "options": ["通用 general", "仕途 career", "求财 wealth", "婚姻 marriage", "疾病 health", "行人 travel", "官讼 lawsuit", "家宅 home"],
            },
        ],
        safe_defaults=[
            {"field": "category", "value": "general", "meaning": "默认按通用问类标注"},
        ],
        do_not_assume=["起卦时刻（决定掷出的卦，须真实）", "所问内容", "counts（冻结卦只在复算既有盘时传，不许自造）"],
    ),
    "xiaoliuren": _policy(
        intent="小六壬 / xiaoliuren：任取三数（月/日/时）作一顺数自大安起，推三传（主流六宫 / 道门九宫）。起课为冻结值——三数一经起出即不重起，改流派只重排判读。占时可起（农历月/日/时支序三数）。",
        required_context=["起课三数 nums 或 起课时刻 date/time", "所问 askEvent", "流派 school"],
        ask_if_missing=[
            {"field": "nums / date-time", "question": "如何起课？给三个数 nums=[月,日,时]，或提供起课的日期/时间（按占时以农历月/日/时支序起）。"},
            {"field": "askEvent", "question": "所问何事？请给出具体问题。"},
            {"field": "school", "question": "用哪一派？", "options": ["主流六宫 main（大安/留连/速喜/赤口/小吉/空亡，各宫吉凶直断）", "道门九宫 dao（+病符/桃花/天德，含五行生克与拜解）"]},
        ],
        safe_defaults=[{"field": "school", "value": "main", "meaning": "默认主流六宫（六宫直断，无五行生克）"}],
        do_not_assume=["起课三数/起课时刻（决定三传，须真实）", "所问内容"],
    ),
    "feigong": _policy(
        intent="飞宫小奇门 / feigong：时上起青龙，甲乘龙飞九宫，布八门九星，看主（日干）客（日支）宫。局为冻结值——起支一经定局即不重起。占时可起（时支作起支 + 日干支）。",
        required_context=["起支 qiMode/qiZhi 或 起局时刻 date/time", "日干支 dayGan/dayZhi", "所问 askEvent", "命宫 mingAge/mingGender（可选）"],
        ask_if_missing=[
            {"field": "qiZhi / date-time", "question": "如何起局？给起支（时支/选支/数取/年支），或提供起局的日期/时间（按占时以时支起局）。"},
            {"field": "dayGan/dayZhi", "question": "日干支是什么？（主=日干、客=日支落宫）。占时可由起局时刻自动取。"},
            {"field": "askEvent", "question": "所问何事？"},
            {"field": "koujing", "question": "河魁口径用哪说？", "options": ["正说 zheng", "异说 yi"]},
        ],
        safe_defaults=[
            {"field": "qiMode", "value": "hour", "meaning": "默认按占时（时支）起局"},
            {"field": "koujing", "value": "zheng", "meaning": "默认河魁正说"},
        ],
        do_not_assume=["起支/起局时刻（决定全局，须真实）", "日干支", "所问内容"],
    ),
    "xiaochengtu": _policy(
        intent="小成图 / xiaochengtu：得一卦排入洛书九宫，正推旁推演事，四象定性、数占/三分两分定应期，股市模式研判开收盘。卦为冻结值——起卦一经起出即不重起，改用宫只重排推演。",
        required_context=["起卦法 qiguaFa + 该法之输入", "用宫 yongGong", "所问 askEvent"],
        ask_if_missing=[
            {"field": "qiguaFa", "question": "用哪种起卦法？", "options": ["手动上下卦 manual（up/lo + 动爻）", "两数 number（upNum/loNum + 天地数/先天数）", "股价 stock（open/close，字符串保末尾0）", "大衍蓍草 dayan（须给 seed 或 6 个 counts）", "占时梅花卦 time（date/time 起）"]},
            {"field": "cast-input", "question": "请给该起卦法所需的输入（手动=上下卦、两数=两数、股价=开收价、大衍=种子/蓍草数、占时=日期时间）。"},
            {"field": "askEvent", "question": "所问何事？"},
        ],
        safe_defaults=[
            {"field": "yongGong", "value": 1, "meaning": "默认用宫 1（坎宫）"},
            {"field": "qiguaShu", "value": "tiandi", "meaning": "两数模式默认天地数"},
            {"field": "piKoujing", "value": "zheng", "meaning": "闢卦细判口径=正传（得配害·失配利，上游缺省）；yiwen=异文（得配利·失配害），只改 [四象] 的闢卦判读"},
        ],
        do_not_assume=["起卦法与起卦输入（决定卦，须真实；大衍禁静默随机）", "所问内容"],
    ),
    "guice": _policy(
        intent="皇极轨策 / guice：十二法之一起一卦，演策数（或轨数）成四位卦，取体用生克断吉凶，兼三要十应、元会运世、大定起数。卦为冻结值——起卦一经起出即不重起，改流派/十开关只重排断法。",
        required_context=["起卦法 qiguaFa + 该法之输入", "起卦时刻 date/time（元会运世/时方所需四柱）", "流派/十开关（可选）", "所问 askEvent"],
        ask_if_missing=[
            {"field": "qiguaFa", "question": "用哪种起卦法？", "options": ["年月日时 time", "报数 baoshu(nums)", "物数 wushu(wuShu)", "声音 shengyin(shengShu)", "字占 zizhan(text+shu+tones)", "丈尺 zhangchi / 尺寸 chicun", "为人 weiren / 自己 ziji(qu+shu)", "动物·五方 dongwu / 端法 duanfa(wuGuaNum+fangGuaNum)", "惊悟 jingwu(kind)"]},
            {"field": "cast-input + date/time", "question": "请给该起卦法所需的输入，并给起卦的日期/时间（元会运世、时方需四柱）。"},
            {"field": "school", "question": "用哪一流派预设？", "options": ["默认·心易发微 default", "梅花 meihua", "周易数 zhouyishu", "大定 dading", "自定 custom"]},
            {"field": "askEvent", "question": "所问何事？"},
        ],
        safe_defaults=[
            {"field": "qiguaFa", "value": "time", "meaning": "默认年月日时起例"},
            {"field": "school", "value": "default", "meaning": "默认心易发微本"},
        ],
        do_not_assume=["起卦法与起卦输入（决定卦，须真实）", "起卦时刻", "所问内容"],
    ),
    "zhengchuan": _policy(
        intent="神数正传 / zhengchuan：铁板/邵子/大定/六亲/铁算心易 五流派共一入口。除铁算心易（查询层）外，以生辰四柱（立春界年柱 + 农历月日）起数装卦、查条文、推大运死月。",
        required_context=["流派 school", "生辰 date/time/zone+lon+lat（除 xinyi 外）", "性别 gender", "流派专属参数"],
        ask_if_missing=[
            {"field": "school", "question": "用哪一流派？", "options": ["铁板神数 tieban", "邵子神数 shaozi(fatherAge/motherAge/yuan)", "大定数 dading(dadingYear)", "六亲数 liuqin(askHourZhi/env)", "铁算心易 xinyi(查询 item/sound/ke/gong)"]},
            {"field": "date/time/gender", "question": "请提供出生的日期、时间、时区（+经度）与性别（铁算心易查询层除外）。"},
            {"field": "school-params", "question": "流派专属：邵子的父母年龄/元(上中下)、大定的所推流年、六亲的演算时辰/环境。"},
        ],
        safe_defaults=[{"field": "school", "value": "tieban", "meaning": "默认铁板神数"}],
        do_not_assume=["生辰四柱（决定起数，须真实）", "流派", "性别"],
    ),
    # wangji/cetian 沿用神数家族策略；三法心易起卦与判词库见各自 schema 字段描述（xinyiMethod/textKey）。
    "wangji": SHENSHU_POLICY,
    "wuzhao": SHENSHU_POLICY,
    "taixuan": SHENSHU_ZONE_POLICY,
    "jingjue": SHENSHU_POLICY,
    "shenyishu": SHENSHU_POLICY,
    "shaozi": SHENSHU_GENDER_ZONE_POLICY,
    "tieban": SHENSHU_GENDER_ZONE_POLICY,
    # 鬼谷分定经：性别/时区只改 [起盘] 展示行（live 实测条文与四柱不变）→ 不问，免假闸门。
    "fendjing": SHENSHU_POLICY,
    # sync311 F5：北极（大运顺逆）/南极（大运干支）/蠢子数（乾/坤码）按性别出不同盘（live 实测），此前从不问。
    "beiji": SHENSHU_GENDER_POLICY,
    "nanji": SHENSHU_GENDER_POLICY,
    "chunzi": SHENSHU_GENDER_ZONE_POLICY,
    # 演禽 live 实测（v0.36.0 收尾）：输出无时区/经纬度行，上海↔乌鲁木齐、timeAlg 翻转全部逐字节相同——
    # 它只按钟表时间换农历 + 性别取用，问地点就是假闸门（§5.12「改参数结果必变」的反例）。
    "xianqin": SHENSHU_GENDER_POLICY,
    "cetian": SHENSHU_PLACE_POLICY,
    "qizhengkin": SHENSHU_PLACE_POLICY,
    "mundane": _policy(
        intent="世俗入宫盘 / mundane ingress：在某年某节气(春分/夏至/秋分/冬至)的精确入宫时刻排世俗盘。",
        required_context=["year", "入宫节气(春分/夏至/秋分/冬至)", "观测地点 lon/lat/zone"],
        ask_if_missing=[
            {"field": "year", "question": "要看哪一年的入宫盘？"},
            {"field": "ingressTerm", "question": "用哪个入宫节气？", "options": ["春分（白羊入宫·年盘默认）", "夏至", "秋分", "冬至"]},
            {"field": "location", "question": "观测地点的经纬度与时区？（通常用首都/关切地）"},
        ],
        safe_defaults=[
            {"field": "ingressTerm", "value": "春分", "meaning": "白羊入宫，世俗年盘的标准起点"},
            {
                "field": "mundaneType",
                "value": "ingress",
                "meaning": "入宫底盘；newmoon/fullmoon/solecl/lunecl/cycles/solunar/vedicmundane/mundanehorary 另加该盘型专属段",
            },
        ],
        do_not_assume=["year", "location"],
    ),
    "harmonic": _policy(
        intent="调波盘 / harmonic chart：本命各点黄经×调波数取调波位置，并找同频(合相)。",
        required_context=COMMON_BIRTH_FIELDS + ["harmonic number (调波数)"],
        ask_if_missing=[
            {"field": "date/time/place", "question": "请提供出生/事件日期、时间、时区和地点。"},
            {"field": "harmonic", "question": "用哪个调波数？", "options": ["H9（星阙默认）", "H5", "H7", "指定其它调波数（1–360）"]},
        ],
        safe_defaults=[
            {"field": "harmonic", "value": 9, "meaning": "星阙调波盘默认 H9"},
            {"field": "orb", "value": 2.0, "meaning": "同频合相容许度，星阙默认 2°"},
        ],
        do_not_assume=["harmonic number"],
    ),
    "chart": ASTRO_CHART_POLICY,
    "chart13": ASTRO_CHART_POLICY,
    "huangli": _policy(
        intent="老黄历日课：某一天的宜忌 / 值神值宿 / 彭祖百忌 / 吉神凶煞 / 冲煞胎神方位 / 时辰吉凶 / 物候 / 流年年神方位。",
        required_context=["date"],
        ask_if_missing=[
            {"field": "date", "question": "要看哪一天的黄历？（公历 YYYY-MM-DD）"},
        ],
        output_contract=["今日宜忌", "值神值宿", "冲煞·胎神·方位", "时辰吉凶"],
    ),
    "tongshu": _policy(
        intent="通书择日：按五流派各自的断语表判某日某用事的吉凶。",
        required_context=["date", "school", "event"],
        ask_if_missing=[
            {"field": "date", "question": "要择的是哪一天？（公历 YYYY-MM-DD）"},
            {
                # 键 = 引擎词表 tongshuSchools.js TONGSHU_SCHOOLS（上游 techniqueMountSettings.js:2086-2095）：
                # sanyuan 是「三元玄空大卦」、三垣列宿是 sanyuanliexiu（v0.40 前这里写反，照传 xuankong 得空结论）。
                "field": "school",
                "question": "用哪一派通书？（同一天在不同流派下结论可以完全相反，必须指定）",
                "options": [
                    "donggong 董公择日（星阙默认）",
                    "qimen 奇门叠数",
                    "sanyuanliexiu 三垣列宿",
                    "wutu 天元乌兔",
                    "sanyuan 三元玄空大卦",
                ],
                "values": ["donggong", "qimen", "sanyuanliexiu", "wutu", "sanyuan"],
            },
            {"field": "event", "question": "要择的用事是什么？（嫁娶 / 开市 / 安葬 / 动土 …）"},
        ],
        output_contract=["通书择日", "方法说明"],
    ),
    "babylon": _policy(
        intent="巴比伦占星：恒星黄道·毕宿锚盘（无宫位/无相位/无上升），解读装置是「位」三法与行星神性。",
        required_context=COMMON_BIRTH_FIELDS,
        ask_if_missing=[
            {"field": "date/time/place", "question": "请提供出生日期、时间、时区和地点。"},
            {
                "field": "scheme/solstice",
                "question": "实位派系与分至规范取哪一套？（派系改「位」的落点、分至规范改春分度数）",
                "options": ["swissA10 + A10（春分白羊 10°，默认）", "systemA", "systemB", "B8（春分白羊 8°）"],
            },
        ],
        output_contract=["起盘信息", "七曜按宫", "分至天狼星", "位三法", "行星神性", "微黄道"],
    ),
    # 十二分盘/龙盘：与本命盘同一套出生资料，无额外结果敏感设置 → 沿用同一策略。
    "chart12": ASTRO_CHART_POLICY,
    "draconic": ASTRO_CHART_POLICY,
    "relocation": _policy(
        intent="重置盘(relocation)：保留出生时刻，按新居住地重算十二宫与上升/中天（行星黄经不变）。",
        required_context=COMMON_BIRTH_FIELDS + ["relocLat", "relocLon"],
        ask_if_missing=[
            {"field": "date/time/place", "question": "请提供出生日期、时间、时区和出生地点。"},
            {
                "field": "relocLat/relocLon",
                "question": "重置到哪个地点？（迁居/旅居地的经纬度，如伦敦 51n30 / 0w07）",
            },
        ],
        output_contract=["起盘信息", "宫位宫头", "星与虚点", "相位"],
    ),
    "india_chart": _policy(
        intent="印度占星(Vedic)恒星黄道盘：分宫制全 24 制(indiaHsys 0–24) + 黄道岁差全 47(indiaAyanamsa)。",
        required_context=COMMON_BIRTH_FIELDS,
        ask_if_missing=[
            {"field": "date/time/place", "question": "请提供出生日期、时间、时区和地点。"},
            {
                "field": "indiaHsys",
                "question": "分宫制取哪一种？（共 24 制，缺省整宫/Rashi）",
                "options": [
                    "0 整宫/Rashi（默认）",
                    "5 等宫 / Lagna Bhava",
                    "7 Sripati（Bhāva Chalit）",
                    "3 KP / Placidus",
                    "其它（2 Regio / 4 Koch / 6 Vehlow / 8 Alcabitus / 10 Campanus / 13 Topocentric 等，见 INDIA_HOUSE_SYSTEM_LABELS）",
                ],
            },
            {
                "field": "indiaAyanamsa",
                "question": "黄道岁差(ayanāṃśa)取哪一制？（共 47 制，缺省 lahiri）",
                "options": [
                    "lahiri（默认）",
                    "raman",
                    "krishnamurti / KP",
                    "yukteshwar / true_citra / fagan_bradley",
                    "其它（共 47 制，见 SIDEREAL_AYANAMSA_LABELS）",
                ],
            },
        ],
        safe_defaults=[
            {"field": "indiaHsys", "value": 0, "meaning": "整宫制 / Rashi"},
            {"field": "indiaAyanamsa", "value": "lahiri", "meaning": "印占缺省 Lahiri"},
            {"field": "ad", "value": 1, "meaning": "公历纪年"},
        ],
        do_not_assume=["birth time", "birthplace", "timezone"],
    ),
    "relative": _policy(
        intent="Relationship / relative chart.",
        required_context=["inner person birth data", "outer person birth data"],
        ask_if_missing=[
            {"field": "inner/outer", "question": "请分别提供双方出生日期、时间、时区和地点。"},
            # 上游 AstroRelative.js hook 表 relative 0–4（此前只写「星阙默认」）。
            {
                "field": "relative",
                "question": "关系盘类型用哪一种？",
                "options": ["比较盘（默认）", "组合盘", "影响盘", "时空中点盘", "马克斯盘"],
                "values": [0, 1, 2, 3, 4],
            },
        ],
        safe_defaults=[{"field": "relative", "value": 0, "meaning": "比较盘（星阙默认）"}],
        do_not_assume=["either party's birth time/place"],
    ),
    "solarreturn": SOLARRETURN_POLICY,
    "lunarreturn": SOLARRETURN_POLICY,
    "solararc": SOLARARC_POLICY,
    "givenyear": SOLARRETURN_POLICY,
    "profection": PROFECTION_POLICY,
    "pd": PD_POLICY,
    "pdchart": PDCHART_POLICY,
    "zr": ZR_POLICY,
    "firdaria": PREDICTIVE_POLICY,
    "decennials": _policy(
        intent="Decennials / 十年大运 timeline.",
        required_context=COMMON_BIRTH_FIELDS,
        ask_if_missing=[
            {"field": "birth data", "question": "请提供出生日期、时间、时区和地点。"},
            {"field": "timeline settings", "question": "十年大运算法设置是否沿用星阙默认？", "options": ["沿用默认", "指定起算/历法/排序/日法"]},
        ],
        safe_defaults=[
            {"field": "startMode", "value": "sect_light", "meaning": "sect light"},
            {"field": "orderType", "value": "zodiacal", "meaning": "zodiacal order"},
            {"field": "dayMethod", "value": "valens", "meaning": "Valens day method"},
        ],
        do_not_assume=["birth time"],
    ),
    "otherbu": _policy(
        intent="西洋游戏 / 占星骰子。",
        required_context=["question", "sign/house/planet if not rolling randomly"],
        ask_if_missing=[
            {"field": "question", "question": "这次占问的问题是什么？"},
            {"field": "dice values", "question": "骰子结果由用户指定还是需要随机/默认？", "options": ["用户指定星座/宫位/行星", "使用默认示例", "先询问用户掷骰结果"]},
        ],
        safe_defaults=[
            {"field": "sign/house/planet", "value": "Aries/0/Sun", "meaning": "placeholder default; should not be used as real divination unless user accepts"}
        ],
        do_not_assume=["random dice result"],
    ),
    "ziwei_birth": _policy(
        intent="紫微斗数命盘（四化流派 + 22 个传本/排盘开关 + 流派叠层，键表见 options_keys；任一传本开关非缺省即走本地 ZiweiCalc 重排，同星阙）。",
        required_context=COMMON_BIRTH_FIELDS + ["gender"],
        ask_if_missing=[
            {"field": "birth data", "question": "请提供出生日期、时间、时区和地点。"},
            {"field": "gender", "question": "紫微需要性别，请选择。", "options": ["男", "女"]},
            {"field": "after23NewDay/lateZiHourUseNextDay/timeAlg", "question": "子时换日、晚子时时柱和时间算法是否沿用星阙默认？", "options": ["沿用默认", "指定"]},
            {
                "field": "sihuaSchool/传本",
                "question": "四化流派与传本设置（大限跨度/天马/星集/三盘/闰月/晚子时/定年界线/火铃/亮度…）是否沿用星阙默认？",
                "options": ["沿用默认（通用·飞星 + 全缺省传本）", "指定流派或传本（键见 options_keys）"],
            },
        ],
        safe_defaults=[
            {"field": "after23NewDay", "value": 1, "meaning": _AFTER23_DEFAULT_MEANING},
            {"field": "sihuaSchool", "value": "beipai", "meaning": "星阙默认：通用·飞星四化"},
        ],
        do_not_assume=["gender", "birth time", "non-default sihuaSchool / 传本"],
    ),
    "ziwei_rules": _policy(
        intent="Fetch Ziwei rule metadata.",
        required_context=[],
        ask_if_missing=[],
        safe_defaults=[{"field": "request", "value": {}, "meaning": "rules have no required input"}],
    ),
    "bazi_birth": _policy(
        intent="八字命盘（同星阙八字页：本地 lunar.js 引擎起盘，公元前等域外日期与 byLon/adjustJieqi 走 Java；盘法/流派键见 options_keys）。",
        required_context=COMMON_BIRTH_FIELDS,
        ask_if_missing=[
            {"field": "birth data", "question": "请提供出生日期、时间、时区和地点。"},
            {"field": "timeAlg/after23NewDay/lateZiHourUseNextDay", "question": "真太阳时、子时换日、晚子时时柱是否沿用星阙默认？", "options": ["沿用默认", "指定设置"]},
            {
                "field": "godKeyPos/minggongMethod/school",
                "question": "神煞主位、命宫起法、断命流派是否沿用星阙默认？",
                "options": ["沿用默认（神煞按年柱 · 命宫通行版 · 传统综合）", "指定（键见 options_keys）"],
            },
        ],
        # 上游 BaZi.js:961-985 genParams + techniqueMountSettings.js:1692-1740 缺省。
        safe_defaults=[
            {"field": "timeAlg", "value": 0, "meaning": "星阙默认：真太阳时"},
            {"field": "after23NewDay", "value": 1, "meaning": _AFTER23_DEFAULT_MEANING},
            {"field": "godKeyPos", "value": "年", "meaning": "星阙默认：按年柱查神煞"},
            {"field": "minggongMethod", "value": "tongxing", "meaning": "星阙默认：命宫通行版"},
            {"field": "byLon", "value": False, "meaning": "星阙默认（给 true 则整盘走 Java，本地引擎无此算法）"},
        ],
        do_not_assume=["birth time", "timezone", "birthplace"],
    ),
    "bazi_direct": _policy(
        intent="八字大运/流年/direct flow（与 bazi_birth 同源本地引擎，盘法/流派键见 options_keys）。",
        required_context=COMMON_BIRTH_FIELDS + ["gender"],
        ask_if_missing=[
            {"field": "birth data", "question": "请提供出生日期、时间、时区和地点。"},
            {"field": "gender", "question": "排大运需要性别，请选择。", "options": ["男", "女"]},
            {"field": "adjustJieqi", "question": "节气校正是否沿用星阙默认？（星阙八字页已隐藏此项：本地引擎未实现；选校正则整盘走 Java）", "options": ["沿用默认", "指定校正"]},
        ],
        safe_defaults=[
            {"field": "adjustJieqi", "value": False, "meaning": "星阙默认（不调整节气）"},
            {"field": "after23NewDay", "value": 1, "meaning": _AFTER23_DEFAULT_MEANING},
        ],
        do_not_assume=["gender"],
    ),
    "jieqi_year": _policy(
        intent="节气年盘。",
        required_context=["year", "zone", "lat/lon"],
        ask_if_missing=[
            {"field": "year", "question": "要生成哪一年的节气盘？"},
            {"field": "location", "question": "地点/经纬度用哪里？"},
            {"field": "jieqis", "question": "要全部节气还是指定节气？", "options": ["全部", "指定节气"]},
        ],
        safe_defaults=[{"field": "jieqis", "value": None, "meaning": "all configured/default jieqis"}],
    ),
    "nongli_time": _policy(
        intent="农历/干支时间。",
        required_context=["date", "time", "zone", "lon", "lat when available"],
        ask_if_missing=[
            {"field": "date/time", "question": "请提供要换算的日期、时间和时区。"},
            {"field": "location", "question": "请提供经度；如需真太阳时也请提供纬度。"},
            {"field": "after23NewDay/lateZiHourUseNextDay/timeAlg", "question": "子时换日、晚子时时柱和时间算法是否沿用默认？", "options": ["沿用默认", "指定"]},
        ],
        do_not_assume=["timezone", "longitude"],
    ),
    "calendar_month": _policy(
        intent="黄历/万年历：整月农历/干支/节气/朔望月历，可选选中日详情。",
        required_context=["date (月份内任一天)", "zone"],
        ask_if_missing=[
            {"field": "date", "question": "要查询哪个月份的黄历？请给出该月内任一公历日期。"},
            {"field": "zone", "question": "用哪个时区？"},
            {"field": "lon", "question": "历算经度沿用东经120度标准，还是指定当地经度？", "options": ["沿用默认 120e00", "指定经度"]},
        ],
        safe_defaults=[{"field": "lon", "value": "120e00", "meaning": "东经 120 度标准历算经度（节气/朔望真时刻按此）"}],
        do_not_assume=["timezone"],
    ),
    "gua_desc": _policy(
        intent="卦辞/卦义查询。",
        required_context=["name list"],
        ask_if_missing=[{"field": "name", "question": "要查询哪些卦名？请给出一个或多个卦名。"}],
        do_not_assume=["hexagram name"],
    ),
    "gua_meiyi": _policy(
        intent="梅易卦义查询。",
        required_context=["name list"],
        ask_if_missing=[{"field": "name", "question": "要查询哪些卦名？请给出一个或多个卦名。"}],
        do_not_assume=["hexagram name"],
    ),
}

# 三式口径词表挂到各工具策略上（horosa_agent_guidance 按工具回报 `options_keys`）：tools/list 字节预算吃紧，
# 长词表不进 schema 描述，住这里（sanshi chunk）。
for _tool_name, _options_text in _SANSHI_OPTIONS_KEYS.items():
    TOOL_GUIDANCE[_tool_name]["options_keys"] = {"options": _options_text}


# ── 命理盘法/流派键表（v0.40 mingli）──────────────────────────────────────────────────────────
# 这些键已在输入模型里声明（MCP 顶层按名直传），但**不进 tools/list 广告层**（x-horosa-hidden，预算见
# verify_mcp_list_budget）——键表与取值只在这里给。取值的唯一真值是引擎自带词表（紫微 = vendored
# ziweiOptions.js 各 *_OPTIONS；八字 = BaZi.js genParams + techniqueMountSettings.js:1692-1740；宿法 = guolaoData
# SU28_MODE_LABEL），认不出的值按缺省起盘并进 warnings；这里的文字只是说明，漂移不影响校验。
_CN_ZONE_KEY = "cnUnifiedZone: 缺省 true=Asia/Urumqi 且日期≥1949-10-01 按北京时间（Asia/Shanghai）折算；false=保留新疆地理时区（或直接给 +06:00）"
_MINGLI_OPTIONS_KEYS: dict[str, dict[str, str]] = {
    "ziwei_birth": {
        "sihuaSchool": "beipai 通用·飞星（缺省）| zhongzhou 中州派 | quanshu 全书系 | beixiang 北派(天相忌) | custom（配 sihuaCustomTable）",
        "sihuaCustomTable": '{"甲":["廉贞","破军","武曲","太阳"],…} 每干 [禄,权,科,忌]；旧入参 sihua 等同 custom',
        "daxianSpan": "10（缺省）| ju 局数年(钦天)",
        "tianmaBasis": "month（缺省）| year 年支三合马",
        "starSet": "full（缺省）| north18 精简18星(河洛)",
        "sanPan": "tian（缺省）| di 地盘(身宫起) | ren 人盘(福德起)",
        "shangShi": "fixed（缺省）| yinyang 中州阴阳互换",
        "leapMonth": "mid_split（缺省）| next | prev | split_days | solar_term | split_star_month",
        "lateZi": "global（缺省=跟随 after23NewDay/lateZiHourUseNextDay）| zi_chu | midnight_split | zi_zheng | dual",
        "yearBoundary": "lunar_1_1 正月初一（缺省）| lichun 立春",
        "huoling": "sanhe（缺省）| nanpai",
        "kongNaming": "modern 地空地劫（缺省）| book 天空地劫",
        "brightnessSource": "zi_jian（缺省）| quanshu | quanshu_full | custom（配 brightnessCustomTable {星:{支:档}}）",
        "lifeMasterBy": "year_branch（缺省）| ming_branch",
        "changshengStart": "shui_tu（缺省）| huo_tu",
        "changshengDirection": "yinyang（缺省）| always_forward",
        "kongwangStyle": "double（缺省）| single",
        "kuiYue": "jia_wu_geng（缺省）| geng_ma_hu | liu_xin_hu_ma | geng_xin_hu_ma",
        "liuYueBasis": "doujun（缺省）| taisui（只影响 [运限] 流月）",
        "liunianSihuaGan": "year_gan（缺省）| ming_gong_gan（只影响 [运限] 流年）",
        "xiaoxianMode": "'0' 男顺女逆（缺省）| '1' 阳男阴女顺（= ziweiXiaoxianYinyang；只影响流年段小限行）",
        "开关(0/1，缺省 0)": "childLimit, zhongxian, huoPan, qishuWei, borrowPalace, taiSuiRuGua, flowLuanXi, flowHuoLing, flowShenshaOnChart",
        "taiSuiRelatives": "「午:母:female 子」或 [{branch,role,sex}]（配 taiSuiRuGua=1）",
        "period": "{daxian:[宫序0–11], liunian:[公历年], liuyue:[1–12], liuri:[1–31], liushi:[0–11]} → [运限] 段",
        "规则": "任一传本开关非缺省（亮度/命主/流月/流年四化/小限/叠层开关除外）即本地 ZiweiCalc 重排盘并重算格局（同星阙）；旧入参 schools{…} 仍收，平铺键优先",
        "cnUnifiedZone": _CN_ZONE_KEY,
    },
    "bazi_birth": {
        "godKeyPos": "年（缺省）| 日 | 年日",
        "minggongMethod": "tongxing 通行版（缺省）| shufa 子平数法",
        "dayunPrecision": "precise 精确（缺省）| integer 取整岁（[大运] 起运行）",
        "school": "zonghe 传统综合（缺省）| fuyi | geju | tiaohou | bingyao | tongguan | mangpai | nayin（只切 [格局·用神] 主用流派标注）",
        "ageStyle": "nominal 虚岁（缺省）| real 周岁（[大运] 小运表年龄列）",
        "zodiacBoundary": "lichun 立春（缺省）| lunar 正月初一（[起盘信息] 生肖行）",
        "cangVersion/fenyeVersion": "common（缺省）| fenye 分野加权 / fajue 法诀版",
        "phaseType": "0 长生火土同（缺省）| 1 水土同 | 2 阳顺阴逆",
        "timeAlg": "0 真太阳时（缺省）| 1 直接时间 | 3 平太阳时（2 春分定卯时上游未实现，报错）",
        "byLon/adjustJieqi": "true → 整盘走 Java /bazi/*（本地引擎不实现；五行力量等本地派生段随之不出）",
        "period": "{liunian:[公历年], liuyue:[1–12], liuri:[公历日], liushi:[0–11]} → [多运限·指定时段]",
        "cnUnifiedZone": _CN_ZONE_KEY,
    },
    "suzhan": {
        "doubingSu28": "0 荀爽距星（缺省）| 1 斗柄定房法 | 2 回归今宿 | 3 回归古制开禧 | 4 恒星制 | 5 恒星制·现代天赤 | 6 授时历古法 | 7 赤道回归(元明) | 8 赤道回归(实时)",
        "houseStartMode": "0 八字公式起盘（缺省，读 Java /chart 农历时支）| 1 ASC 起盘",
        "nongliTimeAlg": "0 真太阳时（缺省）| 1 直接时间 | 3 平太阳时（只作用于八字公式所读的农历时支）",
        "szchart/szshape": "外盘 0–7 / 盘型 0 圆 1 方：只进 [起盘信息] 标签行（缺省不出该行，同星阙）",
        "hsys": "缺省 1（星阙页面缺省宫制）",
        "cnUnifiedZone": _CN_ZONE_KEY,
    },
    "jieqi_year": {
        "doubingSu28": "0–8（缺省 0；同 suzhan）",
        "siderealAyanamsa": "zodiacal=1 时生效：逐节气 /chart 重排分至盘（Python /jieqi/year 不读此键）",
        "after23NewDay": "不适用：[二十四节气] 四柱由 Java 以 after23NewDay=false 硬编码起算（上游同）",
    },
    "nongli_time": {
        "timeAlg": "0 真太阳时（缺省）| 1 直接时间（/nongli/time 只认这两档，其余夹回 0）",
        "cnUnifiedZone": _CN_ZONE_KEY,
    },
}
_MINGLI_OPTIONS_KEYS["bazi_direct"] = _MINGLI_OPTIONS_KEYS["bazi_birth"]
for _tool, _keys in _MINGLI_OPTIONS_KEYS.items():
    TOOL_GUIDANCE[_tool]["options_keys"] = _keys


REPORT_AND_MEMORY_GUIDANCE: dict[str, dict[str, Any]] = {
    "horosa_report_template": _policy(
        intent="Prepare a structured report template for an existing run.",
        required_context=["run_id", "tool_name when a run has multiple results"],
        ask_if_missing=[
            {"field": "run_id", "question": "要基于哪一次计算生成报告？请提供 run_id 或先查询 memory。"},
            {"field": "tool_name", "question": "如果这个 run 有多个工具结果，要为哪个工具生成报告？"},
        ],
    ),
    "horosa_report_render": _policy(
        intent="Render JSON/DOCX/PDF report artifact.",
        required_context=["run_id", "format", "AI analysis text/structured answer for final human report"],
        ask_if_missing=[
            {"field": "format", "question": "报告格式要哪一种？", "options": ["PDF", "DOCX", "JSON"]},
            {"field": "ai_answer_text/ai_report", "question": "是否已经有针对用户问题的 AI 解读正文？没有的话先写解读再渲染。"},
        ],
        safe_defaults=[{"field": "format", "value": "pdf", "meaning": "默认 PDF；用户要可编辑文档时用 DOCX"}],
    ),
    "horosa_memory_query": _policy(
        intent="Search local Horosa memory.",
        required_context=["one of run_id/tool/entity/text/artifact_kind/time range"],
        ask_if_missing=[{"field": "query", "question": "要按 run_id、技法、对象名、关键词还是 artifact 类型检索？"}],
    ),
    "horosa_memory_show": _policy(
        intent="Show one local memory run.",
        required_context=["run_id"],
        ask_if_missing=[{"field": "run_id", "question": "要查看哪一次记录？请提供 run_id，或先用 memory_query 查找。"}],
    ),
}


# 非神数工具的 options 键说明（键集锚引擎；此处只是给 agent 看的索引，取值裁决在引擎侧）。
_EXTRA_OPTIONS_DOC: dict[str, dict[str, str]] = {
    "tarot": {
        "spread": "牌阵键（引擎 SPREADS）：single/three/three_sit/three_mbs/three_pcs/three_choice/horseshoe/celtic/relation/croix/tree_of_life/zodiac/annual…；须在该牌组 caps.spreads 允许表内",
        "verdictMode": "定局法（YESNO_MODES）：majority/orientation/single/numeric/polarity/weighted_center/anchor/single3",
        "options.meaningSystem": "manual/waite/degrees", "options.reversalMode": "stored/blocked/internal/opposite/reduced/excess/delayed/projection/misuse/negation/breakthrough/re_words/retreat",
        "options.timingMethod": "suit_unit/major_number/major_zodiac/decan_full/ace_hunt", "options.timingUnit": "天/周/月",
        "options.<其余>": "showCorrespondences/sig/suitElementSwap/ookTable/reversalGen/crossingUpright/quintMode/showBottomCard/edVersion/astroModern/majorsOverlay/showCutCard/includeBlank/courtElementSystem/courtZodiacSystem（引擎 resolveSettings 键集；值不被接受即报错）",
        "seed": "显式种子；缺省 = name|date|time|lat|lon（上游「生辰」种子）",
    },
    "geomancy": {
        "options.housePlacement": "图形入宫：sequential/angular/golden_dawn",
        "options.castNumbers": "报数起卦：十六个正整数（奇=单点/偶=双点，母一至母四火风水土序）；options.seed 定辅助随机（缺省=时间种子）",
        "options.planetaryChart": "行星地占盘开关（+planetaryChartZodiac classical/… · planetaryChartNodes · planetaryChartExtras）",
        "options.ascSource / houseProjection": "real_chart / real_ephemeris 按所问时地起真实上升/真实星历（date/time/zone/lat/lon 已随请求下发）",
    },
    "wuzhao": {
        "随机诸式": "dunhuang / qian(qianAuto=true) 按 castSeed 定兆（缺省=起课时刻 yyyyMMddHHmm mod 1e9，同刻同兆）；day/hour/minute/tang 须 manual=true(+manualSplits) 方可复现，否则照上游回落干支起例并在 [揲筮] 写复现说明；存档复现：mode=zhushu + zhaoNums=存档六位兆数",
    },
}


def _with_common_fields(tool_name: str, policy: dict[str, Any]) -> dict[str, Any]:
    definition = TOOL_DEFINITIONS.get(tool_name)
    result = deepcopy(policy)
    if definition is not None:
        fields = definition.input_model.model_fields
        result["tool_name"] = tool_name
        result["mcp_name"] = definition.mcp_name
        result["technical_required_fields"] = [name for name, field in fields.items() if field.is_required()]
        result["accepted_fields"] = sorted(fields)
        result["description"] = definition.description
        result["input_contract"] = build_tool_input_contract(tool_name)
    # options_keys 恒为 {键: 说明}：神数逐技法键表（sync311 F6；认不出的键回执 data.params_ignored）、非神数 options 索引、
    # 西占隐藏旋钮与引擎长词表（western_options_doc）、三式口径（策略里预置为 {"options": 文本}）——多源按键合并。
    doc_sources = (options_doc(tool_name), _EXTRA_OPTIONS_DOC.get(tool_name), western_options_doc(tool_name))
    for doc in doc_sources:
        if doc:
            result["options_keys"] = {**(result.get("options_keys") or {}), **doc}
    result["hard_gate"] = {
        "enabled": tool_name not in PREFLIGHT_EXEMPT_TOOLS,
        "pass_condition": "Provide `agent_confirmed_settings: true` after asking the user, or `defaults_accepted: true` when the user explicitly accepts Xingque/default settings.",
        "confirmation_fields": CONFIRMATION_FIELDS,
        "failure_code": "agent_guidance.required",
    }
    result["agent_should"] = [
        "ask_missing_result_changing_options_before_call",
        "use_safe_defaults_only_with_disclosure_or_user_acceptance",
        "store final answer with memory tools when user asks for follow-up continuity",
    ]
    return result


def _model_field_contract(tool_name: str) -> dict[str, Any]:
    definition = TOOL_DEFINITIONS[tool_name]
    fields = definition.input_model.model_fields
    return {
        "technical_required_fields": [name for name, field in fields.items() if field.is_required()],
        "accepted_fields": sorted(fields),
    }


def build_tool_input_contract(tool_name: str) -> dict[str, Any]:
    """Return the user-facing input contract exposed through CLI, MCP, and docs."""

    if tool_name not in TOOL_DEFINITIONS:
        return {
            "schema": INPUT_CONTRACT_SCHEMA,
            "ok": False,
            "error": {"code": "input_contract.unknown_tool", "message": f"Unknown tool: {tool_name}"},
        }

    definition = TOOL_DEFINITIONS[tool_name]
    policy = TOOL_GUIDANCE.get(tool_name)
    contract: dict[str, Any] = {
        "schema": INPUT_CONTRACT_SCHEMA,
        "ok": True,
        "tool_name": tool_name,
        "mcp_name": definition.mcp_name,
        "description": definition.description,
        "confirmation_required": tool_name not in PREFLIGHT_EXEMPT_TOOLS,
        "confirmation_fields": CONFIRMATION_FIELDS if tool_name not in PREFLIGHT_EXEMPT_TOOLS else [],
        "technical": _model_field_contract(tool_name),
        "user_context_required": deepcopy(policy.get("must_have_context", [])) if policy else [],
        "ask_if_missing": deepcopy(policy.get("ask_if_missing", [])) if policy else [],
        "safe_defaults": deepcopy(policy.get("safe_defaults", [])) if policy else [],
        "do_not_assume": deepcopy(policy.get("do_not_assume", [])) if policy else [],
        "output_contract": deepcopy(policy.get("output_contract", [])) if policy else [],
        "example_payload": {},
    }
    if tool_name in PREDICTIVE_INPUT_CONTRACTS:
        predictive = deepcopy(PREDICTIVE_INPUT_CONTRACTS[tool_name])
        contract["predictive_contract"] = predictive
        contract["required_for_real_call"] = predictive["required_fields"]
        contract["target_fields"] = predictive["target_fields"]
        contract["output_contract"] = predictive["output_contract"]
        contract["example_payload"] = predictive["example_payload"]
    elif policy:
        contract["required_for_real_call"] = contract["technical"]["technical_required_fields"]
    return contract


def build_tool_docstring(tool_name: str) -> str:
    """Build a concise MCP-visible docstring with the same input contract as the CLI."""

    definition = TOOL_DEFINITIONS[tool_name]
    contract = build_tool_input_contract(tool_name)
    lines = [definition.description]
    if contract.get("confirmation_required"):
        lines.append(
            "澄清闸：先向用户确认会改变结果的设置，再传 `agent_confirmed_settings=true` 或 "
            "`defaults_accepted=true` 并附 `clarification_notes`。 / Agent gate: confirm result-changing "
            "settings with the user first, then pass `agent_confirmed_settings=true` or "
            "`defaults_accepted=true` with `clarification_notes`."
        )
    required = contract.get("required_for_real_call") or contract.get("technical", {}).get("technical_required_fields", [])
    if required:
        lines.append("真实调用必填 / Required input: " + ", ".join(str(item) for item in required) + ".")
    target_fields = contract.get("target_fields")
    if isinstance(target_fields, dict) and target_fields:
        field_notes = "; ".join(f"{key}: {value}" for key, value in list(target_fields.items())[:5])
        lines.append("时点 / 目标字段 · Timing/target fields: " + field_notes)
    output_contract = contract.get("output_contract") or []
    if output_contract:
        lines.append("预期输出段 / Expected output sections: " + ", ".join(str(item) for item in output_contract) + ".")
    return "\n".join(lines)


# 软件用法帮助语料：随 guidance 返回，供 agent 据实回答「怎么装/怎么用/怎么出报告」类问题。
SOFTWARE_USAGE_HELP: dict[str, list[str]] = {
    "install": [
        "安装：仓库目录执行 `uv run horosa-skill install`（约 730MB 下载，支持断点续传与 HOROSA_RUNTIME_MIRROR 镜像）。",
        "升级：`uv run horosa-skill upgrade`（已最新则秒退不重下）；卸载：`uv run horosa-skill uninstall`（默认只打印将删清单）。",
        "体检：`uv run horosa-skill doctor`（环境/磁盘/端口/文件）；活体验证：`uv run horosa-skill selfcheck`（起盘→存→读回）。",
    ],
    "workflow": [
        "起盘：直接调技法工具（如 horosa_cn_qimen），结果读 data.export_snapshot.export_text 与 sections。",
        "出报告：已有 run_id 时用 horosa_report_render(run_id, format, ai_report)——ai_report 会自动写回记忆；一步到位用 horosa_report_from_tool（注意会重新起盘）。",
        "找历史：horosa_memory_query 按人名/技法/日期/全文组合检索（limit/offset 分页），horosa_memory_show(run_id) 取完整记录。",
        "省 token：技法工具可传 response_view='titles'（只回段标题）或 'sections'（段标题+正文），完整结果始终已存档。",
    ],
    "boundaries": [
        "本产品 local-first：结果全部来自本机运行时，不依赖远程数据库或外部服务；缺字段先怀疑本地输入/运行时而非网络服务。",
        "禁止手算这些技法（shell/Python/记忆公式都不行）——只以工具返回的 export_snapshot 为准。",
    ],
}


def technique_index() -> dict[str, list[str]]:
    """技法名索引：{domain: [tool_name, …]}。约 2.5 KB，只有名字没有描述。

    用在 `tool.unknown` 的 details 里做**自愈式报错**：模型点错名字时当场拿到全部合法名字，
    不必回头去读某个工具的描述。这让 `horosa_tool_run` 的描述得以从 4145 字符降到 1024 以内
    （OpenAI 的 function 描述上限；超了会被拒或截断，而它是精简面下抵达全部技法的唯一通道）。
    """
    groups: dict[str, list[str]] = {}
    for name, definition in TOOL_DEFINITIONS.items():
        groups.setdefault(str(definition.domain), []).append(name)
    return {domain: sorted(names) for domain, names in sorted(groups.items())}


def build_technique_catalog(*, label_chars: int = 72) -> str:
    """技法一行索引（按 domain 分组）——精简 MCP 模式下拼进 tool_run 的 docstring，资源面给全文。

    每行 `name — 描述首句`（截到 label_chars 字），完整输入契约经 horosa_agent_guidance 获取。
    精简面预算 ≤30 KB（verify_mcp_list_budget）：tool_run 用 label_chars=28（约 6 KB），资源用 72。
    """
    groups: dict[str, list[str]] = {}
    for definition in TOOL_DEFINITIONS.values():
        first_sentence = str(definition.description or "").split(". ")[0].split("。")[0].strip()
        if len(first_sentence) > label_chars:
            first_sentence = first_sentence[: label_chars - 1] + "…"
        groups.setdefault(definition.domain, []).append(f"  {definition.name} — {first_sentence}")
    lines = ["Available techniques (call by tool_name; full input contract via horosa_agent_guidance):"]
    for domain in sorted(groups):
        lines.append(f"[{domain}]")
        lines.extend(sorted(groups[domain]))
    return "\n".join(lines)


def _filter_provided_questions(ask_if_missing: list[dict[str, Any]], payload: dict[str, Any]) -> list[dict[str, Any]]:
    """闸问题按 payload 已提供字段过滤：用户已给的信息不再重复追问。

    条目 field 形如 "date/time" 或 "after23NewDay/timeAlg"（斜杠=同组多字段）；组内字段全部
    已显式提供（非 None）才略过该问。别名 location≈lat/lon，birth/date≈date。
    """
    provided = {key for key, value in payload.items() if value is not None}
    alias_groups = {
        "location": {"lat", "lon", "gpsLat", "gpsLon", "location"},
        "place": {"lat", "lon", "gpsLat", "gpsLon", "location"},
        "birth": {"date"},
    }
    filtered: list[dict[str, Any]] = []
    for item in ask_if_missing:
        if not isinstance(item, dict):
            filtered.append(item)
            continue
        fields = [part.strip() for part in str(item.get("field") or "").split("/") if part.strip()]
        if not fields:
            filtered.append(item)
            continue
        def _has(field: str) -> bool:
            if field in provided:
                return True
            aliases = alias_groups.get(field)
            return bool(aliases and aliases & provided)
        if all(_has(field) for field in fields):
            continue
        filtered.append(item)
    return filtered


def validate_agent_preflight(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Return a structured gate result before a calculation tool is allowed to run."""

    if tool_name in PREFLIGHT_EXEMPT_TOOLS:
        return {"ok": True, "tool_name": tool_name, "enforced": False}
    override = _clarify_override(tool_name)
    if override is not None:
        return {"ok": True, "tool_name": tool_name, "enforced": False, "mode": override}
    is_dispatch = tool_name in {"dispatch", "horosa_dispatch"}
    if tool_name not in TOOL_GUIDANCE and not is_dispatch:
        return {"ok": True, "tool_name": tool_name, "enforced": False}

    confirmed = payload.get("agent_confirmed_settings") is True
    defaults_accepted = payload.get("defaults_accepted") is True
    if confirmed or defaults_accepted:
        return {
            "ok": True,
            "tool_name": tool_name,
            "enforced": True,
            "mode": "agent_confirmed_settings" if confirmed else "defaults_accepted",
        }

    if is_dispatch:
        ask_if_missing = [
            {"field": "target technique", "question": "你想调用哪一种技法？", "options": ["星盘", "大六壬", "奇门", "八字", "紫微", "其他"]},
            {"field": "date/time", "question": "使用当前时间，还是指定时间？"},
            {"field": "location", "question": "地点、经纬度、时区用哪里？"},
            {"field": "question", "question": "这次要问的具体事情是什么？"},
        ]
        safe_defaults = [{"field": "routing", "value": "dispatch selection", "meaning": "仅在用户确认目标和默认设置后自动选择工具"}]
        do_not_assume = ["Do not dispatch to a calculation tool before confirming result-changing settings."]
    else:
        guidance = build_agent_guidance(tool_name=tool_name)
        policy = guidance["tools"][tool_name]
        ask_if_missing = _filter_provided_questions(policy.get("ask_if_missing", []), payload)
        safe_defaults = policy.get("safe_defaults", [])
        do_not_assume = policy.get("do_not_assume", [])
    return {
        "ok": False,
        "tool_name": tool_name,
        "enforced": True,
        "code": GATE_FAILURE_CODE,
        "message": (
            "This Horosa tool is protected by the agent guidance gate. "
            "Ask the user for missing result-changing settings first, or pass "
            "`agent_confirmed_settings: true` / `defaults_accepted: true` after explicit confirmation."
        ),
        "ask_if_missing": ask_if_missing,
        "safe_defaults": safe_defaults,
        "do_not_assume": do_not_assume,
        "confirmation_fields": CONFIRMATION_FIELDS,
        "agent_recovery": _agent_recovery(
            tool_name=tool_name,
            ask_if_missing=ask_if_missing,
            safe_defaults=safe_defaults,
            do_not_assume=do_not_assume,
            reason="missing_agent_confirmation",
        ),
    }


def build_validation_recovery(
    *,
    operation_name: str,
    errors: list[dict[str, Any]],
    tool_name: str | None = None,
) -> dict[str, Any]:
    """Build a user-askable recovery contract for incomplete or invalid payloads."""

    target = tool_name or operation_name
    if tool_name in TOOL_GUIDANCE or tool_name in {"dispatch", "horosa_dispatch"}:
        gate = validate_agent_preflight(tool_name, {})
        ask_if_missing = gate.get("ask_if_missing", [])
        safe_defaults = gate.get("safe_defaults", [])
        do_not_assume = gate.get("do_not_assume", [])
    else:
        missing_fields = []
        for error in errors:
            if not isinstance(error, dict):
                continue
            loc = error.get("loc")
            if isinstance(loc, (list, tuple)) and loc:
                missing_fields.append(".".join(str(part) for part in loc))
        ask_if_missing = [
            {
                "field": field,
                "question": f"请补充 `{field}`，这是 `{operation_name}` 继续执行所需的参数。",
            }
            for field in missing_fields[:8]
        ]
        safe_defaults = []
        do_not_assume = ["Do not invent missing IDs, file paths, run IDs, or user questions."]
    return _agent_recovery(
        tool_name=target,
        ask_if_missing=ask_if_missing,
        safe_defaults=safe_defaults,
        do_not_assume=do_not_assume,
        reason="invalid_or_incomplete_payload",
    )


def build_agent_guidance(
    *,
    tool_name: str | None = None,
    intent: str | None = None,
    include_all: bool = False,
) -> dict[str, Any]:
    """Return machine-readable guidance for agents before they call tools."""

    if include_all:
        tools = {name: _with_common_fields(name, TOOL_GUIDANCE[name]) for name in sorted(TOOL_GUIDANCE)}
    elif tool_name:
        if tool_name not in TOOL_GUIDANCE:
            aliases = {definition.mcp_name: name for name, definition in TOOL_DEFINITIONS.items()}
            mapped = aliases.get(tool_name)
            if mapped is None:
                return {
                    "ok": False,
                    "schema": GUIDANCE_SCHEMA,
                    "error": {
                        "code": "agent_guidance.unknown_tool",
                        "message": f"Unknown tool for guidance: {tool_name}",
                    },
                    "known_tools": sorted(TOOL_GUIDANCE),
                }
            tool_name = mapped
        tools = {tool_name: _with_common_fields(tool_name, TOOL_GUIDANCE[tool_name])}
    else:
        tools = {}

    return {
        "ok": True,
        "schema": GUIDANCE_SCHEMA,
        "intent": intent,
        "global_rules": GLOBAL_AGENT_RULES,
        "default_workflow": [
            "Classify user intent and choose candidate tool.",
            "Call horosa_agent_guidance for that tool when settings are unclear.",
            "Ask the user one concise clarification question with concrete options when guidance says ask_if_missing.",
            "Only call the calculation tool after required context and result-changing settings are clear.",
            "Explain from returned export sections, then store/report if requested.",
        ],
        "tools": tools,
        "report_and_memory": deepcopy(REPORT_AND_MEMORY_GUIDANCE) if include_all else {},
        # 软件用法帮助（防编造语料）：agent 回答「这套工具怎么用/怎么装/怎么出报告」时据此作答，
        # 不要凭通用知识虚构不存在的命令或功能。
        "usage_help": SOFTWARE_USAGE_HELP,
    }


def assert_guidance_covers_registered_tools() -> None:
    missing = sorted(set(TOOL_DEFINITIONS) - set(TOOL_GUIDANCE))
    extra = sorted(set(TOOL_GUIDANCE) - set(TOOL_DEFINITIONS))
    if missing or extra:
        raise AssertionError(f"agent guidance mismatch: missing={missing}, extra={extra}")
