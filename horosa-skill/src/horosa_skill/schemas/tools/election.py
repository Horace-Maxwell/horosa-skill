"""择日 / 择时 / 卜卦输入：条件树扫描公共基类与九个择日、天星择日、七政择日、horary、election。"""
from __future__ import annotations

from typing import Any, ClassVar

from pydantic import Field

from horosa_skill.schemas.tools.base import BirthInput
from horosa_skill.schemas.tools.cn_divination import QimenInput


class ZeriScanInput(BirthInput):
    """择日十技法的共享入参（上游 v3.10.0）。

    `date`/`time`/`zone`/`lat`/`lon` 继承自 BirthInput —— 它们是**候选时刻**的坐标，不是出生盘；
    真正的搜索范围由 startDate/startTime/endDate/endTime 给。命中后展示盘按基底技法自己的算源铸，
    只有区间搜索在本地/后端扫描引擎里跑（各工具的 `compute_sources` 如实标出这一分工）。

    条件树按 passthrough 建模而非在此重编：上游十技法合计三百余个条件类，各自 params 形状/validate/
    compile 都不同，在这里重写一遍等于造第二份真值源，上游一加条件类就烂。vendored 的
    `compile<X>Tree` 会跑各叶子自己的 validate 抛本地化错误；条件类键与参数走 agent_guidance 暴露。
    """
    hsys: int | None = 0  # 上游择日条件树 ConditionBuilderModal.js:421 `cfg.hsys || 0`；扫描载荷转发本键

    startDate: str | None = Field(default=None, description="搜索窗起始日（YYYY-MM-DD）")
    startTime: str | None = Field(default="00:00", description="搜索窗起始时刻（HH:mm）")
    endDate: str | None = Field(default=None, description="搜索窗结束日（YYYY-MM-DD）")
    endTime: str | None = Field(default="23:59", description="搜索窗结束时刻（HH:mm）")
    pos: str | None = Field(default=None, description="地点显示名，进配置段与搜索请求")
    conditions: Any | None = Field(
        default=None,
        description=(
            "条件树。组节点 {kind:'group', joiner:'all'|'any'|'xor', negate?, children:[…]}；"
            "叶节点 {kind:'leaf', type:'<条件类键>', negate?, params:{…}}。"
            "条件类键与参数见本工具的 agent_guidance。"
        ),
    )
    options: dict[str, Any] | None = Field(
        default=None, description="起局/判读口径覆写；与顶层同名字段双读合并，options 优先。"
    )
    natal: dict[str, Any] | None = Field(
        default=None, description="本命盘上下文（部分条件类按本命比对时需要，如八字/紫微/六壬的本命组）。"
    )
    maxHits: int | None = Field(default=None, description="命中上限（缺省用引擎自带上限）。")
    maxSpanDays: int | None = Field(
        default=None,
        description="搜索窗天数上限，只能**调低**：给的值超过本工具的硬上限时按硬上限执行，不会放宽。",
    )
    # [Q-452/Q-453] 快照「命中清单」两旋钮（上游 zeriSnapshotPrefs：60 行·10–500；判读树 3 行·0–20）。
    zeriSnapshotMaxRows: int | None = Field(default=None, description="清单行数10-500(缺省60)")
    zeriSnapshotExplainRows: int | None = Field(default=None, description="判读树行数0-20(缺省3)")


class HuangliZeriInput(ZeriScanInput):
    """黄历择吉：**日粒度**扫描（不吃起局开关），命中段是整日。"""


class BaziZeriInput(ZeriScanInput):
    """八字择时：时辰粒度。起局三开关 + godKeyPos/phaseType 与 bazi_birth 同词表。"""

    timeAlg: int | None = None
    after23NewDay: int | None = None
    lateZiHourUseNextDay: int | None = None
    godKeyPos: str | None = None
    phaseType: int | None = None


