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

    # horosa-core-js ships inside every runtime payload and carries its own version. It was outside
    # this lockstep check entirely, so v0.26.0 bumped package.json to 0.26.0 and left package-lock
    # at 0.25.1 — nothing noticed until a build's `npm install` rewrote the lock. Both, every release.
    core_js = ROOT / "horosa-skill" / "horosa-core-js"
    for name, keys in (("package.json", ("version",)), ("package-lock.json", ("version",))):
        path = core_js / name
        if not path.exists():
            continue
        data = json.loads(read(path))
        candidates = [data.get(key) for key in keys]
        if name == "package-lock.json":
            candidates.append((data.get("packages", {}).get("") or {}).get("version"))
        for got in [c for c in candidates if c is not None]:
            if got != version:
                err(f"horosa-core-js/{name} version = {got} != {version}")

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
        r"星阙 (\d+) 个术数",
        r"星阙（Horosa）的 (\d+) 个真实术数",
        r"exposes (\d+) real astrology",
        r"(\d+) 技法一次装齐",
        r"本地进程 · (\d+) 工具",
        r"(\d+) 个真实技法，一次安装",
        r"(\d+) 技法目录索引",
    ),
    "README_EN.md": (
        r"call <strong>(\d+)</strong> real techniques",
        r"Capability map \((\d+) tools\)",
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
    # v0.25.1 的「登记式」与 v0.26.0 的「语言无关式」是互补的，两边都留：
    #   前者：每条声明显式登记，模式找不到就报错——抓「文案改写把声明弄没了」。
    #   后者：不登记也能抓，且覆盖 AGENTS/CLAUDE/manifest/banner/plugin 与 _SERVER_INSTRUCTIONS，
    #         并断言同一行 badge 与 alt 不得自相矛盾。
    check_counted_claims(TOOL_COUNT_CLAIMS, len(TOOL_DEFINITIONS), "tool count")
    # 「已建模 N 个导出 technique」= len(AI_EXPORT_TECHNIQUES)（曾停在 63 而实际 86）。
    check_counted_claims(EXPORT_COUNT_CLAIMS, len(AI_EXPORT_TECHNIQUES), "export-technique count")


# --- 2c. test-count consistency ------------------------------------------------------------

# 「几处一致」不等于「数字是真的」——v0.26.0 五处齐刷刷写 320/63，而 CI 实测 318/65，守卫全绿。
# 一致性只能抓「改了一处忘了另一处」。真值这一半靠下面的 check_test_count_is_real()：
# offline + live-skipped 必须等于 `pytest --collect-only` 的收集总数，那个数是**静态可得**的。
TEST_COUNT_PATTERNS = (
    r"badge/测试-(\d+)_passed",
    r'alt="(\d+) passed"',
    r"工程测试 \| \*\*(\d+) / (\d+) pass",
    r"Engineering tests \| `(\d+) / (\d+) pass",
    r"#\s*(\d+) passed",
)


def check_test_count_is_real() -> None:
    """声明的 offline + live-skipped 必须等于真实收集总数。

    收集总数用 `--collect-only` 静态取（不跑测试、秒级）。这条能抓到「一致但全错」——
    即五处写着同一个假数字、consistency 守卫照样绿的那种。
    """
    import subprocess

    text = read(ROOT / "README.md")
    m = re.search(r"\*\*(\d+) / \d+ pass\*\*（离线 CI 形状[^）]*?另 (\d+) 项 live", text)
    if not m:
        err("README.md: 测试数声明的形状变了，check_test_count_is_real 需要同步")
        return
    claimed = int(m.group(1)) + int(m.group(2))
    try:
        out = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q"],
            cwd=PKG, capture_output=True, text=True, timeout=180,
        ).stdout
    except Exception as exc:  # noqa: BLE001 — 环境问题不该让文档守卫变红
        print(f"::notice::test-count truth check skipped ({exc})")
        return
    got = re.search(r"(\d+) tests? collected", out)
    if not got:
        print("::notice::test-count truth check skipped (could not read collected count)")
        return
    if claimed != int(got.group(1)):
        err(
            f"README 声明 offline+live = {claimed}，而 pytest 实际收集 {got.group(1)} —— "
            "数字对不上真值（五处写成同一个假数字时，一致性守卫是绿的）"
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

    check_tool_counts()


# --- 2b. tool-count claims outside the guarded headline --------------------------------------
# Every drift found in the v0.26.0 audit lived here: the zh README's badge said 83 while the very same
# line's alt said 89, three prose lines said 83, and `_SERVER_INSTRUCTIONS` — which ships to every MCP
# client — said 83 twice. The old regex only matched `badge/tools-(\d+)-`, so the English phrasing
# happened to be guarded and the Chinese one was not. Make the checks language-agnostic instead.

COUNT_BADGE = re.compile(r"badge/(tools|技法|工具)-(\d+)-")
COUNT_ALT = re.compile(r'alt="(\d+)\s*tools?"')
COUNT_PROSE = re.compile(r"(\d+)\s*(?:个)?\s*(技法|工具|tools\b|techniques\b)")
# manifest.json phrases it as "83 real technique tools" / "83 real 术数/占星 techniques" — a bounded
# lazy filler catches those without the tight form's false-positive risk.
COUNT_PROSE_EN = re.compile(r"(\d+)\s+real\s+[^,.;]{0,30}?\b(tools?|techniques?)\b")
# 「N 个术数/占星技法」逐字出现在 CLAUDE.md / AGENTS.md / banner.svg 三处 —— 用精确短语而不是放宽
# 通用正则，否则「约 9 个门面工具」这类真·小数字会被误报。
COUNT_PHRASE_ZH = re.compile(r"(\d+)\s*个术数\s*/?\s*占星技法")
# README 自检表的「N / N ok=true」「N / N 写入」行 —— 描述的是本次发布的构建，必须跟注册表同步。
COUNT_SELFCHECK = re.compile(r"(\d+)\s*/\s*(\d+)\s*`?\s*(?:ok=true|写入|writes)")
# 行内先剥掉强调/标签，`<strong>83</strong> real techniques`、`**83 个**` 才能被上面的模式看到。
EMPHASIS = re.compile(r"</?[A-Za-z][^>]*>|\*\*|`")
# 「N 个技法工具触发 must_ask_user」是**另一个量**（registry 减去 PREFLIGHT_EXEMPT_TOOLS），
# 不是工具总数——单独算、单独断言，好过打 ignore 标记让它继续陈旧下去。
GATED_PROSE = re.compile(r"(\d+)\s*个技法工具触发")
IGNORE_COUNT = "<!-- docs-sync:ignore-count -->"

COUNT_DOCS = [
    "README.md",
    "README_EN.md",
    "AGENTS.md",
    "CLAUDE.md",
    "manifest.json",
    "skills/horosa-agent/SKILL.md",
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    "docs/assets/banner.svg",
    # v0.33.0 批 III-5 盲区修补：examples/ 客户端文档与 .agents 镜像也写工具数——此前不在扫描面，
    # 计数漂移在这两处永不报警（claude-code.md 的门面数就这样陈旧了两个版本）。
    "horosa-skill/examples/clients/codex.md",
    "horosa-skill/examples/clients/codex-config.toml",
    "horosa-skill/examples/clients/claude-code.md",
    ".agents/skills/horosa-agent/SKILL.md",
]


def check_tool_counts() -> None:
    expected = len(TOOL_DEFINITIONS)
    for rel in COUNT_DOCS:
        path = ROOT / rel
        if not path.exists():
            continue
        for lineno, raw_line in enumerate(read(path).splitlines(), 1):
            if IGNORE_COUNT in raw_line:
                continue
            line = EMPHASIS.sub("", raw_line)
            badge = COUNT_BADGE.search(raw_line)
            if badge and int(badge.group(2)) != expected:
                err(f"{rel}:{lineno}: {badge.group(1)} badge says {badge.group(2)}, registry has {expected}")
            # alt lives *inside* a tag, so it must be read before EMPHASIS strips tags away
            alt = COUNT_ALT.search(raw_line)
            # a badge and its own alt disagreeing on one line is always a bug, whatever the registry says
            if badge and alt and badge.group(2) != alt.group(1):
                err(f"{rel}:{lineno}: badge {badge.group(2)} contradicts alt {alt.group(1)} on the same line")
            if alt and int(alt.group(1)) != expected:
                err(f"{rel}:{lineno}: alt says {alt.group(1)} tools, registry has {expected}")
            gated = GATED_PROSE.search(line)
            if gated:
                if int(gated.group(1)) != expected_gated():
                    err(
                        f"{rel}:{lineno}: claims {gated.group(1)} gated tools, "
                        f"registry minus PREFLIGHT_EXEMPT_TOOLS is {expected_gated()}"
                    )
                continue  # a gated-count line is not a total-count line
            for a, b in COUNT_SELFCHECK.findall(line):
                if int(a) != expected or int(b) != expected:
                    err(f"{rel}:{lineno}: self-check row says {a} / {b}, registry has {expected}")
            phrase = [(c, "技法") for c in COUNT_PHRASE_ZH.findall(line)]
            for count, _noun in COUNT_PROSE.findall(line) + COUNT_PROSE_EN.findall(line) + phrase:
                if int(count) != expected:
                    err(
                        f"{rel}:{lineno}: prose claims {count} tools, registry has {expected} "
                        f"(add {IGNORE_COUNT} if this line is a frozen historical record)"
                    )
    check_server_instructions()


def expected_gated() -> int:
    from horosa_skill.agent_guidance import PREFLIGHT_EXEMPT_TOOLS

    return len(TOOL_DEFINITIONS) - len(PREFLIGHT_EXEMPT_TOOLS)


def check_server_instructions() -> None:
    """`_SERVER_INSTRUCTIONS` ships to every MCP client and had no guard at all."""
    from horosa_skill.surfaces.mcp_server import _SERVER_INSTRUCTIONS

    expected = len(TOOL_DEFINITIONS)
    for count in re.findall(r"\((\d+)\s*tools?\)|instead of (\d+)", _SERVER_INSTRUCTIONS):
        got = count[0] or count[1]
        if int(got) != expected:
            err(f"mcp_server._SERVER_INSTRUCTIONS: claims {got} tools, registry has {expected}")


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
    # metadata.version 锁步（v0.33.0 批 III-5 盲区修补）：SKILL frontmatter 版本曾滞留 0.28.0
    # 两个发布无人察觉——现在与 pyproject 版本锁死。
    skill_path = ROOT / "skills/horosa-agent/SKILL.md"
    if skill_path.exists():
        m = re.search(r'version:\s*"?([0-9.]+)"?', read(skill_path).split("\n---", 2)[0])
        pkg_version = expected_version()
        if not m:
            err("skills/horosa-agent/SKILL.md: frontmatter missing metadata.version")
        elif m.group(1) != pkg_version:
            err(f"skills/horosa-agent/SKILL.md: metadata.version {m.group(1)} != package {pkg_version}")


def main() -> None:
    version = expected_version()
    check_versions(version)
    check_tool_coverage()
    check_test_count_consistency()
    check_test_count_is_real()
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
