# Horosa Skill — rules for GitHub Copilot (VS Code)

This repo ships Horosa (星阙): 106 real techniques (Western astrology, 八字, 紫微, 六壬, 奇门, 太乙, 六爻, 神数 …)
as a local-first MCP server + CLI. The **single policy source** is [skills/horosa-agent/SKILL.md](../skills/horosa-agent/SKILL.md);
maintainer law is [AGENTS.md](../AGENTS.md). This file is a thin
pointer — do not add rules here.

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
   `horosa-skill setup --client vscode` (`uv run horosa-skill setup --client vscode` inside this checkout),
   then `horosa-skill doctor` for the machine-readable health report.
5. **Compact surface.** By default this client sees only the 11 facade tools (`HOROSA_MCP_COMPACT=1`); every
   technique is still reachable by name through `horosa_tool_run(tool_name="qimen", …)` and the full list is the
   `horosa://catalog/techniques` resource — a missing flat `horosa_*` name does not mean the technique is missing.
   No `horosa` tools at all? `horosa-skill setup --client vscode` registers everything.
