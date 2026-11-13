"""上游 v3.14.0（Horosa-Public 10fb75de → e55c3a66）cn_b 批的手抄件 / bespoke 抽出件守卫。

每条写明上游出处、旧代码为什么会红、实跑过的负向对照（2026-11-13）。读上游源的用例只在 HOROSA_SOURCE_ROOT 指向上游
checkout 时跑；其余离线可跑（真 node 的用例要 PATH 上有 node）。
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest
from fakes import CaptureClient, FakeClient, FakeJsClient
from skips import needs_upstream, upstream_path

from horosa_skill.config import Settings
from horosa_skill.engine.js_client import HorosaJsEngineClient
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.service.text import divination as D

PKG = Path(__file__).resolve().parents[1]
VENDOR = PKG / "horosa-core-js" / "src" / "vendor"
UI = "Horosa-Web/astrostudyui/src"
requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="[host] node not installed")


# ════════════════════════ bespoke 抽出件：每个顶层声明与上游同名声明逐字相同 ════════════════════════
# vendor 清单的 derived_sha256 只证明「有人看过这一版上游」，不比内容（AGENTS §5.2「sha 看守不比内容」）。这里把内容也比了：
# 抽出件里的每个顶层 function / const 都要在上游源文件里找到同名声明，且文本逐字相同（只容许行首多一个 export）。
# 上游改了其中任何一个函数 → derived_sha256 红（提醒复核）+ 这里红（指出是哪个函数、差在哪）。

_DECL = re.compile(r"^(?:export\s+)?(?:async\s+)?(?:function\*?|const|let|var)\s+([A-Za-z0-9_$]+)")


def _top_level_declarations(text: str) -> dict[str, str]:
    """顶层声明名 → 全文。一行写完的（括号配平、以分号结尾）取这一行；否则取到下一个顶格的 `}` / `]` / `)` 行。"""
    out: dict[str, str] = {}
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        match = _DECL.match(lines[i])
        if not match:
            i += 1
            continue
        line = lines[i]
        balanced = all(line.count(a) == line.count(b) for a, b in ("{}", "[]", "()"))
        if balanced and re.search(r";\s*(//.*)?$", line):
            end = i
        else:
            end = i + 1
            while end < len(lines) and not re.match(r"^[}\])]", lines[end]):
                end += 1
        out[match.group(1)] = re.sub(r"^export\s+", "", "\n".join(lines[i:end + 1]))
        i = end + 1
    return out


BESPOKE_EXTRACTS = [
    # (抽出件, 上游源, 抽出件必须含有的声明)
    ("xiaochengtu/xiaochengtuSnapshot.js", "components/xiaochengtu/XiaoChengTuMain.js",
     {"LUOSHU_ROWS", "buildXiaoChengTuSnapshotText"}),
    ("ziwei/ziweiSnapshotLayers.js", "components/ziwei/ZiWeiMain.js",
     {"ZW_PERIOD_LEVEL_LABEL", "ZW_PERIOD_MAX_SEGMENTS", "formatLuckLayerLines", "findDaxianForYear",
      "buildZiweiPeriodOverviewLines", "buildZiweiPeriodLines", "buildZiweiOverlayLines"}),
    ("ziwei/ziweiSnapshotText.js", "components/ziwei/ZiWeiMain.js",
     {"normalizeGan", "pickYearGan", "collectHouseStars", "formatStarSiHua", "getLifeHouse", "buildZiWeiSnapshotText"}),
]


@needs_upstream(f"{UI}/components/ziwei/ZiWeiMain.js", f"{UI}/components/xiaochengtu/XiaoChengTuMain.js")
@pytest.mark.parametrize(("vendored", "source", "names"), BESPOKE_EXTRACTS, ids=[row[0] for row in BESPOKE_EXTRACTS])
def test_bespoke_extract_declarations_are_verbatim_upstream(vendored: str, source: str, names: set[str]) -> None:
    """负向对照：把 ziweiSnapshotText.js 里 `时区：${params.zone}` 改成 `时区:${params.zone}` → buildZiWeiSnapshotText 红；
    复核前 ziweiSnapshotText.js 有一行注释与上游不同（`[#80]` ≠ `[Windows #80]`），本用例在那一版上也是红的。"""
    upstream_file = upstream_path(f"{UI}/{source}")
    assert upstream_file is not None
    ours = _top_level_declarations((VENDOR / vendored).read_text(encoding="utf-8"))
    theirs = _top_level_declarations(upstream_file.read_text(encoding="utf-8"))
    assert set(ours) == names, f"{vendored} 的顶层声明变了：{sorted(set(ours) ^ names)}——新抽进来的函数登记到 BESPOKE_EXTRACTS"
    for name in sorted(names):
        assert name in theirs, f"上游 {source} 已没有 {name}（改名 / 挪走了？）"
        assert ours[name] == theirs[name], f"{vendored} 的 {name} 与上游 {source} 的同名声明不再逐字相同"
        assert len(ours[name]) > 20


def test_declaration_splitter_takes_whole_bodies() -> None:
    """切分器自己的对照：多行函数取到顶格 `}`，一行常量只取一行，行首 export 不算差异。"""
    sample = "const A = [1, 2];\nexport function f(x){\n\tif(x){ return 1; }\n\treturn 2;\n}\nfunction g(){\n\treturn {\n\t\ta: 1,\n\t};\n}\n"
    got = _top_level_declarations(sample)
    assert got == {
        "A": "const A = [1, 2];",
        "f": "function f(x){\n\tif(x){ return 1; }\n\treturn 2;\n}",
        "g": "function g(){\n\treturn {\n\t\ta: 1,\n\t};\n}",
    }


# ════════════════════════ 地占「问类」：后端只回程序键，快照按上游 questionTypeText 写中文 ════════════════════════
# 上游 GeomancyMain.js（v3.14.0）：`问类：${questionTypeText(reading.questionTypeZh, reading.questionType)}`，
# questionTypeText = 后端给了中文名用后端的，否则查 QUESTION_TYPE_OPTIONS 的 short，表里没有才写键名。
# 后端 reading 从不回 questionTypeZh（webgeomancysrv 与 geomancy 内核里都没有这个键），所以 v3.13.2 及以前的快照是
# 「问类：career」。skill 的 Python 移植同样写键名，而离线桩里恰好塞了一个 questionTypeZh="事业"——桩比真后端多一个字段，
# 于是离线一直看不出来。期望值来源：上游夹具 geomancy/__tests__/fixtures/geomancyHousesTableBaseline.txt 第 2 行
# （career → 「问类：事业」）与 QUESTION_TYPE_OPTIONS 原表。

def _geomancy_reading(**reading: object) -> dict:
    return {"reading": {"question": "事业", "ascendantFigure": {"nameZh": ""}, "ascendantSignZh": "", **reading}}


def _question_line(response: dict) -> str:
    text = D._build_geomancy_snapshot_text(response)
    return next(line for line in text.splitlines() if line.startswith("问类："))


def test_geomancy_question_type_line_uses_the_chinese_short_name() -> None:
    """负向对照：把该行改回 `reading.get('questionTypeZh') or reading.get('questionType') or '—'` → 前两条断言红
    （得到「问类：career」「问类：custom」）。"""
    assert _question_line(_geomancy_reading(questionType="career")) == "问类：事业"   # 上游夹具同值
    assert _question_line(_geomancy_reading(questionType="custom")) == "问类：自订"
    assert _question_line(_geomancy_reading(questionType="career", questionTypeZh="仕途")) == "问类：仕途"   # 后端给了就用后端的
    assert _question_line(_geomancy_reading(questionType="made_up")) == "问类：made_up"   # 表里没有：照上游写键名，不编
    assert _question_line(_geomancy_reading()) == "问类：—"


@needs_upstream(f"{UI}/components/geomancy/GeomancyMain.js")
def test_geomancy_question_short_names_equal_upstream_table() -> None:
    source = upstream_path(f"{UI}/components/geomancy/GeomancyMain.js")
    assert source is not None
    text = source.read_text(encoding="utf-8")
    block = text[text.index("const QUESTION_TYPE_OPTIONS = ["):]
    block = block[:block.index("\n];")]
    upstream = dict(re.findall(r"\{ key: '([a-z]+)', label: '[^']*', short: '([^']+)' \}", block))
    assert len(upstream) == 11 and upstream == D._GEOMANCY_QUESTION_SHORT
    assert set(upstream) == set(D._GEOMANCY_QUESTION_TYPES)   # 每个后端认的问类都有中文名
    assert "lines.push(`问类：${questionTypeText(reading.questionTypeZh, reading.questionType)}`);" in text
    baseline = upstream_path(f"{UI}/components/geomancy/__tests__/fixtures/geomancyHousesTableBaseline.txt")
    assert baseline is not None and baseline.read_text(encoding="utf-8").splitlines()[:2] == ["问题：事业", "问类：事业"]


def _service(tmp_path: Path, *, client: object | None = None, real: set[str] | None = None) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
                        runtime_root=tmp_path / "runtime", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    js: FakeJsClient = FakeJsClient()
    if real:
        engine = HorosaJsEngineClient(settings)

        class _Hybrid(FakeJsClient):
            def run(self, tool_name: str, payload: dict[str, object]) -> dict:
                return engine.run(tool_name, payload) if tool_name in real else super().run(tool_name, payload)

        js = _Hybrid()
    return HorosaSkillService(settings, client=client or CaptureClient(), store=MemoryStore(settings), js_client=js)


def test_geomancy_tool_writes_the_chinese_question_type_through_the_offline_stub(tmp_path: Path) -> None:
    """整条工具链（桩后端只回程序键，与真后端同形）：[起卦信息] 的问类是中文。桩里若又塞回 questionTypeZh，下面第二条断言红。"""
    client = CaptureClient()
    env = _service(tmp_path, client=client).run_tool("geomancy", {
        "date": "2028-04-06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28",
        "question": "事业能否升迁", "questionType": "wealth", "agent_confirmed_settings": True,
    }, save_result=False)
    assert env.ok, env.error
    assert "问类：财富" in env.data["export_snapshot"]["export_text"]
    reading = FakeClient().call("/geomancy/reading", {"questionType": "wealth"})["reading"]
    assert "questionTypeZh" not in reading and reading["questionType"] == "wealth"


# ════════════════════════ 紫微：出生时刻带秒到 Java（上游 v3.14.0 才不再降到分钟） ════════════════════════
# 上游 ZiWeiInput.js:731-732 旧版 `fields.time.value.format('HH:mm')` 把秒丢掉再起盘，v3.14.0 改 'HH:mm:ss'。
# skill 一直把归一化后的 HH:MM:SS 原样发给 /ziwei/birth（上游这次是追上来）——这里钉住，免得哪天「对齐上游」时学了旧写法。

class _ZiweiJava(CaptureClient):
    def call(self, endpoint: str, payload: dict) -> dict:
        self.calls.append((endpoint, dict(payload)))
        if endpoint == "/ziwei/birth":
            return {"chart": {"gender": "Male"}, "patterns": []}
        return FakeClient.call(self, endpoint, payload)


@requires_node
def test_ziwei_sends_the_birth_time_with_seconds(tmp_path: Path) -> None:
    """负向对照：在 mingli._ziwei_params 里把 time 截成 `f"{payload.get('time')}"[:5]` → sent['time'] == '00:59' → 红。"""
    client = _ZiweiJava()
    service = _service(tmp_path, client=client, real={"ziwei_birth"})
    env = service.run_tool("ziwei_birth", {
        "date": "1990-05-15", "time": "00:59:59", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gender": 1,
        "agent_confirmed_settings": True,
    }, save_result=False)
    assert env.ok, env.error
    sent = next(payload for endpoint, payload in client.calls if endpoint == "/ziwei/birth")
    assert sent["time"] == "00:59:59"
    assert "日期：1990-05-15 00:59:59" in env.data["snapshot_text"]
