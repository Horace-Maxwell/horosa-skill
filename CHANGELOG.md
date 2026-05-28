# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows a release-oriented changelog style.

## [Unreleased]

### Fixed

- **0.7.0 release: completed the version-string bump.** The v0.7.0 commit bumped `pyproject.toml` to
  `0.7.0` but left `__init__.py.__version__`, `server.json` (the MCP registry manifest, ×2), `CITATION.cff`,
  and the "current version" references in `README.md` / `README_EN.md` at `0.6.3` — so `horosa-skill
  --version` and the MCP-registry-declared version were stale for the 0.7.0 line. All five files now read
  `0.7.0`. `docs/DATA_CONTRACTS.md`'s `tool envelope: 0.6.3` was left as-is (it tracks an independent
  envelope-schema version, not the package version).

## [0.7.0] - 2026-05-27

### Added — 星阙 v2.2.0 数算 + 调波盘 modules

- **`canping` (邵子参评数 / 金锁银匙).** New local tool mirroring 星阙's `CanPingMain` + `canpingLocal`:
  year-纳音 定部 → 四柱起数 → 本命/大运 歲運条文. The four pillars are computed **in-process** by a
  newly vendored bazi chain (`horosa-core-js/src/vendor/bazi/` → the `lunar-javascript` npm package),
  not the ken backend — so it runs with no chart-service round-trip. Export contract `['起盘','本命',
  '大运']` (the snapshot's `大运·歲運` label legacy-maps to `大运`; the full 1–120 流年 table is exposed
  under `data.canping.series`, matching 星阙 where 流年 lives in the UI table, not the snapshot).
