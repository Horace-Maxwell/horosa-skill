"""星运族快照的「文字层」移植（上游星阙 v3.11.1+，Horosa-Public HEAD 9b74714b）。

纯数据 + 纯函数，不依赖 service（service 的推运 builder 调这里的 helper 逐字镜像上游文字）。
每个常量/函数都注明上游出处；改这里 = 跟上游对账，别凭记忆改字。

⚠ 名称表口径：上游推运 builder 一律用 `AstroText.AstroTxtMsg[id] || id`——行星是**单字**（日/月/水…），
星座是 牡羊/金牛…，相位是 0º/60º…（º = U+00BA）。本仓 `service.ASTRO_TEXT_MAP` 是另一张表（太阳/月亮…），
两者不可混用：镜像上游推运文字时只用本模块的 `astro_txt` / `asp_txt`。
"""

from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from horosa_skill.engine import astroextra_snapshots as _shared

# 上游名称表 / 宫制 / 岁差 / 小推运月长档：与星运新四键同源的那一份（engine/astroextra_snapshots，逐字抽自
# constants/AstroText.js · AstroConst.js · AstroProgChart.js）。两路并行实现曾各抄一份（值一致），现只留一份。
UPSTREAM_ASTRO_TXT_MSG: dict[str, str] = _shared.ASTRO_TXT_MSG
LIST_SIGNS: tuple[str, ...] = _shared.LIST_SIGNS
HOUSE_SYS_LABELS: dict[str, str] = _shared.HOUSE_SYS
ZODIACAL: dict[str, str] = _shared.ZODIACAL
AYANAMSA_LABELS: dict[str, str] = _shared.AYANAMSA_LABELS
MINOR_VARIANT_OPTIONS: tuple[tuple[str, str], ...] = _shared.MINOR_VARIANT_OPTIONS
MINOR_VARIANT_LABEL: dict[str, str] = _shared.MINOR_VARIANT_LABEL
DEFAULT_MINOR_VARIANT: str = _shared.DEFAULT_MINOR_VARIANT

# 上游 HEAD divination/data/hellenisticData.json planetary_years：行星年四档（planetaryAges.js:99-110 ◆ 行星年四档 子块）。
# 与 vendored 副本 horosa-core-js/src/vendor/divination/data/hellenisticData.json 同值（测试互锚；该 JSON 由
# vendor manifest 逐字节对上游看守——v3.11.0 改日/月中年 39.5→69.5/66.5 时它曾因 manifest 只登记 .js 而滞留）。
PLANETARY_YEARS: dict[str, dict[str, float]] = {
    "Saturn": {"least": 30, "mean": 43.5, "greater": 57, "greatest": 465},
    "Jupiter": {"least": 12, "mean": 45.5, "greater": 79, "greatest": 427},
    "Mars": {"least": 15, "mean": 40.5, "greater": 66, "greatest": 284},
    "Sun": {"least": 19, "mean": 69.5, "greater": 120, "greatest": 1461},
    "Venus": {"least": 8, "mean": 45, "greater": 82, "greatest": 1151},
    "Mercury": {"least": 20, "mean": 48, "greater": 76, "greatest": 480},
    "Moon": {"least": 25, "mean": 66.5, "greater": 108, "greatest": 520},
}

# ── JS 语义小工具（字符串化 / 取整 / toFixed 必须与浏览器逐字同形）──────────────────────────────

def js_str(value: Any) -> str:
    """JS 模板串 `${v}` 的数字/字符串形：整数值的 float 不带 `.0`（60.0 → '60'），bool → true/false。"""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if math.isfinite(value) and value == int(value):
            return str(int(value))
        return repr(value)
    return f"{value}"


def js_round(value: float) -> float:
    """JS `Math.round`：半数向 +∞（Python round 是银行家舍入，不可替代）。"""
    return float(math.floor(value + 0.5))


def js_round2(value: float) -> float:
    """`Math.round(x * 100) / 100` 的逐字镜像。"""
    return js_round(value * 100) / 100


