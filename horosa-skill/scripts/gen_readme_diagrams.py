#!/usr/bin/env python3
"""Render the README diagrams (`docs/assets/readme/*.svg`) from the registry, so the numbers they print never drift.

Five figures × two languages × two themes:

    hero · architecture · flow · techniques · repo   ×   zh / en   ×   light / dark

The READMEs show them through `<picture>` (GitHub swaps the dark file in when the reader's theme is dark).
Every number drawn — technique count, MCP surface size, client count, knowledge domains, per-family counts — is
read here from the same sources `verify_docs_sync.py` locks the prose to; the per-family counts come from the zh
README's own technique tables (their headers are already locked to their rows by `check_group_headers`).

    uv run python scripts/gen_readme_diagrams.py           # (re)write the SVGs
    uv run python scripts/gen_readme_diagrams.py --check   # exit 1 when a committed SVG differs from the render

The SVGs are build output: edit this file, never the SVGs. `verify_docs_sync.check_readme_diagrams_generated`
fails CI when they drift (e.g. a technique was added and nobody re-rendered).
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "horosa-skill"
OUT_REL = "docs/assets/readme"
OUT = ROOT / OUT_REL

FIGURES = ("hero", "architecture", "flow", "techniques", "repo")
LANGS = ("zh", "en")
THEME_NAMES = ("light", "dark")

SANS = (
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', "
    "'Noto Sans CJK SC', 'Noto Sans SC', Helvetica, Arial, sans-serif"
)
MONO = "ui-monospace, 'SF Mono', SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace"
SERIF = "'Songti SC', STSong, 'Noto Serif CJK SC', 'Noto Serif SC', 'Source Han Serif SC', SimSun, serif"

THEMES: dict[str, dict[str, str]] = {
    "dark": {
        "bg0": "#0B1020", "bg1": "#101830", "card": "#131C33", "card2": "#0F172B", "line": "#26324F", "line2": "#1C2642",
        "text": "#E9EDF5", "sub": "#A7B1C7", "muted": "#717E99", "on": "#0B1020",
        "gold": "#E9BC62", "gold2": "#F7DC9C", "teal": "#4AD5C5", "violet": "#A597FF", "rose": "#F38BA3",
        "blue": "#73AAFF", "green": "#82D69E", "orange": "#F3A75C", "slate": "#9AA8BD",
        "glow": "0.55", "star": "#FFFFFF", "coretext": "#F7DC9C",
    },
    "light": {
        "bg0": "#FFFFFF", "bg1": "#F7F4EC", "card": "#FFFFFF", "card2": "#FBF9F4", "line": "#E2DDCF", "line2": "#EDE9DF",
        "text": "#141A2A", "sub": "#4A546A", "muted": "#7C859A", "on": "#FFFFFF",
        "gold": "#A6711A", "gold2": "#C8912E", "teal": "#0D8478", "violet": "#6A4FD3", "rose": "#C13E65",
        "blue": "#2D6ACF", "green": "#2D8A56", "orange": "#C2681B", "slate": "#5F6E84",
        "glow": "0.30", "star": "#A6711A", "coretext": "#7A4E0C",
    },
}

# key, probe tool (locates the family's table in README.md), zh name, en name, zh examples, en examples, accent
FAMILIES: tuple[tuple[str, str, str, str, str, str, str], ...] = (
    ("natal", "chart", "西洋 · 本命与派生盘", "Western · natal & derived",
     "标准星盘 · 印度盘 · 七政四余 · 合盘 · 汉堡学派", "natal · Vedic · Qi Zheng · synastry · Uranian", "gold"),
    ("predict", "solarreturn", "西洋 · 推运 / 返照 / 时运", "Western · predictive",
     "主限 · 黄道释放 · 法达 · 返照 · 占星地图", "directions · ZR · firdaria · returns · ACG", "orange"),
    ("divination", "horary", "西洋占卜 · 卜卦 / 择日", "Horary & elections",
     "卜卦 · 择日 · 天星 / 奇门 / 黄历 / 八字等择时", "horary · electional · Qi Men / almanac / BaZi searches", "rose"),
    ("sanshi", "qimen", "中文术数主干 · 三式合一", "Chinese core · Three Styles",
     "八字 · 紫微 · 大六壬 · 奇门 · 太乙 · 金口诀", "BaZi · Zi Wei · Liu Ren · Qi Men · Tai Yi · Jin Kou", "violet"),
    ("local", "sixyao", "本地术数 · 数算 · 占卜", "Numerology & divination",
     "六爻 · 河洛理数 · 塔罗 · 天文地占 · 小六壬", "Liu Yao · He Luo · tarot · geomancy · Xiao Liu Ren", "blue"),
    ("shenshu", "tieban", "神数 · 全 14 路", "Shen Shu · all 14 systems",
     "铁板 · 邵子 · 皇极经世 · 太玄 · 演禽", "Tie Ban · Shao Zi · Huang Ji · Tai Xuan · Yan Qin", "teal"),
    ("calendar", "huangli", "节气 / 农历 / 黄历", "Calendar & almanac",
     "节气 · 农历换算 · 老黄历 · 通书", "solar terms · lunar date · almanac · Tong Shu", "green"),
    ("protocol", "knowledge_read", "协议 / 知识", "Protocol & knowledge",
     "卦义 · 导出注册表 · 知识库", "hexagram texts · export registry · knowledge", "slate"),
)


# --------------------------------------------------------------------------- facts


def readme_family_counts(tool_ids: set[str]) -> dict[str, int]:
    """Count the technique IDs in each `<summary>` table of README.md; every registry tool must land in exactly one family."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    groups: list[set[str]] = []
    current: set[str] | None = None
    for line in text.splitlines():
        if line.startswith("<summary>"):
            current = set()
            groups.append(current)
        elif line.startswith("</details>"):
            current = None
        elif current is not None and line.startswith("|"):
            current.update(t for t in re.findall(r"`([^`]+)`", line) if t in tool_ids)
    counts: dict[str, int] = {}
    covered: set[str] = set()
    for key, probe, *_ in FAMILIES:
        hits = [g for g in groups if probe in g]
        if len(hits) != 1:
            raise SystemExit(f"gen_readme_diagrams: README.md must have exactly one technique table containing `{probe}` (found {len(hits)})")
        counts[key] = len(hits[0])
        covered |= hits[0]
    if covered != tool_ids or sum(counts.values()) != len(tool_ids):
        missing = sorted(tool_ids - covered)
        raise SystemExit(
            "gen_readme_diagrams: README.md technique tables do not partition the registry "
            f"(sum {sum(counts.values())} vs {len(tool_ids)}; missing: {', '.join(missing) or '—'})"
        )
    return counts


