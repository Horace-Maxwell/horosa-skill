"""推运族输入：返照 / 太阳弧 / 主限 / 小限 / 黄道释放 / 年龄点 / 各类推运 / 星历 / progextra 族 / 多重回归 / 129 年 / 波斯向运 / 法达 / 十年期。"""
from __future__ import annotations

from pydantic import Field

from horosa_skill.schemas.tools.base import BirthInput


class PredictiveInput(BirthInput):
    predictive: bool | None = False
    # pdchart 界限显示开关（service 读 params.showPdBounds；agent_guidance 一直在文档里写它，schema 此前未声明 → MCP 扁平面丢弃）。
    showPdBounds: int | bool | None = None


class ProfectionInput(PredictiveInput):
    # [Q-105] 小限页 G9 年/月/日小限 + 多起点（上游 utils/profectionSummary.js，挂载齿轮 techniqueMountSettings.js:1359-1362）。
    profGrain: str | None = Field(default=None, description="[小限摘要]粒度：y 年（缺省）| m 月 | d 日")
    profStart: str | None = Field(default=None, description="[小限摘要]起点：asc 上升（缺省）| sect 区分光 | fortune 福点 | moon | mc")


class ZodiacalReleaseInput(PredictiveInput):
    # 上游 AstroZR.js ZR_BASE_POINTS / AI_MODE_ITEMS（挂载齿轮 techniqueMountSettings.js:1277-1285）。
    basePoint: str | None = Field(
        default=None,
        description="推运基点：Pars Fortuna（缺省）/Pars Spirit/Pars Mercury…Pars Saturn/Asc/Desc/MC/IC/十二星座英文名",
    )
    aiMode: str | None = Field(default=None, description="输出层级：l1_all（缺省）| l2_in_l1 | l3_in_l2 | l4_in_l3")
    aiL1Idx: int | None = Field(default=None, description="钻取序号（0 起；aiL2Idx/aiL3Idx 同）")
    aiL2Idx: int | None = None
    aiL3Idx: int | None = None


class AgePointInput(BirthInput):
    # 年龄推进点 (Age Point / Huber): backend /predict/agepoint computes the whole age-point cycle from the natal
    # chart (no separate target time). Needs predictive on so the predict engine runs.
    # 上游 v3.13.0 四项口径（utils/agePointOptions.js；挂载齿轮 techniqueMountSettings.js:1496-1505，Java 白名单同名）。
    predictive: bool | None = True
    apMethod: str | None = Field(default=None, description="推进方式：koch Koch 宫·每宫 6 年（缺省）| equal5 等速·自上升每年 5°")
    apEvents: str | None = Field(default=None, description="事件：full 全部点 × 五种相位（缺省）| conj 只报合七星")
    apYear: str | None = Field(default=None, description="年长：tropical 回归年（缺省）| sidereal 恒星年")
    apMaxAge: int | None = Field(default=None, description="年限（岁）：72（缺省）| 100 | 120 | 144")


class DistributionsInput(BirthInput):
    # 界推运 (Distributions / 分配法): backend /predict/dist computes distributor (bound-lord) + partner periods
    # as the releaser moves through the bounds (界表随全局界系). Natal params only.
    # 上游 v3.13.0 四项口径（utils/distributionsOptions.js；挂载齿轮 techniqueMountSettings.js:1484-1493，Java 白名单同名）。
    predictive: bool | None = True
    distReleaser: str | None = Field(
        default=None,
        description="发放点：Asc 上升（缺省）| MC | Desc | IC | Sun…Pluto | North Node | Vertex | Pars Fortuna | Spirit | Syzygy",
    )
    distMethod: str | None = Field(default=None, description="时间算法：classical 上升时间（缺省）| exact 斜升差逐度 | qisma 每度 1 年")
    distYear: str | None = Field(default=None, description="年长：tropical 回归年（缺省）| egyptian 365 日 | julian 365.25 日")
    distYears: int | None = Field(default=None, description="年限：100（缺省）| 60 | 80 | 120 | 150")


_TARGET_DATE_DESC = "目标日期 YYYY-MM-DD（缺省=今天，上游同律）"
_MINOR_VARIANT_DESC = "小推运月长：synodic 朔望月/年（缺省）| sidereal 恒星月/年 | engine 引擎历史值"


