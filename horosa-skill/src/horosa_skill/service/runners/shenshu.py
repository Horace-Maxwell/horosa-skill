"""神数 runner（ShenshuRunners）：十四种神数经 _run_shenshu_tool，及五兆 / 演禽 / 仙禽 / 皇极经世辅助。"""
from __future__ import annotations

from typing import Any

from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.errors import (
    HorosaSkillError,
    ToolTransportError,
    ToolValidationError,
    bilingual,
)
from horosa_skill.service import _clock
from horosa_skill.service._common import _human_scalar, _replace_snapshot_line, _replace_snapshot_section
from horosa_skill.service._context import _degrade
from horosa_skill.service.endpoints import _SHENSHU_ENDPOINTS
from horosa_skill.service.options_cn import (
    _SHENSHU_GENERIC_KEYS,
    _SHENSHU_PROMOTABLE_OPTION_KEYS,
    _WANGJI_DIRECTION_ALIASES,
    _WANGJI_DIRECTIONS,
    _WANGJI_TRIGRAM_ALIASES,
    _WANGJI_TRIGRAMS,
    _WANGJI_XINYI_METHODS,
    _WUZHAO_CALC_DEFAULTS,
    _append_replay_note,
    _day_boundary_switches,
    _split_birth_ymdhm,
    _upstream_cast_time_seed,
)
from horosa_skill.true_random import cast_record, is_entropy_seed, new_seed_for, random_below, seed_display_text
from horosa_skill.shenshu_options import SHENSHU_OPTION_KNOBS, resolve_shenshu_options



# 审计 O-14：两门神数的后端把 dict / dict 列表直接交给 row()，正文印成「palace_index：2；branch：2；branch_name：寅…」
# 「name：蛟吞日月；ganzhi：壬午、name：…」。按响应里的结构化值重排这几行（值一字不改，只换排版）；上游 bug 已记，AGENTS §10 登记。
_XIANQIN_LITERATURE_ROWS = (("贵格", "gui"), ("贱格", "jian"), ("福禄上格", "fulu"), ("贫贱下命", "pinjian"))


def _xianqin_literature_text(items: Any) -> str | None:
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        return None
    parts = []
    for item in items:
        name = f"{item.get('name') or ''}".strip()
        extra = "；".join(f"{item.get(k)}".strip() for k in ("ganzhi", "stars", "condition") if f"{item.get(k) or ''}".strip())
        if name:
            parts.append(f"{name}（{extra}）" if extra else name)
    return "、".join(parts) or "—"


def _qizheng_dasha_text(current: Any) -> str | None:
    if not isinstance(current, dict) or not current.get("palace_name"):
        return None
    span = f"{current.get('start_age')}-{current.get('end_age')}岁"
    years = f"{current.get('start_year')}–{current.get('end_year')} 年" if current.get("start_year") is not None else ""
    if current.get("years") is not None:
        years = f"{years}，共 {current.get('years')} 年" if years else f"共 {current.get('years')} 年"
    head = "｜".join(f"{v}" for v in (current.get("palace_name"), span, current.get("lord"), current.get("branch_name")) if v)
    return f"{head}（{years}）" if years else head


def _undict_shenshu_rows(key: str, response: Any, snapshot_text: str) -> str:
    if not isinstance(response, dict):
        return snapshot_text
    if key == "qizhengkin":
        dasha = (response.get("qizheng") or {}).get("dasha") if isinstance(response.get("qizheng"), dict) else None
        text = _qizheng_dasha_text((dasha or {}).get("current") if isinstance(dasha, dict) else None)
        if text:
            snapshot_text = _replace_snapshot_line(snapshot_text, "年限", "当前大限", text)
    if key == "xianqin" and isinstance(response.get("literature"), dict):
        for label, field in _XIANQIN_LITERATURE_ROWS:
            text = _xianqin_literature_text(response["literature"].get(field))
            if text:
                snapshot_text = _replace_snapshot_line(snapshot_text, "情性与格局", label, text)
    return snapshot_text

