"""星运四键（星历 / 回归轴 / 产前朔望 / 二次推运）AI 快照 builder —— 上游前端 builder 的逐字 Python 移植。

上游（Horosa-Public HEAD 9b74714b，`Horosa-Web/astrostudyui/src/`；文件:行 = 该 HEAD）：

- `components/astro/AstroEphemeris.js:25-126`   defaultEphemerisWindow / buildEphemerisSnapshotText / ephemerisLimitsText
- `components/astro/AstroReturnTimeline.js:13-45` buildReturnTimelineSnapshotText
- `components/astro/AstroPrenatalSyzygy.js:27-86` buildPrenatalSyzygySnapshotText / splitDateTime
- `components/astro/astroProgSnapshot.js:16-142`  PROG_SNAPSHOT_VARIANTS / buildProgSnapshotText（'prog' 与 'vedicprog' 两支同源）
- `components/astro/AstroProgChart.js:21-27`      MINOR_VARIANT_OPTIONS / MINOR_VARIANT_LABEL
- `components/astro/AstroExtraCommon.js:63-82`    signName / fmtNum / fmtDegree
- `utils/astroAiSnapshot.js:45-177,507-551`       msg / splitDegree / whichTerm / formatSignDegree / lonToSignDegree /
  gfmTableLines / buildHouseCuspLines / buildStarAndLotPositionLines
- `utils/astroAiSnapshot.js:1956-2019,2140-2146`  buildPredictiveBirthLines / buildPredictiveBirthHeaderLines /
  buildCurrentMomentLines / buildMethodNoteLines
- `utils/planetHouseInfo.js`                      appendPlanetHouseInfoById（缺省 showHouse/showRuler 全开）
- `constants/AstroConst.js`                       ZODIACAL / HOUSE_SYSTEM_OPTIONS / INDIA_AYANAMSA_OPTIONS / ayanamsaLabel /
  zodiacalDisplayText / LIST_SIGNS / LIST_OBJECTS / LOTS / EGYPTIAN_TERMS

本模块只做「数据 → 文本」：HTTP 请求（/chart 本命盘、/astroextra/*）一律在 service.py 的 runner 里发
（AGENTS §4「请求型 builder 一律归 Python」）。星运族 [方法说明] 的文案真值在 service.py 的
`_PREDICTIVE_METHOD_NOTES`（与其余 22 键同表），由 runner 传入，避免两处各存一份。

JS 语义逐条对齐（不是「看起来差不多」）：
- `fmtNum` = `Number(v).toFixed(d)`：toFixed 取 double 精确值的最近值、平局取大（远离零），Python 的
  round/format 是银行家舍入 → 用 `Decimal(...).quantize(ROUND_HALF_UP)`；`Number(null)` 是 0、`Number(undefined)`
  是 NaN（→ '-'），故缺键与 null 分开处理（`_UNDEFINED` 哨兵）。
- JS `%` 是 fmod（符号随被除数），不是 Python 的 `%`。
- 模板字符串里的数字按 JS `String(number)` 出（整数值不带 `.0`）。
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

# JS `undefined` 哨兵：JSON 里的 null 在 Python 是 None（= JS null），缺键才是 undefined。
_UNDEFINED: Any = object()

# ── 上游常量表（scripts 生成、逐字；勿手改——改动请对照上游文件重新核对）──
# 上游 constants/AstroText.js:355-467 AstroTxtMsg（AstroConst 键已解析；脚本生成，逐字）。
ASTRO_TXT_MSG: dict[str, str] = {
    "Asp0": "0º",
    "Asp60": "60º",
    "Asp90": "90º",
    "Asp120": "120º",
    "Asp180": "180º",
    "Asp45": "45º",
    "Asp135": "135º",
    "Asp30": "30º",
    "Asp150": "150º",
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
    "Vertex": "宿命点",
    "Chiron": "凯龙",
    "Syzygy": "月亮朔望点",
    "Intp_Apog": "月亮平均远地点",
    "Intp_Perg": "月亮平均近地点",
    "Pholus": "人龙星",
    "Ceres": "谷神星",
    "Pallas": "智神星",
    "Juno": "婚神星",
    "Vesta": "灶神星",
    "Eris": "阋神星",
    "MoonSun": "日月中点",
    "SaturnMars": "火土中点",
    "JupiterVenus": "金木中点",
    "LifeMasterDeg74": "七政命度点",
    "Asc": "上升",
    "Desc": "下降",
    "MC": "中天",
    "IC": "天底",
    "Sidereal": "恒星黄道",
    "Pars Spirit": "灵点",
    "Pars Faith": "信心点",
    "Pars Substance": "占有点",
    "Pars Wedding [Male]": "婚姻点（男性）",
    "Pars Wedding [Female]": "婚姻点（女性）",
    "Pars Sons": "子女点",
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
    "Pars Eros": "爱欲点",
    "Pars Necessity": "必然点",
    "Pars Courage": "勇气点",
    "Pars Victory": "胜利点",
    "Pars Nemesis": "报应点",
    "Pars Basis": "根基点",
    "Pars Exaltation": "擢升点",
    "Pars Sons Valens": "儿子点",
    "Pars Daughters": "女儿点",
    "Pars Praxis": "事业点",
    "Pars Wedding Dorothean": "婚姻点（通式）",
    "Cupido": "丘比特",
    "Hades": "哈迪斯",
    "Zeus": "宙斯",
    "Kronos": "克洛诺斯",
    "Apollon": "阿波罗",
    "Admetos": "阿德墨托斯",
    "Vulcanus": "伏尔甘",
    "Poseidon": "波塞冬",
    "AriesPoint": "白羊点",
}
# 上游 constants/AstroText.js:139-353 AstroMsg 中**非字形**条目（单字符字形 token 在 msg() 里
# 本就回落为 id 本身，故不收；signName 只会拿星座名来查，星座名先命中 AstroTxtMsg）。
ASTRO_MSG_TEXT: dict[str, str] = {
    "Vertex": "宿命点",
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
    "Algenib": "壁宿一",
    "Alpheratz": "壁宿二",
    "Zaur": "天苑一",
    "Algol": "大陵五",
    "Alcyone": "昴宿六",
    "Aldebaran": "毕宿五",
    "Rigel": "参宿七",
    "Capella": "五车二",
    "Betelgeuse": "参宿四",
    "Sirius": "天狼星",
    "Canopus": "老人星",
    "Castor": "北河二",
    "Pollux": "北河三",
    "Procyon": "南河三",
    "Asellus Borealis": "鬼宿三",
    "Asellus Australis": "鬼宿四",
    "Alphard": "星宿一",
    "Regulus": "狮心轩辕十四",
    "Denebola": "五帝座一",
    "Algorab": "轸宿三",
    "Spica": "角宿一",
    "Arcturus": "大角",
    "Alphecca": "贯索四",
    "Zuben Elgenubi": "氐宿一",
    "Zuben Eshamali": "氐宿四",
    "Unukalhai": "天市右垣七",
    "Agena": "马腹一",
    "Rigel Kentaurus": "南門二",
    "Antares": "蝎心心宿二",
    "Lesath": "尾宿九",
    "Vega": "织女星",
    "Altair": "牛郎星",
    "Deneb Algedi": "垒壁阵四",
    "Fomalhaut": "北落师门",
    "Deneb": "天津四",
    "Achernar": "水委一",
    "Sidereal": "恒星黄道",
    "Tropical": "回归黄道",
    "Whole Sign": "整宫制",
    "Alcabitus": "Alcabitus",
    "Regiomontanus": "Regiomontanus",
    "Placidus": "Placidus",
    "Koch": "Koch",
    "Vehlow Equal": "Vehlow Equal",
    "Polich Page": "Polich Page",
    "Sripati": "Sripati",
    "Porphyrius": "Porphyry",
    "Campanus": "Campanus",
    "Equal": "Equal",
    "Equal MC": "Equal MC",
    "Meridian": "Meridian",
    "Azimuthal": "Horizontal",
    "Morinus": "Morinus",
    "Carter Poli-Equatorial": "Carter Poli-Equatorial",
    "Sunshine": "Sunshine",
    "Sunshine Alternate": "Sunshine Alternate",
    "Krusinski-Pisa-Goelzer": "Krusinski-Pisa-Goelzer",
    "Pullen SD": "Pullen SD",
    "Pullen SR": "Pullen SR",
    "APC Houses": "APC Houses",
    "Savard-A": "Savard-A",
    "Fortuna_Whole": "福点整宫制",
}
# 上游 constants/AstroConst.js:168 LIST_SIGNS
LIST_SIGNS: tuple[str, ...] = (
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
)
# 上游 constants/AstroConst.js:609 LIST_OBJECTS
LIST_OBJECTS: tuple[str, ...] = (
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
    "North Node", "South Node", "Dark Moon", "Purple Clouds", "Syzygy",
    "Pars Fortuna", "Intp_Apog", "Intp_Perg", "Chiron", "Pholus",
    "Ceres", "Pallas", "Juno", "Vesta", "LifeMasterDeg74",
)
# 上游 constants/AstroConst.js:132 LOTS（33 点，含 v3.x 新增的希腊化补全六点）
LOTS: tuple[str, ...] = (
    "Pars Spirit", "Pars Mercury", "Pars Venus", "Pars Mars",
    "Pars Jupiter", "Pars Saturn", "Pars Faith", "Pars Substance",
    "Pars Wedding [Female]", "Pars Wedding [Male]", "Pars Sons", "Pars Mother",
    "Pars Father", "Pars Brothers", "Pars Friends", "Pars Enemies",
    "Pars Diseases", "Pars Death", "Pars Travel", "Pars Horsemanship",
    "Pars Life", "Pars Radix", "Pars Eros", "Pars Necessity",
    "Pars Courage", "Pars Victory", "Pars Nemesis", "Pars Basis",
    "Pars Exaltation", "Pars Sons Valens", "Pars Daughters", "Pars Praxis",
    "Pars Wedding Dorothean",
)
# 上游 constants/AstroConst.js:282 EGYPTIAN_TERMS（formatSignDegree 的「位于 X 界」恒用埃及界）
EGYPTIAN_TERMS: dict[str, tuple[tuple[str, int, int], ...]] = {
    "Aries": (("Jupiter", 0, 6), ("Venus", 6, 12), ("Mercury", 12, 20), ("Mars", 20, 25), ("Saturn", 25, 30)),
    "Taurus": (("Venus", 0, 8), ("Mercury", 8, 14), ("Jupiter", 14, 22), ("Saturn", 22, 27), ("Mars", 27, 30)),
    "Gemini": (("Mercury", 0, 6), ("Jupiter", 6, 12), ("Venus", 12, 17), ("Mars", 17, 24), ("Saturn", 24, 30)),
    "Cancer": (("Mars", 0, 7), ("Venus", 7, 13), ("Mercury", 13, 19), ("Jupiter", 19, 26), ("Saturn", 26, 30)),
    "Leo": (("Jupiter", 0, 6), ("Venus", 6, 11), ("Saturn", 11, 18), ("Mercury", 18, 24), ("Mars", 24, 30)),
    "Virgo": (("Mercury", 0, 7), ("Venus", 7, 17), ("Jupiter", 17, 21), ("Mars", 21, 28), ("Saturn", 28, 30)),
    "Libra": (("Saturn", 0, 6), ("Mercury", 6, 14), ("Jupiter", 14, 21), ("Venus", 21, 28), ("Mars", 28, 30)),
    "Scorpio": (("Mars", 0, 7), ("Venus", 7, 11), ("Mercury", 11, 19), ("Jupiter", 19, 24), ("Saturn", 24, 30)),
    "Sagittarius": (("Jupiter", 0, 12), ("Venus", 12, 17), ("Mercury", 17, 21), ("Saturn", 21, 26), ("Mars", 26, 30)),
    "Capricorn": (("Mercury", 0, 7), ("Jupiter", 7, 14), ("Venus", 14, 22), ("Saturn", 22, 26), ("Mars", 26, 30)),
    "Aquarius": (("Mercury", 0, 7), ("Venus", 7, 13), ("Jupiter", 13, 20), ("Mars", 20, 25), ("Saturn", 25, 30)),
    "Pisces": (("Venus", 0, 12), ("Jupiter", 12, 16), ("Mercury", 16, 19), ("Mars", 19, 28), ("Saturn", 28, 30)),
}
# 上游 constants/AstroConst.js:1045 HOUSE_SYSTEM_OPTIONS → HouseSys（键为 `${value}`）
HOUSE_SYS: dict[str, str] = {
    "0": "整宫制",
    "1": "Alcabitus",
    "2": "Regiomontanus",
    "3": "Placidus",
    "4": "Koch",
    "5": "Vehlow Equal",
    "6": "Polich Page",
    "7": "Sripati",
    "8": "天顶为10宫中点等宫制",
    "9": "Porphyry",
    "10": "Campanus",
    "11": "Equal",
    "12": "Equal MC",
    "13": "Meridian",
    "14": "Horizontal",
    "15": "Morinus",
    "16": "Carter Poli-Equatorial",
    "17": "Sunshine",
    "18": "Sunshine Alternate",
    "19": "Krusinski-Pisa-Goelzer",
    "20": "Pullen SD",
    "21": "Pullen SR",
    "22": "APC Houses",
    "23": "Savard-A",
    "24": "福点整宫制",
}
# 上游 constants/AstroConst.js:1079 INDIA_AYANAMSA_OPTIONS → ayanamsaLabel 用的 label
AYANAMSA_LABELS: dict[str, str] = {
    "lahiri": "Lahiri / Chitrapaksha",
    "lahiri_icrc": "Lahiri ICRC（官定2022）",
    "lahiri_1940": "Lahiri 1940",
    "lahiri_vp285": "Lahiri VP285",
    "raman": "Raman",
    "krishnamurti": "Krishnamurti / KP",
    "krishnamurti_vp291": "KP-Senthilathiban (VP291)",
    "yukteshwar": "Yukteshwar",
    "jn_bhasin": "J.N. Bhasin",
    "ushashashi": "Usha/Shashi",
    "deluce": "De Luce",
    "true_citra": "True Citra（角宿真星）",
    "true_revati": "True Revati（娄宿真星）",
    "true_pushya": "True Pushya / 普舍亚",
    "true_mula": "True Mula（Chandra Hari）",
    "true_sheoran": "Vedic / Sheoran",
    "ss_citra": "SS Citra",
    "ss_revati": "SS Revati",
    "suryasiddhanta": "Surya Siddhanta",
    "suryasiddhanta_msun": "Surya Siddhanta（mean Sun）",
    "aryabhata": "Aryabhata",
    "aryabhata_msun": "Aryabhata（mean Sun）",
    "aryabhata_522": "Aryabhata 522",
    "fagan_bradley": "Fagan/Bradley",
    "djwhal_khul": "Djwhal Khul",
    "valens_moon": "Vettius Valens",
    "galcent_0sag": "Galactic Center 0°Sag（银心）",
    "galcent_rgilbrand": "Galactic Center（Gil Brand）",
    "galcent_mula_wilhelm": "Galactic Center/Mula（Wilhelm）",
    "galcent_cochrane": "Galactic Center（Cochrane）",
    "galequ_iau1958": "Galactic Equator（IAU1958）",
    "galequ_true": "Galactic Equator（true）",
    "galequ_mula": "Galactic Equator（mid-Mula）",
    "galequ_fiorenza": "Galactic Equator（Fiorenza）",
    "galalign_mardyks": "Skydram（Mardyks）",
    "hipparchos": "Hipparchos",
    "sassanian": "Sassanian",
    "aldebaran_15tau": "Aldebaran 15°Tau",
    "babyl_kugler1": "Babylonian/Kugler 1",
    "babyl_kugler2": "Babylonian/Kugler 2",
    "babyl_kugler3": "Babylonian/Kugler 3",
    "babyl_huber": "Babylonian/Huber",
    "babyl_etpsc": "Babylonian/Eta Piscium",
    "babyl_britton": "Babylonian/Britton",
    "j2000": "J2000",
    "j1900": "J1900",
    "b1950": "B1950",
}

# 上游 constants/AstroConst.js:86-89 ZODIACAL
ZODIACAL: dict[str, str] = {"0": "Tropical", "1": "Sidereal"}


# ─────────────────────────────── JS 语义小工具 ───────────────────────────────


def _js_truthy(value: Any) -> bool:
    if value is _UNDEFINED or value is None or value is False:
        return False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0 and not (isinstance(value, float) and math.isnan(value))
    if isinstance(value, str):
        return value != ""
    return True


def _js_str(value: Any) -> str:
    """JS 模板字符串里 `${value}` 的结果（String(value)）。"""
    if value is _UNDEFINED:
        return "undefined"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        if value == int(value) and abs(value) < 1e21:
            return str(int(value))
        return repr(value)
    return str(value)


def _js_number(value: Any) -> float:
    """JS `Number(value)`：null→0、undefined→NaN、bool→0/1、字符串去空白后解析（空串→0，非法→NaN）。"""
    if value is _UNDEFINED:
        return math.nan
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return 0.0
        try:
            return float(text)
        except ValueError:
            return math.nan
    return math.nan


def _js_fmod(a: float, b: float) -> float:
    if not math.isfinite(a):
        return math.nan
    return math.fmod(a, b)


def _js_math_round(value: float) -> int:
    # JS Math.round = floor(x + 0.5)（half-up，负数朝 +∞）。
    return math.floor(value + 0.5)


def _get(obj: Any, key: str) -> Any:
    """`obj.key`：obj 非 dict 或缺键 → undefined。"""
    if isinstance(obj, dict) and key in obj:
        return obj[key]
    return _UNDEFINED


def fmt_num(value: Any, digits: int = 2) -> str:
    """AstroExtraCommon.fmtNum（:67-73）：`Number(value).toFixed(digits)`，非有限数 → '-'。"""
    num = _js_number(value)
    if not math.isfinite(num):
        return "-"
    if num == 0:
        num = 0.0  # (-0).toFixed → '0.00'（JS 只对 x < 0 加负号）
    quantum = Decimal(1).scaleb(-digits)
    return format(Decimal(num).quantize(quantum, rounding=ROUND_HALF_UP), "f")


def sign_name(sign_id: Any) -> str:
    """AstroExtraCommon.signName（:63-65）：AstroTxtMsg → AstroMsg → id → '-'。"""
    if sign_id is not _UNDEFINED and sign_id is not None:
        key = _js_str(sign_id)
        if ASTRO_TXT_MSG.get(key):
            return ASTRO_TXT_MSG[key]
        if ASTRO_MSG_TEXT.get(key):
            return ASTRO_MSG_TEXT[key]
    return _js_str(sign_id) if _js_truthy(sign_id) else "-"


def fmt_degree(item: Any) -> str:
    """AstroExtraCommon.fmtDegree（:75-82）：`${signName(sign)} ${fmtNum(signlon, 2)}°`，signlon 缺 → Number(lon) % 30。"""
    if not _js_truthy(item) or not isinstance(item, dict):
        return "-"
    sign = sign_name(_get(item, "sign"))
    signlon = _get(item, "signlon")
    if signlon is _UNDEFINED:
        signlon = _js_fmod(_js_number(_get(item, "lon")), 30)
    return f"{sign} {fmt_num(signlon, 2)}°"


def _txt_name(obj_id: Any) -> str:
    """ephName（AstroEphemeris.js:18-21）/ psName（AstroPrenatalSyzygy.js:32-35）：空 → '-'，否则 AstroTxtMsg[id] || id。"""
    if obj_id is _UNDEFINED or obj_id is None or obj_id == "":
        return "-"
    key = _js_str(obj_id)
    return ASTRO_TXT_MSG.get(key) or key


def _sym(obj_id: Any) -> str:
    """astroProgSnapshot.js:80 `sym`：AstroTxtMsg[id] || `${id}`（无空值兜底）。"""
    key = _js_str(obj_id)
    return ASTRO_TXT_MSG.get(key) or key


_ENCODED_TOKEN = re.compile(r"^[A-Za-z0-9${}]$")


def ai_msg(obj_id: Any) -> str:
    """astroAiSnapshot.js:45-60 `msg`：AstroTxtMsg → AstroMsg（字形 token 回落 id）→ id。"""
    if obj_id is _UNDEFINED or obj_id is None:
        return ""
    key = _js_str(obj_id)
    if ASTRO_TXT_MSG.get(key):
        return ASTRO_TXT_MSG[key]
    val = ASTRO_MSG_TEXT.get(key)
    if val and not _ENCODED_TOKEN.match(val.strip()):
        return val
    return key


# ─────────────────────────── astroAiSnapshot 共享行 ───────────────────────────


def _split_degree(degree: Any) -> tuple[int, int]:
    # astroAiSnapshot.js:110-127。JSON 不会产出 ±Infinity 经度；非有限数同 NaN 处理只为不崩。
    deg = _js_number(degree)
    if not math.isfinite(deg):
        return 0, 0
    negative = deg < 0
    deg = abs(deg)
    d = math.floor(deg)
    minute = math.floor((deg - d) * 60)
    if minute >= 60:
        d += 1
        minute = 0
    if negative:
        d = -d
    return d, minute


def _which_term(sign: Any, deg: int) -> str:
    # astroAiSnapshot.js:129-141
    terms = EGYPTIAN_TERMS.get(_js_str(sign))
    if not terms:
        return ""
    for ruler, start, end in terms:
        if start <= deg < end:
            return ai_msg(ruler)
    return ""


def _format_sign_degree(sign: Any, signlon: Any) -> str:
    # astroAiSnapshot.js:143-152
    if signlon is _UNDEFINED or signlon is None or sign is _UNDEFINED or sign is None:
        return ""
    d, minute = _split_degree(signlon)
    deg = abs(d)
    minute = abs(minute)
    term = _which_term(sign, deg)
    return f"{deg}˚{ai_msg(sign)}{minute}分；位于 {term} 界"


def _format_retrograde_text(obj: Any) -> str:
    # astroAiSnapshot.js:154-163
    lonspeed = _get(obj, "lonspeed")
    if not _js_truthy(obj) or lonspeed is _UNDEFINED or lonspeed is None:
        return ""
    speed = _js_number(lonspeed)
    if math.isnan(speed) or speed >= 0:
        return ""
    return "；逆行"


def _lon_to_sign_degree(lon: Any) -> str:
    # astroAiSnapshot.js:165-177
    if lon is _UNDEFINED or lon is None or math.isnan(_js_number(lon)):
        return ""
    value = _js_fmod(_js_number(lon), 360)
    if value < 0:
        value += 360
    sign_idx = math.floor(value / 30) % 12
    return _format_sign_degree(LIST_SIGNS[sign_idx], value - sign_idx * 30)


_EMPTY_CELL = "—"  # astroAiSnapshot.js:507


def _gfm_table_lines(headers: list[str], rows: list[list[str]]) -> list[str]:
    # astroAiSnapshot.js:510-519：零行 → []（不产孤表头）。
    if not rows:
        return []
    return [
        f"| {' | '.join(headers)} |",
        f"| {' | '.join('---' for _ in headers)} |",
        *[f"| {' | '.join(cells)} |" for cells in rows],
    ]


def _parse_house_num(house_id: Any) -> int | None:
    # planetHouseInfo.js parseHouseNum
    if house_id is _UNDEFINED or house_id is None:
        return None
    matched = re.search(r"\d+", _js_str(house_id))
    if not matched:
        return None
    num = int(matched.group(0))
    return num if num > 0 else None


def _find_chart_object(chart_wrap: Any, obj_id: str) -> dict[str, Any] | None:
    # planetHouseInfo.js findChartObject
    if not _js_truthy(chart_wrap) or not obj_id or not isinstance(chart_wrap, dict):
        return None
    chart = chart_wrap.get("chart") if _js_truthy(chart_wrap.get("chart")) else chart_wrap
    objects = chart.get("objects") if isinstance(chart, dict) and _js_truthy(chart.get("objects")) else []
    for obj in objects or []:
        if isinstance(obj, dict) and obj.get("id") == obj_id:
            return obj
    lots = chart_wrap.get("lots") if _js_truthy(chart_wrap.get("lots")) else (
        chart.get("lots") if isinstance(chart, dict) and _js_truthy(chart.get("lots")) else []
    )
    for obj in lots or []:
        if isinstance(obj, dict) and obj.get("id") == obj_id:
            return obj
    return None


def _format_planet_house_info(obj: dict[str, Any]) -> str:
    # planetHouseInfo.js getPlanetHouseInfo + formatPlanetHouseInfo（showHouse=showRuler=1）
    house_num = _parse_house_num(_get(obj, "house"))
    raw_rules = obj.get("ruleHouses") if _js_truthy(obj.get("ruleHouses")) else []
    rule_nums = sorted({n for n in (_parse_house_num(item) for item in raw_rules or []) if n})
    parts = [f"{house_num}th" if house_num else "-"]
    parts.append("".join(f"{n}R" for n in rule_nums) if rule_nums else "-")
    return "; ".join(parts)


def _msg_with_house(obj_id: str, chart_obj: dict[str, Any]) -> str:
    # astroAiSnapshot.js:98-101 msgWithHouse → appendPlanetHouseInfoById(msg(id), chartObj, id, 全开)
    label = ai_msg(obj_id)
    obj = _find_chart_object(chart_obj, obj_id)
    if obj is not None:
        info = _format_planet_house_info(obj)
        if info:
            label = f"{label} ({info})"
    return re.sub(r"(\d+)R\s*\(宫主\)", r"\1R", label)


def _objects_map(chart_obj: Any) -> dict[str, dict[str, Any]]:
    # fortuneChartPrimitives.getObjectsMapPure：chart.objects 先、chartObj.lots 后（同 id 以 lots 为准）。
    mapping: dict[str, dict[str, Any]] = {}
    chart = chart_obj.get("chart") if isinstance(chart_obj, dict) else None
    if isinstance(chart, dict) and isinstance(chart.get("objects"), list):
        for obj in chart["objects"]:
            if isinstance(obj, dict):
                mapping[_js_str(obj.get("id", _UNDEFINED))] = obj
    if isinstance(chart_obj, dict) and isinstance(chart_obj.get("lots"), list):
        for obj in chart_obj["lots"]:
            if isinstance(obj, dict):
                mapping[_js_str(obj.get("id", _UNDEFINED))] = obj
    return mapping


def build_house_cusp_lines(chart_obj: Any) -> list[str]:
    """astroAiSnapshot.js:521-533 buildHouseCuspLines（GFM 表）。"""
    chart = chart_obj.get("chart") if isinstance(chart_obj, dict) and _js_truthy(chart_obj.get("chart")) else {}
    rows: list[list[str]] = []
    for house in (chart.get("houses") if isinstance(chart, dict) else None) or []:
        if not _js_truthy(house) or not isinstance(house, dict):
            continue
        lon = _get(house, "lon")
        if lon is _UNDEFINED or lon is None:
            continue
        rows.append([ai_msg(_get(house, "id")), _lon_to_sign_degree(lon)])
    return _gfm_table_lines(["宫位", "宫头"], rows)


def build_star_and_lot_position_lines(chart_obj: Any) -> list[str]:
    """astroAiSnapshot.js:535-551 buildStarAndLotPositionLines（GFM 表：点位/位置/逆行）。"""
    object_map = _objects_map(chart_obj)
    rows: list[list[str]] = []

    def push_one(obj_id: str) -> None:
        obj = object_map.get(obj_id)
        if not obj or "sign" not in obj or "signlon" not in obj:
            return
        rows.append([
            _msg_with_house(obj_id, chart_obj),
            _format_sign_degree(obj.get("sign"), obj.get("signlon")),
            _format_retrograde_text(obj) or _EMPTY_CELL,
        ])

    for obj_id in LIST_OBJECTS:
        push_one(obj_id)
    for obj_id in LOTS:
        push_one(obj_id)
    return _gfm_table_lines(["点位", "位置", "逆行"], rows)


def _ayanamsa_label(key: Any) -> str:
    # AstroConst.js ayanamsaLabel
    if not _js_truthy(key):
        return ""
    if key == "user":
        return "自定义（历元槽位）"
    return AYANAMSA_LABELS.get(_js_str(key)) or _js_str(key)


def _zodiacal_display_text(zodiacal_raw: Any, ayan_key: Any) -> str:
    # AstroConst.js zodiacalDisplayText
    is_sid = zodiacal_raw == "Sidereal" or _js_str(zodiacal_raw) == "1" or zodiacal_raw == "恒星黄道"
    if not is_sid:
        return "回归黄道"
    lab = _ayanamsa_label(ayan_key)
    return f"恒星黄道·{lab}" if lab else "恒星黄道"


def predictive_birth_lines(chart_obj: Any) -> list[str]:
    """astroAiSnapshot.js:1956-1989 buildPredictiveBirthLines（盘主生辰 + 黄道宫制盘型 裸行）。"""
    obj = chart_obj if isinstance(chart_obj, dict) else {}
    params = obj.get("params") if isinstance(obj.get("params"), dict) else {}
    chart = obj.get("chart") if isinstance(obj.get("chart"), dict) else {}
    lines: list[str] = []
    if _js_truthy(_get(params, "birth")):
        dayofweek = _get(chart, "dayofweek")
        suffix = f" {_js_str(dayofweek)}" if _js_truthy(dayofweek) else ""
        lines.append(f"出生时间：{_js_str(params['birth'])}{suffix}")
    nongli = _get(chart, "nongli")
    if _js_truthy(nongli) and _js_truthy(_get(nongli, "birth")):
        lines.append(f"真太阳时：{_js_str(nongli['birth'])}")
    lon, lat = _get(params, "lon"), _get(params, "lat")
    if _js_truthy(lon) or _js_truthy(lat):
        lon_txt = _js_str(lon) if _js_truthy(lon) else ""
        lat_txt = _js_str(lat) if _js_truthy(lat) else ""
        lines.append(f"经纬度：{f'{lon_txt} {lat_txt}'.strip()}")
    zone = _get(params, "zone")
    if zone is not _UNDEFINED and zone is not None and zone != "":
        lines.append(f"时区：{_js_str(zone)}")
    chart_zodiacal = _get(chart, "zodiacal")
    zodiacal_raw = chart_zodiacal if _js_truthy(chart_zodiacal) else ZODIACAL.get(_js_str(_get(params, "zodiacal")))
    if _js_truthy(zodiacal_raw):
        ayan_key = next(
            (v for v in (_get(params, "siderealAyanamsa"), _get(chart, "siderealAyanamsa")) if _js_truthy(v)),
            "",
        )
        lines.append(f"黄道：{_zodiacal_display_text(zodiacal_raw, ayan_key)}")
    hsys = HOUSE_SYS.get(_js_str(_get(params, "hsys"))) or _get(chart, "hsys")
    if _js_truthy(hsys):
        lines.append(f"宫制：{_js_str(hsys)}")
    is_diurnal = _get(chart, "isDiurnal")
    if is_diurnal is not _UNDEFINED and is_diurnal is not None:
        lines.append(f"盘型：{'日生盘' if _js_truthy(is_diurnal) else '夜生盘'}")
    return lines


def predictive_birth_header_lines(chart_obj: Any) -> list[str]:
    """astroAiSnapshot.js:1992-1998：无任何盘境数据 → []（不产空段头）。"""
    lines = predictive_birth_lines(chart_obj)
    if not lines:
        return []
    return ["[起盘信息]", *lines, ""]


def _js_date_parse_local(text: str) -> float | None:
    """`Date.parse(text)` 的秒级时间戳（None = NaN）。ISO 带时刻无时区 → 本地时间；纯日期 → UTC。"""
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(text, fmt).timestamp()
        except ValueError:
            continue
    try:
        return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return None


def current_moment_lines(chart_obj: Any, extra_lines: list[str] | None, now: datetime) -> list[str]:
    """astroAiSnapshot.js:2002-2019 buildCurrentMomentLines：导出时刻 + 盘主当前年龄（本地时钟）。"""
    params = chart_obj.get("params") if isinstance(chart_obj, dict) and isinstance(chart_obj.get("params"), dict) else {}
    lines = [f"导出时刻：{now.strftime('%Y-%m-%d %H:%M')}"]
    birth = _get(params, "birth")
    if _js_truthy(birth):
        birth_ts = _js_date_parse_local(_js_str(birth).strip().replace("/", "-").replace(" ", "T", 1))
        if birth_ts is not None:
            age = (now.timestamp() - birth_ts) / (365.2425 * 24 * 3600)
            if math.isfinite(age) and -1 < age < 200:
                lines.append(f"盘主当前年龄：{_js_str(_js_math_round(age * 100) / 100)} 岁")
    for line in extra_lines or []:
        if _js_truthy(line):
            lines.append(_js_str(line))
    return ["[当前时点]", *lines, ""]


def method_note_lines(notes: list[str] | None) -> list[str]:
    """astroAiSnapshot.js:2140-2146 buildMethodNoteLines（notes = 该键的 PREDICTIVE_METHOD_NOTES）。"""
    if not notes:
        return []
    return ["[方法说明]", *notes, ""]


# ─────────────────────────────── 星历 ephemeris ───────────────────────────────


def _fmt_date_of(item: Any) -> str:
    # AstroEphemeris.js:109-112 fmtDateOf
    if _js_truthy(item) and isinstance(item, dict):
        if _js_truthy(item.get("date")):
            return _js_str(item["date"])
        if _js_truthy(item.get("datetime")):
            head = _js_str(item["datetime"]).split(" ")[0]
            if head:
                return head
    return "-"


def ephemeris_limits_text(params: Any) -> str:
    """AstroEphemeris.js:114-126 ephemerisLimitsText：后端三道截断（区间/逐日/行运触发）明示句；无截断 → ''。"""
    if not _js_truthy(params) or not isinstance(params, dict):
        return ""
    lim = params.get("limits")
    if not _js_truthy(lim) or not isinstance(lim, dict):
        return ""
    notes: list[str] = []
    if _js_truthy(lim.get("rangeTruncated")):
        notes.append(
            f"区间超过 {_js_str(_get(lim, 'rangeDays'))} 天上限，有效区间 {_fmt_date_of(params.get('startDate'))} 至 "
            f"{_fmt_date_of(params.get('endDate'))}（请求至 {_fmt_date_of(lim.get('requestedEndDate'))}）"
        )
    if _js_truthy(lim.get("dailyTruncated")):
        notes.append(f"每日位置只列前 {_js_str(_get(lim, 'dailyDays'))} 天")
    if _js_truthy(lim.get("transitTruncated")):
        notes.append(
            f"行运触发共 {_js_str(_get(lim, 'transitTotal'))} 条，按时间先后只列前 {_js_str(_get(lim, 'transitLimit'))} 条"
        )
    return f"{'；'.join(notes)}（缩小日期范围可查看全部）" if notes else ""


def _cell(value: Any) -> str:
    """`${x || '-'}`"""
    return _js_str(value) if _js_truthy(value) else "-"


def _list_of(result: dict[str, Any], key: str) -> list[Any]:
    value = result.get(key)
    return value if isinstance(value, list) else []


def build_ephemeris_snapshot_text(
    chart_obj: Any,
    result: Any,
    *,
    start_date: str,
    end_date: str,
    include_transits: bool,
    now: datetime,
    method_notes: list[str] | None,
) -> str:
    """AstroEphemeris.js:30-94 buildEphemerisSnapshotText（result = /astroextra/ephemeris 解包后）。无数据 → ''。"""
    if not _js_truthy(chart_obj):
        return ""
    if not _js_truthy(result) or not isinstance(result, dict):
        return ""
    ing = _list_of(result, "ingresses")
    sta = _list_of(result, "stations")
    ph = _list_of(result, "lunarPhases")
    ecl = _list_of(result, "eclipses")
    ta = _list_of(result, "transitAspects")
    if not ing and not sta and not ph and not ecl and not ta:
        return ""
    cap = 60
    lines: list[str] = [*predictive_birth_header_lines(chart_obj)]
    lines.append("[星历事件（入座 · 留逆 · 朔望弦 · 食相）]")
    lines.append(f"区间：{start_date} 至 {end_date}（以本命盘地点与时区计;各表最多列 {cap} 行）")
    lim_text = ephemeris_limits_text(result.get("params"))
    if lim_text:
        lines.append(f"截断说明：{lim_text}")
    lines.append("")
    lines.append("入座：")
    lines.append("| 时间 | 星体 | 进入 | 位置 |")
    lines.append("| --- | --- | --- | --- |")
    if not ing:
        lines.append("| — | — | — | — |")
    for e in ing[:cap]:
        lines.append(f"| {_cell(_get(e, 'datetime'))} | {_txt_name(_get(e, 'body'))} | {_txt_name(_get(e, 'toSign'))} | {fmt_degree(e)} |")
    lines.append("")
    lines.append("留与顺逆转向：")
    lines.append("| 时间 | 星体 | 方向 | 位置 |")
    lines.append("| --- | --- | --- | --- |")
    if not sta:
        lines.append("| — | — | — | — |")
    for e in sta[:cap]:
        lines.append(f"| {_cell(_get(e, 'datetime'))} | {_txt_name(_get(e, 'body'))} | {_cell(_get(e, 'direction'))} | {fmt_degree(e)} |")
    lines.append("")
    lines.append("朔望弦：")
    lines.append("| 时间 | 月相 | 月亮位置 |")
    lines.append("| --- | --- | --- |")
    if not ph:
        lines.append("| — | — | — |")
    for e in ph[:cap]:
        lines.append(f"| {_cell(_get(e, 'datetime'))} | {_cell(_get(e, 'phase'))} | {fmt_degree(e)} |")
    lines.append("")
    lines.append("食相：")
    lines.append("| 时间 | 类型 | 细分 | 位置 | 食分 |")
    lines.append("| --- | --- | --- | --- | --- |")
    if not ecl:
        lines.append("| — | — | — | — | — |")
    for e in ecl[:cap]:
        digit = _get(e, "digit")
        band = _get(e, "band")
        if digit is _UNDEFINED or digit is None:  # JS `e.digit == null`
            digit_text = "—"
        else:
            digit_text = f"{fmt_num(digit)}{(' ' + _js_str(band)) if _js_truthy(band) else ''}"
        lines.append(
            f"| {_cell(_get(e, 'datetime'))} | {_cell(_get(e, 'type'))} | {_cell(_get(e, 'eclipseType'))} | {fmt_degree(e)} | {digit_text} |"
        )
    lines.append("")
    lines.append("[行运触发本命]")
    if include_transits is False:
        lines.append("（未纳入：本次未勾选「行运触发本命」。）")
    else:
        lines.append("| 时间 | 行运 | 相位 | 本命 | 误差 |")
        lines.append("| --- | --- | --- | --- | --- |")
        if not ta:
            lines.append("| — | — | — | — | — |")
        for e in ta[:cap]:
            lines.append(
                f"| {_cell(_get(e, 'datetime'))} | {_txt_name(_get(e, 'transitBody'))} | {fmt_num(_get(e, 'aspect'), 0)}° | "
                f"{_txt_name(_get(e, 'natalPoint'))} | {fmt_num(_get(e, 'orb'), 3)} |"
            )
    tail = [*current_moment_lines(chart_obj, [], now), *method_note_lines(method_notes)]
    if tail:
        lines.append("")
        lines.extend(tail)
    return "\n".join(lines)


# ─────────────────────────────── 回归轴 returntimeline ───────────────────────────────


def _rt_deg(value: Any) -> str:
    # AstroReturnTimeline.js:13-16 rtDeg
    if not _js_truthy(value):
        return "-"
    return fmt_degree(value)


def _datetime_of(value: Any) -> str:
    if _js_truthy(value) and isinstance(value, dict) and _js_truthy(value.get("datetime")):
        return _js_str(value["datetime"])
    return "-"


def build_return_timeline_snapshot_text(
    chart_obj: Any,
    rows: Any,
    *,
    start_year: Any,
    count: Any,
    now: datetime,
    method_notes: list[str] | None,
) -> str:
    """AstroReturnTimeline.js:18-45 buildReturnTimelineSnapshotText（rows = /astroextra/returns 的 rows）。无行 → ''。"""
    if not _js_truthy(chart_obj):
        return ""
    rows = rows if isinstance(rows, list) else []
    if not rows:
        return ""
    lines: list[str] = [*predictive_birth_header_lines(chart_obj)]
    lines.append("[太阳/月亮返照时间轴]")
    lines.append(
        f"区间：{_js_str(start_year)} 年起 {_js_str(count)} 年（太阳返照 = 太阳回到本命度;首个月亮返照 = 该年首个月亮回本命度）"
    )
    lines.append("| 年份 | 太阳返照 | 首个月亮返照 | 太阳返照上升 | 月亮返照上升 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for row in rows:
        sr = _datetime_of(_get(row, "solarReturn"))
        lr = _datetime_of(_get(row, "lunarReturn"))
        lines.append(
            f"| {_js_str(_get(row, 'year'))} | {sr} | {lr} | {_rt_deg(_get(row, 'solarAsc'))} | {_rt_deg(_get(row, 'lunarAsc'))} |"
        )
    tail = [*current_moment_lines(chart_obj, [], now), *method_note_lines(method_notes)]
    if tail:
        lines.append("")
        lines.extend(tail)
    return "\n".join(lines)


# ─────────────────────────────── 产前朔望 prenatalsyzygy ───────────────────────────────

# AstroPrenatalSyzygy.js:27
SYZYGY_TYPE_CN: dict[str, str] = {"new": "朔（日月合）", "full": "望（日月冲）"}


def split_syzygy_datetime(value: Any) -> dict[str, str] | None:
    """AstroPrenatalSyzygy.js:81-86 splitDateTime：朔望时刻 → 起盘用 {date: 'YYYY/MM/DD', time}。"""
    text = f"{value if value is not None and value is not _UNDEFINED else ''}".strip()
    if not text:
        return None
    parts = text.replace("T", " ", 1).split(" ")
    return {"date": (parts[0] if parts else "").replace("-", "/"), "time": parts[1] if len(parts) > 1 and parts[1] else "12:00:00"}


def build_prenatal_syzygy_snapshot_text(
    chart_obj: Any,
    syzygy: Any,
    syzygy_chart: Any,
    *,
    now: datetime,
    method_notes: list[str] | None,
) -> str:
    """AstroPrenatalSyzygy.js:37-79 buildPrenatalSyzygySnapshotText。

    syzygy = /astroextra/prenatal_syzygy 解包后；syzygy_chart = 以朔望时刻起的 /chart（取不到传 None，
    段内如上游写「暂缺」行）。求不得朔望（无 type）→ ''。
    """
    if not _js_truthy(chart_obj):
        return ""
    s = syzygy if isinstance(syzygy, dict) else None
    if not s or not _js_truthy(s.get("type")):
        return ""
    syz_type = s.get("type")
    lines: list[str] = [*predictive_birth_header_lines(chart_obj)]
    lines.append("[产前朔望]")
    lines.append(f"类型：{SYZYGY_TYPE_CN.get(_js_str(syz_type)) or _js_str(syz_type)}")
    lines.append(f"时刻：{_js_str(s['datetime']) if _js_truthy(s.get('datetime')) else '—'}")
    days = _get(s, "daysBeforeBirth")
    lines.append(f"出生前：{f'{fmt_num(days, 2)} 天' if days is not _UNDEFINED and days is not None else '—'}")
    lines.append(
        f"取度发光体：{_txt_name(_get(s, 'hylegBody'))}（{'朔→合相度' if syz_type == 'new' else '望→地平之上发光体度'}）"
    )
    lines.append(f"取度：{fmt_degree({'sign': _get(s, 'hylegSign'), 'signlon': _get(s, 'hylegSignlon')})}")
    lines.append("")
    lines.append("[产前朔望盘·星体位置]")
    chart = syzygy_chart.get("chart") if isinstance(syzygy_chart, dict) else None
    objs = chart.get("objects") if isinstance(chart, dict) and isinstance(chart.get("objects"), list) else []
    if not objs:
        lines.append("（产前朔望盘暂缺：未能以朔望时刻排盘。）")
    else:
        lines.append("（以产前朔望时刻为出生时刻、出生地不变排盘。）")
        lines.append("| 星体 | 星座 | 座内度 |")
        lines.append("| --- | --- | --- |")
        for o in objs:
            if not _js_truthy(o) or not isinstance(o, dict) or not _js_truthy(o.get("id")):
                continue
            signlon = _get(o, "signlon")
            deg = f"{fmt_num(signlon, 2)}°" if signlon is not _UNDEFINED and signlon is not None else "-"
            lines.append(f"| {_txt_name(o['id'])} | {_txt_name(_get(o, 'sign'))} | {deg} |")
    tail = [*current_moment_lines(chart_obj, [], now), *method_note_lines(method_notes)]
    if tail:
        lines.append("")
        lines.extend(tail)
    return "\n".join(lines)


# ─────────────────────────────── 推运 prog / vedicprog ───────────────────────────────

# astroProgSnapshot.js:34-48：两支只差 zodiacal 与三处文案（zodiacal=None → 回归支不下发该键，透传盘自身黄道）。
PROG_SNAPSHOT_VARIANTS: dict[str, dict[str, Any]] = {
    "vedicprog": {
        "zodiacal": 1,
        "section": "恒星推运（Vedic Sidereal）",
        "intro": "二次/三次/小限推运在恒星黄道（sidereal）下计算；下表为二次推运，推至下方所列目标日期。",
        "posCol": "恒星推运位置",
    },
    "prog": {
        "zodiacal": None,
        "section": "二次推运（回归黄道）",
        "intro": "二次/三次/小限推运在回归黄道（tropical）下计算；下表为二次推运，推至下方所列目标日期。",
        "posCol": "推运位置",
    },
}

# AstroProgChart.js:21-27（[Q-180] 缺省 synodic = 标准朔望月）
MINOR_VARIANT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("synodic", "朔望月每年（标准·默认）"),
    ("sidereal", "恒星月每年"),
    ("engine", "引擎历史值（≈无推进）"),
)
MINOR_VARIANT_LABEL: dict[str, str] = dict(MINOR_VARIANT_OPTIONS)
DEFAULT_MINOR_VARIANT = "synodic"

# astroProgSnapshot.js:21
_PROG_EVENT_POINTS = ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Asc", "MC")


def _method_tab(method: Any) -> str:
    # astroProgSnapshot.js:27-29
    name = _get(method, "method")
    return "二次推运" if name == "secondary" else ("三次推运" if name == "tertiary" else "小推运")


def build_prog_snapshot_text(
    chart_obj: Any,
    result: Any,
    variant_key: str,
    *,
    target_date: str,
    target_time: str,
    minor_variant: str,
    now: datetime,
    method_notes: list[str] | None,
) -> str:
    """astroProgSnapshot.js:52-142 buildProgSnapshotText（result = /astroextra/progressions 解包后）。

    target_date/target_time/minor_variant 由 runner 按上游缺省（今天 / 12:00:00 / synodic）解析好再传入。
    无盘、未知 variant、二次推运无位置 → ''。
    """
    variant = PROG_SNAPSHOT_VARIANTS.get(f"{variant_key or ''}")
    if not _js_truthy(chart_obj) or not variant:
        return ""
    methods = result.get("methods") if isinstance(result, dict) and isinstance(result.get("methods"), list) else []
    secondary = next((m for m in methods if isinstance(m, dict) and m.get("method") == "secondary"), None)
    if secondary is None and methods:
        secondary = methods[0]
    positions = _get(secondary, "positions")
    if not isinstance(secondary, dict) or not isinstance(positions, list) or not positions:
        return ""

    def event_points(items: list[Any]) -> list[dict[str, Any]]:
        return [p for p in items if isinstance(p, dict) and p.get("id") in _PROG_EVENT_POINTS]

    lines: list[str] = []
    lines.append(f"[{variant['section']}]")
    lines.append(variant["intro"])
    lines.append(f"目标日期：{target_date} {target_time}（各法推运时刻=按该法折算，见各小节）")
    natal_stars = build_star_and_lot_position_lines(chart_obj)
    natal_houses = build_house_cusp_lines(chart_obj)
    natal_birth = predictive_birth_lines(chart_obj)
    if natal_stars or natal_houses or natal_birth:
        lines.append("")
        lines.append("[本命盘配置]")
        if natal_birth:
            lines.extend(natal_birth)
        if natal_stars:
            lines.append("星与虚点")
            lines.extend(natal_stars)
        if natal_houses:
            lines.append("宫位宫头")
            lines.extend(natal_houses)
    lines.append("")
    lines.append("[时段盘配置 二次推运位置]")
    lines.append(f"| 点 | {variant['posCol']} |")
    lines.append("| --- | --- |")
    for p in event_points(positions):
        lines.append(f"| {_sym(p.get('id'))} | {fmt_degree(p)} |")

    def asp_txt(value: Any) -> str:
        return ASTRO_TXT_MSG.get(f"Asp{fmt_num(value, 0)}") or f"{fmt_num(value, 0)}°"

    def push_method_blocks(method: Any, with_positions: bool) -> None:
        if not _js_truthy(method) or not isinstance(method, dict):
            return
        label = _method_tab(method)
        progressed = method.get("progressedDate")
        when = _js_str(progressed["datetime"]) if isinstance(progressed, dict) and _js_truthy(progressed.get("datetime")) else ""
        m_positions = method.get("positions")
        if with_positions and isinstance(m_positions, list) and m_positions:
            lines.append("")
            lines.append(f"◆ {label} 推运位置")
            if when:
                lines.append(f"推运时刻：{when}")
            if method.get("method") == "minor":
                lines.append(f"月长算法：{MINOR_VARIANT_LABEL.get(minor_variant) or minor_variant}")
            lines.append(f"| 点 | {variant['posCol']} | 速度 |")
            lines.append("| --- | --- | --- |")
            for p in event_points(m_positions):
                lines.append(f"| {_sym(p.get('id'))} | {fmt_degree(p)} | {fmt_num(_get(p, 'lonspeed'), 4)} |")
        aspects = method.get("aspectsToNatal")
        if isinstance(aspects, list) and aspects:
            lines.append("")
            lines.append(f"◆ {label} 与本命相位")
            lines.append("| 推运点 | 相位 | 本命点 | 误差 |")
            lines.append("| --- | --- | --- | --- |")
            for p in aspects[:120]:
                lines.append(
                    f"| {_sym(_get(p, 'a'))} | {asp_txt(_get(p, 'aspect'))} | {_sym(_get(p, 'b'))} | {fmt_num(_get(p, 'orb'), 3)} |"
                )

    push_method_blocks(secondary, False)
    for method in methods:
        if _js_truthy(method) and method is not secondary:
            push_method_blocks(method, True)
    lines.append("")
    lines.extend(current_moment_lines(chart_obj, [], now))
    lines.extend(method_note_lines(method_notes))
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)
