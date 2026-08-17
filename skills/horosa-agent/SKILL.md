---
name: horosa-agent
description: >-
  Call Horosa (星阙) local metaphysics tools correctly over MCP or CLI — 92 real techniques: Western
  natal/predictive astrology (returns, progressions, primary directions, horary 卜卦, election 择日),
  八字, 紫微, 大六壬, 奇门遁甲, 太乙, 金口诀, 三式合一, 河洛理数, 邵子参评数, 六爻, 天文地占, 塔罗, and
  the full 14 神数. Use whenever a user asks to 起盘 / 排盘 / 起课 / 起卦 / 算命 / 推运 / 看盘 / 合盘 /
  卜卦 / 择日 or requests any Horosa/星阙 chart, reading, report, or stored run — and when debugging a
  user-facing Horosa result. Enforces the clarify-before-call gate and the export-snapshot reading
  contract; never hand-calculate these methods.
license: AGPL-3.0-only
compatibility: Requires the local Horosa Skill MCP server/CLI (Python 3.12 + uv + installed offline runtime)
metadata:
  version: "0.28.0"
---

# Horosa Skill Agent Guide

Use this guide when an AI agent is connected to Horosa Skill through MCP, CLI, Cursor, Claude, Codex,
OpenClaw, Open WebUI, or another local-first client and needs to call Horosa metaphysics tools,
generate reports, store memory, or debug user-facing results.

This file is the **single policy source for AI-client behaviour** (repo rules & maintainer law live in
[`AGENTS.md`](../../AGENTS.md)). Detail lives in the reference sheets:

| Reference | Content |
| --- | --- |
| [`references/payloads.md`](./references/payloads.md) | Input payload defaults (event/birth JSON), coordinates, gender/timeAlg fields |
| [`references/late-zi.md`](./references/late-zi.md) | 晚子时/日界 two-switch spec — canonical matrix, how to ask, status |
| [`references/predictive.md`](./references/predictive.md) | Predictive astrology minimum contracts (returns/progressions/PD), PD engine parity |
| [`references/chinese-methods.md`](./references/chinese-methods.md) | 大六壬 defaults, current-time casting flow, 奇门法奇门 sections, 中式技法 notes |
| [`references/reports.md`](./references/reports.md) | Report/memory workflow, one-command CLI report, interpretation style detail |
| [`references/troubleshooting.md`](./references/troubleshooting.md) | Debug commands, openclaw setup/check, symptom table, cross-platform notes |

## Quickstart — 三步出 Word 报告

```jsonc
// 1) 起盘（确认设置后）——返回 memory_ref.run_id
horosa_cn_qimen {date, time, zone:"+08:00", lat:"31n13", lon:"121e28", agent_confirmed_settings:true, clarification_notes:"…"}
// 2) 读 data.export_snapshot.export_text / sections 写出你的解读（ai_report 各字段）
// 3) 渲染 —— ai_report 自动写回记忆，无需再调 memory_record_answer
horosa_report_render {run_id, tool_name:"qimen", format:"docx", ai_report:{executive_summary, answer_text, analysis_sections, recommendations, limitations}}
```

省 token：技法工具可传 `response_view:"titles"`（只回段标题）或 `"sections"`；完整快照始终已存档（`horosa_memory_show(run_id)` 取回）。注意 `horosa_report_from_tool` 会重新起盘——已有 run_id 用 `report_render`。

**每次给出结论后，把 `data.technique_card` 原样转述成一段技法尾注**（技法 / 口径 / 算源 / 段落 / 版本）——
它是确定性元数据，`response_view` 精简时也在。要文件就调 `horosa_technique_report`（`run_id` 单次、
`group_id` 整场，后者还会检出跨技法口径冲突）。细则与两种报告的分界：[`references/reports.md`](./references/reports.md)。

## Core Rule

Horosa Skill is **local-first**. After `horosa-skill install`, algorithms run through the local
runtime, local headless JS engines, and local storage. Do not tell users that a missing field requires
MongoDB, port 7897, Xingque Desktop, a remote database, or an external service unless a current
`doctor` / `openclaw-check` result explicitly says so. If output is missing, describe it as a local
tool/result/input issue and suggest a concrete recheck.

