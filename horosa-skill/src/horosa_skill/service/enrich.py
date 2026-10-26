"""跑完技法后的富化（EnrichMixin）：推运缺省、本命附加段、古典分析、技法依据卡等 _attach_*。"""
from __future__ import annotations

import os
from datetime import timedelta
from typing import Any

from horosa_skill import __version__
from horosa_skill import predictive_text as _ptext
from horosa_skill.decisions.layer import current_decision_records
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.errors import HorosaSkillError, ToolValidationError, bilingual
from horosa_skill.reports.technique_card import build_technique_card
from horosa_skill.schemas.common import TOOL_ENVELOPE_SCHEMA_VERSION
from horosa_skill.service._common import (
    _finite_number,
    _is_astro_chart_payload,
    _require_option,
)
from horosa_skill.service._context import _degrade, logger
from horosa_skill.service.export import TOOL_EXPORT_TECHNIQUE_MAP
from horosa_skill.service.text.astro_core import (
    _build_house_cusp_lines,
    _build_natal_extra_sections,
    _build_planet_section,
    _build_star_and_lot_position_lines,
    _get_chart_object,
)
from horosa_skill.service.text.chart_family import (
    _INDIA_MOUNT_EXTRA_VARGA_MAX,
    _INDIA_MOUNT_VARGA_OPTIONS,
    _fixed_star_orb_params,
    _india_chart_remote_payload,
    _india_mount_varga_label,
    _normalize_india_extra_vargas,
)
from horosa_skill.service.text.chinese import _compact_jieqi_seed_row
from horosa_skill.service.text.pd_zr import (
    _PD_METHOD_LABELS,
    _PD_TIME_KEY_LABELS,
    _ZR_AI_MODES,
    _ZR_BASE_POINTS,
)
from horosa_skill.service.text.predictive import (
    _PD_DISPLAY_ZONE,
    _PERIOD_PREDICTIVE_TOOLS,
    _RETURN_PREDICTIVE_TOOLS,
    _pd_display_rows,
    _persian_birth_date,
    _upstream_now_wall_clock,
)
from horosa_skill.service.text.western import _RELATIVE_TAB_BY_CODE


