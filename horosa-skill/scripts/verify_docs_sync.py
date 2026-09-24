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
from horosa_skill.surfaces.mcp_server import (  # noqa: E402
    COMPACT_SURFACE_TOOL_COUNT,
    FACADE_TOOL_COUNT,
)

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

    # uv.lock 与 package-lock 同族：编辑安装的本包版本也写在锁文件里，发版忘了 `uv lock` 就会
    # 掉版（v0.33.0 前实测停在 0.32.0 且缺 tomlkit 锁定）。锁文件掉版不影响本地跑，却让复现
    # 构建装到旧元数据 —— 与 package-lock 那次一模一样的形状，所以一并纳入锁步。
    uv_lock = ROOT / "horosa-skill" / "uv.lock"
    if uv_lock.exists():
        m = re.search(r'name = "horosa-skill"\nversion = "([^"]+)"', read(uv_lock))
        if not m:
            err("uv.lock: 找不到 horosa-skill 自身的 version 条目")
        elif m.group(1) != version:
            err(f"uv.lock horosa-skill version = {m.group(1)} != {version}（发版前跑 `uv lock`）")

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
# marketplace.json phrased it "97 local Horosa (星阙) technique tools" — `local` instead of `real`, and the
# noun 20 chars later — and sat stale at 97 through 106 while this file listed it in COUNT_DOCS (v0.38.0).
# The reach of a count guard must not depend on which adjective a sentence happens to use.
COUNT_PROSE_EN = re.compile(r"(\d+)\s+(?:real|local)\s+[^,.;]{0,40}?\b(tools?|techniques?)\b")
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
# 「Cursor 全局约 40 个工具上限」「128 工具上限」说的是**别的客户端**的容量，不是我们的工具数。
# 这类行没法像 GATED_PROSE 那样「单独算、单独断言」——第三方的上限不是我们能派生的量。
# 用词判别比打 ignore 标记好：标记会连同行里真正的工具数一起放行，而这条只放行被 cap 词修饰的数。
CAP_WORDS = ("上限", "cap", "caps at", "limit", "静默丢弃", "drops the rest")

