"""上游 v3.14.0（Horosa-Public @ e55c3a66）占星地图两层：日食路径 + 气候带 / 纬圈。

- `eclipse`（off / prenatal / postnatal）+ `eclipseFilter`（any / central）：后端重算（ACGraph._eclipse → acg/eclipse_path.py），
  开了才下发；响应的 `eclipse` 由 vendored 上游 `eclipseSummaryLines`（utils/acgLayers.js）写成 [占星地图] 的「◆ 日食路径」。
- `climes`（off / klimata / parallels）+ `climesObliquity`（date / ptolemy）：快照图层，纬度由 `climesSummaryLines` 按最长昼推。

期望值的独立来源：
- 上游 `astropy/tests/test_eclipse_path.py`：2017-08-21 日全食食甚 18:25 UT、36°58′N 87°40′W、食带宽 105–125 km；
  出生地时区钟面（−05:00 → 13:25；+0800 的 1990-03-01 盘 → 1990/01/27 03:30）；1975-02-11 之前最近一次是偏食、
  只找中心食 → 1974-06-20；2024-01-01 之后最近一次中心食 → 2024-04-08。
- 气候带：tan φ = −cos(7.5° × 最长昼) / tan ε（acgLayers.js 头注的公式）在测试里独立重算；托勒密值 23°51′20″；
  最长昼 24 时 = 极圈 90° − ε。
"""

from __future__ import annotations

from skips import upstream_source  # 上游拆文件后读「门面 + 子模块」全集（v3.15.0）
import copy
import json
import math
import re
from pathlib import Path

import pytest
from fakes import FakeClient
from skips import needs_upstream, upstream_path

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.schemas.tools import ACGInput
from horosa_skill.schemas.tools.base import advertise_hidden_fields
from horosa_skill.service import HorosaSkillService
from horosa_skill.western_vocab import ACG_LAYER_VOCABULARIES

PKG_ROOT = Path(__file__).resolve().parents[1]
VENDOR = PKG_ROOT / "horosa-core-js" / "src" / "vendor"
FIX = json.loads((Path(__file__).parent / "fixtures" / "sync314_mundane_live.json").read_text(encoding="utf-8"))["acg"]
BIRTH = {"date": "2017-08-22", "time": "00:00:00", "zone": "-05:00", "lat": "36n58", "lon": "87w40"}
PTOLEMY = 23 + 51 / 60 + 20 / 3600


class AcgClient(FakeClient):
    def __init__(self, *, eclipse="fixture") -> None:
        super().__init__()
        self.calls: list[tuple[str, dict]] = []
        self.eclipse = eclipse

    def call(self, endpoint: str, payload: dict) -> dict:
        endpoint = "/chart" if endpoint == "/" else endpoint
        self.calls.append((endpoint, copy.deepcopy(payload)))
        out = super().call(endpoint, payload)
        if endpoint == "/location/acg" and self.eclipse != "fixture":
            out["eclipse"] = self.eclipse(payload) if callable(self.eclipse) else copy.deepcopy(self.eclipse)
        return out

    def requests(self, endpoint: str) -> list[dict]:
        return [p for e, p in self.calls if e == endpoint]


def _service(tmp_path, client) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", runtime_root=tmp_path / "runtime",
                        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    return HorosaSkillService(settings, client=client, store=MemoryStore(settings))  # 真 JS 引擎


def _map(text: str) -> list[str]:
    lines = text.split("\n")
    body = []
    for line in lines[lines.index("[占星地图]") + 1:]:
        if re.fullmatch(r"\[.+\]", line):
            break
        body.append(line)
    return [line for line in body if line.strip()]


def _block(body: list[str], head: str) -> list[str] | None:
    start = next((i for i, line in enumerate(body) if line.startswith(head)), None)
    if start is None:
        return None
    out = [body[start]]
    for line in body[start + 1:]:
        if line.startswith("◆ "):
            break
        out.append(line)
    return out


def _latitude(hours: float, obliquity: float) -> float:
    return math.degrees(math.atan(-math.cos(math.radians(7.5 * hours)) / math.tan(math.radians(obliquity))))