class JaynesProgInput(BirthInput):
    # Jayne 赤纬推运 (v2.5.0): secondary progression to a target date, then declination parallels.
    predictive: bool | None = True
    targetDate: str | None = Field(default=None, description=_TARGET_DATE_DESC)
    targetTime: str | None = "12:00:00"
    orb: float | None = 1.0
    minorVariant: str | None = Field(default=None, description=_MINOR_VARIANT_DESC)


class VedicProgInput(BirthInput):
    # 恒星推运 Vedic (v2.5.0): progressions under the sidereal zodiac.
    predictive: bool | None = True
    targetDate: str | None = Field(default=None, description=_TARGET_DATE_DESC)
    targetTime: str | None = "12:00:00"
    orb: float | None = 1.5
    minorVariant: str | None = Field(default=None, description=_MINOR_VARIANT_DESC)


# ── 上游 v3.11 星运四键（[Q-106/T-10] 星历/回归轴/产前朔望 + [#80] 回归黄道二次推运）──
# date/time/zone/lat/lon 恒是**本命盘**；上游请求体（AstroExtraCommon.chartParams）tradition/predictive 恒 false。
class EphemerisInput(BirthInput):
    predictive: bool | None = False
    startDate: str | None = Field(default=None, description="区间起 YYYY-MM-DD（缺省今天）")
    endDate: str | None = Field(default=None, description="区间止（缺省今天+90天）")
    includeTransits: bool | None = Field(default=None, description="列行运触发（缺省 true）")
    eclipseTimeMode: str | None = Field(default=None, description="食相时刻 max（缺省）|syzygy")


class ReturnTimelineInput(BirthInput):
    predictive: bool | None = False
    startYear: int | None = Field(default=None, description="起始年（缺省今年）")
    count: int | None = Field(default=None, description="年数 1–40（缺省 12）")


class PrenatalSyzygyInput(BirthInput):
    predictive: bool | None = False


class ProgInput(BirthInput):
    predictive: bool | None = False
    targetDate: str | None = Field(default=None, description="目标日 YYYY-MM-DD（缺省今天）")
    targetTime: str | None = Field(default=None, description="目标时刻（缺省 12:00:00）")
    minorVariant: str | None = Field(default=None, description="小推运月长 synodic|sidereal|engine")


class PlanetaryArcInput(BirthInput):
    # 行星弧 (v2.5.0): directs the whole chart by the secondary-progressed arc of arcSource (default Moon).
    predictive: bool | None = True
    datetime: str | None = Field(default=None, description="目标时刻（缺省=明天此刻，上游同律）")
    asporb: float | None = 1.0
    arcSource: str | None = Field(default="Moon", description="弧源：Moon（缺省）/Sun/Mercury/Venus/Mars/Jupiter/Saturn")


class PlanetaryAgesInput(BirthInput):
    # 行星年龄 (v2.5.0): Ptolemy seven ages — reads the natal chart, marks the band of asOf (default: none).
    predictive: bool | None = False
    asOf: str | None = None


class BalbillusInput(BirthInput):
    # Balbillus 129年系统 (v2.5.0): 旺距削减主限 — reads the natal chart, splits life into recursive sub-periods.
    # 可调项 = 上游挂载齿轮（techniqueMountSettings.js:1473-1481，v3.13.0 起四项）→ vendored builder opts。
    predictive: bool | None = False
    startPlanet: str | None = Field(default=None, description="起始星：Sun（缺省）/Moon/Mercury/Venus/Mars/Jupiter/Saturn")
    yearType: str | None = Field(
        default=None,
        description="年制：solar 回归年（缺省）| sidereal 恒星年 | hellenistic 360 日 | abumashar | mashaallah | bija",
    )
    mode: str | None = Field(default=None, description="距离口径：nearest 最近角距（缺省）| forward 顺黄道距")
    subRule: str | None = Field(default=None, description="子限铺法：once 一轮不填满（缺省）| cycle 循环到父期末 | fill 末段填满")


class TriplicityRulersInput(BirthInput):
    # 三分主星推运 (星阙 v2.6.x): 区间光体所在座的三颗三分主星按昼夜换序，划分人生各阶段。纯前端切分本命盘。
    # 可调项 = 上游挂载齿轮（techniqueMountSettings.js:1237-1248）。
    predictive: bool | None = False
    system: str | None = Field(default=None, description="三分体系：Dorothean（缺省随本盘 triplicity）| Ptolemaic | PtolemaicWaterVariant")
    division: str | None = Field(default=None, description="划分法：thirds 三分（缺省）| halves 两分")
    lifespan: float | None = Field(default=None, description="寿命基准/年龄上限 30–120（缺省 75）")


