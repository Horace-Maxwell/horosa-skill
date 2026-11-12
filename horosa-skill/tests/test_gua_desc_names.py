"""卦义查询认卦名（v0.50.0 深审余项）。

症状（复现于共享引擎）：gua_desc 把认不出的名字原样发给 /gua/desc——`不存在卦` 在 [卦象] 印「不存在卦：无」，`乾` / `水雷屯` /
`既濟` 什么都不印，ok=true。后端只认六位码。现在：名字按六十四卦表（vendored 上游 GuaConst.Gua64，六爻 guaByName 同表同简名
规则）读成码——全名、简名、繁体、带「卦」字都认；认不出 → tool.invalid_option，options 是最接近的卦名，details.accepted 是全表。

表是生成件（src/horosa_skill/data/gua64_names.json）：本文件在 node 在场时与 JS 表逐行对拍；重生成 `uv run python tests/test_gua_desc_names.py --record`。
负向对照（实跑过）：GuaDescInput 的校验器去掉 → 拒绝用例与卦名用例红；表里改一个简名 → 对拍用例红。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "src" / "horosa_skill" / "data" / "gua64_names.json"
_NODE_DUMP = (
    "import('./horosa-core-js/src/vendor/gua/GuaConst.js').then(m => process.stdout.write(JSON.stringify("
    "m.Gua64.map(g => [g.value.join(''), g.name, g.name.includes('为') ? g.name[0] : g.name.slice(2)]))))"
)


def _js_rows() -> list[list[str]]:
    out = subprocess.run(["node", "-e", _NODE_DUMP], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True, timeout=60)
    return json.loads(out.stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="[host] node not on PATH")
def test_table_is_the_vendored_gua64() -> None:
    assert json.loads(TABLE.read_text(encoding="utf-8"))["rows"] == _js_rows()


@pytest.mark.parametrize("name, code", [
    ("111111", "111111"), ("乾", "111111"), ("乾为天", "111111"), ("乾卦", "111111"), ("坤为地", "000000"),
    ("水雷屯", "100010"), ("屯", "100010"), ("既濟", "101010"), ("水火既济", "101010"), ("火天大有", "111101"),
])
def test_names_read_as_codes(name: str, code: str) -> None:
    from horosa_skill.engine.registry import TOOL_DEFINITIONS

    model = TOOL_DEFINITIONS["gua_desc"].input_model
    assert model.model_validate({"name": [name]}).name == [code]


@pytest.mark.parametrize("bad", ["不存在卦", "xyz", "1111", "乾为地"])
def test_unknown_names_are_refused_with_close_matches(bad: str) -> None:
    from horosa_skill.engine.registry import TOOL_DEFINITIONS
    from horosa_skill.errors import ToolValidationError

    with pytest.raises(ToolValidationError) as caught:
        TOOL_DEFINITIONS["gua_desc"].input_model.model_validate({"name": ["乾", bad]})
    error = caught.value
    assert error.code == "tool.invalid_option"
    assert [item["field"] for item in error.details["fields"]] == ["name[1]"]
    assert len(error.details["accepted"]) == 64
    if bad == "乾为地":  # 近名给候选
        assert error.details["fields"][0]["options"], error.details["fields"][0]


if __name__ == "__main__" and "--record" in sys.argv:
    TABLE.write_text(json.dumps({**json.loads(TABLE.read_text(encoding="utf-8")), "rows": _js_rows()}, ensure_ascii=False, indent=1) + "\n",
                     encoding="utf-8")
    print(f"recorded {TABLE}")
