"""薄传输层：官方 schema 解析、重试语义（注入 sleep/clock）、错误映射、key 永不出现在异常文本里。"""

from __future__ import annotations

import json

import httpx
import pytest

from horosa_skill.decisions.errors import (
    JevAuthError,
    JevConfigError,
    JevRateLimited,
    JevRequestError,
    JevResponseInvalid,
    JevServerError,
    JevTimeout,
)
from horosa_skill.decisions.jev_http import ENDPOINT, JevHttpClient, RetryPolicy, validate_base_url
from horosa_skill.decisions.questions import Choice, Noul, Score

KEY = "sk-live-9f8e7d6c5b4a39281706f5e4d3c2b1a0"
QUESTIONS = {
    "family": Choice(instructions="Which family?", criteria={"bazi": "八字", "ziwei": "紫微", "unknown": "none"}, abstain="unknown"),
    "urgent": Noul(instructions="Is it urgent?"),
    "severity": Score(instructions="How severe?", criteria=["none", "minor", "major"]),
}
GOOD_BODY = {
    "model": "jev-1.13.0",
    "answers": {
        "family": {"type": "choice", "choice": "bazi", "confidence": 0.93, "probabilities": {"bazi": 0.95, "ziwei": 0.04, "unknown": 0.01}},
        "urgent": {"type": "noul", "noul": 0.12},
        "severity": {"type": "score", "score": 1.4, "confidence": 0.4, "probabilities": {"0": 0.0, "1": 0.6, "2": 0.4}, "legend": {"0": "none", "1": "minor", "2": "major"}},
    },
    "usage": {"input_tokens": 300, "output_tokens": 40},
}


def _client(handler, *, retry: RetryPolicy | None = None, key: str = KEY) -> tuple[JevHttpClient, list[float]]:
    sleeps: list[float] = []
    clock = {"t": 0.0}

    def _sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock["t"] += seconds

    client = JevHttpClient(
        api_key=key,
        transport=httpx.MockTransport(handler),
        retry=retry or RetryPolicy(),
        sleep=_sleep,
        clock=lambda: clock["t"],
        rng=lambda: 0.0,
    )
    return client, sleeps


def test_success_parses_all_three_primitives_and_sends_the_official_body() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=GOOD_BODY, headers={"x-request-id": "req_1"})

    client, sleeps = _client(handler)
    answers = client.decide(state={"user_request": "帮我排八字"}, questions=QUESTIONS, surface="dispatch")
    assert seen["path"] == ENDPOINT and seen["auth"] == f"Bearer {KEY}"
    assert seen["body"]["model"] == "jev-1.13.0" and seen["body"]["state"] == {"user_request": "帮我排八字"}
    assert seen["body"]["questions"]["family"]["type"] == "choice" and seen["body"]["questions"]["family"]["criteria"]["bazi"] == "八字"
    assert answers.model == "jev-1.13.0" and answers.usage == {"input_tokens": 300, "output_tokens": 40}
    assert answers.answers["family"].choice == "bazi" and answers.answers["family"].confidence == 0.93
    assert answers.answers["urgent"].noul == 0.12 and answers.answers["severity"].score == 1.4
    assert sleeps == []


def test_429_then_200_is_retried_with_official_backoff_and_retry_after() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"error": "rate limited"}, headers={"retry-after": "2"})
        return httpx.Response(200, json=GOOD_BODY)

    client, sleeps = _client(handler)
    answers = client.decide(state="x", questions=QUESTIONS)
    assert answers.answers["family"].choice == "bazi" and calls["n"] == 2
    assert sleeps == [2.0], "Retry-After (2s) beats the 0.5s initial backoff"


def test_529_overload_retries_then_raises_rate_limited() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(529, text="overloaded")

    client, sleeps = _client(handler)
    with pytest.raises(JevRateLimited) as excinfo:
        client.decide(state="x", questions=QUESTIONS)
    assert excinfo.value.details["status"] == 529
    assert sleeps == [0.5, 1.0], "max_retries=2 → two backoffs, doubling from 0.5s"


def test_5xx_maps_to_server_error_after_retries_and_4xx_never_retries() -> None:
    calls = {"n": 0}

    def five(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, text="down")

    client, sleeps = _client(five)
    with pytest.raises(JevServerError):
        client.decide(state="x", questions=QUESTIONS)
    assert calls["n"] == 3 and len(sleeps) == 2

    calls["n"] = 0

    def four(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(422, json={"detail": "bad question"})

    client, sleeps = _client(four)
    with pytest.raises(JevRequestError) as excinfo:
        client.decide(state="x", questions=QUESTIONS)
    assert calls["n"] == 1 and sleeps == [] and excinfo.value.code == "jev.request"


def test_401_is_auth_error_without_retry() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid key"})

    client, sleeps = _client(handler)
    with pytest.raises(JevAuthError):
        client.decide(state="x", questions=QUESTIONS)
    assert sleeps == []


def test_timeout_is_retried_then_raised_as_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    client, sleeps = _client(handler)
    with pytest.raises(JevTimeout):
        client.decide(state="x", questions=QUESTIONS)
    assert len(sleeps) == 2


def test_retry_budget_stops_early() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    client, sleeps = _client(handler, retry=RetryPolicy(timeout=0.6))
    with pytest.raises(JevServerError):
        client.decide(state="x", questions=QUESTIONS)
    assert sleeps == [0.5], "second backoff (1.0s) would exceed the 0.6s budget → give up"


def test_invalid_response_shapes_are_rejected_not_trusted() -> None:
    bad_choice = json.loads(json.dumps(GOOD_BODY))
    bad_choice["answers"]["family"]["choice"] = "tarot"  # 不在声明的选项里

    client, _ = _client(lambda request: httpx.Response(200, json=bad_choice))
    with pytest.raises(JevResponseInvalid):
        client.decide(state="x", questions=QUESTIONS)

    bad_prob = json.loads(json.dumps(GOOD_BODY))
    bad_prob["answers"]["urgent"]["noul"] = 1.7
    client, _ = _client(lambda request: httpx.Response(200, json=bad_prob))
    with pytest.raises(JevResponseInvalid):
        client.decide(state="x", questions=QUESTIONS)

    client, _ = _client(lambda request: httpx.Response(200, text="<html>oops</html>"))
    with pytest.raises(JevResponseInvalid):
        client.decide(state="x", questions=QUESTIONS)


def test_key_never_leaks_into_error_text_even_when_the_server_echoes_it() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text=f"bad request for key {KEY} from {request.headers['authorization']}")

    client, _ = _client(handler)
    with pytest.raises(JevRequestError) as excinfo:
        client.decide(state="x", questions=QUESTIONS)
    assert KEY not in str(excinfo.value) and KEY not in repr(excinfo.value.details)
    assert "***" in str(excinfo.value)


def test_base_url_must_be_https_except_loopback() -> None:
    assert validate_base_url("https://api.typesafe.ai/") == "https://api.typesafe.ai"
    assert validate_base_url("http://127.0.0.1:8080") == "http://127.0.0.1:8080"
    with pytest.raises(JevConfigError):
        validate_base_url("http://api.typesafe.ai")
    with pytest.raises(JevConfigError):
        JevHttpClient(api_key="")
