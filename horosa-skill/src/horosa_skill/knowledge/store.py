from __future__ import annotations

import difflib
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Any

from horosa_skill.errors import ToolValidationError, bilingual
from horosa_skill.knowledge import retrieval
from horosa_skill.textscript import fold_to_simplified, looks_traditional


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
    bundles = {
        "astro": _load_json("astro.json"),
        "liureng": _load_json("liureng.json"),
        "qimen": _load_json("qimen.json"),
    }
    bundles.update(load_helpdoc_bundles())
    return bundles


@lru_cache(maxsize=1)
def load_helpdoc_bundles() -> dict[str, dict[str, Any]]:
    """方法论手册知识包（v0.28.0，`scripts/gen_knowledge_packs.py` 从上游 HelpDoc 收割）。

    统一 schema `horosa.knowledge.helpdoc.v1`：{domain, label, source, categories:[{name,
    entries:[{key, text, source}]}]}——按目录自动发现，新增域零代码（三个 hover 域仍走各自的
    专用渲染分支，不动）。每条自带出处（组件文件 + tab + 上游版本/commit），是 SKILL.md
    「引教义必带出处」策略的机器前提。
    """
    out: dict[str, dict[str, Any]] = {}
    try:
        root = files("horosa_skill.knowledge.data").joinpath("helpdocs")
        for item in root.iterdir():
            if not item.name.endswith(".json"):
                continue
            try:
                bundle = json.loads(item.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            domain = f"{bundle.get('domain') or ''}".strip()
            if domain and bundle.get("schema") == "horosa.knowledge.helpdoc.v1":
                out[domain] = bundle
    except (FileNotFoundError, OSError):
        return {}
    return out


@lru_cache(maxsize=1)
def load_knowledge_index() -> dict[str, Any]:
    try:
        return _load_json("index.json")
    except FileNotFoundError:
        bundles = load_knowledge_bundles()
        return {
            "schema_version": 1,
            "bundle_version": 1,
            "source": "xingque_hover_docs",
            "build_timestamp": None,
            "upstream_source_marker": "xingque_hover_docs",
            "domains": [
                {
                    "domain": "astro",
                    "categories": [
                        {"name": key, "count": len(value), "keys_sample": sorted(value)[:20]}
                        for key, value in bundles["astro"].get("categories", {}).items()
                    ],
                    "missing_categories": [],
                    "fallback_categories": [],
                },
                {
                    "domain": "liureng",
                    "categories": [
                        {"name": "shen", "count": len(bundles["liureng"].get("shen_entries", {})), "keys_sample": sorted(bundles["liureng"].get("shen_entries", {}))[:20]},
                        {"name": "house", "count": len(bundles["liureng"].get("jiang_info", {})), "keys_sample": sorted(bundles["liureng"].get("jiang_info", {}))[:20]},
                    ],
                    "missing_categories": [],
                    "fallback_categories": [],
                },
                {
                    "domain": "qimen",
                    "categories": [
                        {"name": key, "count": len(value), "keys_sample": sorted(value)[:20]}
                        for key, value in bundles["qimen"].get("categories", {}).items()
                    ],
                    "missing_categories": [],
                    "fallback_categories": [],
                },
            ],
        }


def _domain_index(domain: str) -> dict[str, Any]:
    for item in load_knowledge_index().get("domains", []):
        if item.get("domain") == domain:
            return item
    return {}


def _knowledge_provenance(*, domain: str, category: str | None = None, key: str | None = None) -> dict[str, Any]:
    index = load_knowledge_index()
    return {
        "source_domain": "xingque_hover_docs",
        "domain": domain,
        "category": category,
        "key": key,
        "bundle_version": index.get("bundle_version"),
        "build_timestamp": index.get("build_timestamp"),
        "upstream_source_marker": index.get("upstream_source_marker", "xingque_hover_docs"),
        "coverage": _domain_index(domain),
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


def _liureng_jiang_overview(bundle: dict[str, Any], jiang_name: str, normalized_name: str, info: dict[str, Any]) -> dict[str, Any]:
    """没给天盘 / 地盘地支：读这一将本身，十二支下的注语逐支列出（检索结果给的 read 就是这个形状）。"""
    notes = bundle.get("jiang_branch_note", {}).get(normalized_name, {})
    tips = [*info.get("intros", []), *(f"**{line}**" for line in info.get("verses", [])), *info.get("extra", [])]
    if notes:
        tips.append("==")
        tips.extend(f"{branch}——{note}。" for branch, note in notes.items())
    return {
        "domain": "liureng",
        "category": "house",
        "key": normalized_name,
        "query_normalized": {"jiang_name": normalized_name, "tian_branch": "", "di_branch": ""},
        "title": f"十二天将 · {normalized_name}",
        "tips": tips,
        "lines": [line for line in tips if line and line != "=="],
        "rendered_text": _tips_to_rendered_text(jiang_name or normalized_name, tips),
        "source": "xingque_hover_docs",
        "bundle_version": load_knowledge_index().get("bundle_version"),
        "provenance": _knowledge_provenance(domain="liureng", category="house", key=normalized_name),
        "citation": f"Xingque hover knowledge · liureng/house/{normalized_name}",
    }


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
    if not (tian_branch or di_branch):
        return _liureng_jiang_overview(bundle, jiang_name, normalized_name, info)
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
        "bundle_version": load_knowledge_index().get("bundle_version"),
        "provenance": _knowledge_provenance(domain="liureng", category="house", key=normalized_name),
        "citation": f"Xingque hover knowledge · liureng/house/{normalized_name}",
    }


def build_knowledge_registry(domain: str | None = None) -> dict[str, Any]:
    bundles = load_knowledge_bundles()
    index = load_knowledge_index()
    domains = [canonical_domain(domain)] if domain else sorted(bundles)
    result_domains: list[dict[str, Any]] = []
    for name in domains:
        bundle = bundles[name]
        if bundle.get("schema") == "horosa.knowledge.helpdoc.v1":
            result_domains.append(
                {
                    "domain": name,
                    "label": bundle.get("label"),
                    "source": "xingque_help_docs",
                    "bundle_version": (bundle.get("source") or {}).get("upstream_app_version"),
                    "provenance": bundle.get("source") or {},
                    "categories": [
                        {
                            "name": cat.get("name"),
                            "count": len(cat.get("entries") or []),
                            "keys": [e.get("key") for e in (cat.get("entries") or [])][:24],
                            "supports": ["read"],
                        }
                        for cat in bundle.get("categories") or []
                    ],
                }
            )
            continue
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
                "bundle_version": index.get("bundle_version"),
                "provenance": _knowledge_provenance(domain=name),
                "categories": categories,
            }
        )
    return {
        "source": "xingque_hover_docs",
        "bundle_version": index.get("bundle_version"),
        "provenance": {
            "source_domain": "xingque_hover_docs",
            "bundle_version": index.get("bundle_version"),
            "build_timestamp": index.get("build_timestamp"),
            "upstream_source_marker": index.get("upstream_source_marker", "xingque_hover_docs"),
        },
        "domains": result_domains,
    }


