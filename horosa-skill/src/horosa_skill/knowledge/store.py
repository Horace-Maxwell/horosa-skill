from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib.resources import files
from typing import Any

from horosa_skill.errors import ToolValidationError


ASTRO_LABELS = {
    "Sun": "太阳",
    "Moon": "月亮",
    "Mercury": "水星",
    "Venus": "金星",
    "Mars": "火星",
    "Jupiter": "木星",
    "Saturn": "土星",
    "Uranus": "天王星",
    "Neptune": "海王星",
    "Pluto": "冥王星",
    "North Node": "北交",
    "South Node": "南交",
    "Pars Fortuna": "福点",
    "Pars Spirit": "灵点",
    "Pars Venus": "爱点",
    "Pars Mercury": "弱点",
    "Pars Mars": "勇点",
    "Pars Jupiter": "赢点",
    "Pars Saturn": "罪点",
    "Pars Father": "父权点",
    "Pars Mother": "母爱点",
    "Pars Brothers": "友情点",
    "Pars Wedding [Male]": "婚姻点（男性）",
    "Pars Wedding [Female]": "婚姻点（女性）",
    "Pars Sons": "子嗣点",
    "Pars Diseases": "灾厄点",
    "Pars Life": "生命点",
    "Pars Radix": "光耀点",
    "Aries": "牡羊",
    "Taurus": "金牛",
    "Gemini": "双子",
    "Cancer": "巨蟹",
    "Leo": "狮子",
    "Virgo": "室女",
    "Libra": "天秤",
    "Scorpio": "天蝎",
    "Sagittarius": "射手",
    "Capricorn": "摩羯",
    "Aquarius": "宝瓶",
    "Pisces": "双鱼",
}

QIMEN_GOD_ALIASES = {
    "腾蛇": "螣蛇",
    "符": "值符",
    "蛇": "螣蛇",
    "阴": "太阴",
    "合": "六合",
    "虎": "白虎",
    "玄": "玄武",
    "地": "九地",
    "天": "九天",
}

QIMEN_STAR_ALIASES = {
    "蓬": "天蓬",
    "任": "天任",
    "冲": "天冲",
    "辅": "天辅",
    "英": "天英",
    "芮": "天芮",
    "禽": "天禽",
    "柱": "天柱",
    "心": "天心",
    "天内": "天芮",
}


def _data_path(name: str):
    return files("horosa_skill.knowledge.data").joinpath(name)


