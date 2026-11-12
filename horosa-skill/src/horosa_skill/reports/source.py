"""读存档：一次运行留下的结果、导出段、技法卡，以及调用方写回的答案。这一层不做判断，人读章节也从这里出。"""

from __future__ import annotations

import copy
import re

from typing import Any

# 报告标题用的技法名：导出注册表的 label 有些是桌面端的页签名（「其他页面」）、有些几张盘同名（三份「易卦」、
# 两份「八字」），推运类还带「推运盘-」「星运-」分组前缀。只改报告标题，不动注册表与引擎。
_REPORT_TECHNIQUE_NAMES = {
    "nongli_time": "农历时间换算", "otherbu": "西洋游戏（占星骰子）", "bazi_direct": "八字直断",
    "gua_desc": "卦义说明", "gua_meiyi": "梅花易数卦义", "sixyao": "六爻", "liureng_gods": "大六壬",
    "liureng_runyear": "大六壬行年", "ziwei_rules": "紫微斗数规则", "chart13": "十三宫扩展盘", "zr": "黄道释放",
    "germany": "量化盘（汉堡学派中点）",
}

_REPORT_GROUP_PREFIXES = ("推运盘-", "星运-", "推运盘—", "星运—")

def report_technique_name(tool_name: str, label: str) -> str:
    if tool_name in _REPORT_TECHNIQUE_NAMES:
        return _REPORT_TECHNIQUE_NAMES[tool_name]
    for prefix in _REPORT_GROUP_PREFIXES:
        if label.startswith(prefix):
            return label[len(prefix):]
    return label

# 技法卡设置值 → 人读文字（码表与 schemas/tools 里各字段的 description 同源）；None = 不列这一行。
_SETTING_CODES: dict[str, dict[str, str]] = {
    "zodiacal": {"0": "回归黄道", "1": "恒星黄道"},
    "timeAlg": {"0": "真太阳时", "1": "直接时间（钟表时）"},
}

# 人读附录不列的设置：宫制 / 黄道 / 岁差 / 性别——技法卡里是请求口径（缺省值），可能与盘面实际不同（巴比伦是恒星黄道无宫位、
# 卜卦按自己的宫制），实际值以正文「起盘信息」为准；性别已在基本信息里。机读 JSON 的 technique_card 照常保留全部。
_SETTINGS_SHOWN_ELSEWHERE = frozenset({"hsys", "zodiacal", "siderealAyanamsa", "gender"})

def setting_reader_text(key: str, value: Any, *, standalone: bool = False) -> str | None:
    """技法卡的一项设置 → 读者看得懂的字；None = 这一行不印。完整报告（附录 / 封面「关键设置」）与技法依据报告共用这一个
    （v0.50.0，评审 R-09：此前技法依据报告印的是 `分宫制=1；古典口径=False；岁差=`）。

    standalone=False（完整报告）：宫制 / 黄道 / 岁差 / 性别不列（正文「起盘信息」与基本信息里有实际值），没有码表的枚举不印。
    standalone=True（技法依据报告，单独成文）：这几项照列（要不要省掉由维护者定，见 LESSONS），有码表的写字，没有码表的照原值写；
    空值一律不列。"""
    if value is None or str(value).strip() == "":
        return None
    if key in _SETTINGS_SHOWN_ELSEWHERE and not standalone:
        return None
    if isinstance(value, bool) or key in ("after23NewDay", "lateZiHourUseNextDay") and str(value) in ("0", "1"):
        return "是" if str(value).lower() in ("true", "1") else "否"
    mapped = _SETTING_CODES.get(key, {}).get(str(value))
    if mapped:
        return mapped
    if standalone and key == "hsys":
        from horosa_skill.astro_rulers import HOUSE_SYSTEM_LABELS

        return HOUSE_SYSTEM_LABELS.get(str(value), str(value))
    if standalone and key == "gender":
        return _GENDER_LABELS.get(str(value).lower(), str(value))
    if standalone:
        return str(value)
    # 没有人读码表的枚举（贵人法 2、流派 donggong、主限法 core_alchabitius…）不印：印出来读者也看不懂。
    if isinstance(value, (int, float)) or re.fullmatch(r"[A-Za-z0-9_\-]+", str(value)):
        return None
    return str(value)


