"""runtime 归档：格式看内容（魔数），不看文件名；读不了一律是一种带上下文的错误。

🔴 为什么（v0.50.0-dev，E-04）：旧实现按后缀分流——`.tar.gz` 走 tarfile、`.zip` 走 zipfile、其余交给
`shutil.unpack_archive`（它也按后缀）。而文档教受限网络用户 `curl -o runtime.zip <资产直链>`：macOS 资产是 tar.gz，
存成 `runtime.zip` 就 `BadZipFile`；企业代理把登录页当 200 返回、下载断在一半，是 `tarfile.ReadError` / `EOFError`。
这些异常没人接，用户看到的是一屏 traceback，而不是「你下到的不是归档」。

这里只做三件事：`sniff_format`（看前几百字节）、`list_names`（Windows 长路径预检用）、`extract`。
解压途中的**磁盘 / 权限**错误（OSError）不归这里管：那不是归档坏了，原样冒出去，由调用方按 IO 错误报。
"""
from __future__ import annotations

import gzip
import lzma
import tarfile
import zipfile
import zlib
from pathlib import Path

# 归档本身读不了时可能冒出来的全部异常。注意没有裸 OSError：ENOSPC / EACCES 是磁盘的事。
# `gzip.BadGzipFile` 是 OSError 的子类，单列在这里。
ARCHIVE_READ_ERRORS: tuple[type[BaseException], ...] = (
    tarfile.TarError,
    zipfile.BadZipFile,
    zipfile.LargeZipFile,
    gzip.BadGzipFile,
    lzma.LZMAError,
    zlib.error,
    EOFError,
)

_TAR_MODES = {"tar.gz": "r:gz", "tar.bz2": "r:bz2", "tar.xz": "r:xz", "tar": "r:"}


class ArchiveUnreadable(Exception):
    """归档不是归档 / 读到一半断了。`detected` 是 `sniff_format` 的结论，`reason` 是底层那句话。"""

    def __init__(self, detected: str, reason: str) -> None:
        super().__init__(reason)
        self.detected = detected
        self.reason = reason


def sniff_format(path: Path) -> str:
    """`zip` / `tar.gz` / `tar.bz2` / `tar.xz` / `tar` / `html` / `json` / `empty` / `unknown`。只读开头 512 字节。"""
    try:
        with path.open("rb") as handle:
            head = handle.read(512)
    except OSError:
        return "unknown"
    if not head:
        return "empty"
    if head.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        return "zip"
    if head.startswith(b"\x1f\x8b"):
        return "tar.gz"  # 是不是 tar 要解开才知道；不是的话 extract 会说
    if head.startswith(b"BZh"):
        return "tar.bz2"
    if head.startswith(b"\xfd7zXZ\x00"):
        return "tar.xz"
    if len(head) >= 262 and head[257:262] == b"ustar":
        return "tar"
    text = head.lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if text.startswith((b"<!doctype", b"<html", b"<head", b"<?xml", b"<body")) or b"<html" in text:
        return "html"
    if text.startswith((b"{", b"[")):
        return "json"
    return "unknown"


def list_names(path: Path) -> list[str]:
    """归档里的条目名。读不了返回空列表（预检用：真正的报错留给 `extract`）。"""
    detected = sniff_format(path)
    try:
        if detected == "zip":
            with zipfile.ZipFile(path) as archive:
                return archive.namelist()
        if detected in _TAR_MODES:
            with tarfile.open(path, _TAR_MODES[detected]) as archive:
                return archive.getnames()
    except ARCHIVE_READ_ERRORS:
        return []
    except OSError:
        return []
    return []


def extract(path: Path, destination: Path) -> str:
    """解到 `destination`，返回识别出的格式。归档坏了抛 `ArchiveUnreadable`；磁盘 / 权限错误原样抛 OSError。

    tar 一律 `filter="data"`（拒绝绝对路径、`..` 穿越、设备文件、逃逸的链接）；zip 由 CPython 消毒 `../` 与盘符，
    调用方另有一道「解出来的每个路径都在目录内」的断言。
    """
    detected = sniff_format(path)
    if detected not in _TAR_MODES and detected != "zip":
        raise ArchiveUnreadable(detected, _not_an_archive_reason(detected))
    try:
        if detected == "zip":
            with zipfile.ZipFile(path) as archive:
                archive.extractall(destination)
        else:
            with tarfile.open(path, _TAR_MODES[detected]) as archive:
                archive.extractall(destination, filter="data")
    except tarfile.FilterError:
        raise  # 穿越 / 设备文件：是安全拒绝，不是「归档坏了」，调用方单独报
    except ARCHIVE_READ_ERRORS as exc:
        raise ArchiveUnreadable(detected, f"{type(exc).__name__}: {exc}") from exc
    return detected


def _not_an_archive_reason(detected: str) -> str:
    return {
        "empty": "the file is empty (0 bytes)",
        "html": "the file is an HTML page, not an archive (a login / error page saved by the download?)",
        "json": "the file is JSON text, not an archive (an API error body saved by the download?)",
    }.get(detected, "the file does not start like a zip or tar archive")


__all__ = ["ARCHIVE_READ_ERRORS", "ArchiveUnreadable", "extract", "list_names", "sniff_format"]