def _clean(env) -> None:
    exp = env.data["export_snapshot"]
    assert exp["missing_selected_sections"] == [] and exp["unknown_detected_sections"] == [], exp


# ────────────────────────────── 契约锚点 ──────────────────────────────


def test_layer_vocabularies_equal_the_vendored_upstream_constants() -> None:
    text = (VENDOR / "utils" / "acgLayers.js").read_text(encoding="utf-8")
    for field, const in (("eclipse", "ECLIPSE_MODES"), ("eclipseFilter", "ECLIPSE_FILTERS"), ("climes", "CLIMES_MODES"), ("climesObliquity", "CLIMES_OBLIQUITY")):
        m = re.search(rf"export const {const} = \[([^\]]*)\];", text)
        assert m, const
        assert [a["value"] for a in ACG_LAYER_VOCABULARIES[field].accepted] == re.findall(r"'(\w+)'", m.group(1)), field
        assert field in ACGInput.model_fields and field in advertise_hidden_fields(ACGInput)
        assert ACGInput.model_fields[field].description
    # 缺省 = 上游 ACG_PAGE_SETTINGS 的 def（off / any / off / date）= 各表首项。
    assert [next(iter(v.labels)) for v in ACG_LAYER_VOCABULARIES.values()] == ["off", "any", "off", "date"]
    assert f"{PTOLEMY:.4f}" == "23.8556" and "export const PTOLEMY_OBLIQUITY = 23 + 51 / 60 + 20 / 3600;" in text


@needs_upstream("Horosa-Web/astropy/astrostudy/acg/eclipse_path.py", "Horosa-Web/astrostudyui/src/components/acg/AstroAcg.js")
def test_layer_vocabularies_track_the_backend_and_page_settings() -> None:
    backend = upstream_source(upstream_path("Horosa-Web/astropy/astrostudy/acg/eclipse_path.py"))
    assert "WHICH = ('prenatal', 'postnatal')" in backend and "FILTERS = ('any', 'central')" in backend
    page = upstream_source(upstream_path("Horosa-Web/astrostudyui/src/components/acg/AstroAcg.js"))
    for key, default, const in (("eclipse", "off", "ECLIPSE_MODES"), ("eclipseFilter", "any", "ECLIPSE_FILTERS"),
                                ("climes", "off", "CLIMES_MODES"), ("climesObliquity", "date", "CLIMES_OBLIQUITY")):
        assert re.search(rf"\b{key}: \{{ label: '[^']+', def: '{default}', oneOf: {const} \}}", page), key
    # 开了才下发（关 = 零回归）：genParams 的这一段。
    # v3.15.0：genParams 挪成模块级函数（state 形参 st），条件与缺省不变。
    assert "if (st.eclipse && st.eclipse !== 'off') {" in page and "p.eclipseFilter = st.eclipseFilter || 'any';" in page


def test_unknown_layer_values_are_refused_at_the_schema(tmp_path) -> None:
    from horosa_skill.errors import ToolValidationError

    for extra in ({"eclipse": "sideways"}, {"eclipse": "prenatal", "eclipseFilter": "total"}, {"climes": "zones"}, {"climes": "klimata", "climesObliquity": "j2000"}):
        client = AcgClient()
        with pytest.raises(ToolValidationError) as err:  # 后端 ACGraph 对认不出的 eclipse / eclipseFilter 静默按 off / any
            _service(tmp_path, client).run_tool("acg", {**BIRTH, **extra}, save_result=False)
        assert "tool.invalid_option" in json.dumps(err.value.details, ensure_ascii=False) or err.value.code == "tool.invalid_option", err.value
        assert client.calls == []


# ────────────────────────────── 真 JS + 脚本化后端 ──────────────────────────────


