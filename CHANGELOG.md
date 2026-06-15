# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows a release-oriented changelog style.

## [Unreleased]

### Added — Linux (linux-x64) groundwork (🧪 experimental)

- **`scripts/scaffold_linux_runtime.py`** (new): Linux counterpart of `scaffold_windows_runtime.py`.
- **`scripts/build_runtime_release_linux.py`** (new): Build script for Linux runtime archives.
  Downloads Node.js linux-x64 binary, creates a minimal JRE via `jlink`, extracts a pre-compiled
  portable CPython 3.12 from python-build-standalone, and installs chart-service dependencies
  (`swisseph`, `numpy`, `cherrypy`, etc.) via pip. 邵子神数 verse JSON is generated from the
  vendor-supplied CSV during the build. The start script is patched to use `runtime/linux/` paths.
- **`scripts/generate_release_manifest.py`**: Added `--linux-archive` / `--linux-url` CLI options.
- **`scripts/verify_runtime_release.py`**: Added `linux-x64` required entries and `--linux-archive`.
- **`docs`**: Linux entries in `runtime-manifest.example.json` and `OFFLINE_RUNTIME_RELEASES.md`.
- **`docs/OFFLINE_RUNTIME_RELEASES.md`**: Marked Linux as experimental (🧪).

> **Note:** No `linux-x64` runtime asset has been shipped yet. Linux is not advertised in the
> README badge or `server.json` until the first validated asset exists.

## [0.14.0] - 2026-06-14

第四轮 Horosa-Public 对齐：补**古典占星**——`[古典]` + `[古典格局]` 两段进 chart 家族导出（星阙 v2.6.7）。工具数不变（**72**，两段补到既有 chart 工具，非新工具）。vendor 源 = 开源仓 Horosa-Public。

### Added — 古典占星（chart 家族 +2 导出段，72 工具不变）

- **`[古典]`（`buildClassicalSection`）** — `chart` / `chart13` / `hellen_chart` / `india_chart` / `mundane` 导出新增：**逐曜古典状态**（出界 / 相位显隐 phasis / 喜乐 / 同异宗 sect / 度数性质·性别 / 月站 mansion / 远近地点·数增减·光增减 / 单度主星·九分·面主·Darijan）、**上升宿**、**围攻详断** besiegement、**围绕** encirclement、**Melothesia 身体部位**；逐值源自后端 `/chart`（含 `surround.besiegement`）。
- **`[古典格局]`（`buildClassicalAnalysisSection`）** — `chart` / `chart13` / `hellen_chart` 导出新增：护卫 doryphory / 优势相位 overcoming / 度数围攻、传光·聚光 / 不合意 / 交点弯曲、**逐题主星** topic-almuten、**偶然尊贵** accidental dignity、恒星触发 / 行星时 / 埃及历 / 巴比伦参照星、相位格局 / 分布权重 / 气质评估、**Almuten 总主**、吉化·凶化、阿拉伯点(扩展)；逐值源自后端 `/astroextra/analysis`（`analyze_chart`），仅本命三盘挂接，印度 / 世俗仅出 `[古典]`。
- 两段 builder 由上游 `astroAiSnapshot.js` 的 `buildClassicalSection` / `buildClassicalAnalysisSection` **逐值移植为 Python**（skill 自建后端驱动快照，不解析前端 `aiExport.js`）；`/astroextra/analysis` 归入 `_PYTHON_CHART_ENDPOINTS`（与 chart 服务同源、不触 Java 探针）；preset + optional **双列登记**（条件段缺省时 graceful）。
- **测试**：live `test_chart_carries_v267_classical`（chart 富集两段 + 段头/detected/clean）+ 离线 `test_chart_classical_sections_emit_offline`（FakeClient `/astroextra/analysis` 桩逐键核对建造器输出）+ export-fixture catalog `astrochart_classical_live_snapshot`（离线解析契约）；`263 / 263 pass`。

### Fixed — v0.13.0 Windows half (4th recurrence — auto-caught by the new CI guard)

- **v0.13.0 shipped as `latest` with a darwin-only manifest and no win32 zip — Windows install broke
  again (4th consecutive: v0.10.0/v0.11.0/v0.12.0/v0.13.0).** This time **the `release-completeness`
  CI guard added in v0.12.0 fired on the release event and FAILED automatically** — it worked exactly as
  designed, surfacing the gap without a human noticing. Built + natively verified the win32-x64 v0.13.0
  runtime, regenerated the dual-platform `runtime-manifest.json` + `SHA256SUMS.txt`, and uploaded to the
  v0.13.0 release (already `latest`; upload alone restores Windows install). win zip sha256
  `627a5411e120c08b53ce5fec24f25ca8c667a8e641a611c65b53593d4bfc7eeb`.
