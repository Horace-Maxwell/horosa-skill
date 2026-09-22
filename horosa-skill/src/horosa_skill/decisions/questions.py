"""三原语（Choice / Score / Noul）的规格与答案解析，镜像官方 `/v1/systemone` schema。

官方只在散文里写了 Choice ≤255 项、Score 2–10 级（机器 schema 不校验），这里**自己**校验；
另加本仓纪律：instructions 必须是英文（Jev 英文为主训练语言；criteria 描述可中文），Choice 必须
带一个弃权项（`abstain`）——去掉弃权项时第三方评测量到准确率从 0.95 掉到 0.00。
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

_CJK = re.compile(r"[㐀-鿿]")
_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
MAX_CHOICE_OPTIONS = 255
MIN_SCORE_LEVELS = 2
MAX_SCORE_LEVELS = 10
# instructions 以英文为主（Jev 英文为主训练语言）；允许夹带中文**提示词**（抽取面必须引用 老婆/妻子 这类
# 原话线索），但 CJK 占比超过三成就不再是英文题面。
MAX_CJK_RATIO_IN_INSTRUCTIONS = 0.30


class QuestionSpecError(ValueError):
    """问题规格越界——在发出任何网络请求之前就抛。"""


def cjk_ratio(text: str) -> float:
    stripped = "".join(ch for ch in str(text) if not ch.isspace())
    if not stripped:
        return 0.0
    return len(_CJK.findall(stripped)) / len(stripped)


def _check_instructions(text: Any) -> None:
    if not isinstance(text, str) or not text.strip():
        raise QuestionSpecError("instructions 必须是非空字符串 / instructions must be a non-empty string")
    if cjk_ratio(text) > MAX_CJK_RATIO_IN_INSTRUCTIONS:
        raise QuestionSpecError(
            "instructions 须以英文为主（Jev 英文优先），中文只留线索词、描述放 criteria / instructions must be English-led (Jev is English-primary); keep Chinese to cue words and put descriptions in criteria"
        )


@dataclass(frozen=True)
class Choice:
    instructions: str
    criteria: Mapping[str, str | None]
    abstain: str

    def __post_init__(self) -> None:
        _check_instructions(self.instructions)
        keys = list(self.criteria)
        if not 2 <= len(keys) <= MAX_CHOICE_OPTIONS:
            raise QuestionSpecError(f"choice 选项数须在 2..{MAX_CHOICE_OPTIONS}，现为 {len(keys)} / choice needs 2..{MAX_CHOICE_OPTIONS} options, got {len(keys)}")
        bad = [key for key in keys if not _KEY.match(str(key))]
        if bad:
            raise QuestionSpecError(f"choice 选项键必须是 ASCII 标识符：{bad[:3]} / choice option keys must be ASCII identifiers: {bad[:3]}")
        if self.abstain not in self.criteria:
            raise QuestionSpecError(f"弃权项 {self.abstain!r} 必须在 criteria 之中 / abstain option {self.abstain!r} must be one of the criteria")

    def to_json(self) -> dict[str, Any]:
        return {"type": "choice", "instructions": self.instructions, "criteria": dict(self.criteria)}


@dataclass(frozen=True)
class Score:
    instructions: str
    criteria: Sequence[str]

    def __post_init__(self) -> None:
        _check_instructions(self.instructions)
        levels = list(self.criteria)
        if not MIN_SCORE_LEVELS <= len(levels) <= MAX_SCORE_LEVELS:
            raise QuestionSpecError(f"score 档位数须在 {MIN_SCORE_LEVELS}..{MAX_SCORE_LEVELS}，现为 {len(levels)} / score needs {MIN_SCORE_LEVELS}..{MAX_SCORE_LEVELS} levels, got {len(levels)}")
        if any(not isinstance(level, str) or not level.strip() for level in levels):
            raise QuestionSpecError("score 各档必须是描述具体情形的非空字符串 / score levels must be non-empty strings describing concrete situations")

    def to_json(self) -> dict[str, Any]:
        return {"type": "score", "instructions": self.instructions, "criteria": list(self.criteria)}


@dataclass(frozen=True)
class Noul:
    instructions: str
    criteria: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        _check_instructions(self.instructions)
        if self.criteria is not None and set(self.criteria) - {"true", "false"}:
            raise QuestionSpecError("noul 的 criteria 键必须是 'true' 与 'false' / noul criteria keys must be 'true' and 'false'")

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"type": "noul", "instructions": self.instructions}
        if self.criteria:
            payload["criteria"] = dict(self.criteria)
        return payload


Question = Choice | Score | Noul


@dataclass(frozen=True)
class ChoiceAnswer:
    choice: str
    confidence: float
    probabilities: dict[str, float]

    def top(self, n: int = 3) -> list[tuple[str, float]]:
        return sorted(self.probabilities.items(), key=lambda item: (-item[1], item[0]))[:n]


@dataclass(frozen=True)
class ScoreAnswer:
    score: float
    confidence: float
    probabilities: dict[str, float]
    legend: dict[str, str]


@dataclass(frozen=True)
class NoulAnswer:
    noul: float


Answer = ChoiceAnswer | ScoreAnswer | NoulAnswer


@dataclass
class Answers:
    model: str
    usage: dict[str, int]
    answers: dict[str, Answer]
    latency_ms: int = 0

    def compact(self) -> dict[str, dict[str, Any]]:
        """provenance / 账本用的紧凑形（不带整份分布，但保留 top-3）。"""
        out: dict[str, dict[str, Any]] = {}
        for qid, answer in self.answers.items():
            if isinstance(answer, ChoiceAnswer):
                out[qid] = {
                    "type": "choice",
                    "choice": answer.choice,
                    "confidence": round(answer.confidence, 4),
                    "top": [[key, round(prob, 4)] for key, prob in answer.top(3)],
                }
            elif isinstance(answer, ScoreAnswer):
                out[qid] = {"type": "score", "score": round(answer.score, 4), "confidence": round(answer.confidence, 4)}
            else:
                out[qid] = {"type": "noul", "noul": round(answer.noul, 4)}
        return out


def _prob(value: Any, *, what: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{what} 不是数字：{value!r} / {what} is not a number: {value!r}") from exc
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError(f"{what} 超出 [0, 1]：{number!r} / {what} out of [0, 1]: {number!r}")
    return number


def _distribution(raw: Any, *, allowed: set[str], what: str) -> dict[str, float]:
    if not isinstance(raw, Mapping):
        raise ValueError(f"{what}.probabilities 缺失 / {what}.probabilities missing")
    out: dict[str, float] = {}
    for key, value in raw.items():
        if str(key) not in allowed:
            raise ValueError(f"{what}.probabilities 含未声明的键 {key!r} / {what}.probabilities has an undeclared key {key!r}")
        out[str(key)] = _prob(value, what=f"{what}.probabilities[{key}]")
    return out


def parse_answers(questions: Mapping[str, Question], raw: Any, *, latency_ms: int = 0) -> Answers:
    """把官方响应体解析成类型化答案；任何越界都 ValueError（传输层再包成 JevResponseInvalid）。"""
    if not isinstance(raw, Mapping):
        raise ValueError("响应不是 JSON 对象 / response is not a JSON object")
    model = raw.get("model")
    if not isinstance(model, str) or not model:
        raise ValueError("response.model 缺失 / response.model missing")
    answers_raw = raw.get("answers")
    if not isinstance(answers_raw, Mapping):
        raise ValueError("response.answers 缺失 / response.answers missing")
    parsed: dict[str, Answer] = {}
    for qid, spec in questions.items():
        item = answers_raw.get(qid)
        if not isinstance(item, Mapping):
            raise ValueError(f"问题 {qid!r} 缺少答案 / answer for question {qid!r} missing")
        kind = item.get("type")
        if isinstance(spec, Choice):
            if kind != "choice":
                raise ValueError(f"{qid}：期望 choice，得到 {kind!r} / {qid}: expected choice, got {kind!r}")
            allowed = {str(key) for key in spec.criteria}
            choice = item.get("choice")
            if choice not in allowed:
                raise ValueError(f"{qid}：选项 {choice!r} 不在声明的选项里 / {qid}: choice {choice!r} is not one of the declared options")
            parsed[qid] = ChoiceAnswer(
                choice=str(choice),
                confidence=_prob(item.get("confidence"), what=f"{qid}.confidence"),
                probabilities=_distribution(item.get("probabilities"), allowed=allowed, what=qid),
            )
        elif isinstance(spec, Score):
            if kind != "score":
                raise ValueError(f"{qid}：期望 score，得到 {kind!r} / {qid}: expected score, got {kind!r}")
            levels = {str(index) for index in range(len(spec.criteria))}
            try:
                score = float(item.get("score"))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{qid}.score 不是数字 / {qid}.score is not a number") from exc
            if not math.isfinite(score) or not 0.0 <= score <= len(spec.criteria) - 1:
                raise ValueError(f"{qid}.score 越界：{score!r} / {qid}.score out of range: {score!r}")
            legend_raw = item.get("legend") or {}
            parsed[qid] = ScoreAnswer(
                score=score,
                confidence=_prob(item.get("confidence"), what=f"{qid}.confidence"),
                probabilities=_distribution(item.get("probabilities"), allowed=levels, what=qid),
                legend={str(key): str(value) for key, value in dict(legend_raw).items()},
            )
        else:
            if kind != "noul":
                raise ValueError(f"{qid}：期望 noul，得到 {kind!r} / {qid}: expected noul, got {kind!r}")
            parsed[qid] = NoulAnswer(noul=_prob(item.get("noul"), what=f"{qid}.noul"))
    usage_raw = raw.get("usage") or {}
    usage = {str(key): int(value) for key, value in dict(usage_raw).items() if isinstance(value, (int, float))}
    return Answers(model=model, usage=usage, answers=parsed, latency_ms=latency_ms)