def collect_facts() -> dict:
    sys.path.insert(0, str(PKG / "src"))
    from horosa_skill.client_config.locations import _CLIENT_NAMES
    from horosa_skill.engine.registry import TOOL_DEFINITIONS
    from horosa_skill.knowledge.store import load_knowledge_bundles

    budget = json.loads((PKG / "contracts" / "mcp_list_budget.json").read_text(encoding="utf-8"))
    tool_ids = set(TOOL_DEFINITIONS)
    return {
        "tools": len(tool_ids),
        "full": int(budget["full_tools"]),
        "compact": int(budget["compact_tools"]),
        "clients": len(_CLIENT_NAMES),
        "domains": len(load_knowledge_bundles()),
        "families": readme_family_counts(tool_ids),
    }


# --------------------------------------------------------------------------- svg primitives


def n(v: float) -> str:
    """Stable number formatting: one decimal, no trailing `.0`."""
    s = f"{v:.1f}"
    return s[:-2] if s.endswith(".0") else s


def tw(s: str, size: float, mono: bool = False) -> float:
    """Rough rendered width — CJK full-width, Latin by class. Good enough to size chips with padding to spare."""
    w = 0.0
    for ch in s:
        o = ord(ch)
        if o >= 0x2E80 or ch in "，。：；（）「」、":
            w += 1.0
        elif mono:
            w += 0.61
        elif ch in "il.,:;'|!·()[]/":
            w += 0.32
        elif ch == " ":
            w += 0.28
        elif ch.isupper() or ch in "mwMW":
            w += 0.68
        else:
            w += 0.56
    return w * size


class Svg:
    def __init__(self, w: int, h: int, t: dict[str, str], title: str, desc: str) -> None:
        self.w, self.h, self.t = w, h, t
        self.title, self.desc = title, desc
        self.defs: list[str] = []
        self.body: list[str] = []

    def add(self, s: str) -> None:
        self.body.append(s)

    def text(self, x: float, y: float, s: str, *, size: float, fill: str, weight: int = 400, anchor: str = "start",
             family: str = "sans", spacing: float = 0, opacity: float = 1) -> None:
        attrs = [f'x="{n(x)}"', f'y="{n(y)}"', f'font-size="{n(size)}"', f'fill="{fill}"']
        if weight != 400:
            attrs.append(f'font-weight="{weight}"')
        if anchor != "start":
            attrs.append(f'text-anchor="{anchor}"')
        if family != "sans":
            attrs.append(f'class="{family}"')
        if spacing:
            attrs.append(f'letter-spacing="{n(spacing)}"')
        if opacity != 1:
            attrs.append(f'opacity="{n(opacity)}"' if opacity >= 0.1 else f'opacity="{opacity:.2f}"')
        self.add(f"<text {' '.join(attrs)}>{escape(s)}</text>")

    def rect(self, x: float, y: float, w: float, h: float, *, rx: float = 0, fill: str = "none", stroke: str = "none",
             sw: float = 1, opacity: float = 1, extra: str = "") -> None:
        attrs = f'x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}"'
        if rx:
            attrs += f' rx="{n(rx)}"'
        attrs += f' fill="{fill}"'
        if stroke != "none":
            attrs += f' stroke="{stroke}" stroke-width="{n(sw)}"'
        if opacity != 1:
            attrs += f' opacity="{opacity:.2f}"'
        self.add(f"<rect {attrs}{extra}/>")

    def line(self, x1: float, y1: float, x2: float, y2: float, *, stroke: str, sw: float = 1, opacity: float = 1,
             extra: str = "") -> None:
        op = f' opacity="{opacity:.2f}"' if opacity != 1 else ""
        self.add(f'<line x1="{n(x1)}" y1="{n(y1)}" x2="{n(x2)}" y2="{n(y2)}" stroke="{stroke}" stroke-width="{n(sw)}"{op}{extra}/>')

    def circle(self, cx: float, cy: float, r: float, *, fill: str = "none", stroke: str = "none", sw: float = 1,
               opacity: float = 1, extra: str = "") -> None:
        attrs = f'cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" fill="{fill}"'
        if stroke != "none":
            attrs += f' stroke="{stroke}" stroke-width="{n(sw)}"'
        if opacity != 1:
            attrs += f' opacity="{opacity:.2f}"'
        self.add(f"<circle {attrs}{extra}/>")

    def render(self) -> str:
        t = self.t
        head = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" '
            f'role="img" aria-labelledby="title desc">\n'
            f"<title id=\"title\">{escape(self.title)}</title>\n<desc id=\"desc\">{escape(self.desc)}</desc>\n"
            f"<!-- Generated by horosa-skill/scripts/gen_readme_diagrams.py — do not edit by hand. -->\n"
            f"<style>text{{font-family:{SANS}}}.mono{{font-family:{MONO}}}.serif{{font-family:{SERIF}}}</style>\n"
        )
        defs = (
            "<defs>\n"
            f'<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{t["bg0"]}"/>'
            f'<stop offset="1" stop-color="{t["bg1"]}"/></linearGradient>\n'
            f'<marker id="arrow" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{t["muted"]}"/></marker>\n'
            + "".join(d + "\n" for d in self.defs)
            + "</defs>\n"
        )
        frame = f'<rect x="0.5" y="0.5" width="{self.w - 1}" height="{self.h - 1}" rx="24" fill="url(#bg)" stroke="{t["line"]}"/>\n'
        return head + defs + frame + "\n".join(self.body) + "\n</svg>\n"