- **Native Windows verification:** `/qimen|/taiyi|/jinkou/pan` → `ResultCode 0` + right source (and
  **taiyi now carries its v0.13.0 sections** on the bundled runtime); all 14 神数 return a real
  `Result.snapshot` (shaozi 基础条文 a real verse); tongshefa (火地晋 / 实克思) + canping + heluo via the
  bundled node. No build/launcher/verify changes were needed — v0.13.0's +4 tools
  (triplicityrulers/keypoints/lunationphase/extrareturns) are skill-layer code that rides the existing
  runtime, and the v0.12.0 launcher hardening (port guard, java UTF-8, GetFullPath PID-ownership) + shaozi
  gen + plotly strip carried over automatically.

## [0.13.0] - 2026-06-12

第三轮 Horosa-Public 对齐：补 4 个未同步 AI 技法 + 太乙/八字 段欠暴露修复（68 → 72 工具）。vendor 源 = 开源仓 Horosa-Public。

### Added — 4 个未同步 AI-export 技法（68 → 72）

- **三分主星推运 `triplicityrulers`** / **数字相位推运 `keypoints`** / **月相推运 `lunationphase`**：纯前端 chart→text builder，
  从 Horosa-Public `utils/{triplicityRulers,keypoints120,lunationPhase}.js` verbatim vendored 进 `horosa-core-js`，
  经既有 progextra 通路（/chart → builder）出单段快照。依赖闭合：AstroConst shim 补 `SignsProp`（庙旺陷落+三分主星表）。
- **多重回归 `extrareturns`**：土/木/月交三体返照——上游 builder 是「请求型」（逐体拉 `/astroextra/planetreturn`），
  headless JS 不发 HTTP，故 Python 侧逐体调用后按上游同格式拼 `[多重回归]`。
- 每个新技法都有 live 测试（段头 + clean export）+ 离线 export-fixture 契约。

### Changed — 太乙 / 八字 段口径对齐 Horosa-Public

- **太乙**：kintaiyi 后端返回的 `sections`（太乙诸神/风游/主客定算/八门与宿曜/十二神/断法/七大兵法 + 博弈/命法/命宫行限）
  此前被 `tools/taiyi.js` 整体 strip，现透传（preset 3→13；按起局式条件出的段列 optional）；后端 `起盘` 段去重（builder 已出 `[起盘信息]`）。
- **八字**：`大运` 此前并入 `流年行运概略`，现拆为独立段（对齐 Public aiExport bazi 段口径，preset 4→5）；`大运` 列 optional
  （起运/性别缺则不出）。`多运限·指定时段` 后端响应无该数据、skill 无「指定时间窗」输入入口 → 未接入，列 optional 并如实标注（不伪造）。

### Notes — 如实标出 / 未纳入

- **风水/阳宅法 `fengshui` 仍明确排除**：审计核实其为 canvas + 户型图 + 交互点位驱动，无法 headless（无 birth/time 输入），
  与仓内既有「明确排除·风水未完成 headless 化」政策一致。
- **CI live-test job 未新增**：GitHub Linux runner 无 Linux 运行时（运行时 macOS/Windows-only 且 gitignore），无法在 CI 起后端；
  CI 覆盖由 offline FakeClient 契约测试 + export-fixture 契约承担，全套 live 测试在本机 vendored 运行时发布前跑。
- **质量**：export-fixture catalog +4（新技法 offline 解析契约）；`SZConst.js` parseInt 显式 radix 硬化。

### Fixed — v0.12.0 Windows half (3rd recurrence) + recurrence guards + launcher hardening

- **v0.12.0 shipped as `latest` with a darwin-only manifest and no win32 zip — Windows install broke (3rd
  consecutive recurrence after v0.10.0/v0.11.0).** Built + natively verified the win32-x64 v0.12.0 runtime,
  regenerated the dual-platform `runtime-manifest.json` + `SHA256SUMS.txt`, and uploaded all three to the
  v0.12.0 release (already `latest`; upload alone restores Windows install). Native check: `/qimen|/taiyi|
  /jinkou/pan` → `ResultCode 0` + right source; all 14 神数 real `Result.snapshot`; tongshefa/canping/heluo
  OK; win zip sha256 `edabd313203d5eb5463b3da1eebe34f6c23a54b6abc51f3a5760ad93171df8e5`.
