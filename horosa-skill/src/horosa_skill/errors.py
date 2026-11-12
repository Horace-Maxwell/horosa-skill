from __future__ import annotations


class HorosaSkillError(Exception):
    def __init__(self, message: str, *, code: str = "horosa_skill_error", details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}
        _assert_registered_under_pytest(code)


class UnregisteredErrorCode(BaseException):
    """测试里，包内代码抛出了一个登记表落不到的错误码（A-5）。

    继承 BaseException 而不是 Exception：工具层的 `except Exception` 兜底会把普通异常收成 tool.internal_error 信封，
    测试照样绿——这条检查就白做了。BaseException 穿过兜底，让触发它的那条测试当场红。
    """


def _assert_registered_under_pytest(code: str) -> None:
    """只在 pytest 里查（`PYTEST_CURRENT_TEST`）、只查包内代码抛的码（测试自己造的假码不算）。

    🔴 C-13：`code=f"tool.{tool}_inverted_window"` 这种拼出来的码，`verify_error_recovery.py` 的正则看不见，
    `classify_code` 落不到任何规则 → 信封里没有 agent_recovery。静态扫描管字面量，这里管运行期真抛出来的。
    """
    import os
    import sys

    if not os.environ.get("PYTEST_CURRENT_TEST"):
        return
    if classify_code(code)[0] is not None:
        return
    frame = sys._getframe(2)
    while frame is not None and frame.f_code.co_filename == __file__:
        frame = frame.f_back
    while frame is not None and frame.f_code.co_name == "__init__" and "self" in frame.f_locals \
            and isinstance(frame.f_locals.get("self"), HorosaSkillError):
        frame = frame.f_back  # 子类自己的 __init__
    module = (frame.f_globals.get("__name__") if frame is not None else "") or ""
    if module.startswith("horosa_skill."):
        raise UnregisteredErrorCode(
            f"error code {code!r} raised from {module} has no recovery rule: add it to errors.RECOVERY_TABLE, use a "
            "registered family via errors.tool_code(tool, family), or name it with a classifiable suffix"
        )


class ToolTransportError(HorosaSkillError):
    pass


class ToolValidationError(HorosaSkillError):
    """入参 / 设置不对。没给 code 时是 `tool.invalid_input`（kind=input）。

    🔴 MCP-08：旧缺省码是基类的 `horosa_skill_error`，后缀规则把它归成 retry_or_doctor——`Invalid date for tool
    huangli: 'not-a-date'` 这种明摆着的入参错误，agent 拿到的恢复说明是「重试一次，不行跑 doctor」。
    """

    def __init__(self, message: str, *, code: str = "tool.invalid_input", details: dict | None = None) -> None:
        super().__init__(message, code=code, details=details)


class DispatchResolutionError(HorosaSkillError):
    pass


class RuntimeError(HorosaSkillError):
    pass


class RuntimeInstallError(RuntimeError):
    pass


class RuntimeValidationError(RuntimeError):
    pass


# ---------------------------------------------------------------------------------------------
# 错误可恢复（v0.36.0 B4）：每个 `code` 都能落到一条 agent 可执行的恢复说明（双语）。
# 三层：精确码表 → 前缀规则（runtime./transport./js_engine./client./…）→ 后缀规则（*_missing_*/*invalid*
# → 问用户或修入参；*_failed/*_unavailable/*timeout* → 重试再体检）。新码若三层都落不到，
# scripts/verify_error_recovery.py 即红——错误码是接口，不是日志。
# ---------------------------------------------------------------------------------------------
import re as _re
from typing import Any as _Any


def bilingual(zh: str, en: str) -> str:
    """中英并排的一句话（错误 message / prompt_to_user 用）：非中文用户也能读懂要做什么。"""
    zh, en = zh.strip(), en.strip()
    if not zh:
        return en
    if not en:
        return zh
    return f"{zh} / {en}"


DOCTOR_CMD = "uv run horosa-skill doctor"
INSTALL_CMD = "uv run horosa-skill install"

RECOVERY_KINDS: dict[str, dict[str, _Any]] = {
    "input": {
        "prompt_to_user": bilingual(
            "参数缺失或无效。请按 details.hint 补齐/修正后重试；入参口径可先看 horosa_agent_guidance(tool_name=…)。",
            "Missing or invalid input: fix it per details.hint and retry; horosa_agent_guidance(tool_name=…) documents the contract.",
        ),
        "next_action": "ask_user_or_fix_input",
    },
    "retry_or_doctor": {
        "prompt_to_user": bilingual(
            f"本地引擎/后端本次失败。可重试一次；仍失败请执行 `{DOCTOR_CMD}` 定位。",
            f"The local engine/backend failed this call. Retry once; if it persists run `{DOCTOR_CMD}`.",
        ),
        "next_action": "retry_then_doctor",
        "commands": [DOCTOR_CMD],
    },
    "runtime": {
        "prompt_to_user": bilingual(
            f"本地 Horosa 运行时不可用。请执行 `{DOCTOR_CMD}` 查看体检结果；未安装则先 `{INSTALL_CMD}`。",
            f"The local Horosa runtime is unavailable. Run `{DOCTOR_CMD}`; if it is not installed run `{INSTALL_CMD}` first.",
        ),
        "next_action": "install_or_doctor",
        "commands": [DOCTOR_CMD, INSTALL_CMD],
    },
    "transport": {
        "prompt_to_user": bilingual(
            f"本地后端暂时不可达（可能正在冷启动或已停止）。稍候数秒重试一次；仍失败请执行 `{DOCTOR_CMD}`。",
            f"The local backend is unreachable (cold start or stopped). Wait a few seconds and retry once; then run `{DOCTOR_CMD}`.",
        ),
        "retry": "backend cold start can take up to ~45s on first call; one retry is usually enough",
        "next_action": "retry_then_doctor",
        "commands": [DOCTOR_CMD],
    },
    "js_engine": {
        "prompt_to_user": bilingual(
            f"本地 JS 引擎不可用或执行失败。确认已安装离线 runtime（自带 node），或设 HOROSA_NODE_BIN 指向 node 后重试；`{DOCTOR_CMD}` 可定位。",
            f"The local JS engine is unavailable or failed. Install the offline runtime (bundled node) or point HOROSA_NODE_BIN at node, then retry; `{DOCTOR_CMD}` locates the cause.",
        ),
        "next_action": "install_or_set_node_then_retry",
        "commands": [DOCTOR_CMD],
    },
    "environment": {
        "prompt_to_user": bilingual(
            "客户端/本机环境问题（命令缺失、配置文件不合法或超时）。按 details.hint 修正环境后重试。",
            "Client/host environment problem (missing command, invalid config file, or timeout). Fix the environment per details.hint and retry.",
        ),
        "next_action": "fix_environment_then_retry",
    },
    # v0.39.0 可选云端决策层（jev.*）：这些码正常只出现在 envelope.warnings / 本地账本里——决策层失败一律关闭式
    # 回落确定性路径，技法结果照常。若作为错误码浮出（CLI jev 命令、评测），处理办法是查配置与网络，不是重算盘。
    "decision_layer": {
        "prompt_to_user": bilingual(
            "可选云端决策层（TypeSafe Jev）本次不可用，已回落确定性路径，技法结果不受影响。要排查：`horosa-skill jev status` 看模式/密钥/阈值锁，检查 HOROSA_JEV_API_KEY 与网络；不想用就设 HOROSA_JEV=off。",
            "The optional cloud decision layer (TypeSafe Jev) was unavailable and the deterministic path ran instead; technique results are unaffected. To investigate: `horosa-skill jev status` (mode / key / thresholds lock), check HOROSA_JEV_API_KEY and connectivity; set HOROSA_JEV=off to disable.",
        ),
        "next_action": "check_decision_layer_config_or_disable",
        "commands": ["uv run horosa-skill jev status"],
    },
}

