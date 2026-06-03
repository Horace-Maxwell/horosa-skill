[简体中文](./README.md) | **English**

<div align="center">
  <h1>Horosa Skill</h1>
  <p><strong>Turn Xingque / Horosa into an offline metaphysics capability layer any AI can call locally.</strong></p>
  <p>Clone the repo, install the offline runtime once, and let Claude, Codex, Open WebUI, OpenClaw, etc. call <strong>68</strong> real techniques on your own machine — Western natal / predictive / horary / electional, BaZi / Zi Wei / Da Liu Ren / the Three Styles, and all <strong>14 Shen Shu</strong> systems — read the full Xingque AI-export protocol, return stable structured output, and persist every analysis as a retrievable local record. Works offline, value-for-value identical to the Xingque desktop app.</p>

  <p><a href="https://github.com/Horace-Maxwell/horosa-skill"><img src="https://img.shields.io/badge/GitHub-Repository-111827?style=for-the-badge&logo=github" alt="Repository" /></a>&nbsp;<a href="https://github.com/Horace-Maxwell/horosa-skill/releases"><img src="https://img.shields.io/badge/GitHub-Releases-1d4ed8?style=for-the-badge&logo=github" alt="Releases" /></a>&nbsp;<a href="./README.md"><img src="https://img.shields.io/badge/阅读-简体中文-0f766e?style=for-the-badge" alt="Read in Chinese" /></a></p>

  <p>
    <img src="https://img.shields.io/github/stars/Horace-Maxwell/horosa-skill?style=flat-square" alt="GitHub stars" />
    <img src="https://img.shields.io/github/v/release/Horace-Maxwell/horosa-skill?display_name=tag&style=flat-square" alt="Release" />
    <img src="https://img.shields.io/badge/tools-68-1d4ed8?style=flat-square" alt="68 tools" />
    <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows-0f766e?style=flat-square" alt="Platforms" />
    <img src="https://img.shields.io/badge/runtime-offline%20first-111827?style=flat-square" alt="Offline runtime" />
    <img src="https://img.shields.io/badge/MCP-ready-111827?style=flat-square" alt="MCP ready" />
    <img src="https://img.shields.io/badge/storage-SQLite%20%2B%20JSON-111827?style=flat-square" alt="SQLite and JSON" />
  </p>

  <p><a href="./LICENSE"><img src="https://img.shields.io/badge/License-AGPL--3.0-374151?style=flat-square" alt="License" /></a>&nbsp;<a href="./CONTRIBUTING.md"><img src="https://img.shields.io/badge/Contributing-Guide-0f766e?style=flat-square" alt="Contributing" /></a>&nbsp;<a href="./SECURITY.md"><img src="https://img.shields.io/badge/Security-Policy-991b1b?style=flat-square" alt="Security" /></a>&nbsp;<a href="./SUPPORT.md"><img src="https://img.shields.io/badge/Support-Paths-1d4ed8?style=flat-square" alt="Support" /></a>&nbsp;<a href="./CITATION.cff"><img src="https://img.shields.io/badge/Citation-CFF-7c3aed?style=flat-square" alt="Citation" /></a>&nbsp;<a href="./CHANGELOG.md"><img src="https://img.shields.io/badge/Changelog-Updates-f59e0b?style=flat-square" alt="Changelog" /></a></p>
</div>

---

## In one sentence

Xingque already has a complete local engine, ephemeris, export settings, and a multi-technique system. **Horosa Skill does not rebuild a simplified calculator** — it packages those capabilities into a product-grade interface layer made for GitHub distribution, AI invocation, and long-term local management: the engine runs on your machine, the output is stable JSON + Xingque-style export snapshots, and every call is automatically written as a retrievable local knowledge record.

It solves five things:

- **Get it and use it** — clone from GitHub, install the full offline runtime from GitHub Releases, then run offline.
- **A real AI interface** — call genuine Xingque methods over `MCP` or a `JSON-first CLI`, not a loose prompt layer.
- **Stable & consumable** — every technique returns a uniform envelope + Xingque-style `export_snapshot` / `export_format`; neither machine nor human has to guess fields.
- **Manageable long-term** — one call = one traceable record (run / artifact / manifest / final AI answer).
- **Light repo** — code, docs, CLI, MCP, tests in Git; the heavy runtime in Releases.

