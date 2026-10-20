"""本地数据 runner（AstrodataRunners）：名人库（SQLite）检索与玄史。"""
from __future__ import annotations

import gzip
import os
import shutil
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from horosa_skill.errors import ToolValidationError
from horosa_skill.service._common import _REPO_ROOT, _render_snapshot_text
from horosa_skill.service._context import _degrade
from horosa_skill.service.text.divination import _build_xuanshi_snapshot_text


class AstrodataRunners:
    # ── 名人星盘数据库（离线只读检索）────────────────────────────────────────────
    _ASTRODATA_RELATIVE = Path("Horosa-Web/astrostudyui/dist-file/astrodata/astrodata-aa.sqlite.gz")

    def _astrodata_db_path(self) -> Path | None:
        # 定位序列：显式 env → 已安装 runtime → 仓内 vendored 源快照（开发/live 测试）。
        env_path = os.environ.get("HOROSA_ASTRODATA_DB")
        candidates: list[Path] = []
        if env_path:
            candidates.append(Path(env_path).expanduser())
        current_dir = getattr(self.runtime_manager, "current_dir", None)  # stub managers in offline tests have none
        if current_dir:
            candidates.append(Path(current_dir) / self._ASTRODATA_RELATIVE)
        # 仓根 vendor/runtime-source（源码树里随 sync 脚本落地的上游运行时源码）。
        candidates.append(_REPO_ROOT / "vendor" / "runtime-source" / self._ASTRODATA_RELATIVE)
        for cand in candidates:
            if cand.is_file():
                return cand
        return None

    def _astrodata_connect(self) -> sqlite3.Connection | None:
        source = self._astrodata_db_path()
        if source is None:
            return None
        db_path = source
        if source.suffix == ".gz":
            cache_dir = Path(self.settings.runtime_root) / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            cached = cache_dir / "astrodata-aa.sqlite"
            stamp = cache_dir / "astrodata-aa.sqlite.src"
            src_sig = f"{source}|{source.stat().st_size}|{int(source.stat().st_mtime)}"
            stamp_ok = stamp.is_file() and stamp.read_text(encoding="utf-8").strip() == src_sig
            if not cached.is_file() or not stamp_ok:
                # 原子 + 流式解压：写唯一临时文件（进程/线程隔离，避免并发交错写撕裂 122MB 库），
                # copyfileobj 分块拷贝（不 fin.read() 整库进内存），成功后 os.replace 原子落位，
                # 最后才写 stamp —— 中断/并发都不会留下被当成有效的截断库。
                tmp = cache_dir / f".astrodata-aa.sqlite.{os.getpid()}.{uuid.uuid4().hex}.tmp"
                try:
                    with gzip.open(source, "rb") as fin, open(tmp, "wb") as fout:
                        shutil.copyfileobj(fin, fout, length=1024 * 1024)
                    os.replace(tmp, cached)
                    stamp.write_text(src_sig, encoding="utf-8")
                finally:
                    if tmp.exists():
                        tmp.unlink(missing_ok=True)
            db_path = cached
        # as_uri() 正确百分号编码路径（含空格/%/#/Windows 反斜杠+盘符），勿裸 f-string 拼接。
        con = sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        return con

    @staticmethod
    def _astrodata_row_get(row: sqlite3.Row, key: str, default: Any = None) -> Any:
        # sqlite3.Row 无 .get；对缺列（老库 schema）安全取值，避免裸 row[key] 抛 IndexError。
        try:
            return row[key]
        except (IndexError, KeyError):
            return default

    @classmethod
    def _astrodata_person_brief(cls, row: sqlite3.Row) -> dict[str, Any]:
        # v3.3.2 中文化：优先中文列（name_zh/pos_zh/born_zh），缺则回退英文，与上游前端 nm/ps 同口径。
        g = cls._astrodata_row_get
        name_zh = g(row, "name_zh")
        pos_zh = g(row, "pos_zh")
        born_zh = g(row, "born_zh")
        return {
            "title": row["title"],
            "name": g(row, "name"),
            "nameZh": name_zh or None,
            "nameDisplay": name_zh or g(row, "name"),
            "born": g(row, "born_display"),
            "bornDisplay": born_zh or g(row, "born_display"),
            "rodden": g(row, "rodden"),
            "sun": g(row, "sun"),
            "moon": g(row, "moon"),
            "asc": g(row, "asc"),
            "pos": g(row, "pos"),
            "posDisplay": pos_zh or g(row, "pos"),
            "hasTime": bool(g(row, "has_time", 0)),
        }

    @classmethod
    def _astrodata_has_column(cls, con: sqlite3.Connection, table: str, column: str) -> bool:
        try:
            return any(r[1] == column for r in con.execute(f"PRAGMA table_info({table})"))
        except sqlite3.Error:
            return False

    # 玄史 action → 端点全路径（存字面量：端点登记守卫按字面调用点核对）与该端点**真读**的参数名。
    # 🔴 sync311 F13：参数名逐端点对齐 webxuanshisrv.py 的 `_str/_int/_bool(d, "<键>")`——此前 figure/technique/
    # term/dynasty/story 发 `id` 而后端只读 `slug`（恒 null）、term_profile 要 `omen`、microchronology 发
    # dynasty/年段而后端读 history/omen_type/decade、figures/stories 发 page/page_size 而后端读 limit/offset、
    # celestial 丢了 q/has_crosswalk/in_chapter。离线桩当时对每个端点回同一份数据，所以一条都红不了。
    #   * slug 族：payload.slug（逃生舱）> id > q（名称/slug 皆可由 q 兜）；
    #   * term_profile：omen > q > id（后端读 omen/label）；
    #   * figures/stories 的 page/page_size 折算成 limit/offset（显式 limit/offset 优先）。
    _XUANSHI_ACTIONS: dict[str, tuple[str, tuple[str, ...]]] = {
        "search": ("/xuanshi/search", ("q", "limit", "tradition")),  # :514-516
        "events": ("/xuanshi/events", ("q", "tradition", "dynasty", "technique", "history", "evidence", "page", "page_size")),  # :114-124
        "event": ("/xuanshi/event", ("id",)),  # :138（event_id / id 双认）
        "celestial": ("/xuanshi/celestial", ("dynasty", "omen", "history", "source", "year_from", "year_to", "has_crosswalk", "in_chapter", "q", "page", "page_size")),  # :155-165（q→keyword）
        "celestial_event": ("/xuanshi/celestial_event", ("id",)),  # :179
        "figures": ("/xuanshi/figures", ("q", "dynasty", "limit", "offset")),  # :241-244
        "figure": ("/xuanshi/figure", ("slug",)),  # :268
        "dynasties": ("/xuanshi/dynasties", ()),
        "dynasty": ("/xuanshi/dynasty", ("slug",)),  # :358
        "techniques": ("/xuanshi/techniques", ()),
        "technique": ("/xuanshi/technique", ("slug",)),  # :300
        "terms": ("/xuanshi/celestial_terms", ()),
        "term": ("/xuanshi/celestial_term", ("slug",)),  # :329
        "term_profile": ("/xuanshi/celestial_term_profile", ("omen",)),  # :222
        "timeline": ("/xuanshi/timeline", ("macro", "limit")),  # :456-458
        "map": ("/xuanshi/map", ("period",)),  # :426
        "graph": ("/xuanshi/persons_graph", ("top_n", "min_weight")),  # :441-442
        "stories": ("/xuanshi/stories", ("q", "dynasty", "limit", "offset")),  # :375-382（q→search_text）
        "story": ("/xuanshi/story", ("slug",)),  # :396
        "channels": ("/xuanshi/channels", ()),
        "daily": ("/xuanshi/daily", ("date_key",)),  # :530
        "summary": ("/xuanshi/summary", ()),
        "microchronology": ("/xuanshi/microchronology", ("history", "omen", "decade")),  # :193-195（omen→omen_type）
        "decade_omens": ("/xuanshi/decade_omens", ()),  # :204-210 无参
        "facets": ("/xuanshi/facets", ("tradition", "q", "dynasty", "technique", "history", "evidence")),  # :491-496
        "events_meta": ("/xuanshi/events_meta", ("tradition",)),  # :477
    }

    def _run_xuanshi_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        """玄史知识库检索：runtime 自带的只读 SQLite bundle，经 chart 服务 /xuanshi/* 端点查询。

        纯检索、无结果敏感设置；按 action 分派到 26 个端点之一。快照四段与 astrodata 同范式：
        [检索条件] 恒出；[结果总览]/[条目列表]/[条目详情] 按响应形状条件产出（列表响应出总览+列表，
        详情响应出详情）；[出处引证] 聚合条目里的 citation。
        """
        action = f"{payload.get('action') or 'search'}".strip() or "search"
        spec = self._XUANSHI_ACTIONS.get(action)
        if spec is None:
            raise ToolValidationError(
                f"Unknown xuanshi action: {action!r}",
                code="tool.invalid_argument",
                details={"allowed_actions": sorted(self._XUANSHI_ACTIONS)},
            )
        path, keys = spec
        source = dict(payload)
        if "slug" in keys and source.get("slug") is None:
            source["slug"] = source.get("id") if source.get("id") is not None else source.get("q")
        if action == "term_profile" and source.get("omen") is None:
            source["omen"] = source.get("q") if source.get("q") is not None else source.get("id")
        if "offset" in keys and source.get("limit") is None and source.get("page_size") is not None:
            source["limit"] = source.get("page_size")
        if "offset" in keys and source.get("offset") is None and source.get("page") is not None:
            size = source.get("limit") if source.get("limit") is not None else 30
            source["offset"] = max(0, (int(source["page"]) - 1) * int(size))
        body = {k: source.get(k) for k in keys if source.get(k) is not None}
        response = self._call_remote(path, body)
        snapshot_text = _build_xuanshi_snapshot_text(action, body, response)
        return {
            "action": action,
            "xuanshi": response,
            "snapshot_text": snapshot_text,
            "export_snapshot": self._augment_export_payload(technique="xuanshi", snapshot_text=snapshot_text),
        }

    def _run_astrodata_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        con = self._astrodata_connect()
        if con is None:
            # 数据库缺席（如精简部署）：如实降级，不臆造。
            snapshot_text = _render_snapshot_text([
                ("检索条件", "名人星盘数据库文件不在本地部署中，本次无法检索；可安装完整离线 runtime 后重试。"),
            ])
            return {
                "astrodata": {"available": False, "results": []},
                "snapshot_text": snapshot_text,
                "export_snapshot": self._augment_export_payload(technique="astrodata", snapshot_text=snapshot_text),
                "_warnings": ["名人星盘数据库文件缺席，返回降级说明。"],
            }
        try:
            person_title = f"{payload.get('personTitle') or ''}".strip()
            if person_title:
                row = con.execute("SELECT * FROM person WHERE title = ?", (person_title,)).fetchone()
                if row is None:
                    snapshot_text = _render_snapshot_text([
                        ("检索条件", f"条目：{person_title}"),
                        ("名人详情", "库内无此条目；请先用 query 检索取得精确 title。"),
                    ])
                    return {
                        "astrodata": {"available": True, "person": None},
                        "snapshot_text": snapshot_text,
                        "export_snapshot": self._augment_export_payload(technique="astrodata", snapshot_text=snapshot_text),
                    }
                cats = [r["category"] for r in con.execute(
                    "SELECT category FROM category WHERE person_title = ? LIMIT 30", (person_title,))]
                g = self._astrodata_row_get
                birth_chart = f"{row['birth_chart'] or ''}".strip()
                birth_date, _, birth_time = birth_chart.partition(" ")
                # v3.3.2 中文化：详情优先中文列，缺则回退英文。
                name_disp = g(row, "name_zh") or g(row, "name")
                born_disp = g(row, "born_zh") or g(row, "born_display")
                pos_disp = g(row, "pos_zh") or g(row, "pos")
                summary_disp = g(row, "summary_zh") or g(row, "wiki_summary")
                person = {
                    **self._astrodata_person_brief(row),
                    "gender": g(row, "gender"),
                    "zone": g(row, "zone"),
                    "lat": g(row, "lat"),
                    "lon": g(row, "lon"),
                    "gpsLat": g(row, "gpsLat"),
                    "gpsLon": g(row, "gpsLon"),
                    "birthDate": birth_date or None,
                    "birthTime": birth_time or None,
                    "timeAccuracy": g(row, "time_accuracy"),
                    "adbUrl": g(row, "adb_url"),
                    "wikiUrl": g(row, "wiki_url"),
                    "summaryZh": g(row, "summary_zh") or None,
                    "categories": cats,
                }
                detail_lines = [
                    f"{name_disp}（{row['title']}）",
                    f"出生：{born_disp or '—'}　评级（Rodden）：{g(row, 'rodden') or '—'}　时刻精度：{g(row, 'time_accuracy') or '—'}",
                    f"地点：{pos_disp or '—'}　坐标：{g(row, 'lat')} / {g(row, 'lon')}　时区：{g(row, 'zone')}",
                    f"排盘入参：date={birth_date or '—'} time={birth_time or '—'} zone={g(row, 'zone')} lat={g(row, 'lat')} lon={g(row, 'lon')}",
                    f"星盘三要：日 {g(row, 'sun') or '—'} / 月 {g(row, 'moon') or '—'} / 升 {g(row, 'asc') or '—'}",
                ]
                if cats:
                    detail_lines.append("分类：" + "；".join(cats[:12]) + ("…" if len(cats) > 12 else ""))
                wiki = f"{summary_disp or ''}".strip()
                sections = [
                    ("检索条件", f"条目：{person_title}"),
                    ("名人详情", "\n".join(detail_lines)),
                ]
                if wiki:
                    sections.append(("维基摘要", wiki[:1200] + ("…" if len(wiki) > 1200 else "")))
                sections.append((
                    "数据来源",
                    "出生数据：Astro-Databank / Astrodienst AG（非商业研究用途，保留 Rodden 评级与来源链接）；"
                    f"传记摘要：Wikipedia（CC BY-SA 4.0）。{row['adb_url'] or ''} {row['wiki_url'] or ''}".strip(),
                ))
                snapshot_text = _render_snapshot_text(sections)
                return {
                    "astrodata": {"available": True, "person": person},
                    "snapshot_text": snapshot_text,
                    "export_snapshot": self._augment_export_payload(technique="astrodata", snapshot_text=snapshot_text),
                }

            query = f"{payload.get('query') or ''}".strip()
            category = f"{payload.get('category') or ''}".strip()
            rodden_raw = payload.get("rodden")
            rodden = [r for r in ([rodden_raw] if isinstance(rodden_raw, str) else (rodden_raw or [])) if f"{r}".strip()]
            try:
                limit = max(1, min(100, int(payload.get("limit") or 20)))
            except (TypeError, ValueError):
                limit = 20
            try:
                offset = max(0, int(payload.get("offset") or 0))
            except (TypeError, ValueError):
                offset = 0

            def _like_escape(text: str) -> str:
                return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

            where: list[str] = []
            params: list[Any] = []
            base = "FROM person p"
            has_zh = self._astrodata_has_column(con, "person", "name_zh")
            has_catzh = self._astrodata_has_column(con, "category_zh", "en")
            if query:
                # 多列 LIKE 检索（对齐 v3.3.2 前端：name_zh/name/title/pos_zh/summary_zh），支持中文名/
                # 中文地点；FTS 只索引英文列，中文查询会静默返回空，故不用 FTS 走 LIKE（离线库规模可承受）。
                cols = ["p.name", "p.title", "p.pos"]
                if has_zh:
                    cols = ["p.name_zh", "p.name", "p.title", "p.pos_zh", "p.summary_zh"]
                pat = f"%{_like_escape(query)}%"
                where.append("(" + " OR ".join(f"{c} LIKE ? ESCAPE '\\' COLLATE NOCASE" for c in cols) + ")")
                params.extend(pat for _ in cols)
            if category:
                safe_cat = _like_escape(category)
                if has_catzh:
                    # 中文分类：category_zh(en→zh) 映射，匹配 zh 或英文原名（对齐前端 LEFT JOIN category_zh）。
                    where.append(
                        "p.title IN (SELECT c.person_title FROM category c "
                        "LEFT JOIN category_zh z ON z.en = c.category "
                        "WHERE z.zh LIKE ? ESCAPE '\\' COLLATE NOCASE OR c.category LIKE ? ESCAPE '\\' COLLATE NOCASE)"
                    )
                    params.extend([f"%{safe_cat}%", f"%{safe_cat}%"])
                else:
                    where.append("p.title IN (SELECT person_title FROM category WHERE category LIKE ? ESCAPE '\\')")
                    params.append(f"%{safe_cat}%")
            if rodden:
                where.append(f"p.rodden IN ({','.join('?' for _ in rodden)})")
                params.extend(str(r).upper() for r in rodden)
            if payload.get("birthYearFrom") is not None:
                where.append("p.birth_year >= ?")
                params.append(int(payload["birthYearFrom"]))
            if payload.get("birthYearTo") is not None:
                where.append("p.birth_year <= ?")
                params.append(int(payload["birthYearTo"]))
            if payload.get("hasTimeOnly"):
                where.append("p.has_time = 1")
            where_sql = (" WHERE " + " AND ".join(where)) if where else ""
            order_sql = " ORDER BY p.name_zh, p.name" if has_zh else " ORDER BY p.name"
            total = con.execute(f"SELECT COUNT(*) {base}{where_sql}", params).fetchone()[0]
            rows = con.execute(
                f"SELECT p.* {base}{where_sql}{order_sql} LIMIT ? OFFSET ?", [*params, limit, offset]
            ).fetchall()
            results = [self._astrodata_person_brief(r) for r in rows]
            cond_bits = [bit for bit in (
                f"全文：{query}" if query else "",
                f"分类：{category}" if category else "",
                f"评级：{'/'.join(str(r).upper() for r in rodden)}" if rodden else "",
                f"生年：{payload.get('birthYearFrom') or '…'}–{payload.get('birthYearTo') or '…'}" if (payload.get("birthYearFrom") is not None or payload.get("birthYearTo") is not None) else "",
                "仅含出生时刻" if payload.get("hasTimeOnly") else "",
            ) if bit]
            head = [
                "、".join(cond_bits) if cond_bits else "（无过滤条件）",
                f"命中 {total} 条，返回第 {offset + 1}–{offset + len(results)} 条。",
            ]
            if results:
                rows_txt = ["| 姓名 | 出生 | 评级 | 日/月/升 | 条目 |", "| --- | --- | --- | --- | --- |"]
                for item in results:
                    tri = f"{item['sun'] or '—'}/{item['moon'] or '—'}/{item['asc'] or '—'}"
                    name_disp = item.get("nameDisplay") or item.get("name")
                    born_disp = item.get("bornDisplay") or item.get("born")
                    rows_txt.append(f"| {name_disp} | {born_disp or '—'} | {item['rodden'] or '—'} | {tri} | {item['title']} |")
                body = "\n".join(rows_txt) + "\n用 personTitle=<条目> 取单人详情（含可直接排盘的出生数据）。"
            else:
                body = "无命中；可放宽检索词或分类（支持中文与英文原名）。"
            snapshot_text = _render_snapshot_text([
                ("检索条件", "\n".join(head)),
                ("命中列表", body),
            ])
            return {
                "astrodata": {"available": True, "total": total, "results": results, "offset": offset, "limit": limit},
                "snapshot_text": snapshot_text,
                "export_snapshot": self._augment_export_payload(technique="astrodata", snapshot_text=snapshot_text),
            }
        except sqlite3.Error as exc:
            # 老版本库缺 person_fts / birth_year·has_time 列，或检索式仍非法 → 优雅降级，不让整工具 ok=False。
            # 一次失败只报一条（v0.41.1）：此前 _degrade 与旧的 `_warnings` 通道各报一次、措辞不同、去重不掉 → 调用方看到两条。
            _degrade("astrodata query failed: %s", exc, note=f"名人库检索降级：{exc}")
            snapshot_text = _render_snapshot_text([
                ("检索条件", "名人库检索未能完成（数据库版本过旧或检索式无效）；请改用英文姓名关键词，或更新离线 runtime。"),
            ])
            return {
                "astrodata": {"available": True, "results": [], "error": "query_failed"},
                "snapshot_text": snapshot_text,
                "export_snapshot": self._augment_export_payload(technique="astrodata", snapshot_text=snapshot_text),
            }
        finally:
            con.close()
