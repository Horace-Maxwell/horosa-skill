"""西洋占星族输入：本命 / 印度 / 合盘 / 七政四余 / 占星地图 / 名人库 / 汉堡 / 泛音 / 巴比伦 / 龙头 / 迁移 / 世俗盘 / 骰子。"""
from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import Field

from horosa_skill.schemas.tools.base import (
    _LIFESPAN_METHOD_DESC,
    BirthInput,
    FlexibleModel,
    _ChartDayBoundaryKnobs,
)


class AstroChartInput(BirthInput, _ChartDayBoundaryKnobs):
    """本命/盘面族（chart/chart13/chart12/hellen_chart）：在 BirthInput 上加 [寿命格局] 取主法。"""

    lifespanMethod: str | None = Field(default=None, description=_LIFESPAN_METHOD_DESC)


class IndiaChartInput(BirthInput):
    hsys: int | None = 0  # 印占宫制走 indiaHsys；本键只作 indiaHsys 缺席时的回退 = INDIA_HOUSE_SYSTEM_DEFAULT 0（整宫/Rashi）
    # 印度占星 (星阙 v2.6.4)：分宫制 4→全 24 制(indiaHsys 0–24)、黄道岁差 6→全 47(indiaAyanamsa)。
    # 印占恒星黄道引擎 pyswisseph，与西洋 siderealAyanamsa 共用 47 套岁差键。缺省 hsys=0(整宫)/lahiri。
    # 后端 webindiasrv 读 indiaHsys/indiaAyanamsa（亦兼容 hsys/ayanamsa/siderealMode）。
    indiaHsys: Any | None = None
    indiaAyanamsa: Any | None = None
    # 印占大扩容（星阙 v3.6.0）：KP 完整化 / SBC / 七新大运体系 / Ayurdaya / 纳迪 / Tajika / Prashna。
    # 后端 webindiasrv 已读这些键（本仓经 FlexibleModel extra 早已能透传），此处声明只为让 agent 看得见。
    dashaVariants: Any | None = Field(default=None, description="大运流派 21 开关（Vimśottarī/Kālachakra/Yogini… 的分派选项）。")
    dashaYearLength: Any | None = Field(default=None, description="大运年长档：五档（360日/365.25日/恒星年…）。")
    vargaVariant: Any | None = Field(default=None, description="分割盘(varga)流派：Parāśara / Jaimini 等口径。")
    karakaScheme: Any | None = Field(default=None, description="Chara Kāraka 取法（7/8 星制）。")
    yuddhaCriterion: Any | None = Field(default=None, description="行星战(graha yuddha)胜负判据。")
    # 上游 v3.11.0 挂载齿轮（techniqueMountSettings.js:1030-1039）：
    indiaExtraVargas: Any | None = Field(
        default=None,
        description="附加分盘（简表，最多 4 张）：如 [9, 7] 或 '9,7'。可选 2/3/4/7/9/10/12/16/20/24/27/30/40/45/60；每张只出宫头 + 星曜落宫 + 行星，进 [附加分盘] 段。缺省=只挂主盘。",
    )
    indiaTripataki: bool | None = Field(
        default=None,
        description="Tripataki 三旗盘（opt-in，后端多建 12 盘约 0.3–0.8s）：true 时产 [Tripataki 三旗盘逐月净分] 段（月心/土心逐月净分）。",
    )
    # 上游印度盘页 / 挂载齿轮（techniqueMountSettings.js:1000-1051 → IndiaChart.fieldsToParams :79-143）的其余口径：
    # 照常声明（校验 + MCP 扁平面收顶层键），不进 tools/list 广告层（预算）；值域词表见 agent_guidance。
    ADVERTISE_HIDDEN: ClassVar[frozenset[str]] = frozenset({
        "dashaSystem", "indiaSchool", "dashaSeed", "sthiraStart", "transitDate", "tajakaYear", "annualChartType",
        "varshaLat", "varshaLon", "prashnaTime", "prashnaNumber", "prashnaMatter", "prashnaSchools",
        "prashnaCuspMode", "prashnaPrimaryHouse",
    })
    dashaSystem: str | None = Field(default=None, description="大运体系（15 档，缺省 vimshottari）：决定 [大运Dasha] 段所列体系。")
    indiaSchool: str | None = Field(default=None, description="流派：parashari（缺省）/jaimini/tajika/kp/nadi/western_sidereal；未给岁差/宫制时按派补预设。")
    dashaSeed: str | None = Field(default=None, description="大运起点：moon（缺省）/七政/节点/上升/特殊上升/副星。")
    sthiraStart: str | None = Field(default=None, description="Sthira 座运起座：lagna（缺省）| brahma。")
    transitDate: str | None = Field(default=None, description="过运日期 YYYY/MM/DD（缺省今日）。")
    tajakaYear: int | None = Field(default=None, description="年度盘年份（缺省当前年）。")
    annualChartType: str | None = Field(default=None, description="年盘口径：varsha（缺省）| tithi。")
    varshaLat: Any | None = Field(default=None, description="年盘异地纬度（须与 varshaLon 同给）。")
    varshaLon: Any | None = Field(default=None, description="年盘异地经度（须与 varshaLat 同给）。")
    prashnaTime: str | None = Field(default=None, description="问事起卦时刻 YYYY/MM/DD HH:mm:ss（给了才产 [问事 Praśna]）。")
    prashnaNumber: int | None = Field(default=None, description="KP 问时数 1–249（缺省 1）。")
    prashnaMatter: str | None = Field(default=None, description="所问事项（career/marriage/…）。")
    prashnaSchools: Any | None = Field(default=None, description="问事流派（缺省 ['kp']）。")
    prashnaCuspMode: str | None = Field(default=None, description="问事宫始定法（缺省 asc_driven_placidus）。")
    prashnaPrimaryHouse: int | None = Field(default=None, description="问事主宫 1–12（缺省按事项）。")


