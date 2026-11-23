"""上游 v3.15.0 同步 · 量化盘尾段：[汉堡学派要素]（buildHamburgLines）、时间层 [行运接触] / [图形星历]（挂载 GERMANY_FIELDS 七键）。

三段都由上游原函数出（报告盘图 bundle 的 app-text 通道），skill 只取数与接线；这里钉接线：
① 缺省（classic、没开开关）三段都不出、也不起 node（上游缺省同样没有；skill 旧版无条件附 [虚星参考] 是漏看了 showHamburg 门）；
② 流派 / 差值表 / 戴维森任一介入 → [汉堡学派要素]（差值表行按目标年龄标 ★）；
③ transitAt → 行运盘按该时刻起（/chart + /germany/midpoint）→ [行运接触]；ephemStart/End → /astroextra/ephemeris 逐日 → [图形星历]；
④ 认不出的值报错。
负向对照：runner 不接 _germany_upstream_tail → ②③ 红；门写成恒开 → ① 的「不起 node」红。
"""
from __future__ import annotations

import copy
import re
from pathlib import Path

import pytest
from fakes import FakeClient, FakeJsClient
from test_sync313_western import FIXTURE, _settings

from horosa_skill.config import Settings
from horosa_skill.engine.js_client import HorosaJsEngineClient
from horosa_skill.errors import ToolValidationError
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

PKG_ROOT = Path(__file__).resolve().parents[1]
BASE = {"date": "1990-05-04", "time": "12:30:00", "zone": "+08:00", "lat": "31n14", "lon": "121e30", "hsys": 1, "zodiacal": 0,
        "agent_confirmed_settings": True}


class _Client(FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, dict]] = []

    def call(self, endpoint: str, payload: dict) -> dict:
        self.calls.append((endpoint, copy.deepcopy(payload)))
        if endpoint == "/germany/midpoint":
            return {**super().call(endpoint, payload), **copy.deepcopy(FIXTURE["germany_decl"]["germany_result"])}
        if endpoint == "/astroextra/ephemeris":
            rows = [{"date": f"2026/01/{d:02d}", "positions": {"Mars": {"lon": 100.0 + 0.5 * d}, "Sun": {"lon": 280.0 + d}}} for d in range(1, 31)]
            return {"dailyPositions": rows}
        return super().call(endpoint, payload)


def _service(tmp_path, *, real_texts=True):
    settings = _settings(tmp_path)
    client = _Client()
    js = FakeJsClient()
    if real_texts:
        real = HorosaJsEngineClient(Settings(server_root="http://127.0.0.1:9", runtime_root=tmp_path / "rt", db_path=tmp_path / "x.db",
                                             output_dir=tmp_path / "o"))
        real._candidate_engine_roots = lambda: [PKG_ROOT / "horosa-core-js"]  # type: ignore[method-assign]
        js.run_app_texts = real.run_app_texts
    return HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=js), client


def _titles(text: str) -> list[str]:
    return re.findall(r"^\[([^\]\n]+)\]$", text, re.M)


def _section(text: str, title: str) -> list[str]:
    lines = text.split("\n")
    i = lines.index(f"[{title}]")
    out = []
    for line in lines[i + 1:]:
        if re.match(r"^\[[^\]\n]+\]$", line):
            break
        out.append(line)
    return out


def test_default_call_has_no_upstream_tail_and_spawns_no_node(tmp_path) -> None:
    service, _ = _service(tmp_path, real_texts=False)
    service.js_client.run_app_texts = lambda calls: pytest.fail(f"default germany must not start node: {calls}")
    result = service.run_tool("germany", dict(BASE), save_result=False)
    assert result.ok, result.error
    assert not {"汉堡学派要素", "虚星参考", "戴维森盘", "行运接触", "图形星历"} & set(_titles(result.data["snapshot_text"]))


def test_school_and_diff_list_produce_the_hamburg_section(tmp_path) -> None:
    service, _ = _service(tmp_path)
    uranian = service.run_tool("germany", {**BASE, "school": "uranian"}, save_result=False)
    assert uranian.ok, uranian.error
    titles = _titles(uranian.data["snapshot_text"])
    assert "汉堡学派要素" in titles and "虚星参考" in titles and titles.index("汉堡学派要素") < titles.index("虚星参考")
    assert _section(uranian.data["snapshot_text"], "汉堡学派要素")[0].startswith("流派：")
    diff = service.run_tool("germany", {**BASE, "showDiffList": True, "diffTargetAge": 36, "saKey": "oneDeg"}, save_result=False)
    body = _section(diff.data["snapshot_text"], "汉堡学派要素")
    head = next(line for line in body if line.startswith("差值表"))
    assert "目标年龄36岁" in head and "1°/年" in head
    rows = body[body.index(head) + 1:]
    assert rows and all(line.startswith("  ") and "岁" in line for line in rows[:3])
    assert not any("北交∠南交" in line or "南交∠北交" in line for line in rows)   # 南北交恒对冲，不进差值表


def test_transit_and_graphic_ephemeris_sections(tmp_path) -> None:
    service, client = _service(tmp_path)
    result = service.run_tool("germany", {**BASE, "transitAt": "2026-01-15 08:00", "ephemStart": "2026-01-01", "ephemEnd": "2026-01-30",
                                          "dialBase": 45}, save_result=False)
    assert result.ok, result.error
    text = result.data["snapshot_text"]
    titles = _titles(text)
    assert titles[-2:] == ["行运接触", "图形星历"]
    charts = [p for e, p in client.calls if e in ("/", "/chart")]   # /chart 在 chart 服务上的路由是 "/"
    assert (charts[-1]["date"], charts[-1]["time"]) == ("2026/01/15", "08:00:00")
    mids = [p for e, p in client.calls if e == "/germany/midpoint"]
    assert (mids[-1]["date"], mids[-1]["time"]) == ("2026-01-15", "08:00:00") and "transitAt" not in mids[-1]
    assert _section(text, "行运接触")[0] == "(2026-01-15 08:00 的行运因子落本命单点 / 中点轴;盘基 45°·容许 1°)"
    eph = next(p for e, p in client.calls if e == "/astroextra/ephemeris")
    assert (eph["startDate"], eph["endDate"], eph["includeTransits"]) == ("2026/01/01", "2026/01/30", False)
    assert "Mars" in eph["planets"] and "Moon" not in eph["planets"]   # 页面缺省不含月亮
    gephem = _section(text, "图形星历")
    assert gephem[0].startswith("(2026-01-01 至 2026-01-30;盘基 45°")
    assert any("行运 火" in line for line in gephem[1:]), gephem   # 火星 0.5°/日 扫过本命点


@pytest.mark.parametrize(("key", "bad"), [("dialBase", 30), ("saKey", "fast"), ("transitAt", "2026/1/15"), ("ephemStart", "soon"),
                                          ("diffTargetAge", 200)])
def test_bad_time_layer_values_are_refused(tmp_path, key, bad) -> None:
    service, _ = _service(tmp_path, real_texts=False)
    with pytest.raises(ToolValidationError):
        service.run_tool("germany", {**BASE, key: bad}, save_result=False)
