"""推运族快照：[起盘信息] / [当前时点] / [方法说明] 与各推运技法（年龄点…波斯向运、印度校正、法达 / 十年期、返照 / 太阳弧 / 小限）。"""
from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from horosa_skill import predictive_text as _ptext
from horosa_skill.engine.decennials import (
    DECENNIAL_CALENDAR_ACTUAL,
    DECENNIAL_DAY_METHOD_HEPHAISTIO,
    DECENNIAL_ORDER_CHALDEAN,
    DECENNIAL_START_MODE_SECT_LIGHT,
)
from horosa_skill.exports.registry import AI_EXPORT_PRESET_SECTIONS
from horosa_skill.service import _clock
from horosa_skill.civil_calendar import (
    _MS_PER_DAY,
    _UNIX_EPOCH_JDN,
    _civil_date_str_of_jdn,
    _civil_wall_ms,
    _civil_wall_ms_of_moment,
    _greg_ymd_of_jdn,
)
from horosa_skill.service._common import (
    _finite_number,
    _join_lines,
    _render_snapshot_text,
)
from horosa_skill.service.text.astro_core import (
    ASTRO_TEXT_MAP,
    PLANET_HOUSE_INFO_NOTE,
    _astro_msg,
    _astro_msg_with_house,
    _build_aspect_section,
    _build_house_cusp_lines,
    _build_info_section,
    _build_star_and_lot_position_lines,
    _chart_wrap_from_response,
    _planet_label,
    _round3,
    _top_level_chart_wrap,
)

# 星运族 [方法说明]：每键 2-4 行公开通行机理与读法（零书名零章节）。键=导出 technique 名。
_PREDICTIVE_METHOD_NOTES: dict[str, list[str]] = {
    "primarydirect": [
        # 上游 astroAiSnapshot.js:2007-2012（v3.13.0 +黄纬 / 日期两行）。
        "主限法：天体按周日运动(赤经/方位弧)推进,约 1 度合 1 年;迫星抵达应星的弧量换算年龄,用于判大事应期。",
        "读法：表中每行=一次抵达事件;以应星宫职与迫星性质合断吉凶主题。",
        "黄纬：黄道制里迫星相位点缺省在黄道上(黄纬 0),「相位点黄纬」可改为合冲带黄纬 / 余弦递减 / 线性递减 / 按宫位(按宫位 = 相位点离黄道垂足的宫位偏移与迫星本体相同,只对 Placidus / Regiomontanus / Campanus / Topocentric / Horizontal / Koch / Alcabitius / Meridian 起作用;见扩展设置行);应星用自身黄纬。",
        "日期：整年取第 N 个周年(出生时刻按公历加 N 年)、年内零头按「日期年长」折成天数(默认到下一周年日的实际天数,或 365 / 366 定长年,两档最多差 1 天,见扩展设置行);2 月 29 日生于平年,主限周年取 2 月 28 日(小限 / 太阳弧 / 行星弧年表的行取 3 月 1 日,同一周岁两表可差一天)。",
    ],
    "zodialrelease": [
        # 上游 astroAiSnapshot.js:2029-2033 [Q-363/T-344]：缺省基点=福点，期长=各座守护星小年（非行星大年）。
        "黄道释放：自所选基点(默认幸运点,可改精神点等)所在星座起,按各星座守护星小年逐座、逐层释放,划分人生篇章(一级期)与子期(二级期)。",
        "读法：期主星及其本命状态定该段主题;跳宫(LB)为重大转折;与幸运点十度关系看顺逆。",
    ],
    "firdaria": [
        "法达大限：波斯行星期法,日生盘自太阳、夜生盘自月亮起,诸星依序各主政若干年,内再均分子期。",
        "读法：主期星定大主题、子期星定阶段事项,两星本命状态与彼此关系定吉凶成色。",
    ],
    "distributions": [
        # 上游 astroAiSnapshot.js:2022-2027（v3.13.0 重写：发放点 / 时间算法 / 年长 / 年限四项可选，伙伴星）。
        "界推运(分配法)：周日运动把黄道各度依次带上地平,发放点(默认上升)顺黄道走过其后各界,每一界一期,界主星即该期的\"分配星\";界表用当前全局界系设置。",
        "时间：上升时间法(古典)每度年数 = 该星座在出生纬度的上升时间 ÷ 30;斜升差法逐度取斜升差;Qisma 每度 1 年。伙伴星 = 发放点最近经过的七星本体或其左右 60° / 90° / 120°、180° 相位点,各管到下一点为止。",
        "读法：分配星定该期大方向,伙伴星定其中的具体境遇;换界、换伙伴即换阶段。",
    ],
    "agepoint": [
        # 上游 astroAiSnapshot.js:2028-2033（v3.13.0 重写：推进方式 / 事件 / 年长 / 年限四项可选）。
        "年龄推进点：年龄点自上升点起逐宫顺行,每宫 6 年、72 年回到上升。Koch 宫档在每宫内按黄道跨度匀速(宽宫走得快);等速档自上升每年 5°(= 上升起等宫)。",
        "事件：年龄点经过本命点(日月五星、天王 / 海王 / 冥王、北交、福点、四轴)或其左右六合 / 四分 / 三分与冲的位置,按精确穿越岁数列出;只报合档只看合七星。",
        "读法：落宫定人生课题场域,事件岁数标记该年龄的关键主题;合与冲最强,四分次之,三分 / 六合较顺。",
    ],
    # [Q-106/T-10] 星运三页上线（上游 astroAiSnapshot.js:2045-2057 逐字；ASCII 逗号/分号亦照抄）
    "ephemeris": [
        "星历：以本命盘地点与时区列出区间内行星入座、留与顺逆转向、朔望弦与食相,并按容许度筛出行运触发本命点的时刻。",
        "读法：入座换宫定阶段主题,留点前后事件易停滞反复,食相落宫标重大转折;行运触发行只列精确时刻,结合本命点性质判吉凶。",
    ],
    "returntimeline": [
        "回归轴：逐年列太阳返照(太阳回本命度)与该年首个月亮返照时刻及两盘上升点。",
        "读法：返照上升落座定该年/该月主色,上升与本命宫位的对应指示焦点领域;多年并列可见上升轮转的节律。",
    ],
    "prenatalsyzygy": [
        "产前朔望：自出生时刻回溯最近的朔(日月合)或望(日月冲),取更晚者为产前朔望,以该时刻、出生地排盘。",
        "读法：朔取合相度、望取地平之上发光体度为「取度」;该度及其主星为古典寿主/命主判定的重要候选,产前盘星体位置为本命的先天背景。",
    ],
    "profection": [
        "小限(年限)：每满一岁命宫顺推一宫,该宫为当年小限宫,其宫主星为年主星。",
        "读法：年主星本命状态与流年动态定当年吉凶;小限宫宫职指示当年主战场。",
    ],
    "solararc": [
        "太阳弧向运：全盘诸点按太阳年均约 1 度的弧量整体推进。",
        "读法：推进点与本命点形成的入相位(容许度约 1 度)标记事件年份;点性组合定事件性质。",
    ],
    "solarreturn": [
        "太阳返照(日返)：太阳每年回归本命黄经时刻起盘,该盘统领此后一个太阳年。",
        "读法：返照盘上升与其主星定年度基调;返照盘行星落本命宫位看事项落点。",
    ],
    "lunarreturn": [
        "太阴返照(月返)：月亮每月回归本命黄经时刻起盘,统领此后一个太阴月。",
        "读法：与日返同理,颗粒度为月;月亮状态与四轴最要紧。",
    ],
    "givenyear": [
        # 上游 astroAiSnapshot.js:2076-2080 [Q-170/T-109]：perpredict 给的是实时天象盘，不是二次推运盘。
        "指定年天象盘：按所给年份的时刻与地点起一张实时天象盘,与本命对照。",
        "读法：天象盘行星落本命宫位与两盘相位定该年主题。",
    ],
    "decennials": [
        "十年大运(Decennials)：希腊期法,诸星依序轮值主政各 129 个月(约 10.75 年),内按行星小年分子期。",
        "读法：主政星+子期星组合定阶段主题;换主政为人生大节点。",
    ],
    "planetaryages": [
        "行星年龄段：人生依序由月亮/水星/金星/太阳/火星/木星/土星主政固定年岁段(4/10/8/19/15/12/30 年制式)。",
        "读法：当前年龄所处主政星定人生阶段基调;主政星本命状态定该阶段顺逆。",
    ],
    # [#80] 回归黄道二次推运（上游 astroAiSnapshot.js:2087-2090 逐字）
    "prog": [
        "二次推运:回归黄道下的推运(二次推运一日抵一年、三次推运与小推运同族),叠加本命对照。",
        "读法：推运位与本命位的星座宫位迁移及相位,合冲刑三分为主,应期看推运点行至本命点。",
    ],
    "vedicprog": [
        "恒星推运：以恒星黄道计的推运(含二次推运一日抵一年),叠加本命对照。",
        "读法：推运位与本命位的星座宫位迁移及相位,按恒星制口径判断。",
    ],
    "jaynesprog": [
        "赤纬推运：只看推运星与本命星的赤纬平行(同纬同侧)与反平行(同纬异侧)。",
        "读法：平行视作强合相、反平行视作强对冲;成对年份即应期。",
    ],
    "planetaryarc": [
        "行星弧向运：同太阳弧原理,但以选定行星的推进速率作弧量整体前移。",
        "读法：弧主星的性质给全部触发事件染色;入相位年份为应期。",
    ],
    "persiandirected": [
        "波斯向运：中世纪波斯法,诸点按约 1 度/年向前推进与本命点会照。",
        "读法：向运点与本命点的相位事件按年龄排布;近期命中(距今最近)优先解读。",
        "指定日期：传 datetime=YYYY-MM-DD 可整铸该日向运盘(「指定日期向运盘」段:directed 点位+向运→本命命中);rateKey/direction 可换速率与顺逆。",
    ],
    "yearsystem129": [
        # 上游 astroAiSnapshot.js:2096-2101（v3.13.0：引擎改前端 utils/yearSystem129，子限三种铺法）。
        "129 年系统：七星各管其小年(土30木12火15日19金8水20月25,合 129 年);主限长度 = 小年 × 年长,七星按所选次序(本命黄经序或迦勒底序)从起始星铺开。",
        "子限从本主限星起按同一次序:日数法每颗 = 子星小年 × ⌊2.5 × 主星小年⌋ 日(一轮不填满主限,余下时段无子限);比例法 = 主限 × 子星小年 ⁄ 129;七等分 = 主限 ⁄ 7。",
        "读法：主限星定大阶段,子限星定小阶段,起讫日期定应期窗口。",
    ],
    "balbillus": [
        # 上游 astroAiSnapshot.js:2102-2107（v3.13.0：主限 = N′ ×(360 − d)⁄360，子限 ÷12 / 铺法可选）。
        "主/子限期法(Balbillus)：罗马期法,主限长度 = N′ ×(360 − d)⁄ 360 年,d 为本命星所在度(黄经取整加一)离其擢升度的整度角距,N′ = 水20 / 金8 / 木12 / 土30 / 日18 / 月24 / 火14;七星按本命黄经序自起始星铺开。",
        "子限从父期主星起按同一次序,每颗 = 该星上一层时长 ÷ 12(第三层 ÷ 144);一轮合计不到父期,铺法见快照首行(一轮不填满 / 循环到父期末 / 末段填满)。",
        "读法：主限星与子限星组合断该段主题;换限日期为节点。",
    ],
    "triplicityrulers": [
        # 上游 astroAiSnapshot.js:2122-2126 [Q-170/T-109]：取当值光体所在座的三分性，非命度。
        "三分主星推运：当值光体(昼生取太阳、夜生取月亮)所在星座的三分性三主星(日/夜/伴)依序主管人生前/中/后三段。",
        "读法：各段主星的本命状态(庙旺陷落/宫位/受克)直接定该人生阶段的整体成色。",
    ],
    "keypoints": [
        # 上游 astroAiSnapshot.js:2127-2132 [Q-170/T-109]：位置数 k=自释放点第几座 + 专用小年表倍数激活。
        "数字相位推运(120 关键点)：每颗星取「自释放点起第几个星座」k(1–12),年龄为 k 的倍数时该星被激活;另按各星专用小年(3/8/18/5/7/9/13)的倍数激活一次。",
        "读法：命中即激活年;k 越小复现越密;结合被激活点的本命性质定主题。",
    ],
    "lunationphase": [
        # 上游 astroAiSnapshot.js:2119-2123（v3.13.0：推运日月差按星历逐日精算）。
        "月相推运：二次推运(一日为一年)的日月黄经差约 29.5 年走完一轮朔望循环,分八相;N 岁的推运日月差 = 出生后第 N 天真实的月日黄经差,各相起始岁数按星历精算。",
        "读法：新月=起始、上弦=建设、满月=显化、下弦=释放;当前相定人生大节奏。",
    ],
    "extrareturns": [
        # 上游 astroAiSnapshot.js:2124-2128（v3.13.0：三体 + 黄道 / 平真交点随本盘）。
        "多重回归：土星 / 木星 / 月交回到本命黄经的整回归时刻表(第 n 回 = 走满 n 圈;逆行同一回三过逐过列出;黄道与平 / 真交点随本盘)。",
        "读法：整回归=大周期重启(如土星回归约 29.5 岁);两次回归之间可自行取中点作阶段参照,表内不列。",
    ],
}


