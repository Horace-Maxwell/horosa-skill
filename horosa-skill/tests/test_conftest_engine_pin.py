"""The session pin in conftest.py must make the repo's core-js win over an installed runtime's copy."""

from __future__ import annotations

from pathlib import Path

from conftest import REPO_CORE_JS_ROOT

from horosa_skill.config import Settings
from horosa_skill.engine.js_client import HorosaJsEngineClient


def _client_with_installed_runtime(tmp_path: Path) -> HorosaJsEngineClient:
    """A fake installed runtime whose manifest points core-js at its own (stale) bundled copy."""
    runtime_root = tmp_path / "runtime"
    settings = Settings(runtime_root=runtime_root, data_dir=tmp_path / "data")
    (settings.runtime_current_dir / "horosa-core-js").mkdir(parents=True)
    client = HorosaJsEngineClient(settings)
    manifest = {"artifacts": {"horosa_core_js_root": "horosa-core-js"}, "runtimes": {}}
    client.runtime_manager.load_installed_manifest = lambda *a, **k: manifest  # type: ignore[method-assign]
    return client


def test_repo_core_js_wins_over_an_installed_runtime_during_tests(tmp_path: Path) -> None:
    client = _client_with_installed_runtime(tmp_path)
    assert client._resolve_engine_root().resolve() == REPO_CORE_JS_ROOT.resolve()


def test_without_the_pin_the_installed_runtime_copy_would_win(tmp_path: Path, monkeypatch) -> None:
    # 负向对照：去掉 pin，解析顺序落回「已装 runtime 优先」——正是 pin 要防的那条路。
    monkeypatch.delenv("HOROSA_CORE_JS_ROOT", raising=False)
    client = _client_with_installed_runtime(tmp_path)
    assert client._resolve_engine_root().resolve() == (client.settings.runtime_current_dir / "horosa-core-js").resolve()
