"""七政四余 runner（GuolaoRunners）：希腊盘、七政四余盘（设置 / 农历 / 命主）、宿占。"""
from __future__ import annotations

import copy
import re
from typing import Any

from horosa_skill.errors import (
    HorosaSkillError,
    ToolTransportError,
    ToolValidationError,
    bilingual,
)
from horosa_skill.service import _clock
from horosa_skill.service._common import _ganzhi_year
from horosa_skill.service._context import _degrade
from horosa_skill.service.options_cn import _day_boundary_switches
from horosa_skill.service.text.chinese import (
    _apply_guolao_node_mode,
    _build_guolao_snapshot_text,
    _guolao_slash_date,
    _guolao_warn_missing_life_master,
    _moira_transit_moment,
)


def _guolao_year_from_date(date_text: Any) -> int:
    """上游 guolao/main/snapshot.js yearFromParams：日期串里第一个 `-?\\d{3,4}`（公元前前导负号保留；旧 [:4] 对
    '-0500-…' 取成 -50）；取不到 → 今年（上游 new Date().getFullYear()）。"""
    m = re.search(r"-?\d{3,4}", f"{date_text or ''}")
    return int(m.group(0)) if m else _clock.now().year


class GuolaoRunners:
    def _run_hellen_chart_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        remote_payload = {**payload, "predictive": 0}
        response = self._call_remote("/chart13", remote_payload)
        return response

    # 七政显示层四键（上游 techniqueMountSettings.js:1159-1175 挂载齿轮；缺省 = GuoLaoChartStyle.GUOLAO_DEFAULT_DISPLAY）。
    # 值域逐字同上游 normLifeMasterMode / normMinorLimitType / normTongxianBase / normLimitChildBase。
    # 认不出的值**报错**（不静默归一成缺省）：改这个参数，结果必须变 —— 拼错的值悄悄当缺省用就违背了这一条。
    # 第五键「大限年界」（上游页面左栏 GuoLaoInput.js:850 显示偏好 horosaGuolaoDisplay.limitYearBoundary，值域
    # GuoLaoChartStyle.GUOLAO_LIMIT_YEAR_BOUNDARIES，缺省 gregorian 公历元旦 = Moira；lichun/dongzhi 走本地节气表精算年界）：
    # 不在挂载齿轮里，但上游无头复算读的就是同一份全局显示偏好（getStoredGuolaoDisplay），改它 [大限] 起讫年与首限起点即变。
    _GUOLAO_DISPLAY_KEYS: dict[str, tuple[str, tuple[Any, ...], Any]] = {
        "guolaoLifeMasterMode": ("lifeMasterMode", ("gong", "du", "dudegrade"), "gong"),
        # 'gudu' = 钉死古度限度法（挂载齿轮 techniqueMountSettings.js:1371-1374 的显式项），上游
        # guolaoSnapshotDisplayFromFields（main/snapshot.js:1104-1105）映射成 '' —— 与缺省同口径。
        "guolaoMinorLimitType": ("minorLimitType", ("", "gudu", "minor", "month", "tong", "dongwei"), ""),
        "guolaoTongxianBase": ("tongxianBase", ("tong10", "gu9", "xu11"), "tong10"),
        "guolaoLimitChildBase": ("limitChildBase", (9, 10), 9),
        "guolaoLimitYearBoundary": ("limitYearBoundary", ("gregorian", "lichun", "dongzhi"), "gregorian"),
    }

    def _guolao_display_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        display: dict[str, Any] = {}
        for key, (disp_key, allowed, default) in self._GUOLAO_DISPLAY_KEYS.items():
            raw = payload.get(key)
            if raw is None or (raw == "" and disp_key != "minorLimitType"):
                display[disp_key] = default
                continue
            value: Any = f"{raw}".strip()
            if disp_key == "limitChildBase":
                try:
                    value = int(raw)
                except (TypeError, ValueError):
                    value = raw
            if value not in allowed:
                raise ToolValidationError(
                    bilingual(
                        f"七政四余 {key} 取值无效：{raw!r}（可选：{'、'.join(repr(a) for a in allowed)}）。",
                        f"guolao_chart {key} is invalid: {raw!r} (allowed: {', '.join(repr(a) for a in allowed)}).",
                    ),
                    code="tool.guolao_invalid_display_setting",
                    details={"field": key, "value": raw, "allowed": list(allowed)},
                )
            display[disp_key] = "" if disp_key == "minorLimitType" and value == "gudu" else value
        return display

    # 七政起盘口径（上游页面左栏 / 挂载齿轮 techniqueMountSettings.js:1123-1181；GuoLaoChartStyle.js 各 getStored* 缺省）。
    # 值域逐字同上游 normalize*/getStored*（认不出的值报错，不静默归一成缺省）。宿度制值域 = guolaoData.SU28_MODE_LABEL 的键
    # 0–8（2=回归今宿 缺省；黄仪 2/3/4/6，赤仪 0/1/5/7/8）。
    _GUOLAO_DIZHI = tuple("子丑寅卯辰巳午未申酉戌亥")
    _GUOLAO_CHART_SETTING_VALUES: dict[str, tuple[Any, ...]] = {
        "guolaoLifeMode": ("asc", "yumao", "cotrans", "gumao", *_GUOLAO_DIZHI),
        "guolaoBodyMode": ("taiyin", "youjin", *_GUOLAO_DIZHI),
        "guolaoNodeMode": ("northKetuSouthRahu", "northRahuSouthKetu"),
        "guolaoTrueSolarTime": ("true", "mean", "off"),
        "guolaoNodeType": ("mean", "true"),
        "guolaoLilithType": ("mean", "true"),
        "guolaoTuibianMethod": ("jiyuan", "jintui", "huiyuan"),
        "guolaoGufaPrecess": ("0", "1"),
        "guolaoEqTropicalAnchor": ("dongzhi", "chunfen"),
        # v3.13.0 行星时制式（星盘设置全局键；七政 main/params.js:20-27 guolaoPlanetaryHourMethod，缺省 sunrise）。
        "planetaryHourMethod": ("sunrise", "unequal", "equal24"),
    }
    # 只在某些宿度制下生效的子选项（fieldsToParams GuoLaoChartMain.js:2360-2394 的门控）：别的制下上游不下发。
    _GUOLAO_MODE_GATED: dict[str, tuple[int, ...]] = {
        "guolaoAyanamsa": (4,),
        "guolaoTuibianMethod": (6,),
        "guolaoGufaPrecess": (6,),
        "guolaoEqTropicalAnchor": (7, 8),
    }
    # GuoLaoChartStyle.js:19 GUOLAO_DEFAULT_SU28_MODE。上游 v3.13.0 由 2（回归今宿）改为 0（荀爽距星）：
    # 「与新盘种子 / 后端缺省同值（全站统一）」。七政择日的扫描缺省仍是 2（QizhengZeriMain.js:38，另一个设置，未变）。
    _GUOLAO_DEFAULT_SU28_MODE = 0

    def _guolao_chart_settings(self, payload: dict[str, Any]) -> tuple[int, dict[str, str]]:
        """宿度制 + 起盘口径键（校验后的字符串值）。返回 (su28Mode, {键: 值})；缺省键不在结果里。"""
        raw_mode = payload.get("doubingSu28")
        if raw_mode is None or raw_mode == "":
            su28 = self._GUOLAO_DEFAULT_SU28_MODE
        elif isinstance(raw_mode, bool):
            # 旧布尔语义（perchart.parseSu28Mode：True→1 斗柄定房法 / False→0 荀爽距星）——照后端解释，不再当缺省。
            su28 = 1 if raw_mode else 0
        else:
            try:
                su28 = int(f"{raw_mode}".strip())
            except ValueError:
                su28 = -1
            if su28 not in range(0, 9):
                raise ToolValidationError(
                    bilingual(
                        f"七政四余 doubingSu28（宿度制）取值无效：{raw_mode!r}（可选 0–8：0 荀爽距星〔缺省〕/2 回归今宿/3 回归古制开禧/4 恒星制/"
                        "6 授时历古法 · 1 斗柄定房法/5 恒星制·现代天赤/7 赤道回归(元明)/8 赤道回归(实时)）。",
                        f"guolao_chart doubingSu28 (mansion system) is invalid: {raw_mode!r} (allowed 0–8, default 0).",
                    ),
                    code="tool.guolao_invalid_display_setting",
                    details={"field": "doubingSu28", "value": raw_mode, "allowed": list(range(0, 9))},
                )
        settings: dict[str, str] = {}
        for key, allowed in self._GUOLAO_CHART_SETTING_VALUES.items():
            raw = payload.get(key)
            if raw is None or raw == "":
                continue
            value = ("1" if raw else "0") if isinstance(raw, bool) else f"{raw}".strip()
            if value not in allowed:
                raise ToolValidationError(
                    bilingual(
                        f"七政四余 {key} 取值无效：{raw!r}（可选：{'、'.join(allowed)}）。",
                        f"guolao_chart {key} is invalid: {raw!r} (allowed: {', '.join(allowed)}).",
                    ),
                    code="tool.guolao_invalid_display_setting",
                    details={"field": key, "value": raw, "allowed": list(allowed)},
                )
            settings[key] = value
        if payload.get("guolaoAyanamsa") not in (None, ""):
            settings["guolaoAyanamsa"] = f"{payload.get('guolaoAyanamsa')}".strip()
        for key, modes in self._GUOLAO_MODE_GATED.items():
            if key in settings and su28 not in modes:
                _degrade(
                    "guolao: %s given but su28 mode %s does not use it", key, su28,
                    note=f"七政四余 {key} 只在宿度制 {'/'.join(str(m) for m in modes)} 下生效，本盘宿度制 {su28} 不下发它（上游同口径）。",
                )
                settings.pop(key)
        return su28, settings

    def _guolao_remote_payload(self, payload: dict[str, Any], su28: int, settings: dict[str, str]) -> dict[str, Any]:
        """/chart 请求体：上游 GuoLaoChartMain.fieldsToParams（:2339-2400）七政专属键的条件透传逐条对齐。"""
        remote = {k: v for k, v in payload.items() if k not in self._GUOLAO_CHART_SETTING_VALUES and k != "guolaoAyanamsa"}
        remote.update({
            "tradition": True,
            "predictive": False,
            "hsys": payload.get("hsys", 0),
            "doubingSu28": su28,
            # 恒星制（4）走恒星黄道 + guolaoZhengSidereal；其余制回归黄道（:2351-2356）。
            "zodiacal": 1 if su28 == 4 else payload.get("zodiacal", 0),
            "guolaoZhengSidereal": 1 if su28 == 4 else 0,
            # 命度法恒下发（:2357）；身宫法仅非缺省（:2396-2399）。
            "guolaoLifeMode": settings.get("guolaoLifeMode", "asc"),
        })
        # G2 恒星制岁差：仅恒星宿度制 + 选了 ayanāṃśa 才透传（复用 siderealAyanamsa 键，:2362-2366）。
        if su28 == 4 and settings.get("guolaoAyanamsa"):
            remote["siderealAyanamsa"] = settings["guolaoAyanamsa"]
        # G6 报时星太阳时：仅非缺省（mean/off）才透传（:2369-2372）。
        if settings.get("guolaoTrueSolarTime") in ("mean", "off"):
            remote["trueSolarTime"] = settings["guolaoTrueSolarTime"]
        # 行星时制式：仅非缺省（不等时 / 廿四时）才透传（v3.13.0 main/params.js:158-162）—— 报时星按该制式取，
        # 太阳时三档在这两种制式下才真正分开；缺省不发 = 零回归。
        if settings.get("planetaryHourMethod") in ("unequal", "equal24"):
            remote["planetaryHourMethod"] = settings["planetaryHourMethod"]
        # G10-13 四余取法：仅真值才透传（:2375-2380）。
        if settings.get("guolaoNodeType") == "true":
            remote["guolaoNodeType"] = "true"
        if settings.get("guolaoLilithType") == "true":
            remote["guolaoLilithType"] = "true"
        # WP-D 授时历古法（用制 6）：推变黄道术法 + 古宿随岁差（:2382-2388）。
        if su28 == 6 and settings.get("guolaoTuibianMethod") in ("jintui", "huiyuan"):
            remote["guolaoTuibianMethod"] = settings["guolaoTuibianMethod"]
        if su28 == 6 and settings.get("guolaoGufaPrecess") == "1":
            remote["guolaoGufaPrecess"] = 1
        # 赤道回归制（用制 7/8）锚点：仅 chunfen 才透传（:2390-2394）。
        if su28 in (7, 8) and settings.get("guolaoEqTropicalAnchor") == "chunfen":
            remote["guolaoEqTropicalAnchor"] = "chunfen"
        if settings.get("guolaoBodyMode", "taiyin") != "taiyin":
            remote["guolaoBodyMode"] = settings["guolaoBodyMode"]
        return remote

    @staticmethod
    def _guolao_fields(su28: int, settings: dict[str, str]) -> dict[str, Any]:
        """JS 段 builder 的 fields（上游页面 fields 形：{键: {value}}）：宿度制 + 起盘口径键。"""
        fields: dict[str, Any] = {"doubingSu28": {"value": su28}}
        for key in ("guolaoLifeMode", "guolaoBodyMode", "guolaoNodeMode", "guolaoTrueSolarTime", "guolaoNodeType", "guolaoLilithType",
                    "planetaryHourMethod"):
            if key in settings:
                fields[key] = {"value": settings[key]}
        return fields

    def _guolao_fetch_nongli(self, payload: dict[str, Any], date: Any, time_text: Any, *, role: str) -> dict[str, Any] | None:
        """某时刻的四柱对象 = 上游 Java /chart 挂在 chart.nongli 的同一个 OnlyFourColumns.getNongli()（ChartController.java:78-99：
        缺省 nongliTimeAlg=0 真太阳时、日界两键缺省 1/1）。skill 的 /chart 走 Python 排盘服务、响应里没有 nongli →
        另取 Java /nongli/time（NongliController.java:26-60 同一构造）。取不到返回 None 并进 warnings（`role` = 本命/流年）。"""
        try:
            nongli = self._call_remote(
                "/nongli/time",
                {
                    "date": date,
                    "time": time_text,
                    "zone": payload.get("zone"),
                    "lon": payload.get("lon"),
                    "lat": payload.get("lat"),
                    "gpsLat": payload.get("gpsLat"),
                    "gpsLon": payload.get("gpsLon"),
                    **_day_boundary_switches(payload),
                    "timeAlg": 0,
                    "ad": payload.get("ad", 1),
                },
            )
        except Exception as exc:  # noqa: BLE001 — 四柱只影响神煞/虚实/化曜/月限的取值来源，不许带崩整盘
            if role == "本命":
                note = (
                    "七政四余 本命四柱（/nongli/time）不可用：Moira 规则层按公历年干支单柱起（[神煞]/[虚实]/[本命化曜] 缺月日时三柱）、"
                    "[三主与化曜] 生年化曜/命宫配干按公历年干支回退、[限法实算] 月限行省略。"
                )
            else:
                note = f"七政四余 {role}盘四柱（/nongli/time）不可用：[流年流曜] 的流年年柱按公历年干支回退、缺月日时三柱。"
            _degrade("guolao %s nongli (/nongli/time) unavailable: %s", role, exc, note=note)
            return None
        return nongli if isinstance(nongli, dict) and nongli else None

    @staticmethod
    def _guolao_attach_nongli(chart_response: Any, nongli: dict[str, Any] | None) -> Any:
        """把四柱挂到 chart.nongli（上游 Java /chart 的响应形：ChartController.java:98 chart.put("nongli", map)）。浅拷贝，不改入参。"""
        if not isinstance(chart_response, dict) or not isinstance(nongli, dict) or not nongli:
            return chart_response
        chart_obj = chart_response.get("chart") if isinstance(chart_response.get("chart"), dict) else {}
        return {**chart_response, "chart": {**chart_obj, "nongli": nongli}}

    def _guolao_info_sections(
        self,
        payload: dict[str, Any],
        response: dict[str, Any],
        display: dict[str, Any],
        moira_rules: dict[str, Any] | None,
        guolao_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """[起盘信息] 命度/身度/宿主行 + [大限] + [三主与化曜] + [限法实算] + [七政四余宫位与二十八宿星曜] / [神煞] / [相位]
        （vendored 上游 builder，JS `info_sections`）。

        `response` 已由 runner 挂好本命四柱（chart.nongli，见 _guolao_fetch_nongli）——上游 root 是 Java /chart，四柱本就在
        chart.nongli 上；取不到时事实层照上游回退（年柱按公历年干支、月限行省略、[神煞] 只剩 rules 源），说明已进 warnings。
        """
        date_text = f"{payload.get('date') or ''}"
        slash_date = _guolao_slash_date(date_text)
        root = response
        transit_date, transit_time = _moira_transit_moment(payload)
        guolao_params = {
            "date": slash_date,
            "time": payload.get("time"),
            "zone": payload.get("zone"),
            "lat": payload.get("lat"),
            "lon": payload.get("lon"),
            "gpsLat": payload.get("gpsLat"),
            "gpsLon": payload.get("gpsLon"),
            "ad": payload.get("ad", 1),
        }
        transit_params = {
            **guolao_params,
            "date": f"{transit_date}".replace("-", "/", 2),
            "time": transit_time,
            "predictive": 1,
        }
        fields = guolao_fields if guolao_fields is not None else {}
        try:
            js = self.js_client.run(
                "guolao_moira",
                {
                    "action": "info_sections",
                    "chart": root,
                    "params": guolao_params,
                    "transitParams": transit_params,
                    "display": display,
                    "fields": fields,
                    "moiraRules": moira_rules or {},
                },
            )
        except Exception as exc:  # noqa: BLE001 — 七段来自 JS；失败 → [大限]/宫位表/相位回退 Python 旧行式、其余缺席，进 warnings
            _degrade(
                "guolao info sections build failed: %s", exc,
                note=(
                    "七政四余 [大限] 回退内置旧算法（首限四舍童限、元旦年界）、[七政四余宫位与二十八宿星曜]/[相位] 回退旧行式、"
                    "[神煞] 本次为「无」，[三主与化曜]/[限法实算] 与命度/身度行本次未产出（JS 段 builder 失败）。"
                ),
            )
            return {}
        js = js if isinstance(js, dict) else {}
        for err in js.get("errors") or []:
            if isinstance(err, dict):
                _degrade(
                    "guolao info section %s degraded: %s", err.get("section"), err.get("message"),
                    note=f"七政四余 [{err.get('section') or '?'}]：{err.get('message') or '未知错误'}",
                )
        return js

    def _guolao_attach_life_master(
        self, response: dict[str, Any], remote_payload: dict[str, Any], settings: dict[str, Any]
    ) -> dict[str, Any]:
        """七政命度点（LifeMasterDeg74）：上游的 /chart 是 Java ChartController（ChartController.java:96 → BaZi.genLifeMasterDeg，
        按 guolaoLifeMode 日出安命/赤黄转换/遇卯/自定命宫各有专算法）在 Python 排盘之上**追加**的一个盘面对象；本仓 /chart 走
        Python 排盘服务，响应里没有它。命度法非「占星上升」时向 Java /chart（backend="java"，同一请求体）取该点挂进 chart.objects，
        下游（vendored lifeDegree / 宫位表宫序 / [大限] / [三主与化曜] / Moira 规则层 firstPresent）即按上游同一回退序拿到命度点。
        守卫：Java 盘与 Python 盘必须是同一张（太阳/上升黄经逐值相等，Java 只是聚合层）；不一致不采用（说出来），Java 不可用
        → 留给 _guolao_warn_missing_life_master 告警、命度按上游同一回退序落回上升。"""
        mode = f"{settings.get('guolaoLifeMode') or 'asc'}".strip() or "asc"
        chart = response.get("chart") if isinstance(response, dict) else None
        objects = chart.get("objects") if isinstance(chart, dict) else None
        if mode == "asc" or not isinstance(objects, list):
            return response
        if any(isinstance(obj, dict) and obj.get("id") == "LifeMasterDeg74" for obj in objects):
            return response
        try:
            java = self._call_remote("/chart", remote_payload, backend="java")
        except Exception as exc:  # noqa: BLE001 — Java 不可用：命度回落上升，由 _guolao_warn_missing_life_master 说出来
            _degrade("guolao LifeMasterDeg74 via Java /chart failed: %s", exc)
            return response
        java_chart = java.get("chart") if isinstance(java, dict) else None
        java_objects = java_chart.get("objects") if isinstance(java_chart, dict) else None
        by_id_java = {obj.get("id"): obj for obj in (java_objects or []) if isinstance(obj, dict)}
        life = by_id_java.get("LifeMasterDeg74")
        if not isinstance(life, dict):
            _degrade("guolao: Java /chart returned no LifeMasterDeg74 for lifeMode=%s", mode)
            return response
        by_id = {obj.get("id"): obj for obj in objects if isinstance(obj, dict)}
        for anchor in ("Sun", "Asc"):
            mine, theirs = by_id.get(anchor), by_id_java.get(anchor)
            try:
                same = abs(float(mine.get("lon")) - float(theirs.get("lon"))) < 1e-6
            except (AttributeError, TypeError, ValueError):
                same = False
            if not same:
                _degrade(
                    "guolao: Java /chart %s lon differs from python chart; LifeMasterDeg74 not adopted", anchor,
                    note=f"七政命度点：Java /chart 与本盘的 {anchor} 黄经不一致，命度点不采用（两端盘面不是同一张），命度按上升计。",
                )
                return response
        enriched = dict(response)
        enriched_chart = dict(chart)
        enriched_chart["objects"] = [*objects, copy.deepcopy(life)]
        enriched["chart"] = enriched_chart
        enriched["lifeMasterPoint"] = {
            "source": "java:/chart", "lifeMode": mode, "lon": life.get("lon"), "sign": life.get("sign"),
            "signlon": life.get("signlon"), "house": life.get("house"),
        }
        return enriched

    def _run_guolao_chart_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 显示层四键 + 起盘口径先校验（非法值在任何后端往返之前就报错）。
        display = self._guolao_display_settings(payload)
        # 🔴 宿度制缺省 = 上游 GUOLAO_DEFAULT_SU28_MODE（v3.13.0 起 0 荀爽距星）。更早发 doubingSu28=True，后端
        # parseSu28Mode 把 True 解释成 1（斗柄定房法，赤仪）—— 宿位、显示坐标（displayCoord）、格局判据全随之偏。
        su28, guolao_settings = self._guolao_chart_settings(payload)
        remote_payload = self._guolao_remote_payload(payload, su28, guolao_settings)
        guolao_fields = self._guolao_fields(su28, guolao_settings)
        response = _apply_guolao_node_mode(self._call_remote("/chart", remote_payload), guolao_settings)
        # 本命四柱挂到 chart.nongli —— 上游的盘是 Java /chart（四柱本就在 chart.nongli），下游一切都吃它：政余格局的神煞行
        # （buildGodRowsFromChart 读 chart.nongli.bazi.guolaoGods）、Moira 规则层四柱（MoiraPropRuleEngine.readPoles 读
        # chartObj.chart.nongli.bazi，缺则只剩公历年干支单柱 → [神煞]/[虚实]/[本命化曜] 全按一柱算）、[三主与化曜]/[限法实算]。
        # 此前只在 [三主与化曜] 一处现挂，规则层与格局拿的都是无四柱盘。
        response = self._guolao_attach_nongli(
            response, self._guolao_fetch_nongli(payload, payload.get("date"), payload.get("time"), role="本命")
        )
        # 命度法非「占星上升」→ 命度点 LifeMasterDeg74 由 Java /chart（上游 ChartController → BaZi.genLifeMasterDeg）算，Python
        # 排盘服务不出；向 Java 取同一张盘的该点挂进 objects（盘面一致性有守卫），取不到才落回上升并告警。
        response = self._guolao_attach_life_master(response, remote_payload, guolao_settings)
        _guolao_warn_missing_life_master(response, guolao_settings.get("guolaoLifeMode", "asc"))
        # 政余格局 (星阙 v2.6.x Moira DSL)：vendored JS buildLocalMoiraPatterns 评估盘面物象格局。
        # 失败不阻塞既有段（→ '无'），与 星阙 buildGuolaoPatternSection 的 try/catch 一致。
        pattern_text: str | None = None
        patterns: Any = None
        try:
            # 🔴 params 必须是**起盘时刻**，不是 /chart 信封。引擎读 `params.time`（判昼夜，
            # guolaoMoira.js:390）与 `params.date`（判冬令，:397），而信封顶层与其 `params` 子对象
            # 都没有 date/time（只有 `birth`）——此前传 `response` 等于两者恒缺省：
            # isDay 恒真（夜生盘拿天贵而非玉贵、孤月独明永不触发），isWinter 恒假（冬令排除永不生效）。
            # 段照出、格局照列，只有判据是错的。
            js = self.js_client.run("guolao_moira", {
                "chart": response,
                # 命度法/宿度制随 fields（上游 buildGuolaoPatternSection(result, fields, params) 同参）；恒星制判据读
                # params.doubingSu28 / guolaoZhengSidereal（guolaoMoira.js:610）。
                "fields": guolao_fields,
                "params": {
                    "date": payload.get("date"), "time": payload.get("time"),
                    "doubingSu28": su28, "guolaoZhengSidereal": remote_payload.get("guolaoZhengSidereal"),
                },
            })
            if isinstance(js, dict):
                pattern_text = js.get("snapshot_text")
                patterns = js.get("data", {}).get("patterns") if isinstance(js.get("data"), dict) else None
        except Exception as exc:  # noqa: BLE001 - degrade to '无', never break the guolao chart
            _degrade("guolao_moira pattern eval failed: %s", exc)
        # [星曜庙旺与星点动态]：上游导出的纯函数，只吃 /chart 响应（不需要 Moira 规则服务）。
        # 同批的 [虚实]/[本命化曜]/[流年流曜] 读 moiraRules.weakSolid / .yearStars，来自 **Java** 聚合层的
        # /qizheng/moira（v0.36.0 接活；此前误记为「开源 astropy 无该路由」而永久排除，见 LESSONS）。
        dignity_text: str | None = None
        try:
            js2 = self.js_client.run("guolao_star_dignity", {"chart": response, "fields": guolao_fields})
            if isinstance(js2, dict):
                dignity_text = f"{js2.get('text') or ''}".strip() or None
        except Exception as exc:  # noqa: BLE001 - 富化失败只是该段不出
            _degrade("guolao star dignity build failed: %s", exc)
        # [虚实]/[本命化曜]/[流年流曜]（v0.36.0 C1）：Java /qizheng/moira 规则层 + 流年盘二次铸盘。
        # Java 不可用（A5 冷却快速失败 / 降级）→ 三段缺席并进 envelope.warnings，其余段不受影响（optional 段）。
        moira_sections: dict[str, str] = {}
        moira_rules_slim: dict[str, Any] | None = None
        moira_rules_full: dict[str, Any] | None = None
        if payload.get("moiraRules", True) is not False:
            try:
                transit_date, transit_time = _moira_transit_moment(payload)
                moira_params = {
                    **remote_payload,
                    "guolaoLifeMode": guolao_settings.get("guolaoLifeMode", "asc"),
                    "guolaoBodyMode": guolao_settings.get("guolaoBodyMode", "taiyin"),
                }
                transit_params = {**moira_params, "date": transit_date, "time": transit_time, "predictive": True}
                # 流年盘同本命盘一样经罗计换位（上游 applyGuolaoNodeMode(tRaw, steppedFields)，GuoLaoChartMain.js:2570）。
                transit_chart = _apply_guolao_node_mode(
                    self._call_remote("/chart", {k: v for k, v in transit_params.items() if v is not None}), guolao_settings
                )
                # 流年盘同样挂流年时刻的四柱（上游流年盘也是 Java /chart；规则层 transitPoles 读 transitChartObj.chart.nongli）。
                transit_chart = self._guolao_attach_nongli(
                    transit_chart, self._guolao_fetch_nongli(payload, transit_date, transit_time, role="流年")
                )
                rules = self._call_remote(
                    "/qizheng/moira",
                    {"params": moira_params, "chartObj": response, "transitParams": transit_params, "transitChartObj": transit_chart},
                )
                js3 = self.js_client.run(
                    "guolao_moira",
                    {"action": "rules_sections", "moiraRules": rules, "transitYearGz": _ganzhi_year(_guolao_year_from_date(transit_date))},
                )
                sections = js3.get("sections") if isinstance(js3, dict) else None
                if isinstance(sections, dict):
                    moira_sections = {k: f"{v or ''}".strip() for k, v in sections.items()}
                if isinstance(rules, dict):
                    moira_rules_full = rules
                    moira_rules_slim = {
                        k: rules.get(k) for k in ("weakSolid", "yearStars", "transitYearStars", "natalYearStars", "godHits") if k in rules
                    }
            except Exception as exc:  # noqa: BLE001 — 三段为 optional；说明进 warnings
                _degrade(
                    "guolao moira rules (/qizheng/moira) unavailable: %s", exc,
                    note=(
                        "七政四余 [虚实]/[本命化曜]/[流年流曜] 本次未产出（Java /qizheng/moira 不可用或流年盘失败），"
                        "[神煞] 回退历法四柱神煞（上游 buildHouseGodsSection 同一回退），其余段不受影响。"
                    ),
                )
        info_sections = self._guolao_info_sections(payload, response, display, moira_rules_full, guolao_fields)
        snapshot_text = _build_guolao_snapshot_text(
            remote_payload, response, pattern_text=pattern_text, info_sections=info_sections
        )
        if dignity_text:
            # 段序对齐上游：紧跟 [七政四余宫位与二十八宿星曜]、在 [神煞] 之前。
            marker = "[神煞]"
            at = snapshot_text.find(marker)
            snapshot_text = (
                f"{snapshot_text[:at]}{dignity_text}\n\n{snapshot_text[at:]}" if at >= 0
                else f"{snapshot_text}\n\n{dignity_text}"
            )
        moira_blocks = [
            f"[{title}]\n{moira_sections.get(key)}"
            for title, key in (("虚实", "weakSolid"), ("本命化曜", "birthStars"), ("流年流曜", "transitStars"))
            if moira_sections.get(key)
        ]
        if moira_blocks:
            # 段序对齐上游 aiExport preset：[大限] 之后、[政余格局] 之前。
            marker = "[政余格局]"
            at = snapshot_text.find(marker)
            joined = "\n\n".join(moira_blocks)
            snapshot_text = f"{snapshot_text[:at]}{joined}\n\n{snapshot_text[at:]}" if at >= 0 else f"{snapshot_text}\n\n{joined}"
        response = dict(response)
        response["snapshot_text"] = snapshot_text
        response["guolaoPatterns"] = patterns
        if moira_rules_slim is not None:
            response["guolaoMoiraRules"] = moira_rules_slim
        response["export_snapshot"] = self._augment_export_payload(technique="guolao", snapshot_text=snapshot_text)
        return response

    # 宿度制九档（perchart.py:54-62 SU28_MODE_* / parseSu28Mode :731-748；上游 newChartSeeds.js:48 check 0–8）。
    _SU28_MODES = frozenset(range(9))

    def _run_suzhan_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        """宿占（F11）：与上游页面同源 —— 盘 = Java /chart（ChartController 附农历四柱 chart.nongli），
        快照 = vendored buildSuzhanSnapshotText（SuZhanMain.js:396-428）。

        v0.40 前：doubingSu28 当 bool（缺省 True=斗柄定房，上游缺省 0 且有九档）、houseStartMode 缺省 1（上游 0=八字公式）
        且快照是手写 port 根本不读它、hsys 缺省 0（上游页面 1）、宫位只印 House1…。人事十二宫「八字公式起盘」要
        农历时支 → 只有 Java /chart 带 nongli（Python chart 服务不带），所以缺省档走 Java；ASC 档不需要农历，照走 chart 服务。
        """
        raw_su28 = payload.get("doubingSu28", 0)
        su28 = int(raw_su28) if isinstance(raw_su28, (bool, int)) or f"{raw_su28}".lstrip("-").isdigit() else raw_su28
        if su28 not in self._SU28_MODES:
            raise ToolValidationError(
                f"宿度制 doubingSu28={raw_su28!r} 不在 0–8 / doubingSu28 must be one of 0-8",
                code="tool.suzhan_su28_invalid",
                details={"field": "doubingSu28", "value": raw_su28, "valid": sorted(self._SU28_MODES)},
            )
        house_start = 1 if payload.get("houseStartMode") in (1, True, "1") else 0
        remote_payload = {**payload, "predictive": False, "doubingSu28": su28}
        nongli_alg = payload.get("nongliTimeAlg")
        if nongli_alg is not None:
            # ChartController.java:84-88 [Q-419/T-383]：农历四柱时间算法 0 真太阳时（缺省）/1 直接时间/3 平太阳时。
            if f"{nongli_alg}" not in ("0", "1", "3"):
                raise ToolValidationError(
                    f"nongliTimeAlg={nongli_alg!r} 只收 0/1/3 / nongliTimeAlg must be 0, 1 or 3",
                    code="tool.suzhan_nongli_timealg_invalid",
                    details={"field": "nongliTimeAlg", "value": nongli_alg, "valid": [0, 1, 3]},
                )
            remote_payload["nongliTimeAlg"] = int(nongli_alg)
        java_failed = False
        if house_start == 0:
            try:
                response = self._call_remote("/chart", remote_payload, backend="java")
            except HorosaSkillError as exc:
                java_failed = True
                _degrade(
                    "suzhan Java /chart unavailable, falling back to chart service: %s", exc,
                    note="宿占「八字公式起盘」要 Java /chart 的农历四柱，本次 Java 不可用 → 改由 chart 服务起盘，"
                         f"人事十二宫按 ASC 起（上游缺农历时同）。原因：{exc}",
                )
                response = self._call_remote("/chart", remote_payload)
        else:
            response = self._call_remote("/chart", remote_payload)
        js = self.js_client.run(
            "suzhan",
            {
                "chart": response,
                "params": {
                    "date": payload.get("date"),
                    "time": payload.get("time"),
                    "zone": payload.get("zone"),
                    "lon": payload.get("lon"),
                    "lat": payload.get("lat"),
                    "szchart": payload.get("szchart"),
                    "szshape": payload.get("szshape"),
                    "doubingSu28": su28,
                    "houseStartMode": house_start,
                },
            },
        ) or {}
        data = js.get("data") if isinstance(js.get("data"), dict) else {}
        snapshot_text = f"{js.get('text') or ''}".strip()
        if not snapshot_text:
            raise ToolTransportError(
                "宿占快照未产出 / suzhan snapshot was not produced.",
                code="tool.suzhan_snapshot_failed",
                details={"data": data},
            )
        if house_start == 0 and not java_failed and not data.get("nongliHour"):
            _degrade(
                "suzhan chart carries no nongli hour; house start fell back to ASC",
                note="宿占人事十二宫缺省按八字公式起盘，但本盘没有农历时支（Java /chart 未附 nongli）→ 已按 ASC 起（上游同）。",
            )
        return {
            **response,
            "compute_sources": {"chart": "java" if house_start == 0 and not java_failed else "chart_service"},
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="suzhan", snapshot_text=snapshot_text),
        }
