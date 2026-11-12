"""导出层：TOOL_EXPORT_TECHNIQUE_MAP、逐工具自动快照分派、生成式导出快照与导出契约。"""
from __future__ import annotations

from datetime import timezone
from typing import Any

from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.exports.contract import (  # noqa: F401 - 这里是这几个名字的历史出处
    _EXPORT_TECHNIQUE_OVERRIDES,
    TOOL_EXPORT_TECHNIQUE_MAP,
    _derive_export_technique_map,
)
from horosa_skill.exports import (
    build_export_registry,
    get_technique_info,
    parse_export_content,
)
from horosa_skill.exports.registry import MIRRORED_UPSTREAM_AIEXPORT_VERSION
from horosa_skill.service import _clock
from horosa_skill.service._common import (
    _export_body,
    _is_astro_chart_payload,
    _missing_detail_text,
    _stringify_export_body,
)
from horosa_skill.service.text.astro_core import (
    _build_aspect_section,
    _build_base_info_lines,
    _build_house_cusp_lines,
    _build_info_section,
    _build_lots_section,
    _build_planet_section,
    _build_possibility_section,
    _build_star_and_lot_position_lines,
    _top_level_chart_wrap,
)
from horosa_skill.service.text.chart_family import (
    _CHART_FAMILY_SNAPSHOT_TOOLS,
    _build_astro_snapshot_text,
    _build_india_snapshot_text,
    _chart_family_snapshot_fields,
)
from horosa_skill.service.text.chinese import (
    _build_calendar_month_snapshot_text,
    _build_gua_lookup_snapshot_text,
    _build_jieqi_snapshot_text,
    _build_liureng_snapshot_text,
    _build_nongli_snapshot_text,
    _build_ziwei_snapshot_text,
)
from horosa_skill.service.text.pd_zr import (
    _build_pdchart_snapshot_text,
    _build_primarydirect_snapshot_text,
    _build_zr_snapshot_text,
    _pd_effective_params,
    _pd_nearest_line,
    _pd_source_rows,
    _pd_table_rows,
    _zr_current_period_line,
    _zr_items,
)
from horosa_skill.service.text.predictive import (
    _build_predictive_snapshot_text,
    _natal_chart_wrap,
    _predictive_common_sections_text,
    _predictive_setup_section_text,
)
from horosa_skill.service.text.western import (
    _build_harmonic_snapshot_text,
    _build_relative_snapshot_text,
)

# 工具 → 导出键的表搬到了 exports/contract.py（knowledge 也要用）；名字留在这里，调用方不用改。


def _build_export_provenance(technique: str, snapshot_text: str | None) -> dict[str, Any]:
    technique_info = get_technique_info(technique) or {}
    registry = build_export_registry(technique=technique)
    return {
        "source_domain": "xingque_ai_export",
        "technique": technique,
        "category": technique_info.get("label"),
        "snapshot_key": technique_info.get("snapshot_key"),
        "bundle_version": registry.get("settings_version"),
        "section_migration_version": registry.get("section_migration_version"),
        "upstream_source_marker": "aiExport.js",
        # v0.36.0 C6：快照排版口径 = 镜像的上游 aiExport 版本（与 exports.registry 常量锁步；v57 切换时同批动）
        "astro_snapshot_format_version": MIRRORED_UPSTREAM_AIEXPORT_VERSION,
        "build_timestamp": _clock.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "snapshot_text_present": bool(snapshot_text),
    }


