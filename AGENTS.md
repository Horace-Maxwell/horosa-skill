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

### 神数 family (14) — ALL SHIPPED (v0.9.1)

The kentang registry (`astropy/websrv/kentang/registry.py`) mounts **14 神数 engines on the chart
service (:8899)**: wangji / wuzhao / taixuan / jingjue / shenyishu (5 standalone engines) + shaozi /
tieban / fendjing / beiji / nanji / chunzi / xianqin / cetian / qizhengkin (9 sharing the **`kinastro`**
engine). Both groups are now integrated — the wiring is identical (backend `snapshot` → export), the
only difference is which engine dir is vendored:

- **Tier 1 — 5 standalone engines: SHIPPED.** `vendor/{kinwangji,kinwuzhao,taixuanshifa,jingjue,shenyishu}`
  (~5.2 MB total). Each `web{key}srv.py` builds a `response["snapshot"]` whose `[小节]` headers already
  match 星阙's `aiExport.js` preset, so the skill needs **no snapshot builder** — just POST `/{key}/pan`
  and export `response.snapshot`. Wiring: one shared `_run_shenshu_tool(payload, key)` + `_split_birth_ymdhm`
  (神数 take split year/month/day/hour/minute, not date/time strings) + a `ShenShuInput` (FlexibleModel:
  date + optional time + 晚子时 switches + an `options` passthrough for engine-specific overrides like
  wuzhao mode/number). **CRITICAL routing gotcha:** kentang mounts only reach :8899 if the endpoint is in
  `_PYTHON_CHART_ENDPOINTS` — otherwise `_call_remote` sends them to the Java :9999 server and they 500.
  Add `/wangji/pan` … `/shenyishu/pan` there (alongside `/qimen/pan`).
- **Tier 2 — 9 kinastro-* engines: SHIPPED (v0.9.1).** All 9 share the `kinastro` engine
  (`from astro.{shaozi,fendjing,chunzi,cetian_ziwei,…} import …`). Same shared `_run_shenshu_tool`;
  cetian/qizhengkin/xianqin also forward `gender` + place. **The v0.9.0 "deferred" call was WRONG:** the
  live :8899 returned `basic`-only data only because the user's *running* app was an older build — the
  current source's `web{key}srv.py` all set `pan["snapshot"] = build_snapshot(pan)`, and the engine
  imports + computes cleanly under the bundled Python. Vendor the **engine only**: `vendor/kinastro`
  with `--exclude=tools` (the 26 MB `tools/cities` geocoding DB is not needed for ganzhi 神数) +
  `--exclude={ui,frontend,docs,wiki,examples,tests,styles,scripts,.streamlit,…}` → ~31 MB (`astro/` is
  32 MB raw). `ensure_kinastro_path()` puts `vendor/kinastro` on `sys.path` so `import astro.shaozi`
  resolves; `streamlit` is a kinastro import but it's already in the bundled site-packages (the
  `@cache_data`-without-runtime warning is harmless). **Validate offline by invoking each
  `web{key}srv` class's `pan()` with a mocked `cherrypy.request` from a NEUTRAL CWD** (NOT `cd $HW`, or
  the local `Horosa-Web/astropy/__init__.py` shadows PyPI astropy → `No module named astropy.units`).
- **The 9 kinastro-* have NO live `@requires_chart` test** — the user's running app is an older build
  without their snapshots, so a live test would red. They're covered by the offline FakeClient contract
  suite (the fake synthesizes a preset-covering snapshot) + the in-process srv validation.
- **Some kinastro presets have conditional sections** (tieban/chunzi/cetian emit fewer than the full
  `aiExport.js` preset for a given input). The FakeClient emits the FULL preset so the offline contract
  is clean; real exports may show a few `missing_selected_sections` — that's expected (like election).
- **NATIVELY CONFIRMED on Windows (v0.9.1 release build).** Booting the bundled `win32-x64` chart service
  and POSTing to each `/{key}/pan`, **all 14 神数 returned `ResultCode 0` with a real `Result.snapshot`** —
  the 5 standalone (`source` `kinwangji`/`kinwuzhao`/`taixuanshifa`/`jingjue`/`shenyishu`) and all 9
  kinastro-* (`source: kinastro`, snapshots 540–6000 chars). So the engine-only kinastro trim (above)
  is sufficient and the "deferred" worry is fully retired on Windows too — not just structurally.