def chip(s: Svg, x: float, y: float, label: str, *, size: float = 14.5, h: float = 34, fill: str, stroke: str,
         color: str, weight: int = 500, mono: bool = False, pad: float = 16) -> float:
    """Draw a pill; return its width."""
    w = tw(label, size, mono) + 2 * pad
    s.rect(x, y, w, h, rx=h / 2, fill=fill, stroke=stroke)
    s.text(x + w / 2, y + h / 2 + size * 0.36, label, size=size, fill=color, weight=weight, anchor="middle",
           family="mono" if mono else "sans")
    return w


def header(s: Svg, eyebrow: str, title: str, *, x: float = 48, y: float = 56) -> None:
    t = s.t
    s.text(x, y, eyebrow, size=13, fill=t["gold"], weight=600, family="mono", spacing=2.6)
    s.text(x, y + 36, title, size=26, fill=t["text"], weight=700)


def stars(s: Svg, count: int, box: tuple[float, float, float, float], seed: int, *, max_op: float = 0.7) -> None:
    """Deterministic star field (LCG) — the render must be byte-stable for --check."""
    x0, y0, x1, y1 = box
    state = seed
    out: list[str] = []
    for _ in range(count):
        vals = []
        for _ in range(4):
            state = (1103515245 * state + 12345) % (2**31)
            vals.append(state / 2**31)
        x = x0 + vals[0] * (x1 - x0)
        y = y0 + vals[1] * (y1 - y0)
        r = 0.5 + vals[2] * 1.2
        op = 0.12 + vals[3] * (max_op - 0.12)
        out.append(f'<circle cx="{n(x)}" cy="{n(y)}" r="{n(r)}" opacity="{op:.2f}"/>')
    s.add(f'<g fill="{s.t["star"]}">' + "".join(out) + "</g>")


def polar(cx: float, cy: float, r: float, deg: float) -> tuple[float, float]:
    """deg measured clockwise from 12 o'clock."""
    a = math.radians(deg - 90)
    return cx + r * math.cos(a), cy + r * math.sin(a)


# --------------------------------------------------------------------------- figure: hero

BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
# Early-Heaven (先天) order clockwise from the top; bits bottom → top, 1 = yang (solid).
TRIGRAMS = ((1, 1, 1), (0, 1, 1), (0, 1, 0), (0, 0, 1), (0, 0, 0), (1, 0, 0), (1, 0, 1), (1, 1, 0))


def astrolabe(s: Svg, cx: float, cy: float) -> None:
    t = s.t
    s.circle(cx, cy, 250, fill="url(#glowA)")
    s.circle(cx, cy, 182, stroke=t["line"], sw=1)
    s.circle(cx, cy, 172, stroke=t["gold"], sw=1.3, opacity=0.6)
    ticks = []
    for i in range(144):
        deg = i * 2.5
        length = 15 if i % 12 == 0 else 8 if i % 4 == 0 else 4
        x1, y1 = polar(cx, cy, 172, deg)
        x2, y2 = polar(cx, cy, 172 - length, deg)
        ticks.append(f"M{n(x1)} {n(y1)}L{n(x2)} {n(y2)}")
    s.add(f'<path d="{"".join(ticks)}" stroke="{t["gold"]}" stroke-width="1" opacity="0.55"/>')
    s.circle(cx, cy, 152, stroke=t["gold"], sw=1, opacity=0.35)
    for i, ch in enumerate(BRANCHES):
        x, y = polar(cx, cy, 136, i * 30)
        s.text(x, y + 6, ch, size=17, fill=t["gold2"], anchor="middle", family="serif", opacity=0.9)
    s.circle(cx, cy, 119, stroke=t["line"], sw=1)
    dots = []
    for i in range(28):
        x, y = polar(cx, cy, 107, i * 360 / 28 + 360 / 56)
        big = i % 7 == 0
        dots.append(f'<circle cx="{n(x)}" cy="{n(y)}" r="{2.6 if big else 1.6}"/>')
    s.add(f'<g fill="{t["teal"]}" opacity="0.75">' + "".join(dots) + "</g>")
    s.circle(cx, cy, 95, stroke=t["gold"], sw=1, opacity=0.35, extra=' stroke-dasharray="2 6"')
    bars = []
    for i, tri in enumerate(TRIGRAMS):
        deg = i * 45
        for k, yang in enumerate(tri):
            y = -(66 + k * 6.6)
            if yang:
                bars.append(f'<rect x="-11" y="{n(y)}" width="22" height="3.4" rx="1"/>')
            else:
                bars.append(f'<rect x="-11" y="{n(y)}" width="8.6" height="3.4" rx="1"/><rect x="2.4" y="{n(y)}" width="8.6" height="3.4" rx="1"/>')
        s.add(f'<g transform="translate({n(cx)} {n(cy)}) rotate({deg})" fill="{t["gold"]}" opacity="0.85">' + "".join(bars) + "</g>")
        bars = []
    # orbit + planets
    s.add(f'<g transform="translate({n(cx)} {n(cy)}) rotate(-18)">'
          f'<ellipse rx="226" ry="70" fill="none" stroke="{t["teal"]}" stroke-width="1" opacity="0.4" stroke-dasharray="3 7"/>'
          f'<circle cx="{n(226 * math.cos(math.radians(205)))}" cy="{n(70 * math.sin(math.radians(205)))}" r="6" fill="{t["gold"]}"/>'
          f'<circle cx="{n(226 * math.cos(math.radians(330)))}" cy="{n(70 * math.sin(math.radians(330)))}" r="4" fill="{t["violet"]}"/>'
          f'<circle cx="{n(226 * math.cos(math.radians(70)))}" cy="{n(70 * math.sin(math.radians(70)))}" r="3.4" fill="{t["teal"]}"/>'
          "</g>")
    s.circle(cx, cy, 48, fill="url(#core)", stroke=t["gold"], sw=1.5)
    s.text(cx, cy + 9, "星阙", size=26, fill=t["coretext"], weight=600, anchor="middle", family="serif")