def js_to_fixed(value: Any, digits: int) -> str:
    """JS `Number.prototype.toFixed`：按 double 的精确十进制值四舍五入（半数远离零）。"""
    number = float(value)
    quant = Decimal(1).scaleb(-digits)
    return f"{Decimal(number).quantize(quant, rounding=ROUND_HALF_UP):.{digits}f}"


def js_fmt_num(value: Any, digits: int = 2) -> str:
    """上游 components/astro/AstroExtraCommon.js:67 `fmtNum`：非有限数 → '-'，否则 toFixed(digits)。"""
    if value is None or isinstance(value, bool):
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    if not math.isfinite(number):
        return "-"
    return js_to_fixed(number, digits)


def sign_name(value: Any) -> str:
    """AstroExtraCommon.js:63 `signName`：AstroTxtMsg[id] || id || '-'（AstroMsg 是字形表，文本快照用不到）。"""
    key = js_str(value)
    return UPSTREAM_ASTRO_TXT_MSG.get(key) or key or "-"


def fmt_degree(item: dict[str, Any] | None) -> str:
    """AstroExtraCommon.js:75 `fmtDegree`：`<座> <座内度 toFixed(2)>°`。"""
    if not item:
        return "-"
    signlon = item.get("signlon") if "signlon" in item else None
    if signlon is None:
        try:
            signlon = float(item.get("lon")) % 30
        except (TypeError, ValueError):
            signlon = None
    return f"{sign_name(item.get('sign'))} {js_fmt_num(signlon, 2)}°"



def prog_method_tab(method: dict[str, Any]) -> str:
    """astroProgSnapshot.js:28 / AstroJaynesProgressions.js:26 `methodTab`。"""
    name = method.get("method")
    return "二次推运" if name == "secondary" else ("三次推运" if name == "tertiary" else "小推运")


def astro_txt(value: Any) -> str:
    """`AstroText.AstroTxtMsg[id] || \\`${id}\\``（上游推运 builder 的通用名称函数）。"""
    key = js_str(value)
    return UPSTREAM_ASTRO_TXT_MSG.get(key) or key


