"""辅盘 runner（AuxLabRunners）：变换盘、黄道制（上游 v3.14.0）。"""
from __future__ import annotations

from typing import Any

from horosa_skill.auxlab_vocab import (
    TRANSFORM_DEFAULTS,
    TRANSFORM_FIELD_TO_SETTING,
    TRANSFORM_KIND_LABELS,
    TRANSFORM_KIND_OPTIONS,
    TRANSFORM_OPTION_LABELS,
    TRANSFORM_SETTING_TO_FIELD,
    ZODIAC_VERSION_DEFAULT,
    ZODIAC_VERSION_LABELS,
    transform_request_fields,
)
from horosa_skill.errors import ToolValidationError, bilingual, tool_code

# 这两页与上游无头路径 utils/aiAnalysisContext/derivedLabsHeadless.js 同形：
#   请求体 = AstroExtraCommon.chartParams(本命盘)（tradition / predictive 恒 false）+ 本页设置；
#   正文   = derivedAstroSnapshotText(变换后的整盘 | null, fields, 专属行)。
# 后端 astrostudy/transform_charts.py、zodiac_systems.py 算（JS 层不发 HTTP）；专属段由 vendored 上游
# utils/transformCharts.js 出（tools/auxLabs.js）；变换盘的整盘通用段走 engine/astro_snapshot.py（与本命盘同一份）。

_TRANSFORM_ENDPOINT = "/astroextra/transformchart"
_ZODIAC_ENDPOINT = "/astroextra/zodiacsystems"
# 只作用于快照 / 本页、不属于本命盘参数的键：不进后端请求体（变换盘的专属键由 transform_request_fields 按变换种类另发）。
_TRANSFORM_KNOB_KEYS = frozenset(TRANSFORM_FIELD_TO_SETTING)


