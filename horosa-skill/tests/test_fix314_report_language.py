"""报告的 language 只决定中文简 / 繁；别的值写明未生效，不再静默按中文出（审计 O-04）。

修前：language:"en" / "fr" → ok、无 warnings，PDF 与中文版逐字节同大小，模板只多一个 "language":"en" 字段。
负向对照（实跑过）：_note_language 直接 return result → 前两个用例红。
"""
from __future__ import annotations

import pytest

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.testing_payloads import build_sample_payloads


@pytest.fixture()
def run(tmp_path):
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path,
                        runtime_root=tmp_path / "runtime", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs",
                        trace_enabled=False)
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    result = service.run_tool("tarot", build_sample_payloads()["tarot"])   # 本地 JS，离线可跑
    assert result.ok, result.error
    return service, result.memory_ref.run_id


@pytest.mark.parametrize("language", ["en", "fr"])
def test_template_says_an_unsupported_language_had_no_effect(run, language) -> None:
    service, run_id = run
    warnings = service.report_template({"run_id": run_id, "language": language}).get("warnings") or []
    assert any(f"language='{language}' 未生效" in line for line in warnings), warnings


def test_render_says_it_too(run) -> None:
    service, run_id = run
    rendered = service.report_render({"run_id": run_id, "format": "json", "style": "chart", "language": "en"})
    assert any("language='en' 未生效" in line for line in rendered.get("warnings") or []), rendered.get("warnings")


@pytest.mark.parametrize("language", ["zh-CN", "zh-TW", "zh-HK", None])
def test_chinese_tags_are_quiet(run, language) -> None:
    service, run_id = run
    payload = {"run_id": run_id, **({"language": language} if language else {})}
    assert not any("未生效" in line for line in service.report_template(payload).get("warnings") or [])