COUNT_DOCS = [
    "README.md",
    "README_EN.md",
    "AGENTS.md",
    "CLAUDE.md",
    "horosa-skill/manifest.json",
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
    # v0.38.0 B5：四份薄镜像也写工具数——它们是各家 agent 打开仓库第一眼看到的文件，数字不许陈旧。
    "GEMINI.md",
    ".github/copilot-instructions.md",
    ".windsurf/rules/horosa-skill.md",
    ".clinerules/horosa-skill.md",
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
            line_is_about_a_third_party_cap = any(word in line.lower() or word in line for word in CAP_WORDS)
            for count, _noun in COUNT_PROSE.findall(line) + COUNT_PROSE_EN.findall(line) + phrase:
                if line_is_about_a_third_party_cap and int(count) != expected:
                    continue
                if int(count) != expected:
                    err(
                        f"{rel}:{lineno}: prose claims {count} tools, registry has {expected} "
                        f"(add {IGNORE_COUNT} if this line is a frozen historical record)"
                    )
    check_server_instructions()
    check_full_surface_counts()


FULL_SURFACE_ROW = re.compile(r"(?:全量 |full \()(\d+)")
_PROBE_LITERAL = re.compile(r"\['tools'\] -ne \d+|probe\[\"tools\"\] == \d+")


def check_full_surface_counts() -> None:
    """README×2 客户端表的「全量 N / full (N)」与 ci.yml 的 stdio 探针都必须以 contracts/mcp_list_budget.json 的 full_tools 为准。

    v0.40.0 首推：四个新工具让全量面 116 → 120，README 表与 ci.yml 里写死的 116 谁都没改 —— CI 两个 job 在「wheel 真起 stdio」
    这一步红。数字只许有一个源；ci.yml 里不许再出现 `-ne <数字>` / `== <数字>` 形式的工具数断言。"""
    budget_path = PKG / "contracts" / "mcp_list_budget.json"
    try:
        full = int(json.loads(read(budget_path))["full_tools"])
    except Exception as exc:  # noqa: BLE001
        err(f"contracts/mcp_list_budget.json unreadable: {exc}")
        return
    for rel in ("README.md", "README_EN.md"):
        for lineno, line in enumerate(read(ROOT / rel).splitlines(), 1):
            for got in FULL_SURFACE_ROW.findall(line):
                if int(got) != full:
                    err(f"{rel}:{lineno}: full-surface row says {got} tools, contracts/mcp_list_budget.json full_tools is {full}")
    workflow = ROOT / ".github" / "workflows" / "ci.yml"
    if workflow.exists():
        text = read(workflow)
        for match in _PROBE_LITERAL.finditer(text):
            lineno = text.count("\n", 0, match.start()) + 1
            err(f".github/workflows/ci.yml:{lineno}: stdio probe asserts a literal tool count `{match.group(0)}` — read full_tools/compact_tools from contracts/mcp_list_budget.json instead")
        if "mcp_list_budget.json" not in text:
            err(".github/workflows/ci.yml: stdio probes no longer read contracts/mcp_list_budget.json")


def expected_gated() -> int:
    from horosa_skill.agent_guidance import PREFLIGHT_EXEMPT_TOOLS

    return len(TOOL_DEFINITIONS) - len(PREFLIGHT_EXEMPT_TOOLS)


def check_server_instructions() -> None:
    """`_SERVER_INSTRUCTIONS` ships to every MCP client and had no guard at all."""
    from horosa_skill.surfaces.mcp_server import _SERVER_INSTRUCTIONS

    # 🔴 客户端在 tools/list 里看到的是**门面 + 技法**，不是技法数。这条以前拿 len(TOOL_DEFINITIONS)
    # 比，于是 instructions 写 106 时是绿的 —— 而模型据此以为只有 106 个工具，实际收到 116 个。
    expected = FACADE_TOOL_COUNT + len(TOOL_DEFINITIONS)
    for count in re.findall(r"\((\d+)\s*tools?\)|instead of (\d+)", _SERVER_INSTRUCTIONS):
        got = count[0] or count[1]
        if int(got) != expected:
            err(
                f"mcp_server._SERVER_INSTRUCTIONS: claims {got} tools, default surface is {expected}"
                f" ({FACADE_TOOL_COUNT} facades + {len(TOOL_DEFINITIONS)} techniques)"
            )


# --- 3. stale "current: `X`" claims in docs -------------------------------------------------

def check_stale_claims(version: str) -> None:
    for path in sorted((ROOT / "docs").glob("*.md")):
        for got in re.findall(r"current: `(\d+\.\d+\.\d+)`", read(path)):
            if got != version:
                err(f"docs/{path.name}: stale 'current: `{got}`' claim (package is {version})")


# --- 3a. pinned zero-install commands -------------------------------------------------------
# README / SKILL / server.json / examples carry commands that pin a version inside a URL or a git ref:
#   uvx --from "git+https://…/horosa-skill@v0.37.0#subdirectory=horosa-skill" …
#   uvx --from "https://…/releases/download/v0.37.0/horosa_skill-0.37.0-py3-none-any.whl" …
#   https://…/releases/download/v0.37.0/horosa-skill-0.37.0.mcpb
# `check_versions` only walks JSON `version` keys, so these strings drifted silently once (v0.38.0 B3
# audit). A pinned command that names an older version sends the user to a release that lacks this
# code's contracts. `<!-- docs-sync:ignore-version -->` on the line freezes a deliberately historical one.

PINNED_DOCS = [
    "README.md", "README_EN.md", "docs/INSTALL_RESTRICTED_NETWORK.md",
    "skills/horosa-agent/SKILL.md", ".agents/skills/horosa-agent/SKILL.md", "server.json",
]
PIN_PATTERNS = (
    re.compile(r"horosa-skill@v(\d+\.\d+\.\d+)#"),
    re.compile(r"/v(\d+\.\d+\.\d+)/horosa_skill-(\d+\.\d+\.\d+)-py3-none-any\.whl"),
    re.compile(r"/v(\d+\.\d+\.\d+)/horosa-skill-(\d+\.\d+\.\d+)\.mcpb"),
)
IGNORE_VERSION = "<!-- docs-sync:ignore-version -->"


def check_pinned_install_commands(version: str) -> None:
    docs = [ROOT / rel for rel in PINNED_DOCS] + sorted((ROOT / "horosa-skill" / "examples" / "clients").glob("*.md"))
    for path in docs:
        if not path.exists():
            continue
        rel = path.relative_to(ROOT).as_posix()
        for lineno, line in enumerate(read(path).splitlines(), 1):
            if IGNORE_VERSION in line:
                continue
            for pattern in PIN_PATTERNS:
                for match in pattern.finditer(line):
                    stale = sorted({g for g in match.groups() if g and g != version})
                    if stale:
                        err(f"{rel}:{lineno}: pinned install command names v{stale[0]} but the package is {version} "
                            f"(add {IGNORE_VERSION} only for a frozen historical record)")


# --- 3b2. thin agent mirrors (v0.38.0 B5) --------------------------------------------------------
# Gemini CLI / GitHub Copilot / Windsurf / Cline each read a file of their own before they ever see SKILL.md.
# Those files must exist, stay thin (policy lives in SKILL.md), point at the policy source, and name the
# three contract words plus the one-command onboarding — otherwise an agent on that client starts with no gate.

AGENT_MIRRORS = {
    "GEMINI.md": "./skills/horosa-agent/SKILL.md",
    ".github/copilot-instructions.md": "../skills/horosa-agent/SKILL.md",
    ".windsurf/rules/horosa-skill.md": "../../skills/horosa-agent/SKILL.md",
    ".clinerules/horosa-skill.md": "../skills/horosa-agent/SKILL.md",
}
AGENT_MIRROR_MAX_LINES = 30
# v0.38.1 C13：精简面下技法不平铺，agent 必须知道 `horosa_tool_run` 才不会把「平铺名不在」读成「技法不存在」。
AGENT_MIRROR_KEYWORDS = ("agent_confirmed_settings", "agent_guidance.required", "export_snapshot", "setup --client", "horosa_tool_run")

# v0.38.1 C12：另两份入口文档（Cursor 规则 / Codex-agentskills 入口）。没有行数上限（.agents 那份是 agentskills.io
# 的完整入口，带 frontmatter），但同样必须指向策略源、指针必须**能解析**（它曾指向不存在的
# `horosa-skill/skills/horosa-agent/SKILL.md`），且带全部契约词。
AGENT_ENTRY_DOCS = {
    ".cursor/rules/horosa-skill.mdc": "skills/horosa-agent/SKILL.md",
    ".agents/skills/horosa-agent/SKILL.md": "../../../skills/horosa-agent/SKILL.md",
}
MIRROR_COUNT_CLAIMS = {"README.md": r"(\d+) 份薄镜像", "README_EN.md": r"(\d+) thin mirrors"}


def check_agent_entry_docs() -> None:
    for rel, pointer in AGENT_ENTRY_DOCS.items():
        path = ROOT / rel
        if not path.exists():
            err(f"{rel}: agent entry doc missing")
            continue
        text = read(path)
        if pointer not in text:
            err(f"{rel}: must name the policy source ({pointer})")
        elif not ((path.parent / pointer).exists() or (ROOT / pointer).exists()):
            err(f"{rel}: policy pointer `{pointer}` does not resolve to a file")
        for keyword in AGENT_MIRROR_KEYWORDS:
            if keyword not in text:
                err(f"{rel}: missing `{keyword}` — the gate, the reading contract, the onboarding command and the compact-surface call must be named")


def check_mirror_count_claims() -> None:
    """README 说「N 份薄镜像」，N 必须等于 AGENT_MIRRORS + AGENT_ENTRY_DOCS（曾写「四份」而实际有六份）。"""
    expected = len(AGENT_MIRRORS) + len(AGENT_ENTRY_DOCS)
    for rel, pattern in MIRROR_COUNT_CLAIMS.items():
        path = ROOT / rel
        if not path.exists():
            continue
        found = re.findall(pattern, read(path))
        if not found:
            err(f"{rel}: no thin-mirror count claim matching /{pattern}/ (write the digit, not a word)")
        for got in found:
            if int(got) != expected:
                err(f"{rel}: claims {got} thin mirrors, the repo carries {expected} (AGENT_MIRRORS + AGENT_ENTRY_DOCS)")


def check_agent_mirrors() -> None:
    for rel, pointer in AGENT_MIRRORS.items():
        path = ROOT / rel
        if not path.exists():
            err(f"{rel}: thin agent mirror missing (AGENTS.md §3 — every listed client gets one)")
            continue
        text = read(path)
        lines = len(text.rstrip("\n").splitlines())
        if lines > AGENT_MIRROR_MAX_LINES:
            err(f"{rel}: {lines} lines > {AGENT_MIRROR_MAX_LINES} — mirrors stay thin; policy lives in skills/horosa-agent/SKILL.md")
        if pointer not in text:
            err(f"{rel}: must link to the policy source ({pointer})")
        for keyword in AGENT_MIRROR_KEYWORDS:
            if keyword not in text:
                err(f"{rel}: missing `{keyword}` — the gate, the reading contract and the onboarding command must be named")


# --- 3c. README platform table ↔ contracts/release_platforms.json ---------------------------------
# The platform table is the first thing an Intel-Mac / Windows-on-ARM user reads. Its rows are locked to
# the contract (v0.38.0 A3): every shipped platform, alias and unsupported host must have a row, so the
# table cannot promise a payload the contract does not ship, nor stay silent about one it does.

PLATFORM_ROW_LABELS = {
    "darwin-arm64": "macOS arm64",
    "win32-x64": "Windows x64",
    "win32-arm64": "Windows ARM",
    "darwin-x64": "Intel Mac",
    "linux-x64": "Linux",
}


def check_platform_table() -> None:
    contract_path = PKG / "contracts" / "release_platforms.json"
    if not contract_path.exists():
        return
    contract = json.loads(read(contract_path))
    keys = list(contract.get("platforms", {})) + list(contract.get("aliases", {})) + list(contract.get("unsupported", {}))
    for rel in ("README.md", "README_EN.md"):
        path = ROOT / rel
        if not path.exists():
            continue
        rows = [line for line in read(path).splitlines() if line.startswith("| ")]
        for key in keys:
            label = PLATFORM_ROW_LABELS.get(key)
            if label is None:
                err(f"{rel}: contract platform `{key}` has no README row label in PLATFORM_ROW_LABELS")
                continue
            if not any(line.split("|")[1].strip().startswith(label) for line in rows if line.count("|") >= 3):
                err(f"{rel}: platform table has no row starting with `{label}` (contracts/release_platforms.json lists `{key}`)")


# --- 3b. shipped artifacts the prose denies ------------------------------------------------
# horosa-skill/Dockerfile + docker-compose.yml have been tracked since v0.3x while both READMEs kept
# saying "仓库暂不提供 Dockerfile / No Dockerfile is shipped yet" (v0.38.0 audit). A doc that denies a
# tracked file is worse than silence: an agent trusts it and never looks.

# --- 3d. PyPI is not open: no doc may hand the user `pip install horosa-skill` / bare `uvx horosa-skill` (v0.38.1 C2) ---
# 「PyPI 通道尚未开通」是当前事实：README 曾教 `pip install horosa-skill`（404）。提到未来形态可以，但整行必须带
# 「尚未开通 / not yet live」一类标记；命令形态一律要 wheel URL / git 直链 / `--from`。
PYPI_NOT_LIVE_MARKERS = ("未开通", "not yet live", "not open yet", "not yet open", "not open", "尚未上线", "暂缓")
PYPI_CLAIM_DOCS = (
    "README.md", "README_EN.md", "horosa-skill/README.md", "skills/horosa-agent/SKILL.md",
    ".agents/skills/horosa-agent/SKILL.md", "CLAUDE.md", "AGENTS.md",
)
_BARE_UVX = re.compile(r"(?:^|[`\s(])uvx horosa-skill(?=[\s`)]|$)")


def pypi_claim_errors(rel: str, text: str) -> list[str]:
    found: list[str] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if any(marker in line for marker in PYPI_NOT_LIVE_MARKERS):
            continue
        if "pip install horosa-skill" in line:
            found.append(f"{rel}:{lineno}: `pip install horosa-skill` points at PyPI, which is not open — use the release wheel URL")
        if _BARE_UVX.search(line) and "--from" not in line:
            found.append(f"{rel}:{lineno}: bare `uvx horosa-skill` needs PyPI — write `uvx --from \"<wheel URL>\" horosa-skill …`")
    return found


def check_no_pypi_install_claims() -> None:
    docs = [ROOT / rel for rel in PYPI_CLAIM_DOCS]
    docs += sorted((ROOT / "docs").glob("*.md")) + sorted((ROOT / "horosa-skill" / "examples" / "clients").glob("*.md"))
    for path in docs:
        if not path.exists():
            continue
        for problem in pypi_claim_errors(path.relative_to(ROOT).as_posix(), read(path)):
            err(problem)


# --- 3e. remote-connector rows must describe the OAuth gateway, not promise a static token (v0.38.1 C11) ---
CONNECTOR_ROWS = {"README.md": ("远程连接器", ("网关", "OAuth")), "README_EN.md": ("remote connectors", ("gateway", "OAuth"))}


def check_client_matrix_connectors() -> None:
    for rel, (marker, needles) in CONNECTOR_ROWS.items():
        path = ROOT / rel
        if not path.exists():
            continue
        rows = [line for line in read(path).splitlines() if line.startswith("|") and marker in line]
        if not rows:
            err(f"{rel}: client matrix has no `{marker}` row")
        for row in rows:
            for needle in needles:
                if needle not in row:
                    err(f"{rel}: the `{marker}` row must mention `{needle}` — claude.ai / ChatGPT connectors only speak OAuth; a static Bearer alone cannot connect")


# --- 3f. shipped example configs must not carry a bare `uv` command (v0.38.1 C17) ---
EXAMPLE_JSON_CONFIGS = ("horosa-skill/examples/clients/claude_desktop_config.json",)


def check_client_example_configs() -> None:
    for rel in EXAMPLE_JSON_CONFIGS:
        path = ROOT / rel
        if not path.exists():
            continue
        try:
            data = json.loads(read(path))
        except ValueError as exc:
            err(f"{rel}: not valid JSON ({exc})")
            continue
        for name, entry in (data.get("mcpServers") or {}).items():
            if str(entry.get("command")) in {"uv", "uvx"}:
                err(f"{rel}:{name}: bare `{entry.get('command')}` — GUI clients do not inherit the shell PATH; the example must show an absolute-path placeholder")
        if "setup --client claude-desktop" not in str(data.get("_comment", "")):
            err(f"{rel}: the example must point readers at `setup --client claude-desktop` (the generator writes real absolute paths)")


DOCKER_DENIALS = ("暂不提供 Dockerfile", "No Dockerfile is shipped")
DOCKER_MENTION = "horosa-skill/Dockerfile"


def check_docker_claims() -> None:
    if not (ROOT / "horosa-skill" / "Dockerfile").exists():
        return
    for rel in ("README.md", "README_EN.md"):
        path = ROOT / rel
        if not path.exists():
            continue
        text = read(path)
        for denial in DOCKER_DENIALS:
            if denial in text:
                err(f"{rel}: says '{denial}' but horosa-skill/Dockerfile is tracked")
        if DOCKER_MENTION not in text:
            err(f"{rel}: horosa-skill/Dockerfile is tracked but the README never names it")


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
        *[ROOT / rel for rel in AGENT_MIRRORS],
        *[ROOT / rel for rel in AGENT_ENTRY_DOCS],
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


def check_compact_surface_count() -> None:
    """README×2 写的「11 个门面工具 / 11 facades」必须等于 mcp_server.COMPACT_SURFACE_TOOL_COUNT。

    v0.36.0 之前 mcp_server 里的注释还写着「8 门面 + tool_run = 9 工具」——常量化 + 锁步，数字只准有一个源。
    """
    # 🔴 直接 import 常量，别正则源码：常量一改成派生式（`FACADE_TOOL_COUNT + 1`）正则就抓瞎，
    # 而「抓瞎」在这把守卫里表现为**报缺常量**，很容易被当成误报改掉正则而不是锚到源头。
    n = COMPACT_SURFACE_TOOL_COUNT
    for rel, patterns in {
        "README.md": [rf"{n}\s*个门面工具", rf"MCP 门面（{n}）"],
        "README_EN.md": [rf"\b{n} facades\b", rf"MCP facades \({n}\)"],
    }.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        for pat in patterns:
            if not re.search(pat, text):
                err(f"{rel} 未按 COMPACT_SURFACE_TOOL_COUNT={n} 写门面数（缺 /{pat}/）")
        stale = re.findall(r"(\d+)\s*个门面工具|\b(\d+) facades\b", text)
        for a, b in stale:
            val = a or b
            if val and int(val) != n:
                err(f"{rel} 门面数 {val} ≠ COMPACT_SURFACE_TOOL_COUNT={n}")



def knowledge_truth() -> dict[str, int]:
    """知识库计数的唯一真值：store 实际加载的 bundle（域）+ helpdoc 条目（手册 = 除八字断语库外的 helpdoc 域）。"""
    from horosa_skill.knowledge.store import load_knowledge_bundles

    bundles = load_knowledge_bundles()
    helpdoc = {k: b for k, b in bundles.items() if b.get("schema") == "horosa.knowledge.helpdoc.v1"}
    manuals = {k: b for k, b in helpdoc.items() if k != "bazi_pithy"}

    def entries(bundle: dict) -> int:
        return sum(len(cat.get("entries") or []) for cat in bundle.get("categories") or [])

    return {
        "domains": len(bundles),
        "manual_domains": len(manuals),
        "manual_entries": sum(entries(b) for b in manuals.values()),
        "total_entries": sum(entries(b) for b in helpdoc.values()),
    }


# (文件, 正则, 真值键…)：正则的每个捕获组按序对应一个真值键；每条正则至少命中一次（防措辞改了守卫就瞎）。
KNOWLEDGE_CLAIMS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("README.md", r"(\d+) 域知识库", ("domains",)),
    ("README.md", r"(\d+) 域方法论知识库", ("domains",)),
    ("README.md", r"\| (\d+) 域（hover 知识", ("domains",)),
    ("README.md", r"覆盖 (\d+) 域", ("domains",)),
    ("README.md", r"(\d+) 份技法操作手册", ("manual_domains",)),
    ("README.md", r"八字断语库[^共]{0,12}共 (\d+) 条", ("total_entries",)),
    ("README.md", r"📚 知识库 \| (\d+) 域；技法操作手册 (\d+) 条", ("domains", "manual_entries")),
    ("README_EN.md", r"(\d+) domains", ("domains",)),
    ("README_EN.md", r"(\d+)-domain knowledge base\*\* \((\d+) cited entries", ("domains", "total_entries")),
    ("README_EN.md", r"(\d+) manual entries", ("manual_entries",)),
    ("README_EN.md", r"(\d+) technique operation manuals", ("manual_domains",)),
    ("README_EN.md", r"bazi pithy corpus \((\d+) entries", ("total_entries",)),
    ("AGENTS.md", r"`knowledge_read`（(\d+) 域", ("domains",)),
    ("AGENTS.md", r"（(\d+) 域/(\d+) 条，逐条带出处", ("manual_domains", "manual_entries")),
    ("skills/horosa-agent/SKILL.md", r"`knowledge_read`（(\d+) 域", ("domains",)),
    ("skills/horosa-agent/SKILL.md", r"跨 (\d+) 域全文检索", ("domains",)),
)


