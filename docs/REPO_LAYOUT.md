# Repo Layout

This repository is intentionally split into a small number of uploadable areas:

- `README.md`
  The GitHub landing page and first-run instructions.
- `docs/`
  Maintainer-facing documentation, release notes, and example manifests.
- `vendor/`
  Local runtime source area used for release packaging; may remain outside Git history when payloads are too large for normal GitHub storage.
- `horosa-skill/`
  The actual Python package, CLI, MCP server, tests, and client examples.

## horosa-skill/

- `src/horosa_skill/`
  Application code for schemas, engine adapters, local memory, runtime management, export parsing, and MCP/CLI surfaces.
- `tests/`
  Regression tests for router, service, memory, export tools, and runtime manager behavior.
- `examples/clients/`
  Copy-paste setup examples for Claude Desktop, Codex, Open WebUI, and OpenClaw.
- `scripts/`
  Maintainer utilities for syncing vendored runtime sources, building offline runtime release assets, generating manifests, and scaffolding Windows payloads.
- `.env.example`
  Optional local overrides for ports, runtime root, and backend endpoints.

## What Stays Out Of This Repo

- Full desktop application source tree copies
- Built runtime payloads and release archives
- Local databases, output artifacts, and caches
- Machine-specific files such as `.DS_Store`, `.venv`, and `__pycache__`
