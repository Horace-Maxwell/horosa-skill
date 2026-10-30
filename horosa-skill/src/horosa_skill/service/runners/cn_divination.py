"""中国占卜 runner（CnDivinationRunners）：小六壬、飞宫、小成图、皇极轨策、神数正传、骰子、塔罗、灵棋经、天文地占、六爻。"""
from __future__ import annotations

from typing import Any

from horosa_skill.errors import (
    HorosaSkillError,
    ToolTransportError,
    ToolValidationError,
    bilingual,
)
from horosa_skill.service._common import _SIXYAO_DIZHI, _leading_year_of
from horosa_skill.service._context import _degrade
from horosa_skill.service.options_cn import (
    _day_boundary_switches,
    _ken_datetime_parts,
    _zhengchuan_xinyi_query,
)
from horosa_skill.service.options_zeri import _require_cast_geo
from horosa_skill.service.text.chinese import (
    _derive_changed_gua_code,
    _derive_gua_code,
    _gua_code_lines,
    _normalize_gua_lines,
)
from horosa_skill.service.text.divination import (
    _GEOMANCY_OPTION_KEYS,
    _GEOMANCY_PROFILES,
    _GEOMANCY_QUESTION_HOUSE,
    _GEOMANCY_QUESTION_TYPES,
    _build_geomancy_snapshot_text,
    _geomancy_time_seed,
)
from horosa_skill.service.text.western import _build_otherbu_snapshot_text