def test_layers_off_by_default_send_nothing_and_add_no_block(tmp_path) -> None:
    client = AcgClient()
    env = _service(tmp_path, client).run_tool("acg", dict(BIRTH), save_result=False)
    assert env.ok, env.error
    (sent,) = client.requests("/location/acg")
    assert "eclipse" not in sent and "eclipseFilter" not in sent and "climes" not in sent  # 关 = 请求体与旧版逐键相同
    assert not [line for line in _map(env.data["snapshot_text"]) if line.startswith(("◆ 日食路径", "◆ 七气候带", "◆ 托勒密纬圈"))]
    assert "eclipse" not in env.data["acg"] and "layers" not in env.data["acg"]
    assert not env.warnings, env.warnings


def test_eclipse_path_is_requested_and_summarised_by_the_upstream_builder(tmp_path) -> None:
    client = AcgClient()
    env = _service(tmp_path, client).run_tool("acg", {**BIRTH, "eclipse": "生前", "climes": "klimata"}, save_result=False)
    assert env.ok, env.error
    (sent,) = client.requests("/location/acg")
    assert (sent["eclipse"], sent["eclipseFilter"]) == ("prenatal", "any")  # 中文别名读成规范值；食型缺省 any 一并下发（上游 genParams）
    assert "climes" not in sent and "climesObliquity" not in sent  # 气候带是快照图层，不进后端请求
    body = _map(env.data["snapshot_text"])
    eclipse = _block(body, "◆ 日食路径:")
    # 桩回的是夹具里 2017-08-21 日全食的真实响应：公布值食甚 18:25 UT、出生地（−05:00）钟面 13:25。
    assert eclipse[1].startswith("出生前最近一次日食:全食,食甚 2017/08/21 13:25(出生地时区)/ 2017/08/21 18:25(UT),出生前 ")
    lat, lon, width = re.search(r"食甚地点 ([\d.]+)°N ([\d.]+)°W,食分 [\d.]+,食甚处食带宽约 (\d+) km", eclipse[2]).groups()
    assert abs(float(lat) - 36.97) <= 0.05 and abs(float(lon) - 87.67) <= 0.05 and 105 < int(width) < 125
    assert eclipse[3].startswith("中心线:")
    # 气候带改进档：ε = 后端 meta.obliquity；第 3 带（最长昼 14 时）按公式重算。
    eps = env.data["acg"]["meta"]["obliquity"]
    climes = _block(body, "◆ 七气候带")
    assert climes[0] == f"◆ 七气候带(黄赤交角 {eps:.4f}°,改进:出生时刻的值):"
    bands = climes[1].split(";")
    assert len(bands) == 7 and bands[2].endswith(f" {_latitude(14, eps):.2f}°N") and bands[0].endswith(f" {_latitude(13, eps):.2f}°N")
    # 结果里留原始日食数据与图层口径（报告盘图读同一份）。
    assert env.data["acg"]["eclipse"]["type"] == "total" and len(env.data["acg"]["eclipse"]["track"]) > 100
    assert env.data["acg"]["layers"] == {"climes": "klimata", "climesObliquity": "date"}
    assert not [w for w in env.warnings if "未产出" in w or "须配" in w or "以引擎回显为准" in w], env.warnings
    assert [w for w in env.warnings if "「生前」按 prenatal" in w], env.warnings  # 别名做了解读 → 说出来
    _clean(env)


def test_ptolemy_obliquity_and_parallels(tmp_path) -> None:
    env = _service(tmp_path, AcgClient()).run_tool("acg", {**BIRTH, "climes": "纬圈", "climesObliquity": "经典"}, save_result=False)
    assert env.ok, env.error
    block = _block(_map(env.data["snapshot_text"]), "◆ 托勒密纬圈")
    assert block[0] == "◆ 托勒密纬圈(黄赤交角 23.8556°,经典:托勒密值):"
    rows = block[1].split(";")
    # 《至大论》卷二的纬圈：12¼–18 时每 ¼ 时 24 条、18½–20 时 4 条、21–24 时 4 条，赤道以北共 32 条；24 时 = 极圈 90° − ε。
    assert len(rows) == 32 and rows[0] == f"最长昼 12¼ 时 {_latitude(12.25, PTOLEMY):.2f}°N" and rows[-1] == f"最长昼 24 时 {90 - PTOLEMY:.2f}°N"
    assert env.data["acg"]["layers"] == {"climes": "parallels", "climesObliquity": "ptolemy"}


