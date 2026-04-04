# Open WebUI

Open WebUI docs say native MCP support is `Streamable HTTP` only.

1. Start Horosa Skill:

```bash
cd horosa-skill
uv sync
uv run horosa-skill serve
```

2. In Open WebUI:

- Open `Admin Settings -> External Tools`
- Click `Add Server`
- Set `Type` to `MCP (Streamable HTTP)`
- Set URL to `http://127.0.0.1:8765/mcp`

If your Open WebUI runs in Docker, use `http://host.docker.internal:8765/mcp`.