def read_knowledge_entry(payload: dict[str, Any]) -> dict[str, Any]:
    """按原值查；查不到、且类目 / 键里有繁体专用字时，折回简体**再查一次**（繁体输出模式下 AI 会把看到的繁体键原样送回）。

    只在原值失败后才折：知识库里本来就有繁体原名的键（上游古籍条目）照旧按原名命中，简体输入的行为逐字不变。
    """
    try:
        return _read_knowledge_entry(payload)
    except ToolValidationError as exc:
        if not str(exc.code or "").startswith("knowledge."):
            raise
        folded = {
            **payload,
            **{field: fold_to_simplified(str(payload[field])) for field in ("domain", "category", "key")
               if isinstance(payload.get(field), str) and looks_traditional(payload[field])},
        }
        if folded == payload:
            raise
        try:
            return _read_knowledge_entry(folded)
        except ToolValidationError:
            raise exc from None


def _read_knowledge_entry(payload: dict[str, Any]) -> dict[str, Any]:
    bundles = load_knowledge_bundles()
    domain = canonical_domain(payload.get("domain"))
    category = f"{payload.get('category') or ''}".strip()
    key = f"{payload.get('key') or ''}".strip()
    if bundles[domain].get("schema") == "horosa.knowledge.helpdoc.v1":
        return _read_helpdoc_entry(bundles[domain], domain=domain, category=category, key=key)
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
                "bundle_version": load_knowledge_index().get("bundle_version"),
                "provenance": _knowledge_provenance(domain=domain, category=category, key=aspect_key),
                "citation": f"Xingque hover knowledge · {domain}/{category}/{aspect_key}",
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
            "bundle_version": load_knowledge_index().get("bundle_version"),
            "provenance": _knowledge_provenance(domain=domain, category=category, key=normalized_key),
            "citation": f"Xingque hover knowledge · {domain}/{category}/{normalized_key}",
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
                "bundle_version": load_knowledge_index().get("bundle_version"),
                "provenance": _knowledge_provenance(domain=domain, category=category, key=normalized_key),
                "citation": f"Xingque hover knowledge · {domain}/{category}/{normalized_key}",
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
        "bundle_version": load_knowledge_index().get("bundle_version"),
        "provenance": _knowledge_provenance(domain=domain, category=category, key=normalized_key),
        "citation": f"Xingque hover knowledge · {domain}/{category}/{normalized_key}",
    }