def test_eclipse_not_returned_or_mismatched_is_reported(tmp_path) -> None:
    # 开了日食路径、引擎却没回（找不到 / 旧引擎不认这个键）：不成块并说明。
    env = _service(tmp_path, AcgClient(eclipse=None)).run_tool("acg", {**BIRTH, "eclipse": "postnatal"}, save_result=False)
    assert env.ok, env.error
    assert _block(_map(env.data["snapshot_text"]), "◆ 日食路径") is None and "eclipse" not in env.data["acg"]
    assert [w for w in env.warnings if "eclipse=postnatal" in w and "没有回结果" in w], env.warnings
    # 回的不是所请求的那一次：以引擎回显为准，并说明。
    wrong = {**FIX["tn_2017_prenatal"]["eclipse"], "which": "prenatal", "filter": "any"}
    env = _service(tmp_path, AcgClient(eclipse=wrong)).run_tool("acg", {**BIRTH, "eclipse": "postnatal", "eclipseFilter": "central"}, save_result=False)
    assert env.ok, env.error
    assert [w for w in env.warnings if "请求 postnatal/central" in w and "prenatal/any" in w], env.warnings
    assert _block(_map(env.data["snapshot_text"]), "◆ 日食路径")[1].startswith("出生前最近一次日食:")


def test_orphan_layer_options_are_reported(tmp_path) -> None:
    client = AcgClient()
    env = _service(tmp_path, client).run_tool("acg", {**BIRTH, "eclipseFilter": "central", "climesObliquity": "ptolemy"}, save_result=False)
    assert env.ok, env.error
    assert "eclipseFilter" not in client.requests("/location/acg")[0]
    assert [w for w in env.warnings if "eclipseFilter 须配 eclipse" in w] and [w for w in env.warnings if "climesObliquity 须配 climes" in w]


# ────────────────────────────── live（vendored v3.14.0 实例） ──────────────────────────────

from test_local_js_tools import make_service, requires_chart, requires_current_runtime_contract  # noqa: E402


def _live(tmp_path, payload: dict):
    env = make_service(tmp_path).run_tool("acg", payload, save_result=False)
    assert env.ok, env.error
    # 上游金样用 UT 时刻配美国坐标：审计 F30 的「时区与经度差三小时以上」提示是该有的披露，其余告警一条都不许有
    assert not [w for w in env.warnings if "不像同一个地方" not in w], env.warnings
    _clean(env)
    return env, _map(env.data["snapshot_text"])


@requires_chart
@requires_current_runtime_contract
def test_live_2017_total_eclipse_matches_the_published_greatest_point(tmp_path) -> None:
    env, body = _live(tmp_path, {**BIRTH, "eclipse": "prenatal"})
    block = _block(body, "◆ 日食路径:")
    assert block[1].startswith("出生前最近一次日食:全食,食甚 2017/08/21 13:25(出生地时区)/ 2017/08/21 18:25(UT),出生前 0.")
    lat, lon, width = re.search(r"食甚地点 ([\d.]+)°N ([\d.]+)°W,食分 1\.0\d+,食甚处食带宽约 (\d+) km", block[2]).groups()
    assert abs(float(lat) - 36.97) <= 0.05 and abs(float(lon) - 87.67) <= 0.05  # 36°58′N 87°40′W
    assert 105 < int(width) < 125  # 食甚处食带宽约 115 km
    # 中心线自北太平洋起、止于大西洋（西经 → 西经，北纬）；俄勒冈海岸段约 44.8°N（上游同一断言，取轨迹点核对）。
    assert re.fullmatch(r"中心线:[\d.]+°N [\d.]+°W → [\d.]+°N [\d.]+°W", block[3])
    oregon = [p for p in env.data["acg"]["eclipse"]["track"] if -125 < p["lon"] < -123]
    assert oregon and abs(oregon[0]["lat"] - 44.8) <= 0.3
    assert env.data["acg"]["eclipse"]["which"] == "prenatal" and env.data["acg"]["eclipse"]["central"] is True


