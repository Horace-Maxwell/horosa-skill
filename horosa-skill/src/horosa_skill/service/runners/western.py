"""西洋 runner（WesternRunners）：印度校正、行星周期、占星地图、汉堡盘、泛音盘、巴比伦、龙头盘、迁移盘。"""
from __future__ import annotations

from typing import Any

from horosa_skill.astro_rulers import (
    DRACONIC_HOUSE_LABELS,
    DRACONIC_HOUSE_MODE_DEFAULT,
    DRACONIC_HOUSE_MODES,
)
from horosa_skill.astro_rulers import js_template_str as _js_template_str
from horosa_skill.civil_calendar import (
    _ad_of_date,
    _parse_date_parts,
    _round_hour_to_minute,
)
from horosa_skill.engine.astroextra_snapshots import fmt_num
from horosa_skill.errors import ToolTransportError, ToolValidationError, bilingual
from horosa_skill.schemas.tools.astro import INDIA_RECTIFY_DEAD_KEYS
from horosa_skill.service._common import (
    _is_astro_chart_payload,
    _render_snapshot_text,
    _to_slash_date,
)
from horosa_skill.service._context import _degrade
from horosa_skill.service.text.astro_core import (
    _astro_msg,
    _round3,
    _sign_degree,
)
from horosa_skill.service.text.chart_family import (
    _build_astro_snapshot_text,
    _india_comma_lists,
)
from horosa_skill.service.text.predictive import _build_india_rectify_snapshot_text
from horosa_skill.service.text.western import (
    _angle_text,
    _build_germany_snapshot_text,
    _chart_angles,
    _derived_cn,
    _derived_conjunction_lines,
    _derived_position_lines,
    _dial_points,
    _reloc_display_degree,
    _with_natal_planet_sign,
)
from horosa_skill.western_vocab import CHART_DETAIL_ONLY_KEYS

# [盘面细节] 的五项口径 + 「当前表」只进 /astroextra/chartdetails（enrich._attach_chart_details 另拼请求体），不进起盘请求。
_CHART_DETAIL_ONLY_KEYS = CHART_DETAIL_ONLY_KEYS   # 盘面细节专用键，不进 /chart 与派生盘请求（western_vocab 单源）


