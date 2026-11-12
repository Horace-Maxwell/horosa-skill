"""地名 → 坐标 + 时区（PlaceAPI，v0.48.0）：门面 horosa_place_search 与技法载荷的 `place` 键共用一条管线。

检索算法是上游星阙的，经 horosa-core-js `place_search` 调 vendored 原件：AI 助手离线地名解析 `resolvePlaceOffline`
（城市库 cities + citiesFull + 繁简折叠表、cityMatch 四档评分、同城去重）、`dstAwareZoneAt`（tz-lookup → IANA →
中国大陆统一北京时间 → 当日偏移 + TZ_RULE_OVERRIDES）。十进制 → 31n13 罗盘串与一般十进制入参共用
`input_normalization._format_compact_coordinate`（上游 AstroHelper.convertLatToStr 的逐步移植，tests/test_coordinate_text.py 金标）。

**何时信一个匹配**是 skill 自己的规则（v0.50.0，horosa-core-js `src/tools/placeResolve.js`，AGENTS §10 上游镜像注记）：
上游的 high 会经拼音首字母（NYC → 银川、HK → 海口）、地区半截提示（St. Petersburg → 佛州）给出错城市，所以本模块
只按引擎回的 `verdict` 决定——条目本名 / 英文名 / 全拼 / 行政区词干 / skill 别名等于规范化查询（可带库能核对的国家 /
省市限定词）才 resolved；同名多地一律问用户，没有「挑大城市」规则。上游自己的 confidence 原样另报（upstream_confidence）。

自动补全的规矩（铁律 2：不猜）：
- 显式 lat / lon（或 gpsLat / gpsLon）与 zone 永远优先；两轴都给了就不按 place 定位；没给 zone 且有日期时，按这组坐标
  与日期补 zone（与按地名补同一个上游函数），place 只记为「未用于定位」。
- 歧义 / 只有近似匹配 / 一个候选但限定词库里核对不了 → `place.ambiguous`（带候选，一个候选时措辞是「请确认」）；
  只给了国家 / 省 / 州 → `place.too_broad`；把经纬度写进 place → `place.looks_like_coordinates`；找不到 → `place.not_found`
  （带近似拼写建议）。
- zone 缺省时按事件日期取上游当日偏移（与选点同一个正午锚点）；给了钟点且该钟点的实际偏移与正午不同（夏令时切换日，
  或两套时区库在这一天意见不一）就不替用户定，改问（`place.zone_ambiguous`）。没有日期则不补 zone（由校验层照常要 zone）。
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

from pydantic import ValidationError

from horosa_skill.agent_guidance import build_clarification_recovery
from horosa_skill.errors import ToolTransportError, ToolValidationError, bilingual, validation_errors
from horosa_skill.input_normalization import (
    _DATE_RE,
    _TIME_RE,
    _cn_unified_enabled,
    _coerce_coordinate_decimal,
    _format_compact_coordinate,
    _normalize_date_value,
    _normalize_iana_zone_value,
    _normalize_time_value,
)
from horosa_skill.service import _clock

PLACE_KEY = "place"
# 外层（dispatch / hecan / MCP 面）先解析过时留下的记录：run_tool 取走它挂到技法卡，不进引擎请求。
PLACE_RESOLUTION_KEY = "placeResolution"
# 一份载荷里可能带地名的位置：技法载荷本身、合盘的 inner / outer、dispatch 的 birth / context / subject。
_NESTED_SPOTS = ("birth", "context", "subject", "inner", "outer")
_LAT_KEYS = ("lat", "gpsLat")
_LON_KEYS = ("lon", "gpsLon")
_DEFAULT_LIMIT = 5
_MAX_LIMIT = 10
ENGINE_LABEL = "horosa-core-js place_search: upstream resolvePlaceOffline + dstAwareZoneAt (tz-lookup 6.1.25)"
# 已装 runtime 比本包旧时 JS 侧的两种报错：老 core-js 不认这个工具；新代码配了旧 node_modules（缺 tz-lookup）。
# v0.50.0 起还有接受规则（tools/placeResolve.js + tools/placeData/*.json）：缺了同样是「runtime 半新半旧」。
_STALE_ENGINE = re.compile(
    r"Unsupported horosa-core-js tool: place_search"
    r"|Cannot find (?:package|module) '[^']*(?:tz-lookup|vendor[\\/]place|tools[\\/]placeResolve|tools[\\/]placeData)"
)
# 引擎 verdict 的状态 → 是否「要用户从候选里选 / 确认」。
_ASK_STATUSES = ("ambiguous", "confirm", "near", "qualifier_mismatch")
# 提示语里举的写法：每一条都必须真能唯一解析（tests/test_place_acceptance.py 逐条跑引擎核对）。
PLACE_EXAMPLES_ZH = ("北京市朝阳区", "辽宁朝阳", "美国纽约", "台湾台北")
PLACE_EXAMPLES_EN = ("London, UK", "Taipei, Taiwan", "Los Angeles, CA")
_EXAMPLES_ZH = "、".join(f"「{item}」" for item in PLACE_EXAMPLES_ZH)
_EXAMPLES_EN = ", ".join(f"'{item}'" for item in PLACE_EXAMPLES_EN)


def _present(value: Any) -> bool:
    return value is not None and f"{value}".strip() != ""


def _engine_messages(exc: ToolTransportError) -> list[str]:
    """js_client 的错误把 JS 报错放在 details.error.message，多根回退时放在 details.attempts[*].details.error.message。"""
    found: list[str] = [str(exc)]
    details = exc.details if isinstance(exc.details, dict) else {}
    queue: list[Any] = [details]
    while queue:
        item = queue.pop()
        if isinstance(item, dict):
            error = item.get("error")
            if isinstance(error, dict) and error.get("message"):
                found.append(str(error["message"]))
            if isinstance(item.get("message"), str):
                found.append(item["message"])
            queue.extend(v for v in item.values() if isinstance(v, (dict, list)))
        elif isinstance(item, list):
            queue.extend(item)
    return found


def _candidate_label(candidate: dict[str, Any]) -> str:
    region = f"{candidate.get('region') or ''}".strip()
    en = f"{candidate.get('en') or ''}".strip()
    head = f"{candidate.get('name')}（{region}）" if region else f"{candidate.get('name')}"
    return f"{head} {en} {candidate.get('lat')}/{candidate.get('lon')}".replace("  ", " ").strip()


def _with_text(candidate: dict[str, Any]) -> dict[str, Any]:
    """引擎只回十进制；罗盘串在这里用与一般十进制入参同一个换算补上（一个实现，不是两个）。"""
    out = dict(candidate)
    for key, gps, axis in (("lat", "gpsLat", "lat"), ("lon", "gpsLon", "lon")):
        value = candidate.get(gps)
        out[key] = _format_compact_coordinate(float(value), axis=axis) if isinstance(value, (int, float)) and not isinstance(value, bool) else None
    return out


def _compact(candidate: dict[str, Any]) -> dict[str, Any]:
    """对外的候选形状：与技法载荷同名的键（lat/lon 罗盘串、gpsLat/gpsLon 十进制、zone 偏移）可直接抄进起盘参数。"""
    out = {key: candidate.get(key) for key in ("name", "region", "en", "lat", "lon", "gpsLat", "gpsLon", "zone", "iana", "dst")}
    if candidate.get("advisory"):
        out["advisory"] = candidate["advisory"]
    if candidate.get("geoZone") and candidate.get("geoZone") != candidate.get("iana"):
        out["geoZone"] = candidate["geoZone"]
    if candidate.get("zone_at_time"):
        out["zone_at_time"] = candidate["zone_at_time"]
    if candidate.get("where"):
        out["where"] = list(candidate["where"])  # 由近及远的上级（省 / 市 / 国家），引擎按城市库给
    return out


def _place_key(text: str) -> str:
    """Python 侧的规范化键（只给旧 runtime 的保守路径用）：NFKC、繁→简、去重音、去大小写与标点空格。"""
    from horosa_skill.textscript import fold_to_simplified

    folded = fold_to_simplified(unicodedata.normalize("NFKC", text)).casefold()
    folded = "".join(ch for ch in unicodedata.normalize("NFD", folded) if not unicodedata.combining(ch))
    return re.sub(r"[\W_]+", "", folded)


def _fallback_verdict(query: str, data: dict[str, Any]) -> dict[str, Any]:
    """引擎回包没有 verdict（runtime 比本包旧）：保守接受——上游 high 且命中条目的本名 / 英文名与查询逐字（规范化后）相同；
    其余一律问用户。拼音首字母、前缀、地区半截提示到达的 high 在这里都过不去。"""
    match = data.get("match") if isinstance(data.get("match"), dict) else None
    candidates = list(data.get("candidates") or [])
    key = _place_key(query)
    same = bool(match) and key in {_place_key(f"{match.get('name') or ''}"), _place_key(f"{match.get('en') or ''}")}
    if data.get("resolved") is True and data.get("confidence") == "high" and same:
        status = "resolved"
    elif candidates:
        status = "ambiguous" if len(candidates) > 1 else "near"
    else:
        status = "not_found"
    return {
        "policy": "conservative-fallback", "status": status, "match": match if status == "resolved" else None,
        "candidates": [match] if status == "resolved" else candidates, "total": 1 if status == "resolved" else len(candidates),
        "suggestions": [], "matched_by": "name" if status == "resolved" else None, "alias": None, "qualifiers": [], "caveats": [],
    }


def _verdict_caveats(verdict: dict[str, Any]) -> list[str]:
    """resolved 但要让用户知道的事（进 warnings）：旧称 / 昵称 / 近似别名、核对不了的州省限定词。"""
    notes: list[str] = []
    match = verdict.get("match") or {}
    for caveat in verdict.get("caveats") or []:
        code = caveat.get("code")
        if code in ("alias_historical", "alias_nickname", "alias_approximate"):
            kind_zh = {"alias_historical": "旧称", "alias_nickname": "别称", "alias_approximate": "近似对应"}[code]
            kind_en = {"alias_historical": "a historical name", "alias_nickname": "a nickname", "alias_approximate": "an approximate area name"}[code]
            notes.append(bilingual(
                f"「{caveat.get('alias')}」是{kind_zh}，按今天城市库的「{caveat.get('used')}」（{match.get('region') or ''}）取坐标；"
                "若用户指的是别处请改给具体地名或经纬度。",
                f"'{caveat.get('alias')}' is {kind_en}; coordinates are those of today's library entry '{caveat.get('used')}'. "
                "If the user meant somewhere else, give the specific place or coordinates.",
            ))
        elif code == "qualifier_unverified":
            quals = "、".join(caveat.get("qualifiers") or [])
            notes.append(bilingual(
                f"限定词「{quals}」（州 / 省一级）城市库里没有记录，只核对了国家；该名字在库中唯一，按 {match.get('name')} 取用。",
                f"Qualifier '{quals}' (state/province level) is not recorded in the city library; only the country was checked. "
                f"The name is unique in the library, so {match.get('en') or match.get('name')} was used.",
            ))
    return notes


_QUERY_BASIS = "_from_query"


def _query_date_reference(query: Any, context: dict[str, Any]) -> dict[str, Any] | None:
    """dispatch / 合参：context 只给了地点、没给日期，而问句里明说了日期 / 年份 → 用那一天给地点取时区偏移。"""
    if _present(context.get("date")) or not isinstance(query, str) or not query.strip():
        return None
    from horosa_skill.engine.dispatch_plan import query_target

    target = query_target(query, {})
    if not target or target.get("needs_context"):
        return None
    if target.get("date"):
        return {"date": target["date"], _QUERY_BASIS: True}
    if target.get("year"):
        return {"date": f"{int(target['year']):04d}-01-01", _QUERY_BASIS: True}
    return None


def place_resolution_note(record: dict[str, Any]) -> str:
    """给人看的一行（进 envelope.summary，不进 warnings）：地名解析到了哪里、时区从哪来。结构化的同一份在技法卡
    `place_resolution` 里。只有真要用户留意的事（旧称、核对不了的限定词、没补上时区…）才进 warnings（place_caveat_notes）。"""
    if record.get("status") == "explicit_coordinates":
        zone_part = ""
        if record.get("zone_source") == "coordinates_and_date":
            zone_part = f"；时区 {record.get('zone')} 按这组坐标 + {record.get('date')} 推得（{record.get('iana')}）"
        return bilingual(
            f"已给经纬度，place「{record.get('query')}」只作标签、未用于定位（显式坐标优先）{zone_part}。",
            f"Explicit coordinates were given; place '{record.get('query')}' is kept as a label only"
            + (f"; zone {record.get('zone')} derived from those coordinates and {record.get('date')}." if zone_part else "."),
        )
    region = f"（{record.get('region')}）" if record.get("region") else ""
    zone_text = {
        "place_and_date": f"时区 {record.get('zone')} 按地点 + {record.get('date')} 推得（{record.get('iana')}，夏令时：{'是' if record.get('dst') else '否'}）",
        "place_and_query_date": f"时区 {record.get('zone')} 按地点 + 问句里的日子 {record.get('date')} 推得（只给了年份时取当年 1 月 1 日；"
                                f"{record.get('iana')}，夏令时：{'是' if record.get('dst') else '否'}）",
        "explicit": "时区沿用显式给出的 zone",
        "not_filled_no_date": "没有日期，时区未补",
        "not_resolvable": "该坐标推不出时区，时区未补",
    }.get(str(record.get("zone_source")), "")
    return bilingual(
        f"地点按「{record.get('query')}」解析为 {record.get('name')}{region} {record.get('lat')} / {record.get('lon')}，{zone_text}"
        "（星阙城市库离线解析，与星阙选点同源）。",
        f"Place '{record.get('query')}' resolved to {record.get('en') or record.get('name')} {record.get('lat')}/{record.get('lon')}"
        f" (zone source: {record.get('zone_source')}; offline 星阙 city library, same as the 星阙 place picker).",
    )


def place_caveat_notes(record: dict[str, Any]) -> list[str]:
    """一条地名解析记录里真正要提醒的事（进 warnings）：别名注记、核对不了的限定词、没补上的时区。"""
    notes = list(record.get("caveat_notes") or [])
    if record.get("zone_source") in ("not_filled_no_date", "not_resolvable") and record.get("status") == "resolved":
        notes.append(bilingual(
            f"地点「{record.get('query')}」的时区没有补上（{'没有日期' if record.get('zone_source') == 'not_filled_no_date' else '该坐标推不出时区'}）。",
            f"No zone was filled for place '{record.get('query')}' ({record.get('zone_source')}).",
        ))
    return notes


def _matched_facts(verdict: dict[str, Any]) -> dict[str, Any]:
    """「是怎么认出来的」：命中方式、别名、限定词（及是否核对过）、要提醒的事。门面 matched 与技法卡 place_resolution 共用。"""
    return {
        "matched_by": verdict.get("matched_by"),
        "alias": verdict.get("alias"),
        "qualifiers": list(verdict.get("qualifiers") or []),
        "caveats": [c.get("code") for c in verdict.get("caveats") or [] if isinstance(c, dict)],
        "policy": verdict.get("policy"),
    }


def _refusal_texts(query: str, verdict: dict[str, Any]) -> dict[str, Any]:
    """不能自动接受时的说法（门面 next_step 与技法拒绝共用一套）。一个候选绝不说「不止一个」。"""
    status = verdict.get("status")
    candidates = verdict.get("candidates") or []
    count, total = len(candidates), int(verdict.get("total") or len(candidates))
    more_zh = f"（共 {total} 处，只列前 {count} 个；加省 / 国家可缩小）" if total > count else ""
    more_en = f" ({total} in all, first {count} shown; add a province/country to narrow it)" if total > count else ""
    pick_zh = "把候选念给用户选一个，不要替用户挑；选定后用那一条的 lat / lon / zone 重试，或改传更具体的地名"
    pick_en = "Read the candidates to the user and let them pick (never choose yourself); then retry with its lat/lon/zone or a more specific place"
    examples_zh = f"（如 {_EXAMPLES_ZH}）"
    examples_en = f" (e.g. {_EXAMPLES_EN})"
    if status == "coordinates":
        question = bilingual(
            f"「{query}」看起来是经纬度，不是地名。请把纬度、经度分别传给 lat 与 lon（再给 zone），不要写进 place；哪个数是纬度不替你猜。",
            f"'{query}' looks like coordinates, not a place name. Pass latitude and longitude separately as lat and lon (plus zone), "
            "not in place; which number is the latitude is not guessed.",
        )
        return {"code": "place.looks_like_coordinates", "reason": "place_is_coordinates", "question": question, "next_step": question,
                "message": bilingual(f"place「{query}」是坐标写法。", f"place '{query}' is written as coordinates.")}
    if status == "too_broad":
        regions = "、".join(verdict.get("regions") or []) or query
        question = bilingual(
            f"「{query}」读作地区（{regions}），不是一个地点：请给出生 / 事件所在的城市{examples_zh}，或直接给经纬度。"
            + ("下面是名字最接近的条目，可供核对：" if count else ""),
            f"'{query}' reads as a region ({regions}), not a place: give the city{examples_en}, or coordinates."
            + (" The closest library names are listed for reference." if count else ""),
        )
        return {"code": "place.too_broad", "reason": "place_too_broad", "question": question, "next_step": question,
                "message": bilingual(f"「{query}」只是地区，不够定位。", f"'{query}' is a region, not a place.")}
    if status in _ASK_STATUSES and count:
        if status == "ambiguous":
            zh = f"「{query}」对应 {total} 个不同地点{more_zh}，是哪一个？"
            en = f"'{query}' matches {total} different places{more_en}; which one?"
        elif status == "confirm":
            only = candidates[0]
            zh = (f"城市库在该国只有一个「{only.get('name')}」（{only.get('region') or ''}），但库里不记州 / 省，"
                  f"核对不了「{query}」里的限定词：是这一个吗？")
            en = (f"The library has one '{only.get('en') or only.get('name')}' in that country but records no states/provinces, "
                  f"so the qualifier in '{query}' cannot be checked: is it this one?")
        elif status == "qualifier_mismatch":
            quals = "、".join(verdict.get("qualifiers") or [])
            zh = f"城市库里有这个名字，但都不在「{quals}」；是下面{'这一个' if count == 1 else '这些之一'}吗？"
            en = f"The library has this name, but none in '{quals}'; is it {'this one' if count == 1 else 'one of these'}?"
        else:  # near
            zh = (f"城市库没有正好叫「{query}」的地方；名字最接近的{'是这一个（只是近似匹配）' if count == 1 else f'有 {count} 个（都只是近似匹配）'}，请用户确认。")
            en = (f"No library entry is named exactly '{query}'; the closest {'name is' if count == 1 else f'{count} names are'} "
                  "only approximate matches; ask the user to confirm.")
        return {
            "code": "place.ambiguous", "reason": f"place_{status}",
            "question": bilingual(zh, en),
            "next_step": bilingual(f"{zh}{pick_zh}{examples_zh}。", f"{en} {pick_en}{examples_en}."),
            "message": bilingual(f"地名「{query}」不能自动确定，需要用户确认。", f"Place '{query}' cannot be settled automatically; the user has to confirm."),
        }
    unsupported = verdict.get("unsupported") if isinstance(verdict.get("unsupported"), dict) else None
    suggestions = verdict.get("suggestions") or []
    if unsupported:
        tries = list(unsupported.get("try") or [])
        zh = f"{unsupported.get('zh')}可用：{'、'.join(tries)}。"
        en = f"{unsupported.get('en')} Try: {', '.join(tries)}."
        return {"code": "place.not_found", "reason": "place_not_found", "question": bilingual(zh, en), "options": tries,
                "next_step": bilingual(zh, en), "message": bilingual(f"没有找到地名「{query}」。", f"Place '{query}' was not found.")}
    if suggestions:
        names = "、".join(f"{s.get('name')}（{s.get('region')}）" if s.get("region") else f"{s.get('name')}" for s in suggestions)
        zh = f"城市库里没有「{query}」。是不是拼写有误，指的是：{names}？请用户确认，或给更具体的写法 / 经纬度。"
        en = f"'{query}' is not in the city library. Possible spellings: {names}. Ask the user, or get a more specific name / coordinates."
    else:
        zh = f"城市库里没有「{query}」：请用户给出生 / 事件所在城市的写法{examples_zh}，或直接给经纬度。"
        en = f"'{query}' is not in the city library: ask the user for the city{examples_en}, or coordinates."
    return {"code": "place.not_found", "reason": "place_not_found", "question": bilingual(zh, en), "next_step": bilingual(zh, en),
            "message": bilingual(f"没有找到地名「{query}」。", f"Place '{query}' was not found.")}


class PlaceAPI:
    # ── 门面 ────────────────────────────────────────────────────────────────────────────────
    def place_search(self, payload: dict[str, Any]) -> dict[str, Any]:
        """门面 horosa_place_search：地名 → skill 接受规则的裁决（唯一命中 / 候选 / 太宽 / 找不到 + 建议），候选带坐标串 +
        十进制 + 当日时区，以及下一步怎么做。"""
        from horosa_skill.schemas.tools.facades import PlaceSearchInput

        try:
            request = PlaceSearchInput.model_validate(payload)
        except ValidationError as exc:
            raise ToolValidationError(
                bilingual("地名检索的参数不对。", "Invalid payload for place search."),
                code="place.invalid_payload",
                details={"errors": validation_errors(exc)},
            ) from exc
        query = request.query.strip()
        if not query:
            raise ToolValidationError(
                bilingual("query 不能为空：要查的地名。", "query must not be empty: the place name to look up."),
                code="place.invalid_payload",
                details={"field": "query"},
            )
        date, date_source = self._place_date(request.date, field="date")
        time = self._place_time(request.time, strict=True)
        notes: list[str] = []
        if request.limit is not None and not 1 <= request.limit <= _MAX_LIMIT:
            used = _MAX_LIMIT if request.limit > _MAX_LIMIT else _DEFAULT_LIMIT
            notes.append(bilingual(
                f"limit={request.limit} 超出 1–{_MAX_LIMIT}，按 {used} 返回候选。",
                f"limit={request.limit} is outside 1-{_MAX_LIMIT}; returning up to {used} candidates.",
            ))
        result = self._lookup_place(
            query, date=date, time=time, limit=request.limit, cn_unified=request.cnUnifiedZone is not False,
        )
        return self._place_search_view(result, date_source=date_source, notes=notes)

    def _place_search_view(self, result: dict[str, Any], *, date_source: str, notes: list[str] | None = None) -> dict[str, Any]:
        verdict = result["verdict"]
        status = verdict.get("status")
        unique = status == "resolved" and isinstance(verdict.get("match"), dict)
        candidates = [_compact(item) for item in verdict.get("candidates") or []]
        warnings: list[str] = list(notes or [])
        if date_source == "today":
            warnings.append(bilingual(
                f"没给 date：偏移按今天（{result.get('date')}）算；起盘请按出生 / 事件日期再查一次，或直接传 place 让技法自己按日期补。",
                f"No date given: offsets are for today ({result.get('date')}); for a chart, query with the birth/event date or pass place to the technique.",
            ))
        warnings.extend(result.get("warnings") or [])
        if unique:
            match = _compact(verdict["match"])
            warnings.extend(_verdict_caveats(verdict))
            next_step = bilingual(
                f"唯一命中「{match['name']}」：起盘用 match 里的 lat / lon / gpsLat / gpsLon / zone，或在技法载荷里直接传 place。",
                "Unique match: copy match.lat/lon/gpsLat/gpsLon/zone into the chart call, or pass place to the technique.",
            )
        else:
            match = None
            texts = _refusal_texts(f"{result.get('query')}", verdict)
            next_step = texts["next_step"]
        return {
            "query": result.get("query"),
            "date": result.get("date"),
            "date_source": date_source,
            "resolved": unique,
            "status": status,
            # skill 的接受结论：只有 resolved 才是 high。上游自己的评级另放 upstream_confidence（它会把 NYC 判成银川 high）。
            "confidence": "high" if unique else None,
            "upstream_confidence": result.get("confidence"),
            "ambiguous": status in _ASK_STATUSES and bool(candidates),
            "match": match,
            "matched": _matched_facts(verdict) if unique else None,
            "candidates": candidates,
            "total": verdict.get("total", len(candidates)),
            "suggestions": [_compact(item) for item in verdict.get("suggestions") or []],
            "next_step": next_step,
            "warnings": warnings,
            "engine": ENGINE_LABEL,
            "policy": verdict.get("policy"),
        }

    # ── 共用：一次查询 ───────────────────────────────────────────────────────────────────────────
    def _place_date(self, value: Any, *, field: str) -> tuple[str, str]:
        if not _present(value):
            return _clock.now().strftime("%Y-%m-%d"), "today"
        text = _normalize_date_value(f"{value}".strip())
        if not _DATE_RE.match(text):
            raise ToolValidationError(
                bilingual(f"{field} 要写成 YYYY-MM-DD（公元前带负号）。", f"{field} must be YYYY-MM-DD (BC years with a leading minus)."),
                code="place.invalid_payload",
                details={"field": field, "value": f"{value}"},
            )
        return text, "given"

    @staticmethod
    def _place_time(value: Any, *, strict: bool = False) -> str | None:
        """钟点（只用来判夏令时切换日）。门面 strict：写坏了直接报（以前静默当没给）；技法载荷里的 time 由校验层照常报。"""
        if not _present(value):
            return None
        text = _normalize_time_value(f"{value}".strip())
        if _TIME_RE.match(text):
            return text
        if strict:
            raise ToolValidationError(
                bilingual("time 写法不对：要 HH:mm（或 HH:mm:ss）。", "time is malformed: use HH:mm (or HH:mm:ss)."),
                code="place.invalid_payload",
                details={"field": "time", "value": f"{value}"},
            )
        return None

    def _lookup_place(
        self, query: str, *, date: str | None, time: str | None, limit: int | None, cn_unified: bool,
    ) -> dict[str, Any]:
        from horosa_skill.textscript import fold_to_simplified

        capped = max(1, min(_MAX_LIMIT, int(limit))) if isinstance(limit, int) and limit > 0 else _DEFAULT_LIMIT
        body: dict[str, Any] = {"query": query, "date": date, "limit": capped, "cnUnified": cn_unified}
        folded = fold_to_simplified(query)
        if folded != query:
            body["folded"] = folded  # 繁体写法的简体孪生：上游的城市字表之外的字（如「臺中縣」）也能折回
        raw = self._run_place_engine(body)
        data = raw.get("data") if isinstance(raw, dict) else None
        if not isinstance(data, dict) or not isinstance(data.get("candidates"), list):
            raise ToolValidationError(
                bilingual("地名检索引擎返回了意外的形状。", "The place-search engine returned an unexpected shape."),
                code="place.engine_failed",
                details={"received": type(data).__name__},
            )
        data = {**data, "candidates": [_with_text(item) for item in data["candidates"] if isinstance(item, dict)],
                "match": _with_text(data["match"]) if isinstance(data.get("match"), dict) else None}
        warnings: list[str] = []
        verdict = data.get("verdict")
        if isinstance(verdict, dict) and verdict.get("status"):
            verdict = {
                **verdict,
                "match": _with_text(verdict["match"]) if isinstance(verdict.get("match"), dict) else None,
                "candidates": [_with_text(item) for item in verdict.get("candidates") or [] if isinstance(item, dict)],
                "suggestions": [_with_text(item) for item in verdict.get("suggestions") or [] if isinstance(item, dict)],
            }
        else:
            verdict = _fallback_verdict(query, data)
            warnings.append(bilingual(
                "已装的离线 runtime 早于地名接受规则（v0.50.0）：只接受与城市库条目名逐字相同的地名，其余都会请用户确认；升级 runtime 可恢复全部写法。",
                "The installed runtime predates the place acceptance rule (v0.50.0): only names that equal a library entry are accepted; "
                "everything else asks the user. Upgrade the runtime for the full rule.",
            ))
        if time and date:
            for item in [data.get("match"), *data["candidates"], verdict.get("match"), *verdict["candidates"]]:
                self._mark_zone_at_time(item, date=date, time=time, cn_unified=cn_unified)
            match = verdict.get("match")
            if isinstance(match, dict) and match.get("zone_at_time"):
                warnings.append(self._transition_note(match, date=date, time=time))
        return {**data, "verdict": verdict, "warnings": warnings}

    def _run_place_engine(self, body: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.js_client.run("place_search", body)
        except ToolTransportError as exc:
            messages = _engine_messages(exc)
            if any(_STALE_ENGINE.search(message) for message in messages):
                from horosa_skill.runtime.hints import install_command

                upgrade = install_command()["upgrade"]
                raise ToolValidationError(
                    bilingual(
                        "已装的离线 runtime 比本版 horosa-skill 旧，缺地名检索（horosa-core-js place_search / npm tz-lookup）。"
                        f"升级 runtime：`{upgrade}`；或者先直接给 lat / lon / zone。",
                        "The installed offline runtime predates this horosa-skill and lacks place search "
                        f"(horosa-core-js place_search / npm tz-lookup). Upgrade it: `{upgrade}`; or pass lat/lon/zone explicitly.",
                    ),
                    code="place.runtime_outdated",
                    details={"engine_error": next((m for m in messages if _STALE_ENGINE.search(m)), "")[:300],
                             "commands": [upgrade]},
                ) from exc
            # 其余引擎错误（没有 node、超时…）原码转成结构化拒绝：门面护栏只认 ToolValidationError。
            raise ToolValidationError(str(exc), code=exc.code, details=dict(exc.details or {})) from exc

    def place_verdicts(self, queries: list[str], *, date: str | None = None) -> list[dict[str, Any]]:
        """批量裁决（不算时区、不填坐标）：语料测试与提示语例子的自检用，一次 node 进程。"""
        from horosa_skill.textscript import fold_to_simplified

        items = [{"query": q, "folded": fold_to_simplified(q)} for q in queries]
        raw = self._run_place_engine({"queries": items, "date": date})
        data = raw.get("data") if isinstance(raw, dict) else None
        batch = data.get("batch") if isinstance(data, dict) else None
        if not isinstance(batch, list):
            raise ToolValidationError(
                bilingual("地名检索引擎不支持批量裁决（runtime 过旧）。", "The place engine has no batch verdicts (runtime too old)."),
                code="place.engine_failed",
                details={"received": type(batch).__name__},
            )
        return batch

    def _zone_for_point(self, gps_lat: float, gps_lon: float, *, date: str, cn_unified: bool) -> dict[str, Any] | None:
        """place 同时给了 lat / lon、却没给 zone：按这组坐标 + 日期补 zone（与按地名补同一个上游 dstAwareZoneAt）。旧 runtime 返回 None。"""
        try:
            raw = self._run_place_engine({"point": {"gpsLat": gps_lat, "gpsLon": gps_lon}, "date": date, "cnUnified": cn_unified})
        except ToolValidationError as exc:
            if exc.code == "place.runtime_outdated":
                raise
            return None
        data = raw.get("data") if isinstance(raw, dict) else None
        point = data.get("point") if isinstance(data, dict) else None
        return point if isinstance(point, dict) and point.get("zone") else None

    @staticmethod
    def _mark_zone_at_time(item: Any, *, date: str, time: str, cn_unified: bool) -> None:
        """钟点的实际偏移（本仓 IANA 换算 `_normalize_iana_zone_value`，按钟面时刻）≠ 上游正午偏移时记 zone_at_time。"""
        if not isinstance(item, dict) or not item.get("iana") or not item.get("zone"):
            return
        probe: dict[str, Any] = {"date": date, "time": time, "cnUnifiedZone": cn_unified}
        at_time = _normalize_iana_zone_value(str(item["iana"]), payload=probe, key="zone")
        if at_time and at_time != item["zone"]:
            item["zone_at_time"] = at_time

    @staticmethod
    def _transition_note(item: dict[str, Any], *, date: str, time: str) -> str:
        return bilingual(
            f"{item.get('name')} 在 {date} 这一天偏移不唯一：星阙选点按当日正午取 {item.get('zone')}，钟点 {time} 实际是 "
            f"{item.get('zone_at_time')}（{item.get('iana')}，夏令时切换日或时区库在这天不一致）。请向用户确认用哪个时区。",
            f"{item.get('name')} has two offsets on {date}: the picker's noon anchor gives {item.get('zone')}, "
            f"{time} local is {item.get('zone_at_time')} ({item.get('iana')}). Ask the user which zone to use.",
        )

    # ── 技法载荷的 `place` 键 ────────────────────────────────────────────────────────────────────
    def resolve_place_fields(self, payload: Any, *, tool_name: str | None = None, _reference: dict[str, Any] | None = None) -> Any:
        """把载荷里每一处 `place` 换成 lat / lon / gpsLat / gpsLon（+ 缺省的 zone / pos），并在原处留 `placeResolution`。
        幂等：解析过的位置不再有 `place`，第二遍原样返回。非 dict 原样返回（由下游照常报错）。"""
        if not isinstance(payload, dict):
            return payload
        out = dict(payload)
        for key in _NESTED_SPOTS:
            child = out.get(key)
            if isinstance(child, dict):
                # dispatch 的 context 没有自己的日期时：问句里明说了日期 / 年份（「2027年立春」）就按那一天（只有年份 = 当年 1 月 1 日）
                # 取偏移——那是技法要算的日子；否则借 birth 的。都没有才留空（时区未补）。
                reference = None
                if key == "context":
                    reference = _query_date_reference(out.get("query"), child)
                    if reference is None and isinstance(out.get("birth"), dict):
                        reference = out["birth"]
                out[key] = self.resolve_place_fields(child, tool_name=tool_name, _reference=reference)
        if PLACE_KEY in out:
            out = self._resolve_one_spot(out, tool_name=tool_name, reference=_reference)
        return out

    def _resolve_one_spot(self, spot: dict[str, Any], *, tool_name: str | None, reference: dict[str, Any] | None) -> dict[str, Any]:
        out = dict(spot)
        query = f"{out.pop(PLACE_KEY, '') or ''}".strip()
        if not query:
            return out
        has_lat = any(_present(out.get(key)) for key in _LAT_KEYS)
        has_lon = any(_present(out.get(key)) for key in _LON_KEYS)
        if has_lat and has_lon:
            return self._explicit_coordinates(out, query, reference=reference, tool_name=tool_name or "this technique")
        if has_lat != has_lon:
            raise ToolValidationError(
                bilingual(
                    f"给了 place「{query}」，经纬度却只给了一半：要么 lat 与 lon 都给，要么都不给（由 place 补）。",
                    f"place '{query}' came with only one of lat/lon: give both, or neither (place fills them).",
                ),
                code="place.coordinate_missing",
                details={"query": query, "fields": ["lat", "lon"]},
            )
        dated = out if _present(out.get("date")) or reference is None else reference
        raw_date, raw_time = dated.get("date"), dated.get("time")
        date = None
        if _present(raw_date):
            text = _normalize_date_value(f"{raw_date}".strip())
            date = text if _DATE_RE.match(text) else None
        time = self._place_time(raw_time)
        cn_unified = _cn_unified_enabled(out)
        result = self._lookup_place(query, date=date or _clock.now().strftime("%Y-%m-%d"), time=time if date else None,
                                    limit=_DEFAULT_LIMIT, cn_unified=cn_unified)
        label = tool_name or "this technique"
        verdict = result["verdict"]
        if not (verdict.get("status") == "resolved" and isinstance(verdict.get("match"), dict)):
            raise self._place_refusal(query, verdict, tool_name=label)
        match = verdict["match"]
        for key in ("lat", "lon", "gpsLat", "gpsLon"):
            out[key] = match[key]
        if not _present(out.get("pos")):
            out["pos"] = match["name"]  # 上游 createChartRecord / geoNameRawPatch 同样把地名写进 pos
        zone_source = "explicit"
        if not _present(out.get("zone")):
            if date is None:
                zone_source = "not_filled_no_date"
            elif not match.get("zone"):
                zone_source = "not_resolvable"
            elif match.get("zone_at_time"):
                raise self._zone_refusal(query, match, date=date, time=time or "", tool_name=label)
            else:
                out["zone"] = match["zone"]
                zone_source = "place_and_query_date" if dated is reference and (reference or {}).get(_QUERY_BASIS) else "place_and_date"
                if match.get("advisory") == "cn-unified":
                    out.setdefault("geoZone", match.get("geoZone"))
                    out["zoneAdvisory"] = "cn-unified"
        out[PLACE_RESOLUTION_KEY] = {
            "query": query, "status": "resolved", "confidence": "high",
            **_matched_facts(verdict),
            "name": match.get("name"), "region": match.get("region"), "en": match.get("en"), "where": match.get("where"),
            "lat": match.get("lat"), "lon": match.get("lon"), "gpsLat": match.get("gpsLat"), "gpsLon": match.get("gpsLon"),
            "iana": match.get("iana"), "zone": out.get("zone") if zone_source in ("place_and_date", "place_and_query_date") else match.get("zone"),
            "zone_source": zone_source, "dst": match.get("dst"), "advisory": match.get("advisory"),
            "date": date, "engine": ENGINE_LABEL, "caveat_notes": _verdict_caveats(verdict),
        }
        return out

    def _explicit_coordinates(
        self, out: dict[str, Any], query: str, *, reference: dict[str, Any] | None, tool_name: str,
    ) -> dict[str, Any]:
        """lat / lon 都给了：坐标照用，place 只作标签。没给 zone 而有日期时按这组坐标补 zone（不再把 place 静默丢掉、
        再让校验层回头要 zone）；补不出就照旧交给校验层要 zone。"""
        record: dict[str, Any] = {"query": query, "status": "explicit_coordinates", "engine": ENGINE_LABEL}
        if not _present(out.get("zone")):
            dated = out if _present(out.get("date")) or reference is None else reference
            text = _normalize_date_value(f"{dated.get('date')}".strip()) if _present(dated.get("date")) else ""
            lat = next((v for v in (_coerce_coordinate_decimal(out.get(k)) for k in ("gpsLat", "lat")) if v is not None), None)
            lon = next((v for v in (_coerce_coordinate_decimal(out.get(k)) for k in ("gpsLon", "lon")) if v is not None), None)
            if _DATE_RE.match(text) and lat is not None and lon is not None and abs(lat) <= 90 and abs(lon) <= 180:
                point = self._zone_for_point(lat, lon, date=text, cn_unified=_cn_unified_enabled(out))
                if point:
                    time = self._place_time(dated.get("time"))
                    probe = {"name": query, "iana": point.get("iana"), "zone": point.get("zone")}
                    if time:
                        self._mark_zone_at_time(probe, date=text, time=time, cn_unified=_cn_unified_enabled(out))
                    if probe.get("zone_at_time"):
                        raise self._zone_refusal(query, probe, date=text, time=time or "", tool_name=tool_name)
                    out["zone"] = point["zone"]
                    if point.get("advisory") == "cn-unified":
                        out.setdefault("geoZone", point.get("geoZone"))
                        out["zoneAdvisory"] = "cn-unified"
                    record.update({"zone": point["zone"], "iana": point.get("iana"), "dst": point.get("dst"),
                                   "zone_source": "coordinates_and_date", "date": text})
        out[PLACE_RESOLUTION_KEY] = record
        return out

    @staticmethod
    def _place_refusal(query: str, verdict: dict[str, Any], *, tool_name: str) -> ToolValidationError:
        texts = _refusal_texts(query, verdict)
        candidates = [_compact(item) for item in verdict.get("candidates") or []]
        suggestions = [_compact(item) for item in verdict.get("suggestions") or []]
        options = [_candidate_label(c) for c in (candidates or suggestions)] or list(texts.get("options") or [])
        ask = [{"field": "place", "question": texts["question"], **({"options": options} if options else {})}]
        do_not_assume = [
            "Never pick one of several places yourself; never invent coordinates or a UTC offset.",
            "After the user answers, retry with the chosen candidate's lat/lon/gpsLat/gpsLon (and zone), or a more specific place.",
        ]
        recovery = build_clarification_recovery(tool_name=tool_name, ask_if_missing=ask, do_not_assume=do_not_assume, reason=texts["reason"])
        return ToolValidationError(texts["message"], code=texts["code"], details={
            "query": query, "status": verdict.get("status"), "candidates": candidates, "total": verdict.get("total", len(candidates)),
            "suggestions": suggestions, "ask_if_missing": ask, "do_not_assume": do_not_assume, "agent_recovery": recovery,
            **({"regions": verdict["regions"]} if verdict.get("regions") else {}),
        })

    def _zone_refusal(self, query: str, match: dict[str, Any], *, date: str, time: str, tool_name: str) -> ToolValidationError:
        note = self._transition_note(match, date=date, time=time)
        ask = [{"field": "zone", "question": note, "options": [str(match.get("zone")), str(match.get("zone_at_time"))]}]
        do_not_assume = ["Do not pick a UTC offset on a DST-switch day yourself; ask the user."]
        recovery = build_clarification_recovery(tool_name=tool_name, ask_if_missing=ask, do_not_assume=do_not_assume, reason="zone_ambiguous")
        return ToolValidationError(
            bilingual(f"「{query}」在 {date} {time} 的时区不唯一，需要用户确认。", f"The UTC offset for '{query}' at {date} {time} is not unique; ask the user."),
            code="place.zone_ambiguous",
            details={"query": query, "match": _compact(match), "ask_if_missing": ask, "do_not_assume": do_not_assume, "agent_recovery": recovery},
        )

    @staticmethod
    def pop_place_records(payload: Any) -> tuple[Any, list[dict[str, Any]]]:
        """取走载荷里各处的 `placeResolution`（技法卡与 warnings 用），载荷本身不带它进引擎请求 / 存档 subject。"""
        if not isinstance(payload, dict):
            return payload, []
        out = dict(payload)
        records: list[dict[str, Any]] = []
        record = out.pop(PLACE_RESOLUTION_KEY, None)
        if isinstance(record, dict):
            records.append(record)
        for key in _NESTED_SPOTS:
            if isinstance(out.get(key), dict):
                out[key], nested = PlaceAPI.pop_place_records(out[key])
                records.extend({**item, "spot": key} if "spot" not in item else item for item in nested)
        return out, records
