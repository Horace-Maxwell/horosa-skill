"""随包 Python 的应用控制替身（v0.43.1-dev，Windows 原生复验）。

2026-10-23 实测：新装 v0.43.0 载荷后 Smart App Control 拒绝加载 `astropy/time/_parse_times.pyd`（os error 4551），
`astropy.time` 整个起不来 → kintaiyi 挂 → 太乙 / 三式合一 live 用例红；同一哈希在早先装的根里放行。
替身（scripts/runtime_templates/windows/python/）只在被拦时生效：让 astropy 的快速 C 解析器恒失败，astropy 自己落回
纯 Python 参照解析器（本机对照 JD 逐位相同）。本文件锁：被拦 → 替身 + stderr 留痕；别的 ImportError 原样抛；
真扩展能加载 → 原样用；manager 每次 start 把替身拷进 site-packages。
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.runtime import HorosaRuntimeManager

SHIM_DIR = Path(__file__).resolve().parents[1] / "scripts" / "runtime_templates" / "windows" / "python"
_BLOCKED = "DLL load failed while importing _parse_times: An Application Control policy has blocked this file."


@pytest.fixture()
def shim(monkeypatch: pytest.MonkeyPatch):
    spec = importlib.util.spec_from_file_location("_horosa_app_control_under_test", SHIM_DIR / "_horosa_app_control.py")
    module = importlib.util.module_from_spec(spec)
    before = list(sys.meta_path)
    spec.loader.exec_module(module)
    monkeypatch.setattr(sys, "meta_path", before)  # 不让被测副本的 finder 留在本会话里
    return module


class _RealLoader:
    def __init__(self, error: Exception | None = None) -> None:
        self.error, self.executed = error, False

    def create_module(self, spec):  # noqa: ANN001
        if self.error is not None:
            raise self.error
        return None

    def exec_module(self, module) -> None:  # noqa: ANN001
        self.executed = True
        module.REAL = True


def _load(shim, name: str, real: _RealLoader):
    loader = shim._GuardedLoader(name, real, origin=f"C:/rt/{name}.pyd")
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_blocked_extension_gets_the_stub_and_says_so(shim, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    filled: list[str] = []
    monkeypatch.setitem(shim._STUBS, "pkg._native", lambda module: (filled.append(module.__name__), setattr(module, "STUB", True)))
    real = _RealLoader(ImportError(_BLOCKED))
    module = _load(shim, "pkg._native", real)
    assert module.STUB is True and filled == ["pkg._native"] and not real.executed
    assert "Application Control blocked" in capsys.readouterr().err


def test_other_import_errors_still_raise(shim, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(shim._STUBS, "pkg._native", lambda module: None)
    with pytest.raises(ImportError, match="missing dependency"):
        _load(shim, "pkg._native", _RealLoader(ImportError("DLL load failed: missing dependency")))


def test_loadable_extension_is_used_as_is(shim, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(shim._STUBS, "pkg._native", lambda module: setattr(module, "STUB", True))
    real = _RealLoader()
    module = _load(shim, "pkg._native", real)
    assert real.executed and getattr(module, "REAL", False) and not hasattr(module, "STUB")


def test_the_finder_only_wraps_registered_modules(shim) -> None:
    finder = shim._Finder()
    assert finder.find_spec("json") is None
    assert set(shim._STUBS) == {"astropy.time._parse_times"}


def test_parse_times_stub_matches_the_real_extension_surface(shim) -> None:
    np = pytest.importorskip("numpy")
    module = types.ModuleType("astropy.time._parse_times")
    shim._fill_parse_times(module)
    assert module.dt_pars.names == ("delim", "start", "stop", "break_allowed") and module.dt_pars.isalignedstruct
    assert module.dt_u1 == np.dtype([("byte", "u1")], align=True)
    parser = module.create_parser(np.zeros(3, module.dt_pars))
    with pytest.raises(ValueError):  # astropy 的 set_jds 接住任何异常 → 落回纯 Python 解析器
        parser(np.zeros((1, 4), module.dt_u1))


def test_manager_copies_the_shim_into_site_packages(tmp_path: Path) -> None:
    settings = Settings(runtime_root=tmp_path / "rt", db_path=tmp_path / "m.db", output_dir=tmp_path / "runs")
    manager = HorosaRuntimeManager(settings)
    site_packages = manager.current_dir / "runtime/windows/python/Lib/site-packages"
    site_packages.mkdir(parents=True)
    manifest = {"runtimes": {"python": "runtime/windows/python/python.exe"}}
    copied = manager._install_app_control_shims(manifest, SHIM_DIR.parent)
    assert sorted(Path(p).name for p in copied) == ["_horosa_app_control.py", "horosa_app_control.pth"]
    assert (site_packages / "horosa_app_control.pth").read_text(encoding="utf-8").strip() == "import _horosa_app_control"
    # 没有 python 运行时 / 没有 site-packages 时什么都不做
    assert manager._install_app_control_shims({"runtimes": {}}, SHIM_DIR.parent) == []
    assert manager._install_app_control_shims(None, SHIM_DIR.parent) == []
