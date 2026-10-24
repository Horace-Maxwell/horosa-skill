"""`setup` 装 skill（v0.41.0）：horosa-agent skill 进客户端的 skills 目录。

**为什么旧检查抓不到**：`setup` 此前只写 MCP 配置，测试也只看配置。只装了 wheel 的用户，agent 能调 120 个工具，
却从没读过「先问后调 / 读快照 / 禁手算」——这些在 `skills/horosa-agent/SKILL.md`，只有打开本仓的 agent 才读得到；
而 wheel 里根本没有这份文件。本文件锁：wheel 内副本 = 策略源的渲染；安装的五种状态各走对的分支（尤其绝不覆盖
别人的同名目录、软链接、用户改过的文件不丢）；`setup` 装进假 HOME 且幂等；dry-run / --no-write 零写入。
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from horosa_skill import __version__, skill_install
from horosa_skill.surfaces.cli import app

PKG_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PKG_ROOT.parent
runner = CliRunner()

_spec = importlib.util.spec_from_file_location("gen_agent_mirrors", PKG_ROOT / "scripts" / "gen_agent_mirrors.py")
assert _spec is not None and _spec.loader is not None
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)


@pytest.fixture(autouse=True)
def _fake_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    home = tmp_path / "home"
    monkeypatch.setattr("horosa_skill.skill_install.default_home", lambda: home)
    return home


# ---------------------------------------------------------------- the packaged bundle


def test_packaged_bundle_matches_the_policy_source() -> None:
    assert gen.bundle_drift() == [], "wheel 里的 skill 副本与 skills/horosa-agent 不一致——重跑 scripts/gen_agent_mirrors.py"
    names = set(skill_install.bundle_digests())
    assert "SKILL.md" in names and any(n.startswith("references/") for n in names)


def test_bundle_drift_catches_an_edit_a_missing_file_and_a_stale_extra(tmp_path: Path) -> None:
    """负向对照：守卫真能抓三种漂移（改了策略源没重跑 / 漏拷 / 删了源文件留着旧副本）。"""
    root = tmp_path / "repo"
    shutil.copytree(REPO_ROOT / gen.SKILL_SOURCE_REL, root / gen.SKILL_SOURCE_REL)
    gen.write_bundle(root)
    assert gen.bundle_drift(root) == []
    (root / gen.SKILL_SOURCE_REL / "SKILL.md").write_text("changed\n", encoding="utf-8")
    assert gen.bundle_drift(root) == ["SKILL.md"]
    gen.write_bundle(root)
    (root / gen.SKILL_BUNDLE_REL / "references" / "reports.md").unlink()
    assert gen.bundle_drift(root) == ["references/reports.md"]
    gen.write_bundle(root)
    (root / gen.SKILL_BUNDLE_REL / "stale.md").write_text("x", encoding="utf-8")
    assert gen.bundle_drift(root) == ["stale.md"]


def test_links_out_of_the_skill_folder_become_github_urls() -> None:
    """装到 ~/.agents/skills 后没有仓库在旁边：`../../AGENTS.md` 会悬空。文件夹内的链接保持相对。"""
    rendered = gen.render_skill_file("see [A](../../AGENTS.md) and [r](./references/reports.md)", "SKILL.md")
    assert "](https://github.com/Horace-Maxwell/horosa-skill/blob/main/AGENTS.md)" in rendered
    assert "](./references/reports.md)" in rendered
    nested = gen.render_skill_file("[A](../../../AGENTS.md) [s](../SKILL.md)", "references/x.md")
    assert "](https://github.com/Horace-Maxwell/horosa-skill/blob/main/AGENTS.md)" in nested
    assert "](../SKILL.md)" in nested
    bundle = skill_install.bundled_skill_root()
    for path in bundle.rglob("*.md"):
        assert "](../../AGENTS.md)" not in path.read_text(encoding="utf-8"), path


# ---------------------------------------------------------------- install state machine


def test_fresh_install_writes_the_bundle_and_a_marker(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    result = skill_install.install_skill(skills)
    dest = skills / skill_install.SKILL_NAME
    assert result["action"] == "installed" and result["state"] == "current"
    assert (dest / "SKILL.md").read_bytes() == (skill_install.bundled_skill_root() / "SKILL.md").read_bytes()
    marker = json.loads((dest / skill_install.MARKER_NAME).read_text(encoding="utf-8"))
    assert marker["installed_by"] == "horosa-skill" and marker["version"] == __version__
    assert marker["files"] == skill_install.bundle_digests()
    assert skill_install.install_skill(skills)["action"] == "unchanged", "幂等：第二次不写"


def test_outdated_install_is_replaced_without_leftovers(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    skill_install.install_skill(skills)
    dest = skills / skill_install.SKILL_NAME
    (dest / "SKILL.md").write_bytes(b"old release\n")  # 字节写：Windows 文本模式会落成 CRLF，与下面按 LF 算的摘要对不上
    marker_path = dest / skill_install.MARKER_NAME
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    marker["files"]["SKILL.md"] = skill_install._digest(b"old release\n")
    marker["version"] = "0.0.1"
    marker_path.write_text(json.dumps(marker), encoding="utf-8")
    assert skill_install.skill_status(skills)["state"] == "outdated"
    result = skill_install.install_skill(skills)
    assert result["action"] == "updated" and "backup" not in result
    assert sorted(p.name for p in skills.iterdir()) == [skill_install.SKILL_NAME], "旧目录与临时目录都不许留下"
    assert skill_install.skill_status(skills)["state"] == "current"


def test_user_edits_are_backed_up_before_an_update(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    skill_install.install_skill(skills)
    (skills / skill_install.SKILL_NAME / "SKILL.md").write_text("my notes\n", encoding="utf-8")
    status = skill_install.skill_status(skills)
    assert status["state"] == "modified" and status["changed_files"] == ["SKILL.md"]
    result = skill_install.install_skill(skills)
    backup = Path(result["backup"])
    assert backup.name == "horosa-agent.horosa-bak"
    assert (backup / "SKILL.md").read_text(encoding="utf-8") == "my notes\n"
    assert skill_install.skill_status(skills)["state"] == "current"


def test_a_foreign_folder_with_the_same_name_is_never_touched(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    (skills / skill_install.SKILL_NAME).mkdir(parents=True)
    (skills / skill_install.SKILL_NAME / "SKILL.md").write_text("someone else's skill\n", encoding="utf-8")
    result = skill_install.install_skill(skills)
    assert result["action"] == "skipped" and result["state"] == "foreign"
    assert (skills / skill_install.SKILL_NAME / "SKILL.md").read_text(encoding="utf-8") == "someone else's skill\n"
    assert not (skills / skill_install.SKILL_NAME / skill_install.MARKER_NAME).exists()


def test_a_symlinked_skill_managed_by_another_tool_is_left_alone(tmp_path: Path) -> None:
    real = tmp_path / "elsewhere" / skill_install.SKILL_NAME
    real.mkdir(parents=True)
    (real / "SKILL.md").write_text("managed by npx skills\n", encoding="utf-8")
    skills = tmp_path / "skills"
    skills.mkdir()
    try:
        (skills / skill_install.SKILL_NAME).symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks not permitted on this host")
    result = skill_install.install_skill(skills)
    assert result["action"] == "skipped" and result["state"] == "symlink"
    assert (real / "SKILL.md").read_text(encoding="utf-8") == "managed by npx skills\n"


@pytest.mark.skipif(os.name != "nt", reason="directory junctions are Windows-only")
def test_a_junctioned_skill_on_windows_is_left_alone(tmp_path: Path) -> None:
    """Windows 普通用户建不了符号链接，别的工具常用目录联接；`is_symlink()` 对 junction 是 False（v0.43.1-dev）。
    取 bundle 原样内容当对方目录：不认 junction 时它会被判成 current_unmarked，marker 就写进了对方的真目录。"""
    import _winapi

    real = tmp_path / "elsewhere" / skill_install.SKILL_NAME
    shutil.copytree(skill_install.bundled_skill_root(), real)
    skills = tmp_path / "skills"
    skills.mkdir()
    _winapi.CreateJunction(str(real), str(skills / skill_install.SKILL_NAME))
    result = skill_install.install_skill(skills)
    assert result["action"] == "skipped" and result["state"] == "symlink", result
    assert not (real / skill_install.MARKER_NAME).exists(), "不许往别的工具的真目录里写 marker"


def test_an_identical_unmarked_copy_is_adopted_not_rewritten(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    shutil.copytree(skill_install.bundled_skill_root(), skills / skill_install.SKILL_NAME)
    assert skill_install.skill_status(skills)["state"] == "current_unmarked"
    assert skill_install.install_skill(skills)["action"] == "adopted"
    assert skill_install.skill_status(skills)["state"] == "current"


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    assert skill_install.install_skill(skills, dry_run=True)["action"] == "would_install"
    assert not skills.exists()


# ---------------------------------------------------------------- setup / client integration


def test_shared_folder_is_home_dot_agents_skills(_fake_home: Path) -> None:
    assert skill_install.shared_skills_dir() == _fake_home / ".agents" / "skills"
    assert skill_install.client_skill_dirs("claude-code") == [_fake_home / ".claude" / "skills"]
    assert skill_install.client_skill_dirs("claude-desktop") == [], "Claude Desktop 不读本机 skill 文件夹"


def test_client_skill_command_installs_into_the_shared_folder(_fake_home: Path) -> None:
    result = runner.invoke(app, ["client", "skill"])
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["targets"][0]["action"] == "installed"
    assert (_fake_home / ".agents" / "skills" / "horosa-agent" / "SKILL.md").is_file()
    again = json.loads(runner.invoke(app, ["client", "skill"]).stdout)
    assert again["targets"][0]["action"] == "unchanged"


def test_client_check_reports_skill_state_without_counting_it_as_a_problem(_fake_home: Path) -> None:
    payload = json.loads(runner.invoke(app, ["client", "check", "--client", "claude-code"]).stdout)
    skill = payload["clients"][0]["skill"]
    assert skill and skill[0]["state"] == "absent" and "client skill --client claude-code" in skill[0]["hint"]
    assert payload["problems"] == 0
