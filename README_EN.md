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
    <img src="https://img.shields.io/github/stars/Horace-Maxwell/horosa-skill?style=for-the-badge" alt="GitHub stars" />
    <img src="https://img.shields.io/github/v/release/Horace-Maxwell/horosa-skill?display_name=tag&style=for-the-badge" alt="Release" />
    <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows-0f766e?style=for-the-badge" alt="Platforms" />
    <img src="https://img.shields.io/badge/runtime-offline%20first-111827?style=for-the-badge" alt="Offline runtime" />
    <img src="https://img.shields.io/badge/MCP-ready-111827?style=for-the-badge" alt="MCP ready" />
    <img src="https://img.shields.io/badge/storage-SQLite%20%2B%20JSON-111827?style=for-the-badge" alt="SQLite and JSON" />
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
| Method execution | 39 callable tools across charts, predictive work, occult domains, export tooling, and hover knowledge access | This is a real local capability surface, not just prompt glue |
| Output contract | Every supported method emits stable envelopes plus `export_snapshot` / `export_format` | Machines can consume outputs repeatedly without guesswork |
| Local memory | SQLite + JSON artifacts + run manifest + answer write-back | Every invocation becomes a durable local record |
| Distribution model | Lightweight repository plus heavyweight release assets | Public history stays clean while runtime payloads stay complete |

### Directly callable tools

| Domain | Methods available now |
| --- | --- |
| Export and orchestration | `export_registry`, `export_parse`, `horosa_dispatch` |
| Xingque hover knowledge | `knowledge_registry`, `knowledge_read` |
| Core charts | `chart`, `chart13`, `hellen_chart`, `guolao_chart`, `india_chart`, `relative`, `germany` |
| Predictive methods | `solarreturn`, `lunarreturn`, `solararc`, `givenyear`, `profection`, `pd`, `pdchart`, `zr`, `firdaria`, `decennials` |
| Chinese occult backbone | `ziwei_birth`, `ziwei_rules`, `bazi_birth`, `bazi_direct`, `liureng_gods`, `liureng_runyear`, `qimen`, `taiyi`, `jinkou` |
| Phase 2 local methods | `tongshefa`, `sanshiunited`, `suzhan`, `sixyao`, `otherbu` |
| Seasonal / calendar / hexagram utilities | `jieqi_year`, `nongli_time`, `gua_desc`, `gua_meiyi` |

### Xingque AI export protocol domains already modeled

This project does not only run tools. It also exposes Xingque’s export registry as a machine-readable protocol surface across:

- `astrochart`, `astrochart_like`, `indiachart`, `relative`
- `primarydirect`, `primarydirchart`, `zodialrelease`, `firdaria`, `decennials`
- `solarreturn`, `lunarreturn`, `solararc`, `givenyear`, `profection`
- `bazi`, `ziwei`, `suzhan`, `sixyao`, `tongshefa`
- `liureng`, `jinkou`, `qimen`, `taiyi`, `sanshiunited`
- `guolao`, `germany`
- `jieqi`, `jieqi_meta`, `jieqi_chunfen`, `jieqi_xiazhi`, `jieqi_qiufen`, `jieqi_dongzhi`
- `otherbu`, `generic`

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
