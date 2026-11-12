"""择日条件的极性与回显（深审 F5）：每类条件一行中英说明（生成自上游十张注册表）、negate 的规则写明、每次择日结果回显
引擎把条件树读成了什么；黄历择吉「冲煞生肖 马」不加 negate = 排除冲马的日子（真引擎）。"""
from __future__ import annotations

import json
import shutil
from datetime import date, timedelta
import subprocess
from pathlib import Path

import pytest
from fakes import FakeClient, FakeJsClient

from horosa_skill.agent_guidance import build_agent_guidance
from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.testing_payloads import build_sample_payloads
from horosa_skill.zeri_conditions import DATA_PATH, meanings, zeri_tools

PKG = Path(__file__).resolve().parents[1]
CLI = PKG / "horosa-core-js" / "bin" / "cli.mjs"
requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="[host] node not on PATH")
TEN = ("huanglizeri", "tianxing", "qimenzeri", "bazizeri", "taiyizeri", "ziweizeri", "liurengzeri", "sanshizeri", "qizhengzeri", "indiazeri")


def _js(payload: dict) -> dict:
    out = subprocess.run(["node", str(CLI), "run", "zeri_conditions"], input=json.dumps(payload, ensure_ascii=False),
                         capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(out.stdout)["data"]


def test_the_meaning_table_covers_all_ten_and_states_polarity() -> None:
    assert sorted(zeri_tools()) == sorted(TEN)
    rule = meanings()["negate_rule"]
    assert "取反" in rule["zh"] and "inverts" in rule["en"] and "双重否定" in rule["zh"]
    chong = next(row for row in meanings()["techniques"]["huanglizeri"] if row["type"] == "chong_shengxiao")
    assert "without=不冲所选肖（缺省）" in chong["zh"] and "with=冲所选肖" in chong["zh"] and "(default)" in chong["en"]
    for tool in TEN:
        guidance = build_agent_guidance(tool_name=tool)["tools"][tool]["condition_types"]
        assert " / " in guidance["negate_rule"]
        assert set(guidance["types"]) == {row["type"] for row in meanings()["techniques"][tool]}


@requires_node
def test_generated_meanings_match_the_engine_tables() -> None:
    """生成件：上游注册表变了（re-vendor）而没重跑生成脚本 → 红。"""
    result = subprocess.run(["uv", "run", "python", "scripts/gen_zeri_condition_meanings.py", "--check"], cwd=PKG,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert DATA_PATH.is_file()


@requires_node
@pytest.mark.parametrize("technique", TEN)
def test_every_condition_type_echoes_in_plain_words(technique: str) -> None:
    catalog = _js({"action": "catalog"})["catalog"][technique]
    children = []
    for index, entry in enumerate(catalog):
        leaf = {"kind": "leaf", "type": entry["type"], "negate": index % 2 == 1, "params": {}}
        if index:
            leaf["joiner"] = ("all", "any", "xor")[index % 3]
        children.append(leaf)
    lines = _js({"action": "echo", "technique": technique, "tree": {"kind": "group", "joiner": "all", "children": children}})["lines"]
    assert len(lines) == len(catalog)
    for index, (entry, line) in enumerate(zip(catalog, lines)):
        assert entry["label"] in line["zh"] and entry["type"] in line["en"], (entry, line)
        if index % 2:
            assert "不满足〔" in line["zh"] and "取反" in line["zh"] and line["en"].lstrip().split(" ", 1)[1].startswith("NOT [")
        if index:
            assert line["zh"].split(" ", 1)[0] in ("且", "或", "异或")


@requires_node
def test_nested_and_negated_groups_echo() -> None:
    tree = {"kind": "group", "joiner": "all", "children": [
        {"kind": "leaf", "type": "yi_has", "params": {"values": ["移徙"]}},
        {"kind": "group", "joiner": "any", "negate": True, "children": [
            {"kind": "leaf", "type": "chong_shengxiao", "params": {"values": ["马"], "mode": "with"}},
            {"kind": "leaf", "type": "jianchu", "joiner": "any", "params": {"values": ["破"]}},
        ]},
    ]}
    lines = _js({"action": "echo", "technique": "huanglizeri", "tree": tree})["lines"]
    assert [line["zh"].strip()[:12] for line in lines][1].startswith("或 以下整组不成立")
    assert "冲:马" in lines[2]["zh"] and lines[3]["zh"].strip().startswith("或 ")


def _service(tmp_path: Path, js_client=None) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", runtime_root=tmp_path / "rt",
                        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    return HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=js_client or FakeJsClient())


@requires_node
@pytest.mark.parametrize("tool", TEN)
def test_every_zeri_result_echoes_its_conditions(tmp_path: Path, tool: str) -> None:
    payload = {**build_sample_payloads()[tool], "agent_confirmed_settings": True}
    if tool == "ziweizeri":
        payload["gender"] = 1
    result = _service(tmp_path).run_tool(tool, payload, save_result=False)
    assert result.ok, result.error
    echo = result.data["condition_echo"]
    assert echo["lines"] and all(line["zh"] and line["en"] for line in echo["lines"])
    assert "取反" in echo["negate_rule"]
    assert any(line.startswith("条件按此理解：") and " / Conditions as read: " in line for line in result.summary)


@requires_node
def test_chong_shengxiao_without_negate_excludes_days_that_clash(tmp_path: Path) -> None:
    """真引擎（本地黄历择吉 + 本地黄历）：「冲煞生肖 马」缺省判法 = 不冲马；加 negate = 只要冲马的日子。每个命中日的「冲」由黄历本身读出。"""
    service = _service(tmp_path, js_client=None)
    service.js_client = HorosaSkillService(service.settings).js_client  # 真 JS 引擎；Java / chart 服务不碰（黄历两步都是本地）
    base = {"date": "2026-12-01", "time": "12:00:00", "zone": "+08:00", "lat": "30n16", "lon": "120e09",
            "startDate": "2026-12-01", "endDate": "2026-12-31", "agent_confirmed_settings": True}
    leaf = {"kind": "leaf", "type": "chong_shengxiao", "params": {"values": ["马"]}}

    def hit_days(negate: bool) -> list[str]:
        tree = {"kind": "group", "joiner": "all", "children": [{**leaf, "negate": negate}]}
        result = service.run_tool("huanglizeri", {**base, "conditions": tree}, save_result=False)
        assert result.ok, result.error
        days: list[str] = []
        for row in result.data["intervals"]:  # 连续命中的日子合成一段：按段的起止日展开（日期算术，不是盘面计算）
            first, last = date.fromisoformat(str(row["start"])[:10]), date.fromisoformat(str(row["end"])[:10])
            days += [(first + timedelta(days=n)).isoformat() for n in range((last - first).days + 1)]
        return days

    def clashes_horse(day: str) -> bool:
        almanac = service.run_tool("huangli", {"date": day, "time": "12:00:00", "zone": "+08:00", "lat": "30n16", "lon": "120e09",
                                               "agent_confirmed_settings": True}, save_result=False)
        text = almanac.data["export_snapshot"]["export_text"]
        line = next(row for row in text.splitlines() if row.startswith("冲煞："))
        return line.startswith("冲煞：冲马")

    kept = hit_days(False)
    clashing = hit_days(True)
    assert kept and clashing and not set(kept) & set(clashing)
    assert len(set(kept) | set(clashing)) == 31, "两种读法互补，合起来是整个月"
    assert not any(clashes_horse(day) for day in kept[:6])
    assert all(clashes_horse(day) for day in clashing)
