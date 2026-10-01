# Repo Layout

> 读者：所有 agent（新 agent 首读之一）。何时读：定位代码、理解一次调用的层间流转时。路由：[`AGENTS.md`](../AGENTS.md) §0。

Horosa Skill is a local-first, offline MCP server + CLI that exposes Horosa (星阙) divination
techniques to AI agents. The Git repository stays lightweight; the heavy runtime is published as
GitHub Release assets and assembled from `vendor/runtime-source/` (maintainer machine) plus the hosted
release pipeline.

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

Ports are a hard rule: `:9999` / `:8899` are the **user's desktop app**. Tests and live gates only talk to
an instance named explicitly via `HOROSA_SERVER_ROOT` / `HOROSA_CHART_SERVER_ROOT` (vendored test instance
`:9977` / `:8877`, matrix lanes 19999 / 18899) and never probe the default ports (`AGENTS.md` §8).

## Public repository surface (top level)

- `README.md` / `README_EN.md` / `README.zh-CN.md` — Chinese / English landing pages (zh-CN forwards).
- `CLAUDE.md` / `AGENTS.md` — agent entry points: thin Claude Code router / the full rules-of-record
  (routing, iron laws, problem-logging protocol v3, compute/packaging/release law, stability invariants).
- `CHANGELOG.md` — maintainer-local change log (gitignored; the public record of a release is the GitHub
  release notes + `docs/LESSONS.md`).