def _read_helpdoc_entry(bundle: dict[str, Any], *, domain: str, category: str, key: str) -> dict[str, Any]:
    """手册域通用读取：category 缺省取首类（多数域只有「手册」一类）；key 精确或前缀匹配。

    返回体与 hover 域同形（rendered_text + provenance + citation），citation 逐条落到
    组件文件 + tab + 上游版本——「引教义必带出处」在这里闭环。
    """
    cats = bundle.get("categories") or []
    cat = next((c for c in cats if c.get("name") == category), None) if category else (cats[0] if cats else None)
    if cat is None:
        raise ToolValidationError(
            f"Unknown knowledge category: {domain}/{category}",
            code="knowledge.unknown_category",
            details={"domain": domain, "category": category, "available": [c.get("name") for c in cats]},
        )
    entries = cat.get("entries") or []
    if not key:
        raise ToolValidationError(
            f"knowledge_read({domain}) 需要 key（条目名）。",
            code="knowledge.helpdoc.key_required",
            details={"domain": domain, "category": cat.get("name"), "keys": [e.get("key") for e in entries]},
        )
    entry = next((e for e in entries if e.get("key") == key), None)
    if entry is None:  # 前缀/包含式兜底：手册 tab 名较长，允许「排盘」命中「排盘设置」
        loose = [e for e in entries if key in f"{e.get('key')}"]
        entry = loose[0] if len(loose) == 1 else None
    if entry is None:
        raise ToolValidationError(
            f"Unknown knowledge key: {domain}/{cat.get('name')}/{key}",
            code="knowledge.helpdoc.unknown_key",
            details={"domain": domain, "category": cat.get("name"), "key": key,
                     "available": [e.get("key") for e in entries]},
        )
    src = bundle.get("source") or {}
    entry_src = entry.get("source") or {}
    return {
        "domain": domain,
        "category": cat.get("name"),
        "key": entry.get("key"),
        "query_normalized": {"key": entry.get("key")},
        "title": f"{bundle.get('label')} · {entry.get('label') or entry.get('key')}",
        "rendered_text": entry.get("text", ""),
        "source": "xingque_help_docs",
        "bundle_version": src.get("upstream_app_version"),
        "provenance": {**src, **entry_src},
        "citation": (
            f"星阙操作手册 · {bundle.get('label')} · {entry.get('key')}"
            f"（{entry_src.get('file')} @ 星阙 {src.get('upstream_app_version')}）"
        ),
    }


# --- 全文检索：跨全部知识域；检索的文本就是 knowledge_read 返回的文本 ----------------------------

