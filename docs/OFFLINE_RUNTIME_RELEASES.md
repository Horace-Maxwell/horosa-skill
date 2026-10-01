# Offline Runtime Releases

> 读者：维护者。何时读：打包/发布离线 runtime、核对 payload 必含物时。发布法则：[`AGENTS.md`](../AGENTS.md) §6–§7。

This repository is meant to stay lightweight in Git history while still supporting fully local runtime packaging.

Complete offline runtime payloads are published as GitHub Release assets, but the source inputs needed to build those payloads should live locally inside [`../vendor/runtime-source`](../vendor).

That local folder is allowed to exist on disk without being committed to the repository.

## Supported Platforms

| Platform | Key | Archive type | Build script |
|---|---|---|---|
| macOS (Apple Silicon) | `darwin-arm64` | tar.gz | `package_runtime_payload.sh` |
| Windows (x64) | `win32-x64` | zip | `build_runtime_release_windows.py` |
| Linux (x64) 🧪 | `linux-x64` | tar.gz | `build_runtime_release_linux.py` |

> 🧪 **Linux**: `build_runtime_release_linux.py` / `scaffold_linux_runtime.py` exist as an experimental builder only. No
> `linux-x64` payload has ever been published and `contracts/release_platforms.json` lists it (with Intel Mac) under
> `unsupported` → gateway mode (`HOROSA_SERVER_ROOT` / `HOROSA_CHART_SERVER_ROOT` pointing at a machine that has the runtime).
> Windows ARM is an **alias**: it installs the `win32-x64` payload under emulation (matrix lane `windows-11-arm`).

## Runtime Placement Policy

Use this rule set consistently:

- `vendor/runtime-source/`
  Maintainer-only local packaging inputs. Keep this on disk if you need to build releases from this folder alone.
- installed runtime under `~/.horosa/runtime/current` or `%LOCALAPPDATA%/Horosa/runtime/current`
  End-user runtime location after `horosa-skill install`.
- GitHub Releases assets
  The public distribution channel for complete offline runtimes.

Do not treat these three locations as interchangeable.

- `vendor/runtime-source/` is not the end-user install target
- the installed runtime is not supposed to live inside the repository
- GitHub repo history is not supposed to carry the full packaged runtime by default

## What A Release Must Contain

