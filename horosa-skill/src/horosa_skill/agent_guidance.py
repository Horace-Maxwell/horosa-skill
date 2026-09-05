from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from horosa_skill.engine.registry import TOOL_DEFINITIONS


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
            "datetime": "返照目标时间或目标年份中的参考时间，格式建议 YYYY-MM-DD HH:mm:ss。",
            "dirZone": "返照盘地点时区；如 +08:00。",
            "dirLat/dirLon": "返照盘地点经纬度；若用户没有指定返照地点，必须先询问是否用出生地/现居地。",
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
            "datetime": "月返目标时间或目标月份中的参考时间，格式建议 YYYY-MM-DD HH:mm:ss。",
            "dirZone": "月返盘地点时区。",
            "dirLat/dirLon": "月返盘地点经纬度；不要静默假定等于出生地。",
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
            "datetime": "指定年中的目标时间，格式建议 YYYY-MM-DD HH:mm:ss。",
            "dirZone": "流年盘地点时区。",
            "dirLat/dirLon": "流年盘地点经纬度。",
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
            "datetime": "太阳弧推运目标时间，格式建议 YYYY-MM-DD HH:mm:ss。",
            "dirZone": "推运盘目标时区。",
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
            "datetime": "小限目标时间，格式建议 YYYY-MM-DD HH:mm:ss。",
            "dirZone": "目标时区。",
        },
        "output_contract": ["本命盘配置", "起盘信息", "时段盘配置", "相位"],
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
            "pdMethod": "方位法（核5，逐位核验）：core_alchabitius（Alcabitius 半弧，默认）/ meridian / porphyry / equal_ecliptic（Equal 黄道）/ equal_hour_circle（Equal 时圈）/ horosa_legacy（传统赤经）。未知值后端回退 core_alchabitius。",
            "pdTimeKey": "时间钥匙（22 项）：Ptolemy（托勒密 1°/年，默认）/ Naibod / TrueSolarArc（真太阳弧）/ SymbolicSolarArc（太阳弧·黄经）/ Cardano / Umar / Wollner / Plantiko / Simmonite / SynodicYear / Kepler / Brahe / Kundig / SymbolicDegree / SymbolicYear / SymbolicMoon / SymbolicMonth / Quarterly / Quinary / Duodenary / Novenary / SelfMeasure（Simmonite/Kepler/Brahe 按本命太阳日速每盘真算）。",
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
            "datetime": "主限法盘目标时间，格式建议 YYYY-MM-DD HH:mm:ss。",
            "dirZone": "目标时区。",
            "pdtype/pdMethod/pdTimeKey": "主限法盘算法设置（pdMethod 核5: core_alchabitius/meridian/porphyry/equal_ecliptic/equal_hour_circle，另有 horosa_legacy；pdTimeKey 同 pd 工具 22 项，常用 Ptolemy/Naibod/TrueSolarArc）。逆向用 direction='converse'。",
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
            "startSign": "可选；指定释放起始星座，不给则按星阙默认。",
            "stopLevelIdx": "可选；释放层级深度，不给则按星阙默认。",
        },
        "output_contract": ["黄道释放设置", "黄道释放时间轴"],
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
    intent="神数 (皇极经世/五兆/太玄/京氏易/神乙数)：以干支起数，只需日期(可含时间)即可起盘，不需经纬度。",
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
    intent="神数 (铁板/邵子)：以干支起数并按性别取条文；需日期(含时间更准)与性别。",
    required_context=["date (公历日期)", "time (可选，影响时柱)", "gender (性别)"],
    ask_if_missing=[*SHENSHU_POLICY["ask_if_missing"], _GENDER_QUESTION],
    safe_defaults=SHENSHU_POLICY["safe_defaults"],
    do_not_assume=["date", "gender"],
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
            "options": ["0 整宫制/Whole Sign（默认推荐）", "3 Placidus", "1 Alcabitus", "2 Regiomontanus", "4 Koch", "其他指定宫制（5 Vehlow/6 Polich Page/7 Sripati/8 MC等宫）"],
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
        {"field": "after23NewDay", "value": False, "meaning": "星阙默认，除非用户指定"},
    ],
    do_not_assume=["location for location-sensitive methods", "question context"],
)


def _progression_target_policy(*, intent: str, targets: list[dict[str, Any]], do_not_assume: list[str]) -> dict[str, Any]:
    """推运族专属策略工厂（v0.36.0 B3）：此前 vedicprog/jaynesprog/planetaryarc/planetaryages/extrareturns
    共用 ASTRO_BIRTH_POLICY——问宫制却从不问目标时刻/弧源，agent 只能静默默认。"""
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
        ],
        do_not_assume=["birth time", "timezone", *do_not_assume],
    )