class WesternRunners:
    # ── 印度出生时间校正（批 I-2，/india/rectify）───────────────────────────────

    def _run_india_rectify_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 问事 / 年盘 / 三旗 11 键对 /india/rectify 是死键（schemas/tools/astro.INDIA_RECTIFY_DEAD_KEYS 注释里逐层引了上游行号）：
        # 照收、不下发；给了就在 warnings 说一声（它们曾在 tools/list 上广告过）。
        dead_given = [key for key in INDIA_RECTIFY_DEAD_KEYS if payload.get(key) not in (None, "")]
        remote = {k: v for k, v in payload.items() if k not in INDIA_RECTIFY_DEAD_KEYS}
        for key in ("rectifyWindowMinutes", "rectifyStepSeconds", "rectifyTopK", "rectifyRpSource", "rectifyEvents"):
            if remote.get(key) is None:
                remote.pop(key, None)
        remote = _india_comma_lists(remote)  # rectifyCustomRp：后端 str(x).split(',')，数组得先并成逗号串
        response = self._call_remote("/india/rectify", remote)
        if not isinstance(response, dict) or response.get("available") is not True:
            raise ToolTransportError(
                "印度校时端点未返回可用结果。",
                code="tool.india_rectify_failed",
                details={"endpoint": "/india/rectify", "response": response if isinstance(response, dict) else {"shape": type(response).__name__}},
            )
        snapshot_text = _build_india_rectify_snapshot_text(payload, response)
        result: dict[str, Any] = {
            "rectify": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="india_rectify", snapshot_text=snapshot_text),
        }
        if dead_given:
            names = "、".join(dead_given)
            result["_warnings"] = [bilingual(
                f"出生时间校正不读这些键，已忽略、未转发后端：{names}（上游 /india/rectify 只认校时参数与 indiaHsys / indiaAyanamsa）；"
                "问事、年盘、三旗请用 horosa_astro_india_chart。",
                f"Birth-time rectification ignores {', '.join(dead_given)} (upstream /india/rectify reads only the rectify* knobs "
                "and indiaHsys / indiaAyanamsa); they were not sent. Use horosa_astro_india_chart for praśna / annual / tripatāki.",
            )]
        return result

    # ── 行星周期（批 I-3，/astroextra/planetcycles）─────────────────────────────

    def _run_planet_cycles_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        remote: dict[str, Any] = {}
        for key in ("startYear", "endYear", "p1", "p2", "aspect", "center"):
            if payload.get(key) is not None:
                remote[key] = payload.get(key)
        response = self._call_remote("/astroextra/planetcycles", remote)
        events = response.get("events") if isinstance(response, dict) else None
        if not isinstance(events, list):
            raise ToolTransportError(
                "行星周期端点返回了意外形状。",
                code="tool.planet_cycles_failed",
                details={"endpoint": "/astroextra/planetcycles"},
            )
        aspect = response.get("aspect")
        aspect_cn = {0.0: "合", 180.0: "冲"}.get(float(aspect) if aspect is not None else 0.0, f"{_round3(aspect)}°")
        center_cn = {"geo": "地心", "helio": "日心", "topo": "站心"}.get(str(response.get("center") or "geo"), str(response.get("center")))
        config_lines = [
            f"星对：{_astro_msg(response.get('p1'))}-{_astro_msg(response.get('p2'))}　相位：{aspect_cn}　"
            f"区间：{response.get('startYear')}–{response.get('endYear')}　坐标系：{center_cn}",
        ]
        event_lines: list[str] = [f"共 {len(events)} 次"]
        for ev in events:
            if not isinstance(ev, dict):
                continue
            try:
                year, month, day, hh, mm = _round_hour_to_minute(
                    int(ev.get("year")), int(ev.get("month") or 0), int(ev.get("day") or 0), float(ev.get("hour") or 0.0)
                )
                when = f"{year}-{month:02d}-{day:02d} {hh:02d}:{mm:02d}"
            except (TypeError, ValueError):
                when = f"{ev.get('year')}"
            event_lines.append(f"{when}（UT）　{_sign_degree(ev.get('lon'))}")
        snapshot_text = _render_snapshot_text([
            ("周期配置", "\n".join(config_lines)),
            ("会合事件", "\n".join(event_lines)),
        ])
        return {
            "cycles": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="planet_cycles", snapshot_text=snapshot_text),
        }

    # ── 占星地图（AstroCartoGraphy）请求口径：上游 AstroAcg.genParams（AstroAcg.js:347-371）逐键 ──────────────
    # 引擎口径键（ACGraph.__init__ 按名读，ACGraph.py:239-340）：缺省即后端默认、零回归；给了才下发。
    _ACG_ENGINE_KEYS = (
        "mode", "lsMode", "geodetic", "geodeticVar", "geodeticZero", "cuspLines", "coord", "posType", "horizon",
        "nodeType", "lilithType", "draconic", "harmonic", "vibration", "midpointMode", "lotsCustom", "asteroids",
        "ayanamsa", "stars",
    )
    # 上游这几键以字符串 '1'/'0' 下发（genParams 里 `x ? '1' : '0'`）；后端按字符串集合判真。
    _ACG_FLAG_KEYS = ("cuspLines", "vibration", "asteroids", "stars")
    # CCG 时间地图（只在给了 ccgDate 才下发，:356-360）与关系盘（relMode + relDate 都有才下发，:361-368）。
    _ACG_CCG_KEYS = ("ccgDate", "ccgTime", "ccgMix")
    _ACG_REL_KEYS = ("relMode", "relDate", "relTime", "relZone", "relLat", "relLon")
    # 快照图层开关（纯渲染；进 uiState 决定 [占星地图] 的 ◆ 子块，AstroAcg.js:277-287）。
    _ACG_LAYER_KEYS = ("paranMode", "showLS", "showGeodetic", "showStarParans", "climes", "climesObliquity")
    # 日食路径（上游 v3.14.0 genParams :390-393）：`eclipse !== 'off'` 才下发 eclipse + eclipseFilter（关 = 零回归）。
    _ACG_ECLIPSE_KEYS = ("eclipse", "eclipseFilter")
    # 后端回显 meta 的有效值：请求值与之不符 = 后端不认、按缺省算了（ACGraph 静默归一）→ 说出来。
    _ACG_META_ECHO = ("mode", "lsMode", "geodetic", "geodeticVar", "coord", "posType", "horizon", "nodeType", "lilithType", "midpointMode", "relMode")
    _ACG_ONLY_KEYS = frozenset({
        *_ACG_ENGINE_KEYS, *_ACG_CCG_KEYS, *_ACG_REL_KEYS, *_ACG_LAYER_KEYS, *_ACG_ECLIPSE_KEYS,
        "clickLat", "clickLon", "pointOrb", "pointHsys", "eventKind", "eventDirection", "eventFromDate",
    })

    @staticmethod
    def _acg_flag(value: Any) -> str:
        return "1" if value in (True, 1, "1", "true", "True", "yes", "on") else "0"

    def _acg_remote_params(self, payload: dict[str, Any], ccg: dict[str, Any] | None) -> dict[str, Any]:
        remote: dict[str, Any] = {
            "date": payload["date"],
            "time": payload["time"],
            "zone": payload["zone"],
            "lat": payload["lat"],
            "lon": payload["lon"],
            "ad": payload.get("ad", 1),
            "mode": payload.get("mode", "mundo"),
            "lsMode": payload.get("lsMode", "great"),
            "geodetic": payload.get("geodetic", "sepharial"),
            "geodeticVar": payload.get("geodeticVar", "longitude"),
            # 上游 genParams 恒带 hsys = 页面「落点宫制」（缺省 placidus，AstroAcg.js:131/184）：宫尖线与落点报告同用。
            "hsys": payload.get("pointHsys") or "placidus",
        }
        for key in self._ACG_ENGINE_KEYS:
            value = payload.get(key)
            if value is None or value == "" or key in remote:
                continue
            remote[key] = self._acg_flag(value) if key in self._ACG_FLAG_KEYS else (f"{value}" if key == "harmonic" else value)
        eclipse = payload.get("eclipse")
        if eclipse and eclipse != "off":
            remote["eclipse"] = eclipse
            remote["eclipseFilter"] = payload.get("eclipseFilter") or "any"
        elif payload.get("eclipseFilter"):
            _degrade("acg: eclipseFilter given without eclipse", note="占星地图 eclipseFilter 须配 eclipse（prenatal / postnatal）才起作用；本次未开日食路径，未下发。")
        if ccg:
            remote.update(ccg)
        if payload.get("relMode") and payload.get("relDate"):
            remote["relMode"] = payload.get("relMode")
            remote["relDate"] = _to_slash_date(payload.get("relDate"))  # toSlashDate：公元前前导负号保留
            remote["relTime"] = payload.get("relTime") or "12:00:00"
            for key in ("relZone", "relLat", "relLon"):
                if payload.get(key) not in (None, ""):
                    remote[key] = payload.get(key)
        elif payload.get("relMode") or payload.get("relDate"):
            _degrade("acg: relMode/relDate given alone", note="占星地图关系盘须同时给 relMode（davison/composite/synastry）与 relDate（B 盘出生日期），缺一不下发（上游同口径）。")
        return remote

    def _run_acg_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 占星地图（AstroCartoGraphy）：行星地理投影线。地图渲染属 UI，无头输出为上游 [占星地图] 段（vendored
        # acgSnapshot.buildAcgSectionText）+ 本仓明细段（偕升纬度带/线交点/落点分析/事件时刻）。
        def geo_lon(value: Any) -> str:
            try:
                lon = ((float(value) + 180.0) % 360.0) - 180.0
            except (TypeError, ValueError):
                return "—"
            hemi = "E" if lon >= 0 else "W"
            return f"{abs(lon):.2f}°{hemi}"

        # [事件时刻]（/location/acgevent）先求：上游「世运事件快捷」（AstroAcg.pickMundane :386-404）把事件精确时刻填进
        # CCG 全行运通道重请求地图（事件时刻角化线）；zone 随本命时区下发（T-49：回本命时区钟面，不带则回 UT）。
        event: dict[str, Any] | None = None
        if payload.get("eventKind"):
            event_remote = {
                "kind": payload.get("eventKind"),
                "direction": payload.get("eventDirection") or "next",
                "fromDate": _to_slash_date(payload.get("eventFromDate") or payload.get("date") or ""),
                "zone": payload.get("zone"),
            }
            event = self._call_remote("/location/acgevent", event_remote)
            if not isinstance(event, dict) or not event.get("date"):
                raise ToolTransportError(
                    "世运事件端点未找到该事件。",
                    code="tool.acg_event_failed",
                    details={"endpoint": "/location/acgevent", "kind": payload.get("eventKind"), "response": event if isinstance(event, dict) else None},
                )
        ccg: dict[str, Any] | None = None
        if payload.get("ccgDate"):
            ccg = {
                "ccgDate": _to_slash_date(payload.get("ccgDate")),
                "ccgTime": payload.get("ccgTime") or "12:00:00",
                "ccgMix": payload.get("ccgMix") or "mixed",
            }
        elif event is not None:
            ccg = {"ccgDate": event.get("date"), "ccgTime": event.get("time") or "12:00:00", "ccgMix": payload.get("ccgMix") or "transit"}
        remote_payload = self._acg_remote_params(payload, ccg)
        response = self._call_remote("/location/acg", remote_payload)
        meta = response.get("meta") if isinstance(response.get("meta"), dict) else {}
        for key in self._ACG_META_ECHO:
            asked = payload.get(key)
            if asked in (None, "") or key not in meta:
                continue
            effective = meta.get(key)
            if f"{asked}".lower() != f"{effective}".lower():
                _degrade(
                    "acg: %s=%r not accepted by engine (effective %r)", key, asked, effective,
                    note=f"占星地图 {key}={asked!r} 引擎不认，已按 {effective!r} 计算（ACGraph 值域见 horosa_agent_guidance）。",
                )
        planets = response.get("planets") if isinstance(response.get("planets"), dict) else {}
        # 上游 locastro 是**辅盘 tab**：导出走 extractAstroContent（与 astrochart 逐字同一套本命盘段），
        # 再把地图段拼在尾巴上。这里补拉一次 /chart 并复用通用盘面渲染器；失败只是盘段不出，地图段照常。
        # 本命盘的口径 = 页面同一套 fields（黄道/岁差/宫制/古典全局键），不是只有经纬时区（此前只传 7 键）。
        chart_body = ""
        chart_details: Any = None
        try:
            chart_payload = {k: v for k, v in payload.items() if k not in self._ACG_ONLY_KEYS}
            chart_payload["predictive"] = 0
            chart_response = self._call_remote(
                "/chart", {k: v for k, v in chart_payload.items() if v is not None and k not in _CHART_DETAIL_ONLY_KEYS}
            )
            if _is_astro_chart_payload(chart_response):
                chart_response = self._attach_natal_extras("chart", chart_response, payload)
                chart_response = self._attach_classical_analysis("chart", chart_payload, chart_response)
                # [盘面细节]（上游 v3.14.0：locastro preset 同有此段，按本命盘参数算）。
                chart_response = self._attach_chart_details("chart", chart_payload, chart_response)
                chart_details = {k: chart_response[k] for k in ("chart_details", "settings_applied") if isinstance(chart_response.get(k), dict)}
                chart_body = _build_astro_snapshot_text(chart_payload, chart_response)
        except Exception as exc:  # noqa: BLE001 — 盘面富化失败不许带崩地图段
            _degrade("acg natal chart fetch failed: %s", exc)
        acg_data: dict[str, Any] = {
            "meta": meta,
            "planets": planets,
            "parans": response.get("parans") if isinstance(response.get("parans"), list) else [],
            "crossings": response.get("crossings") if isinstance(response.get("crossings"), list) else [],
        }
        # [落点分析]（/location/acgpoint）：上游 onMapClick = { ...genParams(), clickLat, clickLon, orb, hsys }（:337）。
        point: dict[str, Any] | None = None
        if payload.get("clickLat") is not None and payload.get("clickLon") is not None:
            point_remote = {
                **remote_payload,
                "clickLat": payload.get("clickLat"),
                "clickLon": payload.get("clickLon"),
                "orb": payload.get("pointOrb") if payload.get("pointOrb") is not None else 2,
            }
            point = self._call_remote("/location/acgpoint", point_remote)
            if not isinstance(point, dict) or not isinstance(point.get("relocAngles"), dict):
                raise ToolTransportError(
                    "落点分析端点返回了意外形状。",
                    code="tool.acg_point_failed",
                    details={"endpoint": "/location/acgpoint"},
                )
            acg_data["point"] = point
        # [占星地图]：上游 buildAcgSectionText（vendored 逐字；JS acg_section）。uiState 与页面 snapshotUiState 同形。
        ui_state = {
            "pointReport": point,
            "paranMode": payload.get("paranMode") or "off",
            "showStarParans": self._acg_flag(payload.get("stars")) == "1" and self._acg_flag(payload.get("showStarParans")) == "1",
            "showLS": self._acg_flag(payload.get("showLS")) == "1",
            "showGeodetic": self._acg_flag(payload.get("showGeodetic")) == "1",
            "geodeticZero": f"{payload.get('geodeticZero') if payload.get('geodeticZero') is not None else ''}",
            # v3.14.0 snapshotUiState（AstroAcg.js:296-297）：气候带图层与黄赤交角口径。
            "climes": payload.get("climes") or "off",
            "climesObliquity": payload.get("climesObliquity") or "date",
        }
        if payload.get("climesObliquity") and ui_state["climes"] == "off":
            _degrade("acg: climesObliquity given without climes", note="占星地图 climesObliquity 须配 climes（klimata / parallels）才起作用；本次未开气候带，未成块。")
        # 日食路径（后端 ACGraph._eclipse）：开了却没回 = 引擎没找到 / 不认这个键（旧引擎）→ 「◆ 日食路径」不成块，说出来；
        # 回的不是所请求的那一次（which / filter 不符）同样不许照写。
        eclipse_asked = remote_payload.get("eclipse")
        eclipse = response.get("eclipse") if isinstance(response.get("eclipse"), dict) else None
        if eclipse_asked:
            if eclipse is None or not isinstance(eclipse.get("greatest"), dict):
                eclipse = None
                _degrade(
                    "acg: eclipse=%s asked but engine returned none", eclipse_asked,
                    note=f"占星地图日食路径（eclipse={eclipse_asked}）排盘引擎没有回结果，[占星地图] 的「◆ 日食路径」本次未产出。",
                )
            elif eclipse.get("which") != eclipse_asked or eclipse.get("filter") != remote_payload.get("eclipseFilter"):
                _degrade(
                    "acg: eclipse echo mismatch (asked %s/%s, got %r/%r)", eclipse_asked, remote_payload.get("eclipseFilter"),
                    eclipse.get("which"), eclipse.get("filter"),
                    note=f"占星地图日食路径：请求 {eclipse_asked}/{remote_payload.get('eclipseFilter')}，引擎按 {eclipse.get('which')}/{eclipse.get('filter')} 算，以引擎回显为准。",
                )
        if eclipse is not None:
            # 后端原样（which / filter / type / central / greatest / track / north / south / utc / local…）：正文的「◆ 日食路径」
            # 与报告盘图（app AcgD3Map 的日食层）读同一份。
            acg_data["eclipse"] = eclipse
        if ui_state["climes"] != "off":
            # 气候带是纯渲染层（纬度由 acgLayers.climesLines 现推）：把开着的口径留在结果里，盘图层与正文同一口径。
            acg_data["layers"] = {"climes": ui_state["climes"], "climesObliquity": ui_state["climesObliquity"]}
        map_text = ""
        try:
            js = self.js_client.run("acg_section", {"acgData": response, "uiState": ui_state})
            map_text = f"{(js or {}).get('text') or ''}".strip()
        except Exception as exc:  # noqa: BLE001 — 段 builder 失败：地图段缺席并说出来
            _degrade("acg section build failed: %s", exc, note=f"占星地图 [占星地图] 段本次未产出（JS 段 builder 失败：{exc}），其余段不受影响。")
        # 上游段头是全角 `【占星地图】`（aiExport 的段名解析两种括号等价）；本仓统一以 `[X]` 渲染，正文逐字。
        map_body = map_text.split("\n", 1)[1] if map_text.startswith("【占星地图】\n") else map_text
        sections: list[tuple[str, str]] = []
        if map_body.strip():
            sections.append(("占星地图", map_body.strip()))
        parans = acg_data["parans"]
        if parans:
            rows = [f"偕升纬度带（同纬度两星同时临角，前 {min(len(parans), 40)}/{len(parans)} 条）："]
            for item in parans[:40]:
                if isinstance(item, dict):
                    rows.append(
                        f"纬 {item.get('lat')}°：{_astro_msg(item.get('a'), short=True)}·{item.get('aEvent')} × "
                        f"{_astro_msg(item.get('b'), short=True)}·{item.get('bEvent')}（{item.get('type')}）"
                    )
            sections.append(("偕升纬度带", "\n".join(rows)))
        crossings = acg_data["crossings"]
        if crossings:
            rows = [f"线交点（一星临 MC/IC 直线 × 一星临 ASC/DESC 曲线，前 {min(len(crossings), 40)}/{len(crossings)} 处）："]
            for item in crossings[:40]:
                if isinstance(item, dict):
                    a = _astro_msg(item.get("a"), short=True)
                    b = _astro_msg(item.get("b"), short=True)
                    # 源 _crossings 返回键：a/aAngle(mc|ic) × b/bAngle(asc|desc)。角色标签取 aAngle/bAngle。
                    a_ang = item.get("aAngle") or ""
                    b_ang = item.get("bAngle") or ""
                    lat_v, lon_v = item.get("lat"), item.get("lon")
                    lat_txt = f"{float(lat_v):.2f}°" if isinstance(lat_v, (int, float)) else "—"
                    rows.append(f"{a}·{a_ang} × {b}·{b_ang}：纬 {lat_txt}，经 {geo_lon(lon_v)}")
            sections.append(("线交点", "\n".join(rows)))
        if point is not None:
            point_lines = [
                f"落点：纬 {point.get('lat')}°，经 {geo_lon(point.get('lon'))}　容许度 {_round3(point.get('orb'))}°　"
                f"重置盘分宫制 {point.get('hsys')}",
            ]
            hits = point.get("hits") if isinstance(point.get("hits"), list) else []
            if hits:
                point_lines.append("命中线（该地临角的星）：")
                for hit in hits:
                    if isinstance(hit, dict):
                        point_lines.append(
                            f"{_astro_msg(hit.get('planet'), short=True)} 临 {hit.get('angle')}（距 {_round3(hit.get('orb'))}°）"
                        )
            else:
                point_lines.append("命中线：容许度内无星临角。")
            reloc = point.get("relocAngles") or {}
            point_lines.append(
                "重置四角：" + "　".join(f"{k} {_sign_degree(v)}" for k, v in reloc.items() if v is not None)
            )
            sensitive = point.get("sensitive") if isinstance(point.get("sensitive"), dict) else {}
            if sensitive:
                sens_cn = {
                    "vertex": "宿命点", "eastpoint": "东升点", "coasc_koch": "共升点(Koch)",
                    "coasc_munkasey": "共升点(Munkasey)", "polarasc": "极地上升",
                    "antiscia_mc": "映点MC", "antiscia_asc": "映点ASC",
                }
                point_lines.append(
                    "敏感点：" + "　".join(
                        f"{sens_cn.get(k, k)} {_sign_degree(v)}" for k, v in sensitive.items() if v is not None
                    )
                )
            sections.append(("落点分析", "\n".join(point_lines)))
        if event is not None:
            acg_data["event"] = event
            kind_cn = {
                "solar_eclipse": "日食", "lunar_eclipse": "月食", "newmoon": "新月", "fullmoon": "满月",
                "aries_ingress": "白羊入境（春分）", "cancer_ingress": "巨蟹入境（夏至）",
                "libra_ingress": "天秤入境（秋分）", "capricorn_ingress": "摩羯入境（冬至）",
            }.get(str(event.get("kind")), str(event.get("kind")))
            zone_text = event.get("zone") or "+00:00"
            # 时刻按请求时区的钟面回（后端带回 zone；没带 zone 的旧后端 = UT）。
            zone_label = "UTC" if zone_text in ("+00:00", "0", 0) else f"{zone_text}"
            ccg_note = "；已填入 CCG 全行运通道（事件时刻角化线见 [占星地图]）" if ccg and not payload.get("ccgDate") else ""
            sections.append((
                "事件时刻",
                f"{kind_cn}（{payload.get('eventDirection') or 'next'}）：{event.get('date')} {event.get('time')} {zone_label}{ccg_note}",
            ))
        # 段序对齐上游：本命盘段在前、[占星地图] 及其明细在后。
        snapshot_text = _render_snapshot_text(sections)
        if chart_body:
            snapshot_text = f"{chart_body}\n{snapshot_text}"
        return {
            "acg": acg_data,
            # [盘面细节] 的实际口径 + 点名的表 + 受孕期起算时刻回显（同本命盘工具的 data.chart_details / settings_applied；段没出时无此二键）。
            **(chart_details if isinstance(chart_details, dict) else {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="acg", snapshot_text=snapshot_text),
        }

    def _run_germany_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # rectifyEvents 只喂 [校时预览]（前端纯函数 rectificationHits），不下发后端。
        rectify_events = payload.get("rectifyEvents")
        chart_payload = {**{key: value for key, value in payload.items() if key != "rectifyEvents"}, "predictive": 0}
        chart_response = self._call_remote("/chart", chart_payload)
        germany_result = self._call_remote("/germany/midpoint", chart_payload)
        snapshot_text = _build_germany_snapshot_text(chart_payload, chart_response, germany_result, rectify_events=rectify_events)
        snapshot_text = self._germany_upstream_tail(payload, chart_payload, chart_response, germany_result, snapshot_text)
        result = {
            "chart": chart_response.get("chart"),
            "midpoints": germany_result.get("midpoints", germany_result if isinstance(germany_result, list) else []),
            "aspects": germany_result.get("aspects", {}),
            "raw": germany_result,
            "snapshot_text": snapshot_text,
        }
        result["export_snapshot"] = self._augment_export_payload(technique="germany", snapshot_text=snapshot_text)
        return result

    # 汉堡要素的门（上游 buildHamburgLines 的 showHamburg）里 skill 接得上的那几键：流派非 classic / 差值表 / 严格因子集 / 戴维森第二人。
    # 门内正文全由上游函数出；门外不起 node（缺省调用零开销，正文与上游缺省同样没有这几段）。
    _GERMANY_TIME_KEYS = ("transitAt", "showDiffList", "diffTargetAge", "saKey", "dialBase", "ephemStart", "ephemEnd")

    def _germany_upstream_tail(
        self, payload: dict[str, Any], chart_payload: dict[str, Any], chart_response: dict[str, Any], germany_result: Any, text: str,
    ) -> str:
        """量化盘正文的上游尾段（v3.15.0 AstroMidpoint.buildGermanySnapshotText 末 + buildGermanySnapshotForFields 时间层）：

        - [汉堡学派要素]（+ 组合盘 / [戴维森盘] / [虚星参考]）= 上游 buildHamburgLines：只在流派非 classic 或开了汉堡开关时出
          （上游缺省 classic 全关 → 不出；skill 旧版无条件附 [虚星参考]，是漏看了这道门）；
        - [行运接触] = uranianTransitContactText：给了 transitAt 才出，行运盘同地点在该时刻起 + 中点服务取 TNP；
        - [图形星历] = graphicEphemerisText：给了 ephemStart / ephemEnd 才出，/astroextra/ephemeris 逐日黄经。
        三段都经报告盘图 bundle 的 app-text 通道跑上游原函数；bundle / 后端不可用 → 该段不出 + warnings（上游同：取不到就不出）。
        """
        disp: dict[str, Any] = {k: payload[k] for k in ("school", "orb", "strictFactors", *self._GERMANY_TIME_KEYS)
                                if payload.get(k) not in (None, "")}
        if payload.get("personalOrb") not in (None, ""):
            disp["orbPersonal"] = payload["personalOrb"]
        if payload.get("showTnp") is not None:
            disp["showTnp"] = bool(payload.get("showTnp"))
        if isinstance(payload.get("davison"), dict):
            disp["showDavison"] = True
        tnp = germany_result.get("tnp") if isinstance(germany_result, dict) else None
        hamburg_gate = disp.get("school", "classic") != "classic" or bool(disp.get("showDiffList")) or bool(disp.get("strictFactors")) \
            or bool(disp.get("showDavison"))
        want_transit = bool(disp.get("transitAt"))
        want_gephem = bool(disp.get("ephemStart")) and bool(disp.get("ephemEnd"))
        if not (hamburg_gate or want_transit or want_gephem):
            return text
        dial_points = _dial_points((chart_response.get("chart") or {}).get("objects"), tnp)
        first = [
            {"name": "germany_hamburg", "args": {"disp": disp, "dialPoints": dial_points, "result": germany_result}},
            {"name": "germany_points", "args": {"chart": chart_response, "tnp": tnp}},
            {"name": "germany_gephem_plan", "args": {"disp": disp}},
        ]
        runs = self.js_client.run_app_texts(first)
        if not isinstance(runs, list):
            _degrade("germany upstream tail: app-charts bundle unavailable",
                     note="量化盘的 [汉堡学派要素] / [行运接触] / [图形星历] 本次未产出（上游正文代码不可用）；其余段照常。")
            return text
        hamburg, natal_points, plan = (r.get("value") if r.get("ok") else None for r in runs)
        if hamburg_gate and f"{hamburg or ''}".strip():
            text = f"{text}\n{f'{hamburg}'.strip()}"
        second: list[dict[str, Any]] = []
        if want_transit and isinstance(natal_points, list):
            at = f"{disp['transitAt']}".strip()
            date_part, _, time_part = at.replace("T", " ").partition(" ")
            time_text = (time_part or "12:00")[:8]
            time_text = f"{time_text}:00" if len(time_text) == 5 else time_text
            transit_payload = {k: v for k, v in chart_payload.items() if k not in ("davison", *self._GERMANY_TIME_KEYS)}
            transit_payload.update(date=date_part, time=time_text, ad=_ad_of_date(date_part))
            try:
                t_chart = self._call_remote("/chart", transit_payload)
                t_mid = self._call_remote("/germany/midpoint", transit_payload)
                second.append({"name": "germany_points", "args": {"chart": t_chart, "tnp": (t_mid or {}).get("tnp") if isinstance(t_mid, dict) else None}})
            except Exception as exc:  # noqa: BLE001 — 上游：行运盘取不到 → 不出时间层
                _degrade("germany transit chart failed: %s", exc, note=f"[行运接触] 本次未产出（{at} 的行运盘取不到）。")
        if want_gephem and isinstance(plan, dict):
            rg = plan.get("range") or {}
            body = {k: chart_payload.get(k) for k in ("date", "time", "zone", "lat", "lon", "gpsLat", "gpsLon", "hsys", "zodiacal", "siderealAyanamsa")}
            body.update(startDate=_to_slash_date(rg.get("start")), endDate=_to_slash_date(rg.get("end")),
                        startTime="00:00:00", endTime="00:00:00", planets=plan.get("planets"), includeTransits=False)
            try:
                eph = self._call_remote("/astroextra/ephemeris", {k: v for k, v in body.items() if v is not None})
                rows = eph.get("dailyPositions") if isinstance(eph, dict) else None
                if isinstance(rows, list) and rows:
                    second.append({"name": "germany_gephem", "args": {"rows": rows, "planets": plan.get("planets"), "chart": chart_response,
                                                                      "base": plan.get("base"), "range": rg}})
            except Exception as exc:  # noqa: BLE001 — 上游：星历取不到 → 不出该段
                _degrade("germany graphic ephemeris failed: %s", exc, note="[图形星历] 本次未产出（逐日星历取不到）。")
        if not second:
            return text
        runs2 = self.js_client.run_app_texts(second)
        if not isinstance(runs2, list):
            _degrade("germany time layer: app-charts bundle unavailable", note="量化盘时间层本次未产出（上游正文代码不可用）。")
            return text
        tail: list[str] = []
        for call, run in zip(second, runs2):
            if not run.get("ok"):
                continue
            if call["name"] == "germany_points":
                t3 = self.js_client.run_app_texts([{"name": "germany_transit", "args": {"disp": disp, "natalPts": natal_points, "transitPts": run.get("value")}}])
                if isinstance(t3, list) and t3 and t3[0].get("ok"):
                    tail.append(f"{t3[0].get('value')}".strip())
            else:
                tail.append(f"{run.get('value')}".strip())
        # 上游顺序：正文 → [行运接触] → [图形星历]
        tail.sort(key=lambda s: 0 if s.startswith("[行运接触]") else 1)
        for block in tail:
            if block:
                text = f"{text}\n{block}"
        return text

    def _run_harmonic_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 调波盘: a backend chart-extra computation on the Python chart service (/astroextra/harmonic).
        # 上游 v50 已给调波盘正式导出键（aiExport.js 的 `harmonic`，属 ASTRO_LIKE_EXPORT_KEYS 族），
        # 故此处不再是「无契约的实验面」——见 TOOL_EXPORT_TECHNIQUE_MAP。
        # 调波数在 schema 层已判（western_vocab.parse_harmonic：1–360 整数，越界拒），这里不再夹取。
        harmonic_num = int(payload.get("harmonic") or 9)
        orb = payload.get("orb", 2.0)
        remote_payload = {**payload, "predictive": 0, "harmonic": harmonic_num, "orb": orb}
        response = self._call_remote("/astroextra/harmonic", remote_payload)
        # 注意：这里**不要**回填 `snapshot_text`——统一出口是「工具自带 snapshot_text 就短路自动渲染器」
        # （见 `_flush_export_snapshot` 的 `if not snapshot_text:`）。调波盘要的是通用盘面段 + 调波两段的
        # 合并文本，由 `_auto_snapshot_text_for_tool` 负责；自带一份只含 3 段的文本会把整套盘面段挡掉。
        # `/astroextra/harmonic` 把整个标准 chart-wrap（{chart, aspects, lots, receptions, mutuals,
        # declParallel, params}）放在响应的 `chart` 键下——比导出层通用段构建器预期的深一层。此前原样
        # 转发，导致 [宫位宫头]/[星与虚点]/[相位]/[行星]/[希腊点]/[12分度]/[主宰星链]/[寿命格局] 等
        # 一整批段只出「本次本地计算结果未返回…」占位存根。摊平到顶层，通用构建器才认得。
        chart_wrap = response.get("chart") if isinstance(response.get("chart"), dict) else {}
        # [调波盘] 专属段（v3.9.2）：H 数/位置表/同频，镜像 AstroHarmonicLab.js:65-73。
        lines = [f"调波数：H{_js_template_str(response.get('harmonic') or harmonic_num)}"]
        lines.extend(_derived_position_lines(response.get("positions"), "调波"))
        lines.extend(_derived_conjunction_lines(response.get("conjunctions")))
        return {
            **chart_wrap,
            "harmonic": response.get("harmonic", harmonic_num),
            "positions": response.get("positions", []),
            "conjunctions": response.get("conjunctions", []),
            "raw": response,
            # 上游 out = ['[调波盘]', '调波数：…', …]，`out.length > 1` 恒真（AstroHarmonicLab.js:81）→ [调波盘] 恒出。
            "_derivedSelf": {"title": "调波盘", "lines": lines},
        }

    def _run_babylon_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        """巴比伦占星：恒星黄道 · 毕宿锚盘 → vendored 纯函数链铺各段（v3.14.0 起含后端实算的 [天象实算]）。

        上游的编排函数自己发两个请求，headless 侧按 §5 由 Python 发、JS 只算与排版。
        `/astroextra/ephemeris`（朔望/邻近食）取不到时，[分至天狼星] 段内两行实算自动省略、
        图式行照常 —— 与上游同一条降级口径，故不视为失败。
        """
        chart_payload = {
            **payload,
            "predictive": 0,
            "tradition": 1,
            # 口径由体系决定，不是用户可选项：巴比伦盘恒为恒星黄道 + 毕宿锚（金牛 15°）。
            "zodiacal": 1,
            "siderealAyanamsa": "aldebaran_15tau",
        }
        for stale in ("scheme", "solstice", "era", "ephemerisSource", "dodecaVariant", "cubitDeg", "schemeCn",
                      "datetime", "dirZone", "dirLat", "dirLon"):
            chart_payload.pop(stale, None)
        chart = self._call_remote("/chart", chart_payload)
        # 带符号年（上游 dateStrSafe.parseDateParts）：公元前在入口统一成 '-0500-03-21'（input_normalization._fold_era）。
        # 旧 split('-') 把前导负号切成空段 → 公元前日期一律「Invalid date」。
        parsed_date = _parse_date_parts(payload.get("date"))
        if parsed_date is None:
            raise ToolValidationError(f"Invalid date for tool `babylon`: {payload.get('date')!r}")
        year, month, day = parsed_date
        if f"{payload.get('ad', 1)}" == "-1":
            year = -abs(year)  # 公元前：同上游 babylonBirthJdn 的 signedYear 分支
        ephemeris = None
        try:
            ephemeris = self._call_remote("/astroextra/ephemeris", {**chart_payload, "kinds": "lunations"})
        except Exception as exc:  # noqa: BLE001 — 实算历象缺失只丢两行，不影响成段
            _degrade("babylon ephemeris fetch failed: %s", exc)
        # [天象实算]（上游 v3.14.0，aiExport v64）：七曜所行三道 / 26 颗 ziqpu 星钟 / 目标年取数 / 五星周期现象与出生时可见状态，
        # 后端 /astroextra/babylontables 实算。请求体照上游 fetchBabylonSkyTables（babylonAiSnapshot.js:398-403）：盘面参数里的
        # date / time / zone / lat / lon / ad 六键（无其他口径——「目标年」取本盘年份减各星周期，不是入参）。
        # 上游取不到就静默少这一段；这里说出来（段缺席 + warnings）。
        sky_tables = None
        try:
            sky = self._call_remote(
                "/astroextra/babylontables",
                {key: chart_payload.get(key) for key in ("date", "time", "zone", "lat", "lon", "ad")},
            )
            if isinstance(sky, dict) and isinstance(sky.get("paths"), list):
                sky_tables = sky
                # 后端四块各自 try/except，失败的那块回 None（babylon_tables.build_babylon_tables）：段里少那一行，说出来。
                lost = [cn for key, cn in (("ziqpu", "ziqpu 星钟"), ("goalYear", "目标年取数"), ("phenomena", "周期现象")) if sky.get(key) is None]
                if lost:
                    _degrade(
                        "babylon sky tables partial: %s", "/".join(lost),
                        note=f"巴比伦 [天象实算] 段缺 {'、'.join(lost)}（排盘引擎这一块没有算出来），其余行照常。",
                    )
            else:
                _degrade(
                    "babylon sky tables: 响应无 paths",
                    note="巴比伦 [天象实算] 段本次未产出：/astroextra/babylontables 没有回七曜三道（paths），其余段不受影响。",
                )
        except Exception as exc:  # noqa: BLE001 — 天象实算取不到只少这一段
            _degrade(
                "babylon sky tables fetch failed: %s", exc,
                note=f"巴比伦 [天象实算] 段本次未产出（/astroextra/babylontables 取数失败：{exc}），其余段不受影响。",
            )
        js = self.js_client.run(
            "babylon",
            {
                "chart": chart,
                "year": year,
                "month": month,
                "day": day,
                "ephemeris": ephemeris,
                "skyTables": sky_tables,
                # scheme 是**档 id**（JS 侧据它查 BABYLON_SCHEMES 解析出 judge 参数），
                # solstice/dodecaVariant/cubitDeg/era/ephemerisSource 是显式覆写，缺省则跟档走（v3.11：era 进
                # [起盘信息] 纪元行、ephemerisSource 选 [数理星历] 木星函数；值域锚定 BABYLON_PARAM_SPEC）。
                "scheme": payload.get("scheme"),
                "solstice": payload.get("solstice"),
                **{k: payload[k] for k in ("dodecaVariant", "cubitDeg", "schemeCn", "era", "ephemerisSource") if payload.get(k) is not None},
            },
        )
        invalid = (js or {}).get("invalid") if isinstance(js, dict) else None
        if invalid:
            parts = [f"{i.get('key')}={i.get('value')!r}（可选：{'/'.join(i.get('allowed') or [])}）" for i in invalid if isinstance(i, dict)]
            raise ToolValidationError(
                bilingual(f"巴比伦派系参数取值无效：{'；'.join(parts)}。", f"babylon setting(s) invalid: {'; '.join(parts)}."),
                code="tool.babylon_invalid_setting",
                details={"invalid": invalid},
            )
        if isinstance(js, dict) and js.get("error") == "no_planet_positions":
            # 上游 v3.13.0 buildBabylonSnapshotForFields：/chart 没回七曜位置即抛错、不出快照（此前铺出六段空壳）。
            raise ToolTransportError(
                bilingual("巴比伦占星：排盘服务没有回七曜位置，未出快照。", "babylon: the chart service returned no planet positions."),
                code="tool.babylon_chart_unavailable",
                details={"message": js.get("message")},
            )
        snapshot_text = f"{(js or {}).get('text') or ''}".strip()
        board = (js or {}).get("board") if isinstance(js, dict) else None
        return {
            "chart": chart.get("chart"),
            "raw": chart,
            # 报告盘图（app 原版 BabylonHoroscope）用的起盘口径：JS 算正文时的同一 jdn / 派系 opts，不另算
            "board_context": board if isinstance(board, dict) else None,
            # 天象实算原始数据（/astroextra/babylontables；[天象实算] 段的来源，取不到为 None）
            "sky_tables": sky_tables,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="babylon", snapshot_text=snapshot_text),
        }

    def _run_draconic_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 龙盘：各点黄经减北交点（交点归零）。后端把标准 chart-wrap 放在响应的 `chart` 键下——
        # 与 /astroextra/harmonic 同一形状，比导出层通用段构建器预期深一层，故同样摊平到顶层。
        # v3.13.1 宫位口径（AstroDraconicLab.js:19-25/69）：上游页面恒带 draconicHouses；后端缺键 = 整宫（Java 白名单注释
        # 「缺键 = 整宫 = 零回归」）→ skill 只在 shift 时下发，缺省请求体与 v3.13.0 字节相同。
        house_mode = payload.get("draconicHouses") if payload.get("draconicHouses") in DRACONIC_HOUSE_MODES else DRACONIC_HOUSE_MODE_DEFAULT
        remote_payload = {k: v for k, v in payload.items() if k != "draconicHouses"}
        if house_mode != DRACONIC_HOUSE_MODE_DEFAULT:
            remote_payload["draconicHouses"] = house_mode
        response = self._call_remote("/astroextra/draconic", {**remote_payload, "predictive": 0})
        chart_wrap = response.get("chart") if isinstance(response.get("chart"), dict) else {}
        # [龙盘] 专属段（v3.9.2 派生盘快照重定源）：龙首归零基准/位置/同频，逐字镜像
        # AstroDraconicLab.js:78-84（v3.13.1 起多一行宫位口径，段恒出）。
        lines: list[str] = []
        if response.get("nodeLon") is not None:
            # [Q-351/T-332]（AstroDraconicLab.js:4-7/53）注明真 / 平交点：本命盘 params.westNodeType === 'true' → 真交点，否则平交点。
            # westNodeType 在 schema 层已读成规范值（western_vocab：True / 真交点 / TRUE → 'true'），与后端算龙首用的是同一个值。
            node_type = "真交点" if payload.get("westNodeType") == "true" else "平交点"
            lines.append(f"北交点 {fmt_num(response['nodeLon'], 2)}°（{node_type}） → 归零白羊 0°（龙盘基准）")
        # v3.13.1 AstroDraconicLab.js:80：宫位口径行无条件 push（缺省档同样写出）→ [龙盘] 段恒出。
        lines.append(
            f"宫位口径：{DRACONIC_HOUSE_LABELS.get(house_mode) or DRACONIC_HOUSE_LABELS[DRACONIC_HOUSE_MODE_DEFAULT]}"
            f"{'，各星落宫与本命一致' if house_mode == 'shift' else ''}"
        )
        lines.extend(_derived_position_lines(response.get("positions"), "龙盘"))
        lines.extend(_derived_conjunction_lines(response.get("conjunctions")))
        return {
            **chart_wrap,
            "nodeLon": response.get("nodeLon"),
            "positions": response.get("positions", []),
            "conjunctions": response.get("conjunctions", []),
            "raw": response,
            # 上游 out = [段头, 交点行?, 宫位口径行, …]：v3.13.1 起宫位口径行恒在 → out.length > 1 恒真、[龙盘] 恒出。
            "_derivedSelf": {"title": "龙盘", "lines": lines},
        }

    def _run_relocation_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 重置盘：出生 UT 不变，只按新经纬重算宫位与角点（行星黄经由 UT 决定故不变）。
        # 响应同 harmonic/draconic 的嵌套形状 → 同样摊平。relocLat/relocLon 缺省回退出生地。
        # [盘面细节] / [古典格局] 两段按重置后的地点另取（上游 v3.14.0 AstroRelocationLab.fetchRelocExtras），在富化层
        # （enrich._attach_classical_analysis / _attach_chart_details 经 _derived_section_params 换经纬）；盘面细节的口径键不进本请求。
        response = self._call_remote(
            "/astroextra/relocation", {**{k: v for k, v in payload.items() if k not in _CHART_DETAIL_ONLY_KEYS}, "predictive": 0}
        )
        chart_wrap = response.get("chart") if isinstance(response.get("chart"), dict) else {}
        # [重置盘] 专属段（v3.9.2）：地点 + 四角对比，镜像 AstroRelocationLab.js:138-149。
        # 本命四角需另铸一张本命盘（上游用页面上已有的 props.value；headless 补一次 /chart）——
        # 上游同款 try 包裹：「角点缺省不产行」，本命盘取不到就只出地点行。
        lines = [
            f"重置地点：纬 {_reloc_display_degree(response.get('relocLat', payload.get('relocLat', payload.get('lat'))), lat=True)} / "
            f"经 {_reloc_display_degree(response.get('relocLon', payload.get('relocLon', payload.get('lon'))), lat=False)}"
        ]
        try:
            natal_payload = {k: v for k, v in payload.items() if k not in {"relocLat", "relocLon", *_CHART_DETAIL_ONLY_KEYS}}
            natal = self._call_remote("/chart", {**natal_payload, "predictive": 0})
            chart_wrap = _with_natal_planet_sign(chart_wrap, natal)
            natal_angles = _chart_angles(natal)
            reloc_angles = _chart_angles(chart_wrap)
            for angle_id in ("Asc", "MC", "Desc", "IC"):
                n, r = natal_angles.get(angle_id), reloc_angles.get(angle_id)
                if n or r:
                    lines.append(f"{_derived_cn(angle_id)}：本命 {_angle_text(n)} → 重置后 {_angle_text(r)}")
        except Exception as exc:  # noqa: BLE001 - 角点对比失败不阻断重置盘本体，但四轴对比行缺了要说
            _degrade("relocation natal-angle comparison failed: %s", exc)
        return {
            **chart_wrap,
            "relocLat": response.get("relocLat"),
            "relocLon": response.get("relocLon"),
            "natalLat": response.get("natalLat"),
            "natalLon": response.get("natalLon"),
            "raw": response,
            # 上游 out = [段头, 地点行, …角点]：地点行无条件 push，故 [重置盘] 恒出（角点缺省只少行）。
            "_derivedSelf": {"title": "重置盘", "lines": lines},
        }
