"""恒星黄道 / 月宿 / 印占 共享常量（星阙 v2.6.4 平价）。

下游 skill 把这些表平移自上游 星阙 `india/india_chart_kernel.py`（47 ayanāṃśa + 24 分宫制）
与 `nakshatra.py`（27 宿宿主），用于 ① AI 快照显示岁差名/月宿、② agent_guidance 枚举合法值。
纯数据，无外部依赖；运行时计算仍由打包 Python 后端完成，这里只做展示/校验。
"""

from __future__ import annotations

# ─── 47 恒星黄道 ayanāṃśa：key → 显示名（与 星阙 INDIA_AYANAMSA_MODES 一致）────────────
SIDEREAL_AYANAMSA_LABELS: dict[str, str] = {
    "lahiri": "Lahiri / Chitrapaksha",
    "raman": "Raman",
    "krishnamurti": "Krishnamurti / KP",
    "krishnamurti_vp291": "Krishnamurti VP291",
    "yukteshwar": "Yukteshwar",
    "true_citra": "True Citra",
    "true_revati": "True Revati",
    "fagan_bradley": "Fagan/Bradley",
    "lahiri_icrc": "Lahiri ICRC (官定2022)",
    "lahiri_1940": "Lahiri 1940",
    "lahiri_vp285": "Lahiri VP285",
    "deluce": "De Luce",
    "jn_bhasin": "J.N. Bhasin",
    "ushashashi": "Usha/Shashi",
    "true_pushya": "True Pushya (PVRN Rao)",
    "true_mula": "True Mula (Chandra Hari)",
    "true_sheoran": "Vedic / Sheoran",
    "ss_citra": "SS Citra",
    "ss_revati": "SS Revati",
    "suryasiddhanta": "Surya Siddhanta",
    "suryasiddhanta_msun": "Surya Siddhanta (mean Sun)",
    "aryabhata": "Aryabhata",
    "aryabhata_msun": "Aryabhata (mean Sun)",
    "aryabhata_522": "Aryabhata 522",
    "djwhal_khul": "Djwhal Khul",
    "valens_moon": "Vettius Valens",
    "galcent_0sag": "Galactic Center 0°Sag",
    "galcent_rgilbrand": "Galactic Center (Gil Brand)",
    "galcent_mula_wilhelm": "Galactic Center/Mula (Wilhelm)",
    "galcent_cochrane": "Galactic Center (Cochrane)",
    "galequ_iau1958": "Galactic Equator (IAU1958)",
    "galequ_true": "Galactic Equator (true)",
    "galequ_mula": "Galactic Equator (mid-Mula)",
    "galequ_fiorenza": "Galactic Equator (Fiorenza)",
    "galalign_mardyks": "Skydram (Mardyks)",
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

# ─── 24 印占分宫制：code(int) → 显示名（与 星阙 INDIA_HOUSE_SYSTEMS 一致）────────────────
INDIA_HOUSE_SYSTEM_LABELS: dict[int, str] = {
    0: "Whole Sign / Rashi",
    2: "Regiomontanus",
    3: "KP / Placidus",
    4: "Koch",
    5: "Equal / Lagna Bhava",
    6: "Vehlow 等宫·命居宫中",
    7: "Sripati",
    8: "Alcabitus",
    9: "Porphyry 波菲",
    10: "Campanus",
    11: "Morinus",
    12: "Meridian / Axial",
    13: "Polich-Page / Topocentric",
    14: "Equal MC",
    15: "Azimuthal / Horizon",
    16: "Carter Poli-Equatorial",
    17: "Sunshine",
    18: "Sunshine Alt",
    19: "Krusinski",
    20: "Pullen SD",
    21: "Pullen SR",
    22: "APC Houses",
    23: "Savard-A",
    24: "Equal 2",
}

# ─── 27 宿宿主：英文行星名 → 中文（与 星阙 AstroConst.NAK_LORD_CN 一致）────────────────
NAK_LORD_CN: dict[str, str] = {
    "Ketu": "计都",
    "Venus": "金星",
    "Sun": "太阳",
    "Moon": "月亮",
    "Mars": "火星",
    "Rahu": "罗睺",
    "Jupiter": "木星",
    "Saturn": "土星",
    "Mercury": "水星",
}


def sidereal_ayanamsa_label(key: Any) -> str:
    """key(如 'lahiri') → 显示名；未知/缺省回退 Lahiri。"""
    if not key:
        return SIDEREAL_AYANAMSA_LABELS["lahiri"]
    norm = str(key).strip().lower()
    return SIDEREAL_AYANAMSA_LABELS.get(norm, str(key))


def nakshatra_lord_cn(lord: Any) -> str:
    """宿主行星英文 → 中文；未知原样返回。"""
    if not lord:
        return ""
    return NAK_LORD_CN.get(str(lord), str(lord))


__all__ = [
    "SIDEREAL_AYANAMSA_LABELS",
    "INDIA_HOUSE_SYSTEM_LABELS",
    "NAK_LORD_CN",
    "sidereal_ayanamsa_label",
    "nakshatra_lord_cn",
]
