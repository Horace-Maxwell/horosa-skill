# Export Audit Guide

> 读者：维护者。何时读：逐 section 审计推运类导出、排查 missing/unknown 段时。

Horosa Skill writes Xingque-style output in two layers:

- `export_snapshot.export_text`: the human-readable Xingque export body.
- `export_snapshot.sections`: the machine-readable section map parsed from that body.

**Where you read it matters.** The CLI (`horosa-skill tool run …`) and the stored artifact carry the full envelope. Over MCP the
default is the reading view (since v0.50.0): `export_text` once plus a section index `{index, title, chars}`, no raw engine tree, and a
per-result model budget (about 48,000 characters / 20,000 estimated tokens). When the text is longer, whole sections are left out — the
section index marks them `shown: partial / none` and `warnings` carry a copy-ready follow-up call
(`horosa_memory_show(run_id=…, response_tool=…, response_sections=[…], response_offset=N)`). A section left out that way is **not**
missing: read it with the follow-up call, or audit over MCP with `response_view: "full"` (the full envelope, still within the ~900 KB
wire budget) or `response_view: "sections"` (per-section bodies). `missing_selected_sections` / `unknown_detected_sections` are the
contract check; only those (and 「结果不完整」 / 「降级」 lines in `warnings`) mean a section did not come back.

When auditing a tool, do not rely on a short preview alone. A preview such as the first 1200 characters can be useful for quick inspection, but predictive tools usually write the natal chart first and the return/progression chart after it. If the preview stops inside the natal chart, it can look as if the predictive chart is missing even when the full `export_text` is correct.

## Correct Audit Method

Use the full artifact and inspect sections:

1. Open the saved tool artifact JSON (or `horosa-skill memory show <run_id>`, or MCP `horosa_memory_show` with `response_view: "full"`).
2. Read `data.export_snapshot.export_text` in full.
3. Read `data.export_snapshot.sections` and check `missing_selected_sections` / `unknown_detected_sections` are empty.
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

Agents must interpret the full `export_snapshot` (`export_text` + `sections`), not a hand-written calculation or a truncated preview. Over MCP, a section that the reading view did not include is read with the follow-up call named in `warnings` before drawing any conclusion. If parameters are unclear, call `horosa_agent_guidance` first and ask the user to confirm the missing settings before invoking the real technique.
