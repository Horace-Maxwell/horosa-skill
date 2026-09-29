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

Current vendored inputs (`horosa-skill/scripts/sync_vendored_runtime_sources.sh` pulls them from the read-only
Horosa-Public checkout named by `HOROSA_SOURCE_ROOT`; what was pulled is recorded in
`horosa-skill/contracts/upstream_provenance.json`):

- `Horosa-Web/start_horosa_local.sh` / `stop_horosa_local.sh` — launcher pair (the runtime manager patches the mac launcher for headless use)
- `Horosa-Web/scripts/` — `repairEmbeddedPythonRuntime.py` and friends
- `Horosa-Web/astrostudyui/{dist-file,scripts,src}` — built frontend, `warmHorosaRuntime.js`, and the `src/utils` the
  headless layer mirrors (`aiExport.js`, `localNongliAdapter.js`, …)
- `Horosa-Web/astropy`, `Horosa-Web/flatlib-ctrad2` — the Python chart service and its ephemeris library
- `Horosa-Web/vendor/{kinqimen,kintaiyi,kinjinkou,kinwangji,kinwuzhao,taixuanshifa,jingjue,shenyishu,kinastro}` — the ken / 神数
  engines (MIT; obligations in `AGENTS.md` §11)
- `runtime/mac/{python,java,bundle/astrostudyboot.jar}` — the embedded runtimes and boot jar of the **darwin-arm64 seed**

## Windows Note

There are no Windows-specific inputs here any more. Since v0.38.0 the `win32-x64` archive is **derived from the darwin-arm64
seed** on GitHub's `windows-latest` runner (`release-runtime.yml` → `build_runtime_release_windows.py --seed …`): the
platform-independent tree comes from the seed, JDK 17 / Node 22 / embedded CPython 3.12 come from the pins in
`horosa-skill/contracts/runtime_toolchain.json`, and the Python dependency set is
`horosa-skill/contracts/runtime_python_lock.json` (seed-derived; pyswisseph / sxtwl are built from sdist on the runner).
The Windows build-box flow in `docs/WINDOWS_RELEASE_BUILD_PROMPT.md` is a fallback for when the hosted path is down.

## Why This Exists

- Local work should not require hunting through sibling folders.
- Maintainers can refresh local runtime sources from the development tree when needed.
- `runtime-source/` can remain intentionally outside Git history if payloads are too large for normal GitHub repository storage.
- Runtime packaging scripts in `horosa-skill/scripts/` are expected to read from this directory.
