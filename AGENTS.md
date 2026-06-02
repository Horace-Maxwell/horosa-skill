# Horosa Skill Agent Rules

These rules are for Codex, Cursor, Claude, OpenClaw, Open WebUI, and any agent connected to this repository or its MCP server.

---

## 🔴 MANDATORY: Problem-Logging Protocol (read this first, every session)

**This is an enforced rule, not advice. Any agent or maintainer who hits a problem, gotcha, surprising
behavior, wrong assumption, or ships a fix while working in this repo MUST record it in THIS file
(`AGENTS.md`) before the work is considered done.** No exception is too small — if it bit you, it will
bite the next agent. The whole point of this repo's harness doc is to be the single, permanent sink for
every lesson learned.

**What "record it" means — do ALL of these in the same change that fixes/discovers the problem:**

1. **Append a gotcha bullet to the most relevant `## … gotchas` / invariants section of this file**
   (e.g. *Offline runtime packaging gotchas*, *Stability invariants*, the ken/JS-engine sections). State
   the **symptom**, the **root cause**, and the **fix / guard** so the next agent recognizes it fast.
2. **Sync `skills/horosa-agent/SKILL.md`** if the lesson affects how an AI *client* calls the tools
   (payload fields, gating, section contracts). Maintainer/build-only lessons stay in `AGENTS.md` only,
   but never leave the two docs contradicting each other.
3. **Add a `CHANGELOG.md` `[Unreleased]` entry** for any code/behavior/build/CI change.
4. **If it's a release/build/CI gap, add a code-level guard** (a `verify_*` check, a CI step, a schema
   constraint, a `require_path`) so the gotcha can't silently recur — a doc note alone is not enough for
   anything that a script or CI can assert.

**Self-audit gate (every release + every "check for bugs" pass):** re-read the gotcha sections, confirm
each still holds, and confirm anything you just learned has been written down here. Treat an undocumented
recurring problem as a regression.

**Scope rule:** keep every lesson in *this* repo (`AGENTS.md` + `SKILL.md`). **Never** write skill-repo
lessons into the upstream 星阙 (`Horosa-Primary Direction Trial`) working tree — the skill repo is
self-contained and ships its own agent guidance.

---

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

**Standing rule (force-sync on every issue):** this is the same enforced protocol stated at the top of
this file under **🔴 MANDATORY: Problem-Logging Protocol** — every problem/gotcha/fix gets written into
`AGENTS.md` (+ `SKILL.md` when client-facing, + `CHANGELOG.md`, + a code guard when assertable), in the
same change, kept in sync, and never written into the upstream 星阙 tree. If you are reading this section
first, scroll up and read that protocol now; it governs everything below.

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
- `canping` (邵子参评数) and `heluo` (河洛理数) are **原生·非 ken** tools: they compute their four pillars
  **in-process** via the vendored bazi chain (`horosa-core-js/src/vendor/bazi/` → the `lunar-javascript`
  npm package), then do their own 起数/起卦 + 条文 lookup. No chart-service round-trip. `harmonic` (调波盘)
  is the opposite — a backend chart-extra (`/astroextra/harmonic`) with no aiExport contract (UI/lab-only
  in 星阙), so the skill returns structured `positions`/`conjunctions`/`chart` + a readable snapshot only.

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

### Re-vendoring the 数算 engines (canping / heluo) — different from the ken formatters

`canping`/`heluo` are NOT ken-fed; they are vendored **whole** from 星阙 with almost no transform:

- vendor `src/vendor/bazi/{ZWConst.js,baziShenShaLocal.js,baziLunarLocal.js}` (the bazi chain),
  `src/vendor/canping/{canpingLocal.js,data/canpingTiaowen.json}`, and
  `src/vendor/heluo/{heluoLocal.js,data/heluoTiaowen.json}`;
- the **only** edits are (1) point sibling imports at the vendored copies and (2) add the JSON import
  attribute: `import X from './data/*.json' with { type: 'json' };` — **without it raw Node throws
  "needs an import attribute of type: json"** (this bit us). `heluoLocal.js` deliberately imports only
  `heluoTiaowen.json` (NOT `heluoNihaixiaRaw.json` — the 倪海厦 data is already compiled into the tiaowen).
