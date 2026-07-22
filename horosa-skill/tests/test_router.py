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



def test_router_xiaoliuren_excludes_liureng_both_ways() -> None:
    # 小六壬 含「六壬」二字，须与大六壬互斥（双向）。
    assert select_tools(DispatchInput.model_validate({"query": "小六壬测走失"})) == ["xiaoliuren"]
    assert select_tools(DispatchInput.model_validate({"query": "起小六壬看财"})) == ["xiaoliuren"]
    got = select_tools(DispatchInput.model_validate({"query": "大六壬起课问婚姻"}))
    assert "liureng_gods" in got and "xiaoliuren" not in got


def test_router_feigong_excludes_qimen_both_ways() -> None:
    # 飞宫小奇门 含「奇门」二字，须与奇门遁甲互斥（双向）。
    got = select_tools(DispatchInput.model_validate({"query": "飞宫小奇门问出行"}))
    assert "feigong" in got and "qimen" not in got
    got2 = select_tools(DispatchInput.model_validate({"query": "奇门遁甲排盘看事业"}))
    assert "qimen" in got2 and "feigong" not in got2