- **Native-probe gotcha: the snapshot is nested at `Result.snapshot`, not top-level.** The raw chart-service
  response is `{ResultCode, Result:{source, engine, snapshot, raw, …}}` (the skill's `_call_remote` unwraps
  `Result` for `_run_shenshu_tool`, which then reads `response["snapshot"]`). If you probe `/{key}/pan` with
  raw HTTP and read a top-level `snapshot`/`engine`, you'll wrongly see "empty" and think the engine failed.
  Read `Result.snapshot` / `Result.source`.

### v0.9.2 hardening lessons (audit pass — tests/robustness/fidelity/runtime)

- **`f"{response.get('snapshot')}"` produces the literal string `"None"` when the key is absent** (a truthy
  6-char string → a garbage "None" export that silently passed). Always guard `raw = response.get("snapshot")`
  then `f"{raw}".strip() if raw else ""`. This bit `_run_shenshu_tool`; the same `f"{...or ''}"` idiom is safe
  only because of the explicit `or ''`.
- **Don't silently fall back in compute runners.** `_split_birth_ymdhm` used to substitute `2025-01-01` on an
  unparseable date (wrong-moment chart, no error). Now it raises `tool.shenshu_bad_date`; `_run_shenshu_tool`
  raises `transport.shenshu_snapshot_unavailable` on a no-snapshot (old-backend) response; horary/election/
  progextra log + attach `snapshot_error` instead of a bare `except: pass`.
- **persiandirected dates differ from 星阙 by ≤1 day** (~40% of rows). Root cause: 星阙's moment
  `add(N,'days')` TRUNCATES the fractional day (JS `Date.setDate` floors), AND `arc % 360` has JS↔Python
  float noise that rounds to the same 2-dp age but flips a day at the integer boundary. Matching the truncation
  made it worse (float noise dominates). The ages/aspects/targets are byte-identical; the ≤1-day 应期 date is
  astrologically negligible and documented (`docs/v091-fidelity-spotcheck.md`). To verify a hand-port's
  fidelity, extract the 星阙 builder's pure functions + run them on the same fixture and diff — but mind
  `moment` (CJS, `createRequire`) and the React-class lines.
- **Runtime-slim reality: `pyarrow`(119M)/`pandas`(40M) are astropy deps, NOT streamlit-only.** kintaiyi needs
  `import astropy.units` → astropy needs pyarrow+pandas. Stripping them breaks taiyi. streamlit is imported
  pervasively across `kinastro/astro/*` (st.markdown ×1817 …) so it can't be stripped without a fragile stub.
  **Only `plotly`(40M) is safely strippable** (streamlit-only + lazily imported for `st.plotly_chart`, never hit
  headless). Verified `import streamlit` + cetian snapshot + `astropy.units` all OK without it.
- **Export presets are a SUPERSET; some sections are 星阙-UI-only or conditional.** `AI_EXPORT_OPTIONAL_SECTIONS`
  (registry) lists sections a preset names but the headless snapshot may not emit (检索/查询 panels, mode/topic
  conditional). The parser excludes them from `missing_selected_sections` so real exports read clean; strict
  techniques keep an empty optional set. Also: a preset copied from `aiExport.js` can MISS sections the backend
  actually emits (qizhengkin 今制宿度/古制宿度) → they surface as `unknown_detected_sections`; add them to the preset.

### v0.12.0 sync lessons (主限法 v12 核5收敛 + 排盘修正批 + faRelatedPeople — vendor 源 = Horosa-Public)

