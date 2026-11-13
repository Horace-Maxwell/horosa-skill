"""上游 v3.14.0 波斯向运两项新口径：速率「周期律」periodic（十星各按自身周期推、宫头不动）与年长 persianYear 五档。

权威：上游 components/astro/AstroPersianDirected.js（buildPersianHits / buildPersianDirectedSnapshotText / directedAgeYears）与后端
astrostudy/symbolicdir.py（/predict/persianchart）。skill 侧是 Python 移植（service/text/predictive.py）——手抄件，所以：
- `tests/fixtures/sync314_predictive_persian_upstream.json` = **上游源本身**在 node 里对同一张盘跑出的正文（存 sha256 + 头几行 + 定位行）；
  `test_fixture_matches_upstream` 在 HOROSA_SOURCE_ROOT 可用时重跑，上游一改即红；
- `test_python_port_equals_upstream_text` 把 Python 移植逐字对上这份金标（缺省档也在内：发布说明写明「缺省结果不变」）。
重生夹具：
    HOROSA_SOURCE_ROOT=… uv run python -c "import sys; sys.path[:0]=['tests']; import test_sync314_predictive_persian as t; t._write_fixture()"

负向对照（均实跑，见各条 docstring 与备忘）。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fakes import FakeClient, FakeJsClient
from test_sync313_historical import (
    _MOMENT,
    UPSTREAM_UI,
    _run_module,
    _upstream_decls,
    _vurl,
    requires_node,
    requires_upstream,
)

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService, _chart_server_endpoint
from horosa_skill.service.text import predictive as T

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FIXTURE = FIXTURES / "sync314_predictive_persian_upstream.json"
CHART = json.loads((FIXTURES / "chart_1998_predictive.json").read_text(encoding="utf-8"))   # 1998-02-20 20:48 上海，/chart 实抓
NOW_MS = 1793318400000  # 2026-10-30T00:00:00Z
# (场景名, opts)。缺省档 / 旧三档各留一条（「缺省结果不变」的对照），周期律 × 顺逆 × 年长逐档。
CASES: list[tuple[str, dict[str, Any]]] = [
    ("default", {}),
    ("naibod_converse_120", {"rateKey": "naibod", "direction": "converse", "maxYears": 120}),
    ("prophected_dated", {"rateKey": "prophected", "datetime": "2030-06-01 08:00:00"}),
    ("periodic", {"rateKey": "periodic"}),
    ("periodic_converse_dated", {"rateKey": "periodic", "direction": "converse", "datetime": "2031-03-05 12:00:00"}),
    ("periodic_200", {"rateKey": "periodic", "maxYears": 200}),
    ("periodic_hellenistic", {"rateKey": "periodic", "persianYear": "hellenistic", "datetime": "2026-09-24 12:00:00"}),
    ("persian_sidereal", {"persianYear": "sidereal"}),
    ("persian_hellenistic_dated", {"persianYear": "hellenistic", "datetime": "2026-09-24 12:00:00"}),
    ("persian_bija", {"persianYear": "bija"}),
    ("prophected_bijaclassic_converse", {"rateKey": "prophected", "direction": "converse", "persianYear": "bijaClassic"}),
    ("unknown_values_fall_back", {"rateKey": "fast", "persianYear": "lunar"}),   # 上游 builder 自己的回落（runner 在入口就拒，不会走到这里）
]
BC_BIRTH = "-0500-03-21 12:00:00"


def _digest(text: str) -> dict[str, Any]:
    lines = text.split("\n")
    return {"sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "lines": len(lines), "head": lines[:9]}


def _upstream() -> dict[str, Any]:
    """上游 buildPersianDirectedSnapshotText 在 node 里跑：三段补厚 helper 换成「不产段、只记下定位行」（与 skill 的分工同口径）。"""
    assert UPSTREAM_UI is not None
    decls = _upstream_decls(
        "components/astro/AstroPersianDirected.js",
        ["RATE", "RATE_LABEL", "PERIODIC_YEARS", "SOLAR_YEAR_DAYS", "PERSIAN_YEAR_LABEL", "persianYearDays", "PERSIAN_DEFAULT_OPTS", "MOVERS",
         "PERIODIC_MOVERS", "ASPECTS", "norm360", "lonOf", "buildPersianHits", "buildPersianDirectedSnapshotText", "directedAgeYears",
         "selectNearbyPersianHits"],
    )
    src = (
        f"import moment from '{_vurl(_MOMENT)}';\n"
        f"import * as AstroConst from '{_vurl('src/constants/AstroConst.js')}';\n"
        f"import * as AstroText from '{_vurl('src/constants/AstroText.js')}';\n"
        f"import {{ momentOfCivilDateTimeStr, civilDateAfterDays }} from '{_vurl('src/vendor/utils/civilMoment.js')}';\n"
        f"import {{ TIME_LORD_YEAR_TYPES }} from '{_vurl('src/vendor/utils/timeLordYears.js')}';\n"
        "export const captured = { lines: null };\n"
        "const birthHeaderLines = () => [];\n"
        "const currentMomentLines = (c, x) => { captured.lines = x; return []; };\n"
        "const methodNoteLines = () => [];\n"
        f"{decls}\n"
        "export { moment, buildPersianHits, buildPersianDirectedSnapshotText, directedAgeYears, PERIODIC_YEARS, PERSIAN_YEAR_LABEL, persianYearDays, RATE, RATE_LABEL };\n"
    )
    body = (
        "m.moment.now = () => Number(argv[1]); const chart = JSON.parse(argv[2]); const out = { texts: {}, moments: {} };"
        " for (const [name, opts] of JSON.parse(argv[0])) { m.captured.lines = null;"
        " out.texts[name] = m.buildPersianDirectedSnapshotText(chart, opts); out.moments[name] = m.captured.lines; }"
        " out.bc = m.buildPersianHits({ ...chart, params: { birth: argv[3] } }, 'periodic', 90, 'direct', 'hellenistic').slice(0, 40)"
        ".map((h) => [h.age, h.promittor, h.aspect, h.significator, h.date]);"
        " out.tables = { periodicYears: m.PERIODIC_YEARS, yearLabels: m.PERSIAN_YEAR_LABEL, rates: m.RATE, rateLabels: m.RATE_LABEL,"
        " yearDays: Object.fromEntries(Object.keys(m.PERSIAN_YEAR_LABEL).map((k) => [k, m.persianYearDays(k)])) };"
        " out.ages = [m.directedAgeYears('1998-02-20 20:48:00', '2026-09-24 12:00:00'), m.directedAgeYears('1998-02-20 20:48:00', '2026-09-24 12:00:00', 360)];"
        " return out;"
    )
    slim = {"params": CHART["params"], "chart": {"objects": CHART["chart"]["objects"], "houses": CHART["chart"]["houses"]}}
    with _chart_file(slim) as path:
        body = body.replace("JSON.parse(argv[2])", "JSON.parse((await import('node:fs')).readFileSync(argv[2], 'utf8'))")
        return _run_module(src, body, json.dumps(CASES), str(NOW_MS), f"{path}", BC_BIRTH)


class _chart_file:
    """整盘 JSON 写临时文件（Windows 命令行长度上限：大载荷不进 argv）。"""

    def __init__(self, chart: dict[str, Any]) -> None:
        self.chart = chart

    def __enter__(self) -> str:
        import tempfile

        self.tmp = tempfile.TemporaryDirectory()
        path = Path(self.tmp.name) / "chart.json"
        path.write_text(json.dumps(self.chart), encoding="utf-8")
        return path.as_posix()

    def __exit__(self, *exc: Any) -> None:
        self.tmp.cleanup()


def _compact(raw: dict[str, Any]) -> dict[str, Any]:
    return {**raw, "texts": {name: _digest(text) for name, text in raw["texts"].items()}}


def _write_fixture() -> None:
    FIXTURE.write_text(json.dumps(_compact(_upstream()), ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


GOLD = json.loads(FIXTURE.read_text(encoding="utf-8")) if FIXTURE.is_file() else {}


def _local_now() -> datetime:
    """NOW_MS 的本机钟面（上游 moment() 的本地格式化与之同值）。"""
    return datetime.fromtimestamp(NOW_MS / 1000)


def _python_text(opts: dict[str, Any]) -> tuple[str, list[str]]:
    moment: list[str] = []
    text = T._build_persiandirected_snapshot_text(CHART, dict(opts), now=_local_now(), moment_lines=moment)
    return text.rstrip("\n"), moment


@requires_node
@requires_upstream
def test_fixture_matches_upstream() -> None:
    """夹具 = 上游 v3.14.0 源当场跑出来的值。负向对照（实跑）：夹具 periodic 的 sha256 改一位 → 红。"""
    assert _compact(_upstream()) == GOLD


@pytest.mark.parametrize(("name", "opts"), CASES, ids=[name for name, _ in CASES])
def test_python_port_equals_upstream_text(name: str, opts: dict[str, Any]) -> None:
    """Python 移植逐字 == 上游正文（sha256 + 行数 + 头九行）；定位行（当前向运年龄）== 上游交给 buildCurrentMomentLines 的那一行。
    负向对照（实跑）：_build_persian_hits 里周期律的速率改回 base_rate → periodic×4 红；日期换算恒用 _PERSIAN_YEAR_DAYS → 四个非回归年场景红；
    _build_persiandirected_snapshot_text 去掉「年长：」行 → 同四个红；_persian_directed_age_years 不吃 year_days → 两个带年长的 dated 场景的定位行红。"""
    text, moment = _python_text(opts)
    assert _digest(text) == GOLD["texts"][name]
    assert moment == GOLD["moments"][name]


def test_default_text_is_unchanged_by_the_new_options() -> None:
    """发布说明「缺省结果不变」：不给新键 == 显式给缺省值 == 既有金样（tests/fixtures/…persiandirected 金样由 test_progression_builders 另守）。"""
    base, _ = _python_text({})
    assert _python_text({"rateKey": "persian", "direction": "direct", "maxYears": 90, "persianYear": "solar"})[0] == base
    assert "年长：" not in base and base.splitlines()[1].startswith("黄经象征向运(波斯 1°/年)：")


def test_tables_equal_upstream_and_the_vendored_year_table() -> None:
    """周期年数 / 年长天数与标签 / 速率表 == 上游（夹具里是上游源导出的表）；年长四档 == vendored utils/timeLordYears.js 的同名档。
    负向对照（实跑）：_PERSIAN_PERIODIC_YEARS 的 Saturn 改 29 → 红；_PERSIAN_YEAR_TYPES 的 bija 天数改回 366.256399 → 红。"""
    tables = GOLD["tables"]
    assert T._PERSIAN_PERIODIC_YEARS == tables["periodicYears"] and list(T._PERSIAN_PERIODIC_YEARS) != []
    assert set(T._PERSIAN_PERIODIC_MOVERS) == set(tables["periodicYears"]) and T._PERSIAN_PERIODIC_MOVERS[:7] == T._PERSIAN_MOVERS
    assert {key: label for key, (_days, label) in T._PERSIAN_YEAR_TYPES.items()} == tables["yearLabels"]
    assert {key: days for key, (days, _label) in T._PERSIAN_YEAR_TYPES.items()} == tables["yearDays"]
    assert list(T._PERSIAN_YEAR_TYPES) == list(tables["yearLabels"]) == ["solar", "sidereal", "hellenistic", "bija", "bijaClassic"]
    assert T._PERSIAN_RATE == tables["rates"] and T._PERSIAN_RATE_LABEL == tables["rateLabels"]
    assert T._persian_year_days("solar") == T._persian_year_days("nope") == 365.2421904
    from node_esm import run_node_esm

    years = json.loads(run_node_esm(
        "import { TIME_LORD_YEAR_TYPES as Y } from './src/vendor/utils/timeLordYears.js'; console.log(JSON.stringify(Y))",
        cwd=Path(__file__).resolve().parents[1] / "horosa-core-js", timeout=60,
    ))
    for key in ("sidereal", "hellenistic", "bija", "bijaClassic"):
        assert T._PERSIAN_YEAR_TYPES[key] == (years[key]["days"], years[key]["label"]), key
    assert T._PERSIAN_YEAR_TYPES["solar"][1] == years["solar"]["label"] and tuple(years) == T._TIME_LORD_YEAR_TYPES


def _mini(objects: dict[str, float], birth: str = "2000-01-01 12:00:00") -> dict[str, Any]:
    return {"params": {"birth": birth}, "chart": {"objects": [{"id": k, "lon": v} for k, v in objects.items()], "houses": []}}


def test_periodic_rule_values_by_hand() -> None:
    """值级金标（手算，不取自输出）：周期律速率 = 360° ⁄ 周期年数。
    月亮 4 年一周 = 90°/年：月在 0°、目标在 90° → 合相在 1 岁、5 岁、9 岁…（每 4 年一次）；六合（目标 − 60° = 30°）在 30⁄90 = 0.33 岁。
    冥王 248 年一周：同样 90° 的弧要 62 年。土星 30 年一周 = 12°/年：90° 的弧 7.5 年。交点不作向运星，只作被触及的本命点。
    负向对照（实跑）：_PERSIAN_PERIODIC_YEARS["Moon"] 改 5 → 红（1 岁变 1.25 岁）。"""
    hits = T._build_persian_hits(_mini({"Moon": 0.0, "Venus": 90.0}), "periodic", 12, "direct")
    moon_conj = [h["age"] for h in hits if (h["promittor"], h["aspect"], h["significator"]) == ("Moon", 0, "Venus")]
    assert moon_conj == [1.0, 5.0, 9.0]
    assert [h["age"] for h in hits if (h["promittor"], h["aspect"]) == ("Moon", 60)][0] == 0.33
    assert [h["age"] for h in hits if (h["promittor"], h["aspect"], h["significator"]) == ("Venus", 0, "Moon")] == [6.0]   # 金 8 年一周：270° ⁄ 45
    pluto = T._build_persian_hits(_mini({"Pluto": 0.0, "Sun": 90.0}), "periodic", 90, "direct")
    assert [h["age"] for h in pluto if (h["promittor"], h["aspect"]) == ("Pluto", 0)] == [62.0]
    saturn = T._build_persian_hits(_mini({"Saturn": 0.0, "Sun": 90.0}), "periodic", 40, "direct")
    assert [h["age"] for h in saturn if (h["promittor"], h["aspect"]) == ("Saturn", 0)] == [7.5, 37.5]
    nodes = T._build_persian_hits(_mini({"North Node": 0.0, "Sun": 30.0, "Uranus": 200.0}), "periodic", 90, "direct")
    promittors = {h["promittor"] for h in nodes}
    assert "North Node" not in promittors and {"Sun", "Uranus"} <= promittors
    assert any(h["significator"] == "North Node" for h in nodes)
    # 旧三档只推七曜：天王不作向运星（周期律才把向运星扩到十星）。
    assert "Uranus" not in {h["promittor"] for h in T._build_persian_hits(_mini({"Sun": 30.0, "Uranus": 200.0}), "persian", 90, "direct")}
    # 逆向：弧 = 向运星 − 目标（月 0° → 目标 90° 逆行要走 270°）。
    converse = T._build_persian_hits(_mini({"Moon": 0.0, "Venus": 90.0}), "periodic", 12, "converse")
    assert [h["age"] for h in converse if (h["promittor"], h["aspect"], h["significator"]) == ("Moon", 0, "Venus")] == [3.0, 7.0, 11.0]


def test_year_length_values_by_hand() -> None:
    """值级金标（手算）：应期日期 = 出生日 + round(年龄 × 年长)。日在 0°、月在 10°、波斯 1°/年 → 合相在 10 岁：
    回归年 3652.42 → 第 3652 天；360 日年 → 第 3600 天；恒星年 3652.56 → 第 3653 天；Bija 经典 3662.56 → 第 3663 天。年龄不随年长变。
    当前向运年龄 = 日数差 ⁄ 年长：出生后整 3600 天，按 360 日年正好 10 岁。
    负向对照（实跑）：_build_persian_hits 的日期换算写死 _PERSIAN_YEAR_DAYS → 后三条日期红。"""
    birth = datetime(2000, 1, 1)
    want = {"solar": 3652, "hellenistic": 3600, "sidereal": 3653, "bija": 3653, "bijaClassic": 3663}
    for year, days in want.items():
        hits = T._build_persian_hits(_mini({"Sun": 0.0, "Moon": 10.0}), "persian", 90, "direct", year)
        hit = next(h for h in hits if (h["promittor"], h["aspect"], h["significator"]) == ("Sun", 0, "Moon"))
        assert hit["age"] == 10.0 and hit["date"] == (birth + timedelta(days=days)).strftime("%Y-%m-%d"), year
    target = (datetime(2000, 1, 1, 12) + timedelta(days=3600)).strftime("%Y-%m-%d %H:%M:%S")
    assert T._persian_directed_age_years("2000-01-01 12:00:00", target, 360.0) == 10.0
    assert abs(T._persian_directed_age_years("2000-01-01 12:00:00", target) - 3600 / 365.2421904) < 1e-12
    assert [T._persian_directed_age_years("1998-02-20 20:48:00", "2026-09-24 12:00:00"),
            T._persian_directed_age_years("1998-02-20 20:48:00", "2026-09-24 12:00:00", 360)] == GOLD["ages"]


def test_bc_birth_dates_with_periodic_rate_and_egyptian_year_match_upstream() -> None:
    """公元前出生 × 周期律 × 360 日年：日期走民用历（与上游 civilDateAfterDays 逐值相同）。"""
    hits = T._build_persian_hits({**CHART, "params": {"birth": BC_BIRTH}}, "periodic", 90, "direct", "hellenistic")
    assert [[h["age"], h["promittor"], h["aspect"], h["significator"], h["date"]] for h in hits[:40]] == GOLD["bc"]
    assert GOLD["bc"][0][4].startswith("-0500-") or GOLD["bc"][0][4].startswith("-0499-")


# ── runner / schema / guidance ─────────────────────────────────────────────────────────────────────


CHART_ENDPOINT = _chart_server_endpoint("/chart")


class _Client(FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def call(self, endpoint: str, payload: dict) -> dict:
        self.calls.append((endpoint, dict(payload)))
        if endpoint == CHART_ENDPOINT:
            return json.loads(json.dumps(CHART))
        if endpoint == "/predict/persianchart":
            objects = [o for o in CHART["chart"]["objects"] if o["id"] in T._PERSIAN_PERIODIC_YEARS] if payload.get("rateKey") == "periodic" else CHART["chart"]["objects"]
            return {"date": payload["datetime"], "rateKey": payload.get("rateKey", "persian"), "direction": payload.get("direction", "direct"),
                    "ageYears": 29.0, "chart": {"objects": json.loads(json.dumps(objects)), "aspects": []}, "lots": [{"id": "Pars Spirit", "lon": 1.0}]}
        return super().call(endpoint, payload)

    def sent(self, endpoint: str) -> dict[str, Any]:
        return [p for e, p in self.calls if e == endpoint][-1]


BIRTH = {"date": "1998-02-20", "time": "20:48:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "agent_confirmed_settings": True}


def _service(tmp_path: Path, client: FakeClient) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    return HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=FakeJsClient())


def _section(text: str, title: str) -> str:
    head = f"[{title}]\n"
    start = text.index(head) + len(head)
    end = text.find("\n\n[", start)
    return text[start:] if end < 0 else text[start:end]


def test_runner_passes_the_new_options_to_the_table_and_the_backend(tmp_path: Path) -> None:
    """周期律 + 年长：主表首行 / 年长行按所选写；/predict/persianchart 带 rateKey 与 persianYear（后端按它折算向运年龄）；本命 /chart 不带。
    负向对照（实跑）：_persianchart_by_date 的透传键表去掉 persianYear 不影响（它本就在 payload 里）——所以另断言缺省时不发；
    runner 不把 persianYear 交给 builder → 「年长：」行缺 → 红。"""
    client = _Client()
    result = _service(tmp_path, client).run_tool(
        "persiandirected", {**BIRTH, "rateKey": "periodic", "persianYear": "hellenistic", "datetime": "2026-09-24"}, save_result=False)
    assert result.ok is True, result.error
    body = _section(result.data["snapshot_text"], "波斯向运（Persian Directed）").splitlines()
    assert body[0].startswith("周期律：十星各按自身周期顺向推进(月 4、金 8、水 10、木 12、火 15、日 19、土 30、天 84、海 165、冥 248 年一周),交点与阿拉伯点不向运")
    assert body[1] == "年长：埃及 / 希腊化年（360 日）"
    sent = client.sent("/predict/persianchart")
    assert (sent["rateKey"], sent["persianYear"], sent["datetime"]) == ("periodic", "hellenistic", "2026/09/24 12:00:00")
    assert "persianYear" not in client.sent(CHART_ENDPOINT) and "datetime" not in client.sent(CHART_ENDPOINT)
    dated = _section(result.data["snapshot_text"], "指定日期向运盘")
    assert "速率：periodic（周期律：十星各按自身周期，交点与阿拉伯点不向运）" in dated and "（年长：埃及 / 希腊化年（360 日））" in dated
    assert "周期律不推阿拉伯点" in dated and "向运点位：" in dated
    listed = [line.split("：")[0] for line in dated.split("向运点位：\n")[1].splitlines() if "：" in line and not line.startswith("（")]
    assert len(listed) == len(set(listed)) == 10, listed   # 后端只回十星
    snap = result.data["export_snapshot"]
    assert snap["missing_selected_sections"] == [] and snap["unknown_detected_sections"] == []
    plain = _service(tmp_path, client).run_tool("persiandirected", {**BIRTH, "datetime": "2026-09-24"}, save_result=False)
    assert "persianYear" not in client.sent("/predict/persianchart")
    assert "年长：" not in plain.data["snapshot_text"] and "速率：persian　" in plain.data["snapshot_text"]


def test_bad_values_fail_loudly_and_guidance_lists_the_new_options(tmp_path: Path) -> None:
    from horosa_skill.agent_guidance import TOOL_GUIDANCE
    from horosa_skill.schemas.tools import PersianDirectedInput

    for bad in ({"persianYear": "lunar"}, {"persianYear": "abumashar"}, {"rateKey": "period"}):   # 年长只有五档（没有 abumashar / mashaallah）
        result = _service(tmp_path, _Client()).run_tool("persiandirected", {**BIRTH, **bad}, save_result=False)
        assert result.ok is False and result.error.code == "tool.predictive_invalid_option", bad
    questions = {item["field"]: item for item in TOOL_GUIDANCE["persiandirected"]["ask_if_missing"]}
    assert questions["rateKey"]["values"] == list(T._PERSIAN_RATE) == ["persian", "prophected", "naibod", "periodic"]
    defaults = {item["field"]: item["value"] for item in TOOL_GUIDANCE["persiandirected"]["safe_defaults"]}
    assert defaults["persianYear"] == "solar" and defaults["rateKey"] == "persian"
    fields = PersianDirectedInput.model_fields
    assert "periodic" in fields["rateKey"].description
    assert all(key in fields["persianYear"].description for key in T._PERSIAN_YEAR_TYPES)


# ── live ───────────────────────────────────────────────────────────────────────────────────────────

from test_local_js_tools import make_service, requires_chart, requires_current_runtime_contract  # noqa: E402


@requires_current_runtime_contract
@requires_chart
def test_live_periodic_rate_and_year_length_reach_the_backend(tmp_path: Path) -> None:
    """vendored v3.14.0 引擎：周期律的指定日期盘只有十星、交点不在向运相位里；年长改了行进年数（日数差 ⁄ 年长）与主表日期。"""
    service = make_service(tmp_path)

    def run(**extra: Any) -> Any:
        result = service.run_tool("persiandirected", {**BIRTH, "datetime": "2026-09-24 12:00:00", **extra}, save_result=False)
        assert result.ok is True, result.error
        snap = result.data["export_snapshot"]
        assert snap["missing_selected_sections"] == [] and snap["unknown_detected_sections"] == []
        return result

    plain, periodic, egypt = run(), run(rateKey="periodic"), run(persianYear="hellenistic")
    assert len(plain.data["directed_chart"]["chart"]["objects"]) > 20
    assert {o["id"] for o in periodic.data["directed_chart"]["chart"]["objects"]} == set(T._PERSIAN_PERIODIC_YEARS)
    assert {row["directId"] for row in periodic.data["directed_chart"]["chart"]["aspects"]} <= set(T._PERSIAN_PERIODIC_YEARS)
    days = plain.data["directed_chart"]["ageYears"] * 365.2421904
    assert abs(egypt.data["directed_chart"]["ageYears"] - days / 360.0) < 2e-3   # 后端回显四位小数
    assert plain.data["directed_chart"]["ageYears"] == periodic.data["directed_chart"]["ageYears"]
    # 周期律下月亮 90°/年：向运月亮的黄经 = 本命月亮 + 年龄 × 90°（值级：后端 symbolicdir 与前端应期表同一条律）。
    natal_moon = next(o["lon"] for o in plain.data["raw"]["chart"]["objects"] if o["id"] == "Moon")
    moved = next(o["lon"] for o in periodic.data["directed_chart"]["chart"]["objects"] if o["id"] == "Moon")
    age = periodic.data["directed_chart"]["ageYears"]
    assert abs(((natal_moon + age * 90.0 - moved + 180.0) % 360.0) - 180.0) < 0.05
    main = lambda r: _section(r.data["snapshot_text"], "波斯向运（Persian Directed）")  # noqa: E731
    assert main(plain) != main(periodic) != main(egypt) and main(plain) != main(egypt)
    assert main(egypt).splitlines()[1] == "年长：埃及 / 希腊化年（360 日）"