def _auto_snapshot_text_for_tool(tool_name: str, input_normalized: dict[str, Any], response_data: dict[str, Any]) -> str | None:
    if tool_name == "india_chart" and _is_astro_chart_payload(response_data):
        return _build_india_snapshot_text(input_normalized, response_data)
    if tool_name in _CHART_FAMILY_SNAPSHOT_TOOLS and tool_name != "harmonic" and _is_astro_chart_payload(response_data):
        return _build_astro_snapshot_text(_chart_family_snapshot_fields(input_normalized), response_data)
    # 调波盘：上游 v50 的 `harmonic` 键要求整套本命盘段 + 调波专属段。盘面本就在响应里（已在
    # `_run_harmonic_tool` 摊平到顶层），所以走通用盘面渲染器，再把 [调波位置]/[同频合相] 接在后面。
    # 这两段由 `_build_harmonic_snapshot_text` 出，它自带的 [起盘信息] 与通用器重复，故只取尾两段。
    if tool_name == "harmonic":
        extra = _build_harmonic_snapshot_text(input_normalized, response_data)
        # 后端只回了调波数据、没回盘面时（老响应形状 / 降级），退回「起盘信息 + 调波两段」的旧行为，
        # 而不是整个不出快照。
        if not _is_astro_chart_payload(response_data):
            return extra
        base = _build_astro_snapshot_text(_chart_family_snapshot_fields(input_normalized), response_data)
        tail = [block for block in extra.split("\n[") if block.startswith(("调波位置]", "同频合相]"))]
        return "\n".join([base] + [f"[{block.rstrip()}" for block in tail]) if tail else base
    if tool_name in {"solarreturn", "lunarreturn", "solararc", "givenyear", "profection"}:
        return _build_predictive_snapshot_text(tool_name, input_normalized, response_data)
    if tool_name == "pd":
        return _build_primarydirect_snapshot_text(input_normalized, response_data)
    if tool_name == "pdchart":
        return _build_pdchart_snapshot_text(input_normalized, response_data)
    if tool_name == "zr":
        return _build_zr_snapshot_text(input_normalized, response_data)
    if tool_name == "relative":
        return _build_relative_snapshot_text(input_normalized, response_data)
    if tool_name == "ziwei_rules":
        # ziwei_birth 由 _run_ziwei_tool 出 vendored 上游快照；这里只剩规则库（无盘）一支。
        return _build_ziwei_snapshot_text(input_normalized, response_data)
    if tool_name in {"liureng_gods", "liureng_runyear"}:
        return _build_liureng_snapshot_text(input_normalized, response_data)
    if tool_name == "jieqi_year":
        return _build_jieqi_snapshot_text(input_normalized, response_data)
    if tool_name == "nongli_time":
        return _build_nongli_snapshot_text(input_normalized, response_data)
    if tool_name == "calendar_month":
        return _build_calendar_month_snapshot_text(input_normalized, response_data)
    if tool_name in {"gua_desc", "gua_meiyi"}:
        return _build_gua_lookup_snapshot_text(tool_name, input_normalized, response_data)
    return None


def _pick_section_data(title: str, *, input_normalized: dict[str, Any], response_data: dict[str, Any]) -> Any:
    normalized_title = title.strip()
    if _is_astro_chart_payload(response_data):
        if normalized_title in {"起盘信息", "出生时间", "关系起盘信息", "节气盘参数", "星盘信息"}:
            lines = _build_base_info_lines(response_data, input_normalized)
            return _export_body("\n".join(lines).strip())
        if normalized_title in {"宫位宫头", "宫位总览"}:
            lines = _build_house_cusp_lines(response_data)
            return _export_body("\n".join(lines).strip())
        if normalized_title in {"星与虚点"}:
            lines = _build_star_and_lot_position_lines(response_data)
            return _export_body("\n".join(lines).strip())
        if normalized_title == "信息":
            lines = _build_info_section(response_data, input_normalized)
            return _export_body("\n".join(lines).strip())
        if normalized_title == "相位":
            lines = _build_aspect_section(response_data)
            return _export_body("\n".join(lines).strip())
        if normalized_title == "行星":
            lines = _build_planet_section(response_data)
            return _export_body("\n".join(lines).strip())
        if normalized_title == "希腊点":
            lines = _build_lots_section(response_data)
            return _export_body("\n".join(lines).strip())
        if normalized_title == "可能性":
            lines = _build_possibility_section(response_data)
            return _export_body("\n".join(lines).strip())

    if normalized_title in {"起盘信息", "出生时间", "关系起盘信息", "节气盘参数"}:
        return input_normalized
    if normalized_title in {"主限法设置", "主/界限法设置", "主限法盘设置", "十年大运设置"}:
        return {"input": input_normalized}
    # 其余段一律不带 data（v0.36.0）：引擎对象 chart/pan/liureng/bazi/jinkou/predictives 只在
    # `data.<key>` 出现一次。此前这里兜底 `return response_data` / `X or response_data` 把整份引擎
    # 对象复制进每个段，见 LESSONS v0.36.0「导出段 data 逐段整份复制」。
    return None