- **New CI guard `release-completeness.yml` (stops the recurrence).** On schedule + workflow_dispatch +
  release events it re-inspects the published `latest`: fails loudly if `releases/latest/download/runtime-manifest.json`
  is missing, lacks either the `darwin-arm64` or `win32-x64` platform, has empty url/sha256, has a version
  that mismatches the latest tag, or if either platform archive URL is not HTTP 200. This single ubuntu job
  (default GITHUB_TOKEN) would have caught v0.10.0, v0.11.0, and v0.12.0.
- **New builder-parity lint `verify_builder_parity.py` (wired into CI `test` job).** Asserts the macOS
  (`package_runtime_payload.sh`) and Windows (`build_runtime_release_windows.py`) builders both vendor the
  same 8 standalone engines + kinastro, both run shaozi-gen + plotly-strip + lunar-javascript install, and
  that `verify_runtime_release.py` REQUIRED_ENTRIES requires the engines/shaozi-JSON/lunar-javascript on
  BOTH platforms — catching the class of drift that caused the v0.10.0 shaozi/plotly gap.
- **Windows launcher hardening (baked into the v0.12.0 zip).** `start_horosa_local.ps1`: stale/already-running
  guard (stops a prior owned instance + emits the manager's `pid files already exist` marker before
  relaunch, so it never orphans processes); port-collision fast-fail (clear `port N already in use by PID …`
  instead of a silent 300s hang — verified fails in ~2s); readiness window raised 180s→300s for slow Java
  warmup; **`-Dfile.encoding=UTF-8 -Dsun.jnu.encoding=UTF-8` on the Java launch** (the bundled Temurin 17 is
  pre-JEP-400 and defaults to the OS code page, which cannot represent the CJK star/格局/神煞 tables).
  `stop_horosa_local.ps1`: only force-kills a PID that still maps to OUR runtime image (no more killing a
  recycled/foreign PID), confirms exit before removing the pid file, and exits non-zero if a process survives.
- **`manager.py` stop/start subprocess captures now pass `encoding="utf-8", errors="replace"`** so CJK
  launcher output can't raise `UnicodeDecodeError` (or mojibake) under a non-UTF-8 Windows code page.
- **Doc accuracy:** README "Release runtime" row → `v0.12.0`; the late-zi-hour PENDING banner in `AGENTS.md`
  + `SKILL.md` corrected (the flag is now wired in the 神数 path — the old "0 occurrences in src/" claim was
  stale — but is still not threaded through the bazi/ziwei/liureng/qimen chart-flow payloads).

## [0.12.0] - 2026-06-11

星阙 v2.6.6 批对齐（上游待发版；vendor 源 = 开源仓 Horosa-Public）。无新工具，仍 68 个。

### Changed — 主限法 v12 · 核5方位法收敛（行为变更，如实声明）

- **方位法白名单收敛为逐位核验的核5**：`core_alchabitius`（默认）/ `meridian` / `porphyry` /
  `equal_ecliptic` / `equal_hour_circle`（另保留 `horosa_legacy` 传统赤经）。v0.10.0 起暴露的
  Placidus / Regiomontanus / Campanus / Topocentric 属未达逐位核验的方位法，已随上游 v2.6.6 方法集收敛从引擎移除——**旧值不报错**：引擎内静默回退 `core_alchabitius` 计算（行集与显式 core
  逐位一致，live 测试钉死），skill 快照设置段对此类值如实标注「未核验，引擎回退」。
- **In-Mundo 行集增多是修复非回归**：显示窗口径换为单参数判据（弧 pre-norm |Δ|<107.5），旧三分支
  λ 窗的世俗核符号错配已修。
- **时间钥匙 9→22 项**：新增 TrueSolarArc（真太阳弧）/ SymbolicSolarArc（太阳弧·黄经，逐弧查星历）
  动态键；Simmonite / Kepler / Brahe 由常数改**每盘真算**（本命太阳日速，live 测试验证与 Ptolemy
  日期全面分叉）；Kündig 等其余静态键补齐；修标签键名 Cardan→Cardano。
- **pdYears 上限 360→3000**：>360 年出多圈复发行（同迫星/应星对弧 +360°×n，live 实测 168 组复发对）。
- **宿命点 (Vertex) 应星**：仅 In-Zodiaco 核出，行 id `N_Vertex_0`，快照渲染「宿命点」。
- 引擎层随同：PD 校准 golden 更名 `golden_alcabitius_ptolemy_v266`；响应回显 `pdSyncRev =
  pd_method_sync_v12`（live 测试以心跳回显作防陈旧进程门）。