class TaiyiZeriInput(ZeriScanInput):
    """太乙择时：时辰粒度。太乙时基是**钟表时**（上游口径，与后端 kentang 太乙一致）。"""

    # 引擎按对象展开（taiyiZeriScanEngine：applyTaiyiSchool(pan, o.school || {})）——此前声明成 str，任何字符串都被静默
    # 忽略、对象又过不了校验。展示盘（taiyi runner）读同一顶层 school，扫描与所见同一套流派。
    school: dict[str, Any] | None = Field(default=None, description="流派六轴对象，同 taiyi options.school。")


class ZiweiZeriInput(ZeriScanInput):
    """紫微择时：时辰粒度。"""

    timeAlg: int | None = None
    after23NewDay: int | None = None
    lateZiHourUseNextDay: int | None = None
    # 扫描按 options.gender 起盘（上游工作台常驻键，出厂 1）；顶层写法与 options 双读合并，展示盘同跟。
    gender: int | str | None = None


class LiurengZeriInput(ZeriScanInput):
    """六壬择时：时辰粒度。"""

    guirengType: int | None = Field(default=None, description="贵人取法，与 liureng_gods 同词表。")
    after23NewDay: int | None = None
    lateZiHourUseNextDay: int | None = None


class SanshiZeriInput(ZeriScanInput):
    """三式合一择时：时辰粒度，条件可跨六壬/奇门/太乙三盘（70 个条件类，最多的一支）。"""

    timeAlg: int | None = None
    after23NewDay: int | None = None
    lateZiHourUseNextDay: int | None = None
    guirengType: int | None = None


class ZeriBackendScanInput(ZeriScanInput):
    """后端扫描成员共享：多一个单时刻逐叶判读入口（与 tianxing 的 explainAt 同款）。"""

    explainAt: str | None = Field(
        default=None,
        description="对该时刻做逐叶判读（YYYY-MM-DD HH:mm[:ss]）；与扫描求值器同源。不给则不产该段。",
    )


class QizhengZeriInput(ZeriBackendScanInput):
    """七政择时：判定与区间搜索都在 astropy 后端（swisseph 直连分钟粒度），非本地重算。"""

    height: float | None = Field(default=None, description="海拔（米），缺省 0")
    # 扫描上下文实读三键（QizhengScanContext；上游页出厂 2/mean/mean）。ayanamsaDeg 已删：两个扫描都不读它
    # （它只属七政择日动盘 qizhengelection），声明着等于广告一个死开关。
    su28Mode: int | None = Field(default=None, description="宿度制：2=回归今宿（缺省）3=开禧宿度")
    nodeType: str | None = Field(default=None, description="罗计：mean（缺省）|true")
    lilithType: str | None = Field(default=None, description="月孛：mean（缺省）|true")


class IndiaZeriInput(ZeriBackendScanInput):
    """印度择时（Muhurta）：后端扫描。段自足 —— 印度盘全文见 india_chart 本身，本工具只出择时三段。"""

    # 扫描上下文读 ayanamsa（IndiaScanContext）；indiaAyanamsa 是与 india_chart 同词表的别名（显式 ayanamsa 优先）。
    # indiaHsys 已删：Muhurta 扫描不读分宫制、本工具也不铸印度盘，声明着等于广告一个死开关。
    indiaAyanamsa: Any | None = Field(default=None, description="扫描岁差制（缺省 lahiri），与 india_chart 同词表")
    nodeType: str | None = Field(default=None, description="罗睺计都：mean（缺省）|true")


