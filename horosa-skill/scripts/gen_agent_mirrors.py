#!/usr/bin/env python3
"""Render the thin agent mirrors from ONE template (v0.40.0 doc-currency institution).

Before this script the four thin mirrors (GEMINI.md, .github/copilot-instructions.md, .windsurf/rules/horosa-skill.md,
.clinerules/horosa-skill.md) were four hand-maintained copies of the same 25 lines that differed only in the client
name, the setup key, the relative pointer to the policy source and (Windsurf) a frontmatter block. Every rule change
had to be repeated four times by hand — and the 2026-09 Windsurf → Devin Desktop rename showed how a client fact can go
stale in one copy and not another. Now the text lives here once; the mirrors are build output.

    python scripts/gen_agent_mirrors.py            # (re)write the mirrors
    python scripts/gen_agent_mirrors.py --check    # exit 1 when any mirror differs from the render (docs-sync calls this)

The policy source stays `skills/horosa-agent/SKILL.md`; this template is its 30-second digest (AGENTS.md §3).
Per-client facts (display name, setup key, notes) are the ONLY thing that varies — add a client = add a row below.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
TECHNIQUE_COUNT_SOURCE = ROOT / "horosa-skill" / "src" / "horosa_skill" / "engine" / "registry.py"

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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="report drift instead of writing")
    args = ap.parse_args(argv)
    if args.check:
        stale = drift()
        if stale:
            print("agent-mirrors: DRIFT — regenerate with `python scripts/gen_agent_mirrors.py`: " + ", ".join(stale))
            return 1
        print(f"agent-mirrors: ok ({len(MIRRORS)} mirrors match the template)")
        return 0
    for rel in MIRRORS:
        path = ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render(rel), encoding="utf-8")
        print(f"wrote {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