_SOLSTICE_EQUINOX = ("春分", "夏至", "秋分", "冬至")


_DEFAULT_OFF_REASON = "默认关段（上游 AI_EXPORT_DEFAULT_OFF_SECTIONS：体量大 / 教义型，缺省不导出；要它请在 sections 里点名）"


def _sections_not_requested(
    technique: str, input_normalized: dict[str, Any], preset_sections: list[str], *, tool_name: str | None = None,
    produced: set[str] | frozenset[str] = frozenset(),
) -> dict[str, str]:
    """这次调用本来就不产的预设段 → {段: 理由}：不选、不占位、不算缺（以前印「本次本地计算结果未返回…」，读起来像失败）。

    - 节气盘：二分二至的盘段只在这次要了那个节气时才出（`jieqis` 缺省 = 四个都要；`seedOnly` = 只要节气表）。
    - 这个工具按设计永不产出的段（exports.registry.SECTIONS_NOT_PRODUCED_BY_DESIGN，逐段带理由）——只在确实缺席时归入。
    - 默认关段缺席时（上游 AI_EXPORT_DEFAULT_OFF_SECTIONS）。"""
    from horosa_skill.exports.registry import AI_EXPORT_DEFAULT_OFF_SECTIONS, SECTIONS_NOT_PRODUCED_BY_DESIGN

    out: dict[str, str] = {}
    if technique == "jieqi":
        terms = input_normalized.get("jieqis")
        wanted = set(_SOLSTICE_EQUINOX) if not terms else {str(term).strip() for term in terms} & set(_SOLSTICE_EQUINOX)
        if input_normalized.get("seedOnly"):
            wanted = set()
        out.update({title: "这次没要这个节气的盘（jieqis / seedOnly）"
                    for title in preset_sections if title[:2] in _SOLSTICE_EQUINOX and title[:2] not in wanted})
    for title, reason in SECTIONS_NOT_PRODUCED_BY_DESIGN.get(tool_name or "", {}).items():
        if title in preset_sections and title not in produced:
            out[title] = reason
    for title in AI_EXPORT_DEFAULT_OFF_SECTIONS.get(technique, []):
        if title in preset_sections and title not in produced:
            out.setdefault(title, _DEFAULT_OFF_REASON)
    return out


