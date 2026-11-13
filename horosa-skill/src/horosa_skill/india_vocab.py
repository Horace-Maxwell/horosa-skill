"""印占新表的入参词表（上游 v3.14.0）：穿界时刻所选三项、合盘八重合的男方。

值域与缺省照上游 `utils/indiaExtraTables.js`（vendored 于 horosa-core-js/src/vendor/utils/）：
`TRANSIT_PLANET_OPTIONS` / `TRANSIT_KIND_OPTIONS` / `TRANSIT_DAY_OPTIONS` / `TRANSIT_DEFAULT_SELECTION`，
`tests/test_sync314_india_vocab.py` 逐值对 vendored 表（经 JS 工具 `india_tables` 的 transit_vocab 动作取，不读源码文本）。

为什么在入口就拦：后端 `astrostudy/india/transit_events.py` 对认不出的星回落成七星（`_planets`）、认不出的事件回落成入星座
（`_kinds`）、天数夹到 1–366（`_days`），而 [穿界时刻] 的段头照抄请求里的原值 —— 写错一个词，表与段头就说两件事。
"""

from __future__ import annotations

from horosa_skill.input_fields import Vocabulary

# 上游 TRANSIT_DEFAULT_SELECTION（七星 · 入星座 · 90 天）。键名是 skill 的入参名（= 上游挂载齿轮名 indiaTransit*）。
INDIA_TRANSIT_DEFAULTS: dict[str, object] = {"indiaTransitPlanet": "all", "indiaTransitKind": "sign", "indiaTransitDays": 90}

# skill 入参名 → 后端 /astroextra/transitevents 请求键（上游 requestedTransitSelection，IndiaChart.js:1362-1371）。
INDIA_TRANSIT_REQUEST_KEYS: dict[str, str] = {
    "indiaTransitPlanet": "transitPlanet", "indiaTransitKind": "transitKind", "indiaTransitDays": "transitDays",
}

INDIA_TRANSIT_VOCABULARIES: dict[str, Vocabulary] = {
    "indiaTransitPlanet": Vocabulary(
        "indiaTransitPlanet",
        {
            "all": ("七星", "全部", "七曜", "seven"), "Sun": ("太阳", "日"), "Moon": ("月亮", "月", "太阴"), "Mercury": ("水星", "水"),
            "Venus": ("金星", "金"), "Mars": ("火星", "火"), "Jupiter": ("木星", "木"), "Saturn": ("土星", "土"),
        },
        labels={"all": "七星（缺省）", "Sun": "太阳", "Moon": "月亮", "Mercury": "水星", "Venus": "金星", "Mars": "火星",
                "Jupiter": "木星", "Saturn": "土星"},
    ),
    "indiaTransitKind": Vocabulary(
        "indiaTransitKind",
        {
            "sign": ("入星座", "星座", "rasi", "rashi"), "nakshatra": ("入星宿", "星宿", "月宿", "宿"),
            "pada": ("入足", "足"), "kakshya": ("入 Kakshya", "入kakshya"),
        },
        labels={"sign": "入星座（缺省）", "nakshatra": "入星宿", "pada": "入足", "kakshya": "入 Kakshya"},
    ),
    "indiaTransitDays": Vocabulary(
        "indiaTransitDays",
        {30: ("30", "30天"), 90: ("90", "90天"), 180: ("180", "180天"), 366: ("366", "一年", "1年", "366天")},
        labels={30: "30 天", 90: "90 天（缺省）", 180: "180 天", 366: "一年"},
        numeric=True,
    ),
}

# 八重合男方：上游 AstroAshtakoota.MALE_SIDES（inner = 星盘 A / outer = 星盘 B）。不给 = 按两人的 gender（上游 maleSideOf）。
ASHTAKOOTA_MALE_SIDE = Vocabulary(
    "ashtakootaMaleSide",
    {"inner": ("星盘A", "星盘 A", "a", "甲方", "第一人"), "outer": ("星盘B", "星盘 B", "b", "乙方", "第二人")},
    labels={"inner": "星盘 A（inner）", "outer": "星盘 B（outer）"},
)
