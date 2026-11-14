"""紫微规则库的正文就是规则，不是一张空命盘骨架（审计 O-02）。

修前：horosa_cn_ziwei_rules {} 缺省阅读视图 →「[起盘信息] 日期：— — … [命中格局] 无」，规则库本身（ZWRules 25,868 + ZWRuleSihua 12,320 字）
只在 response_view=full 的原始树里；照 SKILL「只从 export_text 解释」模型会答「没有命中格局」。
负向对照（实跑过）：export.py 的 ziwei_rules 分支改回命盘快照器 → 红。
"""
from __future__ import annotations

from pathlib import Path

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

RULES = {  # Java /ziwei/rules 回包的形状（live 实测键名，条文截短）
    "ZWRules": {
        "RuleSihua": {"禄": ["主情缘，财禄。"], "忌": ["主收藏，执着。"]},
        "RuleHouses": {"命宫": ["表征此生我所有的一切。", "=="]},
        "RuleHouseType": {"六内宫": ["命宫(实)，财帛宫(虚)"]},
        "ZWStarArray": ["紫微", "天机"],
        "RuleStars": {"三台": ["贵显之曜，主科甲。"]},
    },
    "ZWRuleSihua": {
        "TwoHua": {"禄权": ["主丰盛，财官兴旺。"]},
        "MultiHua": {"象": ["四化就称为象。"]},
        "HuaInHouse": {"禄": {"命宫": ["表这一辈子福禄不缺。"]}},
    },
}


def test_rules_become_sections(tmp_path: Path) -> None:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path,
                        runtime_root=tmp_path / "runtime", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs",
                        trace_enabled=False)
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    service._call_remote = lambda endpoint, body: RULES  # type: ignore[attr-defined]
    result = service.run_tool("ziwei_rules", {}, save_result=False)
    assert result.ok, result.error
    snapshot = result.data["export_snapshot"]
    assert snapshot["section_titles_detected"] == ["四化义", "宫位义", "宫位分类", "主星序", "星曜义", "双化", "多象", "化入各宫"]
    text = snapshot["export_text"]
    assert "禄：主情缘，财禄。" in text and "禄·命宫：表这一辈子福禄不缺。" in text and "紫微、天机" in text
    assert "日期：— —" not in text and "==" not in text   # 不再是空命盘骨架；条文里的分隔符不进正文
