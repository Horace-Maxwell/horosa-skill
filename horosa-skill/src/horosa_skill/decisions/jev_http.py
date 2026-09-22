"""TypeSafe `/v1/systemone` 的薄传输层（本仓 httpx，零新依赖）。

为什么不直接用官方 `typesafe-sdk`：它 0.7.x 一天一版、依赖 `httpx2`/tenacity，而本仓所有外部调用都是
「可注入传输 + 子类桩」的离线可测形状（`FakeClient` 惯例）。语义照抄官方 RetryPolicy：2 次重试、0.5 s 起
倍增、封顶 5 s、抖动 0.25、总预算 30 s、重试 408/429/5xx（含 529 过载）、尊重 Retry-After（封顶 60 s）。
同参对拍测试保证两边答案等价；SDK 到 1.0 再评估切默认。

安全：key 只在构造时读入并持有；任何异常消息经 `_scrub` 去掉 key；`base_url` 必须 https（回环除外）。
"""

from __future__ import annotations

import json
import random
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx

from horosa_skill import __version__
from horosa_skill.decisions.errors import (
    JevAuthError,
    JevConfigError,
    JevConnectionError,
    JevError,
    JevRateLimited,
    JevRequestError,
    JevResponseInvalid,
    JevServerError,
    JevTimeout,
)
from horosa_skill.decisions.questions import Answers, Question, parse_answers

DEFAULT_BASE_URL = "https://api.typesafe.ai"
DEFAULT_MODEL = "jev-1.13.0"
ENDPOINT = "/v1/systemone"
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 2
    backoff_initial: float = 0.5
    backoff_max: float = 5.0
    backoff_jitter: float = 0.25
    timeout: float = 30.0  # 整次调用（含重试）的总预算，秒
    http_statuses: frozenset[int] = field(default_factory=lambda: frozenset({408, 429} | set(range(500, 600))))
    respect_retry_after: bool = True
    retry_after_cap: float = 60.0


def validate_base_url(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme == "https" and parsed.netloc:
        return str(url).strip().rstrip("/")
    if parsed.scheme == "http" and parsed.hostname in _LOOPBACK_HOSTS:
        return str(url).strip().rstrip("/")
    raise JevConfigError(f"HOROSA_JEV_BASE_URL 必须是 https（当前 scheme {parsed.scheme or 'none'!r}）/ HOROSA_JEV_BASE_URL must be https (got scheme {parsed.scheme or 'none'!r})")


class JevHttpClient:
    """`decide(state, questions)` → `Answers`。构造即校验 key/URL，不发网络请求。"""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout_s: float = 3.0,
        retry: RetryPolicy | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        rng: Callable[[], float] = random.random,
    ) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise JevConfigError("缺少 TypeSafe API key（HOROSA_JEV_API_KEY）/ TypeSafe API key missing (HOROSA_JEV_API_KEY)")
        self._key = api_key.strip()
        self.base_url = validate_base_url(base_url)
        self.model = str(model or DEFAULT_MODEL)
        self.timeout_s = float(timeout_s)
        self.retry = retry or RetryPolicy()
        self._sleep = sleep
        self._clock = clock
        self._rng = rng
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout_s,
            transport=transport,
            headers={
                "Authorization": f"Bearer {self._key}",
                "Content-Type": "application/json",
                "User-Agent": f"horosa-skill/{__version__} decisions",
            },
        )

    def close(self) -> None:
        self._client.close()

    # ---- helpers -------------------------------------------------------------------------------
    def _scrub(self, text: Any) -> str:
        return str(text).replace(self._key, "***")

    def _map_status(self, response: httpx.Response) -> tuple[JevError, bool]:
        status = response.status_code
        snippet = self._scrub(response.text[:200]).replace("\n", " ")
        details = {"status": status, "request_id": response.headers.get("x-request-id")}
        message = f"TypeSafe Jev HTTP {status}: {snippet}"
        if status in (401, 403):
            return JevAuthError(message, details=details), False
        if status in (429, 529):
            return JevRateLimited(message, details=details), True
        if status >= 500 or status == 408:
            return JevServerError(message, details=details), True
        return JevRequestError(message, details=details), False

    @staticmethod
    def _retry_after(response: httpx.Response | None) -> float | None:
        if response is None:
            return None
        raw = response.headers.get("retry-after")
        if not raw:
            return None
        try:
            return max(0.0, float(raw))
        except ValueError:
            return None

    # ---- main ----------------------------------------------------------------------------------
    def decide(self, *, state: Any, questions: Mapping[str, Question], surface: str = "") -> Answers:
        raw, latency_ms = self.decide_raw(state=state, questions=questions, surface=surface)
        try:
            return parse_answers(questions, raw, latency_ms=latency_ms)
        except ValueError as exc:
            raise JevResponseInvalid(f"TypeSafe Jev 响应不合规：{self._scrub(exc)} / TypeSafe Jev response invalid: {self._scrub(exc)}") from exc

    def decide_raw(self, *, state: Any, questions: Mapping[str, Question], surface: str = "") -> tuple[dict[str, Any], int]:
        """同 `decide`，但返回**未解析**的官方响应体 + 延迟（评测录制回放用：回放必须过同一套解析）。"""
        if not questions:
            raise JevConfigError("没有要问的问题 / no questions to ask")
        body = {
            "model": self.model,
            "state": state,
            "questions": {qid: spec.to_json() for qid, spec in questions.items()},
        }
        deadline = self._clock() + self.retry.timeout
        attempt = 0
        while True:
            started = self._clock()
            error: JevError
            retryable = False
            retry_after: float | None = None
            try:
                response = self._client.post(ENDPOINT, json=body)
            except httpx.TimeoutException as exc:
                error = JevTimeout(f"TypeSafe Jev timed out after {self.timeout_s:g}s ({self._scrub(exc.__class__.__name__)})")
                retryable = True
            except httpx.TransportError as exc:
                error = JevConnectionError(f"TypeSafe Jev connection failed: {self._scrub(exc.__class__.__name__)}")
                retryable = True
            else:
                if 200 <= response.status_code < 300:
                    latency_ms = int((self._clock() - started) * 1000)
                    try:
                        payload = response.json()
                    except (ValueError, json.JSONDecodeError) as exc:
                        raise JevResponseInvalid(f"TypeSafe Jev 返回的不是 JSON：{self._scrub(response.text[:120])} / TypeSafe Jev returned non-JSON: {self._scrub(response.text[:120])}") from exc
                    if not isinstance(payload, dict):
                        raise JevResponseInvalid("TypeSafe Jev 响应不是 JSON 对象 / TypeSafe Jev response is not a JSON object")
                    return payload, latency_ms
                error, retryable = self._map_status(response)
                retry_after = self._retry_after(response)
            if not retryable or attempt >= self.retry.max_retries:
                raise error
            delay = min(self.retry.backoff_initial * (2**attempt), self.retry.backoff_max)
            delay -= delay * self.retry.backoff_jitter * self._rng()
            if self.retry.respect_retry_after and retry_after is not None:
                delay = max(delay, min(retry_after, self.retry.retry_after_cap))
            if self._clock() + delay > deadline:
                raise error
            self._sleep(delay)
            attempt += 1
