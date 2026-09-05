#!/usr/bin/env python
"""收割上游八字断语库 `bazipithy.json`（Java 侧 21 类口诀/断语）→ 知识包 `knowledge/data/helpdocs/bazi_pithy.json`。

上游 `astrostudy/helper/bazipithy.json` 是桌面端「八字断语」页（CommToolsMain → BaziPithy）的数据，经
`/common/bazipithy` 原样下发：三字诀/四字诀/纳音断运/从格/格局/清浊/子息/婚姻/流年…共 21 类。它是 AI 解读八字
时最缺的"口诀层"，且**零运行时依赖**（纯静态 JSON）——按 helpdoc.v1 入知识库，`knowledge_read`/`knowledge_search`
零改动可查（v0.36.0 C2 tier 1）。

纪律与 gen_knowledge_packs.py 相同：读上游 **HEAD blob**（`git show HEAD:<path>`）不读工作区；逐条带出处
（file + category + 上游版本/commit）；`generated_at` 取上游 commit 时间 → 同 commit 重跑逐字节幂等；不改写正文。
条目粒度 = 一条口诀：dict 类目按子键（如 三字诀/甲），list 类目按行序号（如 格局/01）。

用法：HOROSA_SOURCE_ROOT=/path/to/Horosa-Public uv run python scripts/gen_bazi_pithy_pack.py [--check]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "src" / "horosa_skill" / "knowledge" / "data" / "helpdocs" / "bazi_pithy.json"
UPSTREAM_REL = "Horosa-Web/astrostudysrv/astrostudy/src/main/java/spacex/astrostudy/helper/bazipithy.json"
DOMAIN = "bazi_pithy"
LABEL = "八字断语库 · 口诀 21 类"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True).stdout


def build(upstream: Path) -> dict:
    raw = json.loads(_git(upstream, "show", f"HEAD:{UPSTREAM_REL}"))
    sha = _git(upstream, "rev-parse", "HEAD").strip()[:12]
    committed_at = _git(upstream, "log", "-1", "--format=%cI", "--", UPSTREAM_REL).strip()
    app_version = ""
    manifest = upstream / "Horosa_Desktop_Installer/package.json"
    if manifest.is_file():
        try:
            app_version = str(json.loads(manifest.read_text(encoding="utf-8")).get("version", ""))
        except (json.JSONDecodeError, OSError):
            app_version = ""
    categories = []
    for name, body in raw.items():
        entries = []
        if isinstance(body, dict):
            for key, value in body.items():
                text = "\n".join(f"- {line}" for line in value) if isinstance(value, list) else f"{value}"
                entries.append({"key": f"{key}", "text": text.strip(), "source": {"file": UPSTREAM_REL, "tab": name, "category": name, "key": f"{key}"}})
        elif isinstance(body, list):
            for index, line in enumerate(body, start=1):
                entries.append({"key": f"{index:02d}", "text": f"{line}".strip(), "source": {"file": UPSTREAM_REL, "tab": name, "category": name, "key": f"{index:02d}"}})
        else:
            entries.append({"key": "全文", "text": f"{body}".strip(), "source": {"file": UPSTREAM_REL, "tab": name, "category": name, "key": "全文"}})
        categories.append({"name": name, "entries": entries})
    return {
        "schema": "horosa.knowledge.helpdoc.v1",
        "domain": DOMAIN,
        "label": LABEL,
        "source": {
            "file": UPSTREAM_REL,
            "upstream_source_marker": "xingque_bazi_pithy",
            "upstream_app_version": app_version,
            "upstream_git_sha": sha,
        },
        "generated_at": committed_at,
        "categories": categories,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="只比对，不写文件（上游 HEAD 变了即红）")
    args = ap.parse_args()
    root = os.environ.get("HOROSA_SOURCE_ROOT")
    if not root or not Path(root).is_dir():
        print("gen-bazi-pithy-pack: set HOROSA_SOURCE_ROOT to the Horosa-Public checkout", file=sys.stderr)
        return 2
    payload = build(Path(root))
    rendered = json.dumps(payload, ensure_ascii=False, indent=1) + "\n"
    total = sum(len(c["entries"]) for c in payload["categories"])
    if args.check:
        if not OUT.is_file() or OUT.read_text(encoding="utf-8") != rendered:
            print(f"gen-bazi-pithy-pack: {OUT.name} is stale vs upstream HEAD — rerun without --check", file=sys.stderr)
            return 1
        print(f"gen-bazi-pithy-pack: up to date ({len(payload['categories'])} categories, {total} entries)")
        return 0
    OUT.write_text(rendered, encoding="utf-8")
    print(f"gen-bazi-pithy-pack: wrote {OUT.relative_to(REPO)} ({len(payload['categories'])} categories, {total} entries, upstream {payload['source']['upstream_git_sha']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