class QimenZeriInput(QimenInput):
    """奇门择日「找局」：在时间窗内扫出满足条件树的时辰。

    盘面参数与 QimenInput 逐字相同（同一套 22 项 options / 晚子时 / 时家算法），只多出搜索窗与条件树 ——
    展示盘仍走 ken `/qimen/pan`，只有区间**搜索**用本地引擎（见 service._run_qimenzeri_tool 的算权说明）。
    """

    # service 会把 pos 读进搜索请求（_run_qimenzeri_tool 的 geo），但此前 schema 不声明 ——
    # FlexibleModel 收得下，agent 却无从得知它存在。声明即可发现。
    pos: str | None = Field(default=None, description="地点显示名，进配置段与搜索请求")
    startDate: str | None = Field(default=None, description="搜索窗起始日（YYYY-MM-DD）")
    startTime: str | None = Field(default="00:00", description="搜索窗起始时刻（HH:mm）")
    endDate: str | None = Field(default=None, description="搜索窗结束日（YYYY-MM-DD）")
    endTime: str | None = Field(default="23:59", description="搜索窗结束时刻（HH:mm）")
    # 条件树按 passthrough 而非建模：上游有 30+ 条件类，各自 params 形状/validate/compile 都不同，
    # 在此重编一遍等于造第二份真值源，上游一加条件类就烂；vendored compileQimenTree 会跑各叶子自己的
    # validate 抛本地化错误。可发现性放 agent_guidance（列条件类键与必填 params）。
    conditions: Any | None = Field(
        default=None,
        description=(
            "条件树。组节点 {kind:'group', joiner:'all'|'any'|'xor', negate?, children:[…]}；"
            "叶节点 {type:'<条件类键>', params:{…}}。条件类键与参数见本工具的 agent_guidance。"
        ),
    )
    maxSpanDays: int | None = Field(
        default=None,
        description="搜索窗跨度上限（天），缺省即本工具硬上限；只能**调低**，给更大的值不会放宽。",
    )
    maxHits: int | None = Field(default=None, description="命中区间数上限，缺省 1000")
    zeriSnapshotMaxRows: int | None = Field(default=None, description="清单行数10-500(缺省60)")
    zeriSnapshotExplainRows: int | None = Field(default=None, description="判读树行数0-20(缺省3)")


class TianxingInput(BirthInput):
    """天星择日·征象搜索：在时间窗内扫出满足西占征象条件的时段。

    lat/lon/zone/hsys/zodiacal 复用 BirthInput —— 它们就是**搜索盘**的坐标与口径，不另起一套词汇。
    date/time 是 [起盘信息] 展示的锚点时刻，缺省取窗口起点。
    """
    hsys: int | None = 0  # 上游 TianxingElectionMain.js:66/81 出厂种子 hsys 0

    # 后端 ScanContext 实读 partileDef（election_scan.py:367），白名单也一直带着它，
    # 唯独 schema 没声明 —— 能用、agent 看不见。
    partileDef: str | None = Field(default=None, description="精确相位(partile)判定：same_degree（缺省）等。")
    startDate: str | None = Field(default=None, description="搜索窗起始日（YYYY-MM-DD）")
    startTime: str | None = Field(default="00:00", description="搜索窗起始时刻（HH:mm）")
    endDate: str | None = Field(default=None, description="搜索窗结束日（YYYY-MM-DD）")
    endTime: str | None = Field(default="23:59", description="搜索窗结束时刻（HH:mm）")
    pos: str | None = Field(default=None, description="地点显示名，进 [征象搜索配置] 段")
    conditions: Any | None = Field(
        default=None,
        description=(
            "征象条件树。组节点 {kind:'group', joiner:'all'|'any'|'xor', negate?, children:[…]}；"
            "叶节点 {type:'<条件类键>', params:{…}}。32 个条件类键见本工具的 agent_guidance。"
        ),
    )
    precision: str | None = Field(default=None, description="扫描精度，缺省 minute")
    explainAt: str | None = Field(
        default=None,
        description=(
            "单时刻判据判读（YYYY-MM-DD HH:mm[:ss]）：对该时刻逐叶判读条件树（与扫描求值器绝对同源），"
            "加产 [单时判读] 段——每叶列「设定/实际 ✓✗」。用于回答「为什么这个时刻中/不中选」。"
            "Explain one moment leaf-by-leaf against the condition tree (adds a [单时判读] section)."
        ),
    )
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="古典口径直通（cazimiOrb/combustOrb/vocMode/termsVariant/triplicity…）。",
    )
    zeriSnapshotMaxRows: int | None = Field(default=None, description="清单行数10-500(缺省60)")
    zeriSnapshotExplainRows: int | None = Field(default=None, description="判读树行数0-20(缺省3)")


