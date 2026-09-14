"""Unit tests for the docs-sync tool-count checks (scripts/verify_docs_sync.py).

Why these exist: before v0.26.0 the count assertion was a single regex, `badge/tools-(\\d+)-`. The
English README happened to phrase things that way and was guarded; the Chinese README used
`badge/技法-83-` and drifted to 83 while the registry held 89 — with `alt="89 tools"` sitting on the
very same line. Six more stale claims hid in prose, in manifest.json, in banner.svg, and — worst —
twice in `_SERVER_INSTRUCTIONS`, the blurb shipped to every MCP client, which no guard read at all.

The bug was never the number. It was that the guard's reach was decided by an accident of phrasing.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PKG / "src"))
_SCRIPT = _PKG / "scripts" / "verify_docs_sync.py"
_spec = importlib.util.spec_from_file_location("verify_docs_sync", _SCRIPT)
docs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(docs)

from horosa_skill.engine.registry import TOOL_DEFINITIONS  # noqa: E402

N = len(TOOL_DEFINITIONS)


def _scan(line: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str = "README.md") -> list[str]:
    """Run check_tool_counts over a one-line doc and return the errors it raised."""
    (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / name).write_text(line + "\n", encoding="utf-8")
    errors: list[str] = []
    monkeypatch.setattr(docs, "ROOT", tmp_path)
    monkeypatch.setattr(docs, "COUNT_DOCS", [name])
    monkeypatch.setattr(docs, "err", errors.append)
    monkeypatch.setattr(docs, "check_server_instructions", lambda: None)
    docs.check_tool_counts()
    return errors


# --- the literal escape case ---------------------------------------------------------------------


def test_chinese_badge_label_is_checked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bad = f'<img src="https://img.shields.io/badge/技法-{N - 6}-1d4ed8?style=for-the-badge" />'
    assert _scan(bad, tmp_path, monkeypatch), "the 技法 badge label must be guarded, not just `tools`"
    good = f'<img src="https://img.shields.io/badge/技法-{N}-1d4ed8?style=for-the-badge" />'
    assert _scan(good, tmp_path, monkeypatch) == []


def test_badge_contradicting_its_own_alt_on_one_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """This exact shape shipped in v0.25.0: badge 83, alt 89, same line."""
    line = f'<img src="https://img.shields.io/badge/技法-{N - 6}-x" alt="{N} tools" />'
    errors = _scan(line, tmp_path, monkeypatch)
    assert any("contradicts alt" in e for e in errors)


# --- forms that escaped the old regex ------------------------------------------------------------


@pytest.mark.parametrize(
    "template",
    [
        "| 🌌 **{n} 技法一次装齐** |",
        "本地进程 · {n} 工具 · 澄清闸",
        "Local-first Horosa: {n} real technique tools over MCP",
        "exposes {n} real 术数/占星 techniques —",
        "本仓把星阙（Horosa）的 {n} 个术数/占星技法打包成",
        "<strong>{n}</strong> real techniques on your own machine",
        "| 🧰 可调用工具 | {n} / {n} `ok=true` |",
        "| Local memory | `{n} / {n}` writes |",
        # .claude-plugin/marketplace.json sat at 97 through 106: `local` instead of `real`, noun 20 chars later
        '"description": "{n} local Horosa (星阙) technique tools over MCP + the horosa-agent skill"',
    ],
)
def test_stale_count_forms_are_caught(template: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _scan(template.format(n=N - 6), tmp_path, monkeypatch), f"stale count not caught in: {template}"
    assert _scan(template.format(n=N), tmp_path, monkeypatch) == [], f"false positive on correct count: {template}"


# --- precision: things that must NOT be flagged ---------------------------------------------------


def test_small_unrelated_counts_are_not_flagged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`约 9 个门面工具` is a real, different quantity — a looser regex would false-positive here."""
    line = "上下文预算受限的客户端可设 HOROSA_MCP_COMPACT=1，只暴露约 9 个门面工具，澄清闸照常生效。"
    assert _scan(line, tmp_path, monkeypatch) == []


