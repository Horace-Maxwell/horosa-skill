"""生成 contracts/technique_provenance.json —— AGENTS §4「工具算源普查」的机器可读版。

新增技法后重跑本脚本（或手工加条目），verify_technique_provenance.py 会核覆盖率/ken 一致性/端点登记。
它曾是 scratchpad 里的一次性脚本——契约可再生，生成器就必须入仓，否则下次重生成只能凭记忆重写。

证据来自源码本身（AST 扫 `_run_*` runner 里的 `js_client.run` / `_call_remote` / `_require_ken_pan`），
分类来自 §4 的七分法 + 共享 runner 的族属。生成后由 scripts/verify_technique_provenance.py 守。

**输出幂等、契约 == 生成器输出**（`--check` 只比不写；`tests/test_technique_provenance_generator.py` 守）。
AST 只看 runner 本体，经 helper 间接调用的证据与逐工具的说明写进下方 EXTRA_EVIDENCE / NOTE_OVERRIDES——
v0.40.0 前这些只手改在契约里，重跑生成器即被抹掉（newtools 实现者撞到：生成器与契约三十处不一致）。
"""
from __future__ import annotations

import ast
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from horosa_skill.engine.registry import TOOL_DEFINITIONS  # noqa: E402
from horosa_skill.service import TOOL_EXPORT_TECHNIQUE_MAP  # noqa: E402

SRC = REPO / "src/horosa_skill/service.py"
tree = ast.parse(SRC.read_text(encoding="utf-8"))
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name.endswith("Service"))
FUNCS = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}

# 共享 runner：这些工具没有 `_run_<name>_tool`，走族级 runner。
SHARED_RUNNER = {
    **{k: "_run_shenshu_tool" for k in (
        "wangji", "wuzhao", "taixuan", "jingjue", "shenyishu", "shaozi", "tieban", "fendjing",
        "beiji", "nanji", "chunzi", "xianqin", "cetian", "qizhengkin",
    )},
    "liureng_gods": "_run_liureng_tool",
    "liureng_runyear": "_run_liureng_tool",
    "keypoints": "_run_keypoints_tool",
    "lunationphase": "_run_lunationphase_tool",
    "triplicityrulers": "_run_triplicityrulers_tool",
    "export_registry": None,
    "export_parse": None,
    "knowledge_registry": None,
    "knowledge_read": None,
}

