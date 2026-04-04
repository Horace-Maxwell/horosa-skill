from horosa_skill.engine.router import select_tools
from horosa_skill.schemas.tools import DispatchInput


def test_router_prefers_ziwei_when_query_mentions_it() -> None:
    request = DispatchInput.model_validate(
        {
            "query": "请做紫微分析",
            "birth": {"date": "1990-01-01", "time": "12:00", "zone": "8", "lat": "31n14", "lon": "121e28"},
        }
    )
    assert select_tools(request) == ["ziwei_birth"]


def test_router_defaults_to_chart_when_birth_exists() -> None:
    request = DispatchInput.model_validate(
        {
            "query": "请分析一下",
            "birth": {"date": "1990-01-01", "time": "12:00", "zone": "8", "lat": "31n14", "lon": "121e28"},
        }
    )
    assert select_tools(request) == ["chart"]


def test_router_handles_relative_keywords() -> None:
    request = DispatchInput.model_validate(
        {
            "query": "做关系合盘",
            "subject": {
                "inner": {"date": "1990-01-01", "time": "12:00", "zone": "8", "lat": "31n14", "lon": "121e28"},
                "outer": {"date": "1991-01-01", "time": "10:00", "zone": "8", "lat": "39n54", "lon": "116e23"},
            },
        }
    )
    assert select_tools(request) == ["relative"]