- 星阙 has a real **section-name mismatch**: `canpingLocal.buildSnapshotText` emits `[大运·歲運]` and
  `heluoLocal` emits `[先天·<卦>…]/[后天·<卦>…]/[大限·岁运]`, but `aiExport.js` declares `大运`/`先天卦`/
  `后天卦`/`大限`. The skill keeps the snapshot **byte-identical** and reconciles via
  `map_legacy_section_title` in `exports/registry.py` (same mechanism as `三传(…)→三传`). canping's `流年`
  is intentionally NOT in the contract — 星阙's snapshot omits it (the accurate 流年 table is in
  `data.canping.series`).
- the formatter (`src/tools/{canping,heluo}.js`) mirrors `CanPingMain.js`/`HeLuoMain.js`'s `getModel`:
  `buildLocalBaziResult(params).bazi` → pillars → `calculate`/`judge`/`daYun` → `buildSnapshotText`.
  heluo additionally ports `HeLuoMain.solarTerm` (the 命运篇 needs the real 节气 from `lunar-javascript`).
  `timeAlg` default is **1** (clock time) to match 星阙's `fieldVal(f,'timeAlg',1)` — note `timeAlg===0`
  means 真太阳时 (the only value that triggers the longitude+EoT correction).

### v2.4.0 西占 (Western) techniques — agepoint / distributions / mundane / natal extras

These are 星阙 v2.4.0 additions; integrating them required **re-vendoring `vendor/runtime-source` from
星阙 v2.4.0** (the bundled chart service then carries `/predict/agepoint`, `/predict/dist`,
`/astroextra/greatconj`, and the enriched `/chart`). Patterns:

- **`agepoint` / `distributions` are simple backend predict tools** (like harmonic): `_call_remote`
  (`/predict/agepoint` → `{agepoint:{points:[…]}}`; `/predict/dist` → `{dist:[…]}`) + a Python snapshot
  builder (`_build_agepoint_snapshot_text` / `_build_distributions_snapshot_text`, ports of 星阙's frontend
  builders). Both endpoints are in `_PYTHON_CHART_ENDPOINTS`. Each has a single-section export contract.
- **本命增补 (12分度 / 主宰星链 / 寿命格局) is JS-computed, Python-formatted.** 星阙 computes these in the
  frontend (`astroAiSnapshot.js`), reading the chart object. The skill vendored the needed 星阙
  `divination/` engine subtree into `horosa-core-js/src/vendor/divination/` (chartFacts + the Ptolemy
  **lifespan** engine + `data/{signs,dignities,planets,houseMeanings}` + `engine/utils` — a clean 8-file
  closure, no npm deps) and wrote `src/vendor/astroextra/natalExtras.js` + the `astroextra` JS tool that
  return **structured** data (dodeca pairs / dispositor chains / the runLifespan res). `service.py`'s
  `_attach_natal_extras` (only for `chart` + `mundane`) calls it via `js_client`, and
  `_build_natal_extra_sections` formats the 3 sections with `_astro_msg` — so the JS does compute, Python
  does the Chinese formatting (no `AstroText`/`whichTerm` vendored). They are inserted into the astrochart
  snapshot before `可能性`; the `astrochart` preset gained the 3 sections.
- **`mundane` (世俗入宫盘) is a composite** local tool: `/jieqi/year` (seedOnly, `jieqis:[term]`) → find
  the `jieqi24` entry whose `jieqi==term` → its `time` is the precise ingress moment → `/chart` at that
  instant → `_attach_natal_extras('mundane', …)` → prepend a `[世俗入宫]` head to the astrochart snapshot.
  Input is **year + 入宫节气 + place** (date/time are derived, not user input).
