"""决策层评测与晋升协议（P2）：金标集 → 录制/回放 → 指标 → τ 编译 → 预注册闸 → 阈值锁。

纪律：
- **测了才准用**：`enforce` 只认 `contracts/jev_thresholds.json`，锁只能由本模块在留出集上跑出来。
- **预注册闸** `PROMOTION_GATES` 写死在代码里，改数字 = 改代码 + 留痕；闸不过就是不晋升，没有「差一点」。
- **回放零调用**：`measure` 录下原始响应（`contracts/jev_eval/cache.jsonl`），`compile`/`check` 只回放；
  回放走与线上**同一套**解析（`parse_answers`）。
- 一致性同时报「同答率」与「都对率」——同答率单独看会奖励「一致地错」。
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from horosa_skill.decisions.questions import Answers, Choice, ChoiceAnswer, Question, parse_answers
from horosa_skill.decisions.redact import build_meta_state
from horosa_skill.decisions.surfaces.extract import build_gender_question, gender_candidates, resolve_gender
from horosa_skill.decisions.surfaces.routing import build_routing_questions, resolve_routing
from horosa_skill.decisions.surfaces.zhancat import GENERAL, build_zhan_question, resolve_zhan

EVAL_DIR = Path(__file__).resolve().parents[3] / "contracts" / "jev_eval"
CACHE_PATH = EVAL_DIR / "cache.jsonl"
REPORT_PATH = EVAL_DIR / "report.json"
THRESHOLDS_PATH = Path(__file__).resolve().parents[3] / "contracts" / "jev_thresholds.json"
SURFACES = ("routing", "extract", "zhancat")
# 面名 → 线上 policy 面名（routing 面在 policy 里叫 dispatch）。
POLICY_SURFACE = {"routing": "dispatch", "extract": "extract", "zhancat": "zhancat"}
HOLDOUT_RATIO = 0.30
TAU_GRID = [round(0.50 + 0.01 * i, 2) for i in range(50)]  # 0.50 … 0.99
PRICE_PER_MILLION_INPUT_USD = 0.042

# 预注册晋升闸（AGENTS §4 决策层法则 ⑥）。留出集上逐项判，全部过才 promoted。
PROMOTION_GATES: dict[str, float] = {
    "min_holdout_n": 30,
    "min_accuracy_decided": 0.95,     # τ 以上被采纳的判定里正确率
    "max_ece": 0.10,                  # 原始 top-1 置信的期望校准误差
    "max_escalation": 0.15,           # 有确定金标的样本里，弃权/低于 τ 的比例
    "min_paraphrase_both_correct": 0.90,
    "max_false_fill": 0.0,            # extract 专用：填错性别的比例必须为 0
}


# ---- 数据 ----------------------------------------------------------------------------------------


def load_cases(surface: str, eval_dir: Path = EVAL_DIR) -> list[dict[str, Any]]:
    path = eval_dir / f"{surface}.jsonl"
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def dataset_sha256(surface: str, eval_dir: Path = EVAL_DIR) -> str:
    return hashlib.sha256((eval_dir / f"{surface}.jsonl").read_bytes()).hexdigest()


def case_text(surface: str, case: Mapping[str, Any]) -> str:
    return str(case["question"] if surface == "zhancat" else case["query"])


def split_cases(cases: list[dict[str, Any]], *, holdout_ratio: float = HOLDOUT_RATIO, surface: str = "") -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """按文本哈希稳定切分（同组改写落同一侧，防泄漏）。"""
    train: list[dict[str, Any]] = []
    holdout: list[dict[str, Any]] = []
    for case in cases:
        key = str(case.get("group") or case_text(surface, case))
        bucket = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
        (holdout if bucket < holdout_ratio else train).append(case)
    return train, holdout


# ---- 面适配 ------------------------------------------------------------------------------------


def build_request(surface: str, case: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Question]]:
    text = case_text(surface, case)
    state, _redaction = build_meta_state(text)
    if surface == "routing":
        return state, build_routing_questions()
    if surface == "extract":
        return state, {"subject_gender": build_gender_question()}
    if surface == "zhancat":
        return state, {"zhan_category": build_zhan_question()}
    raise ValueError(f"unknown surface {surface!r}")


@dataclass
class Judged:
    """一条样本在某个 τ 下的判定。"""

    case: Mapping[str, Any]
    raw_choice: str | None        # τ 之前模型的 top-1（弃权键也算）
    raw_confidence: float
    decided: str | None           # τ 之后的最终输出（None = 弃权/不填）
    correct_raw: bool             # top-1 是否正确（校准用）
    correct_decided: bool | None  # 采纳后的判定是否正确（None = 未采纳）
    false_fill: bool = False      # extract：填了且填错
    deterministic: list[str] = field(default_factory=list)
    det_correct: bool | None = None
    latency_ms: int = 0
    input_tokens: int = 0


def _expected_set(case: Mapping[str, Any]) -> set[str]:
    out = set(case.get("accept") or [])
    if case.get("expect"):
        out.add(str(case["expect"]))
    return out


def judge(surface: str, case: Mapping[str, Any], answers: Answers, *, tau: float, deterministic: list[str] | None = None) -> Judged:
    tokens = int((answers.usage or {}).get("input_tokens", 0))
    if surface == "routing":
        decision = resolve_routing(answers.answers, tau=tau)
        raw = resolve_routing(answers.answers, tau=0.0)
        expected = _expected_set(case)
        raw_choice = raw.tool
        raw_conf = raw.tool_confidence if raw.tool else raw.family_confidence
        correct_raw = (raw.tool in expected) if raw.tool else (case.get("expect") is None)
        decided = decision.tool
        correct_decided = (decided in expected) if decided else None
        det = list(deterministic or [])
        det_correct = None
        if det:
            det_correct = bool(set(det) & expected)
        return Judged(case, raw_choice, raw_conf, decided, correct_raw, correct_decided, deterministic=det, det_correct=det_correct, latency_ms=answers.latency_ms, input_tokens=tokens)
    if surface == "extract":
        answer = answers.answers.get("subject_gender")
        candidates = gender_candidates(case_text(surface, case))
        decision = resolve_gender(answer, candidates, tau=tau)
        raw_key = answer.choice if isinstance(answer, ChoiceAnswer) else None
        raw_conf = answer.confidence if isinstance(answer, ChoiceAnswer) else 0.0
        expect = str(case["expect"])
        correct_raw = raw_key == expect
        decided = decision.key if decision.value is not None else None
        correct_decided = (decided == expect) if decided else None
        false_fill = decided is not None and decided != expect
        return Judged(case, raw_key, raw_conf, decided, correct_raw, correct_decided, false_fill=false_fill, latency_ms=answers.latency_ms, input_tokens=tokens)
    if surface == "zhancat":
        answer = answers.answers.get("zhan_category")
        decision = resolve_zhan(answer, tau=tau)
        raw_key = answer.choice if isinstance(answer, ChoiceAnswer) else None
        raw_conf = answer.confidence if isinstance(answer, ChoiceAnswer) else 0.0
        expect = str(case["expect"])
        correct_raw = raw_key == expect
        decided = decision.category
        correct_decided = (decided == expect) if decided else None
        return Judged(case, raw_key, raw_conf, decided, correct_raw, correct_decided, latency_ms=answers.latency_ms, input_tokens=tokens)
    raise ValueError(f"unknown surface {surface!r}")


def _has_definite_label(surface: str, case: Mapping[str, Any]) -> bool:
    if surface == "routing":
        return case.get("expect") is not None
    if surface == "extract":
        return case.get("expect") != "not_stated"
    return case.get("expect") != GENERAL


# ---- 指标 ------------------------------------------------------------------------------------------


def expected_calibration_error(pairs: Iterable[tuple[float, bool]], bins: int = 10) -> float:
    rows = list(pairs)
    if not rows:
        return 0.0
    buckets: list[list[tuple[float, bool]]] = [[] for _ in range(bins)]
    for conf, ok in rows:
        index = min(bins - 1, max(0, int(conf * bins)))
        buckets[index].append((conf, ok))
    total = len(rows)
    ece = 0.0
    for bucket in buckets:
        if not bucket:
            continue
        avg_conf = sum(c for c, _ in bucket) / len(bucket)
        acc = sum(1 for _, ok in bucket if ok) / len(bucket)
        ece += (len(bucket) / total) * abs(avg_conf - acc)
    return round(ece, 4)


def _percentile(values: list[int], pct: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(pct * len(ordered)) - 1))
    return int(ordered[index])


def paraphrase_consistency(surface: str, judged: list[Judged]) -> dict[str, float | int]:
    """同组（`group`）样本：同答率 vs 都对率。"""
    groups: dict[str, list[Judged]] = {}
    for item in judged:
        group = item.case.get("group")
        if group:
            groups.setdefault(str(group), []).append(item)
    pairs = 0
    same = 0
    both_correct = 0
    for members in groups.values():
        if len(members) < 2:
            continue
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                a, b = members[i], members[j]
                pairs += 1
                if a.raw_choice == b.raw_choice:
                    same += 1
                if a.correct_raw and b.correct_raw:
                    both_correct += 1
    return {
        "pairs": pairs,
        "same_answer_rate": round(same / pairs, 4) if pairs else 1.0,
        "both_correct_rate": round(both_correct / pairs, 4) if pairs else 1.0,
    }


def evaluate(surface: str, judged: list[Judged], *, tau: float) -> dict[str, Any]:
    n = len(judged)
    decided = [item for item in judged if item.decided is not None]
    definite = [item for item in judged if _has_definite_label(surface, item.case)]
    escalated = [item for item in definite if item.decided is None]
    correct_decided = sum(1 for item in decided if item.correct_decided)
    abstain_cases = [item for item in judged if not _has_definite_label(surface, item.case)]
    abstain_correct = sum(1 for item in abstain_cases if item.decided is None)
    metrics: dict[str, Any] = {
        "surface": surface,
        "tau": tau,
        "n": n,
        "n_decided": len(decided),
        "handled": round(len(decided) / n, 4) if n else 0.0,
        "accuracy_decided": round(correct_decided / len(decided), 4) if decided else None,
        "accuracy_raw": round(sum(1 for item in judged if item.correct_raw) / n, 4) if n else 0.0,
        "escalation": round(len(escalated) / len(definite), 4) if definite else 0.0,
        "abstain_correct_rate": round(abstain_correct / len(abstain_cases), 4) if abstain_cases else None,
        "ece": expected_calibration_error((item.raw_confidence, item.correct_raw) for item in judged),
        "paraphrase": paraphrase_consistency(surface, judged),
        "latency_ms": {"p50": _percentile([item.latency_ms for item in judged], 0.5), "p95": _percentile([item.latency_ms for item in judged], 0.95)},
        "input_tokens_total": sum(item.input_tokens for item in judged),
        "cost_usd": round(sum(item.input_tokens for item in judged) / 1e6 * PRICE_PER_MILLION_INPUT_USD, 6),
    }
    if surface == "extract":
        metrics["false_fill"] = round(sum(1 for item in judged if item.false_fill) / n, 4) if n else 0.0
    if surface == "routing":
        with_det = [item for item in judged if item.det_correct is not None]
        metrics["deterministic_accuracy"] = round(sum(1 for item in with_det if item.det_correct) / len(with_det), 4) if with_det else None
        nomatch = [item for item in judged if not item.deterministic]
        nomatch_decided = [item for item in nomatch if item.decided is not None]
        metrics["nomatch"] = {
            "n": len(nomatch),
            "handled": round(len(nomatch_decided) / len(nomatch), 4) if nomatch else 0.0,
            "accuracy_decided": round(sum(1 for item in nomatch_decided if item.correct_decided) / len(nomatch_decided), 4) if nomatch_decided else None,
        }
        agree = [item for item in judged if item.deterministic]
        metrics["agreement_with_deterministic"] = round(sum(1 for item in agree if item.raw_choice in item.deterministic) / len(agree), 4) if agree else None
    return metrics


def gate_verdicts(surface: str, metrics: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """预注册闸逐项判定；routing 的精度闸看的是 enforce 真正会用到的无匹配子集。"""
    out: dict[str, dict[str, Any]] = {}

    def gate(name: str, value: Any, ok: bool, limit: Any) -> None:
        out[name] = {"value": value, "limit": limit, "pass": bool(ok)}

    n = int(metrics.get("n") or 0)
    gate("min_holdout_n", n, n >= PROMOTION_GATES["min_holdout_n"], PROMOTION_GATES["min_holdout_n"])
    if surface == "routing":
        acc = (metrics.get("nomatch") or {}).get("accuracy_decided")
        gate("min_accuracy_decided", acc, acc is not None and acc >= PROMOTION_GATES["min_accuracy_decided"], PROMOTION_GATES["min_accuracy_decided"])
    else:
        acc = metrics.get("accuracy_decided")
        gate("min_accuracy_decided", acc, acc is not None and acc >= PROMOTION_GATES["min_accuracy_decided"], PROMOTION_GATES["min_accuracy_decided"])
    ece = float(metrics.get("ece") or 0.0)
    gate("max_ece", ece, ece <= PROMOTION_GATES["max_ece"], PROMOTION_GATES["max_ece"])
    esc = float(metrics.get("escalation") or 0.0)
    gate("max_escalation", esc, esc <= PROMOTION_GATES["max_escalation"], PROMOTION_GATES["max_escalation"])
    both = float((metrics.get("paraphrase") or {}).get("both_correct_rate", 1.0))
    gate("min_paraphrase_both_correct", both, both >= PROMOTION_GATES["min_paraphrase_both_correct"], PROMOTION_GATES["min_paraphrase_both_correct"])
    if surface == "extract":
        ff = float(metrics.get("false_fill") or 0.0)
        gate("max_false_fill", ff, ff <= PROMOTION_GATES["max_false_fill"], PROMOTION_GATES["max_false_fill"])
    return out


HANDLED_PLATEAU = 0.02


def _target_accuracy(surface: str, metrics: Mapping[str, Any]) -> float | None:
    return (metrics.get("nomatch") or {}).get("accuracy_decided") if surface == "routing" else metrics.get("accuracy_decided")


def choose_tau(surface: str, judge_at: Callable[[float], list[Judged]], *, target_accuracy: float = PROMOTION_GATES["min_accuracy_decided"]) -> tuple[float, dict[str, Any]]:
    """训练集上扫 τ：满足精度目标的 τ 里，处理率在最高值 2 个百分点内取**最大的 τ**（处理率进入平台期时
    偏保守，别把 τ 钉在网格底部）；都不满足 → 取精度最高的 τ（不会晋升，但报出来）。"""
    candidates: list[tuple[float, dict[str, Any]]] = []
    fallback: tuple[float, dict[str, Any]] | None = None
    for tau in TAU_GRID:
        metrics = evaluate(surface, judge_at(tau), tau=tau)
        acc = _target_accuracy(surface, metrics)
        if acc is not None and acc >= target_accuracy:
            candidates.append((tau, metrics))
        if fallback is None or (acc or 0.0) > (_target_accuracy(surface, fallback[1]) or 0.0):
            fallback = (tau, metrics)
    if candidates:
        max_handled = max(float(m.get("handled") or 0.0) for _t, m in candidates)
        plateau = [(t, m) for t, m in candidates if float(m.get("handled") or 0.0) >= max_handled - HANDLED_PLATEAU]
        return max(plateau, key=lambda item: item[0])
    return fallback or (0.99, evaluate(surface, judge_at(0.99), tau=0.99))


# ---- 录制 / 回放 ----------------------------------------------------------------------------------


def request_digest(state: Any, questions: Mapping[str, Question], model: str, run: int = 0) -> str:
    body = {"model": model, "state": state, "questions": {qid: q.to_json() for qid, q in questions.items()}, "run": run}
    return hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


class ResponseCache:
    def __init__(self, path: Path = CACHE_PATH) -> None:
        self.path = Path(path)
        self._rows: dict[str, dict[str, Any]] = {}
        if self.path.is_file():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and isinstance(row.get("digest"), str):
                    self._rows[row["digest"]] = row

    def __len__(self) -> int:
        return len(self._rows)

    def get(self, digest: str) -> dict[str, Any] | None:
        return self._rows.get(digest)

    def put(self, digest: str, response: dict[str, Any], *, latency_ms: int, surface: str) -> None:
        row = {"digest": digest, "surface": surface, "model": response.get("model"), "latency_ms": latency_ms, "response": response}
        self._rows[digest] = row
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n")


def answers_for(
    surface: str,
    case: Mapping[str, Any],
    *,
    model: str,
    cache: ResponseCache,
    run: int = 0,
    fetch: Callable[[dict[str, Any], dict[str, Question]], tuple[dict[str, Any], int]] | None = None,
) -> Answers | None:
    """缓存命中 → 回放；未命中且给了 fetch → 真调用并录制；否则 None。"""
    state, questions = build_request(surface, case)
    digest = request_digest(state, questions, model, run)
    row = cache.get(digest)
    if row is None:
        if fetch is None:
            return None
        response, latency_ms = fetch(state, questions)
        cache.put(digest, response, latency_ms=latency_ms, surface=surface)
        row = cache.get(digest)
    assert row is not None
    answers = parse_answers(questions, row["response"], latency_ms=int(row.get("latency_ms") or 0))
    return answers


def lint_questions() -> list[str]:
    """无 key 也能跑的静态检查：三面的问题规格都过 Choice 构造校验（英文题面、弃权项、上限）。"""
    problems: list[str] = []
    for surface in SURFACES:
        try:
            _state, questions = build_request(surface, {"query": "测试", "question": "测试"})
        except Exception as exc:  # noqa: BLE001 - lint 就是要把构造错误报出来
            problems.append(f"{surface}: {exc}")
            continue
        for qid, question in questions.items():
            if not isinstance(question, Choice):
                problems.append(f"{surface}/{qid}: not a Choice")
    return problems


def summarize_runs(judged_runs: list[list[Judged]]) -> dict[str, Any]:
    """多次录制之间的翻转率（同一样本 top-1 是否变化）。"""
    if len(judged_runs) < 2:
        return {"runs": len(judged_runs), "flip_rate": 0.0}
    flips = 0
    total = 0
    base = judged_runs[0]
    for other in judged_runs[1:]:
        for a, b in zip(base, other, strict=False):
            total += 1
            if a.raw_choice != b.raw_choice:
                flips += 1
    return {"runs": len(judged_runs), "flip_rate": round(flips / total, 4) if total else 0.0}


def latency_summary(judged: list[Judged]) -> dict[str, float]:
    values = [item.latency_ms for item in judged if item.latency_ms]
    if not values:
        return {"p50": 0, "p95": 0, "mean": 0.0}
    return {"p50": _percentile(values, 0.5), "p95": _percentile(values, 0.95), "mean": round(statistics.fmean(values), 1)}