class PlanetCyclesInput(FlexibleModel):
    """行星周期：任意两星的合/冲时间轴（世运周期研究的骨架数据；无出生盘概念）。"""

    startYear: int | None = Field(default=None, description="起始年（缺省 1900）")
    endYear: int | None = Field(default=None, description="结束年（缺省 2100；区间上限 3400 年）")
    p1: str | None = Field(default=None, description="星一（英文名，缺省 Jupiter）：Jupiter/Saturn/Uranus/Neptune/Pluto/Mars…")
    p2: str | None = Field(default=None, description="星二（英文名，缺省 Saturn）")
    aspect: float | None = Field(default=None, description="相位角：0=合（缺省）/ 180=冲（任意角度亦可）")
    center: str | None = Field(default=None, description="坐标系：geo=地心（缺省）| helio=日心 | topo=站心")
    response_view: str | None = None


class IndiaRectifyInput(BirthInput):
    """印度（KP 法）出生时间校正：以给定时刻为锚，在 ±半窗内扫描候选并按判据打分排序。

    date/time 是**待校正的出生时刻锚点**；判据 = RP（Ruling Planets 命中）/ Pranapada /
    边界（gandanta 甘丹塔预警）+ 可选事件评分（rectifyEvents 录入后才参评）。
    输出证据与排序，是否采用由用户决定（上游免责声明原样带回）。
    """
    hsys: int | None = 0  # 同 IndiaChartInput：印占家族整宫缺省

    rectifyWindowMinutes: float | None = Field(default=None, description="扫描半窗（分钟），缺省 30，上限 240（锚点前后各半窗）")
    rectifyStepSeconds: int | None = Field(default=None, description="扫描步长（秒），缺省 60，上限 600；过粗会整段跳过 KP 子主（响应带步长诊断）")
    rectifyTopK: int | None = Field(default=None, description="返回候选榜条数，缺省 3，上限 10")
    rectifyRpSource: str | None = Field(default=None, description="RP 取法：anchor（缺省，按原始钟表时刻取 RP，无自指）|candidate（字面读法，自动消解自指）")
    rectifyEvents: list[dict[str, Any]] | None = Field(
        default=None,
        description="人生事件列表（可选）：录入后事件评分才参评（criteriaActive 会如实回显参评判据）。",
    )
    indiaHsys: Any | None = Field(default=None, description="印占分宫制 0–24（缺省 0=整宫）")
    indiaAyanamsa: Any | None = Field(default=None, description="印占岁差键（缺省 lahiri，47 套同西洋 siderealAyanamsa）")
    tripataki: Any | None = Field(default=None, description="Tripatāki 三旗盘（opt-in，宿距三旗）。")
    prashnaTime: Any | None = Field(default=None, description="问事(Praśna)盘时刻；不传则用主盘时刻。")
    prashnaSchools: Any | None = Field(default=None, description="问事三派选择。")
    prashnaMatter: Any | None = Field(default=None, description="问事事项/所问之题。")
    prashnaNumber: Any | None = Field(default=None, description="问事数（ārūḍha 起数法用）。")
    prashnaCuspMode: Any | None = Field(default=None, description="问事盘宫头取法。")
    prashnaPrimaryHouse: Any | None = Field(default=None, description="问事主事宫指定。")
    tajakaYear: Any | None = Field(default=None, description="Tājika 年盘的目标年份。")
    annualChartType: Any | None = Field(default=None, description="年盘类型（阴历年盘 / 太阳返照年盘等）。")
    varshaLat: Any | None = Field(default=None, description="年盘地点纬度（不传沿用本命地）。")
    varshaLon: Any | None = Field(default=None, description="年盘地点经度（不传沿用本命地）。")


