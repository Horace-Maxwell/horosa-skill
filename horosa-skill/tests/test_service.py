import json
import re
import zipfile
from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.exports.parser import parse_export_content
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.errors import ToolTransportError, ToolValidationError
from horosa_skill.knowledge import build_knowledge_registry
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import TOOL_EXPORT_TECHNIQUE_MAP, HorosaSkillService, _java_chart_payload, _java_chart_payload_candidates
from horosa_skill.testing_payloads import build_sample_payloads
from fakes import (
    CaptureClient,
    FakeClient,
    FakeJsClient,
    sample_final_ai_report,
)


def test_liureng_tool_description_prevents_manual_agent_calculation() -> None:
    description = TOOL_DEFINITIONS["liureng_gods"].description

    assert "当前" in description or "current-time" in description
    assert "do not hand-calculate" in description
    assert "shell/Python" in description
    assert "Xingque-compatible" in description


class FakeRuntimeManager:
    def __init__(self, *, degraded: bool = False, cooldown: float = 0.0) -> None:
        self.started = 0
        self.degraded = degraded
        self.cooldown = cooldown

    def start_local_services(self, *, wait_seconds: float | None = None) -> dict[str, object]:
        self.started += 1
        return {"ok": True, "already_running": False, "degraded": self.degraded}

    def java_backend_cooldown_remaining(self) -> float:
        return self.cooldown


class ProbeClient(FakeClient):
    def __init__(self, *, probe_ok: bool) -> None:
        super().__init__()
        self.probe_ok = probe_ok
        self.probe_calls = 0

    def probe(self, endpoint: str = "/common/time", payload: dict | None = None) -> bool:
        self.probe_calls += 1
        return self.probe_ok


class OldBuildShenShuClient(FakeClient):
    """Simulates an OLDER 星阙 chart-service build: 神数 /{key}/pan returns structured `basic` data but
    NO `snapshot` field (the build predates the engine's build_snapshot()). The skill must surface this
    as a clean transport error rather than a silently-empty reading."""

    def call(self, endpoint: str, payload: dict) -> dict:
        if endpoint.endswith("/pan") and endpoint.lstrip("/").split("/")[0] in {
            "shaozi", "tieban", "fendjing", "beiji", "nanji", "chunzi", "xianqin", "cetian", "qizhengkin",
            "wangji", "wuzhao", "taixuan", "jingjue", "shenyishu",
        }:
            return {"source": "kinastro", "engine": "kinastro-old", "basic": {"year_gz": "戊寅"}}  # no `snapshot`
        return super().call(endpoint, payload)


