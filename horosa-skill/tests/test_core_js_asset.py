"""The platform-independent JS engine asset (v0.50.0-dev, E-02): `scripts/build_core_js_asset.py`.

Before it, the JS engine reached users only inside the darwin-arm64 / win32-x64 runtime archives: Linux, Intel Mac, Docker and
pip/wheel gateway installs had no engine and every JS technique failed with `js_engine.cli_missing`. These tests pin what the
asset contains (tracked tree + production closure of the lock, minus the payload's exclusion set), that it is byte-for-byte
reproducible, and that it refuses to build from something that is not the release tree.
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from skips import reason

PKG_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("build_core_js_asset", PKG_ROOT / "scripts" / "build_core_js_asset.py")
asset = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = asset  # dataclasses look their module up in sys.modules
_spec.loader.exec_module(asset)
CONTRACT = json.loads((PKG_ROOT / "contracts" / "release_platforms.json").read_text(encoding="utf-8"))

_GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture_tree(root: Path, *, version: str = "1.2.3") -> Path:
    """A miniature skill checkout: pyproject + horosa-core-js with one production and one dev dependency installed."""
    _write(root / "pyproject.toml", f'[project]\nname = "x"\nversion = "{version}"\n')
    core = root / "horosa-core-js"
    _write(core / "package.json", json.dumps({
        "name": "horosa-core-js", "version": version, "engines": {"node": ">=20.10.0"},
        "dependencies": {"prod-a": "1.0.0"}, "devDependencies": {"dev-b": "2.0.0"},
    }))
    _write(core / "package-lock.json", json.dumps({"lockfileVersion": 3, "packages": {
        "": {"name": "horosa-core-js", "version": version},
        "node_modules/prod-a": {"version": "1.0.0"},
        "node_modules/dev-b": {"version": "2.0.0", "dev": True},
    }}))
    _write(core / "bin" / "cli.mjs", "console.log('cli')\n")
    _write(core / "src" / "tools" / "index.js", "export {}\n")
    _write(core / "dist" / "app-charts.cjs", "module.exports = {}\n")
    _write(core / ".gitignore", "node_modules/\n")
    _write(core / "node_modules" / "prod-a" / "package.json", json.dumps({"name": "prod-a", "version": "1.0.0"}))
    _write(core / "node_modules" / "prod-a" / "index.js", "module.exports = 1\n")
    _write(core / "node_modules" / "prod-a" / "index.js.map", "{}")
    _write(core / "node_modules" / ".bin" / "tool", "#!/bin/sh\n")
    _write(core / "node_modules" / ".package-lock.json", "{}")
    _write(core / "node_modules" / "dev-b" / "package.json", json.dumps({"name": "dev-b", "version": "2.0.0"}))
    subprocess.run([*_GIT, "init", "-q", str(root)], check=True)
    subprocess.run([*_GIT, "-C", str(root), "add", "-A"], check=True)
    subprocess.run([*_GIT, "-C", str(root), "commit", "-q", "-m", "fixture"], check=True)
    return root


def _names(archive: Path) -> list[str]:
    with tarfile.open(archive, "r:gz") as tar:
        return tar.getnames()


def test_the_exclusion_set_is_the_darwin_payloads() -> None:
    """The asset claims «same file selection as the runtime payload»: the rsync filters and EXCLUDE_PATTERNS move together."""
    script = (PKG_ROOT / "scripts" / "package_runtime_payload.sh").read_text(encoding="utf-8")
    block = re.search(r"RSYNC_FILTERS=\((.*?)\n\)", script, re.S)
    assert block, "RSYNC_FILTERS block not found in package_runtime_payload.sh"
    patterns = {re.sub(r"^\*/", "", item) for item in re.findall(r"""["']--exclude=([^"']+)["']""", block.group(1))}
    assert patterns == set(asset.EXCLUDE_PATTERNS)


def test_asset_holds_tracked_files_and_production_packages_only(tmp_path: Path) -> None:
    root = _fixture_tree(tmp_path / "skill")
    result = asset.build(skill_root=root, out_dir=tmp_path / "out")
    names = _names(Path(result["path"]))
    assert result["name"] == "horosa-core-js-v1.2.3.tar.gz" and result["node_floor"] == ">=20.10.0"
    assert result["dependencies"] == {"prod-a": "1.0.0"}
    assert all(name == "horosa-core-js" or name.startswith("horosa-core-js/") for name in names)
    for wanted in ("bin/cli.mjs", "package.json", "package-lock.json", "src/tools/index.js", "dist/app-charts.cjs",
                   "node_modules/prod-a/package.json", "node_modules/prod-a/index.js"):
        assert f"horosa-core-js/{wanted}" in names, wanted
    for unwanted in ("node_modules/dev-b", "node_modules/.bin", "node_modules/.package-lock.json", "index.js.map"):
        assert not any(unwanted in name for name in names), unwanted


def test_two_builds_of_the_same_tree_are_byte_identical(tmp_path: Path) -> None:
    root = _fixture_tree(tmp_path / "skill")
    first = asset.build(skill_root=root, out_dir=tmp_path / "a")
    (root / "horosa-core-js" / "bin" / "cli.mjs").touch()  # a newer mtime on disk must not change the bytes
    second = asset.build(skill_root=root, out_dir=tmp_path / "b")
    assert first["sha256"] == second["sha256"]
    with tarfile.open(first["path"], "r:gz") as tar:
        members = tar.getmembers()
    assert {m.mtime for m in members} == {asset.FIXED_MTIME} and {m.uid for m in members} == {0}
    assert [m.name for m in members] == sorted(m.name for m in members)
    raw = Path(first["path"]).read_bytes()
    assert raw[4:8] == b"\x00\x00\x00\x00", "gzip header mtime must be 0"


def test_a_tree_that_differs_from_head_is_refused(tmp_path: Path) -> None:
    root = _fixture_tree(tmp_path / "skill")
    (root / "horosa-core-js" / "src" / "tools" / "index.js").write_text("export const changed = 1\n", encoding="utf-8")
    with pytest.raises(asset.BuildError, match="differs from HEAD"):
        asset.build(skill_root=root, out_dir=tmp_path / "out")
    assert asset.build(skill_root=root, out_dir=tmp_path / "out", allow_dirty=True)["files"] > 0


def test_node_modules_that_do_not_match_the_lock_are_refused(tmp_path: Path) -> None:
    root = _fixture_tree(tmp_path / "skill")
    (root / "horosa-core-js" / "node_modules" / "prod-a" / "package.json").write_text(
        json.dumps({"name": "prod-a", "version": "0.9.0"}), encoding="utf-8")
    with pytest.raises(asset.BuildError, match="prod-a is 0.9.0"):
        asset.build(skill_root=root, out_dir=tmp_path / "out")
    shutil.rmtree(root / "horosa-core-js" / "node_modules" / "prod-a")
    with pytest.raises(asset.BuildError, match="prod-a is not installed"):
        asset.build(skill_root=root, out_dir=tmp_path / "out")


def test_engine_version_must_move_with_the_release(tmp_path: Path) -> None:
    root = _fixture_tree(tmp_path / "skill")
    with pytest.raises(asset.BuildError, match="bump_version"):
        asset.build(skill_root=root, out_dir=tmp_path / "out", version="1.2.4")


def test_a_symlink_inside_a_package_is_refused(tmp_path: Path) -> None:
    root = _fixture_tree(tmp_path / "skill")
    link = root / "horosa-core-js" / "node_modules" / "prod-a" / "escape"
    try:
        link.symlink_to(tmp_path)
    except OSError:
        pytest.skip(reason("host", "cannot create symlinks here"))
    with pytest.raises(asset.BuildError, match="symlink"):
        asset.build(skill_root=root, out_dir=tmp_path / "out")


def test_the_real_tree_builds_with_every_contracted_entry(tmp_path: Path) -> None:
    core = PKG_ROOT / "horosa-core-js"
    package = json.loads((core / "package.json").read_text(encoding="utf-8"))
    if not all((core / "node_modules" / dep / "package.json").is_file() for dep in package["dependencies"]):
        pytest.skip(reason("host", "horosa-core-js/node_modules not installed (npm ci --omit=dev)"))
    result = asset.build(skill_root=PKG_ROOT, out_dir=tmp_path, allow_dirty=True)
    names = set(_names(Path(result["path"])))
    spec = CONTRACT["core_js"]
    assert result["name"] == spec["asset"].format(version=package["version"])
    assert result["node_floor"] == spec["node_floor"] == package["engines"]["node"]
    for entry in spec["required_entries"]:
        assert f"{spec['root']}/{entry}" in names, entry
    for dep in package["dependencies"]:
        assert f"{spec['root']}/node_modules/{dep}/package.json" in names, dep
    assert not any("/node_modules/esbuild" in name or "/node_modules/d3/" in name for name in names), "dev deps leaked"


def test_lockfile_root_mirrors_package_json() -> None:
    """package-lock.json 的根条目（packages[""]）必须与 package.json 逐字段一致。

    v0.50.0 发布时 package.json 的 engines 说明改了、锁文件没跟：发布第 1 步 `npm install --omit=dev` 把锁文件改写，
    第 2 步 build_core_js_asset 见树不干净拒绝出资产——红在发版当场。改 package.json 后跑 `npm install --package-lock-only`。"""
    core = PKG_ROOT / "horosa-core-js"
    package = json.loads((core / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((core / "package-lock.json").read_text(encoding="utf-8"))
    root = lock["packages"][""]
    assert lock["name"] == package["name"] and lock["version"] == package["version"] == root["version"]
    for key in ("dependencies", "devDependencies", "engines", "license"):  # bin 被 npm 规范化（去掉 ./），不比
        assert root.get(key) == package.get(key), f"package-lock.json 根条目的 {key} 与 package.json 不一致"
