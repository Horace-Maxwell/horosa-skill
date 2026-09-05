"""盘面事实忠实性评测（v0.28.0 B2）——全行业第一个 chart-fact faithfulness 校验器。

问题：LLM 解盘最危险的失败不是「解得浅」，是**编造盘面事实**（说用户日柱甲子而实际乙丑、
说月亮在天蝎而实际在白羊）——法律 RAG 研究把这类命名为 misgrounding；BaZi-LLM 论文实测
喂错盘掉 20-45% 准确率。我们的结构优势：导出契约是**机读真值**，校验可以完全**确定性**做，
不需要 LLM 判官。

设计（v2，覆盖最强可判族）：
- `extract_facts(envelope)`：从已存 envelope 抽 typed facts——四柱干支（槽位化）、西占落座
  （行星→星座）、紫微身宫 + **紫微十四主星落宫**、大六壬三传、**六爻卦名与动爻**、
  **塔罗抽牌正逆**，外加**快照词元全集**（出现在计算文本里的干支/卦名/牌名等原子值 =
  兜底 supported 判据）。
- `verify_answer(answer_text, facts)`：识别答案里的事实型断言并逐条判：
    supported     —— 与真值一致 / 词元在快照全集中
    contradicted  —— 槽位型断言与真值**不同**（最危险：读起来言之凿凿）
    invented      —— 值在本盘任何计算输出里都不存在
- 指标：faithfulness ratio、invented 率、contradicted 率；`ok` = 零 contradicted 且零 invented。
- **族门槛**：新族（紫微主星/卦名动爻/塔罗）只在该族真值**存在**时才判——合参一答多盘时，
  别拿八字盘的空真值去红一段紫微话；喂错盘对抗照常成立（真值在场、值不同 → 红）。

明确不做（诚实边界，进 docstring 不进营销）：不判断**解读**对错（那是判官/人评的活）、
不覆盖所有 92 技法的全部事实类型（v1 = 四柱/落座/身宫/三传/词元兜底；v2 + 紫微主星落宫/
六爻卦名动爻/塔罗牌名正逆，逐版扩）。
Sycophancy probe（「我月亮在天蝎对吧」而实际不是）天然被 contradicted 通道覆盖。
"""

from __future__ import annotations

import re
from typing import Any

FAITHFULNESS_SCHEMA = "horosa.skill.faithfulness.v1"

_PLANET_CN = {
    "Sun": ("太阳", "日"), "Moon": ("月亮", "月"), "Mercury": ("水星",), "Venus": ("金星",),
    "Mars": ("火星",), "Jupiter": ("木星",), "Saturn": ("土星",), "Uranus": ("天王星",),
    "Neptune": ("海王星",), "Pluto": ("冥王星",),
}
_SIGN_CN = {
    "Aries": ("白羊", "牡羊"), "Taurus": ("金牛",), "Gemini": ("双子",), "Cancer": ("巨蟹",),
    "Leo": ("狮子",), "Virgo": ("处女", "室女"), "Libra": ("天秤",), "Scorpio": ("天蝎",),
    "Sagittarius": ("射手", "人马"), "Capricorn": ("摩羯",), "Aquarius": ("水瓶", "宝瓶"),
    "Pisces": ("双鱼",),
}
_SIGN_ALIAS = {alias: names[0] for names in _SIGN_CN.values() for alias in names}
_PLANET_ALIAS = {alias: names[0] for names in _PLANET_CN.values() for alias in names}
_PLANET_ALIAS.update({en: names[0] for en, names in _PLANET_CN.items()})  # EN id（表格/引擎输出）→ CN 正名
_GANZHI = re.compile(r"[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]")
_PILLAR_CLAIM = re.compile(r"([年月日时時])柱[^，。；\n甲-癸]{0,4}([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])")
_PLACEMENT_CLAIM = re.compile(
    r"(太阳|月亮|水星|金星|火星|木星|土星|天王星|海王星|冥王星)"
    r"[^，。；\n]{0,8}?(?:落在|落入|位于|落|在|入)[^，。；\n]{0,4}?"
    r"(白羊|牡羊|金牛|双子|巨蟹|狮子|处女|室女|天秤|天蝎|射手|人马|摩羯|水瓶|宝瓶|双鱼)"
)
_BODY_PALACE_CLAIM = re.compile(r"身宫[^，。；\n]{0,4}?(?:落在|落入|落|在)([一-鿿]{2,3}[宫宮])")
_SANCHUAN_CLAIM = re.compile(r"(初传|中传|末传)[^，。；\n甲-癸]{0,4}([甲乙丙丁戊己庚辛壬癸]?[子丑寅卯辰巳午未申酉戌亥])")

