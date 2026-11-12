"""runtime 归档解包的「不出目录」防线：tar 的 `filter="data"`、zip 的 CPython 消毒 + `_assert_extracted_within` 纵深断言。

**为什么要这个文件（C-18 第 4 项）**：此前没有任何测试喂过恶意归档——把 `filter="data"` 删掉、把纵深断言改成恒真、
或者干脆不调它，全量测试照样全绿（审计用影子副本实跑过）。防线没有能让它变红的测试，就等于没有防线。
这里每一类穿越形状各一个归档：`..`、绝对路径、逃出目录的符号链接（绝对 / 相对）、经链接写到外面、设备文件；
每例都断言错误码**并且**目录外什么都没写出来。
"""
from __future__ import annotations

import io
import os
import tarfile
import zipfile
from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.errors import RuntimeValidationError
from horosa_skill.runtime import HorosaRuntimeManager, archives


def _manager(tmp_path: Path) -> HorosaRuntimeManager:
    return HorosaRuntimeManager(Settings(runtime_root=tmp_path / "runtime-root", runtime_platform="darwin-arm64"))


def _tar(path: Path, members: list[tuple[tarfile.TarInfo, bytes | None]]) -> Path:
    with tarfile.open(path, "w:gz") as archive:
        for info, data in members:
            if data is not None:
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
            else:
                archive.addfile(info)
    return path


def _file(name: str) -> tuple[tarfile.TarInfo, bytes]:
    return tarfile.TarInfo(name), b"payload"


def _link(name: str, target: str, kind: bytes = tarfile.SYMTYPE) -> tuple[tarfile.TarInfo, None]:
    info = tarfile.TarInfo(name)
    info.type = kind
    info.linkname = target
    return info, None


def _outside_is_untouched(sandbox: Path, extract_dir: Path) -> list[str]:
    """沙箱里解压目录之外出现的任何东西（归档本身除外）。"""
    return sorted(
        p.relative_to(sandbox).as_posix() for p in sandbox.rglob("*")
        if extract_dir not in p.parents and p != extract_dir and p.suffix not in {".gz", ".zip"}
    )


def _refused(tmp_path: Path, archive: Path) -> RuntimeValidationError:
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()
    with pytest.raises(RuntimeValidationError) as exc:
        _manager(tmp_path)._extract_archive(archive, extract_dir)
    assert exc.value.code == "runtime.install_path_traversal"
    assert _outside_is_untouched(tmp_path, extract_dir) == []
    return exc.value


# ---- tar：filter="data" ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "members",
    [
        pytest.param([_file("runtime-payload/ok.txt"), _file("../escaped.txt")], id="dotdot"),
        pytest.param([_file("runtime-payload/../../escaped.txt")], id="dotdot-nested"),
        pytest.param([_link("runtime-payload/out", "../../")], id="relative-symlink-out"),
        pytest.param([_link("runtime-payload/out", "/etc")], id="absolute-symlink"),
        pytest.param([_link("runtime-payload/out", "../.."), _file("runtime-payload/out/escaped.txt")], id="write-through-link"),
        pytest.param([_link("runtime-payload/hard", "../outside.txt", tarfile.LNKTYPE)], id="hardlink-out"),
    ],
)
def test_tar_entries_that_leave_the_directory_are_refused(tmp_path: Path, members) -> None:
    archive = _tar(tmp_path / "evil.tar.gz", members)
    error = _refused(tmp_path, archive)
    assert error.details["archive"] == str(archive)


def test_tar_absolute_names_are_stripped_into_the_directory(tmp_path: Path) -> None:
    """`filter="data"` 先去掉前导 `/`：绝对路径的条目落在解压目录里，不碰真实的绝对路径。"""
    name = f"{tmp_path}/abs-escape.txt"  # 绝对路径指回沙箱：万一真写出去了，看得见、也清得掉
    archive = _tar(tmp_path / "abs.tar.gz", [_file(name)])
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()
    _manager(tmp_path)._extract_archive(archive, extract_dir)
    assert not (tmp_path / "abs-escape.txt").exists()
    assert (extract_dir / name.lstrip("/")).read_bytes() == b"payload"


