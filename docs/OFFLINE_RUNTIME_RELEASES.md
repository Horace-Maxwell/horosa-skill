# Offline Runtime Releases

This lightweight repository does not commit the full Horosa runtime. Instead, complete offline runtime payloads are published as GitHub Release assets.

The source inputs needed to build those payloads are expected to live locally inside [`../vendor/runtime-source`](../vendor). That local folder may be excluded from Git history.

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
  Pulls the current required runtime subset from a local development tree into `vendor/runtime-source`.

## Example Manifest

See [`runtime-manifest.example.json`](./runtime-manifest.example.json).

For the embedded payload manifest, see [`RUNTIME_MANIFEST_SPEC.md`](./RUNTIME_MANIFEST_SPEC.md).
