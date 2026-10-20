"""中国术数族的载荷与选项归一化：日界开关、六壬 / 金口诀 / 三式 / 奇门 / 正传 / 神数 / 皇极经世。"""
from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any

from horosa_skill.errors import ToolValidationError, bilingual
from horosa_skill.schemas.tools import (
    BaZiBirthInput,
    BirthInput,
    LiuRengGodsInput,
    NongliTimeInput,
    ZiWeiBirthInput,
)
from horosa_skill.service._common import _GANZHI_BRANCHES, _only_payload_keys
from horosa_skill.service._context import _degrade


def _day_boundary_switches(payload: dict[str, Any], keys: tuple[str, ...] = ("after23NewDay", "lateZiHourUseNextDay")) -> dict[str, int]:
    """日界(after23NewDay)/晚子时时柱(lateZiHourUseNextDay)开关：仅显式给定时发送。

    None 不发送 → 后端按其默认(1/1)起算，与未传时字节级等价（零默认漂移）。
    """
    switches: dict[str, int] = {}
    for key in keys:
        value = payload.get(key)
        if value is not None:
            switches[key] = 1 if value in (1, True, "1", "true", "True") else 0
    return switches


def _liureng_remote_payload(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "liureng_runyear":
        return _only_payload_keys(
            payload,
            (
                "date",
                "time",
                "zone",
                "lat",
                "lon",
                "after23NewDay",
                "lateZiHourUseNextDay",
                "ad",
                "gender",
                "guaYearGanZi",
                "guaDate",
                "guaTime",
                "guaZone",
                "guaLon",
                "guaLat",
                "guaAd",
                "guaAfter23NewDay",
            ),
        )
    return _only_payload_keys(
        payload,
        ("date", "time", "zone", "lat", "lon", "after23NewDay", "lateZiHourUseNextDay", "ad", "yue", "isDiurnal"),
    )


def _liureng_chart_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in {
            "date": payload.get("guaDate") or payload.get("date"),
            "time": payload.get("guaTime") or payload.get("time"),
            "zone": payload.get("guaZone") or payload.get("zone"),
            "lat": payload.get("guaLat") or payload.get("lat"),
            "lon": payload.get("guaLon") or payload.get("lon"),
            "gpsLat": payload.get("gpsLat"),
            "gpsLon": payload.get("gpsLon"),
            "ad": payload.get("guaAd") or payload.get("ad", 1),
            "hsys": 0,
            "tradition": False,
            "predictive": False,
            "zodiacal": 0,
        }.items()
        if value is not None
    }


def _liureng_time_alg(payload: dict[str, Any]) -> int | None:
    """大六壬起课时间算法（上游 v3.11 [Q-386/T-367]：LiuRengController 改读 timeAlg，缺省 RealSun=0）。

    `options.timeAlg` 优先、顶层 `timeAlg` 次之（三式合一子盘把共享 timeAlg 放顶层）；缺省返回 None =
    不发送（后端缺省真太阳时，与上游 LIURENG_PAGE_SETTINGS.timeAlg def 0 同值）。上游页面只给两档
    （LiuRengMain.js:3916 oneOf [0, 1]），认不出的值报错而不静默回落。
    """
    options = payload.get("options") if isinstance(payload.get("options"), dict) else {}
    raw = options.get("timeAlg")
    if raw is None:
        raw = payload.get("timeAlg")
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool) or str(raw).strip() not in {"0", "1"}:
        raise ToolValidationError(
            bilingual(
                f"大六壬 timeAlg 取值无效：{raw!r}（可选：0=真太阳时 / 1=直接时间）。",
                f"liureng timeAlg is invalid: {raw!r} (allowed: 0=true solar time / 1=clock time).",
            ),
            code="tool.liureng_invalid_option",
            details={"field": "timeAlg", "value": raw, "allowed": [0, 1]},
        )
    return int(str(raw).strip())


