"""S4 忠实性第二意见（二档 `snapshot` 才可用，永远只读）：对确定性校验器已抽出的每条 claim，各问一个 Noul
「导出快照是否支持这条断言」，与确定性判定并列给出——**从不**改动 `report["ok"]` / `metrics`。

上游 aiReview.js 的边界照搬：确定性问题由调用方注入判官，判官不 import 校验器。断言 ≤12 条、快照 ≤5000 字
（第三方评测：约 1.26 万 token 后区分度塌陷）。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from horosa_skill.decisions.questions import Noul, NoulAnswer

MAX_CLAIMS = 12
MAX_EXPORT_CHARS = 5000


def build_opinion_state(export_text: str) -> dict[str, Any]:
    text = str(export_text or "")
    if len(text) > MAX_EXPORT_CHARS:
        text = text[:MAX_EXPORT_CHARS].rstrip() + "…<截断>"
    return {"chart_export": text}


def build_opinion_questions(claims: list[Mapping[str, Any]]) -> dict[str, Noul]:
    questions: dict[str, Noul] = {}
    for index, claim in enumerate(claims[:MAX_CLAIMS]):
        text = str(claim.get("text") or "").strip()
        if not text:
            continue
        questions[f"claim_{index}"] = Noul(
            instructions=(
                "The state.chart_export is the machine-generated export of a divination / astrology chart. "
                f"Is the following claim about that chart supported by the export? Claim: {text}"
            ),
            criteria={
                "true": "The export states this fact, or it follows directly from a stated fact",
                "false": "The export contradicts the claim, or does not contain the fact at all",
            },
        )
    return questions


def summarize_opinion(claims: list[Mapping[str, Any]], answers: Mapping[str, Any], *, tau: float) -> dict[str, Any]:
    """与确定性判定逐条对齐：supported ↔ noul ≥ τ；invented/contradicted ↔ noul ≤ 1−τ；其余 undecided。"""
    rows: list[dict[str, Any]] = []
    agree = 0
    judged = 0
    for index, claim in enumerate(claims[:MAX_CLAIMS]):
        answer = answers.get(f"claim_{index}")
        if not isinstance(answer, NoulAnswer):
            continue
        deterministic = str(claim.get("status") or "")
        if answer.noul >= tau:
            model = "supported"
        elif answer.noul <= 1.0 - tau:
            model = "unsupported"
        else:
            model = "undecided"
        det_supported = deterministic == "supported"
        agrees: bool | None
        if model == "undecided":
            agrees = None
        else:
            agrees = (model == "supported") == det_supported
            judged += 1
            agree += int(agrees)
        rows.append({
            "text": str(claim.get("text") or ""),
            "deterministic": deterministic,
            "model": model,
            "supported_probability": round(answer.noul, 4),
            "agrees": agrees,
        })
    return {
        "n": len(rows),
        "n_judged": judged,
        "agreement_rate": round(agree / judged, 4) if judged else None,
        "disagreements": [row for row in rows if row["agrees"] is False],
        "per_claim": rows,
        "note": "只读第二意见：确定性判定（report.ok / metrics）不受影响；模型概率不是真值。",
    }
