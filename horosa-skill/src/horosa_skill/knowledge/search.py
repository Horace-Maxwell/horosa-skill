"""跨语料检索：内置知识 + 自备知识库。融合、精确命中置顶、翻页都在这里，service 层只转发。

两边分数不同尺度（内置是档位 + BM25，自备是 BM25 / 向量融合），按名次做倒数排名融合，不拿分数直接比。
"""
from __future__ import annotations

import re
import sqlite3
from typing import Any

from horosa_skill.errors import ToolValidationError, bilingual
from horosa_skill.knowledge import retrieval, store
from horosa_skill.knowledge import user as user_knowledge


def _match_key(match: dict[str, Any]) -> tuple[str, str, str, str]:
    return str(match.get("domain")), str(match.get("category")), str(match.get("key")), str(match.get("lines") or "")


def _user_side(settings: Any, query: str, depth: int) -> dict[str, Any]:
    """自备知识库这一路出任何问题都不能带累内置结果：用户问的是知识，不是这个索引。"""
    try:
        return user_knowledge.search_user(settings, query, limit=depth)
    except (sqlite3.Error, OSError, ValueError, RuntimeError) as exc:
        return {"matches": [], "total_matched": 0, "engine": "unavailable",
                "warnings": [f"自备知识库这次没搜成（{type(exc).__name__}: {exc}），结果只来自内置知识。"]}


LIMIT_DEFAULT, LIMIT_MAX = 8, 20


def _whole_number(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and re.fullmatch(r"\s*[+-]?\d+\s*", value):
        return int(value)
    return None


def page_arguments(payload: dict[str, Any]) -> tuple[int, int, list[str]]:
    """(limit, offset, 说明)。越界 / 不是整数的值照旧落到能用的数上，但要说出来：此前 limit=500 悄悄变 20、offset=-3 悄悄变 0，
    调用方以为拿到了自己要的那一页。"""
    notes: list[str] = []
    limit, offset = LIMIT_DEFAULT, 0
    raw_limit, raw_offset = payload.get("limit"), payload.get("offset")
    if raw_limit is not None:
        number = _whole_number(raw_limit)
        if number is None or number < 1:
            notes.append(bilingual(f"limit={raw_limit!r} 不是 1–{LIMIT_MAX} 的整数，按默认 {LIMIT_DEFAULT} 条返回。",
                                   f"limit={raw_limit!r} is not a whole number in 1–{LIMIT_MAX}; the default {LIMIT_DEFAULT} was used."))
        elif number > LIMIT_MAX:
            limit = LIMIT_MAX
            notes.append(bilingual(f"limit={number} 超过上限，按 {LIMIT_MAX} 条返回；更多结果用 next_offset 翻页。",
                                   f"limit={number} is above the maximum; {LIMIT_MAX} were returned. Page on with next_offset."))
        else:
            limit = number
    if raw_offset is not None:
        number = _whole_number(raw_offset)
        if number is None or number < 0:
            notes.append(bilingual(f"offset={raw_offset!r} 不是 ≥ 0 的整数，从第一条开始返回。",
                                   f"offset={raw_offset!r} is not a whole number ≥ 0; results start from the first match."))
        else:
            offset = number
    return limit, offset, notes


def resolve_domain(name: Any) -> tuple[str, list[str]]:
    """`domain` 参数 → (域 id, 说明)。空串 = 不过滤。认显示名 / 繁体 / 任意大小写；一个叫法指着几个域时只按第一个过滤，并说出其余。"""
    text = f"{name or ''}".strip()
    if not text:
        return "", []
    domain = store.canonical_domain(text, with_user=True)
    others = store.domain_also_named(text)
    notes = [bilingual(f"domain「{text}」按 {domain} 过滤；这个名字还指 {'、'.join(others)}，要查那边请用它的 id。",
                       f"domain \"{text}\" was read as {domain}; the same name also covers {', '.join(others)}: pass that id to search there.")
             ] if others else []
    return domain, notes


def search_all(settings: Any, payload: dict[str, Any]) -> dict[str, Any]:
    query = f"{payload.get('query') or ''}".strip()
    if not query:
        raise ToolValidationError(bilingual("检索词是空的：给 query 一个词。", "knowledge search requires a non-empty `query`"),
                                  code="knowledge.search.empty_query", details={})
    domain, notes = resolve_domain(payload.get("domain"))
    limit, offset, page_notes = page_arguments(payload)
    notes = [*notes, *page_notes]
    result = _search(settings, {**payload, "query": query, "domain": domain}, query, domain, limit, offset)
    if notes:
        result["warnings"] = [*notes, *result.get("warnings", [])]
    return result


def _search(settings: Any, payload: dict[str, Any], query: str, domain: str, limit: int, offset: int) -> dict[str, Any]:
    if domain == user_knowledge.USER_DOMAIN:
        mine = user_knowledge.search_user(settings, query, limit=limit, offset=offset)
        return {"mode": "search", "query": query, "domain": domain, "limit": limit, "offset": offset,
                "total_matched": mine["total_matched"], "next_offset": mine["next_offset"], "engine": mine["engine"],
                "matches": mine["matches"],
                **{key: mine[key] for key in ("expanded_query", "warnings") if key in mine}}
    # 每边取到 offset + limit 条就够：两边的条目互不相同，融合后的前 N 条必在各自的前 N 条里。
    depth = offset + limit
    builtin = store.search_knowledge({**payload, "query": query, "limit": limit}, depth=depth)
    mine = _user_side(settings, query, depth) if not domain else {"matches": [], "total_matched": 0}
    # 同名同档靠 RRF 比不出来：精确命中（键 / 中文名 / 笔记标题全等）是用户在点名要这一条，排在融合结果前面。
    fused = [match for match, _ in retrieval.rrf([builtin["matches"], mine["matches"]], key=_match_key)]
    ordered = sorted(fused, key=lambda match: not match.get("exact"))
    total = int(builtin["total_matched"]) + int(mine["total_matched"])
    page = ordered[offset : offset + limit]
    next_offset = offset + len(page)
    result = {
        **{key: value for key, value in builtin.items() if key not in ("matches", "total_matched", "limit")},
        "mode": "search", "query": query, "limit": limit, "offset": offset, "total_matched": total,
        "next_offset": next_offset if next_offset < total else None, "matches": page,
    }
    if "engine" in mine:
        result["engine"] = mine["engine"]
    expanded = builtin.get("expanded_query") or mine.get("expanded_query")
    if expanded:
        result["expanded_query"] = expanded
    if mine.get("warnings"):
        result["warnings"] = mine["warnings"]
    return result