def _liureng_gods_payload(tool_name: str, payload: dict[str, Any], time_alg: int | None) -> dict[str, Any]:
    """`/liureng/gods` 起课请求 —— 行年盘按**起课时刻**（gua*）起课，同上游 genGodsParams(calcFields)。

    此前 liureng_runyear 只打 `/liureng/runyear`，而该端点只回 {age, ageCycle, year}（LiuRengHelper.runYear），
    没有 liureng 盘 → 四课 / 三传 / 行年整段落空（live 实测）；上游页面是 gods（起课）+ runyear（行年）两请求。
    """
    base = _liureng_remote_payload("liureng_gods", payload)
    if tool_name == "liureng_runyear":
        for key, gua_key in (("date", "guaDate"), ("time", "guaTime"), ("zone", "guaZone"),
                             ("lat", "guaLat"), ("lon", "guaLon"), ("ad", "guaAd"),
                             ("after23NewDay", "guaAfter23NewDay")):
            if payload.get(gua_key) is not None and payload.get(gua_key) != "":
                base[key] = payload[gua_key]
    if time_alg is not None:
        base["timeAlg"] = time_alg
    return base


def _liureng_runyear_from(response: dict[str, Any]) -> dict[str, Any] | None:
    """`/liureng/runyear` 的回包是裸 {age, ageCycle, year}（LiuRengHelper.runYear；`_call_remote` 保证是 dict）。

    v0.41.1 去掉了「包了一层 runyear/runYear」的兼容分支：真后端从没回过那个形状，只有一个旧测试替身在回——那条测试
    因此「因为错误的原因通过」（tests/test_sync311_sanshi.py 对真后端的 live 断言是「该端点只回裸 …」）。
    """
    return response if response.get("year") else None


def _gua_year_ganzi(liureng: Any) -> str:
    """上游 resolveGuaYearGanZi（LiuRengMain.js:183）：起课盘年柱 → 行年所用的卦年干支。"""
    if not isinstance(liureng, dict):
        return ""
    four = liureng.get("fourColumns") if isinstance(liureng.get("fourColumns"), dict) else {}
    year = four.get("year")
    candidates = [year.get("ganzi") if isinstance(year, dict) else year]
    nongli = liureng.get("nongli") if isinstance(liureng.get("nongli"), dict) else {}
    candidates += [nongli.get("yearGanZi"), nongli.get("yearJieqi"), nongli.get("year")]
    for text in candidates:
        match = re.search(r"[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]", str(text or ""))
        if match:
            return match.group(0)
    return ""


# 金口诀排盘流派五键 + 时间基准的词表与缺省（上游 JinKouMain.js:857-864 JINKOU_PAGE_SETTINGS，首项 = 缺省）。
# 上游本地引擎对认不出的值静默归缺省（buildJinKouData `=== 'jiaojie' ? … : 'zhongqi'`），headless 改为报错。
_JINKOU_SCHOOL_VOCAB: dict[str, tuple[str, ...]] = {
    "schoolYueJiang": ("zhongqi", "jiaojie"),
    "schoolGuiTable": ("shiwu", "liuren"),
    "schoolGuiPan": ("di", "tian"),
    "panShi": ("yang", "yin"),
    "soilChangSheng": ("shen", "yin"),
    "timeBasis": ("direct", "trueSolar"),
}


def _jinkou_option_error(field: str, value: Any, allowed: list[Any]) -> ToolValidationError:
    return ToolValidationError(
        bilingual(
            f"金口诀 {field} 取值无效：{value!r}（可选：{' / '.join(str(a) for a in allowed)}）。",
            f"jinkou {field} is invalid: {value!r} (allowed: {', '.join(str(a) for a in allowed)}).",
        ),
        code="tool.jinkou_invalid_option",
        details={"field": field, "value": value, "allowed": allowed},
    )


def _jinkou_validate_options(options: dict[str, Any]) -> None:
    for key, allowed in _JINKOU_SCHOOL_VOCAB.items():
        value = options.get(key)
        if value not in (None, "") and value not in allowed:
            raise _jinkou_option_error(key, value, list(allowed))
    for key in ("yueJiang", "zhanShi"):
        value = options.get(key)
        if value not in (None, "", "auto") and (len(str(value)) != 1 or str(value) not in _GANZHI_BRANCHES):
            raise _jinkou_option_error(key, value, ["auto", *_GANZHI_BRANCHES])
    wuxing = options.get("wuxing")
    if wuxing not in (None, "") and wuxing not in ("木", "火", "土", "金", "水"):
        raise _jinkou_option_error("wuxing", wuxing, ["木", "火", "土", "金", "水"])