- **vendor 源 = 开源仓 Horosa-Public**（`HOROSA_SOURCE_ROOT=/Users/horacedong/Desktop/Horosa-Public`；
  sync 脚本默认根是 Desktop、其下无 Horosa-Web，必须显式传）。Public 的 PD 引擎天然就是核5+legacy 白名单
  （perchart 白名单 ↔ `_PD_METHOD_REGISTRY` 6 键锁步），v12 核 kernel 完整（Vertex/多圈/每盘钥匙/显示窗）。
  同步后核法：vendored astropy 与 Horosa-Public 逐文件 `diff -q` 全同 + `PD_SYNC_REV==pd_method_sync_v12`
  + golden v266 在位。**同步与核对一律以 Horosa-Public 为唯一来源。**
- **`/predict/pd` 的 params 回显是原样输入，不是引擎解析值**：送 `placidus` 回显仍 `placidus`，但引擎内已
  回退 core_alchabitius（行集与显式 core 逐位一致，live 测试钉死）。skill 快照对白名单外键如实标注
  「未核验，引擎回退 Alcabitius 半弧法」，不静默换标签。
- **live 验证必须打 skill 自己 vendored 的引擎实例，不是 :8899/:9999 上恰好在跑的东西**——默认端口上
  常驻的服务不保证与 vendored 引擎同版本（陈旧实例会掩盖白名单/钥匙问题）。本轮把 tests 的
  gate+`make_service` 从写死 `:8899/:9999` 改为尊重 `HOROSA_CHART_SERVER_ROOT`/`HOROSA_SERVER_ROOT`
  （此前 env 覆盖静默无效，一次「带覆盖的全绿」实际测的是默认端口上的旧实例）。
  起 vendored 实例：chart 要 `PYTHONPATH=<vendor>/Horosa-Web/astropy`
  + `HOROSA_CHART_PORT`（脚本只自动解析 flatlib，不解析自身包根）；java 用 vendored
  `runtime/mac/java/bin/java -jar runtime/mac/bundle/astrostudyboot.jar --server.port=… --astrosrv=…`
  （root 500 = 正常无路由）。
- **防陈旧进程门已制度化为 live 测试**：chart 心跳 `GET /` 回显 `pdSyncRev`，断言 ==`pd_method_sync_v12`
  再信任结果（v12 注记坑#6：陈旧引擎把未知时间钥匙静默按 Ptolemy 算）。**钥匙分叉探针别用 Kündig**（静态
  标度 1.0 与 Ptolemy 同日期）——用每盘真算的 Kepler（live：321/321 行日期分叉）。
- **pd 表行是列表不是字典**：`[arc, prom, sig, type, date]`；3000 年多圈 = 同 (prom,sig) 弧 +360°×n
  （live 实测 168 组复发对，max arc 2995.5°）。宿命点行 id `N_Vertex_0` 仅 In-Zodiaco；skill 侧
  `ASTRO_TEXT_MAP["Vertex"]="宿命点"`（主短两表都要）。
- **faRelatedPeople 透传**：vendored `computeProtect` 吃 `pan.faRelatedPeople=[{name, yearGan}]`（显式数组
  为准，缺省不出行）。skill 在 Python 侧把 `{name, birth}` 经 `/nongli/time` 的 `yearJieqi`（立春界）归一化
  为年干（1991-02-03 → 庚，立春前归前一年，live 钉死），JS 保持上游 verbatim 只 stamp。上游的
  `birthToYearGan` 依赖 lunar-javascript，skill 不引这个依赖——走自家 nongli 后端同口径。
- **排盘修正批随重同步自动带入**（日返/月返种子、合盘/组合盘归一化、恒星跨0°、围攻 orb、均时差等，上游
  pytest 60 + golden byte-perfect 已验）；skill 结构断言型测试全绿，无需改动。
- 界 (term) promissor row id = `T_<ruler>_<sign-name>`（非经度）；上游 dial 的 `_PD_CHART_METHOD_HSYS`
  只在 skill 暴露 dial 时才相关（目前只暴露 PD 表）。

### v0.11.0 sync lessons (Xingque v2.6.3→v2.6.5 parity + 2 v0.10.0 deferrals — no new tools, still 68)