class QizhengElectionInput(BirthInput):
    """七政择日动盘（果老「择日双轮」headless 版）。

    date/time/zone/lat/lon 复用 BirthInput —— 它们就是**候选择日时刻**的坐标，非出生盘。
    三个动作共用一套入参：pan 用全部；eclipses 只用 date/zone(+kind/count)；
    azimuthsearch 用 date/time/zone/坐标(+body/targetAz/days)。
    """
    hsys: int | None = 0  # 七政择时展示盘随七政盘：恒整宫（同 GuoLaoInput）

    action: str | None = Field(
        default="pan",
        description=(
            "pan=十一曜动盘（黄道地支度/二十四山位/地平高度/顺逆）| eclipses=未来日月食搜索 | "
            "azimuthsearch=星曜到达目标罗盘方位的时刻搜索"
        ),
    )
    pos: str | None = Field(default=None, description="地点显示名，进快照的起盘信息行")
    height: float | None = Field(default=None, description="海拔（米），缺省 0")
    nodeType: str | None = Field(default=None, description="罗计口径：mean（缺省）|true")
    lilithType: str | None = Field(default=None, description="月孛口径：mean（缺省）|true")
    ayanamsaDeg: float | None = Field(default=None, description="恒星制岁差回加度（回归制传 0/不传）")
    eleLifeMode: str | None = Field(default=None, description="命度起法：sunrise（缺省）|sunset|custom")
    eleLifeCustomTime: str | None = Field(default=None, description="eleLifeMode=custom 时的起命时刻 HH:mm:ss")
    extraBodies: list[dict[str, Any]] | None = Field(
        default=None,
        description=(
            "外圈透传星（照上游果老盘惯例：紫炁/天海冥从流年盘取黄经黄纬传入）："
            "[{id,label,lon,lat?,speed?}…]，后端按 lon/lat 算地平方位。"
        ),
    )
    plate: str | None = Field(default=None, description="二十四山盘别：di=地盘（缺省）|tian=天盘(+7.5°)|ren=人盘(−7.5°)")
    ziZheng: str | None = Field(default=None, description="子正口径：true=真北（缺省）|magnetic=磁北（配 declination）")
    declination: float | None = Field(default=None, description="磁偏角（东偏为正；仅 ziZheng=magnetic 时套用）")
    kind: str | None = Field(default=None, description="eclipses 专用：solar=日食（缺省）|lunar=月食")
    count: int | None = Field(default=None, description="eclipses 专用：搜索数量（缺省 8，上限 24）")
    targetAz: float | None = Field(default=None, description="azimuthsearch 专用：目标罗盘方位 0-359.9（0=北顺时针）")
    days: int | None = Field(default=None, description="azimuthsearch 专用：向后搜索天数（缺省 3，上限 30）")
    body: str | None = Field(default=None, description="azimuthsearch 专用：星曜中文标签 日月金木水火土（缺省 日）")