### Added — 奇门 faRelatedPeople（法奇门相关人员）

- `qimen` 新可选输入 `faRelatedPeople: [{name, yearGan}]` 或 `[{name, birth}]`——birth（公历）经
  `/nongli/time` 的 `yearJieqi` 按**立春界**解析年干（与上游 `birthToYearGan` 同口径；1991-02-03
  立春前 → 庚 已 live 钉死）。提供后 `[八门化气大阵]` 段逐人多出「生年干·姓名」保护行；缺省不出
  该类行（段表不变，export contract 不动）。

### Fixed — 随 vendor 重同步带入的上游排盘修正批

- 重同步带入星阙 2026-06-10 排盘计算修正批：日返/月返种子根因（distance 全角度域单式）、返照相位
  归一化 [0,180]、合盘/组合盘相位与映点归一化、恒星合相跨 0°、围攻独立 pairOrb、时主星 floor、
  均时差表转录修正、半时区 ±HH:MM 解析（上游 pytest 60 全绿 + golden byte-perfect 验证）。
- 测试装具：live gate 与 `make_service` 改为尊重 `HOROSA_CHART_SERVER_ROOT` / `HOROSA_SERVER_ROOT`
  环境变量（此前写死 `:8899/:9999`，env 覆盖静默失效——本轮即据此把整套 live 验证指到 skill 自己
  vendored 的引擎实例上）。
- 发布工程硬化：`build_runtime_release_windows.py` 的 `._pth` 写入强制 LF（Windows 原生构建下
  `write_text` 会 CRLF 化破坏字节奇偶）；`release.yml` 加 `repository_owner` 闸（fork 推 `v*` tag
  不再排队自托管 runner）。

### Fixed — v0.11.0 Windows half + a stray CHANGELOG conflict marker

