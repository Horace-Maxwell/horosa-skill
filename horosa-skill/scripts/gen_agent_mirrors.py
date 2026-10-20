#!/usr/bin/env python3
"""Render the thin agent mirrors from ONE template (v0.40.0 doc-currency institution).

Before this script the four thin mirrors (GEMINI.md, .github/copilot-instructions.md, .windsurf/rules/horosa-skill.md,
.clinerules/horosa-skill.md) were four hand-maintained copies of the same 25 lines that differed only in the client
name, the setup key, the relative pointer to the policy source and (Windsurf) a frontmatter block. Every rule change
had to be repeated four times by hand — and the 2026-09 Windsurf → Devin Desktop rename showed how a client fact can go
stale in one copy and not another. Now the text lives here once; the mirrors are build output.

    python scripts/gen_agent_mirrors.py            # (re)write the mirrors + the packaged skill bundle
    python scripts/gen_agent_mirrors.py --check    # exit 1 when any mirror differs from the render (docs-sync calls this)

The policy source stays `skills/horosa-agent/SKILL.md`; this template is its 30-second digest (AGENTS.md §3).
Per-client facts (display name, setup key, notes) are the ONLY thing that varies — add a client = add a row below.

Second output (v0.41.0): the **packaged skill bundle** `src/horosa_skill/agent_skill/horosa-agent/` — a copy of
`skills/horosa-agent/` (SKILL.md + references/) that ships inside the wheel, so `setup` can install the skill into a
client's skills directory on machines that only have the wheel (no checkout). `uv build --wheel` cannot reach `../skills`
from an sdist, hence a committed copy instead of a hatch force-include. The only transform: links that climb out of the
skill folder (`../../AGENTS.md`) become GitHub URLs, because the installed copy lives in `~/.agents/skills/` where
the relative link would dangle.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]

# rel path → (client display name, `setup --client` key, depth of the mirror below the repo root, frontmatter or "")
MIRRORS: dict[str, tuple[str, str, int, str]] = {
    "GEMINI.md": ("Gemini CLI", "gemini", 0, ""),
    ".github/copilot-instructions.md": ("GitHub Copilot (VS Code)", "vscode", 1, ""),
    # Devin Desktop (ex-Windsurf) still ships this legacy Cascade rules path; whether Devin Local reads it is unverified
    # (contracts/third_party_facts.json `windsurf.devin-desktop`). No blank line after the frontmatter: the thin-mirror cap is 30 lines.
    ".windsurf/rules/horosa-skill.md": ("Devin Desktop (formerly Windsurf; legacy Cascade rules file)", "windsurf", 2,
                                        "---\ntrigger: always_on\n---\n"),
    ".clinerules/horosa-skill.md": ("Cline", "cline", 1, ""),
}

TEMPLATE = """# Horosa Skill — rules for {client}

This repo ships Horosa (星阙): {techniques} real techniques (Western astrology, 八字, 紫微, 六壬, 奇门, 太乙, 六爻, 神数 …)
as a local-first MCP server + CLI. The **single policy source** is [skills/horosa-agent/SKILL.md]({prefix}skills/horosa-agent/SKILL.md);
maintainer law is [AGENTS.md]({prefix}AGENTS.md). This file is **generated** by `horosa-skill/scripts/gen_agent_mirrors.py` —
edit the template there, never this copy.

1. **Never hand-calculate** a technique (no formulas, no memorised tables, no web lookups). Every chart comes
   from a `horosa_*` MCP tool or the `horosa-skill` CLI.
2. **Clarify before calling.** A missing result-changing setting (time, place, timezone, gender, 流派 / house
   system / 起局方式) makes the tool refuse with `agent_guidance.required`. Ask the user with
   `details.agent_recovery.prompt_to_user`, then retry with `agent_confirmed_settings: true` +
   `clarification_notes` (or `defaults_accepted: true` only when the user explicitly accepts defaults).
   Never self-confirm, never switch tools to bypass the gate.
3. **Explain only from `export_snapshot.export_text` / `.sections`.** A missing section is "not returned",
   never a missing dependency (no MongoDB / 7897 / desktop app stories). Quote `data.technique_card` after
   every answer; `warnings` non-empty means the result is incomplete — say so.
4. No `horosa` tools in the list? One command registers everything:
   `horosa-skill setup --client {key}` (`uv run horosa-skill setup --client {key}` inside this checkout),
   then `horosa-skill doctor` for the machine-readable health report.
5. **Compact surface.** By default this client sees only the {compact} facade tools (`HOROSA_MCP_COMPACT=1`); every
   technique is still reachable by name through `horosa_tool_run(tool_name="qimen", …)` and the full list is the
   `horosa://catalog/techniques` resource — a missing flat `horosa_*` name does not mean the technique is missing.
6. Errors carry structured recovery: on `details.agent_recovery` relay `prompt_to_user` verbatim and stop; on
   `runtime.*` errors suggest `horosa-skill doctor --explain` (Linux / Intel Mac = gateway mode; Windows runtime root
   must be pure ASCII). Never retry by flipping a setting the user did not choose.
