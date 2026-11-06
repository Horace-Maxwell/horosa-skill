"""内置知识检索的离线评测：hit@1 / hit@5 / MRR，按查询类别分列；再加一项全库自检索。

    uv run python scripts/eval_knowledge_search.py                 # dev 集 + 自检索（汇总）
    uv run python scripts/eval_knowledge_search.py --misses        # dev 集逐条失败
    uv run python scripts/eval_knowledge_search.py --set heldout   # 只报数，不许拿它调

为什么有两种：手写的 dev 集是看着失败写的，用来调之后分数必然偏高；heldout 在改检索之前写好，写的时候没看过结果；
自检索不靠人挑，语料里每一条都用自己的名字和问句模板去搜。下限在 tests/test_knowledge_eval.py。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from horosa_skill.knowledge import store

EVAL_FILE = Path(__file__).resolve().parents[1] / "contracts" / "knowledge_eval.json"
QUESTION_TEMPLATES = ("{}", "{}是什么", "什么是{}", "{}怎么看")
_CJK = re.compile(r"[一-鿿]")


def _hit(match: dict[str, Any], want: list[list[Any]]) -> bool:
    for domain, key in want:
        if match.get("domain") != domain:
            continue
        if key is None or match.get("key") == key:
            return True
        if isinstance(key, str) and key.startswith("@") and match.get("category") == key[1:]:
            return True
    return False


def rank_of(query: str, want: list[list[Any]]) -> int | None:
    matches = store.search_knowledge({"query": query, "limit": 20})["matches"]
    return next((rank for rank, match in enumerate(matches, 1) if _hit(match, want)), None)


def summarize(ranks: list[int | None]) -> dict[str, float]:
    n = max(len(ranks), 1)
    return {"n": len(ranks), "hit1": round(sum(r == 1 for r in ranks) / n, 3),
            "hit5": round(sum(bool(r and r <= 5) for r in ranks) / n, 3),
            "mrr": round(sum(1 / r for r in ranks if r) / n, 3)}


def evaluate_set(name: str) -> dict[str, Any]:
    cases = json.loads(EVAL_FILE.read_text(encoding="utf-8"))["sets"][name]
    per: dict[str, list[tuple[str, int | None]]] = defaultdict(list)
    for case in cases:
        per[case["class"]].append((case["q"], rank_of(case["q"], case["want"])))
    return {
        "overall": summarize([r for rows in per.values() for _, r in rows]),
        "classes": {cls: summarize([r for _, r in rows]) for cls, rows in per.items()},
        "misses": {cls: [q for q, r in rows if not (r and r <= 5)] for cls, rows in per.items()},
    }


def self_names() -> list[tuple[str, str, str]]:
    """(domain, key, 显示名)：有中文名的条目；断语库的「标题」是一句话不是名字，不算。"""
    names = []
    labels = store.load_knowledge_bundles()["astro"].get("labels") or {}
    for doc in store.search_docs():
        if doc.domain == "bazi_pithy":
            continue
        name = doc.title.rsplit(" · ", 1)[-1] if " · " in doc.title else doc.title
        name = labels.get(doc.key, name) if doc.domain == "astro" else name
        if _CJK.search(name):
            names.append((doc.domain, doc.key, name))
    return names


def evaluate_self() -> dict[str, Any]:
    """全库自检索：每一条用自己的名字（hit@1 才算找到）和问句模板（hit@5）。"""
    out: dict[str, Any] = {}
    names = self_names()
    for template in QUESTION_TEMPLATES:
        ranks = [rank_of(template.format(name), [[domain, key]]) for domain, key, name in names]
        out[template.format("<名>")] = summarize(ranks)
    return out


def evaluate_self_unique() -> float:
    """名字全库唯一的条目 hit@1。「总览」这种 27 本手册共用的名字本来就没有唯一答案，算进去只会拉低分数、盖住真问题。"""
    names = self_names()
    counts: dict[str, int] = defaultdict(int)
    for _domain, _key, name in names:
        counts[name] += 1
    unique = [(domain, key, name) for domain, key, name in names if counts[name] == 1]
    return summarize([rank_of(name, [[domain, key]]) for domain, key, name in unique])["hit1"]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set", default="dev", choices=("dev", "heldout"))
    parser.add_argument("--misses", action="store_true", help="dev only: list the queries that missed the top 5")
    args = parser.parse_args()
    result = evaluate_set(args.set)
    misses = result.pop("misses")
    print(json.dumps({"set": args.set, **result}, ensure_ascii=False))
    if args.set == "dev":
        print(json.dumps({"self": evaluate_self(), "self_unique_hit1": evaluate_self_unique()}, ensure_ascii=False))
        if args.misses:
            print(json.dumps(misses, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
