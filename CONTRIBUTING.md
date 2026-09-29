# Contributing

Thanks for contributing to Horosa Skill.

## Scope

This repository is the public-facing distribution and runtime-packaging layer for Horosa/Xingque AI tooling. Contributions are most helpful when they improve one of these areas:

- CLI or MCP behavior
- schema quality and structured output stability
- local memory and artifact persistence
- runtime install and release tooling
- documentation, onboarding, and client integration examples

## Before Opening A PR

1. Keep changes scoped to this repository only.
2. Do not assume access to a sibling private development tree.
3. Prefer changes that preserve offline operation and local-first behavior.
4. Preserve structured JSON contracts unless versioned intentionally.

## License

By submitting a contribution to this repository, you agree that the change is
offered under the repository's current `GNU AGPL-3.0-only` license.

## Development

```bash
cd horosa-skill
uv sync
uv run python scripts/run_ci_gates.py     # the local mirror of CI (pytest + every verify_* gate CI runs) — the only sanctioned local gate
(cd horosa-core-js && npm test)           # JS goldens / selfcheck / hand-copy guard
```

- Do **not** run `scripts/verify_*.py` bare as "a quick check": several are real lanes with side effects
  (`verify_runtime_live.py` boots a runtime and drives every tool). `run_ci_gates.py` runs exactly what CI runs, in CI's shape.
- Live tests only run against an instance you name explicitly (`HOROSA_SERVER_ROOT` / `HOROSA_CHART_SERVER_ROOT`);
  they never probe the default `:9999` / `:8899` ports (those belong to the user's desktop app) — boot a vendored instance
  with `scripts/start_vendored_instance.sh`.
- Windows behaviour is verified on CI (`windows-smoke` + the release matrix), never by hand-porting paths on macOS.
- A change that fixes a pitfall ships with its lesson in the same PR: `docs/LESSONS.md` entry + the distilled rule in
  `AGENTS.md` + a machine guard that is proven to catch it (protocol v3, `AGENTS.md` §2). Doc-facing changes must keep
  `scripts/verify_docs_sync.py` green (counts, versions, links, `docs/DOC_MAP.md`, generated mirrors, third-party facts ledger).
- Releases are cut by the maintainer through the hosted pipeline (`docs/OPERATIONS.md` → Runtime Release Runbook);
  `preflight_release.py` needs the upstream Horosa-Public checkout and is not something a PR has to run.

## Runtime Packaging Changes

If your change affects offline runtime packaging:

1. update vendored runtime inputs under `vendor/runtime-source` only when truly necessary
2. keep release scripts self-contained
3. document manifest or layout changes in `docs/`

## Pull Request Expectations

- explain user-facing impact clearly
- mention contract, manifest, or packaging changes explicitly
- note any platform assumptions
- include verification steps when possible
