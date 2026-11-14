"""择日条件树的结构性错误说清楚（审计 S-23）：扁平数组以前报「未知条件类型:undefined」、参数键写成 value / shengxiao 报「至少选择一项」、
fix_fields.example 是 null。现在点名出错的叶子（未知条件类给「是不是」，未知参数列出这个条件的参数），并给这个工具一棵最小的合法条件树。

负向对照（实跑过）：zeriScan.js 不先查 structural → 第三条红；exampleTree 恒返回空组 → 第一条红。
"""
from __future__ import annotations

import json
from pathlib import Path

from node_esm import run_node_esm
from test_fix314_zeri_values import CORE_JS, TOOLS, _WINDOW, _service, _tree, requires_node


@requires_node
def test_every_registry_has_a_minimal_valid_example_and_defaults_are_not_flagged() -> None:
    script = """
const { ZERI_REGISTRIES } = await import(process.argv[1]);
const { checkConditionValues, exampleTree } = await import(process.argv[2]);
const problems = [];
for (const [tech, reg] of Object.entries(ZERI_REGISTRIES)) {
  const ex = exampleTree(reg);
  if (!ex.children.length) problems.push(`${tech}: no example`);
  const r = checkConditionValues(reg, ex);
  if (r.structural.length || r.invalid.length) problems.push(`${tech}: example not clean`);
  for (const [type, spec] of Object.entries(reg)) {
    const leaf = { kind: 'group', joiner: 'all', children: [{ type, params: { ...(spec.defaults || {}) } }] };
    if (checkConditionValues(reg, leaf).structural.length) problems.push(`${tech}.${type}: defaults flagged`);
  }
}
console.log(JSON.stringify(problems));
"""
    assert json.loads(run_node_esm(script, TOOLS / "zeriConditions.js", TOOLS / "zeriParamCheck.js", cwd=CORE_JS)) == []


@requires_node
def test_structural_mistakes_name_the_leaf() -> None:
    script = """
const { ZERI_REGISTRIES } = await import(process.argv[1]);
const { checkConditionValues } = await import(process.argv[2]);
const reg = ZERI_REGISTRIES.huanglizeri;
const flat = checkConditionValues(reg, [{ type: 'yi_has', params: { values: ['嫁娶'] } }]);
const wrong = checkConditionValues(reg, { kind: 'group', joiner: 'all', children: [
  { type: 'shengxiao', params: { value: '鼠' } }, { type: 'yi_has', params: { value: '嫁娶' } }, { params: {} }] });
console.log(JSON.stringify({ flat: flat.structural.map((r) => r.problem), example: !!flat.example,
  wrong: wrong.structural.map((r) => [r.problem, r.path, (r.did_you_mean || []).map((c) => c.type), r.given]) }));
"""
    out = json.loads(run_node_esm(script, TOOLS / "zeriConditions.js", TOOLS / "zeriParamCheck.js", cwd=CORE_JS))
    assert out["flat"] == ["flat_array"] and out["example"] is True
    problems = {row[0]: row for row in out["wrong"]}
    assert "chong_shengxiao" in problems["unknown_type"][2]
    assert problems["unknown_params"][1] == "conditions.children[1]" and problems["unknown_params"][3] == ["value"]
    assert problems["missing_type"][1] == "conditions.children[2]"


@requires_node
def test_the_tool_error_carries_the_example(tmp_path: Path) -> None:
    result = _service(tmp_path).run_tool("huanglizeri", {**_WINDOW, "conditions": [{"type": "yi_has", "params": {"values": ["嫁娶"]}}]},
                                         save_result=False)
    assert result.ok is False and result.error.code == "tool.huanglizeri_invalid_conditions"
    assert result.error.details["structural"][0]["problem"] == "flat_array"
    example = json.dumps(result.error.details, ensure_ascii=False)
    assert '"joiner": "all"' in example and "undefined" not in result.error.message
