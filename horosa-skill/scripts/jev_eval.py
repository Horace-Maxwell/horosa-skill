"""决策层评测 CLI：lint → measure（真调用 + 录制）→ replay/compile（零调用）→ check（漂移）。

    uv run python scripts/jev_eval.py lint                      # 无 key：问题规格 + 金标集静态检查
    HOROSA_JEV_API_KEY=… uv run python scripts/jev_eval.py measure [--surface routing] [--runs 1] [--limit N]
    uv run python scripts/jev_eval.py compile                   # 回放缓存 → 训练集选 τ → 留出集过闸 → 写阈值锁
    uv run python scripts/jev_eval.py check                     # 锁 vs 当前数据集/缓存/模型：漂移即非零退出
    uv run python scripts/jev_eval.py report                    # 打印上次 compile 的报告

所有真调用只在 `measure`；其余子命令离线。晋升闸 `PROMOTION_GATES` 在 decisions/eval.py 里预注册。
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Windows 控制台默认 cp1252/cp936：脚本自己 print 的中文会抛 UnicodeEncodeError（tests/test_scripts_stdio.py 守卫）。
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG / "src"))

from horosa_skill.decisions import eval as ev
from horosa_skill.decisions.policy import DEFAULT_MODEL, read_api_key
from horosa_skill.decisions.surfaces.zhancat import ZHANDUAN_CATEGORIES
from horosa_skill.engine.registry import TOOL_DEFINITIONS


def _deterministic_route(query: str) -> list[str]:
    from horosa_skill.engine.router import select_tools
    from horosa_skill.errors import DispatchResolutionError
    from horosa_skill.schemas.tools import DispatchInput

    try:
        return list(select_tools(DispatchInput(query=query)))
    except DispatchResolutionError:
        return []


def cmd_lint(args: argparse.Namespace) -> int:
    problems = ev.lint_questions()
    for surface in ev.SURFACES:
        cases = ev.load_cases(surface)
        if len(cases) < 60:
            problems.append(f"{surface}: only {len(cases)} cases (< 60)")
        texts = [ev.case_text(surface, case) for case in cases]
        if len(set(texts)) != len(texts):
            problems.append(f"{surface}: duplicate case text")
        for case in cases:
            if surface == "routing":
                labels = ([case["expect"]] if case.get("expect") else []) + list(case.get("accept") or [])
                bad = [label for label in labels if label not in TOOL_DEFINITIONS]
                if bad:
                    problems.append(f"routing: unknown tool label {bad} in {case['query']!r}")
            elif surface == "extract" and case.get("expect") not in {"female", "male", "not_stated"}:
                problems.append(f"extract: bad label {case.get('expect')!r} in {case['query']!r}")
            elif surface == "zhancat" and case.get("expect") not in ZHANDUAN_CATEGORIES:
                problems.append(f"zhancat: bad label {case.get('expect')!r} in {case['question']!r}")
        train, holdout = ev.split_cases(cases, surface=surface)
        print(f"{surface}: {len(cases)} cases (train {len(train)} / holdout {len(holdout)}), sha {ev.dataset_sha256(surface)[:12]}")
    if problems:
        print("jev-eval lint: FAIL\n- " + "\n- ".join(problems))
        return 1
    print("jev-eval lint: ok")
    return 0


def cmd_measure(args: argparse.Namespace) -> int:
    key = read_api_key()
    if not key:
        print("jev-eval measure: FAIL — HOROSA_JEV_API_KEY / TYPESAFE_API_KEY not set", file=sys.stderr)
        return 2
    from horosa_skill.decisions.jev_http import JevHttpClient

    client = JevHttpClient(api_key=key, model=args.model, timeout_s=15.0)
    cache = ev.ResponseCache()
    surfaces = [args.surface] if args.surface else list(ev.SURFACES)
    total_calls = 0
    for surface in surfaces:
        cases = ev.load_cases(surface)
        if args.limit:
            cases = cases[: args.limit]
        for run in range(args.runs):
            pending = []
            for case in cases:
                state, questions = ev.build_request(surface, case)
                if cache.get(ev.request_digest(state, questions, args.model, run)) is None:
                    pending.append(case)

            def fetch(state: dict[str, Any], questions: dict[str, Any], *, _surface: str = surface) -> tuple[dict[str, Any], int]:
                return client.decide_raw(state=state, questions=questions, surface=f"eval:{_surface}")

            def work(case: dict[str, Any], *, _surface: str = surface, _run: int = run, _fetch=fetch) -> None:
                ev.answers_for(_surface, case, model=args.model, cache=cache, run=_run, fetch=_fetch)

            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                list(pool.map(work, pending))
            total_calls += len(pending)
            print(f"{surface} run {run}: {len(pending)} new call(s), {len(cases) - len(pending)} cached")
    print(f"jev-eval measure: ok ({total_calls} call(s) recorded; cache {len(cache)} rows at {cache.path})")
    return 0


def _judged_runs(surface: str, cases: list[dict[str, Any]], *, model: str, cache: ev.ResponseCache, tau: float, runs: int) -> list[list[ev.Judged]]:
    out: list[list[ev.Judged]] = []
    for run in range(runs):
        judged: list[ev.Judged] = []
        for case in cases:
            answers = ev.answers_for(surface, case, model=model, cache=cache, run=run)
            if answers is None:
                continue
            det = _deterministic_route(case["query"]) if surface == "routing" else None
            judged.append(ev.judge(surface, case, answers, tau=tau, deterministic=det))
        out.append(judged)
    return out


def cmd_compile(args: argparse.Namespace) -> int:
    cache = ev.ResponseCache()
    if not len(cache):
        print("jev-eval compile: FAIL — no recorded responses (run `measure` first)", file=sys.stderr)
        return 2
    report: dict[str, Any] = {
        "schema": "horosa.skill.jev_eval_report.v1",
        "model": args.model,
        "compiled_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "gates": ev.PROMOTION_GATES,
        "surfaces": {},
    }
    lock: dict[str, Any] = {
        "_comment": "决策层阈值锁：只由 scripts/jev_eval.py compile 在留出集全部预注册闸通过时写 promoted=true；enforce 只认它。",
        "model": args.model,
        "compiled_at": report["compiled_at"],
        "datasets": {},
        "surfaces": {},
    }
    for surface in ev.SURFACES:
        cases = ev.load_cases(surface)
        train, holdout = ev.split_cases(cases, surface=surface)
        covered_train = [c for c in train if ev.answers_for(surface, c, model=args.model, cache=cache) is not None]
        covered_holdout = [c for c in holdout if ev.answers_for(surface, c, model=args.model, cache=cache) is not None]
        if not covered_train or not covered_holdout:
            report["surfaces"][surface] = {"skipped": "no recorded responses for this surface"}
            continue

        def judge_at(tau: float, _cases: list[dict[str, Any]] = covered_train, *, _surface: str = surface) -> list[ev.Judged]:
            return _judged_runs(_surface, _cases, model=args.model, cache=cache, tau=tau, runs=1)[0]

        tau, train_metrics = ev.choose_tau(surface, judge_at)
        holdout_runs = _judged_runs(surface, covered_holdout, model=args.model, cache=cache, tau=tau, runs=args.runs)
        holdout_metrics = ev.evaluate(surface, holdout_runs[0], tau=tau)
        consistency = ev.summarize_runs(holdout_runs)
        verdicts = ev.gate_verdicts(surface, holdout_metrics)
        promoted = all(item["pass"] for item in verdicts.values())
        model_seen = sorted({str(cache.get(ev.request_digest(*ev.build_request(surface, c), args.model, 0))["model"]) for c in covered_holdout if cache.get(ev.request_digest(*ev.build_request(surface, c), args.model, 0))})
        report["surfaces"][surface] = {
            "tau": tau,
            "train": train_metrics,
            "holdout": holdout_metrics,
            "consistency": consistency,
            "gates": verdicts,
            "promoted": promoted,
            "model_returned": model_seen,
            "coverage": {"train": f"{len(covered_train)}/{len(train)}", "holdout": f"{len(covered_holdout)}/{len(holdout)}"},
        }
        lock["datasets"][surface] = ev.dataset_sha256(surface)
        lock["surfaces"][ev.POLICY_SURFACE[surface]] = {
            "tau": tau,
            "promoted": promoted,
            "holdout_n": holdout_metrics["n"],
            "accuracy_decided": (holdout_metrics.get("nomatch") or {}).get("accuracy_decided") if surface == "routing" else holdout_metrics.get("accuracy_decided"),
            "handled": holdout_metrics["handled"],
            "ece": holdout_metrics["ece"],
            "escalation": holdout_metrics["escalation"],
            "failed_gates": sorted(name for name, item in verdicts.items() if not item["pass"]),
        }
        status = "PROMOTED" if promoted else "not promoted"
        print(f"{surface}: tau={tau:.2f} holdout n={holdout_metrics['n']} acc_decided={holdout_metrics.get('accuracy_decided')} "
              f"handled={holdout_metrics['handled']} ece={holdout_metrics['ece']} escalation={holdout_metrics['escalation']} → {status}"
              + (f" (failed: {', '.join(lock['surfaces'][ev.POLICY_SURFACE[surface]]['failed_gates'])})" if not promoted else ""))
    ev.REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ev.THRESHOLDS_PATH.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"jev-eval compile: wrote {ev.REPORT_PATH.name} + {ev.THRESHOLDS_PATH.name}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    if not ev.THRESHOLDS_PATH.is_file():
        print("jev-eval check: no thresholds lock (nothing enforced) — ok")
        return 0
    lock = json.loads(ev.THRESHOLDS_PATH.read_text(encoding="utf-8"))
    problems: list[str] = []
    if lock.get("model") != args.model:
        problems.append(f"lock model {lock.get('model')!r} != {args.model!r}")
    for surface in ev.SURFACES:
        recorded = (lock.get("datasets") or {}).get(surface)
        current = ev.dataset_sha256(surface)
        if recorded and recorded != current:
            problems.append(f"{surface}: dataset changed since the lock (sha {recorded[:12]} → {current[:12]}) — re-run compile")
    cache = ev.ResponseCache()
    for surface in ev.SURFACES:
        entry = (lock.get("surfaces") or {}).get(ev.POLICY_SURFACE[surface]) or {}
        if not entry.get("promoted"):
            continue
        cases = ev.load_cases(surface)
        _train, holdout = ev.split_cases(cases, surface=surface)
        covered = [c for c in holdout if ev.answers_for(surface, c, model=args.model, cache=cache) is not None]
        if not covered:
            problems.append(f"{surface}: promoted but no recorded holdout responses to replay")
            continue
        judged = _judged_runs(surface, covered, model=args.model, cache=cache, tau=float(entry["tau"]), runs=1)[0]
        verdicts = ev.gate_verdicts(surface, ev.evaluate(surface, judged, tau=float(entry["tau"])))
        failed = sorted(name for name, item in verdicts.items() if not item["pass"])
        if failed:
            problems.append(f"{surface}: promoted surface no longer passes gates on replay: {failed}")
    if problems:
        print("jev-eval check: FAIL\n- " + "\n- ".join(problems))
        return 1
    promoted = sorted(name for name, entry in (lock.get("surfaces") or {}).items() if entry.get("promoted"))
    print(f"jev-eval check: ok (model {lock.get('model')}; promoted: {promoted or 'none'})")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    if not ev.REPORT_PATH.is_file():
        print("jev-eval report: no report yet (run compile)")
        return 1
    print(ev.REPORT_PATH.read_text(encoding="utf-8"))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("lint")
    measure = sub.add_parser("measure")
    measure.add_argument("--surface", choices=ev.SURFACES)
    measure.add_argument("--runs", type=int, default=1)
    measure.add_argument("--limit", type=int, default=0)
    measure.add_argument("--workers", type=int, default=4)
    compile_ = sub.add_parser("compile")
    compile_.add_argument("--runs", type=int, default=1, help="replay this many recorded runs for the flip-rate summary")
    sub.add_parser("check")
    sub.add_parser("report")
    args = parser.parse_args()
    return {"lint": cmd_lint, "measure": cmd_measure, "compile": cmd_compile, "check": cmd_check, "report": cmd_report}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