class ShenshuRunners:
    def _run_shenshu_tool(self, payload: dict[str, Any], key: str) -> dict[str, Any]:
        # 神数 family (wangji / wuzhao / taixuan / jingjue / shenyishu + 9 kinastro-*): each is a kentang engine
        # mounted on the chart service that returns a backend-built `snapshot` text whose [小节] headers already
        # match 星阙's aiExport preset. The skill splits date/time into year/month/day/hour/minute, forwards the
        # 晚子时 switches + gender/place, and routes technique knobs through the shenshu_options key table
        # (typed, per tool; unknown keys are receipted in data.params_ignored instead of silently dropped).
        endpoint = _SHENSHU_ENDPOINTS[key]
        parts = _split_birth_ymdhm(payload)
        # 旧 options 是整包 update 进请求体，有人把 gender/zone 之类核心键写在 options 里——这类键不是技法旋钮，
        # 但也不该因为换了键表就被当成「未识别」丢掉：顶层没给时提升为顶层键（顶层已给则以顶层为准）。
        raw_options = payload.get("options") if isinstance(payload.get("options"), dict) else None
        promoted: dict[str, Any] = {}
        if raw_options:
            technique_knobs = SHENSHU_OPTION_KNOBS.get(key, {})
            promoted = {
                k: v for k, v in raw_options.items()
                if k in _SHENSHU_PROMOTABLE_OPTION_KEYS and k not in technique_knobs and payload.get(k) is None and v is not None
            }
            if promoted:
                payload = {**payload, **promoted, "options": {k: v for k, v in raw_options.items() if k not in promoted}}
        knobs = resolve_shenshu_options(
            key, payload, set(TOOL_DEFINITIONS[key].input_model.model_fields), set(_SHENSHU_GENERIC_KEYS)
        )
        if promoted:
            knobs.applied = sorted(set(knobs.applied) | set(promoted))
        remote_payload: dict[str, Any] = {
            **parts,
            "date": payload.get("date"),
            "time": payload.get("time"),
            "after23NewDay": payload.get("after23NewDay", 1),
            "lateZiHourUseNextDay": payload.get("lateZiHourUseNextDay", 1),
        }
        # kinastro 族读 gender + zone（四柱权威口径按时区定气/立春界）+ 经纬；策天/七政另读地名 pos
        # （上游 kinAstroFieldsSync.parseFieldsDateTime 同集下发，:56-83）。后端不读的键无害。
        for extra in ("gender", "lat", "lon", "gpsLat", "gpsLon", "zone", "pos"):
            if payload.get(extra) is not None:
                remote_payload[extra] = payload.get(extra)
        remote_payload.update(knobs.backend)
        settings_applied: dict[str, dict[str, Any]] = {}
        replay_note = ""
        result_extra: dict[str, Any] = {}
        if key in {"jingjue", "taixuan"}:
            # 起筮种子（v3.15.0 同上游页面）：缺省 seedMode=random → 当场取 32 字节系统随机记录 tr1-…（页面 defaultSeed），
            # 后端逐位读它定每一次分策、原样回传；time_seed → 起课时刻 yyyyMMddHHmm mod 1e9（上游挂载重算同口径，同刻同卦）；
            # 显式 seed（整数，0 合法 —— 挂载自检 F-23；或回传的 tr1- 记录）= 手动档原样重开。
            explicit = knobs.backend.get("seed")
            seed_mode = knobs.skill.get("seedMode") or "random"
            if explicit is not None:
                seed = explicit if is_entropy_seed(explicit) else int(explicit) % 1_000_000_000
                label = "起筮种子（显式，原样重开）"
            elif seed_mode == "time_seed":
                seed = _upstream_cast_time_seed(parts)
                label = "起筮种子（起课时刻 yyyyMMddHHmm mod 1e9 派生）"
            else:
                seed = new_seed_for(key)
                label = "起筮种子（系统随机源，真随机记录）"
            result_extra["cast"] = cast_record("seed" if explicit is not None else seed_mode, random=explicit is None and seed_mode != "time_seed",
                                               replay={"options": {"seed": seed}})
            remote_payload["seed"] = seed
            result_extra["seed"] = seed
            settings_applied["seed"] = {"label": label, "value": seed_display_text(seed) if is_entropy_seed(seed) else seed}
        elif key == "wangji" and remote_payload.get("historyYear") == "random":
            # 皇极「随机历史年」（上游 HuangJiMain.randomHistoryYear）：1900–2100 等概率，系统随机源；掷出的年随结果回传。
            remote_payload["historyYear"] = 1900 + random_below(201)
            result_extra["cast"] = cast_record("random_history_year", random=True, replay={"options": {"historyYear": remote_payload["historyYear"]}})
            settings_applied["historyYear"] = {"label": "所推之年（随机历史年，系统随机源）", "value": remote_payload["historyYear"]}
        elif key == "wuzhao":
            remote_payload, replay_note = self._wuzhao_calc_payload(payload, parts, knobs.backend, remote_payload, settings_applied, result_extra)
        elif key == "cetian":
            # 流年年份缺省=「今年」（webcetiansrv.py:496-500 datetime.now()）：同一盘明年再算结果就变。
            # 书法（默认）下显式钉住当年并记进技法卡，读者看得到这份结果是按哪一年起的流年。
            if remote_payload.get("method", "book") == "book" and "liunianYear" not in remote_payload:
                remote_payload["liunianYear"] = _clock.now().year
                settings_applied["liunianYear"] = {"label": "流年年份（未指定→取今年）", "value": remote_payload["liunianYear"]}
        elif key == "qizhengkin":
            # 大运所在年缺省=「今年」（webqizhengkinsrv.py:546 datetime.now()）：同 cetian，钉住并入卡。
            if "qizhengKinCurrentYear" not in remote_payload and "currentYear" not in remote_payload:
                remote_payload["qizhengKinCurrentYear"] = _clock.now().year
                settings_applied["qizhengKinCurrentYear"] = {
                    "label": "大运所在年（未指定→取今年）", "value": remote_payload["qizhengKinCurrentYear"],
                }
            if remote_payload.get("qizhengKinTransitMode") == "now" or remote_payload.get("transitMode") == "now":
                settings_applied["qizhengKinTransitMode"] = {"label": "过运（此刻：随调用时刻变化）", "value": "now"}
        response = self._call_remote(endpoint, remote_payload)
        if isinstance(response, dict) and response.get("ResultCode") not in (None, 0):
            raise ToolValidationError(
                f"{key} 引擎返回错误：{response.get('Result')}",
                code="tool.shenshu_engine_error",
                details={"technique": key, "result": response.get("Result")},
            )
        raw_snapshot = response.get("snapshot") if isinstance(response, dict) else None
        snapshot_text = f"{raw_snapshot}".strip() if raw_snapshot else ""
        if not snapshot_text:
            # A reachable engine that returns no `snapshot` is an OLD chart-service build: the 神数 srv
            # only emits `snapshot` once the current source's build_snapshot() is present. Fail loudly
            # instead of returning a hollow export, so the agent can tell the user to update 星阙 / use
            # the bundled runtime (rather than silently producing an empty reading).
            raise ToolTransportError(
                f"{key} 引擎未返回 snapshot（命中的图表服务构建过旧，缺该神数的 snapshot 输出）。"
                "请更新 星阙 App 或改用 skill 自带的离线 runtime。",
                code="transport.shenshu_snapshot_unavailable",
                details={"technique": key, "endpoint": endpoint, "engine": response.get("engine") if isinstance(response, dict) else None},
            )
        snapshot_text = _undict_shenshu_rows(key, response, snapshot_text)
        if replay_note:
            # 上游 buildWuZhaoSnapshotForFields：回落干支起例后复现说明并入 [揲筮] 段（:394）。
            snapshot_text = _append_replay_note(snapshot_text, "揲筮", replay_note)
        cast = result_extra.get("cast")
        if key == "wuzhao" and isinstance(cast, dict) and cast.get("random") and not cast.get("replay"):
            # 折竹 / 唐法随机分爻的重开配方（上游 wuzhaoReplayOptionsFromPan）：传回这几个键即逐位同兆。
            replay = _wuzhao_replay_options(response, (settings_applied.get("mode") or {}).get("value"))
            if replay:
                result_extra["replay_options"] = replay
                cast["replay"] = {"options": {k: v for k, v in replay.items() if k != "replayNote"}}
        # 铁板「框架推演层」五段：kinastro 后端出盘面与条文，刻分/三元/八卦滚这层是上游前端按四柱
        # 本地推演的。后端响应里的 pillars 即入参，失败只是这几段不出。
        if key == "tieban":
            try:
                framework = self.js_client.run(
                    "tieban_framework",
                    {
                        "pillars": (response or {}).get("pillars") if isinstance(response, dict) else None,
                        "birthYear": parts.get("year"),
                        "gender": payload.get("gender"),
                        # 上游 KinAstroMain.buildKinAstroSnapshotForFields（:329-346）读 tiebanSchool /
                        # tiebanKeSystem / tiebanKe，缺省 south / qing8 / 1（初刻）——考刻是占者核六亲后手定，
                        # 不由钟点换算（sync311 F8：此前读 options.school/keSystem、刻按时分自算，皆非上游口径）。
                        **{k: v for k, v in knobs.skill.items() if k in {"tiebanSchool", "tiebanKeSystem", "tiebanKe"}},
                    },
                )
                extra = f"{(framework or {}).get('text') or ''}".strip()
                fw_data = (framework or {}).get("data") if isinstance(framework, dict) else None
                if isinstance(fw_data, dict) and fw_data.get("ok") is False:
                    _degrade("tieban framework snapshot not produced: %s", (fw_data.get("error") or {}).get("message"))
                if extra:
                    # 上游 `${text}\n\n${suffix}`（KinAstroMain.js:325）：框架段与盘面之间空一行。
                    snapshot_text = f"{snapshot_text}\n\n{extra}".strip()
            except Exception as exc:  # noqa: BLE001 — 富化失败不影响盘面
                _degrade("tieban framework snapshot failed: %s", exc)
        # 演禽「演法」五段（流派/起禽/择日/占卜/投胎）：kinastro 后端不产，它们是上游前端按出生四数
        # 本地推演的（yanqin/yanqinSnapshot.js），与盘面互补。追加在后端快照之后。
        if key == "xianqin":
            snapshot_text = self._append_yanqin_yanfa(payload, parts, knobs, snapshot_text, settings_applied)
        result: dict[str, Any] = {
            "engine": response.get("engine") if isinstance(response, dict) else key,
            "raw": response,
            **result_extra,
        }
        # [判词原文]（v0.33.0 批 I-5，/cetian/texts）：textKey=list 出目录 / all 全库 / <键> 单篇。条件段。
        if key == "cetian" and payload.get("textKey"):
            text_key = str(payload.get("textKey")).strip()
            texts_raw = self._call_remote("/cetian/texts", {})
            texts = (texts_raw or {}).get("texts") if isinstance(texts_raw, dict) else None
            if not isinstance(texts, dict) or not texts:
                raise ToolTransportError(
                    "策天判词库端点返回了意外形状。",
                    code="tool.cetian_texts_failed",
                    details={"endpoint": "/cetian/texts"},
                )
            result["texts"] = texts if text_key in ("all",) else {k: texts[k] for k in texts if text_key in ("list", k)}
            text_lines: list[str] = []
            if text_key == "list":
                text_lines.append(f"判词库 {len(texts)} 篇（textKey 取单篇）：")
                for k, v in texts.items():
                    n_chars = sum(len(f"{s.get('body') or ''}") for s in (v.get("sections") or []) if isinstance(s, dict))
                    text_lines.append(f"{k}：{v.get('title')}（{n_chars} 字）")
            else:
                picked = texts if text_key == "all" else ({text_key: texts[text_key]} if text_key in texts else {})
                if not picked:
                    raise ToolValidationError(
                        f"判词库无此篇：{text_key}（可用键：{'、'.join(texts.keys())}；或 textKey=list 看目录）。",
                        code="tool.cetian_text_unknown_key",
                        details={"available": sorted(texts.keys())},
                    )
                for k, v in picked.items():
                    text_lines.append(f"《{v.get('title')}》（{k}）")
                    for s in v.get("sections") or []:
                        if isinstance(s, dict):
                            subtitle = f"{s.get('subtitle') or ''}".strip()
                            if subtitle:
                                text_lines.append(f"· {subtitle}")
                            text_lines.append(f"{s.get('body') or ''}".strip())
            if snapshot_text and text_lines:
                snapshot_text = f"{snapshot_text}\n\n[判词原文]\n" + "\n".join(text_lines)
        if key == "wangji":
            snapshot_text = self._apply_wangji_xinyi(payload, parts, snapshot_text, result)
        result["params_applied"] = knobs.applied
        result["params_ignored"] = knobs.ignored
        if knobs.ignored:
            # 口径回执（AGENTS §5.12）：认不出的键不转发、原样回执，并在 envelope.warnings 说一声。
            result["_warnings"] = [
                f"{key} 未识别的旋钮已忽略（未转发后端）：{'、'.join(knobs.ignored)}；键表见 "
                f"horosa_agent_guidance(tool_name=\"{key}\").options_keys。"
            ]
        if settings_applied:
            result["settings_applied"] = settings_applied
        result["snapshot_text"] = snapshot_text
        result["export_snapshot"] = self._augment_export_payload(technique=key, snapshot_text=snapshot_text)
        return result

    def _wuzhao_calc_payload(
        self,
        payload: dict[str, Any],
        parts: dict[str, int],
        backend_knobs: dict[str, Any],
        remote_payload: dict[str, Any],
        settings_applied: dict[str, dict[str, Any]],
        result_extra: dict[str, Any],
    ) -> tuple[dict[str, Any], str]:
        """五兆计算键（sync311 F3/F4）：镜像上游 buildWuZhaoSnapshotForFields（WuZhaoMain.js:326-354）。

        * 11 个计算键全量下发（缺省同上游 DEFAULT_OPTIONS）；
        * 性别：五兆后端只认 'male'/'female'（webwuzhaosrv.py:497-499）——顶层 gender 1/0 与 options.gender
          （输入归一化会把嵌套 'male' 改成 1）一律归回 'male'/'female'，此前恒被后端清成「未指定」；
        * 随机诸式（v3.15.0 同上游页面：系统随机源，每次新兆）：敦煌揲筮 / 以钱代筮（自动掷）后端按 castSeed 定兆——缺省当场取
          64 字节真随机记录（WuZhaoMain newCastSeed），显式 castSeed（整数 / tr1- 记录）原样重开；折竹（日/时/分干起盘）与唐法揲筮的
          随机分爻后端当场取系统随机、不吃种子 —— 不再像上游「挂载重算存档」那样回落干支起例（那条路拿不到存档兆数；skill 是新起一卦），
          起出后照上游 wuzhaoReplayOptionsFromPan 把兆数写成重开配方回传（data.replay_options）。
        """
        calc = {**_WUZHAO_CALC_DEFAULTS}
        calc.update({k: v for k, v in backend_knobs.items() if k in _WUZHAO_CALC_DEFAULTS})
        if "gender" not in backend_knobs:
            gender = payload.get("gender")
            calc["gender"] = {1: "male", 0: "female", "1": "male", "0": "female"}.get(gender, "") if gender is not None else ""
        mode = calc["mode"]
        replay_note = ""
        result_extra["cast"] = cast_record(mode, random=False, replay={"options": {"mode": mode}})   # 确定性起例；随机诸式下面覆盖
        if mode in {"day", "hour", "minute", "tang"} and not calc["manual"]:
            result_extra["cast"] = cast_record(mode, random=True, replay={})   # 分爻在后端当场取系统随机；配方在回包后填
        out = {k: v for k, v in remote_payload.items() if k != "castSeed"}
        out.update(calc)
        random_cast = calc["mode"] == "dunhuang" or (calc["mode"] == "qian" and bool(calc["qianAuto"]))
        if random_cast:
            explicit = backend_knobs.get("castSeed")
            cast_seed = explicit if explicit is not None else new_seed_for("wuzhao")
            out["castSeed"] = cast_seed
            result_extra["castSeed"] = cast_seed
            result_extra["cast"] = cast_record(calc["mode"] if explicit is None else "seed", random=explicit is None,
                                               replay={"options": {"mode": calc["mode"], "castSeed": cast_seed}})
            settings_applied["castSeed"] = {
                "label": "起兆种子" + ("（显式，原样重开）" if explicit is not None else "（系统随机源，真随机记录）"),
                "value": seed_display_text(cast_seed),
            }
        settings_applied["mode"] = {"label": "五兆起例", "value": calc["mode"]}
        return out, replay_note

    def _append_yanqin_yanfa(
        self,
        payload: dict[str, Any],
        parts: dict[str, int],
        knobs: Any,
        snapshot_text: str,
        settings_applied: dict[str, dict[str, Any]],
    ) -> str:
        """演禽「演法」五段（sync311 F7/F17）。

        * 流派 + 六开关（school/woBi/xunOffset/monthVerse/huoYaoVariant/sansuo/qinWuxing）逐次调用传入
          （上游经 yanqinStore 全局单例；headless 无 localStorage，此前恒池本理默认、六开关不可设）；
        * 农历月：上游无头路径经 deriveLocalNongliAsync 取权威 monthInt 注入（KinAstroMain.js:351-359）——
          这里同样走 /nongli/time（钟表时，演禽不吃真太阳时），调用方显式 lunarMonth 优先；取数失败
          只降级为引擎内置农历换算并在 warnings 说明（域外年份会退公历月）。
        """
        lunar_month = knobs.backend.get("lunarMonth")
        if lunar_month is None:
            lunar_month = self._xianqin_lunar_month(payload)
        yanfa_payload: dict[str, Any] = {
            "year": parts.get("year"),
            "month": parts.get("month"),
            "day": parts.get("day"),
            "hour": parts.get("hour", 0),
            **({"lunarMonth": lunar_month} if lunar_month is not None else {}),
            **knobs.skill,
        }
        try:
            yanfa = self.js_client.run("yanqin_yanfa", yanfa_payload)
        except Exception as exc:  # noqa: BLE001 — 富化失败不影响盘面
            _degrade("yanqin 演法 snapshot failed: %s", exc)
            return snapshot_text
        data = (yanfa or {}).get("data") if isinstance(yanfa, dict) else None
        if isinstance(data, dict) and data.get("ok") is False:
            error = data.get("error") or {}
            if error.get("code") != "invalid_setting":
                _degrade("yanqin 演法 snapshot failed: %s", error.get("message") or error)
                return snapshot_text
            raise ToolValidationError(
                bilingual(
                    f"演禽演法设置不被引擎接受：{error.get('message') or '未知'}",
                    f"yanqin yanfa setting rejected by the engine: {error.get('message') or 'unknown'}",
                ),
                code="tool.yanqin_invalid_setting",
                details={"error": error},
            )
        if isinstance(data, dict) and isinstance(data.get("settings"), dict):
            settings_applied["yanqinSchool"] = {"label": "演法流派", "value": data["settings"].get("school")}
        if lunar_month is not None:
            settings_applied["yanqinLunarMonth"] = {"label": "演法农历月", "value": lunar_month}
        extra = f"{(yanfa or {}).get('text') or ''}".strip()
        # 上游 `text + '\n\n' + yanfa`（KinAstroMain.js:338）：演法段与盘面之间空一行。
        return f"{snapshot_text}\n\n{extra}".strip() if extra else snapshot_text

    def _xianqin_lunar_month(self, payload: dict[str, Any]) -> int | None:
        try:
            nongli = self._call_remote(
                "/nongli/time",
                {
                    "date": payload.get("date"),
                    "time": payload.get("time"),  # 缺时刻在入口就拒（审计 F08），这里不再按 00:00 兜
                    # 上游域外农历远程桥缺时地时的兜底（divinationTimeDraft.deriveNongliRemote :306-307）。
                    "zone": payload.get("zone") or "+08:00",
                    "lat": payload.get("lat") or "0n00",
                    "lon": payload.get("lon") or "0e00",
                    # 演禽只取生辰原始钟表时刻（techniqueMountSettings xianqin 注：ken 引擎不消费真太阳时）：
                    # 缺经纬时若按真太阳时，0e00 会把钟点整体拨 8 小时、跨日换月。
                    "timeAlg": 1,
                    **_day_boundary_switches(payload),
                },
            )
        except HorosaSkillError as exc:
            _degrade("演禽演法农历月经 /nongli/time 取数失败（%s）：月禽/投胎改按引擎内置农历换算", exc)
            return None
        month = nongli.get("monthInt") if isinstance(nongli, dict) else None
        if isinstance(month, int) and 1 <= month <= 12:
            return month
        _degrade("演禽演法农历月：/nongli/time 未返回 monthInt（%r），月禽/投胎改按引擎内置农历换算", month)
        return None

    def _apply_wangji_xinyi(
        self, payload: dict[str, Any], parts: dict[str, int], snapshot_text: str, result: dict[str, Any]
    ) -> str:
        """皇极经世 [心易发微]（sync311 F15）：镜像上游 buildHuangJiSnapshotForFields（HuangJiMain.js:161-198）。

        上游挂载缺省起心易 = datetime（techniqueMountSettings huangji.xinyiMethod default 'datetime'），
        所选之法经 /wangji/xinyi 起卦后**就放进 [心易发微]**（buildSnapshotText :117-122，逐键 `键：值`）；
        'none' = 不算心易、整段不出。后端 /pan 自带的 [心易发微] 是把 {method,result,sections} 包装整体
        str() 出来的（「method：datetime / result：本卦：…」），上游前端从不采用它——这里整段替换。
        入参全量照上游：upperNum 5 / lowerNum 10 / upperStrokes 5 / lowerStrokes 8 / objectGua 離 / direction 南，
        时辰=盘面时辰（xinyiHour 可覆写）；卦名/方位收简体并归一到后端唯一认得的繁体。
        """
        method = f"{payload.get('xinyiMethod') or 'datetime'}".strip() or "datetime"
        if method not in _WANGJI_XINYI_METHODS:
            raise ToolValidationError(
                bilingual(
                    f"心易起卦法 {method!r} 不存在（可选：{'/'.join(_WANGJI_XINYI_METHODS)}）。",
                    f"Unknown xinyiMethod {method!r} (choose one of {'/'.join(_WANGJI_XINYI_METHODS)}).",
                ),
                code="tool.wangji_invalid_xinyi_method",
                details={"xinyiMethod": method, "allowed": list(_WANGJI_XINYI_METHODS)},
            )
        if method == "none":
            return _replace_snapshot_section(snapshot_text, "心易发微", None)
        object_gua = f"{payload.get('objectGua') or '離'}".strip()
        object_gua = _WANGJI_TRIGRAM_ALIASES.get(object_gua, object_gua)
        direction = f"{payload.get('xinyiDirection') or '南'}".strip()
        direction = _WANGJI_DIRECTION_ALIASES.get(direction, direction)
        if object_gua not in _WANGJI_TRIGRAMS or direction not in _WANGJI_DIRECTIONS:
            raise ToolValidationError(
                bilingual(
                    f"心易方位法入参不合法：objectGua={object_gua!r}（可选 {'/'.join(_WANGJI_TRIGRAMS)}），"
                    f"xinyiDirection={direction!r}（可选 {'/'.join(_WANGJI_DIRECTIONS)}；简体亦可）。",
                    "Invalid xinyi direction-method input (objectGua / xinyiDirection; simplified forms are accepted).",
                ),
                code="tool.wangji_invalid_xinyi_direction",
                details={"objectGua": object_gua, "xinyiDirection": direction,
                         "allowed_objectGua": list(_WANGJI_TRIGRAMS), "allowed_direction": list(_WANGJI_DIRECTIONS)},
            )

        def _num(field: str, default: int) -> Any:
            value = payload.get(field)
            return default if value is None else value

        xinyi_remote: dict[str, Any] = {
            **parts,
            "date": payload.get("date"),
            "time": payload.get("time"),
            "method": method,
            "upperNum": _num("upperNum", 5),
            "lowerNum": _num("lowerNum", 10),
            "upperStrokes": _num("upperStrokes", 5),
            "lowerStrokes": _num("lowerStrokes", 8),
            "objectGua": object_gua,
            "direction": direction,
        }
        if payload.get("xinyiHour") is not None:
            xinyi_remote["hour"] = payload.get("xinyiHour")
        try:
            # ⚠ _unwrap_result 会连剥 {Result:{…}} 与内层小写 {result:{…}} 两层 —— 这里拿到的
            # 直接就是卦面 dict（本卦/變卦/動爻/體用…），外层的 method/sections 已被剥掉。
            xinyi = self._call_remote("/wangji/xinyi", xinyi_remote)
        except HorosaSkillError as exc:
            if payload.get("xinyiMethod"):
                raise
            # 缺省（datetime）心易失败不拖主盘（上游 :195 同律），但不静默：段撤掉 + warnings 说明。
            _degrade("皇极经世缺省心易（datetime）起卦失败：%s", exc)
            return _replace_snapshot_section(snapshot_text, "心易发微", None)
        if not isinstance(xinyi, dict) or not xinyi or "本卦" not in xinyi:
            if payload.get("xinyiMethod"):
                raise ToolTransportError(
                    "心易起卦端点返回了意外形状。",
                    code="tool.wangji_xinyi_failed",
                    details={"endpoint": "/wangji/xinyi", "method": method,
                             "keys": sorted(xinyi.keys()) if isinstance(xinyi, dict) else type(xinyi).__name__},
                )
            _degrade("皇极经世缺省心易（datetime）起卦返回意外形状（%s）", type(xinyi).__name__)
            return _replace_snapshot_section(snapshot_text, "心易发微", None)
        result["xinyi"] = {"method": method, "result": xinyi}
        body = [f"{k}：{_human_scalar(v)}" for k, v in xinyi.items()]
        return _replace_snapshot_section(snapshot_text, "心易发微", body)


