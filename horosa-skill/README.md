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
  - `knowledge registry`
  - `knowledge read`
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

完整双语能力矩阵请看根目录 [README.md](../README.md) 和 [README_EN.md](../README_EN.md)。这里保留运行层视角，强调“你在这个子项目里具体能调什么”。

### 核心星盘与派生盘

- `chart`：标准星盘
- `chart13`：13 宫扩展盘
- `hellen_chart`：希腊星盘
- `guolao_chart`：七政四余盘
- `india_chart`：印度盘
- `relative`：合盘 / 关系盘
- `germany`：量化盘 / 中点盘

### 推运与时运

- `solarreturn`：太阳返照
- `lunarreturn`：月返
- `solararc`：太阳弧推运
- `givenyear`：指定年推运
- `profection`：小限
- `pd`：主限 / 本初方向
- `pdchart`：主限盘
- `zr`：黄道释放
- `firdaria`：法达星限
- `decennials`：十年大运 / 十年星限

### 中文术数与扩展技法

- `ziwei_birth`：紫微斗数命盘
- `ziwei_rules`：紫微规则库
- `bazi_birth`：八字命盘
- `bazi_direct`：八字直断
- `liureng_gods`：大六壬起课
- `liureng_runyear`：大六壬行年
- `qimen`：奇门遁甲
- `taiyi`：太乙神数
- `jinkou`：金口诀
- `tongshefa`：统摄法
- `sanshiunited`：三式合一
- `suzhan`：宿占 / 宿盘
- `sixyao`：六爻 / 易卦
- `otherbu`：西洋游戏 / 占星骰子
- `jieqi_year`：全年节气盘
- `nongli_time`：农历换算
- `gua_desc`：卦义说明
- `gua_meiyi`：梅易卦义

### 导出与调度

- `export_registry`：星阙 AI 导出协议注册表
- `export_parse`：星阙 AI 导出正文解析器
- `horosa_dispatch`：自然语言总调度器

### 星阙悬浮知识库

- `knowledge_registry`：悬浮知识目录
- `knowledge_read`：悬浮知识读取器

已接入：

- 星盘悬浮：`planet`、`sign`、`house`、`lot`、`aspect`
- 大六壬悬浮：`shen`、`house`
- 奇门悬浮：`stem`、`door`、`star`、`god`

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

### 读取星阙悬浮知识

```bash
echo '{"domain":"astro","category":"planet","key":"Sun"}' \
  | uv run horosa-skill knowledge read --stdin
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
