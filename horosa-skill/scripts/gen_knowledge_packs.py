#!/usr/bin/env python
"""收割上游 HelpDoc 面板 → 知识包（B1：grounded interpretation 的地基）。

上游 `components/help/*.js` 是 30+ 份**方法论手册**（每个设置项的取值与差别、流派分歧、算法与
口径），一直只活在桌面端帮助页里——AI 客户端解读时最需要的正是这些口径知识。本脚本在维护机上
读 `$HOROSA_SOURCE_ROOT`（shaozi 条文生成器同模式），把 JSX 手册转成结构化知识包入仓：

  src/horosa_skill/knowledge/data/helpdocs/<domain>.json
  { schema, domain, label, source:{file, upstream_app_version, upstream_git_sha}, generated_at,
    categories:[{name:"手册", entries:[{key:<tab 名>, text:<markdown>, source:{file, tab}}]}] }

纪律：
- **逐条带出处**（file + tab + 上游版本/commit）——SKILL.md 策略「引教义必带出处」的机器前提。
- 抽取是**结构保持**的降级（TabPane→条目、card 标题→###、h→##、li→列表行、kv→`k：v`），
  不做任何改写；正文即上游文本。
- 幂等：同一上游 commit 重跑输出逐字节一致（generated_at 取上游 commit 时间，不取 now）。
- 不收割条文数据集（铁板 12000/邵子 6144 等是引擎数据，随工具输出流动，不进知识库）。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "src" / "horosa_skill" / "knowledge" / "data" / "helpdocs"

# HelpDoc 组件 → (domain, 中文标签)。域名不与既有 hover 域（astro/liureng/qimen）冲突：
# 冲突者带 _manual 后缀；其余用技法页自然名。纯 3D/观星操作页信息密度低，仍收（体量小）。
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
}

_TABPANE = re.compile(r'<TabPane\s+tab="([^"]+)"\s+key="[^"]+">')
_TITLE = re.compile(r"<div style=\{title\}>([^<]+)</div>")


def _jsx_to_markdown(fragment: str) -> str:
    text = fragment
    # 结构标记（先做，标签还在时才知道语义）
    text = re.sub(r"\{kv\(\s*'((?:[^'\\]|\\.)*)'\s*,\s*'((?:[^'\\]|\\.)*)'\s*\)\}", r"\n\1：\2", text)
    text = re.sub(r'\{kv\(\s*"((?:[^"\\]|\\.)*)"\s*,\s*"((?:[^"\\]|\\.)*)"\s*\)\}', r"\n\1：\2", text)
    text = re.sub(r"<div style=\{ct\}>", "\n\n### ", text)
    text = re.sub(r"<div style=\{h\}>", "\n\n## ", text)
    text = re.sub(r"<li[^>]*>", "\n- ", text)
    text = re.sub(r"<p[^>]*>", "\n\n", text)
    text = re.sub(r"<(td|th)[^>]*>", " | ", text)
    text = re.sub(r"<tr[^>]*>", "\n", text)
    # 行内强调保内容
    text = re.sub(r"</?b>", "**", text)
    text = re.sub(r"</?i>", "", text)
    # 去所有剩余标签与 JSX 表达式噪音
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("{' '}", " ")
    text = re.sub(r"\{'((?:[^'\\]|\\.)*)'\}", r"\1", text)
    text = re.sub(r'\{"((?:[^"\\]|\\.)*)"\}', r"\1", text)
    text = re.sub(r"\{[A-Za-z_][^{}]*\}", "", text)  # 残余 JS 表达式（样式/变量）整个丢弃
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    # 收拾空白
    lines = [line.rstrip() for line in text.splitlines()]
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if out and out[-1] != "":
                out.append("")
            continue
        out.append(stripped)
    return "\n".join(out).strip()


_RENDER_METHOD = re.compile(r"\n\trender([A-Z]\w*)\(\)\{")


def _split_tabs(source: str) -> list[tuple[str, str]]:
    matches = list(_TABPANE.finditer(source))
    tabs: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(source)
        tabs.append((m.group(1), source[m.end():end]))
    if tabs:
        return tabs
    # 无 TabPane 的手册（Tarot/Cnyibu/Auxchart 用平铺 + render<Name>() 分节）：按 render 方法切条目，
    # 条目键取方法名（renderTarot → Tarot）；只有 render() 主方法时整册一条（键=总览）。
    methods = list(_RENDER_METHOD.finditer(source))
    if methods:
        for i, m in enumerate(methods):
            end = methods[i + 1].start() if i + 1 < len(methods) else len(source)
            tabs.append((m.group(1), source[m.end():end]))
    if not tabs:
        tabs.append(("总览", source))
    return tabs


def _git(upstream: Path, *args: str) -> str:
    try:
        out = subprocess.run(["git", "-C", str(upstream), *args], capture_output=True, text=True, timeout=30)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def main() -> int:
    root = os.environ.get("HOROSA_SOURCE_ROOT")
    upstream = Path(root).expanduser().resolve() if root else None
    if upstream is None or not (upstream / "Horosa-Web").is_dir():
        print("gen-knowledge-packs: FAIL — HOROSA_SOURCE_ROOT must point at a Horosa-Public checkout.", file=sys.stderr)
        return 2
    help_dir = upstream / "Horosa-Web/astrostudyui/src/components/help"
    sha = _git(upstream, "rev-parse", "HEAD")[:12]
    committed_at = _git(upstream, "log", "-1", "--format=%cI")
    app_version = ""
    manifest = upstream / "Horosa_Desktop_Installer/package.json"
    if manifest.is_file():
        try:
            app_version = str(json.loads(manifest.read_text(encoding="utf-8")).get("version", ""))
        except (json.JSONDecodeError, OSError):
            app_version = ""

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written, skipped, total_entries = 0, [], 0
    for component, (domain, label) in sorted(HELPDOC_DOMAINS.items()):
        path = help_dir / f"{component}.js"
        if not path.is_file():
            skipped.append(component)
            continue
        source = path.read_text(encoding="utf-8")
        title_match = _TITLE.search(source)
        entries = []
        for tab_name, fragment in _split_tabs(source):
            text = _jsx_to_markdown(fragment)
            if len(text) < 40:  # 空 tab / 纯组件引用 tab 不入库
                continue
            entries.append({
                "key": tab_name,
                "text": text,
                "source": {"file": f"components/help/{component}.js", "tab": tab_name},
            })
        if not entries:
            skipped.append(component)
            continue
        payload = {
            "schema": "horosa.knowledge.helpdoc.v1",
            "domain": domain,
            "label": (title_match.group(1).strip() if title_match else label),
            "source": {
                "file": f"components/help/{component}.js",
                "upstream_source_marker": "xingque_help_docs",
                "upstream_app_version": app_version,
                "upstream_git_sha": sha,
            },
            "generated_at": committed_at,  # 取上游 commit 时间 → 同 commit 重跑幂等
            "categories": [{"name": "手册", "entries": entries}],
        }
        (OUT_DIR / f"{domain}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        written += 1
        total_entries += len(entries)
    print(f"gen-knowledge-packs: wrote {written} domains / {total_entries} entries (upstream {app_version} @ {sha})")
    if skipped:
        print(f"  skipped (missing/empty): {', '.join(skipped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