def _load_json(name: str) -> dict[str, Any]:
    return json.loads(_data_path(name).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_knowledge_bundles() -> dict[str, dict[str, Any]]:
    return {
        "astro": _load_json("astro.json"),
        "liureng": _load_json("liureng.json"),
        "qimen": _load_json("qimen.json"),
    }


def _normalize_house_key(key: str) -> str:
    text = (key or "").strip()
    if not text:
        return ""
    match = re.search(r"(\d+)", text)
    if match:
        number = int(match.group(1))
        if 1 <= number <= 12:
            return f"House{number}"
    normalized = text.replace("第", "").replace("宫", "").replace("房", "").strip().lower()
    aliases = {
        "asc": "House1",
        "命宫": "House1",
    }
    return aliases.get(normalized, text)


def _normalize_astro_key(category: str, key: str) -> str:
    text = (key or "").strip()
    if category == "house":
        return _normalize_house_key(text)
    if category == "aspect":
        return text
    bundle = load_knowledge_bundles()["astro"]
    labels = bundle.get("labels", {})
    reverse_labels = {value: one for one, value in labels.items() if isinstance(value, str)}
    return reverse_labels.get(text, text)


def _normalize_qimen_key(category: str, key: str) -> str:
    text = (key or "").strip()
    if category == "stem":
        return text[:1]
    if category == "door":
        return text if text.endswith("门") else f"{text}门"
    if category == "star":
        return QIMEN_STAR_ALIASES.get(text, text)
    if category == "god":
        return QIMEN_GOD_ALIASES.get(text, text)
    return text


def _normalize_liureng_branch(key: str) -> str:
    match = re.search(r"[子丑寅卯辰巳午未申酉戌亥]", key or "")
    return match.group(0) if match else ""


def _tips_to_rendered_text(title: str, tips: list[str]) -> str:
    lines = [f"[{title}]"]
    for tip in tips:
        tip_text = f"{tip}".strip()
        if not tip_text:
            continue
        if tip_text == "==":
            lines.append("")
            continue
        lines.append(f"- {tip_text}")
    return "\n".join(lines).strip()


def _strip_qimen_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _render_qimen_blocks(title: str, blocks: list[dict[str, Any]]) -> tuple[list[str], str]:
    lines = [f"[{title}]"]
    flat_lines: list[str] = []
    for block in blocks:
        block_type = block.get("type")
        if block_type == "blank":
            lines.append("")
            flat_lines.append("")
            continue
        if block_type == "divider":
            lines.append("==")
            flat_lines.append("==")
            continue
        if block_type == "subTitle":
            text = _strip_qimen_html(block.get("text", ""))
            if text:
                lines.append(f"## {text}")
                flat_lines.append(f"## {text}")
            continue
        text = _strip_qimen_html(block.get("text", ""))
        if text:
            lines.append(text)
            flat_lines.append(text)
    rendered = "\n".join(line for line in lines if line is not None).strip()
    normalized_lines = [line for line in flat_lines if line.strip()]
    return normalized_lines, rendered


def _build_liureng_house_entry(bundle: dict[str, Any], jiang_name: str, tian_branch: str, di_branch: str) -> dict[str, Any]:
    aliases = bundle.get("jiang_aliases", {})
    jiang_info = bundle.get("jiang_info", {})
    jiang_branch_note = bundle.get("jiang_branch_note", {})
    normalized_name = aliases.get(jiang_name, jiang_name)
    info = jiang_info.get(normalized_name)
    if not info:
        raise ToolValidationError(
            f"Unknown 六壬将神: {jiang_name}",
            code="knowledge.liureng.unknown_jiang",
            details={"jiang_name": jiang_name},
        )
    tian = _normalize_liureng_branch(tian_branch)
    di = _normalize_liureng_branch(di_branch)
    if not tian or not di:
        raise ToolValidationError(
            "六壬将盘悬浮知识需要有效的天盘地支与地盘地支。",
            code="knowledge.liureng.invalid_branch",
            details={"tian_branch": tian_branch, "di_branch": di_branch},
        )
    shen_entries = bundle.get("shen_entries", {})
    tian_entry = shen_entries.get(tian, {"title": f"{tian}神", "tips": []})
    di_entry = shen_entries.get(di, {"title": f"{di}神", "tips": []})
    notes = jiang_branch_note.get(normalized_name, {})
    tips: list[str] = []
    for line in info.get("intros", []):
        tips.append(line)
    for line in info.get("verses", []):
        tips.append(f"**{line}**")
    for line in info.get("extra", []):
        tips.append(line)
    tips.extend(
        [
            "==",
            f"**天盘神：**{tian_entry.get('title', tian)}",
            f"{tian}——{notes.get(tian, '未载于《将》文。')}。",
            "==",
            f"**地盘神：**{di_entry.get('title', di)}",
            f"{di}——{notes.get(di, '未载于《将》文。')}。",
        ]
    )
    return {
        "domain": "liureng",
        "category": "house",
        "key": normalized_name,
        "query_normalized": {
            "jiang_name": normalized_name,
            "tian_branch": tian,
            "di_branch": di,
        },
        "title": jiang_name or normalized_name,
        "tips": tips,
        "lines": [line for line in tips if line and line != "=="],
        "rendered_text": _tips_to_rendered_text(jiang_name or normalized_name, tips),
        "source": "xingque_hover_docs",
    }


def build_knowledge_registry(domain: str | None = None) -> dict[str, Any]:
    bundles = load_knowledge_bundles()
    domains = [domain] if domain else sorted(bundles)
    result_domains: list[dict[str, Any]] = []
    for name in domains:
        bundle = bundles.get(name)
        if not bundle:
            raise ToolValidationError(
                f"Unknown knowledge domain: {name}",
                code="knowledge.unknown_domain",
                details={"domain": name},
            )
        if name == "astro":
            categories = [
                {
                    "name": category,
                    "count": len(entries),
                    "keys": sorted(entries)[:20],
                    "supports": ["read"],
                }
                for category, entries in bundle.get("categories", {}).items()
            ]
        elif name == "qimen":
            categories = [
                {
                    "name": category,
                    "count": len(entries),
                    "keys": sorted(entries)[:20],
                    "supports": ["read"],
                }
                for category, entries in bundle.get("categories", {}).items()
            ]
        else:
            categories = [
                {
                    "name": "shen",
                    "count": len(bundle.get("shen_entries", {})),
                    "keys": sorted(bundle.get("shen_entries", {})),
                    "supports": ["read"],
                },
                {
                    "name": "house",
                    "count": len(bundle.get("jiang_info", {})),
                    "keys": sorted(bundle.get("jiang_info", {})),
                    "supports": ["read", "jiang_name+tian_branch+di_branch"],
                },
            ]
        result_domains.append(
            {
                "domain": name,
                "source": "xingque_hover_docs",
                "categories": categories,
            }
        )
    return {
        "source": "xingque_hover_docs",
        "domains": result_domains,
    }


def read_knowledge_entry(payload: dict[str, Any]) -> dict[str, Any]:
    bundles = load_knowledge_bundles()
    domain = f"{payload.get('domain') or ''}".strip()
    category = f"{payload.get('category') or ''}".strip()
    key = f"{payload.get('key') or ''}".strip()
    if domain not in bundles:
        raise ToolValidationError(
            f"Unknown knowledge domain: {domain}",
            code="knowledge.unknown_domain",
            details={"domain": domain},
        )
    if domain == "astro":
        bundle = bundles["astro"]
        categories = bundle.get("categories", {})
        if category == "aspect":
            aspect_key = str(payload.get("aspect_degree") if payload.get("aspect_degree") is not None else key).strip()
            entry = categories.get("aspect", {}).get(aspect_key)
            if not entry:
                raise ToolValidationError(
                    f"Unknown astro aspect: {aspect_key}",
                    code="knowledge.astro.unknown_key",
                    details={"category": category, "key": aspect_key},
                )
            object_a = f"{payload.get('object_a') or ''}".strip()
            object_b = f"{payload.get('object_b') or ''}".strip()
            title = entry.get("title", "")
            tips = list(entry.get("tips", []))
            if object_a and object_b:
                title = f"{ASTRO_LABELS.get(object_a, object_a)} - {ASTRO_LABELS.get(object_b, object_b)}：{entry.get('title', '')}"
                if tips and not tips[0].startswith("对象："):
                    tips.insert(0, f"对象：{ASTRO_LABELS.get(object_a, object_a)} 与 {ASTRO_LABELS.get(object_b, object_b)}")
            return {
                "domain": domain,
                "category": category,
                "key": aspect_key,
                "query_normalized": {"key": aspect_key, "object_a": object_a or None, "object_b": object_b or None},
                "title": title,
                "tips": tips,
                "lines": [tip for tip in tips if tip and tip != "=="],
                "rendered_text": _tips_to_rendered_text(title, tips),
                "source": "xingque_hover_docs",
            }
        normalized_key = _normalize_astro_key(category, key)
        entry = categories.get(category, {}).get(normalized_key)
        if not entry:
            raise ToolValidationError(
                f"Unknown astro knowledge key: {key}",
                code="knowledge.astro.unknown_key",
                details={"category": category, "key": key, "normalized_key": normalized_key},
            )
        tips = list(entry.get("tips", []))
        return {
            "domain": domain,
            "category": category,
            "key": normalized_key,
            "query_normalized": {"key": normalized_key},
            "title": entry.get("title", normalized_key),
            "tips": tips,
            "lines": [tip for tip in tips if tip and tip != "=="],
            "rendered_text": _tips_to_rendered_text(entry.get("title", normalized_key), tips),
            "source": "xingque_hover_docs",
        }

    if domain == "liureng":
        bundle = bundles["liureng"]
        if category == "shen":
            normalized_key = _normalize_liureng_branch(key)
            entry = bundle.get("shen_entries", {}).get(normalized_key)
            if not entry:
                raise ToolValidationError(
                    f"Unknown 六壬地支 knowledge key: {key}",
                    code="knowledge.liureng.unknown_key",
                    details={"category": category, "key": key},
                )
            tips = list(entry.get("tips", []))
            return {
                "domain": domain,
                "category": category,
                "key": normalized_key,
                "query_normalized": {"key": normalized_key},
                "title": entry.get("title", normalized_key),
                "tips": tips,
                "lines": [tip for tip in tips if tip and tip != "=="],
                "rendered_text": _tips_to_rendered_text(entry.get("title", normalized_key), tips),
                "source": "xingque_hover_docs",
            }
        if category == "house":
            return _build_liureng_house_entry(
                bundle,
                jiang_name=f"{payload.get('jiang_name') or key or ''}".strip(),
                tian_branch=f"{payload.get('tian_branch') or ''}".strip(),
                di_branch=f"{payload.get('di_branch') or ''}".strip(),
            )
        raise ToolValidationError(
            f"Unknown 六壬 knowledge category: {category}",
            code="knowledge.liureng.unknown_category",
            details={"category": category},
        )

    bundle = bundles["qimen"]
    normalized_key = _normalize_qimen_key(category, key)
    entry = bundle.get("categories", {}).get(category, {}).get(normalized_key)
    if not entry:
        raise ToolValidationError(
            f"Unknown 奇门 knowledge key: {key}",
            code="knowledge.qimen.unknown_key",
            details={"category": category, "key": key, "normalized_key": normalized_key},
        )
    lines, rendered_text = _render_qimen_blocks(entry.get("title", normalized_key), entry.get("blocks", []))
    return {
        "domain": domain,
        "category": category,
        "key": normalized_key,
        "query_normalized": {"key": normalized_key},
        "title": entry.get("title", normalized_key),
        "blocks": entry.get("blocks", []),
        "lines": lines,
        "rendered_text": rendered_text,
        "source": "xingque_hover_docs",
    }