- **`heluo` (河洛理数).** New local tool mirroring 星阙's `HeLuoMain` + `heluoLocal`: 天地数 → 先天/后天卦
  与元堂 → 命运篇 judge + 大限·岁运 with 元堂爻辞. Also pillar-driven in-process; the 命运篇 needs the real
  节气, so the formatter ports `HeLuoMain.solarTerm` (uses `lunar-javascript`'s JieQi table). Export
  contract `['起命','先天卦','后天卦','命运篇','大限']` (the dynamic `先天·<卦>…`/`后天·<卦>…`/`大限·岁运`
  labels legacy-map to the declared section names).
- **`harmonic` (调波盘).** New backend chart-extra tool (`POST /astroextra/harmonic` on the Python chart
  service): 本命黄经×调波数 → 调波位置 + 同频(合相). Returns structured `positions`/`conjunctions`/`chart`
  plus a readable snapshot. 星阙 has no aiExport contract for 调波盘 (UI/lab-only), so the skill exposes
  it as structured data without a formal export technique.
- Tool count is now **42** (was 39): `canping`, `heluo` (`horosa_cn_*`) and `harmonic`
  (`horosa_astro_harmonic`) are exposed on every surface (MCP/CLI/router/agent-guidance/reports).

### Build

- **Offline runtime now bundles `lunar-javascript`.** `package_runtime_payload.sh` and the Windows
  builder run `npm install --omit=dev` in `horosa-core-js` before copying it, and
  `verify_runtime_release.py` now requires `horosa-core-js/node_modules/lunar-javascript/package.json`
  in both archives — without the bundled package, `canping`/`heluo` would throw
  "Cannot find package 'lunar-javascript'" at runtime. `horosa-core-js` declares it as a dependency.

## [0.6.3] - 2026-05-27

### Aligned with 星阙

- **Re-vendored the offline runtime's ken engines to 星阙's current bug-fixed versions.** The v0.6.2
  runtime archives bundled pre-fix ken engines; v0.6.3 rebuilds the offline runtime from 星阙's current
  `vendor/` so the bundled `kinqimen` carries the v2.1.6 奇门历法 fix and `kintaiyi` carries the v2.1.8
  月柱节气-边界 fix (verified: the bundled `kintaiyi/config.py` now contains the `JIE_TERMS`/`JD2DD`
  交节-crossing correction). Offline qimen/taiyi compute is now value-identical to the 星阙 desktop app.
- **taiyi 四柱 now prefer the ken engine's 节气-corrected pillars.** 星阙 v2.1.8 fixed the month-pillar
  节气-boundary in the bazi engines (kinwuzhao/kinastro/kintaiyi) and switched taiyi's displayed 年/月/日/时柱
  from raw 农历 to the fixed bazi. The skill computes taiyi via kintaiyi, so its `pan.ganzhi` already
  carries that fix; `applyNongliDisplay` now prefers `pan.ganzhi` over `/nongli/time` `*GanZi` (falling
  back only if ken omits it) — same-engine, internally consistent, no `lunar-javascript` dependency.
  (Together with the re-vendored runtime above, offline taiyi pillars are now correct at 节气 boundaries.)

### Fixed

- **`evaluation_lock` no longer risks killing a live process on Windows (and the Windows CI is green).**
  `_pid_liveness` probed with `os.kill(pid, 0)`, which is a safe no-op on POSIX but maps to
  `TerminateProcess` on Windows — i.e. it would *terminate* a live lock owner. It now short-circuits to
  `unknown` on Windows (stale locks there are reclaimed by the age threshold, never by killing a PID).
  The PID-reclaim test is marked POSIX-only; the age-reclaim path stays cross-platform. Fixes the
  `windows-smoke` CI job. (Found by inspecting GitHub CI after the macOS work.)
- **Windows runtime builder no longer requires `rsync`.** `build_runtime_release_windows.py` shelled out
  to the `rsync` binary for its in-payload copies, which does not exist on Windows — so the "Windows"
  builder crashed on its first copy (`FileNotFoundError: [WinError 2]`) and could only run on a machine
  that already had rsync. `rsync_copy()` now uses a portable `shutil.copytree` (same copy-into-DST
  semantics, same exclude set, `dirs_exist_ok=True`), so the single builder produces the win32-x64
  payload natively on Windows as well as macOS/Linux. Verified by building and natively running
  `horosa-runtime-win32-x64-v0.6.2.zip`: chart service boots and `/qimen/pan` · `/taiyi/pan` ·
  `/jinkou/pan` return `ResultCode 0` with `source` `kinqimen`/`kintaiyi`/`kinjinkou`, and tongshefa
  (bundled node) returns `右卦 火地晋` → `right_elem 金` / `main_relation 实克思`.
- **`india_chart` no longer crashes (`'list' object has no attribute 'get'`).** Indian charts return
  `normalAsp`/`immediateAsp`/`signAsp` as empty *lists* (no Western aspects), but `_build_aspect_section`
  assumed dicts and called `.get()` on them — so `india_chart` failed with `tool.internal_error` and the
  full self-check crashed at its `report_template` step. The aspect builder (and `_build_possibility_section`)
  now coerce non-dict aspect/predict fields to `{}`. `india_chart` produces a clean export again; the full
  39-tool self-check passes end-to-end. (Surfaced by the new `run_tool` internal-error guard, which turned
  a raw crash into a structured error.) Regression test added.
- **Release verifier no longer greenlights an empty required directory (false-confidence gate).**
  `verify_runtime_release.py` checked directory requirements with `entry.startswith(required)`, which
  for a `.zip` matched an empty directory's own marker entry (`…/swefiles/`) — so a maintainer-zipped
  Windows payload with an empty `swefiles/` (ephemeris), `astropy/`, or `vendor/kin*/` (ken engines)
  could pass verification while being broken at runtime; tar and zip also validated at different
  strictness. It now requires a real file strictly *inside* each required directory (tar + zip
  identical). Also removed a dead `isdir()` ternary. Regression tests added.
- **JS CLI tolerates a null/scalar payload.** `bin/cli.mjs` now coerces a parsed payload that is `null`
  or a scalar (stdin literally `null`, a number, a string) to `{}`, so the tools degrade like any other
  malformed input instead of throwing `Cannot read properties of null` on `payload.field`
  (`liureng`/`taiyi`/`qimen`). Defensive only — the Python service always sends a validated object;
  the regression covers the JS boundary directly.

## [0.6.2] - 2026-05-26

### Aligned with 星阙 (value-identical)

- **统摄法 (tongshefa) element source.** The headless engine derived each hexagram's element from its
  *upper trigram*; 星阙 takes it from the 京房本宫 palace (`Gua64[i].house.elem`). These disagree for
  32 of 64 hexagrams (e.g. 火地晋 → 金 not 火; 天泽履 → 土 not 金), so `left_elem` / `right_elem` and the
  headline `main_relation` were wrong for half of all inputs. Added the 64-hexagram 京房 palace-element
  table (mirrored from `GuaConst.js`) and a `hexElem()` lookup; verified all 64 names resolve and the
  tongshefa aiExport contract (本卦/六爻/潜藏/亲和) is unchanged. The najia/六合/升降 detail that 星阙
  renders is UI-only — it is not part of the `aiExport.js` tongshefa contract, so the skill stays a
  faithful subset.
- **decennials (十年大运) port.** Two value bugs vs 星阙's `utils/decennials.js`: (1) `resolve_l1_count`
  used an integer ceil-trick on a *float* age, dropping the final L1 lord for any chart landing in the
  first <1 minute after a ~10.6-year boundary — now uses `math.ceil` like the JS; (2) Python's `round`
  is banker's rounding while JS uses `Math.round` (half-up), so the period-distribution math could
  diverge by ±1 minute (±5 at the valens step) in the 365.25-day calendar mode — added a `_js_round`
  helper. Cross-checked the port against 星阙's own `decennials.test.js` golden vectors (traditional +
  365.25 calendar + hephaistio) — value-identical. Both fixes are pure compute, fully cross-platform.