def _predictive_birth_source(response: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """[起盘信息]/[本命盘配置] 生辰行的取源：本命 /chart 响应（{params, chart}）。

    优先 runner 挂上的 natalChart；其次响应本身就是 /chart（balbillus/persiandirected 等）；都没有时
    降级为「只用载荷」（出生时间/经纬度/时区/黄道/宫制，**不猜昼夜**）。
    """
    def _is_chart_response(value: Any) -> bool:
        return isinstance(value, dict) and isinstance(value.get("chart"), dict) and isinstance(value.get("params"), dict)

    if isinstance(response, dict):
        # runner 结果常把 /chart 原响应放在 raw 下（progextra/persiandirected/yearsystem129 …）。
        for candidate in (response.get("natalHeader"), response.get("natalChart"), response, response.get("raw")):
            if _is_chart_response(candidate):
                return candidate
        raw = response.get("raw")
        if isinstance(raw, dict) and _is_chart_response(raw.get("natalChart")):
            return raw["natalChart"]
    return _ptext.payload_chart_wrap(payload)


def _predictive_setup_section_text(technique: str | None, payload: dict[str, Any], response: dict[str, Any]) -> str:
    """星运族的 [起盘信息] 段（上游 = buildPredictiveBirthHeaderLines(chartObj)，位于段首）。

    上游 utils/astroAiSnapshot.js:1956-1998：A 组零盘境键（agepoint/distributions/extrareturns/
    persiandirected/balbillus/…）用它自成段——出生时间(+星期)/真太阳时/经纬度/时区/黄道/宫制/盘型。
    旧实现用 buildBaseInfoLines 口径，且对无盘响应（agepoint 等）按 isDiurnal 缺省一律写「夜生盘」——
    日生盘也标夜生盘；现在 runner 补拉本命盘，拿不到盘时不出「盘型」行（不猜）。
    """
    # 门控按「该键的 preset 是否真列了 [起盘信息]」，而不是按「是不是星运键」——primarydirect /
    # primarydirchart / zodialrelease 同属星运族但上游段首是 [出生时间]，多塞一段会变成 unknown 段。
    # 这样写也自洽：以后 preset 增删该段，无需再回来改名单。
    if not _PREDICTIVE_METHOD_NOTES.get(technique or ""):
        return ""
    if "起盘信息" not in (AI_EXPORT_PRESET_SECTIONS.get(technique or "") or []):
        return ""
    lines = _ptext.build_predictive_birth_lines(_predictive_birth_source(response, payload))
    if not lines:
        return ""
    return _render_snapshot_text([("起盘信息", "\n".join(lines))])


def _predictive_common_sections_text(
    technique: str | None, payload: dict[str, Any], extra_lines: list[str] | None = None
) -> str:
    """星运族公共两段：[当前时点](导出时刻+盘主年龄) + [方法说明](机理与读法)。

    非星运键返回空串(零变化)。

    注：早先这里写着「[起盘信息]等价段各技法快照已有,不重复」——**该说法已过期**。实测 10 个星运键
    (agepoint/balbillus/distributions/extrareturns/keypoints/lunationphase/persiandirected/
    planetaryages/triplicityrulers/yearsystem129) 的快照根本没有这一段，而上游 preset 里有
    (= buildBaseInfoLines)。故另由 `_predictive_setup_section_text` 前置补出。
    """
    notes = _PREDICTIVE_METHOD_NOTES.get(technique or "")
    if not notes:
        return ""
    now = _clock.now()
    moment_lines = [f"导出时刻：{now.strftime('%Y-%m-%d %H:%M')}"]
    birth_text = f"{payload.get('date') or ''} {payload.get('time') or ''}".strip()
    if birth_text:
        try:
            birth_dt = datetime.strptime(birth_text[:16].replace("/", "-"), "%Y-%m-%d %H:%M")
        except ValueError:
            try:
                birth_dt = datetime.strptime(birth_text[:10].replace("/", "-"), "%Y-%m-%d")
            except ValueError:
                birth_dt = None
        if birth_dt is not None:
            # 上游 v3.12.0 birthInstantMsInZone(params.birth, params.zone)：出生钟面按**本盘时区**解读（此前按本机时区，
            # 本机与盘不在同一时区时年龄差出时差）；「导出时刻」仍是本机钟面（上游 new Date()）。
            try:
                birth_instant = _birth_instant_in_zone(birth_dt, payload.get("zone"))
                age = (now.astimezone() - birth_instant).total_seconds() / (365.2425 * 24 * 3600)
            except (OverflowError, OSError, ValueError):
                age = (now - birth_dt).total_seconds() / (365.2425 * 24 * 3600)
            if -1 < age < 200:
                # 上游 `Math.round(age * 100) / 100`（半数向 +∞，整数不带 .0）。
                moment_lines.append(f"盘主当前年龄：{_ptext.js_str(_ptext.js_round2(age))} 岁")
    # 上游 buildCurrentMomentLines(chartObj, extraLines)（astroAiSnapshot.js:2002-2018）：各键 timeline 定位行
    # （当前年龄点 / 当前分配星 / 当前向运年龄 / 当前所处…）由 builder 用自己的时间轴算好，追加在基线两行后。
    for line in extra_lines or []:
        if line:
            moment_lines.append(f"{line}")
    # [当前时点] 按该键 preset 门控（与 [起盘信息] 同理）：目标时刻型 5 法（profection/solararc/三返照）上游
    # buildPredictiveSnapshotText 只出 [方法说明]、preset 也不列 [当前时点]（aiExport.js:641-645）。
    if "当前时点" not in (AI_EXPORT_PRESET_SECTIONS.get(technique or "") or []):
        return _render_snapshot_text([("方法说明", "\n".join(notes))])
    return _render_snapshot_text([("当前时点", "\n".join(moment_lines)), ("方法说明", "\n".join(notes))])


def _ap_name(value: Any) -> str:
    """上游 AstroAgePoint.js:19 apName / AstroDistributions.js:21 distName：空 → '-'，否则 AstroTxtMsg。"""
    if value is None or value == "":
        return "-"
    return _ptext.astro_txt(value)


# 年龄推进点 / 界推运的快照（上游 v3.13.0 重写）由 vendored 上游 buildAgePointSnapshotFromResult /
# buildDistributionsSnapshotFromResult 出（horosa-core-js progextra FROM_RESULT 分支；runner 见
# service/runners/predictive.py::_run_predict_result_tool）。此前这里是两份 Python 手抄移植，上游改写时零信号滞留。


def _aspect_label(deg: Any) -> str:
    mapped = ASTRO_TEXT_MAP.get(f"Asp{deg}")
    return mapped if mapped else f"{deg}°"


def _natal_birth_config_block(response: dict[str, Any], payload: dict[str, Any] | None) -> list[str]:
    """上游 [本命盘配置] 头（jaynes/vedic/planetaryarc 同形）：生辰裸行 + 星与虚点 + 宫位宫头。

    上游 AstroJaynesProgressions.js:59-66 / astroProgSnapshot.js:88-96 / AstroPlanetaryArc.js:62-72：
    `if(natalStars.length || natalHouses.length || natalBirth.length)` 才出段；生辰行在前（[YB v42]）。
    （星与虚点/宫位宫头两子块用本仓共享 line-builder——上游 v3.11 已把它们表化成 GFM 表，属西占公共件口径，
    由盘面族统一切换，这里不私自分叉。）
    """
    natal_wrap = _natal_chart_wrap(response)
    birth = _ptext.build_predictive_birth_lines(_predictive_birth_source(response, payload or {}))
    stars = _build_star_and_lot_position_lines(natal_wrap) if natal_wrap else []
    houses = _build_house_cusp_lines(natal_wrap) if natal_wrap else []
    if not (stars or houses or birth):
        return []
    block = ["[本命盘配置]", *birth]
    if stars:
        block.extend(["星与虚点", *stars])
    if houses:
        block.extend(["宫位宫头", *houses])
    return block


def _prog_parallel_row(p: dict[str, Any]) -> str:
    type_label = "反平行" if p.get("type") == "contraparallel" else "平行"
    return f"| {_ptext.astro_txt(p.get('a'))} | {type_label} | {_ptext.astro_txt(p.get('b'))} | {_ptext.js_fmt_num(p.get('orb'), 3)} |"


def _build_jaynesprog_snapshot_text(
    response: dict[str, Any],
    payload: dict[str, Any] | None = None,
    *,
    target_date: str = "",
    target_time: str = "12:00:00",
    minor_variant: str = _ptext.DEFAULT_MINOR_VARIANT,
) -> str:
    """逐字镜像上游 components/astro/AstroJaynesProgressions.js:33-117 buildJaynesProgSnapshotText。

    [Q-176/T-116b] 首行写「推至所选目标日期」；目标日期行写明目标日期→各法推运时刻的映射；
    [YB v42] 三法（二次/三次/小推运）全量各出 ◆ 小节 + 本命赤纬；[Q-180] 小推运写明月长档。
    """
    methods = [m for m in (response.get("methods") if isinstance(response.get("methods"), list) else []) if isinstance(m, dict)]
    sec = next((m for m in methods if m.get("method") == "secondary"), methods[0] if methods else None)
    parallels = sec.get("parallels") if isinstance(sec, dict) and isinstance(sec.get("parallels"), list) else []
    if not parallels:
        return _render_snapshot_text([("赤纬推运（Declination）", "（本盘无赤纬推运数据）")])
    lines = [
        "[赤纬推运（Declination）]",
        "赤纬推运：推运后看赤纬平行/反平行（下表为二次推运，推至所选目标日期）。",
        f"目标日期：{target_date} {target_time}（各法推运时刻=按该法折算，见各小节）",
    ]
    natal_block = _natal_birth_config_block(response, payload)
    natal_decls = [d for d in (response.get("natalDeclinations") if isinstance(response.get("natalDeclinations"), list) else []) if isinstance(d, dict)]
    if natal_block:
        lines.append("")
        lines.extend(natal_block)
        # [YB v42] UI 赤纬图有本命赤纬列 → ◆ 子题段内纯增（平行/反平行的本命侧参照）。
        if natal_decls:
            lines.extend(["", "◆ 本命赤纬", "| 点 | 赤纬 |", "| --- | --- |"])
            lines.extend(f"| {_ptext.astro_txt(d.get('id'))} | {_ptext.js_fmt_num(d.get('decl'), 2)}° |" for d in natal_decls)
    lines.extend(["", "[时段盘 赤纬平行/反平行]", "| 推运点 | 类型 | 本命点 | 误差 |", "| --- | --- | --- | --- |"])
    lines.extend(_prog_parallel_row(p) for p in parallels[:80] if isinstance(p, dict))

    def push_method_blocks(method: dict[str, Any], with_parallels: bool) -> None:
        label = _ptext.prog_method_tab(method)
        progressed = method.get("progressedDate") if isinstance(method.get("progressedDate"), dict) else {}
        when = progressed.get("datetime") or ""
        decls = [d for d in (method.get("declinations") if isinstance(method.get("declinations"), list) else []) if isinstance(d, dict)]
        if decls:
            lines.extend(["", f"◆ {label} 推运赤纬"])
            if when:
                lines.append(f"推运时刻：{when}")
            if method.get("method") == "minor":
                lines.append(f"月长算法：{_ptext.MINOR_VARIANT_LABEL.get(minor_variant) or minor_variant}")
            lines.extend(["| 点 | 赤纬 |", "| --- | --- |"])
            lines.extend(f"| {_ptext.astro_txt(d.get('id'))} | {_ptext.js_fmt_num(d.get('decl'), 2)}° |" for d in decls)
        rows = [p for p in (method.get("parallels") if isinstance(method.get("parallels"), list) else []) if isinstance(p, dict)]
        if with_parallels and rows:
            lines.extend(["", f"◆ {label} 赤纬平行/反平行", "| 推运点 | 类型 | 本命点 | 误差 |", "| --- | --- | --- | --- |"])
            lines.extend(_prog_parallel_row(p) for p in rows[:80])

    push_method_blocks(sec, False)
    for method in methods:
        if method is not sec:
            push_method_blocks(method, True)
    return "\n".join(lines).strip()


# 上游 components/astro/AstroPlanetaryArc.js:19 ARC_SOURCES（页面/挂载齿轮同值域）。
_ARC_SOURCES = ("Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Sun")


def _planetaryarc_default_datetime(now: datetime | None = None, *, zone: Any = None) -> str:
    """上游 AstroPlanetaryArc.js:49-53 todayStr(zone)：[Q-174/T-114] 缺省目标时刻 = 「明天此刻」（与页面构造期
    dt.addDate(1) 同律；函数名叫 today 但取的是 now+24h）。v3.12.0：给了本盘时区 → 按它取此刻（DateTime.nowForChart）；
    不给 = 本机钟面（原样）。"""
    if now is None:
        now = _now_for_chart(zone) if zone else _clock.now()
    return (now + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")


def _build_planetaryarc_snapshot_text(response: dict[str, Any], payload: dict[str, Any] | None = None) -> str:
    """逐字镜像上游 components/astro/AstroPlanetaryArc.js:53-99 formatArcSnapshot。

    段构成：[行星弧（Planetary Arc）]（仅引言）/ [本命盘配置]（生辰 + 星与虚点 + 宫位宫头）/
    [时段盘配置]（向运盘 星与虚点 + 宫位宫头）/ [相位]（| 向运星 | 相位 | 本命星 | 误差 | 表，≤120 行）。
    旧实现把相位表塞在主段、[相位] 段另写「行运X 与 本命Y」句式——两段都与上游不同形。
    """
    chart = response.get("chart") if isinstance(response.get("chart"), dict) else {}
    aspects = chart.get("aspects") if isinstance(chart.get("aspects"), list) else None
    if aspects is None:
        return _render_snapshot_text([("行星弧（Planetary Arc）", "（本盘无行星弧数据）")])
    lines = [
        "[行星弧（Planetary Arc）]",
        "行星弧(默认月亮弧)：以所选天体的二次推运移动量为弧推进全盘，看向运星对本命的相位。",
    ]
    natal_block = _natal_birth_config_block(response, payload)
    if natal_block:
        lines.append("")
        lines.extend(natal_block)
    predictive_wrap = _predictive_chart_wrap(response)
    arc_stars = _build_star_and_lot_position_lines(predictive_wrap)
    arc_houses = _build_house_cusp_lines(predictive_wrap)
    if arc_stars or arc_houses:
        lines.extend(["", "[时段盘配置]"])
        if arc_stars:
            lines.extend(["星与虚点", *arc_stars])
        if arc_houses:
            lines.extend(["宫位宫头", *arc_houses])
    lines.extend(["", "[相位]", "| 向运星 | 相位 | 本命星 | 误差 |", "| --- | --- | --- | --- |"])
    count = 0
    for row in aspects:
        if not isinstance(row, dict):
            continue
        for obj in row.get("objects") or []:
            if count >= 120 or not isinstance(obj, dict):
                continue
            delta = obj.get("delta")
            delta_text = _ptext.js_str(_ptext.js_round(float(delta) * 1000) / 1000) if isinstance(delta, (int, float)) else ""
            lines.append(
                f"| {_ptext.astro_txt(row.get('directId'))} | {_ptext.asp_txt(obj.get('aspect'))} | "
                f"{_ptext.astro_txt(obj.get('natalId'))} | {delta_text} |"
            )
            count += 1
    return "\n".join(lines).strip()


# 托勒密人生七阶 (Ports of Man) — fixed age bands, each ruled by a classical planet (= 星阙 PLANETARY_AGES).
_PLANETARY_AGES = [
    ("Moon", 0, 4), ("Mercury", 4, 14), ("Venus", 14, 22), ("Sun", 22, 41),
    ("Mars", 41, 56), ("Jupiter", 56, 68), ("Saturn", 68, None),
]


# 上游 utils/planetaryAges.js:14-23 YEAR_BAND_ORDER（迦勒底序，土→月）。
_YEAR_BAND_ORDER = ("Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon")


def _full_years_between(birth: Any, when: datetime) -> int | None:
    """上游 moment(now).diff(birth,'years',true) 的整数部分（按月日时逐级比，= 日历周岁）。

    moment 以「生日 + 整月数」为锚，月末钳位：2/29 生人在平年的锚是 2/28（当天即满岁）。
    v3.12.0 planetaryAges.parseBirthMoment = civilMoment.birthMomentOfChart：出生日经民用历单源读（公元前 / 1582 以前
    儒略历 / 五位年），moment 里装的是**同一天**的外推格里历年月日——所以这里先换到外推格里历（天文年）再按月日比。
    """
    parts = _civil_birth_greg_parts(birth)
    if parts is None:
        return None
    b_year, b_month, b_day, b_hour, b_minute, b_second = parts
    years = when.year - b_year
    anchor_day = b_day
    if b_month == 2 and b_day == 29 and not (when.year % 4 == 0 and (when.year % 100 != 0 or when.year % 400 == 0)):
        anchor_day = 28
    if (when.month, when.day, when.hour, when.minute, when.second) < (b_month, anchor_day, b_hour, b_minute, b_second):
        years -= 1
    return years


def _build_planetaryages_snapshot_text(
    response: dict[str, Any], as_of: str | None, *, now: datetime | None = None, moment_lines: list[str] | None = None
) -> str:
    """逐字镜像上游 utils/planetaryAges.js:79-127 buildPlanetaryAgesSnapshotText。

    当前年龄缺省按「此刻」（上游 buildPlanetaryAges(chartObj) 无 asOf → moment()；skill 旧实现无 asOf 即不标
    当前带，与本仓 guidance「缺省=今天」矛盾）；asOf 给了则按该日（skill 扩展，同 JS asOf 形参）。
    带边界是整数岁，故 `curAge>=from && curAge<to` 只取决于日历周岁。段尾 ◆ 行星年四档（上游补的 UI 表）；
    定位行「当前主政」进 moment_lines（→ [当前时点]）。
    """
    chart = response.get("chart") if isinstance(response.get("chart"), dict) else {}
    params = response.get("params") if isinstance(response.get("params"), dict) else (chart.get("params") if isinstance(chart.get("params"), dict) else {})
    objects = chart.get("objects") if isinstance(chart.get("objects"), list) else []
    obj_by_id = {o.get("id"): o for o in objects if isinstance(o, dict)}
    reference = _moment_format_parse(as_of) if as_of else None
    if reference is None:
        reference = (now or _clock.now()).replace(microsecond=0)
    cur_age = _full_years_between(params.get("birth"), reference)
    lines = ["托勒密人生七阶：各年龄带由一颗古典行星主管，当前年龄所落之带为主运行星。"]
    if cur_age is not None:
        lines.append(f"当前年龄：约 {cur_age} 岁")
    lines += ["", "| 年龄带 | 主管 | 本命落座 | 当前 |", "| --- | --- | --- | --- |"]
    active_band = None
    for planet, frm, to in _PLANETARY_AGES:
        rng = f"{frm}+岁" if to is None else f"{frm}-{to}岁"
        active = cur_age is not None and cur_age >= frm and (to is None or cur_age < to)
        if active and active_band is None:
            active_band = (planet, rng)
        o = obj_by_id.get(planet)
        pos = "-"
        if isinstance(o, dict) and o.get("sign"):
            signlon = o.get("signlon")
            pos = _ap_name(o.get("sign")) + (f" {math.floor(float(signlon))}°" if signlon is not None else "")
        lines.append(f"| {rng} | {_ap_name(planet)} | {pos} | {'●' if active else ''} |")
    lines += [
        "",
        "◆ 行星年四档（小年/中年/大年/极大年）",
        "七政各有四档通用年数：小年为传统定数（七政小年之和为 129），中年为小年与大年之平均，大年为五星各自所辖界度数之和（日取 120、月取 108），极大年为传统极数。",
    ]
    for planet in _YEAR_BAND_ORDER:
        years = _ptext.PLANETARY_YEARS.get(planet, {})
        lines.append(
            f"{_ap_name(planet)}：小年 {_ptext.js_str(years.get('least', '-'))} · 中年 {_ptext.js_str(years.get('mean', '-'))}"
            f" · 大年 {_ptext.js_str(years.get('greater', '-'))} · 极大年 {_ptext.js_str(years.get('greatest', '-'))}"
        )
    if moment_lines is not None and active_band is not None:
        moment_lines.append(f"当前主政：{_ap_name(active_band[0])}（{active_band[1]}）")
    return _render_snapshot_text([("行星年龄（Ages of Man）", "\n".join(lines))])


# 时主类星运（129 年系统 / Balbillus）共用的年制键（上游 utils/timeLordYears.js TIME_LORD_YEAR_TYPES，v3.13.0 起六档；
# 值域与 vendored horosa-core-js/src/vendor/utils/timeLordYears.js 互锚：tests/test_sync313_predictive.py）。
# 129 年系统的快照由 vendored yearSystem129.js 出（runner 走 progextra），本仓不再有 Python 移植——上游 v3.13.0 删了
# 后端 yearsystem129.py，旧移植读的 predictives.yearsystem129 字段已不存在。
_TIME_LORD_YEAR_TYPES = ("solar", "sidereal", "hellenistic", "abumashar", "mashaallah", "bija")


_PERSIAN_MOVERS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
_PERSIAN_ASPECTS = [0, 60, 90, 120, 180]
_PERSIAN_SIGN_ORDER = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]


def _persian_lon_of(obj: dict[str, Any] | None) -> float | None:
    if not isinstance(obj, dict):
        return None
    lon = obj.get("lon")
    if lon is not None:
        try:
            return float(lon)
        except (TypeError, ValueError):
            return None
    sign = obj.get("sign")
    signlon = obj.get("signlon")
    if sign in _PERSIAN_SIGN_ORDER and signlon is not None:
        try:
            return _PERSIAN_SIGN_ORDER.index(sign) * 30 + float(signlon)
        except (TypeError, ValueError):
            return None
    return None


# 上游 components/astro/AstroPersianDirected.js:26-29 速率表 + 缺省（波斯速率 + 顺向 + 90 年）。
_PERSIAN_RATE = {"persian": 1.0, "prophected": 30.0, "naibod": 0.9856473}
_PERSIAN_RATE_LABEL = {"persian": "波斯 1°/年", "prophected": "Prophected 30°/年", "naibod": "Naibod 59′08″/年"}
# 上游挂载齿轮（techniqueMountSettings.js:1315-1328）的应期年数五档；builder 本身收任意正数。
_PERSIAN_MAX_YEARS_OPTIONS = (50, 90, 120, 150, 200)
_PERSIAN_YEAR_DAYS = 365.2421904


def _moment_format_parse(text: Any) -> datetime | None:
    """moment(串, ['YYYY-MM-DD HH:mm:ss', 'YYYY-MM-DD HH:mm', 'YYYY-MM-DD']) 的现代子集——只给「此刻 / asOf」这类
    引擎时刻用；命盘出生日期一律走 `_civil_birth_wall_ms`（上游 v3.12.0 起不再拿 moment 的格式解析读命盘日期）。"""
    raw = f"{text or ''}".strip().replace("/", "-")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _civil_birth_wall_ms(birth: Any) -> int | None:
    """civilMoment.momentOfCivilDateTimeStr(`${birth}`) 的墙钟毫秒（民用历：公元前历史纪年、1582 以前儒略历、1–6 位年；
    不验民用历存在性，与上游同）。缺 / 认不出 / 年 0 → None。"""
    if not birth:
        return None
    return _civil_wall_ms_of_moment(f"{birth}".strip(), strict=False)


def _civil_birth_greg_parts(birth: Any) -> tuple[int, int, int, int, int, int] | None:
    """出生时刻 → moment 里装的外推格里历 (天文年, 月, 日, 时, 分, 秒)（civilMoment.momentOfCivilJdn 同式）。"""
    wall = _civil_birth_wall_ms(birth)
    if wall is None:
        return None
    day_n, rem = divmod(int(wall), _MS_PER_DAY)
    year, month, day = _greg_ymd_of_jdn(day_n + _UNIX_EPOCH_JDN)
    seconds = rem // 1000
    return year, month, day, seconds // 3600, seconds // 60 % 60, seconds % 60


def _wall_ms_of_naive(when: datetime) -> int:
    """本机钟面 datetime（现代、格里历）→ 墙钟毫秒（= moment().format(...) 再经民用历单源读回，1582 以后两者同值）。"""
    return _civil_wall_ms(when.year, when.month, when.day, when.hour, when.minute, when.second)


def _build_persian_hits(chart_obj: dict[str, Any], rate_key: str, max_age: float, direction: str) -> list[dict[str, Any]]:
    """逐字镜像上游 AstroPersianDirected.js:56-98 `buildPersianHits`。

    [Q-168/T-102] 速率 >1°/年（Prophected 30°/年）一生可绕黄道多周：按 arc+360k 逐周取应期至 cap。
    日期 = moment(birth).add(age·365.2421904, 'days')——moment 对小数天**四舍五入到整天**（2.12+ 语义，
    node 实测 add(0.5,'days') 进一天），故这里按 JS Math.round 取整天后加到出生日上，与上游逐日一致。
    """
    chart = chart_obj.get("chart") if isinstance(chart_obj.get("chart"), dict) else {}
    params = chart_obj.get("params") if isinstance(chart_obj.get("params"), dict) else {}
    objects = chart.get("objects") if isinstance(chart.get("objects"), list) else []
    rate = _PERSIAN_RATE.get(rate_key) or 1.0
    cap = max_age or 90
    converse = direction == "converse"
    by_id: dict[str, float] = {}
    for obj in objects:
        if isinstance(obj, dict):
            lon = _persian_lon_of(obj)
            if lon is not None:
                by_id[obj.get("id")] = lon
    targets: list[tuple[str, float]] = list(by_id.items())
    for index, house in enumerate(chart.get("houses") if isinstance(chart.get("houses"), list) else []):
        lon = _persian_lon_of(house) if isinstance(house, dict) else None
        if lon is not None:
            targets.append((f"{index + 1}宫头", lon))
    birth_wall = _civil_birth_wall_ms(params.get("birth"))
    birth_jdn = (int(birth_wall) // _MS_PER_DAY + _UNIX_EPOCH_JDN) if birth_wall is not None else None
    hits: list[dict[str, Any]] = []
    for mover in _PERSIAN_MOVERS:
        mover_lon = by_id.get(mover)
        if mover_lon is None:
            continue
        for target_id, target_lon in targets:
            if target_id == mover:
                continue
            for aspect in _PERSIAN_ASPECTS:
                for sign in (1, -1):
                    if aspect in (0, 180) and sign == -1:
                        continue
                    target = (target_lon + sign * aspect) % 360
                    arc = (mover_lon - target) % 360 if converse else (target - mover_lon) % 360
                    for k in range(400):
                        age = (arc + 360 * k) / rate
                        if age > cap:
                            break
                        if age > 0:
                            date = ""
                            if birth_jdn is not None:
                                # v3.12.0 civilDateAfterDays：出生日序 + Math.round(天) → 民用历日期标签
                                date = _civil_date_str_of_jdn(birth_jdn + _ptext.js_round(age * _PERSIAN_YEAR_DAYS))
                            hits.append({
                                "age": _ptext.js_round2(age), "promittor": mover, "aspect": aspect,
                                "significator": target_id, "date": date,
                            })
                        if rate <= 1.0:
                            break
    hits.sort(key=lambda h: h["age"])  # 稳定排序（= V8 Array.prototype.sort）
    return hits


def _persian_directed_age_years(birth: Any, when: Any) -> float | None:
    """上游 AstroPersianDirected.js directedAgeYears：两个时刻都经民用历单源（momentOfCivilDateTimeStr），
    d.diff(b, 'days', true) / 365.2421904（墙钟差）。`when` 是 datetime 时 = 「此刻」的本机钟面。"""
    if not birth or not when:
        return None
    birth_ms = _civil_birth_wall_ms(birth)
    when_ms = _wall_ms_of_naive(when) if isinstance(when, datetime) else _civil_birth_wall_ms(when)
    if birth_ms is None or when_ms is None:
        return None
    return (when_ms - birth_ms) / 86400000.0 / _PERSIAN_YEAR_DAYS


def _select_nearby_persian_hits(hits: list[dict[str, Any]], current_age: float | None, limit: int = 12) -> list[dict[str, Any]]:
    """上游 AstroPersianDirected.js:175 selectNearbyPersianHits：按 |age−当前| 取最近 limit 条，再按 age 重排。"""
    if current_age is None or not hits or not math.isfinite(current_age):
        return []
    near = sorted(hits, key=lambda h: abs(h["age"] - current_age))[:limit]
    return sorted(near, key=lambda h: h["age"])


def _persian_hit_row(hit: dict[str, Any]) -> str:
    return (
        f"| {_ptext.js_str(hit['age'])} | {hit['date'] or '-'} | {_ptext.astro_txt(hit['promittor'])} | "
        f"{_ptext.asp_txt(hit['aspect'])} | {_ptext.astro_txt(hit['significator'])} |"
    )


def _build_persiandirected_snapshot_text(
    response: dict[str, Any],
    opts: dict[str, Any] | None = None,
    *,
    now: datetime | None = None,
    moment_lines: list[str] | None = None,
) -> str:
    """逐字镜像上游 AstroPersianDirected.js:103-157 buildPersianDirectedSnapshotText(chartObj, opts)。

    opts：rateKey（persian/prophected/naibod）/ direction（direct/converse）/ maxYears / datetime。
    [Q-168/T-102] 首行按所选速率/方向写（此前写死 1°/年）；主表上限 max(200, maxYears×4)；
    段尾 ◆ 近期命中（距今最近，12 条）。当前向运年龄：给 datetime 按推运时间，否则按导出时刻；
    该定位行写进 moment_lines（由 [当前时点] 段追加，= 上游 extraLines）。
    """
    o = {"rateKey": "persian", "direction": "direct", **(opts or {})}
    rate_key = o.get("rateKey") if o.get("rateKey") in _PERSIAN_RATE else "persian"
    direction = "converse" if o.get("direction") == "converse" else "direct"
    max_years = _finite_number(o.get("maxYears"))
    max_years = max_years if max_years is not None and max_years > 0 else 90
    hits = _build_persian_hits(response, rate_key, max_years, direction)
    if not hits:
        return _render_snapshot_text([("波斯向运（Persian Directed）", "（本盘无波斯向运应期）")])
    lines = [
        f"黄经象征向运({_PERSIAN_RATE_LABEL.get(rate_key) or rate_key})：所有行星/点按此速率"
        f"{'逆向(Converse)' if direction == 'converse' else '顺向'}推进,本命宫头不动；下表为向运星触及本命的应期。",
        "",
        "| 年龄 | 日期 | 向运星 | 相位 | 本命对象 |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend(_persian_hit_row(hit) for hit in hits[: max(200, int(max_years * 4))])
    params = response.get("params") if isinstance(response.get("params"), dict) else {}
    birth = params.get("birth")
    dt_str = f"{o.get('datetime') or ''}".strip()
    current_age = _persian_directed_age_years(birth, dt_str) if dt_str else None
    age_basis = f"按推运时间 {dt_str}"
    if current_age is None:
        # 上游 moment().format('YYYY-MM-DD HH:mm:ss') 截到秒再解析 → 这里同样去掉微秒。
        current_age = _persian_directed_age_years(birth, (now or _clock.now()).replace(microsecond=0))
        age_basis = "按导出时刻"
    near = _select_nearby_persian_hits(hits, current_age, 12)
    if near:
        lines.extend(["", "◆ 近期命中（距今最近）", "| 年龄 | 日期 | 向运星 | 相位 | 本命对象 |", "| --- | --- | --- | --- | --- |"])
        lines.extend(_persian_hit_row(hit) for hit in near)
    if moment_lines is not None and current_age is not None and math.isfinite(current_age):
        moment_lines.append(f"当前向运年龄：{_ptext.js_str(_ptext.js_round2(current_age))} 岁（{age_basis}）")
    return _render_snapshot_text([("波斯向运（Persian Directed）", "\n".join(lines))])


_KP_LORD_CN = {
    # 逐字取 IndiaChartMain.js KP_LORD_CN（罗睺/计都口径与 KP 面板同源）。
    "Sun": "太阳", "Moon": "月亮", "Mars": "火星", "Mercury": "水星", "Jupiter": "木星",
    "Venus": "金星", "Saturn": "土星", "Rahu": "罗睺", "Ketu": "计都",
    "North Node": "罗睺", "South Node": "计都",
}


def _kp_lord_cn(value: Any) -> str:
    text = f"{value or ''}".strip()
    return _KP_LORD_CN.get(text, text or "—")


def _build_india_rectify_snapshot_text(payload: dict[str, Any], res: dict[str, Any]) -> str:
    """[生时校正]（/india/rectify 的文本化）。语汇照上游校时器抽屉（IndiaChartMain.js §17）：
    「校时之靶」「N 采样」「总/RP/PP」「步长诊断…充分/建议步长 ≤Ns」；vara.note 与 disclaimer 原样带回。"""
    info_lines = [
        f"锚点时刻：{res.get('anchorTime') or '—'}（{payload.get('zone') or ''}）",
        f"地点：{payload.get('pos') or ''}　经度 {payload.get('lon')} 纬度 {payload.get('lat')}".rstrip(),
    ]
    criteria = res.get("criteriaActive") or []
    vara = res.get("vara") if isinstance(res.get("vara"), dict) else {}
    diag = res.get("resolution") if isinstance(res.get("resolution"), dict) else {}
    scan_lines = [
        f"扫描半窗：{_round3(res.get('windowMinutes'))} 分　步长：{res.get('stepSeconds')} 秒　候选：{res.get('candidates')} 个",
        f"RP 取法：{res.get('rpSource') or 'anchor'}　参评判据：{' / '.join(str(c) for c in criteria) or '—'}",
        f"日主(vara)：民用日 {_kp_lord_cn(vara.get('civil'))} · 日出日 {_kp_lord_cn(vara.get('sunrise'))}（以 {vara.get('basisUsed') or 'sunrise'} 为准）",
    ]
    if diag:
        adequacy = " · 充分" if diag.get("adequate") else f" · 会整段跳过子主,建议步长 ≤{diag.get('suggestedStepSeconds')}s"
        scan_lines.append(
            f"步长诊断:单步 Lagna 最大位移 {_round3(diag.get('maxLagnaDeltaDeg'))}° / KP 最窄 Sub {_round3(diag.get('narrowestSubDeg'))}°{adequacy}"
        )
    runs = ((res.get("runs") or {}).get("lagnaSubLord")) or []
    run_lines = [f"校时之靶 · {len(runs)} 段"]
    for r in runs:
        if isinstance(r, dict):
            run_lines.append(f"{_kp_lord_cn(r.get('value'))}：{r.get('fromTime')} ~ {r.get('toTime')}（{r.get('count')} 采样）")
    top = res.get("top") or []
    top_lines: list[str] = [f"Top {len(top)} 候选（按判据总分排序）"]
    for i, t in enumerate(top):
        if not isinstance(t, dict):
            continue
        score = t.get("score") if isinstance(t.get("score"), dict) else {}
        rp = t.get("rp") if isinstance(t.get("rp"), dict) else {}
        pp = t.get("pranapada") if isinstance(t.get("pranapada"), dict) else {}
        boundary = t.get("boundary") if isinstance(t.get("boundary"), dict) else {}
        warn_bits = []
        if boundary.get("moonGandanta"):
            warn_bits.append("月亮落界")
        if boundary.get("lagnaGandanta"):
            warn_bits.append("Lagna 落界")
        lords = (
            f"签 {_kp_lord_cn(t.get('lagnaSignLord'))} / 星 {_kp_lord_cn(t.get('lagnaStarLord'))} / "
            f"子主 {_kp_lord_cn(t.get('lagnaSubLord'))}"
        )
        top_lines.append(
            f"{i + 1}. {t.get('time')}（偏移 {t.get('offsetSeconds')}s）　总 {_round3(score.get('total'))}　"
            f"RP {_round3(rp.get('score'))}/{_round3(rp.get('maxScore'))}　PP {pp.get('overall') or '—'}　{lords}"
            + (f"　⚠ {'/'.join(warn_bits)}" if warn_bits else "")
        )
    note_lines = [line for line in (vara.get("note"), res.get("disclaimer")) if line]
    return _render_snapshot_text([
        ("起盘信息", "\n".join(info_lines)),
        ("校时扫描", "\n".join(scan_lines)),
        ("Lagna 子主区段", "\n".join(run_lines)),
        ("候选榜", "\n".join(top_lines)),
        ("声明", "\n".join(note_lines) or "—"),
    ])


def _build_persianchart_section_text(directed: dict[str, Any]) -> str:
    """[指定日期向运盘]（/predict/persianchart，getPersianDirectedByDate 的文本化）。

    directed 形状：{date, rateKey, direction, ageYears, chart:{objects, aspects}, natalChart, lots}。
    aspects 为向运点→本命点命中：[{directId, objects:[{natalId, aspect, delta}]}]。
    """
    if not isinstance(directed, dict) or not isinstance(directed.get("chart"), dict):
        return ""
    chart = directed["chart"]
    lines = [
        f"目标日期：{directed.get('date') or '—'}　速率：{directed.get('rateKey') or 'persian'}　"
        f"方向：{'逆向' if directed.get('direction') == 'converse' else '顺向'}　行进 {_round3(directed.get('ageYears'))} 年",
        "",
        "向运点位：",
    ]
    for obj in chart.get("objects") or []:
        if not isinstance(obj, dict) or obj.get("id") is None:
            continue
        sign = _astro_msg(obj.get("sign"))
        try:
            signlon = float(obj.get("signlon"))
            deg, minute = int(signlon), int(round((signlon - int(signlon)) * 60)) % 60
            pos = f"{sign} {deg}°{minute:02d}′"
        except (TypeError, ValueError):
            pos = sign or "—"
        lines.append(f"{_astro_msg(obj.get('id'))}：{pos}")
    aspect_rows: list[str] = []
    for row in chart.get("aspects") or []:
        if not isinstance(row, dict):
            continue
        direct_name = _astro_msg(row.get("directId"))
        for hit in row.get("objects") or []:
            if not isinstance(hit, dict):
                continue
            aspect_rows.append(
                f"向运{direct_name} {_aspect_label(hit.get('aspect'))} 本命{_astro_msg(hit.get('natalId'))}"
                f"（差 {_round3(hit.get('delta'))}°）"
            )
    if aspect_rows:
        lines.extend(["", "向运→本命相位命中："])
        lines.extend(aspect_rows)
    lots = directed.get("lots")
    if isinstance(lots, list) and lots:
        lines.append(f"（另有 directed 阿拉伯点 {len(lots)} 枚，见 directed_chart.lots）")
    return _render_snapshot_text([("指定日期向运盘", "\n".join(lines))])


def _build_firdaria_snapshot_text(response: dict[str, Any]) -> str:
    chart = response.get("chart", {}) if isinstance(response, dict) else {}
    params = response.get("params", {}) if isinstance(response, dict) else {}
    predictives = response.get("predictives", {}) if isinstance(response, dict) else {}
    firdaria = predictives.get("firdaria", []) if isinstance(predictives, dict) else []
    birth_text = params.get("birth") or f"{params.get('date', '—')} {params.get('time', '—')}"
    true_solar = chart.get("nongli", {}).get("birth", "无") if isinstance(chart, dict) else "无"
    lines = [
        ("出生时间", "\n".join([f"出生时间：{birth_text}", f"真太阳时：{true_solar}"]).strip()),
        (
            "星盘信息",
            "\n".join(
                [
                    f"经纬度：{params.get('lon', '—')} {params.get('lat', '—')}",
                    f"时区：{params.get('zone', '—')}",
                    f"盘型：{'日生盘' if chart.get('isDiurnal') else '夜生盘'}" if isinstance(chart, dict) and chart.get("isDiurnal") is not None else "盘型：无",
                ]
            ),
        ),
    ]
    table_lines = ["| 主限 | 子限 | 日期 |", "| --- | --- | --- |"]
    row_count = 0
    for main in firdaria or []:
        if not isinstance(main, dict):
            continue
        main_direct = _planet_label(main.get("mainDirect"))
        subs = main.get("subDirect") if isinstance(main.get("subDirect"), list) else []
        if not subs:
            table_lines.append(f"| {main_direct} | 无 | 无 |")
            row_count += 1
            continue
        for sub in subs:
            if not isinstance(sub, dict):
                continue
            table_lines.append(f"| {main_direct} | {_planet_label(sub.get('subDirect'))} | {sub.get('date', '无')} |")
            row_count += 1
    if row_count == 0:
        table_lines.append("| 无 | 无 | 无 |")
    lines.append(("法达星限表格", "\n".join(table_lines)))
    return _render_snapshot_text(lines)


def _build_decennials_snapshot_text(response: dict[str, Any], settings: dict[str, Any], ai_state: dict[str, Any]) -> str:
    chart = response.get("chart", {}) if isinstance(response, dict) else {}
    params = response.get("params", {}) if isinstance(response, dict) else {}
    timeline = response.get("timeline", {}) if isinstance(response, dict) else {}
    list_data = timeline.get("list", []) if isinstance(timeline, dict) else []
    resolved = timeline.get("resolvedStartPlanet", "Sun")
    birth_text = params.get("birth") or f"{params.get('date', '—')} {params.get('time', '—')}"
    true_solar = chart.get("nongli", {}).get("birth", "无") if isinstance(chart, dict) else "无"
    order_label = "迦勒底星序" if settings.get("orderType") == DECENNIAL_ORDER_CHALDEAN else "实际黄道次序"
    day_label = "Hephaistio（原表日数）" if settings.get("dayMethod") == DECENNIAL_DAY_METHOD_HEPHAISTIO else "Valens（精确）"
    # 上游 utils/decennials.js:577-582 getDecennialCalendarLabel（AstroDecennials.js:193 [时间口径] 行逐字取它）：
    # 1461/1440 的换算比是儒略年，不是回归年（v3.11.3 起上游即此文案，本仓此前一直印「按回归年换算」）。
    cal_label = (
        "365.25天/年（儒略年；回归年为 365.2422 天）"
        if settings.get("calendarType") == DECENNIAL_CALENDAR_ACTUAL
        else "360天/年（按30天/月换算）"
    )
    start_label = f"得时光体（{resolved}）" if settings.get("startMode") == DECENNIAL_START_MODE_SECT_LIGHT else settings.get("startMode", resolved)

    def safe_idx(index: Any, length: int) -> int:
        if length <= 0:
            return 0
        try:
            number = int(index)
        except (TypeError, ValueError):
            return 0
        return max(0, min(number, length - 1))

    mode = ai_state.get("aiMode", "l1_all")
    l1_idx = safe_idx(ai_state.get("aiL1Idx", 0), len(list_data))
    l1 = list_data[l1_idx] if list_data else None
    l2_list = l1.get("sublevel", []) if isinstance(l1, dict) else []
    l2_idx = safe_idx(ai_state.get("aiL2Idx", 0), len(l2_list))
    l2 = l2_list[l2_idx] if l2_list else None
    l3_list = l2.get("sublevel", []) if isinstance(l2, dict) else []
    l3_idx = safe_idx(ai_state.get("aiL3Idx", 0), len(l3_list))
    l3 = l3_list[l3_idx] if l3_list else None

    def node_line(prefix: str, item: dict[str, Any], idx: int) -> str:
        return f"{prefix}-{idx + 1}：{item.get('planet', '无')}-{item.get('date', '无')}{'（名义：' + item.get('nominal', '') + '）' if item.get('nominal') else ''}{'-当前' if item.get('active') else ''}"

    output_lines: list[str] = [f"AI输出模式：{mode}"]
    if not list_data:
        output_lines.append("无推运数据")
    elif mode == "l1_all":
        output_lines.extend(node_line("L1", item, idx) for idx, item in enumerate(list_data))
    else:
        if l1:
            output_lines.append(node_line("L1", l1, l1_idx))
        if mode in {"l2_in_l1", "l3_in_l2", "l4_in_l3"}:
            if mode == "l2_in_l1":
                output_lines.extend(node_line("L2", item, idx) for idx, item in enumerate(l2_list)) if l2_list else output_lines.append("无L2数据")
            elif l2:
                output_lines.append(node_line("L2", l2, l2_idx))
        if mode in {"l3_in_l2", "l4_in_l3"}:
            if mode == "l3_in_l2":
                output_lines.extend(node_line("L3", item, idx) for idx, item in enumerate(l3_list)) if l3_list else output_lines.append("无L3数据")
            elif l3:
                output_lines.append(node_line("L3", l3, l3_idx))
        if mode == "l4_in_l3":
            l4_list = l3.get("sublevel", []) if isinstance(l3, dict) else []
            output_lines.extend(node_line("L4", item, idx) for idx, item in enumerate(l4_list)) if l4_list else output_lines.append("无L4数据")

    return _render_snapshot_text(
        [
            (
                "起盘信息",
                "\n".join(
                    [
                        f"出生时间：{birth_text}",
                        f"真太阳时：{true_solar}",
                        f"经纬度：{params.get('lon', '—')} {params.get('lat', '—')}",
                        f"时区：{params.get('zone', '—')}",
                    ]
                ),
            ),
            (
                "星盘信息",
                "\n".join(
                    [
                        f"黄道：{chart.get('zodiacal', params.get('zodiacal', 0)) if isinstance(chart, dict) else params.get('zodiacal', 0)}",
                        f"宫制：{params.get('hsys', 0)}",
                        f"盘型：{'日生盘' if chart.get('isDiurnal') else '夜生盘'}" if isinstance(chart, dict) and chart.get("isDiurnal") is not None else "盘型：无",
                    ]
                ),
            ),
            (
                "十年大运设置",
                "\n".join(
                    [
                        f"起运主星：{start_label}",
                        f"实际起运：{resolved}",
                        f"分配次序：{order_label}",
                        f"日限体系：{day_label}",
                        f"时间口径：{cal_label}",
                    ]
                ),
            ),
            (f"基于{resolved}起运", "\n".join(output_lines).strip() or "无"),
        ]
    )


def _predictive_chart_wrap(response: dict[str, Any]) -> dict[str, Any]:
    return (
        _chart_wrap_from_response(response, "dirChart")
        or _top_level_chart_wrap(response)
    )


def _natal_chart_wrap(response: dict[str, Any]) -> dict[str, Any]:
    return (
        _chart_wrap_from_response(response, "natalChart")
        or _chart_wrap_from_response(response, "birthChart")
        or _chart_wrap_from_response(response, "baseChart")
    )


def _natal_config_lines(chart_wrap: dict[str, Any]) -> list[str]:
    """[本命盘配置]（内圈）：星与虚点 + 宫位宫头 两个子块（上游 AstroPrimaryDirectionChart.js:351-358）。"""
    lines: list[str] = []
    stars = _build_star_and_lot_position_lines(chart_wrap)
    if stars:
        lines.extend(["星与虚点", *stars])
    cusps = _build_house_cusp_lines(chart_wrap)
    if cusps:
        lines.extend(["宫位宫头", *cusps])
    return lines


def _directed_config_lines(chart_wrap: dict[str, Any]) -> list[str]:
    """[主限法盘配置]（外圈/时段盘）：同上两子块，取推导后的盘（上游 :359-366）。"""
    return _natal_config_lines(chart_wrap)


def _build_predictive_cross_aspect_lines(
    response: dict[str, Any],
    predictive_wrap: dict[str, Any] | None = None,
    natal_wrap: dict[str, Any] | None = None,
) -> list[str]:
    """推运盘 ↔ 本命盘的交叉相位（上游 predictiveAiSnapshot.js::buildAspectLines 同款）。

    这**不是**本命盘那种 {normalAsp, immediateAsp, signAsp} 结构：`/predict/*` 把交叉相位放在
    `response["chart"]["aspects"]` 的**数组**里，每项形如
    `{directId, objects:[{natalId, aspect, delta}]}`（后端 perpredict.getAspects 产出）。
    此前这段错走 `_build_aspect_section`（读本命盘形状、且只认顶层 aspects）→ 真机上整段只输出
    「标准相位/立即相位/星座相位」三个空子标题、一条相位都没有。离线测试没抓到，是因为
    FakeClient 在顶层塞了本命形状的 aspects——桩与真实响应形状不一致，把 bug 盖住了。
    """
    chart = response.get("chart") if isinstance(response.get("chart"), dict) else {}
    aspects = chart.get("aspects")
    if not isinstance(aspects, list):
        return []
    lines: list[str] = []
    for item in aspects:
        if not isinstance(item, dict):
            continue
        direct_id = item.get("directId") or item.get("id")
        # 上游 appendPlanetHouseInfoById：推运星的宫位取推运盘、本命星的宫位取本命盘（两张盘各查各的）。
        direct_label = _astro_msg_with_house(direct_id, predictive_wrap or {}, short=True)
        for target in item.get("objects") or []:
            if not isinstance(target, dict):
                continue
            natal_label = _astro_msg_with_house(target.get("natalId") or target.get("id"), natal_wrap or {}, short=True)
            # 上游 predictiveAiSnapshot.js:199：AstroTxtMsg['Asp'+aspect] || aspect+'º'（º=U+00BA，非 ˚）。
            aspect = _ptext.js_str(target.get("aspect"))
            asp = _ptext.UPSTREAM_ASTRO_TXT_MSG.get(f"Asp{aspect}") or f"{aspect}º"
            lines.append(
                f"行运{direct_label} 与 本命{natal_label}"
                f" 成 {asp} 相位，误差{_round3(target.get('delta'))}"
            )
    return lines


# 上游 components/astro/AstroPrimaryDirectionChart.js:39-55 / 188-260：主限法盘缺省时刻 = 主限表首条（按方法/界限法
# 过滤后）的「日期」列（UTC 墙钟，PD_DISPLAY_ZONE '+00:00'）；无行则出生次日（同一墙钟改挂 +00:00）。
_PD_DISPLAY_ZONE = "+00:00"
_PD_CORE_SUPPORTED_BASE_IDS = frozenset({
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
    "North Node", "Pars Fortuna", "Asc", "MC",
})


def _pd_base_object_id(text: Any) -> str:
    """AstroPrimaryDirectionChart.js:205 baseDirectionObjectId。"""
    raw = f"{text or ''}"
    parts = raw.split("_")
    if len(parts) < 3:
        if len(parts) == 2 and parts[0] in ("A", "C"):
            return parts[1]
        return raw.strip()
    if parts[0] == "T":
        return parts[1].strip()
    return "_".join(parts[1:-1]).strip()


def _pd_is_bound_row(row: list[Any]) -> bool:
    return f"{row[1] if len(row) > 1 else ''}".startswith("T_") or f"{row[2] if len(row) > 2 else ''}".startswith("T_")


def _pd_is_antiscia_row(row: list[Any]) -> bool:
    prom = f"{row[1] if len(row) > 1 else ''}"
    sig = f"{row[2] if len(row) > 2 else ''}"
    return prom.startswith(("A_", "C_")) or sig.startswith(("A_", "C_"))


def _pd_display_rows(rows: Any, pd_method: str, show_pd_bounds: Any) -> list[list[Any]]:
    """AstroPrimaryDirectionChart.js:235 buildDisplayRows（只取过滤后的原始行）。"""
    hide_bounds = show_pd_bounds in (0, False)
    is_core = pd_method == "core_alchabitius"
    out: list[list[Any]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, list) or not row:
            continue
        if is_core and (
            _pd_is_bound_row(row)
            or _pd_base_object_id(row[1] if len(row) > 1 else "") not in _PD_CORE_SUPPORTED_BASE_IDS
            or _pd_base_object_id(row[2] if len(row) > 2 else "") not in _PD_CORE_SUPPORTED_BASE_IDS
        ):
            continue
        if hide_bounds and _pd_is_bound_row(row):
            continue
        if is_core and _pd_is_antiscia_row(row):
            continue
        out.append(row)
    return out


# ── 「此刻」按本盘时区（上游 v3.12.0 components/comp/DateTime.js:26-46）────────────────────────────────────
# 上游把推运 / 返照 / 行运类的缺省「此刻 / 今日 / 今年」统一改成按**这张盘的时区**取钟面：此前一律东八区钟面（或本机钟面）
# 再配本命时区下发，不在东八区的盘错开时差那么多小时。东八区盘逐位不变。两个入口语义不同，照抄：
#   nowForChart(zone)       盘时区合法 → 该时区钟面；否则 = new DateTime()（+08:00 钟面）
#   wallClockForChart(zone) 盘时区合法 → 该时区钟面；否则 = new Date()（本机钟面）
# 一切「此刻」都从 `_clock.now()`（本机钟面，测试可冻结）换成真实瞬时再平移，冻结时钟对这几路同样生效。
_CHART_ZONE_RE = re.compile(r"^([+-])(\d{2}):(\d{2})(?::(\d{2}))?$")


def _chart_zone_seconds(zone: Any) -> int | None:
    """上游 nowForChart / wallClockForChart / birthInstantMsInZone 同一判据：`±HH:MM` 或带秒 `±HH:MM:SS`，否则 None。"""
    match = _CHART_ZONE_RE.match(zone) if isinstance(zone, str) else None
    if not match:
        return None
    sign = -1 if match.group(1) == "-" else 1
    return sign * (int(match.group(2)) * 3600 + int(match.group(3)) * 60 + int(match.group(4) or 0))


def _now_instant() -> datetime:
    """真实此刻（带时区）。`_clock.now()` 是本机钟面（naive），`.astimezone()` 按本机时区解读成瞬时。"""
    return _clock.now().astimezone()


def _wall_clock_in(zone_seconds: int) -> datetime:
    return _now_instant().astimezone(timezone(timedelta(seconds=zone_seconds))).replace(tzinfo=None)


def _now_for_chart(zone: Any) -> datetime:
    """上游 DateTime.nowForChart(zone)：盘时区合法 → 该时区此刻钟面；否则 new DateTime()（+08:00 钟面）。"""
    seconds = _chart_zone_seconds(zone)
    return _wall_clock_in(8 * 3600 if seconds is None else seconds)


def _wall_clock_for_chart(zone: Any) -> datetime:
    """上游 DateTime.wallClockForChart(zone)：盘时区合法 → 该时区此刻钟面；否则本机钟面（new Date()）。"""
    seconds = _chart_zone_seconds(zone)
    return _clock.now() if seconds is None else _wall_clock_in(seconds)


def _today_for_chart(zone: Any) -> str:
    """上游 astroProgSnapshot.js:18-21 today(zone) / regenHoraryElection.js:196-199 todayDateStr(zone)：
    给了 zone（非空）= nowForChart(zone) 的日期；不给 = 本机今日。"""
    return (_now_for_chart(zone) if zone else _clock.now()).strftime("%Y-%m-%d")


def _birth_instant_in_zone(birth_wall: datetime, zone: Any) -> datetime:
    """上游 astroAiSnapshot.js birthInstantMsInZone(birth, zone)：出生钟面按本盘时区解读；时区不合法 → 按本机时区（原样）。"""
    seconds = _chart_zone_seconds(zone)
    if seconds is None:
        return birth_wall.astimezone()
    return birth_wall.replace(tzinfo=timezone(timedelta(seconds=seconds)))


def _is_gregorian_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _return_picker_seed(birth: Any, now: datetime) -> str:
    """上游 utils/returnPickerSeed.js（v3.12.0）：三返照 / 流年缺省目标时刻 = 今年 + 出生月日 + 出生时分（'YYYY-MM-DD HH:mm'）。

    出生串按民用历日期串解析（前导负号 / 1–5 位年都对），不按「前 4 位是年」切片——旧写法 `今年 + birth[4:]` 对
    '-0003-03-10' 拼出「20263 年」。2 月 29 日出生、今年没有 2 月 29 日 → 落 3 月 1 日（上游 addCivilYears 同规则）。
    birth 不可解析 → 此刻本身。`now` 是调用方取的 nowForChart(zone) 钟面（今年在盘时区里算）。
    """
    parts = f"{birth or ''}".strip().split()
    match = re.fullmatch(r"(-?)(\d{1,5})-(\d{1,2})-(\d{1,2})", parts[0].replace("/", "-")) if parts else None
    if not match or not 1 <= int(match.group(3)) <= 12 or not 1 <= int(match.group(4)) <= 31:
        return now.strftime("%Y-%m-%d %H:%M")
    month, day = int(match.group(3)), int(match.group(4))
    # 今年（公历、近现代）落不到的 2/29 → 3/1；其余月日原样（出生串已是合法民用历日期）。
    if month == 2 and day == 29 and not _is_gregorian_leap(now.year):
        month, day = 3, 1

    def num(value: str) -> int:
        found = re.match(r"\s*([+-]?\d+)", value)
        return int(found.group(1)) if found else 0

    hms = f"{parts[1] if len(parts) > 1 else '12:00:00'}".split(":")
    hour = num(hms[0])
    minute = num(hms[1]) if len(hms) > 1 else 0
    return f"{now.year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}"


# 上游 predictiveAiSnapshot.js:106-139 pickInfoBlocks 的块标题白名单（[本命盘配置]「信息」子块）。
_PREDICTIVE_INFO_BLOCK_TITLES = ("映点/反映点", "接纳", "互容", "光线围攻", "夹宫", "夹星", "纬照")


def _pick_info_blocks(lines: list[str], titles: tuple[str, ...]) -> list[str]:
    """上游 predictiveAiSnapshot.js:120 pickInfoBlocks：自首个命中标题起收全部非空行（互容→互融）。"""
    out: list[str] = []
    in_block = False
    for line in lines:
        text = f"{line or ''}".strip()
        if not text:
            continue
        if text in titles:
            in_block = True
            out.append(text.replace("互容", "互融"))
            continue
        if in_block:
            out.append(text.replace("互容", "互融"))
    return out


def _predictive_star_info_lines(natal_wrap: dict[str, Any]) -> list[str]:
    """上游 predictiveAiSnapshot.js:51-104 buildStarInfoLines(natalChartObj)。"""
    params = natal_wrap.get("params") if isinstance(natal_wrap.get("params"), dict) else {}
    chart = natal_wrap.get("chart") if isinstance(natal_wrap.get("chart"), dict) else {}
    lines: list[str] = []
    lon, lat = params.get("lon"), params.get("lat")
    if lon or lat:
        lon_lat = f"{lon or ''} {lat or ''}".strip()
        lines.append(f"经纬度：{lon_lat}")
    if params.get("zone") is not None:
        lines.append(f"时区：{params.get('zone')}")
    zodiacal_raw = chart.get("zodiacal") or _ptext.ZODIACAL.get(_ptext.js_str(params.get("zodiacal")))
    if zodiacal_raw:
        ayan_key = params.get("siderealAyanamsa") or chart.get("siderealAyanamsa") or ""
        lines.append(f"黄道：{_ptext.zodiacal_display_text(zodiacal_raw, ayan_key)}")
    hsys = _ptext.HOUSE_SYS_LABELS.get(_ptext.js_str(params.get("hsys"))) or chart.get("hsys")
    if hsys:
        lines.append(f"宫制：{hsys}")
    if chart.get("isDiurnal") is not None:
        lines.append(f"盘型：{'日生盘' if chart.get('isDiurnal') else '夜生盘'}")
    lines.append(PLANET_HOUSE_INFO_NOTE)
    house_lines = _build_house_cusp_lines(natal_wrap)
    if house_lines:
        lines.extend(["宫位宫头", *house_lines])
    star_lines = _build_star_and_lot_position_lines(natal_wrap)
    if star_lines:
        lines.extend(["星与虚点", *star_lines])
    info_only = _pick_info_blocks(_build_info_section(natal_wrap, {}), _PREDICTIVE_INFO_BLOCK_TITLES)
    if info_only:
        lines.extend(["信息", *info_only])
    return lines


def _predictive_setup_lines(params: dict[str, Any]) -> list[str]:
    """上游 predictiveAiSnapshot.js:143-176 buildSetupLines(params)（[起盘信息] = 推运时点口径）。"""
    lines: list[str] = []
    if params.get("datetime"):
        lines.append(f"推运时间：{params['datetime']}")
    if params.get("dirZone") is not None:
        lines.append(f"推运时区：{params['dirZone']}")
    lon = params.get("dirLon") or params.get("lon")
    lat = params.get("dirLat") or params.get("lat")
    if lon or lat:
        lon_lat = f"{lon or ''} {lat or ''}".strip()
        lines.append(f"推运经纬度：{lon_lat}")
    if params.get("tmType"):
        lines.append(f"时间步进：{params['tmType']}")
    if params.get("asporb") is not None:
        lines.append(f"相位容许度：{_ptext.js_str(params['asporb'])}")
    if params.get("nodeRetrograde") is not None:
        lines.append(f"月交点逆行：{'是' if params['nodeRetrograde'] else '否'}")
    # 恒星黄道时标注具体 ayanāṃśa（仅恒星盘追加此行 → 回归盘输出逐字不变）。
    if _ptext.js_str(params.get("zodiacal")) == "1":
        lines.append(f"黄道：{_ptext.zodiacal_display_text(params.get('zodiacal'), params.get('siderealAyanamsa'))}")
    return lines


# 目标时刻型 5 法（上游 aiAnalysisContext.js:2673-2760 buildPredictivePeriodSnapshot）。
_PERIOD_PREDICTIVE_TOOLS = ("profection", "solararc", "solarreturn", "lunarreturn", "givenyear")
_RETURN_PREDICTIVE_TOOLS = ("solarreturn", "lunarreturn", "givenyear")


def _predictive_text_params(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """buildPredictivePeriodSnapshot 的请求体（= [起盘信息] 的文字源）：tmType 恒 'y'、asporb 缺省 1、
    nodeRetrograde 缺省 false、dirZone 缺省本命时区；returns 型另带 dirLat/dirLon（缺省本命经纬）。"""
    params: dict[str, Any] = {
        "date": payload.get("date"),
        "time": payload.get("time"),
        "zone": payload.get("zone"),
        "lon": payload.get("lon"),
        "lat": payload.get("lat"),
        "datetime": payload.get("datetime"),
        "dirZone": payload.get("dirZone") or payload.get("zone"),
        "tmType": "y",
        "asporb": payload.get("asporb") if payload.get("asporb") is not None else 1,
        "nodeRetrograde": bool(payload.get("nodeRetrograde")),
        "zodiacal": payload.get("zodiacal"),
        "siderealAyanamsa": payload.get("siderealAyanamsa"),
    }
    if tool_name in _RETURN_PREDICTIVE_TOOLS:
        params["dirLat"] = payload.get("dirLat") or payload.get("lat")
        params["dirLon"] = payload.get("dirLon") or payload.get("lon")
    return params


def _build_predictive_snapshot_text(tool_name: str, payload: dict[str, Any], response: dict[str, Any]) -> str:
    """逐字镜像上游 utils/predictiveAiSnapshot.js:225-287 buildPredictiveSnapshotText(natal, params, result, key)。

    段：[本命盘配置]（生辰裸行 + buildStarInfoLines）/ [起盘信息]（buildSetupLines 推运时点口径）/
    [小限摘要]（仅 profection，[Q-105]）/ [时段盘配置] / [相位]；[方法说明] 由统一出口追加（这 5 键上游
    preset 无 [当前时点]）。旧实现的 [起盘信息]「技法/目标时间/后台实际成盘时间/推运地点」是自拟文案。
    """
    natal_wrap = _natal_chart_wrap(response)
    predictive_wrap = _predictive_chart_wrap(response)
    params = _predictive_text_params(tool_name, payload)
    birth_lines = _ptext.build_predictive_birth_lines(_predictive_birth_source(response, payload))
    star_lines = _predictive_star_info_lines(natal_wrap) if natal_wrap else []
    natal_config = [*birth_lines, *star_lines]
    sections: list[tuple[str, str]] = [
        ("本命盘配置", _join_lines(natal_config) or "无"),
        ("起盘信息", _join_lines(_predictive_setup_lines(params)) or "无"),
    ]
    if tool_name == "profection":
        # [Q-105 裁决 2026-09-18] 年/月/日小限摘要（粒度 profGrain、起点 profStart；缺省 年/上升）。
        summary = _ptext.build_profection_summary_lines(
            natal_wrap, params, payload.get("profGrain"), payload.get("profStart")
        )
        sections.append(("小限摘要", _join_lines(summary) or "无"))
    directed_lines: list[str] = []
    directed_stars = _build_star_and_lot_position_lines(predictive_wrap)
    if directed_stars:
        directed_lines.extend(["时段盘 星与虚点", *directed_stars])
    directed_cusps = _build_house_cusp_lines(predictive_wrap)
    if directed_cusps:
        directed_lines.extend(["时段盘 宫位宫头", *directed_cusps])
    sections.append(("时段盘配置", _join_lines(directed_lines) or "无"))
    sections.append(
        (
            "相位",
            _join_lines(_build_predictive_cross_aspect_lines(response, _top_level_chart_wrap(response), natal_wrap))
            or _join_lines(_build_aspect_section(predictive_wrap))
            or "无",
        )
    )
    return _render_snapshot_text(sections)