def _jinkou_school_overrides(options: dict[str, Any]) -> list[str]:
    """上游 schoolsAllDefault（JinKouMain.js:1288-1294）的镜像：返回非缺省的流派/盘法键（空 = 全缺省 → ken 路径）。"""
    return [
        key for key, allowed in _JINKOU_SCHOOL_VOCAB.items()
        if key != "timeBasis" and (options.get(key) or allowed[0]) != allowed[0]
    ]


def _jinkou_resolve_difen(raw: Any, time_text: Any) -> str:
    """上游 resolveJinKouDiFen(diFen, diFenAuto, timeZi, hasExistingPan=false)（JinKouState.js:14）的首次起课口径：
    未指定 / 'auto' → 占时支（liureng.nongli.time 的地支），取不到才落「子」；显式给定须是单个地支。"""
    text = str(raw or "").strip()
    if text in ("", "auto"):
        match = re.search(f"[{_GANZHI_BRANCHES}]", str(time_text or ""))
        return match.group(0) if match else "子"
    if len(text) != 1 or text not in _GANZHI_BRANCHES:
        raise _jinkou_option_error("diFen", raw, ["auto", *_GANZHI_BRANCHES])
    return text


def _jinkou_manual_branch(value: Any) -> str:
    """月将/占时手选（上游 fetchJinKouPan：`opt.yueJiang && opt.yueJiang !== 'auto' ? … : ''`）。"""
    text = str(value or "").strip()
    return "" if text in ("", "auto") else text


def _sanshi_liureng_options(payload: dict[str, Any]) -> dict[str, Any]:
    """三式合一六壬层口径（liureng_options → JS 工具 sanshiunited 的 options.liureng）。

    上游三式合一只支持正时正将起课法（pickSanshiLiurengCastOpts 锁 castMethod:'zheng'，SanShiUnitedMain.js:957），
    其余六壬层口径（换将/分昼夜/涉害/阴阳系/年神序/土旺衰/贵人）的词表由 JS 按 vendored SANSHI_PAGE_SETTINGS 校验；
    时间算法是三盘共享的顶层 timeAlg。这里只挡「形状错 / 上游锁死的键」。
    """
    raw = payload.get("liureng_options")
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ToolValidationError(
            bilingual("liureng_options 须为对象。", "liureng_options must be an object."),
            code="tool.sanshiunited_invalid_option",
            details={"field": "liureng_options", "value": raw},
        )
    if raw.get("castMethod") not in (None, "", "zheng"):
        raise ToolValidationError(
            bilingual(
                f"三式合一只支持正时正将起课法（castMethod=zheng），收到 {raw.get('castMethod')!r}；其余起课法请单独调 liureng_gods。",
                f"sanshiunited only supports castMethod=zheng (got {raw.get('castMethod')!r}); use liureng_gods for other methods.",
            ),
            code="tool.sanshiunited_invalid_option",
            details={"field": "liureng_options.castMethod", "value": raw.get("castMethod"), "allowed": ["zheng"]},
        )
    if "timeAlg" in raw:
        raise ToolValidationError(
            bilingual(
                "三式合一的时间算法是三盘共享的顶层 timeAlg，liureng_options 里不接受 timeAlg。",
                "sanshiunited timeAlg is the shared top-level field; liureng_options.timeAlg is not accepted.",
            ),
            code="tool.sanshiunited_invalid_option",
            details={"field": "liureng_options.timeAlg", "value": raw.get("timeAlg")},
        )
    return dict(raw)


def _raise_js_option_error(tool: str, js_result: Any) -> None:
    """JS 工具按上游词表校验口径参数，认不出的值回 data.ok=false + error{field,value,allowed}（不静默回落缺省）。"""
    data = js_result.get("data") if isinstance(js_result, dict) else None
    if not isinstance(data, dict) or data.get("ok") is not False:
        return
    error = data.get("error") if isinstance(data.get("error"), dict) else {}
    raise ToolValidationError(
        bilingual(
            str(error.get("message") or f"{tool} 参数无效。"),
            f"{tool}: invalid option {error.get('field')!r}={error.get('value')!r} (allowed: {error.get('allowed')}).",
        ),
        code=f"tool.{tool}_invalid_option",
        details={k: error.get(k) for k in ("field", "value", "allowed") if k in error},
    )


