"""知识检索对调用方的契约（2026-11-11 深审）：参数怎么认、什么会被说出来、哪些文字要标「不可信」。

每条都对着一次真实复现：域名只认内部 id、limit / offset 越界不吭声、自备知识库里没进索引的文件不吭声、
笔记原文不带标记就交给模型、同一条笔记的命中被悄悄截掉、空库 0 命中没有任何说明。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.errors import ToolValidationError
from horosa_skill.knowledge import search as knowledge_search
from horosa_skill.knowledge import store
from horosa_skill.knowledge import user as uk


def _settings(tmp_path: Path, **extra) -> Settings:
    return Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", runtime_root=tmp_path / "rt",
                    db_path=tmp_path / "data" / "m.db", output_dir=tmp_path / "data" / "runs", data_dir=tmp_path / "data", **extra)


def _put(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / "data" / "knowledge" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ---- domain 参数（K-4）


@pytest.mark.parametrize(("given", "domain"), [
    ("bazi", "bazi"), ("BAZI", "bazi"), (" Bazi ", "bazi"), ("八字", "bazi"), ("八字四柱", "bazi"), ("八字四柱 · 操作手册", "bazi"),
    ("八字断语库", "bazi_pithy"), ("Bazi-Pithy", "bazi_pithy"), ("bazi pithy", "bazi_pithy"),
    ("紫微斗数", "ziwei"), ("紫微斗數", "ziwei"), ("奇門遁甲", "dunjia"), ("大六壬", "liureng_manual"), ("六爻", "guazhan"),
    ("塔羅", "tarot"), ("擇日", "zeri"), ("量化盘", "germany"), ("QIMEN", "qimen"), ("Astro", "astro"),
])
def test_a_domain_is_accepted_by_id_or_display_name_in_either_script_and_any_case(given: str, domain: str) -> None:
    assert store.canonical_domain(given) == domain
    assert store.search_knowledge({"query": "用神", "domain": given})["domain"] == domain
    assert store.build_knowledge_registry(domain=given)["domains"][0]["domain"] == domain


@pytest.mark.parametrize("given", ["user", "USER", "自备知识库", "自備知識庫", "笔记", "Notes"])
def test_the_notes_folder_answers_to_its_names_too(tmp_path: Path, given: str) -> None:
    _put(tmp_path, "a.md", "空亡者，虚也。")
    result = knowledge_search.search_all(_settings(tmp_path), {"query": "空亡", "domain": given})
    assert result["domain"] == "user" and result["matches"][0]["key"] == "a"


def test_every_bundled_display_name_resolves_to_its_own_domain() -> None:
    """清单是从语料自己长出来的：以后收割进来的手册不用改代码就认。"""
    for domain, bundle in store.load_knowledge_bundles().items():
        assert store.canonical_domain(domain.upper()) == domain
        if bundle.get("label"):
            assert store.canonical_domain(bundle["label"]) == domain, bundle["label"]
    assert store.USER_DOMAIN == uk.USER_DOMAIN


@pytest.mark.parametrize("call", [
    lambda: store.search_knowledge({"query": "四化", "domain": "nope"}),
    lambda: store.read_knowledge_entry({"domain": "nope", "category": "x", "key": "y"}),
    lambda: store.build_knowledge_registry(domain="nope"),
    lambda: store.search_knowledge({"query": "四化", "domain": "user"}),  # 内置语料自己的函数不认 user
])
def test_an_unknown_domain_says_so_in_both_languages_and_lists_the_valid_ones(call) -> None:
    with pytest.raises(ToolValidationError) as caught:
        call()
    error = caught.value
    zh, _, en = str(error).partition(" / ")
    assert error.code == "knowledge.unknown_domain"
    assert "没有这个知识域" in zh and "Unknown knowledge domain" in en
    listed = {row["domain"] for row in error.details["valid_domains"]}
    assert set(store.load_knowledge_bundles()) <= listed
    for domain in ("bazi", "ziwei", "astro"):
        assert domain in zh and domain in en


def test_a_near_miss_gets_a_suggestion() -> None:
    with pytest.raises(ToolValidationError) as caught:
        knowledge_search.resolve_domain("bazzi")
    assert "bazi" in caught.value.details["suggestions"] and "Did you mean" in str(caught.value)


def test_a_name_that_covers_two_domains_says_which_one_was_searched(tmp_path: Path) -> None:
    result = knowledge_search.search_all(_settings(tmp_path), {"query": "用神", "domain": "八字"})
    assert result["domain"] == "bazi"
    assert any("bazi_pithy" in note and " / " in note for note in result["warnings"])
    assert "warnings" not in knowledge_search.search_all(_settings(tmp_path), {"query": "用神", "domain": "bazi"})


# ---- limit / offset（K-4）


@pytest.mark.parametrize(("payload", "limit", "offset", "said"), [
    ({"limit": 500}, 20, 0, "limit=500"),
    ({"limit": 0}, 8, 0, "limit=0"),
    ({"limit": -1}, 8, 0, "limit=-1"),
    ({"limit": "many"}, 8, 0, "limit='many'"),
    ({"limit": True}, 8, 0, "limit=True"),
    ({"offset": -3}, 8, 0, "offset=-3"),
    ({"offset": "x"}, 8, 0, "offset='x'"),
    ({"limit": 2.5}, 8, 0, "limit=2.5"),
])
def test_out_of_range_paging_is_reported_not_silently_replaced(tmp_path: Path, payload: dict, limit: int, offset: int, said: str) -> None:
    result = knowledge_search.search_all(_settings(tmp_path), {"query": "用神", **payload})
    assert (result["limit"], result["offset"]) == (limit, offset)
    assert [note for note in result["warnings"] if said in note and " / " in note], result["warnings"]


@pytest.mark.parametrize("payload", [{}, {"limit": 1}, {"limit": 20}, {"limit": "5"}, {"offset": 0}, {"offset": 3, "limit": 2}, {"limit": None}])
def test_valid_paging_is_taken_as_given_without_a_note(tmp_path: Path, payload: dict) -> None:
    result = knowledge_search.search_all(_settings(tmp_path), {"query": "用神", **payload})
    assert "warnings" not in result
    assert result["limit"] == int(payload.get("limit") or 8) and result["offset"] == int(payload.get("offset") or 0)


# ---- 没进索引的文件要说出来（K-U1）


def _mixed_folder(tmp_path: Path) -> None:
    _put(tmp_path, "盲派口诀.md", "# 盲派\n\n七杀有制化为权。\n")
    _put(tmp_path, "长文.markdown", "# 长文\n\n伤官见官。\n")
    _put(tmp_path, "plain.txt", "禄随忌走。\n")
    _put(tmp_path, "book.pdf", "%PDF-1.4 渊海子平")
    _put(tmp_path, "扫描.PDF", "%PDF-1.4 三命通会")
    _put(tmp_path, "notes.docx", "PK fake docx")
    _put(tmp_path, "data.json", '{"a": "三命通会"}')
    _put(tmp_path, "README", "no extension 滴天髓\n")
    _put(tmp_path, ".hidden.md", "# hidden\n甲己合土\n")
    _put(tmp_path, "sub/深层.md", "# 深层\n寅申巳亥\n")
    _put(tmp_path, "sub/图.png", "png")
    for junk in (".DS_Store", "Thumbs.db", "草稿.md~", "~$notes.docx", ".horosa-x.tmp"):
        _put(tmp_path, junk, "junk")


def test_files_that_are_not_read_are_counted_by_reason_and_extension(tmp_path: Path) -> None:
    _mixed_folder(tmp_path)
    overview = uk.overview(_settings(tmp_path))
    assert overview["count"] == 4  # .md / .markdown / .txt / 子目录里的 .md
    skipped = overview["not_indexed"]
    assert skipped["total"] == 7
    assert skipped["by_reason"] == {"unsupported_extension": 5, "no_extension": 1, "hidden": 1}
    assert skipped["by_extension"] == {".pdf": 2, "(none)": 1, ".docx": 1, ".json": 1, ".md": 1, ".png": 1}
    assert set(skipped["examples"]) == {"book.pdf", "扫描.PDF", "notes.docx", "data.json", "README", ".hidden.md", "sub/图.png"}
    assert skipped["supported_extensions"] == list(uk.SUFFIXES)
    chinese, english = skipped["message"].split(" / ", 1)
    assert "7 个文件没有读入" in chinese and ".pdf ×2" in chinese and ".md 或 .txt" in chinese
    assert "7 file(s)" in english and "were not read" in english and " / " not in english
    for suffix in uk.SUFFIXES:  # 说「只读哪几种」的清单就是代码里那一份
        assert suffix in chinese and suffix in english


def test_system_and_editor_droppings_are_not_reported(tmp_path: Path) -> None:
    _put(tmp_path, "a.md", "空亡者，虚也。")
    for junk in (".DS_Store", "Thumbs.db", "desktop.ini", "草稿.md~", "~$a.docx", ".horosa-x.tmp", ".obsidian/app.json"):
        _put(tmp_path, junk, "junk")
    assert "not_indexed" not in uk.overview(_settings(tmp_path))
    assert "warnings" not in uk.search_user(_settings(tmp_path), "空亡")


@pytest.mark.parametrize("domain", ["user", ""])
def test_a_search_says_which_files_it_could_not_look_in(tmp_path: Path, domain: str) -> None:
    """放了 PDF 的人搜「渊海子平」得到 0 条：原因是那个文件没读入，不是笔记里没有。"""
    _mixed_folder(tmp_path)
    result = knowledge_search.search_all(_settings(tmp_path), {"query": "渊海子平", "domain": domain})
    assert not [m for m in result["matches"] if m["domain"] == "user"]
    assert any("7 个文件没有读入" in w and ".pdf ×2" in w for w in result["warnings"]), result.get("warnings")


def test_the_readmes_name_the_same_formats_as_the_code() -> None:
    root = Path(__file__).resolve().parents[2]
    formats = " / ".join(f"`{suffix}`" for suffix in uk.SUFFIXES)
    for name in ("README.md", "README_EN.md"):
        assert formats in (root / name).read_text(encoding="utf-8"), f"{name} 没写 {formats}"


# ---- 同一条笔记的命中封顶要说出来，定义那一段要留下（N2）

SHASHA = ("# 七杀笔记\n\n#八字 #十神\n\n## 七杀的基本意思\n七杀又叫偏官，是克我而与我阴阳相同的那个十神。老师说：七杀有制为权，无制为祸。\n\n"
          "## 七杀格\n月令透七杀，身强喜食神制杀，身弱喜印化杀。忌财生杀。\n\n## 羊刃驾杀\n羊刃与七杀并见，杀刃相停，主武贵。\n")


def _read(settings: Settings, read: dict) -> str:
    return uk.read_entry(settings, read["key"], from_line=read.get("from_line"), max_lines=read.get("max_lines"))["text"]


def test_a_capped_note_keeps_the_passage_that_defines_the_term_and_says_what_it_left_out(tmp_path: Path) -> None:
    """冷客户端复现：笔记开头就是「七杀又叫偏官…」，搜「七杀」返回后两段、total_matched 3、next_offset null，定义永远拿不到。"""
    _put(tmp_path, "七杀笔记.md", SHASHA)
    _put(tmp_path, "紫微随记.txt", "紫微随记\n七杀星在命宫，主刚烈。\n")
    settings = _settings(tmp_path)
    result = knowledge_search.search_all(settings, {"query": "七杀", "domain": "user"})
    mine = [m for m in result["matches"] if m["key"] == "七杀笔记"]
    assert len(mine) == 2 and any("七杀又叫偏官" in m["snippet"] for m in mine)  # 定义那一段在留下的两段里
    assert result["total_matched"] == 3 and result["total_passages"] == 4  # 封顶后能翻到 3 条，封顶前命中 4 段
    more = mine[0]["more_in_note"]
    assert "more_in_note" not in mine[1]  # 只在该笔记的第一条命中上说一次
    assert more["count"] == 1 and len(more["read"]) == 1
    chinese, english = more["note"].split(" / ", 1)
    assert "还有 1 段命中没有列" in chinese and "1 more matching passage" in english
    # 给的精读参数拿去就能读，读到的正是没列出的那一段
    assert more["read"][0] == {"domain": "user", "key": "七杀笔记", "from_line": 11, "max_lines": 2}
    assert _read(settings, more["read"][0]).strip() == "## 羊刃驾杀\n羊刃与七杀并见，杀刃相停，主武贵。"


def test_every_matching_passage_of_a_capped_note_is_either_listed_or_handed_over_as_a_read(tmp_path: Path) -> None:
    sections = "\n\n".join(f"## 第{n}节\n\n空亡在第{n}节里又出现一次：" + "旬空之说，各家不同。" * 12 for n in range(1, 8))
    _put(tmp_path, "长笔记.md", "# 长笔记\n\n空亡者，旬中无干之支也：这是开头的定义。" + "先讲来历。" * 30 + "\n\n" + sections)
    settings = _settings(tmp_path)
    result = uk.search_user(settings, "空亡")
    listed = result["matches"]
    assert len(listed) == 2 and "这是开头的定义" in "".join(_read(settings, m["read"])[:400] for m in listed)
    more = listed[0]["more_in_note"]
    assert result["total_passages"] == 2 + more["count"] and more["count"] == len(more["read"]) >= 5
    for read in more["read"]:
        assert "空亡" in _read(settings, read)
    spans = sorted((r["from_line"], r["from_line"] + r["max_lines"] - 1) for r in more["read"])
    assert spans == sorted(set(spans))


def test_an_uncapped_search_carries_no_cap_fields(tmp_path: Path) -> None:
    _put(tmp_path, "a.md", "空亡者，虚也。")
    result = uk.search_user(_settings(tmp_path), "空亡")
    assert "total_passages" not in result and "more_in_note" not in result["matches"][0]


def test_the_left_out_notice_survives_fusion_with_bundled_results(tmp_path: Path) -> None:
    _put(tmp_path, "七杀笔记.md", SHASHA)
    for limit in (8, 2, 1):
        page = knowledge_search.search_all(_settings(tmp_path), {"query": "七杀", "limit": limit})["matches"]
        mine = [m for m in page if m["domain"] == "user"]
        if mine:  # 这一页里只要有这条笔记的命中，就得有一条带着说明
            assert sum("more_in_note" in m for m in mine) == 1 and "more_in_note" in mine[0], limit


# ---- 空的自备知识库、当前工具面上的精读工具（N3）


def test_searching_an_empty_notes_library_says_where_it_is_and_how_to_fill_it(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    result = knowledge_search.search_all(settings, {"query": "七杀", "domain": "user"})
    library = result["library"]
    assert result["total_matched"] == 0
    assert library["exists"] is False and library["count"] == 0 and library["dir"] == str(uk.knowledge_dir(settings))
    chinese, english = library["how_to_add"].split(" / ", 1)
    assert "文件夹还不存在" in chinese and "does not exist yet" in english
    for suffix in uk.SUFFIXES:
        assert suffix in chinese and suffix in english
    # 文件夹在、但里面只有不读的格式：也算空，并且说出有几个文件没读入
    _put(tmp_path, "book.pdf", "%PDF")
    library = knowledge_search.search_all(settings, {"query": "七杀", "domain": "user"})["library"]
    assert library["exists"] is True and library["count"] == 0 and library["not_indexed"] == 1
    assert "还没有读入任何笔记" in library["how_to_add"]
    # 有笔记了就不再带
    _put(tmp_path, "a.md", "空亡者，虚也。")
    assert "library" not in knowledge_search.search_all(settings, {"query": "七杀", "domain": "user"})
    # 不限域的检索不拿空库说事
    assert "library" not in knowledge_search.search_all(_settings(tmp_path / "other"), {"query": "七杀"})


@pytest.mark.parametrize("compact", [False, True])
def test_the_read_hint_names_a_tool_this_surface_really_exposes(tmp_path: Path, compact: bool) -> None:
    """精简面没有 horosa_knowledge_read：结果里照旧写它，冷客户端照着调得到 Unknown tool。"""
    import asyncio
    import json
    import re

    from mcp.client import Client

    from horosa_skill.service import HorosaSkillService
    from horosa_skill.surfaces.mcp_server import create_mcp_server

    _put(tmp_path, "七杀笔记.md", SHASHA)
    settings = _settings(tmp_path, mcp_compact=compact)
    mcp = create_mcp_server(HorosaSkillService(settings), settings)

    async def run() -> tuple[set[str], dict, dict]:
        async with Client(mcp) as client:
            names = {tool.name for tool in (await client.list_tools()).tools}
            found = json.loads((await client.call_tool("horosa_knowledge_search", {"query": "七杀", "domain": "user"})).content[0].text)
            hint_tool = re.search(r"horosa_\w+", found["how_to_read"]).group(0)
            read = found["matches"][0]["read"]
            arguments = read if hint_tool == "horosa_knowledge_read" else {"tool_name": "knowledge_read", "request": read}
            body = json.loads((await client.call_tool(hint_tool, arguments)).content[0].text)
            return names, found, body

    names, found, body = asyncio.run(run())
    chinese, english = found["how_to_read"].split(" / ", 1)
    for half in (chinese, english):
        first = re.search(r"horosa_\w+", half).group(0)
        assert first in names, f"{first} 不在这个工具面上"
        if compact:
            assert set(re.findall(r"horosa_\w+", half)) <= names
    assert ("horosa_knowledge_read" in names) is (not compact)
    assert body["ok"] is True and "月令透七杀" in json.dumps(body, ensure_ascii=False)  # 照着提示调，真的读到了
