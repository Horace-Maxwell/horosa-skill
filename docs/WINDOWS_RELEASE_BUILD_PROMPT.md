> **Demoted to fallback runbook (v0.38.0 A2)**: the Windows half is derived from the darwin seed on a hosted runner
> (`build_runtime_release_windows.py --seed …`, see docs/OFFLINE_RUNTIME_RELEASES.md). Use this document only when the
> hosted path is unavailable and a Windows box must build in vendor mode.

# Windows runtime build & release — Claude Code handoff prompt

> ⚠️ **状态（2026-09-29）**：这是**后手**。v0.38.0 起 Windows 半边由托管流水线从 darwin 种子派生（`release-runtime.yml` → `build_runtime_release_windows.py --seed`），
> 正常发布不需要 Windows 构建机；只有托管路径不可用时才照本文在 Windows 机上手工构建。手工路径也必须以 `sync_windows_release.py --upload` + `--check` 收尾——
> **不许手写清单、不许手动 `--latest` 翻公开**（digest 闸与矩阵是公开的前提）。文中版本一律写作 `vX.Y.Z`；随包 Python 以 `contracts/runtime_toolchain.json` 为准
> （种子派生的正式载荷是 3.12.x；本文 vendor 模式提到的 3.11.9 只属于旧的本地构建）。

> 读者：Windows 构建机上的维护者/agent。何时读：补建发布的 Windows 半、处理 release-completeness / pin-forward 事故时。

> **Read this whole file, then do the work.** You are a Claude Code agent running on a **Windows**
> machine. A teammate (Claude Code on macOS) finished all the code/test/doc/release work for **Horosa
> Skill vX.Y.Z** but cannot build or natively verify the **Windows** offline runtime — that requires
> win32 wheels and native Windows execution. That is your job. Work carefully and confirm with the
> user before any destructive or irreversible step (especially the final "publish as latest").

---

## 0. Context (what this project is)

Horosa Skill is a local-first MCP/CLI distribution that exposes 星阙 (Horosa) divination engines to AI
agents. Repo: `https://github.com/Horace-Maxwell/horosa-skill` (AGPL-3.0). The Python package lives in
`horosa-skill/`; the headless JS engine in `horosa-skill/horosa-core-js/`.