class RelativePartyInput(FlexibleModel):
    date: str
    time: str
    zone: str
    lat: str
    lon: str
    ad: int | None = 1
    name: str | None = None


class RelativeInput(FlexibleModel):
    inner: RelativePartyInput
    outer: RelativePartyInput
    # 无头挂载 aiAnalysisContext.js:1228 `recordA.hsys ?? 1`（页面 AstroRelative.js:534 硬钉 0；缺省冲突跟无头路径）。
    hsys: int | None = 1
    zodiacal: int | None = 0
    siderealAyanamsa: Any | None = None
    relative: int | None = 0


class GuoLaoInput(BirthInput):
    hsys: int | None = 0  # 上游 GuoLaoChartMain.js:2345 genParams 恒 hsys 0（七政按地支宫域，不随 DefaultHouseSystem）
    # 七政起盘口径长尾键：照常声明（校验 + MCP 扁平面收顶层），不进 tools/list 广告层（词表见 agent_guidance）。
    ADVERTISE_HIDDEN: ClassVar[frozenset[str]] = frozenset({
        "guolaoNodeMode", "guolaoTrueSolarTime", "guolaoNodeType", "guolaoLilithType",
        "guolaoAyanamsa", "guolaoTuibianMethod", "guolaoGufaPrecess", "guolaoEqTropicalAnchor",
        "guolaoLimitYearBoundary",
    })
    # 宿度制（上游 GuoLaoChartStyle.js:19 缺省 0 荀爽距星——v3.13.0 由 2 改；值域 guolaoData.SU28_MODE_LABEL 0–8）。BirthInput 那个是 bool
    # （宿占用），这里放宽成 int —— 2–8 此前被 pydantic 拒；旧 true/false 照后端 parseSu28Mode 解释为 1/0。
    doubingSu28: int | bool | None = Field(default=None, description="宿度制 0–8（缺省 0 荀爽距星；2 回归今宿；4 恒星制；全表见 guidance）。")
    # 七政四余（v0.36.0 C1）：Java /qizheng/moira 规则层入参 + 流年盘时刻。缺省与上游 UI 默认一致。
    guolaoLifeMode: str | None = Field(default=None, description="命度法：asc 上升（缺省）| yumao 日出 | gumao 遇卯 | cotrans 赤黄 | 子–亥自定。")
    guolaoBodyMode: str | None = Field(default=None, description="身宫法：taiyin（太阴落宫，默认）| youjin（逢酉·琴堂）| 指定地支。")
    moiraTransitDate: str | None = Field(default=None, description="流年盘日期 YYYY-MM-DD（[流年流曜] 段的流年时刻；缺省=今天）。")
    moiraTransitTime: str | None = Field(default=None, description="流年盘时间 HH:mm:ss（缺省 12:00:00）。")
    moiraRules: bool | None = Field(default=None, description="false=跳过 /qizheng/moira（不产 [虚实]/[本命化曜]/[流年流曜]，省一次流年铸盘）。")
    # 显示层口径（上游 v3.11.0 挂载齿轮 techniqueMountSettings.js:1159-1175；缺省 = 上游全局缺省
    # GuoLaoChartStyle.GUOLAO_DEFAULT_DISPLAY：gong / 古度限度法 / tong10 / 9）。四键逐字打印进快照并改段结构。
    guolaoLifeMasterMode: str | None = Field(default=None, description="命主取法：gong=宫主（缺省）| du=度主 | dudegrade=贬宫主专度主（果老）。改 [三主与化曜] 的命主与难仇恩用「度」行。")
    guolaoMinorLimitType: str | None = Field(default=None, description="行运法：''=古度限度法（缺省）| minor=小限 | month=月限 | tong=童限 | dongwei=洞微大限。改 [大限] 所附行运法结构与 [限法实算] 的实算行。")
    guolaoTongxianBase: str | None = Field(default=None, description="童限基数（行运法=tong 时生效）：tong10=通行十年（缺省）| gu9=古九岁 | xu11=虚十一。")
    guolaoLimitChildBase: int | None = Field(default=None, description="定童限：9=九年起（缺省）| 10=十年起。改 [大限] 首限年数与各限起讫岁、[限法实算] 的童限/限度。")
    # 上游页面显示偏好 horosaGuolaoDisplay.limitYearBoundary（GuoLaoInput.js:850；GuoLaoChartStyle.GUOLAO_LIMIT_YEAR_BOUNDARIES），
    # 无头复算读同一份全局偏好（_buildGuolaoSnapshotTextV2Core:2058 getStoredGuolaoDisplay）。
    guolaoLimitYearBoundary: str | None = Field(default=None, description="大限年界：gregorian 公历元旦（缺省，Moira）| lichun 立春 | dongzhi 冬至（本地节气表精算）。改 [大限] 首限起点与各限起讫年（立春前生人岁次上一年、冬至后生人下一年）。")
    # 起盘口径（上游页面左栏 / 挂载齿轮 techniqueMountSettings.js:1123-1181；缺省 = GuoLaoChartStyle.js getStored* 缺省）。
    guolaoNodeMode: str | None = Field(default=None, description="罗计命名：northKetuSouthRahu 北计南罗（缺省）| northRahuSouthKetu 北罗南计（整盘换位）。")
    guolaoTrueSolarTime: str | None = Field(default=None, description="报时星太阳时：true 真太阳时（缺省）| mean 平太阳时 | off 钟表时。")
    guolaoNodeType: str | None = Field(default=None, description="罗计取法：mean 平交点（缺省）| true 真交点。")
    guolaoLilithType: str | None = Field(default=None, description="月孛取法：mean 平远地点（缺省）| true 真远地点。")
    guolaoAyanamsa: str | None = Field(default=None, description="恒星制岁差（仅宿度制 4）：47 制键，缺省郑氏。")
    guolaoTuibianMethod: str | None = Field(default=None, description="推变黄道术（仅宿度制 6）：jiyuan 纪元（缺省）| jintui 进退 | huiyuan 会圆。")
    guolaoGufaPrecess: int | bool | None = Field(default=None, description="古宿随岁差（仅宿度制 6）：0 钉死元时（缺省）| 1 东移。")
    guolaoEqTropicalAnchor: str | None = Field(default=None, description="赤道回归锚点（仅宿度制 7/8）：dongzhi 牛前冬至（缺省）| chunfen 春分。")


