from __future__ import annotations

from copy import deepcopy
from typing import Any

from horosa_skill.engine.registry import TOOL_DEFINITIONS


GUIDANCE_SCHEMA = "horosa.skill.agent_guidance.v1"

GLOBAL_AGENT_RULES: list[str] = [
    "If the client does not expose native horosa_* MCP tools, stop and ask the user/admin to run OpenClaw setup/check; do not fall back to shell or hand-written calculations.",
    "Do not hand-calculate Horosa methods with shell, Python, JavaScript, web snippets, or memorized formulas.",
    "Before calling a calculation tool, check whether the user supplied the fields and method settings that change the result.",
    "If a required or result-changing setting is missing, ask a short clarification question with concrete options instead of silently inventing a value.",
    "Use Horosa/Xingque defaults only when the user accepts defaults, asks for a quick/default reading, or the setting is explicitly documented as safe to default.",
    "For current-time questions, using the current local date/time/timezone is allowed, but location and technique-specific settings still need clarification when they matter.",
    "Timezone may be a fixed offset like +08:00 or an IANA name like America/Los_Angeles; Horosa normalizes IANA names by the chart date/time before calling the runtime.",
    "After a tool call, treat export_snapshot.export_text, export_format.sections, and summary as the source of truth.",
]

COMMON_LOCATION_FIELDS = ["date", "time", "zone/timezone", "lat/lon or gpsLat/gpsLon/location"]
COMMON_BIRTH_FIELDS = ["birth date", "birth time", "birth timezone", "birth place / longitude / latitude"]
CONFIRMATION_FIELDS = ["agent_confirmed_settings", "defaults_accepted", "clarification_notes"]
PREFLIGHT_EXEMPT_TOOLS = {"export_registry", "export_parse", "knowledge_registry", "knowledge_read", "ziwei_rules", "gua_desc", "gua_meiyi"}
INPUT_CONTRACT_SCHEMA = "horosa.skill.input_contract.v1"


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
        "output_contract": ["本命盘起盘信息", "本命盘星与虚点", "返照盘起盘信息", "返照盘星与虚点", "返照盘相位"],
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
        "output_contract": ["本命盘起盘信息", "本命盘星与虚点", "返照盘起盘信息", "返照盘星与虚点", "返照盘相位"],
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
        "output_contract": ["本命盘起盘信息", "本命盘星与虚点", "流年盘起盘信息", "流年盘星与虚点", "流年盘相位"],
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
        "output_contract": ["本命盘起盘信息", "本命盘星与虚点", "推运盘起盘信息", "推运盘星与虚点", "推运盘相位"],
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
        "output_contract": ["本命盘起盘信息", "本命盘星与虚点", "推运盘起盘信息", "推运盘星与虚点", "推运盘相位"],
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
            "pdtype": "主限类型；0 为当前星阙常用主限表配置。",
            "pdMethod": "主限方法，如 astroapp_alchabitius / horosa_legacy。",
            "pdTimeKey": "时间钥匙，如 Ptolemy。",
            "pdaspects": "纳入表格的相位角度，例如 [0, 60, 90, 120, 180]。",
        },
        "output_contract": ["主限设置", "主限表格"],
        "example_payload": {
            **COMMON_ASTRO_PAYLOAD_EXAMPLE,
            "pdtype": 0,
            "pdMethod": "astroapp_alchabitius",
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
            "pdtype/pdMethod/pdTimeKey": "主限法盘算法设置。",
        },
        "output_contract": ["本命盘星与虚点", "主限法盘星体表格", "主限法盘相位"],
        "example_payload": {
            **COMMON_ASTRO_PAYLOAD_EXAMPLE,
            "datetime": "2031-04-06 09:33:00",
            "dirZone": "+08:00",
            "pdtype": 0,
            "pdMethod": "astroapp_alchabitius",
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
    if not ask_if_missing:
        return (
            "我还缺少这次调用所需的关键参数。请补充必要输入，或明确说明是否按星阙默认设置继续。"
        )
    lines = [f"调用 `{tool_name}` 前需要先确认这些会影响结果的设置："]
    for index, item in enumerate(ask_if_missing[:6], start=1):
        question = str(item.get("question") or item.get("field") or "请补充这个参数。")
        options = item.get("options")
        if isinstance(options, list) and options:
            question = f"{question} 可选：{' / '.join(str(option) for option in options)}"
        lines.append(f"{index}. {question}")
    if safe_defaults:
        defaults = "; ".join(f"{item.get('field')}={item.get('value')}" for item in safe_defaults[:5])
        lines.append(f"如果你想快速继续，也可以明确说“按星阙默认”，我会使用：{defaults}。")
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
            "Read export_snapshot.export_text and export_format.sections before explaining.",
            "Persist or report only through Horosa memory/report tools when requested.",
        ],
    }


