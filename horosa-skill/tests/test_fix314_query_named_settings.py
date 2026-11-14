"""dispatch：用户在问句里点名的设置（牌阵）照用并写明，不再无声给缺省（审计 S-12）。

修前：horosa_dispatch {"query":"Pull a Celtic cross tarot spread about my career", context, defaults_accepted} → ok、「三张(过去·现在·未来)」、
warnings 空。dispatch 只从原话取年份。词表确定性匹配：唯一命中且调用方没另给才采用；同时提到两种不替用户挑。
负向对照（实跑过）：plan_tool 不调 _apply_query_settings → 前两个用例红。
"""
from __future__ import annotations

from pathlib import Path

from horosa_skill.config import Settings
from horosa_skill.engine import dispatch_plan
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

CONTEXT = {"date": "2026-11-14", "time": "10:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"}


def _inputs(query: str, **preferences) -> dispatch_plan.PlanInputs:
    return dispatch_plan.PlanInputs(query=query, birth={}, birth_fields={}, context=dict(CONTEXT), preferences=preferences,
                                    inner=None, outer=None, subject_year=None, gua_names=[], confirmation={})


def test_a_named_spread_is_used_and_disclosed_end_to_end(tmp_path: Path) -> None:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path,
                        runtime_root=tmp_path / "runtime", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs",
                        trace_enabled=False)
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    result = service.dispatch({"query": "Pull a Celtic cross tarot spread about my career", "context": CONTEXT,
                               "defaults_accepted": True, "tools": ["tarot"]})
    data = result if isinstance(result, dict) else result.model_dump()
    assert data["normalized_inputs"]["tarot"]["spread"] == "celtic"
    assert any("取自问句：凯尔特十字" in line for line in data["warnings"]), data["warnings"]


def test_chinese_wording_and_explicit_choice() -> None:
    plans, warnings = dispatch_plan.plan_all(["tarot"], _inputs("用凯尔特十字看看感情"))
    assert plans[0].payload["spread"] == "celtic" and warnings
    plans, warnings = dispatch_plan.plan_all(["tarot"], _inputs("用凯尔特十字看看感情", spread="three"))
    assert plans[0].payload["spread"] == "three" and not any("取自问句" in w for w in warnings)   # 显式给的照用


def test_two_named_spreads_are_not_chosen_for_the_user() -> None:
    plans, warnings = dispatch_plan.plan_all(["tarot"], _inputs("凯尔特十字还是马蹄阵好"))
    assert "spread" not in plans[0].payload and any("没有替你选" in w for w in warnings)
