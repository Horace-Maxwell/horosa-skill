# Repo Layout

Horosa Skill is a local-first, offline MCP server + CLI that exposes Horosa (星阙) divination
techniques to AI agents. The Git repository stays lightweight; the heavy runtime is published as
GitHub Release assets and assembled locally from `vendor/runtime-source/`.

This document maps the tree and shows how a tool call actually flows through the layers.

## Compute model (read this first)

A tool call resolves through `HorosaSkillService.run_tool` (`horosa-skill/src/horosa_skill/service.py`),
which dispatches by the tool's `execution` mode in `engine/registry.py`:

- **remote** → HTTP to the local runtime. Two backends: the Java aggregation layer (`:9999`,
  `self.client`) and the Python chart service (`:8899`, `self.chart_client`). The chart service hosts
  the astrology engines (`/chart`, `/predict/*`, `/india/*`, `/germany/*`, `/jieqi/*`) **and the ken
  engines** (`/qimen/pan`, `/taiyi/pan`, `/jinkou/pan`); the set of chart-routed endpoints is
  `_PYTHON_CHART_ENDPOINTS` in `service.py`.
- **local** → computed in-process or via the bundled Node engine (`engine/js_client.py` →
  `horosa-core-js`).

**奇门 / 太乙 / 金口 use the ken backend** (`kinqimen` / `kintaiyi` / `kinjinkou`) as the sole compute
authority. `_run_{qimen,taiyi,jinkou}_tool` fetch the ken chart endpoint, then hand the ken response to
`horosa-core-js`, which **reformats** it (via `normalizeKinqimenData` / `normalizeBackendPan` /
`normalizeKinjinkouData` + `buildDunJiaSnapshotText` / `buildTaiyiSnapshotText` / `buildJinkouSnapshotText`)
into 星阙 `aiExport.js` sections — so the `export_snapshot` contract is identical to the product's.
`三式合一` composes the ken 奇门 + 太乙 with the 大六壬 leg; `统摄法` (tongshefa) is the one technique with
no ken engine and stays a pure headless JS calculation.

## Public repository surface (top level)

