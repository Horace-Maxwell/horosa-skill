"""奇门附加层与 v3.15.0 新口径（寄宫「阳遁寄坤·阴遁寄艮」、值使「阳遁死门·阴遁生门」、暗干第六法、寄干 / 天禽 / 翻宫转宫推演 / 十二建星）。

上游 v3.15.0 新增的盘面附加层只在开关开时进快照（缺省关，盘面与快照逐字节同旧）。skill 透传 options 给 vendored calcDunJia，
这里钉三件事：① 开了真的改正文（真 JS 引擎）；② 词表与 vendored 上游表逐项相同；③ 认不出的值报错，不像上游那样静默回落。
负向对照：词表常量少一个 v3.15 新值（如去掉 "tianpan_zhuan"）→ 对拍红；去掉 _qimen_validate_vocab → 坏值用例红。
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from node_esm import run_node_esm
from test_sync311_sanshi import BASE_QM, _fake_service

from horosa_skill.config import Settings
from horosa_skill.engine.js_client import HorosaJsEngineClient
from horosa_skill.service import options_cn as O

CORE_JS = Path(__file__).resolve().parents[1] / "horosa-core-js"


def _real_service(tmp_path: Path):
    js = HorosaJsEngineClient(Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", db_path=tmp_path / "m.db",
                                       output_dir=tmp_path / "o", runtime_root=tmp_path / "r"))
    return _fake_service(tmp_path, js=js)


def test_vocab_equals_the_vendored_upstream_tables() -> None:
    script = ("const [o, v] = await Promise.all([import(process.argv[1]), import(process.argv[2])]);"
              "const vals = (xs) => xs.map((x) => x.value);"
              "process.stdout.write(JSON.stringify({ jigong: vals(o.JIGONG_MODE_OPTIONS), zhishi: vals(o.ZHISHI_OPTIONS), angan: vals(o.ANGAN_MODE_OPTIONS),"
              " view: vals(v.TUIYAN_VIEW_OPTIONS), gong: vals(v.TUIYAN_GONG_OPTIONS) }));")
    vendored = json.loads(run_node_esm(script, CORE_JS / "src" / "vendor" / "dunjia" / "calc" / "options.js",
                                       CORE_JS / "src" / "vendor" / "dunjia" / "calc" / "overlay.js"))
    assert tuple(vendored["jigong"]) == O._QIMEN_JIGONG_MODES and tuple(vendored["zhishi"]) == O._QIMEN_ZHISHI_TYPES
    assert tuple(vendored["angan"]) == O._QIMEN_ANGAN_MODES and tuple(vendored["view"]) == O._QIMEN_TUIYAN_VIEWS
    assert tuple(vendored["gong"]) == O._QIMEN_TUIYAN_GONGS
    assert {"yang_kun_yin_gen", "tianpan_zhuan"} <= set(O._QIMEN_JIGONG_MODES + O._QIMEN_ANGAN_MODES) and 3 in O._QIMEN_ZHISHI_TYPES


def test_overlays_reach_the_snapshot_only_when_switched_on(tmp_path) -> None:
    svc = _real_service(tmp_path)
    base = {**BASE_QM, "agent_confirmed_settings": True}
    off = svc.run_tool("qimen", {**base, "options": {"zhiShiType": 3}}, save_result=False)
    on = svc.run_tool("qimen", {**base, "options": {"zhiShiType": 3, "showJiGan": True, "showTianQin": "1", "tuiYanView": "fan",
                                                     "showJianChu": 1}}, save_result=False)
    assert off.ok and on.ok, (off.error, on.error)
    added = [line for line in on.data["snapshot_text"].split("\n") if line not in off.data["snapshot_text"].split("\n")]
    for head in ("寄干：", "天禽：", "推演 · 翻宫：", "十二建星："):
        assert any(line.startswith(head) for line in added), (head, added)
    assert not any(line.startswith(("寄干：", "天禽：", "推演 · ", "十二建星：")) for line in off.data["snapshot_text"].split("\n"))


@pytest.mark.parametrize(("key", "bad"), [("jiGongMode", "yinyang"), ("zhiShiType", 4), ("anGanMode", "spin"), ("tuiYanView", "both"),
                                          ("tuiYanGong", "5"), ("showJianChu", "maybe")])
def test_unknown_values_are_refused_not_silently_defaulted(key: str, bad) -> None:
    svc = _fake_service(Path(tempfile.mkdtemp()))
    env = svc.run_tool("qimen", {**BASE_QM, "options": {key: bad}, "agent_confirmed_settings": True}, save_result=False)
    assert env.ok is False and env.error.code == "tool.qimen_invalid_option" and env.error.details["field"] == key


def test_sanshiunited_overview_carries_the_qimen_layer_overlays(tmp_path) -> None:
    """三式合一：上游一份页面 options 同管奇门层与快照；skill 的奇门层开关在 qimen_options 里，十二建星行要随盘回填进【概览】。

    负向对照：删掉 sanshiUnited.js 的 `if (dunjia && dunjia.jianChu) options.showJianChu = true;` → 十二建星断言红。
    """
    from test_sync311_sanshi import _replay_service, _run, _ss_section

    svc, _ = _replay_service(tmp_path)
    off = _run(svc, "sanshi_default")
    on = _run(svc, "sanshi_default", qimen_options={"showJiGan": True, "tuiYanView": "zhuan", "showJianChu": True})
    assert off.ok and on.ok, (off.error, on.error)
    off_view = _ss_section(off.data["snapshot_text"], "概览").split("\n")
    on_view = _ss_section(on.data["snapshot_text"], "概览").split("\n")
    added = [line for line in on_view if line not in off_view]
    for head in ("寄干：", "推演 · 转宫：", "十二建星："):
        assert any(line.startswith(head) for line in added), (head, added)
    assert not any(line.startswith(("寄干：", "推演 · ", "十二建星：")) for line in off_view)
