from __future__ import annotations

from copy import deepcopy
from typing import Any

AI_EXPORT_SETTINGS_KEY = "horosa.ai.export.settings.v1"
AI_EXPORT_SETTINGS_VERSION = 6
AI_EXPORT_SECTION_MIGRATION_VERSION = 6
AI_EXPORT_SECTION_MIGRATION_KEYS = ["liureng", "qimen", "sanshiunited"]
MODULE_SNAPSHOT_PREFIX = "horosa.ai.snapshot.module.v1."
AI_EXPORT_PLANET_INFO_DEFAULT = {"showHouse": 1, "showRuler": 1}
AI_EXPORT_ASTRO_MEANING_DEFAULT = {"enabled": 0}

AI_EXPORT_PLANET_INFO_TECHNIQUES = {
    "astrochart",
    "indiachart",
    "astrochart_like",
    "relative",
    "primarydirect",
    "primarydirchart",
    "zodialrelease",
    "firdaria",
    "profection",
    "solararc",
    "solarreturn",
    "lunarreturn",
    "givenyear",
    "decennials",
    "jieqi",
    "jieqi_meta",
    "jieqi_chunfen",
    "jieqi_xiazhi",
    "jieqi_qiufen",
    "jieqi_dongzhi",
    "sanshiunited",
    "guolao",
    "germany",
}

AI_EXPORT_ASTRO_MEANING_TECHNIQUES = {
    *AI_EXPORT_PLANET_INFO_TECHNIQUES,
    "otherbu",
    "qimen",
    "liureng",
}

AI_EXPORT_HOVER_MEANING_TECHNIQUES = {"qimen", "liureng", "sanshiunited"}

JIEQI_SETTING_PRESETS = {
    "jieqi_meta": ["节气盘参数"],
    "jieqi_chunfen": ["春分星盘", "春分宿盘"],
    "jieqi_xiazhi": ["夏至星盘", "夏至宿盘"],
    "jieqi_qiufen": ["秋分星盘", "秋分宿盘"],
    "jieqi_dongzhi": ["冬至星盘", "冬至宿盘"],
}

AI_EXPORT_TECHNIQUES = [
    {"key": "astrochart", "label": "星盘"},
    {"key": "indiachart", "label": "印度律盘"},
    {"key": "astrochart_like", "label": "希腊/星体地图"},
    {"key": "relative", "label": "关系盘"},
    {"key": "primarydirect", "label": "推运盘-主/界限法"},
    {"key": "primarydirchart", "label": "推运盘-主限法盘"},
    {"key": "zodialrelease", "label": "推运盘-黄道星释"},
    {"key": "firdaria", "label": "推运盘-法达星限"},
    {"key": "profection", "label": "推运盘-小限法"},
    {"key": "solararc", "label": "推运盘-太阳弧"},
    {"key": "solarreturn", "label": "推运盘-太阳返照"},
    {"key": "lunarreturn", "label": "推运盘-月亮返照"},
    {"key": "givenyear", "label": "推运盘-流年法"},
    {"key": "decennials", "label": "推运盘-十年大运"},
    {"key": "bazi", "label": "八字"},
    {"key": "ziwei", "label": "紫微斗数"},
    {"key": "suzhan", "label": "宿占"},
    {"key": "sixyao", "label": "易卦"},
    {"key": "tongshefa", "label": "统摄法"},
    {"key": "liureng", "label": "六壬"},
    {"key": "jinkou", "label": "金口诀"},
    {"key": "qimen", "label": "奇门遁甲"},
    {"key": "sanshiunited", "label": "三式合一"},
    {"key": "taiyi", "label": "太乙"},
    {"key": "guolao", "label": "七政四余"},
    {"key": "germany", "label": "量化盘"},
    {"key": "jieqi", "label": "节气盘"},
    {"key": "jieqi_meta", "label": "节气盘-通用参数"},
    {"key": "jieqi_chunfen", "label": "节气盘-春分"},
    {"key": "jieqi_xiazhi", "label": "节气盘-夏至"},
    {"key": "jieqi_qiufen", "label": "节气盘-秋分"},
    {"key": "jieqi_dongzhi", "label": "节气盘-冬至"},
    {"key": "otherbu", "label": "西洋游戏"},
    {"key": "fengshui", "label": "风水"},
    {"key": "generic", "label": "其他页面"},
]

