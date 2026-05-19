# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows a release-oriented changelog style.

## [Unreleased]

## [0.5.13] - 2026-05-18

### Fixed

- Normalized IANA timezone names such as `America/Los_Angeles` and
  `Asia/Shanghai` into date-aware numeric offsets before calling Java date
  endpoints. This closes the remaining `/nongli/time` failure where
  full-parameter Qimen worked with `-07:00`, but a minimal OpenClaw call using
  `America/Los_Angeles` still surfaced `Index 1 out of bounds for length 1`.
- Added Windows-safe `tzdata` packaging so the same IANA timezone normalization
  works on both macOS and Windows fresh installs.
- Added regression coverage for DST-sensitive timezone conversion and Qimen /
  Nongli remote payloads.

## [0.5.12] - 2026-05-18

### Fixed

- Added legacy payload retries for Java date-dependent endpoints such as
  `/nongli/time`, `/jieqi/year`, and Liureng helpers. If a bundled runtime
  rejects the validated Xingque-style payload with `200001 param error`, Horosa
  Skill now retries slash-date, zone-hour, GPS-only, and decimal coordinate
  variants before surfacing a structured error.
- Hardened the Qimen / Taiyi / Sixyao prerequisite path so agent attempts with
  common date/time/coordinate formats no longer collapse into a raw
  `/nongli/time` `Index 1 out of bounds for length 1` backend error.
- Clarified OpenClaw diagnostics: `clientToolCount: 0` in a stale trajectory is
  not authoritative when `openclaw mcp list`, `listed_tool_count`, or direct
  `horosa__...` tool calls prove that Horosa is attached.

## [0.5.11] - 2026-05-18

### Fixed

- `client openclaw-setup` now writes both the workspace `mcporter.json` and the
  native OpenClaw `mcp.servers.horosa` entry in `~/.openclaw/openclaw.json`.
  This closes the gap where mcporter smoke checks passed but new OpenClaw agent
  sessions still showed `clientToolCount: 0`.
- Setup output now reports `native_config_written_to` and explicitly tells users
  to restart OpenClaw or open a new agent session after native MCP config
  changes.
- OpenClaw docs now distinguish mcporter smoke configuration from native agent
  MCP attachment, reducing accidental shell/Python fallback behavior.

## [0.5.10] - 2026-05-18

### Fixed

- Aligned the package `__version__` and headless JS engine metadata with the
  public release version so tool envelopes no longer report an older version.
- Added top-level `manifest_version` and `runtime_payload_version` fields to
  `doctor` output so external checkers do not misread a healthy manifest as
  `null`.
- Added timeout protection to the OpenClaw full-check mcporter call path.
- Clarified full-check counting with `business_tool_count` versus
  `listed_tool_count` so agents do not confuse 39 business tools with all
  OpenClaw-visible helper tools.
- Added native-MCP attachment as a global agent guidance rule: when
  `clientToolCount: 0`, agents must ask the user/admin to fix OpenClaw setup
  instead of falling back to shell calculations.

## [0.5.9] - 2026-05-18

### Fixed

- Added release verification for the embedded `runtime-payload/runtime-manifest.json`
  so macOS and Windows runtime archives can no longer ship with stale internal
  version metadata.
- Stamped `runtime_payload_version` into generated macOS and Windows runtime
  payload manifests.
- Added subprocess timeouts to OpenClaw / mcporter smoke checks so a stuck stdio
  session returns a structured `client.command_timeout` diagnostic instead of
  hanging forever.
- Clarified OpenClaw agent setup: named agents must use the same workspace that
  receives the generated mcporter config, and `clientToolCount: 0` means the
  agent has not received Horosa MCP tools.

## [0.5.8] - 2026-05-18

### Added

- Added a shared `input_contract` surface for Horosa tools so CLI `tool list`,
  MCP tool docstrings, and agent guidance expose the same required inputs, safe
  defaults, and output expectations.
- Added `docs/INPUT_CONTRACTS.md` with explicit predictive-tool input tables and
  examples for return charts, progressions, primary directions, zodiacal
  releasing, Firdaria, and decennials.

### Fixed

- Made predictive tools harder for AI clients to misuse by documenting required
  target fields such as `datetime`, `dirZone`, `dirLat`, `dirLon`, `pdMethod`,
  `pdTimeKey`, and `pdaspects` directly in machine-readable guidance.

## [0.5.7] - 2026-05-18

### Fixed