class ACGInput(BirthInput):
    # 占星地图（AstroCartoGraphy）：本命时刻的行星地理投影线（MC/IC 恒定经度、ASC/DESC 曲线、
    # 天顶点、偕升纬度带、线交点）。口径开关：mode=mundo 真黄纬（Jim Lewis 原版，默认）/zodiac
    # 黄道度；lsMode=great 大圆（默认）/rhumb 等角航线；geodetic 地理等价流派 sepharial（默认）
    # /mcrae/johndro，变体 longitude（默认）/ra。地图渲染属 UI，无头输出为结构化线表。
    mode: str | None = "mundo"
    lsMode: str | None = "great"
    geodetic: str | None = "sepharial"
    geodeticVar: str | None = "longitude"
    # 落点分析（v0.33.0 批 I-4，/location/acgpoint）：给 clickLat/clickLon 时加产 [落点分析] 段。
    clickLat: float | None = Field(default=None, description="落点纬度（十进制；给了 clickLat+clickLon 才产 [落点分析] 段：该地命中线/重置四角/敏感点）")
    clickLon: float | None = Field(default=None, description="落点经度（十进制，西经为负）")
    pointOrb: float | None = Field(default=None, description="落点命中容许度（度，缺省 2.0）")
    pointHsys: str | None = Field(default=None, description="落点/宫尖线宫制（缺省 placidus）")
    # 事件时刻（/location/acgevent）：给 eventKind 时加产 [事件时刻] 段（CCG 事件线时刻）。
    eventKind: str | None = Field(
        default=None,
        description=(
            "世运事件类型：solar_eclipse|lunar_eclipse|newmoon|fullmoon|aries_ingress|cancer_ingress|"
            "libra_ingress|capricorn_ingress（给了才产 [事件时刻] 段，返回 UTC 时刻）"
        ),
    )
    eventDirection: str | None = Field(default=None, description="事件查找方向：next（缺省）|prev")
    eventFromDate: str | None = Field(default=None, description="事件查找起点日期 YYYY-MM-DD（缺省取盘面日期）")
    # 上游 AstroAcg.genParams（AstroAcg.js:348-372）的其余引擎口径 + CCG + 关系盘 + 快照图层：照常声明（校验 + MCP
    # 扁平面收顶层键），不进 tools/list 广告层（预算）；值域见 agent_guidance，后端认不出的值经 meta 回显比对后告警。
    ADVERTISE_HIDDEN: ClassVar[frozenset[str]] = frozenset({
        "geodeticZero", "cuspLines", "coord", "posType", "horizon", "nodeType", "lilithType", "draconic", "harmonic",
        "vibration", "midpointMode", "lotsCustom", "asteroids", "ayanamsa", "stars", "ccgDate", "ccgTime", "ccgMix",
        "relMode", "relDate", "relTime", "relZone", "relLat", "relLon", "paranMode", "showLS", "showGeodetic",
        "showStarParans",
    })
    geodeticZero: float | None = Field(default=None, description="地理等价 0°♈ 子午线（东经度；缺省流派默认）。")
    cuspLines: bool | None = Field(default=None, description="十二宫尖线（opt-in，按 pointHsys 宫制）。")
    coord: str | None = Field(default=None, description="坐标系：geo（缺省）| helio | topo。")
    posType: str | None = Field(default=None, description="位置类型：apparent（缺省）| true | j2000。")
    horizon: str | None = Field(default=None, description="地平：geometric（缺省）| apparent（折射）。")
    nodeType: str | None = Field(default=None, description="交点：mean（缺省）| true。")
    lilithType: str | None = Field(default=None, description="Lilith：mean（缺省）| true | intp | body。")
    draconic: str | None = Field(default=None, description="龙黄道：off（缺省）| mean | true。")
    harmonic: int | None = Field(default=None, description="谐波 H（1=关，缺省）。")
    vibration: bool | None = Field(default=None, description="Cochrane 5/7/9 振动线。")
    midpointMode: str | None = Field(default=None, description="中点线：zodiac（缺省）| mundo。")
    lotsCustom: str | None = Field(default=None, description="自定义阿拉伯点 'A,B,C[,sect]'。")
    asteroids: bool | None = Field(default=None, description="含小行星（Ceres/Pallas/Juno/Vesta/Eris）。")
    ayanamsa: str | None = Field(default=None, description="恒星黄道读数（47 制键；缺省回归）。")
    stars: bool | None = Field(default=None, description="固定星线（opt-in）。")
    ccgDate: str | None = Field(default=None, description="CCG 时间地图日期 YYYY-MM-DD（给了才画）。")
    ccgTime: str | None = Field(default=None, description="CCG 时刻（缺省 12:00:00）。")
    ccgMix: str | None = Field(default=None, description="CCG 口径：mixed（缺省）| transit | progressed。")
    relMode: str | None = Field(default=None, description="关系盘：davison | composite | synastry（须配 relDate）。")
    relDate: str | None = Field(default=None, description="B 盘出生日期 YYYY-MM-DD。")
    relTime: str | None = Field(default=None, description="B 盘出生时间（缺省 12:00:00）。")
    relZone: str | None = Field(default=None, description="B 盘时区（缺省随 A 盘）。")
    relLat: str | None = Field(default=None, description="B 盘纬度（缺省同 A 地）。")
    relLon: str | None = Field(default=None, description="B 盘经度（缺省同 A 地）。")
    paranMode: str | None = Field(default=None, description="快照交映子块：off（缺省）| lum | all。")
    showLS: bool | None = Field(default=None, description="快照含本地空间线子块。")
    showGeodetic: bool | None = Field(default=None, description="快照含地理等价线子块。")
    showStarParans: bool | None = Field(default=None, description="快照含固定星交映（须 stars）。")

