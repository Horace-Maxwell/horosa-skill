"""Local-tool tests.

qimen / taiyi / jinkou are computed by the Horosa "ken" backend (kinqimen / kintaiyi /
kinjinkou) on the Python chart service, then reformatted into 星阙 aiExport.js sections by
the headless JS layer. Because that pipeline needs the live runtime (Java :9999 + Python
chart :8899), those four are integration tests that skip when the services aren't running.
liureng (headless layout) is exercised with a mocked client, and tongshefa has no ken
engine and runs as a pure headless JS tool.
"""
from __future__ import annotations

import socket

import pytest

from horosa_skill.config import Settings
from horosa_skill.engine.client import HorosaApiClient
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService


def _server_up(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


RUNTIME_UP = _server_up("127.0.0.1", 8899) and _server_up("127.0.0.1", 9999)
requires_runtime = pytest.mark.skipif(
    not RUNTIME_UP, reason="Horosa runtime not listening on :9999 (Java) + :8899 (chart/ken)"
)
# Chart-only gate: harmonic / agepoint / distributions are pure Python chart-service computations
# (/astroextra/*, /predict/*) and do NOT need the Java backend on :9999. Gating them on the chart
# service alone lets them run whenever :8899 is up, not only when the full stack is.
CHART_UP = _server_up("127.0.0.1", 8899)
requires_chart = pytest.mark.skipif(
    not CHART_UP, reason="Horosa chart service not listening on :8899"
)


class FakeLocalClient(HorosaApiClient):
    def __init__(self) -> None:
        super().__init__("http://fake")

    def probe(self, endpoint: str = "/common/time", payload: dict | None = None) -> bool:
        return True

    def call(self, endpoint: str, payload: dict) -> dict:
        if endpoint == "/nongli/time":
            return {
                "Result": {
                    "yearJieqi": "丙午",
                    "year": "丙午",
                    "monthGanZi": "庚寅",
                    "dayGanZi": "壬戌",
                    "jieqi": "立春",
                    "jiedelta": "立春后第14天",
                    "birth": f"{payload['date']} {payload['time']}",
                    "month": "正月",
                    "day": "初一",
                    "leap": False,
                    "yearGanZi": "丙午",
                    "monthInt": 1,
                    "dayInt": 1,
                    "time": "辛亥",
                }
            }
        if endpoint == "/jieqi/year":
            return {"Result": {"jieqi24": []}}
        if endpoint == "/liureng/gods":
            return {
                "Result": {
                    "liureng": {
                        "nongli": {"dayGanZi": "甲辰", "time": "申时", "monthGanZi": "丙申"},
                        "fourColumns": {"month": {"ganzi": "丙申"}},
                        "xun": {"旬空": "寅卯", "旬首": "甲辰"},
                        "season": {"金": "囚", "木": "旺", "水": "休", "火": "相", "土": "死"},
                        "gods": {},
                        "godsGan": {},
                        "godsMonth": {},
                        "godsZi": {},
                        "godsYear": {"taisui1": {}},
                    }
                }
            }
        raise AssertionError(f"Unexpected endpoint: {endpoint}")


class LiuRengParityLocalClient(FakeLocalClient):
    def call(self, endpoint: str, payload: dict) -> dict:
        if endpoint == "/liureng/gods":
            return {
                "Result": {
                    "liureng": {
                        "nongli": {"dayGanZi": "戊申", "time": "癸巳", "birth": "2028-04-06 09:35:18"},
                        "fourColumns": {
                            "year": {"ganzi": "戊申"},
                            "month": {"ganzi": "丙辰"},
                            "day": {"ganzi": "戊申"},
                            "time": {"ganzi": "癸巳"},
                        },
                        "xun": {"旬空": "寅卯", "旬首": "甲辰"},
                        "season": {},
                        "gods": {},
                        "godsGan": {},
                        "godsMonth": {},
                        "godsZi": {},
                        "godsYear": {"taisui1": {}},
                    }
                }
            }
        if endpoint in {"/chart", "/"}:
            return {
                "Result": {
                    "chart": {
                        "isDiurnal": True,
                        "nongli": {"dayGanZi": "戊申", "time": "癸巳"},
                        "objects": [{"id": "Sun", "sign": "Aries"}],
                    }
                }
            }
        return super().call(endpoint, payload)


def make_service(tmp_path, client: HorosaApiClient | None = None) -> HorosaSkillService:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        chart_server_root="http://127.0.0.1:8899",
        runtime_root=tmp_path / "runtime",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    # client=None -> real clients (used by the @requires_runtime ken integration tests);
    # a fake client is injected for the mocked liureng test.
    return HorosaSkillService(settings, client=client, store=MemoryStore(settings))


def _assert_clean_export(result) -> None:
    export = result.data.get("export_snapshot")
    assert export is not None
    assert export.get("missing_selected_sections") == []
    assert export.get("unknown_detected_sections") == []


@requires_runtime
def test_qimen_runs_via_ken_backend(tmp_path) -> None:
    service = make_service(tmp_path)
    result = service.run_tool(
        "qimen",
        {"date": "1998-02-20", "time": "20:48:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "options": {"qijuMethod": "chaibu"}},
        save_result=False,
    )
    assert result.ok is True
    pan = result.data["pan"]
    assert pan.get("source") == "kinqimen"
    assert pan.get("juText")
    assert isinstance(pan.get("cells"), list) and pan["cells"]
    assert "[起盘信息]" in result.data["snapshot_text"]
    assert "[九宫方盘]" in result.data["snapshot_text"]
    # 法奇门叠加层 (星阙 v-next)：六害/化解/八门化气大阵/用神分论/七要/孤辰寡宿。
    for header in ("[六害总览]", "[化解方案]", "[八门化气大阵]", "[用神分论]", "[财富七要]", "[孤辰寡宿]"):
        assert header in result.data["snapshot_text"], header
    _assert_clean_export(result)


@requires_runtime
def test_taiyi_runs_via_ken_backend(tmp_path) -> None:
    service = make_service(tmp_path)
    result = service.run_tool(
        "taiyi",
        {"date": "2026-02-17", "time": "21:50:07", "zone": "+08:00", "lat": "31n14", "lon": "121e28", "options": {"style": 3, "tn": 0, "sex": "男"}},
        save_result=False,
    )
    assert result.ok is True
    pan = result.data["pan"]
    assert pan.get("source") == "kintaiyi"
    assert pan.get("zhao")
    kook = pan.get("kook")
    assert (kook.get("text") if isinstance(kook, dict) else kook)
    assert "[太乙盘]" in result.data["snapshot_text"]
    _assert_clean_export(result)


@requires_runtime
def test_jinkou_runs_via_ken_backend(tmp_path) -> None:
    service = make_service(tmp_path)
    result = service.run_tool(
        "jinkou",
        {"date": "2026-02-17", "time": "21:50:07", "zone": "+08:00", "lat": "31n14", "lon": "121e28", "options": {"diFen": "午"}},
        save_result=False,
    )
    assert result.ok is True
    jinkou = result.data["jinkou"]
    assert jinkou.get("source") == "kinjinkou"
    assert isinstance(jinkou.get("rows"), list) and jinkou["rows"]
    assert "[金口诀速览]" in result.data["snapshot_text"]
    _assert_clean_export(result)


@requires_runtime
def test_sanshiunited_combines_ken_qimen_taiyi(tmp_path) -> None:
    service = make_service(tmp_path)
    result = service.run_tool(
        "sanshiunited",
        {"date": "1998-02-20", "time": "20:48:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "qimen_options": {"qijuMethod": "chaibu"}, "taiyi_options": {"style": 3}},
        save_result=False,
    )
    assert result.ok is True
    assert result.data["qimen"].get("juText")
    assert result.data["taiyi"].get("kook")
    assert "[起盘信息]" in result.data["snapshot_text"]
    _assert_clean_export(result)


def test_liureng_defaults_to_xingque_astrology_guiren_system(tmp_path) -> None:
    service = make_service(tmp_path, client=LiuRengParityLocalClient())

    result = service.run_tool(
        "liureng_gods",
        {
            "date": "2028-04-06",
            "time": "09:33:00",
            "zone": "+08:00",
            "lat": "31n13",
            "lon": "121e28",
        },
        save_result=False,
    )

    assert result.ok is True
    layout = result.data["headless_liureng"]["layout"]
    assert layout["guirengType"] == 2
    assert layout["guirengLabel"] == "星占法贵人"
    assert layout["guizi"] == "午"
    assert "贵人体系：星占法贵人" in result.data["snapshot_text"]
    assert "MongoDB" not in result.data["snapshot_text"]
    # 六壬 Phase 4 (星阙 v2.5.x)：常用神煞段按日干支补算 + 入课传标记。
    assert "[常用神煞]" in result.data["snapshot_text"]


class JinKouLocalClient(LiuRengParityLocalClient):
    def call(self, endpoint: str, payload: dict) -> dict:
        if endpoint == "/jinkou/pan":
            # 无 rows → runJinkou 走本地 buildJinKouData fallback，驱动真实 JS 解读层。
            return {"Result": {"source": "kinjinkou"}}
        return super().call(endpoint, payload)


def test_jinkou_local_emits_interpretation_layer(tmp_path) -> None:
    # 金口诀解读层 (星阙 v2.5.x)：真实 JS buildJinKouSnapshotText 出 20 段含解读层。
    service = make_service(tmp_path, client=JinKouLocalClient())
    result = service.run_tool(
        "jinkou",
        {"date": "1998-03-02", "time": "08:18:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "options": {"diFen": "午"}},
        save_result=False,
    )
    assert result.ok is True, result.error
    text = result.data["snapshot_text"]
    for header in ("[金口诀三盘]", "[用神强弱]", "[四位生克]", "[应期]", "[地支关系]", "[相关神煞]", "[分类用神·求财]", "[十二长生]"):
        assert header in text, header
    _assert_clean_export(result)


def test_tongshefa_local_tool_runs_headless_engine(tmp_path) -> None:
    service = make_service(tmp_path)
    result = service.run_tool(
        "tongshefa",
        {"taiyin": "巽", "taiyang": "坤", "shaoyang": "震", "shaoyin": "震"},
        save_result=False,
    )
    assert result.ok is True
    assert result.data["tongshefa"]["baseLeft"]["name"]
    assert result.data["export_snapshot"] is not None


def test_tongshefa_uses_jingfang_palace_element_not_upper_trigram(tmp_path) -> None:
    # Alignment regression: 统摄法 takes a hexagram's element from its 京房本宫 palace, not its upper
    # trigram. left=风雷益 (巽/震, palace 巽宫 木), right=火地晋 (离/坤, palace 乾宫 金 — upper trigram
    # would wrongly give 火). 星阙 expects right_elem=金 and main_relation=实克思.
    service = make_service(tmp_path)
    result = service.run_tool(
        "tongshefa",
        {"taiyin": "巽", "taiyang": "离", "shaoyang": "震", "shaoyin": "坤"},
        save_result=False,
    )
    assert result.ok is True
    data = result.data["tongshefa"]
    assert data["baseLeft"]["name"] == "风雷益"
    assert data["baseRight"]["name"] == "火地晋"
    assert data["left_elem"] == "木"
    assert data["right_elem"] == "金"  # palace 乾宫, NOT upper trigram 离/火
    assert data["main_relation"] == "实克思"


def test_canping_local_tool_runs_headless_engine(tmp_path) -> None:
    # canping (邵子参评数 / 金锁银匙) is a 原生·非 ken tool: the four pillars are computed in-process by
    # the vendored bazi chain (lunar-javascript), then canpingLocal does the 金锁银匙 起数 + 条文 lookup.
    # No live runtime needed (like tongshefa). Pillars for this case are 丙午/庚寅/壬戌/辛亥 → 水部.
    service = make_service(tmp_path)
    result = service.run_tool(
        "canping",
        {"date": "2026-02-17", "time": "21:50:07", "zone": "+08:00", "lon": "120e00", "gender": 1, "timeAlg": 1, "method": "ming"},
        save_result=False,
    )
    assert result.ok is True, result.error
    data = result.data["canping"]
    assert data["element"] == "水"
    assert data["partName"] == "水部"
    assert data["dayPalaceBranch"] == "亥"
    assert data["mingGong"] == "卯"
    assert data["benming"]["verses"]["numShun"] == 2152
    assert data["benming"]["verses"]["numNi"] == 3352
    assert len(data["dayun"]) == 9
    # The accurate per-year 流年 table lives in series (1–120), not the snapshot.
    assert len(data["series"]["rows"]) == 120
    snapshot = result.data["snapshot_text"]
    assert "[起盘]" in snapshot
    assert "[本命]" in snapshot
    assert "[大运·歲運]" in snapshot
    # Export contract is clean: 大运·歲運 legacy-maps to 大运, matching the ['起盘','本命','大运'] preset.
    _assert_clean_export(result)


def test_canping_method_gu_changes_day_palace(tmp_path) -> None:
    # 明法 takes the day-palace branch from the month branch reversed (寅→亥); 古法 takes it from the
    # bazi day branch (壬戌→戌). Same birth input, different 取法 ⇒ different 日宫支.
    service = make_service(tmp_path)
    base = {"date": "2026-02-17", "time": "21:50:07", "zone": "+08:00", "lon": "120e00", "gender": 1, "timeAlg": 1}
    ming = service.run_tool("canping", {**base, "method": "ming"}, save_result=False)
    gu = service.run_tool("canping", {**base, "method": "gu"}, save_result=False)
    assert ming.data["canping"]["dayPalaceBranch"] == "亥"
    assert gu.data["canping"]["dayPalaceBranch"] == "戌"


def test_heluo_local_tool_runs_headless_engine(tmp_path) -> None:
    # heluo (河洛理数) is a 原生·非 ken tool: pillars come from the vendored bazi chain, then heluoLocal
    # does 起命/先天/后天/命运篇/大限. The 命运篇 needs the real 节气 (lunar-javascript JieQi table), so
    # the formatter ports HeLuoMain.solarTerm. For this birth: 先天 火風鼎 → 后天 水火既濟.
    service = make_service(tmp_path)
    result = service.run_tool(
        "heluo",
        {"date": "2026-02-17", "time": "21:50:07", "zone": "+08:00", "lon": "120e00", "gender": 1, "timeAlg": 1},
        save_result=False,
    )
    assert result.ok is True, result.error
    data = result.data["heluo"]
    assert data["chart"]["xian"]["name"] == "火風鼎"
    assert data["chart"]["hou"]["name"] == "水火既濟"
    assert data["chart"]["tian"] == 19
    assert data["chart"]["di"] == 44
    assert isinstance(data["dayun"]["all"], list) and data["dayun"]["all"]
    assert data["solarTerm"]["term"] == "立春"  # 命运篇 depends on this
    snapshot = result.data["snapshot_text"]
    assert "[起命]" in snapshot
    assert "[先天·火風鼎 元堂爻辞]" in snapshot
    assert "[后天·水火既濟 元堂爻辞]" in snapshot
    assert "[命运篇]" in snapshot
    assert "[大限·岁运]" in snapshot
    # The dynamic 先天·…/后天·…/大限·岁运 labels legacy-map to 先天卦/后天卦/大限 ⇒ clean export.
    _assert_clean_export(result)


@requires_chart
def test_harmonic_runs_via_chart_service(tmp_path) -> None:
    # 调波盘 is a backend chart-extra on the Python chart service (/astroextra/harmonic). 星阙 has no
    # aiExport contract for it, so the skill returns structured positions/conjunctions + a readable
    # snapshot_text but no formal export technique (harmonic is not in TOOL_EXPORT_TECHNIQUE_MAP).
    service = make_service(tmp_path)
    result = service.run_tool(
        "harmonic",
        {"date": "1998-02-20", "time": "20:48:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "harmonic": 9, "orb": 2},
        save_result=False,
    )
    assert result.ok is True, result.error
    data = result.data
    assert data["harmonic"] == 9
    assert isinstance(data["positions"], list) and data["positions"]
    assert all(isinstance(p, dict) and "natalLon" in p and "sign" in p for p in data["positions"])
    assert isinstance(data["conjunctions"], list)
    assert data.get("chart")  # full chart obj (same shape as /chart) for downstream rendering
    assert "[起盘信息]" in data["snapshot_text"]
    assert "[调波位置]" in data["snapshot_text"]


@requires_chart
def test_agepoint_runs_via_chart_service(tmp_path) -> None:
    # 年龄推进点 (Age Point / Huber): backend /predict/agepoint computes the Koch-house age cycle.
    # 星阙 v2.4.0 西占技法. Needs only the chart service (:8899), not the Java backend.
    service = make_service(tmp_path)
    result = service.run_tool(
        "agepoint",
        {"date": "1998-02-20", "time": "20:48:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "hsys": 1, "predictive": 1},
        save_result=False,
    )
    assert result.ok is True, result.error
    data = result.data
    assert isinstance(data["points"], list) and data["points"]
    assert all(isinstance(p, dict) and "age" in p and "house" in p for p in data["points"])
    assert "[年龄推进点（Age Point / Huber）]" in data["snapshot_text"]
    _assert_clean_export(result)


@requires_chart
def test_distributions_runs_via_chart_service(tmp_path) -> None:
    # 界推运 (Distributions / 分配法): backend /predict/dist — Asc through the Egyptian bounds.
    service = make_service(tmp_path)
    result = service.run_tool(
        "distributions",
        {"date": "1998-02-20", "time": "20:48:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "hsys": 1, "predictive": 1},
        save_result=False,
    )
    assert result.ok is True, result.error
    rows = result.data["distributions"]
    assert isinstance(rows, list) and rows
    assert all(isinstance(r, dict) and "distributor" in r and "startDate" in r for r in rows)
    assert "[界推运（分配法 / Distributions）]" in result.data["snapshot_text"]
    _assert_clean_export(result)


@requires_chart
def test_chart_carries_v240_natal_extras(tmp_path) -> None:
    # 星阙 v2.4.0 西占: the astrochart export now carries 12分度 / 主宰星链 / 寿命格局, computed by the
    # vendored JS astroextra formatter (Ptolemy hyleg engine) from the /chart response. (可能性 is data-
    # dependent and intentionally not asserted.)
    service = make_service(tmp_path)
    result = service.run_tool(
        "chart",
        {"date": "1998-02-20", "time": "20:48:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "hsys": 1, "tradition": False, "predictive": 0},
        save_result=False,
    )
    assert result.ok is True, result.error
    snapshot = result.data["snapshot_text"]
    for section in ("[12分度]", "[主宰星链]", "[寿命格局]"):
        assert section in snapshot, section
    # 寿命格局 must carry the Hyleg/Alcocoden lines from the vendored lifespan engine.
    assert "生命主(Hyleg)" in snapshot
    assert "寿主星(Alcocoden)" in snapshot
    detected = (result.data.get("export_snapshot") or {}).get("section_titles_detected") or []
    assert "12分度" in detected and "主宰星链" in detected and "寿命格局" in detected


@requires_chart
def test_chart_sidereal_ayanamsa_and_nakshatra(tmp_path) -> None:
    # 星阙 v2.6.4 恒星黄道 47 岁差 + 西洋月宿 nakshatra：sidereal 盘(zodiacal=1) 按 siderealAyanamsa
    # 真实标注岁差名（Raman ≠ Lahiri，修原 '岁差:Lahiri' 硬编码 bug），并按 chart.nakshatras 出「月宿」段。
    service = make_service(tmp_path)
    base = {"date": "1998-02-20", "time": "20:48:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "hsys": 1}

    raman = service.run_tool("chart", {**base, "zodiacal": 1, "siderealAyanamsa": "raman"}, save_result=False)
    assert raman.ok is True, raman.error
    rsnap = raman.data["snapshot_text"]
    assert "恒星黄道岁差：Raman" in rsnap  # 真实岁差，非硬编码 Lahiri
    assert "[月宿]" in rsnap and "宿主" in rsnap
    rexp = raman.data["export_snapshot"]
    assert rexp["unknown_detected_sections"] == []  # 月宿 已登记，不算 unknown
    assert "月宿" not in rexp["missing_selected_sections"]  # 已产出，不算 missing
    assert "月宿" in (rexp.get("section_titles_detected") or [])

    # 缺省恒星黄道 → Lahiri（不是 Raman）
    lahiri = service.run_tool("chart", {**base, "zodiacal": 1}, save_result=False)
    assert lahiri.ok is True, lahiri.error
    assert "恒星黄道岁差：Lahiri / Chitrapaksha" in lahiri.data["snapshot_text"]

    # 回归黄道 → 无岁差行、无月宿段
    trop = service.run_tool("chart", {**base}, save_result=False)
    assert trop.ok is True, trop.error
    tsnap = trop.data["snapshot_text"]
    assert "恒星黄道岁差" not in tsnap
    assert "[月宿]" not in tsnap
    assert "月宿" not in (trop.data["export_snapshot"].get("section_titles_detected") or [])


@requires_chart
def test_mundane_ingress_chart(tmp_path) -> None:
    # 世俗入宫盘 (mundane ingress, 星阙 v2.4.0): (1) /jieqi/year → the precise 春分 ingress moment,
    # (2) /chart at that moment, (3) natal extras, (4) a [世俗入宫] head prepended to the astro snapshot.
    service = make_service(tmp_path)
    result = service.run_tool(
        "mundane",
        {"year": 2025, "ingressTerm": "春分", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gpsLat": 31.2167, "gpsLon": 121.4667, "hsys": 1},
        save_result=False,
    )
    assert result.ok is True, result.error
    data = result.data
    assert data["ingressTerm"] == "春分"
    assert data["ingressMoment"]  # the precise solar-term ingress timestamp
    snapshot = data["snapshot_text"]
    assert "[世俗入宫]" in snapshot
    assert "入宫节气：春分" in snapshot
    # The body reuses the astrochart snapshot with the v2.4.0 natal extras.
    assert "[起盘信息]" in snapshot
    assert "[寿命格局]" in snapshot
    detected = (data.get("export_snapshot") or {}).get("section_titles_detected") or []
    assert "世俗入宫" in detected


@requires_chart
def test_jaynesprog_runs_via_chart_service(tmp_path) -> None:
    # Jayne 赤纬推运 (v2.5.0): secondary progression + declination parallels (/astroextra/jaynesprog).
    service = make_service(tmp_path)
    result = service.run_tool(
        "jaynesprog",
        {"date": "1998-02-20", "time": "20:48:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "hsys": 1, "predictive": 1, "targetDate": "2028-04-06"},
        save_result=False,
    )
    assert result.ok is True, result.error
    assert "[赤纬推运（Jayne Declination）]" in result.data["snapshot_text"]
    _assert_clean_export(result)


@requires_chart
def test_vedicprog_runs_via_chart_service(tmp_path) -> None:
    # 恒星推运 Vedic (v2.5.0): progressions under the sidereal zodiac (/astroextra/progressions).
    service = make_service(tmp_path)
    result = service.run_tool(
        "vedicprog",
        {"date": "1998-02-20", "time": "20:48:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "hsys": 1, "predictive": 1, "targetDate": "2028-04-06"},
        save_result=False,
    )
    assert result.ok is True, result.error
    assert "[恒星推运（Vedic Sidereal）]" in result.data["snapshot_text"]
    _assert_clean_export(result)


@requires_chart
def test_planetaryarc_runs_via_chart_service(tmp_path) -> None:
    # 行星弧 (v2.5.0): whole chart directed by arcSource's secondary arc (/predict/planetaryarc).
    service = make_service(tmp_path)
    result = service.run_tool(
        "planetaryarc",
        {"date": "1998-02-20", "time": "20:48:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "hsys": 1, "predictive": 1, "datetime": "2028-04-06"},
        save_result=False,
    )
    assert result.ok is True, result.error
    assert "[行星弧（Planetary Arc）]" in result.data["snapshot_text"]
    _assert_clean_export(result)


@requires_chart
def test_planetaryages_runs_via_chart_service(tmp_path) -> None:
    # 行星年龄 (v2.5.0): Ptolemy seven ages — reads the natal chart, marks the current band.
    service = make_service(tmp_path)
    result = service.run_tool(
        "planetaryages",
        {"date": "1998-02-20", "time": "20:48:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "hsys": 1, "asOf": "2028-04-06"},
        save_result=False,
    )
    assert result.ok is True, result.error
    snapshot = result.data["snapshot_text"]
    assert "[行星年龄（Ages of Man）]" in snapshot
    assert "年龄带" in snapshot
    _assert_clean_export(result)


@requires_chart
def test_balbillus_runs_via_chart_service(tmp_path) -> None:
    # Balbillus 129年系统 (v2.5.0): 旺距削减主限 — vendored JS builder via horosa-core-js (progextra).
    service = make_service(tmp_path)
    result = service.run_tool(
        "balbillus",
        {"date": "1998-02-20", "time": "20:48:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "hsys": 1, "predictive": 0},
        save_result=False,
    )
    assert result.ok is True, result.error
    snapshot = result.data["snapshot_text"]
    assert "[Balbillus]" in snapshot
    assert "旺距削减" in snapshot
    assert "| 主限 | 子限 |" in snapshot
    _assert_clean_export(result)


@requires_chart
def test_yearsystem129_runs_via_chart_service(tmp_path) -> None:
    # 129年系统 (v2.5.0): seven-planet succession, computed server-side and carried in predictives.
    service = make_service(tmp_path)
    result = service.run_tool(
        "yearsystem129",
        {"date": "1998-02-20", "time": "20:48:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "hsys": 1, "predictive": 1},
        save_result=False,
    )
    assert result.ok is True, result.error
    snapshot = result.data["snapshot_text"]
    assert "[129年系统表格]" in snapshot
    assert "129 年一轮" in snapshot
    _assert_clean_export(result)


@requires_chart
def test_persiandirected_runs_via_chart_service(tmp_path) -> None:
    # 波斯向运 (v2.5.0): symbolic 1°/year direction — pure arithmetic off the natal chart objects/houses.
    service = make_service(tmp_path)
    result = service.run_tool(
        "persiandirected",
        {"date": "1998-02-20", "time": "20:48:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "hsys": 1, "predictive": 0},
        save_result=False,
    )
    assert result.ok is True, result.error
    snapshot = result.data["snapshot_text"]
    assert "[波斯向运（Persian Directed）]" in snapshot
    assert "1°/年" in snapshot
    assert "| 年龄 | 日期 |" in snapshot
    _assert_clean_export(result)


@requires_chart
def test_horary_runs_via_chart_service(tmp_path) -> None:
    # 卜卦 (horary): traditional chart at the question moment → vendored 星阙 horary engine
    # (runHorary + buildHorarySnapshot). category drives the quesited house.
    service = make_service(tmp_path)
    result = service.run_tool(
        "horary",
        {"date": "2026-06-02", "time": "14:30:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gpsLat": 31.2167, "gpsLon": 121.4667, "hsys": 0, "tradition": 1, "category": "marriage"},
        save_result=False,
    )
    assert result.ok is True, result.error
    snapshot = result.data["snapshot_text"]
    for section in ("[起卦信息]", "[根本性]", "[征象星指派]", "[裁决]"):
        assert section in snapshot, section
    assert result.data["category"] == "marriage"
    detected = (result.data.get("export_snapshot") or {}).get("section_titles_detected") or []
    assert "起卦信息" in detected and "裁决" in detected
    _assert_clean_export(result)


@requires_chart
def test_horary_unknown_category_falls_back_to_general(tmp_path) -> None:
    # An unrecognized category must degrade to 'general', never crash the engine.
    service = make_service(tmp_path)
    result = service.run_tool(
        "horary",
        {"date": "2026-06-02", "time": "14:30:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gpsLat": 31.2167, "gpsLon": 121.4667, "hsys": 0, "tradition": 1, "category": "no_such_category"},
        save_result=False,
    )
    assert result.ok is True, result.error
    assert result.data["category"] == "general"
    assert "[起卦信息]" in result.data["snapshot_text"]


@requires_chart
def test_election_runs_via_chart_service(tmp_path) -> None:
    # 择日 (electional): traditional chart at a candidate moment → vendored 星阙 election engine
    # (runElection + buildElectionSnapshot). topicId drives the rule pack + hard flags + scoring.
    service = make_service(tmp_path)
    result = service.run_tool(
        "election",
        {"date": "2026-06-02", "time": "14:30:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gpsLat": 31.2167, "gpsLon": 121.4667, "hsys": 0, "tradition": 1, "topicId": "surgery"},
        save_result=False,
    )
    assert result.ok is True, result.error
    snapshot = result.data["snapshot_text"]
    for section in ("[起盘信息]", "[总评]", "[红线]", "[建议]"):
        assert section in snapshot, section
    assert result.data["topicId"] == "surgery"
    overall = result.data["judgment"]["overall"]
    assert isinstance(overall, dict) and "score" in overall
    export = result.data.get("export_snapshot") or {}
    detected = export.get("section_titles_detected") or []
    assert "总评" in detected
    # 用事专属 (conditional) + 应期 (never emitted) are now declared optional in the export registry, so
    # the export reads clean (P1-1) — no missing/unknown sections.
    _assert_clean_export(result)


@requires_chart
def test_election_unknown_topic_falls_back_to_marriage(tmp_path) -> None:
    # An unrecognized topicId must degrade to 'marriage', never crash the engine.
    service = make_service(tmp_path)
    result = service.run_tool(
        "election",
        {"date": "2026-06-02", "time": "14:30:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gpsLat": 31.2167, "gpsLon": 121.4667, "hsys": 0, "tradition": 1, "topicId": "no_such_topic"},
        save_result=False,
    )
    assert result.ok is True, result.error
    assert result.data["topicId"] == "marriage"
    assert "[起盘信息]" in result.data["snapshot_text"]


# All 14 神数: (first section, a reliably-emitted later section). The 5 standalone work against any
# recent chart service; the 9 kinastro-* (shaozi…qizhengkin) only emit a snapshot on a current build —
# an OLDER live app returns no snapshot, which now surfaces as a clean transport error (see P0-3), and
# the test SKIPS that technique rather than failing (so it greens on the user's old :8899 yet really
# exercises the engine on the bundled v0.10.0 runtime).
_SHENSHU_EXPECTED = {
    # 5 standalone engines
    "wangji": ("[起盘]", "[心易发微]"),
    "wuzhao": ("[起盘]", "[特殊标记]"),
    "taixuan": ("[起盘]", "[表]"),
    "jingjue": ("[起课]", "[十六卦]"),
    "shenyishu": ("[起盘]", "[吉凶]"),
    # 9 kinastro-* engines
    "shaozi": ("[起盘]", "[条文]"),
    "tieban": ("[起盘]", "[条文]"),
    "fendjing": ("[起盘]", "[六段断语]"),
    "beiji": ("[起盘]", "[大运]"),
    "nanji": ("[起盘]", "[密码]"),
    "chunzi": ("[起盘]", "[候选条文]"),
    "xianqin": ("[起盘]", "[吞啖合战]"),
    "cetian": ("[起盘]", "[农历与命身]"),
    "qizhengkin": ("[起盘]", "[星曜]"),
}

# kinastro-* need gender (+ place for cetian/qizhengkin/xianqin) to compute a full chart.
_SHENSHU_PAYLOAD_EXTRA = {
    "shaozi": {"gender": 1},
    "tieban": {"gender": 1},
    "xianqin": {"gender": 1, "lat": "31n13", "lon": "121e28", "gpsLat": 31.2167, "gpsLon": 121.4667, "zone": "+08:00"},
    "cetian": {"gender": 1, "lat": "31n13", "lon": "121e28", "gpsLat": 31.2167, "gpsLon": 121.4667, "zone": "+08:00"},
    "qizhengkin": {"gender": 1, "lat": "31n13", "lon": "121e28", "gpsLat": 31.2167, "gpsLon": 121.4667, "zone": "+08:00"},
}


@requires_chart
@pytest.mark.parametrize("technique", sorted(_SHENSHU_EXPECTED))
def test_shenshu_runs_via_chart_service(tmp_path, technique) -> None:
    # 神数 family: kentang engines mounted on the chart service (:8899) that return a backend-built
    # `snapshot` whose [小节] headers already match the export preset.
    service = make_service(tmp_path)
    payload = {"date": "1998-02-20", "time": "20:48:00", "after23NewDay": 1, **_SHENSHU_PAYLOAD_EXTRA.get(technique, {})}
    result = service.run_tool(technique, payload, save_result=False)
    if not result.ok and result.error and result.error.code == "transport.shenshu_snapshot_unavailable":
        pytest.skip(f"chart service build too old to emit a {technique} snapshot")
    assert result.ok is True, result.error
    snapshot = result.data["snapshot_text"]
    assert snapshot, f"{technique} returned an empty snapshot"
    first, last = _SHENSHU_EXPECTED[technique]
    assert first in snapshot and last in snapshot, f"{technique}: {first}/{last} missing"
    _assert_clean_export(result)


def test_cli_coerces_null_or_scalar_payload_instead_of_crashing(tmp_path) -> None:
    """Regression: a null / scalar payload (stdin literally `null`) used to null-deref-crash the JS
    tools (`payload.liureng` / `normalizeDateTimeInput(null)`). cli.mjs now coerces it to {}, so a
    no-backend formatter like liureng degrades to a structured result instead of throwing."""
    service = make_service(tmp_path)
    # json.dumps(None) -> "null" on stdin; must return a dict (ok=true), not raise ToolTransportError.
    result = service.js_client.run("liureng", None)
    assert isinstance(result, dict)
    assert isinstance(result.get("data"), dict)


@requires_runtime
def test_india_chart_builds_clean_export_despite_empty_western_aspects(tmp_path) -> None:
    """Regression: india_chart returns normalAsp/immediateAsp/signAsp as empty LISTS (Indian charts
    have no Western aspects). `_build_aspect_section` used to crash with `'list' object has no
    attribute 'get'`; india_chart must now produce a clean ok=True envelope with an export contract."""
    service = make_service(tmp_path)
    result = service.run_tool(
        "india_chart",
        {"date": "2028-04-06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gpsLat": 31.2167, "gpsLon": 121.4667},
        save_result=False,
    )
    assert result.ok is True, result.error
    assert isinstance(result.data.get("export_snapshot"), dict)
    assert isinstance(result.data.get("export_format"), dict)
