"""神数 14 支的技法旋钮键表（sync311 F6）：每技法认得哪些 `options` 键、类型/取值域、谁消费它。

为什么要有这张表：`ShenShuInput.options` 此前是**无键表、无校验、未识别键静默丢弃**的透传口——
上游 162 个结果敏感旋钮里 105 个只能靠猜键名经它送达，12 个键名写错（如铁板框架推演读
`options.school`，上游叫 `tiebanSchool`）就一路无声失效；布尔陷阱（`useKey:"0"` 在后端
`bool("0")` 为真）也无人拦。

权威来源（逐键核过，改键先改这里再改调用方）：
  * 后端层：上游 `Horosa-Web/astropy/websrv/web<tech>srv.py` 的 `data.get(...)` 读键（vendored 同树
    `vendor/runtime-source` 逐字节一致）；别名（如 beiji `ke`/`keValue`、nanji `lunarYear`）按后端
    `a or b` 的读法一并收。
  * 本仓层（layer="skill"）：铁板「框架推演层」（上游 KinAstroMain.buildKinAstroSnapshotForFields
    `ov.tiebanSchool/tiebanKeSystem/tiebanKe`）与演禽「演法」（上游 yanqinSchools YANQIN_PRESETS /
    YANQIN_OPTION_META）——它们不发后端，由 JS 层消费。

处理口径（与卜卦 `data.params_ignored` 同范式，AGENTS §5.12）：认得的键按类型归一后应用（回执
`params_applied`）；不认得的键**不转发**并原样回执 `params_ignored` + 一条 envelope 警告；类型/取值不合法
直接结构化报错（`tool.shenshu_invalid_option`），绝不换默认值蒙混。顶层未声明但认得的键（CLI/request
逃生舱写法）与 `options` 同收，`options` 优先。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from horosa_skill.errors import ToolValidationError, bilingual

STEMS: tuple[str, ...] = tuple("甲乙丙丁戊己庚辛壬癸")
BRANCHES: tuple[str, ...] = tuple("子丑寅卯辰巳午未申酉戌亥")
_TRUE = {"1", "true", "yes", "y", "on", "是", "开"}
_FALSE = {"0", "false", "no", "n", "off", "否", "关"}
_INT_RE = re.compile(r"^[+-]?\d+$")
_DATE_RE = re.compile(r"^-?\d{1,5}-\d{1,2}-\d{1,2}$")
_TIME_RE = re.compile(r"^\d{1,2}:\d{1,2}(:\d{1,2})?$")


@dataclass(frozen=True)
class Knob:
    kind: str  # int | num | bool01 | bool | enum | text | ints | ganzhi | date | time | gender_mf
    doc: str
    choices: tuple[Any, ...] = ()
    lo: float | None = None
    hi: float | None = None
    count: int | None = None  # ints：定长
    layer: str = "backend"  # backend=转发后端；skill=本仓 runner / JS 层消费（不发后端）
    aliases: tuple[str, ...] = ()


def _k(kind: str, doc: str, **kw: Any) -> Knob:
    return Knob(kind=kind, doc=doc, **kw)


_KE_MODES = ("auto", "manual")

# 键 → Knob。别名展开在 _expand() 里做（别名与主键共用一份规格，各自按原名转发——后端按 `a or b` 读）。
_RAW_KNOBS: dict[str, dict[str, Knob]] = {
    # webwangjisrv.py:309-330 —— 心易起卦诸键见 WangjiInput 顶层字段（xinyiMethod/upperNum/…）。
    "wangji": {
        "historyYear": _k("int", "所推之年（元会运世值卦；缺省=盘面年）", lo=-4712, hi=9999),
        "classicKey": _k("enum", "典籍", choices=("huangji_jingshi_shu", "xinyi_fawei", "guanwu_yanyi")),
    },
    # webwuzhaosrv.py:476-506,650-667；上游 WuZhaoMain.normalizeCalcOptions（:296-322）同域。
    "wuzhao": {
        "mode": _k("enum", "起例模式（随机诸式见 guidance：揲筮/掷钱按起课时刻定 castSeed；折竹/唐法须 manual 复现，否则回落干支起例）",
                   choices=("ganzhi", "day", "hour", "minute", "tang", "dunhuang", "qian", "zhushu")),
        "number": _k("int", "报数（日/时/分干起盘与干支起例读取；0=不用）", lo=0, hi=9),
        "manual": _k("bool", "手动分爻复现（日/时/分干起盘·唐法揲筮）"),
        "manualSplits": _k("ints", "手动六数（1–35，六个）", count=6, lo=1, hi=35),
        "shifaVariant": _k("enum", "敦煌校录揲筮口径（guayi 挂一回加 / jiaolu 校录原案）", choices=("guayi", "jiaolu")),
        "qianThrows": _k("ints", "以钱代筮六掷阳面数（0–4，六个；qianAuto=false 时读）", count=6, lo=0, hi=4),
        "qianAuto": _k("bool", "以钱代筮每次起盘重掷（true=随机诸式，按 castSeed 定兆）"),
        "zhaoNums": _k("ints", "直输五兆数（1–5，六个；mode=zhushu 读——存档复现配方）", count=6, lo=1, hi=5),
        "xingshenMonth": _k("enum", "行神月制（lunar 农历月 / jieqi 节气月）", choices=("lunar", "jieqi")),
        "mingZhi": _k("enum", "年命支（行年/年立/官禄位用；空=留白）", choices=BRANCHES),
        # 🔴 输入归一化会把嵌套 options.gender 的 'male'/'female' 递归改成 1/0（为八字链设计），而五兆后端
        # 只认 'male'/'female'（webwuzhaosrv.py:497-499）——gender_mf 规格把两种写法都收回后端口径。
        "gender": _k("gender_mf", "性别（行年/年立用；male/female，1/0、男/女 亦可）", choices=("male", "female")),
        "castSeed": _k("int", "随机诸式（敦煌揲筮/自动掷钱）的起兆种子；缺省=起课时刻派生（同刻同兆）", lo=0, hi=2147483646),
    },
    # webtaixuansrv.py:396-417；上游 TaiXuanMain.buildTaiXuanSnapshotForFields（:141-152）。
    "taixuan": {
        "seed": _k("int", "起筮种子（缺省=起课时刻 yyyyMMddHHmm mod 1e9，同刻同卦）", lo=0),
    },
    # webjingjuesrv.py:351；上游 JingJueMain.buildJingJueSnapshotForFields（:105-117）。
    "jingjue": {
        "seed": _k("int", "起筮种子（缺省=起课时刻 yyyyMMddHHmm mod 1e9，同刻同卦）", lo=0),
    },
    # webshenyishusrv.py；上游 techniqueMountSettings SHENYISHU_FIELDS。
    "shenyishu": {
        "hourSource": _k("enum", "时辰来源", choices=("auto", "manual")),
        "manualHour": _k("int", "手动小时（hourSource=manual 读）", lo=0, hi=23),
        "seasonSource": _k("enum", "季令来源", choices=("auto", "manual")),
        "manualSeason": _k("enum", "手动季令（seasonSource=manual 读）", choices=("春", "夏", "秋", "冬")),
    },
    # webshaozisrv.py:170-189。
    "shaozi": {
        "ke": _k("enum", "考刻", choices=("初刻", "二刻", "三刻", "四刻", "五刻", "六刻", "七刻", "八刻")),
        "useKey": _k("bool01", "64 钥匙细调（0/1；后端 bool() 读，字符串 \"0\" 在此归一为 0）"),
        "yearGz": _k("ganzhi", "年柱覆写"), "monthGz": _k("ganzhi", "月柱覆写"),
        "dayGz": _k("ganzhi", "日柱覆写"), "hourGz": _k("ganzhi", "时柱覆写"),
    },
    # webtiebansrv.py:263-299；框架推演三键见上游 KinAstroMain.buildKinAstroSnapshotForFields（:329-346）。
    "tieban": {
        "method": _k("enum", "算法（kunji 坤集取数 / suanpan 算盘法）", choices=("kunji", "suanpan")),
        "startAge": _k("int", "起运年龄", lo=0, hi=120),
        "dayunSteps": _k("int", "大运步数", lo=1, hi=12),
        "yearGz": _k("ganzhi", "年柱覆写"), "monthGz": _k("ganzhi", "月柱覆写"),
        "dayGz": _k("ganzhi", "日柱覆写"), "hourGz": _k("ganzhi", "时柱覆写"),
        "fatherBirthYear": _k("text", "六亲佐证：父生年"), "fatherDeathYear": _k("text", "六亲佐证：父卒年"),
        "motherBirthYear": _k("text", "六亲佐证：母生年"), "motherDeathYear": _k("text", "六亲佐证：母卒年"),
        "siblingsInfo": _k("text", "六亲佐证：兄弟"), "maritalStatus": _k("text", "六亲佐证：婚姻"),
        "childrenInfo": _k("text", "六亲佐证：子女"),
        "tiebanSchool": _k("enum", "框架推演·流派（口径说明，不改推演；缺省 south）", choices=("south", "north"), layer="skill"),
        "tiebanKeSystem": _k("enum", "框架推演·刻制（缺省 qing8）", choices=("qing8", "ming100", "dou12"), layer="skill"),
        "tiebanKe": _k("int", "框架推演·考刻刻位（缺省 1=初刻；清八刻 1–8、十二刻·斗宫 1–12，超出按初刻）", lo=1, hi=12, layer="skill"),
    },
    # webfendjingsrv.py:132-134。
    "fendjing": {
        "stemOverride": _k("bool01", "两头钳手订干（0/1）"),
        "yearStem": _k("enum", "年干（手订时）", choices=STEMS),
        "hourStem": _k("enum", "时干（手订时）", choices=STEMS),
    },
    # webbeijisrv.py:166-175。
    "beiji": {
        "beijiKeMode": _k("enum", "刻法", choices=_KE_MODES, aliases=("keMode",)),
        "beijiKe": _k("int", "刻（手动时 1–8）", lo=1, hi=8, aliases=("keValue", "ke")),
        "useKe": _k("bool01", "强制手动刻（0/1）"),
        "beijiLookupCode": _k("text", "条文码（取数字前 4 位）", aliases=("lookupCode",)),
        "beijiKeyword": _k("text", "关键词检索（≥2 字）", aliases=("keyword",)),
    },
    # webnanjisrv.py:141-162,274-310。
    "nanji": {
        "nanjiMode": _k("enum", "起盘方式（solar 公历精算 / manual 手动古法）", choices=("solar", "manual"), aliases=("mode",)),
        "nanjiAfterLichun": _k("enum", "立春界（手动古法：1 立春后 / 0 立春前）", choices=("1", "0"), aliases=("afterLichun",)),
        "nanjiLunarYear": _k("int", "历年（手动古法）", aliases=("lunarYear",)),
        "nanjiSolarMonth": _k("int", "节月（节气月序，寅=1；手动古法）", lo=1, hi=12, aliases=("solarMonth",)),
        "nanjiDay": _k("int", "日（手动古法）", lo=1, hi=31),
        "nanjiHourZhi": _k("enum", "时支（手动古法）", choices=BRANCHES, aliases=("hourZhi",)),
        "nanjiDayGan": _k("enum", "日干（手动古法）", choices=STEMS, aliases=("dayGan",)),
        "nanjiDayZhi": _k("enum", "日支（手动古法）", choices=BRANCHES, aliases=("dayZhi",)),
        "nanjiSection": _k("text", "宫部（如 子部）", aliases=("section",)),
        "nanjiJianchu": _k("text", "建除（建/除/满/平/定/执/破/危/成/收/开/闭）", aliases=("jianchu",)),
        "nanjiXiu": _k("text", "二十八宿（如 張）", aliases=("xiu",)),
        "nanjiPasswordCode": _k("text", "密码（古法 13 档之一）", aliases=("passwordCode",)),
        "nanjiChart": _k("int", "星图", lo=1, hi=18, aliases=("chart",)),
        "nanjiPalace": _k("enum", "推演宫", choices=BRANCHES, aliases=("palace",)),
        "nanjiDegree": _k("num", "宿度（0–30）", lo=0, hi=30, aliases=("degree",)),
    },
    # webchunzisrv.py:256-321。
    "chunzi": {
        "chunziKeMode": _k("enum", "刻法（仅标注，不影响条文）", choices=("auto", "manual", "none"), aliases=("keMode",)),
        "chunziKe": _k("int", "刻数（手动时 1–10；仅标注）", lo=1, hi=10, aliases=("ke",)),
        "chunziLunarMode": _k("enum", "月日匹配（auto 自动农历 / manual 手动农历 / none 关闭）", choices=("auto", "manual", "none"), aliases=("lunarMode",)),
        "chunziLunarMonth": _k("int", "农历月（manual 时读）", lo=1, hi=12, aliases=("lunarMonth",)),
        "chunziLunarDay": _k("int", "农历日（manual 时读）", lo=1, hi=30, aliases=("lunarDay",)),
        "chunziMansion": _k("text", "宿名（如 室；简繁皆可）", aliases=("mansion",)),
        "chunziHourBranch": _k("enum", "时辰", choices=BRANCHES, aliases=("hourBranch",)),
        "chunziLookupCode": _k("text", "条文代码", aliases=("lookupCode",)),
        "chunziKeyword": _k("text", "关键词", aliases=("keyword",)),
        "chunziTags": _k("text", "多标签（逗号分隔）", aliases=("tags",)),
        "chunziResultLimit": _k("int", "显示数量", lo=5, hi=50, aliases=("resultLimit",)),
    },
    # webxianqinsrv.py:292-296；演法七键见上游 yanqinSchools.js YANQIN_PRESETS / YANQIN_OPTION_META。
    "xianqin": {
        "calendarMode": _k("enum", "入式历法", choices=("autoLunar", "manualLunar", "solarAsLunar")),
        "lunarYear": _k("int", "农历年（manualLunar 时读）"),
        "lunarMonth": _k("int", "农历月（manualLunar 时读；亦作演法月禽/投胎的农历月覆写）", lo=1, hi=12),
        "lunarDay": _k("int", "农历日（manualLunar 时读）", lo=1, hi=30),
        "school": _k("enum", "演法·流派预设（缺省 chibenli 池本理）",
                     choices=("chibenli", "canchou", "guangdong", "jiangxi", "fenghuang", "chenbingyu", "wangfu"), layer="skill"),
        "woBi": _k("enum", "演法·我/彼归属", choices=("fan", "shi", "daoWo"), layer="skill"),
        "xunOffset": _k("bool", "演法·时禽旬头位移", layer="skill"),
        "monthVerse": _k("enum", "演法·月禽口诀", choices=("A", "B"), layer="skill"),
        "huoYaoVariant": _k("enum", "演法·活曜传本", choices=("off", "fanqin", "fanqin2"), layer="skill"),
        "sansuo": _k("enum", "演法·占卜提示侧重", choices=("both", "suobo", "fanqin"), layer="skill"),
        "qinWuxing": _k("enum", "演法·二十八禽五行", choices=("std", "wangfu"), layer="skill"),
    },
    # webcetiansrv.py:393-420,466-505（show* 经 _flag 读，0/false/no/off/空 = 关）。
    "cetian": {
        "method": _k("enum", "排盘算法（book 书法 / kentang 原法）", choices=("book", "kentang")),
        "lunarMode": _k("enum", "农历算法（原法）", choices=("sxtwl", "classic")),
        "starOrder": _k("enum", "十二正曜布法（原法）", choices=("reverse", "forward")),
        "brightnessSchool": _k("enum", "庙旺口径", choices=("yiyu", "quanji")),
        "shenGongMode": _k("enum", "身宫取整", choices=("yizheng", "literal")),
        "daxianMode": _k("enum", "大限起宫", choices=("yiyu", "legacy")),
        "tianluoMode": _k("enum", "天罗地网起法", choices=("benshu", "zhongtian")),
        "palaceNameMode": _k("enum", "宫名体系", choices=("common", "monk")),
        "liunianYear": _k("int", "流年年份（缺省=今年，skill 显式钉住并记入技法卡）", lo=1, hi=9999),
        "liunianQishaMode": _k("enum", "流年七煞起法", choices=("shengshi", "suishu")),
        **{
            key: _k("bool01", label)
            for key, label in (
                ("showBrightness", "显示亮度"), ("showLiunian", "显示流年飞星"), ("showShensha", "显示神煞"),
                ("showZaYao", "显示杂曜"), ("showDuanjue", "显示断诀"), ("showXiu", "显示廿八宿三日宫"),
                ("showBianyao", "显示十干变曜"), ("showWuXingJu", "显示五行局"), ("showSihua", "显示四化"),
                ("showFlying", "显示飞星格局"), ("showSolarTerm", "显示节气"),
            )
        },
        "location": _k("text", "地点名（亦可用顶层 pos）", aliases=("place",)),
    },
    # webqizhengkinsrv.py:481-585。
    "qizhengkin": {
        "qizhengKinCurrentYear": _k("int", "大运所在年（缺省=今年，skill 显式钉住并记入技法卡）", lo=1, hi=9999, aliases=("currentYear",)),
        "qizhengKinTransitMode": _k("enum", "过运（none/now 此刻/same 出生时刻/custom 指定时刻）", choices=("none", "now", "same", "custom"), aliases=("transitMode",)),
        "qizhengKinTransitDate": _k("date", "过运日期（custom）", aliases=("transitDate",)),
        "qizhengKinTransitTime": _k("time", "过运时间（custom）", aliases=("transitTime",)),
        "qizhengKinElectionalStartDate": _k("date", "择时起日（缺省=出生日）", aliases=("electionalStartDate",)),
        "qizhengKinElectionalCriteria": _k("enum", "择时事项", choices=("general", "marriage", "travel", "business", "moving"), aliases=("electionalCriteria",)),
        "qizhengKinElectionalDays": _k("int", "择时天数", lo=1, hi=60, aliases=("electionalDays",)),
        "locationName": _k("text", "地点名（亦可用顶层 pos）", aliases=("location",)),
    },
}


def _expand(table: dict[str, Knob]) -> dict[str, Knob]:
    out: dict[str, Knob] = {}
    for key, knob in table.items():
        out[key] = knob
        for alias in knob.aliases:
            out[alias] = Knob(kind=knob.kind, doc=f"= {key}", choices=knob.choices, lo=knob.lo, hi=knob.hi,
                              count=knob.count, layer=knob.layer)
    return out


SHENSHU_OPTION_KNOBS: dict[str, dict[str, Knob]] = {tool: _expand(table) for tool, table in _RAW_KNOBS.items()}


def _fmt_bound(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def options_doc(tool: str) -> dict[str, str]:
    """guidance 用的键表（主键；别名附注）。tools/list 不带它（预算），agent 经 horosa_agent_guidance 取。"""
    out: dict[str, str] = {}
    for key, knob in _RAW_KNOBS.get(tool, {}).items():
        spec = knob.kind
        if knob.choices:
            spec = "/".join(str(c) for c in knob.choices)
        elif knob.kind in {"int", "num", "ints"} and (knob.lo is not None or knob.hi is not None):
            lo = "" if knob.lo is None else _fmt_bound(knob.lo)
            hi = "" if knob.hi is None else _fmt_bound(knob.hi)
            spec = f"{knob.kind} {lo}–{hi}" + (f" ×{knob.count}" if knob.count else "")
        alias = f"（别名 {'/'.join(knob.aliases)}）" if knob.aliases else ""
        out[key] = f"[{spec}] {knob.doc}{alias}"
    return out


def _bad(tool: str, key: str, value: Any, expected: str) -> ToolValidationError:
    return ToolValidationError(
        bilingual(
            f"{tool} 旋钮 {key}={value!r} 不合法：应为 {expected}。",
            f"{tool} option {key}={value!r} is invalid: expected {expected}.",
        ),
        code="tool.shenshu_invalid_option",
        details={"tool": tool, "key": key, "value": value, "expected": expected,
                 "hint": f"键表见 horosa_agent_guidance(tool_name=\"{tool}\") 的 options_keys。"},
    )


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and _INT_RE.match(value.strip()):
        return int(value.strip())
    return None


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in _TRUE:
            return True
        if text in _FALSE:
            return False
    return None


def _in_range(knob: Knob, number: float) -> bool:
    return (knob.lo is None or number >= knob.lo) and (knob.hi is None or number <= knob.hi)


def _range_text(knob: Knob) -> str:
    lo = "-∞" if knob.lo is None else _fmt_bound(knob.lo)
    hi = "+∞" if knob.hi is None else _fmt_bound(knob.hi)
    return f"{lo}–{hi}"


def coerce_knob(tool: str, key: str, knob: Knob, value: Any) -> Any:
    """按规格归一一个值；不合法抛 tool.shenshu_invalid_option（不换默认值）。"""
    kind = knob.kind
    if kind == "int":
        number = _as_int(value)
        if number is None or not _in_range(knob, number):
            raise _bad(tool, key, value, f"整数 {_range_text(knob)}")
        return number
    if kind == "num":
        try:
            number = float(value) if not isinstance(value, bool) else None
        except (TypeError, ValueError):
            number = None
        if number is None or not _in_range(knob, number):
            raise _bad(tool, key, value, f"数值 {_range_text(knob)}")
        return number
    if kind in {"bool01", "bool"}:
        flag = _as_bool(value)
        if flag is None:
            raise _bad(tool, key, value, "布尔（true/false 或 1/0）")
        return (1 if flag else 0) if kind == "bool01" else flag
    if kind == "enum":
        text = f"{value}".strip() if not isinstance(value, bool) else ""
        if text not in {str(c) for c in knob.choices}:
            raise _bad(tool, key, value, "/".join(str(c) for c in knob.choices))
        return text
    if kind == "text":
        if isinstance(value, (dict, list, bool)):
            raise _bad(tool, key, value, "文本")
        text = f"{value}".strip()
        if not text:
            raise _bad(tool, key, value, "非空文本")
        return text
    if kind == "ints":
        items: list[Any]
        if isinstance(value, str):
            items = [x for x in re.split(r"[,，\s]+", value.strip()) if x]
        elif isinstance(value, (list, tuple)):
            items = list(value)
        else:
            raise _bad(tool, key, value, f"{knob.count} 个整数的数组（或逗号分隔串）")
        numbers = [_as_int(x) for x in items]
        if (knob.count is not None and len(numbers) != knob.count) or any(
            n is None or not _in_range(knob, n) for n in numbers
        ):
            raise _bad(tool, key, value, f"{knob.count} 个 {_range_text(knob)} 的整数")
        return numbers
    if kind == "gender_mf":
        text = f"{value}".strip().lower() if not isinstance(value, bool) else ("1" if value else "0")
        mapped = {"male": "male", "1": "male", "男": "male", "m": "male",
                  "female": "female", "0": "female", "女": "female", "f": "female"}.get(text)
        if mapped is None:
            raise _bad(tool, key, value, "male/female（或 1/0、男/女）")
        return mapped
    if kind == "ganzhi":
        text = f"{value}".strip()
        if len(text) != 2 or text[0] not in STEMS or text[1] not in BRANCHES:
            raise _bad(tool, key, value, "干支两字（如 甲子）")
        return text
    if kind == "date":
        text = f"{value}".strip().replace("/", "-")
        if not _DATE_RE.match(text):
            raise _bad(tool, key, value, "日期 YYYY-MM-DD")
        return text
    if kind == "time":
        text = f"{value}".strip()
        if not _TIME_RE.match(text):
            raise _bad(tool, key, value, "时间 HH:mm[:ss]")
        return text
    raise _bad(tool, key, value, f"未知规格 {kind}")  # 表写错时响亮失败


@dataclass
class ResolvedOptions:
    backend: dict[str, Any]
    skill: dict[str, Any]
    applied: list[str]
    ignored: list[str]


def resolve_shenshu_options(
    tool: str, payload: dict[str, Any], declared_fields: set[str], generic_keys: set[str]
) -> ResolvedOptions:
    """合并 `options` 与顶层认得的键 → 按层分拣 + 类型归一；未识别键回执（不转发）。

    `declared_fields`：该工具输入模型声明的字段（它们有自己的消费方，不当旋钮处理）。
    `generic_keys`：跨技法通用的已知键（BirthInput 族、闸门三键、response_view …）——dispatch/hecan
    会把整份出生资料原样灌给每个技法，这些不是「用户写错的旋钮」，不回执为 ignored。
    """
    knobs = SHENSHU_OPTION_KNOBS.get(tool, {})
    raw_options = payload.get("options")
    if raw_options is not None and not isinstance(raw_options, dict):
        raise _bad(tool, "options", raw_options, "对象（键 → 值）")
    merged: dict[str, Any] = {}
    ignored: list[str] = []
    for key, value in payload.items():
        if key == "options" or key in declared_fields:
            continue
        if key in knobs:
            merged[key] = value
        elif key not in generic_keys:
            ignored.append(key)
    for key, value in (raw_options or {}).items():
        if key in knobs:
            merged[key] = value
        else:
            ignored.append(key)
    backend: dict[str, Any] = {}
    skill: dict[str, Any] = {}
    applied: list[str] = []
    for key, value in merged.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            continue  # 上游 '' 哨兵 = 随盘/自出：不发键即后端默认（与挂载 prune 同口径）
        knob = knobs[key]
        coerced = coerce_knob(tool, key, knob, value)
        (skill if knob.layer == "skill" else backend)[key] = coerced
        applied.append(key)
    return ResolvedOptions(backend=backend, skill=skill, applied=sorted(applied), ignored=sorted(set(ignored)))
