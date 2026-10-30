"""星阙 v3.13.0 七政四余同步：行星时制式（planetaryHourMethod）进七政取盘与 [起盘信息]。

上游 components/guolao/main/params.js：guolaoPlanetaryHourMethod(fields)（:20-27，缺省 sunrise）+ fieldsToParams
（:158-162）只在非缺省（unequal / equal24）时透传 planetaryHourMethod —— 后端 perchart_parts/timing.py 据它取报时星；
main/snapshot.js:1150-1151 的「报时星太阳时」行随之标注制式（日出起算下另注「三档结果相同」）。
v3.11 期 skill 的七政既不校验也不透传这个键（BirthInput 上有声明，七政 runner 不读）→ 用户选了不等时，报时星仍按日出算。
"""

from __future__ import annotations

import pytest
from test_sync311_w3b_gim import _guolao_run, requires_node


def _setup_line(env) -> str:
    return next(line for line in env.data["snapshot_text"].splitlines() if line.startswith("报时星太阳时："))


@requires_node
def test_planetary_hour_method_default_is_not_sent_and_setup_line_says_sunrise(tmp_path) -> None:
    env, client = _guolao_run(tmp_path)
    assert env.ok, env.error
    assert "planetaryHourMethod" not in client.requests("/chart")[0]   # 缺省不发 = 零回归（上游同口径）
    assert _setup_line(env).endswith("（行星时制式：日出起算 · 等长时,此制式下太阳时三档结果相同）")


@requires_node
@pytest.mark.parametrize(("method", "label"), [("unequal", "昼夜不等时"), ("equal24", "廿四时等分")])
def test_non_default_planetary_hour_method_reaches_backend_and_snapshot(tmp_path, method: str, label: str) -> None:
    """负向对照：去掉 runner 里 `remote["planetaryHourMethod"] = …` 一行 → 请求断言红；从 _guolao_fields 的键表里
    去掉 planetaryHourMethod → [起盘信息] 仍写「日出起算」，快照断言红（两处都实跑过）。"""
    env, client = _guolao_run(tmp_path, {"planetaryHourMethod": method})
    assert env.ok, env.error
    assert client.requests("/chart")[0]["planetaryHourMethod"] == method
    assert _setup_line(env).endswith(f"（行星时制式：{label}）")


def test_invalid_planetary_hour_method_is_refused_before_any_backend_call(tmp_path) -> None:
    env, client = _guolao_run(tmp_path, {"planetaryHourMethod": "sundial"})
    assert not env.ok
    assert "planetaryHourMethod" in f"{env.error}"
    assert client.requests("/chart") == []


@requires_node
def test_gudu_minor_limit_is_the_explicit_ancient_limit_method(tmp_path) -> None:
    """挂载齿轮的「古度限度法」= 'gudu'（techniqueMountSettings.js:1372），上游 guolaoSnapshotDisplayFromFields 映成 ''
    （main/snapshot.js:1105）—— 与缺省逐字同盘；此前 skill 词表无 'gudu' → 报「取值无效」。"""
    default, _ = _guolao_run(tmp_path)
    gudu, _ = _guolao_run(tmp_path, {"guolaoMinorLimitType": "gudu"})
    assert gudu.ok, gudu.error
    assert gudu.data["snapshot_text"] == default.data["snapshot_text"]
    assert "行运法：古度限度法" in gudu.data["snapshot_text"]