class AstrodataInput(FlexibleModel):
    # 名人星盘数据库（离线只读检索）：query 走 FTS 全文（姓名/条目/出生地/维基摘要），
    # category 按分类过滤，rodden 按可信度评级过滤（AA/A/B/C/DD/X/XX，可传多个），
    # personTitle 精确取单人详情（含可直接转排盘的出生数据）。纯查询不改结果 → 免确认门。
    query: str | None = None
    personTitle: str | None = None
    category: str | None = None
    rodden: str | list[str] | None = None
    birthYearFrom: int | None = None
    birthYearTo: int | None = None
    hasTimeOnly: bool | None = False
    limit: int | None = 20
    offset: int | None = 0


class GermanyInput(BirthInput):
    predictive: bool | None = False
    # 汉堡中点盘口径（上游挂载齿轮 techniqueMountSettings.js:1213-1238 → AstroMidpoint.js:301-307 下发 /germany/midpoint；
    # 后端 webgermanysrv.midpoint 读这些键）。此前未声明：CLI 经 extra 透传得到，MCP 扁平面却静默丢弃、流派写错也不报。
    # 照常声明（校验 + MCP 扁平面收顶层键），不进 tools/list 广告层（预算）；说明见 agent_guidance options_keys。
    ADVERTISE_HIDDEN: ClassVar[frozenset[str]] = frozenset(
        {"school", "orb", "personalOrb", "strictFactors", "frames", "declination", "davison", "mpCoord"}
    )
    school: Literal["classic", "pure", "uranian", "cosmo"] | None = Field(
        default=None, description="汉堡流派：classic 原始汉堡（缺省）| pure 纯净派 | uranian 美国对称 | cosmo 宇宙生物学（不用虚星，缺省容许度 1.5°）。"
    )
    orb: float | None = Field(default=None, gt=0, le=10, description="中点容许度（°；缺省 1，cosmo 缺省 1.5）。")
    personalOrb: float | None = Field(default=None, gt=0, le=10, description="个人点（Basic Five）容许度（°）；缺省不分叉。")
    strictFactors: bool | None = Field(default=None, description="严格汉堡因子集：true 剔黑月/紫气（缺省 false）。")
    frames: bool | None = Field(default=None, description="六宫框（[六宫框落宫] 段）：缺省 true。")
    declination: bool | None = Field(default=None, description="赤纬平行/反平行接触：缺省 true。")
    davison: dict[str, Any] | None = Field(default=None, description="戴维森盘第二人 {date,time,zone,lat,lon[,ad]}：产 [戴维森盘] 段。")
    # v3.13.0 挂载齿轮 GERMANY_FIELDS.mpCoord（techniqueMountSettings.js）→ germanyMidpointRequestParams 只在 ra/decl 时下发
    # /germany/midpoint（后端 germany/coord_midpoint.py 另算 coordMidpoints）→ 快照 [中点坐标] 段。lon/缺省 = 不成段。
    mpCoord: Literal["lon", "ra", "decl"] | None = Field(
        default=None, description="中点坐标：lon 黄经（缺省，不另成段）| ra 赤经 | decl 赤纬（后两者产 [中点坐标] 段）。"
    )
    # 上游 v3.11 [Q-442/T-405]「校时」页签（只读预览）：待校事件 → 太阳弧（Naibod）推进 MC/Asc 看是否触动本命因子。
    rectifyEvents: list[dict[str, Any]] | None = Field(
        default=None,
        description="校时预览事件（可选）：[{date:'YYYY-MM-DD', type:marriage|children|career|move|loss|accident|other, label}]；给了才产 [校时预览]（推进 MC/Asc 看是否触动本命因子，只预览不改盘）。",
    )


