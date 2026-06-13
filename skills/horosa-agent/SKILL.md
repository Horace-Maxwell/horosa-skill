# Horosa Skill Agent Guide

Use this skill when an AI agent is connected to Horosa Skill through MCP, CLI, Cursor, Claude, Codex, OpenClaw, Open WebUI, or another local-first client and needs to call Horosa metaphysics tools, generate reports, store memory, or debug user-facing results.

## Core Rule

Horosa Skill is local-first. After `horosa-skill install`, algorithms should run through the local runtime, local headless JS engines, and local storage. Do not tell users that a missing field requires MongoDB, port 7897, Xingque Desktop, a remote database, or an external service unless a current `doctor` / `openclaw-check` result explicitly says so. If output is missing, describe it as a local tool/result/input issue and suggest a concrete recheck.

If the client exposes native Horosa MCP tools, call those tools directly. In OpenClaw traces this means the agent should see Horosa tools such as `horosa_cn_qimen`, `horosa_cn_liureng_gods`, `horosa_astro_chart`, `horosa_agent_guidance`, `horosa_memory_show`, and `horosa_report_render`. If the trace shows `clientToolCount: 0` or no `horosa_*` tools are available, the MCP server was not attached to that agent session. Stop and tell the user/admin to run:

```bash
uv run horosa-skill client openclaw-setup --workspace <the-agent-workspace>
uv run horosa-skill client openclaw-check --workspace <the-agent-workspace> --full
```

Do not silently fall back to hand-written Python, shell calculations, web snippets, or unscoped CLI calls. CLI fallback is only acceptable as a diagnostic, and it must use the exact `HOME`, `HOROSA_RUNTIME_ROOT`, and `HOROSA_SKILL_DATA_DIR` env block from the generated mcporter config.

Do not hand-calculate Horosa techniques with `Exec`, shell, Python, JavaScript snippets, web search, or memory-only formulas. If the user asks for a pan/result, call the Horosa MCP or CLI tool and treat the returned `export_snapshot` as the source of truth. Manual scripts bypass Xingque-compatible defaults, true-solar-time handling, runtime parity fixes, memory, and reports.

## Preferred Agent Workflow

1. Understand the user's question.
2. Choose the smallest matching Horosa tool.
3. If required context or result-changing settings are missing, call `horosa_agent_guidance` or follow the guidance table below.
4. Ask the user one concise clarification question with concrete options when settings are unclear.
5. Normalize time, place, timezone, and question text.
6. Call the tool.
7. Read `export_snapshot.export_text`, `export_format.sections`, and `summary`.
8. If the user wants a human-readable answer, explain the calculated chart/pan directly in the chat.
9. If the user wants a file, call the report tools and save JSON/DOCX/PDF artifacts.
10. If the user asks follow-up questions, use memory tools to retrieve prior runs and AI answers.

## Clarification Rule

This is a hard rule: if the user omitted a setting that changes the result, ask before calling. Do not silently pick a value just because the schema has a default.

Use this MCP helper:

```json
{"tool_name":"liureng_gods","intent":"当前时间起大六壬"}
```

or CLI:

```bash
uv run horosa-skill agent guidance --tool liureng_gods --intent "当前时间起大六壬"
```

Ask before calling when these are missing:

- Time/date/timezone/place for birth/event methods.
- Gender for Ziwei, Bazi direct/luck flow, LiuReng runyear, or any gender-sensitive report.
- House system / zodiacal system / traditional settings for astrology charts when the user cares about chart style.
- Qimen 起局方式、命式性别、拆补/置闰/茅山等 method settings when the user expects a non-default pan.
- LiuReng 贵人体系 and昼夜贵人 if the user does not accept Xingque defaults.
- Jinkou 地分 and贵人体系.
- SixYao lines, gua code, or起卦方式.
- Report format and whether AI analysis text is ready.
- Predictive astrology target fields: return/progression target `datetime`, directed location/timezone `dirLat` / `dirLon` / `dirZone`, and primary-direction method settings.

Allowed shortcuts:

