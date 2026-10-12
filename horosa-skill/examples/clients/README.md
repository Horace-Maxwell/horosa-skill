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
| `opencode` | OpenCode | `~/.config/opencode/opencode.json` `mcp`（命令数组 + `environment`，timeout 600000 ms） | 精简 11 | `client config --format opencode` |
| `goose` | Goose | `~/.config/goose/config.yaml` `extensions`（Windows `%APPDATA%\Block\goose\config\`；timeout 600 s） | 精简 11 | `client config --format goose` |
| `kiro` | Kiro | `~/.kiro/settings/mcp.json`（CLI 另设 `mcp.initTimeout`） | 精简 11 | `client config --format kiro` |
| `copilot-cli` | GitHub Copilot CLI | `~/.copilot/mcp-config.json`（`tools: ["*"]`、timeout 600000 ms、env 带 HOME 与 runtime 根） | 精简 11 | `client config --format copilot-cli` |
| `junie` | JetBrains Junie | `~/.junie/mcp/mcp.json` | 精简 11 | `client config --format junie` |
| `qwen` | Qwen Code | `~/.qwen/settings.json`（`discoveryTimeoutMs` 120000、`timeout` 600000） | 精简 11 | `client config --format qwen` |
| `kimi` | Kimi Code CLI | `~/.kimi-code/mcp.json`（`startupTimeoutMs` / `toolTimeoutMs`） | 精简 11 | `client config --format kimi` |
| `qoder` | Qoder | `~/.qoder/settings.json`（timeout 600000） | 精简 11 | `client config --format qoder` |
| `codebuddy` | CodeBuddy | `~/.codebuddy/.mcp.json` / `mcp.json` / `~/.codebuddy.json` 中它实际读的那个 | 精简 11 | `client config --format codebuddy` |
| `trae` | TRAE | 无用户级文件：`trae://` 导入链接 + 粘贴 JSON（env 带 START/RUN_MCP_TIMEOUT_MS） | 精简 11 | `client config --format trae` |
| `amp` | Amp | `~/.config/amp/settings.json` 字面量键 `amp.mcpServers` | 精简 11 | `client config --format amp` |
| `warp` | Warp | `~/.warp/.mcp.json` | 精简 11 | `client config --format warp` |
| `droid` | Factory Droid | `~/.factory/mcp.json`（`connectTimeout` 120000、`timeout` 600000） | 精简 11 | `client config --format droid` |
| `augment` | Augment Auggie CLI | `~/.augment/settings.json` | 精简 11 | `client config --format augment` |
| `deepcode` | Deep Code | `~/.deepcode/settings.json`（严格 JSON；调用固定 60 s 上限） | 精简 11 | `client config --format deepcode` |
| `dsh` | DeepSeek Harness | 独立补丁 `~/.horosa/clients/dsh/horosa.cordis.yml`（`dsh web --patch`） | 精简 11 | `client config --format dsh` |
| — | OpenClaw（经 mcporter） | `client openclaw-setup --workspace …` | 全技法 | [openclaw-mcp.md](./openclaw-mcp.md) |
| — | Open WebUI / 任何 streamable-http 客户端 | `serve --transport streamable-http --token …` | 全量 120 | [openwebui-streamable-http.md](./openwebui-streamable-http.md) |
| — | claude.ai / ChatGPT 连接器 | 只接 OAuth：需要终结 OAuth 的 HTTPS 网关 | 同 HTTP | [remote-connectors-oauth-gateway.md](./remote-connectors-oauth-gateway.md) |

第三方事实（路径 / 超时 / 预算）的来源与核实日期记在 [`contracts/third_party_facts.json`](../../contracts/third_party_facts.json)。
