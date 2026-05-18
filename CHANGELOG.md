# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows a release-oriented changelog style.

## [Unreleased]

## [0.5.0] - 2026-05-08

### Fixed

- Corrected the headless Qimen/Dunjia Tianpan heavenly-stem flying logic so it
  starts from the Earth-pan palace of the hour Xun-head Liuyi stem and flies to
  the Earth-pan palace of the current hour stem, matching legacy Horosa output.
- Synchronized the same fixed Qimen result into `sanshiunited`, because the
  San Shi United aggregation now remains covered by a regression test that
  checks its embedded Qimen Tianpan.
- Completed the local headless LiuReng export surface so `liureng_gods` and
  `liureng_runyear` emit four lessons, three transmissions, and pan sections
  without implying any MongoDB, port 7897, desktop-app, or external-service
  dependency.
- Hardened every callable divination export against bare empty sections and
  dependency hallucination wording, with regression coverage across all
  machine-readable export contracts.

### Added

- Added a golden regression case for `1998-02-20 20:48:00` / `壬戌` hour:
  `阳遁九局上元` with Tianpan stems `1庚 2丙 3丁 4戊 6己 7壬 8辛 9乙`.
- Added `skills/horosa-agent/SKILL.md`, an agent-facing usage skill that
  explains tool selection, report generation, memory write-back, OpenClaw
  checks, and anti-hallucination rules for MCP/CLI clients.
- Added CLI support for `report from-tool --ai-answer-text`,
  `--ai-answer-file`, and `--ai-report-file`, allowing agents to create final
  JSON/DOCX/PDF reports from a calculation payload and completed AI analysis in
  one command.

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
