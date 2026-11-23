"""上游 v3.14.0 · western 桶里的手抄移植（合盘容许度、变换盘宫制标注、古典键说明）。

- 合盘容许度随整体倍率（发布说明「合盘容许度(结果会变)」）：上游 `chartOrbOverrides`（utils/classicalChartGlobals.js）把
  「设置 → 容许度设置」的 orbs / orbScale 带进合盘请求与「关系量化」请求；后端 `modern/chartcomp.cross_orb` = 1° × 整体倍率。
  修前：skill 的 orbScale 只进 /modern/relative（靠 extra 透传，还被报成「不是本技法的参数」），/astroextra/relative 不带——
  比较盘随倍率变、关系量化的分数与连接表恒按 1°。
- 变换盘宫制标注（wholeSignRulers.js derivedModeOf / derivedWholeSignLabelOf / resolveHouseSystem 的两种新标记）。
"""

from __future__ import annotations

from skips import upstream_source  # 上游拆文件后读「门面 + 子模块」全集（v3.15.0）
import json
import re
import shutil
from pathlib import Path

import pytest
from fakes import CaptureClient, FakeClient, FakeJsClient
from node_esm import run_node_esm
from skips import needs_upstream, upstream_path
from test_local_js_tools import make_service, requires_chart

from horosa_skill import astro_rulers
from horosa_skill.config import Settings
from horosa_skill.errors import ToolValidationError
from horosa_skill.memory.store import MemoryStore
from horosa_skill.schemas.tools import BirthInput, RelativeInput
from horosa_skill.schemas.tools.base import advertise_hidden_fields
from horosa_skill.service import HorosaSkillService
from horosa_skill.service.text.chart_family import _chart_orb_overrides
from horosa_skill.western_options_doc import western_options_doc

CORE_JS = Path(__file__).resolve().parents[1] / "horosa-core-js"
requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="[host] node not installed")
PAIR = {
    "inner": {"date": "1990-05-17", "time": "14:30:00", "zone": "+08:00", "lat": "31n14", "lon": "121e28"},
    "outer": {"date": "1992-08-21", "time": "06:10:00", "zone": "+08:00", "lat": "39n54", "lon": "116e23"},
    "defaults_accepted": True,
}


def _service(tmp_path, client=None) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", runtime_root=tmp_path / "runtime", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    return HorosaSkillService(settings, client=client or FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())


# ─────────────────────────── 合盘容许度 ───────────────────────────
@requires_node
def test_chart_orb_overrides_port_equals_the_vendored_upstream_function() -> None:
    """_chart_orb_overrides == vendored classicalChartGlobals.js chartOrbOverridesFromPlain（仅非默认才下发）。
    负向对照：把 Python 里 `abs(scale - 1) > 1e-9` 的判断去掉（倍率 1 也发）→ 红（实跑过）。"""
    cases = [
        {}, {"orbScale": 1}, {"orbScale": 1.0}, {"orbScale": "1"}, {"orbScale": 2}, {"orbScale": "0.5"}, {"orbScale": 0}, {"orbScale": -1},
        {"orbScale": "abc"}, {"orbScale": None}, {"orbScale": ""}, {"orbs": {}}, {"orbs": {"Sun": 9}}, {"orbs": []}, {"orbs": "x"},
        {"orbs": {"Sun": 9, "Moon": 7}, "orbScale": 1.5},
    ]
    script = (
        "const m = await import(process.argv[1]); const cases = JSON.parse(process.argv[2]);"
        "process.stdout.write(JSON.stringify(cases.map((c) => m.chartOrbOverridesFromPlain(c))));"
    )
    upstream = json.loads(run_node_esm(script, CORE_JS / "src" / "vendor" / "utils" / "classicalChartGlobals.js", json.dumps(cases)))
    for case, expected in zip(cases, upstream):
        assert _chart_orb_overrides(case) == expected, case