class CnDivinationRunners:
    def _run_xiaoliuren_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 小六壬：三数起三传（主流六宫/道门九宫）。起课为冻结值——显式 nums 优先；缺 nums 则按占时正统起
        # （农历月 monthInt / 农历日 dayInt / 时支序 三数，前置 /nongli/time 派生，JS 层不发 HTTP，AGENTS §4）。
        nums = payload.get("nums")
        time_lines: list[str] = []
        if not (isinstance(nums, list) and len(nums) == 3):
            _require_cast_geo(payload, tool="xiaoliuren")
            nongli = self._call_remote(
                "/nongli/time",
                {
                    "date": payload["date"],
                    "time": payload["time"],
                    "zone": payload["zone"],
                    "lon": payload.get("lon"),
                    # 🔴 timeAlg 必须转发：真太阳时会改时支（经度差 >7.5° 即可跨支），
                    # 时支一变卦局/起支全变。qimen/taiyi/zhengchuan 三处一直在转发，端点
                    # 明确支持；这几处漏了 → 同一份入参在不同技法间起出不同的盘。
                    "timeAlg": payload.get("timeAlg"),
                    "lat": payload.get("lat"),
                    **_day_boundary_switches(payload),
                },
            )
            month_int = nongli.get("monthInt") if isinstance(nongli, dict) else None
            day_int = nongli.get("dayInt") if isinstance(nongli, dict) else None
            hour_gz = str(nongli.get("time") or "") if isinstance(nongli, dict) else ""
            hour_zhi = hour_gz[1] if len(hour_gz) >= 2 else ""
            hour_idx = (_SIXYAO_DIZHI.index(hour_zhi) + 1) if hour_zhi in _SIXYAO_DIZHI else None
            if not (month_int and day_int and hour_idx):
                raise ToolValidationError(
                    "小六壬占时起数失败：无法从 /nongli/time 取得 农历月/日/时支。请显式给 nums=[月,日,时] 或提供完整 date/time。",
                    code="tool.xiaoliuren_cast_unavailable",
                    details={"monthInt": month_int, "dayInt": day_int, "hourZhi": hour_zhi},
                )
            nums = [month_int, day_int, hour_idx]
            time_lines = [
                f"起卦时间:{payload.get('date')} {payload.get('time')}",
                f"农历:{month_int}月{day_int}日 {hour_zhi}时（时支序{hour_idx}）",
            ]
        js_result = self.js_client.run(
            "xiaoliuren",
            {
                "nums": nums,
                "school": payload.get("school", "main"),
                "showOneThree": payload.get("showOneThree", True),
                "askEvent": payload.get("askEvent") or payload.get("question") or "",
                "timeLines": time_lines,
            },
        )
        snapshot_text = js_result.get("snapshot_text")
        return {
            "xiaoliuren": js_result.get("data", {}),
            "input_normalized": js_result.get("input_normalized", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="xiaoliuren", snapshot_text=snapshot_text),
        }

    def _run_feigong_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 飞宫小奇门：起支 + 日干支定局（冻结）。显式 qiZhi/dayGan/dayZhi 优先；缺则占时起
        # （/nongli/time → 时支作起支 + 日干支），JS 层不发 HTTP（AGENTS §4）。
        qi_mode = payload.get("qiMode", "hour")
        day_gan = payload.get("dayGan")
        day_zhi = payload.get("dayZhi")
        hour_zhi = payload.get("hourZhi")
        time_lines: list[str] = []
        need_hour = qi_mode == "hour" and not payload.get("qiZhi") and not hour_zhi
        if (not day_gan or not day_zhi or need_hour) and payload.get("date"):
            _require_cast_geo(payload, tool="feigong")
            nongli = self._call_remote(
                "/nongli/time",
                {
                    "date": payload["date"],
                    "time": payload.get("time"),
                    "zone": payload.get("zone"),
                    "lon": payload.get("lon"),
                    # 🔴 timeAlg 必须转发：真太阳时会改时支（经度差 >7.5° 即可跨支），
                    # 时支一变卦局/起支全变。qimen/taiyi/zhengchuan 三处一直在转发，端点
                    # 明确支持；这几处漏了 → 同一份入参在不同技法间起出不同的盘。
                    "timeAlg": payload.get("timeAlg"),
                    "lat": payload.get("lat"),
                    **_day_boundary_switches(payload),
                },
            )
            if isinstance(nongli, dict):
                day_gz = str(nongli.get("dayGanZi") or "")
                if len(day_gz) >= 2:
                    day_gan = day_gan or day_gz[0]
                    day_zhi = day_zhi or day_gz[1]
                hour_gz = str(nongli.get("time") or "")
                if len(hour_gz) >= 2 and not hour_zhi:
                    hour_zhi = hour_gz[1]
                time_lines = [
                    f"起卦时间:{payload.get('date')} {payload.get('time') or ''}".strip(),
                    f"农历:{nongli.get('monthInt')}月{nongli.get('dayInt')}日 {hour_zhi}时",
                ]
        js_result = self.js_client.run(
            "feigong",
            {
                "qiMode": qi_mode,
                "qiZhi": payload.get("qiZhi"),
                "hourZhi": hour_zhi,
                "zhi": payload.get("zhi"),
                "num": payload.get("num"),
                "yearZhi": payload.get("yearZhi"),
                "dayGan": day_gan,
                "dayZhi": day_zhi,
                "mingAge": payload.get("mingAge"),
                "mingGender": payload.get("mingGender", "male"),
                "liuYueMonth": payload.get("liuYueMonth"),
                "koujing": payload.get("koujing", "zheng"),
                "askEvent": payload.get("askEvent") or payload.get("question") or "",
                "timeLines": time_lines,
            },
        )
        data = js_result.get("data", {})
        if isinstance(data, dict) and data.get("ok") is False:
            raise ToolValidationError(
                "飞宫小奇门起局失败：无法定起支/日干支。请显式给 qiZhi + dayGan + dayZhi，或提供完整 date/time 按占时起局。",
                code="tool.feigong_cast_unavailable",
                details={"reason": data.get("reason"), "qiMode": qi_mode},
            )
        snapshot_text = js_result.get("snapshot_text")
        return {
            "feigong": data,
            "input_normalized": js_result.get("input_normalized", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="feigong", snapshot_text=snapshot_text),
        }

    def _run_xiaochengtu_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 小成图：五式起卦（manual/number/stock/dayan/time）。卦为冻结值。占时=梅花时间卦：Python 前置
        # /nongli/time 算 upNum=年支序+农历月+日、loNum=upNum+时支序（镜像上游·之卦=本卦不加动爻），
        # 以 number 模式喂 JS（JS 不发 HTTP，AGENTS §4）。
        fa = payload.get("qiguaFa", "manual")
        request: dict[str, Any] = {
            "qiguaFa": fa,
            "up": payload.get("up"),
            "lo": payload.get("lo"),
            "dongYaos": payload.get("dongYaos"),
            "upNum": payload.get("upNum"),
            "loNum": payload.get("loNum"),
            "qiguaShu": payload.get("qiguaShu", "tiandi"),
            "open": payload.get("open"),
            "close": payload.get("close"),
            "seed": payload.get("seed"),
            "manualCounts": payload.get("manualCounts"),
            "yongGong": payload.get("yongGong", 1),
            "kline": payload.get("kline"),
            "askEvent": payload.get("askEvent") or payload.get("question") or "",
            # 闢卦细判口径（上游挂载 schema xiaochengtu.piKoujing：zheng 正传缺省 / yiwen 异文）→ [四象]。
            "piKoujing": payload.get("piKoujing"),
            "timeLines": [],
        }
        if fa == "time":
            _require_cast_geo(payload, tool="xiaochengtu")
            nongli = self._call_remote(
                "/nongli/time",
                {
                    "date": payload["date"],
                    "time": payload.get("time"),
                    "zone": payload.get("zone"),
                    "lon": payload.get("lon"),
                    # 🔴 timeAlg 必须转发：真太阳时会改时支（经度差 >7.5° 即可跨支），
                    # 时支一变卦局/起支全变。qimen/taiyi/zhengchuan 三处一直在转发，端点
                    # 明确支持；这几处漏了 → 同一份入参在不同技法间起出不同的盘。
                    "timeAlg": payload.get("timeAlg"),
                    "lat": payload.get("lat"),
                    **_day_boundary_switches(payload),
                },
            )
            year_gz = str(nongli.get("year") or "") if isinstance(nongli, dict) else ""
            year_zhi = year_gz[1] if len(year_gz) >= 2 else ""
            month_int = nongli.get("monthInt") if isinstance(nongli, dict) else None
            day_int = nongli.get("dayInt") if isinstance(nongli, dict) else None
            hour_gz = str(nongli.get("time") or "") if isinstance(nongli, dict) else ""
            hour_zhi = hour_gz[1] if len(hour_gz) >= 2 else ""
            year_idx = (_SIXYAO_DIZHI.index(year_zhi) + 1) if year_zhi in _SIXYAO_DIZHI else None
            hour_idx = (_SIXYAO_DIZHI.index(hour_zhi) + 1) if hour_zhi in _SIXYAO_DIZHI else None
            if not (year_idx and month_int and day_int and hour_idx):
                raise ToolValidationError(
                    "小成图占时起卦失败：无法从 /nongli/time 取得 年支/农历月日/时支。请改用 manual/number/stock/dayan 显式起卦。",
                    code="tool.xiaochengtu_cast_unavailable",
                    details={"yearZhi": year_zhi, "monthInt": month_int, "dayInt": day_int, "hourZhi": hour_zhi},
                )
            up_num = year_idx + month_int + day_int
            lo_num = up_num + hour_idx
            request["qiguaFa"] = "number"
            request["upNum"] = up_num
            request["loNum"] = lo_num
            request["timeLines"] = [
                f"起卦时间:{payload.get('date')} {payload.get('time') or ''}".strip(),
                f"梅花时间卦:上数{up_num}(年支序{year_idx}+农历{month_int}月+{day_int}日) 下数{lo_num}(+时支序{hour_idx})",
            ]
        js_result = self.js_client.run("xiaochengtu", request)
        data = js_result.get("data", {})
        if isinstance(data, dict) and data.get("ok") is False:
            reason = data.get("reason")
            code = "tool.xiaochengtu_dayan_seed_required" if reason == "dayan_seed_required" else "tool.xiaochengtu_bad_cast"
            raise ToolValidationError(
                data.get("message") or "小成图起卦失败。",
                code=code,
                details={"reason": reason, "qiguaFa": fa},
            )
        snapshot_text = js_result.get("snapshot_text")
        return {
            "xiaochengtu": data,
            "input_normalized": js_result.get("input_normalized", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="xiaochengtu", snapshot_text=snapshot_text),
        }

    def _run_guice_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 皇极轨策：十二法起卦 + 演数四位 + 卦变断法 + 元会运世 + 大定。卦为冻结值。占时四柱（立春界年柱 +
        # 农历月日 + 时支）由前置 /nongli/time 拼 ctx 后传入，JS 层不发 HTTP（AGENTS §4）。
        # settings 十开关 + 各法专属起卦字段（nums/wuShu/… + shu2/tones/zhang/chi/cun/qu/wuGuaNum/fangGuaNum/kind）
        # 经 FlexibleModel extra 透传，此处整体转发（qiGua/normalizeGuiceSettings 忽略多余键）。
        passthrough_keys = (
            "qiguaFa", "school", "yanshuFa", "jiGongMode", "qiguaShu", "shenSha", "shiFang", "shuXi",
            "dadingTable", "shiyingSet", "nums", "wuShu", "shengShu", "text", "shu", "shu2", "tones",
            "zhang", "chi", "cun", "qu", "wuGuaNum", "fangGuaNum", "kind", "hourZhi", "shiyingInputs", "fangKey",
        )
        request: dict[str, Any] = {k: payload.get(k) for k in passthrough_keys if payload.get(k) is not None}
        request["askEvent"] = payload.get("askEvent") or payload.get("question") or ""
        time_lines: list[str] = []
        if payload.get("date"):
            _require_cast_geo(payload, tool="guice")
            nongli = self._call_remote(
                "/nongli/time",
                {
                    "date": payload["date"],
                    "time": payload.get("time"),
                    "zone": payload.get("zone"),
                    "lon": payload.get("lon"),
                    # 🔴 timeAlg 必须转发：真太阳时会改时支（经度差 >7.5° 即可跨支），
                    # 时支一变卦局/起支全变。qimen/taiyi/zhengchuan 三处一直在转发，端点
                    # 明确支持；这几处漏了 → 同一份入参在不同技法间起出不同的盘。
                    "timeAlg": payload.get("timeAlg"),
                    "lat": payload.get("lat"),
                    **_day_boundary_switches(payload),
                },
            )
            if isinstance(nongli, dict):
                year_jieqi = str(nongli.get("yearJieqi") or nongli.get("year") or "")
                month_gz = str(nongli.get("monthGanZi") or "")
                day_gz = str(nongli.get("dayGanZi") or "")
                hour_gz = str(nongli.get("time") or "")
                if len(year_jieqi) >= 2:
                    request["yearZhi"] = year_jieqi[1]
                if len(month_gz) >= 2:
                    request["monthZhi"] = month_gz[1]
                request["lunarMonth"] = nongli.get("monthInt")
                request["lunarDay"] = nongli.get("dayInt")
                if len(hour_gz) >= 2 and not request.get("hourZhi"):
                    request["hourZhi"] = hour_gz[1]
                if len(day_gz) >= 2:
                    request["dayGan"] = day_gz[0]
                request["pillars"] = [p for p in (year_jieqi, month_gz, day_gz, hour_gz) if len(p) >= 2]
                # 上游 GuiceMain.ctxLive（:219）`leadingYearOf(nl.date || '') || undefined`：取农历回包的带符号日期串首年。
                # 旧 lstrip('-') × ad 把公元前 '-0500-03-21'（ad 缺省 1）读成公元 500 年。
                request["year"] = _leading_year_of(nongli.get("date") or "") or None
                time_lines = [
                    f"起卦时间:{payload.get('date')} {payload.get('time') or ''}".strip(),
                    f"农历:{nongli.get('monthInt')}月{nongli.get('dayInt')}日 四柱[{'·'.join(request.get('pillars') or [])}]",
                ]
        # 显式 ctx 覆盖（无 date 时可直接给年支/月支/农历月日/时支等）。
        for k in ("yearZhi", "monthZhi", "lunarMonth", "lunarDay", "year", "dayGan", "pillars"):
            if payload.get(k) is not None:
                request[k] = payload[k]
        request["timeLines"] = time_lines
        js_result = self.js_client.run("guice", request)
        data = js_result.get("data", {})
        if isinstance(data, dict) and data.get("ok") is False:
            raise ToolValidationError(
                data.get("message") or "皇极轨策起卦失败：所需之输入未足。",
                code="tool.guice_insufficient_cast_input",
                details={"reason": data.get("reason"), "qiguaFa": payload.get("qiguaFa")},
            )
        snapshot_text = js_result.get("snapshot_text")
        return {
            "guice": data,
            "input_normalized": js_result.get("input_normalized", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="guice", snapshot_text=snapshot_text),
        }

    def _run_zhengchuan_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 神数正传（五流派）：除 xinyi 查询层外，四柱走 /nongli/time 权威口径（立春界年柱 + 农历月日 + 时柱），
        # JS 层不发 HTTP（AGENTS §4）；条文正文库由 JS 异步载入。dading 另需 birth params 建 bazi 推运表。
        school = payload.get("school", "tieban")
        request: dict[str, Any] = {"school": school}
        if school == "xinyi":
            request.update(_zhengchuan_xinyi_query(payload))
        else:
            _require_cast_geo(payload, tool="zhengchuan")
            # 时间算法一处定、两处用：四柱（/nongli/time）与大定推运表（JS buildLocalBaziResult）必须同口径 ——
            # 上游两路都是一次 buildLocalBaziResult 同出四柱与推运表（aiAnalysisContext.buildChartShusuanBazi:1948-1979，
            # 无头缺省 timeAlg = record.timeAlg ?? 0 真太阳时，buildFieldObject:603）。此前四柱走后端缺省 0、推运表走
            # JS 缺省 1，真太阳时跨时辰的生辰两边时柱不同（sync311 wave 3）。
            time_alg = payload.get("timeAlg")
            time_alg = 0 if time_alg is None else time_alg
            nongli = self._call_remote(
                "/nongli/time",
                {
                    "date": payload["date"],
                    "time": payload.get("time"),
                    "zone": payload.get("zone"),
                    "lon": payload.get("lon"),
                    "lat": payload.get("lat"),
                    "timeAlg": time_alg,
                    **_day_boundary_switches(payload),
                },
            )
            if not isinstance(nongli, dict):
                raise ToolValidationError(
                    "神数正传起盘失败：/nongli/time 未返回农历数据。",
                    code="tool.zhengchuan_pillars_unavailable",
                    details={"school": school},
                )
            pillars = [
                str(nongli.get("yearJieqi") or nongli.get("year") or ""),
                str(nongli.get("monthGanZi") or ""),
                str(nongli.get("dayGanZi") or ""),
                str(nongli.get("time") or ""),
            ]
            if any(len(p) < 2 for p in pillars):
                raise ToolValidationError(
                    "神数正传起盘失败：/nongli/time 未返回完整四柱（年/月/日/时）。请提供完整 date/time。",
                    code="tool.zhengchuan_pillars_unavailable",
                    details={"pillars": pillars},
                )
            request["pillars"] = pillars
            request["lunarMonth"] = nongli.get("monthInt")
            # 农历日 = 后端 dayInt（钟面农历日：23 点档随日柱进位时它不进位，live 实测 after23NewDay 0/1 同值）。
            # 这正是上游 AI 挂载无头口径 —— buildChartShusuanBazi 取 bazi.nongli.dayNum（aiAnalysisContext.js:1971-1972，
            # 钟面日；进位值只在 ziwei* 键）；页面 ZhengChuanMain.getModel 另走 lunarByDayBoundary 进位（:193-196），两路
            # 不一致按无头（sync311 wave 3b 核定，tests/test_sync311_divination_w3b.py 钉值 + 上游源绊线）。
            request["lunarDay"] = nongli.get("dayInt")
            request["isLeapMonth"] = bool(nongli.get("leap"))
            request["gender"] = payload.get("gender")
            for key in ("askGz", "fatherAge", "motherAge", "yuan", "askHourZhi", "env", "dadingYear", "dayun", "xiaoyun", "suijun", "age"):
                if payload.get(key) is not None:
                    request[key] = payload[key]
            if school == "dading":
                # dading 的 JS 端需 birth params 建 bazi 推运表（小运/大运/岁君·年粒度）；timeAlg 与四柱同值。
                for key in ("date", "time", "zone", "lon", "after23NewDay", "lateZiHourUseNextDay"):
                    if payload.get(key) is not None:
                        request[key] = payload[key]
                request["timeAlg"] = time_alg
        js_result = self.js_client.run("zhengchuan", request)
        data = js_result.get("data", {})
        if isinstance(data, dict) and data.get("ok") is False:
            raise ToolValidationError(
                data.get("message") or "神数正传排盘失败。",
                code="tool.zhengchuan_calc_failed",
                details={"reason": data.get("reason"), "school": school},
            )
        snapshot_text = js_result.get("snapshot_text")
        return {
            "zhengchuan": data,
            "input_normalized": js_result.get("input_normalized", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="zhengchuan", snapshot_text=snapshot_text),
        }

    def _run_otherbu_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        remote_payload = {
            **payload,
            "date": payload["date"],
            "time": payload["time"],
            "zone": payload["zone"],
            "lon": payload["lon"],
            "lat": payload["lat"],
            "gpsLon": payload.get("gpsLon"),
            "gpsLat": payload.get("gpsLat"),
            "hsys": payload.get("hsys", 0),
            "zodiacal": payload.get("zodiacal", 0),
            "tradition": payload.get("tradition", False),
            "virtualPointReceiveAsp": payload.get("virtualPointReceiveAsp"),
            "sign": payload.get("sign", "Aries"),
            "house": payload.get("house", 0),
            "planet": payload.get("planet", "Sun"),
        }
        response = self._call_remote("/predict/dice", remote_payload)
        snapshot_text = _build_otherbu_snapshot_text({**remote_payload, "question": payload.get("question")}, response)
        result = {**response, "question": payload.get("question"), "snapshot_text": snapshot_text}
        result["export_snapshot"] = self._augment_export_payload(technique="otherbu", snapshot_text=snapshot_text)
        return result

    def _run_tarot_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 塔罗：core-js tarot 引擎 SHA-256 种子洗牌 + 解读。种子 = 上游「生辰」种子来源 seedFromFields
        # （TarotMain.js:97-108）：name|date|time|lat|lon 取非空项以 | 相连（全空 → 'horosa-tarot-default'）；
        # 显式 seed 覆盖。此前 skill 用 yyyyMMddHHmm，与上游同一盘抽出不同的牌（sync311 F10）。
        seed = payload.get("seed")
        if seed is None or f"{seed}".strip() == "":
            parts = [f"{payload.get(k)}".strip() for k in ("name", "date", "time", "lat", "lon") if payload.get(k) not in (None, "")]
            seed = "|".join(p for p in parts if p) or "horosa-tarot-default"
        js_payload: dict[str, Any] = {
            "seed": str(seed),
            "question": payload.get("question") or "",
            "deck": payload.get("deck") or "rws",
        }
        # 牌阵缺省交给 JS 按牌组允许表定（rws 等 = three）；给了就原样送，由引擎词表裁决。
        if payload.get("spread"):
            js_payload["spread"] = payload.get("spread")
        # 逆位：缺省随牌组；显式 true/false 都下发（此前只发 false，马赛系等默认无逆位的牌组开不了逆位）。
        if payload.get("usesReversals") is not None:
            js_payload["usesReversals"] = bool(payload.get("usesReversals"))
        for key in ("dignities", "variant", "verdictMode", "birth"):
            if payload.get(key) is not None:
                js_payload[key] = payload.get(key)
        # 其余 19 个引擎判读设置（timingMethod/timingUnit/meaningSystem/reversalMode/…）：键集锚引擎 resolveSettings。
        if isinstance(payload.get("options"), dict):
            js_payload["options"] = payload.get("options")
        try:
            result = self.js_client.run("tarot", js_payload)
        except ToolTransportError as exc:
            _degrade("tarot JS engine failed: %s", exc)
            result = {}
        data = result.get("data") if isinstance(result, dict) and isinstance(result.get("data"), dict) else {}
        if data.get("ok") is False:
            error = data.get("error") if isinstance(data.get("error"), dict) else {}
            code = {
                "unknown_deck": "tool.tarot_unknown_deck",
                "unknown_spread": "tool.tarot_unknown_spread",
                "unsupported_spread_for_deck": "tool.tarot_unsupported_spread_for_deck",
                "invalid_setting": "tool.tarot_invalid_setting",
            }.get(str(error.get("code") or ""))
            if code:
                raise ToolValidationError(
                    bilingual(f"塔罗入参不被引擎接受：{error.get('message')}", f"tarot input rejected by the engine: {error.get('message')}"),
                    code=code,
                    details={**(error.get("details") or {}), "engine_error": error.get("code")},
                )
            _degrade("tarot JS engine produced no reading: %s", error.get("message") or error)
        snapshot_text = result.get("snapshot_text") if isinstance(result, dict) else ""
        ignored = list(data.get("params_ignored") or [])
        out: dict[str, Any] = {
            "deck": (isinstance(result, dict) and result.get("deck")) or js_payload["deck"],
            "spread": (isinstance(result, dict) and result.get("spread")) or js_payload.get("spread"),
            "seed": str(seed),
            "params_applied": list(data.get("params_applied") or []),
            "params_ignored": ignored,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="tarot", snapshot_text=snapshot_text),
        }
        if ignored:
            out["_warnings"] = [f"tarot 未识别的 options 键已忽略：{'、'.join(ignored)}（键集锚引擎 resolveSettings）。"]
        return out

    def _run_lingqi_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 灵棋经（上游 v3.9.0）：纯 headless JS —— 占时种子掷十二棋 → counts[上,中,下] → 六十四卦查表，
        # 七段快照由 vendored lingqiSnapshot 产出。种子算法留在 vendored core 里（tools/lingqi.js 只喂
        # 等价的 date/time 字段 shim），两边不各写一份。
        parts = _ken_datetime_parts(payload)
        js_payload: dict[str, Any] = {
            "year": parts["year"],
            "month": parts["month"],
            "day": parts["day"],
            "hour": parts["hour"],
            "minute": parts["minute"],
            "question": payload.get("question") or "",
            "category": payload.get("category") or "general",
            "timeLines": self._lingqi_time_lines(payload, parts),
        }
        if isinstance(payload.get("counts"), list):
            js_payload["counts"] = payload["counts"]
        if isinstance(payload.get("zhuVisible"), dict):
            js_payload["zhuVisible"] = payload["zhuVisible"]
        # 六戊日提示（卷首「六戊日不宜占卜」）需要日干支。走本仓 nongli 后端拿，**不**在 JS 侧引
        # lunar-javascript 另算一份——同口径原则（法奇门 faRelatedPeople 年干也是这么处理的）。
        # 拿不到就不给该行：提示缺失远好于按错口径印一行假的。
        day_ganzhi = self._lingqi_day_ganzhi(payload)
        if day_ganzhi:
            js_payload["dayGanZi"] = day_ganzhi
        # 引擎失败就是本技法失败：照其他 JS 技法上抛传输错误，不回一份 ok 的空盘。
        result = self.js_client.run("lingqi", js_payload)
        snapshot_text = result.get("snapshot_text")
        return {
            "counts": result.get("counts") or js_payload.get("counts"),
            "seed": result.get("seed") or None,
            "category": js_payload["category"],
            "day_ganzhi": day_ganzhi,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="lingqi", snapshot_text=snapshot_text),
        }

    def _lingqi_time_lines(self, payload: dict[str, Any], parts: dict[str, int]) -> list[str]:
        """[起盘信息] 的占时行。上游由 UI 拼，headless 这边按归一化输入如实拼一行。"""
        zone = f"{payload.get('zone') or ''}".strip()
        stamp = (
            f"{parts['year']:04d}-{parts['month']:02d}-{parts['day']:02d} "
            f"{parts['hour']:02d}:{parts['minute']:02d}"
        )
        return [f"占时：{stamp}{f'（{zone}）' if zone else ''}"]

    def _lingqi_day_ganzhi(self, payload: dict[str, Any]) -> str:
        try:
            nongli = self._call_remote(
                "/nongli/time",
                {
                    "date": payload.get("date"),
                    "time": payload.get("time") or "00:00:00",
                    "zone": payload.get("zone"),
                    "lat": payload.get("lat"),
                    "lon": payload.get("lon"),
                    "timeAlg": payload.get("timeAlg"),
                    # 显式 None 会把 null 发上线；帮手的纪律是「只在显式给定时发送」，
                    # 缺省不发 → 后端按默认 1/1 起算，与未传字节级等价。
                    **_day_boundary_switches(payload),
                },
            )
        except HorosaSkillError:
            return ""
        if not isinstance(nongli, dict):
            return ""
        # 后端两种形状都见过：顶层 dayGanZi 串，或 bazi.day.stem.cell。取到哪个用哪个，取不到就空。
        raw = nongli.get("dayGanZi") or nongli.get("dayGanzhi")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        bazi = nongli.get("bazi") if isinstance(nongli.get("bazi"), dict) else {}
        day = bazi.get("day") if isinstance(bazi.get("day"), dict) else {}
        stem = day.get("stem") if isinstance(day.get("stem"), dict) else {}
        cell = stem.get("cell")
        return f"{cell}".strip() if isinstance(cell, str) else ""

    def _run_geomancy_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 天文地占：以起卦时刻确定性起卦（castMethod='time' + timeSeed 由 年月日时分 派生，同盘可复现），
        # 后端 /geomancy/reading 由 4 母卦推 16 图形 + 十二宫图形入宫 + 判官/见证/解读技法 + 转宫派生 + 定局落星。
        options = payload.get("options") if isinstance(payload.get("options"), dict) else {}
        profile = payload.get("profile") or "european_classical"
        chart_mode = options.get("chartMode")
        # ifa（西非同族）是结构对照模式：不产地占判读、须随附文化声明。skill 只暴露 8 家占断传本，明确拒绝
        # ifa（含经 options.chartMode 触发），给结构化错误 + 声明，绝不静默降级出空盘。
        if profile == "ifa" or chart_mode == "ifa":
            raise ToolValidationError(
                "天文地占的 ifa（西非同族）为结构对照模式，只作图形/比特同构对照、不产出该体系之占断，"
                "故本 skill 不作为可调用能力暴露。请改用 "
                + "/".join(_GEOMANCY_PROFILES) + " 之一。",
                code="tool.geomancy_structural_only_unsupported",
                details={"profile": profile, "chartMode": chart_mode,
                         "cultural_notice": "Ifá 为独立圣传体系，仅结构同构对照，不套地占含义、不构成占断。"},
            )
        if profile not in _GEOMANCY_PROFILES:
            profile = "european_classical"
        question_type = f"{payload.get('questionType') or 'custom'}".strip() or "custom"
        if question_type not in _GEOMANCY_QUESTION_TYPES:
            raise ToolValidationError(
                bilingual(
                    f"地占问类 {question_type!r} 不存在（后端只认 {'/'.join(_GEOMANCY_QUESTION_TYPES)}；其余会被静默改回 custom）。",
                    f"Unknown geomancy questionType {question_type!r}; the backend knows {'/'.join(_GEOMANCY_QUESTION_TYPES)}.",
                ),
                code="tool.geomancy_invalid_question_type",
                details={"questionType": question_type, "allowed": list(_GEOMANCY_QUESTION_TYPES)},
            )
        parts = _ken_datetime_parts(payload)
        # 🔴 sync311 F10：时间起卦种子 = 上游 computeTimeSeed（YY 两位年 … mod 2^31−1）；此前 skill 用
        # YYYYMMDDHHmm 整数，与上游同一时刻起出不同的母图。
        time_seed = _geomancy_time_seed(parts)
        request: dict[str, Any] = {
            "question": payload.get("question") or "",
            "questionType": question_type,
            "castMethod": "time",
            "timeSeed": time_seed,
            "profile": profile,
        }
        # 🔴 sync311 F12：所问之时地同发（上游 GeomancyMain.clickCast :1161-1167）——后端只在
        # ascSource=real_chart / houseProjection=real_ephemeris 时用它起真实上升/真实星历（webgeomancysrv
        # _parse_time_place），此前不发 → 两档静默回落图形取法。纪元前才发 ad（公元后请求体逐字节不变）。
        for key in ("date", "time", "zone", "lat", "lon"):
            if payload.get(key) not in (None, ""):
                request[key] = payload[key]
        if payload.get("ad") == -1:
            request["ad"] = -1
        # 🔴 sync311 wave 3：所问宫 / 读取范围 / 黄道体系**恒发**，与上游两路同形 —— 页面 clickCast
        # （GeomancyMain.js:1150-1158）与 AI 挂载复算 buildGeomancySnapshotForFields（:808-817）都是
        # quesitedHouse = Number(所问宫) || QUESTION_TYPE_HOUSE[问类] || 1、readingScope || 'L3'、zodiacSystem ||
        # 'classical'，且换流派不动后两项（changeGeomancyOpt:1437-1444 只清 granular）。此前 skill 未给即不发 →
        # 内核按流派 profile 回落（chart.py:120-121）：european_planetary 走行星黄道、arabic_raml 只读到 L2 ——
        # 同一问占与上游起出两样的判读。
        try:
            quesited = int(payload.get("quesitedHouse") or 0)
        except (TypeError, ValueError):
            quesited = 0
        request["quesitedHouse"] = quesited or _GEOMANCY_QUESTION_HOUSE.get(question_type, 1)
        request["readingScope"] = payload.get("readingScope") or "L3"
        request["zodiacSystem"] = payload.get("zodiacSystem") or "classical"
        if payload.get("turnTo") is not None:
            request["turnTo"] = payload["turnTo"]
        # 传本粒度覆盖 passthrough（白名单；chartMode='ifa' 已在上方拦下，此处不会透传）。
        for key in _GEOMANCY_OPTION_KEYS:
            if options.get(key) is not None:
                request[key] = options[key]
        # 报数起卦（上游 clickCast :1175-1187）：十六个正整数，奇=单点/偶=双点，母一至母四之火风水土序；
        # castMethod=numbers + 种子（盾牌由数定，辅助随机仍须确定：缺省用本刻时间种子，options.seed 覆盖）。
        cast_numbers = options.get("castNumbers")
        if cast_numbers is not None:
            raw_numbers = cast_numbers.replace("，", ",").replace(",", " ").split() if isinstance(cast_numbers, str) else cast_numbers
            try:
                numbers = [int(x) for x in raw_numbers] if isinstance(raw_numbers, (list, tuple)) else []
            except (TypeError, ValueError):
                numbers = []
            if len(numbers) != 16 or any(n < 1 for n in numbers):
                raise ToolValidationError(
                    bilingual(
                        "报数起卦须自报十六个正整数（奇=单点、偶=双点；序为母一至母四之火风水土）。",
                        "castNumbers must be sixteen positive integers (odd = single dot, even = double dot).",
                    ),
                    code="tool.geomancy_invalid_cast_numbers",
                    details={"castNumbers": cast_numbers},
                )
            request.update({"castMethod": "numbers", "castNumbers": numbers, "seedMode": "manual"})
            request.pop("timeSeed", None)
            request["seed"] = int(options["seed"]) if options.get("seed") is not None else time_seed
        # seed 只在报数起卦里有用（时间起卦恒用 timeSeed）：单给 seed 也照实回执为未用。
        known = set(_GEOMANCY_OPTION_KEYS) | {"castNumbers"} | ({"seed"} if cast_numbers is not None else set())
        geo_ignored = sorted(k for k in options if k not in known)
        response = self._call_remote("/geomancy/reading", request)
        snapshot_text = _build_geomancy_snapshot_text(response if isinstance(response, dict) else {})
        result: dict[str, Any] = {
            "reading": response.get("reading") if isinstance(response, dict) else None,
            "figures": response.get("figures") if isinstance(response, dict) else None,
            "time_seed": request.get("timeSeed"),
            "params_ignored": geo_ignored,
        }
        if geo_ignored:
            result["_warnings"] = [f"geomancy 未识别的 options 键已忽略（未转发后端）：{'、'.join(geo_ignored)}。"]
        # [十六卦目录]（v0.33.0 批 I-5，/geomancy/catalog）：16 图形属性总表（agent grounding 用）。
        # 条件段：includeCatalog=true 才产。
        if payload.get("includeCatalog"):
            catalog = self._call_remote("/geomancy/catalog", {})
            figures = catalog.get("figures") if isinstance(catalog, dict) else None
            if not isinstance(figures, list) or not figures:
                raise ToolTransportError(
                    "地占十六卦目录端点返回了意外形状。",
                    code="tool.geomancy_catalog_failed",
                    details={"endpoint": "/geomancy/catalog"},
                )
            result["catalog"] = catalog
            cat_lines = [f"十六图形属性总表（{len(figures)} 形）："]
            for fig in figures:
                if not isinstance(fig, dict):
                    continue
                dots = fig.get("dots") if isinstance(fig.get("dots"), list) else []
                dots_txt = " ".join("●" if int(d or 0) == 1 else "●●" for d in dots)
                bits = [
                    f"{fig.get('nameZh')}（{fig.get('nameEn')}）",
                    f"卦形 {dots_txt}",
                    f"五行 {fig.get('elementZh')}",
                    f"主星 {fig.get('planetZh')}",
                    f"星座 {fig.get('signZh')}",
                    f"性 {fig.get('qualityZh')}",
                ]
                if fig.get("keywordsZh"):
                    bits.append(f"象 {fig.get('keywordsZh')}")
                cat_lines.append("　".join(bits))
            if snapshot_text:
                snapshot_text = f"{snapshot_text}\n\n[十六卦目录]\n" + "\n".join(cat_lines)
        result["snapshot_text"] = snapshot_text
        result["export_snapshot"] = self._augment_export_payload(technique="geomancy", snapshot_text=snapshot_text)
        return result

    def _run_sixyao_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # [Q-390/T-372] 占时时间算法：页面 > 全局 > 缺省真太阳时(0)（上游 GuaZhanMain.genParams，
        # GuaZhanMain.js:666-669）。此前根本不发 timeAlg → 桥恒按真太阳时，用户选「直接时间」静默无效。
        # 日界/晚子时两开关与上游同带（genParams 带 defaultAfter23NewDay/defaultLateZiHourUseNextDay）：
        # 仅显式给定时发送，缺省走后端默认 1/1 = 星阙出厂全局默认，字节与此前相同。
        time_alg = payload.get("timeAlg")
        nongli_request = {
            "date": payload["date"],
            "time": payload["time"],
            "zone": payload["zone"],
            "lon": payload["lon"],
            "lat": payload["lat"],
            "gpsLat": payload.get("gpsLat"),
            "gpsLon": payload.get("gpsLon"),
            "timeAlg": time_alg if time_alg is not None else 0,
            **_day_boundary_switches(payload),
            "ad": payload.get("ad", 1),
        }
        gender = payload.get("gender")
        if gender is not None and gender not in (0, 1):
            # 上游 buildGuaSnapshotText 只认 0/1（GuaZhanMain.js:234 `=== 0 || === 1`），别的值整行静默不出 —— 这里报错不吞。
            raise ToolValidationError(
                bilingual("六爻 gender 只认 1（男）/ 0（女）。", "sixyao gender must be 1 (male) or 0 (female)."),
                code="tool.sixyao_invalid_gender",
                details={"gender": gender},
            )
        nongli = self._call_remote("/nongli/time", nongli_request)
        lines = _normalize_gua_lines(payload.get("lines")) or _gua_code_lines(payload.get("gua_code"), payload.get("changed_code"))
        # 六爻层（core-js tools/liuyao.js）= 上游 AI 挂载无头路径 regenerateSixyaoSnapshot
        # （aiAnalysisContext.js:1739-1760）：未手动摇卦（lines 空）→ vendored buildTimeGua(nongli) 以时起卦
        # （年支序 + 农历月数 + 农历日数 + 时柱支序，时柱随 timeAlg）；齿轮 liuyaoSettings（上游 24 键扁平形）按
        # mergeLiuyaoGearSettings 合并；先载《断易天机》断语库，再由 vendored buildGuaSnapshotText(fields, st) 出**整份**
        # 快照（[起盘信息]…[占类断语] 八段，段序行式即上游；sync311 wave 3b 起不再有 Python 自写段）。
        # record = 上游 buildCaseSnapshotFields(record) 的入参（占时 + 时区 + 经纬度 + 求测人性别，:780-797）；
        # nongliParams 供 JS 按上游 ensureYearGZByLunar 补正月初一口径年干支。
        liuyao_settings = payload.get("liuyaoSettings")
        record: dict[str, Any] = {key: payload.get(key) for key in ("date", "time", "zone", "lon", "lat")}
        if gender is not None:
            record["gender"] = gender
        js_request: dict[str, Any] = {"nongli": nongli, "nongliParams": nongli_request, "record": record}
        if lines:
            js_request["lines"] = lines
        if isinstance(liuyao_settings, dict):
            js_request["liuyaoSettings"] = liuyao_settings
        try:
            struct = self.js_client.run("liuyao", js_request)
        except ToolTransportError as exc:
            # 起卦（以时）与整份快照都只在 vendored 上游函数里：引擎起不来就既起不出卦、也出不了上游快照。
            # 结构化报错，绝不回落一份自写的起卦式或自写段。
            if not lines:
                raise ToolTransportError(
                    bilingual(
                        "六爻以时起卦失败：起卦引擎（core-js buildTimeGua）不可用。请先体检 JS 运行时（horosa-skill doctor）。",
                        "sixyao time-cast failed: the core-js buildTimeGua engine is unavailable. Check the JS runtime (horosa-skill doctor).",
                    ),
                    code="tool.sixyao_time_cast_failed",
                    details={"reason": str(exc)},
                ) from exc
            raise ToolTransportError(
                bilingual(
                    "六爻快照引擎（core-js buildGuaSnapshotText）不可用：卦已由 lines 定，但出不了上游快照。请先体检 JS 运行时。",
                    "sixyao snapshot engine (core-js buildGuaSnapshotText) is unavailable: the lines fix the hexagram but the upstream snapshot cannot be built. Check the JS runtime.",
                ),
                code="tool.sixyao_engine_failed",
                details={"reason": str(exc)},
            ) from exc
        struct_data = struct.get("data") if isinstance(struct.get("data"), dict) else {}
        if struct_data.get("lines_invalid"):
            raise ToolValidationError(
                bilingual(
                    "六爻 lines 须六爻俱全（初→上），每爻 value 为 1 阳 / 0 阴。",
                    "sixyao lines must list all six lines (bottom to top), each with value 1 (yang) or 0 (yin).",
                ),
                code="tool.sixyao_invalid_lines",
                details={"lines": len(lines)},
            )
        if not lines:
            lines = _normalize_gua_lines(struct.get("lines"))
            if len(lines) != 6:
                raise ToolValidationError(
                    bilingual(
                        "六爻以时起卦失败：/nongli/time 缺年支/时柱/农历月日（buildTimeGua 取 year/time/monthInt/dayInt）。",
                        "sixyao time-cast failed: /nongli/time lacks year/time/monthInt/dayInt needed by buildTimeGua.",
                    ),
                    code="tool.sixyao_time_cast_failed",
                    details={"nongli_keys": sorted(nongli) if isinstance(nongli, dict) else []},
                )
        else:
            # 手动摇卦：回显 JS 实际装卦的逐爻（缺省爻名已按 setupYao 取该卦 yaoname）。
            lines = _normalize_gua_lines(struct.get("lines")) or lines
        current_code = payload.get("gua_code") or _derive_gua_code(lines)
        changed_code = payload.get("changed_code") or _derive_changed_gua_code(lines)
        # 卦辞原文：上游无头卦不带 guaDesc，[卦辞与断语] 只有段头（GuaZhanMain.js:338-363 + :62-63）；
        # /gua/desc 照旧取来放 data.descriptions（结构化数据面，不进快照）。
        descs = self._call_remote("/gua/desc", {"name": [current_code, changed_code]})
        snapshot_text = struct.get("snapshot_text") or ""
        if not snapshot_text.strip():
            raise ToolTransportError(
                bilingual(
                    "六爻快照引擎返回空快照（buildGuaSnapshotText）。",
                    "sixyao snapshot engine returned an empty snapshot (buildGuaSnapshotText).",
                ),
                code="tool.sixyao_engine_failed",
                details={"time_cast": bool(struct.get("time_cast"))},
            )
        result = {
            "nongli": nongli,
            "current_code": current_code,
            "changed_code": changed_code,
            "lines": lines,
            "question": payload.get("question"),
            "descriptions": descs,
            "snapshot_text": snapshot_text,
        }
        if struct_data.get("settings"):
            result["liuyao_settings"] = struct_data["settings"]
        warnings: list[str] = []
        if struct_data.get("settings_ignored"):
            warnings.append(
                f"liuyaoSettings 中这些键不是六爻判读口径，已忽略：{struct_data['settings_ignored']}"
                "（可用键见 horosa_agent_guidance(tool_name=\"sixyao\")）。"
            )
        if struct_data.get("settings_invalid"):
            warnings.append(
                f"liuyaoSettings 取值不在词表内，已按缺省处理：{struct_data['settings_invalid']}。"
            )
        # JS 层自报的缺损（断语库未载入 / 正月初一口径年干支补不出）：上游同样不阻断快照，这里如实回执。
        for note in struct_data.get("warnings") or []:
            if isinstance(note, str) and note and note not in warnings:
                warnings.append(note)
        if warnings:
            result["_warnings"] = warnings
        result["export_snapshot"] = self._augment_export_payload(technique="sixyao", snapshot_text=snapshot_text)
        return result
