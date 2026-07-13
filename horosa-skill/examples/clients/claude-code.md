# Claude Code 接入 Horosa Skill

前置：已完成 `uv sync` 与 `uv run horosa-skill install`（离线 runtime）。

## 一条命令注册（推荐，stdio 直连）

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

小上下文场景可让 MCP 只暴露 9 个门面工具（含按名直呼的 `horosa_tool_run`）：

在注册命令的 env 中加 `HOROSA_MCP_COMPACT=1`（stdio 例：`claude mcp add horosa --env HOROSA_MCP_COMPACT=1 -- uv run …`）。

## 验证

注册后在 Claude Code 里问一句「用 horosa 起一张当前时间的奇门盘」；或本机先跑
`uv run horosa-skill selfcheck` 确认计算链路整体可用。