# 上游 constants/AstroText.js:139-339 AstroMsg 里 AstroTxtMsg 未收的条目（:149-150 Retrograde/Unknown 字形、
# :240-255 尊贵/日光态字串键、:257-339 宫位/月相象限/恒星/黄道/宫制文字条目；其余 AstroMsg 键 AstroTxtMsg 都有，
# 走不到这张表）。主限法 msg() 先 AstroTxtMsg 后 AstroMsg——恒星迫星 FS_Algol 因此落「大陵五」而不是 Algol。
UPSTREAM_ASTRO_MSG_FALLBACK: dict[str, str] = {
    "Retrograde": "Z", "Unknown": "{",
    "ruler": "本垣", "exalt": "擢升", "dayTrip": "日三分", "nightTrip": "夜三分", "partTrip": "共管三分",
    "term": "界", "face": "十度", "exile": "陷", "fall": "落", "Hayyiz": "得时得地", "DemiHayyiz": "得时不得地",
    "InWrongPos": "失时", "Cazimi": "日熔", "Combust": "灼伤", "Sunbeams": "日光蔽匿",
    "House1": "第一宫", "House2": "第二宫", "House3": "第三宫", "House4": "第四宫", "House5": "第五宫",
    "House6": "第六宫", "House7": "第七宫", "House8": "第八宫", "House9": "第九宫", "House10": "第十宫",
    "House11": "第十一宫", "House12": "第十二宫",
    "First Quarter": "第一象限", "Second Quarter": "第二象限", "Third Quarter": "第三象限", "Last Quarter": "第四象限",
    "Algenib": "壁宿一", "Alpheratz": "壁宿二", "Zaur": "天苑一", "Algol": "大陵五", "Alcyone": "昴宿六",
    "Aldebaran": "毕宿五", "Rigel": "参宿七", "Capella": "五车二", "Betelgeuse": "参宿四", "Sirius": "天狼星",
    "Canopus": "老人星", "Castor": "北河二", "Pollux": "北河三", "Procyon": "南河三", "Asellus Borealis": "鬼宿三",
    "Asellus Australis": "鬼宿四", "Alphard": "星宿一", "Regulus": "狮心轩辕十四", "Denebola": "五帝座一",
    "Algorab": "轸宿三", "Spica": "角宿一", "Arcturus": "大角", "Alphecca": "贯索四", "Zuben Elgenubi": "氐宿一",
    "Zuben Eshamali": "氐宿四", "Unukalhai": "天市右垣七", "Agena": "马腹一", "Rigel Kentaurus": "南門二",
    "Antares": "蝎心心宿二", "Lesath": "尾宿九", "Vega": "织女星", "Altair": "牛郎星", "Deneb Algedi": "垒壁阵四",
    "Fomalhaut": "北落师门", "Deneb": "天津四", "Achernar": "水委一",
    "Tropical": "回归黄道",
    "Whole Sign": "整宫制", "Alcabitus": "Alcabitus", "Regiomontanus": "Regiomontanus", "Placidus": "Placidus",
    "Koch": "Koch", "Vehlow Equal": "Vehlow Equal", "Polich Page": "Polich Page", "Sripati": "Sripati",
    "Porphyrius": "Porphyry", "Campanus": "Campanus", "Equal": "Equal", "Equal MC": "Equal MC", "Meridian": "Meridian",
    "Azimuthal": "Horizontal", "Morinus": "Morinus", "Carter Poli-Equatorial": "Carter Poli-Equatorial",
    "Sunshine": "Sunshine", "Sunshine Alternate": "Sunshine Alternate", "Krusinski-Pisa-Goelzer": "Krusinski-Pisa-Goelzer",
    "Pullen SD": "Pullen SD", "Pullen SR": "Pullen SR", "APC Houses": "APC Houses", "Savard-A": "Savard-A",
    "Fortuna_Whole": "福点整宫制",
}


def astro_msg(value: Any) -> str:
    """AstroDirectMain.js:100-111 `msg(id)`：null → ''；AstroTxtMsg[id] → AstroMsg[id] → `${id}`。"""
    if value is None:
        return ""
    key = js_str(value)
    return UPSTREAM_ASTRO_TXT_MSG.get(key) or UPSTREAM_ASTRO_MSG_FALLBACK.get(key) or key


def asp_txt(deg: Any) -> str:
    """`AstroText.AstroTxtMsg['Asp' + deg] || \\`${deg}°\\``（persian/planetaryarc 等的相位名）。"""
    key = js_str(deg)
    return UPSTREAM_ASTRO_TXT_MSG.get(f"Asp{key}") or f"{key}°"


def ayanamsa_label(key: Any) -> str:
    """上游 AstroConst.ayanamsaLabel（:1220）。"""
    if not key:
        return ""
    if key == "user":
        return "自定义（历元槽位）"
    return AYANAMSA_LABELS.get(f"{key}", f"{key}")


def zodiacal_display_text(zodiacal_raw: Any, ayan_key: Any) -> str:
    """上游 AstroConst.zodiacalDisplayText（:1227）：回归黄道 / 恒星黄道·<ayan> / 恒星黄道。"""
    is_sid = zodiacal_raw == "Sidereal" or js_str(zodiacal_raw) == "1" or zodiacal_raw == "恒星黄道"
    if not is_sid:
        return "回归黄道"
    label = ayanamsa_label(ayan_key)
    return f"恒星黄道·{label}" if label else "恒星黄道"


