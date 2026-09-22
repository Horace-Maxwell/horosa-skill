"""编排层：面开关 / 缓存 / 熔断 / 账本 / 关闭式降级 / 模型漂移降影子 / from_settings 缺省 None。"""

from __future__ import annotations

import json
from pathlib import Path

from horosa_skill.config import Settings
from horosa_skill.decisions.errors import JevError
from horosa_skill.decisions.fake import FailingJev, FakeJev, choice_answer
from horosa_skill.decisions.layer import DecisionLayer, decision_records, note_decision
from horosa_skill.decisions.ledger import DecisionLedger
from horosa_skill.decisions.policy import Policy
from horosa_skill.decisions.questions import Choice

Q = {"pick": Choice(instructions="Pick one.", criteria={"a": "A", "b": "B", "unknown": "none"}, abstain="unknown")}
LOCK = {"model": "jev-1.13.0", "surfaces": {"dispatch": {"tau": 0.8, "promoted": True}}}


def _policy(mode: str = "shadow", surfaces: tuple[str, ...] = ("dispatch",), model: str = "jev-1.13.0") -> Policy:
    return Policy(
        mode=mode, scope="meta", surfaces=frozenset(surfaces), model=model, base_url="https://api.typesafe.ai",
        timeout_s=3.0, ledger=True, key_present=True, requested_mode=mode,
    )


def test_from_settings_returns_none_when_off(monkeypatch, tmp_path: Path) -> None:
    for key in list(__import__("os").environ):
        if key.startswith("HOROSA_JEV") or key == "TYPESAFE_API_KEY":
            monkeypatch.delenv(key, raising=False)
    assert DecisionLayer.from_settings(Settings(data_dir=tmp_path)) is None
    # 开了但没 key → 仍然 None（策略整体关闭）。
    monkeypatch.setenv("HOROSA_JEV", "shadow")
    assert DecisionLayer.from_settings(Settings(data_dir=tmp_path)) is None


def test_from_settings_builds_a_lazy_layer_without_touching_the_network(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOROSA_JEV", "shadow")
    monkeypatch.setenv("HOROSA_JEV_API_KEY", "sk-test-key-000000000000")
    layer = DecisionLayer.from_settings(Settings(data_dir=tmp_path))
    assert layer is not None and layer.policy.mode == "shadow"
    assert layer.ledger is not None and layer.ledger.path == tmp_path / "jev_events.jsonl"
    assert layer.effective_mode("dispatch") == ("shadow", "mode=shadow")
    assert layer.effective_mode("faithfulness") == ("off", "surface not enabled")


def test_shadow_ask_records_and_ledgers(tmp_path: Path) -> None:
    ledger = DecisionLedger(tmp_path / "events.jsonl")
    fake = FakeJev({"pick": choice_answer("a", confidence=0.91)})
    layer = DecisionLayer(_policy(), fake, ledger=ledger)
    outcome = layer.ask("dispatch", state={"user_request": "x"}, questions=Q, intent="t")
    assert outcome.ok and outcome.mode == "shadow" and outcome.answers.answers["pick"].choice == "a"
    assert outcome.tau == 0.7 and outcome.record["adopted"] is False
    record = layer.finalize(outcome, adopted=False, reason="shadow", decision={"tool": "a"})
    rows = ledger.tail(10)
    assert len(rows) == 2 and rows[1]["event"] == "finalize" and rows[1]["decision"] == {"tool": "a"}
    assert record["state_sha256"] and "user_request" not in json.dumps(rows[0])  # 账本只有摘要，没有原文
    assert fake.calls[0]["surface"] == "dispatch"


def test_surface_off_costs_nothing() -> None:
    fake = FakeJev({})
    layer = DecisionLayer(_policy(surfaces=("extract",)), fake)
    outcome = layer.ask("dispatch", state="x", questions=Q)
    assert not outcome.ok and outcome.mode == "off" and outcome.error_code == "jev.surface_off"
    assert fake.calls == []


def test_enforce_needs_the_lock_else_shadow() -> None:
    fake = FakeJev({"pick": choice_answer("a", confidence=0.95)})
    unlocked = DecisionLayer(_policy("enforce"), fake)
    assert unlocked.effective_mode("dispatch")[0] == "shadow"
    locked = DecisionLayer(_policy("enforce"), fake, thresholds=LOCK)
    assert locked.effective_mode("dispatch") == ("enforce", "promoted")
    outcome = locked.ask("dispatch", state="x", questions=Q)
    assert outcome.enforced and outcome.tau == 0.8


def test_model_drift_downgrades_enforce_to_shadow_for_that_call() -> None:
    fake = FakeJev({"pick": choice_answer("a", confidence=0.95)}, model="jev-1.14.0")
    notes: list[str] = []
    layer = DecisionLayer(_policy("enforce"), fake, thresholds=LOCK, degrade=notes.append)
    outcome = layer.ask("dispatch", state="x", questions=Q)
    assert outcome.ok and outcome.mode == "shadow" and outcome.record["model_drift"] is True
    assert any("jev-1.14.0" in note for note in notes)


def test_failure_degrades_closed_and_breaker_opens_after_three() -> None:
    notes: list[str] = []
    clock = {"t": 100.0}
    layer = DecisionLayer(_policy(), FailingJev(JevError("boom", code="jev.server")), degrade=notes.append, clock=lambda: clock["t"])
    for _ in range(3):
        outcome = layer.ask("dispatch", state="x", questions=Q)
        assert not outcome.ok and outcome.error_code == "jev.server"
    assert len(notes) == 3 and all("jev.server" in note for note in notes)
    fourth = layer.ask("dispatch", state="x", questions=Q)
    assert fourth.error_code == "jev.breaker_open" and len(notes) == 4 and "熔断" in notes[3]
    fifth = layer.ask("dispatch", state="x", questions=Q)
    assert fifth.error_code == "jev.breaker_open" and len(notes) == 4, "one notice per breaker window"
    clock["t"] += 61
    assert layer.ask("dispatch", state="x", questions=Q).error_code == "jev.server", "cooldown over → tries again"


def test_non_jev_exception_is_also_degraded_not_raised() -> None:
    class Boom:
        def decide(self, **_: object):
            raise RuntimeError("unexpected")

    notes: list[str] = []
    layer = DecisionLayer(_policy(), Boom(), degrade=notes.append)
    outcome = layer.ask("dispatch", state="x", questions=Q)
    assert outcome.error_code == "jev.internal" and notes and "RuntimeError" in notes[0]


def test_identical_requests_are_served_from_cache_within_ttl() -> None:
    fake = FakeJev({"pick": choice_answer("b", confidence=0.7)})
    clock = {"t": 0.0}
    layer = DecisionLayer(_policy(), fake, clock=lambda: clock["t"], cache_ttl_s=120.0)
    first = layer.ask("dispatch", state={"user_request": "same"}, questions=Q)
    second = layer.ask("dispatch", state={"user_request": "same"}, questions=Q)
    assert not first.cached and second.cached and len(fake.calls) == 1
    clock["t"] = 200.0
    third = layer.ask("dispatch", state={"user_request": "same"}, questions=Q)
    assert not third.cached and len(fake.calls) == 2


def test_decision_records_scope_bubbles_to_parent() -> None:
    with decision_records() as outer:
        with decision_records() as inner:
            note_decision({"surface": "zhancat", "adopted": True})
        assert inner == [{"surface": "zhancat", "adopted": True}]
        assert outer == inner
    note_decision({"surface": "ignored"})  # 无作用域时是 no-op，不抛