class HoraryInput(BirthInput):
    # 长尾旋钮：照常声明（校验 + MCP 扁平面收顶层键），不进 tools/list 广告层（mcp_schema.advertise_hidden_fields）。
    ADVERTISE_HIDDEN: ClassVar[frozenset[str]] = frozenset(
        {"sincerityConfirmed", "confirmYouthMatch", "isEventChart", "questionText", "castingCamp"}
    )
    # 卜卦 (horary): the chart is cast at the QUESTION moment (date/time/place = when the question was asked).
    # category picks the quesited house — 引擎词表 CATEGORY_DEF 20 类（general/wealth/family/property/father/mother/
    # pregnancy/health/marriage/lawsuit/theft/death/travel/career/hope/enemy/message/lost/lost_animal/trade；
    # unknown → general）。全表与中文名见 agent_guidance。
    category: str | None = "general"
    # 流派档（horarySchools.js HORARY_SCHOOLS 七档）：classical(默认)/renaissance/strict/sequence/hellenistic/medieval/modern。
    # 流派同时决定**起盘字段**（上游 horaryBackendFields：宫制/界系/三分集/福点反转/星群，页面 HoraryMain.js:543）与判读口径。
    school: str | None = Field(default=None, description="卜卦流派七档（缺省 classical；定宫制界系与判读，见 guidance）。")
    # 星群随流派（modern=0 含三王星，其余 1）；显式给值压过流派。
    tradition: bool | None = None
    predictive: bool | None = False
    # 卜卦七档参数谱（星阙 v3.6.0，界表勘误 + 判读叠层二期）。上游 horarySchools.js 的 HORARY_PARAM_SPEC
    # 中 hsys/termsVariant/geminiBoundEmended/tradition 标 sendToBackend：缺省随流派档，显式给值压过流派
    # （与上游高级面板 horaryOverrides 同语义，同时进起盘与判读）。
    hsys: Any | None = Field(default=None, description="宫制：缺省随流派（经典=2 Regiomontanus/希腊化=0/中世纪=1/现代=3）；显式值优先。")
    termsVariant: Any | None = Field(default=None, description="界系 0–3（缺省随流派，见 guidance）。")
    geminiBoundEmended: Any | None = Field(default=None, description="双子界表勘误开关（v3.6.0 修订）。")
    considerationsMode: Any | None = Field(
        default=None, description="定盘考量(considerations before judgment)硬度：warn / strict / lenient / ignore。"
    )
    lotsSet: Any | None = Field(default=None, description="阿拉伯点集：minimal（默认）/ core15。")
    # 定盘自评（上游卜卦左栏三勾选，HoraryMain.js:487-497 → runHorary opts）：影响 [定盘考量] 第 18 条（无诚意）与
    # 命度早晚 / 事件盘两条的「已救济」判定。问句与阵营进 [定盘考量] 段首两行（buildHorarySnapshot 第 3 参）。
    sincerityConfirmed: bool | None = Field(default=None, description="问题真诚自评：缺省 true（上游缺省勾选）；false→定盘考量第18条命中。")
    confirmYouthMatch: bool | None = Field(default=None, description="年轻体貌合上升（救济命度过早）：缺省 false。")
    isEventChart: bool | None = Field(default=None, description="事件盘（客观时刻，救济命度过晚）：缺省 false。")
    questionText: str | None = Field(default=None, description="所问之事原文（进 [定盘考量] 段）。")
    castingCamp: str | None = Field(default=None, description="起盘阵营：astrologer（缺省）/querent/midpoint；时地须已按阵营给。")
    # 判读层参数覆写（HORARY_PARAM_SPEC 全部键，压过流派档；sendToBackend 四键 + tripSystem 同时改起盘）。
    # 键名以引擎自带词表为准；不认识的键会原样回执在 data.params_ignored，不静默吞。
    # 顶层全局古典键（cazimiOrb/combustOrb/underBeamsOrb/vocMode/vocIncludeOuter/viaCombustaVariant/partileDef/
    # antisciaOrb/starOrb/starOrbMode/combustMitigateSameSign/antiscia）进判读**全局层**（流派绑定之下，上游
    # judgeLayerOverrides 同口径）；顶层 triplicity/lotReversal 不作用于卜卦盘（流派绑定，另有告警）。
    # 🔴 receptionMode / almutenScheme 两个字段已删：引擎词表里**根本没有这两个名字**（近邻是
    # receptionForHardAspects / receptionPerfection / accidentalMode，语义并不等同）。
    # 它们是凭空发明的旋钮，声称了三个版本、一次都没生效过。
    options: dict[str, Any] | None = Field(
        default=None, description="判读层参数覆写 {key: value}；键取自引擎词表 HORARY_PARAM_SPEC。"
    )