- **Re-vendoring `vendor/runtime-source` (the skill's copy) is allowed and READ-ONLY on 星阙.**
  `sync_vendored_runtime_sources.sh` with `HOROSA_SOURCE_ROOT=<星阙 tree>` does it. After it, re-apply the
  graceful-kentang-mount patch to the vendor's `astropy/websrv/kentang/registry.py` if you run the chart
  service directly from `vendor/` (the **build** scripts patch the staged copy automatically; the raw
  vendor hard-fails on `mount_kentang_services` because the kentang registry lists engines like `kinwangji`
  that the skill doesn't vendor).

### v2.5.0 推运 (7) + 卜卦/择日 — JS-vendor vs Python-port decision tree

星阙 v2.5.0 added 7 推运 (jaynesprog / vedicprog / planetaryarc / planetaryages / balbillus /
yearsystem129 / persiandirected) plus the **horary (卜卦)** and **election (择日)** divination engines.
The integration rule that emerged:

- **Backend-computed (has a `/predict/*` or `/astroextra/*` endpoint) → Python.** jaynesprog
  (`/astroextra/jaynesprog`), vedicprog (`/astroextra/progressions` zodiacal=1), planetaryarc
  (`/predict/planetaryarc`) — `_call_remote` + a Python snapshot builder. Add the endpoint to
  `_PYTHON_CHART_ENDPOINTS`. **These 3 endpoints did NOT exist in the v2.4.0 `vendor/runtime-source`** —
  they need the v2.5.0 re-sync (`sync_vendored_runtime_sources.sh`) before the bundled runtime can serve
  them; the LIVE 星阙 app (:8899) already has them, which is why the live `@requires_chart` tests pass
  pre-rebuild.
- **Frontend, reads pre-computed chart data → Python.** planetaryages (reads `chart.objects` +
  `params.birth`), yearsystem129 (reads `predictives.yearsystem129`, which `/chart` only emits when cast
  with `predictive` truthy — `getPredictivesObj`), persiandirected (pure 1°/年 arithmetic off
  `chart.objects`/`houses`/`birth`). Ported to Python reusing `_astro_msg` / `_aspect_label` /
  `_split_degree`.
- **Frontend, algorithm-heavy / risky to re-derive → vendor the JS verbatim.** balbillus (247-line
  129年旺距削减 with recursive sub-periods). Vendored `astrostudyui/src/utils/balbillus.js` →
  `horosa-core-js/src/vendor/astroextra/balbillus.js`, redirecting its `AstroConst`/`AstroText` imports to
  a tiny **`progConst.js` stub** (7 classical planet ids + `LIST_SIGNS` + `AstroTxtMsg` — avoids vendoring
  the 1128-line AstroConst). Needs `moment` (added to `horosa-core-js/package.json`). Dispatched through a
  new **`progextra` JS tool** (`technique` → builder map) called from `_run_progextra_js_tool`.
- **卜卦/择日 = vendor the whole `divination/` tree.** It's ~3200 lines of **pure logic with only relative
  imports** (no React/antd). Copy the entire `astrostudyui/src/divination/` into
  `horosa-core-js/src/vendor/divination/` (this also re-syncs the v0.8.0 lifespan subset to upstream), then
  **add `.js` to every relative import** (Node ESM needs explicit extensions; a one-shot regex over
  `from '…'` does it — 22 files). Two thin JS tools `horary.js` / `election.js` call
  `runHorary(chartResp, category)`+`buildHorarySnapshot` / `runElection(chartResp, topicId)`+
  `buildElectionSnapshot`. Python `_run_horary_tool` / `_run_election_tool` cast a **traditional**
  (`tradition:1`, `predictive:0`) chart at the question/candidate moment, pass the `/chart` response as
  `payload.chart`, and read back the JS-resolved `category`/`topicId` (the engine falls back unknown →
  `general`/`marriage`).

Gotchas that bit us here:
- **`buildFacts(result)` wants the full `/chart` response** (it reads `result.chart.objects`, `result.objectMap`,
  `result.aspects`, …), so pass the whole response object as `chart`, not just `chart.objects`.
- **election preset has dead/conditional sections.** 星阙's `aiExport.js` election preset lists `应期`
  (its builder **never** emits it) and `用事专属` (only when the topic rule-pack produced items). We mirror the
  preset for fidelity, but `_assert_clean_export` (which requires `missing_selected_sections == []`) is too
  strict for election — assert `missing ⊆ {用事专属, 应期}` instead. horary's 9 sections are all reliably
  emitted (描述 is technically conditional but present for normal charts), so horary keeps strict clean-export.
- **Router: 卜卦 also contains the generic 卦.** The 梅花易数/卦 branch (`["梅易","卦","gua"]`) must exclude
  horary phrasing (`卜卦/horary/起卦/占问`) or `卜卦问婚姻` mis-routes to `gua_desc`.
- **Offline test fakes must cover the new JS tools.** `FakeJsClient.run` needs `progextra` (balbillus snapshot),
  `horary`, `election` handlers, and `FakeClient` `/chart` needs `predictives.yearsystem129`, or the offline
  export-contract suite falls back to `generated_template` and fails.

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
- **`lunar-javascript` must be bundled for 数算.** `canping`/`heluo` compute pillars in-process via
  `horosa-core-js/src/vendor/bazi/` → the `lunar-javascript` npm package. Both builders
  (`package_runtime_payload.sh` + `build_runtime_release_windows.py`) now run `npm install --omit=dev`
  in `horosa-core-js` before copying it (the core-js copy has **no** `node_modules` rsync/ignore
  exclusion, so `node_modules/lunar-javascript` rides along). `verify_runtime_release.py` requires
  `horosa-core-js/node_modules/lunar-javascript/package.json` in both archives. Without it, canping/heluo
  throw `Cannot find package 'lunar-javascript'` at runtime — the rest of the runtime still boots, so this
  fails silently unless the verifier catches it.
- **CI/test must `npm install` `lunar-javascript` before `pytest` (it does now).** `node_modules` is
  gitignored, and the `canping`/`heluo` tests in `tests/test_local_js_tools.py` are **not**
  `@requires_runtime`-gated, so they run in CI and shell out to bundled Node → the vendored bazi chain →
  `import 'lunar-javascript'`. Before v0.7.0, `horosa-core-js` had **zero** npm deps so CI never needed
  `npm install`; v0.7.0 added the first one and turned CI red (3 `ERR_MODULE_NOT_FOUND` failures) while
  the local `186 green` hid it (dev tree already had `node_modules`). Both `ci.yml` jobs and `release.yml`
  now run `actions/setup-node@v4` + `npm ci --omit=dev` in `horosa-core-js`. **Lesson:** whenever you add
  a JS test that isn't `@requires_runtime`, confirm CI installs whatever that test's `node` needs.
- **`with { type: 'json' }` raises the Node floor for ALL JS tools.** The vendored 数算 JSON
  (`canpingTiaowen.json` / `heluoTiaowen.json`) is imported with the import-attribute syntax
  (`import X from './x.json' with { type: 'json' }`), which requires **Node ≥ 20.10**. Because
  `src/tools/index.js` imports `canping.js`/`heluo.js` at the top, an older Node fails to load the whole
  module graph with a *syntax* error — i.e. qimen/taiyi/jinkou/tongshefa break too, not just 数算. The
  bundled runtime ships Node 22 (safe) and `package.json` declares `engines.node >=20.10.0`; the risk is
  only a dev/PATH `node` that's too old. Don't downgrade the bundled Node below 20.10, and if you add
  another raw-`node` JSON import keep using the `with { type: 'json' }` attribute (not the deprecated
  `assert { type: 'json' }`).
- **Windows `PYTHONPATH` must include `Horosa-Web/vendor`.** `start_horosa_local.ps1` puts the vendor
  root on `PYTHONPATH` so `import kinqimen/kintaiyi/kinjinkou` resolve. `package_runtime_payload.sh` and
  `build_runtime_release_windows.py` both bundle `Horosa-Web/vendor/{kinqimen,kintaiyi,kinjinkou}`.
- **Graceful kentang mount.** The packaging scripts patch the *staged* `kentang/registry.py` mount to
  skip engines that aren't bundled, so the chart service still boots offline (`_load_service` does a bare
  `__import__` and would otherwise hard-fail on a missing engine).
- **`verify_runtime_release.py` checks real files inside required dirs.** A directory requirement
  (`swefiles/`, `astropy/`, `vendor/kin*/`) passes only if the archive holds a real file strictly
  inside it — an empty dir-marker entry fails (a bare `…/swefiles/` in a hand-built zip used to pass).
  When hand-zipping the Windows payload, make sure those dirs are actually populated, not just present.
- **The Windows builder must not shell out to `rsync`.** `build_runtime_release_windows.py`'s
  `rsync_copy()` used to invoke the `rsync` binary for its in-payload copies — which does not exist on
  Windows, so the *Windows* builder died on its very first copy (`FileNotFoundError: [WinError 2]`) and
  could only ever run on a machine that happened to have rsync. It now uses a portable
  `shutil.copytree(src, dst/src.name, ignore=ignore_patterns(*excludes), dirs_exist_ok=True)` — same
  "copy SRC into DST" semantics, same exclude set, merging into existing trees — so the single builder
  runs natively on Windows as well as macOS/Linux. Keep runtime-build copies dependency-free this way;
  do not reintroduce a POSIX-only binary (`rsync`, `cp`, `tar`…) into a path that must also run on
  Windows. (`download()` already uses `curl`, which Windows 10/11 ship natively.)
- **Release version bumps must cover *every* release-version-bearing file.** A pyproject-only bump leaves
  `src/horosa_skill/__init__.py.__version__` (CLI `--version`), `server.json` (the MCP-registry-declared
  version, ×2), `CITATION.cff`, and the "current version" references in `README.md` / `README_EN.md` stale.
  When releasing vX.Y.Z bump **all five** in the same commit; `git grep -n "<OLD>"` after the bump should
  show only legitimate historical references (CHANGELOG history, this gotcha line, the Windows-release
  handoff doc). `docs/DATA_CONTRACTS.md`'s `tool envelope: <ver>` tracks an independent envelope-schema
  version — do **not** bump it just because it shares a number with the package.

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
- For users, **re-install the matching runtime release** — both runtime builders copy the repo's
  (ken-fed) `horosa-core-js` into the payload, so a fresh install carries the formatter.

## Headless engine alignment (tongshefa / decennials)

These two techniques are the skill's own headless reimplementations (no ken backend). Keep them
value-identical to 星阙:

- **`tongshefa.js`**: a hexagram's element comes from its **京房本宫 palace** (`HEXAGRAM_PALACE_ELEM`,
  mirrored from 星阙 `GuaConst.js Gua64[i].house.elem`), NOT the upper trigram — they differ for 32/64
  hexagrams. Use `hexElem(hex)` for `left_elem`/`right_elem`/`main_relation`. The aiExport contract is
  **本卦/六爻/潜藏/亲和 only** (matches 星阙 `aiExport.js`); 星阙's najia/六合/升降 UI detail is deliberately
  out of scope — do not add it to the export.