- `README.md` / `README_EN.md` / `README.zh-CN.md` — Chinese / English landing pages (zh-CN forwards).
- `CHANGELOG.md` — release-oriented change log (current: `0.6.1`).
- `server.json` — Model Context Protocol registry metadata (name, version, packages, transports).
- `CITATION.cff` — citation metadata; version kept in lockstep with the package.
- `LICENSE` — GNU AGPL-3.0-only.
- `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `SECURITY.md`, `SUPPORT.md`, `.github/` — community + CI surface.
- `docs/` — maintainer-facing docs (see below).
- `vendor/` — local-only runtime packaging inputs (see below).
- `horosa-skill/` — the actual Python package + bundled JS engine + scripts + tests.

## docs/

- `REPO_LAYOUT.md` — this file.
- `ARCHITECTURE.md` — layer diagram and module roles.
- `ALGORITHM_COVERAGE.md` — per-technique coverage matrix and the runtime layer that backs each.
- `DATA_CONTRACTS.md` — tool-envelope version, export-contract / record / manifest schema identifiers.
- `OPERATIONS.md` — install / doctor / serve / run operational guide.
- `OFFLINE_RUNTIME_RELEASES.md` — what a runtime release must contain (incl. the ken engines + their
  Python deps) and the maintainer build/publish workflow.
- `RUNTIME_MANIFEST_SPEC.md` + `runtime-manifest.example.json` + `runtime-payload-manifest.example.json` —
  the manifest formats for installed runtimes and payloads.
- `EVALUATION.md` — benchmark / self-check methodology.
- `WINDOWS_REPORT_STABILITY_PROMPT.md` — cross-platform report/OpenClaw verification prompt.

## horosa-skill/ — the package

### src/horosa_skill/ (Python)

- `service.py` — `HorosaSkillService`: tool dispatch, remote/chart routing (`_call_remote`,
  `_PYTHON_CHART_ENDPOINTS`), the per-technique `_run_*_tool` runners (including the ken runners for
  qimen/taiyi/jinkou and the `sanshiunited` aggregator), snapshot builders, export-contract attachment,
  summaries, and memory write-back.
- `config.py` — `Settings` (server/chart roots, ports, runtime root, timeouts) + `from_env`.
- `engine/`
  - `registry.py` — `TOOL_DEFINITIONS` (name → domain/action/endpoint/`execution`/input model).
  - `client.py` — HTTP clients (`HorosaApiClient`, `HorosaPlainJsonClient`) for `:9999` / `:8899`.
  - `js_client.py` — `HorosaJsEngineClient`: runs `horosa-core-js` via the bundled Node; raises on JS failure.
  - `router.py` — natural-language dispatch across tools (shared group/trace ids).
  - `decennials.py` — standalone Python 十年大运 port.
- `exports/` — `registry.py` (the `aiExport.js`-mirroring `AI_EXPORT_PRESET_SECTIONS` per technique) +
  `parser.py` (parse snapshot text into structured sections, with missing/unknown-section checks).
- `schemas/` — `tools.py` (per-tool pydantic input models) + `common.py`.
- `runtime/manager.py` — install / doctor / start / stop of the local runtime services.
- `memory/store.py` — SQLite + JSON artifacts + run manifests + AI-answer write-back.
- `knowledge/` — bundled Xingque hover knowledge (`store.py` + `data/`).
- `reports/` — JSON / DOCX / PDF report builder + renderers.
- `surfaces/` — `mcp_server.py` (MCP stdio/HTTP) and `cli.py` (JSON CLI).
- `tracing.py`, `errors.py`, `evaluation_lock.py`, `input_normalization.py`, `testing_payloads.py`,
  `client_tools.py`, `benchmark/` — tracing, typed errors, eval gating, input normalization, sample
  payloads, the callable-tool client layer, and benchmarking.

### horosa-core-js/ (bundled Node engine)

- `bin/cli.mjs` — `run <tool>` / `list` entry; reads a JSON payload on stdin, returns `{ok, ...}`.
- `src/tools/` — `index.js` (runner registry) + `qimen.js` / `taiyi.js` / `jinkou.js` (ken-response
  formatters) + `tongshefa.js` (standalone 统摄法 engine).
- `src/vendor/` — engine code vendored from the 星阙 frontend, kept as **formatters** for the ken
  response: `dunjia/{DunJiaCalc,DunJiaBaGongRules}.js`, `taiyi/{TaiYiCalc,core/TaiYiCore}.js`,
  `jinkou/{JinKouCalc,JinKouState}.js`, `liureng/LRConst.js`. Each keeps `normalize*Data` +
  `build*SnapshotText`; only the backend `fetch*Pan` calls are stripped (Python does the ken fetch).
- `src/shared/` — `fields.js`, `unpack.js`, `localNongliAdapter.js` helpers.

### scripts/ (maintainer utilities)

- `sync_vendored_runtime_sources.sh` — pull the runtime subset (incl. `Horosa-Web/vendor/{kinqimen,
  kintaiyi,kinjinkou}`) from a local 星阙 tree into `vendor/runtime-source/`.
- `package_runtime_payload.sh` — assemble the macOS runtime payload tarball (bundles the ken engines and
  patches the staged kentang mount to skip absent engines).
- `build_runtime_release.sh` — orchestrate macOS + Windows archives, manifest, checksums, verification.
- `build_runtime_release_windows.{py,ps1}` + `scaffold_windows_runtime.py` + `runtime_templates/windows/` —
  Windows payload build, skeleton, and PowerShell start/stop templates (PYTHONPATH includes `vendor`).
- `generate_release_manifest.py`, `generate_sbom.py`, `build_knowledge_index.py`,
  `build_hover_knowledge_bundle.mjs` — manifest, SBOM, and knowledge-bundle generation.
- `run_full_self_check.py`, `run_openclaw_full_self_check.py`, `run_benchmark.py` — end-to-end self-checks.
- `verify_runtime_release.py`, `verify_vendor_runtime_sources.py`, `verify_server_json.py`,
  `verify_readme_links.py` — release / source / metadata / docs verifiers.

### tests/ and examples/

- `tests/` — pytest suite (router, service, export tools, memory, runtime manager, CLI, MCP server,
  and `test_local_js_tools.py` — qimen/taiyi/jinkou/sanshi run as integration tests against the live ken
  chart service and skip when `:8899`/`:9999` are down; tongshefa runs unconditionally).
- `examples/clients/` — Claude Desktop / Codex / Open WebUI / OpenClaw setup snippets.

## Local-only packaging surface

- `vendor/runtime-source/` — maintainer-only packaging inputs (a 星阙 subset + embedded runtimes). May
  exist on disk uncommitted; `package_runtime_payload.sh` / the Windows builder read from it. Must include
  `Horosa-Web/vendor/{kinqimen,kintaiyi,kinjinkou}` for the ken endpoints.

## What stays out of this repo

- Full 星阙 desktop application source copies
- Built runtime payloads and release archives (published as GitHub Release assets)
- Local databases, run outputs, caches
- Machine-specific files (`.DS_Store`, `.venv`, `__pycache__`, build dirs)

## Cross-platform

macOS and Windows are both first-class. The Python package, `engine/` routing, and `horosa-core-js`
formatters are platform-neutral. Platform specifics live in the runtime layer: macOS uses
`Horosa-Web/start_horosa_local.sh` (`PYTHONPATH_ASTRO` includes `flatlib-ctrad2:astropy:vendor`); Windows
uses `runtime_templates/windows/start_horosa_local.ps1` (`PYTHONPATH` includes `astropy;flatlib-ctrad2;vendor`).
Both put `vendor` on the path so `import kinqimen / kintaiyi / kinjinkou` resolves. The embedded macOS
Python already carries the ken deps (bidict / numpy / kerykeion / ephem / pendulum); the Windows wheel
bundle must include them too (see `OFFLINE_RUNTIME_RELEASES.md`).
