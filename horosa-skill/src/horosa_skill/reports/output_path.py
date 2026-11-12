"""报告落盘路径：事前检查与不撞名的缺省文件名（v0.50.0）。

`output_path` 过了「只能写在输出根之内」的闸（service/api/reports.py::_report_output_path）之后，还有四件事此前没人管，
全都是「调用成功、文件却不是调用方以为的那个」：

- 给的是个目录 → 渲染失败，退化成一份写在**目录旁边**的 TXT；
- 扩展名和 format 对不上（`x.docx` + format=pdf）→ `.docx` 里装着 PDF 字节；没写扩展名 → 一个没有扩展名的 PDF；
- 文件名太长 → `tempfile.mkstemp` 抛裸 OSError，穿出错误信封；
- 缺省文件名只精确到秒 → 同一秒内对同一条 run 出两份（排盘版 + 解读版，或并发）后写的盖掉先写的。

还有一件是丢数据（v0.50.0 评审 C-05）：输出根就是存档目录 `<data>/runs`，点名一个已有文件就原样替换——run 自己的存档、
manifest 都能被一份报告盖掉，之后这条 run 再也出不了报告。现在只替换「报告写出来、记在记忆库里」的文件；记忆库、trace、
档案、自备知识库、runtime 这些存储区一律不写。要不要加一个显式的覆盖开关，留给维护者定（见 docs/LESSONS.md）。

这里的检查都没有副作用（不建目录、不写文件），所以能放在「起盘 / 写回 AI 解读」之前；`reserve` / `claim_exact` 才真的占名字。
"""
from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from horosa_skill.errors import ToolValidationError, bilingual

# 各格式落盘的扩展名（markdown 只有技法依据报告用）。
FORMAT_SUFFIXES: dict[str, tuple[str, ...]] = {
    "pdf": (".pdf",),
    "docx": (".docx",),
    "json": (".json",),
    "png": (".png",),
    "ics": (".ics",),
    "markdown": (".md", ".markdown"),
}

# 明确指着「另一种文件」的扩展名：format 与它对不上就是调用方两处说法矛盾，替它猜哪一处对都可能猜错。
# 不在这张表里的后缀（`报告.终稿`、`v1.2`）只是名字里带点，补上正确扩展名即可。
_OTHER_TYPE_SUFFIXES = frozenset({
    ".pdf", ".docx", ".doc", ".json", ".png", ".ics", ".md", ".markdown", ".txt", ".rtf", ".odt", ".html", ".htm",
    ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".csv", ".xlsx", ".xls", ".pptx", ".xml", ".yaml", ".yml", ".zip",
})

# 单个文件名的上限。各家文件系统是 255（APFS / ext4 按 UTF-8 字节，NTFS 按 UTF-16 单元）；留出多图的 `_12`、
# 占用另存的 ` (99)`、撞名的 `-99` 这些后缀的余量。
MAX_NAME_BYTES = 240

_RESERVE_ATTEMPTS = 1000


@dataclass(frozen=True)
class OutputRequest:
    """调用方的 `output_path` 经检查后的含义。

    kind = "default"（没给）/ "directory"（给的是目录：缺省文件名写进这个目录）/ "file"（就是这个文件）。
    `adjustment` 记下「落盘路径和调用方写的不一样」的原因，原样进结果。"""

    kind: str
    path: Path | None = None
    adjustment: dict[str, Any] | None = None
    requested: str = ""


def unusable(reason: str, zh: str, en: str, **details: Any) -> ToolValidationError:
    return ToolValidationError(
        bilingual(f"output_path 用不了：{zh}", f"output_path cannot be used: {en}"),
        code="report.output_path_unusable",
        details={"reason": reason, **details},
    )


def _refused_by_system(exc: OSError, path: Path, requested: str) -> ToolValidationError:
    """系统连看都不让看的路径（整条路径超过 PATH_MAX、含它不认的字符）：stat 抛的是 OSError，不是「不存在」。"""
    return unusable(
        "path_refused_by_system",
        f"系统不接受这个路径（{exc.strerror or type(exc).__name__}）。换一个短一点、层级浅一点的路径。",
        f"the system rejects this path ({exc.strerror or type(exc).__name__}). Use a shorter, shallower path.",
        requested=requested, errno=exc.errno, path_bytes=len(str(path).encode("utf-8", "surrogatepass")),
    )


