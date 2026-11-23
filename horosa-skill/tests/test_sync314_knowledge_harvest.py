"""上游 v3.14.0 把帮助改成「一页一本书、一技法一章」之后的知识包收割（scripts/harvest_help_books.mjs + gen_knowledge_packs.py）。

旧生成器拿正则切 JSX（`<TabPane tab=…>`、`render<Name>()`），新结构下一条都收不到。现在把上游的手册模块原样打包运行：
书单取上游注册表，章取上游 `bookChapters()`，正文是 `chapter.render()` 的元素树转成 Markdown，并逐章与上游自己的纯文本
（`helpElementToText`）对账。本文件分三段：

1. 收割器（要 Node 与 horosa-core-js 的 devDependencies：esbuild / react；CI 只装运行依赖，那里按 `[host]` 跳过）——对着
   `tests/fixtures/sync314_knowledge_upstream/`（手写的上游帮助布局缩影）跑真的收割器；
2. 落包（纯函数 `build_packs`，不要 Node）；
3. 已提交的包与读取（离线，CI 也跑）。

每条守卫的负向对照写在各自的 docstring 里（注回了什么缺陷、红在哪）。
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from horosa_skill.errors import ToolValidationError
from horosa_skill.knowledge import store
from skips import needs_upstream, reason

ROOT = Path(__file__).resolve().parents[1]
HARVESTER = ROOT / "scripts" / "harvest_help_books.mjs"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sync314_knowledge_upstream"
PACK_DIR = ROOT / "src" / "horosa_skill" / "knowledge" / "data" / "helpdocs"
SRC_REL = "Horosa-Web/astrostudyui/src"

_spec = importlib.util.spec_from_file_location("gen_knowledge_packs", ROOT / "scripts" / "gen_knowledge_packs.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

_HAS_NODE_STACK = shutil.which("node") is not None and all(
    (ROOT / "horosa-core-js" / "node_modules" / name).is_dir() for name in ("esbuild", "react"))
needs_harvester = pytest.mark.skipif(
    not _HAS_NODE_STACK, reason=reason("host", "node or horosa-core-js devDependencies (esbuild / react) not installed — `npm ci` in horosa-core-js"))


# ---- 1. 收割器 ------------------------------------------------------------------------------------------------------


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
                   check=True, capture_output=True, env={"PATH": os.environ["PATH"]})


def _upstream(tmp_path: Path, edits: dict[str, tuple[str, str]] | None = None) -> Path:
    """缩影上游的一份提交过的检出。edits：{相对 src 的路径: (原文, 换成)}，提交前改好。"""
    root = tmp_path / "upstream"
    shutil.copytree(FIXTURE, root / SRC_REL)
    (root / "Horosa_Desktop_Installer").mkdir()
    (root / "Horosa_Desktop_Installer" / "package.json").write_text('{"version": "9.9.9"}\n', encoding="utf-8")
    for relative, (old, new) in (edits or {}).items():
        path = root / SRC_REL / relative
        text = path.read_text(encoding="utf-8")
        assert text.count(old) == 1, f"fixture edit does not apply exactly once: {relative}: {old!r}"
        path.write_text(text.replace(old, new), encoding="utf-8")
    _git(tmp_path, "init", "-q", str(root))
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "fixture")
    return root


def _harvest(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["node", str(HARVESTER), "--source-root", str(root), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)


def _books(root: Path, *args: str) -> dict[str, dict]:
    done = _harvest(root, *args)
    assert done.returncode == 0, done.stderr
    return {book["tab"]: book for book in json.loads(done.stdout)["books"]}


def _chapter(book: dict, key: str) -> dict:
    return next(chapter for group in book["groups"] for chapter in group["chapters"] if chapter["key"] == key)


# 手写的期望（对着 fixtures/…/alpha/chapters.js 的 JSX 一行行写的，不是把输出抄回来）
FIRST_CHAPTER = """\
**第一法**是导语,讲清这一章做什么。

## 原理与算法

正文一段,带**加粗词**与 斜体。两章共用的一句话,来自模块级常量。

### 卡片标题

- **键一**：值一
- **# 井号开头的键**：值里有**加粗**

共用片段:没有标记的函数组件,界面上照样显示。

## 设置逐项

| 选项 | 取值 | 缺省 |
| --- | --- | --- |
| 年长 | 回归年 / 恒星年 | 回归年 |
| 竖线 | a \\| b | 无 |

1. 先选方法
2. 再看期表

- 列表一
- 列表二:
  - 子项甲
  - 子项乙

\\# 井号开头的段落不是标题

