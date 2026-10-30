"""本命盘族快照：格局速览、印度盘、西洋盘族的整份快照与请求缺省、印度分盘预设。"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from horosa_skill.engine import astro_snapshot as _astro_snap
from horosa_skill.engine.astroextra_snapshots import _UNDEFINED as _ASTRO_UNDEF
from horosa_skill.engine.astroextra_snapshots import _js_number as _astro_snap_js_number
from horosa_skill.service import _clock
from horosa_skill.service._common import _render_snapshot_text
from horosa_skill.service._context import _degrade
from horosa_skill.service.text.astro_core import (
    _build_nakshatra_lines,
    _keep_mutual_line,
    _keep_reception_line,
    _only_ruler_exalt_reception,
)

# ── 格局速览 (pattern overview)：龙脉/孤月独明/先验权力/心性·智识/职业·行事/强吉木星/后天凶星 ──
# 纯派生自 /chart 活盘对象(objects: lon/lonspeed/sign/selfDignity/ruleHouses/house/feral/aboveHorizon)
# + isDiurnal + 北交 + mutuals/receptions/aspects.normalAsp 及主宰星链。供 [古典格局] 段尾「格局速览」子块。绝不抛(失败回空)。
_PO_TRAD_KEYS = ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn")
_PO_KEY_TO_ID = {"sun": "Sun", "moon": "Moon", "mercury": "Mercury", "venus": "Venus", "mars": "Mars", "jupiter": "Jupiter", "saturn": "Saturn"}
_PO_ID_TO_KEY = {v: k for k, v in _PO_KEY_TO_ID.items()}
_PO_SEVEN_IDS = ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn")
_PO_SIGN_DOMICILE = {
    "aries": "mars", "taurus": "venus", "gemini": "mercury", "cancer": "moon",
    "leo": "sun", "virgo": "mercury", "libra": "venus", "scorpio": "mars",
    "sagittarius": "jupiter", "capricorn": "saturn", "aquarius": "saturn", "pisces": "jupiter",
}
_PO_SIGN_MODALITY = {
    "aries": "cardinal", "cancer": "cardinal", "libra": "cardinal", "capricorn": "cardinal",
    "taurus": "fixed", "leo": "fixed", "scorpio": "fixed", "aquarius": "fixed",
    "gemini": "mutable", "virgo": "mutable", "sagittarius": "mutable", "pisces": "mutable",
}
_PO_MODALITY_CN = {"cardinal": "转宫", "fixed": "定宫", "mutable": "二体宫"}
_PO_MALEFIC_HOUSES = frozenset({6, 8, 12})
_PO_JUP_WEAK_HOUSES = frozenset({3, 6, 8, 12})


def _po_norm360(x: Any) -> float:
    try:
        return ((float(x) % 360.0) + 360.0) % 360.0
    except (TypeError, ValueError):
        return 0.0


def _po_house_num(h: Any) -> int | None:
    if isinstance(h, bool):
        return None
    if isinstance(h, (int, float)):
        return int(h)
    m = re.search(r"(\d+)", str(h if h is not None else ""))
    return int(m.group(1)) if m else None


def _po_sign_key(s: Any) -> str | None:
    return str(s).lower() if s else None


def _po_dign_token(sd: Any) -> str:
    if not isinstance(sd, list):
        return ""
    if "ruler" in sd:
        return "庙"
    if "exalt" in sd:
        return "旺"
    if "exile" in sd:
        return "陷"
    if "fall" in sd:
        return "落"
    return ""


def _po_compute_dispositors(objects: list[Any]) -> dict[str, Any]:
    # 七政各落座的本垣主，顺链至「落自家座」终极主宰或互容成环；返回 {step: key->本垣主key, loops: [环key数组]}。
    pos: dict[str, str | None] = {}
    for o in objects or []:
        if not isinstance(o, dict):
            continue
        key = _PO_ID_TO_KEY.get(o.get("id"))
        if key:
            pos[key] = _po_sign_key(o.get("sign"))
    step: dict[str, str] = {}
    for k in _PO_TRAD_KEYS:
        sign = pos.get(k)
        dom = _PO_SIGN_DOMICILE.get(sign) if sign else None
        if dom is not None:
            step[k] = dom
    loops: list[list[str]] = []
    for start in _PO_TRAD_KEYS:
        if start not in step:
            continue
        path: list[str] = []
        seen: set[str] = set()
        cur: str | None = start
        while cur is not None and cur in step:
            if cur in seen:
                loops.append(path[path.index(cur):])
                break
            seen.add(cur)
            path.append(cur)
            nxt = step[cur]
            if nxt == cur:
                break
            cur = nxt
    uniq: list[list[str]] = []
    seen_loop: set[str] = set()
    for c in loops:
        key = ">".join(sorted(c))
        if key not in seen_loop:
            seen_loop.add(key)
            uniq.append(c)
    return {"step": step, "loops": uniq}


def _po_conj_linked(id_a: Any, id_b: Any, response: dict[str, Any]) -> bool:
    """上游 astroPatternOverview.js:95-101 conjLinked：normalAsp 里任一方向（a→b 或 b→a）的 Exact/Applicative/Separative
    有 `Number(x.asp) === 0` 即合相联结（[Q-558/T-520]；此前本仓只查 a→b 一个方向）。"""
    aspects = response.get("aspects") if isinstance(response.get("aspects"), dict) else {}
    na = aspects.get("normalAsp") if isinstance(aspects.get("normalAsp"), dict) else None

    def hit(frm: Any, to: Any) -> bool:
        row = na.get(frm) if na is not None and isinstance(frm, str) else None
        if not isinstance(row, dict):
            return False
        for cat in ("Exact", "Applicative", "Separative"):
            for x in row.get(cat) or []:
                if isinstance(x, dict) and x.get("id") == to and _astro_snap_js_number(x.get("asp", _ASTRO_UNDEF)) == 0:
                    return True
        return False

    return hit(id_a, id_b) or hit(id_b, id_a)


def _po_antiscia_linked(id_a: Any, id_b: Any, response: dict[str, Any]) -> bool:
    """上游 astroPatternOverview.js:102-109 antisciaLinked：chart.antiscias 的映点 / 反映点表（元组 [a, b, orb]）里两星成对。"""
    perchart = response.get("chart") if isinstance(response.get("chart"), dict) else {}
    anti = perchart.get("antiscias") if isinstance(perchart.get("antiscias"), dict) else (
        response.get("antiscias") if isinstance(response.get("antiscias"), dict) else {}
    )
    for it in list(anti.get("antiscia") or []) + list(anti.get("cantiscia") or []):
        if isinstance(it, (list, tuple)):
            x = it[0] if len(it) > 0 else None
            y = it[1] if len(it) > 1 else None
        elif isinstance(it, dict):
            x = it.get("a") or (it["planetA"].get("id") if isinstance(it.get("planetA"), dict) else None)
            y = it.get("b") or (it["planetB"].get("id") if isinstance(it.get("planetB"), dict) else None)
        else:
            continue
        if (x == id_a and y == id_b) or (x == id_b and y == id_a):
            return True
    return False


def _po_pair_linked(id_a: Any, id_b: Any, response: dict[str, Any], by_id: dict[str, Any]) -> bool:
    """上游 astroPatternOverview.js:110-120 pairLinked：互容/接纳（原始表，不过滤）或合相或映点——「联结只有四种」。"""
    def in_list(lst: Any) -> bool:
        for it in lst or []:
            if not isinstance(it, dict):
                continue
            x = it["planetA"].get("id") if isinstance(it.get("planetA"), dict) else it.get("beneficiary")
            y = it["planetB"].get("id") if isinstance(it.get("planetB"), dict) else it.get("supplier")
            if (x == id_a and y == id_b) or (x == id_b and y == id_a):
                return True
        return False
    m = response.get("mutuals") or {}
    r = response.get("receptions") or {}
    if in_list(m.get("normal")) or in_list(m.get("abnormal")) or in_list(r.get("normal")) or in_list(r.get("abnormal")):
        return True
    return _po_conj_linked(id_a, id_b, response) or _po_antiscia_linked(id_a, id_b, response)


def _pattern_overview(response: dict[str, Any], *, only_ruler_exalt: bool = False) -> dict[str, Any]:
    perchart = response.get("chart") if isinstance(response.get("chart"), dict) else {}
    objects = perchart.get("objects") if isinstance(perchart.get("objects"), list) else []
    if not objects:
        return {}
    by_id = {o.get("id"): o for o in objects if isinstance(o, dict) and o.get("id")}
    seven = [by_id[i] for i in _PO_SEVEN_IDS if i in by_id]
    is_day = bool(perchart.get("isDiurnal"))
    disp = _po_compute_dispositors(objects)

    def rule_houses(o: Any) -> list[int]:
        if not isinstance(o, dict):
            return []
        return [n for n in (_po_house_num(h) for h in (o.get("ruleHouses") or [])) if n is not None]

    def house_of(o: Any) -> int | None:
        return _po_house_num(o.get("house")) if isinstance(o, dict) else None

    def afflict_flags(o: Any) -> list[str]:
        f: list[str] = []
        if not isinstance(o, dict):
            return f
        try:
            if float(o.get("lonspeed") or 0) < 0:
                f.append("逆")
        except (TypeError, ValueError):
            pass
        if o.get("feral"):
            f.append("野逸")
        t = _po_dign_token(o.get("selfDignity"))
        if t in ("陷", "落"):
            f.append(t)
        return f

    # 龙截龙拥：北交黄经为轴分盘，统计 7 真星各半
    nn = by_id.get("North Node")
    if not nn or nn.get("lon") is None or len(seven) < 7:
        dragon: dict[str, Any] = {"has": False}
    else:
        axis = _po_norm360(nn.get("lon"))
        side_a: list[Any] = []
        side_b: list[Any] = []
        for o in seven:
            (side_a if _po_norm360((o.get("lon") or 0) - axis) < 180 else side_b).append(o)
        small = side_a if len(side_a) <= len(side_b) else side_b
        if len(small) == 0:
            dragon = {"has": True, "kind": "龙拥", "note": f"七星聚一侧（{'昼' if is_day else '夜'}限）"}
        elif len(small) == 1:
            lone = small[0]
            dragon = {"has": True, "kind": "龙截", "lone": lone.get("id"), "loneHouse": house_of(lone), "loneSign": lone.get("sign"), "loneRules": rule_houses(lone)}
        elif len(small) == 2 and _po_pair_linked(small[0].get("id"), small[1].get("id"), response, by_id):
            dragon = {"has": True, "kind": "龙截", "pair": [small[0].get("id"), small[1].get("id")], "note": "两星联结"}
        else:
            dragon = {"has": False}

    # 孤月独明：夜生且 7 星中唯月在地平上
    if is_day:
        lone_moon = {"has": False}
    else:
        def above(o: Any) -> bool:
            ah = o.get("aboveHorizon")
            if ah is not None:
                return bool(ah)
            h = house_of(o)
            return h is not None and 7 <= h <= 12
        above_list = [o for o in seven if above(o)]
        lone_moon = {"has": len(above_list) == 1 and above_list[0].get("id") == "Moon"}

    # 月水心性智识：座·模式·主宰星·主宰星资质·受损旗标
    def mm_one(planet_id: str) -> dict[str, Any] | None:
        o = by_id.get(planet_id)
        if not o:
            return None
        sign_k = _po_sign_key(o.get("sign"))
        modality = _PO_MODALITY_CN.get(_PO_SIGN_MODALITY.get(sign_k or "", ""), "")
        dk = disp["step"].get(_PO_ID_TO_KEY.get(planet_id, ""))
        disp_id = _PO_KEY_TO_ID.get(dk) if dk else None
        disp_obj = by_id.get(disp_id) if disp_id else None
        return {"sign": o.get("sign"), "modality": modality, "ruler": disp_id,
                "rulerDign": _po_dign_token(disp_obj.get("selfDignity")) if disp_obj else "", "flags": afflict_flags(o)}
    moon_mercury = {"moon": mm_one("Moon"), "mercury": mm_one("Mercury")}

    # 职业/行事(东升西没)：西没=黄经在前，取最近为第一
    def first_occidental(ref_id: str) -> str | None:
        ref = by_id.get(ref_id)
        if not ref:
            return None
        occ = sorted(
            ({"id": o.get("id"), "d": _po_norm360((o.get("lon") or 0) - (ref.get("lon") or 0))} for o in seven if o.get("id") != ref_id),
            key=lambda x: x["d"],
        )
        occ = [x for x in occ if 0 < x["d"] < 180]
        occ.sort(key=lambda x: x["d"])
        return occ[0]["id"] if occ else None

    def detail_of(pid: str | None) -> dict[str, Any] | None:
        o = by_id.get(pid) if pid else None
        if not o:
            return None
        return {"id": pid, "sign": o.get("sign"), "house": house_of(o)}
    vocation = {"career": detail_of(first_occidental("Moon")), "style": detail_of(first_occidental("Sun"))}

    # 强吉木星：不主 {3,6,8,12}(例外 ruleHouses=={6,9}) + 照耀星数(遵当前容许度 normalAsp)
    jup = by_id.get("Jupiter")
    if not jup:
        jupiter: dict[str, Any] = {"present": False}
    else:
        rh = rule_houses(jup)
        rh_set = set(rh)
        is69 = len(rh_set) == 2 and 6 in rh_set and 9 in rh_set
        strong = (not any(h in _PO_JUP_WEAK_HOUSES for h in rh)) or is69
        lit: list[str] = []
        na = (response.get("aspects") or {}).get("normalAsp") if isinstance(response.get("aspects"), dict) else None
        ja = na.get("Jupiter") if isinstance(na, dict) else None
        if isinstance(ja, dict):
            for cat in ("Exact", "Applicative", "Separative", "None"):
                for a in (ja.get(cat) or []):
                    aid = a.get("id") if isinstance(a, dict) else None
                    if aid in _PO_SEVEN_IDS and aid != "Jupiter" and aid not in lit:
                        lit.append(aid)
        jupiter = {"present": True, "strong": strong, "sign": jup.get("sign"),
                   "dign": _po_dign_token(jup.get("selfDignity")), "lit": lit, "litCount": len(lit)}

    # 后天凶星：主宰 6/8/12 者
    afflicted = [o.get("id") for o in seven if any(h in _PO_MALEFIC_HOUSES for h in rule_houses(o))]

    # 先验权力：8th 与 12th 或 8th 与 1th 之联结(接纳/互容/主宰环)；夜生 → 八杀朝天大贵
    def in_or_rules(o: Any, h: int) -> bool:
        if not o:
            return False
        return house_of(o) == h or h in rule_houses(o)

    def apriori_link(oa: Any, ob: Any) -> str | None:
        if not oa or not ob:
            return None
        if (in_or_rules(oa, 8) and in_or_rules(ob, 12)) or (in_or_rules(oa, 12) and in_or_rules(ob, 8)):
            return "8·12"
        if (in_or_rules(oa, 8) and in_or_rules(ob, 1)) or (in_or_rules(oa, 1) and in_or_rules(ob, 8)):
            return "8·1"
        return None
    apriori: dict[str, Any] = {"has": False, "links": []}

    def check_apriori(a_id: Any, b_id: Any, kind: str) -> None:
        w = apriori_link(by_id.get(a_id), by_id.get(b_id))
        if w:
            apriori["has"] = True
            apriori["links"].append({"a": a_id, "b": b_id, "which": w, "kind": kind})
    # 「仅按本垣擢升计算互容接纳」开时先滤互容/接纳（上游 astroPatternOverview.js:197-207 keepRec/keepMut），
    # 先验权力的联结与 [信息] 段详细行同口径。
    m_raw = response.get("mutuals") or {}
    r_raw = response.get("receptions") or {}
    m = {k: [it for it in (m_raw.get(k) or []) if _keep_mutual_line(it, only_ruler_exalt=only_ruler_exalt)] for k in ("normal", "abnormal")}
    r = {
        "normal": [it for it in (r_raw.get("normal") or []) if _keep_reception_line(it, only_ruler_exalt=only_ruler_exalt)],
        "abnormal": [it for it in (r_raw.get("abnormal") or []) if _keep_reception_line(it, abnormal=True, only_ruler_exalt=only_ruler_exalt)],
    }
    for it in list(m.get("normal") or []) + list(m.get("abnormal") or []):
        if isinstance(it, dict):
            pa = it["planetA"].get("id") if isinstance(it.get("planetA"), dict) else None
            pb = it["planetB"].get("id") if isinstance(it.get("planetB"), dict) else None
            check_apriori(pa, pb, "互容")
    for it in list(r.get("normal") or []) + list(r.get("abnormal") or []):
        if isinstance(it, dict):
            check_apriori(it.get("beneficiary"), it.get("supplier"), "接纳")
    for lp in disp["loops"]:
        ids = [i for i in (_PO_KEY_TO_ID.get(k) for k in lp) if i]
        for x in range(len(ids)):
            for y in range(x + 1, len(ids)):
                check_apriori(ids[x], ids[y], "主宰环")
    # [Q-558/T-520]（astroPatternOverview.js:227-232）先验权力联结取材补合相(0°)与映点/反映点（七真星两两）。
    for x in range(len(seven)):
        for y in range(x + 1, len(seven)):
            ia, ib = seven[x].get("id"), seven[y].get("id")
            if _po_conj_linked(ia, ib, response):
                check_apriori(ia, ib, "合相")
            if _po_antiscia_linked(ia, ib, response):
                check_apriori(ia, ib, "映点")
    apriori["eightKill"] = apriori["has"] and not is_day

    return {"dragon": dragon, "loneMoon": lone_moon, "moonMercury": moon_mercury,
            "vocation": vocation, "jupiter": jupiter, "afflictedRulers": afflicted, "apriori": apriori}


# classicalParamSpec.js:249-256 的全局仓缺省（headless 无本机仓 = 缺省档）：恒星平轨 1°、轨档 school。
_FIXED_STAR_ORB_DEFAULT = 1
_FIXED_STAR_ORB_MODE_DEFAULT = "school"


def _fixed_star_orb_params(params: dict[str, Any]) -> dict[str, Any]:
    """上游 classicalChartGlobals.js:271 fixedStarOrbParamsFor：/astroextra/analysis 的恒星轨参数。

    随盘优先（chart 级键 starOrb/starOrbMode，缺则前端名 fixedStarOrb/fixedStarOrbMode），再缺取全局缺省；
    档位仅 byMagnitude 时下发（Python fixed_star_hits 据此逐星取星等表轨）。
    """
    def pick(first: Any, second: Any) -> Any:
        return first if first is not None and first != "" else second

    orb = pick(params.get("starOrb"), pick(params.get("fixedStarOrb"), _FIXED_STAR_ORB_DEFAULT))
    mode = pick(params.get("starOrbMode"), pick(params.get("fixedStarOrbMode"), _FIXED_STAR_ORB_MODE_DEFAULT))
    out: dict[str, Any] = {"fixedStarOrb": orb}
    if mode == "byMagnitude":
        out["fixedStarOrbMode"] = "byMagnitude"
    return out


def _india_lines(block: Any) -> list[str]:
    """上游 splitSections 的逐行口径：段体是「行」数组；skill 的行 builder 偶有一项多行，先摊平成单行。"""
    if block is None:
        return []
    items = block if isinstance(block, (list, tuple)) else [block]
    return "\n".join(f"{item if item is not None else ''}" for item in items).split("\n") if items else []


def _india_ensure_section(lines: list[str], title: str, body: Any) -> None:
    """上游 IndiaChart.ensureSection（:287-296）：逐行 trimEnd、滤空行；空段写「无数据」；段尾空一行。"""
    clean = [line.rstrip() for line in _india_lines(body)]
    clean = [line for line in clean if line.strip()]
    lines.append(f"[{title}]")
    lines.extend(clean or ["无数据"])
    lines.append("")


def _india_replace_calibre_line(base_info: list[str], calibre_line: str | None) -> list[str]:
    """上游 replaceIndiaCalibreLine（IndiaChart.js:1241-1246）：替换第一条「回归黄道|恒星黄道」起首的行，无则追加。"""
    lines = list(base_info)
    if not calibre_line:
        return lines
    for index, line in enumerate(lines):
        if re.match(r"^(回归黄道|恒星黄道)", f"{line}".strip()):
            lines[index] = calibre_line
            return lines
    lines.append(calibre_line)
    return lines


def _build_india_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    """印度律盘快照 = 上游 buildIndiaSnapshotText（IndiaChart.js:1248-1305，v3.13.0）的段组成，逐段同序：

    [起盘信息] = 流派 / 大运流派开关 / 当前分盘 / 分盘四行（vendored buildIndiaSchoolHeaderLines）+ 本命 [起盘信息] 各行，
      其中首条黄道行换成印占实际口径行（indiaCalibreLine：恒星黄道·<岁差>，<印占分宫制>）；
    [星盘信息] = 本命 [宫位宫头] + [星与虚点] + [信息] 三段正文拼接（上游不单列宫位宫头/星与虚点）；
    [信息] / [相位] / [行星] / [希腊点] / [可能性] 各一段（ensureSection：空段写「无数据」）；
    数据段（buildIndiaSnapshotDataSections）：[大运Dasha]（有行才出）→ Jyotish 派生段 → [未能计算]；附加分盘接在全文末尾（:1403-1425）。
    上游 buildIndiaSnapshotText 不挑 [月宿]/[古典]（aiExport.js:596 [MU] 注：印度盘 [古典] 是死复选框），skill 此前照本命盘
    整套出段并另起 [宫位宫头]/[星与虚点]，[星盘信息] 则由导出层拿通用起盘行兜底。各段行取自 engine/astro_snapshot.py
    （上游 buildAstroSnapshotContent 的逐字移植，与西占 chart 家族同一 builder）。
    """
    # 各段行 = 上游 buildAstroSnapshotContent 的同一段（engine/astro_snapshot.py 逐字移植：GFM 表、[V6-W2] 请求参数优先的
    # 宫制/黄道标注、showOnlyRulExaltReception 接纳过滤），本函数只按 buildIndiaSnapshotText 挑拣重排（splitSections 同口径）。
    snap = _astro_snap
    only_rul_exalt = _only_ruler_exalt_reception(payload)
    base_info = _india_replace_calibre_line(
        _india_lines(snap.build_base_info_lines(response, payload, with_time_basis=True)), response.get("_indiaCalibreLine")
    )
    info = _india_lines(snap.build_info_section(response, payload, only_ruler_exalt=only_rul_exalt))
    lines: list[str] = []
    _india_ensure_section(lines, "起盘信息", [*_india_lines(response.get("_indiaSchoolLines")), *base_info])
    _india_ensure_section(
        lines, "星盘信息",
        [*_india_lines(snap.build_house_cusp_lines(response)), *_india_lines(snap.build_star_and_lot_position_lines(response)), *info],
    )
    _india_ensure_section(lines, "信息", info)
    _india_ensure_section(lines, "相位", snap.build_aspect_section(response))
    _india_ensure_section(lines, "行星", snap.build_planet_section(response))
    _india_ensure_section(lines, "希腊点", snap.build_lots_section(response))
    _india_ensure_section(lines, "可能性", snap.build_possibility_lines(response))
    # 数据段 = vendored 上游 buildIndiaSnapshotDataSections（IndiaChart.js:1315-1331，v3.12.0 起）：[大运Dasha]（有行才出）
    # → Jyotish 派生段（buildJyotishSnapshotLines 键序）→ [未能计算]（回包 partialErrors 非空才出）。由 _attach_jyotish_sections
    # 挂 `_indiaDataSections`；旧 runtime 的 JS 引擎不回该键时退回分开的 `_indiaDashaLines` + `_jyotishSections`（同序、无 [未能计算]）。
    data_sections = response.get("_indiaDataSections")
    if not isinstance(data_sections, dict):
        data_sections = {}
        dasha_lines = response.get("_indiaDashaLines")
        if isinstance(dasha_lines, list) and dasha_lines:
            data_sections["大运Dasha"] = dasha_lines
        jyotish_sections = response.get("_jyotishSections")
        if isinstance(jyotish_sections, dict):
            for title, body in jyotish_sections.items():
                data_sections.setdefault(str(title), body)
    for title, body in data_sections.items():
        _india_ensure_section(lines, str(title), body)
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    # [附加分盘]（上游 buildIndiaSnapshotForFields:1325-1332）：`${text}\n\n${ensureSection 附加分盘}`；缺省不选 = 不产段。
    extra_vargas = response.get("_indiaExtraVargas")
    if isinstance(extra_vargas, str) and extra_vargas.strip():
        block: list[str] = []
        _india_ensure_section(block, "附加分盘", extra_vargas.split("\n"))
        text = re.sub(r"\n{3,}", "\n\n", f"{text}\n\n" + "\n".join(block)).strip()
    return text


def _chart_family_pattern_overview(response: dict[str, Any], *, only_ruler_exalt: bool) -> dict[str, Any]:
    """[古典] 的「古典格局」子块数据（上游 buildPatternOverview，本仓 Python 移植 `_pattern_overview`）。失败 → 空 + 警告。"""
    try:
        return _pattern_overview(response, only_ruler_exalt=only_ruler_exalt)
    except Exception as exc:  # noqa: BLE001 — 格局速览失败只少这个子块，不连累 [古典] 其余行；但须留痕
        _degrade("astro pattern overview (古典·古典格局子块) failed: %s", exc)
        return {}


def _build_astro_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    """西占整盘快照 = 上游 buildAstroSnapshotContent（astroAiSnapshot.js:1691-1744）逐段逐字移植（engine/astro_snapshot.py）。

    段序同上游：起盘信息 / 宫位宫头 / 星与虚点 / 信息 / 相位 / 行星 / 希腊点 / 12分度 / 主宰星链 / 分宫制宫神星表 / 古典 /
    （古典衍化四段，opt-in）/ 埃及历 / 寿命格局 / 可能性；每段过 buildSectionText（逐行 trim、去空行、全空不产段）。
    本仓在上游段之外保留的：[月宿]（skill-extra，恒星黄道盘才有，登记在 preset）、[古典格局]（上游由 AI 挂载 / 导出
    另拉 /astroextra/analysis 后拼接，本仓富化后在 preset 位次出）、派生盘专属段（`_derivedSelf`）。
    `payload` 即上游 fields（扁平请求体；fieldValue 两形同口径）。12分度 / 主宰星链 / 分宫制宫神星表 仍以
    `_natalExtras` 为「西占 chart 家族」标记（india_chart 走 `_build_india_snapshot_text`，不挂标记）。
    """
    snap = _astro_snap
    only_rul_exalt = _only_ruler_exalt_reception(payload)
    rendered: list[tuple[str, str]] = []

    def add(title: str, lines: list[Any]) -> None:
        body = "\n".join(snap.clean_lines(lines))
        if body:
            rendered.append((title, body))

    add("起盘信息", snap.build_base_info_lines(response, payload, with_time_basis=True))
    add("宫位宫头", snap.build_house_cusp_lines(response))
    add("星与虚点", snap.build_star_and_lot_position_lines(response))
    add("信息", snap.build_info_section(response, payload, only_ruler_exalt=only_rul_exalt))
    add("相位", snap.build_aspect_section(response))
    add("行星", snap.build_planet_section(response))
    add("月宿", _build_nakshatra_lines(response))
    add("希腊点", snap.build_lots_section(response))
    extras = response.get("_natalExtras") if isinstance(response.get("_natalExtras"), dict) else None
    if extras is not None:
        add("12分度", f"{extras.get('12分度') or ''}".split("\n"))
        # [主宰星链]（astroAiSnapshot.js:1010-1050）= 链行 + 判读口径行 + ◆ 整宫制宫主表（v57 #79）。
        add("主宰星链", [*f"{extras.get('主宰星链') or ''}".split("\n"), *snap.build_dispositor_tail_lines(response)])
        add("分宫制宫神星表", snap.build_house_system_ruler_lines(response, payload))
    add("古典", snap.build_classical_section(
        response, pattern_overview=_chart_family_pattern_overview(response, only_ruler_exalt=only_rul_exalt)
    ))
    # 古典衍化四段（astroAiSnapshot.js:1711-1729，上游 opt-in = 仅本命 astro 快照路径）：vendored astroClassicalDerived 算，
    # 只在 `_classicalDerived` 已挂载（= chart 工具）时出段。
    derived = response.get("_classicalDerived") if isinstance(response.get("_classicalDerived"), dict) else None
    if derived:
        for title in ("古典·派生宫转宫", "古典·气候带", "古典·显赫计分", "古典·世界范式盘"):
            add(title, f"{derived.get(title) or ''}".split("\n"))
    # [古典格局]：上游 buildClassicalAnalysisSection（:1529-1689）；本仓在 preset 位次（古典衍化四段之后、埃及历之前）出。
    if isinstance(response.get("_classicalAnalysis"), dict):
        add("古典格局", snap.build_classical_analysis_lines(response["_classicalAnalysis"]))
    # [埃及历]：vendored buildEgyptSectionLines（AstroEgypt.js:66-116）已带 `[埃及历]` 段头，这里只取正文。
    egypt = response.get("_egyptSection")
    if isinstance(egypt, str) and egypt.strip():
        add("埃及历", (egypt.split("\n", 1)[1] if egypt.startswith("[埃及历]\n") else egypt).split("\n"))
    if extras:
        add("寿命格局", f"{extras.get('寿命格局') or ''}".split("\n"))
    add("可能性", snap.build_possibility_lines(response))
    # 派生盘专属段（v3.9.2「快照重定源」）：[龙盘]/[调波盘]/[重置盘]，由各 runner 按上游 AuxLab builder 逐字排出并挂
    # `_derivedSelf`；上游 saveDerivedAstroSnapshot（derivedAstroSnapshot.js:35-45）接在整盘正文之后。空 lines 不产段。
    derived_self = response.get("_derivedSelf")
    if isinstance(derived_self, dict) and derived_self.get("title") and derived_self.get("lines"):
        add(str(derived_self["title"]), [str(line) for line in derived_self["lines"]])
    return _render_snapshot_text(rendered)


# 西占 chart 家族页面/挂载 fields 恒带日界两键（models/astro.js:395-403 页面种子 = dayBoundary.defaultAfter23NewDay() /
# defaultLateZiHourUseNextDay()；AI 挂载 aiAnalysisContext.js:606-607 buildFieldObject 同）——无本机全局设置时二者皆 1。
# 快照 [起盘信息] 的时间基准行与排盘规则行读的就是这两键，headless 缺键即按上游缺省 1/1 补（显式值照用）。
_CHART_FAMILY_DAY_BOUNDARY_DEFAULTS = {"after23NewDay": 1, "lateZiHourUseNextDay": 1}
# 走 `_build_astro_snapshot_text`（上游 buildAstroSnapshotContent 逐字移植）整盘快照的西占 chart 家族（india_chart 走自家
# 入口；relative / jieqi_year 以嵌入无头整盘的形式复用）。western_options_doc 据此给日界两键出说明。
_CHART_FAMILY_SNAPSHOT_TOOLS = frozenset({"chart", "chart13", "chart12", "hellen_chart", "harmonic", "draconic", "relocation"})


# 严格接纳开关的上游缺省（item：strongRecption）。后端 perchart.py:814 在请求**不带**该键时按 True（严格：只认本垣/擢升
# 接纳），而上游这四个键的排盘请求**恒带**它且缺省 0：
#   - 本命页 models/astro.js:105-108 字段种子 value 0 → fieldsToParams :506 `strongRecption: fields.strongRecption.value`；
#   - AI 挂载 aiAnalysisContext.js:567 buildFieldObject `record.strongRecption ?? 0` → fieldParams :704 同键下发；
#   - 十三/十二分盘 hellenastro/AstroChart13.js:24 同读 fields（hellen_chart 与 chart13 同打 /chart13）。
# 不补即 [信息] 接纳/互容（perchart.py:2152 `len(list) > 1 and strongRecption == False` 那支）与上游缺省盘不同。
# 调波/龙盘/重置盘（AuxLab）走 AstroExtraCommon.chartParams（:126-150），**不带**该键 → 后端缺省 True，本仓同样不补。
# 显式传值（true/false/0/1）照原样透传，永远优先。
_STRONG_RECEPTION_DEFAULT_TOOLS = frozenset({"chart", "chart13", "chart12", "hellen_chart"})


def _apply_chart_request_defaults(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    if tool_name not in _STRONG_RECEPTION_DEFAULT_TOOLS or payload.get("strongRecption") is not None:
        return payload
    return {**payload, "strongRecption": 0}


def _chart_family_snapshot_fields(payload: dict[str, Any]) -> dict[str, Any]:
    fields = dict(payload)
    for key, default in _CHART_FAMILY_DAY_BOUNDARY_DEFAULTS.items():
        if fields.get(key) is None:
            fields[key] = default
    return fields


_HEADERLESS_SECTION_TITLE = re.compile(r"^\[(.+?)\]$", re.M)


def _headerless_astro_snapshot_text(fields: dict[str, Any], chart_wrap: dict[str, Any]) -> str:
    """上游 buildAstroSnapshotContent(chartObj, fields, {headerless: true})（astroAiSnapshot.js:1740-1742）。

    嵌入父段（relative 比较盘 A/B、jieqi 分至盘）的整盘：整行段头 `[X]` 转 `· X` 标签，否则按段切分会把
    子段当顶层段拆出、按父段名过滤会把盘体删净。富化（12分度/主宰星链链行/寿命格局/埃及历）由调用方先挂上。
    """
    text = _build_astro_snapshot_text(fields, chart_wrap)
    return _HEADERLESS_SECTION_TITLE.sub(lambda match: f"· {match.group(1)}", text)


# 挂载分盘可选集（上游 v3.13.0 constants/AstroConst.js:1402-1409 INDIA_MOUNT_VARGA_OPTIONS，逐字；v3.12.0 改标签
# 「D9 婚姻→D9 合作」等 —— 此前这份手抄停在 v3.11 一直无信号，现由 tests/test_sync313_ports_guard.py 对上游逐值看守）。
_INDIA_MOUNT_VARGA_OPTIONS: tuple[tuple[int, str], ...] = (
    (1, "D1 命盘"), (2, "D2 财产"), (3, "D3 兄妹"), (4, "D4 资质"), (7, "D7 子嗣"), (9, "D9 合作"),
    (10, "D10 事业"), (12, "D12 父辈"), (16, "D16 座驾"), (20, "D20 灵魂"), (24, "D24 教育"), (27, "D27 生命"),
    (30, "D30 厄运"), (40, "D40 母系"), (45, "D45 父系"), (60, "D60 业力"),
)
_INDIA_MOUNT_EXTRA_VARGA_MAX = 4  # AstroConst.js:1418 INDIA_MOUNT_EXTRA_VARGA_MAX


def _normalize_india_extra_vargas(value: Any) -> tuple[list[int], list[Any]]:
    """上游 normalizeIndiaExtraVargas（AstroConst.js:1419-1435）逐条移植：字符串按 `,，空白` 切；parseInt；
    <=1 / 不在可选集 / 重复 / 超上限 4 的项丢弃。返回 (保留, 丢弃)——上游静默丢，skill 把丢弃项回报进 warnings。"""
    raw: Any = value
    if isinstance(raw, str):
        raw = [part for part in re.split(r"[,，\s]+", raw.strip()) if part] if raw.strip() else []
    if not isinstance(raw, (list, tuple)):
        return [], ([value] if value not in (None, "", [], ()) else [])
    allowed = {num for num, _ in _INDIA_MOUNT_VARGA_OPTIONS}
    out: list[int] = []
    dropped: list[Any] = []
    for item in raw:
        m = re.match(r"\s*([+-]?\d+)", f"{item}")  # JS parseInt：取前导整数
        num = int(m.group(1)) if m else None
        if num is None or num <= 1 or num not in allowed or num in out or len(out) >= _INDIA_MOUNT_EXTRA_VARGA_MAX:
            dropped.append(item)
            continue
        out.append(num)
    return out, dropped


def _india_mount_varga_label(chartnum: int) -> str:
    """上游 indiaMountVargaLabel（AstroConst.js:1410-1415）。"""
    for num, label in _INDIA_MOUNT_VARGA_OPTIONS:
        if num == chartnum:
            return label
    return f"D{chartnum}"


# 上游 AstroConst.INDIA_DASHA_DISPLAY_ONLY_SYSTEMS（:1819）：前端展示体系，数据恒在响应 dasha 块，不下发 dashaSystem。
_INDIA_DASHA_DISPLAY_ONLY = ("taraDasha", "akkg")
# 上游 AstroConst.INDIA_SCHOOL_DEFAULTS（:1650-1676）的 ayanamsa / hsys 两列：无头复算「给了 indiaSchool 但未显式给
# 岁差/宫制时按该派预设补默认」（IndiaChart.resolveIndiaHeadlessParams :1197-1213）。只取这两列；流派行文字走 JS 同源表。
_INDIA_SCHOOL_PRESETS: dict[str, tuple[str, int]] = {
    "parashari": ("lahiri", 0), "jaimini": ("lahiri", 0), "tajika": ("lahiri", 0),
    "kp": ("krishnamurti", 3), "nadi": ("lahiri", 0), "western_sidereal": ("fagan_bradley", 3),
}
_INDIA_PRASHNA_KEYS = ("prashnaNumber", "prashnaMatter", "prashnaSchools", "prashnaCuspMode", "prashnaPrimaryHouse")
# 直通键（webindiasrv 按名读：dashaSystem :408 / dashaSeed :404 / sthiraStart :405 / transitDate :590 / tajakaYear :686 /
# annualChartType :1178）。上游只在给了值时下发（fieldsToParams「缺省 undefined → 不入请求体」），空串一律剔掉。
_INDIA_VERBATIM_KEYS = ("dashaSystem", "dashaSeed", "sthiraStart", "transitDate", "tajakaYear", "annualChartType")


def _india_apply_school_presets(payload: dict[str, Any]) -> dict[str, Any]:
    """流派预设补默认（resolveIndiaHeadlessParams :1197-1213）：给了 indiaSchool 而未显式给岁差/宫制 → 按该派预设补。
    幂等；run_tool 在取盘**之前**对规范化输入套用一次 —— 快照 [起盘信息] 的岁差/宫制行与请求同一口径。"""
    school = f"{payload.get('indiaSchool') or ''}".strip()
    if school not in _INDIA_SCHOOL_PRESETS:
        return payload
    ayan, hsys = _INDIA_SCHOOL_PRESETS[school]
    out = dict(payload)
    if out.get("indiaAyanamsa") in (None, ""):
        out["indiaAyanamsa"] = ayan
        out["siderealMode"] = ayan
    if out.get("indiaHsys") in (None, ""):
        out["indiaHsys"] = hsys
        out["hsys"] = hsys
    return out


def _india_chart_zone_now(zone: Any) -> datetime:
    """上游 DateTime.wallClockForChart(zone)（comp/DateTime.js:37-45）：本盘时区（±HH:MM[:SS]）此刻的钟面；
    时区串认不出 → 本机此刻（上游同）。取「现在」一律经 _clock（测试可冻结）。"""
    m = re.fullmatch(r"([+-])(\d{2}):(\d{2})(?::(\d{2}))?", f"{zone or ''}")
    if not m:
        return _clock.now()
    sign = -1 if m.group(1) == "-" else 1
    offset = timedelta(hours=int(m.group(2)), minutes=int(m.group(3)), seconds=int(m.group(4) or 0))
    return _clock.now(timezone(sign * offset))


def _india_chart_remote_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """india_chart 的后端请求体：skill 侧开关 → 后端键（上游 IndiaChart.fieldsToParams 同一翻译）。

    `indiaTripataki`（上游挂载齿轮名）→ 后端 `tripataki=1`（IndiaChart.js:123-124；webindiasrv 读 data.get('tripataki')，
    12 次建盘 ≈0.3-0.8s 故 opt-in）。`indiaExtraVargas` 不下发主盘请求（附加分盘逐张另取）。
    其余条件透传逐条对齐 fieldsToParams（IndiaChart.js:79-143）与 resolveIndiaHeadlessParams（:1197-1213）：
    dashaSystem 展示体系不下发；indiaSchool 只补预设岁差/宫制（本身不下发）；问事族只在起了卦（prashnaTime）时下发，
    且问时数缺/非法 → 1（[Q-126/T-34]：缺它后端 KP 问事整段空）；年盘异地须经纬齐备。"""
    payload = _india_apply_school_presets(payload)
    remote = {k: v for k, v in payload.items() if k not in ("indiaExtraVargas", "indiaTripataki", "indiaSchool")}
    if payload.get("indiaTripataki") in (True, 1, "1"):
        remote["tripataki"] = 1
    for key in _INDIA_VERBATIM_KEYS:
        if remote.get(key) == "":
            remote.pop(key)
    if payload.get("dashaSystem") in _INDIA_DASHA_DISPLAY_ONLY:
        remote.pop("dashaSystem", None)
    if payload.get("prashnaTime"):
        try:
            number = int(f"{payload.get('prashnaNumber')}")
        except (TypeError, ValueError):
            number = 0
        remote["prashnaNumber"] = number if 1 <= number <= 249 else 1
        if payload.get("prashnaCuspMode") == "asc_driven_placidus":
            remote.pop("prashnaCuspMode", None)
    else:
        for key in _INDIA_PRASHNA_KEYS:
            remote.pop(key, None)
    if payload.get("varshaLat") in (None, "") or payload.get("varshaLon") in (None, ""):
        remote.pop("varshaLat", None)
        remote.pop("varshaLon", None)
    # 过运日 / 年度盘年份恒下发（IndiaChart.fieldsToParams:89-94，v3.12.0）：未给 = 本盘时区的今天 / 今年。
    # 后端 _compute_tajaka（webindiasrv.py:1291「仅 tajakaYear 提供时算」）缺键整段不算 —— skill 此前两键都不发，
    # 缺省盘的 [Tajika 年主]/[Tajika 年 Yoginī]/[Tajika Patyāyinī 年运]/[Tajika Mudda 年运] 等恒缺席（上游页面
    # 自 v3.11 起就恒带今年）；过运日缺键时后端取服务器本地今日，与本盘时区跨日时差一天。
    if remote.get("transitDate") in (None, "") or remote.get("tajakaYear") in (None, ""):
        today = _india_chart_zone_now(payload.get("zone"))
        if remote.get("transitDate") in (None, ""):
            remote["transitDate"] = today.strftime("%Y/%m/%d")
        if remote.get("tajakaYear") in (None, ""):
            remote["tajakaYear"] = today.year
    return remote
