"""自备知识库的数据管理（v0.43.1-dev 重做）：编码、问题清单、撞名、选取解析、预算、并发写、隐私、卸载保护。

每条都对应 2026-10-24 独立审查里实测复现过的一种「丢 / 坏 / 静默跳过 / 删错」（docs/LESSONS.md v0.43.1-dev）。
"""
from __future__ import annotations

import json
import threading
import unicodedata
from pathlib import Path

import pytest
from fakes import FakeClient, FakeJsClient

from horosa_skill.config import Settings
from horosa_skill.errors import ToolValidationError
from horosa_skill.knowledge import user as uk
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.testing_payloads import build_sample_payloads


def _settings(tmp_path: Path, **extra) -> Settings:
    return Settings(
        server_root="http://127.0.0.1:9",
        chart_server_root="http://127.0.0.1:9",
        runtime_root=tmp_path / "runtime",
        db_path=tmp_path / "data" / "memory.db",
        output_dir=tmp_path / "data" / "runs",
        data_dir=tmp_path / "data",
        **extra,
    )


def _kb(tmp_path: Path) -> Path:
    root = tmp_path / "data" / "knowledge"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _put(root: Path, name: str, data: bytes | str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode("utf-8") if isinstance(data, str) else data)
    return path


# ── 读：编码与问题清单 ──────────────────────────────────────────────────


def test_bom_gbk_and_utf16_files_are_read_and_bad_ones_are_reported_not_dropped(tmp_path: Path) -> None:
    root = _kb(tmp_path)
    _put(root, "带BOM.md", "\ufeff---\ntitle: 带 BOM\ntags: 古籍\n---\n正文甲")
    _put(root, "旧笔记.txt", "穷通宝鉴：甲木参天。".encode("gbk"))
    _put(root, "宽字符.md", "滴天髓".encode("utf-16"))
    _put(root, "二进制.md", b"\x00\x01\x02\xff\xfe\x00")
    _put(root, "空.md", "---\ntitle: 空\n---\n")
    _put(root, "大.md", b"x" * (uk.MAX_FILE_BYTES + 1))
    _put(root, "坏头.md", "---\ntitle: 没收尾\n正文")
    settings = _settings(tmp_path)

    entries = {e.id: e for e in uk.list_entries(settings)}
    assert entries["带BOM"].title == "带 BOM" and entries["带BOM"].tags == {"古籍"} and entries["带BOM"].text == "正文甲"
    assert entries["旧笔记"].text == "穷通宝鉴：甲木参天。" and entries["旧笔记"].encoding == "gb18030"
    assert entries["宽字符"].text == "滴天髓"
    assert "坏头" in entries  # 没收尾的元数据：整段当正文读，同时报问题
    problems = {p["file"]: p["kind"] for p in uk.overview(settings)["problems"]}
    assert problems == {"二进制.md": "unreadable_encoding", "空.md": "empty", "大.md": "too_large", "坏头.md": "front_matter"}

    # 点名一个读不了的文件：告警说清原因，而不是「没找到」。
    context = uk.build_context(settings, ["二进制", "大"], tool_name="chart")
    assert context["missing"] == [] and {u["name"] for u in context["unreadable"]} == {"二进制", "大"}
    assert any("没能带入" in w for w in uk.context_warnings(context))


def test_front_matter_variants(tmp_path: Path) -> None:
    root = _kb(tmp_path)
    _put(root, "a.md", "\n\n---\ntitle：全角冒号\ntechniques:\n  - bazi\n  - 八字\ntags: [\"命理\", 古籍]\n---\n正文")
    entry = uk.list_entries(_settings(tmp_path))[0]
    assert entry.title == "全角冒号" and entry.techniques == {"bazi", "八字"} and entry.tags == {"命理", "古籍"}
    # 直接交进来的文本（`knowledge add --text`、客户端贴来的）也可能带 BOM：元数据照样生效、不漏进正文。
    meta, body, problem = uk.parse_front_matter("\ufeff---\ntitle: 带 BOM\n---\n正文")
    assert meta == {"title": "带 BOM"} and body == "正文" and problem is None


def test_files_whose_ids_collide_are_reported_and_never_auto_picked(tmp_path: Path) -> None:
    root = _kb(tmp_path)
    _put(root, "a.md", "md 版")
    _put(root, "a.txt", "txt 版")
    _put(root, "b.md", "唯一的 b")
    settings = _settings(tmp_path)
    assert [e.id for e in uk.list_entries(settings)] == ["b"]
    assert {p["file"] for p in uk.overview(settings)["problems"] if p["kind"] == "duplicate_id"} == {"a.md", "a.txt"}
    context = uk.build_context(settings, "a", tool_name="chart")
    assert context["entries"] == [] and context["unreadable"]
    with pytest.raises(ToolValidationError) as unreadable:
        uk.remove_entry(settings, "a")
    assert unreadable.value.code == "knowledge.user_unreadable"
    assert (root / "a.md").exists() and (root / "a.txt").exists()