# 精确码表：语义明确、需要专门指路的码。
RECOVERY_TABLE: dict[str, dict[str, _Any]] = {
    # 引擎是好的，只是这次算得久：不能落到前缀规则的「确认已安装 runtime」（v0.47.2-dev 实测：长窗口择时超时被说成没装 runtime）。
    "js_engine.timeout": {
        "kind": "js_engine",
        "prompt_to_user": bilingual(
            "这次计算超过了 JS 引擎的时间上限（引擎本身没坏，不用重装）。择日 / 择时类把搜索窗口拆短分段再搜；确实要算这么久，"
            "把 HOROSA_JS_ENGINE_TIMEOUT_SECONDS 调大并重启客户端。",
            "This computation ran past the JS engine's time limit (the engine is fine, nothing to reinstall). For election / date-search "
            "tools, split the window into shorter ranges; if it really needs that long, raise HOROSA_JS_ENGINE_TIMEOUT_SECONDS and restart the client.",
        ),
        "next_action": "shorten_window_or_raise_timeout",
    },
    # JS 引擎的三种「装得不对」各有专门的修法，不落到前缀规则的泛泛一句（v0.50.0-dev，E-11 / C-19 / E-02）。
    "js_engine.node_too_old": {
        "kind": "js_engine",
        "prompt_to_user": bilingual(
            "本机找到的 Node 太旧，本地 JS 引擎跑不起来（details.found / details.required）。装离线 runtime（自带合适版本的 node），"
            "或把 HOROSA_NODE_BIN 指向一个够新的 node，然后重启客户端。",
            "The Node found on this machine is too old for the local JS engine (details.found / details.required). Install the "
            "offline runtime (it ships a suitable node) or point HOROSA_NODE_BIN at a newer node, then restart the client.",
        ),
        "next_action": "install_runtime_or_point_node_bin_at_a_newer_node",
    },
    "js_engine.node_bin_missing": {
        "kind": "js_engine",
        "prompt_to_user": bilingual(
            "HOROSA_NODE_BIN 指向的文件不存在（details.path）。改成真实存在的 node，或删掉这个变量用离线 runtime 自带的 node。",
            "HOROSA_NODE_BIN points at a file that does not exist (details.path). Point it at a real node, or unset it to use the "
            "offline runtime's bundled node.",
        ),
        "next_action": "fix_or_unset_horosa_node_bin",
    },
    "js_engine.cli_missing": {
        "kind": "js_engine",
        "prompt_to_user": bilingual(
            "本地 JS 引擎（horosa-core-js）不在本机（details.searched 列出找过的位置）。装离线 runtime（自带引擎），或设 "
            "HOROSA_CORE_JS_ROOT 指向一份 horosa-core-js 目录；只设 HOROSA_SERVER_ROOT 的网关模式不带这个引擎。",
            "The local JS engine (horosa-core-js) is not on this machine (details.searched lists where it looked). Install the "
            "offline runtime (it ships the engine), or set HOROSA_CORE_JS_ROOT to a horosa-core-js directory; gateway mode "
            "(HOROSA_SERVER_ROOT only) does not include this engine.",
        ),
        "next_action": "install_runtime_or_set_core_js_root",
    },
    # 自备知识库（knowledge/user.py）：都是使用者自己能改的输入问题，不是「重试 / 体检」。
    "knowledge.user_not_found": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "自备知识库里没有这一条。`horosa-skill knowledge mine` 列出全部条目（id / 标题 / 标签）。",
            "That entry is not in your knowledge folder. `horosa-skill knowledge mine` lists every entry (id / title / tags).",
        ),
        "next_action": "pick_entry_from_list",
    },
    "knowledge.user_ambiguous": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "这个名字对应自备知识库里的多条（details.candidates）。用完整 id（相对路径去扩展名）指定其中一条。",
            "That name matches several of your knowledge entries (details.candidates). Use the full id (relative path without extension).",
        ),
        "next_action": "pick_one_candidate_by_full_id",
    },
    "knowledge.user_unreadable": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "文件在知识库里，但读不了（编码不是 UTF-8 / UTF-16 / GB18030、超过 2 MB、是空的，或与别的文件同名）。原因在 details.reason；改好文件后重试，`horosa-skill knowledge mine` 的 problems 列出全部。",
            "The file is in your knowledge folder but cannot be used (not UTF-8 / UTF-16 / GB18030, over 2 MB, empty, or clashing with another file). See details.reason; `horosa-skill knowledge mine` lists every problem.",
        ),
        "next_action": "fix_the_file_then_retry",
    },
    "knowledge.user_too_large": {
        "kind": "input",
        "prompt_to_user": bilingual("单条资料上限 2 MB。拆成几条再加。", "One entry is limited to 2 MB. Split it into several entries."),
        "next_action": "split_entry",
    },
    "knowledge.user_invalid_meta": {
        "kind": "input",
        "prompt_to_user": bilingual("标题 / 标签 / 技法名里不能有换行。", "Titles, tags and technique names may not contain line breaks."),
        "next_action": "fix_metadata",
    },
    "knowledge.user_trash_not_found": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "回收站里没有这一项。`horosa-skill knowledge trash` 列出可恢复的版本（trash_id）。",
            "No such item in the knowledge trash. `horosa-skill knowledge trash` lists restorable versions (trash_id).",
        ),
        "next_action": "pick_trash_id_from_list",
    },
    "knowledge.user_exists": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "已有同名条目。换个名字，或确认要覆盖后加 --overwrite。",
            "An entry with that name already exists. Pick another name, or pass --overwrite to replace it.",
        ),
        "next_action": "rename_or_overwrite",
    },
    # 命主档案（profiles.py）：档案名认不出 / 有歧义是调用方能改的入参（details.known_profiles 列出全部已存档案）；
    # 用户说的那个人还没存过档，就问用户要出生信息（存不存由用户定），不是「重试 / 体检」。
    "profile.not_found": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "没有这个命主档案。已存的名字在 details.known_profiles（horosa_profile action=list 也能列）；对不上就请用户给出生日期、时间、地点，"
            "并问要不要存成档案。",
            "No saved profile by that name. details.known_profiles lists every saved one (or horosa_profile action=list); if none fits, "
            "ask the user for the birth date, time and place, and whether to save them as a profile.",
        ),
        "next_action": "pick_profile_from_list_or_ask_user",
    },
    "profile.ambiguous": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "这个名字对应多条命主档案（details.candidates）：请用户确认是哪一位，再用那条的完整档案名。",
            "That name matches several saved profiles (details.candidates): ask the user which one, then use its full name.",
        ),
        "next_action": "pick_one_candidate_by_name",
    },
    "profile.invalid_payload": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "horosa_profile 的参数由调用方给：action = save / get / list / delete / rename，除 list 外都要带 name，data 是对象"
            "（rename 的新名放 data.new_name）。",
            "horosa_profile arguments come from the caller: action = save / get / list / delete / rename; all but list need a name; "
            "data is an object (rename takes data.new_name).",
        ),
        "next_action": "fix_payload_fields_and_retry",
    },
    "profile.not_applicable": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "这个技法的载荷顶层不收出生信息：合盘把档案名放进 inner.profile / outer.profile；不收出生信息的技法不用档案。",
            "This tool takes no birth data at the top level: for relationship charts put profile names in inner.profile / outer.profile; "
            "tools without birth data do not use profiles.",
        ),
        "next_action": "move_profile_into_person_slot",
    },
    "profile.store_unavailable": {
        "kind": "retry_or_doctor",
        "prompt_to_user": bilingual(
            "命主档案库这次打不开（details.path / details.error：磁盘只读、权限、被别的进程长时间占用）。稍后重试；仍不行就把出生信息直接写进载荷。",
            "The birth-profile database could not be opened (details.path / details.error: read-only disk, permissions, or held by another process). "
            "Retry later; meanwhile pass the birth fields directly.",
        ),
        "next_action": "retry_or_pass_fields_directly",
    },
    "profile.store_corrupt": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "命主档案库文件损坏（details.path）。档案是用户数据，不会自动删除重建：请用户把这个文件改名挪开（留作备份），再重新保存档案。",
            "The birth-profile database is corrupt (details.path). It is user data and is never rebuilt automatically: ask the user to rename "
            "the file aside (keep it as a backup), then save the profiles again.",
        ),
        "next_action": "move_corrupt_file_aside_then_save_again",
    },
    # 地名 → 坐标（v0.48.0，service/api/place.py）：歧义 / 找不到 / 切换日时区不唯一都是「问用户」，details.agent_recovery 带候选；
    # not_found 的后缀会被通用规则判成「重试再体检」，必须精确登记。旧 runtime 缺这项能力 = 升级 runtime，不是重试。
    # v0.50.0 接受规则：同名多地 / 只有近似名 / 一个候选但州省限定词核对不了，都是 place.ambiguous（details.status 区分
    # ambiguous / near / confirm / qualifier_mismatch，单候选措辞是「请确认」）；只给地区 = place.too_broad；坐标写进 place =
    # place.looks_like_coordinates。提示里举的写法必须真能解析（tests/test_place_acceptance.py 逐条跑引擎核对）。
    "place.ambiguous": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "这个地名不能自动确定（details.status：同名多地 / 只有近似匹配 / 限定词核对不了），候选在 details.candidates。"
            "把候选念给用户确认或选一个，不要替用户挑；选定后用那一条的 lat / lon / zone 重试，或改传带省 / 国家的写法（如「辽宁朝阳」「London, UK」）。",
            "The place cannot be settled automatically (details.status: several places share the name / only approximate matches / "
            "a qualifier the library cannot check); candidates are in details.candidates. Let the user confirm or pick one — never "
            "choose yourself — then retry with its lat/lon/zone, or a form with province/country (e.g. 'London, UK').",
        ),
        "next_action": "ask_user_to_pick_a_candidate",
    },
    "place.not_found": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "城市库里没有这个地名（details.suggestions 是拼写相近的条目）。请用户确认，或给带省 / 国家的写法（如「北京市朝阳区」「美国纽约」"
            "「Taipei, Taiwan」），或直接给经纬度。",
            "The place is not in the city library (details.suggestions lists similar spellings). Ask the user, or for a form with "
            "province/country (e.g. 'Taipei, Taiwan', 'London, UK'), or coordinates.",
        ),
        "next_action": "ask_user_for_specific_place_or_coordinates",
    },
    "place.too_broad": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "给的是国家 / 省 / 州（details.regions），不是一个地点：请用户给出生 / 事件所在的城市（如「美国纽约」「台湾台北」），或直接给经纬度。",
            "That is a country / province / state (details.regions), not a place: ask the user for the city (e.g. 'Los Angeles, CA'), "
            "or coordinates.",
        ),
        "next_action": "ask_user_for_city",
    },
    "place.looks_like_coordinates": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "place 里写的是经纬度。把纬度、经度分别传给 lat 与 lon（再给 zone），不要放进 place；哪个数是纬度不要猜，不确定就问用户。",
            "place holds coordinates. Pass latitude and longitude separately as lat and lon (plus zone), not in place; do not guess "
            "which number is the latitude — ask the user if unsure.",
        ),
        "next_action": "pass_lat_lon_fields",
    },
    "place.zone_ambiguous": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "这一天该地的 UTC 偏移不唯一（夏令时切换日）。请用户确认用哪个时区（details.ask_if_missing 给了两个选项），再带 zone 重试。",
            "The UTC offset is not unique on that day (a DST switch). Ask the user which zone to use (two options in details.ask_if_missing), then retry with zone.",
        ),
        "next_action": "ask_user_for_zone",
    },
    "place.runtime_outdated": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "已装的离线 runtime 比本版 horosa-skill 旧，没有地名检索。请执行 details.commands 里的升级命令；升级前可以先直接给 lat / lon / zone。",
            "The installed offline runtime predates this horosa-skill and has no place search. Run the upgrade command in details.commands; until then pass lat/lon/zone explicitly.",
        ),
        "next_action": "upgrade_runtime_or_pass_coordinates",
    },
    "tool.backend_param_error": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "后端拒绝了这组参数（它们已通过本仓的逐字段校验）。details.payload_preview 是发出去的值：与用户核对；值都对就把 details 报给维护者，不要改格式重试。",
            "The backend refused these values (they passed the skill's field validation). details.payload_preview shows what was sent: check it with the user; if right, report the details to the maintainer instead of reformatting.",
        ),
        "next_action": "check_values_with_user_or_report",
    },
    "tool.unknown": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "工具名不存在。用 horosa_tool_run 描述里的技法目录或 resource horosa://catalog/techniques 核对名字。",
            "Unknown tool name. Check the technique catalog in horosa_tool_run's description or resource horosa://catalog/techniques.",
        ),
        "next_action": "pick_tool_from_catalog",
    },
    "dispatch.no_matching_tool": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "没有技法匹配这句话。从 details.candidates 里挑技法名直调对应工具，或换用更明确的技法说法。",
            "No technique matched the query. Pick a tool name from details.candidates and call it directly, or rephrase with the technique's name.",
        ),
        "next_action": "pick_candidate_tool",
    },
    "dispatch.technique_choice_required": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "认出了要问什么，但有几种技法都合适、结论可能不同：把 details.agent_recovery.prompt_to_user 转给用户，按用户选的技法直调对应工具（或用 horosa_hecan 同时跑几种）。",
            "The intent is clear but several techniques fit and may disagree: relay details.agent_recovery.prompt_to_user, then call the tool the user picks (or horosa_hecan to run several).",
        ),
        "next_action": "ask_user_then_call_chosen_tool",
    },
    "dispatch.out_of_scope": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "这类请求不在星阙的技法目录里：如实告诉用户，details.covers 列出了能做什么；不要拿别的技法冒充。",
            "This request is outside Horosa's catalogue: tell the user so; details.covers lists what it does. Do not substitute another technique silently.",
        ),
        "next_action": "tell_user_not_supported",
    },
    "runtime.not_installed": {"kind": "runtime", "next_action": "install"},
    "runtime.java_backend_unavailable": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "Java 后端不可用，运行时处于 chart-only 降级：西占/推运/三式 ken/神数/地占/塔罗仍可用；农历/八字/紫微/六壬与占时起课在冷却期后自动重试。`uv run horosa-skill doctor` 看 Java 启动错误。",
            "The Java backend is down; the runtime is degraded to chart-only: Western/predictive/ken/shenshu/geomancy/tarot still work; nongli/bazi/ziwei/liureng and time-cast tools retry after the cooldown. Run `uv run horosa-skill doctor` for the Java boot error.",
        ),
        "next_action": "run_doctor_or_retry_after_cooldown",
        "commands": [DOCTOR_CMD],
    },
    "runtime.start_timeout": {"kind": "runtime", "next_action": "doctor_then_retry_or_raise_timeout"},
    "runtime.launcher_patch_anchor_missing": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "本机已装的 runtime 启动器与本版 horosa-skill 预期的结构对不上，「只杀自己人」的误杀"
            "保护补丁打不上去。请升级 horosa-skill（uv sync 或 uvx --refresh）后重试；"
            "确需临时跳过设 HOROSA_RUNTIME_LAUNCHER_PATCH=0（会失去该保护）。",
            "The installed runtime launcher does not match what this horosa-skill version expects, so the "
            "foreign-process kill guard could not be applied. Upgrade horosa-skill (uv sync / uvx --refresh) "
            "and retry; set HOROSA_RUNTIME_LAUNCHER_PATCH=0 to skip it deliberately (you lose the guard).",
        ),
        "next_action": "upgrade_horosa_skill_then_retry",
    },
    "runtime.port_conflict_foreign": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "Horosa 的本机服务端口被**其它进程**占用（可能是你自己开着的星阙桌面端，或另一个程序）。"
            "本工具不会去终止不属于自己的进程。请关掉占用者，或改用别的端口："
            "设 HOROSA_PORTS=auto 自动挑空闲端口，或显式设 HOROSA_LOCAL_BACKEND_PORT / "
            "HOROSA_LOCAL_CHART_PORT；若那正是你想用的服务，设 HOROSA_SERVER_ROOT / "
            "HOROSA_CHART_SERVER_ROOT 指向它。",
            "Horosa's local service ports are held by ANOTHER process (possibly your own Horosa desktop "
            "app, or an unrelated program). This tool never terminates processes it did not start. "
            "Close the holder, or move ports: set HOROSA_PORTS=auto, or set HOROSA_LOCAL_BACKEND_PORT / "
            "HOROSA_LOCAL_CHART_PORT explicitly. If that IS the server you want, point "
            "HOROSA_SERVER_ROOT / HOROSA_CHART_SERVER_ROOT at it.",
        ),
        "next_action": "free_the_port_or_change_ports",
    },
    "runtime.port_conflict_unknown_holder": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "端口上有服务在应答，但查不出它是不是 Horosa 的，因此没有采用它 —— 把陌生服务当后端"
            "的症状是「排盘失败但 HTTP 200」。确认那确实是 Horosa 后端后设 "
            "HOROSA_RUNTIME_TRUST_PORTS=1；否则换端口（HOROSA_PORTS=auto）。",
            "Something is answering on the port but could not be identified as Horosa, so it was not "
            "adopted — adopting a stranger shows up as 'chart failed but HTTP 200'. If you know it is a "
            "Horosa backend, set HOROSA_RUNTIME_TRUST_PORTS=1; otherwise move ports (HOROSA_PORTS=auto).",
        ),
        "next_action": "verify_holder_then_trust_or_change_ports",
    },
    "runtime.stop_refused_foreign": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "这些端口上的服务不是本工具启动的（可能是你自己开着的星阙桌面端），已拒绝停止 —— "
            "停脚本按端口和 pid 文件动手，停下去会关掉你正在用的程序。确认无误请用 "
            "`horosa-skill runtime stop --force`。",
            "Those services were not started by this tool (possibly your own Horosa desktop app), so the "
            "stop was refused — the stop script acts by port and pid file and would close a program you "
            "are using. Use `horosa-skill runtime stop --force` if you are sure.",
        ),
        "next_action": "confirm_then_force_stop",
    },
    "runtime.stop_refused_clients_attached": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "还有别的 Horosa 客户端挂在这份 runtime 上，停止会打断它们。确认要停请加 --force。",
            "Other Horosa clients are still attached to this runtime; stopping would cut them off. "
            "Pass --force if you are sure.",
        ),
        "next_action": "confirm_then_force_stop",
    },
    "runtime.external_unreachable": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "你已显式把后端地址指到别处（HOROSA_SERVER_ROOT / HOROSA_CHART_SERVER_ROOT），"
            "但那个地址不可达。外部模式下本工具**不会**在本机启动 runtime。请确认那台机器上的"
            "服务在跑且地址可达；要改用本机 runtime，请取消这两个环境变量。",
            "You pointed the backend elsewhere (HOROSA_SERVER_ROOT / HOROSA_CHART_SERVER_ROOT) but that "
            "address is unreachable. In external mode this tool will NOT start a local runtime. Make sure "
            "the remote services are up, or unset those variables to use the local runtime.",
        ),
        "next_action": "fix_external_address_or_unset",
    },
    "runtime.install_long_path": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "Windows 的 260 字符路径上限会让解包失败。开启长路径支持（注册表 LongPathsEnabled=1，"
            "需重启），或把 runtime 装到更短的路径：设 HOROSA_RUNTIME_ROOT=C:\\horosa 后重试。",
            "Windows' 260-character path limit would make extraction fail. Enable long paths "
            "(registry LongPathsEnabled=1, needs a reboot), or install to a shorter path: set "
            "HOROSA_RUNTIME_ROOT=C:\\horosa and retry.",
        ),
        "next_action": "enable_long_paths_or_shorten_runtime_root",
    },
    "runtime.start_blocked_quarantine": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "runtime 的可执行文件带 macOS 隔离属性，Gatekeeper 会在启动时直接终止它们（这只发生在手动下载"
            "归档后 `install --archive` 的安装方式）。请按错误里的 xattr 命令解除后重试。",
            "The runtime binaries carry the macOS quarantine attribute, so Gatekeeper kills them on launch "
            "(this happens only when the archive was downloaded by hand and installed with `install --archive`). "
            "Run the xattr command from the error, then retry.",
        ),
        "next_action": "clear_quarantine_then_retry",
    },
    "runtime.stop_timeout": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "停止脚本超时未返回。请看 details.survivors 里还活着的进程，用 `horosa-skill runtime status` 复核；"
            "确认是本工具起的服务后可 `runtime stop --force`。",
            "The stop script did not return in time. Check details.survivors, re-check with "
            "`horosa-skill runtime status`, and use `runtime stop --force` once you have confirmed the services are ours.",
        ),
        "next_action": "inspect_survivors_then_force_stop",
    },
    "runtime.launcher_patch_write_failed": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "写入启动器补丁失败（runtime 目录只读或属于别的用户）。请检查目录权限；确需临时跳过设 "
            "HOROSA_RUNTIME_LAUNCHER_PATCH=0（会失去误杀保护）。",
            "Writing the launcher patch failed (runtime directory read-only or owned by another user). Fix the "
            "permissions; set HOROSA_RUNTIME_LAUNCHER_PATCH=0 to skip deliberately (you lose the kill guard).",
        ),
        "next_action": "fix_permissions_then_retry",
    },
    "runtime.install_refused_running_foreign": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "端口上正在运行的服务不是本工具启动的（可能是你自己开着的星阙桌面端），升级/重装不会去停它。"
            "请先关掉它，或改用别的端口（HOROSA_PORTS=auto）后再装。",
            "The services running on the ports were not started by this tool (possibly your own Horosa desktop "
            "app); install/upgrade will not stop them. Close them first, or move ports (HOROSA_PORTS=auto).",
        ),
        "next_action": "close_foreign_service_or_change_ports",
    },
    "runtime.install_previous_locked": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "上一版 runtime 目录（previous/）里还有进程在用，无法清理。请看 details.holders，关掉后重试。",
            "The previous runtime directory (previous/) is still held by a process and cannot be removed. "
            "See details.holders, close them, and retry.",
        ),
        "next_action": "close_holders_then_retry",
    },
    "runtime.previous_cleanup_deferred": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "新 runtime 已装好并可用；旧目录 previous/ 暂时删不掉（Windows 常见：文件句柄未释放），"
            "重启后再跑 `horosa-skill doctor` 会提示清理。",
            "The new runtime is installed and usable; the old previous/ directory could not be removed yet "
            "(common on Windows while handles are open). `horosa-skill doctor` will suggest the cleanup later.",
        ),
        "next_action": "none_retry_cleanup_later",
    },
    "runtime.install_start_in_progress": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "runtime 正在启动，这时换目录会把启动器脚下的文件搬走，安装未动 current/。等它起好（`horosa-skill runtime status` 看进度）后重试。",
            "The runtime is starting; swapping directories now would pull the files out from under the launcher, so "
            "current/ was left untouched. Wait for it to come up (`horosa-skill runtime status`), then retry.",
        ),
        "next_action": "wait_for_start_then_retry_install",
    },
    "runtime.install_stop_failed": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "升级前停止本工具自己的服务失败，安装未动 current/。请看 details.stop，`horosa-skill runtime stop` 成功后重试。",
            "Stopping our own services before the upgrade failed; current/ was left untouched. See details.stop, "
            "get `horosa-skill runtime stop` to succeed, then retry.",
        ),
        "next_action": "stop_then_retry_install",
    },
    "runtime.restart_after_upgrade_failed": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "新 runtime 已装好，但重新启动失败。请跑 `horosa-skill runtime start`，仍失败看 `horosa-skill doctor`。",
            "The new runtime is installed but did not restart. Run `horosa-skill runtime start`; if it still fails, "
            "see `horosa-skill doctor`.",
        ),
        "next_action": "runtime_start_then_doctor",
    },
    "runtime.path_not_ascii": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "Windows 上 Horosa 离线 runtime 必须装在纯英文路径下（当前路径含中文等非英文字符，常见于中文用户名）："
            "随包的 Java 17 与 Swiss Ephemeris 用窄字符 API 访问文件，否则 Java 起不来、星历打不开。请设 HOROSA_RUNTIME_ROOT 为纯英文路径（如 C:\\horosa）后重装。",
            "On Windows the Horosa offline runtime must live under an ASCII-only path (the current path contains non-ASCII "
            "characters, typically from the user name): the bundled Java 17 and Swiss Ephemeris access files through "
            "narrow-character APIs. Set HOROSA_RUNTIME_ROOT to an ASCII-only path (e.g. C:\\horosa) and reinstall.",
        ),
        "next_action": "set_ascii_runtime_root_then_reinstall",
    },
    # 目录写不了不是「没装 / 去体检」：重装同样写不进去。旧行为是把它答成「别的进程正在启动」（v0.50.0-dev，E-08）。
    "runtime.root_not_writable": {
        "kind": "environment",
        "prompt_to_user": bilingual(
            "Horosa 的 runtime 目录写不进去（details.runtime_root；常见原因：目录归别的用户、只读挂载、磁盘满）。"
            "请修好该目录的写权限，或把 HOROSA_RUNTIME_ROOT 指到一个可写的目录，然后重试。",
            "The Horosa runtime directory is not writable (details.runtime_root; typically owned by another user, a "
            "read-only mount, or a full disk). Fix its write permission, or point HOROSA_RUNTIME_ROOT at a writable "
            "directory, then retry.",
        ),
        "next_action": "fix_runtime_root_permissions_or_move_root",
    },
    # 归档坏了不是「没装 / 去体检」：重跑同一条命令还是同一个坏文件。旧行为是 BadZipFile / ReadError 的 traceback（v0.50.0-dev，E-04）。
    "runtime.install_archive_invalid": {
        "kind": "environment",
        "prompt_to_user": bilingual(
            "给安装器的 runtime 归档读不了（details.detected_format 说它实际是什么：html / json = 下到了网页或接口报错，"
            "empty / unknown = 不是归档，zip / tar.gz = 下载没下完）。请重新下载本平台的归档，用 `--sha256` 核对后再装；"
            "已装的 runtime 没有被动过。",
            "The runtime archive given to the installer cannot be read (details.detected_format says what it really is: "
            "html / json = a web page or API error was saved, empty / unknown = not an archive, zip / tar.gz = an "
            "incomplete download). Download the archive for this platform again and check it with `--sha256`; the "
            "installed runtime was not touched.",
        ),
        "next_action": "redownload_archive_and_verify_sha256",
    },
    "runtime.install_sha256_invalid": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "`--sha256` 要的是 64 位十六进制的 SHA-256 摘要（可带 `sha256:` 前缀）；发布页的 runtime-manifest.json 里有本平台归档的值。",
            "`--sha256` takes a 64-hex-digit SHA-256 digest (an optional `sha256:` prefix is fine); the release's "
            "runtime-manifest.json lists the value for this platform's archive.",
        ),
        "next_action": "pass_a_64_hex_sha256",
    },
    # 端口被 HTTP 探针看不见的监听者占着（E-07）：不是「没装 / 去体检」，是换端口或关进程。
    "runtime.port_taken": {
        "kind": "environment",
        "prompt_to_user": bilingual(
            "本机服务要用的端口被别的进程占着（details.port_takers 点名了端口与进程），所以没有启动。关掉那个进程，"
            "或设 HOROSA_PORTS=auto 让本工具换到空闲端口。本工具不会去终止它。",
            "A port the local services need is held by another process (details.port_takers names the port and the "
            "process), so nothing was started. Stop that process, or set HOROSA_PORTS=auto to move to free ports. This "
            "tool will not stop it for you.",
        ),
        "next_action": "free_the_port_or_set_horosa_ports_auto",
    },
    # 清单条目没有摘要 = 下载来的归档无从校验（C-15 / E-15：旧行为是一声不吭地不校验）。
    "runtime.install_sha256_missing": {
        "kind": "environment",
        "prompt_to_user": bilingual(
            "发布清单里本平台的条目没有 sha256，下载来的归档无法校验，所以没有安装（已装的 runtime 没动）。从可信来源"
            "（发布页）拿到归档的 sha256，用 `install --sha256 <摘要>` 重试；或者换用官方清单（不设 HOROSA_RUNTIME_MANIFEST_URL）。",
            "The release manifest has no sha256 for this platform, so a downloaded archive cannot be verified and nothing was "
            "installed (the installed runtime was not touched). Get the archive's sha256 from a source you trust (the release "
            "page) and retry with `install --sha256 <digest>`, or use the official manifest (unset HOROSA_RUNTIME_MANIFEST_URL).",
        ),
        "next_action": "pass_sha256_from_a_trusted_source_or_use_the_official_manifest",
    },
    "runtime.install_manifest_invalid": {
        "kind": "environment",
        "prompt_to_user": bilingual(
            "给安装器的清单文件不是 runtime 发布清单（details.reason 说它实际是什么）。重新下载发布页的 runtime-manifest.json，"
            "或去掉 --manifest-url / HOROSA_RUNTIME_MANIFEST_URL 用官方清单。",
            "The manifest file given to the installer is not a runtime release manifest (details.reason says what it is). "
            "Download runtime-manifest.json from the release page again, or drop --manifest-url / HOROSA_RUNTIME_MANIFEST_URL "
            "to use the official manifest.",
        ),
        "next_action": "redownload_manifest_or_use_the_official_one",
    },
    "runtime.install_download_in_progress": {
        "kind": "retry_or_doctor",
        "prompt_to_user": bilingual(
            "另一个 install 正在下载同一个归档（details.holder）。等它结束后看它的结果；它失败了再重跑，会从断点续传。",
            "Another install is downloading the same archive (details.holder). Wait for it and check its result; if it fails, "
            "rerun and the download resumes.",
        ),
        "next_action": "wait_for_the_other_install",
    },
    # 清数据被拒不是「没装 / 去体检」：数据目录指到了家目录 / 根 / 包着 runtime 根的地方（v0.50.0-dev，E-01）。
    "runtime.purge_refused": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "`--purge-data` 没有执行：数据目录指在一个不可能整个归本工具的位置（details.reason：home / above_home / "
            "filesystem_root / contains_runtime_root）。什么都没有删。把 HOROSA_SKILL_DATA_DIR 指回专用目录后重试，"
            "或者手工删除 details.skill_named_children 里确认要删的；不带 --purge-data 的卸载照常可用。",
            "`--purge-data` did nothing: the data directory points somewhere that cannot belong to this tool alone "
            "(details.reason: home / above_home / filesystem_root / contains_runtime_root). Nothing was deleted. Point "
            "HOROSA_SKILL_DATA_DIR at a dedicated directory and retry, or delete by hand the entries in "
            "details.skill_named_children you are sure about; uninstalling without --purge-data still works.",
        ),
        "next_action": "point_data_dir_at_a_dedicated_directory_or_delete_by_hand",
    },
    "runtime.platform_unsupported": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "本机平台没有离线 runtime 载荷（只发 macOS Apple Silicon 与 Windows x64）。可走网关模式：在一台"
            "受支持的机器上跑 runtime，本机设 HOROSA_SERVER_ROOT 与 HOROSA_CHART_SERVER_ROOT 指过去。",
            "There is no offline runtime payload for this platform (only macOS Apple Silicon and Windows x64 ship). "
            "Use gateway mode: run the runtime on a supported machine and point HOROSA_SERVER_ROOT / "
            "HOROSA_CHART_SERVER_ROOT at it.",
        ),
        "next_action": "use_gateway_mode",
    },
    "config.unexpanded_template": {
        "kind": "environment",
        "prompt_to_user": bilingual(
            "某个路径设置里还留着未展开的 `${…}` 占位符（宿主没有替换它）。请在客户端的扩展设置里填上真实路径，"
            "或删掉该环境变量用默认路径。",
            "A path setting still contains an unexpanded `${…}` placeholder (the host did not substitute it). "
            "Fill in a real path in the client's extension settings, or unset the variable to use the default.",
        ),
        "next_action": "fix_placeholder_or_unset",
    },
    "runtime.starting": {
        "kind": "transport",
        "prompt_to_user": bilingual(
            "本机 runtime 正在启动（首次运行要解压并训练 CDS，可能几分钟）。等 retry_after_seconds "
            "秒后重试**同一个调用**即可，不用改参数。连续三次仍是 starting 请跑 "
            "`horosa-skill runtime status` 看启动器日志。",
            "The local runtime is still starting (first run unpacks and trains CDS; this can take minutes). "
            "Retry the SAME call after retry_after_seconds — no parameter changes needed. If it is still "
            "starting after three tries, run `horosa-skill runtime status` for the launcher log.",
        ),
        "next_action": "retry_same_call_after_delay",
    },
    "transport.connection_error": {"kind": "transport"},
    "report.run_not_found": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "run_id 不存在。先用 horosa_memory_query 找到要导出的运行记录，再用它的 run_id 渲染。",
            "run_id not found. Use horosa_memory_query to locate the run first, then render with its run_id.",
        ),
        "next_action": "query_memory_for_run_id",
    },
    # 记忆库（v0.50.0-dev）：not_found 的后缀会被通用规则判成「重试再体检」，必须精确登记；store_unavailable 是环境问题。
    "memory.run.not_found": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "没有这个 run_id 的记录。先用 horosa_memory_query 找到要的那一条，再用它的 run_id。",
            "No run with this run_id. Use horosa_memory_query to find the run first, then use its run_id.",
        ),
        "next_action": "query_memory_for_run_id",
    },
    # 合参复用（v0.50.0）：tools 里的 run_id 存在，但里面没有算成的技法结果。
    "hecan.run_not_reusable": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "这个 run_id 里没有算成的技法结果，不能拿来合参。用 horosa_memory_query 找一条有技法结果的运行，或在 tools 里写技法名重新起盘。",
            "This run_id holds no successful technique result, so it cannot be reused. Find a run with a technique result via"
            " horosa_memory_query, or name the technique in tools to compute it.",
        ),
        "next_action": "query_memory_for_run_id",
    },
    "memory.query.invalid_time": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "after / before 要写成日期或 ISO 时间（details.accepted_forms）；「昨天」「上周」先换算成日期，时区放 zone。",
            "Write after / before as a date or ISO date-time (details.accepted_forms); turn 'yesterday' / 'last week' into dates"
            " first and put the time zone in zone.",
        ),
        "next_action": "rewrite_time_filter",
    },
    "memory.answer.empty": {"kind": "input", "next_action": "send_non_empty_answer"},
    "memory.answer.too_large": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "写回的答案超过上限（details.limits）。写回结论与要点；完整长文用 horosa_report_render 出报告文件。",
            "The answer exceeds the limits in details.limits. Write back the conclusions and key points; render the long text"
            " as a report with horosa_report_render.",
        ),
        "next_action": "shorten_answer_or_render_report",
    },
    "memory.store_unavailable": {
        "kind": "environment",
        "prompt_to_user": bilingual(
            f"本机记忆库打不开或写不了（details.path / details.error：只读目录、权限、磁盘满）。起盘照常可用；请用户检查数据目录，或跑 `{DOCTOR_CMD}`。",
            "The local memory store cannot be opened or written (details.path / details.error: read-only directory, permissions,"
            f" full disk). Chart tools still work; ask the user to check the data directory, or run `{DOCTOR_CMD}`.",
        ),
        "next_action": "check_data_dir_then_doctor",
        "commands": [DOCTOR_CMD],
    },
    "report.output_path_not_allowed": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "报告只能写进报告输出目录（或 HOROSA_REPORT_OUTPUT_ROOTS 白名单目录）。改用相对路径，或让用户把目标目录加进白名单。",
            "Reports may only be written inside the report output directory (or a HOROSA_REPORT_OUTPUT_ROOTS allow-listed directory). "
            "Use a relative path, or ask the user to allow-list the target directory.",
        ),
        "next_action": "use_relative_output_path_or_allowlist_root",
    },
    "report.output_path_unusable": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "output_path 用不了（details.reason：existing_file 已有文件且不是星阙写的报告，不替换 / store_area 是星阙自己的存储区 / "
            "extension_mismatch 扩展名和 format 对不上 / name_too_long 文件名太长 / path_refused_by_system 系统不接受这条路径"
            "（多半是整条太长）/ parent_not_directory 路径中间是个文件 / not_writable 目录没有写权限 / no_free_name 缺省文件名都被占了 / "
            "write_failed 写盘失败）。换一个新文件名或目录后重试；不写 output_path 就落在缺省位置。除 write_failed 外都在起盘和写回"
            "解读之前检查，被拒时什么都没有写。",
            "output_path cannot be used (details.reason: existing_file = a file that is not a Horosa report is never replaced / "
            "store_area = Horosa's own storage / extension_mismatch / name_too_long / path_refused_by_system / "
            "parent_not_directory / not_writable / no_free_name / write_failed). Retry with a new file name or a directory; "
            "omit output_path to use the default location. Every reason except write_failed is checked before the technique "
            "runs and before the reading is recorded, so nothing was written.",
        ),
        "next_action": "fix_output_path_and_retry",
    },
    "report.ai_report_too_large": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "这次给报告的解读文字超过上限（details.limit 字，details.largest_fields 列出最长的字段）。精简后重出，或分几份报告；"
            "被拒时什么都没有写，也没有记到 run 上。",
            "The reading passed to the report is over the limit (details.limit characters; details.largest_fields lists the "
            "longest fields). Shorten it or split it across reports; nothing was written or recorded on the run.",
        ),
        "next_action": "shorten_ai_report_and_retry",
    },
    "report.source_not_found": {"kind": "input", "next_action": "query_memory_for_run_id"},
    "report.no_chart_content": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "这个结果没有可排的盘面或盘图：解析 / 清单 / 知识类工具没有盘面；PNG 只画有盘式的技法（八字等没有盘图）。"
            "直接读它的结果；要报告就改出 PDF / DOCX，或对起盘类技法出。",
            "This result has no chart or chart figure to lay out: parse / registry / knowledge tools have no chart, and PNG only "
            "draws techniques with a chart layout (BaZi has none). Read the result directly, render PDF / DOCX instead, or "
            "report on a charting technique.",
        ),
        "next_action": "read_tool_result_or_pick_charting_technique",
    },
    "report.chart_figure_unavailable": {
        "kind": "runtime",
        "prompt_to_user": bilingual(
            "这个技法有盘，但这次没画成（details.figure_gaps 写明缺哪张、为什么：多半是补算那张盘要用的排盘引擎没在跑，"
            "或星阙 app 画法这次不可用）。让引擎跑起来（调用一次任一技法工具即可）再重出 PNG；或改出 PDF 排盘报告，"
            "正文照出、缺的那张会写明。",
            "The technique has a chart, but it could not be drawn this time (details.figure_gaps says which figure and why: "
            "usually the chart engine needed to compute it is not running, or the app chart renderer is unavailable). "
            "Get the engine running (any technique call starts it) and render the PNG again, or render a PDF chart report: "
            "the text is complete and the missing figure is stated.",
        ),
        "next_action": "start_engine_then_retry_or_render_pdf",
    },
    "report.no_calendar_content": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "这个结果里没有能写进日历的日期：ICS 只收择日的命中时段 / 候选时刻、推运各期与星历事件这些结果里写着的日期，不推算新日期。"
            "要日历就对择日或推运类技法出（details.calendar_tools）；其余直接读结果。",
            "This result has no dates that can go into a calendar: ICS only exports election hits / candidate moments, "
            "predictive periods and ephemeris events stated in the result, and computes no new dates. Use an election or "
            "predictive technique (details.calendar_tools), or read the result directly.",
        ),
        "next_action": "read_tool_result_or_pick_calendar_technique",
    },
    "report.png_font_unavailable": {
        "kind": "environment",
        "prompt_to_user": bilingual(
            "本机没有能画中文的 TrueType 字体（或所选字体缺图上的字），画不出不带方块字的 PNG 盘图。改出 PDF（自带回退字体），"
            "或请用户装中文字体（如 Noto Sans CJK）后重试。",
            "No TrueType CJK font is available (or the chosen font lacks glyphs the chart needs), so the PNG chart cannot "
            "be drawn without tofu. Render a PDF instead (built-in fallback font), or ask the user to install a CJK font "
            "such as Noto Sans CJK and retry.",
        ),
        "next_action": "render_pdf_or_install_cjk_font",
    },
    "report.from_tool.unsaved_result": {"kind": "input", "next_action": "rerun_with_save_result_true"},
    "report.technique.no_cards": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "这个 run/session 里没有技法依据卡（还没跑过技法工具，或结果未存档）。先调用技法工具（save_result=true）再导出技法报告。",
            "No technique cards in this run/session (no technique tool has run, or results were not saved). Run a technique tool with save_result=true, then export the technique report.",
        ),
        "next_action": "run_technique_tool_first",
    },
    # 这一个码同时覆盖「字段校验没过」（绝大多数）与「整包参数不是对象」两种情形。此前表里写了两遍、后者静默覆盖前者，
    # 字段校验错误的 hint 因此一直写着「参数没解析成对象」（tests/test_no_duplicate_dict_keys.py 起守住整库字面量重键）。
    "tool.invalid_payload": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "参数没通过校验：按 details.errors 逐项改正对应字段（缺的问用户，不要猜）。若是整包参数没解析成对象，"
            "就把各字段按工具的 inputSchema 直接传；确需整包时 request 必须是合法 JSON 对象。",
            "The arguments failed validation: fix each field listed in details.errors (ask the user for anything missing; never guess). "
            "If the whole call did not parse as an object, pass fields directly per the tool's inputSchema; "
            "a single `request` blob must be a valid JSON object.",
        ),
        "next_action": "fix_input_per_validation_errors",
    },
    # v0.50.0 逐字段入参校验（input_fields / input_normalization）：details.fields 每个出问题的字段一条
    # {field, got, expected, example, options}；agent_recovery 已带 must_ask_user / fix_fields，这里只是表内兜底文字。
    "tool.invalid_zone": {"kind": "input", "prompt_to_user": bilingual(
        "时区读不懂：按 details.expected 改成 ±HH:MM 偏移或 IANA 名；缩写有多种含义时从 details.options 里请用户选。",
        "The time zone was not understood: pass an ±HH:MM offset or an IANA name (details.expected); for an ambiguous abbreviation ask the user to pick from details.options."),
        "next_action": "fix_field_and_retry"},
    "tool.zone_ambiguous": {"kind": "input", "prompt_to_user": bilingual(
        "这个钟点在该时区不唯一或不存在（夏令时切换）。请用户从 details.options 的两个偏移里选一个，带 zone 重试。",
        "That wall time is ambiguous or nonexistent in the zone (a DST switch). Ask the user to pick one of the two offsets in details.options and retry with zone."),
        "next_action": "ask_user_for_zone"},
    "tool.invalid_time": {"kind": "input", "prompt_to_user": bilingual(
        "钟点读不懂或越界：改成 24 小时制 HH:MM:SS（details.expected）；有多种读法时请用户选。",
        "The time was not understood or is out of range: pass a 24-hour HH:MM:SS (details.expected); ask the user when it reads more than one way."),
        "next_action": "fix_field_and_retry"},
    "tool.time_unknown": {"kind": "input", "prompt_to_user": bilingual(
        "没有钟点（空、或「不详」）。钟点决定时柱、上升与宫位，不能默认成 0 点：请向用户问钟点。",
        "The clock time is missing or unknown. It decides the hour pillar, Ascendant and houses and must not default to midnight: ask the user."),
        "next_action": "ask_user_for_time"},
    "tool.time_is_shichen": {"kind": "input", "prompt_to_user": bilingual(
        "给的是时辰（两小时一段），不是钟点：请向用户问具体钟点，不要替用户挑一个。",
        "A double-hour (时辰) was given, not a clock time: ask the user for the exact time instead of picking one."),
        "next_action": "ask_user_for_time"},
    "tool.invalid_date": {"kind": "input", "prompt_to_user": bilingual(
        "日期读不懂或不存在：改成公历 YYYY-MM-DD（details.expected）；年份含糊时从 details.options 里请用户选。",
        "The date was not understood or does not exist: pass a Gregorian YYYY-MM-DD (details.expected); ask the user to pick from details.options when the year is ambiguous."),
        "next_action": "fix_field_and_retry"},
    "tool.ambiguous_date": {"kind": "input", "prompt_to_user": bilingual(
        "日期有「月/日」与「日/月」两种读法：请用户从 details.options 里选，按 YYYY-MM-DD 重试。",
        "The date reads both month/day and day/month: ask the user to pick from details.options and retry as YYYY-MM-DD."),
        "next_action": "ask_user_for_date"},
    "tool.lunar_date_unsupported": {"kind": "input", "prompt_to_user": bilingual(
        "给的是农历日期：先用 horosa_cn_calendar_month 查到对应的公历日（或向用户问公历生日），再按 YYYY-MM-DD 起盘。",
        "A lunar-calendar date was given: find the Gregorian day with horosa_cn_calendar_month (or ask the user for it), then retry with YYYY-MM-DD."),
        "next_action": "convert_lunar_date_then_retry"},
    "tool.invalid_coordinate": {"kind": "input", "prompt_to_user": bilingual(
        "经纬度读不懂或越界：纬度 31n13 / 31.22（±90）、经度 121e28 / 121.47（±180）；方向字母与字段不符时多半是经纬传反了。",
        "The coordinate was not understood or is out of range: latitude 31n13 / 31.22 (±90), longitude 121e28 / 121.47 (±180); a hemisphere letter that does not fit the field usually means lat and lon are swapped."),
        "next_action": "fix_field_and_retry"},
    "tool.invalid_gender": {"kind": "input", "prompt_to_user": bilingual(
        "性别读不懂：请向用户确认男 / 女，传 1（男）或 0（女）。",
        "The gender was not understood: confirm male / female with the user and pass 1 (male) or 0 (female)."),
        "next_action": "ask_user_for_gender"},
    "tool.missing_gender": {"kind": "input", "prompt_to_user": bilingual(
        "这个技法的结果随性别而变（大运 / 大限顺逆、条文分男女），没有性别不起盘：请向用户问性别。",
        "This technique's result depends on gender (direction of luck cycles, gendered verses); ask the user for it before casting."),
        "next_action": "ask_user_for_gender"},
    "tool.missing_field": {"kind": "input", "prompt_to_user": bilingual(
        "缺必填字段：details.fields 逐项列出（用户才知道的事实去问用户，不要猜）。",
        "A required field is missing: details.fields lists each one (ask the user for facts only they know; never guess)."),
        "next_action": "fix_field_and_retry"},
    "tool.invalid_datetime": {"kind": "input", "prompt_to_user": bilingual(
        "推运目标时刻读不懂：传 YYYY（那一年）、YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS；时区放 dirZone。",
        "The target datetime was not understood: pass YYYY (that year), YYYY-MM-DD or YYYY-MM-DD HH:MM:SS; put the zone in dirZone."),
        "next_action": "fix_field_and_retry"},
    "tool.field_conflict": {"kind": "input", "prompt_to_user": bilingual(
        "同一件事在两个字段里给了不同的值：只在一处给（details.options 是两个候选）。",
        "Two fields give different values for the same thing: give it in one place only (details.options holds both candidates)."),
        "next_action": "fix_field_and_retry"},
    "tool.invalid_house_system": {"kind": "input", "prompt_to_user": bilingual(
        "宫制读不懂：传 details.options 里的索引或名称（如 3 / Placidus、0 / 整宫制）。",
        "The house system was not understood: pass an index or name from details.options (e.g. 3 / Placidus, 0 / whole sign)."),
        "next_action": "fix_field_and_retry"},
    "tool.invalid_zodiacal": {"kind": "input", "prompt_to_user": bilingual(
        "黄道制读不懂：0 = 回归黄道 tropical，1 = 恒星黄道 sidereal。", "The zodiac was not understood: 0 = tropical, 1 = sidereal."),
        "next_action": "fix_field_and_retry"},
    "tool.invalid_option": {"kind": "input", "prompt_to_user": bilingual(
        "设置值不在可选范围内：从 details.options（全表）里选一个。", "The setting value is not one of the accepted values: pick one from details.options (the full list)."),
        "next_action": "fix_field_and_retry"},
    "tool.confirmation_flag_not_boolean": {"kind": "input", "prompt_to_user": bilingual(
        "agent_confirmed_settings / defaults_accepted 必须是 JSON 布尔值 true（不是 \"true\"、1 或 \"yes\"），且只在用户真的确认后才传。",
        "agent_confirmed_settings / defaults_accepted must be the JSON boolean true (not \"true\", 1 or \"yes\"), and only after the user really confirmed."),
        "next_action": "fix_field_and_retry"},
    "tool.sixyao_invalid_cast": {"kind": "input", "prompt_to_user": bilingual(
        "六爻手动起卦的输入读不懂：lines 给六爻（自下而上，0/1 或 6/7/8/9），或 gua_code 给六位 0/1 或卦名；都不给就按时间起卦。",
        "The manual six-line cast was not understood: give six lines (bottom to top, 0/1 or 6/7/8/9) or gua_code as six 0/1 digits or a hexagram name; give neither to cast by time."),
        "next_action": "fix_field_and_retry"},
    "agent_guidance.required": {"kind": "input", "next_action": "ask_user_then_confirm"},
    # MCP-08：每个 ok:false 都要落到一条恢复规则（tests/test_mcp_error_contract.py 扫全部工具）。
    "tool.invalid_input": {"kind": "input", "next_action": "fix_input_per_message"},
    "tool.internal_error": {
        "kind": "retry_or_doctor",
        "prompt_to_user": bilingual(
            f"工具内部出了意外错误（不是你的输入问题）。可重试一次；仍失败请执行 `{DOCTOR_CMD}`，并把 details.exception_type 一并报告。",
            f"The tool hit an unexpected internal error (not an input problem). Retry once; if it persists run `{DOCTOR_CMD}` "
            "and report details.exception_type.",
        ),
        "next_action": "retry_then_doctor",
    },
    "report.format_unsupported": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "报告格式不支持：从 details.accepted 里选一个（json / docx / pdf / png / ics）。",
            "Unsupported report format: pick one of details.accepted (json / docx / pdf / png / ics).",
        ),
        "next_action": "pick_supported_format",
    },
    "knowledge.unknown_domain": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "知识库 domain 缺失或不认识：从 details.accepted 里选一个（\"user\" = 你自己的笔记）；不确定先用 horosa_knowledge_search。",
            "Missing or unknown knowledge domain: pick one of details.accepted (\"user\" = your own notes); unsure? use horosa_knowledge_search first.",
        ),
        "next_action": "pick_domain_from_accepted",
    },
    # dispatch 选中的技法全部 / 部分失败：顶层给一个码，恢复说明沿用第一个失败技法的（见 lift_failures）。
    "dispatch.tools_failed": {"kind": "retry_or_doctor", "next_action": "see_failed_tools"},
}

