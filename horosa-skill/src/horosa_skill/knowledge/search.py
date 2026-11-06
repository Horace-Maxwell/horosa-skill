"""跨语料检索：内置知识 + 自备知识库。融合、精确命中置顶、翻页都在这里，service 层只转发。

两边分数不同尺度（内置是档位 + BM25，自备是 BM25 / 向量融合），按名次做倒数排名融合，不拿分数直接比。
"""
from __future__ import annotations

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


def search_all(settings: Any, payload: dict[str, Any]) -> dict[str, Any]:
    query = f"{payload.get('query') or ''}".strip()
    domain = f"{payload.get('domain') or ''}".strip()
    try:
        limit = max(1, min(int(payload.get("limit") or 8), 20))
        offset = max(0, int(payload.get("offset") or 0))
    except (TypeError, ValueError):
        limit, offset = 8, 0
    if not query:
        raise ToolValidationError(bilingual("检索词是空的：给 query 一个词。", "knowledge search requires a non-empty `query`"),
                                  code="knowledge.search.empty_query", details={})
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