# 神数正传·铁算心易查询层（sync311 F14）。表键即 vendored zhengchuanXinyiLocal.js 的 XINYI_* 常量（繁体）。
_ZC_XINYI_ITEMS = ("父母", "兄弟", "姻緣", "子孫", "官祿", "疾病")
_ZC_XINYI_SOUNDS = ("日", "月", "星", "辰", "水", "火", "土", "石", "平", "上", "去", "入", "開", "發", "收", "閉")
_ZC_XINYI_KE = ("一刻", "二刻", "三刻", "四刻", "五刻", "六刻", "七刻", "八刻")
_ZC_XINYI_GONG = ("乾", "兌", "離", "震", "巽", "坎", "艮", "坤")
_ZC_XINYI_ZHI = tuple("子丑寅卯辰巳午未申酉戌亥")
_ZC_SIMPLIFIED = {"姻缘": "姻緣", "子孙": "子孫", "官禄": "官祿", "开": "開", "发": "發", "闭": "閉", "兑": "兌", "离": "離"}
# 上游挂载缺省（aiAnalysisContext.js:3240-3243，挂载自检 F-53）：父母·日·一刻·乾·子（与页面缺省同）；
# 此前 skill 只透传显式键 → 缺省心易查询 [条文秘数查询]/[八刻分命] 整段不产。
_ZC_XINYI_DEFAULTS = {"item": "父母", "sound": "日", "ke": "一刻", "gong": "乾", "xqZhi": "子"}


def _zhengchuan_xinyi_query(payload: dict[str, Any]) -> dict[str, Any]:
    query: dict[str, Any] = {}
    for key, default in _ZC_XINYI_DEFAULTS.items():
        value = payload.get(key)
        query[key] = default if value is None or f"{value}".strip() == "" else value
    ke = query["ke"]
    # 八刻分命表键是「一刻…八刻」：数字 1–8（含 "3"）按序映射；此前 ke 被 schema 限成 int 直送，查表恒空。
    ke_text = f"{ke}".strip()
    if ke_text.isdigit() and 1 <= int(ke_text) <= 8:
        ke_text = _ZC_XINYI_KE[int(ke_text) - 1]
    if ke_text not in _ZC_XINYI_KE:
        raise ToolValidationError(
            bilingual(
                f"铁算心易 ke={ke!r} 不合法：应为 1–8 或 {'/'.join(_ZC_XINYI_KE)}。",
                f"zhengchuan xinyi ke={ke!r} is invalid: use 1-8 or {'/'.join(_ZC_XINYI_KE)}.",
            ),
            code="tool.zhengchuan_invalid_xinyi_ke",
            details={"ke": ke, "allowed": list(_ZC_XINYI_KE)},
        )
    query["ke"] = ke_text
    unknown: list[str] = []
    for key, allowed in (("item", _ZC_XINYI_ITEMS), ("sound", _ZC_XINYI_SOUNDS), ("gong", _ZC_XINYI_GONG), ("xqZhi", _ZC_XINYI_ZHI)):
        text = f"{query[key]}".strip()
        text = _ZC_SIMPLIFIED.get(text, text)
        query[key] = text
        if text not in allowed:
            unknown.append(f"{key}={text}")
    if unknown:
        # 上游对表外值同样是「查不到 → 该段不出」；这里照走，但不静默（warnings 点名 + 列表内可选值）。
        _degrade(
            "铁算心易查询项不在古籍表内（%s）：对应查询段不出", "、".join(unknown),
            note=f"铁算心易：{'、'.join(unknown)} 不在表内（项目 {'/'.join(_ZC_XINYI_ITEMS)}；宫 {'/'.join(_ZC_XINYI_GONG)}），对应查询段不出。",
        )
    for key in ("xqYushu", "gender"):
        if payload.get(key) is not None:
            query[key] = payload[key]
    return query