If the client exposes native Horosa MCP tools (`horosa_cn_qimen`, `horosa_cn_liureng_gods`,
`horosa_astro_chart`, `horosa_agent_guidance`, `horosa_memory_show`, `horosa_report_render`, …), call
them directly. If the trace shows `clientToolCount: 0` or no `horosa_*` tools, the MCP server was not
attached — stop and follow [`references/troubleshooting.md`](./references/troubleshooting.md) (openclaw
setup/check). CLI fallback is a diagnostic only, and must use the exact `HOME`, `HOROSA_RUNTIME_ROOT`,
`HOROSA_SKILL_DATA_DIR` env block from the generated mcporter config.

**Never hand-calculate Horosa techniques** with `Exec`, shell, Python, JavaScript snippets, web search,
or memory-only formulas. If the user asks for a pan/result, call the Horosa MCP or CLI tool and treat
the returned `export_snapshot` as the source of truth. Manual scripts bypass input normalization,
true-solar-time and timezone handling, Xingque-compatible defaults, runtime parity fixes, memory, and
reports — they will disagree with 星阙 and there will be no way to tell why.

## Preferred Agent Workflow

1. Understand the user's question.
2. Choose the smallest matching Horosa tool (table below).
3. If required context or result-changing settings are missing, call `horosa_agent_guidance`
   (CLI: `uv run horosa-skill agent guidance --tool <tool> --intent "..."`).
4. Ask the user one concise clarification question with concrete options when settings are unclear.
5. Normalize time, place, timezone, and question text.
6. Call the tool.
7. Read `export_snapshot.export_text`, `export_snapshot.sections`, and `summary`.
8. Explain the chart/pan directly in chat from those returned sections only.
9. If the user wants a file, use the report tools ([`references/reports.md`](./references/reports.md)).
10. For follow-ups, retrieve prior runs and AI answers with the memory tools.

## Clarification Rule (hard gate)

**If the user omitted a setting that changes the result, ask before calling.** Do not silently pick a
value just because the schema has a default. Ask when these are missing:

- Time/date/timezone/place for birth/event methods.
- Gender for Ziwei, Bazi direct/luck flow, LiuReng runyear, or any gender-sensitive report.
- House system / zodiacal (tropical vs sidereal ayanāṃśa) / traditional settings for astrology charts
  when the user cares about chart style.
- Qimen 起局方式、命式性别、拆补/置闰/茅山 method settings when the user expects a non-default pan.
- LiuReng 贵人体系 and 昼夜贵人 if the user does not accept Xingque defaults; Jinkou 地分 and 贵人体系.
- SixYao lines, gua code, or 起卦方式.
- 晚子时/日界 switches when the time is in `[23:00, 24:00)` — see
  [`references/late-zi.md`](./references/late-zi.md).
- Predictive targets: `datetime`, `dirLat` / `dirLon` / `dirZone`, primary-direction method settings —
  see [`references/predictive.md`](./references/predictive.md).
- Report format and whether AI analysis text is ready.

Allowed shortcuts:

- User says “当前时间” → use current local date/time/timezone.
- User says “按星阙默认 / 默认 / 快速起盘 / 你来决定” → use documented safe defaults and say so.
- A stored memory run already contains the setting → reuse it and cite the run.

Runtime enforcement (the gate is in code, not just policy):

- Calculation tools and `horosa_dispatch` reject unconfirmed calls with `agent_guidance.required`.
- After the user answers, include `agent_confirmed_settings: true`. If the user explicitly accepts
  defaults, include `defaults_accepted: true`. Add `clarification_notes` summarizing what was confirmed
  (e.g. `"user accepted Xingque defaults for guirengType and automatic day/night noble-person"`).
- If a response carries `details.agent_recovery`, stop and ask the user with
  `details.agent_recovery.prompt_to_user`. Do not retry the same tool, and do not call another
  calculation tool as a workaround, until the user answers or accepts defaults.
- **Never set `agent_confirmed_settings: true` yourself without a real user answer.**