### Fixed

- **`run_tool` never crashes the surface anymore.** Tool execution + the snapshot/summary/export
  post-processing touch backend-shaped data and could raise unexpected `ValueError`/`KeyError`/
  `IndexError`/`TypeError` that escaped as a CLI traceback, broke the MCP session, or aborted a whole
  `dispatch`. `run_tool` now wraps any unexpected error into a clean `ok=False` envelope
  (`tool.internal_error`). Bad-payload `ValidationError` still raises `tool.invalid_payload` as before.
- **Input normalization no longer crashes on calendar-invalid dates.** The date/time regexes accept
  digit-shaped but invalid values (`2020-02-30`, month `13`); paired with an IANA timezone name this
  reached `datetime()` and raised straight out of normalization. It now degrades gracefully and lets
  the backend reject the bad date with a structured error.
- **UTC designators normalize to a real offset.** `Z` / `UTC` / `GMT` were passed through verbatim
  instead of `+00:00`; now canonicalized (while `UTC+8` / `GMT+05:30` still parse correctly).
- **`report from-tool` no longer dumps a traceback** on a missing/invalid `--ai-report-file` /
  `--ai-answer-file`; these are now clean `BadParameter` errors.
- **`openclaw-check --full` can no longer hang forever** — added a 900s subprocess timeout.
- **MCP report tools never break the session** — `horosa_report_*` now convert an unexpected
  renderer/IO error into a structured `tool.internal_error` payload.
- **`install` reports a clean error for a missing local `--archive`** instead of a raw
  tarfile/shutil traceback; the Windows runtime-start path no longer leaks file handles + a temp dir.
- **Trace writes are best-effort.** A local JSONL trace-write failure (unwritable/deleted trace dir,
  disk full) no longer escapes the span's `finally` and crashes or masks the operation being traced.
- **Node failures stay within the transport contract.** `js_client` now wraps a missing/unstartable
  Node runtime (`FileNotFoundError`) as `js_engine.node_unavailable` and a Node timeout as
  `js_engine.timeout`, instead of letting a raw `OSError`/`TimeoutExpired` escape the engine layer.
- **Evaluation lock recovers from a crashed run.** `acquire_evaluation_lock` now reclaims a stale lock
  left by a `kill -9`/OOM/power-loss run (dead recorded PID on POSIX, or an age threshold when liveness
  is indeterminate — Windows/corrupt lock), instead of deadlocking every future evaluation for 60s +
  failure until manual deletion. A live owner is never reclaimed.
- **Report rendering is atomic.** `render_report` writes to a temp sibling and `os.replace()`s into
  place, so a mid-render DOCX/PDF failure can never leave a truncated/corrupt artifact at the target.
- Defensive guards: `_build_export_provenance` tolerates an unknown technique (no `NoneType` deref);
  `build_validation_recovery` skips non-dict error entries.

## [0.6.1] - 2026-05-26

### Fixed