def _wuzhao_replay_options(pan: Any, mode: Any) -> dict[str, Any] | None:
    """= 上游 WuZhaoMain.wuzhaoReplayOptionsFromPan（v3.15.0，逐分支移植；tests/test_true_random_casting.py 对上游源对拍）：
    随机起兆后把六位兆数写成重开配方 —— 折竹 / 唐法 → manual + manualSplits；敦煌 → zhushu + zhaoNums；
    以钱代筮 → qianAuto=false + qianThrows（逐掷阳面数，取不到则 zhushu）。材料不全 → None。"""
    positions = pan.get("positions") if isinstance(pan, dict) else None
    if not isinstance(positions, list) or len(positions) != 6:
        return None
    nums: list[int] = []
    for position in positions:
        try:
            number = float(position.get("number")) if isinstance(position, dict) else float("nan")
        except (TypeError, ValueError):
            return None
        if not (number == number and 1 <= number <= 5):   # NaN / 越界 → 不成配方
            return None
        nums.append(int(number) if number == int(number) else number)
    if mode == "qian":
        detail = pan.get("shifaDetail") if isinstance(pan.get("shifaDetail"), dict) else {}
        rows = detail.get("rows") if isinstance(detail.get("rows"), list) else None
        def _yang(row: Any) -> float | None:
            try:
                return float(row.get("yang")) if isinstance(row, dict) else None
            except (TypeError, ValueError):
                return None
        if rows and len(rows) == 6 and all(_yang(r) is not None for r in rows):
            return {"qianAuto": False, "qianThrows": [max(0, min(4, round(_yang(r)))) for r in rows], "replayNote": "按存档逐掷阳面数复现(以钱代筮)"}
        return {"mode": "zhushu", "zhaoNums": nums, "replayNote": "按存档六位兆数直输复现(起盘方式行显示为直输五兆数)"}
    if mode in ("day", "hour", "minute", "tang"):
        return {"manual": True, "manualSplits": nums, "replayNote": "按存档六位兆数复现(揲筮段显示为手动复现)"}
    if mode == "dunhuang":
        return {"mode": "zhushu", "zhaoNums": nums, "replayNote": "按存档六位兆数直输复现(起盘方式行显示为直输五兆数)"}
    return None