# 星座的通行异名。read 的键是英文、标签各家译法不同；搜索要让用户说哪个都能到。
_SIGN_VARIANTS = {
    "Aries": ("白羊", "牡羊"), "Virgo": ("处女", "室女"), "Libra": ("天秤", "天平"), "Sagittarius": ("射手", "人马"),
    "Capricorn": ("摩羯", "魔羯", "山羊"), "Aquarius": ("水瓶", "宝瓶"),
}
_NODE_NAMES = {"North Node": ("北交点",), "South Node": ("南交点",)}
_ASPECT_NAMES = {
    "0": ("合相", "合"), "60": ("六分相", "六合相"), "90": ("四分相", "刑相"), "120": ("三分相", "拱相", "三合相"),
    "180": ("对分相", "冲相", "对冲"),
}
_MANUAL_ALIASES = {"Suzhan": ("宿占",)}  # 上游页面叫「宿盘」，技法与工具都叫宿占
_CN_NUMERALS = ("一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二")
_MANUAL_HOME_KEYS = frozenset({"总览", "Overview", "Page"})
_SHEN_SUFFIX = re.compile(r"[子丑寅卯辰巳午未申酉戌亥]神$")
_PARENTHETICAL = re.compile(r"[（(].*?[）)]$")
_CJK_TEXT = re.compile(r"[㐀-鿿]")
# 查询里点名的领域：「六爻起卦」的「六爻」是在说去哪本手册找，别的手册提到「起卦」不该排到前面。
_DOMAIN_WORDS = {
    "八字": ("bazi", "bazi_pithy"), "紫微": ("ziwei",), "紫微斗数": ("ziwei",), "奇门": ("dunjia", "qimen"), "奇门遁甲": ("dunjia", "qimen"),
    "遁甲": ("dunjia", "qimen"), "六壬": ("liureng_manual", "liureng"), "大六壬": ("liureng_manual", "liureng"), "太乙": ("taiyi",),
    "六爻": ("guazhan",), "塔罗": ("tarot",), "印度": ("india",), "印度占星": ("india",), "合盘": ("relative",), "择日": ("zeri",),
    "节气": ("jieqi",), "三式": ("sanshi",), "玄史": ("xuanshi",), "演禽": ("yanqin",), "一掌经": ("yizhangjing",), "占星": ("astro_manual", "astro"),
}
_NAMED_DOMAIN_BOOST = 2.0
_THIN_RESULT = 3  # 比这还少又没有点名命中：多半是整串碰巧在哪儿连着出现过一次，补上切开后的结果
_TIER_SCORE = {3: 100.0, 2: 60.0, 1: 30.0, 0: 0.0}  # 全等 > 名字里含 > 标题里含 > 只在正文
_RELEVANCE_SPAN = 30.0  # 相关度压进 [0, 30)：档内按相关度排，永远越不过上一档


# 自备知识库的域 id 与叫法。字面量与 knowledge/user.py 的 USER_DOMAIN 相同（那边 import 本模块，反过来会成环；测试钉两处相等）。
USER_DOMAIN = "user"
_USER_DOMAIN_NAMES = ("自备知识库", "自备", "笔记", "我的笔记", "用户笔记", "notes", "my notes", "user notes")
_DOMAIN_KEY_NOISE = re.compile(r"[\s_\-·・/／()（）]+")


def _domain_key(name: Any) -> str:
    """域名比较用的键：全半角 / 繁简 / 大小写归一，再去掉空白与连接符（`Bazi-Pithy`、`bazi pithy`、`八字四柱·操作手册` 都认）。"""
    return _DOMAIN_KEY_NOISE.sub("", retrieval.normalize(f"{name or ''}"))


@lru_cache(maxsize=1)
def domain_names() -> dict[str, str]:
    """归一后的叫法 → 域 id。来源只有三处：域 id、手册自己的显示名（整名 / 「·」前半 / 去括号）、查询点名领域用的 `_DOMAIN_WORDS`。

    先登记的不被覆盖：「八字」是 `_DOMAIN_WORDS` 里排第一的 bazi，不是名字里也带「八字」的断语库。
    """
    bundles = load_knowledge_bundles()
    names: dict[str, str] = {}

    def add(name: str, domain: str) -> None:
        key = _domain_key(name)
        if key:
            names.setdefault(key, domain)

    for domain in sorted(bundles):
        add(domain, domain)
    for name in (USER_DOMAIN, *_USER_DOMAIN_NAMES):
        add(name, USER_DOMAIN)
    for word, targets in _DOMAIN_WORDS.items():
        add(word, targets[0])
    for domain in sorted(bundles):
        label = f"{bundles[domain].get('label') or ''}"
        head = label.rsplit("·", 1)[0].strip()
        for name in (label, head, re.sub(r"[（(].*?[）)]", "", head)):
            add(name, domain)
    return names


