"""推运 runner（PredictiveRunners）：年龄点、分配法、各类推运、星历、返照时间线、产前朔望、progextra 族、多重回归、129 年系统、波斯向运、法达、十年期。"""
from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from horosa_skill import predictive_text as _ptext
from horosa_skill.engine.astroextra_snapshots import (
    DEFAULT_MINOR_VARIANT,
    MINOR_VARIANT_LABEL,
    PROG_SNAPSHOT_VARIANTS,
    build_ephemeris_snapshot_text,
    build_prenatal_syzygy_snapshot_text,
    build_prog_snapshot_text,
    build_return_timeline_snapshot_text,
    split_syzygy_datetime,
)
from horosa_skill.engine.decennials import (
    DECENNIAL_CALENDAR_TRADITIONAL,
    DECENNIAL_DAY_METHOD_VALENS,
    DECENNIAL_ORDER_ZODIACAL,
    DECENNIAL_START_MODE_SECT_LIGHT,
    build_decennial_timeline,
)
from horosa_skill.engine.ephemeris_stations import correct_station_directions
from horosa_skill.errors import (
    HorosaSkillError,
    ToolTransportError,
    ToolValidationError,
)
from horosa_skill.service import _clock
from horosa_skill.service._common import _date_part_of, _finite_number, _require_option, _to_slash_date
from horosa_skill.service._context import _degrade
from horosa_skill.service.text.astro_core import _sign_degree
from horosa_skill.service.text.predictive import (
    _ARC_SOURCES,
    _PERSIAN_MAX_YEARS_OPTIONS,
    _PERSIAN_RATE,
    _PREDICTIVE_METHOD_NOTES,
    _TIME_LORD_YEAR_TYPES,
    _build_decennials_snapshot_text,
    _build_firdaria_snapshot_text,
    _build_jaynesprog_snapshot_text,
    _build_persianchart_section_text,
    _build_persiandirected_snapshot_text,
    _build_planetaryages_snapshot_text,
    _build_planetaryarc_snapshot_text,
    _planetaryarc_default_datetime,
    _today_for_chart,
    _wall_clock_for_chart,
)


