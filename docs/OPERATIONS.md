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