def _ken_datetime_parts(payload: dict[str, Any]) -> dict[str, int]:
    date_text = str(payload.get("date") or "")
    time_text = str(payload.get("time") or "")
    date_bits = [int(p) for p in date_text.split("-") if p.strip().lstrip("-").isdigit()]
    time_bits = [int(p) for p in time_text.split(":") if p.strip().isdigit()]
    while len(date_bits) < 3:
        date_bits.append(1)
    while len(time_bits) < 3:
        time_bits.append(0)
    return {
        "year": date_bits[0],
        "month": date_bits[1],
        "day": date_bits[2],
        "hour": time_bits[0],
        "minute": time_bits[1],
        "second": time_bits[2],
    }


# 奇门起局法 / 盘式 / 排盘家词表（上游 DunJiaCalc.js QIJU_METHOD_OPTIONS / SCHOOL_OPTIONS / PAIPAN_OPTIONS；
# 5=综合 为引擎保留分支）。缺省起局法 = 上游 DunJiaMain.js:128 DEFAULT_OPTIONS.qijuMethod 'zhirun'（置闰）——
# 此前 skill 缺省发 chaibu（且把 maoshan/wurun 也压成 chaibu），而本地脚手架 calcDunJia 缺省 zhirun：
# ken 按拆补算盘、[盘型]「定局法」却标置闰，同一张盘两套口径（live 实测局数文本「阴遁一局中」vs「中元」）。
_QIMEN_QIJU_METHODS = ("zhirun", "chaibu", "maoshan", "wurun", "shuzi")
_QIMEN_SCHOOLS = ("转盘", "飞盘", "混合")
_QIMEN_PAIPAN_TYPES = (0, 1, 2, 3, 4, 5, 6)


def _js_parse_int(value: Any) -> int | None:
    """JS `parseInt(v, 10)` 口径（DunJiaCalc normalizeNum）：前导整数前缀；bool/None/非数 → NaN(None)。"""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if math.isfinite(value) else None
    match = re.match(r"\s*([+-]?\d+)", str(value))
    return int(match.group(1)) if match else None


def _qimen_option_error(field: str, value: Any, allowed: list[Any]) -> ToolValidationError:
    return ToolValidationError(
        bilingual(
            f"奇门 {field} 取值无效：{value!r}（可选：{' / '.join(str(a) for a in allowed)}）。",
            f"qimen {field} is invalid: {value!r} (allowed: {', '.join(str(a) for a in allowed)}).",
        ),
        code="tool.qimen_invalid_option",
        details={"field": field, "value": value, "allowed": allowed},
    )


def _qimen_effective_options(payload: dict[str, Any]) -> dict[str, Any]:
    """奇门盘面口径单源：顶层起局三开关（QimenInput 声明的 timeAlg/after23NewDay/lateZiHourUseNextDay）∪
    `options`，options 优先（与 qimenzeri 扫描同一合并）。本地脚手架、路由判据、ken 请求、择日扫描全吃这一份。

    此前本地脚手架只看 `options`（顶层 after23NewDay/timeAlg 在 JS 侧被丢，[盘型]「换日/时间算法」标签与 ken 不一），
    且起局法缺省与上游不同（见 _QIMEN_QIJU_METHODS 注）。认不出的起局法/盘式/排盘家/时间算法报错，不静默归一。
    """
    # 顶层 qijuMethod/paiPanType/school 也认：澄清闸 elicitation 表单按 `values` 把答案落在顶层同名键。
    options: dict[str, Any] = {
        key: payload[key]
        for key in ("timeAlg", "after23NewDay", "lateZiHourUseNextDay", "qijuMethod", "paiPanType", "school")
        if payload.get(key) is not None
    }
    raw = payload.get("options")
    if isinstance(raw, dict):
        options.update(raw)
    method = options.get("qijuMethod")
    if method in (None, ""):
        options["qijuMethod"] = "zhirun"
    elif method not in _QIMEN_QIJU_METHODS:
        raise _qimen_option_error("qijuMethod", method, list(_QIMEN_QIJU_METHODS))
    if options["qijuMethod"] == "shuzi" and not re.sub(r"[^0-9]", "", str(options.get("shuziReportNumber") or "")):
        # 上游 calcDunJia：报数空 → 静默退节气拆补（「占位不崩」，页面上有输入框可见）；headless 没有那个框，直接报错。
        raise ToolValidationError(
            bilingual(
                "阴盘报数起局（qijuMethod=shuzi）需要 options.shuziReportNumber（报数，如 258）。",
                "qijuMethod=shuzi needs options.shuziReportNumber (the reported number, e.g. 258).",
            ),
            code="tool.qimen_invalid_option",
            details={"field": "shuziReportNumber", "value": options.get("shuziReportNumber")},
        )
    school = options.get("school")
    if school not in (None, "") and school not in _QIMEN_SCHOOLS:
        raise _qimen_option_error("school", school, list(_QIMEN_SCHOOLS))
    if options.get("paiPanType") not in (None, ""):
        pai_pan = _js_parse_int(options.get("paiPanType"))
        if pai_pan not in _QIMEN_PAIPAN_TYPES:
            raise _qimen_option_error("paiPanType", options.get("paiPanType"), list(_QIMEN_PAIPAN_TYPES))
        options["paiPanType"] = pai_pan
    if options.get("timeAlg") not in (None, ""):
        # 上游奇门只两档（DunJiaCalc.js TIME_ALG_OPTIONS）；JS normalizeTimeAlg 只认数字 1（`=== 1`），
        # 字符串 "1" 会被当真太阳时 —— 故此处统一收成 int，不让两层对同一个值各读一套。
        time_alg = options.get("timeAlg")
        if isinstance(time_alg, bool) or str(time_alg).strip() not in {"0", "1"}:
            raise _qimen_option_error("timeAlg", time_alg, [0, 1])
        options["timeAlg"] = int(str(time_alg).strip())
    return options


