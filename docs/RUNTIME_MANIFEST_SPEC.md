# Runtime Manifest Spec

> 读者：维护者。何时读：读写 runtime-manifest / payload-manifest 格式时。

Two manifest files are involved in offline distribution.

## Release Manifest

Used by `horosa-skill install --manifest-url ...`.

Required shape:

```json
{
  "version": "<X.Y.Z — equals the release tag>",
  "platforms": {
    "darwin-arm64": {
      "url": "https://github.com/<owner>/<repo>/releases/download/v<X.Y.Z>/horosa-runtime-darwin-arm64-v<X.Y.Z>.tar.gz",
      "sha256": "...",
      "archive_type": "tar.gz",
      "size": 737084194,
      "min_os": "11.0"
    },
    "win32-x64": {
      "url": "https://github.com/<owner>/<repo>/releases/download/v<X.Y.Z>/horosa-runtime-win32-x64-v<X.Y.Z>.zip",
      "sha256": "...",
      "archive_type": "zip",
      "size": 713054877,
      "min_os": "10.0.17763"
    }
  }
}
```

A concrete instance is [`runtime-manifest.example.json`](./runtime-manifest.example.json) (its version is a `bump_version.py` site).

Optional per-platform fields (v0.38.0):

- `size` — byte count of the archive. Emitted by `generate_release_manifest.py`; the installer's disk precheck
  uses it (without it the check falls back to a flat 3 GiB), `verify_runtime_release.py` requires it to equal the
  real archive size, and `release-completeness.yml` compares it with the download's `Content-Length`.
- `min_os` — minimum host OS version (`10.0.17763` for a derived Windows payload). The installer compares it with
  `sys.getwindowsversion()` / `platform.mac_ver()` before downloading and refuses with `runtime.install_os_too_old`;
  the same floor inside the payload (`platform_requirements.min_os`) is checked again after extraction.
- Host fallback (v0.38.0 A4): a `win32-arm64` host installs the `win32-x64` entry under Windows 11 x64 emulation and the
  install result carries `platform_fallback: {requested, installed, mode}` plus a `runtime.platform_emulated` warning;
  `darwin-x64` never falls back (Rosetta does not run arm64 binaries). The table lives in `contracts/release_platforms.json`
  (`aliases`) and is mirrored by `manager.PLATFORM_FALLBACKS` (lockstep test).
- URLs are **tag-pinned** (`…/releases/download/v<version>/<asset>`, `--url-base`), so a manifest that points at
  another release's archive (the pin-forward failure) is visible from the manifest alone. The installer still
  fetches the manifest itself from `releases/latest/download/`.
- The platform key set of a release is `contracts/release_platforms.json` (`since`-gated); `verify_runtime_release.py
  --expect-platforms a,b` asserts it exactly.

See [`runtime-manifest.example.json`](./runtime-manifest.example.json).

## Runtime Payload Manifest

Embedded inside each runtime archive as `runtime-manifest.json`.

A payload derived from the darwin-arm64 seed (`build_runtime_release_windows.py --seed`, v0.38.0) additionally carries
`derived_from: {platform, version}` and `platform_requirements: {arch, min_os}`; the installer compares `min_os` with the
host and refuses with `runtime.install_os_too_old` when the host is older.

Required and normalized fields:

```json
{
  "schema_version": 1,
  "version": "0.40.0",
  "runtime_payload_version": "0.40.0",
  "platform": "win32-x64",
  "runtime_layout_version": 1,
  "export_registry_version": 15,
  "services": {
    "backend_url": "http://127.0.0.1:9999",
    "chart_url": "http://127.0.0.1:8899",
    "start_script": "Horosa-Web/start_horosa_local.ps1",
    "stop_script": "Horosa-Web/stop_horosa_local.ps1"
  },
  "runtimes": {
    "python": "runtime/windows/python/python.exe",
    "java": "runtime/windows/java/bin/java.exe",
    "node": "runtime/windows/node/node.exe"
  },
  "artifacts": {
    "horosa_web_root": "Horosa-Web",
    "astropy_root": "Horosa-Web/astropy",
    "flatlib_root": "Horosa-Web/flatlib-ctrad2/flatlib",
    "swefiles_root": "Horosa-Web/flatlib-ctrad2/flatlib/resources/swefiles",
    "boot_jar": "runtime/windows/bundle/astrostudyboot.jar",
    "horosa_core_js_root": "horosa-core-js"
  },
  "platform_requirements": {
    "arch": "x86_64",
    "min_os": "10.0.17763"
  },
  "derived_from": {
    "platform": "darwin-arm64",
    "version": "0.40.0"
  }
}
```

See [`runtime-payload-manifest.example.json`](./runtime-payload-manifest.example.json).

## Compatibility Notes

- Older payload manifests that only contain `version` are still accepted.
- Installation now normalizes the embedded payload manifest and writes the normalized JSON into the installed runtime.
- `doctor`, `serve`, and `stop` resolve runtime paths from the installed payload manifest instead of assuming only one layout.
- `runtimes.node` and `artifacts.horosa_core_js_root` are **required**: Node 22 is bundled in every payload and install
  verifies both paths exist (`manager._manifest_defaults` supplies the per-platform defaults; `verify_runtime_release.py` checks the archive).
- `runtime_payload_version` defaults to `version`; `platform_requirements` (`arch`, `min_os`) and `derived_from`
  (`platform`, `version` of the seed) are carried through unchanged from derived payloads (v0.38.0 A2): install checks `min_os`
  before download (release manifest) and again after extraction (payload manifest); `doctor` shows both blocks.
- The example above is a derived `win32-x64` payload; the darwin seed has the same keys with `runtime/mac/...` paths and no `derived_from`.
