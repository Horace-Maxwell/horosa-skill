# Codex 接入 Horosa Skill

前置：已完成 `uv sync` 与 `uv run horosa-skill install`（离线 runtime，~730MB，断点续传）。

## 一条命令接入（v0.38.0 起推荐）

```bash
uv run horosa-skill setup --client codex      # 探网 → 装 runtime → 原位合并 ~/.codex/config.toml（只动 [mcp_servers.horosa]，先备份）→ doctor → 回读体检 → 真起一次 stdio
```

回读体检就是 `client check --client codex`：超时缺失、cwd 不存在、命令不在 PATH 都会当场报出来而不是留给 Codex「一堆报错」。

## 只生成配置片段（不落盘）

```bash
uv run horosa-skill client config --format codex
```

输出的 `toml_stdio` 已带真实绝对路径与全部硬约束字段，粘进 `~/.codex/config.toml` 即用。
或直接原位合并（**只动 `[mcp_servers.horosa]` 表**，其余内容与注释逐字保留，写前自动备份
`config.toml.horosa-bak`；目标不是合法 TOML 时会拒绝合并而不是覆盖）：

```bash
uv run horosa-skill client config --format codex --write ~/.codex/config.toml
```

> `codex mcp add horosa -- uv run …` 也能注册，但只写 command/args——超时、cwd、env 白名单
> 这些关键字段仍需手补，故推荐上面的生成器。

生成物形如：

```toml
[mcp_servers.horosa]
command = "uv"
args = ["run", "--directory", "/绝对路径/horosa-skill", "horosa-skill", "serve", "--transport", "stdio"]
cwd = "/绝对路径/horosa-skill"
startup_timeout_sec = 120
tool_timeout_sec = 600
# required = true   # 见「首轮工具缺席」

[mcp_servers.horosa.env]
# HOROSA_MCP_COMPACT = "1"
# HOROSA_TOOLSETS = "astro,cn"
```

## 为什么是这些字段（Codex 硬约束）

| 约束 | 事实 | 对策 |
| --- | --- | --- |
| 未知字段整段拒收 | `RawMcpServerConfig` 是 `deny_unknown_fields`：写错一个字段名，整个 server 配置被拒 | 只用生成器产出的字段；别手创字段 |
| 启动超时默认 30s | 首次冷启动（runtime 预热）常到 ~45s | `startup_timeout_sec = 120` |
| 工具超时默认 60s | 长盘（天星择日跨月扫描、多重回归年表）可超 | `tool_timeout_sec = 600` |
| env 白名单只有 11 个系统变量 | 你 shell 里的 `HOROSA_*` **不会**传给 server | 需要的 HOROSA_* 必须写进 `[mcp_servers.horosa.env]` |
| 首轮工具目录只等 1s | `mcp_optional_startup_grace_ms` 默认 1000：冷启动时第一轮对话可能看不到 horosa 工具，第二轮恢复 | 要首轮即见就解开 `required = true`（代价：server 起不来时 Codex 启动直接报错） |

## 工具面建议

Codex 没有工具搜索，106 个工具全量平铺会占相当的上下文。二选一：

- `HOROSA_MCP_COMPACT = "1"`：11 门面工具 + `horosa_tool_run` 直呼通道（106 技法全部可达）。
- `HOROSA_TOOLSETS = "astro,cn"`：按域裁剪平铺面（域名见 SKILL.md）。

也可用 Codex 侧 `enabled_tools` 只放行高频入口，例如：

```toml
enabled_tools = [
  "horosa_astro_chart", "horosa_cn_bazi_birth", "horosa_cn_ziwei_birth",
  "horosa_cn_qimen", "horosa_cn_liureng_gods", "horosa_cn_sixyao",
  "horosa_agent_guidance", "horosa_tool_run",
]
```

（保留 `horosa_tool_run` 与 `horosa_agent_guidance`，其余技法仍可经直呼通道到达。）

## 澄清闸：交互式 vs `codex exec`

- **交互式 TUI**：Horosa 的结果敏感设置澄清走 MCP elicitation——Codex 已支持并默认开启，会弹
  原生表单（表单含 decision/notes 实字段，不会被空表单自动接受机制吞掉）。
