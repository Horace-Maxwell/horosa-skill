[简体中文](./README.md) | **English**

<div align="center">
  <h1>Horosa Skill</h1>
  <p><strong>Turn Xingque / Horosa into a local-first occult capability layer that any AI can call.</strong></p>
  <p>Clone the repo, install one offline runtime, and let Claude, Codex, Open WebUI, OpenClaw, or any MCP-capable client invoke real Xingque methods locally, consume full export contracts, and persist every analysis as structured memory.</p>

  <p>
    <a href="https://github.com/Horace-Maxwell/horosa-skill">
      <img src="https://img.shields.io/badge/GitHub-Repository-111827?style=for-the-badge&logo=github" alt="Repository" />
    </a>
    <a href="https://github.com/Horace-Maxwell/horosa-skill/releases">
      <img src="https://img.shields.io/badge/GitHub-Releases-1d4ed8?style=for-the-badge&logo=github" alt="Releases" />
    </a>
    <a href="./README.md">
      <img src="https://img.shields.io/badge/Read%20in-Chinese-0f766e?style=for-the-badge" alt="Read in Chinese" />
    </a>
  </p>

  <p>
    <img src="https://img.shields.io/github/stars/Horace-Maxwell/horosa-skill?style=flat-square" alt="GitHub stars" />
    <img src="https://img.shields.io/github/v/release/Horace-Maxwell/horosa-skill?display_name=tag&style=flat-square" alt="Release" />
    <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows-0f766e?style=flat-square" alt="Platforms" />
    <img src="https://img.shields.io/badge/runtime-offline%20first-111827?style=flat-square" alt="Offline runtime" />
    <img src="https://img.shields.io/badge/MCP-ready-111827?style=flat-square" alt="MCP ready" />
    <img src="https://img.shields.io/badge/storage-SQLite%20%2B%20JSON-111827?style=flat-square" alt="SQLite and JSON" />
  </p>

  <p>
    <a href="./LICENSE">
      <img src="https://img.shields.io/badge/License-Apache--2.0-374151?style=flat-square" alt="License" />
    </a>
    <a href="./CONTRIBUTING.md">
      <img src="https://img.shields.io/badge/Contributing-Guide-0f766e?style=flat-square" alt="Contributing" />
    </a>
    <a href="./SECURITY.md">
      <img src="https://img.shields.io/badge/Security-Policy-991b1b?style=flat-square" alt="Security" />
    </a>
  </p>

  <p>
    <a href="./SUPPORT.md">
      <img src="https://img.shields.io/badge/Support-Paths-1d4ed8?style=flat-square" alt="Support" />
    </a>
    <a href="./CITATION.cff">
      <img src="https://img.shields.io/badge/Citation-CFF-7c3aed?style=flat-square" alt="Citation" />
    </a>
    <a href="./CHANGELOG.md">
      <img src="https://img.shields.io/badge/Changelog-Updates-f59e0b?style=flat-square" alt="Changelog" />
    </a>
  </p>
</div>

## What This Repository Is

Xingque already had the hard parts: deep local algorithms, ephemeris-backed runtime behavior, rich AI export settings, and serious occult method coverage. `Horosa Skill` is the GitHub-first delivery surface that makes those capabilities usable by modern AI systems without turning the repo into a giant runtime dump.

This repository is built to solve five practical problems:

- Install a complete offline runtime from GitHub Releases.
- Expose real Xingque methods through `MCP` and a `JSON-first CLI`.
- Turn every method output into a high-signal, sectioned, machine-readable export contract.
- Persist every run, query, tool result, and final AI answer into a local retrieval-friendly record layer.
- Keep the repository lightweight and reviewable while shipping full runtime assets separately.

If the goal is “clone once, install once, and let AI call real Horosa methods locally on any machine,” this repo is designed for exactly that.

## What It Can Do Today

### High-level capability map

| Layer | What ships now | What that means |
| --- | --- | --- |
| Offline runtime | macOS and Windows release assets installable from GitHub Releases | Users can run locally after install, including offline usage |
| AI surface | `MCP server` + `JSON-first CLI` + `ask / dispatch` orchestration | Claude, Codex, Open WebUI, and OpenClaw can all integrate cleanly |
| Method execution | `39` callable tools across charts, predictive work, occult domains, export tooling, and hover knowledge access | This is a real local capability surface, not just prompt glue |
| Output contract | Every supported method emits stable envelopes plus `export_snapshot` / `export_format` | Machines can consume outputs repeatedly without guesswork |
| Knowledge access | Local bundled Xingque hover knowledge for astrology, LiuReng, and Qimen | AI can ask for explanation layers as well as raw calculation layers |
| Local memory | SQLite + JSON artifacts + run manifest + answer write-back | Every invocation becomes a durable local record |
| Distribution model | Lightweight repository plus heavyweight release assets | Public history stays clean while runtime payloads stay complete |