def test_gated_tool_count_is_checked_against_its_own_quantity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`N 个技法工具触发 must_ask_user` is registry-minus-exempt, not the total — and drifted to 67."""
    gated = docs.expected_gated()
    assert gated != N, "this test is meaningless if every tool is gated"
    assert _scan(f"| {gated - 14} 个技法工具触发 `must_ask_user=true` |", tmp_path, monkeypatch)
    assert _scan(f"| {gated} 个技法工具触发 `must_ask_user=true` |", tmp_path, monkeypatch) == []
    assert _scan(f"| {N} 个技法工具触发 `must_ask_user=true` |", tmp_path, monkeypatch), (
        "the gated row must not silently accept the *total* tool count"
    )


def test_ignore_marker_exempts_a_frozen_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    line = f"| 🧰 可调用工具 | {N - 6} / {N - 6} `ok=true` | {docs.IGNORE_COUNT}"
    assert _scan(line, tmp_path, monkeypatch) == []


# --- the blurb that ships to every MCP client -----------------------------------------------------


def test_server_instructions_count_is_guarded() -> None:
    """No guard read _SERVER_INSTRUCTIONS before v0.26.0; it said 83 twice while the registry had 89."""
    errors: list[str] = []
    original = docs.err
    docs.err = errors.append
    try:
        docs.check_server_instructions()
    finally:
        docs.err = original
    assert errors == [], f"_SERVER_INSTRUCTIONS is out of sync with the registry: {errors}"


def test_server_instructions_check_actually_fires(monkeypatch: pytest.MonkeyPatch) -> None:
    import horosa_skill.surfaces.mcp_server as mcp

    monkeypatch.setattr(mcp, "_SERVER_INSTRUCTIONS", f"WHAT IT COVERS ({N - 6} tools)\ninstead of {N - 6}\n")
    errors: list[str] = []
    monkeypatch.setattr(docs, "err", errors.append)
    docs.check_server_instructions()
    assert len(errors) == 2, "both the '(N tools)' and 'instead of N' forms must be checked"


# --- tool envelope 版本锁步（v0.36.0 A1）--------------------------------------------------------


def test_envelope_schema_version_lockstep_fires_on_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """common.py 的注释多年宣称 verify_docs_sync 核对 envelope 版本，实际没有——文档 0.6.3 vs 代码 0.7.0
    漂了两个版本无人察觉。负向对照：文档写错版本必须报错；写对必须静默。"""
    from horosa_skill.schemas.common import TOOL_ENVELOPE_SCHEMA_VERSION

    (tmp_path / "docs").mkdir()
    doc = tmp_path / "docs" / "DATA_CONTRACTS.md"
    monkeypatch.setattr(docs, "ROOT", tmp_path)

    doc.write_text("## 版本面\n\n- tool envelope：`0.0.1`\n", encoding="utf-8")
    errors: list[str] = []
    monkeypatch.setattr(docs, "err", errors.append)
    docs.check_envelope_schema_version()
    assert errors and "0.0.1" in errors[0] and TOOL_ENVELOPE_SCHEMA_VERSION in errors[0]

    doc.write_text(f"## 版本面\n\n- tool envelope：`{TOOL_ENVELOPE_SCHEMA_VERSION}`（说明）\n", encoding="utf-8")
    errors.clear()
    docs.check_envelope_schema_version()
    assert errors == []


# --- shipped artifacts the prose denies (v0.38.0 B0) ---------------------------------------------


def _docker_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, zh: str, en: str, dockerfile: bool) -> list[str]:
    (tmp_path / "horosa-skill").mkdir(exist_ok=True)
    dockerfile_path = tmp_path / "horosa-skill" / "Dockerfile"
    if dockerfile:
        dockerfile_path.write_text("FROM python:3.12-slim\n", encoding="utf-8")
    elif dockerfile_path.exists():
        dockerfile_path.unlink()
    (tmp_path / "README.md").write_text(zh + "\n", encoding="utf-8")
    (tmp_path / "README_EN.md").write_text(en + "\n", encoding="utf-8")
    errors: list[str] = []
    monkeypatch.setattr(docs, "ROOT", tmp_path)
    monkeypatch.setattr(docs, "err", errors.append)
    docs.check_docker_claims()
    return errors


def test_readme_denying_a_tracked_dockerfile_is_caught(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    denial = _docker_errors(tmp_path, monkeypatch, "仓库暂不提供 Dockerfile。", "No Dockerfile is shipped yet.", dockerfile=True)
    assert len(denial) == 4, denial  # one denial + one missing mention per README
    honest = _docker_errors(
        tmp_path, monkeypatch,
        "仓库附带实验性的 `horosa-skill/Dockerfile`。", "An experimental `horosa-skill/Dockerfile` ships.", dockerfile=True,
    )
    assert honest == []
    # without a Dockerfile in the tree there is nothing to deny — the old sentence would be true
    assert _docker_errors(tmp_path, monkeypatch, "仓库暂不提供 Dockerfile。", "No Dockerfile is shipped yet.", dockerfile=False) == []


# --- pinned zero-install commands (v0.38.0 B3) ----------------------------------------------------


def _pinned_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str) -> list[str]:
    (tmp_path / "README.md").write_text(text + "\n", encoding="utf-8")
    errors: list[str] = []
    monkeypatch.setattr(docs, "ROOT", tmp_path)
    monkeypatch.setattr(docs, "PINNED_DOCS", ["README.md"])
    monkeypatch.setattr(docs, "err", errors.append)
    docs.check_pinned_install_commands("0.38.0")
    return errors


@pytest.mark.parametrize(
    "template",
    [
        'uvx --from "git+https://github.com/o/horosa-skill@v{v}#subdirectory=horosa-skill" horosa-skill install',
        'uvx --from "https://github.com/o/r/releases/download/v{v}/horosa_skill-{v}-py3-none-any.whl" horosa-skill serve',
        '"identifier": "https://github.com/o/r/releases/download/v{v}/horosa-skill-{v}.mcpb"',
    ],
)
def test_pinned_install_commands_drift_is_caught(template: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _pinned_errors(tmp_path, monkeypatch, template.format(v="0.0.1")), template
    assert _pinned_errors(tmp_path, monkeypatch, template.format(v="0.38.0")) == [], template
    frozen = template.format(v="0.0.1") + " " + docs.IGNORE_VERSION
    assert _pinned_errors(tmp_path, monkeypatch, frozen) == []


# --- README platform table ↔ contracts/release_platforms.json (v0.38.0 A3) ------------------------


def _platform_table_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rows: str) -> list[str]:
    (tmp_path / "horosa-skill" / "contracts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "horosa-skill" / "contracts" / "release_platforms.json").write_text(json.dumps({
        "platforms": {"darwin-arm64": {}, "win32-x64": {}}, "aliases": {"win32-arm64": {}}, "unsupported": {"darwin-x64": "", "linux-x64": ""}}), encoding="utf-8")
    (tmp_path / "README.md").write_text(rows, encoding="utf-8")
    (tmp_path / "README_EN.md").write_text(rows, encoding="utf-8")
    errors: list[str] = []
    monkeypatch.setattr(docs, "ROOT", tmp_path)
    monkeypatch.setattr(docs, "PKG", tmp_path / "horosa-skill")
    monkeypatch.setattr(docs, "err", errors.append)
    docs.check_platform_table()
    return errors


_ROWS = "| 平台 | 离线 runtime | 说明 |\n| :-- | :-- | :-- |\n| macOS arm64 | ✅ |  |\n| Windows x64 | ✅ |  |\n| Windows ARM（骁龙本） | ✅ |  |\n| Linux | ⚠️ |  |\n| Intel Mac | ❌ |  |\n"


def test_platform_table_row_missing_for_a_contracted_platform_is_caught(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import json  # noqa: F811 - local import keeps the helper self-contained

    assert _platform_table_errors(tmp_path, monkeypatch, _ROWS) == []
    without_arm = _ROWS.replace("| Windows ARM（骁龙本） | ✅ |  |\n", "")
    errors = _platform_table_errors(tmp_path, monkeypatch, without_arm)
    assert len(errors) == 2 and all("Windows ARM" in e for e in errors)


# --- thin agent mirrors (v0.38.0 B5) -------------------------------------------------------------

_GOOD_MIRROR = (
    "# Horosa\n"
    "Policy: [SKILL](./skills/horosa-agent/SKILL.md)\n"
    "Gate: agent_guidance.required -> agent_confirmed_settings; read export_snapshot only.\n"
    "Onboard: `horosa-skill setup --client gemini`\n"
    "Compact surface: call techniques via horosa_tool_run(tool_name=…).\n"
)


def _mirror_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, files: dict[str, str], *, only: bool = True) -> list[str]:
    for rel, text in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    errors: list[str] = []
    monkeypatch.setattr(docs, "ROOT", tmp_path)
    monkeypatch.setattr(docs, "err", errors.append)
    if only:
        monkeypatch.setattr(docs, "AGENT_MIRRORS", {rel: docs.AGENT_MIRRORS[rel] for rel in files})
    docs.check_agent_mirrors()
    return errors


def test_agent_mirror_that_meets_the_contract_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _mirror_errors(tmp_path, monkeypatch, {"GEMINI.md": _GOOD_MIRROR}) == []


def test_agent_mirror_that_grew_fat_is_caught(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fat = _GOOD_MIRROR + "".join(f"rule {i}\n" for i in range(40))
    errors = _mirror_errors(tmp_path, monkeypatch, {"GEMINI.md": fat})
    assert any("lines >" in e for e in errors), errors


@pytest.mark.parametrize("dropped", ["agent_confirmed_settings", "agent_guidance.required", "export_snapshot", "setup --client", "horosa_tool_run"])
def test_agent_mirror_missing_a_contract_word_is_caught(dropped: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    errors = _mirror_errors(tmp_path, monkeypatch, {"GEMINI.md": _GOOD_MIRROR.replace(dropped, "…")})
    assert any(dropped in e for e in errors), errors


def test_agent_mirror_without_the_policy_pointer_is_caught(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    errors = _mirror_errors(tmp_path, monkeypatch, {"GEMINI.md": _GOOD_MIRROR.replace("./skills/horosa-agent/SKILL.md", "./README.md")})
    assert any("policy source" in e for e in errors), errors


def test_missing_agent_mirror_files_are_caught(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    errors = _mirror_errors(tmp_path, monkeypatch, {"GEMINI.md": _GOOD_MIRROR}, only=False)
    missing = {e.split(":")[0] for e in errors if "missing (" in e}
    assert missing == {".github/copilot-instructions.md", ".windsurf/rules/horosa-skill.md", ".clinerules/horosa-skill.md"}


def test_agent_mirror_tool_count_is_locked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _scan(f"Horosa ships {N} real techniques as a local MCP server.", tmp_path, monkeypatch, name="GEMINI.md") == []
    stale = _scan(f"Horosa ships {N - 1} real techniques as a local MCP server.", tmp_path, monkeypatch, name="GEMINI.md")
    assert stale, "a stale technique count in a mirror must be flagged"


def test_real_agent_mirrors_pass() -> None:
    errors: list[str] = []
    original = docs.err
    docs.err = errors.append
    try:
        docs.check_agent_mirrors()
    finally:
        docs.err = original
    assert errors == []


# ---------------------------------------------------------------- v0.38.1 B2：C2 / C11 / C12 / C13 / C17 / C21


def _errors_of(check, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, files: dict[str, str]) -> list[str]:
    for rel, text in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    errors: list[str] = []
    monkeypatch.setattr(docs, "ROOT", tmp_path)
    monkeypatch.setattr(docs, "err", errors.append)
    check()
    return errors


def test_pypi_install_claims_are_caught_unless_marked_not_live() -> None:
    assert docs.pypi_claim_errors("README.md", "手工起也行：`pip install horosa-skill` 后 serve") , "旧 README 的这行必须红"
    assert docs.pypi_claim_errors("README.md", "```\nuvx horosa-skill serve --transport stdio\n```")
    assert docs.pypi_claim_errors("README.md", 'uvx --from "https://x/horosa_skill-0.38.0-py3-none-any.whl" horosa-skill serve') == []
    assert docs.pypi_claim_errors("README.md", 'pip install "https://x/horosa_skill-0.38.0-py3-none-any.whl"') == []
    assert docs.pypi_claim_errors("README.md", "> PyPI 通道（`uvx horosa-skill …`）已就绪但暂未开通") == []
    assert docs.pypi_claim_errors("README.md", "The PyPI channel (`uvx horosa-skill …`) is wired but not yet live") == []
    assert docs.pypi_claim_errors("README.md", "run `uvx horosa-skill-other` or uvx horosa-skillet") == []


def test_real_docs_carry_no_pypi_install_claims() -> None:
    errors: list[str] = []
    original = docs.err
    docs.err = errors.append
    try:
        docs.check_no_pypi_install_claims()
    finally:
        docs.err = original
    assert errors == []


def test_connector_rows_must_name_the_oauth_gateway(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    old_row = "| 🔶 **ChatGPT / claude.ai 远程连接器** | streamable-http | 同上，再套一层 HTTPS 反代 | 全量 116 | 需要你自己的公网 HTTPS URL + 令牌 |\n"
    errors = _errors_of(docs.check_client_matrix_connectors, tmp_path, monkeypatch, {"README.md": old_row})
    assert any("网关" in e for e in errors) and any("OAuth" in e for e in errors), errors
    good = "| 🔶 **ChatGPT / claude.ai 远程连接器** | streamable-http | 终结 OAuth 的 HTTPS 网关 | 全量 116 | 说明 |\n"
    assert _errors_of(docs.check_client_matrix_connectors, tmp_path, monkeypatch, {"README.md": good}) == []
    assert _errors_of(docs.check_client_matrix_connectors, tmp_path, monkeypatch, {"README.md": "no table\n"})


def test_entry_docs_need_a_resolving_pointer_and_the_contract_words(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "skills" / "horosa-agent").mkdir(parents=True)
    (tmp_path / "skills" / "horosa-agent" / "SKILL.md").write_text("policy", encoding="utf-8")
    body = " ".join(docs.AGENT_MIRROR_KEYWORDS)
    monkeypatch.setattr(docs, "AGENT_ENTRY_DOCS", {".agents/skills/horosa-agent/SKILL.md": "../../../skills/horosa-agent/SKILL.md"})
    # 今天之前的指针：../../../horosa-skill/skills/… 不存在 → 必红
    stale = f"[SKILL](../../../horosa-skill/skills/horosa-agent/SKILL.md) {body}"
    errors = _errors_of(docs.check_agent_entry_docs, tmp_path, monkeypatch, {".agents/skills/horosa-agent/SKILL.md": stale})
    assert any("policy source" in e for e in errors), errors
    good = f"[SKILL](../../../skills/horosa-agent/SKILL.md) {body}"
    assert _errors_of(docs.check_agent_entry_docs, tmp_path, monkeypatch, {".agents/skills/horosa-agent/SKILL.md": good}) == []
    no_tool_run = good.replace("horosa_tool_run", "…")
    errors = _errors_of(docs.check_agent_entry_docs, tmp_path, monkeypatch, {".agents/skills/horosa-agent/SKILL.md": no_tool_run})
    assert any("horosa_tool_run" in e for e in errors)


def test_real_entry_docs_pass() -> None:
    errors: list[str] = []
    original = docs.err
    docs.err = errors.append
    try:
        docs.check_agent_entry_docs()
        docs.check_mirror_count_claims()
        docs.check_client_matrix_connectors()
        docs.check_client_example_configs()
    finally:
        docs.err = original
    assert errors == []


def test_mirror_count_claim_is_locked_to_the_tables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    expected = len(docs.AGENT_MIRRORS) + len(docs.AGENT_ENTRY_DOCS)
    assert _errors_of(docs.check_mirror_count_claims, tmp_path, monkeypatch, {"README.md": f"仓根另带 {expected} 份薄镜像"}) == []
    assert _errors_of(docs.check_mirror_count_claims, tmp_path, monkeypatch, {"README.md": "仓根另带四份薄镜像"}), "旧写法（汉字数词）必红"
    assert _errors_of(docs.check_mirror_count_claims, tmp_path, monkeypatch, {"README_EN.md": f"carries {expected + 1} thin mirrors"})


def test_client_example_config_must_not_carry_a_bare_uv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rel = "horosa-skill/examples/clients/claude_desktop_config.json"
    old = json.dumps({"mcpServers": {"horosa": {"command": "uv", "args": ["run"], "cwd": "<PATH_TO_REPO>/horosa-skill"}}})
    errors = _errors_of(docs.check_client_example_configs, tmp_path, monkeypatch, {rel: old})
    assert any("bare `uv`" in e for e in errors) and any("setup --client claude-desktop" in e for e in errors), errors
    good = json.dumps({"_comment": "use setup --client claude-desktop", "mcpServers": {"horosa": {"command": "<ABSOLUTE PATH TO uv>", "args": []}}})
    assert _errors_of(docs.check_client_example_configs, tmp_path, monkeypatch, {rel: good}) == []
