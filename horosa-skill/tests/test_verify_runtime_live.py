"""verify_runtime_live.py 的纯函数（v0.38.0 A5）：矩阵 lane 的判据必须本身可测——负向对照各一。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

PKG_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("verify_runtime_live", PKG_ROOT / "scripts" / "verify_runtime_live.py")
live = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(live)


def _envelope(**overrides):
    base = {
        "ok": True,
        "data": {
            "export_snapshot": {"sections": [{"title": "起盘信息", "body": "…"}], "missing_selected_sections": []},
            "technique_card": {"compute": {"matches_declaration": True, "declared_engines": ["java"], "measured": "java"}},
        },
    }
    base.update(overrides)
    return base


def test_engine_result_accepts_a_healthy_envelope() -> None:
    assert live.check_engine_result("nongli_time", _envelope()) == []


def test_engine_result_rejects_failure_empty_sections_missing_sections_and_engine_mismatch() -> None:
    assert live.check_engine_result("x", _envelope(ok=False, error={"code": "tool.internal_error", "message": "boom"}))[0].startswith("x: ok=False")
    empty = _envelope(); empty["data"]["export_snapshot"]["sections"] = []
    assert any("sections is empty" in p for p in live.check_engine_result("x", empty))
    missing = _envelope(); missing["data"]["export_snapshot"]["missing_selected_sections"] = ["八宫详解"]
    assert any("missing_selected_sections" in p for p in live.check_engine_result("x", missing))
    mismatch = _envelope(); mismatch["data"]["technique_card"]["compute"]["matches_declaration"] = False
    assert any("matches_declaration=False" in p for p in live.check_engine_result("x", mismatch))
    # techniques without a declared engine set report None (chart / nongli_time / bazi_birth on a real runtime) — not a failure
    undeclared = _envelope(); undeclared["data"]["technique_card"]["compute"] = {"matches_declaration": None, "declared_engines": [], "measured": {}}
    assert live.check_engine_result("x", undeclared) == []
    no_card = _envelope(); no_card["data"].pop("technique_card")
    assert any("technique_card missing" in p for p in live.check_engine_result("x", no_card))


def test_doctor_ready_requires_both_endpoints_and_no_degrade() -> None:
    ready = {"installed": True, "platform_supported": True, "issues": [], "degraded": None,
             "endpoints": [{"label": "java_backend", "reachable": True}, {"label": "python_chart", "reachable": True}]}
    assert live.doctor_ready(ready) == []
    chart_only = dict(ready, issues=["services:java_backend_not_running"], degraded="chart_only",
                      endpoints=[{"label": "java_backend", "reachable": False}, {"label": "python_chart", "reachable": True}])
    problems = live.doctor_ready(chart_only)
    assert any("chart-only is a failure" in p for p in problems) and any("java_backend not reachable" in p for p in problems)
    assert "not installed" in live.doctor_ready({"installed": False, "issues": [], "endpoints": []})


def test_forbidden_skips_catch_live_gates_that_never_ran() -> None:
    output = (
        "SKIPPED [12] tests/test_local_js_tools.py:94: live gates only run against an explicitly named instance — export …\n"
        "SKIPPED [1] tests/test_ports.py:10: powershell.exe not on PATH\n"
        "SKIPPED [3] tests/test_local_js_tools.py:94: Horosa runtime unusable — chart http://127.0.0.1:8899 (java_routes_dead)\n"
        "900 passed, 16 skipped in 80.0s\n"
    )
    hits = live.forbidden_skips(output)
    assert len(hits) == 2 and all("test_local_js_tools" in h for h in hits)
    assert live.forbidden_skips("SKIPPED [1] tests/test_ports.py:10: powershell.exe not on PATH\n") == []


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("905 passed, 72 skipped, 1 warning in 87.11s (0:01:27)", {"passed": 905, "failed": 0, "error": 0, "skipped": 72}),
        ("2 failed, 900 passed, 3 skipped in 10s", {"passed": 900, "failed": 2, "error": 0, "skipped": 3}),
        ("1 error, 5 passed in 1s", {"passed": 5, "failed": 0, "error": 1, "skipped": 0}),
        ("no summary here", {"passed": 0, "failed": 0, "error": 0, "skipped": 0}),
    ],
)
def test_pytest_summary_parses_the_final_line(line: str, expected: dict) -> None:
    assert live.pytest_summary("noise\n" + line + "\n") == expected


def test_localize_manifest_points_urls_at_local_archives_and_keeps_hashes(tmp_path: Path) -> None:
    (tmp_path / "horosa-runtime-darwin-arm64-v1.tar.gz").write_bytes(b"a")
    (tmp_path / "horosa-runtime-win32-x64-v1.zip").write_bytes(b"b")
    manifest = {"version": "1", "platforms": {
        "darwin-arm64": {"url": "https://github.com/x/y/releases/download/v1/horosa-runtime-darwin-arm64-v1.tar.gz", "sha256": "aa", "size": 1},
        "win32-x64": {"url": "https://github.com/x/y/releases/download/v1/horosa-runtime-win32-x64-v1.zip", "sha256": "bb", "size": 1},
    }}
    localized = live.localize_manifest(manifest, tmp_path)
    assert localized["platforms"]["darwin-arm64"]["url"].startswith("file://")
    assert localized["platforms"]["darwin-arm64"]["sha256"] == "aa" and localized["platforms"]["win32-x64"]["size"] == 1
    assert manifest["platforms"]["darwin-arm64"]["url"].startswith("https://"), "input untouched"
    (tmp_path / "horosa-runtime-win32-x64-v1.zip").unlink()
    with pytest.raises(FileNotFoundError):
        live.localize_manifest(manifest, tmp_path)


def test_engine_cases_carry_the_gate_confirmation_and_cover_three_engine_families() -> None:
    assert set(live.ENGINE_CASES) == {"chart", "qimen", "nongli_time", "bazi_birth"}
    assert live.CONFIRM["agent_confirmed_settings"] is True and live.CONFIRM["clarification_notes"]
    # v0.38.1 R17：四家 → 九家（vscode / gemini / windsurf / cline / zed 此前没有任何真机 lane 跑过 setup）
    assert {"claude-code", "codex", "cursor", "claude-desktop"} <= set(live.CLIENTS) and len(live.CLIENTS) == 9


def test_origin_of_strips_the_probe_path() -> None:
    """首跑真机矩阵：把 `…/common/time` 整个当 HOROSA_SERVER_ROOT 导出，闸门探 `…/common/time/nongli/time` → 404 → java_routes_dead。"""
    assert live.origin_of("http://127.0.0.1:9999/common/time") == "http://127.0.0.1:9999"
    assert live.origin_of("http://127.0.0.1:8899") == "http://127.0.0.1:8899"
    assert live.origin_of("") == ""


def test_failed_tests_are_kept_in_the_report() -> None:
    output = "FAILED tests/test_a.py::test_x - AssertionError\nERROR tests/test_b.py::test_y\n2 failed in 1s\n"
    assert live.failed_tests(output) == ["FAILED tests/test_a.py::test_x - AssertionError", "ERROR tests/test_b.py::test_y"]


def test_pytest_env_carries_origins_and_node_but_not_the_lane_port_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """本机 lane #3：HOROSA_LOCAL_BACKEND_PORT 漏进 pytest 进程 → `test_auto_ports_avoid_a_held_default` 的 provenance 断言红。"""
    import argparse

    monkeypatch.setenv("HOROSA_SERVER_ROOT", "http://elsewhere:1")
    args = argparse.Namespace(work_dir=str(tmp_path), runtime_root=None, data_dir=None, start_timeout=900,
                              platform=None, backend_port=19999, chart_port=18899)
    lane = live.Lane(args)
    lane.endpoints = {"java_backend": "http://127.0.0.1:19999/common/time", "python_chart": "http://127.0.0.1:18899"}
    lane.node_bin = "/x/node"
    runtime_env = lane.env()
    assert runtime_env["HOROSA_LOCAL_BACKEND_PORT"] == "19999" and "HOROSA_SERVER_ROOT" not in runtime_env
    env = lane.pytest_env()
    assert env["HOROSA_SERVER_ROOT"] == "http://127.0.0.1:19999" and env["HOROSA_CHART_SERVER_ROOT"] == "http://127.0.0.1:18899"
    assert env["HOROSA_NODE_BIN"] == "/x/node"
    assert "HOROSA_LOCAL_BACKEND_PORT" not in env and "HOROSA_LOCAL_CHART_PORT" not in env


