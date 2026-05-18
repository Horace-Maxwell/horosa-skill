# Horosa Skill Agent Guide

Use this skill when an AI agent is connected to Horosa Skill through MCP, CLI, Cursor, Claude, Codex, OpenClaw, Open WebUI, or another local-first client and needs to call Horosa metaphysics tools, generate reports, store memory, or debug user-facing results.

## Core Rule

Horosa Skill is local-first. After `horosa-skill install`, algorithms should run through the local runtime, local headless JS engines, and local storage. Do not tell users that a missing field requires MongoDB, port 7897, Xingque Desktop, a remote database, or an external service unless a current `doctor` / `openclaw-check` result explicitly says so. If output is missing, describe it as a local tool/result/input issue and suggest a concrete recheck.

## Preferred Agent Workflow

1. Understand the user's question.
2. Choose the smallest matching Horosa tool.
3. Normalize time, place, timezone, and question text.
4. Call the tool.
5. Read `export_snapshot.export_text`, `export_format.sections`, and `summary`.
6. If the user wants a human-readable answer, explain the calculated chart/pan directly in the chat.
7. If the user wants a file, call the report tools and save JSON/DOCX/PDF artifacts.
8. If the user asks follow-up questions, use memory tools to retrieve prior runs and AI answers.

## Do Not Hallucinate Dependencies

Never say:

- "大六壬 needs MongoDB."
- "四课/三传 require port 7897."
- "You must install Xingque Desktop to get the full pan."
- "This tool needs a remote database."
- "The skill cannot output this because an external service is missing."

Instead say:

- "This local run did not return that section. I will rely on the returned sections, or we can rerun `doctor` / `openclaw-check`."
- "The current export contract shows the available sections. I should not invent missing data."
- "Please provide missing birth/event time, location, timezone, gender, or question context if needed."

## Tool Selection

Use these user intents:

- Astrology natal chart: `chart`
- Hellenistic / Greek chart: `hellen_chart`
- Qizheng Siyi / Guolao: `guolao_chart`
- Indian chart: `india_chart`
- Relationship chart: `relative`
- Solar return: `solarreturn`
- Lunar return: `lunarreturn`
- Solar arc: `solararc`
- Given-year prediction: `givenyear`
- Annual profection: `profection`
- Primary directions: `pd`, `pdchart`
- Zodiacal releasing: `zr`
- Firdaria: `firdaria`
- Decennials: `decennials`
- Bazi natal: `bazi_birth`
- Bazi luck / direct flow: `bazi_direct`
- Ziwei chart: `ziwei_birth`
- Ziwei rules: `ziwei_rules`
- Qimen Dunjia: `qimen`
- Taiyi: `taiyi`
- Daliuren: `liureng_gods`
- Daliuren runyear: `liureng_runyear`
- Jinkou Jue: `jinkou`
- Sanshi United: `sanshiunited`
- Tongshefa: `tongshefa`
- Six Yao: `sixyao`
- Gua description: `gua_desc`, `gua_meiyi`
- Suzhan: `suzhan`
- Germany / midpoint chart: `germany`
- Astrology dice / Western game: `otherbu`
- Jieqi year charts: `jieqi_year`
- Nongli / Ganzhi time: `nongli_time`
- Hover knowledge: `knowledge_registry`, `knowledge_read`
- Export protocol: `export_registry`, `export_parse`

Fengshui is intentionally excluded from this public skill surface.

## Input Defaults

For event-based Chinese methods, prefer:

```json
{
  "date": "2028-04-06",
  "time": "09:33:00",
  "zone": "+08:00",
  "lat": "31n13",
  "lon": "121e28",
  "gpsLat": 31.2167,
  "gpsLon": 121.4667,
  "ad": 1,
  "after23NewDay": false
}
```

For birth-based methods, include as much as possible:

```json
{
  "date": "1995-06-03",
  "time": "05:30:00",
  "zone": "+08:00",
  "lat": "31n13",
  "lon": "121e28",
  "gpsLat": 31.2167,
  "gpsLon": 121.4667,
  "ad": 1,
  "name": "User",
  "pos": "Shanghai"
}
```

For gender-sensitive tools, include `gender`. For Bazi and Ziwei, include `timeAlg`, `after23NewDay`, and direct/luck-flow options when the user asks about timing.

## Report Workflow

When the user wants a structured report:

1. Call the calculation tool.
2. Call `horosa_report_template` with the `run_id` and `tool_name`.
3. Fill the AI analysis fields from the actual exported sections:
   - `answer_text`
   - `direct_answer`
   - `executive_summary`
   - `analysis_sections`
   - `evidence`
   - `recommendations`
   - `limitations`
4. Call `horosa_memory_record_answer` to attach the AI answer to the run.
5. Call `horosa_report_render` with `format` as `json`, `docx`, or `pdf`.
6. Confirm the returned artifact exists and is retrievable through `horosa_memory_show` or `horosa_memory_query`.

Human-facing DOCX/PDF reports should be readable consulting reports. Do not put machine metadata, run IDs, schema names, raw JSON, or provenance tables into the visible body unless the user asks. Those belong in JSON artifacts and memory metadata.

## Interpretation Style

Answer like a careful consultant:

- Start with the direct conclusion.
- Cite the actual chart/pan sections that support the conclusion.
- Explain the reasoning path in human language.
- Separate opportunity, risk, timing, and suggested action.
- If the user has no specific question, produce a comprehensive overall reading.
- If the user has a specific question, prioritize that question and avoid generic textbook explanations.
- Mention limitations without hiding behind them.

## Validation Checklist

Before telling the user a result is ready, check:

- `ok` is `true`.
- `export_snapshot.export_text` is present for calculation tools.
- `export_format.sections` is non-empty.
- No section body is a bare `"无"`.
- The output does not contain dependency hallucinations such as MongoDB, 7897, Xingque Desktop, remote database, or external service.
- If a report was generated, the returned artifact path exists and has non-zero size.
- If memory was used, `memory_show` or `memory_query` can retrieve the run.

## Debug Commands

Use these locally when the client seems confused:

```bash
uv run horosa-skill doctor
uv run horosa-skill tool list
uv run horosa-skill client openclaw-check --workspace <workspace>
uv run python scripts/run_full_self_check.py
```

For OpenClaw onboarding:

```bash
uv run horosa-skill client openclaw-setup --workspace <workspace>
```

For a direct tool call:

```bash
uv run horosa-skill tool run liureng_gods --stdin
```

Then pass JSON on stdin.

For a one-command report after the AI has already written the analysis:

```bash
uv run horosa-skill report from-tool liureng_gods \
  --format docx \
  --question "用户的问题" \
  --ai-answer-file answer.txt \
  --input payload.json
```

Use `--ai-answer-text` for a short inline answer, `--ai-answer-file` for a full prose answer, and `--ai-report-file` for structured JSON with fields such as `direct_answer`, `analysis_sections`, `evidence`, `recommendations`, and `limitations`.

## Cross-Platform Notes

- macOS paths use `~/.horosa/runtime/current`.
- Windows paths use `%LOCALAPPDATA%/Horosa/runtime/current`.
- Do not emit `/bin/zsh`, `export HOME=...`, or POSIX-only commands in Windows configs.
- Do not emit `.cmd`-only commands in macOS configs.
- Use Horosa client config commands rather than hand-writing MCP JSON whenever possible.
