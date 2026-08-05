from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILDERS = ["build_runtime_release_windows", "build_runtime_release_linux"]


@pytest.mark.parametrize("builder_name", BUILDERS)
def test_wipe_targets_staging_only_so_the_download_cache_survives(builder_name: str) -> None:
    # Wiping BUILD_ROOT took DOWNLOAD_ROOT with it and re-downloaded the JDK on every rebuild.
    builder = _load(builder_name)
    source = (SCRIPTS / f"{builder_name}.py").read_text(encoding="utf-8")
    assert "shutil.rmtree(BUILD_ROOT)" not in source
    assert "shutil.rmtree(PAYLOAD_ROOT)" in source
    assert builder.DOWNLOAD_ROOT.parent == builder.BUILD_ROOT
    assert builder.PAYLOAD_ROOT != builder.DOWNLOAD_ROOT


@pytest.mark.parametrize("builder_name", BUILDERS)
def test_cached_download_is_reused_only_for_the_same_url(
    builder_name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    builder = _load(builder_name)
    calls: list[list[str]] = []

    def fake_run(cmd, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        calls.append(cmd)
        Path(cmd[cmd.index("-o") + 1]).write_bytes(b"payload")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(builder.subprocess, "run", fake_run)
    dest = tmp_path / "archive.zip"

    builder.download("https://example.invalid/v1/archive.zip", dest)
    assert len(calls) == 1
    assert dest.read_bytes() == b"payload"

    # Same URL -> cache hit, no second transfer.
    builder.download("https://example.invalid/v1/archive.zip", dest)
    assert len(calls) == 1

    # A new upstream release resolves to a different URL -> must re-download, not serve the old one.
    builder.download("https://example.invalid/v2/archive.zip", dest)
    assert len(calls) == 2


@pytest.mark.parametrize("builder_name", BUILDERS)
def test_interrupted_download_does_not_poison_the_cache(
    builder_name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Previously the BUILD_ROOT wipe hid this; with a persistent cache a truncated file would be
    # served forever as a "cache hit".
    builder = _load(builder_name)

    def failing_run(cmd, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        Path(cmd[cmd.index("-o") + 1]).write_bytes(b"trunc")
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(builder.subprocess, "run", failing_run)
    dest = tmp_path / "archive.zip"

    with pytest.raises(subprocess.CalledProcessError):
        builder.download("https://example.invalid/v1/archive.zip", dest)

    assert not dest.exists(), "a failed transfer must not leave a cache-hittable file"
    assert not dest.with_name(dest.name + ".url").exists()
