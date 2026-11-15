from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import httpx

from horosa_skill.appendlog import append_line
from horosa_skill.config import Settings


SENSITIVE_PAYLOAD_KEYS = {
    "payload",
    "input",
    "input_normalized",
    "snapshot_text",
    "raw_text",
    "filtered_text",
    "export_text",
}

SENSITIVE_ANSWER_KEYS = {
    "ai_answer",
    "ai_answer_text",
    "ai_answer_structured",
    "user_question",
    "query_text",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# 单条 trace 行的字节上限。超过就只留骨架键 + truncated 标记 —— 一条几 MB 的行既写不原子，
# 也会让整个 .jsonl 变得没法读。
_WRITE_LOCK = threading.Lock()
_MAX_TRACE_LINE_BYTES = 256 * 1024
_TRACE_LINE_KEEP_KEYS = (
    "trace_id", "group_id", "workflow_name", "tool", "started_at", "finished_at",
    "duration_ms", "ok", "error_code", "error_message",
)


class TraceRecorder:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.trace_dir = settings.trace_dir
        self.enabled = settings.trace_enabled and self.trace_dir is not None
        if self.enabled:
            try:
                settings.ensure_dirs()
            except OSError as exc:  # 追踪是诊断用的：目录建不出来只是没有追踪记录，不能让服务起不来（记忆库同理）
                logging.getLogger(__name__).debug("tracing disabled: %s", exc)
                self.enabled = False

    def new_trace_id(self) -> str:
        return uuid.uuid4().hex

    def new_group_id(self) -> str:
        return uuid.uuid4().hex

    def latest_trace_files(self, *, limit: int = 5) -> list[Path]:
        if not self.trace_dir or not self.trace_dir.exists():
            return []
        return sorted(self.trace_dir.glob("*.jsonl"), reverse=True)[:limit]

    def read_latest(self, *, limit: int = 50) -> list[dict[str, Any]]:
        files = self.latest_trace_files(limit=1)
        if not files:
            return []
        rows: list[dict[str, Any]] = []
        # errors="replace"：Windows 上并发追加可能把一个多字节序列撕成两半（本模块顶部如实记着那条边界），
        # 整文件 strict 解码会在那一行之前就抛 UnicodeDecodeError，让下面逐行的 JSONDecodeError 兜底永远轮不到。
        for line in files[0].read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows[-limit:]

    @contextmanager
    def span(
        self,
        *,
        workflow_name: str,
        trace_id: str | None = None,
        group_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        span_trace_id = trace_id or self.new_trace_id()
        span_group_id = group_id or span_trace_id
        started_at = utc_now_iso()
        start_clock = time.perf_counter()
        envelope: dict[str, Any] = {
            "trace_id": span_trace_id,
            "group_id": span_group_id,
            "workflow_name": workflow_name,
            "started_at": started_at,
            "success": True,
            "error_code": None,
            "error_message": None,
        }
        if metadata:
            envelope.update(metadata)
        try:
            yield envelope
        except Exception as exc:
            envelope["success"] = False
            envelope["error_message"] = str(exc)
            raise
        finally:
            envelope["finished_at"] = utc_now_iso()
            envelope["duration_ms"] = round((time.perf_counter() - start_clock) * 1000, 3)
            self._write_event(self._sanitize(envelope))

    def _write_event(self, event: dict[str, Any]) -> None:
        if not self.enabled or self.trace_dir is None:
            return
        target = self.trace_dir / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"
        try:
            # 一次追加完整一行，跨进程原子（多个 MCP 会话共写同一天的 .jsonl）：POSIX 靠 O_APPEND，
            # Windows 靠只申请 FILE_APPEND_DATA 的原生句柄——CRT 的 O_APPEND 是模拟的，「定位 + 写」会互相盖
            # （v0.43.0 CI：4 进程 × 60 次写剩 191/213 行；v0.46.1-dev 起换原生追加，见 appendlog.py）。
            #
            # 另一条各平台一致的旧缺陷是没有行长上限：开了 HOROSA_TRACE_CAPTURE_PAYLOADS
            # 之后一个几 MB 的事件会被整条写进去，.jsonl 迅速膨胀到没法读。下面的截断补上这一条。
            line = (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
            if len(line) > _MAX_TRACE_LINE_BYTES:
                # 超大事件（巨型 payload）截断并打标，绝不静默丢：截断后仍是合法 JSON 行。
                event = {
                    **{k: v for k, v in event.items() if k in _TRACE_LINE_KEEP_KEYS},
                    "truncated": True,
                    "original_bytes": len(line),
                }
                line = (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
            # 进程内仍串行化（成本可忽略）：原生追加已让线程 / 进程间互不覆盖，这把锁保住同进程内的行序。
            with _WRITE_LOCK:
                self._append_line(target, line)
        except Exception:
            # Best-effort local trace recorder: a write failure (unwritable/deleted dir, disk
            # full, serialization error) must never crash or mask the operation being traced.
            pass
        self._emit_otlp(event)

    def _append_line(self, target: Path, line: bytes) -> None:
        """把一整行追加到 target。调用方必须持有 `_WRITE_LOCK`。"""
        append_line(target, line)

    def _emit_otlp(self, event: dict[str, Any]) -> None:
        """审计 PF-06：外发改白名单 + 真 OTLP/HTTP JSON + 有界后台队列。
        以前把整条本地事件（出生时刻、用户写的地名、家目录路径）同步 POST 出去，每次调用最多卡 2 秒，格式也不是 OTLP。"""
        endpoint = self.settings.trace_otlp_endpoint
        if not endpoint:
            return
        _OUTBOUND.submit(endpoint, otlp_payload(event))

    def _sanitize(self, value: Any, *, key: str | None = None) -> Any:
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            for one_key, one_value in value.items():
                if one_key in SENSITIVE_PAYLOAD_KEYS and not self.settings.trace_capture_payloads:
                    result[one_key] = "<redacted>"
                    continue
                if one_key == "summary" and not self.settings.trace_capture_payloads and one_value:
                    # 技法结果的 summary 带着盘面要点（「日期：1990-05-17 14:30」「种子:张三丰|…」），以前原文落 trace（审计 O-06）：
                    # 载荷与正文都脱敏了，它是漏网的那份。只记行数。
                    count = len(one_value) if isinstance(one_value, list) else 1
                    result[one_key] = f"<redacted: {count} line(s)>"
                    continue
                if one_key in SENSITIVE_ANSWER_KEYS and not self.settings.trace_capture_ai_answers:
                    result[one_key] = "<redacted>"
                    continue
                result[one_key] = self._sanitize(one_value, key=one_key)
            return result
        if isinstance(value, list):
            return [self._sanitize(item, key=key) for item in value]
        return value


# ---- 外发（审计 PF-06）-----------------------------------------------------------------------------------------
# 只有这些键离开本机；其余（载荷、summary、错误原文、路径）只进本地 .jsonl。
OUTBOUND_KEYS: tuple[str, ...] = ("trace_id", "group_id", "workflow_name", "tool", "tool_name", "ok", "error_code",
                                  "duration_ms", "started_at", "finished_at")


def outbound_view(event: dict[str, Any]) -> dict[str, Any]:
    from horosa_skill import __version__

    return {**{key: event[key] for key in OUTBOUND_KEYS if key in event and not isinstance(event[key], (dict, list))},
            "version": __version__}


def _unix_nanos(text: Any) -> int:
    try:
        return int(datetime.fromisoformat(str(text)).timestamp() * 1_000_000_000)
    except (TypeError, ValueError):
        return int(time.time() * 1_000_000_000)


def otlp_payload(event: dict[str, Any]) -> dict[str, Any]:
    """一条事件 → OTLP/HTTP JSON 的 ExportTraceServiceRequest（只带 outbound_view 的键）。"""
    view = outbound_view(event)
    trace_hex = uuid.UUID(str(view.get("trace_id"))).hex if _is_uuid(view.get("trace_id")) else uuid.uuid4().hex
    attributes = [{"key": f"horosa.{key}", "value": ({"boolValue": value} if isinstance(value, bool) else
                                                     {"doubleValue": value} if isinstance(value, float) else
                                                     {"intValue": str(value)} if isinstance(value, int) else {"stringValue": str(value)})}
                  for key, value in view.items() if key not in ("trace_id", "started_at", "finished_at")]
    span = {
        "traceId": trace_hex, "spanId": uuid.uuid4().hex[:16], "name": str(view.get("workflow_name") or "horosa"),
        "kind": 1, "startTimeUnixNano": str(_unix_nanos(view.get("started_at"))), "endTimeUnixNano": str(_unix_nanos(view.get("finished_at"))),
        "attributes": attributes, "status": {"code": 1 if view.get("ok", True) is not False and not view.get("error_code") else 2},
    }
    return {"resourceSpans": [{
        "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "horosa-skill"}}]},
        "scopeSpans": [{"scope": {"name": "horosa-skill", "version": str(view.get("version"))}, "spans": [span]}],
    }]}


def _is_uuid(value: Any) -> bool:
    try:
        uuid.UUID(str(value))
    except (TypeError, ValueError):
        return False
    return True


class _OutboundQueue:
    """有界后台队列：调用方从不等网络；满了就丢（计数），进程退出不等待（daemon 线程）。"""

    def __init__(self, maxsize: int = 256) -> None:
        import queue

        self._queue: "queue.Queue[tuple[str, dict[str, Any]]]" = queue.Queue(maxsize=maxsize)
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self.dropped = 0
        self.sent = 0

    def submit(self, endpoint: str, payload: dict[str, Any]) -> None:
        import queue

        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._run, name="horosa-trace-export", daemon=True)
                self._thread.start()
        try:
            self._queue.put_nowait((endpoint, payload))
        except queue.Full:
            self.dropped += 1

    def _run(self) -> None:
        while True:
            endpoint, payload = self._queue.get()
            try:
                with httpx.Client(timeout=2.0) as client:
                    client.post(endpoint, json=payload)
                self.sent += 1
            except Exception:  # noqa: BLE001 — 外发是可选诊断：失败只是少一条
                pass
            finally:
                self._queue.task_done()

    def join(self, timeout: float = 5.0) -> None:
        """测试用：等队列清空（有上限）。"""
        deadline = time.monotonic() + timeout
        while self._queue.unfinished_tasks and time.monotonic() < deadline:
            time.sleep(0.01)


_OUTBOUND = _OutboundQueue()