class PredictiveRunners:
    # [起盘信息] 生辰行只要本命盘的这几项（上游 buildPredictiveBirthLines 读 params + chart.{dayofweek,nongli,
    # zodiacal,hsys,isDiurnal,siderealAyanamsa}）——只留这些，不把 ~170 KB 的整盘塞进响应。
    _NATAL_HEADER_CHART_KEYS = ("dayofweek", "nongli", "zodiacal", "hsys", "isDiurnal", "siderealAyanamsa")

    def _natal_header(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        """A 组星运键（agepoint/distributions/extrareturns：后端只回自家时间线、不带盘）补拉本命 /chart，
        供 [起盘信息]（上游 fetchChartResultForRecord → buildPredictiveBirthHeaderLines 同源）。
        拉取失败 → 降级为只用载荷的生辰行 + envelope 警告，不拖垮技法本身。"""
        natal_payload = {**payload, "predictive": 0}
        for key in ("datetime", "dirZone", "dirLat", "dirLon"):
            natal_payload.pop(key, None)
        try:
            natal = self._call_remote("/chart", natal_payload)
        except HorosaSkillError as exc:
            _degrade("predictive natal header fetch failed (tool=%s): %s", tool_name, exc)
            return None
        chart = natal.get("chart") if isinstance(natal.get("chart"), dict) else {}
        params = natal.get("params") if isinstance(natal.get("params"), dict) else {}
        header_chart = {key: chart.get(key) for key in self._NATAL_HEADER_CHART_KEYS if key in chart}
        # 极区天顶说明行（buildPredictiveBirthLines → polarMcOf(chart)）只读 houses[].polarMc：只带这一个字段。
        polar = [{"polarMc": h.get("polarMc")} for h in (chart.get("houses") or []) if isinstance(h, dict) and h.get("polarMc")]
        if polar:
            header_chart["houses"] = polar
        return {"params": params, "chart": header_chart}

    # 上游 v3.13.0 年龄推进点 / 界推运各四项口径（utils/agePointOptions.js · utils/distributionsOptions.js，与后端
    # agepoint.py / distributions.py、Java PredictiveController 白名单同名）。值域与 vendored 两份 options 文件互锚
    # （tests/test_sync313_predictive.py）。认不出就报错——上游 normalize 会静默回落出厂值，那正是本仓要防的形状。
    _PREDICT_RESULT_OPTION_DOMAINS: dict[str, dict[str, tuple[Any, ...]]] = {
        "agepoint": {
            "apMethod": ("koch", "equal5"),
            "apEvents": ("full", "conj"),
            "apYear": ("tropical", "sidereal"),
            "apMaxAge": (72, 100, 120, 144),
        },
        "distributions": {
            "distReleaser": (
                "Asc", "MC", "Desc", "IC", "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
                "Uranus", "Neptune", "Pluto", "North Node", "Vertex", "Pars Fortuna", "Spirit", "Syzygy",
            ),
            "distMethod": ("classical", "exact", "qisma"),
            "distYear": ("tropical", "egyptian", "julian"),
            "distYears": (60, 80, 100, 120, 150),
        },
    }
    # 出厂值（AP_DEFAULTS / DIST_DEFAULTS）：请求体只带与之不同的键（apRequestParams / distRequestParams 同律——缺省请求
    # 与旧版逐字节相同）。
    _PREDICT_RESULT_OPTION_DEFAULTS: dict[str, dict[str, Any]] = {
        "agepoint": {"apMethod": "koch", "apEvents": "full", "apYear": "tropical", "apMaxAge": 72},
        "distributions": {"distReleaser": "Asc", "distMethod": "classical", "distYear": "tropical", "distYears": 100},
    }

    def _predict_result_options(self, payload: dict[str, Any], technique: str) -> dict[str, Any]:
        options: dict[str, Any] = {}
        for field, allowed in self._PREDICT_RESULT_OPTION_DOMAINS[technique].items():
            value = payload.get(field)
            if value is None or value == "":
                continue
            if isinstance(allowed[0], int):
                number = _finite_number(value)
                value = int(number) if number is not None and number == int(number) else value
            _require_option(value, allowed, field=field, tool=technique)
            options[field] = value
        return options

    def _run_predict_result_tool(
        self, payload: dict[str, Any], technique: str, endpoint: str, fetch: Callable[[dict[str, Any]], dict[str, Any]]
    ) -> dict[str, Any]:
        """年龄推进点 / 界推运（上游 v3.13.0）：后端算时间线，vendored 上游 buildXxxSnapshotFromResult 排版。

        与上游无头路径同形（AstroAgePoint.js / AstroDistributions.js buildXxxSnapshotText）：请求体 = 本盘排盘参数 +
        与出厂值不同的口径键；结果交 builder(chartObj, r, opts)。builder 自带的 [当前时点] 定位行（当前年龄点 / 下一事件 /
        当前分配星 / 当前伙伴星）经 progextra 回传，[起盘信息]/[当前时点]/[方法说明] 由 Python 公共段出。
        """
        options = self._predict_result_options(payload, technique)
        defaults = self._PREDICT_RESULT_OPTION_DEFAULTS[technique]
        remote_payload = {key: value for key, value in payload.items() if key not in defaults}
        remote_payload["predictive"] = payload.get("predictive", 1)
        remote_payload.update({key: value for key, value in options.items() if value != defaults[key]})
        response = fetch(remote_payload)
        natal_header = self._natal_header(technique, payload)
        chart_obj = natal_header or _ptext.payload_chart_wrap(payload)
        try:
            js = self.js_client.run("progextra", self._progextra_payload(technique, chart_obj, options, response))
            snapshot_text, moment_lines, js_error = self._progextra_unpack(technique, js)
        except Exception as exc:
            _degrade("progextra JS engine failed (technique=%s): %s", technique, exc)
            snapshot_text, moment_lines, js_error = "", [], f"{exc}"
        if not snapshot_text:
            # 上游 builder 无数据返回 ''（挂载显示「缺失」）；skill 侧空快照会落 generated_template 假导出——一律报错（§5.9）。
            raise ToolValidationError(
                f"{endpoint} 没有返回可排版的{technique}时间线（上游此时显示「缺失」）{f'：{js_error}' if js_error else ''}"
                f" / {endpoint} returned no {technique} timeline to format",
                code=f"tool.{technique}_empty",
                details={"tool": technique, "endpoint": endpoint, "options": options, "js_error": js_error},
            )
        result: dict[str, Any] = {"options": options, "raw": response, "snapshot_text": snapshot_text}
        if technique == "agepoint":
            agepoint = response.get("agepoint") if isinstance(response.get("agepoint"), dict) else {}
            result.update({"agepoint": agepoint, "points": agepoint.get("points", [])})
        else:
            result.update({"distributions": response.get("dist", []), "partners": response.get("distPartners", [])})
        if natal_header:
            result["natalHeader"] = natal_header
        result["_moment_lines"] = moment_lines
        result["export_snapshot"] = self._augment_export_payload(technique=technique, snapshot_text=snapshot_text)
        return result

    def _run_agepoint_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 年龄推进点 (Age Point / Huber): backend /predict/agepoint computes the cycle; vendored upstream builder formats.
        return self._run_predict_result_tool(
            payload, "agepoint", "/predict/agepoint", lambda body: self._call_remote("/predict/agepoint", body)
        )

    def _run_distributions_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 界推运 (Distributions / 分配法): backend /predict/dist computes distributor + partner periods.
        return self._run_predict_result_tool(
            payload, "distributions", "/predict/dist", lambda body: self._call_remote("/predict/dist", body)
        )

    def _progression_target(self, payload: dict[str, Any]) -> dict[str, Any]:
        """目标时刻型推运（vedicprog/jaynesprog）的请求三键，缺省与上游 builder 同律（F10）：

        上游 AstroJaynesProgressions.js:37-39 / astroProgSnapshot.js:57-59：
        targetDate 缺省 today()（本地日期）、targetTime 缺省 12:00:00、minorVariant 缺省 synodic（[Q-180]，
        后端 progression_date 同缺省）。旧实现把 targetDate 缺省成**出生日**——推运零年、结果恒等本命，
        与上游和本仓自己的 guidance（「缺省=今天」）都不一致。
        """
        minor_variant = payload.get("minorVariant")
        if minor_variant is not None:
            _require_option(minor_variant, tuple(_ptext.MINOR_VARIANT_LABEL), field="minorVariant", tool="progression")
        return {
            # v3.12.0：缺省「今日」按本盘时区（astroProgSnapshot.js:18-21 today(chartZone(chartObj))）。
            "targetDate": f"{payload.get('targetDate') or _today_for_chart(payload.get('zone'))}".strip(),
            "targetTime": f"{payload.get('targetTime') or '12:00:00'}".strip(),
            "minorVariant": minor_variant or _ptext.DEFAULT_MINOR_VARIANT,
        }

    def _run_jaynesprog_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # Jayne 赤纬推运 (v2.5.0): /astroextra/jaynesprog — secondary progression + declination parallels.
        target = self._progression_target(payload)
        remote_payload = {**payload, **target, "orb": payload.get("orb", 1.0)}
        response = self._call_remote("/astroextra/jaynesprog", remote_payload)
        # 上游 [本命盘配置]（生辰 + 星与虚点 + 宫位宫头 + ◆ 本命赤纬）要本命盘——/astroextra/jaynesprog 只回推运结果。
        response = self._attach_predictive_chart_context("jaynesprog", payload, response)
        snapshot_text = _build_jaynesprog_snapshot_text(
            response, payload, target_date=target["targetDate"], target_time=target["targetTime"],
            minor_variant=target["minorVariant"],
        )
        return {
            "methods": response.get("methods", []),
            "target": target,
            "raw": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="jaynesprog", snapshot_text=snapshot_text),
        }

    def _run_vedicprog_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 恒星推运 Vedic (v2.5.0): /astroextra/progressions with zodiacal=1 (sidereal).
        target = self._progression_target(payload)
        remote_payload = {**payload, **target, "zodiacal": 1, "orb": payload.get("orb", 1.5)}
        response = self._call_remote("/astroextra/progressions", remote_payload)
        # execution="local" 的工具不走统一出口的 _attach_predictive_chart_context（那一支只对
        # remote 工具生效），所以这里显式补拉本命盘 —— [本命盘配置] 段要它。
        response = self._attach_predictive_chart_context("vedicprog", payload, response)
        # 与 prog 共用 engine/astroextra_snapshots.py 的逐字移植 builder（已对上游 astroProgSnapshot.js 逐字节核过；
        # 此前本仓有第二份 service 内移植，[本命盘配置] 还是 v3.11 前的逐行旧形——合并时去重）。
        natal = response.get("natalChart") if isinstance(response, dict) else None
        snapshot_text = build_prog_snapshot_text(
            natal if isinstance(natal, dict) else {},
            response,
            "vedicprog",
            target_date=target["targetDate"],
            target_time=target["targetTime"],
            minor_variant=target["minorVariant"],
            now=_clock.now(),
            method_notes=_PREDICTIVE_METHOD_NOTES["vedicprog"],
        )
        if not snapshot_text:
            raise ToolValidationError(
                "推运端点没有返回二次推运位置（上游此时显示「缺失」） / /astroextra/progressions returned no secondary positions",
                code="tool.vedicprog_empty",
                details={"tool": "vedicprog", "targetDate": target["targetDate"]},
            )
        return {
            "methods": response.get("methods", []),
            "target": target,
            "raw": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="vedicprog", snapshot_text=snapshot_text),
        }

    # ── 星运四键（上游 v3.11：[Q-106/T-10] 星历/回归轴/产前朔望三页 + [#80] 回归黄道二次推运）──────────────
    # 与上游无头路径 aiAnalysisContext.regenerateChartTechniqueSnapshot（:2956-2983）同形：先取本命盘
    # （chartObj——[起盘信息] 与 prog 的 [本命盘配置] 由它出），再以页面同一请求体（AstroExtraCommon.chartParams：
    # tradition / predictive 恒 false）打 /astroextra/*，最后交给 engine/astroextra_snapshots.py 的逐字移植 builder。
    # 上游 builder 求不得数据时返回 ''（挂载面显示「缺失」）；skill 侧空快照会落 generated_template 假导出，
    # 故一律抛结构化错误（AGENTS §5.9 勿静默回退）。本命盘 fetch 失败同样直接抛（没有它就没有 [起盘信息]）。
    _ASTROEXTRA_OPTION_KEYS = frozenset({
        "startDate", "endDate", "includeTransits", "eclipseTimeMode", "startYear", "count",
        "targetDate", "targetTime", "minorVariant",
    })

    def _astroextra_natal_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        natal = {key: value for key, value in payload.items() if key not in self._ASTROEXTRA_OPTION_KEYS}
        natal["predictive"] = 0
        for key in ("datetime", "dirZone", "dirLat", "dirLon"):
            natal.pop(key, None)
        return natal

    @staticmethod
    def _astroextra_chart_params(natal_payload: dict[str, Any]) -> dict[str, Any]:
        # AstroExtraCommon.chartParams（:126-150）：随本命盘透传，tradition / predictive 恒 false。
        return {**natal_payload, "tradition": False, "predictive": False}

    @staticmethod
    def _astroextra_date(payload: dict[str, Any], key: str, *, code: str) -> str | None:
        """YYYY-MM-DD（亦收 YYYY/MM/DD、单位数月日）→ 规范 YYYY-MM-DD；缺省/空 → None（走上游缺省）。"""
        raw = payload.get(key)
        text = f"{raw if raw is not None else ''}".strip()
        if not text:
            return None
        match = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", text)
        try:
            if not match:
                raise ValueError(text)
            value = datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            raise ToolValidationError(
                f"{key} 不是合法日期（要 YYYY-MM-DD）：{text!r} / {key} is not a valid date (expected YYYY-MM-DD): {text!r}",
                code=code,
                details={"field": key, "value": raw},
            ) from None
        return value.strftime("%Y-%m-%d")

    def _run_ephemeris_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        """星历（AstroEphemeris.buildEphemerisSnapshotText）：区间内入座/留逆/朔望弦/食相 + 行运触发本命。

        缺省窗 = 上游 defaultEphemerisWindow：今日起 90 天、含行运触发（startDate/endDate 各自缺省，与页面
        `{...defaults, ...opts}` 同语义）；eclipseTimeMode 是上游全局口径（缺省 max=食甚，非 max 才下发）。
        """
        natal_payload = self._astroextra_natal_payload(payload)
        natal = self._call_remote("/chart", natal_payload)
        # v3.12.0 defaultEphemerisWindow(zone)：「今日」按本盘时区钟面（DateTime.wallClockForChart；无时区 = 本机今日）。
        today = _wall_clock_for_chart(payload.get("zone"))
        start_date = self._astroextra_date(payload, "startDate", code="tool.ephemeris_invalid_window") or today.strftime("%Y-%m-%d")
        end_date = self._astroextra_date(payload, "endDate", code="tool.ephemeris_invalid_window") or (
            today + timedelta(days=90)
        ).strftime("%Y-%m-%d")
        if end_date < start_date:
            raise ToolValidationError(
                f"星历结束日早于开始日：{start_date} → {end_date}（只给 startDate 时 endDate 仍按上游缺省=今日+90天）"
                f" / ephemeris endDate precedes startDate: {start_date} → {end_date} (pass endDate too)",
                code="tool.ephemeris_invalid_window",
                details={"startDate": start_date, "endDate": end_date},
            )
        include_transits = payload.get("includeTransits") is not False
        eclipse_mode = f"{payload.get('eclipseTimeMode') or ''}".strip() or "max"
        if eclipse_mode not in {"max", "syzygy"}:
            raise ToolValidationError(
                f"eclipseTimeMode 只能是 max（食甚时刻）或 syzygy（精确朔望）：{eclipse_mode!r}"
                f" / eclipseTimeMode must be 'max' or 'syzygy': {eclipse_mode!r}",
                code="tool.ephemeris_invalid_option",
                details={"field": "eclipseTimeMode", "value": eclipse_mode, "allowed": ["max", "syzygy"]},
            )
        body = {
            **self._astroextra_chart_params(natal_payload),
            "startDate": start_date,
            "endDate": end_date,
            "includeTransits": include_transits,
        }
        if eclipse_mode != "max":
            body["eclipseTimeMode"] = eclipse_mode
        response = self._call_remote("/astroextra/ephemeris", body)
        if isinstance(response, dict) and isinstance(response.get("stations"), list):
            # 本仓声明式偏离（v0.40.0）：上游按留点那一刻≈0 的速度正负定顺逆，标签是浮点噪声；改按同一响应的逐日速度复核
            # （engine/ephemeris_stations.py）。判不出的留保留上游标签并明示。
            stations, unresolved = correct_station_directions(response.get("stations"), response.get("dailyPositions"))
            if unresolved:
                _degrade(
                    "ephemeris: %d station direction(s) could not be re-derived from dailyPositions; upstream labels kept",
                    len(unresolved),
                    note=f"降级：{len(unresolved)} 个留的顺逆方向无法按逐日速度复核，沿用上游标签（上游按留点时刻≈0 的速度正负定，可能不准）。",
                )
            response = {**response, "stations": stations}
        snapshot_text = build_ephemeris_snapshot_text(
            natal,
            response,
            start_date=start_date,
            end_date=end_date,
            include_transits=include_transits,
            now=_clock.now(),
            method_notes=_PREDICTIVE_METHOD_NOTES["ephemeris"],
        )
        if not snapshot_text:
            raise ToolValidationError(
                f"星历区间 {start_date} 至 {end_date} 内没有任何可列事件（入座/留逆/朔望弦/食相/行运触发皆空；上游此时显示「缺失」）"
                f" / no ephemeris events in {start_date}..{end_date} — widen the window",
                code="tool.ephemeris_empty",
                details={"startDate": start_date, "endDate": end_date, "endpoint": "/astroextra/ephemeris"},
            )
        # data 只带 builder 实际消费的事件表（每日位置/升落现象是页面专属 tab，不进上游 AI 导出；整份 ~0.4 MB）。
        return {
            "window": {
                "startDate": start_date,
                "endDate": end_date,
                "includeTransits": include_transits,
                "eclipseTimeMode": eclipse_mode,
            },
            "ephemeris": {
                key: response.get(key)
                for key in ("params", "ingresses", "stations", "lunarPhases", "eclipses", "transitAspects")
            },
            "natal_params": natal.get("params"),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="ephemeris", snapshot_text=snapshot_text),
        }

    def _run_returntimeline_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        """回归轴（AstroReturnTimeline.buildReturnTimelineSnapshotText）：逐年太阳返照 + 该年首个月亮返照 + 两盘上升。

        缺省 = 上游 `{startYear: 今年, count: 12}`；后端把 count 夹到 1–40，页面输入框同界——越界直接报错，
        免得段头写「50 年」而表里只有 40 行。
        """
        natal_payload = self._astroextra_natal_payload(payload)
        natal = self._call_remote("/chart", natal_payload)
        start_year = payload.get("startYear")
        if start_year in (None, "", 0):
            # v3.12.0 AstroReturnTimeline.js:18：「今年」按本盘时区钟面（DateTime.wallClockForChart）。
            start_year = _wall_clock_for_chart(payload.get("zone")).year
        count = payload.get("count")
        if count in (None, "", 0):
            count = 12
        try:
            start_year = int(start_year)
            count = int(count)
        except (TypeError, ValueError):
            raise ToolValidationError(
                f"startYear / count 必须是整数：{start_year!r} / {count!r} / startYear and count must be integers",
                code="tool.returntimeline_invalid_range",
                details={"startYear": start_year, "count": count},
            ) from None
        if not 1 <= count <= 40:
            raise ToolValidationError(
                f"回归轴年数 count 须在 1–40 之间（后端上限 40）：{count} / count must be within 1–40 (backend clamp): {count}",
                code="tool.returntimeline_invalid_range",
                details={"count": count, "min": 1, "max": 40},
            )
        body = {**self._astroextra_chart_params(natal_payload), "startYear": start_year, "count": count}
        response = self._call_remote("/astroextra/returns", body)
        rows = response.get("rows")
        if not isinstance(rows, list):
            raise ToolTransportError(
                "回归轴端点返回了意外形状（缺 rows 数组） / /astroextra/returns returned an unexpected shape (no rows list)",
                code="transport.invalid_result_shape",
                details={"endpoint": "/astroextra/returns", "keys": sorted(response)},
            )
        snapshot_text = build_return_timeline_snapshot_text(
            natal,
            rows,
            start_year=start_year,
            count=count,
            now=_clock.now(),
            method_notes=_PREDICTIVE_METHOD_NOTES["returntimeline"],
        )
        if not snapshot_text:
            raise ToolValidationError(
                f"回归轴没有返回任何年份行（startYear={start_year}, count={count}） / the return timeline returned no rows",
                code="tool.returntimeline_empty",
                details={"startYear": start_year, "count": count, "endpoint": "/astroextra/returns"},
            )
        return {
            "range": {"startYear": start_year, "count": count},
            "rows": rows,
            "natal_params": natal.get("params"),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="returntimeline", snapshot_text=snapshot_text),
        }

    def _run_prenatalsyzygy_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        """产前朔望（AstroPrenatalSyzygy.buildPrenatalSyzygySnapshotText）：回溯最近朔/望 + 以该时刻、出生地起盘。

        第二张盘（朔望时刻 /chart）取不到时上游照出段并写「暂缺」行——同样照写，另经 _degrade 进 envelope.warnings。
        """
        natal_payload = self._astroextra_natal_payload(payload)
        natal = self._call_remote("/chart", natal_payload)
        base = self._astroextra_chart_params(natal_payload)
        syzygy = self._call_remote("/astroextra/prenatal_syzygy", base)
        if not syzygy.get("type"):
            raise ToolValidationError(
                "未能求得产前朔望（极区或星历不可用；上游此时显示「缺失」） / prenatal syzygy could not be solved "
                "(polar latitude or ephemeris unavailable)",
                code="tool.prenatalsyzygy_unavailable",
                details={"endpoint": "/astroextra/prenatal_syzygy", "result": syzygy},
            )
        syzygy_chart: dict[str, Any] | None = None
        moment = split_syzygy_datetime(syzygy.get("datetime"))
        if moment is None:
            _degrade("prenatalsyzygy: 朔望结果缺 datetime，无法以朔望时刻排盘（[产前朔望盘·星体位置] 写「暂缺」行）")
        else:
            try:
                syzygy_chart = self._call_remote("/chart", {**base, "date": moment["date"], "time": moment["time"]})
            except HorosaSkillError as exc:
                _degrade("prenatalsyzygy: 以朔望时刻排盘失败（[产前朔望盘·星体位置] 写「暂缺」行）: %s", exc)
        snapshot_text = build_prenatal_syzygy_snapshot_text(
            natal,
            syzygy,
            syzygy_chart,
            now=_clock.now(),
            method_notes=_PREDICTIVE_METHOD_NOTES["prenatalsyzygy"],
        )
        syzygy_objects = []
        chart_body = syzygy_chart.get("chart") if isinstance(syzygy_chart, dict) else None
        for obj in (chart_body.get("objects") if isinstance(chart_body, dict) else None) or []:
            if isinstance(obj, dict) and obj.get("id"):
                syzygy_objects.append({key: obj.get(key) for key in ("id", "sign", "signlon", "lon") if key in obj})
        return {
            "syzygy": syzygy,
            "syzygy_chart": {
                "params": syzygy_chart.get("params") if isinstance(syzygy_chart, dict) else None,
                "objects": syzygy_objects,
            },
            "natal_params": natal.get("params"),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="prenatalsyzygy", snapshot_text=snapshot_text),
        }

    def _run_prog_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        """二次推运·回归黄道（astroProgSnapshot.buildProgSnapshotText variant 'prog'）。

        与 vedicprog 同一后端 /astroextra/progressions、同一 builder 族；本支**不下发 zodiacal 覆写**（随盘自身黄道，
        上游 PROG_SNAPSHOT_VARIANTS.prog.zodiacal = null）。缺省 = 上游 targetDate 今天 / targetTime 12:00:00 /
        minorVariant synodic；orb 上游写死 1.5。`datetime`（YYYY-MM-DD HH:MM:SS）只在没给 targetDate 时作目标时刻用
        （后端 build_progressions 的同一回退顺序），目标日期行照实写出，不静默吞。
        """
        natal_payload = self._astroextra_natal_payload(payload)
        natal = self._call_remote("/chart", natal_payload)
        target_date = self._astroextra_date(payload, "targetDate", code="tool.prog_invalid_option")
        target_time_raw = f"{payload.get('targetTime') or ''}".strip()
        if target_date is None and payload.get("datetime"):
            parts = f"{payload['datetime']}".strip().replace("T", " ").split(" ")
            target_date = self._astroextra_date({"datetime": parts[0]}, "datetime", code="tool.prog_invalid_option")
            if not target_time_raw and len(parts) > 1:
                target_time_raw = parts[1]
        target_date = target_date or _today_for_chart(payload.get("zone"))  # v3.12.0：今日按本盘时区
        target_time = "12:00:00"
        if target_time_raw:
            time_match = re.fullmatch(r"(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?", target_time_raw)
            if not time_match or int(time_match.group(1)) > 23 or int(time_match.group(2)) > 59 or int(time_match.group(3) or 0) > 59:
                raise ToolValidationError(
                    f"targetTime 不是合法时刻（要 HH:MM[:SS]）：{target_time_raw!r} / targetTime must be HH:MM[:SS]: {target_time_raw!r}",
                    code="tool.prog_invalid_option",
                    details={"field": "targetTime", "value": target_time_raw},
                )
            target_time = f"{int(time_match.group(1)):02d}:{int(time_match.group(2)):02d}:{int(time_match.group(3) or 0):02d}"
        minor_variant = f"{payload.get('minorVariant') or ''}".strip() or DEFAULT_MINOR_VARIANT
        if minor_variant not in MINOR_VARIANT_LABEL:
            raise ToolValidationError(
                f"minorVariant 只能是 {'/'.join(MINOR_VARIANT_LABEL)}：{minor_variant!r}"
                f" / minorVariant must be one of {', '.join(MINOR_VARIANT_LABEL)}: {minor_variant!r}",
                code="tool.prog_invalid_option",
                details={"field": "minorVariant", "value": minor_variant, "allowed": list(MINOR_VARIANT_LABEL)},
            )
        body = {
            **self._astroextra_chart_params(natal_payload),
            "targetDate": target_date,
            "targetTime": target_time,
            "minorVariant": minor_variant,
            "orb": 1.5,
        }
        variant_zodiacal = PROG_SNAPSHOT_VARIANTS["prog"]["zodiacal"]
        if variant_zodiacal:
            body["zodiacal"] = variant_zodiacal
        response = self._call_remote("/astroextra/progressions", body)
        snapshot_text = build_prog_snapshot_text(
            natal,
            response,
            "prog",
            target_date=target_date,
            target_time=target_time,
            minor_variant=minor_variant,
            now=_clock.now(),
            method_notes=_PREDICTIVE_METHOD_NOTES["prog"],
        )
        if not snapshot_text:
            raise ToolValidationError(
                "推运端点没有返回二次推运位置（上游此时显示「缺失」） / /astroextra/progressions returned no secondary positions",
                code="tool.prog_empty",
                details={"endpoint": "/astroextra/progressions", "targetDate": target_date, "targetTime": target_time},
            )
        return {
            "target": {"targetDate": target_date, "targetTime": target_time, "minorVariant": minor_variant},
            "methods": response.get("methods", []),
            "ageDays": response.get("ageDays"),
            "natal_params": natal.get("params"),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="prog", snapshot_text=snapshot_text),
        }

    def _run_planetaryarc_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 行星弧 (v2.5.0): /predict/planetaryarc — directs the whole chart by the arc of arcSource (default Moon).
        # F10：目标时刻缺省 = 上游 todayStr()（明天此刻，AstroPlanetaryArc.js:46）；旧实现缺省成**出生日**（零弧）。
        arc_source = payload.get("arcSource", "Moon")
        _require_option(arc_source, _ARC_SOURCES, field="arcSource", tool="planetaryarc")
        remote_payload = {
            **payload,
            "datetime": payload.get("datetime") or payload.get("targetDate") or _planetaryarc_default_datetime(zone=payload.get("zone")),
            "asporb": payload.get("asporb", 1),
            "arcSource": arc_source,
        }
        response = self._call_remote("/predict/planetaryarc", remote_payload)
        # 后端随回的 natalChart 只有 {hsys,houses,objects,isDiurnal}：无 params/星期/黄道，也无本命 lots——
        # 旧实现经 _as_chart_wrap 的 fallback_lots 把顶层的**向运** lots 当本命 lots 印进 [本命盘配置]。
        # 上游 formatArcSnapshot 的本命块读的是真本命 chartObj（buildPredictiveBirthLines + 星与虚点 + 宫位宫头），
        # 故补拉本命 /chart 顶替之；拉取失败则退回后端那份（_degrade 已留警告）。
        natal_payload = {**payload, "predictive": 0}
        for key in ("datetime", "dirZone", "dirLat", "dirLon"):
            natal_payload.pop(key, None)
        try:
            response = {**response, "natalChart": self._call_remote("/chart", natal_payload)}
        except HorosaSkillError as exc:
            _degrade("planetaryarc natal chart fetch failed: %s", exc)
        snapshot_text = _build_planetaryarc_snapshot_text(response, payload)
        return {
            "chart": response.get("chart"),
            "target": {"datetime": remote_payload["datetime"], "arcSource": arc_source},
            "raw": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="planetaryarc", snapshot_text=snapshot_text),
        }

    def _run_planetaryages_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 行星年龄 (v2.5.0): Ptolemy seven ages of man — reads the natal chart, marks the current band.
        chart_payload = {**payload, "predictive": 0}
        response = self._call_remote("/chart", chart_payload)
        as_of = payload.get("asOf") or payload.get("targetDate")
        moment_lines: list[str] = []
        snapshot_text = _build_planetaryages_snapshot_text(response, as_of, moment_lines=moment_lines)
        return {
            "_moment_lines": moment_lines,
            "chart": response.get("chart"),
            "raw": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="planetaryages", snapshot_text=snapshot_text),
        }

    # F7：上游挂载齿轮（techniqueMountSettings.js:1237-1274）→ builder opts 的键与值域（aiAnalysisContext.js:2998-3013
    # regen 传的就是这几键）。值域抄 vendored builder 自己的常量表（balbillus.js BALBILLUS_YEAR_TYPES/MODES、
    # triplicityRulers.js TRIPLICITY_SYSTEMS/DIVISIONS、keypoints120.js RELEASE_MODES）——认不出就报错，
    # 不像 builder 那样静默回落缺省。
    _PROGEXTRA_OPTION_DOMAINS: dict[str, dict[str, tuple[str, ...]]] = {
        "balbillus": {
            "startPlanet": ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"),
            # 上游 v3.13.0：年制扩成 utils/timeLordYears.js TIME_LORD_YEAR_TYPES 六档（与 129 年系统共用一张表）。
            "yearType": _TIME_LORD_YEAR_TYPES,
            "mode": ("nearest", "forward"),
            # 上游 v3.13.0 新增子限铺法（balbillus.js BALBILLUS_SUB_RULES；缺省 once）。
            "subRule": ("once", "cycle", "fill"),
        },
        "triplicityrulers": {
            "system": ("Dorothean", "Ptolemaic", "PtolemaicWaterVariant"),
            "division": ("thirds", "halves"),
        },
        "keypoints": {"mode": ("soul", "body")},
        # 上游 v3.13.0 utils/yearSystem129.js:33-46（YS129_START_OPTIONS / YS129_ORDERS / YS129_YEAR_TYPES /
        # YS129_SUB_RULES）。入参键带 ys129 前缀（= 上游页面保存键与挂载齿轮键，techniqueMountSettings.js:1509-1518），
        # 下发给 builder 时按 _PROGEXTRA_OPTION_KEYS 换成 opts 键（regenChart.js:263-267 同一映射）。
        "yearsystem129": {
            "ys129StartPlanet": ("sect", "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"),
            "ys129Order": ("zodiacal", "chaldean"),
            "ys129YearType": _TIME_LORD_YEAR_TYPES,
            "ys129SubRule": ("days", "proportional", "equal"),
        },
    }
    # 入参键 → builder opts 键（未列 = 同名）。
    _PROGEXTRA_OPTION_KEYS: dict[str, dict[str, str]] = {
        "yearsystem129": {
            "ys129StartPlanet": "startPlanet", "ys129Order": "order", "ys129YearType": "yearType", "ys129SubRule": "subRule",
        },
    }
    # triplicityrulers.lifespan：上游齿轮 number 30–120（缺省 75）。
    _TRIPLICITY_LIFESPAN_RANGE = (30, 120)

    def _progextra_options(self, payload: dict[str, Any], technique: str) -> dict[str, Any]:
        options: dict[str, Any] = {}
        for field, allowed in self._PROGEXTRA_OPTION_DOMAINS.get(technique, {}).items():
            value = payload.get(field)
            if value is None:
                continue
            _require_option(value, allowed, field=field, tool=technique)
            options[self._PROGEXTRA_OPTION_KEYS.get(technique, {}).get(field, field)] = value
        if technique == "triplicityrulers" and payload.get("lifespan") is not None:
            lifespan = _finite_number(payload.get("lifespan"))
            low, high = self._TRIPLICITY_LIFESPAN_RANGE
            if lifespan is None or not low <= lifespan <= high:
                raise ToolValidationError(
                    f"triplicityrulers 的 lifespan={payload.get('lifespan')!r} 须在 {low}–{high} 之间 / "
                    f"lifespan must be a number within {low}-{high}.",
                    code="tool.predictive_invalid_option",
                    details={"tool": technique, "field": "lifespan", "value": payload.get("lifespan"), "allowed": [low, high]},
                )
            options["lifespan"] = lifespan
        return options

    @staticmethod
    def _progextra_payload(
        technique: str, chart: dict[str, Any], options: dict[str, Any], result: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """horosa-core-js progextra 的入参。`now_ms` 把服务层的「此刻」（`_clock.now()`，测试可冻结）交给 JS：builder 的
        定位行（当前主限 / 当前年龄点 / 当前分配星…）按 `Date.now()` 算，progextra 在调用期间把它钉到这个瞬时——
        与 Python 侧 [当前时点] 同一个「此刻」。"""
        payload: dict[str, Any] = {
            "technique": technique, "chart": chart, "options": options,
            "now_ms": int(_clock.now().astimezone().timestamp() * 1000),
        }
        if result is not None:
            payload["result"] = result
        return payload

    @staticmethod
    def _progextra_unpack(technique: str, js: Any) -> tuple[str, list[str], str]:
        """progextra 回包 → (snapshot_text, [当前时点] 定位行, 失败原因)；builder 失败经 _degrade 进 envelope 警告。"""
        if not isinstance(js, dict):
            return "", [], "progextra returned a non-object"
        # builder 自算的 [当前时点] 定位行（当前主限 / 当前所处阶段 / 当前推运月相…）。
        moment_lines = [f"{line}" for line in (js.get("moment_lines") or []) if line]
        js_data = js.get("data") if isinstance(js.get("data"), dict) else {}
        error = ""
        if js_data.get("ok") is False:
            error = f"{js_data.get('reason') or ''} {js_data.get('error') or ''}".strip()
            _degrade("progextra builder failed (technique=%s): %s", technique, error)
        return f"{js.get('snapshot_text') or ''}".strip(), moment_lines, error

    def _run_progextra_js_tool(self, payload: dict[str, Any], technique: str) -> dict[str, Any]:
        # v2.5.0 推运 builders that are too algorithm-heavy to re-port (balbillus 129年旺距削减 / persiandirected /
        # yearsystem129): cast the natal /chart, then run the vendored 星阙 frontend builder via horosa-core-js,
        # which emits the single-section snapshot text directly.
        options = self._progextra_options(payload, technique)
        chart_payload = {**payload, "predictive": 0}
        chart_payload.pop("datetime", None)
        chart_payload.pop("dirZone", None)
        chart_payload.pop("dirLat", None)
        chart_payload.pop("dirLon", None)
        response = self._call_remote("/chart", chart_payload)
        snapshot_text, moment_lines = "", []
        try:
            js = self.js_client.run("progextra", self._progextra_payload(technique, response, options))
            snapshot_text, moment_lines, _ = self._progextra_unpack(technique, js)
        except Exception as exc:
            _degrade("progextra JS engine failed (technique=%s): %s", technique, exc)
        return {
            "chart": response.get("chart"),
            "options": options,
            "_moment_lines": moment_lines,
            "raw": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique=technique, snapshot_text=snapshot_text),
        }

    def _run_balbillus_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # Balbillus 129年系统（旺距削减）: vendored JS builder (see horosa-core-js progextra).
        return self._run_progextra_js_tool(payload, "balbillus")

    # 多重回归 (星阙 v2.6.x): 土/木/月交三体返照。上游前端 buildExtraReturnsSnapshotText 是「请求型」——
    # 逐体拉 /astroextra/planetreturn。skill 把这三次后端调用放在 Python 侧（headless JS 不发 HTTP），
    # 再按上游同格式拼 [多重回归] 段。
    _EXTRARETURNS_BODIES = (("Saturn", "土星返照", "≈29.5 年"), ("Jupiter", "木星返照", "≈11.9 年"), ("Node", "月交返照", "≈18.6 年"))

    # 上游 components/astro/AstroExtraReturns.js:40：导出取 5 回（与组件 state.count=5 对齐；此前 4 回是上游已修的 bug）。
    _EXTRARETURNS_COUNT = 5

    @staticmethod
    def _extrareturns_node_type_text(natal_params: dict[str, Any] | None, payload: dict[str, Any]) -> str:
        """上游 AstroExtraReturns.js:44-48 nodeTypeText(chartObj)：本盘 westNodeType / guolaoNodeType 为 'true' → 真交点，
        否则平交点（缺省）。chartObj.params 取本命 /chart 回显，回显缺键时退回请求载荷（同一组排盘参数）。"""
        params = natal_params if isinstance(natal_params, dict) else {}

        def pick(key: str) -> Any:
            return params.get(key) if params.get(key) is not None else payload.get(key)

        return "真交点" if pick("westNodeType") == "true" or pick("guolaoNodeType") == "true" else "平交点"

    @staticmethod
    def _extrareturns_body_line(cn: str, period: str, resp: dict[str, Any], rows: list[dict[str, Any]], node_txt: str = "") -> str:
        """逐字镜像上游 AstroExtraReturns.js:72-82（v3.13.0）的每体一行。

        [Q-366/T-345] 后端同一回列全部逆行三过（passes，顺→逆→顺）：>1 过时写 `第N回 d1/d2(逆)/d3`，
        单过仍是一个日期；行尾追加各回时刻 + 本命黄经（toFixed(1)，与 UI 同口径）。v3.13.0：后端在星历范围外求不到的回
        带 `found: false` → 日期格写「范围内未找到」、时刻格写「-」；月交行在体名后标（真交点）/（平交点）。
        """
        def passes_of(row: dict[str, Any]) -> list[Any]:
            passes = row.get("passes")
            return passes if isinstance(passes, list) else []

        def dates_cell(row: dict[str, Any]) -> str:
            if row.get("found") is False:
                return f"第{_ptext.js_str(row.get('which'))}回 范围内未找到"
            passes = passes_of(row)
            if len(passes) > 1:
                joined = "/".join(
                    f"{pp.get('date')}{'(逆)' if pp.get('retrograde') else ''}" for pp in passes if isinstance(pp, dict)
                )
                return f"第{_ptext.js_str(row.get('which'))}回 {joined}"
            return f"第{_ptext.js_str(row.get('which'))}回 {row.get('date')}"

        dates_txt = "，".join(dates_cell(row) for row in rows)
        times_txt = "，".join(
            f"第{_ptext.js_str(row.get('which'))}回 {'-' if row.get('found') is False else (row.get('time') or '-')}" for row in rows
        )
        natal_lon = resp.get("natalLon")
        natal_lon_txt = f"；本命黄经 {_ptext.js_to_fixed(natal_lon, 1)}°" if natal_lon is not None else ""
        node = f"（{node_txt}）" if node_txt else ""
        return f"{cn}{node}（{period}）：{dates_txt}；时刻：{times_txt}{natal_lon_txt}"

    def _run_extrareturns_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        remote_base = {**payload, "predictive": 0}
        for key in ("datetime", "dirZone", "dirLat", "dirLon"):
            remote_base.pop(key, None)
        lines = ["[多重回归]"]
        # 本命盘先取（[起盘信息] + 月交行的真/平交点标注都读它；上游 chartObj 同一份）。
        natal_header = self._natal_header("extrareturns", payload)
        node_txt = self._extrareturns_node_type_text((natal_header or {}).get("params"), payload)
        for body_key, cn, period in self._EXTRARETURNS_BODIES:
            try:
                resp = self._call_remote(
                    "/astroextra/planetreturn", {**remote_base, "body": body_key, "count": self._EXTRARETURNS_COUNT}
                )
            except Exception as exc:
                _degrade("extrareturns planetreturn failed (body=%s): %s", body_key, exc)
                continue
            rows = resp.get("returns") if isinstance(resp, dict) else None
            if not isinstance(rows, list) or not rows:
                continue
            rows = [r for r in rows if isinstance(r, dict)]
            if rows:
                lines.append(self._extrareturns_body_line(cn, period, resp, rows, node_txt if body_key == "Node" else ""))
        snapshot_text = "\n".join(lines) if len(lines) > 1 else ""
        result: dict[str, Any] = {}
        if natal_header:
            result["natalHeader"] = natal_header
        # [日月返照年表]（v0.33.0 批 I-3，/astroextra/returns）：逐年日返/月返精确时刻 + 返照上升。
        # 条件段：给 timelineStartYear/timelineCount 才产，零回归。
        if payload.get("timelineStartYear") is not None or payload.get("timelineCount") is not None:
            timeline_remote = {**remote_base}
            if payload.get("timelineStartYear") is not None:
                timeline_remote["startYear"] = payload.get("timelineStartYear")
            if payload.get("timelineCount") is not None:
                timeline_remote["count"] = payload.get("timelineCount")
            timeline = self._call_remote("/astroextra/returns", timeline_remote)
            t_rows = timeline.get("rows") if isinstance(timeline, dict) else None
            if not isinstance(t_rows, list):
                raise ToolTransportError(
                    "日月返照年表端点返回了意外形状。",
                    code="tool.extrareturns_timeline_failed",
                    details={"endpoint": "/astroextra/returns"},
                )
            result["timeline"] = t_rows
            timeline_lines = ["[日月返照年表]"]
            for row in t_rows:
                if not isinstance(row, dict):
                    continue
                solar = row.get("solarReturn") if isinstance(row.get("solarReturn"), dict) else {}
                lunar = row.get("lunarReturn") if isinstance(row.get("lunarReturn"), dict) else {}
                solar_asc = row.get("solarAsc") if isinstance(row.get("solarAsc"), dict) else {}
                lunar_asc = row.get("lunarAsc") if isinstance(row.get("lunarAsc"), dict) else {}
                bits = [f"{row.get('year')}："]
                if solar.get("datetime"):
                    asc_txt = f"（升 {_sign_degree(solar_asc.get('lon'))}）" if solar_asc.get("lon") is not None else ""
                    bits.append(f"日返 {solar.get('datetime')}{asc_txt}")
                if lunar.get("datetime"):
                    asc_txt = f"（升 {_sign_degree(lunar_asc.get('lon'))}）" if lunar_asc.get("lon") is not None else ""
                    bits.append(f"　首月返 {lunar.get('datetime')}{asc_txt}")
                timeline_lines.append("".join(bits))
            section = "\n".join(timeline_lines)
            snapshot_text = f"{snapshot_text}\n\n{section}" if snapshot_text else section
        result["snapshot_text"] = snapshot_text
        result["export_snapshot"] = self._augment_export_payload(technique="extrareturns", snapshot_text=snapshot_text)
        return result

    def _run_yearsystem129_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 129 年系统：上游 v3.13.0 删了后端 astrostudy/yearsystem129.py（/chart 不再回 predictives.yearsystem129——
        # 旧 runner 读这个字段，于是恒出「本盘无数据」）。现由 vendored 上游 utils/yearSystem129.js 在本命盘上推算
        # （horosa-core-js progextra），起始星 / 次序 / 年制 / 子限铺法四项经 ys129* 入参下发。
        return self._run_progextra_js_tool(payload, "yearsystem129")

    @staticmethod
    def _persian_target_datetime(payload: dict[str, Any]) -> str:
        """datetime → 'YYYY-MM-DD HH:mm:ss'；只给日期补正午（与上游 predict 面板日期选择同义）。
        「只有日期」按日期段整串判（公元前 '-0450-03-21' 11 个字符、五位年 12 个——旧 len()==10 判不出、不补正午）。"""
        target = str(payload.get("datetime") or "").strip().replace("/", "-").replace("T", " ")
        if target and _date_part_of(target) == target:
            target = f"{target} 12:00:00"
        return target

    def _run_persiandirected_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 波斯向运 (Persian Directed)：纯算术读本命盘 objects/houses/birth（上游 AstroPersianDirected.js）。
        # F6（上游 v3.11 [Q-168/T-102]）：主表此前写死 1°/年·顺向·90 年，声明的 rateKey/direction 只进了
        # 可选的指定日期盘；现在 rateKey/direction/maxYears 同时驱动主表（= 上游 builder opts）。
        rate_key = payload.get("rateKey")
        direction = payload.get("direction")
        max_years = payload.get("maxYears")
        if rate_key is not None:
            _require_option(rate_key, tuple(_PERSIAN_RATE), field="rateKey", tool="persiandirected")
        if direction is not None:
            _require_option(direction, ("direct", "converse"), field="direction", tool="persiandirected")
        if max_years is not None:
            number = _finite_number(max_years)
            if number is None or number <= 0:
                raise ToolValidationError(
                    f"persiandirected 的 maxYears={max_years!r} 必须为正数 / maxYears must be a positive number "
                    f"(上游齿轮五档 {list(_PERSIAN_MAX_YEARS_OPTIONS)})。",
                    code="tool.predictive_invalid_option",
                    details={"tool": "persiandirected", "field": "maxYears", "value": max_years,
                             "allowed": list(_PERSIAN_MAX_YEARS_OPTIONS)},
                )
        chart_payload = {**payload, "predictive": 0}
        chart_payload.pop("datetime", None)
        chart_payload.pop("dirZone", None)
        response = self._call_remote("/chart", chart_payload)
        target = self._persian_target_datetime(payload) if payload.get("datetime") else ""
        moment_lines: list[str] = []
        snapshot_text = _build_persiandirected_snapshot_text(
            response,
            {"rateKey": rate_key, "direction": direction, "maxYears": max_years, "datetime": target},
            moment_lines=moment_lines,
        )
        result: dict[str, Any] = {
            "chart": response.get("chart"),
            "raw": response,
            "_moment_lines": moment_lines,
        }
        # [指定日期向运盘]（v0.33.0 批 I-2）：datetime 时后端整铸该日向运盘（/predict/persianchart，
        # getPersianDirectedByDate）。条件段：缺省不产，零回归。
        if payload.get("datetime"):
            directed = self._persianchart_by_date(payload)
            result["directed_chart"] = directed
            section = _build_persianchart_section_text(directed)
            if snapshot_text and section:
                snapshot_text = f"{snapshot_text}\n\n{section}"
        result["snapshot_text"] = snapshot_text
        result["export_snapshot"] = self._augment_export_payload(
            technique="persiandirected", snapshot_text=snapshot_text
        )
        return result

    def _persianchart_by_date(self, payload: dict[str, Any]) -> dict[str, Any]:
        # toSlashDate：只换数字之间的 '-'（旧 replace("-", "/") 连公元前前导负号一起换掉）
        target = _to_slash_date(self._persian_target_datetime(payload))
        remote = {**payload, "datetime": target, "predictive": 0}
        # 上游 v3.11 [Q-173]：/predict/persianchart 按 dirZone 解释目标时刻（空则本命时区）——dirZone 必须透传，
        # 不能再剥（旧实现剥掉 = 撤销上游「按所选时区」修正）。
        for key in ("rateKey", "direction", "nodeRetrograde", "dirZone"):
            if payload.get(key) is None:
                remote.pop(key, None)
        return self._call_remote("/predict/persianchart", remote)

    def _run_firdaria_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        remote_payload = {**payload, "predictive": True}
        response = self._call_remote("/chart", remote_payload)
        snapshot_text = _build_firdaria_snapshot_text(response)
        result = {
            "chart": response.get("chart"),
            "params": response.get("params", remote_payload),
            "predictives": response.get("predictives", {}),
            "firdaria": response.get("predictives", {}).get("firdaria", {}) if isinstance(response.get("predictives"), dict) else [],
            "snapshot_text": snapshot_text,
        }
        result["export_snapshot"] = self._augment_export_payload(technique="firdaria", snapshot_text=snapshot_text)
        return result

    def _run_decennials_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        remote_payload = {**payload, "predictive": True}
        response = self._call_remote("/chart", remote_payload)
        response = dict(response)
        if "params" not in response or not isinstance(response.get("params"), dict):
            response["params"] = remote_payload
        settings = {
            "startMode": payload.get("startMode", DECENNIAL_START_MODE_SECT_LIGHT),
            "orderType": payload.get("orderType", DECENNIAL_ORDER_ZODIACAL),
            "dayMethod": payload.get("dayMethod", DECENNIAL_DAY_METHOD_VALENS),
            "calendarType": payload.get("calendarType", DECENNIAL_CALENDAR_TRADITIONAL),
        }
        ai_state = {
            "aiMode": payload.get("aiMode", "l1_all"),
            "aiL1Idx": payload.get("aiL1Idx", 0),
            "aiL2Idx": payload.get("aiL2Idx", 0),
            "aiL3Idx": payload.get("aiL3Idx", 0),
        }
        timeline = build_decennial_timeline(response, settings)
        snapshot_holder = {"chart": response.get("chart"), "params": response.get("params"), "timeline": timeline}
        snapshot_text = _build_decennials_snapshot_text(snapshot_holder, settings, ai_state)
        result = {
            "chart": response.get("chart"),
            "params": response.get("params"),
            "timeline": timeline,
            "settings": settings,
            "aiState": ai_state,
            "snapshot_text": snapshot_text,
        }
        result["export_snapshot"] = self._augment_export_payload(technique="decennials", snapshot_text=snapshot_text)
        return result