class HarmonicInput(BirthInput, _ChartDayBoundaryKnobs):
    # 调波盘 (harmonic chart) is a backend chart-extra computation (POST /astroextra/harmonic on the
    # Python chart service). harmonic = the H-number (1–360, 星阙 default 9); orb = conjunction orb.
    predictive: bool | None = False
    lifespanMethod: str | None = Field(default=None, description=_LIFESPAN_METHOD_DESC)
    harmonic: int | None = 9
    orb: float | None = 2.0


class BabylonInput(BirthInput):
    # 巴比伦占星（美索不达米亚天象体系）：恒星黄道 · 毕宿锚（Aldebaran = 金牛 15°）。
    # 本体系无十二宫位、无相位、无上升点——盘面是数据清单，解读装置是「位」(三分+日段) 与行星神性。
    # 派系口径直接改分至规范与「位」的落点 → 结果敏感，缺省不静默切换。
    predictive: bool | None = False
    scheme: str | None = Field(default=None, description="实位派系：swissA10（默认）/ systemA / systemB。")
    solstice: str | None = Field(default=None, description="分至规范：A10（春分白羊 10°）/ B8（春分白羊 8°）；缺省跟派系档。")
    # 真正的判读参数（此前一个都没接）：
    dodecaVariant: str | None = Field(default=None, description="十二分变体：A（加于宫起点）/ B（加于点本身·楔文）；缺省跟派系档。")
    cubitDeg: float | None = Field(default=None, description="肘度（1 cubit 折合黄经度数），缺省跟派系档（2.2）。")
    # v3.11：era 进 [起盘信息] 纪元行（babylonAiSnapshot.js:219-221）；ephemerisSource 选 [数理星历] 木星阶梯/锯齿函数（:120）。
    # 不进 tools/list 广告层（预算），词表见 agent_guidance。
    ADVERTISE_HIDDEN: ClassVar[frozenset[str]] = frozenset({"era", "ephemerisSource"})
    era: str | None = Field(default=None, description="纪元显示：seleucid 塞琉古 S.E.（缺省）| arsacid 安息（= S.E.−64）。")
    ephemerisSource: str | None = Field(default=None, description="数理星历位置源：swiss（缺省）| systemA 阶梯 | systemB 锯齿（木星）；缺省跟派系档。")