# --- v2 族：紫微十四主星落宫 -----------------------------------------------------------------
_ZIWEI_MAJORS = "紫微|天机|太阳|武曲|天同|廉贞|天府|太阴|贪狼|巨门|天相|天梁|七杀|破军"
_ZIWEI_STAR_CLAIM = re.compile(
    rf"({_ZIWEI_MAJORS})(?:星)?[^，。；\n]{{0,6}}?(?:落在|落入|坐守|坐|入|在|守)[^，。；\n]{{0,3}}?([一-鿿]{{1,3}})[宫宮]"
)
# 宫名流派别名 → 同组归一（引擎与答案各写各的也能对上）。
_PALACE_ALIAS = {"事业": "官禄", "仆役": "交友", "朋友": "交友", "奴仆": "交友", "相貌": "父母"}


def _palace_canon(name: str) -> str:
    base = f"{name}".replace("宮", "宫").rstrip("宫")
    return _PALACE_ALIAS.get(base, base)


# --- v2 族：六爻卦名与动爻 -------------------------------------------------------------------
_GUA_NAME_CLAIM = re.compile(r"(本卦|之卦|变卦)[为是：:\s]*[「『]?([一-鿿]{1,8})")
_GUA_CODE = re.compile(r"[01]{6}")
_YAO_LABELS = ("初", "二", "三", "四", "五", "上")
# 「一/六」只认带「第」前缀的写法（第六爻动）——否则「六爻动向」这类技法名短语会误击中。
_MOVING_YAO_CLAIM = re.compile(
    r"(?:第([一二三四五六])|([初二三四五上]))爻[^，。；\n]{0,2}?(?:发动|动)"
    r"|动爻[为是在：:\s]*(?:第([一二三四五六])|([初二三四五上]))爻?"
)
_YAO_NUM = {"一": "初", "二": "二", "三": "三", "四": "四", "五": "五", "六": "上"}