ASTRO_BIRTH_POLICY = _policy(
    intent="Birth/event astrology chart calculation.",
    required_context=COMMON_BIRTH_FIELDS,
    ask_if_missing=[
        {"field": "date/time/place", "question": "请提供出生/事件的日期、时间、时区和地点。"},
        {"field": "hsys", "question": "宫制要用哪一种？", "options": ["整宫制/Whole Sign（默认推荐）", "Placidus", "其他指定宫制"]},
        {"field": "zodiacal", "question": "黄道体系要用哪一种？", "options": ["回归黄道（默认推荐）", "恒星黄道"]},
        {"field": "tradition", "question": "是否需要传统占星扩展项？", "options": ["需要", "不需要/默认"]},
    ],
    safe_defaults=[
        {"field": "hsys", "value": 0, "meaning": "Whole Sign / 整宫制"},
        {"field": "zodiacal", "value": 0, "meaning": "Tropical / 回归黄道"},
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
        {"field": "after23NewDay", "question": "23 点后是否按次日换日？", "options": ["按星阙默认", "23 点后换日", "23 点后不换日"]},
    ],
    safe_defaults=[
        {"field": "ad", "value": 1, "meaning": "公历"},
        {"field": "after23NewDay", "value": False, "meaning": "星阙默认，除非用户指定"},
    ],
    do_not_assume=["location for location-sensitive methods", "question context"],
)


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
        intent="奇门遁甲起盘。",
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
            {"field": "diFen", "question": "金口诀地分/方位用哪一支？如不确定，请说明取数方式。"},
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
    "chart": ASTRO_BIRTH_POLICY,
    "chart13": ASTRO_BIRTH_POLICY,
    "india_chart": ASTRO_BIRTH_POLICY,
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
            {"field": "after23NewDay/timeAlg", "question": "子时换日和时间算法是否沿用星阙默认？", "options": ["沿用默认", "指定"]},
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
            {"field": "timeAlg/byLon/after23NewDay", "question": "真太阳时、经度校正、子时换日是否沿用星阙默认？", "options": ["沿用默认", "指定设置"]},
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
            {"field": "after23NewDay/timeAlg", "question": "子时换日和时间算法是否沿用默认？", "options": ["沿用默认", "指定"]},
        ],
        do_not_assume=["timezone", "longitude"],
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
            "Agent gate: ask the user for result-changing settings first, then pass "
            "`agent_confirmed_settings=true` or `defaults_accepted=true` with `clarification_notes`."
        )
    required = contract.get("required_for_real_call") or contract.get("technical", {}).get("technical_required_fields", [])
    if required:
        lines.append("Required input for a real call: " + ", ".join(str(item) for item in required) + ".")
    target_fields = contract.get("target_fields")
    if isinstance(target_fields, dict) and target_fields:
        field_notes = "; ".join(f"{key}: {value}" for key, value in list(target_fields.items())[:5])
        lines.append("Timing/target fields: " + field_notes)
    output_contract = contract.get("output_contract") or []
    if output_contract:
        lines.append("Expected output sections: " + ", ".join(str(item) for item in output_contract) + ".")
    return "\n".join(lines)


def validate_agent_preflight(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Return a structured gate result before a calculation tool is allowed to run."""

    if tool_name in PREFLIGHT_EXEMPT_TOOLS:
        return {"ok": True, "tool_name": tool_name, "enforced": False}
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
        ask_if_missing = policy.get("ask_if_missing", [])
        safe_defaults = policy.get("safe_defaults", [])
        do_not_assume = policy.get("do_not_assume", [])
    return {
        "ok": False,
        "tool_name": tool_name,
        "enforced": True,
        "code": "agent_guidance.required",
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
    }


def assert_guidance_covers_registered_tools() -> None:
    missing = sorted(set(TOOL_DEFINITIONS) - set(TOOL_GUIDANCE))
    extra = sorted(set(TOOL_GUIDANCE) - set(TOOL_DEFINITIONS))
    if missing or extra:
        raise AssertionError(f"agent guidance mismatch: missing={missing}, extra={extra}")