- **Compute model:** 奇门/太乙/金口 (and 三式合一's 奇门+太乙) are computed by the **ken** Python engines
  (`kinqimen` / `kintaiyi` / `kinjinkou`) mounted on the local Python **chart service** (`:8899`) at
  `/qimen/pan` · `/taiyi/pan` · `/jinkou/pan`. The JS layer only reformats ken's response into
  `aiExport.js` sections. `tongshefa` is pure headless JS; `decennials` is headless Python.
- **Why vX.Y.Z:** the **星阙 v2.6.6 batch — no new tools, still 68.** Primary directions move to the
  PD v12 engine with the **core-5 verified method set** (core_alchabitius/meridian/porphyry/equal_ecliptic/
  equal_hour_circle; 22 time keys; Vertex rows; pdYears 3000), plus the upstream 排盘修正批 (returns /
  synastry / composite normalization fixes) and a new optional `qimen.faRelatedPeople` passthrough.
  **The vendor source is the open-source repo (`HOROSA_SOURCE_ROOT` → `Horosa-Public`)**; the engine itself enforces the core-5 whitelist. Re-syncing the vendor source
  (§2/§3) is REQUIRED. The full 14 神数 (5 standalone + the shared `kinastro` engine) and the
  数算 line (canping/heluo via `lunar-javascript`, so `npm` must be on PATH) carry over from v0.9.x.
  **Build steps added in v0.10.0 (already wired into `build_runtime_release_windows.py` — no manual action):**
  (1) it runs `gen_shaozi_tiaowen.py` over the staged `kinastro/.../shaozi/data/` so 邵子神数 emits real
  verses (without it 邵子's `基础条文` is a placeholder), and (2) it strips plotly (~40 MB, streamlit-only).
  `verify_runtime_release.py` requires `…/shaozi/data/shaozi_tiaowen_6144.json` on **both** platforms.
- **Current state:** main is at vX.Y.Z; the mac side published the `vX.Y.Z` release as `latest`
  (per the user's standing decision: stable, not prerelease) carrying the darwin tar.gz + a
  **darwin-only** `runtime-manifest.json` + `SHA256SUMS.txt`. **The Windows half of vX.Y.Z is PENDING —
  that is your job:** build the win32-x64 zip, natively verify, regenerate the **dual-platform** manifest +
  checksums, and upload to the existing `vX.Y.Z` release (no flip needed — it is already latest; the
  upload alone restores Windows install, same as the v0.11.0 restore). **Heads-up gotcha (hit on v0.10.0 AND v0.11.0):** the mac
  side keeps publishing the new version *already flipped to `latest`* but with an **incomplete release** —
  two variants seen: (a) **no `runtime-manifest.json` at all** (v0.10.0) → `releases/latest/download/runtime-manifest.json`
  404s and `install` breaks on BOTH platforms; (b) a **darwin-only manifest + no win32 zip** (v0.11.0) →
  mac installs but Windows `install` finds no `win32-x64` entry / 404s the zip. **Always check first:**
  `gh release view vX.Y.Z --json assets` (want darwin tar.gz + win32 zip + manifest + SHA256SUMS) and that
  the manifest JSON lists **both** `darwin-arm64` and `win32-x64`. The fix is to build the win half +
  regenerate the **dual-platform** manifest/checksums + upload (no flip needed — it's already latest).
- **Read `AGENTS.md` first** (repo root) — §6 打包不变量, §7 发布协议, and §9 Stability invariants
  are authoritative. **Standing rule (protocol v2, AGENTS.md §2):** any problem/gotcha/fix you hit
  lands in the same change as: a `docs/LESSONS.md` ledger entry + the distilled rule in the right
  `AGENTS.md` section (+ `skills/horosa-agent/SKILL.md` when client-facing) + a `CHANGELOG.md`
  `[Unreleased]` entry + a machine guard when assertable.

## 1. Goal (acceptance criteria)

1. Build `horosa-skill/dist/runtime/horosa-runtime-win32-x64-vX.Y.Z.zip`.
2. **Natively verify on Windows** that the bundled chart service boots and the ken endpoints + the
   corrected tongshefa work (commands in §4). This is the part macOS could not do.
3. Regenerate `runtime-manifest.json` + `SHA256SUMS.txt` covering **both** platform archives, and run
   `verify_runtime_release.py` against both.
4. Upload the Windows zip (+ refreshed manifest/checksums) to the `vX.Y.Z` GitHub release. No flip is
   needed — vX.Y.Z is already the public **latest**; the upload alone restores Windows install.

## 2. Prerequisites — confirm with the user before building

You need these present; **ask the user** where they live if not obvious:

- **Tools:** `git`, `gh` (authenticated: `gh auth status`), Python 3.12 + `uv`, **Node.js + `npm` on
  PATH**, and internet access (the build downloads Node win-x64, Temurin JDK17, and the CPython 3.11.9
  embeddable zip).
- **`npm` is required (new for the 数算 modules).** The Windows builder now runs `npm install --omit=dev`
  in `horosa-skill/horosa-core-js` so the `lunar-javascript` package (which `canping`/`heluo` need to
  compute four pillars in-process) is bundled into `horosa-core-js/node_modules/`. `verify_runtime_release.py`
  requires `horosa-core-js/node_modules/lunar-javascript/package.json` in the zip — if `npm` is missing
  the builder aborts with `npm not found on PATH`.
- **Vendored runtime source** under `vendor/runtime-source/` (the build reads it; it is *not* committed
  to git). The Windows builder `scripts/build_runtime_release_windows.py` `require_path()`s all of:
  - `vendor/runtime-source/Horosa-Web/{start_horosa_local.sh, astropy, flatlib-ctrad2, vendor/kinqimen,
    vendor/kintaiyi, vendor/kinjinkou, astrostudyui/dist-file, astrostudyui/scripts/warmHorosaRuntime.js,
    scripts/repairEmbeddedPythonRuntime.py}`
  - **the 14 神数 engines** under `vendor/runtime-source/Horosa-Web/vendor/`: the 5 standalone
    (`kinwangji`, `kinwuzhao`, `taixuanshifa`, `jingjue`, `shenyishu`) are `require_path`'d in full, and
    **`kinastro/astro/`** (engine-only; `tools`/`cities`/`ui`/`docs` excluded) backs the 9 kinastro-* 神数.
    `verify_runtime_release.py` requires all of these in the zip — `sync_vendored_runtime_sources.sh`
    pulls them (with the kinastro trim) when you re-sync from a the pinned Horosa-Public tree (see contracts/upstream_provenance.json).
  - `vendor/runtime-source/runtime/mac/bundle/astrostudyboot.jar` (the Java boot jar is
    platform-independent and reused for Windows)
  - **`vendor/runtime-source/runtime/windows/bundle/wheels/`** ← **the critical Windows-only input.**
- **win32 wheels** in that `wheels/` dir. They MUST include the ken deps **`bidict`, `numpy`,
  `kerykeion`, `ephem`, `pendulum`** *plus* the base chart deps (`cn2an`, `sxtwl`, `cnlunar`,
  `swisseph`) and the rest of `astropy`'s requirements — as **win_amd64 / cp311** wheels (the embedded
  Python is 3.11.9). If `swefiles/` ephemeris data or these wheels are missing the runtime will not
  start. Sync the vendor source from the 星阙 tree(s):
  `HOROSA_SOURCE_ROOT=<星阙-tree> HOROSA_WINDOWS_SOURCE_ROOT=<windows-tree> bash
  horosa-skill/scripts/sync_vendored_runtime_sources.sh` — `HOROSA_SOURCE_ROOT` (the dir containing
  `Horosa-Web/`) brings in the **current ken engines** + astropy + flatlib + the Java jar, and
  `HOROSA_WINDOWS_SOURCE_ROOT` brings in `runtime/windows/{python,java,bundle/wheels}`. **Re-syncing is
  required for vX.Y.Z** — that is how the build picks up the current `kinqimen`/`kintaiyi`. Confirm the
  win32 wheels are produced (typically `pip download --only-binary=:all: --platform win_amd64
  --python-version 311` of the dep set, or built on this machine).

## 3. Build the Windows runtime

```powershell
# from the repo root
git fetch origin; git checkout main; git pull        # must include vX.Y.Z (pyproject version == X.Y.Z)
cd horosa-skill
uv sync
uv run python -c "from horosa_skill import __version__; print(__version__)"   # expect X.Y.Z

# build the win32-x64 zip (downloads Node/Java/embedded-Python, unpacks the win32 wheels, bundles
# Horosa-Web + ken engines + horosa-core-js, writes the embedded runtime-manifest.json)
uv run python scripts/build_runtime_release_windows.py
dir dist\runtime\horosa-runtime-win32-x64-vX.Y.Z.zip
```

If `build_runtime_release_windows.py` exits with `missing required path: …`, that input (§2) is absent —
fix the input, don't patch the script around it.

## 4. Verify natively on Windows (the important part)

Extract the zip to a scratch dir and confirm the runtime actually runs.

```powershell
$dst = "$env:TEMP\horosa-vX-verify"
Remove-Item -Recurse -Force $dst -ErrorAction SilentlyContinue
Expand-Archive dist\runtime\horosa-runtime-win32-x64-vX.Y.Z.zip -DestinationPath $dst
$payload = Join-Path $dst "runtime-payload"

# (a) embedded manifest must read X.Y.Z
Get-Content (Join-Path $payload "runtime-manifest.json")

# (b) start the chart service on a NON-default port (do NOT collide with anything on 8899)
$env:HOROSA_CHART_PORT = "8896"
& (Join-Path $payload "Horosa-Web\start_horosa_local.ps1")
# wait until 127.0.0.1:8896 is listening (the PD warmup takes a few seconds), then:

# (c) ken endpoints must respond with ResultCode 0 + the right source
$qi = '{"year":1998,"month":2,"day":20,"hour":20,"minute":48,"qimenMode":"hour","qijuMethod":"chaibu","option":1}'
Invoke-RestMethod -Uri http://127.0.0.1:8896/qimen/pan -Method Post -ContentType 'application/json' -Body $qi | ConvertTo-Json -Depth 4 | Select-String 'ResultCode','kinqimen'
$ty = '{"year":2026,"month":2,"day":17,"hour":21,"minute":50,"style":3,"tn":0,"sex":"男"}'
Invoke-RestMethod -Uri http://127.0.0.1:8896/taiyi/pan -Method Post -ContentType 'application/json' -Body $ty | ConvertTo-Json -Depth 4 | Select-String 'ResultCode','kintaiyi'
$jk = '{"year":2026,"month":2,"day":17,"hour":21,"minute":50,"difen":"午"}'
Invoke-RestMethod -Uri http://127.0.0.1:8896/jinkou/pan -Method Post -ContentType 'application/json' -Body $jk | ConvertTo-Json -Depth 4 | Select-String 'ResultCode','kinjinkou'

# (d) corrected tongshefa via the BUNDLED node (palace element from the 京房本宫, not the upper trigram)
$node = Join-Path $payload "runtime\windows\node\node.exe"
$cli  = Join-Path $payload "horosa-core-js\bin\cli.mjs"
'{"taiyin":"巽","taiyang":"离","shaoyang":"震","shaoyin":"坤"}' | & $node $cli run tongshefa
# expect data.baseRight.name == 火地晋, data.right_elem == 金, data.main_relation == 实克思

# stop the services by PID when done (NEVER pkill/kill by process name — that would also kill a real
# :8899 stack). The .ps1 prints/records the PIDs it started; stop those, or use stop_horosa_local.ps1.
```

Acceptance: all three ken endpoints return `ResultCode 0` with `source` = `kinqimen`/`kintaiyi`/`kinjinkou`;
tongshefa returns `right_elem=金 / main_relation=实克思`; the embedded manifest says `X.Y.Z`.

Also run the unit suite on Windows for cross-platform coverage (the ken integration tests need the live
chart service — point the skill at your running `:8896` or bring up the full stack):

```powershell
cd horosa-skill
uv run pytest -q
```

## 5. Regenerate manifest + checksums over BOTH archives, then verify both

The macOS archive already exists on the `vX.Y.Z` release — download it next to the Windows zip so the
manifest and `SHA256SUMS.txt` cover both platforms.

```powershell
cd horosa-skill
gh release download vX.Y.Z --repo Horace-Maxwell/horosa-skill `
  --pattern "horosa-runtime-darwin-arm64-vX.Y.Z.tar.gz" --dir dist\runtime

uv run python scripts/generate_release_manifest.py `
  --version X.Y.Z `
  --darwin-archive dist\runtime\horosa-runtime-darwin-arm64-vX.Y.Z.tar.gz `
  --darwin-url https://github.com/Horace-Maxwell/horosa-skill/releases/download/vX.Y.Z/horosa-runtime-darwin-arm64-vX.Y.Z.tar.gz `
  --windows-archive dist\runtime\horosa-runtime-win32-x64-vX.Y.Z.zip `
  --windows-url https://github.com/Horace-Maxwell/horosa-skill/releases/download/vX.Y.Z/horosa-runtime-win32-x64-vX.Y.Z.zip `
  --output dist\runtime\runtime-manifest.json

# checksums over both archives (regenerate SHA256SUMS.txt for both)
cd dist\runtime
(Get-FileHash horosa-runtime-darwin-arm64-vX.Y.Z.tar.gz -Algorithm SHA256).Hash.ToLower() + "  horosa-runtime-darwin-arm64-vX.Y.Z.tar.gz" | Out-File SHA256SUMS.txt -Encoding ascii
(Get-FileHash horosa-runtime-win32-x64-vX.Y.Z.zip -Algorithm SHA256).Hash.ToLower() + "  horosa-runtime-win32-x64-vX.Y.Z.zip" | Out-File SHA256SUMS.txt -Append -Encoding ascii
cd ..\..

# verify BOTH archives structurally (this checks required entries incl. real files inside swefiles/,
# astropy/, vendor/kin*/ — an empty required dir now correctly FAILS).
uv run python scripts/verify_runtime_release.py `
  --darwin-archive dist\runtime\horosa-runtime-darwin-arm64-vX.Y.Z.tar.gz `
  --windows-archive dist\runtime\horosa-runtime-win32-x64-vX.Y.Z.zip `
  --manifest dist\runtime\runtime-manifest.json
```

`verify_runtime_release.py` must exit 0. If it reports a missing entry, the Windows zip is incomplete —
fix the input/build, don't loosen the verifier.

## 6. Finalize the vX.Y.Z release (confirm with the user first)

Never upload a hand-written manifest and never flip `--latest` by hand. The fallback ends exactly like the hosted path:

```powershell
# build + verify + dual-platform manifest/checksums + upload to the (draft) release, idempotently:
python horosa-skill\scripts\sync_windows_release.py --upload --tag vX.Y.Z --draft
# authoritative verdict — [OK] required, [GAP] means do not publish:
python horosa-skill\scripts\sync_windows_release.py --check --tag vX.Y.Z --draft
```

Then hand back to the macOS maintainer: the public flip goes through `gh workflow run release-runtime.yml -f version=X.Y.Z -f publish=true
-f run_matrix=true` so the three-machine matrix and the digest gate (lane-installed sha == release asset digest) still run
(`docs/OPERATIONS.md`「Runtime Release Runbook」). A post-flip `sync_windows_release.py --check` on the public latest must print `[OK]`.