> 说明：换盘会清掉查看位置。"""


@needs_harvester
def test_the_book_list_groups_and_chapters_come_from_the_upstream_book_objects(tmp_path: Path) -> None:
    """书单 = 注册表，分组与章 = 各册的 book：键、章名、别名、组的提示语都原样带出。

    负向对照：把收割器里 `aliases: (chapter.aliases || [])…` 换成 `aliases: []`，本条红在 `first["aliases"]`。"""
    books = _books(_upstream(tmp_path))
    assert list(books) == ["alphatab", "betatab"]
    alpha = books["alphatab"]
    assert (alpha["component"], alpha["file"], alpha["title"]) == ("AlphaHelpDoc", "components/help/AlphaHelpDoc.js", "甲术 · 操作手册")
    assert [(g["key"], g["label"], g["hint"]) for g in alpha["groups"]] == [("methods", "两法", "甲术的两种算法。")]
    first = _chapter(alpha, "first")
    assert (first["label"], first["aliases"]) == ("第一法", ["one", "First"])
    assert [(g["key"], [c["key"] for c in g["chapters"]]) for g in books["betatab"]["groups"]] == [
        ("own", ["own", "alphaAll"]), ("alpha", ["alpha.first", "alpha.second"])]


@needs_harvester
def test_a_chapter_becomes_markdown_that_keeps_its_structure(tmp_path: Path) -> None:
    """小节 → ##、卡片标题 → ###、键值行 → 「- **键**：值」、选项表 → Markdown 表（格内竖线转义）、步骤 → 编号、嵌套列表缩进、
    提示框 → 「> 说明：…」、段首的 # 转义、模块级常量与 props 里的字（选项表 / 步骤）都在。

    负向对照（各改收割器一处，本条都红）：键值行不加粗 → 「- 键一：值一」；删掉段首 # 的转义 → 「# 井号开头的段落不是标题」
    成了一级标题；表格不转义竖线 → 那一行变成四格。"""
    assert _chapter(_books(_upstream(tmp_path))["alphatab"], "first")["text"] == FIRST_CHAPTER


@needs_harvester
def test_a_chapter_is_attributed_to_the_file_that_holds_its_text(tmp_path: Path) -> None:
    """章的出处是正文真正所在的文件（星运手册的章在 help/direction/chapters*.js，不在 34 行的 DirectionHelpDoc.js）；
    合订本自己拼出来的章（combined）出处是合订本那个文件。书的 files = 这本书 import 到的手册文件。

    负向对照：`file: fileOf(chapter.render) || file` 换成 `file`，本条红在 alpha/chapters.js 那一行。"""
    books = _books(_upstream(tmp_path))
    assert _chapter(books["alphatab"], "first")["file"] == "components/help/alpha/chapters.js"
    assert _chapter(books["betatab"], "alpha.second")["file"] == "components/help/alpha/chapters.js"
    assert _chapter(books["betatab"], "alphaAll")["file"] == "components/help/BetaHelpDoc.js"
    assert books["alphatab"]["files"] == ["components/help/AlphaHelpDoc.js", "components/help/alpha/chapters.js"]
    assert books["betatab"]["files"] == ["components/help/AlphaHelpDoc.js", "components/help/BetaHelpDoc.js", "components/help/alpha/chapters.js"]
    assert "components/help/HelpBook.js" not in books["betatab"]["files"], "外壳与样式件不算哪一册的正文文件"


@needs_harvester
def test_a_function_component_the_reference_text_skips_is_harvested_as_displayed_and_reported(tmp_path: Path) -> None:
    """没标 __helpPure 的函数组件：帮助弹窗照样渲染，上游给 AI 的纯文本却不调用它（v3.14.0 星运手册的 TimeBlockNote，七章各少一段）。
    知识包按界面所见收，名字报出来。

    负向对照：收割器里去掉 `type.__helpPure = true`（只自己调用、不让参考文本同口径），对账立刻红：
    「harvested text differs from upstream helpElementToText … 共用片段」。真上游上同样操作，红的正是那七章。"""
    done = _harvest(_upstream(tmp_path))
    assert done.returncode == 0, done.stderr
    payload = json.loads(done.stdout)
    assert payload["unmarked_function_components"] == {"SharedNote": 1}
    text = _chapter({b["tab"]: b for b in payload["books"]}["alphatab"], "first")["text"]
    assert text.count("共用片段:没有标记的函数组件,界面上照样显示。") == 1


@needs_harvester
def test_the_committed_blob_is_harvested_not_the_working_tree(tmp_path: Path) -> None:
    """正文与出处同源：出处记的是 commit，正文就得取那次提交的 blob（上游维护机常年有未提交的改动）。

    负向对照：`makeSource` 里把读 blob 换成读磁盘，第一条断言红（收到了「未提交的改动」）。"""
    root = _upstream(tmp_path)
    path = root / SRC_REL / "components/help/alpha/chapters.js"
    path.write_text(path.read_text(encoding="utf-8").replace("第二法的导语。", "未提交的改动。"), encoding="utf-8")
    assert _chapter(_books(root)["alphatab"], "second")["text"].startswith("第二法的导语。")
    assert _chapter(_books(root, "--worktree")["alphatab"], "second")["text"].startswith("未提交的改动。")


CHAPTERS = "components/help/alpha/chapters.js"
BROKEN_UPSTREAMS = {
    # 名字: (改哪个文件, 原文, 换成, 报错里该有的字)
    "unknown-tag": (CHAPTERS, "<Lead>第二法的导语。</Lead>", "<video>第二法的导语。</video>", "unsupported tag <video>"),
    "render-throws": (CHAPTERS, "<Lead>第二法的导语。</Lead>", "{(()=>{ throw new Error('chapter exploded'); })()}", "chapter exploded"),
    "duplicate-key": (CHAPTERS, "key: 'second',", "key: 'first',", "duplicate chapter key"),
    "empty-chapter": (CHAPTERS, "<Lead>第二法的导语。</Lead>\n\t\t\t\t<Section title=\"怎么读\">\n\t\t\t\t\t<p style={p}>第二法正文,足够长的一段话,用来当作一章的内容。</p>\n\t\t\t\t</Section>",
                      "", "help text for this chapter is empty"),
    "no-label": (CHAPTERS, "label: '第二法',", "", "chapter has no label"),
    "manual-without-a-book": ("components/help/AlphaHelpDoc.js", "\tstatic book = HELP_BOOK;\n", "", "has no static book"),
    "book-without-title": ("components/help/AlphaHelpDoc.js", "\ttitle: '甲术 · 操作手册',\n", "", "book has no title"),
    "unresolved-import": (CHAPTERS, "from '../helpDocStyle';", "from '../helpDocStyleGone';", "cannot resolve ../helpDocStyleGone"),
    # 桩（界面库）的值被当成正文：静默成空串就是丢字
    "stub-used-as-text": (CHAPTERS, "<Lead>第二法的导语。</Lead>", "<Lead>{`${require('antd').version}`}</Lead>", "stubbed module value was used as text"),
    "stub-rendered": (CHAPTERS, "<Lead>第二法的导语。</Lead>", "{React.createElement(require('antd').Alert, null, '第二法的导语。')}", "renders a stubbed component"),
    # 带 hooks 的函数组件不能脱离 React 渲染直接调用：抛错即失败，不许退回「只取 children」
    "hook-component": (CHAPTERS, "<Lead>第二法的导语。</Lead>", "{React.createElement(()=>{ React.useState(0); return <p>第二法的导语。</p>; })}", "FAIL"),
    # 参考文本里有、收割结果里没有的字 = 丢字
    "reference-has-more-text": ("utils/aiTools/helpText.js", "if(type === 'mark')", "if(type === 'b')", "differs from upstream helpElementToText"),
}


@needs_harvester
@pytest.mark.parametrize("name", sorted(BROKEN_UPSTREAMS))
def test_a_structure_the_harvester_cannot_read_fails_instead_of_yielding_an_empty_entry(tmp_path: Path, name: str) -> None:
    """解析不了就失败（非 0 退出、stdout 没有半份 JSON），不是静默产出空条目或少一章。

    每个参数本身就是一次负向对照：同一棵缩影上游不改时收割成功（上面几条），改这一处就红。
    `reference-has-more-text` 是对账本身的对照：参考文本每个加粗词后多出几个字，收割结果里没有，对账报出第一处差异。"""
    relative, old, new, expected = BROKEN_UPSTREAMS[name]
    done = _harvest(_upstream(tmp_path, {relative: (old, new)}))
    assert done.returncode != 0 and done.stdout == "", (done.returncode, done.stdout[:200])
    assert "harvest-help-books: FAIL" in done.stderr and expected in done.stderr, done.stderr


@needs_harvester
def test_a_checkout_without_the_help_registry_is_refused(tmp_path: Path) -> None:
    root = _upstream(tmp_path)
    _git(root, "rm", "-q", f"{SRC_REL}/components/help/techniqueHelpRegistry.js")
    _git(root, "commit", "-q", "-m", "registry gone")
    done = _harvest(root)
    assert done.returncode != 0 and "the help registry moved" in done.stderr


# ---- 2. 落包（纯函数） ------------------------------------------------------------------------------------------------

LONG = "这一章的正文要够长才算一章,不是空壳。"


def _harvest_dict() -> dict:
    """一份合成的收割结果：甲册两章；乙册 = 自己一章 + 甲册整册合排 + 甲册两章原样搬来（键改过）。"""
    first = {"key": "first", "label": "第一法", "aliases": ["one"], "file": "components/help/alpha/chapters.js", "text": f"第一法。{LONG}"}
    second = {"key": "second", "label": "第二法", "aliases": [], "file": "components/help/alpha/chapters.js", "text": f"第二法。{LONG}"}
    alpha = {"tab": "alphatab", "component": "AlphaHelpDoc", "file": "components/help/AlphaHelpDoc.js", "title": "甲术 · 操作手册",
             "files": ["components/help/AlphaHelpDoc.js", "components/help/alpha/chapters.js"],
             "groups": [{"key": "methods", "label": "两法", "hint": "甲术的两种算法。", "chapters": [first, second]}]}
    beta = {"tab": "betatab", "component": "BetaHelpDoc", "file": "components/help/BetaHelpDoc.js", "title": "乙术合订 · 操作手册",
            "files": ["components/help/AlphaHelpDoc.js", "components/help/BetaHelpDoc.js", "components/help/alpha/chapters.js"],
            "groups": [
                {"key": "own", "label": "本册", "hint": "", "chapters": [
                    {"key": "own", "label": "乙术本法", "aliases": [], "file": "components/help/BetaHelpDoc.js", "text": f"乙术。{LONG}"},
                    {"key": "alphaAll", "label": "甲术", "aliases": ["alpha"], "file": "components/help/BetaHelpDoc.js",
                     "text": f"{first['text']}\n\n# 第二法\n\n{second['text']}"}]},
                {"key": "alpha", "label": "甲术各法", "hint": "", "chapters": [
                    {**first, "key": "alpha.first", "aliases": []}, {**second, "key": "alpha.second"}]}]}
    return {"schema": "horosa.help_books.v1", "books": [alpha, beta]}


@pytest.fixture
def two_books(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gen, "HELPDOC_DOMAINS", {"AlphaHelpDoc": ("alpha", "甲术"), "BetaHelpDoc": ("beta", "乙术合订")})
    monkeypatch.setattr(gen, "EXCLUDED_HELPDOCS", {})


def _build(harvest: dict) -> dict[str, dict]:
    return gen.build_packs(harvest, app_version="9.9.9", sha="abcdef012345", committed_at="2026-11-12T00:00:00+00:00")


def test_one_chapter_becomes_one_entry_keyed_by_the_upstream_chapter_key(two_books: None) -> None:
    """条目键 = 上游章节键，章名在 label，组名、别名、全书目录、逐条出处都在。

    负向对照：`build_packs` 里把 `"tab": chapter["key"]` 去掉，本条红在 source 那一行（逐条出处缺章节键）。"""
    alpha = _build(_harvest_dict())["alpha"]
    assert (alpha["schema"], alpha["domain"], alpha["label"], alpha["generated_at"]) == (
        "horosa.knowledge.helpdoc.v1", "alpha", "甲术 · 操作手册", "2026-11-12T00:00:00+00:00")
    assert alpha["source"] == {
        "file": "components/help/AlphaHelpDoc.js", "files": ["components/help/AlphaHelpDoc.js", "components/help/alpha/chapters.js"],
        "help_tab": "alphatab", "upstream_source_marker": "xingque_help_docs", "upstream_app_version": "9.9.9", "upstream_git_sha": "abcdef012345"}
    assert alpha["groups"] == [{"key": "methods", "label": "两法", "hint": "甲术的两种算法。", "chapters": ["first", "second"]}]
    assert alpha["categories"] == [{"name": "手册", "entries": [
        {"key": "first", "label": "第一法", "group": "两法", "aliases": ["one"], "text": f"第一法。{LONG}",
         "source": {"file": "components/help/alpha/chapters.js", "tab": "first", "book": "alphatab"}},
        {"key": "second", "label": "第二法", "group": "两法", "text": f"第二法。{LONG}",
         "source": {"file": "components/help/alpha/chapters.js", "tab": "second", "book": "alphatab"}}]}]
    assert "includes" not in alpha


def test_a_chapter_borrowed_from_another_book_is_stored_once(two_books: None) -> None:
    """合订本里取自别册的章不重复存正文：原样搬来的记 {domain, key}（键改过也认，按正文判），整册合排成一章的记 {domain, keys}。

    负向对照：`_borrowed_from` 恒返回 None，本条红在 entries（乙册四条全成了自己的正文，同一段话在两个域里各存一份）。"""
    beta = _build(_harvest_dict())["beta"]
    assert [entry["key"] for entry in beta["categories"][0]["entries"]] == ["own"]
    assert beta["includes"] == [
        {"key": "alphaAll", "label": "甲术", "group": "本册", "aliases": ["alpha"], "ref": {"domain": "alpha", "keys": ["first", "second"]}},
        {"key": "alpha.first", "label": "第一法", "group": "甲术各法", "ref": {"domain": "alpha", "key": "first"}},
        {"key": "alpha.second", "label": "第二法", "group": "甲术各法", "ref": {"domain": "alpha", "key": "second"}}]
    assert beta["groups"][1]["chapters"] == ["alpha.first", "alpha.second"], "目录仍是全书的"


def test_a_chapter_that_only_resembles_another_book_stays_its_own(two_books: None) -> None:
    """改过一个字的章不是别册的章：正文照收（按正文逐字判，不按章名 / 键猜）。"""
    harvest = _harvest_dict()
    harvest["books"][1]["groups"][1]["chapters"][0]["text"] += "合订本里多写的一句。"
    beta = _build(harvest)["beta"]
    assert [entry["key"] for entry in beta["categories"][0]["entries"]] == ["own", "alpha.first"]
    assert [item["key"] for item in beta["includes"]] == ["alphaAll", "alpha.second"]


@pytest.mark.parametrize(("mutate", "message"), [
    (lambda h: h["books"].append({**h["books"][0], "tab": "newtab", "component": "BrandNewHelpDoc"}), "neither harvested nor explicitly excluded: BrandNewHelpDoc"),
    (lambda h: h["books"].pop(0), "missing from the upstream help registry: AlphaHelpDoc"),
    (lambda h: h["books"][0]["groups"][0]["chapters"][1].update(text="太短"), "alpha/second: chapter text is 2 characters"),
    (lambda h: h["books"].append({**h["books"][0], "tab": "othertab"}), "registered under two help tabs"),
    (lambda h: h["books"][1]["groups"].__setitem__(0, {"key": "own", "label": "本册", "hint": "", "chapters": []}), "every chapter of this book is borrowed"),
    (lambda h: h.update(schema="something.else"), "unexpected harvest schema"),
])
def test_the_packer_refuses_what_it_cannot_account_for(two_books: None, mutate, message: str) -> None:
    """上游多出一册没人认领的手册、白名单里的手册不见了、空壳章、整册都是借来的：一律 HarvestError，不落半份包。

    负向对照 = 参数表本身：不动的合成收割结果能落包（上面三条），每个 mutate 各红一处。"""
    harvest = _harvest_dict()
    mutate(harvest)
    with pytest.raises(gen.HarvestError, match=re.escape(message)):
        _build(harvest)


def test_every_manual_is_harvested_or_explicitly_excluded() -> None:
    """白名单与排除表不相交；检测只认 *HelpDoc 组件（文件名或组件名），外壳与样式件不算手册。"""
    assert not set(gen.EXCLUDED_HELPDOCS) & set(gen.HELPDOC_DOMAINS)
    assert gen.unlisted_helpdocs(["components/guolao/GuoLaoHelpDoc.js", "HelpBook.js", "helpDocStyle.js", "techniqueHelpRegistry.js",
                                  "FengshuiHelpDoc", "BrandNewHelpDoc.js", "OtherNewHelpDoc"]) == ["BrandNewHelpDoc", "OtherNewHelpDoc"]
    domains = [domain for domain, _label in gen.HELPDOC_DOMAINS.values()]
    assert len(domains) == len(set(domains)), "两册手册不能落进同一个域"
    # 七政四余的手册在 components/guolao/：只扫 components/help/ 的旧实现从没收过它
    assert {"guolao", "dongya", "zhufang", "mingother"} <= set(domains)


@needs_harvester
def test_generating_twice_is_byte_identical_and_check_notices_a_stale_or_orphan_pack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                                                    capsys: pytest.CaptureFixture[str]) -> None:
    """端到端（缩影上游 → 收割器 → 落包 → 磁盘）：同一提交重跑逐字节一致；`--check` 在包被手改、少了、或多出没人认领的包时红；
    重新生成会删掉白名单里已经没有的包。

    负向对照：`--check` 分支里去掉 `stale_files` 那一半条件，「orphan」那条断言红（多出的包没人发现）。"""
    root = _upstream(tmp_path)
    out = tmp_path / "packs"
    monkeypatch.setattr(gen, "HELPDOC_DOMAINS", {"AlphaHelpDoc": ("alpha", "甲术"), "BetaHelpDoc": ("beta", "乙术合订")})
    monkeypatch.setattr(gen, "EXCLUDED_HELPDOCS", {})
    monkeypatch.setattr(gen, "OUT_DIR", out)
    monkeypatch.setenv("HOROSA_SOURCE_ROOT", str(root))

    def run(*args: str) -> int:
        monkeypatch.setattr("sys.argv", ["gen_knowledge_packs.py", *args])
        return gen.main()

    assert run() == 0
    first = {path.name: path.read_bytes() for path in sorted(out.glob("*.json"))}
    assert sorted(first) == ["alpha.json", "beta.json"]
    alpha = json.loads(first["alpha.json"])
    assert alpha["source"]["upstream_app_version"] == "9.9.9" and len(alpha["source"]["upstream_git_sha"]) == 12
    assert alpha["categories"][0]["entries"][0]["text"].startswith("**第一法**是导语")
    assert [item["ref"] for item in json.loads(first["beta.json"])["includes"]] == [
        {"domain": "alpha", "keys": ["first", "second"]}, {"domain": "alpha", "key": "first"}, {"domain": "alpha", "key": "second"}]
    assert run() == 0 and {path.name: path.read_bytes() for path in sorted(out.glob("*.json"))} == first
    assert run("--check") == 0
    assert "SharedNote" in capsys.readouterr().out, "上游参考文本跳过的函数组件要说出来"

    (out / "alpha.json").write_text(first["alpha.json"].decode("utf-8").replace("第一法", "第一发"), encoding="utf-8")
    assert run("--check") == 1 and "stale vs upstream HEAD: alpha" in capsys.readouterr().err
    (out / "alpha.json").write_bytes(first["alpha.json"])
    (out / "gone.json").write_text("{}", encoding="utf-8")
    assert run("--check") == 1 and "orphan pack files: gone.json" in capsys.readouterr().err
    assert run() == 0 and not (out / "gone.json").exists()
    (out / "bazi_pithy.json").write_text("{}", encoding="utf-8")  # 别的生成器的包（EXTRA_PACK_DOMAINS）不归这里删
    assert run("--check") == 0 and (out / "bazi_pithy.json").exists()


@needs_harvester
def test_an_unregistered_manual_file_fails_generation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """help/ 目录里写了一册手册却没登记进注册表（帮助弹窗打不开它，收割器也看不见）：生成器要报，不是当它不存在。"""
    root = _upstream(tmp_path)
    (root / SRC_REL / "components/help/GammaHelpDoc.js").write_text("export default null;\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "an unregistered manual")
    monkeypatch.setattr(gen, "HELPDOC_DOMAINS", {"AlphaHelpDoc": ("alpha", "甲术"), "BetaHelpDoc": ("beta", "乙术合订")})
    monkeypatch.setattr(gen, "EXCLUDED_HELPDOCS", {})
    monkeypatch.setattr(gen, "OUT_DIR", tmp_path / "packs")
    monkeypatch.setenv("HOROSA_SOURCE_ROOT", str(root))
    monkeypatch.setattr("sys.argv", ["gen_knowledge_packs.py"])
    assert gen.main() == 1
    assert "GammaHelpDoc" in capsys.readouterr().err and not (tmp_path / "packs").exists()


# ---- 3. 已提交的包与读取 ----------------------------------------------------------------------------------------------

_NOT_TEXT = re.compile(r"[\s#*\-|·:：.\\>]")


def _book_packs() -> dict[str, dict]:
    return {domain: bundle for domain, bundle in store.load_helpdoc_bundles().items() if bundle.get("groups")}


def test_every_manual_pack_is_a_book_with_a_complete_table_of_contents() -> None:
    """每册 = 分组目录 + 章；目录里的每个键要么是本册的一条、要么是取自别册的一章，反过来也一样；键在册内唯一；逐条出处齐。

    负向对照：从 direction.json 的 entries 里删掉 timelords 一条（目录还列着它），本条红在「目录 ≠ 条目」。"""
    packs = _book_packs()
    assert set(packs) == {domain for domain, _label in gen.HELPDOC_DOMAINS.values()}
    for domain, pack in packs.items():
        entries = pack["categories"][0]["entries"]
        includes = pack.get("includes") or []
        keys = [entry["key"] for entry in [*entries, *includes]]
        assert len(keys) == len(set(keys)), f"{domain}: 章节键重复"
        listed = [key for group in pack["groups"] for key in group["chapters"]]
        assert sorted(listed) == sorted(keys), f"{domain}: 目录 ≠ 条目"
        labels = {group["label"] for group in pack["groups"]}
        for entry in entries:
            where = f"{domain}/{entry['key']}"
            assert entry["label"].strip() and entry["group"] in labels, where
            assert len(_NOT_TEXT.sub("", entry["text"])) >= gen.MIN_CHAPTER_CHARS, where
            assert entry["source"]["tab"] == entry["key"] and entry["source"]["book"] == pack["source"]["help_tab"], where
            assert entry["source"]["file"] in pack["source"]["files"], f"{where}: 章的出处文件不在这本书的文件清单里"
        assert pack["label"].endswith(" · 操作手册") and pack["source"]["file"] in pack["source"]["files"], domain


def test_no_chapter_text_is_stored_twice() -> None:
    """合订本（命 · 其他、辅盘里的量化盘一组）不把别册的章再存一遍：检索里不会出现两条一样的。

    负向对照：把 mingother.json 的 includes 里「dongya.tibetan」改回带正文的条目（正文抄 dongya/tibetan），本条红并点出两处坐标。"""
    seen: dict[str, tuple[str, str]] = {}
    for doc in store.search_docs():
        if doc.category != "手册":
            continue
        bare = _NOT_TEXT.sub("", doc.body)
        assert bare not in seen, f"{doc.domain}/{doc.key} 与 {'/'.join(seen[bare])} 正文相同"
        seen[bare] = (doc.domain, doc.key)


def test_borrowed_chapters_read_through_to_their_home_book() -> None:
    """合订本里取自别册的章照样读得到：读到的是本家那一条（domain / key / 出处都是本家的），`via` 记下从哪儿找过来的；
    整册合排的一章 = 本家全部章连起来。每个 ref 都指向真有的域与键。

    负向对照：`_read_helpdoc_entry` 里不查 includes（`_helpdoc_find([*entries], key)`），本条第一句就红：knowledge.helpdoc.unknown_key。"""
    packs = _book_packs()
    borrowed = [(domain, item) for domain, pack in packs.items() for item in pack.get("includes") or []]
    assert {domain for domain, _item in borrowed} == {"auxchart", "mingother"}
    for domain, item in borrowed:
        home = packs[item["ref"]["domain"]]
        home_entries = {entry["key"]: entry for entry in home["categories"][0]["entries"]}
        read = store.read_knowledge_entry({"domain": domain, "key": item["key"]})
        assert read["domain"] == item["ref"]["domain"] and read["via"] == {"domain": domain, "key": item["key"], "label": item["label"]}
        if "key" in item["ref"]:
            assert read["key"] == item["ref"]["key"] and read["rendered_text"] == home_entries[item["ref"]["key"]]["text"]
        else:
            assert item["ref"]["keys"] == [entry["key"] for entry in home["categories"][0]["entries"]], "整册合排 = 本家全部章"
            assert read["keys"] == item["ref"]["keys"] and all(home_entries[key]["text"] in read["rendered_text"] for key in item["ref"]["keys"])
            assert f"# {home_entries[item['ref']['keys'][1]]['label']}\n\n" in read["rendered_text"]
    tibetan = store.read_knowledge_entry({"domain": "mingother", "key": "dongya.tibetan"})
    assert (tibetan["domain"], tibetan["key"]) == ("dongya", "tibetan") and "DongyaHelpDoc.js" in tibetan["citation"]
    yanqin = store.read_knowledge_entry({"domain": "命·其他", "key": "演禽"})
    assert yanqin["domain"] == "yanqin" and "全册 4 章" in yanqin["title"] and yanqin["via"]["key"] == "xianqin"


@pytest.mark.parametrize(("domain", "given", "key"), [
    ("direction", "primarydirect", "primarydirect"),  # 章节键
    ("direction", "PrimaryDirect", "primarydirect"),  # 不分大小写
    ("direction", "主限法", "primarydirect"),  # 章名全等（「主限法盘」「主限天球」也含这三个字：全等先于包含）
    ("direction", "时主轮转", "timelords"),
    ("direction", "推运", "progressions"),  # 「赤纬推运」「恒星推运」「月相推运」也含这两个字：章名全等的那一条
    ("auxchart", "acg", "locastro"),  # 上游给这一章的别名
    ("germany", "Midpoint", "germany.midpoint"),
    ("cnyibu", "Jinkou", "jinkou"),  # v3.14.0 之前的键（方法名）
    ("bazi", "排盘设置", "setup"),  # v3.14.0 之前的键（页签名）= 现在的章名
    ("bazi", "格局", "geju"),  # 唯一包含
    ("yanqin", "overview", "xianqin"),
])
def test_a_chapter_answers_to_its_key_its_aliases_and_its_name(domain: str, given: str, key: str) -> None:
    """手册条目的键是上游的章节键（页面子页签的运行时键）；人说的是章名，旧包的键是页签名 / 方法名：都读得到同一条。

    负向对照：`_helpdoc_find` 只留第一步（键全等），除第一行外全红（knowledge.helpdoc.unknown_key）。"""
    assert store.read_knowledge_entry({"domain": domain, "key": given})["key"] == key


def test_an_ambiguous_fragment_is_refused_with_the_key_list() -> None:
    """「返照」同时在「太阳返照」「月亮返照」里：不替调用方挑一条。"""
    with pytest.raises(ToolValidationError) as caught:
        store.read_knowledge_entry({"domain": "direction", "key": "返照"})
    assert caught.value.code == "knowledge.helpdoc.unknown_key"
    assert {"solarreturn", "lunarreturn"} <= set(caught.value.details["available"])
    with pytest.raises(ToolValidationError) as missing:
        store.read_knowledge_entry({"domain": "mingother"})
    assert missing.value.code == "knowledge.helpdoc.key_required"
    assert "dongya.tibetan" in missing.value.details["keys"] and "策天飞星" in missing.value.details["labels"], "借来的章也在可读清单里"


def test_the_registry_gives_one_book_its_full_table_of_contents() -> None:
    """点名一个域：分组 → 章（键 + 章名），取自别册的章带本家坐标；列全部域时不带目录（33 章的星运手册一册就 2 KB）。"""
    direction = store.build_knowledge_registry("direction")["domains"][0]
    assert [group["label"] for group in direction["groups"]] == ["主限法", "方向类(推星)", "推运与推运图", "时主类(分段轮值)", "返照与流年", "工具与辅助"]
    assert sum(len(group["chapters"]) for group in direction["groups"]) == 33
    assert {"key": "timelords", "label": "时主轮转"} in direction["groups"][3]["chapters"]
    mingother = store.build_knowledge_registry("mingother")["domains"][0]
    chapters = {chapter["key"]: chapter for group in mingother["groups"] for chapter in group["chapters"]}
    assert chapters["dongya.tibetan"] == {"key": "dongya.tibetan", "label": "藏历藏占", "from": {"domain": "dongya", "key": "tibetan"}}
    assert "from" not in chapters["cetian"]
    assert all("groups" not in item for item in store.build_knowledge_registry()["domains"])


def test_manual_text_carries_no_markup_or_code_residue() -> None:
    """正文里没有 JSX / 代码残渣。旧的正则收割把 JSX 注释收成了正文（节气、合盘、辅助三册里的
    「{/* ───── 排盘设置 ───── */}」）；元素树里没有注释，这类残渣从结构上进不来。

    负向对照：往 jieqi.json 一章正文里放回「{/* ── 排盘设置 ── */}」，本条红并点出坐标。"""
    residue = re.compile(r"\{/\*|\*/\}|─{4,}|\[object Object\]|\bundefined\b|\bNaN\b|</?(?:div|span|p|b|li|ul|td|tr|section)\b[^>]*>|style=\{|className=")
    bad = [(doc.domain, doc.key, match.group(0)) for doc in store.search_docs() if doc.category == "手册" and (match := residue.search(doc.body))]
    assert bad == []


def test_option_tables_survive_as_well_formed_markdown_tables() -> None:
    """选项表没有塌：每张表有表头分隔行，每一行的格数与表头相同（格内的竖线已转义）。全库不少于 100 张。

    负向对照：收割器里表格不转义格内竖线（去掉 `.replace(/\\|/g, '\\\\|')`），含「a | b」取值的行格数对不上，本条红。"""
    tables = 0
    cells = lambda line: len(re.findall(r"(?<!\\)\|", line)) - 1  # noqa: E731
    for doc in store.search_docs():
        if doc.category != "手册":
            continue
        lines = doc.body.split("\n")
        for index, line in enumerate(lines):
            if not line.startswith("|") or (index and lines[index - 1].startswith("|")):
                continue
            block = []
            for row in lines[index:]:
                if not row.startswith("|"):
                    break
                block.append(row)
            assert len(block) >= 3 and re.fullmatch(r"\|( --- \|)+", block[1]), f"{doc.domain}/{doc.key}: {block[:2]}"
            assert {cells(row) for row in block} == {cells(block[0])}, f"{doc.domain}/{doc.key}: 表格各行格数不一：{block[0]}"
            tables += 1
    assert tables >= 100, tables


# 期望来自上游 v3.14.0 的发布说明（「新增『时主轮转』十二法：期表类（…）与事件类（…）」「新增『东亚』」「新增『诸方』」
# 「新增『变换盘』」「新增『黄道制』」），不是从包里抄的。
V3140_CONTENT = {
    ("direction", "timelords"): ["轮主", "轨主", "年度分配", "月相四分", "月亮单度主", "月亮九年", "九分主", "匀速点", "发展年龄", "周日象限", "对数时标", "月亮日"],
    ("direction", "persiandirected"): ["周期律"],
    ("auxchart", "transformchart"): ["变换", "宫位同转", "经典", "改进"],
    ("auxchart", "zodiacsystems"): ["十三星座", "银河黄道"],
    ("auxchart", "mundane"): ["周期表"],
    ("auxchart", "babylon"): ["天象实算"],
    ("auxchart", "locastro"): ["日食路径"],
    ("dongya", "tibetan"): ["藏历"], ("dongya", "zurkhai"): ["Zurkhai"], ("dongya", "sanmei"): ["算命学"],
    ("dongya", "ninestar"): ["九星气学"], ("dongya", "loshu"): ["洛书流年"], ("dongya", "iching"): ["易卦星盘"],
    ("zhufang", "mayan"): ["玛雅历"], ("zhufang", "dreamspell"): ["十三月亮历"], ("zhufang", "hd"): ["人类图"], ("zhufang", "spirit"): ["灵名字母"],
    ("astro_manual", "rightpanel"): ["细节", "专题主星", "受孕期", "危机日", "人体对应"],
    ("india", "tabs"): ["穿界"],
    ("mingother", "cetian"): ["策天飞星"],
    ("guolao", "su28"): ["回归今宿", "开禧", "授时历"],  # 七政四余手册此前从没收过；词取自上游该章的卡片标题
}


@pytest.mark.parametrize(("domain", "key"), sorted(V3140_CONTENT))
def test_the_v3_14_0_techniques_each_have_their_chapter(domain: str, key: str) -> None:
    """新技法的章在、讲的是它（发布说明点名的词都在那一章里）。旧生成器在新结构下产出的是空包，这些词一个都搜不到。"""
    text = store.read_knowledge_entry({"domain": domain, "key": key})["rendered_text"]
    assert [word for word in V3140_CONTENT[(domain, key)] if word not in text] == []


def test_the_direction_manual_is_one_chapter_per_technique() -> None:
    """星运手册：v3.13.2 是 6 个页签（逐法一览、时主类·子设置…），v3.14.0 是右侧 33 个页签每个一章。"""
    pack = _book_packs()["direction"]
    assert len(pack["categories"][0]["entries"]) == 33 and not pack.get("includes")
    assert {entry["source"]["file"] for entry in pack["categories"][0]["entries"]} == {
        "components/help/direction/chaptersDirectional.js", "components/help/direction/chaptersTimelord.js"}
    # 33 章的形状自 v3.14.0 起（之后的版本照此；不钉死版本号，重同步时不必改这里）
    assert tuple(int(x) for x in pack["source"]["upstream_app_version"].split(".")) >= (3, 14, 0)


# ---- 检索：新内容的用例与新别名 -----------------------------------------------------------------------------------------

_EVAL_SPEC = importlib.util.spec_from_file_location("eval_knowledge_search", ROOT / "scripts" / "eval_knowledge_search.py")
_EVAL = importlib.util.module_from_spec(_EVAL_SPEC)
_EVAL_SPEC.loader.exec_module(_EVAL)
# 2026-11-13 第一遍实测 0.957 / 0.986（69 条；未命中 1 条：「巴博周期」——发布说明的叫法，手册正文只写 Barbault）。只许往上调。
SYNC314_FLOOR = {"hit1": 0.94, "hit5": 0.97}


def test_the_new_content_is_found_by_its_terms() -> None:
    """contracts/knowledge_eval.json 的 sync314_2026_11_13：时主轮转十二法、变换盘、黄道制、东亚 / 诸方各子术、盘面细节各表、
    世运周期表、印占新表、七政四余，中文术语 + 语料里的拉丁写法 + 繁体。"""
    result = _EVAL.evaluate_set("sync314_2026_11_13")
    overall = result["overall"]
    assert overall["n"] >= 60 and overall["hit1"] >= SYNC314_FLOOR["hit1"] and overall["hit5"] >= SYNC314_FLOOR["hit5"], (overall, result["misses"])


@pytest.mark.parametrize(("query", "domain", "key"), [
    ("time lords", "direction", "timelords"), ("prenatal syzygy", "direction", "prenatalsyzygy"),
    ("zodiac systems", "auxchart", "zodiacsystems"), ("secondary progression", "direction", "progressions"),
    ("nine star", "dongya", "ninestar"),
])
def test_english_names_reach_the_chapter_through_the_upstream_chapter_key(query: str, domain: str, key: str) -> None:
    """新手册正文不再逐法列英文名；英文别名改认「上游章节键 ↔ 章名」这一层对照（prenatalsyzygy ↔ 产前朔望）。

    负向对照：从 TERM_ALIASES 里拿掉这一条，查询零命中（语料里没有空格分开的这个英文词）。"""
    result = store.search_knowledge({"query": query, "limit": 3})
    assert (result["matches"][0]["domain"], result["matches"][0]["key"]) == (domain, key) and result["aliases_used"]


def test_a_term_in_an_entrys_own_name_counts_when_several_terms_are_asked() -> None:
    """多词查询：条目自己的名字（章名 / 分类名）里有其中一个词的，排在几个词只在正文里凑齐的条目前面。
    「如何判断用神」→「判断 用神」：v3.14.0 的新章把「用神动变」「格局用神」挤出了前五。

    负向对照：`_NAMED_TERM_BONUS = 0`，第一条断言红（两条都掉到第 5 名以后）。"""
    matches = store.search_knowledge({"query": "如何判断用神", "limit": 5})["matches"]
    assert {("guazhan", "yong"), ("bazi", "geju")} & {(m["domain"], m["key"]) for m in matches}
    first = store.search_knowledge({"query": "比较盘和组合盘有什么区别", "limit": 3})["matches"][0]
    assert (first["domain"], first["key"]) == ("relative", "comp")


# ---- 已提交的包 = 上游 HEAD 收割出来的那一份（要上游检出） ------------------------------------------------------------------


@needs_harvester
@needs_upstream("Horosa-Web/astrostudyui/src/components/help/techniqueHelpRegistry.js")
def test_the_committed_packs_are_what_the_generator_produces_from_the_pinned_upstream() -> None:
    """修生成的东西就修生成器：包不许手改，也不许落后于生成器（v0.38.1 手改产物、v0.40.0 重跑即复发）。
    检出的 HEAD 不是收包时的那个提交时不比（那是下一次同步的事）。"""
    recorded = _book_packs()["direction"]["source"]["upstream_git_sha"]
    root = os.environ["HOROSA_SOURCE_ROOT"]
    head = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"], capture_output=True, text=True, encoding="utf-8").stdout.strip()
    if not head.startswith(recorded):
        pytest.skip(reason("upstream-checkout", f"checkout HEAD {head[:12]} is not the commit the packs were harvested from ({recorded})"))
    done = subprocess.run(["uv", "run", "python", str(ROOT / "scripts" / "gen_knowledge_packs.py"), "--check"], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    assert done.returncode == 0, done.stderr + done.stdout