class ElectionInput(BirthInput):
    hsys: int | None = 0  # 上游 ElectionMain.js:100 出厂种子 { tradition: 1, zodiacal: 0, hsys: 0 }（:121 回退亦 0）
    ADVERTISE_HIDDEN: ClassVar[frozenset[str]] = frozenset(
        {"tradeSide", "talismanStar", "surgeryPart", "surgeryPartOpposite", "crisisBase"}
    )
    # 择日 (electional): the chart is cast at a CANDIDATE moment (date/time/place = the time being evaluated).
    # topicId picks the rule pack + hard flags: marriage/business/move_in/buy_property/trade/buy_car/contract/
    # surgery/travel/job_hunt/... (TOPIC_MASTER 37 类；unknown → marriage；全表见 agent_guidance).
    topicId: str | None = "marriage"
    tradition: bool | None = True
    predictive: bool | None = False
    # 宫制：缺省随流派档联动（westernSchools.js hsys：hellenistic/modern_revival=0、persian=1、renaissance=2；
    # modern_main 不联动 → 页面缺省 0）；显式给值压过流派。
    hsys: int | None = Field(default=None, description="宫制：缺省随流派（hellenistic=0/persian=1/renaissance=2，现代主流=0）；显式值优先。")
    # 择日口径（星阙 v3.6.0）：流派轴 + 13 个判读层参数，全部取自上游 electionParams.js。
    # 🔴 此前这里挂着 dignityScheme / starSet / medicalCritical / hourRuler / returnCharts /
    # primaryDirections / natalCompare / mundaneCompare / lotsSet / considerationsMode 十个字段，
    # 与 ELECTION_PARAM_SPEC 的 13 键**零重合**，且 skill 与上游全树都无人消费 —— 注释一边引着
    # 正确出处、字段一边写着发明的名字，声称了三个版本一次都没生效。诚实起见整批删除。
    # 顶层全局古典键（cazimiOrb/vocMode/partileDef/antisciaOrb/starOrb… 同卜卦）进判读**全局层**（流派口径之下）。
    school: Any | None = Field(
        default=None,
        description="择日流派档：modern_main（默认）/ hellenistic / persian / renaissance / modern_revival。",
    )
    options: dict[str, Any] | None = Field(
        default=None,
        description=(
            "判读层参数覆写 {key: value}；键取自引擎词表 ELECTION_PARAM_SPEC："
            "termsVariant / tripSystem / orbProfile / vocMode / bodySet / mansionAnchor / "
            "marriageTradition / querentGender / erosConstruction / lotsReversal / "
            "firdariaNightOrder / zrLot / pdTimeKey。不认识的键原样回执在 data.params_ignored。"
        ),
    )
    # 本命合参（上游「选本命盘」）：给了才产 [本命合参] 与 [回归与主限]（择日前最近日返/月返 + 择日日期 ±240 日
    # 主限命中，主限时间钥匙随 options.pdTimeKey）。缺 date/time/zone/lat/lon 任一 → tool.election_natal_missing_fields。
    natal: dict[str, Any] | None = Field(
        default=None,
        description="本命出生资料 {date,time,zone,lat,lon[,ad]}：加产 [本命合参] 与 [回归与主限]（日/月返 + 主限命中）。",
    )
    # 用事专属输入（上游左栏按用事显示的控件，ElectionMain.js:376-440 → runElection opts）：只在对应用事的规则包里
    # 生效，给了却不作用会进 warnings。值域锚定引擎词表（认不出的报错）。
    tradeSide: str | None = Field(default=None, description="买卖方向（trade）：sell=强己方 / buy=强货主方；缺省不指定。")
    talismanStar: str | None = Field(default=None, description="护符主星（talisman）：sun/moon/mercury/venus/mars/jupiter/saturn。")
    surgeryPart: str | None = Field(default=None, description="手术部位星座（surgery）：aries…pisces（按星座主管身体部位）。")
    surgeryPartOpposite: bool | None = Field(default=None, description="部位禁忌延及对宫（surgery）；缺省不延。")
    crisisBase: Any | None = Field(default=None, description="病始日期 YYYY-MM-DD（surgery/medication）：产 [危象日参照]。")