- If the user says “当前时间”, use current local date/time/timezone.
- If the user says “按星阙默认 / 默认 / 快速起盘 / 你来决定”, use documented safe defaults and mention that defaults were used.
- If a stored memory run already contains the setting, reuse it and cite the run.

Runtime enforcement:

- Calculation tools and `horosa_dispatch` reject unconfirmed calls with `agent_guidance.required`.
- After asking the user, include `agent_confirmed_settings: true`.
- If the user explicitly accepts defaults, include `defaults_accepted: true`.
- Include `clarification_notes` with a short summary such as `"user accepted Xingque defaults for guirengType and automatic day/night noble-person"`.
- If a response contains `details.agent_recovery`, you must stop and ask the user with `details.agent_recovery.prompt_to_user`.
- Do not call another calculation tool as a workaround for a blocked or incomplete call.
- Do not mark `agent_confirmed_settings` true unless the user actually answered the missing settings.

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
- Primary directions: `pd`, `pdchart` — engine at 星阙 v2.6.6 PD v12 parity: 5 verified methods (`core_alchabitius`/`meridian`/`porphyry`/`equal_ecliptic`/`equal_hour_circle`; unknown values fall back to `core_alchabitius` inside the engine), 22 time keys (incl. per-chart Simmonite/Kepler/Brahe and dynamic TrueSolarArc/SymbolicSolarArc), Vertex significator rows (In-Zodiaco only), `pdYears` up to 3000 with per-revolution recurrence rows.
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
- Shaozi Canping (邵子参评数 / 金锁银匙): `canping`
- Heluo Lishu (河洛理数): `heluo`
- Harmonic chart (调波盘): `harmonic`
- Age Point / 年龄推进点 (Huber, v2.4.0): `agepoint`
- Distributions / 界推运 (分配法, v2.4.0): `distributions`
- Mundane ingress / 世俗入宫盘 (v2.4.0): `mundane` — input is year + 入宫节气 (春分/夏至/秋分/冬至) + place
- Triplicity-ruler periods / 三分主星推运 (v2.6.x): `triplicityrulers`
- Numeric keypoints / 数字相位推运 (v2.6.x): `keypoints`
- Progressed lunation phase / 月相推运 (v2.6.x): `lunationphase`
- Multiple returns / 多重回归 (v2.6.x): `extrareturns` — Saturn / Jupiter / lunar-node returns
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

For gender-sensitive tools, include `gender`. For Bazi and Ziwei, include `timeAlg`, `after23NewDay`, `lateZiHourUseNextDay`, and direct/luck-flow options when the user asks about timing.

### Day boundary + late-zi-hour rules (v2.2.1+) — two independent switches

> **⏳ STATUS as of v0.12.0: runtime ready, skill wiring PARTIAL.** The offline runtime's ken engine carries
> the v2.2.1 lateZi code, and the skill **now forwards `lateZiHourUseNextDay` in the 神数 path** (it is a
> schema field and is passed through for wangji/wuzhao/.../the 9 kinastro-* 神数). It is **not yet threaded
> through the bazi / ziwei / liureng / qimen chart-flow payloads**, so for those the non-default `hour==23`
> rows below remain the **target spec**, not current shipped behavior — only the default
> `(after23NewDay=1, lateZiHourUseNextDay=1)` is guaranteed correct there. If you must be exact about an
> `hour==23` non-default case for a chart-flow technique, tell the user that switch isn't threaded yet.
> (Maintainers: see the matching banner + the remaining wiring to-do in `AGENTS.md`.)

For ANY hour-23 input (`time` ∈ `23:00:00`–`23:59:59`), the four pillars depend on **two** independent settings. Treat them as separate flags — the user may have set one or both globally in 星阙 desktop, and predictive runs must mirror what the user sees on screen.

| Field | Values | Default | Effect at `hour == 23` |
|---|---|---|---|
| `after23NewDay` | `1` / `0` | `1` | `1` = "23点算第二天" → day pillar advances to next day. `0` = "24点算第二天" → day pillar stays today. |
| `lateZiHourUseNextDay` | `1` / `0` | `1` | `1` = "晚子时按次日日柱计算" → hour stem起 from next-day day stem. `0` = "晚子时按当日柱计算" → hour stem起 from today's day stem. |

