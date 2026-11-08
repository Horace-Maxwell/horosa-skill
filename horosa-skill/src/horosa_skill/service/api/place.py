"""地名 → 坐标 + 时区（PlaceAPI，v0.48.0）：门面 horosa_place_search 与技法载荷的 `place` 键共用一条管线。

算法全是上游星阙的，经 horosa-core-js `place_search` 调 vendored 原件：AI 助手离线地名解析 `resolvePlaceOffline`
（城市库 cities + citiesFull + 繁简折叠表、cityMatch 四档评分、同城去重、high / medium 置信）、`dstAwareZoneAt`
（tz-lookup → IANA → 中国大陆统一北京时间 → 当日偏移 + TZ_RULE_OVERRIDES）。十进制 → 31n13 罗盘串与一般十进制入参共用
`input_normalization._format_compact_coordinate`（上游 AstroHelper.convertLatToStr 的逐步移植，tests/test_coordinate_text.py 金标）。
本模块只管四件事：入参归一、`place` 自动补全的判定（只认上游 high）、拒绝时的澄清载荷、旧 runtime 的降级。

自动补全的规矩（铁律 2：不猜）：
- 显式 lat / lon（或 gpsLat / gpsLon）与 zone 永远优先；两轴都给了就不解析 `place`，只记一笔「未使用」。
- 唯一命中 = 上游 `confidence == "high"`（名 / 全拼 / 首字母 / 英文精确命中且只有一处，或多处精确命中里按地区唯一）；
  medium（前缀唯一最优，上游自己也要求「向用户复述确认」）与多个候选一律走澄清（`place.ambiguous`），找不到是 `place.not_found`。
- zone 缺省时按事件日期取上游当日偏移（与选点同一个正午锚点）；给了钟点且该钟点的实际偏移与正午不同（夏令时切换日，
  或两套时区库在这一天意见不一）就不替用户定，改问（`place.zone_ambiguous`）。没有日期则不补 zone（由校验层照常要 zone）。
"""
from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError

