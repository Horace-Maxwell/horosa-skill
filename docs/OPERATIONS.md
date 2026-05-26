# Operations

## 目标

这份文档面向维护者，描述 Horosa Skill 的安装、运行、发布、校验和排障路径。

## 本地运行

1. 进入 [`horosa-skill`](../horosa-skill)
2. 运行 `uv sync --dev`
3. 运行 `uv run horosa-skill install`
4. 运行 `uv run horosa-skill doctor`
5. 运行 `uv run horosa-skill serve`

## 发布前检查

- `uv run pytest -q`
- `uv run python scripts/verify_readme_links.py`
- `uv run python scripts/verify_server_json.py`
- `uv run python scripts/build_knowledge_index.py --check`
- `uv run python scripts/run_benchmark.py --skip-runtime`
- `uv run python scripts/verify_vendor_runtime_sources.py`

## ken 技法验证（奇门 / 太乙 / 金口 / 三式合一）

这些技法由 **ken 后端**（`kinqimen`/`kintaiyi`/`kinjinkou`）在 Python chart 服务上计算（`/qimen/pan`、
`/taiyi/pan`、`/jinkou/pan`），`horosa-core-js` 只负责把 ken 响应重排成 `aiExport.js` 分段。验证需要 chart
服务在线（`:8899`，以及 Java `:9999`）：

1. 起后端：在 Horosa-Web 下 `HOROSA_SKIP_UI_BUILD=1 ./start_horosa_local.sh`（mac）/ `start_horosa_local.ps1`（Win）。
2. 确认监听：`:9999`（Java）+ `:8899`（chart/ken）。
3. `uv run pytest -q`：`tests/test_local_js_tools.py` 里 qimen/taiyi/jinkou/sanshiunited 为集成测试，后端不在时自动 skip；
   `tongshefa` 始终执行。
4. 验收标准：每个技法产出其 aiExport.js 分段（奇门：起盘信息/盘型/盘面要素/奇门演卦/八宫详解/九宫方盘；
   太乙：起盘信息/太乙盘/十六宫标记；金口：起盘信息/金口诀速览/金口诀四位/四位神煞），且 export 契约干净
   （无 missing/unknown 分段）。

离线运行时必须打包 `Horosa-Web/vendor/{kinqimen,kintaiyi,kinjinkou}` 及其依赖（bidict/numpy/kerykeion/ephem/
pendulum）——见 [`OFFLINE_RUNTIME_RELEASES.md`](./OFFLINE_RUNTIME_RELEASES.md)。

## Runtime Release

Runtime release 采用“轻仓库 + 重 release 资产”模式。

- 构建脚本：[`build_runtime_release.sh`](./../horosa-skill/scripts/build_runtime_release.sh)
- 输出目录：`horosa-skill/dist/runtime/`
- 必要资产：
  - `horosa-runtime-darwin-arm64-v<version>.tar.gz`
  - `horosa-runtime-win32-x64-v<version>.zip`
  - `runtime-manifest.json`
  - `SHA256SUMS.txt`
  - `horosa-skill-sbom.json`

## Provenance / Attestation

release workflow 会上传 runtime 资产并调用 GitHub artifact attestation。发布后可在本机执行：

```bash
gh attestation verify horosa-skill/dist/runtime/runtime-manifest.json --repo Horace-Maxwell/horosa-skill
```

当前 release workflow 设计为 `self-hosted runner` 路径，因为完整 runtime 组装依赖本地维护者持有的 vendored runtime source。

## 故障处理

- `doctor` 显示 `runtime.manifest_invalid`
  - 检查 `~/.horosa/runtime/current/runtime-manifest.json`
- `services:not_running`
  - 先运行 `horosa-skill stop`
  - 再运行 `horosa-skill serve`
- benchmark 只想跑无 runtime 部分
  - 运行 `uv run horosa-skill benchmark run --skip-runtime`
- `uv run` / `pytest` 报 `pydantic_core` 的 `.so` `library load disallowed by system policy`
  - `.venv` 指向了 miniconda（带 library validation）。重建为 uv 自管 CPython：
    `uv venv --clear --python-preference only-managed --python 3.12 && uv sync`
- 奇门/太乙/金口报 `transport.connection_error` 或返回空盘
  - chart 服务（`:8899`）未起或未挂载 ken。确认后端在线，且 `import kinqimen/kintaiyi/kinjinkou` 能成功
    （`vendor` 在 PYTHONPATH 上）。