- **`engine/decennials.py`** is a port of 星阙 `utils/decennials.js`. JS uses `Math.round` (half-up) and
  `Math.ceil`; Python's `round` is banker's rounding. Use `_js_round` (= `floor(x+0.5)`) for every JS
  `Math.round`, and `math.ceil` for the L1 count. Cross-check against 星阙's `decennials.test.js` golden
  vectors (`tests/test_decennials.py`) whenever you touch the period math.

## Day boundary + late-zi-hour — two independent global switches (upstream v2.2.1+)

> **⏳ STATUS as of v0.8.0: PARTIALLY landed — runtime YES, skill-side wiring still PENDING.** As of the
> v2.4.0 re-vendor, the bundled ken engine **does** carry the v2.2.1 lateZi code (`vendor/runtime-source`
> kintaiyi now has the `_get_after23`/`_get_hour_gan_next` markers). But the **skill still does not forward
> `lateZiHourUseNextDay`** (grep confirms 0 occurrences in `src/`), so the flag is **accepted-but-ignored**:
> the default `(after23=1, lateZi=1)` is correct, but a non-default `hour==23` request won't take effect
> until the skill threads the flag through every chart-flow payload + schema. **Remaining v2.2.1 round:**
> thread `lateZiHourUseNextDay` through the payloads/schema (the runtime already supports it) — no re-sync
> needed. Until then, treat the non-default rows of the matrix below as the target spec, not live behavior.

