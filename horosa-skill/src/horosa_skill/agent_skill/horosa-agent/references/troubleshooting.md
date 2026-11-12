# Troubleshooting (client-side)

> 读者：AI 客户端。何时读：结果异常、工具缺席、或用户质疑输出时。维护者级排障：[`AGENTS.md`](https://github.com/Horace-Maxwell/horosa-skill/blob/main/AGENTS.md) §8。

## Reading failures

A failed tool returns `ok: false` with a top-level `code`, `message` and `details.agent_recovery.kind` — it does not
throw. `kind` says who can fix it: `input` (ask the user / fix the payload — see SKILL.md §6), `retry_or_doctor` (retry
once, then suggest `horosa-skill doctor`), `transport` (cold start ≤ ~45 s: wait and retry once), `runtime` / `js_engine`
(install or repair the local engine), `environment` (PATH / encoding / ports), `decision_layer` (the optional cloud layer
was unavailable; the local path answered). Relay the error; never conclude "the technique is unavailable" from one
failure, and never invent an external dependency (MongoDB, port 7897, the 星阙 desktop app, a remote database).

## Symptom table

| Symptom | Cause | Action |
| --- | --- | --- |
| qimen/taiyi/jinkou `source: null`, or chart disagrees with 星阙 desktop | Installed runtime is stale (pre-ken) — the JS layer fell back to its local scaffold | Re-install the current runtime release; for development set `HOROSA_CORE_JS_ROOT` to the repo's `horosa-core-js`. Not an algorithm failure. |
| `agent_guidance.required` / `details.agent_recovery` returned | Clarification gate (by design) | Ask the user with `prompt_to_user`. Settings → retry with the answers + `agent_confirmed_settings: true` (or `defaults_accepted: true` when they accept defaults). Items with `fact: true` → put the user's answer in the payload; a flag never replaces them. Never self-confirm |
| `warnings` non-empty | Not necessarily a failure: interpreted inputs, unused arguments, a cut text with its follow-up call, a fallback engine | Read each line; only 降级 / 结果不完整 / 缺段 lines mean a part is missing — name it to the user; make the follow-up call for cut text |
| A section is missing from the export | Local tool/input issue or conditional section | Say the local run didn't return it; rerun `doctor` / `openclaw-check`; do NOT claim MongoDB/7897/Xingque-Desktop |
| Four pillars disagree with the hour-23 matrix | Runtime predates upstream v2.2.1 | User re-installs the runtime ([`late-zi.md`](./late-zi.md)) |
| No `horosa_*` tools in the agent session (`clientToolCount: 0`) | MCP server not attached to that workspace | Run openclaw setup/check below |
| Chinese text garbled on Windows | Console/codepage, not data | Check the JSON artifact; runtime launchers already force UTF-8 |
| A section or option the docs promise is missing (e.g. `southMonth`, [间爻] detail, 2033 leap month) | Installed runtime payload is older than this package — `doctor` reports `runtime:payload_outdated` / `freshness.export_registry_version.outdated` | `uv run horosa-skill upgrade` (stops its own services, swaps, restarts); never hand-compute the missing part |
| `runtime.starting` | Services still warming (cold start ≤ ~45 s; ~120 s under Windows-on-ARM emulation) | Retry the same call after `retry_after_seconds`; after 3 tries `horosa-skill runtime status` |
| `runtime.java_backend_unavailable` | Java aggregation layer down; chart service alive | Chart-family tools keep working; 农历/八字/紫微/六壬 retry after the cooldown; `doctor --explain` |
| `runtime.platform_unsupported` | Linux / Intel Mac have no offline payload | Gateway mode: point `HOROSA_SERVER_ROOT` / `HOROSA_CHART_SERVER_ROOT` at a supported machine (or Docker compose) |
| Windows: horosa never starts; `setup` stdio probe fails with `diagnosis.cause = windows_app_control_blocked` / `Failed to spawn: ... (os error 4551)` | Smart App Control blocked the per-environment `horosa-skill.exe` launcher uv generated (unsigned, no reputation); not a missing dependency | Re-run `setup --client <x> --entry module` (config becomes `... python -m horosa_skill serve`); never advise turning Smart App Control off |
| `runtime.path_not_ascii` / doctor `windows:runtime_root_not_ascii` | Windows runtime root contains non-ASCII characters (Chinese user name) — JDK 17 + Swiss Ephemeris cannot open it | `setx HOROSA_RUNTIME_ROOT C:\horosa`, reopen the terminal and the client, reinstall |
| `runtime.stop_refused_clients_attached` / `runtime.stop_refused_foreign` | Another MCP client session is attached, or the ports belong to the user's 星阙 desktop app | Do not add `--force` on your own; ask the user; `restart` / `upgrade` handle their own services |
| Devin Desktop (formerly Windsurf) shows no `horosa` tools | Cascade was removed in 2026-09; Devin Local reads `~/.config/devin/mcp_config.json`, not the old `~/.codeium/windsurf/` file | `horosa-skill setup --client windsurf` (writes the Devin path; merges in place if the legacy file exists); `client check --client windsurf` |
| Codex shows tools but parameter descriptions are gone | Codex ≥ 0.158 compacts any inputSchema over 5000 B | Not expected (largest schema is under 4 KB); report it — the repo's budget guard should have caught it |

## Debug commands

```bash
horosa-skill doctor            # machine-readable health report; --explain for prose
horosa-skill selfcheck         # live check of the installed runtime
horosa-skill tool list
horosa-skill client openclaw-check --workspace <workspace>
```

Inside a source checkout prefix them with `uv run`.

OpenClaw onboarding:

```bash
uv run horosa-skill client openclaw-setup --workspace <the-agent-workspace>
uv run horosa-skill client openclaw-check --workspace <the-agent-workspace> --full
```

For named OpenClaw agents, `<workspace>` must be the workspace that agent actually uses, e.g.
`~/.openclaw/workspace-horosabot` — passing `~/.openclaw/workspace` while the agent runs in
`workspace-horosabot` verifies the wrong environment.

Direct tool call (diagnostic only — use the env block from the generated client config):

```bash
horosa-skill tool run liureng_gods --input payload.json --output result.json
```

## Installing on a new machine

`horosa-skill setup --client <key>` installs the offline runtime, writes the client config, installs this skill
into the client's skills folder and test-starts the server (commands for a machine without `uv`: SKILL.md, last
section). Client keys: `claude-code`, `claude-desktop`, `cursor`, `vscode`, `codex`, `gemini`, `windsurf` (= Devin
Desktop, formerly Windsurf), `cline`, `zed`, `opencode`, `goose`, `kiro`, `copilot-cli`, `junie`, `qwen`, `kimi`,
`qoder`, `codebuddy`, `trae` (prints an import link), `amp`, `warp`, `droid`, `augment`, `deepcode`, `dsh`.
`horosa-skill client skill --client <key>` installs only this skill.

- `setup` can be re-run (upgrade, changed options); `--dry-run` shows the plan without side effects; `--surface
  full|compact` picks the tool surface. A failure is a stderr JSON with `step` / `code` / `config_untouched` /
  `retry_command` (exit 2).
- No github.com access: put `HOROSA_RUNTIME_MIRROR=<mirror prefix>` in front of the same commands, or
  `setup --archive <local runtime archive>` (see `docs/INSTALL_RESTRICTED_NETWORK.md` in the repo).
- Windows on ARM installs the x64 payload under emulation. Intel Macs and Linux have no offline payload: gateway mode
  (`HOROSA_SERVER_ROOT` / `HOROSA_CHART_SERVER_ROOT` pointing at a supported machine); `setup` then writes the config
  and skips the install.

## Cross-platform notes

- macOS runtime: `~/.horosa/runtime/current`; Windows: `%LOCALAPPDATA%/Horosa/runtime/current`.
- Do not emit `/bin/zsh`, `export HOME=...`, or POSIX-only commands in Windows configs; do not emit
  `.cmd`-only commands in macOS configs.
- Prefer `horosa-skill client ...` config generators over hand-writing MCP JSON.