from horosa_skill.agent_guidance import build_clarification_recovery
from horosa_skill.errors import ToolTransportError, ToolValidationError, bilingual, validation_errors
from horosa_skill.input_normalization import (
    _DATE_RE,
    _TIME_RE,
    _cn_unified_enabled,
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
_STALE_ENGINE = re.compile(r"Unsupported horosa-core-js tool: place_search|Cannot find (?:package|module) '[^']*(?:tz-lookup|vendor[\\/]place)")


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
    return out


def place_resolution_note(record: dict[str, Any]) -> str:
    """warnings 里给人看的一行：地名解析到了哪里、时区从哪来。"""
    if record.get("status") == "explicit_coordinates":
        return bilingual(
            f"已给经纬度，place「{record.get('query')}」未用于定位（显式坐标优先）。",
            f"Explicit coordinates were given; place '{record.get('query')}' was not used.",
        )
    region = f"（{record.get('region')}）" if record.get("region") else ""
    zone_text = {
        "place_and_date": f"时区 {record.get('zone')} 按地点 + {record.get('date')} 推得（{record.get('iana')}，夏令时：{'是' if record.get('dst') else '否'}）",
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


class PlaceAPI:
    # ── 门面 ────────────────────────────────────────────────────────────────────────────────
    def place_search(self, payload: dict[str, Any]) -> dict[str, Any]:
        """门面 horosa_place_search：地名 → 按上游顺序排好的候选（坐标串 + 十进制 + 当日时区）、是否有歧义、下一步怎么做。"""
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
        time = self._place_time(request.time)
        result = self._lookup_place(
            query, date=date, time=time, limit=request.limit, cn_unified=request.cnUnifiedZone is not False,
        )
        return self._place_search_view(result, date_source=date_source)

    def _place_search_view(self, result: dict[str, Any], *, date_source: str) -> dict[str, Any]:
        unique = result.get("resolved") is True and result.get("confidence") == "high"
        candidates = [_compact(item) for item in result.get("candidates") or []]
        ambiguous = not unique and bool(candidates)
        warnings: list[str] = []
        if date_source == "today":
            warnings.append(bilingual(
                f"没给 date：偏移按今天（{result.get('date')}）算；起盘请按出生 / 事件日期再查一次，或直接传 place 让技法自己按日期补。",
                f"No date given: offsets are for today ({result.get('date')}); for a chart, query with the birth/event date or pass place to the technique.",
            ))
        warnings.extend(result.get("warnings") or [])
        if unique:
            match = _compact(result["match"])
            next_step = bilingual(
                f"唯一命中「{match['name']}」：起盘用 match 里的 lat / lon / gpsLat / gpsLon / zone，或在技法载荷里直接传 place。",
                "Unique match: copy match.lat/lon/gpsLat/gpsLon/zone into the chart call, or pass place to the technique.",
            )
        elif candidates:
            match = None
            medium = result.get("confidence") == "medium"
            reason_zh = "最接近的只是前缀匹配，上游也要求向用户复述确认；" if medium else "有多个同名或近名的地点；"
            reason_en = "The best hit is only a prefix match (upstream asks to confirm it)." if medium else "Several places share this name."
            next_step = bilingual(
                f"{reason_zh}把 candidates 念给用户选一个，不要替用户挑；选定后用那一条的 lat / lon / zone，"
                "或改传更具体的 place（带省 / 国家，如「辽宁朝阳市」）。",
                f"{reason_en} Read the candidates to the user and let them pick; never choose yourself. "
                "Then use that candidate's lat/lon/zone, or pass a more specific place (with province/country).",
            )
        else:
            match = None
            next_step = bilingual(
                "城市库里没有这个地名：请用户给更具体的写法（带省 / 国家，或英文名）或直接给经纬度。",
                "Not in the city library: ask the user for a more specific name (with province/country, or English) or coordinates.",
            )
        return {
            "query": result.get("query"),
            "date": result.get("date"),
            "date_source": date_source,
            "resolved": unique,
            "confidence": result.get("confidence"),
            "ambiguous": ambiguous,
            "match": match,
            "candidates": candidates,
            "next_step": next_step,
            "warnings": warnings,
            "engine": ENGINE_LABEL,
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
    def _place_time(value: Any) -> str | None:
        if not _present(value):
            return None
        text = _normalize_time_value(f"{value}".strip())
        return text if _TIME_RE.match(text) else None

    def _lookup_place(
        self, query: str, *, date: str | None, time: str | None, limit: int | None, cn_unified: bool,
    ) -> dict[str, Any]:
        capped = max(1, min(_MAX_LIMIT, int(limit))) if isinstance(limit, int) and limit > 0 else _DEFAULT_LIMIT
        body = {"query": query, "date": date, "limit": capped, "cnUnified": cn_unified}
        try:
            raw = self.js_client.run("place_search", body)
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
        if time and date:
            for item in [data.get("match"), *data["candidates"]]:
                self._mark_zone_at_time(item, date=date, time=time, cn_unified=cn_unified)
            match = data.get("match")
            if isinstance(match, dict) and match.get("zone_at_time"):
                warnings.append(self._transition_note(match, date=date, time=time))
        return {**data, "warnings": warnings}

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
                # dispatch 的 context 没有自己的日期时借 birth 的（「当下」的地点按事件日期取偏移）。
                reference = out.get("birth") if key == "context" and isinstance(out.get("birth"), dict) else None
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
            out[PLACE_RESOLUTION_KEY] = {"query": query, "status": "explicit_coordinates", "engine": ENGINE_LABEL}
            return out
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
        if not (result.get("resolved") is True and result.get("confidence") == "high" and isinstance(result.get("match"), dict)):
            raise self._place_refusal(query, result, tool_name=label)
        match = result["match"]
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
                zone_source = "place_and_date"
                if match.get("advisory") == "cn-unified":
                    out.setdefault("geoZone", match.get("geoZone"))
                    out["zoneAdvisory"] = "cn-unified"
        out[PLACE_RESOLUTION_KEY] = {
            "query": query, "status": "resolved", "confidence": result.get("confidence"),
            "name": match.get("name"), "region": match.get("region"), "en": match.get("en"),
            "lat": match.get("lat"), "lon": match.get("lon"), "gpsLat": match.get("gpsLat"), "gpsLon": match.get("gpsLon"),
            "iana": match.get("iana"), "zone": out.get("zone") if zone_source == "place_and_date" else match.get("zone"),
            "zone_source": zone_source, "dst": match.get("dst"), "advisory": match.get("advisory"),
            "date": date, "engine": ENGINE_LABEL,
        }
        return out

    @staticmethod
    def _place_refusal(query: str, result: dict[str, Any], *, tool_name: str) -> ToolValidationError:
        candidates = [_compact(item) for item in result.get("candidates") or []]
        if candidates:
            question = bilingual(
                f"「{query}」对应不止一个地点（或只是近似匹配），是哪一个？",
                f"'{query}' matches more than one place (or only approximately) — which one?",
            )
            ask = [{"field": "place", "question": question, "options": [_candidate_label(c) for c in candidates]}]
            code, reason = "place.ambiguous", "place_ambiguous"
            message = bilingual(
                f"地名「{query}」不能唯一确定，需要用户从候选里选。", f"Place '{query}' is not unique; the user has to pick a candidate.",
            )
        else:
            ask = [{"field": "place", "question": bilingual(
                f"城市库里没有「{query}」：请给更具体的地名（带省 / 国家，或英文名）或经纬度。",
                f"'{query}' is not in the city library: give a more specific name (with province/country, or English) or coordinates.",
            )}]
            code, reason = "place.not_found", "place_not_found"
            message = bilingual(f"没有找到地名「{query}」。", f"Place '{query}' was not found.")
        do_not_assume = [
            "Never pick one of several places yourself; never invent coordinates or a UTC offset.",
            "After the user answers, retry with the chosen candidate's lat/lon/gpsLat/gpsLon (and zone), or a more specific place.",
        ]
        recovery = build_clarification_recovery(tool_name=tool_name, ask_if_missing=ask, do_not_assume=do_not_assume, reason=reason)
        return ToolValidationError(message, code=code, details={
            "query": query, "confidence": result.get("confidence"), "candidates": candidates,
            "ask_if_missing": ask, "do_not_assume": do_not_assume, "agent_recovery": recovery,
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
