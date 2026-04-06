# Evaluation

## 评测体系

Horosa Skill 现在有两层评测：

- 工程自检：确保每个工具能调用、能输出、能落库、能检索
- HorosaBench：确保调度、导出协议和知识读取质量达到稳定基线

## HorosaBench

数据集位置：

- [`horosa_bench.json`](./../horosa-skill/src/horosa_skill/benchmark/data/horosa_bench.json)

覆盖维度：

- 自然语言问法 -> 应选工具
- 工具输出 -> 必须出现的 technique / section / fragment
- 知识读取 -> 必须命中的 hover 内容
- runtime 依赖与否 -> 可做 CI 的 local-only smoke

## 运行方式

```bash
uv run horosa-skill benchmark run
uv run horosa-skill benchmark run --skip-runtime
uv run python scripts/run_full_self_check.py --rounds 2
```

## 当前指标

- `cases_passed / cases_executed`
- `pass_rate`
- dispatch `selection_ok`
- export `required_sections_ok`
- export `required_fragments_ok`
- knowledge `required_fragments_ok`

## 已知盲区

- benchmark 目前仍以 golden corpus 为主，还不是公开 leaderboard
- Windows runtime 的进程级实机验证需要 Windows runner
- `fengshui` 仍然刻意排除在当前主线之外