# ---------------------------------------------------------------------------------------------
# A-5 / C-13：按技法生成的错误码（`tool.<技法>_<族>`）走登记过的「族」，不再在调用处用 f-string 拼。
# 拼出来的码有两个毛病：静态扫描（verify_error_recovery.py）看不见它；族名不在后缀规则里（`inverted_window`、
# `span_too_large`）时 classify_code 落不到任何一条 → 信封没有 agent_recovery。码的拼写不变（技法名仍在码里，
# 也在 details.tool 里）：调用方、测试与 skill 文档引用的 `tool.qimenzeri_span_too_large` 这类码照旧有效。
# 引擎（horosa-core-js）回报的子码也在这里登记（它们是有限集合，见 horosa-core-js/src 里的 `code: '…'`）；
# 没登记的子码落到 `engine_failed`，原值放进 details.engine_code。
# ---------------------------------------------------------------------------------------------
TOOL_CODE_FAMILIES: dict[str, dict[str, _Any]] = {
    "bad_window": {"kind": "input", "next_action": "fix_window_dates"},
    "inverted_window": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "搜索窗倒置：结束日期早于起始日期。把 startDate / endDate 对调后重试。",
            "The search window is inverted (end before start): swap startDate / endDate and retry.",
        ),
        "next_action": "swap_window_bounds",
    },
    "span_too_large": {
        "kind": "input",
        "prompt_to_user": bilingual(
            "搜索窗超过这个技法的天数上限（details.max_span_days）。把窗口拆成几段分别搜索；上限只能调低不能调高。",
            "The search window exceeds this technique's day limit (details.max_span_days): split it into shorter ranges; the cap cannot be raised.",
        ),
        "next_action": "split_window",
    },
    "cast_geo_required": {"kind": "input", "next_action": "ask_user_for_place"},
    "invalid_option": {"kind": "input"},
    "invalid_setting": {"kind": "input"},
    "invalid_conditions": {"kind": "input"},
    "invalid_datetime": {"kind": "input"},
    "missing_window": {"kind": "input"},
    "missing_conditions": {"kind": "input"},
    "missing_inputs": {"kind": "input"},
    "missing_data": {"kind": "input"},
    "missing_chart": {"kind": "input"},
    "missing_explain_tree": {"kind": "retry_or_doctor"},
    "unknown_kind": {"kind": "input"},
    "unknown_region": {"kind": "input"},
    "unknown_region_candidate": {"kind": "input"},
    "incomplete_four_pillars": {"kind": "input"},
    "bad_nodetype": {"kind": "input"},
    "bad_lilithtype": {"kind": "input"},
    "empty": {"kind": "input"},
    "empty_snapshot": {"kind": "retry_or_doctor"},
    "empty_star_dignity": {"kind": "retry_or_doctor"},
    "empty_sihua_lines": {"kind": "retry_or_doctor"},
    "empty_period_lines": {"kind": "retry_or_doctor"},
    "base_chart_failed": {"kind": "retry_or_doctor"},
    "snapshot_failed": {"kind": "retry_or_doctor"},
    "scan_failed": {"kind": "retry_or_doctor"},
    "split_failed": {"kind": "retry_or_doctor"},
    "stitch_failed": {"kind": "retry_or_doctor"},
    "explain_section_failed": {"kind": "retry_or_doctor"},
    "star_dignity_build_failed": {"kind": "retry_or_doctor"},
    "sihua_build_failed": {"kind": "retry_or_doctor"},
    "period_build_failed": {"kind": "retry_or_doctor"},
    "card_builder_failed": {"kind": "retry_or_doctor"},
    "analysis_builder_failed": {"kind": "retry_or_doctor"},
    "engine_failed": {"kind": "retry_or_doctor"},
}
_TOOL_FAMILY_ORDER = tuple(sorted(TOOL_CODE_FAMILIES, key=len, reverse=True))  # 最长族名先配（scan_failed 先于 failed）


