# 客户端接入示例索引

每个客户端一条命令：`uv run horosa-skill setup --client <key>`（零安装：`uvx --from "<发布页 wheel URL>" horosa-skill setup --client <key>`）；
只看配置不落盘：`client config --format <key>`；体检本机已写的配置：`client check`。策略源是 [`skills/horosa-agent/SKILL.md`](../../../skills/horosa-agent/SKILL.md)。

| key | 客户端 | 配置落点 | 工具面缺省 | 示例 / 备注 |
| --- | --- | --- | --- | --- |
| `claude-code` | Claude Code | `claude mcp add`（scope local / project / user）或 `.mcp.json`；插件 `.claude-plugin/` | 全量 120 | [claude-code.md](./claude-code.md) |
| `claude-desktop` | Claude Desktop | `claude_desktop_config.json`（GUI 不继承 shell PATH → 绝对 `uv` 路径）或 `.mcpb` 一键包 | 全量 120 | [claude_desktop_config.json](./claude_desktop_config.json) |
| `codex` | Codex CLI | `~/.codex/config.toml` `[mcp_servers.horosa]`（含 startup / tool 超时与 env 根） | 精简 11 | [codex.md](./codex.md) · [codex-config.toml](./codex-config.toml) |
| `cursor` | Cursor | `~/.cursor/mcp.json` / 项目 `.cursor/mcp.json`；deep link | 精简 11 | `client config --format cursor` |
| `vscode` | VS Code（Copilot） | `.vscode/mcp.json` `servers` | 精简 11 | `client config --format vscode` |
| `gemini` | Gemini CLI | `~/.gemini/settings.json` / 项目 `.gemini/settings.json`（timeout 600000 ms） | 精简 11 | `client config --format gemini` |
| `windsurf` | Devin Desktop（原 Windsurf；key 保留兼容） | `~/.config/devin/mcp_config.json`（Windows `%APPDATA%\devin\`；项目 `.devin/mcp_config.json`）；旧 Cascade 文件存在则原位合并 | 精简 11 | `client config --format windsurf` |
| `cline` | Cline | `cline_mcp_settings.json`（timeout 600 s） | 精简 11 | `client config --format cline` |
| `zed` | Zed | `settings.json` `context_servers`（timeout 600 s） | 精简 11 | `client config --format zed` |
| — | OpenClaw（经 mcporter） | `client openclaw-setup --workspace …` | 全技法 | [openclaw-mcp.md](./openclaw-mcp.md) |
| — | Open WebUI / 任何 streamable-http 客户端 | `serve --transport streamable-http --token …` | 全量 120 | [openwebui-streamable-http.md](./openwebui-streamable-http.md) |
| — | claude.ai / ChatGPT 连接器 | 只接 OAuth：需要终结 OAuth 的 HTTPS 网关 | 同 HTTP | [remote-connectors-oauth-gateway.md](./remote-connectors-oauth-gateway.md) |

第三方事实（路径 / 超时 / 预算）的来源与核实日期记在 [`contracts/third_party_facts.json`](../../contracts/third_party_facts.json)。
