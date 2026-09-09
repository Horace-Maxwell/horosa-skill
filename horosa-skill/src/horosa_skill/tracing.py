from __future__ import annotations

import json
import os
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import httpx

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
            settings.ensure_dirs()

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
        for line in files[0].read_text(encoding="utf-8").splitlines():
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
            # 一次写完整行 + O_APPEND。**跨进程原子性只在 POSIX 上成立。**
            #
            # 两次被现实纠正，都记在这里：
            # ① 「旧写法（TextIOWrapper 追加）会撕行」—— 本机 (macOS/APFS) **复现不了**：
            #    8 进程 × 520 KB 行并发追加，250 行全部可解析。它安全靠的是 CPython 的实现细节
            #    （close 时把整行交给一次 raw.write），而 O_APPEND 让那次 write(2) 原子。
            #    改成显式的 O_APPEND + 单次写不是「修了一个 bug」，是把「碰巧成立」变成「写明成立」。
            # ② 「那 O_APPEND 就到处成立了吧」—— **Windows 上不成立**，CI 当场打脸：
            #    4 进程 × 60 次写只剩 191/213 行（每次跑还不一样）。Windows 的 O_APPEND 由 CRT
            #    模拟，「定位到末尾 + 写」不是一个原子操作，并发追加会互相盖。
            #    trace 是尽力而为的本地记录器，为它上跨进程锁不划算；所以这里如实承认边界，
            #    对应的守卫用例也只在 POSIX 上断言跨进程完整性（见 test_runtime_lifecycle）。
            #
            # 真正**能演示**、且各平台一致的旧缺陷是没有行长上限：开了 HOROSA_TRACE_CAPTURE_PAYLOADS
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
            # 🔴 进程内串行化。Windows 上**线程之间**就会丢行（CI 实测 6 线程 × 40 次写只剩 190 行）：
            # 每次 _write_event 各开一个 fd，而 Windows 的 O_APPEND 由 CRT 模拟，
            # 「定位到末尾 + 写」不是一个原子操作，两个 fd 各按自己的偏移写就互相盖。
            # 一把模块级锁只挡同进程的并发，成本可忽略；跨进程的边界如实留在下面的说明里。
            with _WRITE_LOCK:
                self._append_line(target, line)
        except Exception:
            # Best-effort local trace recorder: a write failure (unwritable/deleted dir, disk
            # full, serialization error) must never crash or mask the operation being traced.
            pass
        self._emit_otlp(event)

    def _append_line(self, target: Path, line: bytes) -> None:
        """把一整行追加到 target。调用方必须持有 `_WRITE_LOCK`。"""
        fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            # 🔴 `os.write` **可以短写**，返回值必须看。不看的后果不是「少几个字节」，而是
            # 那一行没有结尾的 \n —— 下一条记录接在它后面，两条并成一行，整行解析不了。
            # 症状是「行数比写入次数少」，而不是显眼的报错。
            written = 0
            while written < len(line):
                written += os.write(fd, line[written:])
        finally:
            os.close(fd)

    def _emit_otlp(self, event: dict[str, Any]) -> None:
        endpoint = self.settings.trace_otlp_endpoint
        if not endpoint:
            return
        try:
            with httpx.Client(timeout=2.0) as client:
                client.post(endpoint, json=event)
        except Exception:
            return

    def _sanitize(self, value: Any, *, key: str | None = None) -> Any:
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            for one_key, one_value in value.items():
                if one_key in SENSITIVE_PAYLOAD_KEYS and not self.settings.trace_capture_payloads:
                    result[one_key] = "<redacted>"
                    continue
                if one_key in SENSITIVE_ANSWER_KEYS and not self.settings.trace_capture_ai_answers:
                    result[one_key] = "<redacted>"
                    continue
                result[one_key] = self._sanitize(one_value, key=one_key)
            return result
        if isinstance(value, list):
            return [self._sanitize(item, key=key) for item in value]
        return value