def _setting_text(key: str, value: Any) -> str | None:
    return setting_reader_text(key, value)

_GENDER_LABELS = {"1": "男", "0": "女", "true": "男", "false": "女", "male": "男", "female": "女", "m": "男", "f": "女"}

def _coord_text(value: Any) -> str:
    """星阙的经纬度写法（`121e28` / `31n13`）→ 「东经 121°28′」「北纬 31°13′」；认不出原样返回。"""
    match = re.fullmatch(r"\s*(\d{1,3})\s*([nsewNSEW])\s*(\d{1,2})(?:\s*(\d{1,2}))?\s*", str(value or ""))
    if not match:
        return str(value)
    degrees, hemisphere, minutes, seconds = match.groups()
    label = {"n": "北纬", "s": "南纬", "e": "东经", "w": "西经"}[hemisphere.lower()]
    return f"{label} {int(degrees)}°{int(minutes):02d}′" + (f"{int(seconds):02d}″" if seconds else "")

def moment_text(input_normalized: Any) -> str:
    """起盘时刻 / 时区 / 地点一行（技法依据报告每个技法下面一行）：只用存档入参里写着的值；缺哪项就不写哪项。"""
    if not isinstance(input_normalized, dict):
        return ""
    when = " ".join(str(input_normalized.get(k)) for k in ("date", "time") if input_normalized.get(k))
    zone = str(input_normalized.get("zone") or "")
    place = str(input_normalized.get("place") or input_normalized.get("pos") or "")
    coords = "，".join(_coord_text(input_normalized.get(k)) for k in ("lat", "lon") if input_normalized.get(k))
    parts = []
    if when:
        parts.append(f"起盘时刻 {when}" + (f"（时区 {zone}）" if zone else ""))
    elif zone:
        parts.append(f"时区 {zone}")
    if place or coords:
        parts.append("地点 " + (place + (f"（{coords}）" if coords else "") if place else coords))
    return "；".join(parts)


_BASIS_FIELDS = (
    ("name", "姓名"), ("gender", "性别"), ("date", "日期"), ("time", "时间"), ("zone", "时区"),
    ("pos", "地点"), ("place", "地点"), ("lat", "纬度"), ("lon", "经度"), ("question", "所问"),
    ("askEvent", "所问"), ("datetime", "推运目标时刻"), ("year", "年份"), ("ingressTerm", "入宫节气"),
)


def read_payload(source_artifact: dict[str, Any]) -> dict[str, Any]:
    payload = source_artifact.get("payload")
    return payload if isinstance(payload, dict) else {}


def read_export_format(payload: dict[str, Any]) -> dict[str, Any]:
    # 唯一导出契约 = data.export_snapshot；旧归档（曾带 export_format 副本）回退读取保持可回放。
    data = payload.get("data") if isinstance(payload, dict) else {}
    if not isinstance(data, dict):
        return {}
    contract = data.get("export_snapshot")
    if isinstance(contract, dict):
        return contract
    legacy = data.get("export_format")
    return legacy if isinstance(legacy, dict) else {}


def read_source_meta(
    *,
    run: dict[str, Any],
    source_artifact: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload, dict) else {}
    export_snapshot = data.get("export_snapshot") if isinstance(data, dict) else {}
    technique = export_snapshot.get("technique") if isinstance(export_snapshot, dict) else {}
    record_meta = payload.get("record_meta") if isinstance(payload, dict) else {}
    return {
        "tool_name": payload.get("tool") or source_artifact.get("tool_name"),
        "technique": technique.get("key") if isinstance(technique, dict) else None,
        "technique_label": technique.get("label") if isinstance(technique, dict) else None,
        "artifact_path": source_artifact.get("path"),
        "artifact_kind": source_artifact.get("kind"),
        "trace_id": payload.get("trace_id") or (record_meta or {}).get("trace_id"),
        "group_id": payload.get("group_id") or run.get("group_id") or (record_meta or {}).get("group_id"),
    }


