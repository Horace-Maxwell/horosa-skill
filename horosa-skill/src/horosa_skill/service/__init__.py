"""星阙技法服务层：HorosaSkillService 由各 mixin 组合而成（v0.41.1 起 service.py 拆成本包，导入路径不变）。

分层（下层不依赖上层；runner 之间、api 与 runner 之间只经 self 互调）：
  _context / _clock / _common / endpoints          调用作用域、时钟、共用小工具、端点路由
  options_zeri / options_cn                        选项与载荷归一化
  text/*                                           快照文本构造（纯函数）
  export / envelope                                导出层与信封层
  remote / enrich                                  远端调用、跑完后的富化（mixin）
  runners/*                                        技法 runner（mixin，每族一个模块）
  api/*                                            run_tool / dispatch / hecan / 记忆与报告（mixin）
"""
from __future__ import annotations

from horosa_skill.config import Settings
from horosa_skill.decisions.layer import DecisionLayer
from horosa_skill.engine.client import HorosaApiClient, HorosaPlainJsonClient
from horosa_skill.engine.js_client import HorosaJsEngineClient
from horosa_skill.memory.store import MemoryStore
from horosa_skill.reports import ReportBuilder
from horosa_skill.runtime import HorosaRuntimeManager
from horosa_skill.service._common import _gender_label, _js_round
from horosa_skill.service._context import (
    _degrade,
    _degrade_collector,
    _progress_tick,
    progress_sink,
)
from horosa_skill.service.api.dispatch import DispatchAPI
from horosa_skill.service.api.reports import ReportsAPI
from horosa_skill.service.api.tools import ToolsAPI
from horosa_skill.service.endpoints import (
    _PYTHON_CHART_ENDPOINTS,
    _SHENSHU_ENDPOINTS,
    _chart_server_endpoint,
    _java_chart_payload,
    _java_chart_payload_candidates,
)
from horosa_skill.service.enrich import EnrichMixin
from horosa_skill.service.envelope import (
    _missing_sections_warning,
    _with_operational_recovery,
)
from horosa_skill.service.export import (
    TOOL_EXPORT_TECHNIQUE_MAP,
    _build_generated_export_snapshot,
)
from horosa_skill.service.options_cn import (
    _qimen_effective_options,
    _qimen_local_route_reasons,
)
from horosa_skill.service.options_zeri import (
    _clamped_max_span,
    _require_sane_window,
    _zeri_explain_rows,
)
from horosa_skill.service.remote import RemoteMixin
from horosa_skill.service.runners.astrodata import AstrodataRunners
from horosa_skill.service.runners.cn_divination import CnDivinationRunners
from horosa_skill.service.runners.guolao import GuolaoRunners
from horosa_skill.service.runners.horary_election import HoraryElectionRunners
from horosa_skill.service.runners.mingli import MingliRunners
from horosa_skill.service.runners.mundane import MundaneRunners
from horosa_skill.service.runners.predictive import PredictiveRunners
from horosa_skill.service.runners.sanshi import SanshiRunners
from horosa_skill.service.runners.shenshu import ShenshuRunners
from horosa_skill.service.runners.western import WesternRunners
from horosa_skill.service.runners.zeri import ZeriRunners
from horosa_skill.service.text.astro_core import (
    ASTRO_HOUSE_SYSTEM_TEXT,
    _build_nakshatra_lines,
    _build_natal_extra_sections,
)
from horosa_skill.service.text.chart_family import (
    _INDIA_SCHOOL_PRESETS,
    _STRONG_RECEPTION_DEFAULT_TOOLS,
    _build_astro_snapshot_text,
    _build_india_snapshot_text,
    _chart_family_snapshot_fields,
    _fixed_star_orb_params,
    _india_chart_remote_payload,
    _normalize_india_extra_vargas,
)
from horosa_skill.service.text.chinese import (
    _build_guolao_limit_lines,
    _build_jieqi_snapshot_text,
    _build_ziwei_snapshot_text,
    _derive_changed_gua_code,
    _derive_gua_code,
    _guolao_limit_table,
)
from horosa_skill.service.text.divination import _GEOMANCY_QUESTION_HOUSE
from horosa_skill.service.text.pd_zr import (
    _PD_METHOD_LABELS,
    _PD_TIME_KEY_LABELS,
    _pd_degree_text,
    _pd_direction_obj_text,
    _pd_split_degree_text,
    _primary_direction_method_text,
    _primary_direction_time_key_text,
    _zr_current_period_line,
)
from horosa_skill.service.text.predictive import (
    _PREDICTIVE_METHOD_NOTES,
    _build_persian_hits,
    _build_persianchart_section_text,
    _build_persiandirected_snapshot_text,
    _build_planetaryages_snapshot_text,
    _full_years_between,
)
from horosa_skill.service.text.western import (
    _build_otherbu_snapshot_text,
    _build_relative_snapshot_text,
    _dial_antiscion,
    _dial_mid,
    _dial_planetary_pictures,
    _dial_sep,
    _dice_chart_aspect_lines,
    _dice_chart_object_lines,
    _germany_house_frames_lines,
    _germany_rectify_lines,
)
from horosa_skill.time_basis import build_time_basis_line
from horosa_skill.tracing import TraceRecorder


class HorosaSkillService(
    RemoteMixin,
    EnrichMixin,
    SanshiRunners,
    ZeriRunners,
    MingliRunners,
    CnDivinationRunners,
    WesternRunners,
    AstrodataRunners,
    GuolaoRunners,
    PredictiveRunners,
    ShenshuRunners,
    HoraryElectionRunners,
    MundaneRunners,
    ToolsAPI,
    ReportsAPI,
    DispatchAPI,
):
    def __init__(
        self,
        settings: Settings,
        client: HorosaApiClient | None = None,
        chart_client: HorosaPlainJsonClient | HorosaApiClient | None = None,
        store: MemoryStore | None = None,
        js_client: HorosaJsEngineClient | None = None,
        runtime_manager: HorosaRuntimeManager | None = None,
        decision_layer: DecisionLayer | None = None,
    ) -> None:
        self.settings = settings
        self.client = client or HorosaApiClient(settings.server_root)
        self.chart_client = chart_client or (client if client is not None else HorosaPlainJsonClient(settings.chart_server_root))
        self.store = store or MemoryStore(settings)
        self.js_client = js_client or HorosaJsEngineClient(settings)
        self.runtime_manager = runtime_manager or HorosaRuntimeManager(settings)
        self.tracer = TraceRecorder(settings)
        self.report_builder = ReportBuilder()
        self._java_runtime_ready = False
        self._chart_runtime_ready = False
        # 可选云端决策层（v0.39.0）：HOROSA_JEV=off（缺省）→ None，本进程零对象、零网络。
        # 失败通过 _degrade 进 envelope.warnings（关闭式降级，禁静默）。测试注入桩走这个参数。
        self.decision_layer = (
            decision_layer
            if decision_layer is not None
            else DecisionLayer.from_settings(settings, degrade=lambda message: _degrade("%s", message, note=message))
        )


# 包外经 `horosa_skill.service.X` 读到的名字（tests/test_service_structure.py 冻结这份清单）。
__all__ = [
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
]
