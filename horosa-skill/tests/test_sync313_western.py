"""上游 v3.13.0（Horosa-Public @ 965af0f4，自 07df9799 / v3.11.3 起）西占 chart 家族 + 汉堡学派快照增量 —— 值级金标。

金标来源（不手写）：`tests/fixtures/sync313_western_live.json`
- live 盘 / 合盘 / 中点响应 = vendored 引擎 :8877 实抓（skill `run_tool` 经 HOROSA_CHART_SERVER_ROOT=:8877）；
- upstream_* = 上游 965af0f4 源在 node 里（esbuild 打包 utils/astroAiSnapshot.js · components/astro/AstroRelative.js ·
  components/germany/AstroMidpoint.js）对**同一份数据**跑出的原文。

覆盖的上游增量（每条测试写明「旧代码为什么会红」= 负向对照，实测见同步报告）：
1. AstroConst.ANTIVERTEX + AstroText 三表「反宿命点」（主限法世俗盘轴应星 N_Antivertex_0）；
2. buildBaseInfoLines / buildPredictiveBirthLines：houses[].polarMc → POLAR_MC_NOTE（wholeSignRulers.js:232-241）；
3. resolveHouseSystem：derivedModeOf==='compositeWholeFromAsc' → 「整宫(组合上升)」+ 宫主表按整宫折叠；
4. buildRelativeSnapshotText：「宫制：所选 X,本盘实际 Y」/ 口径行（unifiedByA）/「宫制说明：」+ snapHsys；
5. buildRectifySection：太阳弧标签 均日弧 / 59′12″（盘基 dialBaseDegText，缺省 90°）；
6. CLS_CALIBRE_LABELS.hermeticLotsReversal 七星点 → 六星点；
7. 汉堡学派：[赤纬接触]（aiExport v59 自 [汉堡学派要素] 拆出、缺省开）与 [中点坐标]（v60，挂载 mpCoord）；
8. buildCurrentMomentLines：出生时刻按本盘时区解读（birthInstantMsInZone）。
"""
from __future__ import annotations

import copy
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

import pytest
from fakes import FakeClient, FakeJsClient

from horosa_skill.astro_rulers import (
    COMPOSITE_WHOLE_SIGN_LABEL,
    POLAR_MC_NOTE,
    build_house_system_ruler_section_lines,
    resolve_house_system,
)
from horosa_skill.config import Settings
from horosa_skill.engine import astro_snapshot as snap
from horosa_skill.engine import astroextra_snapshots as ax
from horosa_skill.engine.js_client import HorosaJsEngineClient
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService, _build_astro_snapshot_text, _build_natal_extra_sections
from horosa_skill.service.text import astro_core
from horosa_skill.service.text.western import (
    _build_relative_snapshot_text,
    _dial_points,
    _germany_coord_midpoint_lines,
    _germany_declination_lines,
    _germany_rectify_lines,
)

FIXTURE = json.loads((Path(__file__).resolve().parent / "fixtures" / "sync313_western_live.json").read_text(encoding="utf-8"))
_UPSTREAM_SRC = Path(os.environ.get("HOROSA_SOURCE_ROOT") or "/nonexistent") / "Horosa-Web" / "astrostudyui" / "src"
needs_upstream = pytest.mark.skipif(not _UPSTREAM_SRC.is_dir(), reason="drift sentinel needs HOROSA_SOURCE_ROOT (upstream checkout)")
requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def _split(text: str) -> dict[str, str]:
    """`[X]` 整行段头切段（与 exports/parser 同口径），段体去首尾空白。"""
    out: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in f"{text}".split("\n"):
        if re.fullmatch(r"\[.+\]", line):
            current = out.setdefault(line[1:-1], [])
            continue
        if current is not None:
            current.append(line)
    return {title: "\n".join(lines).strip() for title, lines in out.items()}


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        server_root="http://127.0.0.1:9",
        chart_server_root="http://127.0.0.1:9",
        runtime_root=tmp_path / "runtime",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )


# ─────────────────────────── 1. 反宿命点 ───────────────────────────
def test_antivertex_label_is_in_every_label_table() -> None:
    """AstroText.js AstroTxtMsg / AstroMsg / AstroMsgCN[ANTIVERTEX] = '反宿命点'（v3.13.0 新增）。主限法世俗盘轴应星行
    id N_Antivertex_0 经这些表出名。旧代码：四张表都缺 → 名字回落原样英文 id「Antivertex」。"""
    assert ax.ASTRO_TXT_MSG["Antivertex"] == "反宿命点"
    assert ax.ASTRO_MSG_TEXT["Antivertex"] == "反宿命点"
    assert ax.ai_msg("Antivertex") == "反宿命点"
    assert astro_core.ASTRO_TEXT_MAP["Antivertex"] == "反宿命点"
    assert astro_core._astro_msg("Antivertex", short=True) == "反宿命点"