- Python calculation layer and required dependencies
- ken engines `Horosa-Web/vendor/{kinqimen,kintaiyi,kinjinkou}` backing the chart-service
  `/qimen/pan` · `/taiyi/pan` · `/jinkou/pan` mounts (奇门 / 太乙 / 金口, and 三式合一's 奇门+太乙)
- the ken Python dependencies in the wheel/site-packages set, **in addition to** the base chart deps
  (`cn2an` / `sxtwl` / `cnlunar` / `swisseph`): `bidict` (kinqimen), `numpy` · `kerykeion` ·
  `ephem` (kintaiyi), `pendulum` (kinjinkou). macOS's embedded Python already carries these; the derived
  Windows payload takes them from `contracts/runtime_python_lock.json` (seed-derived; pyswisseph / sxtwl are
  built from sdist on the runner) — a missing one means the chart service fails to mount the ken endpoints.
- Java aggregation layer and boot jar
- Node runtime for headless JS calculation modules (统摄法 + ken-response → aiExport.js formatting)
- Swiss Ephemeris data and any other local astronomical assets
- `runtime-manifest.json`
- inside the wheel (pyproject force-include, `verify_wheel_contents.py`): `runtime_templates/windows` and the runtime
  contracts `contracts/jev_thresholds.json` + `contracts/technique_provenance.json`, resolved at runtime by
  `contracts_locator.py`; `.mcpbignore` whitelists the same files for the `.mcpb` bundle (v0.40.0 P1)

- `horosa_skill-<version>-py3-none-any.whl` — the pure-Python wheel; `uvx --from <its URL> horosa-skill …` is the git-free, PyPI-free zero-install path (v0.38.0). Mirror-aware via `HOROSA_RUNTIME_MIRROR`; asserted + executed by `release-completeness.yml`.

## Maintainer Workflow

1. Refresh vendored runtime sources inside this repository when needed (`sync_vendored_runtime_sources.sh`).
2. `publish_release.sh --draft --dispatch` builds the **darwin seed** from `vendor/runtime-source` (via `package_runtime_payload.sh`),
   puts seed / `.mcpb` / wheel / SBOM on a **draft** release and dispatches `release-runtime.yml`.
3. The hosted pipeline derives the Windows archive from the seed on `windows-latest`, assembles the dual-platform manifest
   (tag-pinned URLs + sizes + `min_os`), `SHA256SUMS.txt`, SBOM and provenance attestation, then runs the three-machine matrix.
4. `sync_windows_release.py --check --tag vX --draft` must print `[OK]`; the publish job flips the draft to `latest` only after the
   lane-installed archive digests equal the draft assets.
5. `horosa-skill install` reads `releases/latest/download/runtime-manifest.json`; the completeness guard re-checks every asset every 6 h.

> **Windows fallback only.** Since v0.38.0 the Windows archive is derived on the hosted runner; the self-contained Windows-box runbook
> [`WINDOWS_RELEASE_BUILD_PROMPT.md`](./WINDOWS_RELEASE_BUILD_PROMPT.md) is the fallback when the hosted path is down, and it must end
> in `sync_windows_release.py --upload` + `--check`, never a manual manifest or a manual `--latest` flip.

## Scripts In This Repo

- `horosa-skill/scripts/publish_release.sh`
  The maintainer-side release entry (`--draft --dispatch`): seed payload → darwin manifest (local check) → SBOM → MCPB → wheel → SHA256SUMS → verify → draft upload → dispatch.
- `horosa-skill/scripts/build_runtime_release.sh`
  **Historical (≤ v0.37.0)**: local dual-platform build in vendor mode; needs Windows-side inputs (`runtime/windows/bundle/wheels`) and stamps `latest` URLs — do not use for a release.
- `horosa-skill/scripts/package_runtime_payload.sh`
  Assembles the runtime payload tarball from `vendor/runtime-source`.
- `horosa-skill/scripts/build_runtime_release_windows.ps1`
  Packages a staged Windows `runtime-payload/` directory into a release zip.
- `horosa-skill/scripts/generate_release_manifest.py`
  Generates a manifest JSON containing version, URLs, checksums, and archive type.
- `horosa-skill/scripts/verify_runtime_release.py`
  Validates that the generated runtime archives really contain the required runtime payload layout.
- `horosa-skill/scripts/scaffold_windows_runtime.py`
  Creates a Windows runtime directory skeleton with manifest and PowerShell entrypoints.
- `horosa-skill/scripts/scaffold_linux_runtime.py`
  Creates a Linux runtime directory skeleton with manifest and POSIX shell entrypoints.
- `horosa-skill/scripts/build_runtime_release_linux.py`
  Experimental Linux builder (no payload published; `linux-x64` is `unsupported` in `contracts/release_platforms.json`).
- `horosa-skill/scripts/sync_vendored_runtime_sources.sh`
  Pulls the required runtime subset from the read-only Horosa-Public checkout (`HOROSA_SOURCE_ROOT`) into `vendor/runtime-source`; what was pulled is recorded in `contracts/upstream_provenance.json`.
- `horosa-skill/scripts/sync_windows_release.py`
  `--check` = the authoritative completeness / pin-forward verdict (`--tag vX --draft` during a release, bare for the public latest); `--upload` = the Windows-box remediation fallback.

## Current Windows Reality

> **v0.38.0 (A2)**: the Windows payload is now **derived from the darwin-arm64 seed** —
> `python horosa-skill/scripts/build_runtime_release_windows.py --seed dist/runtime/horosa-runtime-darwin-arm64-v<ver>.tar.gz`
> runs on any host (`release-runtime.yml` runs it on GitHub's `windows-latest`, then `runtime-matrix.yml` installs the result on
> macos-latest / windows-latest / windows-11-arm and boots it — v0.38.0 A5). The platform-independent tree comes from the seed;
> JDK / Node / embedded CPython 3.12 come from the pins in `contracts/runtime_toolchain.json`; the Python dep set is
> `contracts/runtime_python_lock.json` (seed-derived; pyswisseph and sxtwl are built from sdist on the Windows runner because PyPI
> ships no cp312 Windows wheels). The vendor mode described below is the Windows-box fallback only.


The repository now produces a real Windows runtime archive:

- embedded Java runtime
- embedded Python runtime
- embedded Node runtime
- local wheels unpacked into the payload (must include the ken deps: `bidict`, `numpy`,
  `kerykeion`, `ephem`, `pendulum`)
- ken engines under `Horosa-Web/vendor/{kinqimen,kintaiyi,kinjinkou}`
- **(v0.9.0+) the 5 standalone 神数 engines** under
  `Horosa-Web/vendor/{kinwangji,kinwuzhao,taixuanshifa,jingjue,shenyishu}`
- **(v0.9.1+) the shared `kinastro` engine** (engine only — `Horosa-Web/vendor/kinastro/astro/` + root
  modules; the ~26 MB `tools/cities` geocoding DB + the streamlit ui/frontend/docs are excluded) backing
  the 9 kinastro-* 神数 (`/shaozi/pan` … `/qizhengkin/pan`)
- `astrostudyboot.jar`
- `horosa-core-js`
- runtime manifest and startup scripts

`build_runtime_release_windows.py` must bundle the three ken engines **+ the 5 standalone 神数
engines** (kinwangji/kinwuzhao/taixuanshifa/jingjue/shenyishu) **+ the shared `kinastro` engine**
(engine-only, for the 9 kinastro-* 神数 — mirror the mac `package_runtime_payload.sh` engine loop +
kinastro trim) and patch the staged `kentang/registry.py` mount so the chart service still boots and
gracefully skips any engine that is genuinely absent; `start_horosa_local.ps1` puts `Horosa-Web/vendor`
on `PYTHONPATH` so `import kinqimen` / `kintaiyi` / `kinjinkou` / `kinwangji` / `kinwuzhao` /
`taixuanshifa` / `jingjue` / `shenyishu` / `kinastro` resolve. Before it starts the chart service it also sets
`HOROSA_EPHE_PATH_FASTPATH=0`: Swiss Ephemeris state is thread-local on Windows, and upstream v3.11.2's ephemeris-path
fast path would leave CherryPy's pool threads on the default `\sweph\ephe\` path, losing every asteroid (v0.40.0 draft;
guarded by `scripts/verify_runtime_scripts.py`).

