# Report & memory workflow

> 读者：AI 客户端。何时读：用户要结构化报告/文件，或要回查历史运行时。策略总纲：[`../SKILL.md`](../SKILL.md)。

## Structured report flow (MCP)

1. Call the calculation tool.
2. Call `horosa_report_template` with the `run_id` and `tool_name`.
3. Fill the AI analysis fields **from the actual exported sections**: `answer_text`, `direct_answer`,
   `executive_summary`, `analysis_sections`, `evidence`, `recommendations`, `limitations`.
4. Passing `ai_report` to `report_render`/`report_from_tool` auto-writes the answer back to the run —
   only call `horosa_memory_record_answer` when you store an answer WITHOUT rendering a report.
5. Call `horosa_report_render` with `format` = `json`, `docx`, or `pdf`.
6. Confirm the returned artifact exists and is retrievable via `horosa_memory_show` /
   `horosa_memory_query`.

**Human-facing DOCX/PDF reports read as consulting reports.** Do not put machine metadata, run IDs,
schema names, raw JSON, or provenance tables into the visible body unless the user asks — those belong
in JSON artifacts and memory metadata. Keep the `排盘规则: …` line quoted (see
[`late-zi.md`](./late-zi.md)).

## One-command CLI report (AI answer already written)

```bash
uv run horosa-skill report from-tool liureng_gods \
  --format docx \
  --question "用户的问题" \
  --ai-answer-file answer.txt \
  --input payload.json
```

- `--ai-answer-text` — short inline answer.
- `--ai-answer-file` — full prose answer.
- `--ai-report-file` — structured JSON with `direct_answer`, `analysis_sections`, `evidence`,
  `recommendations`, `limitations`.

## Interpretation style (detail)

- Start with the direct conclusion; then the supporting sections (cite actual 四课/三传/宫位/相位
  content, not generic theory).
- Separate 机会 / 风险 / 时机 / 建议行动.
- No specific question → comprehensive overall reading; specific question → prioritize it, avoid
  textbook filler.
- State limitations honestly (e.g. a conditional section absent, a switch not threaded) without
  hiding behind them.
