"""Install the `horosa-agent` skill into an AI client's skills directory (v0.41.0).

🔴 Why: `setup` used to write only the MCP config. A user who installed from the wheel (no checkout) then had an agent
that could call 120 tools but had never read the clarify-before-call gate, the export-snapshot reading contract or
"never hand-calculate" — those live in `skills/horosa-agent/SKILL.md`, which only reached agents that opened this repo.
Most clients now read Agent Skills from a fixed user-level folder (`~/.agents/skills` is the shared one), so `setup`
copies the packaged bundle there (or into the client's own folder when it does not read the shared one).

Rules for an existing `<skills_dir>/horosa-agent`:
- symlink → left alone (another tool manages it, e.g. `npx skills add` links into agent folders);
- carries our marker → replaced when outdated; files the user edited are kept as `horosa-agent.horosa-bak` first;
- no marker but byte-identical to the bundle → adopted (marker written);
- no marker and different → left alone and reported (`foreign`): it is somebody's own skill with the same name.

The bundle is a generated copy of `skills/horosa-agent` (scripts/gen_agent_mirrors.py; docs-sync checks drift).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from horosa_skill import __version__
from horosa_skill.errors import bilingual

SKILL_NAME = "horosa-agent"
MARKER_NAME = ".horosa-skill-install.json"
BACKUP_SUFFIX = ".horosa-bak"


def bundled_skill_root() -> Path:
    """The packaged copy inside the wheel / source tree."""
    root = Path(__file__).resolve().parent / "agent_skill" / SKILL_NAME
    if not (root / "SKILL.md").is_file():
        raise FileNotFoundError(bilingual(
            f"包内的 skill 副本缺失：{root}——在源码 checkout 里运行 `python scripts/gen_agent_mirrors.py`",
            f"packaged skill bundle missing: {root} — run `python scripts/gen_agent_mirrors.py` in a checkout",
        ))
    return root


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bundle_digests(root: Path | None = None) -> dict[str, str]:
    """{posix rel path: sha256} of every bundle file (the marker records exactly this)."""
    base = root or bundled_skill_root()
    return {
        path.relative_to(base).as_posix(): _digest(path.read_bytes())
        for path in sorted(base.rglob("*"))
        if path.is_file() and path.name != MARKER_NAME
    }


def _tree_digests(path: Path) -> dict[str, str]:
    return {
        item.relative_to(path).as_posix(): _digest(item.read_bytes())
        for item in sorted(path.rglob("*"))
        if item.is_file() and item.name != MARKER_NAME
    }


def _read_marker(dest: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads((dest / MARKER_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) and payload.get("installed_by") == "horosa-skill" else None


def skill_status(skills_dir: Path, *, bundle: dict[str, str] | None = None) -> dict[str, Any]:
    """State of `<skills_dir>/horosa-agent` relative to this package's bundle. Never writes."""
    dest = Path(skills_dir).expanduser() / SKILL_NAME
    expected = bundle if bundle is not None else bundle_digests()
    out: dict[str, Any] = {"path": str(dest), "bundle_version": __version__}
    if dest.is_symlink():
        out.update(state="symlink", target=os.readlink(dest))
        return out
    if not dest.exists():
        out["state"] = "absent"
        return out
    if not dest.is_dir():
        out["state"] = "foreign"
        out["note"] = "a file (not a folder) sits where the skill folder should be"
        return out
    marker = _read_marker(dest)
    current = _tree_digests(dest)
    if marker is None:
        out["state"] = "current_unmarked" if current == expected else "foreign"
        return out
    out["installed_version"] = marker.get("version")
    recorded = marker.get("files") if isinstance(marker.get("files"), dict) else {}
    if current != recorded:
        out["state"] = "modified"
        out["changed_files"] = sorted(k for k in set(current) | set(recorded) if current.get(k) != recorded.get(k))
    elif current == expected:
        out["state"] = "current"
    else:
        out["state"] = "outdated"
    return out


