"""天文地占（geomancy）快照与选项表、玄史记录。"""
from __future__ import annotations

from typing import Any

from horosa_skill.service._common import (
    _join_lines,
    _render_snapshot_text,
    _stringify_export_body,
)

# ── 天文地占 (astronomical geomancy)：4 母卦→16 图形 + 十二宫图形入宫 + 判官/见证/解读技法。port GeomancyMain.buildGeomancySnapshotText ──
_GEO_TRAD = {"european_classical": "古典定局派", "european_planetary": "行星共鸣派", "european_modern": "现代综合派(同古典口径)", "arabic_raml": "阿拉伯沙占派", "india_ramal": "印度骰占派", "sikidy": "异或表盘", "hakata": "四片盘", "greek": "希腊传本", "ifa": "西非同族结构对照"}
_GEO_PERF = {"occupation": "入主成局", "conjunction": "会合成局", "mutation": "互变成局", "translation": "传递成局", "none": "未成局"}
_GEO_ASP = {"conjunction": "合", "sextile": "六分(吉)", "square": "刑(凶)", "trine": "拱(吉)", "opposition": "冲", "none": "无相位"}
_GEO_SLOT = ["母一", "母二", "母三", "母四", "女一", "女二", "女三", "女四", "甥一", "甥二", "甥三", "甥四", "右证", "左证", "判官", "调和"]
# 传本粒度设置注记（仅注记与主流缺省不同者）；镜像 GeomancyMain GNAME。
_GEO_GNAME = {
    "house_projection": {"sequential": "落星=不落(仅图形入宫)", "astro_from_chart": "落星=占星甲(星落所主图之宫)", "astro_bytwelves": "落星=占星乙(另起点数定宫)"},
    "compound_mode": {"reverse": "合成同伴=逆转法"},
    "number_system": {"planetary": "图数=行星序", "abjad": "图数=字母值"},
    "reconciler_mode": {"judge_querent_significator": "调和者=判官⊕问者指示星"},
    "mark_style": {"lines": "记号=线形", "bindu": "记号=点线", "tablets": "记号=开合片"},
    "direction": {"RTL": "书写=自右向左"},
}
_GEO_PARITY_SCOPE = {"shield16": "全盘十六图", "mothers": "四母", "houses12": "十二宫"}
_GEO_PZH = {"Sun": "日", "Moon": "月", "Mercury": "水", "Venus": "金", "Mars": "火", "Jupiter": "木", "Saturn": "土", "NorthNode": "龙头", "SouthNode": "龙尾"}
_GEO_TRI = {1: "火", 5: "火", 9: "火", 2: "地", 6: "地", 10: "地", 3: "风", 7: "风", 11: "风", 4: "水", 8: "水", 12: "水"}
# ifa（西非同族）为结构对照模式：不产地占判读。skill 暴露的 8 家占断传本白名单（明确排除 ifa）。
_GEOMANCY_PROFILES = ("european_classical", "european_planetary", "european_modern", "arabic_raml", "india_ramal", "sikidy", "hakata", "greek")
# 传本粒度覆盖 passthrough 白名单（未传即不发 → 内核回落 profile 默认，旧盘字节零变）。键名 = webgeomancysrv.reading
# 的 `_opt/_optb(...)` 读键（:443-465）；sync311 F12 补 housePlacement / 行星地占盘四键（castNumbers 另行处理）。
_GEOMANCY_OPTION_KEYS = (
    "markStyle", "direction", "houseProjection", "wrapHouses", "reconciler", "reconcilerMode", "haltEnabled",
    "compoundMode", "numberSystem", "chartMode", "houseSystem", "ascSource", "namesSystem", "parityScope",
    "housePlacement", "planetaryChart", "planetaryChartZodiac", "planetaryChartNodes", "planetaryChartExtras",
)
# 问类 = 后端 _QTYPES 十一类（webgeomancysrv.py:42-46）；其它值后端静默改回 custom（:379-381）→ 这里显式拒。
# 值 = 问类预设所问宫：上游 GeomancyMain.QUESTION_TYPE_HOUSE（:204-208，注「与引擎 question_house 表同源」，
# 即内核 data/house_meanings.json question_house）；两边逐值对拍见 tests/test_sync311_divination_w3.py。
_GEOMANCY_QUESTION_HOUSE = {
    "custom": 1, "life": 1, "health": 6, "wealth": 2, "marriage": 7, "career": 10, "children": 5, "journey": 9,
    "religion": 9, "enemy": 7, "death": 8,
}
_GEOMANCY_QUESTION_TYPES = tuple(_GEOMANCY_QUESTION_HOUSE)