def build_predictive_birth_lines(chart_wrap: dict[str, Any] | None) -> list[str]:
    """上游 utils/astroAiSnapshot.js:1956 `buildPredictiveBirthLines(chartObj)`。

    chart_wrap = /chart 响应（{params, chart}）。缺盘时只出 params 能给的行（不猜昼夜）。
    """
    obj = chart_wrap if isinstance(chart_wrap, dict) else {}
    params = obj.get("params") if isinstance(obj.get("params"), dict) else {}
    chart = obj.get("chart") if isinstance(obj.get("chart"), dict) else {}
    lines: list[str] = []
    if params.get("birth"):
        dayofweek = chart.get("dayofweek")
        lines.append(f"出生时间：{params['birth']}{f' {dayofweek}' if dayofweek else ''}")
    nongli = chart.get("nongli")
    if isinstance(nongli, dict) and nongli.get("birth"):
        lines.append(f"真太阳时：{nongli['birth']}")
    lon, lat = params.get("lon"), params.get("lat")
    if lon or lat:
        lines.append(f"经纬度：{f'{js_str(lon) if lon else ''} {js_str(lat) if lat else ''}'.strip()}")
    zone = params.get("zone")
    if zone is not None and zone != "":
        lines.append(f"时区：{zone}")
    zodiacal_raw = chart.get("zodiacal") or ZODIACAL.get(js_str(params.get("zodiacal")))
    if zodiacal_raw:
        ayan_key = params.get("siderealAyanamsa") or chart.get("siderealAyanamsa") or ""
        lines.append(f"黄道：{zodiacal_display_text(zodiacal_raw, ayan_key)}")
    hsys = HOUSE_SYS_LABELS.get(js_str(params.get("hsys"))) or chart.get("hsys")
    if hsys:
        lines.append(f"宫制：{hsys}")
    if chart.get("isDiurnal") is not None:
        lines.append(f"盘型：{'日生盘' if chart.get('isDiurnal') else '夜生盘'}")
    return lines


def payload_chart_wrap(payload: dict[str, Any]) -> dict[str, Any]:
    """无本命盘响应时的降级 wrap：只用请求载荷拼 params（出生时间/经纬度/时区/黄道/宫制），不猜昼夜。"""
    date = f"{payload.get('date') or ''}".strip()
    time = f"{payload.get('time') or ''}".strip()
    params: dict[str, Any] = {
        "birth": f"{date} {time}".strip() or None,
        "lon": payload.get("lon"),
        "lat": payload.get("lat"),
        "zone": payload.get("zone"),
        "zodiacal": payload.get("zodiacal"),
        "hsys": payload.get("hsys"),
        "siderealAyanamsa": payload.get("siderealAyanamsa"),
    }
    return {"params": params, "chart": {}}


# ── 上游 components/comp/DateTime.js 的 jdn 口径（profectionSummary 用它算整岁/月/日）─────────────

def _zone_days(zone: Any) -> float:
    """DateTime.getZoneJdn：'+HH:MM' → 天数；畸形按 0（与上游兜底同）。"""
    if not isinstance(zone, str) or not zone:
        return 0.0
    parts = zone.split(":")
    head = parts[0]
    sign = 1
    if head.startswith("+"):
        head = head[1:]
    elif head.startswith("-"):
        head = head[1:]
        sign = -1
    try:
        hours = int(head)
    except ValueError:
        hours = 0
    try:
        minutes = int(parts[1]) if len(parts) > 1 else 0
    except ValueError:
        minutes = 0
    return sign * (hours + minutes / 60.0) / 24.0


