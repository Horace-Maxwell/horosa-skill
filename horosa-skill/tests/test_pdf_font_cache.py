"""字体集的子字体枚举每个文件只做一次：枚举要把 .ttc 里每个子字体都解析一遍，占了一次 PDF 渲染约七成的时间。

台账：docs/LESSONS.md v0.47.2-dev「每出一份 PDF 都把系统字体集重新解析一遍」。
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from horosa_skill.reports.renderers import _face_index


class CountingFont:
    """假的 TTFont：三个子字体 Face0–Face2，越界抛错（真 reportlab 也是这样结束探测）。"""

    built = 0

    def __init__(self, name: str, path: str, subfontIndex: int = 0) -> None:  # noqa: N803 - reportlab 的参数名
        type(self).built += 1
        if subfontIndex >= 3:
            raise IndexError(subfontIndex)
        self.face = SimpleNamespace(name=f"Face{subfontIndex}".encode())


@pytest.fixture
def collection(tmp_path: Path) -> Path:
    CountingFont.built = 0
    path = tmp_path / "Songti.ttc"
    path.write_bytes(b"collection")
    return path


def test_a_collection_is_only_enumerated_once(collection: Path) -> None:
    """Songti.ttc 一次枚举约 0.3 秒，一份 PDF 查五次；长命的 MCP server 每份报告都重来。"""
    assert _face_index(CountingFont, str(collection), ("Face2",)) == 2
    parsed = CountingFont.built
    assert parsed == 4, "三个子字体 + 一次越界"

    assert _face_index(CountingFont, str(collection), ("Face2",)) == 2
    assert CountingFont.built == parsed


def test_other_names_in_the_same_file_need_no_second_enumeration(collection: Path) -> None:
    """常规体与粗体在同一个文件里，是两次查询、一次枚举。"""
    assert _face_index(CountingFont, str(collection), ("Face0",)) == 0
    parsed = CountingFont.built
    assert _face_index(CountingFont, str(collection), ("Nope", "Face1")) == 1
    assert CountingFont.built == parsed


def test_a_name_the_file_does_not_have_is_still_none(collection: Path) -> None:
    assert _face_index(CountingFont, str(collection), ("Face1",)) == 1
    assert _face_index(CountingFont, str(collection), ("Nope",)) is None


def test_a_changed_font_file_is_enumerated_again(collection: Path) -> None:
    """系统更新字体后序号可能变（`_PDF_FONT_CANDIDATES` 按字面名找就是因为这个），长命进程不能用旧表。"""
    assert _face_index(CountingFont, str(collection), ("Face2",)) == 2
    parsed = CountingFont.built
    stamp = collection.stat().st_mtime + 10
    os.utime(collection, (stamp, stamp))

    assert _face_index(CountingFont, str(collection), ("Face2",)) == 2
    assert CountingFont.built == parsed * 2


def test_a_failed_enumeration_is_not_remembered(collection: Path) -> None:
    class Unreadable(CountingFont):
        def __init__(self, name: str, path: str, subfontIndex: int = 0) -> None:  # noqa: N803
            raise OSError("cannot read font")

    assert _face_index(Unreadable, str(collection), ("Face2",)) is None
    assert _face_index(CountingFont, str(collection), ("Face2",)) == 2


def test_single_face_files_and_unnamed_lookups_parse_nothing(tmp_path: Path) -> None:
    CountingFont.built = 0
    plain = tmp_path / "Arial.ttf"
    plain.write_bytes(b"font")
    assert _face_index(CountingFont, str(plain), ("Face2",)) == 0
    assert _face_index(CountingFont, str(tmp_path / "x.ttc"), None) == 0
    assert CountingFont.built == 0
