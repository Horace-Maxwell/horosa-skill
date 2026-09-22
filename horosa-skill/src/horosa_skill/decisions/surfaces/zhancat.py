"""S3 六壬占断门类：把「这课问什么事」分到上游 `ZHANDUAN_CATEGORIES` 的闭集里（含 general）。

门类只驱动 [占断向导] 段的取象口径，不是结果敏感设置（分错=多一段不贴题的向导，盘面不变），所以
允许在 conf ≥ τ 时直接填；`general` 与弃权都=不填。键集镜像上游 LRZhanDuanDoc.js（改上游要同步这里）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from horosa_skill.decisions.questions import Choice, ChoiceAnswer

ZHANDUAN_CATEGORIES: dict[str, str] = {
    "hunyin": "婚姻 — marriage, relationship, engagement, divorce",
    "taichan": "胎产 — pregnancy, childbirth, fertility",
    "jibing": "疾病 — illness, health, recovery",
    "caiyun": "财运 — wealth, money, income, investment, business profit",
    "guansong": "官讼 — lawsuit, dispute, legal trouble, official punishment",
    "qiuming": "求名 / 官职 — fame, career promotion, exams, official position, job seeking",
    "shiwu": "失物 / 盗 — lost items, theft, finding something",
    "xingren": "行人 — waiting for a traveller / someone to return or arrive, contacting a person",
    "chuxing": "出行 — travel, moving, going out, journeys",
    "zhaiyun": "宅运 — house, home, real estate, moving house, residence luck",
    "tianshi": "天时 — weather, rain, seasons, natural events",
    "general": "通用 — none of the above, or the question is unspecified / mixed",
}
GENERAL = "general"


def build_zhan_question() -> Choice:
    return Choice(
        instructions=(
            "The user_request is a question for a 大六壬 (Da Liu Ren) divination. Which topic category does the question ask about? "
            "Choose the single best category from the list; choose general when the question names no specific topic or mixes several."
        ),
        criteria=dict(ZHANDUAN_CATEGORIES),
        abstain=GENERAL,
    )


@dataclass(frozen=True)
class ZhanDecision:
    category: str | None
    key: str
    confidence: float
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {"field": "zhanCategory", "value": self.category, "choice": self.key, "confidence": round(self.confidence, 4), "reason": self.reason}


def resolve_zhan(answer: Any, *, tau: float) -> ZhanDecision:
    if not isinstance(answer, ChoiceAnswer):
        return ZhanDecision(None, GENERAL, 0.0, "answer missing")
    if answer.choice == GENERAL:
        return ZhanDecision(None, GENERAL, answer.confidence, "general")
    if answer.confidence < tau:
        return ZhanDecision(None, answer.choice, answer.confidence, f"confidence {answer.confidence:.2f} < tau {tau:.2f}")
    if answer.choice not in ZHANDUAN_CATEGORIES:
        return ZhanDecision(None, answer.choice, answer.confidence, "unknown category")
    return ZhanDecision(answer.choice, answer.choice, answer.confidence, "ok")