def _geomancy_time_seed(parts: dict[str, int]) -> int:
    """上游 GeomancyMain.computeTimeSeed（:229-246）：(YY)MMDDHHmm 折进 int32 正区间（mod 2^31−1）。"""
    value = (parts["year"] % 100) * 100000000 + parts["month"] * 1000000 + parts["day"] * 10000 + parts["hour"] * 100 + parts["minute"]
    return value % 2147483647


def _geo_figure_line(fig: Any, role: str) -> str:
    if not isinstance(fig, dict):
        return ""
    parts = [p for p in [fig.get("nameZh") or fig.get("nameEn")] if p]
    if fig.get("planetZh"):
        parts.append(f"行星{fig['planetZh']}")
    if fig.get("elementZh"):
        parts.append(fig["elementZh"])
    if fig.get("keywordsZh"):
        parts.append(fig["keywordsZh"])
    return f"{role}：{' · '.join(parts)}" if parts else ""


def _build_geomancy_snapshot_text(response: dict[str, Any]) -> str:
    reading = response.get("reading") if isinstance(response.get("reading"), dict) else {}
    # 结构对照模式（ifa）防御性早退：skill schema 已挡 ifa，此分支仅为稳健 + 供 export_parse 识别面。
    if reading.get("structuralOnly") or reading.get("structural_only"):
        notice = reading.get("culturalNotice") or reading.get("note") or "独立圣传体系，仅结构同构对照，不套地占含义、不构成占断。"
        body = [notice]
        ifa = reading.get("ifa") if isinstance(reading.get("ifa"), dict) else {}
        if ifa.get("label"):
            right = ifa.get("right") or {}
            left = ifa.get("left") or {}
            body.append(
                f"结构对照：{ifa['label']}{'(主形)' if ifa.get('is_meji') else ''}；"
                f"右列 {right.get('odu_name') or '—'}→{right.get('figure') or '—'}、"
                f"左列 {left.get('odu_name') or '—'}→{left.get('figure') or '—'}（自右向左读）"
            )
        body.append("※ 本模式只作形的识别与比特对照，不产出该体系之占断，亦不套用地占含义。")
        return _render_snapshot_text([("边界声明", "\n".join(body).strip())])

    # [起卦信息]：问题/问类/上升 + 传本设置（仅注记非默认口径）。
    info = [
        f"问题：{reading.get('question') or '—'}",
        f"问类：{reading.get('questionTypeZh') or reading.get('questionType') or '—'}",
        f"上升图形：{(reading.get('ascendantFigure') or {}).get('nameZh') or ''}（上升星座 {reading.get('ascendantSignZh') or ''}）",
    ]
    tb: list[str] = []
    if reading.get("profileId") and reading.get("profileId") != "european_classical":
        tb.append(f"流派={_GEO_TRAD.get(reading['profileId'], reading['profileId'])}")
    if reading.get("zodiacSystem") == "planetary":
        tb.append("黄道=行星归属体系")
    if reading.get("readingScope") and reading.get("readingScope") != "L3":
        tb.append(f"范围={reading['readingScope']}")
    gs = reading.get("settings") if isinstance(reading.get("settings"), dict) else {}
    for gkey, gtable in _GEO_GNAME.items():
        hit = gtable.get(gs.get(gkey))
        if hit:
            tb.append(hit)
    if gs.get("wrap_houses") is True:
        tb.append("宫位成环")
    if gs.get("reconciler") is False:
        tb.append("不取调和者")
    if gs.get("halt_enabled") is False:
        tb.append("不启用首母中止")
    if tb:
        info.append(f"传本设置：{'、'.join(tb)}")

    # [判定]：首母中止 + 判官/调和者/证 + 主宫 + sikidy/hakata 中栏结论。
    judge: list[str] = []
    if reading.get("haltedOnFirstMother"):
        judge.append("⚠ 首母中止：首母落 Rubeus/Cauda 之属，依所选传本传统应中止本占、另择时再占（以下判读仅作参考）。")
    for fig, role in ((reading.get("judge"), "判官"), (reading.get("reconciler"), "调和者"), (reading.get("rightWitness"), "右证(过去/问者)"), (reading.get("leftWitness"), "左证(现在/所问)")):
        ln = _geo_figure_line(fig, role)
        if ln:
            judge.append(ln)
    if reading.get("primaryHouse"):
        judge.append(f"主宫：第 {reading['primaryHouse']} 宫")
    sk = reading.get("sikidy")
    if isinstance(sk, dict):
        princes = sk.get("princes") if isinstance(sk.get("princes"), list) else []
        judge.append(
            f"异或表盘：三道校验{'通过' if sk.get('valid') else '未过'}"
            f"{'；红 Sikidy(大凶)' if sk.get('red_sikidy') else ''}"
            f"{('；诸侯列:' + '、'.join(str(p) for p in princes)) if princes else ''}"
        )
        compare = sk.get("compare") if isinstance(sk.get("compare"), dict) else None
        columns = sk.get("columns") if isinstance(sk.get("columns"), dict) else None
        if compare and columns:
            hits = [f"第{k}列 {(columns.get(k) or {}).get('name') or ''}（{(columns.get(k) or {}).get('meaning') or ''}）"
                    for k in compare if compare.get(k) and compare[k].get("equal")]
            judge.append(f"列比对：问者列与{('、'.join(hits) + ' 同形 —— 事之所系在此') if hits else '各主题列皆不同形，无直指之应'}")
    hk = reading.get("hakata")
    if isinstance(hk, dict):
        tablets = hk.get("tablets") if isinstance(hk.get("tablets"), list) else []
        tb_str = " ".join(f"{t.get('name') or ''}{'开' if t.get('open') else '合'}" for t in tablets if isinstance(t, dict))
        judge.append(
            f"四片盘：{tb_str or '—'} → {hk.get('figure_zh') or hk.get('figure') or '—'}"
            f"{('；' + hk['reading']) if hk.get('reading') else ''}"
            f"{('；' + hk['orientation']) if hk.get('orientation') else ''}"
        )

    # [解读技法]（条件）+ 判官之数折入。
    tech: list[str] = []
    t = reading.get("technique")
    if isinstance(t, dict):
        perf = t.get("perfection")
        if perf and perf != "none":
            tech.append(f"完美：{_GEO_PERF.get(perf, perf)}")
        elif t.get("perfection_by_aspect"):
            tech.append(f"完美：借相位({_GEO_ASP.get(t['perfection_by_aspect'], t['perfection_by_aspect'])})成局")
        else:
            tech.append("完美：未成局")
        tech.append(f"相位：{_GEO_ASP.get(t.get('aspect'), t.get('aspect'))}")
        if t.get("prohibition"):
            tech.append(f"阻碍：第 {t['prohibition']} 宫强凶图阻断")
        pp = t.get("points_parity")
        if isinstance(pp, dict):
            scope = _GEO_PARITY_SCOPE.get(pp.get("scope"), "全盘十六图")
            degen = "，该取样结构恒偶、不具判别力" if pp.get("degenerate") else ""
            tech.append(f"点数是否：总 {pp.get('total')} 点·{'偶→是/稳' if pp.get('parity') == 'even' else '奇→否/动'}（取样 {scope}{degen}）")
        tm = t.get("timing")
        if isinstance(tm, dict):
            tech.append(f"应期：{'速' if tm.get('speed') == 'fast' else '迟'}·以「{tm.get('unit')}」计")
        vp = t.get("via_puncti")
        if isinstance(vp, dict):
            tech.append(f"点之路：{'贯通' if vp.get('through') else '断于' + str(vp.get('broken_at'))}")
        if t.get("natural_cosignificator"):
            tech.append("自然共主：月亮")
        tri = t.get("triplicities") if isinstance(t.get("triplicities"), list) else []
        if len(tri) > 1:
            tech.append(f"黄道宫三方：宫 {'/'.join(str(x) for x in tri)}（{_GEO_TRI.get(tri[0], '')}三方）")
        if isinstance(tm, dict) and isinstance(tm.get("quantity"), dict):
            q = tm["quantity"]
            tech.append(f"数量：{q.get('label')}(总 {q.get('total')} 点·域 {q.get('min')}–{q.get('max')})")
    jn = (reading.get("judge") or {}).get("number") if isinstance(reading.get("judge"), dict) else None
    if isinstance(jn, dict) and jn.get("system") != "points":
        tech.append(f"判官之数：{jn.get('value')}（{jn.get('basis') or jn.get('system')}）")

    # [转宫派生]（条件）
    derived_lines: list[str] = []
    d = reading.get("derived")
    if isinstance(d, dict):
        derived_lines.append(f"以第 {d.get('turn_to')} 宫为新命宫：新命宫 {d.get('derived_querent_house')} → 所问宫 {d.get('derived_quesited_house')}")
        derived_lines.append(f"派生完美：{_GEO_PERF.get(d.get('perfection'), d.get('perfection'))}{('；派生阻碍在第 ' + str(d['prohibition']) + ' 宫') if d.get('prohibition') else ''}")
        df = d.get("figure")
        if isinstance(df, dict):
            derived_lines.append(f"派生宫图：{df.get('nameZh') or df.get('nameEn') or '—'}")

    # [定局落星·甲/乙]（条件）
    placement_a: list[str] = []
    ppA = reading.get("planetPlacement") if isinstance(reading.get("planetPlacement"), dict) else {}
    ppA_keys = [k for k in ppA if (ppA.get(k) or [])]
    if ppA_keys:
        placement_a.append("；".join(f"{_GEO_PZH.get(k, k)}→{'/'.join(f'{h}宫' for h in ppA[k])}" for k in ppA_keys))
        absent = [_GEO_PZH.get(k, k) for k in ppA if not (ppA.get(k) or [])]
        if absent:
            placement_a.append(f"（缺席：{'、'.join(absent)} —— 星所主之图未入盘，乃本法固有，非算漏）")
    placement_b: list[str] = []
    ppB = reading.get("planetPlacementByTwelves")
    if isinstance(ppB, dict) and ppB:
        placement_b.append("；".join(f"{_GEO_PZH.get(k, k)}→{ppB[k]}宫" for k in ppB))

    # [十二宫·图形入宫] markdown 表（印度派多支名/曜两列）
    houses = reading.get("houses") if isinstance(reading.get("houses"), list) else []
    house_body = ""
    if houses:
        is_india = reading.get("profileId") == "india_ramal"
        rows = (["| 宫 | 宫名 | 支名 | 角色 | 图形 | 曜 | 断语 |", "| --- | --- | --- | --- | --- | --- | --- |"]
                if is_india else ["| 宫 | 宫名 | 角色 | 图形 | 断语 |", "| --- | --- | --- | --- | --- |"])
        for h in houses:
            if not isinstance(h, dict):
                continue
            fig = h.get("figure") or {}
            roles = h.get("roles") or []
            role = "【所问】" if "quesited" in roles else ("【问者】" if "querent" in roles else "—")
            if is_india:
                bh = f"{h['bhava']}（{h.get('bhavaZh') or ''}）" if h.get("bhava") else "—"
                gr = ((fig.get("vedic") or {}).get("graha_zh")) or "—"
                rows.append(f"| 第{h.get('house')}宫 | {h.get('nameZh') or '—'} | {bh} | {role} | {fig.get('nameZh') or fig.get('nameEn') or '—'} | {gr} | {h.get('reading') or '—'} |")
            else:
                rows.append(f"| 第{h.get('house')}宫 | {h.get('nameZh') or '—'} | {role} | {fig.get('nameZh') or fig.get('nameEn') or '—'} | {h.get('reading') or '—'} |")
        house_body = "\n".join(rows)

    # [十六图形] markdown 表
    figs = reading.get("figures16") if isinstance(reading.get("figures16"), list) else []
    fig_body = ""
    if figs:
        rows = ["| 位 | 图形 | 行星 | 元素 |", "| --- | --- | --- | --- |"]
        for i, f in enumerate(figs):
            if not isinstance(f, dict):
                continue
            slot = _GEO_SLOT[i] if i < len(_GEO_SLOT) else f"图{i + 1}"
            rows.append(f"| {slot} | {f.get('nameZh') or f.get('nameEn')} | {f.get('planetZh') or '—'} | {f.get('elementZh') or '—'} |")
        fig_body = "\n".join(rows)

    # [图形释义] doctrine 段：上游默认关段，skill 不产出（仅在 preset 保留作 export_parse 识别面）。
    sections: list[tuple[str, str]] = [("起卦信息", "\n".join(info).strip())]
    if judge:
        sections.append(("判定", "\n".join(judge).strip()))
    if tech:
        sections.append(("解读技法", "\n".join(tech).strip()))
    if derived_lines:
        sections.append(("转宫派生", "\n".join(derived_lines).strip()))
    if placement_a:
        sections.append(("定局落星·甲", "\n".join(placement_a).strip()))
    if placement_b:
        sections.append(("定局落星·乙", "\n".join(placement_b).strip()))
    if house_body:
        sections.append(("十二宫·图形入宫", house_body))
    if fig_body:
        sections.append(("十六图形", fig_body))
    return _render_snapshot_text(sections)


