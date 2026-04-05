# Repo Layout

This project is intentionally split so the repository can stay clean while the local folder can still stay self-contained.

## Public Repository Surface

- `README.md`
  Default Chinese GitHub landing page and first-run instructions.
- `README_EN.md`
  English landing page for the same product surface.
- `README.zh-CN.md`
  Compatibility entry that forwards readers to the default Chinese and English READMEs.
- `docs/`
  Maintainer-facing documentation, release notes, specs, and example manifests.
- `horosa-skill/`
  The actual Python package, CLI, MCP server, tests, and client examples.

## Local-Only Packaging Surface

- `vendor/`
  Local runtime source area used for release packaging. This folder may exist on disk even when large contents inside it are excluded from Git history.

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
