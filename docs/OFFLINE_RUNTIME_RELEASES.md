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
- Java aggregation layer and boot jar
- Node runtime for headless JS calculation modules
- Swiss Ephemeris data and any other local astronomical assets
- `runtime-manifest.json`

## Maintainer Workflow

1. Refresh vendored runtime sources inside this repository when needed.
2. Build the platform runtime archive from the local `vendor/runtime-source` directory.
3. Upload the generated archive to GitHub Releases.
4. Generate a release manifest that points to those archives.
5. Publish the manifest URL for `horosa-skill install`.

## Scripts In This Repo

- `horosa-skill/scripts/build_runtime_release.sh`
  Builds a macOS runtime archive directly from vendored sources in this repository.
- `horosa-skill/scripts/package_runtime_payload.sh`
  Assembles the runtime payload tarball from `vendor/runtime-source`.
- `horosa-skill/scripts/build_runtime_release_windows.ps1`
  Packages a staged Windows `runtime-payload/` directory into a release zip.
- `horosa-skill/scripts/generate_release_manifest.py`
  Generates a manifest JSON containing version, URLs, checksums, and archive type.
- `horosa-skill/scripts/scaffold_windows_runtime.py`
  Creates a Windows runtime directory skeleton with manifest and PowerShell entrypoints.
- `horosa-skill/scripts/sync_vendored_runtime_sources.sh`
  Pulls the current required runtime subset from a local development tree into `vendor/runtime-source`. It can also ingest Windows preparation inputs from a separate local Windows source repo via `HOROSA_WINDOWS_SOURCE_ROOT`.

## Current Windows Reality

The current Windows source chain is now useful for `horosa-skill`, but it is still a preparation chain rather than a final payload archive.

What it gives us now:

- `prepareruntime/Prepare_Runtime_Windows.ps1`
- `runtime/windows/bundle/runtime.manifest.json`
- offline Python wheels
- URL templates for Java, Python, and `astrostudyboot.jar`

What still must exist before a true `horosa-skill` Windows release is complete:

- actual `runtime/windows/java`
- actual `runtime/windows/python`
- actual `runtime/windows/bundle/astrostudyboot.jar`
- frontend build output in the final runtime payload
- packaged Node runtime for the future headless JS layer

## Example Manifest

See [`runtime-manifest.example.json`](./runtime-manifest.example.json).

For the embedded payload manifest, see [`RUNTIME_MANIFEST_SPEC.md`](./RUNTIME_MANIFEST_SPEC.md).
