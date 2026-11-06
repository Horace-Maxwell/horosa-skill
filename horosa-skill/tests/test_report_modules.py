"""报告模块的分层：读存档、问题拆解、默认解读、质量闸、索引、模板各管一段，builder 只管顺序。

依赖方向要是单向的：`source` 不知道任何判断，默认解读碰不到闸，闸也不看回填。这张表一破，
「闸量的是回填」那类问题（docs/LESSONS.md v0.47.2-dev）就又能悄悄写回来。
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from fakes import FakeClient, FakeJsClient
from horosa_skill import reports
from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.reports import builder as builder_module
from horosa_skill.service import HorosaSkillService
from horosa_skill.testing_payloads import build_sample_payloads

ALLOWED_IMPORTS = {
    "source": set(),
    "question": set(),
    "search_index": set(),
    "gates": {"source"},
    "default_report": {"question", "source"},
    "template": {"gates", "question", "source"},
}


def _report_imports(module: str) -> set[str]:
    tree = ast.parse((Path(reports.__file__).parent / f"{module}.py").read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("horosa_skill.reports"):
            tail = (node.module or "").removeprefix("horosa_skill.reports").lstrip(".")
            found |= {tail} if tail else {alias.name for alias in node.names}
    return found


@pytest.mark.parametrize("module", sorted(ALLOWED_IMPORTS))
def test_each_seam_only_imports_downward(module: str) -> None:
    assert _report_imports(module) <= ALLOWED_IMPORTS[module]


def test_the_default_report_is_kept_away_from_the_gates() -> None:
    """闸不许读默认解读：它量的必须是调用方自己写的。"""
    assert "default_report" not in _report_imports("gates")


def _document(tmp_path: Path, **kwargs: object) -> dict:
    settings = Settings(server_root="http://127.0.0.1:9", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    env = service.run_tool("bazi_birth", build_sample_payloads()["bazi_birth"], query_text="今年事业")
    run, source = service._load_report_source(env.memory_ref.run_id, "bazi_birth")
    return service.report_builder.build_document(run=run, source_artifact=source, language="zh-CN", **kwargs)


def test_the_index_is_built_exactly_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """此前先建一遍只为给清单读三个布尔值，填完 `sections[2]` 再全部重建：大报告的检索文本算两次。"""
    calls = {"index": 0, "text": 0}
    real_index, real_text = builder_module.build_search_index, builder_module.build_plain_text

    def counting_index(**kwargs: object) -> dict:
        calls["index"] += 1
        return real_index(**kwargs)

    def counting_text(**kwargs: object) -> str:
        calls["text"] += 1
        return real_text(**kwargs)

    monkeypatch.setattr(builder_module, "build_search_index", counting_index)
    monkeypatch.setattr(builder_module, "build_plain_text", counting_text)

    _document(tmp_path)

    assert calls == {"index": 1, "text": 1}


def test_the_checklist_section_sits_in_its_place_with_its_real_content(tmp_path: Path) -> None:
    document = _document(tmp_path)
    ids = [section["id"] for section in document["sections"]]
    assert ids[:4] == ["report_metadata", "report_quality", "delivery_checklist", "coverage_contract"]
    section = document["sections"][2]
    assert section["items"] == document["delivery_checklist"]
    assert section["body"].startswith("- 可交付：")
    assert section["body"] in document["plain_text"], "索引建在定稿的清单之后"


def test_nothing_is_patched_by_position() -> None:
    """`sections[2][...] =` 这种写法一个章节挪位就写错地方，而且不报错。"""
    tree = ast.parse(Path(builder_module.__file__).read_text(encoding="utf-8"))
    patched = [node.lineno for node in ast.walk(tree) if isinstance(node, ast.Assign)
               for target in node.targets if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Subscript)]
    assert patched == []


@pytest.mark.parametrize("style", ["analysis", "chart"])
def test_index_checks_agree_with_the_finished_index(tmp_path: Path, style: str) -> None:
    """清单里这三项是从输入判断的（清单的正文本身要进索引），这里拿成品核对。"""
    document = _document(tmp_path, style=style)
    checks = document["delivery_checklist"]["checks"]
    assert checks["has_content_outline"] is bool(document["content_outline"])
    assert checks["has_plain_text"] is bool(document["plain_text"].strip())
    assert checks["has_search_index"] is bool(document["search_index"]["keywords"] and document["search_index"]["search_text"])


def test_index_checks_can_say_no() -> None:
    from horosa_skill.reports.search_index import index_checks

    assert index_checks(sections=[], run={"run_id": "r"}, source={}) == {"has_content_outline": False, "has_plain_text": False, "has_search_index": False}
    assert index_checks(sections=[{"id": "a"}], run={}, source={})["has_search_index"] is False


def test_the_document_is_still_json(tmp_path: Path) -> None:
    assert json.dumps(_document(tmp_path), ensure_ascii=False, default=str)


# ── 技法措辞表是数据：顺序有含义，字段齐，随 wheel 走 ─────────────────────────────────────


def _profile_table() -> dict:
    from horosa_skill.reports import default_report

    return json.loads(default_report._TECHNIQUE_PROFILES_PATH.read_text(encoding="utf-8"))


def test_every_profile_has_its_markers_and_all_four_phrases() -> None:
    table = _profile_table()
    phrases = {"basis", "decision_style", "evidence_name", "recommended_followup"}
    assert len(table["profiles"]) >= 15
    for entry in table["profiles"]:
        assert entry["markers"] and all(isinstance(marker, str) and marker for marker in entry["markers"])
        assert phrases <= set(entry) and all(entry[key] for key in phrases), entry["markers"]
    assert phrases == set(table["default"])


def test_the_first_matching_profile_wins() -> None:
    """`pdchart` 同时命中两条，表里靠前的那条算数：挪动顺序会静默改掉这个工具的措辞。"""
    from horosa_skill.reports.default_report import _technique_report_profile

    table = _profile_table()
    hits = [entry for entry in table["profiles"] if any(marker in "pdchart" for marker in entry["markers"])]
    assert len(hits) == 2, "这条用例靠 pdchart 同时命中两条才有意义"
    assert _technique_report_profile({"tool_name": "pdchart"})["basis"] == hits[0]["basis"]


def test_an_unknown_technique_falls_back_to_the_default_profile() -> None:
    from horosa_skill.reports.default_report import _technique_report_profile

    assert _technique_report_profile({"tool_name": "不存在的技法"})["basis"] == _profile_table()["default"]["basis"]
    assert _technique_report_profile({})["basis"] == _profile_table()["default"]["basis"]


def test_a_label_in_chinese_reaches_the_same_profile_as_the_tool_name() -> None:
    from horosa_skill.reports.default_report import _technique_report_profile

    assert _technique_report_profile({"technique_label": "奇门遁甲"}) == _technique_report_profile({"tool_name": "qimen"})


def test_the_profile_table_ships_in_the_wheel() -> None:
    """AGENTS §6：运行期要读的数据文件必须随 wheel 走，别假定源码树布局。"""
    from horosa_skill.reports import default_report

    guard = (Path(reports.__file__).parents[3] / "scripts" / "verify_wheel_contents.py").read_text(encoding="utf-8")
    relative = default_report._TECHNIQUE_PROFILES_PATH.relative_to(Path(reports.__file__).parents[2]).as_posix()
    assert f'"{relative}"' in guard
