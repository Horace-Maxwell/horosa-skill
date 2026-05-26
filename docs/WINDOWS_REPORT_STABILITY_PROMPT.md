# Windows Codex 跨平台稳定性复核 Prompt

请在 Windows 机器上作为 Codex 执行这份复核。目标不是继续做激进优化，而是确认 Horosa Skill 的最新报告层在 Windows 上稳定可用，同时不能破坏 macOS / POSIX 路径。

## 背景

本轮 macOS 侧已经完成报告层修复：

- `report_template` 给 AI 返回对话式解盘 brief。
- `report_from_tool` / `report_render` 支持 `ai_answer_text`，AI 可以直接提交自然语言完整解盘正文。
- 没有 AI 分析时不会伪造最终报告，而是返回 `needs_ai_analysis=true` 的分析请求包。
- JSON 保留完整机器元信息、coverage、provenance、source export。
- DOCX / PDF 只展示人类需要看的最终咨询报告，不再把 `run_id`、`schema`、`来源追溯`、`可读解读`、`关键线索`、原始星阙字段堆叠进正文。
- 报告 artifact 会写入 memory manifest，包含 `exists`、`file_size`、`sha256`、`artifact_summary`，能被 `memory_show` / `memory_query` 检索。

请你重点验证 Windows 上也能保持这一套行为。

## 工作目录要求

1. 只处理这个仓库：`https://github.com/Horace-Maxwell/horosa-skill.git`
2. 使用 fresh clone，不要复用旧目录、旧 `.venv`、旧 runtime、旧 OpenClaw workspace。
3. 不要碰用户其他 GitHub repo。
4. 不要提交任何 API key、`.env`、生成的大量报告产物、临时 runtime、临时 workspace。
5. 不要使用 LFS。

建议临时目录：

```powershell
$Root = "$env:TEMP\horosa-report-windows-final"
$RepoRoot = "$Root\repo"
$Home = "$Root\home"
$Workspace = "$Root\workspace"
$Logs = "$Root\logs"
Remove-Item -Recurse -Force $Root -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $RepoRoot, $Home, $Workspace, $Logs | Out-Null
git clone https://github.com/Horace-Maxwell/horosa-skill.git $RepoRoot\horosa-skill
Set-Location $RepoRoot\horosa-skill\horosa-skill
git rev-parse HEAD
```

## 基础环境记录

请先输出以下版本：

```powershell
python --version
uv --version
node --version
npm --version
java -version
mcporter --version
git status --short
```

如果 `mcporter` 没有安装：

```powershell
npm install -g mcporter
```

## 必跑验证

### 1. 依赖与测试

```powershell
uv sync
uv run pytest -q
```

期望：

- pytest 全绿。
- pytest 必须来自项目 `.venv`，不要落到用户全局 Python。
- 不允许因为 Windows 编码、路径、PowerShell、字体或 reportlab/docx 依赖失败。

### 2. OpenClaw / mcporter 一键接入

```powershell
uv run horosa-skill client openclaw-setup --workspace $Workspace --isolate-home $Home
```

期望：

- 返回 JSON，不挂死。
- `ready_for_openclaw=true`。
- `config_written_to` 指向 `$Workspace\config\mcporter.json`。
- `local_home` 指向 `$Home`。
- `command` 应是 Windows 可执行路径，通常是 `uv.exe` 或 `cmd.exe` 包装后的 Windows 路径。
- 不得出现 `/bin/zsh`、`export HOME=...`、POSIX shell 语法。
- `HOME`、`USERPROFILE`、`HOROSA_RUNTIME_ROOT`、`HOROSA_SKILL_DATA_DIR` 都应该是 Windows 绝对路径。

### 3. OpenClaw smoke

```powershell
uv run horosa-skill client openclaw-check --workspace $Workspace
```

期望：

- `ok=true`
- `server_visible=true`
- `listed_tool_count >= 43`
- `knowledge_registry_ok=true`
- `chart_ok=true`
- `memory_show_ok=true`

如果失败，请先看错误是否是 Windows 路径、runtime 启动、mcporter JSON 解析、或后台子进程句柄继承问题。修复时务必只在 Windows 分支动刀，避免破坏 macOS。

### 4. Full self-check

```powershell
uv run horosa-skill client openclaw-check --workspace $Workspace --full
```

期望：

- `ok=true`
- `tool_count=39`
- `passed_tools=39`
- `failed_tools={}`
- `dispatch.ok=true`
- `answer_writeback.ok=true`

## 报告层专项验证

### 5. 无 AI 时不能伪造最终报告

运行一个代表性技法，例如奇门：

```powershell
$Payload = '{"date":"2028-04-06","time":"09:33:00","zone":"8","lat":"31n13","lon":"121e28","question":"这个事情能不能推进？风险在哪里？"}'
$Payload | uv run horosa-skill report from-tool qimen --stdin --format pdf --question "这个事情能不能推进？风险在哪里？"
```

> 说明（v0.6.0）：`qimen` / `taiyi` / `jinkou`（及 `sanshiunited` 里的奇门 + 太乙）现在由星阙 `ken` 后端（`kinqimen` / `kintaiyi` / `kinjinkou`）计算，需要本地 chart 服务在线。安装版 runtime 已内置这三个引擎，`doctor` 通过即代表 chart 服务可起；若 `report from-tool qimen` 报无法连接后端，先确认 runtime 为含 ken 引擎的版本（v0.6.0 及以上）、chart 服务已启动，而不是误判算法不可用。

