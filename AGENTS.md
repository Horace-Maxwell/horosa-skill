# Horosa Skill Agent Rules

These rules are for Codex, Cursor, Claude, OpenClaw, Open WebUI, and any agent connected to this repository or its MCP server.

## Do Not Hand-Calculate Horosa Methods

When the user asks for a Horosa technique result, call the Horosa MCP/CLI tool. Do not write ad-hoc Python, JavaScript, shell scripts, web-search snippets, or calendar formulas to recreate the method.

## Clarify Settings Before Calling

Do not silently call a technique with guessed settings when those settings change the result. If the user did not provide enough context, ask a concise question with concrete options first.

Use `horosa_agent_guidance` before direct tool calls when settings are unclear:

```json
{"tool_name":"liureng_gods","intent":"当前时间起大六壬"}
```

Equivalent CLI:

```bash
uv run horosa-skill agent guidance --tool liureng_gods --intent "当前时间起大六壬"
```

Hard rule:

- If the user says “当前时间”, you may use current local date/time/timezone.
- If location matters and no location is provided, ask whether to use client/current location or a specified city/longitude/latitude.
- If a method has multiple result-changing systems, ask the user to choose or explicitly accept Xingque defaults.
- If gender, house system, zodiacal system, 起局方式, 贵人体系, 六爻 lines, 地分, target year, or report format matters and is missing, ask before calling.
- For predictive astrology, natal data is not enough. Ask for target `datetime`, target location/timezone `dirLat` / `dirLon` / `dirZone`, or primary-direction settings when the selected tool needs them.
- Only use defaults without asking when the user says “默认 / 按星阙 / 快速起盘 / 你来决定”.

Runtime gate:

- Calculation tools and `horosa_dispatch` will reject unconfirmed calls with `agent_guidance.required`.
- After asking the user, pass `agent_confirmed_settings: true`.
- If the user explicitly accepts defaults, pass `defaults_accepted: true`.
- Add `clarification_notes` summarizing what was confirmed.
- If any tool returns `agent_guidance.required` or an `*.invalid_payload` error with `details.agent_recovery`, stop immediately and ask the user using `details.agent_recovery.prompt_to_user`.
- Do not retry the same tool until the user answered the missing settings or explicitly accepted defaults.
- Never satisfy the gate by setting `agent_confirmed_settings: true` yourself without a user answer.

This is especially important for:

- 大六壬: use `horosa_cn_liureng_gods` / `liureng_gods`.
- 大六壬行年: use `horosa_cn_liureng_runyear` / `liureng_runyear`.
- 奇门遁甲: use `horosa_cn_qimen` / `qimen`.
- 三式合一: use `horosa_cn_sanshiunited` / `sanshiunited`.
- 太乙、金口诀、八字、紫微、星盘、推运 and all other registered Horosa tools.

Predictive tool contracts:

- `solarreturn` / `lunarreturn`: birth data + `datetime` + `dirZone` + `dirLat` + `dirLon`; output must include natal chart, return chart, and return aspects.
- `givenyear`: birth data + `datetime` + `dirZone` + `dirLat` + `dirLon`; output must include natal chart, given-year chart, and aspects.
- `solararc` / `profection`: birth data + `datetime` + `dirZone`; output must include natal chart, progressed/profection chart, and aspects.
- `pd`: birth data + `pdtype` + `pdMethod` + `pdTimeKey` + `pdaspects`; output must include real primary-direction table rows.
- `pdchart`: birth data + `datetime` + `dirZone` + primary-direction method settings; output must include primary-direction chart table and aspects.
- `zr` / `firdaria` / `decennials`: birth data plus confirmed/default timeline settings; output must include timeline rows.

The same contracts are exposed through `uv run horosa-skill tool list`, `uv run horosa-skill agent guidance --tool <tool>`, MCP `horosa_agent_guidance`, and MCP tool docstrings.

Manual calculations can easily disagree with Xingque/Horosa because they bypass:

- Horosa input normalization.
- true solar time and timezone handling.
- Xingque-compatible defaults.
- local Java/Python/JS runtime layers.
- export snapshots and fixed report contracts.
- memory storage and retrieval.

## Current-Time Requests

For requests like “用当前时间起一个大六壬盘”:

1. Get the current local date/time/timezone.
2. Build a normal Horosa payload with `date`, `time`, `timezone` or `zone`, location/longitude/latitude when available, and the user question.
3. Call `horosa_cn_liureng_gods`.
4. Read `export_snapshot.export_text`, `export_format.sections`, and `summary`.
5. Explain from those returned sections only.
6. If the user wants persistence or a document, use memory/report tools.

Never replace step 3 with `Exec`, `python3`, a web search, or handwritten 六壬 formulas.

## Daliuren Defaults

Horosa Skill follows Xingque-compatible defaults:

- Default `guirengType` is `2` / `星占法贵人`.
- Only use `guirengType=0` (`六壬法贵人`) or `guirengType=1` (`遁甲法贵人`) when the user explicitly requests that system or an existing saved case already specifies it.

## Safe Explanation

Never tell users that 大六壬 requires MongoDB, port `7897`, Xingque Desktop, a remote database, or an external service unless a current Horosa `doctor` or `openclaw-check` result explicitly says so.

If a section is missing, say that the local tool did not return that section and rerun `doctor` / `openclaw-check`; do not invent a dependency.

---

# Maintainer & Build Notes (ken backend, offline runtime)

The section above is for AI **clients consuming** Horosa Skill. This section is for any agent or
maintainer **modifying / building / releasing** this repository.

**Standing rule (force-sync on every issue):** whenever you hit a problem, gotcha, or fix while working
on this repo, you MUST update **both** docs in the same change and keep them in sync — this harness doc
(`AGENTS.md`) **and** the skill doc (`skills/horosa-agent/SKILL.md`). Do not update one and leave the
other stale. Keep these notes in *this* repo — never write skill-repo lessons into the upstream 星阙
(`Horosa-Primary Direction Trial`) working tree; the skill repo is self-contained and ships its own
agent guidance.

## Third-party engine provenance & MIT obligation (ken)

