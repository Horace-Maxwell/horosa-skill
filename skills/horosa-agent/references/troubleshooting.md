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
| A section or option the docs promise is missing (e.g. `southMonth`, [间爻] detail, 2033 leap month) | Installed runtime payload is older than this package — `doctor` reports `runtime:payload_outdated` / `freshness.export_registry_version.outdated` | `uv run horosa-skill upgrade` (stops its own services, swaps, restarts); never hand-compute the missing part |
| `runtime.starting` | Services still warming (cold start ≤ ~45 s; ~120 s under Windows-on-ARM emulation) | Retry the same call after `retry_after_seconds`; after 3 tries `horosa-skill runtime status` |
| `runtime.java_backend_unavailable` | Java aggregation layer down; chart service alive | Chart-family tools keep working; 农历/八字/紫微/六壬 retry after the cooldown; `doctor --explain` |
| `runtime.platform_unsupported` | Linux / Intel Mac have no offline payload | Gateway mode: point `HOROSA_SERVER_ROOT` / `HOROSA_CHART_SERVER_ROOT` at a supported machine (or Docker compose) |
| `runtime.path_not_ascii` / doctor `windows:runtime_root_not_ascii` | Windows runtime root contains non-ASCII characters (Chinese user name) — JDK 17 + Swiss Ephemeris cannot open it | `setx HOROSA_RUNTIME_ROOT C:\horosa`, reopen the terminal and the client, reinstall |
| `runtime.stop_refused_clients_attached` / `runtime.stop_refused_foreign` | Another MCP client session is attached, or the ports belong to the user's 星阙 desktop app | Do not add `--force` on your own; ask the user; `restart` / `upgrade` handle their own services |
| Devin Desktop (formerly Windsurf) shows no `horosa` tools | Cascade was removed in 2026-09; Devin Local reads `~/.config/devin/mcp_config.json`, not the old `~/.codeium/windsurf/` file | `horosa-skill setup --client windsurf` (writes the Devin path; merges in place if the legacy file exists); `client check --client windsurf` |
| Codex shows tools but parameter descriptions are gone | Codex ≥ 0.158 compacts any inputSchema over 5000 B | Not expected (largest schema is under 4 KB); report it — the repo's budget guard should have caught it |

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