### Feature pillars

- Real offline execution: no cloud divination API dependency after runtime install.
- Real tool surface: not prompt glue, but explicit schemas, explicit tools, and stable contracts.
- Real lifecycle storage: runs, artifacts, manifests, user questions, and final AI answers are persisted together.
- Real Xingque fidelity: outputs are cleaned toward Xingque export and hover-document style instead of loose summaries.
- Real GitHub packaging: lightweight public history, heavyweight runtime in Releases, product-like repo presentation.

### Directly callable tools

#### Export, orchestration, and knowledge

| Tool ID | Name | Purpose |
| --- | --- | --- |
| `export_registry` | Xingque export registry | Return the full machine-readable export registry |
| `export_parse` | Export text parser | Parse Xingque-style export text back into structured JSON |
| `horosa_dispatch` | Natural-language dispatcher | Choose methods from user intent and run them coherently |
| `knowledge_registry` | Hover knowledge catalog | List bundled astrology / LiuReng / Qimen knowledge domains and keys |
| `knowledge_read` | Hover knowledge reader | Read bundled Xingque hover content on demand and persist it |

#### Core charts and derived charts

| Tool ID | Name | Purpose |
| --- | --- | --- |
| `chart` | Standard chart | Generate the main western chart with full export output |
| `chart13` | Chart13 variant | Generate the `chart13` flavor |
| `hellen_chart` | Hellenistic chart | Generate a Hellenistic-leaning chart output |
| `guolao_chart` | Seven Governors / Guolao chart | Generate 七政四余 output |
| `india_chart` | Indian chart | Generate Indian astrology output |
| `relative` | Relationship / relative chart | Generate two-person or relational chart structures |
| `germany` | Midpoint / quantitative chart | Generate midpoint-based analysis output |

#### Predictive and timing systems

| Tool ID | Name | Purpose |
| --- | --- | --- |
| `solarreturn` | Solar return | Compute solar return output |
| `lunarreturn` | Lunar return | Compute lunar return output |
| `solararc` | Solar arc directions | Compute solar arc results |
| `givenyear` | Given-year analysis | Generate year-specific predictive output |
| `profection` | Profection | Compute annual profection |
| `pd` | Primary directions | Compute primary directions |
| `pdchart` | Primary direction chart | Render the chart-style primary direction output |
| `zr` | Zodiacal release | Compute zodiacal release |
| `firdaria` | Firdaria | Generate Firdaria timelines |
| `decennials` | Decennials | Generate decennial timing layers |

#### Chinese occult backbone

| Tool ID | Name | Purpose |
| --- | --- | --- |
| `ziwei_birth` | Zi Wei birth chart | Generate Zi Wei chart output |
| `ziwei_rules` | Zi Wei rules | Return Zi Wei rules and structure info |
| `bazi_birth` | BaZi birth chart | Generate Four Pillars chart output |
| `bazi_direct` | BaZi direct reading | Generate direct-interpretation BaZi output |
| `liureng_gods` | Da Liu Ren main reading | Generate Da Liu Ren course / gods output |
| `liureng_runyear` | Da Liu Ren annual timing | Generate LiuReng run-year output |
| `qimen` | Qimen Dunjia | Generate Qimen layout, palace details, and divination sections |
| `taiyi` | Taiyi | Generate Taiyi output and palace markers |
| `jinkou` | Jinkou Jue | Generate Jinkou output |

#### Phase 2 local methods

| Tool ID | Name | Purpose |
| --- | --- | --- |
| `tongshefa` | Tong She Fa | Generate the Tong She Fa structure |
| `sanshiunited` | San Shi United | Aggregate Qimen, Taiyi, and LiuReng into one result |
| `suzhan` | Su Zhan / lunar mansion chart | Generate宿占 output |
| `sixyao` | Six Yao / hexagram reading | Generate base hexagram, changed hexagram, and line state output |
| `otherbu` | Astrology dice / western game method | Generate dice-like western symbolic output |

#### Calendar and hexagram support

| Tool ID | Name | Purpose |
| --- | --- | --- |
| `jieqi_year` | Annual Jieqi grid | Generate annual solar-term structures |
| `nongli_time` | Lunar calendar conversion | Convert to Nongli / Ganzhi time information |
| `gua_desc` | Hexagram description | Return hexagram name and core text |
| `gua_meiyi` | Mei Yi hexagram explanation | Return Meiyi-oriented hexagram explanation |