> **✅ v0.9.1 Windows sync DONE (was a v0.9.0 TODO):** the Windows v0.9.1 zip was built **and natively
> verified on a real Windows machine** (not just structurally on the mac dev box). Confirmed: the bundled
> chart service boots and `/qimen/pan` · `/taiyi/pan` · `/jinkou/pan` return `ResultCode 0` with the
> right `source`; **all 14 神数 respond with a real `Result.snapshot`** — the 5 standalone
> (`/wangji` · `/wuzhao` · `/taixuan` · `/jingjue` · `/shenyishu`) **and** the 9 kinastro-*
> (`/shaozi` … `/qizhengkin`, `source: kinastro`) under the trimmed engine-only kinastro; tongshefa /
> canping / heluo work via the bundled node; `verify_runtime_release.py` passes both archives.

Windows verification is **native** on every release: `runtime-matrix.yml` installs the derived zip on `windows-latest` and
`windows-11-arm` (x64 emulation) and boots it, runs the nine client setups, the HTTP handshake, the offline pytest suite
(`PYTEST_BUDGET_SECONDS` nt 2700 / posix 1500, streamed to `pytest.log`) and the live tool sweep. The runtime root on Windows
must be pure ASCII (`runtime.path_not_ascii`; lane step `non_ascii_root_refusal`). The same matrix runs on a weekly `schedule`
(Mondays, `23 4 * * 1`) against `main` × the public latest, and `release-completeness.yml` kicks it if the cron slot was skipped.

## Example Manifest

See [`runtime-manifest.example.json`](./runtime-manifest.example.json).

For the embedded payload manifest, see [`RUNTIME_MANIFEST_SPEC.md`](./RUNTIME_MANIFEST_SPEC.md).

## PyPI（v0.36.0 通道就绪、**尚未开通**；开通后 `uvx horosa-skill`）

- 状态（2026-09-04）：v0.36.0 发布时 publish-pypi 的 build 作业已绿，publish 作业因 pypi.org 侧尚无项目/Trusted Publisher 而失败（预期）；维护者决定暂缓，GitHub Release 仍是安装渠道。开通只需下面的一次性步骤，之后手动 dispatch 一次即可补发 0.36.0。

- 通道：`.github/workflows/publish-pypi.yml`——GitHub Release **published** 自动触发（与 darwin 半同一次发布）或手动
  dispatch（`dry_run=true` 只构建校验不上传）。认证走 PyPI Trusted Publishing（OIDC），仓库不存任何 token。
- **一次性人工步骤**（维护者）：在 PyPI 创建 `horosa-skill` 项目并添加 pending publisher（owner `Horace-Maxwell`、
  repo `horosa-skill`、workflow `publish-pypi.yml`、environment `pypi`）；GitHub 仓库 Settings → Environments 建 `pypi`。
  没做之前 publish 步骤 403——可见失败，不是静默跳过。
- 守卫：`scripts/verify_wheel_contents.py`（CI + 发布前）重建 wheel 并断言知识包/bench/闸表/Windows 启动模板/入口点
  都在；`verify_server_json.py` 锁 `server.json` 的 pypi 条目与 `pyproject` 的 name/version；发布工作流断言
  pyproject 版本 == release tag。
- wheel **不含** `horosa-core-js`：它随离线 runtime payload 分发（manifest `artifacts.horosa_core_js_root`），
  `HOROSA_CORE_JS_ROOT` 可覆盖；源码树回退只在 checkout 里有效。
- 发布顺序（v0.38.0 A5，v0.40.0 补齐）：`preflight_release.py` 全绿（含上游 pin 在公开远端）→ tag → `publish_release.sh --draft --dispatch`
  （draft + 触发 `release-runtime.yml`：派生 Windows 半、双平台清单、真机矩阵）→ 提交 `server.json` 的 mcpb sha 回填（来自这一次 draft 构建）→
  `sync_windows_release.py --check --tag vX --draft` [OK] → `gh workflow run release-runtime.yml -f version=X -f publish=true -f run_matrix=true`
  （转公开；publish 前 `verify_matrix_digests.py` 比对三条 lane 装的 sha 与 draft 资产 digest（v0.38.1 R5）；
  GITHUB_TOKEN 产生的 published 事件**不**触发下游 workflow，completeness 由 publish job 显式 dispatch，publish-pypi 开通后同理）→
  `--check` 公开 latest → publish job 再 dispatch 一次 release 模式矩阵（真 https 下载）→ `uvx --from <wheel URL> horosa-skill --version` 烟测。