def test_cache_sees_edits_made_outside_the_tool(tmp_path: Path) -> None:
    root = _kb(tmp_path)
    path = _put(root, "笔记.md", "第一版")
    settings = _settings(tmp_path)
    assert uk.read_entry(settings, "笔记")["text"] == "第一版"
    path.write_text("第二版，长一点", encoding="utf-8")
    assert uk.read_entry(settings, "笔记")["text"] == "第二版，长一点"
    path.unlink()
    assert uk.list_entries(settings) == []


def test_relative_knowledge_dir_is_anchored_to_the_data_dir(tmp_path: Path) -> None:
    settings = _settings(tmp_path, user_knowledge_dir=Path("我的笔记"))
    assert uk.knowledge_dir(settings) == tmp_path / "data" / "我的笔记"


# ── 选取 ──────────────────────────────────────────────────────────────


def test_selection_accepts_json_strings_fullwidth_hash_titles_with_separators_and_nfd_names(tmp_path: Path) -> None:
    root = _kb(tmp_path)
    _put(root, "合评.md", "---\ntitle: 子平真诠、滴天髓合评\ntags: 古籍\n---\n合评正文")
    _put(root, unicodedata.normalize("NFD", "Café笔记.md"), "咖啡")
    settings = _settings(tmp_path)
    assert [e["id"] for e in uk.build_context(settings, '["合评", "#古籍"]', tool_name="chart")["entries"]] == ["合评"]
    assert [e["id"] for e in uk.build_context(settings, "＃古籍", tool_name="chart")["entries"]] == ["合评"]
    assert [e["id"] for e in uk.build_context(settings, "子平真诠、滴天髓合评", tool_name="chart")["entries"]] == ["合评"]
    assert [e["id"] for e in uk.build_context(settings, "CAFÉ笔记", tool_name="chart")["entries"]] == ["Café笔记"]
    nfd_query = unicodedata.normalize("NFD", "café笔记")  # macOS 输入法 / 文件名拷来的分解形式
    assert [e["id"] for e in uk.build_context(settings, nfd_query, tool_name="chart")["entries"]] == ["Café笔记"]


def test_auto_understands_chinese_technique_names_and_warns_when_nothing_matches(tmp_path: Path) -> None:
    root = _kb(tmp_path)
    _put(root, "八字.md", "---\ntechniques: 八字\n---\n八字心得")
    _put(root, "拼错.md", "---\ntechniques: bazzi\n---\n拼错了")
    settings = _settings(tmp_path)
    assert [e["id"] for e in uk.build_context(settings, "auto", tool_name="bazi_birth", technique="bazi")["entries"]] == ["八字"]
    nothing = uk.build_context(settings, "auto", tool_name="ziwei_birth", technique="ziwei")
    assert nothing["entries"] == [] and nothing["auto_unmatched"] is True
    assert any("auto 没有选中" in w for w in uk.context_warnings(nothing))
    unknown = [p for p in uk.overview(settings)["problems"] if p["kind"] == "unknown_technique"]
    assert [p["file"] for p in unknown] == ["拼错.md"] and "bazzi" in unknown[0]["message"]


def test_budget_is_fair_counts_the_marker_and_caps_the_entry_count(tmp_path: Path) -> None:
    root = _kb(tmp_path)
    _put(root, "长.md", "甲" * 3000)
    _put(root, "短.md", "乙" * 100)
    settings = _settings(tmp_path, user_knowledge_max_chars=1000)
    # 长的先点名、短的后点名：短的整条给全，剩下的全给长的（此前长条目先拿一半，短条目用不完的份额浪费掉）。
    context = uk.build_context(settings, ["长", "短"], tool_name="chart")
    long_entry, short_entry = context["entries"]
    assert short_entry["text"] == "乙" * 100 and long_entry["truncated"] is True
    total = sum(len(e["text"]) for e in context["entries"])
    assert 950 <= total <= 1000  # 截断标记也算进预算，且预算几乎用满
    assert 'knowledge_read(domain="user", key="长")' in long_entry["text"]

    for i in range(20):
        _put(root, f"多/{i:02d}.md", f"---\ntechniques: '*'\n---\n第 {i} 条")
    many = uk.build_context(_settings(tmp_path, user_knowledge_max_chars=12_000), "auto", tool_name="chart")
    assert len(many["entries"]) == uk.MAX_ENTRIES_PER_RUN and len(many["omitted"]) == 20 - uk.MAX_ENTRIES_PER_RUN


# ── 写：并发 ──────────────────────────────────────────────────────────