def _qimen_local_route_reasons(options: dict[str, Any]) -> list[str]:
    """上游路由单源 isQimenLocalRoute / qimenLocalOnlyOverrides（DunJiaCalc.js:1195-1226）的 Python 镜像。

    非空 = 走本地 calcDunJia（年/月/日/刻/金函家、飞盘/混合、阴盘报数、七组本地口径任一非缺省）——ken `/qimen/pan`
    只收排盘家/起局法/盘式，这些口径后端不认、合并阶段也不施加，照打 ken 会得到「按缺省出盘、[盘型]却标所选」。
    Python 先判（决定打不打 ken），JS 用 vendored isQimenLocalRoute 再判一次并回报 `route`，两边不一致即报错
    （tool.qimen_route_check_failed）——上游改了判据，这里当场红，而不是静默分叉。
    """
    reasons: list[str] = []
    pai_pan = _js_parse_int(options.get("paiPanType"))
    if (3 if pai_pan is None else pai_pan) not in (3, 5):
        reasons.append("paiPanType")
    if options.get("school") in ("飞盘", "混合"):
        reasons.append("school")
    if options.get("qijuMethod") == "shuzi":
        reasons.append("qijuMethod")
    zhi_shi = _js_parse_int(options.get("zhiShiType"))
    if (0 if zhi_shi is None else zhi_shi) != 0:
        reasons.append("zhiShiType")
    leap_days = _js_parse_int(options.get("zhirunLeapDays"))
    if options.get("qijuMethod") == "zhirun" and (9 if leap_days is None else leap_days) != 9:
        reasons.append("zhirunLeapDays")
    for key, default in (("godsPreset", "baihu_xuanwu"), ("jiGongMode", "kun"), ("anGanMode", "off")):
        if options.get(key) and options.get(key) != default:
            reasons.append(key)
    if options.get("kongMarkBoth"):
        reasons.append("kongMarkBoth")
    shift = _js_parse_int(options.get("shiftPalace")) or 0
    shift = 0 if shift < 0 else (shift % 8 if shift > 7 else shift)
    if shift and options.get("shiftZhiFuMode") == "recalc":
        reasons.append("shiftZhiFuMode")
    return reasons


def _parse_solar_datetime_text(text: Any) -> dict[str, int] | None:
    """上游 DunJiaCalc.js parseDateTimeText：从 nongli.birth（真太阳时串）取年月日时分秒。"""
    normalized = str(text or "").strip().replace("T", " ", 1).replace("Z", " ", 1).strip()
    match = re.search(r"([-+]?\d{1,6})[/-](\d{1,2})[/-](\d{1,2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?", normalized)
    if not match:
        return None
    year, month, day, hour, minute, second = match.groups()
    return {
        "year": int(year), "month": int(month), "day": int(day),
        "hour": int(hour), "minute": int(minute), "second": int(second or 0),
    }


