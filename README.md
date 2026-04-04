[简体中文](./README.zh-CN.md) | **English**

<div align="center">
  <h1>Horosa Skill</h1>
  <p><strong>The local-first AI skill layer for Xingque / Horosa.</strong></p>
  <p>Run structured metaphysical calculations, parse the full Xingque AI export format, and expose offline tools to Claude, Codex, Open WebUI, or OpenClaw through MCP.</p>

  <p>
    <a href="https://github.com/Horace-Maxwell/horosa-skill">
      <img src="https://img.shields.io/badge/Browse-Repository-0f172a?style=for-the-badge&logo=github" alt="Browse Repository" />
    </a>
    <a href="https://github.com/Horace-Maxwell/horosa-skill/releases">
      <img src="https://img.shields.io/badge/Browse-Releases-1d4ed8?style=for-the-badge&logo=github" alt="Browse Releases" />
    </a>
    <a href="./README.zh-CN.md">
      <img src="https://img.shields.io/badge/Read%20in-Chinese-0f766e?style=for-the-badge" alt="Read in Chinese" />
    </a>
  </p>

  <p>
    <img src="https://img.shields.io/github/stars/Horace-Maxwell/horosa-skill?style=for-the-badge" alt="GitHub stars" />
    <img src="https://img.shields.io/github/v/release/Horace-Maxwell/horosa-skill?display_name=tag&style=for-the-badge" alt="Release" />
    <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows-0f766e?style=for-the-badge" alt="Platforms" />
    <img src="https://img.shields.io/badge/runtime-local%20first-111827?style=for-the-badge" alt="Local first runtime" />
    <img src="https://img.shields.io/badge/MCP-ready-111827?style=for-the-badge" alt="MCP ready" />
    <img src="https://img.shields.io/badge/python-3.12%2B-111827?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.12+" />
  </p>
</div>

![Horosa Skill hero](./docs/media/hero-banner.svg)

## What Horosa Skill Is

Horosa Skill turns Xingque's richest export surface and offline calculation stack into something modern AI tools can actually call.

- Parse the full Xingque AI export format into stable JSON
- Expose structured tools through MCP and a JSON-first CLI
- Persist results to local SQLite and JSON artifacts
- Package offline runtime assets from one local project folder
- Keep the public GitHub repo clean without losing local self-containment

If the goal is "install once, let any serious AI call real Xingque methods locally, and do not depend on an external service," this repo is built for that.

## What Lives Where

This project intentionally separates two concerns:

| Area | Purpose |
| --- | --- |
| GitHub repository | Public code, docs, CLI, MCP surface, examples, and release scripts |
| Local project folder | Everything above, plus any large runtime sources needed for offline packaging |

The important rule is:

- required runtime inputs can live inside this local folder
- they do not need to be committed to GitHub history
- packaging scripts must be able to build from this folder alone, without hunting through sibling directories

That is why `vendor/runtime-source/` exists locally and is ignored by git.

## Runtime Handling Rules

There are only three correct runtime locations in this project:

| Scenario | Where runtime lives | Should it be committed to GitHub? |
| --- | --- | --- |
| Normal user installs from GitHub | `~/.horosa/runtime/current` on macOS or `%LOCALAPPDATA%/Horosa/runtime/current` on Windows | No |
| Maintainer prepares a release locally | `vendor/runtime-source/` inside this local project folder | No, not by default |
| Public distribution to end users | GitHub Releases runtime archives plus release manifest | Yes, as release assets, not as repo history |

What this means in practice:

- end users who clone the repo should run `horosa-skill install` and download a platform runtime from GitHub Releases
- maintainers may keep large packaging inputs under `vendor/runtime-source/` locally so release builds do not depend on sibling folders
- the repository itself should stay lightweight and should not carry full offline runtimes in normal Git history

If a file is only needed to build the runtime archive, it belongs either in the local `vendor/runtime-source/` area or in a published Release asset, not in regular repository commits.

## Why This Repo Exists

- Xingque already has a very rich AI export surface, but raw text is not enough for tool-calling models.
- Most users should not need your private dev tree just to run Horosa offline.
- A serious AI-facing repository needs a stable schema, install path, runtime story, and client integration story.

Horosa Skill is the delivery layer for exactly that.

## Core Capabilities

| Area | What it does |
| --- | --- |
| Export protocol | Publishes the Xingque AI export registry as machine-readable schema |
| Export parsing | Converts Xingque AI export text into structured JSON sections |
| Tool surface | Exposes `horosa_dispatch` plus atomic tools for charting and metaphysical methods |
| AI integration | Supports MCP-based clients such as Claude, Codex, Open WebUI, and OpenClaw |
| Local storage | Stores runs in SQLite and writes JSON artifacts for later retrieval |
| Offline packaging | Builds runtime payloads from local vendored sources inside this folder |

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
uv run horosa-skill install
uv run horosa-skill doctor
```

## AI Client Integrations

- [Claude Desktop config](./horosa-skill/examples/clients/claude_desktop_config.json)
- [Codex config](./horosa-skill/examples/clients/codex-config.toml)
- [Open WebUI setup](./horosa-skill/examples/clients/openwebui-streamable-http.md)
- [OpenClaw setup](./horosa-skill/examples/clients/openclaw-mcp.md)

## CLI Examples

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

Run an atomic tool directly:

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

| Path | Role |
| --- | --- |
| [`horosa-skill/`](./horosa-skill) | Python package, CLI, MCP server, tests, examples, and release scripts |
| [`docs/`](./docs) | Runtime specs, release notes, and maintainership docs |
| [`vendor/`](./vendor) | Local runtime source area for offline packaging |

See [Repo Layout](./docs/REPO_LAYOUT.md) for the maintainer view.

## Offline Runtime Strategy

This repo uses a two-layer model:

- the public repository stays reviewable and uploadable
- full offline runtime payloads are built from local runtime sources inside this folder

Typical local runtime inputs can include:

- Horosa Python calculation layer
- flatlib and Swiss Ephemeris data
- Xingque export-related frontend assets
- embedded macOS Python runtime
- embedded macOS Java runtime
- bundled `astrostudyboot.jar`

See:

- [Offline Runtime Releases](./docs/OFFLINE_RUNTIME_RELEASES.md)
- [Runtime Manifest Spec](./docs/RUNTIME_MANIFEST_SPEC.md)
- [Algorithm Coverage](./docs/ALGORITHM_COVERAGE.md)
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
- CLI and MCP surfaces
- local memory store
- runtime install, doctor, and stop commands
- runtime start or stop orchestration
- release manifest driven install flow
- production runtime archives for macOS and Windows
- headless JS runtime for `qimen`, `taiyi`, and `jinkou`
- runtime archive verification tooling

Shipping exclusions:

- `fengshui`

## Design References

This repo direction is informed by strong open-source product repositories and by your own product-style repo structure:

- [supabase/supabase](https://github.com/supabase/supabase)
- [shadcn-ui/ui](https://github.com/shadcn-ui/ui)
- [n8n-io/n8n](https://github.com/n8n-io/n8n)
- [open-webui/open-webui](https://github.com/open-webui/open-webui)
- your `portpilot` repo pattern for hero layout, bilingual README flow, and product-first framing

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md).

## Security

See [SECURITY.md](./SECURITY.md).
