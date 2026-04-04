# Runtime Manifest Spec

Two manifest files are involved in offline distribution.

## Release Manifest

Used by `horosa-skill install --manifest-url ...`.

Required shape:

```json
{
  "version": "0.2.0",
  "platforms": {
    "darwin-arm64": {
      "url": "https://.../horosa-runtime-darwin-arm64.tar.gz",
      "sha256": "...",
      "archive_type": "tar.gz"
    },
    "win32-x64": {
      "url": "https://.../horosa-runtime-win32-x64.zip",
      "sha256": "...",
      "archive_type": "zip"
    }
  }
}
```

See [`runtime-manifest.example.json`](./runtime-manifest.example.json).

## Runtime Payload Manifest

Embedded inside each runtime archive as `runtime-manifest.json`.

Required and normalized fields:

```json
{
  "schema_version": 1,
  "version": "0.2.0",
  "platform": "darwin-arm64",
  "runtime_layout_version": 1,
  "export_registry_version": 6,
  "services": {
    "backend_url": "http://127.0.0.1:9999",
    "chart_url": "http://127.0.0.1:8899",
    "start_script": "Horosa-Web/start_horosa_local.sh",
    "stop_script": "Horosa-Web/stop_horosa_local.sh"
  },
  "runtimes": {
    "python": "runtime/mac/python/bin/python3",
    "java": "runtime/mac/java/bin/java"
  },
  "artifacts": {
    "horosa_web_root": "Horosa-Web",
    "astropy_root": "Horosa-Web/astropy",
    "flatlib_root": "Horosa-Web/flatlib-ctrad2/flatlib",
    "swefiles_root": "Horosa-Web/flatlib-ctrad2/flatlib/resources/swefiles",
    "boot_jar": "runtime/mac/bundle/astrostudyboot.jar"
  }
}
```

See [`runtime-payload-manifest.example.json`](./runtime-payload-manifest.example.json).

## Compatibility Notes

- Older payload manifests that only contain `version` are still accepted.
- Installation now normalizes the embedded payload manifest and writes the normalized JSON into the installed runtime.
- `doctor`, `serve`, and `stop` resolve runtime paths from the installed payload manifest instead of assuming only one layout.
- `runtimes.node` is optional for now. Add it only when a packaged headless JS runtime is actually bundled.
