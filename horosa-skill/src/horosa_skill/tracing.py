from __future__ import annotations

import json
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
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        self._emit_otlp(event)

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