def fig_hero(t: dict[str, str], lang: str, f: dict) -> Svg:
    zh = lang == "zh"
    title = f"Horosa Skill — 把星阙 {f['tools']} 个术数 / 占星技法做成任何 AI 都能本地调用的 MCP server 与 CLI" if zh else \
        f"Horosa Skill — {f['tools']} real astrology & metaphysics techniques, callable by any AI on your own machine"
    s = Svg(1280, 440, t, title, "Banner: an astrolabe with the twelve earthly branches and the eight trigrams, next to the project name and headline numbers.")
    s.defs += [
        f'<radialGradient id="glowA" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="{t["violet"]}" stop-opacity="{t["glow"]}"/>'
        f'<stop offset="1" stop-color="{t["violet"]}" stop-opacity="0"/></radialGradient>',
        f'<radialGradient id="glowB" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="{t["gold"]}" stop-opacity="{t["glow"]}"/>'
        f'<stop offset="1" stop-color="{t["gold"]}" stop-opacity="0"/></radialGradient>',
        f'<radialGradient id="core" cx="0.4" cy="0.35" r="0.75"><stop offset="0" stop-color="{t["violet"]}" stop-opacity="0.55"/>'
        f'<stop offset="1" stop-color="{t["bg0"]}" stop-opacity="0.95"/></radialGradient>',
        f'<linearGradient id="ink" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{t["gold2"]}"/><stop offset="1" stop-color="{t["gold"]}"/></linearGradient>',
    ]
    s.circle(1180, 40, 300, fill="url(#glowB)", opacity=0.8)
    stars(s, 70, (24, 24, 1256, 416), seed=7)
    astrolabe(s, 300, 220)

    x0 = 580
    s.text(x0, 104, "HOROSA · 星阙   ·   LOCAL-FIRST MCP & CLI", size=14, fill=t["gold"], weight=600, family="mono", spacing=3)
    s.add(f'<text x="{x0 - 4}" y="184" font-size="78" font-weight="800" fill="{t["text"]}" letter-spacing="-1.5">Horosa '
          f'<tspan fill="url(#ink)">Skill</tspan></text>')
    if zh:
        s.text(x0, 234, f"把星阙 {f['tools']} 个术数 / 占星技法，", size=27, fill=t["text"], weight=600)
        s.text(x0, 272, "做成任何 AI 都能在本机调用的 MCP server 与 CLI。", size=21, fill=t["sub"])
        stats = (
            (str(f["tools"]), "个真实技法", t["gold"]),
            (str(f["full"]), "MCP 工具（全量面）", t["teal"]),
            (str(f["clients"]), "客户端一条命令接入", t["violet"]),
            ("100%", "本机计算 · 可断网", t["rose"]),
        )
    else:
        s.text(x0, 234, f"{f['tools']} real astrology & metaphysics techniques —", size=26, fill=t["text"], weight=600)
        s.text(x0, 272, "an MCP server and CLI any AI can call, on your own machine.", size=21, fill=t["sub"])
        stats = (
            (str(f["tools"]), "real techniques", t["gold"]),
            (str(f["full"]), "MCP tools (full surface)", t["teal"]),
            (str(f["clients"]), "clients, one command", t["violet"]),
            ("100%", "local · offline", t["rose"]),
        )
    s.line(x0, 306, 1220, 306, stroke=t["line"])
    for i, (num, label, color) in enumerate(stats):
        x = x0 + i * 168
        s.text(x, 354, num, size=38, fill=color, weight=700)
        s.text(x, 382, label, size=14, fill=t["muted"])
    return s


# --------------------------------------------------------------------------- figure: architecture


def band(s: Svg, y: float, h: float, num: str, name: str, subs: tuple[str, ...], *, highlight: bool = False) -> None:
    t = s.t
    if highlight:
        s.rect(24, y, 952, h, rx=20, fill="none", stroke=t["gold"], sw=6, opacity=0.12)
        s.rect(24, y, 952, h, rx=20, fill=t["card"], stroke=t["gold"], sw=1.4, opacity=1)
    else:
        s.rect(24, y, 952, h, rx=20, fill=t["card2"], stroke=t["line"])
    s.text(48, y + 36, num, size=13, fill=t["gold"], weight=600, family="mono", spacing=2)
    s.text(48, y + 64, name, size=19, fill=t["text"], weight=700)
    for i, line in enumerate(subs):
        s.text(48, y + 88 + i * 19, line, size=13, fill=t["muted"])


def down_arrow(s: Svg, x: float, y1: float, y2: float) -> None:
    s.line(x, y1, x, y2, stroke=s.t["muted"], sw=1.3, extra=' marker-end="url(#arrow)"')