# 玄史条目的展示键序（存在才渲染；覆盖 事件/天象/人物/朝代/术数/名词/故事 各族的常见字段）。
_XUANSHI_FIELD_ORDER: tuple[tuple[str, str], ...] = (
    ("title", "标题"), ("name", "名称"), ("event_id", "编号"), ("slug", "slug"), ("id", "编号"),
    ("tradition", "传统"), ("dynasty", "朝代"), ("period", "时期"), ("year", "公历年"),
    ("history", "史书"), ("volume_no", "卷次"), ("citation", "引证"),
    ("region", "地域"), ("operators", "施术者"), ("targets", "对象"), ("techniques", "术数"),
    ("omen", "天象类"), ("source", "出处"), ("trigger", "起因"), ("procedure", "过程"),
    ("outcome", "结局"), ("evidence", "证据"), ("original_text", "原文"), ("modern_text", "白话"),
    ("reading", "解读"), ("reliability_note", "可信度"), ("cross_ref", "互见"),
    ("summary", "摘要"), ("text", "正文"), ("desc", "说明"), ("note", "注"),
)


def _xuanshi_record_lines(rec: dict[str, Any], *, brief: bool) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for key, label in _XUANSHI_FIELD_ORDER:
        if key in seen:
            continue
        value = rec.get(key)
        if value is None or value == "" or value == []:
            continue
        seen.add(key)
        if isinstance(value, list):
            value = "、".join(f"{v}" for v in value[:12])
        text = f"{value}"
        if brief and len(text) > 120:
            text = text[:120] + "…"
        lines.append(f"{label}：{text}")
        if brief and len(lines) >= 4:
            break
    return lines


