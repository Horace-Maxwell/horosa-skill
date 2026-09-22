"""决策层编排：面开关 → 缓存 → 熔断 → 调用 → 账本 → provenance 记录。

`ask()` 永不抛异常：失败变成 `Outcome(ok=False, error_code=…)` 并经调用方注入的 `degrade` 回调
进 `envelope.warnings`（一次熔断窗只报一次）。采纳与否由各面的代码决定并写回 `record`。
"""

from __future__ import annotations

import contextlib
import contextvars
import hashlib
import json
import logging
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from horosa_skill.decisions.errors import JevError
from horosa_skill.decisions.ledger import LEDGER_FILENAME, DecisionLedger
from horosa_skill.decisions.policy import Policy, enforce_allowed, load_policy, load_thresholds, resolve_tau
from horosa_skill.decisions.questions import Answers, Question
from horosa_skill.decisions.redact import Redaction

logger = logging.getLogger(__name__)

# 一次 run_tool / dispatch 的决策记录作用域（与 service._DEGRADE_NOTES 同款；嵌套冒泡到外层）。
_DECISION_RECORDS: contextvars.ContextVar[list[dict[str, Any]] | None] = contextvars.ContextVar(
    "horosa_decision_records", default=None
)


@contextlib.contextmanager
def decision_records() -> Iterator[list[dict[str, Any]]]:
    parent = _DECISION_RECORDS.get()
    records: list[dict[str, Any]] = []
    token = _DECISION_RECORDS.set(records)
    try:
        yield records
    finally:
        _DECISION_RECORDS.reset(token)
        if parent is not None:
            parent.extend(item for item in records if item not in parent)


def note_decision(record: dict[str, Any]) -> None:
    records = _DECISION_RECORDS.get()
    if records is not None and record not in records:
        records.append(record)


def current_decision_records() -> list[dict[str, Any]]:
    """当前作用域里已落的决策记录（technique_card 挂 `decisions[]` 用）。"""
    records = _DECISION_RECORDS.get()
    return [dict(item) for item in records] if records else []


class DecisionProvider:
    """结构化协议：`decide(state=…, questions=…, surface=…) -> Answers`（真传输 / 桩 / 回放都实现它）。"""

    def decide(self, *, state: Any, questions: Mapping[str, Question], surface: str = "") -> Answers:  # pragma: no cover - protocol
        raise NotImplementedError


@dataclass
class Outcome:
    ok: bool
    surface: str
    mode: str  # off | shadow | enforce
    answers: Answers | None = None
    error_code: str | None = None
    note: str | None = None
    latency_ms: int = 0
    cached: bool = False
    tau: float = 0.7
    record: dict[str, Any] = field(default_factory=dict)

    @property
    def enforced(self) -> bool:
        return self.ok and self.mode == "enforce"


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


