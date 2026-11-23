"""塔罗 [对读] 是条件段（vendored reportText：两两解读有行才写段头）。v0.53.0-dev 前导出目录把它登成恒出段——确定性种子下的
巧合；起卦改真随机后，抽到没有成对关系的牌（单张、三张全是小牌且无配偶对……）就不出，surface_audit 在 live 上实红
「missing: 对读」。这里用确定性种子各钉一例：出 / 不出都不算缺段。负向对照：把「对读」移出条件段 → 不出的那例报缺段。"""

from __future__ import annotations

import shutil

import pytest

from horosa_skill.config import Settings
from horosa_skill.exports.registry import AI_EXPORT_OPTIONAL_SECTIONS
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.testing_payloads import build_sample_payloads

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="[host] node not on PATH")


@requires_node
@pytest.mark.parametrize(("seed", "has_pairs"), [("a", False), ("e", True)])
def test_pair_reading_section_is_conditional(tmp_path, seed: str, has_pairs: bool) -> None:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", runtime_root=tmp_path / "rt",
                        db_path=tmp_path / "m.db", output_dir=tmp_path / "runs")
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    env = service.run_tool("tarot", {**build_sample_payloads()["tarot"], "spread": "single", "seed": seed}, save_result=False)
    assert env.ok, env.error
    export = env.data["export_snapshot"]
    assert ("对读" in export["section_titles_detected"]) is has_pairs
    assert export["missing_selected_sections"] == [] and "对读" in AI_EXPORT_OPTIONAL_SECTIONS["tarot"]