- **v0.11.0 was published as `latest` with a darwin-only `runtime-manifest.json` and no Windows zip — so
  `install` worked on macOS but broke on Windows.** Unlike v0.10.0 (which had *no* manifest, breaking both
  platforms), v0.11.0's manifest existed but listed only the `darwin-arm64` platform, and the win32 zip
  404'd — a Windows `install` finds no `win32-x64` entry / asset. Built + natively verified the win32-x64
  v0.11.0 runtime, regenerated the **dual-platform** `runtime-manifest.json` + `SHA256SUMS.txt`, and
  uploaded all three to the v0.11.0 release (already `latest`; the upload alone restores Windows install).
  Native check: `/qimen|/taiyi|/jinkou/pan` → `ResultCode 0` + right source; all 14 神数 return a real
  `Result.snapshot` (shaozi `基础条文` real); tongshefa/canping/heluo OK; `verify_runtime_release.py`
  passes both archives; win zip sha256 `13159b8268748547fef09bae4a54c454ce20526b8601715c8859c2dabac5e5e2`.
  No build-script changes were needed — the v0.10.0 parity work (shaozi gen + plotly strip) carried over,
  and the LF fix landed (the v0.11.0 win zip's `shaozi_tiaowen_6144.json` is now LF, byte-clean).
- **Removed a committed git conflict marker from `CHANGELOG.md`.** The v0.11.0 release-prep merge left a
  stray `>>>>>>> d45ebaf …` line in the changelog on `main` (the `<<<<<<<`/`=======` halves were already
  resolved away). Deleted it; the surrounding content was intact.

### Fixed — v0.10.0 Windows half + cross-platform build parity

- **v0.10.0 was published as `latest` with no `runtime-manifest.json` and no Windows zip — `install` was
  404-broken for *both* platforms.** `horosa-skill install` resolves
  `releases/latest/download/runtime-manifest.json`, which did not exist on the v0.10.0 release (it shipped
  only the darwin tarball + `SHA256SUMS.txt`). Built + natively verified the win32-x64 v0.10.0 runtime on
  Windows, regenerated the dual-platform `runtime-manifest.json` + `SHA256SUMS.txt`, and uploaded all three
  to the v0.10.0 release — restoring `install` for macOS and Windows. (v0.10.0 was already `latest`, so no
  flip was needed; adding the assets fixed the broken state.)
- **`build_runtime_release_windows.py` reached cross-platform parity with `package_runtime_payload.sh`.**
  The v0.10.0 mac packaging script gained two steps the Windows builder lacked, so a Windows build would
  have silently regressed:
  - **邵子神数 verse generation.** Now runs `gen_shaozi_tiaowen.py` over the staged
    `kinastro/astro/shaozi/data/` so `shaozi_tiaowen_6144.json` is generated (4608 verses) and 邵子's
    `基础条文` emits a real verse instead of a placeholder. `verify_runtime_release.py` now requires this
    file on **win32-x64** too (it previously listed it for darwin-arm64 only — an asymmetry that would
    let a placeholder-only Windows build pass). Natively confirmed: `基础条文` resolves a real verse;
    `完整条文` falls back to the engine placeholder because its id is absent from the upstream CSV — this
    is upstream-faithful and **identical on macOS** (verified the mac archive's JSON is content-identical
    and also lacks that id).
  - **plotly strip (~40 MB).** Removed from the embedded site-packages (streamlit-only, never on the
    headless 神数 path; pyarrow/pandas kept). Native cetian/qizhengkin snapshots still build.
- **`gen_shaozi_tiaowen.py` now writes the JSON with `newline="\n"`** so the Windows-built file is
  byte-identical to the macOS-built one (Path.write_text otherwise emits CRLF on Windows — same content,
  different bytes). Functionally inert; keeps the two platform builds reproducible.

## [0.11.0] - 2026-06-08

### Sync — Xingque v2.6.3 → v2.6.5 parity + two v0.10.0 deferrals finished (no new tools; still 68)

Re-synced the bundled runtime from Xingque HEAD and wired the AI-consumable additions.
All changes extend existing tools (parameters / snapshot sections); no new tool was added.

- **Sidereal ayanāṃśa (v2.6.4)** — `siderealAyanamsa` on every BirthInput-derived Western tool
  (47 modes; absent → backend default Lahiri, tropical charts unchanged). The snapshot now prints the
  real ayanāṃśa name, fixing an inherited hardcoded-"Lahiri" bug that mislabelled Raman/Fagan charts.
- **Western nakshatra (v2.6.4)** — a `月宿` section (planet → mansion / lord / pada) on sidereal charts,
  read from `chart.nakshatras`.
- **India chart full (v2.6.4)** — new `IndiaChartInput` with `indiaHsys` (0–24 house systems) +
  `indiaAyanamsa` (47), plus enumerating guidance and a golden test against SE ayanāṃśa baselines.
- **Da Liu Ren Bi-Fa (deferred from v0.10.0)** — the 100 Bi-Fa rules + divination guide, via a verbatim
  vendor of `buildLiuRengReferenceContext` + the `ChuangChart` 三传 engine (pure closures, draw-only deps stubbed).
- **Qi Zheng Si Yu Zheng-Yu patterns (deferred from v0.10.0)** — the Moira-DSL `buildLocalMoiraPatterns`
  vendored verbatim; chart-object patterns fire (god-dependent ones limited by the upstream gods gap, flagged).
- **Zi Wei P0–P2 (v2.6.x)** — the ziwei snapshot gains matched patterns (命中格局), secondary stars (杂曜),
  school-specific si-hua tags, plus 命主/身主/五行局/斗君 and structured 主/辅/煞/杂 + 大限/小限 overview.
- **Python geo robustness** — float lat/lon handled (v2.6.5), via the runtime re-sync.

## [0.10.0] - 2026-06-07

### Sync — Xingque v2.5.2 → v2.6.x feature parity (no new tools; still 68)

Brings the Skill up to the desktop app's current feature surface. All changes extend
existing tools (parameters / snapshot sections); the tool count stays 68.

- **Primary Direction, all house systems (A)** — `pd`/`pdchart` accept `pdMethod`
  (`core_alchabitius`/`placidus`/`regiomontanus`/`campanus`/`topocentric`), `pdtype`
  (In Zodiaco/In Mundo), `pdDirect`/`pdConverse`, `pdAntiscia`/`pdTerms`, `pdTimeKey`
  (`Ptolemy`/`Naibod`); the directions-settings snapshot section now surfaces all of them.
  De-branded the legacy PD-method alias to the canonical `core_alchabitius` (identical output).
- **Midpoint chart → Hamburg/Uranian dial (B)** — `germany` snapshot expands 4 → 10 sections
  (planets / TNP bodies / 90° dial / planetary pictures / antiscia / midpoint list); ports
  `uranianDial.js` to Python.
- **Qi Zheng Si Yu major-period + aspects (C)** — `guolao_chart` snapshot adds `大限` (ported
  `lifeDegree`+`buildGuolaoLimitTable`, golden-tested) and `相位`. Uses the default life mode
  (headless has no per-chart UI prefs). `政余格局` (Moira pattern DSL) is left optional —
  see AGENTS.
- **Jin Kou Jue reading layer (D)** — `jinkou` snapshot expands 4 → 20 sections (yong-strength,
  four-position interactions, timing, branch relations, related shen-sha, categorized
  significators); vendors `JinKouDoc`/`JinKouSnapshot`/`LRZhangSheng` + the 太玄数/刑冲害破 tables.
- **Da Liu Ren common shen-sha (E)** — `liureng_gods` snapshot adds `常用神煞`. 毕法/占断向导
  left out (need the full ~40-field layout context) — see AGENTS.
- **Qi Men Fa Qi Men overlay (F)** — `qimen` snapshot expands 6 → 14 sections (six-harm /
  resolutions / eight-gate array / significator analysis / wealth & career seven-essentials /
  romance / gu-gua); validated against the live `kinqimen` pan.
- **Zi Wei self-transformation (G)** — rides the re-synced jar (compute-layer correctness fix).

## [0.9.2] - 2026-06-02

### Hardening — tests, robustness, fidelity, runtime (no new tools; still 68)

An audit-driven hardening pass over the v0.9.x work (3 read-only Explore audits + manual
verification). No behaviour change for valid input.

- **Tests (P0).** Golden + invariant unit tests for the hand-ported Python 推运 builders
  (persiandirected/yearsystem129/planetaryages) against a fixed chart fixture; all 14 神数 now
  parametrized live with a skip-guard for older backends; an OldBuildClient + bad-date regression
  test; a node golden self-check (`horosa-core-js/test/selfcheck.mjs`) for the vendored horary /
  election / balbillus engines, wired into CI (`npm test` in both jobs). 227 Python tests pass.
- **Robustness (P0-3).** `_split_birth_ymdhm` now raises `tool.shenshu_bad_date` instead of silently
  substituting 2025-01-01; `_run_shenshu_tool` raises `transport.shenshu_snapshot_unavailable` when an
  old backend returns no snapshot; horary/election/progextra log + surface swallowed JS errors. **Fixed
  a real pre-existing bug**: `f"{response.get('snapshot')}"` produced the literal string `"None"` when
  the snapshot was absent (truthy → garbage export).
- **邵子神数 verse fix (P0-5).** Upstream ships 邵子 with only the verse CSV (no 6144 JSON), so every
  reading came back with 【條文待補充】 placeholders. The package step now generates
  `shaozi_tiaowen_6144.json` from the CSV (without touching the 星阙 tree) so the bundled runtime emits
  real 判词 (~75% corpus coverage — the rest fall back, as upstream).
- **Export contracts (P1-1).** New `AI_EXPORT_OPTIONAL_SECTIONS`: conditional / 星阙-UI-only sections
  (election 用事专属/应期; tieban/beiji/chunzi/qizhengkin search panels & mode-conditional sections) no
  longer mark exports "dirty". Completed the qizhengkin preset (今制宿度/古制宿度).
- **Fidelity spot-check (P1-2).** Ran 星阙's actual frontend builder against the same fixture: ages /
  aspects / 向运星 / 本命对象 are byte-identical; only persiandirected's 应期 DATE differs by ≤1 day on
  ~40% of rows (moment fractional-day truncation + JS↔Python float). Documented as astrologically
  negligible (`docs/v091-fidelity-spotcheck.md`). yearsystem129 / planetaryages / balbillus / horary /
  election are faithful by construction.
- **Runtime slim (P2-1).** Dropped `plotly` (~40 MB, streamlit-only, lazily imported). The plan's larger
  target was infeasible — `pyarrow`/`pandas` are astropy dependencies (taiyi needs them), so they stay.
- **De-brand (P2-2).** The pd `pdMethod` guidance description no longer names the borrowed app; the
  functional enum value remains in the example payload (the chart service's API contract).

### Build / Docs (Windows v0.9.1, by the Windows maintainer)

- **v0.9.1 Windows runtime shipped + natively verified.** Built `horosa-runtime-win32-x64-v0.9.1.zip`
  on Windows from a re-synced 星阙 v2.5.0 `vendor/runtime-source` (all 14 神数 engines: the 5 standalone
  + the engine-only `kinastro` for the 9 kinastro-*). Natively confirmed: `/qimen|/taiyi|/jinkou/pan` →
  `ResultCode 0`; **all 14 神数 `/{key}/pan` return a real `Result.snapshot`**; tongshefa/canping/heluo
  via the bundled node; `verify_runtime_release.py` passes both archives; `install` + `doctor` green.
  Uploaded to the `v0.9.1` release and flipped it to public `latest` (supersedes v0.7.0).
- **Docs synced** (`OFFLINE_RUNTIME_RELEASES.md` kinastro input + completed-TODO,
  `WINDOWS_RELEASE_BUILD_PROMPT.md` v0.8.0→v0.9.1, `AGENTS.md` 3 native-build lessons).

## [0.9.1] - 2026-06-02

### Added — the 9 kinastro-* 神数 (total now 68; all 14 神数 complete)

- **All 9 remaining kinastro-* 神数 are now shipped**, completing the 14-技法 神数 family:
  `shaozi` (邵子神数), `tieban` (铁板神数), `fendjing` (分经神数·两头钳), `beiji` (北极神数),
  `nanji` (南极神数), `chunzi` (淳子神数), `xianqin` (演禽), `cetian` (策天飞星·紫微),
  `qizhengkin` (七政四余·张果星宗). Each is a kentang engine mounted on the chart service that
  returns a backend-built `snapshot` matching its export preset (same pattern as the 5 standalone
  神数; cetian/qizhengkin/xianqin also take gender + place).
- These were **deferred in v0.9.0** on the assumption the shared `kinastro` engine was unusable
  offline. That was wrong: the engine imports cleanly under the bundled Python and every srv builds a
  `snapshot` — the v0.9.0 live probe only returned `basic`-only data because the *running* app was an
  older build. The offline runtime now vendors the kinastro **engine only** (`astro/` + root modules,
  ~31 MB) — the 26 MB `tools/cities` geocoding DB + the streamlit ui/docs are excluded (not needed for
  ganzhi-based 神数). Verified in-process: all 9 produce snapshots under the trimmed bundled engine,
  and the kentang mount sim mounts all 17 engines (3 ken + 14 神数).

## [0.9.0] - 2026-06-02

### Added — 星阙 v2.5.0 推运 (7) + 卜卦/择日 + 5 standalone 神数 (14 new tools, total now 59)

- **v2.5.0 推运 (7 techniques).** Completes the predictive set:
  - `jaynesprog` (赤纬推运 / Jayne Declination), `vedicprog` (恒星推运 / Vedic Sidereal),
    `planetaryarc` (行星弧 / Planetary Arc) — backend predict tools (`/astroextra/jaynesprog`,
    `/astroextra/progressions` sidereal, `/predict/planetaryarc`) + Python snapshot builders.
  - `planetaryages` (行星年龄 / Ages of Man), `yearsystem129` (129年系统), `persiandirected`
    (波斯向运 / Persian Directed, 1°/年) — frontend builders ported to Python (read pre-computed chart
    data / pure arithmetic), reusing `_astro_msg` / `_aspect_label`.
  - `balbillus` (Balbillus 129年系统 · 旺距削减主限) — the 247-line recursive algorithm is vendored as
    JS verbatim (`horosa-core-js/src/vendor/astroextra/balbillus.js` + a minimal `progConst.js` stub +
    `moment`) and dispatched through a new `progextra` JS tool.
  - Each has a single-section export contract.
- **`horary` (卜卦) + `election` (择日).** 星阙's entire `divination/` engine (~3200 lines of pure logic)
  is vendored into `horosa-core-js/src/vendor/divination/`. `horary` runs radicality / significators (14
  question categories) / perfection / moon story / verdict / timing; `election` runs hard flags / per-topic
  rule packs (28 topics) / scoring / recommendations. Both cast a traditional chart at the question/candidate
  moment and read back the JS-resolved category/topic (unknown → general/marriage). 9- and 7-section export
  contracts mirroring 星阙's `aiExport.js`.
- **5 standalone 神数 (`wangji` 皇极经世 / `wuzhao` 五兆 / `taixuan` 太玄 / `jingjue` 京氏易 /
  `shenyishu` 神乙数).** kentang engines mounted on the chart service; each returns a backend-built
  `snapshot` whose sections already match the export preset, so the skill just calls `/{key}/pan` and
  exports it. The offline runtime now vendors these 5 engines (`sync_vendored_runtime_sources.sh`).
  The 9 kinastro-* 神数 (shaozi/tieban/fendjing/beiji/nanji/chunzi/xianqin/cetian/qizhengkin) are
  **deferred** — they share a ~61 MB engine and return degraded data on the current chart service
  (documented in AGENTS.md).

### Changed

- **Offline runtime re-vendored to 星阙 v2.5.0** so the bundled chart service carries the v2.5.0 predict
  endpoints (`/astroextra/jaynesprog`, `/astroextra/progressions`, `/predict/planetaryarc`) and the 5
  standalone 神数 kentang mounts. The kentang graceful-mount patch now mounts those 5 (engines vendored)
  while still skipping the 9 kinastro-* (engine not vendored).
- **`_PYTHON_CHART_ENDPOINTS`** gained the v2.5.0 predict endpoints + the 5 神数 `/{key}/pan` mounts
  (kentang mounts only reach the chart service :8899 when listed here).

## [0.8.0] - 2026-05-31

### Added — 星阙 v2.4.0 西占 (Western) techniques

- **`agepoint` (年龄推进点 / Age Point · Huber).** New predictive tool backed by the chart service's
  `/predict/agepoint` — the Koch-house age-point cycle (每宫 6 年, 72 年回归上升) with natal contacts.
  Export contract `['年龄推进点（Age Point / Huber）']`.
- **`distributions` (界推运 / Distributions · 分配法).** New predictive tool backed by `/predict/dist` —
  the Ascendant's primary motion through the Egyptian bounds (distributor + participants timeline).
  Export contract `['界推运（分配法 / Distributions）']`.
- **`mundane` (世俗入宫盘 / mundane ingress chart).** New composite tool: it gets the precise solar-term
  ingress moment (春分/夏至/秋分/冬至) for a year via `/jieqi/year`, casts a `/chart` at that instant, and
  prepends a `[世俗入宫]` section to the astrochart snapshot. Export contract is the astrochart set led by
  `世俗入宫`.
- **本命增补: the astrochart export now carries 12分度 / 主宰星链 / 寿命格局.** The `chart` (and `mundane`)
  astrochart snapshot is enriched with the v2.4.0 Dodekatemoria, dispositor chains, and Hyleg/Alcocoden
  寿命格局. These are computed by a newly vendored 星阙 `divination/` engine subtree
  (`horosa-core-js/src/vendor/divination/` — chartFacts + the Ptolemy lifespan engine + signs/dignities/
  planets/houseMeanings) via a new `astroextra` JS formatter; the skill's Python layer formats them with
  `_astro_msg`. Tool count is now **45** (was 42).

### Changed

- **Offline runtime re-vendored to 星阙 v2.4.0.** `vendor/runtime-source` was re-synced from 星阙's
  current tree so the bundled chart service carries `/predict/agepoint`, `/predict/dist`,
  `/astroextra/greatconj`, and the v2.4.0-enriched `/chart`. (The ken engines came along too; existing
  qimen/taiyi/jinkou behavior is unchanged.)
- **Harness docs: installed an enforced Problem-Logging Protocol.** `AGENTS.md` now opens with a
  `🔴 MANDATORY: Problem-Logging Protocol` (first section, read-first) requiring every problem/gotcha/fix
  to be logged in `AGENTS.md` (+ `SKILL.md` when client-facing, + `CHANGELOG.md`, + a code-level guard
  when machine-assertable) in the same change, with a self-audit gate on every release / bug-check pass.
  `skills/horosa-agent/SKILL.md`'s Maintainer Notes mirror it. The v0.7.0 build/CI/Node-floor lessons are
  recorded in the packaging-gotchas section, and the (deferred) v2.2.1 晚子时 section in both docs now
  carries a `STATUS: PENDING` banner so its target spec is not mistaken for shipped behavior.

### Fixed

- **0.7.0 release: completed the version-string bump.** The v0.7.0 commit bumped `pyproject.toml` to
  `0.7.0` but left `__init__.py.__version__`, `server.json` (the MCP registry manifest, ×2), `CITATION.cff`,
  and the "current version" references in `README.md` / `README_EN.md` at `0.6.3` — so `horosa-skill
  --version` and the MCP-registry-declared version were stale for the 0.7.0 line. All five files now read
  `0.7.0`. `docs/DATA_CONTRACTS.md`'s `tool envelope: 0.6.3` was left as-is (it tracks an independent
  envelope-schema version, not the package version).
- **CI now installs the `lunar-javascript` JS dependency before running tests.** v0.7.0 added
  `lunar-javascript` as `horosa-core-js`'s first npm dependency (needed by the in-process `canping` /
  `heluo` engines), but `node_modules` is gitignored and the CI workflow had no `npm install` step — so
  a fresh checkout failed the three non-runtime-gated `canping` / `heluo` tests with
  `ERR_MODULE_NOT_FOUND`. Both `ci.yml` jobs (`test` + `windows-smoke`) now run `actions/setup-node@v4`
  + `npm ci --omit=dev` in `horosa-core-js` before `pytest`; `release.yml` gains `setup-node` so the
  runtime build's own `npm install` has node on PATH (incl. self-hosted runners). Verified by hiding
  `node_modules` locally (repro'd the failure) then restoring via `npm ci` (3 tests green).

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
