import ast
import collections
import json
from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "export_snapshots"
REGISTRY_SOURCE = Path(__file__).resolve().parents[1] / "src/horosa_skill/exports/registry.py"


def test_registry_tables_have_no_duplicate_keys() -> None:
    """重复字面量键 = Python 静默保留最后一个，前面那份整条消失。

    registry 的每张表都是「技法键 → 段列表」，一个技法的条目常常分散在几百行里按主题分组，
    给某族补段时非常容易在另一处又写一个同名键——解释器不报错，导入后前一份 list 直接不存在，
    症状是「明明加了 optional 段，missing 里还在报」。本轮补 v13 段时就现场踩了一次
    （cetian / astrochart_like 各一处）。
    """
    tree = ast.parse(REGISTRY_SOURCE.read_text(encoding="utf-8"))
    problems: list[str] = []
    named: dict[int, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict) and isinstance(node.targets[0], ast.Name):
            named[id(node.value)] = node.targets[0].id
    # ast.walk 全量扫（含嵌套 dict）——只看顶层 Assign 会漏掉 AnnAssign/嵌套字面量整类位置。
    for dict_node in ast.walk(tree):
        if not isinstance(dict_node, ast.Dict):
            continue
        node_value = dict_node
        name = named.get(id(node_value), f"<dict@L{dict_node.lineno}>")
        keys = [key.value for key in node_value.keys if isinstance(key, ast.Constant)]
        for key, count in collections.Counter(keys).items():
            if count > 1:
                lines = [
                    k.lineno for k in node_value.keys if isinstance(k, ast.Constant) and k.value == key
                ]
                problems.append(f"{name}[{key!r}] appears {count}× at lines {lines}")
    assert problems == [], "合并到同一个键上，别新增重复键：\n  " + "\n  ".join(problems)


def make_service(tmp_path) -> HorosaSkillService:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    return HorosaSkillService(settings, store=store)


def load_export_fixture_catalog() -> list[dict]:
    return json.loads((FIXTURE_ROOT / "catalog.json").read_text(encoding="utf-8"))


def test_export_registry_returns_ai_export_catalog(tmp_path) -> None:
    service = make_service(tmp_path)

    result = service.run_tool("export_registry", {"technique": "qimen"}, save_result=False)

    assert result.ok is True
    assert result.data["settings_key"] == "horosa.ai.export.settings.v1"
    assert result.data["settings_version"] == 14  # v0.28.0: 上游 v3.9.2 十四段/八键补齐
    assert result.data["selected_technique"]["key"] == "qimen"
    assert "奇门演卦" in result.data["selected_technique"]["preset_sections"]


def test_export_parse_normalizes_legacy_titles_and_filters_forbidden_sections(tmp_path) -> None:
    service = make_service(tmp_path)
    content = "\n".join(
        [
            "[起盘信息]",
            "排盘参数",
            "",
            "[右侧栏目]",
            "这里不该进入最终导出",
            "",
            "[八宫]",
            "这里是八宫详解内容",
            "",
            "[演卦]",
            "这里是奇门演卦内容",
        ]
    )

    result = service.run_tool(
        "export_parse",
        {
            "technique": "qimen",
            "content": content,
            "selected_sections": ["起盘信息", "八宫详解", "奇门演卦"],
        },
        save_result=False,
    )

    assert result.ok is True
    assert result.data["section_titles_detected"] == ["起盘信息", "盘面要素", "八宫详解", "奇门演卦"]
    assert "这里不该进入最终导出" not in result.data["export_text"]
    assert "这里是八宫详解内容" in result.data["export_text"]
    assert "这里是奇门演卦内容" in result.data["export_text"]


def test_export_parse_can_persist_memory(tmp_path) -> None:
    service = make_service(tmp_path)

    result = service.run_tool(
        "export_parse",
        {
            "technique": "bazi",
            "content": "[起盘信息]\n测试",
        },
        save_result=True,
    )

    assert result.ok is True
    assert result.memory_ref is not None
    queried = service.store.query_runs(tool="export_parse")
    assert len(queried) == 1


@pytest.mark.parametrize("fixture_case", load_export_fixture_catalog(), ids=lambda case: case["name"])
def test_export_parse_fixture_catalog_matches_app_snapshot_shapes(tmp_path, fixture_case) -> None:
    service = make_service(tmp_path)
    content = (FIXTURE_ROOT / fixture_case["fixture_file"]).read_text(encoding="utf-8")

    result = service.run_tool(
        "export_parse",
        {
            "technique": fixture_case["technique"],
            "content": content,
            "selected_sections": fixture_case["selected_sections"],
        },
        save_result=True,
    )

    assert result.ok is True
    assert result.memory_ref is not None
    assert result.data["section_titles_detected"] == fixture_case["expected_detected"]
    assert result.data["selected_sections"] == fixture_case["selected_sections"]
    assert result.data["export_text"]
    assert result.data["settings_used"]["sections"][fixture_case["technique"]] == fixture_case["selected_sections"]

    for expected in fixture_case["expected_in_export"]:
        assert expected in result.data["export_text"]

    for excluded in fixture_case["expected_excluded"]:
        assert excluded not in result.data["export_text"]

    queried = service.store.query_runs(tool="export_parse", include_payload=True)
    assert len(queried) == 1
    payload = queried[0]["artifacts"][0]["payload"]
    assert payload["data"]["selected_sections"] == fixture_case["selected_sections"]
    assert payload["data"]["section_titles_detected"] == fixture_case["expected_detected"]

