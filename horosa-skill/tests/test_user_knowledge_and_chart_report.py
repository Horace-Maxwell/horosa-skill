"""自备知识库（每次计算按点名附加上下文）+ 完整排盘报告（style=chart，不经 AI 也能出全盘 PDF / DOCX）。"""
from __future__ import annotations

import json
import os
import re
import zipfile
from pathlib import Path

import pytest
from fakes import FakeClient, FakeJsClient

from horosa_skill.config import Settings
from horosa_skill.errors import ToolValidationError
from horosa_skill.knowledge import user as user_knowledge
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.testing_payloads import build_sample_payloads


def _settings(tmp_path: Path, **extra) -> Settings:
    return Settings(
        server_root="http://127.0.0.1:9",
        chart_server_root="http://127.0.0.1:9",
        runtime_root=tmp_path / "runtime",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        user_knowledge_dir=tmp_path / "kb",
        **extra,
    )


def _service(tmp_path: Path, **extra) -> HorosaSkillService:
    settings = _settings(tmp_path, **extra)
    return HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())


def _write(root: Path, name: str, body: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _seed(root: Path) -> None:
    _write(root, "滴天髓笔记.md", "---\ntitle: 滴天髓笔记\ntechniques: bazi_birth, xiaoliuren\ntags: 古籍, 命理\n---\n天道：欲识三元万法宗。\n")
    _write(root, "占卜/求财心得.txt", "---\ntags: 求财\n---\n小六壬遇速喜，求财宜速。\n")
    _write(root, "通用.md", "---\ntechniques: *\n---\n先看盘面再看资料。\n")


def _link_outside(outside_file: Path, root: Path) -> None:
    """在知识库里放指向目录外的链接，断言它不被读到。

    Windows 普通用户建不了文件符号链接（`WinError 1314`，要开发者模式或管理员；托管 runner 是管理员，所以 CI 一直绿、维护机红——
    v0.43.1-dev 台账）。Windows 上另建一个目录联接（junction，无需特权，也是普通用户真能造出来的形状）。
    """
    try:
        os.symlink(outside_file, root / "链接.md")
    except OSError:
        if os.name != "nt":
            raise
    if os.name == "nt":
        import _winapi

        _winapi.CreateJunction(str(outside_file.parent), str(root / "联接目录"))
        assert (root / "联接目录" / outside_file.name).exists(), "junction 建好了，读不到是 loader 的功劳"


# ── 条目读取 ───────────────────────────────────────────────────────────────


def test_entries_parse_front_matter_subfolders_and_skip_unsafe_files(tmp_path: Path) -> None:
    root = tmp_path / "kb"
    _seed(root)
    _write(root, ".hidden/秘.md", "不该被读到")
    _write(root, "空.md", "---\ntitle: 空\n---\n")
    (root / "大.md").write_bytes(b"x" * (user_knowledge.MAX_FILE_BYTES + 1))
    outside = _write(tmp_path / "outside", "外.md", "目录外的文件")
    _link_outside(outside, root)

    entries = {e.id: e for e in user_knowledge.list_entries(_settings(tmp_path))}
    assert set(entries) == {"滴天髓笔记", "占卜/求财心得", "通用"}
    note = entries["滴天髓笔记"]
    assert note.title == "滴天髓笔记" and note.text == "天道：欲识三元万法宗。"
    assert note.techniques == {"bazi_birth", "xiaoliuren"} and note.tags == {"古籍", "命理"}
    assert entries["占卜/求财心得"].title == "求财心得"  # 没写 title 用文件名


def test_missing_folder_is_an_empty_knowledge_base(tmp_path: Path) -> None:
    assert user_knowledge.list_entries(_settings(tmp_path)) == []
    context = user_knowledge.build_context(_settings(tmp_path), ["auto", "不存在"], tool_name="xiaoliuren")
    assert context["entries"] == [] and context["missing"] == ["不存在"] and context["available"] == 0


# ── 点名选择 ───────────────────────────────────────────────────────────────


def test_selection_by_id_title_tag_and_auto_dedupes_and_reports_missing(tmp_path: Path) -> None:
    _seed(tmp_path / "kb")
    settings = _settings(tmp_path)
    context = user_knowledge.build_context(
        settings, ["占卜/求财心得", "滴天髓笔记", "#古籍", "auto", "没有这条", "#无此标签"], tool_name="xiaoliuren"
    )
    picked = [(e["id"], e["matched_by"]) for e in context["entries"]]
    # 先到先得、同一条只出现一次；auto 只补 techniques 命中本技法（或 *）的条目。
    assert picked == [("占卜/求财心得", "name"), ("滴天髓笔记", "name"), ("通用", "auto")]
    assert context["missing"] == ["没有这条", "#无此标签"]
    assert "不是星阙引擎的输出" in context["note"]
    warning = user_knowledge.missing_warning(context)
    assert warning and "没有这条" in warning

    auto_other = user_knowledge.build_context(settings, "auto", tool_name="ziwei_birth")
    assert [e["id"] for e in auto_other["entries"]] == ["通用"]  # 别的技法：只有 * 条目
    by_tag = user_knowledge.build_context(settings, "#求财, #命理", tool_name="chart")
    assert [e["id"] for e in by_tag["entries"]] == ["占卜/求财心得", "滴天髓笔记"]  # 逗号分隔的字符串也认
    assert user_knowledge.missing_warning(by_tag) is None


def test_budget_is_shared_and_truncation_is_marked(tmp_path: Path) -> None:
    root = tmp_path / "kb"
    _write(root, "长.md", "甲" * 3000)
    _write(root, "短.md", "乙" * 100)
    settings = _settings(tmp_path, user_knowledge_max_chars=1000)
    context = user_knowledge.build_context(settings, ["长", "短"], tool_name="chart")
    long_entry, short_entry = context["entries"]
    assert long_entry["truncated"] is True and "已截断：原文 3000 字" in long_entry["text"]
    assert short_entry["truncated"] is False and short_entry["text"] == "乙" * 100
    assert sum(len(e["text"]) for e in context["entries"]) <= 1000
    assert context["max_chars"] == 1000


# ── 增删 / 精读 / 检索 ────────────────────────────────────────────────────


def test_add_entry_validates_names_instead_of_rewriting_them(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / "kb"
    entry = user_knowledge.add_entry(settings, text="正文", entry_id="八字/笔记", techniques=["bazi_birth"], tags=["#t"])
    assert entry.path == root / "八字" / "笔记.md" and entry.techniques == {"bazi_birth"} and entry.tags == {"t"}
    # 不合法的名字直接拒绝并说明原因——此前被悄悄改写（../../逃出去/笔记 → 逃出去/笔记），两个名字可能写到同一个文件。
    for bad in ("../../逃出去/笔记", "../..", ".私密", "a/CON", "a:b", "x/" * 6 + "y"):
        with pytest.raises(ToolValidationError) as invalid:
            user_knowledge.add_entry(settings, text="x", entry_id=bad)
        assert invalid.value.code == "knowledge.user_invalid_id", bad
    with pytest.raises(ToolValidationError) as empty:
        user_knowledge.add_entry(settings, text="  ", entry_id="空")
    assert empty.value.code == "knowledge.user_empty"
    with pytest.raises(ToolValidationError) as injected:
        user_knowledge.add_entry(settings, text="x", entry_id="注入", title="标题\ntechniques: *")
    assert injected.value.code == "knowledge.user_invalid_meta"
    # 「滴天髓 v1.2」与「滴天髓 v1.3」是两条：扩展名是追加的，不再被 with_suffix 吃掉「.2」「.3」后撞成同一个文件。
    a = user_knowledge.add_entry(settings, text="一", entry_id="滴天髓 v1.2")
    b = user_knowledge.add_entry(settings, text="二", entry_id="滴天髓 v1.3")
    assert a.path != b.path and a.path.read_text(encoding="utf-8").endswith("一\n")
    # 写进去的元数据读回来一字不差（引号、冒号、井号都安全）。
    tricky = user_knowledge.add_entry(settings, text="正文", entry_id="怪标题", title='C# 笔记: "通神" #1', tags=["子平 真诠"])
    assert tricky.title == 'C# 笔记: "通神" #1' and tricky.tags == {"子平 真诠"}


def test_overwrite_keeps_the_old_version_in_the_trash_and_merges_metadata(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = tmp_path / "kb"
    _write(root, "旧笔记.txt", "---\ntitle: 旧标题\ntechniques: bazi\ntags: 古籍\n---\n旧正文")
    with pytest.raises(ToolValidationError) as exists:
        user_knowledge.add_entry(settings, text="新正文", entry_id="旧笔记")
    assert exists.value.code == "knowledge.user_exists"
    entry = user_knowledge.add_entry(settings, text="新正文", entry_id="旧笔记", overwrite=True)
    # 覆盖的是原文件本身（.txt 不会多出一个 .md 同名条目），没给的 title / techniques / tags 沿用旧值。
    assert entry.path == root / "旧笔记.txt" and entry.text == "新正文"
    assert entry.title == "旧标题" and entry.techniques == {"bazi"} and entry.tags == {"古籍"}
    assert [e.id for e in user_knowledge.list_entries(settings)] == ["旧笔记"]
    trash = user_knowledge.list_trash(settings)
    assert len(trash) == 1 and trash[0]["reason"] == "overwrite" and trash[0]["file"] == "旧笔记.txt"
    # 回收站在数据目录的状态区，不在用户的知识库文件夹里。
    assert not any(p.name == "manifest.json" for p in root.rglob("*"))


def test_remove_goes_to_the_trash_and_restore_brings_it_back(tmp_path: Path) -> None:
    _seed(tmp_path / "kb")
    settings = _settings(tmp_path)
    removed = user_knowledge.remove_entry(settings, "求财心得")  # 唯一标题也认
    assert removed["id"] == "占卜/求财心得" and not Path(removed["path"]).exists()
    assert not (tmp_path / "kb" / "占卜").exists()  # 删空的子文件夹顺手收掉
    with pytest.raises(ToolValidationError) as gone:
        user_knowledge.remove_entry(settings, "求财心得")
    assert gone.value.code == "knowledge.user_not_found"
    restored = user_knowledge.restore_entry(settings, removed["trash_id"])
    assert restored["restored"] == "占卜/求财心得.txt"
    assert user_knowledge.read_entry(settings, "占卜/求财心得")["text"] == "小六壬遇速喜，求财宜速。"
    assert user_knowledge.list_trash(settings) == []
    with pytest.raises(ToolValidationError) as missing:
        user_knowledge.restore_entry(settings, "../../etc")
    assert missing.value.code == "knowledge.user_trash_not_found"


def test_one_resolver_for_select_read_and_remove_and_ambiguity_is_an_error(tmp_path: Path) -> None:
    root = tmp_path / "kb"
    _write(root, "x.md", "顶层 x")
    _write(root, "sub/x.md", "子目录里的 x（标题默认也是 x）")
    _write(root, "z.md", "---\ntitle: 共同标题\n---\nz")
    _write(root, "w.md", "---\ntitle: 共同标题\n---\nw")
    settings = _settings(tmp_path)
    # 「x」精确等于顶层的 id：选取、精读、删除都指向同一个文件（此前 remove 按排序删到了 sub/x.md）。
    assert user_knowledge.build_context(settings, "x", tool_name="chart")["entries"][0]["id"] == "x"
    assert user_knowledge.read_entry(settings, "x")["key"] == "x"
    assert user_knowledge.remove_entry(settings, "x")["id"] == "x" and (root / "sub/x.md").exists()
    with pytest.raises(ToolValidationError) as ambiguous:
        user_knowledge.remove_entry(settings, "共同标题")
    assert ambiguous.value.code == "knowledge.user_ambiguous" and set(ambiguous.value.details["candidates"]) == {"z", "w"}
    assert (root / "z.md").exists() and (root / "w.md").exists()  # 歧义时一个都不删
    context = user_knowledge.build_context(settings, "共同标题", tool_name="chart")
    assert context["entries"] == [] and context["ambiguous"][0]["name"] == "共同标题"
    assert any("对应多条" in w for w in user_knowledge.context_warnings(context))


def test_read_and_search_user_entries(tmp_path: Path) -> None:
    _seed(tmp_path / "kb")
    settings = _settings(tmp_path)
    read = user_knowledge.read_entry(settings, "滴天髓笔记")
    assert read["domain"] == "user" and read["lines"] == ["天道：欲识三元万法宗。"]
    assert "用户自备知识库" in read["citation"]
    hits = user_knowledge.search_matches(settings, "求财")
    assert hits[0]["key"] == "占卜/求财心得" and hits[0]["domain"] == "user"
    assert user_knowledge.search_matches(settings, "根本没有") == []


# ── 接进计算 ───────────────────────────────────────────────────────────────


def test_run_tool_attaches_selected_knowledge_without_touching_the_chart(tmp_path: Path) -> None:
    _seed(tmp_path / "kb")
    service = _service(tmp_path)
    payload = build_sample_payloads()["xiaoliuren"]
    plain = service.run_tool("xiaoliuren", dict(payload), save_result=False)
    assert "knowledge_context" not in plain.data

    result = service.run_tool("xiaoliuren", {**payload, "knowledge": ["auto", "不存在"]}, save_result=True)
    assert result.ok
    context = result.data["knowledge_context"]
    assert [e["id"] for e in context["entries"]] == ["滴天髓笔记", "通用"]
    # 只是附加上下文：不进回显入参、不进存档、不改盘面、少一条只告警不失败。
    assert "knowledge" not in result.input_normalized
    assert result.data["export_snapshot"] == plain.data["export_snapshot"]
    assert any("不存在" in w for w in result.warnings)
    stored = "\n".join(f.read_text(encoding="utf-8") for f in (tmp_path / "runs").rglob("*.json"))
    # 存档只记引用、不存正文。此前这里只查 `"knowledge":` 键——它从来不在存档里，真正装着全文的
    # `knowledge_context` 一直被存下来，断言却是绿的（因为错误的原因通过）。
    assert stored and "knowledge_context" in stored
    assert "欲识三元万法宗" not in stored and "先看盘面再看资料" not in stored
    stored_run = json.loads(next((tmp_path / "runs").rglob("*_xiaoliuren_1.json")).read_text(encoding="utf-8"))
    refs = stored_run["data"]["knowledge_context"]["entries"]
    assert [ref["id"] for ref in refs] == ["滴天髓笔记", "通用"]
    assert all("text" not in ref and ref["text_stored"] is False and len(ref["sha256"]) == 64 for ref in refs)
    assert result.data["knowledge_context"]["entries"][0]["text"] == "天道：欲识三元万法宗。"  # 交给 AI 的那份仍有全文


def test_knowledge_selection_never_reaches_the_engine_request(tmp_path: Path) -> None:
    from fakes import CaptureClient

    _seed(tmp_path / "kb")
    settings = _settings(tmp_path)
    client = CaptureClient()
    service = HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=FakeJsClient())
    result = service.run_tool("chart", {**build_sample_payloads()["chart"], "knowledge": "#古籍"}, save_result=False)
    assert [e["id"] for e in result.data["knowledge_context"]["entries"]] == ["滴天髓笔记"]
    assert client.calls and all("knowledge" not in payload for _, payload in client.calls)


def test_knowledge_registry_and_read_cover_the_user_domain(tmp_path: Path) -> None:
    _seed(tmp_path / "kb")
    service = _service(tmp_path)
    registry = service.run_tool("knowledge_registry", {"domain": "user"}, save_result=False).data
    assert registry["user_knowledge"]["count"] == 3
    full = service.run_tool("knowledge_registry", {}, save_result=False).data
    assert full["user_knowledge"]["count"] == 3
    read = service.run_tool("knowledge_read", {"domain": "user", "key": "通用"}, save_result=False).data
    assert read["title"] == "通用" and read["source"] == "user_knowledge"
    search = service.run_tool("knowledge_read", {"query": "求财"}, save_result=False).data
    assert any(m.get("domain") == "user" for m in search["matches"])


def test_server_profile_lists_user_entries(tmp_path: Path) -> None:
    from horosa_skill.surfaces.mcp_surface import _user_knowledge_profile

    _seed(tmp_path / "kb")
    profile = _user_knowledge_profile(_settings(tmp_path))
    assert profile["count"] == 3 and "滴天髓笔记" in profile["entries"]


def test_knowledge_is_advertised_on_dispatch_and_tool_run_but_hidden_on_techniques() -> None:
    from horosa_skill.schemas.tools.base import FlexibleModel
    from horosa_skill.schemas.tools.facades import _DISPATCH_OWN_FIELDS

    assert "knowledge" in _DISPATCH_OWN_FIELDS
    field = FlexibleModel.model_fields["knowledge"]
    assert (field.json_schema_extra or {}).get("x-horosa-hidden") is True


def test_cli_knowledge_add_mine_remove(tmp_path: Path, monkeypatch) -> None:
    from typer.testing import CliRunner

    from horosa_skill.surfaces import cli

    monkeypatch.setenv("HOROSA_USER_KNOWLEDGE_DIR", str(tmp_path / "kb"))
    runner = CliRunner()
    added = runner.invoke(cli.app, ["knowledge", "add", "八字/笔记", "--text", "正文", "--techniques", "bazi_birth，ziwei_birth", "--tags", "命理"])
    assert added.exit_code == 0, added.output
    assert json.loads(added.stdout)["entry"]["techniques"] == ["bazi_birth", "ziwei_birth"]
    again = runner.invoke(cli.app, ["knowledge", "add", "八字/笔记", "--text", "正文"])
    assert again.exit_code == 2 and "knowledge.user_exists" in again.output
    mine = json.loads(runner.invoke(cli.app, ["knowledge", "mine"]).stdout)
    assert mine["count"] == 1 and mine["entries"][0]["id"] == "八字/笔记"
    assert runner.invoke(cli.app, ["knowledge", "remove", "八字/笔记"]).exit_code == 0
    assert json.loads(runner.invoke(cli.app, ["knowledge", "mine"]).stdout)["count"] == 0


# ── 完整排盘报告 ───────────────────────────────────────────────────────────


def test_chart_style_refuses_tools_without_a_chart(tmp_path: Path) -> None:
    # 解析 / 注册表 / 知识检索没有盘面：此前照样出一份只有封面、标题是工具 id 的「完整排盘报告」。
    service = _service(tmp_path)
    with pytest.raises(ToolValidationError) as refused:
        service.report_from_tool({"tool_name": "export_registry", "payload": {}, "format": "pdf", "style": "chart"})
    assert refused.value.code == "report.no_chart_content"
    with pytest.raises(ToolValidationError) as rules:  # 规则库查询：段落有标题、内容是「无」，同样不出空壳报告
        service.report_from_tool({"tool_name": "ziwei_rules", "payload": {}, "format": "pdf", "style": "chart"})
    assert rules.value.code == "report.no_chart_content"


class _PdfSpy:
    """记下最后一遍排版的 story 文本与 PDF 书签（真 PDF 里的中文是子集字形，抽不出文字）。"""

    def __init__(self, monkeypatch) -> None:
        from reportlab.pdfgen.canvas import Canvas
        from reportlab.platypus import SimpleDocTemplate

        self.builds = 0
        self.story: list = []
        self.outline: list[tuple[str, int, int]] = []
        original_build = SimpleDocTemplate.build
        original_outline = Canvas.addOutlineEntry
        spy = self

        def build(doc, flowables, *args, **kwargs):
            spy.builds += 1
            spy.story = list(flowables)
            spy.outline = []
            return original_build(doc, flowables, *args, **kwargs)

        def add_outline(canvas, title, key, level=0, closed=None):
            spy.outline.append((title, level, canvas.getPageNumber()))
            return original_outline(canvas, title, key, level=level, closed=closed)

        monkeypatch.setattr(SimpleDocTemplate, "build", build)
        monkeypatch.setattr(Canvas, "addOutlineEntry", add_outline)

    def texts(self) -> list[str]:
        out: list[str] = []

        for flowable in self.story:
            for item in _flat(flowable):
                if isinstance(getattr(item, "text", None), str):
                    out.append(re.sub("<[^>]+>", "", item.text))
        return out

    def toc(self) -> list[tuple[str, str]]:
        for flowable in self.story:
            rows = [[next(iter(_flat(cell)), None) for cell in row] for row in getattr(flowable, "_cellvalues", None) or []]
            if rows and 'href="#h' in str(getattr(rows[0][0], "text", "")):
                return [(re.sub("<[^>]+>", "", r[0].text), r[1].text) for r in rows]
        return []


def _flat(item) -> list:
    # 排版过的 Table 把单元格换成了 tuple 子类（_ExpandedCellTuple）：列表 / 元组都展开。
    if isinstance(item, (list, tuple)):
        return [leaf for sub in item for leaf in _flat(sub)]
    if hasattr(item, "_cellvalues"):
        return [leaf for row in item._cellvalues for leaf in _flat(row)]
    if isinstance(getattr(item, "_content", None), list):  # KeepTogether（短表整张不拆）
        return [leaf for sub in item._content for leaf in _flat(sub)]
    return [item]


def _chart_run(service: HorosaSkillService, **extra):
    return service.run_tool("chart", {**build_sample_payloads()["chart"], **extra}, save_result=True)


def test_chart_style_report_renders_every_section_without_an_ai_answer(tmp_path: Path, monkeypatch) -> None:
    _seed(tmp_path / "kb")
    service = _service(tmp_path)
    run = _chart_run(service, knowledge="通用")
    titles = [s["title"] for s in run.data["export_snapshot"]["sections"]]
    assert len(titles) >= 10

    spy = _PdfSpy(monkeypatch)
    rendered = service.report_render({"run_id": run.memory_ref.run_id, "tool_name": "chart", "format": "pdf", "style": "chart"})
    assert rendered["format"] == "pdf" and Path(rendered["artifact_path"]).read_bytes().startswith(b"%PDF")
    texts = spy.texts()
    joined = "\n".join(texts)
    from horosa_skill.service._common import _missing_detail_text

    sections = run.data["export_snapshot"]["sections"]
    produced = [s["title"] for s in sections if str(s.get("body") or "").strip() not in ("", _missing_detail_text(s["title"]))]
    unproduced = [s["title"] for s in sections if s["title"] not in produced]
    assert produced and unproduced  # 假客户端下两种都有，两条路径都验到
    for title in produced:
        assert title in texts, title  # 每个有内容的导出章节都有自己的标题块
    # 引擎没给内容的段：不再各占一个标题 + 一段写给 AI 的护栏话，统一列进附录「本次未产出」。
    assert "本次未产出" in texts and all(title in joined for title in unproduced)
    assert "不能臆造外部依赖" not in joined
    assert "完整盘面" in texts and "附录" in texts and "基本信息" in texts and "技法依据" in texts
    # 自备资料只列引用（标题 / 条目 / 字数），正文不随报告印出。
    assert "自备参考资料" in texts and "通用" in joined and "先看盘面再看资料。" not in joined
    assert "完整排盘报告" in joined
    assert not any(t in joined for t in ("False", "True", "aiExport", "settings v"))  # 附录不漏机器值
    # 没有 AI 解读就不出 AI 章节，也不出内部字样。
    assert not any(t in texts for t in ("核心结论", "起盘依据", "解盘步骤", "总览摘要"))
    assert not any(term in joined for term in ("Run ID", "report_metadata", "Horosa Skill"))
    # 两遍排版：第二遍目录页码 = 实际书签页码（第一遍留空）。
    assert spy.builds == 2
    toc = spy.toc()
    # 段内小标题（◆ / [x]）只进书签第三级、不进目录：目录对照只看前两级。
    outline_pages = [(title, str(page)) for title, level, page in spy.outline if level <= 1]
    assert any(level == 2 for _, level, _ in spy.outline)
    assert toc and toc == outline_pages

    docx = service.report_render({"run_id": run.memory_ref.run_id, "tool_name": "chart", "format": "docx", "style": "chart"})
    with zipfile.ZipFile(Path(docx["artifact_path"])) as archive:
        docx_text = re.sub("<[^>]+>", "", archive.read("word/document.xml").decode("utf-8"))
    for title in titles:
        assert title in docx_text, title
    assert "完整盘面" in docx_text and "自备参考资料" in docx_text
    assert not any(term in docx_text for term in ("Run ID", "来源追溯", "report_metadata", "Horosa Skill", "核心结论"))


def test_analysis_style_still_requires_an_ai_answer(tmp_path: Path) -> None:
    """负向对照：放行无 AI 渲染的是 style=chart，不是别的什么。"""
    service = _service(tmp_path)
    run = _chart_run(service)
    pending = service.report_render({"run_id": run.memory_ref.run_id, "tool_name": "chart", "format": "pdf"})
    assert pending["mode"] == "analysis_required" and pending["artifact_path"] is None
    with pytest.raises(ToolValidationError) as bad:
        service.report_render({"run_id": run.memory_ref.run_id, "tool_name": "chart", "format": "pdf", "style": "fancy"})
    assert bad.value.code == "report.invalid_style"


def test_report_from_tool_chart_style_runs_and_renders_in_one_call(tmp_path: Path) -> None:
    service = _service(tmp_path)
    result = service.report_from_tool(
        {"tool_name": "chart", "payload": build_sample_payloads()["chart"], "format": "docx", "style": "chart"}
    )
    assert result.get("mode") != "analysis_required"
    assert Path(result["artifact_path"]).read_bytes().startswith(b"PK")


def test_cli_report_commands_forward_language_only_when_given(monkeypatch) -> None:
    """v0.42.0 缺陷：CLI 的 `--language` 缺省 zh-CN 总被传下去，盖掉 HOROSA_OUTPUT_SCRIPT 推出的繁体报告语言。"""
    from typer.testing import CliRunner

    from horosa_skill.surfaces import cli

    seen: list[tuple[str, dict]] = []

    class _Recorder:
        def report_render(self, payload):
            seen.append(("render", payload))
            return {"ok": True}

        def report_template(self, payload):
            seen.append(("template", payload))
            return {"ok": True}

    monkeypatch.setattr(cli, "_service", lambda: _Recorder())
    runner = CliRunner()
    assert runner.invoke(cli.app, ["report", "render", "--run-id", "r1", "--style", "chart"]).exit_code == 0
    assert runner.invoke(cli.app, ["report", "template", "--run-id", "r1"]).exit_code == 0
    assert runner.invoke(cli.app, ["report", "render", "--run-id", "r1", "--language", "zh-TW"]).exit_code == 0
    (_, render), (_, template), (_, explicit) = seen
    assert "language" not in render and render["style"] == "chart"
    assert "language" not in template
    assert explicit["language"] == "zh-TW" and explicit["style"] == "analysis"


def test_traditional_reports_convert_the_renderers_own_labels_exactly_once(tmp_path: Path, monkeypatch) -> None:
    """繁体输出时，渲染器写死的标签（目录 / 完整盘面 / 附录 / 页脚）也要转；文档正文调用方已转，不能再转（不幂等）。"""
    from horosa_skill.textscript import convert

    service = _service(tmp_path, output_script="zh-Hant")
    run = _chart_run(service)
    spy = _PdfSpy(monkeypatch)
    service.report_render({"run_id": run.memory_ref.run_id, "tool_name": "chart", "format": "pdf", "style": "chart"})
    texts = spy.texts()
    assert {"目錄", "完整盤面", "附錄"} <= set(texts)
    assert not {"目录", "完整盘面", "附录"} & set(texts)
    # 封面大标题是技法名、小标签是「完整排盘报告」（各转一次；整份标题在页脚与 PDF 元数据里）。
    assert convert("星盘", "zh-Hant") in texts and convert("完整排盘报告", "zh-Hant") in texts

    docx = service.report_render({"run_id": run.memory_ref.run_id, "tool_name": "chart", "format": "docx", "style": "chart"})
    with zipfile.ZipFile(Path(docx["artifact_path"])) as archive:
        footer = "".join(archive.read(n).decode("utf-8") for n in archive.namelist() if "footer" in n)
        body = archive.read("word/document.xml").decode("utf-8")
    assert "頁" in footer and "页" not in footer
    assert "完整盤面" in body and "完整盘面" not in body


def test_traditional_technique_report_converts_template_labels_once(tmp_path: Path) -> None:
    from horosa_skill.reports.renderers import render_report
    from horosa_skill.reports.technique_card import (
        build_technique_report,
        render_technique_report_markdown,
    )
    from horosa_skill.textscript import convert

    service = _service(tmp_path, output_script="zh-Hant")
    run = _chart_run(service)
    document = build_technique_report(cards=[run.data["technique_card"]], scope="run", scope_id=run.memory_ref.run_id)
    out = tmp_path / "t.md"
    render_report(document, output_path=out, format_name="markdown", script="zh-Hant")
    # 模板标签与数据一起、只转一次（简体原文进渲染器，生成后整体转）。
    assert out.read_text(encoding="utf-8") == convert(render_technique_report_markdown(document), "zh-Hant")

    via_service = service.technique_report({"run_id": run.memory_ref.run_id, "format": "markdown"})
    markdown = Path(via_service["artifact_path"]).read_text(encoding="utf-8")
    assert "一致性檢查" in markdown and "一致性检查" not in markdown
    assert "技法依據報告" in markdown


def test_knowledge_stays_off_facades_and_out_of_the_hidden_knob_count(tmp_path: Path) -> None:
    """基类上的隐藏字段：门面不广告（否则每个门面多一个无描述属性），技法也不把它算成「另 N 个高级旋钮」（44 个工具各 +66 B）。"""
    import asyncio

    from horosa_skill.surfaces.mcp_server import create_mcp_server

    settings = _settings(tmp_path)
    mcp = create_mcp_server(HorosaSkillService(settings, store=MemoryStore(settings)), settings)
    tools = {tool.name: tool.inputSchema for tool in asyncio.run(mcp.list_tools())}
    facades = ["horosa_memory_query", "horosa_memory_show", "horosa_report_render", "horosa_report_template", "horosa_technique_report"]
    assert all("knowledge" not in tools[name]["properties"] for name in facades)
    assert tools["horosa_report_render"]["properties"]["style"]["description"]
    assert tools["horosa_dispatch"]["properties"]["knowledge"]["description"]
    # 神数没有自己的隐藏旋钮：request 描述保持最短形态。
    assert tools["horosa_shenshu_wangji"]["properties"]["request"]["description"] == "整包载荷"
