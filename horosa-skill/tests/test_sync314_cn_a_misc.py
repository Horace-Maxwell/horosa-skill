"""星阙 v3.14.0 同步 · cn_a 批其余口径：六壬 / 金口诀时刻不降到分钟、奇门全局速览宫号、宿占 / 金口诀快照改 verbatim、
公元 3003–4649 年起盘。

一、六壬 / 金口诀「不再把时刻降到分钟」（release「中式术数与时间」）
  上游 LiuRengMain.js / JinKouMain.js 的 genGodsParams / genRunYearParams / 缓存键、aiAnalysisContext/regenDivination.js 的
  requestLiurengGods：`time: flds.time.value.format('HH:mm')` → `format('HH:mm:ss')`。两处后果：/liureng/gods 收到带秒的时刻
  （skill 的 Python 侧历来原样发 HH:mm:ss，这一半本就一致）；快照 [起盘信息]「日期：」行印 params.time —— 现在带秒。
  此前 tools/liureng.js、tools/jinkou.js 把 time 切成前 5 位（照旧版上游的 'HH:mm'）。
二、奇门 [全局速览] 宫号（DunJiaCalc.js buildDunJiaSnapshotText）
  「九遁 / 吉格 / 凶格」标签此前写 `${x.palaceName}${x.palace}`（x.palace 是概览的内部九宫序号：艮 7、离 2…），v3.14.0 改
  `${x.palaceName}${LUOSHU_NUM[x.palaceName]}宫`。vendored verbatim 已随重渲染带上；这里用上游自己的测试夹具
  （dunjia/__tests__/dunjiaOverviewPalaceNumber.test.js 的真盘）经 tools/qimen.js 入口钉住。
三、宿占 / 金口诀快照：bespoke 手抄件 → 「上游全文件 + 声明式 deviation」（AGENTS §5.2 末条）
  suzhan/SuZhanMain.js、jinkou/JinKouMain.js 现在是 verbatim（流水线逐字可复现）；宿占用到的 AstroHelper 两个函数是 curated 子集
  suzhan/suzhanAstroHelper.js —— 这里逐行对上游源码（sha 看守只证明「有人看过」，不证明内容相同）。
四、公元 3003–4649 年起盘不再报错（后端 perchart.py：插值远 / 近地点越域时按各天体数据域精确筛，此前 KeyError）——live。

负向对照（实跑过）：
- tools/liureng.js / tools/jinkou.js 的 formatTimeLikeDateTime 换回 `.slice(0, 5)` → 「日期」行两条用例红；
- shared/fields.js formatTimeLikeDateTime 去掉补 ':00' → 补秒用例红；
- vendored DunJiaCalc.js 的 patTag 换回 `${x.palaceName}${x.palace}` → 宫号用例红（艮7 / 离2 …）；
- suzhanAstroHelper.js 里改一个字 → 逐行对上游用例红。
"""

from __future__ import annotations

from skips import upstream_source  # 上游拆文件后读「门面 + 子模块」全集（v3.15.0）
import json
import re
import subprocess
from pathlib import Path

import pytest
from skips import needs_upstream, upstream_path
from test_local_js_tools import make_service, requires_runtime
from test_sync311_w3b_gim import _section, requires_node
from test_sync314_cn_a_ascra import _replay

ROOT = Path(__file__).resolve().parents[1]
CORE_JS = ROOT / "horosa-core-js"
MANIFEST = json.loads((ROOT / "contracts" / "vendor_manifest.json").read_text(encoding="utf-8"))["files"]


