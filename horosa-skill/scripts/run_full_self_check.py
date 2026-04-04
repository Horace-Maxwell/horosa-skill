from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from horosa_skill.config import Settings
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.runtime import HorosaRuntimeManager
from horosa_skill.service import TOOL_EXPORT_TECHNIQUE_MAP, HorosaSkillService


def build_payloads() -> dict[str, dict]:
    base_birth = {
        "date": "2028/04/06",
        "time": "09:33:00",
        "zone": "+00:00",
        "lat": "41n26",
        "lon": "174w30",
        "gpsLat": -41.433333,
        "gpsLon": 174.5,
        "hsys": 1,
        "tradition": False,
        "predictive": True,
        "zodiacal": 0,
        "simpleAsp": False,
        "strongRecption": False,
        "virtualPointReceiveAsp": True,
        "southchart": False,
        "ad": 1,
        "name": "Horosa Smoke",
        "pos": "Wellington",
    }
    east_birth = {
        "date": "2028-04-06",
        "time": "09:33:00",
        "zone": "+08:00",
        "lat": "31n13",
        "lon": "121e28",
        "gpsLat": 31.2167,
        "gpsLon": 121.4667,
        "ad": 1,
    }
    return {
        "export_registry": {"technique": "qimen"},
        "export_parse": {
            "technique": "qimen",
            "content": (
                "[起盘信息]\n日期：2028-04-06 09:33:00\n\n"
                "[八宫]\n坎一宫：值符=天蓬；值使=休门\n\n"
                "[演卦]\n值符值使演卦：天泽履之乾为天\n"
            ),
            "selected_sections": ["起盘信息", "八宫详解", "奇门演卦"],
        },
        "qimen": dict(east_birth),
        "taiyi": dict(east_birth),
        "jinkou": {**east_birth, "diFen": "酉", "guirengType": 0},
        "chart": dict(base_birth),
        "chart13": {**base_birth, "predictive": 0},
        "solarreturn": {**base_birth, "datetime": "2031-04-06 09:33:00", "dirZone": "+08:00", "dirLat": "31n13", "dirLon": "121e28"},
        "lunarreturn": {**base_birth, "datetime": "2031-04-06 09:33:00", "dirZone": "+08:00", "dirLat": "31n13", "dirLon": "121e28"},
        "solararc": {**base_birth, "datetime": "2031-04-06 09:33:00", "dirZone": "+00:00"},
        "givenyear": {**base_birth, "datetime": "2031-04-06 09:33:00", "dirZone": "+08:00", "dirLat": "31n13", "dirLon": "121e28"},
        "profection": {**base_birth, "datetime": "2031-04-06 09:33:00", "dirZone": "+00:00"},
        "pd": {**base_birth, "pdtype": 0, "pdMethod": "astroapp_alchabitius", "pdTimeKey": "Ptolemy", "pdaspects": [0, 60, 90, 120, 180]},
        "pdchart": {**base_birth, "pdtype": 0, "pdMethod": "astroapp_alchabitius", "pdTimeKey": "Ptolemy", "showPdBounds": 1, "datetime": "2031-04-06 09:33:00", "dirZone": "+00:00"},
        "zr": dict(base_birth),
        "relative": {
            "inner": {**base_birth, "name": "甲"},
            "outer": {**base_birth, "date": "1992/03/02", "time": "08:18:00", "name": "乙"},
            "hsys": 0,
            "zodiacal": 0,
            "relative": 0,
        },
        "india_chart": {**base_birth, "zodiacal": 1, "predictive": 1, "pdtype": 0, "pdMethod": "astroapp_alchabitius", "pdTimeKey": "Ptolemy", "pdaspects": [0, 60, 90, 120, 180]},
        "ziwei_birth": {**east_birth, "gender": True, "timeAlg": 0},
        "ziwei_rules": {},
        "bazi_birth": dict(east_birth),
        "bazi_direct": {**east_birth, "gender": True, "timeAlg": 0, "after23NewDay": 0, "adjustJieqi": False, "byLon": False, "phaseType": 0},
        "liureng_gods": {**east_birth, "after23NewDay": False},
        "liureng_runyear": {
            **east_birth,
            "date": "2020-04-06",
            "gender": True,
            "guaDate": "2028-04-06",
            "guaTime": "09:33:00",
            "guaZone": "+08:00",
            "guaLat": "31n13",
            "guaLon": "121e28",
            "guaAd": 1,
            "guaAfter23NewDay": False,
        },
        "jieqi_year": {
            "year": 2028,
            "zone": "+08:00",
            "lat": "31n13",
            "lon": "121e28",
            "gpsLat": 31.2167,
            "gpsLon": 121.4667,
            "hsys": 1,
            "zodiacal": 0,
            "doubingSu28": False,
            "jieqis": ["春分", "夏至", "秋分", "冬至"],
            "ad": 1,
        },
        "nongli_time": {
            "date": "2028-04-06",
            "time": "09:33:00",
            "zone": "+08:00",
            "lat": "31n13",
            "lon": "121e28",
            "gpsLat": 31.2167,
            "gpsLon": 121.4667,
            "gender": True,
            "after23NewDay": 0,
            "timeAlg": 0,
            "ad": 1,
        },
        "gua_desc": {"name": ["111111", "000000", "101010"]},
        "gua_meiyi": {"name": ["111", "000"]},
    }


