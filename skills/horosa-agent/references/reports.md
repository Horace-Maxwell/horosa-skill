# Report & memory workflow

> 读者：AI 客户端。何时读：用户要结构化报告/文件，或要回查历史运行时。策略总纲：[`../SKILL.md`](../SKILL.md)。

## 两种报告，别混

| | 技法依据报告 | 咨询报告 |
| --- | --- | --- |
| 工具 | `horosa_technique_report` | `horosa_report_render` |
| 内容 | 用了什么技法 / 什么口径 / 谁算的 / 段落全不全 / 版本链 | 你写的解盘结论 |
| 需要 AI 正文 | **不需要**（确定性元数据） | **必须**（没有 `ai_report` 就不出终稿） |
| 机器元数据 | 就是正文 | 正文里**禁止**出现 |
| 格式 | markdown / json / docx / pdf | json / docx / pdf |

## 每次输出都要带的技法尾注（必做）

每个技法响应的 `data.technique_card` 是一张确定性的「这盘怎么来的」卡片。**给出结论后，把它原样转述
成一段尾注**——技法名、口径（含 `排盘规则` 那两个晚子时开关）、算源、段数与导出契约是否干净、版本。

- 不要改写、不要挑着说，尤其不要省略口径行：用户换过晚子时开关时，尾注缺这一行就是**静默错解**。
- `compute.matches_declaration` 为 `false` 时必须明说「实测算源与声明不符，结果请谨慎采信」——
  那正是 ken 端点静默回退本地脚手架的形状（HTTP 200 也可能是失败）。
- `sections.contract_clean` 为 `false` 时如实说缺了哪几段，别把缺段说成「该技法就这些」。
- 用户要文件时再调 `horosa_technique_report`（单次给 `run_id`，整场问答给 `group_id`）。
  会话态会额外检出**跨技法口径冲突**（例如两个技法用了不同的晚子时开关 —— 它们的结论不可互证）。
- `HOROSA_TECHNIQUE_CARD=0` 时卡片不出现，此时照常回答，不要编造一段尾注。

```bash
uv run horosa-skill report technique --group-id <group_id> --format markdown
```

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
