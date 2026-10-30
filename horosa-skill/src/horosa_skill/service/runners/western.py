"""西洋 runner（WesternRunners）：印度校正、行星周期、占星地图、汉堡盘、泛音盘、巴比伦、龙头盘、迁移盘。"""
from __future__ import annotations

from typing import Any

from horosa_skill.astro_rulers import js_template_str as _js_template_str
from horosa_skill.engine.astroextra_snapshots import fmt_num
from horosa_skill.errors import ToolTransportError, ToolValidationError, bilingual
from horosa_skill.service._common import _is_astro_chart_payload, _render_snapshot_text, _to_slash_date
from horosa_skill.service._context import _degrade
from horosa_skill.service.text.astro_core import (
    ASTRO_TEXT_MAP,
    _astro_msg,
    _round3,
    _sign_degree,
)
from horosa_skill.service.text.chart_family import _build_astro_snapshot_text
from horosa_skill.service.text.predictive import _build_india_rectify_snapshot_text
from horosa_skill.service.text.western import (
    _angle_text,
    _build_germany_snapshot_text,
    _chart_angles,
    _derived_conjunction_lines,
    _derived_position_lines,
    _reloc_display_degree,
)


class WesternRunners:
    # ── 印度出生时间校正（批 I-2，/india/rectify）───────────────────────────────

    def _run_india_rectify_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        remote = {**payload}
        for key in ("rectifyWindowMinutes", "rectifyStepSeconds", "rectifyTopK", "rectifyRpSource", "rectifyEvents"):
            if remote.get(key) is None:
                remote.pop(key, None)
        response = self._call_remote("/india/rectify", remote)
        if not isinstance(response, dict) or response.get("available") is not True:
            raise ToolTransportError(
                "印度校时端点未返回可用结果。",
                code="tool.india_rectify_failed",
                details={"endpoint": "/india/rectify", "response": response if isinstance(response, dict) else {"shape": type(response).__name__}},
            )
        snapshot_text = _build_india_rectify_snapshot_text(payload, response)
        return {
            "rectify": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="india_rectify", snapshot_text=snapshot_text),
        }

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
                hour_val = float(ev.get("hour") or 0.0)
                hh, mm = int(hour_val), int(round((hour_val - int(hour_val)) * 60)) % 60
                when = f"{ev.get('year')}-{int(ev.get('month') or 0):02d}-{int(ev.get('day') or 0):02d} {hh:02d}:{mm:02d}"
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

    # ── 占星地图（AstroCartoGraphy）请求口径：上游 AstroAcg.genParams（AstroAcg.js:348-372）逐键 ──────────────
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
    _ACG_LAYER_KEYS = ("paranMode", "showLS", "showGeodetic", "showStarParans")
    # 后端回显 meta 的有效值：请求值与之不符 = 后端不认、按缺省算了（ACGraph 静默归一）→ 说出来。
    _ACG_META_ECHO = ("mode", "lsMode", "geodetic", "geodeticVar", "coord", "posType", "horizon", "nodeType", "lilithType", "midpointMode", "relMode")
    _ACG_ONLY_KEYS = frozenset({
        *_ACG_ENGINE_KEYS, *_ACG_CCG_KEYS, *_ACG_REL_KEYS, *_ACG_LAYER_KEYS,
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
            # 上游 genParams 恒带 hsys = 页面「落点宫制」（缺省 placidus，AstroAcg.js:130/184）：宫尖线与落点报告同用。
            "hsys": payload.get("pointHsys") or "placidus",
        }
        for key in self._ACG_ENGINE_KEYS:
            value = payload.get(key)
            if value is None or value == "" or key in remote:
                continue
            remote[key] = self._acg_flag(value) if key in self._ACG_FLAG_KEYS else (f"{value}" if key == "harmonic" else value)
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
        try:
            chart_payload = {k: v for k, v in payload.items() if k not in self._ACG_ONLY_KEYS}
            chart_payload["predictive"] = 0
            chart_response = self._call_remote("/chart", {k: v for k, v in chart_payload.items() if v is not None})
            if _is_astro_chart_payload(chart_response):
                chart_response = self._attach_natal_extras("chart", chart_response, payload)
                chart_response = self._attach_classical_analysis("chart", chart_payload, chart_response)
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
        }
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
        # [戴维森盘]（后端 davison 字段，仅在请求带 davison 第二人时返回）+ [虚星参考]（静态口径表）。
        # 两段由 vendored 上游排版逐字产出；失败只是这两段不出，不影响主盘。
        try:
            extra = self.js_client.run(
                "uranian_extra",
                {
                    "davison": germany_result.get("davison") if isinstance(germany_result, dict) else None,
                    "school": payload.get("school"),
                    "showTnp": payload.get("showTnp", True),
                    "labels": ASTRO_TEXT_MAP,
                },
            )
            extra_text = f"{(extra or {}).get('text') or ''}".strip()
            if extra_text:
                snapshot_text = f"{snapshot_text}\n{extra_text}".strip()
        except Exception as exc:  # noqa: BLE001 — 附注段失败不影响量化盘
            _degrade("uranian extra sections failed: %s", exc)
        result = {
            "chart": chart_response.get("chart"),
            "midpoints": germany_result.get("midpoints", germany_result if isinstance(germany_result, list) else []),
            "aspects": germany_result.get("aspects", {}),
            "raw": germany_result,
            "snapshot_text": snapshot_text,
        }
        result["export_snapshot"] = self._augment_export_payload(technique="germany", snapshot_text=snapshot_text)
        return result

    def _run_harmonic_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 调波盘: a backend chart-extra computation on the Python chart service (/astroextra/harmonic).
        # 上游 v50 已给调波盘正式导出键（aiExport.js 的 `harmonic`，属 ASTRO_LIKE_EXPORT_KEYS 族），
        # 故此处不再是「无契约的实验面」——见 TOOL_EXPORT_TECHNIQUE_MAP。
        try:
            harmonic_num = max(1, min(int(payload.get("harmonic", 9)), 360))
        except (TypeError, ValueError):
            harmonic_num = 9
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
        """巴比伦占星：恒星黄道 · 毕宿锚盘 → vendored 纯函数链铺六段。

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
        date_text = f"{payload.get('date') or ''}".replace("/", "-")
        parts = date_text.split("-")
        try:
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2][:2])
        except (IndexError, ValueError):
            raise ToolValidationError(f"Invalid date for tool `babylon`: {payload.get('date')!r}") from None
        if f"{payload.get('ad', 1)}" in {"-1", "0"}:
            year = -abs(year)  # 公元前：同上游 babylonBirthJdn 的 signedYear 分支
        ephemeris = None
        try:
            ephemeris = self._call_remote("/astroextra/ephemeris", {**chart_payload, "kinds": "lunations"})
        except Exception as exc:  # noqa: BLE001 — 实算历象缺失只丢两行，不影响成段
            _degrade("babylon ephemeris fetch failed: %s", exc)
        js = self.js_client.run(
            "babylon",
            {
                "chart": chart,
                "year": year,
                "month": month,
                "day": day,
                "ephemeris": ephemeris,
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
        return {
            "chart": chart.get("chart"),
            "raw": chart,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="babylon", snapshot_text=snapshot_text),
        }

    def _run_draconic_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 龙盘：各点黄经减北交点（交点归零）。后端把标准 chart-wrap 放在响应的 `chart` 键下——
        # 与 /astroextra/harmonic 同一形状，比导出层通用段构建器预期深一层，故同样摊平到顶层。
        response = self._call_remote("/astroextra/draconic", {**payload, "predictive": 0})
        chart_wrap = response.get("chart") if isinstance(response.get("chart"), dict) else {}
        # [龙盘] 专属段（v3.9.2 派生盘快照重定源）：龙首归零基准/位置/同频，逐字镜像
        # AstroDraconicLab.js:46-55；仅头一行（无位置无同频）不产段（上游 out.length > 1 同判）。
        lines: list[str] = []
        if response.get("nodeLon") is not None:
            # [Q-351/T-332]（AstroDraconicLab.js:4-7/53）注明真 / 平交点：本命盘 params.westNodeType === 'true' → 真交点，否则平交点。
            node_type = "真交点" if payload.get("westNodeType") in ("true", True) else "平交点"
            lines.append(f"北交点 {fmt_num(response['nodeLon'], 2)}°（{node_type}） → 归零白羊 0°（龙盘基准）")
        lines.extend(_derived_position_lines(response.get("positions"), "龙盘"))
        lines.extend(_derived_conjunction_lines(response.get("conjunctions")))
        return {
            **chart_wrap,
            "nodeLon": response.get("nodeLon"),
            "positions": response.get("positions", []),
            "conjunctions": response.get("conjunctions", []),
            "raw": response,
            **({"_derivedSelf": {"title": "龙盘", "lines": lines}} if lines else {}),
        }

    def _run_relocation_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 重置盘：出生 UT 不变，只按新经纬重算宫位与角点（行星黄经由 UT 决定故不变）。
        # 响应同 harmonic/draconic 的嵌套形状 → 同样摊平。relocLat/relocLon 缺省回退出生地。
        response = self._call_remote("/astroextra/relocation", {**payload, "predictive": 0})
        chart_wrap = response.get("chart") if isinstance(response.get("chart"), dict) else {}
        # [重置盘] 专属段（v3.9.2）：地点 + 四角对比，镜像 AstroRelocationLab.js:138-149。
        # 本命四角需另铸一张本命盘（上游用页面上已有的 props.value；headless 补一次 /chart）——
        # 上游同款 try 包裹：「角点缺省不产行」，本命盘取不到就只出地点行。
        lines = [
            f"重置地点：纬 {_reloc_display_degree(response.get('relocLat', payload.get('relocLat', payload.get('lat'))), lat=True)} / "
            f"经 {_reloc_display_degree(response.get('relocLon', payload.get('relocLon', payload.get('lon'))), lat=False)}"
        ]
        try:
            natal_payload = {k: v for k, v in payload.items() if k not in {"relocLat", "relocLon"}}
            natal = self._call_remote("/chart", {**natal_payload, "predictive": 0})
            natal_angles = _chart_angles(natal)
            reloc_angles = _chart_angles(chart_wrap)
            for angle_id in ("Asc", "MC", "Desc", "IC"):
                n, r = natal_angles.get(angle_id), reloc_angles.get(angle_id)
                if n or r:
                    lines.append(f"{angle_id}：本命 {_angle_text(n)} → 重置后 {_angle_text(r)}")
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