License: the repo is published under `GNU AGPL-3.0-only` (root [LICENSE](./LICENSE)). The three bundled third-party `ken` engines are used under their own MIT licenses (see [Credits](#credits-the-bundled-open-source-ken-engines)).

## Documentation map

| Doc | Content |
| --- | --- |
| [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) | Architecture |
| [`docs/INPUT_CONTRACTS.md`](./docs/INPUT_CONTRACTS.md) | Per-tool input contracts (required fields) |
| [`docs/DATA_CONTRACTS.md`](./docs/DATA_CONTRACTS.md) | Output / envelope / export data contracts |
| [`docs/EXPORT_AUDIT_GUIDE.md`](./docs/EXPORT_AUDIT_GUIDE.md) | Section-by-section audit method for predictive exports |
| [`docs/OPERATIONS.md`](./docs/OPERATIONS.md) · [`docs/EVALUATION.md`](./docs/EVALUATION.md) | Operations · evaluation |
| [`docs/OFFLINE_RUNTIME_RELEASES.md`](./docs/OFFLINE_RUNTIME_RELEASES.md) | Offline runtime packaging & release |
| [`server.json`](./server.json) · [`skills/horosa-agent/SKILL.md`](./skills/horosa-agent/SKILL.md) · [`AGENTS.md`](./AGENTS.md) | MCP metadata · agent skill · repo rules |

## Current stable baseline

**Current public version: `Horosa Skill 0.9.2` (68 callable tools).**

This release line brings the capability surface roughly to parity with the desktop app:

- **Full Western astrology** — natal and derived charts, 10 classic return/progression/timeline tools, 3 v2.4.0 Western additions (Age Point / Distributions / mundane ingress), 7 v2.5.0 progressions (Jayne declination / Vedic sidereal / Planetary Arc / Ages of Man / Balbillus / 129-year system / Persian Directed), plus full **horary** and **electional** judgment engines.
- **Chinese metaphysics core** — BaZi, Zi Wei, Da Liu Ren, Qi Men, Tai Yi, Jin Kou Jue, the Three Styles unified, Tong She Fa, He Luo Li Shu, Shao Zi Can Ping Shu, harmonic charts, Su Zhan, Liu Yao.
- **All 14 Shen Shu** — 5 standalone (Huang Ji Jing Shi / Wu Zhao / Tai Xuan / Jing Fang Yi / Shen Yi Shu) + 9 (Shao Zi / Tie Ban / Fen Jing / Bei Ji / Nan Ji / Chun Zi / Yan Qin / Ce Tian / Qi Zheng·Zhang Guo).
- **Same backend** — Qi Men / Tai Yi / Jin Kou Jue (and the Qi Men + Tai Yi inside the Three Styles) run on Xingque's `ken` backend (`kinqimen` / `kintaiyi` / `kinjinkou`); the 14 Shen Shu run on kentang engines mounted on the Xingque chart service; results are reformatted by the headless JS layer into `aiExport.js` sections. **The Skill and the Xingque desktop app share one backend, value-for-value identical.**

A hard protocol runs throughout: **the AI may not invent parameters**. Whenever a technique is affected by time, place, timezone, gender, topic, house system, calendar, or casting method, the agent cannot proceed until the user confirms — the tool returns a structured block with a question you can forward verbatim.

Local end-to-end signals:

| Check | Result |
| --- | --- |
| Callable tools | `68 / 68 ok=true` |
| Engineering tests | `227 / 227 pass` (ken / Shen Shu live integration + offline golden unit tests) |
| Forced clarification when params unconfirmed | `61` technique tools trigger `must_ask_user=true` |
| Safe-exempt tools | `7` registry / knowledge / parser tools are directly readable |
| Xingque-style export structure | every business technique carries `export_snapshot` / `export_format` (`63` export techniques modeled) |
| Local memory / report | `68 / 68` writes + `68 / 68` JSON artifacts |
| Qi Men / Tai Yi / Jin Kou / Three Styles | unified on `ken`, same as the desktop app |
| Tong She Fa / Decennials | headless, value-for-value with Xingque (`decennials.test.js` golden) |
| GitHub CI | Linux/macOS unit tests + horosa-core-js JS golden self-check + Windows OpenClaw smoke |
| Release runtime | macOS / Windows `v0.9.x` assets (ken + 14 Shen Shu engines bundled) packaged and verified |

> About `solarreturn` / `lunarreturn` / `solararc` / `givenyear` / `profection` / `pd` / `pdchart` / `zr`: these predictive tools are verified working in this version and should not be flagged by an agent as "Java `/predict/*` unavailable". If a client still says so, check whether it is on an old runtime, bypassing MCP to hand-compute, or hasn't run `doctor` / `openclaw-check --full`.

## Capability map (68 tools)

> Every business technique returns a uniform envelope plus a Xingque-style `export_snapshot` / `export_format`. Tools marked ⓟ are setting-sensitive and require parameter confirmation before calling.

### Western astrology · natal & derived charts

| Tool ID | Name | Notes |
| --- | --- | --- |
| `chart` ⓟ | Standard chart | Western natal chart + full AI export (Dodekatemoria / dispositor chain / hyleg lifespan) |
| `chart13` ⓟ | 13-house variant | `chart13` form |
| `hellen_chart` ⓟ | Hellenistic chart | Hellenistic-oriented chart |
| `india_chart` ⓟ | Indian chart | Vedic chart |
| `guolao_chart` ⓟ | Seven Governors (Guolao) | Seven Governors / Guo Lao chart |
| `relative` ⓟ | Synastry / relationship | Two-person relationship, composite, relative output |
| `germany` ⓟ | Cosmobiology / midpoints | Midpoint structures and quantitative analysis |

### Western astrology · returns / progressions / timelines (20)

| Tool ID | Name | Notes |
| --- | --- | --- |
| `solarreturn` ⓟ | Solar return | natal + return chart + aspects |
| `lunarreturn` ⓟ | Lunar return | natal + lunar return + aspects |
| `solararc` ⓟ | Solar arc | natal + directed chart + aspects |
| `givenyear` ⓟ | Given-year | natal + given-year chart + aspects |
| `profection` ⓟ | Profection | profection timeline |
| `pd` ⓟ | Primary directions | real primary-direction table |
| `pdchart` ⓟ | Primary-direction chart | readable PD chart + aspects |
| `zr` ⓟ | Zodiacal release | ZR timeline |
| `firdaria` ⓟ | Firdaria | Firdaria structure & timeline |
| `decennials` ⓟ | Decennials | decennials timeline (headless, Xingque golden) |
| `agepoint` ⓟ | Age Point / Huber | Koch-house age-point cycle (6 yrs/house) |
| `distributions` ⓟ | Distributions | Asc through the Egyptian bounds |
| `mundane` ⓟ | Mundane ingress | chart cast at a year's solar-term ingress moment |
| `jaynesprog` ⓟ | Jayne declination | secondary progression + declination parallels |
| `vedicprog` ⓟ | Vedic sidereal progression | progressions under the sidereal zodiac |
| `planetaryarc` ⓟ | Planetary Arc | whole chart directed by arcSource's secondary arc |
| `planetaryages` ⓟ | Ages of Man | Ptolemy seven ages + current band |
| `yearsystem129` ⓟ | 129-year system | seven-planet succession, 129-year cycle |
| `persiandirected` ⓟ | Persian Directed | symbolic 1°/year direction hit-list |
| `balbillus` ⓟ | Balbillus 129-year | exaltation-distance reduction + recursive sub-periods (vendored JS, identical to Xingque) |

### Western divination · horary / electional

| Tool ID | Name | Notes |
| --- | --- | --- |
| `horary` ⓟ | Horary | radicality / significators (14 categories) / perfection / moon story / verdict / timing |
| `election` ⓟ | Electional | hard flags / 28 topic rule packs / scoring / cast moment / recommendations |

### Chinese metaphysics core

| Tool ID | Name | Notes |
| --- | --- | --- |
| `bazi_birth` ⓟ / `bazi_direct` ⓟ | BaZi chart / direct reading | Four Pillars chart / direct reading |
| `ziwei_birth` ⓟ | Zi Wei Dou Shu | Zi Wei chart (`ziwei_rules` returns the rule base) |
| `liureng_gods` ⓟ / `liureng_runyear` ⓟ | Da Liu Ren / yearly | four lessons & three transmissions / runyear |
| `qimen` ⓟ | Qi Men Dun Jia | cast by ken (`kinqimen`), palace detail + gua |
| `taiyi` ⓟ | Tai Yi Shen Shu | cast by ken (`kintaiyi`), 16-palace marks |
| `jinkou` ⓟ | Jin Kou Jue | cast by ken (`kinjinkou`), quick reading |
| `sanshiunited` ⓟ | Three Styles unified | aggregates ken Qi Men + Tai Yi with Da Liu Ren |

### Local metaphysics · numerology · divination

| Tool ID | Name | Notes |
| --- | --- | --- |
| `tongshefa` ⓟ | Tong She Fa | gua, six lines, hidden, affinity (headless, Xingque parity) |
| `canping` ⓟ | Shao Zi Can Ping Shu | four-pillar numbers, verses (in-process, bundled `lunar-javascript`) |
| `heluo` ⓟ | He Luo Li Shu | pre/post-heaven gua, fate chapter, decade fortunes (in-process) |
| `harmonic` ⓟ | Harmonic chart | natal longitude × harmonic number, same-frequency conjunctions |
| `suzhan` ⓟ | Su Zhan | mansion-divination structure |
| `sixyao` ⓟ | Liu Yao / I Ching | hexagram, changing lines, question-oriented output |
| `otherbu` ⓟ | Astro dice | astrological dice + reading |

### Shen Shu (all 14)

> kentang engines mounted on the Xingque chart service; the backend emits the `snapshot` directly, with section headers matching the aiExport preset. `shaozi` / `tieban` / `cetian` / `qizhengkin` / `xianqin` also take gender (+ place).

| Tool ID | Name | Engine |
| --- | --- | --- |
| `wangji` ⓟ | Huang Ji Jing Shi · Xin Yi Fa Wei | standalone |
| `wuzhao` ⓟ | Wu Zhao | standalone |
| `taixuan` ⓟ | Tai Xuan · milfoil | standalone |
| `jingjue` ⓟ | Jing Fang Yi · Jing Jue | standalone |
| `shenyishu` ⓟ | Shen Yi Shu | standalone |
| `shaozi` ⓟ | Shao Zi Shen Shu | kinastro |
| `tieban` ⓟ | Tie Ban Shen Shu | kinastro |
| `fendjing` ⓟ | Fen Jing Shen Shu · Liang Tou Qian | kinastro |
| `beiji` ⓟ | Bei Ji Shen Shu | kinastro |
| `nanji` ⓟ | Nan Ji Shen Shu | kinastro |
| `chunzi` ⓟ | Chun Zi Shen Shu | kinastro |
| `xianqin` ⓟ | Yan Qin | kinastro |
| `cetian` ⓟ | Ce Tian Fei Xing · Zi Wei | kinastro |
| `qizhengkin` ⓟ | Seven Governors · Zhang Guo | kinastro |

### Solar terms / lunar calendar / gua · protocol / dispatch / knowledge

| Tool ID | Name | Notes |
| --- | --- | --- |
| `jieqi_year` ⓟ / `nongli_time` ⓟ | Year solar terms / lunar time | solar-term nodes / lunar ganzhi |
| `gua_desc` / `gua_meiyi` | Gua meaning / Mei Yi gua | hexagram names & texts / Plum-Blossom gua |
| `export_registry` / `export_parse` | Export registry / parser | machine-readable export table / parse Xingque export text back to JSON |
| `horosa_dispatch` | Dispatcher | takes natural-language intent and routes to the right technique |
| `knowledge_registry` / `knowledge_read` | Hover-knowledge catalog / reader | list / read Xingque in-app hover knowledge and persist it |

> **Explicitly excluded:** `fengshui` (not yet headless; we don't disguise unfinished capability as shippable). The 9 kinastro-* Shen Shu deferred in v0.9.0 are all shipped in v0.9.1.

## Hard rules for agents

This is the **most important** rule when wiring into Cursor, OpenClaw, Claude, Codex, Open WebUI.

If an agent is unsure of the user's settings before calling a technique, it should first query `horosa_agent_guidance` (CLI: `uv run horosa-skill agent guidance --tool <tool> --intent "..."`) — it tells the AI which fields must be asked first and which Xingque defaults may be used once the user accepts.

Calculation tools and `horosa_dispatch` are gated: if the agent didn't confirm settings it gets `agent_guidance.required`, and must pass `agent_confirmed_settings: true` after the user confirms, or `defaults_accepted: true` after the user explicitly accepts defaults. If the response has `details.agent_recovery.prompt_to_user`, the AI client must stop and forward that question to the user — it may not bypass or self-fill.

Standard flow: ① user states a need → ② agent checks if params suffice; if not, call `horosa_agent_guidance` or ask the user → ③ user confirms time/place/topic/whether to accept defaults → ④ agent calls the real tool with `agent_confirmed_settings: true` + `clarification_notes` → ⑤ explain from `export_snapshot` / `export_format`, not from a hand calculation.

❌ Blocked (missing confirmation, place, timezone, topic):

```json
{ "date": "2026-05-18", "time": "13:14:00" }
```

✅ Correct (user confirmation + full context):

```json
{
  "agent_confirmed_settings": true,
  "clarification_notes": "User confirmed: 2026-05-18 13:14:00, America/Los_Angeles, San Francisco, topic = current work decision.",
  "date": "2026-05-18", "time": "13:14:00", "zone": "-07:00",
  "lat": "37n46", "lon": "122w25", "gpsLat": 37.7667, "gpsLon": -122.4167,
  "after23NewDay": false
}
```

When the user says "use Xingque defaults", switch to `{ "defaults_accepted": true, "clarification_notes": "User explicitly accepted Xingque defaults." }` — but the agent **must not** set `defaults_accepted: true` on the user's behalf.

> Timezone accepts both fixed offsets (`+08:00` / `-07:00`) and IANA names (`America/Los_Angeles` / `Asia/Shanghai`); Horosa Skill normalizes to a backend-stable offset using the chart's date and time.

## Output protocol: the point is "stably consumable", not just "compute"

Every tool call returns a uniform envelope:

```json
{
  "ok": true, "tool": "qimen", "version": "0.9.2",
  "input_normalized": {}, "data": {}, "summary": [],
  "warnings": [], "memory_ref": {}, "error": null
}
```

Techniques wired into the Xingque export protocol also carry `data.export_snapshot` (with `.snapshot_text` / `.sections` / `.selected_sections`) and `data.export_format`. So: the AI doesn't guess structure from free text; repeated calls of one technique return the same contract; `horosa_dispatch`'s aggregation layer carries each sub-result's export contract; and the structure survives into the JSON artifact. Full field tables: [`docs/DATA_CONTRACTS.md`](./docs/DATA_CONTRACTS.md) and [`docs/INPUT_CONTRACTS.md`](./docs/INPUT_CONTRACTS.md).

## Data management: a full local record system

Local data defaults to `~/.horosa-skill/` (Windows: `%APPDATA%/HorosaSkill/`). Each run persists: run metadata, tool-call records, an entity index, JSON artifacts, a `run manifest`, the raw `query_text`, the user's `user_question`, the final `ai_answer_text`, and optional `ai_answer_structured`.

```bash
uv run horosa-skill memory query                 # query history by tool / entity / run_id
uv run horosa-skill memory show <run_id>          # replay one full call
echo '{"run_id":"<run_id>","user_question":"...","ai_answer":"...","ai_answer_structured":{}}' \
  | uv run horosa-skill memory answer --stdin     # write the final AI answer back to a record
```

This makes it not just a "tool layer" but a "tool layer + traceable knowledge base".

## Quick start

```bash
cd horosa-skill
uv sync
uv run horosa-skill install      # install the offline runtime from a GitHub Release
uv run horosa-skill doctor       # confirm runtime is ready (expect issues: [])
uv run horosa-skill serve        # start local MCP (default http://127.0.0.1:8765/mcp)
```

For stdio clients like Claude Desktop: `uv run horosa-skill serve --transport stdio`.

### Let the dispatcher pick the technique

```bash
echo '{
  "agent_confirmed_settings": true,
  "clarification_notes": "User confirmed: sample birth data, Shanghai, +08:00, Xingque defaults.",
  "query":"Analyze my current situation across Qi Men, Liu Ren, and the chart",
  "birth":{"date":"1990-01-01","time":"12:00","zone":"+08:00","lat":"31n14","lon":"121e28"},
  "save_result": true
}' | uv run horosa-skill ask --stdin
```

### Call a single tool / read hover knowledge / parse export text

```bash
echo '{"agent_confirmed_settings":true,"clarification_notes":"sample chart, Shanghai defaults","date":"1990-01-01","time":"12:00","zone":"+08:00","lat":"31n14","lon":"121e28","gpsLat":31.2333,"gpsLon":121.4667}' \
  | uv run horosa-skill tool run chart --stdin
echo '{"domain":"qimen","category":"door","key":"休门"}' | uv run horosa-skill knowledge read --stdin
echo '{"technique":"qimen","content":"[起盘信息]\n参数\n\n[八宫]\n八宫内容"}' | uv run horosa-skill export parse --stdin
uv run horosa-skill export registry
```

> If an agent calls Qi Men / Tai Yi / Liu Yao with too few params and `/nongli/time` returns `200001 param error`, have it use `horosa_agent_guidance` to ask for date / time / timezone / lat-lon and defaults first; Horosa Skill also retries Xingque-compatible date formats against the Java endpoint so a backend format error isn't mistaken for an unavailable algorithm.

## Supported AI clients

- [Claude Desktop config example](./horosa-skill/examples/clients/claude_desktop_config.json)
- [Codex config example](./horosa-skill/examples/clients/codex-config.toml)
- [Open WebUI integration](./horosa-skill/examples/clients/openwebui-streamable-http.md)
- [OpenClaw integration](./horosa-skill/examples/clients/openclaw-mcp.md)

For OpenClaw / mcporter, prefer the generator to avoid hand-editing JSON and paths:

```bash
cd horosa-skill
uv run horosa-skill client openclaw-setup --workspace ~/.openclaw/workspace
uv run horosa-skill client openclaw-check --workspace ~/.openclaw/workspace
```

> If `openclaw-check` passes and `horosa__...` tools appear in a real session but the agent trace still shows `clientToolCount: 0`, that's stale trajectory-stat noise — restart OpenClaw or open a new session; don't let the agent fall back to Shell / Python hand-computation.

## Credits: the bundled open-source ken engines

Qi Men Dun Jia / Tai Yi Shen Shu / Jin Kou Jue (and the Qi Men + Tai Yi inside the Three Styles) are computed by three open-source Python engines from **[kentang2017](https://github.com/kentang2017)**. Xingque wired them into its backend; Horosa Skill reuses the same compute path and ships them with the offline runtime:

- **kinqimen** (Qi Men Dun Jia) — MIT — <https://github.com/kentang2017/kinqimen>
- **kintaiyi** (Tai Yi Shen Shu) — MIT — <https://github.com/kentang2017/kintaiyi>
- **kinjinkou** (Jin Kou Jue) — MIT — <https://github.com/kentang2017/kinjinkou>

Full copyright and license text ships in `Horosa-Web/vendor/{kinqimen,kintaiyi,kinjinkou}/LICENSE` and is preserved on distribution.

**License attribution:** the three `ken` engines above are third-party MIT components (by kentang2017). Every other metaphysics implementation here — Tong She Fa, Decennials, and the `aiExport.js` formatting + headless adapters for Qi Men / Tai Yi / Jin Kou / Da Liu Ren / charts / progressions / horary / electional / Shen Shu — is **Xingque's own algorithm**, licensed under the root `GNU AGPL-3.0-only`. The traditional systems themselves (Jing Fang's eight palaces, Hellenistic decennials, etc.) are public knowledge and constitute no third-party copyright.

## Release & runtime strategy

The repo is intentionally split into three layers:

| Layer | Where | Role |
| --- | --- | --- |
| Public repo | GitHub repo | code, docs, CLI, MCP, tests, examples, packaging scripts |
| Maintainer packaging inputs | `vendor/runtime-source/` | large inputs to build the offline runtime (not in Git history) |
| End-user runtime | `~/.horosa/runtime/current` / `%LOCALAPPDATA%/Horosa/runtime/current` | the local runtime users actually execute after install |

This keeps the GitHub page clean, the Release assets complete, local execution offline, and the maintainer packaging flow independent of sibling directories. Further reading: [Offline Runtime Releases](./docs/OFFLINE_RUNTIME_RELEASES.md) · [Runtime Manifest Spec](./docs/RUNTIME_MANIFEST_SPEC.md) · [Repo Layout](./docs/REPO_LAYOUT.md).

## Repository layout

| Path | Description |
| --- | --- |
| [`horosa-skill/`](./horosa-skill) | Core Python package, CLI, MCP server, `horosa-core-js` (headless JS engines), tests, examples, release scripts |
| [`docs/`](./docs) | runtime spec, algorithm coverage, release docs, maintainer docs |
| [`vendor/`](./vendor) | local runtime packaging inputs |

## Verification checklist

After a fresh clone, to confirm "this isn't an empty shell", run this minimal set:

```bash
cd horosa-skill
uv sync
uv run horosa-skill install
uv run horosa-skill doctor                              # expect issues: []
uv run pytest -q                                        # 227 passed
uv run python scripts/run_benchmark.py                  # HorosaBench: dispatch / export parity / knowledge
uv run python scripts/run_full_self_check.py --rounds 1 # all-tool call / export / persist / retrieve / dispatch
```

The full self-check covers: each tool is callable → returns a uniform envelope → business techniques carry `export_snapshot` / `export_format` → export text re-parses → the run is written to memory → `memory show/query` retrieves it → report JSON/DOCX/PDF generate and register artifacts → `horosa_dispatch`'s aggregation layer keeps sub-tool export contracts → OpenClaw / mcporter see the MCP tools and complete smoke/full check.

> **When auditing predictive / Shen Shu tools, don't read only the short preview.** Their Xingque-style body usually writes the natal chart first, then the return / progressed / annual / primary-direction / Shen Shu tables; a 1200-char prefix may show only the natal chart. Open the full artifact and check each `export_format.sections`. See [`docs/EXPORT_AUDIT_GUIDE.md`](./docs/EXPORT_AUDIT_GUIDE.md).

## Is the output identical to Xingque?

"Identical to Xingque" means two things:

1. **Identical export structure** — business techniques generate a Xingque-style `export_snapshot.export_text`, parsed by `snapshot_parser` into `export_format`; the full self-check confirms no missing or unknown sections.
2. **Identical compute path** — the Skill forbids agents from hand-computing charts with shell / Python / web search. Qi Men / Tai Yi / Jin Kou and the Qi Men+Tai Yi in the Three Styles are computed exclusively by the ken backend; the 14 Shen Shu by the kentang engines on the chart service; horary / electional / Balbillus by the vendored Xingque frontend engines — all same-source.

> Content fidelity was byte-checked: running Xingque's actual frontend builder on the same chart, the ages / aspects / promittors / significators are identical; only Persian Directed's hit dates differ by ≤1 day (moment's fractional-day truncation + JS↔Python float), which is astrologically negligible and documented (see [`horosa-skill/docs/v091-fidelity-spotcheck.md`](./horosa-skill/docs/v091-fidelity-spotcheck.md)). To prove a specific input matches the Xingque desktop UI field-for-field, put Xingque's golden snapshot for that input into fixtures and diff.

## FAQ / boundaries

**Why isn't the release a pure cloud build?** Because the full runtime depends on locally maintained runtime sources and platform runtimes. Keeping the repo light is a goal, but the full runtime still needs reliable local packaging inputs — hence "light repo + heavy release + explicit verification".

**Why keep stressing `export_snapshot` / `export_format`?** Because one of the project's core values is "let the AI stably consume Xingque output". Without this contract the AI can only read loose text, and retrieval / comparison / write-back / evaluation all become brittle.

**Why keep both SQLite and JSON?** SQLite handles structured indexing and queries; JSON artifacts handle long-term archival — portable, diffable, reviewable.

**Why isn't `fengshui` in the surface yet?** The current goal is the "complete, headless, offline-verifiable" surface. `fengshui` stays excluded; we don't disguise an un-headless capability as shippable.

**What's the most important quality signal?** Not badges or screenshots, but whether these four hold at once: tools really call · exports are really stable structured · results really persist and write back · benchmark / self-check really keep passing.
