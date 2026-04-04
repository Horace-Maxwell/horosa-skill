# Vendored Runtime Sources

This directory exists so the local project folder can stay self-contained for offline runtime packaging.

## The Important Boundary

- `vendor/runtime-source/` is for local packaging inputs
- it may exist on disk without being committed to GitHub
- build scripts should still work from this folder alone
- it is not the final install location used by end users
- it is not a substitute for GitHub Release runtime assets

That means the maintainer should not need to go back to another sibling project folder when producing runtime payloads.

## runtime-source/

`runtime-source/` stores the source assets required to package the offline Horosa runtime without reaching outside this project folder.

Current vendored inputs can include:

- `Horosa-Web/start_horosa_local.sh`
- `Horosa-Web/stop_horosa_local.sh`
- `Horosa-Web/scripts/repairEmbeddedPythonRuntime.py`
- `Horosa-Web/astrostudyui/dist-file`
- `Horosa-Web/astrostudyui/scripts/warmHorosaRuntime.js`
- `Horosa-Web/astrostudyui/src/utils/aiExport.js`
- `Horosa-Web/astropy`
- `Horosa-Web/flatlib-ctrad2`
- `runtime/mac/python`
- `runtime/mac/java`
- `runtime/mac/bundle/astrostudyboot.jar`
- `runtime/windows/bundle/runtime.manifest.json`
- `runtime/windows/bundle/wheels`
- `runtime/windows/bundle/*.url.txt`
- `prepareruntime/Prepare_Runtime_Windows.ps1`
- `prepareruntime/Prepare_Runtime_Windows.bat`

## Windows-Specific Note

The Windows source repository currently gives this project two important things:

- a Windows runtime preparation flow
- an offline wheel bundle and runtime manifest template

That is enough to keep the local project folder self-contained for Windows runtime preparation inputs.

It is not the same thing as a fully materialized Windows runtime payload.

The final Windows runtime payload still needs the real packaged Java, Python, backend jar, frontend build output, and eventually Node runtime to be materialized into the release archive layout.

## Why This Exists

- Local work should not require hunting through sibling folders.
- Maintainers can refresh local runtime sources from the development tree when needed.
- `runtime-source/` can remain intentionally outside Git history if payloads are too large for normal GitHub repository storage.
- Runtime packaging scripts in `horosa-skill/scripts/` are expected to read from this directory.
