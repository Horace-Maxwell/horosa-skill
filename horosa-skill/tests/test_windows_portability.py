"""macOS 绿 ≠ Windows 绿：本机就能抓到的那几类（v0.50.1-dev，v0.50.0 main CI windows-smoke 红 13 条之后）。

- 相对路径拿 `str(p.relative_to(root))` 当键 / 拿去比：Windows 上是 `runners\\mingli.py`，和写死的 `runners/mingli.py` 永远对不上
  （test_era_pairing 两红）。一律 `.as_posix()`。
- `with sqlite3.connect(...) as conn:` 只提交、不关连接：Windows 上那个库（和 -wal / -shm）就删不掉、挪不走（WinError 32，4 红）。
  一律 `with closing(sqlite3.connect(...)) as conn[, conn]:`。
- 开着的文件改名 / 删除：tests/winsim.py 在本机按 Windows 的规则拒绝（conftest 让每条用例都在它下面跑）；这里证明它真的会拒。
"""
from __future__ import annotations

import ast
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

import pytest
import winsim

PKG_ROOT = Path(__file__).resolve().parents[1]
SCANNED = ("src", "tests", "scripts")


def _python_files() -> list[Path]:
    return [path for base in SCANNED for path in sorted((PKG_ROOT / base).rglob("*.py"))]


def str_of_relative_to(source: str) -> list[int]:
    """`str(<x>.relative_to(...))` 的行号（f-string 里的不算：那是给人看的消息）。"""
    return [
        node.lineno for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "str" and node.args
        and isinstance(node.args[0], ast.Call) and isinstance(node.args[0].func, ast.Attribute)
        and node.args[0].func.attr == "relative_to"
    ]


def bare_sqlite_context(source: str) -> list[int]:
    """`with sqlite3.connect(...) as x:` / `with connect(...)`（来自 sqlite3）——连接的 with 只管事务，不关连接。"""
    tree = ast.parse(source)
    imported = {alias.asname or alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
                and node.module == "sqlite3" for alias in node.names if alias.name == "connect"}
    hits: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.With | ast.AsyncWith):
            continue
        for item in node.items:
            call = item.context_expr
            if not isinstance(call, ast.Call):
                continue
            func = call.func
            if (isinstance(func, ast.Attribute) and func.attr == "connect" and isinstance(func.value, ast.Name)
                    and func.value.id == "sqlite3") or (isinstance(func, ast.Name) and func.id in imported):
                hits.append(node.lineno)
    return hits


def test_relative_paths_are_built_with_as_posix() -> None:
    hits = [f"{path.relative_to(PKG_ROOT).as_posix()}:{line}" for path in _python_files()
            for line in str_of_relative_to(path.read_text(encoding="utf-8"))]
    assert hits == [], "Windows 上 str(relative_to) 是反斜杠，拿去当键或比较会对不上：改用 .as_posix() → " + ", ".join(hits)


def test_sqlite_connections_are_closed_not_just_committed() -> None:
    hits = [f"{path.relative_to(PKG_ROOT).as_posix()}:{line}" for path in _python_files()
            for line in bare_sqlite_context(path.read_text(encoding="utf-8"))]
    assert hits == [], ("`with sqlite3.connect()` 不关连接，Windows 上库文件删不掉、挪不走："
                        "改成 `with closing(sqlite3.connect(...)) as conn, conn:` → " + ", ".join(hits))


def test_the_source_guards_can_go_red() -> None:
    assert str_of_relative_to("key = str(path.relative_to(root))\nmsg = f'{path.relative_to(root)}'\n") == [1]
    assert str_of_relative_to("key = path.relative_to(root).as_posix()\n") == []
    assert bare_sqlite_context("import sqlite3\nwith sqlite3.connect(p) as c:\n    pass\n") == [2]
    assert bare_sqlite_context("from sqlite3 import connect\nwith connect(p) as c:\n    pass\n") == [2]
    assert bare_sqlite_context("import sqlite3\nfrom contextlib import closing\nwith closing(sqlite3.connect(p)) as c, c:\n    pass\n") == []


@pytest.mark.skipif(not winsim.active(), reason="[platform] Windows 上是真规则；拿不到描述符路径的平台装不了模拟")
def test_the_simulator_refuses_what_windows_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    refused = winsim.windows_sharing(monkeypatch)  # conftest 已装：拿到的是同一份记录
    db = tmp_path / "data" / "x.db"
    db.parent.mkdir()
    leaked = sqlite3.connect(db)  # noqa: SIM115 - 故意不关：这正是 Windows 上删不掉的情形
    leaked.execute("CREATE TABLE t(x)")
    with pytest.raises(PermissionError) as caught:
        db.unlink()
    assert getattr(caught.value, "winerror", None) == 32
    with pytest.raises(PermissionError):
        db.replace(tmp_path / "moved.db")
    with pytest.raises(PermissionError):
        os.rename(db.parent, tmp_path / "moved-dir")  # 含开着文件的目录同样挪不动
    leaked.close()
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("INSERT INTO t VALUES (1)")
    db.replace(tmp_path / "moved.db")  # 关了就能挪
    assert len(refused) == 3
    with tempfile.TemporaryFile() as handle:  # POSIX 的 TemporaryFile 是「开着就删」：Windows 不走这条，不算
        handle.write(b"x")
    refused.clear()