def check_knowledge_counts() -> None:
    """知识库的域数 / 手册数 / 条目数必须等于 store 实际加载的数。

    v0.40.0 时同一件事在文档里有四个数：README 31 域与 30 域并存、SKILL.md 与 AGENTS.md 还写 24 域、条目数停在
    上游补条之前（235/408）——工具数、测试数都有真值守卫，知识库计数没有。
    """
    truth = knowledge_truth()
    for rel, pattern, keys in KNOWLEDGE_CLAIMS:
        found = re.findall(pattern, read(ROOT / rel))
        if not found:
            err(f"{rel}: 知识库计数措辞没找到（改了措辞就同步改 KNOWLEDGE_CLAIMS）: /{pattern}/")
            continue
        for match in found:
            values = match if isinstance(match, tuple) else (match,)
            for key, got in zip(keys, values):
                if int(got) != truth[key]:
                    err(f"{rel}: 知识库 {key} 写 {got}，store 实际 {truth[key]}（/{pattern}/）")


def check_root_manifest_version() -> None:
    """MCPB manifest 的 version 必须与包版本锁步（曾停在 0.32.0 两个版本无人察觉）。

    v0.37.0 起它住在 horosa-skill/ —— MCPB 的 bundle 根必须持有 pyproject.toml，
    `server.type: "uv"` 才解析得到依赖。"""
    init = (ROOT / "horosa-skill/src/horosa_skill/__init__.py").read_text(encoding="utf-8")
    m = re.search(r"__version__\s*=\s*[\"']([^\"']+)[\"']", init)
    manifest = json.loads((ROOT / "horosa-skill/manifest.json").read_text(encoding="utf-8"))
    if not m:
        err("__init__.py 读不到 __version__")
        return
    if manifest.get("version") != m.group(1):
        err(f"horosa-skill/manifest.json version={manifest.get('version')!r} ≠ 包版本 {m.group(1)!r}")


