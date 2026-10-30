"""中国术数快照：七政四余、卦码、紫微 / 六壬 / 节气 / 农历 / 月历 / 卦查询段。"""
from __future__ import annotations

import copy
import re
from datetime import timedelta, timezone
from typing import Any

from horosa_skill.engine import astro_snapshot as _astro_snap
from horosa_skill.service import _clock
from horosa_skill.civil_calendar import _month_day_label, _year_month_key
from horosa_skill.service._common import (
    _chart_at_moment_date_fields,
    _gender_label,
    _gz_text,
    _is_astro_chart_payload,
    _join_lines,
    _js_round,
    _msg,
    _render_snapshot_text,
    _stringify_export_body,
)
from horosa_skill.service._context import _degrade
from horosa_skill.service.text.astro_core import (
    _aspect_text,
    _build_base_info_lines,
    _build_house_cusp_lines,
    _build_star_and_lot_position_lines,
    _planet_label,
    _round3,
)
from horosa_skill.service.text.chart_family import _headerless_astro_snapshot_text
from horosa_skill.time_basis import GUOLAO_TIME_BASIS_NOTE, build_time_basis_line

# ── 七政四余·大限（命度→十二宫）+ 相位：星阙 GuoLaoMoiraWheel/GuoLaoChartMain 的 Python 移植 ──
# 仅作 JS 段 builder（vendored buildGuolaoLimitSection / buildGuolaoAspectSection）整体失败时的兜底（已进 warnings）。
# 政余格局（buildLocalMoiraPatterns Moira DSL）v0.11.0 起 JS vendor（guolaoMoira.js）评估；神煞行所需的
# chart.nongli.bazi.guolaoGods 由 runner 以 Java /nongli/time 挂上（上游 Java /chart 同形）。见 _run_guolao_chart_tool。
_GUOLAO_LIMIT_SEQ = [11.0, 10.0, 11.0, 15.0, 8.0, 7.0, 11.0, 4.5, 4.5, 4.5, 5.0, 5.0]
_GUOLAO_HOUSE_BRANCH = ("命宫", "财帛", "兄弟", "田宅", "男女", "奴仆", "夫妻", "疾厄", "迁移", "官禄", "福德", "相貌")
_GUOLAO_ASP_STATES = (("Applicative", "入相"), ("Exact", "精确"), ("Separative", "离相"), ("None", "容许"))


def _guolao_norm(deg: Any) -> float:
    try:
        val = float(deg) % 360
    except (TypeError, ValueError):
        return 0.0
    return val + 360 if val < 0 else val


def _guolao_object_ra(obj: Any, prefer_lon: bool) -> float | None:
    if not isinstance(obj, dict):
        return None
    if prefer_lon and obj.get("lon") is not None:
        raw = obj.get("lon")
    elif obj.get("ra") is not None:
        raw = obj.get("ra")
    else:
        raw = obj.get("lon")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _guolao_life_degree(chart: dict[str, Any]) -> float:
    # 命度（默认 ASC 模式）：primary=ASC 赤经，缺则命主度(LifeMasterDeg74)，再缺则太阳。
    objects = chart.get("objects") if isinstance(chart, dict) else []
    params = chart.get("params") if isinstance(chart, dict) else {}
    prefer_lon = isinstance(params, dict) and (str(params.get("doubingSu28")) == "4" or str(params.get("guolaoZhengSidereal")) == "1")
    by_id = {o.get("id"): o for o in objects or [] if isinstance(o, dict)}
    asc = _guolao_object_ra(by_id.get("Asc"), prefer_lon)
    life = _guolao_object_ra(by_id.get("LifeMasterDeg74"), prefer_lon)
    sun = _guolao_object_ra(by_id.get("Sun"), prefer_lon)
    val = asc if asc is not None else (life if life is not None else sun)
    return 0.0 if val is None else val


def _guolao_limit_table(life: float, birth_year: int) -> list[dict[str, Any]]:
    in_sign = _guolao_norm(life) % 30
    segs = [max(1, _js_round(9 + in_sign / 3))] + _GUOLAO_LIMIT_SEQ[1:]
    rows: list[dict[str, Any]] = []
    age = 1.0
    for k in range(12):
        span = max(0.5, float(segs[k]) if k < len(segs) else 0.0)
        from_age = _js_round(age)
        to_age = _js_round(age + span) - 1
        rows.append({
            "index": k + 1, "palace": _GUOLAO_HOUSE_BRANCH[k], "years": _js_round(span * 10) / 10,
            "from_age": from_age, "to_age": to_age,
            "from_year": birth_year + from_age - 1, "to_year": birth_year + to_age - 1,
        })
        age += span
    return rows