def run_self_check() -> dict:
    payloads = build_payloads()
    with tempfile.TemporaryDirectory(prefix="horosa-selfcheck-") as tmp_dir:
        tmp_root = Path(tmp_dir)
        settings = Settings.from_env().model_copy(
            update={
                "db_path": tmp_root / "memory.db",
                "output_dir": tmp_root / "runs",
            }
        )
        manager = HorosaRuntimeManager(settings)
        service = HorosaSkillService(settings)
        tool_results: list[dict] = []
        dispatch_result: dict | None = None
        manager.start_local_services()
        try:
            for tool_name in TOOL_DEFINITIONS:
                payload = payloads[tool_name]
                result = service.run_tool(tool_name, payload, save_result=True)
                queried = service.store.query_runs(tool=tool_name, include_payload=True)
                artifact_payload = queried[0]["artifacts"][0]["payload"] if queried else {}
                tool_results.append(
                    {
                        "tool": tool_name,
                        "ok": result.ok,
                        "retrieved_runs": len(queried),
                        "artifact_exists": bool(result.memory_ref and Path(result.memory_ref.artifact_path).is_file()),
                        "stored_payload_ok": artifact_payload.get("ok") == result.ok if artifact_payload else False,
                        "has_export_snapshot": isinstance(result.data.get("export_snapshot"), dict),
                        "has_export_format": isinstance(result.data.get("export_format"), dict),
                        "export_sections_count": len(result.data.get("export_format", {}).get("sections", [])) if isinstance(result.data, dict) else 0,
                        "summary": result.summary,
                        "memory_ref": result.memory_ref.model_dump(mode="json") if result.memory_ref else None,
                    }
                )

            dispatch_payload = {
                "query": "请综合奇门、西占和六壬分析测试对象甲当前的状态",
                "subject": {"name": "甲"},
                "birth": payloads["qimen"],
                "save_result": True,
            }
            dispatch = service.dispatch(dispatch_payload)
            queried_dispatch = service.store.query_runs(entity="甲", include_payload=True)
            dispatch_result = {
                "ok": dispatch.ok,
                "selected_tools": dispatch.selected_tools,
                "memory_ref": dispatch.memory_ref.model_dump(mode="json") if dispatch.memory_ref else None,
                "retrieved_runs": len(queried_dispatch),
                "results_ok": {name: one.ok for name, one in dispatch.results.items()},
            }
        finally:
            manager.stop_local_services()

    failed_tools = [item["tool"] for item in tool_results if not item["ok"] or item["retrieved_runs"] < 1 or not item["artifact_exists"] or not item["stored_payload_ok"]]
    missing_export = [
        item["tool"]
        for item in tool_results
        if item["tool"] in TOOL_EXPORT_TECHNIQUE_MAP and (not item["has_export_snapshot"] or not item["has_export_format"])
    ]
    return {
        "generated_at": datetime.now(ZoneInfo("America/Los_Angeles")).isoformat(),
        "tool_count": len(tool_results),
        "tools": tool_results,
        "dispatch": dispatch_result,
        "failed_tools": failed_tools,
        "missing_export_contract_tools": missing_export,
        "ok": not failed_tools and not missing_export and bool(dispatch_result and dispatch_result["ok"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full Horosa skill self-check.")
    parser.add_argument("--output", type=Path, help="Optional output path for the JSON report.")
    args = parser.parse_args()

    report = run_self_check()
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