def test_relative_orb_settings_reach_both_requests(tmp_path) -> None:
    """orbs / orbScale 是合盘工具的入参（声明而不广告）：进 /modern/relative，也进「关系量化」的 /astroextra/relative；
    缺省 / 倍率 1 时两个请求体都不带（上游「默认态请求体不变」）。技法卡回显倍率。
    负向对照：把 enrich._attach_relative_score 里的 `**_chart_orb_overrides(input_normalized)` 删掉 → 关系量化请求体断言红（实跑过）。"""
    assert {"orbs", "orbScale"} <= set(RelativeInput.model_fields) and {"orbs", "orbScale"} <= advertise_hidden_fields(RelativeInput)
    assert {"orbs", "orbScale"} <= set(western_options_doc("relative"))
    client = CaptureClient()
    result = _service(tmp_path, client=client).run_tool("relative", {**PAIR, "orbScale": 2, "orbs": {"Sun": 9}}, save_result=False)
    assert result.ok, result.error
    sent = {endpoint: payload for endpoint, payload in client.calls}
    for endpoint in ("/modern/relative", "/astroextra/relative"):
        assert sent[endpoint]["orbScale"] == 2 and sent[endpoint]["orbs"] == {"Sun": 9}, endpoint
    assert not any("不是本技法的参数" in note for note in result.warnings), result.warnings
    assert result.data["technique_card"]["settings"]["orbScale"]["value"] == 2

    for neutral in ({}, {"orbScale": 1}):
        plain = CaptureClient()
        assert _service(tmp_path / f"n{len(neutral)}", client=plain).run_tool("relative", {**PAIR, **neutral}, save_result=False).ok
        score_body = dict(plain.calls)["/astroextra/relative"]
        assert "orbScale" not in score_body and "orbs" not in score_body


@pytest.mark.parametrize("value", [0, -2, float("inf")])
def test_relative_refuses_an_orb_scale_the_backend_would_silently_ignore(tmp_path, value) -> None:
    """后端 cross_orb 对 ≤ 0 / 非有限的倍率静默按 1° 算（modern/chartcomp.py）——入口就拒。"""
    with pytest.raises(ToolValidationError):
        _service(tmp_path).run_tool("relative", {**PAIR, "orbScale": value}, save_result=False)


@requires_chart
def test_live_relative_score_follows_the_orb_scale(tmp_path) -> None:
    """共享 v3.14.0 引擎：倍率 2 时比较盘回显 crossOrb=2、关系量化的连接里出现误差 1°–2° 的相位（倍率 1 时全部 ≤ 1°），分数随之变。
    期望值的依据 = 上游定义「跨盘接触容许度 = 1° × 整体倍率」（modern/chartcomp.py CROSS_ASPECT_ORB / cross_orb），不是抄当前输出。"""
    service = make_service(tmp_path)
    base = service.run_tool("relative", PAIR, save_result=False)
    wide = service.run_tool("relative", {**PAIR, "orbScale": 2}, save_result=False)
    assert base.ok and wide.ok, (base.error, wide.error)
    assert "crossOrb" not in base.data and wide.data["crossOrb"] == 2.0

    def orbs_of(result) -> list[float]:
        score = result.data["_relativeScore"]
        return [float(item["orb"]) for item in [*score["highlights"], *score["challenges"]]]

    assert orbs_of(base) and max(orbs_of(base)) <= 1.0 + 1e-9
    assert max(orbs_of(wide)) <= 2.0 + 1e-9 and any(orb > 1.0 for orb in orbs_of(wide))
    assert base.data["_relativeScore"]["score"] != wide.data["_relativeScore"]["score"]
    assert len(wide.data["snapshot_text"]) > len(base.data["snapshot_text"])   # 比较盘跨盘相位 / 映点 / 中点表随之变多


@needs_upstream("Horosa-Web/astropy/astrostudy/modern/chartcomp.py", "Horosa-Web/astropy/astrostudy/astroextra_parts/relative.py",
                "Horosa-Web/astropy/websrv/webmodernsrv.py")
def test_backend_reads_the_orb_keys_where_the_skill_sends_them() -> None:
    comp = upstream_source(upstream_path("Horosa-Web/astropy/astrostudy/modern/chartcomp.py"))
    assert "CROSS_ASPECT_ORB = 1.0" in comp and "d.get('orbScale')" in comp
    score = upstream_source(upstream_path("Horosa-Web/astropy/astrostudy/astroextra_parts/relative.py"))
    assert "for key in ('orbs', 'orbScale'):" in score
    modern = upstream_source(upstream_path("Horosa-Web/astropy/websrv/webmodernsrv.py"))
    assert "'orbs', 'orbScale'):" in modern


