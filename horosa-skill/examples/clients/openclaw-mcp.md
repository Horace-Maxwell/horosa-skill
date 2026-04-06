# OpenClaw / mcporter

推荐优先使用 `stdio` 方式接入。对 OpenClaw / mcporter 这类本地 MCP 客户端，Horosa Skill 现在会在首次调用后保持离线 runtime 热启动，这样后续每次工具调用都不会再重新完整拉起 Java + Python runtime。

## 最短可用路径

### 1. 安装仓库依赖与离线 runtime

```bash
cd horosa-skill
uv sync
uv run horosa-skill install
uv run horosa-skill doctor
```

### 2. 直接生成当前仓库可用的 OpenClaw / mcporter 配置

如果你已经在 `horosa-skill` 目录里，最省心的方式是直接生成一份带当前绝对路径的配置：

```bash
uv run horosa-skill client openclaw-config --format mcporter
```

如果你想顺手写到某个文件里：

```bash
uv run horosa-skill client openclaw-config \
  --format mcporter \
  --write ~/.openclaw/workspace/config/mcporter.json
```

写完后还可以直接做一次最小联通检查：

```bash
uv run horosa-skill client openclaw-check --workspace ~/.openclaw/workspace
```

如果你要跑完整 `39` 工具检查：

```bash
uv run horosa-skill client openclaw-check --workspace ~/.openclaw/workspace --full
```

### 3. 手动粘贴配置时，使用下面这段 MCP 配置

把 `<ABSOLUTE_PATH_TO_REPO>` 替换成你的仓库绝对路径。

```json
{
  "mcpServers": {
    "horosa": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "<ABSOLUTE_PATH_TO_REPO>/horosa-skill",
        "horosa-skill",
        "serve",
        "--transport",
        "stdio"
      ],
      "cwd": "<ABSOLUTE_PATH_TO_REPO>/horosa-skill"
    }
  }
}
```

如果你是直接维护 `~/.openclaw/openclaw.json`，把它放进：

```json
{
  "mcp": {
    "servers": {
      "horosa": {
        "command": "uv",
        "args": [
          "run",
          "--directory",
          "<ABSOLUTE_PATH_TO_REPO>/horosa-skill",
          "horosa-skill",
          "serve",
          "--transport",
          "stdio"
        ],
        "cwd": "<ABSOLUTE_PATH_TO_REPO>/horosa-skill"
      }
    }
  }
}
```

### 4. 验证接入

```bash
mcporter list horosa --json
mcporter call horosa.horosa_knowledge_registry --output json
mcporter call horosa.horosa_astro_chart --args '{"date":"2026-04-04","time":"15:58:35","zone":"+08:00","lat":"26n04","lon":"119e19"}' --output json
```

## 为什么推荐 `stdio`

- OpenClaw / mcporter 复制粘贴配置就能接入，不需要额外开 HTTP 服务窗口。
- Horosa Skill 会自动拉起本机离线 runtime。
- 首次调用后 runtime 会保持热启动，后续工具调用明显更快。
- 需要彻底关闭本机 runtime 时，只要执行：

```bash
cd horosa-skill
uv run horosa-skill stop
```

## 可选：Streamable HTTP

如果你更喜欢显式启动一个本地 MCP 服务，也可以这样：

```bash
cd horosa-skill
uv sync
uv run horosa-skill install
uv run horosa-skill serve
```

然后在 OpenClaw / mcporter 里注册：

```json
{
  "mcpServers": {
    "horosa": {
      "url": "http://127.0.0.1:8765/mcp",
      "transport": "streamable-http"
    }
  }
}
```