- **Sidereal ayanāṃśa is pure Python passthrough.** `perchart.py` reads `data.get('siderealAyanamsa')` and emits
  `chart.siderealAyanamsa` + `chart.nakshatras` (sidereal only). `BirthInput` has `extra="allow"` so the param already
  flows via `model_dump(exclude_none=True)`; declaring it is for discoverability + guidance only. **Real bug fixed:** the
  skill's `ASTRO_MSG["Sidereal"]` was hardcoded `恒星黄道，岁差:Lahiri` → mislabelled Raman/Fagan charts; de-hardcode it,
  read the ayanāṃśa from `chart.siderealAyanamsa` (西占) / `chart.siderealModeKey`+`ayanamsaValue` (印占, **different field
  names**), and put the real name on its own line. `chart.zodiacal` is a *localized string* ("恒星黄道"), not an int — don't
  gate on `== 1`. Nakshatras read from `response.chart.nakshatras`, NOT top-level.
- **India is Python (`/india/chart` in `_PYTHON_CHART_ENDPOINTS`), reads `indiaHsys`/`indiaAyanamsa`** (aliases hsys/ayanamsa/
  siderealMode). Golden = ayanāṃśa *differences* are stable astronomical constants (Raman−Lahiri Sun lon = +1.446°,
  Lahiri−Fagan = +0.88°) — robust without pinning fragile absolute lon.
- **JS vendor dependency-closure is the whole game (六壬毕法 D + 政余格局 E).** Both are pure module-level closures
  (zero `this.`/React) — extract by transitive-call analysis, but **CONST refs are caught separately from function refs**
  (missing `JiaZiList`/`ERFAN_SU_TO_BRANCH` → silent `ReferenceError` swallowed by try/catch → null result). The 六壬 三传
  engine is a plain `ChuangChart` class — vendor it with draw-only imports (GraphHelper/helper/LRShenJiangDoc) replaced by
  no-op stubs (only `genCuangs` runs). `SZConst.js` reads `localStorage` at *module load* → **hardcode a no-op shim** (node
  25's experimental global `localStorage` throws without `--localstorage-file`; don't probe `globalThis.localStorage`).
  `AstroText.js` keys its maps on `AstroConst.*` constants → extend the `constants/AstroConst.js` shim with every planet/
  node/point the closure looks up, or the lookups return `undefined`-keyed.
- **政余格局 honest limitation:** 七政神煞 (官/福/疾/天贵/玉贵/岁驾) come from a *separate* kinastro qizheng engine
  (`fetchKinastroQizheng`) the western-`/chart` guolao path never calls → `guolaoGods` absent → god-dependent patterns
  can't fire (chart-object ones do). The 神煞 section was already empty for the same reason. `能接多少接多少、跑不通如实标出`.
- **紫微 P0–P2 data is all in the jar response** (re-synced): top-level `patterns` (命中格局: name/category/duanyi/broken),
  `houses[].starsOthersGood/Bad/Small` (杂曜), `direction`/`smallDirection` (大限/小限). Just surface it in
  `_build_ziwei_snapshot_text`. 来因宫 + rich 流曜运限 are frontend-only (ZiWeiHelper) → not in the response, honestly skipped.
- **Offline contract (`test_all_callable_techniques...`) forbids bare `无` sections.** Any new JS-fed or jar-fed section
  needs a `FakeJsClient`/`FakeClient` handler returning real content (guolao_moira; `/ziwei/{birth,rules}` patterns), AND
  the section in both preset + `AI_EXPORT_OPTIONAL_SECTIONS` (conditional → no false `missing`).

### v0.10.0 sync lessons (Xingque v2.5.4/v2.6.x parity — no new tools, still 68)

- **PD full-house params flow through `PerChart`, not the web layer.** `webpredictsrv.py:pd()` is just
  `PerChart(data) → getPredict() → getPrimaryDirection()`; `perchart.py` reads `pdMethod/pdDirect/pdAntiscia/...`
  from the request, `perpredict.py` reads them via `getattr(self.perchart, ...)`. So A only needed schema fields
  + a vendor re-sync (`input_normalized` is `model_dump(exclude_none=True)` → unset params fall back to the
  upstream defaults: direct/converse on, antiscia/terms off). Don't grep the web srv for the param — grep `perchart.py`.