- **Silent ken→local divergence.** The ken chart endpoints return HTTP 200 even on failure
  (`{"ResultCode": -1, "Result": "<engine> ... failed"}`). Because that envelope is still a dict,
  `_call_remote` did not treat it as an error, and the JS formatter would silently fall back to its
  *local* scaffold compute — producing a qimen/taiyi/jinkou chart that does not match 星阙, with no
  error surfaced. Added `_require_ken_pan` (checks the `source` marker) to `_run_{qimen,taiyi,jinkou}_tool`
  so a failed ken response now raises `tool.ken_compute_failed` instead of degrading silently
  (`sanshiunited` inherits the guard via its qimen/taiyi legs). Regression test added.
- `verify_runtime_release.py` now requires the `Horosa-Web/vendor/{kinqimen,kintaiyi,kinjinkou}`
  engine dirs in both platform archives, so a release that drops the ken engines fails verification
  instead of shipping a runtime that cannot mount `/qimen/pan` · `/taiyi/pan` · `/jinkou/pan`.
- `build_runtime_release_windows.ps1`: fixed a `param()`-ordering parse error (the script never ran),
  the archive prefix (now keeps the required `runtime-payload/` root), and the output filename
  (now `horosa-runtime-<platform>-v<version>.zip`, matching the Python builder + verifier).
- `build_runtime_release_windows.py`: derive the embedded-Python stdlib zip name from the discovered
  `._pth` instead of hardcoding `python311.zip`, so a future embed bump cannot silently orphan the stdlib.

## [0.6.0] - 2026-05-25

### Changed

- Unified 奇门遁甲 / 太乙 / 金口诀 (and the 奇门 + 太乙 legs of 三式合一) onto the
  Horosa **ken** backend, matching what 星阙 itself now computes. These techniques
  previously ran the headless JS engine's *local* algorithm; they now call the
  ken chart-service endpoints (`/qimen/pan` → kinqimen, `/taiyi/pan` → kintaiyi,
  `/jinkou/pan` → kinjinkou) so the skill and the product produce identical charts.
- The bundled `horosa-core-js` engine is repurposed as a **ken-response formatter**:
  ken stays the sole compute authority, and `normalizeKinqimenData` /
  `normalizeBackendPan` / `normalizeKinjinkouData` + `buildDunJiaSnapshotText` /
  `buildTaiyiSnapshotText` / `buildJinkouSnapshotText` reformat the ken response into
  星阙 `aiExport.js` sections, so the structured `export_snapshot` contract is unchanged.
- `三式合一` (`sanshiunited`) inherits ken automatically — it composes the ken
  奇门 + 太乙 results with the 大六壬 leg.
- `统摄法` (tongshefa) keeps its pure headless JS engine (it has no ken backend).

### Added

- The offline runtime payload now bundles the `kinqimen` / `kintaiyi` / `kinjinkou`
  ken engines (embedded Python already carries their deps: bidict / numpy / kerykeion
  / ephem / pendulum), and the staged chart-service kentang mount skips any engine that
  is not bundled so the chart service still boots offline.

### Documentation

- Rewrote `README.md` / `README_EN.md` and refreshed `horosa-skill/README.md` to lead with the
  ken compute model and bump the baseline to `0.6.0`.
- Added a "ken 计算后端" section to `docs/ARCHITECTURE.md`, a ken note to the Windows report-stability
  prompt, and a "Maintainer & Build Notes (ken backend)" section to the repo harness doc `AGENTS.md`
  plus a maintainer cross-reference in `skills/horosa-agent/SKILL.md` (re-vendoring transform, offline
  packaging gotchas, the `pkill webchartsrv.py` caveat, venv repair, stale-runtime fallback, local
  verification).

### Verified

- qimen / taiyi / jinkou / sanshiunited run end-to-end against the live ken chart
  service (`:8899`); each emits its 星阙 aiExport.js sections (qimen:
  起盘信息/盘型/盘面要素/奇门演卦/八宫详解/九宫方盘; taiyi: 起盘信息/太乙盘/十六宫标记;
  jinkou: 起盘信息/金口诀速览/金口诀四位/四位神煞) with a clean export contract
  (no missing / unknown sections). Full skill test suite green (164 passed, incl. live ken
  integration tests).

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