# ---------------------------------------------------------------- v0.38.1 B3


def test_lane_covers_every_client_the_cli_knows() -> None:
    from horosa_skill.surfaces.cli import _CLIENT_NAMES

    assert set(live.CLIENTS) == set(_CLIENT_NAMES) and len(live.CLIENTS) == 9


def test_http_probe_verdict_requires_401_421_and_the_full_surface() -> None:
    assert live.evaluate_http_probe(no_auth_status=401, bad_host_status=421, tools=116, expected_tools=116) == []
    assert live.evaluate_http_probe(no_auth_status=200, bad_host_status=421, tools=116, expected_tools=116), "无令牌放行 = 红"
    assert live.evaluate_http_probe(no_auth_status=401, bad_host_status=200, tools=116, expected_tools=116), "错 Host 放行 = 红"
    assert live.evaluate_http_probe(no_auth_status=401, bad_host_status=421, tools=11, expected_tools=116), "精简面冒充全量 = 红"
    assert live.evaluate_http_probe(no_auth_status=None, bad_host_status=None, tools=None, expected_tools=116)


def test_release_mode_install_must_record_a_real_download() -> None:
    remote = ["--manifest-url", "https://github.com/x/y/releases/download/v1/runtime-manifest.json"]
    assert live.download_problems(remote, None), "旧 lane 的空白必红"
    assert live.download_problems(remote, {"bytes": 0})
    assert live.download_problems(remote, {"bytes": 737084051, "url": "https://…", "mirror_used": False}) == []
    assert live.download_problems(["--manifest-url", "file:///tmp/lane-manifest.json"], None) == [], "artifact 模式（file://）不要求下载"
    assert live.download_problems(["--archive", "/x.tar.gz"], None) == []


def test_attached_client_is_recognised_by_a_new_registry_entry_not_by_the_popen_pid() -> None:
    """Windows 上 Popen 拿到的是 venv launcher 的 pid，登记表里是子进程 pid —— 按 pid 相等去找必然落空（负向对照）。"""
    before = {"111"}
    after = {"111": {"transport": "stdio"}, "4242": {"transport": "stdio"}}
    launcher_pid = 4000  # the Popen pid on Windows: never what `serve` registers
    assert {pid for pid in after if int(pid) == launcher_pid} == set(), "the old pid-equality lookup finds nothing"
    assert live.new_client_entries(before, after) == {"4242": {"transport": "stdio"}}
    assert live.new_client_entries(set(after), after) == {}