### Xingque AI export protocol domains already modeled

This repository also exposes Xingque’s export registry as a machine-readable protocol layer. The following `technique` domains are already modeled and reusable:

| technique ID | Meaning |
| --- | --- |
| `astrochart` | standard chart export |
| `astrochart_like` | chart-like export variant |
| `indiachart` | Indian chart export |
| `relative` | relationship chart export |
| `primarydirect` | primary directions export |
| `primarydirchart` | primary directions chart export |
| `zodialrelease` | zodiacal release export |
| `firdaria` | Firdaria export |
| `decennials` | decennials export |
| `solarreturn` | solar return export |
| `lunarreturn` | lunar return export |
| `solararc` | solar arc export |
| `givenyear` | given-year export |
| `profection` | profection export |
| `bazi` | BaZi export |
| `ziwei` | Zi Wei export |
| `suzhan` | Su Zhan export |
| `sixyao` | Six Yao export |
| `tongshefa` | Tong She Fa export |
| `liureng` | Da Liu Ren export |
| `jinkou` | Jinkou export |
| `qimen` | Qimen export |
| `taiyi` | Taiyi export |
| `sanshiunited` | unified three-method export |
| `guolao` | seven governors export |
| `germany` | midpoint / quantitative export |
| `jieqi` | main Jieqi export |
| `jieqi_meta` | Jieqi metadata export |
| `jieqi_chunfen` | spring equinox domain |
| `jieqi_xiazhi` | summer solstice domain |
| `jieqi_qiufen` | autumn equinox domain |
| `jieqi_dongzhi` | winter solstice domain |
| `otherbu` | western game / dice export |
| `generic` | generic export domain |

### Explicit shipping exclusion

- `fengshui`

## Bundled Xingque Hover Knowledge Is Also Available

This repository now ships a local bundled knowledge layer for Xingque hover / popover content, so AI systems and users can read those explanations on demand without depending on the original app source tree.

Current bundled domains:

- Astrology: `planet`, `sign`, `house`, `lot`, `aspect`
- Da Liu Ren: `shen`, `house`
- Qimen Dunjia: `stem`, `door`, `star`, `god`

That means users can directly read:

- full hover explanations for chart planets, signs, houses, aspects, and lots
- full hover content for LiuReng earthly branch shen entries and house overlays
- full hover content for Qimen stems, doors, stars, and gods

Those reads are also persisted and queryable like any other tool call.

## Why The Output Layer Matters

Every tool returns a stable envelope:

```json
{
  "ok": true,
  "tool": "qimen",
  "version": "0.3.0",
  "input_normalized": {},
  "data": {},
  "summary": [],
  "warnings": [],
  "memory_ref": {},
  "error": null
}
```

Methods wired into the Xingque export system also attach:

- `data.export_snapshot`
- `data.export_format`
- `data.export_snapshot.snapshot_text`
- `data.export_snapshot.sections`
- `data.export_snapshot.selected_sections`

That means:

- AI systems do not need to reverse-engineer loose prose.
- Repeated calls keep the same semantic structure.
- `horosa_dispatch` also exposes export contracts for every child result.
- Stored JSON artifacts preserve the same cleaned structure.

## Local Data Management

By default, local records are stored under:

- macOS / Linux: `~/.horosa-skill/`
- Windows: `%APPDATA%/HorosaSkill/`

Each run can store:

- run metadata
- tool call records
- entity references
- JSON artifacts
- one `run manifest`
- original `query_text`
- `user_question`
- final `ai_answer_text`
- optional `ai_answer_structured`

This project already supports:

- `memory query`
  query history by tool, entity, or run id
- `memory show <run_id>`
  inspect one exact run end-to-end
- `memory answer --stdin`
  write the AI’s final answer back into an existing run

So the repository is not just an execution layer. It is also a local retrieval layer.

## Quick Start

```bash
cd horosa-skill
uv sync
uv run horosa-skill install
uv run horosa-skill doctor
uv run horosa-skill serve
```

Default MCP endpoint:

```text
http://127.0.0.1:8765/mcp
```

For stdio-based clients such as Claude Desktop:

```bash
cd horosa-skill
uv run horosa-skill serve --transport stdio
```

## Fastest Usable Workflow

### 1. Install and verify the offline runtime

```bash
cd horosa-skill
uv sync
uv run horosa-skill install
uv run horosa-skill doctor
```

### 2. Let the dispatcher select methods

