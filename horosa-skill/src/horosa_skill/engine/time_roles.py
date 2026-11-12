"""每个技法的「时间角色」——它要的那个时刻到底是谁的（v0.50.0）。

为什么要有这张表：`horosa_dispatch` 过去把同一份出生数据发给所有被选中的技法。「今天黄历」于是查的是出生那天，
「用奇门看这笔投资」起的是出生时刻的局，塔罗用出生时刻当抽牌种子——全部 ok、没有任何提示。技法入参里的
`date/time` 只是一个槽位，槽位里该放「出生」还是「起课此刻」还是「要推的那一天」，由技法本身决定，不由载荷里
恰好有什么决定。这张表把这个决定写在一处；`engine/dispatch_plan.py` 按角色拼载荷，闸门按角色问问题。

角色：
- `natal`        出生时刻（本命盘、命理、整生时间线）。
- `moment`       起课 / 所问 / 被查询的那个时刻，从 `context` 来；出生数据**永不**顶替。
- `natal+target` 出生 + 一个要推到的目标时刻（返照 / 推运 / 小限 …）；目标从 `context` 或问句里的明确年份来。
- `natal+moment` 出生 + 起课时刻（六壬行年：命主行年 + 占时）。
- `window`       择日搜索窗（startDate/endDate），不是出生盘。
- `year`         只要一个年份（节气年表、世俗入宫盘）。
- `two_party`    两个人各自的出生数据（合盘）。
- `lookup`       不吃时间（卦义、规则库、知识库、导出工具 …）。

新增技法必须在这里登记角色：`tests/test_time_roles.py` 会在缺登记、或登记的角色与入参模型对不上时变红。
"""
from __future__ import annotations

from horosa_skill.errors import bilingual

NATAL = "natal"
MOMENT = "moment"
NATAL_TARGET = "natal+target"
NATAL_MOMENT = "natal+moment"
WINDOW = "window"
YEAR = "year"
TWO_PARTY = "two_party"
LOOKUP = "lookup"

ROLES: tuple[str, ...] = (NATAL, MOMENT, NATAL_TARGET, NATAL_MOMENT, WINDOW, YEAR, TWO_PARTY, LOOKUP)

_BY_ROLE: dict[str, tuple[str, ...]] = {
    NATAL: (
        # 西占本命 / 派生盘
        "chart", "chart12", "chart13", "babylon", "draconic", "relocation", "hellen_chart", "guolao_chart",
        "germany", "harmonic", "acg", "india_chart", "india_rectify", "jieqi_birth", "suzhan",
        # 命理
        "ziwei_birth", "bazi_birth", "bazi_direct", "canping", "heluo", "yizhangjing", "zhengchuan",
        # 神数（生辰起数）
        "wangji", "wuzhao", "taixuan", "jingjue", "shenyishu", "shaozi", "tieban", "fendjing", "beiji",
        "nanji", "chunzi", "xianqin", "cetian", "qizhengkin",
        # 整生时间线（一次给出全程，不需要目标时刻）
        "agepoint", "distributions", "michon", "prenatalsyzygy", "balbillus", "yearsystem129",
        "triplicityrulers", "keypoints", "lunationphase", "pd", "pdchart", "zr", "firdaria", "decennials",
        "persiandirected",
    ),
    MOMENT: (
        "qimen", "taiyi", "jinkou", "sanshiunited", "sixyao", "liureng_gods", "xiaoliuren", "feigong",
        "xiaochengtu", "guice", "horary", "election", "qizhengelection", "geomancy", "lingqi", "tarot",
        "otherbu", "huangli", "tongshu", "nongli_time", "calendar_month",
    ),
    NATAL_TARGET: (
        "solarreturn", "lunarreturn", "solararc", "givenyear", "profection", "planetaryarc",
        "jaynesprog", "neroman", "bezzafigure", "jayprofection", "vedicprog", "prog",
        "planetaryages", "ephemeris", "returntimeline", "extrareturns",
    ),
    NATAL_MOMENT: ("liureng_runyear",),
    WINDOW: (
        "tianxing", "qimenzeri", "huanglizeri", "bazizeri", "taiyizeri", "ziweizeri", "liurengzeri",
        "sanshizeri", "qizhengzeri", "indiazeri",
    ),
    YEAR: ("mundane", "jieqi_year"),
    TWO_PARTY: ("relative",),
    LOOKUP: (
        "export_registry", "export_parse", "knowledge_registry", "knowledge_read", "xuanshi", "bazi_inverse",
        "astrodata", "ziwei_rules", "gua_desc", "gua_meiyi", "planet_cycles", "tongshefa",
    ),
}

TIME_ROLES: dict[str, str] = {}
for _role, _tools in _BY_ROLE.items():
    for _tool in _tools:
        if _tool in TIME_ROLES:  # pragma: no cover - 表写重了就在导入时炸，不留到运行时
            raise RuntimeError(bilingual(f"技法 {_tool} 的时间角色登记了两次：{TIME_ROLES[_tool]} / {_role}", f"time role declared twice for {_tool}: {TIME_ROLES[_tool]} / {_role}"))
        TIME_ROLES[_tool] = _role

# 目标时刻落在技法的哪个入参上（`natal+target` / `natal+moment` 必填本表）。
#   datetime    → `datetime`（"YYYY-MM-DD HH:MM:SS"）+ dirZone/dirLat/dirLon（目标地点，缺省=出生地）
#   targetDate  → `targetDate` + `targetTime`
#   asOf        → `asOf`（YYYY-MM-DD）
#   startDate   → `startDate`（区间起点，YYYY-MM-DD）
#   startYear / timelineStartYear → 起始年（整数）
#   guaDate     → `guaDate` + `guaTime` + `guaZone`
TARGET_STYLE: dict[str, str] = {
    "solarreturn": "datetime", "lunarreturn": "datetime", "solararc": "datetime", "givenyear": "datetime",
    "profection": "datetime", "planetaryarc": "datetime",
    "jaynesprog": "targetDate", "neroman": "targetDate", "bezzafigure": "targetDate",
    "jayprofection": "targetDate", "vedicprog": "targetDate", "prog": "targetDate",
    "planetaryages": "asOf",
    "ephemeris": "startDate",
    "returntimeline": "startYear",
    "extrareturns": "timelineStartYear",
    "liureng_runyear": "guaDate",
}

# 每种落点实际写哪些键（守卫用：这些键必须都是该技法入参模型的字段）。
TARGET_FIELDS: dict[str, tuple[str, ...]] = {
    "datetime": ("datetime", "dirZone", "dirLat", "dirLon"),
    "targetDate": ("targetDate", "targetTime"),
    "asOf": ("asOf",),
    "startDate": ("startDate",),
    "startYear": ("startYear",),
    "timelineStartYear": ("timelineStartYear",),
    "guaDate": ("guaDate", "guaTime", "guaZone"),
}

# `moment` 里只吃日期（或日期 + 时区）的历法查询：问句里写了明确日期就直接用，不必要求完整的时刻与地点。
CALENDAR_LOOKUPS: frozenset[str] = frozenset({"huangli", "tongshu", "calendar_month", "nongli_time"})


def time_role(tool_name: str) -> str | None:
    return TIME_ROLES.get(tool_name)


def target_fields(tool_name: str) -> tuple[str, ...]:
    return TARGET_FIELDS.get(TARGET_STYLE.get(tool_name, ""), ())