CLASS = {
    # ken 是唯一算权，JS 只格式化（§4）。
    "ken_backed": {"qimen", "taiyi", "jinkou"},
    # 原生·非 ken 数算：core-js 进程内经 vendored bazi 链起四柱，再自行起数/起卦 + 条文查表。
    "native_js_numerology": {"canping", "heluo"},
    # 纯 headless JS：无后端引擎，JS 内完成计算与排版。
    "headless_js": {"tongshefa", "tarot", "lingqi", "huangli", "tongshu", "yizhangjing"},
    # 复合型：多腿聚合 / 多次请求拼段（请求型 builder 一律归 Python）。
    # 择日十技法（v3.10.0）全是复合型：区间搜索一条腿 + 展示盘另一条腿（各按基底技法的原算源），
    # 两条腿算权不同，`compute_sources` 逐项写明。落到兜底会被判成 local_data「不起盘」——
    # 那是**不诚实**的：它们确实铸盘，只是盘不是搜索算的。
    "composite": {"sanshiunited", "mundane", "extrareturns", "qimenzeri", "tianxing",
                  "huanglizeri", "bazizeri", "taiyizeri", "ziweizeri", "liurengzeri", "sanshizeri",
                  "qizhengzeri", "indiazeri", "guolao_chart"},
    # Python port：星阙前端算法的 Python 移植。
    "python_port": {"decennials"},
    # frontend 读数型 Python 移植：读已算好的 chart 对象再排版。
    "frontend_read_port": {"planetaryages", "yearsystem129", "persiandirected", "balbillus"},
    # 神数族：kentang 引擎挂在 chart 服务上，后端直出 snapshot。
    "chart_service_shenshu": set(SHARED_RUNNER) - {"liureng_gods", "liureng_runyear", "keypoints",
                                                   "lunationphase", "triplicityrulers",
                                                   "export_registry", "export_parse",
                                                   "knowledge_registry", "knowledge_read"},
    # 本地数据检索：不算盘，只读本地库/注册表。
    "local_data": {"astrodata", "export_registry", "export_parse", "knowledge_registry", "knowledge_read"},
    # 后端算、JS 只排版：runner 同时有端点与 JS 调用时启发式会误判 headless_js，这里显式点名。
    "python_chart_backend": {"acg"},
}
NOTES = {
    "ken_backed": "ken 后端算、JS 只格式化；健康结果带 pan.source/jinkou.source == 引擎名，runner 必须调 _require_ken_pan",
    "native_js_numerology": "core-js 进程内经 vendored bazi 链（lunar-javascript）起四柱后自行起数/起卦 + 条文查表，不打 chart 服务",
    "headless_js": "纯 headless JS，无后端引擎",
    "composite": "多腿/多请求聚合；请求型 builder 归 Python，JS 层不发 HTTP",
    "python_port": "星阙前端算法的 Python 移植（金标对上游测试）",
    "frontend_read_port": "读已算好的 chart 对象再排版的 Python 移植",
    "chart_service_shenshu": "kentang 神数引擎挂在 Python chart 服务上，后端直出 snapshot（真身在 Result.snapshot）",
    "local_data": "不起盘：读本地离线库 / 内置注册表",
    "python_chart_backend": "Python _call_remote 打 chart 服务（/chart · /predict/* · /astroextra/* · /india/* …）+ Python snapshot builder",
    "java_backend": "Java 聚合层（:9999）计算，Python 只转发与排版",
}
# 逐工具说明（覆盖族级 NOTES）。
NOTE_OVERRIDES = {
    "acg": "chart 服务 /location/acg*（ACGraph）算行星线、落点与世运事件；vendored JS acgSnapshot 只排 [占星地图] 段",
    "bazi_inverse": "Java BaZiHelper.getBirthes 逐年回推；Python 只校验四柱干支、转发与排版",
    "guolao_chart": (
        "盘面 /chart（Python chart 服务）+ 政余格局/庙旺 headless JS + [虚实]/[本命化曜]/[流年流曜] 走 Java "
        "/qizheng/moira 规则层（流年盘二次铸盘；Java 不可用时三段缺席进 warnings）"
    ),
}
# runner 经 helper 间接调用、AST 扫 runner 本体看不到的证据。
EXTRA_EVIDENCE: dict[str, dict[str, list[str]]] = {
    # 神数族：_shenshu_xinyi_lines（正传心易 → /wangji/xinyi）与演禽演法 JS（yanqin_yanfa）。
    **{k: {"engines": ["yanqin_yanfa"], "endpoints": ["/wangji/xinyi"]} for k in (
        "wangji", "wuzhao", "taixuan", "jingjue", "shenyishu", "shaozi", "tieban", "fendjing",
        "beiji", "nanji", "chunzi", "xianqin", "cetian", "qizhengkin",
    )},
    "indiazeri": {"endpoints": ["/indiaelectionscan/scan"]},
    "qizhengzeri": {"endpoints": ["/qizhengelectionscan/scan"]},
    "mundane": {"engines": ["mundane_cards"]},  # 世俗盘右栏卡（tools/mundaneCards.js）
    # ken 族里「上游同判据路由到本地引擎」的合法算源（v3.11 sanshi chunk）：qimen 按 isQimenLocalRoute（本地家/飞盘/
    # 混合/报数/七组本地口径）走 calcDunJia、jinkou 按 schoolsAllDefault（五项流派任一非缺省）走 buildJinKouData ——
    # 两者都不打 ken，runner 回 compute_sources = 下列名字。不声明的话依据卡会把合法路由误标「与声明不一致」；
    # 反过来 ken 失败被静默回退本地（§4）仍然抓得到：那条路径不会带这些 compute_sources。
    "qimen": {"engines": ["local_route_calcDunJia"]},
    "jinkou": {"engines": ["local_route_buildJinKouData"]},
}




