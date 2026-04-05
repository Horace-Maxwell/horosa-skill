# Horosa Skill Core

`horosa-skill` 是这个仓库真正可运行的核心子项目。它把星阙 / Horosa 的本地算法、AI 导出协议、离线 runtime、MCP 暴露层和本地数据管理统一进一个 Python 包里。

如果根目录 README 讲的是“这个项目是什么”，这里讲的是“这个包具体能做什么”。

## 这个子项目包含什么

- 离线 runtime 安装与诊断
  - `install`
  - `doctor`
  - `serve`
  - `stop`
- MCP 服务层
  - Streamable HTTP
  - stdio
- JSON-first CLI
  - `tool run`
  - `dispatch`
  - `ask`
  - `export registry`
  - `export parse`
- 本地数据管理
  - SQLite
  - JSON artifacts
  - run manifest
  - AI answer write-back
- 星阙 AI 导出协议机器建模
  - export registry
  - export snapshot parsing
  - per-tool `export_snapshot`
  - per-tool `export_format`

## 当前已经接进来的技法

### 核心星盘与派生盘

- `chart`
- `chart13`
- `hellen_chart`
- `guolao_chart`
- `india_chart`
- `relative`
- `germany`

### 推运与时运

- `solarreturn`
- `lunarreturn`
- `solararc`
- `givenyear`
- `profection`
- `pd`
- `pdchart`
- `zr`
- `firdaria`
- `decennials`

### 中文术数与扩展技法

- `ziwei_birth`
- `ziwei_rules`
- `bazi_birth`
- `bazi_direct`
- `liureng_gods`
- `liureng_runyear`
- `qimen`
- `taiyi`
- `jinkou`
- `tongshefa`
- `sanshiunited`
- `suzhan`
- `sixyao`
- `otherbu`
- `jieqi_year`
- `nongli_time`
- `gua_desc`
- `gua_meiyi`

### 导出与调度

- `export_registry`
- `export_parse`
- `horosa_dispatch`

明确排除：

- `fengshui`

## 快速开始

```bash
cd horosa-skill
uv sync
uv run horosa-skill install
uv run horosa-skill doctor
uv run horosa-skill serve
```

## 最短工作流

### 1. 安装 runtime

```bash
uv run horosa-skill install
uv run horosa-skill doctor
```

### 2. 直接让调度器选技法

```bash
echo '{
  "query":"请综合奇门、六壬和星盘分析当前状态",
  "birth":{"date":"1990-01-01","time":"12:00","zone":"8","lat":"31n14","lon":"121e28"},
  "save_result": true
}' | uv run horosa-skill ask --stdin
```

### 3. 查看某一次完整记录

```bash
uv run horosa-skill memory show <run_id>
```

### 4. 回写 AI 最终回答

```bash
echo '{
  "run_id":"<run_id>",
  "user_question":"我接下来事业走势如何？",
  "ai_answer":"先稳后升，宜先整理资源再扩张。",
  "ai_answer_structured":{"trend":"up_later"}
}' | uv run horosa-skill memory answer --stdin
```

## 常用命令

### 列出工具

```bash
uv run horosa-skill tool list
```

### 直接运行单个方法

```bash
echo '{"date":"1990-01-01","time":"12:00","zone":"8","lat":"31n14","lon":"121e28"}' \
  | uv run horosa-skill tool run chart --stdin
```

### 运行本地 Phase 2 技法

```bash
echo '{"taiyin":"巽","taiyang":"坤","shaoyang":"震","shaoyin":"震"}' \
  | uv run horosa-skill tool run tongshefa --stdin
```

### 导出 registry

```bash
uv run horosa-skill export registry --technique qimen
```

### 解析星阙 AI 导出正文

```bash
echo '{
  "technique":"qimen",
  "content":"[起盘信息]\n参数\n\n[八宫]\n八宫内容\n\n[演卦]\n演卦内容"
}' | uv run horosa-skill export parse --stdin
```

## 本地记录系统会保存什么

每次 run 会持久化：

- run 元信息
- tool call 记录
- entity 索引
- JSON artifact
- run manifest
- query_text
- user_question
- ai_answer_text
- ai_answer_structured

对应管理命令：

- `uv run horosa-skill memory query`
- `uv run horosa-skill memory show <run_id>`
- `uv run horosa-skill memory answer --stdin`

## 环境变量

可以复制 `.env.example` 再按需覆盖：

```bash
cp .env.example .env
```

常见项：

- `HOROSA_SERVER_ROOT`
- `HOROSA_CHART_SERVER_ROOT`
- `HOROSA_SKILL_DATA_DIR`
- `HOROSA_SKILL_DB_PATH`
- `HOROSA_SKILL_OUTPUT_DIR`
- `HOROSA_RUNTIME_ROOT`
- `HOROSA_RUNTIME_MANIFEST_URL`
- `HOROSA_RUNTIME_RELEASE_REPO`
- `HOROSA_RUNTIME_PLATFORM`
- `HOROSA_RUNTIME_START_TIMEOUT_SECONDS`
- `HOROSA_SKILL_HOST`
- `HOROSA_SKILL_PORT`

## 相关文档

- [根目录中文首页](../README.md)
- [Root English README](../README_EN.md)
- [客户端配置示例](./examples/clients)
- [Runtime 发布说明](../docs/OFFLINE_RUNTIME_RELEASES.md)
- [算法覆盖矩阵](../docs/ALGORITHM_COVERAGE.md)
