"""信封层：摘要、实体、警告、运维恢复提示、响应视图与 dispatch / 精简面契约。"""
from __future__ import annotations

from typing import Any

from horosa_skill.errors import recovery_for
from horosa_skill.schemas.common import ToolEnvelope


def _missing_sections_warning(response_data: Any) -> str | None:
    """预设段有缺 → 一条可读的「结果不完整」说明（此前只躺在 export_snapshot.missing_selected_sections 里）。"""
    export = response_data.get("export_snapshot") if isinstance(response_data, dict) else None
    if not isinstance(export, dict):
        return None
    missing = [f"{title}".strip() for title in (export.get("missing_selected_sections") or []) if f"{title}".strip()]
    if not missing:
        return None
    selected = export.get("selected_sections") or []
    shown = "、".join(missing[:8]) + ("…" if len(missing) > 8 else "")
    return (
        f"结果不完整：预设 {len(selected)} 段中 {len(missing)} 段未产出（{shown}）；"
        "缺段原因见 warnings 其余条目，清单见 export_snapshot.missing_selected_sections。"
    )


def _cn_unified_zone_note(input_normalized: dict[str, Any]) -> str | None:
    """F17：输入层把 Asia/Urumqi 归并成北京时间时，warnings 里说清楚（上游 advisory 'cn-unified' 同义）。"""
    if input_normalized.get("zoneAdvisory") != "cn-unified":
        return None
    geo = input_normalized.get("geoZone") or "Asia/Urumqi"
    return (
        f"时区按中国大陆统一北京时间口径起盘：{geo} → Asia/Shanghai（{input_normalized.get('zone')}，"
        f"1949-10-01 起法定时间）；如需新疆当地惯用时间，传 cnUnifiedZone=false 或直接给偏移 +06:00。"
    )