def domain_listing(*, with_user: bool = True) -> list[dict[str, str]]:
    """可用的域：[{domain, label}]。报错与 registry 用同一份。"""
    bundles = load_knowledge_bundles()
    listing = [{"domain": domain, "label": f"{bundles[domain].get('label') or ''}"} for domain in sorted(bundles)]
    if with_user:
        listing.append({"domain": USER_DOMAIN, "label": _USER_DOMAIN_NAMES[0]})
    return listing


def unknown_domain_error(name: Any, *, with_user: bool = True) -> ToolValidationError:
    text = f"{name or ''}".strip()
    listing = domain_listing(with_user=with_user)
    names = domain_names()
    near = difflib.get_close_matches(_domain_key(text), list(names), n=3, cutoff=0.6)
    suggestions = list(dict.fromkeys(names[key] for key in near if with_user or names[key] != USER_DOMAIN))
    hint_zh = f"是不是：{'、'.join(suggestions)}？" if suggestions else ""
    hint_en = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
    # 消息里只放显示名的前半：整名里有「 / 」，会和双语分隔符撞上（完整显示名在 details.valid_domains）。
    shown_zh = "、".join(f"{row['domain']}（{row['label'].rsplit('·', 1)[0].strip()}）" if row["label"] else row["domain"] for row in listing)
    return ToolValidationError(
        bilingual(
            f"没有这个知识域：{text}。{hint_zh}可用的域（id 或中文名都行，繁简、大小写不限）：{shown_zh}。",
            f"Unknown knowledge domain: {text}.{hint_en} Valid domains (an id or its Chinese display name, either script, any case): "
            f"{', '.join(row['domain'] for row in listing)}.",
        ),
        code="knowledge.unknown_domain",
        details={"domain": text, "valid_domains": listing, "suggestions": suggestions},
    )


def canonical_domain(name: Any, *, with_user: bool = False) -> str:
    """`domain` 参数 → 域 id。认 id、显示名、繁体、任意大小写；认不出抛一条带可用清单的双语错误（三处入口同一条）。

    `with_user`：自备知识库（user）在这个入口能不能用。内置语料自己的函数不认它。
    """
    domain = domain_names().get(_domain_key(name))
    if domain is None or (domain == USER_DOMAIN and not with_user):
        raise unknown_domain_error(name, with_user=with_user)
    return domain


def domain_also_named(name: Any) -> tuple[str, ...]:
    """这个叫法在 `_DOMAIN_WORDS` 里还指着哪些别的域（「八字」→ 过滤用 bazi，另有 bazi_pithy）：过滤只取一个域，其余要说出来。"""
    key = _domain_key(name)
    return next((targets[1:] for word, targets in _DOMAIN_WORDS.items() if _domain_key(word) == key), ())



@dataclass(frozen=True)
class SearchDoc:
    domain: str
    category: str
    key: str
    title: str
    body: str
    citation: str
    names: frozenset[str]  # 归一后的「这一条叫什么」：键、中文标签、别名
    fields: tuple[tuple[str, float], ...]  # (归一文本, 权重)

    @property
    def haystack(self) -> str:
        return "\n".join(text for text, _ in self.fields)

    def read(self) -> dict[str, str]:
        return {"domain": self.domain, "category": self.category, "key": self.key}


def _coordinates() -> Iterator[tuple[str, str, str]]:
    """全部 (domain, category, key)：四种 bundle 形状都在这一处。"""
    bundles = load_knowledge_bundles()
    for domain in sorted(bundles):
        bundle = bundles[domain]
        if bundle.get("schema") == "horosa.knowledge.helpdoc.v1":
            for cat in bundle.get("categories") or []:
                yield from ((domain, f"{cat.get('name')}", f"{entry.get('key')}") for entry in cat.get("entries") or [])
        elif domain == "liureng":
            yield from ((domain, "shen", key) for key in bundle.get("shen_entries") or {})
            yield from ((domain, "house", key) for key in bundle.get("jiang_info") or {})
        else:
            for category, entries in (bundle.get("categories") or {}).items():
                if isinstance(entries, dict):
                    yield from ((domain, category, f"{key}") for key in entries)


def _helpdoc_label(bundle: dict[str, Any], category: str, key: str) -> str | None:
    for cat in bundle.get("categories") or []:
        if cat.get("name") == category:
            return next((entry.get("label") for entry in cat.get("entries") or [] if entry.get("key") == key), None)
    return None


