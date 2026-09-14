#!/usr/bin/env python3
"""Live verification of a runtime payload on a real machine (v0.38.0 A5 — the runtime-matrix lanes).

Drives the `horosa-skill` CLI as subprocesses exactly the way a user would, on the machine it runs on:

  install (manifest or archive; a real HTTPS download in release/schedule mode, v0.38.1 R1) → doctor →
  runtime start with the FACTORY budget (no HOROSA_RUNTIME_START_TIMEOUT_SECONDS override; ready or `starting`
  + poll, v0.38.1 R11) → four engine calls (chart / qimen / nongli_time / bazi_birth) → `setup --client …`
  for all nine clients (config → re-read → real stdio probe, R17) → `setup --client claude-code --scope user`
  (R6) → streamable-http handshake with Bearer / 401 / 421 (R7) → a second stdio client keeps `runtime stop`
  refused until --force (R14) → `runtime restart` + HOROSA_PORTS=auto reuses the registry ports (R12/R13) →
  the live pytest suite against the running endpoints → runtime stop.

One JSON report on stdout (also `--out`), exit 0 only when every step passed. A chart-only degrade
(Java backend dead) is a FAILURE in every lane — that is precisely the Windows condition (issue #14) the
matrix exists to catch before a release goes public. Nothing here is mocked: no runtime, no green.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

PKG_ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, "-m", "horosa_skill.surfaces.cli"]
# Windows consoles default to a code page that cannot encode the Chinese in doctor advice — the first matrix run
# died printing its own report after every step had passed.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

# Budgets (seconds): the plan's install 10 / start 15 / engines 5 / pytest 25 minutes.
BUDGET = {"install": 600, "doctor": 120, "start": 900, "engine": 300, "setup": 600, "pytest": 1500, "stop": 180}
DOCTOR_POLL_SECONDS = 10.0

CONFIRM = {
    "agent_confirmed_settings": True,
    "clarification_notes": "runtime-matrix live verification: the lane accepts the documented defaults",
}
ENGINE_CASES: dict[str, dict[str, Any]] = {
    # Python chart service (western natal chart)
    "chart": {"date": "1990-07-15", "time": "14:30:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
    # ken engine on the chart service (奇门)
    "qimen": {"date": "2028-04-06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
    # Java backend (农历)
    "nongli_time": {"date": "2028-04-06", "time": "09:33:00", "zone": "+08:00", "lon": "121e28", "lat": "31n13"},
    # Java backend + core-js enrichment (八字)
    "bazi_birth": {"date": "1990-07-15", "time": "14:30:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gender": 1},
}
# v0.38.1 R17：九个客户端全部走一遍 setup（配置 → 回读 → 真起一次 stdio）。
CLIENTS = ("claude-code", "codex", "cursor", "claude-desktop", "vscode", "gemini", "windsurf", "cline", "zed")
FACTORY_START_POLL_SECONDS = 600  # a `starting` answer under the factory budget must turn ready within this
# A live pytest run that skips for one of these reasons did not test the runtime at all.
FORBIDDEN_SKIP_REASONS = (
    "Horosa runtime unusable",
    "live gates only run against an explicitly named instance",
    "chart service not listening",
    "java_routes_dead",
    "not_listening",
)


# ---------------------------------------------------------------- pure helpers (unit-tested)


def check_engine_result(tool: str, envelope: dict[str, Any]) -> list[str]:
    """Problems with one `tool run` envelope: must be ok, carry sections, miss nothing, match its declared engine."""
    problems: list[str] = []
    if envelope.get("ok") is not True:
        error = envelope.get("error") or {}
        problems.append(f"{tool}: ok={envelope.get('ok')} error={error.get('code') or envelope.get('code')}: {error.get('message') or envelope.get('message')}")
        return problems
    data = envelope.get("data") or {}
    export = data.get("export_snapshot") or {}
    sections = export.get("sections") or []
    if not sections:
        problems.append(f"{tool}: export_snapshot.sections is empty")
    missing = export.get("missing_selected_sections") or []
    if missing:
        problems.append(f"{tool}: missing_selected_sections={missing}")
    card = data.get("technique_card") or {}
    if not card:
        problems.append(f"{tool}: data.technique_card missing")
        return problems
    compute = card.get("compute") or {}
    # matches_declaration is None for techniques that declare no engine set (chart / nongli_time / bazi_birth);
    # only an explicit False — a declared engine that was not the one measured — is a failure.
    if compute.get("matches_declaration") is False:
        problems.append(
            f"{tool}: technique_card.compute.matches_declaration=False "
            f"(declared={compute.get('declared_engines')}, measured={compute.get('measured')})"
        )
    return problems


def doctor_ready(report: dict[str, Any]) -> list[str]:
    """Why a doctor report is NOT a fully running runtime (empty list = ready)."""
    problems: list[str] = []
    if report.get("installed") is not True:
        problems.append("not installed")
    if report.get("platform_supported") is False:
        problems.append("platform_supported=false")
    issues = [str(i) for i in report.get("issues") or []]
    if issues:
        problems.append(f"issues={issues}")
    if report.get("degraded"):
        problems.append(f"degraded={report.get('degraded')} (chart-only is a failure in every lane)")
    reachable = {e.get("label"): e.get("reachable") for e in report.get("endpoints") or []}
    for label in ("java_backend", "python_chart"):
        if reachable.get(label) is not True:
            problems.append(f"{label} not reachable")
    return problems


def forbidden_skips(pytest_output: str) -> list[str]:
    """`pytest -rs` lines whose reason means the live gates never ran."""
    hits: list[str] = []
    for line in pytest_output.splitlines():
        if line.startswith("SKIPPED") and any(reason in line for reason in FORBIDDEN_SKIP_REASONS):
            hits.append(line.strip())
    return hits


_SUMMARY = re.compile(r"(\d+) (passed|failed|error|errors|skipped)")


def pytest_summary(pytest_output: str) -> dict[str, int]:
    """Counts from the final `N passed, M skipped …` line (zeros when absent)."""
    counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}
    for line in reversed(pytest_output.splitlines()):
        if " passed" in line or " failed" in line or " error" in line:
            for number, word in _SUMMARY.findall(line):
                counts["error" if word == "errors" else word] = int(number)
            break
    return counts


def origin_of(url: str) -> str:
    """`http://127.0.0.1:9999/common/time` → `http://127.0.0.1:9999`.

    Doctor's endpoint URLs include the probe path; the first matrix run exported that whole URL as
    HOROSA_SERVER_ROOT, so the live gates probed `…/common/time/nongli/time`, saw 404, and skipped every
    Java-backed test as `java_routes_dead` — on a lane whose Java backend was perfectly healthy.
    """
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url
    return f"{parsed.scheme}://{parsed.netloc}"


def failed_tests(pytest_output: str, limit: int = 12) -> list[str]:
    """`FAILED …` / `ERROR …` lines from `pytest -rf` (kept in the report so a lane is diagnosable without artifacts)."""
    hits = [line.strip() for line in pytest_output.splitlines() if line.startswith(("FAILED ", "ERROR "))]
    return hits[:limit]


def localize_manifest(manifest: dict[str, Any], assets_dir: Path) -> dict[str, Any]:
    """Point every platform URL at the archive of the same name inside `assets_dir` (file://), keeping sha256/size.

    The pipeline's manifest carries tag-pinned GitHub URLs that do not exist yet while the release is a draft
    (or a dry run); the lanes install from the assembled artifact instead — through the manifest, so the
    Windows-on-ARM fallback (win32-arm64 → win32-x64) is exercised for real.
    """
    localized = json.loads(json.dumps(manifest))
    for key, entry in (localized.get("platforms") or {}).items():
        name = Path(urlparse(str(entry.get("url") or "")).path).name
        archive = assets_dir / name
        if not name or not archive.is_file():
            raise FileNotFoundError(f"{key}: archive {name or '<no url>'} not found in {assets_dir}")
        entry["url"] = archive.resolve().as_uri()
    return localized


def evaluate_http_probe(*, no_auth_status: int | None, bad_host_status: int | None, tools: int | None, expected_tools: int) -> list[str]:
    """R7：无令牌必须 401、错 Host 必须 421、带令牌的 initialize+tools/list 必须列出完整工具面。"""
    problems: list[str] = []
    if no_auth_status != 401:
        problems.append(f"request without a token got {no_auth_status}, expected 401")
    if bad_host_status != 421:
        problems.append(f"request with a foreign Host header got {bad_host_status}, expected 421 (DNS-rebinding guard)")
    if tools != expected_tools:
        problems.append(f"tools/list over streamable-http returned {tools}, expected {expected_tools}")
    return problems


def new_client_entries(before: set[str], clients: dict[str, Any]) -> dict[str, Any]:
    """挂接后新出现的客户端登记（按 pid 集合差认，不按 Popen 的 pid —— Windows venv launcher 的子进程才是真 serve）。"""
    return {pid: info for pid, info in clients.items() if pid not in before}


def download_problems(source_args: list[str], download: dict[str, Any] | None) -> list[str]:
    """R1：release / schedule 模式（http(s) 清单）必须记录到一次真实传输；file:// / --archive 不要求。"""
    manifest = source_args[1] if len(source_args) == 2 and source_args[0] == "--manifest-url" else ""
    if not manifest.startswith(("http://", "https://")):
        return []
    if not isinstance(download, dict) or int(download.get("bytes") or 0) <= 0:
        return ["release-mode install recorded no real download (download.bytes must be > 0)"]
    return []


# ---------------------------------------------------------------- subprocess driving


class Lane:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.work = Path(args.work_dir).resolve() if args.work_dir else Path(tempfile.mkdtemp(prefix="horosa-lane-"))
        self.work.mkdir(parents=True, exist_ok=True)
        self.runtime_root = Path(args.runtime_root).resolve() if args.runtime_root else self.work / "runtime"
        self.data_dir = Path(args.data_dir).resolve() if args.data_dir else self.work / "data"
        self.report: dict[str, Any] = {"ok": False, "steps": {}, "work_dir": str(self.work), "runtime_root": str(self.runtime_root)}
        self.endpoints: dict[str, str] = {}
        self.node_bin: str | None = None

    # env for managed-mode CLI calls: never inherit an external HOROSA_*_SERVER_ROOT from the runner
    def env(self, **extra: str) -> dict[str, str]:
        base = {k: v for k, v in os.environ.items() if k not in {"HOROSA_SERVER_ROOT", "HOROSA_CHART_SERVER_ROOT", "HOROSA_PORTS"}}
        base.update({
            "HOROSA_RUNTIME_ROOT": str(self.runtime_root),
            "HOROSA_SKILL_DATA_DIR": str(self.data_dir),
            "HOROSA_RUNTIME_START_TIMEOUT_SECONDS": str(self.args.start_timeout),
            "HOROSA_LOCAL_BACKEND_PORT": str(self.args.backend_port),
            "HOROSA_LOCAL_CHART_PORT": str(self.args.chart_port),
            "HOROSA_TRACE_ENABLED": "0",
            "PYTHONIOENCODING": "utf-8",
        })
        if self.args.platform:
            base["HOROSA_RUNTIME_PLATFORM"] = self.args.platform
        base.update(extra)
        return base

    def pytest_env(self) -> dict[str, str]:
        """Env for the live pytest run: the running endpoints as *origins* (external mode) + the payload's node.

        The lane's own port overrides (HOROSA_LOCAL_*_PORT) must NOT leak in: tests such as
        `test_auto_ports_avoid_a_held_default` read `Settings.from_env()` provenance and an inherited
        HOROSA_LOCAL_BACKEND_PORT turns `auto:HOROSA_PORTS` into `env:HOROSA_LOCAL_BACKEND_PORT` (local lane run #3).
        """
        env = self.env(
            HOROSA_SERVER_ROOT=origin_of(self.endpoints.get("java_backend", "")),
            HOROSA_CHART_SERVER_ROOT=origin_of(self.endpoints.get("python_chart", "")),
        )
        for key in ("HOROSA_LOCAL_BACKEND_PORT", "HOROSA_LOCAL_CHART_PORT"):
            env.pop(key, None)
        if self.node_bin:
            env["HOROSA_NODE_BIN"] = self.node_bin
        return env

    def cli(self, *args: str, timeout: float, env: dict[str, str] | None = None) -> tuple[int, str, str]:
        completed = subprocess.run(
            [*CLI, *args], cwd=str(PKG_ROOT), env=env or self.env(), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        return completed.returncode, completed.stdout, completed.stderr

    def cli_json(self, *args: str, timeout: float, env: dict[str, str] | None = None) -> tuple[int, dict[str, Any] | None, str]:
        code, out, err = self.cli(*args, timeout=timeout, env=env)
        payload: dict[str, Any] | None
        try:
            payload = json.loads(out[out.index("{"):]) if "{" in out else None
        except ValueError:
            payload = None
        if payload is None and "{" in err:
            try:
                payload = json.loads(err[err.index("{"):])
            except ValueError:
                payload = None
        return code, payload, (err or "")[-3000:]

    def step(self, name: str, ok: bool, **fields: Any) -> bool:
        fields["ok"] = ok
        self.report["steps"][name] = fields
        print(f"[{name}] {'ok' if ok else 'FAIL'} " + json.dumps({k: v for k, v in fields.items() if k in ('seconds', 'problems', 'code')}, ensure_ascii=False), file=sys.stderr)
        return ok

    # ---- steps
    def install(self) -> bool:
        started = time.perf_counter()
        source_args: list[str]
        if self.args.archive:
            source_args = ["--archive", str(Path(self.args.archive).resolve())]
        elif self.args.assets_dir:
            assets = Path(self.args.assets_dir).resolve()
            manifest = json.loads((assets / "runtime-manifest.json").read_text(encoding="utf-8"))
            localized = localize_manifest(manifest, assets)
            lane_manifest = self.work / "lane-manifest.json"
            lane_manifest.write_text(json.dumps(localized, ensure_ascii=False, indent=2), encoding="utf-8")
            source_args = ["--manifest-url", lane_manifest.resolve().as_uri()]
        else:
            source_args = ["--manifest-url", self.args.manifest_url] if self.args.manifest_url else []
        code, payload, err = self.cli_json("install", *source_args, timeout=BUDGET["install"])
        seconds = round(time.perf_counter() - started, 1)
        if code != 0 or not payload or payload.get("ok") is not True:
            return self.step("install", False, seconds=seconds, code=(payload or {}).get("code"), stderr=err, source=source_args)
        problems: list[str] = []
        if self.args.expect_payload_platform and payload.get("platform") != self.args.expect_payload_platform:
            problems.append(f"installed platform {payload.get('platform')} != expected {self.args.expect_payload_platform}")
        fallback = payload.get("platform_fallback")
        if self.args.expect_emulated and not fallback:
            problems.append("expected a platform fallback (x64 emulation) but install reported none")
        if not self.args.expect_emulated and fallback:
            problems.append(f"unexpected platform fallback {fallback}")
        download = payload.get("download")
        problems.extend(download_problems(source_args, download))
        asset = payload.get("asset") or {}
        self.report["installed_archive_sha256"] = asset.get("sha256") or None
        self.report["installed_archive_name"] = Path(urlparse(str(asset.get("url") or "")).path).name or None
        self.report["download"] = download
        return self.step("install", not problems, seconds=seconds, platform=payload.get("platform"), platform_fallback=fallback,
                         warnings=[w.get("code") for w in payload.get("warnings") or []], problems=problems,
                         version=(payload.get("manifest") or {}).get("version"), source=source_args, download=download,
                         installed_archive_sha256=self.report["installed_archive_sha256"])

    def non_ascii_root_refusal(self) -> bool:
        """v0.38.1（仅 Windows）：runtime 根含非 ASCII 字符时，install 必须在下载前以 runtime.path_not_ascii 拒绝。

        随包 JDK 17 的 java.exe（GetModuleFileNameA）与 Swiss Ephemeris（UTF-8 路径进 C fopen）在这种目录里起不来 / 打不开星历
        （draft 真机矩阵三轮实证）。拿工作目录下一个带中文的子目录当 runtime 根，走一次真 CLI。
        """
        if os.name != "nt":
            return True
        candidate = self.work / "runtime-测试"
        code, payload, err = self.cli_json(
            "install", "--archive", str(self.work / "never-read.zip"), timeout=120,
            env=self.env(HOROSA_RUNTIME_ROOT=str(candidate)),
        )
        problems: list[str] = []
        if code == 0 or (payload or {}).get("code") != "runtime.path_not_ascii":
            problems.append(f"install under a non-ASCII root: exit {code} code={(payload or {}).get('code')!r} (expected runtime.path_not_ascii) {err[-300:]}")
        if candidate.exists() and any(candidate.iterdir()):
            problems.append(f"the refused install still wrote into {candidate}")
        return self.step("non_ascii_root_refusal", not problems, problems=problems, code=(payload or {}).get("code"))

    def doctor(self, name: str = "doctor") -> tuple[bool, dict[str, Any]]:
        code, payload, err = self.cli_json("doctor", timeout=BUDGET["doctor"])
        if code != 0 or not payload:
            self.step(name, False, code=code, stderr=err)
            return False, {}
        (self.work / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return True, payload

    def doctor_after_install(self) -> bool:
        ok, payload = self.doctor()
        if not ok:
            return False
        problems: list[str] = []
        if payload.get("installed") is not True:
            problems.append("installed != true")
        if payload.get("platform_supported") is not True:
            problems.append("platform_supported != true")
        if self.args.expect_payload_platform and payload.get("payload_platform") != self.args.expect_payload_platform:
            problems.append(f"payload_platform {payload.get('payload_platform')} != {self.args.expect_payload_platform}")
        if bool(payload.get("emulated")) != bool(self.args.expect_emulated):
            problems.append(f"emulated={payload.get('emulated')} but lane expects {self.args.expect_emulated}")
        missing = [f["label"] for f in payload.get("files") or [] if f.get("required") and not f.get("exists")]
        if missing:
            problems.append(f"missing files: {missing}")
        self.node_bin = (payload.get("paths") or {}).get("node")
        issues = [str(i) for i in payload.get("issues") or []]
        if not set(issues) <= {"services:not_running"}:
            problems.append(f"issues before start: {issues}")
        return self.step("doctor", not problems, problems=problems, host_platform=payload.get("host_platform"),
                         payload_platform=payload.get("payload_platform"), emulated=payload.get("emulated"),
                         arch=payload.get("arch"), windows=payload.get("windows"), quarantine=payload.get("quarantine"),
                         warnings=[w.get("code") for w in payload.get("warnings") or []])

    def start(self) -> bool:
        started = time.perf_counter()
        # v0.38.1 R11：出厂预算 —— 不带 HOROSA_RUNTIME_START_TIMEOUT_SECONDS 覆盖。CLI 必须要么 ready、要么返回
        # `starting`（启动器活着、预算用完），绝不能 start_timeout；`starting` 之后 doctor 轮询必须在限期内变 ready。
        factory_env = self.env()
        factory_env.pop("HOROSA_RUNTIME_START_TIMEOUT_SECONDS", None)
        code, payload, err = self.cli_json("runtime", "start", timeout=BUDGET["start"] + 60, env=factory_env)
        if code != 0 or not payload or payload.get("ok") is not True:
            return self.step("start", False, seconds=round(time.perf_counter() - started, 1), code=(payload or {}).get("code"), stderr=err,
                             factory_budget=True)
        self.report["factory_budget"] = {
            "starting": bool(payload.get("starting")), "budget_seconds": payload.get("budget_seconds"),
            "cap_seconds": payload.get("cap_seconds"), "elapsed_seconds": payload.get("elapsed_seconds"),
        }
        deadline = started + (FACTORY_START_POLL_SECONDS if payload.get("starting") else BUDGET["start"])
        last: list[str] = ["doctor not run"]
        while time.perf_counter() < deadline:
            ok, report = self.doctor("doctor-after-start")
            if ok:
                last = doctor_ready(report)
                if not last:
                    for endpoint in report.get("endpoints") or []:
                        self.endpoints[str(endpoint.get("label"))] = str(endpoint.get("url"))
                    return self.step("start", True, seconds=round(time.perf_counter() - started, 1), endpoints=self.endpoints,
                                     listener_scope=report.get("listener_scope"), factory_budget=self.report.get("factory_budget"))
                if any("degraded=" in p for p in last) and time.perf_counter() - started > 120:
                    break  # a dead Java backend does not come back by waiting
            time.sleep(DOCTOR_POLL_SECONDS)
        return self.step("start", False, seconds=round(time.perf_counter() - started, 1), problems=last)

    def engines(self) -> bool:
        results: dict[str, Any] = {}
        all_ok = True
        for tool, base in ENGINE_CASES.items():
            payload_path = self.work / f"{tool}.in.json"
            out_path = self.work / f"{tool}.out.json"
            payload_path.write_text(json.dumps({**base, **CONFIRM}, ensure_ascii=False), encoding="utf-8")
            started = time.perf_counter()
            code, envelope, err = self.cli_json("tool", "run", tool, "--input", str(payload_path), "--output", str(out_path),
                                                timeout=BUDGET["engine"])
            seconds = round(time.perf_counter() - started, 1)
            if code != 0 or not envelope:
                results[tool] = {"ok": False, "seconds": seconds, "exit": code, "stderr": err}
                all_ok = False
                continue
            problems = check_engine_result(tool, envelope)
            card = ((envelope.get("data") or {}).get("technique_card") or {}).get("compute") or {}
            results[tool] = {"ok": not problems, "seconds": seconds, "problems": problems,
                             "sections": len(((envelope.get("data") or {}).get("export_snapshot") or {}).get("sections") or []),
                             "engine": card.get("measured"), "warnings": envelope.get("warnings") or []}
            all_ok = all_ok and not problems
        return self.step("engines", all_ok, results=results)

    def client_setup(self) -> bool:
        results: dict[str, Any] = {}
        all_ok = True
        configs = self.work / "client-configs"
        configs.mkdir(exist_ok=True)
        for client in CLIENTS:
            config = configs / ("config.toml" if client == "codex" else f"{client}.json")
            started = time.perf_counter()
            code, payload, err = self.cli_json(
                "setup", "--client", client, "--config", str(config), "--skip-install", "--no-probe-network",
                timeout=BUDGET["setup"],
            )
            seconds = round(time.perf_counter() - started, 1)
            ok = code == 0 and bool(payload) and payload.get("ok") is True
            steps = (payload or {}).get("steps") or {}
            results[client] = {
                "ok": ok, "seconds": seconds,
                "stdio_tools": (steps.get("stdio_probe") or {}).get("tools"),
                "client_check_problems": (steps.get("client_check") or {}).get("problems"),
                "failure": None if ok else {"step": (payload or {}).get("step"), "code": (payload or {}).get("code"), "stderr": err},
            }
            all_ok = all_ok and ok
        return self.step("client_setup", all_ok, results=results)

    def claude_code_user_scope(self) -> bool:
        """R6：`setup --client claude-code --scope user`（不传 --config）。`claude` 不在 PATH 时必须打印可复制命令并 ok；
        在 PATH 时真跑 `claude mcp add --scope user` → `claude mcp get horosa` → 清理。"""
        started = time.perf_counter()
        code, payload, err = self.cli_json("setup", "--client", "claude-code", "--scope", "user", "--skip-install",
                                           "--no-probe-network", "--no-stdio-probe", timeout=BUDGET["setup"])
        config = ((payload or {}).get("steps") or {}).get("config") or {}
        problems: list[str] = []
        if code != 0 or not payload or payload.get("ok") is not True:
            problems.append(f"setup --scope user failed: exit {code} code={(payload or {}).get('code')} {err[-300:]}")
        mode = config.get("mode")
        if mode not in {"printed", "claude-mcp-add"}:
            problems.append(f"config.mode {mode!r}, expected printed / claude-mcp-add")
        if mode == "printed" and not str(config.get("command") or "").startswith(("claude mcp add", '"claude" mcp add')):
            problems.append(f"printed mode without a copy-pasteable `claude mcp add` command: {config.get('command')!r}")
        executed = bool(config.get("executed"))
        verified = None
        if executed:
            got, out, _ = self.cli_wrap(["claude", "mcp", "get", "horosa"], timeout=60)
            verified = got == 0 and "horosa" in out
            if not verified:
                problems.append("`claude mcp add --scope user` ran but `claude mcp get horosa` does not show it")
            self.cli_wrap(["claude", "mcp", "remove", "--scope", "user", "horosa"], timeout=60)
        return self.step("claude_code_user_scope", not problems, seconds=round(time.perf_counter() - started, 1), mode=mode,
                         executed=executed, verified=verified, command=config.get("command"), problems=problems)

    def cli_wrap(self, command: list[str], *, timeout: float) -> tuple[int, str, str]:
        try:
            completed = subprocess.run(command, cwd=str(PKG_ROOT), env=self.env(), capture_output=True, text=True,
                                       encoding="utf-8", errors="replace", timeout=timeout)
        except (OSError, subprocess.SubprocessError) as exc:
            return 1, "", f"{type(exc).__name__}: {exc}"
        return completed.returncode, completed.stdout, completed.stderr

    def http_probe(self) -> bool:
        """R7：streamable-http 真握手 —— 无令牌 401、错 Host 421、带 Bearer 的 initialize + tools/list 列出完整工具面。"""
        import secrets
        import socket

        started = time.perf_counter()
        with socket.socket() as probe_socket:
            probe_socket.bind(("127.0.0.1", 0))
            port = probe_socket.getsockname()[1]
        token = secrets.token_urlsafe(18)
        url = f"http://127.0.0.1:{port}/mcp"
        env = self.env()
        env.pop("HOROSA_MCP_COMPACT", None)  # full surface
        log_path = self.work / "http-serve.log"
        with log_path.open("w", encoding="utf-8") as log:
            proc = subprocess.Popen(
                [*CLI, "serve", "--transport", "streamable-http", "--host", "127.0.0.1", "--port", str(port), "--token", token,
                 "--skip-runtime-start"],
                cwd=str(PKG_ROOT), env=env, stdout=log, stderr=subprocess.STDOUT,
            )
        result: dict[str, Any] = {"port": port}
        try:
            deadline = time.perf_counter() + 180
            while time.perf_counter() < deadline:
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=1):
                        break
                except OSError:
                    if proc.poll() is not None:
                        break
                    time.sleep(1)
            import httpx

            body = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "lane", "version": "0"}}}
            headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
            with httpx.Client(timeout=30) as http:
                result["no_auth_status"] = http.post(url, json=body, headers=headers).status_code
                result["bad_host_status"] = http.post(url, json=body, headers={**headers, "Authorization": f"Bearer {token}", "Host": "evil.example"}).status_code
            import anyio
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client

            async def handshake() -> tuple[int, str]:
                with anyio.fail_after(120):
                    async with streamablehttp_client(url, headers={"Authorization": f"Bearer {token}"}) as (read, write, _sid):
                        async with ClientSession(read, write) as session:
                            init = await session.initialize()
                            tools = await session.list_tools()
                            return len(tools.tools), init.serverInfo.version

            try:
                result["tools"], result["server_version"] = anyio.run(handshake)
            except Exception as exc:  # noqa: BLE001 - 失败要连日志尾巴一起报
                result["tools"] = None
                result["handshake_error"] = f"{type(exc).__name__}: {exc}"[:300]
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
        from horosa_skill.engine.registry import TOOL_DEFINITIONS
        from horosa_skill.surfaces.mcp_server import FACADE_TOOL_COUNT

        expected = FACADE_TOOL_COUNT + len(TOOL_DEFINITIONS)
        problems = evaluate_http_probe(no_auth_status=result.get("no_auth_status"), bad_host_status=result.get("bad_host_status"),
                                       tools=result.get("tools"), expected_tools=expected)
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-1500:] if problems else None
        return self.step("http_probe", not problems, seconds=round(time.perf_counter() - started, 1), expected_tools=expected,
                         problems=problems, serve_log_tail=tail, **result)

    def clients_attached_stop(self) -> bool:
        """R14：第二个 stdio 客户端挂着时 `runtime stop` 必须 stop_refused_clients_attached；客户端退出后登记消失。"""
        started = time.perf_counter()
        problems: list[str] = []
        # 🔴 按「新出现的登记」认客户端，不按 Popen 的 pid：Windows 上 venv 的 python.exe 是个 launcher，真解释器是它的
        # 子进程，`serve` 登记的是子进程 pid（v0.37.0 CI 在监听者 pid 上踩过同一个坑）。先拍一张挂接前的快照。
        _c, before_status, _e = self.cli_json("runtime", "status", timeout=60)
        before = set(((before_status or {}).get("clients") or {}))
        client = subprocess.Popen(
            [*CLI, "serve", "--transport", "stdio", "--skip-runtime-start"], cwd=str(PKG_ROOT), env=self.env(),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        attached: dict[str, Any] = {}
        try:
            deadline = time.perf_counter() + 90
            while time.perf_counter() < deadline:
                _c, status, _e = self.cli_json("runtime", "status", timeout=60)
                attached = new_client_entries(before, (status or {}).get("clients") or {})
                if attached:
                    break
                time.sleep(2)
            if not attached:
                problems.append("the second stdio client never appeared in `runtime status`.clients")
            code, payload, err = self.cli_json("runtime", "stop", timeout=BUDGET["stop"])
            refused_code = (payload or {}).get("code")
            if code == 0 or refused_code != "runtime.stop_refused_clients_attached":
                problems.append(f"`runtime stop` with a client attached: exit {code} code={refused_code!r} (expected refusal) {err[-200:]}")
            _c, status_after, _e = self.cli_json("runtime", "status", timeout=60)
            still = [e.get("label") for e in (status_after or {}).get("endpoints") or [] if e.get("reachable") is True]
            if len(still) < 2:
                problems.append(f"services went down although the stop was refused: reachable={still}")
        finally:
            client.terminate()
            try:
                client.wait(timeout=30)
            except subprocess.TimeoutExpired:
                client.kill()
        deadline = time.perf_counter() + 60
        while time.perf_counter() < deadline:
            _c, status, _e = self.cli_json("runtime", "status", timeout=60)
            if not attached or not set(attached) & set((status or {}).get("clients") or {}):
                break
            time.sleep(2)
        else:
            problems.append("the dead client is still listed in `runtime status`.clients (live_clients must drop dead pids)")
        return self.step("clients_attached_stop", not problems, seconds=round(time.perf_counter() - started, 1), problems=problems,
                         attached=attached)

    def restart_and_auto_ports(self) -> bool:
        """R12/R13：`runtime restart` 必 ok 并回到 ready；随后 HOROSA_PORTS=auto 必须复用登记表里的端口（不另挑一对）。"""
        started = time.perf_counter()
        code, payload, err = self.cli_json("runtime", "restart", timeout=BUDGET["start"] + 60)
        problems: list[str] = []
        if code != 0 or not payload or payload.get("ok") is not True:
            problems.append(f"runtime restart: exit {code} {(payload or {}).get('code')} {err[-300:]}")
        deadline = time.perf_counter() + BUDGET["start"]
        last: list[str] = ["doctor not run"]
        while time.perf_counter() < deadline and not problems:
            ok, report = self.doctor("doctor-after-restart")
            if ok:
                last = doctor_ready(report)
                if not last:
                    break
            time.sleep(DOCTOR_POLL_SECONDS)
        if last:
            problems.append(f"not ready after restart: {last}")
        auto_env = self.env(HOROSA_PORTS="auto")
        for key in ("HOROSA_LOCAL_BACKEND_PORT", "HOROSA_LOCAL_CHART_PORT"):
            auto_env.pop(key, None)
        _c, auto_report, _e = self.cli_json("doctor", timeout=BUDGET["doctor"], env=auto_env)
        provenance = {row.get("field"): row for row in (auto_report or {}).get("settings_provenance") or []}
        backend = provenance.get("local_backend_port") or {}
        if backend.get("source") != "auto:HOROSA_PORTS":
            problems.append(f"HOROSA_PORTS=auto provenance is {backend.get('source')!r}, expected auto:HOROSA_PORTS")
        if str(backend.get("value")) != str(self.args.backend_port):
            problems.append(f"HOROSA_PORTS=auto picked backend port {backend.get('value')} instead of reusing the registry's {self.args.backend_port}")
        reachable = [e.get("label") for e in (auto_report or {}).get("endpoints") or [] if e.get("reachable") is True]
        if len(reachable) < 2:
            problems.append(f"under HOROSA_PORTS=auto the running services are not both reachable: {reachable}")
        return self.step("restart_and_auto_ports", not problems, seconds=round(time.perf_counter() - started, 1), problems=problems,
                         auto_ports={"backend": backend.get("value"), "source": backend.get("source")})

    def live_pytest(self) -> bool:
        if self.args.skip_pytest:
            return self.step("pytest", True, skipped=True)
        env = self.pytest_env()
        started = time.perf_counter()
        command = [sys.executable, "-m", "pytest", "-q", "-rsf", "-p", "no:cacheprovider", *self.args.pytest_args]
        try:
            completed = subprocess.run(command, cwd=str(PKG_ROOT), env=env, capture_output=True, text=True,
                                       encoding="utf-8", errors="replace", timeout=BUDGET["pytest"])
        except subprocess.TimeoutExpired:
            return self.step("pytest", False, seconds=round(time.perf_counter() - started, 1), problems=["pytest timed out"])
        output = (completed.stdout or "") + "\n" + (completed.stderr or "")
        (self.work / "pytest.log").write_text(output, encoding="utf-8")
        counts = pytest_summary(output)
        skips = forbidden_skips(output)
        failures = failed_tests(output)
        problems: list[str] = []
        if completed.returncode != 0 or counts["failed"] or counts["error"]:
            problems.append(f"pytest exit {completed.returncode}: {counts}; failed: {failures}")
        if skips:
            problems.append(f"live gates skipped: {skips[:3]}")
        tail = "\n".join(output.splitlines()[-40:])
        return self.step("pytest", not problems, seconds=round(time.perf_counter() - started, 1), counts=counts, problems=problems,
                         failed=failures, env={"HOROSA_SERVER_ROOT": env["HOROSA_SERVER_ROOT"], "HOROSA_CHART_SERVER_ROOT": env["HOROSA_CHART_SERVER_ROOT"], "HOROSA_NODE_BIN": env.get("HOROSA_NODE_BIN")},
                         tail=tail if problems else None)

    def stop(self) -> bool:
        started = time.perf_counter()
        code, payload, err = self.cli_json("runtime", "stop", timeout=BUDGET["stop"])
        problems: list[str] = []
        if code != 0 or not payload or payload.get("ok") is not True:
            problems.append(
                f"stop exit {code}: ok={(payload or {}).get('ok')} code={(payload or {}).get('code')} "
                f"stdout={((payload or {}).get('stdout') or '')[-400:]!r} stderr={err[-400:]!r}"
            )
        # the manager waits ≤ 10 s for the ports to close; a JVM can take longer to exit — give it a grace period
        status: dict[str, Any] | None = None
        still: list[str] = []
        deadline = time.perf_counter() + 60
        while True:
            _code, status, _err = self.cli_json("runtime", "status", timeout=60)
            still = [str(e.get("label")) for e in (status or {}).get("endpoints") or [] if e.get("reachable") is True]
            if not still or time.perf_counter() > deadline:
                break
            time.sleep(3)
        if status and status.get("registry_status") not in (None, "stopped") and still:
            problems.append(f"registry_status after stop: {status.get('registry_status')}")
        if still:
            problems.append(f"still reachable after stop: {still}")
        return self.step("stop", not problems, seconds=round(time.perf_counter() - started, 1), problems=problems,
                         stop_result={k: (payload or {}).get(k) for k in ("ok", "already_stopped", "returncode", "code")})

    def run(self) -> dict[str, Any]:
        started = time.perf_counter()
        ok = self.non_ascii_root_refusal() and self.install() and self.doctor_after_install() and self.start()
        if ok:
            engines_ok = self.engines()
            clients_ok = self.client_setup()
            user_scope_ok = self.claude_code_user_scope()
            http_ok = self.http_probe()
            attached_ok = self.clients_attached_stop()
            restart_ok = self.restart_and_auto_ports()
            pytest_ok = self.live_pytest()
            ok = engines_ok and clients_ok and user_scope_ok and http_ok and attached_ok and restart_ok and pytest_ok
        # always try to leave the machine clean; a failed stop is a failure of its own
        stop_ok = self.stop() if (self.report["steps"].get("start") or {}).get("ok") else True
        self.report["ok"] = bool(ok and stop_ok)
        self.report["seconds"] = round(time.perf_counter() - started, 1)
        self.report["launcher_log"] = str(self.runtime_root / "launcher.log")
        self.report["service_logs"] = self._collect_service_logs()
        return self.report

    def _collect_service_logs(self) -> list[str]:
        """Copy launcher.log and the services' own logs next to the report (one artifact root, every OS)."""
        import shutil

        dest = self.work / "logs"
        dest.mkdir(exist_ok=True)
        copied: list[str] = []
        candidates = [self.runtime_root / "launcher.log"]
        current = self.runtime_root / "current"
        for logs_root in (current / "Horosa-Web" / ".horosa-local-logs", Path.home() / ".horosa-local-logs"):
            if logs_root.is_dir():
                candidates.extend(p for p in logs_root.rglob("*") if p.is_file() and p.suffix in {".log", ".txt", ".out", ".err"})
        for source in candidates[:40]:
            try:
                if source.is_file() and source.stat().st_size <= 5_000_000:
                    target = dest / (source.name if source.parent == self.runtime_root else f"{source.parent.name}-{source.name}")
                    shutil.copyfile(source, target)
                    copied.append(str(target))
            except OSError:
                continue
        return copied


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = ap.add_mutually_exclusive_group()
    source.add_argument("--archive", help="local runtime archive (install --archive)")
    source.add_argument("--assets-dir", help="directory with runtime-manifest.json + both archives (the pipeline artifact); URLs are localised")
    source.add_argument("--manifest-url", help="release manifest URL (default: the public latest)")
    ap.add_argument("--platform", default=None, help="force HOROSA_RUNTIME_PLATFORM (normally detected)")
    ap.add_argument("--expect-payload-platform", default=None, help="the payload the lane must end up with (win32-x64 on Windows on ARM)")
    ap.add_argument("--expect-emulated", action="store_true", help="the lane runs the payload under x64 emulation (win32-arm64)")
    ap.add_argument("--work-dir", default=None)
    ap.add_argument("--runtime-root", default=None)
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--start-timeout", type=int, default=900)
    ap.add_argument("--backend-port", type=int, default=19999, help="HOROSA_LOCAL_BACKEND_PORT for the lane (non-default on purpose)")
    ap.add_argument("--chart-port", type=int, default=18899, help="HOROSA_LOCAL_CHART_PORT for the lane (non-default on purpose)")
    ap.add_argument("--skip-pytest", action="store_true")
    ap.add_argument("--pytest-args", nargs="*", default=[])
    ap.add_argument("--out", default=None, help="also write the report here")
    args = ap.parse_args(argv)
    report = Lane(args).run()
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
