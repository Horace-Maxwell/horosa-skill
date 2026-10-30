"""service 包的结构约束（v0.41.1 可维护性重构：service.py 18k 行拆成包）。

拆分只搬不改；这些测试锁住「搬完以后还能被安全地继续搬」的几条前提——每条都对应一种会让测试安静变绿的错法。
"""
from __future__ import annotations

import ast
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parents[1] / "src" / "horosa_skill" / "service"


def _modules() -> dict[str, ast.Module]:
    return {
        path.relative_to(SERVICE_DIR).as_posix(): ast.parse(path.read_text(encoding="utf-8"))
        for path in sorted(SERVICE_DIR.rglob("*.py"))
    }


def test_the_service_reads_the_clock_only_through_the_clock_seam() -> None:
    # 冻结时间的测试 patch 的是 service._clock.datetime；任何直接 `datetime.now(` 都会绕过它，
    # 那几条金标测试就会在真实「今天」上跑（今天对、明年错）。
    offenders = [
        f"{name}:{node.lineno}"
        for name, tree in _modules().items()
        if name != "_clock.py"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"now", "utcnow", "today"}
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in {"datetime", "date"}
    ]
    assert not offenders, f"read the time via `_clock.now(...)`: {offenders}"


# 包外经 `horosa_skill.service.X` 读到的名字（拆包时由全仓扫描得出：src / scripts / tests 的 import、属性访问、字符串目标）。
# 门面必须一直给得出它们；要删一个，先改完所有读它的地方再改这里。
EXTERNAL_NAMES = frozenset({
    "ASTRO_HOUSE_SYSTEM_TEXT",
    "HorosaSkillService",
    "TOOL_EXPORT_TECHNIQUE_MAP",
    "_GEOMANCY_QUESTION_HOUSE",
    "_INDIA_SCHOOL_PRESETS",
    "_PD_METHOD_LABELS",
    "_PD_TIME_KEY_LABELS",
    "_PREDICTIVE_METHOD_NOTES",
    "_PYTHON_CHART_ENDPOINTS",
    "_SHENSHU_ENDPOINTS",
    "_STRONG_RECEPTION_DEFAULT_TOOLS",
    "_build_astro_snapshot_text",
    "_build_generated_export_snapshot",
    "_build_guolao_limit_lines",
    "_build_india_snapshot_text",
    "_build_jieqi_snapshot_text",
    "_build_nakshatra_lines",
    "_build_natal_extra_sections",
    "_build_otherbu_snapshot_text",
    "_build_persian_hits",
    "_build_persianchart_section_text",
    "_build_persiandirected_snapshot_text",
    "_build_planetaryages_snapshot_text",
    "_build_relative_snapshot_text",
    "_build_ziwei_snapshot_text",
    "_chart_family_snapshot_fields",
    "_chart_server_endpoint",
    "_clamped_max_span",
    "_degrade",
    "_degrade_collector",
    "_derive_changed_gua_code",
    "_derive_gua_code",
    "_dial_antiscion",
    "_dial_mid",
    "_dial_planetary_pictures",
    "_dial_sep",
    "_dice_chart_aspect_lines",
    "_dice_chart_object_lines",
    "_fixed_star_orb_params",
    "_full_years_between",
    "_gender_label",
    "_germany_house_frames_lines",
    "_germany_rectify_lines",
    "_guolao_limit_table",
    "_india_chart_remote_payload",
    "_java_chart_payload",
    "_java_chart_payload_candidates",
    "_js_round",
    "_missing_sections_warning",
    "_normalize_india_extra_vargas",
    "_pd_degree_text",
    "_pd_direction_obj_text",
    "_pd_split_degree_text",
    "_primary_direction_method_text",
    "_primary_direction_time_key_text",
    "_progress_tick",
    "_qimen_effective_options",
    "_qimen_local_route_reasons",
    "_require_sane_window",
    "_with_operational_recovery",
    "_zeri_explain_rows",
    "_zr_current_period_line",
    "build_time_basis_line",
    "progress_sink",
})


def test_the_facade_still_exposes_every_name_other_code_reads() -> None:
    import horosa_skill.service as service

    missing = sorted(name for name in EXTERNAL_NAMES if not hasattr(service, name))
    assert not missing, f"horosa_skill.service no longer exposes: {missing}"


def test_mixins_never_define_the_same_member_twice() -> None:
    # 成员两两不相交 → MRO 顺序无关紧要；一旦重名，排在前面的 mixin 会安静地盖掉后面那个。
    from horosa_skill.service import HorosaSkillService

    seen: dict[str, str] = {}
    clashes = []
    for cls in HorosaSkillService.__mro__[:-1]:
        for name in vars(cls):
            if name.startswith("__") and name.endswith("__"):
                continue
            if name in seen:
                clashes.append(f"{name}: {seen[name]} / {cls.__name__}")
            seen[name] = cls.__name__
    assert not clashes, clashes


_MIXIN_LAYERS = ("remote", "enrich", "runners", "api")


def _package_imports(name: str, tree: ast.Module) -> set[str]:
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("horosa_skill.service"):
            if node.module != "horosa_skill.service":
                out.add(node.module)
                continue
            for alias in node.names:  # `from horosa_skill.service import _clock` = importing a submodule: fine
                is_submodule = (SERVICE_DIR / f"{alias.name}.py").is_file() or (SERVICE_DIR / alias.name).is_dir()
                out.add(f"horosa_skill.service.{alias.name}" if is_submodule else "horosa_skill.service")
    return out


def test_layering_runners_and_api_only_meet_through_self() -> None:
    # runner 之间、api 与 runner 之间只经 self 互调（测试会在实例上替换 run_tool / _run_qimen_tool 等）；
    # 下层（text / options / export / envelope / endpoints / _common…）不得反向依赖 mixin 层。
    problems = []
    for name, tree in _modules().items():
        if name == "__init__.py":
            continue
        layer = name.split("/")[0].removesuffix(".py")
        for module in _package_imports(name, tree):
            target = module.removeprefix("horosa_skill.service").lstrip(".").split(".")[0]
            if module == "horosa_skill.service":
                problems.append(f"{name} imports from the package root (half-initialised while __init__ runs)")
            elif layer == "runners" and target in {"runners", "api"}:
                problems.append(f"{name} imports {module}")
            elif layer == "api" and target == "runners":
                problems.append(f"{name} imports {module}")
            elif layer not in _MIXIN_LAYERS and target in _MIXIN_LAYERS:
                problems.append(f"{name} (lower layer) imports {module}")
    assert not problems, problems
