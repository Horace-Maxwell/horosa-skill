"""评测与晋升协议：切分稳定、判定正确、ECE、τ 编译、预注册闸、回放零调用、金标集 lint。"""

from __future__ import annotations

import json
from pathlib import Path

from horosa_skill.decisions import eval as ev
from horosa_skill.decisions.fake import FakeJev, choice_answer
from horosa_skill.decisions.surfaces.zhancat import ZHANDUAN_CATEGORIES
from horosa_skill.engine.registry import TOOL_DEFINITIONS

EVAL_DIR = Path(__file__).resolve().parents[1] / "contracts" / "jev_eval"


def test_gold_sets_are_well_formed_and_large_enough() -> None:
    routing = ev.load_cases("routing")
    extract = ev.load_cases("extract")
    zhancat = ev.load_cases("zhancat")
    assert len(routing) >= 200 and len(extract) >= 150 and len(zhancat) >= 100
    for case in routing:
        labels = ([case["expect"]] if case.get("expect") else []) + list(case.get("accept") or [])
        assert all(label in TOOL_DEFINITIONS for label in labels), case
    assert {case["expect"] for case in extract} == {"female", "male", "not_stated"}
    assert all(case["expect"] in ZHANDUAN_CATEGORIES for case in zhancat)
    assert len({case["query"] for case in routing}) == len(routing)
    assert ev.lint_questions() == []


def test_split_is_stable_and_keeps_groups_together() -> None:
    cases = ev.load_cases("extract")
    a = ev.split_cases(cases, surface="extract")
    b = ev.split_cases(cases, surface="extract")
    assert a == b
    train, holdout = a
    assert train and holdout and len(holdout) / len(cases) > 0.15
    train_groups = {c["group"] for c in train if c.get("group")}
    holdout_groups = {c["group"] for c in holdout if c.get("group")}
    assert not train_groups & holdout_groups, "同组改写必须落在同一侧，否则改写一致性在留出集上是泄漏"


def _routing_answers(family: str, tool: str, conf: float):
    fake = FakeJev({"family": choice_answer(family, confidence=conf), f"tool__{family}": choice_answer(tool, confidence=conf)})
    state, questions = ev.build_request("routing", {"query": "x"})
    return fake.decide(state=state, questions=questions)


def test_judge_routing_scores_expect_accept_and_abstention() -> None:
    answers = _routing_answers("bazi", "bazi_birth", 0.9)
    judged = ev.judge("routing", {"query": "q", "expect": "bazi_birth"}, answers, tau=0.7, deterministic=["bazi_birth"])
    assert judged.correct_raw and judged.correct_decided and judged.det_correct and judged.decided == "bazi_birth"
    judged = ev.judge("routing", {"query": "q", "expect": None, "accept": ["bazi_birth"]}, answers, tau=0.7, deterministic=[])
    assert judged.correct_decided is True, "accept 列表里的工具算对"
    judged = ev.judge("routing", {"query": "q", "expect": "ziwei_birth"}, answers, tau=0.95, deterministic=[])
    assert judged.decided is None and judged.correct_decided is None and judged.correct_raw is False
    abstain = _routing_answers("unknown", "none_of_these", 0.99)
    judged = ev.judge("routing", {"query": "q", "expect": None}, abstain, tau=0.7)
    assert judged.correct_raw is True and judged.decided is None


def test_judge_extract_flags_false_fills_and_double_key() -> None:
    fake = FakeJev({"subject_gender": choice_answer("female", confidence=0.99)})
    state, questions = ev.build_request("extract", {"query": "帮我老婆排八字"})
    answers = fake.decide(state=state, questions=questions)
    ok = ev.judge("extract", {"query": "帮我老婆排八字", "expect": "female"}, answers, tau=0.9)
    assert ok.decided == "female" and ok.correct_decided and not ok.false_fill
    wrong = ev.judge("extract", {"query": "帮我老婆排八字", "expect": "not_stated"}, answers, tau=0.9)
    assert wrong.false_fill is True and wrong.correct_decided is False
    no_lexicon = ev.judge("extract", {"query": "帮我朋友排八字", "expect": "not_stated"}, answers, tau=0.9)
    assert no_lexicon.decided is None and not no_lexicon.false_fill, "双钥：无词表证据不填"


def test_ece_is_zero_for_perfect_calibration_and_large_for_overconfidence() -> None:
    assert ev.expected_calibration_error([(1.0, True)] * 10) == 0.0
    assert ev.expected_calibration_error([(0.95, False)] * 10) >= 0.9
    assert ev.expected_calibration_error([]) == 0.0