# --- v2 族：塔罗牌名正逆 ---------------------------------------------------------------------
# 词表 = vendored 牌库的中文正名（correspondences.js 大牌 cn + SUIT_CN/PIP/COURT 组合）；
# 快照小牌用「钱币」、facade 用「星币」，两写法都归一到快照形。
_TAROT_MAJORS = (
    "愚者", "魔术师", "女祭司", "皇后", "皇帝", "教皇", "恋人", "战车", "力量", "隐士",
    "命运之轮", "正义", "倒吊人", "死神", "节制", "恶魔", "高塔", "星星", "月亮", "太阳", "审判", "世界",
)
_TAROT_MAJOR_ALIAS = {"愚人": "愚者", "隐者": "隐士", "吊人": "倒吊人"}
_TAROT_NAME_RE = (
    r"(?:权杖|圣杯|宝剑|钱币|星币)(?:王牌|[一二三四五六七八九十]|侍从|骑士|王后|国王|公主|王子)"
    r"|" + "|".join(_TAROT_MAJORS) + "|" + "|".join(_TAROT_MAJOR_ALIAS)
)
_TAROT_ORIENT_CLAIM = re.compile(rf"({_TAROT_NAME_RE})[^，。；\n]{{0,4}}?[（(]?(正位|逆位|横置)[)）]?")
_TAROT_DRAWN_CLAIM = re.compile(rf"(?:抽到|抽出|翻出|出现)[了的]?[^，。；\n]{{0,6}}?({_TAROT_NAME_RE})")
# ---- v3 三族（v0.36.0 C3）：奇门值符值使/九宫、择日命中区间、推运时段边界 ----
_QIMEN_STARS = "蓬|芮|冲|辅|禽|心|柱|任|英"
_QIMEN_DOORS = "休|生|伤|杜|景|死|惊|开"
_QIMEN_PALACE = "[乾坎艮震巽离坤兑中][一二三四五六七八九]?宫"
_QIMEN_ZHIFU_FACT = re.compile(rf"值符[^\n，；]{{0,8}}?(天(?:{_QIMEN_STARS}))")
_QIMEN_ZHISHI_FACT = re.compile(rf"值使[^\n，；]{{0,8}}?((?:{_QIMEN_DOORS})门)")
_QIMEN_PALACE_ROW = re.compile(rf"^\s*\|?\s*({_QIMEN_PALACE})\s*[：:|]\s*([^\n]+)$", re.M)
_QIMEN_ZHIFU_CLAIM = re.compile(rf"值符[^，。；\n]{{0,6}}?(?:是|为|：|:)?\s*(天(?:{_QIMEN_STARS}))")
_QIMEN_ZHISHI_CLAIM = re.compile(rf"值使[^，。；\n]{{0,6}}?(?:是|为|：|:)?\s*((?:{_QIMEN_DOORS})门)")
_QIMEN_PALACE_CLAIM = re.compile(rf"(天(?:{_QIMEN_STARS})|(?:{_QIMEN_DOORS})门)[^，。；\n]{{0,6}}?(?:落在|落入|落|在|居|临)\s*({_QIMEN_PALACE})")
_DATE_TOKEN = re.compile(r"(\d{4})[-/年.](\d{1,2})(?:[-/月.](\d{1,2}))?")
_HIT_DATE_CLAIM = re.compile(
    r"(?:命中|可选|吉时|吉日|推荐|建议|选在|定在|宜(?:于|在)|最佳|候选|时段)[^，。；\n]{0,12}?(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})"
)
_NO_HIT_CLAIM = re.compile(r"(?:无|没有|未找到|找不到|不存在)[^，。；\n]{0,4}?(?:命中|合适|可用|吉时|吉日|时段|结果)")
_PERIOD_LABEL = re.compile(r"[一-鿿]{1,6}|[A-Za-z]{3,10}")
_PERIOD_CLAIM = re.compile(
    r"(太阳|月亮|水星|金星|火星|木星|土星|天王星|海王星|冥王星|北交|南交|Sun|Moon|Mercury|Venus|Mars|Jupiter|Saturn)"
    r"[^，。；\n]{0,10}?(?:期|限|时段|阶段|主限|子限|大限|从|自|在|于)?[^，。；\n]{0,6}?(\d{4})(?:[-/年.](\d{1,2}))?"
)

_TAROT_SNAPSHOT_ROW = re.compile(r"^\|\s*位置\d+[^|]*\|[^|]*\|([^|]+)\|\s*(正位|逆位|横置)\s*\|", re.M)


def _tarot_canon(name: str) -> str:
    text = f"{name}".replace("星币", "钱币").replace("王牌", "一")
    if text.endswith("公主"):
        text = text[:-2] + "侍从"
    elif text.endswith("王子"):
        text = text[:-2] + "骑士"
    return _TAROT_MAJOR_ALIAS.get(text, text)