AI_EXPORT_PRESET_SECTIONS = {
    "astrochart": ["起盘信息", "宫位宫头", "星与虚点", "信息", "相位", "行星", "希腊点", "可能性"],
    "indiachart": ["星盘信息", "起盘信息", "信息", "相位", "行星", "希腊点", "可能性"],
    "astrochart_like": ["起盘信息", "宫位宫头", "星与虚点", "信息", "相位", "行星", "希腊点", "可能性"],
    "relative": ["关系起盘信息", "A对B相位", "B对A相位", "A对B中点相位", "B对A中点相位", "A对B映点", "A对B反映点", "B对A映点", "B对A反映点", "合成图盘", "影响图盘-星盘A", "影响图盘-星盘B"],
    "primarydirect": ["出生时间", "星盘信息", "主/界限法设置", "主/界限法表格"],
    "primarydirchart": ["出生时间", "星盘信息", "主限法盘设置", "主限法盘说明"],
    "zodialrelease": ["起盘信息", "星盘信息", "基于X点推运"],
    "firdaria": ["出生时间", "星盘信息", "法达星限表格"],
    "profection": ["星盘信息", "起盘信息", "相位"],
    "solararc": ["星盘信息", "起盘信息", "相位"],
    "solarreturn": ["星盘信息", "起盘信息", "相位"],
    "lunarreturn": ["星盘信息", "起盘信息", "相位"],
    "givenyear": ["星盘信息", "起盘信息", "相位"],
    "decennials": ["起盘信息", "星盘信息", "十年大运设置", "基于X起运"],
    "bazi": ["起盘信息", "四柱与三元", "流年行运概略", "神煞（四柱与三元）"],
    "ziwei": ["起盘信息"],
    "suzhan": ["起盘信息"],
    "sixyao": ["起盘信息", "卦象", "六爻与动爻", "卦辞与断语"],
    "tongshefa": ["本卦", "六爻", "潜藏", "亲和"],
    "liureng": ["起盘信息", "十二盘式", "十二地盘/十二天盘/十二贵神对应", "四课", "三传", "行年", "旬日", "旺衰", "基础神煞", "干煞", "月煞", "支煞", "岁煞", "十二长生", "大格", "小局", "参考", "概览"],
    "jinkou": ["起盘信息", "金口诀速览", "金口诀四位", "四位神煞"],
    "taiyi": ["起盘信息", "太乙盘", "十六宫标记"],
    "qimen": ["起盘信息", "盘型", "盘面要素", "奇门演卦", "八宫详解", "九宫方盘"],
    "sanshiunited": ["起盘信息", "概览", "太乙", "太乙十六宫", "神煞", "大六壬", "六壬大格", "六壬小局", "六壬参考", "六壬概览", "八宫详解", "正北坎宫", "东北艮宫", "正东震宫", "东南巽宫", "正南离宫", "西南坤宫", "正西兑宫", "西北乾宫"],
    "guolao": ["起盘信息", "七政四余宫位与二十八宿星曜", "神煞"],
    "germany": ["起盘信息"],
    "jieqi": ["节气盘参数", "春分星盘", "春分宿盘", "夏至星盘", "夏至宿盘", "秋分星盘", "秋分宿盘", "冬至星盘", "冬至宿盘"],
    **JIEQI_SETTING_PRESETS,
    "otherbu": ["起盘信息"],
    "fengshui": ["起盘信息", "标记判定", "冲突清单", "建议汇总", "纳气建议"],
    "generic": ["起盘信息"],
}

AI_EXPORT_FORBIDDEN_SECTIONS = {
    "liureng": ["右侧栏目"],
    "qimen": ["右侧栏目"],
    "sanshiunited": ["右侧栏目"],
}


def normalize_planet_info_setting(raw: dict[str, Any] | None) -> dict[str, int]:
    value = raw or {}
    return {
        "showHouse": 1 if value.get("showHouse") in {1, True} else 0,
        "showRuler": 1 if value.get("showRuler") in {1, True} else 0,
    }


def normalize_astro_meaning_setting(raw: dict[str, Any] | None) -> dict[str, int]:
    value = raw or {}
    return {"enabled": 1 if value.get("enabled") in {1, True} else 0}


def normalize_section_title(title: str | None) -> str:
    text = f"{title or ''}".strip()
    if not text:
        return ""
    if text.startswith("基于") and text.endswith("推运"):
        return "基于X点推运"
    if text.startswith("基于") and text.endswith("起运"):
        return "基于X起运"
    return text