def test_shenshu_old_backend_without_snapshot_errors_clearly(tmp_path) -> None:
    settings = Settings(server_root="http://127.0.0.1:9999", db_path=tmp_path / "m.db", output_dir=tmp_path / "runs")
    service = HorosaSkillService(settings, client=OldBuildShenShuClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    result = service.run_tool("shaozi", {"date": "1998-02-20", "time": "20:48:00", "gender": 1}, save_result=False)
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "transport.shenshu_snapshot_unavailable"
    assert "过旧" in result.error.message or "snapshot" in result.error.message.lower()


def test_shenshu_unparseable_date_errors_clearly(tmp_path) -> None:
    settings = Settings(server_root="http://127.0.0.1:9999", db_path=tmp_path / "m.db", output_dir=tmp_path / "runs")
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    result = service.run_tool("wuzhao", {"date": "not-a-date", "time": "20:48:00"}, save_result=False)
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "tool.shenshu_bad_date"


def test_service_tool_list_exposes_input_contracts(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    tools = {tool["name"]: tool for tool in service.list_tools()}

    assert tools["solarreturn"]["input_contract"]["required_for_real_call"] == [
        "date",
        "time",
        "zone",
        "lat",
        "lon",
        "datetime",
        "dirZone",
        "dirLat",
        "dirLon",
    ]
    assert tools["pd"]["input_contract"]["target_fields"]["pdaspects"].startswith("纳入表格")
    assert "主限法盘星体表格" in tools["pdchart"]["input_contract"]["output_contract"]


def test_service_tool_call_persists_memory(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    service = HorosaSkillService(settings, client=FakeClient(), store=store, js_client=FakeJsClient())

    result = service.run_tool(
        "chart",
        {"date": "1990-01-01", "time": "12:00", "zone": "8", "lat": "31n14", "lon": "121e28"},
    )

    assert result.ok is True
    assert result.memory_ref is not None
    assert result.data["export_snapshot"]["technique"]["key"] == "astrochart"
    assert result.data["export_snapshot"]["sections"][0]["title"] == "起盘信息"
    assert "宫位宫头" in result.data["export_snapshot"]["selected_sections"]
    assert "星与虚点" in result.data["export_snapshot"]["selected_sections"]
    assert "| 第八宫 | " in result.data["export_snapshot"]["export_text"]   # [宫位宫头] 宫位|宫头 GFM 表（astroAiSnapshot.js:521-533）
    assert "日 (8th; 12R)" in result.data["export_snapshot"]["export_text"]
    assert "福点 (8th; -)" in result.data["export_snapshot"]["export_text"]
    queried = store.query_runs(tool="chart")
    assert len(queried) == 1


def test_invalid_tool_payload_returns_agent_recovery_prompt(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    with pytest.raises(ToolValidationError) as exc_info:
        service.run_tool("chart", {"agent_confirmed_settings": True}, save_result=False)

    assert exc_info.value.code == "tool.invalid_payload"
    recovery = exc_info.value.details["agent_recovery"]
    assert recovery["must_ask_user"] is True
    assert "调用 `chart` 前需要先确认" in recovery["prompt_to_user"]
    assert any(item["field"] == "date/time/place" for item in recovery["ask_if_missing"])


def test_service_starts_runtime_before_first_remote_call_when_probe_fails(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    runtime_manager = FakeRuntimeManager()
    client = ProbeClient(probe_ok=False)
    service = HorosaSkillService(
        settings,
        client=client,
        store=MemoryStore(settings),
        js_client=FakeJsClient(),
        runtime_manager=runtime_manager,
    )

    result = service.run_tool(
        "chart",
        {"date": "1990-01-01", "time": "12:00", "zone": "8", "lat": "31n14", "lon": "121e28"},
        save_result=False,
    )

    assert result.ok is True
    assert runtime_manager.started == 1
    assert client.probe_calls == 1


def test_service_skips_runtime_restart_after_remote_runtime_is_confirmed(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    runtime_manager = FakeRuntimeManager()
    client = ProbeClient(probe_ok=False)
    service = HorosaSkillService(
        settings,
        client=client,
        store=MemoryStore(settings),
        js_client=FakeJsClient(),
        runtime_manager=runtime_manager,
    )

    for _ in range(2):
        result = service.run_tool(
            "chart",
            {"date": "1990-01-01", "time": "12:00", "zone": "8", "lat": "31n14", "lon": "121e28"},
            save_result=False,
        )
        assert result.ok is True

    assert runtime_manager.started == 1
    assert client.probe_calls == 1


def test_chart_classical_sections_emit_offline(tmp_path) -> None:
    # 星阙 v2.6.7 古典占星 (hermetic)：FakeClient 的 /astroextra/analysis 替身提供派生格局后，chart 导出应稳定
    # 含 [古典] (buildClassicalSection ← /chart objects: Melothesia 等) 与 [古典格局]
    # (buildClassicalAnalysisSection ← analyze_chart: 护卫/优势相位/传光/逐题主星/偶然尊贵/Almuten/分布/气质)。
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    result = service.run_tool(
        "chart",
        {"date": "1990-01-01", "time": "12:00", "zone": "+08:00", "lat": "31n14", "lon": "121e28"},
        save_result=False,
    )
    assert result.ok is True, result.error
    snapshot = result.data["snapshot_text"]
    assert "[古典]" in snapshot and "[古典格局]" in snapshot
    # [古典]: FakeClient 各曜带 sign 但无逐曜古典状态字段，故离线仅 身体部位(Melothesia) 恒在；
    # 逐曜古典状态/围攻/围绕 等富集内容由 live 测试 + catalog fixture 覆盖。
    assert "身体部位(Melothesia)" in snapshot
    # [古典格局]: 桩数据派生的逐键内容，逐条核对建造器输出形态。
    for marker in (
        "护卫：金 护卫 日",                 # doryphory
        "优势相位：火(牡羊) 凌驾 金(金牛)·四分",   # overcoming
        "度数围攻：水 被 火/土 度数围攻",        # besieging
        "传光：月 自 土 传光予 木",             # translation
        "聚光：土 聚 日、月 之光",              # collection
        "不合意：日 与 土 不合意",              # aversion
        "交点弯曲：月 交点弯曲（北弯）",          # bending
        "空亡：月 空亡（本座内不再成相）",        # void
        "阻止：火 阻止 金→木 入相",             # prohibition
        "挫败：金 挫败（木 先成相 土）",          # frustration
        "收回：水 收回（趋留撤离 日）",          # refranation
        "婚配（7宫·自然象征金）主星火",          # topicAlmuten
        "偶然尊贵",
        "土 12（角宫+5·行速+2·自由光+5）",      # accidentalDignity
        "Almuten 总主：土",                   # almutem
        "分布权重",
        "气质评估",
    ):
        assert marker in snapshot, marker
    export = result.data.get("export_snapshot") or {}
    detected = export.get("section_titles_detected") or []
    assert "古典" in detected and "古典格局" in detected
    assert export.get("unknown_detected_sections") == []


def test_liureng_headless_export_includes_courses_transmissions_without_mongodb_claims(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    client = CaptureClient()
    service = HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool(
        "liureng_gods",
        {
            "date": "2028-04-06",
            "time": "09:33:00",
            "zone": "+08:00",
            "lat": "31n13",
            "lon": "121e28",
            "gpsLat": 31.2167,
            "gpsLon": 121.4667,
            "after23NewDay": False,
        },
        query_text="请用大六壬分析这件事",
    )

    assert result.ok is True
    assert result.memory_ref is not None
    export_text = result.data["export_snapshot"]["export_text"]
    assert "四课" in result.data["export_snapshot"]["selected_sections"]
    assert "三传" in result.data["export_snapshot"]["selected_sections"]
    assert "一课：地盘=甲，天盘=申，贵神=青龙" in export_text
    assert "课式：涉害课" in export_text
    assert "MongoDB" not in export_text
    assert "7897" not in export_text
    liureng_call = next(payload for endpoint, payload in client.calls if endpoint == "/liureng/gods")
    assert "gpsLat" not in liureng_call
    assert "gpsLon" not in liureng_call
    chart_call = next(payload for endpoint, payload in client.calls if endpoint in {"/chart", "/"})
    assert chart_call["gpsLat"] == 31.2167
    assert chart_call["gpsLon"] == 121.4667

    template = service.report_template({"run_id": result.memory_ref.run_id, "tool_name": "liureng_gods"})
    brief_text = json.dumps(template["conversation_brief"], ensure_ascii=False)
    contract_text = json.dumps(template["targeted_analysis_contract"], ensure_ascii=False)
    assert "不要把空字段或缺失章节解释成需要 MongoDB" in brief_text
    assert "Never claim that Horosa Skill requires MongoDB" in contract_text


def test_service_memory_query_and_show(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    service = HorosaSkillService(settings, client=FakeClient(), store=store, js_client=FakeJsClient())

    result = service.run_tool(
        "chart",
        {"date": "1990-01-01", "time": "12:00", "zone": "8", "lat": "31n14", "lon": "121e28", "name": "Horosa Smoke"},
    )

    assert result.memory_ref is not None
    query_result = service.query_memory({"tool": "chart", "entity": "Horosa Smoke", "limit": 5})
    assert query_result["ok"] is True
    assert query_result["count"] == 1
    assert query_result["results"][0]["run_id"] == result.memory_ref.run_id

    show_result = service.show_memory({"run_id": result.memory_ref.run_id})
    assert show_result["ok"] is True
    assert show_result["result"]["run_id"] == result.memory_ref.run_id

    text_query = service.query_memory({"text": "Horosa Smoke", "limit": 5})
    assert text_query["ok"] is True
    assert text_query["count"] == 1
    assert text_query["results"][0]["run_id"] == result.memory_ref.run_id


def test_local_tool_call_always_attaches_complete_export_contract(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool(
        "qimen",
        {"date": "2026-04-04", "time": "21:18", "zone": "+08:00", "lat": "31n14", "lon": "121e28"},
        save_result=False,
    )

    assert result.ok is True
    assert result.data["export_snapshot"]["technique"]["key"] == "qimen"
    assert result.data["export_snapshot"]["format_source"] == "snapshot_parser"
    # v13（上游 v3.9.x 重同步）：段序改为**逐字镜像上游** preset —— 八宫克应 回到上游位置（八宫详解 之后），
    # 末尾新增条件段 日家占方（古籍金函系）。段序不是装饰：selected_sections 决定导出正文的出段顺序。
    assert result.data["export_snapshot"]["selected_sections"] == [
        "起盘信息", "盘型", "全局速览", "盘面要素", "奇门演卦", "八宫详解", "八宫克应", "九宫方盘",
        "旺相休囚死·月令能量", "六害总览", "化解方案", "八门化气大阵", "用神分论", "财富七要", "事业七要",
        "恋爱姻缘", "孤辰寡宿", "日家占方（古籍金函系）",
    ]
    assert any(section["title"] == "奇门演卦" for section in result.data["export_snapshot"]["sections"])
    assert any(section["title"] == "化解方案" for section in result.data["export_snapshot"]["sections"])


def test_qimen_fails_loudly_when_ken_returns_failure_envelope(tmp_path) -> None:
    """Regression: ken endpoints return HTTP 200 with ``{"ResultCode": -1, "Result": "..."}`` on
    failure. Because that envelope is still a dict, ``_call_remote`` does not raise. It must NOT be
    forwarded to the JS layer (which would silently fall back to its local scaffold compute and
    produce a chart that does NOT match 星阙). ken is the sole compute authority, so a failed ken
    response has to surface as a loud ``tool.ken_compute_failed`` error. ``_require_ken_pan`` guards
    qimen/taiyi/jinkou identically; qimen exercises the path here."""

    class KenFailureClient(FakeClient):
        def call(self, endpoint: str, payload: dict) -> dict:
            if endpoint == "/qimen/pan":
                return {"ResultCode": -1, "Result": "qimen calculation failed"}
            return super().call(endpoint, payload)

    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=KenFailureClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool(
        "qimen",
        {"date": "2026-04-04", "time": "21:18", "zone": "+08:00", "lat": "31n14", "lon": "121e28"},
        save_result=False,
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "tool.ken_compute_failed"
    assert result.error.details.get("engine") == "kinqimen"


def test_knowledge_registry_and_read_are_queryable_and_persisted(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    service = HorosaSkillService(settings, client=FakeClient(), store=store, js_client=FakeJsClient())

    registry = service.run_tool("knowledge_registry", {"domain": "astro"}, save_result=False)
    assert registry.ok is True
    assert registry.data["domains"][0]["domain"] == "astro"
    assert any(category["name"] == "planet" for category in registry.data["domains"][0]["categories"])

    liureng = service.run_tool("knowledge_read", {"domain": "liureng", "category": "shen", "key": "子"}, save_result=True)
    assert liureng.ok is True
    assert liureng.memory_ref is not None
    assert liureng.data["title"] == "神后子神"
    assert "类象" in liureng.data["rendered_text"]

    qimen = service.run_tool("knowledge_read", {"domain": "qimen", "category": "door", "key": "休门"}, save_result=False)
    assert qimen.ok is True
    assert qimen.data["key"] == "休门"
    assert "休养" in qimen.data["rendered_text"]

    astro = service.run_tool(
        "knowledge_read",
        {"domain": "astro", "category": "aspect", "aspect_degree": 90, "object_a": "Sun", "object_b": "Jupiter"},
        save_result=False,
    )
    assert astro.ok is True
    assert astro.data["title"].startswith("太阳 - 木星")
    assert "相位角：90°" in astro.data["tips"]

    queried = store.query_runs(tool="knowledge_read", include_payload=True)
    assert len(queried) == 1
    payload = queried[0]["artifacts"][0]["payload"]
    assert payload["data"]["domain"] == "liureng"
    assert payload["data"]["category"] == "shen"


def test_knowledge_registry_bundle_has_expected_domains() -> None:
    registry = build_knowledge_registry()
    # v0.28.0：3 个 hover 域之外新增 21 个方法论手册域（helpdocs 自动发现）——断超集不断全集，
    # 手册域自己的契约在 tests/test_knowledge_helpdocs.py。
    domains = [item["domain"] for item in registry["domains"]]
    assert {"astro", "liureng", "qimen"} <= set(domains)
    assert len(domains) >= 24


def test_phase2_tools_attach_export_contracts(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    guolao = service.run_tool(
        "guolao_chart",
        {"date": "2028/04/06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
        save_result=False,
    )
    hellen = service.run_tool(
        "hellen_chart",
        {"date": "2028/04/06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
        save_result=False,
    )
    tongshe = service.run_tool("tongshefa", {}, save_result=False)
    sanshi = service.run_tool(
        "sanshiunited",
        {"date": "2028-04-06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
        save_result=False,
    )
    suzhan = service.run_tool(
        "suzhan",
        {"date": "2028/04/06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
        save_result=False,
    )
    germany = service.run_tool(
        "germany",
        {"date": "2028/04/06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
        save_result=False,
    )
    otherbu = service.run_tool(
        "otherbu",
        {"date": "2028/04/06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "question": "测试"},
        save_result=False,
    )
    firdaria = service.run_tool(
        "firdaria",
        {"date": "2028/04/06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
        save_result=False,
    )
    decennials = service.run_tool(
        "decennials",
        {"date": "2028/04/06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
        save_result=False,
    )
    sixyao = service.run_tool(
        "sixyao",
        {"date": "2028/04/06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gua_code": "111111", "changed_code": "101010"},
        save_result=False,
    )

    assert guolao.ok is True
    assert guolao.data["export_snapshot"]["technique"]["key"] == "guolao"
    assert hellen.ok is True
    # 上游 v50 把这一族按出盘页面拆键（ASTRO_LIKE_EXPORT_KEYS）：希腊盘有自己的 `hellenastro`。
    assert hellen.data["export_snapshot"]["technique"]["key"] == "hellenastro"
    assert tongshe.ok is True
    assert tongshe.data["export_snapshot"]["technique"]["key"] == "tongshefa"
    assert sanshi.ok is True
    assert sanshi.data["export_snapshot"]["technique"]["key"] == "sanshiunited"
    assert suzhan.ok is True
    assert suzhan.data["export_snapshot"]["technique"]["key"] == "suzhan"
    assert germany.ok is True
    assert germany.data["export_snapshot"]["technique"]["key"] == "germany"
    assert otherbu.ok is True
    assert otherbu.data["export_snapshot"]["technique"]["key"] == "otherbu"
    assert firdaria.ok is True
    assert firdaria.data["export_snapshot"]["technique"]["key"] == "firdaria"
    assert decennials.ok is True
    assert decennials.data["export_snapshot"]["technique"]["key"] == "decennials"
    assert sixyao.ok is True
    assert sixyao.data["export_snapshot"]["technique"]["key"] == "sixyao"


def test_sixyao_time_based_gua_varies_with_time_and_is_deterministic() -> None:
    # 回归 #12: lines 空时曾写死返回 既济(101010)→益(100011)，与起卦时间无关。以时起卦 = vendored 上游
    # buildTimeGua（GuaZhanMain.js:74-98，年支序 + 农历月数 + 农历日数 + 时柱支序）：不同时间不同卦、恰一动爻、
    # 同输入确定一致、不再是写死的既济→益。（sync311 wave 3：Python 手写式 _time_based_gua_lines 已删——它取
    # 月/日地支序 + 钟表时辰，与上游起出不同的卦；本条改钉 JS 真函数，值级对拍见 test_sync311_divination_w3.py。）
    import subprocess

    from horosa_skill.service import _derive_changed_gua_code, _derive_gua_code

    cases = [
        {"year": "癸卯", "monthInt": 11, "dayInt": 1, "time": "甲子"},
        {"year": "甲辰", "monthInt": 5, "dayInt": 20, "time": "丁卯"},
        {"year": "乙巳", "monthInt": 2, "dayInt": 3, "time": "辛酉"},
        {"year": "丙午", "monthInt": 5, "dayInt": 9, "time": "丙午"},
        {"year": "丙午", "monthInt": 11, "dayInt": 23, "time": "丙子"},
    ]
    module = Path(__file__).resolve().parents[1] / "horosa-core-js" / "src" / "vendor" / "guazhan" / "GuaZhanMain.js"
    script = (
        "import(process.argv[1]).then((m) => { const cs = JSON.parse(process.argv[2]);"
        " process.stdout.write(JSON.stringify(cs.map((n) => m.buildTimeGua(n).yao.map((y) => ({ value: y.value, change: y.change }))))); });"
    )

    def cast(items: list[dict]) -> list[list[dict]]:
        from node_esm import run_node_esm  # Path → file:// URL（Windows ESM loader 不认裸盘符路径）

        return json.loads(run_node_esm(script, module, json.dumps(items, ensure_ascii=False)))

    combos = set()
    for lines in cast(cases):
        assert len(lines) == 6
        assert all(line["value"] in (0, 1) for line in lines)
        assert sum(1 for line in lines if line["change"]) == 1  # 以时起卦恰一个动爻
        combos.add((_derive_gua_code(lines), _derive_changed_gua_code(lines)))
    assert len(combos) >= 4, combos  # 不再固定单一卦象 (修复前为 1)
    assert ("101010", "100011") not in combos  # 写死的 既济→益 不再出现
    again = cast([cases[3], cases[3]])
    assert _derive_gua_code(again[0]) == _derive_gua_code(again[1])


@pytest.mark.parametrize("tool_name", ["chart", "guolao_chart"])
def test_service_normalizes_human_friendly_birth_fields_before_remote_calls(tmp_path, tool_name: str) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    client = CaptureClient()
    service = HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool(
        tool_name,
        {
            "date": "1995-06-03",
            "time": "5:30",
            "zone": "8",
            "lat": "31.2167",
            "lon": "121.4667",
            "ad": 1,
        },
        save_result=False,
    )

    assert result.ok is True
    assert result.input_normalized["zone"] == "+08:00"
    assert result.input_normalized["lat"] == "31n13"
    assert result.input_normalized["lon"] == "121e28"
    assert result.input_normalized["gpsLat"] == pytest.approx(31.2167)
    assert result.input_normalized["gpsLon"] == pytest.approx(121.4667)
    assert client.calls, "expected remote client call to be captured"
    endpoint, remote_payload = client.calls[0]
    assert endpoint == "/"
    assert result.input_normalized["date"] == "1995-06-03"
    assert remote_payload["date"] == "1995/06/03"
    assert remote_payload["zone"] == "+08:00"
    assert remote_payload["lat"] == "31n13"
    assert remote_payload["lon"] == "121e28"
    assert remote_payload["gpsLat"] == pytest.approx(31.2167)
    assert remote_payload["gpsLon"] == pytest.approx(121.4667)


def test_service_sends_slash_dates_to_python_chart_server_without_changing_input(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    client = CaptureClient()
    service = HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool(
        "chart",
        {
            "date": "2028/04/06",
            "time": "09:33",
            "zone": "+00:00",
            "lat": "41n26",
            "lon": "174w30",
            "gpsLat": -41.433333,
            "gpsLon": -174.5,
        },
        save_result=False,
    )

    assert result.ok is True
    assert result.input_normalized["date"] == "2028-04-06"
    chart_payloads = [call_payload for endpoint, call_payload in client.calls if endpoint == "/"]
    assert chart_payloads
    assert chart_payloads[0]["date"] == "2028/04/06"


def test_java_chart_payload_slashes_datetime_only_for_chart_family() -> None:
    chart_payload = _java_chart_payload(
        "/chart",
        {"date": "2028-04-06", "datetime": "2031-04-06 09:33:00", "time": "09:33:00"},
    )
    assert chart_payload["date"] == "2028/04/06"
    assert chart_payload["datetime"] == "2031/04/06 09:33:00"

    nongli_payload = _java_chart_payload("/nongli/time", {"date": "2028-04-06"})
    assert nongli_payload["date"] == "2028-04-06"


def test_java_chart_payload_candidates_cover_windows_runtime_variants() -> None:
    candidates = _java_chart_payload_candidates(
        "/chart",
        {
            "date": "2028-04-06",
            "time": "09:33:00",
            "zone": "+08:00",
            "lat": "41n26",
            "lon": "174w30",
            "gpsLat": -41.433333,
            "gpsLon": -174.5,
        },
    )

    assert {
        "date": "2028/04/06",
        "time": "09:33:00",
        "zone": "+08:00",
        "lat": "41n26",
        "lon": "174w30",
        "gpsLat": -41.433333,
        "gpsLon": -174.5,
    } in candidates
    assert {
        "date": "2028-04-06",
        "time": "09:33:00",
        "zone": "+08:00",
        "lat": "41n26",
        "lon": "174w30",
        "gpsLat": -41.433333,
        "gpsLon": -174.5,
    } in candidates
    assert {
        "date": "2028/04/06",
        "time": "09:33:00",
        "zone": "8",
        "lat": "41n26",
        "lon": "174w30",
        "gpsLat": -41.433333,
        "gpsLon": -174.5,
    } in candidates
    assert {
        "date": "2028-04-06",
        "time": "09:33:00",
        "zone": "8",
        "lat": "41n26",
        "lon": "174w30",
    } in candidates
    assert {
        "date": "2028/04/06",
        "time": "09:33:00",
        "zone": "+08:00",
        "gpsLat": -41.433333,
        "gpsLon": -174.5,
    } in candidates
    assert {
        "date": "2028/04/06",
        "time": "09:33:00",
        "zone": "+08:00",
        "lat": -41.433333,
        "lon": -174.5,
        "gpsLat": -41.433333,
        "gpsLon": -174.5,
    } in candidates
    # v0.41.1：重试阶梯只许换写法，不许换地点——任何候选都不能把西经改成东经（旧阶梯有 abs(gpsLon) 两族，纽约会被算成中亚还报成功）。
    for candidate in candidates:
        for key in ("gpsLon", "lon"):
            value = candidate.get(key)
            if isinstance(value, (int, float)):
                assert value < 0, f"candidate flipped the longitude sign: {candidate}"


def test_calendar_month_snapshot_sections_and_cross_month_filter(tmp_path) -> None:
    # 黄历/万年历：起盘信息+当月月历(GFM 表)+选中日详情+方法说明；跨月补位项不入当月表。
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool(
        "calendar_month",
        {"date": "2028-04-06", "zone": "+08:00", "lon": "120e00", "day": "2028-04-06", "agent_confirmed_settings": True},
        save_result=False,
    )

    assert result.ok is True
    snapshot = result.data["snapshot_text"]
    for head in ("[起盘信息]", "[当月月历]", "[选中日详情]", "[方法说明]"):
        assert head in snapshot
    assert "| 公历 | 星期 | 农历 | 日干支 | 节气/朔望 |" in snapshot
    assert "清明 2028-04-04 16:02:11" in snapshot
    assert "朔 12:20:33" in snapshot
    # 跨月补位（2028-05-01）不得混入当月月历表。
    assert "05-01" not in snapshot
    # 选中日详情字段落位。
    assert "农历：戊申年三月初六" in snapshot
    assert "年柱口径" in snapshot
    export_format = result.data.get("export_snapshot") or {}
    assert export_format.get("technique", {}).get("key") == "calendar"
    assert export_format.get("missing_selected_sections") in (None, [])
    assert export_format.get("unknown_sections") in (None, [])


def test_predictive_common_sections_appended_for_predictive_family(tmp_path) -> None:
    # 星运族公共段：当前时点(导出时刻+盘主年龄) + 方法说明(机理与读法) 在统一出口追加。
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool(
        "profection",
        {
            "date": "1995-06-03",
            "time": "05:30:00",
            "zone": "+08:00",
            "lat": "31n13",
            "lon": "121e28",
            "datetime": "2026-07-12 12:00:00",
            "agent_confirmed_settings": True,
        },
        save_result=False,
    )

    assert result.ok is True
    snapshot = result.data["snapshot_text"]
    assert "[方法说明]" in snapshot
    assert "小限(年限)" in snapshot
    # 上游 v3.11（aiExport.js:641-645 / predictiveAiSnapshot.js）：目标时刻型 5 法只出 [方法说明]、preset 无 [当前时点]。
    assert "[当前时点]" not in snapshot
    agepoint = service.run_tool(
        "agepoint",
        {"date": "1995-06-03", "time": "05:30:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "agent_confirmed_settings": True},
        save_result=False,
    )
    agepoint_snapshot = agepoint.data["snapshot_text"]
    assert "[当前时点]" in agepoint_snapshot and "[方法说明]" in agepoint_snapshot
    assert "导出时刻：" in agepoint_snapshot
    assert "盘主当前年龄：" in agepoint_snapshot
    # 非星运技法不受影响（零变化）。
    nongli = service.run_tool(
        "nongli_time",
        {"date": "2028-04-06", "time": "09:33:00", "zone": "+08:00", "lon": "121e28", "agent_confirmed_settings": True},
        save_result=False,
    )
    assert "[方法说明]" not in (nongli.data.get("snapshot_text") or "")


def test_nongli_payload_candidates_keep_validated_payload_first_then_legacy_slash_fallback() -> None:
    candidates = _java_chart_payload_candidates(
        "/nongli/time",
        {
            "date": "2028-04-06",
            "time": "09:03:00",
            "zone": "+08:00",
            "lat": "31n13",
            "lon": "121e28",
            "gpsLat": 31.2167,
            "gpsLon": 121.4667,
        },
    )

    assert candidates[0] == {
        "date": "2028-04-06",
        "time": "09:03:00",
        "zone": "+08:00",
        "lat": "31n13",
        "lon": "121e28",
        "gpsLat": 31.2167,
        "gpsLon": 121.4667,
    }
    assert {
        "date": "2028/04/06",
        "time": "09:03:00",
        "zone": "+08:00",
        "lat": "31n13",
        "lon": "121e28",
        "gpsLat": 31.2167,
        "gpsLon": 121.4667,
    } in candidates
    assert {
        "date": "2028/04/06",
        "time": "09:03:00",
        "zone": "8",
        "lat": "31n13",
        "lon": "121e28",
        "gpsLat": 31.2167,
        "gpsLon": 121.4667,
    } in candidates
    assert {
        "date": "2028/04/06",
        "time": "09:03:00",
        "zone": "+08:00",
        "gpsLat": 31.2167,
        "gpsLon": 121.4667,
    } in candidates


def test_service_retries_chart_payload_variants_after_backend_param_error(tmp_path) -> None:
    class RetryChartClient(FakeClient):
        def __init__(self) -> None:
            super().__init__()
            self.calls: list[tuple[str, dict]] = []

        def call(self, endpoint: str, payload: dict) -> dict:
            self.calls.append((endpoint, dict(payload)))
            if endpoint == "/" and payload.get("zone") != "8":
                raise ToolTransportError(
                    "backend rejected payload",
                    code="transport.http_error",
                    details={"endpoint": endpoint, "status_code": 500, "body": '{"ResultCode":200001,"Result":"param error"}'},
                )
            return super().call(endpoint, payload)

    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    client = RetryChartClient()
    service = HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool(
        "chart",
        {"date": "2026-04-04", "time": "15:58:35", "zone": "+08:00", "lat": "26n04", "lon": "119e19"},
        save_result=False,
    )

    assert result.ok is True
    assert result.input_normalized["zone"] == "+08:00"
    assert any(payload.get("zone") == "8" for endpoint, payload in client.calls if endpoint == "/")


def test_service_retries_nongli_time_legacy_payload_after_backend_param_error(tmp_path) -> None:
    class RetryNongliClient(FakeClient):
        def __init__(self) -> None:
            super().__init__()
            self.calls: list[tuple[str, dict]] = []

        def call(self, endpoint: str, payload: dict) -> dict:
            self.calls.append((endpoint, dict(payload)))
            if endpoint == "/nongli/time" and "/" not in str(payload.get("date", "")):
                raise ToolTransportError(
                    "backend rejected payload",
                    code="transport.http_error",
                    details={
                        "endpoint": endpoint,
                        "status_code": 500,
                        "body": '{"ResultCode":200001,"Result":"param error Index 1 out of bounds for length 1"}',
                    },
                )
            return super().call(endpoint, payload)

    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    client = RetryNongliClient()
    service = HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool(
        "qimen",
        {
            "date": "2028/4/6",
            "time": "9:3",
            "zone": "8",
            "lat": "31.2167",
            "lon": "121.4667",
            "ad": 1,
        },
        save_result=False,
    )

    assert result.ok is True
    nongli_calls = [call_payload for endpoint, call_payload in client.calls if endpoint == "/nongli/time"]
    assert nongli_calls[0]["date"] == "2028-04-06"
    assert any(call_payload["date"] == "2028/04/06" for call_payload in nongli_calls)


def test_sanshiunited_subresults_use_compact_export_contracts(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool("sanshiunited", build_sample_payloads()["sanshiunited"], save_result=False)

    assert result.ok is True
    subresults = result.data["subresults"]
    # v3.11.x wave-3：六壬层不再另起 liureng_gods 子盘（上游三式合一用三式农历 + 奇门盘干支就地起课）。
    assert sorted(subresults) == ["qimen", "taiyi"]
    for subresult in subresults.values():
        assert "data" not in subresult
        assert "export_snapshot" not in subresult
        assert "export_format" not in subresult
        assert subresult["export_contract"]["has_export_snapshot"] is True
        assert subresult["export_contract"]["has_export_snapshot"] is True
        assert subresult["export_contract"]["section_titles"]


@pytest.mark.parametrize("tool_name", ["nongli_time", "qimen", "sixyao"])
def test_service_normalizes_single_digit_nongli_dates_before_remote_calls(tmp_path, tool_name: str) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    client = CaptureClient()
    service = HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=FakeJsClient())

    payload = {
        "date": "2028/4/6",
        "time": "9:3",
        "zone": "8",
        "lat": "31.2167",
        "lon": "121.4667",
        "ad": 1,
    }
    if tool_name == "sixyao":
        payload["question"] = "测试六爻输出"

    result = service.run_tool(tool_name, payload, save_result=False)

    assert result.ok is True
    assert result.input_normalized["date"] == "2028-04-06"
    assert result.input_normalized["time"] == "09:03:00"
    assert result.input_normalized["zone"] == "+08:00"
    assert result.input_normalized["lat"] == "31n13"
    assert result.input_normalized["lon"] == "121e28"

    nongli_calls = [call_payload for endpoint, call_payload in client.calls if endpoint == "/nongli/time"]
    assert nongli_calls, "expected /nongli/time to be called with normalized values"
    assert nongli_calls[0]["date"] == "2028-04-06"
    assert nongli_calls[0]["time"] == "09:03:00"
    assert nongli_calls[0]["zone"] == "+08:00"
    assert nongli_calls[0]["lat"] == "31n13"
    assert nongli_calls[0]["lon"] == "121e28"


def test_service_normalizes_iana_zone_before_nongli_remote_calls(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    client = CaptureClient()
    service = HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool(
        "qimen",
        {
            "date": "2026-05-18",
            "time": "13:14",
            "zone": "America/Los_Angeles",
            "lat": "34.0522",
            "lon": "-118.2437",
            "ad": 1,
        },
        save_result=False,
    )

    assert result.ok is True
    assert result.input_normalized["zone"] == "-07:00"
    nongli_calls = [call_payload for endpoint, call_payload in client.calls if endpoint == "/nongli/time"]
    assert nongli_calls, "expected /nongli/time to be called with normalized IANA timezone"
    assert nongli_calls[0]["zone"] == "-07:00"


def test_all_callable_techniques_keep_non_empty_structured_export_contracts(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    payloads = build_sample_payloads()

    assert sorted(payloads) == sorted(TOOL_DEFINITIONS)

    for tool_name, technique_key in TOOL_EXPORT_TECHNIQUE_MAP.items():
        result = service.run_tool(tool_name, payloads[tool_name], save_result=False)
        assert result.ok is True, tool_name
        assert result.data["export_snapshot"]["technique"]["key"] == technique_key, tool_name
        assert result.data["export_snapshot"]["format_source"] == "snapshot_parser", tool_name
        assert result.data["export_snapshot"]["selected_sections"], tool_name
        assert result.data["export_snapshot"]["sections"], tool_name
        assert all(section["title"] for section in result.data["export_snapshot"]["sections"]), tool_name


def test_predictive_tools_export_real_natal_and_timed_chart_content(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    payloads = build_sample_payloads()

    # 上游 v50 的推运族段结构：[本命盘配置]/[起盘信息]/[时段盘配置]/[相位]（不再带
    # 本命盘/返照盘/推运盘/流年盘 前缀；旧名走 map_legacy_section_title 迁移）。
    expected_sections = {
        "solarreturn": ["本命盘配置", "时段盘配置", "相位"],
        "lunarreturn": ["本命盘配置", "时段盘配置", "相位"],
        "givenyear": ["本命盘配置", "时段盘配置", "相位"],
        "solararc": ["本命盘配置", "时段盘配置", "相位"],
        "profection": ["本命盘配置", "时段盘配置", "相位"],
    }
    for tool_name, sections in expected_sections.items():
        result = service.run_tool(tool_name, payloads[tool_name], save_result=False)
        export_format = result.data["export_snapshot"]
        text = result.data["snapshot_text"]
        assert all(section in export_format["selected_sections"] for section in sections), tool_name
        assert "本命盘配置" in text, tool_name
        # 时段盘的两个子块标题（上游 buildDirectedChartLines 的排版）。
        assert "时段盘 星与虚点" in text, tool_name
        assert "日 (" in text and "月 (" in text, tool_name
        # 推运族的 [X盘相位] 是**交叉相位**（行运星 ↔ 本命星），不是本命盘那三个子标题。
        # 旧断言查 "标准相位" 恰恰是在断言那个 bug 的产物：真机上该段只有三个空子标题、
        # 零条相位，而桩在顶层塞了本命形状的 aspects 才让它显得成立。
        assert "行运" in text and "与 本命" in text, tool_name
        assert "标准相位" not in text, tool_name


def test_primary_direction_exports_tables_and_pdchart_positions(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    payloads = build_sample_payloads()

    pd_result = service.run_tool("pd", payloads["pd"], save_result=False)
    pd_text = pd_result.data["snapshot_text"]
    assert "主限法表格" in pd_text  # 上游 v48 段名对齐（旧名 主/界限法表格 → 主限法表格）
    # 上游 v3.11 AstroDirectMain.js buildPrimaryDirectSnapshotText：4 列「日期(UTC)」、弧写「X度Y分」、
    # 迫星/应星走 directionObjText（D_Moon_120 → 月…的120度右相位处）。
    assert "| Arc | 迫星 | 应星 | 日期(UTC) |" in pd_text
    assert "| 0度15分 | 月 (3th; 11R)的120度右相位处 | 土 (8th; 5R6R) | 2031-04-06 09:33:00 |" in pd_text

    pdchart_result = service.run_tool("pdchart", payloads["pdchart"], save_result=False)
    pdchart_text = pdchart_result.data["snapshot_text"]
    assert "本命盘星与虚点" in pdchart_text
    assert "主限法盘星体表格" in pdchart_text
    assert "| 星体/虚点 | 位置 | 宫位 | 速度 |" in pdchart_text
    assert "主限法盘相位" in pdchart_text


def test_primary_direction_full_house_settings_surface(tmp_path) -> None:
    # 主限法 v12 (星阙 v2.6.6)：核5方位法 + In Mundo + 仅逆向 + 映点 + 界 + 新时间钥匙 全部出现在设置段。
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    payloads = build_sample_payloads()
    payload = {
        **payloads["pd"],
        "pdMethod": "meridian",
        "pdtype": 1,
        "pdDirect": 0,
        "pdConverse": 1,
        "pdAntiscia": 1,
        "pdTerms": 1,
        "pdTimeKey": "Kundig",
    }
    text = service.run_tool("pd", payload, save_result=False).data["snapshot_text"]
    # 上游 [主限法设置] 行口径（v3.13.0 AstroDirectMain.js:349-411；无显式 pdProjection → 仍写「推运方法」）。
    assert "推运方法：Meridian" in text
    assert "方向类型：世俗（In Mundo）" in text
    assert "向运方向：逆向 Converse" in text
    assert "度数换算：Kündig" in text
    assert "映点迫星：是" in text
    assert "界迫星：是" in text
    # v3.13.0 pdTypeBaselineNote：In Mundo × Ptolemy × Meridian 有专属世俗核（PD_MUNDO_DEDICATED_PTOLEMY_FRAMES），
    # 不再标「（世界主限下走核内基线）」；几何口径只在世俗平行开时影响 Meridian（PD_GEOMETRY_APPLIES）→ 不带（改进）。
    assert "弧算法（投影）：Ptolemy（半弧）" in text.splitlines()


def test_primary_direction_core5_method_labels() -> None:
    # 上游 v3.13.0（primaryDirectionSync.js:298-374）：方位法 13 法、度数换算 38 项，标签取 PD_METHOD_LABELS /
    # PD_TIME_KEY_LABELS。旧「核5 + placidus 未核验回退」注记已过期（placidus 等自 v3.6 起真算，后端 perchart.py:892 白名单）。
    from horosa_skill.service import _primary_direction_method_text, _primary_direction_time_key_text

    assert _primary_direction_method_text("core_alchabitius") == "Alchabitius"
    assert _primary_direction_method_text("meridian") == "Meridian"
    assert _primary_direction_method_text("porphyry") == "Porphyry"
    assert _primary_direction_method_text("equal_ecliptic") == "Equal（黄道）"
    assert _primary_direction_method_text("equal_hour_circle") == "Equal（时圈）"
    assert _primary_direction_method_text("horosa_legacy") == "Horosa原方法"
    assert _primary_direction_method_text("placidus") == "Placidus（半弧）"
    # 时间钥匙 38 项全部有标签（上游下拉一致；v3.13.0 新增 12 项在末行）。
    for key in (
        "Ptolemy", "Naibod", "TrueSolarArc", "SymbolicSolarArc", "Cardano", "Umar", "Wollner",
        "Plantiko", "Simmonite", "SynodicYear", "Kepler", "Brahe", "Kundig", "SymbolicDegree",
        "SymbolicYear", "SymbolicMoon", "SymbolicMonth", "Quarterly", "Quinary", "Duodenary",
        "Novenary", "SelfMeasure", "NaibodRA", "AscendantArc", "VanDam", "User",
        "TrueSolarArcMean", "KeplerClassic", "BraheClassic", "BirthdaySunLon", "VerticalArc", "WollnerClassic",
        "SynodicYearClassic", "SymbolicMoonClassic", "SymbolicWeek", "Septenary", "NovenaryClassic", "SubDuodenary",
    ):
        label = _primary_direction_time_key_text(key)
        # 未登记键回落 Ptolemy 标签（getPdTimeKeyLabel），所以「有标签」要排除回落值才不空转。
        assert label and label != "无" and (key == "Ptolemy" or label != "Ptolemy"), key


def test_germany_uranian_snapshot_has_full_sections(tmp_path) -> None:
    # 中点盘 Uranian (星阙 v2.5.2)：10 段含 行星/TNP星体/90°中点盘/行星图/映点/中点列表。
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    result = service.run_tool(
        "germany",
        {"date": "2028/04/06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
        save_result=False,
    )
    text = result.data["snapshot_text"]
    for header in ("行星", "TNP星体", "90°中点盘", "行星图", "映点", "中点列表"):
        assert header in text, header
    assert "Cupido" in text or "Hades" in text  # TNP 渲染


def test_uranian_dial_math_matches_upstream() -> None:
    # 移植自 星阙 utils/uranianDial.js 的纯函数校验。
    from horosa_skill.service import _dial_antiscion, _dial_mid, _dial_planetary_pictures, _dial_sep

    assert abs(_dial_antiscion(15.0) - 165.0) < 1e-9  # 15°白羊 回照 → 165
    assert abs(_dial_mid(10.0, 20.0) - 15.0) < 1e-9
    assert abs(_dial_mid(350.0, 10.0) - 0.0) < 1e-9  # 跨 0° 近中点 = 0，非 180
    pts = [
        {"id": "Sun", "lon": 0.0},
        {"id": "Moon", "lon": 90.0},
        {"id": "Asc", "lon": 0.0},
        {"id": "MC", "lon": 90.0},
    ]
    pics = _dial_planetary_pictures(pts, 90.0, 1.0)
    assert pics, "Sun+Moon−Asc=MC 应命中一张行星图"


def test_guolao_limit_table_matches_upstream_algorithm() -> None:
    # 七政四余·大限：移植自 星阙 GuoLaoMoiraWheel.buildGuolaoLimitTable（JS Math.round half-up）。
    from horosa_skill.service import _guolao_limit_table

    rows = _guolao_limit_table(0.0, 2000)
    assert len(rows) == 12
    assert rows[0] == {"index": 1, "palace": "命宫", "years": 9.0, "from_age": 1, "to_age": 9, "from_year": 2000, "to_year": 2008}
    assert rows[1]["palace"] == "财帛" and (rows[1]["from_age"], rows[1]["to_age"]) == (10, 19)
    assert rows[3]["palace"] == "田宅" and rows[3]["years"] == 15.0
    # 首限年数随命度入宫度变化：life=15° → 9 + 15/3 = 14。
    assert _guolao_limit_table(15.0, 2000)[0]["to_age"] == 14


def test_guolao_snapshot_has_limit_and_aspect_sections(tmp_path) -> None:
    # 七政四余 大限 + 相位 段（星阙 v2.5.x Moira 还原度）。
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    result = service.run_tool(
        "guolao_chart",
        {"date": "1998/03/02", "time": "08:18:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
        save_result=False,
    )
    text = result.data["snapshot_text"]
    assert "大限" in text
    # v3.11.x：[大限] 由 vendored 上游 buildGuolaoLimitSection 出（GFM 表，GuoLaoChartMain.js:2191-2201），
    # 不再是 skill 旧行式「第1限 命宫：…」。
    assert "| 第1限 | 命宫 |" in text
    assert "相位" in text


def test_zodiacal_release_exports_timeline_rows(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    payloads = build_sample_payloads()

    result = service.run_tool("zr", payloads["zr"], save_result=False)
    text = result.data["snapshot_text"]
    # 上游 AstroZR.js buildZRAISnapshotBody（v3.11）：段头取基点中文名（缺省福点），L1 全列「座-起始日」。
    assert "[基于福点推运]" in text
    assert "AI输出模式：输出所有L1（星座+时间）" in text
    assert "L1-1：牡羊-2028-04-06" in text
    drill = service.run_tool("zr", {**payloads["zr"], "aiMode": "l2_in_l1"}, save_result=False)
    assert "L2-1：金牛-2028-04-21" in drill.data["snapshot_text"]


def test_all_callable_techniques_keep_clean_contracts_across_repeated_saved_runs(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    service = HorosaSkillService(settings, client=FakeClient(), store=store, js_client=FakeJsClient())
    payloads = build_sample_payloads()

    for tool_name, technique_key in TOOL_EXPORT_TECHNIQUE_MAP.items():
        service.run_tool(tool_name, payloads[tool_name], save_result=True)
        service.run_tool(tool_name, payloads[tool_name], save_result=True)

        queried = store.query_runs(tool=tool_name, include_payload=True, limit=5)
        assert len(queried) >= 2, tool_name

        for run in queried[:2]:
            artifact_payload = run["artifacts"][0]["payload"]
            export_snapshot = artifact_payload["data"]["export_snapshot"]
            export_format = artifact_payload["data"]["export_snapshot"]
            assert artifact_payload["ok"] is True, tool_name
            assert export_snapshot["technique"]["key"] == technique_key, tool_name
            assert export_snapshot["format_source"] == "snapshot_parser", tool_name
            assert export_format["selected_sections"], tool_name
            assert export_format["sections"], tool_name
            assert all(section["title"] for section in export_format["sections"]), tool_name


def test_all_callable_techniques_can_generate_report_json_artifacts(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    service = HorosaSkillService(settings, client=FakeClient(), store=store, js_client=FakeJsClient())
    payloads = build_sample_payloads()

    for tool_name, technique_key in TOOL_EXPORT_TECHNIQUE_MAP.items():
        result = service.run_tool(tool_name, payloads[tool_name], save_result=True, query_text=f"生成 {tool_name} 报告")
        assert result.memory_ref is not None, tool_name
        template = service.report_template({"run_id": result.memory_ref.run_id, "tool_name": tool_name})
        assert template["schema"] == "horosa.skill.report.template.v1", tool_name
        assert template["technique"] == technique_key, tool_name
        assert template["source_export_sections"], tool_name
        assert template["coverage_contract"]["all_source_export_sections_required"] is True, tool_name
        assert template["coverage_contract"]["source_export_section_count"] == len(template["source_export_sections"]), tool_name
        assert template["source_context"]["export_text"], tool_name
        assert template["source_context"]["export_sections"], tool_name
        assert all(section["body"] for section in template["source_context"]["export_sections"]), tool_name
        assert template["targeted_analysis_contract"]["answer_priority"] == "directly_answer_user_question_first", tool_name
        assert template["question_analysis"]["has_question"] is True, tool_name
        assert template["targeted_analysis_contract"]["question_analysis"]["raw_question"] == f"生成 {tool_name} 报告", tool_name
        assert template["targeted_analysis_contract"]["answer_plan"], tool_name
        assert template["targeted_analysis_contract"]["targeted_answer_requirements"], tool_name
        assert template["ai_fillable"]["targeted_answer_requirements"], tool_name
        assert template["ai_fillable"]["answer_plan"], tool_name
        assert template["ai_fillable"]["analysis_focus"] == f"生成 {tool_name} 报告", tool_name
        assert template["conversation_brief"]["role"].startswith("你是接入 Horosa Skill 的 AI 解盘助手"), tool_name
        assert "像在 AI 对话窗口中完成一次认真解盘" in "\n".join(template["conversation_brief"]["output_style"]), tool_name
        assert "answer_text" in template["ai_fillable"], tool_name
        assert "direct_answer" in template["ai_fillable"], tool_name

        ai_sections = [
            {
                "title": section["title"],
                "body": f"解释 {section['title']}",
                "evidence_lines": [section["title"]],
                "relevance_to_question": "用于回答用户问题。",
            }
            for section in template["source_export_sections"]
        ]
        rendered = service.report_render(
            {
                "run_id": result.memory_ref.run_id,
                "tool_name": tool_name,
                "format": "json",
                "ai_report": {
                    "analysis_focus": f"生成 {tool_name} 报告",
                    "direct_answer": "已根据用户问题完成针对性分析。",
                    "executive_summary": "报告摘要。",
                    "analysis_sections": ai_sections,
                    "evidence": [{"source": tool_name, "line": "测试证据"}],
                    "recommendations": ["保留报告。"],
                    "limitations": [],
                },
            }
        )
        path = Path(rendered["artifact_path"])
        assert rendered["ok"] is True, tool_name
        assert path.is_file(), tool_name
        assert rendered["file_size"] > 100, tool_name
        report_payload = json.loads(path.read_text(encoding="utf-8"))
        assert report_payload["schema"] == "horosa.skill.report.v1", tool_name
        assert report_payload["source"]["tool_name"] == tool_name, tool_name
        assert report_payload["source"]["technique"] == technique_key, tool_name
        assert report_payload["sections"], tool_name
        assert report_payload["coverage"]["all_source_export_sections_required"] is True, tool_name
        assert report_payload["coverage"]["must_explain_sections"] == [
            section["title"] for section in template["source_export_sections"]
        ], tool_name
        assert report_payload["targeted_analysis_contract"]["user_question"] == f"生成 {tool_name} 报告", tool_name
        assert report_payload["question_analysis"]["has_question"] is True, tool_name
        assert report_payload["report_index"]["question_analysis"]["raw_question"] == f"生成 {tool_name} 报告", tool_name
        assert report_payload["report_index"]["answer_plan"], tool_name
        assert report_payload["report_index"]["targeted_answer_requirements"], tool_name
        assert report_payload["targeted_analysis_contract"]["targeted_answer_requirements"], tool_name
        assert report_payload["report_index"]["analysis_focus"] == f"生成 {tool_name} 报告", tool_name
        assert report_payload["report_index"]["coverage_status"] == "complete", tool_name
        assert report_payload["report_index"]["ready_to_deliver"] is True, tool_name
        assert report_payload["report_index"]["delivery_missing"] == [], tool_name
        assert report_payload["report_index"]["delivery_checks"]["has_targeted_requirements"] is True, tool_name
        assert report_payload["ai_coverage_status"]["missing_sections"] == [], tool_name
        assert report_payload["ai_coverage_status"]["has_direct_answer"] is True, tool_name
        assert report_payload["ai_coverage_status"]["has_evidence"] is True, tool_name
        assert report_payload["section_coverage_matrix"]["all_sections_covered"] is True, tool_name
        assert report_payload["section_coverage_matrix"]["missing_section_titles"] == [], tool_name
        assert report_payload["section_coverage_matrix"]["source_section_count"] == len(template["source_export_sections"]), tool_name
        assert report_payload["content_outline"], tool_name
        assert len(report_payload["content_outline"]) == len(report_payload["sections"]), tool_name
        assert report_payload["content_outline"][0]["title"] == "报告元信息", tool_name
        assert report_payload["sections"][0]["id"] == "report_metadata", tool_name
        assert "逐章解释覆盖矩阵" in report_payload["plain_text"], tool_name
        assert "报告元信息" in report_payload["plain_text"], tool_name
        assert result.memory_ref.run_id in report_payload["plain_text"], tool_name
        assert tool_name in report_payload["plain_text"], tool_name
        assert "星阙 AI 导出正文" in report_payload["plain_text"], tool_name
        assert template["source_export_sections"][0]["title"] in report_payload["plain_text"], tool_name
        assert report_payload["search_index"]["schema"] == "horosa.skill.report.search_index.v1", tool_name
        assert report_payload["search_index"]["tool_name"] == tool_name, tool_name
        assert report_payload["search_index"]["technique"] == technique_key, tool_name
        assert f"生成 {tool_name} 报告" in report_payload["search_index"]["keywords"], tool_name
        assert template["source_export_sections"][0]["title"] in report_payload["search_index"]["section_titles"], tool_name
        assert "逐章解释覆盖矩阵" in report_payload["search_index"]["search_text"], tool_name
        assert "交付检查清单" in report_payload["search_index"]["search_text"], tool_name
        assert report_payload["report_quality"]["source_complete"] is True, tool_name
        assert report_payload["report_quality"]["ai_analysis_complete"] is True, tool_name
        assert report_payload["report_quality"]["ready_for_human_reading"] is True, tool_name
        assert report_payload["delivery_checklist"]["schema"] == "horosa.skill.report.delivery_checklist.v1", tool_name
        assert report_payload["delivery_checklist"]["ready_to_deliver"] is True, tool_name
        assert report_payload["delivery_checklist"]["missing"] == [], tool_name
        assert report_payload["delivery_checklist"]["checks"]["source_sections_covered"] is True, tool_name
        assert report_payload["delivery_checklist"]["checks"]["has_targeted_requirements"] is True, tool_name
        assert report_payload["delivery_checklist"]["checks"]["has_search_index"] is True, tool_name
        section_ids = {section["id"] for section in report_payload["sections"]}
        assert {
            "report_metadata",
            "report_quality",
            "delivery_checklist",
            "coverage_contract",
            "section_coverage_matrix",
            "targeted_analysis_contract",
            "question_analysis",
            "ai_interpretation",
            "recommendations_limitations",
            "xingque_export_text",
            "provenance",
        }.issubset(section_ids), tool_name
        queried = store.query_runs(run_id=result.memory_ref.run_id, include_payload=True)
        assert "report_json" in {artifact["kind"] for artifact in queried[0]["artifacts"]}, tool_name
        report_artifact = next(artifact for artifact in queried[0]["artifacts"] if artifact["kind"] == "report_json")
        assert report_artifact["exists"] is True, tool_name
        assert report_artifact["file_size"] > 100, tool_name
        assert report_artifact["sha256"], tool_name
        assert report_artifact["payload"]["report_index"]["tool_name"] == tool_name, tool_name
        assert report_artifact["payload"]["report_index"]["storage"]["managed_by"] == "horosa_skill.memory", tool_name
        assert report_artifact["payload"]["report_index"]["ready_to_deliver"] is True, tool_name
        assert report_artifact["payload"]["report_index"]["delivery_missing"] == [], tool_name


def test_all_callable_techniques_can_generate_human_readable_pdf_and_docx(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    service = HorosaSkillService(settings, client=FakeClient(), store=store, js_client=FakeJsClient())
    payloads = build_sample_payloads()
    bad_terms = ["待 AI", "AI 后续应", "这份报告已把"]

    for tool_name in TOOL_EXPORT_TECHNIQUE_MAP:
        question = f"请针对这个人的事业、财务和决策风险生成可直接阅读的 {tool_name} 咨询报告。"
        result = service.run_tool(tool_name, payloads[tool_name], save_result=True, query_text=question)
        assert result.memory_ref is not None, tool_name

        rendered_json = service.report_render(
            {
                "run_id": result.memory_ref.run_id,
                "tool_name": tool_name,
                "format": "json",
                "ai_report": sample_final_ai_report(question),
            }
        )
        report_payload = json.loads(Path(rendered_json["artifact_path"]).read_text(encoding="utf-8"))
        assert report_payload["report_quality"]["ready_for_human_reading"] is True, tool_name
        assert report_payload["delivery_checklist"]["ready_to_deliver"] is True, tool_name
        assert report_payload["delivery_checklist"]["missing"] == [], tool_name
        assert report_payload["ai_report"]["direct_answer"], tool_name
        assert report_payload["ai_report"]["consultation_basis"], tool_name
        assert report_payload["ai_report"]["reading_steps"], tool_name
        assert report_payload["ai_report"]["analysis_sections"], tool_name
        assert not any(term in report_payload["plain_text"] for term in bad_terms), tool_name

        rendered_pdf = service.report_render(
            {"run_id": result.memory_ref.run_id, "tool_name": tool_name, "format": "pdf"}
        )
        rendered_docx = service.report_render(
            {"run_id": result.memory_ref.run_id, "tool_name": tool_name, "format": "docx"}
        )
        pdf_path = Path(rendered_pdf["artifact_path"])
        docx_path = Path(rendered_docx["artifact_path"])
        assert pdf_path.read_bytes().startswith(b"%PDF"), tool_name
        assert docx_path.read_bytes().startswith(b"PK"), tool_name
        assert rendered_pdf["file_size"] > 500, tool_name
        assert rendered_docx["file_size"] > 5000, tool_name
        with zipfile.ZipFile(docx_path) as archive:
            docx_text = re.sub("<[^>]+>", "", archive.read("word/document.xml").decode("utf-8"))
        assert "起盘依据" in docx_text, tool_name
        assert "解盘步骤" in docx_text, tool_name
        assert not any(term in docx_text for term in ["Run ID", "来源追溯", "report_metadata", "Horosa Skill"]), tool_name
        if tool_name in {"bazi_birth", "bazi_direct"}:
            assert "大运流年与阶段判断" in docx_text, tool_name


def test_all_callable_techniques_without_question_generate_overall_reading_docx(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    service = HorosaSkillService(settings, client=FakeClient(), store=store, js_client=FakeJsClient())
    payloads = build_sample_payloads()

    for tool_name in TOOL_EXPORT_TECHNIQUE_MAP:
        result = service.run_tool(tool_name, payloads[tool_name], save_result=True)
        assert result.memory_ref is not None, tool_name
        rendered = service.report_render(
            {
                "run_id": result.memory_ref.run_id,
                "tool_name": tool_name,
                "format": "docx",
                "ai_report": sample_final_ai_report("整体综合解盘"),
            }
        )
        with zipfile.ZipFile(Path(rendered["artifact_path"])) as archive:
            docx_text = re.sub("<[^>]+>", "", archive.read("word/document.xml").decode("utf-8"))
        assert "解读目标" in docx_text, tool_name
        assert "综合命局咨询" in docx_text or "整体综合解盘" in docx_text, tool_name
        assert "解读目标无" not in docx_text, tool_name
        assert "起盘依据" in docx_text, tool_name
        assert "解盘步骤" in docx_text, tool_name
        assert "核心结论" in docx_text, tool_name
        assert not any(term in docx_text for term in ["Run ID", "来源追溯", "report_metadata", "Horosa Skill"]), tool_name


def test_bazi_report_promotes_liunian_output_into_human_reading(tmp_path) -> None:
    class BaziFlowClient(FakeClient):
        def call(self, endpoint: str, payload: dict) -> dict:
            def column(ganzi: str) -> dict:
                return {"ganzi": ganzi, "stem": {"name": ganzi[0]}, "branch": {"name": ganzi[1]}}

            return {
                "bazi": {
                    "nongli": {"birth": "1995-06-03 05:18:42"},
                    "fourColumns": {
                        "year": column("乙亥"),
                        "month": column("辛巳"),
                        "day": column("乙卯"),
                        "time": column("己卯"),
                    },
                    "mainDirection": [
                        {"year": 2019, "ganzi": "甲申"},
                        {"year": 2029, "ganzi": "乙酉"},
                    ],
                    "direction": [
                        {
                            "mainDirect": {"ganzi": "甲申"},
                            "startYear": 2019,
                            "subDirect": [
                                {"date": "2026", "ganzi": "丙午"},
                                {"date": "2027", "ganzi": "丁未"},
                                {"date": "2028", "ganzi": "戊申"},
                            ],
                        }
                    ],
                }
            }

    class BaziFlowJs(FakeJsClient):
        # v0.40 F9：八字改本地引擎优先（tools/baziLocal.js，上游页面主路径），Java 桩不再被调；
        # 流年行运数据改由 JS 快照给 —— 节选自真引擎同盘实出（1995-06-03 05:30 上海男命，
        # vendored buildBaziSnapshotText；[流年行运概略] 为 BaZi.js:575-599 的 GFM 表）。
        def run(self, tool_name: str, payload: dict[str, object]) -> dict:
            if tool_name != "bazi_local":
                return super().run(tool_name, payload)
            out = super().run(tool_name, payload)
            out["snapshot_text"] = "\n".join([
                "[起盘信息]", "日期：1995-06-03 05:30:00", "性别：男", "命造：乾造",
                "直接时间：1995-06-03 05:30:00　真太阳时：1995-06-03 05:37:55", "",
                "[四柱与三元]", "| 柱 | 干支 | 藏干 | 十神 | 纳音 | 纳音长生 | 星运 | 自坐 | 空亡 |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
                "| 年柱 | 乙亥 | 壬印、甲劫 | 比·印 | 山头火 | 绝 | 长生 | 长生 | 申酉 |",
                "| 月柱 | 辛巳 | 丙伤、庚官、戊财 | 杀·伤 | 白蜡金 | 长生 | 病 | 长生 | 申酉 |",
                "| 日柱 | 乙丑 | 己才、癸枭、辛杀 | 日元·才 | 海中金 | 墓 | 冠带 | 冠带 | 戌亥 |",
                "| 时柱 | 己卯 | 乙比 | 才·比 | 城头土 | 死 | 帝旺 | 沐浴 | 申酉 |", "",
                "[神煞（四柱与三元）]", "胎元：整柱=无；天干=无；地支=无；太岁=无", "",
                "[流年行运概略]", "| 板块 | 起始年 | 起始年龄 | 大运 | 流年 |", "| --- | --- | --- | --- | --- |",
                "| 板块3 | 2024 | 30岁 | 戊寅 | 2024-甲辰 2025-乙巳 2026-丙午 2027-丁未 2028-戊申 2029-己酉 2030-庚戌 2031-辛亥 2032-壬子 2033-癸丑 |",
            ])
            return out

    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=BaziFlowClient(), store=MemoryStore(settings), js_client=BaziFlowJs())
    result = service.run_tool(
        "bazi_birth",
        {
            "date": "1995-06-03",
            "time": "05:30:00",
            "zone": "+08:00",
            "lat": "31n13",
            "lon": "121e28",
            "gender": True,
            "timeAlg": 0,
        },
        save_result=True,
        query_text="这个人未来三年事业和财务风险如何？",
    )

    rendered = service.report_render(
        {
            "run_id": result.memory_ref.run_id,
            "tool_name": "bazi_birth",
            "format": "docx",
            "ai_report": sample_final_ai_report("这个人未来三年事业和财务风险如何？"),
        }
    )
    with zipfile.ZipFile(Path(rendered["artifact_path"])) as archive:
        docx_text = re.sub("<[^>]+>", "", archive.read("word/document.xml").decode("utf-8"))
    assert "大运流年与阶段判断" in docx_text
    assert "2026" in docx_text
    assert "2027" in docx_text
    assert "2028" in docx_text
    assert "事业判断上" in docx_text
    assert "财务判断上" in docx_text


def test_all_callable_techniques_final_export_text_matches_max_section_contract(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    payloads = build_sample_payloads()

    for tool_name, technique_key in TOOL_EXPORT_TECHNIQUE_MAP.items():
        result = service.run_tool(tool_name, payloads[tool_name], save_result=False)
        export_text = result.data["export_snapshot"]["export_text"]
        reparsed = parse_export_content(technique=technique_key, content=export_text)
        assert reparsed["missing_selected_sections"] == [], tool_name
        assert reparsed["unknown_detected_sections"] == [], tool_name


def test_all_callable_techniques_do_not_emit_bare_empty_or_dependency_hallucination_sections(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    payloads = build_sample_payloads()
    forbidden_claim_terms = [
        "MongoDB",
        "7897",
        "星阙桌面",
        "桌面应用",
        "远程数据库",
        "外部数据库",
        "外部服务",
        "无法输出",
        "需要安装",
    ]

    for tool_name in TOOL_EXPORT_TECHNIQUE_MAP:
        result = service.run_tool(tool_name, payloads[tool_name], save_result=False, query_text=f"审计 {tool_name}")
        export_snapshot = result.data["export_snapshot"]
        export_text = export_snapshot["export_text"]
        assert not any(term in export_text for term in forbidden_claim_terms), tool_name
        # 段名一致性闸：任何工具 emit 的段名必须能被契约认领（preset/可选段/legacy 映射之一），
        # unknown 非空 = builder 段名与 registry 拼写漂移，立即红。
        assert export_snapshot.get("unknown_detected_sections") == [], (
            f"{tool_name}: unknown sections {export_snapshot.get('unknown_detected_sections')}"
        )
        for section in export_snapshot["sections"]:
            body = section.get("body", "").strip()
            assert body and body != "无", f"{tool_name}:{section.get('title')}"
            if "未返回" in body:
                assert "不能臆造" in body, f"{tool_name}:{section.get('title')}"


def test_dispatch_exposes_child_export_contracts_explicitly(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    service = HorosaSkillService(settings, client=FakeClient(), store=store, js_client=FakeJsClient())

    result = service.dispatch(
        {
            "query": "请用奇门和六壬综合分析",
            "birth": {"date": "2028/04/06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
            "save_result": True,
        }
    )

    assert result.ok is True
    assert "qimen" in result.result_export_contracts
    assert "liureng_gods" in result.result_export_contracts
    qimen_contract = result.result_export_contracts["qimen"]
    liureng_contract = result.result_export_contracts["liureng_gods"]
    assert qimen_contract["has_export_snapshot"] is True
    assert qimen_contract["has_export_snapshot"] is True
    assert qimen_contract["technique"]["key"] == "qimen"
    assert "奇门演卦" in qimen_contract["selected_sections"]
    assert liureng_contract["has_export_snapshot"] is True
    assert liureng_contract["has_export_snapshot"] is True
    assert liureng_contract["technique"]["key"] == "liureng"
    queried = store.query_runs(tool="liureng_gods", include_payload=True)
    assert queried
    assert sorted(result.selected_tools) == sorted(result.result_export_contracts)
    for tool_name, contract in result.result_export_contracts.items():
        assert contract["tool"] == tool_name
        assert contract["selected_sections"]
        # dispatch 轻契约：快照本体在 results[tool].data，contract 只带元信息。
        assert contract["technique"]["key"] == TOOL_EXPORT_TECHNIQUE_MAP[tool_name]
        assert "export_snapshot" not in contract and "snapshot_text" not in contract
        assert contract["section_titles"]


def test_service_can_attach_ai_answer_to_existing_run(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    service = HorosaSkillService(settings, client=FakeClient(), store=store, js_client=FakeJsClient())

    result = service.dispatch(
        {
            "query": "请用奇门分析事业",
            "birth": {"date": "2028/04/06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
            "save_result": True,
        }
    )

    assert result.memory_ref is not None
    updated = service.record_ai_answer(
        {
            "run_id": result.memory_ref.run_id,
            "user_question": "我接下来事业走势如何？",
            "ai_answer": "先稳后升，宜先整理资源再扩张。",
            "ai_answer_structured": {"trend": "up_later"},
            "answer_meta": {"source": "assistant"},
        }
    )

    assert updated["ok"] is True
    queried = store.query_runs(text="我接下来事业走势如何", include_payload=True)
    assert queried
    assert queried[0]["run_id"] == result.memory_ref.run_id
    by_tool = store.query_runs(tool="qimen", include_payload=True)
    assert by_tool
    assert by_tool[0]["ai_answer_text"] == "先稳后升，宜先整理资源再扩张。"
    assert by_tool[0]["artifacts"][0]["payload"]["conversation"]["ai_answer_structured"] == {"trend": "up_later"}


def test_service_can_build_report_template_and_render_json_docx_pdf(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    service = HorosaSkillService(settings, client=FakeClient(), store=store, js_client=FakeJsClient())

    result = service.run_tool(
        "chart",
        {"date": "2026-04-04", "time": "15:58:35", "zone": "8", "lat": "26n04", "lon": "119e19"},
        save_result=True,
        query_text="请生成当前星盘报告",
    )
    assert result.memory_ref is not None
    service.record_ai_answer(
        {
            "run_id": result.memory_ref.run_id,
            "ai_answer": "这是一份结构化报告测试回答。",
            "ai_answer_structured": {
                "executive_summary": "星盘报告摘要。",
                "analysis_focus": "检查后天宫位",
                "direct_answer": "后天宫位信息可以被报告引用。",
                "analysis_sections": [{"title": "起盘信息", "body": "后天宫位与星体信息齐全。", "evidence_lines": ["宫位宫头"]}],
                "evidence": [{"source_section_title": "宫位宫头", "source_line": "第八宫 宫头"}],
                "recommendations": ["保留完整导出正文。"],
                "limitations": ["测试环境不代表真实解读。"],
            },
        }
    )

    template = service.report_template({"run_id": result.memory_ref.run_id, "tool_name": "chart"})
    assert template["schema"] == "horosa.skill.report.template.v1"
    assert template["tool_name"] == "chart"
    assert template["technique"] == "astrochart"
    assert template["source_export_sections"]
    assert template["source_context"]["export_sections"][0]["body"]
    assert template["coverage_contract"]["must_explain_sections"]
    assert template["targeted_analysis_contract"]["required_ai_fields"]
    assert template["question_analysis"]["focus_domains"] == ["general_reading"]
    assert template["targeted_analysis_contract"]["answer_plan"]
    assert template["ai_fillable"]["direct_answer"] == ""
    service.record_ai_answer(
        {
            "run_id": result.memory_ref.run_id,
            "ai_answer": "这是一份覆盖全部星盘导出章节的结构化报告测试回答。",
            "ai_answer_structured": {
                "executive_summary": "星盘报告摘要。",
                "analysis_focus": "检查后天宫位",
                "direct_answer": "后天宫位信息可以被报告引用。",
                "analysis_sections": [
                    {
                        "title": section["title"],
                        "body": f"{section['title']} 已纳入报告解释。",
                        "evidence_lines": [section["title"]],
                        "relevance_to_question": "用于检查星盘报告是否完整覆盖原始导出。",
                    }
                    for section in template["source_export_sections"]
                ],
                "evidence": [{"source_section_title": "宫位宫头", "source_line": "第八宫 宫头"}],
                "recommendations": ["保留完整导出正文。"],
                "limitations": ["测试环境不代表真实解读。"],
            },
        }
    )

    rendered_json = service.report_render(
        {
            "run_id": result.memory_ref.run_id,
            "tool_name": "chart",
            "format": "json",
            "include_raw_json": True,
        }
    )
    rendered_docx = service.report_render({"run_id": result.memory_ref.run_id, "tool_name": "chart", "format": "docx"})
    rendered_pdf = service.report_render({"run_id": result.memory_ref.run_id, "tool_name": "chart", "format": "pdf"})

    for rendered in (rendered_json, rendered_docx, rendered_pdf):
        path = Path(rendered["artifact_path"])
        assert path.is_file()
        assert rendered["file_size"] > 100
        assert rendered["sha256"]

    assert Path(rendered_json["artifact_path"]).read_text(encoding="utf-8").startswith("{")
    report_payload = json.loads(Path(rendered_json["artifact_path"]).read_text(encoding="utf-8"))
    assert report_payload["coverage"]["source_export_section_count"] == len(template["source_export_sections"])
    assert report_payload["coverage"]["source_export_text_chars"] > 0
    assert report_payload["report_index"]["has_ai_answer"] is True
    assert report_payload["report_index"]["question_analysis"]["has_question"] is True
    assert report_payload["report_index"]["answer_plan"]
    assert report_payload["report_index"]["targeted_answer_requirements"]
    assert report_payload["report_index"]["storage"]["managed_by"] == "horosa_skill.memory"
    assert report_payload["report_index"]["ready_to_deliver"] is True
    assert report_payload["report_index"]["delivery_missing"] == []
    assert report_payload["report_quality"]["source_complete"] is True
    assert report_payload["report_quality"]["ready_for_human_reading"] is True
    assert report_payload["delivery_checklist"]["ready_to_deliver"] is True
    assert report_payload["delivery_checklist"]["missing"] == []
    assert report_payload["delivery_checklist"]["checks"]["has_ai_direct_answer"] is True
    assert report_payload["delivery_checklist"]["checks"]["has_provenance"] is True
    assert report_payload["section_coverage_matrix"]["source_section_count"] == len(template["source_export_sections"])
    assert report_payload["content_outline"][0]["title"] == "报告元信息"
    assert report_payload["sections"][0]["items"]["run_id"] == result.memory_ref.run_id
    assert "报告元信息" in report_payload["plain_text"]
    assert "交付检查清单" in report_payload["plain_text"]
    assert "AI 解盘正文" in report_payload["plain_text"]
    assert "来源追溯" in report_payload["plain_text"]
    assert report_payload["search_index"]["plain_text_chars"] == len(report_payload["plain_text"])
    assert "检查后天宫位" in report_payload["search_index"]["keywords"]
    section_titles = {section["title"] for section in report_payload["sections"]}
    assert {
        "报告质量检查",
        "报告元信息",
        "交付检查清单",
        "AI 解释覆盖清单",
        "逐章解释覆盖矩阵",
        "针对性解盘要求",
        "用户问题拆解",
        "AI 解盘正文",
        "建议、限制与追问",
        "来源追溯",
    }.issubset(section_titles)
    assert Path(rendered_docx["artifact_path"]).read_bytes().startswith(b"PK")
    assert Path(rendered_pdf["artifact_path"]).read_bytes().startswith(b"%PDF")
    queried = store.query_runs(run_id=result.memory_ref.run_id, include_payload=False)
    artifact_kinds = {artifact["kind"] for artifact in queried[0]["artifacts"]}
    assert {"report_json", "report_docx", "report_pdf"}.issubset(artifact_kinds)
    for artifact in queried[0]["artifacts"]:
        assert artifact["exists"] is True
        assert artifact["file_size"] > 0
        assert artifact["sha256"]

    report_pdf_runs = store.query_runs(
        run_id=result.memory_ref.run_id,
        text="后天宫位",
        artifact_kind="report_pdf",
        include_payload=False,
    )
    assert report_pdf_runs
    assert report_pdf_runs[0]["artifacts"]
    assert {artifact["kind"] for artifact in report_pdf_runs[0]["artifacts"]} == {"report_pdf"}
    assert report_pdf_runs[0]["artifact_summary"]["has_reports"] is True
    assert report_pdf_runs[0]["artifact_summary"]["counts_by_kind"]["report_pdf"] == 1
    assert report_pdf_runs[0]["artifact_summary"]["latest_report"]["kind"] == "report_pdf"

    report_json_plain_text_runs = store.query_runs(
        text="逐章解释覆盖矩阵",
        artifact_kind="report_json",
        include_payload=False,
    )
    assert any(run["run_id"] == result.memory_ref.run_id for run in report_json_plain_text_runs)


def test_service_can_render_report_from_tool_in_one_call(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    rendered = service.report_from_tool(
        {
            "tool_name": "qimen",
            "payload": {"date": "2028-04-06", "time": "09:33:00", "zone": "8", "lat": "31n13", "lon": "121e28"},
            "format": "json",
            "question": "请生成奇门结构化报告",
            "ai_report": {"executive_summary": "奇门报告摘要。"},
        }
    )

    assert rendered["ok"] is True
    assert rendered["format"] == "json"
    assert Path(rendered["artifact_path"]).is_file()
    assert rendered["tool_result"]["ok"] is True
    assert rendered["source"]["tool_name"] == "qimen"
    assert rendered["answer_writeback"]["ok"] is True
    assert rendered["answer_writeback"]["answer_text_chars"] > 0
    run_id = rendered["tool_result"]["memory_ref"]["run_id"]
    stored = service.store.query_runs(run_id=run_id, text="奇门报告摘要", include_payload=True)
    assert stored
    assert stored[0]["ai_answer_text"] == "奇门报告摘要。"
    assert stored[0]["ai_answer_structured"]["executive_summary"] == "奇门报告摘要。"
    assert stored[0]["answer_meta"]["source"] == "report_render"
    assert stored[0]["artifact_summary"]["has_reports"] is True
    assert stored[0]["artifact_summary"]["counts_by_kind"]["report_json"] == 1


def test_report_from_tool_without_ai_report_returns_analysis_packet_not_final_report(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.report_from_tool(
        {
            "tool_name": "qimen",
            "payload": {"date": "2028-04-06", "time": "09:33:00", "zone": "8", "lat": "31n13", "lon": "121e28"},
            "format": "pdf",
            "question": "这个事情能不能推进？风险在哪里？",
        }
    )

    assert result["ok"] is True
    assert result["mode"] == "analysis_required"
    assert result["needs_ai_analysis"] is True
    assert result["final_report_generated"] is False
    assert result["artifact_path"] is None
    assert result["tool_result"]["ok"] is True
    assert result["report_template"]["source_context"]["export_text"]
    assert result["report_template"]["source_context"]["export_sections"]
    assert result["report_template"]["targeted_analysis_contract"]["targeted_answer_requirements"]
    assert result["report_template"]["conversation_brief"]["role"].startswith("你是接入 Horosa Skill 的 AI 解盘助手")
    assert "完整对话式解盘正文" in result["report_template"]["conversation_brief"]["final_ai_report_contract"]["answer_text"]
    assert result["ai_process"]["input"]
    assert result["ai_process"]["conversation_brief"]["plate_context"]["tool_name"] == "qimen"
    assert result["ai_process"]["process"]
    assert result["ai_process"]["output"].startswith("最终报告必须来自 AI")
    assert "answer_text" in result["ai_process"]["ai_report_skeleton"]
    assert result["ai_process"]["next_call"]["payload"]["run_id"] == result["run_id"]
    assert result["ai_process"]["next_call"]["payload"]["ai_report"] == "<AI fills this object from ai_report_skeleton>"

    stored = service.show_memory({"run_id": result["run_id"], "include_payload": True})
    assert stored["ok"] is True
    assert stored["result"]["artifact_summary"]["has_reports"] is False
    assert stored["result"]["ai_answer_text"] is None
    artifact_kinds = {artifact["kind"] for artifact in stored["result"]["artifacts"]}
    assert "tool_result" in artifact_kinds
    assert "report_pdf" not in artifact_kinds


def test_report_from_tool_accepts_freeform_ai_answer_text(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    answer_text = (
        "结论上，这件事可以推进，但不适合在信息不足时突然加速。"
        "我会先看奇门盘里的起局信息、值符值使和宫位关系，再把这些线索转成现实行动建议。"
        "事业上适合先整理资源和选择窗口，财务上要避免高杠杆，决策上要把可验证的小步骤放在前面。"
    )

    rendered = service.report_from_tool(
        {
            "tool_name": "qimen",
            "payload": {"date": "2028-04-06", "time": "09:33:00", "zone": "8", "lat": "31n13", "lon": "121e28"},
            "format": "docx",
            "question": "这个事情能不能推进？风险在哪里？",
            "ai_answer_text": answer_text,
        }
    )

    assert rendered["ok"] is True
    assert rendered["answer_writeback"]["ok"] is True
    run_id = rendered["tool_result"]["memory_ref"]["run_id"]
    stored = service.show_memory({"run_id": run_id, "include_payload": True})
    assert stored["result"]["ai_answer_text"] == answer_text
    assert stored["result"]["ai_answer_structured"]["answer_text"] == answer_text
    with zipfile.ZipFile(Path(rendered["artifact_path"])) as archive:
        docx_text = re.sub("<[^>]+>", "", archive.read("word/document.xml").decode("utf-8"))
    assert "完整解盘正文" in docx_text
    assert "这件事可以推进" in docx_text
    assert "可读解读" not in docx_text
    assert "关键线索" not in docx_text
    assert "本次咨询使用" not in docx_text
    assert "盘面返回的核心摘要" not in docx_text
    assert "Run ID" not in docx_text


def test_report_contract_targets_user_question_and_memory_retrieval(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    service = HorosaSkillService(settings, client=FakeClient(), store=store, js_client=FakeJsClient())

    question = "我接下来事业什么时候适合换工作？是否应该跳槽？"
    result = service.run_tool(
        "qimen",
        {"date": "2028-04-06", "time": "09:33:00", "zone": "8", "lat": "31n13", "lon": "121e28"},
        save_result=True,
        query_text=question,
    )
    assert result.memory_ref is not None

    template = service.report_template({"run_id": result.memory_ref.run_id, "tool_name": "qimen"})
    assert template["question_analysis"]["focus_domains"] == ["career", "timing", "decision"]
    assert template["question_analysis"]["needs_timing"] is True
    assert template["question_analysis"]["needs_decision_support"] is True
    requirement_ids = {
        item["id"]
        for item in template["targeted_analysis_contract"]["targeted_answer_requirements"]
    }
    assert {"focus_career", "timing_window", "decision_support"}.issubset(requirement_ids)
    assert template["ai_fillable"]["targeted_answer_requirements"]

    ai_sections = [
        {
            "title": section["title"],
            "body": f"{section['title']} 用于判断事业换工作节奏与跳槽风险。",
            "evidence_lines": [section["title"]],
            "relevance_to_question": "直接服务于事业、时间窗口和是否跳槽的判断。",
        }
        for section in template["source_export_sections"]
    ]
    rendered = service.report_render(
        {
            "run_id": result.memory_ref.run_id,
            "tool_name": "qimen",
            "format": "json",
            "ai_report": {
                "analysis_focus": question,
                "direct_answer": "可以准备换工作，但需要等待更清晰的时间窗口再正式跳槽。",
                "executive_summary": "事业问题以先准备、后行动为宜。",
                "analysis_sections": ai_sections,
                "evidence": [{"source_section_title": template["source_export_sections"][0]["title"], "source_line": "奇门自检线索"}],
                "recommendations": ["先整理作品和资源，再选择合适窗口投递。"],
                "limitations": ["真实决策仍需结合行业机会与个人现实约束。"],
                "follow_up_questions": ["可以继续追问具体月份或目标公司方向。"],
            },
        }
    )

    report_payload = json.loads(Path(rendered["artifact_path"]).read_text(encoding="utf-8"))
    assert report_payload["delivery_checklist"]["ready_to_deliver"] is True
    assert report_payload["delivery_checklist"]["checks"]["has_targeted_requirements"] is True
    assert report_payload["targeted_analysis_contract"]["question_analysis"]["focus_domains"] == ["career", "timing", "decision"]
    assert report_payload["report_index"]["ready_to_deliver"] is True
    assert report_payload["report_index"]["delivery_missing"] == []
    report_requirement_ids = {
        item["id"]
        for item in report_payload["report_index"]["targeted_answer_requirements"]
    }
    assert {"focus_career", "timing_window", "decision_support"}.issubset(report_requirement_ids)
    assert "时间窗口" in report_payload["search_index"]["keywords"]
    assert "决策建议" in report_payload["search_index"]["keywords"]
    assert "换工作" in report_payload["plain_text"]
    assert "跳槽" in report_payload["plain_text"]

    by_question = store.query_runs(text="跳槽", artifact_kind="report_json", include_payload=True)
    assert any(run["run_id"] == result.memory_ref.run_id for run in by_question)
    by_requirement = store.query_runs(text="时间窗口", artifact_kind="report_json", include_payload=False)
    assert any(run["run_id"] == result.memory_ref.run_id for run in by_requirement)
    stored = service.show_memory({"run_id": result.memory_ref.run_id, "include_payload": True})
    assert stored["ok"] is True
    assert stored["result"]["ai_answer_text"].startswith("可以准备换工作")
    assert stored["result"]["ai_answer_structured"]["analysis_focus"] == question
    assert stored["result"]["answer_meta"]["source"] == "report_render"
    assert stored["result"]["artifact_summary"]["has_reports"] is True
    assert stored["result"]["artifact_summary"]["latest_report"]["kind"] == "report_json"


def test_targeted_consultation_report_roundtrip_persists_and_retrieves_ai_analysis(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    service = HorosaSkillService(settings, client=FakeClient(), store=store, js_client=FakeJsClient())

    question = "这个人未来三年事业、财务和决策风险应该怎么判断？是否适合换工作或做更激进的投资？"
    result = service.run_tool(
        "qimen",
        {"date": "2028-04-06", "time": "09:33:00", "zone": "8", "lat": "31n13", "lon": "121e28"},
        save_result=True,
        query_text=question,
    )
    assert result.memory_ref is not None

    template = service.report_template({"run_id": result.memory_ref.run_id, "tool_name": "qimen"})
    assert template["question_analysis"]["focus_domains"] == ["career", "wealth", "timing", "decision"]
    source_title = template["source_export_sections"][0]["title"]
    ai_report = {
        "analysis_focus": question,
        "direct_answer": "结论上：可以准备换工作，但不宜裸辞；财务上不建议高杠杆或激进投资。",
        "executive_summary": "此局适合先做机会筛选和资源整理，等时间窗口清楚后再行动。",
        "consultation_basis": [
            "以奇门局的起局时间、值符值使、门星神仪和宫位互动作为判断依据。",
            "把事业、财务、风险和时间窗口分开判断，避免只给抽象结论。",
        ],
        "reading_steps": [
            "先确认用局和用户问题。",
            "再看事业相关宫位、门星神仪与动静变化。",
            "最后把财务风险、行动窗口和现实约束合并成建议。",
        ],
        "analysis_sections": [
            {
                "title": "事业策略",
                "body": "事业上可以主动准备换工作，但应先建立备选机会，不宜裸辞。",
                "evidence_lines": [source_title],
                "relevance_to_question": "直接回答是否适合换工作。",
            },
            {
                "title": "财务风险",
                "body": "财务判断偏保守，暂时不建议高杠杆、借贷扩张或激进投资。",
                "evidence_lines": [source_title],
                "relevance_to_question": "直接回答是否适合做更激进的投资。",
            },
            {
                "title": "行动窗口",
                "body": "更适合先观察机会质量，再选择阻力较小的窗口推进。",
                "evidence_lines": [source_title],
                "relevance_to_question": "给出时间和行动节奏。",
            },
        ],
        "evidence": [{"source_section_title": source_title, "source_line": "奇门起局与宫位线索"}],
        "recommendations": [
            "先整理简历、作品和目标岗位，再分批投递。",
            "投资部分以现金流安全为先，暂缓高杠杆配置。",
            "如果出现明确 offer，再结合薪资、团队和行业周期做最终决策。",
        ],
        "limitations": ["本报告提供决策辅助，不替代现实尽调、合同审核和财务规划。"],
        "follow_up_questions": ["可以继续追问具体月份、目标行业或某个 offer 是否值得接。"],
    }

    rendered_json = service.report_render(
        {
            "run_id": result.memory_ref.run_id,
            "tool_name": "qimen",
            "format": "json",
            "ai_report": ai_report,
        }
    )
    assert rendered_json["answer_writeback"]["ok"] is True
    rendered_docx = service.report_render({"run_id": result.memory_ref.run_id, "tool_name": "qimen", "format": "docx"})
    rendered_pdf = service.report_render({"run_id": result.memory_ref.run_id, "tool_name": "qimen", "format": "pdf"})

    report_payload = json.loads(Path(rendered_json["artifact_path"]).read_text(encoding="utf-8"))
    assert report_payload["report_index"]["ready_to_deliver"] is True
    assert report_payload["delivery_checklist"]["ready_to_deliver"] is True
    assert report_payload["report_quality"]["ready_for_human_reading"] is True
    assert report_payload["ai_report"]["analysis_focus"] == question
    assert "不宜裸辞" in report_payload["ai_report"]["direct_answer"]
    assert "高杠杆" in report_payload["plain_text"]
    assert "换工作" in report_payload["search_index"]["keywords"]
    assert "激进投资" in report_payload["search_index"]["keywords"]

    with zipfile.ZipFile(Path(rendered_docx["artifact_path"])) as archive:
        docx_text = re.sub("<[^>]+>", "", archive.read("word/document.xml").decode("utf-8"))
    assert "解读目标" in docx_text
    assert "起盘依据" in docx_text
    assert "解盘步骤" in docx_text
    assert "核心结论" in docx_text
    assert "事业策略" in docx_text
    assert "财务风险" in docx_text
    assert "不宜裸辞" in docx_text
    assert "高杠杆" in docx_text
    assert not any(term in docx_text for term in ["Run ID", "来源追溯", "report_metadata", "Horosa Skill"])
    assert Path(rendered_pdf["artifact_path"]).read_bytes().startswith(b"%PDF")

    shown = service.show_memory({"run_id": result.memory_ref.run_id, "include_payload": True})
    assert shown["ok"] is True
    stored_run = shown["result"]
    assert stored_run["ai_answer_text"] == ai_report["direct_answer"]
    assert stored_run["ai_answer_structured"]["analysis_focus"] == question
    assert stored_run["answer_meta"]["source"] == "report_render"
    artifact_kinds = {artifact["kind"] for artifact in stored_run["artifacts"]}
    assert {"tool_result", "report_json", "report_docx", "report_pdf", "run_manifest"}.issubset(artifact_kinds)
    assert stored_run["artifact_summary"]["has_reports"] is True
    assert stored_run["artifact_summary"]["counts_by_kind"]["report_json"] == 1
    assert stored_run["artifact_summary"]["counts_by_kind"]["report_docx"] == 1
    assert stored_run["artifact_summary"]["counts_by_kind"]["report_pdf"] == 1
    for artifact in stored_run["artifacts"]:
        assert artifact["exists"] is True
        assert artifact["file_size"] > 0
        assert artifact["sha256"]

    by_question = service.query_memory(
        {"text": "激进投资", "artifact_kind": "report_json", "include_payload": True, "limit": 5}
    )
    assert by_question["ok"] is True
    assert any(item["run_id"] == result.memory_ref.run_id for item in by_question["results"])
    matched = next(item for item in by_question["results"] if item["run_id"] == result.memory_ref.run_id)
    assert matched["artifact_summary"]["has_reports"] is True
    assert matched["artifacts"][0]["kind"] == "report_json"
    assert matched["artifacts"][0]["payload"]["report_index"]["ready_to_deliver"] is True
    assert "高杠杆" in json.dumps(matched["artifacts"][0]["payload"], ensure_ascii=False)

    by_answer = service.query_memory(
        {"text": "不宜裸辞", "tool": "qimen", "include_payload": False, "limit": 5}
    )
    assert by_answer["ok"] is True
    assert any(item["run_id"] == result.memory_ref.run_id for item in by_answer["results"])


def test_report_manifest_preserves_ai_answer_and_report_artifact_index(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    rendered = service.report_from_tool(
        {
            "tool_name": "bazi_birth",
            "payload": {
                "date": "1995-06-03",
                "time": "05:30:00",
                "zone": "+08:00",
                "lat": "31n13",
                "lon": "121e28",
                "gender": True,
            },
            "format": "json",
            "question": "未来三年事业和财务怎么规划？是否适合激进投资？",
            "ai_report": {
                "analysis_focus": "未来三年事业、财务和投资风险。",
                "direct_answer": "结论上：事业宜稳中求进，财务不宜激进投资。",
                "executive_summary": "先保现金流，再筛选更确定的机会。",
                "analysis_sections": [
                    {
                        "title": "事业规划",
                        "body": "适合准备机会，但不宜仓促转向。",
                        "evidence_lines": ["起盘信息"],
                        "relevance_to_question": "回应事业规划。",
                    },
                    {
                        "title": "财务规划",
                        "body": "不宜激进投资，应先控制风险和现金流。",
                        "evidence_lines": ["起盘信息"],
                        "relevance_to_question": "回应财务规划。",
                    },
                ],
                "recommendations": ["先保现金流。", "投资降低杠杆。"],
                "limitations": ["仍需结合现实收入、行业和负债情况。"],
                "evidence": [{"source_section_title": "起盘信息", "source_line": "样本起盘线索"}],
            },
        }
    )
    assert rendered["ok"] is True
    run_id = rendered["tool_result"]["memory_ref"]["run_id"]
    service.report_render({"run_id": run_id, "tool_name": "bazi_birth", "format": "docx"})
    service.report_render({"run_id": run_id, "tool_name": "bazi_birth", "format": "pdf"})

    shown = service.show_memory({"run_id": run_id, "include_payload": True})
    manifest_artifact = next(artifact for artifact in shown["result"]["artifacts"] if artifact["kind"] == "run_manifest")
    manifest = manifest_artifact["payload"]
    assert manifest["run"]["id"] == run_id
    assert manifest["run"]["user_question"] == "未来三年事业和财务怎么规划？是否适合激进投资？"
    assert manifest["run"]["ai_answer_text"] == "结论上：事业宜稳中求进，财务不宜激进投资。"
    assert manifest["run"]["ai_answer_structured"]["analysis_focus"] == "未来三年事业、财务和投资风险。"
    assert manifest["run"]["answer_meta"]["source"] == "report_render"
    manifest_kinds = {artifact["kind"] for artifact in manifest["artifacts"]}
    assert {"tool_result", "report_json", "report_docx", "report_pdf"}.issubset(manifest_kinds)
    manifest_paths = [Path(artifact["path"]) for artifact in manifest["artifacts"]]
    assert all(path.is_file() for path in manifest_paths)
    assert manifest["artifact_summary"]["has_reports"] is True
    assert manifest["artifact_summary"]["counts_by_kind"]["report_json"] == 1
    assert manifest["artifact_summary"]["counts_by_kind"]["report_docx"] == 1
    assert manifest["artifact_summary"]["counts_by_kind"]["report_pdf"] == 1
    for artifact in manifest["artifacts"]:
        assert artifact["exists"] is True
        assert artifact["file_size"] > 0
        assert artifact["sha256"]

    queried = service.query_memory(
        {"text": "激进投资", "artifact_kind": "run_manifest", "include_payload": True, "limit": 5}
    )
    assert queried["ok"] is True
    assert any(item["run_id"] == run_id for item in queried["results"])
    matched = next(item for item in queried["results"] if item["run_id"] == run_id)
    assert matched["artifacts"][0]["payload"]["run"]["ai_answer_text"].endswith("财务不宜激进投资。")


def test_report_question_analysis_understands_natural_timing_and_decision_words(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool(
        "qimen",
        {"date": "2028-04-06", "time": "09:33:00", "zone": "8", "lat": "31n13", "lon": "121e28"},
        save_result=True,
        query_text="重点分析事业、时间窗口、决策建议，并保留原始技法依据。",
    )
    assert result.memory_ref is not None

    template = service.report_template({"run_id": result.memory_ref.run_id, "tool_name": "qimen"})
    assert template["question_analysis"]["focus_domains"] == ["career", "timing", "decision"]
    assert "时间窗口" in template["question_analysis"]["keywords_detected"]
    assert "决策" in template["question_analysis"]["keywords_detected"]
    assert "建议" in template["question_analysis"]["keywords_detected"]
    assert template["question_analysis"]["needs_timing"] is True
    assert template["question_analysis"]["needs_decision_support"] is True
    requirement_ids = {
        item["id"]
        for item in template["targeted_analysis_contract"]["targeted_answer_requirements"]
    }
    assert {"focus_career", "timing_window", "decision_support"}.issubset(requirement_ids)


def test_late_zi_switch_threads_through_all_chart_flows(tmp_path) -> None:
    # 晚子时开关全链穿透：显式 0 抵达各端点；不传时键缺席（零默认漂移，后端按默认 1 起算）。
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    client = CaptureClient()
    service = HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=FakeJsClient())
    base = {"date": "2026-05-27", "time": "23:30:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "agent_confirmed_settings": True}

    # v0.40：bazi_birth 改本地引擎优先（不打 /bazi/birth），其两开关穿透本地引擎由
    # test_sync311_mingli.py::test_bazi_day_boundary_defaults_reach_local_engine 看守。
    cases = [
        ("ziwei_birth", "/ziwei/birth"),
        ("liureng_gods", "/liureng/gods"),
        ("nongli_time", "/nongli/time"),
        ("qimen", "/qimen/pan"),
        ("taiyi", "/taiyi/pan"),
        ("jinkou", "/jinkou/pan"),
    ]
    for tool_name, endpoint in cases:
        client.calls.clear()
        service.run_tool(tool_name, {**base, "lateZiHourUseNextDay": 0}, save_result=False)
        captured = [payload for ep, payload in client.calls if ep == endpoint]
        assert captured, f"{tool_name} 未调用 {endpoint}"
        assert captured[0].get("lateZiHourUseNextDay") == 0, f"{tool_name} 未穿透 lateZi 到 {endpoint}"

        client.calls.clear()
        service.run_tool(tool_name, dict(base), save_result=False)
        captured = [payload for ep, payload in client.calls if ep == endpoint]
        assert captured and "lateZiHourUseNextDay" not in captured[0], f"{tool_name} 缺省时不得发送 lateZi（零漂移）"

    # qimen 显式 after23NewDay=0 抵达权威引擎（此前 ken 调用收不到该开关）。
    client.calls.clear()
    service.run_tool("qimen", {**base, "after23NewDay": 0}, save_result=False)
    ken = [payload for ep, payload in client.calls if ep == "/qimen/pan"]
    assert ken and ken[0].get("after23NewDay") == 0

    # sanshiunited 显式开关透传三式子工具（六壬层随三式农历就地起课，不再打 /liureng/gods —— wave-3）。
    client.calls.clear()
    service.run_tool("sanshiunited", {**base, "lateZiHourUseNextDay": 0}, save_result=False)
    for endpoint in ("/qimen/pan", "/taiyi/pan", "/nongli/time"):
        captured = [payload for ep, payload in client.calls if ep == endpoint]
        assert captured and captured[0].get("lateZiHourUseNextDay") == 0, f"sanshiunited 未透传到 {endpoint}"


def test_operational_errors_carry_agent_recovery(tmp_path) -> None:
    # 运行时/传输类错误统一带 agent_recovery（可执行的修复指引），不再只丢技术字段。
    settings = Settings(
        server_root="http://127.0.0.1:1",  # 无监听端口 → transport.connection_error
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, store=MemoryStore(settings), js_client=FakeJsClient())
    result = service.run_tool(
        "nongli_time",
        {"date": "2028-04-06", "time": "09:33:00", "zone": "+08:00", "lon": "121e28", "agent_confirmed_settings": True},
        save_result=False,
    )
    assert result.ok is False
    assert result.error is not None
    recovery = (result.error.details or {}).get("agent_recovery")
    assert isinstance(recovery, dict) and recovery.get("prompt_to_user")
    assert "doctor" in json.dumps(recovery)


def test_preflight_skips_questions_for_provided_fields(tmp_path) -> None:
    # 闸按已提供字段过滤：用户已给出生数据时不再重复追问 date/time/location。
    from horosa_skill.agent_guidance import validate_agent_preflight

    gate_empty = validate_agent_preflight("chart", {})
    fields_when_empty = {str(item.get("field")) for item in gate_empty["ask_if_missing"]}

    gate_full = validate_agent_preflight(
        "chart",
        {"date": "1995-06-03", "time": "05:30", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
    )
    fields_when_full = {str(item.get("field")) for item in gate_full["ask_if_missing"]}
    assert gate_full["ok"] is False  # 仍需确认结果敏感设置（hsys/zodiacal 等仍在问）
    # 已提供的出生信息组不再出现在追问里；空 payload 时仍会问。
    assert "date/time/place" in fields_when_empty
    assert "date/time/place" not in fields_when_full
    assert "hsys" in fields_when_full


def test_dispatch_no_match_returns_candidates(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    # 「老黄历宜忌」自 v0.36.0 起有路由（huangli）；玄史是查询层工具，故意不进 dispatch 规则 → 只能靠候选建议到达。
    result = service.dispatch({"query": "查一下玄学史里的天象记录", "agent_confirmed_settings": True, "save_result": False})
    assert result.ok is False
    details = result.error.details or {}
    assert details.get("candidates") and details["candidates"][0] == "xuanshi"


def test_response_view_trims_payload_but_archives_full(tmp_path) -> None:
    # response_view=titles：返回体只留段标题索引；memory 存档仍是全量（可取回）。
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    base = {"date": "2028-04-06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "agent_confirmed_settings": True}

    result = service.run_tool("qimen", {**base, "response_view": "titles"})
    assert result.ok is True
    contract = result.data["export_snapshot"]
    assert contract["sections"] and all(set(section) == {"index", "title"} for section in contract["sections"])
    assert "export_text" not in contract
    assert result.data["snapshot_text"] == ""
    assert any("response_view" in warning for warning in result.warnings)
    # 存档保全量。
    shown = service.show_memory({"run_id": result.memory_ref.run_id, "include_payload": True})
    archived = None
    for artifact in shown["result"].get("artifacts", []):
        if artifact.get("kind") == "tool_result":
            archived = json.loads(Path(artifact["path"]).read_text(encoding="utf-8"))
            break
    assert archived and archived["data"]["snapshot_text"]
    assert archived["data"]["export_snapshot"]["export_text"]

    # sections 视图：标题+正文，剥结构化 data。
    result2 = service.run_tool("qimen", {**base, "response_view": "sections"}, save_result=False)
    sections2 = result2.data["export_snapshot"]["sections"]
    assert sections2 and all(set(section) == {"index", "title", "body"} for section in sections2)


def test_export_contract_is_deduplicated_single_copy(tmp_path) -> None:
    # 响应体去重锚：同一份快照只存 顶层 snapshot_text + export_snapshot.export_text 两份，
    # 冗余副本（export_format / raw_text / filtered_text / 内嵌 snapshot_text / sections.content）不复现。
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    result = service.run_tool(
        "qimen",
        {"date": "2028-04-06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "agent_confirmed_settings": True},
        save_result=False,
    )
    assert result.ok is True
    data = result.data
    assert isinstance(data["snapshot_text"], str) and data["snapshot_text"]
    assert "export_format" not in data
    contract = data["export_snapshot"]
    for redundant in ("raw_text", "filtered_text", "snapshot_text"):
        assert redundant not in contract, redundant
    assert contract["export_text"]
    assert contract["sections"]
    for section in contract["sections"]:
        assert "content" not in section
        assert section["title"]
    # 全文最多出现 2 份：顶层 snapshot_text + export_snapshot.export_text。
    serialized = json.dumps(data, ensure_ascii=False)
    probe = data["snapshot_text"][:24]
    assert probe and serialized.count(probe) <= 2


def test_report_render_replays_legacy_archive_shape(tmp_path) -> None:
    # 向后兼容锚：旧归档（data.export_format 副本、无新形状 export_snapshot）仍可出报告。
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    result = service.run_tool(
        "qimen",
        {"date": "2028-04-06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "agent_confirmed_settings": True},
        query_text="旧归档回放",
    )
    run_id = result.memory_ref.run_id
    # 把归档改写成旧形状：export_snapshot → export_format（含彼时的 snapshot_text 内嵌份）。
    shown = service.show_memory({"run_id": run_id, "include_payload": True})
    artifact_path = None
    for artifact in shown["result"].get("artifacts", []):
        if artifact.get("kind") == "tool_result":
            artifact_path = artifact.get("path")
            break
    assert artifact_path
    archive = json.loads(Path(artifact_path).read_text(encoding="utf-8"))
    data = archive["data"]
    # 还原旧归档形状：export_snapshot 带冗余全文键 + export_format 完整副本并存。
    legacy_snapshot = dict(data["export_snapshot"])
    legacy_snapshot["raw_text"] = data.get("snapshot_text")
    legacy_snapshot["filtered_text"] = legacy_snapshot.get("export_text")
    legacy_snapshot["snapshot_text"] = data.get("snapshot_text")
    data["export_snapshot"] = legacy_snapshot
    data["export_format"] = {
        "technique": legacy_snapshot["technique"],
        "selected_sections": legacy_snapshot["selected_sections"],
        "format_source": legacy_snapshot["format_source"],
        "snapshot_text": data.get("snapshot_text"),
        "bundle_version": legacy_snapshot.get("bundle_version"),
        "provenance": legacy_snapshot.get("provenance"),
        "citation": legacy_snapshot.get("citation"),
        "sections": [
            {**{k: v for k, v in section.items() if k != "raw_title"}, "content": f"[{section['title']}]"}
            for section in legacy_snapshot["sections"]
        ],
    }
    Path(artifact_path).write_text(json.dumps(archive, ensure_ascii=False), encoding="utf-8")

    rendered = service.report_render(
        {
            "run_id": run_id,
            "tool_name": "qimen",
            "format": "json",
            "ai_report": {"executive_summary": "旧归档也能出报告。", "answer_text": "结论：可以推进。"},
        }
    )
    assert rendered["ok"] is True


def test_service_emits_trace_and_provenance_for_tool_results(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        trace_dir=tmp_path / "traces",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool(
        "chart",
        {"date": "1990-01-01", "time": "12:00", "zone": "8", "lat": "31n14", "lon": "121e28"},
        save_result=True,
        evaluation_case_id="chart_case",
    )

    assert result.trace_id
    assert result.group_id
    assert result.memory_ref is not None
    assert result.memory_ref.trace_id == result.trace_id
    assert result.memory_ref.group_id == result.group_id
    assert result.data["export_snapshot"]["provenance"]["source_domain"] == "xingque_ai_export"
    assert result.data["export_snapshot"]["provenance"]["bundle_version"] == result.data["export_snapshot"]["bundle_version"]
    # 唯一导出契约：export_format 副本不再产出。
    assert "export_format" not in result.data
    assert settings.trace_dir.exists()
    trace_files = sorted(settings.trace_dir.glob("*.jsonl"))
    assert trace_files
    assert result.trace_id in trace_files[0].read_text(encoding="utf-8")


def test_knowledge_results_include_provenance(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool("knowledge_read", {"domain": "qimen", "category": "door", "key": "休门"}, save_result=False)

    assert result.ok is True
    assert result.data["bundle_version"] == 1
    assert result.data["provenance"]["domain"] == "qimen"
    assert result.data["provenance"]["category"] == "door"
    assert result.data["citation"] == "Xingque hover knowledge · qimen/door/休门"


def test_dispatch_emits_group_trace_for_children(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        trace_dir=tmp_path / "traces",
    )
    store = MemoryStore(settings)
    service = HorosaSkillService(settings, client=FakeClient(), store=store, js_client=FakeJsClient())

    result = service.dispatch(
        {
            "query": "请用奇门和六壬综合分析",
            "birth": {"date": "2028/04/06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
            "save_result": True,
        },
        evaluation_case_id="dispatch_case",
    )

    assert result.trace_id
    assert result.group_id
    for item in result.results.values():
        assert item.group_id == result.group_id
        assert item.trace_id
    queried = store.query_runs(run_id=result.memory_ref.run_id, include_payload=True)
    assert queried[0]["group_id"] == result.group_id


def test_run_tool_wraps_unexpected_exception_into_error_envelope(tmp_path) -> None:
    """Regression: an unexpected (non-HorosaSkillError) exception during tool execution or
    snapshot/summary/export post-processing must surface as a clean ok=False envelope
    (`tool.internal_error`), never crash the CLI / break the MCP session / abort a dispatch."""

    class ExplodingClient(FakeClient):
        def call(self, endpoint: str, payload: dict) -> dict:
            # `/chart` is rewritten to "/" by _chart_server_endpoint before reaching the
            # client, so raise on both forms to be robust.
            if endpoint in {"/chart", "/"}:
                raise ValueError("boom from backend")
            return super().call(endpoint, payload)

    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=ExplodingClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool(
        "chart",
        {"date": "1990-01-01", "time": "12:00", "zone": "+08:00", "lat": "31n14", "lon": "121e28"},
        save_result=False,
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "tool.internal_error"
    assert "boom from backend" in result.error.message
    assert result.error.details.get("exception_type") == "ValueError"


# --- 择日搜索族（上游 v3.7.0 tianxing / v3.7.1 qimenzeri）--------------------------------------


def _zeri_service(tmp_path):
    settings = Settings(
        server_root="http://127.0.0.1:9999", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs"
    )
    return HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())


def test_tianxing_splits_by_month_and_stitches(tmp_path) -> None:
    """窗口超 93 天必须切分（后端单请求硬顶），且缝合回一份区间表。"""
    service = _zeri_service(tmp_path)
    calls: list[dict] = []
    original = service.client.call

    def spy(endpoint: str, payload: dict) -> dict:
        if endpoint == "/electionscan/scan":
            calls.append(payload)
        return original(endpoint, payload)

    service.client.call = spy  # type: ignore[method-assign]
    result = service.run_tool("tianxing", build_sample_payloads()["tianxing"], save_result=False)
    assert result.ok is True, result.error
    assert len(calls) == 2, "跨月窗口必须切成多段请求"
    assert result.data["stats"]["segments"] == 2
    assert result.data["hit_count"] == len(result.data["intervals"]) == 2


def test_tianxing_fails_loudly_on_electionscan_error_envelope(tmp_path) -> None:
    """端点 HTTP 200 回 {'err': …}；没有守卫时会静默退化成「零命中」——那是一个看起来合理的假结果。"""
    service = _zeri_service(tmp_path)
    payload = {**build_sample_payloads()["tianxing"], "startDate": "1999-01-01", "endDate": "1999-03-01"}
    result = service.run_tool("tianxing", payload, save_result=False)
    assert result.ok is False, "span_too_large 必须报错，绝不能变成零命中"
    assert result.error.code == "tool.electionscan_failed"
    assert result.error.details["scan_error"]["err"] == "span_too_large"


def test_tianxing_rejects_invalid_conditions_before_any_http(tmp_path) -> None:
    service = _zeri_service(tmp_path)
    payload = {**build_sample_payloads()["tianxing"]}
    payload.pop("conditions")
    result = service.run_tool("tianxing", payload, save_result=False)
    assert result.ok is False
    assert result.error.code == "tool.tianxing_missing_conditions"


def test_tianxing_explain_at_appends_section_and_tree(tmp_path) -> None:
    """explainAt（v0.33.0）：结果多 explain 键 + 快照尾追 [单时判读]；t 归一 '-'→'/'、缺秒补 ':00'。"""
    service = _zeri_service(tmp_path)
    seen: list[dict] = []
    original = service.client.call

    def spy(endpoint: str, payload: dict) -> dict:
        if endpoint == "/electionscan/explain":
            seen.append(payload)
        return original(endpoint, payload)

    service.client.call = spy  # type: ignore[method-assign]
    payload = {**build_sample_payloads()["tianxing"], "explainAt": "2028-04-01 00:01"}
    result = service.run_tool("tianxing", payload, save_result=False)
    assert result.ok is True, result.error
    # [Q-453] 缺省另为命中清单前 3 行预取判读树（t = row.pick），用户 explainAt 那一次要按 t 找。
    user_calls = [p for p in seen if p["t"] == "2028/04/01 00:01:00"]
    assert user_calls, "t 必须照上游 explainInterval 归一"
    assert user_calls[0].get("conditions"), "explain 必须带编译后的条件树"
    explain = result.data["explain"]
    assert explain["tree"]["kind"] == "group" and explain["tree"]["children"], "判读树必须原样带回"
    text = result.data["snapshot_text"]
    assert "[单时判读]" in text and text.index("[单时判读]") > text.index("[命中区间]"), "段须追加在快照尾部"
    assert "设定" in text and "实际" in text
    export = result.data["export_snapshot"]
    assert "单时判读" in export["section_titles_detected"]
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []


def test_tianxing_without_explain_at_emits_no_explain_key(tmp_path) -> None:
    """条件段零回归：未给 explainAt 时无 explain 键、无 [单时判读] 段、不打 /electionscan/explain。"""
    service = _zeri_service(tmp_path)
    calls: list[str] = []
    original = service.client.call
    service.client.call = lambda e, p: (calls.append(e) or original(e, p))  # type: ignore[method-assign]
    result = service.run_tool("tianxing", build_sample_payloads()["tianxing"], save_result=False)
    assert result.ok is True, result.error
    assert "explain" not in result.data
    assert "[单时判读]" not in (result.data["snapshot_text"] or "")
    # [Q-453] 缺省仍会为命中清单前 3 行预取判读树（上游 prefetchSnapshotExplains，进 [命中区间] 行内，
    # 不是 [单时判读]）→ 恰 min(3, 命中数) 次。zeriSnapshotExplainRows=0 时一次不打（见 test_sync311_divination）。
    assert calls.count("/electionscan/explain") == min(3, result.data["hit_count"])
    assert "单时判读" not in result.data["export_snapshot"]["missing_selected_sections"]


def test_tianxing_invalid_conditions_error_carries_server_types(tmp_path) -> None:
    """条件树编译失败时（自愈式报错），details 附服务端 /electionscan/conditiontypes 实现集。"""

    class RejectingJs(FakeJsClient):
        def run(self, tool_name: str, payload: dict[str, object]) -> dict:
            if tool_name == "tianxing" and str(payload.get("action")) == "compile":
                return {"data": {"ok": False, "error": {"code": "invalid_conditions", "message": "「相位」条件：planetA 缺失"}}}
            return super().run(tool_name, payload)

    settings = Settings(
        server_root="http://127.0.0.1:9999", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs"
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=RejectingJs())
    result = service.run_tool("tianxing", build_sample_payloads()["tianxing"], save_result=False)
    assert result.ok is False
    assert result.error.code == "tool.tianxing_invalid_conditions"
    assert result.error.details["server_condition_types"] == ["aspect", "in_sign", "numeric"]


def test_cetian_text_key_appends_classics(tmp_path) -> None:
    """批 I-5：textKey=list 出目录 / 单篇出原文；未给不打 /cetian/texts。"""
    service = _zeri_service(tmp_path)
    calls: list[str] = []
    original = service.client.call
    service.client.call = lambda e, p: (calls.append(e) or original(e, p))  # type: ignore[method-assign]
    base = {"date": "1998-02-20", "time": "20:48", "gender": 1}
    plain = service.run_tool("cetian", base, save_result=False)
    assert plain.ok is True, plain.error
    assert "/cetian/texts" not in calls and "[判词原文]" not in plain.data["snapshot_text"]
    listing = service.run_tool("cetian", {**base, "textKey": "list"}, save_result=False)
    assert listing.ok is True, listing.error
    assert "判词库 2 篇" in listing.data["snapshot_text"] and "照胆经叙跋" in listing.data["snapshot_text"]
    one = service.run_tool("cetian", {**base, "textKey": "keying"}, save_result=False)
    assert "《克应歌》（keying）" in one.data["snapshot_text"] and "克应之说最玄微" in one.data["snapshot_text"]
    bad = service.run_tool("cetian", {**base, "textKey": "nope"}, save_result=False)
    assert bad.ok is False and bad.error.code == "tool.cetian_text_unknown_key"
    export = one.data["export_snapshot"]
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []


def test_wangji_xinyi_casting_methods(tmp_path) -> None:
    """批 I-5 → sync311 F15：所选心易法的卦面按上游进 [心易发微]（buildHuangJiSnapshotForFields），
    不再另起 skill 自造的 [心易起卦] 段（该段名上游 preset 里没有）。"""
    service = _zeri_service(tmp_path)
    base = {"date": "1998-02-20", "time": "20:48"}
    plain = service.run_tool("wangji", base, save_result=False)
    assert plain.ok is True, plain.error
    assert "[心易起卦]" not in plain.data["snapshot_text"]
    cast = service.run_tool("wangji", {**base, "xinyiMethod": "number", "upperNum": 7, "lowerNum": 12}, save_result=False)
    assert cast.ok is True, cast.error
    text = cast.data["snapshot_text"]
    assert "[心易起卦]" not in text and "[心易发微]\n本卦：頤" in text
    assert cast.data["xinyi"]["result"]["本卦"] == "頤" and cast.data["xinyi"]["method"] == "number"
    export = cast.data["export_snapshot"]
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []


def test_geomancy_include_catalog(tmp_path) -> None:
    """批 I-5：includeCatalog=true 产 [十六卦目录]（属性总表）；缺省零回归。"""
    service = _zeri_service(tmp_path)
    base = build_sample_payloads()["geomancy"]
    plain = service.run_tool("geomancy", base, save_result=False)
    assert plain.ok is True, plain.error
    assert "[十六卦目录]" not in plain.data["snapshot_text"]
    rich = service.run_tool("geomancy", {**base, "includeCatalog": True}, save_result=False)
    assert rich.ok is True, rich.error
    text = rich.data["snapshot_text"]
    assert "[十六卦目录]" in text and "道路（Via）" in text and "五行 水" in text and "主星 太阴" in text
    assert "●" in text, "卦形点须渲染"
    assert rich.data["catalog"]["figures"]
    export = rich.data["export_snapshot"]
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []


def test_acg_click_point_and_event_conditional_sections(tmp_path) -> None:
    """批 I-4：clickLat/clickLon → [落点分析]；eventKind → [事件时刻]；缺省两段不产、不打端点。"""
    service = _zeri_service(tmp_path)
    calls: list[str] = []
    original = service.client.call
    service.client.call = lambda e, p: (calls.append(e) or original(e, p))  # type: ignore[method-assign]
    base = build_sample_payloads()["acg"]
    plain = service.run_tool("acg", base, save_result=False)
    assert plain.ok is True, plain.error
    assert "/location/acgpoint" not in calls and "/location/acgevent" not in calls
    assert "[落点分析]" not in plain.data["snapshot_text"] and "[事件时刻]" not in plain.data["snapshot_text"]
    rich = service.run_tool(
        "acg", {**base, "clickLat": 40.7, "clickLon": -74.0, "eventKind": "solar_eclipse"}, save_result=False
    )
    assert rich.ok is True, rich.error
    text = rich.data["snapshot_text"]
    assert "[落点分析]" in text and "[事件时刻]" in text
    assert "北交 临 Asc（距 1.27°）" in text
    assert "重置四角：" in text and "宿命点" in text
    assert "日食（next）：2027/02/06 15:59:39 UTC" in text
    assert rich.data["acg"]["point"]["hits"] and rich.data["acg"]["event"]["date"] == "2027/02/06"
    export = rich.data["export_snapshot"]
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []


def test_planet_cycles_renders_timeline(tmp_path) -> None:
    """批 I-3：行星周期两段恒出；事件行 = UT 时刻 + 黄经度分（_sign_degree）。"""
    service = _zeri_service(tmp_path)
    result = service.run_tool("planet_cycles", build_sample_payloads()["planet_cycles"], save_result=False)
    assert result.ok is True, result.error
    assert result.data["cycles"]["events"]
    text = result.data["snapshot_text"]
    assert "[周期配置]" in text and "[会合事件]" in text
    assert "木星-土星" in text and "合" in text and "地心" in text
    assert "2020-12-21 18:20（UT）" in text and "宝瓶" in text, "2020 大合相在宝瓶 0°29′"
    export = result.data["export_snapshot"]
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []


def test_jieqi_birth_marks_bracketing_terms(tmp_path) -> None:
    """批 I-3：出生节气窗——节/气标注 + 出生所落区间（纯时刻比较）。"""
    service = _zeri_service(tmp_path)
    result = service.run_tool("jieqi_birth", build_sample_payloads()["jieqi_birth"], save_result=False)
    assert result.ok is True, result.error
    text = result.data["snapshot_text"]
    assert "[出生节气窗]" in text
    assert "清明（节）　2028-04-04 15:02:44" in text
    assert "谷雨（气）" in text
    assert "出生落于 清明（2028-04-04 15:02:44）与 谷雨（2028-04-19 22:08:00）之间" in text
    export = result.data["export_snapshot"]
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []


def test_extrareturns_timeline_conditional_section(tmp_path) -> None:
    """批 I-3：timelineStartYear/timelineCount 才产 [日月返照年表]；缺省不打 /astroextra/returns。"""
    service = _zeri_service(tmp_path)
    calls: list[str] = []
    original = service.client.call
    service.client.call = lambda e, p: (calls.append(e) or original(e, p))  # type: ignore[method-assign]
    plain = service.run_tool("extrareturns", build_sample_payloads()["extrareturns"], save_result=False)
    assert plain.ok is True, plain.error
    assert "/astroextra/returns" not in calls
    assert "[日月返照年表]" not in (plain.data["snapshot_text"] or "")
    dated = service.run_tool(
        "extrareturns", {**build_sample_payloads()["extrareturns"], "timelineStartYear": 2026, "timelineCount": 1},
        save_result=False,
    )
    assert dated.ok is True, dated.error
    assert "/astroextra/returns" in calls
    text = dated.data["snapshot_text"]
    assert "[日月返照年表]" in text
    assert "2026：日返 2026-06-02 17:35:27（升 26˚天蝎15分）" in text
    assert dated.data["timeline"][0]["year"] == 2026
    export = dated.data["export_snapshot"]
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []


def test_india_rectify_emits_five_sections_with_upstream_vocabulary(tmp_path) -> None:
    """批 I-2：生时校正五段恒出，语汇照上游校时器（校时之靶/采样/总-RP-PP/免责声明原样）。"""
    service = _zeri_service(tmp_path)
    result = service.run_tool("india_rectify", build_sample_payloads()["india_rectify"], save_result=False)
    assert result.ok is True, result.error
    assert result.data["rectify"]["available"] is True
    text = result.data["snapshot_text"]
    for section in ("[起盘信息]", "[校时扫描]", "[Lagna 子主区段]", "[候选榜]", "[声明]"):
        assert section in text, section
    assert "校时之靶 · 2 段" in text
    assert "罗睺：11:50:00 ~ 11:56:00（4 采样）" in text, "KP 主星须走罗睺/计都中文口径"
    assert "总 13　RP 6/6　PP good" in text
    assert "⚠ Lagna 落界" in text, "gandanta 边界预警必须上榜行"
    assert "半自动校时:输出证据与排序,采信与「采用」由用户决定" in text, "免责声明须原样带回"
    export = result.data["export_snapshot"]
    assert export["technique"]["key"] == "india_rectify"
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []


def test_india_rectify_fails_loudly_when_unavailable(tmp_path) -> None:
    class UnavailableClient(FakeClient):
        def call(self, endpoint: str, payload: dict) -> dict:
            if endpoint == "/india/rectify":
                return {"available": False, "reason": "scan_error"}
            return super().call(endpoint, payload)

    settings = Settings(
        server_root="http://127.0.0.1:9999", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs"
    )
    service = HorosaSkillService(settings, client=UnavailableClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    result = service.run_tool("india_rectify", build_sample_payloads()["india_rectify"], save_result=False)
    assert result.ok is False
    assert result.error.code == "tool.india_rectify_failed"


def test_persiandirected_datetime_appends_directed_chart_section(tmp_path) -> None:
    """批 I-2：datetime 时 /predict/persianchart 整铸 + [指定日期向运盘] 段；缺省不打端点（零回归）。"""
    service = _zeri_service(tmp_path)
    calls: list[str] = []
    original = service.client.call
    service.client.call = lambda e, p: (calls.append(e) or original(e, p))  # type: ignore[method-assign]
    base = {"date": "1995-06-03", "time": "05:30", "zone": "+08:00", "lat": "31n13", "lon": "121e28"}
    plain = service.run_tool("persiandirected", base, save_result=False)
    assert plain.ok is True, plain.error
    assert "/predict/persianchart" not in calls
    assert "directed_chart" not in plain.data
    assert "\n[指定日期向运盘]\n" not in plain.data["snapshot_text"]
    dated = service.run_tool("persiandirected", {**base, "datetime": "2026-09-01"}, save_result=False)
    assert dated.ok is True, dated.error
    assert "/predict/persianchart" in calls
    assert dated.data["directed_chart"]["chart"]["objects"]
    text = dated.data["snapshot_text"]
    assert "[指定日期向运盘]" in text and text.index("[指定日期向运盘]") > text.index("[波斯向运（Persian Directed）]")
    assert "向运太阳" in text
    export = dated.data["export_snapshot"]
    assert "指定日期向运盘" in export["section_titles_detected"]
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []


def test_qizhengelection_pan_emits_sections_and_data(tmp_path) -> None:
    """七政择日动盘（批 I-1b）：pan 出 [起盘信息]+[择日动盘]+[天象要素]，契约零缺零未知。"""
    service = _zeri_service(tmp_path)
    result = service.run_tool("qizhengelection", build_sample_payloads()["qizhengelection"], save_result=False)
    assert result.ok is True, result.error
    assert result.data["action"] == "pan"
    assert result.data["pan"]["planets"], "pan 原始数据必须带回"
    text = result.data["snapshot_text"]
    for section in ("[起盘信息]", "[择日动盘]", "[天象要素]"):
        assert section in text, section
    export = result.data["export_snapshot"]
    assert export["technique"]["key"] == "qizhengelection"
    assert export["missing_selected_sections"] == []
    assert export["unknown_detected_sections"] == []


def test_qizhengelection_eclipses_action(tmp_path) -> None:
    service = _zeri_service(tmp_path)
    payload = {**build_sample_payloads()["qizhengelection"], "action": "eclipses", "kind": "solar", "count": 2}
    result = service.run_tool("qizhengelection", payload, save_result=False)
    assert result.ok is True, result.error
    assert len(result.data["eclipses"]) == 2
    assert "[日月食搜索]" in result.data["snapshot_text"]
    # 夹具 JS 客户端不产 [星曜庙旺…]（另一条 optional）；只断言三段 moira 段不再缺席
    assert not ({"虚实", "本命化曜", "流年流曜"} & set(result.data["export_snapshot"]["missing_selected_sections"]))


def test_qizhengelection_azimuthsearch_requires_target(tmp_path) -> None:
    service = _zeri_service(tmp_path)
    payload = {**build_sample_payloads()["qizhengelection"], "action": "azimuthsearch"}
    result = service.run_tool("qizhengelection", payload, save_result=False)
    assert result.ok is False
    assert result.error.code == "tool.qizhengelection_missing_target"
    ok = service.run_tool("qizhengelection", {**payload, "targetAz": 180}, save_result=False)
    assert ok.ok is True, ok.error
    assert ok.data["hits"] and "[方位搜索]" in ok.data["snapshot_text"]


def test_qizhengelection_fails_loudly_on_error_envelope(tmp_path) -> None:
    """HTTP 200 + {'ResultCode':-1,'Result':'… failed'} 必须报错，绝不能静默变空结果。"""

    class FailingClient(FakeClient):
        def call(self, endpoint: str, payload: dict) -> dict:
            if endpoint == "/qizhengelection/eclipses":
                return {"ResultCode": -1, "Result": "eclipse search failed"}
            return super().call(endpoint, payload)

    settings = Settings(
        server_root="http://127.0.0.1:9999", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs"
    )
    service = HorosaSkillService(settings, client=FailingClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    payload = {**build_sample_payloads()["qizhengelection"], "action": "eclipses"}
    result = service.run_tool("qizhengelection", payload, save_result=False)
    assert result.ok is False
    assert result.error.code == "tool.qizhengelection_failed"
    assert "eclipse search failed" in str(result.error.details.get("error"))


def test_qimenzeri_carries_qimen_sections_plus_three(tmp_path) -> None:
    """21 段 = 奇门 18 + 择日 3（v13：奇门侧多了条件段 日家占方）；八宫克应 是 default-off，
    既不该被检出也不该记为缺段。段表仍由 qimen 的 preset spread 派生 —— 单一真值源不变。"""
    service = _zeri_service(tmp_path)
    result = service.run_tool("qimenzeri", build_sample_payloads()["qimenzeri"], save_result=False)
    assert result.ok is True, result.error
    export = result.data["export_snapshot"]
    assert export["technique"]["key"] == "qimenzeri"
    assert len(export["technique"]["preset_sections"]) == 21
    assert "日家占方（古籍金函系）" in export["technique"]["preset_sections"]
    for title in ("择日搜索配置", "择日条件", "命中时辰"):
        assert title in export["section_titles_detected"], title
    assert "八宫克应" not in export["missing_selected_sections"], "default-off 段不得记为缺段"
    assert export["missing_selected_sections"] == []
    assert export["unknown_detected_sections"] == []


def test_qimenzeri_discloses_the_split_compute_authority(tmp_path) -> None:
    """展示盘走 ken、区间搜索走本地引擎 —— 结果必须逐项写明，不许含糊成「都是 ken 算的」。"""
    service = _zeri_service(tmp_path)
    result = service.run_tool("qimenzeri", build_sample_payloads()["qimenzeri"], save_result=False)
    assert result.data["compute_sources"] == {"scan": "local_calcDunJia", "pan": "kinqimen"}
    # 起盘时刻取 pick（两端各内缩 1 分钟的边界安全值），不是 start —— 用 start 会落到时辰边界外侧。
    assert result.data["pan_moment"] == "2028-04-01 19:01"


def test_qimenzeri_rejects_oversized_span(tmp_path) -> None:
    service = _zeri_service(tmp_path)
    payload = {**build_sample_payloads()["qimenzeri"], "endDate": "2029-04-08"}
    result = service.run_tool("qimenzeri", payload, save_result=False)
    assert result.ok is False
    assert result.error.code == "tool.qimenzeri_span_too_large"
    assert "HOROSA_JS_ENGINE_TIMEOUT_SECONDS" in result.error.details["hint"]


def test_zero_hit_search_still_emits_the_hit_section(tmp_path) -> None:
    """零命中时上游写的是「无满足条件」这句真话，而不是丢段 —— 所以**搜索/命中这几段不是条件段**，
    不进 AI_EXPORT_OPTIONAL_SECTIONS。登记成 optional 等于拿一个真实回归探测器换零收益。

    ⚠ 断言口径是「这几段不许在 optional 里」，不是「optional 集必须为空」：v13 起 qimenzeri
    从 qimen spread 继承了真·条件段 日家占方（vendored DunJiaCalc 只在 pan.isJinhan 时出，
    且那时常规段一个都不出）。把整集断言成空，会逼下一个人要么删掉真条件段的登记、要么删掉本测试。
    """
    from horosa_skill.exports.registry import AI_EXPORT_OPTIONAL_SECTIONS

    never_optional = {
        "tianxing": ("起盘信息", "搜索配置", "条件", "命中区间"),
        "qimenzeri": ("择日搜索配置", "择日条件", "命中时辰"),
    }
    for key, titles in never_optional.items():
        optional = set(AI_EXPORT_OPTIONAL_SECTIONS.get(key) or ())
        leaked = sorted(optional.intersection(titles))
        assert leaked == [], f"{key} 的零命中仍出段，不该登记为条件段: {leaked}"

    service = _zeri_service(tmp_path)

    class NoHits(FakeJsClient):
        def run(self, tool_name: str, payload: dict) -> dict:
            out = super().run(tool_name, payload)
            if tool_name == "qimenzeri" and str(payload.get("action")) == "scan":
                out["data"] = {**out["data"], "intervals": [], "hit_count": 0}
            return out

    service.js_client = NoHits()
    result = service.run_tool("qimenzeri", build_sample_payloads()["qimenzeri"], save_result=False)
    assert result.ok is True, result.error
    assert result.data["hit_count"] == 0
    assert "命中时辰" in result.data["export_snapshot"]["section_titles_detected"]


# --- 占时起课的经纬度前置（v0.26.1）---------------------------------------------------------


def test_time_cast_tools_demand_geo_before_hitting_nongli(tmp_path) -> None:
    """五个占时工具此前把 `lat: null` 发给 /nongli/time → Java 回 200001 → 用户只看到一句
    「本地 Horosa 后端返回 HTTP 500」。现在缺 lon/lat 就提前报结构化错误，指名缺哪个。

    ⚠️ 这个 bug 曾被误诊为环境问题：Java 的农历结果按**年**缓存，任何一次带 lat 的请求都会焐热该年，
    此后同年无 lat 请求全部成功 —— 所以它表现为时好时坏。复现必须换冷年份。
    """
    service = _zeri_service(tmp_path)
    cases = {
        "xiaoliuren": {"date": "2031-05-20", "time": "12:30:00", "zone": "+08:00", "school": "dao", "askEvent": "问事"},
        "feigong": {"date": "2031-05-20", "time": "12:30:00", "zone": "+08:00", "qiMode": "hour", "askEvent": "求财"},
        "xiaochengtu": {"date": "2031-05-20", "time": "12:30:00", "zone": "+08:00", "qiguaFa": "time", "askEvent": "问事"},
        "guice": {"date": "2031-05-20", "time": "12:30:00", "zone": "+08:00", "qiguaFa": "time", "askEvent": "问事"},
        "zhengchuan": {"date": "2031-05-20", "time": "12:30:00", "zone": "+08:00", "school": "tieban", "gender": 1},
    }
    for tool, payload in cases.items():
        result = service.run_tool(tool, {**payload, "agent_confirmed_settings": True}, save_result=False)
        assert result.ok is False, f"{tool}: 缺 lat 时不该成功"
        assert result.error.code == f"tool.{tool}_cast_geo_required", f"{tool}: {result.error.code}"
        assert "lat" in result.error.details["missing"], tool


def test_time_cast_geo_guard_names_only_what_is_missing(tmp_path) -> None:
    service = _zeri_service(tmp_path)
    payload = {
        "date": "2031-05-20", "time": "12:30:00", "zone": "+08:00", "lon": "121e28",
        "school": "dao", "askEvent": "问事", "agent_confirmed_settings": True,
    }
    result = service.run_tool("xiaoliuren", payload, save_result=False)
    assert result.error.details["missing"] == ["lat"], "给了 lon 就不该再报 lon"


def test_java_result_codes_are_translated_not_swallowed() -> None:
    """`HorosaApiClient.call` 从不看 ResultCode，两个语义完全不同的失败都长成同一句 HTTP 500。"""
    from horosa_skill.engine.client import _java_result_code_hint

    assert "经纬度" in _java_result_code_hint('{"ResultCode" : 200001, "Result" : "param error"}')
    register = _java_result_code_hint('{"ResultCode" : 9999, "Result" : "no.register.app"}')
    # v0.36.0 收尾实锤：注册表是 jar 内 data/rsakey.json（RequestHeaderInterceptor 读），不在 Mongo
    assert "rsakey.json" in register and "无关" in register, register
    assert _java_result_code_hint('{"ResultCode" : 0, "Result" : {}}') == ""


def test_mongo_unreachable_9999_points_back_to_the_launch_mode() -> None:
    """第三种 9999（v0.36.0 收尾首次全量 live 抓到）：裸 `java -jar` 起的实例连 jar 内写死的 `mongodb.host`
    超时。它不是「本机无 Mongo」——按上游桌面模式起（--mongodb.ip + MONGO_OPTIONAL + 文件回退）Mongo 不在
    也全族真数据。提示必须指回起法，且不许污染另外两种 9999 的提示。"""
    from horosa_skill.engine.client import _java_result_code_hint

    body = ('{"ResultCode" : 9999, "Result" : "Timed out after 30000 ms while waiting to connect. Client view of '
            'cluster state is {type=UNKNOWN, servers=[{address=mongodb.host:27017, exception={com.mongodb.'
            'MongoSocketException: mongodb.host}, caused by {java.net.UnknownHostException: mongodb.host}}]"}')
    hint = _java_result_code_hint(body)
    assert "桌面模式" in hint and "start_vendored_instance.sh" in hint and "--mongodb.ip" in hint, hint
    assert "本机无 Mongo" not in hint, "不得把它定性成环境限制"
    # 负向对照：参数越界与 no.register.app 两种 9999 不得被 Mongo 分支抢走
    generic = _java_result_code_hint('{"ResultCode" : 9999, "Result" : "begin 1, end 3, length 1"}')
    register = _java_result_code_hint('{"ResultCode" : 9999, "Result" : "no.register.app.in.sys.forapp:1"}')
    assert "桌面模式" not in generic and "桌面模式" not in register
    assert "rsakey.json" in register


def test_generic_9999_is_not_labelled_a_mongo_problem() -> None:
    """9999 是通用失败码，不是 no.register.app 的同义词。

    Windows 构建机实测：缺 lat 触发的上游字符串越界回的是
    `{"ResultCode": 9999, "Result": "begin 1, end 3, length 1"}`（不是 mac 侧看到的 200001）。
    只按码值贴「app 注册没读到（在 MongoDB 里）」，会把一个参数 bug 指去查 Mongo——正是本仓
    连着两轮在清的那类误诊。认不出就给中性提示，不替用户断案。
    """
    from horosa_skill.engine.client import _java_result_code_hint

    hint = _java_result_code_hint('{"ResultCode" : 9999, "Result" : "begin 1, end 3, length 1"}')
    assert "MongoDB" not in hint, f"不得把参数 bug 指去查 Mongo: {hint}"
    assert "不等于" in hint, f"要显式否掉「9999 == app 注册问题」这个等式: {hint}"
    assert "Result" in hint and "lat" in hint, "中性提示要指向 Result 原文并提醒核经纬度"


# --- tianxing 三个「用户拿到错答案」的 bug（v0.26.1）------------------------------------------


def test_tianxing_forwards_top_level_classical_options(tmp_path) -> None:
    """古典口径既可走 options 字典、也可走 BirthInput 继承的**顶层**同名字段（schema 逐个带描述）。
    v0.26.0 只读 options → 顶层写法被静默丢弃，搜索用默认口径跑，结果不同却零报错。"""
    service = _zeri_service(tmp_path)
    sent: list[dict] = []
    original = service.client.call

    def spy(endpoint: str, payload: dict) -> dict:
        if endpoint == "/electionscan/scan":
            sent.append(payload)
        return original(endpoint, payload)

    service.client.call = spy  # type: ignore[method-assign]
    payload = {**build_sample_payloads()["tianxing"], "combustOrb": 15, "termsVariant": "ptolemy",
               "siderealAyanamsa": "fagan_bradley", "precision": "minute"}
    assert service.run_tool("tianxing", payload, save_result=False).ok is True
    assert sent, "没有发出扫描请求"
    first = sent[0]
    assert first["combustOrb"] == 15, "顶层 combustOrb 被丢了"
    assert first["termsVariant"] == "ptolemy", "顶层 termsVariant 被丢了"
    # 快照会把 siderealAyanamsa 印出来，所以它必须真的进请求，否则输出在声称一个没用上的设置
    assert first["siderealAyanamsa"] == "fagan_bradley", "siderealAyanamsa 没进请求，但快照会印它"
    assert first["precision"] == "minute", "precision 是个文档化了却没接线的死旋钮"


def test_tianxing_options_dict_wins_over_top_level(tmp_path) -> None:
    service = _zeri_service(tmp_path)
    sent: list[dict] = []
    original = service.client.call
    service.client.call = lambda e, p: (sent.append(p) if e == "/electionscan/scan" else None) or original(e, p)  # type: ignore[method-assign,assignment]
    payload = {**build_sample_payloads()["tianxing"], "combustOrb": 15, "options": {"combustOrb": 9}}
    service.run_tool("tianxing", payload, save_result=False)
    assert sent[0]["combustOrb"] == 9, "显式 options 应压过顶层"


def test_tianxing_forwards_every_key_the_backend_actually_reads(tmp_path) -> None:
    """白名单窄于后端实读集 = 在客户端把已修好的后端 bug 重新装回去。

    election_scan.scan 把整个请求体交给 perchart.push_classical_request（`_cls_req = dict(data)`），
    后者实读 nodeExaltation/dignityDebilities/lotsDocReverse/orbSystem/luminaryOrbBonus/
    customTermsDay/customTermsNight 等键；上游 [F8] 那条注释记的正是「dignityDebilities/orbSystem
    等发了不生效」，后端收编修好了，而 skill 的白名单窄 7 键又把它们静默滤掉 ——
    schema 上带着描述、chart 工具上照常生效，唯独天星择日搜索里无声失效。
    """
    service = _zeri_service(tmp_path)
    sent: list[dict] = []
    original = service.client.call
    service.client.call = lambda e, p: (sent.append(p) if e == "/electionscan/scan" else None) or original(e, p)  # type: ignore[method-assign,assignment]
    backend_read_keys = {
        "nodeExaltation": 1, "dignityDebilities": 0, "lotsDocReverse": 1,
        "orbSystem": "lilly", "luminaryOrbBonus": 2, "customTermsDay": "egyptian",
        "customTermsNight": "ptolemy",
    }
    payload = {**build_sample_payloads()["tianxing"], **backend_read_keys}
    assert service.run_tool("tianxing", payload, save_result=False).ok is True
    assert sent, "没有发出扫描请求"
    for key, value in backend_read_keys.items():
        assert sent[0].get(key) == value, f"{key} 被白名单滤掉了，但后端实读它"


def test_tianxing_js_failure_never_becomes_a_fabricated_export(tmp_path) -> None:
    """JS 侧失败时旧实现只读 snapshot_text → None → format_source 回落 generated_template，
    产出一份拿 payload YAML 填出来的伪造导出，而 agent 被要求只依据 export_text 解读。"""
    service = _zeri_service(tmp_path)

    class SnapshotBroken(FakeJsClient):
        def run(self, tool_name: str, payload: dict) -> dict:
            if tool_name == "tianxing" and str(payload.get("action")) == "snapshot":
                return {"data": {"ok": False, "error": {"code": "snapshot_failed", "message": "boom"}},
                        "snapshot_text": ""}
            return super().run(tool_name, payload)

    service.js_client = SnapshotBroken()
    result = service.run_tool("tianxing", build_sample_payloads()["tianxing"], save_result=False)
    assert result.ok is False, "JS 快照失败必须报错，不能伪造出一份导出"
    assert result.error.code == "tool.tianxing_snapshot_failed"


def test_tianxing_stitch_failure_is_not_reported_as_zero_hits(tmp_path) -> None:
    service = _zeri_service(tmp_path)

    class StitchBroken(FakeJsClient):
        def run(self, tool_name: str, payload: dict) -> dict:
            if tool_name == "tianxing" and str(payload.get("action")) == "stitch":
                return {"data": {"ok": False, "error": {"code": "stitch_failed", "message": "boom"}}}
            return super().run(tool_name, payload)

    service.js_client = StitchBroken()
    result = service.run_tool("tianxing", build_sample_payloads()["tianxing"], save_result=False)
    assert result.ok is False, "缝合失败会变成一个看起来完全合理的「零命中」"
    assert result.error.code == "tool.tianxing_stitch_failed"


def test_tianxing_rejects_unparseable_inverted_and_oversized_windows(tmp_path) -> None:
    """旧守卫用 `span is not None` 判 → 解析不出来的日期形状**直接跳过上限**；倒置窗口得负数，
    `负数 > max` 恒 False 也能溜过去。而 JS 侧 wallToMs 照样能解析它们，于是一路跑到超时。"""
    service = _zeri_service(tmp_path)
    base = build_sample_payloads()["tianxing"]
    cases = [
        ({"startDate": "2028-04-01T00:00", "endDate": "2032-12-31"}, "tool.tianxing_bad_window"),
        ({"startDate": "2028-04-01 10:00", "endDate": "2032-12-31"}, "tool.tianxing_bad_window"),
        ({"startDate": "2028-12-31", "endDate": "2028-01-01"}, "tool.tianxing_inverted_window"),
        ({"startDate": "2028-01-01", "endDate": "2038-01-01"}, "tool.tianxing_span_too_large"),
    ]
    for override, expected in cases:
        result = service.run_tool("tianxing", {**base, **override}, save_result=False)
        assert result.ok is False, f"{override} 不该放行"
        assert result.error.code == expected, f"{override}: {result.error.code}"


def _service(tmp_path) -> HorosaSkillService:
    """离线技法服务（FakeClient + FakeJsClient）——技法卡/技法报告用例共用。"""
    settings = Settings(
        server_root="http://127.0.0.1:9",
        chart_server_root="http://127.0.0.1:9",
        runtime_root=tmp_path / "runtime",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    return HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())


def test_technique_card_rides_every_technique_response_and_survives_response_view(tmp_path) -> None:
    """技法卡必须**随每次输出**给出，且 `response_view` 精简时也留着。

    精简模式恰恰是最需要溯源的场景（快照都不回了），把卡一起裁掉等于让它在唯一需要它的时候消失。
    """
    service = _service(tmp_path)
    payload = build_sample_payloads()["tarot"]
    result = service.run_tool("tarot", payload, save_result=True)
    card = result.data["technique_card"]
    assert card["schema"] == "horosa.skill.technique_card.v1"
    assert card["tool"] == "tarot"
    assert card["technique"]["key"] == "tarot"
    assert card["versions"]["skill"] and card["versions"]["export_settings"] == 16
    assert card["refs"]["run_id"] == result.memory_ref.run_id

    slim = service.run_tool("tarot", {**payload, "response_view": "titles"}, save_result=False)
    assert slim.data["snapshot_text"] == "", "response_view 该裁的还是要裁"
    assert slim.data["technique_card"]["tool"] == "tarot", "但技法卡不裁"


def test_technique_card_can_be_switched_off(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOROSA_TECHNIQUE_CARD", "0")
    service = _service(tmp_path)
    result = service.run_tool("tarot", build_sample_payloads()["tarot"], save_result=False)
    assert "technique_card" not in result.data


def test_technique_report_covers_a_whole_session_and_needs_no_ai_report(tmp_path) -> None:
    """与咨询报告的分界线：这份不需要 ai_report，也**永远**不含解读。"""
    service = _service(tmp_path)
    samples = build_sample_payloads()
    group_id = None
    for tool in ("tarot", "tongshefa"):
        result = service.run_tool(tool, samples[tool], save_result=True, group_id=group_id)
        group_id = group_id or result.group_id

    report = service.technique_report({"group_id": group_id, "format": "markdown"})
    assert report["ok"] is True
    assert report["technique_count"] == 2
    assert report["scope"] == "group"
    artifact = Path(report["artifact_path"])
    assert artifact.is_file() and artifact.stat().st_size > 0
    text = artifact.read_text(encoding="utf-8")
    assert "# 会话技法依据报告" in text
    assert "## 一致性检查" in text
    # 确定性文档：不许出现任何「解读/建议」字样的伪装——它不是咨询报告。
    assert "ai_report" not in text


def test_technique_report_refuses_cleanly_when_nothing_has_been_run(tmp_path) -> None:
    service = _service(tmp_path)
    with pytest.raises(ToolValidationError) as excinfo:
        service.technique_report({"format": "markdown"})
    assert excinfo.value.code == "report.technique.no_cards"


def test_technique_report_rejects_an_unknown_format(tmp_path) -> None:
    service = _service(tmp_path)
    with pytest.raises(ToolValidationError) as excinfo:
        service.technique_report({"format": "html"})
    assert excinfo.value.code == "report.technique.invalid_format"


# --- v0.28.0（上游 v3.9.2）：干支合冲 / 选中时刻星盘 ---------------------------------------------


# v0.40 F9：[干支合冲] 不再是 Python 手写 port（_build_bazi_hechong_lines 已删）—— 行由 vendored 上游
# buildBaziSnapshotText 的 relLine 逐字产出（BaZi.js:515-534），真引擎值级金标见 test_sync311_mingli.py。
def test_bazi_snapshot_carries_hechong_between_fenye_and_dayun(tmp_path) -> None:
    service = _service(tmp_path)
    result = service.run_tool("bazi_birth", build_sample_payloads()["bazi_birth"], save_result=False)
    assert result.ok is True
    titles = [s["title"] for s in result.data["export_snapshot"]["sections"]]
    assert "干支合冲" in titles
    assert titles.index("月令司令（分野）") < titles.index("干支合冲") < titles.index("大运")
    body = next(s["body"] for s in result.data["export_snapshot"]["sections"] if s["title"] == "干支合冲")
    assert "干合：丙（月） 辛（日）→丙辛合水" in body


def test_tianxing_selected_moment_chart_is_conditional_on_hits(tmp_path) -> None:
    """[选中时刻星盘]（v3.9.2）：有命中→补铸 /chart 并入（headerless 子段头 `· X`）；零命中→不产段
    且不误报 missing（条件段双登记）。"""
    service = _service(tmp_path)
    payload = build_sample_payloads()["tianxing"]
    hit = service.run_tool("tianxing", payload, save_result=False)
    assert hit.ok is True
    export = hit.data["export_snapshot"]
    assert "选中时刻星盘" in export["section_titles_detected"]
    body = next(s["body"] for s in export["sections"] if s["title"] == "选中时刻星盘")
    assert body.startswith("选中命中：")
    assert "· 起盘信息" in body, "整张盘 headerless 并入：子段头必须已转 `· X`，防被顶层拆段"
    assert "\n[" not in f"\n{body}", "段内不得残留顶层段头"

    # 零命中窗口（FakeClient 对 1999 起点回空 intervals）→ 段自然缺席、契约仍干净。
    miss = service.run_tool(
        "tianxing", {**payload, "startDate": "1997-01-02", "endDate": "1997-01-05"}, save_result=False
    )
    assert miss.ok is True
    miss_export = miss.data["export_snapshot"]
    assert "选中时刻星盘" not in miss_export["section_titles_detected"]
    assert miss_export["missing_selected_sections"] == []


# --- v0.28.0 B3：合参 horosa_hecan --------------------------------------------------------------


def test_hecan_routes_and_returns_a_synthesis_template(tmp_path) -> None:
    """合参 = 模板不是终稿：逐技法证据表 + 口径一致性 + ai_fillable 综合槽，分歧披露写进 instructions。"""
    service = _service(tmp_path)
    result = service.hecan({
        "query": "综合奇门和六壬分析当前事业局势",
        "birth": build_sample_payloads()["qimen"],
        "save_result": True,
    })
    assert result["ok"] is True
    assert result["schema"] == "horosa.skill.hecan.v1"
    assert set(result["selected_tools"]) == {"qimen", "liureng_gods"}
    rows = result["synthesis_contract"]["ai_fillable"]["cross_validation"]
    assert [r["tool"] for r in rows] == result["selected_tools"]
    assert all(r["conclusion"] == "" for r in rows), "结论槽必须留白给 AI——预填即伪造"
    instructions = "\n".join(result["synthesis_contract"]["instructions"])
    assert "分歧" in instructions and "不许平均" in instructions
    assert "只准引用" in instructions or "不许引用未导出" in instructions
    # 证据是指针不是全文（memory_show 取全量），响应不背 N 份快照。
    for tech in result["techniques"]:
        assert tech["evidence_pointer"]["read_with"] == "horosa_memory_show"
        assert "export_snapshot" not in tech
    assert result["consistency"]["setting_conflicts"] == []


def test_hecan_accepts_explicit_tools_and_caps_them(tmp_path) -> None:
    service = _service(tmp_path)
    result = service.hecan({
        "query": "全面看这个人",
        "tools": ["bazi_birth", "ziwei_birth", "liureng_gods", "qimen", "taiyi", "jinkou", "sixyao"],
        "max_tools": 3,
        "birth": build_sample_payloads()["bazi_birth"],
        "save_result": False,
    })
    assert result["ok"] is True
    assert result["selected_tools"] == ["bazi_birth", "ziwei_birth", "liureng_gods"], "上限必须截断"


def test_hecan_routing_failure_passes_through_recovery(tmp_path) -> None:
    service = _service(tmp_path)
    result = service.hecan({"query": "呵呵", "save_result": False})
    assert result["ok"] is False
    assert result["code"], "路由失败必须透出结构化错误，不包一层假成功"


def test_birthinput_declares_upstream_classical_echo_whitelist() -> None:
    """批 I-6 锁步：上游 helper.py 古典回显白名单（45 键）必须全部在 BirthInput typed 声明——
    typed 化是可发现性契约（agent 只能看见声明过的旋钮），删声明=旋钮对 agent 隐形。
    新键到达由重同步侦察负责；本测试防「已声明键被误删」的回退。"""
    from horosa_skill.schemas.tools import BirthInput

    upstream_echo_keys = {
        "termsVariant", "leoBoundFirst", "geminiBoundEmended", "triplicity", "lotReversal",
        "westNodeType", "sectBuffer", "houseCuspAdvance", "cazimiOrb", "combustOrb", "underBeamsOrb",
        "vocMode", "vocIncludeOuter", "starOrb", "starOrbMode", "antisciaOrb", "viaCombustaVariant",
        "lotsDocReverse", "nodeExaltation", "combustOwnChariotExempt", "westLilithType",
        "topocentricMoon", "stationMarking", "hermeticLotsReversal", "erosConstruction",
        "lotFortuneVariant", "lotFatherCombustAlt", "lotProjection", "dignityDebilities",
        "almutenTripMode", "planetaryHourMethod", "orbSystem", "luminaryOrbBonus",
        "aspectIncludeCusps", "aspectIncludeLots", "aspectIncludeMidpoints", "solarReturnVariant",
        "returnLatitudeMode", "vulcanCalc", "customTermsDay", "customTermsNight",
        "siderealAyanamsa", "userAyanT0", "userAyanDeg", "orbs", "orbScale",
    }
    declared = set(BirthInput.model_fields.keys())
    missing = sorted(upstream_echo_keys - declared)
    assert missing == [], f"BirthInput 缺少上游古典白名单键的 typed 声明：{missing}"


# ---- v0.36.0 A5 分后端就绪：Java 挂了不许先杀健康的 chart 服务再全量重启 ----
def _java_cooldown_service(tmp_path, runtime_manager: FakeRuntimeManager) -> tuple[HorosaSkillService, ProbeClient]:
    settings = Settings(server_root="http://127.0.0.1:9999", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    java_client = ProbeClient(probe_ok=False)  # Java 探针失败
    service = HorosaSkillService(
        settings,
        client=java_client,
        chart_client=FakeClient(),  # chart 服务健康（probe True）
        store=MemoryStore(settings),
        js_client=FakeJsClient(),
        runtime_manager=runtime_manager,
    )
    return service, java_client


def test_java_endpoint_fails_fast_during_cooldown_and_chart_tool_stays_up(tmp_path) -> None:
    from horosa_skill.testing_payloads import build_sample_payloads

    runtime_manager = FakeRuntimeManager(cooldown=90.0)
    service, java_client = _java_cooldown_service(tmp_path, runtime_manager)
    payloads = build_sample_payloads()

    # v0.40：bazi_birth 改本地引擎优先（不再是 Java 工具），Java 端点示例换成 nongli_time（/nongli/time 纯 Java）。
    bazi = service.run_tool("nongli_time", payloads["nongli_time"], save_result=False)
    assert bazi.ok is False
    assert bazi.error is not None and bazi.error.code == "runtime.java_backend_unavailable"
    assert bazi.error.details["retry_after_seconds"] == 90.0
    assert "doctor" in bazi.error.details["hint"]
    assert runtime_manager.started == 0  # 冷却期内：不重启、更不 stop 健康的 chart 服务
    assert java_client.probe_calls == 1

    chart = service.run_tool("chart", payloads["chart"], save_result=False)
    assert chart.ok is True, chart.error
    assert runtime_manager.started == 0


def test_java_endpoint_starts_once_and_does_not_restart_again_when_start_comes_back_degraded(tmp_path) -> None:
    from horosa_skill.testing_payloads import build_sample_payloads

    runtime_manager = FakeRuntimeManager(degraded=True, cooldown=0.0)
    service, _java_client = _java_cooldown_service(tmp_path, runtime_manager)
    bazi = service.run_tool("nongli_time", build_sample_payloads()["nongli_time"], save_result=False)  # v0.40：bazi 已本地优先
    assert bazi.ok is False
    assert bazi.error is not None and bazi.error.code == "runtime.java_backend_unavailable"
    # 此前：start(degraded) → 调用连不上 → connection_retry 再 start 一次（又杀一次 chart）。现在只起一次。
    assert runtime_manager.started == 1


# ---- v0.36.0 C1：guolao [虚实]/[本命化曜]/[流年流曜] 走 Java /qizheng/moira ----
def test_guolao_moira_sections_land_between_limit_and_patterns(tmp_path) -> None:
    settings = Settings(server_root="http://127.0.0.1:9999", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    client = CaptureClient()
    service = HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=FakeJsClient())
    result = service.run_tool(
        "guolao_chart",
        {"date": "1985-03-21", "time": "10:00:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28",
         "moiraTransitDate": "2026-09-04", "guolaoLifeMode": "yumao", "agent_confirmed_settings": True},
        save_result=False,
    )
    assert result.ok is True, result.error
    snap = result.data["snapshot_text"]
    for title in ("[虚实]", "[本命化曜]", "[流年流曜]"):
        assert title in snap, title
    assert snap.index("[大限]") < snap.index("[虚实]") < snap.index("[本命化曜]") < snap.index("[流年流曜]") < snap.index("[政余格局]")
    assert "流年干支：丙午" in snap  # 2026 = 丙午（Python _ganzhi_year 兜底）
    # 请求形状：流年盘二次铸盘 + moira 四键；lifeMode 透传
    moira_calls = [payload for endpoint, payload in client.calls if endpoint == "/qizheng/moira"]
    assert len(moira_calls) == 1
    assert set(moira_calls[0]) == {"params", "chartObj", "transitParams", "transitChartObj"}
    assert moira_calls[0]["params"]["guolaoLifeMode"] == "yumao" and moira_calls[0]["params"]["guolaoBodyMode"] == "taiyin"
    assert moira_calls[0]["transitParams"]["date"] == "2026-09-04" and moira_calls[0]["transitParams"]["predictive"] is True
    chart_calls = [payload for endpoint, payload in client.calls if endpoint in {"/chart", "/"}]  # chart 服务把 /chart 映射为 /
    # v0.40.0（sync311 w3b）：命度法非「占星上升」时 runner 会再向 Java /chart 取一次命度点 LifeMasterDeg74（上游 ChartController
    # 在 Python 排盘之上追加的对象）；夹具的 Java 盘没有它 → 命度落回上升并告警。所以 /chart 是三次：本命（chart 服务）、
    # 本命（Java，取命度点）、流年（chart 服务）；顺序不入契约。chart 服务载荷用斜杠日期。
    assert len(chart_calls) == 3
    natal_calls = [p for p in chart_calls if str(p["date"]).replace("/", "-") == "1985-03-21"]
    transit_calls = [p for p in chart_calls if str(p["date"]).replace("/", "-") == "2026-09-04"]
    assert len(natal_calls) == 2 and len(transit_calls) == 1
    assert any("LifeMasterDeg74" in f"{w}" for w in result.warnings), result.warnings
    assert result.data["guolaoMoiraRules"]["weakSolid"]["houses"][0]["house"] == "命宫"
    # 夹具 JS 客户端不产 [星曜庙旺…]（另一条 optional）；只断言三段 moira 段不再缺席
    assert not ({"虚实", "本命化曜", "流年流曜"} & set(result.data["export_snapshot"]["missing_selected_sections"]))
    assert not any("虚实" in w for w in result.warnings)


def test_guolao_moira_off_or_java_down_degrades_with_warning(tmp_path) -> None:
    settings = Settings(server_root="http://127.0.0.1:9999", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    # moiraRules=false：不打 /qizheng/moira，也不铸流年盘
    client = CaptureClient()
    service = HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=FakeJsClient())
    off = service.run_tool("guolao_chart", {"date": "1985-03-21", "time": "10:00:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "moiraRules": False, "agent_confirmed_settings": True}, save_result=False)
    assert off.ok and "[虚实]" not in off.data["snapshot_text"]
    assert not any(endpoint == "/qizheng/moira" for endpoint, _ in client.calls)
    assert len([1 for endpoint, _ in client.calls if endpoint in {"/chart", "/"}]) == 1

    # Java 在冷却期：/qizheng/moira 快速失败 → 三段缺席 + warnings 说明，主盘照出
    class JavaDownClient(CaptureClient):
        def call(self, endpoint: str, payload: dict) -> dict:
            if endpoint == "/qizheng/moira":
                raise ToolTransportError("down", code="runtime.java_backend_unavailable", details={})
            return super().call(endpoint, payload)

    service2 = HorosaSkillService(settings, client=JavaDownClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    down = service2.run_tool("guolao_chart", {"date": "1985-03-21", "time": "10:00:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "agent_confirmed_settings": True}, save_result=False)
    assert down.ok is True
    assert "[虚实]" not in down.data["snapshot_text"] and "[政余格局]" in down.data["snapshot_text"]
    assert any("[虚实]/[本命化曜]/[流年流曜] 本次未产出" in w for w in down.warnings), down.warnings


# ---- v0.36.0 C2：八字反查（Java /common/inversebazi）----
def test_bazi_inverse_returns_candidates_and_sections(tmp_path) -> None:
    from horosa_skill.agent_guidance import validate_agent_preflight

    settings = Settings(server_root="http://127.0.0.1:9999", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    client = CaptureClient()
    service = HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=FakeJsClient())
    result = service.run_tool("bazi_inverse", {"pillars": ["甲子", "丙寅", "戊辰", "庚申"], "count": 2, "fromYear": 2030}, save_result=False)
    assert result.ok is True, result.error
    model = result.data["bazi_inverse"]
    assert [c["date"] for c in model["candidates"]] == ["2024-02-15", "1964-02-29"]
    assert model["candidates"][0]["time"] == "15:30:00"
    call = next(payload for endpoint, payload in client.calls if endpoint == "/common/inversebazi")
    assert call == {"Year": "甲子", "Month": "丙寅", "Date": "戊辰", "Time": "庚申", "Count": 2, "Desc": True, "FromYear": 2030}
    snap = result.data["snapshot_text"]
    assert "[反查条件]" in snap and "[候选时刻]" in snap and "1. 2024-02-15 15:30:00" in snap
    assert result.data["export_snapshot"]["technique"]["key"] == "bazi_inverse"
    assert result.data["export_snapshot"]["missing_selected_sections"] == []
    assert result.summary[0].startswith("八字反查 甲子 丙寅 戊辰 庚申：2 个候选时刻")
    # 纯反查免确认门（与 astrodata 同类）
    assert validate_agent_preflight("bazi_inverse", {})["ok"] is True


def test_bazi_inverse_rejects_bad_pillars(tmp_path) -> None:
    settings = Settings(server_root="http://127.0.0.1:9999", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    service = HorosaSkillService(settings, client=CaptureClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    result = service.run_tool("bazi_inverse", {"year": "甲子", "month": "丙寅", "day": "戊辰", "hour": "庚"}, save_result=False)
    assert result.ok is False and result.error.code == "tool.bazi_inverse_invalid_pillars"
    assert result.error.details["invalid"] == ["庚"]
    assert result.error.details["agent_recovery"]["kind"] == "input"