This is **upstream 星阙 context** that the skill must mirror, not skill-local invariants. Stick to the
self-check fixture below in tests/fakes; if a real backend call returns four pillars that disagree, the
runtime is pre-v2.2.1 (re-install) — do **not** patch the skill to mask the discrepancy.

Two independent flags control `hour ∈ [23:00, 24:00)`:

| Field | Default | Effect |
|---|---|---|
| `after23NewDay` (`1`/`0`) | `1` | `1` advances day pillar at 23:00; `0` keeps day pillar until 24:00. |
| `lateZiHourUseNextDay` (`1`/`0`) | `1` | `1` starts hour stem from next-day day stem; `0` starts from today's day stem. |

Outside `hour == 23` both flags are no-ops.

**Self-check matrix — `2026-05-27 23:30:00`, direct-time mode:**

```
┌────────────────┬──────────────┬──────────────────────┐
│                │ lateZi = 1   │ lateZi = 0           │
├────────────────┼──────────────┼──────────────────────┤
│ after23 = 1    │ 壬寅 庚子    │ 壬寅 庚子 (equiv.)   │
│ after23 = 0    │ 辛丑 庚子    │ 辛丑 戊子 ← only 新  │
└────────────────┴──────────────┴──────────────────────┘
```

**Skill payloads must forward both flags verbatim.** Any chart-flow tool that builds Chinese pillars
(`bazi_*`, `ziwei_*`, `liureng_*`, `qimen`, `taiyi`, `jinkou`, `sanshiunited`, `canping`, `heluo`,
`nongli_time`, `jieqi_year`, `chart` for Bazi-aware paths) must thread both `after23NewDay` and
`lateZiHourUseNextDay` from the user payload down to the engine call. Java `:9999` reads them through
`ChartController.getParams()`'s **whitelist** — silent dropping there was the v2.2.1 root-cause bug
upstream; if you ever add a new chart-flow payload field, audit every `getParams()`-style controller
the same way. The Python chart service (`:8899`) reads them on every chart-creating endpoint.