- **JS re-vendor dependency closure is the #1 trap.** The jinkou 解读层 crashed on `LRConst.TaiXuanNum` undefined —
  the curated `vendor/liureng/LRConst.js` (131-line, AstroConst-free) was missing 6 new constants
  (`TaiXuanNum/ZiCong/ZiHai/ZiPo/ZiSangHe/ZiXing`). Do NOT re-vendor the full upstream `LRConst.js` (it `import`s
  `AstroConst` from a path that doesn't exist headless); append only the new pure constants. Always do a
  `node -e "import('...')"` load-check AND a real-data run after vendoring, not just a load-check.
- **qimen 法奇门 = surgical add, not a 2086-line re-vendor.** `DunJiaFaDoc.js` is pure; `DunJiaFaCalc.js` imports
  only `DunJiaFaDoc`. The existing `DunJiaCalc.js` works, so just add `import { buildFaQimenAnalysis }` + the +8-section
  block before its `return`. `buildFaQimenAnalysis(pan)` is compatible with the skill's kinqimen pan (live-verified);
  all 8 法 headers emit when `fa` is truthy. Preset = the builder's actual sections (14: skill has no `九宫与宫内星体`).
- **liureng `毕法/占断向导` — DONE in v0.11.0** (was deferred in v0.10.0): the ~40-field layout context IS assemblable
  headless. `buildLiuRengReferenceContext` + `buildLiuRengLayout`/`buildKeData`/`buildSanChuanData` are pure
  module-level functions (20-fn / ~570-LOC closure, zero `this.`/React) — extracted verbatim into
  `vendor/liureng/liurengRefContext.js`. The 三传 engine is `ChuangChart.genCuangs()` (plain class; vendored with
  the 3 draw-only imports — GraphHelper/helper/LRShenJiangDoc — replaced by no-op stubs since only genCuangs runs).
  Deps: full `LRConst.js` (re-vendored 21→52 exports superset; has GanJiZi/GuiRengs/GanZiWuXing/getGuiZi), `LRPanStyle.js`,
  a 12-LOC `constants/AstroConst.js` shim (LIST_SIGNS + Sun/Moon). Wired in `tools/liureng.js`: `[毕法（已命中）]` always
  (refCtx success), `[占断向导]` only when `payload.zhanCategory` ∈ {hunyin/taichan/jibing/caiyun/…}. Both in the liureng
  preset + `AI_EXPORT_OPTIONAL_SECTIONS["liureng"]` (conditional → no false missing). **坑**: missing a module-level const
  in the closure (JiaZiList/ERFAN_SU_TO_BRANCH) → silent `ReferenceError` caught by try/catch → refCtx null → 毕法 absent;
  and a missing `ChuangChart` import → 三传 null → only non-三传 毕法 fire. Always trace refCtx + sanChuan on a real 盘.
- **guolao `政余格局` — DONE in v0.11.0** (was deferred): `buildLocalMoiraPatterns` (Moira DSL) + its 34-fn/~600-LOC
  pure closure (zero `this.`) extracted verbatim into `vendor/guolao/guolaoMoira.js`; runs via `js_client.run("guolao_moira")`
  in `_run_guolao_chart_tool`, appended as the `[政余格局]` section. Deps chained out: `vendor/suzhan/SZConst.js` (with a
  hardcoded `localStorage` no-op shim — node 25's experimental global localStorage throws without a flag), the real
  `constants/AstroText.js` (name maps) + an extended `constants/AstroConst.js` shim (planets/nodes/points the maps key on),
  and inline `GUOLAO_LIFE_MODE_*` + `getStored*` default stubs (headless has no UI prefs → ASC 命度 / su28=2).
  **Honest limitation** (`能接多少接多少、跑不通如实标出`): the 七政神煞 (官/福/疾/天贵/玉贵/岁驾) come from a *separate*
  kinastro qizheng engine (`fetchKinastroQizheng`), which the skill's western-`/chart`-only guolao path never fetches — so
  `guolaoGods` is absent and the **god-dependent patterns** (八杀朝天/日月拱官/官福失垣/…) can't fire. The **chart-object
  patterns** (孛犯太阳/罗犯太阳/金水相涵/日月失所/命坐两歧/孤月独明) DO fire (golden: 1985-03-21 → 金水相涵 + 孛犯太阳).
  The 神煞 section was already empty for the same reason (pre-existing). Closing it = wiring the qizhengkin gods in (future).
- **Live services make the @requires_* tests run.** When `:8899` (chart/ken) and `:9999` (Java) are up, pytest runs
  the integration tests for real (233 passed, 0 skipped). That validated B/C/A against real Python compute and the
  qimen/jinkou 解读层 against the real ken backend — the best signal available. CI (services down) skips them.

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
  version — do **not** bump it just because it shares a number with the package. (v0.9.1 note: the mac
  side bumped all five correctly this round — `__version__` read `0.9.1` straight away.)
- **`start_horosa_local.ps1`'s 180s readiness gate is too short on a box without Mongo/Redis, but the
  services still come up.** On a clean machine the Java backend retries Mongo/Redis connects on boot and
  takes >180s to answer `/common/time`, so the launcher hits its deadline and `throw`s "Windows Horosa
  runtime did not become ready in time." This is a FALSE failure: `Start-Process` already detached both
  the chart (`:8899`) and Java (`:9999`) processes, they keep coming up, and `horosa-skill doctor` goes
  green (`issues: []`) ~30–60s later. When self-checking after `install`: start the stack, ignore the
  launcher throw, then poll `doctor` (or the two endpoints) for a few minutes rather than trusting the
  launcher's exit code. (Candidate fix: raise the deadline to ~300s, or gate "ready" on the chart service
  alone since that is what the ken/神数 endpoints need.) Verified harmless across the v0.7.0 and v0.9.1
  Windows release builds.
- **The two runtime builders MUST stay in lockstep — every `package_runtime_payload.sh` (mac) step needs
  a parallel `build_runtime_release_windows.py` (Windows) step, and `verify_runtime_release.py` must list
  new required entries for BOTH platforms.** v0.10.0 broke this: the mac packager gained (1) a
  `gen_shaozi_tiaowen.py` call (so 邵子神数 emits real verses) and (2) a plotly strip, and the verifier
  added `…/shaozi/data/shaozi_tiaowen_6144.json` to the **darwin-arm64** list only — but the Windows
  builder and the win32-x64 verifier list were left untouched. A Windows build would then have silently
  shipped placeholder 邵子 verses *and still passed verify*. Fixed by adding both steps to the Windows
  builder and the shaozi entry to the win32-x64 verifier list. **Rule: when you touch one builder or add a
  required artifact, grep the other builder + both `REQUIRED_ENTRIES` lists in the same change.**
- **A new release published as `latest` is repeatedly missing its Windows half — ALWAYS check the release
  manifest first.** The mac side has shipped three `latest` releases incomplete: v0.10.0 had **no**
  `runtime-manifest.json` at all (`releases/latest/download/runtime-manifest.json` 404 → `install` broke on
  BOTH platforms); v0.11.0 had a **darwin-only** manifest + no win32 zip (mac installs, **Windows** install
  finds no `win32-x64` entry / 404s the zip). The Windows runtime is built off-repo on a Windows box, so a
  mac-only release publish leaves it out. **First diagnostic when "check sync" / a new version appears:**
  `gh release view vX.Y.Z --json assets` (expect darwin tar.gz + win32 zip + runtime-manifest.json +
  SHA256SUMS.txt) and `curl -sI https://github.com/Horace-Maxwell/horosa-skill/releases/latest/download/runtime-manifest.json`
  then confirm the manifest JSON has **both** `darwin-arm64` and `win32-x64` platforms. If the win half is
  missing: build it, regenerate the **dual-platform** manifest + SHA256SUMS, and upload — the release is
  usually already `latest`, so the upload alone (no flip) restores Windows `install`.
- **Watch for committed git conflict markers after a mac-side merge.** v0.11.0's release-prep left a stray
  `>>>>>>> <sha>` line in `CHANGELOG.md` on `main`. `git grep -nE '^(<<<<<<<|=======|>>>>>>>)'` after every
  fetch/ff; delete any stray marker (the surrounding content is usually already resolved).
- **邵子神数 `完整条文` placeholder is upstream-faithful, not a bug.** The shaozi engine looks up two verse
  ids; `基础条文` uses an id that IS in the upstream CSV (real verse after generation), but `完整条文` uses
  an id scheme not covered by the 6144-verse CSV, so it falls back to the engine's `【条文待補充】`. macOS
  behaves identically (same CSV → same generated JSON → same missing id). Don't "fix" it by faking verses.
  A coarse `grep 條文待補充` over the snapshot will false-positive on this expected fallback — check that
  `基础条文` is a real verse instead.
- **`gen_shaozi_tiaowen.py` must write LF (`newline="\n"`).** Without it, `Path.write_text` emits CRLF on
  Windows, so the Windows-built `shaozi_tiaowen_6144.json` differs from the macOS-built one purely by line
  endings (same content, +1 byte/line). Inert functionally; the explicit LF keeps the two platform builds
  byte-reproducible. (The shipped v0.10.0 win zip predates this fix and carries CRLF — verified
  content-identical to mac's LF copy, so it is fine; future builds are byte-clean.)

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

## 奇门遁甲 法奇门叠加层 (upstream 星阙；AI导出/导出设置/挂载/命盘事盘储存 四同步已含)

星阙 v-next 给奇门加了荀爽法奇门「断 + 解」层（纯前端 JS，consume kinqimen 的 `pan`，不改 ken 引擎/不重编 jar）：六害完整（补 **庚/白虎** + 危害排序 击刑>入墓>庚>白虎>门迫>空亡）、**逐宫合并化解**（灭象/布阵/解刑墓庚虎迫空；庚击刑→乙巳、庚单独→只乙、庚入墓→冲，本宫优先；卡片只写「怎么做」+ 物象例 + 龙/蛇/虎脚注替代）、用神分论（识破人心/财富七要/事业七要/恋爱姻缘/解孤辰寡宿）、取象/神煞 hover。

- **对 AI 客户端的影响（必知）**：qimen 的 AI 快照（`components/dunjia/DunJiaCalc.js:buildDunJiaSnapshotText`）末尾新增 8 段 `[六害总览][化解方案][八门化气大阵][用神分论][财富七要][事业七要][恋爱姻缘][孤辰寡宿]`。**AI导出 / 导出设置段表（`utils/aiExport.js` `AI_EXPORT_PRESET_SECTIONS.qimen` 同步 +8）/ AI分析挂载（`aiAnalysisContext` 复用同 builder）/ 命盘·事盘储存（快照随 pan 重生成）四处全同步**——都走同一个 builder + 同一段表，新增段必同步「builder + 段表」两处。求测事项（识破人心/财富/事业/婚恋）是 localStorage 偏好、不进 fields，**无网测**（仅荀爽）。
- **口径**：六害化解以荀爽视频 docx 为准（用户给的 md 掺了个人补充，已回退）；**八神显示已归一 `勾→虎 / 雀→玄`（白虎玄武）于 `DunJiaCalc.buildCells`**——盘面/hover/八宫/化解/快照一致。qimen 仍由 ken（`kinqimen`,:8899）算 pan，化解/用神/六害是 **JS 层格式化**，`pan.source=="kinqimen"` 守恒不变。
- **后续批：相关人员(生年干) + 命盘/事盘（纯前端，不影响 ken 引擎/快照段数）**：星阙左栏加「相关人员」多选（从命盘库选人，各人**生年干**＝`birthToYearGan` 按立春算）喂 **八门化气大阵**保护清单——`computeProtect` 删占位「示本盘年干」、改读 `pan.faRelatedPeople`，**未选则不出生年干行**。对 AI 客户端：**快照仍是同 8 段，无新顶层段**；只是 `[八门化气大阵]` 段内容可多出「生年干·姓名」逐人行（折叠进现有段，段表不动）。另加左栏「盘类」选择器：命盘→复用命盘库 `localCharts`（一等人命盘、跨技法可用，**保存恒弹新增星盘抽屉**、信息预填完整、奇门设置存 `payload.qimen`）；事盘→`localCases`（现状）。**四同步挂载加固**：`aiAnalysisContext.js` 的重算路径（`regenerateQimenSnapshot`、亦被三式合一调用）已补 stamp `faRelatedPeople`（兼容事盘 `payload.faRelatedPeople`/命盘 `payload.qimen.faRelatedPeople`）+ `computeProtect` 全局兜底 `window.__horosa_qimen_related_people`，确保 AI 挂载不漏相关人员。
- **再 vendor 星阙 JS 时**（见 §Re-vendoring the JS engines from 星阙）会带入新文件 `components/dunjia/DunJiaFaCalc.js` + `DunJiaFaDoc.js`，并改 `DunJiaMain.js` / `DunJiaCalc.js` / `QimenXiangDoc.js` / `utils/aiExport.js`（及命盘往返的 `models/astro.js` / `models/user.js` / `components/user/ChartAddFormComp.js`，均 guarded 增量、占星零回归）。星阙侧自检：jest `dunjia/__tests__/DunJiaFaCalc.test.js`+`DunJiaCalc.test.js`+`DunJiaFaDoc.test.js`、preflight `[26]`。


## 主限法 v12 批(upstream 星阙 v2.6.6 — ✅ 已于 v0.12.0 同步完成,vendor 源=Horosa-Public)

> 下面 7 条是当时的同步清单,留作历史核对参照;实际执行结论与坑见上方「v0.12.0 sync lessons」节
> (全部逐条核到:核5白名单/22钥匙/Vertex/3000多圈/golden v266/pdSyncRev 心跳门/钥匙分叉 live 测试)。

1. **显示窗口径换了**:行星对显示窗 = 「弧 pre-norm 原值 |Δ| < 107.5」单参数判据(`_passesCoreDisplayWindow`),旧三分支 λ 窗 + EPS 已删。世俗(In-Mundo)核旧窗符号错配修复 → **In-Mundo 行星对行显著增多是修复非回归**,skill 的 golden/selfcheck 若按旧行数断言会假红。
2. **宿命点(Vertex)应星新增**(仅黄道向运;世俗核不出):行 id `N_Vertex_0`,闭式直算。snapshot/导出段如列方向行,新应星会出现。
3. **时间钥匙修真**:Simmonite/Kepler/Brahe 由常数改**每盘真算**(本命太阳日速);新增 `Kündig`(静态 1.0)与 `SymbolicSolarArc`(动态,逐弧查星历)。同步时 `STATIC_TIME_KEY_SCALES` 集合与 `PER_CHART_TIME_KEY_FALLBACK` 一起带。
4. **pdYears 上限 360→3000**:`perchart.py` 夹断 3000;`perpredict._extendCorePdRecurrences` 统一旧「180+ 互补行」与多圈复发(基弧+360m)。≤360 逐位等价旧式;skill 侧若有 pdYears 校验/文档要同步上限。
5. **golden 改名** `golden_alcabitius_ptolemy_v266.ndjson.gz`(v253 删),manifest 同步;`PD_SYNC_REV = pd_method_sync_v12`(helper.py/webchartsrv.py + 前端 + Java 4 控制器——skill 只 vendor Python 也要带 rev,响应 params.pdSyncRev 会回显)。
6. **坑·陈旧 Python 进程静默吞新钥匙**:长驻 webchartsrv 不重启时,新动态钥匙会**静默按 Ptolemy 算日期**(未知 key 不报错走默认 scale)。skill 打包运行时若复用旧进程同坑;验证法 = 直接 POST 对比 Ptolemy vs 新键日期是否分叉。
7. 同步自检建议:vendored 引擎跑 `pdYears=3000` 应出多圈行(同 (prom,sig) 链上 arc+360k、日期逐圈递增);`pdYears=100` 行集与 v2.6.5 vendor 比对 — 仅显示窗/宿命点差异属预期。
