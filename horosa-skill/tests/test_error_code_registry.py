"""A-5 / C-13：错误码登记表，以及守它的脚本自己会不会红。

拼出来的码（`code=f"tool.{tool}_inverted_window"`）静态扫描看不见、`inverted_window` / `span_too_large` 又不在任何后缀
规则里——信封没有 agent_recovery。现在：按技法生成的码只能经 `errors.tool_code(tool, family)`，族登记在
`errors.TOOL_CODE_FAMILIES`；scripts/verify_error_recovery.py 禁 f-string 码、要求每个码 / 族都有测试（或列在只减不增的
债务表里）；pytest 下包内代码抛出落不到恢复规则的码，当场以 BaseException 红（工具层 `except Exception` 吞不掉）。
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

from horosa_skill import errors
from horosa_skill.errors import (
    TOOL_CODE_FAMILIES,
    ToolValidationError,
    UnregisteredErrorCode,
    classify_code,
    engine_tool_code,
    recovery_for,
    tool_code,
)

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_error_recovery.py"


def _verifier():
    spec = importlib.util.spec_from_file_location("verify_error_recovery_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _tree(tmp_path: Path, source: str, test_text: str = "") -> tuple[Path, Path]:
    src, tests = tmp_path / "src", tmp_path / "tests"
    src.mkdir()
    tests.mkdir()
    (src / "mod.py").write_text(source, encoding="utf-8")
    (tests / "test_mod.py").write_text(test_text, encoding="utf-8")
    return src, tests


@pytest.mark.parametrize(("code", "kind"), [
    ("tool.qimenzeri_inverted_window", "input"),
    ("tool.tianxing_span_too_large", "input"),
    ("tool.taiyizeri_bad_window", "input"),
    ("tool.sanshiunited_snapshot_failed", "retry_or_doctor"),
    ("tool.tianxing_stitch_failed", "retry_or_doctor"),
    ("tool.indiazeri_bad_nodetype", "input"),
])
def test_per_technique_codes_classify_through_their_family(code: str, kind: str) -> None:
    assert classify_code(code) == (kind, "family")
    recovery = recovery_for(code, {})["agent_recovery"]
    assert recovery["kind"] == kind and recovery["prompt_to_user"]


def test_the_two_families_the_audit_found_now_say_what_to_do() -> None:
    assert "swap" in recovery_for("tool.qimenzeri_inverted_window", {})["agent_recovery"]["next_action"]
    assert recovery_for("tool.tianxing_span_too_large", {})["agent_recovery"]["next_action"] == "split_window"


def test_tool_code_refuses_an_unregistered_family_and_engine_codes_fall_back() -> None:
    assert tool_code("qimenzeri", "inverted_window") == "tool.qimenzeri_inverted_window"
    with pytest.raises(KeyError):
        tool_code("qimenzeri", "inverted_windwo")
    assert engine_tool_code("tianxing", "invalid_conditions", "scan_failed") == "tool.tianxing_invalid_conditions"
    assert engine_tool_code("tianxing", None, "split_failed") == "tool.tianxing_split_failed"
    assert engine_tool_code("tianxing", "something_new", "scan_failed") == "tool.tianxing_engine_failed"
    assert all(TOOL_CODE_FAMILIES[f]["kind"] in errors.RECOVERY_KINDS for f in TOOL_CODE_FAMILIES)


def test_an_unclassifiable_code_raised_from_package_code_fails_the_test() -> None:
    fake = types.ModuleType("horosa_skill._fake_raiser")
    exec(  # noqa: S102 - 构造一个「包内」模块，模拟 service 代码抛出没登记的码
        "from horosa_skill.errors import ToolValidationError\n"
        "def boom():\n    raise ToolValidationError('x', code='zzz.qqq')\n",
        fake.__dict__,
    )
    sys.modules[fake.__name__] = fake
    try:
        with pytest.raises(UnregisteredErrorCode):
            fake.boom()
        try:
            fake.boom()
        except Exception:  # noqa: BLE001
            pytest.fail("UnregisteredErrorCode must pass through `except Exception` (that is the point)")
        except UnregisteredErrorCode:
            pass
    finally:
        sys.modules.pop(fake.__name__, None)
    # 测试自己造的假码不算（这条测试本身就在用）
    assert ToolValidationError("x", code="zzz.qqq").code == "zzz.qqq"


def test_verifier_flags_f_string_codes_unregistered_codes_and_families(tmp_path: Path) -> None:
    verifier = _verifier()
    src, tests = _tree(tmp_path, (
        "from horosa_skill.errors import ToolValidationError, tool_code\n"
        "def a(tool):\n    raise ToolValidationError('x', code=f'tool.{tool}_inverted_window')\n"
        "def b():\n    raise ToolValidationError('x', code=\"zzz.qqq\")\n"
        "def c(tool):\n    raise ToolValidationError('x', code=tool_code(tool, \"no_such_family\"))\n"
    ), test_text="zzz.qqq no_such_family")
    problems = "\n".join(verifier.check_registry(src, tests, debt=[]))
    assert "f-strings" in problems and "mod.py:3" in problems
    assert "no recovery rule" in problems and "zzz.qqq" in problems
    assert "not registered" in problems and "no_such_family" in problems


def test_verifier_flags_an_untested_code_and_a_paid_debt(tmp_path: Path) -> None:
    verifier = _verifier()
    src, tests = _tree(tmp_path, (
        "from horosa_skill.errors import ToolValidationError\n"
        "def a():\n    raise ToolValidationError('x', code=\"place.not_found\")\n"
        "def b():\n    raise ToolValidationError('x', code=\"place.ambiguous\")\n"
    ), test_text="assert code == 'place.ambiguous'\n")
    untested = "\n".join(verifier.check_registry(src, tests, debt=[]))
    assert "no test exercises" in untested and "place.not_found" in untested and "place.ambiguous" not in untested
    assert verifier.check_registry(src, tests, debt=["place.not_found"]) == []
    paid = "\n".join(verifier.check_registry(src, tests, debt=["place.not_found", "place.ambiguous"]))
    assert "tested now" in paid and "place.ambiguous" in paid


def test_the_real_tree_passes_the_registry_rules() -> None:
    verifier = _verifier()
    assert verifier.check_registry(debt=verifier.load_test_debt()) == []