def test_tar_device_files_are_refused(tmp_path: Path) -> None:
    info = tarfile.TarInfo("runtime-payload/dev")
    info.type = tarfile.CHRTYPE
    info.devmajor, info.devminor = 1, 3
    _refused(tmp_path, _tar(tmp_path / "dev.tar.gz", [(info, None)]))


def test_tar_links_that_stay_inside_still_extract(tmp_path: Path) -> None:
    """对照组：目录内的相对链接是合法 runtime 形状（JDK / Python 的 lib 链接），不能被误拒。"""
    archive = _tar(tmp_path / "ok.tar.gz", [_file("runtime-payload/lib/real.txt"), _link("runtime-payload/current", "lib")])
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()
    assert _manager(tmp_path)._extract_archive(archive, extract_dir) == "tar.gz"
    assert (extract_dir / "runtime-payload" / "current" / "real.txt").read_bytes() == b"payload"


# ---- zip：CPython 消毒 + 纵深断言 ------------------------------------------------------------------


@pytest.mark.parametrize("name", ["../escaped.txt", "runtime-payload/../../escaped.txt", "/abs/escaped.txt", "C:/escaped.txt"])
def test_zip_traversal_names_land_inside_the_directory(tmp_path: Path, name: str) -> None:
    """zipfile 把 `..` / 绝对路径 / 盘符消毒成目录内的相对路径：解包成功，且目录外什么都没有。"""
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr(name, b"payload")
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()
    assert _manager(tmp_path)._extract_archive(archive, extract_dir) == "zip"
    assert _outside_is_untouched(tmp_path, extract_dir) == []
    assert [p.read_bytes() for p in extract_dir.rglob("*") if p.is_file()] == [b"payload"]


def _symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=target.is_dir())
    except OSError as exc:  # Windows 普通账户没有建符号链接的特权（WinError 1314）
        pytest.skip(f"[host] symlinks not permitted on this host: {exc}")


def test_zip_branch_runs_the_containment_check_after_extraction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """zip 分支必须在解包后走纵深断言：换成一个会保留符号链接的解包器（zip-slip 复发的形状），逃出目录的链接要被拒。"""
    outside = tmp_path / "outside"
    outside.mkdir()

    def keeps_symlinks(_path: Path, destination: Path) -> str:
        (destination / "runtime-payload").mkdir()
        _symlink_or_skip(destination / "runtime-payload" / "escape", outside)
        return "zip"

    monkeypatch.setattr(archives, "extract", keeps_symlinks)
    archive = tmp_path / "any.zip"
    archive.write_bytes(b"PK\x05\x06" + b"\x00" * 18)
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()
    with pytest.raises(RuntimeValidationError) as exc:
        _manager(tmp_path)._extract_archive(archive, extract_dir)
    assert exc.value.code == "runtime.install_path_traversal"
    assert exc.value.details["offending_path"].endswith("escape")


def test_containment_check_accepts_inside_links_and_rejects_every_escape(tmp_path: Path) -> None:
    root = tmp_path / "extract"
    (root / "a" / "b").mkdir(parents=True)
    (root / "a" / "b" / "f.txt").write_text("x", encoding="utf-8")
    _symlink_or_skip(root / "a" / "inside", root / "a" / "b")
    HorosaRuntimeManager._assert_extracted_within(root)  # 目录内的链接：放行

    sibling = tmp_path / "extract-sibling"  # 前缀相同的兄弟目录：字符串前缀比较会误放行
    sibling.mkdir()
    for name, target in [("abs", tmp_path), ("rel", Path("..") / ".."), ("prefix", sibling)]:
        link = root / "a" / name
        _symlink_or_skip(link, target)
        with pytest.raises(RuntimeValidationError) as exc:
            HorosaRuntimeManager._assert_extracted_within(root)
        assert exc.value.code == "runtime.install_path_traversal", name
        os.unlink(link)
    HorosaRuntimeManager._assert_extracted_within(root)