def names_a_directory(text: str, resolved: Path) -> bool:
    """以分隔符结尾，或已经是个目录。"""
    seps = {"/", os.sep} | ({os.altsep} if os.altsep else set())
    if text.rstrip()[-1:] in seps:
        return True
    try:
        return resolved.is_dir()
    except OSError as exc:
        raise _refused_by_system(exc, resolved, text) from exc


def _name_units(name: str) -> int:
    return max(len(name.encode("utf-8", "surrogatepass")), len(name.encode("utf-16-le", "surrogatepass")) // 2)


def check_names(path: Path, *, requested: str) -> None:
    for part in path.parts[1:] if path.is_absolute() else path.parts:
        size = _name_units(part)
        if size > MAX_NAME_BYTES:
            shown = part[:40] + "…"
            raise unusable(
                "name_too_long",
                f"文件名太长（「{shown}」有 {size} 字节，上限 {MAX_NAME_BYTES}）。换一个短一点的名字。",
                f"the file name is too long (\"{shown}\" is {size} bytes; the limit is {MAX_NAME_BYTES}). Use a shorter name.",
                requested=requested, name_bytes=size, limit=MAX_NAME_BYTES,
            )


def check_writable(path: Path, *, requested: str) -> None:
    """目标所在位置写得进去：往上找到第一个已存在的祖先，它得是个可写、可进入的目录。不建任何东西。"""
    ancestor = path.parent
    try:
        while not ancestor.exists() and ancestor.parent != ancestor:
            ancestor = ancestor.parent
        is_directory = ancestor.is_dir()
    except OSError as exc:
        raise _refused_by_system(exc, path, requested) from exc
    if not is_directory:
        raise unusable(
            "parent_not_directory",
            f"路径里的 {ancestor} 是个文件，不是目录，没法往里写。",
            f"{ancestor} in the path is a file, not a directory, so nothing can be written under it.",
            requested=requested, blocking_path=str(ancestor),
        )
    if not os.access(ancestor, os.W_OK | os.X_OK):
        raise unusable(
            "not_writable",
            f"目录 {ancestor} 没有写权限。换一个目录，或请用户放开权限。",
            f"the directory {ancestor} is not writable. Choose another directory, or ask the user to grant write access.",
            requested=requested, blocking_path=str(ancestor),
        )


def with_format_suffix(path: Path, format_name: str, *, requested: str) -> tuple[Path, dict[str, Any] | None]:
    """让文件名的扩展名和 format 一致：对得上原样；没有扩展名（或只是名字里带点）补上并记一笔；指着另一种文件 → 拒绝。"""
    expected = FORMAT_SUFFIXES[format_name]
    suffix = path.suffix.lower()
    if suffix in expected:
        return path, None
    if suffix in _OTHER_TYPE_SUFFIXES:
        raise unusable(
            "extension_mismatch",
            f"文件名的扩展名是 {path.suffix}，format 却是 {format_name}，两处对不上。"
            f"要 {format_name} 就把扩展名改成 {expected[0]}（或不写扩展名）；要的是别的格式就改 format。",
            f"the file name ends in {path.suffix} but format is {format_name}. For {format_name}, use the extension "
            f"{expected[0]} (or leave it off); for another format, change `format`.",
            requested=requested, extension=path.suffix, format=format_name, expected_extension=expected[0],
        )
    fixed = path.with_name(path.name + expected[0])
    return fixed, {"requested": requested, "reason": "extension_added", "extension": expected[0]}


def check_not_store_area(path: Path, *, protected: Iterable[Path], requested: str) -> None:
    """不往星阙自己的存储区里写：记忆库文件本身（含 -wal / -shm）、trace、档案、自备知识库、runtime。
    `protected` 里是文件就比文件，是目录就比「在它之内」。"""
    for area in protected:
        if path == area or area in path.parents:
            raise unusable(
                "store_area",
                f"{area} 是星阙自己的存储区，报告不能写在这里（会损坏记忆库 / 档案）。写到报告输出目录里一个新的文件名。",
                f"{area} is Horosa's own storage, so a report must not be written there (it would damage the memory store / "
                "profiles). Write to a new file name inside the report output directory.",
                requested=requested, protected_path=str(area),
            )


def refuse_existing(path: Path, *, requested: str) -> ToolValidationError:
    return unusable(
        "existing_file",
        f"{path} 已经存在，而且不是星阙写出来的报告（可能是这条记录的存档、manifest 或你自己的文件），不替换它。"
        "换一个新的文件名，或给一个目录让报告用缺省文件名。",
        f"{path} already exists and is not a report Horosa wrote (it may be this run's stored result, its manifest, or "
        "a file of your own), so it is not replaced. Use a new file name, or pass a directory to get the default name.",
        requested=requested, existing_path=str(path),
    )


def check_replaceable(path: Path, *, may_replace: Callable[[Path], bool], requested: str) -> None:
    """点名的文件已经在：只有报告自己写过（记忆库里记着）的才能替换。"""
    try:
        exists = path.exists() or path.is_symlink()
    except OSError as exc:
        raise _refused_by_system(exc, path, requested) from exc
    if exists and not (path.is_file() and not path.is_symlink() and may_replace(path)):
        raise refuse_existing(path, requested=requested)


def numbered(path: Path, count: int) -> list[Path]:
    """一张图一个文件：多张时在文件名后加 _1、_2…"""
    if count == 1:
        return [path]
    return [path.with_name(f"{path.stem}_{index}{path.suffix}") for index in range(1, count + 1)]


def _create_exclusive(path: Path) -> bool:
    try:
        os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644))
    except FileExistsError:
        return False
    return True