def _build_xuanshi_snapshot_text(action: str, body: dict[str, Any], response: Any) -> str:
    cond = [f"action：{action}"] + [f"{k}：{v}" for k, v in body.items()]
    sections: list[tuple[str, str]] = [("检索条件", _join_lines(cond))]
    # 列表族：裸数组，或 {items|list|events|figures…: [...], total: n} 包装；详情族：单 dict 条目。
    items: list[Any] | None = None
    total: Any = None
    detail: dict[str, Any] | None = None
    if isinstance(response, list):
        items = response
    elif isinstance(response, dict):
        for key in ("items", "list", "events", "figures", "records", "results", "rows", "points", "nodes", "stories"):
            if isinstance(response.get(key), list):
                items = response[key]
                total = response.get("total")
                break
        if items is None:
            # summary/timeline/facets 一类结构响应：作总览渲染；带 title/event_id 的当详情。
            if any(k in response for k in ("title", "event_id", "original_text", "name")):
                detail = response
            else:
                overview = _stringify_export_body(response)
                if overview.strip():
                    sections.append(("结果总览", overview.strip()[:4000]))
    if items is not None:
        head = f"命中 {total if total is not None else len(items)} 条（列出 {min(len(items), 20)} 条）"
        sections.append(("结果总览", head))
        rows: list[str] = []
        for i, rec in enumerate(items[:20], 1):
            if isinstance(rec, dict):
                brief = "；".join(_xuanshi_record_lines(rec, brief=True)) or _stringify_export_body(rec)[:120]
            else:
                brief = f"{rec}"
            rows.append(f"{i}. {brief}")
        if rows:
            sections.append(("条目列表", _join_lines(rows)))
    if detail is not None:
        lines = _xuanshi_record_lines(detail, brief=False)
        if lines:
            sections.append(("条目详情", _join_lines(lines)))
        related = detail.get("related") or detail.get("same_dyn") or detail.get("same_hist")
        if isinstance(related, list) and related:
            rel = ["、".join(f"{(r.get('title') or r.get('event_id') or r)}" if isinstance(r, dict) else f"{r}" for r in related[:8])]
            sections.append(("相关条目", _join_lines(rel)))
    # 出处引证聚合（列表与详情通吃）
    cites: list[str] = []
    pool = (items or [])[:20] + ([detail] if detail else [])
    for rec in pool:
        if isinstance(rec, dict) and rec.get("citation"):
            c = f"{rec['citation']}"
            if c not in cites:
                cites.append(c)
    if cites:
        sections.append(("出处引证", _join_lines(cites[:20])))
    return _render_snapshot_text(sections)
