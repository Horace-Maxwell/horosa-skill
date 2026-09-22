"""S2 抽取：只把用户原话里**明说**的结果敏感设置变成「已提供」——双钥：词表先出候选，Jev 在候选里选，
选中的一侧必须有词表证据且置信 ≥ τ 才填；否则仍走澄清门问用户。永不替用户选默认值（铁律 2）。

P1 只做 `gender`（神数 / 八字 / 紫微 / 六壬行年等按性别分列的技法）；值填中文标签，由
`input_normalization` 按各工具映射 0/1。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from horosa_skill.decisions.questions import Choice, ChoiceAnswer

NOT_STATED = "not_stated"

FEMALE_TERMS: tuple[str, ...] = (
    "老婆", "妻子", "太太", "媳妇", "夫人", "女儿", "闺女", "母亲", "妈妈", "女朋友", "女友", "女士", "小姐", "姐姐",
    "妹妹", "奶奶", "外婆", "姥姥", "阿姨", "姑姑", "婶婶", "女性", "女生", "女孩", "女的", "女命", "坤造", "她",
)
# 「他」在现代汉语里既指男性也泛指，不算「明说」；「她」是有标记的女性代词，算。
MALE_TERMS: tuple[str, ...] = (
    "老公", "丈夫", "先生", "儿子", "父亲", "爸爸", "男朋友", "男友", "男士", "哥哥", "弟弟", "爷爷", "外公", "姥爷",
    "叔叔", "舅舅", "伯伯", "男性", "男生", "男孩", "男的", "男命", "乾造",
)
GENDER_LABEL = {"female": "女", "male": "男"}


@dataclass(frozen=True)
class GenderCandidates:
    female: tuple[str, ...]
    male: tuple[str, ...]

    @property
    def any(self) -> bool:
        return bool(self.female or self.male)


def gender_candidates(text: str) -> GenderCandidates:
    raw = str(text or "")
    female = tuple(term for term in FEMALE_TERMS if term in raw)
    male = tuple(term for term in MALE_TERMS if term in raw)
    return GenderCandidates(female=female, male=male)


def build_gender_question() -> Choice:
    return Choice(
        instructions=(
            "The user_request asks for a Chinese astrology / divination chart for some person (the chart subject). "
            "Judging ONLY from what the text explicitly states, what is the chart subject's gender? "
            "Choose female if the subject is described as 老婆/妻子/太太/女儿/母亲/女朋友/女性/女命 or similar, "
            "male if described as 老公/丈夫/先生/儿子/父亲/男朋友/男性/男命 or similar. "
            "If the subject's gender is not explicitly stated, or the gendered word refers to a different person than the subject, choose not_stated."
        ),
        criteria={
            "female": "The chart subject is explicitly female（女 / 老婆 / 妻子 / 女儿 / 母亲 / 女命 …）",
            "male": "The chart subject is explicitly male（男 / 老公 / 丈夫 / 儿子 / 父亲 / 男命 …）",
            NOT_STATED: "Not stated for the subject, or ambiguous",
        },
        abstain=NOT_STATED,
    )


@dataclass(frozen=True)
class GenderDecision:
    value: str | None  # "女" / "男"
    key: str
    confidence: float
    evidence: tuple[str, ...]
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {"field": "gender", "value": self.value, "choice": self.key, "confidence": round(self.confidence, 4), "evidence": list(self.evidence), "reason": self.reason}


def resolve_gender(answer: Any, candidates: GenderCandidates, *, tau: float) -> GenderDecision:
    if not isinstance(answer, ChoiceAnswer):
        return GenderDecision(None, NOT_STATED, 0.0, (), "answer missing")
    if answer.choice == NOT_STATED:
        return GenderDecision(None, NOT_STATED, answer.confidence, (), "not_stated")
    evidence = candidates.female if answer.choice == "female" else candidates.male
    if not evidence:
        return GenderDecision(None, answer.choice, answer.confidence, (), "no lexicon evidence for the chosen side (double-key failed)")
    if answer.confidence < tau:
        return GenderDecision(None, answer.choice, answer.confidence, evidence, f"confidence {answer.confidence:.2f} < tau {tau:.2f}")
    return GenderDecision(GENDER_LABEL[answer.choice], answer.choice, answer.confidence, evidence, "ok")
