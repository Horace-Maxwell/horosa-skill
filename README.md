# Horosa Skill

<p align="center">
  <strong>GitHub-first, offline-capable AI skill distribution for Xingque / Horosa.</strong>
</p>

<p align="center">
  Turn the full Xingque AI export protocol, structured metaphysical tooling, and local runtime packaging flow into a repository that other AI systems can actually use.
</p>

<p align="center">
  <a href="https://github.com/Horace-Maxwell/horosa-skill/stargazers"><img alt="GitHub stars" src="https://img.shields.io/github/stars/Horace-Maxwell/horosa-skill?style=for-the-badge"></a>
  <a href="https://github.com/Horace-Maxwell/horosa-skill/releases"><img alt="GitHub release" src="https://img.shields.io/github/v/release/Horace-Maxwell/horosa-skill?style=for-the-badge"></a>
  <img alt="Python 3.12+" src="https://img.shields.io/badge/python-3.12%2B-111111?style=for-the-badge&logo=python&logoColor=white">
  <img alt="MCP" src="https://img.shields.io/badge/MCP-ready-111111?style=for-the-badge">
  <img alt="Offline runtime" src="https://img.shields.io/badge/offline-runtime-111111?style=for-the-badge">
  <img alt="macOS" src="https://img.shields.io/badge/macOS-supported-111111?style=for-the-badge&logo=apple&logoColor=white">
  <img alt="Windows scaffold" src="https://img.shields.io/badge/Windows-scaffolded-111111?style=for-the-badge&logo=windows&logoColor=white">
</p>

## What This Repo Is

`horosa-skill` is the GitHub distribution layer for a local-first Horosa runtime and AI skill surface.

It is designed so someone can:

1. clone the repository
2. install or unpack a local runtime
3. connect Claude, Codex, Open WebUI, or OpenClaw through MCP
4. call Horosa/Xingque methods with structured JSON input and output
5. persist every run locally for later retrieval

This repository is not trying to be a copy of the entire desktop app source tree. It is trying to be the cleanest possible public-facing delivery layer for:

- the Xingque AI export protocol
- the local MCP and CLI surfaces
- the offline runtime packaging workflow
- the vendored runtime source subset needed for release builds

## Why This Repo Exists

- Most AI tools can read JSON and call tools, but cannot understand Xingque's richest export format out of the box.
- Most users should not need your private dev tree or local folder layout just to publish or run Horosa offline.
- A GitHub repo intended for other AIs needs a stable entrypoint, stable schema, stable install story, and stable local storage model.

This repo is built around exactly that.

## Core Capabilities

- `horosa_dispatch` for natural-language request routing
- atomic tools for charting, predictive, Chinese metaphysical, and export-related calls
- machine-readable Xingque AI export registry
- parser from Xingque AI export text snapshots to structured JSON
- local SQLite + JSON artifact persistence
- MCP server for AI clients
- JSON-first CLI for direct testing
- vendored runtime source layout for offline packaging

## Quick Start

```bash
cd horosa-skill
uv sync
uv run horosa-skill doctor
uv run horosa-skill serve
```

Default MCP endpoint:

```text
http://127.0.0.1:8765/mcp
```

For stdio clients such as Claude Desktop:

```bash
cd horosa-skill
uv run horosa-skill serve --transport stdio
```

## Install Flow

If you already have a runtime archive:

```bash
cd horosa-skill
uv run horosa-skill install --archive /path/to/runtime-payload.tar.gz
uv run horosa-skill doctor
```

If you publish runtime assets through GitHub Releases:

```bash
cd horosa-skill
uv run horosa-skill install --manifest-url https://example.com/runtime-manifest.json
uv run horosa-skill doctor
```

## AI Client Integrations

- [Claude Desktop config](./horosa-skill/examples/clients/claude_desktop_config.json)
- [Codex config](./horosa-skill/examples/clients/codex-config.toml)
- [Open WebUI setup](./horosa-skill/examples/clients/openwebui-streamable-http.md)
- [OpenClaw setup](./horosa-skill/examples/clients/openclaw-mcp.md)

## CLI Examples

List tools:

```bash
cd horosa-skill
uv run horosa-skill tool list
```

Export the full Xingque AI export registry:

```bash
cd horosa-skill
uv run horosa-skill export registry
```

Parse Xingque AI export text into structured JSON:

```bash
cd horosa-skill
echo '{
  "technique": "qimen",
  "content": "[起盘信息]\n参数\n\n[八宫]\n八宫内容\n\n[演卦]\n演卦内容"
}' | uv run horosa-skill export parse --stdin
```

Run a tool directly:

```bash
echo '{"date":"1990-01-01","time":"12:00","zone":"8","lat":"31n14","lon":"121e28"}' \
  | uv run horosa-skill tool run chart --stdin
```

Run the dispatcher:

```bash
echo '{
  "query":"请做本命盘分析并给出主运势方向",
  "birth":{"date":"1990-01-01","time":"12:00","zone":"8","lat":"31n14","lon":"121e28"},
  "save_result": true
}' | uv run horosa-skill dispatch --stdin
```

## Repository Layout

- [`horosa-skill/`](./horosa-skill)
  Python package, CLI, MCP server, tests, client examples, and release scripts.
- [`docs/`](./docs)
  Runtime manifest spec, release docs, and repo layout docs.
- [`vendor/`](./vendor)
  Local maintainer area for runtime sources kept on disk but not required in Git history.

## Offline Runtime Strategy

This repo uses a two-layer release model:

- the Git repository stays reviewable and reasonably organized
- full offline runtime assets are produced from local runtime sources and shipped as release archives

Current local runtime inputs can include:

- Horosa Python calculation layer
- flatlib and Swiss Ephemeris files
- Xingque export-related frontend bundle assets
- embedded macOS Python runtime
- embedded macOS Java runtime
- bundled `astrostudyboot.jar`

See:

- [Offline Runtime Releases](./docs/OFFLINE_RUNTIME_RELEASES.md)
- [Runtime Manifest Spec](./docs/RUNTIME_MANIFEST_SPEC.md)
- [Vendored Runtime Sources](./vendor/README.md)

## Local Storage Model

Structured results are stored locally by default:

- macOS / Linux: `~/.horosa-skill/`
- Windows: `%APPDATA%/HorosaSkill/`

Each saved run can write:

- run metadata
- tool call records
- entity references
- JSON artifacts under `runs/<YYYY>/<MM>/<DD>/`

## Current Status

Implemented now:

- structured export registry
- structured export parser
- CLI surface
- MCP surface
- local memory store
- runtime install and doctor commands
- runtime start/stop orchestration
- vendored macOS runtime packaging inputs
- Windows runtime scaffold

Still in progress:

- production Windows runtime payload
- fully packaged headless JS runtime for all frontend-local algorithms
- public GitHub Release publishing flow

## Design References

This repository direction was informed by how strong high-star projects present themselves:

- [supabase/supabase](https://github.com/supabase/supabase)
- [shadcn-ui/ui](https://github.com/shadcn-ui/ui)
- [n8n-io/n8n](https://github.com/n8n-io/n8n)
- [open-webui/open-webui](https://github.com/open-webui/open-webui)

The main takeaways applied here are:

- strong value proposition at the top
- clean first-run path
- visible integration story
- dedicated contributing and security files
- clear separation between product surface and release internals

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md).

## Security

See [SECURITY.md](./SECURITY.md).
