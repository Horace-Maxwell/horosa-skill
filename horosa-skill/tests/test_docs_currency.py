"""文档实时更新制度（v0.40.0，AGENTS §2 协议 v3）的四把守卫，各带负向对照：

1. DOC_MAP：仓里每份指导性文档必须在 docs/DOC_MAP.md 有一行（新文档不登记即红）。
2. LESSONS 蒸馏：每个 `### vX / …` 节必有索引行；最新三个版本必须在 AGENTS.md 里被蒸馏（出现版本号）。
3. 镜像 = 生成件：四份薄镜像必须逐字等于 scripts/gen_agent_mirrors.py 的渲染。
4. 第三方事实账本：每个 required_subjects 有条目、来源是 https、日期合法、affects 路径存在；超龄条目 CI 只 warning，
   `--strict-staleness` 下报错（docs-currency.yml 每周一执行并开 issue）。
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
ROOT = PKG_ROOT.parent
_spec = importlib.util.spec_from_file_location("verify_docs_sync", PKG_ROOT / "scripts" / "verify_docs_sync.py")
ds = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(ds)
_gspec = importlib.util.spec_from_file_location("gen_agent_mirrors", PKG_ROOT / "scripts" / "gen_agent_mirrors.py")
gen = importlib.util.module_from_spec(_gspec)
assert _gspec.loader is not None
_gspec.loader.exec_module(gen)


# ---- 1. DOC_MAP -------------------------------------------------------------------------------
def test_every_guidance_doc_has_a_doc_map_row() -> None:
    docs = ds.guidance_docs()
    assert "AGENTS.md" in docs and "docs/LESSONS.md" in docs and "GEMINI.md" in docs, docs
    assert ds.doc_map_problems(docs, ds.doc_map_rows(ds.read(ds.DOC_MAP))) == []


def test_doc_map_catches_an_unregistered_doc() -> None:
    rows = ds.doc_map_rows(ds.read(ds.DOC_MAP))
    problems = ds.doc_map_problems(["docs/NEW_GUIDE.md", "AGENTS.md"], rows)
    assert len(problems) == 1 and "docs/NEW_GUIDE.md" in problems[0]


def test_doc_map_row_parser_accepts_multi_doc_rows_and_annotations() -> None:
    text = "| `CONTRIBUTING.md` / `SECURITY.md` | x | y | z |\n| `CHANGELOG.md`（gitignored 本地件） | a | b | c |\n| not a row |\n"
    assert ds.doc_map_rows(text) == {"CONTRIBUTING.md", "SECURITY.md", "CHANGELOG.md"}


# ---- 2. LESSONS → AGENTS ----------------------------------------------------------------------
def test_real_lessons_are_indexed_and_the_newest_versions_are_distilled() -> None:
    assert ds.lessons_distillation_problems(ds.read(ROOT / "docs" / "LESSONS.md"), ds.read(ROOT / "AGENTS.md")) == []


def test_lessons_guard_catches_a_missing_index_row_and_a_missing_distillation() -> None:
    lessons = "| 时代 | 条目 | 一句话 |\n| --- | --- | --- |\n| v0.41.0 (2026-10) | a | b |\n\n### v0.41.0 / 2026-10-01 — new\n\n### v0.40.0 / 2026-09-29 — old\n"
    problems = ds.lessons_distillation_problems(lessons, "AGENTS mentions v0.40.0 only")
    assert any("v0.40.0" in p and "no index row" in p for p in problems), problems
    assert any("never mentions v0.41.0" in p for p in problems), problems
    assert ds.lessons_distillation_problems(lessons.replace("| v0.41.0 (2026-10) | a | b |", "| v0.41.0 (2026-10) | a | b |\n| v0.40.0 (2026-09) | c | d |"),
                                            "v0.41.0 and v0.40.0 distilled") == []


# ---- 3. mirrors are generated ----------------------------------------------------------------
def test_real_mirrors_match_the_generator() -> None:
    assert gen.drift() == []


def test_mirror_drift_is_detected(tmp_path: Path) -> None:
    for rel in gen.MIRRORS:
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(gen.render(rel, techniques=110, compact=11), encoding="utf-8")
    assert gen.drift(tmp_path, techniques=110, compact=11) == []
    (tmp_path / "GEMINI.md").write_text(gen.render("GEMINI.md", techniques=110, compact=11).replace("Never hand-calculate", "Hand-calculate freely"), encoding="utf-8")
    assert gen.drift(tmp_path, techniques=110, compact=11) == ["GEMINI.md"]
    (tmp_path / ".clinerules" / "horosa-skill.md").unlink()
    assert set(gen.drift(tmp_path, techniques=110, compact=11)) == {"GEMINI.md", ".clinerules/horosa-skill.md"}


def test_generated_mirrors_still_satisfy_the_thin_mirror_contract() -> None:
    for rel in gen.MIRRORS:
        text = gen.render(rel, techniques=110, compact=11)
        assert len(text.rstrip("\n").splitlines()) <= ds.AGENT_MIRROR_MAX_LINES, rel
        for keyword in ds.AGENT_MIRROR_KEYWORDS:
            assert keyword in text, (rel, keyword)
        assert ds.AGENT_MIRRORS[rel] in text, rel


# ---- 4. third-party facts ledger --------------------------------------------------------------
def _ledger() -> dict:
    return json.loads(ds.read(ds.THIRD_PARTY_LEDGER))


def test_real_ledger_is_complete_sourced_dated_and_points_at_real_files() -> None:
    # The real ledger is judged against the real date, exactly like the CLI: a frozen "today" turns every
    # re-verification (bumping verified_on, which the ledger itself asks for) into a "future" failure.
    assert ds.third_party_fact_problems(_ledger(), dt.date.today()) == []


def test_ledger_guard_catches_missing_subject_bad_url_bad_date_and_dead_path() -> None:
    ledger = {"max_age_days": 120, "required_subjects": ["codex", "zed"], "facts": [
        {"id": "codex.x", "subject": "codex", "fact": "f", "source_url": "http://insecure", "verified_on": "2026-13-01", "affects": ["nope/missing.py"]},
    ]}
    problems = ds.third_party_fact_problems(ledger, dt.date(2026, 9, 29))
    assert any("https" in p for p in problems) and any("YYYY-MM-DD" in p for p in problems)
    assert any("nope/missing.py" in p for p in problems) and any("`zed` has no entry" in p for p in problems)
    ahead = {"max_age_days": 120, "required_subjects": [], "facts": [
        {"id": "ahead", "subject": "s", "fact": "f", "source_url": "https://x", "verified_on": "2026-09-30", "affects": ["horosa-skill/pyproject.toml"]},
    ]}
    assert ds.third_party_fact_problems(ahead, dt.date(2026, 9, 29)) == ["third_party_facts[ahead]: verified_on 2026-09-30 is in the future"]
    assert ds.third_party_fact_problems(ahead, dt.date(2026, 9, 30)) == []


def test_staleness_is_a_warning_in_ci_and_an_error_under_strict() -> None:
    ledger = {"max_age_days": 120, "required_subjects": [], "facts": [
        {"id": "fresh", "subject": "s", "fact": "f", "source_url": "https://x", "verified_on": "2026-09-01", "affects": []},
        {"id": "old", "subject": "s", "fact": "f", "source_url": "https://x", "verified_on": "2026-01-01", "affects": []},
    ]}
    assert ds.stale_facts(ledger, dt.date(2026, 9, 29)) == [("old", 271)]
    assert ds.stale_facts(ledger, dt.date(2026, 9, 29), max_age_days=400) == []
    # the CLI: default run must not fail on age alone; --strict-staleness must
    env_ok = subprocess.run([sys.executable, str(PKG_ROOT / "scripts" / "verify_docs_sync.py"), "--only", "third-party-facts"],
                            capture_output=True, text=True, encoding="utf-8", cwd=str(PKG_ROOT))
    assert env_ok.returncode == 0, env_ok.stdout + env_ok.stderr


def test_strict_staleness_fails_when_a_fact_is_old(tmp_path: Path, monkeypatch) -> None:
    old = dict(_ledger())
    old["facts"] = [dict(old["facts"][0], verified_on="2025-01-01")]
    old["required_subjects"] = []
    ledger_path = tmp_path / "third_party_facts.json"
    ledger_path.write_text(json.dumps(old), encoding="utf-8")
    monkeypatch.setattr(ds, "THIRD_PARTY_LEDGER", ledger_path)
    ds.ERRORS.clear(); ds.WARNINGS.clear()
    ds.check_third_party_facts(strict_staleness=False, today=dt.date(2026, 9, 29))
    assert ds.ERRORS == [] and ds.WARNINGS and "days ago" in ds.WARNINGS[0]
    ds.ERRORS.clear(); ds.WARNINGS.clear()
    ds.check_third_party_facts(strict_staleness=True, today=dt.date(2026, 9, 29))
    assert ds.ERRORS and "days ago" in ds.ERRORS[0]
    ds.ERRORS.clear(); ds.WARNINGS.clear()


def test_docs_currency_workflow_runs_the_strict_check_weekly_off_the_hour() -> None:
    wf = ds.read(ROOT / ".github" / "workflows" / "docs-currency.yml")
    assert "--strict-staleness --only third-party-facts" in wf and "schedule:" in wf
    minute = wf.split("cron: \"")[1].split(" ")[0]
    assert minute != "0", "GitHub delays/drops :00 slots — keep the cron off the hour"
    assert "issues: write" in wf and "gh issue" in wf


def test_bump_version_script_agrees_with_pyproject() -> None:
    result = subprocess.run([sys.executable, str(PKG_ROOT / "scripts" / "bump_version.py"), "--check"],
                            capture_output=True, text=True, encoding="utf-8", cwd=str(PKG_ROOT))
    assert result.returncode == 0, result.stdout + result.stderr


def test_lessons_guard_requires_code_anchors_of_recent_titles_in_agents() -> None:
    """版本号出现 ≠ 规则蒸馏了：最新版本的台账标题若点名了代码标识符（反引号），AGENTS.md 里至少要出现其中一个。"""
    lessons = ("| 时代 | 条目 | 一句话 |\n| --- | --- | --- |\n| v0.41.0 (2026-10) | a | b |\n\n"
               "### v0.41.0 / 2026-10-01 — `src/shared/foo.js` 是近似公式，`buildSeed` 差 6 小时\n\nbody\n")
    assert ds.lessons_distillation_problems(lessons, "v0.41.0 mentioned but no identifiers") != []
    assert ds.lessons_distillation_problems(lessons, "v0.41.0: `buildSeed` now reads the precise table") == []
    untitled = lessons.replace("`src/shared/foo.js` 是近似公式，`buildSeed` 差 6 小时", "一条没有代码标识符的教训")
    assert ds.lessons_distillation_problems(untitled, "v0.41.0") == []


def test_group_header_guard_counts_ids_in_first_column() -> None:
    zh = "<details>\n<summary>⏳ <b>推运（2）</b></summary>\n\n| 工具 ID | 名称 |\n| --- | --- |\n| `a` ⓟ / `b` ⓟ | x |\n</details>\n"
    assert ds.group_header_problems(zh) == []
    assert ds.group_header_problems(zh.replace("（2）", "（3）")) != []
    en = "### Western (1)\n\n| Tool ID | Name |\n| --- | --- |\n| `a` | x |\n| `a` | dup |\n\n### Next (0)\n"
    assert ds.group_header_problems(en) == []
    two = "<summary>x（6）+ y（11）</b></summary>\n| `a` | z |\n"
    assert ds.group_header_problems(two) == []  # two-number headers are check_tool_counts' business


def test_export_contract_guard_reads_both_numbers() -> None:
    zh_pat = dict(ds.EXPORT_CONTRACT_CLAIMS)["README.md"]
    ok = "（导出契约 v15 镜像桌面端 aiExport v58）"
    assert ds.export_contract_problems(ok, zh_pat, contract=15, mirrored=58, label="t") == []
    assert ds.export_contract_problems(ok, zh_pat, contract=16, mirrored=58, label="t") != []
    assert ds.export_contract_problems("no claim here", zh_pat, contract=15, mirrored=58, label="t") != []
    en_pat = dict(ds.EXPORT_CONTRACT_CLAIMS)["README_EN.md"]
    for text in (
        "export contract v15 mirrors the desktop app's aiExport v58",
        "contract v15 mirrors desktop aiExport v58",
        "The export contract (v15) mirrors the desktop app's aiExport v58 section-for-section.",
    ):
        assert ds.export_contract_problems(text, en_pat, contract=15, mirrored=58, label="t") == [], text
        assert ds.export_contract_problems(text.replace("v58", "v56"), en_pat, contract=15, mirrored=58, label="t") != [], text


def test_gate_count_guard_locks_gated_and_exempt_rows() -> None:
    gated = ds.GATE_COUNT_CLAIMS[0][1]
    assert ds.gate_count_problems("`100` technique tools trigger `must_ask_user=true`", gated, expected=100, label="t") == []
    assert ds.gate_count_problems("`84` technique tools trigger `must_ask_user=true`", gated, expected=100, label="t") != []
    assert ds.gate_count_problems("nothing lockable", gated, expected=100, label="t") != []
    exempt_zh = ds.GATE_COUNT_CLAIMS[1][1]
    assert ds.gate_count_problems("| 🔓 免闸直读 | 10 个注册表 / 知识 / 解析类工具不经澄清闸 |", exempt_zh, expected=10, label="t") == []
