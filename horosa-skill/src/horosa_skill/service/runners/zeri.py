"""择日 runner（ZeriRunners）：天星择日、七政择日、奇门择日与其余七个择日扫描（本地 / 后端）。"""
from __future__ import annotations

import re
from typing import Any

from horosa_skill.errors import (
    HorosaSkillError,
    ToolTransportError,
    ToolValidationError,
    bilingual,
)
from horosa_skill.service._context import _degrade, _progress_tick
from horosa_skill.service.options_cn import _qimen_effective_options
from horosa_skill.service.options_zeri import (
    _QIMENZERI_MAX_SPAN_DAYS,
    _TIANXING_MAX_SPAN_DAYS,
    _clamped_max_span,
    _electionscan_options,
    _electionscan_zone,
    _require_sane_window,
    _zeri_explain_rows,
    _zeri_snapshot_row_opts,
)


class ZeriRunners:
    @staticmethod
    def _tianxing_window(payload: dict[str, Any]) -> tuple[str, str, str, str]:
        start_date = str(payload.get("startDate") or payload.get("date") or "")
        end_date = str(payload.get("endDate") or start_date)
        return start_date, str(payload.get("startTime") or "00:00"), end_date, str(payload.get("endTime") or "23:59")

    def _tianxing_js(self, request: dict[str, Any], *, stage: str) -> dict[str, Any]:
        """跑 tianxing 的 JS 侧动作并**检查 data.ok**。

        🔴 tianxing.js 在 buildTianxingSnapshot 抛异常时返回 {data:{ok:false,…}, snapshot_text:''}。
        旧实现只读 snapshot_text → 拿到 None → _augment_export_payload 回落
        `format_source: "generated_template"`，产出一份拿 payload YAML 填出来的**伪造四段导出**，
        而 SKILL.md 要求 agent 只依据 export_snapshot.export_text 解读。stitch 那侧的 `or []`
        同理会把失败变成「零命中」——一个看起来完全合理的空结果。
        """
        result = self.js_client.run("tianxing", request)
        data = result.get("data") or {}
        if not data.get("ok"):
            error = data.get("error") or {}
            raise ToolTransportError(
                f"天星择日 JS 层 {stage} 失败：{error.get('message') or '未知错误'}",
                code=f"tool.tianxing_{error.get('code') or f'{stage}_failed'}",
                details={"stage": stage, "error": error},
            )
        return {**data, "snapshot_text": result.get("snapshot_text")}

    def _run_tianxing_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        start_date, start_time, end_date, end_time = self._tianxing_window(payload)
        if not start_date or not end_date:
            raise ToolValidationError(
                "天星择日需要搜索时间窗（startDate/endDate）。",
                code="tool.tianxing_missing_window",
                details={"startDate": start_date, "endDate": end_date},
            )
        conditions = payload.get("conditions")
        if not conditions:
            raise ToolValidationError(
                "天星择日需要征象条件树（conditions）。",
                code="tool.tianxing_missing_conditions",
                details={"hint": "条件类键与参数见本工具的 agent_guidance。"},
            )
        # Compile through the vendored table so validation messages come from the same source the
        # backend uses — never re-encode 32 condition schemas here (they go stale on every upstream add).
        compiled_result = self.js_client.run("tianxing", {"action": "compile", "tree": conditions})
        compiled_data = compiled_result.get("data") or {}
        if not compiled_data.get("ok"):
            error = compiled_data.get("error") or {}
            details: dict[str, Any] = {"error": error}
            # 自愈式报错：把**服务端实现集**（运行时孪生）一并带回，agent 不用猜哪些条件类键合法。
            # _call_remote 已剥 {ResultCode, Result} 信封 → 这里拿到的就是 {types, groups}。
            try:
                ct = self._call_remote("/electionscan/conditiontypes", {})
                if isinstance(ct, dict) and isinstance(ct.get("types"), list):
                    details["server_condition_types"] = ct.get("types")
            except Exception:  # noqa: BLE001 - 自省失败不该遮住原始校验错误
                pass
            raise ToolValidationError(
                f"征象条件树不合法：{error.get('message') or '未知错误'}",
                code="tool.tianxing_invalid_conditions",
                details=details,
            )
        compiled = compiled_data.get("compiled")

        # 窗口上限。每一段都是一次串行后端扫描，5 年窗口 = 60 次；而 splitByMonth 的 800 次 guard 一旦
        # 耗尽（约 66 年）会**不 push 最后一段**就退出——尾部被丢，结果却仍报成对整个窗口的完整搜索。
        # 绝不静默截断（AGENTS §5.9）。
        max_span = _clamped_max_span(payload, _TIANXING_MAX_SPAN_DAYS)
        _require_sane_window(start_date, end_date, max_span=max_span, tool="tianxing")

        cfg = {"startDate": start_date, "startTime": start_time, "endDate": end_date, "endTime": end_time}
        # The backend hard-caps ONE request at 93 days (election_scan.py MAX_SPAN_DAYS); upstream works
        # around it by month-splitting in the UI. §5「请求型 builder 一律归 Python」→ the loop lives here,
        # but the split/stitch arithmetic stays the vendored one so boundaries match 星阙 byte-for-byte.
        segments = self._tianxing_js(
            {"action": "split", "cfg": cfg}, stage="split"
        ).get("segments") or [cfg]
        base = {
            "zone": _electionscan_zone(payload.get("zone")),
            "ad": payload.get("ad", 1),
            "gpsLat": payload.get("gpsLat"),
            "gpsLon": payload.get("gpsLon"),
            "lat": payload.get("lat"),
            "lon": payload.get("lon"),
            "hsys": payload.get("hsys"),
            "zodiacal": payload.get("zodiacal"),
            # 恒星黄道口径：ScanContext 会读它，缺失就回落 Lahiri —— 而 [起盘信息] 段照样把用户给的值
            # 印出来，等于输出主动声称了一个没被使用的设置。
            "siderealAyanamsa": payload.get("siderealAyanamsa"),
            # schema 声明了 precision，之前全代码没人消费它（后端 election_scan.py:1994 恒取默认
            # 'minute'）。文档化了却什么都不做的旋钮比没有更糟——接上。
            "precision": payload.get("precision"),
            "conditions": compiled,
            # protocol salt: invalidates cached rows predating the pick/pickEnd fields (scanOrchestrator.js)
            "_v": 2,
        }
        # 古典口径既可走 `options` 字典，也可走 BirthInput 继承来的**顶层**同名字段（schema 里逐个带
        # 描述，agent 照着传是完全正确的用法）。此前只读 options → 顶层写法被静默丢弃、搜索结果不同
        # 却无任何报错。两处都收，options 优先。
        base.update(_electionscan_options(payload))
        base.update(_electionscan_options(payload.get("options")))

        lists: list[list[dict[str, Any]]] = []
        truncated = False
        eval_points = 0
        total_segments = len(segments)
        for index, segment in enumerate(segments, start=1):
            _progress_tick(index - 1, total_segments, f"天星择时：扫描第 {index}/{total_segments} 段")
            raw = self._call_remote("/electionscan/scan", {**base, **segment})
            data = self._require_electionscan_ok(raw, endpoint="/electionscan/scan")
            lists.append(list(data.get("intervals") or []))
            truncated = truncated or bool(data.get("truncated"))
            eval_points += int(((data.get("stats") or {}).get("evalPoints")) or 0)
        _progress_tick(total_segments, total_segments, "天星择时：缝合区间")
        stitched = self._tianxing_js({"action": "stitch", "lists": lists}, stage="stitch")
        intervals = stitched.get("intervals") or []

        fields = {
            "date": {"value": payload.get("date") or start_date},
            "time": {"value": payload.get("time") or start_time},
            "pos": {"value": payload.get("pos")},
            "lon": {"value": payload.get("lon")},
            "lat": {"value": payload.get("lat")},
            "zone": {"value": payload.get("zone")},
            "zodiacal": {"value": payload.get("zodiacal")},
            "siderealAyanamsa": {"value": payload.get("siderealAyanamsa")},
        }
        ctx = {
            # the snapshot renders the **UI** tree (chain joiners), not the compiled one
            # 🔴 zodiacal / siderealAyanamsa 必须进 cfg：快照的 [征象搜索配置] 段读 cfg.zodiacal
            # 决定打「回归黄道」还是「恒星黄道(ayanamsa)」（tianxingSnapshot.js:76）。此前没送 →
            # 恒星盘搜索也恒打「回归黄道」，而同一份输出里 [起盘信息] 的「黄道：」行读的是 fields
            # （已正确填充）→ 一份交付物里两行自相矛盾，且声称的口径不是真正跑的那个。
            # gpsLon/gpsLat 同理：pos 缺省时「搜索地点」行读它们（:74），不送就渲染成空。
            "cfg": {
                **cfg,
                "hsys": payload.get("hsys"),
                "pos": payload.get("pos"),
                # zone 不放这里：tianxingSnapshot.js 全文只读 startDate/startTime/endDate/endTime/
                # pos/gpsLon/gpsLat/hsys/zodiacal/siderealAyanamsa 十键，cfg.zone 无人消费。
                "zodiacal": payload.get("zodiacal"),
                "siderealAyanamsa": payload.get("siderealAyanamsa"),
                "gpsLon": payload.get("gpsLon"),
                "gpsLat": payload.get("gpsLat"),
            },
            "tree": conditions,
            "results": intervals,
            "truncated": truncated,
        }
        # [Q-453] 命中清单前 N 行附判读树：判读是服务端的，上游宿主扫描后预取（prefetchSnapshotExplains），
        # builder 经 ctx.explainAt 按行序读缓存。函数过不了 JSON 边界 → 预取结果按行序交 JS，由 JS 装 explainAt。
        explains = self._zeri_prefetch_explains("/electionscan/explain", base, intervals, payload, "天星择日")
        js_result = self._tianxing_js(
            {"action": "snapshot", "chart": payload.get("chart"), "fields": fields, "ctx": ctx,
             "explains": explains, **_zeri_snapshot_row_opts(payload)},
            stage="snapshot",
        )
        raw_snapshot = js_result.get("snapshot_text")
        snapshot_text = raw_snapshot if isinstance(raw_snapshot, str) and raw_snapshot.strip() else None
        # [选中时刻星盘]（v3.9.2）：命中时刻的整张判读底盘。上游在 UI 里把选中命中的 chart 喂
        # buildAstroSnapshotContent(headerless)——headless 侧同语义：取首个命中的 pick 时刻补铸
        # /chart（走完整 chart 工具管线，享受同一套段构建），再把子段头 `[X]` 转 `· X` 并入本段
        # （上游 headerless 正则逐字同款，防子段被顶层拆走）。无命中/铸盘失败不产段（条件段，零回归）。
        if snapshot_text and intervals:
            moment_section = self._tianxing_selected_moment_section(payload, intervals[0])
            if moment_section:
                snapshot_text = f"{snapshot_text}\n\n{moment_section}"
        # [单时判读]（v0.33.0）：explainAt 时刻的逐叶判读，与扫描求值器绝对同源（/electionscan/explain
        # pass 复用微域自证）。条件段：未给 explainAt 不产段，零回归。
        explain_tree: dict[str, Any] | None = None
        explained_at: str | None = None
        if payload.get("explainAt"):
            explained_at, explain_tree, explain_section = self._tianxing_explain(payload, base, conditions)
            if snapshot_text and explain_section:
                snapshot_text = f"{snapshot_text}\n\n{explain_section}"
        result_payload = {
            "intervals": intervals,
            "hit_count": len(intervals),
            "truncated": truncated,
            "stats": {"evalPoints": eval_points, "segments": len(segments)},
            "compiled_conditions": compiled,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="tianxing", snapshot_text=snapshot_text),
        }
        if explain_tree is not None:
            result_payload["explain"] = {"t": explained_at, "tree": explain_tree}
        return result_payload

    def _tianxing_explain(
        self, payload: dict[str, Any], base: dict[str, Any], ui_tree: Any
    ) -> tuple[str, dict[str, Any] | None, str]:
        """/electionscan/explain 往返 + [单时判读] 段文本（JS 侧同源语汇渲染）。

        t 归一照上游 explainInterval（TianxingElectionMain.js:346）：'-'→'/'，缺秒补 ':00'。
        """
        t_raw = str(payload.get("explainAt") or "").strip().replace("-", "/")
        if len(t_raw) == 16:  # YYYY/MM/DD HH:mm
            t_raw = f"{t_raw}:00"
        raw = self._call_remote("/electionscan/explain", {**base, "t": t_raw})
        data = self._require_electionscan_ok(raw, endpoint="/electionscan/explain")
        tree = data.get("tree") if isinstance(data, dict) else None
        js = self._tianxing_js(
            {"action": "explain_section", "t": data.get("t") or t_raw, "tree": ui_tree, "explain": tree},
            stage="explain_section",
        )
        section = js.get("snapshot_text")
        return t_raw, (tree if isinstance(tree, dict) else None), (section if isinstance(section, str) else "")

    def _qizhengelection_snapshot(self, kind: str, fields: dict[str, Any], data: dict[str, Any], options: dict[str, Any]) -> str:
        result = self.js_client.run(
            "qizhengelection", {"kind": kind, "fields": fields, "data": data, "options": options}
        )
        js_data = result.get("data") or {}
        if not js_data.get("ok"):
            error = js_data.get("error") or {}
            raise ToolTransportError(
                f"七政择日快照渲染失败：{error.get('message') or '未知错误'}",
                code=f"tool.qizhengelection_{error.get('code') or 'snapshot_failed'}",
                details={"error": error},
            )
        text = result.get("snapshot_text")
        return text if isinstance(text, str) else ""

    def _run_qizheng_election_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        action = str(payload.get("action") or "pan").strip().lower()
        if action not in {"pan", "eclipses", "azimuthsearch"}:
            raise ToolValidationError(
                f"未知动作 {action}（可选：pan / eclipses / azimuthsearch）。",
                code="tool.qizhengelection_unknown_action",
                details={"action": action},
            )
        zone = payload.get("zone") or "+08:00"
        fields = {
            "date": payload.get("date"),
            "time": payload.get("time"),
            "zone": zone,
            "pos": payload.get("pos"),
            "lat": payload.get("lat"),
            "lon": payload.get("lon"),
        }
        options: dict[str, Any] = {
            "plate": payload.get("plate") or "di",
            "ziZheng": payload.get("ziZheng") or "true",
            "declination": payload.get("declination") or 0,
            "eleLifeMode": payload.get("eleLifeMode") or "sunrise",
        }
        if action == "pan":
            if payload.get("gpsLat") is None or payload.get("gpsLon") is None:
                raise ToolValidationError(
                    "七政择日动盘需要经纬度（lat/lon 或 gpsLat/gpsLon）。",
                    code="tool.qizhengelection_missing_geo",
                    details={"lat": payload.get("lat"), "lon": payload.get("lon")},
                )
            remote: dict[str, Any] = {
                "date": payload.get("date"),
                "time": payload.get("time") or "12:00:00",
                "zone": zone,
                "gpsLat": payload.get("gpsLat"),
                "gpsLon": payload.get("gpsLon"),
            }
            for key in ("height", "nodeType", "lilithType", "ayanamsaDeg", "eleLifeMode", "eleLifeCustomTime", "extraBodies"):
                if payload.get(key) is not None:
                    remote[key] = payload.get(key)
            data = self._require_qizhengelection_ok(
                self._call_remote("/qizhengelection/pan", remote), endpoint="/qizhengelection/pan", expect="dict"
            )
            snapshot_text = self._qizhengelection_snapshot("pan", fields, data, options)
            body: dict[str, Any] = {"pan": data}
        elif action == "eclipses":
            options["kind"] = "lunar" if str(payload.get("kind") or "").strip().lower() == "lunar" else "solar"
            remote = {"date": payload.get("date"), "zone": zone, "kind": options["kind"]}
            if payload.get("count") is not None:
                remote["count"] = payload.get("count")
            rows = self._require_qizhengelection_ok(
                self._call_remote("/qizhengelection/eclipses", remote), endpoint="/qizhengelection/eclipses", expect="list"
            )
            snapshot_text = self._qizhengelection_snapshot("eclipses", fields, {"rows": rows}, options)
            body = {"eclipses": rows}
        else:  # azimuthsearch
            if payload.get("targetAz") is None:
                raise ToolValidationError(
                    "方位搜索需要目标罗盘方位 targetAz（0-359.9，0=北顺时针）。",
                    code="tool.qizhengelection_missing_target",
                    details={},
                )
            if payload.get("gpsLat") is None or payload.get("gpsLon") is None:
                raise ToolValidationError(
                    "方位搜索需要经纬度（lat/lon 或 gpsLat/gpsLon）。",
                    code="tool.qizhengelection_missing_geo",
                    details={"lat": payload.get("lat"), "lon": payload.get("lon")},
                )
            options["body"] = str(payload.get("body") or "日")
            options["targetAz"] = payload.get("targetAz")
            options["days"] = payload.get("days") or 3
            remote = {
                "date": payload.get("date"),
                "time": payload.get("time") or "00:00:00",
                "zone": zone,
                "gpsLat": payload.get("gpsLat"),
                "gpsLon": payload.get("gpsLon"),
                "targetAz": payload.get("targetAz"),
                "days": options["days"],
                "body": options["body"],
            }
            rows = self._require_qizhengelection_ok(
                self._call_remote("/qizhengelection/azimuthsearch", remote), endpoint="/qizhengelection/azimuthsearch", expect="list"
            )
            snapshot_text = self._qizhengelection_snapshot("azimuthsearch", fields, {"rows": rows}, options)
            body = {"hits": rows}
        return {
            "action": action,
            **body,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="qizhengelection", snapshot_text=snapshot_text),
        }

    def _tianxing_selected_moment_section(self, payload: dict[str, Any], hit: dict[str, Any]) -> str:
        try:
            pick = f"{(hit or {}).get('pick') or (hit or {}).get('start') or ''}".strip()
            if not pick:
                return ""
            parts = pick.split(" ")
            moment_payload = {
                "date": parts[0],
                "time": (parts[1] if len(parts) > 1 else "12:00") + (":00" if len(parts) > 1 and parts[1].count(":") == 1 else ""),
                "zone": payload.get("zone"),
                "lat": payload.get("lat"),
                "lon": payload.get("lon"),
                "pos": payload.get("pos"),
                "hsys": payload.get("hsys"),
                "zodiacal": payload.get("zodiacal"),
                "siderealAyanamsa": payload.get("siderealAyanamsa"),
                # [Q-419/T-382][Q-268/T-254] 选中时刻盘与扫描同源构参（上游 previewChartParams 带全局古典口径 +
                # 'user' 档历元两键，TianxingElectionMain.js:393-395）：否则非缺省口径下命中判定与所见盘不同形。
                # 与扫描同一次双读合并（顶层 → options 覆盖）。
                **_electionscan_options(payload),
                **_electionscan_options(payload.get("options")),
                # 择时盘沿用调用方已确认的设置；这里是同一次请求的内部子盘，不再过闸。
                "agent_confirmed_settings": True,
                "clarification_notes": "tianxing selected-moment sub-chart (same confirmed settings)",
            }
            moment_payload = {k: v for k, v in moment_payload.items() if v is not None}
            chart_env = self.run_tool("chart", moment_payload, save_result=False)
            if not chart_env.ok:
                _degrade("tianxing [选中时刻星盘] sub-chart failed: %s", chart_env.error.code if chart_env.error else "unknown")
                return ""
            body = f"{chart_env.data.get('snapshot_text') or ''}".strip()
            if not body:
                return ""
            headerless = re.sub(r"^\[(.+?)\]$", r"· \1", body, flags=re.MULTILINE)
            return f"[选中时刻星盘]\n选中命中：{pick}\n{headerless}"
        except Exception as exc:  # noqa: BLE001 - 星盘正文失败不阻断搜索段（上游同款 try 包裹），但要让调用方知道少了这一段
            _degrade("tianxing [选中时刻星盘] sub-chart failed: %s", exc)
            return ""

    def _run_qimenzeri_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        start_date, start_time, end_date, end_time = self._tianxing_window(payload)
        if not start_date or not end_date:
            raise ToolValidationError(
                "奇门择日需要搜索时间窗（startDate/endDate）。",
                code="tool.qimenzeri_missing_window",
                details={"startDate": start_date, "endDate": end_date},
            )
        conditions = payload.get("conditions")
        if not conditions:
            raise ToolValidationError(
                "奇门择日需要择日条件树（conditions）。",
                code="tool.qimenzeri_missing_conditions",
                details={"hint": "条件类键与参数见本工具的 agent_guidance。"},
            )
        # Skill-side span guard, tighter than the engine's own 1830-day cap: the JS subprocess has a
        # 60s wall clock (config.js_engine_timeout_seconds) and the scan costs ~2s per month-window,
        # so the engine limit would blow the timeout ~30x over. Never silently truncate (§5.9).
        # 🔴 用 _require_sane_window，不要写 `span is not None and span > max` —— 后者正是
        # 当初为 tianxing 杀掉的形状：解析不出来（`'2026-08-05 10:00'`）就跳过上限、倒置窗
        # 拿负数恒 False 也溜过去，而 JS 侧 wallToMs 照样能解析，于是超长窗一路跑到超时。
        # 这把帮手写出来就是为了根治它，此处此前漏改。
        max_span = _clamped_max_span(payload, _QIMENZERI_MAX_SPAN_DAYS)
        _require_sane_window(
            start_date, end_date, max_span=max_span, tool="qimenzeri",
            # 奇门择日的上限成因与 tianxing 不同：JS 子进程有 60s 墙钟（js_engine_timeout_seconds），
            # 扫描约 2s/月窗，所以引擎自带的 1830 天上限会把超时撑爆约 30 倍。提示保留这条成因。
            span_hint="把窗口拆成多段分别搜索；maxSpanDays 只能调低。"
                      "本上限来自 JS 引擎墙钟（HOROSA_JS_ENGINE_TIMEOUT_SECONDS），不是可协商的礼貌建议。",
        )

        cfg = {"startDate": start_date, "startTime": start_time, "endDate": end_date, "endTime": end_time}
        geo = {
            "zone": payload.get("zone"),
            "gpsLon": payload.get("gpsLon"),
            "gpsLat": payload.get("gpsLat"),
            "lon": payload.get("lon"),
            "lat": payload.get("lat"),
            "pos": payload.get("pos"),
        }
        # 🔴 起局三开关（timeAlg / after23NewDay / lateZiHourUseNextDay）是 QimenInput 继承来的
        # **顶层**字段（schemas/tools/cn_divination.py 的 QimenInput，各带描述），agent 照 schema 传顶层是正确用法。
        # 扫描引擎只从 `options` 读（qimenScanEngine.js:124-126），此前顶层写法被静默丢弃 →
        # 命中区间用默认起局算、而同一次调用里的**展示盘**走 _run_qimen_tool 是honor 顶层的，
        # 于是两者不同局；[奇门择日配置] 段还会打出一个根本没用上的设置标签。
        # 与 tianxing 同款双读合并（见上方 _electionscan_options 两连击），options 优先。
        # sanshi chunk F1/F3：扫描与展示盘吃**同一份**已校验口径（_qimen_effective_options：同款双读合并 +
        # 起局法缺省 zhirun 显式填入 + 认不出的值报错）。此前展示盘缺省拆补、扫描的 calcDunJia 缺省置闰，
        # 同一次调用里命中判定与所见盘不同局。
        options = _qimen_effective_options(payload)
        _progress_tick(0, 2, "奇门择日：本地区间扫描")
        scan = self.js_client.run(
            "qimenzeri",
            {
                "action": "scan", "cfg": cfg, "geo": geo, "options": options, "tree": conditions,
                "limits": {"maxHits": payload.get("maxHits")} if payload.get("maxHits") else None,
            },
        )
        _progress_tick(1, 2, "奇门择日：铸展示盘")
        scan_data = scan.get("data") or {}
        if not scan_data.get("ok"):
            error = scan_data.get("error") or {}
            raise ToolValidationError(
                f"奇门择日搜索失败：{error.get('message') or '未知错误'}",
                code=f"tool.qimenzeri_{error.get('code') or 'scan_failed'}",
                details={"error": error},
            )
        intervals = scan_data.get("intervals") or []

        # Cast the DISPLAYED pan through ken at the winning moment, so all 17 奇门 段 keep their normal
        # compute authority (`_require_ken_pan` inside `_run_qimen_tool`). Only the interval search is
        # local — ken exposes no range endpoint (see the tool's compute_sources disclosure below).
        # `pick` is upstream's boundary-safe instant (both ends pulled 1 minute inward); using `start`
        # lands the pan on the wrong side of a 时辰 boundary.
        pan_moment = intervals[0].get("pick") if intervals else f"{start_date} {start_time}"
        pan_date, _, pan_time = str(pan_moment).partition(" ")
        # ⚠️ 必须剔掉调用方可能传进来的农历/节气**预取**：QimenInput 声明 nongli / jieqi_year_prev /
        # jieqi_year_current 作为缓存，_run_qimen_tool 见到就跳过 HTTP。但展示盘的时刻已经换成 pick，
        # 沿用按原 date 预取的那份 → realSunTime/jiedelta 对不上 → 时柱/局错；窗口跨年时
        # jieqi_year_current 更是整年都错。本工具自己返回 prerequisites，正诱使 agent 回传它们。
        qimen_payload = {k: v for k, v in payload.items()
                         if k not in ("nongli", "jieqi_year_prev", "jieqi_year_current", "jieqi_year_next",
                                      "zeriSnapshotMaxRows", "zeriSnapshotExplainRows")}
        # 展示盘跟随扫描口径：上游 QimenZeriMain.onPickInterval（:309-322）把冻结的扫描 options 整包回写
        # 主盘。_run_qimen_tool 的起局三开关读**顶层**，此前 options 里给的 timeAlg/日界 只进了扫描 →
        # 命中区间与展示盘不同局。这里用同一份合并后的 options（options 优先）回填顶层，整包 options 同传。
        for key in ("timeAlg", "after23NewDay", "lateZiHourUseNextDay"):
            if options.get(key) is not None:
                qimen_payload[key] = options[key]
        qimen_payload["options"] = options
        qimen = self._run_qimen_tool({
            **qimen_payload,
            "date": pan_date or start_date,
            "time": pan_time or start_time or "00:00:00",
        })
        extra = self.js_client.run(
            "qimenzeri",
            {
                "action": "snapshot", "cfg": cfg, "geo": geo, "options": options, "tree": conditions,
                "results": intervals, "truncated": bool(scan_data.get("truncated")),
                # [Q-452/Q-453] 命中清单上限 + 前 N 行附判读树（JS 侧同步引擎直算，与扫描同源）。
                **_zeri_snapshot_row_opts(payload),
            },
        )
        extra_data = extra.get("data") if isinstance(extra.get("data"), dict) else {}
        if extra_data.get("explain_error"):
            _degrade("qimenzeri 命中行判读树不可得：%s", extra_data.get("explain_error"))
        base_text = qimen.get("snapshot_text")
        extra_text = extra.get("snapshot_text")
        snapshot_text = "\n\n".join(part.strip() for part in (base_text, extra_text) if isinstance(part, str) and part.strip()) or None
        return {
            "pan": qimen.get("pan"),
            "pan_moment": pan_moment,
            "intervals": intervals,
            "hit_count": len(intervals),
            "truncated": bool(scan_data.get("truncated")),
            "stats": scan_data.get("stats"),
            "compiled_conditions": scan_data.get("compiled_tree"),
            # Honest算权 disclosure: the pan is ken-computed (or local calcDunJia when the options take
            # upstream's isQimenLocalRoute path), the interval search is not. Upstream anchors the local
            # 排盘 against the backend on a 42,731-point 0-diff parity grid.
            "compute_sources": {
                "scan": "local_calcDunJia",
                "pan": ((qimen.get("compute_sources") or {}).get("pan")) or "kinqimen",
            },
            "route": qimen.get("route"),
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="qimenzeri", snapshot_text=snapshot_text),
            "prerequisites": qimen.get("prerequisites"),
        }

    # ── 择日十技法（上游 v3.10.0）：六个本地扫描成员 ──────────────────────────────────
    # 每个 <x>zeri = 「基底技法的完整快照」+「择时三段」，与上游 aiExport 的 preset 组成
    # 逐字同构（AI_EXPORT_PRESET_SECTIONS.bazizeri = [...bazi, '择时搜索配置', '择时条件', '命中时段']）。
    # 六个引擎共享 makeHourlyScanEngine，API 逐字同形，所以这里也只有一个 runner ——
    # 复制六份近似代码等于复制六份同样的坑（尤其是「编译树 vs UI 树」那条，qimenzeri 上踩过）。
    _ZERI_SCAN_TOOLS: dict[str, dict[str, Any]] = {
        "huanglizeri": {"label": "黄历择吉", "base_tool": "huangli", "hourly": False,
                        "sections": ("择吉搜索配置", "择吉条件", "命中日段")},
        "bazizeri": {"label": "八字择时", "base_tool": "bazi_birth", "hourly": True,
                     "sections": ("择时搜索配置", "择时条件", "命中时段")},
        "taiyizeri": {"label": "太乙择时", "base_tool": "taiyi", "hourly": True,
                      "sections": ("择时搜索配置", "择时条件", "命中时段")},
        "ziweizeri": {"label": "紫微择时", "base_tool": "ziwei_birth", "hourly": True,
                      "sections": ("择时搜索配置", "择时条件", "命中时段")},
        "liurengzeri": {"label": "六壬择时", "base_tool": "liureng_gods", "hourly": True,
                        "sections": ("择时搜索配置", "择时条件", "命中时段")},
        "sanshizeri": {"label": "三式合一择时", "base_tool": "sanshiunited", "hourly": True,
                       "sections": ("择时搜索配置", "择时条件", "命中时段")},
    }

    # 各择日成员的窗口上限（天）。都比引擎自带上限紧：JS 子进程有墙钟，而扫描成本随窗口线性涨。
    # 日粒度的黄历便宜得多，故放宽。绝不静默截断（AGENTS §5.9）。
    _ZERI_MAX_SPAN_DAYS = {"huanglizeri": 366}
    _ZERI_DEFAULT_MAX_SPAN_DAYS = 92

    # 上游各择时宿主页的**出厂扫描口径**（组件 state.options 初值；日界两键=全局出厂值 1/1）。
    # skill 此前只把调用方显式给的键交给引擎，余下落到引擎内建缺省 —— 而引擎缺省与页面出厂档并不
    # 处处相同：六壬/三式扫描的贵人 guirengType 引擎缺省 0、页面出厂 2（liureng_gods 展示盘也是 2），
    # 同一窗口因此扫出与桌面不同的命中集。现以此表打底，顶层与 options 依次覆盖。
    _ZERI_PAGE_DEFAULT_OPTIONS: dict[str, dict[str, Any]] = {
        "huanglizeri": {},                                                        # HuangliZeriMain：无扫描口径
        "bazizeri": {"timeAlg": 0, "after23NewDay": 1, "lateZiHourUseNextDay": 1,
                     "godKeyPos": "年", "phaseType": 0},                           # BaziZeriMain.js:80
        "taiyizeri": {"tn": 0},                                                   # TaiyiZeriMain.js:47
        "ziweizeri": {"timeAlg": 1, "gender": 1},                                 # ZiweiZeriMain.js:72
        "liurengzeri": {"guirengType": 2, "yueMode": "zhongqi",
                        "after23NewDay": 1, "lateZiHourUseNextDay": 1},            # LiurengZeriMain.js:79
        "sanshizeri": {"guirengType": 2, "yueMode": "zhongqi", "taiyiAccum": 0,
                       "after23NewDay": 1, "lateZiHourUseNextDay": 1, "timeAlg": 0},  # SanshiZeriMain.js:80
    }

    @staticmethod
    def _zeri_display_overrides(
        tool_name: str, options: dict[str, Any], option_split: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """展示盘跟随扫描口径（上游 v3.11 [挂载自检 F-37]「所见行=所判口径」）。

        按各宿主 buildFields / applyWorkbenchCalibre 的键映射，把**扫描实际生效**的口径（页面出厂档 ⊕ 顶层
        ⊕ options；键缺席时取扫描引擎自身缺省）写进基底工具的入参。六壬择时的 yueMode(节气换将) / 阴阳系、
        三式择时的六壬层（贵人 / 换将 / 阴阳系）与奇门播种键，自 liureng_gods options / sanshiunited liureng_options
        可达（v3.11.x sanshi chunk）起一并回写。三式的三家拆分取 JS 扫描回传的 vendored splitSanshiOptions 结果
        （option_split），不在这里手抄键表。
        """
        def eff(key: str, engine_default: Any) -> Any:
            value = options.get(key)
            return engine_default if value is None else value

        if tool_name == "bazizeri":
            # BaziZeriMain.buildFields（:323-345）：timeAlg/phaseType/godKeyPos/日界/晚子时 取冻结扫描 options。
            out = {"timeAlg": eff("timeAlg", 0), "after23NewDay": eff("after23NewDay", 1),
                   "lateZiHourUseNextDay": eff("lateZiHourUseNextDay", 1)}
            for key in ("godKeyPos", "phaseType"):
                if options.get(key) is not None:
                    out[key] = options[key]
            return out
        if tool_name == "ziweizeri":
            # ZiweiZeriMain.buildFields（:318-332）：gender/timeAlg 取扫描 options，缺省 1/1 = 扫描引擎缺省
            # （computeZiweiScanPan：timeAlg 缺省钟表时、gender 缺省男）。
            return {"timeAlg": eff("timeAlg", 1), "gender": eff("gender", 1)}
        if tool_name == "liurengzeri":
            # LiurengZeriMain.requestChartAndPlot（:146-148 日界/晚子时）+ applyWorkbenchCalibre（:306-313：
            # guirengType→guireng、yueMode→yueJiangMethod（'jieqi' 否则 'zhongqi'）、yinyangSystem 原名）。
            out = {"guirengType": eff("guirengType", 0), "after23NewDay": eff("after23NewDay", 1),
                   "lateZiHourUseNextDay": eff("lateZiHourUseNextDay", 1)}
            cast: dict[str, Any] = {}
            if options.get("yueMode") is not None:
                cast["yueJiangMethod"] = "jieqi" if options["yueMode"] == "jieqi" else "zhongqi"
            if options.get("yinyangSystem") not in (None, ""):
                cast["yinyangSystem"] = options["yinyangSystem"]
            if cast:
                out["options"] = cast
            return out
        if tool_name == "taiyizeri":
            # TaiyiZeriMain.buildFields（:309-327：性别←options.sex、日界缺省 0、晚子时缺省 1，与
            # computeTaiyiScanPan 同缺省）+ applyWorkbenchCalibre（:255-261：tn 进太乙页 options）。
            taiyi_options = {"tn": eff("tn", 0)}
            if options.get("sex") is not None:
                taiyi_options["sex"] = options["sex"]
            if isinstance(options.get("school"), dict):
                # 流派六轴对象（扫描引擎 applyTaiyiSchool(pan, o.school) 按对象展开；字符串档在扫描侧即无效）。
                taiyi_options["school"] = options["school"]
            return {"after23NewDay": eff("after23NewDay", 0), "lateZiHourUseNextDay": eff("lateZiHourUseNextDay", 1),
                    "options": taiyi_options}
        if tool_name == "sanshizeri":
            # SanshiZeriMain.onPickInterval → applyWorkbenchCalibre（:319-335）：工作台 13 键回写三式页 options
            # （guirengType→guireng、yueMode→yueJiangMethod、其余原名）；奇门播种键（QM_SEED_KEYS，startScan
            # 取自内嵌三式页）本就是三式页的值。扫描实际吃的三家口径 = vendored splitSanshiOptions 的拆分
            # （JS 扫描回传 option_split）——逐家原样写进 sanshiunited 的三个子口径。
            if not isinstance(option_split, dict):
                raise ToolTransportError(
                    bilingual("三式择时扫描未回传口径拆分（option_split），无法让展示盘跟随扫描口径。",
                              "sanshizeri: the scan returned no option_split, so the display chart cannot follow the scan settings."),
                    code="tool.sanshizeri_option_split_missing",
                    details={"hint": "tools/zeriScan.js 的 sanshizeri scan 应回 data.option_split（splitSanshiOptions）。"},
                )
            out = {"timeAlg": eff("timeAlg", 0), "after23NewDay": eff("after23NewDay", 1),
                   "lateZiHourUseNextDay": eff("lateZiHourUseNextDay", 1)}
            time_keys = ("timeAlg", "after23NewDay", "lateZiHourUseNextDay")   # 三式共享时间键走顶层
            qimen = {k: v for k, v in (option_split.get("qimen") or {}).items() if k not in time_keys and v is not None}
            if qimen:
                out["qimen_options"] = qimen
            split_lr = option_split.get("liureng") or {}
            liureng: dict[str, Any] = {}
            if split_lr.get("guirengType") not in (None, ""):
                liureng["guirengType"] = split_lr["guirengType"]
            if split_lr.get("yueMode") is not None:
                liureng["yueJiangMethod"] = "jieqi" if split_lr["yueMode"] == "jieqi" else "zhongqi"
            if split_lr.get("yinyangSystem") not in (None, ""):
                liureng["yinyangSystem"] = split_lr["yinyangSystem"]
            if liureng:
                out["liureng_options"] = liureng
            split_ty = option_split.get("taiyi") or {}
            if split_ty.get("tn") is not None:
                out["taiyi_options"] = {"tn": split_ty["tn"]}
            return out
        return {}

    def _zeri_prefetch_explains(
        self, endpoint: str, base: dict[str, Any], intervals: list[dict[str, Any]], payload: dict[str, Any], label: str
    ) -> list[Any]:
        """[Q-453] 后端扫描家族（天星/七政/印度）命中清单前 N 行的判读树。

        与上游宿主 prefetchSnapshotExplains（TianxingElectionMain.js:358-374 等三处）同式：扫描完成后对前
        N 行（zeriSnapshotExplainRows，缺省 3）逐行打 /explain，t = row.pick 或 start+':00'、'-'→'/'；结果按
        行序交给 builder 的 explainAt。单行失败按上游置 null（该行只列清单、不附判读），但失败本身进
        envelope.warnings，不静默。
        """
        count = min(_zeri_explain_rows(payload), len(intervals))
        explains: list[Any] = []
        for index in range(count):
            row = intervals[index] if isinstance(intervals[index], dict) else {}
            t = str(row.get("pick") or f"{row.get('start')}:00").replace("-", "/")
            try:
                raw = self._call_remote(endpoint, {**base, "t": t})
                data = self._require_electionscan_ok(raw, endpoint=endpoint)
            except HorosaSkillError as exc:
                _degrade("%s 第 %d 行判读树预取失败（%s）：%s", label, index + 1, endpoint, exc)
                explains.append(None)
                continue
            explains.append(data if isinstance(data, dict) else None)
        return explains

    def _run_zeri_scan_tool(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        spec = self._ZERI_SCAN_TOOLS[tool_name]
        label = spec["label"]
        start_date, start_time, end_date, end_time = self._tianxing_window(payload)
        if not start_date or not end_date:
            raise ToolValidationError(
                f"{label}需要搜索时间窗（startDate/endDate）。",
                code=f"tool.{tool_name}_missing_window",
                details={"startDate": start_date, "endDate": end_date},
            )
        conditions = payload.get("conditions")
        if not conditions:
            raise ToolValidationError(
                f"{label}需要择日条件树（conditions）。",
                code=f"tool.{tool_name}_missing_conditions",
                details={"hint": "条件类键与参数见本工具的 agent_guidance。"},
            )
        max_span = _clamped_max_span(
            payload, self._ZERI_MAX_SPAN_DAYS.get(tool_name, self._ZERI_DEFAULT_MAX_SPAN_DAYS)
        )
        _require_sane_window(start_date, end_date, max_span=max_span, tool=tool_name)

        cfg = {"startDate": start_date, "startTime": start_time, "endDate": end_date, "endTime": end_time}
        geo = {k: payload.get(k) for k in ("zone", "gpsLon", "gpsLat", "lon", "lat", "pos")
               if payload.get(k) is not None}
        # 起局开关既可走顶层（schema 逐个带描述，agent 照传是正确用法）也可走 options，options 优先
        # —— 与 tianxing / qimenzeri 同款双读合并。只读 options 会让顶层写法被静默丢弃，
        # 于是命中区间与展示盘不同局，而配置段还打出一个没用上的设置（v0.33.1 教训）。
        # 底层先铺**上游宿主页出厂扫描口径**（_ZERI_PAGE_DEFAULT_OPTIONS）：只把调用方给的键交给
        # 引擎时，余下落到引擎内建缺省，而它与桌面页出厂档并不处处相同。
        top_keys = ("timeAlg", "after23NewDay", "lateZiHourUseNextDay", "godKeyPos", "phaseType", "guirengType", "school")
        if tool_name == "ziweizeri":
            # 紫微扫描按 options.gender 起盘（ziweiZeriScanEngine.computeZiweiScanPan），上游工作台常驻该键；
            # 此前 skill 既不声明也不合并顶层 gender → 女命恒按男命扫描，展示盘却按顶层性别出。
            top_keys = (*top_keys, "gender")
        options = {
            **self._ZERI_PAGE_DEFAULT_OPTIONS.get(tool_name, {}),
            **{k: payload[k] for k in top_keys if payload.get(k) is not None},
            **(payload.get("options") or {}),
        }
        if tool_name == "ziweizeri" and options.get("gender") is not None:
            # 上游 ZiweiZeriMain.buildGeoParams 同把工作台性别放进 geoParams（:193）。
            geo["gender"] = options["gender"]
        natal = payload.get("natal") if isinstance(payload.get("natal"), dict) else None

        request = {"technique": tool_name, "action": "scan", "cfg": cfg, "geo": geo,
                   "options": options, "tree": conditions}
        if natal:
            request["natal"] = natal
        if payload.get("maxHits"):
            request["limits"] = {"maxHits": payload.get("maxHits")}
        _progress_tick(0, 2, f"{label}：本地区间扫描")
        scan = self.js_client.run("zeri_scan", request)
        _progress_tick(1, 2, f"{label}：铸展示盘")
        scan_data = scan.get("data") or {}
        if not scan_data.get("ok"):
            error = scan_data.get("error") or {}
            raise ToolValidationError(
                f"{label}搜索失败：{error.get('message') or '未知错误'}",
                code=f"tool.{tool_name}_{error.get('code') or 'scan_failed'}",
                details={"error": error},
            )
        intervals = scan_data.get("intervals") or []

        # 展示盘走**基底技法自己的 runner**，所有段保持它原本的算权（ken/后端/本地各按其旧）。
        # 只有区间搜索在本地跑。`pick` 是上游的边界安全时刻（两端各内缩），用 `start` 会把盘
        # 落到时辰边界的另一侧 —— qimenzeri 上已验证过这一条。
        pan_moment = intervals[0].get("pick") if intervals else f"{start_date} {start_time}"
        pan_date, _, pan_time = str(pan_moment).partition(" ")
        base_payload = {k: v for k, v in payload.items()
                        if k not in ("conditions", "options", "natal", "maxHits", "maxSpanDays",
                                     "startDate", "startTime", "endDate", "endTime",
                                     "zeriSnapshotMaxRows", "zeriSnapshotExplainRows",
                                     "nongli", "jieqi_year_prev", "jieqi_year_current")}
        base_payload["date"] = pan_date or start_date
        base_payload["time"] = pan_time or start_time or "00:00:00"
        # 展示盘跟随**扫描口径**（上游 v3.11「所见行=所判口径」：各宿主 buildFields/applyWorkbenchCalibre
        # 把冻结的扫描 options 回写进 pick 后的显示盘）。此前 base_payload 丢掉 options、只剩顶层 →
        # options 里给的时间算法/贵人/日界对展示盘全无效，且缺省时展示盘走基底工具自己的缺省
        # （紫微扫描恒钟表时、展示盘却按 ziwei_birth 的真太阳时出），同一次结果里两套口径。
        base_payload.update(self._zeri_display_overrides(tool_name, options, scan_data.get("option_split")))
        # 走公共 run_tool 而非各自的私有 runner：六个基底技法的内部调用形状并不统一
        # （qimen 是 _run_qimen_tool(payload)、liureng 是 _run_liureng_tool(name, payload)、
        # bazi/ziwei 干脆没有私有 runner 而走通用远端路径）。run_tool 对四种都一致，
        # 且顺带跑完各自 runner 的富化，展示盘因此与直接调该技法**逐字同段**。
        # agent_confirmed_settings：这是同一次请求内部的子盘，设置已在外层过闸，
        # 不再重复拦（与 _tianxing_selected_moment_section 同款）。
        base_payload["agent_confirmed_settings"] = True
        base_payload.setdefault("clarification_notes", f"{tool_name} selected-moment sub-chart")
        base_env = self.run_tool(spec["base_tool"], base_payload, save_result=False)
        if not base_env.ok:
            # 🔴 把基底工具的**原始报错**带出来。只说「铸盘失败」时，无 Mongo 机器上的
            # Java 9999 与真正的接线错误长得一模一样 —— 本轮 live 验证为区分这两者做了整轮排查，
            # 而那轮排查本可以由这一行错误信息省掉。
            base_err = base_env.error
            raise ToolTransportError(
                f"{label}的展示盘（{spec['base_tool']}）铸盘失败，命中区间已算出但无法出盘："
                f"{(base_err.message if base_err else '') or '未知错误'}",
                code=f"tool.{tool_name}_base_chart_failed",
                details={"base_tool": spec["base_tool"], "pan_moment": pan_moment,
                         "base_error": {"code": base_err.code, "message": base_err.message} if base_err else None,
                         "hint": f"先单独调 {spec['base_tool']} 同刻复现：它也红 = 基底技法/环境问题"
                                 f"（Java 族回 9999 时先读 Result 原文；裸 -jar 起的实例连不上 Mongo 就是这样），"
                                 f"只有择日这条红才是接线问题。"},
            )
        base = base_env.data if isinstance(base_env.data, dict) else {}

        extra = self.js_client.run(
            "zeri_scan",
            {"technique": tool_name, "action": "snapshot", "cfg": cfg, "geo": geo, "options": options,
             **({"natal": natal} if natal else {}),
             "tree": conditions, "results": intervals, "truncated": bool(scan_data.get("truncated")),
             # [Q-452/Q-453] 命中清单上限 + 前 N 行附判读树（JS 侧同步引擎直算 explainAt，与扫描同源）。
             **_zeri_snapshot_row_opts(payload)},
        )
        extra_data = extra.get("data") if isinstance(extra.get("data"), dict) else {}
        if extra_data.get("explain_error"):
            _degrade("%s 命中行判读树不可得：%s", tool_name, extra_data.get("explain_error"))
        base_text = base.get("snapshot_text") if isinstance(base, dict) else None
        extra_text = extra.get("snapshot_text")
        snapshot_text = "\n\n".join(
            part.strip() for part in (base_text, extra_text) if isinstance(part, str) and part.strip()
        ) or None
        return {
            "pan_moment": pan_moment,
            "pan": base.get("pan") if isinstance(base, dict) else None,
            "base": base,
            "intervals": intervals,
            "hit_count": len(intervals),
            "truncated": bool(scan_data.get("truncated")),
            "stats": scan_data.get("stats"),
            "compiled_conditions": scan_data.get("compiled_tree"),
            "limits": scan_data.get("limits"),
            # 算权如实披露：展示盘按基底技法的原算源，区间搜索是本地 vendored 引擎
            # （上游对每个成员都有跨引擎一致性金标与压力网看守，见 v3.10.0 发行说明）。
            "compute_sources": {"scan": f"local_{tool_name}_engine", "pan": spec["base_tool"]},
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique=tool_name, snapshot_text=snapshot_text),
        }

    # ── 择日十技法：两个**后端扫描**成员（七政 / 印度）───────────────────────────────
    # 与上面六个的分工不同：判定跑在 astropy（swisseph 直连分钟粒度），skill 只发请求 ——
    # 与 tianxing 走 /electionscan/* 是同一条路，端点三件套 scan/conditiontypes/explain 也同形。
    # 端点写**完整字面量**而不是 f"{prefix}/scan" 拼出来：`test_registered_endpoints_have_call_sites`
    # 靠在源码里搜字面量确认「登记的端点真有人调」，拼接会让它看不见 —— 那条守卫的价值恰恰在于
    # 抓「登记了却没接线」和「拼写漂移」，为省几个字符把它弄瞎不划算。
    _ZERI_BACKEND_TOOLS: dict[str, dict[str, Any]] = {
        "qizhengzeri": {
            "label": "七政择时", "base_tool": "guolao_chart",
            "scan": "/qizhengelectionscan/scan",
            "explain": "/qizhengelectionscan/explain",
            "conditiontypes": "/qizhengelectionscan/conditiontypes",
        },
        "indiazeri": {
            # 印度页是 A 类星盘系，上游 preset 里 indiazeri 只有择时三段、无基底快照槽
            # （盘全文见 india_chart 本身）—— 故不铸展示盘，段自足。
            "label": "印度择时（Muhurta）", "base_tool": None,
            "scan": "/indiaelectionscan/scan",
            "explain": "/indiaelectionscan/explain",
            "conditiontypes": "/indiaelectionscan/conditiontypes",
        },
    }
    # 后端单请求硬上限 93 天（election_scan 家族共用），上游用按月分段绕开。
    _ZERI_BACKEND_MAX_SPAN_DAYS = 731

    # 后端扫描上下文**实读**的口径键 + 上游宿主页出厂档（buildScanPayload 同键同缺省）：
    #   七政 QizhengScanContext（qizheng_election_scan.py:72-81）读 su28Mode（仅 2 回归今宿 / 3 开禧宿度，其余
    #     ValueError）、nodeType、lilithType（mean|true）、fuOrb；页面出厂 {su28Mode:2, nodeType:'mean',
    #     lilithType:'mean'}（QizhengZeriMain.js:56,201-219）。
    #   印度 IndiaScanContext（india_election_scan.py:71-72）读 ayanamsa（缺省 lahiri）、nodeType；页面出厂
    #     {ayanamsa:'lahiri', nodeType:'mean'}（IndiaZeriMain.js:57,170-193）。
    _ZERI_BACKEND_SCAN_KEYS: dict[str, tuple[str, ...]] = {
        "qizhengzeri": ("su28Mode", "nodeType", "lilithType", "fuOrb"),
        "indiazeri": ("ayanamsa", "nodeType"),
    }
    _ZERI_BACKEND_SCAN_DEFAULTS: dict[str, dict[str, Any]] = {
        "qizhengzeri": {"su28Mode": 2, "nodeType": "mean", "lilithType": "mean"},
        "indiazeri": {"ayanamsa": "lahiri", "nodeType": "mean"},
    }

    def _zeri_backend_scan_options(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        """后端扫描口径：页面出厂档 → 顶层 → options 依次覆盖（与 tianxing 同款双读，options 优先）。

        取值越界一律结构化报错，不交后端去静默回落（nodeType 写错会被后端当 mean、su28Mode 越界会 500）。
        """
        keys = self._ZERI_BACKEND_SCAN_KEYS.get(tool_name, ())
        options = payload.get("options") if isinstance(payload.get("options"), dict) else {}
        merged: dict[str, Any] = dict(self._ZERI_BACKEND_SCAN_DEFAULTS.get(tool_name, {}))
        if tool_name == "indiazeri" and payload.get("indiaAyanamsa") is not None:
            # 与 india_chart 同词表的 indiaAyanamsa 作 ayanamsa 的别名（上游印度择时页把扫描岁差回写
            # 显示盘的 indiaAyanamsa 字段，IndiaZeriMain.js:350 —— 两名同一值）；显式 ayanamsa 优先。
            merged["ayanamsa"] = payload["indiaAyanamsa"]
        for source in (payload, options):
            for key in keys:
                if source.get(key) is not None:
                    merged[key] = source[key]
        if tool_name == "qizhengzeri":
            try:
                su28 = int(merged.get("su28Mode"))
            except (TypeError, ValueError):
                su28 = None
            if su28 not in (2, 3):
                raise ToolValidationError(
                    "七政择时的宿度制只支持 su28Mode=2（回归今宿，缺省）或 3（开禧宿度）。",
                    code="tool.qizhengzeri_bad_su28mode",
                    details={"su28Mode": merged.get("su28Mode"), "allowed": [2, 3],
                             "why": "后端 QizhengScanContext 只实现这两档（qizheng_election_scan.py:74-76）。"},
                )
            merged["su28Mode"] = su28
        for key in ("nodeType", "lilithType"):
            if key not in merged:
                continue
            value = str(merged[key]).strip().lower()
            if value not in ("mean", "true"):
                raise ToolValidationError(
                    f"{tool_name} 的 {key} 只接受 mean（平，缺省）或 true（真）。",
                    code=f"tool.{tool_name}_bad_{key.lower()}",
                    details={key: merged[key], "allowed": ["mean", "true"]},
                )
            merged[key] = value
        return merged

    def _run_zeri_backend_tool(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        spec = self._ZERI_BACKEND_TOOLS[tool_name]
        label = spec["label"]
        start_date, start_time, end_date, end_time = self._tianxing_window(payload)
        if not start_date or not end_date:
            raise ToolValidationError(
                f"{label}需要搜索时间窗（startDate/endDate）。",
                code=f"tool.{tool_name}_missing_window",
                details={"startDate": start_date, "endDate": end_date},
            )
        conditions = payload.get("conditions")
        if not conditions:
            raise ToolValidationError(
                f"{label}需要择时条件树（conditions）。",
                code=f"tool.{tool_name}_missing_conditions",
                details={"hint": "条件类键与参数见本工具的 agent_guidance。"},
            )
        max_span = _clamped_max_span(payload, self._ZERI_BACKEND_MAX_SPAN_DAYS)
        _require_sane_window(start_date, end_date, max_span=max_span, tool=tool_name)

        # 🔴 后端吃的是**编译树**，不是 UI 树。直接发 UI 树的后果不是报「形状不对」，而是
        # `unknown condition type: None`——它按编译树的键去读 type，读到 None。这与
        # zeriScan.js 里那条注释是同一个坑，只不过发生在 HTTP 边界上。tianxing 一直是先 compile
        # 再发（service.py:7126），此处照办；本地先编译还能把条件错误挡在一次远端往返之前。
        compile_result = self.js_client.run(
            "zeri_scan_remote", {"technique": tool_name, "action": "compile", "tree": conditions}
        )
        compile_data = compile_result.get("data") or {}
        if not compile_data.get("ok"):
            error = compile_data.get("error") or {}
            details: dict[str, Any] = {"error": error}
            # 自愈式报错：把服务端**实现集**（运行时孪生）带回，agent 不用猜哪些键合法。
            try:
                ct = self._call_remote(spec["conditiontypes"], {})
                if isinstance(ct, dict) and isinstance(ct.get("types"), list):
                    details["server_condition_types"] = ct.get("types")
            except Exception:  # noqa: BLE001 - 自省失败不该遮住原始校验错误
                pass
            raise ToolValidationError(
                f"{label}条件树不合法：{error.get('message') or '未知错误'}",
                code=f"tool.{tool_name}_invalid_conditions",
                details=details,
            )
        compiled = compile_data.get("compiled")

        cfg = {"startDate": start_date, "startTime": start_time, "endDate": end_date, "endTime": end_time}
        base_request: dict[str, Any] = {
            **cfg,
            "zone": _electionscan_zone(payload.get("zone")),
            "ad": payload.get("ad", 1),
            "conditions": compiled,
        }
        for key in ("lat", "lon", "gpsLat", "gpsLon", "pos", "hsys", "zodiacal", "siderealAyanamsa",
                    "height", "natal"):
            if payload.get(key) is not None:
                base_request[key] = payload[key]
        base_request.update(_electionscan_options(payload))
        base_request.update(_electionscan_options(payload.get("options")))
        # 后端扫描上下文**实读**的口径键（与上游宿主 buildScanPayload 同键同缺省）。此前 skill 发的是
        # indiaAyanamsa（IndiaScanContext 不读 → 印度择时恒按 Lahiri）与 ayanamsaDeg/indiaHsys（两个扫描都不读），
        # 七政三键一个不发、options 白名单也滤掉了它们 —— 口径看似可调，搜索结果从不变。
        scan_opts = self._zeri_backend_scan_options(tool_name, payload)
        base_request.update(scan_opts)

        # 按月分段：后端单请求 93 天硬顶，上游在 UI 里分段绕开。§5「请求型 builder 归 Python」→
        # 循环写在这里；分段/缝合的算术仍走 vendored 那份，边界才与星阙逐字一致。
        segments = self._tianxing_js({"action": "split", "cfg": cfg}, stage="split").get("segments") or [cfg]
        lists: list[list[dict[str, Any]]] = []
        truncated = False
        total_segments = len(segments)
        for index, segment in enumerate(segments, start=1):
            _progress_tick(index - 1, total_segments, f"{label}：扫描第 {index}/{total_segments} 段")
            raw = self._call_remote(spec["scan"], {**base_request, **segment})
            data = self._require_electionscan_ok(raw, endpoint=spec["scan"])
            lists.append(list(data.get("intervals") or []))
            truncated = truncated or bool(data.get("truncated"))
        _progress_tick(total_segments, total_segments, f"{label}：缝合区间")
        stitched = self._tianxing_js({"action": "stitch", "lists": lists}, stage="stitch")
        intervals = stitched.get("intervals") or []

        # [Q-453] 命中清单前 N 行附判读树：服务端判读，上游宿主扫描后预取（QizhengZeriMain.js:327-340 /
        # IndiaZeriMain.js:295-308），builder 经 explainAt 按行序读缓存。
        explains = self._zeri_prefetch_explains(spec["explain"], base_request, intervals, payload, label)
        extra = self.js_client.run(
            "zeri_scan_remote",
            {"technique": tool_name, "action": "snapshot",
             "cfg": {**cfg, **{k: payload.get(k) for k in ("pos", "hsys", "zodiacal", "siderealAyanamsa",
                                                           "gpsLon", "gpsLat") if payload.get(k) is not None}},
             "geo": {k: payload.get(k) for k in ("zone", "lat", "lon", "gpsLat", "gpsLon", "pos")
                     if payload.get(k) is not None},
             "tree": conditions, "results": intervals, "truncated": truncated,
             "explains": explains, **_zeri_snapshot_row_opts(payload)},
        )
        extra_text = extra.get("snapshot_text")

        base_text = None
        base: dict[str, Any] = {}
        if spec["base_tool"]:
            pan_moment = intervals[0].get("pick") if intervals else f"{start_date} {start_time}"
            pan_date, _, pan_time = str(pan_moment).partition(" ")
            base_payload = {k: v for k, v in payload.items()
                            if k not in ("conditions", "options", "natal", "maxHits", "maxSpanDays",
                                         "startDate", "startTime", "endDate", "endTime",
                                         "zeriSnapshotMaxRows", "zeriSnapshotExplainRows",
                                         "su28Mode", "nodeType", "lilithType", "fuOrb")}
            base_payload.update({"date": pan_date or start_date,
                                 "time": pan_time or start_time or "00:00:00",
                                 "agent_confirmed_settings": True,
                                 "clarification_notes": f"{tool_name} selected-moment sub-chart"})
            if tool_name == "qizhengzeri":
                # 展示盘跟随扫描口径（上游 QizhengZeriMain.buildFields :365-402 [挂载自检 F-37]）：罗计交点 / 月孛
                # 走 guolao 键名（perchart.applyGuolaoSiyu 读 guolaoNodeType/guolaoLilithType）；宿度制
                # su28Mode → doubingSu28（:390 `doubingSu28: Number(o.su28Mode)`，缺省 2 回归今宿）。
                base_payload["guolaoNodeType"] = scan_opts.get("nodeType", "mean")
                base_payload["guolaoLilithType"] = scan_opts.get("lilithType", "mean")
                base_payload["doubingSu28"] = int(scan_opts.get("su28Mode", 2))
            base_env = self.run_tool(spec["base_tool"], base_payload, save_result=False)
            if base_env.ok and isinstance(base_env.data, dict):
                base = base_env.data
                base_text = base.get("snapshot_text")
            else:
                # 命中区间照常交付，但展示盘缺席必须可见（此前静默吞掉 → 基底段整段消失而无任何说明）。
                base_err = base_env.error
                _degrade("%s 展示盘（%s）铸盘失败：%s", tool_name, spec["base_tool"],
                         (base_err.message if base_err else "") or "未知错误")
        else:
            pan_moment = intervals[0].get("pick") if intervals else f"{start_date} {start_time}"

        # [单时判读]：与 tianxing 同款能力 —— 后端 explain 端点复用**同一个求值器**，
        # 所以逐叶 pass 与扫描结果绝对同源。未给 explainAt 不产，零回归。
        explain_payload = None
        if payload.get("explainAt"):
            t_raw = str(payload.get("explainAt") or "").strip().replace("-", "/")
            if len(t_raw) == 16:  # YYYY/MM/DD HH:mm
                t_raw = f"{t_raw}:00"
            raw = self._call_remote(spec["explain"], {**base_request, "t": t_raw})
            data = self._require_electionscan_ok(raw, endpoint=spec["explain"])
            if isinstance(data, dict) and data.get("tree") is not None:
                explain_payload = {"t": data.get("t") or t_raw, "tree": data.get("tree")}

        snapshot_text = "\n\n".join(
            part.strip() for part in (base_text, extra_text) if isinstance(part, str) and part.strip()
        ) or None
        return {
            "pan_moment": pan_moment,
            "base": base or None,
            **({"explain": explain_payload} if explain_payload else {}),
            "intervals": intervals,
            "hit_count": len(intervals),
            "truncated": truncated,
            "segments": len(segments),
            "compiled_conditions": compiled,
            # 算权如实披露：判定与区间搜索都在后端 astropy（swisseph 直连），不是本地重算。
            "compute_sources": {"scan": f"astropy{spec['scan']}", "pan": spec["base_tool"] or "none"},
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique=tool_name, snapshot_text=snapshot_text),
        }