def _entry_names(domain: str, category: str, key: str, title: str) -> set[str]:
    """这一条的所有叫法，用的是 knowledge_read 认的同一批表。检索此前完全不看这些表：read 查得到的 40 个星体标签，搜索有 18 个搜不到。"""
    bundles = load_knowledge_bundles()
    bundle = bundles[domain]
    names = {key, title}
    if bundle.get("schema") == "horosa.knowledge.helpdoc.v1":
        label = _helpdoc_label(bundle, category, key)
        names |= {label or "", *_MANUAL_ALIASES.get(key, ())}
        if key in _MANUAL_HOME_KEYS:  # 「奇门遁甲」这种查询，到这本手册的总览
            names.add(f"{bundle.get('label') or ''}".split(" · ")[0])
    elif domain == "astro":
        labels = {*(value for value in (ASTRO_LABELS.get(key), (bundle.get("labels") or {}).get(key)) if value)}
        names |= labels | {_PARENTHETICAL.sub("", label) for label in labels} | set(_NODE_NAMES.get(key, ()))
        if category == "sign":
            spoken = labels | set(_SIGN_VARIANTS.get(key, ()))
            names |= spoken | {f"{name}座" for name in spoken}
        elif category == "aspect":
            names |= set(_ASPECT_NAMES.get(key, ())) | {f"{key}度", f"{key}°"}
        elif category == "house" and key.removeprefix("House").isdigit():
            number = int(key.removeprefix("House"))
            names |= {f"第{_CN_NUMERALS[number - 1]}宫", f"第{number}宫", f"{_CN_NUMERALS[number - 1]}宫"}
    elif domain == "qimen":
        names |= {alias for table in (QIMEN_GOD_ALIASES, QIMEN_STAR_ALIASES) for alias, target in table.items()
                  if target == key and len(alias) > 1}
    elif domain == "liureng":
        names.add(_SHEN_SUFFIX.sub("", title))
        names |= {alias for alias, target in (bundle.get("jiang_aliases") or {}).items() if target == key}
    return {retrieval.normalize(name) for name in names if name}


def _search_doc(domain: str, category: str, key: str) -> SearchDoc:
    """一条检索文档。正文取 knowledge_read 的 rendered_text：搜到的就是读到的，每个坐标都能读回由这里保证。

    此前递归收集条目里所有字符串，奇门条目的 `text` / `blank` 块类型标记占了 31% 的「正文」，摘要里全是这些词。
    """
    read = read_knowledge_entry({"domain": domain, "category": category, "key": key})
    title, body = f"{read.get('title') or key}", f"{read.get('rendered_text') or ''}"
    named_category = category if _CJK_TEXT.search(category) and category != "手册" else ""
    names = _entry_names(domain, category, key, title)
    fields = ((retrieval.normalize(title) + "\n" + "\n".join(sorted(names)), retrieval.FIELD_WEIGHTS["title"]),
              (retrieval.normalize(named_category), retrieval.FIELD_WEIGHTS["heading"]),
              (retrieval.normalize(body), retrieval.FIELD_WEIGHTS["body"]))
    return SearchDoc(domain, category, key, title, body, f"{read.get('citation') or ''}", frozenset(names), fields)


@lru_cache(maxsize=1)
def search_docs() -> tuple[SearchDoc, ...]:
    """检索语料。bundle 是只读打包数据，进程内建一次。"""
    return tuple(_search_doc(*coordinate) for coordinate in _coordinates())


def _tier(doc: SearchDoc, exact: str, tokens: tuple[str, ...]) -> int:
    if exact in doc.names:
        return 3
    if tokens and len(exact) > 1 and any(retrieval.term_count(name, tokens) for name in doc.names):
        return 2
    return 1 if tokens and retrieval.term_count(doc.fields[0][0], tokens) else 0