期望：

- 如果没有提供 `ai_report` 或 `ai_answer_text`，结果应返回 `mode=analysis_required` 或等价结构。
- `needs_ai_analysis=true`
- `final_report_generated=false`
- 不应生成假的最终 PDF。

### 6. 自然语言 AI 正文能生成最终报告

用 `ai_answer_text` 生成报告。可以通过 Python 调 service，避免 CLI 引号麻烦：

```powershell
uv run python - <<'PY'
from pathlib import Path
from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

settings = Settings(
    db_path=Path("windows-report-smoke.db"),
    output_dir=Path("windows-report-runs"),
)
service = HorosaSkillService(settings, store=MemoryStore(settings))
answer_text = (
    "结论上，这件事可以推进，但不适合立刻重仓或裸奔式冲刺。"
    "我会先看起盘信息、盘面结构、关键宫位和风险线索，再把它翻译成现实行动建议。"
    "当前更适合先验证机会质量、保留现金流和备选方案，等阻力较小的窗口再正式推进。"
)
result = service.report_from_tool({
    "tool_name": "qimen",
    "payload": {"date":"2028-04-06","time":"09:33:00","zone":"8","lat":"31n13","lon":"121e28"},
    "format": "docx",
    "question": "这个事情能不能推进？风险在哪里？",
    "ai_answer_text": answer_text,
})
print(result)
PY
```

期望：

- `ok=true`
- `answer_writeback.ok=true`
- 返回 `artifact_path`，DOCX 文件存在且非空。
- `memory_show` 能看到 `ai_answer_text` 和 `report_docx` artifact。

### 7. 人类版 DOCX/PDF 不能含机器噪音

请打开或解析上一步生成的 DOCX。正文必须包含：

- `解读目标`
- `核心结论`
- `完整解盘正文`
- 用户的问题
- AI 的自然语言结论和建议

正文不能包含：

- `run_id`
- `schema`
- `report_metadata`
- `来源追溯`
- `Horosa Skill`
- `本次咨询使用`
- `可读解读`
- `关键线索`
- `盘面返回的核心摘要`
- `星阙 AI 导出正文`
- 原始 JSON / 内部路径 / 模板说明

可用下面的检查脚本：

```powershell
uv run python - <<'PY'
from pathlib import Path
from docx import Document

docx = next(Path("windows-report-runs").rglob("*_report_*.docx"))
doc = Document(docx)
texts = []
for p in doc.paragraphs:
    if p.text.strip():
        texts.append(p.text.strip())
for table in doc.tables:
    for row in table.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                if p.text.strip():
                    texts.append(p.text.strip())
text = "\n".join(texts)
required = ["解读目标", "核心结论", "完整解盘正文"]
for item in required:
    assert item in text, item
forbidden = ["run_id", "schema", "report_metadata", "来源追溯", "Horosa Skill", "本次咨询使用", "可读解读", "关键线索", "盘面返回的核心摘要", "星阙 AI 导出正文"]
bad = [item for item in forbidden if item in text]
assert not bad, bad
assert len(text) > 300, len(text)
print({"docx": str(docx), "chars": len(text), "ok": True})
PY
```

### 8. 每个技法至少验证 report template

请确认每个已注册技法都能生成 `report_template`，且模板里存在：

- `conversation_brief`
- `ai_fillable.answer_text`
- `targeted_analysis_contract`
- `source_context.export_text`

如果已有 full self-check 覆盖了全部工具，也请补一个小脚本抽样检查 report tools 是否在 MCP 列表里。

## 如果发现问题，修复原则

1. 稳定优先，不要为了几秒性能动高风险 runtime 架构。
2. Windows 特有修复必须尽量放在 `os.name == "nt"` 或平台分支里。
3. 不要破坏 macOS 的 POSIX shell / runtime 启动路径。
4. 不要把 DOCX/PDF 做成机器 dump；机器信息留在 JSON。
5. `ai_answer_text` 路径必须是第一等公民，因为 Cursor、OpenClaw、Claude、Codex 都可能只回自然语言。
6. 若 reportlab 字体在 Windows 出问题，优先使用系统字体 `Microsoft YaHei` / `SimSun`，不要依赖 Word、LibreOffice、Pandoc、Chromium。
7. 修复后必须新增或更新测试，尤其是 Windows 路径、自然语言报告、机器噪音过滤。

## 最终交付格式

请回报：

- Windows 版本、Python / uv / Node / Java / mcporter 版本。
- fresh clone commit hash。
- `uv sync` 结果。
- `pytest` 结果。
- `openclaw-setup` 结果与耗时。
- `openclaw-check` smoke 结果。
- full self-check 结果：`tool_count`、`passed_tools`、`failed_tools`、`dispatch.ok`、`answer_writeback.ok`。
- 报告专项验证结果：DOCX/PDF 是否生成、是否可读、是否无机器噪音、memory 是否能检索。
- 如果改了代码，列出文件、原因、验证方式。
- 如果一切通过且需要推送，才 commit/push 到 GitHub main。

最终目标：Windows 和 macOS 都能稳定完成 `调用 -> 计算 -> AI 解盘 -> DOCX/PDF/JSON 报告 -> memory 写入 -> 检索读取`，且人类版报告像专业咨询报告，不像调试日志。
