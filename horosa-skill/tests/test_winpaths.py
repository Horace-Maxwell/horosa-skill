r"""Windows 路径形状（v0.47.2-dev，Windows 原生复验）：report output_path 的字符串闸必须在任何文件系统访问之前。

最贵的一条：`Path(r"\\host\share\x.pdf").resolve()` 会真的连 host（SMB + 当前用户 NTLM 凭据），旧实现先 resolve 再判断——
本机对不可路由地址卡 21 秒才「拒绝」，那时凭据已经送出去了。纯函数在每个平台都测；闸的集成按 os.name == "nt" 分支打桩，CI 的 Linux 也跑得到。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from horosa_skill import winpaths
from horosa_skill.errors import ToolValidationError
from horosa_skill.knowledge import user as kb
from horosa_skill.service.api import reports as reports_module
from horosa_skill.service.api.reports import ReportsAPI


@pytest.mark.parametrize("text", [
    r"\\host\share\x.pdf", "//host/share/x.pdf", r"\\?\C:\x.pdf", r"\\.\NUL", r"\\?\GLOBALROOT\Device\Null",
    r"\\?\UNC\host\share\x", "/\\host\\share", "\\/host/share",
])
def test_network_and_device_paths_are_recognised(text: str) -> None:
    assert winpaths.is_network_or_device_path(text)


@pytest.mark.parametrize("text", ["x.pdf", r"sub\x.pdf", r"C:\x.pdf", r"\x.pdf", "/x.pdf", "C:x.pdf", r"sub\\host\x"])
def test_ordinary_paths_are_not_network_paths(text: str) -> None:
    assert not winpaths.is_network_or_device_path(text)


@pytest.mark.parametrize("text", [
    "NUL", "nul.pdf", "CON", "con.PDF", "AUX", "PRN", "COM1.pdf", "LPT9", r"sub\NUL", "sub/CON.txt", "CONIN$", "CONOUT$",
    "COM¹", "LPT²", "NUL .pdf", "x.pdf:stream", "x.pdf::$DATA", "ab:c", "a<b>.pdf", 'a"b.pdf', "a|b.pdf", "a?.pdf", "a*.pdf",
    "\x00evil.pdf", "a\nb.pdf", r"C:\ok\NUL",
])
def test_problem_shapes_are_named(text: str) -> None:
    problem = winpaths.path_problem(text)
    assert problem is not None and all(problem)


@pytest.mark.parametrize("text", [
    "report.pdf", r"sub\report.pdf", "C:report.pdf", r"C:\Users\x\report.pdf", "命盘.pdf", "console.pdf", "nullable.pdf",
    "com10.pdf", "lpt0.pdf", "conin.pdf", r"..\x.pdf", "x.y.z.pdf",
])
def test_ordinary_names_have_no_problem(text: str) -> None:
    assert winpaths.path_problem(text) is None


def test_network_root_match_is_string_only_and_collapses_dotdot() -> None:
    roots = [r"\\nas\share\reports", r"C:\local"]
    assert winpaths.is_under_network_root(r"\\NAS\Share\Reports\sub\x.pdf", roots)
    assert winpaths.is_under_network_root("//nas/share/reports/x.pdf", roots)
    assert not winpaths.is_under_network_root(r"\\nas\share\reports\..\secrets\x.pdf", roots)
    assert not winpaths.is_under_network_root(r"\\nas\share\reports-evil\x.pdf", roots)
    assert not winpaths.is_under_network_root(r"\\attacker\share\reports\x.pdf", roots)
    assert not winpaths.is_under_network_root(r"\\?\C:\local\x.pdf", roots)


class _Api(ReportsAPI):
    """只测闸本身：不需要 store / runtime。"""

    def __init__(self, roots: list[str]) -> None:
        self._roots = roots

    def _report_output_roots(self) -> list[str]:  # type: ignore[override]
        return self._roots


class _NoTouchPath(type(Path())):
    """任何 resolve 都算失败：闸必须在碰文件系统之前就拒绝。"""

    def resolve(self, strict: bool = False):  # noqa: ANN201
        raise AssertionError(f"guard touched the filesystem for {self}")


@pytest.mark.parametrize("text", [
    r"\\192.0.2.1\share\x.pdf", "//192.0.2.1/share/x.pdf", r"\\?\UNC\192.0.2.1\share\x.pdf", r"\\?\GLOBALROOT\Device\Null",
    r"\\.\pipe\horosa", "NUL", r"sub\NUL", "CON.pdf", "x.pdf:stream", "a<b>.pdf", "\x00.pdf",
])
def test_guard_refuses_before_touching_the_filesystem(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    monkeypatch.setattr(reports_module.os, "name", "nt", raising=False)
    monkeypatch.setattr(reports_module, "Path", _NoTouchPath)
    with pytest.raises(ToolValidationError) as caught:
        _Api([str(tmp_path)])._report_output_path(text, default=tmp_path / "d.pdf")
    assert caught.value.code == "report.output_path_not_allowed"
    assert caught.value.details["requested"] == text.strip() and caught.value.details["reason"]


def test_allow_listed_share_still_passes_the_string_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reports_module.os, "name", "nt", raising=False)
    monkeypatch.setattr(reports_module, "Path", _NoTouchPath)
    # 字符串闸放行后才走到 resolve；这里只断言「走到了 resolve」，不真连网络。
    with pytest.raises(AssertionError, match="touched the filesystem"):
        _Api([r"\\nas\reports"])._report_output_path(r"\\nas\reports\x.pdf", default=tmp_path / "d.pdf")


def test_unresolvable_path_is_a_clean_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Boom(type(Path())):
        def resolve(self, strict: bool = False):  # noqa: ANN201
            raise OSError(36, "File name too long")

    monkeypatch.setattr(reports_module, "Path", Boom)
    with pytest.raises(ToolValidationError) as caught:
        _Api([Boom(tmp_path)])._report_output_path("x" * 5000 + ".pdf", default=tmp_path / "d.pdf")
    assert caught.value.code == "report.output_path_not_allowed"


def test_normal_paths_still_work(tmp_path: Path) -> None:
    api = _Api([tmp_path.resolve()])
    assert api._report_output_path("sub/ok.pdf", default=tmp_path / "d.pdf") == (tmp_path / "sub" / "ok.pdf").resolve()
    assert api._report_output_path(None, default=tmp_path / "d.pdf") == tmp_path / "d.pdf"
    with pytest.raises(ToolValidationError):
        api._report_output_path("../escape.pdf", default=tmp_path / "d.pdf")


@pytest.mark.parametrize("name", ["CONIN$", "CONOUT$", "COM¹", "LPT²", "con", "x/NUL.md"])
def test_knowledge_ids_share_the_reserved_list(name: str) -> None:
    with pytest.raises(ToolValidationError):
        kb.validate_id(name)
