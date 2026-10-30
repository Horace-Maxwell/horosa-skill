"""三式 runner（SanshiRunners）：奇门 / 太乙 / 金口诀（ken 后端）、大六壬、三式合一。"""
from __future__ import annotations

from typing import Any

from horosa_skill.civil_calendar import _leading_year_of
from horosa_skill.errors import (
    HorosaSkillError,
    ToolTransportError,
    ToolValidationError,
    bilingual,
)
from horosa_skill.service._context import _degrade
from horosa_skill.service.envelope import _build_compact_subresult_contract
from horosa_skill.service.options_cn import (
    _day_boundary_switches,
    _gua_year_ganzi,
    _jinkou_manual_branch,
    _jinkou_resolve_difen,
    _jinkou_school_overrides,
    _jinkou_validate_options,
    _js_parse_int,
    _ken_datetime_parts,
    _liureng_chart_payload,
    _liureng_gods_payload,
    _liureng_remote_payload,
    _liureng_runyear_from,
    _liureng_time_alg,
    _parse_taiyi_datetime_text,
    _qimen_effective_options,
    _qimen_ken_payload,
    _qimen_local_route_reasons,
    _raise_js_option_error,
    _sanshi_liureng_options,
)


class SanshiRunners:
    _TIAN_GAN = ("甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸")

    def _normalize_fa_related_people(self, payload: dict[str, Any]) -> list[dict[str, Any]] | None:
        """法奇门「相关人员」：把 [{name, yearGan|birth}] 归一化为上游 stamp 形状 [{name, yearGan}]。

        yearGan 直接收十天干字符；birth（公历 YYYY-MM-DD[ HH:mm:ss]）走 /nongli/time 的
        yearJieqi（立春界年干支）取年干——与上游 birthToYearGan 同口径（1-2 月出生立春前后
        归属不同年）。解析不出的人员跳过：computeProtect 对 falsy yearGan 同样不出行。
        """
        raw = payload.get("faRelatedPeople")
        if not isinstance(raw, list):
            return None
        normalized: list[dict[str, Any]] = []
        for person in raw:
            if not isinstance(person, dict):
                continue
            name = str(person.get("name") or "").strip() or "相关人员"
            year_gan = str(person.get("yearGan") or "").strip()
            if year_gan not in self._TIAN_GAN:
                year_gan = ""
                birth = str(person.get("birth") or "").strip()
                if birth:
                    birth_date, _, birth_time = birth.partition(" ")
                    birth_time = birth_time.strip() or "12:00:00"
                    if len(birth_time) == 5:
                        birth_time = f"{birth_time}:00"
                    try:
                        person_nongli = self._call_remote(
                            "/nongli/time",
                            {
                                "date": birth_date,
                                "time": birth_time,
                                "zone": payload.get("zone"),
                                "lat": payload.get("lat"),
                                "lon": payload.get("lon"),
                                "gpsLat": payload.get("gpsLat"),
                                "gpsLon": payload.get("gpsLon"),
                                "ad": 1,
                            },
                        )
                        year_jieqi = str((person_nongli or {}).get("yearJieqi") or "")
                        if year_jieqi[:1] in self._TIAN_GAN:
                            year_gan = year_jieqi[0]
                    except Exception as exc:  # noqa: BLE001 - one person's lookup must not sink the whole pan
                        # v0.41.1：此前静默丢人——用户明说的相关人员从「八门化气大阵」护持行里消失，调用方无从知道。
                        _degrade(
                            "faRelatedPeople %s /nongli/time failed: %s", name, exc,
                            note=f"降级：相关人员「{name}」的出生年干没算出来（/nongli/time 失败：{exc}），八门化气大阵的护持行缺这一人。",
                        )
                        year_gan = ""
            if year_gan:
                normalized.append({"name": name, "yearGan": year_gan})
        return normalized

    def _run_qimen_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 上游 DunJiaMain（:1765）`parseInt(flds.date.value.format('YYYY'))` = DateTime 的 ad × year：带符号显示年
        # （公元前 '-0500-03-21' → -500；五位年原样）。旧 int(date[:4]) 把 '-0500' 切成 -50、'10000' 切成 1000 →
        # 节气种子年全错。日期不带负号而 ad=-1（公元前的另一种写法）同样读成负年。
        year = _leading_year_of(payload["date"])
        if year is None:
            raise ToolValidationError(
                bilingual(f"奇门遁甲：读不出日期的年份：{payload['date']!r}。", f"qimen: cannot read the year of date {payload['date']!r}."),
                code="tool.qimen_invalid_date",
                details={"date": payload.get("date")},
            )
        if year > 0 and _js_parse_int(payload.get("ad")) == -1:
            year = -year
        options = _qimen_effective_options(payload)
        time_alg = options.get("timeAlg", 0)
        nongli = payload.get("nongli")
        if not isinstance(nongli, dict):
            nongli = self._call_remote(
                "/nongli/time",
                {
                    "date": payload["date"],
                    "time": payload["time"],
                    "zone": payload["zone"],
                    "lon": payload["lon"],
                    "lat": payload["lat"],
                    "gpsLat": payload.get("gpsLat"),
                    "gpsLon": payload.get("gpsLon"),
                    # 日界/晚子时开关与 ken 权威引擎同口径：仅显式给定时发送，缺省沿用后端默认(1/1)。
                    **_day_boundary_switches(options),
                    "timeAlg": time_alg,
                    "ad": payload.get("ad", 1),
                },
            )

        def _jieqi_year(target_year: int) -> Any:
            return self._call_remote(
                "/jieqi/year",
                {"year": target_year, "zone": payload["zone"], "lat": payload["lat"], "lon": payload["lon"], "time": payload["time"], "gpsLat": payload.get("gpsLat"), "gpsLon": payload.get("gpsLon"), "ad": payload.get("ad", 1), "timeAlg": time_alg},
            )

        prev_year = payload.get("jieqi_year_prev")
        if not isinstance(prev_year, dict):
            prev_year = _jieqi_year(year - 1)
        current_year = payload.get("jieqi_year_current")
        if not isinstance(current_year, dict):
            current_year = _jieqi_year(year)
        # 日家(2)/金函(6) 腊月过冬至需次年至日 → 种子年 y-1,y,y+1（上游 jieqiSeedYears，DunJiaCalc.js:1243）。
        next_year = None
        if _js_parse_int(options.get("paiPanType")) in (2, 6):
            next_year = payload.get("jieqi_year_next")
            if not isinstance(next_year, dict):
                next_year = _jieqi_year(year + 1)
        # 路由与上游 DunJiaMain.getResolvedPan 同判据（isQimenLocalRoute）：本地家/飞盘/混合/报数/七组本地口径 →
        # 本地 calcDunJia，**不打** ken（后端不认这些口径）；其余（时家/综合·转盘·全缺省口径）ken 是唯一算权。
        route_reasons = _qimen_local_route_reasons(options)
        ken_response = None
        if not route_reasons:
            ken_response = self._call_remote("/qimen/pan", _qimen_ken_payload(payload, options, nongli))
            self._require_ken_pan(ken_response, engine="kinqimen", endpoint="/qimen/pan")
        js_payload = {
            **{k: v for k, v in payload.items() if k not in ("ken_response", "kenResponse")},
            "options": options,
            "nongli": nongli,
            "jieqi_year_prev": prev_year,
            "jieqi_year_current": current_year,
            **({"jieqi_year_next": next_year} if isinstance(next_year, dict) else {}),
            **({"ken_response": ken_response} if ken_response is not None else {}),
        }
        fa_related_people = self._normalize_fa_related_people(payload)
        if fa_related_people is not None:
            js_payload["faRelatedPeople"] = fa_related_people
        js_result = self.js_client.run("qimen", js_payload)
        js_route = js_result.get("route") if isinstance(js_result, dict) else None
        if isinstance(js_route, dict) and bool(js_route.get("local")) != bool(route_reasons):
            raise ToolTransportError(
                "奇门路由判据漂移：Python 镜像与 vendored isQimenLocalRoute 结论不一致。",
                code="tool.qimen_route_check_failed",
                details={"python_local_reasons": route_reasons, "js_route": js_route, "options": options},
            )
        snapshot_text = js_result.get("snapshot_text")
        result: dict[str, Any] = {
            "pan": js_result.get("data", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="qimen", snapshot_text=snapshot_text),
            "prerequisites": {
                "nongli": nongli, "jieqi_year_prev": prev_year, "jieqi_year_current": current_year,
                **({"jieqi_year_next": next_year} if isinstance(next_year, dict) else {}),
            },
            "route": {"local": bool(route_reasons), "reasons": route_reasons},
        }
        if route_reasons:
            # 算源如实：本地路由的盘不带 pan.source，依据卡按 compute_sources 标注（technique_provenance 已声明该引擎）。
            result["compute_sources"] = {"pan": "local_route_calcDunJia"}
        return result

    def _run_taiyi_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 口径单源：顶层日界两开关（0/1 整数，JS buildOptions 按 `=== 1` 标「换日」）∪ options，options 优先。
        options = {**_day_boundary_switches(payload), **(payload.get("options") or {})}
        # 时间基准（上游 TaiYiMain TAIYI_PAGE_SETTINGS.timeBasis def 'direct'，TIME_BASIS_OPTIONS 两档）：
        # trueSolar 时 ken 按 nongli.birth 的真太阳时分量起局（上游 resolveCalculationDateTime，TaiYiCalc.js:254）。
        # 此前该档既不发也不施加，快照却标「真太阳时」—— ken 恒按钟表时起局。
        time_basis = options.get("timeBasis") or "direct"
        if time_basis not in ("direct", "trueSolar"):
            raise ToolValidationError(
                bilingual(
                    f"太乙 timeBasis 取值无效：{time_basis!r}（可选：direct=直接时间 / trueSolar=真太阳时）。",
                    f"taiyi timeBasis is invalid: {time_basis!r} (allowed: direct / trueSolar).",
                ),
                code="tool.taiyi_invalid_option",
                details={"field": "timeBasis", "value": time_basis, "allowed": ["direct", "trueSolar"]},
            )
        options["timeBasis"] = time_basis
        nongli = payload.get("nongli")
        if not isinstance(nongli, dict):
            nongli = self._call_remote(
                "/nongli/time",
                {
                    "date": payload["date"],
                    "time": payload["time"],
                    "zone": payload["zone"],
                    "lon": payload["lon"],
                    "lat": payload["lat"],
                    "gpsLat": payload.get("gpsLat"),
                    "gpsLon": payload.get("gpsLon"),
                    # 日界/晚子时开关与 ken 权威引擎同口径：仅显式给定时发送，缺省沿用后端默认(1/1)。
                    **_day_boundary_switches(payload),
                    # 真太阳时基准要的是 nongli.birth = 真太阳时（上游太乙取农历不带 timeAlg = 后端缺省真太阳时）。
                    "timeAlg": 0 if time_basis == "trueSolar" else payload.get("timeAlg", 0),
                    "ad": payload.get("ad", 1),
                },
            )
        # taiyi ken 期望 sex 为 '男'/'女' 字符串；gender 经 input_normalization 已归一为 0(女)/1(男)，
        # 故此处显式映射（不能靠 `or gender` —— int 0 为 falsy 会误落默认「男」）。
        _g = payload.get("gender")
        _sex_from_gender = "女" if _g in (0, "0", False, "女", "female", "f") else "男"
        sex = options.get("sex") or _sex_from_gender
        ken_parts: dict[str, Any] = _ken_datetime_parts(payload)
        if time_basis == "trueSolar":
            solar = _parse_taiyi_datetime_text((nongli or {}).get("birth"))
            if solar:
                ken_parts = {**ken_parts, **solar}
        ken_response = self._call_remote(
            "/taiyi/pan",
            {
                **ken_parts,
                "zone": payload.get("zone"),
                "style": options.get("style", 3),
                "tn": options.get("tn", 0),
                "sex": sex,
                "timeBasis": time_basis,
                "enableGameTheory": bool(options.get("gameTheory") in (1, True, "1")),
                "date": payload.get("date"),
                "time": payload.get("time"),
                "realSunTime": (nongli or {}).get("birth", ""),
                "jiedelta": (nongli or {}).get("jiedelta", ""),
                # 显式日界/晚子时开关直达权威引擎（缺省不发→引擎默认 1/1）。
                **_day_boundary_switches(payload),
            },
        )
        self._require_ken_pan(ken_response, engine="kintaiyi", endpoint="/taiyi/pan")
        js_result = self.js_client.run(
            "taiyi", {**payload, "options": options, "nongli": nongli, "ken_response": ken_response}
        )
        # 流派六轴（options.school / 平铺键 / 顶层 school）由 JS 按上游 TAIYI_SCHOOL_OPTIONS 校验。
        _raise_js_option_error("taiyi", js_result)
        snapshot_text = js_result.get("snapshot_text")
        return {
            "pan": js_result.get("data", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="taiyi", snapshot_text=snapshot_text),
            "prerequisites": {"nongli": nongli},
        }

    def _run_jinkou_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        options = dict(payload.get("options") or {})
        _jinkou_validate_options(options)
        liureng = payload.get("liureng")
        if not isinstance(liureng, dict):
            # v3.12.0 起四柱 / 占时随「时间基准」取（JinKouMain.genGodsParams:1389-1412、无头 regenDivination.js:176-178：
            # timeAlg = trueSolar ? 0 : 1，缺省 direct = 按钟表时）。此前不带 timeAlg → 后端恒按真太阳时，而 ken 四位按钟表时，
            # 一张课两个时辰；本地引擎（流派非缺省）则时间基准整个无效。
            jinkou_time_alg = 0 if (options.get("timeBasis") or "direct") == "trueSolar" else 1
            remote = self._call_remote(
                "/liureng/gods",
                _liureng_gods_payload("liureng_gods", payload, jinkou_time_alg),
            )
            liureng = remote.get("liureng", remote)
        nongli = liureng.get("nongli") if isinstance(liureng, dict) and isinstance(liureng.get("nongli"), dict) else {}
        # 地分缺省 = 自动取占时支（上游 JinKouMain.js:907 diFenAuto:true → resolveJinKouDiFen 首次起课取
        # 占时支）。此前缺省发「子」给 ken（本地脚手架却取占时支），默认盘恒按子地分起。
        difen = _jinkou_resolve_difen(payload.get("diFen") or options.get("diFen"), nongli.get("time"))
        options["diFen"] = difen
        time_basis = options.get("timeBasis") or "direct"
        # 路由（上游 JinKouMain.assembleJinKouData:1255-1270 + schoolsAllDefault:1288）：五项流派/盘法全缺省才用
        # ken /jinkou/pan（再由 JS 判两源日柱是否对齐），任一非缺省即本地 buildJinKouData —— ken 不认这五项，照打会
        # 得到「按缺省流派出盘、快照却按所选解读」。此前 skill 恒用 ken 行覆盖本地脚手架，五项流派全是死开关。
        school_overrides = _jinkou_school_overrides(options)
        warnings: list[str] = []
        ken_response = None
        if not school_overrides:
            ken_parts: dict[str, Any] = _ken_datetime_parts(payload)
            if time_basis == "trueSolar":
                # 上游 fetchJinKouPan → resolveCalculationDateTime（JinKouCalc.js:2630，v3.13.0）：真太阳时 = liureng.nongli.birth。
                solar = _parse_taiyi_datetime_text(nongli.get("birth"))
                if solar:
                    ken_parts = {**ken_parts, **solar}
            ken_response = self._call_remote(
                "/jinkou/pan",
                {
                    **ken_parts,
                    "zone": payload.get("zone"),
                    "difen": difen,
                    "yuejiang": _jinkou_manual_branch(options.get("yueJiang") or options.get("yuejiang")),
                    "zhanshi": _jinkou_manual_branch(options.get("zhanShi") or options.get("zhanshi")),
                    "timeBasis": time_basis,
                    "realSunTime": nongli.get("birth", ""),
                    "jiedelta": nongli.get("jiedelta", ""),
                    "date": payload.get("date"),
                    "time": payload.get("time"),
                    # 日界 + 晚子时两开关（上游 JinKouCalc.js:2747-2748 fetchJinKouPan 两键齐发，缺省=defaultAfter23NewDay()=1）：
                    # 显式给定才发送，缺省不发 → ken 缺省 1/1（webjinkousrv.py:244-245）= 上游出厂缺省，且与六壬前置同口径
                    # （LiuRengGodsInput.after23NewDay 缺省不再硬塞 False）。此前只发晚子时键，显式 after23NewDay=0 到不了 ken。
                    **_day_boundary_switches(payload),
                },
            )
            self._require_ken_pan(ken_response, engine="kinjinkou", endpoint="/jinkou/pan")
        # 贵神昼夜按真实地平（上游无头 regenerateJinkouSnapshot → ensureLiurengChartObjects：/liureng/gods 回包缺 isDiurnal
        # 时补一份 /chart 取 isDiurnal，取不到才留 null = 按时支粗判；页面 castIsDiurnal 同为地平口径）。此前 skill 只认调用方
        # 显式 isDiurnal，缺省恒按时支粗判 —— 日出 / 日落前后的课贵人昼夜取反。
        jinkou_payload = dict(payload)
        if jinkou_payload.get("isDiurnal") is None:
            lr_diurnal = liureng.get("isDiurnal") if isinstance(liureng, dict) else None
            if lr_diurnal is None:
                try:
                    chart = self._call_remote("/chart", _liureng_chart_payload(payload))
                    inner = chart.get("chart") if isinstance(chart.get("chart"), dict) else chart
                    lr_diurnal = inner.get("isDiurnal")
                except Exception as exc:  # noqa: BLE001 — 取不到昼夜只回退时支粗判（上游同），须留痕
                    _degrade(
                        "jinkou isDiurnal chart fetch failed: %s", exc,
                        note="金口诀贵神昼夜：取 /chart 昼夜失败，本次按占时支粗判昼夜（上游取不到时同样回退）。",
                    )
            if lr_diurnal is not None:
                jinkou_payload["isDiurnal"] = bool(lr_diurnal)
        js_result = self.js_client.run(
            "jinkou",
            {**jinkou_payload, "options": options, "liureng": liureng, "ken_response": ken_response},
        )
        _raise_js_option_error("jinkou", js_result)
        js_route = js_result.get("route") if isinstance(js_result, dict) else None
        if isinstance(js_route, dict) and bool(js_route.get("schoolsDefault")) != (not school_overrides):
            raise ToolTransportError(
                "金口诀路由判据漂移：Python 与 JS 对「五项流派是否全缺省」结论不一致。",
                code="tool.jinkou_route_check_failed",
                details={"python_overrides": school_overrides, "js_route": js_route},
            )
        data = js_result.get("data", {}) if isinstance(js_result.get("data"), dict) else {}
        if isinstance(data.get("daySourceNote"), str) and data["daySourceNote"]:
            # 上游只在页面上显示这条（不进快照）；headless 必须说出来：盘由本地引擎重出，不是 ken 盘。
            warnings.append(data["daySourceNote"])
        route_reason = js_route.get("reason") if isinstance(js_route, dict) else None
        if ken_response is not None and route_reason == "no_ken":
            warnings.append("金口诀 ken 盘未带四位行（rows），本次由本地引擎出课 —— 与星阙 ken 盘可能不一致。")
        snapshot_text = js_result.get("snapshot_text")
        result: dict[str, Any] = {
            "jinkou": data,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="jinkou", snapshot_text=snapshot_text),
            "prerequisites": {"liureng": liureng},
            "route": js_route if isinstance(js_route, dict) else {"schoolOverrides": school_overrides},
        }
        # 只给**上游同判据**的本地路由（五项流派非缺省 / 两源日柱不齐）标声明过的本地算源；ken 畸形被迫回退本地
        # 不标 —— 依据卡照旧把它显示成「与声明不一致」（AGENTS §4 静默回退形状）。
        if data.get("source") != "kinjinkou" and route_reason in ("school", "day_misaligned"):
            result["compute_sources"] = {"jinkou": "local_route_buildJinKouData"}
        if warnings:
            result["_warnings"] = warnings
        return result

    def _run_liureng_tool(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        time_alg = _liureng_time_alg(payload)
        gods_payload = _liureng_gods_payload(tool_name, payload, time_alg)
        remote = self._call_remote("/liureng/gods", gods_payload)
        liureng = remote.get("liureng", remote)
        runyear = None
        remote_payloads: dict[str, Any] = {"/liureng/gods": gods_payload}
        if tool_name == "liureng_runyear":
            # 上游 genRunYearParams（LiuRengMain.js:5090）：出生档 + 起课档，卦年干支取起课盘年柱。
            runyear_payload = _liureng_remote_payload("liureng_runyear", payload)
            if not runyear_payload.get("guaYearGanZi"):
                gua_year = _gua_year_ganzi(liureng)
                if gua_year:
                    runyear_payload["guaYearGanZi"] = gua_year
            remote_payloads["/liureng/runyear"] = runyear_payload
            runyear = _liureng_runyear_from(self._call_remote("/liureng/runyear", runyear_payload))
        chart: dict[str, Any] = {}
        chart_error: dict[str, Any] | None = None
        try:
            chart = self._call_remote("/chart", _liureng_chart_payload(payload))
        except HorosaSkillError as exc:
            chart_error = {"code": exc.code, "message": str(exc), "details": exc.details}
        except Exception as exc:
            chart_error = {"code": "liureng.chart_context_unavailable", "message": str(exc), "details": {}}

        # 决策层 S3（可选，缺省关）：没给 zhanCategory 时按问题文本分门类，驱动 [占断向导] 段。
        payload = self._decide_zhan_category(payload)
        js_result = self.js_client.run(
            "liureng",
            {
                **payload,
                "liureng": liureng,
                "runyear": runyear,
                "chart": chart,
                "guirengType": payload.get("guirengType", 2),
            },
        )
        # 起课口径（castMethod / 换将 / 分昼夜 / 涉害 / 阴阳系 / 十二长生五行 / 贵人 0–4）由 JS 按上游
        # LIURENG_PAGE_SETTINGS / QI_METHODS 词表校验；认不出的值 → 结构化报错（不回落缺省盘）。
        _raise_js_option_error("liureng", js_result)
        snapshot_text = js_result.get("snapshot_text")
        data = js_result.get("data", {}) if isinstance(js_result.get("data"), dict) else {}
        result = {
            "liureng": {
                **(liureng if isinstance(liureng, dict) else {}),
                "layout": data.get("layout"),
                "ke": data.get("ke", {}).get("raw") if isinstance(data.get("ke"), dict) else None,
                "keText": data.get("ke", {}).get("lines") if isinstance(data.get("ke"), dict) else None,
                "sanChuan": data.get("sanChuan"),
                "panStyle": data.get("panStyleName"),
            },
            "runyear": runyear,
            "headless_liureng": data,
            "snapshot_text": snapshot_text,
            "prerequisites": {
                "remote_payload": gods_payload,
                **({"runyear_payload": remote_payloads["/liureng/runyear"]} if "/liureng/runyear" in remote_payloads else {}),
                "chart_available": bool(chart),
                "chart_error": chart_error,
            },
        }
        result["export_snapshot"] = self._augment_export_payload(technique="liureng", snapshot_text=snapshot_text)
        return result

    def _run_sanshiunited_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        """三式合一 —— 快照正文交给 vendored 上游 buildSanShiUnitedSnapshotText（JS 工具 sanshiunited）。

        数据链逐步对齐上游 components/sanshi/SanShiUnitedMain.js（v3.11.x）：
        ① 三式农历 = genParams → fetchPreciseNongli（:3235-3265 / :3984）：timeAlg 与日界两键随三式 options，
           出厂 0 / 1 / 1（构造器 :2037-2047，日界两键 = 全局出厂值），上游恒显式发送；
        ② 真太阳时显示值 = resolveDisplaySolarTime（:2226-2248）：timeAlg=0 即该农历 birth，否则另取一份真太阳时农历；
        ③ 星盘 = props.chartObj（主页全局盘，三式与之共享 hsys / zodiacal，出厂 1 / 0 —— utils/newChartSeeds.js:38-41）；
        ④ 奇门盘 = getKinqimenDunJia（:2281-2308）：同一份三式农历，context = {displaySolarTime, isDiurnal=星盘昼夜}
           （calcDunJia 的神煞贵人按它分昼夜，normalizeKinqimenData 沿用这层）；getQimenOptions（:3297-3346）显式带日界两键；
        ⑤ 太乙盘 = getKintaiyiPan（:2319-2340）：同一份三式农历（trueSolar 基准取它的 birth）；
        ⑥ 六壬层**不另起盘**（此前另打 /liureng/gods，占时取真太阳时农历、不随三式 timeAlg）：JS 侧按 performRecalcByNongli
           （:3677-3876）用 ①④③ 起课 —— 占日 / 占时 = 奇门盘干支（buildLrNongli），月将 / 昼夜 = 星盘。
        """
        time_alg_raw = payload.get("timeAlg", 0)
        if time_alg_raw in (None, ""):
            time_alg_raw = 0
        if isinstance(time_alg_raw, bool) or str(time_alg_raw).strip() not in {"0", "1"}:
            raise ToolValidationError(
                bilingual(
                    f"三式合一 timeAlg 取值无效：{time_alg_raw!r}（可选：0=真太阳时 / 1=直接时间）。",
                    f"sanshiunited timeAlg is invalid: {time_alg_raw!r} (allowed: 0=true solar time / 1=clock time).",
                ),
                code="tool.sanshiunited_invalid_option",
                details={"field": "timeAlg", "value": time_alg_raw, "allowed": [0, 1]},
            )
        time_alg = int(str(time_alg_raw).strip())
        # 上游三式 options 的日界两键出厂 1 / 1（全局出厂「23 点算第二天」「晚子时用次日」），genParams / getQimenOptions /
        # getKintaiyiPan 都显式发送；显式给定则随之。
        day_switches = {"after23NewDay": 1, "lateZiHourUseNextDay": 1, **_day_boundary_switches(payload)}
        gender = payload.get("gender")
        sex = 0 if gender in (0, "0", False, "女", "female", "f") else 1
        shared = {
            "date": payload["date"],
            "time": payload["time"],
            "zone": payload["zone"],
            "lat": payload["lat"],
            "lon": payload["lon"],
            "gpsLat": payload.get("gpsLat"),
            "gpsLon": payload.get("gpsLon"),
            "ad": payload.get("ad", 1),
            **day_switches,
            "timeAlg": time_alg,
        }
        liureng_options = _sanshi_liureng_options(payload)
        taiyi_options = dict(payload.get("taiyi_options") or {})
        # 上游三式合一太乙区的时间基准键名是 taiyiTimeBasis（SanShiUnitedMain.js:446 / :2326，缺省 direct，
        # 不随盘 timeAlg 串改）；skill 的 taiyi_options 用 taiyi 工具原名 timeBasis —— 两种写法都认，taiyi_options 优先。
        if payload.get("taiyiTimeBasis") not in (None, "") and taiyi_options.get("timeBasis") in (None, ""):
            taiyi_options["timeBasis"] = payload["taiyiTimeBasis"]
        if gender is not None and taiyi_options.get("sex") in (None, ""):
            taiyi_options["sex"] = "女" if sex == 0 else "男"   # getKintaiyiPan：sex = options.sex === 0 ? '女' : '男'
        qimen_options = dict(payload.get("qimen_options") or {})
        if gender is not None and qimen_options.get("sex") in (None, ""):
            qimen_options["sex"] = sex

        nongli_request = {k: v for k, v in shared.items() if v is not None}
        nongli = self._call_remote("/nongli/time", nongli_request)
        if not isinstance(nongli, dict) or not nongli.get("dayGanZi"):
            raise ToolTransportError(
                bilingual("三式合一取三式农历失败（/nongli/time 未回日柱）。",
                          "sanshiunited could not get the 三式 nongli (/nongli/time returned no day pillar)."),
                code="tool.sanshiunited_nongli_unavailable",
                details={"request": nongli_request},
            )
        display_solar = str(nongli.get("birth") or "")
        if time_alg != 0:
            solar = self._call_remote("/nongli/time", {**nongli_request, "timeAlg": 0})
            solar_birth = solar.get("birth") if isinstance(solar, dict) else None
            if solar_birth:
                display_solar = str(solar_birth)
            else:
                # 上游 resolveDisplaySolarTime 同样回退到当前农历 birth（此时是钟表时）；headless 把回退说出来。
                _degrade("三式合一真太阳时显示值不可得（/nongli/time timeAlg=0 未回 birth），【起盘信息】真太阳时行按直接时间显示")
        chart_request = {
            key: value
            for key, value in {
                "date": payload["date"],
                "time": payload["time"],
                "zone": payload["zone"],
                "lat": payload["lat"],
                "lon": payload["lon"],
                "gpsLat": payload.get("gpsLat"),
                "gpsLon": payload.get("gpsLon"),
                "ad": payload.get("ad", 1),
                "hsys": payload.get("hsys", 1),
                "zodiacal": payload.get("zodiacal", 0),
                "siderealAyanamsa": payload.get("siderealAyanamsa"),
                "tradition": 0,
                "predictive": 0,
            }.items()
            if value is not None
        }
        chart = self._call_remote("/chart", chart_request)
        astro_chart = chart.get("chart") if isinstance(chart, dict) else None
        if not isinstance(astro_chart, dict) or not astro_chart.get("objects"):
            raise ToolTransportError(
                bilingual("三式合一取星盘失败（/chart 未回 chart.objects）——六壬层月将 / 昼夜与外圈星盘都取自它。",
                          "sanshiunited could not get the astro chart (/chart returned no chart.objects); the 六壬 "
                          "layer's 月将 / day-night and the outer ring are read from it."),
                code="tool.sanshiunited_chart_unavailable",
                details={"request": chart_request},
            )
        is_diurnal = astro_chart.get("isDiurnal")

        qimen_result = self.run_tool(
            "qimen",
            {
                **shared,
                "options": qimen_options,
                "nongli": nongli,
                "context": {"displaySolarTime": display_solar, "isDiurnal": is_diurnal},
            },
            save_result=False,
        )
        taiyi_result = self.run_tool(
            "taiyi",
            {**shared, "options": taiyi_options, "nongli": nongli},
            save_result=False,
        )
        # 口径参数认不出（*_invalid_option）是调用方输入错误，不是引擎故障：直接报错，不出残盘。
        for _res in (qimen_result, taiyi_result):
            _err_info = _res.error
            if not _res.ok and _err_info is not None and str(getattr(_err_info, "code", "")).endswith("_invalid_option"):
                raise ToolValidationError(
                    str(getattr(_err_info, "message", "")),
                    code=str(getattr(_err_info, "code", "")),
                    details=dict(getattr(_err_info, "details", None) or {}),
                )
        if not qimen_result.ok:
            # 上游 builder 缺奇门盘即回空串（buildSanShiUnitedSnapshotText:1447）——没有「占位」形态可出。
            _err = qimen_result.error
            raise ToolTransportError(
                bilingual(f"三式合一子技法「奇门」计算失败，无法成盘：{(_err.message if _err else '') or '未知错误'}",
                          "sanshiunited: the 奇门 sub-chart failed, so no united chart can be built."),
                code="tool.sanshiunited_qimen_failed",
                details={"qimen_error": _err.model_dump(mode="json") if _err else None},
            )
        sub_warnings: list[str] = []
        taiyi_pan = taiyi_result.data.get("pan") if taiyi_result.ok and isinstance(taiyi_result.data, dict) else None
        if not taiyi_result.ok:
            _err = taiyi_result.error
            sub_warnings.append(
                f"三式合一子技法「太乙」计算失败，【太乙】【太乙十六宫】及太乙派生段缺席：{(_err.message if _err else '') or '未知错误'}"
            )

        # [紫微四化]：上游由紫微子页签上报的 UI 状态驱动（盘 + 选中的大运/流年下标），tab 未打开过就整段不产。
        # headless 把同一份选择开成 ziweiSihua 入参；紫微盘按**起课时间**另取一张（同上游 SanShiZiWeiSihua
        # buildZiweiParams：共享时间算法 + 性别）。不给该入参就不产该段。
        sihua_opts = payload.get("ziweiSihua") if isinstance(payload.get("ziweiSihua"), dict) else None
        ziwei_sihua: dict[str, Any] | None = None
        if sihua_opts is not None:
            try:
                zw = self._call_remote(
                    "/ziwei/birth",
                    {**{k: v for k, v in shared.items() if v is not None}, "gender": payload.get("gender", 1)},
                )
                zw_chart = zw.get("chart") if isinstance(zw, dict) else None
                if isinstance(zw_chart, dict):
                    ziwei_sihua = {
                        "chart": zw_chart,
                        "daxianIdx": sihua_opts.get("daxianIdx") or 0,
                        "liunianIdx": sihua_opts.get("liunianIdx") or 0,
                    }
                else:
                    _degrade("sanshi ziwei sihua: /ziwei/birth returned no chart")
            except Exception as exc:  # noqa: BLE001 — 富化失败不许带崩三式主盘
                _degrade("sanshi ziwei sihua fetch failed: %s", exc)

        js_result = self.js_client.run(
            "sanshiunited",
            {
                "date": payload["date"],
                "time": payload["time"],
                "zone": payload["zone"],
                "lat": payload["lat"],
                "lon": payload["lon"],
                "gpsLat": payload.get("gpsLat"),
                "gpsLon": payload.get("gpsLon"),
                "ad": payload.get("ad", 1),
                "options": {"timeAlg": time_alg, **day_switches, "sex": sex, "liureng": liureng_options},
                "nongli": nongli,
                "displaySolarTime": display_solar,
                "dunjia": qimen_result.data.get("pan", {}),
                "taiyi": taiyi_pan,
                "chart": chart,
                "ziweiSihua": ziwei_sihua,
                "liurengYue": payload.get("liureng_yue"),
                "liurengIsDiurnal": payload.get("liureng_isDiurnal"),
            },
        )
        data = js_result.get("data") if isinstance(js_result.get("data"), dict) else {}
        # 六壬层口径（贵人 / 换将 / 分昼夜 / 涉害 / 阴阳系 / 年神序 / 土旺衰）由 JS 按上游 SANSHI_PAGE_SETTINGS 词表校验；
        # 其余失败（缺输入 / 三传起不出 / 快照空）是构建失败，不是参数错。
        if isinstance(data.get("error"), dict) and data["error"].get("code") == "invalid_option":
            _raise_js_option_error("sanshiunited", js_result)
        snapshot_text = js_result.get("snapshot_text")
        if not data.get("ok") or not isinstance(snapshot_text, str) or not snapshot_text.strip():
            error = data.get("error") if isinstance(data.get("error"), dict) else {}
            raise ToolTransportError(
                bilingual(f"三式合一快照构建失败：{error.get('message') or '未知错误'}",
                          "sanshiunited: building the united snapshot failed (see details.error)."),
                code=f"tool.sanshiunited_{error.get('code') or 'snapshot_failed'}",
                details={"error": error},
            )
        for note in data.get("warnings") or []:
            sub_warnings.append(str(note))
        subresults = {
            "qimen": _build_compact_subresult_contract(qimen_result),
            "taiyi": _build_compact_subresult_contract(taiyi_result),
        }
        return {
            "qimen": qimen_result.data.get("pan", {}),
            "taiyi": taiyi_pan or {},
            "liureng": data.get("liureng") or {},
            "subresults": subresults,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="sanshiunited", snapshot_text=snapshot_text),
            "prerequisites": {
                "nongli_request": nongli_request,
                "displaySolarTime": display_solar,
                "chart_request": chart_request,
                "isDiurnal": is_diurnal,
            },
            **({"_warnings": sub_warnings} if sub_warnings else {}),
        }