def _node(script: str) -> object:
    done = subprocess.run(["node", "-e", script], cwd=CORE_JS, capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(done.stdout)


# ───────────────────────────── 一、时刻不降到分钟 ─────────────────────────────
@requires_node
@pytest.mark.parametrize("case", ["liureng_gods", "jinkou"])
def test_liureng_and_jinkou_snapshots_keep_the_seconds(tmp_path, case: str) -> None:
    """起课 07:30:27：[起盘信息]「日期」行带秒（上游 genGodsParams format('HH:mm:ss')），/liureng/gods 也收到带秒的时刻。
    负向：tools 里换回 `.slice(0, 5)` → 行成「07:30」。"""
    env, seen = _replay(tmp_path, case)
    assert env.ok, env.error
    assert _section(env.data["snapshot_text"], "起盘信息").split("\n")[0] == "日期：1990-05-17 07:30:27"
    gods = [payload for endpoint, payload in seen if endpoint == "/liureng/gods"]
    assert gods and all(payload["time"] == "07:30:27" for payload in gods)


@requires_node
def test_time_formatter_pads_minutes_and_leaves_the_rest_alone() -> None:
    """formatTimeLikeDateTime = 上游 DateTime.format('HH:mm:ss') 同形：'HH:mm' 补 ':00'，带秒原样，认不出的原样（不猜）。
    行年盘（liureng_runyear）的「日期」行取 guaTime，同一格式器。"""
    out = _node(
        "import('./src/shared/fields.js').then((m)=>{console.log(JSON.stringify(['07:30','07:30:27','23:59:59','',null,'7:3'].map("
        "(t)=>m.formatTimeLikeDateTime(t))));});"
    )
    assert out == ["07:30:00", "07:30:27", "23:59:59", "", "", "7:3"]
    for tool in ("liureng.js", "jinkou.js"):
        source = (CORE_JS / "src" / "tools" / tool).read_text(encoding="utf-8")
        assert "formatTimeLikeDateTime(" in source and ".slice(0, 5)" not in source, tool


# ───────────────────────────── 二、奇门全局速览宫号 ─────────────────────────────
# 洛书九宫数（独立来源：戴九履一、左三右七、二四为肩、六八为足）。
_LUOSHU = {"坎": 1, "坤": 2, "震": 3, "巽": 4, "中": 5, "乾": 6, "兑": 7, "艮": 8, "离": 9}


@requires_node
def test_qimen_overview_labels_carry_luoshu_palace_numbers() -> None:
    """上游 dunjiaOverviewPalaceNumber.test.js 的真盘（2026-05-15 00:12 拆补 时家转盘）经 tools/qimen.js：[全局速览] 的
    吉格 / 凶格 / 九遁标签一律「格名(宫名N宫)」，N = 洛书宫号。此前是内部九宫序号（艮7 / 离2 / 坎8 …，仓里记过「只报上游」）。
    负向：vendored patTag 换回 `${x.palaceName}${x.palace}` → 标签不带「宫」字、艮写成 7。"""
    script = (
        "import('./src/tools/qimen.js').then((m)=>{const nongli={yearJieqi:'丙午',year:'丙午',monthGanZi:'癸巳',dayGanZi:'己丑',"
        "time:'甲子',jieqi:'立夏',jiedelta:'立夏后第10天',birth:'2026-05-15 00:12:00',month:'三月',day:'廿九',leap:false};"
        "const r=m.runQimen({date:'2026-05-15',time:'00:12:00',zone:'+08:00',lat:'31n14',lon:'121e28',nongli,options:{paiPanType:3,"
        "qijuMethod:'chaibu',zhiShiType:0,yueJiaQiJuType:1,kongMode:'day',yimaMode:'day',shiftPalace:0,fengJu:false,timeAlg:1,"
        "school:'转盘',after23NewDay:0}});console.log(JSON.stringify(r.snapshot_text));});"
    )
    text = _node(script)
    lines = [line for line in _section(text, "全局速览").split("\n") if re.match(r"^(九遁：|吉格 |凶格 )", line)]
    assert len(lines) == 3, lines
    labels = re.findall(r"[^(、：\s]+\([^)]+\)", "\n".join(lines))
    assert labels, lines
    for label in labels:
        hit = re.search(r"\((.)(\d)宫\)$", label)
        assert hit, label
        assert int(hit.group(2)) == _LUOSHU[hit.group(1)], label
    assert "吉格 8 例：天显时格(乾6宫)、天显时格(坎1宫)、天显时格(艮8宫) 等8例" in lines   # 艮 = 洛书 8（内部序号 7）


# ───────────────────────────── 三、verbatim 化 ─────────────────────────────
def test_suzhan_and_jinkou_snapshot_builders_are_verbatim_vendored() -> None:
    """两份手抄件已换成流水线产物：清单里是 verbatim（上游全文件 + 声明式 deviation），旧 bespoke 条目与文件都不在了；
    工具从 verbatim 模块取 builder。"""
    entry = MANIFEST["suzhan/SuZhanMain.js"]
    assert entry["mode"] == "verbatim" and entry["upstream"] == "components/suzhan/SuZhanMain.js"
    assert [dev["kind"] for dev in entry["deviations"]][0] == "truncate_before"   # 剥 React 尾部：正则锚点，上游改名即报错
    assert (CORE_JS / "src" / "vendor" / "suzhan" / "SuZhanMain.js").is_file()
    # v3.15.0：上游把 JinKouMain 拆成壳 + main/*，快照 builder 在纯逻辑模块 main/snapshot.js —— 整文件 verbatim、零偏离，壳不再 vendor。
    entry = MANIFEST["jinkou/main/snapshot.js"]
    assert entry["mode"] == "verbatim" and entry["upstream"] == "components/jinkou/main/snapshot.js" and entry["deviations"] == []
    assert "jinkou/JinKouMain.js" not in MANIFEST and not (CORE_JS / "src" / "vendor" / "jinkou" / "JinKouMain.js").exists()
    for gone in ("suzhan/suzhanSnapshot.js", "jinkou/JinKouSnapshot.js"):
        assert gone not in MANIFEST and not (CORE_JS / "src" / "vendor" / gone).exists(), gone
    assert MANIFEST["suzhan/suzhanAstroHelper.js"]["mode"] == "curated"
    assert MANIFEST["suzhan/suzhanAstroHelper.js"]["extracts"] == ["signDegMin", "astroMsgPlainText"]
    assert "../vendor/suzhan/SuZhanMain.js" in (CORE_JS / "src" / "tools" / "suzhan.js").read_text(encoding="utf-8")
    assert "../vendor/jinkou/main/snapshot.js" in (CORE_JS / "src" / "tools" / "jinkou.js").read_text(encoding="utf-8")


def _js_block(source: str, start_marker: str) -> str:
    """从 start_marker 起到第一个行首 `}` / `};`（含）为止的源码块。"""
    at = source.index(start_marker)
    end = re.search(r"^\};?[ \t]*$", source[at:], re.M)
    assert end, start_marker
    return source[at: at + end.end()]


_UPSTREAM_ASTRO_HELPER = "Horosa-Web/astrostudyui/src/components/astro/AstroHelper.js"


@needs_upstream(_UPSTREAM_ASTRO_HELPER)
def test_suzhan_astro_helper_subset_is_line_for_line_upstream() -> None:
    """curated 子集逐块对上游 components/astro/AstroHelper.js（sha 戳只证明看过）：signDegMin / SIMPLE_TOKEN_MAP /
    isEncodedToken / astroMsgPlainText 四块源码逐字相同。负向：子集里改一个字 → 红。"""
    upstream = upstream_source(upstream_path(_UPSTREAM_ASTRO_HELPER))
    mine = (CORE_JS / "src" / "vendor" / "suzhan" / "suzhanAstroHelper.js").read_text(encoding="utf-8")
    for marker in ("export function signDegMin(", "const SIMPLE_TOKEN_MAP = {", "function isEncodedToken(", "export function astroMsgPlainText("):
        assert _js_block(mine, marker) == _js_block(upstream, marker), marker


@requires_node
def test_jinkou_verbatim_module_keeps_headless_stubs_unreachable() -> None:
    """v3.14.0 的 JinKouMain.js 带两处 headless stub（DateTime / utils/constants）；v3.15.0 上游把快照 builder 拆进纯逻辑模块
    jinkou/main/snapshot.js（只 import JinKouDoc / LRZhangSheng），skill 直接取它 —— 不再需要任何 stub。这里钉住：
    builder 模块不碰页面件（DateTime / Constants / 出生档回退链）、不 import React / UI，照常加载并导出 builder。"""
    source = (CORE_JS / "src" / "vendor" / "jinkou" / "main" / "snapshot.js").read_text(encoding="utf-8")
    assert not re.search(r"\b(DateTime|Constants|buildBirthFields|cloneDateTimeSafe)\b", source)
    imports = re.findall(r"^import .* from '([^']+)';", source, re.M)
    assert imports and all(spec.startswith("../") for spec in imports), imports
    assert not any(re.search(r"react|antd|xq-ui|comp/", spec) for spec in imports), imports
    exports = _node("import('./src/vendor/jinkou/main/snapshot.js').then((m)=>{console.log(JSON.stringify(Object.keys(m).sort()));});")
    assert "buildJinKouSnapshotText" in exports


# ───────────────────────────── 四、live ─────────────────────────────
@requires_runtime
@requires_node
def test_live_far_future_year_no_longer_errors(tmp_path) -> None:
    """公元 3500 年（3003–4649：插值远 / 近地点已越域、凯龙仍在域内）：/chart 系的宿占 / 七政 / 三式 / 六壬 / 金口诀与节气盘都能起盘，
    导出契约 clean。此前后端 KeyError。"""
    service = make_service(tmp_path)
    birth = {"date": "3500-06-01", "time": "07:30:00", "zone": "+08:00", "lat": "31n14", "lon": "121e28", "ad": 1,
             "agent_confirmed_settings": True}
    runs = {
        "suzhan": {**birth, "houseStartMode": 1},
        "guolao_chart": {**birth, "moiraTransitDate": "3530-01-01"},
        "sanshiunited": birth,
        "liureng_gods": birth,
        "jinkou": {**birth, "diFen": "酉"},
        "jieqi_year": {"year": 3500, "zone": "+08:00", "lat": "31n14", "lon": "121e28", "jieqis": ["春分", "夏至", "秋分", "冬至"],
                       "ad": 1, "agent_confirmed_settings": True},
    }
    for tool, payload in runs.items():
        env = service.run_tool(tool, payload, save_result=False)
        assert env.ok, (tool, env.error)
        exp = env.data["export_snapshot"]
        assert exp["missing_selected_sections"] == [] and exp["unknown_detected_sections"] == [], tool
    chart = service.run_tool("suzhan", runs["suzhan"], save_result=False).data["chart"]
    ids = {obj["id"] for obj in chart["objects"]}
    assert "Chiron" in ids and "Asc" in ids


@requires_runtime
@requires_node
def test_live_liureng_and_jinkou_date_line_has_seconds(tmp_path) -> None:
    service = make_service(tmp_path)
    birth = {"date": "2028-04-06", "time": "09:33:27", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "ad": 1,
             "agent_confirmed_settings": True}
    for tool, extra in (("liureng_gods", {}), ("jinkou", {"diFen": "酉"})):
        env = service.run_tool(tool, {**birth, **extra}, save_result=False)
        assert env.ok, (tool, env.error)
        assert _section(env.data["snapshot_text"], "起盘信息").split("\n")[0] == "日期：2028-04-06 09:33:27", tool
