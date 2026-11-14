"""闸门回包定型（审计 S-04）+ 地点首选 place（S-06）。

修前：114 个技法里 71 个被闸门拦，回包中位 8,179 B、最大 12,526 B，给用户的话只有 725 B；缺省句列着已经给了的键。
负向对照（实跑过）：shape_result 里不走 slim_failure → 第一条红；_unanswered_defaults 恒原样 → 第二条红。
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

from test_result_view_catalogue import call_all, mcp_server, offline_service

from horosa_skill.engine.registry import TOOL_DEFINITIONS, UNADVERTISED_TECHNIQUES
from horosa_skill.testing_payloads import build_sample_payloads

CONFIRM_KEYS = {"agent_confirmed_settings", "defaults_accepted", "clarification_notes"}


def test_gate_refusals_are_small(tmp_path: Path) -> None:
    payloads = build_sample_payloads()
    calls = [(name, (d.mcp_name, {k: v for k, v in payloads[name].items() if k not in CONFIRM_KEYS}))
             for name, d in TOOL_DEFINITIONS.items() if name not in UNADVERTISED_TECHNIQUES]
    sizes = []
    for label, wire, text in call_all(mcp_server(offline_service(tmp_path)), calls):
        body = json.loads(text)
        if body.get("code") == "agent_guidance.required":
            assert "details" not in body["error"] and body["details"]["agent_recovery"]["prompt_to_user"], label
            sizes.append(len(text.encode("utf-8")))
    assert len(sizes) > 40
    assert statistics.median(sizes) <= 3000 and max(sizes) <= 6000, (statistics.median(sizes), max(sizes))


def test_the_defaults_sentence_lists_only_unanswered_keys(tmp_path: Path) -> None:
    payload = {"date": "1990-05-03", "time": "08:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gender": 1, "datetime": "2027"}
    (_, _, text), = call_all(mcp_server(offline_service(tmp_path)), [("sr", ("horosa_predict_solarreturn", payload))])
    defaults = json.loads(text)["details"]["agent_recovery"]["safe_defaults"]
    assert defaults and all(item["field"] != "datetime" for item in defaults)


def test_guidance_intent_rows_ask_for_a_place() -> None:
    from horosa_skill.agent_guidance.catalog import suggest_tools_for_intent

    rows = suggest_tools_for_intent("看看我的八字")
    assert rows and "place | zone+lat+lon" in rows[0]["required_fields"] and "zone" not in rows[0]["required_fields"]
