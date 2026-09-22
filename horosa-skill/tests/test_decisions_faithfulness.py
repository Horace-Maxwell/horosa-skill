"""S4 忠实性第二意见：二档才开、只读、永不改确定性判定；异常降级。"""

from __future__ import annotations

from pathlib import Path

from test_service import FakeClient, FakeJsClient

from horosa_skill.config import Settings
from horosa_skill.decisions.fake import FailingJev, FakeJev, noul_answer
from horosa_skill.decisions.layer import DecisionLayer
from horosa_skill.decisions.policy import Policy
from horosa_skill.decisions.surfaces.faithfulness import MAX_CLAIMS, build_opinion_questions, build_opinion_state, summarize_opinion
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

REPORT = {
    "ok": False,
    "claims": [
        {"type": "ganzhi_pillar", "text": "年柱甲子", "status": "supported"},
        {"type": "placement", "text": "太阳在狮子座", "status": "contradicted"},
        {"type": "sanchuan", "text": "初传申", "status": "invented"},
    ],
    "metrics": {"claims_total": 3, "supported": 1, "invented": 1, "contradicted": 1},
}
EXPORT = "[四柱]\n年柱：甲子 月柱：丙寅\n[行星]\n太阳 处女座 12°\n"


def _policy(scope: str, mode: str = "shadow") -> Policy:
    return Policy(
        mode=mode, scope=scope, surfaces=frozenset({"faithfulness"}), model="jev-1.13.0", base_url="https://api.typesafe.ai",
        timeout_s=3.0, ledger=False, key_present=True, requested_mode=mode,
    )


def _service(tmp_path: Path, layer: DecisionLayer | None) -> HorosaSkillService:
    settings = Settings(db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    return HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient(), decision_layer=layer)


def test_questions_are_one_noul_per_claim_capped_and_english_led() -> None:
    claims = [{"text": f"断言{i}", "status": "supported"} for i in range(20)]
    questions = build_opinion_questions(claims)
    assert len(questions) == MAX_CLAIMS and all(q.instructions.startswith("The state.chart_export") for q in questions.values())
    state = build_opinion_state("x" * 9000)
    assert len(state["chart_export"]) <= 5010 and state["chart_export"].endswith("<截断>")


def test_summary_aligns_model_probability_with_the_deterministic_status() -> None:
    from horosa_skill.decisions.questions import NoulAnswer

    answers = {"claim_0": NoulAnswer(0.96), "claim_1": NoulAnswer(0.05), "claim_2": NoulAnswer(0.5)}
    summary = summarize_opinion(REPORT["claims"], answers, tau=0.7)
    assert summary["n"] == 3 and summary["n_judged"] == 2 and summary["agreement_rate"] == 1.0
    assert summary["per_claim"][2]["model"] == "undecided" and summary["per_claim"][2]["agrees"] is None
    assert summary["disagreements"] == []


def test_opinion_requires_snapshot_scope_and_never_touches_the_report(tmp_path: Path) -> None:
    fake = FakeJev({"claim_0": noul_answer(0.9), "claim_1": noul_answer(0.8), "claim_2": noul_answer(0.1)})
    meta = _service(tmp_path / "meta", DecisionLayer(_policy("meta"), fake))
    assert meta.faithfulness_opinion(dict(REPORT), EXPORT) is None and fake.calls == []

    snap = _service(tmp_path / "snap", DecisionLayer(_policy("snapshot"), fake))
    report = {**REPORT, "claims": [dict(c) for c in REPORT["claims"]]}
    opinion = snap.faithfulness_opinion(report, EXPORT)
    assert opinion is not None and opinion["mode"] == "shadow" and opinion["provider"] == "typesafe_jev"
    assert report["ok"] is False and report["metrics"] == REPORT["metrics"], "report untouched"
    assert opinion["n_judged"] == 3 and opinion["agreement_rate"] == 0.6667
    assert [row["text"] for row in opinion["disagreements"]] == ["太阳在狮子座"]
    assert fake.calls and fake.calls[0]["state"]["chart_export"].startswith("[四柱]")


def test_opinion_degrades_to_none_on_provider_failure_or_empty_input(tmp_path: Path) -> None:
    notes: list[str] = []
    failing = _service(tmp_path / "f", DecisionLayer(_policy("snapshot"), FailingJev(), degrade=notes.append))
    assert failing.faithfulness_opinion(dict(REPORT), EXPORT) is None and notes
    ok = _service(tmp_path / "e", DecisionLayer(_policy("snapshot"), FakeJev({})))
    assert ok.faithfulness_opinion({"ok": True, "claims": []}, EXPORT) is None
    assert ok.faithfulness_opinion(dict(REPORT), "") is None