# ─────────────────────────── 变换盘宫制标注 ───────────────────────────
def test_transform_chart_house_modes_follow_upstream_jest() -> None:
    """上游 jest transformCharts.test.js「变换盘的等宫不折叠宫主表」的原样用例 + 基础宫制那一档。
    负向对照：把 astro_rulers._TRANSFORM_HOUSE_MODES 里的两个标记去掉 → 标签回空、isAscWholeSign 回 True，本用例红（实跑过）。"""
    chart = {"chart": {"hsys": "Whole Sign", "houses": [{"id": "House1", "hsysDerived": "equalFromTransform"}]}, "params": {"hsys": 0}}
    resolved = astro_rulers.resolve_house_system(chart, None)
    assert resolved["isAscWholeSign"] is False and resolved["label"] == "等宫(变换后)"
    assert astro_rulers.derived_whole_sign_label_of({"houses": chart["chart"]["houses"]}) == "等宫(变换后)"
    base = {"chart": {"hsys": "Whole Sign", "houses": [{"id": "House1", "hsysDerived": "baseFromTransform"}]}, "params": {"hsys": 0}}
    assert astro_rulers.resolve_house_system(base, None) == {"num": "0", "label": "基础宫制(变换后)", "isAscWholeSign": False}
    # 既有两档不动：十三分等派生盘仍标「整宫(变换后上升)」、组合盘仍折叠。
    derived = {"chart": {"hsys": "Alcabitus", "houses": [{"id": "House1", "hsysDerived": "wholeFromAsc"}]}, "params": {"hsys": 1}}
    assert astro_rulers.resolve_house_system(derived, None)["label"] == "整宫(变换后上升)"
    composite = {"chart": {"hsys": "Alcabitus", "houses": [{"id": "House1", "hsysDerived": "compositeWholeFromAsc"}]}, "params": {"hsys": 1}}
    assert astro_rulers.resolve_house_system(composite, None) == {"num": "1", "label": "整宫(组合上升)", "isAscWholeSign": True}


@needs_upstream("Horosa-Web/astrostudyui/src/utils/wholeSignRulers.js", "Horosa-Web/astropy/astrostudy/transform_charts.py")
def test_transform_house_mode_strings_equal_upstream_source() -> None:
    js = upstream_source(upstream_path("Horosa-Web/astrostudyui/src/utils/wholeSignRulers.js"))
    labels = dict(re.findall(r"export const (\w+_LABEL) = '([^']+)';", js))
    assert labels == {
        "DERIVED_WHOLE_SIGN_LABEL": astro_rulers.DERIVED_WHOLE_SIGN_LABEL, "COMPOSITE_WHOLE_SIGN_LABEL": astro_rulers.COMPOSITE_WHOLE_SIGN_LABEL,
        "TRANSFORM_EQUAL_LABEL": astro_rulers.TRANSFORM_EQUAL_LABEL, "TRANSFORM_BASE_LABEL": astro_rulers.TRANSFORM_BASE_LABEL,
    }
    modes = re.search(r"if\(m === '([^)]*)'\)\{\s*return m;", js).group(0)
    assert sorted(re.findall(r"'(\w+)'", modes)) == sorted((astro_rulers._DERIVED_HOUSE_MODE, astro_rulers._COMPOSITE_HOUSE_MODE, *astro_rulers._TRANSFORM_HOUSE_MODES))
    backend = upstream_source(upstream_path("Horosa-Web/astropy/astrostudy/transform_charts.py"))
    assert f"EQUAL_HOUSE_MODE = '{astro_rulers._TRANSFORM_EQUAL_HOUSE_MODE}'" in backend
    assert f"BASE_HOUSE_MODE = '{astro_rulers._TRANSFORM_BASE_HOUSE_MODE}'" in backend


# ─────────────────────────── 古典键说明 ───────────────────────────
@needs_upstream("Horosa-Web/astrostudyui/src/utils/classicalParamSpec.js")
def test_topocentric_moon_note_tracks_the_upstream_hint() -> None:
    """classicalParamSpec.js v3.14.0 给 topocentricMoon 的提示补了「印占各盘恒用地心月」——skill 的字段说明是手抄，跟上。"""
    spec = upstream_source(upstream_path("Horosa-Web/astrostudyui/src/utils/classicalParamSpec.js"))
    hint = re.search(r"key: 'topocentricMoon'.*?hint: '([^']+)'", spec, flags=re.S).group(1)
    assert hint == "影响月亮黄经 ≤1° · 福点随动 · 印占各盘恒用地心月"
    description = str(BirthInput.model_fields["topocentricMoon"].description)
    for part in ("影响月亮黄经 ≤1°", "福点随动", "印占各盘恒用地心月"):
        assert part in description
