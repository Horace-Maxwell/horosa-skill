"""所有技法输入的地基：FlexibleModel（extra=allow）、出生信息 BirthInput、不进广告层的旋钮标记、本命盘日界开关。"""
from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from horosa_skill.astro_rulers import HOUSE_SYSTEM_LABELS


class FlexibleModel(BaseModel):
    model_config = ConfigDict(extra="allow")
    agent_confirmed_settings: bool | None = None
    defaults_accepted: bool | None = None
    clarification_notes: str | None = None
    # 自备知识库点名（knowledge/user.py）：条目 id / 标题 / `#标签` / `auto`。run_tool 在校验**之前**就把它取走——
    # 不进 input_normalized、不进引擎请求、不进存档的 subject；只决定 data.knowledge_context 带哪些条目。
    # 声明在这里是为了 MCP 顶层按名可传（FastMCP 丢未声明键），不进广告层（预算），用法见 SKILL.md 与 server_profile。
    knowledge: list[str] | str | None = Field(default=None, json_schema_extra={"x-horosa-hidden": True})


def _unadvertised() -> Any:
    """已声明（MCP 顶层按名可传、进 pydantic 校验层）但不进 tools/list 广告层的旋钮（长词表 → 预算）。

    键表与取值由 horosa_agent_guidance 的 options_keys 给（agent_guidance/tool_table.py），广告层只在 `request`
    描述里计数「另 N 个高级旋钮」（surfaces/mcp_schema.py 的 x-horosa-hidden）。
    """
    return Field(default=None, json_schema_extra={"x-horosa-hidden": True})


