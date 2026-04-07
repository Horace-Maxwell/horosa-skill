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
uv run pytest
```

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
