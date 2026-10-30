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
from horosa_skill.service._common import _human_scalar, _replace_snapshot_section
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
    _WUZHAO_MODE_LABELS,
    _append_replay_note,
    _day_boundary_switches,
    _split_birth_ymdhm,
    _upstream_cast_time_seed,
)
from horosa_skill.shenshu_options import SHENSHU_OPTION_KNOBS, resolve_shenshu_options


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
            # 🔴 起筮种子（sync311 F1/F2）：上游无头挂载按起课时刻 yyyyMMddHHmm mod 1e9 派生（同刻同卦），
            # 显式 seed 覆盖（0 合法，挂载自检 F-23）。此前 skill 不发 seed：荆诀后端 random.randint 真随机、
            # 太玄后端缺省只到小时（yyyyMMddHH）——同一时刻两次调用得不同卦 / 同一小时内恒同卦。
            explicit = knobs.backend.get("seed")
            seed = int(explicit) % 1_000_000_000 if explicit is not None else _upstream_cast_time_seed(parts)
            remote_payload["seed"] = seed
            result_extra["seed"] = seed
            settings_applied["seed"] = {
                "label": "起筮种子" + ("（显式）" if explicit is not None else "（起课时刻 yyyyMMddHHmm mod 1e9 派生）"),
                "value": seed,
            }
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
        if replay_note:
            # 上游 buildWuZhaoSnapshotForFields：回落干支起例后复现说明并入 [揲筮] 段（:394）。
            snapshot_text = _append_replay_note(snapshot_text, "揲筮", replay_note)
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
                    # 上游 `${text}\n\n${suffix}`（KinAstroMain.js:346）：框架段与盘面之间空一行。
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
        """五兆计算键（sync311 F3/F4）：镜像上游 buildWuZhaoSnapshotForFields（WuZhaoMain.js:368-396）。

        * 11 个计算键全量下发（缺省同上游 DEFAULT_OPTIONS）；
        * 性别：五兆后端只认 'male'/'female'（webwuzhaosrv.py:497-499）——顶层 gender 1/0 与 options.gender
          （输入归一化会把嵌套 'male' 改成 1）一律归回 'male'/'female'，此前恒被后端清成「未指定」；
        * 随机诸式：敦煌揲筮 / 以钱代筮（自动掷）后端按 castSeed 定兆（v3.11「按存档兆数复现」同一枚种子）——
          缺省由起课时刻派生（同刻同兆，与灵棋经/太玄/荆诀同一「以时起卦」语义），显式 castSeed 覆盖；
        * 折竹（日/时/分干起盘）与唐法揲筮的随机分爻后端不吃种子，无头不可复现：未开 manual 手动分爻复现时
          照上游挂载回落干支起例，并把上游原句「复现说明」并入 [揲筮] 段 + envelope 警告（不静默）。
        """
        calc = {**_WUZHAO_CALC_DEFAULTS}
        calc.update({k: v for k, v in backend_knobs.items() if k in _WUZHAO_CALC_DEFAULTS})
        if "gender" not in backend_knobs:
            gender = payload.get("gender")
            calc["gender"] = {1: "male", 0: "female", "1": "male", "0": "female"}.get(gender, "") if gender is not None else ""
        mode = calc["mode"]
        replay_note = ""
        if mode in {"day", "hour", "minute", "tang"} and not calc["manual"]:
            replay_note = (
                # 原句逐字取自上游 buildWuZhaoSnapshotForFields（v3.13.0 WuZhaoMain.js 措辞：「把「揲筮模式」设为手动复现」
                # 「已按干支起盘」；v3.11 是「开启「手动分爻复现」」「已按干支起例」）。
                f"挂载无法复现随机起兆(所选「{_WUZHAO_MODE_LABELS[mode]}」需把「揲筮模式」设为手动复现并填分爻数;存档亦无兆数)"
                "→ 已按干支起盘"
            )
            calc["mode"] = "ganzhi"
            _degrade(
                "五兆 %s 在无头起课下不可复现（后端随机分爻不吃种子）：已按上游挂载口径回落干支起例；"
                "要该法请传 options.manual=true + manualSplits（六数）", mode,
                note=f"五兆「{_WUZHAO_MODE_LABELS[mode]}」无 manual 手动分爻时不可复现，已回落干支起例（见 [揲筮] 复现说明）。",
            )
        out = {k: v for k, v in remote_payload.items() if k != "castSeed"}
        out.update(calc)
        random_cast = calc["mode"] == "dunhuang" or (calc["mode"] == "qian" and bool(calc["qianAuto"]))
        if random_cast:
            explicit = backend_knobs.get("castSeed")
            cast_seed = int(explicit) if explicit is not None else _upstream_cast_time_seed(parts)
            out["castSeed"] = cast_seed
            result_extra["castSeed"] = cast_seed
            settings_applied["castSeed"] = {
                "label": "起兆种子" + ("（显式）" if explicit is not None else "（起课时刻 yyyyMMddHHmm mod 1e9 派生）"),
                "value": cast_seed,
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
        # 上游 `text + '\n\n' + yanfa`（KinAstroMain.js:359）：演法段与盘面之间空一行。
        return f"{snapshot_text}\n\n{extra}".strip() if extra else snapshot_text

    def _xianqin_lunar_month(self, payload: dict[str, Any]) -> int | None:
        try:
            nongli = self._call_remote(
                "/nongli/time",
                {
                    "date": payload.get("date"),
                    "time": payload.get("time") or "00:00:00",
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
