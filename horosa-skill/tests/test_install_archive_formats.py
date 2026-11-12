"""`install --archive`：归档格式看内容不看文件名；任何坏归档都是结构化拒绝；文档里的配方真的跑得通。

**为什么旧检查抓不到**：全仓的 `--archive` 测试都拿 `create_runtime_archive` 生成的 `runtime-payload.tar.gz` 喂安装器——
文件名与内容永远一致。而 README / INSTALL_RESTRICTED_NETWORK 教用户的是 `curl -o runtime.zip <资产直链>`：macOS 资产是
tar.gz，存成 `runtime.zip` 之后按后缀走 `zipfile`，`BadZipFile` 没人接，用户看到的是一屏 traceback。企业代理把登录页 /
错误页当 200 返回、下载中断留下半个文件，是同一个口子（`tarfile.ReadError` / `EOFError`）。

docs/LESSONS.md v0.50.0-dev「归档格式按后缀判」。
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import tarfile
import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from horosa_skill.config import Settings
from horosa_skill.errors import RuntimeInstallError, RuntimeValidationError
from horosa_skill.runtime import HorosaRuntimeManager
from horosa_skill.runtime import archives
from horosa_skill.surfaces import cli
from test_runtime_manager import _managed_mode, create_runtime_archive  # noqa: F401

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER = CliRunner()


def _manager(tmp_path: Path) -> HorosaRuntimeManager:
    return HorosaRuntimeManager(Settings(runtime_root=tmp_path / "runtime-root", runtime_platform="darwin-arm64"))


def _zip_of_payload(tmp_path: Path, name: str = "payload.zip") -> Path:
    """与 tar.gz 夹具同一棵载荷树，打成 zip（Windows 资产的形状）。"""
    create_runtime_archive(tmp_path)
    target = tmp_path / name
    root = tmp_path / "runtime-payload"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            archive.write(path, arcname=str(Path("runtime-payload") / path.relative_to(root)))
    return target


def _json_tail(text: str) -> dict:
    """install 先往 stderr 打一行进度提示，JSON 在其后。"""
    return json.loads(text[text.index("{"):])


def _renamed(source: Path, name: str) -> Path:
    target = source.parent / name
    shutil.copyfile(source, target)
    return target


# ---- 格式看内容 -------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["runtime.zip", "runtime", "runtime.bin", "runtime.tar.gz"])
def test_a_tar_gz_installs_whatever_it_is_called(tmp_path: Path, name: str) -> None:
    archive = _renamed(create_runtime_archive(tmp_path), name)

    result = _manager(tmp_path).install(archive=str(archive))

    assert result["ok"] is True and result["manifest"]["version"] == "1.2.3"
    assert (tmp_path / "runtime-root" / "current" / "runtime-manifest.json").is_file()


@pytest.mark.parametrize("name", ["runtime.tar.gz", "runtime", "runtime.zip"])
def test_a_zip_installs_whatever_it_is_called(tmp_path: Path, name: str) -> None:
    archive = _renamed(_zip_of_payload(tmp_path), name)

    result = _manager(tmp_path).install(archive=str(archive))

    assert result["ok"] is True and result["manifest"]["version"] == "1.2.3"


def test_sniff_names_what_the_bytes_are(tmp_path: Path) -> None:
    tar_gz = create_runtime_archive(tmp_path)
    assert archives.sniff_format(tar_gz) == "tar.gz"
    assert archives.sniff_format(_zip_of_payload(tmp_path)) == "zip"
    html = tmp_path / "page.zip"
    html.write_bytes(b"\n  <!DOCTYPE html><html><head><title>Sign in</title></head></html>")
    assert archives.sniff_format(html) == "html"
    empty = tmp_path / "empty.zip"
    empty.write_bytes(b"")
    assert archives.sniff_format(empty) == "empty"
    noise = tmp_path / "noise.tar.gz"
    noise.write_bytes(bytes(range(7, 200)))
    assert archives.sniff_format(noise) == "unknown"
    plain_tar = tmp_path / "plain.bin"
    with tarfile.open(plain_tar, "w") as archive:
        archive.add(tmp_path / "runtime-payload" / "runtime-manifest.json", arcname="runtime-payload/runtime-manifest.json")
    assert archives.sniff_format(plain_tar) == "tar"


# ---- 坏归档：一律 runtime.install_archive_invalid，不留半装 ---------------------------------------


def _bad_archives(tmp_path: Path) -> dict[str, Path]:
    good = create_runtime_archive(tmp_path)
    good_zip = _zip_of_payload(tmp_path)
    out: dict[str, Path] = {}
    out["html_as_zip"] = tmp_path / "html.zip"
    out["html_as_zip"].write_bytes(b"<!DOCTYPE html>\n<html><body>404: Not Found</body></html>\n")
    out["json_error_as_tar"] = tmp_path / "error.tar.gz"
    out["json_error_as_tar"].write_bytes(b'{"message":"Not Found","status":"404"}')
    out["empty"] = tmp_path / "empty.zip"
    out["empty"].write_bytes(b"")
    out["noise"] = tmp_path / "noise.zip"
    out["noise"].write_bytes(bytes(range(7, 250)) * 20)
    out["truncated_tar_gz"] = tmp_path / "trunc.tar.gz"
    out["truncated_tar_gz"].write_bytes(good.read_bytes()[: good.stat().st_size // 2])
    out["truncated_zip"] = tmp_path / "trunc.zip"
    out["truncated_zip"].write_bytes(good_zip.read_bytes()[: good_zip.stat().st_size // 2])
    out["gzip_but_not_tar"] = tmp_path / "notatar.tar.gz"
    import gzip

    out["gzip_but_not_tar"].write_bytes(gzip.compress(b"just some text, not a tar stream\n" * 50))
    return out


BAD_KINDS = ["html_as_zip", "json_error_as_tar", "empty", "noise", "truncated_tar_gz", "truncated_zip", "gzip_but_not_tar"]


@pytest.mark.parametrize("kind", BAD_KINDS)
def test_a_bad_archive_is_a_structured_refusal(tmp_path: Path, kind: str) -> None:
    archive = _bad_archives(tmp_path)[kind]
    manager = _manager(tmp_path)

    with pytest.raises(RuntimeInstallError) as caught:
        manager.install(archive=str(archive))

    assert caught.value.code == "runtime.install_archive_invalid"
    details = caught.value.details
    assert details["archive"] == str(archive)
    assert details["size_bytes"] == archive.stat().st_size
    assert " / " in details["next_action"]  # 双语
    if kind.startswith("html"):
        assert details["detected_format"] == "html"
    # 没装上就什么都不留：current 不存在，临时解压目录已清
    root = tmp_path / "runtime-root"
    assert not (root / "current").exists()
    assert [p.name for p in root.iterdir() if p.name.startswith(".hi-")] == []


def test_a_bad_archive_leaves_the_installed_runtime_alone(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    manager.install(archive=str(create_runtime_archive(tmp_path)))
    before = (tmp_path / "runtime-root" / "current" / "runtime-manifest.json").read_text(encoding="utf-8")

    with pytest.raises(RuntimeInstallError) as caught:
        manager.install(archive=str(_bad_archives(tmp_path)["truncated_tar_gz"]), force=True)

    assert caught.value.code == "runtime.install_archive_invalid"
    assert (tmp_path / "runtime-root" / "current" / "runtime-manifest.json").read_text(encoding="utf-8") == before


@pytest.mark.parametrize("kind", BAD_KINDS)
def test_cli_prints_a_refusal_not_a_traceback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    archive = _bad_archives(tmp_path)[kind]
    monkeypatch.setenv("HOROSA_RUNTIME_ROOT", str(tmp_path / "runtime-root"))
    monkeypatch.setenv("HOROSA_SKILL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("HOROSA_RUNTIME_PLATFORM", "darwin-arm64")

    result = RUNNER.invoke(cli.app, ["install", "--archive", str(archive)])

    assert result.exit_code != 0
    assert result.exception is None or isinstance(result.exception, SystemExit), repr(result.exception)
    assert "Traceback" not in result.output
    payload = _json_tail(result.stderr)
    assert payload["ok"] is False and payload["code"] == "runtime.install_archive_invalid"


# ---- --sha256 ---------------------------------------------------------------------------------


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_sha256_pin_accepts_the_right_archive(tmp_path: Path) -> None:
    archive = create_runtime_archive(tmp_path)

    result = _manager(tmp_path).install(archive=str(archive), sha256=_sha(archive).upper())

    assert result["ok"] is True and result["archive_sha256"] == _sha(archive)
    assert result["sha256_verified"] is True


def test_without_a_pin_the_result_says_the_archive_was_not_verified(tmp_path: Path) -> None:
    archive = create_runtime_archive(tmp_path)

    result = _manager(tmp_path).install(archive=str(archive))

    assert result["sha256_verified"] is False and result["archive_sha256"] == _sha(archive)


def test_sha256_pin_rejects_another_archive_before_extracting(tmp_path: Path) -> None:
    archive = create_runtime_archive(tmp_path)
    manager = _manager(tmp_path)

    with pytest.raises(RuntimeValidationError) as caught:
        manager.install(archive=str(archive), sha256="0" * 64)

    assert caught.value.code == "runtime.install_sha256_mismatch"
    assert caught.value.details["expected_sha256"] == "0" * 64
    assert caught.value.details["actual_sha256"] == _sha(archive)
    assert not (tmp_path / "runtime-root" / "current").exists()


@pytest.mark.parametrize("value", ["abc", "sha256:" + "g" * 64, "0" * 63, ""])
def test_a_malformed_sha256_is_refused_up_front(tmp_path: Path, value: str) -> None:
    archive = create_runtime_archive(tmp_path)
    manager = _manager(tmp_path)

    if value == "":
        assert manager.install(archive=str(archive), sha256=value)["ok"] is True  # 空串 = 没给
        return
    with pytest.raises(RuntimeInstallError) as caught:
        manager.install(archive=str(archive), sha256=value)
    assert caught.value.code == "runtime.install_sha256_invalid"


def test_sha256_accepts_the_prefixed_form_github_prints(tmp_path: Path) -> None:
    archive = create_runtime_archive(tmp_path)

    result = _manager(tmp_path).install(archive=str(archive), sha256=f"sha256:{_sha(archive)}")

    assert result["sha256_verified"] is True


def test_a_pin_that_disagrees_with_the_manifest_is_refused_before_download(tmp_path: Path) -> None:
    archive = create_runtime_archive(tmp_path)
    manifest = tmp_path / "release-manifest.json"
    manifest.write_text(json.dumps({"version": "1.2.3", "platforms": {"darwin-arm64": {
        "url": archive.resolve().as_uri(), "sha256": _sha(archive), "archive_type": "tar.gz"}}}), encoding="utf-8")
    manager = _manager(tmp_path)

    with pytest.raises(RuntimeValidationError) as caught:
        manager.install(manifest_url=str(manifest), sha256="1" * 64)

    assert caught.value.code == "runtime.install_sha256_mismatch"
    assert caught.value.details["manifest_sha256"] == _sha(archive)


def test_cli_install_takes_sha256(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = _renamed(create_runtime_archive(tmp_path), "runtime.zip")
    monkeypatch.setenv("HOROSA_RUNTIME_ROOT", str(tmp_path / "runtime-root"))
    monkeypatch.setenv("HOROSA_SKILL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("HOROSA_RUNTIME_PLATFORM", "darwin-arm64")

    bad = RUNNER.invoke(cli.app, ["install", "--archive", str(archive), "--sha256", "f" * 64])
    assert bad.exit_code != 0
    assert _json_tail(bad.stderr)["code"] == "runtime.install_sha256_mismatch"

    good = RUNNER.invoke(cli.app, ["install", "--archive", str(archive), "--sha256", _sha(archive)])
    assert good.exit_code == 0, (good.output, repr(good.exception))
    assert _json_tail(good.stdout)["sha256_verified"] is True


# ---- 文档里的配方 -----------------------------------------------------------------------------

_RECIPE_DOCS = ("README.md", "README_EN.md", "docs/INSTALL_RESTRICTED_NETWORK.md")
_RECIPE = re.compile(r"horosa-skill install --archive (?P<name>[\w./<>-]+)")


def _documented_archive_names() -> set[str]:
    names: set[str] = set()
    for relative in _RECIPE_DOCS:
        text = (REPO_ROOT / relative).read_text(encoding="utf-8")
        found = {m.group("name").rstrip(".") for m in _RECIPE.finditer(text)}
        assert found, f"{relative} no longer documents `install --archive <file>`; update this test with the doc"
        names |= found
    return names


def test_the_documented_api_download_recipe_installs_either_platform_asset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """文档教用户 `curl -o <名字> <资产直链>` 再 `install --archive <名字>`：对两个平台的资产、对文档里出现的每个文件名都要成立。"""
    monkeypatch.setenv("HOROSA_SKILL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("HOROSA_RUNTIME_PLATFORM", "darwin-arm64")
    assets = {"tar.gz": create_runtime_archive(tmp_path), "zip": _zip_of_payload(tmp_path)}
    literal_names = sorted(name for name in _documented_archive_names() if "<" not in name)
    assert "runtime.zip" in literal_names or any(name.startswith("runtime") for name in literal_names), literal_names

    for index, name in enumerate(literal_names):
        for kind, asset in assets.items():
            workdir = tmp_path / f"case-{index}-{kind}"
            workdir.mkdir()
            saved = workdir / Path(name).name  # `curl -o <名字>`：名字是文档给的，内容是哪个平台的资产由用户的机器决定
            shutil.copyfile(asset, saved)
            monkeypatch.setenv("HOROSA_RUNTIME_ROOT", str(workdir / "rt"))
            monkeypatch.chdir(workdir)

            result = RUNNER.invoke(cli.app, ["install", "--archive", name])

            assert result.exit_code == 0, (name, kind, result.output, repr(result.exception))
            assert _json_tail(result.stdout)["manifest"]["version"] == "1.2.3"


def test_the_docs_tell_the_user_how_to_verify_a_hand_downloaded_archive() -> None:
    text = (REPO_ROOT / "docs/INSTALL_RESTRICTED_NETWORK.md").read_text(encoding="utf-8")
    assert "--sha256" in text
    assert "runtime.install_archive_invalid" in text
