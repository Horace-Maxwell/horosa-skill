# Claude Code 接入 Horosa Skill

前置：已完成 `uv sync` 与 `uv run horosa-skill install`（离线 runtime）。

## 一条命令接入（v0.38.0 起推荐）

```bash
uv run horosa-skill setup --client claude-code                  # 探网 → 装 runtime → 注册 → doctor → 回读 → 真起一次 stdio
uv run horosa-skill setup --client claude-code --scope project  # 只写当前项目的 .mcp.json（默认：CWD 有 .mcp.json 就写它，否则 claude mcp add --scope user）
```

`claude` 不在 PATH 时不会替你猜路径：注册命令原样打印在 `steps.config.command`，复制执行即可；
失败包在 stderr（`step` / `code` / `config_untouched` / `retry_command`），退出码 2。

## 只生成注册命令（不落盘，stdio 直连）

让 CLI 生成带真实绝对路径的注册命令，复制执行即可：

```bash
uv run horosa-skill client config --format claude-code
```

输出里的 `command` 形如：

```bash
claude mcp add horosa -- uv run --directory /绝对路径/horosa-skill horosa-skill serve --transport stdio
```

stdio 模式无需常驻 `serve` 进程，Claude Code 启动会话时自动拉起（首次调用后端冷启动约 10–45 秒）。

## HTTP 变体（常驻服务）

```bash
uv run horosa-skill serve            # 默认 http://127.0.0.1:8765/mcp
claude mcp add horosa --transport http http://127.0.0.1:8765/mcp
```

## 精简工具面（可选）

小上下文场景可让 MCP 只暴露 11 个门面工具（含按名直呼的 `horosa_tool_run`）：

在注册命令的 env 中加 `HOROSA_MCP_COMPACT=1`（stdio 例：`claude mcp add horosa --env HOROSA_MCP_COMPACT=1 -- uv run …`）。

## 验证

注册后在 Claude Code 里问一句「用 horosa 起一张当前时间的奇门盘」；或本机先跑
`uv run horosa-skill selfcheck` 确认计算链路整体可用。