def tool_code(tool: str, family: str) -> str:
    """`tool.<tool>_<family>`；族必须登记过（拼错族名在这里就 KeyError，而不是变成一个落不到恢复规则的码）。"""
    if family not in TOOL_CODE_FAMILIES:
        raise KeyError(f"unregistered tool error-code family {family!r}: add it to errors.TOOL_CODE_FAMILIES")
    return f"tool.{tool}_{family}"


def engine_tool_code(tool: str, engine_code: _Any, default: str) -> str:
    """引擎回报的子码 → 登记过的族（未登记的落 `engine_failed`；原值请放进 details.engine_code）。"""
    family = f"{engine_code or ''}".strip()
    return tool_code(tool, family if family in TOOL_CODE_FAMILIES else (default if not family else "engine_failed"))


def _tool_family(code: str) -> str | None:
    if not code.startswith("tool."):
        return None
    body = code[len("tool."):]
    for family in _TOOL_FAMILY_ORDER:
        if body.endswith(f"_{family}") and len(body) > len(family) + 1:
            return family
    return None


RECOVERY_PREFIX_KINDS: tuple[tuple[str, str], ...] = (
    ("runtime.", "runtime"),
    ("transport.", "transport"),
    ("js_engine.", "js_engine"),
    ("client.", "environment"),
    ("openclaw.", "environment"),
    ("jev.", "decision_layer"),
)
_INPUT_SUFFIX = _re.compile(r"(missing|required|empty|invalid|unknown|bad_|unsupported|insufficient|traversal|mismatch|unsaved)")
_RETRY_SUFFIX = _re.compile(r"(failed|unavailable|timeout|not_found|_error$|^error$)")