```bash
echo '{
  "query":"Please combine qimen, liureng, and chart methods to analyze the current state",
  "birth":{"date":"1990-01-01","time":"12:00","zone":"8","lat":"31n14","lon":"121e28"},
  "save_result": true
}' | uv run horosa-skill ask --stdin
```

### 3. Inspect one exact run

```bash
uv run horosa-skill memory show <run_id>
```

### 4. Attach the AI’s final answer

```bash
echo '{
  "run_id":"<run_id>",
  "user_question":"What does this imply for my career next?",
  "ai_answer":"The pattern is cautious first, then gradually upward.",
  "ai_answer_structured":{"trend":"up_later"}
}' | uv run horosa-skill memory answer --stdin
```

## Common Usage Patterns

### Dump the export registry

```bash
cd horosa-skill
uv run horosa-skill export registry
```

### Parse Xingque export text into structured JSON

```bash
echo '{
  "technique":"qimen",
  "content":"[起盘信息]\nparams\n\n[八宫]\nbody\n\n[演卦]\nbody"
}' | uv run horosa-skill export parse --stdin
```

### Run one atomic tool directly

```bash
echo '{"date":"1990-01-01","time":"12:00","zone":"8","lat":"31n14","lon":"121e28"}' \
  | uv run horosa-skill tool run chart --stdin
```

### Read bundled Xingque hover knowledge directly

```bash
echo '{"domain":"astro","category":"planet","key":"Sun"}' \
  | uv run horosa-skill knowledge read --stdin
```

```bash
echo '{"domain":"liureng","category":"shen","key":"子"}' \
  | uv run horosa-skill knowledge read --stdin
```

```bash
echo '{"domain":"qimen","category":"door","key":"休门"}' \
  | uv run horosa-skill knowledge read --stdin
```

### Run one Phase 2 local method

```bash
echo '{"taiyin":"巽","taiyang":"坤","shaoyang":"震","shaoyin":"震"}' \
  | uv run horosa-skill tool run tongshefa --stdin
```

### Run the unified dispatcher

```bash
echo '{
  "query":"Please analyze the current situation using qimen, liureng, and chart methods",
  "birth":{"date":"1990-01-01","time":"12:00","zone":"8","lat":"31n14","lon":"121e28"},
  "save_result": true
}' | uv run horosa-skill dispatch --stdin
```

## AI Client Integrations

- [Claude Desktop config example](./horosa-skill/examples/clients/claude_desktop_config.json)
- [Codex config example](./horosa-skill/examples/clients/codex-config.toml)
- [Open WebUI setup](./horosa-skill/examples/clients/openwebui-streamable-http.md)
- [OpenClaw setup](./horosa-skill/examples/clients/openclaw-mcp.md)

## Runtime And Release Strategy

This repository intentionally separates three layers:

| Layer | Lives where | Purpose |
| --- | --- | --- |
| Public repo layer | GitHub repository | code, docs, CLI, MCP, tests, examples, release scripts |
| Maintainer packaging input | `vendor/runtime-source/` | large local inputs required to build offline runtime releases |
| End-user runtime | `~/.horosa/runtime/current` or `%LOCALAPPDATA%/Horosa/runtime/current` | the actual installed runtime used for local execution |

This keeps the GitHub surface clean while still preserving full offline distribution.

## Repository Layout

| Path | Role |
| --- | --- |
| [`horosa-skill/`](./horosa-skill) | core Python package, CLI, MCP server, tests, examples, release scripts |
| [`docs/`](./docs) | runtime specs, coverage docs, release documentation, maintainer notes |
| [`vendor/`](./vendor) | local runtime packaging input area |

Useful documents:

- [Repo Layout](./docs/REPO_LAYOUT.md)
- [Offline Runtime Releases](./docs/OFFLINE_RUNTIME_RELEASES.md)
- [Runtime Manifest Spec](./docs/RUNTIME_MANIFEST_SPEC.md)
- [Algorithm Coverage](./docs/ALGORITHM_COVERAGE.md)
- [Vendored Runtime Sources](./vendor/README.md)

## Current Status

Already implemented:

- GitHub-first offline runtime install flow
- macOS and Windows runtime release assets
- local MCP server and JSON-first CLI
- full Xingque AI export registry and parser
- stable structured outputs across 39 callable tools
- bundled and queryable hover knowledge for chart, LiuReng, and Qimen
- dispatch-level child export contracts
- SQLite + JSON artifacts + run manifest data model
- AI answer write-back and retrieval workflow
- real fresh-clone validation from GitHub plus runtime reinstall

If you need a repository that turns Xingque into AI-callable infrastructure rather than a pile of loose scripts, this project is already operating in that direction.