- **`codex exec`（无头）**：approval 被硬编码为 Never，elicitation 一律被拒 → 工具回落为结构化
  错误 `agent_guidance.required`，`details.agent_recovery.prompt_to_user` 带着该问用户的问题。
  **正确行为**：把问题原样作为最终输出交给用户，不猜、不自确认；拿到答案后带
  `agent_confirmed_settings: true` + `clarification_notes` 重试。
- 仓库级 `.agents/skills/horosa-agent/SKILL.md`（agentskills.io）向 Codex agent 声明了这套行为契约。

## 排障

**先跑一条**：`uv run horosa-skill client check --client codex`——它读的是磁盘上**真写着**的条目（Windows 上也能找到
`%USERPROFILE%\.codex\config.toml`），每个问题码对应下表一行；`setup --client codex` 写完会自动跑这一步。

| 症状 / `client check` 码 | 因 | 治 |
| --- | --- | --- |
| `codex_startup_timeout_missing` / `codex_tool_timeout_missing`（「一堆报错」，issue #18） | 超时没写，Codex 默认 10 s / 60 s | `setup --client codex` 或 `client config --format codex --write ~/.codex/config.toml` 原位补上 120 / 600 |
| `codex_cwd_missing` | `cwd` 指向不存在的目录（配置是别的机器生成的） | 删掉 `cwd`（uvx 形态不需要）或指向存在的包目录 |
| `command_not_on_path` | `command` 是裸 `uv`/`uvx`，Codex 不继承 shell PATH | 重跑生成器（v0.38.0 起写绝对路径） |
| `launcher_version_drift` | 配置钉的 wheel / git tag 版本 ≠ 本机包版本 | 重跑 `setup` 让 URL 跟上版本 |
| 首轮没有 horosa 工具，第二轮有 | 冷启动 > 1s grace（见上表） | 正常；或 `required = true` |
| 启动报 server 超时 | 首次预热超 30s 默认 | 确认 `startup_timeout_sec = 120` 在场 |
| `HOROSA_*` 设了没生效 | Codex env 白名单 | 写进 `[mcp_servers.horosa.env]` |
| 整段配置像没读到 | 字段名写错（deny_unknown_fields） | 与生成器输出逐字段对照 |
| 工具报 `agent_guidance.required` | 澄清闸（设计如此） | 按 `agent_recovery.prompt_to_user` 问用户后重试 |
| 长盘超时 | 默认 60s 工具超时 | 确认 `tool_timeout_sec = 600` 在场 |

维护者真机清单（本机装有 codex CLI 时逐项过）：冷启动首轮/第二轮工具可见性；elicitation 表单
弹出与提交；`codex exec` 下 `agent_guidance.required` 文本回落；`--write` 合并后 Codex 正常读取；
`enabled_tools` 生效。

## Windows

- 用 `setup --client codex`（或 `client config --format codex --write`）生成：`command` 是绝对路径的 `uv.exe`
  （Codex 不继承 shell PATH），`args` / `cwd` 里的反斜杠已按 TOML 基本字符串转义——裸插值会让整个 `config.toml`
  解析失败（`Unescaped '\'`），这是 Windows 独有、mac 上永远绿的坑。
- 首轮对话可能看不到 horosa（冷启动只等 1 s）：正常，第二轮即恢复；要首轮即见解开 `required = true`。
- 配置在 `%USERPROFILE%\.codex\config.toml`；`client check --client codex` 在 Windows 也按这个位置找。
- 第一次调用会起本机 Java / Python 服务（v0.38.0 起只绑 127.0.0.1，正常不再弹防火墙）；安全软件拦 JDK 回环见
  `AGENTS.md` §8 症状表与 `doctor` 的 `java_diagnostics`。
- `codex exec`（无头）：elicitation 一律被拒，工具回落 `agent_guidance.required`。agent 把 `prompt_to_user` 原样作为
  最终输出；**只有用户明说接受默认时才带 `defaults_accepted: true`**，绝不自确认（`.agents/skills/horosa-agent/SKILL.md`
  的「Shell-only agents」一节是 Codex 读到的契约）。

## HTTP 变体

先常驻 `uv run horosa-skill serve`，再用生成物里的 `toml_http`（`url = "http://127.0.0.1:8765/mcp"`，
同样带超时字段）。