def _rank(corpus: list[SearchDoc], query: str, df: dict[tuple[str, ...], int]) -> list[tuple[float, bool, SearchDoc]]:
    """(分数, 是否全等, 文档)，分数降序。分数 = 档位底分 + 相关度：同一档内按相关度排，不会再一片同分。"""
    parsed = retrieval.parse_query(query)
    exact = retrieval.normalize(query).strip()
    tokens = retrieval.TOKEN.findall(exact)
    whole = tuple(tokens) if " " not in exact else ()
    n_docs = max(len(corpus), 1)
    avg_len = sum(len(doc.haystack) for doc in corpus) / n_docs if corpus else 1.0
    for term in parsed.scored:
        if term not in df:
            df[term] = sum(1 for doc in corpus if retrieval.term_count(doc.haystack, term))
    ranked: list[tuple[float, bool, SearchDoc]] = []
    named = {term: _DOMAIN_WORDS["".join(term)] for term in parsed.scored if "".join(term) in _DOMAIN_WORDS}
    for doc in corpus:
        by_term = {
            term: retrieval.bm25(sum(weight * retrieval.term_count(text, term) for text, weight in doc.fields),
                                 df[term], n_docs, len(doc.haystack), avg_len)
            for term in parsed.scored}
        relevance = sum(by_term.values())
        topic = sum(score for term, score in by_term.items() if term not in named)
        if topic and any(doc.domain in domains for domains in named.values()):
            relevance *= _NAMED_DOMAIN_BOOST
        tier = _tier(doc, exact, whole)
        if tier == 0 and relevance <= 0:
            continue
        ranked.append((round(_TIER_SCORE[tier] + _RELEVANCE_SPAN * relevance / (1 + relevance), 4), tier == 3, doc))
    ranked.sort(key=lambda row: (-row[0], row[2].domain, row[2].category, row[2].key))
    return ranked


def search_knowledge(payload: dict[str, Any], *, depth: int | None = None) -> dict[str, Any]:
    """`knowledge_read` 的 query 模式：跨全部知识域全文检索。

    排序：全等（键 / 中文名 / 别名）> 名字里含 > 标题里含 > 只在正文；档内按 BM25，同分按 (domain, category, key)，
    同一 query 永远同一结果。整句零命中时改写一次（去问句外壳、切开连写的词），结果带 `expanded_query`。
    `depth`：内部翻页用，一次取够这么多条。
    """
    query = f"{payload.get('query') or ''}".strip()
    if not query:
        raise ToolValidationError(
            bilingual("检索词是空的：给 query 一个词。", "knowledge search requires a non-empty `query`"),
            code="knowledge.search.empty_query",
            details={},
        )
    domain_filter = canonical_domain(payload.get("domain")) if f"{payload.get('domain') or ''}".strip() else None
    try:
        limit = int(payload.get("limit") or 8)
    except (TypeError, ValueError):
        limit = 8
    limit = max(1, min(limit, 20))
    corpus = [doc for doc in search_docs() if not domain_filter or doc.domain == domain_filter]
    df: dict[tuple[str, ...], int] = {}
    ranked = _rank(corpus, query, df)
    expanded = None
    if len(ranked) < _THIN_RESULT and " " not in query and not any(row[1] for row in ranked):
        whole_query = retrieval.normalize(query)
        expanded = retrieval.expand_query(
            query, retrieval.cached(lambda term: 0 if term == whole_query else sum(1 for doc in corpus if term in doc.haystack)),
            len(corpus))
        if expanded:
            found = {id(row[2]) for row in ranked}  # 原查询的命中留在前面：改写只补不换
            ranked = [*ranked, *(row for row in _rank(corpus, expanded, df) if id(row[2]) not in found)]
    terms = [term for term in retrieval.parse_query(expanded or query).terms if term]
    matches = [
        {
            "domain": doc.domain,
            "category": doc.category,
            "key": doc.key,
            "title": doc.title,
            "score": score,
            "snippet": retrieval.snippet(doc.body, terms),
            "citation": doc.citation,
            "read": doc.read(),
            **({"exact": True} if exact else {}),
        }
        for score, exact, doc in ranked[: depth or limit]
    ]
    result = {
        "mode": "search",
        "query": query,
        "domain": domain_filter,
        "limit": limit,
        "total_scanned": len(corpus),
        "total_matched": len(ranked),
        "matches": matches,
        "bundle_version": load_knowledge_index().get("bundle_version"),
    }
    if expanded:
        result["expanded_query"] = expanded
    if looks_traditional(query):
        result["query_folded"] = fold_to_simplified(query)
    return result