class AuxLabRunners:
    # ── 变换盘（/astroextra/transformchart）─────────────────────────────────────

    @staticmethod
    def _transform_settings(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """页面键口径的设置（缺省补齐）+ 这种变换用不上、却被显式给了的选项。

        值已由 schema 读成规范值（auxlab_vocab 词表）。用不上的选项不下发、不进正文（上游页面在这种变换下根本不显示
        那个控件），回到缺省值并原样回执——不静默吞。"""
        settings = dict(TRANSFORM_DEFAULTS)
        given: dict[str, Any] = {}
        for field, setting in TRANSFORM_FIELD_TO_SETTING.items():
            value = payload.get(field)
            if value is None or value == "":
                continue
            given[setting] = value
        kind = given.get("kind", settings["kind"])
        if kind not in TRANSFORM_KIND_OPTIONS:
            raise ToolValidationError(
                bilingual(f"transformKind 认不出 {kind!r}。", f"Unrecognized transformKind: {kind!r}."),
                code="tool.invalid_option",
                details={"field": "transformKind", "value": kind, "accepted": list(TRANSFORM_KIND_OPTIONS)},
            )
        used = TRANSFORM_KIND_OPTIONS[kind]
        ignored: list[dict[str, Any]] = []
        for setting, value in given.items():
            if setting == "kind" or setting in used:
                settings[setting] = value
                continue
            ignored.append({
                "key": TRANSFORM_SETTING_TO_FIELD[setting],
                "value": value,
                "reason": bilingual(
                    f"{TRANSFORM_KIND_LABELS[kind]}不用「{TRANSFORM_OPTION_LABELS[setting]}」",
                    f"{kind} does not use {TRANSFORM_SETTING_TO_FIELD[setting]}",
                ),
                "used_by": [name for name, opts in TRANSFORM_KIND_OPTIONS.items() if setting in opts],
            })
        return settings, ignored

    def _transform_body(self, payload: dict[str, Any], request_fields: dict[str, Any]) -> dict[str, Any]:
        natal = {key: value for key, value in self._astroextra_natal_payload(payload).items() if key not in _TRANSFORM_KNOB_KEYS}
        return {**self._astroextra_chart_params(natal), **request_fields}

    def _run_transformchart_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        settings, ignored = self._transform_settings(payload)
        kind = settings["kind"]
        request_fields = transform_request_fields(settings)
        # 端点写字面量：算源生成器（gen_technique_provenance.py）按 AST 扫 runner 里的 _call_remote 取证。
        response = self._call_remote("/astroextra/transformchart", self._transform_body(payload, request_fields))
        if not isinstance(response, dict):
            response = {}
        # 后端对认不出的变换静默退回倒置盘：回来的种类与请求的不同 = 这张盘不是所要的那一种。
        if response.get("kind") != kind:
            raise ToolValidationError(
                bilingual(
                    f"{_TRANSFORM_ENDPOINT} 回的是「{response.get('kind')}」而不是请求的「{kind}」（后端不认得这种变换）。",
                    f"{_TRANSFORM_ENDPOINT} answered kind {response.get('kind')!r} instead of the requested {kind!r}.",
                ),
                code=tool_code("transformchart", "unknown_kind"),
                details={"tool": "transformchart", "requested": kind, "answered": response.get("kind")},
            )
        chart_wrap = response.get("chart") if isinstance(response.get("chart"), dict) else None
        if chart_wrap is None:
            # 人格盘 / 受孕盘要另找一个时刻起盘；找不到时后端回 momentFailed（不带 err：Java 见 err 就整体抛错）。
            # 上游页面此时显示「这张盘算不出这个时刻,高纬的受孕盘常有这种情况」、AI 快照为空；这里给结构化错误。
            raise ToolValidationError(
                bilingual(
                    f"{TRANSFORM_KIND_LABELS[kind]}算不出起盘时刻（高纬的受孕盘常有这种情况）：换一个对应宫头、基准星，或换一种变换。",
                    f"The {kind} chart has no solvable moment for this birth data (common for epoch charts at high latitudes): "
                    "try another house / planet, or another transform.",
                ),
                code=tool_code("transformchart", "empty"),
                details={
                    "tool": "transformchart", "endpoint": _TRANSFORM_ENDPOINT, "settings": settings,
                    "reason": "moment_failed" if response.get("momentFailed") else "no_chart",
                },
            )
        try:
            js = self.js_client.run("aux_labs", {"technique": "transformchart", "result": response, "settings": settings})
        except Exception as exc:
            raise ToolValidationError(
                bilingual(f"变换盘专属段排版失败：{exc}", f"transformchart: formatting the [变换盘] section failed: {exc}"),
                code=tool_code("transformchart", "snapshot_failed"),
                details={"tool": "transformchart", "settings": settings},
            ) from exc
        js = js if isinstance(js, dict) else {}
        if js.get("invalid"):
            parts = [f"{item.get('key')}={item.get('value')!r}" for item in js["invalid"] if isinstance(item, dict)]
            raise ToolValidationError(
                bilingual(f"变换盘设置取值无效：{'；'.join(parts)}。", f"transformchart setting(s) invalid: {'; '.join(parts)}."),
                code=tool_code("transformchart", "invalid_setting"),
                details={"tool": "transformchart", "invalid": js["invalid"]},
            )
        js_request = js.get("request_fields")
        if js_request != request_fields:
            # 请求体里「这种变换带哪些选项」是照上游 transformRequestOptions 手写的；vendored 上游函数重算的那份才是准的。
            raise ToolValidationError(
                bilingual(
                    f"变换盘的请求体与上游 transformRequestOptions 不一致（Python 发 {request_fields}，上游算 {js_request}）",
                    "transformchart: request fields diverge from the vendored upstream mapping",
                ),
                code="tool.transformchart_request_mismatch",
                details={"tool": "transformchart", "sent": request_fields, "upstream": js_request},
            )
        lines = [f"{line}" for line in js.get("lines") or []]
        if js.get("title") != "变换盘" or not lines:
            raise ToolValidationError(
                bilingual("变换盘专属段是空的（后端结果里没有可排版的内容）。", "transformchart: the [变换盘] section came back empty."),
                code=tool_code("transformchart", "empty_snapshot"),
                details={"tool": "transformchart", "settings": settings, "title": js.get("title")},
            )
        # 北交宫盘：盘面画的是「段头」，正文与宫主表要用真宫头（上游 transformSnapshotChart）。`raw.chart` 保留后端原样（画盘用）。
        houses = js.get("snapshot_houses")
        if isinstance(houses, list) and isinstance(chart_wrap.get("chart"), dict):
            chart_wrap = {**chart_wrap, "chart": {**chart_wrap["chart"], "houses": houses}}
        kind_def = js.get("kind") if isinstance(js.get("kind"), dict) else {}
        result: dict[str, Any] = {
            **chart_wrap,
            "transform": {
                "kind": kind,
                "label": kind_def.get("label") or TRANSFORM_KIND_LABELS[kind],
                "description": kind_def.get("desc"),
                "options_used": list(TRANSFORM_KIND_OPTIONS[kind]),
                "moment": response.get("moment"),
                "coordinatesMoved": response.get("coordinatesMoved"),
                "natalHorizon": response.get("natalHorizon"),
            },
            "settings": settings,
            "request": request_fields,
            "positions": response.get("positions", []),
            "rulers": response.get("rulers", []),
            "golden": response.get("golden", []),
            "raw": response,
            "_derivedSelf": {"title": "变换盘", "lines": lines},
        }
        if "vertical" in response:
            result["vertical"] = response.get("vertical")
        result["params_ignored"] = ignored
        if ignored:
            names = "、".join(f"{item['key']}={item['value']!r}" for item in ignored)
            result["_warnings"] = [bilingual(
                f"{TRANSFORM_KIND_LABELS[kind]}（{kind}）用不上这些选项，已忽略（未下发、不影响结果）：{names}；"
                f"各种变换用到哪些选项见 horosa_agent_guidance(tool_name=\"transformchart\").options_keys。",
                f"{kind} does not use these options; they were ignored (not sent, no effect): {names}.",
            )]
        return result

    # ── 黄道制（/astroextra/zodiacsystems）──────────────────────────────────────

    def _run_zodiacsystems_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        version = payload.get("zodiacVersion") or ZODIAC_VERSION_DEFAULT
        if version not in ZODIAC_VERSION_LABELS:
            raise ToolValidationError(
                bilingual(f"zodiacVersion 认不出 {version!r}。", f"Unrecognized zodiacVersion: {version!r}."),
                code="tool.invalid_option",
                details={"field": "zodiacVersion", "value": version, "accepted": list(ZODIAC_VERSION_LABELS)},
            )
        natal = {key: value for key, value in self._astroextra_natal_payload(payload).items() if key != "zodiacVersion"}
        response = self._call_remote("/astroextra/zodiacsystems", {**self._astroextra_chart_params(natal), "zodiacVersion": version})
        if not isinstance(response, dict):
            response = {}
        # 后端对认不出的版本静默退回十三星座甲本：回来的版本与请求的不同 = 落段是按另一个版本读的。
        if response.get("version") != version:
            raise ToolValidationError(
                bilingual(
                    f"{_ZODIAC_ENDPOINT} 回的是版本「{response.get('version')}」而不是请求的「{version}」（后端不认得这个黄道版本）。",
                    f"{_ZODIAC_ENDPOINT} answered version {response.get('version')!r} instead of the requested {version!r}.",
                ),
                code=tool_code("zodiacsystems", "unknown_kind"),
                details={"tool": "zodiacsystems", "requested": version, "answered": response.get("version")},
            )
        try:
            js = self.js_client.run("aux_labs", {"technique": "zodiacsystems", "result": response, "settings": {"version": version}})
        except Exception as exc:
            raise ToolValidationError(
                bilingual(f"黄道制专属段排版失败：{exc}", f"zodiacsystems: formatting the [黄道制] section failed: {exc}"),
                code=tool_code("zodiacsystems", "snapshot_failed"),
                details={"tool": "zodiacsystems", "zodiacVersion": version},
            ) from exc
        js = js if isinstance(js, dict) else {}
        if js.get("invalid"):
            raise ToolValidationError(
                bilingual(f"黄道制设置取值无效：zodiacVersion={version!r}。", f"zodiacsystems setting invalid: zodiacVersion={version!r}."),
                code=tool_code("zodiacsystems", "invalid_setting"),
                details={"tool": "zodiacsystems", "invalid": js["invalid"]},
            )
        lines = [f"{line}" for line in js.get("lines") or []]
        if js.get("title") != "黄道制" or not lines:
            # 上游 zodiacSnapshotLines：结果里没有 rows 即空（挂载面显示「缺失」）；skill 不落模板假导出。
            raise ToolValidationError(
                bilingual(
                    f"{_ZODIAC_ENDPOINT} 没有返回各点落段（上游此时显示「缺失」）。",
                    f"{_ZODIAC_ENDPOINT} returned no rows to format.",
                ),
                code=tool_code("zodiacsystems", "empty"),
                details={"tool": "zodiacsystems", "endpoint": _ZODIAC_ENDPOINT, "zodiacVersion": version},
            )
        # 这一页没有盘体（上游 derivedAstroSnapshotText(null, …)）：正文只有 [黄道制] 一段。
        snapshot_text = "\n".join([f"[{js['title']}]", *lines])
        version_info = js.get("version") if isinstance(js.get("version"), dict) else {}
        return {
            "version": version,
            "versionLabel": version_info.get("label") or ZODIAC_VERSION_LABELS[version],
            "galacticCenter": response.get("galacticCenter"),
            "rows": response.get("rows", []),
            "around": response.get("around", []),
            "year": response.get("year", []),
            "wheel": response.get("wheel", []),
            "houses13Cusps": response.get("houses13Cusps", []),
            "versions": response.get("versions", []),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="zodiacsystems", snapshot_text=snapshot_text),
        }
