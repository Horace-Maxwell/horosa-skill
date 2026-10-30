"""命理 runner（MingliRunners）：节气八字、八字、紫微、统摄法、参评数、河洛、反推八字、一掌经、黄历、通书。"""
from __future__ import annotations

from typing import Any

from horosa_skill.errors import ToolTransportError, ToolValidationError, bilingual
from horosa_skill.service._common import (
    _civil_wall_ms_of_moment,
    _GANZHI_BRANCHES,
    _GANZHI_STEMS,
    _render_snapshot_text,
)
from horosa_skill.service._context import _degrade
from horosa_skill.service.options_cn import _day_boundary_switches


class MingliRunners:
    # ── 出生节气窗（批 I-3，/jieqi/birth）───────────────────────────────────────

    def _run_jieqi_birth_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        remote = {
            "date": payload.get("date"),
            "time": payload.get("time"),
            "zone": payload.get("zone"),
            "lat": payload.get("lat"),
            "lon": payload.get("lon"),
        }
        for key in ("ad", "useLocalMao", "byLon"):
            if payload.get(key) is not None:
                remote[key] = payload.get(key)
        response = self._call_remote("/jieqi/birth", remote)
        rows = response.get("jieqi") if isinstance(response, dict) else None
        if not isinstance(rows, list) or not rows:
            raise ToolTransportError(
                "出生节气端点返回了意外形状。",
                code="tool.jieqi_birth_failed",
                details={"endpoint": "/jieqi/birth"},
            )
        info_lines = [
            f"出生：{payload.get('date')} {payload.get('time')}（{payload.get('zone')}）",
            f"地点：{payload.get('pos') or ''}　经度 {payload.get('lon')} 纬度 {payload.get('lat')}".rstrip(),
        ]
        # 括界按民用历墙钟毫秒比（_civil_wall_ms_of_moment，非严格）：旧做法是字符串比较，公元前出生（'-0500-03-21'）
        # 对后端回的 '-500-03-11 …' 恒「小于」→ 括界行整条缺席；年不足 4 位（'999-…' vs '0999-…'）同病。
        birth_ms = _civil_wall_ms_of_moment(f"{payload.get('date')} {payload.get('time')}".strip(), strict=False)
        row_lines: list[str] = []
        prev_row: dict[str, Any] | None = None
        bracket: tuple[dict[str, Any], dict[str, Any]] | None = None
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_lines.append(f"{row.get('jieqi')}（{'节' if row.get('jie') else '气'}）　{row.get('time')}")
            # 括界判定：民用历墙钟时刻比较（后端时刻同时区），非任何技法推算。
            if prev_row is not None and bracket is None and birth_ms is not None:
                lo = _civil_wall_ms_of_moment(f"{prev_row.get('time')}", strict=False)
                hi = _civil_wall_ms_of_moment(f"{row.get('time')}", strict=False)
                if lo is not None and hi is not None and lo <= birth_ms < hi:
                    bracket = (prev_row, row)
            prev_row = row
        if bracket:
            row_lines.append(
                f"出生落于 {bracket[0].get('jieqi')}（{bracket[0].get('time')}）与 "
                f"{bracket[1].get('jieqi')}（{bracket[1].get('time')}）之间"
            )
        snapshot_text = _render_snapshot_text([
            ("起盘信息", "\n".join(info_lines)),
            ("出生节气窗", "\n".join(row_lines)),
        ])
        return {
            "jieqi": rows,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="jieqi_birth", snapshot_text=snapshot_text),
        }

    # ── 八字（F9）──────────────────────────────────────────────────────────────────────────────
    # 上游八字页主路径是**本地** lunar.js 引擎：BaZi.js:716-755 fetchBaziCached（bazi_direct 同形 :757-795）
    # `buildLocalBaziResult(params)` 成功即用，抛错（lunar-js 不可靠域：公元前 / 万年后 / 不可解析日期）才回退
    # Java /bazi/birth；两条路都经 normalizeBaziResult → buildBaziSnapshotText（BaZi.js:1000-1046）。
    # v0.40 前本仓整盘走 Java：godKeyPos 缺省「年日」（页面「年」，techniqueMountSettings.js:1699）、命宫缺省
    # 子平数法（页面通行版，:1705）、晚子时 (1,0) 档 Java /bazi/birth 直接 500（timegan.error，live 实测），
    # 快照是 Python 手写 port（缺纳音长生列 / 命宫起法标注 / 起运行 / 小运年龄口径 / 三维分列）。
    # 现与页面同源：本地引擎 + vendored builder（vendor/bazi/baziSnapshot.js，逐字抽自 BaZi.js）。
    _BAZI_OPTION_VOCAB: dict[str, tuple[Any, ...]] = {
        # 取值表逐条对照 techniqueMountSettings.js:1692-1740（八字挂载设置）；缺省 = BaZi.js:961-985 genParams。
        # timeAlg 2（春分定卯时）上游置灰「尚无独立换算」（CnTraditionInput.js:517），不收。
        "godKeyPos": ("年", "日", "年日"),
        "phaseType": (0, 1, 2),
        "timeAlg": (0, 1, 3),
        "minggongMethod": ("tongxing", "shufa"),
        "fenyeVersion": ("common", "fajue"),
        "cangVersion": ("common", "fenye"),
        "dayunPrecision": ("precise", "integer"),
        "school": ("zonghe", "fuyi", "geju", "tiaohou", "bingyao", "tongguan", "mangpai", "nayin"),
        "ageStyle": ("nominal", "real"),
        "zodiacBoundary": ("lichun", "lunar"),
        # v3.11.2：南半球月令（BaZi.js:1031 genParams 缺省 'none'；baziLunarLocal.js flipMonthPillar 只在 isSouthLatitude 时生效；
        # Java /bazi/birth /bazi/direct 读同名参数 southMonth=chong|none 进缓存键）。
        "southMonth": ("none", "chong"),
    }
    _BAZI_OPTION_DEFAULTS: dict[str, Any] = {
        "godKeyPos": "年", "phaseType": 0, "timeAlg": 0, "minggongMethod": "tongxing",
        "fenyeVersion": "common", "cangVersion": "common", "dayunPrecision": "precise", "southMonth": "none",
    }

    def _bazi_option(self, payload: dict[str, Any], key: str) -> Any:
        """取一个八字口径键：缺省 → 上游缺省；认不出 → 按缺省出并进 warnings（同 zodiacBoundary 先例，不静默吞）。"""
        raw = payload.get(key)
        if raw is None or f"{raw}" == "":
            return self._BAZI_OPTION_DEFAULTS.get(key)
        vocab = self._BAZI_OPTION_VOCAB[key]
        value = int(raw) if isinstance(vocab[0], int) and f"{raw}".lstrip("-").isdigit() else raw
        if value in vocab:
            return value
        if key == "timeAlg":
            raise ToolValidationError(
                f"八字 timeAlg={raw!r} 不受支持 / unsupported bazi timeAlg {raw!r}: 0=真太阳时 1=直接时间 3=平太阳时"
                "（2 春分定卯时上游尚未实现）",
                code="tool.bazi_timealg_unsupported",
                details={"field": "timeAlg", "value": raw, "valid": list(vocab)},
            )
        fallback = self._BAZI_OPTION_DEFAULTS.get(key)
        _degrade(
            "bazi %s %r unrecognised", key, raw,
            note=f"八字 {key}={raw!r} 无法识别（可选 {' / '.join(str(v) for v in vocab)}），已按缺省"
                 f"{f' {fallback}' if fallback is not None else ''}起盘。",
        )
        return fallback

    def _bazi_params(self, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        """上游 genParams（BaZi.js:961-985）同形同序的起盘参数 + 只进快照的附加项（:1029 snapshotParams / 挂载 period）。"""
        gender = payload.get("gender")
        # 性别缺省 = 上游「未知(按男排)」档 -1（CnTraditionInput.js:506-509）：引擎按男排、快照印「性别：未知」。
        gender = 1 if gender in (1, True, "1") else (0 if gender in (0, False, "0") else -1)

        def bit(value: Any) -> int:
            return 0 if value in (0, False, "0", "false", "False") else 1

        # 公元前：上游 DateTime.format('YYYY-MM-DD') 出带负号的年（'-0100-05-15'，dateStrSafe.js 头注），本地引擎按带符号
        # 年判可靠域（lunarDomainGuard：AD1–9999）→ 域外抛错走 Java。本仓约定是正号日期 + ad=-1，照上游补负号
        # （Java BaZiBirthController.java:110-114 自己也补，已带负号不重复）；不补则公元前 100 年被当成公元 100 年本地起盘。
        date = f"{payload.get('date') or ''}"
        if payload.get("ad") in (-1, "-1") and date and not date.startswith("-"):
            date = f"-{date}"
        params = {
            "date": date,
            "time": payload.get("time"),
            "ad": payload.get("ad", 1),
            "zone": payload.get("zone"),
            "lon": payload.get("lon"),
            "lat": payload.get("lat"),
            "gpsLat": payload.get("gpsLat"),
            "gpsLon": payload.get("gpsLon"),
            "gender": gender,
            "timeAlg": self._bazi_option(payload, "timeAlg"),
            "phaseType": self._bazi_option(payload, "phaseType"),
            "godKeyPos": self._bazi_option(payload, "godKeyPos"),
            # 日界/晚子时：缺省 = 上游出厂缺省 1/1（dayBoundary.js:39-45 / :91-93）；本地引擎缺键 = 不进位，必须显式补。
            "after23NewDay": 1 if payload.get("after23NewDay") is None else bit(payload.get("after23NewDay")),
            "lateZiHourUseNextDay": 1 if payload.get("lateZiHourUseNextDay") is None else bit(payload.get("lateZiHourUseNextDay")),
            # v3.13.0 BAZI_ADJUST_JIEQI_SENT（baziLunarLocal.js:1236-1238 / BaZi.js:1066-1069）：恒发 0 —— 本地引擎不实现、
            # 控件已隐藏，旧记录带来的 1 也不再下发（否则回退 Java 的域会真把节气平移 (|lat|−35)×2 天，同一记录两域口径不一）。
            "adjustJieqi": 0,
            "minggongMethod": self._bazi_option(payload, "minggongMethod"),
            "fenyeVersion": self._bazi_option(payload, "fenyeVersion"),
            "cangVersion": self._bazi_option(payload, "cangVersion"),
            "dayunPrecision": self._bazi_option(payload, "dayunPrecision"),
            # v3.11.2 南半球月令：进 params（本地引擎核心缓存键含它；Java 回退时随 java_payload 一起发）。
            "southMonth": self._bazi_option(payload, "southMonth"),
        }
        snapshot: dict[str, Any] = {}
        for key in ("school", "ageStyle", "zodiacBoundary"):
            if payload.get(key) not in (None, ""):
                value = self._bazi_option(payload, key)
                if value is not None:
                    snapshot[key] = value
        if isinstance(payload.get("period"), dict):
            snapshot["period"] = payload["period"]
        return params, snapshot

    def _run_bazi_tool(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        params, snapshot = self._bazi_params(payload)
        endpoint = "/bazi/direct" if tool_name == "bazi_direct" else "/bazi/birth"
        # byLon：本地引擎不实现，给了真值只有 Java 算得出 → 整盘走 Java 并如实告知（命宫起法随之标「子平数法(本域回退)」）。
        # adjustJieqi：v3.13.0 起上游恒发 0（见 _bazi_params），不再因它改走 Java；调用方显式要了 → 说清本次未调整。
        if payload.get("adjustJieqi") in (1, True, "1", "true"):
            _degrade(
                "bazi adjustJieqi requested but upstream always sends 0",
                note="八字 adjustJieqi（节气按纬度调整）：星阙 v3.13.0 起八字页、AI 无头重算与八字择日恒不调整节气"
                "（本地引擎未实现该算法、控件已隐藏），本盘按「不调整节气」起。",
            )
        java_only = [key for key in ("byLon",) if payload.get(key) in (1, True, "1", "true")]
        js: dict[str, Any] = {}
        reason = ""
        if not java_only:
            js = self.js_client.run("bazi_local", {"params": params, "snapshot": snapshot}) or {}
            data = js.get("data") if isinstance(js.get("data"), dict) else {}
            if data.get("ok") is False:
                if data.get("reason") != "local_engine_unavailable":
                    raise ToolTransportError(
                        f"八字本地引擎未出盘 / bazi local engine produced no chart: {data.get('message') or data.get('reason')}",
                        code="tool.bazi_local_failed",
                        details={"reason": data.get("reason"), "message": data.get("message")},
                    )
                reason = f"本地历法引擎不可用（{data.get('message') or '域外日期'}）"
        else:
            reason = f"{'/'.join(java_only)} 只有 Java 引擎实现（上游页面本地引擎不支持）"
        if reason:
            java_payload = {k: v for k, v in params.items() if v is not None and not (k == "gender" and v == -1)}
            if payload.get("byLon") in (1, True, "1", "true"):
                java_payload["byLon"] = True
            java_result = self._call_remote(endpoint, java_payload)
            js = self.js_client.run("bazi_local", {"params": params, "snapshot": snapshot, "java_result": java_result}) or {}
            _degrade(
                "bazi computed by Java %s: %s", endpoint, reason,
                note=f"八字由 Java {endpoint} 起盘（{reason}）：命宫起法按 Java 口径（快照命宫行已标注），"
                     "五行力量/格局·用神/盲派/分野等本地派生段不出（与上游回退路径同）。",
            )
        data = js.get("data") if isinstance(js.get("data"), dict) else {}
        text = f"{js.get('snapshot_text') or ''}".strip()
        if not data.get("ok") or not text:
            raise ToolTransportError(
                "八字快照未产出 / bazi snapshot was not produced.",
                code="tool.bazi_local_failed",
                details={"reason": data.get("reason"), "message": data.get("message"), "java_fallback": bool(reason)},
            )
        local = bool(data.get("local"))
        return {
            "bazi": data.get("bazi"),
            "gender": data.get("gender"),
            "local": local,
            "compute_sources": {"bazi": "lunar-local" if local else "java"},
            "snapshot_text": text,
            "export_snapshot": self._augment_export_payload(technique="bazi", snapshot_text=text),
        }

    # ── 紫微（F8）──────────────────────────────────────────────────────────────────────────────
    # 上游 AI 无头复算 buildZiweiSnapshotForParams（ZiWeiMain.js:716-822）：Java /ziwei/birth 起盘，四化流派非通用
    # 时附 sihua 表（后端格局随流派）；22 个传本/排盘开关任一非缺省 → 本地 ZiweiCalc 重排盘核心 + 重算格局
    # （Java 不支持大限跨度/天马/星集/三盘…）；快照 = vendored buildZiWeiSnapshotText（[起盘信息] 四化流派/传本设置行、
    # [宫位总览] 四化括注与庙旺档）。编排在 tools/ziweiBirth.js（单例覆盖/还原同上游），JS 不发 HTTP → 两段式。
    # v0.40 前：sihuaSchool/传本键 Java 一概不读、Python 快照是手写 port —— 这些键全是死开关。
    _ZIWEI_OPTION_KEYS: tuple[str, ...] = (
        # 上游 ZW_ENGINE_SWITCH_KEYS（ZiWeiMain.js:752-754）+ 挂载键 ziweiXiaoxianYinyang（aiAnalysisContext.js:1904）
        "daxianSpan", "tianmaBasis", "starSet", "sanPan", "shangShi", "leapMonth", "lateZi", "yearBoundary", "huoling",
        "kongNaming", "brightnessSource", "lifeMasterBy", "liuYueBasis", "liunianSihuaGan", "changshengStart",
        "changshengDirection", "kuiYue", "kongwangStyle", "flowLuanXi", "flowHuoLing", "flowShenshaOnChart", "childLimit",
        "zhongxian", "huoPan", "qishuWei", "borrowPalace", "taiSuiRuGua", "taiSuiRelatives", "xiaoxianMode",
        "ziweiXiaoxianYinyang", "sihuaSchool", "sihuaCustomTable", "brightnessCustomTable",
    )

    def _ziwei_params(self, payload: dict[str, Any]) -> dict[str, Any]:
        """上游 buildChartZiweiParams（aiAnalysisContext.js:1879-1944）同形：起盘字段 + 显式给了的流派/传本键 + period。"""
        gender = payload.get("gender")
        gender = 1 if gender in (1, True, "1") else (0 if gender in (0, False, "0") else None)

        def bit(value: Any) -> int:
            return 0 if value in (0, False, "0", "false", "False") else 1

        params: dict[str, Any] = {
            "date": payload.get("date"),
            "time": payload.get("time"),
            "zone": payload.get("zone"),
            "lon": payload.get("lon"),
            "lat": payload.get("lat"),
            "gpsLat": payload.get("gpsLat"),
            "gpsLon": payload.get("gpsLon"),
            "gender": gender,
            "timeAlg": 1 if payload.get("timeAlg") in (1, "1") else 0,   # 紫微页只两档（:1890）
            # 本地引擎档要已解析的日界缺省（calcZiwei 'global' 分支直读，缺键 = 不进位）：上游出厂缺省 1/1。
            "after23NewDay": 1 if payload.get("after23NewDay") is None else bit(payload.get("after23NewDay")),
            "lateZiHourUseNextDay": 1 if payload.get("lateZiHourUseNextDay") is None else bit(payload.get("lateZiHourUseNextDay")),
        }
        # 旧入参 schools {childLimit, zhongxian, …} 仍收：与上游平铺键同义，平铺键优先。
        schools = payload.get("schools") if isinstance(payload.get("schools"), dict) else {}
        for key in self._ZIWEI_OPTION_KEYS:
            value = payload.get(key)
            if value is None:
                value = schools.get(key)
            if value is not None:
                params[key] = value
        # 旧入参 sihua（原样四化表）≡ 上游 custom 档随盘自定义表（sihuaCustomTable，techniqueMountSettings.js:1760-1763）。
        if isinstance(payload.get("sihua"), dict) and "sihuaSchool" not in params:
            params["sihuaSchool"] = "custom"
            params["sihuaCustomTable"] = payload["sihua"]
        if isinstance(payload.get("period"), dict):
            params["period"] = payload["period"]
        return params

    def _ziwei_warn(self, items: Any) -> None:
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            valid = item.get("valid") if isinstance(item.get("valid"), list) else []
            _degrade(
                "ziwei option %s=%r unrecognised", item.get("key"), item.get("value"),
                note=f"紫微 {item.get('key')}={item.get('value')!r} 无法识别（可选 {' / '.join(str(v) for v in valid)}），"
                     "该项按缺省排盘。",
            )

    def _run_ziwei_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        params = self._ziwei_params(payload)
        java_payload: dict[str, Any] = {
            key: params[key] for key in ("date", "time", "zone", "lat", "lon", "gpsLat", "gpsLon", "timeAlg")
            if params.get(key) is not None
        }
        java_payload["ad"] = payload.get("ad", 1)
        if params.get("gender") is not None:
            java_payload["gender"] = params["gender"]
        # 日界/晚子时：只发显式给定的（缺省 → Java 缺省 1/1 = 上游出厂缺省；ZiWeiController.java:87-90）。
        java_payload.update(_day_boundary_switches(payload))
        school = f"{params.get('sihuaSchool') or ''}".strip()
        prep_warnings: list[Any] = []
        if school and school != "beipai":
            prep = self.js_client.run("ziwei_birth", {"action": "prepare", "params": params}) or {}
            prep_data = prep.get("data") if isinstance(prep.get("data"), dict) else {}
            if isinstance(prep_data.get("sihua"), dict):
                java_payload["sihua"] = prep_data["sihua"]
            prep_warnings = prep.get("warnings") or []
        java_result = self._call_remote("/ziwei/birth", java_payload)
        fin = self.js_client.run("ziwei_birth", {"action": "finalize", "params": params, "result": java_result}) or {}
        data = fin.get("data") if isinstance(fin.get("data"), dict) else {}
        self._ziwei_warn(fin.get("warnings") or prep_warnings)
        text = f"{fin.get('text') or ''}".strip()
        if not data.get("ok") or not text:
            raise ToolTransportError(
                "紫微快照未产出 / ziwei snapshot was not produced.",
                code="tool.ziwei_snapshot_failed",
                details={"reason": data.get("reason")},
            )
        if data.get("localEngine") and not data.get("localApplied"):
            _degrade(
                "ziwei local engine failed, Java chart kept: %s", data.get("localError"),
                note=f"紫微传本开关需本地引擎重排，但本地引擎失败（{data.get('localError') or '未产出12宫'}），"
                     "已保留 Java 盘（上游同）——盘面未按所选传本设置变化。",
            )
        return {
            "chart": data.get("chart"),
            "patterns": data.get("patterns"),
            "compute_sources": {"chart": "ZiweiCalc" if data.get("localApplied") else "java"},
            "snapshot_text": text,
            "export_snapshot": self._augment_export_payload(technique="ziwei", snapshot_text=text),
        }

    def _run_tongshefa_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        js_result = self.js_client.run("tongshefa", payload)
        snapshot_text = js_result.get("snapshot_text")
        return {
            "tongshefa": js_result.get("data", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="tongshefa", snapshot_text=snapshot_text),
        }

    def _run_canping_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # canping is computed entirely in-process by horosa-core-js (bazi chain → 金锁银匙 起数),
        # not the ken backend. The JS returns the canping model + the 星阙-identical snapshot text.
        js_result = self.js_client.run("canping", payload)
        snapshot_text = js_result.get("snapshot_text")
        return {
            "canping": js_result.get("data", {}),
            "input_normalized": js_result.get("input_normalized", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="canping", snapshot_text=snapshot_text),
        }

    def _run_heluo_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # heluo (河洛理数) is also a 原生·非 ken tool: the JS computes the chart (起命/先天/后天), 大限/
        # 岁运, and 命运篇 judge in-process and returns the 星阙-identical snapshot text.
        js_result = self.js_client.run("heluo", payload)
        snapshot_text = js_result.get("snapshot_text")
        return {
            "heluo": js_result.get("data", {}),
            "input_normalized": js_result.get("input_normalized", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="heluo", snapshot_text=snapshot_text),
        }

    def _run_bazi_inverse_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        """八字反查（Java /common/inversebazi）：四柱干支 → 候选公历出生时刻。

        上游契约（CommController.inverseBazi / BaZiHelper.getBirthes）：Year/Month/Date/Time 四柱干支，
        Count 条数，Desc=true 从 FromYear 向过去逐年回推；返回 Dates=["YYYY-MM-DD HH:mm:ss", …]。
        """
        pillars = payload.get("pillars")
        if not isinstance(pillars, list) or len(pillars) != 4:
            pillars = [payload.get("year"), payload.get("month"), payload.get("day"), payload.get("hour")]
        cleaned = [f"{item or ''}".strip() for item in pillars]
        bad = [item for item in cleaned if len(item) != 2 or item[0] not in _GANZHI_STEMS or item[1] not in _GANZHI_BRANCHES]
        if bad or len(cleaned) != 4:
            raise ToolValidationError(
                bilingual("八字反查需要四柱干支（年/月/日/时各一组，如 甲子）。", "bazi_inverse needs four ganzhi pillars (year/month/day/hour, e.g. 甲子)."),
                code="tool.bazi_inverse_invalid_pillars",
                details={"pillars": cleaned, "invalid": bad, "hint": "pillars=['甲子','丙寅','戊辰','庚申'] 或 year/month/day/hour 四键"},
            )
        count = payload.get("count")
        try:
            count = max(1, min(10, int(count if count is not None else 3)))
        except (TypeError, ValueError):
            count = 3
        desc = payload.get("desc")
        desc = True if desc is None else bool(desc)
        remote_payload: dict[str, Any] = {
            "Year": cleaned[0], "Month": cleaned[1], "Date": cleaned[2], "Time": cleaned[3],
            "Count": count, "Desc": desc,
        }
        from_year = payload.get("fromYear")
        if from_year is not None:
            remote_payload["FromYear"] = int(from_year)
        response = self._call_remote("/common/inversebazi", remote_payload)
        dates = response.get("Dates") if isinstance(response, dict) else None
        candidates = []
        for item in dates or []:
            text = f"{item}".strip()
            if not text:
                continue
            date_part, _, time_part = text.partition(" ")
            candidates.append({"datetime": text, "date": date_part.replace("/", "-"), "time": time_part or None})
        condition_lines = [
            f"四柱：{' '.join(cleaned)}",
            f"回推方向：{'向过去' if desc else '向未来'}；起始年：{from_year if from_year is not None else '后端当前年'}；数量：{count}",
        ]
        candidate_lines = [f"{index}. {c['datetime']}" for index, c in enumerate(candidates, start=1)]
        snapshot_text = _render_snapshot_text([
            ("反查条件", "\n".join(condition_lines)),
            ("候选时刻", "\n".join(candidate_lines) if candidate_lines else "无（该四柱在起始年前后未找到匹配时刻）"),
            ("口径说明", "候选由后端按四柱干支自起始年起逐年匹配（BaZiHelper.getBirthes）；同一四柱约每 60 年重现；时刻取该时辰的代表时间，实际排盘请以候选时刻附近的真实钟表时间与地点重新起盘。"),
        ])
        return {
            "bazi_inverse": {"pillars": cleaned, "count": count, "desc": desc, "fromYear": from_year, "candidates": candidates},
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="bazi_inverse", snapshot_text=snapshot_text),
        }

    def _run_yizhangjing_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 一掌经：原生·非 ken 工具，JS 进程内完成 农历解析→四柱四宫→命宫/人事十二宫→格局/重犯/
        # 大限/小限流年十二神（+可选神煞合参层），返回引擎自产快照（段头已转 [段名]）。
        js_result = self.js_client.run("yizhangjing", payload)
        snapshot_text = js_result.get("snapshot_text")
        return {
            "yizhangjing": js_result.get("data", {}),
            "input_normalized": js_result.get("input_normalized", {}),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="yizhangjing", snapshot_text=snapshot_text),
        }

    def _run_huangli_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 老黄历日课：上游这支是纯前端本地推演（lunar-javascript + 择日表），**零后端往返**，
        # 所以这里没有任何 _call_remote —— 与 canping/heluo 一类的 execution="local" 同款。
        year, month, day = self._split_ymd(payload.get("date"), tool="huangli")
        hour = payload.get("hour")
        js = self.js_client.run(
            "huangli",
            {"year": year, "month": month, "day": day, "hour": hour if hour is not None else 12},
        )
        snapshot_text = f"{(js or {}).get('text') or ''}".strip()
        return {
            "date": payload.get("date"),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="huangli", snapshot_text=snapshot_text),
        }

    # 通书流派键的唯一真值是引擎词表（vendored tongshuSchools.js TONGSHU_SCHOOLS：donggong / qimen /
    # sanyuanliexiu=三垣列宿 / wutu / sanyuan=三元玄空大卦），JS 侧核验、认不出回 unknown_school。
    # 唯一别名 xuankong：v0.40 前本仓 schema/guidance 把玄空写成 xuankong、把 sanyuan 写成三垣（与引擎相反），
    # 照旧文档传 xuankong 的调用方拿到的是「（该流派待实现）」——按引擎键 sanyuan 起并在 warnings 说明。
    _TONGSHU_SCHOOL_ALIASES = {"xuankong": "sanyuan"}

    def _tongshu_school(self, school: Any) -> Any:
        key = f"{school or ''}".strip()
        target = self._TONGSHU_SCHOOL_ALIASES.get(key)
        if target is None:
            return school
        _degrade(
            "tongshu school alias %s -> %s", key, target,
            note=f"通书流派 {key!r} 是旧文档写法，已按引擎键 {target!r}（三元玄空大卦）起盘；三垣列宿的引擎键是 'sanyuanliexiu'。",
        )
        return target

    @staticmethod
    def _raise_tongshu_unknown_school(bad: dict[str, Any], *, field: str) -> None:
        valid = bad.get("valid") if isinstance(bad.get("valid"), list) else []
        raise ToolValidationError(
            f"通书流派 {bad.get('school')!r} 不在引擎词表内 / unknown tongshu school "
            f"{bad.get('school')!r}; valid keys: {', '.join(str(v.get('key')) for v in valid if isinstance(v, dict))}",
            code="tool.tongshu_unknown_school",
            details={"field": field, "school": bad.get("school"), "valid": valid},
        )

    def _run_tongshu_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 通书择日：同样纯本地。school 是结果敏感项（五流派断语可以完全相反），由闸门在调用前问清；
        # 这里只做透传，不替用户挑。
        self._split_ymd(payload.get("date"), tool="tongshu")  # 仅校验格式，JS 侧吃 'YYYY-MM-DD' 原串
        school = self._tongshu_school(payload.get("school"))
        js = self.js_client.run(
            "tongshu",
            {
                "date": f"{payload.get('date') or ''}".replace("/", "-"),
                # zuoShan 不在此列：上游 techniqueMountSettings.js:1938 已把它删掉并记明理由
                # ——「双重幽灵：无任何流派声明 needs.zuoShan，快照 builder 全文不消费，齿轮选它
                # 100% 无效果」。继续转发只会白白打散下游 memo 缓存。
                **{k: payload.get(k) for k in ("event", "liexiuUse", "mingYear") if payload.get(k)},
                **({"school": school} if school else {}),
            },
        )
        js_data = (js or {}).get("data") if isinstance(js, dict) else None
        if isinstance(js_data, dict) and js_data.get("ok") is False and js_data.get("reason") == "unknown_school":
            self._raise_tongshu_unknown_school(js_data, field="school")
        snapshot_text = f"{(js or {}).get('text') or ''}".strip()
        return {
            "date": payload.get("date"),
            "school": school,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="tongshu", snapshot_text=snapshot_text),
        }