def _build_generated_export_snapshot(
    *,
    technique: str,
    tool_name: str | None = None,
    input_normalized: dict[str, Any],
    response_data: dict[str, Any],
    snapshot_text: str | None = None,
    parsed_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    technique_info = get_technique_info(technique)
    if technique_info is None:
        return None

    preset_sections = list(technique_info["preset_sections"])
    forbidden_sections = {f"{item or ''}".strip() for item in technique_info.get("forbidden_sections", [])}
    selected_sections = list(preset_sections)
    settings_used = {
        "version": build_export_registry(technique=technique)["settings_version"],
        "sections": {technique: selected_sections},
        "planetInfo": {},
        "astroMeaning": {},
    }
    if technique_info["supports_planet_info"]:
        settings_used["planetInfo"][technique] = technique_info["planet_info_default"]
    if technique_info["supports_astro_meaning"] or technique_info["supports_hover_meaning"]:
        settings_used["astroMeaning"][technique] = technique_info["astro_meaning_default"]

    parsed_sections_by_title = {}
    detected_titles: list[str] = []
    unknown_detected_sections: list[str] = []
    missing_selected_sections: list[str] = []
    if isinstance(parsed_snapshot, dict):
        for section in parsed_snapshot.get("sections", []):
            if isinstance(section, dict) and section.get("title"):
                parsed_sections_by_title[section["title"]] = section
                title = f"{section['title']}".strip()
                if title and title not in forbidden_sections:
                    detected_titles.append(title)
        if detected_titles:
            merged_sections = list(preset_sections)
            for title in detected_titles:
                if title not in merged_sections:
                    merged_sections.append(title)
            selected_sections = [title for title in merged_sections if title not in forbidden_sections]
            settings_used["sections"][technique] = selected_sections
        unknown_detected_sections = list(parsed_snapshot.get("unknown_detected_sections", []) or [])
        missing_selected_sections = list(parsed_snapshot.get("missing_selected_sections", []) or [])

    # 这次调用没要的段（节气盘只查「立春」/ seedOnly：二分二至的盘本就不算）：不选、不占位、不算缺（深审 F13）。
    produced = {title for title, section in parsed_sections_by_title.items() if f"{section.get('body') or ''}".strip()}
    not_requested = _sections_not_requested(technique, input_normalized, preset_sections, tool_name=tool_name, produced=produced)
    if not_requested:
        selected_sections = [title for title in selected_sections if title not in not_requested]
        settings_used["sections"][technique] = selected_sections
        missing_selected_sections = [title for title in missing_selected_sections if title not in not_requested]

    sections: list[dict[str, Any]] = []
    rendered_blocks: list[str] = []
    for index, title in enumerate(selected_sections, start=1):
        parsed_section = parsed_sections_by_title.get(title, {})
        body = f"{parsed_section.get('body') or ''}".strip()
        if not body:
            # 段未进快照时才生成兜底正文（此前对每段都算一遍、还把整份引擎对象塞进段 data）。
            section_data = _pick_section_data(title, input_normalized=input_normalized, response_data=response_data)
            if isinstance(section_data, dict) and "__export_body__" in section_data:
                body = _stringify_export_body(section_data.get("__export_body__"))
            else:
                body = _stringify_export_body(section_data)
                # 守卫按**字节+行数**双判：单行 JSON dump 曾靠「只数行」漏进 export_text（303 KB）。
                if body and (len(body.encode("utf-8")) > 2048 or len(body.splitlines()) > 80):
                    body = _missing_detail_text(title)
            # 段既不在快照里、又无可生成正文 → 明示「未产出」占位（旧实现靠整份 dump 触发 80 行守卫才得到同一
            # 占位；段正文绝不裸空——faithfulness/报告/「不得臆造依赖」检查都以非空正文为前提）。
            if not body:
                body = _missing_detail_text(title)
        content = parsed_section.get("content") or (f"[{title}]\n{body}".strip() if body else f"[{title}]")
        rendered_blocks.append(content)
        # 段只存 body（content 可由 "[title]\nbody" 推导）；全文只存 export_text 一份；引擎对象只在
        # data.<key> 存一份 —— 段不再带 data 键（envelope schema 0.8.0）。
        sections.append(
            {
                "index": index,
                "raw_title": parsed_section.get("raw_title", title),
                "title": title,
                "included": True,
                "body": body,
            }
        )

    export_text = "\n\n".join(block for block in rendered_blocks if block.strip()).strip()
    provenance = _build_export_provenance(technique, snapshot_text)
    citation = (
        f"Xingque AI export · {technique_info.get('label', technique)} · "
        f"settings v{provenance.get('bundle_version')} · source {provenance.get('upstream_source_marker')}"
    )
    return {
        "technique": technique_info,
        "settings_used": settings_used,
        "section_titles_detected": detected_titles or [section["title"] for section in sections],
        "selected_sections": selected_sections,
        "unknown_detected_sections": unknown_detected_sections,
        "missing_selected_sections": missing_selected_sections,
        **({"not_requested_sections": [title for title in preset_sections if title in not_requested],
            "not_requested_reasons": {title: not_requested[title] for title in preset_sections if title in not_requested}}
           if not_requested else {}),
        "sections": sections,
        "export_text": export_text,
        "format_source": "snapshot_parser" if parsed_snapshot else "generated_template",
        "bundle_version": provenance.get("bundle_version"),
        "provenance": provenance,
        "citation": citation,
    }


def _attach_export_contract(tool_name: str, input_normalized: dict[str, Any], response_data: dict[str, Any]) -> dict[str, Any]:
    technique = TOOL_EXPORT_TECHNIQUE_MAP.get(tool_name)
    if not technique:
        return response_data

    augmented = dict(response_data)
    snapshot_text = augmented.get("snapshot_text") if isinstance(augmented.get("snapshot_text"), str) else None
    parsed_snapshot = augmented.get("export_snapshot") if isinstance(augmented.get("export_snapshot"), dict) else None
    if not snapshot_text:
        snapshot_text = _auto_snapshot_text_for_tool(tool_name, input_normalized, response_data)
        augmented["snapshot_text"] = snapshot_text
    # 星运族公共段（当前时点/方法说明）在统一出口追加一次,22 键全覆盖;追加后强制重解析。
    # [起盘信息] 按上游位于段首；已有该段的技法（推运族等）不重复加。
    predictive_setup = _predictive_setup_section_text(technique, input_normalized, response_data)
    if snapshot_text and predictive_setup and "[起盘信息]" not in snapshot_text:
        snapshot_text = f"{predictive_setup}\n\n{snapshot_text}"
        augmented["snapshot_text"] = snapshot_text
        parsed_snapshot = None
    moment_extra = augmented.pop("_moment_lines", None)
    if moment_extra is None and technique == "zodialrelease":
        # 上游 AstroZR.js:236：[当前时点] 追加「当前所处：L1 …期 / L2 …期」定位行（远端工具在统一出口补算）。
        zr_line = _zr_current_period_line(_zr_items(augmented))
        moment_extra = [zr_line] if zr_line else []
    if moment_extra is None and technique == "primarydirect":
        # 上游 AstroDirectMain.js:405-431：[当前时点] 追加「表中距今最近行」。
        pd_params = _pd_effective_params(augmented, input_normalized)
        pd_rows = _pd_table_rows(_pd_source_rows(augmented), pd_params)
        pd_wrap = _natal_chart_wrap(augmented) or _top_level_chart_wrap(augmented)
        nearest = _pd_nearest_line(pd_rows, pd_params, pd_wrap)
        moment_extra = [nearest] if nearest else []
    predictive_common = _predictive_common_sections_text(
        technique, input_normalized, moment_extra if isinstance(moment_extra, list) else None
    )
    if snapshot_text and predictive_common and "[方法说明]" not in snapshot_text:
        snapshot_text = f"{snapshot_text}\n\n{predictive_common}"
        augmented["snapshot_text"] = snapshot_text
        parsed_snapshot = None
    if snapshot_text and not parsed_snapshot:
        try:
            parsed_snapshot = parse_export_content(technique=technique, content=snapshot_text)
            augmented["export_snapshot"] = parsed_snapshot
        except ValueError:
            parsed_snapshot = None
    export_contract = _build_generated_export_snapshot(
        technique=technique,
        tool_name=tool_name,
        input_normalized=input_normalized,
        response_data=augmented,
        snapshot_text=snapshot_text,
        parsed_snapshot=parsed_snapshot,
    )
    if export_contract is None:
        # 兜底剥离：_run_* 自写 parser 形状 export_snapshot 而模板生成失败时，冗余全文键不外泄。
        if isinstance(augmented.get("export_snapshot"), dict):
            augmented["export_snapshot"] = _slim_export_snapshot(augmented["export_snapshot"])
        return augmented

    # data.export_snapshot 是唯一导出契约（原 export_format 为其真子集，已并入不再单独产出）；
    # 原始全段快照的唯一权威是顶层 data.snapshot_text。
    augmented["export_snapshot"] = export_contract
    return augmented


def _slim_export_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """剥离 parser 中间态里的冗余全文键（与顶层 snapshot_text / export_text 重复）。"""
    slim = {key: value for key, value in snapshot.items() if key not in {"raw_text", "filtered_text", "snapshot_text"}}
    sections = slim.get("sections")
    if isinstance(sections, list):
        slim["sections"] = [
            {key: value for key, value in section.items() if key != "content"} if isinstance(section, dict) else section
            for section in sections
        ]
    return slim