## Do Not Hallucinate Dependencies

Never say: “大六壬 needs MongoDB” / “四课三传 require port 7897” / “you must install Xingque Desktop” /
“this tool needs a remote database or external service”.

Instead say: “This local run did not return that section — I'll rely on the returned sections, or we
can rerun `doctor` / `openclaw-check`.” / “The export contract shows the available sections; I won't
invent missing data.” / “Please provide the missing birth/event time, location, timezone, gender, or
question context.”

## Tool Selection

| User intent | Tool |
| --- | --- |
| Natal chart 标准星盘 | `chart` (13-house: `chart13`; 12th-harmonic/Dwadasamsa: `chart12`; Hellenistic: `hellen_chart`) |
| 老黄历 / 通书择日 | `huangli` (day almanac) · `tongshu` (needs `school` — the five schools can disagree outright on the same day) |
| 巴比伦占星 Babylonian | `babylon` (no houses/aspects/Asc by design — the reading device is the bīt niṣirti triplicity + planetary numina) |
| Draconic / Relocation 衍生盘 | `draconic` (node-zeroed) · `relocation` (needs `relocLat`/`relocLon` — without them it degenerates to the natal chart) |
| 古典占星 dignities reading (v2.6.7) | no separate tool — `chart`/`chart13`/`hellen_chart` exports carry `[古典]` + `[古典格局]` automatically; `india_chart`/`mundane` carry `[古典]` only |
| Qizheng Siyi / 七政四余 | `guolao_chart` |
| Indian chart 印度盘 | `india_chart` |
| Relationship 合盘 | `relative` |
| Midpoint/Uranian 中点盘 | `germany` |
| Solar/lunar return 返照 | `solarreturn` / `lunarreturn` |
| Solar arc / given year / profection | `solararc` / `givenyear` / `profection` |
| Primary directions 主限法 | `pd`, `pdchart` (see `references/predictive.md` for the v12 engine surface) |
| Zodiacal releasing / Firdaria / Decennials | `zr` / `firdaria` / `decennials` |
| Age point / distributions / mundane ingress | `agepoint` / `distributions` / `mundane` (year + 入宫节气 + place) |
| Triplicity rulers / keypoints / lunation phase / extra returns | `triplicityrulers` / `keypoints` / `lunationphase` / `extrareturns` |
| More progressions (v2.5.0) | `jaynesprog` / `vedicprog` / `planetaryarc` / `planetaryages` / `balbillus` / `yearsystem129` / `persiandirected` |
| Horary 卜卦 / Election 择日 | `horary` / `election` |
| 择日「找日子」——要在一段时间里搜时刻，而不是评一个候选时刻 | 西占征象 → `tianxing`；奇门条件 → `qimenzeri`（两者都要 startDate/endDate + conditions 条件树；单点评估仍用 `election`） |
| Harmonic 调波盘 | `harmonic` |
| 八字 | `bazi_birth` / `bazi_direct` |
| 紫微斗数 | `ziwei_birth` (`ziwei_rules` returns the rules library) |
| 大六壬 / 行年 | `liureng_gods` / `liureng_runyear` |
| 奇门遁甲 / 太乙 / 金口诀 / 三式合一 | `qimen` / `taiyi` / `jinkou` / `sanshiunited` |
| 统摄法 | `tongshefa` |
| 邵子参评数 / 河洛理数 | `canping` / `heluo` |
| 六爻 | `sixyao` |
| 卦义 | `gua_desc`, `gua_meiyi` |
| 宿占 | `suzhan` |
| 一掌经 | `yizhangjing` |
| 神数正传（铁板 / 邵子 / 大定 / 六亲 / 铁算心易） | `zhengchuan`（school 选流派；除铁算心易外需生辰） |
| 小六壬 | `xiaoliuren`（三数或占时起课，冻结值；改流派只重排） |
| 飞宫小奇门 | `feigong`（起支+日干支定局，冻结值；占时可起） |
| 小成图 | `xiaochengtu`（手动/两数/股价/大衍/占时，大衍须显式 seed，卦为冻结值） |
| 皇极轨策 | `guice`（十二法起卦，冻结值；十开关流派只重排断法） |
| 天文地占 geomancy | `geomancy` |
| 塔罗 tarot | `tarot` |
| 灵棋经 lingqi | `lingqi`（以起卦时刻确定性掷十二棋；给了 counts 就复排，绝不重掷） |
| 占星地图 ACG | `acg` |
| 名人库 celebrity data | `astrodata` (read-only, no confirmation gate) |
| Astrology dice 西占游戏 | `otherbu` |
| 14 神数 | `wangji` / `wuzhao` / `taixuan` / `jingjue` / `shenyishu` / `shaozi` / `tieban` / `fendjing` / `beiji` / `nanji` / `chunzi` / `xianqin` / `cetian` / `qizhengkin` |
| 节气 / 农历 | `jieqi_year` / `nongli_time` |
| 黄历 / 万年历 | `calendar_month` |
| Hover knowledge + 方法论手册 | `knowledge_registry`, `knowledge_read`（24 域 = hover 三域 + 各技法操作手册域，逐条带出处） |
| Export protocol | `export_registry`, `export_parse` |
| Natural-language dispatch | `horosa_dispatch` (MCP) |
| 合参（多技法交叉印证） | `horosa_hecan`（模板制：结论槽留白，分歧必须披露；细则见 [`references/reports.md`](./references/reports.md)） |