def test_concurrent_adds_of_the_same_name_never_clobber(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    outcomes: list[str] = []

    def add(i: int) -> None:
        try:
            uk.add_entry(settings, text=f"写入者 {i}", entry_id="抢")
            outcomes.append("ok")
        except ToolValidationError as exc:
            outcomes.append(exc.code)

    threads = [threading.Thread(target=add, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert outcomes.count("ok") == 1 and outcomes.count("knowledge.user_exists") == 7
    assert not [p for p in _kb(tmp_path).rglob("*") if p.name.endswith(".tmp")]


# ── 接进计算与存档 ─────────────────────────────────────────────────────


def _service(tmp_path: Path) -> HorosaSkillService:
    settings = _settings(tmp_path)
    return HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())


def test_a_knowledge_failure_never_costs_the_chart(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from horosa_skill.service.api import tools as tools_api

    _put(_kb(tmp_path), "笔记.md", "x")

    def boom(*args, **kwargs):
        raise OSError("磁盘拔了")

    monkeypatch.setattr(tools_api, "build_user_knowledge_context", boom)
    result = _service(tmp_path).run_tool("xiaoliuren", {**build_sample_payloads()["xiaoliuren"], "knowledge": "笔记"})
    assert result.ok and "export_snapshot" in result.data and "knowledge_context" not in result.data
    assert any("没能带入" in w and "磁盘拔了" in w for w in result.warnings)


def test_purge_data_keeps_the_knowledge_folder_and_trash_unless_asked(tmp_path: Path) -> None:
    from horosa_skill.surfaces import runtime_helpers

    settings = _settings(tmp_path)
    _put(_kb(tmp_path), "心血.md", "多年笔记")
    uk.add_entry(settings, text="v1", entry_id="改过")
    uk.add_entry(settings, text="v2", entry_id="改过", overwrite=True)  # 回收站里有一份
    _put(tmp_path / "data" / "runs", "r.json", "{}")
    manager = runtime_helpers._runtime_manager(settings)
    plan = manager.uninstall(purge_data=True, yes=False)
    removing = set(plan["would_remove"])
    assert str(tmp_path / "data" / "knowledge") not in removing and str(tmp_path / "data") not in removing
    assert str(tmp_path / "data" / "runs") in removing
    assert {Path(p).name for p in plan["kept"]} == {"knowledge", uk.STATE_DIRNAME}
    manager.uninstall(purge_data=True, yes=True)
    assert (tmp_path / "data" / "knowledge" / "心血.md").read_text(encoding="utf-8") == "多年笔记"
    assert uk.list_trash(settings) and not (tmp_path / "data" / "runs").exists()
    everything = manager.uninstall(purge_data=True, purge_knowledge=True, yes=False)
    assert str(tmp_path / "data") in everything["would_remove"]


def test_cli_add_from_a_gbk_file_and_trash_restore(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    from horosa_skill.surfaces import cli

    monkeypatch.setenv("HOROSA_SKILL_DATA_DIR", str(tmp_path / "data"))
    source = _put(tmp_path, "旧.txt", "\ufeff三命通会".encode("utf-8"))
    gbk = _put(tmp_path, "gbk.txt", "渊海子平".encode("gbk"))
    runner = CliRunner()
    assert runner.invoke(cli.app, ["knowledge", "add", "三命", "--file", str(source)]).exit_code == 0
    added = runner.invoke(cli.app, ["knowledge", "add", "渊海", "--file", str(gbk)])
    assert added.exit_code == 0, added.output
    assert uk.read_entry(Settings.from_env(), "渊海")["text"] == "渊海子平"
    assert uk.read_entry(Settings.from_env(), "三命")["text"] == "三命通会"  # BOM 不进正文
    removed = json.loads(runner.invoke(cli.app, ["knowledge", "remove", "渊海"]).stdout)
    assert removed["trash_id"] and "knowledge restore" in removed["restore"]
    trash = json.loads(runner.invoke(cli.app, ["knowledge", "trash"]).stdout)
    assert trash["count"] == 1 and trash["items"][0]["file"] == "渊海.md"
    assert runner.invoke(cli.app, ["knowledge", "restore", removed["trash_id"]]).exit_code == 0
    mine = json.loads(runner.invoke(cli.app, ["knowledge", "mine"]).stdout)
    assert {e["id"] for e in mine["entries"]} == {"三命", "渊海"} and mine["problems"] == [] and mine["trash"] == 0
    binary = _put(tmp_path, "bin.txt", b"\x00\xff\x00")
    bad = runner.invoke(cli.app, ["knowledge", "add", "坏", "--file", str(binary)])
    assert bad.exit_code == 2 and "knowledge.user_unreadable" in bad.output  # 不再是裸 UnicodeDecodeError 回溯