# ─────────────────────────── 2. 极区天顶说明行 ───────────────────────────
@requires_node
def test_polar_chart_snapshot_matches_upstream_builder_byte_for_byte(tmp_path) -> None:
    """70°N 冬至正午（上游 test_polar_mc_house_systems.py POLAR_BELOW 同一时刻）：后端逐宫打 polarMc → [起盘信息]
    在「黄道，宫制」行后多一行 POLAR_MC_NOTE。整盘与上游 buildAstroSnapshotContent 同段逐字节相同。
    旧代码：无此行 → [起盘信息] 与上游差一行（红）。"""
    fx = FIXTURE["polar_chart"]
    assert fx["chart"]["chart"]["houses"][0]["polarMc"] == "upperMeridian"
    js = HorosaJsEngineClient(_settings(tmp_path))
    chart = fx["chart"]
    extras = js.run("astroextra", {"chart": chart, "options": {}})["data"]
    egypt = js.run("egypt_section", {"chart": chart, "fields": {}})["text"]
    response = {**chart, "_natalExtras": _build_natal_extra_sections(extras), "_egyptSection": egypt}
    skill = _split(_build_astro_snapshot_text(fx["fields"], response))
    upstream = _split(fx["upstream_text"])
    assert [title for title in skill if title != "月宿"] == list(upstream)
    for title, body in upstream.items():
        assert skill[title] == body, title
    start = skill["起盘信息"].splitlines()
    assert start[start.index("回归黄道，Regiomontanus") + 1] == POLAR_MC_NOTE


def test_polar_note_follows_the_backend_flag_in_all_three_header_ports() -> None:
    """三处 [起盘信息] 移植都只认 houses[].polarMc（truthy）：engine 整盘 / service 旧版 base-info / 星运 buildPredictiveBirthLines。
    去掉标记 → 一行都不出（非极区零变化）。"""
    chart = copy.deepcopy(FIXTURE["polar_chart"]["chart"])
    fields = FIXTURE["polar_chart"]["fields"]
    assert POLAR_MC_NOTE in snap.build_base_info_lines(chart, fields)
    assert POLAR_MC_NOTE in astro_core._build_base_info_lines(chart, fields)
    birth = ax.predictive_birth_lines(chart)
    assert birth[birth.index("宫制：Regiomontanus") + 1] == POLAR_MC_NOTE
    for house in chart["chart"]["houses"]:
        house.pop("polarMc", None)
    for lines in (snap.build_base_info_lines(chart, fields), astro_core._build_base_info_lines(chart, fields), ax.predictive_birth_lines(chart)):
        assert POLAR_MC_NOTE not in lines


@needs_upstream
def test_polar_note_text_tracks_upstream() -> None:
    src = (_UPSTREAM_SRC / "utils/wholeSignRulers.js").read_text(encoding="utf-8")
    assert f"export const POLAR_MC_NOTE = '{POLAR_MC_NOTE}';" in src
    assert f"export const COMPOSITE_WHOLE_SIGN_LABEL = '{COMPOSITE_WHOLE_SIGN_LABEL}';" in src


# ─────────────────────────── 9. 交点入旺（后端算、快照照印）───────────────────────────
@requires_node
def test_node_exaltation_chart_matches_upstream_builder(tmp_path) -> None:
    """nodeExaltation=1、北交在双子：后端（perchart_parts/classical_request.py）给北交/南交 selfDignity=['exalt'] score 4；
    快照 [行星]◆尊贵 照印「擢升 | 4」、[起盘信息] 出「古典口径（非默认项）：交点入旺=开。」——与上游同段逐字节相同。"""
    fx = FIXTURE["node_exalt"]
    node = next(o for o in fx["chart"]["chart"]["objects"] if o["id"] == "North Node")
    assert node["sign"] == "Gemini" and node["selfDignity"] == ["exalt"]
    js = HorosaJsEngineClient(_settings(tmp_path))
    chart = fx["chart"]
    extras = js.run("astroextra", {"chart": chart, "options": {}})["data"]
    egypt = js.run("egypt_section", {"chart": chart, "fields": {}})["text"]
    response = {**chart, "_natalExtras": _build_natal_extra_sections(extras), "_egyptSection": egypt}
    skill = _split(_build_astro_snapshot_text(fx["fields"], response))
    upstream = _split(fx["upstream_text"])
    for title, body in upstream.items():
        assert skill[title] == body, title
    assert "古典口径（非默认项）：交点入旺=开。" in skill["起盘信息"].splitlines()
    assert any(line.startswith("| 北交 (10th; -) | 擢升 | 4 |") for line in skill["行星"].splitlines())