def _generic_summary(tool_name: str, data: dict[str, Any]) -> list[str]:
    if tool_name == "export_registry":
        count = len(data.get("techniques", []))
        total = int(data.get("techniques_total") or count)
        if count < total:
            summary = [f"已输出 1 个星阙 AI 导出 technique 的注册表（全库共 {total} 个）。"]
        else:
            summary = [f"已输出 {count} 个星阙 AI 导出 technique 的完整注册表。"]
        selected = data.get("selected_technique")
        if isinstance(selected, dict) and selected.get("label"):
            summary.append(f"当前聚焦：{selected['label']}。")
        missing = data.get("technique_not_found")
        if missing:
            summary.append(f"未识别的 technique「{missing}」——已返回全量注册表供比对名称。")
        return summary
    if tool_name == "export_parse":
        summary = ["已将星阙 AI 导出文本转换为结构化分段 JSON。"]
        detected = data.get("section_titles_detected", [])
        if detected:
            summary.append(f"识别到 {len(detected)} 个分段标题。")
        selected = data.get("selected_sections", [])
        if selected:
            summary.append(f"当前导出将保留 {len(selected)} 个目标分段。")
        return summary
    if tool_name == "knowledge_registry":
        domains = data.get("domains", [])
        summary = [f"已输出 {len(domains)} 个悬浮知识域的可读目录。"]
        if domains:
            summary.append(f"当前包含：{'、'.join(one.get('domain', '') for one in domains if one.get('domain'))}。")
        return summary
    if tool_name == "knowledge_read":
        if data.get("mode") == "search":
            summary = [f"已跨知识域全文检索「{data.get('query')}」：命中 {data.get('total_matched', 0)} 条（扫描 {data.get('total_scanned', 0)} 条目）。"]
            matches = data.get("matches") or []
            if matches:
                summary.append(f"最优命中：{matches[0].get('citation')}。")
            return summary
        summary = ["已读取星阙悬浮知识，并转换为稳定的本地可读文档。"]
        if data.get("domain") and data.get("category"):
            summary.append(f"知识域：{data['domain']} / {data['category']}。")
        if data.get("title"):
            summary.append(f"条目：{data['title']}。")
        return summary
    if tool_name == "qimen":
        pan = data.get("pan", {})
        summary = ["已通过 ken 后端运行奇门遁甲。"]
        if pan.get("juText"):
            summary.append(f"局数：{pan['juText']}。")
        if pan.get("zhiFu") and pan.get("zhiShi"):
            summary.append(f"值符 {pan['zhiFu']}，值使 {pan['zhiShi']}。")
        return summary
    if tool_name == "taiyi":
        pan = data.get("pan", {})
        summary = ["已通过 ken 后端运行太乙。"]
        if pan.get("zhao"):
            summary.append(f"命式：{pan['zhao']}。")
        kook = pan.get("kook")
        kook_text = kook.get("text") if isinstance(kook, dict) else kook
        if kook_text:
            summary.append(f"局式：{kook_text}。")
        return summary
    if tool_name == "jinkou":
        result = data.get("jinkou", {})
        summary = ["已通过 ken 后端运行金口诀。"]
        if result.get("guiName") and result.get("jiangName"):
            summary.append(f"贵神 {result['guiName']}，将神 {result['jiangName']}。")
        if result.get("wangElem"):
            summary.append(f"旺神五行：{result['wangElem']}。")
        return summary
    if tool_name == "suzhan":
        chart = data.get("chart", {})
        summary = ["已生成宿占 / 宿盘输出。"]
        if isinstance(chart.get("objects"), list):
            summary.append(f"星曜数量：{len(chart['objects'])}。")
        return summary
    if tool_name == "sixyao":
        summary = ["已生成易卦 / 六爻输出。"]
        if data.get("current_code"):
            summary.append(f"本卦编码：{data['current_code']}。")
        if data.get("changed_code"):
            summary.append(f"之卦编码：{data['changed_code']}。")
        return summary
    if tool_name == "tongshefa":
        model = data.get("tongshefa", {})
        summary = ["已运行本地统摄法算法。"]
        if model.get("baseLeft", {}).get("name") and model.get("baseRight", {}).get("name"):
            summary.append(f"本卦：左{model['baseLeft']['name']}，右{model['baseRight']['name']}。")
        if model.get("main_relation"):
            summary.append(f"主关系：{model['main_relation']}。")
        return summary
    if tool_name == "canping":
        model = data.get("canping", {})
        summary = ["已运行本地邵子参评数（金锁银匙）算法。"]
        if model.get("element") and model.get("partName"):
            summary.append(f"年纳音：{model['element']}（{model['partName']}）。")
        if model.get("dayPalaceBranch") and model.get("mingGong"):
            summary.append(f"日宫支 {model['dayPalaceBranch']}，命宫 {model['mingGong']}。")
        benming = model.get("benming") if isinstance(model.get("benming"), dict) else {}
        verses = benming.get("verses") if isinstance(benming.get("verses"), dict) else {}
        if verses.get("numShun") and verses.get("numNi"):
            summary.append(f"本命数：顺 {verses['numShun']} / 逆 {verses['numNi']}。")
        return summary
    if tool_name == "heluo":
        model = data.get("heluo", {})
        summary = ["已运行本地河洛理数算法。"]
        chart = model.get("chart") if isinstance(model.get("chart"), dict) else {}
        xian = chart.get("xian") if isinstance(chart.get("xian"), dict) else {}
        hou = chart.get("hou") if isinstance(chart.get("hou"), dict) else {}
        if xian.get("name") and hou.get("name"):
            summary.append(f"先天卦 {xian['name']} → 后天卦 {hou['name']}。")
        if chart.get("tian") is not None and chart.get("di") is not None:
            summary.append(f"天数 {chart['tian']}（{chart.get('tianGua', '')}）／地数 {chart['di']}（{chart.get('diGua', '')}）。")
        return summary
    if tool_name == "yizhangjing":
        model = data.get("yizhangjing", {})
        summary = ["已运行本地一掌经算法。"]
        ming = model.get("mingGong") if isinstance(model.get("mingGong"), dict) else {}
        if ming.get("branch") and ming.get("star"):
            summary.append(f"命宫 {ming['branch']}宫·{ming['star']}。")
        pattern = model.get("pattern") if isinstance(model.get("pattern"), dict) else {}
        if pattern.get("mingGe"):
            summary.append(f"命格：{pattern['mingGe']}（九品估 {pattern.get('nineGrade', '—')}）。")
        return summary
    if tool_name == "acg":
        model = data.get("acg", {})
        summary = ["已生成占星地图行星线表（AstroCartoGraphy）。"]
        planets = model.get("planets") if isinstance(model.get("planets"), dict) else {}
        if planets:
            summary.append(f"行星线：{len(planets)} 星（MC/IC 经度 + 天顶点）。")
        parans = model.get("parans")
        if isinstance(parans, list) and parans:
            summary.append(f"偕升纬度带 {len(parans)} 条。")
        return summary
    if tool_name == "bazi_inverse":
        model = data.get("bazi_inverse", {})
        pillars = "".join(f"{x} " for x in (model.get("pillars") or [])).strip()
        candidates = model.get("candidates") or []
        return [f"八字反查 {pillars or '—'}：{len(candidates)} 个候选时刻。"]
    if tool_name == "astrodata":
        model = data.get("astrodata", {})
        summary = ["已检索离线名人星盘数据库。"]
        if isinstance(model.get("person"), dict):
            summary.append(f"单人详情：{model['person'].get('name')}（评级 {model['person'].get('rodden', '—')}）。")
        elif model.get("total") is not None:
            summary.append(f"命中 {model['total']} 条。")
        return summary
    if tool_name == "harmonic":
        summary = [f"已生成调波盘（H{data.get('harmonic', '—')}）。"]
        positions = data.get("positions")
        if isinstance(positions, list):
            summary.append(f"调波位置点数：{len(positions)}。")
        conjunctions = data.get("conjunctions")
        if isinstance(conjunctions, list) and conjunctions:
            summary.append(f"同频合相：{len(conjunctions)} 组。")
        return summary
    if tool_name == "agepoint":
        summary = ["已生成年龄推进点（Age Point / Huber）时间线。"]
        points = data.get("points")
        if isinstance(points, list):
            summary.append(f"年龄点数：{len(points)}。")
            key_ages = [p for p in points if isinstance(p, dict) and p.get("aspectTo")]
            if key_ages:
                summary.append(f"合本命关键岁数：{len(key_ages)} 处。")
        return summary
    if tool_name == "distributions":
        summary = ["已生成界推运（分配法 / Distributions）时间线。"]
        rows = data.get("distributions")
        if isinstance(rows, list):
            summary.append(f"分配期数：{len(rows)}。")
        return summary
    if tool_name == "mundane":
        summary = ["已生成世俗入宫盘（mundane ingress）。"]
        if data.get("ingressTerm") and data.get("ingressYear"):
            summary.append(f"{data['ingressYear']} 年「{data['ingressTerm']}」入宫。")
        if data.get("ingressMoment"):
            summary.append(f"入宫时刻：{data['ingressMoment']}。")
        return summary
    if tool_name == "sanshiunited":
        summary = ["已运行本地三式合一聚合算法。"]
        qimen = data.get("qimen", {})
        taiyi = data.get("taiyi", {})
        if qimen.get("juText"):
            summary.append(f"奇门局数：{qimen['juText']}。")
        taiyi_kook = taiyi.get("kook")
        if isinstance(taiyi_kook, dict) and taiyi_kook.get("text"):
            summary.append(f"太乙局式：{taiyi_kook['text']}。")
        elif taiyi_kook:
            summary.append(f"太乙局式：{taiyi_kook}。")
        return summary
    if tool_name == "guolao_chart":
        chart = data.get("chart", {})
        summary = ["已生成七政四余盘。"]
        if isinstance(chart.get("objects"), list):
            summary.append(f"星曜数量：{len(chart['objects'])}。")
        return summary
    if tool_name == "hellen_chart":
        chart = data.get("chart", {})
        summary = ["已生成希腊星盘。"]
        if isinstance(chart, dict):
            summary.append(f"字段数：{len(chart.keys())}。")
        return summary
    if tool_name == "germany":
        summary = ["已生成量化盘 / 中点盘。"]
        if isinstance(data.get("midpoints"), list):
            summary.append(f"中点数量：{len(data['midpoints'])}。")
        return summary
    if tool_name == "firdaria":
        firdaria = data.get("firdaria", [])
        summary = ["已生成法达星限。"]
        if isinstance(firdaria, list):
            summary.append(f"主限数量：{len(firdaria)}。")
        return summary
    if tool_name == "decennials":
        timeline = data.get("timeline", {})
        summary = ["已生成十年大运。"]
        if isinstance(timeline.get("list"), list):
            summary.append(f"L1 层数量：{len(timeline['list'])}。")
        resolved = timeline.get("resolvedStartPlanet")
        if resolved:
            summary.append(f"起运主星：{resolved}。")
        return summary
    if tool_name == "otherbu":
        summary = ["已生成西洋游戏 / 占星骰子结果。"]
        if data.get("planet") and data.get("sign"):
            summary.append(f"骰面：{data['planet']} / {data['sign']}。")
        return summary
    lines = [f"工具 `{tool_name}` 已返回结构化结果。"]
    keys = sorted(data.keys())
    if keys:
        lines.append(f"顶层字段：{', '.join(keys[:8])}{' ...' if len(keys) > 8 else ''}")
    if "chart" in data:
        lines.append("结果包含 chart 结构。")
    if "predictives" in data:
        lines.append("结果包含 predictive / 时运相关数据。")
    if "bazi" in data:
        lines.append("结果包含八字结构。")
    if "liureng" in data:
        lines.append("结果包含六壬结构。")
    if "jieqi24" in data and isinstance(data["jieqi24"], list):
        lines.append(f"结果包含 {len(data['jieqi24'])} 个节气节点。")
    return lines[:4]


