"""命主档案 × 地名（v0.48.0 合并时接上）：save 只给地名时用技法载荷同一条 resolve_place_fields 补坐标与时区。

两个功能分头做完，单看都对：档案只存 `place` 文字标签、不解析；地名解析只认技法载荷。合起来的缺口是
「存档案时说『上海出生』」——档案里没坐标，之后每次起盘都得再问一遍地点。这里锁住接法：唯一命中才补、
歧义照样拒、显式坐标优先、只改备注不重查、换了地名 zone 跟新地名走。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.errors import ToolValidationError
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

CORE_JS = Path(__file__).resolve().parents[1] / "horosa-core-js"
requires_engine = pytest.mark.skipif(
    shutil.which("node") is None or not (CORE_JS / "node_modules" / "tz-lookup" / "tz.js").is_file(),
    reason="node + horosa-core-js node_modules (npm ci --omit=dev) required",
)


def _service(tmp_path: Path) -> HorosaSkillService:
    data = tmp_path / "data"
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=data,
                        db_path=data / "memory.db", output_dir=data / "runs", runtime_root=tmp_path / "rt")
    return HorosaSkillService(settings, store=MemoryStore(settings))


def _save(service: HorosaSkillService, name: str, data: dict) -> dict:
    return service.profile({"action": "save", "name": name, "data": data})


def _stored(service: HorosaSkillService, name: str) -> dict:
    return service.profile({"action": "get", "name": name})["profile"]


@requires_engine
def test_place_only_save_fills_coordinates_and_zone_from_the_birth_date(tmp_path: Path) -> None:
    """负向对照：profile() 不调 _profile_place_coordinates → 坐标没存上，红（实跑过）。"""
    service = _service(tmp_path)
    result = _save(service, "妈妈", {"date": "1988-07-01", "time": "08:00", "place": "上海", "gender": 0})
    fields = _stored(service, "妈妈")["payload"]
    assert (fields["lat"], fields["lon"], fields["zone"]) == ("31n13", "121e28", "+09:00")  # 1988 年夏令时
    assert _stored(service, "妈妈")["place"] == "上海"  # 标签照留
    assert result["place_resolution"]["status"] == "resolved" and result["place_resolution"]["zone_source"] == "place_and_date"
    assert "上海" in result["place_note"] and not any("上海" in note for note in result.get("warnings", []))


@requires_engine
def test_ambiguous_place_refuses_the_save_and_stores_nothing(tmp_path: Path) -> None:
    service = _service(tmp_path)
    with pytest.raises(ToolValidationError) as exc:
        _save(service, "老王", {"date": "1970-01-01", "time": "08:00", "place": "朝阳"})
    assert exc.value.code == "place.ambiguous" and exc.value.details["candidates"]
    assert service.profile({"action": "list"})["count"] == 0


@requires_engine
def test_explicit_coordinates_win_and_are_not_looked_up(tmp_path: Path) -> None:
    service = _service(tmp_path)
    result = _save(service, "我", {"date": "1990-05-18", "time": "08:30", "place": "朝阳", "lat": "41n34", "lon": "120e27",
                                   "zone": "+08:00"})
    assert "place_resolution" not in result
    fields = _stored(service, "我")["payload"]
    assert (fields["lat"], fields["lon"], fields["zone"]) == ("41n34", "120e27", "+08:00")


@requires_engine
def test_editing_notes_with_the_same_label_does_not_look_the_place_up_again(tmp_path: Path) -> None:
    """「朝阳」有歧义，但库里已有显式坐标：只改备注时不该因重查而被拒。负向对照：去掉「标签没变且已有坐标」短路 → 红（实跑过）。"""
    service = _service(tmp_path)
    _save(service, "我", {"date": "1990-05-18", "time": "08:30", "place": "朝阳", "lat": "41n34", "lon": "120e27", "zone": "+08:00"})
    result = _save(service, "我", {"place": "朝阳", "notes": "辽宁朝阳市"})
    assert result["ok"] is True and "place_resolution" not in result
    assert _stored(service, "我")["payload"]["lat"] == "41n34"


@requires_engine
def test_changing_the_place_takes_the_zone_from_the_new_place(tmp_path: Path) -> None:
    """旧 zone 是用户当时显式给的 +08:00；换成上海后（1990-07-01 夏令时）应取 +09:00，而不是沿用旧值。
    负向对照：把库里已存的 zone 也带进解析 → 解析把它当显式值留着，红（实跑过）。"""
    service = _service(tmp_path)
    _save(service, "爸爸", {"date": "1990-07-01", "time": "08:00", "lat": "39n54", "lon": "116e24", "zone": "+08:00", "place": "北京"})
    result = _save(service, "爸爸", {"place": "上海", "lat": None, "lon": None})
    fields = _stored(service, "爸爸")["payload"]
    assert (fields["lat"], fields["lon"], fields["zone"]) == ("31n13", "121e28", "+09:00")
    assert result["place_resolution"]["name"] == "上海"


@requires_engine
def test_cli_profile_save_resolves_the_place_like_the_facade(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """v0.48.0 的 CLI `profile` 直接调 run_action，绕过了地名解析：只给地名存下的档案没有坐标，之后拿它起盘被
    `tool.invalid_payload`（缺 zone / lat / lon）拒（Windows 原生复验实测）。负向对照：改回 run_action → 红（实跑过）。"""
    from horosa_skill.surfaces import cli

    monkeypatch.setattr(cli, "_service", lambda: _service(tmp_path))
    data = tmp_path / "mom.json"
    data.write_text(json.dumps({"date": "1988-07-01", "time": "08:00", "place": "上海", "gender": 0}, ensure_ascii=False),
                    encoding="utf-8")
    cli.profile("save", "妈妈", stdin=False, input_file=data, detail=False)
    saved = json.loads(capsys.readouterr().out)
    assert saved["place_resolution"]["status"] == "resolved"
    fields = saved["profile"]["payload"]
    assert (fields["lat"], fields["lon"], fields["zone"]) == ("31n13", "121e28", "+09:00")