def fig_architecture(t: dict[str, str], lang: str, f: dict) -> Svg:
    zh = lang == "zh"
    L = {
        "title": "Horosa Skill 架构图" if zh else "Horosa Skill architecture",
        "desc": ("四层：AI 客户端经 MCP / CLI 接入本地 Horosa Skill 进程（调度、澄清闸、技法、依据卡、报告与记忆），"
                 "由离线 runtime（Java 后端、Python chart 服务、Node headless JS）计算，结果落本地存储。") if zh else
                ("Four layers: AI clients reach the local Horosa Skill process over MCP or the CLI; it gates, dispatches and "
                 "documents each call, computes on the offline runtime (Java backend, Python chart service, Node headless JS) "
                 "and stores every run locally."),
        "eyebrow": "ARCHITECTURE  ·  系统架构" if zh else "ARCHITECTURE",
        "head": "四层架构，默认一切都在你的机器上" if zh else "Four layers — by default, nothing leaves your machine",
    }
    s = Svg(1000, 0, t, L["title"], L["desc"])  # height set once the last row is placed
    header(s, L["eyebrow"], L["head"])
    cx0, cw = 212, 740  # content column

    # 01 clients
    y = 118
    band(s, y, 124, "01", "AI 客户端" if zh else "AI clients", ("MCP 或 CLI，任选其一",) if zh else ("over MCP or the CLI",))
    names = ["Claude Code", "Claude Desktop", "Codex", "Cursor", "VS Code", "Gemini CLI", "Kiro", "Zed", "Open WebUI",
             "ChatGPT 连接器" if zh else "ChatGPT connector"]
    last = f"共 {f['clients']} 个一键接入" if zh else f"{f['clients']} one-command setups"
    x, row_y = cx0, y + 22
    for name in names + [last]:
        hl = name == last
        w = tw(name, 14.5) + 32
        if x + w > cx0 + cw:
            x, row_y = cx0, row_y + 44
        chip(s, x, row_y, name, fill=t["gold"] if hl else t["card"], stroke=t["gold"] if hl else t["line"],
             color=t["on"] if hl else t["sub"], weight=600 if hl else 500)
        x += w + 10

    # transports
    ty = y + 124
    for i, label in enumerate(("MCP · stdio", "MCP · streamable-http", "JSON-first CLI")):
        ax = cx0 + cw * (i + 0.5) / 3
        down_arrow(s, ax, ty + 4, ty + 50)
        w = tw(label, 13, mono=True) + 24
        s.rect(ax - w / 2, ty + 14, w, 24, rx=12, fill=t["bg0"], stroke=t["line"])
        s.text(ax, ty + 30.5, label, size=13, fill=t["teal"], anchor="middle", family="mono")

    # 02 horosa skill
    y = ty + 56
    band(s, y, 314, "02", "Horosa Skill", ("本地 MCP 进程", "Python 3.12 · uv") if zh else ("local MCP process", "Python 3.12 · uv"), highlight=True)
    facades = (("自然语言调度", "horosa_dispatch"), ("多技法合参", "horosa_hecan"), ("按名直调", "horosa_tool_run"),
               ("参数指引", "horosa_agent_guidance")) if zh else \
              (("Dispatch", "horosa_dispatch"), ("Synthesis", "horosa_hecan"), ("Call by name", "horosa_tool_run"),
               ("Guidance", "horosa_agent_guidance"))
    fw = (cw - 30) / 4
    for i, (name, tool) in enumerate(facades):
        fx = cx0 + i * (fw + 10)
        s.rect(fx, y + 22, fw, 60, rx=12, fill=t["card2"], stroke=t["line"])
        s.text(fx + 14, y + 47, name, size=15.5, fill=t["text"], weight=600)
        s.text(fx + 14, y + 69, tool, size=12, fill=t["muted"], family="mono")
    gy = y + 94
    s.rect(cx0, gy, cw, 48, rx=12, fill=t["rose"], opacity=0.10)
    s.rect(cx0, gy, cw, 48, rx=12, fill="none", stroke=t["rose"], sw=1.2, opacity=0.6)
    # gate glyph: two posts and a bar
    s.add(f'<g stroke="{t["rose"]}" stroke-width="2.2" stroke-linecap="round"><path d="M{cx0 + 20} {gy + 14}v20M{cx0 + 38} {gy + 14}v20M{cx0 + 16} {gy + 20}h26"/></g>')
    gate_name = "澄清闸" if zh else "Clarification gate"
    s.text(cx0 + 54, gy + 30, gate_name, size=15.5, fill=t["rose"], weight=700)
    gate_text = ("时间 / 地点 / 时区 / 性别 / 流派缺一项就先问用户，绝不替用户脑补" if zh else
                 "missing time / place / timezone / gender / school → ask the user, never guess")
    s.text(cx0 + 54 + tw(gate_name, 15.5) + 16, gy + 30, gate_text, size=14, fill=t["sub"])
    core = ((f"{f['tools']} 个技法", "西洋 · 中式术数 · 神数 · 择日", "gold"),
            ("统一 envelope", "export_snapshot 段结构正文", "teal"),
            ("技法依据卡", "technique_card · 口径与版本链", "violet")) if zh else \
           ((f"{f['tools']} techniques", "Western · Chinese · Shen Shu", "gold"),
            ("Uniform envelope", "export_snapshot, sectioned text", "teal"),
            ("Provenance card", "technique_card · settings", "violet"))
    cwid = (cw - 20) / 3
    for i, (name, sub, accent) in enumerate(core):
        kx = cx0 + i * (cwid + 10)
        s.rect(kx, gy + 60, cwid, 86, rx=14, fill=t["card2"], stroke=t["line"])
        s.rect(kx, gy + 60, 4, 86, rx=2, fill=t[accent])
        s.text(kx + 20, gy + 96, name, size=18, fill=t[accent], weight=700)
        s.text(kx + 20, gy + 122, sub, size=13.5, fill=t["sub"])
    pills = (["地名检索", "命主档案", f"知识库 {f['domains']} 域", "报告 DOCX / PDF / PNG / ICS", "忠实性评测", "本地记忆"] if zh else
             ["Places", "Profiles", f"{f['domains']} knowledge domains", "DOCX / PDF / PNG / ICS", "Faithfulness", "Memory"])
    px = cx0
    for label in pills:
        px += chip(s, px, gy + 162, label, size=13.5, h=32, pad=14, fill=t["card2"], stroke=t["line"], color=t["sub"]) + 9

    # local call arrows
    ry = y + 314
    for i in range(3):
        down_arrow(s, cx0 + cw * (i + 0.5) / 3, ry + 4, ry + 50)
    lab = "本机调用 · 断网可用" if zh else "local calls · works offline"
    w = tw(lab, 13) + 26
    s.rect(cx0 + cw / 2 - w / 2, ry + 14, w, 24, rx=12, fill=t["bg0"], stroke=t["line"])
    s.text(cx0 + cw / 2, ry + 30.5, lab, size=13, fill=t["muted"], anchor="middle")

    # 03 runtime
    y = ry + 56
    band(s, y, 214, "03", "离线 runtime" if zh else "Offline runtime",
         ("随 Release 分发", "macOS · Windows") if zh else ("release assets", "macOS · Windows"))
    engines = (("Java 后端", ("农历 · 节气 · 八字", "紫微斗数 · 大六壬"), "Spring Boot · 随包 JDK 17", "orange"),
               ("Python chart 服务", ("西洋星盘 · 推运 · 择日", "ken 三式 · kentang 神数"), "Swiss Ephemeris · flatlib", "blue"),
               ("Node · horosa-core-js", ("aiExport 段结构重排", "本地 JS 引擎 · 离线城市库"), "headless · 与桌面端同源", "teal")) if zh else \
              (("Java backend", ("lunar calendar · solar terms", "BaZi · Zi Wei · Da Liu Ren"), "Spring Boot · bundled JDK 17", "orange"),
               ("Python chart service", ("Western charts · predictive", "ken Three Styles · Shen Shu"), "Swiss Ephemeris · flatlib", "blue"),
               ("Node · horosa-core-js", ("aiExport section layout", "local JS engines · city atlas"), "headless · desktop parity", "teal"))
    ew = (cw - 20) / 3
    for i, (name, lines, foot, accent) in enumerate(engines):
        ex = cx0 + i * (ew + 10)
        s.rect(ex, y + 22, ew, 170, rx=14, fill=t["card"], stroke=t["line"])
        s.circle(ex + 22, y + 50, 5, fill=t[accent])
        s.text(ex + 36, y + 55.5, name, size=16, fill=t["text"], weight=700)
        s.line(ex + 18, y + 72, ex + ew - 18, y + 72, stroke=t["line2"])
        for k, text in enumerate(lines):
            s.text(ex + 20, y + 100 + k * 25, text, size=14, fill=t["sub"])
        s.text(ex + 20, y + 172, foot, size=12, fill=t["muted"], family="mono")

    # 04 storage
    y += 214 + 16
    band(s, y, 118, "04", "本地存储" if zh else "Local storage", ("~/.horosa-skill",))
    items = (("SQLite 全文索引", "trigram · 中文子串可命中", "blue"), ("JSON artifact", "每次调用一份完整快照", "teal"),
             ("trace JSONL", "调用链可回放", "slate"), ("命主档案", "「我」「妈妈」本机保存", "violet"),
             ("自备知识库", "你自己的笔记", "gold")) if zh else \
            (("SQLite full-text", "trigram · CJK substrings", "blue"), ("JSON artifacts", "one per call", "teal"),
             ("trace JSONL", "replayable", "slate"), ("Profiles", "“me”, “mom”", "violet"),
             ("Your notes", "your own folder", "gold"))
    iw = cw / 5
    for i, (name, sub, accent) in enumerate(items):
        ix = cx0 + i * iw
        s.circle(ix + 6, y + 47, 4.5, fill=t[accent])
        s.text(ix + 18, y + 52, name, size=14.5, fill=t["text"], weight=600)
        s.text(ix + 18, y + 76, sub, size=12, fill=t["muted"])

    # footer: upstream + distribution
    fy = y + 118 + 34
    up = "上游：星阙开源仓 → 单向同步进 vendor/（从不反向）" if zh else "Upstream: the open-source Horosa tree → vendor/ (one-way sync)"
    dist = "分发：GitHub Releases（runtime · wheel · .mcpb）· MCP Registry" if zh else "Distribution: GitHub Releases (runtime · wheel · .mcpb) · MCP Registry"
    s.circle(54, fy - 4.5, 3.5, fill=t["gold"])
    s.text(66, fy, up, size=13, fill=t["muted"])
    s.circle(520, fy - 4.5, 3.5, fill=t["teal"])
    s.text(532, fy, dist, size=13, fill=t["muted"])
    s.h = int(fy + 30)
    return s