def classify_code(code: str) -> tuple[str | None, str | None]:
    """错误码 → (kind, 来源)；来源 ∈ exact / family / prefix / suffix；都落不到 → (None, None)。"""
    text = f"{code or ''}".strip()
    if not text:
        return None, None
    entry = RECOVERY_TABLE.get(text)
    if entry is not None:
        return str(entry.get("kind") or "input"), "exact"
    family = _tool_family(text)
    if family is not None:
        return str(TOOL_CODE_FAMILIES[family]["kind"]), "family"
    # 基础设施前缀优先于通用后缀：js_engine.node_unavailable 要的是「装 runtime/设 HOROSA_NODE_BIN」，
    # 不是泛泛的「重试再体检」；runtime.* 同理（安装/体检语义比后缀更具体）。
    for prefix, kind in RECOVERY_PREFIX_KINDS:
        if text.startswith(prefix):
            return kind, "prefix"
    last = text.rsplit(".", 1)[-1]
    if _INPUT_SUFFIX.search(last):
        return "input", "suffix"
    if _RETRY_SUFFIX.search(last):
        return "retry_or_doctor", "suffix"
    return None, None


def validation_errors(exc: _Any) -> list[dict[str, _Any]]:
    """pydantic ValidationError → 能进信封的错误表。

    `exc.errors()` 的 `ctx.error` 是异常对象（字段校验器抛的 ValueError）：放进 details 就出不了进程，`json.dumps` 当场 TypeError，
    CLI 契约里的 exit 2 + JSON 变成 exit 1 + traceback。说明已经在 `msg` 里，`ctx` 与 `url` 都不要。
    """
    return exc.errors(include_url=False, include_context=False)