_TARGET_DATE_QUESTION = {"field": "targetDate/targetTime", "question": "推到哪一天？（targetDate YYYY-MM-DD，可加 targetTime；缺省=今天）"}
VEDICPROG_POLICY = _progression_target_policy(
    intent="恒星推运 / Vedic sidereal 二次推运：本命 + 目标日期。",
    targets=[_TARGET_DATE_QUESTION],
    do_not_assume=["target date"],
)
JAYNESPROG_POLICY = _progression_target_policy(
    intent="赤纬推运 / Jayne：二次推运 + 赤纬平行，本命 + 目标日期。",
    targets=[_TARGET_DATE_QUESTION],
    do_not_assume=["target date"],
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

# 闸问题允许没有 options 的字段（自由文本/复合输入）；新问题要么带 options 要么在这里登记（tests/test_gate_policies.py 守）。
FREE_TEXT_GATE_FIELDS: frozenset[str] = frozenset({
    "date", "time", "date/time", "date/time/place", "date/time/gender", "datetime", "targetDate/targetTime", "asOf",
    "startDate/endDate", "conditions", "topic", "question", "natal data", "target time", "location", "askEvent",
    "birth data", "year", "name", "technique", "content", "category/key", "rectifyEvents", "guaDate/guaYearGanZi",
    "q", "query", "pillars", "fromYear", "nums / date-time", "qiZhi / date-time", "dayGan/dayZhi", "cast-input", "cast-input + date/time",
    "school-params", "event", "relocLat/relocLon", "inner/outer", "zone", "target technique",
})


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
            {"field": "qijuMethod", "question": "起局方式是否沿用星阙默认？", "options": ["星阙默认", "指定置闰/拆补/茅山等"]},
            {"field": "sex", "question": "如果是命盘/人事局，请确认性别；纯事件局可沿用默认。", "options": ["男", "女", "事件局/不指定"]},
        ],
        safe_defaults=[
            {"field": "paiPanType", "value": 3, "meaning": "时家奇门"},
            {"field": "sex", "value": 1, "meaning": "星阙默认；涉及命式时应先问"},
            {"field": "after23NewDay", "value": False, "meaning": "星阙默认"},
        ],
        do_not_assume=["question", "location", "non-default qijuMethod"],
    ),
    "qimenzeri": _policy(
        intent=(
            "奇门择日「找局」：在一段时间窗内扫出满足奇门条件树的时辰，并附命中首刻的完整奇门盘"
            "（17 段奇门 + [择日搜索配置]/[择日条件]/[命中时辰]）。"
            "\n算权：**展示盘由 ken 后端计算**（/qimen/pan，与普通 qimen 工具同源）；"
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
            {"field": "qijuMethod", "question": "起局方式是否沿用星阙默认？", "options": ["星阙默认", "指定置闰/拆补/茅山等"]},
        ],
        safe_defaults=[
            {"field": "paiPanType", "value": 3, "meaning": "时家奇门"},
            {"field": "maxSpanDays", "value": 92, "meaning": "搜索窗上限；更长请分段，否则 JS 引擎会超时"},
        ],
        do_not_assume=["搜索时间窗", "择日条件", "location", "non-default qijuMethod"],
        output_contract=(
            "intervals 为本地引擎扫出的命中时辰（含 pick/pickEnd 边界安全时刻）；pan 为 ken 计算的展示盘，"
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
        ],
        safe_defaults=[
            {"field": "maxSpanDays", "value": 92, "meaning": "搜索窗上限；更长请分段"},
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
        safe_defaults=[{"field": "precision", "value": "minute", "meaning": "扫描到分钟"}],
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
            {"field": "gender/options", "question": "是否需要指定性别或太乙参数？", "options": ["沿用星阙默认", "指定参数"]},
        ],
        safe_defaults=[{"field": "timeAlg", "value": 0, "meaning": "星阙默认"}],
        do_not_assume=["location", "custom options"],
    ),
    "jinkou": _policy(
        intent="金口诀起课。",
        required_context=COMMON_LOCATION_FIELDS + ["question/topic", "diFen/地分 when the method requires it"],
        ask_if_missing=[
            {
                "field": "diFen",
                "question": "金口诀地分/方位用哪一支？如不确定，请说明取数方式。",
                "options": ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"],
                "values": ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"],
            },
            {"field": "guirengType", "question": "贵人体系用哪一种？", "options": ["六壬法贵人（星阙金口诀默认）", "星占法贵人", "遁甲法贵人"]},
            {"field": "question", "question": "这课主要问什么事？"},
        ],
        safe_defaults=[{"field": "guirengType", "value": 0, "meaning": "金口诀星阙默认"}],
        do_not_assume=["diFen"],
    ),
    "liureng_gods": _policy(
        intent="大六壬正盘：四课、三传、贵神、神煞。",
        required_context=COMMON_LOCATION_FIELDS + ["question/topic"],
        ask_if_missing=[
            {"field": "date/time", "question": "大六壬用当前时间还是指定时间？", "options": ["当前时间", "指定时间"]},
            {"field": "location", "question": "起课地点用哪里？", "options": ["当前位置/客户端位置", "指定城市或经纬度"]},
            {"field": "question", "question": "这课主要问什么事？"},
            {"field": "guirengType", "question": "贵人体系用哪一种？", "options": ["星占法贵人（星阙默认/推荐）", "六壬法贵人", "遁甲法贵人"]},
            {"field": "isDiurnal", "question": "昼夜贵人是否由 Horosa 自动判定？", "options": ["自动判定", "指定昼贵", "指定夜贵"]},
        ],
        safe_defaults=[
            {"field": "guirengType", "value": 2, "meaning": "星占法贵人 / Xingque default"},
            {"field": "isDiurnal", "value": None, "meaning": "由本地 runtime 根据时间判定"},
            {"field": "after23NewDay", "value": False, "meaning": "星阙默认"},
        ],
        do_not_assume=["question", "location", "non-default guirengType"],
    ),
    "liureng_runyear": _policy(
        intent="大六壬行年/年运。",
        required_context=COMMON_LOCATION_FIELDS + ["gender", "target year/date when different from base time"],
        ask_if_missing=[
            {"field": "gender", "question": "行年需要性别，请选择。", "options": ["男", "女"]},
            {"field": "guaDate/guaYearGanZi", "question": "要看哪一年/哪一段行年？"},
            {"field": "guirengType", "question": "贵人体系是否沿用星阙默认星占法贵人？", "options": ["星占法贵人", "六壬法贵人", "遁甲法贵人"]},
        ],
        safe_defaults=[{"field": "guirengType", "value": 2, "meaning": "星占法贵人"}],
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
        safe_defaults=[{"field": "liureng guirengType", "value": 2, "meaning": "通过六壬工具使用星阙默认"}],
        do_not_assume=["question"],
    ),
    "sixyao": _policy(
        intent="六爻/易卦。",
        required_context=COMMON_LOCATION_FIELDS + ["question", "lines or gua_code"],
        ask_if_missing=[
            {"field": "question", "question": "这卦要问什么事？"},
            {"field": "lines/gua_code", "question": "卦怎么来？", "options": ["用户给六爻阴阳动静", "用户给本卦/变卦", "使用指定起卦法后再算"]},
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
        ],
        safe_defaults=[
            {"field": "timeAlg", "value": 1, "meaning": "钟表时，对应 HeLuoMain.js 的默认"},
        ],
        do_not_assume=["gender"],
    ),
    "yizhangjing": _policy(
        intent="一掌经：农历生辰四宫十二星（六道），排命宫/人事十二宫/格局/重犯/大限/小限流年十二神，可叠神煞合参层。",
        required_context=["birth date", "birth time", "gender"],
        ask_if_missing=[
            {"field": "date/time", "question": "请提供出生日期、时间和性别（一掌经按农历口径排盘）。"},
            {"field": "dingYue", "question": "定月用农历月还是节气月？", "options": ["农历月（默认，闰月十五折半）", "节气月（按八字月支序）"]},
        ],
        safe_defaults=[
            {"field": "dingYue", "value": "lunar", "meaning": "农历月，闰月十五折半归属"},
            {"field": "dayunLength", "value": 7, "meaning": "大限一宫 7 年（通行口径）"},
            {"field": "shenshaLayer", "value": True, "meaning": "神煞合参层开（无头导出全量）"},
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
        intent="宿占/宿盘。",
        required_context=COMMON_BIRTH_FIELDS,
        ask_if_missing=[
            {"field": "date/time/place", "question": "请提供出生/事件日期、时间、时区和地点。"},
            {"field": "szchart/szshape/houseStartMode", "question": "宿占盘式和形制是否沿用星阙默认？", "options": ["沿用默认", "指定盘式/形制"]},
        ],
        safe_defaults=[{"field": "doubingSu28", "value": True, "meaning": "星阙默认"}],
    ),
    "hellen_chart": ASTRO_BIRTH_POLICY,
    "guolao_chart": ASTRO_BIRTH_POLICY,
    "germany": ASTRO_BIRTH_POLICY,
    "agepoint": ASTRO_BIRTH_POLICY,
    "distributions": ASTRO_BIRTH_POLICY,
    "jaynesprog": JAYNESPROG_POLICY,
    "vedicprog": VEDICPROG_POLICY,
    "planetaryarc": PLANETARYARC_POLICY,
    "planetaryages": PLANETARYAGES_POLICY,
    "balbillus": ASTRO_BIRTH_POLICY,
    "yearsystem129": ASTRO_BIRTH_POLICY,
    "persiandirected": ASTRO_BIRTH_POLICY,
    "triplicityrulers": ASTRO_BIRTH_POLICY,
    "keypoints": ASTRO_BIRTH_POLICY,
    "lunationphase": ASTRO_BIRTH_POLICY,
    "extrareturns": EXTRARETURNS_POLICY,
    "horary": _policy(
        intent="卜卦 / horary：盘的时刻是「提问的当下」（占者收到问题、心中疑问成形的那一刻），不是当事人的出生时间。按问题类别取事项宫。",
        required_context=["提问时刻 date/time/zone", "提问地点 lon/lat", "问题类别 category"],
        ask_if_missing=[
            {"field": "date/time/place", "question": "请提供「提问当下」的日期、时间、时区和地点（卜卦以提问时刻起盘，不是出生时间）。"},
            {"field": "category", "question": "问的是哪一类事？", "options": ["综合 general", "财物 wealth", "婚姻/对象 marriage", "事业/职位 career", "疾病 health", "官非/对手 lawsuit", "失物/盗贼 theft", "子嗣 pregnancy", "房产 property", "旅行 travel", "愿望 hope", "死亡/遗产 death", "私敌 enemy", "兄弟/亲属 family"]},
        ],
        safe_defaults=[{"field": "category", "value": "general", "meaning": "综合判断：事项守护星取月亮下一个入相的星 / 相关宫主"}],
        do_not_assume=["提问时刻（绝不可编造，必须是占者真实收到问题的时刻）", "问题类别"],
    ),
    "election": _policy(
        intent="择日 / electional：评估某个「候选时刻」适不适合做某事；盘的时刻是被评估的候选时间，topicId 决定用事规则包与红线。",
        required_context=["候选时刻 date/time/zone", "举事地点 lon/lat", "用事类型 topicId"],
        ask_if_missing=[
            {"field": "date/time/place", "question": "请提供要评估的候选日期、时间、时区和举事地点。"},
            {"field": "topicId", "question": "做什么事（用事类型）？", "options": ["结婚 marriage", "开业/创业 business", "入宅/迁居 move_in", "购屋 buy_property", "买卖交易 trade", "购车 buy_car", "签约 contract", "手术 surgery", "出行 travel", "求职 job_hunt", "其它（见 TOPIC_MASTER）"]},
        ],
        safe_defaults=[{"field": "topicId", "value": "marriage", "meaning": "默认按结婚用事规则包评估"}],
        do_not_assume=["候选时刻", "用事类型"],
    ),
    "geomancy": _policy(
        intent="天文地占 / astronomical geomancy：以「起卦时刻」确定性起卦（castMethod='time'，由 date/time 派生 timeSeed，同刻可复现），由 4 母卦推 16 图形入十二宫，取判官/见证/解读技法断吉凶。",
        required_context=["起卦时刻 date/time/zone", "起卦地点 lon/lat", "所问 question", "问类 questionType"],
        ask_if_missing=[
            {"field": "date/time/place", "question": "请提供起卦的日期、时间、时区和地点（地占以起卦时刻确定性起卦）。"},
            {"field": "question", "question": "所问何事？请给出具体问题。"},
            {"field": "questionType", "question": "问的是哪一类？", "options": ["综合/自定 custom", "财物 wealth", "婚姻 marriage", "事业 career", "疾病 health", "官非 lawsuit", "失物 theft", "子嗣 pregnancy", "房产 property", "旅行 travel", "愿望 hope", "私敌 enemy"]},
        ],
        safe_defaults=[{"field": "questionType", "value": "custom", "meaning": "自定问类：按主问句判事项宫"}],
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
            {"field": "spread", "question": "用哪种牌阵？", "options": ["三张·过去现在未来 three", "凯尔特十字 celtic", "单张 one", "关系 relationship", "其它（见 SPREADS）"]},
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
    "taixuan": SHENSHU_POLICY,
    "jingjue": SHENSHU_POLICY,
    "shenyishu": SHENSHU_POLICY,
    "shaozi": SHENSHU_GENDER_POLICY,
    "tieban": SHENSHU_GENDER_POLICY,
    "fendjing": SHENSHU_POLICY,
    "beiji": SHENSHU_POLICY,
    "nanji": SHENSHU_POLICY,
    "chunzi": SHENSHU_POLICY,
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
        safe_defaults=[{"field": "ingressTerm", "value": "春分", "meaning": "白羊入宫，世俗年盘的标准起点"}],
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
    "chart": ASTRO_BIRTH_POLICY,
    "chart13": ASTRO_BIRTH_POLICY,
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
                "field": "school",
                "question": "用哪一派通书？（同一天在不同流派下结论可以完全相反，必须指定）",
                "options": [
                    "donggong 董公择日",
                    "qimen 奇门叠数",
                    "sanyuan 三垣列宿",
                    "wutu 天元乌兔",
                    "xuankong 三元玄空大卦",
                ],
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
    "chart12": ASTRO_BIRTH_POLICY,
    "draconic": ASTRO_BIRTH_POLICY,
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
            {"field": "relative", "question": "关系盘类型用哪一种？", "options": ["星阙默认", "指定关系盘参数"]},
        ],
        safe_defaults=[{"field": "relative", "value": 0, "meaning": "星阙默认"}],
        do_not_assume=["either party's birth time/place"],
    ),
    "solarreturn": PREDICTIVE_POLICY,
    "lunarreturn": PREDICTIVE_POLICY,
    "solararc": PREDICTIVE_POLICY,
    "givenyear": PREDICTIVE_POLICY,
    "profection": PREDICTIVE_POLICY,
    "pd": PREDICTIVE_POLICY,
    "pdchart": PREDICTIVE_POLICY,
    "zr": PREDICTIVE_POLICY,
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
        intent="紫微斗数命盘。",
        required_context=COMMON_BIRTH_FIELDS + ["gender"],
        ask_if_missing=[
            {"field": "birth data", "question": "请提供出生日期、时间、时区和地点。"},
            {"field": "gender", "question": "紫微需要性别，请选择。", "options": ["男", "女"]},
            {"field": "after23NewDay/lateZiHourUseNextDay/timeAlg", "question": "子时换日、晚子时时柱和时间算法是否沿用星阙默认？", "options": ["沿用默认", "指定"]},
        ],
        safe_defaults=[{"field": "after23NewDay", "value": False, "meaning": "星阙默认"}],
        do_not_assume=["gender", "birth time"],
    ),
    "ziwei_rules": _policy(
        intent="Fetch Ziwei rule metadata.",
        required_context=[],
        ask_if_missing=[],
        safe_defaults=[{"field": "request", "value": {}, "meaning": "rules have no required input"}],
    ),
    "bazi_birth": _policy(
        intent="八字命盘。",
        required_context=COMMON_BIRTH_FIELDS,
        ask_if_missing=[
            {"field": "birth data", "question": "请提供出生日期、时间、时区和地点。"},
            {"field": "timeAlg/byLon/after23NewDay/lateZiHourUseNextDay", "question": "真太阳时、经度校正、子时换日、晚子时时柱是否沿用星阙默认？", "options": ["沿用默认", "指定设置"]},
        ],
        safe_defaults=[
            {"field": "timeAlg", "value": 0, "meaning": "星阙默认"},
            {"field": "byLon", "value": False, "meaning": "星阙默认"},
            {"field": "after23NewDay", "value": False, "meaning": "星阙默认"},
        ],
        do_not_assume=["birth time", "timezone", "birthplace"],
    ),
    "bazi_direct": _policy(
        intent="八字大运/流年/direct flow.",
        required_context=COMMON_BIRTH_FIELDS + ["gender"],
        ask_if_missing=[
            {"field": "birth data", "question": "请提供出生日期、时间、时区和地点。"},
            {"field": "gender", "question": "排大运需要性别，请选择。", "options": ["男", "女"]},
            {"field": "adjustJieqi", "question": "节气校正是否沿用星阙默认？", "options": ["沿用默认", "指定校正"]},
        ],
        safe_defaults=[{"field": "adjustJieqi", "value": False, "meaning": "星阙默认"}],
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