# --------------------------------------------------------------------------- figure: flow


def fig_flow(t: dict[str, str], lang: str, f: dict) -> Svg:
    zh = lang == "zh"
    steps = (("用户提问", "「查今年事业」", "生辰 · 出生地", "slate"),
             ("澄清闸", "缺时区 / 宫制？", "先问，不脑补", "rose"),
             ("本机起盘", "离线 runtime", "统一 envelope", "blue"),
             ("读盘", "只读 export_snapshot", "禁止手算", "teal"),
             ("溯源", "technique_card", "技法 · 口径 · 版本", "violet"),
             ("归档 · 出报告", "SQLite + JSON", "DOCX / PDF / PNG", "gold")) if zh else \
            (("Ask", "“career this year?”", "birth time · place", "slate"),
             ("Clarify", "timezone? houses?", "ask, never guess", "rose"),
             ("Compute", "offline runtime", "uniform envelope", "blue"),
             ("Read", "export_snapshot only", "no hand math", "teal"),
             ("Trace", "technique_card", "technique · settings", "violet"),
             ("Archive", "SQLite + JSON", "DOCX / PDF / PNG", "gold"))
    title = "一次调用的流程" if zh else "The life of one call"
    desc = " → ".join(step[0] for step in steps)
    s = Svg(1000, 318, t, title, desc)
    header(s, "ONE CALL  ·  一次调用" if zh else "ONE CALL",
           "从一句提问，到一份可溯源的报告" if zh else "From one question to a traceable report")
    cy, x_first, step = 200, 92, 163
    for i in range(len(steps) - 1):
        x1 = x_first + i * step + 31
        s.line(x1, cy, x1 + step - 62, cy, stroke=t["muted"], sw=1.3, extra=' marker-end="url(#arrow)"')
    # the gate loops back to the user
    x1, x2 = x_first + step, x_first
    s.add(f'<path d="M{x1 - 6} {cy - 30} C{x1 - 30} {cy - 84} {x2 + 30} {cy - 84} {x2 + 6} {cy - 30}" fill="none" '
          f'stroke="{t["rose"]}" stroke-width="1.4" stroke-dasharray="4 4" marker-end="url(#arrowRose)"/>')
    s.defs.append(f'<marker id="arrowRose" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" '
                  f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{t["rose"]}"/></marker>')
    s.text((x1 + x2) / 2, cy - 76, "缺设置 → 先问用户" if zh else "missing a setting → ask", size=13, fill=t["rose"], anchor="middle", weight=600)
    for i, (name, a, b, accent) in enumerate(steps):
        x = x_first + i * step
        s.circle(x, cy, 26, fill=t["card"], stroke=t[accent], sw=2)
        s.text(x, cy + 6, f"{i + 1:02d}", size=15, fill=t[accent], weight=700, anchor="middle", family="mono")
        s.text(x, cy + 58, name, size=16.5, fill=t["text"], weight=700, anchor="middle")
        s.text(x, cy + 80, a, size=12.5, fill=t["sub"], anchor="middle")
        s.text(x, cy + 99, b, size=12.5, fill=t["muted"], anchor="middle")
    return s


# --------------------------------------------------------------------------- figure: techniques


def arc_path(cx: float, cy: float, r1: float, r2: float, a0: float, a1: float) -> str:
    large = 1 if a1 - a0 > 180 else 0
    p0, p1 = polar(cx, cy, r2, a0), polar(cx, cy, r2, a1)
    q1, q0 = polar(cx, cy, r1, a1), polar(cx, cy, r1, a0)
    return (f"M{n(p0[0])} {n(p0[1])}A{r2} {r2} 0 {large} 1 {n(p1[0])} {n(p1[1])}"
            f"L{n(q1[0])} {n(q1[1])}A{r1} {r1} 0 {large} 0 {n(q0[0])} {n(q0[1])}Z")


def fig_techniques(t: dict[str, str], lang: str, f: dict) -> Svg:
    zh = lang == "zh"
    fam = f["families"]
    total = sum(fam.values())
    title = f"{total} 个技法的门类分布" if zh else f"The {total} techniques by family"
    desc = "; ".join(f"{(z if zh else e)}: {fam[k]}" for k, _p, z, e, *_ in FAMILIES)
    s = Svg(1000, 580, t, title, desc)
    header(s, "TECHNIQUES  ·  技法图谱" if zh else "TECHNIQUES", f"{total} 个真实技法，八大门类" if zh else f"{total} real techniques in eight families")
    cx, cy, r1, r2 = 250, 332, 112, 176
    s.circle(cx, cy, 192, stroke=t["line"], sw=1, extra=' stroke-dasharray="2 5"')
    gap = 1.4
    a = 0.0
    for key, _probe, _z, _e, _zx, _ex, accent in FAMILIES:
        sweep = fam[key] / total * 360
        s.add(f'<path d="{arc_path(cx, cy, r1, r2, a + gap / 2, a + sweep - gap / 2)}" fill="{t[accent]}"/>')
        mx, my = polar(cx, cy, (r1 + r2) / 2, a + sweep / 2)
        s.text(mx, my + 6, str(fam[key]), size=16 if fam[key] >= 10 else 15, fill=t["on"], weight=700, anchor="middle")
        tx, ty = polar(cx, cy, 192, a)
        ox, oy = polar(cx, cy, 186, a)
        s.line(ox, oy, tx, ty, stroke=t["muted"], sw=1)
        a += sweep
    s.circle(cx, cy, r1 - 10, fill=t["card"], stroke=t["line"])
    s.text(cx, cy + 10, str(total), size=56, fill=t["text"], weight=800, anchor="middle")
    s.text(cx, cy + 38, "个技法 · 全部离线" if zh else "techniques · offline", size=14, fill=t["muted"], anchor="middle")

    lx, rx, y = 500, 952, 156
    for key, _probe, zname, ename, zex, eex, accent in FAMILIES:
        s.rect(lx, y - 13, 14, 14, rx=4, fill=t[accent])
        s.text(lx + 26, y, zname if zh else ename, size=16.5, fill=t["text"], weight=600)
        s.text(rx, y, str(fam[key]), size=17, fill=t[accent], weight=700, anchor="end", family="mono")
        s.text(lx + 26, y + 22, zex if zh else eex, size=13, fill=t["muted"])
        s.line(lx + 26, y + 36, rx, y + 36, stroke=t["line2"])
        y += 52
    return s


# --------------------------------------------------------------------------- figure: repo


def fig_repo(t: dict[str, str], lang: str, f: dict) -> Svg:
    zh = lang == "zh"
    rows = (
        (0, "horosa-skill/", "Python 包：MCP server · CLI · 门禁与测试（uv 项目）", "Python package: MCP server · CLI · gates & tests (uv)", "gold"),
        (1, "src/horosa_skill/", "主程序", "the application", ""),
        (2, "surfaces/", "MCP server 与 CLI 两个入口", "the two entry points: MCP server and CLI", ""),
        (2, "service/", "调度 · 各族技法 runner · 合参 · 报告与记忆 API", "dispatch · per-family runners · synthesis · report & memory APIs", ""),
        (2, "engine/", f"{f['tools']} 个技法的注册表 · 路由 · 引擎客户端", f"registry of the {f['tools']} techniques · router · engine clients", ""),
        (2, "agent_guidance/", "澄清闸：哪些设置必须先问用户", "the clarification gate: which settings must be asked", ""),
        (2, "runtime/", "离线 runtime 安装 · doctor · 启停", "offline runtime install · doctor · start / stop", ""),
        (2, "exports/  knowledge/", "导出契约 · 知识库检索", "export contract · knowledge retrieval", ""),
        (2, "memory/  reports/", "SQLite 记忆 · DOCX / PDF / PNG / ICS 报告", "SQLite memory · DOCX / PDF / PNG / ICS reports", ""),
        (1, "horosa-core-js/", "headless JS：aiExport 段结构 · 城市库 · 本地引擎", "headless JS: aiExport sections · city atlas · local engines", ""),
        (1, "contracts/", "机读契约与守卫基线（JSON）", "machine-readable contracts & guard baselines (JSON)", ""),
        (1, "scripts/  tests/", "CI 门禁镜像 · 发版脚本 · 测试", "CI gate mirror · release scripts · tests", ""),
        (0, "skills/horosa-agent/", "给 AI 客户端的行为规则（策略唯一源）", "behaviour rules for AI clients (single policy source)", "violet"),
        (0, "vendor/", "从星阙开源仓单向同步的 runtime 源", "runtime sources synced one-way from the open-source Horosa tree", "orange"),
        (0, "docs/", "架构 · 输入 / 输出契约 · 运维 · 经验台账", "architecture · input / output contracts · operations · lessons", "blue"),
        (0, ".claude-plugin/  plugin.json  mcp.json", "Claude Code 插件与 Agent Plugins 清单", "Claude Code plugin & Agent Plugins manifests", "teal"),
        (0, "server.json", "MCP Registry 元数据", "MCP Registry metadata", "teal"),
    )
    top, row_h = 132, 32
    h = top + len(rows) * row_h + 22
    s = Svg(1000, h, t, "仓库结构" if zh else "Repository layout",
            "; ".join(f"{r[1]} — {r[2] if zh else r[3]}" for r in rows))
    header(s, "REPOSITORY  ·  仓库结构" if zh else "REPOSITORY",
           "代码与文档在 Git，离线 runtime 走 GitHub Releases" if zh else "Code and docs in Git — the offline runtime ships via GitHub Releases")
    base_x, indent, desc_x = 64, 28, 520
    ys = [top + i * row_h for i in range(len(rows))]
    # guide lines: for each parent, a vertical rail down to its last child, and a stub to each child
    guides: list[str] = []
    for i, (level, *_rest) in enumerate(rows):
        children = []
        for j in range(i + 1, len(rows)):
            if rows[j][0] <= level:
                break
            if rows[j][0] == level + 1:
                children.append(j)
        if not children:
            continue
        vx = base_x + level * indent + 7
        guides.append(f"M{n(vx)} {n(ys[i] + 8)}V{n(ys[children[-1]] - 5)}")
        for j in children:
            guides.append(f"M{n(vx)} {n(ys[j] - 5)}H{n(vx + indent - 12)}")
    s.add(f'<path d="{"".join(guides)}" fill="none" stroke="{t["line"]}" stroke-width="1.2"/>')
    for i, (level, name, zdesc, edesc, accent) in enumerate(rows):
        x, y = base_x + level * indent, ys[i]
        if level == 0:
            s.rect(x - 3, y - 13, 12, 12, rx=3, fill=t[accent])
            nx = x + 18
        else:
            nx = x + 6
        weight = 700 if level == 0 else 500
        color = t["text"] if level < 2 else t["sub"]
        s.text(nx, y, name, size=15, fill=color, weight=weight, family="mono")
        end = nx + tw(name, 15, mono=True) + 12
        if end < desc_x - 14:
            s.line(end, y - 4, desc_x - 14, y - 4, stroke=t["line"], sw=1, extra=' stroke-dasharray="1 5" stroke-linecap="round"')
        s.text(desc_x, y, zdesc if zh else edesc, size=14, fill=t["sub"] if level == 0 else t["muted"])
    return s


# --------------------------------------------------------------------------- driver

RENDERERS = {"hero": fig_hero, "architecture": fig_architecture, "flow": fig_flow, "techniques": fig_techniques, "repo": fig_repo}


def render_all(facts: dict | None = None) -> dict[str, str]:
    facts = facts or collect_facts()
    out: dict[str, str] = {}
    for fig in FIGURES:
        for lang in LANGS:
            for theme in THEME_NAMES:
                out[f"{OUT_REL}/{fig}-{lang}-{theme}.svg"] = RENDERERS[fig](THEMES[theme], lang, facts).render()
    return out


def drift(rendered: dict[str, str] | None = None) -> list[str]:
    """Repo-relative paths whose committed bytes differ from the render (plus stray SVGs nobody renders)."""
    rendered = rendered or render_all()
    bad = [rel for rel, body in rendered.items()
           if not (ROOT / rel).exists() or (ROOT / rel).read_text(encoding="utf-8") != body]
    if OUT.exists():
        bad += sorted(p.relative_to(ROOT).as_posix() for p in OUT.glob("*.svg") if p.relative_to(ROOT).as_posix() not in rendered)
    return bad


def main() -> None:
    # Windows consoles default to cp1252 / cp936; the drift report can name paths and the docstring is CJK-adjacent.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="exit 1 when a committed SVG differs from the render")
    args = parser.parse_args()
    rendered = render_all()
    if args.check:
        bad = drift(rendered)
        if bad:
            print("readme-diagrams: out of date — rerun `uv run python scripts/gen_readme_diagrams.py`:\n  " + "\n  ".join(bad))
            raise SystemExit(1)
        print(f"readme-diagrams: {len(rendered)} SVGs up to date")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    for rel, body in rendered.items():
        (ROOT / rel).write_text(body, encoding="utf-8", newline="\n")
    for stray in drift(rendered):
        (ROOT / stray).unlink()
    print(f"readme-diagrams: wrote {len(rendered)} SVGs to {OUT_REL}/")


if __name__ == "__main__":
    main()