# ─────────────────────────── 3/4. 组合盘回落整宫 ───────────────────────────
def test_composite_whole_sign_fallback_resolves_like_upstream() -> None:
    """wholeSignRulers.js:168-214：组合盘宫位带 hsysDerived='compositeWholeFromAsc' → 标签「整宫(组合上升)」、
    isAscWholeSign 恒真（[分宫制宫神星表] 折叠成一行）——即便请求宫制是 24（福点整宫制）。
    旧代码：derivedModeOf 只认 'wholeFromAsc' → 标签回落「福点整宫制」、宫神星表 12 行不折叠。"""
    result = FIXTURE["rel_composite_24"]["result"]
    assert result["chart"]["houses"][0]["hsysDerived"] == "compositeWholeFromAsc"
    resolved = resolve_house_system(result, {"hsys": 24})
    assert resolved == {"num": "24", "label": COMPOSITE_WHOLE_SIGN_LABEL, "isAscWholeSign": True}
    lines = build_house_system_ruler_section_lines(result, {"hsys": 24}, ax.ai_msg)
    assert len(lines) == 1 and lines[0].startswith("当前分宫制即整宫制")


def test_relative_composite_house_note_matches_upstream() -> None:
    """AstroRelative.js buildRelativeSnapshotText（v3.13.0）：组合盘所选宫制 24 属整宫一类 → 后端回落整宫（compositeHouseNote +
    params.hsys=0）→ [关系起盘信息]「宫制：所选 福点整宫制,本盘实际 整宫制」、[合成图盘] 首行「宫制说明：…」，嵌入整盘按实际宫制
    （snapHsys=0）且宫制标注「整宫(组合上升)」。与上游同一份 live 响应逐字节比 [关系起盘信息]、[合成图盘] 逐行集合比。
    旧代码：「宫制：福点整宫制」、无宫制说明、嵌入盘按 24 标注。"""
    fx = FIXTURE["rel_composite_24"]
    skill = _split(_build_relative_snapshot_text(fx["payload"], fx["result"]))
    upstream = _split(fx["upstream_text"])
    assert skill["关系起盘信息"] == upstream["关系起盘信息"]
    assert "宫制：所选 福点整宫制,本盘实际 整宫制" in skill["关系起盘信息"].splitlines()
    body, up_body = skill["合成图盘"].splitlines(), upstream["合成图盘"].splitlines()
    assert body[0] == up_body[0] == f"宫制说明：{fx['result']['compositeHouseNote']}"
    assert "回归黄道，整宫(组合上升)" in body

    def sub_block(lines: list[str], title: str) -> list[str]:
        start = lines.index(f"· {title}")
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("· ")), len(lines))
        return lines[start:end]

    # 嵌入整盘的富化段（12分度/寿命格局…）由 service 另挂，这里只比与宫制相关的子块（live 全段逐行一致见同步报告）。
    for title in ("起盘信息", "宫位宫头"):
        assert sub_block(body, title) == sub_block(up_body, title), title


def test_relative_composite_polar_fallback_uses_the_echoed_house_system() -> None:
    """极区分支（chartcomposite.py）：星盘A 70°N 下 Placidus 无解 → 两盘统一改 Porphyry 合宫头（note + params.hsys=9 + 逐宫
    hsysFallback）。表头「所选 Placidus,本盘实际 Porphyry」；嵌入整盘 fields.hsys 取回显 9（snapHsys）→「回归黄道，Porphyry」。
    旧代码 / 去掉 snapHsys：嵌入盘照请求 3 标「Placidus」（宫头其实是 Porphyry 合出的）。与上游 live 同响应逐字节比。"""
    fx = FIXTURE["rel_composite_polar"]
    assert fx["result"]["params"]["hsys"] == 9 and fx["result"]["chart"]["houses"][0]["hsysFallback"] == "Porphyry"
    skill = _split(_build_relative_snapshot_text(fx["payload"], fx["result"]))
    upstream = _split(fx["upstream_text"])
    assert skill["关系起盘信息"] == upstream["关系起盘信息"]
    assert "宫制：所选 Placidus,本盘实际 Porphyry" in skill["关系起盘信息"].splitlines()
    body, up_body = skill["合成图盘"].splitlines(), upstream["合成图盘"].splitlines()
    assert body[0] == up_body[0] == f"宫制说明：{fx['result']['compositeHouseNote']}"
    start = body.index("· 起盘信息")
    up_start = up_body.index("· 起盘信息")
    assert body[start:start + 9] == up_body[up_start:up_start + 9]
    assert "回归黄道，Porphyry" in body[start:start + 9] and POLAR_MC_NOTE in body[start:start + 9]


