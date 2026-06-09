# Windows runtime build & release — Claude Code handoff prompt

> **Read this whole file, then do the work.** You are a Claude Code agent running on a **Windows**
> machine. A teammate (Claude Code on macOS) finished all the code/test/doc/release work for **Horosa
> Skill v0.11.0** but cannot build or natively verify the **Windows** offline runtime — that requires
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
- **Why v0.11.0:** a **星阙 v2.5.2→v2.6.x parity sync — no new tools, still 68.** It extends existing
  tools (PD all-house-systems, Hamburg/Uranian midpoint dial, 七政四余 大限/相位, 金口诀 reading layer,
  大六壬 常用神煞, 奇门 法奇门 overlay). The runtime is re-vendored to the current 星阙, so re-syncing the
  vendor source (§2/§3) is REQUIRED. The full 14 神数 (5 standalone + the shared `kinastro` engine) and the
  数算 line (canping/heluo via `lunar-javascript`, so `npm` must be on PATH) carry over from v0.9.x.
  **Build steps added in v0.10.0 (already wired into `build_runtime_release_windows.py` — no manual action):**
  (1) it runs `gen_shaozi_tiaowen.py` over the staged `kinastro/.../shaozi/data/` so 邵子神数 emits real
  verses (without it 邵子's `基础条文` is a placeholder), and (2) it strips plotly (~40 MB, streamlit-only).
  `verify_runtime_release.py` requires `…/shaozi/data/shaozi_tiaowen_6144.json` on **both** platforms.
- **Current state:** main is at v0.11.0 and **v0.11.0 has shipped on both platforms** (darwin + win32-x64
  zips + dual-platform `runtime-manifest.json` + `SHA256SUMS.txt`), and it is the public `releases/latest`.
  There is **no pending Windows build right now.** If you are reading this for the *next* version vX.Y.Z:
  the mac side will publish a `vX.Y.Z` prerelease carrying only the darwin archive (+ maybe SHA256SUMS) —
  your job is to produce the win32-x64 zip, regenerate the dual-platform manifest + checksums, upload, and
  (after the user confirms) flip it to latest. **Heads-up gotcha (hit on v0.10.0 AND v0.11.0):** the mac
  side keeps publishing the new version *already flipped to `latest`* but with an **incomplete release** —
  two variants seen: (a) **no `runtime-manifest.json` at all** (v0.10.0) → `releases/latest/download/runtime-manifest.json`
  404s and `install` breaks on BOTH platforms; (b) a **darwin-only manifest + no win32 zip** (v0.11.0) →
  mac installs but Windows `install` finds no `win32-x64` entry / 404s the zip. **Always check first:**
  `gh release view vX.Y.Z --json assets` (want darwin tar.gz + win32 zip + manifest + SHA256SUMS) and that
  the manifest JSON lists **both** `darwin-arm64` and `win32-x64`. The fix is to build the win half +
  regenerate the **dual-platform** manifest/checksums + upload (no flip needed — it's already latest).
- **Read `AGENTS.md` first** (repo root) — its "Maintainer & Build Notes" + "Stability invariants"
  sections are authoritative. **Standing rule:** if you hit any problem/gotcha/fix, update **both**
  `AGENTS.md` and `skills/horosa-agent/SKILL.md` in the same change (keep them in sync), and log it in
  `CHANGELOG.md` under `[Unreleased]`.

## 1. Goal (acceptance criteria)

1. Build `horosa-skill/dist/runtime/horosa-runtime-win32-x64-v0.11.0.zip`.
2. **Natively verify on Windows** that the bundled chart service boots and the ken endpoints + the
   corrected tongshefa work (commands in §4). This is the part macOS could not do.
3. Regenerate `runtime-manifest.json` + `SHA256SUMS.txt` covering **both** platform archives, and run
   `verify_runtime_release.py` against both.
4. Upload the Windows zip (+ refreshed manifest/checksums) to the `v0.11.0` GitHub release, then — only
   after the user confirms — flip it from prerelease to the public **latest** release.

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
    pulls them (with the kinastro trim) when you re-sync from a 星阙 v2.5.0 tree.
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
  required for v0.11.0** — that is how the build picks up the current `kinqimen`/`kintaiyi`. Confirm the
  win32 wheels are produced (typically `pip download --only-binary=:all: --platform win_amd64
  --python-version 311` of the dep set, or built on this machine).

## 3. Build the Windows runtime

```powershell
# from the repo root
git fetch origin; git checkout main; git pull        # must include v0.11.0 (pyproject version == 0.11.0)
cd horosa-skill
uv sync
uv run python -c "from horosa_skill import __version__; print(__version__)"   # expect 0.11.0

# build the win32-x64 zip (downloads Node/Java/embedded-Python, unpacks the win32 wheels, bundles
# Horosa-Web + ken engines + horosa-core-js, writes the embedded runtime-manifest.json)
uv run python scripts/build_runtime_release_windows.py
dir dist\runtime\horosa-runtime-win32-x64-v0.11.0.zip
```

If `build_runtime_release_windows.py` exits with `missing required path: …`, that input (§2) is absent —
fix the input, don't patch the script around it.

## 4. Verify natively on Windows (the important part)

Extract the zip to a scratch dir and confirm the runtime actually runs.

```powershell
$dst = "$env:TEMP\horosa-v062-verify"
Remove-Item -Recurse -Force $dst -ErrorAction SilentlyContinue
Expand-Archive dist\runtime\horosa-runtime-win32-x64-v0.11.0.zip -DestinationPath $dst
$payload = Join-Path $dst "runtime-payload"

# (a) embedded manifest must read 0.11.0
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
tongshefa returns `right_elem=金 / main_relation=实克思`; the embedded manifest says `0.11.0`.

Also run the unit suite on Windows for cross-platform coverage (the ken integration tests need the live
chart service — point the skill at your running `:8896` or bring up the full stack):

```powershell
cd horosa-skill
uv run pytest -q
```

## 5. Regenerate manifest + checksums over BOTH archives, then verify both

The macOS archive already exists on the `v0.11.0` release — download it next to the Windows zip so the
manifest and `SHA256SUMS.txt` cover both platforms.

```powershell
cd horosa-skill
gh release download v0.11.0 --repo Horace-Maxwell/horosa-skill `
  --pattern "horosa-runtime-darwin-arm64-v0.11.0.tar.gz" --dir dist\runtime

uv run python scripts/generate_release_manifest.py `
  --version 0.11.0 `
  --darwin-archive dist\runtime\horosa-runtime-darwin-arm64-v0.11.0.tar.gz `
  --darwin-url https://github.com/Horace-Maxwell/horosa-skill/releases/latest/download/horosa-runtime-darwin-arm64-v0.11.0.tar.gz `
  --windows-archive dist\runtime\horosa-runtime-win32-x64-v0.11.0.zip `
  --windows-url https://github.com/Horace-Maxwell/horosa-skill/releases/latest/download/horosa-runtime-win32-x64-v0.11.0.zip `
  --output dist\runtime\runtime-manifest.json

# checksums over both archives (regenerate SHA256SUMS.txt for both)
cd dist\runtime
(Get-FileHash horosa-runtime-darwin-arm64-v0.11.0.tar.gz -Algorithm SHA256).Hash.ToLower() + "  horosa-runtime-darwin-arm64-v0.11.0.tar.gz" | Out-File SHA256SUMS.txt -Encoding ascii
(Get-FileHash horosa-runtime-win32-x64-v0.11.0.zip -Algorithm SHA256).Hash.ToLower() + "  horosa-runtime-win32-x64-v0.11.0.zip" | Out-File SHA256SUMS.txt -Append -Encoding ascii
cd ..\..

# verify BOTH archives structurally (this checks required entries incl. real files inside swefiles/,
# astropy/, vendor/kin*/ — an empty required dir now correctly FAILS).
uv run python scripts/verify_runtime_release.py `
  --darwin-archive dist\runtime\horosa-runtime-darwin-arm64-v0.11.0.tar.gz `
  --windows-archive dist\runtime\horosa-runtime-win32-x64-v0.11.0.zip `
  --manifest dist\runtime\runtime-manifest.json
```

`verify_runtime_release.py` must exit 0. If it reports a missing entry, the Windows zip is incomplete —
fix the input/build, don't loosen the verifier.

## 6. Finalize the v0.11.0 release (confirm with the user first)

```powershell
gh release upload v0.11.0 --repo Horace-Maxwell/horosa-skill `
  horosa-skill\dist\runtime\horosa-runtime-win32-x64-v0.11.0.zip `
  horosa-skill\dist\runtime\runtime-manifest.json `
  horosa-skill\dist\runtime\SHA256SUMS.txt --clobber

# ONLY after the user confirms they want v0.11.0 to become the public latest:
gh release edit v0.11.0 --repo Horace-Maxwell/horosa-skill --draft=false --prerelease=false --latest
```

After flipping to latest, sanity-check a fresh install path on a clean Windows box if possible:
`uv run horosa-skill install` then `uv run horosa-skill doctor` (expect `issues: []`).

## 7. Gotchas (these have bitten the macOS side — heed them)

- **win32 wheels are the whole game.** If `vendor/runtime-source/runtime/windows/bundle/wheels` lacks
  `bidict`/`numpy`/`kerykeion`/`ephem`/`pendulum` (or the swefiles ephemeris is empty), the chart service
  boots but mounts no ken endpoints, or fails to import — verify §4(c) actually returns charts, don't
  trust "it started".
- **Never kill chart services by process name.** `taskkill /im python.exe` (or pkill-style) would also
  kill any other Python. Stop by the PID the launcher started.
- **Don't loosen `verify_runtime_release.py`.** It intentionally requires a real file *inside* each
  required directory (an empty `swefiles/`/`vendor/kin*/` marker fails). A failure means the build is
  incomplete.
- **Keep edits cross-platform.** Don't break the macOS/POSIX paths; the same scripts build both platforms.
- **Report back to the user** with: the Windows zip SHA256, the three ken endpoint results, the tongshefa
  result, `verify_runtime_release.py` output, and whether you flipped v0.11.0 to latest. If you changed
  anything in the repo, push to `main` and update `CHANGELOG.md` + `AGENTS.md`/skill doc per the
  force-sync rule.
