from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService


def make_service(tmp_path) -> HorosaSkillService:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    return HorosaSkillService(settings, store=store)


def test_export_registry_returns_ai_export_catalog(tmp_path) -> None:
    service = make_service(tmp_path)

    result = service.run_tool("export_registry", {"technique": "qimen"}, save_result=False)

    assert result.ok is True
    assert result.data["settings_key"] == "horosa.ai.export.settings.v1"
    assert result.data["settings_version"] == 6
    assert result.data["selected_technique"]["key"] == "qimen"
    assert "奇门演卦" in result.data["selected_technique"]["preset_sections"]


def test_export_parse_normalizes_legacy_titles_and_filters_forbidden_sections(tmp_path) -> None:
    service = make_service(tmp_path)
    content = "\n".join(
        [
            "[起盘信息]",
            "排盘参数",
            "",
            "[右侧栏目]",
            "这里不该进入最终导出",
            "",
            "[八宫]",
            "这里是八宫详解内容",
            "",
            "[演卦]",
            "这里是奇门演卦内容",
        ]
    )

    result = service.run_tool(
        "export_parse",
        {
            "technique": "qimen",
            "content": content,
            "selected_sections": ["起盘信息", "八宫详解", "奇门演卦"],
        },
        save_result=False,
    )

    assert result.ok is True
    assert result.data["section_titles_detected"] == ["起盘信息", "盘面要素", "八宫详解", "奇门演卦"]
    assert "这里不该进入最终导出" not in result.data["export_text"]
    assert "这里是八宫详解内容" in result.data["export_text"]
    assert "这里是奇门演卦内容" in result.data["export_text"]


def test_export_parse_can_persist_memory(tmp_path) -> None:
    service = make_service(tmp_path)

    result = service.run_tool(
        "export_parse",
        {
            "technique": "bazi",
            "content": "[起盘信息]\n测试",
        },
        save_result=True,
    )

    assert result.ok is True
    assert result.memory_ref is not None
    queried = service.store.query_runs(tool="export_parse")
    assert len(queried) == 1