def test_evaluate_and_gates_on_a_synthetic_surface() -> None:
    cases = [{"query": f"q{i}", "expect": "hunyin" if i % 2 else "general", "group": f"g{i // 2}"} for i in range(40)]
    judged = []
    for case in cases:
        fake = FakeJev({"zhan_category": choice_answer(case["expect"], confidence=0.97)})
        state, questions = ev.build_request("zhancat", {"question": case["query"]})
        judged.append(ev.judge("zhancat", {"question": case["query"], **case}, fake.decide(state=state, questions=questions), tau=0.7))
    metrics = ev.evaluate("zhancat", judged, tau=0.7)
    assert metrics["n"] == 40 and metrics["accuracy_decided"] == 1.0 and metrics["escalation"] == 0.0
    assert metrics["abstain_correct_rate"] == 1.0 and metrics["ece"] <= 0.05
    verdicts = ev.gate_verdicts("zhancat", metrics)
    assert all(item["pass"] for item in verdicts.values()), verdicts


def test_gates_fail_loudly_when_accuracy_or_calibration_is_bad() -> None:
    bad = {"n": 40, "accuracy_decided": 0.8, "ece": 0.3, "escalation": 0.5, "paraphrase": {"both_correct_rate": 0.5}, "false_fill": 0.1}
    verdicts = ev.gate_verdicts("extract", bad)
    assert not verdicts["min_accuracy_decided"]["pass"] and not verdicts["max_ece"]["pass"]
    assert not verdicts["max_escalation"]["pass"] and not verdicts["min_paraphrase_both_correct"]["pass"] and not verdicts["max_false_fill"]["pass"]
    routing = {"n": 10, "nomatch": {"accuracy_decided": 1.0}, "ece": 0.0, "escalation": 0.0, "paraphrase": {"both_correct_rate": 1.0}}
    assert not ev.gate_verdicts("routing", routing)["min_holdout_n"]["pass"], "留出集太小不许晋升"


def test_choose_tau_prefers_the_widest_tau_that_meets_the_target() -> None:
    cases = [{"question": f"q{i}", "expect": "caiyun"} for i in range(20)]

    def judge_at(tau: float):
        out = []
        for i, case in enumerate(cases):
            conf = 0.6 if i < 5 else 0.95            # 前 5 条置信低且错，其余高且对
            key = "hunyin" if i < 5 else "caiyun"
            fake = FakeJev({"zhan_category": choice_answer(key, confidence=conf)})
            state, questions = ev.build_request("zhancat", case)
            out.append(ev.judge("zhancat", case, fake.decide(state=state, questions=questions), tau=tau))
        return out

    tau, metrics = ev.choose_tau("zhancat", judge_at)
    assert 0.6 < tau <= 0.95 and metrics["accuracy_decided"] == 1.0 and metrics["handled"] == 0.75


def test_response_cache_replays_without_fetch(tmp_path: Path) -> None:
    cache = ev.ResponseCache(tmp_path / "cache.jsonl")
    case = {"question": "问财运", "expect": "caiyun"}
    calls = {"n": 0}

    def fetch(state, questions):
        calls["n"] += 1
        fake = FakeJev({"zhan_category": choice_answer("caiyun", confidence=0.9)})
        answers = fake.decide(state=state, questions=questions)
        return {"model": answers.model, "answers": {"zhan_category": {"type": "choice", "choice": "caiyun", "confidence": 0.9, "probabilities": {k: (1.0 if k == "caiyun" else 0.0) for k in ZHANDUAN_CATEGORIES}}}, "usage": {"input_tokens": 50}}, 123

    first = ev.answers_for("zhancat", case, model="jev-1.13.0", cache=cache, fetch=fetch)
    assert first is not None and calls["n"] == 1
    replay = ev.answers_for("zhancat", case, model="jev-1.13.0", cache=ev.ResponseCache(tmp_path / "cache.jsonl"))
    assert replay is not None and replay.answers["zhan_category"].choice == "caiyun" and replay.latency_ms == 123
    assert ev.answers_for("zhancat", {"question": "别的", "expect": "general"}, model="jev-1.13.0", cache=cache) is None
    assert calls["n"] == 1
    row = json.loads((tmp_path / "cache.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert row["surface"] == "zhancat" and "question" not in json.dumps(row), "缓存只有摘要 + 响应，不存原文"


def test_dataset_sha256_is_line_ending_agnostic(tmp_path: Path) -> None:
    """v0.39.0 Windows 维护机：锁里的数据集 sha 不能依赖工作区换行——Windows 上重生成（文本模式）或未被
    `.gitattributes` 覆盖的 autocrlf 检出是 CRLF，按原始字节算会写进只在那台机器上成立的值。"""
    import hashlib

    rows = '{"group": "g1", "query": "问事业"}\n{"group": "g2", "query": "看流年"}\n'
    lf, crlf = tmp_path / "lf", tmp_path / "crlf"
    lf.mkdir()
    crlf.mkdir()
    (lf / "routing.jsonl").write_bytes(rows.encode("utf-8"))
    (crlf / "routing.jsonl").write_bytes(rows.replace("\n", "\r\n").encode("utf-8"))
    assert ev.dataset_sha256("routing", lf) == ev.dataset_sha256("routing", crlf)
    assert ev.dataset_sha256("routing", lf) == hashlib.sha256(rows.encode("utf-8")).hexdigest(), "LF 内容 sha 不变 → 已提交的锁仍有效"
