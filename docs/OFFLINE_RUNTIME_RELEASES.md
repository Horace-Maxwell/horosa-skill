# Offline Runtime Releases

This repository is meant to stay lightweight in Git history while still supporting fully local runtime packaging.

Complete offline runtime payloads are published as GitHub Release assets, but the source inputs needed to build those payloads should live locally inside [`../vendor/runtime-source`](../vendor).

That local folder is allowed to exist on disk without being committed to the repository.

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
  `ephem` (kintaiyi), `pendulum` (kinjinkou). macOS's embedded Python already carries these; the
  Windows `runtime/windows/bundle/wheels` set MUST include them too or the chart service will fail to
  mount the ken endpoints.
- Java aggregation layer and boot jar
- Node runtime for headless JS calculation modules (统摄法 + ken-response → aiExport.js formatting)
- Swiss Ephemeris data and any other local astronomical assets
- `runtime-manifest.json`

## Maintainer Workflow

1. Refresh vendored runtime sources inside this repository when needed.
2. Build the platform runtime archive from the local `vendor/runtime-source` directory.
3. Upload the generated archive to GitHub Releases.
4. Generate a release manifest that points to those archives.
5. Publish the manifest URL for `horosa-skill install`.
6. Verify the release archives before upload.

> **Building the Windows archive** (which needs win32 wheels and native Windows verification) is a
> Windows-only step. A complete, self-contained runbook for a Windows agent (or a person) lives at
> [`WINDOWS_RELEASE_BUILD_PROMPT.md`](./WINDOWS_RELEASE_BUILD_PROMPT.md) — build, native ken/tongshefa
> verification, manifest+checksums over both platforms, and release finalization.

## Scripts In This Repo

- `horosa-skill/scripts/build_runtime_release.sh`
  Builds the macOS and Windows runtime archives, emits `runtime-manifest.json`, writes `SHA256SUMS.txt`, and runs archive verification.
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
- `horosa-skill/scripts/sync_vendored_runtime_sources.sh`
  Pulls the current required runtime subset from a local development tree into `vendor/runtime-source`. It can also ingest Windows preparation inputs from a separate local Windows source repo via `HOROSA_WINDOWS_SOURCE_ROOT`.

## Current Windows Reality

The repository now produces a real Windows runtime archive:

- embedded Java runtime
- embedded Python runtime
- embedded Node runtime
- local wheels unpacked into the payload (must include the ken deps: `bidict`, `numpy`,
  `kerykeion`, `ephem`, `pendulum`)
- ken engines under `Horosa-Web/vendor/{kinqimen,kintaiyi,kinjinkou}`
- `astrostudyboot.jar`
- `horosa-core-js`
- runtime manifest and startup scripts

`build_runtime_release_windows.py` bundles the three ken engines and patches the staged
`kentang/registry.py` mount so the chart service still boots when other (out-of-scope) ken
engines are absent; `start_horosa_local.ps1` puts `Horosa-Web/vendor` on `PYTHONPATH` so
`import kinqimen` / `kintaiyi` / `kinjinkou` resolve.

In this macOS development environment, Windows verification is structural rather than native-process execution. The release zip is built and checked for required contents here, and should still be validated on a real Windows machine before public release sign-off — in particular, confirm the chart service boots and `/qimen/pan` · `/taiyi/pan` · `/jinkou/pan` respond.

## Example Manifest

See [`runtime-manifest.example.json`](./runtime-manifest.example.json).

For the embedded payload manifest, see [`RUNTIME_MANIFEST_SPEC.md`](./RUNTIME_MANIFEST_SPEC.md).
