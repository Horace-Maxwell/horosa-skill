# Horosa Skill

`horosa-skill` turns the existing Horosa calculation services and 星阙 AI 导出设置 into a GitHub-first local skill distribution:

- offline runtime installer and doctor commands
- MCP server for AI clients
- JSON-first CLI for direct testing
- machine-readable 星阙 AI 导出 registry
- AI 导出文本快照 -> structured JSON parser
- Local SQLite memory plus JSON artifacts
- Streamable HTTP mode for Open WebUI / OpenClaw

This subproject intentionally ships only the skill layer. It does not bundle the original Horosa desktop/runtime source tree.

## Quick Start

```bash
cd horosa-skill
uv sync
uv run horosa-skill install --archive /path/to/runtime-payload.tar.gz
uv run horosa-skill doctor
uv run horosa-skill serve
```

That starts a local Streamable HTTP MCP server on `http://127.0.0.1:8765/mcp`.

For stdio clients such as Claude Desktop, run:

```bash
cd horosa-skill
uv run horosa-skill serve --transport stdio
```

## CLI Examples

List tools:

```bash
uv run horosa-skill tool list
```

Install or refresh the offline runtime:

```bash
uv run horosa-skill install --manifest-url https://example.com/runtime-manifest.json
```

Check runtime health:

```bash
uv run horosa-skill doctor
```

Stop a managed runtime:

```bash
uv run horosa-skill stop
```

Run a tool from stdin:

```bash
echo '{"date":"1990-01-01","time":"12:00","zone":"8","lat":"31n14","lon":"121e28"}' \
  | uv run horosa-skill tool run chart --stdin
```

Dump the AI export registry:

```bash
uv run horosa-skill export registry --technique qimen
```

Convert exported snapshot text into structured JSON:

```bash
echo '{
  "technique":"qimen",
  "content":"[起盘信息]\n参数\n\n[右侧栏目]\n忽略\n\n[八宫]\n八宫内容\n\n[演卦]\n演卦内容",
  "selected_sections":["起盘信息","八宫详解","奇门演卦"]
}' | uv run horosa-skill export parse --stdin
```

Run the dispatcher:

```bash
echo '{
  "query":"请先起本命盘并给出主运势方向",
  "birth":{"date":"1990-01-01","time":"12:00","zone":"8","lat":"31n14","lon":"121e28"},
  "save_result": true
}' | uv run horosa-skill dispatch --stdin
```

Query local memory:

```bash
uv run horosa-skill memory query --tool chart --limit 5
```

## AI Client Setup

Example config snippets live in `examples/clients/`.

- Claude Desktop: `examples/clients/claude_desktop_config.json`
- Codex: `examples/clients/codex-config.toml`
- Open WebUI: `examples/clients/openwebui-streamable-http.md`
- OpenClaw: `examples/clients/openclaw-mcp.md`

Maintainer docs for runtime packaging and repository layout live one level up under `../docs/`.
Vendored offline runtime sources live under `../vendor/runtime-source`.

## Environment

Copy `.env.example` if you want to override defaults:

```bash
cp .env.example .env
```

Key settings:

- `HOROSA_SERVER_ROOT`
- `HOROSA_CHART_SERVER_ROOT`
- `HOROSA_SKILL_DB_PATH`
- `HOROSA_SKILL_OUTPUT_DIR`
- `HOROSA_RUNTIME_ROOT`
- `HOROSA_RUNTIME_MANIFEST_URL`
- `HOROSA_RUNTIME_PLATFORM`
- `HOROSA_RUNTIME_START_TIMEOUT_SECONDS`
- `HOROSA_SKILL_HOST`
- `HOROSA_SKILL_PORT`

## Docker

```bash
docker compose up --build
```

## Current v1 Tool Coverage

- `export_registry`, `export_parse`
- `chart`, `chart13`
- `solarreturn`, `lunarreturn`, `solararc`, `givenyear`, `profection`, `pd`, `pdchart`, `zr`, `relative`, `india_chart`
- `ziwei_birth`, `ziwei_rules`
- `bazi_birth`, `bazi_direct`
- `liureng_gods`, `liureng_runyear`
- `jieqi_year`, `nongli_time`
- `gua_desc`, `gua_meiyi`

The current source of truth for the AI export registry is the main 星阙 app file `Horosa-Web/astrostudyui/src/utils/aiExport.js`. This lightweight repo vendors the export schema and parsing behavior so users do not need the full 星阙 app just to consume the AI export protocol.

The offline runtime packaging flow is prepared through `scripts/sync_vendored_runtime_sources.sh`, `scripts/package_runtime_payload.sh`, `scripts/build_runtime_release.sh`, `scripts/build_runtime_release_windows.ps1`, `scripts/scaffold_windows_runtime.py`, and `scripts/generate_release_manifest.py`, so GitHub Releases can host the full Java/Python + ephemeris payload while this repository stays self-contained.