def read_export_sections(export_format: dict[str, Any], *, include_body: bool = False) -> list[dict[str, Any]]:
    sections = export_format.get("sections")
    if not isinstance(sections, list):
        return []
    result: list[dict[str, Any]] = []
    for index, section in enumerate(sections, start=1):
        if not isinstance(section, dict):
            continue
        lines = section.get("lines") if isinstance(section.get("lines"), list) else []
        body = section.get("body")
        if not body and lines:
            body = "\n".join(str(line) for line in lines)
        section_payload = {
            "id": section.get("id") or f"section_{index}",
            "cite_id": f"E{index}",  # 段号：报告里的盘面段与 AI 引用 [E3] 用同一个编号（与 _document_sections_from_export_format 同序）
            "title": str(section.get("title") or f"Section {index}"),
            "line_count": len(lines),
        }
        if include_body:
            section_payload["body"] = str(body or "")
            section_payload["lines"] = [str(line) for line in lines]
        result.append(section_payload)
    return result


def document_sections_from_export_format(export_format: dict[str, Any]) -> list[dict[str, Any]]:
    sections = export_format.get("sections")
    if not isinstance(sections, list):
        return []
    # 局部导入：service 包导入时会回头导入 reports（顶层导入会循环）
    from horosa_skill.exports.contract import missing_detail_text


    result: list[dict[str, Any]] = []
    for index, section in enumerate(sections, start=1):
        if not isinstance(section, dict):
            continue
        lines = section.get("lines")
        body = section.get("body")
        if not body and isinstance(lines, list):
            body = "\n".join(str(line) for line in lines)
        title = str(section.get("title") or f"导出章节 {index}")
        # 引擎这次没给内容的段，导出层填的是一句写给 AI 的护栏话（service/_common._missing_detail_text）。
        # 机读版照留（AI 要知道缺了什么）；人读版不给它一个标题加一段护栏话，统一记进附录「本次未产出」。
        placeholder = str(body or "").strip() in ("", missing_detail_text(title))
        result.append(
            {
                "id": section.get("id") or f"export_section_{index}",
                "cite_id": f"E{index}",
                "title": title,
                "body": str(body or ""),
                "items": section,
                # 人读版收录全部盘面段（「完整盘面」一部分）；正文是引擎原文，不截断。
                "human_visible": not placeholder,
                "group": "chart",
                **({"placeholder": True} if placeholder else {}),
            }
        )
    return result


def chart_basis_section(
    input_normalized: dict[str, Any], source: dict[str, Any], *, card: dict[str, Any] | None = None
) -> dict[str, Any]:
    rows = [("技法", str(source.get("technique_label") or source.get("tool_name") or ""))]
    seen: set[str] = set()
    for key, label in _BASIS_FIELDS:
        value = input_normalized.get(key)
        if value in (None, "") or label in seen:
            continue
        if key == "name" and not isinstance(value, str):
            continue  # 卦类工具的 name 是卦码列表，不是人名
        if key == "gender":
            # 命理类的 gender 是布尔（true = 男，见 schemas/tools/cn_mingli.py）；此前布尔原样印成「True」。
            value = _GENDER_LABELS.get(str(value).strip().lower(), value)
        elif key in ("lat", "lon"):
            value = _coord_text(value)
        seen.add(label)
        rows.append((label, str(value)))
    # 合盘：甲乙双方各一行（入参是 inner / outer 两份出生资料，顶层没有日期，封面此前只剩「技法」一格）。
    for key, label in (("inner", "甲方"), ("outer", "乙方")):
        person = input_normalized.get(key)
        if isinstance(person, dict) and person.get("date"):
            parts = [str(person.get(k)) for k in ("name", "date", "time") if person.get(k) not in (None, "")]
            rows.append((label, " ".join(parts)))
    # 关键设置放在封面（改了结论就变的口径：晚子时开关、贵人法、主限法……）——读者先知道「这盘按什么算的」再往下读
    # （kerykeion / Astro.com 报告头都先列口径）。只列读者看得懂的（与附录「技法依据」同一套人读规则）。
    settings = (card or {}).get("settings") if isinstance((card or {}).get("settings"), dict) else {}
    key_settings = []
    for key, item in settings.items():
        if isinstance(item, dict) and item.get("label"):
            text = _setting_text(str(key), item.get("value"))
            if text:
                key_settings.append(f"{item['label']}：{text}")
    if key_settings:
        rows.append(("关键设置", "；".join(key_settings)))
    body = "| 项目 | 内容 |\n| --- | --- |\n" + "\n".join(f"| {k} | {v.replace('|', '／')} |" for k, v in rows)
    return {"id": "chart_basis", "title": "基本信息", "body": body, "items": dict(rows), "human_visible": True, "group": "basis"}