class DecisionLayer:
    def __init__(
        self,
        policy: Policy,
        provider: DecisionProvider | Callable[[], DecisionProvider],
        *,
        ledger: DecisionLedger | None = None,
        degrade: Callable[[str], Any] | None = None,
        thresholds: Mapping[str, Any] | None = None,
        clock: Callable[[], float] = time.monotonic,
        cache_ttl_s: float = 120.0,
        breaker_threshold: int = 3,
        breaker_cooldown_s: float = 60.0,
    ) -> None:
        self.policy = policy
        self._provider_or_factory = provider
        self._provider: DecisionProvider | None = provider if not callable(provider) or hasattr(provider, "decide") else None
        self.ledger = ledger
        self._degrade = degrade
        self.thresholds = dict(thresholds) if thresholds else None
        self._clock = clock
        self._cache_ttl = float(cache_ttl_s)
        self._cache: dict[str, tuple[float, Answers]] = {}
        self._breaker_threshold = int(breaker_threshold)
        self._breaker_cooldown = float(breaker_cooldown_s)
        self._failures = 0
        self._breaker_open_until = 0.0
        self._breaker_notified = False
        self._lock = threading.Lock()

    # ---- construction ----------------------------------------------------------------------------
    @classmethod
    def from_settings(
        cls,
        settings: Any,
        *,
        degrade: Callable[[str], Any] | None = None,
        provider: DecisionProvider | None = None,
        env: Mapping[str, str] | None = None,
    ) -> DecisionLayer | None:
        """`HOROSA_JEV=off`（或配置无效）→ None：零对象、零 import、零字节。"""
        policy = load_policy(env)
        if not policy.enabled:
            return None
        ledger = None
        if policy.ledger:
            data_dir = getattr(settings, "data_dir", None)
            if data_dir is not None:
                ledger = DecisionLedger(data_dir / LEDGER_FILENAME)
        if provider is None:
            def factory() -> DecisionProvider:
                from horosa_skill.decisions.jev_http import JevHttpClient
                from horosa_skill.decisions.policy import read_api_key

                key = read_api_key(env)
                if not key:
                    raise JevError("调用时缺少 TypeSafe API key / TypeSafe API key missing at call time", code="jev.config")
                return JevHttpClient(api_key=key, base_url=policy.base_url, model=policy.model, timeout_s=policy.timeout_s)

            provider_arg: DecisionProvider | Callable[[], DecisionProvider] = factory
        else:
            provider_arg = provider
        return cls(policy, provider_arg, ledger=ledger, degrade=degrade, thresholds=load_thresholds())

    def _get_provider(self) -> DecisionProvider:
        if self._provider is None:
            factory = self._provider_or_factory
            self._provider = factory() if callable(factory) and not hasattr(factory, "decide") else factory  # type: ignore[assignment]
        return self._provider  # type: ignore[return-value]

    # ---- policy views ----------------------------------------------------------------------------
    def effective_mode(self, surface: str) -> tuple[str, str]:
        if not self.policy.surface_enabled(surface):
            return "off", "surface not enabled"
        allowed, reason = enforce_allowed(self.policy, surface, self.thresholds)
        return ("enforce", reason) if allowed else ("shadow", reason)

    def tau(self, surface: str) -> float:
        return resolve_tau(surface, self.thresholds)[0]

    def summary(self) -> dict[str, Any]:
        """信封级自陈（`DispatchEnvelope.decision_layer` / doctor 共用）。"""
        return {
            "provider": "typesafe_jev",
            "mode": self.policy.mode,
            "scope": self.policy.scope,
            "model": self.policy.model,
            "surfaces": {name: self.effective_mode(name)[0] for name in sorted(self.policy.surfaces)},
        }

    # ---- breaker ----------------------------------------------------------------------------------
    def _breaker_open(self) -> bool:
        return self._clock() < self._breaker_open_until

    def _record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._breaker_threshold:
            self._breaker_open_until = self._clock() + self._breaker_cooldown
            self._breaker_notified = False

    def _record_success(self) -> None:
        self._failures = 0
        self._breaker_notified = False

    def _notify(self, message: str) -> None:
        if self._degrade is not None:
            try:
                self._degrade(message)
            except Exception:  # noqa: BLE001 - 通知失败不能变成新的失败
                logger.debug("decision degrade callback failed", exc_info=True)

    # ---- main entry -------------------------------------------------------------------------------
    def ask(
        self,
        surface: str,
        *,
        state: Any,
        questions: Mapping[str, Question],
        redaction: Redaction | None = None,
        intent: str = "",
    ) -> Outcome:
        mode, mode_reason = self.effective_mode(surface)
        tau = self.tau(surface)
        if mode == "off":
            return Outcome(ok=False, surface=surface, mode="off", error_code="jev.surface_off", note=mode_reason, tau=tau)
        state_sha = _sha256_json(state)
        cache_key = _sha256_json({"state": state_sha, "questions": {qid: q.to_json() for qid, q in questions.items()}, "model": self.policy.model})
        base_record: dict[str, Any] = {
            "surface": surface,
            "intent": intent,
            "mode": mode,
            "mode_reason": mode_reason,
            "tau": tau,
            "model_requested": self.policy.model,
            "state_sha256": state_sha,
            "redaction": redaction.as_dict() if redaction is not None else None,
            "questions": list(questions),
            "adopted": False,
            "reason": None,
        }
        with self._lock:
            hit = self._cache.get(cache_key)
            if hit is not None and self._clock() - hit[0] <= self._cache_ttl:
                answers = hit[1]
                record = {**base_record, "model": answers.model, "answers": answers.compact(), "latency_ms": 0, "cached": True}
                return Outcome(ok=True, surface=surface, mode=mode, answers=answers, latency_ms=0, cached=True, tau=tau, record=record)
            if self._breaker_open():
                if not self._breaker_notified:
                    self._breaker_notified = True
                    self._notify("决策层（TypeSafe Jev）连续失败，已熔断 %.0f 秒并回落确定性路径。" % self._breaker_cooldown)
                record = {**base_record, "error": "jev.breaker_open"}
                return Outcome(ok=False, surface=surface, mode=mode, error_code="jev.breaker_open", note="breaker open", tau=tau, record=record)
        started = self._clock()
        try:
            provider = self._get_provider()
            answers = provider.decide(state=state, questions=questions, surface=surface)
        except JevError as exc:
            latency_ms = int((self._clock() - started) * 1000)
            with self._lock:
                self._record_failure()
            record = {**base_record, "error": exc.code, "latency_ms": latency_ms}
            self._write_ledger(record)
            self._notify(f"决策层（TypeSafe Jev）本次不可用（{exc.code}），已回落确定性路径。")
            return Outcome(ok=False, surface=surface, mode=mode, error_code=exc.code, note=str(exc), latency_ms=latency_ms, tau=tau, record=record)
        except Exception as exc:  # noqa: BLE001 - 未知异常同样关闭式降级，但要留痕
            latency_ms = int((self._clock() - started) * 1000)
            logger.debug("decision provider raised a non-Jev error", exc_info=True)
            with self._lock:
                self._record_failure()
            record = {**base_record, "error": "jev.internal", "latency_ms": latency_ms}
            self._write_ledger(record)
            self._notify(f"决策层（TypeSafe Jev）内部错误（{exc.__class__.__name__}），已回落确定性路径。")
            return Outcome(ok=False, surface=surface, mode=mode, error_code="jev.internal", note=exc.__class__.__name__, latency_ms=latency_ms, tau=tau, record=record)
        latency_ms = answers.latency_ms or int((self._clock() - started) * 1000)
        answers.latency_ms = latency_ms
        with self._lock:
            self._record_success()
            self._cache[cache_key] = (self._clock(), answers)
            if len(self._cache) > 256:
                oldest = sorted(self._cache.items(), key=lambda item: item[1][0])[: len(self._cache) - 256]
                for key, _ in oldest:
                    self._cache.pop(key, None)
        record = {**base_record, "model": answers.model, "answers": answers.compact(), "latency_ms": latency_ms, "cached": False, "usage": answers.usage}
        if answers.model != self.policy.model and self.policy.model != "jev-latest":
            # 返回的模型 id 与钉版不一致：账本要看得见，enforce 面在这一轮按 shadow 处理。
            record["model_drift"] = True
            if mode == "enforce":
                mode = "shadow"
                record["mode"] = "shadow"
                record["mode_reason"] = f"returned model {answers.model!r} != pinned {self.policy.model!r}"
                self._notify(f"决策层返回模型 {answers.model} 与钉版 {self.policy.model} 不一致，本轮按影子处理。")
        self._write_ledger(record)
        return Outcome(ok=True, surface=surface, mode=mode, answers=answers, latency_ms=latency_ms, tau=tau, record=record)

    def finalize(self, outcome: Outcome, *, adopted: bool, reason: str, decision: dict[str, Any] | None = None) -> dict[str, Any]:
        """各面代码在决定采纳与否后调用：补齐记录、写账本、挂进当前 provenance 作用域。"""
        record = dict(outcome.record)
        record["adopted"] = bool(adopted)
        record["reason"] = reason
        if decision:
            record["decision"] = decision
        self._write_ledger({"event": "finalize", **record})
        note_decision(record)
        return record

    def _write_ledger(self, record: dict[str, Any]) -> None:
        if self.ledger is None:
            return
        self.ledger.append(record)
