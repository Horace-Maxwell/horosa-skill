"""报告 API 的事前检查与写回次序（v0.50.0，评审 R-04 / R-05 / R-08 / R-12 / R-17）。

此前的次序是「起盘 → 写回 AI 解读 → 才看 output_path」，于是：路径被拒时解读已经记到 run 上（下一次不带答案的调用就把它
印成报告）；`report_from_tool` 被拒时技法已经跑完存好，错误里却没有 run_id；目录 / 错扩展名 / 超长名字要么「成功」得
名不副实，要么抛裸 OSError；缺省文件名同一秒内相撞，后写的盖掉先写的。

每条用例都是「旧次序下必红」的：见各用例注释里的负向对照。
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

import pytest
from fakes import FakeClient, FakeJsClient

from horosa_skill import winpaths
from horosa_skill.config import Settings
from horosa_skill.errors import ToolValidationError, recovery_for
from horosa_skill.memory.store import MemoryStore
from horosa_skill.reports import output_path as output_paths
from horosa_skill.service import HorosaSkillService
from horosa_skill.service.api import reports as reports_api

CHART = {"date": "2026-04-04", "time": "15:58:35", "zone": "8", "lat": "26n04", "lon": "119e19"}
ANSWER = "## 总体结论\n\n这次的解读正文。"


def _service(tmp_path: Path) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", db_path=tmp_path / "memory.db",
                        output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt", data_dir=tmp_path / "data")
    return HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())


def _run(service: HorosaSkillService) -> str:
    result = service.run_tool("chart", CHART, save_result=True, query_text="事前检查测试")
    assert result.ok and result.memory_ref is not None, result.error
    return result.memory_ref.run_id


def _stored_answer(service: HorosaSkillService, run_id: str) -> str | None:
    return service.show_memory({"run_id": run_id})["result"].get("ai_answer_text")


def _run_count(service: HorosaSkillService) -> int:
    return len(service.store.query_runs(limit=200, include_payload=False))


# ---------------------------------------------------------------- R-04：写回在产物落盘之后


@pytest.mark.parametrize("bad_path", ["/etc/horosa_preflight.json", "blocker/inside.json", "report.docx"])
def test_a_refused_output_path_leaves_the_run_without_the_answer(tmp_path: Path, bad_path: str) -> None:
    service = _service(tmp_path)
    run_id = _run(service)
    (tmp_path / "runs").mkdir(exist_ok=True)
    (tmp_path / "runs" / "blocker").write_text("我是个文件", encoding="utf-8")
    with pytest.raises(ToolValidationError) as caught:
        service.report_render({"run_id": run_id, "format": "json", "ai_answer_text": ANSWER, "output_path": bad_path})
    assert caught.value.code in {"report.output_path_not_allowed", "report.output_path_unusable"}
    assert caught.value.details["run_id"] == run_id
    assert _stored_answer(service, run_id) is None
    # 没有答案的下一次调用仍然只拿到分析模板，而不是把上一次被拒的答案印成报告。
    again = service.report_render({"run_id": run_id, "format": "json"})
    assert again["mode"] == "analysis_required" and again["final_report_generated"] is False


def test_a_failed_render_leaves_the_run_without_the_answer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service(tmp_path)
    run_id = _run(service)

    def boom(*args: object, **kwargs: object) -> dict:
        raise RuntimeError("渲染器坏了")

    monkeypatch.setattr(reports_api, "render_report", boom)
    with pytest.raises(RuntimeError):
        service.report_render({"run_id": run_id, "format": "json", "ai_answer_text": ANSWER})
    assert _stored_answer(service, run_id) is None
    # 占位的空文件没有留下。
    assert not [p for p in (tmp_path / "runs").rglob("*_report_*") if p.is_file()]


def test_the_result_says_which_answer_was_printed(tmp_path: Path) -> None:
    service = _service(tmp_path)
    run_id = _run(service)
    chart_only = service.report_render({"run_id": run_id, "format": "json", "style": "chart"})
    assert chart_only["answer_source"] is None and chart_only["answer_writeback"] is None
    first = service.report_render({"run_id": run_id, "format": "json", "ai_answer_text": ANSWER})
    assert first["answer_source"] == "request" and first["answer_writeback"]["ok"] is True
    assert _stored_answer(service, run_id) == ANSWER
    reused = service.report_render({"run_id": run_id, "format": "json"})
    assert reused["answer_source"] == "stored" and reused["answer_writeback"] is None
    # 空白答案今天沿用存档里的那份（是否该拒由维护者定）：行为不变，但结果里看得见。
    blank = service.report_render({"run_id": run_id, "format": "json", "ai_answer_text": "   "})
    assert blank["answer_source"] == "stored"
    assert any("存档" in line for line in blank["summary"])


def test_the_document_built_before_the_writeback_equals_the_one_built_after(tmp_path: Path) -> None:
    """写回挪到落盘之后，文档是照「写回之后 run 会是什么样」排的：新答案整份替换旧答案，不是和旧的结构化字段合并。"""
    import json

    service = _service(tmp_path)
    run_id = _run(service)
    service.record_ai_answer({"run_id": run_id, "ai_answer": "旧答案。", "ai_answer_structured": {
        "answer_text": "旧答案。", "recommendations": ["旧建议不该出现"], "limitations": ["旧边界不该出现"]}})
    first = service.report_render({"run_id": run_id, "format": "json", "ai_answer_text": ANSWER})
    second = service.report_render({"run_id": run_id, "format": "json"})  # 用存档里（刚写回的）那份
    docs = [json.loads(Path(item["artifact_path"]).read_text(encoding="utf-8")) for item in (first, second)]
    for doc in docs:
        assert "旧建议不该出现" not in json.dumps(doc, ensure_ascii=False)
    assert docs[0]["ai_report"] == docs[1]["ai_report"]
    assert docs[0]["ai_report"]["human_recommendations"] == [] and docs[0]["ai_report"]["answer_text"] == ANSWER


# ---------------------------------------------------------------- R-05：先检查，再起盘


@pytest.mark.parametrize("override, code", [
    ({"format": "xlsx"}, "report.format_unsupported"),
    ({"style": "fancy"}, "report.invalid_style"),
    ({"output_path": "/etc/horosa_preflight.pdf"}, "report.output_path_not_allowed"),
    ({"output_path": "report.docx"}, "report.output_path_unusable"),
    ({"output_path": "名" * 200 + ".pdf"}, "report.output_path_unusable"),
])
def test_from_tool_refuses_before_running_the_technique(tmp_path: Path, override: dict, code: str) -> None:
    service = _service(tmp_path)
    before = _run_count(service)
    with pytest.raises(ToolValidationError) as caught:
        service.report_from_tool({"tool_name": "chart", "payload": CHART, "format": "pdf", "ai_answer_text": ANSWER, **override})
    assert caught.value.code == code
    assert _run_count(service) == before  # 没起盘、没存档
    assert " / " in str(caught.value)  # 中英双语


def test_errors_raised_after_the_run_exists_carry_its_run_id(tmp_path: Path) -> None:
    from horosa_skill.testing_payloads import build_sample_payloads

    service = _service(tmp_path)
    with pytest.raises(ToolValidationError) as caught:
        service.report_from_tool({"tool_name": "nongli_time", "payload": build_sample_payloads()["nongli_time"], "format": "png"})
    assert caught.value.code == "report.no_chart_content"
    run_id = caught.value.details["run_id"]
    assert service.show_memory({"run_id": run_id})["ok"] is True


# ---------------------------------------------------------------- R-08 / R-17：目录、扩展名、超长名字、写不进去


def test_a_directory_as_output_path_gets_the_default_name_inside_it(tmp_path: Path) -> None:
    service = _service(tmp_path)
    run_id = _run(service)
    (tmp_path / "runs" / "已有目录").mkdir(parents=True)
    for requested in ("已有目录", "新目录/"):
        rendered = service.report_render({"run_id": run_id, "format": "json", "style": "chart", "output_path": requested})
        written = Path(rendered["artifact_path"])
        assert written.is_file() and written.parent == (tmp_path / "runs" / requested.rstrip("/")).resolve()
        assert written.suffix == ".json" and run_id in written.name
        assert rendered["output_path_adjustment"]["reason"] == "directory"
        assert rendered.get("degraded_from") is None
    assert not list((tmp_path / "runs").glob("*.txt"))  # 旧行为：目录旁边冒出一份退化的 TXT


def test_a_missing_extension_is_added_and_reported(tmp_path: Path) -> None:
    service = _service(tmp_path)
    run_id = _run(service)
    for requested, expected in (("noext", "noext.json"), ("报告.终稿", "报告.终稿.json"), ("ok.JSON", "ok.JSON")):
        rendered = service.report_render({"run_id": run_id, "format": "json", "style": "chart", "output_path": requested})
        written = Path(rendered["artifact_path"])
        assert written.name == expected and written.is_file()
        if requested == expected:
            assert "output_path_adjustment" not in rendered
        else:
            assert rendered["output_path_adjustment"] == {"requested": requested, "reason": "extension_added", "extension": ".json"}
            assert any(expected in line for line in rendered["summary"])
            assert not (tmp_path / "runs" / requested).exists()


def test_an_extension_that_names_another_format_is_refused_and_nothing_is_written(tmp_path: Path) -> None:
    service = _service(tmp_path)
    run_id = _run(service)
    with pytest.raises(ToolValidationError) as caught:
        service.report_render({"run_id": run_id, "format": "pdf", "style": "chart", "output_path": "wrong.docx"})
    assert caught.value.code == "report.output_path_unusable"
    details = caught.value.details
    assert details["reason"] == "extension_mismatch" and details["expected_extension"] == ".pdf" and details["run_id"] == run_id
    assert not (tmp_path / "runs" / "wrong.docx").exists()
    assert recovery_for("report.output_path_unusable", None)["next_action"] == "fix_output_path_and_retry"
    for call in (
        lambda: service.report_render({"run_id": run_id, "format": "png", "output_path": "wrong.pdf"}),
        lambda: service.technique_report({"run_id": run_id, "format": "markdown", "output_path": "wrong.pdf"}),
    ):
        with pytest.raises(ToolValidationError) as other:
            call()
        assert other.value.details["reason"] == "extension_mismatch"


def test_an_overlong_name_is_refused_in_the_envelope_and_a_long_legal_name_still_renders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tempfile

    from horosa_skill.reports import renderers

    service = _service(tmp_path)
    run_id = _run(service)
    for call in (
        lambda name: service.report_render({"run_id": run_id, "format": "json", "style": "chart", "output_path": name}),
        lambda name: service.technique_report({"run_id": run_id, "format": "json", "output_path": name}),
    ):
        with pytest.raises(ToolValidationError) as caught:
            call("长" * 100 + ".json")  # 305 字节
        assert caught.value.details["reason"] == "name_too_long" and caught.value.details["limit"] == output_paths.MAX_NAME_BYTES
    # 真机复验抓到的两种：名字长到整条路径也超了 PATH_MAX（stat 抛 OSError 63，不是「不存在」）；每一段都合法、
    # 合起来超了 PATH_MAX。都得是信封里的拒绝，不是裸 OSError。
    (tmp_path / "runs" / "sub").mkdir(parents=True, exist_ok=True)
    with pytest.raises(ToolValidationError) as caught:
        service.report_render({"run_id": run_id, "format": "json", "style": "chart", "output_path": "sub/" + "长" * 400 + ".json"})
    assert caught.value.details["reason"] == "name_too_long"
    # 段数按本机上限算（v0.50.0 windows-smoke：写死 25 段 ≈ 5000 字符，开了长路径的 Windows 上限是 32 767，照常写成了）。
    limit, _unit = output_paths.path_limit()
    with pytest.raises(ToolValidationError) as caught:
        service.report_render({"run_id": run_id, "format": "json", "style": "chart",
                               "output_path": "/".join(["d" * 200] * (limit // 201 + 2)) + "/x.json"})
    assert caught.value.code in {"report.output_path_unusable", "report.output_path_not_allowed"}
    assert not (tmp_path / "runs" / ("d" * 200)).exists()
    # 上限以内的长名字照常写成。临时文件名与目标文件名的长度无关（旧写法 `.{目标名}.xxxxxxxx.tmp` 比目标名长 14 字节，
    # 240 字节的名字只差 1 字节就撞上 255 的上限——上限再放宽一点就是 mkstemp 上的裸 OSError）。
    prefixes: list[str] = []
    real_mkstemp = tempfile.mkstemp

    def spy(*args, **kwargs):
        prefixes.append(str(kwargs.get("prefix") or ""))
        return real_mkstemp(*args, **kwargs)

    monkeypatch.setattr(renderers.tempfile, "mkstemp", spy)
    legal = "a" * (output_paths.MAX_NAME_BYTES - 5) + ".json"
    rendered = service.report_render({"run_id": run_id, "format": "json", "style": "chart", "output_path": legal})
    assert prefixes and all(len(prefix) < 32 for prefix in prefixes)
    assert Path(rendered["artifact_path"]).name == legal and Path(rendered["artifact_path"]).is_file()
    assert not [p for p in (tmp_path / "runs").iterdir() if p.name.endswith(".tmp")]


def test_path_limits_follow_the_platform() -> None:
    assert output_paths.path_limit(os_name="nt", long_paths=False) == (259, "utf-16")
    assert output_paths.path_limit(os_name="nt", long_paths=True) == (32_766, "utf-16")
    assert output_paths.path_limit(os_name="posix", platform="darwin") == (1023, "utf-8")
    assert output_paths.path_limit(os_name="posix", platform="linux") == (4095, "utf-8")


@pytest.mark.parametrize("long_paths", [False, True])
def test_windows_path_limits_are_checked_before_anything_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, long_paths: bool
) -> None:
    """按 Windows 的规则跑（本机模拟）：没开长路径时整条 260 个 UTF-16 单元。每一段都合法、合起来超了——此前 Windows 上
    stat 只说「不存在」，事前检查全过，到建目录才是裸 OSError；开了长路径照常写成。按 UTF-16 数：𡛸 这类扩展 B 字算 2 个单元。"""
    real = output_paths.path_limit
    monkeypatch.setattr(output_paths, "path_limit", lambda: real(os_name="nt", long_paths=long_paths))
    service = _service(tmp_path)
    run_id = _run(service)
    base = len(str(tmp_path / "runs")) + 1
    if base > 198:  # 下面「给目录」那一例要留出 60 + 缺省文件名
        pytest.skip("[host] 临时目录本身就太长，模拟不了 Windows 的 260 上限")
    if long_paths and os.name == "nt" and not winpaths.long_paths_enabled():
        pytest.skip("[host] 这台 Windows 没开长路径，真写不进超过 260 的路径")
    deep = "/".join(["d" * 50] * ((259 - base) // 51 + 2)) + "/x.json"  # 每段都合法，整条刚好超过 259（ASCII：本机字节上限远够）
    short = "a.json"
    attempt = lambda name: service.report_render({"run_id": run_id, "format": "json", "style": "chart", "output_path": name})  # noqa: E731
    if long_paths:
        assert Path(attempt(deep)["artifact_path"]).is_file()
    else:
        with pytest.raises(ToolValidationError) as caught:
            attempt(deep)
        assert caught.value.details["reason"] == "path_refused_by_system"
        assert caught.value.details["unit"] == "utf-16" and caught.value.details["limit"] == 259
        assert not (tmp_path / "runs" / ("d" * 50)).exists(), "被拒时什么都没建"
        with pytest.raises(ToolValidationError) as as_directory:  # 给目录：落进去的缺省文件名也要放得下
            attempt("x" * (259 - base - 60) + "/")
        assert as_directory.value.details["reason"] == "path_refused_by_system"
    assert Path(attempt(short)["artifact_path"]).is_file()
    wide = "𡛸" * 100 + ".json"  # 200 个 UTF-16 单元、405 字节：名字本身已经超了 240（按两种数法取大）
    with pytest.raises(ToolValidationError) as caught:
        attempt(wide)
    assert caught.value.details["reason"] == "name_too_long"


def test_windows_counts_utf16_units_not_code_points(monkeypatch: pytest.MonkeyPatch) -> None:
    """扩展 B 字（𡛸）在 Windows 的路径长度里算 2 个单元。按码位数会放过一条 Windows 写不进去的路径。"""
    real = output_paths.path_limit
    monkeypatch.setattr(output_paths, "path_limit", lambda: real(os_name="nt", long_paths=False))
    output_paths.check_path_length(Path("/a/" + "𡛸" * 100 + "/x.json"), requested="ok")  # 3 + 200 + 1 + 32 = 236
    with pytest.raises(ToolValidationError) as caught:
        output_paths.check_path_length(Path("/a/" + "𡛸" * 115 + "/x.json"), requested="x")  # 码位 152，UTF-16 266
    assert caught.value.details == {"reason": "path_refused_by_system", "requested": "x", "path_length": 266, "limit": 259, "unit": "utf-16"}


def test_a_location_that_cannot_be_written_is_refused(tmp_path: Path) -> None:
    service = _service(tmp_path)
    run_id = _run(service)
    (tmp_path / "runs" / "blocker").write_text("我是个文件", encoding="utf-8")
    with pytest.raises(ToolValidationError) as caught:
        service.report_render({"run_id": run_id, "format": "json", "style": "chart", "output_path": "blocker/x.json"})
    assert caught.value.details["reason"] == "parent_not_directory"
    if os.name != "nt" and os.geteuid() != 0:
        locked = tmp_path / "runs" / "locked"
        locked.mkdir()
        locked.chmod(0o500)
        try:
            with pytest.raises(ToolValidationError) as denied:
                service.report_render({"run_id": run_id, "format": "json", "style": "chart", "output_path": "locked/x.json"})
            assert denied.value.details["reason"] == "not_writable"
        finally:
            locked.chmod(0o700)


# ---------------------------------------------------------------- R-12：缺省文件名不相撞


def test_default_names_never_collide_within_a_second(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service(tmp_path)
    run_id = _run(service)
    service.record_ai_answer({"run_id": run_id, "ai_answer": ANSWER})
    fixed = tmp_path / "runs" / "2026" / "11" / "11"
    # 把「现在」钉死在同一秒：存储层的缺省名只精确到秒。
    monkeypatch.setattr(
        service.store, "default_report_path",
        lambda *, run_id, tool_name, format_name: fixed / f"{run_id}_{tool_name}_report_20261111T000000Z.{format_name.lower()}",
    )
    renders = [
        service.report_render({"run_id": run_id, "format": "json", "style": style})
        for style in ("chart", "analysis", "chart", "chart")
    ]
    paths = [Path(item["artifact_path"]) for item in renders]
    assert len(set(paths)) == 4 and all(path.is_file() and path.stat().st_size > 0 for path in paths)
    assert "_chart_report_" in paths[0].name and "_analysis_report_" in paths[1].name  # 两种样式一眼分得开
    assert paths[2].name == paths[0].name.replace(".json", "-2.json") and paths[3].name.endswith("-3.json")
    technique = [service.technique_report({"run_id": run_id, "format": "markdown"}) for _ in range(2)]
    assert len({item["artifact_path"] for item in technique}) == 2


def test_reserve_hands_each_concurrent_caller_its_own_name(tmp_path: Path) -> None:
    target = tmp_path / "out" / "report.pdf"
    claimed: list[Path] = []
    lock = threading.Lock()

    def claim() -> None:
        path = output_paths.reserve(target)
        with lock:
            claimed.append(path)

    threads = [threading.Thread(target=claim) for _ in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(set(claimed)) == 12 and target in claimed
    assert {path.name for path in claimed} == {"report.pdf", *(f"report-{n}.pdf" for n in range(2, 13))}
    # 空壳可以收走；写了内容的不动。
    claimed[0].write_text("内容", encoding="utf-8")
    for path in claimed:
        output_paths.release(path)
    assert [path for path in claimed if path.exists()] == [claimed[0]]


# ---------------------------------------------------------------- C-05：报告不能盖掉存档、manifest 和别的已有文件


def _stored_files(service: HorosaSkillService, run_id: str) -> dict[Path, bytes]:
    artifacts = service.show_memory({"run_id": run_id})["result"]["artifacts"]
    paths = {Path(item["path"]) for item in artifacts if item.get("path")}
    assert any(path.name.endswith("_manifest.json") for path in paths) and len(paths) >= 2
    return {path: path.read_bytes() for path in paths}


def test_a_report_never_replaces_the_runs_own_stored_files(tmp_path: Path) -> None:
    """评审 C-05（P0 丢数据）：输出根就是存档目录，点名这条 run 自己的存档（或 manifest）就被整份替换，之后这条 run 再也出不了
    报告（report.export_contract_missing）。旧代码下这里写成功、存档被换成报告——断言「字节不变」必红。"""
    service = _service(tmp_path)
    run_id = _run(service)
    before = _stored_files(service, run_id)
    for path in before:
        for call in (
            lambda: service.report_render({"run_id": run_id, "format": "json", "style": "chart", "output_path": str(path)}),
            lambda: service.report_from_tool({"tool_name": "chart", "payload": CHART, "format": "json", "style": "chart",
                                              "output_path": str(path)}),
        ):
            with pytest.raises(ToolValidationError) as caught:
                call()
            assert caught.value.code == "report.output_path_unusable" and caught.value.details["reason"] == "existing_file"
    assert {path: path.read_bytes() for path in before} == before
    assert _run_count(service) == 1  # report_from_tool 在起盘之前就拒了
    # 存档完好：这条 run 照常出报告
    assert service.report_render({"run_id": run_id, "format": "json", "style": "chart"})["ok"] is True


@pytest.mark.parametrize("font_host", ["host", "no_cjk_font"], indirect=True)  # 补字链与这里无关：两种现场就够
def test_an_existing_file_of_the_users_is_kept_but_a_report_can_be_rewritten(tmp_path: Path, font_host: str) -> None:
    service = _service(tmp_path)
    run_id = _run(service)
    mine = tmp_path / "runs" / "我的笔记.json"
    mine.parent.mkdir(parents=True, exist_ok=True)
    mine.write_text('{"mine": true}', encoding="utf-8")
    with pytest.raises(ToolValidationError) as caught:
        service.report_render({"run_id": run_id, "format": "json", "style": "chart", "output_path": "我的笔记.json"})
    assert caught.value.details["reason"] == "existing_file" and mine.read_text(encoding="utf-8") == '{"mine": true}'
    assert "不替换" in str(caught.value) and "not replaced" in str(caught.value)
    # 报告自己写过的那份（记忆库里记着）照旧可以重写
    first = service.report_render({"run_id": run_id, "format": "json", "style": "chart", "output_path": "同一份.json"})
    again = service.report_render({"run_id": run_id, "format": "json", "style": "chart", "output_path": "同一份.json"})
    assert first["artifact_path"] == again["artifact_path"]
    # ICS 同一条规则
    from horosa_skill.testing_payloads import build_sample_payloads

    (tmp_path / "runs" / "日历.ics").write_text("BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n", encoding="utf-8")
    fd = service.run_tool("firdaria", build_sample_payloads()["firdaria"], save_result=True).memory_ref.run_id
    with pytest.raises(ToolValidationError) as ics:
        service.report_render({"run_id": fd, "format": "ics", "output_path": "日历.ics"})
    assert ics.value.details["reason"] == "existing_file"
    # 多张 PNG 的 _1 / _2 也一样：点名 x.png，已有一个不是报告的 x_2.png → 拒绝，一个文件都不写
    (tmp_path / "runs" / "x_2.png").write_bytes(b"not a report")
    sr = service.run_tool("solarreturn", build_sample_payloads()["solarreturn"], save_result=True).memory_ref.run_id
    with pytest.raises(ToolValidationError) as png:
        service.report_render({"run_id": sr, "format": "png", "output_path": "x.png"})
    from horosa_skill.reports.renderers import SIMPLIFIED, _drawing_font_files

    if _drawing_font_files(SIMPLIFIED) is None:  # 没有中文 TrueType（CI ubuntu）：PNG 先因字体被拒，同样一个文件都不写
        assert png.value.code == "report.png_font_unavailable"
    else:
        assert png.value.details["reason"] == "existing_file"
    assert not (tmp_path / "runs" / "x.png").exists() and not (tmp_path / "runs" / "x_1.png").exists()
    assert (tmp_path / "runs" / "x_2.png").read_bytes() == b"not a report"


def test_the_memory_store_and_its_neighbours_are_never_a_report_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service(tmp_path)
    run_id = _run(service)
    monkeypatch.setattr(service.settings, "report_output_roots", [tmp_path])
    for target in ("memory.db", "memory.db-wal", "data/profiles/new.json", "rt/x.json"):
        with pytest.raises(ToolValidationError) as caught:
            service.report_render({"run_id": run_id, "format": "json", "style": "chart", "output_path": str(tmp_path / target)})
        assert caught.value.details["reason"] in {"store_area", "extension_mismatch"}, target
    db = (tmp_path / "memory.db").read_bytes()
    with pytest.raises(ToolValidationError) as caught:
        service.report_render({"run_id": run_id, "format": "json", "style": "chart", "output_path": str(tmp_path / "rt")})
    assert caught.value.details["reason"] == "store_area"
    assert (tmp_path / "memory.db").read_bytes()[:16] == db[:16] == b"SQLite format 3\x00"


def test_default_png_sets_never_share_a_numbered_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """多张 PNG 的缺省名：上一次占了 X.png 写 X_1 / X_2 后把空的 X.png 收走；同一秒内下一次又占到 X.png，旧代码就把 X_1 / X_2 盖掉。"""
    from horosa_skill.reports import chart_png
    from horosa_skill.testing_payloads import build_sample_payloads

    monkeypatch.setattr(chart_png, "missing_glyphs", lambda texts: [])
    service = _service(tmp_path)
    run_id = service.run_tool("solarreturn", build_sample_payloads()["solarreturn"], save_result=True).memory_ref.run_id
    fixed = service.store.default_report_path(run_id=run_id, tool_name="solarreturn", format_name="png")
    monkeypatch.setattr(service.store, "default_report_path", lambda **_: fixed)
    try:
        first = service.report_render({"run_id": run_id, "format": "png"})
    except ToolValidationError as exc:  # 本机没有 CJK TrueType 字体
        pytest.skip(f"[host] PNG needs a CJK font here: {exc.code}")
    second = service.report_render({"run_id": run_id, "format": "png"})
    names = [card["path"] for result in (first, second) for card in result["files"]]
    assert len(names) == len(set(names)) == 4


# ---------------------------------------------------------------- R-17：错误消息双语、带下一步


def test_run_not_found_and_invalid_format_speak_both_languages(tmp_path: Path) -> None:
    service = _service(tmp_path)
    with pytest.raises(ToolValidationError) as missing:
        service.report_render({"run_id": "no-such-run", "format": "pdf"})
    assert missing.value.code == "report.run_not_found" and missing.value.details["run_id"] == "no-such-run"
    text = str(missing.value)
    assert "找不到" in text and " / " in text and "horosa_memory_query" in text
    run_id = _run(service)
    for call, code in (
        (lambda: service.report_render({"run_id": run_id, "format": "xlsx"}), "report.format_unsupported"),
        (lambda: service.technique_report({"run_id": run_id, "format": "xlsx"}), "report.technique.invalid_format"),
    ):
        with pytest.raises(ToolValidationError) as bad:
            call()
        assert bad.value.code == code and "xlsx" in str(bad.value) and " / " in str(bad.value)
        assert "pdf" in bad.value.details["accepted"]  # 与其余「值不在可选表里」的错误同一个键
    assert recovery_for("report.format_unsupported", None)["agent_recovery"]["kind"] == "input"
