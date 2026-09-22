"""live smoke（操作者手动跑，CI 永不跑）：三原语各一条打真 API。

门禁只认**显式**环境：`HOROSA_JEV_LIVE=1` 且 key 在 `HOROSA_JEV_API_KEY` / `TYPESAFE_API_KEY`——
key 恰好在环境里不等于同意打网络。
"""

from __future__ import annotations

import os

import pytest

from horosa_skill.decisions.policy import read_api_key

_LIVE = os.environ.get("HOROSA_JEV_LIVE", "").strip() == "1" and read_api_key() is not None
requires_jev_live = pytest.mark.skipif(not _LIVE, reason="set HOROSA_JEV_LIVE=1 and HOROSA_JEV_API_KEY to run the TypeSafe Jev smoke")


@requires_jev_live
def test_live_three_primitives_round_trip() -> None:
    from horosa_skill.decisions.jev_http import JevHttpClient
    from horosa_skill.decisions.questions import Choice, Noul, Score

    client = JevHttpClient(api_key=read_api_key() or "", timeout_s=10.0)
    answers = client.decide(
        state={"user_request": "帮我排一下八字，看看今年财运"},
        questions={
            "family": Choice(instructions="Which technique family does the request ask for?", criteria={"bazi": "八字", "ziwei": "紫微", "unknown": "none"}, abstain="unknown"),
            "wealth": Noul(instructions="Does the request ask about wealth or money luck?"),
            "urgency": Score(instructions="How urgent does the request sound?", criteria=["not urgent", "somewhat urgent", "very urgent"]),
        },
        surface="live_smoke",
    )
    assert answers.model.startswith("jev-")
    assert answers.answers["family"].choice == "bazi" and answers.answers["family"].confidence >= 0.7
    assert answers.answers["wealth"].noul >= 0.7
    assert 0.0 <= answers.answers["urgency"].score <= 2.0
    assert answers.usage.get("input_tokens", 0) > 0