def test_germany_schema_declares_mp_coord() -> None:
    """GermanyInput.mpCoord（挂载 GERMANY_FIELDS.mpCoord 值域 lon/ra/decl）：声明才进 MCP 扁平面 + 校验；不进 tools/list 广告层。"""
    from pydantic import ValidationError

    from horosa_skill.schemas.tools import GermanyInput

    birth = {"date": "1990-05-04", "time": "12:30:00", "zone": "+08:00", "lat": "31n14", "lon": "121e30"}
    assert GermanyInput(**birth, mpCoord="ra").mpCoord == "ra"
    with pytest.raises(ValidationError):
        GermanyInput(**birth, mpCoord="ecliptic")
    assert "mpCoord" in GermanyInput.ADVERTISE_HIDDEN


def test_relative_header_without_note_or_unified_flag_is_unchanged() -> None:
    """无 compositeHouseNote → 照旧「宫制：X」、无宫制说明行；unifiedByA 只在 AI 双盘挂载（pair.js）出口径行。"""
    fx = FIXTURE["rel_composite_24"]
    result = {k: v for k, v in fx["result"].items() if k != "compositeHouseNote"}
    skill = _split(_build_relative_snapshot_text(fx["payload"], result))
    assert "宫制：福点整宫制" in skill["关系起盘信息"].splitlines()
    assert not skill["合成图盘"].startswith("宫制说明：")
    unified = _split(_build_relative_snapshot_text({**fx["payload"], "unifiedByA": True}, result))["关系起盘信息"].splitlines()
    assert unified[-1] == "口径：两盘统一按星盘A的宫制 / 黄道 / 古典口径起盘(星盘B 的单盘段仍按它自己记录的口径)"


# ─────────────────────────── 5. 校时预览 ───────────────────────────
def test_rectify_section_matches_upstream_labels() -> None:
    """buildRectifySection（v3.13.0）：太阳弧缺省标签 Naibod → 均日弧；盘基 dialBaseDegText(90) = '90°'。
    旧代码：「太阳弧 Naibod」→ 与上游首行不等（红）。"""
    fx = FIXTURE["germany_default"]
    points = _dial_points(fx["objects"], fx["tnp"])
    lines = _germany_rectify_lines(fx["payload"], fx["payload"]["rectifyEvents"], points)
    assert "\n".join(["[校时预览]", *lines]) == fx["upstream_rect"]
    assert "太阳弧 均日弧；" in lines[0]


# ─────────────────────────── 6. 六星点 ───────────────────────────
def test_hermetic_lots_calibre_label_is_six_star_points() -> None:
    """CLS_CALIBRE_LABELS.hermeticLotsReversal：'七星点' → '六星点'（后端只按昼夜反转六个点，福点另由开关定）。"""
    assert snap.build_classical_calibre_line({"hermeticLotsReversal": 0}) == "古典口径（非默认项）：六星点=恒同式(批判本校勘)。"


@needs_upstream
def test_hermetic_lots_calibre_label_tracks_upstream() -> None:
    src = (_UPSTREAM_SRC / "utils/astroAiSnapshot.js").read_text(encoding="utf-8")
    assert "hermeticLotsReversal: { label: '六星点', map: { 0: '恒同式(批判本校勘)' } }" in src


# ─────────────────────────── 7. 汉堡学派：[赤纬接触] / [中点坐标] ───────────────────────────
def test_declination_section_matches_upstream() -> None:
    """buildDeclinationSection（aiExport v59，缺省开、不受汉堡门控）：live 中点响应的 declination 全表与上游逐字节相同；
    declination:false → 不产段；后端给空对象 → 段在、「暂无」行（JS `{}` 为真）。旧代码：无此段。"""
    fx = FIXTURE["germany_default"]
    assert "\n".join(["[赤纬接触]", *_germany_declination_lines(fx["payload"], fx["germany_result"])]) == fx["upstream_decl"]
    assert _germany_declination_lines({**fx["payload"], "declination": False}, fx["germany_result"]) == []
    assert _germany_declination_lines({}, {}) == []
    assert _germany_declination_lines({}, {"declination": {}})[-1] == "容许度内暂无平行 / 反平行"