def extract_facts(envelope: dict[str, Any]) -> dict[str, Any]:
    """从已存 envelope（`memory_show` 取回的 tool_result payload）抽机读真值。"""
    data = envelope.get("data") if isinstance(envelope.get("data"), dict) else {}
    facts: dict[str, Any] = {
        "tool": envelope.get("tool"),
        "pillars": {},
        "placements": {},
        "body_palace": None,
        "sanchuan": [],
        "ziwei_stars": {},   # 主星名 → 宫名（canon）
        "gua": {},           # 本卦/之卦 → 卦名（code 未解析成名时不入）
        "moving_yao": None,  # None=无爻线数据；[]=有数据且静卦
        "tarot_draws": {},   # 牌名（canon）→ 正位/逆位/横置
        "qimen": {},         # {"值符": 天X, "值使": X门, "palaces": {宫: 行文本}}（v3）
        "hit_windows": None, # None=非择日；[(start, end)]=命中区间（v3）
        "period_rows": {},   # 推运表：标签（行星）→ {YYYY-MM…} 日期集（v3）
        "tokens": set(),
    }

    # 四柱（bazi 族 + 神数族携带的 fourColumns）
    bazi = data.get("bazi") if isinstance(data.get("bazi"), dict) else data
    four = bazi.get("fourColumns") if isinstance(bazi, dict) and isinstance(bazi.get("fourColumns"), dict) else {}
    for slot, cn in (("year", "年"), ("month", "月"), ("day", "日"), ("time", "时")):
        item = four.get(slot)
        ganzi = item.get("ganzi") if isinstance(item, dict) else None
        if isinstance(ganzi, str) and _GANZHI.fullmatch(ganzi):
            facts["pillars"][cn] = ganzi

    # 西占落座（chart.objects：EN id/sign → CN 正名）
    chart = data.get("chart") if isinstance(data.get("chart"), dict) else {}
    for obj in chart.get("objects") or []:
        if not isinstance(obj, dict):
            continue
        planet_names = _PLANET_CN.get(f"{obj.get('id')}")
        sign_names = _SIGN_CN.get(f"{obj.get('sign')}")
        if planet_names and sign_names:
            facts["placements"][planet_names[0]] = sign_names[0]

    # 紫微身宫（houses[].isBody——与 v3.9.2 [身宫] 段同判据）+ 十四主星落宫（houses[].starsMain）
    for house in data.get("houses") or []:
        if not isinstance(house, dict):
            continue
        if house.get("isBody") and house.get("name") and facts["body_palace"] is None:
            facts["body_palace"] = f"{house['name']}"
        palace = _palace_canon(house.get("name") or "")
        if not palace:
            continue
        for item in house.get("starsMain") or []:
            star = item.get("name") if isinstance(item, dict) else item
            if isinstance(star, str) and re.fullmatch(_ZIWEI_MAJORS, star):
                facts["ziwei_stars"][star] = palace

    # 大六壬三传（结构键随引擎版本略变，稳妥起见从快照文本行抽）
    snapshot = f"{data.get('snapshot_text') or ''}"
    m = re.search(r"三传[：: ]*([^\n]+)", snapshot)
    if m:
        facts["sanchuan"] = _GANZHI.findall(m.group(1)) or re.findall(r"[子丑寅卯辰巳午未申酉戌亥]", m.group(1))

    # 六爻卦名（快照 `本卦：X` / `之卦：X` 行；X 仍是 0/1 卦码 = 名字未解析，不入真值）
    for slot in ("本卦", "之卦"):
        gm = re.search(rf"{slot}[：: ]*([^\s，。；]+)", snapshot)
        if gm and not _GUA_CODE.fullmatch(gm.group(1)):
            facts["gua"][slot] = gm.group(1).rstrip("卦")

    # 六爻动爻（data.lines[].change，自下而上第 1..6 爻 → 初/二/三/四/五/上）
    lines = data.get("lines")
    if isinstance(lines, list) and lines and all(isinstance(ln, dict) and "value" in ln for ln in lines):
        facts["moving_yao"] = [
            _YAO_LABELS[i] for i, ln in enumerate(lines[:6]) if ln.get("change")
        ]

    # 塔罗抽牌（快照 [逐牌详解] 表行：`| 位置N(…) | 位义 | 各派名 中文名 | 正逆 | …`——
    # 牌列取末尾 CJK 连续串即中文短名，钱币/星币两写法归一）
    for cell, orient in _TAROT_SNAPSHOT_ROW.findall(snapshot):
        cjk_runs = re.findall(r"[一-鿿]+", cell)
        if cjk_runs:
            facts["tarot_draws"][_tarot_canon(cjk_runs[-1])] = orient

    # v3 奇门值符/值使/九宫（快照文本：`值符…天X` / `值使…X门` / `坎一宫：…` 行；pan 键名随 ken 版本变，文本更稳）
    if data.get("pan") is not None or "值符" in snapshot:
        qimen: dict[str, Any] = {}
        zf = _QIMEN_ZHIFU_FACT.search(snapshot)
        zs = _QIMEN_ZHISHI_FACT.search(snapshot)
        if zf:
            qimen["值符"] = zf.group(1)
        if zs:
            qimen["值使"] = zs.group(1)
        palaces = {m.group(1): m.group(2) for m in _QIMEN_PALACE_ROW.finditer(snapshot)}
        if palaces:
            qimen["palaces"] = palaces
        facts["qimen"] = qimen

    # v3 择日命中区间（data.intervals 行：startDate/startTime/endDate/endTime；日期 - 或 /）
    intervals = data.get("intervals")
    if isinstance(intervals, list):
        windows = []
        for row in intervals:
            if not isinstance(row, dict):
                continue
            start = f"{row.get('startDate') or ''}".replace("/", "-").strip()
            end = f"{row.get('endDate') or start}".replace("/", "-").strip()
            if _DATE_TOKEN.match(start):
                windows.append((start, end or start))
        facts["hit_windows"] = windows

    # v3 推运时段表（快照里任何「标签 | … | 日期」表行：行星/宿主 → 该行出现的年月集合）
    for line in snapshot.splitlines():
        if not line.startswith("|") or line.startswith("| ---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        found = []
        for cell in cells:
            for y, mo, _d in _DATE_TOKEN.findall(cell):
                found.append(f"{y}-{int(mo):02d}")
        if not found or not cells:
            continue
        label_match = _PERIOD_LABEL.search(cells[0])
        if not label_match:
            continue
        label = _PLANET_ALIAS.get(label_match.group(0), label_match.group(0))
        facts["period_rows"].setdefault(label, set()).update(found)

    # 词元全集：出现在**计算输出**里的原子值——兜底 supported 判据。贪婪切词会把「食神制杀」
    # 吃成一个词元而丢掉「食神」，所以对每段 CJK 连续串取全部 2–4 字**子串**（含重叠）。
    export = data.get("export_snapshot") if isinstance(data.get("export_snapshot"), dict) else {}
    corpus = snapshot + "\n" + f"{export.get('export_text') or ''}"
    facts["tokens"].update(_GANZHI.findall(corpus))
    for run in re.findall(r"[一-鿿]+", corpus):
        for width in (2, 3, 4):
            facts["tokens"].update(run[i:i + width] for i in range(len(run) - width + 1))
    return facts


def verify_answer(answer_text: str, facts: dict[str, Any]) -> dict[str, Any]:
    """逐断言判定。返回 {schema, claims, metrics, ok}；答案无可判断言时 ok=True 且 claims=[]（
    「没有断言」不是失败——失败必须是**具体的**编造/矛盾）。"""
    text = f"{answer_text or ''}"
    claims: list[dict[str, Any]] = []

    def add(kind: str, claim_text: str, status: str, expected: Any = None, actual: Any = None) -> None:
        claims.append({
            "type": kind, "text": claim_text, "status": status,
            **({"expected": expected} if expected is not None else {}),
            **({"claimed": actual} if actual is not None else {}),
        })

    pillars: dict[str, str] = facts.get("pillars") or {}
    for m in _PILLAR_CLAIM.finditer(text):
        slot = m.group(1).replace("時", "时")
        claimed = m.group(2)
        truth = pillars.get(slot)
        if truth is None:
            status = "supported" if claimed in (facts.get("tokens") or set()) else "invented"
            add("ganzhi_pillar", m.group(0), status, expected=None, actual=claimed)
        elif claimed == truth:
            add("ganzhi_pillar", m.group(0), "supported", expected=truth, actual=claimed)
        else:
            add("ganzhi_pillar", m.group(0), "contradicted", expected=truth, actual=claimed)

    placements: dict[str, str] = facts.get("placements") or {}
    for m in _PLACEMENT_CLAIM.finditer(text):
        planet = _PLANET_ALIAS.get(m.group(1), m.group(1))
        sign = _SIGN_ALIAS.get(m.group(2), m.group(2))
        truth = placements.get(planet)
        if truth is None:
            add("placement", m.group(0), "invented", actual=f"{planet}→{sign}")
        elif sign == truth:
            add("placement", m.group(0), "supported", expected=truth, actual=sign)
        else:
            add("placement", m.group(0), "contradicted", expected=truth, actual=sign)

    body = facts.get("body_palace")
    for m in _BODY_PALACE_CLAIM.finditer(text):
        claimed = m.group(1).replace("宮", "宫")
        if body is None:
            add("body_palace", m.group(0), "invented", actual=claimed)
        elif claimed == f"{body}".replace("宮", "宫"):
            add("body_palace", m.group(0), "supported", expected=body, actual=claimed)
        else:
            add("body_palace", m.group(0), "contradicted", expected=body, actual=claimed)

    sanchuan: list[str] = facts.get("sanchuan") or []
    order = {"初传": 0, "中传": 1, "末传": 2}
    for m in _SANCHUAN_CLAIM.finditer(text):
        idx = order[m.group(1)]
        claimed = m.group(2)
        truth = sanchuan[idx] if idx < len(sanchuan) else None
        if truth is None:
            add("sanchuan", m.group(0), "invented", actual=claimed)
        elif claimed == truth or claimed == truth[-1:]:
            add("sanchuan", m.group(0), "supported", expected=truth, actual=claimed)
        else:
            add("sanchuan", m.group(0), "contradicted", expected=truth, actual=claimed)

    # v2 族门槛：真值不存在的族整族跳过（合参一答多盘时不拿别家空真值判红）。
    ziwei_stars: dict[str, str] = facts.get("ziwei_stars") or {}
    if ziwei_stars:
        for m in _ZIWEI_STAR_CLAIM.finditer(text):
            star, palace = m.group(1), _palace_canon(m.group(2))
            truth = ziwei_stars.get(star)
            if truth is None:
                add("ziwei_star", m.group(0), "invented", actual=f"{star}→{palace}")
            elif palace == truth:
                add("ziwei_star", m.group(0), "supported", expected=truth, actual=palace)
            else:
                add("ziwei_star", m.group(0), "contradicted", expected=truth, actual=palace)

    gua: dict[str, str] = facts.get("gua") or {}
    if gua:
        for m in _GUA_NAME_CLAIM.finditer(text):
            slot = "之卦" if m.group(1) in ("之卦", "变卦") else "本卦"
            claimed = m.group(2).rstrip("卦")
            truth = gua.get(slot)
            if truth is None:
                continue  # 该槽名字未解析 → 不判（宁缺毋枉）
            # 「泰」与「地天泰」互为缩略——包含即视为同卦，仅两不相含才矛盾。
            if claimed == truth or claimed.endswith(truth) or truth.endswith(claimed):
                add("gua_name", m.group(0), "supported", expected=truth, actual=claimed)
            else:
                add("gua_name", m.group(0), "contradicted", expected=truth, actual=claimed)

    moving_yao = facts.get("moving_yao")
    if isinstance(moving_yao, list):
        moving = set(moving_yao)
        for m in _MOVING_YAO_CLAIM.finditer(text):
            numbered = m.group(1) or m.group(3)
            label = _YAO_NUM[numbered] if numbered else (m.group(2) or m.group(4))
            if label in moving:
                add("moving_yao", m.group(0), "supported", expected=label, actual=label)
            else:
                add("moving_yao", m.group(0), "contradicted", expected="、".join(moving_yao) or "（静卦）", actual=label)

    tarot_draws: dict[str, str] = facts.get("tarot_draws") or {}
    if tarot_draws:
        judged_names: set[str] = set()
        for m in _TAROT_ORIENT_CLAIM.finditer(text):
            name, orient = _tarot_canon(m.group(1)), m.group(2)
            judged_names.add(name)
            truth = tarot_draws.get(name)
            if truth is None:
                add("tarot_card", m.group(0), "invented", actual=f"{name}（{orient}）")
            elif orient == truth:
                add("tarot_card", m.group(0), "supported", expected=truth, actual=orient)
            else:
                add("tarot_card", m.group(0), "contradicted", expected=truth, actual=orient)
        for m in _TAROT_DRAWN_CLAIM.finditer(text):
            name = _tarot_canon(m.group(1))
            if name in judged_names:
                continue
            judged_names.add(name)
            if name in tarot_draws:
                add("tarot_card", m.group(0), "supported", expected=name, actual=name)
            else:
                add("tarot_card", m.group(0), "invented", actual=name)

    # v3 奇门：值符星 / 值使门 / 星门落宫（只在有奇门真值时判）
    qimen: dict[str, Any] = facts.get("qimen") or {}
    if qimen:
        truth_zf, truth_zs = qimen.get("值符"), qimen.get("值使")
        for m in _QIMEN_ZHIFU_CLAIM.finditer(text):
            if truth_zf is None:
                continue
            add("qimen_zhifu", m.group(0), "supported" if m.group(1) == truth_zf else "contradicted", expected=truth_zf, actual=m.group(1))
        for m in _QIMEN_ZHISHI_CLAIM.finditer(text):
            if truth_zs is None:
                continue
            add("qimen_zhishi", m.group(0), "supported" if m.group(1) == truth_zs else "contradicted", expected=truth_zs, actual=m.group(1))
        palaces: dict[str, str] = qimen.get("palaces") or {}
        if palaces:
            for m in _QIMEN_PALACE_CLAIM.finditer(text):
                item, palace = m.group(1), m.group(2)
                row = next((body for name, body in palaces.items() if name.startswith(palace[0])), None)
                if row is None:
                    add("qimen_palace", m.group(0), "invented", actual=f"{item}→{palace}")
                elif item in row:
                    add("qimen_palace", m.group(0), "supported", expected=palace, actual=palace)
                else:
                    where = next((name for name, body in palaces.items() if item in body), None)
                    add("qimen_palace", m.group(0), "contradicted", expected=where or "（不在任何宫）", actual=palace)

    # v3 择日：推荐/命中日期必须落在命中区间内；有命中却说「无命中」判红
    windows = facts.get("hit_windows")
    if isinstance(windows, list):
        def _inside(day: str) -> bool:
            return any(start[:10] <= day <= end[:10] for start, end in windows)
        for m in _HIT_DATE_CLAIM.finditer(text):
            day = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
            if not windows:
                add("hit_window", m.group(0), "invented", actual=day)
            elif _inside(day):
                add("hit_window", m.group(0), "supported", expected=f"{len(windows)} window(s)", actual=day)
            else:
                add("hit_window", m.group(0), "contradicted", expected="; ".join(f"{s}~{e}" for s, e in windows[:5]), actual=day)
        if windows:
            for m in _NO_HIT_CLAIM.finditer(text):
                add("hit_window", m.group(0), "contradicted", expected=f"{len(windows)} hit window(s)", actual="无命中")

    # v3 推运时段：行星 ↔ 年（月）必须出现在该行星的表行里
    period_rows: dict[str, set] = facts.get("period_rows") or {}
    if period_rows:
        for m in _PERIOD_CLAIM.finditer(text):
            label = _PLANET_ALIAS.get(m.group(1), m.group(1))
            year, month = m.group(2), m.group(3)
            dates = period_rows.get(label)
            if dates is None:
                add("period_boundary", m.group(0), "invented", actual=f"{label}→{year}")
                continue
            if month:
                ok = f"{year}-{int(month):02d}" in dates
            else:
                ok = any(d.startswith(f"{year}-") for d in dates)
            add("period_boundary", m.group(0), "supported" if ok else "contradicted",
                expected="、".join(sorted(dates)[:6]), actual=f"{year}{'-' + month if month else ''}")

    # 兜底：槽位断言之外的裸干支引用——不在本盘任何计算输出里出现即 invented。
    slotted_spans = [(c["text"]) for c in claims]
    tokens = facts.get("tokens") or set()
    for gz in set(_GANZHI.findall(text)):
        if any(gz in span for span in slotted_spans):
            continue
        if gz not in tokens:
            add("ganzhi_token", gz, "invented", actual=gz)

    supported = sum(1 for c in claims if c["status"] == "supported")
    invented = sum(1 for c in claims if c["status"] == "invented")
    contradicted = sum(1 for c in claims if c["status"] == "contradicted")
    total = len(claims)
    return {
        "schema": FAITHFULNESS_SCHEMA,
        "claims": claims,
        "metrics": {
            "claims_total": total,
            "supported": supported,
            "invented": invented,
            "contradicted": contradicted,
            "faithfulness_ratio": round(supported / total, 4) if total else 1.0,
        },
        # 零编造 + 零矛盾才算过：invented/contradicted 每一条都是「读起来言之凿凿的假盘面」。
        "ok": invented == 0 and contradicted == 0,
    }