def check_envelope_schema_version() -> None:
    """docs/DATA_CONTRACTS.md 的「tool envelope：`X`」必须等于 `schemas/common.py::TOOL_ENVELOPE_SCHEMA_VERSION`。
    common.py 的注释一直宣称本脚本核对它，实际从未有此检查——文档停在 0.6.3、代码走到 0.7.0 两个版本无人察觉
    （v0.36.0 升 0.8.0 时才发现）。"""
    from horosa_skill.schemas.common import TOOL_ENVELOPE_SCHEMA_VERSION

    path = ROOT / "docs" / "DATA_CONTRACTS.md"
    if not path.exists():
        err("docs/DATA_CONTRACTS.md missing (tool envelope version has no documented home)")
        return
    match = re.search(r"tool envelope[：:]\s*`([0-9.]+)`", read(path))
    if not match:
        err("docs/DATA_CONTRACTS.md: 「tool envelope：`X`」版本行未找到（pattern drifted?）")
    elif match.group(1) != TOOL_ENVELOPE_SCHEMA_VERSION:
        err(
            f"docs/DATA_CONTRACTS.md: tool envelope {match.group(1)} != "
            f"schemas/common.py TOOL_ENVELOPE_SCHEMA_VERSION {TOOL_ENVELOPE_SCHEMA_VERSION}"
        )


def main() -> None:
    version = expected_version()
    check_versions(version)
    check_tool_coverage()
    check_test_count_consistency()
    check_test_count_is_real()
    check_stale_claims(version)
    check_pinned_install_commands(version)
    check_platform_table()
    check_docker_claims()
    check_agent_mirrors()
    check_agent_entry_docs()
    check_mirror_count_claims()
    check_no_pypi_install_claims()
    check_client_matrix_connectors()
    check_client_example_configs()
    check_links()
    check_conflict_markers()
    check_frontmatter()
    check_envelope_schema_version()
    check_compact_surface_count()
    check_knowledge_counts()
    check_root_manifest_version()
    if ERRORS:
        raise SystemExit("docs-sync: FAIL\n- " + "\n- ".join(ERRORS))
    print(f"docs-sync: ok (version {version}, {len(TOOL_DEFINITIONS)} tools, "
          "links/markers/frontmatter clean)")


if __name__ == "__main__":
    main()
