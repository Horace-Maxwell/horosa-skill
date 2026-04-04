# OpenClaw

OpenClaw docs support saved MCP server definitions with `stdio`, `sse`, and `streamable-http`.

## Streamable HTTP

Start Horosa Skill:

```bash
cd horosa-skill
uv sync
uv run horosa-skill serve
```

Register it:

```bash
openclaw mcp set horosa '{"url":"http://127.0.0.1:8765/mcp","transport":"streamable-http"}'
```

## Stdio

```bash
openclaw mcp set horosa '{"command":"uv","args":["run","--directory","<PATH_TO_REPO>/horosa-skill","horosa-skill","serve","--transport","stdio"],"cwd":"<PATH_TO_REPO>/horosa-skill"}'
```