**The export snapshot carries the active rule.** `aiExport.js` injects a leading
`排盘规则: 日柱开关【…】+ 时柱开关【…】。本盘四柱按此规则计算。` line. Tool formatters MUST preserve this
line; reports and AI answers MUST quote it back so the consultant can verify which convention the chart
was built under. Stripping it produces silently-wrong analyses when the user has flipped either switch.

**Upstream root-cause references** (for maintainers debugging a value mismatch — the skill itself
shouldn't replicate these fixes, but knowing they exist saves hours):

1. **`ChartController.getParams()` is a whitelist** — fields not explicitly `params.put(...)` are dropped
   silently, defaults take over. Audit ALL `getParams()`-style controllers when adding a chart-flow
   field upstream.
2. **`mvn package` ≠ live process update** — replacing `runtime/mac/bundle/astrostudyboot.jar` doesn't
   reload the JVM; `lsof -ti :9999` + `ps -p <PID> -o lstart=` to confirm the process started AFTER the
   jar mtime, or kill + `start_horosa_local.sh` cycle.
3. **`lunar-javascript` hardcodes `timeGanIndex = (dayGanIndexExact … )`** — `setSect()` shifts only the
   day pillar, never the hour pillar. To honor `lateZiHourUseNextDay = 0`, the frontend must compute the
   hour stem itself using `getDayGanIndexExact2()` (today, no shift).
4. **Triple cache (JVM mem + Redis + `.horosa-cache/paramhash/`)** — new key fields auto-miss, but type
   changes can hit stale entries; clear `redis-cli KEYS "*chart*"` + `.horosa-cache/` when debugging.
5. **Client-side `chartMem` cache (`services/astro.js`)** keys by `JSON.stringify(values)`; new fields
   auto-miss, but `requestOptions.cache = false` forces refresh.
6. **AI snapshots must carry the rule line** — see above; otherwise downstream models default-assume
   `1/1` and explain pillars that don't match the chart.

Authoritative upstream doc: `Horosa-Web/docs/global-day-boundary-v2.2.1.md` (in the 星阙 working tree,
not this repo). When this section drifts from upstream, treat upstream as truth and sync — do not edit
upstream from inside the skill repo.

### Bonus upstream trap (v2.2.1) — AI-analysis SSE Issue #8

The skill talks to its own ken backend, not 星阙's `chat/stream` SSE proxy, so this does NOT affect
skill compute paths. It's documented here because if a user ever debugs 星阙 desktop and asks "why did
my Ollama chat just go silent and then die", the answer is upstream:

- **Catch block in `AIAnalysisProxyService.chatStream` used to swallow the first-cause exception**:
  `sendEvent` inside catch rethrew `ClientAbortException` as `RuntimeException`, killing the
  `ai-analysis-chat-stream` thread, and the original Ollama error went only into a
  `safeErrorMessage(...)` SSE frame that never reached the client. Upstream fix: `QueueLog.error(...)`
  first, then nested try around `sendEvent` + `completeWithError`.
- **The three `stream***` methods used to send zero bytes until the first delta**: with a local Ollama
  TTFT of 10–60 s, browsers/Chromium/middleware time the SSE socket out as idle. Upstream fix: each
  stream method is now wrapped in `withHeartbeat`, which emits `: keep-alive` every 15 s.

If a skill user reports flaky 星阙 AI streaming, point them at upstream v2.2.1 and the
`release_preflight.sh` sentinel `[7]` that gates both lines (`QueueLog.error(AppLoggers.ErrorLogger` and
`keep-alive`) in `AIAnalysisProxyService.java`.

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
- **`js_client` keeps the transport contract.** Every Node failure becomes a `ToolTransportError`:
  a missing/unstartable Node → `js_engine.node_unavailable`, a timeout → `js_engine.timeout`. The
  `subprocess.run` call is wrapped — don't let a raw `OSError`/`TimeoutExpired` escape. On the JS side,
  `bin/cli.mjs` always prints a JSON `{ok:...}` envelope to stdout (never a bare stack trace) and
  coerces a `null`/scalar parsed payload to `{}` so tools don't null-deref on `payload.field`.
- **Tracing is best-effort.** `TraceRecorder._write_event` swallows local-write failures (like
  `_emit_otlp`); a trace write must never crash or mask the traced operation.
- **`evaluation_lock` self-heals.** `acquire_evaluation_lock` reclaims a stale lock (dead PID on POSIX,
  or age threshold when liveness is unknown) but never reclaims a *live* owner. A crashed run must not
  deadlock future evaluations; a long live run must not be stolen from. **Never call `os.kill(pid, 0)`
  on Windows** to probe liveness — on Windows `os.kill` maps to `TerminateProcess`, so it would *kill*
  the lock owner. `_pid_liveness` returns `unknown` on Windows (→ age-based reclaim); keep it that way.
- **Report rendering is atomic.** `render_report` renders to a temp sibling then `os.replace()`s — never
  write a report format directly to its final `output_path` (a mid-render failure would corrupt it).

## 西占(占星)新功能 — AI导出 / AI分析 / 命盘事盘储存 必查 (upstream 星阙)

新增占星功能（判读/预测/辅盘盘）默认只渲染成 tab，**不会**自动接入 AI导出 / AI分析 / 命盘事盘储存——漏接 = 用户眼里「不全面/不稳定」。全链路接入点 + 缺口 + 已修/待修详见 `Horosa-Web/docs/西占新功能-AI导出与储存接入清单.md`。要点：

- **判读类**(寿命/12分度/主宰链…) → 写 `utils/astroAiSnapshot.js` 的 section builder + `utils/aiExport.js` 段名并升 `AI_EXPORT_SETTINGS_VERSION`，才进 AI导出。
- **预测类**(界推运/Huber…) → 仿 `AstroDirectMain.buildPrimaryDirectSnapshotText` 写 `buildXxxSnapshotText` + 在 `utils/aiAnalysisContext.regenerateChartTechniqueSnapshot` switch 加 case。
- **希腊点/阿拉伯点** → 只要进 `AstroConst.LOTS` 就**自动**进 AI导出「希腊点」段(`buildLotsSection`)。
- **新 chart-calc 参数(如 orbs/容许度)** → 四点存/取，否则**存盘后丢**：`models/user.js` 命盘 fields 定义 + 存档复制(~498，镜像 after23NewDay)、`utils/localcharts.js buildLocalChartRecord`、`models/astro.js` 重建 fields(~566)。**铁律：勿连带改坏 pdMethod/主限法。**
- **DivinationChartShell 事盘** → `utils/localcases.js CASE_TYPE_OPTIONS` 注册 module；技法 `state.extra` 现已**通用存取**(`divinationCaseSave` 写 `payload.extra` + `applyRestoreIfAny` 读 `c.payload.extra`)，新 module 不必再逐个改 extra 逻辑。
- **陷阱**：predictHook 的 hook prop 只管 UI 实时刷新；**AI 分析不遍历 hook、走专用 builder**——别以为传了 hook prop 就接入了 AI。
- 本轮已修：世俗盘(mundane) 事盘注册 + 通用 extra 存取。待修(已在清单文档逐点写明，加性低回归、单独谨慎做)：orbs 随命盘存档、各新分析的 AI导出 builder。