def reserve_set(path: Path, count: int = 1) -> list[Path]:
    """原子地占住一组还没有人用的文件名（各建一个空文件）：`名字.pdf` 已有就试 `名字-2.pdf`、`名字-3.pdf`…；
    多张图时是 `名字_1.png … 名字_k.png` 整组一起占（组里有一个被占就整组换下一个名字，不和上一次的 `_2` 混在一起）。
    同一秒内的两次调用、两个进程都各拿到各的名字。渲染结果随后 os.replace 到这些名字上；没写成由 `release` 收走空壳。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    for index in range(1, _RESERVE_ATTEMPTS + 1):
        candidate = path if index == 1 else path.with_name(f"{path.stem}-{index}{path.suffix}")
        taken: list[Path] = []
        for member in numbered(candidate, count):
            if not _create_exclusive(member):
                break
            taken.append(member)
        else:
            return taken
        for member in taken:
            release(member)
    raise unusable(
        "no_free_name",
        f"{path.parent} 里以 {path.stem} 开头的名字都被占了。给一个明确的 output_path。",
        f"every name starting with {path.stem} in {path.parent} is taken. Pass an explicit output_path.",
        requested=str(path),
    )


def reserve(path: Path) -> Path:
    return reserve_set(path, 1)[0]


def claim_exact(paths: list[Path], *, may_replace: Callable[[Path], bool], requested: str) -> list[Path]:
    """调用方点名的文件：不存在就原子地占住（空文件，返回在占位列表里）；已存在只有报告自己写过的才让替换。
    事前检查与这里之间被别人抢先建出来的文件，同样按「不是报告就不替换」处理。"""
    paths[0].parent.mkdir(parents=True, exist_ok=True)
    taken: list[Path] = []
    try:
        for path in paths:
            if _create_exclusive(path):
                taken.append(path)
            else:
                check_replaceable(path, may_replace=may_replace, requested=requested)
    except BaseException:
        for member in taken:
            release(member)
        raise
    return taken


def release(path: Path | None) -> None:
    """占位的空文件还在（这次没有东西写到这个名字上：失败、退化成 TXT、多图改用了带序号的名字）就拿掉。"""
    if path is None:
        return
    try:
        if path.is_file() and path.stat().st_size == 0:
            path.unlink()
    except OSError:
        pass
