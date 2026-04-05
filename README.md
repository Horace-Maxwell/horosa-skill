**简体中文** | [English](./README_EN.md)

<div align="center">
  <h1>Horosa Skill</h1>
  <p><strong>把星阙 / Horosa 变成任何 AI 都能本地调用的离线玄学能力层。</strong></p>
  <p>下载仓库，安装一次离线 runtime，然后让 Claude、Codex、Open WebUI、OpenClaw 等 AI 在你的机器上直接调用真实算法、读取完整 AI 导出协议、输出稳定结构化结果，并把每次分析沉淀为可检索的本地记录。</p>

  <p>
    <a href="https://github.com/Horace-Maxwell/horosa-skill">
      <img src="https://img.shields.io/badge/GitHub-Repository-111827?style=for-the-badge&logo=github" alt="Repository" />
    </a>
    <a href="https://github.com/Horace-Maxwell/horosa-skill/releases">
      <img src="https://img.shields.io/badge/GitHub-Releases-1d4ed8?style=for-the-badge&logo=github" alt="Releases" />
    </a>
    <a href="./README_EN.md">
      <img src="https://img.shields.io/badge/Read%20in-English-0f766e?style=for-the-badge" alt="Read in English" />
    </a>
  </p>

  <p>
    <img src="https://img.shields.io/github/stars/Horace-Maxwell/horosa-skill?style=for-the-badge" alt="GitHub stars" />
    <img src="https://img.shields.io/github/v/release/Horace-Maxwell/horosa-skill?display_name=tag&style=for-the-badge" alt="Release" />
    <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows-0f766e?style=for-the-badge" alt="Platforms" />
    <img src="https://img.shields.io/badge/runtime-offline%20first-111827?style=for-the-badge" alt="Offline runtime" />
    <img src="https://img.shields.io/badge/MCP-ready-111827?style=for-the-badge" alt="MCP ready" />
    <img src="https://img.shields.io/badge/storage-SQLite%20%2B%20JSON-111827?style=for-the-badge" alt="SQLite and JSON" />
  </p>
</div>

## 项目定位

星阙本身已经有完整的本地算法、星历、导出设置和多技法体系。`Horosa Skill` 做的不是“再造一个简化版占算器”，而是把这些能力整理成一个适合 GitHub 分发、适合 AI 调用、适合长期本地管理的产品化接口层。

它解决的是五件事：

- 让用户从 GitHub 直接获取项目，并通过 GitHub Releases 安装完整离线 runtime。
- 让 AI 通过 `MCP` 或 `JSON-first CLI` 调用真正的星阙方法，而不是调用一层松散 prompt。
- 让每个技法的输出都变成高机器可读、稳定 section 化的“星阙 AI 导出完全体”文档。
- 让每次工具调用、用户问题、AI 最终回答、结构化摘要都落到本地，可回看、可检索、可复用。
- 让仓库保持轻量、清晰、可维护，而不是把大体积 runtime 和开发缓存全部塞进 Git 历史。

如果你的目标是：

- “别人 clone 这个仓库后，就能让自己的 AI 在本机直接调用星阙”
- “调用结果不是杂乱文本，而是稳定 JSON + 星阙式导出快照”
- “每次问卜、起盘、推运都能自动写成本地知识记录”

这个仓库就是围绕这个目标设计的。

## 现在它已经能做什么

### 一句话能力总览

| 能力层 | 当前已经实现的内容 | 对使用者意味着什么 |
| --- | --- | --- |
| 离线 runtime | 通过 GitHub Releases 安装 macOS / Windows 完整 runtime | 安装后可断网运行，不依赖远程算法服务 |
| AI 调用接口 | `MCP server` + `JSON-first CLI` + `ask / dispatch` | Claude、Codex、Open WebUI、OpenClaw 都能接 |
| 技法执行 | 37 个可调用工具，覆盖星盘、推运、术数、导出协议 | 不是 demo，而是可直接使用的多技法本地能力面 |
| 输出协议 | 每个技法返回统一 envelope，并附带 `export_snapshot` / `export_format` | 机器和人都能稳定消费，不需要猜字段 |
| 数据管理 | SQLite + JSON artifacts + run manifest + AI answer write-back | 一次调用就是一条可追溯记录 |
| 发布策略 | 轻仓库 + 重 Release | GitHub 页面专业、清楚，不拖慢协作 |

### 当前可直接调用的技法与工具

