"""玄史检索：写成 `query` 也按检索词用；没有检索词的全文检索拒绝并说明，不回「命中 0 条」（审计 S-18）。

修前：`horosa_knowledge_xuanshi {"query":"袁天罡"}` → ok、「命中 0 条」、warnings 空（参数叫 q，query 被静默忽略）；不带参数也一样。
负向对照（实跑过）：去掉 XuanshiInput._query_is_q → 第一个用例红；去掉 runner 的空检索拒绝 → 第二个用例红。
"""
from __future__ import annotations

import pytest

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService


def _service(tmp_path, sent: list):
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path,
                        runtime_root=tmp_path / "runtime", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs",
                        trace_enabled=False)
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    service._call_remote = lambda endpoint, body: sent.append((endpoint, body)) or {"total": 0, "items": []}  # type: ignore[attr-defined]
    return service


def test_query_is_read_as_the_search_term(tmp_path) -> None:
    sent: list = []
    result = _service(tmp_path, sent).run_tool("xuanshi", {"query": "袁天罡"}, save_result=False)
    assert result.ok, result.error
    assert sent == [("/xuanshi/search", {"q": "袁天罡"})]
    assert not any("query" in line and "不是本技法的参数" in line for line in result.warnings), result.warnings


@pytest.mark.parametrize("payload", [{}, {"q": "  "}, {"action": "search"}])
def test_a_search_without_a_term_is_refused_not_answered_with_zero_hits(tmp_path, payload) -> None:
    sent: list = []
    result = _service(tmp_path, sent).run_tool("xuanshi", payload, save_result=False)
    assert result.ok is False and result.error.code == "tool.missing_field" and sent == []
    assert result.error.details["missing"] == ["q"]
    assert "取自用户的问题" in result.error.details["agent_recovery"]["prompt_to_user"]


def test_browsing_actions_still_need_no_term(tmp_path) -> None:
    sent: list = []
    result = _service(tmp_path, sent).run_tool("xuanshi", {"action": "summary"}, save_result=False)
    assert result.ok and sent and sent[0][0] == "/xuanshi/summary"