class DraconicInput(BirthInput, _ChartDayBoundaryKnobs):
    # 龙盘 (draconic chart)：把命盘各点黄经减去北交点黄经（POST /astroextra/draconic）。
    # 后端返回 {nodeLon, positions, conjunctions, chart}，chart 与 /chart 同形。
    predictive: bool | None = False
    lifespanMethod: str | None = Field(default=None, description=_LIFESPAN_METHOD_DESC)
    orb: float | None = 2.0


class RelocationInput(BirthInput, _ChartDayBoundaryKnobs):
    # 重置盘 (relocation)：保留出生 UT，仅用新经纬重算十二宫与上升/中天（POST /astroextra/relocation）。
    # 行星黄经由 UT 决定故不变，宫位/角点随地点变 —— 迁居占星的标准做法。
    # relocLat/relocLon 缺省回退到出生地，等于本命盘（结果敏感：不给新地点就不是「重置」）。
    predictive: bool | None = False
    lifespanMethod: str | None = Field(default=None, description=_LIFESPAN_METHOD_DESC)
    relocLat: Any | None = Field(default=None, description="重置地纬度（如 51n30）；缺省回退出生地。")
    relocLon: Any | None = Field(default=None, description="重置地经度（如 0w07）；缺省回退出生地。")


# 世俗盘也吃的 F17 快照口径键（BirthInput 上「send:'never'——不进 /chart，只改导出段」的那组里，世俗盘正文真消费的部分：
# [信息] 互容接纳过滤 + [埃及历] 七轴；[古典·显赫计分] 四键不列——该段上游只在本命 astro 快照路径产，世俗盘无）。
MUNDANE_SNAPSHOT_KEYS: tuple[str, ...] = (
    "showOnlyRulExaltReception",
    "egypt_decanRuler", "egypt_decanAnchor", "egypt_decanNaming", "egypt_starClock",
    "egypt_calendarAnchor", "egypt_petosirisMod", "egypt_godEdition",
)