| 领域 | 当前可用方法 |
| --- | --- |
| 导出协议与调度 | `export_registry`、`export_parse`、`horosa_dispatch` |
| 核心星盘 | `chart`、`chart13`、`hellen_chart`、`guolao_chart`、`india_chart`、`relative`、`germany` |
| 推运与时运 | `solarreturn`、`lunarreturn`、`solararc`、`givenyear`、`profection`、`pd`、`pdchart`、`zr`、`firdaria`、`decennials` |
| 中文术数主干 | `ziwei_birth`、`ziwei_rules`、`bazi_birth`、`bazi_direct`、`liureng_gods`、`liureng_runyear`、`qimen`、`taiyi`、`jinkou` |
| Phase 2 本地技法 | `tongshefa`、`sanshiunited`、`suzhan`、`sixyao`、`otherbu` |
| 节气 / 农历 / 卦义 | `jieqi_year`、`nongli_time`、`gua_desc`、`gua_meiyi` |

### 已完成机器建模的星阙 AI 导出协议

除了“能算”，这个仓库还把星阙的 AI 导出协议整理成机器可读的 registry surface，覆盖这些 technique 域：

- `astrochart`、`astrochart_like`、`indiachart`、`relative`
- `primarydirect`、`primarydirchart`、`zodialrelease`、`firdaria`、`decennials`
- `solarreturn`、`lunarreturn`、`solararc`、`givenyear`、`profection`
- `bazi`、`ziwei`、`suzhan`、`sixyao`、`tongshefa`
- `liureng`、`jinkou`、`qimen`、`taiyi`、`sanshiunited`
- `guolao`、`germany`
- `jieqi`、`jieqi_meta`、`jieqi_chunfen`、`jieqi_xiazhi`、`jieqi_qiufen`、`jieqi_dongzhi`
- `otherbu`、`generic`

### 明确排除项

- `fengshui`

## 对 AI 来说，这个仓库最重要的不是“算”，而是“稳定可消费”

每个工具调用最终都会返回统一 envelope：

```json
{
  "ok": true,
  "tool": "qimen",
  "version": "0.3.0",
  "input_normalized": {},
  "data": {},
  "summary": [],
  "warnings": [],
  "memory_ref": {},
  "error": null
}
```

对于已经接入星阙导出协议的技法，还会额外带：

- `data.export_snapshot`
- `data.export_format`
- `data.export_snapshot.snapshot_text`
- `data.export_snapshot.sections`
- `data.export_snapshot.selected_sections`

这意味着：

- AI 不需要自己从自由文本里乱猜结构。
- 同一个技法连续多次调用，都会得到同一套格式化 contract。
- `horosa_dispatch` 的汇总层也显式带每个子结果的 export contract。
- 最终落库到 JSON artifact 后，结构不会丢失。

## 数据管理已经不是“把结果存一下”，而是完整本地记录系统

本地数据默认写到：

- macOS / Linux：`~/.horosa-skill/`
- Windows：`%APPDATA%/HorosaSkill/`

每一次 run 会沉淀这些内容：

- run 元信息
- tool call 记录
- entity 索引
- JSON artifact
- `run manifest`
- 原始 `query_text`
- 用户问题 `user_question`
- AI 最终回答 `ai_answer_text`
- 可选结构化回答 `ai_answer_structured`

现在支持的典型管理动作：

- `memory query`
  按 tool、entity、run_id 查询历史记录
- `memory show <run_id>`
  精确回看某一次完整调用
- `memory answer --stdin`
  把 AI 最终回答回写到已有记录

这让它不只是“工具层”，而是“工具层 + 可追溯知识库”。

## 快速开始

```bash
cd horosa-skill
uv sync
uv run horosa-skill install
uv run horosa-skill doctor
uv run horosa-skill serve
```

默认 MCP 地址：

```text
http://127.0.0.1:8765/mcp
```

如果你要给 Claude Desktop 这类 stdio 客户端使用：

```bash
cd horosa-skill
uv run horosa-skill serve --transport stdio
```

## 最短可用路径

### 1. 安装并验证离线 runtime

```bash
cd horosa-skill
uv sync
uv run horosa-skill install
uv run horosa-skill doctor
```

### 2. 让调度器自动选技法

```bash
echo '{
  "query":"请综合奇门、六壬和星盘分析当前状态",
  "birth":{"date":"1990-01-01","time":"12:00","zone":"8","lat":"31n14","lon":"121e28"},
  "save_result": true
}' | uv run horosa-skill ask --stdin
```