"""


def technique_count() -> int:
    sys.path.insert(0, str(ROOT / "horosa-skill" / "src"))
    from horosa_skill.engine.registry import TOOL_DEFINITIONS  # noqa: E402

    return len(TOOL_DEFINITIONS)


def compact_count() -> int:
    sys.path.insert(0, str(ROOT / "horosa-skill" / "src"))
    from horosa_skill.surfaces.mcp_server import COMPACT_SURFACE_TOOL_COUNT  # noqa: E402

    return int(COMPACT_SURFACE_TOOL_COUNT)


def render(rel: str, *, techniques: int | None = None, compact: int | None = None) -> str:
    client, key, depth, frontmatter = MIRRORS[rel]
    prefix = "./" if depth == 0 else "../" * depth
    return frontmatter + TEMPLATE.format(client=client, techniques=techniques if techniques is not None else technique_count(),
                                         compact=compact if compact is not None else compact_count(), prefix=prefix, key=key)


def drift(root: Path = ROOT, *, techniques: int | None = None, compact: int | None = None) -> list[str]:
    """[rel] of mirrors whose on-disk text differs from the render (missing counts as drift)."""
    out: list[str] = []
    for rel in MIRRORS:
        path = root / rel
        expected = render(rel, techniques=techniques, compact=compact)
        if not path.is_file() or path.read_text(encoding="utf-8") != expected:
            out.append(rel)
    return out


SKILL_SOURCE_REL = "skills/horosa-agent"
SKILL_BUNDLE_REL = "horosa-skill/src/horosa_skill/agent_skill/horosa-agent"
SKILL_REPO_BLOB = "https://github.com/Horace-Maxwell/horosa-skill/blob/main/"
_CLIMBING_LINK = re.compile(r"\]\((?P<up>(?:\.\./)+)(?P<rest>[^)\s]+)\)")


def render_skill_file(text: str, rel_in_skill: str) -> str:
    """Rewrite links that climb out of the skill folder into GitHub URLs (the installed copy has no repo around it)."""
    depth = len(Path(rel_in_skill).parts) - 1  # SKILL.md = 0, references/x.md = 1

    def repl(match: re.Match[str]) -> str:
        ups = match.group("up").count("../")
        if ups <= depth:
            return match.group(0)  # stays inside the skill folder
        # skills/horosa-agent/<rel_in_skill> → climb `ups` levels from the file's own directory.
        anchor = Path(SKILL_SOURCE_REL) / Path(rel_in_skill).parent
        for _ in range(ups):
            anchor = anchor.parent
        return f"]({SKILL_REPO_BLOB}{(anchor / match.group('rest')).as_posix()})"

    return _CLIMBING_LINK.sub(repl, text)


def skill_bundle_render(root: Path = ROOT) -> dict[str, str]:
    """{path inside the skill folder: rendered text} for every .md file of the policy source."""
    source = root / SKILL_SOURCE_REL
    return {
        path.relative_to(source).as_posix(): render_skill_file(path.read_text(encoding="utf-8"), path.relative_to(source).as_posix())
        for path in sorted(source.rglob("*.md"))
    }


def bundle_drift(root: Path = ROOT) -> list[str]:
    """[rel under the bundle] that are missing, differ from the render, or are stale extras."""
    bundle = root / SKILL_BUNDLE_REL
    expected = skill_bundle_render(root)
    out = [rel for rel, text in expected.items()
           if not (bundle / rel).is_file() or (bundle / rel).read_text(encoding="utf-8") != text]
    if bundle.is_dir():
        out += sorted(p.relative_to(bundle).as_posix() for p in bundle.rglob("*") if p.is_file()
                      and p.relative_to(bundle).as_posix() not in expected)
    return out


def write_bundle(root: Path = ROOT) -> list[str]:
    bundle = root / SKILL_BUNDLE_REL
    expected = skill_bundle_render(root)
    if bundle.is_dir():
        for stale in [p for p in bundle.rglob("*") if p.is_file() and p.relative_to(bundle).as_posix() not in expected]:
            stale.unlink()
    for rel, text in expected.items():
        (bundle / rel).parent.mkdir(parents=True, exist_ok=True)
        (bundle / rel).write_text(text, encoding="utf-8")
    return sorted(expected)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="report drift instead of writing")
    args = ap.parse_args(argv)
    if args.check:
        stale = drift() + [f"{SKILL_BUNDLE_REL}/{rel}" for rel in bundle_drift()]
        if stale:
            print("agent-mirrors: DRIFT — regenerate with `python scripts/gen_agent_mirrors.py`: " + ", ".join(stale))
            return 1
        print(f"agent-mirrors: ok ({len(MIRRORS)} mirrors match the template; packaged skill bundle matches skills/horosa-agent)")
        return 0
    for rel in MIRRORS:
        path = ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render(rel), encoding="utf-8")
        print(f"wrote {rel}")
    for rel in write_bundle():
        print(f"wrote {SKILL_BUNDLE_REL}/{rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