def js_datetime_jdn(text: str, zone: Any = "+08:00") -> float | None:
    """`new DateTime().parse(text,'YYYY-MM-DD HH:mm:ss')` 后的 `.jdn`（DateTime 缺省时区 +08:00）。

    上游 DateTime.parse 只按空格切日期/时间、按 '/' 或 '-' 切年月日，前导 '-' = 公元前；
    getOnlyDateNum 在 1582-10-15 前走儒略历。
    """
    raw = f"{text or ''}".strip().replace("T", " ")
    if not raw:
        return None
    parts = raw.split(" ")
    dstr = parts[0]
    tmstr = parts[1] if len(parts) > 1 else "12:00:00"
    ad = 1
    if dstr.startswith("-"):
        ad = -1
        dstr = dstr[1:]
    dparts = dstr.split("/")
    if len(dparts) == 1:
        dparts = dstr.split("-")
    if len(dparts) == 1:
        dparts += ["01", "01"]
    tparts = tmstr.split(":")
    if len(tparts) == 2:
        tparts.append("00")
    try:
        year, month, day = int(dparts[0]), int(dparts[1]), int(dparts[2])
        hour, minute, second = int(tparts[0]), int(tparts[1]), int(tparts[2])
    except (ValueError, IndexError):
        return None
    a = (14 - month) // 12
    y = ad * year + 4800 - a
    if ad < 0:
        y += 1
    m = month + 12 * a - 3
    signed_year = ad * year
    is_grego = not (
        signed_year < 1582
        or (signed_year == 1582 and month < 10)
        or (signed_year == 1582 and month == 10 and day < 15)
    )
    if is_grego:
        jdn = day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
    else:
        jdn = day + (153 * m + 2) // 5 + 365 * y + y // 4 - 32083
    time_days = (hour + minute / 60.0 + second / 3600.0) / 24.0
    return jdn + time_days - _zone_days(zone) - 0.5


# ── 上游 utils/profectionSummary.js（[Q-105] 年/月/日小限 + 多起点，纯前端派生）──────────────────

# :13-24 选项（与页面控件 / 挂载齿轮同值域）。
PROFECTION_GRAIN_OPTIONS: tuple[tuple[str, str], ...] = (("y", "年"), ("m", "月"), ("d", "日"))
PROFECTION_START_OPTIONS: tuple[tuple[str, str], ...] = (
    ("asc", "上升（默认）"), ("sect", "区分光（昼日夜月）"), ("fortune", "福点"), ("moon", "月亮"), ("mc", "天顶"),
)
PROFECTION_GRAIN_CN: dict[str, str] = {"y": "年", "m": "月", "d": "日"}
PROFECTION_START_CN: dict[str, str] = {"asc": "上升", "sect": "区分光", "fortune": "福点", "moon": "月亮", "mc": "天顶"}
# 座序庙主（divination/data/signs.js 的 domicile）→ 行星 id。
_SIGN_DOMICILE: dict[str, str] = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury",
    "Libra": "Venus", "Scorpio": "Mars", "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn",
    "Pisces": "Jupiter",
}


def normalize_profection_grain(value: Any) -> str:
    return value if value in ("m", "d") else "y"


def normalize_profection_start(value: Any) -> str:
    return value if value in PROFECTION_START_CN else "asc"


def profection_point_sign_idx(chart_wrap: dict[str, Any] | None, start_key: str) -> int | None:
    """profectionSummary.js:37 `profectionPointSignIdx`：起点所在座序号（0=白羊）；取不到 None。"""
    chart = (chart_wrap or {}).get("chart") if isinstance(chart_wrap, dict) else None
    if not isinstance(chart, dict):
        return None
    by_id: dict[str, dict[str, Any]] = {}
    for item in list(chart.get("objects") or []) + list(chart.get("angles") or []):
        if isinstance(item, dict) and item.get("id"):
            by_id[item["id"]] = item
    target = "Asc"
    if start_key == "mc":
        target = "MC"
    elif start_key == "moon":
        target = "Moon"
    elif start_key == "fortune":
        target = "Pars Fortuna"
    elif start_key == "sect":
        target = "Sun" if chart.get("isDiurnal") else "Moon"
    obj = by_id.get(target)
    if not obj:
        return None
    if obj.get("sign") in LIST_SIGNS:
        return LIST_SIGNS.index(obj["sign"])
    lon = obj.get("lon")
    if lon is not None:
        try:
            return int(math.floor(((float(lon) % 360) + 360) % 360 / 30)) % 12
        except (TypeError, ValueError):
            return None
    return None


