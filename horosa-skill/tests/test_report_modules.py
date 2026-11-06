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