@pytest.mark.parametrize("case", ["germany_ra", "germany_decl"])
def test_coord_midpoint_section_matches_upstream(case: str) -> None:
    """buildCoordMidpointSection（aiExport v60）：mpCoord=ra|decl 且后端 coordMidpoints.coord 同值 → [中点坐标]（前 80 条），
    与上游逐字节相同；lon / 缺省 / coord 不符 → 不产段。旧代码：无此段、schema 无 mpCoord（MCP 扁平面静默丢）。"""
    fx = FIXTURE[case]
    assert "\n".join(["[中点坐标]", *_germany_coord_midpoint_lines(fx["payload"], fx["germany_result"])]) == fx["upstream_coord"]
    for coord in ("lon", None):
        assert _germany_coord_midpoint_lines({**fx["payload"], "mpCoord": coord}, fx["germany_result"]) == []
    other = "decl" if fx["payload"]["mpCoord"] == "ra" else "ra"
    assert _germany_coord_midpoint_lines({**fx["payload"], "mpCoord": other}, fx["germany_result"]) == []


class _GermanyClient(FakeClient):
    def __init__(self, germany_result: dict) -> None:
        super().__init__()
        self.germany_result = germany_result
        self.bodies: list[dict] = []

    def call(self, endpoint: str, payload: dict) -> dict:
        if endpoint == "/germany/midpoint":
            self.bodies.append(copy.deepcopy(payload))
            return {**super().call(endpoint, payload), **copy.deepcopy(self.germany_result)}
        return super().call(endpoint, payload)


def test_germany_tool_forwards_mp_coord_and_orders_new_sections(tmp_path) -> None:
    """run_tool('germany', mpCoord='decl')：schema 收 mpCoord 并原样下发 /germany/midpoint；段序 = 上游 buildGermanySnapshotText
    六宫框落宫 → 赤纬接触 → 校时预览 → 中点坐标（→ 汉堡学派要素…）。旧 schema 无 mpCoord → MCP 扁平面丢键、段不出。"""
    fx = FIXTURE["germany_decl"]
    client = _GermanyClient(fx["germany_result"])
    settings = _settings(tmp_path)
    service = HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=FakeJsClient())
    payload = {"date": "1990-05-04", "time": "12:30:00", "zone": "+08:00", "lat": "31n14", "lon": "121e30", "hsys": 1, "zodiacal": 0,
               "mpCoord": "decl", "rectifyEvents": [{"date": "2015-06-01", "type": "marriage"}], "agent_confirmed_settings": True}
    result = service.run_tool("germany", payload, save_result=False)
    assert result.ok, result.error
    assert client.bodies and client.bodies[0]["mpCoord"] == "decl"
    titles = re.findall(r"^\[([^\]\n]+)\]$", result.data["snapshot_text"], re.M)
    assert titles.index("中点列表") < titles.index("赤纬接触") < titles.index("校时预览") < titles.index("中点坐标")


# ─────────────────────────── 8. 当前年龄按盘时区 ───────────────────────────
def test_current_age_reads_birth_in_the_chart_zone() -> None:
    """birthInstantMsInZone：出生钟面按本盘时区（±HH:MM）解读。东八区 2000-01-01 08:00 = UTC 00:00；导出时刻 = UTC 2001-01-01 00:00
    （与本机时区无关）。旧代码按本机钟面解读：本机不在东八区时出生瞬时差出时差。无合法 zone 时仍按本机钟面（原样）。"""
    ts_birth = ax._birth_instant_ts_in_zone("2000-01-01 08:00:00", "+08:00")
    assert ts_birth == datetime.fromisoformat("2000-01-01T00:00:00+00:00").timestamp()
    assert ax._birth_instant_ts_in_zone("2000/01/01 08:00:00", "-05:30") == datetime.fromisoformat("2000-01-01T13:30:00+00:00").timestamp()
    local = ax._birth_instant_ts_in_zone("2000-01-01 08:00:00", "8")
    assert local == datetime(2000, 1, 1, 8, 0, 0).timestamp()