class BirthInput(FlexibleModel):
    date: str = Field(description="公历日期 YYYY-MM-DD（如 1995-06-03）；公元前配 ad=-1。")
    time: str = Field(description="时间 HH:mm 或 HH:mm:ss（24 小时制，如 05:30）。")
    zone: str = Field(description="时区：+08:00 这类固定偏移，或 IANA 名（如 Asia/Shanghai，按盘面日期自动折算）。")
    # F17（上游 utils/timezone.js:124-151 unifyCnZone）：IANA Asia/Urumqi 且日期 ≥ 1949-10-01 时按北京时间
    # （Asia/Shanghai）折算，载荷留 geoZone/zoneAdvisory 并进 warnings/技法卡。false=保留新疆地理时区（+06:00）；
    # 直接给偏移（如 "+06:00"）也不归并。非 BirthInput 族模型经 request 逃生舱传。
    cnUnifiedZone: bool | None = Field(default=None, description="北京时间统一（false=保留新疆时区）")
    lat: str = Field(description="纬度：31n13（31°13'N）或十进制 31.2167（会自动归一）；南纬用 s。")
    lon: str = Field(description="经度：121e28（121°28'E）或十进制 121.4667（会自动归一）；西经用 w。")
    ad: int | None = Field(default=1, description="纪元：1=公元后（默认），-1=公元前。")
    # 响应视图（所有技法工具通用，FlexibleModel 均接受）：None=完整；"sections"=段标题+正文；
    # "titles"=只留段标题索引。仅精简返回体，完整快照照常存档（memory_show 可取回）。
    response_view: str | None = Field(
        default=None,
        description="响应精简视图：缺省=完整；'sections'=段标题+正文；'titles'=只留段标题索引（完整结果已存档，memory_show 可取回）。",
    )
    # 全表 0–24 由 astro_rulers.HOUSE_SYSTEM_LABELS（上游 AstroConst.HOUSE_SYSTEM_OPTIONS 镜像）生成——校验层描述，
    # 不进 tools/list（广告层 hsys 走 mcp_schema.CORE_DOC + 0–8 enum，预算所限）。
    # 缺省 1 = 星阙 DefaultHouseSystem（models/astro.js:29；无头挂载 aiAnalysisContext.js:494 `record.hsys ?? 1`、
    # techniqueMountSettings.js:828 default 1）。v0.40.0 起随上游（此前 skill 缺省 0 整宫，与上游分叉）；
    # 上游页面硬钉 0 的技法（七政 / 节气 / 择日 / 世运 / 印占）在各自模型显式覆盖回 0。
    hsys: int | None = Field(
        default=1,
        description=(
            "宫制索引 0–24（缺省 1 Alcabitus = 星阙 DefaultHouseSystem；上游 AstroConst.HOUSE_SYSTEM_OPTIONS）："
            + " ".join(f"{k}={v}" for k, v in HOUSE_SYSTEM_LABELS.items())
            + "。缺省 0=整宫 Whole Sign（上游页面缺省 1 Alcabitus）。注意 1 不是 Placidus（Placidus=3）。"
        ),
    )
    # 地点显示名：进 [起盘信息]/配置段与搜索请求（样例载荷一直带它，此前 MCP 扁平面静默丢弃）。
    pos: str | None = None
    # 当事人显示名：随请求透传到后端并进盘头（样例载荷一直带它，此前 MCP 扁平面静默丢弃）。
    name: str | None = None
    tradition: bool | None = False
    predictive: bool | None = True
    southchart: bool | None = False
    zodiacal: int | bool | None = Field(default=0, description="黄道：0=回归 tropical（默认），1=恒星 sidereal（配 siderealAyanamsa）。")
    # 恒星黄道 ayanāṃśa (星阙 v2.6.4)：仅在 zodiacal=1(恒星) 时生效，选 47 个岁差模式之一
    # (lahiri/raman/krishnamurti/fagan_bradley/…，见 astro_sidereal.SIDEREAL_AYANAMSA_LABELS)。
    # 缺省(不传) == Lahiri，向后兼容回归黄道盘不受影响。贯穿全西洋技法盘(命占/合盘/中点/卜卦/三式/节气)。
    siderealAyanamsa: Any | None = None
    pdtype: Any | None = None
    pdMethod: Any | None = None
    pdTimeKey: Any | None = None
    pdaspects: list[int | str] | None = None
    # 主限法（星阙 v3.6.0 大改版）：顺/逆向、映点(antiscia)、界(terms) promissor 开关 + 年限上限。
    # pdMethod 现为**方位法全谱 13 法**（旧「核5」注记已过期两代）；pdTimeKey 含每盘真算
    # Simmonite/Kepler/Brahe/VanDam + 动态 TrueSolarArc/SymbolicSolarArc + 自定义率；
    # pdYears 上限 3000（>360 出多圈复发行）。仅在显式设置时透传（model_dump(exclude_none=True)），
    # 缺省走后端默认（顺逆都开/映点界关/100 年）。白名单在上游 astropy/astrostudy/perchart.py。
    pdDirect: Any | None = None
    pdConverse: Any | None = None
    pdAntiscia: Any | None = None
    pdTerms: Any | None = None
    pdYears: Any | None = None
    # v3.6.0 正交解耦：弧算法(投影) × 盘面宫制(分宫) 拆成两个独立轴，不再由 pdMethod 一个键决定。
    # 这些字段此前已能经 FlexibleModel extra 透传到后端并真实生效，但没有 schema 描述 = agent 发现不了，
    # 等于事实上不可用。声明出来即解锁（零 service 改动）。
    pdProjection: Any | None = Field(default=None, description="弧算法/投影（11 种）：与 pdFrame 正交，决定弧如何投影。")
    pdFrame: Any | None = Field(default=None, description="盘面宫制/分宫 frame（12 种，含 koch）：与 pdProjection 正交。")
    pdFramework: Any | None = Field(default=None, description="界行框架：aspect | bounds | release（hyleg/anareta 判读层）。")
    pdSignificators: Any | None = Field(default=None, description="应星扩展：Desc/IC/Syzygy/Spirit/Cusps/Stars/Lots 等。")
    pdPromissorTypes: Any | None = Field(default=None, description="迫星类型扩展：cusps / stars / lots。")
    pdTimeKeyCustom: Any | None = Field(default=None, description="自定义时间钥匙速率（0.001–30 度/年）。")
    pdParallel: Any | None = Field(default=None, description="赤纬平行是否计入（三类被限星之一）。")
    pdRaptParallel: Any | None = Field(default=None, description="周日运动平行（rapt parallel）是否计入。")
    # 古典参数全局化（星阙 v3.6.0）：以下 16 键由后端 webmodernsrv 统一透传给古典判读层，
    # 影响 [古典] / [古典格局] 段的逐值结果（容许度、空亡口径、界表流派、交点性质…）。
    # 与主限法同理：本仓早已能经 extra 透传，声明只为可发现性。
    westNodeType: Any | None = Field(default=None, description="交点取法：真交点 / 平交点。")
    sectBuffer: Any | None = Field(default=None, description="同异宗(sect)判定的地平缓冲角。")
    cazimiOrb: Any | None = Field(default=None, description="核心内(cazimi)容许度。")
    combustOrb: Any | None = Field(default=None, description="燃烧(combust)容许度。")
    underBeamsOrb: Any | None = Field(default=None, description="日光下(under the beams)容许度。")
    vocMode: Any | None = Field(default=None, description="月空(void of course)判定口径（六种之一）。")
    vocIncludeOuter: Any | None = Field(default=None, description="月空判定是否计入外行星。")
    starOrb: Any | None = Field(default=None, description="恒星触发容许度。")
    antisciaOrb: Any | None = Field(default=None, description="映点(antiscia)容许度。")
    viaCombustaVariant: Any | None = Field(default=None, description="燃烧之路(via combusta)区间口径。")
    termsVariant: Any | None = Field(default=None, description="界(terms)表流派：埃及 / 托勒密 等。")
    leoBoundFirst: Any | None = Field(default=None, description="狮子座界首主星口径。")
    geminiBoundEmended: Any | None = Field(default=None, description="双子界表勘误（v3.6.0 修订）。")
    triplicity: Any | None = Field(default=None, description="三分主星体系（Dorotheus / Ptolemy 等）。")
    # saturnExalt20 已随上游 v3.9.3 删档（2026-08-18 上游拍板：degree 位全仓零消费者=真死开关，
    # push_request_exalt_variants 签名 2→1 参）。typed 字段保留只会向 agent 广告一个死开关。
    nodeExaltation: Any | None = Field(default=None, description="交点是否参与旺弱(exaltation)判定。")
    # ── 古典参数 typed 化（v0.33.0 批 I-6：上游 WP-2~8 30 键补全声明；描述照 classicalParamSpec.js
    # 标签逐条对齐，helper.py 45 键白名单为回显权威。全部 None=不发送=后端默认，零回归。──
    dignityDebilities: Any | None = Field(default=None, description="弱陷计负分（陷 −5 · 落 −4；缺省开）。")
    almutenTripMode: str | None = Field(default=None, description="Almuten 三分计分：all=三主全计（缺省）| sectRulerOnly=仅当值主。")
    planetaryHourMethod: str | None = Field(default=None, description="行星时制式：sunrise=日出起算等长时（缺省）| unequal=昼夜不等时（传统）| equal24=廿四时等分。")
    combustOwnChariotExempt: Any | None = Field(default=None, description="界内三分内免燃烧 own chariot（Porphyry；缺省关）。")
    westLilithType: str | None = Field(default=None, description="黑月莉莉丝：mean=平均远地点（缺省）| true=真实远地点(osculating)。")
    topocentricMoon: Any | None = Field(default=None, description="月亮站心视差修正（影响月亮黄经 ≤1°，福点随动；缺省关）。")
    lotReversal: Any | None = Field(default=None, description="福点按昼夜反转（缺省开；关则恒昼式）。")
    lotsDocReverse: Any | None = Field(default=None, description="婚·子·友·疾四点用文档序公式（缺省关）。")
    hermeticLotsReversal: Any | None = Field(default=None, description="七星点按昼夜反转（批判本校勘；缺省开，关则恒同式）。")
    erosConstruction: str | None = Field(default=None, description="爱欲点构成：paulus=金星·水星系（缺省）| valens=福点·精神系。")
    lotFortuneVariant: str | None = Field(default=None, description="福点公式变体：standard=标准昼夜式（缺省）| moonAboveNight=月在地平上恒夜式。")
    lotFatherCombustAlt: Any | None = Field(default=None, description="父点土星伏时替代式（Dorotheus 系；缺省关）。")
    lotProjection: str | None = Field(default=None, description="希腊点点度计数法：portion=度数投射（缺省）| sign=整星座。")
    orbSystem: str | None = Field(default=None, description="容许度判据体系：perObject=星体轨任一覆盖（缺省）| byAspect=按相位名(合冲刑拱8°/六合4°) | wholeSign=整星座位相 | wholeSignMoiety=整星座内两轨半距和。")
    luminaryOrbBonus: int | None = Field(default=None, description="发光体·四轴轨加成：0（缺省）/10/20/30（%）。")
    orbs: dict[str, Any] | None = Field(default=None, description="逐星容许度覆盖（星体 id → 度；缺省用默认表）。")
    orbScale: float | None = Field(default=None, description="容许度全局倍数（缺省 1.0）。")
    aspectIncludeCusps: Any | None = Field(default=None, description="宫头参与相位（≤3°；缺省关）。")
    aspectIncludeLots: Any | None = Field(default=None, description="希腊点参与相位（点为受体 ≤3°；缺省关）。")
    aspectIncludeMidpoints: Any | None = Field(default=None, description="中点参与相位（日月四轴硬相 ≤1.5°；缺省关）。")
    starOrbMode: str | None = Field(default=None, description="恒星轨档：school=按流派平轨（缺省）| byMagnitude=按星等。")
    stationMarking: str | None = Field(default=None, description="留驻判定（盘面 S·D 标）：off=仅逆行R标（缺省）| exactWindow=距留点≤1日 | distance=距留点黄经≤2′ | absSpeed=日速<1′ | relSpeed=日速<3%均速。")
    solarReturnVariant: str | None = Field(default=None, description="太阳返照法：precise=精确回归（缺省，现代）| hellenistic=希腊式（月定上升）。")
    returnLatitudeMode: str | None = Field(default=None, description="返照落宫投影：ecliptic=黄道度（缺省）| withLatitude=计入黄纬（Umar al-Tabari 法）。")
    houseCuspAdvance: int | None = Field(default=None, description="行星落宫宫头前移：5°（缺省，传统）/3/1/0（整宫制豁免）。")
    vulcanCalc: str | None = Field(default=None, description="祝融星（推算行星）：off（缺省）| weston=轨道根数法 | baker=水星系推算。")
    customTermsDay: Any | None = Field(default=None, description="自定义界表·昼表（termsVariant=4 时生效；非法整表回落埃及界）。")
    customTermsNight: Any | None = Field(default=None, description="自定义界表·夜表（可缺=昼夜同表）。")
    userAyanT0: float | None = Field(default=None, description="自定义恒星黄道参考历元 JD（siderealAyanamsa='user' 配套）。")
    userAyanDeg: float | None = Field(default=None, description="自定义恒星黄道在 T0 历元的岁差度（'user' 配套）。")
    # 快照口径键（send:'never'——不进 /chart，只改导出段；BirthInput 字段不进 tools/list 广告层）：
    # [古典·显赫计分] 主宰光体判定四键（classicalParamSpec.js）+ [信息]/[古典格局] 互容接纳过滤 + [埃及历] 七轴（egypt_*）。
    busyPlaces: str | None = Field(default=None, description="有利宫位集：'1,4,5,7,10,11'（缺省）| '1,4,7,10' | '1,2,4,5,7,9,10,11' | '1,3,4,5,7,9,10,11'。")
    dynamicalDivisions: Any | None = Field(default=None, description="动力学区分（象限强度分区）：0（缺省）/1。")
    domicileMasterMethod: str | None = Field(default=None, description="主宰主星判法：domicile 庙主派（缺省）| bound 界主派。")
    rayWeighting: str | None = Field(default=None, description="七射线权重：off（缺省）| equal | weighted。")
    showOnlyRulExaltReception: Any | None = Field(default=None, description="仅按本垣/擢升计算互容接纳（[信息] 接纳互容行与 [古典格局] 格局速览·先验权力同口径）：0（缺省）/1。")
    # 埃及历七轴取值 = egyptianSchools.EGYPT_SCHOOL_AXES（首项默认档；认不出的值报 tool.egypt_invalid_setting）。
    egypt_decanRuler: str | None = Field(default=None, description="埃及历·旬主星制：chaldean 迦勒底外貌（缺省）| triplicity 三分性旬星。")
    egypt_decanAnchor: str | None = Field(default=None, description="埃及历·旬序锚定：greek 希腊化回归（缺省）| ancient 古代恒星。")
    egypt_decanNaming: str | None = Field(default=None, description="埃及历·旬名录传统：egypt 埃及本名（缺省）| coptic 科普特-希腊名 | hermes 赫尔墨斯名。")
    egypt_starClock: str | None = Field(default=None, description="埃及历·星钟法：diagonal 对角星钟·升起法（缺省）| transit 过中天星钟。")
    egypt_calendarAnchor: str | None = Field(default=None, description="埃及历·历法锚点：ce139 公元 139 年重合点（缺省）| nabonassar 那波那萨尔纪元 | philip 腓力纪元。")
    egypt_petosirisMod: int | None = Field(default=None, description="埃及历·Petosiris 模数：29（缺省）| 30。")
    egypt_godEdition: str | None = Field(default=None, description="埃及历·众神版本：seamless 无缺口自洽版（缺省）| variant 通行变体。")
    gpsLat: float | None = None
    gpsLon: float | None = None
    includePrimaryDirection: bool | None = None
    simpleAsp: bool | None = None
    # wave 3b：本命 / 十三分 / 十二分 / 希腊分盘缺省随上游发 0（models/astro.js:105-108、aiAnalysisContext.js:567 buildFieldObject
    # `record.strongRecption ?? 0`）；不发则 perchart.py:814 缺省严格 → [信息] 接纳/互容与上游缺省盘不同（service._apply_chart_request_defaults）。
    strongRecption: bool | None = Field(
        default=None,
        description="严格接纳开关：false/0（缺省，随上游本命/十三分/十二分/希腊分盘请求）=五种尊贵任一即算接纳；true/1=只认本垣/擢升。"
        "调波/龙盘/重置盘不带该键（后端缺省严格），显式传值永远优先。",
    )
    virtualPointReceiveAsp: bool | None = None
    doubingSu28: bool | None = None
    nodeRetrograde: bool | None = None
    asporb: float | None = 1.0
    datetime: str | None = None
    dirLat: str | None = None
    dirLon: str | None = None
    dirZone: str | None = None
    startSign: str | None = None
    stopLevelIdx: int | None = None


