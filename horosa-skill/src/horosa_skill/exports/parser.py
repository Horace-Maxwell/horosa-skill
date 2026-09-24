from __future__ import annotations

import re

from typing import Any

from horosa_skill.exports.registry import (
    AI_EXPORT_SETTINGS_VERSION,
    JIEQI_SETTING_PRESETS,
    get_technique_info,
    map_legacy_section_title,
    normalize_astro_meaning_setting,
    normalize_planet_info_setting,
    normalize_section_title,
    unique_list,
)

# 上游 `exportKey === 'jieqi' || isJieQiSplitSettingKey(exportKey)`（aiExport.js:3552）。
JIEQI_EXPORT_KEYS = frozenset({"jieqi", *JIEQI_SETTING_PRESETS})


def parse_section_title_line(line: str | None) -> str:
    text = f"{line or ''}".strip()
    if not text:
        return ""
    if text.startswith("[") and text.endswith("]") and len(text) > 2:
        return normalize_section_title(text[1:-1])
    if text.startswith("【") and text.endswith("】") and len(text) > 2:
        return normalize_section_title(text[1:-1])
    return ""


def split_content_sections(content: str, technique: str) -> list[dict[str, Any]]:
    lines = f"{content or ''}".splitlines()
    sections: list[dict[str, Any]] = []
    current_title = ""
    current_raw_title = ""
    current_lines: list[str] = []

    def push_current() -> None:
        nonlocal current_title, current_raw_title, current_lines
        if not current_title and not "".join(current_lines).strip():
            current_lines = []
            return
        body_lines = current_lines[1:] if current_title and current_lines else current_lines
        sections.append(
            {
                "raw_title": current_raw_title,
                "title": current_title,
                "body": "\n".join(body_lines).strip(),
                "content": "\n".join(current_lines).strip(),
            }
        )
        current_title = ""
        current_raw_title = ""
        current_lines = []

    for line in lines:
        raw_title = parse_section_title_line(line)
        if raw_title:
            if current_lines:
                push_current()
            current_raw_title = raw_title
            current_title = map_legacy_section_title(technique, raw_title)
            current_lines = [line]
            continue
        current_lines.append(line)

    if current_lines:
        push_current()
    return sections


def render_sections_to_text(sections: list[dict[str, Any]]) -> str:
    blocks = [section["content"] for section in sections if f"{section.get('content', '')}".strip()]
    return "\n\n".join(blocks).strip()


_ASCII_I = re.IGNORECASE | re.ASCII  # 上游 JS 正则的 \b / \d 是 ASCII 语义；Python str 正则默认 Unicode（汉字算 \w），须 re.ASCII 对齐


def trim_planet_info_by_setting(content: str, setting: dict[str, Any] | None) -> str:
    """上游 aiExport.js:1933-2036 trimPlanetInfoBySetting 逐字移植：「星曜后天信息」导出开关（showHouse 宫位 / showRuler 主宰宫）。
    两者全开 → 原样返回（零回归）；否则把行内括号里**整段都是**后天信息（后天:… / Nth / - / NR… / 主…宫 / 宫位未知 / (第)X宫）的
    部分按开关裁成 `(宫位; 主宰)` 之一或整个删除；非后天信息括号（[Q-316/T-302]：三式合一「日马：申（坤二宫）」）原样保留。
    尾处理同上游：多空格并一、空括号删除、三连空行并二。"""
    source = f"{content or ''}"
    mode = normalize_planet_info_setting(setting)
    show_house = mode["showHouse"] == 1
    show_ruler = mode["showRuler"] == 1
    if show_house and show_ruler:
        return source

    def split_segments(text: str) -> list[str]:
        return [f"{item or ''}".strip() for item in re.split(r"[；;]", text) if f"{item or ''}".strip()]

    def is_planet_info_inner(inner: str) -> bool:
        txt = f"{inner or ''}".strip()
        if not txt:
            return False
        if re.match(r"^后天[:：]", txt):
            return True
        segs = split_segments(txt)
        if not segs:
            return False
        return all(
            re.fullmatch(r"\d{1,2}th", seg, _ASCII_I) is not None
            or seg == "-"
            or re.fullmatch(r"\d{1,2}R(?:\d{1,2}R)*", seg, _ASCII_I) is not None
            or re.fullmatch(r"主.+宫", seg) is not None
            or re.fullmatch(r"(宫位未知|主宫未知)", seg) is not None
            or re.fullmatch(r"第?[一二三四五六七八九十]+宫", seg) is not None
            for seg in segs
        )

    def split_planet_info_parts(inner: str) -> tuple[str, str]:
        txt = re.sub(r"^后天[:：]\s*", "", f"{inner or ''}").strip()
        house_part = ""
        ruler_part = ""
        for seg in split_segments(txt):
            if not house_part and re.fullmatch(r"\d{1,2}th|-", seg, _ASCII_I):
                house_part = seg
                continue
            if not ruler_part and re.fullmatch(r"\d{1,2}R(?:\d{1,2}R)*", seg, _ASCII_I):
                ruler_part = seg.upper()
                continue
            if not ruler_part and (re.match(r"^主", seg) or re.search(r"\b\d{1,2}R(?:\d{1,2}R)*\b", seg, _ASCII_I)):
                ruler_part = seg
                continue
            if not house_part and re.search(r"宫", seg):
                house_part = seg
                continue
            if not house_part:
                house_part = seg
                continue
            if not ruler_part:
                ruler_part = seg
        if not house_part:
            house_match = re.search(r"\b(\d{1,2}th|-)\b", txt, _ASCII_I)
            if house_match and house_match.group(1):
                house_part = house_match.group(1)
        if not ruler_part:
            ruler_match = re.search(r"\b(\d{1,2}R(?:\d{1,2}R)*)\b", txt, _ASCII_I)
            if ruler_match and ruler_match.group(1):
                ruler_part = ruler_match.group(1).upper()
        return f"{house_part or ''}".strip(), f"{ruler_part or ''}".strip()

    def replace_bracket(match: re.Match[str]) -> str:
        left, inner, right = match.group(1), match.group(2), match.group(3)
        if not is_planet_info_inner(inner):
            return match.group(0)
        house_part, ruler_part = split_planet_info_parts(inner)
        pieces: list[str] = []
        if show_house and house_part:
            pieces.append(house_part)
        if show_ruler and ruler_part:
            pieces.append(ruler_part)
        if not pieces:
            return ""
        return f"{left}{'; '.join(pieces)}{right}"

    out = re.sub(r"([（(])([^（）()]*)([）)])", replace_bracket, source)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"([（(])\s*([）)])", "", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out


