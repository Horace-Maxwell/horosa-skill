"""离线桩：`FakeJev`（按问题 id 脚本化答案）/ `FailingJev`（固定抛错）/ `RecordedJev`（按请求摘要回放）。

桩管形状，真值归 live smoke 与评测；桩返回的答案必须过 `parse_answers` 的同一套校验，
所以桩和真传输在解析层零分叉。
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from horosa_skill.decisions.errors import JevError, JevUnavailable
from horosa_skill.decisions.layer import DecisionProvider
from horosa_skill.decisions.questions import Answers, Choice, Question, Score, parse_answers

FAKE_MODEL = "jev-1.13.0"


def choice_answer(choice: str, *, confidence: float = 0.95, probabilities: Mapping[str, float] | None = None) -> dict[str, Any]:
    return {"type": "choice", "choice": choice, "confidence": confidence, "probabilities": dict(probabilities or {choice: 1.0})}


def score_answer(score: float, *, confidence: float = 0.9, probabilities: Mapping[str, float] | None = None) -> dict[str, Any]:
    return {"type": "score", "score": score, "confidence": confidence, "probabilities": dict(probabilities or {str(int(round(score))): 1.0}), "legend": {}}


def noul_answer(noul: float) -> dict[str, Any]:
    return {"type": "noul", "noul": noul}


def _default_answer(spec: Question) -> dict[str, Any]:
    """脚本没写的问题：Choice 选弃权项（置信 0）、Score 取 0 级、Noul 0.5——永远是「不采纳」的形状。"""
    if isinstance(spec, Choice):
        probs = {key: 0.0 for key in spec.criteria}
        probs[spec.abstain] = 1.0
        return {"type": "choice", "choice": spec.abstain, "confidence": 0.0, "probabilities": probs}
    if isinstance(spec, Score):
        probs = {str(i): 0.0 for i in range(len(spec.criteria))}
        probs["0"] = 1.0
        return {"type": "score", "score": 0.0, "confidence": 0.0, "probabilities": probs, "legend": {}}
    return {"type": "noul", "noul": 0.5}


def _fill_probabilities(spec: Question, raw: dict[str, Any]) -> dict[str, Any]:
    """脚本可以只给 `choice`：分布按「选中 1.0、其余 0」补齐，让桩答案过官方 schema 校验。"""
    out = dict(raw)
    if isinstance(spec, Choice):
        probs = {key: 0.0 for key in spec.criteria}
        probs.update({k: float(v) for k, v in (out.get("probabilities") or {}).items() if k in probs})
        if not any(out.get("probabilities") or {}):
            probs[str(out.get("choice"))] = 1.0
        out["probabilities"] = probs
    elif isinstance(spec, Score):
        probs = {str(i): 0.0 for i in range(len(spec.criteria))}
        probs.update({str(k): float(v) for k, v in (out.get("probabilities") or {}).items() if str(k) in probs})
        if not any(out.get("probabilities") or {}):
            probs[str(int(round(float(out.get("score", 0)))))] = 1.0
        out["probabilities"] = probs
        out.setdefault("legend", {})
    return out


class FakeJev(DecisionProvider):
    def __init__(
        self,
        script: Mapping[str, Mapping[str, Any]] | Callable[[Any, Mapping[str, Question]], Mapping[str, Mapping[str, Any]]] | None = None,
        *,
        model: str = FAKE_MODEL,
        latency_ms: int = 1,
    ) -> None:
        self._script = script or {}
        self.model = model
        self.latency_ms = latency_ms
        self.calls: list[dict[str, Any]] = []

    def decide(self, *, state: Any, questions: Mapping[str, Question], surface: str = "") -> Answers:
        self.calls.append({"surface": surface, "state": state, "questions": {qid: q.to_json() for qid, q in questions.items()}})
        scripted = self._script(state, questions) if callable(self._script) else self._script
        answers = {
            qid: _fill_probabilities(spec, dict(scripted[qid])) if qid in scripted else _default_answer(spec)
            for qid, spec in questions.items()
        }
        raw = {"model": self.model, "answers": answers, "usage": {"input_tokens": 100, "output_tokens": 10}}
        return parse_answers(questions, raw, latency_ms=self.latency_ms)


class FailingJev(DecisionProvider):
    def __init__(self, error: JevError | None = None) -> None:
        self.error = error or JevError("simulated failure", code="jev.server")
        self.calls = 0

    def decide(self, *, state: Any, questions: Mapping[str, Question], surface: str = "") -> Answers:
        self.calls += 1
        raise self.error


def request_digest(state: Any, questions: Mapping[str, Question], model: str) -> str:
    body = {"model": model, "state": state, "questions": {qid: q.to_json() for qid, q in questions.items()}}
    return hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


class RecordedJev(DecisionProvider):
    """评测回放：`cache.jsonl` 每行 {digest, response}；缺记录 → JevUnavailable（永不静默编造）。"""

    def __init__(self, cache_path: Path, *, model: str = FAKE_MODEL) -> None:
        self.cache_path = Path(cache_path)
        self.model = model
        self._cache: dict[str, dict[str, Any]] = {}
        if self.cache_path.is_file():
            for line in self.cache_path.read_text(encoding="utf-8").splitlines():
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and isinstance(row.get("digest"), str) and isinstance(row.get("response"), dict):
                    self._cache[row["digest"]] = row["response"]

    def __len__(self) -> int:
        return len(self._cache)

    def decide(self, *, state: Any, questions: Mapping[str, Question], surface: str = "") -> Answers:
        digest = request_digest(state, questions, self.model)
        response = self._cache.get(digest)
        if response is None:
            raise JevUnavailable("本请求没有录制过的响应（先跑 `jev_eval measure`）/ no recorded response for this request (run `jev_eval measure` first)", code="jev.replay_missing")
        return parse_answers(questions, response, latency_ms=0)