def map_legacy_section_title(key: str, title: str | None) -> str:
    normalized = normalize_section_title(title)
    if key == "tongshefa":
        if normalized == "互潜":
            return "潜藏"
        if normalized == "错亲":
            return "亲和"
        if normalized == "统摄法起盘":
            return "本卦"
    elif key == "qimen":
        if normalized == "八宫":
            return "八宫详解"
        if normalized == "演卦":
            return "奇门演卦"
        if normalized == "九宫":
            return "九宫方盘"
        if normalized in {"右侧栏目", "概览"}:
            return "盘面要素"
    elif key == "liureng":
        if normalized.startswith("三传("):
            return "三传"
    elif key == "sanshiunited":
        if normalized == "状态":
            return "概览"
        if normalized == "八宫":
            return "八宫详解"
        if normalized == "大格":
            return "六壬大格"
        if normalized == "小局":
            return "六壬小局"
        if normalized == "参考":
            return "六壬参考"
        if normalized == "六壬格局概览":
            return "六壬概览"
    elif key == "sixyao":
        if normalized == "起卦方式":
            return "卦象"
        if normalized == "卦辞":
            return "卦辞与断语"
    return normalized


def unique_list(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        value = f"{item or ''}".strip()
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return output


def get_meaning_setting_meta(key: str) -> dict[str, str]:
    if key in AI_EXPORT_HOVER_MEANING_TECHNIQUES:
        return {
            "title": "悬浮注释（仅AI导出）：",
            "checkbox": "在对应分段输出六壬/遁甲/占星悬浮注释",
        }
    if key in AI_EXPORT_ASTRO_MEANING_TECHNIQUES:
        return {
            "title": "占星注释（仅AI导出）：",
            "checkbox": "在对应分段输出星/宫/座/相/希腊点释义",
        }
    return {"title": "", "checkbox": ""}


def get_technique_info(key: str) -> dict[str, Any] | None:
    base = next((item for item in AI_EXPORT_TECHNIQUES if item["key"] == key), None)
    if base is None:
        return None
    meaning_meta = get_meaning_setting_meta(key)
    supports_planet_info = key in AI_EXPORT_PLANET_INFO_TECHNIQUES
    supports_astro_meaning = key in AI_EXPORT_ASTRO_MEANING_TECHNIQUES
    supports_hover_meaning = key in AI_EXPORT_HOVER_MEANING_TECHNIQUES
    return {
        "key": base["key"],
        "label": base["label"],
        "preset_sections": deepcopy(AI_EXPORT_PRESET_SECTIONS.get(key, [])),
        "forbidden_sections": deepcopy(AI_EXPORT_FORBIDDEN_SECTIONS.get(key, [])),
        "supports_planet_info": supports_planet_info,
        "planet_info_default": deepcopy(AI_EXPORT_PLANET_INFO_DEFAULT) if supports_planet_info else None,
        "supports_astro_meaning": supports_astro_meaning,
        "supports_hover_meaning": supports_hover_meaning,
        "astro_meaning_default": deepcopy(AI_EXPORT_ASTRO_MEANING_DEFAULT) if (supports_astro_meaning or supports_hover_meaning) else None,
        "astro_meaning_title": meaning_meta["title"],
        "astro_meaning_checkbox": meaning_meta["checkbox"],
        "settings_template": {
            "sections": deepcopy(AI_EXPORT_PRESET_SECTIONS.get(key, [])),
            "planetInfo": deepcopy(AI_EXPORT_PLANET_INFO_DEFAULT) if supports_planet_info else None,
            "astroMeaning": deepcopy(AI_EXPORT_ASTRO_MEANING_DEFAULT) if (supports_astro_meaning or supports_hover_meaning) else None,
        },
    }


def build_export_registry(*, technique: str | None = None) -> dict[str, Any]:
    techniques = [get_technique_info(item["key"]) for item in AI_EXPORT_TECHNIQUES]
    techniques = [item for item in techniques if item is not None]
    selected = get_technique_info(technique) if technique else None
    return {
        "source_of_truth": "Horosa-Web/astrostudyui/src/utils/aiExport.js",
        "settings_key": AI_EXPORT_SETTINGS_KEY,
        "settings_version": AI_EXPORT_SETTINGS_VERSION,
        "section_migration_version": AI_EXPORT_SECTION_MIGRATION_VERSION,
        "section_migration_keys": deepcopy(AI_EXPORT_SECTION_MIGRATION_KEYS),
        "module_snapshot_prefix": MODULE_SNAPSHOT_PREFIX,
        "jieqi_split_keys": list(JIEQI_SETTING_PRESETS.keys()),
        "planet_info_default": deepcopy(AI_EXPORT_PLANET_INFO_DEFAULT),
        "astro_meaning_default": deepcopy(AI_EXPORT_ASTRO_MEANING_DEFAULT),
        "default_normalized_settings": {
            "version": AI_EXPORT_SETTINGS_VERSION,
            "sections": {},
            "planetInfo": {},
            "astroMeaning": {},
        },
        "techniques": techniques,
        "selected_technique": selected,
    }