class EnrichMixin:
    def _apply_upstream_predictive_defaults(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        """F19：远端星运工具缺目标时刻/返照地时按上游缺省补齐（写回 input_normalized，回显即实算口径）。

        上游 utils/aiAnalysisContext.js:2673-2760 buildPredictivePeriodSnapshot：
        - solarreturn/lunarreturn/givenyear：datetime 缺省 = 「今年生日时刻」（当年 + 出生月日 + 出生时分，
          [挂载自检 F-17]）；dirLat/dirLon 缺省本命经纬（lunarreturn/givenyear 后端**必读** dirLat/dirLon，
          缺了直接 param error）；
        - profection/solararc：datetime 缺省 = 此刻（`new DateTime()` 钟面，+08:00）；
        - 五法 dirZone 缺省本命时区。
        pdchart（aiAnalysisContext.js:2515-2531 pdCurrentDateTime）：缺省 = 主限表首条应期日期（UTC 墙钟 +
        dirZone '+00:00'），无行则出生次日。旧实现一概不补：solarreturn/profection/solararc 无 datetime 时后端回
        90 年**列表**（skill 当 invalid_result_shape 报错），lunarreturn/givenyear/pdchart 直接 param error。
        """
        if tool_name == "zr":
            return self._apply_zr_base_point(payload)
        if tool_name in ("pd", "pdchart"):
            # F20：词表 = 上游 SUPPORTED_PD_METHODS（13）/ SUPPORTED_PD_TIME_KEYS（26）。后端对白名单外静默回退
            # core_alchabitius / Ptolemy——认不出就报错，不让「传了 X 实算 Alchabitius」无声发生。
            if payload.get("pdMethod") is not None:
                _require_option(payload["pdMethod"], tuple(_PD_METHOD_LABELS), field="pdMethod", tool=tool_name)
            if payload.get("pdTimeKey") is not None:
                _require_option(payload["pdTimeKey"], tuple(_PD_TIME_KEY_LABELS), field="pdTimeKey", tool=tool_name)
            if tool_name == "pd":
                return payload
        if tool_name not in _PERIOD_PREDICTIVE_TOOLS and tool_name != "pdchart":
            return payload
        if tool_name == "profection":
            # [Q-105] profGrain/profStart 只喂 [小限摘要] 文本（纯前端派生），值域 = profectionSummary.js:13-24。
            if payload.get("profGrain") is not None:
                _require_option(payload["profGrain"], tuple(_ptext.PROFECTION_GRAIN_CN), field="profGrain", tool="profection")
            if payload.get("profStart") is not None:
                _require_option(payload["profStart"], tuple(_ptext.PROFECTION_START_CN), field="profStart", tool="profection")
        effective = dict(payload)
        if tool_name in _PERIOD_PREDICTIVE_TOOLS:
            if not effective.get("datetime"):
                now = _upstream_now_wall_clock()
                date_text = f"{payload.get('date') or ''}"
                if tool_name in _RETURN_PREDICTIVE_TOOLS and len(date_text) >= 10:
                    time_text = f"{payload.get('time') or '12:00:00'}"
                    effective["datetime"] = f"{now.strftime('%Y')}{date_text[4:].replace('/', '-')} {time_text[:5]}"
                else:
                    effective["datetime"] = now.strftime("%Y-%m-%d %H:%M")
            if not effective.get("dirZone"):
                effective["dirZone"] = payload.get("zone")
            if tool_name in _RETURN_PREDICTIVE_TOOLS:
                if not effective.get("dirLat"):
                    effective["dirLat"] = payload.get("lat")
                if not effective.get("dirLon"):
                    effective["dirLon"] = payload.get("lon")
        elif not effective.get("datetime"):
            effective["datetime"], effective["dirZone"] = self._pdchart_default_datetime(payload)
        return effective

    def _apply_zr_base_point(self, payload: dict[str, Any]) -> dict[str, Any]:
        """F8：黄道星释基点 → startSign（上游 AstroZR.js:354-385 buildZodialReleaseSnapshotText）。

        福点 = 不传 startSign（后端按福点所在座起）；基点本身是星座 → 直接用；其余（六希腊点/四轴）取本命盘上
        该点所在座。显式 startSign 优先（本仓旧参数，语义 = 以星座为基点）。认不出的 basePoint/aiMode 报结构化错误，
        取不到基点位置也报错（上游此时静默回落福点而段头仍写所选基点 = 标签与算法不符）。
        """
        base_point = payload.get("basePoint")
        ai_mode = payload.get("aiMode")
        if base_point is not None:
            _require_option(base_point, _ZR_BASE_POINTS, field="basePoint", tool="zr")
        if ai_mode is not None:
            _require_option(ai_mode, tuple(_ZR_AI_MODES), field="aiMode", tool="zr")
        for field in ("aiL1Idx", "aiL2Idx", "aiL3Idx"):
            value = payload.get(field)
            if value is not None and (_finite_number(value) is None or _finite_number(value) < 0):
                raise ToolValidationError(
                    f"zr 的 {field}={value!r} 须为 ≥0 的整数 / {field} must be a non-negative integer.",
                    code="tool.predictive_invalid_option",
                    details={"tool": "zr", "field": field, "value": value},
                )
        if not base_point or base_point == "Pars Fortuna" or payload.get("startSign"):
            return payload
        effective = dict(payload)
        if base_point in _ptext.LIST_SIGNS:
            effective["startSign"] = base_point
            return effective
        natal_payload = {**payload, "predictive": 0}
        for key in ("datetime", "dirZone", "dirLat", "dirLon", "startSign", "stopLevelIdx"):
            natal_payload.pop(key, None)
        natal = self._call_remote("/chart", natal_payload)
        obj = _get_chart_object(natal, base_point) if isinstance(natal, dict) else None
        sign = obj.get("sign") if isinstance(obj, dict) else None
        if sign not in _ptext.LIST_SIGNS:
            raise ToolValidationError(
                f"zr 基点 {base_point} 在本命盘上取不到所在星座 / base point {base_point} not found on the natal chart.",
                code="tool.zr_invalid_base_point",
                details={"basePoint": base_point},
            )
        effective["startSign"] = sign
        return effective

    def _pdchart_default_datetime(self, payload: dict[str, Any]) -> tuple[str, str]:
        """上游 AstroPrimaryDirectionChart.js:454 defaultPdChartDateTime：首条（过滤后）主限行的「日期」列，
        按 UTC 墙钟解释（dirZone='+00:00'）；取不到行 → 出生次日同一墙钟挂 +00:00。"""
        chart_payload = {**payload, "predictive": 1, "includePrimaryDirection": 1}
        for key in ("datetime", "dirZone", "dirLat", "dirLon"):
            chart_payload.pop(key, None)
        rows: Any = []
        params: dict[str, Any] = {}
        try:
            chart = self._call_remote("/chart", chart_payload)
            predictives = chart.get("predictives") if isinstance(chart.get("predictives"), dict) else {}
            rows = predictives.get("primaryDirection") or []
            params = chart.get("params") if isinstance(chart.get("params"), dict) else {}
        except HorosaSkillError as exc:
            _degrade("pdchart default datetime: primary-direction table fetch failed, using birth+1d: %s", exc)
        pd_method = f"{payload.get('pdMethod') or params.get('pdMethod') or 'core_alchabitius'}"
        show_bounds = payload.get("showPdBounds") if payload.get("showPdBounds") is not None else params.get("showPdBounds")
        for row in _pd_display_rows(rows, pd_method, show_bounds):
            date_text = f"{row[4] if len(row) > 4 and row[4] else ''}".strip()
            if date_text:
                return date_text, _PD_DISPLAY_ZONE
        birth = _persian_birth_date(f"{payload.get('date') or ''} {payload.get('time') or ''}".strip())
        if birth is None:
            raise ToolValidationError(
                "pdchart 缺目标时刻且无法解析出生时刻 / pdchart needs a datetime (birth date/time unparseable).",
                code="tool.pdchart_invalid_datetime",
                details={"date": payload.get("date"), "time": payload.get("time")},
            )
        return (birth + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"), _PD_DISPLAY_ZONE

    def _attach_predictive_chart_context(self, tool_name: str, payload: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
        # planetaryarc 同属「本命 ↔ 时段两盘对照」形态（上游 preset 也列 [本命盘配置]/[时段盘配置]/[相位]），
        # 但 /predict/planetaryarc 只回时段盘 → 同样需要补拉本命盘。
        if tool_name not in {"solarreturn", "lunarreturn", "solararc", "givenyear", "profection", "pd", "pdchart", "zr", "planetaryarc", "vedicprog", "jaynesprog"}:
            return response
        enriched = dict(response)
        if "params" not in enriched:
            enriched["params"] = {
                **payload,
                "birth": f"{payload.get('date', '—')} {payload.get('time', '—')}",
            }
        if not any(key in enriched for key in ("natalChart", "birthChart", "baseChart")):
            natal_payload = {**payload, "predictive": 0}
            natal_payload.pop("datetime", None)
            natal_payload.pop("dirZone", None)
            natal_payload.pop("dirLat", None)
            natal_payload.pop("dirLon", None)
            # 辅助本命盘 fetch 失败不得清空已算好的推运结果 → 与其余 _attach_* 一致的优雅降级。
            try:
                enriched["natalChart"] = self._call_remote("/chart", natal_payload)
            except HorosaSkillError as exc:
                _degrade("predictive natal chart fetch failed (tool=%s): %s", tool_name, exc)
        return enriched

    # [寿命格局] 取主法（上游 AstroLifespan.js:14-18 METHODS）。
    _LIFESPAN_METHODS = ("ptolemy", "alcabitius", "dorotheus")

    def _attach_natal_extras(
        self, tool_name: str, response_data: dict[str, Any], payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        # v2.4.0 西占: enrich the astrochart (and mundane) export with 12分度 / 主宰星链 / 寿命格局.
        # These are computed by the vendored JS astroextra formatter (Ptolemy hyleg engine) from the
        # chart object. Only `chart` (astrochart) and `mundane` carry them in 星阙; never fail the
        # chart if the enrichment errors.
        # 上游 v50 给整个 chart 家族（含 13 宫/希腊化/衍生盘）都出 12分度/主宰星链/寿命格局，
        # 不只本命与世俗盘——门控放开到 astrochart_like 家族，段随之进导出。
        if tool_name not in {"chart", "mundane", "chart13", "chart12", "hellen_chart", "harmonic", "draconic", "relocation"}:
            return response_data
        if not isinstance(response_data, dict) or not _is_astro_chart_payload(response_data):
            return response_data
        sections: dict[str, str] = {}
        # F15：取主法随调用方（上游读 localStorage horosa.lifespan.method，缺省 ptolemy）；太阳三态阈值由 JS 侧从
        # 本盘 params 回显读取（cazimiOrb/combustOrb/underBeamsOrb，上游 astroAiSnapshot.js:1127-1132 同源）。
        lifespan_method = (payload or {}).get("lifespanMethod")
        if lifespan_method is not None:
            _require_option(lifespan_method, self._LIFESPAN_METHODS, field="lifespanMethod", tool=tool_name)
        options = {"lifespanMethod": lifespan_method} if lifespan_method else {}
        try:
            js = self.js_client.run("astroextra", {"chart": response_data, "options": options})
            extras_data = js.get("data") if isinstance(js, dict) else None
            if isinstance(extras_data, dict):
                sections = _build_natal_extra_sections(extras_data)
        except Exception as exc:  # noqa: BLE001 — 富化失败不许影响主盘；此前裸 pass 连日志都没有
            _degrade("astro natal extras (12分度/主宰星链/寿命格局) build failed: %s", exc)
        # 恒挂（JS 失败时为空 dict）：它同时是「本盘属西占 chart 家族」的标记——[主宰星链] 尾部的整宫制宫主表与
        # [分宫制宫神星表]（v57，astro_rulers.py 纯 Python 单源）在快照构建时据此照出，不随 JS 富化成败丢失。
        enriched = dict(response_data)
        enriched["_natalExtras"] = sections
        return enriched

    # [古典·显赫计分] 主宰光体判定项（上游 astroAiSnapshot.js:1716-1726 predOpts）：四键读全局仓（headless = 请求顶层），
    # 界系/双子界序/自定义界表随盘 fields。
    _EMINENCE_KEYS = (
        "busyPlaces", "dynamicalDivisions", "domicileMasterMethod", "rayWeighting",
        "termsVariant", "geminiBoundEmended", "customTermsDay", "customTermsNight",
    )

    def _attach_classical_derived(
        self, tool_name: str, response_data: dict[str, Any], payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """古典衍化四段（上游 v3.9.2）：仅本命 astrochart 挂载。

        上游 opt-in 语义（astroAiSnapshot.js:1550）：只有本命 astro 快照路径传 classicalDerived，
        germany/mundane/indiachart 等嵌套消费方缺省 falsy = 零输出——skill 同口径，只 gate `chart`。
        计算走 vendored `astroClassicalDerived.js`（与上游四组件同引），JS 失败优雅降级不产段
        （条件段双登记，缺席不算漏）。
        """
        if tool_name != "chart":
            return response_data
        if not isinstance(response_data, dict) or not _is_astro_chart_payload(response_data):
            return response_data
        eminence = {k: (payload or {})[k] for k in self._EMINENCE_KEYS if (payload or {}).get(k) not in (None, "")}
        try:
            js = self.js_client.run("classical_derived", {"chart": response_data, "eminence": eminence})
            invalid = js.get("invalid") if isinstance(js, dict) else None
            if invalid:
                parts = [f"{i.get('key')}={i.get('value')!r}（可选：{'/'.join(str(a) for a in (i.get('allowed') or []))}）" for i in invalid if isinstance(i, dict)]
                raise ToolValidationError(
                    bilingual(f"显赫计分口径取值无效：{'；'.join(parts)}。", f"eminence setting(s) invalid: {'; '.join(parts)}."),
                    code="tool.chart_invalid_setting",
                    details={"invalid": invalid},
                )
            text = js.get("snapshot_text") if isinstance(js, dict) else ""
            if isinstance(text, str) and text.strip():
                sections: dict[str, str] = {}
                for block in text.split("\n\n"):
                    lines = block.strip().splitlines()
                    if lines and lines[0].startswith("[") and lines[0].endswith("]"):
                        sections[lines[0][1:-1]] = "\n".join(lines[1:]).strip()
                if sections:
                    enriched = dict(response_data)
                    enriched["_classicalDerived"] = sections
                    return enriched
        except ToolValidationError:
            raise
        except Exception as exc:  # noqa: BLE001 - enrichment must never fail the chart, but say so
            _degrade("classical derived sections failed: %s", exc)
        return response_data

    def _attach_jyotish_sections(
        self, tool_name: str, response_data: dict[str, Any], payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """印占 Jyotish 派生段 (星阙 v3.6.0 印占大扩容)。

        后端 `/india/chart` 本就返回整棵 `jyotish` 树（panchanga / jaimini / kp / shadbala / dasha /
        ashtakavarga … 30 个子树），星阙前端用一个纯格式化函数把它铺成 50+ 个具名段——skill 此前只登记
        了 11 段，其余全被丢弃。这里复用逐字 vendor 的同一个 builder（`horosa-core-js` 的
        `india_jyotish` 工具），保持与桌面端逐字同源。与其他 `_attach_*` 同款：gated + 优雅降级，
        任何失败都只是这些段不出，绝不带崩排盘本身。
        """
        if tool_name != "india_chart":
            return response_data
        if not isinstance(response_data, dict) or not response_data.get("jyotish"):
            return response_data
        src = payload or {}
        # [起盘信息] 口径行（上游 indiaCalibreLine(fields)，IndiaChart.js:1113-1124）的分宫制/岁差：取后端**实际用的**口径
        # （响应 params.hsys / params.ayanamsa = webindiasrv 按 indiaHsys→hsys、indiaAyanamsa→ayanamsa→siderealMode 解析后的值），
        # 与上游页面「请求即已归一」同一结果；缺回显时按同一取值序落请求值。
        echo = response_data.get("params") if isinstance(response_data.get("params"), dict) else {}
        req_hsys = src.get("indiaHsys") if src.get("indiaHsys") not in (None, "") else src.get("hsys", 0)
        req_ayan = src.get("indiaAyanamsa") or src.get("ayanamsa") or src.get("siderealMode") or "lahiri"
        calibre_overrides = {
            "indiaHsys": echo.get("hsys") if echo.get("hsys") not in (None, "") else req_hsys,
            "indiaAyanamsa": echo.get("ayanamsa") or req_ayan,
        }
        # [大运Dasha] 体系 + [起盘信息] 流派头行的页面口径（上游 fields：indiaDashaSystem / indiaSchool /
        # indiaDashaVariants + 出生时刻供扩展大运推日期）。chartnum = 所绘分盘：上游 buildIndiaSnapshotText(result, fields,
        # params.chartnum, hook)（IndiaChart.js:1348）据它印「当前分盘 / 分盘」两行；不传则恒为「命盘 / D1」。
        params = {
            "dashaSystem": src.get("dashaSystem"),
            "indiaSchool": src.get("indiaSchool"),
            "dashaVariants": src.get("dashaVariants"),
            "date": src.get("date"),
            "time": src.get("time"),
            "ad": src.get("ad", 1),
            "chartnum": src.get("chartnum"),
            "calibreOverrides": calibre_overrides,
        }
        try:
            # js_client 已解包 envelope 的 data，返回的就是 runner 的结果对象。
            js = self.js_client.run("india_jyotish", {"chart": response_data, "params": params})
            invalid = js.get("invalid") if isinstance(js, dict) else None
            if invalid:
                parts = [f"{i.get('key')}={i.get('value')!r}（可选：{'/'.join(i.get('allowed') or [])}）" for i in invalid if isinstance(i, dict)]
                raise ToolValidationError(
                    bilingual(f"印度律盘设置取值无效：{'；'.join(parts)}。", f"india_chart setting(s) invalid: {'; '.join(parts)}."),
                    code="tool.india_chart_invalid_setting",
                    details={"invalid": invalid},
                )
            if isinstance(js, dict):
                enriched = dict(response_data)
                sections = js.get("sections")
                if isinstance(sections, dict) and sections:
                    enriched["_jyotishSections"] = sections
                if isinstance(js.get("dashaLines"), list):
                    enriched["_indiaDashaLines"] = js.get("dashaLines")
                if isinstance(js.get("schoolLines"), list):
                    enriched["_indiaSchoolLines"] = js.get("schoolLines")
                calibre_line = f"{js.get('calibreLine') or ''}".strip()
                if calibre_line:
                    enriched["_indiaCalibreLine"] = calibre_line
                    used = js.get("calibre") if isinstance(js.get("calibre"), dict) else {}
                    if f"{used.get('indiaHsys')}" != f"{calibre_overrides['indiaHsys']}" or f"{used.get('indiaAyanamsa')}" != f"{calibre_overrides['indiaAyanamsa']}":
                        # 上游 normalize* 认不出 → 口径行按缺省（整宫 / Lahiri）写，而后端按原值算：说出来，不让标注与实算静默分叉。
                        _degrade(
                            "india calibre line normalized %s -> %s", calibre_overrides, used,
                            note=(
                                f"印度律盘 [起盘信息] 口径行按上游词表归一为 分宫制 {used.get('indiaHsys')} / 岁差 {used.get('indiaAyanamsa')}，"
                                f"与后端实算口径 分宫制 {calibre_overrides['indiaHsys']} / 岁差 {calibre_overrides['indiaAyanamsa']} 不一致（该值不在上游可选表内）。"
                            ),
                        )
                return enriched
        except ToolValidationError:
            raise
        except Exception as exc:  # noqa: BLE001 — 富化失败不许影响主盘
            _degrade(
                "jyotish section build failed: %s", exc,
                note="印度律盘 Jyotish 派生段、[大运Dasha] 与 [起盘信息] 流派行 / 口径行本次未产出（JS 段 builder 失败），其余段不受影响。",
            )
        return response_data

    def _attach_india_extra_vargas(
        self, tool_name: str, payload: dict[str, Any], response_data: dict[str, Any]
    ) -> dict[str, Any]:
        """[附加分盘]（上游 v3.11.0 #80，IndiaChart.js:1219-1333 buildIndiaSnapshotForFields 的 extraVargas 分支）。

        主盘之外再挂几张分盘（如婚姻 D9 + 子女 D7），每张只出「宫位宫头 + 星与虚点 + 行星」简表（整张分盘快照约
        2.6 万字，N 张全出会把预算吃穿）。归一（值域/去重/上限 4）后剔掉主盘自身（planIndiaExtraVargas），逐张另取
        /india/chart?chartnum=N（上游 fetchIndiaVargaBriefLines 同路），段内小标题 `── D9 婚姻 ──`。缺省不选 = 不发请求、不加段。
        """
        if tool_name != "india_chart" or not isinstance(response_data, dict):
            return response_data
        raw = payload.get("indiaExtraVargas")
        if raw in (None, "", [], ()):
            return response_data
        wanted, dropped = _normalize_india_extra_vargas(raw)
        if dropped:
            _degrade(
                "india extra vargas dropped invalid entries: %s", dropped,
                note=(
                    f"印度盘 [附加分盘]：已忽略无效/重复/超上限的分盘 {dropped}"
                    f"（可选 {'/'.join(str(n) for n, _ in _INDIA_MOUNT_VARGA_OPTIONS if n > 1)}，最多 {_INDIA_MOUNT_EXTRA_VARGA_MAX} 张）。"
                ),
            )
        try:
            main = int(payload.get("chartnum") or 1)
        except (TypeError, ValueError):
            main = 1
        main = main if main > 0 else 1
        extras = [n for n in wanted if n != main]
        if not extras:
            return response_data
        base_remote = {
            k: v for k, v in _india_chart_remote_payload(payload).items() if k not in ("chartnum", "tripataki")
        }
        extra_lines: list[str] = []
        for chartnum in extras:
            try:
                varga = self._call_remote("/india/chart", {**base_remote, "chartnum": chartnum})
            except Exception as exc:  # noqa: BLE001 — 单张附加分盘失败不许带崩主盘
                _degrade(
                    "india extra varga D%s fetch failed: %s", chartnum, exc,
                    note=f"印度盘 [附加分盘] D{chartnum} 本次未能取到（其余分盘与主盘不受影响）。",
                )
                continue
            if not isinstance(varga, dict) or not _is_astro_chart_payload(varga):
                _degrade(
                    "india extra varga D%s returned no chart", chartnum,
                    note=f"印度盘 [附加分盘] D{chartnum} 后端未返回盘面，已跳过。",
                )
                continue
            # 上游 pickIndiaVargaBriefLines：只挑该分盘自己的 宫位宫头 + 星与虚点 + 行星 三段正文（trimEnd + 去空行）。
            body = [
                line.rstrip()
                for block in (
                    _build_house_cusp_lines(varga),
                    _build_star_and_lot_position_lines(varga),
                    _build_planet_section(varga),
                )
                for line in "\n".join(f"{item}" for item in (block or [])).split("\n")
                if line.strip()
            ]
            if body:
                extra_lines.append(f"── {_india_mount_varga_label(chartnum)} ──")
                extra_lines.extend(body)
        if not extra_lines:
            return response_data
        enriched = dict(response_data)
        # 上游 ensureSection：首行说明 + 各张简表（ensureSection 会滤掉空行，故各张之间无空行）。
        enriched["_indiaExtraVargas"] = "\n".join(
            ["以下为主盘之外另挂的分盘,只列该分盘的宫头与星曜落宫(大运/瑜伽/相位等仍以主盘段为准)。", *extra_lines]
        )
        return enriched

    # 古典格局派生分析 (星阙 v2.6.7): astrochart/astrochart_like 的 [古典格局] 段来自 /astroextra/analysis
    # (护卫/优势相位/相位动态/逐题主星/偶然尊贵/恒星/行星时/埃及历/巴比伦/格局/分布/气质/almutem/吉化-extraLots)。
    # 与前端同源:按需 fetch、优雅降级(失败→不挂载→该段不出)。[古典](逐曜状态/围攻/围绕)直接读 /chart 响应,无需此 fetch。
    # 调波盘同属上游 ASTRO_LIKE_EXPORT_KEYS 族，盘面形状与本命盘一致 → 同样吃得下派生分析。
    # （上游把 harmonic 放在 skipClassical 名单里是 UI 侧的性能取舍，headless 无此顾虑，多出的
    # [古典格局] 是 skill 相对上游的 extra，不是漂移。）
    # mundane 也纳入：它已走 `_build_astro_snapshot_text`，开门控即得 [埃及历]。但**不要**因此
    # 给 mundane 登记 [古典格局]——世俗盘无该段是既定结论（docs/LESSONS.md）。
    _CLASSICAL_ANALYSIS_TOOLS = {"chart", "chart13", "chart12", "hellen_chart", "harmonic", "mundane", "draconic", "relocation"}

    def _attach_classical_analysis(self, tool_name: str, payload: dict[str, Any], response_data: dict[str, Any]) -> dict[str, Any]:
        if tool_name not in self._CLASSICAL_ANALYSIS_TOOLS:
            return response_data
        if not isinstance(response_data, dict) or not _is_astro_chart_payload(response_data):
            return response_data
        # [埃及历] 只吃本盘（上游 astroAiSnapshot.js:1731 buildEgyptSectionLines(chartObj, …)，与 /astroextra/analysis 无关）：
        # 先于、且独立于 analysis 拉取挂上——analysis 缺参 / 失败只少 [古典格局]，不再连带 [埃及历]。
        egypt = self._build_egypt_section(response_data, payload)
        if egypt:
            response_data = {**response_data, "_egyptSection": egypt}
        for key in ("date", "zone", "lat", "lon"):
            if not payload.get(key):
                return response_data
        try:
            analysis = self._call_remote(
                "/astroextra/analysis",
                {
                    # 缓存代次盐，与上游 aiExport.js / AstroHelper.java 同值：后端 paramhash 磁盘缓存不区分
                    # 「古典口径进入临界区之前/之后」算出的结果，不带盐的请求会命中旧代次的缓存条目。
                    "_v": "cls1",
                    "date": payload.get("date"),
                    "time": payload.get("time"),
                    "zone": payload.get("zone"),
                    "lat": payload.get("lat"),
                    "lon": payload.get("lon"),
                    "gpsLat": payload.get("gpsLat"),
                    "gpsLon": payload.get("gpsLon"),
                    "ad": payload.get("ad", 1),
                    "hsys": payload.get("hsys"),
                    "zodiacal": payload.get("zodiacal"),
                    "siderealAyanamsa": payload.get("siderealAyanamsa"),
                    # [M-1][Q-340/T-321]（上游 aiExport.js:6742 fixedStarOrbParamsFor）：恒星轨随盘（此前硬编 1°，
                    # 用户给了 starOrb/starOrbMode 时 [古典格局] 的恒星命中与主盘口径分叉）。
                    **_fixed_star_orb_params(payload),
                },
            )
            if isinstance(analysis, dict) and analysis:
                enriched = dict(response_data)
                enriched["_classicalAnalysis"] = analysis
                return enriched
        except ToolValidationError:
            raise
        except Exception as exc:
            _degrade("classical /astroextra/analysis failed (tool=%s): %s", tool_name, exc)
        return response_data

    # 埃及历七轴（上游随盘键 egypt_<axis>，egyptianSchools.EGYPT_RECORD_KEYS；挂载齿轮 techniqueMountSettings.js:965-980）。
    _EGYPT_AXIS_KEYS = (
        "egypt_decanRuler", "egypt_decanAnchor", "egypt_decanNaming", "egypt_starClock",
        "egypt_calendarAnchor", "egypt_petosirisMod", "egypt_godEdition",
    )

    def _build_egypt_section(self, chart: dict[str, Any], payload: dict[str, Any] | None = None) -> str:
        """[埃及历] 独立段：各点落旬 / 上升旬详情 / 埃及民用历 + Sothic。

        上游把埃及历**同时**写在两处：`古典格局` 段里一行摘要（天狼偕日升/岁年/上升旬，来自 /astroextra/analysis），以及
        这个逐点铺开的独立段（`aiExport.js` 的 preset 里 astrochart 与 5 个衍生盘键都列了它）。两处并存是上游原样。

        🔴 本段**只吃本盘**：上游唯一调用点 astroAiSnapshot.js:1731 `buildEgyptSectionLines(chartObj, …)` 传的是 /chart 结果，
        其中没有 `egyptianCalendar`（该字段只在 /astroextra/analysis）——页面 AstroEgypt 组件另拉 extra 浅合并只供 UI 渲染，
        不进快照。故上游 [埃及历] 恒无「天狼偕日升」行（那一行在 [古典格局] 的「埃及历：」摘要里）。本仓此前把 analysis 的
        egyptianCalendar 并进盘对象，多出一行上游没有的正文；wave 3b 起与上游同形。失败只是本段不出（进 warnings）。
        """
        try:
            chart_obj = {k: v for k, v in chart.items() if k != "egyptianCalendar"}
            # 流派口径：随盘键 egypt_* → egyptSchoolFromFields（上游 astroAiSnapshot.js:1733 优先读 fields，缺键回全局=默认档）。
            egypt_fields = {k: {"value": (payload or {})[k]} for k in self._EGYPT_AXIS_KEYS if (payload or {}).get(k) not in (None, "")}
            js = self.js_client.run("egypt_section", {"chart": chart_obj, "fields": egypt_fields})
            invalid = js.get("invalid") if isinstance(js, dict) else None
            if invalid:
                parts = [f"{i.get('key')}={i.get('value')!r}（可选：{'/'.join(str(a) for a in (i.get('allowed') or []))}）" for i in invalid if isinstance(i, dict)]
                raise ToolValidationError(
                    bilingual(f"埃及历流派口径取值无效：{'；'.join(parts)}。", f"egypt school setting(s) invalid: {'; '.join(parts)}."),
                    code="tool.egypt_invalid_setting",
                    details={"invalid": invalid},
                )
            text = js.get("text") if isinstance(js, dict) else None
            return f"{text}".strip() if text else ""
        except ToolValidationError:
            raise
        except Exception as exc:  # noqa: BLE001 — 富化失败不许影响主盘
            _degrade("egypt section build failed: %s", exc)
            return ""

    def _attach_relative_score(
        self, tool_name: str, input_normalized: dict[str, Any], response_data: dict[str, Any]
    ) -> dict[str, Any]:
        # 合盘关系量化：/modern/relative 出比较盘后，另调 /astroextra/relative 取契合分数 +
        # 顺畅/张力连接（同 inner/outer），挂到 _relativeScore 供 [关系量化]/[顺畅连接]/[张力连接] 段。
        # 打分失败不阻塞既有比较盘段（优雅降级）。
        if tool_name != "relative" or not isinstance(response_data, dict):
            return response_data
        inner = input_normalized.get("inner")
        outer = input_normalized.get("outer")
        if not isinstance(inner, dict) or not isinstance(outer, dict):
            return response_data
        try:
            score = self._call_remote(
                "/astroextra/relative",
                {
                    "inner": inner,
                    "outer": outer,
                    "hsys": input_normalized.get("hsys", 1),  # 缺省随 RelativeInput（无头 aiAnalysisContext.js:1228 ?? 1）
                    "zodiacal": input_normalized.get("zodiacal", 0),
                },
            )
        except Exception as exc:  # noqa: BLE001 - degrade to no-score, keep comparison chart
            _degrade("relative score failed: %s", exc)
            return response_data
        if isinstance(score, dict) and score.get("score") is not None:
            enriched = dict(response_data)
            # 只留渲染三段所需字段，剥离 raw（整份 ChartComp）避免臃肿 envelope.data。
            enriched["_relativeScore"] = {
                "score": score.get("score"),
                "highlights": score.get("highlights"),
                "challenges": score.get("challenges"),
            }
            return enriched
        return response_data

    def _enrich_embedded_astro_chart(self, chart_wrap: dict[str, Any]) -> dict[str, Any]:
        """嵌入整盘（relative 比较盘 A/B、jieqi 分至盘）的富化 = 上游 buildAstroSnapshotContent 对任意盘本地算的几段：
        12分度 / 主宰星链链行 / 寿命格局（JS astroextra）+ 埃及历（JS egypt_section，只吃本盘，与主盘同口径）。
        失败只是对应段不出（`_degrade` 进 warnings），
        [主宰星链] 尾部整宫制宫主表与 [分宫制宫神星表] 是纯 Python，照出。
        """
        if not isinstance(chart_wrap, dict) or not _is_astro_chart_payload(chart_wrap):
            return chart_wrap
        enriched = self._attach_natal_extras("chart", chart_wrap)
        egypt = self._build_egypt_section(enriched)
        if egypt:
            enriched = dict(enriched)
            enriched["_egyptSection"] = egypt
        return enriched

    def _attach_relative_comp_charts(self, tool_name: str, input_normalized: dict[str, Any], response_data: dict[str, Any]) -> dict[str, Any]:
        """合盘各页签嵌入的无头整盘富化（12分度/主宰星链链行/寿命格局/埃及历，见 `_enrich_embedded_astro_chart`）：
        比较盘/影响盘/马克斯盘 = inner/outer 两盘（[比较盘-星盘A/B]、[影响图盘-星盘A/B]）；组合盘/时空中点盘 = 响应盘本身
        （[合成图盘]/[时空中点·合成图盘]）。上游这几段都是 buildAstroSnapshotContent 全口径（AstroRelative.js:168-206）。"""
        if tool_name != "relative" or not isinstance(response_data, dict):
            return response_data
        tab = _RELATIVE_TAB_BY_CODE.get(f"{input_normalized.get('relative', 0)}", "Comp")
        if tab in ("Composite", "TimeSpace"):
            return self._enrich_embedded_astro_chart(response_data) if _is_astro_chart_payload(response_data) else response_data
        enriched = response_data
        for key in ("inner", "outer"):
            chart = response_data.get(key)
            if isinstance(chart, dict) and _is_astro_chart_payload(chart):
                if enriched is response_data:
                    enriched = dict(response_data)
                enriched[key] = self._enrich_embedded_astro_chart(chart)
        return enriched

    # 上游页面种子请求的参数面（JieQiChartsMain.genParams(false) → Java JieQiController.getYearParams 白名单）：
    # 不带 jieqis（= 全年 24 节气）、不带 seedOnly（= 走 setupBazi 逐节气补四柱）。
    _JIEQI_SEED_DROP_KEYS = frozenset({"jieqis", "seedOnly"})

    def _attach_jieqi_year_extras(self, tool_name: str, input_normalized: dict[str, Any], response_data: dict[str, Any]) -> dict[str, Any]:
        """jieqi_year 的两项富化（上游 v3.11 整年快照）：

        ① [二十四节气]：全年 24 节气交节时刻 + 四柱。上游页面的种子请求打的是 **Java** `/jieqi/year`（无 jieqis），
           Java 层 `JieQiController.setupBazi` 给每个节气补 `bazi.fourColumns`；本仓工具主调用走 Python 同名路由
           （只回所请求的分至四项、无四柱），故另发一次 Java 种子请求。Java 不可用 → 本段不出 + warnings（条件段双登记）。
        ② 分至盘嵌入整盘的 JS 富化（12分度/主宰星链链行/寿命格局/埃及历，见 `_enrich_embedded_astro_chart`）。
        """
        if tool_name != "jieqi_year" or not isinstance(response_data, dict):
            return response_data
        enriched = dict(response_data)
        seed_payload = {key: value for key, value in input_normalized.items() if key not in self._JIEQI_SEED_DROP_KEYS and value is not None}
        seed_payload.setdefault("timeAlg", 0)   # preciseCalcBridge.normalizeJieqiParams：timeAlg 缺省 0（真太阳时）
        try:
            seed = self._call_remote("/jieqi/year", seed_payload, backend="java")
            rows = seed.get("jieqi24") if isinstance(seed, dict) else None
            if isinstance(rows, list) and rows:
                enriched["_jieqi24Seed"] = [_compact_jieqi_seed_row(row) for row in rows if isinstance(row, dict)]
            else:
                _degrade("jieqi_year [二十四节气] seed (Java /jieqi/year) returned no jieqi24 rows")
        except Exception as exc:  # noqa: BLE001 — 种子段失败不许带崩分至四盘
            _degrade("jieqi_year [二十四节气] seed (Java /jieqi/year) failed: %s", exc)
        charts = response_data.get("charts")
        if isinstance(charts, dict):
            charts = self._jieqi_sidereal_recharts(input_normalized, charts)
            enriched["charts"] = {
                title: self._enrich_embedded_astro_chart(chart) if isinstance(chart, dict) else chart
                for title, chart in charts.items()
            }
        return enriched

    def _jieqi_sidereal_recharts(self, input_normalized: dict[str, Any], charts: dict[str, Any]) -> dict[str, Any]:
        """F16：恒星黄道岁差逐节气重排（上游 JieQiChartsMain.js:524-553 loadJieqiChart → buildChartRequestParams）。

        上游的分至盘是逐节气一次 `/chart`（带 siderealAyanamsa）；本仓主调用走 Python `/jieqi/year`，它按
        YearJieQi.params（zone/lat/lon/hsys/zodiacal/doubingSu28）起 PerChart —— **不带岁差键**，于是恒星黄道盘
        一律是 swisseph 缺省岁差。所以给了 siderealAyanamsa（且 zodiacal=1，PerChart 只在恒星黄道下读它）时，
        按交节时刻（charts[x].params.birth）逐盘重发 `/chart`。重排失败 → 该节气盘不出 + warnings
        （留着缺省岁差的盘冒充所选岁差，比缺段更糟）。
        """
        ayan = f"{input_normalized.get('siderealAyanamsa') or ''}".strip()
        if not ayan or f"{input_normalized.get('zodiacal', 0)}" not in ("1", "Sidereal"):
            return charts
        out: dict[str, Any] = {}
        for title, one in charts.items():
            params = one.get("params") if isinstance(one, dict) else None
            birth = f"{(params or {}).get('birth') or ''}".strip()
            date_text, _, time_text = birth.partition(" ")
            if not date_text or not time_text:
                _degrade("jieqi_year sidereal re-chart: %s has no birth time", title,
                         note=f"{title}盘缺交节时刻，无法按所选岁差 {ayan} 重排，该盘不出。")
                continue
            request = {
                "ad": input_normalized.get("ad", 1),
                "date": date_text, "time": time_text,
                "zone": input_normalized.get("zone"), "lat": input_normalized.get("lat"), "lon": input_normalized.get("lon"),
                "gpsLat": input_normalized.get("gpsLat"), "gpsLon": input_normalized.get("gpsLon"),
                "hsys": input_normalized.get("hsys", 0), "southchart": False,
                "zodiacal": 1, "siderealAyanamsa": ayan, "tradition": 0,
                "doubingSu28": input_normalized.get("doubingSu28", 0),
                "strongRecption": 0, "simpleAsp": 0, "virtualPointReceiveAsp": 0, "predictive": 0,
                "pdaspects": [0, 60, 90, 120, 180],
                **{k: input_normalized[k] for k in ("userAyanT0", "userAyanDeg") if input_normalized.get(k) is not None},
            }
            try:
                chart = self._call_remote("/chart", {k: v for k, v in request.items() if v is not None})
            except Exception as exc:  # noqa: BLE001 — 单盘失败不带崩其余节气
                _degrade("jieqi_year sidereal re-chart %s failed: %s", title, exc,
                         note=f"{title}盘按所选岁差 {ayan} 重排失败（{exc}），该盘不出，其余段不受影响。")
                continue
            if isinstance(chart, dict) and _is_astro_chart_payload(chart):
                out[title] = chart
            else:
                _degrade("jieqi_year sidereal re-chart %s returned no chart", title,
                         note=f"{title}盘按所选岁差 {ayan} 重排未返回盘面，该盘不出。")
        return out

    @staticmethod
    def _split_ymd(value: Any, *, tool: str) -> tuple[int, int, int]:
        parts = f"{value or ''}".replace("/", "-").split("-")
        try:
            return int(parts[0]), int(parts[1]), int(parts[2][:2])
        except (IndexError, ValueError):
            raise ToolValidationError(f"Invalid date for tool `{tool}`: {value!r}") from None

    def _attach_calendar_extras(self, tool_name: str, payload: dict[str, Any], response_data: dict[str, Any]) -> dict[str, Any]:
        """黄历页的三个子模块段块（老黄历 8 段 + 通书择日 + 日子馆 2 段）。

        上游 `calendar` 是页面聚合快照：NongLi（走后端 /calendar/month，本仓已有）+ HuangLi +
        Tongshu + Rizi 四子并出。后三子纯前端推演，由 vendored builder 一次跑完。
        日子馆两段只在传了 `rizi.persons` 时产出——没有当事人就没有「个性化」可言，故列 optional。
        """
        if tool_name != "calendar_month" or not isinstance(response_data, dict):
            return response_data
        selected = f"{payload.get('day') or payload.get('date') or ''}".replace("/", "-")
        parts = selected.split("-")
        try:
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2][:2])
        except (IndexError, ValueError):
            return response_data
        tongshu = dict(payload["tongshu"]) if isinstance(payload.get("tongshu"), dict) else None
        if tongshu and tongshu.get("school"):
            tongshu["school"] = self._tongshu_school(tongshu.get("school"))
        js: Any = None
        try:
            js = self.js_client.run(
                "calendar_extras",
                {
                    "year": year,
                    "month": month,
                    "day": day,
                    "hour": payload.get("hour"),
                    "tongshu": tongshu,
                    "rizi": payload.get("rizi") if isinstance(payload.get("rizi"), dict) else None,
                },
            )
        except Exception as exc:  # noqa: BLE001 — 子模块失败不许影响月历本体
            _degrade("calendar extras build failed: %s", exc)
            return response_data
        js = js if isinstance(js, dict) else {}
        # 显式给了认不出的通书流派键：结构化报错（此前照印「（该流派待实现）」冒充一段结论）。
        for err in js.get("errors") or []:
            if isinstance(err, dict) and err.get("reason") == "unknown_school":
                self._raise_tongshu_unknown_school(err, field="tongshu.school")
        text = f"{js.get('text') or ''}".strip()
        if text:
            enriched = dict(response_data)
            enriched["_calendarExtras"] = text
            return enriched
        return response_data

    def _attach_technique_card(
        self, tool_name: str, input_normalized: dict[str, Any], response_data: dict[str, Any]
    ) -> dict[str, Any]:
        """给技法响应挂上技法依据卡（`data.technique_card`）。

        best-effort：卡片是元数据，任何构造失败都不许影响技法结果本身——宁可没有卡，
        也不能因为一份说明性数据让一次真实起盘失败（与 tracing 同款纪律，§9）。
        `HOROSA_TECHNIQUE_CARD=0` 关闭。
        """
        if not isinstance(response_data, dict):
            return response_data
        if os.environ.get("HOROSA_TECHNIQUE_CARD", "1").strip() in {"0", "false", "no"}:
            return response_data
        try:
            card = build_technique_card(
                tool_name=tool_name,
                technique_key=TOOL_EXPORT_TECHNIQUE_MAP.get(tool_name),
                domain=TOOL_DEFINITIONS[tool_name].domain if tool_name in TOOL_DEFINITIONS else None,
                input_normalized=input_normalized,
                response_data=response_data,
                skill_version=__version__,
                envelope_schema=TOOL_ENVELOPE_SCHEMA_VERSION,
                runtime_version=self._installed_runtime_version(),
            )
        except Exception:  # noqa: BLE001 - 元数据失败绝不拖垮技法调用
            logger.debug("technique card build failed for %s", tool_name, exc_info=True)
            return response_data
        # 决策层自陈（v0.39.0）：本次调用里每一条 Jev 决策（面 / 模型 / 选项 / 置信 / 是否采纳）。
        # 只在有记录时挂键——缺省 off 时卡片逐字节不变。
        decisions = current_decision_records()
        if decisions:
            card["decisions"] = decisions
        augmented = dict(response_data)
        augmented["technique_card"] = card
        return augmented

    def _installed_runtime_version(self) -> str | None:
        try:
            manifest = self.runtime_manager.load_installed_manifest()
        except Exception:  # noqa: BLE001 - 每次技法调用都走这里（技法卡）：
            # 没装 / 坏 JSON 已由 load_installed_manifest 自己返回 None；这里兜的是字段类型异常（int() 失败）
            # 与没有该方法的桩 manager——版本号只是卡片上的一栏，拿不到就是 None，不该连整张卡一起丢。
            return None
        if isinstance(manifest, dict):
            version = manifest.get("version")
            if isinstance(version, str) and version.strip():
                return version.strip()
        return None
