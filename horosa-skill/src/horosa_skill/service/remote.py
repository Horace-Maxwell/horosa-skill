"""远端调用层（RemoteMixin）：_call_remote、Java 冷却与错误、HTTP 200 里的失败信封识别。"""
from __future__ import annotations

import os
import time
from typing import Any

from horosa_skill.errors import ToolTransportError, bilingual
from horosa_skill.exports import parse_export_content
from horosa_skill.service.endpoints import (
    _PYTHON_CHART_ENDPOINTS,
    _chart_server_endpoint,
    _java_chart_payload_candidates,
)


class RemoteMixin:
    def _unwrap_result(self, payload: Any) -> Any:
        current = payload
        for _ in range(4):
            if not isinstance(current, dict):
                return current
            if isinstance(current.get("Result"), dict):
                current = current["Result"]
                continue
            if isinstance(current.get("result"), dict):
                current = current["result"]
                continue
            return current
        return current

    def _java_cooldown_remaining(self) -> float:
        # getattr: test stubs without the method. A broken state file is already absorbed inside the manager
        # (`load_runtime_state` → None, bad timestamp → 0.0), so no broad except here.
        probe = getattr(self.runtime_manager, "java_backend_cooldown_remaining", None)
        return float(probe()) if callable(probe) else 0.0

    @staticmethod
    def _java_unavailable_error(endpoint: str, remaining: float) -> ToolTransportError:
        return ToolTransportError(
            "Horosa Java backend (:9999) is unavailable; the runtime is running degraded on the chart service only.",
            code="runtime.java_backend_unavailable",
            details={
                "endpoint": endpoint,
                "runtime_target": "java_backend",
                "retry_after_seconds": round(max(0.0, remaining), 1),
                "hint": (
                    "Chart-side techniques (西占 chart 族/推运/三式 ken/神数/地占/塔罗) still work. Java-side ones "
                    "(nongli/bazi/ziwei/liureng and 占时 casts) fail fast until the backend recovers; it is retried "
                    "automatically after the cooldown (HOROSA_RUNTIME_JAVA_RETRY_COOLDOWN_SECONDS, default 120s). "
                    "Run `horosa-skill doctor` for the captured Java boot error."
                ),
                "next_action": "run_doctor_or_retry_after_cooldown",
            },
        )

    @staticmethod
    def _runtime_call_wait_seconds() -> float:
        """一次工具调用**最多**为「等 runtime 起来」阻塞多久（秒）。

        🔴 旧行为是一直等到启动器自己超时（runtime_start_timeout_seconds，首次运行含解压 + CDS
        训练，实测 300–900 秒），全都发生在**一次 MCP 请求内部**。Codex 的 tool_timeout_sec 默认
        60 秒，其它客户端各有默认 —— 用户看到的是「工具超时/无响应」，而 runtime 其实正常启动中。
        默认 5 秒：够覆盖「已经起好了、只是探针慢一拍」，不够的场合改回 runtime.starting 让调用方重试。
        """
        raw = os.environ.get("HOROSA_RUNTIME_CALL_WAIT_SECONDS", "5").strip()
        try:
            value = float(raw)
        except ValueError:
            return 5.0
        return max(0.0, value)

    @staticmethod
    def _runtime_starting_error(endpoint: str, started: dict[str, Any]) -> ToolTransportError:
        retry_after = started.get("retry_after_seconds") or 5
        return ToolTransportError(
            "本机 Horosa runtime 正在启动，尚未就绪。",
            code="runtime.starting",
            details={
                "endpoint": endpoint,
                "retry_after_seconds": retry_after,
                "elapsed_seconds": started.get("elapsed_seconds"),
                "budget_seconds": started.get("budget_seconds"),
                "cap_seconds": started.get("cap_seconds"),
                "first_start": started.get("first_start"),
                "launcher_log": started.get("launcher_log"),
                "next_action": (
                    f"等 {retry_after} 秒后重试**同一个调用**（参数不用改）。"
                    "连续三次仍是 starting 就跑 `horosa-skill runtime status` 看启动器日志。"
                ),
            },
        )

    def _call_remote(self, endpoint: str, payload: dict[str, Any], *, backend: str | None = None) -> dict[str, Any]:
        # backend="java"：同名路由两端都有、而本次要的是 Java 聚合层的附加字段时显式指定（例：/jieqi/year 的
        # Java 层给 jieqi24 逐节气补 bazi.fourColumns，Python 端无此字段——上游页面的种子请求走的就是 Java）。
        if backend not in (None, "java"):
            raise ValueError(bilingual(f"未知的后端覆写：{backend!r}", f"unknown backend override: {backend!r}"))
        use_chart_server = endpoint in _PYTHON_CHART_ENDPOINTS and backend != "java"
        client = self.chart_client if use_chart_server else self.client
        # /healthz（批 I-6）：chart 服务的真就绪探针（ok/warm）；老 runtime 无此路由时 404 仍算「服务在」。
        probe_endpoint = "/healthz" if use_chart_server else "/common/time"
        runtime_ready = self._chart_runtime_ready if use_chart_server else self._java_runtime_ready
        if not runtime_ready and not client.probe(probe_endpoint):
            # 分后端就绪（v0.36.0 A5）：Java 在冷却期内快速失败，不触发会先杀健康 chart 服务的全量重启；
            # chart 端点不受 Java 状态影响。
            if not use_chart_server:
                remaining = self._java_cooldown_remaining()
                if remaining > 0:
                    raise self._java_unavailable_error(endpoint, remaining)
            started = self.runtime_manager.start_local_services(
                wait_seconds=self._runtime_call_wait_seconds()
            )
            if isinstance(started, dict) and started.get("starting"):
                raise self._runtime_starting_error(endpoint, started)
            if not use_chart_server and isinstance(started, dict) and started.get("degraded"):
                raise self._java_unavailable_error(endpoint, self._java_cooldown_remaining())
        remote_endpoint = _chart_server_endpoint(endpoint) if use_chart_server else endpoint
        connection_retry_used = False
        data: dict[str, Any] | None = None
        while True:
            candidate_payloads = _java_chart_payload_candidates(endpoint, payload)
            param_errors: list[tuple[dict[str, Any], ToolTransportError]] = []
            # 🔴 「调用成功」必须单独记：后端合法地回 JSON `null`（玄史 get_figure 等查无此 slug 即回 null）时
            # data 仍是 None——旧循环拿 `data is not None` 当成功判据，于是对 null 无限重发、每轮新建 TLS 上下文，
            # 进程 100% CPU 挂死并持续打后端（sync311 F13 实测：旧映射下 figure 恒发错键 → 恒 null → 恒挂）。
            call_succeeded = False
            for remote_payload in candidate_payloads:
                try:
                    data = client.call(remote_endpoint, remote_payload)
                    call_succeeded = True
                    break
                except ToolTransportError as exc:
                    body = str(exc.details.get("body", ""))
                    is_param_error = exc.code == "tool.backend_param_error" or (
                        exc.code == "transport.http_error" and "200001" in body and "param error" in body
                    )
                    if not is_param_error:
                        if exc.code == "transport.connection_error" and not connection_retry_used:
                            connection_retry_used = True
                            if not use_chart_server and self._java_cooldown_remaining() > 0:
                                raise self._java_unavailable_error(endpoint, self._java_cooldown_remaining()) from exc
                            restarted = self.runtime_manager.start_local_services(
                                wait_seconds=self._runtime_call_wait_seconds()
                            )
                            if isinstance(restarted, dict) and restarted.get("starting"):
                                raise self._runtime_starting_error(endpoint, restarted) from exc
                            # start_local_services 已等到端口可达才返回；这一秒留给「already_running 但刚拒绝过连接」
                            # 的竞态（进程在、监听还没恢复）。没测过去掉它的后果之前不动。
                            time.sleep(1.0)
                            break
                        raise
                    param_errors.append((remote_payload, exc))
            else:
                remote_payload, exc = param_errors[-1]
                payload_preview = {
                    key: remote_payload.get(key)
                    for key in ("date", "time", "zone", "lat", "lon", "gpsLat", "gpsLon", "dirZone", "dirLat", "dirLon")
                    if key in remote_payload
                }
                attempted_payloads = [
                    {
                        key: attempted.get(key)
                        for key in ("date", "time", "zone", "lat", "lon", "gpsLat", "gpsLon", "dirZone", "dirLat", "dirLon")
                        if key in attempted
                    }
                    for attempted, _error in param_errors
                ]
                raise ToolTransportError(
                    "Horosa backend rejected the birth parameters.",
                    code="tool.backend_param_error",
                    details={
                        **exc.details,
                        "endpoint": endpoint,
                        "runtime_target": "python_chart" if use_chart_server else "java_backend",
                        "payload_preview": payload_preview,
                        "attempted_payloads": attempted_payloads,
                        "hint": (
                            "Use timezone like `+08:00` and compact coordinates like `31n13` / `121e28`, or send decimal "
                            "coordinates so Horosa Skill can normalize them automatically."
                        ),
                    },
                ) from exc
            if call_succeeded:
                break
            continue
        if use_chart_server:
            self._chart_runtime_ready = True
        else:
            self._java_runtime_ready = True
        unwrapped = self._unwrap_result(data)
        if not isinstance(unwrapped, dict):
            # 玄史检索端点（/xuanshi/search、/xuanshi/timeline 等）按 jsonpickle 直吐**裸数组**——
            # 对这族端点数组是合法形状，包一层交给调用方；其余端点维持 dict 硬约束（形状漂移要炸出来）。
            if endpoint.startswith("/xuanshi/") and isinstance(unwrapped, list):
                return {"items": unwrapped}
            # 详情端点查无此条（slug/id 不存在）回 JSON null：是合法的「零命中」，不是形状漂移。
            if endpoint.startswith("/xuanshi/") and unwrapped is None:
                return {"items": [], "total": 0}
            raise ToolTransportError(
                "Horosa endpoint returned a non-object result payload.",
                code="transport.invalid_result_shape",
                details={"endpoint": endpoint, "runtime_target": "python_chart" if use_chart_server else "java_backend"},
            )
        return unwrapped

    def _augment_export_payload(self, *, technique: str, snapshot_text: str | None) -> dict[str, Any] | None:
        if not snapshot_text:
            return None
        try:
            return parse_export_content(technique=technique, content=snapshot_text)
        except ValueError:
            return None

    def _require_ken_pan(self, ken_response: Any, *, engine: str, endpoint: str) -> None:
        """Fail loudly when the ken backend did not actually compute a pan.

        The ken chart endpoints (`/qimen/pan`, `/taiyi/pan`, `/jinkou/pan`) return HTTP 200
        even on failure, with an envelope like ``{"ResultCode": -1, "Result": "<engine> ...
        failed"}`` (a string ``Result``). That envelope is still a ``dict``, so ``_call_remote``
        does not treat it as a transport error. If we forwarded it to the JS layer, the formatter
        would silently fall back to its *local* scaffold compute — producing a chart that does
        NOT match 星阙. ken is the sole compute authority for these techniques, so a failed ken
        response must surface as a loud error instead of a silent local-engine fallback.
        """
        if isinstance(ken_response, dict) and ken_response.get("source") == engine:
            return
        detail_result = ken_response.get("Result") if isinstance(ken_response, dict) else ken_response
        raise ToolTransportError(
            f"Horosa ken ({engine}) engine did not return a valid pan.",
            code="tool.ken_compute_failed",
            details={
                "endpoint": endpoint,
                "engine": engine,
                "ken_result": detail_result,
                "hint": (
                    f"{engine} is the sole compute authority for this technique; the chart "
                    "service raised on these parameters (it returns HTTP 200 with a failure "
                    "envelope). Check the chart-service log and the input fields — the skill "
                    "will not silently fall back to a local-engine chart."
                ),
            },
        )

    # --- 天星择日 / 奇门择日（上游 v3.7.0 / v3.7.1）------------------------------------------

    def _require_electionscan_ok(self, result: Any, *, endpoint: str) -> dict[str, Any]:
        """Fail loudly when /electionscan/scan returned a failure envelope.

        Same family as `_require_ken_pan` (AGENTS §4「HTTP 200 也回失败信封，永不信状态码」):
        the endpoint wraps errors as ``{"ResultCode": -1, "Result": {"err": …, "detail": …}}``,
        and `_call_remote` only inspects a **top-level** `err`, so the unwrapped `{"err": …}` comes
        back with no exception. Without this guard a `span_too_large` / `invalid_conditions` would
        silently degrade into "zero hits" — a plausible-looking empty search that is actually a
        rejected request.
        """
        if isinstance(result, dict) and not result.get("err"):
            return result
        detail = result if not isinstance(result, dict) else {"err": result.get("err"), "detail": result.get("detail")}
        raise ToolTransportError(
            "Horosa 征象搜索端点未返回结果。",
            code="tool.electionscan_failed",
            details={
                "endpoint": endpoint,
                "scan_error": detail,
                "hint": (
                    "invalid_conditions=条件树不合法（叶子 params 见 agent_guidance）；"
                    "span_too_large=单次请求超 93 天（skill 已按月切分，出现即切分逻辑有误）。"
                ),
            },
        )

    # ── 七政择日动盘（批 I-1b，/qizhengelection/*）────────────────────────────────

    def _require_qizhengelection_ok(self, result: Any, *, endpoint: str, expect: str) -> Any:
        """信封判读（同 _require_electionscan_ok 家族，HTTP 200 也回失败信封）。

        pan 的 Result 是 dict → `_unwrap_result` 已剥出内层；eclipses/azimuthsearch 的 Result
        是**数组** → 信封原样返回（unwrap 只剥 dict）。失败时 Result 是字符串（"… failed"）。
        """
        if isinstance(result, dict) and "ResultCode" in result:
            if result.get("ResultCode") == 0:
                inner = result.get("Result")
                if expect == "list" and isinstance(inner, list):
                    return inner
                if expect == "dict" and isinstance(inner, dict):
                    return inner
            raise ToolTransportError(
                "七政择日端点返回失败信封。",
                code="tool.qizhengelection_failed",
                details={"endpoint": endpoint, "error": result.get("Result")},
            )
        if expect == "dict" and isinstance(result, dict):
            return result
        raise ToolTransportError(
            "七政择日端点返回了意外形状。",
            code="tool.qizhengelection_failed",
            details={"endpoint": endpoint, "shape": type(result).__name__},
        )