- Reworked predictive astrology export snapshots so `solarreturn`,
  `lunarreturn`, `solararc`, `givenyear`, and `profection` now explicitly emit
  both the natal chart and the corresponding return/progressed chart sections.
- Fixed `pd` primary direction exports to render the actual returned direction
  table instead of an empty placeholder.
- Fixed `pdchart` exports to include a readable primary-direction chart position
  table and aspect section.
- Fixed `zr` exports to surface zodiacal release timeline rows from the runtime
  response instead of reporting empty data.

### Added

- Added regression tests that fail unless predictive methods contain substantive
  natal/progressed chart content, primary direction tables, and zodiacal release
  rows.

## [0.5.6] - 2026-05-18

### Added

- Added `details.agent_recovery` to guidance and invalid-payload failures so AI
  clients receive a direct `prompt_to_user` instead of guessing how to recover.
- Added regression coverage proving every enforced tool has user-facing
  clarification questions and incomplete payloads produce an ask-user recovery
  contract.

### Changed

- Strengthened Agent, Cursor, OpenClaw, and skill instructions: clients must stop
  tool use when `agent_recovery` is returned and ask the user before retrying.

## [0.5.5] - 2026-05-18

### Added

- Added a hard agent preflight gate for CLI, MCP, and report-from-tool calls:
  calculation tools now reject unconfirmed requests with
  `agent_guidance.required` instead of letting AI clients silently assume
  result-changing settings.
- Added shared confirmation fields across tool schemas:
  `agent_confirmed_settings`, `defaults_accepted`, and `clarification_notes`.

### Changed

- Updated Agent, Cursor, OpenClaw, and README guidance so AI clients must call
  `horosa_agent_guidance` first, ask the user for missing required settings, and
  only call calculation tools after explicit confirmation or accepted defaults.
- Updated full-check fixtures so self-checks exercise the same confirmed-call
  contract that real AI clients must follow.

## [0.5.4] - 2026-05-18

### Added

- Added `horosa_agent_guidance` and `horosa-skill agent guidance` so AI clients can
  inspect which settings must be clarified before calling each Horosa tool.
- Added full guidance coverage for every registered tool, including astrology,
  predictive methods, Bazi, Ziwei, Daliuren, Qimen, Taiyi, Jinkou, Six Yao,
  Sanshi United, knowledge, export, and report/memory workflows.

### Changed

- Updated Agent, Cursor, and OpenClaw instructions to require clarification for
  result-changing settings such as location, gender, house system, zodiacal
  system, Qimen setup, Daliuren noble-person system, Jinkou `diFen`, Six Yao
  lines, target year/date, and report format.
- Added tests that fail if a registered tool is missing agent guidance coverage.

## [0.5.3] - 2026-05-18

### Fixed

- Strengthened the `liureng_gods` MCP tool description so OpenClaw, Cursor, and
  other agents route current-time 大六壬 requests through Horosa instead of
  hand-written shell/Python calculations.
- Added repository-level agent rules and Cursor rules that explicitly forbid
  manual recalculation of Horosa techniques and point 大六壬, 奇门, 三式合一, and
  report generation to the correct MCP tools.
- Expanded the Horosa agent skill and OpenClaw docs with current-time 大六壬
  routing guidance and Xingque-compatible `guirengType=2` defaults.

## [0.5.2] - 2026-05-18

### Fixed

- Made OpenClaw/mcporter JSON parsing tolerant of trailing diagnostic text after
  a valid JSON body, preventing occasional false `No JSON content was found`
  failures during full self-checks.
- Added explicit `doctor` environment context so default `~/.horosa` checks are
  not confused with OpenClaw isolated HOME/runtime installs.
- Filled missing Qimen headless defaults so exported pan text no longer leaks
  `undefined` for pan type or birth-sex labels when clients omit optional
  options.
- Aligned LiuReng's default noble-person system with the Xingque UI default
  (`星占法贵人`) while still allowing explicit `guirengType` overrides, and
  added regression coverage for the default pan output.

### Changed

- Documented OpenClaw troubleshooting for isolated HOME, full-check JSON
  extraction, and non-Horosa gateway PATH/plugin warnings.
- Clarified agent-facing LiuReng defaults so connected clients do not silently
  interpret Xingque-style LiuReng pans with the wrong noble-person system.

## [0.5.1] - 2026-05-18

### Fixed

- Completed the local headless LiuReng export surface so `liureng_gods` and
  `liureng_runyear` emit four lessons, three transmissions, and pan sections
  without implying any MongoDB, port 7897, desktop-app, or external-service
  dependency.
