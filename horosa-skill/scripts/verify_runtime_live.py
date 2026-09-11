#!/usr/bin/env python3
"""Live verification of a runtime payload on a real machine (v0.38.0 A5 — the runtime-matrix lanes).

Drives the `horosa-skill` CLI as subprocesses exactly the way a user would, on the machine it runs on:

  install (manifest or archive) → doctor → runtime start (+ poll doctor until ready) → four engine calls
  (chart / qimen / nongli_time / bazi_birth) → `setup --client …` for four clients (config → re-read →
  real stdio probe) → the live pytest suite against the running endpoints → runtime stop.

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
CLIENTS = ("claude-code", "codex", "cursor", "claude-desktop")
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
        return self.step("install", not problems, seconds=seconds, platform=payload.get("platform"), platform_fallback=fallback,
                         warnings=[w.get("code") for w in payload.get("warnings") or []], problems=problems,
                         version=(payload.get("manifest") or {}).get("version"), source=source_args)

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
        code, payload, err = self.cli_json("runtime", "start", timeout=BUDGET["start"] + 60)
        if code != 0 or not payload or payload.get("ok") is not True:
            return self.step("start", False, seconds=round(time.perf_counter() - started, 1), code=(payload or {}).get("code"), stderr=err)
        deadline = started + BUDGET["start"]
        last: list[str] = ["doctor not run"]
        while time.perf_counter() < deadline:
            ok, report = self.doctor("doctor-after-start")
            if ok:
                last = doctor_ready(report)
                if not last:
                    for endpoint in report.get("endpoints") or []:
                        self.endpoints[str(endpoint.get("label"))] = str(endpoint.get("url"))
                    return self.step("start", True, seconds=round(time.perf_counter() - started, 1), endpoints=self.endpoints,
                                     listener_scope=report.get("listener_scope"))
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
        ok = self.install() and self.doctor_after_install() and self.start()
        if ok:
            engines_ok = self.engines()
            clients_ok = self.client_setup()
            pytest_ok = self.live_pytest()
            ok = engines_ok and clients_ok and pytest_ok
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