class MundaneInput(FlexibleModel):
    # 世俗入宫盘 (mundane ingress chart): cast at the precise solar-term ingress moment of a given year.
    # date/time are DERIVED from the ingress (jieqi) computation, so the inputs are year + 入宫节气 + place.
    year: int | str = Field(description="年份：入宫盘的入宫年；mundaneType=region（地区盘）时为推运目标年（[地区盘推运] 盘龄 = year − 建置年）。")
    ingressTerm: str | None = "春分"  # 春分 / 夏至 / 秋分 / 冬至 (the four cardinal ingresses)
    lifespanMethod: str | None = Field(default=None, description=_LIFESPAN_METHOD_DESC)
    zone: str | None = "+08:00"
    lat: str | None = None
    lon: str | None = None
    gpsLat: float | None = None
    gpsLon: float | None = None
    ad: int | None = 1
    hsys: int | None = 0
    tradition: bool | None = False
    # 盘型分派（上游 MundaneMain 的 MUNDANE_TYPES）：底盘恒为入宫盘；盘型只决定加产哪组专属段/卡
    # （mundanehorary → [世运卜卦]/[世运问判]；solunar/vedicmundane → 各自求根盘；newmoon/fullmoon/
    # solecl/lunecl/cycles → 对应子盘的判读卡）。region（地区盘）底盘换成 regionKey 指定的预置建置盘（不求入宫）。
    mundaneType: str | None = Field(
        default=None,
        description="盘型：ingress（默认）/ newmoon / fullmoon / solecl / lunecl / cycles / solunar / vedicmundane / mundanehorary / region（地区盘，配 regionKey）。",
    )
    mhKind: str | None = Field(default=None, description="世运卜卦问类：war 战争（默认）/ weather 天候 / price 物价。")
    solunarType: str | None = Field(default=None, description="恒星派入境盘型：capsolar（默认）/arisolar/cansolar/libsolar/caplunar/arilunar/canlunar/liblunar。")
    solunarWeights: str | None = Field(default=None, description="恒星派权重方案（scheme_a 默认）。")
    solunarOrb: float | None = Field(default=None, description="角化容许度（默认 3°）。")
    vedicYear: int | None = Field(default=None, description="吠陀世运年份（缺省取 year）。")
    # 世运口径（上游页面设置 MundaneMain.js:519-526 + 吠陀世运 :1330-1340）与入宫盘的黄道口径：照常声明（校验 + MCP 扁平面
    # 收顶层键），不进 tools/list 广告层（预算）；值域见 agent_guidance。古典全局键（cazimiOrb…）经 request 整包透传进 /chart。
    ADVERTISE_HIDDEN: ClassVar[frozenset[str]] = frozenset({
        "mundaneRuleset", "mundaneOrbScheme", "mundaneIngressRule", "vedicDashaYearLen", "vedicFoundingYear",
        "vedicNatalAsc", "zodiacal", "siderealAyanamsa", "regionKey", "regionCandidate", *MUNDANE_SNAPSHOT_KEYS,
    })
    mundaneRuleset: str | None = Field(default=None, description="规则集：ptolemaic / medieval / modern（缺省）/ barbault；[定局·年主/盘主]（界/三分变体定年主）与 [地理分野]（数据集）随之。")
    mundaneOrbScheme: str | None = Field(default=None, description="受冲容许度覆盖：auto（缺省随规则集）/ moiety / by_aspect。")
    mundaneIngressRule: str | None = Field(default=None, description="入境主管制覆盖：auto（缺省）/ quarterly / aries_annual / capricorn_year。")
    vedicDashaYearLen: float | None = Field(default=None, description="世运大运年长：365.2425（缺省）/ 360。")
    vedicFoundingYear: int | None = Field(default=None, description="建国年（Muntha 敏感点用，须配 vedicNatalAsc）。")
    vedicNatalAsc: str | None = Field(default=None, description="建国盘上升星座键（aries…pisces）。")
    zodiacal: int | None = Field(default=None, description="黄道：0 回归（缺省）/ 1 恒星（配 siderealAyanamsa）。")
    siderealAyanamsa: str | None = Field(default=None, description="恒星黄道岁差制（zodiacal=1 时）。")
    # 地区盘（上游 MUNDANE_TYPES 'region' + divination/data/regionCharts.js 预置建置盘；MundaneMain.applyRegion :715-733）。
    regionKey: str | None = Field(
        default=None,
        description="地区盘建置盘键（mundaneType=region 必填）：vendored regionCharts.js 预置 london_1066 / philadelphia_1776 / paris_1792；认不出的键报错并列出可选键。",
    )
    regionCandidate: str | None = Field(
        default=None,
        description="地区盘候选建置时刻键（a/b/c；缺省首候选 = 最通行者。philadelphia_1776：a 17:10 / b 02:13 / c 12:00；paris_1792：a 12:00 / b 09:00 / c 15:00；london_1066：a 12:00 / b 13:30）。",
    )
    # F17 快照口径键（与 BirthInput 同名同义、描述单源）：[信息] 互容接纳过滤 + [埃及历] 七轴。世俗盘正文是同一套本命段 builder，
    # 这些键此前未在本模型声明 → MCP 扁平面按广告签名静默丢弃（CLI / tool_run / request 整包不丢），见 test_mcp_flat_surface_keys。
    showOnlyRulExaltReception: Any | None = Field(default=None, description=BirthInput.model_fields["showOnlyRulExaltReception"].description)
    egypt_decanRuler: str | None = Field(default=None, description=BirthInput.model_fields["egypt_decanRuler"].description)
    egypt_decanAnchor: str | None = Field(default=None, description=BirthInput.model_fields["egypt_decanAnchor"].description)
    egypt_decanNaming: str | None = Field(default=None, description=BirthInput.model_fields["egypt_decanNaming"].description)
    egypt_starClock: str | None = Field(default=None, description=BirthInput.model_fields["egypt_starClock"].description)
    egypt_calendarAnchor: str | None = Field(default=None, description=BirthInput.model_fields["egypt_calendarAnchor"].description)
    egypt_petosirisMod: int | None = Field(default=None, description=BirthInput.model_fields["egypt_petosirisMod"].description)
    egypt_godEdition: str | None = Field(default=None, description=BirthInput.model_fields["egypt_godEdition"].description)


class OtherBuInput(BirthInput):
    tradition: bool | None = False
    sign: str | None = "Aries"
    house: int | None = 0
    planet: str | None = "Sun"
    question: str | None = None
