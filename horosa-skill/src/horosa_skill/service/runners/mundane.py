"""世俗盘 runner（MundaneRunners）：入宫盘求解、地区盘、子盘段、类型卡、食相 / 周期任务。"""
from __future__ import annotations

from typing import Any

from horosa_skill.errors import ToolValidationError, bilingual
from horosa_skill.service._common import (
    _ad_of_date,
    _chart_at_moment_date_fields,
    _civil_date_str_of_ms,
    _civil_shift_moment,
    _civil_wall_ms_of_moment,
    _js_math_round,
    _leading_year_of,
    _render_snapshot_text,
    _shift_moment,
    _solunar_body_lon,
)
from horosa_skill.service._context import _degrade
from horosa_skill.service.text.astro_core import (
    _lon_to_sign_degree,
    _mundane_analysis_sections,
    _mundane_chart_digest,
)
from horosa_skill.service.text.chart_family import _build_astro_snapshot_text


class MundaneRunners:
    # 恒星派入境（solunar）盘型表：逐字取自上游 divination/mundane/solunar.js 的 SOLUNAR_TYPES。
    _SOLUNAR_TYPES = {
        "capsolar": {"body": "sun", "target": 270.0, "approx": "01-14"},
        "arisolar": {"body": "sun", "target": 0.0, "approx": "04-14"},
        "cansolar": {"body": "sun", "target": 90.0, "approx": "07-16"},
        "libsolar": {"body": "sun", "target": 180.0, "approx": "10-17"},
        "caplunar": {"body": "moon", "target": 270.0, "approx": None},
        "arilunar": {"body": "moon", "target": 0.0, "approx": None},
        "canlunar": {"body": "moon", "target": 90.0, "approx": None},
        "liblunar": {"body": "moon", "target": 180.0, "approx": None},
    }
    _SOLUNAR_MEAN_SPEED = {"sun": 0.9856, "moon": 13.1764}  # °/日，同上游 MEAN_SPEED

    def _solve_sidereal_ingress(
        self, type_key: str, year: str, payload: dict[str, Any], *, ayanamsa: str = "fagan_bradley"
    ) -> tuple[str, dict[str, Any]] | None:
        """迭代 /chart 求某体入某恒星黄道度的时刻（上游 solveSiderealIngress 的 Python 端口）。

        🔴 上游 solunar.js:150-157 明确警告的陷阱，这里逐条照搬：
        - **首步的带符号最短弧**只在「近种子」时才允许取负。太阳有 approx（±2 日内）算近种子；
          月盘无 approx、种子固定 1/1 属**远种子**，月速 13°/日、距目标常 >180°，首步若允许取负
          会有约半数年份收敛到上一年 12 月的回归。故远种子首步只许向前，其后各步已贴近真根，
          恢复双向微调。
        - 收敛判据 |diff| < 0.002°（约 7″；太阳约 3 分钟）。
        - 迭代上限：太阳 4 次、月 6 次。
        """
        spec = self._SOLUNAR_TYPES.get(type_key)
        if not spec:
            return None
        body = spec["body"]
        speed = self._SOLUNAR_MEAN_SPEED[body]
        moment = f"{year}-{spec['approx']} 12:00:00" if spec["approx"] else f"{year}-01-01 12:00:00"
        near_seed = spec["approx"] is not None
        chart: dict[str, Any] = {}
        for step in range(4 if body == "sun" else 6):
            # momentPipeline.chartAtMoment：ad / date / time 都取自时刻本身（DateTime.parse → format），不沿用页面 ad；
            # 日期只换数字间的分隔符——旧 replace("-", "/") 连公元前的前导负号一起换掉。
            chart = self._call_remote(
                "/chart",
                {
                    **_chart_at_moment_date_fields(moment),
                    "zone": payload.get("zone") or "+08:00",
                    "lat": payload.get("lat") or "31n13",
                    "lon": payload.get("lon") or "121e28",
                    "gpsLat": payload.get("gpsLat"),
                    "gpsLon": payload.get("gpsLon"),
                    "zodiacal": 1,
                    "siderealAyanamsa": ayanamsa,
                    "hsys": 10,
                    "tradition": 0,
                    "predictive": 0,
                },
            )
            lon = _solunar_body_lon(chart, body)
            if lon is None:
                return None
            diff = (spec["target"] - lon) % 360.0  # 前向弧（入境=向前到达目标）
            if diff > 180.0 and (near_seed or step > 0):
                diff -= 360.0
            if abs(diff) < 0.002:
                break
            moment = _shift_moment(moment, diff / speed)
        return moment, chart

    # 年之九主：九职的入境目标度与种子日，逐字取自上游 vedicMundane.js 的 EVENT_TARGET / APPROX_DAY。
    _NAVANAYAKA_EVENTS = {
        "ingress_0": (0.0, "04-14"),
        "ingress_60": (60.0, "06-15"),
        "ingress_90": (90.0, "07-16"),
        "ingress_120": (120.0, "08-17"),
        "ingress_180": (180.0, "10-17"),
        "ingress_240": (240.0, "12-16"),
        "ingress_270": (270.0, "01-14"),
        "ingress_ardra": (66 + 40 / 60, "06-22"),
    }
    # 九职表（key / 中文 / 事件 / 年偏移 / 管辖），同上游 NAVANAYAKA_OFFICES。
    _NAVANAYAKA_OFFICES = [
        ("raja", "王", "lunar_new_year", 0, "全年总基调、统治者、国运"),
        ("mantri", "相", "ingress_0", 0, "行政、内阁、治理"),
        ("senadhipati", "军帅", "ingress_120", 0, "国防、军队、治安"),
        ("sasyadhipati", "田主", "ingress_90", 0, "田间庄稼、收成"),
        ("dhanyadhipati", "谷主", "ingress_240", 0, "谷物、存粮"),
        ("arghadhipati", "价主", "ingress_60", 0, "物价、生活成本"),
        ("meghadhipati", "云主", "ingress_ardra", 0, "云、降雨"),
        ("rasadhipati", "汁主", "ingress_180", 0, "油、糖、盐、汁液类"),
        # 🔴 yearOffset=1：吠陀太阳年自梅沙入境起，摩羯入境(01-14)落在**次一公历年**才属同一
        # samvatsara；与其余八职同传 year 会取到梅沙年首之前 3 个月的那次，归属上一年度（上游原注）。
        ("nirasadhipati", "干主", "ingress_270", 1, "金属、宝石、矿、干货"),
    ]

    def _solve_vedic_ingress(self, event_key: str, year: int, payload: dict[str, Any]) -> str | None:
        """太阳入某恒星黄道度（Lahiri）的时刻（上游 solveVedicSolarIngress 的 Python 端口）。

        与恒星派那支的关键差异：**首步也须取最短带符号弧**（上游 :60-62 明确写了「曾加 i>0 守卫 →
        种子晚于真实入境时 diff≈360⁻ 被当成向前一整年，收敛到次年的入境盘」）。九职的种子都是
        approx 近似日，属近种子，故无远种子那条限制。
        """
        spec = self._NAVANAYAKA_EVENTS.get(event_key)
        if not spec:
            return None
        target, approx = spec
        moment = f"{year}-{approx} 12:00:00"
        for _ in range(4):
            chart = self._call_remote(
                "/chart",
                {
                    **_chart_at_moment_date_fields(moment),  # chartAtMoment：纪元随时刻（见 _solve_sidereal_ingress）
                    "zone": payload.get("zone") or "+08:00",
                    "lat": payload.get("lat") or "31n13",
                    "lon": payload.get("lon") or "121e28",
                    "gpsLat": payload.get("gpsLat"),
                    "gpsLon": payload.get("gpsLon"),
                    "zodiacal": 1,
                    "siderealAyanamsa": "lahiri",
                    "hsys": 0,
                    "tradition": 0,
                    "predictive": 0,
                },
            )
            lon = _solunar_body_lon(chart, "sun")
            if lon is None:
                return None
            diff = (target - lon) % 360.0
            if diff > 180.0:
                diff -= 360.0  # 首步也取最短带符号弧 —— 见 docstring
            if abs(diff) < 0.002:
                return moment
            # 上游 v3.13.0 vedicMundane.js:66-69：民用历墙钟轴挪（1582 以前儒略历），认不出即停（chart:null）。
            next_moment = _civil_shift_moment(moment, _js_math_round(diff / 0.98565 * 86400000))
            if not next_moment:
                return moment
            moment = next_moment
        return moment

    def _build_navanayaka_section(self, year: int, mesha_moment: str, payload: dict[str, Any]) -> str:
        """[年之九主]：九职各由一次恒星入境求根定时刻，再按该日的 vāra（星期主）定职星。

        「王」职是唯一例外：上游取梅沙入境前 35 日窗内**最近一次新月**，走
        `fetchMundaneEvents({kinds:['lunations']})`。本仓改用语义等价且**已在白名单**的
        `/astroextra/prenatal_syzygy`（「某时刻之前最近一次朔」正是它），避免为一职新放行端点。
        任一职求根失败留空（同上游「王位留空,UI 提示」的降级）。
        """
        try:
            js_v = self.js_client.run("mundane_navanayaka", {"offices": self._solve_navanayaka(year, mesha_moment, payload)})
            return f"{(js_v or {}).get('text') or ''}".strip()
        except Exception as exc:  # noqa: BLE001
            _degrade("navanayaka build failed: %s", exc)
            return ""

    def _solve_navanayaka(self, year: int, mesha_moment: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        offices: list[dict[str, Any]] = []
        for key, cn, event, offset, domain in self._NAVANAYAKA_OFFICES:
            moment = None
            if event == "lunar_new_year":
                moment = self._last_new_moon_before(mesha_moment, payload)
            else:
                try:
                    moment = self._solve_vedic_ingress(event, year + offset, payload)
                except Exception as exc:  # noqa: BLE001 — 单职失败只留空
                    _degrade("navanayaka office %s failed: %s", key, exc)
            offices.append({"key": key, "cn": cn, "domain": domain, "moment": moment})
        return offices

    def _last_new_moon_before(self, moment: str, payload: dict[str, Any]) -> str | None:
        """梅沙入境前最近一次朔。/astroextra/prenatal_syzygy 的语义即「此前最近一次朔望」。"""
        try:
            rsp = self._call_remote(
                "/astroextra/prenatal_syzygy",
                {
                    # 纪元 / 日期随梅沙时刻本身（公元前前导负号保留；/astroextra/prenatal_syzygy 不认 '/0500/…'）
                    **_chart_at_moment_date_fields(moment),
                    "zone": payload.get("zone") or "+08:00",
                    "lat": payload.get("lat") or "31n13",
                    "lon": payload.get("lon") or "121e28",
                    "gpsLat": payload.get("gpsLat"),
                    "gpsLon": payload.get("gpsLon"),
                },
            )
            if isinstance(rsp, dict):
                for field in ("date", "localTime", "moment", "time"):
                    value = rsp.get(field)
                    if isinstance(value, str) and len(value) >= 10:
                        return value
        except Exception as exc:  # noqa: BLE001 — 王位留空
            _degrade("navanayaka raja syzygy failed: %s", exc)
        return None

    # 世运口径（上游页面设置 MUNDANE_PAGE_SETTINGS，MundaneMain.js:519-526 + 吠陀世运输入 :1330-1340）：进每张卡的 extra
    # （buildMundaneCardSections 读 ex.mundaneRuleset / mundaneOrbScheme / mundaneIngressRule / vedic*），规则集行进快照头。
    _MUNDANE_SETTING_KEYS = (
        "mundaneRuleset", "mundaneOrbScheme", "mundaneIngressRule", "vedicDashaYearLen", "vedicFoundingYear", "vedicNatalAsc",
    )
    # 世运专属输入：不进 /chart 请求体（其余键 = 页面 fields：黄道/岁差/宫制/古典全局键，与 astro 盘同一套）。
    _MUNDANE_ONLY_KEYS = frozenset({
        "year", "ingressTerm", "mundaneType", "mhKind", "solunarType", "solunarWeights", "solunarOrb", "vedicYear",
        "regionKey", "regionCandidate",
        *_MUNDANE_SETTING_KEYS,
    })

    def _mundane_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        """世运口径键（有值才收）；给了任一键就先让 JS 按引擎自带表校验值域（认不出的报错，不静默当缺省）。"""
        settings = {k: payload[k] for k in self._MUNDANE_SETTING_KEYS if payload.get(k) not in (None, "")}
        if "vedicDashaYearLen" in settings:
            try:
                settings["vedicDashaYearLen"] = float(settings["vedicDashaYearLen"])
            except (TypeError, ValueError):
                pass
            if settings.get("vedicDashaYearLen") == 360.0:
                settings["vedicDashaYearLen"] = 360
        if "vedicFoundingYear" in settings:
            try:
                settings["vedicFoundingYear"] = int(f"{settings['vedicFoundingYear']}".strip())
            except ValueError:
                raise ToolValidationError(
                    bilingual(f"世运 vedicFoundingYear（建国年）须为整数：{settings['vedicFoundingYear']!r}",
                              f"mundane vedicFoundingYear must be an integer: {settings['vedicFoundingYear']!r}"),
                    code="tool.mundane_invalid_setting",
                    details={"invalid": [{"key": "vedicFoundingYear", "value": settings["vedicFoundingYear"], "allowed": "int"}]},
                ) from None
        if "vedicNatalAsc" in settings:
            settings["vedicNatalAsc"] = f"{settings['vedicNatalAsc']}".strip().lower()
        if not settings:
            return settings
        js = self.js_client.run("mundane_cards", {"action": "settings", "settings": settings})
        data = js.get("data") if isinstance(js, dict) else None
        invalid = data.get("invalid") if isinstance(data, dict) else None
        if invalid:
            parts = [f"{i.get('key')}={i.get('value')!r}（可选：{'/'.join(str(a) for a in (i.get('allowed') or []))}）" for i in invalid if isinstance(i, dict)]
            raise ToolValidationError(
                bilingual(f"世运盘设置取值无效：{'；'.join(parts)}。", f"mundane setting(s) invalid: {'; '.join(parts)}."),
                code="tool.mundane_invalid_setting",
                details={"invalid": invalid},
            )
        return settings

    def _run_mundane_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        # 世俗入宫盘 (mundane ingress): (1) get the precise solar-term ingress moment for the year via
        # /jieqi/year, (2) cast a /chart at that moment, (3) enrich with the v2.4.0 natal extras, then
        # (4) prepend a [世俗入宫] section to the astrochart snapshot. Mirrors 星阙 MundaneMain.
        year = f"{payload.get('year', '')}".strip()
        term = f"{payload.get('ingressTerm') or '春分'}".strip()
        zone = payload.get("zone") or "+08:00"
        lon = payload.get("lon")
        lat = payload.get("lat")
        settings = self._mundane_settings(payload)
        # 地区盘（上游 MUNDANE_TYPES 'region'）：底盘 = 预置建置盘（regionKey），不求入宫时刻——另走一条流程。
        if f"{payload.get('mundaneType') or ''}".strip() == "region":
            return self._run_mundane_region_chart(payload, settings)
        seed_payload = {
            "year": year,
            "ad": payload.get("ad", 1),
            "zone": zone,
            "lon": lon or "116e23",
            "lat": "23n26",  # jieqi MOMENT is global; lat only affects the (unused) seed chart.
            "gpsLat": 23.43,
            "gpsLon": payload.get("gpsLon") if payload.get("gpsLon") is not None else 116.38,
            "timeAlg": 0,
            "jieqis": [term],
            "seedOnly": 1,
        }
        seed_response = self._call_remote("/jieqi/year", seed_payload)
        jieqi24 = seed_response.get("jieqi24") if isinstance(seed_response, dict) else None
        ingress_time = ""
        if isinstance(jieqi24, list):
            for entry in jieqi24:
                if isinstance(entry, dict) and f"{entry.get('jieqi')}".strip() == term and entry.get("time"):
                    ingress_time = f"{entry.get('time')}".strip()
                    break
        if not ingress_time:
            raise ToolValidationError(
                f"无法取得 {year} 年「{term}」的入宫时刻。",
                code="tool.mundane_ingress_unavailable",
                details={"year": year, "ingressTerm": term, "jieqi24_count": len(jieqi24) if isinstance(jieqi24, list) else 0},
            )
        date_part, _, time_part = ingress_time.partition(" ")
        # 入宫盘 = 页面 fields（黄道/岁差/古典全局键随盘，上游 DivinationChartShell 与 astro 盘同一套构参）+ 入宫时刻。
        chart_payload = {
            **{k: v for k, v in payload.items() if k not in self._MUNDANE_ONLY_KEYS and v is not None},
            "date": date_part,
            "time": time_part or "00:00:00",
            "zone": zone,
            "lat": lat or "23n26",
            "lon": lon or "116e23",
            "gpsLat": payload.get("gpsLat"),
            "gpsLon": payload.get("gpsLon"),
            # castIngress：dt.parse(入宫时刻) → setTime(dt)，纪元随时刻本身（DateTime.parse 前导负号 = 公元前）
            "ad": _ad_of_date(date_part),
            "hsys": payload.get("hsys", 0),
            "tradition": payload.get("tradition", False),
            "predictive": 0,
        }
        chart_response = self._call_remote("/chart", chart_payload)
        chart_response = self._attach_natal_extras("mundane", chart_response, payload)
        chart_response = self._mundane_attach_egypt(chart_response, payload)

        # 世运卜卦（mundaneType='mundanehorary'）：上游对该盘型走的是「问事时刻的普通 /chart →
        # buildFacts → describeXQuestion」，机制同卜卦、问主=公众/国家、宫义按世运读。这里复用
        # 已经算好的入宫盘作为问事盘面（headless 无「问事时刻」这个交互输入，故以本盘为准），
        # 由 vendored 的三个纯函数出 [世运卜卦]/[世运问判] 两段。失败只是这两段不出。
        # 恒星派入境（solunar）：入境时刻由 Python 迭代 /chart 求根（上游那支走 HTTP，按 §5 归 Python），
        # 段文本由 vendored 的 describeSolunar / computeAngularity / rulerDeathSignature 纯函数出。
        mundane_type = f"{payload.get('mundaneType') or ''}".strip()
        if mundane_type not in self._MUNDANE_SUPPORTED_TYPES:
            # 认不出的盘型不许静默当入宫盘——说出来（region 已在上方分支走建置盘流程）。
            _degrade(
                "mundane: 不支持的盘型 mundaneType=%s（支持 %s），按入宫盘出段",
                mundane_type,
                "/".join(sorted(t for t in self._MUNDANE_SUPPORTED_TYPES if t)),
            )
        # 盘型专属卡要在该盘型自己的盘上算（上游页面盘 = 该盘型的盘）：求根得到的 (时刻, 盘) 记在这里。
        type_chart_ctx: dict[str, tuple[str, dict[str, Any]]] = {}
        solunar_text = ""
        if mundane_type == "solunar":
            try:
                solved = self._solve_sidereal_ingress(
                    f"{payload.get('solunarType') or 'capsolar'}", year, payload
                )
                if solved:
                    moment, solunar_chart = solved
                    type_chart_ctx["solunar"] = (moment, solunar_chart)
                    js_s = self.js_client.run(
                        "mundane_solunar",
                        {
                            "chart": solunar_chart,
                            "solunarType": payload.get("solunarType") or "capsolar",
                            "solunarWeights": payload.get("solunarWeights") or "scheme_a",
                            "solunarOrb": payload.get("solunarOrb") or 3,
                            "moment": moment,
                        },
                    )
                    solunar_text = f"{(js_s or {}).get('text') or ''}".strip()
                else:
                    # 求根器回 None（盘型键不认识 / 盘里取不到日月黄经）：盘型段与 [恒星派入境·概览] 都不会出，说出来。
                    _degrade("mundane solunar ingress unsolved (solunarType=%s)", payload.get("solunarType") or "capsolar")
            except Exception as exc:  # noqa: BLE001 — 求根/富化失败不许带崩入宫盘
                _degrade("mundane solunar build failed: %s", exc)
        # 吠陀世运（vedicmundane）：恒星黄道 Lahiri 的梅沙（白羊）入境盘。
        # 上游 castVedicIngress（MundaneMain.js:1282）用 vedicMundane.solveVedicSolarIngress('ingress_0') 求根，
        # 再把页面盘改成 恒星黄道 Lahiri · hsys 0 · tradition 0 在该时刻起盘；[吠陀世运·年度盘]/[世运大运]/
        # [KP 副主链] 读的正是这张盘，st.vedicMoment = 求根时刻。求根走同一个忠实端口 _solve_vedic_ingress
        # （九主各职也用它）——此前这里借用恒星派的 _solve_sidereal_ingress（步速 0.9856、首步规则不同），
        # 收敛点可差到分钟级，会让盘头与卡片印出两个不同的「入境时刻」。
        vedic_text = ""
        if mundane_type == "vedicmundane":
            try:
                vedic_year = f"{payload.get('vedicYear') or year}".strip()
                v_moment = self._solve_vedic_ingress("ingress_0", int(vedic_year), payload)
                if v_moment:
                    v_chart = self._call_remote("/chart", self._vedic_chart_payload(v_moment, payload))
                    type_chart_ctx["vedicmundane"] = (v_moment, v_chart)
                    vedic_text = "\n".join(
                        [
                            "[吠陀世运]",
                            f"年份：{vedic_year}",
                            "体系：恒星黄道 Lahiri · 梅沙入境为年度主盘",
                            f"梅沙入境时刻：{v_moment}",
                        ]
                    )
                    nav = self._build_navanayaka_section(int(vedic_year), v_moment, payload)
                    if nav:
                        vedic_text = f"{vedic_text}\n\n{nav}"
                else:
                    _degrade("mundane vedic mesha ingress unsolved (year=%s)", vedic_year)
            except Exception as exc:  # noqa: BLE001
                _degrade("mundane vedic ingress failed: %s", exc)
        horary_text = ""
        if mundane_type == "mundanehorary":
            try:
                js = self.js_client.run(
                    "mundane_horary",
                    {"chart": chart_response, "mhKind": payload.get("mhKind") or "war"},
                )
                horary_text = f"{(js or {}).get('text') or ''}".strip()
            except Exception as exc:  # noqa: BLE001 — 富化失败不许带崩入宫盘
                _degrade("mundane horary build failed: %s", exc)
        # 子盘群：新月/满月/日月食/地区盘/行星周期 + 世俗宫义/定局·年主·盘主/入境骨架/地理分野/地区盘推运。
        # collected 顺手收下子盘群已经取到的物料（朔望子盘、四季入境时刻），卡片段复用，不重复请求。
        collected: dict[str, Any] = {}
        # 判词 + 分析段（上游 buildAiSnapshot:2882-2915，vendored 抽出件）：skill 的世俗盘恒以入宫盘为底，故按 ingress 盘型在
        # 入宫盘上产 [世俗宫义]/[定局·年主/盘主]/[入境骨架]/[地理分野]（各盘型专属的 [世运问判]/[角化] 另由各自 JS 工具出）。
        try:
            year_num_for_extra: int | None = int(str(year).strip())
        except (TypeError, ValueError):
            year_num_for_extra = None
        analysis = self._mundane_analysis(
            chart_response,
            {**settings, "mundaneType": "ingress", "ingressTerm": term, "ingressYear": year_num_for_extra, "ingressMoment": ingress_time},
            {},
        )
        subchart_sections = self._build_mundane_subchart_sections(
            base_chart_payload=chart_payload,
            seed_payload=seed_payload,
            ingress_time=ingress_time,
            year=year,
            zone=zone,
            collect=collected,
            analysis=analysis,
        )
        subcharts_text = _render_snapshot_text(subchart_sections) if subchart_sections else ""
        # 右栏卡片段（上游 v3.11 [Q-444/T-407]）：上游 buildAiSnapshot 的拼接序是
        # head / 判词 / 分析段 / **cardSecs** / 盘面正文（MundaneMain.js:2992-2995），卡片段紧贴正文之前。
        cards_meta: dict[str, Any] = {}
        cards_text = self._build_mundane_card_text(
            payload=payload,
            mundane_type=mundane_type,
            year=year,
            term=term,
            ingress_time=ingress_time,
            zone=zone,
            chart_payload=chart_payload,
            chart_response=chart_response,
            collected=collected,
            type_chart_ctx=type_chart_ctx,
            settings=settings,
            meta_out=cards_meta,
        )
        # 快照头（上游 buildAiSnapshot MundaneMain.js:2852-2860）：盘名 / 规则集 / 入宫节气 / 年份 / 页面级覆盖行；
        # 「入宫时刻」是本仓底盘恒为入宫盘的补注。日/月食盘型的「受冲容许度」覆盖行（:2863-2867）同附头内。
        head_lines = ["[世俗入宫]"]
        if cards_meta.get("rulesetLabel"):
            head_lines.append(f"规则集：{cards_meta['rulesetLabel']}")
        head_lines += [f"入宫节气：{term}", f"年份：{year or '-'}"]
        if cards_meta.get("ingressRuleLabel"):
            head_lines.append(f"入境主管制：{cards_meta['ingressRuleLabel']}（页面级覆盖）")
        head_lines.append(f"入宫时刻：{ingress_time}")
        if mundane_type in ("solecl", "lunecl") and cards_meta.get("orbSchemeLabel"):
            head_lines.append(f"受冲容许度：{cards_meta['orbSchemeLabel']}（页面级覆盖）")
        head = "\n".join(head_lines)
        body = _build_astro_snapshot_text(chart_payload, chart_response)
        snapshot_text = "\n\n".join(
            part for part in (head, solunar_text, vedic_text, horary_text, subcharts_text, cards_text, body) if part
        ).strip()
        result = {
            "ingressTerm": term,
            "ingressYear": year,
            "ingressMoment": ingress_time,
            "chart": chart_response.get("chart"),
            "raw": chart_response,
            "snapshot_text": snapshot_text,
        }
        result["export_snapshot"] = self._augment_export_payload(technique="mundane", snapshot_text=snapshot_text)
        return result

    def _mundane_analysis(
        self, chart_response: dict[str, Any], extra: dict[str, Any], state: dict[str, Any]
    ) -> dict[str, Any] | None:
        """上游 buildAiSnapshot（MundaneMain.js:2849-2997）的 headLines / judge / extraSecs / cardSecs：vendored 抽出件
        buildMundaneAiSnapshotParts（经 JS 工具 mundane_cards action=analysis）。chart = 该盘型自己的盘；extra = 页面 extra
        （盘型键 + 世运口径 mundaneRuleset…）；state = 页面按需拉取物（progTargetYear / patData…）。失败 → warnings + None（不出段）。"""
        try:
            js = self.js_client.run("mundane_cards", {"action": "analysis", "chart": chart_response, "extra": extra, "state": state})
        except Exception as exc:  # noqa: BLE001 — 分析段失败不许带崩世俗盘，但必须说出来
            _degrade("mundane analysis sections failed: %s", exc)
            return None
        data = js.get("data") if isinstance(js, dict) else None
        if not isinstance(data, dict) or not data.get("ok"):
            err = data.get("error") if isinstance(data, dict) and isinstance(data.get("error"), dict) else {}
            _degrade("mundane analysis sections failed: %s", err.get("message") or err.get("code") or "unknown")
            return None
        return data

    def _mundane_attach_egypt(self, chart_response: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        """[埃及历]（上游 mundane preset 含该段；buildAstroSnapshotContent 对任意盘按 fields 的 egypt_* 七轴产出，astroAiSnapshot.js:1733）。
        与嵌入盘同：无 /astroextra/analysis 的天狼偕日升行。失败只是该段不出（_degrade 进 warnings）。"""
        try:
            egypt = self._build_egypt_section(chart_response, payload)
        except ToolValidationError:
            raise
        except Exception as exc:  # noqa: BLE001
            _degrade("mundane egypt section failed: %s", exc)
            return chart_response
        if not egypt:
            return chart_response
        enriched = dict(chart_response)
        enriched["_egyptSection"] = egypt
        return enriched

    def _run_mundane_region_chart(self, payload: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
        """地区盘（上游 MUNDANE_TYPES 'region'）：MundaneMain.applyRegion（:715-733）按 regionKey 取 regionCharts.js 预置建置记录
        （多候选时刻取 regionCandidate，缺省首候选 = 最通行者），把 日期/时刻/时区/经纬度 打进页面 fields 起普通 /chart，extra =
        {mundaneType:'region', regionKey, regionCn, regionFoundingYear}；快照 = buildAiSnapshot（:2849-2997）：
        头行 [地区盘] / 规则集 / 地区 → [世俗宫义] → [定局·年主/盘主] → [地理分野] → [地区盘推运]（盘龄 = 目标年 − 建置年，小限 + 法达；
        返照/次限是页面按需拉取，headless 不出）→ 右栏卡（[地区盘·12世俗宫]/[时刻校正] + 本命式各卡）→ 盘面正文。
        目标年 = 请求的 year（上游 progTargetYear，页面缺省今年——headless 由调用方给，改它 [地区盘推运] 必变）。"""
        resolved = self.js_client.run(
            "mundane_cards",
            {"action": "region", "regionKey": payload.get("regionKey"), "regionCandidate": payload.get("regionCandidate")},
        )
        data = resolved.get("data") if isinstance(resolved, dict) else None
        if not isinstance(data, dict) or not data.get("ok"):
            err = data.get("error") if isinstance(data, dict) and isinstance(data.get("error"), dict) else {}
            keys = list((data or {}).get("keys") or []) if isinstance(data, dict) else []
            raise ToolValidationError(
                bilingual(
                    f"地区盘 {err.get('message') or '取盘失败'}；可选 regionKey：{'/'.join(keys) or '（无）'}。",
                    f"mundane region chart: {err.get('message') or 'lookup failed'}; regionKey must be one of {keys}.",
                ),
                code="tool.mundane_unknown_region",
                details={
                    "regionKey": payload.get("regionKey"), "regionCandidate": payload.get("regionCandidate"),
                    "allowed": keys, "candidates": (data or {}).get("candidates") if isinstance(data, dict) else None,
                    "reason": err.get("code"),
                },
            )
        fields = data.get("fields") or {}
        extra = data.get("extra") or {}
        region = data.get("region") or {}
        try:
            target_year = int(f"{payload.get('year')}".strip())
        except (TypeError, ValueError):
            raise ToolValidationError(
                bilingual(f"地区盘的 year（推运目标年）须为整数：{payload.get('year')!r}", f"mundane region: year (progression target year) must be an integer: {payload.get('year')!r}"),
                code="tool.mundane_invalid_setting",
                details={"invalid": [{"key": "year", "value": payload.get("year"), "allowed": "int"}]},
            ) from None
        # 建置盘 = 页面 fields（黄道/岁差/宫制/古典全局键随盘）+ 建置记录的时刻与地点（applyRegion 的 patchFields 同键）。
        chart_payload = {
            **{k: v for k, v in payload.items() if k not in self._MUNDANE_ONLY_KEYS and v is not None},
            "date": fields.get("date"),
            "time": fields.get("time") or "12:00:00",
            "zone": fields.get("zone") or "+00:00",
            "lat": fields.get("lat"),
            "lon": fields.get("lon"),
            "gpsLat": fields.get("gpsLat"),
            "gpsLon": fields.get("gpsLon"),
            "pos": fields.get("pos"),
            "ad": _ad_of_date(fields.get("date")),  # applyRegion：ad = dt.ad（建置记录日期的纪元）
            "hsys": payload.get("hsys", 0),
            "tradition": payload.get("tradition", False),
            "predictive": 0,
        }
        chart_response = self._call_remote("/chart", chart_payload)
        chart_response = self._attach_natal_extras("mundane", chart_response, payload)
        chart_response = self._mundane_attach_egypt(chart_response, payload)
        region_extra = {**settings, **extra}
        state: dict[str, Any] = {"progTargetYear": target_year}
        patterns = self._mundane_pattern_data(chart_payload)
        if patterns is not None:
            state["patData"] = patterns
        analysis = self._mundane_analysis(chart_response, region_extra, state)
        if analysis is not None:
            head_lines = [f"{line}" for line in (analysis.get("headLines") or [])]
            judge = f"{analysis.get('judge') or ''}".strip()
            extra_secs = [f"{b}".strip() for b in (analysis.get("extraSecs") or []) if f"{b}".strip()]
            card_texts = [f"{c.get('text') or ''}".strip() for c in (analysis.get("cards") or []) if isinstance(c, dict) and f"{c.get('text') or ''}".strip()]
        else:
            # 抽出件失败（已进 warnings）：头行按上游 :2852-2853/2868 最小复现（规则集查名走 JS 设置面），分析段/卡片缺席。
            meta = self._mundane_settings_meta(settings)
            head_lines = ["[地区盘]"]
            if meta.get("rulesetLabel"):
                head_lines.append(f"规则集：{meta['rulesetLabel']}")
            head_lines.append(f"地区：{extra.get('regionCn') or '-'}")
            judge, extra_secs, card_texts = "", [], []
        body = _build_astro_snapshot_text(chart_payload, chart_response)
        # 拼接序 = 上游 :2996 [head, judge, ...extraSecs, ...cardSecs, body].filter(Boolean).join('\n\n')。
        snapshot_text = "\n\n".join(part for part in ("\n".join(head_lines), judge, *extra_secs, *card_texts, body) if part).strip()
        result = {
            "mundaneType": "region",
            "regionKey": extra.get("regionKey"),
            "regionCn": extra.get("regionCn"),
            "regionFoundingYear": extra.get("regionFoundingYear"),
            "regionCandidate": (region.get("candidate") or {}).get("key") if isinstance(region.get("candidate"), dict) else None,
            "regionMoment": f"{fields.get('date')} {fields.get('time') or '12:00:00'} {fields.get('zone') or '+00:00'}",
            "progTargetYear": target_year,
            "chart": chart_response.get("chart"),
            "raw": chart_response,
            "snapshot_text": snapshot_text,
        }
        result["export_snapshot"] = self._augment_export_payload(technique="mundane", snapshot_text=snapshot_text)
        return result

    def _mundane_settings_meta(self, settings: dict[str, Any]) -> dict[str, Any]:
        """快照头的查名（规则集 label / 两条页面级覆盖行）：JS mundane_cards action=settings 的 meta；失败回 {}（已 _degrade）。"""
        try:
            js = self.js_client.run("mundane_cards", {"action": "settings", "settings": settings or {}})
            data = js.get("data") if isinstance(js, dict) else None
            meta = data.get("meta") if isinstance(data, dict) else None
            return dict(meta) if isinstance(meta, dict) else {}
        except Exception as exc:  # noqa: BLE001
            _degrade("mundane settings meta failed: %s", exc)
            return {}

    def _build_mundane_subchart_sections(
        self,
        *,
        base_chart_payload: dict[str, Any],
        seed_payload: dict[str, Any],
        ingress_time: str,
        year: str,
        zone: str,
        collect: dict[str, Any] | None = None,
        analysis: dict[str, Any] | None = None,
    ) -> list[tuple[str, str]]:
        # 每个子盘独立 try/except：任一端点失败只降级该段为说明文本，绝不破坏世俗盘主流程。
        # collect（可选）：把已取到的朔望子盘 {'syzygy': {'new'|'full': {'moment', 'chart'}}} 与四季入境时刻
        # {'season': {节气: 时刻}} 交还调用方，供右栏卡片段复用（不为同一份物料再打一遍后端）。
        ing_date = base_chart_payload.get("date")
        ing_time = base_chart_payload.get("time")
        lat = base_chart_payload.get("lat")
        lon = base_chart_payload.get("lon")
        try:
            year_num = int(str(year).strip())
        except (TypeError, ValueError):
            year_num = 0
        sections: list[tuple[str, str]] = []

        # ── 新月图 / 满月图：自入宫时刻回溯最近朔望，再自该朔望回溯得另一相，一朔一望各起子盘 ──
        syz_by_type: dict[str, dict[str, Any]] = {}
        try:
            s1 = self._call_remote(
                "/astroextra/prenatal_syzygy",
                {"date": ing_date, "time": ing_time, "zone": zone, "lat": lat, "lon": lon},
            )
            if isinstance(s1, dict) and s1.get("type"):
                syz_by_type[s1["type"]] = s1
                # 另一相恒在首相之前 ~14.77 天：探针取首相前一日再回溯。若直接从首相时刻起搜，
                # 该时刻按秒舍入恰落在真朔/望点之后时，回溯会把同一相当场重捕，另一相就丢了。
                probe_date, probe_time = s1.get("date"), s1.get("time")
                # 民用历墙钟轴上退一日（公元前 / 1582 以前儒略历；旧 strptime 对公元前直接失败 → 探针原地重捕同一相）
                probe = _civil_shift_moment(f"{probe_date} {probe_time}", -86400000)
                if probe:
                    probe_date, probe_time = probe.split(" ")
                s2 = self._call_remote(
                    "/astroextra/prenatal_syzygy",
                    {"date": probe_date, "time": probe_time, "zone": zone, "lat": lat, "lon": lon},
                )
                if isinstance(s2, dict) and s2.get("type") and s2["type"] not in syz_by_type:
                    syz_by_type[s2["type"]] = s2
        except Exception as exc:  # noqa: BLE001 - degrade to a note, never break mundane
            _degrade("mundane prenatal_syzygy failed: %s", exc)
        for title, syz_type, phase_cn in (("新月图", "new", "朔（新月·日月合）"), ("满月图", "full", "望（满月·日月冲）")):
            syz = syz_by_type.get(syz_type)
            if not isinstance(syz, dict):
                sections.append((title, f"未能定位入宫前最近的{phase_cn}。"))
                continue
            moment = syz.get("datetime") or f"{syz.get('date', '')} {syz.get('time', '')}".strip()
            lines = [
                f"{phase_cn}时刻：{moment}",
                f"日黄经 {syz.get('sunLon')}°，月黄经 {syz.get('moonLon')}°",
            ]
            try:
                sub_chart = self._call_remote(
                    "/chart", {**base_chart_payload, "date": syz.get("date"), "time": syz.get("time"), "ad": _ad_of_date(syz.get("date"))}
                )
                if collect is not None and isinstance(sub_chart, dict):
                    collect.setdefault("syzygy", {})[syz_type] = {"moment": moment, "chart": sub_chart}
                digest = _mundane_chart_digest(sub_chart)
                if digest:
                    lines.append("子盘四轴/日月：" + "；".join(digest))
            except Exception as exc:  # noqa: BLE001
                _degrade("mundane %s chart failed: %s", title, exc)
            sections.append((title, "\n".join(lines)))

        # ── 日食图 / 月食图：eclipsedetail 只回全球食时长（食时长定则的关键量），呈影响时长判词 ──
        for title, kind, phase_cn, unit_default, rule in (
            ("日食图", "solar", "日食", "年", "日食时长 N 小时 → 影响约 N 年"),
            ("月食图", "lunar", "月食", "月", "月食时长 N 小时 → 影响约 N 月"),
        ):
            try:
                ed = self._call_remote(
                    "/astroextra/eclipsedetail",
                    {"date": ing_date, "time": ing_time, "zone": zone, "eclipseKind": kind},
                )
            except Exception as exc:  # noqa: BLE001
                _degrade("mundane eclipsedetail(%s) failed: %s", kind, exc)
                ed = {}
            if isinstance(ed, dict) and ed.get("durationHours"):
                unit = ed.get("influenceUnit") or unit_default
                sections.append((
                    title,
                    "\n".join([
                        f"自入宫时刻顺推最近{phase_cn}：全球食持续约 {ed.get('durationHours')} 小时。",
                        f"食时长定则（{rule}）→ 本次影响约 {ed.get('influence')} {unit}。",
                        "（食盘极大时刻的整轮定盘属交互功能，此处给出无头可复算的影响时长判词。）",
                    ]),
                ))
            else:
                sections.append((title, f"自入宫时刻顺推未检索到{phase_cn}。"))

        # ── 地区盘：以入宫（全球统一）时刻定盘于格林尼治（世界年图基准），与本地入宫盘对照 ──
        try:
            world_chart = self._call_remote(
                "/chart",
                {**base_chart_payload, "lat": "51n29", "lon": "0e00", "gpsLat": 51.48, "gpsLon": 0.0},
            )
            digest = _mundane_chart_digest(world_chart)
            body = [f"以入宫时刻（{ingress_time}）定盘于格林尼治（0°经线 51°29′N，世界年图基准）："]
            body.extend(digest or ["未取得地区盘轴点。"])
            body.append("——同一天象、异地宫位；与上文本地入宫盘四轴对照可见地域落点差异。")
            sections.append(("地区盘", "\n".join(body)))
        except Exception as exc:  # noqa: BLE001
            _degrade("mundane world chart failed: %s", exc)
            sections.append(("地区盘", "未能取得世界年图基准盘。"))

        # ── 行星周期：木土大合相（前后 20 年最近三次）+ Barbault 行星聚散指数拐点 ──
        cycle_lines: list[str] = []
        if year_num:
            try:
                gc = self._call_remote("/astroextra/greatconj", {"startYear": year_num - 20, "endYear": year_num + 20})
                conjs = gc.get("conjunctions") if isinstance(gc, dict) else None
                if isinstance(conjs, list) and conjs:
                    nearest = sorted(conjs, key=lambda c: abs(int(c.get("year", 0)) - year_num))[:3]
                    cycle_lines.append("木土大合相（前后 20 年内，至多三次）：")
                    for c in sorted(nearest, key=lambda c: int(c.get("year", 0))):
                        cycle_lines.append(f"  {c.get('year')}-{int(c.get('month', 0)):02d} 合于 {_lon_to_sign_degree(c.get('lon'))}")
            except Exception as exc:  # noqa: BLE001
                _degrade("mundane greatconj failed: %s", exc)
            try:
                bb = self._call_remote(
                    "/astroextra/barbault",
                    {"startYear": year_num - 10, "endYear": year_num + 10, "stepMonths": 1},
                )
                extrema = bb.get("extrema") if isinstance(bb, dict) else None
                if isinstance(extrema, list) and extrema:
                    near = sorted(extrema, key=lambda e: abs(int(e.get("year", 0)) - year_num))[:2]
                    planets = "、".join(str(p) for p in (bb.get("planets") or []))
                    cycle_lines.append(f"Barbault 行星聚散指数（{planets}；满值 {bb.get('maxIndex')}）最近拐点：")
                    for e in sorted(near, key=lambda e: int(e.get("year", 0))):
                        kind_cn = "极小（聚集·危机/紧张）" if e.get("kind") == "min" else "极大（四散·扩张/繁荣）"
                        cycle_lines.append(f"  {e.get('year')}-{int(e.get('month', 0)):02d} 指数 {e.get('index')} {kind_cn}")
            except Exception as exc:  # noqa: BLE001
                _degrade("mundane barbault failed: %s", exc)
        sections.append(("行星周期", "\n".join(cycle_lines) if cycle_lines else "未能取得慢星周期数据（需有效年份）。"))

        # ── [世俗宫义] / [定局·年主/盘主] / [入境骨架] / [地理分野]：上游 buildAiSnapshot（MundaneMain.js:2882-2915）的判词与
        # 分析段，由 vendored 抽出件 buildMundaneAiSnapshotParts 在入宫盘上产出：describeMundaneChart → formatMundaneHouseTable（GFM 表）/
        # describeMundaneVictor(facts, mundaneRuleset)（年主星累分 + 逐星得分与偶然项）/ describeIngressSkeleton + describeMundaneSyzygy /
        # describeChorography(facts, rulesetConfig(mundaneRuleset).chorographyDataset)（数据集随规则集：托勒密古典 / 古典+中世纪 / 现代综合）。
        # 此前四段是 skill 自拟 Python 行（静态宫义表、上升座主落点、托勒密静态配当），[定局·年主/盘主]/[地理分野] 不随规则集。
        # analysis=None（JS builder 失败，已进 warnings）→ 四段缺席（导出层报 missing，不回落自拟行）。
        sections.extend(_mundane_analysis_sections(analysis, ("世俗宫义", "定局·年主/盘主", "入境骨架", "地理分野")))

        # ── 地区盘推运：年度四季入宫时刻序列（地区盘随每季太阳入基本宫推移）──
        prog_rows: list[str] = []
        try:
            sy = self._call_remote(
                "/jieqi/year",
                {**seed_payload, "jieqis": ["春分", "夏至", "秋分", "冬至"]},
            )
            j24 = sy.get("jieqi24") if isinstance(sy, dict) else None
            if isinstance(j24, list):
                want = ["春分", "夏至", "秋分", "冬至"]
                by_term = {
                    str(e.get("jieqi")).strip(): str(e.get("time")).strip()
                    for e in j24
                    if isinstance(e, dict) and str(e.get("jieqi")).strip() in want and e.get("time")
                }
                for t in want:
                    if t in by_term:
                        prog_rows.append(f"  {t}入宫：{by_term[t]}")
                if collect is not None and by_term:
                    collect["season"] = {t: by_term[t] for t in want if t in by_term}
        except Exception as exc:  # noqa: BLE001
            _degrade("mundane seasonal ingress failed: %s", exc)
        prog_body = ["年度四季入宫定盘序列（地区盘随每季太阳入基本宫逐季推移）："]
        prog_body.extend(prog_rows or ["未能取得四季入宫时刻。"])
        sections.append(("地区盘推运", "\n".join(prog_body)))

        return sections

    # ── 世运右栏卡片段（上游 v3.11 [Q-444/T-407]）─────────────────────────────────────────────
    # 产段函数 = 上游 components/mundane/MundaneMain.js:232 `buildMundaneCardSections(chart, extra, state, facts)`，
    # vendored 逐字（horosa-core-js/src/vendor/mundane/MundaneMain.js，manifest truncate_before 剥 UI 尾部），
    # 经 JS 工具 `mundane_cards` 调用。上游页面的「按需拉取物」在 React state 里；这里由 Python 取数后原样喂入
    # （请求型编排归 Python，AGENTS §5）。无数据即不成段，与上游「算过才成段」同形。
    #
    # 支持的盘型（上游 MUNDANE_TYPES，MundaneMain.js:43）。region（地区盘）走 _run_mundane_region_chart：按 regionKey 取
    # vendored regionCharts.js 的预置建置盘（上游 applyRegion 同一取值），底盘即该建置盘、不求入宫。
    _MUNDANE_SUPPORTED_TYPES = frozenset(
        {"", "ingress", "newmoon", "fullmoon", "solecl", "lunecl", "cycles", "solunar", "vedicmundane", "mundanehorary", "region"}
    )
    # 盘型专属卡（上游按 extra.mundaneType 分支产出，行号为 MundaneMain.js）。其余「本命式」卡
    # （天气占星/四轴特殊点/会合指示星/盘型格局/世运恒星命中/赤纬平行）对任何非 cycles 盘型都会产——
    # skill 的世俗盘恒以入宫盘为底（正文段即入宫盘），故本命式卡只取入宫底盘那一轮；盘型轮只保留本表的
    # 专属卡，免得同名段在一份快照里出现两次、且归属到错的盘。天气与农业（:457）需页面手填的「受孕日」
    # st.garbhaDate，headless 无来源 → 永不产，仍留在表里以便将来有输入时自动放行。
    _MUNDANE_TYPE_CARDS: dict[str, tuple[str, ...]] = {
        "newmoon": ("新月图判读",),  # :269
        "fullmoon": ("满月图判读",),  # :269
        "solecl": ("日食图判读", "食族 Saros", "天象占参考"),  # :278-310
        "lunecl": ("月食图判读", "食族 Saros", "天象占参考"),  # :278-310
        "solunar": ("恒星派入境·概览",),  # :428
        "vedicmundane": ("吠陀世运·年度盘", "世运大运", "KP 副主链", "天气与农业"),  # :435-458
        "mundanehorary": ("世运问判·得力明细",),  # :460
        "cycles": ("木土纪元", "大年时代", "Barbault 聚散指数"),  # :471-502
    }
    # 行星周期卡的页面物料（type==='cycles'）：
    #   木土会合表 = 页面挂载即自动算的 computeGreatConj（:576 componentDidMount → :753），state 缺省
    #   gcStart 1300 / gcEnd 2200 / gcPair 'jupiter-saturn' / gcAspect 0（:554），木土合相走 /astroextra/greatconj、
    #   gcMode 置 'ages'（:769）。builder 自己的显示回落 clampYear(st.gcStart, 1300)（:476）与之同值。
    #   Barbault 指数 = 「绘制」按钮 computeBarbault（:787）：缺省 bbStart 1900 / bbEnd 2050 / bbSet 'slow5'（:557），
    #   行星取 BARBAULT_SETS[0]（:101，五慢星），stepMonths = 跨度>160 年 12、>80 年 6、否则 3（:793）。
    _MUNDANE_GC_DEFAULT_STATE = {"gcStart": 1300, "gcEnd": 2200, "gcPair": "jupiter-saturn", "gcAspect": 0, "gcMode": "ages"}
    _MUNDANE_BB_DEFAULT_STATE = {"bbStart": 1900, "bbEnd": 2050, "bbSet": "slow5"}
    _MUNDANE_BB_DEFAULT_PLANETS = ("Jupiter", "Saturn", "Uranus", "Neptune", "Pluto")

    @staticmethod
    def _vedic_chart_payload(moment: str, payload: dict[str, Any]) -> dict[str, Any]:
        """梅沙入境盘：上游 castVedicIngress 把页面盘改成 zodiacal 1 · lahiri · hsys 0 · tradition 0（:1290）。"""
        return {
            # castVedicIngress：setTime(momentToDateTime(求根时刻)) → 纪元 / 日期随时刻本身
            **_chart_at_moment_date_fields(moment),
            "zone": payload.get("zone") or "+08:00",
            "lat": payload.get("lat") or "31n13",
            "lon": payload.get("lon") or "121e28",
            "gpsLat": payload.get("gpsLat"),
            "gpsLon": payload.get("gpsLon"),
            "zodiacal": 1,
            "siderealAyanamsa": "lahiri",
            "hsys": 0,
            "tradition": 0,
            "predictive": 0,
        }

    def _build_mundane_card_text(
        self,
        *,
        payload: dict[str, Any],
        mundane_type: str,
        year: str,
        term: str,
        ingress_time: str,
        zone: str,
        chart_payload: dict[str, Any],
        chart_response: dict[str, Any],
        collected: dict[str, Any],
        type_chart_ctx: dict[str, tuple[str, dict[str, Any]]],
        settings: dict[str, Any] | None = None,
        meta_out: dict[str, Any] | None = None,
    ) -> str:
        try:
            year_num: int | None = int(str(year).strip())
        except (TypeError, ValueError):
            year_num = None
        # ── 入宫底盘一轮：上游 castIngress 落的 extra 就是这四键（:629）。
        base_state: dict[str, Any] = {}
        season = collected.get("season")
        if isinstance(season, dict) and season and year_num is not None:
            # 上游「起四季盘」按钮（:638 scanSeasonalIngresses）= fetchPreciseJieqiSeed 四枢轴 → {节气: {time…}}；
            # skill 的 [地区盘推运] 已为同一年取过这四个时刻（同一 /jieqi/year seedOnly 请求），直接复用。
            base_state["seasonSeed"] = {t: {"term": t, "time": v} for t, v in season.items()}
            base_state["seasonSeedYear"] = year_num
        patterns = self._mundane_pattern_data(chart_payload)
        if patterns is not None:
            base_state["patData"] = patterns
        jobs: list[dict[str, Any]] = [
            {
                "id": "ingress",
                "chart": chart_response,
                "extra": {"mundaneType": "ingress", "ingressTerm": term, "ingressYear": year_num, "ingressMoment": ingress_time},
                "state": base_state,
            }
        ]
        type_job = self._mundane_type_card_job(
            mundane_type=mundane_type,
            payload=payload,
            ingress_time=ingress_time,
            zone=zone,
            chart_payload=chart_payload,
            chart_response=chart_response,
            collected=collected,
            type_chart_ctx=type_chart_ctx,
        )
        if type_job is not None:
            jobs.append(type_job)
        # 世运口径随每张卡的 extra（上游页面 extra 是各盘型共享的一份；buildMundaneCardSections 按键读）。
        for job in jobs:
            job["extra"] = {**(settings or {}), **(job.get("extra") or {})}
        try:
            js = self.js_client.run("mundane_cards", {"jobs": jobs, "settings": settings or {}})
        except Exception as exc:  # noqa: BLE001 — 卡片段失败不许带崩世俗盘主流程，但必须说出来
            _degrade("mundane card sections failed: %s", exc)
            return ""
        data = js.get("data") if isinstance(js, dict) else None
        if meta_out is not None and isinstance(data, dict) and isinstance(data.get("meta"), dict):
            meta_out.update(data["meta"])
        results = data.get("jobs") if isinstance(data, dict) else None
        if not isinstance(results, list):
            _degrade("mundane card sections: JS 工具返回形状异常（缺 data.jobs）")
            return ""
        blocks: list[str] = []
        for res in results:
            if not isinstance(res, dict):
                continue
            job_id = f"{res.get('id') or ''}"
            if not res.get("ok"):
                err = res.get("error") if isinstance(res.get("error"), dict) else {}
                _degrade("mundane card job %s failed: %s", job_id, err.get("message") or err.get("code") or "unknown")
                continue
            keep = None if job_id == "ingress" else set(self._MUNDANE_TYPE_CARDS.get(job_id, ()))
            for card in res.get("cards") or []:
                if not isinstance(card, dict):
                    continue
                if keep is not None and card.get("title") not in keep:
                    continue
                text = f"{card.get('text') or ''}".strip()
                if text:
                    blocks.append(text)
        return "\n\n".join(blocks)

    def _mundane_pattern_data(self, chart_payload: dict[str, Any]) -> list[Any] | None:
        """[盘型格局] 的「相位格局」行：上游「查格局」按钮（MundaneMain.js:825 computeMundanePatterns）以
        chartParams(chart) 打 /astroextra/analysis、取 `patterns`（后端 detect_patterns）。

        请求体照 AstroExtraCommon.chartParams 的键：盘面时刻/地点/宫制/黄道 + tradition=false·predictive=false。
        失败返回 None（该几行不出）并记降级——**不**像上游那样把错误信封读成「本盘无显著相位格局」。
        """
        body = {
            "date": chart_payload.get("date"),
            "time": chart_payload.get("time"),
            "ad": chart_payload.get("ad", 1),
            "zone": chart_payload.get("zone"),
            "lat": chart_payload.get("lat"),
            "lon": chart_payload.get("lon"),
            "hsys": chart_payload.get("hsys", 0),
            "zodiacal": chart_payload.get("zodiacal", 0),
            "siderealAyanamsa": chart_payload.get("siderealAyanamsa") or "",
            "tradition": False,
            "predictive": False,
        }
        try:
            rsp = self._call_remote("/astroextra/analysis", body)
        except Exception as exc:  # noqa: BLE001
            _degrade("mundane aspect patterns (/astroextra/analysis) failed: %s", exc)
            return None
        if not isinstance(rsp, dict):
            _degrade("mundane aspect patterns: /astroextra/analysis 返回非对象")
            return None
        pats = rsp.get("patterns")
        # 上游：`(r && r.patterns) ? r.patterns : []` —— 成功但无格局 = 空表（卡内写「本盘无显著相位格局」）。
        return pats if isinstance(pats, list) else []

    def _mundane_type_card_job(
        self,
        *,
        mundane_type: str,
        payload: dict[str, Any],
        ingress_time: str,
        zone: str,
        chart_payload: dict[str, Any],
        chart_response: dict[str, Any],
        collected: dict[str, Any],
        type_chart_ctx: dict[str, tuple[str, dict[str, Any]]],
    ) -> dict[str, Any] | None:
        if mundane_type in ("newmoon", "fullmoon"):
            # 上游 useMoment（:688）：选中的朔/望行 → extra.selectedMoment = 该行 localTime，页面盘改排到该时刻。
            # skill 的新月/满月子盘 = 入宫前最近一次朔/望（[新月图]/[满月图] 段同一张盘）。
            syz = (collected.get("syzygy") or {}).get("new" if mundane_type == "newmoon" else "full")
            if not isinstance(syz, dict) or not isinstance(syz.get("chart"), dict):
                _degrade("mundane %s card: 未取得朔望子盘", mundane_type)
                return None
            return {
                "id": mundane_type,
                "chart": syz["chart"],
                "extra": {"mundaneType": mundane_type, "selectedMoment": syz.get("moment")},
                "state": {},
            }
        if mundane_type in ("solecl", "lunecl"):
            return self._mundane_eclipse_job(mundane_type, chart_payload=chart_payload, ingress_time=ingress_time, zone=zone)
        if mundane_type == "solunar":
            ctx = type_chart_ctx.get("solunar")
            if not ctx:
                return None  # 求根失败已在求根处记过降级
            return {
                "id": "solunar",
                "chart": ctx[1],
                "extra": {
                    "mundaneType": "solunar",
                    "solunarType": payload.get("solunarType"),
                    "solunarWeights": payload.get("solunarWeights"),
                    "solunarOrb": payload.get("solunarOrb"),
                },
                "state": {},
            }
        if mundane_type == "vedicmundane":
            ctx = type_chart_ctx.get("vedicmundane")
            if not ctx:
                return None
            try:
                vedic_year: int | None = int(f"{payload.get('vedicYear') or payload.get('year')}".strip())
            except (TypeError, ValueError):
                vedic_year = None
            return {
                "id": "vedicmundane",
                "chart": ctx[1],
                "extra": {"mundaneType": "vedicmundane", "vedicYear": vedic_year},
                "state": {"vedicMoment": ctx[0]},
            }
        if mundane_type == "mundanehorary":
            # 问事盘 = 入宫盘（同 [世运卜卦]/[世运问判] 的既有口径：headless 无「问事时刻」这个交互输入）。
            return {
                "id": "mundanehorary",
                "chart": chart_response,
                "extra": {"mundaneType": "mundanehorary", "mhKind": payload.get("mhKind") or "war"},
                "state": {},
            }
        if mundane_type == "cycles":
            return {
                "id": "cycles",
                "chart": chart_response,  # cycles 分支不读盘面（isNatalLike=false），builder 只要求 chart 非空
                "extra": {"mundaneType": "cycles"},
                "state": self._mundane_cycles_state(),
            }
        return None

    def _mundane_cycles_state(self) -> dict[str, Any]:
        state: dict[str, Any] = {}
        try:
            gc = self._call_remote(
                "/astroextra/greatconj",
                {"startYear": self._MUNDANE_GC_DEFAULT_STATE["gcStart"], "endYear": self._MUNDANE_GC_DEFAULT_STATE["gcEnd"]},
            )
            # 上游 :768：`(r && r.conjunctions) ? r.conjunctions : (Array.isArray(r) ? r : [])`。
            conjs = gc.get("conjunctions") if isinstance(gc, dict) else (gc if isinstance(gc, list) else None)
            state.update(self._MUNDANE_GC_DEFAULT_STATE)
            state["gcResults"] = conjs if isinstance(conjs, list) else []
        except Exception as exc:  # noqa: BLE001
            _degrade("mundane cycles greatconj failed: %s", exc)
        start, end = self._MUNDANE_BB_DEFAULT_STATE["bbStart"], self._MUNDANE_BB_DEFAULT_STATE["bbEnd"]
        span = end - start
        step_months = 12 if span > 160 else (6 if span > 80 else 3)
        try:
            bb = self._call_remote(
                "/astroextra/barbault",
                {"startYear": start, "endYear": end, "stepMonths": step_months, "planets": list(self._MUNDANE_BB_DEFAULT_PLANETS)},
            )
            # 上游 :801：`bbData: (r && r.points) ? r : null`。
            if isinstance(bb, dict) and bb.get("points"):
                state.update(self._MUNDANE_BB_DEFAULT_STATE)
                state["bbData"] = bb
            else:
                _degrade("mundane cycles barbault: 响应无 points")
        except Exception as exc:  # noqa: BLE001
            _degrade("mundane cycles barbault failed: %s", exc)
        return state

    def _mundane_eclipse_job(
        self, mundane_type: str, *, chart_payload: dict[str, Any], ingress_time: str, zone: str
    ) -> dict[str, Any] | None:
        """日/月食判读卡的食盘。

        上游（MundaneMain.js:669 scanEvents → :688 useMoment）：/astroextra/ephemeris 扫出食表，用户点选一行 →
        extra.selectedMoment = 该行 localTime、eclipseTypeText = 该行 eclipseType，页面盘改排到食时刻，
        并以该时刻打 /astroextra/eclipsedetail 取食时长（:703 fetchEclipseDetail → state.eclipseDetail）。
        headless 选行口径：与 skill 既有 [日食图]/[月食图] 段同一次食——eclipsedetail 自「入宫时刻 − 2 日」向后
        搜到的第一次（astroextra.compute_eclipse_detail：jd_search = jd − 2），在 ephemeris 食表里取
        localTime ≥ 入宫 − 2 日的第一行。scanYear 取该食所在年（上游 scanYear 即扫出这次食的那一年）。
        """
        kind = "lunar" if mundane_type == "lunecl" else "solar"
        # 民用历墙钟轴（公元前历史纪年、1582 以前儒略历）：旧 strptime 对公元前入宫时刻直接失败 → 食盘卡缺席。
        ingress_ms = _civil_wall_ms_of_moment(f"{ingress_time or ''}".strip())
        if ingress_ms is None:
            _degrade("mundane %s card: 入宫时刻格式异常 %s", mundane_type, ingress_time)
            return None
        floor_ms = ingress_ms - 2 * 86400000
        floor_date = _civil_date_str_of_ms(floor_ms)
        end_date = _civil_date_str_of_ms(floor_ms + 400 * 86400000)  # 两个以上食季：日食 ≥2、月食 ≥1
        try:
            eph = self._call_remote(
                "/astroextra/ephemeris",
                {
                    # 请求体照上游 momentPipeline.fetchMundaneEvents（:79）。
                    "date": floor_date,
                    "time": "00:00:00",
                    "startDate": floor_date,
                    "endDate": end_date,
                    "startTime": "00:00:00",
                    "endTime": "23:59:59",
                    "zone": zone,
                    "lat": chart_payload.get("lat") or "0n00",
                    "lon": chart_payload.get("lon") or "0e00",
                    "gpsLat": chart_payload.get("gpsLat") if chart_payload.get("gpsLat") is not None else 0,
                    "gpsLon": chart_payload.get("gpsLon") if chart_payload.get("gpsLon") is not None else 0,
                    "includeTransits": False,
                },
            )
        except Exception as exc:  # noqa: BLE001
            _degrade("mundane %s card: /astroextra/ephemeris failed: %s", mundane_type, exc)
            return None
        rows = eph.get("eclipses") if isinstance(eph, dict) else None
        picked: tuple[str, dict[str, Any]] | None = None
        for ev in rows if isinstance(rows, list) else []:
            if not isinstance(ev, dict):
                continue
            # 上游 fetchMundaneEvents：kind = type==='lunar_eclipse' ? 'lunar' : 'solar'；localTime = datetime || date+time。
            ev_kind = "lunar" if ev.get("type") == "lunar_eclipse" else "solar"
            if ev_kind != kind:
                continue
            local_time = ev.get("datetime") or (f"{ev.get('date')} {ev.get('time')}" if ev.get("date") and ev.get("time") else ev.get("date"))
            ev_ms = _civil_wall_ms_of_moment(f"{local_time or ''}".strip())
            if ev_ms is None:
                continue
            if ev_ms >= floor_ms:
                picked = (f"{local_time}", ev)
                break
        if picked is None:
            _degrade("mundane %s card: 入宫后 400 日内未检索到%s食", mundane_type, "月" if kind == "lunar" else "日")
            return None
        local_time, ev = picked
        date_part, _, time_part = local_time.partition(" ")
        try:
            chart = self._call_remote("/chart", {**chart_payload, "date": date_part, "time": time_part, "ad": _ad_of_date(date_part)})
        except Exception as exc:  # noqa: BLE001
            _degrade("mundane %s card: eclipse chart failed: %s", mundane_type, exc)
            return None
        state: dict[str, Any] = {}
        try:
            detail = self._call_remote(
                "/astroextra/eclipsedetail",
                {
                    "date": date_part,
                    "time": time_part or "00:00:00",
                    "zone": zone,
                    "lat": chart_payload.get("lat"),
                    "lon": chart_payload.get("lon"),
                    "eclipseKind": kind,
                },
            )
            # 上游 :710：`eclipseDetail: (r && !r.err) ? r : null`。
            if isinstance(detail, dict) and not detail.get("err"):
                state["eclipseDetail"] = detail
        except Exception as exc:  # noqa: BLE001
            _degrade("mundane %s card: eclipsedetail failed: %s", mundane_type, exc)
        return {
            "id": mundane_type,
            "chart": chart,
            "extra": {
                "mundaneType": mundane_type,
                "selectedMoment": local_time,
                "eclipseKind": kind,
                "eclipseTypeText": ev.get("eclipseType"),
                # 上游 scanYear 是年份数（clampYear）；取食时刻的串首带符号年（leadingYearOf；旧 [:4] 对公元前 / 五位年取错）
                "scanYear": _leading_year_of(local_time),
            },
            "state": state,
        }