def parse_export_content(
    *,
    technique: str,
    content: str,
    selected_sections: list[str] | None = None,
    planet_info: dict[str, Any] | None = None,
    astro_meaning: dict[str, Any] | None = None,
) -> dict[str, Any]:
    technique_info = get_technique_info(technique)
    if technique_info is None:
        raise ValueError(f"Unknown AI export technique: {technique}")

    # 「星曜后天信息」开关（上游 aiExport.js:6840 applyPlanetInfoFilterByContext：仅 planetInfo 技法、且只在显式设置非全开时改文）：
    # planet_info=None = 上游无用户设置 → 缺省全开 → 原样；给了对象才按 normalizePlanetInfoSetting 裁剪（缺键即 0，与上游同）。
    if technique_info["supports_planet_info"] and isinstance(planet_info, dict):
        content = trim_planet_info_by_setting(content, planet_info)

    raw_text = f"{content or ''}".strip()
    sections = split_content_sections(raw_text, technique)
    detected_titles = unique_list([section["title"] for section in sections if section["title"]])

    forbidden = {normalize_section_title(item) for item in technique_info["forbidden_sections"]}
    preset_sections = [normalize_section_title(item) for item in technique_info["preset_sections"]]
    requested = selected_sections[:] if selected_sections else technique_info["preset_sections"][:]
    selected_normalized = unique_list(
        [
            map_legacy_section_title(technique, item)
            for item in requested
            if map_legacy_section_title(technique, item) and normalize_section_title(map_legacy_section_title(technique, item)) not in forbidden
        ]
    )
    wanted = {normalize_section_title(item) for item in selected_normalized}

    filtered_sections = []
    for index, section in enumerate(sections, start=1):
        normalized_title = normalize_section_title(section["title"])
        include_section = True if not normalized_title else normalized_title in wanted
        if normalized_title and normalized_title in forbidden:
            include_section = False
        filtered_sections.append(
            {
                "index": index,
                "raw_title": section["raw_title"],
                "title": section["title"],
                "included": include_section,
                "body": section["body"],
                "content": section["content"],
            }
        )

    strict_filtered = render_sections_to_text([section for section in filtered_sections if section["included"]])
    if not strict_filtered and selected_sections and technique in JIEQI_EXPORT_KEYS:
        # [挂载自检 F-38]（上游 aiExport.js:3547-3552）：节气盘整键/分键——盘页签下的内容只含当前一盘，用户显式勾的段
        # 本内容没有 → 真取消（''）而非回吐全文（否则「只要夏至星盘」被盖成「春分整份」）。其他技法段名与内容同源、
        # 失配只会是命名漂移，保留下面「回退剥后文」兜底。
        safe_export_text = ""
    else:
        safe_export_text = strict_filtered or render_sections_to_text(
            [
                {
                    "content": section["content"],
                }
                for section in filtered_sections
                if normalize_section_title(section["title"]) not in forbidden
            ]
        )

    optional_norm = {normalize_section_title(item) for item in technique_info.get("optional_sections", [])}
    unknown_detected = [title for title in detected_titles if normalize_section_title(title) not in {normalize_section_title(item) for item in preset_sections}]
    # A selected section counts as "missing" only if the snapshot didn't emit it AND it isn't one of the
    # technique's optional sections (星阙-UI-only search panels / mode-conditional sections — see registry).
    missing_selected = [
        title
        for title in selected_normalized
        if normalize_section_title(title) not in {normalize_section_title(item) for item in detected_titles}
        and normalize_section_title(title) not in optional_norm
    ]
    settings_used = {
        "version": AI_EXPORT_SETTINGS_VERSION,
        "sections": {technique: selected_normalized},
        "planetInfo": {},
        "astroMeaning": {},
    }
    if technique_info["supports_planet_info"]:
        settings_used["planetInfo"][technique] = normalize_planet_info_setting(planet_info)
    if technique_info["supports_astro_meaning"] or technique_info["supports_hover_meaning"]:
        settings_used["astroMeaning"][technique] = normalize_astro_meaning_setting(astro_meaning)

    return {
        "technique": technique_info,
        "settings_used": settings_used,
        "section_titles_detected": detected_titles,
        "selected_sections": selected_normalized,
        "unknown_detected_sections": unknown_detected,
        "missing_selected_sections": missing_selected,
        # 全文仅存 export_text 一份；原始输入回显（raw_text）与严格过滤中间态（filtered_text）
        # 与调用方已持有的内容重复，不再返回。
        "sections": filtered_sections,
        "export_text": safe_export_text,
    }