class KeypointsInput(BirthInput):
    # 数字相位推运 (星阙 v2.6.x): 七星小年数 + 自释放点起第 k 座挂钩，凡年龄为 k 或小年倍数即激活。纯前端切分本命盘。
    predictive: bool | None = False
    mode: str | None = Field(default=None, description="释放点：soul 身·月亮起（缺省）| body 命·上升起")


class LunationPhaseInput(BirthInput):
    # 月相推运 (星阙 v2.6.x): 由本命日月黄经差 + 次限推进率(约12.19°/年)求推运八相时间轴。纯前端切分本命盘。
    predictive: bool | None = False


class ExtraReturnsInput(BirthInput):
    # 多重回归 (星阙 v2.6.x): 土/木/月交三体返照——逐体走后端 /astroextra/planetreturn 取最近数回返照日期。
    predictive: bool | None = False
    # 日月返照年表（v0.33.0 批 I-3，/astroextra/returns）：逐年太阳返照/首月返精确时刻 + 返照上升。
    timelineStartYear: int | None = Field(
        default=None,
        description="日月返照年表起始年（给了本参数或 timelineCount 才加产 [日月返照年表] 段；缺省取出生年）",
    )
    timelineCount: int | None = Field(default=None, description="年表年数（缺省 10，上限 40）")


class YearSystem129Input(BirthInput):
    # 129年系统: seven planets each rule their 小年 (土30木12火15日19金8水20月25 = 129y). 上游 v3.13.0 起由前端
    # utils/yearSystem129.js 计算（vendored，horosa-core-js progextra）；四项口径 = 挂载齿轮 YEARSYSTEM129_FIELDS
    # （techniqueMountSettings.js:1509-1518，键带 ys129 前缀 = 页面保存键）。
    predictive: bool | None = False
    ys129StartPlanet: str | None = Field(
        default=None, description="起始星：Sun（缺省）| sect 区分光体（昼日夜月）| Moon/Mercury/Venus/Mars/Jupiter/Saturn",
    )
    ys129Order: str | None = Field(default=None, description="次序：zodiacal 本命黄经递增（缺省）| chaldean 迦勒底序")
    ys129YearType: str | None = Field(
        default=None,
        description="年制：solar 回归年（缺省）| sidereal | hellenistic 360 日 | abumashar | mashaallah | bija",
    )
    ys129SubRule: str | None = Field(
        default=None, description="子限：days 日数法（缺省，不填满主限）| proportional 比例法 | equal 七等分",
    )


class PersianDirectedInput(BirthInput):
    # 波斯向运 (v2.5.0): symbolic 1°/year direction — every planet/point advances +1°/年, natal cusps fixed.
    predictive: bool | None = False
    # 指定日期向运盘（v0.33.0 批 I-2，/predict/persianchart）：给 datetime 时后端整铸该日向运盘
    # （27 directed 点 + 33 directed lots + 向运→本命相位命中），加产 [指定日期向运盘] 段。
    datetime: str | None = Field(
        default=None,
        description=(
            "目标日期 YYYY-MM-DD[ HH:mm:ss]：铸该日的波斯向运盘（directed 点位 + 向运→本命相位命中），"
            "加产 [指定日期向运盘] 段。缺省只出 1°/年应期表。Cast the directed chart at this date."
        ),
    )
    rateKey: str | None = Field(default=None, description="速率：persian 1°/年（缺省）| prophected 30°/年 | naibod 59′08″/年；驱动应期表与指定日期盘")
    direction: str | None = Field(default=None, description="方向：direct（缺省）| converse 逆向；驱动应期表与指定日期盘")
    maxYears: float | None = Field(default=None, description="应期年数（缺省 90；上游五档 50/90/120/150/200）")
    nodeRetrograde: bool | None = Field(default=None, description="交点按逆行处理（缺省 false，上游同默认）")


class FirdariaInput(BirthInput):
    predictive: bool | None = True


class DecennialsInput(BirthInput):
    predictive: bool | None = True
    startMode: str | None = "sect_light"
    orderType: str | None = "zodiacal"
    dayMethod: str | None = "valens"
    calendarType: str | None = "calendar_360"
    aiMode: str | None = "l1_all"
    aiL1Idx: int | None = 0
    aiL2Idx: int | None = 0
    aiL3Idx: int | None = 0