def _extract_entities(input_normalized: dict[str, Any], query_text: str | None = None) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []

    def add(display_name: str, *, entity_type: str = "subject", key: str | None = None, metadata: dict[str, Any] | None = None) -> None:
        value = (display_name or "").strip()
        if not value:
            return
        entities.append(
            {
                "entity_type": entity_type,
                "entity_key": (key or value).lower(),
                "display_name": value,
                "metadata": metadata or {},
            }
        )

    def birth_meta(source: dict[str, Any]) -> dict[str, Any]:
        return {
            k: source.get(src_key)
            for k, src_key in (("date", "date"), ("time", "time"), ("zone", "zone"), ("lat", "lat"), ("lon", "lon"))
            if source.get(src_key) is not None
        }

    if query_text:
        add(query_text[:80], entity_type="query")

    def add_person(source: dict[str, Any]) -> None:
        # 按人聚合的索引基础：姓名实体带出生元数据；有 name+date 时另建 `name|date` 复合键实体
        # （精确定位同名同生辰之人），有 date 时建 birthdate 实体（按生日横向聚合历史盘）。
        p_name = source.get("name")
        p_date = source.get("date")
        meta = birth_meta(source)
        if isinstance(p_name, str) and p_name.strip():
            add(p_name, metadata=meta)
            if isinstance(p_date, str) and p_date.strip():
                add(p_name, entity_type="person", key=f"{p_name.strip()}|{p_date.strip()}", metadata=meta)
        if isinstance(p_date, str) and p_date.strip():
            add(p_date.strip(), entity_type="birthdate", metadata=meta)

    add_person(input_normalized)
    for key in ("inner", "outer", "subject", "birth"):
        nested = input_normalized.get(key)
        if isinstance(nested, dict):
            add_person(nested)

    return entities