- `server.json` — Model Context Protocol registry metadata (name, version, `pypi` + `mcpb` packages, transports).
- `CITATION.cff` — citation metadata; version kept in lockstep with the package.
- `LICENSE` — GNU AGPL-3.0-only.
- `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `SECURITY.md`, `SUPPORT.md`, `.github/` — community + CI surface
  (`ci.yml`, `runtime-matrix.yml`, `release-runtime.yml`, `release-completeness.yml`, `docs-currency.yml`, `publish-pypi.yml`).
- `skills/horosa-agent/` — the published agent skill (SKILL.md + references/) — the single policy
  source for AI-client behaviour.
- `.agents/skills/horosa-agent/SKILL.md` (Codex / agentskills.io pointer) and four **generated** thin mirrors —
  `GEMINI.md` (Gemini CLI), `.github/copilot-instructions.md` (Copilot), `.windsurf/rules/horosa-skill.md`
  (Devin Desktop, formerly Windsurf), `.clinerules/horosa-skill.md` (Cline) — rendered by
  `horosa-skill/scripts/gen_agent_mirrors.py` (≤30 lines, numbers from the registry; `--check` runs inside
  `verify_docs_sync`). Policy never lives here.
- Committed client configs: `.mcp.json` (Claude Code project scope), `.cursor/mcp.json` + `.cursor/rules/horosa-skill.mdc`,
  `.vscode/mcp.json`, `.claude-plugin/{plugin.json,mcp.json,marketplace.json}` (Claude Code plugin); all audited by
  `scripts/verify_client_configs.py`.
- `docs/` — maintainer-facing docs (see below); `docs/DOC_MAP.md` is the index that `verify_docs_sync` keeps complete.
- `vendor/` — local-only runtime packaging inputs (see below).
- `horosa-skill/` — the actual Python package + bundled JS engine + contracts + scripts + tests.

## docs/

- `DOC_MAP.md` — every guidance document: purpose / reader / update trigger / guard (completeness locked by CI).
- `REPO_LAYOUT.md` — this file.
- `LESSONS.md` — append-only ledger of per-version lessons (原文, index table on top); current-truth rules live in `AGENTS.md`
  (distillation locked by `verify_docs_sync.check_lessons_distilled`).
- `GLOSSARY.md` — domain/name glossary (ken, kentang, 命盘/事盘, pin-forward, Jev, port ownership, …).
- `ARCHITECTURE.md` — layer diagram and module roles.
- `ALGORITHM_COVERAGE.md` — runtime layer per technique family; the per-tool truth is `contracts/technique_provenance.json`.
- `INPUT_CONTRACTS.md` — per-tool input contracts (required fields).
- `DATA_CONTRACTS.md` — tool-envelope version, export-contract / record / manifest identifiers, MCP budget face.
- `EXPORT_AUDIT_GUIDE.md` — section-by-section audit method for predictive exports.
- `OPERATIONS.md` — local gates / preflight / re-vendor / live / hosted release runbooks + the doc-currency institution.
- `INSTALL_RESTRICTED_NETWORK.md` — mirrors / assets API / offline USB / proxies for machines that cannot reach github.com.
- `OFFLINE_RUNTIME_RELEASES.md` — what a runtime release must contain (incl. the ken engines + their
  Python deps) and the hosted build/publish workflow.
- `RUNTIME_MANIFEST_SPEC.md` + `runtime-manifest.example.json` + `runtime-payload-manifest.example.json` —
  the manifest formats for installed runtimes and payloads.
- `EVALUATION.md` — benchmark / self-check methodology.
- `WINDOWS_RELEASE_BUILD_PROMPT.md` — Windows build-box **fallback** runbook (the hosted pipeline is primary).
- `WINDOWS_REPORT_STABILITY_PROMPT.md` — cross-platform report/OpenClaw verification prompt.
- `templates/HANDOFF_TEMPLATE.md` — skeleton for the maintainer-local `HANDOFF-*.local.md` files.

## horosa-skill/ — the package

### src/horosa_skill/ (Python)

- `service.py` — `HorosaSkillService`: tool dispatch, remote/chart routing (`_call_remote`,
  `_PYTHON_CHART_ENDPOINTS`), the per-technique `_run_*_tool` runners (including the ken runners for
  qimen/taiyi/jinkou and the `sanshiunited` aggregator), snapshot builders, export-contract attachment,
  summaries, memory write-back, and the report output-path guard (`_report_output_path`).
- `config.py` — `Settings` (server/chart roots, ports, runtime root, timeouts, `HOROSA_*` flag registry) + `from_env`.
- `agent_guidance.py` — the clarification gate: family policies + tool-specific policies, `PREFLIGHT_EXEMPT_TOOLS`.
- `engine/`
  - `registry.py` — `TOOL_DEFINITIONS` (name → domain/action/endpoint/`execution`/input model).
  - `client.py` — HTTP clients (`HorosaApiClient`, `HorosaPlainJsonClient`) for `:9999` / `:8899`.
  - `js_client.py` — `HorosaJsEngineClient`: runs `horosa-core-js` via the bundled Node; raises on JS failure.
  - `router.py` / `synonyms.py` — natural-language dispatch across tools (shared group/trace ids); corpus in `contracts/router_corpus.json`.
  - `decennials.py` — standalone Python 十年大运 port.
- `exports/` — `registry.py` (the `aiExport.js`-mirroring `AI_EXPORT_PRESET_SECTIONS` per technique,
  `AI_EXPORT_SETTINGS_VERSION` / `MIRRORED_UPSTREAM_AIEXPORT_VERSION`) + `parser.py` (parse snapshot text into
  structured sections, with missing/unknown-section checks).
- `schemas/` — `tools.py` (per-tool pydantic input models) + `common.py`.
- `runtime/` — `manager.py` (install / upgrade / doctor / start / stop), `identity.py` (endpoint ownership evidence),
  `registry.py` (atomic state file), `ports.py` / `procs.py` / `pidlock.py` / `mirrors.py`.
- `memory/store.py` — SQLite + JSON artifacts + run manifests + AI-answer write-back.
- `knowledge/` — bundled Xingque hover knowledge (`store.py` + `data/`).
- `reports/` — JSON / DOCX / PDF report builder + renderers.
- `surfaces/` — `mcp_server.py` (MCP stdio/HTTP, compact surface, toolsets), `mcp_schema.py` (advertised-schema
  slimming), `cli.py` (JSON CLI: setup / client / doctor / runtime / jev / …).
- `decisions/` — optional cloud decision layer (TypeSafe Jev, off by default): `policy.py`, `redact.py`, `ledger.py`,
  `eval.py`, `fake.py`.
- `contracts_locator.py` — finds `contracts/` in a checkout, or the wheel/MCPB copies of `jev_thresholds.json` and
  `technique_provenance.json`.
- `astro_rulers.py`, `astro_sidereal.py`, `time_basis.py`, `predictive_text.py`, `shenshu_options.py`,
  `western_options_doc.py` — ported upstream helpers (rulers, ayanamsa, time-basis labels, option docs).
- `tracing.py`, `errors.py`, `evaluation_lock.py`, `input_normalization.py`, `testing_payloads.py`,
  `client_tools.py`, `jsonc.py`, `benchmark/` — tracing, typed errors + recovery table, eval gating, input
  normalization, sample payloads, the callable-tool client layer, JSONC tolerance, and benchmarking.

### contracts/ (machine-readable truth, 19 files)

`vendor_manifest.json` (what `revendor_core_js.py` vendors and how), `upstream_provenance.json` (upstream pin / runtime /
aiExport version), `technique_provenance.json`, `release_platforms.json`, `runtime_toolchain.json`, `runtime_python_lock.json`,
`upstream_python_requirements.txt`, `mcp_list_budget.json`, `mcp_client_compat.json`, `router_corpus.json`,
`js_boundary_contracts.json`, `jev_thresholds.json` + `jev_eval/`, `third_party_facts.json` (dated third-party facts), and the
debt ratchets `export_section_debt.json` / `error_recovery_debt.json` / `schema_knob_debt.json` / `silent_degrade_debt.json` /
`silent_empty_returns.json` / `value_golden_debt.json`. Each has a `verify_*.py` or test that consumes it.

### horosa-core-js/ (bundled Node engine)

- `bin/cli.mjs` — `run <tool>` / `list` entry; reads a JSON payload on stdin, returns `{ok, ...}`.
- `src/tools/` — `index.js` (runner registry) + one module per technique family (51 files): the ken-response
  formatters `qimen.js` / `taiyi.js` / `jinkou.js`, `tongshefa.js`, the in-process 数算 engines `canping.js` / `heluo.js`,
  `baziLocal.js` / `baziGeju.js` / `baziPeriod.js`, `liureng.js`, `liuyao.js`, `sanshiUnited.js`, the 择日 families, the
  astrology extras (`astroextra.js`, `progextra.js`, `guolao*.js`, `mundane*.js`, …).
- `src/vendor/` — 36 directories vendored from the 星阙 frontend by `scripts/revendor_core_js.py --from-manifest`
  (`contracts/vendor_manifest.json`; modes verbatim / curated / bespoke, every deviation declared). Two roles:
  ken-response formatters (backend `fetch*Pan` calls stripped, Python does the fetch) and in-process engines
  (the bazi chain → `lunar-javascript`, canping/heluo, `utils/localNongliAdapter.js` precise solar-term seed, …).
- `node_modules/lunar-javascript` — runtime dependency of the bazi chain (declared in `package.json`),
  installed via `npm install --omit=dev` and bundled into the offline runtime payload.
- `src/shared/` — `fields.js`, `unpack.js` only; a file here may not share an upstream name
  (`tests/test_core_js_shared_provenance.py` — the v0.40.0 solar-term-seed lesson).
- `test/` — goldens, `selfcheck.mjs` (knob-flip checks), `handcopy.mjs` (no copied vendor tables) — `npm test`.

### scripts/ (maintainer utilities)

- **Gates** — `run_ci_gates.py` is the only sanctioned local gate (pytest + every `verify_*.py` CI runs, in CI's shape);
  `preflight_release.py` orchestrates the cross-tree checks that need the upstream checkout (`verify_upstream_sync.py`,
  `verify_export_section_baseline.py`, `verify_export_contract_mirror.py`, upstream pin on the public remote) and must be
  green before a tag. Never run `verify_*.py` bare as "a quick check" — `verify_runtime_live.py` is a real lane.
- **Re-vendor** — `sync_vendored_runtime_sources.sh` (runtime subset from the read-only Horosa-Public checkout),
  `revendor_core_js.py` (the only writer of `src/vendor`), `_upstream_preset.py` (upstream aiExport parser), and the generators
  `gen_knowledge_packs.py` / `gen_bazi_pithy_pack.py` / `build_hover_knowledge_bundle.mjs` / `build_knowledge_index.py` /
  `gen_technique_provenance.py` / `gen_js_boundary_contracts.py` / `gen_jev_eval_sets.py` / `gen_shaozi_tiaowen.py` /
  `gen_runtime_python_lock.py` (fix the generator, never the generated file).
- **Live** — `start_vendored_instance.sh` / `stop_vendored_instance.sh` (vendored instance on `:9977` / `:8877`),
  `verify_runtime_live.py` (the matrix lane), `section_harness.py` (every tool's sample payload against a live instance),
  `run_full_self_check.py`, `run_openclaw_full_self_check.py`, `run_benchmark.py`.
- **Release** — `publish_release.sh` (`--draft --dispatch`: seed → manifest → SBOM → MCPB → wheel → SHA256SUMS → verify → draft →
  dispatch `release-runtime.yml`), `package_runtime_payload.sh` (darwin seed), `build_runtime_release_windows.py` (derives the
  Windows zip from the seed; runs on `windows-latest`), `generate_release_manifest.py`, `generate_sbom.py`, `build_mcpb.sh`,
  `verify_runtime_release.py`, `verify_matrix_digests.py` (lane-installed sha == draft assets before publish),
  `sync_windows_release.py` (`--check` = completeness / pin-forward verdict; `--upload` = Windows-box fallback),
  `runtime_seed.py`, `scaffold_windows_runtime.py`; `build_runtime_release.sh`, `build_runtime_release_linux.py`,
  `scaffold_linux_runtime.py`, `repack_release_assets.py` are historical / experimental.
- **Docs institution** — `verify_docs_sync.py` (versions, counts, links, DOC_MAP, lessons distillation, generated mirrors,
  third-party facts ledger), `gen_agent_mirrors.py`, `bump_version.py` (15 version sites, `--check`), `verify_readme_links.py`.
- **Other verifiers** — `verify_vendor_runtime_sources.py`, `verify_server_json.py`, `verify_builder_parity.py`,
  `verify_client_configs.py`, `verify_error_recovery.py`, `verify_mcp_list_budget.py`, `verify_mcp_client_compat.py`,
  `verify_mcpb_manifest.py`, `verify_schema_knob_wiring.py`, `verify_silent_degrades.py`, `verify_silent_returns.py`,
  `verify_router_corpus.py`, `verify_technique_provenance.py`, `verify_undefined_names.py`, `verify_value_goldens.py`,
  `verify_wheel_contents.py`, `verify_runtime_scripts.py`, `verify_runtime_python_lock.py`, `verify_no_stray_runtime_dirs.py`,
  `verify_js_boundary_contracts.py`.
- `runtime_templates/windows/` — PowerShell start/stop templates (force-included into the wheel).

### tests/ and examples/

- `tests/` — pytest suite (router, service, export tools, memory, runtime manager, CLI, MCP server, client configs,
  workflow shapes, docs currency). Live tests (`test_local_js_tools.py`, sync311 modules, sanshiunited) run only when
  `HOROSA_SERVER_ROOT` / `HOROSA_CHART_SERVER_ROOT` name an instance explicitly — default ports are never probed —
  and skip with a stated reason when the installed payload's `export_registry_version` is older than the tree
  (`requires_current_runtime_contract`). `conftest.py` pins this checkout's `src` onto `PYTHONPATH` for subprocess tests.
- `examples/clients/` — `README.md` (index), `claude-code.md`, `claude_desktop_config.json`, `codex.md` + `codex-config.toml`,
  `openclaw-mcp.md`, `openwebui-streamable-http.md`, `remote-connectors-oauth-gateway.md`.

## Local-only packaging surface

- `vendor/runtime-source/` — maintainer-only packaging inputs (the Horosa-Web subset + the darwin-arm64 embedded
  runtimes), pulled from the read-only Horosa-Public checkout by `sync_vendored_runtime_sources.sh`; uncommitted. Must include
  `Horosa-Web/vendor/{kinqimen,kintaiyi,kinjinkou,kinwangji,kinwuzhao,taixuanshifa,jingjue,shenyishu,kinastro}`.
  The Windows half is **not** built from local inputs: it is derived from the darwin seed with the pins in
  `contracts/runtime_toolchain.json` and `contracts/runtime_python_lock.json`.

## What stays out of this repo

- Full 星阙 desktop application source copies (and anything from a private tree — the only reference is Horosa-Public)
- Built runtime payloads and release archives (published as GitHub Release assets)
- Local databases, run outputs, caches, `CHANGELOG.md`, `HANDOFF-*.local.md`, `notes-local/`
- Machine-specific files (`.DS_Store`, `.venv`, `__pycache__`, build dirs)

## Cross-platform

macOS and Windows are both first-class. The Python package, `engine/` routing, and `horosa-core-js`
formatters are platform-neutral. Platform specifics live in the runtime layer: macOS uses
`Horosa-Web/start_horosa_local.sh` (`PYTHONPATH_ASTRO` includes `flatlib-ctrad2:astropy:vendor`); Windows
uses `runtime_templates/windows/start_horosa_local.ps1` (`PYTHONPATH` includes `astropy;flatlib-ctrad2;vendor`; it also sets
`HOROSA_EPHE_PATH_FASTPATH=0`, because Swiss Ephemeris keeps its state per thread on Windows — AGENTS §9.3).
Both put `vendor` on the path so `import kinqimen / kintaiyi / kinjinkou` resolves. On Windows the runtime root must be a
pure-ASCII path (`runtime.path_not_ascii`), subprocess text is always decoded explicitly, and every release is exercised on
`windows-latest` + `windows-11-arm` by the matrix (see `OFFLINE_RUNTIME_RELEASES.md`).
