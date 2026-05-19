# OpenClaw / mcporter

推荐优先使用 `stdio` 方式接入。对 OpenClaw / mcporter 这类本地 MCP 客户端，Horosa Skill 现在会在首次调用后保持离线 runtime 热启动，这样后续每次工具调用都不会再重新完整拉起 Java + Python runtime。

## 最短可用路径

如果你希望它自动完成安装、隔离 HOME、写入 mcporter 配置、预热 runtime、并跑 smoke check，优先用一条命令：

```bash
uv run horosa-skill client openclaw-setup --workspace ~/.openclaw/workspace
```

这个命令会把 OpenClaw 使用的 runtime 放在隔离 HOME 下，并同时写入两份配置：

- `~/.openclaw/workspace/config/mcporter.json`：给 `mcporter` / `openclaw-check` 使用。
- `~/.openclaw/openclaw.json` 中的 `mcp.servers.horosa`：给 OpenClaw agent 原生 MCP 挂载使用。

写入后请重启 OpenClaw 或开启新的 agent session，让 OpenClaw 重新加载 `openclaw.json`。后续排障时，请优先用：

```bash
uv run horosa-skill client openclaw-check --workspace ~/.openclaw/workspace
```

不要只看默认 `uv run horosa-skill doctor`，因为默认 doctor 检查的是当前 shell 的 `HOME` / `HOROSA_RUNTIME_ROOT`，不一定等于 OpenClaw 配置里的隔离 HOME。

如果你使用的是具名 Agent，例如 `horosabot`，请确认它实际使用哪个 workspace。OpenClaw trace 里通常会出现类似：

```json
{
  "workspaceDir": "/Users/you/.openclaw/workspace-horosabot",
  "clientToolCount": 47
}
```

这种情况下 setup / check 都要指向同一个 workspace：

```bash
uv run horosa-skill client openclaw-setup --workspace ~/.openclaw/workspace-horosabot
uv run horosa-skill client openclaw-check --workspace ~/.openclaw/workspace-horosabot --full
```

如果 trace 显示 `clientToolCount: 0`，但 `openclaw mcp list` 能看到 `horosa`，或真实对话里已经出现并能调用 `horosa__...` 工具，这个字段就是旧 trajectory 的统计噪音，不能当作未挂载依据。此时只需要重启 OpenClaw / 开新 session 让统计刷新。只有当 `openclaw mcp list`、真实工具列表和 `openclaw-check` 都看不到 Horosa 时，才按未挂载处理。无论哪种情况，都不要让模型退回 shell 手算或无 env 的 CLI 调用。

如果 `openclaw-check --full` 通过，但 `openclaw mcp list` 仍提示 `No MCP servers configured in ~/.openclaw/openclaw.json`，说明只写了 workspace 的 mcporter 配置，没有写 OpenClaw 原生配置。重新运行：

```bash
uv run horosa-skill client openclaw-setup --workspace ~/.openclaw/workspace
```

然后重启 OpenClaw 或开启新会话。

## Agent 调用纪律

OpenClaw 里如果同时有 `Exec` / shell 工具和 Horosa MCP 工具，必须优先调用 Horosa MCP。不要让 Agent 用 Python、Shell、Web Search 或手写干支公式来“自己算”星阙技法。

同时不要在用户缺少关键设置时直接调用。先调用：

```text
horosa_agent_guidance
```

例如：

```json
{"tool_name":"liureng_gods","intent":"当前时间起大六壬"}
```

它会告诉 Agent 哪些字段必须问、哪些默认值可以在用户同意后使用。缺少地点、性别、宫制、黄道体系、起局方式、贵人体系、六爻爻线、金口诀地分、目标年份或报告格式时，都应该先问用户给选项。

运行时也会强制执行：计算工具和 `horosa_dispatch` 如果没有 `agent_confirmed_settings: true` 或 `defaults_accepted: true`，会返回 `agent_guidance.required`，不会继续排盘。用户确认后请在 payload 中写入：

```json
{
  "agent_confirmed_settings": true,
  "clarification_notes": "用户确认使用当前时间、当前位置、星阙默认贵人体系"
}
```

如果返回中包含 `details.agent_recovery.prompt_to_user`，OpenClaw / Agent 必须停止继续调用，并把这段问题发给用户确认；不能通过换工具、手写代码或自行补默认值绕过。

典型映射：

- “用当前时间起一个大六壬盘” -> `horosa_cn_liureng_gods`
- “起奇门盘” -> `horosa_cn_qimen`
- “三式合一” -> `horosa_cn_sanshiunited`
- “生成报告 / PDF / DOCX” -> 先调用技法工具，再调用 `horosa_report_template` / `horosa_report_render`

如果 Agent 自己写脚本算大六壬，结果会绕过 Horosa 的真太阳时、星阙默认贵人体系、runtime parity、memory 和 report，因此不能作为正式结果。大六壬默认贵人体系为 `guirengType=2` / `星占法贵人`；只有用户明确要求时才切换到 `六壬法贵人` 或 `遁甲法贵人`。

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
uv run horosa-skill client openclaw-setup --workspace ~/.openclaw/workspace
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

## 常见提示与误报

- 如果默认 `uv run horosa-skill doctor` 显示 `installed=false`，但 `openclaw-check` 是 `ok=true`，通常是因为 OpenClaw 使用了隔离 HOME。以 `openclaw-check` 的结果为准，或用同一组 `HOROSA_RUNTIME_ROOT` / `HOROSA_SKILL_DATA_DIR` 运行 doctor。
- 如果 agent 用“最小参数”直接试跑奇门 / 太乙 / 六爻并触发 `/nongli/time` 的 `200001 param error`，先让它调用 `horosa_agent_guidance` 补问日期、时间、时区、经纬度和默认设置。`v0.5.12` 起也会自动对 Java 日期接口重试星阙兼容 payload，避免把格式问题误判成算法不可用。
- 如果 full check 偶发出现 `No JSON content was found`，请升级到 `0.5.12` 或更新 main；新版本会从 mcporter/stdio 混合输出里提取第一个完整 JSON，并且会在未确认关键设置时返回清晰的 `agent_guidance.required` 提示。
- 如果 `openclaw-check` 或 agent session 长时间没有 JSON 输出，请升级到 `0.5.12` 或更新 main；新版会给 mcporter subprocess 加超时，并返回 `client.command_timeout` 诊断，而不是无限挂住。
- 如果 release runtime 外层版本和内部 `runtime-payload/runtime-manifest.json` 不一致，请使用 `v0.5.12` 或更新后的 release；构建验证现在会拒绝这种 stale embedded manifest。
- 如果 OpenClaw gateway 报 `PATH missing` 或其他插件 manifest warning，只要 `horosa-skill client openclaw-check` 是 `ok=true`，这类 warning 通常不是 Horosa MCP 的阻塞项。

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