def _parse_taiyi_datetime_text(text: Any) -> dict[str, int] | None:
    """上游 TaiYiCalc.js / JinKouCalc.js parseDateTimeText（行首锚定、分可单位数）：nongli.birth → 年月日时分秒。"""
    match = re.match(r"^(-?\d{1,6})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?", str(text or "").strip())
    if not match:
        return None
    year, month, day, hour, minute, second = match.groups()
    return {
        "year": int(year), "month": int(month), "day": int(day),
        "hour": int(hour), "minute": int(minute), "second": int(second or 0),
    }


def _qimen_ken_payload(payload: dict[str, Any], options: dict[str, Any], nongli: Any) -> dict[str, Any]:
    """`/qimen/pan` 请求体，逐键对齐上游 fetchQimenPan（DunJiaCalc.js:1473-1495）。

    时间：timeAlg=0（缺省）用 nongli.birth 校正后的真太阳时分量（上游 resolveCalcDateTime）——此前 skill 恒发钟表时，
    ken 只把 realSunTime 当回显，于是九宫按钟表时起、时柱按真太阳时标，两套时辰。
    """
    nongli = nongli if isinstance(nongli, dict) else {}
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    display_solar = context.get("displaySolarTime") or nongli.get("birth", "")
    parts: dict[str, int] = _ken_datetime_parts(payload)
    if options.get("timeAlg") != 1:
        solar = _parse_solar_datetime_text(nongli.get("birth") or context.get("displaySolarTime"))
        if solar:
            parts = {**parts, **solar}
    method = options.get("qijuMethod") or "zhirun"
    return {
        **parts,
        "zone": payload.get("zone"),
        "qimenMode": _ken_qimen_mode(options),
        "qijuMethod": method,
        "option": 2 if method == "zhirun" else 1,
        "school": options.get("school") or "转盘",
        "date": payload.get("date"),
        "time": payload.get("time"),
        "realSunTime": display_solar,
        "jiedelta": nongli.get("jiedelta", ""),
        # 显式日界/晚子时开关直达权威引擎（缺省不发→引擎默认 1/1）。
        **_day_boundary_switches(options),
    }


def _ken_qimen_mode(options: dict[str, Any]) -> str:
    explicit = options.get("qimenMode")
    if isinstance(explicit, str) and explicit:
        return explicit
    mode_by_paipan = {0: "year", 2: "golden", 4: "minute", 5: "overall"}
    pai_pan = options.get("paiPanType")
    try:
        return mode_by_paipan.get(int(pai_pan), "hour")
    except (TypeError, ValueError):
        return "hour"


# 跨技法通用的已知顶层键：dispatch/hecan 把整份出生资料（BirthInput 族全字段）原样灌给每个技法，
# 它们不是「写错的神数旋钮」→ 不回执 params_ignored（否则每次合参都刷一屏噪声警告）。
_SHENSHU_GENERIC_KEYS: frozenset[str] = frozenset(
    set(BirthInput.model_fields)
    | set(ZiWeiBirthInput.model_fields)
    | set(BaZiBirthInput.model_fields)
    | set(LiuRengGodsInput.model_fields)
    | set(NongliTimeInput.model_fields)
    | {"request", "save_result", "response_view", "question", "name", "pos", "ad"}
)


# 写在 options 里也照收的核心键（它们是请求体的一级字段，不是技法旋钮；见 _run_shenshu_tool）。
_SHENSHU_PROMOTABLE_OPTION_KEYS = frozenset(
    {"gender", "zone", "lat", "lon", "gpsLat", "gpsLon", "pos", "after23NewDay", "lateZiHourUseNextDay"}
)


