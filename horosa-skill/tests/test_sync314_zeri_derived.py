"""上游 v3.14.0 同步 · zeri 批：基底技法这一版的修正，在择日派生技法上同样生效（逐个验证，不靠假定）。

上游发布说明「择日：主页面修过的问题一并迁到择日各子页」。skill 的 `<x>zeri` = 本地 / 后端扫描 + 基底技法 runner 铸的展示盘，
扫描引擎与基底页共用同一批 vendored 模块，所以修正「应该」自动跟到——这里把跟到了的每一条钉成值：

- 黄历择吉：九星值日条件与展示盘的「九星值日」行都按日紫白（上游 calendar/huangliDay.js dayNineStarOf，v3.14.0）；
- 奇门择日：展示盘 [全局速览] 的宫号走洛书（上游 dunjia/DunJiaCalc.js patTag，v3.14.0；此前印内部九宫序号）；
- 派生键的段表 = 基底段表 + 择时三段：基底这一版新增的段（别的批加）自动进派生键，不用逐键手抄。

期望值的来源写在各条 docstring；负向对照（把修正改回去）都实跑过。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from test_local_js_tools import make_service, requires_runtime
from test_sync311_divination import RecordingClient, _capture_base_calls, _zeri
from test_sync311_divination import _service as _scan_service

from horosa_skill.config import Settings
from horosa_skill.exports.registry import (
    AI_EXPORT_OPTIONAL_SECTIONS,
    AI_EXPORT_PRESET_SECTIONS,
    ZERI_DERIVED_KEYS,
)
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.testing_payloads import build_sample_payloads

# 洛书九宫数（戴九履一、左三右七、二四为肩、六八为足、五居中）——古法口诀，不取自被测代码。
LUOSHU = {"坎": 1, "坤": 2, "震": 3, "巽": 4, "中": 5, "乾": 6, "兑": 7, "艮": 8, "离": 9}


def _offline_service(tmp_path: Path) -> HorosaSkillService:
    settings = Settings(
        server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs", runtime_root=tmp_path / "runtime",
    )
    return HorosaSkillService(settings, store=MemoryStore(settings))  # 真 JS 引擎；黄历择吉全程不打后端


def _nine_star(values: list[str]) -> dict[str, Any]:
    return {"kind": "group", "joiner": "all", "children": [
        {"kind": "leaf", "type": "nine_star", "params": {"values": values, "matchMode": "any"}}]}


def test_huanglizeri_nine_star_scan_and_display_both_use_day_zibai(tmp_path: Path) -> None:
    """2020 夏至闰期（6-20 … 7-19）是新旧口径分歧的 30 天。手算（日紫白：离夏至最近的甲子换阴遁，遇闰在甲午先换）：
    夏至 2020-06-21；前后甲子日 5-21（早 31 天）/ 7-20（晚 29 天）→ 7-20 起阴遁上元九紫；闰期后半自甲午 6-20 起已逆行，
    所以 7-19 一白、7-10 一白、7-1 一白。旧口径（lunar-javascript getDayNineStar）到 7-19 仍顺行：7-1 六白、7-5 一白。
    同一窗口 6-28 … 7-5 找一白日：新 = 只有 7-1，旧 = 只有 7-5。展示盘（老黄历）与判读行必须同一颗星——所见即所判。
    负向对照：把 vendored calendar/huangliDay.js 的 readNineStar 改回 `lunarForDetail().getDayNineStar()` →
    命中变成 2020-07-05，第一条断言即红（实跑过；horosa-core-js selfcheck 的同名金标同时红）。"""
    service = _offline_service(tmp_path)
    env = service.run_tool(
        "huanglizeri",
        {"date": "2020-07-01", "time": "12:00:00", "zone": "+08:00", "lat": "26n04", "lon": "119e19", "pos": "福州",
         "startDate": "2020-06-28", "endDate": "2020-07-05", "conditions": _nine_star(["一"]), "agent_confirmed_settings": True},
        save_result=False,
    )
    assert env.ok, env.error
    assert [(row["start"], row["end"]) for row in env.data["intervals"]] == [("2020-07-01", "2020-07-01")]
    text = env.data["snapshot_text"]
    assert "九星值日：一白水" in text, "展示盘（基底 huangli）的九星值日行"
    assert "· 设定 九星值日·九星:一 → 实际 九星:一白水 ✓" in text, "命中行的判读树"
    # 换遁处：7-20 甲子九紫（日干支核对：JDN 2459051，(JDN+49)%60=0）。
    turn = service.run_tool(
        "huanglizeri",
        {"date": "2020-07-20", "time": "12:00:00", "zone": "+08:00", "lat": "26n04", "lon": "119e19",
         "startDate": "2020-07-18", "endDate": "2020-07-22", "conditions": _nine_star(["九"]), "agent_confirmed_settings": True},
        save_result=False,
    )
    assert [row["start"] for row in turn.data["intervals"]] == ["2020-07-20"]
    assert "九星值日：九紫火" in turn.data["snapshot_text"]


@pytest.mark.parametrize(("zeri_key", "base_key"), [*ZERI_DERIVED_KEYS, ("huanglizeri", "huangli")])
def test_derived_preset_is_the_base_preset_plus_the_scan_sections(zeri_key: str, base_key: str) -> None:
    """派生键的段表整份取自基底（exports.registry 的循环），所以别的批给基底加段（如七政 / 六壬这一版的新段）时派生键自动多出同一段、
    顺序相同；基底的条件段在派生键上仍是条件段。负向对照：把 registry 里派生循环的 `*AI_EXPORT_PRESET_SECTIONS[_base_key]`
    改成少取末段（`[:-1]`）→ 六个派生键的第一条断言红（实跑过）。"""
    preset, base = AI_EXPORT_PRESET_SECTIONS[zeri_key], AI_EXPORT_PRESET_SECTIONS[base_key]
    assert preset[: len(base)] == base
    tail = preset[len(base):]
    assert tail == (["择吉搜索配置", "择吉条件", "命中日段"] if zeri_key == "huanglizeri" else ["择时搜索配置", "择时条件", "命中时段"])
    assert set(AI_EXPORT_OPTIONAL_SECTIONS.get(base_key, [])) <= set(AI_EXPORT_OPTIONAL_SECTIONS.get(zeri_key, []))
    assert not set(tail) & set(AI_EXPORT_OPTIONAL_SECTIONS.get(zeri_key, [])), "择时三段是必出段"


@pytest.mark.parametrize(
    ("zeri_tool", "base_tool", "scan_endpoint"),
    [("qizhengzeri", "guolao_chart", "/qizhengelectionscan/scan"), ("sanshizeri", "sanshiunited", None)],
)
def test_a_display_knob_declared_on_a_derived_tool_reaches_the_display_chart_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, zeri_tool: str, base_tool: str, scan_endpoint: str | None,
) -> None:
    """基底技法这一版的新显示键（上游 v3.14.0 `ascRaMode`：zeriEmbeddedInputsRegistry / zeriTechniqueParity 把它登记成七政、三式内嵌页的
    显示键，「择日条件不读」）要进择日派生工具时，只需在派生输入模型上声明同名字段：展示盘载荷自动带上，扫描请求 / 扫描口径不带。
    这里用一个临时子类模拟「声明之后」的形状，钉住这条机制（真正的声明由加基底键的那一批做）。
    没声明的键照旧不流进展示盘（`_declared_only`），并在入口提示「不是本技法的参数」。
    负向对照：把 `_run_zeri_backend_tool` 的 base_request 白名单 / `_run_zeri_scan_tool` 的 top_keys 加上 `ascRaMode` → 「扫描不带」断言红；
    把 `_declared_only` 改成只认 NON_TECHNIQUE_KEYS → 「展示盘带上」断言红（都实跑过）。"""
    import dataclasses

    from horosa_skill.engine.registry import TOOL_DEFINITIONS
    from horosa_skill.schemas.tools.base import _unadvertised

    definition = TOOL_DEFINITIONS[zeri_tool]
    one_day = {"startDate": "2028-04-01", "endDate": "2028-04-01"}

    def run() -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
        client = RecordingClient()
        service = _scan_service(tmp_path, client)
        seen = _capture_base_calls(service)
        scan_requests: list[dict[str, Any]] = []
        original_js = service.js_client.run

        def spy_js(tool: str, payload: dict[str, Any], **kwargs: Any) -> Any:
            if tool == "zeri_scan" and payload.get("action") == "scan":
                scan_requests.append(payload)
            return original_js(tool, payload, **kwargs)

        monkeypatch.setattr(service.js_client, "run", spy_js)
        env = service.run_tool(zeri_tool, {**_zeri(zeri_tool, ascRaMode="classic", **one_day), "agent_confirmed_settings": True}, save_result=False)
        assert env.ok, env.error
        scans = client.endpoints(scan_endpoint) if scan_endpoint else scan_requests
        assert scans, "扫描应当真的跑过"
        return [payload for name, payload in seen if name == base_tool][-1], scans, list(env.warnings)

    # 现状（未声明）：不进展示盘，入口说出来。
    display, scans, warnings = run()
    assert "ascRaMode" not in display
    assert any("ascRaMode" in w and "不是本技法的参数" in w for w in warnings)

    # 声明之后：展示盘带上，扫描不带。
    declared = type(f"{definition.input_model.__name__}WithAscRaMode", (definition.input_model,),
                    {"__annotations__": {"ascRaMode": Any}, "ascRaMode": _unadvertised()})
    monkeypatch.setitem(TOOL_DEFINITIONS, zeri_tool, dataclasses.replace(definition, input_model=declared))
    display, scans, warnings = run()
    assert display.get("ascRaMode") == "classic"
    assert not any("ascRaMode" in w for w in warnings)
    for request in scans:
        assert "ascRaMode" not in request and "ascRaMode" not in (request.get("options") or {})
        assert "ascRaMode" not in (request.get("geo") or {})


@requires_runtime
def test_live_qimenzeri_overview_palace_numbers_are_luoshu(tmp_path: Path) -> None:
    """奇门择日的展示盘 [全局速览]：九遁 / 吉格 / 凶格后面括注的宫号是洛书数（上游 v3.14.0 `patTag`：
    `${name}(${palaceName}${LUOSHU_NUM[palaceName]}宫)`；v3.13.2 印的是内部九宫序号且不带「宫」字，如「风遁(巽3)」）。
    期望值 = 洛书口诀表（本文件 LUOSHU），与同段「值符落宫：离9宫」「空亡宫：坎1宫」同一套数。
    负向对照：把 vendored dunjia/DunJiaCalc.js 的 patTag 改回 `${x.name}(${x.palaceName}${x.palace})` → 新格式一条也匹配不到、
    断言红（实跑过）。"""
    service = make_service(tmp_path)
    env = service.run_tool("qimenzeri", {**build_sample_payloads()["qimenzeri"], "agent_confirmed_settings": True}, save_result=False)
    assert env.ok, env.error
    text = env.data["snapshot_text"]
    overview = text[text.index("[全局速览]"): text.index("[盘面要素]")]
    tags = re.findall(r"[一-鿿]+\(([坎坤震巽中乾兑艮离])(\d)宫\)", overview)
    assert len(tags) >= 3, overview
    assert all(int(number) == LUOSHU[palace] for palace, number in tags), tags
    assert not re.findall(r"\([坎坤震巽中乾兑艮离]\d\)", overview), "旧格式（内部序号、无「宫」字）不应再出现"
    assert "九遁：风遁(巽4宫)" in overview and "青龙回首(兑7宫)" in overview  # 2028-04-01 19:01 福州，阳遁九局（样例载荷）