def _with_operational_recovery(code: str, details: dict[str, Any] | None) -> dict[str, Any]:
    """给每个错误码统一补 agent_recovery（安装/体检/重试/修入参语义，双语），已带者不覆盖。

    v0.36.0 B4：此前只认 runtime./transport./js_engine./backend_param 四类，其余 ~100 个码裸奔；现在
    走 errors.recovery_for 的三层规则（精确码表 → 后缀 → 前缀），新码落不到规则即 CI 红。
    """
    return recovery_for(code, details)

def _apply_response_view(envelope: ToolEnvelope, input_normalized: dict[str, Any]) -> ToolEnvelope:
    """response_view 响应视图：titles=只留段标题索引；sections=段标题+正文。

    只精简返回体（存档已保全量，完整结果可经 memory_show(run_id) 取回）；未知/缺省值原样返回。
    """
    view = str(input_normalized.get("response_view") or "").strip().lower()
    if view not in {"titles", "sections"} or not isinstance(envelope.data, dict):
        return envelope
    data = dict(envelope.data)
    contract = data.get("export_snapshot")
    if isinstance(contract, dict):
        slim = dict(contract)
        sections = [section for section in contract.get("sections", []) if isinstance(section, dict)]
        if view == "titles":
            slim["sections"] = [{"index": section.get("index"), "title": section.get("title")} for section in sections]
        else:
            slim["sections"] = [
                {"index": section.get("index"), "title": section.get("title"), "body": section.get("body")}
                for section in sections
            ]
        slim.pop("export_text", None)
        data["export_snapshot"] = slim
    if isinstance(data.get("snapshot_text"), str):
        data["snapshot_text"] = ""
    # `technique_card` **不裁**：它几行大小，而且正是「省 token 时也要知道这盘是谁算的、什么口径」
    # 的那份数据。裁掉它等于让最需要溯源的场景（精简模式）反而没有溯源。
    envelope.data = data
    envelope.warnings = [
        *envelope.warnings,
        f"response_view={view}：返回体已按需精简；完整快照已存档，可用 memory_show(run_id) 取回。",
    ]
    return envelope


