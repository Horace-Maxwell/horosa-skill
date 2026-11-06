"""MCP 资源与提示词：只读目录与高频工作流，由 `create_mcp_server` 注册，不占 tools/list。"""
from __future__ import annotations

import json

from mcp.server.mcpserver import MCPServer

from horosa_skill.agent_guidance import build_technique_catalog
from horosa_skill.config import Settings
from horosa_skill.exports.registry import build_export_registry


def register_resources(mcp: MCPServer, settings: Settings) -> None:
    """MCP resources：只读目录以资源形态暴露（客户端可 @ 引用，不占 tools/list）。"""

    @mcp.resource(
        "horosa://catalog/techniques",
        name="horosa-technique-catalog",
        title="Horosa 技法目录 / technique catalog",
        description="All callable Horosa technique tools with one-line bilingual descriptions.",
        mime_type="text/markdown",
    )
    def technique_catalog_resource() -> str:
        return build_technique_catalog()

    @mcp.resource(
        "horosa://catalog/export-registry",
        name="horosa-export-registry",
        title="Horosa 导出契约注册表 / export contract registry",
        description="Machine-readable export contract (per-technique snapshot sections) mirrored from Xingque aiExport.",
        mime_type="application/json",
    )
    def export_registry_resource() -> str:
        return json.dumps(build_export_registry(), ensure_ascii=False, indent=2)

    @mcp.resource(
        "horosa://runtime/status",
        name="horosa-runtime-status",
        title="Horosa 本机 runtime 状态 / local runtime status",
        description=(
            "Where THIS server process looks for the offline runtime and local data (installed / runtime_root / "
            "data_dir / mode / version / knowledge_vectors). Read-only, never starts the runtime; `setup` compares it with the host."
        ),
        mime_type="application/json",
    )
    def runtime_status_resource() -> str:
        # 🔴 只读文件系统，绝不 start_local_services：这是 setup 的 stdio 探针在「客户端形状的环境」里读的第一样东西，
        # 用来抓「server 算出的 runtime 根 ≠ 终端里装的」（Codex 不转发 shell 环境 / GUI 客户端不读 shell 配置）。
        from horosa_skill import __version__ as _pkg_version
        from horosa_skill.knowledge import vectors as _vectors
        from horosa_skill.runtime.manager import HorosaRuntimeManager as _Manager

        manager = _Manager(settings)
        return json.dumps(
            {
                "installed": settings.runtime_current_dir.exists(),
                "runtime_root": str(settings.runtime_root),
                "data_dir": str(settings.data_dir),
                "mode": manager.runtime_mode(),
                "package_version": _pkg_version,
                "server_root": settings.server_root,
                "chart_server_root": settings.chart_server_root,
                # `setup --vectors` 的探针读这一项：依赖在不在这个 server 的环境里，只有这个进程自己知道。
                "knowledge_vectors": _vectors.status(settings),
            },
            ensure_ascii=False,
            indent=2,
        )


def register_prompts(mcp: MCPServer) -> None:
    """MCP prompts：高频工作流按钮化（Claude Code 里成为 /mcp__horosa__… 斜杠命令）。"""

    @mcp.prompt(
        name="quick_cast",
        title="快速起盘并解读 / quick cast & read",
        description="Cast one Horosa technique for a moment/birth and explain from the export snapshot.",
    )
    def prompt_quick_cast(technique: str = "", question: str = "") -> str:
        target = technique or "（按用户意图选择技法）"
        asked = question or "（用户尚未给出具体问题）"
        return (
            f"请用 Horosa 工具起一个「{target}」盘并解读。用户的问题：{asked}。\n"
            "流程：1) 若时间/地点/性别/流派等会改变结果的设置缺失，先按 horosa_agent_guidance 问我；"
            "2) 调用对应技法工具（用户确认后带 agent_confirmed_settings/defaults_accepted）；"
            "3) 只根据返回的 export_snapshot.export_text 分段解读——先结论、再证据段、再机会/风险/时机/建议；"
            "4) 不要手算任何术数结果。"
        )

    @mcp.prompt(
        name="annual_fortune",
        title="流年运势报告 / annual fortune report",
        description="Run the right predictive tools for a target year and produce a structured reading.",
    )
    def prompt_annual_fortune(year: str = "", birth: str = "") -> str:
        return (
            f"请为我做{year or '目标年份'}的流年运势分析（出生信息：{birth or '待我提供'}）。\n"
            "要求：1) 先确认目标年份、出生数据、地点时区等必需设置（缺了就问我）；"
            "2) 选择合适的推运工具（如 profection/solarreturn/bazi_direct/liureng_runyear），"
            "预测类必须带目标 datetime/dirZone 等字段；3) 每个结论都引用返回快照里的具体段落；"
            "4) 最后按 机会/风险/时机/建议 汇总。"
        )

    @mcp.prompt(
        name="export_report",
        title="导出正式报告 / export a formal report",
        description="Render the latest run into a DOCX/PDF consulting report with the AI analysis written back.",
    )
    def prompt_export_report(format: str = "docx") -> str:
        return (
            f"请把刚才的分析导出为 {format or 'docx'} 报告。\n"
            "流程：用已有 run_id 调 horosa_report_render（format + ai_report，分析会自动写回记忆；"
            "不要用 horosa_report_from_tool 重复起盘）。报告正文要像咨询报告：直接结论开头、"
            "引用盘面证据、机会/风险/时机/建议分列、保留「排盘规则」行；不要出现 run_id/JSON 等机器元数据。"
        )
