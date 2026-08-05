"""Cross-file documentation drift guard (CI: runs in the `test` job).

Deterministic assertions over the guidance layer:

1. **Version lockstep** — `pyproject.toml`, `src/horosa_skill/__init__.py`, `server.json` (every
   `version` key), `CITATION.cff`, and the README zh/en "当前公开版本 / Current public version"
   headlines all carry the same package version.
2. **Tool coverage** — every tool id in `TOOL_DEFINITIONS` appears (as `` `id` ``) in `README.md`,
   `README_EN.md`, and `skills/horosa-agent/SKILL.md`; the `tools-N` badges and headline tool counts
   equal the registry count.
3. **Stale-version claims** — any ``current: `X.Y.Z` `` claim in `docs/*.md` must equal the package
   version (the class of drift that once left REPO_LAYOUT at 0.6.1).
4. **Links** — every relative markdown link in the guidance docs (CLAUDE.md, AGENTS.md, READMEs,
   docs/*.md, skill docs) resolves to an existing file.
5. **Conflict markers** — no `<<<<<<< ` / `=======` / `>>>>>>> ` lines anywhere tracked-ish.
6. **Skill frontmatter** — both SKILL.md files start with YAML frontmatter carrying `name:` and
   `description:` (required for agent-skill discovery).

Extend this file whenever a new cross-file doc invariant appears (AGENTS.md §2 rule 4: assertable
gotchas get a machine guard, not just a doc note).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "horosa-skill"

sys.path.insert(0, str(PKG / "src"))
from horosa_skill.engine.registry import TOOL_DEFINITIONS  # noqa: E402
from horosa_skill.exports.registry import AI_EXPORT_TECHNIQUES  # noqa: E402

ERRORS: list[str] = []


def err(msg: str) -> None:
    ERRORS.append(msg)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --- 1. version lockstep -------------------------------------------------------------------

def expected_version() -> str:
    m = re.search(r'^version = "([^"]+)"', read(PKG / "pyproject.toml"), re.M)
    assert m, "pyproject.toml: version line not found"
    return m.group(1)


def check_versions(version: str) -> None:
    m = re.search(r'^__version__ = "([^"]+)"', read(PKG / "src/horosa_skill/__init__.py"), re.M)
    if not m or m.group(1) != version:
        err(f"__init__.py __version__ = {m.group(1) if m else '?'} != {version}")

    def walk(node: object) -> list[str]:
        found: list[str] = []
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "version" and isinstance(value, str):
                    found.append(value)
                else:
                    found.extend(walk(value))
        elif isinstance(node, list):
            for item in node:
                found.extend(walk(item))
        return found

    for got in walk(json.loads(read(ROOT / "server.json"))):
        if got != version:
            err(f"server.json carries version {got} != {version}")

    m = re.search(r'^version: "?([0-9][^"\s]*)"?', read(ROOT / "CITATION.cff"), re.M)
    if not m or m.group(1) != version:
        err(f"CITATION.cff version = {m.group(1) if m else '?'} != {version}")

    plugin = ROOT / ".claude-plugin/plugin.json"
    if plugin.exists():
        got = json.loads(read(plugin)).get("version")
        if got != version:
            err(f".claude-plugin/plugin.json version = {got} != {version}")
        json.loads(read(ROOT / ".claude-plugin/marketplace.json"))  # must parse

    # CHANGELOG.md 是 gitignored 本地文件——公开 README 里任何指向它的链接在 GitHub 上都是 404。
    for path in (ROOT / "README.md", ROOT / "README_EN.md"):
        if "CHANGELOG.md" in read(path):
            err(f"{path.name}: references CHANGELOG.md (gitignored local-only file; link would 404 on GitHub)")

    # zh README（v0.21 视觉重构后）版本声明在 Release runtime 行；EN 保留 headline 句。
    headline = {
        ROOT / "README.md": re.compile(r"`v([0-9.]+)` 已打包并校验"),
        ROOT / "README_EN.md": re.compile(r"Current public version: `Horosa Skill ([0-9.]+)` \((\d+) callable tools\)"),
    }
    for path, pattern in headline.items():
        m = pattern.search(read(path))
        if not m:
            err(f"{path.name}: version headline not found (pattern drifted?)")
            continue
        if m.group(1) != version:
            err(f"{path.name}: headline version {m.group(1)} != {version}")
        if len(m.groups()) > 1 and int(m.group(2)) != len(TOOL_DEFINITIONS):
            err(f"{path.name}: headline tool count {m.group(2)} != registry {len(TOOL_DEFINITIONS)}")


# --- 2. tool coverage ----------------------------------------------------------------------

# 每一处把「工具数」写死进散文/徽章/表格的地方。散文里的数字没人守，83→89 那次 bump 就在中文首页留下
# 四处 83（徽章 URL 的 alt 甚至已经写着 89）。凡是 registry 的纯函数就在这里登记，别靠人记得改。
# 模式找不到时报错而非静默跳过——文案改写了要来这里同步，这正是我们想要的提醒。
TOOL_COUNT_CLAIMS = {
    "README.md": (
        r"badge/技法-(\d+)-",
        r"星阙 (\d+) 个术数",
        r"星阙（Horosa）的 (\d+) 个真实术数",
        r"exposes (\d+) real astrology",
        r"(\d+) 技法一次装齐",
        r"本地进程 · (\d+) 工具",
        r"(\d+) 个真实技法，一次安装",
        r"(\d+) 技法目录索引",
        r"可调用工具 \| (\d+) / (\d+)",
    ),
    "README_EN.md": (
        r"badge/tools-(\d+)-",
        r"call <strong>(\d+)</strong> real techniques",
        r"Capability map \((\d+) tools\)",
        r"Callable tools \| `(\d+) / (\d+) ok=true`",
    ),
}

EXPORT_COUNT_CLAIMS = {
    "README.md": (r"已建模 (\d+) 个导出 technique",),
    "README_EN.md": (r"`(\d+)` export techniques modeled",),
}


def check_counted_claims(claims: dict[str, tuple[str, ...]], expected: int, label: str) -> None:
    for name, patterns in claims.items():
        text = read(ROOT / name)
        for pattern in patterns:
            found = re.findall(pattern, text)
            if not found:
                err(f"{name}: {label} pattern not found (copy drifted?): {pattern}")
                continue
            for match in found:
                for got in (match if isinstance(match, tuple) else (match,)):
                    if int(got) != expected:
                        err(f"{name}: {label} says {got}, registry has {expected} ({pattern})")


def check_tool_coverage() -> None:
    docs = [ROOT / "README.md", ROOT / "README_EN.md", ROOT / "skills/horosa-agent/SKILL.md"]
    for path in docs:
        text = read(path)
        missing = sorted(t for t in TOOL_DEFINITIONS if f"`{t}`" not in text)
        if missing:
            err(f"{path.relative_to(ROOT)}: tool ids not documented: {', '.join(missing)}")
    check_counted_claims(TOOL_COUNT_CLAIMS, len(TOOL_DEFINITIONS), "tool count")
    # 「已建模 N 个导出 technique」= len(AI_EXPORT_TECHNIQUES)（曾停在 63 而实际 86）。
    check_counted_claims(EXPORT_COUNT_CLAIMS, len(AI_EXPORT_TECHNIQUES), "export-technique count")


# --- 2b. test-count consistency ------------------------------------------------------------

# 测试数不能从代码静态推出（要真跑一轮），所以这里只能守「四处口径一致」——但那正是它漏掉的：
# v0.25.0 时 zh 三处写 326、EN 表格写 326 而 EN 代码块写 315，实际收集数早已不是这些。
TEST_COUNT_PATTERNS = (
    r"badge/测试-(\d+)_passed",
    r'alt="(\d+) passed"',
    r"工程测试 \| \*\*(\d+) / (\d+) pass",
    r"Engineering tests \| `(\d+) / (\d+) pass",
    r"#\s*(\d+) passed",
)


def check_test_count_consistency() -> None:
    seen: dict[int, list[str]] = {}
    for path in (ROOT / "README.md", ROOT / "README_EN.md"):
        text = read(path)
        for pattern in TEST_COUNT_PATTERNS:
            for match in re.findall(pattern, text):
                for got in (match if isinstance(match, tuple) else (match,)):
                    seen.setdefault(int(got), []).append(f"{path.name}:{pattern}")
    if not seen:
        err("README.md/README_EN.md: no test-count claim found (patterns drifted?)")
    elif len(seen) > 1:
        detail = "; ".join(f"{count} ({len(where)}x)" for count, where in sorted(seen.items()))
        err(f"README test-count claims disagree: {detail} — all mentions must carry one number")


# --- 3. stale "current: `X`" claims in docs -------------------------------------------------

def check_stale_claims(version: str) -> None:
    for path in sorted((ROOT / "docs").glob("*.md")):
        for got in re.findall(r"current: `(\d+\.\d+\.\d+)`", read(path)):
            if got != version:
                err(f"docs/{path.name}: stale 'current: `{got}`' claim (package is {version})")


# --- 4. relative links ---------------------------------------------------------------------

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def check_links() -> None:
    targets = [
        ROOT / "CLAUDE.md",
        ROOT / "AGENTS.md",
        ROOT / "README.md",
        ROOT / "README_EN.md",
        # local-only (gitignored) — checked when present, skipped on public/CI checkouts
        ROOT / ".claude/skills/horosa-dev/SKILL.md",
        *sorted((ROOT / "docs").glob("*.md")),
        *sorted((ROOT / "skills").rglob("*.md")),
    ]
    for path in targets:
        if not path.exists():
            continue
        for raw in LINK.findall(read(path)):
            if raw.startswith(("http://", "https://", "mailto:", "#")):
                continue
            rel = raw.split("#", 1)[0]
            if not rel:
                continue
            if not (path.parent / rel).resolve().exists():
                err(f"{path.relative_to(ROOT)}: broken relative link -> {raw}")


# --- 5. conflict markers -------------------------------------------------------------------

SKIP_DIRS = {".git", ".venv", "node_modules", "vendor", ".horosa-cache", ".pytest_cache",
             "runs", "dist", "build", "__pycache__", ".umi", ".umi-production"}
TEXT_SUFFIXES = {".md", ".py", ".yml", ".yaml", ".json", ".js", ".mjs", ".toml", ".cff",
                 ".mdc", ".txt", ".sh", ".ps1", ".cfg", ".ini"}
MARKER = re.compile(r"^(<{7}( |$)|={7}$|>{7}( |$))")


def check_conflict_markers() -> None:
    for path in ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        if path.stat().st_size > 2_000_000:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(lines, 1):
            if MARKER.match(line):
                err(f"{path.relative_to(ROOT)}:{lineno}: git conflict marker: {line[:40]!r}")


# --- 6. skill frontmatter ------------------------------------------------------------------

def check_frontmatter() -> None:
    # horosa-dev is local-only (gitignored) — checked when present, skipped on public/CI checkouts
    for path in (ROOT / "skills/horosa-agent/SKILL.md", ROOT / ".claude/skills/horosa-dev/SKILL.md"):
        if not path.exists():
            continue
        text = read(path)
        if not text.startswith("---\n"):
            err(f"{path.relative_to(ROOT)}: missing YAML frontmatter (must start with ---)")
            continue
        head = text.split("\n---", 2)[0]
        for field in ("name:", "description:"):
            if field not in head:
                err(f"{path.relative_to(ROOT)}: frontmatter missing '{field}'")


def main() -> None:
    version = expected_version()
    check_versions(version)
    check_tool_coverage()
    check_test_count_consistency()
    check_stale_claims(version)
    check_links()
    check_conflict_markers()
    check_frontmatter()
    if ERRORS:
        raise SystemExit("docs-sync: FAIL\n- " + "\n- ".join(ERRORS))
    print(f"docs-sync: ok (version {version}, {len(TOOL_DEFINITIONS)} tools, "
          "links/markers/frontmatter clean)")


if __name__ == "__main__":
    main()