**Outside of `hour == 23`, both flags are no-ops.** They do not change anything in `[00:00, 23:00)`. Don't ask the user about them unless the time is actually in that window.

**Self-check matrix — `2026-05-27 23:30:00`, direct-time mode:**

| `after23NewDay` | `lateZiHourUseNextDay` | 日柱 | 时柱 |
|---|---|---|---|
| 1 (default) | 1 (default) | 壬寅 | 庚子 |
| 1 | 0 | 壬寅 | 庚子 *(day pillar already advanced, equivalent)* |
| 0 | 1 | 辛丑 | 庚子 |
| 0 | 0 | 辛丑 | **戊子** ← only case where the new switch changes anything |

If a tool returns four pillars that don't match this matrix for that fixture, the runtime is stale (predates v2.2.1) — tell the user to re-install the runtime release, do not blame the technique.

**When asking the user about the two switches:**

- If the user explicitly mentions 晚子时 / 子时 / 23 点 / 24 点 in the question, ask which mode they want before calling. Concrete options:
  - 日柱开关: 「23点算第二天 (默认)」 / 「24点算第二天」
  - 时柱开关: 「晚子时按次日日柱计算 (默认)」 / 「晚子时按当日柱计算」
- If a stored case/memory already contains either field, reuse it and cite the saved run.
- If the user says 「默认 / 按星阙 / 你来决定」, use `after23NewDay: 1` + `lateZiHourUseNextDay: 1` (current shipping default), and mention that defaults were used.
- The flags belong on every chart-flow payload (`chart`, `bazi_birth`, `bazi_direct`, `ziwei_birth`, `liureng_gods`, `liureng_runyear`, `qimen`, `taiyi`, `jinkou`, `sanshiunited`, `canping`, `heluo`, `nongli_time`, `jieqi_year`). Tools that don't read them ignore them harmlessly — but tools that DO read them silently pick `1`/`1` if absent, which can produce a chart that disagrees with the user's 星阙 desktop settings.

**AI explanation hook — always quote the active rule.** The export snapshot now includes a `排盘规则: 日柱开关【…】+ 时柱开关【…】。本盘四柱按此规则计算。` line in `export_snapshot.export_text`. When you write the interpretation, mirror that line back to the user so they can verify the chart was built under the same convention they assumed. Don't strip it from the report.

For predictive astrology tools, do not call with natal data alone. These are the minimum real-call contracts:

```json
{
  "solarreturn_or_lunarreturn": "birth data + datetime + dirZone + dirLat + dirLon; output must include natal chart + return chart + return aspects",
  "givenyear": "birth data + datetime + dirZone + dirLat + dirLon; output must include natal chart + given-year chart + aspects",
  "solararc_or_profection": "birth data + datetime + dirZone; output must include natal chart + progressed/profection chart + aspects",
  "pd": "birth data + pdtype + pdMethod + pdTimeKey + pdaspects; output must include a real primary-direction table",
  "pdchart": "birth data + datetime + dirZone + pdtype + pdMethod + pdTimeKey; output must include a primary-direction chart table",
  "zr_firdaria_decennials": "birth data + confirmed/default timeline settings; output must include timeline rows"
}
```

Use this before any predictive call:

```bash
uv run horosa-skill agent guidance --tool solarreturn
uv run horosa-skill tool list
```

If the user asks “看今年运势” without giving target year/date and location, ask for the missing values. Do not silently use the current date or birth location unless the user accepts that default.

For Daliuren, the Xingque-compatible default is `guirengType: 2` (`星占法贵人`). Only use `guirengType: 0` (`六壬法贵人`) or `guirengType: 1` (`遁甲法贵人`) when the user explicitly asks for that noble-person system or an existing case record already specifies it.

For current-time Daliuren requests such as "用当前时间起一个大六壬盘", do this:

1. Read the current local date, time, and timezone.
2. Include location/longitude/latitude if the user or client environment provides them.
3. Call `horosa_cn_liureng_gods` / `liureng_gods`.
4. Explain only from returned 四课、三传、旬日、神煞、概览 sections.
5. Do not run an ad-hoc calendar script to compute 干支、天盘、四课、三传.

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

For named OpenClaw agents, `<workspace>` must be the workspace actually used by that agent, for example `~/.openclaw/workspace-horosabot`. Passing `~/.openclaw/workspace` while the agent runs in `workspace-horosabot` verifies the wrong environment.

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

## Maintainer Notes (ken backend)

This skill guide is for AI clients **using** Horosa Skill. If you are **modifying or building** the
repo, the full maintainer playbook (re-vendoring the JS engines, offline-runtime packaging gotchas
(incl. the cross-platform Windows build — no `rsync`/POSIX-only binaries), `pkill` caveat, venv repair,
local verification, the **tongshefa/decennials 星阙-alignment notes** —
京房 palace element + JS-`Math.round` parity, **and the "Stability invariants" — `run_tool` always
returns an envelope; surfaces, the Node/`js_client` layer, tracing, the evaluation lock, and report
rendering all fail safe**) lives in the repo's harness doc [`AGENTS.md`](../../AGENTS.md) under
"Maintainer & Build Notes".

For client behaviour this means: a tool that fails returns `ok=False` with an `error.code` (e.g.
`tool.internal_error` for an unexpected backend/format error, `tool.ken_compute_failed` for a ken
miss) — it does not throw. Read the `error` and relay it; do not assume a crash means the tool is
unavailable.

**🔴 MANDATORY — Problem-Logging Protocol (enforced):** every problem, gotcha, surprising behavior, or
fix you hit while working in this repo MUST be recorded in [`AGENTS.md`](../../AGENTS.md) — see its
top-of-file **🔴 MANDATORY: Problem-Logging Protocol** for the full rule. In the same change: append a
gotcha bullet to the relevant `AGENTS.md` section (symptom → root cause → guard), sync **this** skill doc
when the lesson is client-facing (payload fields, gating, section contracts), add a `CHANGELOG.md`
`[Unreleased]` entry, and add a code-level guard (`verify_*` / CI step / schema constraint) whenever the
gotcha is machine-assertable. A doc note alone is not enough for anything CI or a script can check. Never
leave `AGENTS.md` and this doc contradicting each other, and never write skill-repo lessons into the
upstream 星阙 tree.

**Engine credit (MIT):** the ken engines are open-source and MIT-licensed, by **kentang2017** —
`kinqimen` / `kintaiyi` / `kinjinkou`. Their `LICENSE` files ship inside the offline runtime under
`Horosa-Web/vendor/*/LICENSE` and must never be stripped; the acknowledgement is in `README.md` /
`README_EN.md`. See the harness doc for the full MIT obligation.

The two facts most relevant to debugging user-facing results:

- **`qimen` / `taiyi` / `jinkou` (and `sanshiunited`'s 奇门 + 太乙) are computed by 星阙's `ken` backend**
  (`kinqimen` / `kintaiyi` / `kinjinkou`) on the chart service (`:8899`), not by the JS layer. The JS
  only reformats the ken response into `aiExport.js` sections. A healthy result carries
  `pan.source == "kinqimen"` / `"kintaiyi"` and `jinkou.source == "kinjinkou"`.
  - 奇门的「化解 / 用神分论 / 六害 / 取象」由 JS 层（`DunJiaFaCalc`/`DunJiaFaDoc`）在 kinqimen `pan` 上叠加格式化，随 AI 快照一并返回（新增 8 段：六害总览/化解方案/八门化气大阵/用神分论/财富七要/事业七要/恋爱姻缘/孤辰寡宿）；这是 JS 格式化层、非后端缺失，勿误判。
- **If those tools return `source: null`** (or a chart that doesn't match 星阙), the runtime in use is
  almost certainly **pre-ken**: re-install the current runtime release, or for development set
  `HOROSA_CORE_JS_ROOT` to the repo's `horosa-core-js`. This is a stale-runtime issue, not an algorithm
  failure — do not tell the user the technique is unavailable.