def _upstream_cast_time_seed(parts: dict[str, int]) -> int:
    """上游无头起课种子（TaiXuanMain.js:141-152 / JingJueMain.js:105-117 同式）：

    (年·月·日)·时·分 拼成 yyyyMMddHHmm 再 mod 1e9；BC 年把年位平移 |年|+5（同数 BC/AD 必异种子，
    AD 逐位不变）。同一起课时刻反复挂载得同一卦——「以时起卦」语义。
    """
    year = int(parts["year"])
    year_part = year if year >= 0 else abs(year) + 5
    stamp = ((year_part * 10000 + parts["month"] * 100 + parts["day"]) * 10000) + parts["hour"] * 100 + parts["minute"]
    return stamp % 1_000_000_000


# 五兆计算键缺省（上游 WuZhaoMain DEFAULT_OPTIONS :109-121 + DEFAULT_SPLITS/QIAN_THROWS/ZHAO_NUMS :87-89）。
# 上游页面与挂载都**全量**下发这 11 键（buildPanPayload / normalizeCalcOptions），缺哪键后端就回落
# 它自己的缺省——以钱代筮关自动掷而不带六掷时后端会逐掷走 RNG（webwuzhaosrv._qian_shifa），所以必须全发。
_WUZHAO_CALC_DEFAULTS: dict[str, Any] = {
    "mode": "ganzhi", "number": 0, "manual": False, "manualSplits": [18, 8, 5, 2, 1, 1],
    "shifaVariant": "guayi", "qianThrows": [2, 2, 2, 2, 2, 2], "qianAuto": True,
    "zhaoNums": [3, 3, 3, 3, 3, 3], "xingshenMonth": "lunar", "mingZhi": "", "gender": "",
}
_WUZHAO_MODE_LABELS = {
    "ganzhi": "干支起盘", "day": "日干起盘", "hour": "时干起盘", "minute": "分干起盘",
    "tang": "唐代正法揲筮", "dunhuang": "敦煌校录揲筮", "qian": "以钱代筮", "zhushu": "直输五兆数",
}


def _append_replay_note(text: str, section_title: str, note: str) -> str:
    """上游 WuZhaoMain.appendReplayNote（:360-366）逐字移植：复现说明并入既有段，不新增段头。"""
    blocks = f"{text or ''}".split("\n\n")
    for index, block in enumerate(blocks):
        if block.startswith(f"[{section_title}]"):
            blocks[index] = f"{block}\n复现说明：{note}"
            return "\n\n".join(blocks)
    return f"{text}\n复现说明：{note}"


# 皇极经世·心易发微（kinwangji/xinyi.py:42-72 只收**繁体**卦名/方位，简体直送即 ValueError → 500）。
_WANGJI_XINYI_METHODS = ("none", "datetime", "number", "character", "direction")
_WANGJI_TRIGRAMS = ("乾", "兌", "離", "震", "巽", "坎", "艮", "坤")
_WANGJI_TRIGRAM_ALIASES = {"兑": "兌", "离": "離"}
_WANGJI_DIRECTIONS = ("北", "西南", "東", "東南", "南", "中", "西北", "西", "東北")
_WANGJI_DIRECTION_ALIASES = {"东": "東", "东南": "東南", "东北": "東北"}


def _split_birth_ymdhm(payload: dict[str, Any]) -> dict[str, int]:
    # 神数 engines take split year/month/day/hour/minute (ganzhi-based). Derive from date "YYYY-MM-DD"/
    # "YYYY/MM/DD" (+ optional time "HH:MM[:SS]"). Raises ToolValidationError on an unparseable date
    # rather than silently substituting a default (which would compute a chart for the wrong moment).
    date_raw = f"{payload.get('date', '')}".strip().replace("/", "-")
    time_raw = f"{payload.get('time', '')}".strip()
    combined = f"{date_raw} {time_raw}".strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(combined if "%H" in fmt else date_raw, fmt)
            return {"year": dt.year, "month": dt.month, "day": dt.day, "hour": dt.hour, "minute": dt.minute}
        except ValueError:
            continue
    raise ToolValidationError(
        f"无法解析神数起盘日期/时间：date={payload.get('date')!r} time={payload.get('time')!r}。"
        "请提供公历日期（YYYY-MM-DD，可含 HH:MM[:SS] 时间）。",
        code="tool.shenshu_bad_date",
        details={"date": payload.get("date"), "time": payload.get("time")},
    )