def evidence(fn: ast.FunctionDef | None) -> tuple[list[str], list[str], list[str]]:
    if fn is None:
        return [], [], []
    js, eps, ken = set(), set(), set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = getattr(f, "attr", None)
        if name == "run" and isinstance(f.value, ast.Attribute) and f.value.attr == "js_client":
            if node.args and isinstance(node.args[0], ast.Constant):
                js.add(node.args[0].value)
        if name == "_call_remote" and node.args and isinstance(node.args[0], ast.Constant):
            eps.add(node.args[0].value)
        if name == "_require_ken_pan":
            for kw in node.keywords:
                if kw.arg == "engine" and isinstance(kw.value, ast.Constant):
                    ken.add(kw.value.value)
    return sorted(js), sorted(eps), sorted(ken)


def classify(name: str, definition, js, eps) -> str:
    for klass, members in CLASS.items():
        if name in members:
            return klass
    if definition.execution == "remote":
        # /predict/* 与 /modern/relative 走 Python chart 服务；其余远端端点是 Java 聚合层。
        from horosa_skill.service import _PYTHON_CHART_ENDPOINTS
        return "python_chart_backend" if definition.endpoint in _PYTHON_CHART_ENDPOINTS else "java_backend"
    if eps and not js:
        # 本地 runner 只打 Java 端点（如 bazi_inverse → /common/inversebazi）就是 Java 算的。
        from horosa_skill.service import _PYTHON_CHART_ENDPOINTS
        return "python_chart_backend" if set(eps) & _PYTHON_CHART_ENDPOINTS else "java_backend"
    if js:
        return "headless_js"
    return "local_data"


out: dict[str, dict] = {}
for name, definition in sorted(TOOL_DEFINITIONS.items()):
    fn = FUNCS.get(f"_run_{name}_tool") or FUNCS.get(SHARED_RUNNER.get(name) or "")
    js, eps, ken = evidence(fn)
    if definition.endpoint:
        eps = sorted(set(eps) | {definition.endpoint})
    if name in CLASS["chart_service_shenshu"]:
        eps = sorted(set(eps) | {f"/{name}/pan"})
    klass = classify(name, definition, js, eps)
    extra = EXTRA_EVIDENCE.get(name, {})
    out[name] = {
        "compute_class": klass,
        "engines": sorted(set(ken or js) | set(extra.get("engines", []))),
        "endpoints": sorted(set(eps) | set(extra.get("endpoints", []))),
        "export_technique": TOOL_EXPORT_TECHNIQUE_MAP.get(name),
        "notes": NOTE_OVERRIDES.get(name, NOTES[klass]),
    }

payload = {
    "_comment": (
        "每个技法工具的**算源**声明（AGENTS §4「工具算源普查」的机器可读版）。"
        "技法依据卡/报告用它说明「这一段是谁算的」；运行期实测（pan.source / compute_sources）优先于本声明，"
        "两者不一致时如实标注分歧，不静默采信任何一边。由 scripts/verify_technique_provenance.py 守："
        "新增技法不声明算源即红。"
    ),
    "_classes": {k: NOTES[k] for k in sorted(NOTES)},
    "tools": out,
}
CONTRACT = REPO / "contracts/technique_provenance.json"
rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
if "--check" in sys.argv[1:]:
    current = CONTRACT.read_text(encoding="utf-8") if CONTRACT.is_file() else ""
    if current != rendered:
        committed = json.loads(current or "{}").get("tools", {})
        stale = sorted(k for k in set(committed) | set(out) if committed.get(k) != out.get(k))
        print(f"technique_provenance.json != generator output ({len(stale)} tool(s)): {', '.join(stale)}")
        print("fix the generator (EXTRA_EVIDENCE / NOTE_OVERRIDES / CLASS), then rerun without --check")
        raise SystemExit(1)
    print(f"technique_provenance.json == generator output ({len(out)} tools)")
    raise SystemExit(0)
CONTRACT.write_text(rendered, encoding="utf-8")
counts: dict[str, int] = {}
for entry in out.values():
    counts[entry["compute_class"]] = counts.get(entry["compute_class"], 0) + 1
print(f"wrote {len(out)} tools: {json.dumps(counts, ensure_ascii=False)}")
