"""卜卦与择时 runner（HoraryElectionRunners）：horary、election（本命附加、返照求解、主限命中）。"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from horosa_skill.errors import ToolTransportError, ToolValidationError, bilingual
from horosa_skill.service._common import (
    _chart_body_lon_speed,
    _drop_none,
    _fmt_moment,
    _js_math_round,
)
from horosa_skill.service._context import _degrade


class HoraryElectionRunners:
    # 卜卦 / 择日 JS 引擎的「请求顶层」转交：判读全局层（judgeLayerOverrides 同形）与页面覆盖都从这里取。
    # 只收标量（dict/list 形的 orbs/customTerms*/natal 与判读无关，且会把 JS 管道撑大）。
    _DIVINATION_PARAM_SKIP = frozenset({"options", "natal", "chart", "datetime", "dirZone", "dirLat", "dirLon"})

    @classmethod
    def _divination_params(cls, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            k: v for k, v in payload.items()
            if k not in cls._DIVINATION_PARAM_SKIP and not isinstance(v, (dict, list, tuple))
        }

    @staticmethod
    def _raise_invalid_divination_inputs(tool: str, invalid: Any) -> None:
        if not isinstance(invalid, list) or not invalid:
            return
        parts = [
            f"{item.get('key')}={item.get('value')!r}（可选：{item.get('allowed')}）"
            for item in invalid if isinstance(item, dict)
        ]
        raise ToolValidationError(
            bilingual(
                f"{tool} 设置取值无效：{'；'.join(parts)}。",
                f"{tool} setting(s) invalid: {'; '.join(parts)}.",
            ),
            code=f"tool.{tool}_invalid_setting",
            details={"invalid": invalid},
        )

    def _horary_backend_fields(self, payload: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        """流派档 → /chart 字段补丁（JS horary action=backend_fields，即上游 horaryBackendFields(school, overrides)）。

        上游页面 `{ zodiacal: 0, ...horaryBackendFields(school) }`（HoraryMain.js:543）、挂载再生 aiAnalysisContext.js:2264：
        宫制 / 界系 / 星群 / 福点反转 / 三分集随流派下发；显式覆盖（options 或卜卦自己的 hsys/termsVariant/
        geminiBoundEmended/tradition/tripSystem）压过流派。取不到就不能起盘——宫头、宫主、尊贵全随它变。"""
        js = self.js_client.run(
            "horary",
            {"action": "backend_fields", "school": payload.get("school") or "classical", "options": payload.get("options"), "params": params},
        )
        data = js.get("data") if isinstance(js, dict) else None
        fields = data.get("backendFields") if isinstance(data, dict) else None
        if not isinstance(fields, dict) or fields.get("hsys") is None:
            raise ToolTransportError(
                "卜卦流派起盘字段取不到（JS horary backend_fields 返回形状异常）。",
                code="tool.horary_backend_fields_failed",
                details={"school": payload.get("school") or "classical", "response_keys": sorted(js) if isinstance(js, dict) else None},
            )
        return data

    def _run_horary_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 卜卦 (horary): cast the traditional chart at the question moment, then run the vendored 星阙
        # horary engine (runHorary + buildHorarySnapshot) over it. category drives the quesited house.
        category = f"{payload.get('category') or 'general'}".strip() or "general"
        params = self._divination_params(payload)
        backend = self._horary_backend_fields(payload, params)
        backend_fields: dict[str, Any] = dict(backend["backendFields"])
        school = f"{backend.get('school') or payload.get('school') or 'classical'}"
        # 流派学理绑定键（界系/双子界序/福点反转/宫制/星群/三分集）恒以流派为准（上游 HoraryMain.js:563 globalSyncKeys
        # 注释）：顶层的 triplicity / lotReversal 是**全局**古典设置，卜卦盘不跟 —— 与流派不同就说出来，不静默吞。
        for key in ("triplicity", "lotReversal"):
            given = payload.get(key)
            if given is not None and f"{given}" != f"{backend_fields.get(key)}":
                _degrade(
                    "horary: top-level %s=%r overridden by school %s (%r)", key, given, school, backend_fields.get(key),
                    note=(
                        f"卜卦盘的 {key} 随流派档（{school} → {backend_fields.get(key)}），顶层全局设置 {key}={given!r} 不作用于卜卦盘"
                        "（上游同口径）；要改三分集请用 tripSystem（ptolemaic/dorothean）或换流派。"
                    ),
                )
        chart_payload = {**payload, "predictive": 0, "zodiacal": payload.get("zodiacal", 0), **backend_fields}
        for stale in ("datetime", "dirZone", "dirLat", "dirLon", "category", "school", "options",
                      "sincerityConfirmed", "confirmYouthMatch", "isEventChart", "questionText", "castingCamp"):
            chart_payload.pop(stale, None)
        response = self._call_remote("/chart", chart_payload)
        snapshot_text, data, snapshot_error = "", {}, None
        try:
            js = self.js_client.run(
                "horary",
                {
                    "chart": response,
                    "category": category,
                    "school": school,
                    # 判读层覆写（第 4 层）：JS 侧按引擎自带词表 HORARY_PARAM_BY_KEY 过滤，认不出的键
                    # 原样回执在 data.params_ignored（不静默吞）。顶层古典键 → 全局层（第 2 层）。
                    "options": payload.get("options"),
                    "params": params,
                    # 定盘自评（上游页面左栏三勾选，HoraryMain.js:487-497）+ 问句/阵营（→ [定盘考量]）。
                    **{k: payload[k] for k in ("sincerityConfirmed", "confirmYouthMatch", "isEventChart", "questionText", "castingCamp")
                       if payload.get(k) is not None},
                },
            )
            if isinstance(js, dict):
                data = js.get("data") if isinstance(js.get("data"), dict) else {}
                self._raise_invalid_divination_inputs("horary", data.get("invalid_inputs"))
                snapshot_text = f"{js.get('snapshot_text') or ''}".strip()
                # the JS engine resolves an unknown category back to 'general'; reflect that.
                category = f"{js.get('category') or category}".strip() or category
        except ToolValidationError:
            raise
        except Exception as exc:  # don't fail the chart, but don't hide the empty snapshot either
            snapshot_error = str(exc)
            _degrade("horary JS engine failed (category=%s): %s", category, exc)
        result = {
            "chart": response.get("chart"),
            "category": category,
            "school": school,
            # 起盘口径回执：流派档实际下发给 /chart 的字段（宫制/界系/三分集/福点反转/星群）。
            "backendFields": backend_fields,
            "judgment": data,
            "raw": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="horary", snapshot_text=snapshot_text),
        }
        if snapshot_error:
            result["snapshot_error"] = snapshot_error
        return result

    _ELECTION_TOPIC_INPUTS = ("tradeSide", "talismanStar", "surgeryPart", "surgeryPartOpposite")

    def _election_resolve(self, payload: dict[str, Any], params: dict[str, Any]) -> dict[str, Any] | None:
        """JS election action=resolve_params：四层有效口径 eff（含 pdTimeKey）+ 流派宫制联动 schoolHsys。

        引擎自己的 resolveElectionParams / westernSchools 给值，Python 不手抄流派表。取不到 → None（调用方降级并说出来）；
        认不出的全局判读键值 → ToolValidationError（同判读路径）。"""
        try:
            js = self.js_client.run(
                "election",
                {"action": "resolve_params", "school": payload.get("school"), "options": payload.get("options"), "params": params},
            )
        except Exception as exc:  # noqa: BLE001
            _degrade("election resolve_params failed: %s", exc)
            return None
        data = (js or {}).get("data") if isinstance(js, dict) else None
        if not isinstance(data, dict):
            _degrade("election resolve_params: JS 工具返回形状异常（缺 data）")
            return None
        self._raise_invalid_divination_inputs("election", data.get("invalid_inputs"))
        return data

    def _election_crisis(self, payload: dict[str, Any], js_payload: dict[str, Any]) -> None:
        """危象日参照（WP-8）：病始日期 → 上游 fetchCrisisBase（ElectionMain.js:159-171）同口径——该日正午、择日地点与盘式
        起盘，JS 侧 buildFacts 取月黄经成 crisisBase={date, moonLon}。也收上游存档形状 {date, moonLon} 直通。"""
        raw = payload.get("crisisBase")
        if raw is None or raw == "":
            return
        if isinstance(raw, dict):
            js_payload["crisisBase"] = raw
            return
        date = f"{raw}".strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            raise ToolValidationError(
                bilingual(f"crisisBase（病始日期）须为 YYYY-MM-DD：{raw!r}", f"crisisBase (illness onset date) must be YYYY-MM-DD: {raw!r}"),
                code="tool.election_invalid_setting",
                details={"invalid": [{"key": "crisisBase", "value": raw, "allowed": "YYYY-MM-DD 或 {date, moonLon}"}]},
            )
        fields_like = {k: payload.get(k) for k in ("zone", "lon", "lat", "gpsLat", "gpsLon", "hsys", "zodiacal", "siderealAyanamsa", "tradition")}
        try:
            crisis_chart = self._chart_at_moment(f"{date} 12:00:00", fields_like)
        except Exception as exc:  # noqa: BLE001 — 病始盘起不来：[危象日参照] 缺席并说出来
            _degrade("election crisis chart failed: %s", exc, note=f"择日 [危象日参照] 未产出：病始日 {date} 正午起盘失败（{exc}）。")
            return
        if crisis_chart is None:
            _degrade("election crisis chart empty", note=f"择日 [危象日参照] 未产出：病始日 {date} 正午起盘返回异常形状。")
            return
        js_payload["crisisChart"] = crisis_chart
        js_payload["crisisDate"] = date

    def _run_election_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 择日 (electional): cast the traditional chart at a candidate moment, then run the vendored 星阙
        # election engine (runElection + buildElectionSnapshot). topicId drives the rule pack + hard flags.
        topic_id = f"{payload.get('topicId') or payload.get('topic') or 'marriage'}".strip() or "marriage"
        # natal（可选，本命出生资料）：先验全再起任何盘——缺字段是输入错，不许半途静默少段。
        natal_spec = self._election_natal_spec(payload)
        params = self._divination_params(payload)
        # 流派宫制联动（westernSchools.js hsys）：切档即 patchFields({hsys})（ElectionMain.js:348-353）、挂载再生
        # chartRecord.hsys = sc.hsys（aiAnalysisContext.js:2316-2327）；现代主流档 hsys=null 不联动、页面缺省 0（:100）。
        # 显式 hsys 压过流派（同卜卦）。只在有流派档或要拉主限（natal）时才问 JS，缺省路径零额外进程。
        resolved = self._election_resolve(payload, params) if (payload.get("school") or natal_spec is not None) else None
        if payload.get("hsys") is None:
            school_hsys = (resolved or {}).get("schoolHsys")
            if payload.get("school") and resolved is None:
                _degrade("election school hsys unresolved", note="择日流派宫制联动未取到（JS 口径解析失败），本盘按整宫制 0 起。")
            payload = {**payload, "hsys": school_hsys if school_hsys is not None else 0}
        chart_payload = {**payload, "predictive": 0, "tradition": payload.get("tradition", 1)}
        for stale in ("datetime", "dirZone", "dirLat", "dirLon", "topicId", "topic", "school", "options", "natal",
                      "crisisBase", *self._ELECTION_TOPIC_INPUTS):
            chart_payload.pop(stale, None)
        response = self._call_remote("/chart", chart_payload)
        js_payload: dict[str, Any] = {
            "chart": response,
            "topicId": topic_id,
            # 流派档 + 13 个判读层参数：JS 侧按 ELECTION_PARAM_BY_KEY 过滤并回执。
            "school": payload.get("school"),
            "options": payload.get("options"),
            # 请求顶层 → 判读全局层（judgeLayerOverrides 同形，第 2 层）。
            "params": params,
            # 用事专属四键（上游左栏按用事显示：买卖方向 / 护符主星 / 手术部位 / 部位延及对宫）。
            **{k: payload[k] for k in self._ELECTION_TOPIC_INPUTS if payload.get(k) is not None},
        }
        self._election_crisis(payload, js_payload)
        natal_returns: dict[str, Any] | None = None
        if natal_spec is not None:
            natal_returns = self._attach_election_natal(payload, natal_spec, js_payload, resolved=resolved)
        snapshot_text, data, snapshot_error = "", {}, None
        try:
            js = self.js_client.run("election", js_payload)
            if isinstance(js, dict):
                data = js.get("data") if isinstance(js.get("data"), dict) else {}
                self._raise_invalid_divination_inputs("election", data.get("invalid_inputs"))
                snapshot_text = f"{js.get('snapshot_text') or ''}".strip()
                # the JS engine resolves an unknown topicId back to 'marriage'; reflect that.
                topic_id = f"{js.get('topicId') or topic_id}".strip() or topic_id
                natal_echo = data.get("natal") if isinstance(data.get("natal"), dict) else None
                if natal_spec is not None and natal_echo is not None and not natal_echo.get("integrated"):
                    _degrade("election natal chart not integrated: %s", natal_echo.get("error"))
                returns_echo = data.get("returns") if isinstance(data.get("returns"), dict) else None
                for err in (returns_echo or {}).get("errors") or []:
                    _degrade("election return chart facts failed: %s", err)
                for err in data.get("extra_errors") or []:
                    _degrade("election extra input failed: %s", err, note=f"择日：{err}")
                for key in data.get("unused_inputs") or []:
                    _degrade(
                        "election: %s given but unused by topic %s", key, topic_id,
                        note=f"择日：{key} 只作用于对应用事的规则包（买卖 trade / 护符 talisman / 手术 surgery；病始日 surgery·medication），本次用事 {topic_id} 不读它，未参与判读。",
                    )
        except ToolValidationError:
            raise
        except Exception as exc:  # don't fail the chart, but don't hide the empty snapshot either
            snapshot_error = str(exc)
            _degrade("election JS engine failed (topicId=%s): %s", topic_id, exc)
        result = {
            "chart": response.get("chart"),
            "topicId": topic_id,
            "judgment": data,
            "raw": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="election", snapshot_text=snapshot_text),
        }
        if natal_returns is not None:
            result["natalReturns"] = natal_returns
        if snapshot_error:
            result["snapshot_error"] = snapshot_error
        return result

    # ── 择日·本命合参 + 回归与主限（上游 v3.11 [Q-445]）─────────────────────────────────────────
    # 上游页面：左栏「选本命盘」（ElectionMain.js:173 selectNatal）→ natalFacts 进 runElection（[本命合参]）；
    # 其下两颗按钮「拉日/月返盘」（:204 fetchReturns → returnCharts.fetchReturnSet）与「拉主限命中」
    # （:218 fetchPdHits → returnCharts.fetchPdHitsNearElection）的结果经 extra 进快照 [回归与主限]
    # （ElectionJudgment.js:289 → electionSnapshot.js:120-135）。三者全是 HTTP 编排，按 AGENTS §5 归 Python；
    # JS 只做 buildFacts + 上游 builder 排版（tools/election.js）。
    _ELECTION_NATAL_REQUIRED = ("date", "time", "zone", "lat", "lon")
    # 上游 divination/engine/timeLords.js:209-210（returnCharts.js 的回归周期与平均速率 RATE 都取它）。
    _SOLAR_RETURN_DAYS = 365.25
    _LUNAR_RETURN_DAYS = 27.321661
    # fetchPdHitsNearElection（returnCharts.js:98）：±windowDays（缺省 240）、按 |Δ日| 升序取前 limit（缺省 8）。
    _ELECTION_PD_WINDOW_DAYS = 240
    _ELECTION_PD_LIMIT = 8
    _ELECTION_PD_TIME_KEY_COMPAT = {"Cardan": "Cardano", "Placidus": "Ptolemy"}  # returnCharts.js:106 旧存档值兼容

    def _election_natal_spec(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        natal = payload.get("natal")
        if natal is None:
            return None
        if not isinstance(natal, dict):
            raise ToolValidationError(
                bilingual("natal 必须是本命出生资料对象 {date,time,zone,lat,lon}", "natal must be an object {date,time,zone,lat,lon}"),
                code="tool.election_natal_invalid",
                details={"natal_type": type(natal).__name__},
            )
        missing = [k for k in self._ELECTION_NATAL_REQUIRED if not f"{natal.get(k) or ''}".strip()]
        if missing:
            raise ToolValidationError(
                bilingual(
                    f"本命出生资料不全，缺 {'/'.join(missing)}（本命合参与回归/主限都要完整的出生时刻与地点）",
                    f"natal birth data incomplete: missing {', '.join(missing)}",
                ),
                code="tool.election_natal_missing_fields",
                details={"missing": missing},
            )
        return natal

    def _attach_election_natal(
        self, payload: dict[str, Any], natal: dict[str, Any], js_payload: dict[str, Any], *, resolved: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """起本命盘 + 求日/月返 + 取主限命中，挂到 js_payload（natalChart / extra）。返回回执（时刻与命中）。"""
        hsys = payload.get("hsys") if payload.get("hsys") is not None else 0
        zodiacal = payload.get("zodiacal") if payload.get("zodiacal") is not None else 0
        ayanamsa = payload.get("siderealAyanamsa") or ""
        natal_ad = natal.get("ad") if natal.get("ad") is not None else 1
        natal_date = f"{natal.get('date')}".strip()
        natal_time = f"{natal.get('time')}".strip() or "12:00:00"
        # selectNatal（:173-181）：本命参数 + 页面宫制/黄道 + tradition 1 / predictive 0 / pdaspects。
        natal_chart_payload = _drop_none({
            "ad": natal_ad, "date": natal_date, "time": natal_time,
            "zone": natal.get("zone"), "lat": natal.get("lat"), "lon": natal.get("lon"),
            "gpsLat": natal.get("gpsLat"), "gpsLon": natal.get("gpsLon"),
            "hsys": hsys, "zodiacal": zodiacal, "siderealAyanamsa": ayanamsa,
            "tradition": 1, "predictive": 0, "pdaspects": [0, 60, 90, 120, 180],
        })
        try:
            natal_chart = self._call_remote("/chart", natal_chart_payload)
        except Exception as exc:  # noqa: BLE001 — 本命盘起不来：择日盘照出，合参两段缺席并说出来
            _degrade("election natal chart failed: %s", exc)
            return {"solarReturn": None, "lunarReturn": None, "pdTimeKey": None, "pdHits": [], "error": str(exc)}
        js_payload["natalChart"] = natal_chart

        # fetchReturns（:204）：fieldsLike = 电盘页的地点与盘式（geoFromFields :113）。
        fields_like = {
            "zone": payload.get("zone"), "lon": payload.get("lon"), "lat": payload.get("lat"),
            "gpsLat": payload.get("gpsLat"), "gpsLon": payload.get("gpsLon"),
            "hsys": hsys, "zodiacal": zodiacal, "siderealAyanamsa": ayanamsa,
            "tradition": payload.get("tradition") if payload.get("tradition") is not None else 1,
        }
        election_moment = f"{payload.get('date')} {payload.get('time') or '12:00:00'}"
        solar = lunar = None
        for kind in ("sun", "moon"):
            natal_lon, _ = _chart_body_lon_speed(natal_chart, kind)
            try:
                ret = self._solve_return_before(kind, natal_lon, election_moment, fields_like)
                if ret is None:
                    _degrade("election %s return: 未求得（本命黄经缺失或回归起盘失败）", kind)
            except Exception as exc:  # noqa: BLE001 — 上游 solveReturnBefore 失败 = 该返为 null；这里说出来
                _degrade("election %s return solve failed: %s", kind, exc)
                ret = None
            if kind == "sun":
                solar = ret
            else:
                lunar = ret

        # fetchPdHits（:218-240）：本命参数（日期用 /）+ 页面宫制/黄道 + tradition 1；时间钥匙 = 有效口径 eff.pdTimeKey。
        pd_time_key = self._election_effective_pd_time_key(payload, resolved=resolved)
        natal_params = _drop_none({
            "ad": natal_ad, "date": natal_date.replace("-", "/"), "time": natal_time,
            "zone": natal.get("zone"), "lat": natal.get("lat"), "lon": natal.get("lon"),
            "gpsLat": natal.get("gpsLat"), "gpsLon": natal.get("gpsLon"),
            "hsys": hsys, "zodiacal": zodiacal, "siderealAyanamsa": ayanamsa, "tradition": 1,
        })
        pd_hits = self._election_pd_hits(natal_params, f"{payload.get('date')}", pd_time_key)
        js_payload["extra"] = {"returnSet": {"solar": solar, "lunar": lunar}, "pdHits": pd_hits}
        return {
            "solarReturn": solar.get("momentStr") if solar else None,
            "lunarReturn": lunar.get("momentStr") if lunar else None,
            "pdTimeKey": pd_time_key,
            "pdHits": pd_hits,
        }

    def _election_effective_pd_time_key(self, payload: dict[str, Any], *, resolved: dict[str, Any] | None = None) -> str | None:
        """eff.pdTimeKey 由引擎自己的 resolveElectionParams 给（流派档 × 覆写四层合并），Python 不手抄默认表。"""
        data = resolved if resolved is not None else self._election_resolve(payload, self._divination_params(payload))
        if data is None:
            _degrade("election resolve_params unavailable (主限时间钥匙回落 Ptolemy)")
            return None
        effective = data.get("effective")
        value = effective.get("pdTimeKey") if isinstance(effective, dict) else None
        return f"{value}" if value else None

    def _chart_at_moment(self, moment: str, fields_like: dict[str, Any]) -> dict[str, Any] | None:
        """上游 divination/mundane/momentPipeline.chartAtMoment（:157）的 Python 端口：任意时刻 + 给定地点独立起盘。"""
        date_part, _, time_part = moment.partition(" ")
        params = {
            "ad": 1,
            "date": date_part.replace("-", "/"),
            "time": time_part or "00:00:00",
            "zone": fields_like.get("zone") or "+08:00",
            "lat": fields_like.get("lat") or "0n00",
            "lon": fields_like.get("lon") or "0e00",
            "gpsLat": fields_like.get("gpsLat") if fields_like.get("gpsLat") is not None else 0,
            "gpsLon": fields_like.get("gpsLon") if fields_like.get("gpsLon") is not None else 0,
            "hsys": fields_like.get("hsys") if fields_like.get("hsys") is not None else 0,
            "zodiacal": fields_like.get("zodiacal") if fields_like.get("zodiacal") is not None else 0,
            "siderealAyanamsa": fields_like.get("siderealAyanamsa") if fields_like.get("siderealAyanamsa") is not None else "",
            "tradition": fields_like.get("tradition") if fields_like.get("tradition") is not None else 1,
            "predictive": 0,
            "pdaspects": [0, 60, 90, 120, 180],
        }
        rsp = self._call_remote("/chart", params)
        return rsp if isinstance(rsp, dict) and isinstance(rsp.get("chart"), dict) else None

    def _solve_return_before(
        self, kind: str, natal_lon: float | None, election_moment: str, fields_like: dict[str, Any]
    ) -> dict[str, Any] | None:
        """上游 returnCharts.solveReturnBefore（:23-58）的逐步端口：择日时刻之前最近一次精确日返/月返。

        逐条照搬：种子 = 电盘时刻按「该体已行过的角距 / 平均速率」回推；牛顿迭代 ≤6 次，|Δ| < 0.005° 停；
        速率取该时刻盘的 lonspeed（|v| > 0.05 才用，否则平均速率）；**时间一律换算成整秒**（上游 daysToSec =
        Math.round(d·86400)，Math.round 是 half-up → _js_math_round）；收敛点落在电盘之后则回退一整周期、
        只重起一次盘（上游不再精化）。返回 {momentStr, chart}：chart 是**产出 facts 的那张盘**——上游循环
        未 break 时 t 在最后一次 facts 之后又前推了一步，momentStr 与 facts 来源盘因此可以不同刻，照搬。
        时刻算术为墙钟（无 DST）：等同上游在无夏令时的机器时区（如 Asia/Shanghai）下 moment.js 的行为。
        """
        if natal_lon is None:
            return None
        cycle = self._SOLAR_RETURN_DAYS if kind == "sun" else self._LUNAR_RETURN_DAYS
        rate = 360 / cycle
        try:
            elec = datetime.strptime(election_moment, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
        r0 = self._chart_at_moment(election_moment, fields_like)
        if r0 is None:
            return None
        lon0, _ = _chart_body_lon_speed(r0, kind)
        if lon0 is None:
            return None
        elapsed = ((lon0 - natal_lon) % 360 + 360) % 360
        t = elec - timedelta(seconds=_js_math_round(elapsed / rate * 86400))
        facts_chart: dict[str, Any] | None = None
        for _ in range(6):
            chart = self._chart_at_moment(_fmt_moment(t), fields_like)
            if chart is None:
                return None
            facts_chart = chart
            lon, speed = _chart_body_lon_speed(chart, kind)
            if lon is None:
                return None
            d = ((natal_lon - lon + 540) % 360) - 180
            if abs(d) < 0.005:
                break
            v = abs(speed) if isinstance(speed, (int, float)) and not isinstance(speed, bool) and abs(speed) > 0.05 else rate
            t = t + timedelta(seconds=_js_math_round(d / v * 86400))
        if t > elec:
            t = t - timedelta(seconds=_js_math_round(cycle * 86400))
            chart = self._chart_at_moment(_fmt_moment(t), fields_like)
            if chart is not None:
                facts_chart = chart
        return {"momentStr": _fmt_moment(t), "chart": facts_chart} if facts_chart is not None else None

    def _election_pd_hits(self, natal_params: dict[str, Any], election_date: str, pd_time_key: str | None) -> list[dict[str, Any]]:
        """上游 returnCharts.fetchPdHitsNearElection（:98-128）端口：本命带主限法补拉一盘，取
        predictives.primaryDirection，过滤择日日期 ±240 日，按 |Δ日| 升序取前 8。行 = [弧, 迫星, 应星, 法, 日期]。
        上游失败回 []（静默）；这里同样回 [] 但记降级。"""
        params = {
            **natal_params,
            "predictive": 1,
            "includePrimaryDirection": True,
            "pdtype": 0,
            "showPdBounds": 0,
            "pdMethod": "core_alchabitius",
            "pdTimeKey": self._ELECTION_PD_TIME_KEY_COMPAT.get(pd_time_key or "") or pd_time_key or "Ptolemy",
            "pdDirect": 1,
            "pdConverse": 0,
            "pdAntiscia": 0,
            "pdTerms": 0,
            "pdaspects": [0, 60, 90, 120, 180],
        }
        try:
            rsp = self._call_remote("/chart", params)
        except Exception as exc:  # noqa: BLE001
            _degrade("election primary-direction hits failed: %s", exc)
            return []
        predictives = rsp.get("predictives") if isinstance(rsp, dict) else None
        rows = predictives.get("primaryDirection") if isinstance(predictives, dict) else None
        try:
            elec = datetime.strptime(f"{election_date}"[:10], "%Y-%m-%d").date()
        except ValueError:
            return []
        out: list[dict[str, Any]] = []
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, list) or len(row) < 5 or not row[4]:
                continue
            day = f"{row[4]}"[:10]
            try:
                hit = datetime.strptime(day, "%Y-%m-%d").date()
            except ValueError:
                continue
            delta = (hit - elec).days
            if abs(delta) > self._ELECTION_PD_WINDOW_DAYS:
                continue
            out.append({"promissor": row[1], "significator": row[2], "method": row[3], "date": day, "deltaDays": delta})
        out.sort(key=lambda h: abs(h["deltaDays"]))  # 稳定排序，同上游 Array.prototype.sort
        return out[: self._ELECTION_PD_LIMIT]
