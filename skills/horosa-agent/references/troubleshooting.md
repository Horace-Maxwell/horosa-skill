# Troubleshooting (client-side)

> 读者：AI 客户端。何时读：结果异常、工具缺席、或用户质疑输出时。维护者级排障：[`AGENTS.md`](../../../AGENTS.md) §8。

## Reading failures

A failed tool returns `ok=False` with a structured `error.code` — it does not throw. Common codes:
`tool.invalid_payload` (often with `details.agent_recovery` → ask the user), `tool.internal_error`
(unexpected backend/format error), `tool.ken_compute_failed` (ken engine miss),
`js_engine.node_unavailable` / `js_engine.timeout` (Node layer). Relay the error; never conclude
“the technique is unavailable” from a single failure, and never invent an external dependency.

## Symptom table

| Symptom | Cause | Action |
| --- | --- | --- |
| qimen/taiyi/jinkou `source: null`, or chart disagrees with 星阙 desktop | Installed runtime is stale (pre-ken) — the JS layer fell back to its local scaffold | Re-install the current runtime release; for development set `HOROSA_CORE_JS_ROOT` to the repo's `horosa-core-js`. Not an algorithm failure. |
| `agent_guidance.required` / `details.agent_recovery` returned | Clarification gate (by design) | Ask the user with `prompt_to_user`; then `agent_confirmed_settings: true` (or `defaults_accepted: true`); never self-confirm |
| A section is missing from the export | Local tool/input issue or conditional section | Say the local run didn't return it; rerun `doctor` / `openclaw-check`; do NOT claim MongoDB/7897/Xingque-Desktop |
| Four pillars disagree with the hour-23 matrix | Runtime predates upstream v2.2.1 | User re-installs the runtime ([`late-zi.md`](./late-zi.md)) |
| No `horosa_*` tools in the agent session (`clientToolCount: 0`) | MCP server not attached to that workspace | Run openclaw setup/check below |
| Chinese text garbled on Windows | Console/codepage, not data | Check the JSON artifact; runtime launchers already force UTF-8 |

## Debug commands

```bash
uv run horosa-skill doctor
uv run horosa-skill tool list
uv run horosa-skill client openclaw-check --workspace <workspace>
uv run python scripts/run_full_self_check.py
```

OpenClaw onboarding:

```bash
uv run horosa-skill client openclaw-setup --workspace <the-agent-workspace>
uv run horosa-skill client openclaw-check --workspace <the-agent-workspace> --full
```

For named OpenClaw agents, `<workspace>` must be the workspace that agent actually uses, e.g.
`~/.openclaw/workspace-horosabot` — passing `~/.openclaw/workspace` while the agent runs in
`workspace-horosabot` verifies the wrong environment.

Direct tool call (diagnostic only — use the env block from the generated mcporter config):

```bash
uv run horosa-skill tool run liureng_gods --stdin   # then pass JSON on stdin
```

## Cross-platform notes

- macOS runtime: `~/.horosa/runtime/current`; Windows: `%LOCALAPPDATA%/Horosa/runtime/current`.
- Do not emit `/bin/zsh`, `export HOME=...`, or POSIX-only commands in Windows configs; do not emit
  `.cmd`-only commands in macOS configs.
- Prefer `horosa-skill client ...` config generators over hand-writing MCP JSON.
