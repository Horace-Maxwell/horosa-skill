# Vendored Runtime Sources

This directory exists so the project folder on disk can stay self-contained at release time.

## runtime-source/

`runtime-source/` stores the source assets required to package the offline Horosa runtime without reaching outside this project folder.

Current vendored inputs include:

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

## Why This Exists

- Working locally should not require hunting through sibling folders.
- Maintainers can refresh local runtime sources from the development tree when needed.
- `runtime-source/` may be intentionally excluded from Git history if the local runtime payload is too large for normal GitHub repository storage.
- Runtime packaging scripts in `horosa-skill/scripts/` are expected to read from this directory.