def recovery_for(code: str, details: dict[str, _Any] | None) -> dict[str, _Any]:
    """给 details 补 agent_recovery（kind/prompt_to_user/next_action[/commands]）与 hint；已带者不覆盖。"""
    result = dict(details) if isinstance(details, dict) else {}
    kind, source = classify_code(code)
    if kind is None:
        return result
    base = dict(RECOVERY_KINDS.get(kind) or RECOVERY_KINDS["input"])
    exact = RECOVERY_TABLE.get(f"{code}".strip()) or TOOL_CODE_FAMILIES.get(_tool_family(f"{code}".strip()) or "", {})
    recovery = {**base, **{k: v for k, v in exact.items() if k != "kind"}, "kind": kind, "code": f"{code}".strip(), "source": source}
    if "agent_recovery" not in result:
        result["agent_recovery"] = recovery
    elif isinstance(result["agent_recovery"], dict):
        for key in ("kind", "next_action", "prompt_to_user"):
            result["agent_recovery"].setdefault(key, recovery[key])
    result.setdefault("hint", recovery["prompt_to_user"])
    result.setdefault("next_action", recovery["next_action"])
    return result


def lift_failures(failures: dict[str, tuple[str, str, dict[str, _Any] | None]]) -> tuple[str, str, dict[str, _Any]] | None:
    """多技法结果（dispatch）里的失败 → 顶层的 (code, message, details)。

    🔴 MCP-08：dispatch 选中的技法全部失败（例如引擎没起），旧信封顶层 ok:false 而 code / message 都是 null——
    agent 得自己翻 results.<tool>.error 才知道发生了什么。现在：失败的码都一样 → 原样抬到顶层（同一条恢复说明）；
    码不一样 → `dispatch.tools_failed`，恢复说明沿用第一个失败的技法，details.failed_tools 列出每个技法的码。
    """
    if not failures:
        return None
    codes = {code for code, _message, _details in failures.values()}
    first_tool, (first_code, first_message, first_details) = next(iter(failures.items()))
    failed_tools = {tool: code for tool, (code, _m, _d) in failures.items()}
    if len(codes) == 1:
        details = recovery_for(first_code, {**(first_details or {}), "failed_tools": failed_tools})
        return first_code, first_message, details
    inherited = recovery_for(first_code, first_details).get("agent_recovery")
    details = recovery_for("dispatch.tools_failed", {
        "failed_tools": failed_tools, **({"agent_recovery": inherited} if inherited else {}),
    })
    message = bilingual(
        f"{len(failures)} 个技法失败，原因不同（见 details.failed_tools）；第一个是 {first_tool}：{first_message}",
        f"{len(failures)} techniques failed for different reasons (see details.failed_tools); first: {first_tool}: {first_message}",
    )
    return "dispatch.tools_failed", message, details