def _build_dispatch_export_contract(result: ToolEnvelope) -> dict[str, Any]:
    # dispatch 轻契约：只带元信息与段标题索引；快照本体在 results[tool].data 已有一份，不再内嵌复制。
    export_snapshot = result.data.get("export_snapshot") if isinstance(result.data, dict) else None
    technique = export_snapshot.get("technique") if isinstance(export_snapshot, dict) else None
    section_titles: list[str] = []
    if isinstance(export_snapshot, dict):
        for section in export_snapshot.get("sections", []):
            if isinstance(section, dict) and section.get("title"):
                section_titles.append(section["title"])
    return {
        "ok": result.ok,
        "tool": result.tool,
        "summary": list(result.summary),
        "warnings": list(result.warnings),
        "memory_ref": result.memory_ref.model_dump(mode="json") if result.memory_ref else None,
        "has_export_snapshot": isinstance(export_snapshot, dict),
        "technique": technique,
        "selected_sections": list(export_snapshot.get("selected_sections", [])) if isinstance(export_snapshot, dict) else [],
        "format_source": export_snapshot.get("format_source") if isinstance(export_snapshot, dict) else None,
        "section_count": len(section_titles),
        "section_titles": section_titles,
        "bundle_version": export_snapshot.get("bundle_version") if isinstance(export_snapshot, dict) else None,
        "provenance": export_snapshot.get("provenance") if isinstance(export_snapshot, dict) else None,
        "citation": export_snapshot.get("citation") if isinstance(export_snapshot, dict) else None,
        "error": result.error.model_dump(mode="json") if result.error else None,
    }


def _build_compact_subresult_contract(result: ToolEnvelope) -> dict[str, Any]:
    data = result.data if isinstance(result.data, dict) else {}
    export_snapshot = data.get("export_snapshot") if isinstance(data.get("export_snapshot"), dict) else None
    section_titles = []
    if isinstance(export_snapshot, dict):
        for section in export_snapshot.get("sections", []):
            if isinstance(section, dict) and section.get("title"):
                section_titles.append(section["title"])
    return {
        "ok": result.ok,
        "tool": result.tool,
        "version": result.version,
        "input_normalized": result.input_normalized,
        "summary": list(result.summary),
        "warnings": list(result.warnings),
        "memory_ref": result.memory_ref.model_dump(mode="json") if result.memory_ref else None,
        "trace_id": result.trace_id,
        "group_id": result.group_id,
        "export_contract": {
            "has_export_snapshot": isinstance(export_snapshot, dict),
            "technique": export_snapshot.get("technique") if isinstance(export_snapshot, dict) else None,
            "selected_sections": list(export_snapshot.get("selected_sections", [])) if isinstance(export_snapshot, dict) else [],
            "format_source": export_snapshot.get("format_source") if isinstance(export_snapshot, dict) else None,
            "section_count": len(section_titles),
            "section_titles": section_titles,
            "bundle_version": export_snapshot.get("bundle_version") if isinstance(export_snapshot, dict) else None,
            "provenance": export_snapshot.get("provenance") if isinstance(export_snapshot, dict) else None,
            "citation": export_snapshot.get("citation") if isinstance(export_snapshot, dict) else None,
        },
        "error": result.error.model_dump(mode="json") if result.error else None,
    }
