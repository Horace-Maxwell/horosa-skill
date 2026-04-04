from __future__ import annotations

from typing import Any

from horosa_skill.exports.registry import (
    AI_EXPORT_SETTINGS_VERSION,
    get_technique_info,
    map_legacy_section_title,
    normalize_astro_meaning_setting,
    normalize_planet_info_setting,
    normalize_section_title,
    unique_list,
)


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
    safe_export_text = strict_filtered or render_sections_to_text(
        [
            {
                "content": section["content"],
            }
            for section in filtered_sections
            if normalize_section_title(section["title"]) not in forbidden
        ]
    )

    unknown_detected = [title for title in detected_titles if normalize_section_title(title) not in {normalize_section_title(item) for item in preset_sections}]
    missing_selected = [title for title in selected_normalized if normalize_section_title(title) not in {normalize_section_title(item) for item in detected_titles}]
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
        "sections": filtered_sections,
        "raw_text": raw_text,
        "filtered_text": strict_filtered,
        "export_text": safe_export_text,
    }
