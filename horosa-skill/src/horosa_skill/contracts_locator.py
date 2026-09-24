"""运行期契约文件定位（v0.40.0 P1）。

`decisions/policy.py`（Jev 阈值锁）、`decisions/eval.py`、`reports/technique_card.py`（算源契约）此前一律
`Path(__file__).resolve().parents[3] / "contracts"`——那是**源码树**布局；wheel / uvx 安装后 `parents[3]` 是
site-packages 的父目录，契约不存在 → Jev `enforce` 永不生效、技法依据卡算源一律「未标注」（v0.39.0 已出货的 bug）。

现在两处候选按序查找：源码树 `<pkg-root>/contracts/`（开发 / MCPB bundle：bundle 根 = horosa-skill/）优先，
其次包内副本 `horosa_skill/contracts/`（pyproject force-include 装进 wheel）。都不存在时返回源码树路径（调用方
按「文件缺席」处理，不在这里抛）。
"""
from __future__ import annotations

from pathlib import Path

PACKAGE_CONTRACTS_DIR = Path(__file__).resolve().parent / "contracts"
SOURCE_TREE_CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "contracts"
PACKAGED_CONTRACT_FILES = ("jev_thresholds.json", "technique_provenance.json")


def contract_candidates(name: str, *, source_dir: Path | None = None, package_dir: Path | None = None) -> list[Path]:
    return [(source_dir or SOURCE_TREE_CONTRACTS_DIR) / name, (package_dir or PACKAGE_CONTRACTS_DIR) / name]


def contract_path(name: str, *, source_dir: Path | None = None, package_dir: Path | None = None) -> Path:
    """第一个存在的候选；都不存在 → 源码树路径（保持旧调用方的「缺席」语义）。"""
    candidates = contract_candidates(name, source_dir=source_dir, package_dir=package_dir)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]