def derive_profection(
    birth_jdn: float | None, target_jdn: float | None, grain: str, start_key: str, chart_wrap: dict[str, Any] | None
) -> dict[str, Any] | None:
    """profectionSummary.js:73 `deriveProfection`（年=365.2422 天、月=年/12、日=2.5 天/座）。"""
    start_idx = profection_point_sign_idx(chart_wrap, start_key)
    if start_idx is None or birth_jdn is None or target_jdn is None:
        return None
    days = target_jdn - birth_jdn
    if not days >= 0:
        days = 0.0
    year_days = 365.2422
    age = int(math.floor(days / year_days))
    year_sign = (start_idx + age) % 12
    year_house = (age % 12) + 1
    days_into_year = days - age * year_days
    month_days = year_days / 12.0
    months = max(0, min(11, int(math.floor(days_into_year / month_days))))
    month_sign = (year_sign + months) % 12
    days_into_month = days_into_year - months * month_days
    days_adv = max(0, min(11, int(math.floor(days_into_month / 2.5))))
    day_sign = (month_sign + days_adv) % 12
    sign_idx, house = year_sign, year_house
    if grain == "m":
        sign_idx, house = month_sign, ((month_sign - start_idx + 12) % 12) + 1
    elif grain == "d":
        sign_idx, house = day_sign, ((day_sign - start_idx + 12) % 12) + 1
    return {
        "ageYears": age,
        "startSignIdx": start_idx,
        "yearSignIdx": year_sign,
        "yearHouse": year_house,
        "signIdx": sign_idx,
        "house": house,
        "rulerId": _SIGN_DOMICILE.get(LIST_SIGNS[sign_idx % 12]),
        "monthsIntoYear": months,
    }


def profection_jdns(params: dict[str, Any]) -> tuple[float | None, float | None]:
    """profectionSummary.js:111 `profectionDateTimesFromParams` 的无头口径。

    出生 = date + time（**不挂时区** → DateTime 缺省 +08:00，与上游同）；目标 = datetime 挂 dirZone。
    """
    birth = None
    date = f"{params.get('date') or ''}".strip()
    if date:
        birth = js_datetime_jdn(f"{date} {params.get('time') or '12:00:00'}")
    target = None
    dt = f"{params.get('datetime') or ''}".strip()
    if dt:
        zone = params.get("dirZone") or "+08:00"
        target = js_datetime_jdn(dt, zone)
    return birth, target


def build_profection_summary_lines(
    chart_wrap: dict[str, Any] | None, params: dict[str, Any], grain: Any, start_key: Any
) -> list[str]:
    """profectionSummary.js:137 `buildProfectionSummaryLines`：算不出（缺起点/缺时刻）→ []。"""
    g = normalize_profection_grain(grain)
    s = normalize_profection_start(start_key)
    birth_jdn, target_jdn = profection_jdns(params)
    info = derive_profection(birth_jdn, target_jdn, g, s, chart_wrap)
    if not info:
        return []

    def sign_cn(idx: int) -> str:
        name = LIST_SIGNS[((idx % 12) + 12) % 12]
        return UPSTREAM_ASTRO_TXT_MSG.get(name) or name

    def planet_cn(pid: str | None) -> str:
        return (UPSTREAM_ASTRO_TXT_MSG.get(pid) or pid) if pid else "—"

    start_cn = PROFECTION_START_CN[s]
    month_text = f"　当年第 {info['monthsIntoYear'] + 1} 月" if g != "y" else ""
    lines = [
        f"{PROFECTION_GRAIN_CN[g]}小限（自{start_cn}）：{sign_cn(info['signIdx'])} · 第 {info['house']} 宫（自{start_cn}所在星座起数）",
        f"小限主星：{planet_cn(info['rulerId'])}",
        f"已满 {info['ageYears']} 岁{month_text}",
    ]
    if g != "y":
        lines.append(f"年级参照：{sign_cn(info['yearSignIdx'])} · 第 {info['yearHouse']} 宫（自{start_cn}所在星座起数）")
    return lines