### 3. 回看某一条完整记录

```bash
uv run horosa-skill memory show <run_id>
```

### 4. 把 AI 最终回答写回这条记录

```bash
echo '{
  "run_id":"<run_id>",
  "user_question":"我接下来事业走势如何？",
  "ai_answer":"先稳后升，宜先整理资源再扩张。",
  "ai_answer_structured":{"trend":"up_later"}
}' | uv run horosa-skill memory answer --stdin
```

## 典型调用方式

### 查看完整导出 registry

```bash
cd horosa-skill
uv run horosa-skill export registry
```

### 把星阙导出正文解析成结构化 JSON

```bash
echo '{
  "technique":"qimen",
  "content":"[起盘信息]\n参数\n\n[八宫]\n八宫内容\n\n[演卦]\n演卦内容"
}' | uv run horosa-skill export parse --stdin
```

### 直接调用某个工具

```bash
echo '{"date":"1990-01-01","time":"12:00","zone":"8","lat":"31n14","lon":"121e28"}' \
  | uv run horosa-skill tool run chart --stdin
```

### 直接运行 Phase 2 本地技法

```bash
echo '{"taiyin":"巽","taiyang":"坤","shaoyang":"震","shaoyin":"震"}' \
  | uv run horosa-skill tool run tongshefa --stdin
```

### 运行统一调度器

```bash
echo '{
  "query":"请综合奇门、六壬和星盘做当前状态分析",
  "birth":{"date":"1990-01-01","time":"12:00","zone":"8","lat":"31n14","lon":"121e28"},
  "save_result": true
}' | uv run horosa-skill dispatch --stdin
```

## 当前支持的 AI 客户端

- [Claude Desktop 配置示例](./horosa-skill/examples/clients/claude_desktop_config.json)
- [Codex 配置示例](./horosa-skill/examples/clients/codex-config.toml)
- [Open WebUI 接入说明](./horosa-skill/examples/clients/openwebui-streamable-http.md)
- [OpenClaw 接入说明](./horosa-skill/examples/clients/openclaw-mcp.md)

## Release 与 runtime 策略

这个仓库故意拆成三层：

| 层 | 放在哪里 | 作用 |
| --- | --- | --- |
| 公开仓库层 | GitHub repo | 代码、文档、CLI、MCP、测试、示例、打包脚本 |
| 维护者本地打包输入层 | `vendor/runtime-source/` | 构建离线 runtime release 所需的大体积输入 |
| 最终用户运行层 | `~/.horosa/runtime/current` 或 `%LOCALAPPDATA%/Horosa/runtime/current` | 用户安装后真实执行算法的本地 runtime |

这样可以同时满足：

- GitHub 页面足够干净
- Release 资产足够完整
- 本地运行足够离线
- 维护者打包流程不依赖外部兄弟目录

## 仓库结构

| 路径 | 说明 |
| --- | --- |
| [`horosa-skill/`](./horosa-skill) | 核心 Python 包、CLI、MCP server、tests、examples、release scripts |
| [`docs/`](./docs) | runtime 规范、算法覆盖矩阵、Release 文档、维护文档 |
| [`vendor/`](./vendor) | 本地 runtime 打包输入区 |

建议顺手看的文档：

- [Repo Layout](./docs/REPO_LAYOUT.md)
- [Offline Runtime Releases](./docs/OFFLINE_RUNTIME_RELEASES.md)
- [Runtime Manifest Spec](./docs/RUNTIME_MANIFEST_SPEC.md)
- [Algorithm Coverage](./docs/ALGORITHM_COVERAGE.md)
- [Vendored Runtime Sources](./vendor/README.md)

## 当前状态

已完成：

- GitHub-first 离线 runtime 安装链
- macOS / Windows runtime release 资产
- 本地 MCP server 与 JSON-first CLI
- 完整星阙 AI 导出 registry 与 parser
- 37 个可调用工具的结构化稳定输出
- `dispatch` 汇总层 export contract
- SQLite + JSON artifact + run manifest 数据管理
- AI answer 回写与检索链路
- 从 GitHub fresh clone 后重新安装 runtime 的实测闭环

如果你需要的是一个“把星阙变成 AI 可调用基础设施”的仓库，而不是一堆分散脚本，这个 repo 现在已经是按这个方向搭好的。
