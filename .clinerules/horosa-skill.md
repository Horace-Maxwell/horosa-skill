# Horosa Skill — rules for Cline

This repo ships Horosa (星阙): 114 real techniques (Western astrology, 八字, 紫微, 六壬, 奇门, 太乙, 六爻, 神数 …)
as a local-first MCP server + CLI. The **single policy source** is [skills/horosa-agent/SKILL.md](../skills/horosa-agent/SKILL.md);
maintainer law is [AGENTS.md](../AGENTS.md). This file is **generated** by `horosa-skill/scripts/gen_agent_mirrors.py` —
edit the template there, never this copy.

1. **Never hand-calculate** a technique (no formulas, no memorised tables, no web lookups). Every chart comes
   from a `horosa_*` MCP tool or the `horosa-skill` CLI.
2. **Clarify before calling.** A missing fact (time, place, gender, the moment of the question) or an
   unanswered setting (流派 / house system / 起局方式) makes the tool refuse with `agent_guidance.required`.
   Ask the user with `details.agent_recovery.prompt_to_user`. Settings → retry with `agent_confirmed_settings: true`
   + `clarification_notes` (or `defaults_accepted: true` only when the user accepts defaults). Facts go in the
   payload — no flag replaces them. Never self-confirm, never switch tools to bypass the gate.
3. **Explain only from `export_snapshot.export_text`.** A section not shown is "not returned", never a missing
   dependency. Cut text: `warnings` give the follow-up call. Quote `data.technique_card` after every answer.
4. No `horosa` tools in the list? One command registers everything:
   `horosa-skill setup --client cline` (`uv run horosa-skill setup --client cline` inside this checkout),
   then `horosa-skill doctor` for the machine-readable health report.
5. **Compact surface.** By default this client sees only the facades + `horosa_tool_run` (14 in all, `HOROSA_MCP_COMPACT=1`); every
   technique is still reachable by name through `horosa_tool_run(tool_name="qimen", …)` and the full list is the
   `horosa://catalog/techniques` resource — a missing flat `horosa_*` name does not mean the technique is missing.
6. Errors carry structured recovery: `details.agent_recovery.must_ask_user: true` → relay `prompt_to_user` and stop;
   `false` → fix the listed `fix_fields` yourself. On
   `runtime.*` errors suggest `horosa-skill doctor --explain` (Linux / Intel Mac = gateway mode; Windows runtime root
   must be pure ASCII). Never retry by flipping a setting the user did not choose.
