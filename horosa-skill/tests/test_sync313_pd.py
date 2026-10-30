"""上游 v3.13.0（Horosa-Public 965af0f4）主限法同步：词表 / [主限法设置] / [主限法盘设置] / 恒星相位行 / 值域闸。

权威出处：utils/primaryDirectionSync.js（词表、PD_EXTRA_SETTING_SPECS、PD_GEOMETRY_APPLIES、pdTypeBaselineNote、
pdStarPointText、pdDisplayMethod）、components/direction/AstroDirectMain.js:308-450 buildPrimaryDirectSnapshotText、
components/astro/AstroPrimaryDirectionChart.js:340-372 buildSnapshotText、utils/aiAnalysisContext/primaryDirection.js:171-184。
Python 端口另在开发期用 node 原样执行上游 primaryDirectionSync.js 做过全域差分（59 696 组输入，0 差异）。

每条测试注明负向对照：把对应修复改回 v3.11 口径后该测试红（实际跑过）。
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from fakes import FakeClient, FakeJsClient

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.schemas.tools.base import BirthInput
from horosa_skill.service import HorosaSkillService
from horosa_skill.service.text import pd_zr as Z

BIRTH = {
    "date": "1995-06-03", "time": "05:30:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28",
    "hsys": 0, "zodiacal": 0, "agent_confirmed_settings": True,
}
_UPSTREAM_SYNC = (
    Path(os.environ.get("HOROSA_SOURCE_ROOT") or "/nonexistent")
    / "Horosa-Web" / "astrostudyui" / "src" / "utils" / "primaryDirectionSync.js"
)


class _PdClient(FakeClient):
    """FakeClient，/predict/pd 换成给定行（真实行形：[arc, 迫星, 应星, cat, 日期]）。"""

    def __init__(self, rows: list[list] | None = None) -> None:
        super().__init__()
        self.rows = rows
        self.calls: list[tuple[str, dict]] = []

    def call(self, endpoint: str, payload: dict) -> dict:
        self.calls.append((endpoint, dict(payload)))
        if endpoint == "/predict/pd" and self.rows is not None:
            return {"pd": [list(row) for row in self.rows]}
        return super().call(endpoint, payload)


def _service(tmp_path: Path, client: FakeClient | None = None) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    return HorosaSkillService(settings, client=client or _PdClient(), store=MemoryStore(settings), js_client=FakeJsClient())


def _section(text: str, title: str) -> list[str]:
    head = f"[{title}]\n"
    start = text.index(head) + len(head)
    end = text.find("\n\n[", start)
    return (text[start:] if end < 0 else text[start:end]).splitlines()


def _js_block(src: str, name: str, opener: str, closer: str) -> str:
    start = src.index(f"export const {name} = {opener}")
    return src[start: src.index(closer, start)]


# ── 词表 ─────────────────────────────────────────────────────────────────────────────────────


def test_pd_vocabulary_sizes_and_relabels_follow_v313() -> None:
    """负向对照：把 _PD_TIME_KEY_LABELS / _PD_PROJECTION_LABELS / morinus 配对改回 v3.11（26 项 / 11 种 / ptolemy）→ 红。"""
    assert len(Z._PD_SUPPORTED_TIME_KEYS) == 38 and set(Z._PD_SUPPORTED_TIME_KEYS) == set(Z._PD_TIME_KEY_LABELS)
    assert len(Z._PD_SUPPORTED_PROJECTIONS) == 14 and set(Z._PD_SUPPORTED_PROJECTIONS) == set(Z._PD_PROJECTION_LABELS)
    assert len(Z._PD_METHOD_LABELS) == 13 and len(Z._PD_SUPPORTED_FRAMES) == 12
    # 新增 12 键与改名 4 键（primaryDirectionSync.js:335-374）
    assert Z._primary_direction_time_key_text("KeplerClassic") == "Kepler（经典 · 出生后一日）"
    assert Z._primary_direction_time_key_text("SymbolicWeek") == "Symbolic Week（1° = 7 年）"
    assert Z._primary_direction_time_key_text("VerticalArc") == "Vertical-arc（垂直弧计时）"
    assert Z._primary_direction_time_key_text("Simmonite") == "Simmonite（生日赤经日行）"
    assert Z._primary_direction_time_key_text("AscendantArc") == "Ascendant-arc（上升弧计时）"
    assert Z._PD_PROJECTION_LABELS["placidus_under_pole"] == "Placidus under-pole（极下法）"
    assert Z._PD_PROJECTION_LABELS["koch"] == "Koch（出生地）"
    # :389 morinus 有了自己的投影；后端 perpredict._PD_METHOD_TO_PAIR 同表
    assert Z._PD_METHOD_TO_PAIR["morinus"] == ("morinus", "morinus")
    assert Z._PD_TYPE_LABELS == {0: "黄道（In Zodiaco）", 1: "世俗（In Mundo）", 4: "场平面（Field Plane）"}


@pytest.mark.skipif(not _UPSTREAM_SYNC.is_file(), reason="drift sentinel needs HOROSA_SOURCE_ROOT (upstream checkout)")
def test_pd_vocabulary_sentinel_against_upstream_source() -> None:
    """上游再改 primaryDirectionSync.js 的词表 / 标签 / 登记表 → 红 → 同步 pd_zr 的镜像表。
    负向对照：删掉 _PD_SUPPORTED_TIME_KEYS 里的 SubDuodenary → 红。"""
    src = _UPSTREAM_SYNC.read_text(encoding="utf-8")
    quoted = re.compile(r"'([^']*)'")
    keyed = re.compile(r"(\w+):\s*'([^']*)'")
    assert tuple(quoted.findall(_js_block(src, "SUPPORTED_PD_TIME_KEYS", "[", "];"))) == Z._PD_SUPPORTED_TIME_KEYS
    assert dict(keyed.findall(_js_block(src, "PD_TIME_KEY_LABELS", "{", "};"))) == Z._PD_TIME_KEY_LABELS
    assert tuple(quoted.findall(_js_block(src, "SUPPORTED_PD_PROJECTIONS", "[", "];"))) == Z._PD_SUPPORTED_PROJECTIONS
    assert dict(keyed.findall(_js_block(src, "PD_PROJECTION_LABELS", "{", "};"))) == Z._PD_PROJECTION_LABELS
    assert tuple(quoted.findall(_js_block(src, "SUPPORTED_PD_FRAMES", "[", "];"))) == Z._PD_SUPPORTED_FRAMES
    assert dict(keyed.findall(_js_block(src, "PD_METHOD_LABELS", "{", "};"))) == Z._PD_METHOD_LABELS
    pairs = re.findall(r"(\w+):\s*\['(\w+)',\s*(?:'(\w+)'|null)\]", _js_block(src, "PD_METHOD_TO_PAIR", "{", "};"))
    assert {k: (p, f or None) for k, p, f in pairs} == Z._PD_METHOD_TO_PAIR
    applies = re.findall(r"\[(\d), '(\w+)', '([\w*]+)', (true|false)\]", _js_block(src, "PD_GEOMETRY_APPLIES", "[", "];"))
    assert tuple((int(t), p, f, b == "true") for t, p, f, b in applies) == Z._PD_GEOMETRY_APPLIES
    specs = _js_block(src, "PD_EXTRA_SETTING_SPECS", "[", "\n];")
    assert tuple(re.findall(r"\{ key: '(\w+)'", specs)) == Z._PD_EXTRA_SETTING_KEYS
    assert re.findall(r"key: '\w+', type: '\w+', default: [^,]+, label: '([^']+)'", specs) == [
        spec["label"] for spec in Z._PD_EXTRA_SETTING_SPECS
    ]


# ── [主限法设置]（AstroDirectMain.js:349-411）──────────────────────────────────────────────


def test_pd_settings_lines_explicit_projection_field_plane_geometry_and_registry(tmp_path: Path) -> None:
    """显式弧算法 → 不写「推运方法」；方向类型三值；弧算法带几何口径 + Field Plane 基线注记；框架后接登记表 9 行；
    扩展写面板名。负向对照：恢复旧版「恒写推运方法 / pdtype==1 才世俗 / 原样 join 扩展键 / 无登记表行」→ 红。"""
    text = _service(tmp_path).run_tool(
        "pd",
        {
            **BIRTH, "pdtype": 4, "pdProjection": "koch", "pdGeometry": "classic", "pdTimeKey": "KeplerClassic",
            "pdYearDays": 1, "pdAspectSide": 2, "pdTradConverse": 0, "pdPromAspectLat": 4,
            "pdSignificators": ["Desc", "Stars"], "pdPromissorTypes": ["stars"],
        },
        save_result=False,
    ).data["snapshot_text"]
    assert _section(text, "主限法设置") == [
        "度数换算：Kepler（经典 · 出生后一日）",
        "方向类型：场平面（Field Plane）",
        "向运方向：顺向 Direct",
        "映点迫星：否",
        "界迫星：否",
        # PD_GEOMETRY_APPLIES 有 [4,'koch','*',false]；koch 不在 PD_FIELD_PLANE_DEDICATED_PROJECTIONS
        "弧算法（投影）：Koch（出生地）（经典）（Field Plane 下走核内基线）",
        "盘面宫制（分宫）：Alcabitius",
        "框架：相位主限",
        "相位侧：只出左旋",
        "传统逆向：否",
        "忽略应星黄纬：否",
        "忽略迫星黄纬：否",
        "月亮视差：否",
        "真位置：否",
        "逆向弧用出生前太阳：否",
        "日期年长：365 / 366",
        "相位点黄纬：按宫位",
        "应星扩展：下降 DSC、恒星（王星+比尼）",
        "迫星扩展：恒星",
        "显示界限法：是",
    ]


def test_pd_settings_without_explicit_projection_keeps_method_line_and_dedicated_mundo(tmp_path: Path) -> None:
    """无显式弧算法 → 旧单维决定弧，照写「推运方法」，两维由 pdMethod 推（与后端 _pdResolveProjectionFrame 同表）。
    In Mundo × Ptolemy × Meridian 在 v3.13.0 有专属世俗核（PD_MUNDO_DEDICATED_PTOLEMY_FRAMES）→ 不再标核内基线；
    morinus 推出 Morinus 投影。负向对照：旧 4 投影规则 / 旧 morinus→ptolemy 配对 → 红。"""
    service = _service(tmp_path)
    mundo = _section(
        service.run_tool("pd", {**BIRTH, "pdMethod": "meridian", "pdtype": 1}, save_result=False).data["snapshot_text"],
        "主限法设置",
    )
    assert mundo[0] == "推运方法：Meridian"
    assert "方向类型：世俗（In Mundo）" in mundo and "弧算法（投影）：Ptolemy（半弧）" in mundo
    morinus = _section(
        service.run_tool("pd", {**BIRTH, "pdMethod": "morinus"}, save_result=False).data["snapshot_text"], "主限法设置"
    )
    assert morinus[0] == "推运方法：Morinus"
    assert "弧算法（投影）：Morinus（黄极圈）" in morinus and "盘面宫制（分宫）：Morinus" in morinus
    # 世俗下无专属核的组合照实注明（zodiacal 不在 PD_MUNDO_DEDICATED_PROJECTIONS）
    base = _section(
        service.run_tool("pd", {**BIRTH, "pdtype": 1, "pdProjection": "zodiacal"}, save_result=False).data["snapshot_text"],
        "主限法设置",
    )
    assert "弧算法（投影）：纯黄道（斜升差）（世界主限下走核内基线）" in base and not base[0].startswith("推运方法")


# ── 恒星相位行与显示口径 ──────────────────────────────────────────────────────────────────────


def test_fixed_star_aspect_rows_render_and_survive_core_filter(tmp_path: Path) -> None:
    """FSD_/FSS_（恒星右 / 左相位）行：pdStarPointText 句式 + isPdExtensionPromissorId 放行。
    负向对照：恢复旧正则 ^(HC|FS|LT|PD|PC|MP|RP)_ 与「FS_ → 恒星 X」分支 → 两条相位行被滤掉、id 原样露出 → 红。"""
    rows = [
        [0.5, "FS_Algol_0", "N_Sun_0", "Z", "1996-01-01 00:00:00"],
        [1.0, "FSD_Regulus_60", "N_Moon_0", "Z", "1997-01-01 00:00:00"],
        [1.5, "FSS_Algol_120", "N_Asc_0", "Z", "1998-01-01 00:00:00"],
        [2.0, "FS_Algol_180", "N_MC_0", "Z", "1999-01-01 00:00:00"],
    ]
    text = _service(tmp_path, _PdClient(rows)).run_tool(
        "pd", {**BIRTH, "pdPromissorTypes": ["stars"]}, save_result=False
    ).data["snapshot_text"]
    table = _section(text, "主限法表格")[2:]
    promissors = [line.split(" | ")[1] for line in table]
    assert promissors == ["恒星 大陵五", "恒星 狮心轩辕十四的60度右相位处", "恒星 大陵五的120度左相位处", "恒星 大陵五的180度相位处"]


def test_horosa_legacy_projection_uses_legacy_display_method(tmp_path: Path) -> None:
    """pdDisplayMethod：弧算法选 Horosa原方法 → 列头「赤经」、不按 core 白名单滤行（凯龙不在核内体集）。
    负向对照：只认 pdMethod（旧 AstroDirectMain.js:67）→ 列头 Arc 且凯龙行被滤 → 红。"""
    rows = [[0.25, "N_Chiron_0", "N_Saturn_0", "Z", "1996-01-01 00:00:00"], [1.5, "S_Sun_90", "N_MC_0", "Z", "1997-01-01 00:00:00"]]
    text = _service(tmp_path, _PdClient(rows)).run_tool(
        "pd", {**BIRTH, "pdProjection": "horosa_legacy"}, save_result=False
    ).data["snapshot_text"]
    table = _section(text, "主限法表格")
    assert table[0] == "| 赤经 | 迫星 | 应星 | 日期(UTC) |"
    assert len(table) == 4 and table[2].split(" | ")[1].startswith("凯龙")


# ── [主限法盘设置]（AstroPrimaryDirectionChart.js:361-370）────────────────────────────────────


def test_pdchart_settings_replace_method_with_projection_frame_and_year_days(tmp_path: Path) -> None:
    """7 行：时间选择 / 弧算法（主限法表用）/ 盘面宫制（外圈宫头）/ 度数换算 / 向运方向 / 日期年长 / 当前Arc。
    负向对照：旧 5 行（含「推运方法」）→ 红。"""
    service = _service(tmp_path)
    lines = _section(
        service.run_tool(
            "pdchart",
            {**BIRTH, "datetime": "2031-04-06 09:33:00", "pdProjection": "placidus", "pdFrame": "koch",
             "pdGeometry": "classic", "pdYearDays": 1, "pdTimeKey": "VerticalArc", "direction": "converse"},
            save_result=False,
        ).data["snapshot_text"],
        "主限法盘设置",
    )
    assert lines == [
        "时间选择：2031-04-06 09:33:00",
        "弧算法（主限法表用）：Placidus（半弧严密）（经典）",
        "盘面宫制（外圈宫头）：Koch",
        "度数换算：Vertical-arc（垂直弧计时）",
        "向运方向：逆向 Converse",
        "日期年长：365 / 366",
        "当前Arc：3度0分",
    ]
    # 只给旧单维：两维由 pdMethod 推（外圈宫头 = 后端 _PD_FRAME_HSYS[frame]）
    legacy = _section(
        service.run_tool("pdchart", {**BIRTH, "datetime": "2031-04-06 09:33:00", "pdMethod": "regiomontanus"}, save_result=False)
        .data["snapshot_text"],
        "主限法盘设置",
    )
    assert legacy[1:3] == ["弧算法（主限法表用）：Regiomontanus（改进）", "盘面宫制（外圈宫头）：Regiomontanus"]
    assert legacy[5] == "日期年长：实际天数"


# ── 值域闸与 schema ───────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "bad",
    [
        {"pdtype": 2},  # 后端界推运内部值：快照方向类型表达不了
        {"pdProjection": "Koch"},  # 后端白名单外静默丢弃、改由 pdMethod 推
        {"pdFrame": "koch_house"},
        {"pdTimeKey": "Bogus"},  # 后端回退 Ptolemy
        {"pdGeometry": "Classic"},  # 后端 lower() 认作 classic，上游归一回 improved → 自陈与实算分叉
        {"pdAspectSide": 3},
        {"pdYearDays": 2},
        {"pdIgnoreSigLat": 2},
    ],
)
def test_pd_option_gate_rejects_values_upstream_cannot_express(tmp_path: Path, bad: dict) -> None:
    """负向对照：去掉 _pd_validate_options 里对应一项 → 该参数化用例 ok=True → 红。"""
    client = _PdClient()
    result = _service(tmp_path, client).run_tool("pd", {**BIRTH, **bad}, save_result=False)
    assert result.ok is False and result.error.code == "tool.predictive_invalid_option", bad
    assert result.error.details["field"] == next(iter(bad))
    assert not [c for c in client.calls if c[0] == "/predict/pd"], "rejected before reaching the backend"


def test_pd_registry_keys_are_declared_and_forwarded(tmp_path: Path) -> None:
    """十键声明在 BirthInput（MCP 扁平面按名可传）；pdtype 声明 int → "4" 归一成 4 再发后端（后端 `in (0,1,4)` 严格比较，
    vendored 实例实测字符串 '4' 落进旧 flatlib 分支）。负向对照：pdtype 回到 Any → 发出去的是 '4' → 红。"""
    assert set(Z._PD_EXTRA_SETTING_KEYS) <= set(BirthInput.model_fields)
    client = _PdClient()
    _service(tmp_path, client).run_tool(
        "pd", {**BIRTH, "pdtype": "4", "pdYearDays": "1", "pdGeometry": "classic", "pdTruePosition": 1}, save_result=False
    )
    sent = [payload for endpoint, payload in client.calls if endpoint == "/predict/pd"][-1]
    assert sent["pdtype"] == 4 and sent["pdYearDays"] == 1 and sent["pdGeometry"] == "classic" and sent["pdTruePosition"] == 1