def appendix_sections(
    data: dict[str, Any], *, source: dict[str, Any], provenance: dict[str, Any], unproduced: list[str] | None = None
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    card = data.get("technique_card") if isinstance(data.get("technique_card"), dict) else {}
    if card:
        versions = card.get("versions") if isinstance(card.get("versions"), dict) else {}
        settings = card.get("settings") if isinstance(card.get("settings"), dict) else {}
        lines = ["| 项目 | 内容 |", "| --- | --- |"]
        technique = card.get("technique") if isinstance(card.get("technique"), dict) else {}
        label = str(technique.get("label") or source.get("technique_label") or "")
        lines.append(f"| 技法 | {report_technique_name(str(source.get('tool_name') or ''), label)} |")
        # 人读附录只放读者看得懂的口径：布尔 / 枚举码翻成文字，空值不列；引擎内部名、导出设置版本这类
        # 机器字段留在机读 JSON 的 technique_card 里（v0.43 评审：「古典口径 False」「分宫制 1」漏到读者面前）。
        for key, item in settings.items():
            if isinstance(item, dict) and item.get("label"):
                text = _setting_text(str(key), item.get("value"))
                if text:
                    lines.append(f"| {item['label']} | {text} |")
        for key, label in (("skill", "排盘程序版本"), ("runtime", "离线计算包版本")):
            if versions.get(key) not in (None, ""):
                lines.append(f"| {label} | {versions[key]} |")
        lines.append("| 数据来源 | 星阙（Horosa）排盘引擎，本机离线计算；盘面文字为引擎导出原文，报告只做排版 |")
        if unproduced:  # 一行就够：单列成节时常常只有它被挤到最后一页
            lines.append(f"| 本次未产出 | 引擎这次没有给出这些段落的内容：{'、'.join(unproduced)} |")
        out.append({"id": "technique_basis", "title": "技法依据", "body": "\n".join(lines), "items": card,
                    "human_visible": True, "group": "appendix"})
    knowledge = data.get("knowledge_context") if isinstance(data.get("knowledge_context"), dict) else {}
    entries = [e for e in knowledge.get("entries") or [] if isinstance(e, dict)]
    if entries:
        # 只列引用、不印正文：存档本就只存引用（knowledge/user.py::redact_for_storage）；报告常被转给别人看，
        # 用户的私人笔记不该跟着出去（v0.43 知识库审查 H6）。
        rows = ["| 资料 | 条目 | 字数 | 带入方式 |", "| --- | --- | --- | --- |"]
        for e in entries:
            how = str(e.get("matched_by") or "")
            how = ("自动（auto）" if how == "auto" else f"标签 #{how[4:]}" if how.startswith("tag:")
                   else f"检索「{how[7:]}」" if how.startswith("search:") else "点名")
            passages = [str(p.get("lines")) for p in e.get("passages") or [] if isinstance(p, dict) and p.get("lines")]
            chars = f"{e.get('chars')}" + (f"（带入相关段落：第{'、'.join(passages)}行）" if e.get("truncated") and passages
                                           else "（带入时截断）" if e.get("truncated") else "")
            rows.append(f"| {str(e.get('title') or '').replace('|', '／')} | {str(e.get('id') or '').replace('|', '／')} | {chars} | {how} |")
        out.append({"id": "user_knowledge", "title": "自备参考资料",
                    "body": "本次计算附带了使用者自己的以下资料（不是引擎输出；正文不随报告印出）：\n\n" + "\n".join(rows),
                    "items": knowledge, "human_visible": True, "group": "appendix"})
    if unproduced and not card:
        out.append({"id": "chart_unproduced", "title": "本次未产出",
                    "body": "引擎这次没有给出以下段落的内容（盘面里不再单列空标题）：\n" + "、".join(unproduced),
                    "items": {"titles": unproduced}, "human_visible": True, "group": "appendix"})
    citation = provenance.get("citation") if isinstance(provenance, dict) else None
    if citation:
        # 机读来源（导出文件名 / 设置版本）只留在 JSON；人读版的来源已是「技法依据」表的最后一行。
        out.append({"id": "chart_source", "title": "来源",
                    "body": "星阙（Horosa）排盘引擎，本机离线计算；盘面文字为引擎导出原文，报告只做排版。",
                    "items": {"citation": citation},
                    "human_visible": not card, "group": "appendix"})
    return out


def read_provenance(*, export_snapshot: Any, export_format: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    snapshot_provenance = export_snapshot.get("provenance") if isinstance(export_snapshot, dict) else {}
    format_provenance = export_format.get("provenance") if isinstance(export_format, dict) else {}
    snapshot_bundle = export_snapshot.get("bundle_version") if isinstance(export_snapshot, dict) else None
    snapshot_citation = export_snapshot.get("citation") if isinstance(export_snapshot, dict) else None
    return {
        "source_domain": (snapshot_provenance or {}).get("source_domain") or (format_provenance or {}).get("source_domain"),
        "bundle_version": export_format.get("bundle_version") or snapshot_bundle,
        "citation": export_format.get("citation") or snapshot_citation,
        "technique": source.get("technique"),
        "artifact_path": source.get("artifact_path"),
        "trace_id": source.get("trace_id"),
        "group_id": source.get("group_id"),
    }


def read_export_text(*, export_snapshot: dict[str, Any], export_format: dict[str, Any], payload: dict[str, Any] | None = None) -> str:
    # 新契约取 export_text；旧归档回退 export_format.snapshot_text；末级回退顶层 data.snapshot_text。
    data = payload.get("data") if isinstance(payload, dict) else {}
    top_snapshot = data.get("snapshot_text") if isinstance(data, dict) else ""
    return str(export_snapshot.get("export_text") or export_format.get("snapshot_text") or top_snapshot or "")


def read_user_question(run: dict[str, Any]) -> str:
    return str(run.get("user_question") or run.get("query_text") or "").strip()


def read_caller_answer(*, run: dict[str, Any], ai_report: dict[str, Any] | None) -> dict[str, Any]:
    """调用方自己写的答案：run 里写回的加这次传的，不含任何回填。"""
    answer_structured = run.get("ai_answer_structured")
    base = copy.deepcopy(answer_structured) if isinstance(answer_structured, dict) else {}
    if run.get("ai_answer_text") and "answer_text" not in base:
        base["answer_text"] = run.get("ai_answer_text")
    if ai_report:
        base.update(copy.deepcopy(ai_report))
    return base


def analysis_section_matches_source(section: Any, source_title: str) -> bool:
    if not isinstance(section, dict):
        return False
    ai_title = str(section.get("source_section_title") or section.get("title") or "")
    evidence_lines = section.get("evidence_lines") if isinstance(section.get("evidence_lines"), list) else []
    evidence_text = " ".join(str(item) for item in evidence_lines)
    return bool(
        ai_title == source_title
        or (source_title and source_title in ai_title)
        or (ai_title and ai_title in source_title)
        or (source_title and source_title in evidence_text)
    )