Fengshui is intentionally excluded from this public skill surface (not headless-ready).

**引知识必带出处（v0.28.0 反 Barnum 第一机制）**：解读中引用口径/流派/教义时，先用
`knowledge_read` 取条目并转述其 `citation`（形如「星阙操作手册 · 八字四柱 · 算法与口径」）；
`knowledge_read` 没有的内容按通则推理并**明说无出处**。不许把通则包装成「古籍说」「星阙口径」。

Payload shapes and defaults: [`references/payloads.md`](./references/payloads.md). 中式技法 specifics
(大六壬 guirengType, current-time casting, 法奇门 sections):
[`references/chinese-methods.md`](./references/chinese-methods.md).

## Interpretation Style

Answer like a careful consultant: start with the direct conclusion; cite the actual chart/pan sections
that support it; explain the reasoning path in human language; separate opportunity, risk, timing, and
suggested action; with no specific question give a comprehensive overall reading, with a specific
question prioritize it over textbook generalities; mention limitations without hiding behind them.
Quote the `排盘规则: …` line back to the user when present (see `references/late-zi.md`). Report-body
style rules: [`references/reports.md`](./references/reports.md).

## Validation Checklist

Before telling the user a result is ready:

- `ok` is `true`; a failed tool returns `ok=False` with an `error.code` (e.g. `tool.internal_error`,
  `tool.ken_compute_failed`) — it does not throw. Read and relay the error; a failure is not
  “the tool is unavailable”.
- `export_snapshot.export_text` present (calculation tools); `export_snapshot.sections` non-empty;
  no section body is a bare `"无"`.
- The answer contains no dependency hallucinations (MongoDB, 7897, Xingque Desktop, remote DB).
- If a report was generated: the artifact path exists with non-zero size.
- If memory was used: `memory_show` / `memory_query` can retrieve the run.

Anything off → [`references/troubleshooting.md`](./references/troubleshooting.md) (symptom table,
debug commands, stale-runtime signals like `source: null`).

## Maintainer Pointer

Modifying/building/releasing this repo is governed by [`AGENTS.md`](../../AGENTS.md) — routing (§0),
iron laws (§1), and the **🔴 problem-logging protocol v2 (§2)**: every gotcha lands in
`docs/LESSONS.md` + a distilled rule + `CHANGELOG.md` + a machine guard, in the same change; sync this
skill doc whenever a lesson is client-facing, and never leave the two contradicting. Engine credit:
the ken engines (`kinqimen` / `kintaiyi` / `kinjinkou`, MIT, by **kentang2017**) ship their LICENSE
files inside the runtime and are acknowledged in `README.md` / `README_EN.md` — see AGENTS.md §11.
