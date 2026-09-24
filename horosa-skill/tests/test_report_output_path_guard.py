"""v0.40.0 P0：报告类 MCP 工具的 `output_path` 只许落在报告输出目录（或 HOROSA_REPORT_OUTPUT_ROOTS 白名单根）内。

此前 `Path(output_path).expanduser().resolve()` 后由 renderers.render_report 用 os.replace 直接覆盖目标——MCP 工具可被
提示注入调用，一次被注入的 horosa_report_render 就能覆盖用户任意文件（如 ~/.zshrc）。现在：缺省仍写存储层缺省产物路径；
相对路径按输出目录解析；越界绝对路径 → `report.output_path_not_allowed`，且**不写任何文件**。负向对照：把闸换回
「resolve 即用」的旧写法，越界写入必须真的发生（证明本测试盯的是闸而不是别的失败）。
"""
from __future__ import annotations

from pathlib import Path

import pytest
from test_service import FakeClient, FakeJsClient

from horosa_skill.config import Settings
from horosa_skill.errors import ToolValidationError
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService


def _service(tmp_path: Path, *, roots: list[Path] | None = None) -> HorosaSkillService:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        report_output_roots=list(roots or []),
    )
    return HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())


def _saved_run(service: HorosaSkillService) -> str:
    result = service.run_tool(
        "chart", {"date": "2026-04-04", "time": "15:58:35", "zone": "8", "lat": "26n04", "lon": "119e19"},
        save_result=True, query_text="报告路径闸测试",
    )
    assert result.ok and result.memory_ref is not None, result.error
    # 没有 AI 正文时 report_render 只回分析模板、不落盘 —— 闸要在真正渲染的路径上测。
    service.record_ai_answer({
        "run_id": result.memory_ref.run_id,
        "ai_answer": "报告路径闸测试回答。",
        "ai_answer_structured": {"executive_summary": "摘要。", "direct_answer": "答。", "analysis_sections": [], "evidence": [], "recommendations": [], "limitations": []},
    })
    return result.memory_ref.run_id


def test_absolute_output_path_outside_the_output_dir_is_refused_and_nothing_is_written(tmp_path: Path) -> None:
    service = _service(tmp_path)
    run_id = _saved_run(service)
    target = tmp_path / "elsewhere" / "zshrc"
    for render in (
        lambda: service.report_render({"run_id": run_id, "format": "json", "output_path": str(target)}),
        lambda: service.technique_report({"run_id": run_id, "format": "json", "output_path": str(target)}),
    ):
        with pytest.raises(ToolValidationError) as caught:
            render()
        assert caught.value.code == "report.output_path_not_allowed"
        details = caught.value.details
        assert details["resolved"] == str(target.resolve()) and str((tmp_path / "runs").resolve()) in details["allowed_roots"]
        assert not target.exists() and not target.parent.exists()
    # 恢复语义齐全（错误码分类 + 人话 + 下一步）。
    from horosa_skill.errors import recovery_for

    assert recovery_for("report.output_path_not_allowed", None)["next_action"] == "use_relative_output_path_or_allowlist_root"


def test_relative_output_path_lands_under_the_output_dir_and_default_stays(tmp_path: Path) -> None:
    service = _service(tmp_path)
    run_id = _saved_run(service)
    rendered = service.report_render({"run_id": run_id, "format": "json", "output_path": "sub/dir/report.json"})
    written = Path(rendered["artifact_path"])
    assert written == (tmp_path / "runs" / "sub" / "dir" / "report.json").resolve() and written.is_file()
    by_default = service.report_render({"run_id": run_id, "format": "json"})
    assert Path(by_default["artifact_path"]).is_file() and (tmp_path / "runs").resolve() in Path(by_default["artifact_path"]).parents
    # `..` 逃逸同样被拦（相对路径也先解析再判归属）。
    with pytest.raises(ToolValidationError) as caught:
        service.report_render({"run_id": run_id, "format": "json", "output_path": "../escaped.json"})
    assert caught.value.code == "report.output_path_not_allowed"
    assert not (tmp_path / "escaped.json").exists()


def test_allowlisted_root_from_settings_admits_that_directory_only(tmp_path: Path) -> None:
    allowed = tmp_path / "Documents"
    service = _service(tmp_path, roots=[allowed])
    run_id = _saved_run(service)
    ok = service.report_render({"run_id": run_id, "format": "json", "output_path": str(allowed / "a" / "r.json")})
    assert Path(ok["artifact_path"]).is_file() and allowed.resolve() in Path(ok["artifact_path"]).parents
    with pytest.raises(ToolValidationError):
        service.report_render({"run_id": run_id, "format": "json", "output_path": str(tmp_path / "Desktop" / "r.json")})


def test_env_knob_populates_settings_roots(monkeypatch, tmp_path: Path) -> None:
    import os

    monkeypatch.setenv("HOROSA_SKILL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("HOROSA_REPORT_OUTPUT_ROOTS", os.pathsep.join([str(tmp_path / "one"), " ", str(tmp_path / "two")]))
    settings = Settings.from_env()
    assert settings.report_output_roots == [tmp_path / "one", tmp_path / "two"]
    monkeypatch.delenv("HOROSA_REPORT_OUTPUT_ROOTS")
    assert Settings.from_env().report_output_roots == []


def test_negative_control_the_old_resolver_would_have_written_outside(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path)
    run_id = _saved_run(service)
    target = tmp_path / "elsewhere" / "zshrc.json"
    monkeypatch.setattr(
        HorosaSkillService, "_report_output_path",
        lambda self, requested, *, default: Path(requested).expanduser().resolve() if requested else default,
    )
    rendered = service.report_render({"run_id": run_id, "format": "json", "output_path": str(target)})
    assert Path(rendered["artifact_path"]) == target.resolve() and target.is_file()  # 旧写法：越界写入真的发生
