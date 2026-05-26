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
maintainer **modifying / building / releasing** this repository. **Standing rule: whenever you hit a
new gotcha while working on this repo, append it here** so the next agent sees it. Keep these notes in
*this* repo — never write skill-repo build lessons into the upstream 星阙 (`Horosa-Primary Direction Trial`)
working tree; the skill repo is self-contained and ships its own agent guidance.

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