@requires_chart
@requires_current_runtime_contract
def test_live_eclipse_modes_and_filters_pick_the_documented_eclipses(tmp_path) -> None:
    # 出生地时区钟面（上游 test_acg_zone_without_colon）：1990-01-26 日环食食甚 19:30 UT = +08:00 的 01/27 03:30。
    _env, body = _live(tmp_path, {"date": "1990-03-01", "time": "12:00:00", "zone": "+08:00", "lat": "30n00", "lon": "120e00", "eclipse": "prenatal"})
    assert "食甚 1990/01/27 03:30(出生地时区)/ 1990/01/26 19:30(UT)" in _block(body, "◆ 日食路径:")[1]
    # 1975-02-11 05:15 UT 之前最近一次是偏食（上游 test_partial_eclipse_has_no_central_line）；只找中心食 → 1974-06-20。
    born = {"date": "1975-02-11", "time": "05:15:00", "zone": "+00:00", "lat": "36n58", "lon": "87w40"}
    _env, body = _live(tmp_path, {**born, "eclipse": "prenatal"})
    partial = _block(body, "◆ 日食路径:")
    assert partial[1].startswith("出生前最近一次日食:偏食,") and partial[3].startswith("最大食分点轨迹:")
    assert partial[4] == "偏食没有中心线,地图上画的是每一刻食分最大的地点连成的线。" and "食带宽" not in partial[2]
    env, body = _live(tmp_path, {**born, "eclipse": "prenatal", "eclipseFilter": "central"})
    central = _block(body, "◆ 日食路径:")
    assert central[1].startswith("出生前最近一次中心日食:") and "/ 1974/06/20 " in central[1] and central != partial
    assert env.data["acg"]["eclipse"]["filter"] == "central"
    # 2024-01-01 之后最近一次中心食 = 2024-04-08 日全食（上游 test_postnatal_and_unknown_modes）。
    _env, body = _live(tmp_path, {"date": "2024-01-01", "time": "00:00:00", "zone": "+00:00", "lat": "36n58", "lon": "87w40",
                                  "eclipse": "postnatal", "eclipseFilter": "central"})
    after = _block(body, "◆ 日食路径:")[1]
    assert after.startswith("出生后最近一次中心日食:全食,") and "/ 2024/04/08 " in after and ",出生后 " in after


@requires_chart
@requires_current_runtime_contract
def test_live_climes_follow_the_obliquity_setting(tmp_path) -> None:
    env, body = _live(tmp_path, {**BIRTH, "climes": "klimata"})
    eps = env.data["acg"]["meta"]["obliquity"]
    assert 23.42 < eps < 23.45  # 2017 年真黄赤交角约 23.435°
    date = _block(body, "◆ 七气候带")
    assert date[0] == f"◆ 七气候带(黄赤交角 {eps:.4f}°,改进:出生时刻的值):"
    hours = [13, 13.5, 14, 14.5, 15, 15.5, 16]  # 七气候带中线的最长昼
    assert [b.rsplit(" ", 1)[1] for b in date[1].split(";")] == [f"{_latitude(h, eps):.2f}°N" for h in hours]
    _env, body = _live(tmp_path, {**BIRTH, "climes": "klimata", "climesObliquity": "ptolemy"})
    classic = _block(body, "◆ 七气候带")
    assert classic[0] == "◆ 七气候带(黄赤交角 23.8556°,经典:托勒密值):" and classic[1] != date[1]
    _env, body = _live(tmp_path, {**BIRTH, "climes": "parallels", "climesObliquity": "ptolemy"})
    rows = _block(body, "◆ 托勒密纬圈")[1].split(";")
    assert len(rows) == 32 and rows[-1] == "最长昼 24 时 66.14°N"
    # 图层关着不成块、也不改其余正文。
    _env, plain = _live(tmp_path, dict(BIRTH))
    assert plain == [line for line in body if not line.startswith(("◆ 托勒密纬圈", "最长昼 "))]