def _copy_bundle(source: Path, target: Path, digests: dict[str, str]) -> None:
    for rel in digests:
        (target / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / rel, target / rel)
    marker = {"installed_by": "horosa-skill", "version": __version__, "skill": SKILL_NAME, "files": digests}
    (target / MARKER_NAME).write_text(json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def install_skill(skills_dir: Path, *, dry_run: bool = False, source: Path | None = None) -> dict[str, Any]:
    """Install / refresh `<skills_dir>/horosa-agent`. Returns {path, state, action, …}; never raises on a foreign folder.

    `action` ∈ installed / updated / unchanged / adopted / skipped (+ `would_*` under dry_run).
    Replacement is staged: copy into a sibling temp folder, move the old folder aside, move the new one in, then delete
    the old one — an interrupted run leaves either the old or the new skill, never half of each.
    """
    base = source or bundled_skill_root()
    digests = bundle_digests(base)
    status = skill_status(skills_dir, bundle=digests)
    dest = Path(status["path"])
    state = status["state"]
    result = dict(status)
    if state in {"symlink", "foreign"}:
        result["action"] = "skipped"
        result["reason"] = (
            "managed by another tool (symlink) — update it there, e.g. `npx skills update`" if state == "symlink"
            else "a different folder with the same name already exists and was not written by horosa-skill — left untouched"
        )
        return result
    if state == "current":
        result["action"] = "unchanged"
        return result
    action = {"absent": "installed", "current_unmarked": "adopted", "outdated": "updated", "modified": "updated"}[state]
    if dry_run:
        result["action"] = f"would_{'install' if action == 'installed' else 'adopt' if action == 'adopted' else 'update'}"
        return result
    if state == "current_unmarked":
        marker = {"installed_by": "horosa-skill", "version": __version__, "skill": SKILL_NAME, "files": digests}
        (dest / MARKER_NAME).write_text(json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result.update(action=action, state="current")
        return result
    dest.parent.mkdir(parents=True, exist_ok=True)
    staging = dest.with_name(f"{SKILL_NAME}.horosa-tmp-{os.getpid()}")
    if staging.exists():
        shutil.rmtree(staging)
    _copy_bundle(base, staging, digests)
    retired: Path | None = None
    if state == "modified":
        # The user edited files we installed: keep their copy next to it instead of deleting their work.
        retired = dest.with_name(SKILL_NAME + BACKUP_SUFFIX)
        if retired.exists():
            shutil.rmtree(retired)
        result["backup"] = str(retired)
    elif state == "outdated":
        retired = dest.with_name(f"{SKILL_NAME}.horosa-old-{os.getpid()}")
    if retired is not None:
        dest.rename(retired)
    staging.rename(dest)
    if state == "outdated" and retired is not None:
        shutil.rmtree(retired, ignore_errors=True)
    result.update(action=action, state="current", installed_version=__version__)
    return result


# --------------------------------------------------------------------------------------------------------------------
# Where each `setup --client` target reads user-level skills. ONE folder per client: clients that read both the shared
# `~/.agents/skills` and their own folder would otherwise list the skill twice. [] = the client has no filesystem skills
# (the MCP server's own instructions still carry the gate). Facts + sources: contracts/third_party_facts.json.
# --------------------------------------------------------------------------------------------------------------------


def _os_name(os_name: str | None) -> str:
    if os_name is not None:
        return os_name
    return "nt" if os.name == "nt" else ("darwin" if sys.platform == "darwin" else "linux")


def default_home() -> Path:
    """The home the skill folders hang off (one seam, so tests never write into the maintainer's real ~/.agents)."""
    return Path.home()


def shared_skills_dir(*, home: Path | None = None) -> Path:
    """`~/.agents/skills` — the cross-vendor user-level folder (agentskills.io convention)."""
    return (Path(home) if home is not None else default_home()) / ".agents" / "skills"


def _override(env: Mapping[str, str], var: str, default: Path) -> Path:
    value = (env.get(var) or "").strip()
    return Path(value) if value else default


def _shared(_env: Mapping[str, str], home: Path) -> list[Path]:
    return [shared_skills_dir(home=home)]


def _own(var: str, folder: str) -> Callable[[Mapping[str, str], Path], list[Path]]:
    """`$VAR/skills`, else `~/<folder>/skills` — for clients that do NOT read the shared folder."""
    return lambda env, home: [_override(env, var, home / folder) / "skills"]


# Each client's ONE user-level folder (facts read 2026-10-12 from vendor docs / source; contracts/third_party_facts.json
# `clients-2026-10.skills`). 17 of the 25 read `~/.agents/skills`; installing a second copy into a client's own folder makes
# Cursor / VS Code / Codex list it twice and Droid treat the duplicate name as invalid configuration.
CLIENT_SKILL_DIRS: dict[str, Callable[[Mapping[str, str], Path], list[Path]]] = {
    # Claude Code reads only ~/.claude/skills ($CLAUDE_CONFIG_DIR/skills when set), never ~/.agents.
    "claude-code": lambda env, home: [_override(env, "CLAUDE_CONFIG_DIR", home / ".claude") / "skills"],
    # Chat / Cowork take skills only as a ZIP uploaded in the app; its Code tab is Claude Code (setup --client claude-code).
    "claude-desktop": lambda _env, _home: [],
    "cursor": _shared, "vscode": _shared, "codex": _shared, "windsurf": _shared, "cline": _shared, "zed": _shared,
    # Gemini CLI: GEMINI_CLI_HOME replaces the home for both of its folders.
    "gemini": lambda env, home: [shared_skills_dir(home=_override(env, "GEMINI_CLI_HOME", home))],
    "opencode": _shared, "goose": _shared, "junie": _shared, "qwen": _shared, "kimi": _shared, "amp": _shared,
    "warp": _shared, "droid": _shared, "augment": _shared, "deepcode": _shared,
    # Copilot CLI stops reading ~/.agents/skills when COPILOT_HOME is set.
    "copilot-cli": lambda env, home: [_override(env, "COPILOT_HOME", home / ".copilot") / "skills"] if (env.get("COPILOT_HOME") or "").strip()
    else [shared_skills_dir(home=home)],
    "dsh": lambda env, home: [Path(env["DSH_AGENTS_HOME"]) / "skills"] if (env.get("DSH_AGENTS_HOME") or "").strip()
    else [shared_skills_dir(home=home)],
    # Their own folders only (the shared one is undocumented, behind a project toggle, or unknown).
    "kiro": _own("KIRO_HOME", ".kiro"),
    "qoder": _own("QODER_CONFIG_DIR", ".qoder"),
    "codebuddy": _own("CODEBUDDY_CONFIG_DIR", ".codebuddy"),
    "trae": lambda _env, home: [home / ".trae" / "skills"] + ([home / ".trae-cn" / "skills"] if (home / ".trae-cn").is_dir() else []),
}


def export_zip(dest_dir: Path | None = None, *, source: Path | None = None) -> Path:
    """`<dest>/horosa-agent.zip` with `horosa-agent/…` at its root — the shape Claude Desktop's Customize > Skills upload takes."""
    import zipfile

    base = source or bundled_skill_root()
    dest_dir = dest_dir or (default_home() / ".horosa" / "skill-bundles")
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / f"{SKILL_NAME}.zip"
    tmp = target.with_name(target.name + ".horosa-tmp")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rel in bundle_digests(base):
            archive.write(base / rel, f"{SKILL_NAME}/{rel}")
    os.replace(tmp, target)
    return target


def duplicate_copies(installed_in: Path, *, home: Path | None = None) -> list[Path]:
    """Other copies of our skill that clients reading BOTH ~/.agents/skills and ~/.claude/skills would list twice."""
    home = Path(home) if home is not None else default_home()
    pair = {shared_skills_dir(home=home), home / ".claude" / "skills"}
    if Path(installed_in) not in pair:
        return []
    return [other / SKILL_NAME for other in pair - {Path(installed_in)} if (other / SKILL_NAME / "SKILL.md").is_file()]


def client_skill_dirs(
    client: str, *, os_name: str | None = None, env: Mapping[str, str] | None = None, home: Path | None = None,
) -> list[Path]:
    """User-level skills folder(s) `setup --client <client>` installs into. Pure; parametrised for cross-OS tests.

    Every folder is home-relative on all three OSes (the Windows docs give `%USERPROFILE%\\.<x>\\skills`), so `os_name`
    only exists for signature parity with `_client_config_locations`. Unknown client → the shared folder.
    """
    _os_name(os_name)
    env = os.environ if env is None else env
    home = Path(home) if home is not None else default_home()
    resolver = CLIENT_SKILL_DIRS.get(client)
    return resolver(env, home) if resolver is not None else [shared_skills_dir(home=home)]
