"""上游 v3.15.0 择日盘逐时 / 逐日择优（utils/aiTools/tools/scanElectionMoments.js）在 skill 的接法：
horosa_chart_election 的隐藏键 scanMode（hours | days）/ scanLimit（1–17）。

- 候选窗：electionScanCandidates 的 Python 端口（那份文件拖着 AI 助手壳，不能整份 vendor）——对拍用例把上游函数原文
  抠出来、配 vendored dateStrSafe 在 node 里跑，逐条比对。
- 每个候选同一个核：真 JS 引擎（vendored runElection）+ 脚本化 /chart 桩（日月黄经随请求时刻走）；真值 = 逐个候选用
  **单刻判读**（不带 scanMode）起的 [总评] 分数，排名规则按上游 workflow.rankResults 的文字定义判，不抄引擎输出。
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest
from node_esm import run_node_esm
from skips import needs_upstream, upstream_path
from test_sync311_mundane_election import ScriptedClient, _clean, _section, _service

from horosa_skill.service.runners.horary_election import _election_scan_candidates

PKG_ROOT = Path(__file__).resolve().parents[1]
DATE_STR_SAFE = PKG_ROOT / "horosa-core-js" / "src" / "vendor" / "bazi" / "dateStrSafe.js"
_UPSTREAM_SCAN = "Horosa-Web/astrostudyui/src/utils/aiTools/tools/scanElectionMoments.js"
requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="[host] node not on PATH")

BASE = {"date": "2028-04-06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "topicId": "surgery"}


# ──────────────────────────────── 候选窗 ────────────────────────────────

def test_hours_window_is_the_same_day_6_to_22_on_the_hour() -> None:
    cands = _election_scan_candidates("2028-04-06 09:33:00", "hours")
    assert [c["label"] for c in cands] == [f"{h:02d}:00" for h in range(6, 23)]
    assert [c["idx"] for c in cands] == list(range(17))
    assert cands[0]["time"] == "2028-04-06 06:00:00" and cands[-1]["time"] == "2028-04-06 22:00:00"


def test_days_window_walks_the_civil_calendar_for_14_days() -> None:
    cands = _election_scan_candidates("1582-10-01 08:05", "days")
    # 民用历：1582-10-04（儒略）的次日是 10-15（格里）；时刻原样、缺秒补 00。
    assert [c["time"] for c in cands[:5]] == [
        "1582-10-01 08:05:00", "1582-10-02 08:05:00", "1582-10-03 08:05:00", "1582-10-04 08:05:00", "1582-10-15 08:05:00",
    ]
    assert len(cands) == 14 and cands[4]["label"] == "10/15 08:05" and cands[-1]["idx"] == 13
    # 公元前 45 年 = 天文纪年 -44（无 0 年），儒略历闰年有 2 月 29 日；公元前 44 年（天文 -43）不闰。
    bce = _election_scan_candidates("-0045-02-27 12:00:00", "days")
    assert [c["time"][:11] for c in bce[:4]] == ["-0045-02-27", "-0045-02-28", "-0045-02-29", "-0045-03-01"]
    assert [c["time"][:11] for c in _election_scan_candidates("-0044-02-28 12:00:00", "days")[:2]] == ["-0044-02-28", "-0044-03-01"]


@pytest.mark.parametrize("base", ["", "2028-04-06", "28-04-06 09:00", "2028/04/06 09:00"])
def test_unreadable_base_gives_no_candidates(base: str) -> None:
    assert _election_scan_candidates(base, "hours") == [] and _election_scan_candidates(base, "days") == []


@requires_node
@needs_upstream(_UPSTREAM_SCAN, why="对拍上游 electionScanCandidates 原文")
def test_candidate_port_matches_the_upstream_function_verbatim() -> None:
    src = upstream_path(_UPSTREAM_SCAN).read_text(encoding="utf-8")
    m = re.search(r"export function electionScanCandidates\(baseStr, mode\)\{.*?\n\}\n", src, re.S)
    assert m, "上游 electionScanCandidates 形状变了——重审 Python 端口"
    fn = m.group(0).replace("export function", "function")
    bases = ["2028-04-06 09:33:00", "1582-10-01 08:05", "-0044-02-27 12:00:00", "2024-12-25T23:59", "12345-01-31 01:02:03", "bad"]
    script = (
        "const { civilJdnOfDateStr, civilDateStrOfJdn } = await import(process.argv[1]);\n"
        "const pad = (n)=>`${n}`.padStart(2, '0');\n"
        f"{fn}\n"
        f"const out = {{}}; for (const b of {json.dumps(bases)}) for (const m of ['hours','days']) out[b + '|' + m] = electionScanCandidates(b, m);\n"
        "process.stdout.write(JSON.stringify(out));\n"
    )
    upstream = json.loads(run_node_esm(script, DATE_STR_SAFE, timeout=60))
    for key, want in upstream.items():
        base, mode = key.rsplit("|", 1)
        assert _election_scan_candidates(base, mode) == want, key


# ──────────────────────────────── 服务级（真 JS 引擎） ────────────────────────────────

def _score(env) -> int:
    return int(env.data["judgment"]["overall"]["score"])


@requires_node
def test_hours_scan_ranks_every_candidate_with_the_single_moment_core(tmp_path) -> None:
    payload = {**BASE, "school": "persian", "scanMode": "hours", "scanLimit": 17}
    client = ScriptedClient()
    svc = _service(tmp_path, client)
    env = svc.run_tool("election", payload, save_result=False)
    assert env.ok, env.error
    scan = env.data["scan"]
    assert (scan["mode"], scan["total"], scan["failed"], len(scan["ranked"])) == ("hours", 17, 0, 17)
    # 真值：每个候选按单刻判读起（同 payload 只换时刻、不带 scanMode）。
    truth = {}
    for h in range(6, 23):
        single = svc.run_tool("election", {**BASE, "school": "persian", "time": f"{h:02d}:00:00"}, save_result=False)
        assert single.ok, single.error
        truth[f"2028-04-06 {h:02d}:00:00"] = _score(single)
    assert {r["time"]: r["score"] for r in scan["ranked"]} == truth
    assert len(set(truth.values())) > 1, "桩星历要让分数有高低，排名才有意义"
    # rankResults：分高者先；同分严重红线少者先、再较重红线少者先、再按时间先后。
    keys = [(-r["score"], r["crit"], r["high"], r["time"]) for r in scan["ranked"]]
    assert keys == sorted(keys)
    # 推荐语 = 上游 buildScanRecommendation 的句式，取第 1 名的标签。
    best = scan["ranked"][0]
    flag = "；注意仍含严重红线" if best["crit"] else ("；尚有较重代价" if best["high"] else "")
    assert scan["recommendation"] == f"窗口内较优：{best['time'][-8:-3]}（{best['score']} 分 · {best['grade']}）{flag}。"
    # 第 1 名时刻的完整判读：[总评] 分数与排名一致；末尾 [择优扫描] 列全表。
    assert _score(env) == best["score"]
    text = env.data["snapshot_text"]
    body = _section(text, "择优扫描")
    assert body[0] == "窗口：本日逐时择优（6:00–22:00）" and body[1] == "已评 17 个候选时刻。"
    assert body[2].startswith(scan["recommendation"]) and len(body) == 3 + 17 + 1
    assert body[3].startswith(f"1. {best['time']}（{best['time'][-8:-3]}）· {best['score']} 分 · {best['grade']}")
    assert text.rstrip().split("\n")[-1] == body[-1] and best["time"] in body[-1]
    _clean(env)
    # 流派宫制联动（persian → hsys 1）随每张候选盘走。
    cand_reqs = [r for r in client.requests("/chart")][:17]
    assert [r["time"] for r in cand_reqs] == [f"{h:02d}:00:00" for h in range(6, 23)]
    assert {r["hsys"] for r in cand_reqs} == {1}


@requires_node
def test_scan_limit_defaults_to_five_and_days_mode_walks_the_calendar(tmp_path) -> None:
    client = ScriptedClient()
    env = _service(tmp_path, client).run_tool("election", {**BASE, "date": "2028-02-25", "scanMode": "days"}, save_result=False)
    assert env.ok, env.error
    scan = env.data["scan"]
    assert (scan["mode"], scan["total"], len(scan["ranked"])) == ("days", 14, 5)
    dates = [r["date"] for r in client.requests("/chart")[:14]]
    assert dates[:6] == ["2028/02/25", "2028/02/26", "2028/02/27", "2028/02/28", "2028/02/29", "2028/03/01"]
    assert _section(env.data["snapshot_text"], "择优扫描")[0] == "窗口：未来 14 日同时刻择优"
    assert all(r["time"].endswith(" 09:33:00") for r in scan["ranked"])


@requires_node
def test_failed_candidates_are_counted_and_announced(tmp_path) -> None:
    class Flaky(ScriptedClient):
        def call(self, endpoint, payload):
            if endpoint in ("/", "/chart") and payload.get("time") in ("10:00:00", "11:00:00"):
                raise RuntimeError("chart service hiccup")
            return super().call(endpoint, payload)

    env = _service(tmp_path, Flaky()).run_tool("election", {**BASE, "scanMode": "hours"}, save_result=False)
    assert env.ok, env.error
    assert (env.data["scan"]["total"], env.data["scan"]["failed"]) == (15, 2)
    assert "已评 15 个候选时刻（2 个未能起盘评分）。" in _section(env.data["snapshot_text"], "择优扫描")
    assert any("择优扫描：2 个候选时刻起盘失败" in w for w in env.warnings)


@requires_node
def test_scan_with_no_scorable_candidate_is_a_transport_error(tmp_path) -> None:
    class Down(ScriptedClient):
        def call(self, endpoint, payload):
            if endpoint in ("/", "/chart"):
                raise RuntimeError("chart service down")
            return super().call(endpoint, payload)

    env = _service(tmp_path, Down()).run_tool("election", {**BASE, "scanMode": "hours"}, save_result=False)
    assert not env.ok and env.error.code == "tool.election_scan_failed"
    assert env.error.details["candidates"] == 17 and len(env.error.details["failed"]) == 5


@pytest.mark.parametrize(
    ("extra", "bad_key"),
    [
        ({"scanMode": "weeks"}, "scanMode"),
        ({"scanMode": "hours", "scanLimit": 0}, "scanLimit"),
        ({"scanMode": "hours", "scanLimit": 18}, "scanLimit"),
        ({"scanMode": "hours", "scanLimit": True}, "scanLimit"),
        ({"scanLimit": 3}, "scanLimit"),  # 只给名次数、没给窗：不猜 hours
    ],
)
def test_bad_scan_settings_are_refused(tmp_path, extra: dict, bad_key: str) -> None:
    env = _service(tmp_path, ScriptedClient()).run_tool("election", {**BASE, **extra}, save_result=False)
    assert not env.ok and env.error.code == "tool.election_invalid_setting"
    assert bad_key in json.dumps(env.error.details, ensure_ascii=False)


def test_scan_section_is_registered_as_a_conditional_skill_section() -> None:
    from horosa_skill.exports.registry import AI_EXPORT_OPTIONAL_SECTIONS, AI_EXPORT_PRESET_SECTIONS

    assert AI_EXPORT_PRESET_SECTIONS["election"][-1] == "择优扫描"
    assert "择优扫描" in AI_EXPORT_OPTIONAL_SECTIONS["election"]