def _build_guolao_limit_lines(chart: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    """[大限] 的 Python 兜底（仅当 JS 段 builder 不可用时用；正路是 vendored buildGuolaoLimitSection）。"""
    life = _guolao_life_degree(chart)
    # 🔴 skill 归一后的日期是 YYYY-MM-DD（上游 fieldsToParams 才是 YYYY/MM/DD）：旧版只按 '/' 切，
    # int('2028-04-06') 失败 → 出生年恒 0 →「（0-12年）」这类年份全错。两种分隔都认。
    m = re.match(r"\s*(-?\d{1,4})", str(payload.get("date", "")))
    birth_year = int(m.group(1)) if m else 0
    return [
        f"第{r['index']}限 {r['palace']}：{r['from_age']}-{r['to_age']}岁（{r['from_year']}-{r['to_year']}年），约{r['years']}年"
        for r in _guolao_limit_table(life, birth_year)
    ]


def _build_guolao_aspect_lines(chart: dict[str, Any], response: dict[str, Any]) -> list[str]:
    aspects = (chart.get("aspects") if isinstance(chart, dict) else None) or (response.get("aspects") if isinstance(response, dict) else None)
    normal = aspects.get("normalAsp") if isinstance(aspects, dict) and isinstance(aspects.get("normalAsp"), dict) else aspects
    lines: list[str] = []
    if not isinstance(normal, dict):
        return lines
    for key, bucket in normal.items():
        if not isinstance(bucket, dict):
            continue
        for field, state in _GUOLAO_ASP_STATES:
            for asp in bucket.get(field) or []:
                if not isinstance(asp, dict) or not asp.get("id"):
                    continue
                try:
                    orb_text = f"，误差{_round3(float(asp.get('orb')))}"
                except (TypeError, ValueError):
                    orb_text = ""
                lines.append(f"{_planet_label(key)} {_aspect_text(asp.get('asp'))} {_planet_label(asp.get('id'))}（{state}{orb_text}）")
    return lines


def _moira_transit_moment(payload: dict[str, Any]) -> tuple[str, str]:
    """流年盘时刻：显式 moiraTransitDate/Time，缺省 = 当前日期（按出生时区）正午。"""
    date = f"{payload.get('moiraTransitDate') or ''}".strip().replace("/", "-")
    time_text = f"{payload.get('moiraTransitTime') or ''}".strip() or "12:00:00"
    if date:
        return date, time_text
    zone = f"{payload.get('zone') or ''}".strip()
    offset = timedelta(0)
    m = re.match(r"^([+-])(\d{1,2})(?::?(\d{2}))?$", zone)
    if m:
        sign = -1 if m.group(1) == "-" else 1
        offset = sign * timedelta(hours=int(m.group(2)), minutes=int(m.group(3) or 0))
    elif re.fullmatch(r"-?\d{1,2}(\.\d+)?", zone):
        offset = timedelta(hours=float(zone))
    now = _clock.now(timezone.utc) + offset
    return now.strftime("%Y-%m-%d"), time_text


def _swap_guolao_node_ids_deep(value: Any) -> Any:
    """上游 swapGuolaoNodeIdsDeep（GuoLaoChartMain.js:1150-1188）：北交/南交 id 深换（含字典键），其余原样。"""
    swap = {"North Node": "South Node", "South Node": "North Node"}
    if isinstance(value, str):
        return swap.get(value, value)
    if isinstance(value, list):
        return [_swap_guolao_node_ids_deep(item) for item in value]
    if isinstance(value, dict):
        return {swap.get(k, k) if isinstance(k, str) else k: _swap_guolao_node_ids_deep(v) for k, v in value.items()}
    return value


def _apply_guolao_node_mode(chart_obj: Any, settings: dict[str, Any]) -> Any:
    """上游 applyGuolaoNodeMode（:1202-1211）：罗计取「北罗南计」时整盘深换北/南交 id（盘面、规则、快照同吃换位后的盘），
    缺省「北计南罗」原样返回。"""
    if settings.get("guolaoNodeMode") != "northRahuSouthKetu" or not isinstance(chart_obj, dict):
        return chart_obj
    return _swap_guolao_node_ids_deep(copy.deepcopy(chart_obj))


def _guolao_slash_date(date_text: Any) -> str:
    """上游 GuoLaoChartMain.fieldsToParams:2337 `fields.date.value.format('YYYY/MM/DD')`——params.date 恒斜杠；skill 归一后是
    YYYY-MM-DD。[起盘信息] 日期行与 JS 段 builder 的 params.date（出生年取 split('/')[0]）都要斜杠形。"""
    text = f"{date_text or ''}"
    # DateTime.format('YYYY/MM/DD') = `${ad * year}/${MM}/${DD}`：公元前带负号、年不补零（'-0500-03-21' → '-500/03/21'；
    # 旧版只认四位正年，公元前原样留横杠 → 段 builder 的 split('/')[0] 取不到出生年）。
    if re.match(r"^-?\d{1,6}[-/]\d{1,2}[-/]\d{1,2}$", text.strip()):
        return _chart_at_moment_date_fields(text.strip())["date"]
    return text


_GUOLAO_LIFE_MODE_NAMES = {"yumao": "日出安命", "cotrans": "赤黄转换", "gumao": "遇卯安命(古法)"}


def _guolao_warn_missing_life_master(response: Any, life_mode: str) -> None:
    """命度法非「占星上升」时，上游命度 = Java BaZi.genLifeMasterDeg 算出的命度点 LifeMasterDeg74（ChartController.java:96，
    日出安命/遇卯/赤黄转换/自定命宫各有专算法）。本仓 /chart 走 Python 排盘服务，响应里没有这个点，runner 先向 Java /chart 取点
    （_guolao_attach_life_master）；仍缺（Java 不可用 / 两端盘面不一致）时上游消费方（lifeDegree / localLifeObject /
    QizhengMoiraRuleService.firstPresent）对缺点的回退序是「命度点 → 上升 → 太阳」，于是命度落回上升点。结果照出（与上游缺点时同形），
    但必须说出来：[起盘信息] 印的是所选命度法，数是上升的。"""
    mode = f"{life_mode or 'asc'}".strip() or "asc"
    if mode == "asc":
        return
    chart = response.get("chart") if isinstance(response, dict) else None
    objects = chart.get("objects") if isinstance(chart, dict) else None
    if any(isinstance(obj, dict) and obj.get("id") == "LifeMasterDeg74" for obj in objects or []):
        return
    name = _GUOLAO_LIFE_MODE_NAMES.get(mode) or f"自定命宫·{mode}"
    _degrade(
        "guolao LifeMasterDeg74 missing for lifeMode=%s (python chart service has no 七政命度点)", mode,
        note=(
            f"七政命度「{name}」要 Java 排盘层算出的命度点 LifeMasterDeg74（上游 /chart 走 Java ChartController → "
            "BaZi.genLifeMasterDeg）；本仓 /chart 走 Python 排盘服务、无此点，本次向 Java /chart 取点也未取到（Java 不可用或两端盘面"
            "不一致，见前一条）→ 命度按上游同一回退序落回上升点：[起盘信息] 命度行、[七政四余宫位与二十八宿星曜] 宫序、[大限]、"
            "[三主与化曜]/[限法实算] 与 Moira 规则层均按上升计。"
        ),
    )


def _build_guolao_snapshot_text(
    payload: dict[str, Any],
    response: dict[str, Any],
    pattern_text: str | None = None,
    *,
    info_sections: dict[str, Any] | None = None,
) -> str:
    """七政四余快照。`info_sections` = JS `guolao_moira` 的 info_sections 动作结果（vendored 上游段 builder）：
    setupLines/anchorLines（[起盘信息] 口径六行 + 命度/身度/宿主行）/ houseSu（[七政四余宫位与二十八宿星曜] GFM 表）/
    gods（[神煞]：rules 源 → 历法 ziGods 回退）/ limitSection（[大限]）/ masters（[三主与化曜]）/ limitCalc（[限法实算]）/
    aspects（[相位] GFM 表）。段序同上游 _buildGuolaoSnapshotTextV2Core（GuoLaoChartMain.js:2031-2140）：大限 → 三主与化曜 →
    限法实算 →（虚实/本命化曜/流年流曜 由 runner 插在 [政余格局] 之前）。info_sections 为空（JS 段 builder 整体失败，已进
    warnings）时宫位表 / 相位回退 Python 旧行式、[神煞] 为「无」。"""
    info = info_sections if isinstance(info_sections, dict) else {}
    chart = response.get("chart", {})
    houses = chart.get("houses") if isinstance(chart, dict) else []
    objects = chart.get("objects") if isinstance(chart, dict) else []

    house_text = f"{info.get('houseSu') or ''}".strip()
    if not house_text:
        house_lines: list[str] = []
        for index, house in enumerate(houses or [], start=1):
            house_id = house.get("id", f"House{index}") if isinstance(house, dict) else f"House{index}"
            house_lines.append(f"宫位：{house_id}")
            in_house = [obj for obj in (objects or []) if isinstance(obj, dict) and obj.get("house") == house_id]
            if not in_house:
                house_lines.append("星曜：无")
            else:
                for obj in in_house:
                    house_lines.append(f"星曜：{obj.get('id', '—')} {obj.get('su28', '')}".strip())
            house_lines.append("")
        house_text = "\n".join(house_lines).strip()
    aspect_text = f"{info.get('aspects') or ''}".strip() or "\n".join(_build_guolao_aspect_lines(chart, response)).strip()
    info_lines = [
        # 上游 params.date = fields.date.value.format('YYYY/MM/DD')（GuoLaoChartMain.js:2337/2043）。
        f"日期：{_guolao_slash_date(payload.get('date', '—'))} {payload.get('time', '—')}",
        f"时区：{payload.get('zone', '—')}",
        f"经纬度：{payload.get('lon', '—')} {payload.get('lat', '—')}",
        # [Q-191/T-134]（上游 GuoLaoChartMain.js:2046）时间基准 + 七政两套时标补注。上游 fieldsToParams 不带
        # timeAlg（盘面星体恒按输入钟面时刻换算）→ timeBasisLabel(undefined) = 钟表时；日界两键缺省取上游全局缺省 1/1
        # （defaultAfter23NewDay / defaultLateZiHourUseNextDay，本命四柱 /nongli/time 同口径）。
        build_time_basis_line(
            time_alg=None,
            late_zi_hour_use_next_day=1 if payload.get("lateZiHourUseNextDay") is None else payload.get("lateZiHourUseNextDay"),
            after23_new_day=1 if payload.get("after23NewDay") is None else payload.get("after23NewDay"),
            note=GUOLAO_TIME_BASIS_NOTE,
        ),
        # 七政命度 / 罗计 / 报时星太阳时 / 罗计取法 / 宿度制·身宫法 / 命主取法·行运法（上游 GuoLaoChartMain.js:2047-2073，
        # vendored buildGuolaoSetupLines 逐字产出）。
        *[f"{line}" for line in (info.get("setupLines") or []) if f"{line}".strip()],
        # [Q-231/Q-434]（上游 GuoLaoChartMain.js:2073-2076）命度 / 身度 / 命度宿主·身度宿主（右栏同源事实层）。
        *[f"{line}" for line in (info.get("anchorLines") or []) if f"{line}".strip()],
    ]
    limit_text = f"{info.get('limitSection') or ''}".strip() or "\n".join(_build_guolao_limit_lines(chart, payload)).strip()
    sections: list[tuple[str, str]] = [
        ("起盘信息", "\n".join(info_lines)),
        # 上游 :2079 buildHouseSuAndGodsSection(result, planetDisplay, fields) || '无'（无头 planetDisplay=null → 传统星曜）。
        ("七政四余宫位与二十八宿星曜", house_text or "无"),
        # 上游 :2086 buildRulesGodsSection(moiraRules) || buildHouseGodsSection(result, fields) || '无'。
        ("神煞", f"{info.get('gods') or ''}".strip() or "无"),
        ("大限", limit_text or "无"),
    ]
    # [Q-435]（上游 GuoLaoChartMain.js:2092-2104）三主化曜 / 难仇恩用 与 五限实算 / 行运法实算：有数据才产段。
    masters_text = f"{info.get('masters') or ''}".strip()
    if masters_text:
        sections.append(("三主与化曜", masters_text))
    limit_calc_text = f"{info.get('limitCalc') or ''}".strip()
    if limit_calc_text:
        sections.append(("限法实算", limit_calc_text))
    sections += [
        # 政余格局 (星阙 v2.6.x Moira DSL)：由 vendored guolaoMoira.js (buildLocalMoiraPatterns) 评估，经 js_client 注入。
        # 神煞行（天贵/玉贵/岁驾…）读 chart.nongli.bazi.guolaoGods —— runner 已把本命四柱挂上（同上游 Java /chart 形）。
        ("政余格局", (pattern_text or "").strip() or "无"),
        # 上游 :2138 buildGuolaoAspectSection(result)（GFM 五列表，无相位 → '无'）。
        ("相位", aspect_text or "无"),
    ]
    return _render_snapshot_text(sections)


def _normalize_gua_lines(lines: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in lines or []:
        if not isinstance(item, dict):
            continue
        value = 1 if bool(item.get("value")) else 0
        normalized.append(
            {
                "value": value,
                "change": bool(item.get("change")),
                "god": item.get("god"),
                "name": item.get("name"),
            }
        )
    return normalized[:6]


def _derive_gua_code(lines: list[dict[str, Any]]) -> str:
    return "".join(str(int(line.get("value", 0))) for line in lines) or "000000"


def _derive_changed_gua_code(lines: list[dict[str, Any]]) -> str:
    chars: list[str] = []
    for line in lines:
        value = int(line.get("value", 0))
        if line.get("change"):
            value = 1 - value
        chars.append(str(value))
    return "".join(chars) or "000000"


def _gua_code_lines(gua_code: Any, changed_code: Any) -> list[dict[str, Any]]:
    """给了本卦码（/变卦码）却没给 lines：卦线即码（初→上，1=阳），动爻 = 两码相异之位（_derive_changed_gua_code 的逆）。
    否则会落到以时起卦 —— [卦象] 写的是用户的本卦，[断卦结构]/[断诀命中] 判的却是另一卦。"""
    code = str(gua_code or "")
    if len(code) != 6 or set(code) - {"0", "1"}:
        return []
    changed = str(changed_code or "")
    moving = [len(changed) == 6 and changed[i] != code[i] for i in range(6)]
    return [{"value": int(code[i]), "change": moving[i], "god": None, "name": None} for i in range(6)]


def _ziwei_star_names(value: Any) -> list[str]:
    names: list[str] = []
    if isinstance(value, list):
        for item in value:
            text = _msg(item.get("name") or item.get("id")) if isinstance(item, dict) else _msg(item)
            if text:
                # 四化标注（紫微 P1 流派四化随 jar）：星体若带 sihua 化象，附「(化X)」。
                hua = item.get("sihua") or item.get("hua") if isinstance(item, dict) else None
                names.append(f"{text}（化{_msg(hua)}）" if hua else text)
    return names


def _build_ziwei_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    chart = response.get("chart", response if isinstance(response, dict) else {})
    houses = chart.get("houses") if isinstance(chart, dict) else []
    lines = [
        f"日期：{payload.get('date', '—')} {payload.get('time', '—')}",
        f"时区：{payload.get('zone', '—')}",
        f"经纬度：{payload.get('lon', '—')} {payload.get('lat', '—')}",
        # [Q-193/T-139]（上游 v3.11.0 ZiWeiMain.js:419-420）「未知」在紫微是按男排（Java 缺省 gender=true，
        # 引擎 male = gender !== 0）：只写「未知」会与命局阴阳自相矛盾。
        f"性别：{_gender_label(payload.get('gender'), unknown='未知（按男排）')}",
        f"时间算法：{'直接时间' if str(payload.get('timeAlg', 0)) == '1' else '真太阳时'}",
    ]
    # 命主/身主/五行局/斗君/年命（星阙 P0 杂曜与全盘信息一并落盘）。
    extra = [
        ("命主", chart.get("lifeMaster")),
        ("身主", chart.get("bodyMaster")),
        ("五行局", chart.get("wuxingJuText") or chart.get("wuxingJu")),
        ("斗君", chart.get("doujun")),
        ("子斗", chart.get("zidou")),
        ("年命", f"{_msg(chart.get('yearGan'))}{_msg(chart.get('yearZi'))}".strip() or None),
    ]
    for label, val in extra:
        text = _msg(val)
        if text:
            lines.append(f"{label}：{text}")

    overview: list[str] = []
    for index, house in enumerate(houses or [], start=1):
        if not isinstance(house, dict):
            continue
        name = house.get("name") or house.get("id") or f"宫位{index}"
        ganzi = _msg(house.get("ganzi")) or "无"
        direction = house.get("direction")
        direction_text = f"{direction[0]}~{direction[1]}" if isinstance(direction, list) and len(direction) == 2 else "无"
        # 主星 / 辅星 / 煞星 / 杂曜 (星阙 P0：杂曜补显 OthersGood/OthersBad/Small)，分类列出。
        main = _ziwei_star_names(house.get("starsMain"))
        assist = _ziwei_star_names(house.get("starsAssist"))
        evil = _ziwei_star_names(house.get("starsEvil"))
        misc = _ziwei_star_names(house.get("starsOthersGood")) + _ziwei_star_names(house.get("starsOthersBad")) + _ziwei_star_names(house.get("starsSmall"))
        small_dir = house.get("smallDirection")
        small_text = "、".join(str(a) for a in small_dir) if isinstance(small_dir, list) else _msg(small_dir)
        overview.append(f"{name}（干支={ganzi}，大限={direction_text}{('，小限=' + small_text) if small_text else ''}）")
        overview.append(f"主星：{'、'.join(main) or '无'}；辅星：{'、'.join(assist) or '无'}")
        overview.append(f"煞星：{'、'.join(evil) or '无'}；杂曜：{'、'.join(misc) or '无'}")
        overview.append("")

    # 命中格局（星阙 P2：格局随流派四化 + 新增格局/天伤天使安星，由 jar 返回 response.patterns）。
    patterns = response.get("patterns")
    pattern_lines: list[str] = []
    if isinstance(patterns, list):
        for pat in patterns:
            if not isinstance(pat, dict):
                continue
            pname = _msg(pat.get("name"))
            if not pname:
                continue
            cat = _msg(pat.get("category"))
            broke = "（破格）" if pat.get("broken") else ""
            duan = _msg(pat.get("duanyi"))
            head = f"{pname}（{cat}）{broke}" if cat else f"{pname}{broke}"
            pattern_lines.append(f"{head}：{duan}" if duan else head)

    # [来因宫]：与生年天干同干的宫。v3.9.2 起口径收紧为 isLaiyinPalace 单源
    # （ziweiSchools.js:127-131：首字 == 年干 **且** 地支非子非丑——子丑是借干宫，排除），
    # 排版 `宫名（干支）`、顿号连接。纯查表，响应里 chart.yearGan 与 houses[].ganzi 都现成。
    year_gan = f"{chart.get('yearGan') or ''}".strip() if isinstance(chart, dict) else ""
    laiyin_lines: list[str] = []
    if year_gan and isinstance(houses, list):
        hits = [
            f"{h.get('name') or ''}（{h.get('ganzi')}）"
            for h in houses
            if isinstance(h, dict)
            and f"{h.get('ganzi') or ''}".startswith(year_gan)
            and f"{h.get('ganzi') or ''}"[1:2] not in ("子", "丑")
        ]
        if hits:
            laiyin_lines.append("、".join(hits))

    # [身宫]（v3.9.2）：判据钉死引擎输出 house.isBody（本地/后端两引擎皆保证；bodyHouseIndex 仅本地
    # 引擎有故禁走旁路——上游 ZiWeiMain.js:477 原话）。找不到整段不产（best-effort，与来因宫同范式）。
    body_lines: list[str] = []
    if isinstance(houses, list):
        body_house = next((h for h in houses if isinstance(h, dict) and h.get("isBody")), None)
        if body_house and body_house.get("name"):
            ganzi = body_house.get("ganzi")
            body_lines.append(f"身宫落{body_house['name']}{f'（{ganzi}）' if ganzi else ''}")

    # [八字大运]（v3.9.2）：盘心十列（起运虚岁+大运干支+起始年）。数据与盘心/info 面板同源
    # chart.bazi.direct.direction，缺省（本地引擎无 direct）整段不产。GFM 表镜像 ZiWeiMain.js:498-508。
    bz_dayun_lines: list[str] = []
    bazi_node = chart.get("bazi") if isinstance(chart, dict) else None
    direct = bazi_node.get("direct") if isinstance(bazi_node, dict) else None
    direction = direct.get("direction") if isinstance(direct, dict) else None
    if isinstance(direction, list) and direction:
        rows = []
        for item in direction:
            if not isinstance(item, dict):
                continue
            main_direct = item.get("mainDirect") if isinstance(item.get("mainDirect"), dict) else {}
            gz = main_direct.get("ganzi")
            if not gz:
                continue
            rows.append(f"| {(item.get('age') or 0) + 1} | {item.get('startYear') or '无'} | {gz} |")
        if rows:
            bz_dayun_lines = ["| 起运虚岁 | 起始年份 | 大运干支 |", "| --- | --- | --- |", *rows]

    # 段序逐字镜像上游 v56 preset：起盘信息, 宫位总览, 身宫, 来因宫, 八字大运, 命中格局, (运限, 流派叠层)。
    blocks = [
        ("起盘信息", _join_lines(lines)),
        ("宫位总览", _join_lines(overview) or "无"),
    ]
    if body_lines:
        blocks.append(("身宫", _join_lines(body_lines)))
    if laiyin_lines:
        blocks.append(("来因宫", _join_lines(laiyin_lines)))
    if bz_dayun_lines:
        blocks.append(("八字大运", _join_lines(bz_dayun_lines)))
    blocks.append(("命中格局", _join_lines(pattern_lines) or "无"))
    text = _render_snapshot_text(blocks)
    # [运限] / [流派叠层]：由 vendored builder 出（自带段头），仅在调用方给了 period / schools 时产。
    extras = response.get("_ziweiExtras")
    if isinstance(extras, str) and extras.strip():
        text = f"{text}\n\n{extras.strip()}"
    return text


def _build_liureng_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    liureng = response.get("liureng", response if isinstance(response, dict) else {})
    nongli = liureng.get("nongli") if isinstance(liureng, dict) else {}
    four = liureng.get("fourColumns") if isinstance(liureng, dict) else {}
    runyear = response.get("runyear") or response.get("runYear") or liureng.get("runyear") if isinstance(liureng, dict) else None
    base_lines = [
        f"日期：{payload.get('date', '—')} {payload.get('time', '—')}",
        f"时区：{payload.get('zone', '—')}",
        f"经纬度：{payload.get('lon', '—')} {payload.get('lat', '—')}",
    ]
    if isinstance(nongli, dict) and nongli.get("birth"):
        base_lines.append(f"真太阳时：{nongli.get('birth')}")
    if isinstance(four, dict):
        base_lines.append(
            f"四柱：{_gz_text(four.get('year'))}年 {_gz_text(four.get('month'))}月 {_gz_text(four.get('day'))}日 {_gz_text(four.get('time'))}时"
        )
    sections: list[tuple[str, str]] = [("起盘信息", _join_lines(base_lines))]
    key_aliases = {
        "十二盘式": ("panStyle", "panStyleName", "pan_style"),
        "十二地盘/十二天盘/十二贵神对应": ("layout", "pan", "twelvePan"),
        "四课": ("keText", "ke", "fourLessons", "fourLesson", "sike", "courses"),
        "三传": ("sanChuan", "sanchuan", "threeTransmissions", "threeTransmission", "transmissions"),
    }
    for title, key in [
        ("十二盘式", "panStyle"),
        ("十二地盘/十二天盘/十二贵神对应", "layout"),
        ("四课", "ke"),
        ("三传", "sanChuan"),
        ("行年", None),
        ("旬日", "xun"),
        ("旺衰", "season"),
        ("基础神煞", "gods"),
        ("干煞", "godsGan"),
        ("月煞", "godsMonth"),
        ("支煞", "godsZi"),
        ("岁煞", "godsYear"),
        ("十二长生", "zhangsheng"),
        ("大格", "dage"),
        ("小局", "xiaoju"),
        ("参考", "reference"),
        ("概览", "overview"),
    ]:
        if title == "行年":
            body = _stringify_export_body(runyear) or "无"
        else:
            body = ""
            if isinstance(liureng, dict):
                for candidate_key in key_aliases.get(title, (key,)):
                    body = _stringify_export_body(liureng.get(candidate_key))
                    if body:
                        break
            if not body and isinstance(response, dict):
                for candidate_key in key_aliases.get(title, (key,)):
                    body = _stringify_export_body(response.get(candidate_key))
                    if body:
                        break
        sections.append((title, body or "无"))
    return _render_snapshot_text(sections)


def _build_jieqi_compact_chart_text(payload: dict[str, Any], chart_wrap: dict[str, Any]) -> str:
    lines = _build_base_info_lines(chart_wrap, payload)
    lines.extend(_build_house_cusp_lines(chart_wrap))
    lines.extend(_build_star_and_lot_position_lines(chart_wrap))
    return _join_lines(lines) or "无数据"


def _normalize_ganzi(text: Any) -> str:
    """JieQiChartsMain.js:349 normalizeGanZi：取前两字。"""
    raw = f"{text or ''}".strip()
    return raw[:2] if len(raw) >= 2 else raw


def _simple_four_columns(nongli: Any) -> dict[str, dict[str, str]] | None:
    """JieQiChartsMain.js:354 toSimpleFourColumns：农历字段 → 四柱 ganzi（无纳音）。"""
    if not isinstance(nongli, dict) or not nongli:
        return None
    return {
        "year": {"ganzi": _normalize_ganzi(nongli.get("yearGanZi") or nongli.get("yearJieqi") or nongli.get("year")), "naying": ""},
        "month": {"ganzi": _normalize_ganzi(nongli.get("monthGanZi")), "naying": ""},
        "day": {"ganzi": _normalize_ganzi(nongli.get("dayGanZi")), "naying": ""},
        "time": {"ganzi": _normalize_ganzi(nongli.get("time") or nongli.get("timeGanZi")), "naying": ""},
    }


def _jieqi_four_columns(item: Any) -> dict[str, Any] | None:
    """JieQiChartsMain.js:378 getJieqiFourColumns：bazi.fourColumns → fourColumns → bazi(农历形) → nongli。"""
    if not isinstance(item, dict):
        return None
    bazi = item.get("bazi")
    if isinstance(bazi, dict) and bazi.get("fourColumns"):
        return bazi["fourColumns"]
    if item.get("fourColumns"):
        return item["fourColumns"]
    if bazi:
        from_bazi = _simple_four_columns(bazi)
        if from_bazi:
            return from_bazi
    if item.get("nongli"):
        return _simple_four_columns(item["nongli"])
    return None


def _compact_jieqi_seed_row(item: dict[str, Any]) -> dict[str, Any]:
    """JieQiChartsMain.js:420 compactJieqiSeedResult 的逐行形状：四柱只留 ganzi/naying（Java 四柱对象带神煞/卦等，体量大）。"""
    four = _jieqi_four_columns(item)

    def part(value: Any) -> dict[str, str]:
        src = value if isinstance(value, dict) else {}
        return {"ganzi": f"{src.get('ganzi') or ''}", "naying": f"{src.get('naying') or ''}"}

    return {
        "ord": item.get("ord"),
        "jieqi": f"{item.get('jieqi') or ''}",
        "jie": item.get("jie"),
        "time": f"{item.get('time') or ''}",
        "ad": item.get("ad"),
        "bazi": {"fourColumns": {key: part(four.get(key)) for key in ("year", "month", "day", "time")}} if isinstance(four, dict) else None,
    }


def _build_jieqi24_table_lines(rows: Any) -> list[str]:
    """[二十四节气]（上游 JieQiChartsMain.js:893-906 [Q-224/T-180]）：交节时刻 + 四柱，与页面「二十四节气」页签同源。"""
    if not isinstance(rows, list) or not rows:
        return []
    out = ["| 节气 | 交节时刻 | 年柱 | 月柱 | 日柱 | 时柱 |", "| --- | --- | --- | --- | --- | --- |"]
    for item in rows:
        item = item if isinstance(item, dict) else {}
        four = _jieqi_four_columns(item) or {}

        def gz(key: str) -> str:
            column = four.get(key) if isinstance(four, dict) else None
            return f"{column.get('ganzi')}" if isinstance(column, dict) and column.get("ganzi") else ""

        out.append(f"| {item.get('jieqi') or ''} | {item.get('time') or ''} | {gz('year')} | {gz('month')} | {gz('day')} | {gz('time')} |")
    return out


def _build_jieqi_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    """上游 JieQiChartsMain.js:880-933 buildJieQiSnapshotText（整年快照）。

    [节气盘参数] → [二十四节气]（全年交节时刻+四柱；种子行由 `_attach_jieqi_year_extras` 取自 Java /jieqi/year）
    → 未拉取分至盘的说明行 → 逐节气 [X星盘]（buildAstroSnapshotContent 全口径无头整盘，Q-446/T-409）/ [X宿盘] /
    [X3D盘]（与 [X星盘] 同一盘数据的三维视图 → 一行指引，不整盘重复）。
    """
    charts = response.get("charts") if isinstance(response, dict) else {}
    charts = charts if isinstance(charts, dict) else {}
    jieqis = payload.get("jieqis") or ["春分", "夏至", "秋分", "冬至"]
    meta_lines = [
        f"年份：{payload.get('year', '—')}",
        f"时区：{payload.get('zone', '—')}",
        f"经纬度：{payload.get('lon', '—')} {payload.get('lat', '—')}",
        "说明：以下包含二分二至（春分、夏至、秋分、冬至）的星盘与宿盘专用导出。",
    ]
    sections: list[tuple[str, list[str]]] = [("节气盘参数", meta_lines)]
    rows24 = _build_jieqi24_table_lines(response.get("_jieqi24Seed") if isinstance(response, dict) else None)
    if rows24:
        sections.append(("二十四节气", rows24))
    # [Q-224/T-180] 分至盘未拉到时明示未纳入（上游句式逐字；行落在当时的末段——有 [二十四节气] 则随它，否则随参数段）。
    missing = [title for title in jieqis if not charts.get(title)]
    if missing:
        sections[-1][1].append(f"说明：{'、'.join(missing)}的星盘 / 宿盘尚未拉取（打开对应页签后再导出即纳入）。")
    rendered: list[tuple[str, str]] = [(title, _join_lines(lines)) for title, lines in sections]
    for title in jieqis:
        one = charts.get(title)
        if not isinstance(one, dict):
            continue
        fields = one.get("params") if isinstance(one.get("params"), dict) else payload
        chart_body = (
            (_headerless_astro_snapshot_text(fields, one) if _is_astro_chart_payload(one) else "")
            or _build_jieqi_compact_chart_text(fields, one)
            or "无数据"
        )
        rendered.append((f"{title}星盘", chart_body))
        # [X宿盘]（上游 JieQiChartsMain.js:928-930 `buildJieQiSuSection(one, flds, planetDisplay) || '无数据'`，:739-821 逐字移植）：
        # 页面星表缺省 DEFAULT_OBJECTS（models/app.js:201）；八字起宫要 chart.nongli.bazi（上游分至盘走 Java /chart 才有），
        # 本仓分至盘出自 Python /jieqi/year 无 nongli → 走上游同一回退分支（ASC 赤经起宫）。
        rendered.append((f"{title}宿盘", _astro_snap.build_jieqi_su_section(one, fields) or "无数据"))
        rendered.append((f"{title}3D盘", f"3D 盘为「{title}星盘」同一节气盘的三维视图(星位/宫位/相位同上 [{title}星盘] 段,无独立数据)。"))
    return _render_snapshot_text(rendered)


def _build_nongli_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    lines = [
        f"日期：{payload.get('date', '—')} {payload.get('time', '—')}",
        f"时区：{payload.get('zone', '—')}",
        f"经纬度：{payload.get('lon', '—')} {payload.get('lat', '—')}",
    ]
    for key in ("birth", "nongli", "year", "yearJieqi", "monthGanZi", "dayGanZi", "time", "jiedelta", "chef"):
        value = response.get(key) if isinstance(response, dict) else None
        if value:
            lines.append(f"{key}：{value}")
    return _render_snapshot_text([("起盘信息", _join_lines(lines))])


_CALENDAR_WEEK_CN = {0: "星期日", 1: "星期一", 2: "星期二", 3: "星期三", 4: "星期四", 5: "星期五", 6: "星期六"}


def _build_calendar_month_snapshot_text(payload: dict[str, Any], response: dict[str, Any]) -> str:
    """黄历/万年历快照：起盘信息 / 当月月历(GFM 表) / 选中日详情(可选) / 方法说明。

    月历行只收与 days[0] 同月的项（days 可能带下月补位）；字段均后端真值直引，不重算。
    """
    days = response.get("days") if isinstance(response.get("days"), list) else []
    prev_days = response.get("prevDays") if isinstance(response.get("prevDays"), list) else []

    # 年月 / 月日按日期串解析（dateStrSafe.yearMonthKey / monthDayLabel）——[:7] / [5:10] 按位置切，公元前 / 五位年切错位。
    def month_of(d: dict[str, Any]) -> str:
        return _year_month_key(str(d.get("birth") or ""))

    def day_of(d: dict[str, Any]) -> str:
        return _month_day_label(str(d.get("birth") or ""))

    # 上游 st.date.format('YYYY-MM')（DateTime：`${ad * year}-${MM}`，公元前带负号、年不补零）
    query_date = f"{payload.get('date') or ''}".strip()
    query_month = ""
    if re.match(r"^-?\d{1,6}[-/]\d{1,2}[-/]\d{1,2}", query_date):
        query_month = _chart_at_moment_date_fields(query_date)["date"].rsplit("/", 1)[0].replace("/", "-")
    query_month = query_month or query_date[:7] or (month_of(days[0]) if days else "")
    info_lines: list[str] = []
    if query_month:
        info_lines.append(f"查询月份：{query_month}")
    if payload.get("zone"):
        info_lines.append(f"时区：{payload.get('zone')}")
    if payload.get("lon"):
        info_lines.append(f"历算经度：{payload.get('lon')}")

    sections: list[tuple[str, str]] = [("起盘信息", _join_lines(info_lines))]

    table_lines: list[str] = []
    if days:
        cur_month = month_of(days[0])
        rows = [d for d in days if isinstance(d, dict) and month_of(d) == cur_month]
        if rows:
            table_lines.append("| 公历 | 星期 | 农历 | 日干支 | 节气/朔望 |")
            table_lines.append("| --- | --- | --- | --- | --- |")
            for d in rows:
                nl = str(d.get("day") or "")
                if d.get("dayInt") == 1:
                    nl = f"{'闰' if d.get('leap') else ''}{d.get('month') or ''}{d.get('day') or ''}"
                notes: list[str] = []
                if d.get("jieqi"):
                    notes.append(f"{d.get('jieqi')} {d.get('jieqiTime') or ''}".strip())
                if d.get("moonTime"):
                    mt = "朔" if d.get("dayInt") == 1 else ("望" if d.get("dayInt") == 15 else "月相")
                    notes.append(f"{mt} {d.get('moonTime')}".strip())
                week = _CALENDAR_WEEK_CN.get(d.get("dayOfWeek"), "")
                table_lines.append(f"| {day_of(d)} | {week} | {nl} | {d.get('dayGanZi') or ''} | {'；'.join(notes)} |")
    sections.append(("当月月历", _join_lines(table_lines) or "无"))

    # 选中日详情：payload.day 指定公历日，从当月/补位项中按 birth 前缀匹配。
    selected_day = str(payload.get("day") or "").strip()
    if selected_day:
        sel = next(
            (d for d in [*days, *prev_days] if isinstance(d, dict) and str(d.get("birth") or "").startswith(selected_day)),
            None,
        )
        detail_lines: list[str] = []
        if sel:
            week = _CALENDAR_WEEK_CN.get(sel.get("dayOfWeek"), "")
            detail_lines.append(f"公历：{str(sel.get('birth') or '').split(' ')[0]} {week}".strip())
            sel_month = f"{'闰' if sel.get('leap') else ''}{sel.get('month') or ''}"
            detail_lines.append(f"农历：{sel.get('year') or ''}年{sel_month}{sel.get('day') or ''}")
            if sel.get("yearNaying"):
                detail_lines.append(f"年纳音：{sel.get('yearNaying')}")
            detail_lines.append(
                f"干支：{sel.get('yearJieqi') or ''}年 {sel.get('monthGanZi') or ''}月 {sel.get('dayGanZi') or ''}日 {sel.get('time') or ''}时"
            )
            jiehou = [v for v in (sel.get("jiedelta"), sel.get("chef")) if v]
            if jiehou:
                detail_lines.append(f"节候：{'，'.join(jiehou)}")
            if sel.get("jieqi"):
                jdn_note = f"（jdn {sel.get('jieqiJdn')}）" if sel.get("jieqiJdn") else ""
                detail_lines.append(f"节气：{sel.get('jieqi')} {sel.get('jieqiTime') or ''}{jdn_note}")
            if sel.get("moonTime"):
                mt = "朔月" if sel.get("dayInt") == 1 else ("望月" if sel.get("dayInt") == 15 else "月相")
                jdn_note = f"（jdn {sel.get('moonJdn')}）" if sel.get("moonJdn") else ""
                detail_lines.append(f"{mt}：{sel.get('date') or ''} {sel.get('moonTime') or ''}{jdn_note}")
            if sel.get("qimengYearGua"):
                detail_lines.append(f"奇门年卦：{sel.get('qimengYearGua')}")
        sections.append(("选中日详情", _join_lines(detail_lines) or f"未在返回月历中找到 {selected_day}"))

    sections.append(
        (
            "方法说明",
            _join_lines(
                [
                    "月干支：以当天正午12点是否已跨节气决定归属月。",
                    "年柱口径：干支年以节气（立春）为界；农历年月日以朔望月与置闰为准，两者并列显示。",
                    "节气/朔望时刻为该历算经度下的真时刻；jdn 为对应儒略日数。",
                ]
            ),
        )
    )
    text = _render_snapshot_text(sections)
    # 子模块段块（老黄历 8 段 / 通书择日 / 日子馆 2 段）按上游段序插在 [选中日详情] 与 [方法说明] 之间。
    # 文本已由 vendored builder 带好各自的 `[段名]` 段头，故不进 sections 列表（那会被再包一层段头），
    # 而是在渲染完成后按 [方法说明] 的位置整块拼进去。
    #
    # v3.9.2 [E-6] 聚合导出**子源标签**：整行 `【农历】/【老黄历】/【通书择日】/【日子馆】` 是来源分界
    # 而非内容段（上游 CALENDAR_SUB_SOURCE_LABELS + extractCalendarContent：每个子模块文本前冠一行标签，
    # 经 parseSectionTitleLine 归一为段名）。skill 同形：农历标签置顶（NongLi 主 tab 内容之前）；
    # 老黄历/通书择日/日子馆标签由 calendar_extras 的分块边界插入。标签必须进 preset，
    # 否则用户自定义段时标签行会被过滤删掉、同名段无法分辨来源（上游原话）。
    text = f"【农历】\n{text}"
    extras = response.get("_calendarExtras")
    if isinstance(extras, str) and extras.strip():
        block = extras.strip()
        # 老黄历块以 [今日宜忌] 起、通书块以 [通书择日] 起、日子馆块以 [日子馆·个性化择日] 起——
        # 在各自块首插入子源标签行（缺块则该标签自然不出，与上游「未挂载子 tab 被跳过」同形）。
        for marker, label in (
            ("[今日宜忌]", "【老黄历】"),
            ("[通书择日]", "【通书择日】"),
            ("[日子馆·个性化择日]", "【日子馆】"),
        ):
            at = block.find(marker)
            if at >= 0:
                block = f"{block[:at]}{label}\n{block[at:]}"
        marker = "[方法说明]"
        at = text.find(marker)
        if at >= 0:
            text = f"{text[:at]}{block}\n\n{text[at:]}"
        else:
            text = f"{text}\n\n{block}"
    return text


def _build_gua_lookup_snapshot_text(tool_name: str, payload: dict[str, Any], response: dict[str, Any]) -> str:
    queried = payload.get("name") or []
    gua_lines: list[str] = []
    desc_lines: list[str] = []
    for key in queried:
        item = response.get(key) if isinstance(response, dict) else None
        if isinstance(item, dict):
            gua_lines.append(f"{key}：{item.get('name', '无')}")
            text = item.get("卦辞") or item.get("desc") or item.get("text") or _stringify_export_body(item)
            desc_lines.append(f"{item.get('name', key)}：{text}")
        else:
            gua_lines.append(f"{key}：无")
    return _render_snapshot_text(
        [
            ("起盘信息", _join_lines([f"查询：{'、'.join(queried) if queried else '无'}", f"来源：{tool_name}"])),
            ("卦象", _join_lines(gua_lines) or "无"),
            ("六爻与动爻", "此工具为卦义查询，不包含起卦六爻与动爻排盘；如需完整六爻盘，请调用 sixyao。"),
            (
                "卦辞与断语",
                _join_lines(desc_lines)
                or "本次卦义查询未返回卦辞断语；请基于已返回卦象说明，不能臆造不存在的数据来源。",
            ),
        ]
    )
