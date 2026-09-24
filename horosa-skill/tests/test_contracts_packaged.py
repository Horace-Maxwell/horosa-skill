"""v0.40.0 P1：运行期契约必须随 wheel / MCPB 走，消费方不能再假定源码树布局。

`decisions/policy.py`（Jev 阈值锁）与 `reports/technique_card.py`（技法算源）此前用 `parents[3] / "contracts"` 找文件——
源码树成立、wheel 安装后不成立：Jev `enforce` 永不生效、技法依据卡算源一律「未标注」（v0.39.0 已出货）。三件套：
pyproject force-include 两份契约进包内 `horosa_skill/contracts/`；定位器先源码树后包内副本；wheel 守卫锁条目。
"""
from __future__ import annotations

import tomllib
from pathlib import Path

from horosa_skill import contracts_locator
from horosa_skill.contracts_locator import PACKAGED_CONTRACT_FILES, contract_candidates, contract_path
from horosa_skill.decisions import policy
from horosa_skill.reports import technique_card

PKG_ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_force_includes_every_runtime_contract() -> None:
    wheel = tomllib.loads((PKG_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["hatch"]["build"]["targets"]["wheel"]
    force = wheel["force-include"]
    for name in PACKAGED_CONTRACT_FILES:
        assert force.get(f"contracts/{name}") == f"horosa_skill/contracts/{name}", name
        assert (PKG_ROOT / "contracts" / name).is_file(), name
    # wheel 守卫锁同一组条目（缺一即 verify_wheel_contents 红）。
    guard = (PKG_ROOT / "scripts" / "verify_wheel_contents.py").read_text(encoding="utf-8")
    for name in PACKAGED_CONTRACT_FILES:
        assert f'"horosa_skill/contracts/{name}"' in guard, name


def test_consumers_resolve_through_the_locator_in_the_source_tree() -> None:
    assert policy.THRESHOLDS_PATH == PKG_ROOT / "contracts" / "jev_thresholds.json" and policy.THRESHOLDS_PATH.is_file()
    assert technique_card._PROVENANCE_PATH == PKG_ROOT / "contracts" / "technique_provenance.json" and technique_card._PROVENANCE_PATH.is_file()
    assert contracts_locator.SOURCE_TREE_CONTRACTS_DIR == PKG_ROOT / "contracts"


def test_locator_falls_back_to_the_packaged_copy_when_the_source_tree_is_gone(tmp_path: Path) -> None:
    """模拟 wheel 安装：site-packages/horosa_skill/contracts/ 有副本、源码树 contracts/ 不存在。"""
    site = tmp_path / "site-packages" / "horosa_skill" / "contracts"
    site.mkdir(parents=True)
    (site / "jev_thresholds.json").write_text("{}", encoding="utf-8")
    missing_source = tmp_path / "not-a-checkout" / "contracts"  # 不创建
    assert contract_path("jev_thresholds.json", source_dir=missing_source, package_dir=site) == site / "jev_thresholds.json"
    # 源码树在场时优先源码树（开发期改契约立刻生效）。
    source = tmp_path / "checkout" / "contracts"
    source.mkdir(parents=True)
    (source / "jev_thresholds.json").write_text("{}", encoding="utf-8")
    assert contract_path("jev_thresholds.json", source_dir=source, package_dir=site) == source / "jev_thresholds.json"
    # 都不在：回源码树路径（调用方按缺席处理），候选顺序固定。
    assert contract_path("nope.json", source_dir=source, package_dir=site) == source / "nope.json"
    assert contract_candidates("x.json", source_dir=source, package_dir=site) == [source / "x.json", site / "x.json"]


def test_negative_control_old_parents3_layout_does_not_exist_in_an_install(tmp_path: Path) -> None:
    """旧写法 `Path(__file__).resolve().parents[3] / "contracts"` 在安装布局下指向 site-packages 的父目录——那里没有契约。"""
    fake_module = tmp_path / "venv" / "lib" / "site-packages" / "horosa_skill" / "decisions" / "policy.py"
    fake_module.parent.mkdir(parents=True)
    fake_module.write_text("", encoding="utf-8")
    old_style = fake_module.resolve().parents[3] / "contracts" / "jev_thresholds.json"
    assert old_style == tmp_path / "venv" / "lib" / "contracts" / "jev_thresholds.json"
    assert not old_style.exists()
    # 新定位器在同一布局下找到包内副本。
    packaged = fake_module.parent.parent / "contracts"
    packaged.mkdir()
    (packaged / "jev_thresholds.json").write_text("{}", encoding="utf-8")
    assert contract_path("jev_thresholds.json", source_dir=fake_module.parent.parent.parent / "contracts", package_dir=packaged).is_file()