# [寿命格局] 取主法（上游 AstroLifespan.js:14-18；上游是全局设置 horosa.lifespan.method，skill 按调用传）。
_LIFESPAN_METHOD_DESC = "[寿命格局]取主法：ptolemy 托勒密（缺省）| alcabitius | dorotheus"


class _ChartDayBoundaryKnobs(BaseModel):
    """西占 chart 家族的日界两键（wave 3b）：只进 [起盘信息] 的时间基准行与排盘规则行（astroAiSnapshot.js:446-455；上游页面 /
    AI 挂载 fields 恒带二键、缺省 dayBoundary 出厂 1/1，service._chart_family_snapshot_fields 同补），不进 /chart 请求（Python 盘
    不算四柱）。声明而不广告（tools/list 预算；🔴 不能放进 BirthInput——`advertised_technique_schema` 以「不在 BirthInput 里」判
    子类自有字段，放进去会把紫微/八字/奇门等中式工具**已广告**的同名键静默挤出广告层）。说明进 western_options_doc → guidance。"""

    ADVERTISE_HIDDEN: ClassVar[frozenset[str]] = frozenset({"after23NewDay", "lateZiHourUseNextDay"})
    after23NewDay: int | bool | None = Field(
        default=None,
        description="日界开关（西占盘只进 [起盘信息] 时间基准/排盘规则两行，不改星位）：1=23 点换日（缺省，上游 dayBoundary 出厂值）0=24 点换日。",
    )
    lateZiHourUseNextDay: int | bool | None = Field(
        default=None,
        description="晚子时时柱开关（同上两行）：1=时干按次日日干起子时（缺省）0=按当日日干。",
    )
