#!/usr/bin/env python
"""收割上游「操作手册」→ 知识包（B1：grounded interpretation 的地基）。

上游的操作手册是三十来份**方法论手册**（每个设置项的取值与差别、流派分歧、算法与口径），一直只活在桌面端
帮助页里——AI 客户端解读时最需要的正是这些口径知识。本脚本在维护机上读 `$HOROSA_SOURCE_ROOT`，把手册转成
结构化知识包入仓：

  src/horosa_skill/knowledge/data/helpdocs/<domain>.json
  { schema, domain, label, source:{file, files, help_tab, upstream_app_version, upstream_git_sha}, generated_at,
    groups:[{key, label, hint?, chapters:[章节键…]}],            # 全书目录（左栏菜单的同一份分组）
    categories:[{name:"手册", entries:[{key:<章节键>, label:<章名>, group:<组名>, aliases?, text:<markdown>,
                                         source:{file, tab:<章节键>, book:<页签键>}}]}],
    includes?:[{key, label, group, aliases?, ref:{domain, key} | {domain, keys:[…]}}] }   # 取自别册的章

**v3.14.0 起上游是「一页一本书、一技法一章」**（`components/help/HelpBook.js`）：每册手册导出
`book = { title, groups:[{ key, label, chapters:[{ key, label, aliases?, render }] }] }`，章节键 = 页面上该技法子页签
的运行时键。所以这里一章一条，条目键 = 章节键，中文章名在 `label`。此前按 `<TabPane>` / `render<Name>()` 的正则切
JSX，新结构下一条都收不到。现在不再拿正则猜 JSX：`scripts/harvest_help_books.mjs` 把上游手册模块原样打包运行，
书单取上游注册表（`techniqueHelpRegistry.js`，帮助弹窗用的同一张表），章取上游 `bookChapters()`，正文是
`chapter.render()` 的元素树转成 Markdown，并逐章与上游自己的 `helpElementToText`（给外部 AI 的纯文本）对账——
去掉排版记号后必须逐字相同。解析不了的结构（未知标签、渲染抛错、空章、重复键、没有 book 的手册）一律 FAIL。

纪律：
- **逐条带出处**（file + 章节键 + 上游版本 / commit）——SKILL.md 策略「引教义必带出处」的机器前提。章的 `file`
  是这章正文真正所在的文件（星运手册的章在 `help/direction/chapters*.js`，不在 34 行的 `DirectionHelpDoc.js`）。
- 抽取是**结构保持**的降级（小节 → `##`、卡片标题 → `###`、键值行 → `- **键**：值`、选项表 → Markdown 表、
  步骤 → 编号列表、提示框 → `> 提示：…`），不做任何改写；正文即上游文本。
- **一章只收一次**：合订本（命 · 其他 = 策天飞星 + 演禽 + 一掌经 + 东亚 + 诸方；辅盘里的量化盘一组）里取自别册的章
  不重复存正文，记在 `includes`（指向本家的域与键），`knowledge_read` 照样读得到，检索不出现两条一样的。
- 幂等：同一上游 commit 重跑输出逐字节一致（generated_at 取上游 commit 时间，不取 now）。
- **正文与出处同源**：默认读上游 **HEAD 提交的 blob**（`git show HEAD:<path>`），不读工作区——出处记的是 commit、
  正文却取自带未提交改动的磁盘文件，这份出处就是假的（上游维护机常年有 WIP）。`--worktree` 才读磁盘，只用于非 git
  的快照目录。
- **上游每一册手册要么收割、要么明文排除**：注册表里的组件、以及 `components/help/*HelpDoc.js`，既不在
  `HELPDOC_DOMAINS` 也不在 `EXCLUDED_HELPDOCS` 的，本脚本 FAIL。v0.35.0 之前白名单与已上架技法脱钩——择日十技法 /
  太乙 / 三式 / 演禽 / 一掌经 / 玄史的工具发了三个版本，它们的手册一册没收；七政四余的手册在 `components/guolao/`，
  旧实现只扫 `components/help/`，到 v3.14.0 同步才发现从没收过。
- 不收割条文数据集（铁板 12000/邵子 6144 等是引擎数据，随工具输出流动，不进知识库）。

用法：HOROSA_SOURCE_ROOT=/path/to/Horosa-Public uv run python scripts/gen_knowledge_packs.py [--check] [--worktree]
（要 Node 与 `horosa-core-js/node_modules` 里的 esbuild / react：先 `cd horosa-core-js && npm ci`。）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

# Windows 控制台默认 cp1252/cp936：脚本自己 print 的中文会抛 UnicodeEncodeError 并让脚本 exit 1
# （v0.38.0 的 repack 脚本在「打印成功信息」那一步失败过）。统一在入口把两条流改成 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")
from collections.abc import Iterable
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "src" / "horosa_skill" / "knowledge" / "data" / "helpdocs"
HARVESTER = REPO / "scripts" / "harvest_help_books.mjs"
HELP_REL = "Horosa-Web/astrostudyui/src/components/help"
APP_MANIFEST_REL = "Horosa_Desktop_Installer/package.json"
SCHEMA = "horosa.knowledge.helpdoc.v1"
MIN_CHAPTER_CHARS = 20  # 比这还短的章 = 空壳；上游自己的合同（helpBookCoverage.test.js）要求技法章不少于 700 字

# 手册组件 → (domain, 中文标签)。域名不与既有 hover 域（astro/liureng/qimen）冲突：冲突者带 _manual 后缀；其余用
# 技法页自然名。包的 label 取上游书名（book.title），这里的标签只作白名单里的说明。纯 3D/观星操作页信息密度低，仍收。
# 非手册来源、由各自生成器产出的知识包（同 helpdoc.v1 schema）：域名 → 生成脚本。磁盘上的包必须
# 要么在 HELPDOC_DOMAINS 要么在这里（tests/test_knowledge_helpdocs 守），否则是没人认领的孤儿包。
EXTRA_PACK_DOMAINS: dict[str, str] = {
    "bazi_pithy": "scripts/gen_bazi_pithy_pack.py",  # v0.36.0 C2：上游 Java bazipithy.json 21 类口诀
}

HELPDOC_DOMAINS: dict[str, tuple[str, str]] = {
    "AstroHelpDoc": ("astro_manual", "西洋占星 · 操作手册"),
    "BaziHelpDoc": ("bazi", "八字四柱 · 操作手册"),
    "ZiweiHelpDoc": ("ziwei", "紫微斗数 · 操作手册"),
    "DunjiaHelpDoc": ("dunjia", "奇门遁甲 · 操作手册"),
    "LiurengHelpDoc": ("liureng_manual", "大六壬 · 操作手册"),
    "GuazhanHelpDoc": ("guazhan", "六爻卦占 · 操作手册"),
    "CntraditionHelpDoc": ("cntradition", "中式命术合集 · 操作手册"),
    "CnyibuHelpDoc": ("cnyibu", "卜术合集 · 操作手册"),
    "TarotHelpDoc": ("tarot", "塔罗 · 操作手册"),
    "IndiaHelpDoc": ("india", "印度占星 · 操作手册"),
    "DirectionHelpDoc": ("direction", "推运与向运 · 操作手册"),
    "AuxchartHelpDoc": ("auxchart", "派生盘 · 操作手册"),
    "CalendarHelpDoc": ("calendar", "黄历万年历 · 操作手册"),
    "JieqiHelpDoc": ("jieqi", "节气 · 操作手册"),
    "GermanyHelpDoc": ("germany", "汉堡学派量化盘 · 操作手册"),
    "RelativeHelpDoc": ("relative", "合盘 · 操作手册"),
    "ShusuanHelpDoc": ("shusuan", "数算 · 操作手册"),
    "AstrodataHelpDoc": ("astrodata_manual", "名人星盘库 · 操作手册"),
    "AIAnalysisHelpDoc": ("aianalysis", "AI 分析与挂载 · 操作手册"),
    "Astro3DHelpDoc": ("astro3d", "3D 天球 · 操作手册"),
    "PlanetariumHelpDoc": ("planetarium", "观星 · 操作手册"),
    "ZeriHelpDoc": ("zeri", "择日十技法 · 操作手册"),
    "TaiyiHelpDoc": ("taiyi", "太乙神数 · 操作手册"),
    "SanshiHelpDoc": ("sanshi", "三式合一 · 操作手册"),
    "YanqinHelpDoc": ("yanqin", "演禽 · 操作手册"),
    "YizhangjingHelpDoc": ("yizhangjing", "一掌经 · 操作手册"),
    "XuanshiHelpDoc": ("xuanshi", "玄史知识库 · 操作手册"),
    # v3.14.0：命 · 其他页新增的两本（东亚六技法 / 诸方四技法）与把它们和策天飞星、演禽、一掌经合订的那本
    "DongyaHelpDoc": ("dongya", "东亚诸术 · 操作手册"),
    "ZhufangHelpDoc": ("zhufang", "诸方杂术 · 操作手册"),
    "MingOtherHelpDoc": ("mingother", "命 · 其他（策天飞星等）· 操作手册"),
    # 七政四余的手册在 components/guolao/（不在 help/ 目录），只扫目录的旧实现从没收过它；注册表里一直有
    "GuoLaoHelpDoc": ("guolao", "七政四余 · 操作手册"),
}

# 明文排除的手册（政策性排除，不是缺口）——排除项台账见 docs/LESSONS.md「开源栈上不可得的段」。
EXCLUDED_HELPDOCS: dict[str, str] = {
    "FengshuiHelpDoc": "fengshui 是 canvas + 户型图上传 + 交互点位驱动的技法，skill 无法 headless，整技法不上架。",
}


class HarvestError(RuntimeError):
    """收割失败：结构解析不了 / 上游与白名单对不上。一律 FAIL，不产出半份包。"""


def unlisted_helpdocs(present: Iterable[str]) -> list[str]:
    """手册组件里既未收割也未明文排除的——每一个都是「技法可能已上架、口径知识却缺席」。

    `present` 收文件名（`XHelpDoc.js`，带不带目录都行）或组件名（`XHelpDoc`）；别的文件（`helpDocStyle.js`、`HelpBook.js`）不算。"""
    names = {Path(f"{name}").stem for name in present if re.search(r"HelpDoc(\.js)?$", f"{name}")}
    return sorted(names - set(HELPDOC_DOMAINS) - set(EXCLUDED_HELPDOCS))


# 对账口径与 harvest_help_books.mjs 的 NOT_TEXT 相同：只比「字」，空白与排版记号不算
_NOT_TEXT = re.compile(r"[\s#*\-|·:：.\\>]")


def _bare(text: str) -> str:
    return _NOT_TEXT.sub("", text)


def _chapters(book: dict[str, Any]) -> list[dict[str, Any]]:
    return [{**chapter, "group": group} for group in book["groups"] for chapter in group["chapters"]]


def _combined_text(chapters: list[dict[str, Any]]) -> str:
    """上游「一个技法的多章合排成一章」（MingOtherHelpDoc.combined）的文字：首章正文，其后每章先章名再正文。"""
    parts = [chapters[0]["text"]]
    for chapter in chapters[1:]:
        parts.append(f"# {chapter['label']}\n\n{chapter['text']}")
    return "\n\n".join(parts)


def build_packs(harvest: dict[str, Any], *, app_version: str, sha: str, committed_at: str) -> dict[str, dict[str, Any]]:
    """harvest_help_books.mjs 的输出 → {domain: 包}。纯函数（不碰磁盘 / git），测试直接喂合成的 harvest。"""
    if harvest.get("schema") != "horosa.help_books.v1":
        raise HarvestError(f"unexpected harvest schema: {harvest.get('schema')!r}")
    books = list(harvest.get("books") or [])
    unlisted = unlisted_helpdocs(book["component"] for book in books)
    foreign = sorted({book["component"] for book in books} - set(HELPDOC_DOMAINS) - set(EXCLUDED_HELPDOCS) - set(unlisted))
    if unlisted or foreign:
        raise HarvestError(
            "upstream manual(s) neither harvested nor explicitly excluded: "
            f"{', '.join(unlisted + foreign)} — add each to HELPDOC_DOMAINS (technique shipped → its manual ships) or to "
            "EXCLUDED_HELPDOCS with the policy reason."
        )
    by_component: dict[str, dict[str, Any]] = {}
    for book in books:
        if book["component"] in by_component:
            raise HarvestError(f"{book['component']} is registered under two help tabs ({by_component[book['component']]['tab']}, {book['tab']})")
        by_component[book["component"]] = book
    missing = sorted(set(HELPDOC_DOMAINS) - set(by_component))
    if missing:
        raise HarvestError(f"whitelisted manual(s) missing from the upstream help registry: {', '.join(missing)}")

    harvested = {HELPDOC_DOMAINS[name][0]: book for name, book in by_component.items() if name in HELPDOC_DOMAINS}
    packs: dict[str, dict[str, Any]] = {}
    for domain in sorted(harvested):
        book = harvested[domain]
        entries: list[dict[str, Any]] = []
        includes: list[dict[str, Any]] = []
        for chapter in _chapters(book):
            where = f"{domain}/{chapter['key']}"
            if len(_bare(chapter["text"])) < MIN_CHAPTER_CHARS:
                raise HarvestError(f"{where}: chapter text is {len(_bare(chapter['text']))} characters — an empty shell, not a manual chapter")
            head = {
                "key": chapter["key"],
                "label": chapter["label"],
                "group": chapter["group"]["label"],
                **({"aliases": chapter["aliases"]} if chapter.get("aliases") else {}),
            }
            ref = _borrowed_from(chapter, book, domain, harvested)
            if ref is not None:
                includes.append({**head, "ref": ref})
                continue
            entries.append({**head, "text": chapter["text"], "source": {"file": f"components/{chapter['file'].removeprefix('components/')}", "tab": chapter["key"], "book": book["tab"]}})
        if not entries:
            raise HarvestError(f"{domain}: every chapter of this book is borrowed from another book — nothing of its own to ship")
        packs[domain] = {
            "schema": SCHEMA,
            "domain": domain,
            "label": book["title"],
            "source": {
                "file": book["file"],
                "files": book["files"],
                "help_tab": book["tab"],
                "upstream_source_marker": "xingque_help_docs",
                "upstream_app_version": app_version,
                "upstream_git_sha": sha,
            },
            "generated_at": committed_at,  # 取上游 commit 时间 → 同 commit 重跑幂等
            "groups": [
                {"key": group["key"], "label": group["label"], **({"hint": group["hint"]} if group.get("hint") else {}),
                 "chapters": [chapter["key"] for chapter in group["chapters"]]}
                for group in book["groups"]
            ],
            "categories": [{"name": "手册", "entries": entries}],
            **({"includes": includes} if includes else {}),
        }
    return packs


def _borrowed_from(chapter: dict[str, Any], book: dict[str, Any], domain: str, harvested: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """这一章是不是别册的章。本家 = 被本册 import 的那一册（合订本 import 各分册，反过来不成立）。两种合订法，都按正文判、不按名字猜：

    - 原样搬来（键可以改过：东亚的 `tibetan` 在合订本里叫 `dongya.tibetan`）：本家里有正文逐字相同的一章 → {domain, key}；
    - 整册合排成一章（上游 `combined(chapters)`）：正文 = 本家全部章按「首章正文 + 其后每章 章名 + 正文」连起来 → {domain, keys}。
    对不上的就是本册自己的章，正文照收。"""
    bare = _bare(chapter["text"])
    for other_domain in sorted(harvested):
        other = harvested[other_domain]
        if other_domain == domain or other["file"] not in book["files"] or book["file"] in other["files"]:
            continue
        chapters = _chapters(other)
        same = [item for item in chapters if item["text"] == chapter["text"]]
        if len(same) == 1:
            return {"domain": other_domain, "key": same[0]["key"]}
        if len(chapters) > 1 and _bare(_combined_text(chapters)) == bare:
            return {"domain": other_domain, "keys": [item["key"] for item in chapters]}
    return None


def render_pack(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=1) + "\n"


def _git(upstream: Path, *args: str) -> str | None:
    """stdout on success, None on any failure（区分「空输出」与「不是 git 树」）。"""
    try:
        out = subprocess.run(["git", "-C", str(upstream), *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout if out.returncode == 0 else None


def _help_files(upstream: Path, worktree: bool) -> list[str] | None:
    """`components/help/` 下的文件名：注册表之外再扫一遍目录，写了手册却忘了登记的那一册也要报出来。"""
    if worktree:
        help_dir = upstream / HELP_REL
        return sorted(p.name for p in help_dir.glob("*.js")) if help_dir.is_dir() else None
    listing = _git(upstream, "ls-tree", "--name-only", "HEAD", f"{HELP_REL}/")
    if listing is None:
        return None
    return sorted(Path(line).name for line in listing.splitlines() if line.strip())


def harvest(upstream: Path, worktree: bool) -> dict[str, Any]:
    """跑 harvest_help_books.mjs。它自己逐章对账，对不上就非 0 退出；这里把它的报错原样带出来。"""
    node = shutil.which("node")
    if node is None:
        raise HarvestError("node is not on PATH — the manuals are harvested by running the upstream help modules (scripts/harvest_help_books.mjs)")
    if not (REPO / "horosa-core-js" / "node_modules" / "esbuild").is_dir():
        raise HarvestError("horosa-core-js/node_modules has no esbuild — run `npm ci` in horosa-core-js first")
    command = [node, str(HARVESTER), "--source-root", str(upstream), *(["--worktree"] if worktree else [])]
    try:
        done = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        raise HarvestError(f"could not run the help harvester: {exc}") from exc
    if done.returncode != 0:
        raise HarvestError((done.stderr or done.stdout or "the help harvester failed without a message").strip())
    try:
        return json.loads(done.stdout)
    except json.JSONDecodeError as exc:
        raise HarvestError(f"the help harvester printed something that is not JSON: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worktree", action="store_true", help="read the working-tree files instead of HEAD blobs (non-git snapshots only)")
    parser.add_argument("--check", action="store_true", help="compare with the committed packs instead of writing (red when upstream HEAD or this script moved)")
    args = parser.parse_args()

    root = os.environ.get("HOROSA_SOURCE_ROOT")
    upstream = Path(root).expanduser().resolve() if root else None
    if upstream is None or not (upstream / "Horosa-Web").is_dir():
        print("gen-knowledge-packs: FAIL — HOROSA_SOURCE_ROOT must point at a Horosa-Public checkout.", file=sys.stderr)
        return 2
    present = _help_files(upstream, args.worktree)
    if not present:
        mode = "the working tree" if args.worktree else "HEAD (not a git checkout? pass --worktree for a snapshot directory)"
        print(f"gen-knowledge-packs: FAIL — no help components found in {mode}: {HELP_REL}", file=sys.stderr)
        return 2
    sha = (_git(upstream, "rev-parse", "HEAD") or "").strip()[:12]
    committed_at = (_git(upstream, "log", "-1", "--format=%cI") or "").strip()
    dirty = [line[3:] for line in (_git(upstream, "status", "--porcelain", "--", HELP_REL) or "").splitlines() if line.strip()]
    if dirty and not args.worktree:
        print(
            f"gen-knowledge-packs: notice — {len(dirty)} manual(s) modified but uncommitted upstream; harvesting HEAD, "
            f"those edits are NOT included: {', '.join(Path(d).name for d in dirty)}"
        )
    # 版本号与正文同源：HEAD 的 package.json（工作区那份可能已经是下一个版本的 WIP）
    manifest_text = (upstream / APP_MANIFEST_REL).read_text(encoding="utf-8") if args.worktree and (upstream / APP_MANIFEST_REL).is_file() \
        else _git(upstream, "show", f"HEAD:{APP_MANIFEST_REL}")
    try:
        app_version = str(json.loads(manifest_text or "{}").get("version", ""))
    except json.JSONDecodeError:
        app_version = ""

    try:
        harvested = harvest(upstream, args.worktree)
        unregistered = sorted(set(unlisted_helpdocs(present)) | (
            {Path(name).stem for name in present if name.endswith("HelpDoc.js")} - {book["component"] for book in harvested.get("books") or []}))
        if unregistered:
            raise HarvestError(
                f"manual file(s) under {HELP_REL} that are neither in the upstream help registry nor handled here: {', '.join(unregistered)}")
        packs = build_packs(harvested, app_version=app_version, sha=sha, committed_at=committed_at)
    except HarvestError as exc:
        print(f"gen-knowledge-packs: FAIL — {exc}", file=sys.stderr)
        return 1

    total_entries = sum(len(pack["categories"][0]["entries"]) for pack in packs.values())
    total_includes = sum(len(pack.get("includes") or []) for pack in packs.values())
    summary = f"{len(packs)} domains / {total_entries} chapters + {total_includes} borrowed (upstream {app_version} @ {sha})"
    unmarked = harvested.get("unmarked_function_components") or {}
    if unmarked:
        print("gen-knowledge-packs: notice — function component(s) the upstream AI help text skips (not marked __helpPure) but the help "
              f"dialog renders; harvested as displayed: {', '.join(sorted(unmarked))}")
    stale_files = sorted(path.name for path in OUT_DIR.glob("*.json") if path.stem not in packs and path.stem not in EXTRA_PACK_DOMAINS)
    if args.check:
        stale = sorted(domain for domain, pack in packs.items()
                       if not (OUT_DIR / f"{domain}.json").is_file() or (OUT_DIR / f"{domain}.json").read_text(encoding="utf-8") != render_pack(pack))
        if stale or stale_files:
            print(f"gen-knowledge-packs: FAIL — stale vs upstream HEAD: {', '.join(stale) or '—'}; orphan pack files: {', '.join(stale_files) or '—'} "
                  "— rerun without --check", file=sys.stderr)
            return 1
        print(f"gen-knowledge-packs: up to date — {summary}")
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for domain, pack in packs.items():
        (OUT_DIR / f"{domain}.json").write_text(render_pack(pack), encoding="utf-8", newline="\n")
    for name in stale_files:  # 白名单里已经没有的包：留在磁盘上就是没人认领的孤儿
        (OUT_DIR / name).unlink()
        print(f"gen-knowledge-packs: removed orphan pack {name}")
    print(f"gen-knowledge-packs: wrote {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
