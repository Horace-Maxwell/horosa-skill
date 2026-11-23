"""天文馆取数（SkyAPI，上游 v3.15.0 AI 工具 sky_at）：门面 horosa_sky_at。

上游工具（utils/aiTools/tools/skyAt.js）= 解析时间地点 → 天文馆同一个后端接口 /planetarium/state（纯天文口径）→
skyStateText 排版。时间地点解析走 skill 自己的那条（`place` 与技法载荷同一管线）；请求体照上游 run() 逐键；排版跑上游
skyStateText 原函数（报告盘图 bundle 的 app-text 通道 sky_state，那份文件拖着 AI 助手壳不能整份 vendor），skill 不手抄。
回包是工具正文，不是技法快照（上游小标题用「■」不用 [段头]）：不进导出段目录、不存档。
"""
from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError

from horosa_skill.civil_calendar import _parse_date_parts, _to_slash_date
from horosa_skill.errors import ToolTransportError, ToolValidationError, bilingual, validation_errors
from horosa_skill.input_normalization import normalize_request_payload

# 上游 skyAt.js SKY_BODIES（只要这几颗的取值域；bundle 的 sky_bodies 入口与之对拍，tests/test_sync315_sky_at.py）
SKY_BODIES = ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "North Node", "South Node")
SKY_BRIGHTEST_MAX = 60  # 上游 inputSchema brightestStars maximum
_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")


def _invalid(zh: str, en: str, **details: Any) -> ToolValidationError:
    return ToolValidationError(bilingual(zh, en), code="sky.invalid_payload", details=details)


class SkyAPI:
    def sky_at(self, payload: dict[str, Any]) -> dict[str, Any]:
        from horosa_skill.schemas.tools.facades import SkyAtInput

        placed = self.resolve_place_fields(payload, tool_name="sky_at") if isinstance(payload, dict) else payload
        # 与 MCP 层同一道归一（十进制坐标 → 31n13 + gpsLat/gpsLon、IANA → 当日偏移、时刻补秒、越界日期 / 时刻报错）：CLI / 直调同口径。
        if isinstance(placed, dict):
            placed = normalize_request_payload(placed, model=SkyAtInput)
        try:
            req = SkyAtInput.model_validate(placed)
        except ValidationError as exc:
            raise _invalid("天文馆取数的参数不对。", "Invalid payload for sky_at.", errors=validation_errors(exc)) from exc
        date = f"{req.date or ''}".strip()
        if _parse_date_parts(date) is None:
            raise _invalid(f"date 须为 YYYY-MM-DD：{req.date!r}", f"date must be YYYY-MM-DD: {req.date!r}", field="date")
        assumptions: list[str] = []
        time = f"{req.time or ''}".strip()
        if not time:
            # 上游 run()：时刻只有日期 → 12:00:00
            time = "12:00:00"
            assumptions.append(bilingual("没给时刻，按当日 12:00:00 取数。", "No time given: using 12:00:00 on that date."))
        tm = _TIME_RE.match(time)
        if not tm or int(tm.group(1)) > 23 or int(tm.group(2)) > 59 or int(tm.group(3) or 0) > 59:
            raise _invalid(f"time 须为 HH:mm[:ss]：{req.time!r}", f"time must be HH:mm[:ss]: {req.time!r}", field="time")
        time = f"{int(tm.group(1)):02d}:{tm.group(2)}:{tm.group(3) or '00'}"
        missing = [k for k in ("lat", "lon", "zone") if not f"{getattr(req, k) or ''}".strip()]
        if missing:
            raise ToolValidationError(
                bilingual(f"缺观测地点：{'/'.join(missing)}。给 place（地名）或 lat/lon/zone。",
                          f"Observer location missing: {', '.join(missing)}. Give place, or lat/lon/zone."),
                code="sky.location_missing",
                details={"missing": missing},
            )
        bodies = None
        if req.bodies is not None:
            by_fold = {b.casefold().replace(" ", ""): b for b in SKY_BODIES}
            picked, unknown = [], []
            for item in req.bodies:
                hit = by_fold.get(f"{item}".casefold().replace(" ", "").replace("_", ""))
                (picked if hit else unknown).append(hit or item)
            if unknown or not picked:
                raise _invalid(f"bodies 认不出：{unknown or req.bodies}（可选：{' / '.join(SKY_BODIES)}）",
                               f"unknown bodies: {unknown or req.bodies}", field="bodies", allowed=list(SKY_BODIES))
            bodies = list(dict.fromkeys(picked))
        n = req.brightestStars or 0
        if not 0 <= n <= SKY_BRIGHTEST_MAX:
            raise _invalid(f"brightestStars 须为 0–{SKY_BRIGHTEST_MAX}：{req.brightestStars!r}",
                           f"brightestStars must be 0-{SKY_BRIGHTEST_MAX}", field="brightestStars")
        # 上游 skyAt.run() 的请求体逐键（天文馆同一口径：hsys 1 / 回归黄道 / 无岁差制 / 不倒置；要亮星才带星表、恒带升中落）。
        body = {
            "date": _to_slash_date(date), "time": time, "zone": req.zone,
            "lat": req.lat, "lon": req.lon, "gpsLat": req.gpsLat, "gpsLon": req.gpsLon, "pos": req.pos or None,
            "hsys": 1, "zodiacal": 0, "siderealAyanamsa": "", "doubingSu28": 0, "southchart": 0,
            "starLimit": 9000 if n > 0 else 0, "includeRiseSet": True,
        }
        rsp = self._call_remote("/planetarium/state", {k: v for k, v in body.items() if v is not None})
        data = rsp.get("Result") if isinstance(rsp, dict) and isinstance(rsp.get("Result"), dict) else rsp
        if not isinstance(data, dict) or not isinstance(data.get("bodies"), list):
            raise ToolTransportError(
                bilingual("天文馆数据没取到（需本机计算服务在线）。", "The planetarium backend returned no sky state."),
                code="sky.backend_failed",
                details={"backend_error": rsp.get("err") if isinstance(rsp, dict) else None},
            )
        opts = {k: v for k, v in {"bodies": bodies, "fixedStars": req.fixedStars, "brightestStars": n or None,
                                  "visibleOnly": req.visibleOnly}.items() if v}
        runs = self.js_client.run_app_texts([{"name": "sky_state", "args": {"data": data, "opts": opts}}])
        out = runs[0] if isinstance(runs, list) and runs else None
        content = f"{out.get('value') or ''}".strip() if isinstance(out, dict) and out.get("ok") else ""
        if not content:
            raise ToolTransportError(
                bilingual("天文馆正文排版不可用（报告盘图 bundle / Node 不可用）：跑 horosa-skill doctor。",
                          "The sky-state text builder is unavailable (app-charts bundle / Node): run `horosa-skill doctor`."),
                code="sky.render_unavailable",
                details={"error": out.get("error") if isinstance(out, dict) else "no bundle"},
            )
        result: dict[str, Any] = {
            "content": content,
            "date": date, "time": time, "zone": req.zone, "lat": req.lat, "lon": req.lon,
            "summary": f"天象 {date} {time}",
        }
        if isinstance(placed, dict) and placed.get("placeResolution"):
            result["placeResolution"] = placed["placeResolution"]
        if assumptions:
            result["assumptions"] = assumptions
        return result
