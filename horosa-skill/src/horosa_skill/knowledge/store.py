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
        "bundle_version": load_knowledge_index().get("bundle_version"),
        "provenance": _knowledge_provenance(domain="liureng", category="house", key=normalized_name),
        "citation": f"Xingque hover knowledge · liureng/house/{normalized_name}",
    }


def build_knowledge_registry(domain: str | None = None) -> dict[str, Any]:
    bundles = load_knowledge_bundles()
    index = load_knowledge_index()
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
        "title": f"{bundle.get('label')} · {entry.get('key')}",
        "rendered_text": entry.get("text", ""),
        "source": "xingque_help_docs",
        "bundle_version": src.get("upstream_app_version"),
        "provenance": {**src, **entry_src},
        "citation": (
            f"星阙操作手册 · {bundle.get('label')} · {entry.get('key')}"
            f"（{entry_src.get('file')} @ 星阙 {src.get('upstream_app_version')}）"
        ),
    }


# --- 全文检索（v0.30.0）：query 模式 —— 跨 24 域一把搜，命中带出处、可直接回读 -----------------


def _flat_strings(value: Any) -> list[str]:
    """递归收集条目里所有字符串值（tips/blocks/verse… 各域形状不一，搜索只关心文本本体）。"""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _flat_strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _flat_strings(v)]
    return []


def _iter_search_entries():
    """产出 (domain, category, key, title, body_text, citation)——覆盖全部四种 bundle 形状，
    且 (domain, category, key) 恒可直接喂回 `knowledge_read` 精读。"""
    bundles = load_knowledge_bundles()
    for domain in sorted(bundles):
        bundle = bundles[domain]
        if bundle.get("schema") == "horosa.knowledge.helpdoc.v1":
            src = bundle.get("source") or {}
            label = bundle.get("label")
            for cat in bundle.get("categories") or []:
                for entry in cat.get("entries") or []:
                    key = f"{entry.get('key')}"
                    citation = (
                        f"星阙操作手册 · {label} · {key}"
                        f"（{src.get('file')} @ 星阙 {src.get('upstream_app_version')}）"
                    )
                    yield domain, f"{cat.get('name')}", key, f"{label} · {key}", f"{entry.get('text') or ''}", citation
            continue
        if domain == "liureng":
            for key, entry in (bundle.get("shen_entries") or {}).items():
                yield (
                    domain, "shen", key, entry.get("title", key),
                    "\n".join(_flat_strings(entry)),
                    f"Xingque hover knowledge · liureng/shen/{key}",
                )
            notes = bundle.get("jiang_branch_note") or {}
            for key, entry in (bundle.get("jiang_info") or {}).items():
                body = "\n".join(_flat_strings(entry) + _flat_strings(notes.get(key)))
                yield (
                    domain, "house", key, f"十二天将 · {key}", body,
                    f"Xingque hover knowledge · liureng/house/{key}",
                )
            continue
        for category, entries in (bundle.get("categories") or {}).items():
            if not isinstance(entries, dict):
                continue
            for key, entry in entries.items():
                title = entry.get("title", key) if isinstance(entry, dict) else key
                yield (
                    domain, category, f"{key}", f"{title}",
                    "\n".join(_flat_strings(entry)),
                    f"Xingque hover knowledge · {domain}/{category}/{key}",
                )


def _search_snippet(body: str, query: str, width: int = 45) -> str:
    pos = body.find(query)
    if pos < 0:
        return " ".join(body[: width * 2].split())
    start, end = max(0, pos - width), pos + len(query) + width
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(body) else ""
    return prefix + " ".join(body[start:end].split()) + suffix


def search_knowledge(payload: dict[str, Any]) -> dict[str, Any]:
    """`knowledge_read` 的 query 模式：跨全部知识域全文检索。

    排序确定性：得分（key 全等 100 > key 含 40 > 标题含 30 > 正文出现次数封顶 10）降序，
    同分按 (domain, category, key) 字典序——同一 query 永远同一结果，评测可 golden。
    """
    query = f"{payload.get('query') or ''}".strip()
    if not query:
        raise ToolValidationError(
            "knowledge search requires a non-empty `query`",
            code="knowledge.search.empty_query",
            details={},
        )
    domain_filter = f"{payload.get('domain') or ''}".strip() or None
    if domain_filter and domain_filter not in load_knowledge_bundles():
        raise ToolValidationError(
            f"Unknown knowledge domain: {domain_filter}",
            code="knowledge.unknown_domain",
            details={"domain": domain_filter},
        )
    try:
        limit = int(payload.get("limit") or 8)
    except (TypeError, ValueError):
        limit = 8
    limit = max(1, min(limit, 20))

    scored: list[tuple[int, str, str, str, dict[str, Any]]] = []
    scanned = 0
    for domain, category, key, title, body, citation in _iter_search_entries():
        if domain_filter and domain != domain_filter:
            continue
        scanned += 1
        score = 0
        if key == query:
            score += 100
        elif query in key:
            score += 40
        if query in title:
            score += 30
        occurrences = body.count(query)
        score += min(occurrences, 10)
        if score <= 0:
            continue
        scored.append((
            score, domain, category, key,
            {
                "domain": domain,
                "category": category,
                "key": key,
                "title": title,
                "score": score,
                "snippet": _search_snippet(body, query),
                "citation": citation,
            },
        ))
    scored.sort(key=lambda item: (-item[0], item[1], item[2], item[3]))
    return {
        "mode": "search",
        "query": query,
        "domain": domain_filter,
        "limit": limit,
        "total_scanned": scanned,
        "total_matched": len(scored),
        "matches": [row[4] for row in scored[:limit]],
        "bundle_version": load_knowledge_index().get("bundle_version"),
    }
