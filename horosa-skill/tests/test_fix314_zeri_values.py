"""择日条件的取值预检（审计 S-01，P0）。

上游的条件值域靠页面下拉框兜着，判定函数对界外值落缺省分支：太乙择日写「阴遁」（选项 value 是「阴」）拿到阳遁的 97 个时辰、
黄历「宜」写「搬家」零命中且不报错。`horosa-core-js/src/tools/zeriParamCheck.js` 只读注册表：value 照用；唯一等于某个标签 → 读成 value
并回说明；其余按字段拒绝、列可选值（黄历用事另给「是不是指」）。

负向对照（实跑过）：zeriScan.js 里的 `checkConditionValues` 那一段删掉 → 第一条（全注册表扫）与黄历「搬家」两条红。
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fakes import FakeClient
from node_esm import run_node_esm
from test_local_js_tools import requires_chart

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="[host] node not installed")
CORE_JS = Path(__file__).resolve().parents[1] / "horosa-core-js"
TOOLS = CORE_JS / "src" / "tools"


@requires_node
def test_every_enumerated_field_accepts_values_maps_unique_labels_and_refuses_junk() -> None:
    """九张注册表的每个 select / multiselect 字段：value 原样过、唯一标签读成 value、乱串被拒——一个都不能落到判定函数的缺省分支。"""
    script = """
const { ZERI_REGISTRIES } = await import(process.argv[1]);
const { checkConditionValues } = await import(process.argv[2]);
const out = { fields: 0, label_cases: 0, problems: [] };
for (const [tech, reg] of Object.entries(ZERI_REGISTRIES)) {
  for (const [type, spec] of Object.entries(reg)) {
    for (const f of spec.fields || []) {
      if ((f.kind !== 'select' && f.kind !== 'multiselect') || !Array.isArray(f.options) || !f.options.length) continue;
      if (typeof f.showIf === 'function' && !f.showIf(spec.defaults || {})) continue;   // 缺省参数下页面不显示这一项
      out.fields += 1;
      const opts = f.options.map((o) => (o && typeof o === 'object' ? o : { value: o, label: o }));
      const many = f.kind === 'multiselect';
      const leaf = (v) => ({ kind: 'group', joiner: 'all', children: [{ kind: 'leaf', type, params: { ...(spec.defaults || {}), [f.key]: many ? [v] : v } }] });
      const first = opts[0];
      let r = checkConditionValues(reg, leaf(first.value));
      if (r.invalid.length) out.problems.push(`${tech}.${type}.${f.key}: value ${first.value} refused`);
      const uniq = opts.find((o) => `${o.label}` !== `${o.value}` && opts.filter((x) => `${x.label}`.replace(/\\s+/g, '') === `${o.label}`.replace(/\\s+/g, '')).length === 1
        && !opts.some((x) => `${x.value}` === `${o.label}`));
      if (uniq) {
        out.label_cases += 1;
        r = checkConditionValues(reg, leaf(uniq.label));
        const got = r.tree.children[0].params[f.key];
        if (r.invalid.length || `${many ? got[0] : got}` !== `${uniq.value}`) out.problems.push(`${tech}.${type}.${f.key}: label ${uniq.label} not mapped to ${uniq.value}`);
      }
      r = checkConditionValues(reg, leaf('__不存在的值__'));
      if (!r.invalid.length) out.problems.push(`${tech}.${type}.${f.key}: junk accepted`);
    }
  }
}
console.log(JSON.stringify(out));
"""
    out = json.loads(run_node_esm(script, TOOLS / "zeriConditions.js", TOOLS / "zeriParamCheck.js", cwd=CORE_JS))
    assert out["problems"] == []
    assert out["fields"] > 100 and out["label_cases"] > 20, out


def _service(tmp_path: Path) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", db_path=tmp_path / "m.db", output_dir=tmp_path / "runs")
    return HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings))


def _tree(*leaves: dict) -> dict:
    return {"kind": "group", "joiner": "all", "children": list(leaves)}


_WINDOW = {"date": "2026-12-01", "time": "00:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "startDate": "2026-12-01",
           "endDate": "2026-12-31", "defaults_accepted": True}


@requires_node
def test_everyday_word_for_a_huangli_term_is_refused_with_a_suggestion(tmp_path: Path) -> None:
    result = _service(tmp_path).run_tool("huanglizeri", {**_WINDOW, "conditions": _tree(
        {"kind": "leaf", "type": "yi_has", "params": {"values": ["搬家"]}})}, save_result=False)
    assert result.ok is False and result.error.code == "tool.huanglizeri_invalid_conditions"
    row = result.error.details["invalid"][0]
    assert row["given"] == ["搬家"] and row["did_you_mean"] == ["移徙", "入宅"] and len(row["allowed"]) > 50
    assert "是不是指：移徙 / 入宅" in result.error.message


@requires_node
def test_condition_echo_reads_the_normalized_value() -> None:
    script = """
const m = await import(process.argv[1]);
const r = await m.runZeriConditions({ action: 'echo', technique: 'taiyizeri', tree: { kind: 'group', joiner: 'all', children: [
  { kind: 'leaf', type: 'yinyang_ju', params: { value: '阴遁' } }] } });
console.log(JSON.stringify(r.data.lines));
"""
    lines = json.loads(run_node_esm(script, TOOLS / "zeriConditions.js", cwd=CORE_JS))
    assert lines[0]["zh"] == "阴阳遁：阴遁"   # 修前回显成「阴遁遁」


@requires_chart
def test_live_label_spelling_reads_as_the_same_condition_as_the_value(tmp_path: Path) -> None:
    """「阴遁」与「阴」同一批命中（此前「阴遁」拿到的是阳遁的 97 个时辰）；零命中时摘要第一行直说。"""
    from horosa_skill.config import Settings as S

    svc = HorosaSkillService(S.from_env().model_copy(update={"db_path": tmp_path / "m.db", "output_dir": tmp_path / "runs"}))
    common = {"place": "上海", "defaults_accepted": True, "date": "2028-04-01", "time": "00:00", "startDate": "2028-04-01", "endDate": "2028-04-08"}
    by_label = svc.run_tool("taiyizeri", {**common, "conditions": _tree({"kind": "leaf", "type": "yinyang_ju", "params": {"value": "阴遁"}})}, save_result=False)
    by_value = svc.run_tool("taiyizeri", {**common, "conditions": _tree({"kind": "leaf", "type": "yinyang_ju", "params": {"value": "阴"}})}, save_result=False)
    assert by_label.ok and by_value.ok
    assert by_label.data["intervals"] == by_value.data["intervals"]
    assert any("阴遁 → 阴" in w for w in by_label.warnings)
    if by_label.data["hit_count"] == 0:
        assert by_label.summary[0].startswith("搜索窗内 0 个命中")
