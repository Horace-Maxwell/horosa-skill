"""conftest 的 `_never_touch_the_users_real_dirs` 必须真的生效：默认数据目录与 runtime 根都在临时目录里。"""
from __future__ import annotations

import tempfile
from pathlib import Path

from horosa_skill.config import Settings


def _under_tmp(path: Path) -> bool:
    return Path(tempfile.gettempdir()).resolve() in path.resolve().parents or "user-dirs" in str(path)


def test_settings_defaults_point_into_a_temp_dir() -> None:
    settings = Settings()
    assert _under_tmp(settings.data_dir), settings.data_dir
    assert _under_tmp(settings.runtime_root), settings.runtime_root


def test_from_env_defaults_point_into_a_temp_dir(monkeypatch) -> None:
    for name in ("HOROSA_SKILL_DATA_DIR", "HOROSA_RUNTIME_ROOT", "HOROSA_TRACE_DIR"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings.from_env()
    assert _under_tmp(settings.data_dir) and _under_tmp(settings.runtime_root)
    assert settings.trace_dir is not None and _under_tmp(settings.trace_dir)
