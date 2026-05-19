# Export Audit Guide

Horosa Skill writes Xingque-style output in two layers:

- `export_snapshot.export_text`: the human-readable Xingque export body.
- `export_format.sections`: the machine-readable section map parsed from that body.

When auditing a tool, do not rely on a short preview alone. A preview such as the first 1200 characters can be useful for quick inspection, but predictive tools usually write the natal chart first and the return/progression chart after it. If the preview stops inside the natal chart, it can look as if the predictive chart is missing even when the full `export_text` is correct.

## Correct Audit Method

Use the full artifact and inspect sections:

1. Open the saved tool artifact JSON.
2. Read `data.export_snapshot.export_text` in full.
3. Read `data.export_format.sections`.
4. Confirm the expected natal chart, target chart, aspect, table, or timeline sections are present.
5. If a user-facing report is needed, render it through `report_render` and confirm the report artifact is registered in memory.

## Local Audit Artifacts

Full input/output audits are local runtime artifacts and should not be committed to Git:

- `HOROSA_IO_AUDIT_*/all_tool_inputs_outputs_full.json`
- `HOROSA_IO_AUDIT_*/all_tool_inputs_outputs.jsonl`
- `HOROSA_IO_AUDIT_*/all_tool_inputs_outputs_summary.md`
- `HOROSA_IO_AUDIT_*/predictive_tools_full_export_sections.md`

The last file is the preferred way to inspect predictive tools because it expands the full export body by section instead of showing only a short prefix.

## Predictive Tools Checklist

| Tool | Required content |
|---|---|
| `solarreturn` | Natal chart + solar return chart + return aspects |
| `lunarreturn` | Natal chart + lunar return chart + return aspects |
| `givenyear` | Natal chart + selected-year / transit chart + aspects |
| `solararc` | Natal chart + solar-arc progressed chart + aspects |
| `profection` | Natal chart + profection / directed chart + aspects |
| `pd` | Natal chart + real primary-direction table rows |
| `pdchart` | Natal chart + primary-direction chart table + aspects + notes |
| `zr` | Natal chart + zodiacal releasing timeline |
| `firdaria` | Firdaria table |
| `decennials` | Decennials timeline |

For these tools, `ok=true` is necessary but not sufficient. A client or agent should also verify that the expected sections exist. If a client claims the `/predict/*` tools are unavailable, first check whether it is reading a truncated preview, using an old runtime, bypassing MCP, or skipping `doctor` / `openclaw-check --full`.

## Agent Rule

Agents must interpret the full `export_snapshot` and `export_format`, not a hand-written calculation or a truncated preview. If parameters are unclear, call `horosa_agent_guidance` first and ask the user to confirm the missing settings before invoking the real technique.