The ken engines are open-source, **MIT-licensed**, by **kentang2017**: `kinqimen`
(<https://github.com/kentang2017/kinqimen>), `kintaiyi` (<https://github.com/kentang2017/kintaiyi>),
`kinjinkou` (<https://github.com/kentang2017/kinjinkou>). MIT requires the copyright + license text to
travel with every distribution, so:

- **Never strip `Horosa-Web/vendor/{kinqimen,kintaiyi,kinjinkou}/LICENSE`** from the runtime payload.
  The packaging strip must leave these `LICENSE` files intact; `verify_runtime_release.py` requires the
  engine dirs, and the LICENSE files ship inside them.
- The acknowledgement lives in `README.md` / `README_EN.md` ("致谢 / Acknowledgements") and in the
  GitHub release notes. If you bump or re-vendor an engine, keep that credit accurate.

## Compute model: ken is authoritative, JS only formats

`qimen` / `taiyi` / `jinkou`, and the 奇门 + 太乙 legs of `sanshiunited`, are computed by 星阙's **ken
backend** — the `kinqimen` / `kintaiyi` / `kinjinkou` Python engines mounted on the chart service
(`:8899`) at `/qimen/pan` · `/taiyi/pan` · `/jinkou/pan`. The skill's charts therefore match the 星阙
desktop app value-for-value.

- `service.py`: `_run_{qimen,taiyi,jinkou}_tool` fetch the JS-scaffold prerequisites (nongli + jieqi for
  qimen, liureng for jinkou), call the ken endpoint via `_call_remote`, then pass `ken_response` into
  `js_client.run(...)`. The three ken endpoints are listed in `_PYTHON_CHART_ENDPOINTS` so they route to
  the chart server (`:8899`), not Java (`:9999`).
- `horosa-core-js` does **not** compute these — it is a **ken-response → aiExport.js formatter**.
  `tools/{qimen,taiyi,jinkou}.js` overlay the ken response onto a local scaffold via 星阙's
  `normalizeKinqimenData` / `normalizeBackendPan` / `normalizeKinjinkouData`, then `build*SnapshotText`
  emits the `export_snapshot` sections. ken stays the sole compute authority; the JS falls back to the
  local scaffold only when `ken_response` is missing/malformed (graceful, but not the normal path).

## ⚠️ ken endpoints fail with HTTP 200 — guard on `source`, never trust the status code

The chart-service ken handlers (`web{qimen,taiyi,jinkou}srv.py`) wrap everything in
`try/except` and on **any** exception return **HTTP 200** with `{"ResultCode": -1/1, "Result":
"<engine> ... failed"}` (a string `Result`). Pitfalls this creates:

- `_call_remote` only raises on transport/param errors, and `_unwrap_result` returns that failure
  envelope unchanged (it's still a dict). So a ken failure looks like a successful call.
- If you forward it to the JS formatter, the JS guard (`ken.selected || ken.raw` etc.) is falsy and
  the formatter **silently falls back to the old local-engine chart** — a wrong result with no error.

The fix already in place: `service.py::_require_ken_pan` checks `ken_response.get("source") == engine`
right after each `_call_remote("/…/pan", …)` and raises `tool.ken_compute_failed` otherwise. **Keep this
guard.** If you add another ken-backed technique, call `_require_ken_pan` on its response too, and never
rely on HTTP status alone to decide whether ken succeeded. Regression test:
`tests/test_service.py::test_qimen_fails_loudly_when_ken_returns_failure_envelope`. Note this means test
fakes for ken endpoints must return a body with the right `source` (see `FakeClient` in `test_service.py`).
- `tongshefa` is pure headless JS (no ken engine). `sanshiunited` composes ken 奇门+太乙 with the 大六壬 leg.

## Re-vendoring the JS engines from 星阙

When refreshing `horosa-core-js/src/vendor/{dunjia,taiyi,jinkou}` from 星阙's frontend engines, copy the
**full** 星阙 files and apply exactly this headless transform:

- add `.js` to sibling imports;
- drop the 3 backend imports (`request` / `{ServerRoot,ResultKey}` / `{buildKentangEndpoint}`);
- drop **only** the `fetch*Pan` network helpers;
- **keep** the `normalize*` overlay functions (`normalizeKinqimenData`, `normalizeBackendPan`,
  `normalizeKinjinkouData`) — these are what turn a ken response into a 星阙 pan object.

For taiyi, build the snapshot from `{ ...pan, sections: undefined }` — ken's in-app detail `sections`
are not part of the aiExport contract and will otherwise show up as unknown sections.

## Offline runtime packaging gotchas (these have bitten us)

- **flatlib must survive the strip.** `scripts/package_runtime_payload.sh` must keep its
  `flatlib-ctrad2/flatlib` rsync line. Dropping it makes the bundled chart service fail with
  `ModuleNotFoundError: No module named 'flatlib'`.
- **`site-packages` tests must survive the strip.** The python-strip removes `test`/`tests` dirs, but it
  must `-prune` `site-packages` first. If `site-packages/astropy/tests` gets removed, `kintaiyi`'s
  `import astropy` fails and the `/taiyi/pan` mount is silently skipped.
- **ken deps must be bundled.** The chart service needs `bidict` (kinqimen), `numpy` · `kerykeion` ·
  `ephem` (kintaiyi), `pendulum` (kinjinkou) **on top of** the base chart deps. macOS's embedded Python
  already has them; the Windows `runtime/windows/bundle/wheels` set MUST include them too.
- **Windows `PYTHONPATH` must include `Horosa-Web/vendor`.** `start_horosa_local.ps1` puts the vendor
  root on `PYTHONPATH` so `import kinqimen/kintaiyi/kinjinkou` resolve. `package_runtime_payload.sh` and
  `build_runtime_release_windows.py` both bundle `Horosa-Web/vendor/{kinqimen,kintaiyi,kinjinkou}`.
- **Graceful kentang mount.** The packaging scripts patch the *staged* `kentang/registry.py` mount to
  skip engines that aren't bundled, so the chart service still boots offline (`_load_service` does a bare
  `__import__` and would otherwise hard-fail on a missing engine).

## `pkill` will take down the live 星阙 stack

Both the bundled offline chart service and the live 星阙 dev chart service run `webchartsrv.py`. Running
`pkill -f webchartsrv.py` to stop a test service (e.g. on `:8896`) **also kills the live 星阙 `:8899`**.
Stop services by port/PID, not by process-name match.

## Verifying skill changes locally

1. Fix the venv if it's broken: the skill `.venv` symlinking miniconda trips macOS library-validation on
   `pydantic_core`. Rebuild with `uv venv --clear --python-preference only-managed --python 3.12 && uv sync`
   (uv-managed CPython has no library-validation).
2. Bring up the 星阙 stack: `cd Horosa-Web && HOROSA_SKIP_UI_BUILD=1 ./start_horosa_local.sh` → Java `:9999`
   + chart `:8899`.
3. Run `uv run pytest`. The qimen/taiyi/jinkou/sanshi cases in `tests/test_local_js_tools.py` are
   `@requires_runtime` integration tests that **skip** when `:8899`/`:9999` are down — a green run with
   them skipped is not a full verification. Acceptance: each emits its aiExport sections with a clean
   export contract (`missing_selected_sections == []` and `unknown_detected_sections == []`).

## The installed runtime can be stale (CLI/MCP fall back to local compute)

`js_client` resolves the JS engine via `HOROSA_CORE_JS_ROOT` → installed-manifest
`horosa_core_js_root` (`~/.horosa/runtime/current/horosa-core-js`) → the package's bundled
`horosa-core-js`. If the **installed** runtime predates the ken migration, it lacks
`normalizeKinqimenData`, so a real CLI/MCP call returns the local scaffold (`source: null`) instead of
ken (`source: kinqimen`). Two fixes:

- For development, point at the repo's engine: `HOROSA_CORE_JS_ROOT="$PWD/horosa-core-js"`.
- For users, **re-install the matching runtime release** — both runtime builders rsync the repo's
  (ken-fed) `horosa-core-js` into the payload, so a fresh install carries the formatter.

## Stability invariants (don't regress these)

A global stability pass hardened these; keep them true when you touch the relevant code:

- **`run_tool` always returns a `ToolEnvelope`, never lets an unexpected exception escape.** Tool
  execution + the snapshot/summary/export post-processing run inside a try that catches
  `HorosaSkillError` **and** a last-resort `except Exception` → `ok=False` / `tool.internal_error`.
  Only invalid-payload `ValidationError` (raised *before* that try) intentionally surfaces as
  `tool.invalid_payload`. Do not add a tool/post-processing path that can raise out of `run_tool` —
  it would crash the CLI, break the MCP session, or abort a whole `dispatch`.
- **Surfaces never dump a traceback.** CLI file reads (`--ai-report-file` / `--ai-answer-file`) raise
  clean `typer.BadParameter`; the MCP `horosa_report_*` handlers wrap unexpected renderer/IO errors via
  `_mcp_internal_error_payload`; subprocess calls carry timeouts (incl. `openclaw-check --full`, 900s).
- **`input_normalization` degrades, never crashes.** The date/time regexes are shape-only (they accept
  month `13`, day `45`), so anything that builds a `datetime` from them must tolerate `ValueError`
  (see `_combine_date_time`). IANA-zone→offset conversion uses the *chart date*, not `now()`. `Z`/`UTC`/
  `GMT` → `+00:00`. Compact coords like `121e28` are parsed as 121°28′ (NOT float scientific notation).
- **Runtime manager:** close file handles before `shutil.rmtree` on the Windows start path; a missing
  local `--archive` raises `RuntimeError` (which `install` catches), not a raw tarfile error. Never kill
  chart services by process-name (`pkill -f webchartsrv.py` would also kill a live :8899) — the stop
  script already scopes kills by the runtime root path; keep it that way.
