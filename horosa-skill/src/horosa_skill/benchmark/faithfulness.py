"""盘面事实忠实性评测（v0.28.0 B2）——全行业第一个 chart-fact faithfulness 校验器。

问题：LLM 解盘最危险的失败不是「解得浅」，是**编造盘面事实**（说用户日柱甲子而实际乙丑、
说月亮在天蝎而实际在白羊）——法律 RAG 研究把这类命名为 misgrounding；BaZi-LLM 论文实测
喂错盘掉 20-45% 准确率。我们的结构优势：导出契约是**机读真值**，校验可以完全**确定性**做，
不需要 LLM 判官。

设计（v1，覆盖最强可判族）：
- `extract_facts(envelope)`：从已存 envelope 抽 typed facts——四柱干支（槽位化）、西占落座
  （行星→星座）、紫微身宫、大六壬三传，外加**快照词元全集**（出现在计算文本里的干支/卦名/
  牌名等原子值 = 兜底 supported 判据）。
- `verify_answer(answer_text, facts)`：识别答案里的事实型断言并逐条判：
    supported     —— 与真值一致 / 词元在快照全集中
    contradicted  —— 槽位型断言与真值**不同**（最危险：读起来言之凿凿）
    invented      —— 值在本盘任何计算输出里都不存在
- 指标：faithfulness ratio、invented 率、contradicted 率；`ok` = 零 contradicted 且零 invented。

明确不做（诚实边界，进 docstring 不进营销）：不判断**解读**对错（那是判官/人评的活）、
不覆盖所有 92 技法的全部事实类型（v1 = 四柱/落座/身宫/三传/词元兜底，逐版扩）。
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
_GANZHI = re.compile(r"[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]")
_PILLAR_CLAIM = re.compile(r"([年月日时時])柱[^，。；\n甲-癸]{0,4}([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])")
_PLACEMENT_CLAIM = re.compile(
    r"(太阳|月亮|水星|金星|火星|木星|土星|天王星|海王星|冥王星)"
    r"[^，。；\n]{0,8}?(?:落在|落入|位于|落|在|入)[^，。；\n]{0,4}?"
    r"(白羊|牡羊|金牛|双子|巨蟹|狮子|处女|室女|天秤|天蝎|射手|人马|摩羯|水瓶|宝瓶|双鱼)"
)
_BODY_PALACE_CLAIM = re.compile(r"身宫[^，。；\n]{0,4}?(?:落在|落入|落|在)([一-鿿]{2,3}[宫宮])")
_SANCHUAN_CLAIM = re.compile(r"(初传|中传|末传)[^，。；\n甲-癸]{0,4}([甲乙丙丁戊己庚辛壬癸]?[子丑寅卯辰巳午未申酉戌亥])")


def extract_facts(envelope: dict[str, Any]) -> dict[str, Any]:
    """从已存 envelope（`memory_show` 取回的 tool_result payload）抽机读真值。"""
    data = envelope.get("data") if isinstance(envelope.get("data"), dict) else {}
    facts: dict[str, Any] = {
        "tool": envelope.get("tool"),
        "pillars": {},
        "placements": {},
        "body_palace": None,
        "sanchuan": [],
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

    # 紫微身宫（houses[].isBody——与 v3.9.2 [身宫] 段同判据）
    for house in data.get("houses") or []:
        if isinstance(house, dict) and house.get("isBody") and house.get("name"):
            facts["body_palace"] = f"{house['name']}"
            break

    # 大六壬三传（结构键随引擎版本略变，稳妥起见从快照文本行抽）
    snapshot = f"{data.get('snapshot_text') or ''}"
    m = re.search(r"三传[：: ]*([^\n]+)", snapshot)
    if m:
        facts["sanchuan"] = _GANZHI.findall(m.group(1)) or re.findall(r"[子丑寅卯辰巳午未申酉戌亥]", m.group(1))

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