- Hardened every callable divination export against bare empty sections and
  dependency hallucination wording, with regression coverage across all
  machine-readable export contracts.

### Added

- Added `skills/horosa-agent/SKILL.md`, an agent-facing usage skill that
  explains tool selection, report generation, memory write-back, OpenClaw
  checks, and anti-hallucination rules for MCP/CLI clients.
- Added CLI support for `report from-tool --ai-answer-text`,
  `--ai-answer-file`, and `--ai-report-file`, allowing agents to create final
  JSON/DOCX/PDF reports from a calculation payload and completed AI analysis in
  one command.

### Changed

- Added timeout guards to CI and release workflows so accidental hangs fail
  visibly instead of blocking cross-platform validation indefinitely.

## [0.5.0] - 2026-05-08

### Fixed

- Corrected the headless Qimen/Dunjia Tianpan heavenly-stem flying logic so it
  starts from the Earth-pan palace of the hour Xun-head Liuyi stem and flies to
  the Earth-pan palace of the current hour stem, matching legacy Horosa output.
- Synchronized the same fixed Qimen result into `sanshiunited`, because the
  San Shi United aggregation now remains covered by a regression test that
  checks its embedded Qimen Tianpan.

### Added

- Added a golden regression case for `1998-02-20 20:48:00` / `壬戌` hour:
  `阳遁九局上元` with Tianpan stems `1庚 2丙 3丁 4戊 6己 7壬 8辛 9乙`.

## [0.4.2] - 2026-04-28

### Fixed

- Polished human-facing DOCX/PDF report rendering so natural-language AI
  answers become the primary consultation body without leaking machine-only
  schema, provenance, coverage, run identifiers, raw export dumps, or fallback
  section prose into the final document.
- Kept complete source coverage, delivery checks, provenance, and artifact
  metadata in the JSON report and memory manifest, preserving machine
  readability while making the PDF/DOCX report suitable for direct client
  reading.

### Added

- Added a Windows Codex stability prompt for cross-platform report, OpenClaw,
  memory, and MCP verification.

## [0.4.1] - 2026-04-28

### Fixed

- Send Java chart-family runtime payload dates with slash-formatted date prefixes
  while preserving normalized API inputs, fixing Windows `/chart` backend
  `200001 param error` failures seen through Cursor/OpenClaw-style MCP calls.
- Corrected the self-check sample longitude sign for west-longitude birth data.

### Changed

- CI now includes the Windows OpenClaw path plus full Horosa self-check coverage,
  so chart, report, memory, retrieval, dispatch, and AI answer write-back flows
  are verified on Windows before release confidence claims.

## [0.4.0] - 2026-04-28

### Added

- Community and repository metadata files for a more complete public GitHub
  surface.
- Cross-platform structured report layer for JSON, DOCX, and PDF artifacts.
- Report template, render, from-tool, and from-run surfaces across CLI and MCP.
- Machine-readable report contracts with delivery checklists, section coverage,
  search indexes, targeted answer requirements, and provenance.
- Local memory integration for report artifacts, AI answer write-back,
  artifact summaries, and text/artifact-kind retrieval.
- Full self-check coverage for report generation, storage, retrieval,
  targeted analysis, and delivery readiness across callable tools.

### Changed

- Switched repository-level public licensing metadata from Apache-2.0 to
  `GNU AGPL-3.0-only`, including root docs, citation metadata, and MCP server
  metadata.
- Version metadata is aligned across the Python package, MCP server metadata,
  citation file, README examples, and the headless JS package.

## [0.3.0] - 2026-04-05

### Added

- Offline runtime release packaging for macOS and Windows.
- JSON-first CLI, MCP surface, and dispatch tooling for local AI invocation.
- Structured `export_snapshot` and `export_format` contracts across callable
  divination tools.
- Phase 2 local techniques including `tongshefa`, `sanshiunited`, `suzhan`,
  `sixyao`, `otherbu`, `firdaria`, and `decennials`.
- Bundled Xingque hover knowledge readers for astrology, liureng, and qimen.
- Local record management with JSON artifacts, run manifests, and AI answer
  write-back.

## [0.2.0] - 2026-04-04

### Added

- Initial public-facing `horosa-skill` repository structure.
- Runtime install, doctor, and serve flows for local-first operation.
- Export protocol registry and snapshot parsing surfaces.

## [0.1.0] - 2026-04-04

### Added

- First packaged repository for GitHub-first Horosa Skill distribution.
